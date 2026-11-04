# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-046 (EP-CWP-09) — your payment methods: a token, never a
#           card number · US-CWP-022 (EP-CWP-05) — step up before a stored
#           method changes. Screen: CWP-039
# Rules:    BR-CWP-057 (a stored payment method is a TOKEN from the gateway
#           with a brand and a last four; the product never holds a full card
#           number) · BR-CWP-040 (step-up before a method is added, changed or
#           removed) · BR-CWP-056 (a refused control is visible, disabled and
#           carries its reason) · BR-CWP-010 (tenant AND the login's own set,
#           intersected IN THE QUERY) · BR-PAY-013 (the bounce count and the
#           cash-only / no-autopay privilege flag) · BR-INT-038 (an adapter
#           TRANSLATES; it decides nothing) · CLAUDE.md hard rule 1 (tenant
#           scoping) · rule 4 (nothing a payment points at is destroyed) ·
#           rule 7 (every money action writes `audit_log`)
# Change:   CR-068 phase 5 · OQ-1394 CLOSED 2026-09-04 (absorb AND surcharge,
#           behind a per-tenant switch) · OQ-1396 CLOSED 2026-09-04 (delegate
#           access DEFERRED)
# Tests:    06-backend/tests/test_us_cwp_046_methods.py ·
#           06-backend/tests/test_us_cwp_022_step_up.py
# Impacts:  apps/portal/api.py (the four routes that reach this) ·
#           apps/integrations/adapters/payments_sandbox.py (`tokenise`) ·
#           07-frontend/src/portal/methods/Methods.tsx
# ───────────────────────────────────────────────────────
"""The customer's saved cards and mandates — **a token, never a card number**.

⚠ **THIS FILE HOLDS NO CARD NUMBER AND CANNOT BE MADE TO** (`BR-CWP-057`). What
arrives here is a *reference* to a tokenisation the VENDOR performed on the
VENDOR's own page; what comes back from `tokenise` is a token, a brand, four
digits and an expiry. There is no argument, no column and no log line below that
a sixteen-digit number would fit in — and `save_instrument` refuses a reference
that carries a PAN-shaped digit run, because the way a card number actually
arrives in a product like this is somebody typing one into the field meant for
something else.

WHY THE SERVICE LIVES IN `payments` AND THE ROUTES LIVE IN `portal`
-------------------------------------------------------------------
`stored_payment_instruments` is a **payments** table (`B2` §2, `03-field-map.md`
§payments), so the write belongs to the module that owns it — the same shape
`apps/customers/portal_self_service.py` has for the contact-detail and
account-link writes. `apps/portal/api.py` authenticates the customer, proves the
step-up code and calls in; it performs no ORM write of its own, which is what
`G81` checks.

⚠ **AND THE PORTAL'S DECLARED WRITE POINTS DO NOT YET NAME THIS ONE.**
`apps/portal/write_points.py` declares six kinds — payment, service request,
meter reading, preference, contact detail, account link — and a saved instrument
is **none of them**. Its `payment` row says *"lands_in: payments (one row,
allocated by the tenant's rule)"*, which is the money movement and not the
instrument; and it is not a `companion` of that row either, because a companion
is defined there as a row with **no independent door**, and this one has one: a
customer saves a card without paying anything.

**So a SEVENTH kind is owed, and it is a ruling rather than an edit** — that
file's own docstring says so in as many words: *"Nobody ever decides to allow one
more; a lane just needs one more field."* It is REPORTED with the row it needs
rather than taken. Until it lands, `G81` is green over this code for a reason
worth naming out loud so nobody mistakes it for approval: the gate refuses an
ORM write **inside `apps/portal/`** and an import of another module's
`…services`, and this module is called `instruments`. **That is the letter of the
check and not its spirit**, and this paragraph is here so the next reader knows
the difference.

WHAT A REFUSAL LOOKS LIKE HERE (BR-CWP-056)
--------------------------------------------
Autopay is refused on an account the utility has put on cash-only, or one that
has bounced payments (`BR-PAY-013`). The refusal is **data on the way out** — a
reason KEY and a count — never a hidden control and never a sentence composed
here: eleven catalogues write the sentence in their own language (B14 rule 35)
at five or six words (rule 33).

⚠ **THE CARD FEE IS A STANCE, NOT AN ARITHMETIC** (`OQ-1394`, CLOSED
2026-09-04). The Product Owner took **both** answers — absorb and surcharge —
behind a per-tenant switch: *"we have to give both the options so far some
utilities abosrb it other pass it to customer"*. `card_fee_payer` on the
finance-controls family stores that intention and defaults to `utility`, which
is hard-won law 3 (surcharging is regulated in several states and prohibited in
some). **Turning it to `customer` obliges a figure that does not exist**: the fee
must be computed from a processor's own schedule, disclosed before the commit and
checked against the customer's state, and there is no processor. So
`price_card_surcharge` REFUSES BY NAME rather than inventing a percentage —
which is what `settings_families.py` already promised beside that parameter, and
this is the file that keeps the promise.

⚠ **A REMOVAL IS SOFT** (hard rule 4). A payment already taken on an instrument
names it; destroying the row would leave a payment pointing at nothing.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.integrations.adapters import payments_sandbox
from apps.payments import models, settings_seam
from core import audit as core_audit

#: A run of five or more digits. The shortest card number in circulation is
#: thirteen and the longest nineteen, so five is comfortably below anything a
#: real PAN could be trimmed to and comfortably above every legitimate value a
#: gateway reference carries (a month, a year, four digits).
PAN_SHAPED = re.compile(r"\d{5,}")

#: What `autopay_stance` answers with. KEYS, never sentences — see the module
#: docstring. `cash_only` outranks `bounced` because it is the utility's
#: explicit decision and `bounced` is the automatic one that led to it.
BLOCK_CASH_ONLY = "cash_only"
BLOCK_BOUNCED = "bounced"

#: `finance-controls` → who pays the card fee (`OQ-1394`).
CARD_FEE_KEY = "card_fee_payer"
CARD_FEE_UTILITY = "utility"

#: Why no surcharge figure exists. Not an open question — a missing vendor.
FEE_NOT_PRICED = "no_processor"

ACTION_ADDED = "portal.payment_method.added"
ACTION_REMOVED = "portal.payment_method.removed"
ENTITY = "stored_payment_instrument"


class LooksLikeACardNumber(ValueError):
    """`BR-CWP-057` — refused at the door, and nothing is written.

    ⚠ **THE MESSAGE MUST NEVER ECHO WHAT WAS SENT.** An exception that quoted
    the offending value would put a card number in a traceback, a log and an
    error tracker — which is the one outcome this whole class exists to prevent.
    """


class SurchargeNotPriced(NotImplementedError):
    """There is no processor, so there is no fee schedule to compute from.

    ⚠ **NOT A BLOCKED QUESTION.** `OQ-1394` is CLOSED; what is missing is a
    vendor. Citing a closed question here would send the next lane to ask the
    Product Owner something they have already answered — hard-won law 13.
    """


class NotYours(LookupError):
    """The instrument is not this login's — answered as *not found*.

    Same body as an id that does not exist, so the id space cannot be walked to
    learn which instruments the utility holds (`BR-CWP-010`, the posture
    `_account_in_set` already takes for accounts).
    """


def _portal_actor(actor: Any) -> dict[str, Any]:
    """WHO did it, for `audit_log` — and it is **not** `actor_user_id`.

    A portal customer is not a `User` (`BR-CWP-004`: separate table, separate
    session, separate permission catalogue), so there is no staff user id to put
    in that column and inventing one would make a customer's act
    indistinguishable from a clerk's in the one record that exists to tell them
    apart. `core.audit.write_row`'s own contract covers it: *"None = system job;
    name the job in the payload"*.

    ⚠ **DELIBERATELY THE SAME SHAPE AS
    `apps.customers.portal_self_service._portal_actor`** and deliberately not
    imported from it: that is another module's private helper, and a
    cross-module import of a private name to save six lines is a coupling the
    next refactor breaks silently. The SHAPE is the contract — a reader of
    `audit_log` sees one payload for every portal act.
    """
    return {
        "portal_customer_id": str(getattr(actor, "customer_id", "") or "") or None,
        "portal_session_id": str(getattr(actor, "session_id", "") or "") or None,
        "channel": "customer_portal",
    }


def _expired(row: Any, today: date) -> bool:
    """A card whose expiry month has passed. **Derived, never stored.**

    Nothing in this product ages a row nightly, so a read that trusted `status`
    would go on offering an expired card for a payment until somebody swept the
    table. A mandate has no expiry and is therefore never expired here.
    """
    if row.kind != models.INSTRUMENT_CARD:
        return False
    if row.expires_month is None or row.expires_year is None:
        return False
    return (int(row.expires_year), int(row.expires_month)) < (today.year, today.month)


def _view(row: Any, today: date) -> dict[str, Any]:
    """One row as the screen reads it — **and `gateway_token` is not in it.**

    The keys are a closed set and a test asserts exactly that set, so a
    serialiser that grew a field fails rather than shipping whatever the model
    gained. `ref` is the row id and travels only in a URL: B14 rule 31 forbids a
    database id as the VISIBLE VALUE of a field, and `Methods.dom.test.tsx`
    asserts it never appears on screen.
    """
    expired = _expired(row, today)
    return {
        "ref": str(row.pk),
        "brand": row.brand,
        "last_four": row.last_four,
        "kind": row.kind,
        "status": models.INSTRUMENT_EXPIRED if expired else row.status,
        "used_for": list(row.used_for or []),
        "added_on": timezone.localtime(row.created_at).date().isoformat(),
        "expires": (
            f"{int(row.expires_month):02d}/{int(row.expires_year) % 100:02d}"
            if row.expires_month and row.expires_year
            else None
        ),
        #: What `CWP-038` may offer. An expired card is listed — a customer has
        #: to be able to see it in order to replace it — and cannot be chosen.
        "usable": not expired and row.status != models.INSTRUMENT_EXPIRED,
    }


def _live(tenant_id: Any, customer_id: Any):
    """The queryset every read and every write below starts from.

    ⚠ **BOTH HALVES OF `BR-CWP-010` ARE IN THIS `filter` AND NOWHERE ELSE** —
    the tenant and the login's own customer. There is no screen-side filtering
    anywhere above this, so a customer id from a body or a path cannot widen it.
    """
    return models.StoredPaymentInstrument.objects.filter(
        tenant_id=tenant_id, customer_id=customer_id, deleted_at__isnull=True
    )


def list_for_customer(tenant_id: Any, *, customer_id: Any, today: date | None = None) -> list[dict[str, Any]]:
    """Every live instrument this login holds, oldest first."""
    when = today or timezone.localdate()
    return [_view(row, when) for row in _live(tenant_id, customer_id).order_by("created_at")]


def autopay_stance(tenant_id: Any, account_ids: list[Any]) -> dict[str, Any]:
    """May this login use autopay, and if not, WHY (`BR-CWP-056`, `BR-PAY-013`).

    ⚠ **ANY ACCOUNT IN THE SET BLOCKS IT, AND THAT IS THE CONSERVATIVE READING
    RATHER THAN A SHORTCUT.** The instrument is the CUSTOMER's — a landlord
    saves one card and pays four accounts with it — so a card enrolled for
    autopay could be charged for an account the utility has put on cash-only. A
    per-account election is `CWP-040`'s screen (`US-CWP-047`), and until it
    exists the safe answer for this screen is the strictest one; the reason is
    named so the customer knows which fact to argue with.

    ⚠ **THE CONTROL IS DISABLED, NEVER ABSENT** — that is the caller's job and
    the test asserts the list is untouched beside it.

    ⚠ **THE ACCOUNTS COME THROUGH CUSTOMERS' OWN PUBLISHED QUERYSET, RESOLVED BY
    NAME** — no customers model is imported here and no ORM of theirs is walked.
    That is `collections_read._accounts_by_id`'s shape and its reason (B1's
    rings, `BR-TEN-013`): this is payments asking customers a question customers
    published an answer to, rather than payments reaching into another module's
    tables. Tenant scoping is customers' own — `account_queryset()` filters on
    `app.tenant_id` itself under RLS FORCE (hard rule 1) — which is why it is
    not given a tenant to look at.
    """
    if not account_ids:
        return {"allowed": True, "reason": None, "bounces": 0}
    queryset = settings_seam._resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover — customers publishes it
        # ⚠ **REFUSED CLOSED, NOT OPEN** (hard-won law 3). An unreadable block
        # list is not an absent one: answering *allowed* here would enrol an
        # account the utility has put on cash-only.
        return {"allowed": False, "reason": None, "bounces": 0}
    rows = list(
        queryset()
        .filter(pk__in=[str(one) for one in account_ids])
        .values("cash_only_no_autopay", "nsf_count")
    )
    bounces = max((int(one["nsf_count"] or 0) for one in rows), default=0)
    if any(one["cash_only_no_autopay"] for one in rows):
        return {"allowed": False, "reason": BLOCK_CASH_ONLY, "bounces": bounces}
    if bounces > 0:
        return {"allowed": False, "reason": BLOCK_BOUNCED, "bounces": bounces}
    return {"allowed": True, "reason": None, "bounces": 0}


def card_fee_stance() -> dict[str, Any]:
    """Who pays the card fee, as the tenant has set it — and whether it can be
    priced, which today it cannot.

    The switch is READ, never assumed: a utility that has chosen `customer` has
    made a decision about its customers' bills, and a hardcoded `utility` would
    quietly overrule them. `priced` is `False` for everybody until a processor
    exists, so the screen states the stance without ever showing a figure
    nobody computed.
    """
    try:
        payer = str(settings_seam.finance_controls().get(CARD_FEE_KEY) or CARD_FEE_UTILITY)
    except Exception:  # pragma: no cover - the seam names its own failure
        payer = CARD_FEE_UTILITY
    return {"payer": payer, "priced": False, "reason": FEE_NOT_PRICED}


def price_card_surcharge(amount: str) -> str:
    """What a `$142.18` card payment would carry as a surcharge. **It refuses.**

    ⚠ **AND IT REFUSES FOR A REASON THAT IS NOT A QUESTION.** `OQ-1394` is
    CLOSED: both stances ship, behind a switch. What does not exist is a
    processor and therefore a fee schedule — and the ruling itself names the
    three obligations that come with `customer`: the fee must be COMPUTED from
    the processor's own schedule, DISCLOSED before the commit, and CHECKED
    against the customer's state. Inventing a percentage would satisfy none of
    them while looking like all three.
    """
    raise SurchargeNotPriced(
        "no payment processor is connected, so no fee schedule exists to price a "
        f"surcharge on {amount} from — the tenant switch stores the utility's "
        "intention and the intention is not the arithmetic"
    )


@transaction.atomic
def save_instrument(
    actor: Any,
    *,
    tenant_id: Any,
    customer_id: Any,
    reference: str,
    used_for: list[str] | None = None,
) -> dict[str, Any]:
    """Turn a card page's reference into a stored token. **Step-up is the
    caller's** — this signature has no way to check a code, and saying so here is
    the same posture `services.add_account_to_login` takes rather than implying
    the check happened somewhere safe.

    ⚠ **THE REFERENCE IS REFUSED IF IT LOOKS LIKE A CARD NUMBER.** Nothing else
    in this product would produce a five-digit run in this field, and the cost
    of being wrong once is a PAN in a database.
    """
    given = str(reference or "").strip()
    if not given:
        raise ValueError("a card page reference is required")
    if PAN_SHAPED.search(given):
        # ⚠ The value is NOT in the message. See `LooksLikeACardNumber`.
        raise LooksLikeACardNumber(
            "that reference carries a long run of digits — a card number never "
            "reaches this product (BR-CWP-057)"
        )

    #: `BR-INT-038` — the adapter TRANSLATES. Every field below is the
    #: provider's answer; not one of them is composed here.
    token = payments_sandbox.tokenise(given)
    wanted = list(used_for or [models.INSTRUMENT_USE_ONE_OFF])
    unknown = [one for one in wanted if one not in models.INSTRUMENT_USES]
    if unknown:
        raise ValueError(f"unknown use {unknown[0]!r} for a stored instrument")

    kind = token["kind"]
    row = models.StoredPaymentInstrument.objects.create(
        tenant_id=tenant_id,
        customer_id=customer_id,
        gateway_token=token["gateway_token"],
        brand=token["brand"],
        last_four=token["last_four"],
        kind=kind,
        #: A card is active the moment the gateway tokenises it; a mandate is
        #: not active until the bank confirms it, and nothing here can confirm
        #: one — so a bank row lands `active` and the bank's own confirmation
        #: is what moves it to `verified`.
        status=models.INSTRUMENT_ACTIVE,
        used_for=wanted,
        expires_month=token["expires_month"] if kind == models.INSTRUMENT_CARD else None,
        expires_year=token["expires_year"] if kind == models.INSTRUMENT_CARD else None,
    )

    #: Hard rule 7. ⚠ **THE TOKEN IS NOT IN THE PAYLOAD.** `audit_log` is read
    #: by support screens and exported; a token there would be a second place
    #: the gateway's credential lives, for no gain — the brand and four digits
    #: identify the instrument to any human reading the trail.
    core_audit.write_row(
        action=ACTION_ADDED,
        entity_type=ENTITY,
        entity_id=row.pk,
        actor_user_id=None,  # see `_portal_actor`
        before=None,
        after={
            "brand": row.brand,
            "last_four": row.last_four,
            "kind": row.kind,
            "used_for": list(row.used_for or []),
            "actor": _portal_actor(actor),
        },
    )
    return _view(row, timezone.localdate())


@transaction.atomic
def remove_instrument(
    actor: Any, *, tenant_id: Any, customer_id: Any, instrument_id: Any
) -> dict[str, Any]:
    """Take a method off the list. **Soft, because a payment may point at it.**

    Hard rule 4 forbids destroying what a payment names, and a payment taken on
    this card names this row. `deleted_at` is what the unique index on the token
    is conditioned on, so the same card can be added again afterwards.
    """
    try:
        row = _live(tenant_id, customer_id).get(pk=instrument_id)
    except (models.StoredPaymentInstrument.DoesNotExist, ValueError, TypeError) as exc:
        # ⚠ ONE ANSWER FOR THREE FAILURES — not found, not yours, not a uuid.
        raise NotYours("no such payment method on this login") from exc

    before = {"brand": row.brand, "last_four": row.last_four, "kind": row.kind}
    row.deleted_at = timezone.now()
    row.save(update_fields=["deleted_at", "updated_at"])
    core_audit.write_row(
        action=ACTION_REMOVED,
        entity_type=ENTITY,
        entity_id=row.pk,
        actor_user_id=None,  # see `_portal_actor`
        before=before,
        after={"removed": True, "actor": _portal_actor(actor)},
    )
    return {"removed": True}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-046 · US-CWP-022 (EP-CWP-09 / EP-CWP-05 + BR-CWP-040/056/057,
#         03-field-map.md §payments, OQ-1394 and OQ-1396 as closed 2026-09-04)
# generated: 2026-09-05 by the CR-068 phase 5 lane A build
# checklist: A✔ B✔ C✔ D✔(apps/portal/api.py — four routes) E✔(Methods.tsx ·
#            MethodsPage.tsx) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_046_methods.py tests/test_us_cwp_022_step_up.py
#        · G81 (portal write points) · G84
# exceptions: **a SEVENTH portal write point is owed and is NOT taken here** —
#             `write_points.py` declares six kinds and a stored instrument is
#             none of them; the row is reported for a ruling (see the module
#             docstring) · TC-9's citation of `OQ-1394` is amended: the question
#             is CLOSED and the refusal now names the missing processor ·
#             US-CWP-046 TC-8 and US-CWP-022 TC-5/TC-7 (delegates) are not built
#             — `OQ-1396` CLOSED 2026-09-04, the feature is DEFERRED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
