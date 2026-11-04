# ── Trace ──────────────────────────────────────────────
# Change:  CR-039 wave C tasks 12-13 — *"an owner as a typed record (kind ·
#          contact · linked to the customer they already are)"* and *"migrate
#          the free-text names"*. Unblocked by the PO ruling of 2026-08-27,
#          verbatim: *"category is okay, no richer text"*.
# Rules:   BR-MET-150 (the typed record) · BR-MET-151 (matching, never
#          guessing) · BR-TEN-150 (the category vocabulary) · BR-MET-035
#          (server-enforced roles) · BR-MET-048 (every change audited)
# Question: OQ-500 (does the typed owner become the default payer? — NOT
#          decided, and this module deliberately changes nothing about it) ·
#          OQ-501 (is `owner_manager` retired?) · OQ-503 (must a paying owner
#          carry a contact method?)
# Screens: S14 premises list · S16 guided add · PRM-01 edit modal ·
#          PRM-04 the owner-matching review surface
# Tests:   06-backend/tests/test_cr039_c12_premises_owner.py ·
#          06-backend/tests/test_cr039_c13_owner_migration.py
# ───────────────────────────────────────────────────────
"""Premises owners — the typed party record, its writes and its matching.

⛔ **CR-058 W3 (2026-09-01) — `BR-MET-1030`: this module gained the caller the
premises import walks through.** `ensure_master_account_for_premises` is the one
entry; it reaches `customers.create_master_account` through the seam, exactly as
`ensure_owner_master_account` does for New Connect, and writes the declared
`master_account_id` link through the single `_link_created_master_account`
writer. **There is no second account-creation path in this module and there must
never be** — customers owns `accounts` (B1/B2 §2). This also closes `CR-056`
task 24, whose whole content was *the caller that never existed*.

**A SEPARATE MODULE RATHER THAN MORE OF `services.py`, and the reason is
mechanical rather than aesthetic.** `apps/metering/services.py` is six thousand
lines and is edited by several lanes in the same session; CLAUDE.md law 11's
fourth and fifth occurrences are both *two lanes, one file*. Everything here is
NEW behaviour with no existing caller, so it costs nothing to keep it out of
that file. `services.py` gains exactly two hunks: the `owner_id` key on
`_validate_premises` and the re-export below.

WHAT THIS MODULE REFUSES TO DO, STATED FIRST
--------------------------------------------
1. **It never derives a CATEGORY from a NAME.** BR-MET-151 clause 3: *Whitfield
   Rentals LLC* is not evidence of a landlord and *Chen, David* is not evidence
   of an owner-occupier. There is no heuristic here, no suffix table and no
   "smart" default — `create_premises_owner` REFUSES a payload with no category
   rather than choosing one, and that refusal is the whole point of the task.
2. **It never writes `customers`.** The `customer` link is a POINTER (B2
   addendum r21). The id is validated by asking the customers module through
   `seams`, and nothing is inserted, updated or read out of that module's ORM.
3. **It never changes who gets billed.** `customers.services.open_account`
   still reads `premises.owner_manager`; making it read the typed owner instead
   is `OQ-500` and is a money decision nobody has taken.
"""

from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.metering import models
from apps.tenancy import models as tenancy_models
from core import errors
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

from apps.metering.services import (  # noqa: E402 — shared plumbing, single source
    _audit,
    _field_error,
    _payload_dict,
    _refuse_fields,
    _tenant_id,
    _text,
)

#: The payload keys this module accepts. Anything else is REFUSED by name
#: rather than ignored — an ignored key is how a caller comes to believe it set
#: something it did not (the posture `_validate_premises` already takes).
#:
#: ⚠ **THERE IS NO `notes`, `description` OR `comment` KEY, AND THERE MUST NOT
#: BE.** PO 2026-08-27: *"category is okay, no richer text"*. The option that
#: sentence rejected was *keep the free-text box and make it longer*; a notes
#: column on this record would be that option, arriving one row lower down.
OWNER_FIELDS: frozenset[str] = frozenset(
    {
        "category",
        "category_code",
        "name",
        "contact_name",
        "email",
        "phone",
        # ⛔ CR-056 W3 task 18 — `customer_id` STAYS IN THIS SET AND IS REFUSED
        # ONE STEP LATER, BY NAME. Removing it here would make the refusal read
        # "unknown field", which tells a caller nothing about where the link
        # now lives. See `_refuse_customer_shortcut` and `BR-MET-1020`.
        "customer_id",
        "source_owner_manager",
    }
)


def _owner_row(owner_id: Any, *, locked: bool = False) -> models.PremisesOwner:
    qs = models.PremisesOwner.objects.filter(tenant_id=_tenant_id(), pk=owner_id)
    if locked:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _resolve_category(payload: dict[str, Any], fe: list[dict[str, Any]]) -> Any:
    """The category, by id or by code, from the CURRENT tenant's own list.

    ⚠ **REQUIRED, AND ITS ABSENCE IS A REFUSAL RATHER THAN A DEFAULT.** A
    record with no category is the free-text box the PO ruled against on
    2026-08-27; picking `landlord` because it is the commonest would be this
    code answering a question about a real party on the utility's behalf. The
    same posture `_jurisdiction_flag` takes for the same class of reason.
    """
    raw = payload.get("category", payload.get("category_code"))
    value = _text(raw, 120)
    if value is None:
        fe.append(
            _field_error(
                "category",
                errors.VAL_REQUIRED,
                "metering.premises_owner.category_required",
            )
        )
        return None
    qs = tenancy_models.PremisesOwnerCategory.objects.filter(tenant_id=_tenant_id())
    row = qs.filter(code__iexact=value).first()
    if row is None:
        try:
            row = qs.filter(pk=UUID(str(value))).first()
        except (ValueError, AttributeError, TypeError):
            row = None
    if row is None:
        fe.append(
            _field_error(
                "category",
                errors.VAL_UNKNOWN_LOOKUP,
                "metering.premises_owner.category_unknown",
                value=value,
                allowed=list(qs.filter(active=True).values_list("code", flat=True)),
            )
        )
        return None
    if not row.active:
        # BR-TEN-036's deactivate-first: a retired category may keep the owners
        # already on it and may not take a new one. Refused by NAME so the
        # clerk is told which word is retired rather than being shown an empty
        # picker.
        fe.append(
            _field_error(
                "category",
                errors.VAL_UNKNOWN_LOOKUP,
                "metering.premises_owner.category_inactive",
                value=row.code,
            )
        )
        return None
    return row


#: ⛔ **CR-056 W3 TASK 18 — `BR-MET-1020`. THE OWNER→CUSTOMER SHORTCUT IS RULED
#: OUT, AND THIS IS THE DOOR THAT ENFORCES IT.**
#:
#: Two paths reached the same person and one of them skipped the only thing
#: that holds a balance:
#:
#:     premises_owner ──customer_id──────────────────────────────► customer
#:     premises_owner ──master_account_id──► account ──link──────► customer
#:
#: **The second is the ruled path** (PO 2026-08-31, CR-056 ruling 1: *"a Master
#: Account is the owner's account at an address"*, and `BR-MET-400`'s own words,
#: *"Premises -> owner = Master account"*). The first reaches a party that holds
#: no balance, receives no bill and cannot be posted to — so a lane resolving
#: *"who owns this address"* through it gets a NAME where it needed an ACCOUNT,
#: which is `DEF-650` again, wearing a foreign key.
#:
#: ⚠ **THE COLUMN IS NOT DROPPED, AND THAT IS A DELIBERATE LIMIT ON THIS
#: LANE.** `BR-MET-150` is a PO ruling and it asked for this link in its own
#: words — *"linked to the customer they already are"*. That INTENT is fully
#: served through the account: the fact *this owner is that customer* is still
#: recorded, one hop further along, on the row that also holds the money.
#: Removing the physical column would additionally reverse the ruling's own
#: sentence, which is a supersession only the PO can state (CLAUDE.md law 13),
#: and it would destroy existing rows. It is `OQ-1240`, open and non-blocking.
#:
#: What this lane DOES do, which is what *"rule it out explicitly rather than
#: leaving it to drift"* asks for: the write door refuses the field BY NAME with
#: its reason, and `owner_selectors.owner_detail_dict` answers the question from
#: the ACCOUNT. A column nothing writes and nothing reads to decide anything
#: cannot drift.
CUSTOMER_SHORTCUT_REFUSED: dict[str, str] = {
    "br_ref": "BR-MET-1020",
    "reason": (
        "an owner is reached through the master account, which is the only thing that holds a "
        "balance — set `master_account_id` and link the customer on that account instead"
    ),
}


def _refuse_customer_shortcut(payload: dict[str, Any], fe: list[dict[str, Any]]) -> None:
    """`BR-MET-1020` — refuse `customer_id` BY NAME, never by ignoring it.

    An ignored key is how a caller comes to believe it set something it did
    not, which is the posture this module already takes on every unknown field.
    The refusal names the path that DOES work, because a refusal that only says
    *no* leaves the clerk with the same job and no way to do it.
    """
    if "customer_id" not in payload:
        return
    if payload.get("customer_id") in (None, ""):
        # Clearing a column that no longer decides anything is not an attempt
        # to use the shortcut, and refusing it would trap a caller that sends
        # its whole form back with the field blank.
        return
    fe.append(
        _field_error(
            "customer_id",
            errors.VAL_FORMAT,
            "metering.premises_owner.customer_via_account",
            **CUSTOMER_SHORTCUT_REFUSED,
        )
    )


def _validate_owner(payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    for field in payload:
        if field not in OWNER_FIELDS:
            fe.append(_field_error(field, errors.VAL_FORMAT, "metering.unknown_field"))
    _refuse_fields(fe)

    if not partial or "category" in payload or "category_code" in payload:
        category = _resolve_category(payload, fe)
        if category is not None:
            out["category"] = category
    if not partial or "name" in payload:
        name = _text(payload.get("name"), 200)
        if not name:
            fe.append(
                _field_error("name", errors.VAL_REQUIRED, "metering.premises_owner.name_required")
            )
        out["name"] = name
    for field, limit in (("contact_name", 200), ("email", 254), ("phone", 40)):
        if field in payload:
            out[field] = _text(payload[field], limit)
    # CR-056 W3 task 18 · BR-MET-1020 — the shortcut is refused, not resolved.
    # `out` never carries `customer_id`, so no write path can reach the column.
    _refuse_customer_shortcut(payload, fe)
    if "source_owner_manager" in payload:
        out["source_owner_manager"] = _text(payload["source_owner_manager"], 200)
    _refuse_fields(fe)
    return out


def _duplicate_name_error(name: str | None) -> None:
    """The `uq_premises_owners_tenant_name_ci` refusal, turned into an answer.

    ⚠ **THIS IS WHY THE INDEX EXISTS AT ALL.** The ruling's reason for a typed
    record is *"the same landlord across twelve addresses is one party rather
    than twelve unrelated strings"*. Matching happens one premises at a time, so
    without the index a clerk working down the review list creates twelve
    parties called *Whitfield Rentals LLC* and the change achieves nothing while
    appearing to work. The clerk is told to LINK to the one that exists.
    """
    existing = (
        models.PremisesOwner.objects.filter(tenant_id=_tenant_id(), name__iexact=name or "")
        .values("id", "name")
        .first()
    )
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-MET-150",
        message_key="metering.premises_owner.name_taken",
        params={
            "name": name,
            "owner_id": str(existing["id"]) if existing else None,
        },
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def create_premises_owner(actor: Any, payload: Any) -> dict[str, Any]:
    """One typed owner (BR-MET-150). ONE transaction, audited (BR-MET-048)."""
    from apps.metering import owner_selectors

    cleaned = _validate_owner(_payload_dict(payload), partial=False)
    with transaction.atomic():
        try:
            # ⚠ **INNER `atomic()` IS A SAVEPOINT AND IT IS LOAD-BEARING, NOT
            # DECORATION.** An `IntegrityError` marks the enclosing transaction
            # broken, so the very next query — `_duplicate_name_error`'s lookup
            # of the party that already exists — raises
            # `TransactionManagementError` and the clerk gets a 500 instead of
            # *"this owner already exists, link to it"*. Rolling back to a
            # savepoint restores a usable transaction. Caught in test
            # `…__one_party_not_twelve_strings__a_duplicate_name_is_refused`,
            # which failed on exactly this before the savepoint existed.
            with transaction.atomic():
                row = models.PremisesOwner.objects.create(tenant_id=_tenant_id(), **cleaned)
        except IntegrityError:
            _duplicate_name_error(cleaned.get("name"))
        _audit(
            actor,
            "premises_owner.created",
            "premises_owner",
            row.id,
            after=owner_selectors.owner_detail_dict(row),
        )
    return owner_selectors.owner_detail_dict(_owner_row(row.pk))


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def update_premises_owner(actor: Any, owner_id: Any, changes: Any) -> dict[str, Any]:
    """Edit a typed owner. An absent key means *leave it alone*; an explicit
    empty string CLEARS a contact field — the same three-state posture
    `_validate_premises` takes for `services_available` and the area tag.

    ⚠ **CHANGING A NAME HERE CHANGES IT AT EVERY ADDRESS THAT POINTS AT IT**,
    which is the ruling's own intent (*"one party rather than twelve unrelated
    strings"*) and worth knowing before pressing save. It does NOT touch any
    premises' `owner_manager` — that column is BR-MET-151's provenance and the
    thing `open_account` reads (`OQ-500`).
    """
    from apps.metering import owner_selectors

    cleaned = _validate_owner(_payload_dict(changes), partial=True)
    with transaction.atomic():
        row = _owner_row(owner_id, locked=True)
        before = owner_selectors.owner_detail_dict(row)
        fields: list[str] = []
        for field, value in cleaned.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                fields.append(field)
        if fields:
            try:
                with transaction.atomic():  # savepoint — see create_premises_owner
                    row.save(update_fields=[*fields, "updated_at"])
            except IntegrityError:
                _duplicate_name_error(cleaned.get("name"))
            _audit(
                actor,
                "premises_owner.updated",
                "premises_owner",
                row.id,
                before=before,
                after=owner_selectors.owner_detail_dict(row),
            )
    return owner_selectors.owner_detail_dict(_owner_row(owner_id))


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def deactivate_premises_owner(actor: Any, owner_id: Any) -> dict[str, Any]:
    """IS-1 deactivate-first, and the blockers are NAMED.

    An owner that addresses still point at cannot be retired: the premises would
    keep a link to a party the product has stopped offering, and re-activating
    later would be indistinguishable from never having deactivated. The
    addresses are listed in the refusal, exactly as `deactivate_premises` lists
    its blocking units, because *"it is in use"* is not an answer a clerk can act
    on.
    """
    from apps.metering import owner_selectors

    with transaction.atomic():
        row = _owner_row(owner_id, locked=True)
        blockers = list(
            models.Premises.objects.filter(
                tenant_id=_tenant_id(), owner_id=row.id, deleted_at__isnull=True
            ).values_list("address_line", flat=True)[:20]
        )
        if blockers:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-150",
                message_key="metering.premises_owner.deactivate_blocked",
                params={"blockers": blockers},
            )
        before = {"active": row.active}
        row.active = False
        row.save(update_fields=["active", "updated_at"])
        _audit(
            actor,
            "premises_owner.deactivated",
            "premises_owner",
            row.id,
            before=before,
            after={"active": False},
        )
    return owner_selectors.owner_detail_dict(_owner_row(owner_id))


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def match_premises_owner(actor: Any, premises_id: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-151 — a PERSON matches one free-text name to one typed party.

    **This function is the whole of task 13's "flagged migration".** The
    migration itself (`metering 0040`) writes nothing; the names move one at a
    time, through here, because the PO's caveat says so in as many words: *"A
    flagged migration that offers each name for matching is the shape; silently
    guessing which string is which party is not."*

    Two shapes of payload, and no third:

      ``{"owner_id": "<uuid>"}``      LINK this address to a party that exists.
      ``{"category": "landlord", …}`` CREATE the party, then link — and the
                                      CATEGORY IS THE CALLER'S, always. The
                                      free-text name is offered as the default
                                      `name`, which is the only thing about the
                                      string this code is willing to reuse.

    ⚠ **THE PREMISES' `owner_manager` IS NOT CLEARED, AND THAT IS DELIBERATE**
    (BR-MET-151 clause 4). It is the provenance of this match, it is what
    `customers.services.open_account` reads for the default payer, and whether
    the typed owner should supersede it is `OQ-500` — a money decision nobody
    has taken. Clearing it here would take that decision by accident, on a
    screen a clerk opened to tidy up a name.
    """
    from apps.metering import owner_selectors
    from apps.metering import selectors as metering_selectors
    from apps.metering.services import _premises_row

    data = _payload_dict(payload)
    with transaction.atomic():
        premises = _premises_row(premises_id, locked=True)
        if "owner_id" in data:
            unexpected = sorted(set(data) - {"owner_id"})
            if unexpected:
                _refuse_fields(
                    [
                        _field_error(
                            field,
                            errors.VAL_FORMAT,
                            "metering.premises_owner.link_takes_only_owner_id",
                        )
                        for field in unexpected
                    ]
                )
            owner = _owner_row(data["owner_id"], locked=True)
            if not owner.active:
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-MET-150",
                    message_key="metering.premises_owner.owner_inactive",
                    params={"owner_id": str(owner.id)},
                )
        else:
            # The free text is offered as the DEFAULT name and never as the
            # default category (BR-MET-151 clause 3).
            create_payload = {"source_owner_manager": premises.owner_manager, **data}
            create_payload.setdefault("name", premises.owner_manager)
            cleaned = _validate_owner(create_payload, partial=False)
            try:
                with transaction.atomic():  # savepoint — see create_premises_owner
                    owner = models.PremisesOwner.objects.create(tenant_id=_tenant_id(), **cleaned)
            except IntegrityError:
                _duplicate_name_error(cleaned.get("name"))
            _audit(
                actor,
                "premises_owner.created",
                "premises_owner",
                owner.id,
                after=owner_selectors.owner_detail_dict(owner),
            )
        before = metering_selectors.premises_detail_dict(premises)
        premises.owner_id = owner.id
        premises.save(update_fields=["owner", "updated_at"])
        _audit(
            actor,
            "premises.owner_matched",
            "premises",
            premises.id,
            before=before,
            after=metering_selectors.premises_detail_dict(premises),
        )
    return {
        "premises": metering_selectors.premises_detail_dict(_premises_row(premises_id)),
        "owner": owner_selectors.owner_detail_dict(_owner_row(owner.pk)),
    }


def unmatched_premises_qs():
    """BR-MET-151 clause 2 — *unmatched* is COMPUTED, never a stored column.

    A premises is unmatched when it holds a free-text owner name and points at
    no typed owner. Two columns already answer it, so a third `migration_status`
    column would be a second copy of a fact that already has an owner — which is
    how two numbers come to disagree (decision log 2026-08-27 §3).

    Everything downstream of this — the review list, its count, the badge on
    S14 — reads THIS queryset, so there is exactly one definition of the word.
    """
    return (
        models.Premises.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .exclude(Q(owner_manager__isnull=True) | Q(owner_manager=""))
        .filter(owner_id__isnull=True)
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-039 wave C tasks 12-14 (12-governance/11-change-requests.md) + PO ruling 2026-08-27 ("category is okay, no richer text") + BR-MET-150/151/152 + BR-TEN-150
# generated: 2026-08-27 by the CR-039 wave C tasks 12-14 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: ruff✔ black✔ · manage.py check 0 issues✔ · makemigrations --check clean✔ · pytest tests/test_cr039_c12_premises_owner.py 13 passed · tests/test_cr039_c13_owner_migration.py 12 passed · RED-proved (see the lane report)
# exceptions:
#   E3 a SEPARATE MODULE rather than more of `services.py` — that file is six
#      thousand lines and several lanes edit it in one session (CLAUDE.md law 11's
#      fourth and fifth occurrences are both *two lanes, one file*). Everything
#      here is new behaviour with no existing caller, so it costs nothing to keep
#      out of it.
#   E3 `OQ-500` is stated rather than stubbed: `open_account` still reads the
#      free-text column, which is BEHAVIOUR rather than a gap, and a
#      NotImplementedError there would refuse to open an account in order to ask a
#      question. A test asserts the fallback so the day it is ruled, that test names
#      the place to build.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-400 / BR-MET-401 — THE OWNER **IS** THE MASTER ACCOUNT
# ═══════════════════════════════════════════════════════════════════════════
#
# PO ruling 2026-08-27, verbatim and in full:
#
#   *"so premises owner is master accountin system. you ahve to showall details
#   form account - Bascially Premises -> owner = Master account - it can be
#   existing master account also so at the time of premises creation we should
#   check - how you will handle this"*
#
# and the four decisions that answer its second half, also PO, the same day:
#
#   1. *"when presmies are created you have owner for it, without owner how you
#      can create premsies = owner = master account"* — the owner is MANDATORY
#      at premises creation.
#   2. *"A premises whose owner has no master yet - we have to create one."*
#   3. *"Near match on the name - (b) offer the match, clerk decides"* — never
#      auto-merge.
#   4. the geometric derivation is RETIRED, not kept as a fallback.
#
# ⚠ **DECISION 2 IS THE ONE THIS MODULE DOES NOT IMPLEMENT, AND `OQ-790` SAYS
# WHY.** Creating the account needs two facts nobody has at premises creation:
# WHICH KIND it is — the same PO closed `OQ-500` end to end with *"(b) — an
# owner-occupier"*, making master-ness **derived from whether anyone else
# occupies the premises** (`OCC-O` against `OCC-T`) and explicitly *"never chosen
# at creation"* — and, for a master, WHICH COMMON AREA it anchors on, since
# `create_master_account` attaches through common-area units and a brand-new
# premises has no units at all. Choosing either would decide who is billed.
# `ensure_owner_master_account` below is the stub, at its own door.
#
# ⚠⚠ **SUPERSEDED 2026-09-01 — `CR-056` W1, AND BOTH HALVES OF THE PARAGRAPH
# ABOVE ARE GONE.** WHICH KIND is no longer ambiguous: the PO ruled on
# 2026-08-31 that **every address gets its owner a Master Account, whether or
# not anything is shared, and whether or not the owner lives there** — so the
# *"never chosen at creation"* clause it rests on is itself superseded, and an
# owner-occupier holds two accounts and gets one bill. WHICH COMMON AREA is no
# longer asked at all: under `BR-CUS-1010` the account hangs off the PREMISES
# (`accounts.premises_id`) and names no unit, so there is nothing to anchor.
# `ensure_owner_master_account` is a working door from that date (`BR-MET-1010`),
# and nothing about it was chosen here — `OQ-790` closed on 2026-08-27 on
# option (c), and W1 removed the one obstacle that row recorded as WORK.

#: Suffixes that are part of a company's legal form rather than its identity.
#: Used ONLY to spot a NEAR match to OFFER — never to merge two parties, and
#: never to decide a category (BR-MET-151 clause 3 forbids reading a category
#: off a name and this table must not become that by the back door).
#: ⚠ **LEGAL FORMS ONLY — NOT TRADE WORDS.** An earlier draft also stripped
#: `property`, `rentals`, `holdings` and `group`, and it collapsed *Ridge
#: Property LLC* and *Ridge Holdings LLC* onto the same key. Offering two
#: unrelated landlords to a clerk never merges anything, but it teaches them to
#: dismiss the offer — and an offer nobody reads is decision 3 defeated by
#: noise. The suffix is the only part of a name that is genuinely not identity.
_LEGAL_FORMS: frozenset[str] = frozenset(
    {
        "llc", "inc", "incorporated", "corp", "corporation", "co",
        "company", "ltd", "limited", "lp", "llp", "plc",
    }
)


def _normalise_owner_name(name: Any) -> str:
    """A name reduced to the letters and digits that carry its identity.

    ⚠ **THIS IS A SEARCH KEY AND NEVER AN EQUALITY TEST.** *Ridge Property LLC*
    and *Ridge Property, L.L.C.* normalise the same and are still offered to a
    clerk rather than merged, because two landlords with similar names are two
    parties and merging them bills the wrong one (PO decision 3). The EXACT
    match — the one that reuses without asking — is the DATABASE's own
    `uq_premises_owners_tenant_name_ci`, not this.
    """
    import re

    lowered = re.sub(r"[^0-9a-z ]+", " ", str(name or "").lower())
    # ⚠ **RUNS OF SINGLE LETTERS COLLAPSE FIRST, AND WITHOUT IT THIS FINDS
    # NOTHING.** `L.L.C.` loses its stops to the substitution above and arrives
    # as three one-letter words; a suffix table that only knows `llc` would then
    # keep all three, and *Ridge Property, L.L.C.* would normalise to
    # `ridge l l c` against *Ridge Property LLC*'s `ridge` — the two names a
    # clerk most needs offered would be the two this never offers.
    words: list[str] = []
    for word in lowered.split():
        if len(word) == 1 and words and len(words[-1]) <= 3 and words[-1].isalpha():
            words[-1] += word
        else:
            words.append(word)
    return " ".join(word for word in words if word and word not in _LEGAL_FORMS)


def resolve_owner_name(name: Any) -> dict[str, Any]:
    """**THE CHECK THE PO ASKS FOR**, in one call, with FOUR answers and no
    fifth: *"it can be existing master account also so at the time of premises
    creation we should check"*.

    ⛔ **THE FOURTH ANSWER ARRIVED ON 2026-08-27 AND IT IS A NARROWING OF
    `BR-MET-401`, NOT A REVERSAL OF IT.** PO verbatim: *"what if owner column is
    empty - in such case we create the premises and keep owner name empty - we
    cna edit and updaste it later"*.

    ``{"match": "empty", "owner": None, "candidates": []}``
        **The column names nobody.** On the CREATE SCREEN this is still refused
        — `BR-MET-1181` stands there unchanged, and decision 1 (*"without owner
        how you can create premsies"*) is about a clerk filling in a form, who
        knows the answer or can find it. On the **IMPORT** the premises LOADS
        with no owner and is flagged for someone to fill in later, because a
        migration is thousands of rows and half the owner answers are in a
        filing cabinet — refusing them would mean a utility cannot load its own
        address book until it finishes a research project, and the addresses it
        cannot load are the ones its meters and accounts then cannot name
        either.

        ⚠ **THIS USED TO BE SPELLED `"none"`, WHICH IS A DIFFERENT FACT.**
        *"the column is empty"* and *"nobody is called that"* lead to opposite
        actions — one waits for a person, the other creates a party — and one
        word for both is how the empty case went unnoticed until the PO read
        the picture.

        ⚠ **WHAT IT COSTS, SAID OUT LOUD:** no owner means **no master
        account**, so that address has **nobody to charge**. It is a real
        premises — it holds units, it holds meters, it can be read — and it
        cannot be BILLED until the owner is filled in.

        ⚠ **AND THIS PARAGRAPH USED TO CLAIM A MITIGATION THAT DOES NOT EXIST
        (`DEF-2793`, corrected 2026-09-01).** It read: *"Those rows are listed
        by `unmatched_premises_qs()` and counted on the import receipt
        (`premises_with_no_owner`), so they are never silently indistinguishable
        from complete ones."* **The second half is true and the first half can
        never be true.** `unmatched_premises_qs()` excludes a null or empty
        `owner_manager` and a blank Owner column writes none, so the two
        conditions are mutually exclusive: a blank-owner premises is on that
        list on no day, for no tenant. The NEAR case DOES land there, because it
        keeps the operator's string — which is why every existing test passed
        and why the sentence read as covered.

        **WHAT IS ACTUALLY TRUE TODAY:** the row is COUNTED on the import
        receipt (`premises_with_no_owner`, split by CR-055 into
        `premises_owner_blank` and `premises_owner_ambiguous`) on the day of the
        run, and after that day it is on **no standing worklist at all** —
        `unmatched_premises_qs()` does not hold it and the S14 premises list
        offers no "no owner" filter to find it with. Hard-won law 1: a comment
        claiming a guarantee is not the guarantee, and this one sat in the
        paragraph describing the mitigation for the ruling's own cost.

        **THE GAP IS NAMED AND NOT CLOSED HERE.** Widening what *unmatched*
        MEANS moves the S14 badge, the PRM-04 list and its count — three
        surfaces CR-055 does not name — so it is a change and not a fix.
        `tests/test_cr055_owner_never_rejects.py
        ::test_cr055__DEF_2795_a_BLANK_owner_premises_is_NOT_on_the_unmatched_list`
        pins the product as it actually is and inverts the day it is widened.

    ``{"match": "exact", "owner": {...}, "candidates": []}``
        This tenant already holds this party. **REUSE IT** — the party keeps its
        master account, its contact details and every other address that points
        at it. This is the branch that stops twelve addresses becoming twelve
        landlords, and the key is the DATABASE's:
        `uq_premises_owners_tenant_name_ci` already makes an owner name unique
        per tenant, so *"the match key the PO asks for already exists"* (decision
        log, 2026-08-27) and this is a lookup rather than a heuristic.

    ``{"match": "near", "owner": None, "candidates": [...]}``
        Something close exists. **OFFER IT; THE CLERK DECIDES** (decision 3).
        `owner` is deliberately `None` — a near match that resolved would be an
        auto-merge wearing a different word.

    ``{"match": "none", "owner": None, "candidates": []}``
        Nobody by that name. The caller creates the party, with a CATEGORY it
        supplies (never one derived from the name — BR-MET-151 clause 3).

    Read-only, so it takes no actor: nothing here writes.
    """
    from apps.metering import owner_selectors

    text = _text(name, 200)
    if not text:
        # PO 2026-08-27 — the fourth answer. See the docstring for why this is
        # NOT `"none"`: the two lead to opposite actions.
        return {"match": "empty", "owner": None, "candidates": []}
    tenant_id = _tenant_id()
    exact = (
        models.PremisesOwner.objects.filter(tenant_id=tenant_id, name__iexact=text)
        .select_related("category")
        .first()
    )
    if exact is not None:
        return {
            "match": "exact",
            "owner": owner_selectors.owner_detail_dict(exact),
            "candidates": [],
        }
    key = _normalise_owner_name(text)
    if not key:
        return {"match": "none", "owner": None, "candidates": []}
    candidates = [
        owner_selectors.owner_detail_dict(row)
        for row in models.PremisesOwner.objects.filter(
            tenant_id=tenant_id, active=True
        ).select_related("category")
        if _normalise_owner_name(row.name) == key
    ]
    if candidates:
        return {"match": "near", "owner": None, "candidates": candidates}
    return {"match": "none", "owner": None, "candidates": []}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def link_owner_master_account(actor: Any, owner_id: Any, account_id: Any) -> dict[str, Any]:
    """BR-MET-400 — declare which ACCOUNT this owner is billed through.

    **This is the whole of DEF-650's fix on the write side.** After this call a
    charge that BR-MET-105 sends to *"the owner / landlord"* has a real posting
    target instead of a string, and a move-out shortfall has somewhere to be
    sent — the sentence the move-out wizard prints about itself.

    ⚠ **IT NEVER CREATES OR EDITS AN ACCOUNT.** `accounts` is customers' table
    (B1/B2 §2); this validates the id through `seams` and writes ONE column on a
    metering row. An existing master is the PO's own case — *"it can be existing
    master account also"* — and reusing one is a pointer write, not a creation.

    Passing `None` CLEARS the link, which is a real act a clerk may need (an
    account closed, the wrong one picked) and is audited like any other.
    """
    from apps.metering import owner_selectors, seams

    if account_id in (None, ""):
        resolved: Any = None
    else:
        exists = seams.account_exists(account_id)
        if exists is None:
            # Customers cannot answer at all. REFUSING is the safe direction:
            # writing an unvalidated id would put an unresolvable payer on an
            # owner and the failure would surface at billing time.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-400",
                message_key="metering.premises_owner.accounts_unavailable",
                params={"account_id": str(account_id)},
            )
        if not exists:
            _refuse_fields(
                [
                    _field_error(
                        "master_account_id",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "metering.premises_owner.account_unknown",
                        value=str(account_id),
                    )
                ]
            )
        resolved = str(account_id)
    with transaction.atomic():
        row = _owner_row(owner_id, locked=True)
        before = owner_selectors.owner_detail_dict(row)
        row.master_account_id = resolved
        row.save(update_fields=["master_account", "updated_at"])
        _audit(
            actor,
            "premises_owner.master_account_linked",
            "premises_owner",
            row.id,
            before=before,
            after=owner_selectors.owner_detail_dict(row),
        )
    return owner_selectors.owner_detail_dict(_owner_row(owner_id))


def _link_created_master_account(actor: Any, row: Any, account_id: Any) -> None:
    """`premises_owners.master_account_id` ← the account just created.

    ⚠ **ONE WRITER, TWO DOORS.** `ensure_owner_master_account` (New Connect's
    caller) and `ensure_master_account_for_premises` (the premises import's)
    both end here, so the declared link `DEF-2902` / `DEF-2903` report missing is
    written the same way whichever door ran. A second copy is how the two would
    eventually record it differently, which is the failure `BR-MET-400` exists
    to close.
    """
    from apps.metering import owner_selectors

    before = owner_selectors.owner_detail_dict(row)
    row.master_account_id = account_id
    row.save(update_fields=["master_account", "updated_at"])
    _audit(
        actor,
        "premises_owner.master_account_created",
        "premises_owner",
        row.id,
        before=before,
        after=owner_selectors.owner_detail_dict(row),
    )


def _declare_premises_master_account(actor: Any, premises_id: Any, account_id: Any) -> None:
    """`premises.master_account_id` ← the account this address's owner holds.

    ⛔ **`BR-MET-1181` (PO 2026-09-22) — THE DECLARATION THE RULING IS ABOUT.**
    *"why you are point is at owner id - why not directly at master accoutn Id -
    it will solev the problem"*. Every path that OPENS an owner's account for an
    address ends here, so the premises names it directly from the first write and
    the chain a screen walks is one hop instead of two.

    ⚠ **IT IS WRITTEN BESIDE `premises_owners.master_account_id`, NEVER INSTEAD
    OF IT.** Where a typed owner exists both are written, in one transaction,
    naming the same account — so nothing that reads the owner record starts
    answering less, and `BR-MET-151`'s import matching and the move-out shortfall
    are untouched. Two columns naming ONE account cannot disagree; two columns
    filled by two different paths could, which is why there is one writer.

    ⚠ **IT NEVER WRITES WHAT `accounts.premises_id` SAYS.** Precedence 3 is not
    promoted — see `premises_master_account_link`. This writer is only ever
    handed an account that was just opened FOR this address, or one a clerk
    explicitly named on the form.

    **A no-op where the premises already declares the same account**, so saving
    twice writes nothing and audits nothing — the `ensure` posture the two doors
    above already take, for the same reason: an event reported twice is a lie
    about a money object.
    """
    from apps.metering import selectors

    row = (
        models.Premises.objects.select_for_update()
        .filter(tenant_id=_tenant_id(), pk=premises_id)
        .first()
    )
    if row is None or str(row.master_account_id or "") == str(account_id or ""):
        return
    before = selectors.premises_detail_dict(row, with_owner_account=False)
    row.master_account_id = account_id
    row.save(update_fields=["master_account", "updated_at"])
    _audit(
        actor,
        "premises.master_account_declared",
        "premises",
        row.id,
        before=before,
        after=selectors.premises_detail_dict(row, with_owner_account=False),
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def declare_premises_master_account(actor: Any, premises_id: Any, account_id: Any) -> None:
    """`BR-MET-1181` — a clerk NAMES the account that owns this address.

    ⛔ **THE ROLE-GATED FACE OF `_declare_premises_master_account`, AND THE ONLY
    ONE A DOOR OUTSIDE THIS MODULE CALLS.** The private writer is reached from
    inside a transaction that has already been authorised — the create path, the
    import — and this is reached from a form. `BR-SHL-025`: a write a clerk asks
    for is checked against a role, every time, at the boundary.

    ⚠ **IT VALIDATES NOTHING ABOUT THE ACCOUNT, DELIBERATELY.** Whether the id
    names a real, `master`-kind account in this tenant is answered by asking
    `customers` through the seam (`seams.owner_master_account_summary`), and the
    caller does that BEFORE reaching here, so the refusal carries the id the
    clerk typed. A second opinion here would be this module deciding what a
    master account is, which is `customers`' to say (B1/B2 §2).
    """
    _declare_premises_master_account(actor, premises_id, account_id)


#: Why a sale of a master account did NOT move the owner record — a CODE a
#: caller states, never a silence (`transfer_premises_owner`).
OWNER_NOT_MOVED_NO_CATEGORY = "premises_has_no_typed_owner_to_carry_a_category_from"
OWNER_NOT_MOVED_NO_NAME = "buyer_has_no_name"


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def transfer_premises_owner(
    actor: Any, premises_id: Any, account_id: Any, owner: Any
) -> dict[str, Any]:
    """`BR-CUS-1081` (T2) — **the buyer of the premises' MASTER account becomes
    the property's owner.** PO ruling 2026-09-23, verbatim: *"in case of master
    account - not in case of regualr account - (a) The sale makes the buyer the
    property's owner."*

    Customers decides WHEN (a master account changed hands) and hands over the
    buyer's name and reach; this module decides HOW, because `premises.owner_id`
    and `premises_owners` are metering's rows (B1 / B2 §2) and customers may not
    write them.

    **WHAT IT WRITES, IN ONE TRANSACTION, EACH AUDITED:**

      1. **the party.** The owner record named exactly as the buyer (case
         ignored) is REUSED if it exists — `uq_premises_owners_tenant_name_ci`
         already makes a name one party in this tenant, and a second row would be
         the *"twelve unrelated strings"* that index exists to stop. Otherwise a
         new record is created. It is ASKED first rather than caught, so no
         `IntegrityError` is ever raised inside a caller's transaction (hard-won
         law 14).
      2. **`premises.owner_id` ← that party.**
      3. **the master-account links.** The seller's party stops being billed
         through this account (their `master_account_id` is released when it
         named it), the buyer's party is billed through it (unless it already is
         through another account, which is left alone and reported), and the
         premises keeps naming this account (`_declare_premises_master_account`,
         a no-op when it already does).

    ⚠ **THE CATEGORY IS CARRIED, NEVER GUESSED — BR-MET-151 clause 3.** A new
    party needs a category and a buyer's name is not evidence of one. The sale
    changes WHO owns the building, not what kind of property owner the building
    has, so the outgoing owner's category is carried to a NEW record. **Where the
    premises has no typed owner at all there is nothing to carry**, and the
    answer is `moved: False` with `OWNER_NOT_MOVED_NO_CATEGORY` rather than a
    category chosen on the utility's behalf. A lane judgment, decision log
    2026-09-23.

    ⚠ **`owner_manager` (the legacy free text) IS NOT TOUCHED** — `OQ-500`'s
    reason, stated in `match_premises_owner`.

    Returns `{"moved", "owner_id", "reused", "reason"}`.
    """
    from apps.metering import owner_selectors
    from apps.metering import selectors as metering_selectors
    from apps.metering.services import _premises_row

    data = _payload_dict(owner) if owner else {}
    name = _text(data.get("name"), 200)
    if not name:
        return {"moved": False, "owner_id": None, "reused": False, "reason": OWNER_NOT_MOVED_NO_NAME}
    with transaction.atomic():
        premises = _premises_row(premises_id, locked=True)
        outgoing = (
            models.PremisesOwner.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), pk=premises.owner_id)
            .first()
            if premises.owner_id
            else None
        )
        if outgoing is None:
            return {
                "moved": False,
                "owner_id": None,
                "reused": False,
                "reason": OWNER_NOT_MOVED_NO_CATEGORY,
            }
        incoming = (
            models.PremisesOwner.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), name__iexact=name)
            .first()
        )
        reused = incoming is not None
        if incoming is None:
            incoming = models.PremisesOwner.objects.create(
                tenant_id=_tenant_id(),
                name=name,
                category=outgoing.category,
                email=_text(data.get("email"), 254),
                phone=_text(data.get("phone"), 40),
            )
            _audit(
                actor,
                "premises_owner.created",
                "premises_owner",
                incoming.id,
                after=owner_selectors.owner_detail_dict(incoming),
            )
        if incoming.pk != outgoing.pk and str(outgoing.master_account_id or "") == str(account_id):
            before = owner_selectors.owner_detail_dict(outgoing)
            outgoing.master_account_id = None
            outgoing.save(update_fields=["master_account", "updated_at"])
            _audit(
                actor,
                "premises_owner.master_account_released",
                "premises_owner",
                outgoing.id,
                before=before,
                after=owner_selectors.owner_detail_dict(outgoing),
            )
        if incoming.master_account_id is None:
            # Not `_link_created_master_account`: that writer's audit action says
            # the account was just CREATED, and here it was sold.
            before = owner_selectors.owner_detail_dict(incoming)
            incoming.master_account_id = account_id
            incoming.save(update_fields=["master_account", "updated_at"])
            _audit(
                actor,
                "premises_owner.master_account_linked",
                "premises_owner",
                incoming.id,
                before=before,
                after=owner_selectors.owner_detail_dict(incoming),
            )
        before = metering_selectors.premises_detail_dict(premises)
        premises.owner_id = incoming.id
        premises.save(update_fields=["owner", "updated_at"])
        _audit(
            actor,
            "premises.owner_transferred",
            "premises",
            premises.id,
            before=before,
            after=metering_selectors.premises_detail_dict(premises),
        )
        _declare_premises_master_account(actor, premises_id, account_id)
    return {"moved": True, "owner_id": str(incoming.id), "reused": reused, "reason": None}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def ensure_owner_master_account(
    actor: Any, owner_id: Any, premises_id: Any = None, payload: Any = None
) -> dict[str, Any]:
    """`BR-MET-1010` — the owner's account at an address, created if it is not
    there already.

    ⚠ **THIS RAISED `NotImplementedError("OQ-790")` UNTIL 2026-09-01, AND WHAT
    REMOVED THE REFUSAL WAS A RULING, NOT A DECISION TAKEN HERE.** The stub's
    stated reason was that master-ness was *derived from whether anyone else
    occupies the premises* and *never chosen at creation* — so at premises
    creation, with no units and nobody occupying anything, the kind could not be
    derived. **The PO reversed exactly that on 2026-08-31** (`CR-056`): *every
    address gets its owner a Master Account, whether or not anything is shared,
    and whether or not the owner lives there.* An owner-occupier holds two
    accounts and receives one bill, because an account with no charges produces
    no document.

    `OQ-790` itself had already CLOSED on 2026-08-27 on option (c), MASTER
    IMMEDIATELY, with the PO naming the mechanism (*"you ahev to call master
    account creation logic by passing the details and generate account number
    using Setting -> numbering"*), leaving ONE obstacle recorded as WORK rather
    than as a question: *"`create_master_account` anchors on common-area units
    and a new premises has none, so the creation path must anchor on the
    premises."* `CR-056` W1 removed it — `accounts.premises_id` exists and
    `accounts.unit_id` is nullable — so this door opens with nothing guessed.

    **IT IS IDEMPOTENT.** An owner already linked to an account gets that
    account back and nothing is written: this is *ensure*, not *create a second
    one*, and `BR-CUS-1011` (one owner account per address) would refuse the
    second anyway.

    **WHICH ADDRESS.** `premises_owners.master_account_id` is a link on the
    OWNER and an account is per ADDRESS, so an owner of two buildings is a
    question this signature cannot answer by itself. The premises is therefore
    NAMED by the caller; when it is not, it is resolved only where the owner owns
    exactly one, and an owner of several **refuses by name rather than picking**.
    That refusal is the honest boundary — `CR-056` W2/W3 own the identity work
    that would let one party hold several accounts properly.

    ⚠ **CROSS-MODULE WRITE, THROUGH THE SEAM AND NEVER AROUND IT** (B1). Customers
    owns accounts; this resolves `create_master_account` and calls it, so the
    whole guard set — the per-unit advisory locks, BR-CUS-017's family,
    BR-MET-040's plan requirement, BR-CUS-1011 — applies to an owner's account
    exactly as it applies to a hand-made one. The same posture
    `create_owner_account_for_connection` already takes one file along.

    ⚠ **NOTHING CALLS THIS YET, AND THAT IS STATED RATHER THAN IMPLIED**
    (hard-won law 2). `CR-056` task 23 (New Connect creating the premises) and
    task 24 (the premises import) own the callers; a door that works is not a
    door somebody walks through.
    """
    from apps.metering import owner_selectors, seams

    data = _payload_dict(payload) if payload is not None else {}
    with transaction.atomic():
        row = _owner_row(owner_id, locked=True)
        if row.master_account_id is not None:
            # Already linked. Writes nothing, audits nothing — there is no event.
            return owner_selectors.owner_detail_dict(row)

        owned = list(
            models.Premises.objects.filter(
                tenant_id=_tenant_id(), owner_id=row.id, deleted_at__isnull=True
            )
            .order_by("address_line", "id")
            .values_list("id", flat=True)
        )
        if premises_id in (None, ""):
            if len(owned) != 1:
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-MET-1010",
                    params={
                        "owner_id": str(row.id),
                        "premises_count": len(owned),
                        "reason": (
                            "owner_owns_no_premises"
                            if not owned
                            else "owner_owns_several_premises_name_one"
                        ),
                    },
                )
            resolved_premises_id = str(owned[0])
        else:
            resolved_premises_id = str(premises_id)
            if resolved_premises_id not in {str(value) for value in owned}:
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-MET-1010",
                    params={
                        "owner_id": str(row.id),
                        "premises_id": resolved_premises_id,
                        "reason": "premises_is_not_owned_by_this_owner",
                    },
                )

        create_master = seams.resolve("customers", "create_master_account")
        if create_master is None:  # pragma: no cover — the customers lane is landed
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-MET-1010",
                params={"reason": "customers_has_not_published_create_master_account"},
            )
        account = create_master(
            actor,
            {
                "premises_id": resolved_premises_id,
                # ⛔ **CR-058 W3 — THE CUSTOMER BLOCK IS FORWARDED, NOT
                # RESOLVED HERE.** `BR-CUS-1023` and ruling 0 of 2026-09-01 make
                # customer resolution ONE act — match first, create only on no
                # match, and only where an identifier is present — and it
                # belongs to the module that owns the customer. This door hands
                # the evidence over and reads the answer back; it does not
                # match, does not create, and does not decide whether the
                # minimum was met. A second copy of that logic here is exactly
                # what the ruling's *"no door repeats the logic"* forbids.
                # ⚠ An absent block is not an empty one: omitted, so
                # `create_master_account` falls back to the premises' own owner
                # name exactly as it did before this key existed.
                **({"customer": data["customer"]} if data.get("customer") else {}),
                # ⚠ **NO DEFAULT IS INVENTED FOR EITHER OF THESE.** The account
                # type is the consumer category the bill is priced and reported
                # by; guessing `residential` for a builder's site or `commercial`
                # for a family home is a money decision taken by a shrug.
                # `create_master_account` refuses a missing one BY NAME, which is
                # the refusal this door wants and does not need to restate.
                "account_type": data.get("account_type"),
                # The account opens on the TENANT'S today, never the server's —
                # `create_owner_account_for_connection`'s own reasoning: an
                # account that opened "yesterday" in the utility's timezone dates
                # its charges into a period that may already be closed.
                "opened_at": data.get("opened_at") or str(seams.tenant_today()),
                "contact": data.get("contact") or {},
                #: ⚠ **`CR-058` / `BR-CUS-1024` — THE CUSTOMER BLOCK TRAVELS
                #: THROUGH, AND WITHOUT THIS LINE THIS DOOR COULD NOT SATISFY
                #: THE RULE IT IS UNDER.** PO 2026-09-01, said of THIS door:
                #: *"we have to create it if not matching customer ID not
                #: available, - rest is correct"*. The master door matches a
                #: customer first and creates one where no match exists, and it
                #: can only do that with the name, the kind and the identifier
                #: the caller was given. Passed through UNREAD — this module
                #: does not own the vocabulary and must not validate a second
                #: copy of it; `customers._validate_customer_block` refuses an
                #: unknown key there, once, for every door.
                #:
                #: ⛔ **AND WITHOUT AN IDENTIFIER THE MASTER DOOR NOW REFUSES**,
                #: which refuses this action too: *"Without identifier we cannot
                #: create Customer ID or master account ot regular account"*.
                #: That is the ruling reaching a door the question was not about,
                #: and it is stated here rather than discovered at a counter.
                "customer": data.get("customer"),
            },
        )
        _link_created_master_account(actor, row, account["id"])
        # ⛔ **`BR-MET-1181` — AND THE PREMISES NAMES IT DIRECTLY (2026-09-22).**
        # BOTH links are written, in this one transaction, naming the SAME
        # account. The owner record keeps its link because 19 backend files read
        # it; the premises gains one because the ruling says a screen walks
        # `premises → account` and not `premises → owner → account`.
        _declare_premises_master_account(actor, resolved_premises_id, account["id"])
    return owner_selectors.owner_detail_dict(_owner_row(owner_id))


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def ensure_master_account_for_premises(
    actor: Any, premises_id: Any, payload: Any = None
) -> dict[str, Any]:
    """`BR-MET-1030` — the owner's account at THIS ADDRESS, created if it is not
    there already. **The one entry the premises import walks through.**

    ⚠ **IT IS NOT A SECOND CREATION PATH AND MUST NEVER BECOME ONE.** Both
    branches below end at the SAME door — `customers.create_master_account`
    through the seam — and the first of them reaches it through
    `ensure_owner_master_account` verbatim, which is New Connect's caller too
    (`CR-056` task 23). Customers owns `accounts` (B1/B2 §2), so the whole guard
    set travels with it: the per-unit advisory locks, `BR-CUS-017`'s family,
    `BR-CUS-1011`'s one-owner-account-per-address, and the customer resolution
    the account door performs. Nothing about an imported owner is judged more
    loosely than a hand-typed one.

    ⚠ **WHY THERE ARE TWO BRANCHES AT ALL, AND IT IS NOT UNTIDINESS.** The
    account belongs to the ADDRESS (`BR-CUS-1010`). The `premises_owners` row is
    a separate, TYPED party record whose own rule requires a **category**
    (`BR-MET-150`; PO 2026-08-27: *"category is okay, no richer text"*), and a
    spreadsheet row carries no category. So:

      * the premises HAS a typed owner  ->  `ensure_owner_master_account`, which
        also writes `premises_owners.master_account_id` — the declared link
        `DEF-2902` / `DEF-2903` report is missing from every master account in
        the product.
      * the premises has NO typed owner ->  the account is created for the
        ADDRESS and the typed party is left for a person to settle on `PRM-04`.
        **Inventing a category to force the first branch would be reading a
        category off a name, which `BR-MET-151` clause 3 forbids in as many
        words** — and it would put a fabricated party in the master list a clerk
        searches.

    Both outcomes are honest and both are reported: the caller is told which one
    happened, so a receipt can say *"the address has an owner account"* without
    claiming the party record was matched.

    **IT IS IDEMPOTENT.** An address that already has an active master account
    gets that account back and nothing is written — `BR-CUS-1011` would refuse a
    second one anyway, and *ensure* means what it says.
    """
    from apps.metering import seams

    data = _payload_dict(payload) if payload is not None else {}
    premises = (
        models.Premises.objects.filter(
            tenant_id=_tenant_id(), pk=premises_id, deleted_at__isnull=True
        )
        .values("id", "owner_id")
        .first()
    )
    if premises is None:
        raise errors.NotFoundError(message_key="metering.premises.not_found")

    # ── already there? ────────────────────────────────────────────────────
    # ⚠ **THE QUESTION IS ANSWERED BY THE MODULE THAT OWNS IT, NOT BY A COPY OF
    # ITS GUARD.** `BR-CUS-1011` — one owner account per address — lives in
    # `customers._refuse_if_premises_has_master` and refuses BY NAME with the
    # account it found. A duplicate query here would be a second opinion about
    # who owns a building, and the two would eventually disagree; `BR-CUS-171`
    # already records what that felt like. So the declared link is read where it
    # exists, and the door's own refusal is read as the answer where it does not.
    #
    # ⛔ **ASKED FOR EVERY ADDRESS SINCE `BR-MET-1181`, NOT ONLY FOR ONE WITH A
    # TYPED OWNER (2026-09-22).** This read used to sit behind
    # `if premises["owner_id"]`, because the only declaration there was on the
    # owner record. The premises now declares directly, so an address with no
    # owner record can HAVE an account — and a door that asked only where a
    # typed owner existed would open a second one for it, which is
    # `BR-CUS-1011` reached at the database instead of answered here.
    linked, _source = premises_master_account_link(premises_id)
    if linked:
        return {
            "created": False,
            "account_id": str(linked),
            "owner_id": str(premises["owner_id"]) if premises["owner_id"] else None,
            "owner_linked": bool(premises["owner_id"]),
            "reason": "premises_already_has_an_owner_account",
        }
    owner_row = _owner_row(premises["owner_id"]) if premises["owner_id"] else None

    payload_out: dict[str, Any] = {
        "premises_id": str(premises_id),
        # ⚠ **NO DEFAULT IS INVENTED FOR EITHER OF THESE**, and the reasoning is
        # `ensure_owner_master_account`'s verbatim rather than a second wording
        # of it: the account type is the consumer category the bill is priced and
        # reported by, and the account opens on the TENANT'S today.
        "account_type": data.get("account_type"),
        "opened_at": data.get("opened_at") or str(seams.tenant_today()),
        "contact": data.get("contact") or {},
    }
    if data.get("customer"):
        # ⛔ **THE CUSTOMER IS RESOLVED BY THE ACCOUNT DOOR, NOT HERE.**
        # `CR-058`'s governing ruling makes it ONE act — match first, create only
        # on no match, and only where an identifier is present — inside the
        # module that owns customers. This carries the evidence and reads the
        # answer back; it does not match, does not create, and does not decide
        # whether the minimum was met.
        payload_out["customer"] = data["customer"]

    with transaction.atomic():
        try:
            account = seams.create_master_account_from_import(
                actor=actor, payload=payload_out
            )
        except errors.BizError as refusal:
            # `BR-CUS-1011`'s own refusal, read as the idempotent answer it is:
            # the address HAS an owner account, so *ensure* is satisfied and
            # nothing more should be written. **Every other refusal is a real
            # one and is re-raised untouched** — a bare `except BizError` would
            # swallow a missing account type and report an account that does not
            # exist, which is a check that cannot fail.
            params = getattr(refusal, "params", None) or {}
            if getattr(refusal, "br_ref", None) != "BR-CUS-1011" or not params.get("account_id"):
                raise
            return {
                "created": False,
                "account_id": str(params["account_id"]),
                "owner_id": str(premises["owner_id"]) if premises["owner_id"] else None,
                "owner_linked": False,
                "reason": "premises_already_has_an_owner_account",
            }
        if account is None:  # pragma: no cover — the customers lane is landed
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-MET-1030",
                params={"reason": "customers_has_not_published_the_import_writer"},
            )
        if owner_row is not None:
            _link_created_master_account(actor, owner_row, account["id"])
        # ⛔ **`BR-MET-1181` — THE ADDRESS NAMES ITS ACCOUNT, WITH OR WITHOUT A
        # TYPED OWNER (2026-09-22).** This line is what makes the no-owner-record
        # branch below stop being a dead end: before it, an account created for
        # an address with no typed party was findable by nothing —
        # `owner_master_account_for_premises` answered `None` for it, so the
        # empty-unit base charge and the move-out shortfall had no target, and
        # the note below said as much out loud. It is written INSIDE the same
        # transaction as the account, so a rollback takes both.
        _declare_premises_master_account(actor, premises_id, account["id"])

    return {
        "created": True,
        "account_id": str(account["id"]),
        "owner_id": str(owner_row.id) if owner_row is not None else None,
        # ⚠ **SAID OUT LOUD, BECAUSE IT IS STILL WORK SOMEBODY OWES — THOUGH A
        # SMALLER PIECE OF IT SINCE `BR-MET-1181`.** With no typed party the
        # `PRM-04` matching worklist still shows this address, because nobody has
        # said WHO the owner is as a party. **What is no longer true is that the
        # account could not be found:** the premises declares it directly now, so
        # `owner_master_account_for_premises` answers, and the money path has its
        # target. Inventing a `premises_owners` row to close the rest would need
        # a CATEGORY, and reading a category off a name is what `BR-MET-151`
        # clause 3 forbids.
        "owner_linked": owner_row is not None,
        "reason": (
            "created_and_linked_to_the_typed_owner"
            if owner_row is not None
            else "created_for_the_address__typed_owner_not_matched"
        ),
        "customer_match": account.get("customer_match"),
        "customer_not_created": account.get("customer_not_created"),
    }


#: ── `BR-MET-1181` (PO ruling 2026-09-22) — WHICH DECLARATION ANSWERED ──────
#: Served beside the account on every premises read. Two columns can answer
#: *who is the master account for this address*, so a screen showing one owes
#: its reader the same sentence `BR-MET-1162` demands of a map pin: **say which
#: of the two you are showing.** There it is the unit's own point against its
#: building's; here it decides who is billed, so the case for saying it is
#: stronger rather than weaker.
MASTER_ACCOUNT_SOURCE_PREMISES = "premises"
MASTER_ACCOUNT_SOURCE_OWNER_RECORD = "owner_record"


def premises_master_account_link(premises_id: Any) -> tuple[Any, str | None]:
    """`BR-MET-1181` — the account id AND which declaration named it.

    ⛔ **THE PRECEDENCE IS RULED, NOT LEFT TO THIS FUNCTION'S READING ORDER**
    (decision log 2026-09-22). Three columns in this product can answer *who is
    the master account for this address*, and three answers that disagree is who
    gets billed wrongly:

      1. **`premises.master_account_id`** — the declaration. It WINS whenever it
         is set.
      2. **`premises_owners.master_account_id`** — the PRE-RULING declaration,
         read for rows written before 2026-09-22. Nothing is backfilled, so this
         is what answers for them, and it goes on being WRITTEN wherever a typed
         owner exists — no reader of it starts answering less.
      3. **`accounts.premises_id`** — *which premises this account covers*,
         **never** *who owns this premises*. It is NOT READ HERE and is never
         promoted to answer this question. Both master and regular accounts
         carry it, so promoting it would make every tenant at an address a
         candidate owner of it.

    ⚠ **`BR-MET-400`'s *DECLARED, NEVER INFERRED* IS NARROWED AND NOT WEAKENED.**
    That rule retired the hallway derivation in the PO's own words — *"a fallback
    that disagrees with the declared owner would silently bill a different
    party"* — and BOTH branches below are reads of a DECLARED column. This is a
    SHORTER CHAIN between the same two ends, never a guess; what the ruling
    narrows is only WHICH declaration is read first.

    `(None, None)` where neither declaration names an account. That is a real
    state — nobody has said who owns this address — and it is what the
    **Needs an owner** filter finds, never something to infer a way around.

    **ONE QUERY**, both columns, because two reads of one row is how the two
    start being asked at different moments and answering differently.
    """
    if premises_id in (None, ""):
        return (None, None)
    row = (
        models.Premises.objects.filter(tenant_id=_tenant_id(), pk=premises_id)
        .values_list("master_account_id", "owner__master_account_id")
        .first()
    )
    if row is None:
        return (None, None)
    declared, from_owner_record = row
    if declared:
        return (declared, MASTER_ACCOUNT_SOURCE_PREMISES)
    if from_owner_record:
        return (from_owner_record, MASTER_ACCOUNT_SOURCE_OWNER_RECORD)
    return (None, None)


def owner_master_account_for_premises(premises_id: Any) -> Any:
    """BR-MET-400 / `BR-MET-1181` — *Premises → master account*, DECLARED.

    The id only, so a caller that needs the account's own facts asks the module
    that owns them (`seams.owner_master_account_summary`) rather than being
    handed a stale copy.

    ⛔ **SINCE 2026-09-22 THE PREMISES NAMES THE ACCOUNT DIRECTLY AND THE OWNER
    RECORD IS THE FALLBACK, NOT THE FIRST HOP** (`BR-MET-1181`, PO: *"why you are
    point is at owner id - why not directly at master accoutn Id"*). The order
    and its reasoning are `premises_master_account_link`'s, which this is the
    one-value form of — **there is one implementation of the precedence and this
    is not a second copy of it.**

    ⚠ **THIS STILL REPLACES `BR-CUS-171`'s GEOMETRIC DERIVATION AND IS STILL NOT
    A SECOND OPINION BESIDE IT.** The old path walked the premises' COMMON AREAS
    and took the account that pays for the hallway. Decision 4 of the 2026-08-27
    ruling retires it outright — *"the premises names its owner, the owner is the
    master, and nothing is inferred from hallways. The old path is retired rather
    than kept as a fallback, because a fallback that disagrees with the declared
    owner would silently bill a different party."*

    `None` where neither column declares an account. A real state, and the money
    path (the empty-unit base charge, the move-out shortfall) reports it rather
    than picking somebody.
    """
    return premises_master_account_link(premises_id)[0]


def premises_ids_owned_by_account(account_id: Any) -> list[str]:
    """The inverse of `owner_master_account_for_premises` — every premises this
    account is the DECLARED owner of.

    ⛔ **BOTH DECLARATIONS, AND `accounts.premises_id` IS STILL NOT ONE OF THEM**
    (`BR-MET-1181`). A premises answers here when it names this account itself OR
    when its owner record does — the same two columns
    `premises_master_account_link` reads, from the other end, so the forward and
    the reverse reading can never disagree about a pair. **`accounts.premises_id`
    is deliberately absent**: it says which premises an account COVERS, and a
    tenant's ordinary account covers a premises it does not own.

    ⚠ **THIS IS WHAT MAKES `sub_accounts_for_master` STOP BEING GEOMETRIC TOO.**
    Its old reading was *the premises my ANCHOR UNIT sits on*, which is the same
    hallway inference seen from the other end: an owner's account anchored on
    one building's common area would list that building's tenants even where the
    declared ownership says otherwise. A declared link answers directly.

    ⚠ **`distinct()` IS LOAD-BEARING, NOT TIDINESS.** A premises that names the
    account AND whose owner record names the same account matches both halves of
    the OR, and a duplicated premises id would double-count a building in the
    sub-account list and in the move-out shortfall.

    An empty list is a real answer — an account nobody has named as an owner.
    """
    if account_id in (None, ""):
        return []
    return [
        str(value)
        for value in models.Premises.objects.filter(
            tenant_id=_tenant_id(),
            deleted_at__isnull=True,
        )
        .filter(
            Q(master_account_id=account_id) | Q(owner__master_account_id=account_id)
        )
        .values_list("id", flat=True)
        .distinct()
    ]
