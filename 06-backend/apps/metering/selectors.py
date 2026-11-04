# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (S14 premises list + roll-up + capability row) ·
#           US-MET-002 (S15 units list — meters cell, DERIVED occupancy) ·
#           US-MET-003 (S16 wizard reads: premises types, meter grid options) ·
#           US-MET-005 (S26/S27 read-only ops tabs — derived progress) ·
#           US-MET-006 (S8 config tables + membership read) · US-MET-016 (the
#           J6 correction linkage beside the supersession chain) · US-AST-012
#           (typed read records + the quantities-only rating interface) ·
#           US-MET-013 (the dispute marker on a read) · US-MET-019 (the S25
#           Disputed chip and the TC-4 drill-in behind it)
#           CR-030 W5 tasks 5.2 + 5.3 (unit_assets · unit_pricing — B18
#           §5.5.5; NO STORY OWNS EITHER, hard-won law 8, REPORTED)
#           Screens: S14, S15, S16, S26, S27, S8, S25, S29
# Rules:    BR-MET-001/002 (identity) · BR-MET-003 (services ⊆ enabled) ·
#           BR-MET-011 (progress derives from committed reads, never stored) ·
#           BR-MET-033 (membership + optional walk order) · BR-MET-034
#           (premises types = Reference data) · BR-MET-036 (occupancy DERIVED
#           from the active account) · BR-MET-037 (delete-guard counts) ·
#           BR-MET-045 (detail tabs) · BR-MET-024 (the dispute marker feeds the
#           S25 count AND holds the account from the bill run — OQ-043 closure) ·
#           IS-2/IS-3/IS-4 (sort · search · filters)
#           BR-AST-004 (post-CR-028: exactly ONE tab per asset — the W5
#           grouping key) · BR-RAT-027 (plan base Σ is RATING's derived
#           figure, forwarded not recomputed) · BR-RAT-081 / DEF-495 (the
#           metered declaration has no reader, so `reading_expected` is a
#           STATED ABSENCE) · BR-MET-100 (an unplanned unit is not an error)
#           AMENDED 2026-08-11 (tenant custom-fields lane): `custom_data_for_location`,
#           PUBLISHED FOR BILLING (B2 r17.2 — unit + premises values in one read;
#           `service_points` deliberately absent, OQ-118).
# Tests:    06-backend/tests/test_us_met_001_002_lists.py ·
#           test_us_met_005_006_routes_cycles.py ·
#           test_w5_unit_reads.py (CR-030 W5 5.2/5.3)
# Impacts:  apps/metering/api.py (every read) · apps/metering/services.py
#           (before/after audit snapshots) · apps.assets (unit reference reads)
# ───────────────────────────────────────────────────────
"""metering read path (LAW 0: api thin → services sole writer → selectors read).

Every query is tenant-filtered at the app layer AND backed by RLS on Postgres
— the filter is convenience, RLS is the law (the G5 isolation suite proves it;
sqlite exercises the filter). No cross-module ORM: neighbour data arrives
through apps/metering/seams.py.

Occupancy and unit status are COMPUTED here and stored nowhere (BR-MET-036 /
US-MET-002 §5); the S26/S27 collected/progress figures are derived from
committed reads and render as null while the W2 reads lane is unwired — a
fabricated 0 would read as "nothing collected", which is a different claim.
"""

import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from django.apps import apps as django_apps
from django.db import connection
from django.db.models import Count, F, IntegerField, OuterRef, Q, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.metering import (
    completeness,
    counted_reading,
    models,
    owner_selectors,
    period_engine,
    quantity_display,
    read_import,
    register_units,
    schedule,
    seams,
)
from core import errors
from core import batch_reads
from core import search as core_search
from core import tenancy as core_tenancy
from core.pagination import ListParams, filter_values

# US-MET-001 capability row (S14): sortable columns → ORM fields.
PREMISES_SORTS = {
    "premise_no": "premise_no",
    "address": "address_line",
    "type": "premises_type__name",
    "status": "status",
    # `DEF-MET-10164` (PO 2026-10-17) — *"sort, oldest to newest"*. ONE sort
    # name for two columns: the list's **Created** and **Age** headers both
    # send `created`, because an age is only the distance from this stamp to
    # today and a second sort name would be a second answer to one question.
    # `_order` adds the `id` tie-break, so an import that stamped 400 rows
    # with one date still pages in a stable order.
    "created": "created_at",
}
PREMISES_DEFAULT_SORT = "premise_no"
# US-MET-002 capability row (S15).
UNIT_SORTS = {
    "unit_no": "unit_no",
    "premise": "premises__premise_no",
    # CR-089 wave E (`E1`/`PUJ-22`) — the S15 list now leads its second column
    # with the ADDRESS and prints the premise number beneath it, so it needs a
    # sort that agrees with what it shows. `premise` above is KEPT and still
    # orders by the number: it is the URL grammar live links already carry
    # (`?sort=premise`), and a column that changed what an existing sort name
    # means would re-order somebody's saved view without saying so.
    "address": "premises__address_line",
    "label": "label",
    "type": "unit_type",
    # `DEF-MET-10164` — the unit's OWN stamp, never its building's (PO: *"a
    # unit added in 2015 to a 1996 building is 11 yrs"*). One name for two
    # headers, for `PREMISES_SORTS["created"]`'s reason.
    "created": "created_at",
}
UNIT_DEFAULT_SORT = "unit_no"

#: How many of a building's existing unit labels `premises_lends_dict` prints
#: before it says there are more. Four, because the sentence it feeds —
#: *"1 unit today, numbered 1"* — is there to tell a clerk what the NEXT label
#: should look like, and four examples answer that where forty would not.
UNITS_TODAY_LABELS_SHOWN = 4


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _order(qs: QuerySet, sorts: dict[str, str], sort: str | None, direction: str) -> QuerySet:
    field = sorts.get(sort or "", sorts[next(iter(sorts))])
    prefix = "-" if direction == "desc" else ""
    return qs.order_by(f"{prefix}{field}", "id")  # IS-2 stable secondary sort


# ── premises types (BR-MET-034 Reference data) ──────────────────────────────
def premises_types() -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "active": row.active,
            "is_system": row.is_system,
            # `CR-162-BRC10` — the ACCOUNT TYPE a premises of this type takes.
            "account_kind": row.account_kind,
        }
        for row in models.PremisesType.objects.filter(tenant_id=_tenant_id()).order_by("name", "id")
    ]


# ── premises (S14) ──────────────────────────────────────────────────────────
def _premises_master_account_cells(
    row: models.Premises,
    *,
    expand: bool,
    numbers: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`BR-MET-1181` — the five cells every premises read carries about its
    master account, from ONE reading of the ruled precedence.

    ⛔ **THE PRECEDENCE IS NOT RE-IMPLEMENTED HERE.**
    `premises_owners.premises_master_account_link` owns it; this is a
    serialiser. A second reading in a dict comprehension is exactly how the
    money path and the screen come to disagree about who owns a building —
    `BR-CUS-171` already records what that felt like.

    **WHERE THE NUMBER AND THE NAME COME FROM, AND WHY IT IS THREE CASES AND
    NOT ONE.** Both travel together, from the same place, in every case —
    ⚠ **which is the fix for `DEF-MET-6304` and is stated as a rule rather than
    left to each branch.** The Owner cell read *"No name recorded ·
    AC-2026-00051"* on every list row that HAD an account, because the number
    was served here and the name was not; a screen given one and not the other
    has to invent a sentence for the gap, and the sentence it invented was
    false.

      * **A DETAIL read (`expand=True`)** takes both out of the expansion it is
        already paying for. **No extra statement at all** — the account summary
        carries `account_no` AND `name`, and reading either twice would be a
        second answer to one question.
      * **A LIST (`expand=False`, `numbers` supplied)** takes both from the
        page's batched answer — two statements for fifty rows, and two for two.
      * **ANY OTHER caller (`expand=False`, no `numbers`)** gets `None` for
        both, and `master_account_expanded: false` says nobody asked. ⚠ **THIS
        IS DELIBERATE AND THE EXPORT IS WHY.** `exports.PREMISES` serialises
        EVERY premises the tenant has, one row at a time, with no page to batch
        over; a per-row fallback here would put one statement per property into
        a file that runs over the whole register — which is `DEF-324` re-created
        in the one place `NFR-3` cares about most. **An opt-in batch is the only
        shape that cannot be reached accidentally.**

    ⛔ **`master_account_name` IS NOT `row.owner_manager` AND MAY NEVER BE
    BACKFILLED FROM IT.** That column is the free text somebody typed for the
    OWNER of the building; this is the name on the ACCOUNT, which is a party
    the utility bills and which is not always the same one. `BR-MET-151` clause
    3 forbids deriving a fact about a real party from a typed string — *"a
    heuristic over legal suffixes would be a silent claim about a real party"* —
    and a seeder has already been failed for one. An account with nobody named
    answers `None` and the screen says so.
    """
    from apps.metering import premises_owners, seams

    account_id, source = premises_master_account_from_row(row)
    if account_id is None:
        return {
            "master_account_id": None,
            "master_account_source": None,
            "master_account_no": None,
            "master_account_name": None,
            "master_account": None,
            "master_account_expanded": bool(expand),
        }
    key = str(account_id)
    summary = seams.owner_master_account_summary(account_id) if expand else None
    if summary is not None:
        # ── `BR-MET-1181` — *Already owns 3 other properties* ────────────────
        # ⛔ **THE BLUEPRINT DRAWS THIS LINE AND NO SERVER FACT FED IT.** It is
        # the reverse reading of the declared link — `premises_ids_owned_by_account`
        # — and it CANNOT come from `customers`, because how many addresses name
        # an account is a METERING fact and asking customers for it would be a
        # seam pointing back at its own caller.
        #
        # ⚠ **OTHER properties, so THIS one is not counted.** *"Already owns 1
        # other property"* on a building's own page, counting that building, is
        # a sentence that reads as a second address the clerk cannot find.
        #
        # ⚠ **IT REPLACES A COUNT THAT NOW MEANS SOMETHING ELSE.** The screens
        # drew `owner.premises_count` — how many addresses point at the OWNER
        # RECORD — and the owner record is out of the chain under this ruling, so
        # on an address with no owner record that line read zero for ever with
        # every test green. That is `DEF-CUS-3653`'s shape, and it is why this is
        # served rather than left for the screen to derive.
        #
        # **DETAIL ONLY.** It is one more statement per call, which is exactly
        # what a LIST may not spend (`DEF-324`); `master_account_expanded: false`
        # already tells a list row that nobody asked.
        owned = premises_owners.premises_ids_owned_by_account(account_id)
        summary = {
            **summary,
            "owns_premises_count": max(
                len([pid for pid in owned if str(pid) != str(row.id)]), 0
            ),
        }
    return {
        "master_account_id": key,
        "master_account_source": source,
        "master_account_no": (
            summary.get("account_no")
            if summary
            else ((numbers or {}).get(key) or {}).get("account_no")
        ),
        # `DEF-MET-6304` — the same three cases as the number above it, on
        # purpose and in the same expression shape, so the two cells cannot
        # drift into one being served where the other is not. That drift IS the
        # defect: a row with a number and no name renders an absence sentence
        # about an account that is perfectly well named.
        "master_account_name": (
            summary.get("name") if summary else ((numbers or {}).get(key) or {}).get("name")
        ),
        "master_account": summary,
        "master_account_expanded": bool(expand),
    }


def premises_master_account_from_row(row: models.Premises) -> tuple[Any, str | None]:
    """The ruled precedence read off a row that is ALREADY IN MEMORY.

    ⚠ **IT IS THE SAME ORDER AS `premises_owners.premises_master_account_link`
    AND THAT IS ASSERTED BY A TEST, NOT BY THIS COMMENT** (hard-won law 1 —
    a comment claiming a guarantee is not the guarantee). Two readings exist for
    one reason: that one takes an id and issues a query, and a list holding 200
    rows must not issue 200 of them. **If they ever disagree, the money path is
    right and this is wrong**, because that one is what the seam calls.

    `row.owner` is followed only when the premises declares nothing itself, and
    a list that has not `select_related("owner")` pays a query there — which is
    why `premises_list` does.
    """
    from apps.metering.premises_owners import (
        MASTER_ACCOUNT_SOURCE_OWNER_RECORD,
        MASTER_ACCOUNT_SOURCE_PREMISES,
    )

    if row.master_account_id:
        return (row.master_account_id, MASTER_ACCOUNT_SOURCE_PREMISES)
    if row.owner_id and row.owner.master_account_id:
        return (row.owner.master_account_id, MASTER_ACCOUNT_SOURCE_OWNER_RECORD)
    return (None, None)


def managed_by_for_master_accounts(account_ids: Any) -> dict[str, str | None]:
    """`CR-177-BRC10` task 1b — *Managed by* on the Owner card, ONE statement
    for a page.

    ⚠ **AN ACCOUNT HAS NO *MANAGED BY* OF ITS OWN** — no column in `customers`
    holds one. The fact lives here, as `premises.owner_manager`: the name typed
    for who manages a property this master account already owns. So the card
    reads it from those properties, every distinct name in premise-number
    order joined by ` · `, and an account owning none (or none with a name)
    reads `None` and is drawn as an absence (decision log 2026-10-09,
    `CR-177-BRC10` judgment 3).
    """
    ids = [str(a) for a in (account_ids or []) if a]
    if not ids:
        return {}
    seen: dict[str, list[str]] = {key: [] for key in ids}
    for account_id, manager in (
        models.Premises.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True, master_account_id__in=ids
        )
        .exclude(owner_manager__isnull=True)
        .exclude(owner_manager="")
        .order_by("premise_no", "id")
        .values_list("master_account_id", "owner_manager")
    ):
        names = seen.setdefault(str(account_id), [])
        text = str(manager).strip()
        if text and text not in names:
            names.append(text)
    return {key: (" · ".join(names) if names else None) for key, names in seen.items()}


def premises_master_account_numbers(rows: Any) -> dict[str, dict[str, Any]]:
    """`BR-MET-1181` — every master account number on ONE PAGE, in one statement.

    ⛔ **THIS IS WHAT LETS A LIST DRAW AN ACCOUNT NUMBER WITHOUT BUYING
    `DEF-324` A SECOND TIME.** The list does not expand accounts — one account
    read plus one ledger derivation per row is what that defect measured at *47
    of 118 profiled seconds answering one question 304 times* — and B14 rule 31
    forbids drawing the id it does have. So the page's ids are collected once
    and asked once.

    `{}` for a page where nothing declares an account, which costs no query at
    all. Handed to `premises_detail_dict` as `master_account_numbers`; a caller
    that omits it gets a per-row read, which is right for a DETAIL and wrong for
    a list.
    """
    from apps.metering import seams

    ids = {
        str(account_id)
        for account_id in (premises_master_account_from_row(row)[0] for row in rows or [])
        if account_id
    }
    return seams.master_account_numbers(sorted(ids)) if ids else {}


def premises_detail_dict(
    row: models.Premises,
    *,
    with_owner_account: bool = True,
    master_account_numbers: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    unit_qs = models.Unit.objects.filter(tenant_id=row.tenant_id, premises=row)
    return {
        "id": str(row.id),
        "premise_no": row.premise_no,
        # `DEF-MET-10164` — the stamp the lists' Created and Age columns read.
        # Served as the INSTANT, never as a day: which day it is depends on the
        # tenant's zone, and the screen already turns an instant into a day in
        # that zone (`DateCell.todayInZone`). A day served from here would cost
        # a zone read per row or be read on the server's clock. Stamped by the
        # system on save; an import may carry the old system's date
        # (`import_runs.CREATED_FIELD`); no screen edits it.
        "created_at": row.created_at.isoformat() if row.created_at else None,
        # `CR-161-BRC10` W3 · `DEF-MET-9226` — the tenant's own answers, which
        # the Premise page, Edit premise and the premises list column read.
        # Served on the list row too: one more key per row, never a second read.
        "custom_data": dict(row.custom_data or {}),
        "name": row.name,
        "address_line": row.address_line,
        "city": row.city,
        "state": row.state,
        "postal_code": row.postal_code,
        "premises_type": row.premises_type.code if row.premises_type_id else None,
        "premises_type_name": row.premises_type.name if row.premises_type_id else None,
        # `CR-162-BRC10` (Q1) — the ACCOUNT TYPE this premises' type takes
        # (`master` / `regular`, or `None` when nobody has answered), so the
        # Common areas tab opens or closes the master form on the same fact
        # the server's guard reads.
        "premises_account_kind": (
            row.premises_type.account_kind if row.premises_type_id else None
        ),
        # BR-MET-071 / BR-MET-083 — the area tag, in the THREE shapes the three
        # readers need and none of them derived on the client:
        #   · `area_code`   the form posts it back unchanged (the picker's value)
        #   · `area_parent_code` the form re-opens on the right LEVEL without a
        #                   second request — a sub-area's picker must show its
        #                   parent selected in the Area box and itself in the
        #                   Sub-area box, and the client cannot know which of
        #                   the two a bare code is
        #   · `area_path`   what a human reads: "South · SE" (the same
        #                   `parent · child` join `route_premises_picker`
        #                   already renders, so the two never diverge)
        # ⚠ **DEF-507 — THREE STATES, AND THE THIRD ONE DECIDES MONEY.**
        # `inside_city_limits` has been stored since migration 0013 for
        # BR-RAT-101/102's outside-city surcharge and no selector served it, so
        # the flag deciding whether every bill at this address carries a ×1.5
        # multiplier reached the rating engine and reached NO SCREEN. PRM-02
        # printed a paragraph saying so instead of the answer (PO, 2026-08-26:
        # *"Why Juridiction is showing the in text it should shown inside city
        # and outside city"*).
        #
        # Served as the column stands — `True` / `False` / `None` — for exactly
        # the reason `services_available` below is (DEF-762): `None` means
        # **nobody was ever asked**, and collapsing it into `False` here would be
        # the serialiser answering *outside the city* on the utility's behalf, on
        # the one field in this dict that adds a surcharge to every future bill.
        # `rating.resolution` already reads all three (`resolution.py:865` — None
        # takes no multiplier and says why); the screen now reads the same three.
        #
        # ⚠ **NO LONGER READ-ONLY (CR-039 wave C task 10, 2026-08-27).** These
        # four lines said *"`services._validate_premises` does not accept the
        # field, so no screen can SET it … where an edit control belongs (and
        # whether changing it re-rates issued bills) is a bigger question than
        # this defect — REPORTED, not invented"*. Both halves are answered:
        # `_validate_premises` takes the three states, `JurisdictionField` draws
        # them on the S16 single step and the PRM-01 edit modal, and the
        # re-rating question is `OQ-423` with the product's forward-only
        # behaviour stated in `update_premises`'s own docstring.
        "inside_city_limits": row.inside_city_limits,
        "area_code": row.area.code if row.area_id else None,
        "area_name": row.area.name if row.area_id else None,
        "area_parent_code": (row.area.parent.code if row.area_id and row.area.parent_id else None),
        "area_path": (
            f"{row.area.parent.name} · {row.area.name}"
            if row.area_id and row.area.parent_id
            else (row.area.name if row.area_id else None)
        ),
        # ⚠ **`None` IS SERVED AS `null`, AND THAT IS THE WHOLE OF DEF-762.**
        # This line read `list(row.services_available or [])`, which turned SQL
        # NULL into `[]` — and CR-036 (h) says plainly that the two are
        # DIFFERENT ANSWERS: an existing premises holds NULL because **nobody
        # was ever asked**, while `[]` is a clerk saying *this address offers
        # nothing*. The no-backfill rule (pinned by
        # `tests/test_cr036h_premises_services_write.py`) exists to keep that
        # distinction in the column; collapsing it HERE undid the rule one layer
        # above it, and every screen printed "No services" for both.
        #
        # The column is passed through unchanged rather than described by a
        # second `services_asked` flag: one nullable field cannot contradict
        # itself, where two fields can (`asked: false` beside a non-empty list is
        # representable and meaningless), and hard-won law 5 is the same shape —
        # one source, views derived. The list is still COPIED (never the model's
        # own object) so a caller cannot mutate the row through the dict.
        "services_available": (
            None if row.services_available is None else list(row.services_available)
        ),
        # ⚠ **THE FREE TEXT AND THE TYPED OWNER ARE BOTH SERVED, AND NEITHER
        # SUBSTITUTES FOR THE OTHER** (CR-039 wave C tasks 12-13, PO 2026-08-27:
        # *"category is okay, no richer text"*).
        #   · `owner_manager` is the legacy string. It is what
        #     `customers.services.open_account` reads for the default payer, so
        #     it is NOT collapsed into the typed record here — whether the typed
        #     owner should supersede it is `OQ-500`, a money decision nobody has
        #     taken, and a serialiser is the last place to take it.
        #   · `owner` is the typed party (BR-MET-150) or `null`.
        #   · `owner_unmatched` is BR-MET-151's computed state, served rather
        #     than derived on the client: text and no link. The review surface
        #     and this badge therefore mean exactly the same thing, because both
        #     read the one definition.
        "owner_manager": row.owner_manager,
        # ── DEF-650 · BR-MET-400 — the typed owner, WITH its account ────────
        # ⚠ **`with_owner_account=False` ON THE LIST AND THE EXPORT, AND IT IS
        # THE SAME N+1 DEF-324 MEASURED.** Expanding the owner's account costs
        # one account read plus one LEDGER derivation per row — and S14 is one
        # of the two screens a utility opens most, while the CSV export runs
        # over every premises the tenant has. The row still carries
        # `owner.master_account_id` (a column, joined) and
        # `owner.master_account_expanded: false`, so a caller can tell *not
        # asked* from *no account is linked*.
        "owner": (
            owner_selectors.owner_detail_dict(row.owner, with_account=with_owner_account)
            if row.owner_id
            else None
        ),
        "owner_unmatched": bool((row.owner_manager or "").strip()) and row.owner_id is None,
        # ── 2026-09-22 · `BR-MET-1181` — THE ADDRESS NAMES ITS MASTER ACCOUNT ──
        # ⛔ **PO ruling:** *"why you are point is at owner id - why not directly
        # at master accoutn Id - it will solev the problem"*. **These four keys
        # are the chain a screen walks, and `owner` above is no longer part of
        # it.** They are served on EVERY premises read because a fact a screen
        # must state is a fact the read must carry (hard-won law 2), and because
        # `DEF-CUS-3653` is what an absence costs: a header line composed from a
        # retired value returned null for ever with every test green.
        #
        #   · `master_account_id`     the LINK — what a form posts back and what
        #                             a charge posts to.
        #   · `master_account_source` WHICH declaration answered: `premises` (the
        #                             ruling's own column) or `owner_record` (the
        #                             pre-ruling link, on rows that predate it).
        #                             `BR-MET-1162`'s shape — a unit showing a
        #                             point says whether it is its own or its
        #                             building's; here the same sentence decides
        #                             who is billed. `null` where neither names
        #                             one, which is a real state and is what the
        #                             **Needs an owner** filter finds.
        #   · `master_account_no`     B14 rule 31: **no database id is ever the
        #                             visible value of a field.** Without this
        #                             every screen either prints a UUID or fetches
        #                             the account a second time to print a number.
        #                             It rides free — ONE batched read per page,
        #                             never one per row (see `premises_list`).
        #   · `master_account`        the account's own details, read through the
        #                             seam at the moment of asking, so nothing is
        #                             copied onto a metering row and nothing can
        #                             drift. `null` on the list and the export.
        #
        # ⚠ **`master_account: null` MEANS TWO THINGS, SO THE SECOND IS SPELLED
        # OUT** (`DEF-324` · `DEF-762`) — `master_account_expanded` says whether
        # anybody asked, exactly as `owner.master_account_expanded` does.
        **_premises_master_account_cells(
            row, expand=with_owner_account, numbers=master_account_numbers
        ),
        "external_ref": row.external_ref,
        # ── 2026-09-17 · `BR-MET-1173` — THE CITY'S KEY, BESIDE THE IMPORT KEY
        # AND NOT INSTEAD OF IT. Two facts, two columns, both served: one is
        # what a utility's PREVIOUS SOFTWARE called this property, the other is
        # what the CITY calls it. Until today the second was overwriting the
        # first, which would have collided on the very first run at any utility
        # that had migrated.
        #
        # ⚠ **SERVED, NOT MERELY STORED** (hard-won law 2). The account header
        # is the cautionary tale one column along: `DEF-CUS-3653` had a screen
        # composing a locality from a retired value and returning null for ever
        # with every test green.
        "gis_parcel_id": row.gis_parcel_id,
        "gis_parcel_id_was": row.gis_parcel_id_was,
        "gis_key_changed_at": row.gis_key_changed_at,
        "gis_status": row.gis_status,
        "gis_verified": row.gis_verified,
        "gis_verified_at": row.gis_verified_at,
        # ⚠ **CR-069 wave M · `OQ-INT-1471` — THE MARK IS THE WHOLE RULING, SO
        # IT IS SERVED WHEREVER A PREMISES IS READ.** `true` means **the City
        # has not confirmed this address** — it was typed rather than picked
        # from the City's own list, whether because the City was unreachable
        # (the ruled branch), because nobody searched, or because the clerk
        # typed her own after seeing the candidates (`DEF-INT-4266`: three
        # paths, and every document named one). The question this answers
        # said in its own words that the unsafe case *"looks identical on
        # screen to the good case"*, so a column nothing renders would be
        # hard-won law 2 rather than compliance.
        "gis_unchecked": bool(row.gis_unchecked),
        # ── CR-089 wave A `PUJ-10` — THE POINT, ON THE ONE SCREEN WHOSE
        # SUBJECT IS A PLACE ────────────────────────────────────────────────
        # `premises.lat`/`lng` have existed since CR-028 and **657 of 673
        # properties carry one that no screen has ever read** (CR-089 §4). This
        # is the line that ends that. Served as the stored NUMERIC(9,6)
        # STRINGS, never floats: the wire carries what the column holds, which
        # is the same posture `unit_premises_geo_index` already takes for the
        # map, so a figure on the property page and a pin on the map are the
        # same number.
        # `null` is a real state and the screen draws it as one — *No point
        # recorded*, which is what the **Needs a location** filter finds.
        "lat": _coord_str(row.lat),
        "lng": _coord_str(row.lng),
        # ── CR-089 wave A `PUJ-10` — *Checked against GIS*, WITH WHO AND WHEN ─
        # ⚠ **THE FLAG ALONE IS NOT THE ANSWER, AND SERVING IT ALONE WAS THE
        # BUG WAITING TO HAPPEN.** `gis_unchecked` is `NOT NULL DEFAULT false`,
        # so on all 673 properties it reads *false* — and a screen that drew
        # *false* as **Checked** would tell a clerk the whole estate had been
        # verified by somebody, when in fact nobody has ever checked one. The
        # pair decides: a property is **Checked** only where a person pressed
        # the control and `gis_checked_at` records when.
        "gis_checked_at": (
            row.gis_checked_at.date().isoformat() if row.gis_checked_at else None
        ),
        # `full_name or email` is this module's own convention for naming a
        # person (`route_sheet.py:160`) — an invited user's name is `""` until
        # they accept, and a blank beside a date reads as a broken row.
        "gis_checked_by": (
            (row.gis_checked_by.full_name or row.gis_checked_by.email)
            if row.gis_checked_by_id
            else None
        ),
        "status": row.status,
        "units": unit_qs.filter(deleted_at__isnull=True).count(),
        # BR-MET-101 — r10's PRM-02 tile reads "3 + common". `units` stays the
        # TOTAL (BR-MET-037's delete guard and every existing reader count on
        # that); the split rides beside it and the screen derives the "3" by
        # subtraction, so the two numbers cannot disagree.
        "units_common": unit_qs.filter(deleted_at__isnull=True, is_common_area=True).count(),
    }


# ── THE STAFF ADDRESS SEARCH'S FIELD LISTS — `CR-200-BRC10` S2–S6 ─────────
#
# PO 2026-10-29, Question 3 A: *"each typed word may match the address or the
# unit label, on Units and Premises lists"*, and the code plan *"this is ok"*:
# the Premises list, Units list, Move-in unit picker, Premises picker and top
# search bar share ONE word-by-word matcher (`core.search.matches_every_word`)
# and metering owns what it is matched against. "12 Oak 2B" finds Apt 2B at
# 12 Oak St; before, every word was matched as one phrase in one field
# (`DEF-MET-10678`). The measured "before" of all five is the CR file's §6a.
#
# The address lives on `premises` and nowhere else (hard rule 8), so a UNIT is
# found by its building's street by WALKING to `premises__…`, never by a column
# of its own. The two tuples are the places' SHARED floor: a search may add its
# own fields (the Premises list keeps owner and parcel) but never drops one.
PREMISES_WORD_FIELDS: tuple[str, ...] = (
    "address_line",
    "city",
    "postal_code",
    "premise_no",
    "name",
)
UNIT_WORD_FIELDS: tuple[str, ...] = (
    "label",
    "unit_no",
    "premises__address_line",
    "premises__city",
    "premises__postal_code",
    "premises__premise_no",
    "premises__name",
)


def premises_with_unit_word(word: str) -> Q:
    """A premises a word may match through a UNIT inside it — its label or number.

    A lazy subquery (`pk IN (SELECT premises_id …)`), never a join: a join on the
    reverse FK would repeat the premises once per matching unit and break the
    page count. Removed units do not answer. Tenant-scoped at source (rule 1).
    """
    return Q(
        pk__in=models.Unit.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .filter(Q(label__icontains=word) | Q(unit_no__icontains=word))
        .values("premises_id")
    )


def premises_word_match(term: str, extra_fields: tuple[str, ...] = ()) -> Q:
    """The premises searches' matcher: every word, any premises field or unit."""
    return core_search.matches_every_word(
        term, PREMISES_WORD_FIELDS + extra_fields, also=premises_with_unit_word
    )


def unit_word_match(term: str) -> Q:
    """The unit searches' matcher: every word, the unit or its building."""
    return core_search.matches_every_word(term, UNIT_WORD_FIELDS)


def premises_list(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> QuerySet:
    """S14 rows. Search = address · premise_no · owner_manager (BR-MET-041's
    metering twin: US-MET-001 capability row); filters AND-combine (IS-4)."""
    # `area__parent` is joined because premises_detail_dict renders the
    # "South · SE" path for every row — without it the S14 list is one extra
    # query per tagged premises.
    # `owner__category` joins for the same reason: premises_detail_dict serves
    # the typed owner's category CODE and NAME (BR-MET-150), so without it the
    # S14 list is two extra queries per matched premises.
    # `gis_checked_by` joins for the same reason the four above it do: CR-089
    # wave A puts *Checked against GIS · <who>* on every premises payload, and
    # `premises_detail_dict` is what renders a LIST row — without this join S14
    # is one user read per checked property (the DEF-324 discipline).
    qs = models.Premises.objects.filter(tenant_id=_tenant_id()).select_related(
        "premises_type", "area", "area__parent", "owner", "owner__category", "gis_checked_by"
    )
    filters = filters or {}
    if term := (q or "").strip():
        if len(term) >= 2:  # IS-3: server-side, min 2 chars
            # `CR-200-BRC10` — word by word over the shared premises fields,
            # plus this list's own three: the owner, and (`CR-176-BRC10`, the
            # Add units building search's *"Address, premise number or
            # parcel"*) the utility's own reference and the City's parcel key.
            qs = qs.filter(
                premises_word_match(term, ("owner_manager", "external_ref", "gis_parcel_id"))
            )
    if type_code := filters.get("type"):
        qs = qs.filter(
            Q(premises_type__code__iexact=str(type_code))
            | Q(premises_type__name__iexact=str(type_code))
        )
    if status := filters.get("status"):
        qs = qs.filter(status=str(status))
    # ── BR-MET-138 / DEF-836 · the area filter this list never had ──────────
    #
    # BR-MET-072 has said since 2026-08-16 that *"selecting a PARENT area
    # matches every premises tagged to it and to any of its sub-areas"*, and
    # `_area_predicate` has implemented it since CR-006 — **for the route
    # premises picker and for nothing else.** This function read `type` and
    # `status`, and `core.pagination.parse_list_params` documents that
    # *"undeclared filter names are ignored"*, so S14's own list silently
    # dropped every area the caller asked for and answered with the whole
    # tenant. `test_cr029_w0_seed.py` called it with `area_codes` to prove
    # DEF-220 closed and its `assert list(matched)` was true for `NORTH`, for
    # `IND` and for a code that does not exist — a check that cannot fail.
    #
    # ⚠ THE NAME IS `area`, MATCHING `ROUTE_FILTERS` — never a second spelling
    # for one concept — and the predicate is the EXISTING `_area_predicate`,
    # so "a district covers its sub-areas" is stated once in this module
    # (hard-won law 1) and a premises tagged `North district · NW` is returned
    # by a `NORTH` chip without this line knowing anything about hierarchies.
    if area := filters.get("area"):
        qs = qs.filter(_area_predicate(area))
    # ── CR-089 wave A `PUJ-01` — **Needs a location** ───────────────────────
    # 657 of 673 properties carry a point and 16 do not, and until this line
    # there was no way to ask which sixteen: a clerk could only find them by
    # opening properties one at a time. The predicate is `lat IS NULL OR lng IS
    # NULL` rather than `lat IS NULL` because half a point cannot be drawn
    # either — it is the same *not placed* to everything that reads it.
    # ⚠ **`placed` IS OFFERED TOO, AND NOT ONLY FOR SYMMETRY.** A filter with
    # one value cannot be un-set by choosing the other, and B14's list furniture
    # draws a group of choices; a lone chip is a control a clerk has to know to
    # clear. An unknown value falls through to no filter (BR-SHL-011's spirit)
    # rather than answering with an empty list, which would read as *none of
    # your properties are placed*.
    # ⚠ **THREE VALUES FROM 2026-09-10, NOT TWO (`DEF-4740`'s other half).**
    # The blueprint draws the column and the chip with THREE states —
    # `Checked` · `Placed, unchecked` · `Not placed` — and argues for the split
    # in its own words: *"a point that arrived from an address lookup and a
    # point a person has seen against the city map are different degrees of
    # confidence."* With only `placed` a clerk could ask *is there a point at
    # all* and could not ask *which of these still needs a person's eye*, which
    # is over half the work the wave exists to end.
    #
    # ⚠ **`checked` READS `gis_checked_at`, NEVER `gis_unchecked` ALONE.** That
    # column is `NOT NULL DEFAULT false`, so *false* is what all 673 properties
    # hold and what every create that never mentions it gets — it means *nobody
    # has looked*. Filtering on `gis_unchecked=False` would answer *Checked*
    # with the whole estate, which is DEF-836's shape: a chip that lies.
    # `premisesMapState` on the client draws the same three states off the same
    # two facts, so the column and the chip cannot disagree about a row.
    #
    # `placed` is KEPT and no longer offered on screen: it is the union of the
    # two states above, so a fourth chip would answer with two other chips added
    # together — but it is in URLs bookmarked since wave A and dropping the
    # branch would silently widen those to the whole tenant.
    if location := filters.get("location"):
        wanted = str(location).strip().lower()
        if wanted == "needs_location":
            qs = qs.filter(Q(lat__isnull=True) | Q(lng__isnull=True))
        elif wanted == "placed":
            qs = qs.filter(lat__isnull=False, lng__isnull=False)
        elif wanted == "checked":
            qs = qs.filter(
                lat__isnull=False, lng__isnull=False, gis_checked_at__isnull=False
            )
        elif wanted == "placed_unchecked":
            qs = qs.filter(
                lat__isnull=False, lng__isnull=False, gis_checked_at__isnull=True
            )
    # ── CR-089 wave B `B2` — **Needs an owner** ─────────────────────────────
    #
    # ⚠ **THIS IS NOT A CONVENIENCE FILTER. IT IS THE HALF OF `B1` THAT KEEPS
    # THE REVERSAL HONEST.** `B1` lets a property be created with nobody
    # attached to it (PO 2026-09-08, *"Owner = search ( it should be
    # optional)"*), and CR-089 §2.1 names the cost in the same sentence as the
    # ruling: *"a property can now exist with no party attached to it, so
    # `PUJ-11` and the *Needs an owner* list are not optional extras — they are
    # what stops the reversal creating orphans nobody can find."* This is that
    # list. **`B1` must not ship without it.**
    #
    # ⚠ **IT IS NOT THE SAME QUESTION AS `unmatched_premises_qs()`, AND THE GAP
    # BETWEEN THEM IS THE WHOLE POINT.** That queryset (BR-MET-151, the PRM-04
    # matching surface) reads *has a free-text NAME and no typed record* — it
    # exists to turn strings into parties, so a premises with no string at all
    # is invisible to it BY DESIGN. Measured on the demo utility, 2026-09-09:
    #
    #     79 properties · 6 with a typed owner · 8 with a name and no record
    #                   · **65 with nothing at all**
    #
    # The 8 are on PRM-04. The 65 are on no list in this product, and they are
    # exactly the shape `B1` now creates more of. So the predicate here is
    # `owner_id IS NULL` — 73 of 79 — because the fact that matters to a bill is
    # whether there is a PARTY, not whether somebody once typed a name. A name
    # in a box cannot be sent a shortfall (DEF-650); that is why it was typed
    # into a record in the first place.
    #
    # ⚠ **`has_owner` IS OFFERED TOO, FOR `location`'s REASON ONE BLOCK UP:** a
    # filter with one value cannot be un-set by choosing the other, and B14's
    # list furniture draws a GROUP of choices. An unknown value falls through to
    # no filter (BR-SHL-011's spirit) rather than answering with an empty list,
    # which would read as *none of your properties have an owner*.
    if owner_state := filters.get("owner"):
        wanted = str(owner_state).strip().lower()
        if wanted == "needs_owner":
            qs = qs.filter(owner_id__isnull=True)
        elif wanted == "has_owner":
            qs = qs.filter(owner_id__isnull=False)
    return _order(qs, PREMISES_SORTS, sort or PREMISES_DEFAULT_SORT, direction)


def premises_external_ref_taken(external_ref: Any, *, except_id: Any = None) -> bool:
    """Is this outside reference already on a premises in this tenant?

    ⚠ **A READ THAT EXISTS SO A COLLISION IS A SENTENCE AND NOT A `500`
    (`DEF-INT-4273`).** `premises` carries `uq_premises_tenant_external_ref_ci`
    — one outside reference per tenant, case-insensitively — and the City
    address lookup writes the parcel key into that column. Picking the same
    candidate twice is an ordinary thing for a clerk to do, and without this it
    reached them as a database error.

    Case-insensitive to MATCH the index; a check that is stricter than the
    constraint it stands in front of would pass and then fail at the write,
    which is the same defect wearing a check.

    ⚠ **`except_id` IS WHAT LETS AN EDIT USE THIS AT ALL (`DEF-MET-4757`).**
    Without it the check is only usable on CREATE, because a PATCH that resends
    the row's own parcel would find the row itself and refuse a property for
    colliding with itself. That is exactly why the guard in `_validate_premises`
    was gated to create-only, and why the identical `500` this read exists to
    remove survived on the edit form for anyone who typed a parcel another
    property already had.

    **Pass the row being edited.** Omit it and the answer is *"does ANY row hold
    this"*, which is the create question.
    """
    ref = str(external_ref or "").strip()
    if not ref:
        return False
    rows = models.Premises.objects.filter(tenant_id=_tenant_id(), external_ref__iexact=ref)
    if except_id is not None:
        rows = rows.exclude(pk=except_id)
    return rows.only("id").exists()


def premises_gis_parcel_taken(parcel: Any, *, except_id: Any = None) -> bool:
    """Is the CITY's parcel key already on a premises in this tenant?

    ── 2026-09-17 · `BR-MET-1173` ──────────────────────────────────────────────
    ⚠ **THIS IS A DIFFERENT QUESTION FROM `premises_external_ref_taken` ABOVE,
    AND UNTIL TODAY ONE READ ANSWERED BOTH — WRONGLY.** `CR-069` wave M wrote
    the City's parcel into `external_ref` and checked it with that selector.
    But `external_ref` is `BR-MET-403`'s **import match key** — a migrating
    utility's own id, under `uq_premises_tenant_external_ref_ci` — so on any
    tenant that migrated, the two facts were sharing one column and one unique
    index, and the first GIS run would have refused every migrated row.

    ⚠ **AND THE ANSWER HERE IS ADVICE, NOT A CONSTRAINT.** `gis_parcel_id`
    carries **no unique index**, deliberately: *two premises on one parcel* is a
    real thing a City does — a duplex split into two properties on one lot — and
    `BR-INT-073` classifies it as a difference a PERSON judges.

    So the two callers use this differently, and that split is the rule:
      * **a clerk picking a candidate on the create form** is refused, because
        creating a second property on a parcel that already has one is almost
        always the accident it looks like, and a sentence beats a duplicate;
      * **a reconciliation run** never refuses on it. It QUEUES the pair with
        both premises named and stores nothing (ruling 7, 2026-09-17).

    Case-insensitive, matching how `BR-INT-073` compares keys. `except_id` is
    `premises_external_ref_taken`'s own lesson (`DEF-MET-4757`): without it an
    EDIT that resends the row's own parcel finds the row itself and refuses a
    property for colliding with itself.
    """
    key = str(parcel or "").strip()
    if not key:
        return False
    rows = models.Premises.objects.filter(tenant_id=_tenant_id(), gis_parcel_id__iexact=key)
    if except_id is not None:
        rows = rows.exclude(pk=except_id)
    return rows.only("id").exists()


#: The two columns a person types a parcel number into, and nothing else.
#: `external_ref` is the Parcel box on Edit premise and New Connection (under a
#: unique index); `gis_parcel_id` is the Parcel box on Add premises (no index,
#: `BR-MET-1173`). One lookup answers both, so one sentence names the property.
PARCEL_COLUMNS = ("external_ref", "gis_parcel_id")


def premises_holding_parcel(
    value: Any, *, column: str = "external_ref", except_id: Any = None
) -> str | None:
    """WHERE is the property that already holds this parcel number? Its address.

    ── `DEF-MET-9847` · 2026-10-07 (PO GIS review, gap 6) ─────────────────────
    ⚠ **A REFUSAL THAT DOES NOT NAME THE OTHER PROPERTY CANNOT BE ACTED ON.**
    *"That Parcel ID is already used."* leaves the clerk to search the whole
    register to learn whether they mistyped a digit or found a real duplicate.
    This returns the other property's address, so the sentence can say
    *"This parcel already belongs to 12 Deed Row, Katy."*

    ⚠ **THE ADDRESS IS READ OFF `premises`, ITS ONE HOME (hard rule 8)**, never
    composed from a second copy — the walk is one step because a premises IS
    the address. Tenant-scoped like every read here (hard rule 1): the unique
    index is per tenant, so another utility's property can never be the answer
    and its address can never be shown. Case-insensitive, as the index is.
    `None` when nothing else holds it.
    """
    if column not in PARCEL_COLUMNS:
        raise ValueError(f"{column!r} is not a parcel column; it is one of {PARCEL_COLUMNS}")
    key = str(value or "").strip()
    if not key:
        return None
    rows = models.Premises.objects.filter(
        tenant_id=_tenant_id(), **{f"{column}__iexact": key}
    )
    if except_id is not None:
        rows = rows.exclude(pk=except_id)
    other = rows.order_by("created_at").only("address_line", "city").first()
    if other is None:
        return None
    return ", ".join(part for part in (other.address_line, other.city) if (part or "").strip())


def premises_rollup() -> dict[str, int]:
    """S14 header: "N premises · N units · N vacant · N pending activation".

    ⚠ **`vacant` COST ONE ACCOUNT QUERY PER UNIT IN THE TENANT UNTIL
    `DEF-MET-5761`.** It was `sum(1 for unit in units if occupancy_of(unit) ==
    "vacant")`, and `occupancy_of` asks `seams.active_account_for_unit` — one
    account read (and a contact read behind it) for EVERY unit, on the header of
    a screen a utility opens all day. At the 1,109 units of the demo utility
    that is already the dominant cost of `GET /premises`; at the top of T5 it is
    tens of thousands of round trips per keystroke on the search box.

    ⚠ **WHAT IT COUNTS HAS NOT MOVED, AND THAT IS THE POINT.**
    `seams.accounts_for_units` is `active_account_for_unit` asked about a LIST,
    and `apps.customers.selectors` says so in its own docstring: *"The occupancy
    boundary is unchanged … the same `occupying_accounts_for_unit` reading
    (BR-CUS-055 — key off the behaviour CLASS, never the label), and the same
    first-by-`created_at` tie-break, so a unit answers identically whichever
    call site asks."* Both filter `tenant_id`, `unit_id` and
    `status__behavior_class__in=OCCUPYING_BEHAVIOR_CLASSES` and nothing else, so
    a unit is in the returned map exactly when `occupancy_of` would have said
    *occupied* — and `vacant` is therefore the same integer, computed by
    subtraction instead of by 40,000 questions. An EMPTY map while customers
    publishes nothing still means every unit is vacant, which is true by
    construction rather than assumed (the seam's own note).

    ⚠ **THE REMAINING `O(tenant)` PASS IS STATED RATHER THAN HIDDEN
    (hard-won law 1).** The unit ids are still read in full — one `SELECT id`,
    then one `IN (…)` — because the published seam takes a list. That is four
    queries where there were `1 + 2N`, and the durable removal is a COUNTING
    seam owned by `apps/customers` (*"how many of these units are occupied"*),
    which is that module's to publish and not metering's to reach around. The
    figures are in the decision log for 2026-09-18.
    """
    tenant_id = _tenant_id()
    units = models.Unit.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True)
    unit_ids = list(units.values_list("id", flat=True))
    occupied = seams.accounts_for_units(unit_ids) if unit_ids else {}
    vacant = len(unit_ids) - len(occupied)
    return {
        "premises": models.Premises.objects.filter(tenant_id=tenant_id).count(),
        "units": len(unit_ids),
        # BR-MET-101: the header line reads "N + M common" when M > 0. `units`
        # stays the TOTAL; `common` is the M, and the screen subtracts.
        "common": units.filter(is_common_area=True).count(),
        "vacant": vacant,
        "pending_activation": models.Premises.objects.filter(
            tenant_id=tenant_id, status="pending"
        ).count(),
    }


def premises_row(premises_id: Any) -> models.Premises:
    if not _is_uuid(premises_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    row = (
        models.Premises.objects.filter(tenant_id=_tenant_id(), pk=premises_id)
        .select_related("premises_type")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


# ── CR-089 wave E · what a building LENDS to the units added to it ──────────
def premises_lends_dict(row: models.Premises) -> dict[str, Any]:
    """**`E3`/`PUJ-23` — the building, as the add-units wizard has to state it.**

    ⚠ **THE JOURNEY THIS EXISTS FOR.** Adding units used to start on a four-way
    *"How many?"* chooser whose first required box was an EMPTY *Premise*
    picker — so a clerk standing on `P-00043` who pressed **+ New unit** was
    asked to find `P-00043` again, from 79 addresses, by number. The wizard now
    starts by naming the building, and this is what it can say about the one
    that was named.

    Everything here is a READ of something the building already holds. Nothing
    is invented and nothing is written: the wizard shows it, the clerk confirms
    it, and the create is what changes anything.

    Four groups, and each answers a question a clerk actually asks before
    typing *how many*:

      * **which building is this** — its number, its address, its type and its
        status, so a wrong pick is visible before three units land on it;
      * **what is here already** — how many units, and what the last few are
        CALLED, because *"1 unit today, numbered 1"* is what tells you the next
        one should be `2` and not `Apt 101`;
      * **what it lends** — the services the address offers (`BR-MET-119`: a
        unit inherits this list BY DEFAULT — amended 2026-09-25 — and has none
        of its own) and the routes and
        cycles its units sit on (`BR-MET-083(b)`: a unit added to a routed
        building JOINS those routes, so this is a consequence of pressing
        Create, not decoration);
      * **who owns it** — served as the premises' own dict already serves it,
        matched party and free text both, neither substituting for the other.

    ⚠ **THE ROUTE LIST IS `services._routes_a_premises_is_on`, NOT A SECOND
    READING.** That function is what the create actually cascades through, and
    it reads BOTH directions (sibling units' memberships, and the routes drawn
    for the area). A screen-only re-derivation would be a second definition of
    *which routes does this building sit on* and would start disagreeing with
    the create the first time either changed — hard-won law 1.
    """
    from apps.metering import services as metering_services

    unit_qs = models.Unit.objects.filter(
        tenant_id=row.tenant_id, premises=row, deleted_at__isnull=True
    ).order_by("unit_no", "id")
    labels = [unit.label for unit in unit_qs[:UNITS_TODAY_LABELS_SHOWN] if unit.label]
    routes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for route in metering_services._routes_a_premises_is_on(row):
        if str(route.id) in seen:
            continue
        seen.add(str(route.id))
        routes.append(
            {
                "code": route.code,
                "name": route.name,
                "service": _service_code(route.service_id) if route.service_id else None,
                "cycle_code": route.cycle.code if route.cycle_id else None,
                "cycle_name": route.cycle.name if route.cycle_id else None,
                # `null` is *nobody set a start day*, which is a real state on
                # this table and is NOT day 1 (DEF-762's shape).
                "cycle_start_day": route.cycle.start_day if route.cycle_id else None,
            }
        )
    # ── `CR-176-BRC10` · THE OWNER IS THE MASTER ACCOUNT, AND IT IS NAMED ──
    # `DEF-MET-10035`: the building card printed a bare *"Not recorded"* with no
    # label, because this read asked for no account (`with_owner_account=False`)
    # and the card fell back on the legacy owner string. The account's NUMBER
    # and NAME now ride the one batched read the premises LIST already uses
    # (`seams.master_account_numbers`, two statements, no ledger derivation),
    # so the card can say *Owner · <name>* — or `—` where no account is named.
    account_id, _source = premises_master_account_from_row(row)
    numbers = seams.master_account_numbers([account_id]) if account_id is not None else {}
    return {
        "premises": premises_detail_dict(
            row, with_owner_account=False, master_account_numbers=numbers
        ),
        "units_today": unit_qs.count(),
        "unit_labels": labels,
        "unit_labels_truncated": unit_qs.count() > len(labels),
        "routes": routes,
    }


def submeter_reconciliation_row_dict(row: Any) -> dict[str, Any]:
    """One stored master-vs-subs reconciliation, as the report renders it.

    Quantities are served as STRINGS at full stored scale, with the unit beside
    them (hard rule 3) — the screen rounds to 2dp for display (hard rule 2) and
    the wire never loses precision on the way. `null` is an ABSENCE and is drawn
    as one: a `not_evaluated` row has no gap, which is a different fact from a
    gap of zero.
    """
    return {
        "id": str(row.id),
        "period_month": row.period_month.isoformat(),
        "channel": row.channel,
        "master_asset_id": str(row.master_asset_id),
        "master_asset_no": getattr(row.master_asset, "asset_no", None),
        "service_code": getattr(getattr(row, "service", None), "code", None),
        "unit": row.unit,
        "master_consumption": _decimal_str(row.master_consumption),
        "submeter_sum": _decimal_str(row.submeter_sum),
        "gap_quantity": _decimal_str(row.gap_quantity),
        "gap_pct": _decimal_str(row.gap_pct),
        "tolerance_pct": _decimal_str(row.tolerance_pct),
        # ⚠ THE 2dp DISPLAY STRINGS ARE THE SERVER'S, NOT THE SCREEN'S — hard
        # rule 2 ("percentages … DISPLAY 2") and the RateScheduleWizard's
        # `*_pct_display` precedent. One rounding, on one side of the wire; the
        # full-scale value travels beside it for anyone who needs it. A screen
        # that rounded for itself is how two surfaces come to disagree about the
        # same percentage.
        "gap_pct_display": _pct_display(row.gap_pct),
        "tolerance_pct_display": _pct_display(row.tolerance_pct),
        "within_tolerance": row.within_tolerance,
        "status": row.status,
        "reason": row.reason,
        "submeter_count": row.submeter_count,
        "submeters_resolved": row.submeters_resolved,
        "unresolved_submeters": row.unresolved_submeters or [],
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }


def _decimal_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _pct_display(value: Any) -> str | None:
    """A percentage at its DISPLAY precision — 2 decimals plus the sign
    (CLAUDE.md hard rule 2, PO re-sign 2026-08-22). 3.709677…% → `3.71%`."""
    if value is None:
        return None
    return f"{Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"


def premises_submeter_reconciliation(
    premises_id: Any, *, period_month: Any = None
) -> dict[str, Any]:
    """**BR-MET-125's report half** — master vs Σ subs for one premises.

    PO verbatim, 2026-08-26: *"Open 9 - (a) store + report — keeps the door
    open"*. This is the *report*; `submeter_reconciliation.store_reconciliation`
    is the *store*.

    **It READS the stored rows and computes nothing.** That is deliberate and it
    is the point of storing them: a figure recomputed at render time would
    silently restate a closed month the moment a late read landed, and the
    number a person quoted last week would change under them. The stored row
    carries the tolerance it was judged against for the same reason.

    `period_month` narrows to one month; without it every stored period answers,
    newest first. `periods` lists the months that HAVE a stored row, so a period
    picker offers only real ones rather than an invented calendar.

    An EMPTY result is not the same as "this building reconciles". A premises
    with no masters has nothing to reconcile and `has_masters` says so — the
    screen draws that sentence instead of a table of zero gaps.
    """
    premises = premises_row(premises_id)
    rows = (
        models.PremisesSubmeterReconciliation.objects.filter(
            tenant_id=premises.tenant_id, premises_id=premises.id
        )
        .select_related("master_asset", "service")
        .order_by("-period_month", "master_asset__asset_no", "channel")
    )
    periods = sorted(
        {row.period_month.isoformat() for row in rows},
        reverse=True,
    )
    if period_month is not None:
        rows = rows.filter(period_month=period_month)
    return {
        "premises_id": str(premises.id),
        "periods": periods,
        "period_month": period_month.isoformat() if period_month is not None else None,
        "rows": [submeter_reconciliation_row_dict(row) for row in rows],
        # Whether this premises has any MASTER at all — the honest empty state.
        # Asked of the asset structure, not of the stored rows, so a building
        # whose first period has not been read yet still says "nothing stored
        # yet" rather than "no sub-metering here".
        "has_masters": _premises_has_masters(premises),
    }


def _premises_has_masters(premises: Any) -> bool:
    """Does any meter on this premises have sub-meters hanging off it?

    BR-AST-003 structure again — a master is a meter with children, and nothing
    is asked to declare itself one.
    """
    asset_ids = [
        asset_id
        for unit_id in models.Unit.objects.filter(
            tenant_id=premises.tenant_id, premises_id=premises.id
        ).values_list("id", flat=True)
        for point_id in models.ServicePoint.objects.filter(
            tenant_id=premises.tenant_id, unit_id=unit_id, deleted_at__isnull=True
        ).values_list("id", flat=True)
        for asset_id in seams.asset_ids_for_service_point(point_id)
    ]
    return any(seams.submeters_of(asset_id) for asset_id in asset_ids)


def premises_detail(premises_id: Any) -> dict[str, Any]:
    """BR-MET-045: the detail payload behind the Units/Assets/Accounts/Audit
    tabs (the Audit tab reads audit_log through the audit module, S61).

    ⚠ **`unit_list_rows` AND NOT `unit_list_dict` (`CR-089` wave C task `C1`,
    `PUJ-12`).** The Units tab listed a building's flats with **no money on it
    at all**, so *which of my flats owes something* — the question a landlord
    rings about — could not be answered from the tab that lists them.

    ⚠ **THE MONEY IS WAVE E's SEAM, DELIBERATELY, AND THIS LANE DELETED ITS OWN
    SECOND ANSWER TO USE IT.** This wave first wrote a per-unit `unit_owed()`
    over `money_block_state`; wave `E1` landed `unit_list_rows` +
    `seams.owed_for_units` the same day, which asks the ledger **once for the
    whole page** and forwards `customers._balance_cells`' own output — the same
    derivation the accounts list, the S21 header and the unit's Account tab all
    show. `DEF-127`'s whole lesson is that a money figure with two computations
    agrees on the day it is written and disagrees the first time a posting is
    reversed, so the second answer was removed rather than kept beside it.
    """
    row = premises_row(premises_id)
    units = list(
        models.Unit.objects.filter(tenant_id=row.tenant_id, premises=row).order_by(
            "unit_no", "label", "id"
        )
    )
    # ⚠ **ONE LEDGER READ FOR THE WHOLE PAGE, AND THE TILE RIDES IT**
    # (`DEF-MET-4733`). It is resolved HERE rather than inside `unit_list_rows`
    # so the Units tab's column and the *Owed here* tile are the same answer,
    # asked once. See `_owed_here_tile` for what it will and will not claim.
    owed = seams.owed_for_units([unit.id for unit in units])
    return {
        **premises_detail_dict(row),
        "unit_rows": _with_custom_answers(unit_list_rows(units, owed=owed), units),
        # CR-089 wave B `B6` — see `premises_routes` for why this is on the
        # DETAIL and never on `premises_detail_dict`.
        "routes": premises_routes(row),
        # ── CR-089 `F3` · the property's four tiles (`DEF-MET-4733`) ────────
        # `Units` is already on the payload (`units` + `units_common`); the
        # ASSETS half is counted from rows the page has ALREADY fetched for its
        # Assets tab, on the client, so it is deliberately not served here — a
        # third asset read for a number the browser is holding would be the
        # `DEF-324` N+1 this file spends four paragraphs avoiding.
        "owed_here": _owed_here_tile(units, owed),
        "open_work": _open_work_at_premises(row.id),
    }


def _owed_here_tile(
    units: list[models.Unit], owed: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """`CR-089` `F3` tile 3 — **what is owed AT THIS ADDRESS, and over how many
    accounts.**

    The building total of the same `owed_for_units` derivation the Units tab's
    column draws, summed over the map that read already produced. No second
    ledger read and no second arithmetic: `DEF-127`.

    ⚠ **THIS TILE WILL NOT MANUFACTURE A ZERO, AND THAT IS THE WHOLE OF WAVE
    C's RULING CARRIED UP A LEVEL (`DEF-138`).** `owed_for_units` resolves the
    **occupying** account, so:

      * a VACANT unit is absent from the map — it is not measured at all;
      * a unit whose tenant left still owing has a CLOSED account the map
        excludes, so its debt is real and unseen;
      * a unit whose books could not be read carries `balance_unavailable`.

    A total that silently skipped all three and printed `$0.00` would say
    *nothing is owed here* over a real debt — the exact substitution wave C
    refused on the row, and worse on a total because a total looks complete.
    So the tile serves what it summed and what it could NOT:

      `amount`      the sum of the balances actually read, as a decimal STRING
                    at stored scale (hard rule 2 — never a float, rounded for
                    display only);
      `accounts`    how many accounts that sum covers — the design's
                    *"across 3 accounts"*, and the number that makes the sum
                    readable rather than authoritative;
      `not_counted` how many units were NOT measured, and
      `unreadable`  how many of those were unreadable rather than vacant.

    The screen states the second pair beside the first. `accounts` of 0 with
    `not_counted` of 4 is *nothing here has been billed to anybody*, which is a
    different sentence from `$0.00`.
    """
    total = Decimal("0")
    currencies: set[str] = set()
    accounts: set[str] = set()
    unreadable = 0
    counted = 0
    for unit in units:
        cell = owed.get(str(unit.id))
        if cell is None:
            continue  # no occupying account — VACANT, and not a zero
        if cell.get("balance_unavailable") or cell.get("balance") is None:
            unreadable += 1
            continue
        total += Decimal(str(cell["balance"]))
        counted += 1
        if cell.get("balance_currency"):
            currencies.add(str(cell["balance_currency"]))
        if cell.get("account_id"):
            accounts.add(str(cell["account_id"]))
    # ⚠ **TWO CURRENCIES CANNOT BE ADDED AND ARE NOT ADDED.** `accounts
    # .currency` is per ACCOUNT (`CHAR(3)`, hard rule 2), so a building whose
    # accounts disagree has no single total — and a figure printed under one
    # symbol over amounts in two would be a wrong number, not a rounded one.
    # The tile then draws no amount and says how many accounts it found.
    mixed = len(currencies) > 1
    return {
        # STORAGE scale, as a string, exactly as `_balance_cells` serves each
        # part (hard rule 2 — never a float; rounding is display's business).
        "amount": (
            None
            if (mixed or counted == 0)
            else str(total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
        ),
        "currency": None if mixed else next(iter(currencies), None),
        "mixed_currency": mixed,
        "accounts": len(accounts),
        "counted": counted,
        "not_counted": len(units) - counted,
        "unreadable": unreadable,
    }


def _open_work_at_premises(premises_id: Any) -> dict[str, Any]:
    """`CR-089` `F3` tile 4 — **how many jobs are still running at this
    address**, and what the next one is.

    ⚠ **THE TILE AND THE WORK-ORDERS TAB COUNT THE SAME ROWS, WHICH IS THE ONE
    THING THE UNIT'S TILE COULD NOT DO.** `work.selectors
    .open_work_order_count_at_premises` narrows the SAME
    `metering_seam.orders_at_premises_queryset` the tab pages through
    (`BR-WRK-006`'s five anchors, every one of them a WALK to the premises per
    `BR-MET-1161`) to `metering_seam.OPEN_WORK_ORDER_STATES`. Wave F recorded
    that a tile reading 3 over a list showing 2 is worse than a narrow tile;
    here the two are one queryset, so the question does not arise.

    ⚠ **`None` IS *WORK COULD NOT BE ASKED* AND IS NEVER `0`** (`DEF-075`).
    Metering asks by name and does not count: the word **open** belongs to
    work (`CLAUDE.md`'s module map, `G78`).
    """
    return seams.open_work_at_premises(premises_id)


def premises_routes(row: models.Premises) -> list[dict[str, Any]]:
    """**CR-089 wave B `B6` — the route and cycle a property is on.**

    PO 2026-09-08, verbatim: *"In header we are not shouding Route and Cycle
    information - if it is assign or if it nor assign both the thing and you
    should add that at the time of creation also - it should be optional"*.
    Two halves: this is the READ, and `_join_premises_to_route` is the write.

    ⚠ **IT IS ON `premises_detail` AND DELIBERATELY NOT ON
    `premises_detail_dict`, WHICH IS WHAT RENDERS A LIST ROW.** Answering it
    costs a membership read per property, and S14 asks for 200 at a time — the
    exact N+1 `DEF-324` measured at *47 of 118 profiled seconds answering one
    question 304 times*, and the same reason `with_owner_account=False` exists
    two functions up. A property's route belongs on the property's own page.

    ⚠ **ROUTE MEMBERSHIP IS PER UNIT AND THIS ANSWERS PER PROPERTY**, which is
    not a mismatch but the honest shape: `BR-MET-083` joins every unit of a
    building to the same area routes, and a reader walks to an ADDRESS
    (`RoutePremisesOrder`'s own docstring: *"one stop, many meters"*). Where a
    building's units genuinely sit on different routes, every one of them is
    listed rather than one being picked — a header that showed *Route 12* for a
    building half of which is on Route 14 would be worse than showing neither.

    ⚠ **A DRAFT ROUTE OR A DRAFT CYCLE IS NOT AN ANSWER.** `_routes_a_premises
    _is_on` already drops non-active routes (BR-MET-076 boundary 1), and the
    cycle is reported only when the cycle itself is not a draft — the same test
    `_stamp_service_points` makes, for `DEF-219`'s reason: *"a draft is a thing
    that has not happened yet and must not have consequences a person can
    see"*. A route with a draft cycle reads as *on a route, no cycle yet*, which
    is true.
    """
    from apps.metering import services as metering_services

    out: list[dict[str, Any]] = []
    for route in metering_services._routes_a_premises_is_on(row):
        cycle = route.cycle if route.cycle_id and route.cycle.status != "draft" else None
        out.append(
            {
                "id": str(route.id),
                "code": route.code,
                "name": route.name,
                # B14 rule 31 — the CODE a person quotes, never the row id.
                "cycle_code": cycle.code if cycle else None,
                "cycle_name": cycle.name if cycle else None,
                # ── CR-089 `F3` header line · `DEF-MET-4733` ────────────────
                # ⚠ **THE BILLING DAY IS A REAL COLUMN AND IT IS READ, NOT
                # COMPUTED.** `CR-089`'s drawing writes *"bills on the 12th"*,
                # and wave `B6` recorded that this payload served no due day —
                # true of the PAYLOAD, and the column has existed all along.
                # `cycles.bill_day` is a DAY-OF-MONTH DEFAULT kept by the PO's
                # own ruling of 2026-08-23 (`D9`, verbatim: *"when we configure
                # Cycle we are provideing default values; mostly it wil remain
                # as it is but user can over ride them during billing"*), and
                # `OQ-344` made it what a run with no typed bill date resolves
                # through. So the screen may say what this cycle NORMALLY does
                # and must not say what a particular bill WILL do — the run
                # overrides it and the override does not rewrite it.
                # `None` where the utility has not set one, and the screen then
                # states the absence instead of naming a day.
                "cycle_bill_day": cycle.bill_day if cycle else None,
                # ⚠ **THE EFFECTIVE START DAY, NEVER THE STORED ONE (`OQ-340`).**
                # The period engine anchors on the first run and does NOT read
                # `cycles.start_day`, so a stored day the engine ignores is a
                # field that lies to the operator — five surfaces printed it
                # before `OQ-340` closed. `effective_start_day` is what the
                # cycle actually does, and `None` for the frequencies that have
                # no day-of-month anchor at all (Daily, Weekly, Fortnightly).
                "cycle_read_day": (
                    period_engine.effective_start_day(
                        frequency=cycle.frequency,
                        start_day=cycle.start_day,
                        first_run=cycle.first_run_date,
                    )["effective_start_day"]
                    if cycle
                    else None
                ),
            }
        )
    return out


# ── CR-089 wave D · taking a place out of service (BR-MET-1164) ─────────────
# PO 2026-09-08, verbatim: *"Allow user to cahnge Unit and Premsies status"* and
# *"if you ahve units - active, assets or active accounts, you cannot shut down
# building pr premises."*
#
# ⚠ **THE COUNTS ARE READ WHEN THE DIALOG OPENS AND ARE NEVER REMEMBERED.**
# BR-MET-1164 refuses on live dependencies, so a screen drawing a cached count
# would offer a commit the server then refuses — and a clerk who closed the last
# account thirty seconds ago would still be told to close it.
#
# ⚠ **A COUNT WITH NOWHERE TO GO IS A WALL** (CR-089 §6 D1: *"each of them a
# link to the list that clears it"*), so every row names the list it is cleared
# from as a ROUTE NAME and its parameters rather than a URL — the SPA owns its
# own paths (`/:tenant/…`) and a server-built link would be a second copy of the
# route table that nothing keeps in step.
#
# ⚠ **FOUR TERMS, FROM TWO RULES, AND THE FOURTH IS NOT CR-089's.** BR-MET-1164
# names three (active units · attached assets · open accounts). BR-MET-047 —
# signed earlier and NOT superseded by it — refuses a unit that still owes
# money, which is a different fact from an open account: an account can be
# CLOSED with a balance behind it. Both rules are enforced, and the money row is
# drawn only when it has something to say, because the PO was shown three.
PREMISES_STATUS_DEPENDENCY_KINDS = (
    "open_accounts",
    "unpaid_balances",
    "attached_assets",
    "active_units",
)
UNIT_STATUS_DEPENDENCY_KINDS = ("open_accounts", "unpaid_balances", "attached_assets")


def money_block_state(unit: models.Unit) -> dict[str, Any] | None:
    """BR-MET-047's money term for ONE unit — `None` when the books are clear.

    ⛔ DEF-138's posture, moved here from `services._unit_deactivation_blockers`
    rather than re-decided: a book that CANNOT BE ASKED blocks, because a guard
    that cannot check must not pass. ⛔ DEF-099's too: the figure travels with its
    `CHAR(3)`, so a refusal about money can never state a bare number.
    """
    state = seams.unpaid_balance_state(unit.id)
    if state is None:
        return {"state": "unpaid_balance"} if seams.unpaid_balance_exists(unit.id) else None
    if state.get("state") == "clear":
        return None
    out: dict[str, Any] = {"state": state["state"]}
    if state.get("amount") is not None:
        out["amount"] = state["amount"]
        out["currency"] = state.get("currency")
    if state.get("unavailable"):
        out["unavailable"] = list(state["unavailable"])
    return out


def _dependency(kind: str, count: int, *, blocking: bool, link: dict[str, Any]) -> dict[str, Any]:
    return {"kind": kind, "count": int(count), "blocking": blocking, "link": link}


def premises_status_dependencies(row: models.Premises) -> list[dict[str, Any]]:
    """BR-MET-1164 + BR-MET-047 for a PREMISES, counted from live data.

    Every row is served whether or not its count is zero, and `blocking` is the
    RULE's verdict rather than a function of the count — so the screen can say
    *"no open accounts"* instead of leaving a reader to wonder whether anybody
    looked (the DEF-127 posture: an absence must not be spelled like a zero).
    """
    units = list(models.Unit.objects.filter(tenant_id=row.tenant_id, premises=row))
    unit_ids = [str(unit.id) for unit in units]
    # An asset attached to an ALREADY deactivated unit is still attached, so the
    # asset and money counts run over every unit of the building rather than the
    # live ones — the rule's own word is *"still attached"*.
    asset_counts = seams.asset_counts_for_units(unit_ids)
    accounts = seams.accounts_for_units(unit_ids)
    units_link = {"route": "premises_units", "premises_id": str(row.id)}
    return [
        _dependency(
            "open_accounts",
            len([1 for value in accounts.values() if value]),
            blocking=True,
            link=units_link,
        ),
        _dependency(
            "unpaid_balances",
            len([1 for unit in units if money_block_state(unit) is not None]),
            blocking=True,
            link=units_link,
        ),
        _dependency(
            "attached_assets",
            sum(int(value) for value in asset_counts.values()),
            blocking=True,
            link={"route": "premises_assets", "premises_id": str(row.id)},
        ),
        _dependency(
            "active_units",
            len([1 for unit in units if unit.deleted_at is None]),
            blocking=True,
            link=units_link,
        ),
    ]


def unit_status_dependencies(unit: models.Unit) -> list[dict[str, Any]]:
    """BR-MET-1164 one level down — *"a unit cannot be deactivated while an
    account on it is open"* — plus BR-MET-047's money term.

    ⚠ **THE ATTACHED ASSETS ARE COUNTED AND DO NOT BLOCK, AND THAT IS THE RULE
    RATHER THAN AN OVERSIGHT.** BR-MET-1164 names ONE term for a unit. Making a
    meter block would refuse nearly every unit this product has, and the control
    exists precisely to retire a flat that has been knocked through — which has
    a meter on it. The count is served because the clerk is about to strand it,
    which is CR-089's *"what happens to the meters"* consequence, and it links to
    the tab that clears it.
    """
    account = seams.active_account_for_unit(unit.id)
    account_link = {"route": "unit_account", "unit_id": str(unit.id)}
    money = money_block_state(unit)
    money_row = _dependency(
        "unpaid_balances", 1 if money is not None else 0, blocking=True, link=account_link
    )
    if money is not None:
        # DEF-099 — the amount and its CHAR(3) travel together or neither does.
        money_row["detail"] = money
    accounts_row = _dependency(
        "open_accounts",
        1 if account is not None else 0,
        blocking=True,
        link=account_link,
    )
    # ── `DEF-MET-4763` — the U12 frame NAMES the account, it does not count it ──
    #
    # The drawn refusal row reads *Account <number> is still open*, not *1 open
    # account*. A unit is blocked by AT MOST ONE account (`BR-MET-036` — one
    # active account per unit is what occupancy is derived from), so the number
    # is knowable here and the count alone was throwing it away: a clerk with
    # two flats open in two tabs could not tell which account the refusal meant.
    #
    # ⚠ **IT IS `reference` AND NOT `detail`, DELIBERATELY.** `detail` is
    # `DEF-099`'s money shape — `state`/`amount`/`currency` — and posting an
    # account number into it would make one field answer two questions, which is
    # `DEF-755`'s mechanism exactly. A premises row never carries this: a
    # building blocked by three accounts has no single number to name, and the
    # `P11` frame counts them for the same reason.
    if account is not None and account.get("account_no"):
        accounts_row["reference"] = str(account["account_no"])
    return [
        accounts_row,
        money_row,
        _dependency(
            "attached_assets",
            len(seams.assets_on_unit(unit.id)),
            blocking=False,
            link={"route": "unit_assets", "unit_id": str(unit.id)},
        ),
    ]


def status_change_dict(
    *,
    entity: str,
    entity_id: str,
    status: str,
    dependencies: list[dict[str, Any]],
) -> dict[str, Any]:
    """The ONE shape both previews answer with, and the one both refusals carry.

    `held_by` is the FIRST blocking row with a count — what to do NEXT, not a
    list of everything that is wrong. B14 rule 33 caps a refusal at five or six
    words, and *"close the accounts, then clear the balances, then remove the
    assets, then deactivate the units"* is not a refusal; it is a plan nobody can
    act on in one press. The order the rows are declared in IS the order the work
    is done in, which is why this reads the list rather than sorting it.
    """
    target = "active" if status == "inactive" else "inactive"
    held_by = None
    if target == "inactive":
        for row in dependencies:
            if row["blocking"] and row["count"] > 0:
                held_by = row["kind"]
                break
    return {
        "entity": entity,
        "id": entity_id,
        "status": status,
        # What the press would DO. A reactivation asks the same two questions (a
        # date and a reason) and is blocked by nothing — CR-089 §8 names it as
        # the one half of this wave a rollback must keep, because reverting the
        # wave without it leaves anything already deactivated with no screen that
        # can bring it back.
        "target_status": target,
        "dependencies": dependencies,
        "blocked": held_by is not None,
        "held_by": held_by,
    }


def premises_status_change(premises_id: Any) -> dict[str, Any]:
    """`GET /premises/{id}/status-change` — what the dialog draws before it asks."""
    row = premises_row(premises_id)
    return status_change_dict(
        entity="premises",
        entity_id=str(row.id),
        status=row.status,
        dependencies=premises_status_dependencies(row),
    )


def unit_status_change(unit_id: Any) -> dict[str, Any]:
    """`GET /units/{id}/status-change` — the same, one level down.

    A unit has no stored status column (US-MET-002 §5), so the status here is the
    DERIVED one every other unit surface shows: `deleted_at` set is `inactive`,
    anything else is live.
    """
    unit = unit_row(unit_id)
    return status_change_dict(
        entity="unit",
        entity_id=str(unit.id),
        status="inactive" if unit.deleted_at is not None else "active",
        dependencies=unit_status_dependencies(unit),
    )


# ── units (S15) ─────────────────────────────────────────────────────────────
def occupancy_of(unit: models.Unit) -> str:
    """BR-MET-036: DERIVED — an active account ⇒ occupied, none ⇒ vacant.
    There is no stored occupancy column and no way to set one."""
    return "occupied" if seams.active_account_for_unit(unit.id) is not None else "vacant"


#: ── CR-089 wave A — ONE STRING SHAPE FOR A COORDINATE, EVERYWHERE ──────────
#:
#: ⚠ **THIS EXISTS BECAUSE A SQL `COALESCE` DOES NOT RETURN THE COLUMN'S
#: SCALE.** `unit_premises_geo_index` picks a unit's point over its building's
#: with `Coalesce("lat", "premises__lat")`, and the value that comes back is a
#: Decimal whose scale is the EXPRESSION's rather than `NUMERIC(9,6)`'s — so
#: `str()` on it produced **`30.7521040000000`** where the same coordinate read
#: straight off the row is `30.752104`. Same place, two spellings, on two
#: screens that a person compares.
#:
#: It is backend-dependent as well, which is the part that makes it a trap: the
#: suite runs on sqlite (law 14) and PostgreSQL types the expression its own
#: way, so a check written against one is not a promise about the other.
#:
#: Every coordinate this module serves goes through here. `None` stays `None` —
#: an absent point is a state, not a zero.
def _coord_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal("0.000001")))


def unit_point(unit: models.Unit) -> dict[str, Any]:
    """`BR-MET-1162` — WHERE THIS UNIT IS, AND WHICH OF THE TWO POINTS IT IS.

    PO ruling 2026-09-08: *"a unit may carry its own point and parcel, and where
    it does, that is the truth for that unit. Where it does not, it uses its
    building's."*

    ⚠ **THE FALLBACK IS THE RULE, NOT AN IMPLEMENTATION DETAIL, AND `source` IS
    WHY THIS IS ONE FUNCTION RATHER THAN A COALESCE AT EACH CALL SITE.** The
    ruling's second half is *"any screen showing a point says which of the two
    it is showing"* — so a caller that merely took whichever value was non-null
    would satisfy the arithmetic and lose the requirement. A cabin reading its
    own point and a flat reading its building's are two different facts and the
    screen has to say which, so the two travel together (hard-won law 1: one
    definition, views derived).

    `source` is one of:
      * `"unit"`     — this unit carries its own point.
      * `"premises"` — it does not, and this is its building's.
      * `"none"`     — neither has one. `lat`/`lng` are `null` and the screen
        says *No point recorded*; nothing is invented, which is the same
        posture `unit_premises_geo_index` has always taken for the map.

    Coordinates as their stored NUMERIC(9,6) STRINGS, never floats — the wire
    carries what the column holds.
    """
    if unit.lat is not None and unit.lng is not None:
        return {"lat": _coord_str(unit.lat), "lng": _coord_str(unit.lng), "source": "unit"}
    premises = unit.premises
    if premises.lat is not None and premises.lng is not None:
        return {
            "lat": _coord_str(premises.lat),
            "lng": _coord_str(premises.lng),
            "source": "premises",
        }
    return {"lat": None, "lng": None, "source": "none"}


def unit_detail_dict(unit: models.Unit) -> dict[str, Any]:
    """⚠ **`services` IS THE PREMISES' LIST, AND THAT IS THE WHOLE OF DEF-755.**

    The rule in force (PO, 2026-08-26, after CR-037 was withdrawn): **a unit's
    services ARE its premises' services.** There is no unit-level column and no
    override, so this reads the premises and nothing else.

    It used to be derived — in `unit_list_dict` — from SERVICE POINTS, and that
    was not wrong when it was written: it answered *what is METERED here*, which
    is true and useful, and the field was simply named `services`. It became
    wrong the moment the ruling landed, and the three consequences were all live
    on 9,881 units:

      · a unit with a service available and NO METER YET showed nothing;
      · a unit whose meter was PULLED lost the service that day;
      · a sub-metered unit could carry the same code twice, once per point.

    The metered set still exists and still matters — it moved to
    `metered_services` on the list row. Two facts, two names; sharing one word
    IS the defect. Every other service-point reader (`derivation.py`'s
    route/cycle logic, the service agreements, `_service_code_by_asset`, the
    billing gather) is about REALISATION and is deliberately untouched.

    ⚠ **AND `None` IS SERVED AS `None`, NOT `[]` (DEF-762, one level down).** A
    premises nobody was ever asked about holds SQL NULL; its units inherit that
    unanswered state. Publishing `[]` would put *this unit offers nothing* into
    a clerk's mouth on every unit of every address nobody has been asked about
    — which is exactly the "No services" on 9,881 rows the PO is looking at.
    """
    return {
        "id": str(unit.id),
        "unit_no": unit.unit_no,
        # `DEF-MET-10164` — the UNIT's own stamp (see `premises_detail_dict`).
        "created_at": unit.created_at.isoformat() if unit.created_at else None,
        # `CR-161-BRC10` W3 · `DEF-MET-9227` — what Edit unit re-opens on.
        "custom_data": dict(unit.custom_data or {}),
        "premises_id": str(unit.premises_id),
        "premise_no": unit.premises.premise_no,
        "premise_address": unit.premises.address_line,
        "label": unit.label,
        "unit_type": unit.unit_type,
        "floor_label": unit.floor_label,
        "square_feet": unit.square_feet,
        # ── CR-089 wave A · `BR-MET-1162` — the unit's OWN point, and the
        # effective one beside it ───────────────────────────────────────────
        # Two things and not one, deliberately. `lat`/`lng` are what THIS ROW
        # holds — `null` on all 1,109 units today, and what the edit form reads
        # back so a clerk can tell *I gave this unit a point* from *it is using
        # the building's*. `point` is the ANSWER, with `source` naming which of
        # the two it came from, because the ruling requires the screen to say.
        # Collapsing them into one field would make *cleared* and *never set*
        # the same payload, and clearing is a real answer (`services.py`).
        "lat": _coord_str(unit.lat),
        "lng": _coord_str(unit.lng),
        "point": unit_point(unit),
        "rate_plan_id": str(unit.rate_plan_id) if unit.rate_plan_id else None,
        "plan_effective_from": (
            unit.plan_effective_from.isoformat() if unit.plan_effective_from else None
        ),
        "plan_locked": unit.plan_locked,
        "vacant_standby_auto": unit.vacant_standby_auto,
        # BR-MET-101: the flag "must be visible everywhere it matters" — it is
        # what separates a common area from a vacant unit billed to the owner
        # (BR-MET-094), so every unit payload carries it.
        "is_common_area": unit.is_common_area,
        # DEF-755 — the premises' list, copied (never the model's own object) so
        # a caller cannot mutate the premises through a unit payload. Served on
        # the DETAIL dict rather than only the list row because
        # `unit_detail_dict` is what the write path audits and what
        # `customers.seams` hands the move-in/move-out flows: a unit's services
        # were invisible to all of them.
        "services": (
            None
            if unit.premises.services_available is None
            else list(unit.premises.services_available)
        ),
        "active": unit.deleted_at is None,
    }


def unit_list_dict(unit: models.Unit, *, owed: dict[str, Any] | None = None) -> dict[str, Any]:
    """One S15 row: `services` from the PREMISES (DEF-755 — see
    `unit_detail_dict`), the METERED set beside it under its own name, meters
    with (sub)/(master) qualifiers from the assets registry, occupant + status
    DERIVED.

    ⚠ **`owed` IS RESOLVED BY THE CALLER FOR THE WHOLE PAGE, EXACTLY AS
    `customers.selectors.account_row`'s keywords are.** It is one ledger read
    per PAGE; a row that resolved its own would be one per ROW, on a list a
    utility opens all day. `None` means the caller did not ask — the row then
    carries `owed: null` and the screen says nothing about money, which is what
    every caller before CR-089 wave E gets, unchanged.
    """
    account = seams.active_account_for_unit(unit.id)
    occupancy = "occupied" if account is not None else "vacant"
    meters = seams.assets_on_unit(unit.id)
    # ⚠ **THIS LINE USED TO BE `services` AND NOW HAS ITS OWN NAME (DEF-755).**
    # It answers a DIFFERENT question — *what is metered here* — and it is worth
    # answering: it is what tells a clerk that a unit with Water available has
    # no water meter on it. De-duplicated because a sub-metered unit can hold
    # more than one point on the same service, and order is preserved (the
    # points' own `created_at` order) rather than sorted, so a screen reading it
    # sees the same sequence the service-point list shows.
    metered: list[str] = []
    for point in service_points_for(unit.id):
        if point["service"] not in metered:
            metered.append(point["service"])
    # ── `missing_services` — PO ruling 2026-09-28, the gap block's second fact
    # ⚠ **IT IS DERIVED HERE AND NOWHERE ELSE.** The retired `GET
    # /units/service-gaps` computed its own `offered`/`held`/`missing` triple
    # beside this row's `services`/`metered_services` pair; two derivations of
    # one fact is `DEF-127`'s shape even when both are correct, and the two
    # doors drifting apart is what the PO closed. `services` is what the
    # ADDRESS offers and `metered` is what this unit HOLDS, so the difference
    # is the answer and the ADDRESS's own order is kept — every other surface
    # prints an offer in that order and a list that re-sorts it reads as a
    # different list.
    #
    # A premises nobody has been asked about holds `None` and is short of
    # NOTHING (`BR-MET-119`): *unrecorded* is not *offered*. That is the same
    # distinction `_short_of_offer` makes in SQL, and the two must agree — a
    # row served under the filter with an empty `missing_services` would be
    # them disagreeing in public.
    offered = unit.premises.services_available or []
    return {
        **unit_detail_dict(unit),
        "metered_services": metered,
        "missing_services": [code for code in offered if code not in metered],
        "meters": [
            {
                "asset_no": m.get("asset_no"),
                "qualifier": m.get("qualifier"),
                "id": m.get("id"),
                # CR-089 wave F `F3` — `BR-AST-004`'s category, forwarded from
                # the assets registry's own row so the unit's Assets tile can
                # split *what is read and bills* from *what we own and do not
                # read* without a second request and without inferring a
                # category from a type code on the client.
                "tab": m.get("tab"),
            }
            for m in meters
        ],
        "occupancy": occupancy,  # BR-MET-036 derived
        "occupant": (account or {}).get("customer_name"),
        "account_no": (account or {}).get("account_no"),
        # Record links (PO 2026-10-19): the occupying account's id, so the
        # Occupant cell can open the account. An address ingredient only —
        # never a visible value (B14 rule 31). Null exactly when vacant.
        "account_id": (account or {}).get("id"),
        "status": _unit_status(unit, account, occupancy),
        "sub_metered": any(m.get("qualifier") == "sub" for m in meters),
        # CR-089 wave E (`E1`/`PUJ-22`) — `null` when the caller did not ask,
        # ABSENT-from-the-map when this unit has no occupying account. The two
        # are different sentences on the screen and neither is `0.00`.
        "owed": owed,
    }


def unit_page_dict(unit: models.Unit) -> dict[str, Any]:
    """`GET /units/{id}` — the S15 row PLUS the three figures the four tiles need.

    ── WHY THE TILES ARE SERVED HERE AND NOT FETCHED SEPARATELY ──────────────
    `CR-089` `F3`, PO 2026-09-08 verbatim: *"Kpis you ahve shown on Unit view -
    these KPis will be displayed across all views"* — **Assets · Owed · Plan ·
    Open work**, on all six tabs of the unit. `CR-089` §5 flags that ruling as
    *"the one ruling in this CR whose cost grows with tenant size"*, so the
    cost was designed rather than discovered:

      * the strip already renders OUTSIDE the tab bodies, so a tab change
        re-renders it and fetches nothing;
      * all three new figures ride the payload the page **already** requests,
        so the tiles cost **no extra HTTP request at all** — not on first load
        and not on any of the five tab changes after it;
      * what they do cost is **three extra queries on this one endpoint**, and
        nothing else in the product pays them. `unit_list_dict` is untouched,
        so the units LIST, the create's response and every internal caller are
        byte-identical to what they were.

    ⚠ **AND THAT IS WHY THIS IS A SEPARATE FUNCTION RATHER THAN THREE LINES
    ADDED TO `unit_list_dict`.** That dict is what `update_unit` and
    `create_unit` write into `audit_log` as `before`/`after`, what
    `customers.seams` hands the move-in and move-out flows, and what
    `unit_list_rows` calls once per row of a 133-row page. Three figures added
    there would put a ledger read and a work-order count into an audit write
    and into every row of a list that does not draw them — `DEF-2723`'s shape,
    where six per-row reads became a 562 ms list nobody had measured.

    ⚠ **EVERY ONE OF THE THREE HAS A NULL THAT IS NOT A ZERO** (`DEF-127`,
    `DEF-138`, `DEF-075`). `owed` is absent-from-the-map for a unit with no
    occupying account and null when the books could not be asked; `open_work`
    is null when work cannot answer. The screen says *vacant*, *could not be
    read* or *not asked* — never `0.00` and never `0`.
    """
    owed = seams.owed_for_units([unit.id])
    row = unit_list_dict(unit, owed=owed.get(str(unit.id)))
    return {**row, "assets": _asset_tile(row["meters"]), "open_work": _open_work_tile(unit)}


def _asset_tile(meters: list[dict[str, Any]]) -> dict[str, Any]:
    """`F3` tile 1 — everything tagged to the unit, split the way `C3` splits it.

    PO ruling 2026-09-08, verbatim: *"Unit → Overview -> Meter = assets"*. The
    tile counted `meters` and was LABELLED *Meters*, and the list it counted
    has always held every asset assigned to the unit — a cart, a fire line and
    a PV panel among them — so the number was already right and the word was
    wrong. `CR-089` §3: *"The tile counts everything tagged to the unit and
    splits it: what is read and bills, and what is ours and is not"*.

    ⚠ **THE SPLIT IS `BR-AST-004`'s CATEGORY, NOT A TYPE-CODE GUESS.** Same
    predicate `PremisesDetailPage.isMeteredAsset` groups the property's Assets
    tab by (`C3`), from the same server field. Inferring it from the type code
    would break the first time a tenant adds a type of their own, which
    `BR-TEN-036` says they may.

    ⚠ **A ROW WHOSE CATEGORY DID NOT ARRIVE IS COUNTED IN THE TOTAL AND IN
    NEITHER HALF.** `total` is what the tile shows; `bills` + `behind` may be
    smaller, and the two halves are the DETAIL line. Forcing an unknown into
    *behind the meter* would say *we own it and never read it* about a meter.
    """
    bills = sum(1 for m in meters if m.get("tab") in ("meters", "sub_meters"))
    behind = sum(1 for m in meters if m.get("tab") == "behind_the_meter")
    return {"total": len(meters), "bills": bills, "behind": behind}


def _open_work_tile(unit: models.Unit) -> dict[str, Any]:
    """`F3` tile 4 — how many jobs are still running on this unit.

    `None` when work cannot answer, which is NOT zero (`DEF-075`): a `0` on
    this tile says *nobody is coming and nobody needs to*, and the screen must
    be able to tell that from *we could not ask*.
    """
    return {"count": seams.open_work_order_count_for_unit(unit.id)}


def unit_list_rows(
    units: list[models.Unit], *, owed: dict[str, dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """A PAGE of S15 rows, with the money resolved once for the page.

    CR-089 wave E (`E1`/`PUJ-22`). The one ledger read lives here rather than in
    `unit_list_dict` so that the single-row readers — `GET /units/{id}`, the
    create's response, every internal caller — keep the shape they had and pay
    nothing for a column they do not draw.

    ⚠ **`owed` IS AN ALREADY-RESOLVED MAP, AND PASSING IT IS HOW THE PROPERTY'S
    *Owed here* TILE COSTS NO SECOND LEDGER READ (`CR-089` `F3`,
    `DEF-MET-4733`).** The property page draws BOTH the Units tab's per-unit
    column and a building total, and those are one question asked once. A
    caller holding `seams.owed_for_units(...)` hands it in; every other caller
    passes nothing and this asks the ledger itself, exactly as before. Two
    derivations of one balance is `DEF-127`'s shape even when both are correct
    — and here it would also be two ledger reads on a screen a utility opens
    all day.
    """
    resolved = seams.owed_for_units([unit.id for unit in units]) if owed is None else owed
    return [unit_list_dict(unit, owed=resolved.get(str(unit.id))) for unit in units]


def _with_custom_answers(
    rows: list[dict[str, Any]], units: list[models.Unit]
) -> list[dict[str, Any]]:
    """`CR-161-BRC10` W3 · `DEF-MET-9227` / `DEF-MET-9173` — the Premise page's
    Units tab shows each unit's own custom answers and each of its service
    points', keyed by service code. ONE service-point read for the whole tab
    (never one per row). Only the property page asks for these, so the S15 list
    and every single-row reader keep the shape they had."""
    by_unit: dict[str, dict[str, Any]] = {}
    points = models.ServicePoint.objects.filter(
        tenant_id__in={unit.tenant_id for unit in units},
        unit_id__in=[unit.id for unit in units],
    ).values_list("unit_id", "service_id", "custom_data")
    for unit_id, service_id, custom in points:
        if custom:
            by_unit.setdefault(str(unit_id), {})[_service_code(service_id)] = dict(custom)
    custom_by_unit = {str(unit.id): dict(unit.custom_data or {}) for unit in units}
    return [
        {
            **row,
            "custom_data": custom_by_unit.get(row["id"], {}),
            "service_point_custom_data": by_unit.get(row["id"], {}),
        }
        for row in rows
    ]


def _unit_status(unit: models.Unit, account: dict[str, Any] | None, occupancy: str) -> str:
    """US-MET-002 §5: display only, computed from the account status + derived
    occupancy — no stored unit status column exists."""
    if unit.deleted_at is not None:
        return "inactive"
    if account is None:
        return "vacant" if occupancy == "vacant" else "pending"
    return str(account.get("status") or "active")


@batch_reads.memoised(copy=True)
def service_points_for(unit_id: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": str(point.id),
            "service": _service_code(point.service_id),
            "route_id": str(point.route_id) if point.route_id else None,
        }
        for point in models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_id, deleted_at__isnull=True
        ).order_by("created_at", "id")
    ]


def service_points_for_units(unit_ids: Any) -> dict[str, list[dict[str, Any]]]:
    """`{unit_id: [service point, …]}` for MANY units — **ONE query, not one per
    unit and not one per point.**

    ⛔ **DEF-2723's third and fourth statements per row.** `service_points_for`
    above is a per-unit read, and each point it returns then costs a catalog
    probe through `_service_code`, so a page of accounts paid `1 + P` round
    trips FOR EVERY ROW: on `customers.account_list` that was five of the nine
    statements per account behind a 562 ms accounts list. This is the same
    answer for a whole page.

    ⚠ **`select_related("service")` IS THE POINT, NOT AN OPTIMISATION DETAIL.**
    Without it `point.service.code` re-runs `_service_code`'s probe per point and
    this function is a loop over the singular wearing a plural's name — which is
    the shape `service_codes_for_points` warns about in its own docstring one
    screen down.

    Same tenant filter as the singular, never a wider one (CLAUDE.md hard rule
    1); a unit belonging to another tenant is simply absent, and a unit with no
    points is absent rather than present-and-empty, so a caller must use
    `.get(uid, [])` and cannot mistake "no points" for "not asked".
    """
    ids = [str(u) for u in (unit_ids or []) if _is_uuid(u)]
    if not ids:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for point in (
        models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(), unit_id__in=ids, deleted_at__isnull=True
        )
        .select_related("service")
        .order_by("created_at", "id")
    ):
        out.setdefault(str(point.unit_id), []).append(
            {
                "id": str(point.id),
                "service": point.service.code if point.service_id else None,
                "route_id": str(point.route_id) if point.route_id else None,
            }
        )
    return out


def unit_refs(unit_ids: Any) -> dict[str, dict[str, Any]]:
    """`{unit_id: {id, label, unit_no, premises_id, premise_no, premise_address}}`
    for MANY units — **ONE query.**

    ⛔ **DEF-2723's `units` statement per row.** `unit_row` is a perfectly good
    single-unit read and `customers._premise_cell` called it once per account to
    build the Premise cell. This is the page-wide form; it deliberately returns
    the FOUR fields that cell needs rather than `unit_detail_dict`'s full
    payload, because the detail dict reads the premises' service list too and a
    list row does not draw it.

    A unit that is absent from the map is a unit this tenant cannot see — the
    same 404-never-403 boundary `unit_row` enforces, expressed as absence
    because a batch read has no single subject to refuse about.
    """
    ids = [str(u) for u in (unit_ids or []) if _is_uuid(u)]
    if not ids:
        return {}
    return {
        str(unit.id): {
            "id": str(unit.id),
            "label": unit.label,
            # `DEF-CUS-9763` — the tenant's unit number (`SCW-U-311`), which the
            # move-in screens draw beside the label. A column on the same row,
            # so the read stays one query.
            "unit_no": unit.unit_no,
            "premises_id": str(unit.premises_id),
            "premise_no": unit.premises.premise_no,
            "premise_address": unit.premises.address_line,
        }
        for unit in models.Unit.objects.filter(tenant_id=_tenant_id(), pk__in=ids)
        .select_related("premises")
    }


def premises_refs(premises_ids: Any) -> dict[str, dict[str, Any]]:
    """The plural of `premises_row`, in the shape `customers.seams.premises_ref`
    publishes — **ONE query.**

    ⛔ **DEF-2723, the owner's-account half.** An account with no unit hangs off
    the ADDRESS (`BR-CUS-1010`), so its Premise cell is read from the premises
    instead; on a page of master accounts that was one round trip per row, and a
    fix that batched only the unit path would have left this one and quietly
    kept the defect for the customers who have the most of them.
    """
    ids = [str(p) for p in (premises_ids or []) if _is_uuid(p)]
    if not ids:
        return {}
    return {
        str(row.id): {
            "id": str(row.id),
            "premise_no": row.premise_no,
            "address_line": row.address_line,
            "owner_manager": row.owner_manager,
        }
        for row in models.Premises.objects.filter(tenant_id=_tenant_id(), pk__in=ids)
    }


def premises_services_for(premises_ids: Any) -> dict[str, list[str] | None]:
    """`{premises_id: services_available}` for many properties — **ONE query.**

    `BR-CUS-1093` (PO ruling 2026-09-23, *"in case of mater account - we will
    have to take utility servcies from premies, since it belong to premises"*)
    makes a MASTER account's service list a READ of this column. The account
    names no unit (`BR-CUS-1010`), so the walk customers already had —
    account → unit → service points — reaches nothing for it, and the owner's
    account showed *No services* at a building that takes water.

    ⚠ **HELD BY REFERENCE, NEVER COPIED**, which is `BR-CUS-672`'s own
    requirement of an inherited fact and the reason this is a read rather than
    a column or a backfill: a service added to the building appears on the
    owner's account the next time the list is drawn, and there is no second
    copy to drift.

    ⚠ **THREE STATES, NOT TWO — `DEF-762` / `CR-036` (h).** `None` means
    **nobody was ever asked**; `[]` is a clerk answering *this address offers
    nothing*. `premises_detail_dict` passes the column through unchanged for
    exactly that reason, and a batch read that collapsed the two here would
    undo the rule one layer above it. The list is COPIED (never the model's own
    object) so a caller cannot mutate the row through this map.

    ⚠ **ABSENCE, NOT A REFUSAL** — a premises this tenant cannot see is simply
    missing from the map, the same posture `premises_refs` takes and for the
    same reason: a batch read has no single subject to refuse about. A caller
    uses `.get(pid)` and cannot tell *not visible* from *not asked* by the shape
    alone; `premises_row` is the singular that refuses.
    """
    ids = [str(p) for p in (premises_ids or []) if _is_uuid(p)]
    if not ids:
        return {}
    return {
        str(row["id"]): (
            None if row["services_available"] is None else list(row["services_available"])
        )
        for row in models.Premises.objects.filter(
            tenant_id=_tenant_id(), pk__in=ids
        ).values("id", "services_available")
    }


def premises_locality(premises_id: Any) -> dict[str, Any] | None:
    """`BR-MET-1161` — the town, the state and the postcode of one premises.

    ⚠ **NEW 2026-09-04, AND IT REPLACES A COLUMN RATHER THAN ADDING A FEATURE**
    (`DEF-CUS-3653`). The account header used to compose its locality line from
    a `customers.addresses` row of `kind='service'` — a second, editable copy of
    where the meter is. That kind is retired under the PO's ruling of that day
    (*"we are having addresses at one place now - Premises and Units"*), so the
    line had to come from the one home or go silent, and a line that goes silent
    while every test passes is hard-won law 2 exactly.

    Three columns of one indexed row; nothing else about the premises travels.
    `None` for an id this tenant does not hold — the HR-1 answer, byte-identical
    to *there is no such premises*.
    """
    if premises_id in (None, ""):
        return None
    row = (
        models.Premises.objects.filter(tenant_id=_tenant_id(), pk=premises_id)
        .values("city", "state", "postal_code")
        .first()
    )
    return dict(row) if row else None


def envelope_addresses(*, unit_ids: Any = (), premises_ids: Any = ()) -> dict[str, dict]:
    """`BR-MET-1161` — the SERVICE ADDRESS as envelope lines, for MANY places.

    ⚠ **PUBLISHED FOR CUSTOMERS' RECIPIENT READ (`DEF-PAY-6342`, PO ruling
    2026-09-23: *"fx it - ensure you update correct address - mailing or
    service"*).** B2 §2 makes an account with no mailing row mean *"same as
    service"*, and `customers.selectors.delivery_recipients_for_account` said so
    in its docstring for six weeks while its code could not do it: the only
    premises reads published were `_premise_cell`'s DISPLAY string
    (`"1408 Elm St · A"`) and `premises_locality`'s three columns without the
    street. So every letter to an account with no mailing row was queued
    UNADDRESSED as `recipient_not_resolvable`. This is the structured read that
    was missing — four discrete columns, never a composed string, so nothing on
    the far side has to split one (`BR-NOT-029` clause (a)'s reasoning).

    ⚠ **THE UNIT IS A LABEL, NEVER A SECOND ADDRESS (hard rule 8).** A unit
    refines its premises by `label` and declares no address column, so a unit's
    envelope is its BUILDING's four lines plus `unit_label`. `lat`/`lng` are
    `BR-MET-1162`'s narrowing and have nothing to do with post; they do not
    travel.

    ⛔ **TWO QUERIES AT MOST, WHATEVER IS ASKED (`NFR-3`).** One for the units
    named (joined to their premises), one for the premises named directly — the
    owner's account names a premises and no unit (`BR-CUS-1010`). Nothing per
    row: the same shape `unit_refs` / `premises_refs` took after `DEF-2723`.

    Returns `{"units": {unit_id: env}, "premises": {premises_id: env}}` where
    `env` is `{"premises_id", "line1", "city", "state", "postal_code",
    "unit_label"}`. **An id absent from its map is one this tenant cannot see**
    — absence rather than a refusal, because a batch read has no single subject
    to refuse about (`premises_refs`' posture). A present entry whose `line1` is
    blank is a premises nobody gave a street, which is a fact about the
    PROPERTY; this read reports it as it is and the caller decides what that
    means for a letter.
    """
    unit_keys = [str(u) for u in (unit_ids or []) if _is_uuid(u)]
    premises_keys = [str(p) for p in (premises_ids or []) if _is_uuid(p)]
    units: dict[str, dict[str, Any]] = {}
    premises: dict[str, dict[str, Any]] = {}
    tenant_id = _tenant_id() if (unit_keys or premises_keys) else None
    if unit_keys:
        for row in models.Unit.objects.filter(tenant_id=tenant_id, pk__in=unit_keys).values(
            "id",
            "label",
            "premises_id",
            "premises__address_line",
            "premises__city",
            "premises__state",
            "premises__postal_code",
        ):
            units[str(row["id"])] = {
                "premises_id": str(row["premises_id"]),
                "line1": row["premises__address_line"],
                "city": row["premises__city"],
                "state": row["premises__state"],
                "postal_code": row["premises__postal_code"],
                "unit_label": row["label"],
            }
    if premises_keys:
        for row in models.Premises.objects.filter(tenant_id=tenant_id, pk__in=premises_keys).values(
            "id", "address_line", "city", "state", "postal_code"
        ):
            premises[str(row["id"])] = {
                "premises_id": str(row["id"]),
                "line1": row["address_line"],
                "city": row["city"],
                "state": row["state"],
                "postal_code": row["postal_code"],
                "unit_label": None,
            }
    return {"units": units, "premises": premises}


def service_point_ref(service_point_id: Any) -> dict[str, Any] | None:
    """Same-tenant service point resolved for the assets lane's FK check."""
    if not _is_uuid(service_point_id):
        return None
    row = (
        models.ServicePoint.objects.filter(tenant_id=_tenant_id(), pk=service_point_id)
        .select_related("unit")
        .first()
    )
    if row is None:
        return None
    return {
        "id": str(row.id),
        "unit_id": str(row.unit_id),
        "service": _service_code(row.service_id),
    }


@batch_reads.memoised
def _service_code(service_id: Any) -> str | None:
    # Read-only probe on the RLS-exempt platform catalog (Eng disposition —
    # tenancy exposes no id→code selector; identical precedent in identity).
    model = django_apps.get_model("tenancy", "Service")
    return model.objects.filter(pk=service_id).values_list("code", flat=True).first()


# Above this many ids a batched read asks for the tenant's whole set and filters
# in Python instead of binding every id as a parameter (`DEF-TEN-8731`,
# `DEF-MET-8732`): binding costs ~30–50 µs of Python per id before PostgreSQL
# sees the statement, which is seconds at 40,000; reading two narrow columns of
# every row is a fraction of that. No cap — both branches answer every row.
_BIND_IDS_UP_TO = 2000


def service_points_queryset() -> Any:
    """The tenant's service points as a LAZY queryset — for a caller that
    needs a point's service INSIDE its own statement (`DEF-TEN-8731`).

    Handed out unevaluated, the way `premises_list` is for the customers search
    leg: the caller correlates it as a subquery (`OuterRef`), so PostgreSQL
    joins and groups, and no point id crosses into Python. Only this tenant's
    rows (CLAUDE.md hard rule 1), and RLS still applies to the statement."""
    return models.ServicePoint.objects.filter(tenant_id=_tenant_id())


def service_codes_by_ids(service_ids: Any) -> dict[str, str]:
    """`{service id: code}` for platform catalog services — the second half of
    `service_codes_for_points`, for a caller that already grouped by id."""
    ids = {value for value in service_ids if value is not None}
    if not ids:
        return {}
    model = django_apps.get_model("tenancy", "Service")
    return {str(pk): code for pk, code in model.objects.filter(pk__in=ids).values_list("pk", "code")}


def service_codes_for_points(service_point_ids: Any) -> dict[str, str | None]:
    """`{service_point_id: service code}` for MANY points — **TWO queries, not
    two per point.**

    ⛔ **DEF-1549's second N+1, published so its one caller can stop paying it.**
    `customers.active_account_count` resolved the service behind an agreement by
    calling `service_point_ref` once per point, and that function costs **two**
    round trips each (the point row, then `_service_code`'s catalog probe). It
    memoised inside a single call and not across calls, so
    `tenancy.services_overview()` — which calls it once per active service — paid
    `~10 × 2P` queries to draw one screen, and the asset importer paid that
    again for every row of the file. This answers the whole set at once.

    ⚠ **IT IS THE SET QUESTION, NOT A LOOP OVER THE SINGULAR.** Returning a dict
    keyed by `str(id)` is deliberate: the caller holds `UUID`s from a
    `values_list` and the singular's callers hold strings, and a map that only
    matched one of those shapes would silently answer `None` — which reads as
    *"no such point"* and would undercount rather than fail. Non-UUID input is
    dropped exactly as `service_point_ref` drops it, and a point belonging to
    another tenant is simply absent (CLAUDE.md hard rule 1 — the same
    `tenant_id` filter, never a wider one).
    """
    # A `UUID` needs no parse to prove it is one (160,000 parses were ~1 s of
    # the 40,000-account S8 read — `DEF-TEN-8731`).
    ids = [
        str(value) for value in service_point_ids if isinstance(value, UUID) or _is_uuid(value)
    ]
    if not ids:
        return {}
    points = models.ServicePoint.objects.filter(tenant_id=_tenant_id())
    if len(ids) > _BIND_IDS_UP_TO:
        # ⛔ `DEF-TEN-8731` — a WHOLE-ESTATE set is read without binding it.
        # `pk__in=<40,000 ids>` cost ~2 s of Django building the filter before
        # PostgreSQL saw the statement, and `services_overview` paid it once per
        # service. Above the bound, read the tenant's points (two narrow
        # columns) and keep the asked ones: the same rows, the same answer.
        wanted = set(ids)
        rows = [
            (point_id, service_id)
            for point_id, service_id in points.values_list("id", "service_id")
            if str(point_id) in wanted
        ]
    else:
        rows = list(points.filter(pk__in=ids).values_list("id", "service_id"))
    if not rows:
        return {}
    model = django_apps.get_model("tenancy", "Service")
    codes = dict(
        model.objects.filter(pk__in={service_id for _, service_id in rows}).values_list(
            "pk", "code"
        )
    )
    return {str(point_id): codes.get(service_id) for point_id, service_id in rows}


@batch_reads.memoised
def unit_row(unit_id: Any) -> models.Unit:
    if not _is_uuid(unit_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    row = (
        models.Unit.objects.filter(tenant_id=_tenant_id(), pk=unit_id)
        .select_related("premises")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def unit_id_for_reference(ref: str) -> str | None:
    """BR-AST-034: resolve the import template's "unit ref" column against
    EXISTING units only — "1408 Elm Street · Unit A", "P-00101 · Unit A", a
    unit_no or a uuid. An unmatched reference is a ROW ERROR for the caller,
    never an auto-created premises/unit."""
    tenant_id = _tenant_id()
    cleaned = str(ref or "").strip()
    if not cleaned:
        return None
    qs = models.Unit.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True)
    row = qs.filter(unit_no__iexact=cleaned).first()
    if row is None and "·" in cleaned:
        premise_part, _, label_part = cleaned.partition("·")
        premise_part, label_part = premise_part.strip(), label_part.strip()
        row = qs.filter(
            Q(premises__premise_no__iexact=premise_part)
            | Q(premises__address_line__iexact=premise_part),
            label__iexact=label_part,
        ).first()
    if row is None and _is_uuid(cleaned):
        row = qs.filter(pk=cleaned).first()
    return str(row.id) if row is not None else None


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def unit_ids_matching(term: str) -> list[str]:
    """BR-AST-041: the S49 search covers the premises/unit address."""
    return [
        str(unit_id)
        for unit_id in models.Unit.objects.filter(tenant_id=_tenant_id())
        .filter(
            Q(label__icontains=term)
            | Q(unit_no__icontains=term)
            | Q(premises__address_line__icontains=term)
            | Q(premises__premise_no__icontains=term)
        )
        .values_list("id", flat=True)
    ]


def move_in_unit_queryset(term: str, *, also_unit_ids: Any = None) -> QuerySet:
    """`DEF-CUS-10190` — EVERY live unit of this tenant a move-in may search,
    LAZY, matched on what a clerk has in front of them (PO 2026-10-17,
    *"user wants search all units irrespective of ther tatus"*).

    Matched here (metering owns the columns): the unit's number and label, the
    property number and name, and the ADDRESS — which lives on `premises` and
    nowhere else (hard rule 8). `also_unit_ids` is the caller's own legs (the
    meter number, the occupant's name), passed as ids or an unevaluated
    queryset, so the whole search stays one SQL statement (`NFR-3`).

    ⚠ **A REMOVED UNIT IS NOT LISTED** (`deleted_at` set) — PO, same day:
    *"Removed (inactive) unit: dont allow it"*. Unordered: the caller sorts,
    because *vacant first* is a fact customers owns.
    """
    text = str(term or "").strip()
    qs = models.Unit.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
    if text == "":
        return qs
    # `CR-200-BRC10` — every word must match the unit or its building; the
    # caller's own legs stay whole-phrase alternatives, as they were.
    matches = unit_word_match(text)
    if also_unit_ids is not None:
        matches |= Q(pk__in=also_unit_ids)
    return qs.filter(matches)


def premises_id_query(term: str) -> QuerySet:
    """`DEF-LED-10071` (J1) — this tenant's premises whose ADDRESS matches, LAZY.

    Published for the ledger's journal search: *"find an entry when any of its
    lines belongs to a matching premises address"*. It returns an UNEVALUATED
    `values("id")` queryset, so the caller can use it as a subquery and the
    whole search stays ONE SQL statement (`NFR-3`) — a list of ids here would
    be one query per search leg and an unbounded `IN (...)` at the top of T5.

    The address lives on `premises` and nowhere else (CLAUDE.md hard rule 8),
    so this is the one place an address is matched. `premise_no` rides with it
    because the premises number is printed beside the address on every screen.
    Tenant-scoped at source (rule 1).
    """
    return (
        models.Premises.objects.filter(tenant_id=_tenant_id())
        .filter(Q(address_line__icontains=term) | Q(premise_no__icontains=term))
        .values("id")
    )


def unit_id_query(term: str) -> QuerySet:
    """`DEF-LED-10071` (J1) — this tenant's units whose LABEL matches, LAZY.

    The unit half of `premises_id_query`, for the same caller and the same
    reason. A unit refines a premises by LABEL, never by address (hard rule
    8), so this matches the label and the unit number and nothing else — the
    address leg is `premises_id_query`'s, and a journal line carries both ids.
    """
    return (
        models.Unit.objects.filter(tenant_id=_tenant_id())
        .filter(Q(label__icontains=term) | Q(unit_no__icontains=term))
        .values("id")
    )


#: The three `units_list` filters that are NOT a `WHERE` clause.
#:
#: ⚠ **THIS TUPLE IS WHAT LETS THE UNITS LIST TAKE ITS PAGE IN SQL
#: (`DEF-MET-5761`), AND IT IS WRITTEN OUT RATHER THAN INFERRED.** Each of the
#: three partitions on a value no column on `units` holds: `occupancy` is
#: DERIVED and has no stored column at all (`BR-MET-036` — *"there is no stored
#: occupancy column and no way to set one"*), `sub_metered` asks the ASSETS
#: seam what is fitted, and `service` reads the unit's BUILDING's
#: `services_available` (`DEF-755` — the filter must match what the column
#: shows). A row has to be built before any of them can be read, so a `LIMIT`
#: applied first would page a different set than the one the count claims.
#: `units_list_is_sql_pageable` is the ONE place that decision is made.
UNIT_DERIVED_FILTERS = ("occupancy", "sub_metered", "service")


def units_list_is_sql_pageable(filters: dict[str, Any] | None) -> bool:
    """Can this filter set be answered entirely by the database?

    ⚠ **THE PREDICATE MIRRORS `units_list`'s THREE PYTHON PASSES EXACTLY,
    INCLUDING WHERE THEY ARE LOOSE.** `sub_metered` is tested for TRUTHINESS
    there, so `f.sub_metered=false` is a non-empty string and narrows to
    sub-metered units; `occupancy` narrows only for the three values it
    recognises and any other value falls through filtering NOTHING. Both
    readings are reproduced here rather than tidied, because a predicate that
    is stricter or looser than the passes it guards would page one set and
    count another — which is worse than the cost it removes.
    """
    filters = filters or {}
    if filters.get("occupancy") in ("occupied", "vacant", "sub_metered"):
        return False
    if filters.get("sub_metered"):
        return False
    if filters.get("service"):
        return False
    return True


def units_queryset(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> QuerySet:
    """The SQL half of `units_list` — narrowed and ORDERED, **not evaluated**.

    ⚠ **EXTRACTED, NOT REWRITTEN (`DEF-MET-5761`).** Every line below stood
    inside `units_list`, which still calls this and still returns exactly what
    it returned; splitting it is what lets `units_page` put a `LIMIT` on the
    same narrowing the derived path builds from, so the two cannot drift into
    filtering differently (hard-won law 1). The ORDER is `_order`'s, tiebroken
    on `id`, so a page is a window over a TOTAL order and page 2 cannot repeat
    a row from page 1.
    """
    qs = models.Unit.objects.filter(tenant_id=_tenant_id()).select_related("premises")
    filters = filters or {}
    if premises_id := filters.get("premises_id"):
        qs = qs.filter(premises_id=premises_id)
    # `CR-168-BRC10` image 14 (lane SRV-2, for lane RAISE) — the raise's
    # *Residential · Commercial* chips: the unit type CODE(s), any of them
    # (OQ-306's grammar). A plain SQL narrowing, so the list still pages in SQL.
    if unit_types := filter_values(filters.get("unit_type")):
        qs = qs.filter(unit_type__in=unit_types)
    # BR-MET-100 (second half): an unplanned unit must be COUNTED AND FINDABLE —
    # "the Units tab carries a filter that lists them". Option B's decided cost
    # is that a unit with no plan never appears on a bill while looking complete
    # on every screen; this filter is what makes that risk operable. `planned`
    # is the complement, so the one control can partition rather than only carve.
    if (plan := filters.get("plan")) in ("unplanned", "planned"):
        qs = qs.filter(rate_plan_id__isnull=(plan == "unplanned"))
    # ── `missing_services` — PO ruling 2026-09-28 ────────────────────────────
    # *"the Units 'Missing services' block — filter or leave it. - filter"*.
    # The shortfall used to be a SECOND READ under a SECOND TABLE with a second
    # pager; it is now one value on the list's own filter set, which is what
    # lets a clerk combine it with the search, with the other four filters, and
    # — the reason the PO gave — SELECT the units it matches and act on them
    # together. The narrowing is `_short_of_offer` and it is SQL, so the page is
    # still a `LIMIT` over an ordered set (`NFR-3`) and nothing here caps
    # anything (`NFR-5`).
    #
    # ⚠ **THE DELETED-UNIT EXCLUSION BELONGS TO THE FILTER AND NOT TO THE
    # LIST.** `BR-MET-119`'s report has always excluded them — *"a unit taken
    # out of service is not a service the utility is failing to bill"* — while
    # the units list itself shows them with an `inactive` status. Both stay
    # true: the exclusion rides inside this branch, so the count a clerk reads
    # is the same number the retired block printed.
    if filters.get("missing_services"):
        qs = _short_of_offer(qs.filter(deleted_at__isnull=True))
    if term := (q or "").strip():
        if len(term) >= 2:
            # `CR-200-BRC10` — every word must match the unit or its building
            # (`unit_word_match`). The meter number stays a WHOLE-PHRASE
            # alternative: it is an identifier a clerk types alone, not a word
            # of an address, and it is exactly what this leg matched before.
            matches = unit_word_match(term)
            meter_unit_ids = seams.resolve("assets", "unit_ids_for_asset_search", kind="selectors")
            if meter_unit_ids is not None:
                matches |= Q(id__in=list(meter_unit_ids(term)))
            qs = qs.filter(matches)
    return _order(qs, UNIT_SORTS, sort or UNIT_DEFAULT_SORT, direction)


def units_list(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> list[models.Unit]:
    """S15 rows. `occupancy` / `sub_metered` filters partition on DERIVED
    values (BR-MET-036), so they are applied after the SQL narrowing.

    ⚠ **PREFER `units_page` FOR A SCREEN.** This builds EVERY matching row by
    construction, which is what the three derived filters above need and what
    `DEF-MET-5761` records as the cost when a list read takes it and then keeps
    fifty. It stays exactly as it was because a dozen callers — the exports,
    the seed, both sample-data builders and the customers seam — read every row
    on purpose and are not screens.
    """
    filters = filters or {}
    rows = list(units_queryset(q=q, filters=filters, sort=sort, direction=direction))
    occupancy = filters.get("occupancy")
    services = filter_values(filters.get("service"))  # OQ-306 — ANY of
    if occupancy in ("occupied", "vacant"):
        rows = [u for u in rows if occupancy_of(u) == occupancy]
    if occupancy == "sub_metered" or filters.get("sub_metered"):
        rows = [
            u for u in rows if any(m.get("qualifier") == "sub" for m in seams.assets_on_unit(u.id))
        ]
    if services:
        # ⚠ **DEF-755 — THE FILTER MATCHES WHAT THE COLUMN SHOWS.** It read
        # service points, so a clerk who filtered by Water lost every unit that
        # HAS water available and no water meter — the filter disagreeing with
        # the column beside it. Now both read the premises' list, so "filter by
        # water" returns exactly the rows whose Services cell says Water.
        #
        # A unit whose premises has never been asked (`None`) matches NOTHING,
        # and that is right: *unrecorded* is not *water*. Those units are found
        # by their empty Services cell, not by a service filter that guessed.
        rows = [
            u
            for u in rows
            if any(one in (u.premises.services_available or []) for one in services)
        ]
    return rows


def units_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """THE S15 list read: `(one page of rows, the whole result set's count)`.

    ⚠ **THIS IS `NFR-3` ON THE UNITS TAB (`DEF-MET-5761`).** `GET /units` built
    every unit the tenant has, ordered them, and handed the lot to a paginator
    that kept fifty — and `unit_list_rows` then resolved the ledger for those
    fifty, so the money was never the cost. The count comes from `COUNT(*)`
    over the same queryset, so a clerk on page 1 of 40,000 units is told there
    are 40,000 without 40,000 rows being built. `NFR-5` is honoured by there
    being no cap of any kind here: `per` clamps to the IS-2 vocabulary and
    `page` clamps into range (`BR-SHL-011`), and neither ever refuses a row
    that exists.

    ⚠ **THE DERIVED PATH IS KEPT AND IS NOT AN OVERSIGHT.** When
    `units_list_is_sql_pageable` says no — occupancy, sub-metering or service —
    this builds the matching set and slices it, which is `O(tenant)` and is
    recorded HERE rather than hidden, exactly as `customers.account_page` records
    its own four derived sorts. Those three filters are chips a clerk chooses,
    not the screen's default, so the list as it OPENS is the SQL path.

    ⚠ **ONE LEDGER READ PER PAGE, STILL.** `unit_list_rows` resolves the OWED
    column once for the rows it is given (`CR-089` `E1`/`PUJ-22`,
    `DEF-MET-4733`), and it is given a PAGE in both branches — so the money is
    asked for fifty units whichever way the page was taken.
    """
    filters = params.filters or {}
    start = max(params.page - 1, 0) * params.per
    if not units_list_is_sql_pageable(filters):
        rows = units_list(q=params.q, filters=filters, sort=params.sort, direction=params.dir)
        return unit_list_rows(rows[start : start + params.per]), len(rows)
    qs = units_queryset(q=params.q, filters=filters, sort=params.sort, direction=params.dir)
    total = qs.count()
    return unit_list_rows(list(qs[start : start + params.per])), total


# ── THE SERVICE GAP — `missing_services`, A FILTER ON THE UNITS LIST ────────
# `DEF-MET-6796` · `BR-MET-119` as amended 2026-09-25 · **PO ruling 2026-09-28**
#
# ⚠ **THIS WAS `GET /units/service-gaps` UNTIL 2026-09-28 AND THE ENDPOINT IS
# RETIRED.** PO, verbatim: *"the Units 'Missing services' block — filter or
# leave it. - filter"*. A second read under a second table with a second pager
# could not compose: the same 60 units appeared twice, could be combined with
# neither the search nor the four filters, could not be paged with the list, and
# — the reason the PO gave — could not be SELECTED for a bulk action, which is
# the one thing a clerk wants to do with a list of units that are short. What
# survives is the SQL: `_short_of_offer` narrows, `units_gap_count` counts, and
# both run inside `units_queryset`'s own narrowing rather than beside it.
def _held_points_subquery() -> Subquery:
    """How many live service points a unit holds, as a CORRELATED SUBQUERY.

    ⚠ **A SUBQUERY RATHER THAN `Count(...)` ON PURPOSE.** `units_queryset`
    carries `select_related("premises")`, so an aggregate annotation would put
    every premises column into the `GROUP BY` — which PostgreSQL refuses and
    SQLite silently permits, i.e. a query that passes the whole test suite and
    fails on the only database this product runs on (hard-won law 14's shape,
    one layer out from the transaction it is written about). The subquery adds
    no grouping to the outer query at all, so the two backends run the same
    plan and the page stays a `LIMIT` over an ordered set.
    """
    return Subquery(
        models.ServicePoint.objects.filter(
            tenant_id=OuterRef("tenant_id"), unit=OuterRef("pk"), deleted_at__isnull=True
        )
        .order_by()
        .values("unit")
        .annotate(held=Count("id"))
        .values("held")[:1],
        output_field=IntegerField(),
    )


def premises_offer_sizes() -> list[list[str]]:
    """Every DISTINCT non-empty service offer any of this tenant's addresses
    declares, newest reading each time.

    This is what makes the gap read answerable in SQL. A unit is short when the
    number of service points it holds is fewer than the number of services its
    address offers, and `services_available` is a JSON list — so there is no
    portable `length(column)` to compare against. There does not need to be:
    the number of DISTINCT offers in a utility is a handful (a utility selling
    eleven services still writes the same two or three lists over and over),
    so the lengths go into a `CASE` and the comparison happens in the database.

    `None` and `[]` are both dropped here and that is `BR-MET-119`'s own
    distinction doing its job twice over: `None` is *nobody was asked* and `[]`
    is *this address offers nothing*. **Neither address can leave a unit
    short**, because neither offers anything to be short OF.
    """
    return [
        offer
        for offer in models.Premises.objects.filter(tenant_id=_tenant_id())
        .values_list("services_available", flat=True)
        .distinct()
        if offer
    ]


def _short_of_offer(qs: QuerySet) -> QuerySet:
    """Narrow a units queryset to those holding FEWER service points than their
    premises OFFERS — the engine behind the `missing_services` filter.

    **`BR-MET-119` AS AMENDED 2026-09-25.** A unit's set is *within* its
    premises' set rather than equal to it, so a shortfall is a legitimate state
    and this exists to COUNT it rather than to refuse it. What makes it worth
    counting is `BR-BIL-300`: service points decide what a bill charges, so
    every row it keeps is a service the address advertises and nobody is billed
    for.

    ⚠ **`held < offered` IS SOUND ONLY BECAUSE THE OTHER SIDE IS GUARDED.**
    `_refuse_service_not_at_premises` makes a unit's points a SUBSET of the
    offer, so comparing two counts is the same question as comparing two sets —
    and comparing counts is a thing SQL can do. The subset guard is therefore
    load-bearing here; if it is ever relaxed, this comparison becomes wrong
    before it becomes slow. **The ROW still computes the SET**
    (`unit_list_dict`'s `missing_services`) so a clerk sees which services are
    missing, and a row under this filter that names none would be this
    assumption breaking in public — `T4-B` asserts exactly that.

    ⚠ **IT TAKES A QUERYSET RATHER THAN BUILDING ONE (hard-won law 1).** It is
    applied INSIDE `units_queryset`, on the same narrowing the search box and
    the other four filters build, so the gap filter cannot start answering
    about a different set the first time either changes. That is also why it is
    private: `GET /units/service-gaps` was a second door onto one set and the
    PO closed it on 2026-09-28.
    """
    offers = premises_offer_sizes()
    if not offers:
        # No address offers anything, so nobody can be short of anything. An
        # empty narrowing rather than an unfiltered queryset: the filter must
        # never be a no-op that quietly serves the whole list.
        return qs.none()
    from django.db.models import Case, When

    return qs.annotate(
        offer_size=Case(
            *[
                When(premises__services_available=offer, then=Value(len(offer)))
                for offer in offers
            ],
            default=Value(0),
            output_field=IntegerField(),
        ),
        points_held=Coalesce(_held_points_subquery(), Value(0)),
    ).filter(points_held__lt=F("offer_size"))


def units_gap_count(params: ListParams) -> int:
    """**HOW MANY UNITS ARE SHORT, UNDER EVERYTHING ELSE THE CLERK HAS SET.**

    ⚠ **THIS NUMBER IS THE DELIVERABLE, NOT THE FILTER CONTROL (PO ruling
    2026-09-28).** `DEF-MET-6796` exists precisely because the shortfall was
    INVISIBLE — no screen, gate or test counted it — and a filter nobody
    switches on is invisible in exactly the same way. So the units list serves
    this figure in its own envelope on EVERY read, whether or not the filter is
    engaged, and the toolbar draws it whether or not it is engaged.

    ⚠ **IT IGNORES `missing_services` AND HONOURS EVERYTHING ELSE.** Switching
    the filter on must not change the number beside the control — a count that
    became its own result set would read as though turning the filter on had
    fixed something. The search term and the other four filters DO narrow it,
    because the answer to *how many of what I am looking at are short* is the
    one a clerk can act on.

    ⚠ **IT IS ONE `COUNT(*)` ON THE SQL PATH (`NFR-3`, `NFR-5`).** No row is
    built and nothing is capped. On the DERIVED path — occupancy, sub-metering
    or service, the three filters `units_list_is_sql_pageable` refuses — it
    builds the matching set and takes its length, which is the identical cost
    `units_page` itself already pays on that path and is recorded here rather
    than hidden. Those three are chips a clerk chooses; the list as it OPENS is
    the SQL path.
    """
    filters = {**(params.filters or {}), "missing_services": "yes"}
    if not units_list_is_sql_pageable(filters):
        return len(units_list(q=params.q, filters=filters, sort=params.sort, direction=params.dir))
    return units_queryset(
        q=params.q, filters=filters, sort=params.sort, direction=params.dir
    ).count()


# ── routes & cycles (S26, S27, S8) ──────────────────────────────────────────
def premises_order_map(route_id: Any) -> dict[str, int]:
    """CR-029 D11 — premises id → its STOP NUMBER on this route, or nothing.

    The ruled grain (`route_premises_orders`), read as a map so the membership
    below can carry the stop's position instead of the superseded per-unit
    column's.
    """
    return {
        str(premises_id): order
        for premises_id, order in models.RoutePremisesOrder.objects.filter(
            tenant_id=_tenant_id(), route_id=route_id
        ).values_list("premises_id", "walk_order")
    }


def _ordered_members(rows: list[dict[str, Any]], stops: dict[str, int]) -> list[dict[str, Any]]:
    """Membership rows carrying the RULED stop number as their walk order.

    ⚠ **THE SERVED `walk_order` IS THE STOP'S, AND THIS IS WHY (D11).** SET-06D
    folds these rows into stops and sorts them by this value — it never renders
    it — so the number has to agree with `route_premises_orders` or the screen
    re-orders a walk somebody saved. `services._set_route_membership` writes
    `walk_order=None` for every premises-selected member on EVERY route edit,
    so a saved order would silently stop being reflected the next time anyone
    renamed the route: the table would still hold the truth and the screen
    would draw insertion order. Deriving it here cannot go stale that way.

    A route with no stored order keeps the column's own value (which is null on
    every route in this product — the column has never had a writer), and the
    rows then fall back to the address order they were read in.
    """
    for row in rows:
        stop = stops.get(row["premises_id"])
        if stop is not None:
            row["walk_order"] = stop
    # Stable: rows with a stop number lead, in stop order; everything else
    # keeps the order the database returned it in.
    return sorted(rows, key=lambda row: (row["walk_order"] is None, row["walk_order"] or 0))


def stored_route_members(route_id: Any) -> list[dict[str, Any]]:
    """The STORED membership rows — the human choices, exactly as saved.

    ⚠ **THIS IS NOT "WHO IS ON THIS ROUTE" (CR-029 D4).** It is what somebody
    ticked, which is a different question and has exactly two consumers: the
    WRITE paths, whose before/after audit must show what the write changed, and
    the service-point stamp, which is a projection of the stored rows. Every
    READ uses `route_members` below, which asks the tags.
    """
    # ⚠ **READ FROM THE PREMISES THE HUMAN PICKED (`CR-131-BRC07`).** The rows
    # a person ticked are buildings now, so this expands them to their units in
    # ONE query rather than reading 726 stored rows that all said the same six
    # things. The SHAPE is unchanged — every consumer (the audit's before/after
    # count, the service-point stamp) reads unit rows and still gets them.
    tenant_id = _tenant_id()
    picked = list(
        models.RoutePremisesMembership.objects.filter(
            tenant_id=tenant_id, route_id=route_id
        ).values_list("premises_id", flat=True)
    )
    rows = (
        [
            {
                "unit_id": str(unit.id),
                "unit_label": unit.label,
                "premises_id": str(unit.premises_id),
                "premise_no": unit.premises.premise_no,
                # ⚠ Always `None` here, and `_ordered_members` below replaces it
                # with the STOP number from `route_premises_orders` — the ruled
                # grain (PO 2026-08-23 *"Per premises"*, re-affirmed 2026-09-22
                # *"a is okay"*). The superseded per-unit column is not read.
                "walk_order": None,
            }
            for unit in models.Unit.objects.filter(
                tenant_id=tenant_id, premises_id__in=picked, deleted_at__isnull=True
            )
            .select_related("premises")
            .order_by("premises__premise_no", "label", "id")
        ]
        if picked
        else []
    )
    return _ordered_members(rows, premises_order_map(route_id))


def _expected_meters(routes: list[Any]) -> int:
    """How many meters a cycle's routes expect, in ONE assets read.

    ⚠ **`CR-131-BRC07` step 7 — this was `assets_on_unit` PER MEMBER UNIT**,
    which is `D7`'s N+1 surviving on the path no page uses. A cycle holding a
    726-unit route paid 1,452 queries to print one number.
    """
    unit_ids = [member["unit_id"] for route in routes for member in route_members(route.id)]
    if not unit_ids:
        return 0
    counts = seams.asset_counts_for_units(unit_ids)
    return sum(counts.get(unit_id, 0) for unit_id in unit_ids)


def _hydrate_members(rows: list[dict[str, Any]], stops: dict[str, int]) -> list[dict[str, Any]]:
    """Turn the derivation's `{unit_id, basis, walk_order}` rows into the shape
    every reader of a route's membership already consumes — in ONE query for the
    whole route, never one per member (D7)."""
    if not rows:
        return []
    units = {
        str(unit.id): unit
        for unit in models.Unit.objects.filter(
            tenant_id=_tenant_id(), id__in=[row["unit_id"] for row in rows]
        ).select_related("premises")
    }
    served: list[dict[str, Any]] = []
    for row in rows:
        unit = units.get(row["unit_id"])
        if unit is None:  # pragma: no cover - the resolution read the same rows
            continue
        served.append(
            {
                "unit_id": str(unit.id),
                "unit_label": unit.label,
                "premises_id": str(unit.premises_id),
                "premise_no": unit.premises.premise_no,
                "walk_order": row.get("walk_order"),
            }
        )
    # The same order the stored read used — `order_by("walk_order",
    # "unit__label", "id")`, with Postgres' NULLS LAST written out.
    served.sort(
        key=lambda row: (
            row["walk_order"] is None,
            row["walk_order"] if row["walk_order"] is not None else 0,
            row["unit_label"] or "",
            row["unit_id"],
        )
    )
    return _ordered_members(served, stops)


def route_members(route_id: Any) -> list[dict[str, Any]]:
    """BR-MET-033: the membership set with its walk order (D11 — the STOP's).

    ⚠ **DERIVED (CR-029 D4, PO *"yes member resolve at run time"*).** *"Who is on
    this route right now"* is one of the three scoping questions B17 §5 names,
    so it is asked of the current tags through `apps.metering.derivation` rather
    than read back from `route_memberships`. The stored rows are still what a
    human ticked and are still read — as one of the two ways a route can claim a
    unit, never as the answer. `stored_route_members` above serves the write
    paths that need the rows themselves.
    """
    from apps.metering import derivation

    return _hydrate_members(derivation.members_of_route(route_id), premises_order_map(route_id))


def route_excluded_asset_ids(route_id: Any) -> list[str]:
    """BR-MET-075 — the meters deliberately NOT read on this route."""
    return [
        str(value)
        for value in models.RouteMeterExclusion.objects.filter(
            tenant_id=_tenant_id(), route_id=route_id
        ).values_list("asset_id", flat=True)
    ]


def route_exclusion_reasons(route_id: Any) -> dict[str, str | None]:
    """CR-029 (B17 §6) — asset id → **the two words that explain the exclusion**.

    *"`route_meter_exclusions.reason` — two words, shown in place"*: SET-06D's
    Assets tab renders *"MTR-W2262 excluded · premise demolished"* where the row
    sits. RC-W1 landed the column and nothing served it, so the screen could say
    THAT a meter is off the route and never WHY — and the next staff member
    re-ticks it.

    `None` is a real answer and is kept as one: every exclusion made before the
    column has no reason, and inventing one would be worse than the blank.
    """
    return {
        str(asset_id): reason
        for asset_id, reason in models.RouteMeterExclusion.objects.filter(
            tenant_id=_tenant_id(), route_id=route_id
        ).values_list("asset_id", "reason")
    }


def _route_service_rows(route_id: Any) -> list[models.RouteService]:
    """CR-029 D10 — the route's service SET, ordered by service code.

    ONE ORDER, ALWAYS. `route_services` is a set and a set has no order, so the
    two published reads below sort by the service's own code — otherwise the
    "Service(s)" cell on SET-05 could read *"Water + Electric"* on one request
    and *"Electric + Water"* on the next, which reads as a change and is not one.
    """
    return list(
        models.RouteService.objects.filter(tenant_id=_tenant_id(), route_id=route_id)
        .select_related("service")
        .order_by("service__code", "id")
    )


def route_service_codes(route_id: Any) -> list[str]:
    """The set as CODES — what SET-05's "Service(s)" column and SET-06D's Facts
    rail render. An EMPTY list is the legacy ALL-SERVICES route and is the true
    answer for it; it is never filled in with every enabled service, because
    that would be this selector deciding what an untagged route reads."""
    return [row.service.code for row in _route_service_rows(route_id)]


def route_service_ids(route_id: Any) -> list[str]:
    """The same set as IDS, in the same order, for the wizard's picker."""
    return [str(row.service_id) for row in _route_service_rows(route_id)]


class RouteBatch:
    """CR-029 D7 — every per-row derivation a page of routes needs, in five reads.

    **THE DEFECT THIS REMOVES, IN ITS OWN ARITHMETIC.** `route_dict` asked the
    assets seam for the meters on a unit once per MEMBER: a route with 380
    members cost 760 queries, and `GET /routes` paid it for every route in the
    tenant on every keystroke of the search box. B17 §5 gap G7 names it
    (*"unpaginated lists with per-row N+1"*) and D7 rules it out — *"Yes -
    please do it"*.

    ⚠ **THE MAPS ARE BUILT WITH THE SAME ORDERINGS THE PER-ROW SELECTORS USE**,
    which is what makes `route_dict(row)` and `route_dict(row, batch=…)` the
    same answer rather than two nearly-identical ones. Grouping preserves the
    relative order the database returned, so the membership a screen folds into
    stops comes back in the walk order either way.
    """

    def __init__(self, rows: list[models.Route]) -> None:
        route_ids = [row.id for row in rows]
        # Taken HERE: `rows` is rebound by the membership loop below.
        reader_ids = [row.assigned_to_id for row in rows]
        tenant_id = _tenant_id()
        # D11 — the ruled stop numbers for the whole page, in one read, so the
        # membership rows below carry the STOP's order (see `_ordered_members`).
        stops: dict[str, dict[str, int]] = {}
        for route_id, premises_id, position in models.RoutePremisesOrder.objects.filter(
            tenant_id=tenant_id, route_id__in=route_ids
        ).values_list("route_id", "premises_id", "walk_order"):
            stops.setdefault(str(route_id), {})[str(premises_id)] = position
        # CR-029 D4 — DERIVED membership, one resolution for the whole page.
        # `route_dict`'s Members and Meters columns answer *"who is on this
        # route right now"*, which B17 §5 rules is a live question; asking it
        # per route would be the N+1 D7 ruled against, so the resolution takes
        # the page's route ids at once.
        from apps.metering import derivation

        derived = derivation.members_of_routes(route_ids)
        units = {
            str(unit.id): unit
            for unit in models.Unit.objects.filter(
                tenant_id=tenant_id,
                id__in=[row["unit_id"] for rows in derived.values() for row in rows],
            ).select_related("premises")
        }
        self.members: dict[str, list[dict[str, Any]]] = {}
        for route_id_key, rows in derived.items():
            served = [
                {
                    "unit_id": row["unit_id"],
                    "unit_label": units[row["unit_id"]].label,
                    "premises_id": str(units[row["unit_id"]].premises_id),
                    "premise_no": units[row["unit_id"]].premises.premise_no,
                    "walk_order": row.get("walk_order"),
                }
                for row in rows
                if row["unit_id"] in units
            ]
            served.sort(
                key=lambda row: (
                    row["walk_order"] is None,
                    row["walk_order"] if row["walk_order"] is not None else 0,
                    row["unit_label"] or "",
                    row["unit_id"],
                )
            )
            self.members[route_id_key] = _ordered_members(served, stops.get(route_id_key, {}))
        self.exclusions: dict[str, dict[str, str | None]] = {}
        for route_id, asset_id, reason in models.RouteMeterExclusion.objects.filter(
            tenant_id=tenant_id, route_id__in=route_ids
        ).values_list("route_id", "asset_id", "reason"):
            self.exclusions.setdefault(str(route_id), {})[str(asset_id)] = reason
        self.services: dict[str, list[tuple[str, str]]] = {}
        for service in (
            models.RouteService.objects.filter(tenant_id=tenant_id, route_id__in=route_ids)
            .select_related("service")
            .order_by("service__code", "id")
        ):
            self.services.setdefault(str(service.route_id), []).append(
                (service.service.code, str(service.service_id))
            )
        unit_ids = [member["unit_id"] for members in self.members.values() for member in members]
        self.asset_counts: dict[str, int] = seams.asset_counts_for_units(unit_ids)
        # MQ-033 (PO 2026-10-24) — the page's readers, named in ONE read.
        self.reader_names: dict[str, str] = seams.user_display_names(reader_ids)

    def members_of(self, route_id: Any) -> list[dict[str, Any]]:
        return self.members.get(str(route_id), [])

    def exclusions_of(self, route_id: Any) -> dict[str, str | None]:
        return self.exclusions.get(str(route_id), {})

    def service_codes_of(self, route_id: Any) -> list[str]:
        return [code for code, _ in self.services.get(str(route_id), [])]

    def service_ids_of(self, route_id: Any) -> list[str]:
        return [service_id for _, service_id in self.services.get(str(route_id), [])]


def route_dict(row: models.Route, *, batch: "RouteBatch | None" = None) -> dict[str, Any]:
    """One route, as every reader of a route sees it.

    ⚠ **`batch` IS CR-029 D7's ANSWER TO THE N+1 AND CHANGES NOTHING ELSE.**
    Every fact below is the same fact; the batch merely supplies it from one
    query over the whole page instead of one query per member unit. Passing
    `None` keeps the per-row reads a single-row caller wants, so the two paths
    cannot drift into two answers (`_route_batch` builds the maps with the SAME
    orderings the per-row selectors use).
    """
    members = batch.members_of(row.id) if batch is not None else route_members(row.id)
    member_count = len(members)
    # ⚠ **THE PER-ROW BRANCH IS BATCHED TOO (`CR-131-BRC07` step 7).** `D7`
    # removed this N+1 from the LIST path and left it standing on the single-row
    # path, where nothing pages and nobody looks — so `create_route` and
    # `update_route` still asked the assets seam once per member unit. Measured
    # on a 726-unit property, which is the size the Product Owner reported:
    # **4,420 queries and 10.4 seconds for ONE save**, of which 4,354 were this
    # line and its twin in `cycle_dict` calling `assets_on_unit` 1,452 times.
    # Batched, the same save is **68 queries and 0.5 seconds**.
    #
    # `asset_counts_for_units` is the same fact in ONE query and has existed
    # since `D7`; both branches now use it, so they cannot drift into two
    # answers — which is why `batch` shares its maps with the per-row
    # selectors in the first place.
    asset_counts = (
        batch.asset_counts
        if batch is not None
        else seams.asset_counts_for_units([m["unit_id"] for m in members])
    )
    meters_available = sum(asset_counts.get(m["unit_id"], 0) for m in members)
    exclusion_reasons = (
        batch.exclusions_of(row.id) if batch is not None else route_exclusion_reasons(row.id)
    )
    excluded = sorted(exclusion_reasons)
    # BR-MET-075: the count the landing table shows is meters ON THE ROUTE —
    # available minus exclusions. Both halves travel so the wizard can say
    # "151 of 153" and an exclusion is never invisible.
    meters = max(0, meters_available - len(excluded))
    collected = seams.collected_read_count(route_id=row.id)
    # DEF-217: bound here so the dict below can serialize it. See the note there.
    last_completion = seams.last_read_completion(row.id)
    premises_ids = {m["premises_id"] for m in members}
    reader_names = (
        batch.reader_names
        if batch is not None
        else seams.user_display_names([row.assigned_to_id] if row.assigned_to_id else [])
    )
    return {
        "id": str(row.id),
        "code": row.code,
        "name": row.name,
        "route_type": row.route_type,
        "feeder_ref": row.feeder_ref,
        # CR-006 / BR-MET-073 — the transitional HEAD. Still served under its
        # shipped names because S8's landing table and every wizard read them;
        # CR-029 D10's SET rides beside it, and RC-W5 retires the pair.
        "service_id": str(row.service_id) if row.service_id else None,
        "service_code": row.service.code if row.service_id else None,
        # CR-029 D10 — *"yes it will be multi service"*. RT-001 is
        # "Water + Electric", and this is the field that sentence is true of.
        # Sorted by code so a route renders the same way on every request.
        "services": (
            batch.service_codes_of(row.id) if batch is not None else route_service_codes(row.id)
        ),
        "service_ids": (
            batch.service_ids_of(row.id) if batch is not None else route_service_ids(row.id)
        ),
        "area_id": str(row.area_id) if row.area_id else None,
        "area_code": row.area.code if row.area_id else None,
        "area_name": row.area.name if row.area_id else None,
        "notes": row.notes,
        # CR-161-BRC10 W4 — the utility's own answers: pre-filled on the route
        # wizard (`ROUTE_FORM`) and shown on the route page (`ROUTE_PAGE`).
        "custom_data": dict(row.custom_data or {}),
        # BR-MET-075 — both halves, always.
        "meters_available": meters_available,
        "meters_excluded": len(excluded),
        "excluded_asset_ids": excluded,
        # CR-029 (B17 §6) — **the two words, beside the id they explain.**
        # `excluded_asset_ids` above says WHICH meters are off the route and can
        # never say why; SET-06D renders *"MTR-W2262 excluded · premise
        # demolished"* in place. A null reason is served as null: an exclusion
        # made before the column has none, and inventing one is worse.
        "exclusions": [
            {"asset_id": asset_id, "reason": exclusion_reasons[asset_id]} for asset_id in excluded
        ],
        # CR-006 SET-05 "Members (premises+units count)".
        "premises": len(premises_ids),
        "units": member_count,
        # US-MET-005 §5: NULL assignee renders "System (auto-pull)".
        "assigned_to": str(row.assigned_to_id) if row.assigned_to_id else None,
        # MQ-033 (PO 2026-10-24) — the READER, by name, for Reads → cycle →
        # Routes; the id rides only as the dialog's anchor (B14 rule 31).
        # Settings → Routes stays reader-free and renders none of it.
        "reader": (
            {
                "id": str(row.assigned_to_id),
                "name": reader_names.get(str(row.assigned_to_id), ""),
            }
            if row.assigned_to_id
            else None
        ),
        "cycle_id": str(row.cycle_id) if row.cycle_id else None,
        "cycle_code": row.cycle.code if row.cycle_id else None,
        "status": row.status,
        "members": member_count,
        "meters": meters,
        # BR-MET-011: derived from committed reads; null while the W2 reads
        # lane is unwired — never a fabricated 0.
        "collected": collected,
        # ⚠ ISO STRING, NEVER THE RAW `datetime` (DEF-217). The seam returns
        # `read_at` straight from the ORM, and this dict is not only the API
        # shape — `services.create_route`/`update_route` put the WHOLE of it in
        # the audit row's JSON. psycopg will not adapt a datetime there, so
        # `POST /routes` answered **HTTP 500** for any premises that had ever
        # been read, and the screen said "Nothing was saved."
        #
        # It survived 26 new backend tests and a 650-case selection because no
        # fixture puts a premises WITH READS on a route — and on the demo tenant
        # exactly one premises of nine has reading history, which is why it was
        # nearly invisible here and would have been unmissable on a live
        # utility, where every premises has been read.
        #
        # Every other value in this dict is already a primitive (`str(...)` on
        # the ids); this one was the exception.
        "last_completion": (last_completion.isoformat() if last_completion is not None else None),
        "progress": (None if collected is None or not meters else round(collected * 100 / meters)),
    }


def route_row(route_id: Any) -> models.Route:
    if not _is_uuid(route_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    row = (
        models.Route.objects.filter(tenant_id=_tenant_id(), pk=route_id)
        .select_related("cycle", "service", "area")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def route_detail(route_id: Any) -> dict[str, Any]:
    from apps.metering import walk_order

    row = route_row(route_id)
    return {
        # D7 — a batch of ONE. A route with 300 members cost 600 asset-seam
        # queries to draw its own detail page; the batch is five reads whether
        # the page holds one route or fifty.
        **route_dict(row, batch=RouteBatch([row])),
        "membership": route_members(row.id),
        # CR-029 D11 — **the ruled grain, read back.** `membership.walk_order`
        # is the superseded per-unit column and orders the rows; this is the
        # stop list itself, one entry per premises, which is what the Premises
        # tab numbers and the route sheet prints.
        "premises_order": walk_order.premises_order_for_route(row.id),
    }


def route_accounts(route_id: Any) -> dict[str, Any]:
    """SET-06D's Accounts tab — *"whose accounts does a missed read here hit"*.

    ⚠ **STATUS ONLY (D12, *"not required"*)** — the screenshot's Balance column
    is not built and no money reaches this payload (BR-MET-078, hardened by
    this CR). What a staff member needs from this tab is who to warn, not what
    they owe; the balance lives on the account.

    Read through the reviewed customers seam in ONE batched call for the whole
    route (D7), not `GET /accounts?unit_id=` once per unit — which is why the
    tab had no endpoint at all before this wave.

    A unit with no occupying account is REPORTED as its own count rather than
    dropped: on a route where half the units are empty, "12 accounts" beside 30
    units is a fact a reader needs.
    """
    row = route_row(route_id)
    members = route_members(row.id)
    accounts = seams.accounts_for_units([member["unit_id"] for member in members])
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for member in members:
        account = accounts.get(member["unit_id"])
        if account is None or str(account.get("id")) in seen:
            continue
        seen.add(str(account["id"]))
        rows.append(
            {
                "account_id": str(account["id"]),
                "account_no": account.get("account_no"),
                "customer_name": account.get("customer_name"),
                "status": account.get("status"),
                "unit_id": member["unit_id"],
                "unit_label": member["unit_label"],
                "premises_id": member["premises_id"],
                "premise_no": member["premise_no"],
            }
        )
    return {
        "accounts": rows,
        "total": len(rows),
        "units": len(members),
        "units_without_account": sum(
            1 for member in members if accounts.get(member["unit_id"]) is None
        ),
    }


def routes_queryset(*, q: str | None = None, filters: dict[str, Any] | None = None) -> QuerySet:
    """The filtered route rows, unserialized — the half `routes_page` sorts and
    slices BEFORE any derivation runs (D7)."""
    qs = models.Route.objects.filter(tenant_id=_tenant_id()).select_related(
        "cycle", "service", "area"
    )
    filters = filters or {}
    if term := (q or "").strip():
        if len(term) >= 2:
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
    if cycle := filters.get("cycle"):
        qs = qs.filter(Q(cycle__code__iexact=str(cycle)) | Q(cycle_id=str(cycle)))
    # ⚠ **`on_cycle` IS *ANY* CYCLE, WHICH `cycle` CANNOT ASK** (`DEF-MET-5743`).
    # SET-07 step 2's one filter chip is *"already on a cycle"* — the question
    # that step asks, because picking such a route MOVES it (BR-MET-034). It was
    # answered in the browser over an array holding every route in the tenant;
    # with the picker paged, a chip that filtered the PAGE would report "no
    # routes are on a cycle" whenever this page happened to hold none.
    on_cycle = filters.get("on_cycle")
    if on_cycle not in (None, ""):
        qs = qs.filter(cycle_id__isnull=str(on_cycle) not in ("1", "true", "yes"))
    if route_type := filters.get("type"):
        qs = qs.filter(route_type=str(route_type))
    if status := filters.get("status"):
        qs = qs.filter(status=str(status))
    if service := filters.get("service"):  # CR-006 / BR-MET-073
        qs = qs.filter(service__code__iexact=str(service))
    if area := filters.get("area"):  # BR-MET-072 — multi-select, OR-combined
        qs = qs.filter(_area_predicate(area))
    return qs.order_by("code", "id")


def routes_list(
    *, q: str | None = None, filters: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    rows = list(routes_queryset(q=q, filters=filters))
    return [route_dict(row, batch=RouteBatch(rows)) for row in rows]


#: CR-029 D7 / BR-SHL-011 — the sort vocabulary SET-05's Routes table declares.
#: ⚠ EVERY KEY IS A COLUMN THE SCREEN MARKS `sortable`, and the two DERIVED
#: ones are here on purpose: `members` and `meters` are counts, so they are
#: sorted from the batch after it is built, never from a column that does not
#: exist. A key outside this map falls back to the default (never an error).
ROUTE_SORTS = {
    "code": "code",
    "name": "name",
    "route_type": "route_type",
    "area_code": "area__code",
    "cycle_code": "cycle__code",
    "status": "status",
    "members": None,  # derived — sorted on the built page
    "meters": None,  # derived — BR-MET-075, available minus exclusions
}
ROUTE_DEFAULT_SORT = "code"


def routes_page(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> list[dict[str, Any]]:
    """The routes list, SORTED server-side and batched (D7 — *"Yes - please do
    it"*).

    ⚠ **THE ROWS ARE BUILT ONCE FOR THE WHOLE FILTERED SET AND THAT IS WHAT
    MAKES THE DERIVED SORTS HONEST.** `members` and `meters` are counts, not
    columns: a `LIMIT` applied before they exist would page a different order
    than the one the header claims. With the batch that costs a constant five
    queries for the tenant's routes, so the correct answer is also the cheap
    one; the paginator slices the sorted list.
    """
    key = sort if sort in ROUTE_SORTS else ROUTE_DEFAULT_SORT
    column = ROUTE_SORTS[key]
    qs = routes_queryset(q=q, filters=filters)
    if column is not None:
        qs = qs.order_by(column, "code", "id")
    rows = list(qs)
    batch = RouteBatch(rows)
    served = [route_dict(row, batch=batch) for row in rows]
    if column is None:
        served.sort(key=lambda served_row: (served_row[key], served_row["code"]))
    if direction == "desc":
        served.reverse()
    return served


def _area_ids_for(selection: Any) -> list[str]:
    """BR-MET-072 — the area rows a filter selection covers.

    **A PARENT MATCHES ITS SUB-AREAS.** Picking "South" must return the
    premises in "South · SE" and "South · SW" as well as the ones tagged to
    South itself, because a utility that has divided South into two halves
    still thinks of it as South. Picking a sub-area matches only that one.

    Accepts one value or many, codes or ids; the values OR together
    (*"all option 1 to many options will be required"*). An EMPTY selection
    returns an empty list, which the caller reads as "no area filter" — and
    that is the All chip, which must also return premises with NO area, since
    a filter that hid untagged premises would hide exactly the rows a utility
    is trying to find and tag.
    """
    from apps.tenancy import models as tenancy_models

    values = selection if isinstance(selection, (list, tuple, set)) else [selection]
    wanted = [str(value).strip() for value in values if str(value or "").strip()]
    if not wanted:
        return []
    qs = tenancy_models.Area.objects.filter(tenant_id=_tenant_id())
    lowered = {value.lower() for value in wanted}
    # Codes are matched case-insensitively (BR-TEN-030's own convention) and
    # ids exactly. Done in Python over a per-tenant list of at most a few dozen
    # rows rather than as an OR of N `iexact` clauses, which is the same answer
    # with a query that grows with the chip count.
    picked = [row for row in qs if row.code.lower() in lowered or str(row.pk) in wanted]
    ids = {str(row.pk) for row in picked}
    # …plus every sub-area of a picked top-level area.
    for child in qs.filter(parent_id__in=[row.pk for row in picked]):
        ids.add(str(child.pk))
    return sorted(ids)


def _area_predicate(selection: Any, field: str = "area_id") -> Q:
    """BR-MET-072 as a queryset filter.

    ⚠ **"NOBODY PICKED AN AREA" AND "SOMEBODY PICKED ONE THAT DOES NOT EXIST"
    ARE DIFFERENT ANSWERS, AND THIS RETURNED THE SAME `Q()` FOR BOTH UNTIL
    2026-08-27 (DEF-836, second half).** An EMPTY selection is the All chip and
    correctly matches everything. A NON-EMPTY selection that resolves to no
    rows — a renamed code, a deleted district, a bookmarked URL carrying last
    month's chip, a typo — is a filter the caller ASKED FOR and cannot honour,
    and answering it with the whole tenant is the worst of the three possible
    answers: it looks like the filter worked. Found by a test asserting that an
    unknown code returns nothing; it returned all 70 premises.

    `pk__in=[]` is the never-matching predicate rather than a raised error,
    because a stale chip is an ordinary thing for a URL to carry and an empty
    list is what the screen can render (*"no premises match"*), which is the
    truth.
    """
    ids = _area_ids_for(selection)
    if ids:
        return Q(**{f"{field}__in": ids})
    values = selection if isinstance(selection, (list, tuple, set)) else [selection]
    asked = [str(value).strip() for value in values if str(value or "").strip()]
    return Q(pk__in=[]) if asked else Q()


#: CR-029 RC-W2-T2 — what a screen SAYS about a cycle whose windows COLLIDE.
#:
#: ⚠ **THIS USED TO BE `_SCHEDULE_GAP_DETAIL`, THREE SENTENCES FOR THREE
#: SILENCES, AND THE PO CLOSED ALL THREE ON 2026-08-23.** OQ-339 (the month-end
#: anchor) clamps, OQ-340 (a first run off its start day) anchors on the first
#: run, and OQ-341 (windows longer than the repeat) OVERLAPS — so no cycle
#: refuses to propose its windows any more and no gap sentence can be reached.
#: They are deleted rather than left unreachable (hard-won law 1).
#:
#: What replaces them is ONE sentence, and it is a WARNING beside real windows
#: rather than an absence instead of them: OQ-341 verbatim, *"you give warning
#: and if user override; let them do it"*. **No internal provenance** (G28) —
#: the OQ id lives here in the comment, never in served copy.
_SCHEDULE_WARNING_DETAIL: dict[str, str] = {
    period_engine.WARN_WINDOWS_OVERLAP: (
        "This cycle takes longer to complete than the gap between its readings, so the "
        "next window opens before this one finishes. The windows below overlap."
    ),
}

#: How many windows a cycle offers. THREE, because the upgraded prototype's
#: SET-07D Schedule tab draws *"Next three windows"* and the wizard's step 3
#: preview shows the same three.
PROPOSED_WINDOW_COUNT = 3


def _schedule_proposal(row: models.Cycle, as_of: date) -> dict[str, Any]:
    """CR-029 D1 — the cycle's next windows, derived on demand.

    ⚠ **IT USED TO RENDER A REFUSAL AND THERE IS NOTHING LEFT TO REFUSE.** Three
    silences reached this function — a start day some months do not have, a first
    run off its start day, and windows longer than the cycle's own repeat — and
    each returned no window and a stated gap rather than answering an open
    question by call site. The PO ruled all three on 2026-08-23 (OQ-339 ·
    OQ-340 · OQ-341), so every cycle a human can save now proposes its windows.

    THREE THINGS THE PAYLOAD GAINED WITH THOSE RULINGS:

      `effective_start_day` — OQ-340 made the first run the anchor, which can
          leave the stored `start_day` describing nothing. The screens must show
          what the cycle DOES, so the effective day is served with `differs`
          saying when the stored one is decorative. **The column is not
          rewritten** — that is the operator's value.
      `schedule_warning`    — OQ-341's collision, named. A warning beside real
          windows, never instead of them.
      `schedule_gap`        — kept on the payload, always `None`. The key is
          part of a contract three screens already read, and removing it would
          break them for no gain; what it can no longer be is a sentence.

    It still does not let an exception escape: a cycle a human saved is a cycle
    the Cycles page has to draw, so an unknown frequency word (a hand-written
    row) yields no windows rather than a 500 (BR-REP-024's posture).
    """
    warning = period_engine.overlap_warning(
        frequency=row.frequency, days_to_complete=row.days_to_complete
    )
    anchor = period_engine.effective_start_day(
        frequency=row.frequency, start_day=row.start_day, first_run=row.first_run_date
    )
    base: dict[str, Any] = {
        "effective_start_day": anchor["effective_start_day"],
        "start_day_differs": anchor["differs"],
        "schedule_gap": None,
        "schedule_warning": (
            None
            if warning is None
            else {**warning, "detail": _SCHEDULE_WARNING_DETAIL[warning["code"]]}
        ),
    }
    empty: dict[str, Any] = {
        **base,
        "proposed_windows": [],
        "next_period": None,
        "next_cycle_date": None,
    }
    try:
        windows = period_engine.upcoming_windows(
            frequency=row.frequency,
            start_day=row.start_day,
            days_to_complete=row.days_to_complete,
            first_run=row.first_run_date,
            as_of=as_of,
            count=PROPOSED_WINDOW_COUNT,
        )
        next_date = period_engine.next_cycle_date(
            frequency=row.frequency,
            start_day=row.start_day,
            days_to_complete=row.days_to_complete,
            first_run=row.first_run_date,
            as_of=as_of,
        )
    except ValueError:
        # A frequency this vocabulary does not hold (a hand-written row, or one
        # from before CR-006's three words were mapped). Nothing is proposed and
        # nothing is claimed; the frequency itself is already on the payload for
        # a human to correct.
        return empty
    if not windows:
        return empty
    return {
        **base,
        "proposed_windows": [
            {
                "period_start": window.period_start.isoformat(),
                "period_end": window.period_end.isoformat(),
                "status": window.status,
                "occurrence": window.occurrence,
            }
            for window in windows
        ],
        "next_period": {
            "period_start": windows[0].period_start.isoformat(),
            "period_end": windows[0].period_end.isoformat(),
        },
        "next_cycle_date": next_date.isoformat() if next_date else None,
    }


class CycleBatch:
    """CR-029 D7 — a page of cycles' derivations, without the per-row cascade.

    A cycle's counts run cycle → routes → memberships → units → (assets,
    accounts), and `cycle_dict` walked all four PER CYCLE: the routes in one
    query, then the assets seam once per member unit, then the accounts seam
    once per unit in the cycle's service points. `GET /cycles` on a tenant with
    ten cycles paid it ten times over.

    Everything here is the same fact from the same tables — the route half is
    literally `RouteBatch`, so a cycle's expected-meter count and its routes'
    own meter counts cannot disagree.
    """

    def __init__(self, rows: list[models.Cycle]) -> None:
        cycle_ids = [row.id for row in rows]
        tenant_id = _tenant_id()
        self.routes: dict[str, list[models.Route]] = {}
        route_rows = list(
            models.Route.objects.filter(tenant_id=tenant_id, cycle_id__in=cycle_ids).order_by(
                "code", "id"
            )
        )
        for route in route_rows:
            self.routes.setdefault(str(route.cycle_id), []).append(route)
        self.route_batch = RouteBatch(route_rows)
        # The cycle's ACCOUNTS, through the DERIVED membership `cycle_account_
        # count` documents (CR-029 D4/D13) — read off the route batch that has
        # already resolved it, so the page costs no extra query and the two
        # numbers cannot disagree. A DRAFT cycle contributes nothing
        # (BR-MET-076), which is the same silence the stamp gave it.
        from apps.metering import derivation

        draft_cycles = {str(row.id) for row in rows if row.status == "draft"}
        units_by_cycle: dict[str, set[str]] = {}
        for route in route_rows:
            cycle_key = str(route.cycle_id)
            if cycle_key in draft_cycles:
                continue
            units_by_cycle.setdefault(cycle_key, set()).update(
                member["unit_id"] for member in self.route_batch.members_of(route.id)
            )
        # …and the units whose service point names the cycle and NO route, which
        # `units_in_cycle` counts for the same reason (see
        # `derivation.directly_stamped_units`) — otherwise the page's Accounts
        # column and the bill run's own population would disagree.
        for cycle_key, units in derivation.directly_stamped_units(
            [row.id for row in rows if row.status != "draft"]
        ).items():
            units_by_cycle.setdefault(cycle_key, set()).update(units)
        # `DEF-MET-8732` — the ids only: this is a COUNT, and the full
        # `accounts_for_units` row (a model, three joins, every contact's name)
        # was 18.5 s of a 21 s `GET /cycles` at 40,000 accounts.
        accounts = seams.account_ids_for_units(
            {unit_id for units in units_by_cycle.values() for unit_id in units}
        )
        self.account_counts: dict[str, int] = {
            cycle_id: len({accounts[str(u)] for u in units if accounts.get(str(u))})
            for cycle_id, units in units_by_cycle.items()
        }

    def routes_of(self, cycle_id: Any) -> list[models.Route]:
        return self.routes.get(str(cycle_id), [])

    def expected_of(self, cycle_id: Any) -> int:
        return sum(
            self.route_batch.asset_counts.get(member["unit_id"], 0)
            for route in self.routes_of(cycle_id)
            for member in self.route_batch.members_of(route.id)
        )

    def accounts_of(self, cycle_id: Any) -> int:
        return self.account_counts.get(str(cycle_id), 0)


def _default_bill_date(bill_day: int | None, next_period: dict[str, Any] | None) -> date | None:
    """OQ-344's rule, for the cycle's own NEXT period: the bill day, in the
    month AFTER that period ends.

    **PO ruling 2026-08-23, verbatim:** *"I'd say B - these are defualt - user
    can override"*. Worked, and it is the figure the ruling was put on: bill day
    5, a period ending 31 August → **5 September** (and with 21 due-days, due
    26 September).

    ⚠ **THE DAY CLAMPS TO THE MONTH'S LAST DAY** — OQ-339, ruled the same day:
    *"there is no 31st feb so we have to manage either 28th or 29th of Feb."*
    Through `schedule.clamp_day_to_month`, which is the one place that
    arithmetic lives in this module.

    `None` when the cycle has no bill day or no next period. A cycle nobody has
    scheduled has no next bill date, and inventing one would put a date on a
    settings screen that no run would ever produce.
    """
    if bill_day is None or not next_period:
        return None
    try:
        period_end = date.fromisoformat(str(next_period["period_end"]))
    except (KeyError, TypeError, ValueError):
        return None
    total = period_end.year * 12 + period_end.month  # one month past period end
    year, month = divmod(total, 12)
    month += 1
    return date(year, month, schedule.clamp_day_to_month(year, month, bill_day))


def cycle_dict(
    row: models.Cycle, *, as_of: date | None = None, batch: "CycleBatch | None" = None
) -> dict[str, Any]:
    """One cycle, as every reader of a cycle sees it.

    ⚠ **CR-029 D2 — THE READ WINDOW IS DERIVED. FULL STOP (W5-T2).** This is
    where gap G2 died. `window_start`/`window_end` were the legacy DATE pair
    from the 2026-08-08 modal; SET-07 stopped writing them, so a cycle created
    through the wizard served two nulls — and the bill-run picker
    (`BillRunWizard.tsx` reads exactly these two keys), the S27 ops tab and the
    cycles export each rendered an em-dash for a cycle with a perfectly
    well-defined window.

    W1 answered it with *stored wins while it exists, derived otherwise*, and
    published `read_window_source` so no screen had to guess. **metering 0021
    dropped the columns**, so there is nothing left to prefer: the window is
    always `start_day` + `days_to_complete` — *"start day + N days IS the read
    window"* (B17 §2) — and `read_window_source` answers `"derived"` or `None`.
    The key STAYS rather than being removed with the branch: a screen that shows
    a window is entitled to say where it came from, and a third source (the
    period engine's own occurrence) is what RC-W2 already produces beside it.

    `as_of` anchors the derived window's MONTH and defaults to the tenant's own
    today (`seams.tenant_today`, BR-TEN-081). ⚠ That placement is a LANE
    JUDGMENT — no ruling says which occurrence S27 renders — and RC-W2's period
    engine replaces it with the true per-frequency period. It is an argument so
    the engine can pass its own.
    """
    routes = (
        batch.routes_of(row.id)
        if batch is not None
        else list(
            models.Route.objects.filter(tenant_id=row.tenant_id, cycle=row).order_by("code", "id")
        )
    )
    # D7 — the same sums, from one batched read when a page supplies one.
    # ⚠ Batched on BOTH branches — `route_dict`'s note above, same measurement.
    expected = batch.expected_of(row.id) if batch is not None else _expected_meters(routes)
    collected = seams.collected_read_count(cycle_id=row.id)
    accounts = batch.accounts_of(row.id) if batch is not None else cycle_account_count(row.id)
    # ONE clock read for this row, not one per fact. Two `tenant_today()` calls
    # in one payload can straddle midnight and put a proposal from tomorrow
    # beside a window from yesterday — the same reason `cycles_list` reads it
    # once for the whole page (RC-W1's D2 follow-up).
    anchor = as_of or seams.tenant_today()
    # CR-029 D1 / RC-W2-T2 — the run wizard OFFERS: the next windows the cycle
    # proposes, computed on demand from its own three fields. Nothing is stored
    # and nothing can go stale.
    proposal = _schedule_proposal(row, anchor)
    # CR-029 D2 — the window, derived, computed once for the three keys below.
    # ⚠ THE ONE READ WINDOW (`DEF-MET-10588`, MQ-033 2026-10-24): the EFFECTIVE
    # start day, the one `effective_start_day` above serves to Settings — this
    # read the stored day and printed CY-001 as 10/10–10/14 beside Settings' 14–18.
    derived_window = period_engine.cycle_read_window(row, anchor)
    if derived_window is not None:
        window_start, window_end = derived_window
        window_source: str | None = "derived"
    else:
        window_start, window_end = None, None
        window_source = None
    # CR-029 OQ-344 — the cycle's DEFAULT bill date, derived from its bill DAY
    # and the period its next window covers (see the two keys below for why the
    # next window is the period this read chooses). `metering` owns the
    # arithmetic here rather than calling billing's `runs.default_bill_date`,
    # because the dependency runs the other way (B1 / gate G6: billing reads
    # metering, never the reverse). What the two share is the PO's sentence,
    # quoted at both, and the same worked figure in both test files.
    derived_bill_date = _default_bill_date(row.bill_day, proposal.get("next_period"))
    return {
        "id": str(row.id),
        "code": row.code,
        # CR-006 / BR-MET-077 — the DEFINITION's own fields.
        "name": row.name,
        "frequency": row.frequency,
        # CR-029 / B17 §2 — the three fields about time. `start_day` and
        # `days_to_complete` are the SOURCE; the window below is derived.
        "start_day": row.start_day,
        "days_to_complete": row.days_to_complete,
        "read_window_source": window_source,
        "first_run_date": row.first_run_date.isoformat() if row.first_run_date else None,
        # CR-029 D1 — THE PROPOSAL. `proposed_windows` carries the upgraded
        # prototype's own Next/Scheduled statuses, `next_period` is what the run
        # wizard prefills (editable — it offers, never forces), `next_cycle_date`
        # is D8②'s countdown target, and `schedule_gap` states the silence when
        # the cycle's next window is not ruled. All four DERIVE; none is stored.
        **proposal,
        # ⚠ **ONE DAY-OF-MONTH DEFAULT, NOT FOUR (W5-T2).** `read_day_from` /
        # `read_day_to` / `due_day` were served here and their columns are
        # gone (metering 0021); serving them as permanent nulls would be dead
        # payload a screen renders as an em-dash forever (hard-won law 2).
        # `bill_day` survives because D9 keeps it: *"when we configure Cycle we
        # are provideing default values … user can over ride them during
        # billing"*.
        "bill_day": row.bill_day,
        # CR-006 SET-05 "Accounts" column — a real count, not a label.
        "accounts": accounts,
        "route_ids": [str(route.id) for route in routes],
        "routes": [route.code for route in routes],
        # ⚠ THE CONTRACTED KEYS ARE UNCHANGED AND THEIR SOURCE HAS MOVED. Every
        # consumer — the run picker, S27, the export — keeps reading these two;
        # what changed is that they are DERIVED for every cycle now, and that a
        # wizard-created cycle has an answer at all.
        "window_start": window_start.isoformat() if window_start else None,
        "window_end": window_end.isoformat() if window_end else None,
        # ⚠ **THE LAST DEPRECATED COLUMN IS GONE AND THESE TWO KEYS ARE NOW
        # DERIVED (RC-W6, metering 0023).** `bill_date` was a stored calendar
        # date W5-T2 could not drop, because billing read it as the fallback for
        # a run with no typed bill date and nothing ruled what replaced it.
        # OQ-344 ruled it on 2026-08-23 — PO verbatim *"I'd say B - these are
        # defualt - user can override"* — so the answer is **the cycle's bill
        # day, in the month AFTER the period ends**.
        #
        # The keys STAY on the payload and change source, exactly as
        # `window_start`/`window_end` did in W1-T2: serving them as permanent
        # nulls would be an em-dash on a screen forever (hard-won law 2).
        #
        # ⚠ **WHICH PERIOD** is this read's own choice, and it is stated rather
        # than hidden: the cycle's NEXT proposed window, so the screen answers
        # *"when does this cycle bill next"*. The ruling fixes the RULE (the
        # month after a period ends) and names no particular period, because a
        # RUN always has one; a cycle on its own does not. A cycle with no
        # schedule yet has no next period and both keys are null — which is a
        # fact, not a gap.
        "bill_date": derived_bill_date.isoformat() if derived_bill_date else None,
        "due_days": row.due_days,
        # US-MET-006 §7: due date is date math consumed by billing — no money.
        "due_date": (
            (derived_bill_date + timedelta(days=row.due_days)).isoformat()
            if derived_bill_date and row.due_days is not None
            else None
        ),
        "expected": expected,
        "collected": collected,
        "progress": (
            None if collected is None or not expected else round(collected * 100 / expected)
        ),
        # BR-MET-011: "Billed" derives from the bill run (billing, read-only).
        #
        # ⚠ TWO DIFFERENT FACTS ARE BOTH CALLED "STATUS" AND THEY ARE KEPT
        # APART DELIBERATELY. `status` here has ALWAYS been the OPERATIONAL
        # progress of the current period — scheduled / in progress / billed —
        # and S27 renders it. CR-006 adds a stored LIFECYCLE (draft / active /
        # inactive, BR-MET-076), which is a different question about a
        # different thing. Overloading one key would have silently changed
        # what S27 draws the day this shipped, so the new fact gets a new
        # name and the old contract is untouched.
        "status": "scheduled" if collected in (None, 0) else "in_progress",
        "lifecycle_status": row.status,
    }


def cycle_row(cycle_id: Any) -> models.Cycle:
    """This tenant's cycle, or ABSENT — `route_row`'s twin (hard rule 1)."""
    if not _is_uuid(cycle_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    row = models.Cycle.objects.filter(tenant_id=_tenant_id(), pk=cycle_id).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def cycle_detail(cycle_id: Any) -> dict[str, Any]:
    """`GET /cycles/{id}` — SET-07D's own read.

    ⚠ **THE ID ROUTE WAS PATCH+DELETE ONLY**, so the cycle detail screen and
    its editor each fetched the WHOLE list and picked their row out of it —
    every cycle's routes, accounts and proposed windows computed to render one.
    The shape is deliberately `cycle_dict` unchanged: the screen already types
    the list row, so the day it calls this it renders with nothing else edited.

    That includes the SCHEDULE PROPOSAL (`proposed_windows`, `next_period`,
    `next_cycle_date`, `schedule_gap`) — RC-W2's period engine, reached through
    the payload the detail already reads rather than a second endpoint.
    """
    row = cycle_row(cycle_id)
    return cycle_dict(row, batch=CycleBatch([row]))  # D7 — a batch of one


def cycle_account_count(cycle_id: Any) -> int:
    """CR-006 SET-05 "Accounts" — how many accounts bill on this cycle.

    ⚠ **DERIVED (CR-029 D13, PO *"Cycles are not directlya ssing to accounts it
    is derived and determined at the time of bill run"*).** The chain is walked
    live — account → unit → route → cycle — through the same resolution the bill
    run scopes on, so this number and the run's population cannot disagree. It
    was counted off `service_points.cycle_id`, which is the stamp, and a stamp
    is a snapshot. A DRAFT cycle answers 0 (BR-MET-076) — the true answer for a
    cycle that has never run, not a missing one.

    The per-unit `active_account_for_unit` is gone with it: the seam takes the
    whole cycle at once (D7).
    """
    from apps.metering import derivation

    return len(derivation.accounts_in_cycle(cycle_id))


#: How many uncovered accounts SET-07D's Coverage tab LISTS. The KPI above the
#: list is the true total either way; this bounds one screen's table, and 200 is
#: four of this product's own 50-row pages.
UNCOVERED_ROW_LIMIT = 200


def uncovered_account_count(
    extra_route_ids: list[str] | None = None, *, limit: int = UNCOVERED_ROW_LIMIT
) -> dict[str, Any]:
    """BR-MET-080 — *"flag any active account NOT covered by any cycle
    ('47 accounts unscheduled')"*. A real query, not a label.

    An account is COVERED when one of its units is reached by a cycle.
    `extra_route_ids` is the set the wizard has just selected but not yet saved:
    their units count as covered, because the figure a staff member needs on
    step 3 is **"what will still be unscheduled after I press create"**, not
    "what is unscheduled now" — the second number would say 47 on a screen that
    is about to fix 47.

    ⚠ **COVERAGE READS LIVE (CR-029 D4 / B17 §7 W4-T5).** It read
    `service_points.cycle_id`, so a building tagged into a routed area this
    morning still counted as uncovered this afternoon — the same snapshot
    DEF-225 is about, on the screen that exists to report it. The question is
    now asked of the tags, so tagging a premises fixes the number with no route
    edited and no membership written.
    """
    from apps.metering import derivation

    tenant_id = _tenant_id()
    covered_units = derivation.covered_unit_ids(list(extra_route_ids or []))

    # D7 — one batched read for every uncovered unit, not one per unit.
    open_units = [
        unit
        for unit in models.Unit.objects.filter(
            tenant_id=tenant_id, deleted_at__isnull=True
        ).select_related("premises")
        if str(unit.id) not in covered_units
    ]
    accounts = seams.accounts_for_units([str(unit.id) for unit in open_units])
    uncovered: set[str] = set()
    rows: list[dict[str, Any]] = []
    for unit in open_units:
        account = accounts.get(str(unit.id))
        if not account or not account.get("id"):
            continue
        account_id = str(account["id"])
        if account_id in uncovered:
            continue
        uncovered.add(account_id)
        # ⚠ **D13 — WHAT THE ACCOUNT LACKS IS A ROUTE, AND THAT IS THE WHOLE
        # ROW.** The screenshot puts *"Assign a cycle →"* on every uncovered
        # line; the PO ruled *"Cycles are not directlya ssing to accounts it is
        # derived and determined at the time of bill run"*. So the row names
        # the account, where it is, and the thing that is missing — and no
        # assignment endpoint exists for the screen to call.
        rows.append(
            {
                "account_id": account_id,
                "account_no": account.get("account_no"),
                "customer_name": account.get("customer_name"),
                "status": account.get("status"),
                "unit_id": str(unit.id),
                "unit_label": unit.label,
                "premises_id": str(unit.premises_id),
                "premise_no": unit.premises.premise_no,
                "lacks": "route",
            }
        )
    rows.sort(key=lambda row: (row["account_no"] or "", row["account_id"]))
    return {
        # The COUNT is the whole set — the KPI trio must not shrink to a page.
        "uncovered_accounts": len(uncovered),
        "uncovered": rows[: max(1, limit)],
        "truncated": len(rows) > max(1, limit),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-006 · SET-06 steps 2 and 3 — the two pickers
#
# Both answer a question the shipped selectors could not: *"which premises may
# I put on this route, and what is already true of them"*. They live here
# rather than being assembled on the client because every fact in them —
# current route, unit count, meter count, area path — is a join the client
# cannot make without reading three modules' tables.
# ═══════════════════════════════════════════════════════════════════════════


#: `DEF-MET-5743` — the SORT VOCABULARY this picker can actually serve.
#:
#: ⚠ **`meters` AND `current_route` ARE DELIBERATELY ABSENT, AND THE SCREEN
#: DROPS THEIR SORT CONTROLS WITH THEM.** Both are derived from another
#: module's tables through a seam; ordering by either would mean building every
#: row in the tenant before the slice, which is the defect this function was
#: rewritten to remove. A column offering an ordering the request cannot ask
#: for is the refusal `ACCOUNT_SORTS` already carries for `last_bill`, and it
#: is the honest half of the trade: five orderings that are true at 40,000
#: premises beat seven that are only true at 3,000.
#:
#: A key outside this map falls back to the default (never an error), exactly
#: as `ROUTE_SORTS` behaves.
PREMISES_PICKER_SORTS = {
    "premise_no": "premise_no",
    "address_line": "address_line",
    "premises_type": "premises_type__name",
    "area_path": "area__name",
    "units": "unit_count",  # annotated below — a COUNT, not a Python pass
}
PREMISES_PICKER_DEFAULT_SORT = "premise_no"


def _picker_service_row(service: str | None) -> Any:
    """The `Service` a picker filter names, or None for "every service"."""
    if not service:
        return None
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Service.objects.filter(code__iexact=str(service)).first()


def _premises_already_on_another_route(service_row: Any, route_id: Any):
    """The premises ids that the `unassigned` chip HIDES, as a SUBQUERY.

    ⚠ **A SUBQUERY AND NOT A PYTHON SET, BECAUSE THE SET IS THE TENANT**
    (`DEF-MET-5743`). The predecessor read every membership in the tenant into
    a dict and then dropped rows one at a time while building them, so the
    filter could only be applied AFTER the whole list existed — which is why
    this picker could not be paged at all. Expressed here it is a `NOT IN` the
    database evaluates, so the chip narrows the queryset BEFORE the slice and
    the `count` beside the page is the true number of matching rows.
    """
    tenant_id = _tenant_id()
    memberships = models.RouteMembership.objects.filter(tenant_id=tenant_id)
    if service_row is not None:
        memberships = memberships.filter(service_id=service_row.id)
    if route_id:
        # A premises on THIS route is not "on another route" — an edit must be
        # able to see its own members.
        memberships = memberships.exclude(route_id=route_id)
    return models.Unit.objects.filter(
        tenant_id=tenant_id,
        deleted_at__isnull=True,
        id__in=memberships.values("unit_id"),
    ).values("premises_id")


def _route_premises_picker_queryset(
    *,
    q: str | None,
    areas: Any,
    service_row: Any,
    unassigned_only: bool,
    route_id: Any,
    sort: str | None,
    direction: str,
):
    """Every premises that may join this route, as a QUERYSET — nothing built.

    Filtering, the `unassigned` chip and the ordering are all expressed here so
    that the caller may slice before a single row is assembled.
    """
    tenant_id = _tenant_id()
    qs = models.Premises.objects.filter(tenant_id=tenant_id).select_related(
        "premises_type", "area", "area__parent"
    )
    if term := (q or "").strip():
        if len(term) >= 2:
            qs = qs.filter(
                Q(address_line__icontains=term)
                | Q(premise_no__icontains=term)
                | Q(city__icontains=term)
            )
    predicate = _area_predicate(areas)
    if predicate:
        qs = qs.filter(predicate)
    if unassigned_only:
        qs = qs.exclude(id__in=_premises_already_on_another_route(service_row, route_id))

    key = sort if sort in PREMISES_PICKER_SORTS else PREMISES_PICKER_DEFAULT_SORT
    column = PREMISES_PICKER_SORTS[key]
    if column == "unit_count":
        qs = qs.annotate(
            unit_count=Count("unit", filter=Q(unit__deleted_at__isnull=True), distinct=True)
        )
    prefix = "-" if str(direction).lower() == "desc" else ""
    # `premise_no`, then `id`, are the tie-breakers on every ordering, so two
    # requests for page 2 of the same list cannot answer with different rows.
    return qs.order_by(f"{prefix}{column}", "premise_no", "address_line", "id")


def _route_premises_picker_rows(
    premises_rows: list[Any], *, service_row: Any, route_id: Any
) -> list[dict[str, Any]]:
    """Build the picker's rows for ONE PAGE of premises, in a fixed number of
    queries whatever the page holds.

    ⚠ **THIS IS THE HALF `DEF-MET-5743` WAS FILED FOR.** The predecessor ran,
    per premises, one `Unit` query and then one `assets_on_unit` call per unit
    — so drawing SET-06 step 2 for a utility with 10,000 premises issued more
    than 20,000 queries and serialised every row to the browser. The facts are
    unchanged; what changed is that they are fetched in THREE reads for the
    whole page: the units, the asset counts (through `seams.asset_counts_for_
    units`, the batched seam `CR-029` D7 added for exactly this), and the
    memberships.

    ⚠ **AND IT WIDENS NOTHING (`DEF-650`, `DEF-324`).** Those two defects
    removed a per-row owner-account expansion from the premises list because it
    cost one account read and one ledger derivation per row; the answer there
    was to STOP CARRYING the fact, and nothing here starts carrying it. This
    row holds exactly the eleven keys it held before.
    """
    tenant_id = _tenant_id()
    premises_ids = [row.pk for row in premises_rows]
    if not premises_ids:
        return []

    units_by_premises: dict[Any, list[Any]] = {}
    unit_ids: list[Any] = []
    for unit in models.Unit.objects.filter(
        tenant_id=tenant_id, premises_id__in=premises_ids, deleted_at__isnull=True
    ).order_by("label", "id"):
        units_by_premises.setdefault(unit.premises_id, []).append(unit)
        unit_ids.append(unit.id)

    # ONE read for every meter count on the page (D7's seam). A unit with no
    # assignment is ABSENT from the map, which `.get(..., 0)` reads as zero.
    meter_counts = seams.asset_counts_for_units(unit_ids)

    memberships = models.RouteMembership.objects.filter(
        tenant_id=tenant_id, unit_id__in=unit_ids
    ).select_related("route")
    if service_row is not None:
        memberships = memberships.filter(service_id=service_row.id)
    # ORDERED, so "which membership wins for a unit on two routes" is the same
    # answer twice. The predecessor's dict took whatever the database happened
    # to return last.
    membership_by_unit: dict[Any, tuple[str, str]] = {}
    for membership in memberships.order_by("id"):
        membership_by_unit[membership.unit_id] = (
            membership.route.code,
            str(membership.route_id),
        )

    wanted_route = str(route_id or "")
    rows: list[dict[str, Any]] = []
    for premises in premises_rows:
        units = units_by_premises.get(premises.pk, [])
        meters = sum(meter_counts.get(str(unit.id), 0) for unit in units)
        current: tuple[str, str] | None = None
        for unit in units:
            found = membership_by_unit.get(unit.id)
            if found is not None and found[1] != wanted_route:
                current = found
                break
        area = premises.area
        rows.append(
            {
                "id": str(premises.id),
                "premise_no": premises.premise_no,
                "address_line": premises.address_line,
                "premises_type": premises.premises_type.name if premises.premises_type_id else None,
                "units": len(units),
                "unit_ids": [str(unit.id) for unit in units],
                "meters": meters,
                # r10 draws "South · SE" — the parent path, then the leaf.
                "area_code": area.code if area else None,
                "area_name": area.name if area else None,
                "area_path": (
                    f"{area.parent.name} · {area.name}"
                    if area and area.parent_id
                    else (area.name if area else None)
                ),
                # BR-MET-074: the move badge, or None.
                "current_route": current[0] if current else None,
                "current_route_id": current[1] if current else None,
                # Already on THIS route (an edit re-opening its own members).
                "on_this_route": route_id is not None
                and any(membership_by_unit.get(unit.id, ("", ""))[1] == wanted_route for unit in units),
            }
        )
    return rows


def route_premises_picker_page(
    *,
    q: str | None = None,
    areas: Any = None,
    service: str | None = None,
    unassigned_only: bool = False,
    route_id: Any = None,
    members_only: bool = False,
    sort: str | None = None,
    direction: str = "asc",
    page: int = 1,
    per: int | None = None,
) -> dict[str, Any]:
    """SET-06 step 2 — ONE PAGE of the picker, with the true total beside it.

    ⚠ **`NFR-3` ARRIVES HERE AND `NFR-5` IS NOT BROKEN GETTING IT IN.** `per`
    is what the caller asked for and there is no maximum: `per=None` returns
    every matching row, which is what the seven existing callers of
    `route_premises_picker` below still do. What this adds is the ABILITY to
    ask for a window and be told how many rows there are — the thing the
    screen needs so that a footer reading "1–50 of 9,412" is a true sentence
    rather than the length of whatever happened to arrive.

    ⚠ **`members_only` IS THE EDIT PATH AND IT IS BOUNDED BY THE ROUTE, NOT BY
    THE TENANT.** Re-opening a route has to re-tick the premises already on it,
    and with a paged picker those rows are mostly not on the page in front of
    you. Reading them back by walking every page would be the defect again, so
    the route is asked for its own membership instead — a set bounded by one
    crew's walk, which is `BR-MET-055`'s posture and the same bound
    `chase_list` states.

    `count` is the number of rows the FILTERS match, computed by the database,
    so it is right whether or not the page is full.
    """
    service_row = _picker_service_row(service)
    qs = _route_premises_picker_queryset(
        q=q,
        areas=areas,
        service_row=service_row,
        unassigned_only=unassigned_only,
        route_id=route_id,
        sort=sort,
        direction=direction,
    )
    if members_only:
        if not route_id:
            return {"count": 0, "next": None, "previous": None, "results": []}
        qs = qs.filter(
            id__in=models.Unit.objects.filter(
                tenant_id=_tenant_id(),
                deleted_at__isnull=True,
                id__in=models.RouteMembership.objects.filter(
                    tenant_id=_tenant_id(), route_id=route_id
                ).values("unit_id"),
            ).values("premises_id")
        )
    total = qs.count()
    if per is None:
        window = list(qs)
    else:
        size = max(1, int(per))
        start = max(0, (max(1, int(page)) - 1) * size)
        window = list(qs[start : start + size])
    return {
        "count": total,
        "next": None,
        "previous": None,
        "results": _route_premises_picker_rows(
            window, service_row=service_row, route_id=route_id
        ),
    }


def route_premises_picker(
    *,
    q: str | None = None,
    areas: Any = None,
    service: str | None = None,
    unassigned_only: bool = False,
    route_id: Any = None,
) -> list[dict[str, Any]]:
    """Every premises that may join this route, with what is already true of
    it (BR-MET-074) — the WHOLE set, for callers that legitimately want it.

    `current_route` is the badge r10 draws (*"on SCW-R1"*) and it is scoped to
    the SERVICE being filtered: a premises on the electric route is NOT on
    "another route" when you are building a water route, so badging it would
    warn about a move that will not happen.

    `areas` is BR-MET-072's multi-select — a list, ORed, with a parent
    matching its own sub-areas. Empty = All, which INCLUDES premises with no
    area at all.

    ⚠ **THE SCREEN NO LONGER CALLS THIS — `route_premises_picker_page` DOES
    (`DEF-MET-5743`).** It is kept because the same question asked without a
    window is a reasonable one and seven tests ask it, and because it is now
    the paged function with `per=None` rather than a second implementation:
    the fixed-query row builder is the same one either way, so a batch that
    goes wrong goes wrong for both.
    """
    return route_premises_picker_page(
        q=q,
        areas=areas,
        service=service,
        unassigned_only=unassigned_only,
        route_id=route_id,
        per=None,
    )["results"]


def route_meter_picker(
    *,
    route_id: Any = None,
    premises_ids: list[str] | None = None,
    page: int = 1,
    per: int | None = 50,
) -> dict[str, Any]:
    """SET-06 step 3 — the meters the chosen premises bring, and which are
    excluded (BR-MET-075).

    Also answers r10's CHECK callout — *"2 premises have no active meter —
    they stay on the route and appear on the reader's sheet as 'no meter ·
    verify'"* — because a unit with no meter is an exception a human handles,
    never a reason to drop it from the route.

    ── `CR-131-BRC07` steps 5 and 7 · IT TAKES PREMISES, NOT 726 UNIT IDS ────
    This took `unit_ids: list[str]` and the front end put **one query parameter
    per unit** in the URL. Measured on 2026-09-22
    (`10-scripts/cr131_scale_measure.py`), not estimated:

        52 URL characters per unit   -> 37,994 characters at 726 units,
                                        against a 4–8 KB server limit
        5.1 database queries per unit -> 3,711 sequential round trips

    The request never arrived, so step 3 drew *"No meters yet"* over a route
    with 726 units on it. **Both numbers are arithmetic on one mistake: the
    caller was sending the answer to a question the server can ask itself.**

    Two ways in, and they are two different moments rather than a convenience:

      * **`route_id`** — the saved route. It knows its own premises, so NOTHING
        is sent but the id. This is what `RouteDetailPage` and `RouteReadsPage`
        use, and what the wizard uses when re-opening a route.
      * **`premises_ids`** — the wizard's UNSAVED selection, which no route
        knows yet. **6 ids, ~250 characters**, not 726 and 37,994.

    Both given: `premises_ids` wins, because an open wizard is showing what the
    clerk has ticked and not what was last saved. Neither: an empty answer with
    `premises` = 0, which is honest — nothing was asked about.

    ⚠ **IT IS SERVER-PAGINATED (`NFR-3`), AND `total` IS THE WHOLE SET RATHER
    THAN THE PAGE.** `NFR-5` forbids a hard cap, so `per=None` serves
    everything for a caller that genuinely needs it; the default is 50 and the
    counts beside it — `total`, `included` — are counted in SQL over the whole
    set, never over `meters`. A footer computed from the page is how a route's
    meter count silently stops growing at fifty.

    WHAT WOULD MAKE THIS ANSWER WRONGLY: returning `{"meters": []}` when the
    premises could not be resolved, which is indistinguishable from a route
    with no meters — the false absence `DEF-MET-6143`'s own register row calls
    out and the reason step 6 exists. It does not: `premises` and
    `premises_without_meter` are served beside the rows so a caller can tell
    *nothing was asked* from *nothing was found*.
    """
    tenant_id = _tenant_id()
    # CR-029 (B17 §6) — the reason travels WITH the exclusion, because SET-06D's
    # Assets tab renders them together (*"MTR-W2262 excluded · premise
    # demolished"*). Reading the ids alone is what left that tab able to say
    # that a meter was excluded and never why.
    exclusion_reasons = route_exclusion_reasons(route_id) if route_id else {}
    excluded = set(exclusion_reasons)

    wanted = [str(value) for value in (premises_ids or []) if str(value).strip()]
    if not wanted and route_id:
        wanted = [
            str(value)
            for value in models.RoutePremisesMembership.objects.filter(
                tenant_id=tenant_id, route_id=route_id
            ).values_list("premises_id", flat=True)
        ]
    if not wanted:
        return {
            "meters": [],
            "total": 0,
            "included": 0,
            "premises": 0,
            "premises_without_meter": 0,
            "page": 1,
            "per": per,
        }

    # ── the units of those buildings — ONE query, not one per premises ──────
    units = list(
        models.Unit.objects.filter(
            tenant_id=tenant_id, premises_id__in=wanted, deleted_at__isnull=True
        )
        .select_related("premises")
        .order_by("premises__premise_no", "label", "id")
    )
    # ── their meters — THREE queries, not 5.1 per unit ──────────────────────
    by_unit = seams.assets_on_units([unit.id for unit in units])

    meters: list[dict[str, Any]] = []
    premises_with_meter: set[str] = set()
    for unit in units:
        for asset in by_unit.get(str(unit.id), []):
            # `DEF-CUS-9753` — a route is walked to READ; a cart, a fire line
            # or a PV array is not a meter and was counted among them.
            if not _is_read_device(asset):
                continue
            asset_id = str(asset.get("id"))
            premises_with_meter.add(str(unit.premises_id))
            meters.append(
                {
                    "id": asset_id,
                    "asset_no": asset.get("asset_no") or asset.get("serial_no"),
                    "unit_id": str(unit.id),
                    "unit_label": unit.label,
                    "premises_id": str(unit.premises_id),
                    "address_line": unit.premises.address_line,
                    "service_code": asset.get("service"),
                    "size_class": asset.get("size_class"),
                    "read_method": asset.get("read_method"),
                    "excluded": asset_id in excluded,
                    # NULL for an included meter AND for an exclusion made
                    # before the column existed — the screen draws the blank
                    # rather than a reason nobody wrote.
                    "exclusion_reason": exclusion_reasons.get(asset_id),
                }
            )
    total = len(meters)
    included = sum(1 for meter in meters if not meter["excluded"])
    # ⚠ The COUNTS above are over the whole set and the SLICE below is the
    # page. They are computed in that order on purpose — swap them and the
    # footer starts agreeing with the page instead of with the route.
    if per is not None:
        start = max(page - 1, 0) * per
        page_rows = meters[start : start + per]
    else:
        page_rows = meters
    return {
        "meters": page_rows,
        "total": total,
        "included": included,
        # `premises` is what makes an empty answer readable: 6 buildings and 0
        # meters is a route of unmetered properties; 0 buildings is a request
        # that asked about nothing.
        "premises": len(wanted),
        "premises_without_meter": len(wanted) - len(premises_with_meter),
        "page": page,
        "per": per,
    }


def cycles_queryset(*, q: str | None = None, filters: dict[str, Any] | None = None) -> QuerySet:
    """The filtered cycle rows, unserialized (D7's sort-then-derive half)."""
    qs = models.Cycle.objects.filter(tenant_id=_tenant_id())
    filters = filters or {}
    if term := (q or "").strip():
        if len(term) >= 2:
            # ⚠ **THE ROUTE CODE IS PART OF THIS SEARCH — Meter Reads blueprint
            # entry 15, callout ②: *"Search · cycle code and route code"*.**
            # The Read cycles list draws a Routes column of route CODES beside
            # the cycle code, and a clerk holding a route sheet knows `RT-004`
            # and not which cycle owns it. Matching `code`/`name` alone left the
            # one identifier a reader actually carries unsearchable — and the
            # screen's prompt would then have been FALSE, which CR-041's own
            # amendment names as the thing no source-reading check can catch.
            #
            # `route` is the reverse query name of `Route.cycle` (that FK
            # declares no `related_name`). **`.distinct()` is not optional:**
            # a cycle with three matching routes would otherwise be joined into
            # three rows, and `_page` paginates the list this feeds — so the
            # duplicates would be real rows on a real page under a `count` that
            # agreed with them.
            qs = qs.filter(
                Q(code__icontains=term)
                | Q(name__icontains=term)
                | Q(route__code__icontains=term)
            ).distinct()
    if status := filters.get("status"):  # BR-MET-076 draft | active | inactive
        qs = qs.filter(status=str(status))
    # ── CR-045 wave D task D.7 (DEF-1702) · `f.frequency` ──────────────────
    # The Frequency column was SORTABLE and not FILTERABLE — the one dimension
    # SET-05.cycles most obviously offers.
    #
    # ⚠ **IT MATCHES BOTH GENERATIONS OF THE SPELLING, AND A NAIVE `=` WOULD
    # HAVE SHIPPED A CONTROL THAT MISSES ROWS.** `cycles.frequency` is FREE
    # TEXT: RC-W1's migration 0019 moved the shipped rows onto the eight
    # business words (`Monthly`), and the CR-006 generation wrote the enum
    # (`monthly`, `bi_monthly`). The frontend already folds the two through
    # `frequencyKey()`; this is the same fold on the server, through
    # `schedule.business_frequency` so there is ONE mapping and not a second
    # copy that can drift from it.
    #
    # It is still EXACT per token and never `icontains`: `annual` is a substring
    # of `semiannual`, so a loose match would put every semiannual cycle into
    # the annual answer with a count that looks entirely plausible.
    if frequency := filters.get("frequency"):
        word = schedule.business_frequency(str(frequency))
        spellings = {str(frequency)}
        if word is not None:
            spellings.add(word)
            spellings.update(
                legacy
                for legacy, business in schedule.LEGACY_FREQUENCIES.items()
                if business == word
            )
        match = Q()
        for spelling in sorted(spellings):
            match |= Q(frequency__iexact=spelling)
        qs = qs.filter(match)
    # ⚠ THE DEFAULT ORDER MOVED WITH THE COLUMN (W5-T2). It was
    # `-window_start` — one particular period's stored date, which metering 0021
    # dropped and which was null on every cycle created since CR-029 landed, so
    # the "newest window first" it promised had already stopped being true. The
    # derived window's start is `start_day`, and a cycle with none sorts last
    # rather than first: an unscheduled cycle is not the newest thing on the
    # page. `code` remains the tiebreak and the list's own default sort.
    return qs.order_by(F("start_day").desc(nulls_last=True), "code", "id")


#: CR-029 D7 / BR-SHL-011 — SET-05.cycles' sortable columns. `accounts` is the
#: one derived key: a COUNT through the service-point stamp, sorted from the
#: batch. `lifecycle_status` is the stored `status` column under the name the
#: screen shows it by (the operational `status` is derived and is NOT sortable).
CYCLE_SORTS = {
    "code": "code",
    "name": "name",
    "frequency": "frequency",
    "start_day": "start_day",
    "days_to_complete": "days_to_complete",
    "lifecycle_status": "status",
    "accounts": None,  # derived — sorted on the built page
    # ── Meter Reads blueprint entry 15 — the two ⇅ the drawing adds ──────────
    # The Read cycles list draws a sort control on **Cycle**, **Read window**
    # and **Bill date**, and only the first of those three had a key.
    #
    # `read_window` is an ALIAS of `start_day` rather than a second column: the
    # window IS start day + days-to-complete (B17 §2), so ordering by its start
    # is ordering by that column. It exists under the screen's own word because
    # a sort key travels as `?sort=` from the column it sits on, and a column
    # called *Read window* sending `sort=start_day` is the silent mismatch
    # `SET-05.cycles` already had to write a paragraph about.
    #
    # `bill_date` is DERIVED per row (`_default_bill_date` over the cycle's
    # bill DAY and its next period), so it sorts on the built page exactly as
    # `accounts` does. See `cycles_page` for why that is still a whole-list
    # sort and not a per-page one — and for the null handling it needs and
    # `accounts` never did.
    "read_window": "start_day",
    "bill_date": None,  # derived — sorted on the built page
}
CYCLE_DEFAULT_SORT = "code"


def cycles_page(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> list[dict[str, Any]]:
    """The cycles list, sorted server-side and batched (D7).

    One tenant-clock read and one batch for the whole page — see `cycles_list`
    for why the clock is read once, and `CycleBatch` for the four cascades it
    replaces.
    """
    key = sort if sort in CYCLE_SORTS else CYCLE_DEFAULT_SORT
    column = CYCLE_SORTS[key]
    qs = cycles_queryset(q=q, filters=filters)
    if column is not None:
        qs = qs.order_by(column, "code", "id")
    rows = list(qs)
    batch = CycleBatch(rows)
    as_of = seams.tenant_today()
    served = [cycle_dict(row, as_of=as_of, batch=batch) for row in rows]
    if column is None:
        # ⚠ **NULLS LAST, AND THE TUPLE IS WHY THIS IS NO LONGER ONE TERM.**
        # `accounts` is always an int, so the single-term key was total and
        # correct for the only derived sort that existed. `bill_date` is a
        # string OR `None` — a cycle with no bill day, or none with a next
        # period, has no bill date at all — and `None < "2026-11-05"` raises
        # `TypeError`, which is a 500 on the list rather than a bad order. The
        # leading boolean puts the absent ones last and keeps every remaining
        # comparison between two values of one type.
        served.sort(
            key=lambda served_row: (
                served_row[key] is None,
                "" if served_row[key] is None else served_row[key],
                served_row["code"],
            )
        )
    if direction == "desc":
        served.reverse()
    return served


def cycles_list(
    *, q: str | None = None, filters: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    qs = cycles_queryset(q=q, filters=filters)
    # CR-029 D2 — ONE tenant-clock read for the whole page, not one per row.
    # `cycle_dict` anchors its derived window on the tenant's today
    # (`seams.tenant_today`, which resolves the tenant's Regional timezone), and
    # leaving that to default per row would be a lookup per cycle for a value
    # that cannot differ between them. It is also the CORRECT answer, not only
    # the cheap one: a list rendered across midnight would otherwise show two
    # different "current" windows in one table.
    as_of = seams.tenant_today()
    rows = list(qs)
    batch = CycleBatch(rows)
    return [cycle_dict(row, as_of=as_of, batch=batch) for row in rows]


def plant_key(cycle_id: Any) -> str | None:
    """`DEF-BIL-8696` — a key that MOVES whenever any row `units_in_cycle` (and
    a cycle's terms) is derived from is written: the cycle itself and this
    utility's routes, their services and premises picks, service points, units
    and premises (`core.row_versions`). Billing's Sign off rebuilds its saved
    whole-run summary when it differs. None where the database cannot say."""
    from core import row_versions

    if not row_versions.supported():
        return None
    tenant_id = _tenant_id()
    return row_versions.keys(
        models.Cycle.objects.filter(tenant_id=tenant_id, pk=cycle_id),
        models.Route.objects.filter(tenant_id=tenant_id),
        models.RouteService.objects.filter(tenant_id=tenant_id),
        models.RoutePremisesMembership.objects.filter(tenant_id=tenant_id),
        models.ServicePoint.objects.filter(tenant_id=tenant_id),
        models.Unit.objects.filter(tenant_id=tenant_id),
        models.Premises.objects.filter(tenant_id=tenant_id),
    )


def units_in_cycle(cycle_id: Any, *, service_codes: list[str] | None = None) -> list[str]:
    """The unit IDs a bill run over this cycle covers. Billing's scope seam.

    WHY BILLING CANNOT WORK THIS OUT ITSELF. "Which accounts does this run
    bill" reads as a customers question, and it is not: an account is billed
    because its unit has a metered service point stamped with this cycle, and
    `service_points` is a metering table. Billing joining to it would be a
    cross-module read (B1), and it would also encode metering's routing rule —
    that the cycle stamp follows route membership (BR-MET-033) — in a module
    that does not own it. So metering answers the question and billing asks.

    `service_codes` narrows to a run's scope (US-BIL-001 §5: an unchecked
    service is an explicit recorded choice). A unit keeps its place in the run
    if ANY of its service points is in scope — a house on electric + water in
    a water-only run is still billed, for water.

    Order is stable so a run scoped twice covers the same accounts in the same
    order — a run whose membership shifts between the preview and the issue is
    a run whose approval meant something different from what shipped.

    ── CR-029 D4 · DERIVED, NOT STAMPED ─────────────────────────────────────
    ⚠ **THIS USED TO FILTER `service_points.cycle_id`, AND THAT IS THE DEFECT.**
    The stamp is written only when a route is created or edited, so the answer
    was a snapshot: DEF-225 (a unit added to a serviced building afterwards was
    never read and never billed) and DEF-249 (a unit with membership and NO
    service point — a base-only unit with no meter — was invisible here) are
    both that one reading. BR-MET-082 Amendment 1, PO verbatim: *"at the time of
    Run -> it will figure out how many accounts or meter or devices it has to
    take into account; every run it is not necessry it will ahve same number of
    accounts or meters - since Utility will make changes"*.

    **BOTH OF THE TWO SENTENCES THIS SEAM HAS TO SATISFY STILL HOLD**, and they
    are about different windows. Run-to-run variation is CORRECT and no guard
    may treat it as drift. The preview-to-issue stability above is about ONE
    run: the answer is a pure function of the tags, so it is identical while
    they are, and the run's real freeze is the DRAFT INVOICE set `issue.
    issue_run` works from — written once by the preview and never re-scoped.

    Soft-deleted service points and deleted units are excluded by the
    resolution: a removed row is not a reason to bill.
    """
    from apps.metering import derivation
    from core import walk_switches

    # DEF-BIL-8510 — a walk's TEST-ONLY outage switch (off unless a walk names
    # a directory; forbidden in production). Raises as an unreachable store.
    walk_switches.refuse_if_down("meter_reads")
    return derivation.units_in_cycle(cycle_id, service_codes=service_codes)


# ═══════════════════════════════════════════════════════════════════════════
# W2 READS LANE — read path (US-MET-008 KPIs · US-MET-012 S25 list ·
# US-MET-013 S29 drawer · US-MET-019 Needs-attention chips)
#
# Rules:  BR-MET-016/053 (consumers resolve the lineage HEAD — a superseded
#         chain appears once) · BR-MET-021/052 (status vocabulary) ·
#         BR-MET-055 (server pagination + 2-year hot window; NO unbounded read
#         endpoint exists) · BR-MET-056 (the drawer renders STORED data — the
#         math line, the flag reason with its thresholds and the chain all come
#         from storage, never re-derived here) · CLAUDE.md rule 3 (every
#         consumption is rendered WITH its unit)
# ═══════════════════════════════════════════════════════════════════════════

# US-MET-012 capability row (S25).
READ_SORTS = {
    "read_at": "read_at",
    "meter": "asset__asset_no",
    "usage": "consumption",
    "status": "status",
    "channel": "channel",
}
READ_DEFAULT_SORT = "-read_at"
# `disputed` joined the vocabulary with the US-MET-013 dispute writer
# (2026-08-16). Until then the S25 Disputed chip counted markers and had no
# drill-in, because BE-05 IGNORES an undeclared `f.` param — a "Disputed" button
# over an undeclared filter would have returned the WHOLE list while looking
# like a filtered slice. Declaring it here is what makes US-MET-019 TC-4's
# drill-in ("Click Disputed → the 1 disputed read with reason, actor and hold
# state") a real query rather than a lie.
# `asset` joined with CR-028 AST-W2 (2026-08-22): DEF-475 recorded that no
# declared filter could narrow the list to ONE METER, which is what left the
# S50 Reads tab deliberately unserved — an undeclared `f.` param is IGNORED
# (BE-05), so a "this meter's reads" link would have returned the whole list
# while looking like a filtered slice. Declaring it is the fix.
READ_FILTERS = ("route", "status", "cycle", "service", "source", "channel", "disputed", "asset")
# BR-MET-055: the default query window is the last 2 years (the hot
# partitions). Older reads are reachable only through the explicit archive
# opt-in, and there is no code path that answers an unbounded query.
HOT_WINDOW_DAYS = 730


def _as_day(value: Any) -> date:
    """`value` as the calendar day a `__date` lookup would compare — the same
    conversion Django's `DateField.to_python` makes (an aware datetime is read
    in the current time zone, a string is ISO)."""
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


def _day_start(day: Any) -> datetime:
    """THE INSTANT `day` BEGINS, in the time zone a `read_at__date` lookup reads
    it in — so `read_at__gte=_day_start(d)` selects exactly the rows
    `read_at__date__gte=d` did.

    ⚠ **WHY NOT `read_at__date__…` (DEF-BIL-8490).** `meter_reads` is
    partitioned by month on `read_at`. A `__date` lookup reaches PostgreSQL as
    `(read_at AT TIME ZONE 'UTC')::date >= …` — an expression over the
    partition key, which the planner cannot prune on, so every period-bounded
    read planned and probed all 28 monthly partitions (2.9 ms planning + 1.6–1.9
    ms executing, measured warm; 12 more partitions a year whatever the
    tenant's size). A plain range on the column itself prunes to the one or two
    months the period touches (0.2–0.3 ms + 0.05–0.09 ms). The rows are the
    same: a day is `[its midnight, the next midnight)` in the time zone the
    `__date` cast used, which is Django's current time zone."""
    return timezone.make_aware(
        datetime.combine(_as_day(day), datetime.min.time()), timezone.get_current_timezone()
    )


def _day_after(day: Any) -> datetime:
    """The instant the day AFTER `day` begins — `read_at__lt=_day_after(d)`
    selects exactly what `read_at__date__lte=d` did (see `_day_start`)."""
    return _day_start(_as_day(day) + timedelta(days=1))


def _register_heads() -> QuerySet:
    """EVERY committed lineage head in this tenant's register — including a
    same-day sibling that does not count (BR-MET-1189). For LISTINGS only: the
    Reads list, a meter's reading list, the needs-attention counts and the
    dispute holds, each of which must show a reading that exists."""
    return models.MeterRead.objects.filter(tenant_id=_tenant_id(), superseded_by_id__isnull=True)


def _read_heads() -> QuerySet:
    """Committed lineage heads for this tenant — the ONLY set any consumer
    sees (BR-MET-016/053).

    ⚠ **AND ONLY THE READING THAT COUNTS ON EACH REGISTER AND DATE —
    BR-MET-1189 (PO 2026-10-04, DEF-WRK-9642).** PO verbatim: *"take the
    reading records in register and use date and highest consumption reading
    if it is apprved and validated"*. Where one register holds two readings on
    one date (E-5000: office 3,400 kWh, technician 3,412 kWh), billing's read
    selection, the export pair, move-in/out prefill and every history below
    see ONE of them — `counted_reading.only_counted`, the highest approved and
    validated. A reading alone on its date is untouched. A LISTING that must
    show both uses `_register_heads()` instead.
    """
    return counted_reading.only_counted(_register_heads())


#: How many read ids one `IN (…)` carries — a sent run at the top of T5 names
#: ~80,000 reads, and one statement per chunk keeps the bind list bounded.
_READ_LOCK_CHUNK = 5000
#: A canonical UUID's text, checked without building a `UUID` per id (90,000
#: parses were ~1 s of the sent run's read lock — `DEF-BIL-8758`).
_UUID_TEXT = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def read_lock_counts(read_ids: Any) -> dict[str, int]:
    """`{"reads": n, "locked": m}` — of these reads, how many carry BR-MET-053's
    BILLED lock (`lifecycle="billed"`). ONE query per 5,000 ids.

    `DEF-BIL-8685`: the bulk run's Sent card says *"Meter reads: Locked"*
    (D1 35). The lock is metering's lifecycle on metering's row, so billing
    asks rather than reading `meter_reads` (B1). `reads` counts only the ids
    this tenant holds (hard rule 1) — an id that does not resolve here is not
    counted as unlocked, it is not a read of this utility's at all.
    """
    ids = sorted(
        {
            str(read_id)
            for read_id in (read_ids or ())
            if (isinstance(read_id, str) and _UUID_TEXT.fullmatch(read_id)) or _is_uuid(read_id)
        }
    )
    reads = locked = 0
    if ids and connection.vendor == "postgresql":
        # ⛔ `DEF-BIL-8758` — ONE statement with the ids as ONE array
        # parameter. Bound as `IN (…)` lists of 5,000, the ~90,000 reads of a
        # 40,008-bill sent run cost 11.8 s of Django building filters (the bulk
        # run page's first read, every other read queued behind it). The same
        # rows, the same tenant filter (hard rule 1), RLS on the statement.
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT lifecycle, count(*) FROM {models.MeterRead._meta.db_table} "
                # `IN (SELECT unnest(…))`, never `= ANY(…)`: on the
                # partitioned `meter_reads` the ANY form scanned every
                # partition comparing each row with the whole array (72 s in
                # EXPLAIN ANALYZE at 90,014 ids); this one is a hash semi
                # join (0.28 s).
                "WHERE tenant_id = %s AND id IN (SELECT unnest(%s::uuid[])) GROUP BY lifecycle",
                [str(_tenant_id()), ids],
            )
            for lifecycle, total in cursor.fetchall():
                reads += int(total)
                if lifecycle == "billed":
                    locked += int(total)
        return {"reads": reads, "locked": locked}
    for start in range(0, len(ids), _READ_LOCK_CHUNK):
        chunk = ids[start : start + _READ_LOCK_CHUNK]
        for lifecycle, total in (
            models.MeterRead.objects.filter(tenant_id=_tenant_id(), id__in=chunk)
            .values_list("lifecycle")
            .annotate(total=Count("id"))
            .order_by()
        ):
            reads += int(total)
            if lifecycle == "billed":
                locked += int(total)
    return {"reads": reads, "locked": locked}


def read_is_estimated(status: Any, disposition: Any) -> bool:
    """THE derivation of *"this head is an estimate"* — one place, two inputs.

    US-MET-014's writer stamps `status="estimated"`; BR-MET-015's disposition
    path lets a flagged row post as `disposition="estimate"`. Either makes the
    head an estimate. This was an inline expression in `billing_reads_for_unit`
    and is extracted (CR-038 W9 task 2) because `reads_for_unit` below needs the
    same answer and a second spelling of one derivation is how two consumers
    start disagreeing about which reads are estimates (hard-won law 5)."""
    return status == "estimated" or disposition == "estimate"


#: CR-038 W5 (DEF-045) — the joins `read_dict`'s linkage block reads from, in
#: ONE place so the list, the chain and the detail row cannot disagree about
#: which relations must be loaded. Spelled from the READ (`asset__…`); the
#: archive path re-spells it from the Asset (`service_point__…`) because its
#: bulk lookup starts there — see `ReadArchiveResultSet.__getitem__`.
READ_LINKAGE_RELATED: tuple[str, ...] = (
    # ⚠ **THE READ'S OWN ROUTE — the `BR-MET-079` collection stamp
    # (`DEF-MET-6143`).** `_read_linkage` renders the ROUTE column from this as
    # of the PO's 2026-09-22 ruling, and without the join here a fifty-row page
    # would lazy-load fifty routes to print it — DEF-324's discipline, which is
    # the reason this tuple exists at all.
    "route",
    "asset__service_point__route",
    "asset__service_point__cycle",
    "asset__service_point__service",
    "asset__service_point__unit__premises",
)


#: BR-AST-029 record kinds, as the assets stories and the rating contract name
#: them. DERIVED from `channel` — see models.CHANNEL_EXPORT for why there is no
#: `read_type` column and why the field name is still served.
READ_TYPE_CONSUMPTION = "consumption"
READ_TYPE_EXPORT = "export"


def read_type_of(channel: str) -> str:
    """`export` for the export register, `consumption` for every other channel.

    A TOU window read is consumption too: `tou_on` measures energy DELIVERED,
    and only the export register measures energy fed back. Nothing here adds the
    two together — they are different quantities of the same unit (CLAUDE.md
    rule 3), and combining them is the rating module's question, gated by OQ-001.
    """
    return READ_TYPE_EXPORT if channel == models.CHANNEL_EXPORT else READ_TYPE_CONSUMPTION


def paired_read_id(read: Any) -> str | None:
    """US-AST-012 TC-1: the drawer links a record to its pair — the other typed
    record of the same asset at the same `read_at`. None when there is none."""
    if read.channel == models.CHANNEL_EXPORT:
        other = models.CHANNEL_TOTAL
    elif read.channel == models.CHANNEL_TOTAL:
        other = models.CHANNEL_EXPORT
    else:
        return None  # a TOU window has no export twin — the cycle does
    row = (
        _read_heads()
        .filter(asset_id=read.asset_id, read_at=read.read_at, channel=other)
        .values_list("id", flat=True)
        .first()
    )
    return str(row) if row else None


#: Why a net meter's cycle has no pair to show. VALUES, not prose — the screen
#: renders its own sentence per code, and "we did not measure it" must never
#: come out as a zero (BR-RAT-021's discipline applied to a display).
PAIR_NOT_NET_METER = "asset_is_not_net_metering"
PAIR_NO_EXPORT_RECORD = "no_export_record"
PAIR_NO_CONSUMPTION_RECORD = "no_consumption_record"


def _pair_side(read: Any) -> dict[str, Any]:
    """One half of the pair, as a screen needs it — QUANTITY WITH ITS UNIT."""
    return {
        "read_id": str(read.id),
        "channel": read.channel,
        "read_type": read_type_of(read.channel),
        "consumption": str(read.consumption) if read.consumption is not None else None,
        "unit": read.unit,
        # Rule 3, composed ONCE by the server exactly as `read_dict` does it —
        # DEF-060's lesson is that a screen given a bare number invents a
        # rendering, and two renderings of one figure disagree eventually.
        "usage_display": (quantity_display.quantity_with_unit(read.consumption, read.unit)),
        "current_value": str(read.current_value) if read.current_value is not None else None,
        # DEF-1086 / BR-SHL-250 — the register reading gets the same composed
        # string its consumption already gets, one line above. Composed here so
        # the pair panel cannot invent a second rendering of the same figure,
        # which is the reason `usage_display` exists at all.
        "current_value_display": (
            quantity_display.quantity_with_unit(read.current_value, read.unit)
        ),
        "status": read.status,
        "lifecycle": read.lifecycle,
    }


def net_meter_pair(read: Any) -> dict[str, Any]:
    """US-AST-011/012: this cycle's import AND export records, AS A PAIR.

    **THE SURFACE THE STORY IS ABOUT.** BR-AST-029 is quoted rather than
    summarised: *"Net-meter reads are TWO SEPARATE read records with a reading
    type … A net meter's cycle read = one consumption record + one export
    record, same `read_at`"*. `apps/metering/validation.py` has enforced that
    since W2 and `models.py` has carried the channel, and until 2026-08-16 **no
    screen ever showed the two channels together** — a solar customer's import
    and export were two unrelated rows in a list sorted by date, which is the
    one thing the story exists to prevent (US-AST-012 TC-1: *"S29 drawer shows
    each record's type + a link to its paired record"*).

    Three answers, and NONE of them is a zero:
      · not a net meter → `absent_reason = asset_is_not_net_metering`, and the
        drawer draws nothing. Every flat meter would otherwise grow an "Export:
        0" line that is not a measurement of anything;
      · a net meter whose cycle has no export record → the consumption side
        with `no_export_record`. (The import pipeline creates a 0-value FLAGGED
        export record for exactly this case — BR-AST-029, `_ensure_export_
        records` — so this branch is the one where a read arrived by another
        path, and it says so rather than printing a 0 nobody measured.)
      · both present → both sides, each with its own unit.

    ⚠ **NO MONEY, ANYWHERE.** BR-AST-025: *"export renders as quantity + unit
    everywhere, never money"*. This payload carries no currency field of any
    kind, and it does not net the two figures against each other either —
    subtracting export from import IS the credit math, that is rating's
    EP-RAT-06, and it is gated by OQ-001 (v1 bills solar as capacity charges).
    Two quantities of the same unit measuring DIFFERENT things (CLAUDE.md rule
    3); the screen shows both and lets a human read them.
    """
    asset = read.asset
    if not getattr(asset, "net_metering", False):
        return {
            "is_net_meter": False,
            "read_at": read.read_at.isoformat() if read.read_at else None,
            "consumption": None,
            "export": None,
            "absent_reason": PAIR_NOT_NET_METER,
        }
    heads = _read_heads().filter(asset_id=read.asset_id, read_at=read.read_at)
    # The IMPORT half is whatever this cycle's consumption register says. TOU
    # windows are consumption too (`read_type_of`), but the pair BR-AST-029
    # describes is the CYCLE's: one export register against the total delivered,
    # never one export against each window.
    consumed = heads.filter(channel=models.CHANNEL_TOTAL).order_by("-id").first()
    exported = heads.filter(channel=models.CHANNEL_EXPORT).order_by("-id").first()
    absent = None
    if exported is None:
        absent = PAIR_NO_EXPORT_RECORD
    elif consumed is None:
        absent = PAIR_NO_CONSUMPTION_RECORD
    return {
        "is_net_meter": True,
        "read_at": read.read_at.isoformat() if read.read_at else None,
        "consumption": _pair_side(consumed) if consumed is not None else None,
        "export": _pair_side(exported) if exported is not None else None,
        "absent_reason": absent,
    }


def typed_read_dates_for_asset(asset_id: Any) -> QuerySet:
    """`CR-092` wave C lane 3 / `DEF-MET-4995` — the S50 Reads tab's PAGING UNIT.

    The tab draws ONE ROW PER READ DATE (`apps.assets.selectors.asset_reads`
    folds `BR-AST-029`'s typed pair into the Import/Export columns of one row),
    so what a page of that tab holds is fifty read DATES — not fifty read rows,
    which for a three-register meter would cut a reading event in half. This is
    that list, DISTINCT and NEWEST FIRST, as a **QuerySet**: the `LIMIT`/`OFFSET`
    therefore reaches SQL (`NFR-3`) instead of slicing a materialised list,
    which is the whole of `DEF-MET-4951`'s shape.

    Lineage HEADS only (`BR-MET-016/053`), exactly as `typed_reads_for_asset`.

    ⚠ **WHY A SECOND FUNCTION RATHER THAN A `limit=` ON THE EXISTING ONE.**
    `typed_reads_for_asset` is the read interface **rating** consumes
    (`US-AST-012` TC-3) and `DEF-MET-4101` already refused to move it for a
    display reason, in those words: *narrowing a shared money-path contract to
    fix a display is how a money path acquires a defect*. So the display gets
    its own pair of reads and the money path keeps the one it had.
    """
    return (
        _register_heads()
        .filter(asset_id=asset_id)
        .values_list("read_at", flat=True)
        .distinct()
        .order_by("-read_at")
    )


def typed_reads_for_asset_on(asset_id: Any, read_ats: Any) -> list[dict[str, Any]]:
    """The rows for ONE PAGE of `typed_read_dates_for_asset`, in the same shape
    `typed_reads_for_asset` serves — so `asset_reads`' fold is unchanged and
    cannot drift between the paged answer and the money-path one.

    An empty page answers `[]` without issuing a query at all. That is not a
    micro-optimisation: an empty `__in` spelled as "no filter" would be a
    perfectly valid query returning the asset's ENTIRE history, which is the
    defect this whole lane exists to remove.
    """
    instants = list(read_ats)
    if not instants:
        return []
    queryset = _register_heads().filter(asset_id=asset_id, read_at__in=instants)
    return _typed_read_rows(list(queryset.order_by("read_at", "channel", "id")))


def _typed_read_row(row: Any) -> dict[str, Any]:
    """The ONE typed-read row shape. Named once so the paged read and the
    money-path read cannot answer two different things (hard-won law 5)."""
    return {
        "read_id": str(row.id),
        "asset_id": str(row.asset_id),
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "read_type": read_type_of(row.channel),
        "channel": row.channel,
        "consumption": row.consumption,
        "unit": row.unit,  # rule 3 — never separated from the number
        "current_value": row.current_value,
        "status": row.status,
        # CR-028 AST-W2: the S50 Reads tab draws a Source column; additive
        # — the pinned field set above is asserted as a SUBSET on purpose.
        "source": row.source,
        # DEF-WRK-10184 (PO 2026-10-17): BR-MET-128's EVENT, so the meter's
        # Reads tab says a field move-out reading IS a move-out reading.
        # Additive, like `source` above; None for an ordinary read.
        "event_context": row.event_context,
    }


def _typed_read_rows(rows: list[Any]) -> list[dict[str, Any]]:
    """`_typed_read_row` for each, plus BR-MET-1189's `counts`: True on the
    reading that counts where its register holds two on one date, False on
    the sibling kept as history, None on a reading alone on its date (nothing
    to tell apart, and a screen draws nothing). ⚠ A consumer that SUMS these
    rows must skip `counts is False` — the meter's reading list shows both."""
    flags = counted_reading.counted_flags(rows)
    return [{**_typed_read_row(row), "counts": flags.get(str(row.id))} for row in rows]


def typed_reads_for_asset(
    asset_id: Any, *, period_start: Any = None, period_end: Any = None
) -> list[dict[str, Any]]:
    """US-AST-012 TC-3 — THE READ INTERFACE RATING CONSUMES for a net meter.

    Returns BOTH record kinds for the period: the consumption record(s) and the
    export record(s), each with `read_type`, `consumption` and `unit`. The field
    names are the contract (they are what the story pins), and the payload
    carries no currency field of any kind: rating owns the money, this module
    hands over QUANTITIES ONLY (BR-AST-025).

    Net-metering CREDIT MATH IS NOT HERE AND IS NOT BLOCKED ON: it is rating's
    EP-RAT-06, gated by OQ-001, and v1 bills solar/battery as capacity charges.
    Capture and hand-off are complete; the arithmetic that turns 120 kWh of
    export into money does not exist in this product yet, by design.

    Lineage HEADS only (BR-MET-016/053) — a corrected read is represented by its
    correction, exactly like every other consumer.
    """
    queryset = _register_heads().filter(asset_id=asset_id).select_related("asset")
    if period_start is not None:
        queryset = queryset.filter(read_at__gte=_day_start(period_start))
    if period_end is not None:
        queryset = queryset.filter(read_at__lt=_day_after(period_end))
    return _typed_read_rows(list(queryset.order_by("read_at", "channel", "id")))


def latest_read_for_asset(asset_id: Any) -> dict[str, Any] | None:
    """DEF-592 (CR-028 AST-W1) — the Sub-meters registry's "Last read" summary.

    The newest committed lineage HEAD on any register (BR-MET-016/053 — a
    corrected read is represented by its correction, like every consumer).
    QUANTITY with its explicit unit (CLAUDE.md rule 3) plus the read date; no
    money and no derivation of any kind. Published READ-ONLY for the assets
    seam in the read_count_for_asset shape: assets asks, it never joins (B1).
    None means "no committed read exists" — the screen renders a dash, and
    nothing downstream may treat that as a zero quantity.
    """
    row = _read_heads().filter(asset_id=asset_id).order_by("-read_at", "-id").first()
    if row is None:
        return None
    return {
        "read_id": str(row.id),
        # ── THE READING ITSELF (`DEF-MET-5862`, PO ruling 2026-09-19: *"fix it"*)
        #
        # ⚠ **THIS SHAPE CARRIED THE USAGE AND NOT THE READING, AND ON A FIRST
        # READ THAT IS NOTHING AT ALL.** `consumption` is the DELTA between two
        # reads, so the first read on a register has `prior_value` null and
        # `consumption` null — and every screen drawing this summary showed a
        # bare date over a reading that exists. Measured on `brazosbend`:
        # `W-5042` holds four reads and the earliest carries
        # `current_value=2585.000000` with `consumption=None`.
        #
        # `register_heads_for_assets` below already ruled the same distinction
        # for the reading sheet, in the same words: *"the REGISTER's own figure
        # … is what a clerk compares against the dial"*, and `consumption` *"is
        # the wrong number to put in a column headed previous reading"*. This
        # is that finding applied to the summary the registry rows carry.
        #
        # ⚠ **INDEPENDENTLY NULLABLE FROM `consumption`, AND BOTH DIRECTIONS
        # HAPPEN.** A first read has a reading and no usage; an ESTIMATE has a
        # usage and NO reading at all (`BR-MET-028` — nobody read the dial). A
        # screen must be able to draw either alone, so neither is derived from
        # the other and neither is ever defaulted to zero (`BR-MET-106`,
        # `DEF-079`: absent is not a measurement).
        "current_value": str(row.current_value) if row.current_value is not None else None,
        "consumption": str(row.consumption) if row.consumption is not None else None,
        "unit": row.unit,
        "read_at": row.read_at.date().isoformat() if row.read_at else None,
    }


def _read_linkage(asset: Any, read: Any = None) -> dict[str, Any]:
    """DEF-045 (CR-038 W5) — the four S25 columns the capability row declares
    and `read_dict` never served: CYCLE · ROUTE · SERVICE · PREMISE (with its
    unit label — RDS-01 draws "1408 Elm · A" as one cell of two facts).

    Joined SERVER-side along the asset's service point, which is the one path
    metering already owns (`asset → service_point → route/cycle/service/unit →
    premises`); every query that feeds this serializer carries
    `READ_LINKAGE_RELATED`, so a page costs ONE query (DEF-324 discipline —
    asserted by test, not trusted).

    A stock meter has no service point, and an unstamped one has no route or
    cycle: each fact is independently null — an honest absence, never an
    invented value. IDs travel beside the display codes so a screen can LINK
    (premises detail, route filter) without a second lookup.

    ── ⚠ THE **ROUTE** COLUMN COMES OFF THE READ, NOT OFF THE POINT ──────────
    `DEF-MET-6143`, and it is `DEF-045`'s own requirement held rather than a
    new one: that defect's test is named *"the route filter and the route
    column agree"*, because a clerk who narrows to `RT-009` and then reads
    `RT-001` in the column has been told two different things about one row.
    `read_list`'s route filter reads `meter_reads.route_id` as of the PO's
    2026-09-22 ruling (*"100"* — a route reports the readings COLLECTED on it),
    so this column reads the same stamp. Taking it off
    `asset.service_point.route` would have left the two disagreeing on every
    row whose premises has moved since it was read, which is exactly the state
    `DEF-045` exists to prevent.

    **The CYCLE column is deliberately NOT moved with it.** There is no cycle
    stamp on `meter_reads`, so the point is still the only source; the
    asymmetry is stated here so it reads as a boundary rather than a half-done
    change. `read` is optional and the point is the fallback, so the one caller
    that has no read in hand keeps working instead of losing a column.

    ⚠ A read with NO stamp — collected before `metering/0012` — renders a BLANK
    route cell. That is the same honest absence this docstring already promises
    for a stock meter, and it is the visible half of the cost the PO accepted:
    such a reading is also absent from the route filter. 0 of 516 on the seeded
    fixture; not zero on an older tenant.
    """
    point = getattr(asset, "service_point", None) if asset is not None else None
    stamped = getattr(read, "route", None) if read is not None else None
    stamped_id = getattr(read, "route_id", None) if read is not None else None
    if read is None:  # no read in hand — the point is the only source there is
        stamped = point.route if point is not None and point.route_id else None
        stamped_id = point.route_id if point is not None else None
    cycle = point.cycle if point is not None and point.cycle_id else None
    service = point.service if point is not None else None
    unit = point.unit if point is not None else None
    premises = unit.premises if unit is not None else None
    return {
        "cycle": cycle.code if cycle is not None else None,
        "cycle_id": str(point.cycle_id) if point is not None and point.cycle_id else None,
        "route": stamped.code if stamped is not None else None,
        "route_id": str(stamped_id) if stamped_id else None,
        "service": service.code if service is not None else None,
        "premise": premises.address_line if premises is not None else None,
        "premise_no": premises.premise_no if premises is not None else None,
        "premises_id": str(unit.premises_id) if unit is not None else None,
        "unit_label": unit.label if unit is not None else None,
        "unit_id": str(point.unit_id) if point is not None else None,
    }


#: The three answers `read_method_origin` can carry. Codes, not prose: a
#: screen translates them and a filter groups on them.
READ_METHOD_RECORDED = "recorded"
READ_METHOD_DERIVED = "derived"
READ_METHOD_NOT_STATED = "not_stated"


def _read_method_of(read: Any) -> dict[str, Any]:
    """`{read_method, read_method_origin}` for one committed read.

    Applied ON READ rather than by a backfill - see the decision written out in
    `read_import.LEGACY_READ_METHOD_BY_SOURCE`. Three of the six legacy
    `source_detail` words name no PO method, so a migration would have had to
    guess; this reports what can be known and says so when nothing can.
    """
    recorded = getattr(read, "read_method", None)
    if recorded:
        return {"read_method": recorded, "read_method_origin": READ_METHOD_RECORDED}
    derived = read_import.legacy_read_method(
        getattr(read, "source", None), getattr(read, "source_detail", None)
    )
    if derived:
        return {"read_method": derived, "read_method_origin": READ_METHOD_DERIVED}
    return {"read_method": None, "read_method_origin": READ_METHOD_NOT_STATED}


def unit_type_options() -> list[dict[str, str]]:
    """The tenant's unit-type vocabulary for a picker — `[{code, name}]`.

    ⚠ **THIS EXISTS BECAUSE THE ADD-UNITS FORM WAS READING A HARDCODED ARRAY**
    (`DEF-MET-5656`). `AddUnitsWizard.tsx` rendered its dropdown from a
    five-string tuple compiled into the JavaScript bundle, under a comment
    calling it *"the five ratified unit types (the server's own set)"*. That was
    true when written and stopped being true on **2026-08-18**, when
    `BR-MET-084` made the list tenant-extensible. `models.UnitType`'s own
    docstring dates it: *"Until 2026-08-18 the vocabulary was the UNIT_TYPES
    5-tuple in services.py — a closed enum no tenant could extend and no screen
    could show."* So a utility could add a sixth type, the SERVER would accept
    it — `_resolve_unit_type` reads this table first — and the one control a
    clerk touches never offered it.

    ⚠ **AND THE PICKER MAY NOT READ `/lookups/unit_types` INSTEAD.** That
    endpoint is System-Admin-only and adding a unit is a Billing Clerk's job, so
    the clerk's own wizard would receive an EMPTY control. This repo has paid
    for that lesson once already — `DEF-196`, where S28's read-method picker got
    `GET /reads/read-methods` under `AnyTenantRole` rather than the Settings
    card's route. `read_method_options` above is the shape this copies.

    **INACTIVE ROWS ARE EXCLUDED AND THAT IS THE RULE, NOT A CONVENIENCE**
    (`BR-TEN-034`): a deactivated row stops being PICKABLE while staying lawful
    on every unit already carrying it. `_resolve_unit_type` makes the same
    distinction and says so — the fallback deliberately does not resurrect a
    code the tenant switched off.

    Ordered by the seed's own order, then a tenant's additions, so a clerk who
    has learned where a type sits in the dropdown finds it in the same place.
    """
    rows = models.UnitType.objects.filter(tenant_id=_tenant_id(), active=True)
    return [
        {"code": row.code, "name": row.name}
        for row in rows.order_by("-is_system", "created_at", "id")
    ]


def read_method_options() -> list[dict[str, str]]:
    """The tenant's read-method vocabulary for a picker - `[{code, name}]`.

    BR-MET-123's method vocabulary — Manual, Walk-by, AMI, AMR, Mobile, and
    since BR-MET-142 (2026-08-27) also Drive-by, Self-read and Field visit —
    lives in the tenant's `read_methods` reference list (BR-AST-043), which a
    System Admin
    edits on the S8 reference-data card. THIS IS THE ONLY PLACE THE WIZARD MAY
    GET THEM FROM: a hardcoded frontend array would drift the moment a tenant
    added a sixth, and `/lookups/read_methods` is System-Admin-only (DEF-196)
    while S28 belongs to the Billing Clerk (BR-MET-035) - so the clerk's own
    screen could not read it.

    Ordered as the seed lists them, so the picker reads AMI, AMR, walk-by,
    Manual, Mobile, Drive-by, Self-read, Field visit — and a tenant's own
    additions follow. ⚠ BR-MET-142's three are APPENDED rather than interleaved
    for exactly that reason: a clerk who has learned where Mobile sits in the
    dropdown finds it in the same place.

    An unwired assets module answers `[]`, and the wizard then says the
    vocabulary is unavailable rather than offering an invented one.
    """
    return list(seams.assets_reference_options(models.READ_METHOD_LIST_CODE))


def read_dict(read: Any) -> dict[str, Any]:
    """One read, rendered from STORED values (BR-MET-056 — the drawer must not
    re-derive the math, the thresholds or the chain)."""
    asset = read.asset
    return {
        "id": str(read.id),
        "meter": getattr(asset, "asset_no", None),
        "asset_id": str(read.asset_id),
        # DEF-045 — cycle · route · service · premise (+ their ids), see above.
        # ⚠ The READ travels too, because its `route_id` is the collection
        # stamp and the column must agree with the filter (`DEF-MET-6143`).
        **_read_linkage(asset, read),
        "channel": read.channel,
        # BR-AST-029's record kind, derived from the channel (models.CHANNEL_EXPORT).
        "read_type": read_type_of(read.channel),
        # ⚠ **A CALENDAR DATE, NOT AN INSTANT — `DEF-MET-4101`.** `read_at` is a
        # `timestamptz` that `_parse_date` stamps at `00:00:00Z` of the read DAY,
        # because that midnight IS what makes `UNIQUE (asset, read_at, channel)`
        # the per-date key `BR-MET-052` describes. Served raw, it reached
        # `DateCell` as an instant, which — correctly, by its own contract —
        # converts into the tenant's timezone: S25 drew a read stored
        # `2026-08-14T00:00:00Z` as **`08/13/2026 19:00`** for `America/Chicago`,
        # a day early AND with a clock time nobody ever recorded. Taking `.date()`
        # puts it on `DateCell`'s calendar-date path, which formats the digits and
        # routes through no zone, so every tenant draws the same day.
        # It now matches its own siblings `period_start`/`period_end` below, which
        # are `DateField`s and were always right — on S29 the two disagreed by
        # exactly this one day, next to a usage line that said "14 days".
        # ⚠ NOTHING STORED CHANGES. Storing the clock moment instead would fix the
        # screen and SILENTLY disable the one-read-per-meter-per-date guarantee.
        "read_at": read.read_at.date().isoformat() if read.read_at else None,
        "period_start": read.period_start.isoformat() if read.period_start else None,
        "period_end": read.period_end.isoformat() if read.period_end else None,
        "prior_value": str(read.prior_value) if read.prior_value is not None else None,
        "current_value": str(read.current_value) if read.current_value is not None else None,
        # ── DEF-1086 · THE REGISTER READING IS A QUANTITY AND IT NEEDS THE SAME
        #    TREATMENT `usage_display` ALREADY GIVES CONSUMPTION (BR-SHL-250).
        #
        # The two lines above serve BR-MET-019's `NUMERIC(18,6)` as its own
        # string, and the reads list printed it: the Product Owner read
        # **`1008.000000`** in the PREVIOUS and CURRENT columns of `RDS-01`,
        # two cells away from a USAGE column reading `8 kgal` — because that
        # one renders `usage_display` and these two had no sibling to render.
        #
        # ⚠ **THE RAW KEYS STAY.** They are the values the correction modal
        # prefills and the value the CSV writes; deleting them would be a
        # different defect (`UploadReadsWizard` and `exports.READS` both read
        # them). BR-SHL-250's rule is that the DISPLAY string is a separate
        # field composed by the server, not that the number stops travelling.
        #
        # The unit is the REGISTER's own (`register_units.register_unit`,
        # BR-MET-143 — `kW` on a demand register, the service unit elsewhere),
        # which is what `read.unit` holds, so a reading and its consumption are
        # stated in the same unit and a clerk can check one against the other.
        # `quantity_with_unit` refuses a bare number when the unit is missing
        # (CLAUDE.md hard rule 3) and returns None for an absent reading, which
        # is BR-MET-106's *an unread month is ABSENT, never a zero* held at the
        # display layer — the cell dashes it exactly as it dashed the raw None.
        "prior_value_display": (quantity_display.quantity_with_unit(read.prior_value, read.unit)),
        "current_value_display": (
            quantity_display.quantity_with_unit(read.current_value, read.unit)
        ),
        "multiplier": str(read.multiplier) if read.multiplier is not None else None,
        # Rule 3: consumption NEVER travels without its unit, not even in an
        # internal dict — a caller that receives only the number has to guess.
        "consumption": str(read.consumption) if read.consumption is not None else None,
        "unit": read.unit,
        "usage_display": (quantity_display.quantity_with_unit(read.consumption, read.unit)),
        "days_since_prior": read.days_since_prior,
        "source": read.source,
        "source_detail": read.source_detail,
        # ── HOW THIS READING WAS COLLECTED (BR-MET-123 - CR-038 W3) ──────────
        # Two keys, always both, and the second is what keeps the first honest:
        #   recorded    - a clerk tagged it and the value is stored on the row
        #   derived     - a pre-CR-038 row, translated by the DECLARED mapping
        #                 in read_import.legacy_read_method (never a rewrite of
        #                 the stored row - CLAUDE.md hard rule 4)
        #   not_stated  - nothing on file says how it was collected, and the
        #                 product refuses to invent it. `source='import'` is a
        #                 TRANSPORT and lands here, which is the point of
        #                 BR-MET-123.
        # A screen that showed a DERIVED value with no origin would be showing
        # a guess as a record; hard-won law 1, one field over.
        **_read_method_of(read),
        # BR-MET-128 (CR-038 W9): an event read renders ITS EVENT and ITS USER
        # on the detail. `event_context` is one of models.EVENT_CONTEXTS or
        # None (not an event read); `imported_by` is the acting user for an
        # event/manual batch, the uploader for a CSV one, None where nothing
        # recorded a person. Served on every read so the meter and account
        # views can carry both without a second query shape.
        "event_context": read.event_context,
        "imported_by": str(read.imported_by_id) if read.imported_by_id else None,
        "status": read.status,
        "lifecycle": read.lifecycle,
        "rule_outcomes": read.rule_outcomes or [],
        "import_batch_id": str(read.import_batch_id) if read.import_batch_id else None,
        # **B14 rule 31 — WHAT A CLERK READS IS THE BATCH NUMBER, NEVER THE
        # UUID.** S25 drew `import_batch_id` raw because it was the only
        # thing served, which made the Batch column a live rule-31 breach
        # on a screen whose own blueprint names it. `batch_no` is NULLABLE
        # (a batch a series never numbered is a real state), so this is a
        # THIRD value and not a replacement: the screen shows the number
        # where there is one, says so where there is not, and keeps the id
        # on `title` as evidence.
        "import_batch_no": (
            read.import_batch.batch_no if read.import_batch_id else None
        ),
        "disposition": read.disposition,
        "disposition_reason": read.disposition_reason,
        "estimation_method": read.estimation_method,
        "consecutive_estimate_no": read.consecutive_estimate_no,
        "trues_up_read_ids": read.trues_up_read_ids or [],
        "superseded_by_id": str(read.superseded_by_id) if read.superseded_by_id else None,
        "superseded_at": read.superseded_at.isoformat() if read.superseded_at else None,
        "supersede_reason": read.supersede_reason,
        "disputed_at": read.disputed_at.isoformat() if read.disputed_at else None,
        "dispute_reason": read.dispute_reason,
        # US-MET-013 / BR-MET-024. `disputed` is the ACTIVE marker — set and not
        # cleared — which is what the S25 chip counts, what the list filter
        # selects and what holds the account out of the bill run. A screen that
        # read `disputed_at` alone would show a cleared dispute as live.
        "disputed": read.disputed_at is not None and read.dispute_cleared_at is None,
        "disputed_by": str(read.disputed_by_id) if read.disputed_by_id else None,
        "dispute_cleared_at": (
            read.dispute_cleared_at.isoformat() if read.dispute_cleared_at else None
        ),
        "dispute_cleared_by": (
            str(read.dispute_cleared_by_id) if read.dispute_cleared_by_id else None
        ),
        "demand_reset_noted": read.demand_reset_noted,
        # CR-161-BRC10 W4 — the utility's own reading fields, shown read-only
        # on the reading detail (S29). `getattr` because an ARCHIVED row is
        # hydrated from `ReadArchiveResultSet._COLUMNS`, which deliberately
        # does not name the column (a detached partition may not have it).
        "custom_data": dict(getattr(read, "custom_data", None) or {}),
        # ── CR-038 W4 · a PEAK is not energy (CLAUDE.md hard rule 3) ────────
        # BR-MET-051's register is a maximum DEMAND, not a quantity consumed:
        # `demand_rate_per_kw` prices it per kW while every other channel on
        # the same meter is priced per kWh, and adding the two produces a
        # number that means nothing. Served as a FLAG rather than left to each
        # screen to test `channel === "demand"`, so one rule governs every
        # surface (BR-MET-056 — rendered from stored values, never re-derived).
        "is_peak": read.channel == models.CHANNEL_DEMAND,
        # ✅ **AND THE HONEST HALF IS NOW CLOSED — BR-MET-143, PO 2026-08-27,
        # closing OQ-391 and DEF-797.** This comment used to report a mismatch
        # rather than fix it: `_post_row` stamped `unit=asset.unit` for every
        # channel, so a peak was stored in the METER's own kWh while
        # `rate_schedules.demand_rate_per_kw` priced it per kW, and no signed
        # rule said otherwise. PO verbatim: *"A demand reading carries kW - we
        # have to match utility service unit and meter reading unit"*. The unit
        # is now recorded per REGISTER (`register_units.register_unit`), so
        # `read.unit` above is `kW` on this row and `kWh` on the energy row of
        # the SAME meter, and `usage_display` composes the right pair.
        #
        # ⚠ **`is_peak` STILL EARNS ITS PLACE, and for the reason it always
        # did.** The unit now says the quantity is power; the FLAG says the
        # figure is a MAXIMUM rather than a total (BR-MET-051), which no unit
        # string can carry. A screen needs both — one to label the number, one
        # to decide whether it may ever be added to the row above it.
    }


#: `B30`'s two absences, and they are DIFFERENT FACTS (the DEF-075 posture).
#: `not_stamped` — this reading carries no account: a vacancy read, a meter on a
#: unit nobody has taken service at, or a row committed before `DEF-658` taught
#: the import path to stamp one. `unresolved` — the id is there and customers
#: could not answer it. A screen that printed one sentence over both would tell
#: a clerk "no account" about a reading that has one.
READ_ACCOUNT_NOT_STAMPED = "not_stamped"
READ_ACCOUNT_UNRESOLVED = "unresolved"


def read_account(read: Any) -> dict[str, Any]:
    """`B30` / `MR-39` — the account a reading was taken for, for the detail.

    ⚠ **THE COLUMN HAS BEEN THERE SINCE THE TABLE WAS AND NOTHING EVER READ IT
    BACK.** `meter_reads.account_id` is a reviewed cross-module FK (B2 §2),
    stamped at collection by `services.collection_account_id` since `DEF-658`,
    and `read_dict` serves 41 keys, **none of them the account** — so the screen
    printed *"The account is not served on a reading; open it through the
    unit"* over the top of a stored answer. The blueprint's own words for that:
    *"a stored column and a printed absence for the same fact is the two-homes
    problem waiting to happen"* (`B30`).

    **SERVED FROM THE STORED ID, NEVER FROM THE UNIT.** `seams.account_references`
    says why at length: a reading belongs to whoever was on supply the day it was
    taken, so walking to the unit's CURRENT account would hand the previous
    occupant's year of consumption to the new one. That is the hazard the stamp
    exists to prevent and it would be reintroduced here, silently, on a screen
    whose whole job is proving where a number came from.

    **B14 rule 31:** `account_no` is what a clerk reads. The uuid travels so the
    screen can put it on `title` as evidence, and for nothing else.

    ⚠ **SERVED ON THE DETAIL AND NOT ON THE LIST, DELIBERATELY.** The seam is
    batched and the list COULD carry it; one seam call per row on a fifty-row
    page is the N+1 `accounts_for_units` was added to remove (`NFR-3`, the
    DEF-324 discipline), and no drawn column asks for it. A list that wants it
    later calls `seams.account_references` ONCE with the page's ids.
    """
    account_id = getattr(read, "account_id", None)
    if not account_id:
        return {"account": None, "account_absent_reason": READ_ACCOUNT_NOT_STAMPED}
    found = seams.account_references([account_id]).get(str(account_id))
    if found is None:
        return {"account": None, "account_absent_reason": READ_ACCOUNT_UNRESOLVED}
    return {"account": found, "account_absent_reason": None}


#: BR-MET-024 / OQ-043's closure, as billing's exception screen groups it. A
#: CODE, not prose, for the same reason every other `absent_reason` is one:
#: S31.2 groups its findings tabs on the value and prose cannot be grouped.
ACCOUNT_HELD_BY_DISPUTE = "read_disputed"


@batch_reads.memoised(copy=True)
def dispute_holds_for_unit(unit_id: Any) -> list[dict[str, Any]]:
    """Every UNCLEARED dispute on this unit's meters — billing's hold seam.

    OQ-043's closure, verbatim: *"record + flag, hold account from run until
    SysAdmin clears (PO R6)"*, and BR-MET-024 the same: *"the account is HELD
    from the bill run until a System Admin clears the dispute"*.

    **NO PERIOD ARGUMENT, AND THAT IS THE RULE RATHER THAN AN OMISSION.** The
    closure holds the ACCOUNT until the dispute is cleared — not "until the
    period containing the disputed read has passed". A dispute raised in August
    and never cleared still holds September's run, which is the pressure the
    rule exists to create: the only way back into a bill run is a System Admin
    clearing it. Scoping this to the run's own window would silently release the
    account the following month and the hold would look like it worked.

    LINEAGE HEADS ONLY (BR-MET-016). A dispute on a superseded row cannot exist
    — `dispute_read` refuses one — and a head that was disputed and then
    superseded carries no marker forward, because the correction is the answer.

    Returns one entry per held read, each carrying the meter, the reason and the
    QUANTITY WITH ITS UNIT (rule 3), so the exception screen shows the clerk the
    number that is being argued about rather than only an id.
    """
    service_points = models.ServicePoint.objects.filter(
        tenant_id=_tenant_id(), unit_id=unit_id, deleted_at__isnull=True
    )
    asset_ids: list[Any] = []
    for point in service_points.only("id"):
        asset_ids.extend(seams.asset_ids_for_service_point(point.id))
    if not asset_ids:
        return []
    held = (
        _register_heads()
        .filter(asset_id__in=asset_ids, disputed_at__isnull=False, dispute_cleared_at__isnull=True)
        .select_related("asset")
        .order_by("-disputed_at")
    )
    return [_dispute_row(row) for row in held]


def _dispute_row(row: Any) -> dict[str, Any]:
    """ONE row of `dispute_holds_for_unit` — the single builder, shared with the
    bulk Check's batch read (`prime_check_batch`) so the two cannot drift."""
    return {
        "read_id": str(row.id),
        "meter": getattr(row.asset, "asset_no", None),
        "channel": row.channel,
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "disputed_at": row.disputed_at.isoformat() if row.disputed_at else None,
        "dispute_reason": row.dispute_reason,
        "lifecycle": row.lifecycle,
        # Rule 3 — the disputed quantity NEVER travels as a bare number.
        "usage_display": (quantity_display.quantity_with_unit(row.consumption, row.unit)),
    }


#: Why a service point in a bill run has no usable consumption. These are
#: VALUES, not prose, because billing groups its exception screen on them
#: (BR-BIL-015) and prose cannot be grouped. Metering names them because
#: metering is the module that knows which of them is true.
READ_ABSENT_NO_METER = "no_meter"
READ_ABSENT_NO_READ = "no_read"
READ_ABSENT_FLAGGED = "read_flagged"
#: ⚠ **DEF-161 — THE SERVICE IS NOT MEASURED BY DESIGN, SO NOTHING IS ABSENT.**
#: PO ruling 2026-08-27, verbatim: *"DEF-161 — the bill refuses because trash
#: has no meter - this is correct - (a) Teach it that a service with no meter by
#: design is normal — bill it from its base charge or percentage and never ask
#: for a read."*
#:
#: **THIS VALUE EXISTS TO BE DIFFERENT FROM `READ_ABSENT_NO_METER` ABOVE, and
#: that difference IS the fix.** Until it existed the two facts below were one
#: string and the engine could not tell them apart:
#:
#:   * a TRASH service point with no cart meter — normal, forever, by design;
#:   * a WATER service point whose meter was removed, mis-assigned or never
#:     attached — a configuration fault that must reach a human.
#:
#: Both answered `no_meter`, `billing.measure_consumption` treated every absence
#: as BR-BIL-015's missing read, and `runs.calculate_account` refused the WHOLE
#: account. The only decision that released it — `bill_without_service` —
#: DELETES the service from the bill, so an `$18.00` trash charge and the sewer
#: percentage could never reach a customer.
#:
#: ⚠ **A FIX THAT MADE EVERY `no_meter` BENIGN WOULD HAVE TRADED ONE SILENT
#: WRONG BILL FOR ANOTHER** — a genuinely unread meter would bill as base-only
#: and nobody would know. So the branch below asks the SERVICE's own
#: declaration (`tenant_services.metered`, BR-RAT-081) and nothing else; a
#: service that has not declared itself unmetered still answers `no_meter` and
#: still stops the bill.
READ_ABSENT_SERVICE_NOT_METERED = "service_not_metered"

#: ⚠ **BR-MET-710 / BR-RAT-090 (DEF-1813) — THE SERVICE IS UNMETERED AND NOBODY
#: CAN SAY HOW MANY THINGS IT HAS.** An unmetered service's billable quantity is
#: a COUNT of its assets on the unit (PO ruling 2026-08-20, option A). **Worked,
#: ratified: 3 carts × `$15.00` = `$45.00`; remove one and the next bill is
#: `$30.00`.**
#:
#: **THIS VALUE EXISTS TO BE DIFFERENT FROM `READ_ABSENT_SERVICE_NOT_METERED`
#: ABOVE, for the same shape of reason that value exists at all.** *"This unit
#: has no carts"* is a count of **0** and it BILLS; *"nobody looked"* is no
#: count at all and it REFUSES. Collapsing them bills a three-cart household
#: `$0.00` for trash on a document that foots and prints — which is the exact
#: failure BR-RAT-090 spells out: *"'no carts recorded' and 'zero carts' are
#: different facts and only one of them is billable."*
#:
#: Reachable only when the assets read itself is unavailable — an unpublished
#: `assets.billable_asset_count`, or a unit with no service point for the
#: service. `resolution.AssetCountUnavailable` is the chain's twin of it.
READ_ABSENT_ASSET_COUNT_UNAVAILABLE = "asset_count_unavailable"


#: Statuses that make a committed read unusable for billing WITHOUT a human
#: first. BR-MET-021 gives one primary status per read; these are the ones that
#: say "this number is suspect", and billing a suspect read silently is the
#: failure this list exists to prevent. `estimated` is deliberately ABSENT — an
#: estimate is a lawful bill input (BR-MET-029) that travels flagged, not a
#: refusal.
UNBILLABLE_READ_STATUSES: frozenset[str] = frozenset(
    {"missing", "negative_usage", "mismatch", "unknown_meter", "duplicate", "tou_sum_sanity"}
)


#: 🔒 HUMAN-REVIEW-PENDING — FB-022, PO 2026-10-31 (decision log *"Which
#: reading bills: a lower reading waits for a clerk; the latest approved
#: reading in a cycle bills (PO, R1 A · R2 A)"*). A reading LOWER than the
#: meter's last is stored with BR-MET-052's `negative_usage` flag and no
#: consumption (the field door accepts it since that day). It is AWAITING A
#: CLERK — rollover, misread or meter change — and until one corrects it:
#:   * billing skips it, so the latest APPROVED reading in the period closes
#:     the bill, and a period with none meets the meter as having no reading
#:     (the tenant's missing-reading behaviour) — R1 and R2;
#:   * a later reading is NOT measured from it (`services._prior_actual_head`):
#:     4,812 → 4,790 (flagged) → 4,900 measures 88 from 4,812, never 110 from a
#:     figure nobody has accepted.
#: Ledger: `12-governance/09-human-review-ledger.md`, row "FB-022 — a lower
#: reading waits for a clerk".
AWAITING_REVIEW_READ_STATUSES: frozenset[str] = frozenset({"negative_usage"})


def _period_registers(heads: Any) -> list[dict[str, Any]]:
    """`DEF-RAT-8849` — the period's register readings, NEWEST FIRST, as facts.

    One entry per head `_period_heads` returned: its DAY (the read date, as the
    period filter reads it), register, meter, the dial value, the factor it
    USED (BR-MET-500 — never defaulted to 1), and whether it is an estimate or
    unbillable. An estimate carries no dial value (BR-MET-028), and that `None`
    is published as `None`. Billing's season-change-day cut is the only reader.
    """
    return [
        {
            "read_id": str(head.id),
            "day": _as_day(head.read_at).isoformat(),
            "channel": head.channel,
            "asset_id": str(head.asset_id) if head.asset_id else None,
            "current_value": head.current_value,
            "multiplier": head.multiplier,
            "estimated": read_is_estimated(head.status, head.disposition),
            "billable": head.status not in UNBILLABLE_READ_STATUSES,
        }
        for head in heads
    ]


def _chained_from(
    closing: Any, heads: Any, period_start: Any, *, across_wraps: bool = False
) -> tuple[Decimal, Any, tuple[str, ...], Any]:
    """`DEF-BIL-9016` — the period's usage on ONE register: the closing
    reading plus every reading it is CHAINED back to inside the period.

    Returns `(quantity, opening, read_ids, wrapped)`: the summed `consumption`,
    the reading the chain stops at — the one whose `prior_value` is the dial the period opens at
    (its `prior_value` / `period_start` are what the bill prints and counts from).

    ⚠ **WHY THIS EXISTS.** Each reading is stored as measured from the reading
    before it (BR-MET-019). This seam used to hand billing the NEWEST reading's
    own quantity, so a reading partway through the period cut the bill off at
    it: dials 1,000 → 1,200 → 1,300 billed **100 kWh ($10.00) of 300 ($30.00)**
    on a one-time bill, and the cycle run refused a time-of-use meter.

    THE CHAIN IS WALKED BY DIAL, NEVER BY DATE ALONE. A reading's predecessor is
    the newest earlier billable head on the same meter and register whose dial
    equals its `prior_value` — so an ESTIMATE (no dial) that a later actual
    reading measured ACROSS is never counted twice, and a reading on another
    meter (an exchange) ends the chain. ⚠ **A READING DATED THE PERIOD'S FIRST
    DAY IS THE OPENING DIAL AND IS NOT COUNTED**: metering stamps `read_at` at
    00:00 of its date, so that reading is the register at the instant the
    period opens and its own usage belongs to the period before. The CLOSING
    reading is always counted, so a period with one reading is byte-identical
    to before. A predecessor that is flagged, has no quantity, carries another
    unit (rule 3) or WRAPPED (its dial went backwards) also ends the chain,
    which is the old answer for it — a wrap stays the clerk's to accept.
    """
    quantity = Decimal(closing.consumption)
    opening = closing
    #: `DEF-BIL-9075` — every reading the quantity was summed from, so issue
    #: locks them all (BR-MET-053), not only the closing one.
    read_ids: list[str] = [str(closing.id)]
    wrapped = None
    first_day = _as_day(period_start) if period_start is not None else None
    while opening.prior_value is not None:
        earlier = next(
            (
                head
                for head in heads
                if head.channel == opening.channel
                and head.asset_id == opening.asset_id
                and (head.read_at, head.id) < (opening.read_at, opening.id)
                and head.current_value is not None
                and head.current_value == opening.prior_value
            ),
            None,
        )
        if (
            earlier is None
            or first_day is None
            or _as_day(earlier.read_at) <= first_day
            or earlier.status in UNBILLABLE_READ_STATUSES
            or earlier.consumption is None
            or earlier.unit != closing.unit
        ):
            break
        if (
            not across_wraps
            and earlier.prior_value is not None
            and earlier.current_value < earlier.prior_value
        ):
            # A reading whose dial went BACKWARDS is a register wrap metering
            # recorded. The chain stops short of it and NAMES it, so the
            # period opens at that reading and billing asks a clerk to accept
            # the rollover (PO 2026-09-30, changes rows 45–46): the run through
            # its last-bill anchor, a bill with no anchor through the wrap
            # named here (`DEF-BIL-9076`).
            wrapped = earlier
            break
        quantity += Decimal(earlier.consumption)
        opening = earlier
        read_ids.append(str(earlier.id))
    return quantity, opening, tuple(read_ids), wrapped


def _rollover_entry(read: Any, heads: Any, period_start: Any, wrapped: Any) -> dict[str, Any]:
    """`DEF-BIL-9076` — a rollover inside the period, and the period ACROSS it.

    What a clerk is asked to accept (the wrapped reading, from → to) and what
    the bill becomes once they do: the chain walked through the wrap, its
    quantity, the dial it opens at and every reading it charges for.
    """
    quantity, opening, read_ids, _ = _chained_from(read, heads, period_start, across_wraps=True)
    return {
        "read_id": str(wrapped.id),
        # DEF-BIL-9077 — what the clerk is shown beside the Accept control: the
        # METER by its number (never an id, B14 rule 31) and the closing dial,
        # so the screen can read 99,800 → 240 → 700.
        "meter": getattr(getattr(wrapped, "asset", None), "asset_no", None),
        "closing": read.current_value,
        "day": _as_day(wrapped.read_at).isoformat(),
        "from": wrapped.prior_value,
        "to": wrapped.current_value,
        "quantity": quantity,
        "prior_value": opening.prior_value,
        "measured_from": opening.period_start or _prior_head_day(opening),
        "read_ids": list(read_ids),
    }


def _channel_quantities(
    heads: Any, channels: tuple[str, ...], *, chain_from: Any = None
) -> list[dict[str, Any]]:
    """The latest billable head on each named register, with its own unit.

    One entry per channel that HAS a billable head; a channel with none is
    simply absent, which is what lets rating tell "measured nothing" apart from
    "was not measured" (BR-RAT-021). The same unbillable-status filter the main
    read uses applies here, so a flagged window read is an absence rather than a
    number a clerk has already rejected.

    `chain_from` (the period's first day) sums a register's chained readings
    over the period (`_chained_from`, `DEF-BIL-9016`) — passed for the TOU
    windows and NEVER for demand, which is a PEAK and does not add up.
    """
    out: list[dict[str, Any]] = []
    for channel in channels:
        # `heads` is `_period_heads`' list, NEWEST FIRST (`-read_at, -id`), so
        # the first head on the channel is what `.order_by("-read_at", "-id")
        # .first()` answered (B27: one read of the period, not one per channel).
        read = next((head for head in heads if head.channel == channel), None)
        if read is None or read.consumption is None:
            continue
        if read.status in UNBILLABLE_READ_STATUSES:
            continue
        chained = (
            (read.consumption, read, (str(read.id),), None)
            if chain_from is None
            else _chained_from(read, heads, chain_from)
        )
        out.append(
            {
                # DEF-BIL-9075 / 9076 — the readings summed, and a rollover the
                # chain stopped at (None when there was none).
                "chain_read_ids": list(chained[2]),
                "rollover": (
                    None
                    if chained[3] is None
                    else _rollover_entry(read, heads, chain_from, chained[3])
                ),
                "channel": channel,
                "consumption": chained[0],
                "unit": read.unit,  # rule 3 — never separated from the number
                "read_id": str(read.id),
            }
        )
    return out


def _stamp_asset_count(row: dict[str, Any], unit_id: Any, *, as_of: Any) -> None:
    """BR-MET-710 / BR-RAT-090 — put the OBSERVED count on a designed-absence row.

    Called only where `absent_reason` is already
    `READ_ABSENT_SERVICE_NOT_METERED`: the service is declared unmetered
    (BR-RAT-081) and no usable read exists, which is the one situation in which
    BR-RAT-090 makes the count of the unit's assets the billable quantity.
    **Worked, ratified: 3 carts × `$15.00` = `$45.00`; remove one and the next
    bill is `$30.00`.**

    ⚠ **THERE IS NO DEFAULT AND NO `or 0` IN THIS FUNCTION, AND THAT IS THE
    WHOLE OF IT.** Three outcomes, three different facts, and they must stay
    three:

      * a count of **3** — bills three carts;
      * a count of **0** — the utility looked and this unit has none. A real,
        billable answer: the cart line prices `$0.00` and the base still
        applies;
      * **no count at all** — nobody looked. The row's reason becomes
        `READ_ABSENT_ASSET_COUNT_UNAVAILABLE` and the account STOPS, because
        reading it as a zero bills a three-cart household nothing for trash on
        a document that looks entirely normal (BR-RAT-090, verbatim: *"'no
        carts recorded' and 'zero carts' are different facts and only one of
        them is billable"*).

    ⚠ **THE COUNT IS PUBLISHED WITHOUT A UNIT, AND THAT IS SIGNED LAW RATHER
    THAN AN OVERSIGHT.** BR-RAT-036's rule row draws the distinction in terms:
    *"`per_unit` prices billed USAGE — a measured quantity, so hard rule 3 makes
    its unit mandatory. `per_meter` prices a COUNT, and a meter is not a measure
    of anything; a UoM box would invite 'meters' as a unit… It is the same
    distinction BR-RAT-090 draws for an unmetered service's cart count."* Three
    carts is three things, not three of any measure. The unit the PRICE is
    quoted per belongs to the tariff, and billing attaches it where the tariff
    is in hand — `stages/measure_consumption.py`, which is also the only place
    that can tell a `$15.00`-per-cart schedule from a `$0.0000` one.
    """
    if row.get("absent_reason") != READ_ABSENT_SERVICE_NOT_METERED:
        return
    count = seams.billable_asset_count(unit_id, row["service_code"], as_of)
    if count is None:
        row["absent_reason"] = READ_ABSENT_ASSET_COUNT_UNAVAILABLE
        return
    row["asset_count"] = count


def _stamp_installed_capacity(row: dict[str, Any], unit_id: Any, *, as_of: Any) -> None:
    """**CR-062 D1/H2 — put the SUM of installed capacity on a designed-absence
    row, beside the count.** 🔒 rating math. HUMAN-REVIEW-PENDING.

    PO verbatim, 2026-09-02: *"on given Unit we have installed 3 panels with
    2Kw, 4Kw and 8 Kw , it means the totla capacity will be 14 Kw ; rate will be
    for 1 Kw = 14 $ per KW"* — **14 kW at $14.00 is $196.00**, and until this
    function existed the product could only produce **3**, which prices a 14 kW
    array exactly like three 1 kW ones. (Their message reads *"156"*; 14 × 14 is
    196, they were told so in the same session and did not dispute it, and $156
    is written nowhere in this repo.)

    ⚠ **IT DECIDES NOTHING AND NAMES NO SERVICE.** It publishes two facts and
    stops: how much capacity is installed, and the unit that total is in. WHICH
    fact becomes the billable quantity is BR-RAT-090's rule and BILLING's
    decision — taken in `apps/billing/stages/measure_consumption.py`, the one
    place the TARIFF is in hand, because a schedule quoting *$14.00 per kW*
    bills the kW and a schedule quoting *$10.00 per panel* bills the panels.
    The whole sum/count distinction is read off `capacity_uom_for_service`,
    which is `BR-TEN-171`'s ratified rows, so **the eleventh service (fire)
    landed on the counting side with no edit here and a twelfth will land on
    whichever side its own rows put it.**

    ⚠ **FOUR OUTCOMES, AND THE LAST TWO ARE THE ONES THAT COST MONEY IF THEY
    COLLAPSE INTO EACH OTHER:**

      * the service SUMS IN NO UNIT (`capacity_uom_for_service` -> `None`) —
        trash, fire, and every BANDED service. Nothing is stamped, the row keeps
        its count, and this function has no opinion;
      * a total of **14 kW** — stamped with its unit (hard rule 3);
      * a total of **0 kW** — the utility looked and this unit has no panels. A
        real, billable answer: BR-MET-108's ruled zero prices it at `$0.00` and
        puts the line on the document rather than the gap in a silence;
      * **no total at all** — an asset records no size class, or records one
        this service does not have. `installed_capacity` stays `None` and the
        bill refuses on it. **Skipping the unknown panels and totalling the rest
        is the failure this arm exists to prevent**: three panels of unrecorded
        type would bill `$0.00` for solar, and one unrecorded panel beside a
        2 kW one would bill 2 kW for a 12 kW array. It is BR-RAT-090's own
        sentence one level up — *"'no carts recorded' and 'zero carts' are
        different facts and only one of them is billable"*.

    ⚠ **THE POPULATION IS THE COUNT'S POPULATION**, by construction: both seams
    run the same three predicates over `AssetAssignment` at the same `as_of`. A
    bill that counted one set of assets and summed another would foot perfectly
    and be wrong, and nothing downstream could see it.

    ⚠ **AND ONE CAPACITY SERVICE DOES NOT ASK THE EQUIPMENT AT ALL — `CR-062`
    D6, PO ruling 2026-09-02.** Storm water's capacity is a fact recorded on the
    UNIT, so this function branches ONCE, by name, on
    `connections.unit_capacity_key`. Everything above still describes the other
    ten services exactly. See `_stamp_unit_recorded_capacity` for the ruling in
    the PO's own words and for why a change that made solar read a unit field
    would have implemented the ruling and broken four working services.
    """
    if row.get("absent_reason") != READ_ABSENT_SERVICE_NOT_METERED:
        return
    service_code = row["service_code"]
    uom = seams.capacity_uom_for_service(service_code)
    if uom is None:
        # A BANDED service — trash, fire, water. Its quantity is the COUNT and
        # its size classes add up to nothing in any unit. Not an absence, not a
        # gap: a finished answer, and the row is correct without either key.
        return
    # CR-062 D6 — the one capacity service whose quantity is recorded on the
    # UNIT rather than carried by a device. `None` for the other ten, which is a
    # FINISHED answer meaning *ask the equipment*, and the equipment path below
    # is untouched by this branch.
    unit_key = _unit_capacity_key(service_code)
    if unit_key is not None:
        _stamp_unit_recorded_capacity(row, unit_id, service_code, key=unit_key, uom=uom)
        return
    codes = seams.billable_asset_size_classes(unit_id, service_code, as_of)
    if codes is None:
        # Nobody looked — the same fact the count's `None` carries, and the row
        # has already been given `READ_ABSENT_ASSET_COUNT_UNAVAILABLE` for it by
        # `_stamp_asset_count`, so there is nothing to add. Reached only when
        # the assets read itself is unavailable.
        return
    row["capacity_uom"] = uom
    if any(code is None for code in codes):
        # At least one asset does not say what it is. `total_capacity` cannot be
        # asked — it would be asked about the panels we DO know and would return
        # a plausible, smaller, wrong number.
        _stamp_capacity_unresolved_assets(row, unit_id, service_code, as_of=as_of)
        return
    row["installed_capacity"] = seams.total_installed_capacity(service_code, list(codes))
    if row["installed_capacity"] is None:
        _stamp_capacity_unresolved_assets(row, unit_id, service_code, as_of=as_of)


def _stamp_capacity_unresolved_assets(
    row: dict[str, Any], unit_id: Any, service_code: str, *, as_of: Any
) -> None:
    """**`DEF-RAT-10220` — WHICH assets the total could not be stated over.**

    PO 2026-10-17: *"the bill run Check names the asset whose size has no kW"*.
    An asset is named when it records no size class, or records one whose
    capacity is unknown for this service — asked one code at a time through
    the SAME seam the total uses (`seams.total_installed_capacity`), so the
    names and the refusal can never disagree. Published as asset NUMBERS
    (`capacity_unresolved_assets`), never ids. Changes no quantity: the total
    stays `None` and the bill still refuses.
    """
    pairs = seams.billable_asset_size_classes_by_asset(unit_id, service_code, as_of)
    if not pairs:
        return
    known: dict[str, bool] = {}
    names: list[str] = []
    for asset_no, code in pairs:
        if code is None:
            names.append(asset_no)
            continue
        if code not in known:
            known[code] = seams.total_installed_capacity(service_code, [code]) is not None
        if not known[code]:
            names.append(asset_no)
    if names:
        row["capacity_unresolved_assets"] = names


def _unit_capacity_key(service_code: str) -> str | None:
    """Which characteristic key holds this service's capacity ON THE UNIT, or
    `None` when it comes from installed equipment.

    Imported inside the function rather than at module scope because
    `apps.metering.connections` imports `apps.metering.services`, and this
    module is reached from there. Same posture as `seams.capacity_uom_for_
    service`'s lazy reach into tenancy: one fact, no query, no cycle.
    """
    from apps.metering import connections

    return connections.unit_capacity_key(service_code)


def capacity_is_recorded_on_unit(service_code: str) -> bool:
    """**PUBLISHED** — does this service carry its capacity ON THE UNIT rather
    than on installed equipment? Storm water (ERU) and thermal/heat (tons).

    Billing asks this beside *does an asset stand on this point*
    (`gather._point_has_asset`, `DEF-BIL-8725`): the PO ruled on 2026-09-02 and
    2026-09-07 that these two services have NO asset — nobody installs an ERU or
    a ton — so *no asset = not in service* (PO 2026-09-30) cannot be asked of
    them, any more than of sewer. One fact, no query.
    """
    return _unit_capacity_key(service_code) is not None


def _stamp_unit_recorded_capacity(
    row: dict[str, Any], unit_id: Any, service_code: str, *, key: str, uom: str
) -> None:
    """**CR-062 D6 — STORM WATER'S CAPACITY IS READ OFF THE UNIT.** 🔒 rating
    math. HUMAN-REVIEW-PENDING.

    **PO ruling 2026-09-02, verbatim:** *"In case of strom water - we have to
    take it from Unit - B ⭐ Take the size from the property, not from
    equipment. Storm water becomes the one capacity service whose quantity comes
    from the premises"* — option B of three, **corrected in the same sentence
    from the property to the UNIT**, and that correction is the substance.

    **WHY THIS FUNCTION EXISTS.** `_stamp_installed_capacity` above reads a
    capacity off `Asset.size_class` through the asset's service point, so a
    capacity service needs A DEVICE TO CARRY ITS SIZE. Storm water has none: an
    ERU measures hard surface on a property, it is not equipment, and nobody
    installs one. The sum was `0` on every unit, the line printed **`$0.00`**,
    and **no check in this repo could see it** — the line exists, foots and
    prints, so the invoice count, the service scoreboard and every golden check
    passed straight over it (`DEF-2388`).

    **Worked, and asserted on a seeded tenant:** a house is **1 ERU × $4.50 =
    `$4.50`** a month; the apartment block's 6 ERU is **1 ERU on each of its six
    flats**, `$27.00` across the block; the demo estate is **59 ERU =
    `$265.50`** — and the utility collects **`$270.00`**, because two of its
    houses are outside the city limits and `BR-RAT-101` multiplies their base
    and variable lines by 1.5. **The ruled figure is the QUANTITY**: a surcharge
    moves the price and never the measurement.

    ⚠ **THE ESTATE FIGURES SAID `54 ERU` / `$243.00` / `$247.50` UNTIL
    2026-09-02 (`DEF-2368`) — A DEMO TOTAL, NOT A RULE, AND NOTHING THIS
    FUNCTION DOES MOVED.** `CR-062`'s addendum appended two premises with units,
    the seeded estate assessed 5 ERU more, and the constants stating the total
    did not follow. The per-unit figures above are untouched and so is the
    PO's ruling: the size comes from the unit, at `$4.5000` per ERU.

    ⚠ **THE OTHER FOUR CAPACITY SERVICES ARE UNTOUCHED AND THAT IS THE POINT.**
    Solar, battery, broadband and trash still SUM (or COUNT) installed
    equipment. This branch is reached only for a service
    `connections.unit_capacity_key` names, which is storm water and nothing
    else; a change that made the other four read a unit field would have
    implemented the ruling and broken four working services.

    ⚠ **THREE OUTCOMES, AND THEY ARE THE SAME THREE THE EQUIPMENT PATH HAS,
    reached differently:**

      * a recorded **1 ERU** — stamped with its unit (hard rule 3);
      * **no row at all** — `BR-MET-108` as amended (PO 2026-08-25, *"Bill it as
        zero"*): the assessment was never recorded, so the quantity is `0`, the
        line prices `$0.00` and goes ON the document rather than the gap going
        into a silence. `connections.units_priced_at_zero("storm_water",
        "assessment", unit_ids)` is the ruling's surfacing half and now has a
        real key to be asked with — a utility can list every unit billed at zero
        for want of an assessment. ⚠ The `$0.00` LINE itself is not stamped with
        that reason; that is `DEF-3084`, it is true of every capacity service
        including trash, and it is named here rather than half-fixed for one;
      * **a row that cannot be read as this service's capacity** — a value that
        is not a number, or one recorded in some other unit of measure.
        `installed_capacity` stays `None` and the bill REFUSES by name
        (`installed_capacity_undetermined`). **Reading either as a zero would
        discard an answer the customer gave us**, which is not what *"bill it as
        zero"* ruled: that ruling is about a number nobody recorded, and
        `ServiceCharacteristic.decimal_value` draws the same line in its own
        docstring. Silently billing a `2450 sqft` impervious area as `2450 ERU`
        is the same failure with four orders of magnitude on it.

    ⚠ **ONE INDEXED READ PER UNIT PER STORM-WATER SERVICE POINT**, on the
    unique `(tenant, unit, service, key)` constraint — the same shape and the
    same hot path as `_stamp_asset_count`'s count, and stated rather than
    optimised away (DEF-324's lesson). If a bill run is ever profiled and this
    shows up, the fix is a run-scoped cache in the CALLER.
    """
    from apps.metering import connections

    row["capacity_uom"] = uom
    reading = connections.characteristic_for_pricing(unit_id, service_code, key)
    if reading.absent:
        # BR-MET-108 as amended — the ruled zero. A real, billable answer.
        row["installed_capacity"] = Decimal("0")
        return
    if reading.value is None:
        # Recorded and not a number. The total cannot be STATED, so the bill
        # refuses on the `None` rather than inventing a plausible one.
        return
    recorded_uom = str(reading.unit_of_measure or "").strip()
    if recorded_uom != uom:
        # Hard rule 3 — a quantity is never relabelled. An assessment recorded
        # in square feet is a real answer to a different question, and pricing
        # it per ERU would satisfy the rule in FORM and be wrong in SUBSTANCE.
        return
    row["installed_capacity"] = reading.value


def _stamp_size_counts(row: dict[str, Any], unit_id: Any, *, as_of: Any) -> None:
    """**CR-063 C3/C5 — put the count PER SIZE on a designed-absence row.**
    🔒 rating math. HUMAN-REVIEW-PENDING.

    Decision log 2026-09-02, verbatim: *"For a capacity service billed by a
    COUNT — today trash and fire — the one-size-per-connection rule does not
    apply. The bill carries ONE LINE PER SIZE, and the quantity on each line is
    the count of items of that size."* Worked, on a fire property carrying a 6"
    line and two 2" lines:

        Fire — 6" line             1 connection   60.0000    60.00
        Fire — 2" line             2 connections  12.0000    24.00
        Fire, total                                          84.00

    ⚠ **THIS WORKED TABLE WAS `CR-063`'s WAREHOUSE — a 6" line and two private
    hydrants totalling `$110.00` — UNTIL THE PO REMOVED THE HYDRANT ON
    2026-09-03** (*"remove private hydrants from list"*). That warehouse now
    bills `$60.00` on a single line, so a second SIZE is needed to show the
    split this function exists for. **The ruling changed which sizes exist and
    nothing whatever about the split.**

    ⚠ **THIS IS THE COUNT SPLIT, NOT A SECOND COUNT.** `_stamp_asset_count`
    above publishes HOW MANY items stand on the unit and this publishes how many
    of EACH SIZE, over the SAME population at the SAME `as_of` — the same three
    predicates `billable_asset_size_classes` runs for the summing services. The
    two must agree: `sum(asset_size_counts.values()) == asset_count`, and a bill
    that counted one set and grouped another would foot perfectly and be wrong.

    ⚠ **ONLY FOR A SERVICE WHOSE PRICE VARIES BY SIZE**, which for a capacity
    service means the COUNTING pair — `capacity_uom_for_service` answers `None`.
    Solar, battery, storm water and broadband SUM: `2 + 4 + 8 kW` is ONE quantity
    of 14 kW on ONE line and grouping them per size would be the misreading
    `core/sample_fixture` warns about in terms — *"If a lane finds itself needing
    per-size grouping for solar, it has misread the model."*

    ⚠ **A SIZE NOBODY RECORDED IS A REFUSAL AND NEVER A ZERO**, and it is
    carried as the `None` KEY rather than dropped. Decision log, same ruling: an
    item whose type was never entered *"stops that customer's bill and says
    so"*. Dropping it would bill a 6" fire line at nothing on a document that
    foots and prints — `BR-RAT-090`'s own distinction, *"'no carts recorded' and
    'zero carts' are different facts and only one of them is billable"*. Billing
    refuses on the `None` key by name; this function reports it.

    An EMPTY map is a real, billable answer — the utility looked and this unit
    has no such equipment — which `BR-MET-108`'s ruled zero prices at `$0.00`.
    """
    if row.get("absent_reason") != READ_ABSENT_SERVICE_NOT_METERED:
        return
    service_code = row["service_code"]
    if seams.capacity_uom_for_service(service_code) is not None:
        # A SUMMING capacity service. Its quantity is the total, not a count per
        # band, and `_stamp_installed_capacity` has already published it.
        return
    codes = seams.billable_asset_size_classes(unit_id, service_code, as_of)
    if codes is None:
        # Nobody looked. `_stamp_asset_count` has already re-coded the row to
        # `READ_ABSENT_ASSET_COUNT_UNAVAILABLE` for exactly this, so there is
        # nothing to add and a `{}` here would say the utility looked.
        return
    counts: dict[str | None, int] = {}
    for code in codes:
        counts[code] = counts.get(code, 0) + 1
    row["asset_size_counts"] = counts


def units_changed_since(unit_ids: Any, since: Any) -> dict[str, Any]:
    """`{unit_id: latest change}` for the named units whose unit row (its plan
    assignment lives there), readings or meters changed after `since`.

    Billing's bulk Check asks this to re-check exactly the accounts a change
    concerns (OQ-843 re-ruled 2026-09-30, option C: *"re-check an account when
    its plan, reading, meter … changes"*). Read-only; three queries whatever the
    number of units. Meters are reached through the reviewed asset →
    service point → unit path, the same one the reads seam walks.

    `unit_ids=None` (`DEF-BIL-8694`) asks about EVERY unit of the utility — the
    caller keeps the ones it saved. It costs what changed rather than the size
    of the run: a 40,000-unit run's ids bound as parameters three times were
    most of a 3.1 s read.
    """
    from django.db.models import Max

    every = unit_ids is None
    ids = [] if every else [str(one) for one in unit_ids or () if one]
    if (not every and not ids) or since is None:
        return {}
    tenant_id = _tenant_id()
    unit_scope = {} if every else {"pk__in": ids}
    point_scope = {} if every else {"asset__service_point__unit_id__in": ids}
    asset_scope = {} if every else {"service_point__unit_id__in": ids}
    out: dict[str, Any] = {}

    def keep(unit_id: Any, changed: Any) -> None:
        if changed is None:
            return
        key = str(unit_id)
        out[key] = max(changed, out.get(key, changed))

    for unit_id, changed in models.Unit.objects.filter(
        tenant_id=tenant_id, updated_at__gt=since, **unit_scope
    ).values_list("id", "updated_at"):
        keep(unit_id, changed)
    for unit_id, changed in (
        models.MeterRead.objects.filter(
            tenant_id=tenant_id, updated_at__gt=since, **point_scope
        )
        .values("asset__service_point__unit_id")
        .annotate(last=Max("updated_at"))
        .values_list("asset__service_point__unit_id", "last")
    ):
        keep(unit_id, changed)
    asset_model = django_apps.get_model("assets", "Asset")
    for unit_id, changed in (
        asset_model.objects.filter(
            tenant_id=tenant_id, updated_at__gt=since, **asset_scope
        )
        .values("service_point__unit_id")
        .annotate(last=Max("updated_at"))
        .values_list("service_point__unit_id", "last")
    ):
        keep(unit_id, changed)
    return out


def register_digits_for_read(read_id: Any) -> int | None:
    """The register span (BR-AST-015 `register_digits`) of the meter a read was
    taken on — billing's Check asks it ONLY when a register went backwards, to
    say whether the meter's own dial proves a wrap (PO 2026-09-30, *Possible
    rollover*: 99,950 → 00,120 on a 5-digit dial = 170). One read, one row;
    None when the read or its meter cannot be found. Read-only."""
    row = (
        models.MeterRead.objects.filter(tenant_id=_tenant_id(), id=read_id)
        .values_list("asset__register_digits", flat=True)
        .first()
    )
    return int(row) if row else None


def billing_reads_for_unit(
    unit_id: Any,
    *,
    period_start: Any,
    period_end: Any,
    service_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """What each of this unit's services measured over the period. Billing's
    reads seam — one row per SERVICE POINT, whether or not it has a read.

    ── DEF-161 (PO 2026-08-27) · TWO KINDS OF "NO METER" ─────────────────────
    **A SERVICE THE UTILITY DOES NOT MEASURE IS NOT A MISSING READ.** PO
    verbatim: *"Teach it that a service with no meter by design is normal — bill
    it from its base charge or percentage and never ask for a read."* A service
    point with no asset therefore answers one of TWO reasons, and which one is
    decided by the SERVICE's own declaration (`tenant_services.metered`,
    BR-RAT-081) and by nothing else:

      * `READ_ABSENT_SERVICE_NOT_METERED` — declared unmetered. Billing bills it
        from its base charge and never lists it as work.
      * `READ_ABSENT_NO_METER` — not declared. Unchanged: a setup fault a human
        must see, and it still stops the account's bill.

    ⚠ **A DECLARED-UNMETERED SERVICE THAT NEVERTHELESS HAS A METER AND A READ
    STILL BILLS THE READ.** The branch below is reached only when the service
    point holds NO asset, so the declaration never suppresses a real
    measurement — it only says what an EMPTY service point means. A tenant who
    declares trash unmetered and then attaches a metered cart gets the cart's
    quantity, because the read is a fact and the declaration is a default.

    A SERVICE POINT WITH NO READ STILL GETS A ROW, and that is the whole point.
    Returning only the services that were read would make a missing read
    invisible: the bill would simply not carry that service and would look
    complete. BR-BIL-015 makes a missing read a DECISION a human takes, so the
    absence has to arrive as data with a reason on it (`absent_reason`), never
    as a shorter list.

    `consumption` is metering's stored figure — `(current − prior) × multiplier`,
    unrounded (B4.4) — and it is ALREADY POST-MULTIPLIER. PO ruling 2026-08-11:
    metering applies the meter multiplier and the pricing engine refuses one,
    because the multiplier belongs to the METER, not the tariff. Nothing
    downstream multiplies again; the engine raises if asked to.

    It travels with its `unit`, always (CLAUDE.md rule 3). The unit is the
    asset's own UoM as stamped on the read, never inferred from the service —
    whether it matches the tariff's billed unit is rating's gate (BR-RAT-038),
    and it refuses rather than converting silently.

    Only LINEAGE HEADS are considered (BR-MET-016/053): a read that was
    corrected is represented by its correction, and a superseded chain appears
    once. Within the period, the LATEST head per service point is the CLOSING
    reading — a cycle read taken after a re-read on the same point is the one
    the bill closes at. ⚠ **AND SINCE 2026-10-02 (`DEF-BIL-9016`) THE PERIOD'S
    QUANTITY IS NOT THAT READING'S ALONE.** This sentence used to end *"is the
    one the bill uses"*, and the bill used its stored quantity — which is
    measured from the reading before it, so a reading partway through the
    period cut the bill off there (dials 1,000 → 1,200 → 1,300 billed 100 kWh
    of 300). `consumption` is now the closing reading plus every reading it is
    chained back to inside the period, and `prior_value` the dial the period
    opens at (`_chained_from`).

    ── CHANNELS, added 2026-08-16 with the TOU and demand pricing engines ──────
    A meter can hold more than one register (B2 r8 / BR-MET-059: `total`,
    `tou_on`, `tou_mid`, `tou_off`, `export`, `demand`). Two things changed here,
    and the first is a correction:

    1. **`consumption` no longer picks a TOU or demand register by accident.**
       The latest head was chosen with no regard to channel, so on a
       time-of-use meter whichever window register happened to be read last
       became "the" consumption for the whole service — a plausible number,
       priced against the whole tariff. The main read is now the latest head on
       a register that MEASURES THE PERIOD'S TOTAL, and the window and demand
       registers are excluded from that choice.
    2. **`windows` and `demand` are published beside it.** BR-RAT-021 says TOU
       reads arrive PRE-SPLIT per window and BR-RAT-014's demand measurement is
       a max-demand register read; both are measurements this seam already held
       and threw away. Each carries its own `unit` (hard rule 3) — the demand
       register's is not the energy register's.

    An ABSENT window or demand register is reported by being absent, never by a
    zero: rating refuses a TOU tariff whose window was not measured, because
    "used nothing on-peak" and "nobody read the on-peak register" are different
    facts.

    ── BR-MET-143 (PO 2026-08-27, closing OQ-391 · DEF-797) ────────────────────
    **The `demand` entry now carries the PEAK, in kW, and both halves of that
    sentence moved on 2026-08-27.** Until then `consumption` on a demand row was
    BR-MET-019's `(current − prior) × multiplier` — the difference between two
    maxima — stamped with the METER's energy unit. Measured: peaks 398 → 412
    handed rating `14.000000 kWh`, which the Industrial schedule priced at
    **$154.00** against a correct **412 kW × $11.00 = $4,532.00**. The quantity
    is now `register_units.billable_quantity` (BR-MET-051's *"manual
    demand-register value at cycle read"*) and the unit is the register's own.
    Nothing in THIS function changed to make that true — it reads the stored
    row, as BR-MET-056 requires — which is the point: one fix at the write.

    ── BR-MET-500 (2026-08-27, DEF-1812) · THE `multiplier` KEY ────────────────
    **A SEAM SHAPED FOR ONE CONSUMER AND NOW NEEDED BY TWO.** `consumption`
    above is already post-multiplier and the live bill run needs nothing else,
    so for its whole life this seam published the PRODUCT and threw the FACTOR
    away. The R1–R7 resolution chain needs the factor, because
    `resolution.billable_quantity` scales the RAW register difference itself
    (BR-RAT-001). Measured before the key landed: on a ×10 meter this function
    published `consumption=500.000000` and `current − prior = 50`, and **nothing
    told the caller which factor produced the 500**.

    The figure was never missing — BR-MET-056 stores the factor USED on the read
    row, and `read_dict` and `read_analysis_for_unit` both publish it. Only this
    one seam did not. So the fix is one key off the row already in hand: no new
    query, no new join, no second definition of what the factor is.

    ⚠ **AND IT IS NEVER DEFAULTED TO 1.** See the key's own comment below: a
    defaulted 1 would make the shadow report parity by construction on every
    account with a ×1 meter, which is the great majority — the report would read
    as the best possible news while measuring nothing.
    """
    service_points = _live_service_points_for(unit_id, service_codes)
    # DEF-161 — ONE read for the whole unit, not one per service point. The
    # declaration is a fact about the TENANT's catalogue, so asking it per point
    # would be D7's N+1 on the hot path of every bill run.
    #
    # ⚠ **IT IS STILL ONE QUERY PER UNIT, AND THAT IS STATED RATHER THAN
    # OPTIMISED AWAY (DEF-324's lesson, measured rather than assumed).** A run
    # over 3,000 connections issues 3,000 of these. Each is a single indexed
    # read of `tenant_services`, a table that holds at most TEN rows per tenant
    # — the whole result is smaller than one of the read rows this function
    # already returns — so it is not the shape DEF-324 was about (that one cost
    # ~150 queries and 155 ms PER CALL, because it built a whole screen payload
    # to answer a boolean). If a bill run is ever profiled and this shows up, the
    # fix is a run-scoped cache in the CALLER, not a second definition of what a
    # tenant sells here.
    unmetered = seams.unmetered_service_codes()
    rows: list[dict[str, Any]] = []
    for point in service_points:
        row: dict[str, Any] = {
            "service_code": point.service.code,
            "service_id": str(point.service_id),
            "service_point_id": str(point.id),
            "consumption": None,
            "unit": None,
            "estimated": False,
            "absent_reason": None,
            "prior_value": None,
            "current_value": None,
            "read_id": None,
            #: `DEF-BIL-8324` (PO 2026-09-30) — the day the read MEASURES FROM
            #: (the prior read's date, `meter_reads.period_start`). A read taken
            #: after a stretch nobody read measures that whole stretch, and a
            #: catch-up has to know that before it estimates any of it again.
            #: None when there is no read, or the read stored no start.
            "measured_from": None,
            #: 🔒 `DEF-MET-10163` (PO 2026-10-15) — on a `no_read` row only: the
            #: id and date of a LATER actual reading on this meter whose interval
            #: already spans `period_end` (it measures from on or before it).
            #: Billing then makes no estimate for the period — the usage waits
            #: for the next bill, which that reading measures. None otherwise.
            "covered_by_read_id": None,
            "covered_by_read_on": None,
            #: BR-MET-500 (DEF-1812) — the factor BR-MET-056 stored as USED,
            #: beside the consumption computed FROM it. One key, no new query,
            #: the same row. None when there is no read to have used one.
            #:
            #: ⚠ **NEVER 1 ON THE ABSENT BRANCH, AND THIS IS THE WHOLE POINT OF
            #: THE KEY.** `resolution.billable_quantity` scales the RAW register
            #: difference itself (BR-RAT-001: a ×10 register reading 62 is
            #: 620 kWh, which lands in tier 2), so a defaulted 1 would make ×1
            #: of the difference equal metering's stored figure exactly when the
            #: multiplier really is 1 — and the R1–R7 shadow would report
            #: PARITY ON EVERY ACCOUNT by construction, which reads as the best
            #: possible news while measuring nothing.
            #: `resolution.MeterMultiplierUnstated` exists for this and says so:
            #: *"an absent factor is not 1"*.
            "multiplier": None,
            #: BR-MET-710 (DEF-1813) — BR-RAT-090's OBSERVED quantity for a
            #: service the tenant has declared UNMETERED (BR-RAT-081), and
            #: `None` on every other row because no other row has one. The
            #: count is a fact about the UNIT (PO 2026-08-27 closing OQ-317:
            #: *"where do you see the carts - they are not on accounts theya
            #: re on Units"*), read at the SERVICE-PERIOD END DATE per
            #: BR-RAT-090, so a cart delivered on the 20th does not retro-bill
            #: the cycle and a cart removed mid-cycle still billed while it
            #: was there.
            #:
            #: ⚠ **`None` HERE IS NEVER `0`.** `0` is the utility having
            #: looked and found no carts — a real answer that bills nothing
            #: for carts — and `None` is nobody having looked. The row's
            #: `absent_reason` carries which of the two it is
            #: (`READ_ABSENT_ASSET_COUNT_UNAVAILABLE`), because a caller that
            #: read the absence as a zero would bill a three-cart household
            #: `$0.00` on a document that foots.
            #:
            #: ⚠ **AND IT IS NOT A `consumption`.** This module publishes the
            #: COUNT and never a quantity: saying `consumption=3` would claim a
            #: meter was read. Whether a count becomes the billable quantity is
            #: BR-RAT-090's rule and BILLING's decision, taken in
            #: `apps/billing/stages/measure_consumption.py` — where the tariff
            #: is in hand, so the quantity carries the unit the PRICE is quoted
            #: per and BR-RAT-038 can never be asked to reconcile two units
            #: nobody stated.
            "asset_count": None,
            #: **CR-062 D1/H2 · THE OTHER ARITHMETIC A CAPACITY SERVICE HAS.**
            #: `installed_capacity` is the SUM of what stands on this unit —
            #: 2 + 4 + 8 kW is **14 kW**, not 3 — and `capacity_uom` is the unit
            #: it is summed in (`kW`, `ERU`, `Mbps`). Both are `None` for a
            #: service whose size classes are BANDS, which is what trash and
            #: fire are: their quantity is the COUNT above, and `capacity_uom`
            #: answering `None` IS the statement *"do not sum these"*.
            #:
            #: ⚠ **THE COUNT IS PUBLISHED BESIDE THE SUM AND NEVER INSTEAD OF
            #: IT.** This module publishes FACTS; which of them becomes the
            #: billable quantity is BILLING's decision, taken where the tariff
            #: is in hand — a schedule quoting *$14.00 per kW* bills the kW, a
            #: schedule quoting *$10.00 per panel* bills the panels, and only
            #: the caller holding the tariff can tell those apart.
            #:
            #: ⚠ **`installed_capacity=None` ON A SUMMING SERVICE MEANS THE
            #: TOTAL COULD NOT BE STATED, AND IT IS NEVER A ZERO.** An empty
            #: unit sums to `Decimal("0.0000")` — a real, billable answer
            #: (BR-MET-108's ruled zero). `None` means an asset records no size
            #: class, or one this service does not have, and the bill refuses on
            #: it rather than inventing a plausible total.
            "installed_capacity": None,
            "capacity_uom": None,
            "windows": [],
            "demand": None,
        }
        asset_ids = seams.asset_ids_for_service_point(point.id)
        if not asset_ids:
            # ── DEF-161 · TWO DIFFERENT FACTS THAT USED TO BE ONE STRING ────
            # The service's OWN declaration decides which of them this is
            # (BR-RAT-081, PO 2026-08-20: *"yes we have to say service is meter
            # or unmetered"*), and nothing else does — not the tariff model, not
            # whether a plan prices it, not whether an asset has ever existed.
            #
            #   * DECLARED UNMETERED → no read was ever owed. Billing carries
            #     this forward as a normal outcome and prices the service from
            #     its base charge (DEF-161, PO 2026-08-27).
            #   * NOT DECLARED → a metered service point with no meter, which
            #     is a configuration problem the staff must see, not a
            #     zero-usage bill. Unchanged, deliberately: this is the half of
            #     the ruling a careless fix would have destroyed.
            row["absent_reason"] = (
                READ_ABSENT_SERVICE_NOT_METERED
                if point.service.code in unmetered
                else READ_ABSENT_NO_METER
            )
            _stamp_asset_count(row, unit_id, as_of=period_end)
            # CR-062 D1/H2 — the OTHER arithmetic a capacity service has. Runs
            # beside the count and never instead of it; both are facts and
            # billing chooses between them where the tariff is in hand.
            _stamp_installed_capacity(row, unit_id, as_of=period_end)
            _stamp_size_counts(row, unit_id, as_of=period_end)
            rows.append(row)
            continue
        # ── 2026-09-30 · TWO METERS ON ONE METERED POINT ARE TWO ROWS ──────
        # PO: *"both meter should be build in metered case also - as a
        # speearte line"* — each meter its own connection, its own ladder, its
        # own base. So where a METERED point carries two or more IN-SERVICE
        # meters, each gets its own row over ITS OWN reads, naming it as
        # `asset_id`. Until this, one latest read was taken across every
        # meter on the point and the other meter was never billed.
        #
        # ⚠ **IN SERVICE, NOT MERELY ATTACHED — AND THAT IS THE EXCHANGE
        # GUARD.** A meter exchanged mid-cycle leaves the old meter on the
        # point (retired meters are INCLUDED in `asset_ids`, see
        # `assets.asset_ids_for_service_point`). Splitting on that list would
        # turn every exchange into two connections, the old one with no read.
        # One in-service meter — every exchange, every ordinary point — keeps
        # the single row across all the point's meters exactly as before, and
        # an unpublished in-service read keeps it too (nobody can tell).
        #
        # 🔒 `DEF-BIL-10155` / `DEF-BIL-10156` — and the single row is taken
        # across the point's BILLING meters, not across every asset on it. The
        # latest head among a unit meter, its sub-meters and a building master
        # was whichever was read last: a move-out keys them all on one day and
        # AC-2026-00044 was billed SM-7201's 1 kgal instead of W-5043's 6. A
        # point with no unit meter answers every asset, as before
        # (`assets.billing_asset_ids_for_service_point`).
        groups: list[tuple[list[Any], str | None]] = [
            (list(seams.billing_asset_ids_for_service_point(point.id)) or list(asset_ids), None)
        ]
        if point.service.code not in unmetered:
            in_service = seams.in_service_asset_ids_for_service_point(point.id)
            if in_service is not None and len(in_service) >= 2:
                groups = [([meter], str(meter)) for meter in in_service]
        for group_ids, meter_id in groups:
            meter_row = row if meter_id is None else {**row, "windows": [], "asset_id": meter_id}
            heads = _period_heads(group_ids, period_start, period_end)
            # 🔒 DEF-RAT-8849 (PO 2026-10-01, *"yes build the season-change day
            # reading"*) — every register reading of the period, from the heads
            # already loaded (no extra query). Billing looks among them for a
            # reading dated on a season-change day; metering says nothing about
            # seasons and decides nothing here.
            meter_row["period_registers"] = _period_registers(heads)
            # DEF-BIL-9016 — each window is the sum of its chained readings.
            meter_row["windows"] = _channel_quantities(
                heads, models.TOU_WINDOW_CHANNELS, chain_from=period_start
            )
            demand = _channel_quantities(heads, (models.CHANNEL_DEMAND,))
            meter_row["demand"] = demand[0] if demand else None
            # The window and demand registers are separate MEASUREMENTS of the
            # same service point, published above; `_latest_consumption_head`
            # carries the exclusion and its history (CR-038 W6).
            # 🔒 FB-022 R1/R2 (PO 2026-10-31) — a reading awaiting a clerk
            # never closes the bill; the latest approved one before it does,
            # and none at all is the missing-reading case below.
            read = _latest_consumption_head(
                [head for head in heads if head.status not in AWAITING_REVIEW_READ_STATUSES]
            )
            if read is None:
                # ── BR-MET-710 (DEF-1813) · A CART IS NOT A METER THAT WAS MISSED ──
                # `asset_ids_for_service_point` returns the assets on the point, and
                # for a DECLARED-UNMETERED service those assets are the CARTS — so
                # reaching this line with three carts and no read used to answer
                # `no_read` and stop the whole account. The service point holding an
                # asset is exactly what made the branch above unreachable for the
                # units BR-RAT-090 is about, which is why trash could be declared
                # unmetered and still not be billable by count.
                #
                # BR-RAT-081 says no read is ever owed for this service, and that is
                # true whether or not something stands on its service point. So the
                # designed absence wins here too, and the count below is the
                # quantity.
                #
                # ⚠ **THE TWO BRANCHES THIS DOES NOT TOUCH ARE THE DOCSTRING'S OWN
                # PROMISE, KEPT VERBATIM.** A declared-unmetered service that
                # nevertheless has a meter and a GOOD read still bills the read (the
                # measured branch below), and a read that exists and is UNBILLABLE
                # is still `read_flagged` for a human to judge (the branch above) —
                # on any service, declared or not. The declaration says what an
                # unread point MEANS; it never suppresses a real measurement.
                meter_row["absent_reason"] = (
                    READ_ABSENT_SERVICE_NOT_METERED
                    if point.service.code in unmetered
                    else READ_ABSENT_NO_READ
                )
                if meter_row["absent_reason"] == READ_ABSENT_NO_READ:
                    # 🔒 DEF-MET-10163 (PO 2026-10-15, *"go with 1 and 3"*) —
                    # a LATER actual whose interval already spans this
                    # period's end. Billing then estimates nothing here.
                    covering = _later_actual_covering(group_ids, period_end)
                    if covering is not None:
                        meter_row["covered_by_read_id"] = str(covering.id)
                        meter_row["covered_by_read_on"] = covering.read_at.date().isoformat()
                _stamp_asset_count(meter_row, unit_id, as_of=period_end)
                # CR-062 D1/H2 — the OTHER arithmetic a capacity service has. Runs
                # beside the count and never instead of it; both are facts and
                # billing chooses between them where the tariff is in hand.
                _stamp_installed_capacity(meter_row, unit_id, as_of=period_end)
                _stamp_size_counts(meter_row, unit_id, as_of=period_end)
                rows.append(meter_row)
                continue
            meter_row["read_id"] = str(read.id)
            # 🔒 DEF-BIL-9016 — the period's usage is the closing reading plus
            # every reading chained back to the period's opening dial, and the
            # bill counts (and prints, BR-BIL-030) from THAT dial. `opening`
            # is the closing reading itself wherever the period holds one
            # reading, which is every period before this fix reached.
            period_quantity, opening, chain_ids, wrapped = (
                _chained_from(read, heads, period_start)
                if read.consumption is not None and read.status not in UNBILLABLE_READ_STATUSES
                else (None, read, (str(read.id),), None)
            )
            # 🔒 DEF-BIL-9075 — every reading this quantity was summed from, so
            # issue locks them all. 🔒 DEF-BIL-9076 — a rollover the chain
            # stopped at, for billing to hold or (once accepted) bill across.
            meter_row["chain_read_ids"] = list(chain_ids)
            meter_row["rollover"] = (
                None if wrapped is None else _rollover_entry(read, heads, period_start, wrapped)
            )
            meter_row["measured_from"] = opening.period_start or _prior_head_day(
                opening
            )  # DEF-BIL-8324
            meter_row["prior_value"] = opening.prior_value
            meter_row["current_value"] = read.current_value
            # BR-MET-500 — set HERE, beside the two register values it relates, and
            # BEFORE the unbillable branch below: an exception row already carries
            # `prior_value`/`current_value` so the screen can show the number a
            # human is being asked to judge, and the factor is part of that number.
            meter_row["multiplier"] = read.multiplier
            meter_row["estimated"] = read_is_estimated(read.status, read.disposition)
            if read.status in UNBILLABLE_READ_STATUSES or read.consumption is None:
                # The read exists and cannot be billed as it stands. Reported with
                # the read attached so the exception screen can show the number a
                # human is being asked to judge, rather than an empty row.
                meter_row["absent_reason"] = READ_ABSENT_FLAGGED
                rows.append(meter_row)
                continue
            meter_row["consumption"] = period_quantity
            meter_row["unit"] = read.unit  # rule 3 — never separated from the number
            if not read.unit:
                # PO ruling 2026-09-30 (billing decision log, *"A PROBLEM NEVER
                # STOPS THE CHECKING"*, item 2): a reading stored with no unit
                # takes the unit RECORDED ON ITS METER. Published as its own key
                # — never written into `unit` — so the reading stays exactly as
                # stored and billing's Check decides, with a warning, whether to
                # use it. The REGISTER's unit, the string `_post_row` stamps;
                # `None` when the meter records none either (rule 3: never a
                # default). Asked only on this rare branch, so the ordinary path
                # issues no extra query.
                meter_row["meter_unit"] = register_units.register_unit(
                    getattr(read.asset, "unit", None) if read.asset_id else None,
                    read.channel or models.CHANNEL_TOTAL,
                )
            rows.append(meter_row)
    return rows


# ══════════════════════════════════════════════════════════════════════════
# BR-MET-1170 · A READING THE CLERK HAS KEYED AND NOBODY HAS COMMITTED
#
# **PO ruling 2026-09-20, verbatim: *"option b is correct"*** — *price from
# what's keyed, commit at the close* (decision log, *"THE FINAL BILL IS PRICED
# FROM WHAT THE CLERK KEYED; THE READS COMMIT WITH THE CLOSE"*, `DEF-CUS-5931`).
#
# The move-out wizard asks for the closing register on step 2 and prices the
# final bill on step 3, and the Billing blueprint p111 puts the WRITE at step 6:
# *"The reads are committed with the close, not before it. The whole move-out is
# one transaction, so a refused reading rolls the close back with it and
# everything stays on screen."* So at the moment step 3 prices, the closing read
# does not exist, `billing_reads_for_unit` answers `no_read` with no multiplier,
# and `resolution.MeterMultiplierUnstated` refuses the account — correctly, and
# on every move-out in the product.
#
# The option the PO rejected was committing the reads at step 2. Its cost is the
# worked case they were shown: a clerk keys **52,410** on the 28th, reaches step
# 4, is called away and never finishes — and under that option a live meter now
# carries a committed final reading, which the next bill run uses, for a
# move-out that never happened.
#
# ⚠ **THIS FUNCTION WRITES NOTHING, AND THAT IS THE WHOLE POINT OF IT.** No
# `meter_reads` row, no staged batch, no estimate, no lock. It answers what
# `billing_reads_for_unit` WOULD answer once the keyed reading commits, from the
# same registers, the same prior head and the same arithmetic — so a clerk who
# abandons the wizard leaves the meter exactly as they found it.
# ══════════════════════════════════════════════════════════════════════════

#: The key a provisional row carries, and `False`/absent on every row that came
#: from a committed read. Named once so both sides of billing's seam spell it
#: the same way (`apps/billing/runs.py` reads it onto `ServiceReading`).
PROVISIONAL_READ_KEY = "provisional"

#: Why a keyed row produced no quantity, when it produced none. Each is a
#: DIFFERENT fact and a caller may not read any of them as a zero.
PROVISIONAL_ABSENT_ESTIMATE = "provisional_estimate_not_computed"
PROVISIONAL_ABSENT_UNREADABLE = "provisional_value_unreadable"
PROVISIONAL_ABSENT_NO_PRIOR = "provisional_no_prior_register"
#: 🔒 `DEF-BIL-10067` — a keyed value asked to price from a SAVED reading
#: (`KEYED_SAVED_ONLY`) where Meter Reads holds none with that value in the
#: period. Not a zero and not the committed read it would have replaced.
PROVISIONAL_ABSENT_NOT_SAVED = "provisional_value_not_saved"

#: 🔒 `DEF-BIL-10067` (PO 2026-10-12, *"the draft is priced on the reading
#: entered"*) — the two OPTIONS a keyed entry may carry, each `False`/absent
#: on every entry the move-out wizard builds, so its answer is unchanged.
#:
#: `KEYED_WINS_OVER_COMMITTED` — the keyed value replaces a committed read in
#: the period instead of yielding to it. The ONE-TIME BILL sets it: there the
#: clerk types the reading the bill is priced on, over whatever is on file.
#: `KEYED_SAVED_ONLY` — the keyed value prices only where Meter Reads HOLDS a
#: reading of exactly that value in the period (the one step 2's Continue
#: posted), and the row then names THAT read, so issue locks it. The one-time
#: DRAFT sets it; the preview does not.
KEYED_WINS_OVER_COMMITTED = "wins_over_committed"
KEYED_SAVED_ONLY = "saved_reads_only"


def asset_numbers(asset_ids: Any) -> dict[str, str]:
    """`{asset id: asset number}` for MANY assets, in one read, this tenant only.

    `DEF-BIL-8315` (2026-09-30): an issued bill's lines name the meter they were
    priced for by id (`invoice_lines.asset_id`, `billing/0031`), and the bill's
    every-charge list printed no meter at all — two water lines, and no way to
    tell W-10442's from W-10443's. The NUMBER is the asset's, read here through
    the same probe `seams.meter_by_id` uses, and never an id on screen
    (B14 rule 31). An id of another tenant or of no asset is simply absent.
    """
    wanted = {str(one) for one in (asset_ids or ()) if one}
    if not wanted:
        return {}
    from django.apps import apps as django_apps

    from core import tenancy as core_tenancy

    model = django_apps.get_model("assets", "Asset")
    return {
        str(asset_id): str(asset_no)
        for asset_id, asset_no in model.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), pk__in=wanted
        ).values_list("id", "asset_no")
    }


def provisional_reads_for_unit(
    unit_id: Any,
    *,
    period_start: Any,
    period_end: Any,
    keyed_reads: Any,
    service_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """`billing_reads_for_unit`, with the reads a clerk has KEYED laid over it.

    `keyed_reads` is the wizard's step-2 capture in its own shape — the rows
    `moveReadsCapture.eventReadRows` builds and `commit_event_reads` will
    later post: `{"meter_no": "M-4021", "value": "52410"}`, or
    `{"meter_no": …, "estimate": true}`. It is read and never stored.

    **EVERY ROW `billing_reads_for_unit` RETURNS IS RETURNED HERE**, in its
    order, with its facts. A service the clerk did not key comes back byte for
    byte — its asset count, its installed capacity, its size split, its
    windows, its `service_not_metered` declaration — because this function
    overlays a reading and decides nothing else.

    ⚠ **A COMMITTED READ ALWAYS WINS.** Where the period already carries a head
    (`read_id` is not None) the row is left alone, whatever the clerk keyed.
    That is not politeness to the database: the committed read is the one the
    bill will be raised on, and showing a clerk a figure computed from a
    different number is the drift `runs.price_account` was extracted to make
    impossible. It also means an account whose closing read was taken in the
    field before the wizard opened prices EXACTLY as it does today.

    ⚠ **THE FACTOR IS THE METER'S AND IS NEVER 1.** `BR-MET-056` stores the
    factor USED and `resolution.MeterMultiplierUnstated` says *"an absent factor
    is not 1"*. A provisional row carries `asset.multiplier` — the factor the
    commit itself stamps (`services._build_context`, `multiplier=asset
    .multiplier`) — so the preview's quantity and the committed read's quantity
    come from one number. A meter that states no factor produces no provisional
    quantity at all; it is refused by the same rule, one layer up.

    ⚠ **THE ARITHMETIC IS `validation.compute_consumption`, NOT A SECOND
    SUBTRACTION.** That function owns `(current − prior) × multiplier`,
    OQ-009's rollover branch and BR-MET-052's negative-usage refusal, and a
    copy here would be a second answer to *what did this meter measure* — the
    hard-won law 5 failure this seam exists to avoid. Where it cannot compute
    honestly it returns `None`, and this function then leaves the row ABSENT
    with a reason rather than inventing a quantity.

    ⚠ **EXCEPT WHERE THE CALLER SAYS OTHERWISE, PER ENTRY — `DEF-BIL-10067`
    (PO 2026-10-12, *"the draft is priced on the reading entered"*).** An entry
    carrying `KEYED_WINS_OVER_COMMITTED` replaces the committed read: the ONE-
    TIME BILL's step 2 is where the clerk types the reading that bill is priced
    on (walk: W-9011, previous 2.9, a committed 8.0 on 29 Sep, typed 4.6 —
    priced 5.1 kgal until this, 1.7 since). It counts up from the dial the
    period OPENS at (the row's own `prior_value`, which `_chained_from` set),
    names no read unless one is saved, and drops the committed chain so issue
    never locks a read the bill was not priced on. With `KEYED_SAVED_ONLY` as
    well (the one-time DRAFT), it prices only where Meter Reads holds a reading
    of that value in the period — including a same-day sibling BR-MET-1189 does
    not count — and names it; otherwise the row is absent
    (`PROVISIONAL_ABSENT_NOT_SAVED`) and the draft refuses, rather than pricing
    the committed figure the clerk replaced. A row with time-of-use windows or a
    meter exchange (`meter_parts`) keeps its committed read: one typed total
    cannot restate several registers. The move-out wizard sets neither option.

    ⚠ **AN `estimate: true` ROW IS NOT PRICED HERE AND SAYS SO.** US-MET-014's
    estimator is a metering WRITE — it records a disclosed method and counts
    consecutive estimates per register — and a preview may not run it. The row
    comes back absent with `provisional_estimate_not_computed`, which reaches
    the screen as a stated absence and never as a figure.
    """
    rows = billing_reads_for_unit(
        unit_id,
        period_start=period_start,
        period_end=period_end,
        service_codes=service_codes,
    )
    # ── WHICH METER A KEYED VALUE IS FOR ─────────────────────────────────────
    # An entry names its meter by NUMBER (the move-out wizard) or by ID (the
    # one-time bill's step 2, contract §2 `readings[].asset_id`). An optional
    # `prior` is a start reading the clerk keyed in the same breath — a first
    # bill's move-in reading with none on file — and stands in for the
    # register's last head only where the row has no committed read.
    keyed: list[tuple[Any, str | None, str | None, bool, bool]] = []
    for entry in keyed_reads or ():
        meter_no = str(entry.get("meter_no") or "").strip()
        asset_id = str(entry.get("asset_id") or "").strip()
        if not meter_no and not asset_id:
            continue
        prior_raw = str(entry.get("prior") or "").strip() or None
        if entry.get("estimate"):
            value: str | None = None  # remembered so the row can say WHY, not dropped
        else:
            raw = str(entry.get("value") or "").strip()
            if raw == "":
                continue  # ⛔ NOT a zero. An unkeyed register stays unkeyed.
            value = raw
        asset = seams.meter_by_id(asset_id) if asset_id else seams.meter_by_no(meter_no)
        keyed.append(
            (
                asset,
                value,
                prior_raw,
                bool(entry.get(KEYED_WINS_OVER_COMMITTED)),
                bool(entry.get(KEYED_SAVED_ONLY)),
            )
        )
    if not keyed:
        return rows

    # ⚠ **`DEF-BIL-8320` — KEYED BY METER WHERE THE ROW NAMES ONE, BY SERVICE
    # POINT ONLY WHERE IT DOES NOT.** Since 2026-09-30 a metered point carrying
    # two in-service meters publishes ONE ROW PER METER (`asset_id` on the
    # row). Staged by point alone, the second meter's typed value overwrote
    # the first and was laid over BOTH rows. A meter that stands on another
    # unit's point still overlays nothing: both maps are filtered by unit.
    by_point: dict[str, tuple[Any, str | None, str | None, bool, bool]] = {}
    by_asset: dict[str, tuple[Any, str | None, str | None, bool, bool]] = {}
    for entry in keyed:
        asset = entry[0]
        point = getattr(asset, "service_point", None) if asset is not None else None
        if point is None or str(getattr(point, "unit_id", "") or "") != str(unit_id):
            continue
        by_point[str(point.id)] = entry
        by_asset[str(asset.id)] = entry
    if not by_point:
        return rows

    from apps.metering import validation

    for row in rows:
        row_asset = row.get("asset_id")
        # 🔒 `DEF-MET-10111` — a row that names no meter but carries a committed
        # head is resolved by the meter that head was READ ON before the point.
        # By point alone, a sub-meter ticked Estimate on the same point (keyed
        # later) overwrote the main meter's typed value and step 3 dropped it:
        # AC-2026-00043 priced 10 kgal of water where its bill prices 15.
        head_asset = (
            _head_asset_id(row.get("read_id")) if not row_asset and row.get("read_id") else None
        )
        if row_asset:
            entry = by_asset.get(str(row_asset))
        elif head_asset is not None and str(head_asset) in by_asset:
            entry = by_asset[str(head_asset)]
        else:
            # 🔒 `DEF-BIL-10155` / `DEF-BIL-10156` — by point, but only a value
            # keyed on one of the point's BILLING meters (the row's own group,
            # `billing_reads_for_unit`). By point alone the LAST meter keyed on
            # the point won, so a sub-meter's 5 → 6 priced Apt 104's water at
            # 1 kgal, and a never-read sub-meter or a master ticked Estimate on
            # Apt 101 refused the whole draft. A value keyed on a sub-meter or
            # a master is still committed at the close; it is not this bill's.
            point_key = str(row.get("service_point_id") or "")
            billing = {str(one) for one in seams.billing_asset_ids_for_service_point(point_key)}
            entry = next(
                (
                    candidate
                    for candidate in reversed(keyed)
                    if candidate[0] is not None and str(candidate[0].id) in billing
                    and str(getattr(candidate[0], "service_point_id", "") or "") == point_key
                ),
                None,
            ) if billing else by_point.get(point_key)
        if entry is None:
            continue
        asset, value, prior_raw, wins, saved_only = entry
        committed = row.get("read_id") is not None
        if committed and not wins and _extends_the_head(row, value, period_end):
            # 🔒 `DEF-MET-10110` — the keyed reading is LATER than the window's
            # committed head (a read taken on 11 Oct, the move day the 12th),
            # so it is not "the closing read already taken": it is the next
            # reading on the same chain, and the move-out commits it after the
            # head. Priced as head → keyed, exactly what the committed chain
            # will hold once Complete writes it, so step 3 and the drafted
            # final bill price the same dials (DEF-CUS-10093). Ana Alvarez:
            # 2600 → 3400 committed + 3400 → 3450 typed = 850 kWh, never 800.
            _extend_the_head(row, asset, value)
            continue
        if committed and (
            not wins or row.get("windows") or row.get("meter_parts") or value is None
        ):
            # The DEFAULT, and the move-out wizard's: a committed read wins.
            # With `KEYED_WINS_OVER_COMMITTED` too where one typed total cannot
            # restate the row (time-of-use windows, a meter exchange).
            continue
        if value is None:
            row[PROVISIONAL_READ_KEY] = True
            row["absent_reason"] = PROVISIONAL_ABSENT_ESTIMATE
            continue
        try:
            keyed_value = Decimal(value)
            keyed_prior = Decimal(prior_raw) if prior_raw is not None else None
        except (ArithmeticError, ValueError):
            row[PROVISIONAL_READ_KEY] = True
            # What a clerk typed is not a number. Reported as an absence rather
            # than coerced — a coerced register is a bill.
            row["absent_reason"] = PROVISIONAL_ABSENT_UNREADABLE
            continue
        if (
            committed
            and keyed_prior is None
            and row.get("current_value") is not None
            and Decimal(row["current_value"]) == keyed_value
        ):
            # The committed read already says what the clerk typed: metering's
            # own row, chain and rollover answer stand, byte for byte.
            continue
        saved = (
            _saved_keyed_read(asset, keyed_value, period_start, period_end) if wins else None
        )
        if saved_only and saved is None:
            if committed:
                # 🔒 DEF-BIL-10067 — the clerk replaced the committed figure
                # and their reading is not in Meter Reads: no quantity, never
                # the committed one the screen did not show.
                row[PROVISIONAL_READ_KEY] = True
                row["consumption"] = None
                row["absent_reason"] = PROVISIONAL_ABSENT_NOT_SAVED
                row["read_id"] = None
                row["chain_read_ids"] = []
            continue
        # The flag says THE OVERLAY computed this row's quantity, which it did
        # even where it names a saved read (billing's split reads it to share
        # a typed reading by days — `midperiod._apportion_evenly_by_day`).
        row[PROVISIONAL_READ_KEY] = True
        measured_from = None
        if committed:
            # 🔒 DEF-BIL-10067 — the period's quantity is the TYPED dial less
            # the dial the period opens at, which is the row's own prior (the
            # opening of `_chained_from`'s chain), never the committed read it
            # replaces. Nothing of the committed chain is locked by this bill.
            opening = row.get("prior_value")
            measured_from = row.get("measured_from")
            row["read_id"] = None
            row["chain_read_ids"] = []
            row["rollover"] = None
            row["estimated"] = False
            prior = (
                _read_heads()
                .filter(
                    asset_id=asset.id,
                    channel=models.CHANNEL_TOTAL,
                    current_value__isnull=False,
                    read_at__lt=_day_start(period_start),
                )
                .order_by("-read_at", "-id")
                .first()
            )
            if keyed_prior is None and opening is not None:
                keyed_prior = Decimal(opening)
        else:
            prior = (
                _read_heads()
                .filter(
                    asset_id=asset.id,
                    channel=models.CHANNEL_TOTAL,
                    current_value__isnull=False,
                    read_at__lt=_day_after(period_end),
                )
                .order_by("-read_at", "-id")
                .first()
            )
        if saved is not None:
            row["read_id"] = str(saved.id)
            row["chain_read_ids"] = [str(saved.id)]
        ctx = validation.ReadContext(
            value=keyed_value,
            channel=models.CHANNEL_TOTAL,
            # BR-MET-143 — the REGISTER's unit, exactly as the commit stamps it.
            unit=register_units.register_unit(asset.unit, models.CHANNEL_TOTAL),
            multiplier=asset.multiplier,
            register_digits=asset.register_digits,
            prior_value=(
                keyed_prior
                if keyed_prior is not None
                else (prior.current_value if prior is not None else None)
            ),
            prior_read_at=prior.read_at if prior is not None else None,
        )
        consumption, _outcome = validation.compute_consumption(ctx)
        # The two register values reach the row whatever happens next, because
        # a screen asking a human to judge a reading has to be able to show the
        # number it is asking about (`billing_reads_for_unit`'s own posture on
        # its unbillable branch).
        row["prior_value"] = ctx.prior_value
        row["current_value"] = keyed_value
        row["multiplier"] = asset.multiplier
        # DEF-BIL-8324 — a keyed reading measures from the prior head it counts
        # up from; a keyed START reading names no day, so none is claimed.
        row["measured_from"] = (
            measured_from
            if measured_from is not None
            else prior.read_at.date() if keyed_prior is None and prior is not None else None
        )
        if consumption is None or ctx.unit is None:
            # A missing prior register, a wrap that cannot be told from a
            # mistype, BR-MET-052's negative usage, or a meter with no declared
            # UoM. None of them is a zero and none of them is priced.
            row["absent_reason"] = (
                PROVISIONAL_ABSENT_NO_PRIOR
                if ctx.prior_value is None
                else READ_ABSENT_FLAGGED
            )
            continue
        row["absent_reason"] = None
        row["consumption"] = consumption
        row["unit"] = ctx.unit  # rule 3 — never separated from the number
    return rows


def _head_asset_id(read_id: Any) -> Any:
    """The meter a committed head read was taken on, or None (`DEF-MET-10111`)."""
    return (
        models.MeterRead.objects.filter(id=read_id).values_list("asset_id", flat=True).first()
    )


def _extends_the_head(row: dict[str, Any], value: str | None, period_end: Any) -> bool:
    """🔒 `DEF-MET-10110` — is this keyed value the NEXT reading after the window's head?

    True only for a plain total register (no time-of-use windows, no meter
    exchange) whose committed head was read BEFORE the window's last day and
    whose keyed value is a number different from the head's dial. A head read
    ON the last day is the field read taken before the wizard opened, and it
    still wins (the docstring above); a keyed value equal to the head says
    nothing new.
    """
    if value is None or row.get("windows") or row.get("meter_parts"):
        return False
    if row.get("current_value") in (None, ""):
        return False
    try:
        keyed = Decimal(str(value))
    except (ArithmeticError, ValueError):
        return False
    if keyed == Decimal(str(row["current_value"])):
        return False
    head = (
        models.MeterRead.objects.filter(id=row["read_id"]).only("read_at").first()
        if row.get("read_id")
        else None
    )
    return head is not None and head.read_at < _day_start(period_end)


def _extend_the_head(row: dict[str, Any], asset: Any, value: str) -> None:
    """Lay the keyed reading ON TOP of the committed chain: head dial → keyed dial.

    `validation.compute_consumption` owns the subtraction, the factor and
    BR-MET-052's negative-usage refusal; a refusal leaves the row ABSENT and
    flagged, never priced at the committed figure the screen did not show.
    The committed chain stays named (`read_id`, `chain_read_ids`) — those reads
    ARE on the bill — and `PROVISIONAL_READ_KEY` says the overlay added to it.
    """
    from apps.metering import validation

    head = models.MeterRead.objects.filter(id=row["read_id"]).only("read_at").first()
    ctx = validation.ReadContext(
        value=Decimal(str(value)),
        channel=models.CHANNEL_TOTAL,
        unit=register_units.register_unit(asset.unit, models.CHANNEL_TOTAL),
        multiplier=asset.multiplier,
        register_digits=asset.register_digits,
        prior_value=Decimal(str(row["current_value"])),
        prior_read_at=head.read_at if head is not None else None,
    )
    added, _outcome = validation.compute_consumption(ctx)
    row[PROVISIONAL_READ_KEY] = True
    row["current_value"] = ctx.value
    if added is None or ctx.unit is None or row.get("consumption") is None:
        row["consumption"] = None
        row["absent_reason"] = READ_ABSENT_FLAGGED
        return
    row["consumption"] = Decimal(str(row["consumption"])) + added
    row["absent_reason"] = None


def _saved_keyed_read(asset: Any, value: Decimal, period_start: Any, period_end: Any) -> Any:
    """🔒 `DEF-BIL-10067` — the reading Meter Reads holds for a value the clerk
    keyed: this meter's total register, inside the period, at exactly that dial,
    billable. The newest if several. None when there is none.

    Read over `_register_heads()` and NOT `_read_heads()`, deliberately: the
    one-time bill's step-2 Continue posts the typed reading on the date of the
    reading it replaces (29 Sep beside a committed 8.0), and BR-MET-1189 then
    counts only the higher-consumption sibling of the two — so the reading the
    clerk saved is exactly the one the counted set hides."""
    return (
        _register_heads()
        .filter(
            asset_id=asset.id,
            channel=models.CHANNEL_TOTAL,
            current_value=value,
            read_at__gte=_day_start(period_start),
            read_at__lt=_day_after(period_end),
        )
        .exclude(status__in=UNBILLABLE_READ_STATUSES)
        .order_by("-read_at", "-id")
        .first()
    )


@batch_reads.memoised
def _prior_head_day(read: Any) -> date | None:
    """The day of the register read this one counts up from, when the row did
    not store `period_start` (an imported history row, say). The latest earlier
    head on the same meter and channel that carries a register value — the
    same prior `_post_row` would have stamped. None when there is none."""
    prior = (
        _read_heads()
        .filter(
            asset_id=read.asset_id,
            channel=read.channel,
            read_at__lt=read.read_at,
            current_value__isnull=False,
        )
        .order_by("-read_at", "-id")
        .values_list("read_at", flat=True)
        .first()
    )
    return prior.date() if prior is not None else None


def back_bill_segment_estimate(
    unit_id: Any,
    *,
    service_code: str,
    period_start: Any,
    period_end: Any,
    asset_id: Any = None,
) -> dict[str, Any]:
    """BR-MET-026's estimate for ONE meter over ONE window. WRITES NOTHING.

    ── `DEF-BIL-8324` · PO ruling 2026-09-30, verbatim: *"A for catch-up
    estimate"* (BR-BIL-018) ──────────────────────────────────────────────
    A catch-up stretch where a meter was NEVER read has nothing to day-weight,
    and the PO ruled it is priced on the meter's OWN estimate from its reading
    history — OQ-191's option C, used as the fallback. This is the read-only
    half `apps/billing/backbill.METERING_ESTIMATE_ATTRIBUTE` has named since
    2026-08-12 and that nothing published.

    **ONE IMPLEMENTATION OF THE RULE.** The arithmetic is `estimation.estimate`
    and the inputs are the same three helpers `services.estimate_missing_read`
    uses — the tenant's config, this channel's ACTUAL trailing history before
    the window (BR-MET-026 / BR-MET-058) and the estimates already standing
    since the last actual (BR-MET-027's cap). The one difference is that no
    `meter_reads` row is written: a phase-1 prepare writes nothing.

    Returns `EstimationResult.as_dict()` — an estimate with its working, or a
    refusal with metering's own reason (`no_history`, `consecutive_estimate_
    cap_reached`, …). `asset_id` names the meter where a point carries two; with
    none named, a point holding exactly one in-service meter answers for it and
    any other count refuses `meter_not_named` rather than guessing.
    """
    from apps.metering import estimation
    from apps.metering import services as metering_services

    asset = seams.meter_by_id(asset_id) if asset_id else None
    if asset is None:
        point = _service_point_for(unit_id, service_code)
        in_service = (
            seams.in_service_asset_ids_for_service_point(point.id) if point is not None else None
        )
        if not in_service or len(in_service) != 1:
            return {"estimated": False, "reason": "meter_not_named", "detail": {}}
        asset = seams.meter_by_id(in_service[0])
    if asset is None:
        return {"estimated": False, "reason": "meter_not_named", "detail": {}}
    start = period_start if isinstance(period_start, date) else date.fromisoformat(str(period_start))
    end = period_end if isinstance(period_end, date) else date.fromisoformat(str(period_end))
    before = datetime.combine(start, datetime.min.time(), tzinfo=timezone.get_current_timezone())
    channel = models.CHANNEL_TOTAL
    spec = estimation.EstimationInput(
        channel=channel,
        unit=register_units.register_unit(asset.unit, channel),
        days_in_period=(end - start).days + 1,
        # 12 back, so a tenant on `same_period_last_year` has its year; the
        # method's own window decides which of them it averages (CR-079).
        trailing_actuals=metering_services._trailing_actuals(asset.id, channel, before, limit=12),
        consecutive_estimates=len(metering_services._standing_estimates(asset.id, channel, before)),
    )
    result = estimation.estimate(spec, metering_services._read_config())
    return {**result.as_dict(), "asset_id": str(asset.id)}


# ══════════════════════════════════════════════════════════════════════════
# BR-MET-500 · THE TWO PER-CONNECTION FACTS BILLING RESOLVES BY NAME
#
# `apps/billing/gather.py` has resolved `connection_size_for` through
# `_resolve("metering", "connection_size_for")` since the DEF-438 cutover
# step-5 lane (2026-08-21) and got `None` every time, because no row in this
# product recorded a connection size (DEF-514). `apps/billing/resolution_shadow
# .py` resolves the same name, plus `billing_multiplier_for`, and reported
# `attempted 0 · blocked {connection_size_unresolved: 1}` on 1 of 1 accounts of
# a provisioned tenant (DEF-1811). Neither caller changes to consume these; the
# hop was already built and proved, and what was missing was the SOURCE.
#
# Both live in METERING and not in assets, because billing must never join to
# assets (B1 §2 — assets is reached through the module that owns the service
# point). Both take `(unit_id, service_code)` and not an account, because a
# house on water and electric has TWO connections and they need not be the same
# size: a per-account answer could only ever be one of them, and the per-size
# ladder is per SCHEDULE, which is per service.
# ══════════════════════════════════════════════════════════════════════════


@batch_reads.memoised
def _live_service_points(unit_id: Any) -> tuple[Any, ...]:
    """This unit's LIVE service points, with their service, in id order — the
    set `billing_reads_for_unit`, `read_analysis_for_unit` and
    `_service_point_for` each read (tenant-scoped, `deleted_at` filtered).

    One definition for the three, memoised for a bulk Check batch (B27) and
    primed for the whole batch by `prime_check_batch`."""
    return tuple(
        models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_id, deleted_at__isnull=True
        )
        .select_related("service")
        .order_by("id")
    )


def _live_service_points_for(unit_id: Any, service_codes: Any = None) -> list[Any]:
    """`_live_service_points`, narrowed to `service_codes` when given — the
    `service_id__in=service_ids_for_codes(...)` filter, applied to the rows."""
    points = list(_live_service_points(unit_id))
    if service_codes is None:
        return points
    wanted = set(seams.service_ids_for_codes(service_codes))
    return [point for point in points if point.service_id in wanted]


@batch_reads.memoised
def _asset_heads(asset_id: str, period_start: Any, period_end: Any) -> tuple[Any, ...]:
    """ONE meter's committed heads inside `[period_start, period_end]` (either
    bound optional), NEWEST FIRST (`-read_at, -id`), each with its asset.

    Memoised for a bulk Check batch and primed for every meter of the batch by
    `prime_check_batch` in one query (B27)."""
    heads = _read_heads().filter(asset_id=asset_id).select_related("asset")
    if period_start is not None:
        heads = heads.filter(read_at__gte=_day_start(period_start))
    if period_end is not None:
        heads = heads.filter(read_at__lt=_day_after(period_end))
    return tuple(heads.order_by("-read_at", "-id"))


def _period_heads(asset_ids: Any, period_start: Any, period_end: Any) -> list[Any]:
    """The committed heads of these meters inside the period, NEWEST FIRST.

    ⚠ **THE ORDER IS THE CONTRACT.** Every reader takes "the first head that
    …" off this list, which is what `.order_by("-read_at", "-id").first()`
    answered when each asked the database on its own. Python orders a UUID by
    its 128-bit value and PostgreSQL by its 16 bytes, which is the same order,
    so `(read_at, id)` descending here is `-read_at, -id` there.

    Outside a bulk Check batch this is ONE query for all the meters (it used
    to be one per register asked about); inside one it is served from the
    batch's single read of every meter's heads (B27)."""
    ids = [str(one) for one in asset_ids]
    if batch_reads.active() is None:
        heads = _read_heads().filter(asset_id__in=ids).select_related("asset")
        if period_start is not None:
            heads = heads.filter(read_at__gte=_day_start(period_start))
        if period_end is not None:
            heads = heads.filter(read_at__lt=_day_after(period_end))
        return list(heads.order_by("-read_at", "-id"))
    rows: list[Any] = []
    for one in dict.fromkeys(ids):
        loaded = _loaded_heads(one, period_start, period_end)
        rows.extend(loaded if loaded is not None else _asset_heads(one, period_start, period_end))
    rows.sort(key=lambda head: (head.read_at, head.id), reverse=True)
    return rows


#: The batch store `prime_check_batch` keeps each meter's heads under:
#: `(window_start, every head from that day on, newest first)` — open-ended,
#: so a later read (after the period) is in it too and "the newest" is knowable.
_HEADS_WINDOW = "metering.heads_window"


def _loaded_heads(asset_id: str, period_start: Any, period_end: Any) -> tuple[Any, ...] | None:
    """This meter's heads inside the period, taken from the batch's one read
    of every meter's heads over a WINDOW — when the window covers the period.

    None when no batch loaded this meter or its window does not cover the
    period (no start, an account whose bill starts earlier): the caller then
    reads it on its own, exactly as without a batch. The same
    `[day start, next day start)` bounds as the query, applied to the rows."""
    if period_start is None:
        return None
    found = batch_reads.get(_HEADS_WINDOW, asset_id)
    if found is None:
        return None
    window_start, heads = found
    if _as_day(period_start) < window_start:
        return None
    low = _day_start(period_start)
    high = _day_after(period_end) if period_end is not None else None
    return tuple(
        head for head in heads if low <= head.read_at and (high is None or head.read_at < high)
    )


def _newest_consumption_head(asset_ids: Any, period_start: Any, period_end: Any) -> Any:
    """`_latest_consumption_head(_period_heads(...))` — with one more way to
    answer inside a batch: an ask with NO START (`billing_multiplier_for`'s
    *"the latest billable head"*) is answered from the batch's open-ended read
    when that read holds a consumption head at or before the end. Every head
    from the window's start on is in it, so the newest one there is the newest
    anywhere; when there is none, the meters are asked, as before."""
    ids = [str(one) for one in asset_ids]
    if period_start is None and batch_reads.active() is not None:
        loaded = [batch_reads.get(_HEADS_WINDOW, one) for one in dict.fromkeys(ids)]
        if loaded and all(found is not None for found in loaded):
            high = _day_after(period_end) if period_end is not None else None
            candidates = [
                head
                for _start, heads in loaded
                for head in heads
                if head.channel not in _NOT_CONSUMPTION and (high is None or head.read_at < high)
            ]
            if candidates:
                return max(candidates, key=lambda head: (head.read_at, head.id))
    return _latest_consumption_head(_period_heads(ids, period_start, period_end))


#: The registers that are never the period's consumption (see below).
_NOT_CONSUMPTION = frozenset(
    (*models.TOU_WINDOW_CHANNELS, models.CHANNEL_DEMAND, *models.NON_CONSUMPTION_CHANNELS)
)


def _latest_consumption_head(heads: list[Any]) -> Any:
    """The newest head on a CONSUMPTION register — `heads` newest first.

    The window and demand registers are separate MEASUREMENTS of the
    same service point, published above. Letting one of them win the
    "latest head" race made it the period's whole consumption.

    ⚠ **`export` AND `generation` JOINED THIS LIST ON 2026-08-26 AND
    `export` WAS ALWAYS MISSING FROM IT — A LIVE DEFECT ON THE MONEY
    PATH (CR-038 W6, REPORTED for a defect row).** This is the seam
    billing reads for a period's usage. `_ensure_export_records`
    writes a net meter's export row with the SAME `read_at` as its
    total row and a LATER uuid7 id, so `-read_at, -id` picked the
    EXPORT record — a 0-value row with `status='missing'` — as the
    service's consumption. The net meter's real usage never reached
    the bill. `generation` (BR-MET-135) is the same hazard on new
    equipment: a solar device's 612 kWh is production, *"never summed
    with consumption"*, and it must never win this race either.
    `models.NON_CONSUMPTION_CHANNELS` is the named set, so the next
    non-consumption register joins it in the commit that mints it.
    """
    return next((head for head in heads if head.channel not in _NOT_CONSUMPTION), None)


def _later_actual_covering(asset_ids: Any, period_end: Any) -> Any:
    """🔒 DEF-MET-10163 — the earliest LATER actual reading that already covers
    `period_end`, or None. HUMAN-REVIEW-PENDING (billing reads seam).

    PO ruling 2026-10-15, verbatim *"go with 1 and 3"*; option 3 as put: *"also
    stop a bill run estimating days a later actual already covers"*. Worked:
    AC-2026-00049's September closes 09/30 with its last reading on 09/24; the
    10/06 actual (5,176 → 6,376, measured FROM 09/24) already spans 09/30, so an
    estimate for September would count 09/24–09/30 twice (560 kWh on top of the
    1,200 the 10/06 reading carries).

    A counted lineage head on a CONSUMPTION register of these meters, dated
    after `period_end`, measuring from on or before it (`period_start`), with a
    register value (an actual — BR-MET-028) and a billable status — because
    billing will price that reading on the next bill, a reading billing would
    refuse cannot stand in for the estimate. A row with no `period_start`
    covers nothing: an unknown interval is never assumed to span the period.

    One query, and only for a meter that has no reading in the period — the
    rare branch of the seam, not the hot one.
    """
    if period_end is None:
        return None
    return (
        _read_heads()
        .filter(
            asset_id__in=[str(one) for one in asset_ids],
            read_at__gte=_day_after(period_end),
            period_start__lte=_as_day(period_end),
            current_value__isnull=False,
            consumption__isnull=False,
        )
        .exclude(status__in=sorted(UNBILLABLE_READ_STATUSES | {"estimated"}))
        .exclude(channel__in=sorted(_NOT_CONSUMPTION))
        .order_by("read_at", "id")
        .first()
    )


def prime_check_batch(
    unit_ids: Any, *, period_start: Any, period_end: Any, reads_from: Any = None
) -> dict[str, int]:
    """B27 — ONE BULK CHECK BATCH'S METERING FACTS, IN A HANDFUL OF QUERIES.

    Billing's bulk Check asks this module, one account at a time, for the
    unit row, its live service points (three shapes), the meters on each
    point (through assets), each meter's heads in the period, the prior head
    a read counts up from, and the unit's open disputes — about 45 statements
    an account (`19-check-cost-measured.md` §3). This answers the whole batch's
    questions in one query each and PRIMES the batch memo (`core.batch_reads`)
    with exactly what each per-account read returns, keyed as it will be asked.
    Nothing is primed outside a batch.

    ⚠ **SAME ROWS, SAME ORDER, SAME BUILDER.** Each list is taken from ONE
    query carrying the per-account read's own `ORDER BY` and split by unit,
    point or meter, so the order inside a split is the database's; each row is
    built by the per-account read's own builder (`_dispute_row`, the model
    rows themselves). A question this does not prime — a master account's
    other units, an account whose bill starts before the pass's period — is
    simply asked per account, as before. `test_b27_batch_reads` holds the
    batch answer equal to the per-account one on a mixed seed.
    """
    if batch_reads.active() is None:
        return {}
    ids = sorted({str(u) for u in (unit_ids or ()) if _is_uuid(u)})
    if not ids:
        return {}
    tenant_id = _tenant_id()

    # The unit rows — `unit_row`.
    for row in models.Unit.objects.filter(tenant_id=tenant_id, pk__in=ids).select_related(
        "premises"
    ):
        batch_reads.prime(unit_row, row, str(row.id))

    # The live service points — `_live_service_points` (id order) and
    # `service_points_for` (`created_at, id` order).
    points = list(
        models.ServicePoint.objects.filter(
            tenant_id=tenant_id, unit_id__in=ids, deleted_at__isnull=True
        )
        .select_related("service")
        .order_by("id")
    )
    by_unit: dict[str, list[Any]] = {unit_id: [] for unit_id in ids}
    for point in points:
        by_unit.setdefault(str(point.unit_id), []).append(point)
    for unit_id, mine in by_unit.items():
        batch_reads.prime(_live_service_points, tuple(mine), unit_id)
        batch_reads.prime(
            service_points_for,
            [
                {
                    "id": str(point.id),
                    "service": point.service.code if point.service_id else None,
                    "route_id": str(point.route_id) if point.route_id else None,
                }
                for point in sorted(mine, key=lambda p: (p.created_at, p.id))
            ],
            unit_id,
        )

    # The meters on each point, and on each unit — assets' own batch read.
    on_point = seams.prime_assets_for_check(
        {
            unit_id: tuple(sorted({p.service.code for p in mine if p.service_id}))
            for unit_id, mine in by_unit.items()
        },
        [point.id for point in points],
        as_of=period_end,
    )
    meters = sorted({a for ids_ in on_point.values() for a in ids_})

    # Every meter's heads from `reads_from` ON (open-ended) — newest
    # first, kept per meter so any period inside the window is answered from
    # it (`_loaded_heads`): the pass's own period, and the span back to each
    # account's last bill that the anchor read is found in (`reads_from`,
    # the earliest of those, which billing names).
    window_start = _as_day(reads_from if reads_from is not None else period_start)
    window_start = min(window_start, _as_day(period_start))
    heads_by_meter: dict[str, list[Any]] = {meter: [] for meter in meters}
    if meters:
        for head in (
            _read_heads()
            .filter(asset_id__in=meters, read_at__gte=_day_start(window_start))
            .select_related("asset")
            .order_by("-read_at", "-id")
        ):
            heads_by_meter.setdefault(str(head.asset_id), []).append(head)
    for meter, heads in heads_by_meter.items():
        batch_reads.put(_HEADS_WINDOW, meter, (window_start, tuple(heads)))

    # The register value each of those heads counts up from, where the row
    # stored no `period_start` — `_prior_head_day`, one correlated read.
    undated = [h.id for heads in heads_by_meter.values() for h in heads if not h.period_start]
    if undated:
        # `_register_heads`, not `_read_heads`: this asks only for the prior
        # reading's DATE, which two same-day siblings share (BR-MET-1189), and
        # a window-filtered queryset is not used as a correlated subquery.
        prior = (
            _register_heads()
            .filter(
                asset_id=OuterRef("asset_id"),
                channel=OuterRef("channel"),
                read_at__lt=OuterRef("read_at"),
                current_value__isnull=False,
            )
            .order_by("-read_at", "-id")
            .values("read_at")[:1]
        )
        found = dict(
            _read_heads()
            .filter(id__in=undated)
            .annotate(prior_at=Subquery(prior))
            .values_list("id", "prior_at")
        )
        for heads in heads_by_meter.values():
            for head in heads:
                if head.id in found:
                    at = found[head.id]
                    batch_reads.prime(_prior_head_day, at.date() if at is not None else None, head)

    # The unit's uncleared disputes — `dispute_holds_for_unit`, newest first.
    unit_of_meter = {}
    for point in points:
        for meter in on_point.get(str(point.id), ()):
            unit_of_meter[meter] = str(point.unit_id)
    held: dict[str, list[dict[str, Any]]] = {unit_id: [] for unit_id in ids}
    if meters:
        for row in (
            _read_heads()
            .filter(asset_id__in=meters, disputed_at__isnull=False, dispute_cleared_at__isnull=True)
            .select_related("asset")
            .order_by("-disputed_at")
        ):
            held.setdefault(unit_of_meter.get(str(row.asset_id), ""), []).append(_dispute_row(row))
    for unit_id in ids:
        batch_reads.prime(dispute_holds_for_unit, held.get(unit_id, []), unit_id)
    return {"units": len(ids), "service_points": len(points), "meters": len(meters)}


def _service_point_for(unit_id: Any, service_code: str) -> Any:
    """This unit's live service point for one service, or None.

    Tenant-scoped and `deleted_at`-filtered exactly as `billing_reads_for_unit`
    does it, so the two seams can never disagree about which point they mean.
    """
    service_ids = seams.service_ids_for_codes([service_code])
    if not service_ids:
        return None
    wanted = set(service_ids)
    return next(
        (point for point in _live_service_points(unit_id) if point.service_id in wanted), None
    )


def _connection_top_assets(unit_id: Any, service_code: str) -> list[dict[str, Any]]:
    """The assets that SIZE this unit's connection for one service — the ones
    currently on the unit and on its service point whose parent is NOT also on
    that connection. 🔒 HUMAN-REVIEW-PENDING — `DEF-MET-9773`.

    ONE set, read by all three of `connection_size_for` (the size),
    `unsized_meters_for` (the meter the Check names when there is none) and
    `connection_asset_ids_for` (where the bulk Check's inline size fix writes),
    so the meter named, the meter written and the meter read cannot drift.

    A sub-meter or device whose parent stands on the same connection
    (BR-AST-003) is left out: it is part of that meter's connection, not a
    second claim on its size. One whose parent stands elsewhere — an apartment
    submetered off the building's master meter — is the top of its own unit's
    connection and stays in. `[]` when the unit has no connection for the
    service.
    """
    point = _service_point_for(unit_id, service_code)
    if point is None:
        return []
    on_point = {str(asset_id) for asset_id in seams.asset_ids_for_service_point(point.id)}
    if not on_point:
        return []
    on_connection = [
        asset for asset in seams.assets_on_unit(unit_id) if str(asset.get("id")) in on_point
    ]
    ids = {str(asset.get("id")) for asset in on_connection}
    return [
        asset
        for asset in on_connection
        if not (asset.get("parent_asset_id") and str(asset.get("parent_asset_id")) in ids)
    ]


def connection_size_for(unit_id: Any, service_code: str) -> str | None:
    """BR-MET-500 / BR-AST-500 — this connection's `service_size_classes.code`,
    or None where nobody has recorded one. **Billing's seam for R3's size axis.**

    Answered from `assets.Asset.size_class` through the assets seam, never by
    joining: assets owns the meter, metering owns the service point, and B1
    draws the boundary at exactly this join. The size lives on the DEVICE
    because BR-RAT-108 puts it there (PO verbatim: *"based on Asset and Account
    type you will have select 1 base charge"*) and because it travels with the
    device — a 5/8" meter moved to another premises is still a 5/8" meter.

    ⚠ **`None` IS A REAL ANSWER AND IT IS NEVER A GUESS.** It means *"no size is
    recorded for this connection"*, which after DEF-514 is a data state a human
    can fix rather than a product that cannot hold the fact. The caller must not
    read it as a size: `gather` refuses BY NAME
    (`connection_size_unresolved_for_sized_schedule`) whenever the version in
    force carries per-size overrides and no size came back, so a tenant who
    typed a 2" ladder gets a named exception on the run screen instead of a bill
    that is quietly short. A defaulted size would pick a tier ladder — money —
    on the strength of nothing.

    ⚠ **TWO METERS ON ONE SERVICE POINT DISAGREEING ABOUT THE SIZE ANSWER
    `None`, DELIBERATELY (decision log 2026-08-27).** One connection has one
    size; two different recorded sizes on one point is a data error, and the
    only two things this function could do about it are *pick one* — which
    selects a tier ladder, and therefore prices a bill, on a coin toss — or
    *say it cannot tell*. It says it cannot tell, and the caller's existing
    named refusal carries it to a human. A meter with no size recorded beside a
    meter with one is NOT a disagreement: absence is not a competing claim, so
    the recorded size wins and the account bills.

    🔒 HUMAN-REVIEW-PENDING — `DEF-MET-9773` (2026-10-06). **THE MAIN METER
    SIZES THE CONNECTION; WHAT HANGS UNDER IT ON THE SAME CONNECTION DOES NOT.**
    The 2026-08-27 rule above was written about two METERS and is kept exactly:
    two top-level meters with two sizes still answer `None`. It was never about
    a sub-meter or a device under one (BR-AST-003) — an irrigation sub-meter
    measures PART of what its main meter measures, so its size says nothing
    about how big the connection is. Until this fix it was read as a competing
    claim: Rosa Delgado's 300 Willow Court Apt 2B, main 3/4" (`W-34`) with a
    5/8" (`W-58`) irrigation sub-meter under it, answered `None` and her first
    bill refused *"This connection's size is not recorded"* with both sizes
    recorded; and an UNSIZED main with a sized sub-meter answered the
    sub-meter's size, pricing the connection off the wrong device. Now Rosa's
    connection is `W-34`, and the unsized main answers `None`. **"Under" means
    under an asset ON THIS SAME CONNECTION** (`_connection_top_assets`): an
    apartment submetered off a master meter that stands on ANOTHER unit has
    its sub-meter at the top of its own connection, and that size still
    prices the apartment. No rate, price or signed figure moves.

    Only meters CURRENTLY assigned to the unit are considered. A retired meter
    still on the service point produced reads the period may be billed on
    (`asset_ids_for_service_point` includes it by its own stated reason), but it
    is not what the connection IS today, and the size answers *what is connected
    now*.
    """
    sizes: set[str] = set()
    for asset in _connection_top_assets(unit_id, service_code):
        size = asset.get("size_class")
        size = (str(size).strip() or None) if size else None
        if size is not None:
            sizes.add(size)
    # Exactly one recorded size is the answer; none and "two that disagree" are
    # both "this connection's size is unresolved" — see the docstring.
    return sizes.pop() if len(sizes) == 1 else None


def unsized_meters_for(unit_id: Any, service_code: str) -> list[str]:
    """The METER NUMBERS (`asset_no`) currently on this unit's connection for
    one service that carry NO recorded size — read-only, `[]` when there is no
    connection or every meter on it has a size.

    PO ruling 2026-10-01 (decision log *"A METER WITH NO RECORDED SIZE GETS NO
    MINIMUM, AND THE BILL-RUN CHECK FLAGS IT"*, option A): such a connection
    bills no minimum and the Check names the account AND THE METER. The same
    set `connection_size_for` reads a size off, so the meter named is the one
    whose size, once recorded, brings that size's minimum back. A unit with no
    connection for the service (sewer following its basis) answers `[]` — no
    meter, nothing to record, no warning.
    """
    return sorted(
        str(asset.get("asset_no") or "")
        for asset in _connection_top_assets(unit_id, service_code)
        if not (str(asset.get("size_class") or "").strip())
    )


def connection_asset_ids_for(unit_id: Any, service_code: str) -> list[str]:
    """The assets CURRENTLY assigned to this unit's connection for one service —
    exactly the set `connection_size_for` reads a size off, so a size written to
    them is the size that seam then answers. READ-ONLY; `[]` when the unit has
    no live connection for the service (the bulk run's inline size fix,
    DEF-BIL-8218, then has nothing to write to and says so)."""
    return sorted(
        str(asset.get("id")) for asset in _connection_top_assets(unit_id, service_code)
    )


def billing_multiplier_for(
    unit_id: Any,
    service_code: str,
    *,
    period_start: Any = None,
    period_end: Any = None,
) -> Any:
    """BR-MET-500 / BR-MET-056 — the meter multiplier this connection's read
    was computed with, or None where no read states one. **Billing's seam for
    R3b's quantity.**

    ⚠ **`billing_reads_for_unit`'s `multiplier` KEY IS THE AUTHORITATIVE
    ANSWER, AND THIS FUNCTION IS THE ONE FOR A CALLER THAT HAS NO ROW IN HAND.**
    The key travels on the SAME row as the `prior_value`/`current_value` the
    quantity is derived from, so it can never name a different read from the one
    being priced. This function is reached by `resolution_shadow._multiplier_for`,
    which holds an account and a service code and no reading row; called without
    a period it answers from the LATEST billable head, which is the same read
    that seam would have chosen for an open period and may not be for a closed
    one. **Pass `period_start`/`period_end` when you have them** — then the two
    answers are the same read by construction.

    ⚠ **NEVER 1 ON THE ABSENT BRANCH.** `resolution.MeterMultiplierUnstated`
    exists for this and its own message says *"an absent factor is not 1"*: a
    ×10 register whose factor nobody recorded would bill a TENTH of the
    customer's consumption on a document that looks entirely normal, and — worse
    for the cutover this seam serves — a defaulted 1 makes the shadow report
    parity by construction on every ×1 meter, which is most of them.

    Returns the stored `Decimal` untouched. Rule 3 does not apply: a multiplier
    is a ratio and carries no unit — the UNIT travels with the consumption, on
    the row beside it.
    """
    point = _service_point_for(unit_id, service_code)
    if point is None:
        return None
    asset_ids = seams.asset_ids_for_service_point(point.id)
    if not asset_ids:
        return None
    # The same exclusion `billing_reads_for_unit` applies, for the same
    # reason: a window, demand, export or generation register is a separate
    # MEASUREMENT and its factor is not this service's billing factor.
    read = _newest_consumption_head(asset_ids, period_start, period_end)
    return None if read is None else read.multiplier


def billable_asset_count(unit_id: Any, service_code: str, as_of: Any) -> int | None:
    """BR-MET-710 / BR-RAT-090 — how many of this service's assets stand on this
    unit on `as_of`, or `None` where nobody can say. **Billing's seam for R3b's
    UNMETERED quantity.**

    ⚠ **`billing_reads_for_unit`'s `asset_count` KEY IS THE AUTHORITATIVE
    ANSWER, AND THIS FUNCTION IS THE ONE FOR A CALLER THAT HAS NO ROW IN HAND.**
    Exactly the split `billing_multiplier_for` records against the `multiplier`
    key, and for the same reason: the key travels on the row the service is
    being priced from, so it can never name a different unit or a different
    date from the one being billed. `resolution_shadow` holds an account and a
    service code, so it reads this — passing the period end it is shadowing, so
    the two answers are the same count by construction.

    ⚠ **NEVER `0` ON THE ABSENT BRANCH.** `0` is *"the utility looked and this
    unit has no carts"*, which is a real answer and bills nothing for carts;
    `None` is *"nobody looked"*, and `resolution.AssetCountUnavailable` refuses
    on it. A `None` read as a `0` bills a three-cart household `$0.00` for trash
    on a document that looks entirely normal — and, for the R1–R7 cutover this
    seam serves, it would make the shadow report agreement on every unmetered
    service by construction, exactly as a defaulted multiplier would.

    Answered through the assets seam, never by joining: assets is B2 r4's table
    and B1 draws the boundary at that join. `None` also when this unit has no
    service point for the service at all — there is no connection here, which is
    not the same statement as *"this connection has nothing on it"*.

    Rule 3 does not apply to the return value, and BR-RAT-036's rule row says
    why in terms: *"`per_meter` prices a COUNT, and a meter is not a measure of
    anything… It is the same distinction BR-RAT-090 draws for an unmetered
    service's cart count."* Three carts is three things. The unit the PRICE is
    quoted per belongs to the tariff and is attached where the tariff is in hand.
    """
    point = _service_point_for(unit_id, service_code)
    if point is None:
        return None
    return seams.billable_asset_count(unit_id, service_code, as_of)


def billable_asset_size_counts(
    unit_id: Any, service_code: str, as_of: Any
) -> "dict[str | None, int] | None":
    """**HOW MANY OF EACH SIZE stand on this unit, or `None` where nobody
    looked** — `CR-063` C3/C5, `BR-RAT-090` as narrowed on 2026-09-02.
    🔒 rating math. HUMAN-REVIEW-PENDING.

    **Billing's seam for a COUNTING capacity service's per-size bill lines.**
    `billable_asset_count` above answers *how many*; this answers *how many of
    what*, over the SAME population at the SAME date, because a bill that
    counted one set of assets and grouped another would foot and be wrong.

    Worked, on a fire property with a 6" line and two 2" lines:

        {"FL-6": 1, "FL-2": 2}   ->   1 × $60.00 + 2 × $12.00   =   $84.00

    ⚠ This example was `CR-063`'s warehouse — a 6" line and two private hydrants
    at `$110.00` — until the PO removed the hydrant from fire's size list on
    2026-09-03 (*"remove private hydrants from list"*). **The grouping is what
    the example is for and it did not change**; that warehouse now bills
    `$60.00` on one line, so a second SIZE is needed to show two.

    ⚠ **THE `None` KEY IS A REAL ENTRY AND MUST NOT BE DROPPED.** An asset whose
    size nobody recorded appears as `{None: 1}`, and the caller REFUSES on it:
    decision log 2026-09-02, *"A size nobody recorded is still a refusal, not a
    zero."* Skipping it would price a 6" line at nothing.

    ⚠ **`None` (the RETURN) IS *NOBODY LOOKED* AND `{}` IS *THE UTILITY LOOKED
    AND THERE IS NOTHING*.** The same distinction the count draws, for the same
    money: an empty map bills `BR-MET-108`'s ruled `$0.00` and a `None` stops
    the account. `None` also where this unit has no service point for the
    service — there is no connection here at all.

    Answered through the assets seam and never by joining (B1). It asks about
    every capacity service alike; **whether the answer is USED is the caller's
    decision**, exactly as `_stamp_installed_capacity` records for the sum —
    solar's `2 + 4 + 8 kW` is one 14 kW quantity and grouping it per size would
    be a misreading of the model, not a feature.
    """
    point = _service_point_for(unit_id, service_code)
    if point is None:
        return None
    codes = seams.billable_asset_size_classes(unit_id, service_code, as_of)
    if codes is None:
        return None
    counts: dict[str | None, int] = {}
    for code in codes:
        counts[code] = counts.get(code, 0) + 1
    return counts


def bills_one_line_per_size(service_code: str) -> bool:
    """**DOES THIS SERVICE BILL ONE LINE PER SIZE?** — `CR-063`, decision log
    2026-09-02. Billing's seam for the per-size split.

    THREE conditions, all required, and each one rules out a wrong answer that
    would move money:

      1. **THE TENANT DECLARES IT UNMETERED** (`BR-RAT-081` /
         `tenant_services.billing_basis`). Water and electric are BANDED too —
         a 2" water service prices on a different ladder from a 5/8" one — but
         their quantity comes from ONE register, so splitting them would price
         the SAME reading twice and double the customer's water bill. This
         condition is the one that keeps the narrowing narrow.
      2. **ITS SIZES DO NOT SUM** (`capacity_uom_for_service` answers `None`).
         Solar, battery, storm water and broadband ADD their capacity up:
         `2 + 4 + 8 kW` is one 14 kW quantity on ONE line at one rate, and
         `core/sample_fixture` says so in terms — *"If a lane finds itself
         needing per-size grouping for solar, it has misread the model."*
      3. **IT HAS A RATIFIED SIZE LADDER.** A service ruled to have none has
         nothing to group by.

    Trash and fire are the pair that answers `True` today, which is exactly the
    pair the ruling names: *"For a capacity service billed by a COUNT — today
    trash and fire — the one-size-per-connection rule does not apply. The bill
    carries ONE LINE PER SIZE."*

    ⚠ **AND THE TWELFTH SERVICE LANDS ON WHICHEVER SIDE ITS OWN ROWS PUT IT**,
    with no edit here — the same property `_stamp_installed_capacity` records
    about the sum. No service is named in this function.

    Unruled bands (thermal steam, `OQ-560`) and a code this product does not
    recognise both answer `False`: there is nothing to group by, and the prime
    directive forbids resolving an unruled boundary by choosing a value.
    """
    from apps.tenancy import service_size_classes

    if service_code not in seams.unmetered_service_codes():
        return False
    if service_size_classes.capacity_uom_for_service(service_code) is not None:
        return False
    try:
        return bool(service_size_classes.size_classes_for_service(service_code))
    except (service_size_classes.SizeClassNotRuled, KeyError):
        return False


def billable_size_groups(
    unit_id: Any, service_code: str, as_of: Any
) -> "dict[str | None, int] | None":
    """**THE PER-SIZE BILL LINES THIS UNIT OWES FOR THIS SERVICE, or `None`
    where the service is not billed that way** — `CR-063` C3/C5.
    🔒 rating math. HUMAN-REVIEW-PENDING.

    `billing.gather` asks exactly this question and builds one tariff per key.
    Worked, on a fire property with a 6" line and two 2" lines:

        {"FL-6": 1, "FL-2": 2}   ->   1 × $60.00 + 2 × $12.00   =   $84.00

    ⚠ This example was `CR-063`'s warehouse — a 6" line and two private hydrants
    at `$110.00` — until the PO removed the hydrant from fire's size list on
    2026-09-03 (*"remove private hydrants from list"*). **The grouping is what
    the example is for and it did not change**; that warehouse now bills
    `$60.00` on one line, so a second SIZE is needed to show two.

    ⚠ **`None` MEANS *DO NOT GROUP* AND NEVER *NOTHING IS INSTALLED*.** It is
    the answer for every metered service, for the four capacity services that
    SUM, for the case where nobody has looked at this unit's equipment at all,
    and for a unit with **no service point for this service at all**. `{}`
    itself is the real, billable *"the utility looked and there is nothing"*,
    which `BR-MET-108` prices at `$0.00`.

    ⚠⚠ **THIS PARAGRAPH CLAIMED A DOWNSTREAM GUARANTEE THAT DOES NOT HOLD, AND
    IT COST A WHOLE BILL (`DEF-BIL-6759`, corrected 2026-09-25).** It read
    *"…in which the account is already stopped by name
    (`asset_count_unavailable`), so grouping is moot"*. **It is not stopped
    there.** For a schedule that names sizes, the SIZE gate fires FIRST — in
    `billing.gather._tariff_config_for`, before `measure_consumption` is ever
    reached — so the account is refused as
    `connection_size_unresolved_for_sized_schedule` and the customer's water
    stops with their fire. Measured on a seeded water + sewer + fire tenant on
    real PostgreSQL 16, gathering all 75 accounts: **21 refused on that reason,
    20 of them over a unit with no fire service point.** That is hard-won law
    1 exactly — a comment claiming a guarantee is not the guarantee — and the
    comment was believed for three weeks.

    ⚠ **AND THE NO-SERVICE-POINT CASE IS NOW RULED AND IS HANDLED ELSEWHERE, BY
    NAME (`BR-BIL-301`, PO 2026-09-25, option (b): *"Bill it at $0.00, and say
    so"*).** **It is deliberately NOT expressed as a `{}` here**, and the
    reason is money rather than tidiness: `{}` routes into
    `gather._per_size_configs`' empty-map arm, **which passes the plan's base
    charge** — so a connection that does not exist would be billed the STANDING
    CHARGE (`BR-RAT-080`: a base is charged because a connection exists). The
    ruling says `$0.00`, not *a base plus a zero*. `gather` asks
    `service_points_for` and builds the ruled line itself; this seam keeps the
    two meanings its own docstring gives it and gains no third.

    ⚠ **A `None` KEY IS CARRIED AND MUST BE REFUSED BY THE CALLER**, never
    dropped: an item whose size nobody recorded *"stops that customer's bill and
    says so"* (decision log 2026-09-02).
    """
    if not bills_one_line_per_size(service_code):
        return None
    return billable_asset_size_counts(unit_id, service_code, as_of)


def billable_base_size_counts(
    unit_id: Any, service_code: str, as_of: Any
) -> "dict[str, int] | None":
    """**HOW MANY OF EACH SIZE, FOR A SUMMING CAPACITY SERVICE'S BASE** — or
    `None` where the base is not looked up by size. 🔒 rating math.
    HUMAN-REVIEW-PENDING (*"2026-10-01 · CAPACITY BASE BY SIZE"*).

    PO ruling 2026-10-01, verbatim: *"in case of all capacity based base rates
    for example ofr base charges for Trash, Fire, Battery, Solar - all capacity
    based - based rates should be search based on sizes dueing billing"*.
    Trash and fire already group per size (`billable_size_groups`); this is
    the same count for the services whose sizes SUM — solar, battery,
    broadband, thermal, and storm water where its assets carry sizes. Worked:
    2 panels of size A and 1 of size B → `{"A": 2, "B": 1}`, and billing bills
    `2 × base(A) + 1 × base(B)`.

    ⚠ **IT IS FOR THE BASE ONLY, AND THE USAGE IS NOT GROUPED.** Solar's
    `2 + 4 + 8 kW` is still ONE 14 kW quantity on one line — the misreading
    `bills_one_line_per_size` warns about is not made here; this map never
    reaches `measure_consumption`.

    `None` — *do not look the base up by size* — for: a service that is not
    capacity-based, a counting one (trash, fire: `billable_size_groups` owns
    it), no service point, nobody looked (`None` count), nothing installed
    (`{}`: the base is looked up once, as before), and ANY asset with no size
    recorded — that is not "a rate not found", and the existing named stop
    (`installed_capacity_undetermined`) keeps it.
    """
    from apps.tenancy import service_size_classes

    if service_code not in seams.unmetered_service_codes():
        return None
    if service_size_classes.capacity_uom_for_service(service_code) is None:
        return None
    counts = billable_asset_size_counts(unit_id, service_code, as_of)
    if not counts or None in counts:
        return None
    return {str(code): int(count) for code, count in counts.items()}


def service_size_class_labels(service_code: str) -> dict[str, str]:
    """`BR-TEN-171`'s ratified size classes as `{code: NAME}` — `CR-063` C5.

    **WHAT A PER-SIZE BILL LINE IS CALLED.** A fire property's two line sizes
    are the same service at two prices, so without a name on each the document
    reads *"fire usage"* twice and the customer cannot tell the 6" line from the
    2" ones — which is the thing the 2026-09-02 ruling asks the bill to show:
    *"they are different equipment at different prices and a single blended
    quantity would hide that."*

    ⚠ **THE RATIFIED NAME, NOT THE TENANT'S OWN LOOKUP ROW, AND THAT IS A
    LIMITATION STATED RATHER THAN HIDDEN.** A tenant may rename a size class on
    Settings → Service sizes (`BR-TEN-036`), and this does not follow the
    rename: it reads `tenancy.service_size_classes`, the ratified law the tenant
    lookup is SEEDED from. It is the same sanctioned read
    `ratified_size_class_codes` above already makes and for the same B1 reason —
    that module holds no model and issues no query. Following the tenant's own
    row is a real improvement and is not made here, because it needs a decision
    about what a bill issued under an OLD name should print (hard rule 4), and
    that decision has not been taken.

    An empty map for a service ruled to have no size classes (sewer), for one
    whose bands nobody has ruled (thermal steam, `OQ-560`), and for a code this
    product does not recognise — three different facts that agree on the answer
    *"there is no label to put on a line"*, which is the only question asked.
    """
    from apps.tenancy import service_size_classes

    try:
        rows = service_size_classes.size_classes_for_service(service_code)
    except (service_size_classes.SizeClassNotRuled, KeyError):
        return {}
    return {code: name for code, name in rows}


def cycle_expected_span_days(cycle_id: Any, *, period_start: Any) -> int | None:
    """**BR-MET-121 (PO 2026-08-26)** — the day span ONE period of this cycle
    covers, starting at `period_start`. Billing's seam for the run's Days tab.

    The ruling's second half, verbatim from the rule row: *"The AUTHORITATIVE
    days judgment happens when the BILL RUN pulls the readings: the run decides
    whether the span it is pricing is 15, 30 or 90 days against the cycle it is
    billing."* The judgment is billing's; the CYCLE's own expected span is this
    module's fact, derived from the frequency machinery (`period_engine
    .expected_span_days` — B17 §2's step table, OQ-339's clamp), never from a
    tenant threshold (BR-MET-020) and never from a clock (`period_start` is the
    run's own argument).

    `None` when the cycle carries no frequency the vocabulary holds — a cycle
    provisioned before CR-029, or hand-written text. The caller REPORTS that
    absence beside the tenant-bounds verdict it falls back to; answering a
    guessed 30 here would judge a quarterly cycle's healthy 92-day read wrong
    every single period, which is the exact failure BR-MET-121 closes.

    Tenant-scoped through `cycle_row` (HR-1: unknown, malformed and
    cross-tenant are one absent answer).
    """
    row = cycle_row(cycle_id)
    try:
        return period_engine.expected_span_days(row.frequency, period_start)
    except ValueError:
        return None


def _cycles_for_unit(unit_id: Any) -> list[models.Cycle]:
    """Every DISTINCT cycle this unit bills on, resolved the CR-029 D4 way.

    Two sources, and both are needed because the derivation has exactly two:

      * **route membership**, `derivation.routes_for_unit` — BR-MET-082
        Amendment 1, PO verbatim: *"at the time of Run -> it will figure out how
        many accounts or meter or devices it has to take into account"*. A
        `service_points.cycle_id` that carries a route is a PROJECTION of that
        membership and is re-derived, never trusted (`units_in_cycle` records
        why: a stale stamp dropped units out of bill runs, DEF-225/DEF-249).
      * **the route-less stamp**, the one stored row the derivation still reads
        as an explicit human statement (`directly_stamped_units`: *"nothing
        about routing explains it, so it is a standing statement that this unit
        bills on this cycle"*).

    Tenant-scoped both ways, so a cross-tenant or malformed unit id is simply
    absent (hard rule 1; the `unit_row` posture — unknown and forbidden are one
    answer). A DRAFT cycle is excluded exactly as it is from a bill run
    (BR-MET-076): a cycle that scopes no run cannot be what a bill divides by.
    """
    if not _is_uuid(unit_id):
        return []
    from apps.metering import derivation

    found: dict[str, models.Cycle] = {}
    cycle_ids = {
        answer.cycle_id
        for answer in derivation.routes_for_unit(unit_id).values()
        if answer.cycle_id
    }
    cycle_ids |= {
        str(value)
        for value in models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(),
            unit_id=unit_id,
            route_id__isnull=True,
            cycle_id__isnull=False,
            deleted_at__isnull=True,
            unit__deleted_at__isnull=True,
        ).values_list("cycle_id", flat=True)
    }
    if not cycle_ids:
        return []
    for row in models.Cycle.objects.filter(
        tenant_id=_tenant_id(), pk__in=sorted(cycle_ids), deleted_at__isnull=True
    ).exclude(status="draft"):
        found[str(row.pk)] = row
    return [found[key] for key in sorted(found)]


def billing_period_for_unit(unit_id: Any, *, as_of: Any = None) -> dict[str, Any] | None:
    """**THE UNIT'S BILLING PERIOD — `{start, end}`, ISO dates. `DEF-2708`.**

    🔒 HUMAN-REVIEW-PENDING — this is a MONEY path. It is B4.3's ❄️ FROZEN
    denominator: *base ÷ cycle length × service days*. The RULE is finance-signed
    and does not move; what was missing was the **cycle length**, and every
    caller was falling back to the billed window's own length, making the factor
    1 and charging a FULL period's standing charge for a PART period. On the
    PO's own account `A-11488`, cut 18 August on a **$40.00** monthly base:
    **$40.00 charged where 18 days of 31 is $23.23 — $16.77 too much, on a
    customer's final bill.**

    THE CONTRACT, quoted from `apps/customers/seams.billing_period_for_unit`
    which has asked for it by name since 2026-08-11 and never been answered:

        apps.metering.selectors.billing_period_for_unit(unit_id)
            -> {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} | None

    `as_of` is an ADDITION to that contract and is optional, so the published
    signature is unchanged for anyone already calling it. See below for why a
    money caller must pass it.

    ════════════════════════════════════════════════════════════════════════
    ⛔ THE SEAM'S OWN DESCRIPTION OF THE JOIN IS STALE, AND FOLLOWING IT WOULD
    HAVE BUILT NOTHING
    ════════════════════════════════════════════════════════════════════════
    It says the period is *"`cycles.window_start`/`.window_end` reached through
    the unit's service points"*. **Both of those columns are gone** — metering
    `0021_cr029_drop_legacy_cycle_columns` executes `RemoveField(model_name=
    "cycle", name="window_start")` and the same for `window_end`, and `0023`
    took `bill_date`. A cycle now carries `frequency` · `start_day` ·
    `days_to_complete` · `bill_day` · `due_days` · `first_run_date`, and not one
    calendar date describing a period. **And the stamp is stale too**: CR-029 D4
    made a unit's cycle DERIVED (see `_cycles_for_unit`).

    So the period is DERIVED, and from facts the PO has already ruled — no
    column is added and no new rule is minted:

      start   the anchor of the occurrence `as_of` falls in — `OQ-340` (the
              first run is the anchor) and `OQ-339` (a month with no such day
              clamps), both PO-ruled 2026-08-23.
      end     the day before the NEXT anchor — `period_engine.billing_period`,
              which argues there why it is not `expected_span_days`.

    That length is the same fact `cycle_expected_span_days` above has served
    billing's Days tab since 2026-08-26 under **BR-MET-121** (*"when you run
    bill cycle you pull the reading and at that time we have to decide whether
    it is for 90 days or whrther it for 30 days or 15 days"*). The cut-bill path
    was never asking metering a question metering was not already answering.

    ⚠ **IT IS NOT THE READ WINDOW.** `period_engine`'s `Window` is `[anchor,
    anchor + days_to_complete − 1]` — the days the crew is out with the
    handheld, *"Sep 1-3"* for a 3-day Monthly cycle. Dividing a $40.00 base by
    that would charge `A-11488` **$144.00** for 18 days. The read window is a
    short sub-window sharing the period's start, and `DEF-2708` is what happens
    when the two are treated as one thing.

    ⚠ **`as_of` IS AN ARGUMENT AND A MONEY CALLER MUST PASS THE EVENT DATE**
    (BR-TEN-043 / G6 — no clock on a money path). A cut on 18 February committed
    by a clerk in March must divide by February's **28** days, not March's 31:
    the same $40.00 base is $23.23 over 31 days and $25.71 over 28. It defaults
    to the tenant's today (`seams.tenant_today`) so a screen asking *"what
    period are we in"* needs no argument, which is what the plan-change preview
    asks.

    ════════════════════════════════════════════════════════════════════════
    `None` IS AN HONEST ANSWER, AND EVERY CALLER MUST STATE IT
    ════════════════════════════════════════════════════════════════════════
    A unit on no cycle · a cycle with no `first_run_date` or a frequency the
    B17 §2 vocabulary does not hold (every cycle provisioned before CR-029) · an
    `as_of` before the cycle's first run · **and a unit on TWO cycles**, which
    has no single period: answering one of them would silently choose which
    calendar a customer's standing charge is divided by. Nothing here guesses a
    30-day month — that would be money invented from a calendar nobody
    configured, and `apps/billing/cut_bill.CUT_BILL_DENOMINATOR_ABSENT` is the
    sentence a caller puts on the result instead.

    ⚠ **B2 §2 INTERFACE-REGISTER ROW IS OWED AND IS NOT WRITTEN HERE** — the
    same posture `reads_for_unit` above records for the same reason: publishing
    a cross-module contract earns a row in the reviewed interface set, and
    `04-docs` is not a backend lane's to edit. REPORTED rather than skipped.

    Tests: `06-backend/tests/test_def2708_billing_period_for_unit.py`.
    """
    cycles = _cycles_for_unit(unit_id)
    if len(cycles) != 1:
        # Zero = nothing to read. More than one = two calendars and no ruling
        # saying which a base charge divides by; both are STATED, never picked.
        return None
    cycle = cycles[0]
    when = as_of if as_of is not None else seams.tenant_today()
    # ⚠ NORMALISE THE EVENT DATE RATHER THAN LET IT RAISE. This read runs INSIDE
    # `commit_cut`'s transaction, and an exception here does not degrade a
    # figure — it aborts the whole cut, so a customer's supply is recorded as
    # off with no bill and no status. A `datetime` compared against a `date`
    # raises `TypeError`; an ISO string raises nothing and compares wrong. Both
    # are coerced, and anything else is the honest `None` this function already
    # answers for a cycle it cannot place.
    if isinstance(when, datetime):
        when = when.date()
    elif isinstance(when, str):
        try:
            when = date.fromisoformat(when)
        except ValueError:
            return None
    if not isinstance(when, date):
        return None
    period = period_engine.billing_period(
        frequency=cycle.frequency,
        start_day=cycle.start_day,
        first_run=cycle.first_run_date,
        as_of=when,
    )
    if period is None:
        return None
    return {"start": period[0].isoformat(), "end": period[1].isoformat()}


def billing_cycle_for_unit(unit_id: Any, *, as_of: Any = None) -> dict[str, Any] | None:
    """**THE UNIT'S CYCLE, ITS CURRENT PERIOD AND ITS NEXT BILL — `DEF-CUS-5182`.**

    The transfer wizard draws *Billing cycle · Cycle 2 · the 9th*, *Current
    period* and *Next bill* on the account being sold, and until 2026-09-23 it
    hard-coded all three as *"Not available yet"* because no read answered them.
    Every fact below was already METERING's and already computed elsewhere in
    this file; this only puts them in one answer:

      * the cycle is `_cycles_for_unit` — CR-029 D4's derivation, never the
        stale stamp — and a unit on no cycle or on TWO answers `None`, for
        `billing_period_for_unit`'s reason (two calendars and no ruling saying
        which one a bill divides by);
      * the period is `billing_period_for_unit`'s arithmetic (`OQ-340` ·
        `OQ-339`), called rather than restated;
      * the next bill is `OQ-344`'s rule — *"the bill day, in the month after
        the period ends"* (PO 2026-08-23, *"I'd say B - these are defualt - user
        can override"*) — through `_default_bill_date`, the one place this
        module applies it.

    ⚠ **A READ FOR A SCREEN, NOT A MONEY PATH.** It divides nothing and prices
    nothing; the next bill is the cycle's DEFAULT, which a run may override (D9).
    `as_of` defaults to the tenant's today because the question a clerk asks is
    *what period are we in now*.

    Returns `{code, name, bill_day, period_start, period_end, next_bill_on}` —
    the three dates are `None` when the cycle carries no schedule to derive them
    from — or `None` when there is no single cycle.
    """
    cycles = _cycles_for_unit(unit_id)
    if len(cycles) != 1:
        return None
    cycle = cycles[0]
    period = billing_period_for_unit(unit_id, as_of=as_of)
    next_bill = (
        _default_bill_date(cycle.bill_day, {"period_end": period["end"]}) if period else None
    )
    return {
        "code": cycle.code,
        "name": cycle.name,
        "bill_day": cycle.bill_day,
        # `CR-190-BRC10` (additive) — the cycle's business word (`schedule
        # .FREQUENCIES`), so a customer letter can say what period a base
        # charge covers without typing "a month" anywhere.
        "frequency": cycle.frequency,
        "period_start": period["start"] if period else None,
        "period_end": period["end"] if period else None,
        "next_bill_on": next_bill.isoformat() if next_bill else None,
    }


def cycle_terms_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """The unit's ONE cycle and the days-to-pay it carries — or `None`.

    The one-time bill's step 1 defaults *Days to pay* from the account's cycle
    (`04-docs/05-modules/07-billing/13-one-time-bill-api-contract.md` §2,
    `account.cycle_due_days`; design §2 *"defaults from the account's cycle"*).
    `billing_cycle_for_unit` above answers the cycle but not its terms, and
    derives a period from today's date, which this question does not need — so
    this is the narrow read: which cycle, and `cycles.due_days` (BR-BIL-024's
    input, D9).

    A unit on no cycle or on TWO answers `None`, for `billing_period_for_unit`'s
    reason (two calendars and no ruling saying which one a bill follows), and
    `due_days` is `None` where the cycle carries none. **Nothing here chooses a
    default** — the screen leaves the field empty and asks the clerk.
    """
    cycles = _cycles_for_unit(unit_id)
    if len(cycles) != 1:
        return None
    cycle = cycles[0]
    return {"code": cycle.code, "name": cycle.name, "due_days": cycle.due_days}


def one_time_read_positions(
    unit_id: Any, *, period_start: Any, period_end: Any
) -> list[dict[str, Any]]:
    """Every METER on a unit, with where its register stood around one window.

    The one-time bill's step 2 draws one reading row per meter (design §4 —
    *"One per meter; 2 meters = 2 rows"*) with the PREVIOUS reading and its date
    from Meter Reads and the NEW reading beside it. This is that read, and it is
    a read only: a reading is SAVED through `/read-batches` (stage → validate →
    post), never by billing and never here.

    Per meter (asset category `meters`; the service answered through this
    module's own service points — `_service_code_by_asset`):

      * ``current`` — the newest committed lineage head whose DATE falls inside
        ``[period_start, period_end]``: the reading this window closes on, once
        somebody has saved it. ``None`` while nobody has.
      * ``previous`` — the newest committed head dated BEFORE ``current`` (or,
        with no current, on or before ``period_end``): the reading the window
        opens on. ``None`` when the meter has never been read.

    Only the consumption channel is read (``total`` where the meter has one): an
    export register is a different quantity, and a multi-register meter is sent
    to the full readings screen by the client rather than flattened here
    (``registers`` says how many channels it has).

    Values travel as strings WITH their unit (CLAUDE.md rule 3); nothing here
    computes a usage — ``consumption`` is the stored one on ``current``.
    """
    if not _is_uuid(unit_id):
        return []
    start = (
        period_start if isinstance(period_start, date) else date.fromisoformat(str(period_start))
    )
    end = period_end if isinstance(period_end, date) else date.fromisoformat(str(period_end))
    types = _asset_type_index()
    services = _service_code_by_asset(unit_id)
    out: list[dict[str, Any]] = []
    for row in seams.assets_on_unit(unit_id):
        if types.get(str(row.get("type")), {}).get("category") != "meters":
            continue
        asset_id = str(row.get("id"))
        heads = [
            head
            for head in _read_heads().filter(asset_id=asset_id).order_by("-read_at", "-id")
            if read_type_of(head.channel) == READ_TYPE_CONSUMPTION
        ]
        channels = {head.channel for head in heads}
        if models.CHANNEL_TOTAL in channels:
            heads = [head for head in heads if head.channel == models.CHANNEL_TOTAL]
        current = next(
            (head for head in heads if head.read_at and start <= head.read_at.date() <= end),
            None,
        )
        cutoff = current.read_at.date() if current is not None else end + timedelta(days=1)
        previous = next(
            (head for head in heads if head.read_at and head.read_at.date() < cutoff),
            None,
        )
        either = current if current is not None else previous
        previous_position = _read_position(previous)
        if previous_position is None and current is not None and current.prior_value is not None:
            # The CURRENT read already records what it counted up from
            # (`meter_reads.prior_value`, BR-MET-056 shows the math) — a meter
            # whose earlier read was never loaded as its own row still has a
            # previous reading, and it is this. Its date is the one the read
            # states (`days_since_prior`), or none where it states none.
            previous_position = {
                "read_id": None,
                "value": str(current.prior_value),
                "read_at": (
                    (current.read_at.date() - timedelta(days=current.days_since_prior)).isoformat()
                    if current.read_at and current.days_since_prior is not None
                    else None
                ),
                "estimated": False,
            }
        out.append(
            {
                "asset_id": asset_id,
                "label": row.get("asset_no"),
                "service": services.get(asset_id),
                "unit": None if either is None else either.unit,
                "registers": len(channels),
                "previous": previous_position,
                "current": _read_position(current),
                "consumption": (
                    None
                    if current is None or current.consumption is None
                    else str(current.consumption)
                ),
            }
        )
    return out


def _read_position(head: Any) -> dict[str, Any] | None:
    """One head as `one_time_read_positions` serves it, or `None`."""
    if head is None:
        return None
    return {
        "read_id": str(head.id),
        "value": None if head.current_value is None else str(head.current_value),
        "read_at": head.read_at.date().isoformat() if head.read_at else None,
        "estimated": read_is_estimated(head.status, getattr(head, "disposition", None)),
    }


def read_analysis_for_unit(
    unit_id: Any,
    *,
    period_start: Any,
    period_end: Any,
    service_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """CR-038 W8 — the bill run's read-ANALYSIS facts for one unit's period,
    from STORED values only (BR-MET-022/056: outcomes are self-describing and a
    consumer must not re-derive the math or the thresholds).

    `billing_reads_for_unit` above is the PRICING seam: one row per service
    point, the single latest billable head. This is the JUDGMENT seam beside
    it: **every committed lineage head on a total-measuring register in the
    period**, oldest first, each carrying the stored facts the S31 read-analysis
    tabs render — `rule_outcomes` (every flag with the thresholds it was judged
    against travels onto the committed read, BR-MET-129), the estimation trio
    (`estimation_method` · `consecutive_estimate_no` · `trues_up_read_ids`,
    US-MET-014/015), the factor actually USED (`multiplier`, BR-MET-056 shows
    the math), and `days_since_prior` (BR-MET-121's span).

    MORE THAN ONE ASSET in one service point's list is the mid-cycle
    replacement fact (assets' `asset_ids_for_service_point` includes retired
    meters by its own stated reason: *"a meter replaced mid-cycle still
    produced the reads that half the period is billed on"*). Each read names
    its asset, so the caller can see the old meter's final read and the new
    meter's start without this module deciding what a swap means for money —
    that judgment is billing's.

    Quantities are serialised as strings WITH their unit (CLAUDE.md rule 3);
    nothing here computes, sums or prices anything.
    """
    service_points = _live_service_points_for(unit_id, service_codes)
    rows: list[dict[str, Any]] = []
    for point in service_points:
        asset_ids = seams.asset_ids_for_service_point(point.id)
        reads: list[dict[str, Any]] = []
        if asset_ids:
            # The window and demand registers are separate measurements
            # (BR-RAT-021/014) with their own surfaces; the analysis tabs
            # judge the register the period's TOTAL is priced from. Oldest
            # first (`read_at, id`), the reverse of `_period_heads`' order.
            heads = [
                head
                for head in reversed(_period_heads(asset_ids, period_start, period_end))
                if head.channel not in (*models.TOU_WINDOW_CHANNELS, models.CHANNEL_DEMAND)
            ]
            for read in heads:
                reads.append(
                    {
                        "read_id": str(read.id),
                        "asset_id": str(read.asset_id),
                        "meter": getattr(read.asset, "asset_no", None),
                        "channel": read.channel,
                        "read_at": read.read_at.isoformat() if read.read_at else None,
                        "prior_value": (
                            str(read.prior_value) if read.prior_value is not None else None
                        ),
                        "current_value": (
                            str(read.current_value) if read.current_value is not None else None
                        ),
                        "multiplier": str(read.multiplier) if read.multiplier is not None else None,
                        "consumption": (
                            str(read.consumption) if read.consumption is not None else None
                        ),
                        "unit": read.unit,  # rule 3 — never separated from the number
                        "days_since_prior": read.days_since_prior,
                        "status": read.status,
                        "billable": read.status not in UNBILLABLE_READ_STATUSES,
                        # THE derivation, not a re-spelling of it (hard-won law 5).
                        "estimated": read_is_estimated(read.status, read.disposition),
                        "estimation_method": read.estimation_method,
                        "consecutive_estimate_no": read.consecutive_estimate_no,
                        "trues_up_read_ids": read.trues_up_read_ids or [],
                        "rule_outcomes": read.rule_outcomes or [],
                        "source": read.source,
                    }
                )
        rows.append(
            {
                "service_code": point.service.code,
                "service_id": str(point.service_id),
                "service_point_id": str(point.id),
                "asset_count": len(asset_ids),
                "reads": reads,
            }
        )
    return rows


def read_correction_dict(row: Any) -> dict[str, Any]:
    """One `read_corrections` linkage — the J6 step-1 handoff, rendered.

    Quantities and references only; no money field exists on this row or in
    this payload, because the money side is billing's (US-MET-016 §7)."""
    return {
        "id": str(row.id),
        "superseded_read_id": str(row.superseded_read_id),
        "superseding_read_id": str(row.superseding_read_id),
        "invoice_id": str(row.invoice_id),
        "invoice_no": row.invoice_no,
        "asset_id": str(row.asset_id),
        "channel": row.channel,
        "reason": row.reason,
        "status": row.status,
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
    }


def read_corrections_for_read(read_id: Any) -> list[dict[str, Any]]:
    """Every correction linkage that names this read, either side of the pair.

    The S29 drawer shows it beside the chain (BR-MET-056: "supersession
    history"), and billing reads the same rows for J6 step 1.
    """
    rows = models.ReadCorrection.objects.filter(tenant_id=_tenant_id()).filter(
        Q(superseded_read_id=read_id) | Q(superseding_read_id=read_id)
    )
    return [read_correction_dict(row) for row in rows.order_by("opened_at")]


def read_corrections_for_invoice(invoice_id: Any) -> list[dict[str, Any]]:
    """BILLING'S READ: the corrections opened against one invoice (J6 step 1).

    Published here so billing never queries `read_corrections` itself (B1) —
    it resolves this selector by name like every other cross-module read.
    """
    rows = models.ReadCorrection.objects.filter(tenant_id=_tenant_id(), invoice_id=invoice_id)
    return [read_correction_dict(row) for row in rows.order_by("opened_at")]


def read_chain(read_id: Any) -> list[dict[str, Any]]:
    """The full supersession history (BR-MET-056), oldest first. Walks
    `superseded_by_id` forward from the row asked for, then back to the
    lineage's first version so the drawer can render v1 → v2 → v3.

    `select_related` carries the asset AND the DEF-045 linkage: every entry is
    rendered through `read_dict`, and without the joins each version would
    lazy-load its way to a premises — the N+1 this query already avoids for
    the asset itself."""
    rows = {
        str(row.id): row
        for row in models.MeterRead.objects.filter(tenant_id=_tenant_id()).select_related(
            "asset", *READ_LINKAGE_RELATED
        )
    }
    row = rows.get(str(read_id))
    if row is None:
        return []
    # Walk back to the origin.
    by_successor = {
        str(r.superseded_by_id): r for r in rows.values() if r.superseded_by_id is not None
    }
    origin = row
    while str(origin.id) in by_successor:
        origin = by_successor[str(origin.id)]
    chain: list[dict[str, Any]] = []
    cursor: Any = origin
    seen: set[str] = set()
    while cursor is not None and str(cursor.id) not in seen:
        seen.add(str(cursor.id))
        entry = read_dict(cursor)
        entry["version"] = len(chain) + 1
        chain.append(entry)
        cursor = rows.get(str(cursor.superseded_by_id)) if cursor.superseded_by_id else None
    return chain


def read_list(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    direction: str = "desc",
    include_archive: bool = False,
) -> QuerySet:
    """The S25 query (US-MET-012). Server-side by law: the hot window is
    applied HERE, so no caller can ask for everything (BR-MET-055).

    `direction` defaults to "desc" to match `READ_DEFAULT_SORT` — the newest
    read first, which is what a clerk opening the screen wants and what the
    capability row declares. It is an ARGUMENT rather than a constant because
    the header is clickable; see DEF-044 below for what happened when it was
    neither."""
    # DEF-045: the linkage joins ride the ONE list query (DEF-324 discipline).
    # `import_batch` rides the SAME query (DEF-324): `read_dict` serves the
    # batch NUMBER now, and without this join a 50-row page would lazy-load
    # fifty batches to print it.
    qs = _register_heads().select_related("asset", "import_batch", *READ_LINKAGE_RELATED)
    if not include_archive:
        cutoff = timezone.now() - timedelta(days=HOT_WINDOW_DAYS)
        qs = qs.filter(read_at__gte=cutoff)
    filters = filters or {}
    if filters.get("status"):
        value = filters["status"]
        if value == "flagged":
            qs = qs.exclude(status__in=("ok", "estimated"))
        else:
            qs = qs.filter(status=value)
    if filters.get("channel"):
        qs = qs.filter(channel=filters["channel"])
    if filters.get("asset"):
        # DEF-475 (CR-028 AST-W2): one meter's rows, by the internal id the
        # API addresses — never the display number (BR-AST-026).
        qs = qs.filter(asset_id=filters["asset"])
    if filters.get("source"):
        qs = qs.filter(source=filters["source"])
    if filters.get("route"):
        # ── `DEF-MET-6143` · A ROUTE REPORTS WHAT WAS **COLLECTED** ON IT ────
        #
        # PO ruling 2026-09-22 (`CR-131-BRC07`), verbatim: **"100"**. The
        # question put to them was whether RT-009, asked what was read on it,
        # should answer with the 100 readings COLLECTED on it or with the 0 on
        # the meters that are on it TODAY. They chose the 100, and this line is
        # that answer.
        #
        # This read `asset__service_point__route_id` until then — the LIVE
        # membership projection — so moving a route's premises took a hundred
        # readings out of its list in the same instant and handed them to the
        # receiving route. `BR-MET-081` ("collected reads keep their route")
        # was printed in the wizard and asserted in `update_route`'s docstring,
        # and both were TRUE of the stored stamp and FALSE of this screen.
        #
        # `meter_reads.route_id` is the `BR-MET-079` collection stamp: written
        # once by `services.collection_route_id` at the moment the reader stood
        # in front of the meter, immutable afterwards. It is not a hard-coded
        # answer — it is the already-computed one, and re-deriving it would
        # need a temporal record of every membership change that this product
        # deliberately does not keep.
        #
        # ⚠ **THE COST IS REAL AND IS STATED ON SCREEN RATHER THAN DISCOVERED:
        # a reading collected before `metering/0012` carries NO stamp, so it
        # belongs to no route and leaves this filter.** That is 0 of 516 on the
        # seeded fixture and is NOT zero on a tenant that predates the column.
        # S25 says so where the filter is applied; a later lane must not
        # "repair" it by falling back to the live join, which is the defect.
        qs = qs.filter(route_id=filters["route"])
    if filters.get("cycle"):
        qs = qs.filter(asset__service_point__cycle_id=filters["cycle"])
    if services := filter_values(filters.get("service")):  # OQ-306 — ANY of
        qs = qs.filter(asset__service_point__service__code__in=services)
    if str(filters.get("disputed", "")).lower() == "true":
        # US-MET-019 TC-4's drill-in. The predicate is IDENTICAL to the one
        # `needs_attention_counts` counts — set and not cleared — because the
        # chip and its slice must reconcile exactly (US-MET-019 §6). Written
        # twice would be two things to drift; asserted by the TC-4 test.
        qs = qs.filter(disputed_at__isnull=False, dispute_cleared_at__isnull=True)
    if q:
        # **THE SEARCH MATCHES THE METER NUMBER *AND* THE PREMISE ADDRESS.**
        # It matched the meter number alone until 2026-09-14, and S25's search
        # box said so in as many words because naming a field the endpoint
        # ignores is the DEF-950 trap. A clerk on a phone call has an address
        # and not a meter number, so the box now keeps the promise it makes.
        #
        # The address is walked to `premises` and is read NOWHERE else
        # (CLAUDE.md hard rule 8) — the same `asset → service_point → unit →
        # premises` chain `read_linkage` composes the Premise cell from, so the
        # column a clerk searches and the column they see cannot disagree. The
        # chain is one-to-one at every hop, so the OR adds no row fan-out.
        qs = qs.filter(
            Q(asset__asset_no__icontains=q)
            | Q(asset__service_point__unit__premises__address_line__icontains=q)
        )
    # DEF-044: this used to order itself, and got it wrong in a way no test
    # could see. The expression was
    #   READ_SORTS.get((sort or "").lstrip("-"), "read_at") if sort else READ_DEFAULT_SORT
    # and `parse_list_params` ALWAYS returns a truthy sort — it falls back to
    # the endpoint's default rather than to None. So the `else` branch was
    # unreachable, `READ_DEFAULT_SORT = "-read_at"` was dead code, the leading
    # minus was stripped and never reapplied, and the list came back
    # **read_at ASCENDING — newest LAST**. It also took no `direction` at all,
    # so clicking a column header changed the URL and nothing else.
    #
    # Fixed by using the module's own `_order`, which every other list here
    # already uses and which applies the direction and adds IS-2's stable
    # secondary sort. The lesson is the one the helper existed to teach: a
    # second ordering implementation is a second thing to be wrong.
    return _order(qs, READ_SORTS, sort or READ_DEFAULT_SORT, direction)


class ReadArchiveResultSet:
    """US-MET-020 TC-3 — the S25 "Search archive" opt-in, over the COLD store.

    THE PROBLEM THIS SOLVES, STATED PLAINLY. `read_list(include_archive=True)`
    used to mean only "drop the 2-year cutoff". That was true and sufficient
    while nothing had ever been archived. The moment US-MET-020's job detaches a
    partition, those rows leave the parent — so the widened query would return
    NOTHING extra and the archive toggle would answer "no older reads" about
    reads that exist. A toggle that reports emptiness where there is data is the
    seam-answers-zero shape this codebase has a gate for; it is closed here
    rather than left as a comment.

    Same technique as apps/audit/selectors.ArchiveResultSet and the same two
    constraints, restated because they are load-bearing: the compiled SQL of the
    ORM's OWN query is re-pointed at each detached partition by table name, so
    there is one filter implementation rather than two that can drift; and that
    is safe only for a query with NO JOIN, which is why the archive base
    queryset drops `select_related` and the assets are fetched in one bulk
    lookup afterwards.

    RLS is unchanged and is the point: a detached partition keeps the tenant
    policy it was created with (DEF-027), so an archive read is scoped by
    `app.tenant_id` exactly like a hot one (US-MET-020 TC-7).
    """

    #: `meter_reads` columns, in one place — the SELECT list and the hydration
    #: must agree, and two literal lists would be two things to drift.
    _COLUMNS = (
        "id",
        "tenant_id",
        "asset_id",
        "account_id",
        "read_at",
        "channel",
        "period_start",
        "period_end",
        "prior_value",
        "current_value",
        "multiplier",
        "consumption",
        "unit",
        "source",
        "source_detail",
        # ⛔ `read_method` (CR-038 W3) IS DELIBERATELY ABSENT, AND THE ABSENCE
        # IS STATED RATHER THAN SILENT (hard-won law 1).
        # `_union` re-points ONE compiled SELECT at each detached partition BY
        # TABLE NAME, so every partition must have every column named here. A
        # partition detached BEFORE migration 0032 ran has no `read_method`
        # column at all, and naming it would make the archive toggle raise
        # instead of answering - a worse failure than the one below.
        # THE CONSEQUENCE, MEASURED: an archived row hydrates with
        # `read_method` unset, so `_read_method_of` falls through to the
        # DECLARED legacy mapping and reports `derived` or `not_stated`. It can
        # never report a wrong method, and it can never claim `recorded` for a
        # value it did not read. What it loses is a method a clerk DID record
        # on a read that has since been archived.
        # OWED, REPORTED to the Eng-Lead: the fix is a per-partition column
        # probe (or an ALTER over the detached set) in the US-MET-020 job, not
        # a line here. `route_id` has sat in exactly this position since
        # DEF-233 and is the precedent.
        "status",
        "lifecycle",
        "days_since_prior",
        "rule_outcomes",
        "import_batch_id",
        "imported_by",
        "disposition",
        "disposition_reason",
        "fix_disposition",
        "fix_reason",
        "fixed_by",
        "superseded_by_id",
        "superseded_at",
        "supersede_reason",
        "estimation_method",
        "consecutive_estimate_no",
        "trues_up_read_ids",
        "disputed_at",
        "dispute_reason",
        "disputed_by",
        "dispute_cleared_at",
        "dispute_cleared_by",
        "demand_reset_noted",
        "created_at",
        "updated_at",
    )

    def __init__(self, queryset: QuerySet, partitions: list[str]) -> None:
        self._queryset = queryset
        self._partitions = partitions
        self._count: int | None = None

    def _union(self) -> tuple[str, list[Any]]:
        base_sql, base_params = self._queryset.query.sql_with_params()
        table = models.MeterRead._meta.db_table
        sqls = [base_sql]
        params: list[Any] = list(base_params)
        for partition in self._partitions:
            sqls.append(base_sql.replace(f'"{table}"', f'"{partition}"'))
            params.extend(base_params)
        body = " UNION ALL ".join(
            f"SELECT * FROM ({sql}) AS part_{i}" for i, sql in enumerate(sqls)
        )
        return body, params

    def count(self) -> int:
        if self._count is None:
            if not self._partitions:
                self._count = self._queryset.count()
            else:
                body, params = self._union()
                from django.db import connection

                with connection.cursor() as cursor:
                    cursor.execute(f"SELECT count(*) FROM ({body}) AS combined", params)
                    self._count = int(cursor.fetchone()[0])
        return self._count

    def __len__(self) -> int:
        return self.count()

    def __getitem__(self, item: Any) -> Any:
        if not self._partitions:
            return self._queryset[item]
        if not isinstance(item, slice):  # pragma: no cover - paginator slices only
            return list(self)[item]
        from django.db import connection

        offset = item.start or 0
        limit = (item.stop - offset) if item.stop is not None else None
        body, params = self._union()
        columns = ", ".join(self._COLUMNS)
        sql = f"SELECT {columns} FROM ({body}) AS combined ORDER BY read_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params = [*params, limit, offset]
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            raw = cursor.fetchall()
        rows = [models.MeterRead(**dict(zip(self._COLUMNS, values, strict=True))) for values in raw]
        # One bulk asset lookup for the page — `select_related` cannot ride a
        # union whose parts are different tables, and N queries for N rows would
        # be a worse answer than one. The DEF-045 linkage joins ride THIS query
        # (spelled from the Asset, so `service_point__…` where the read-side
        # constant says `asset__service_point__…`) — an archive row must serve
        # the same cycle/route/service/premise columns a hot row does, and
        # without the joins each row would lazy-load four relations.
        # ⚠ **ONLY THE `asset__` PATHS RE-SPELL — `DEF-MET-6785`, 2026-09-25.**
        # This used to `removeprefix("asset__")` across the WHOLE tuple, which
        # was correct while every entry started with it. `DEF-MET-6143` then
        # added the READ's OWN `route` — no prefix — and `removeprefix` left it
        # as `"route"`, handed to a **select_related on the Asset**, which has
        # no such relation:
        #
        #     django.core.exceptions.FieldError: Invalid field name(s) given in
        #     select_related: 'route'. Choices are: tenant, type, status,
        #     service_point, parent_asset, meter_type, read_method,
        #     replaced_by_asset
        #
        # So the archived-reads opt-in RAISED for every tenant from the day
        # that entry landed. The read's own route is not an Asset relation and
        # cannot ride this lookup at all: `route_id` is not in `_COLUMNS`
        # either, for the reason stated there, so an archived row has no route
        # of its own and `_read_linkage` falls through to the service point's.
        # `startswith` rather than `removeprefix` alone, so the next entry
        # added without the prefix is dropped here rather than aimed at the
        # wrong model.
        asset_paths = [
            path.removeprefix("asset__")
            for path in READ_LINKAGE_RELATED
            if path.startswith("asset__")
        ]
        assets = {
            asset.id: asset
            for asset in django_apps.get_model("assets", "Asset")
            .objects.filter(tenant_id=_tenant_id(), id__in={row.asset_id for row in rows})
            .select_related(*asset_paths)
        }
        for row in rows:
            if row.asset_id in assets:
                row.asset = assets[row.asset_id]
        return rows

    def __iter__(self) -> Any:
        return iter(self[0:None])


def read_archive_partitions() -> list[str]:
    """The detached `meter_reads` partitions in THIS database, from the catalog.

    Empty on sqlite and wherever the retention job has never run — in which case
    the archive opt-in answers from the hot store over the widened window, which
    is all the rows there are.
    """
    from core import archival

    return archival.detached_partitions(models.MeterRead._meta.db_table)


def read_result_set(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    direction: str = "desc",
    include_archive: bool = False,
    answer_filters: dict[str, str] | None = None,
) -> Any:
    """What S25 lists (BR-MET-055): hot by default, cold only on the opt-in.

    The default NEVER touches an archived partition — that is the whole point of
    the hot window — and the opt-in reads both.

    `answer_filters` (MQ-033, `BR-MET-1218`) — `{question_key: value}` from the
    URL's `answer[<key>]=<value>`: an `id IN (subquery)` over `field_reads` and
    `read_answers`. The archive substitution rewrites only `"meter_reads"`, so
    the subquery's own tables are untouched by it.
    """

    def narrowed(queryset: Any) -> Any:
        if not answer_filters:
            return queryset
        from apps.metering import read_formats

        return queryset.filter(id__in=read_formats.meter_read_ids_answering(answer_filters))

    queryset = narrowed(
        read_list(
            q=q, filters=filters, sort=sort, direction=direction, include_archive=include_archive
        )
    )
    if not include_archive:
        return queryset
    partitions = read_archive_partitions()
    if not partitions:
        return queryset
    # No join: the substitution above rewrites ONE table name, so a queryset
    # carrying `select_related` or a filter that joins `assets` cannot be used.
    plain = narrowed(
        read_list(
            q=q, filters=filters, sort=sort, direction=direction, include_archive=True
        ).select_related(None)
    )
    return ReadArchiveResultSet(plain, partitions)


def needs_attention_counts() -> dict[str, Any]:
    """US-MET-019 chips. `flagged` = heads whose primary status is a validation
    flag (excluding ok/estimated — BR-MET-021/052); `disputed` = uncleared
    dispute markers. `missing` is the BR-MET-049 plan-driven computation —
    REAL since CR-038 W1 (US-MET-018): missing required RECORDS (meter ×
    channel, *"records, not bare meters"* — US-MET-019 §5) across every active
    cycle whose read window is OPEN (BR-MET-057 window-scoping: before open
    there is nothing to chase, TC-6). This key served `null` with a
    `missing_unavailable_reason` from W2 until 2026-08-26, because the honest
    "—" beat a fabricated 0; the derivation exists now
    (`apps/metering/completeness.py`) and the reason key is GONE with the
    absence it named.

    `missing_unresolved_meters` rides along: meters whose required set could
    not be stated (rating unwired, no version in force, a TOU window whose
    channel was never stated — BR-RAT-067). A chip reading "3 missing" over
    eleven unresolvable meters would lie by omission; the screen can say both.
    """
    heads = _register_heads()
    missing = completeness.missing_records_count()
    return {
        "flagged": heads.exclude(status__in=("ok", "estimated")).count(),
        "disputed": heads.filter(
            disputed_at__isnull=False, dispute_cleared_at__isnull=True
        ).count(),
        "missing": missing["missing"],
        "missing_unresolved_meters": missing["unresolved_meters"],
    }


# ── staged batch (S28 steps 3–5) ────────────────────────────────────────────


def read_row_dict(row: Any) -> dict[str, Any]:
    return {
        "row_no": row.row_no,
        "meter_no": row.meter_no_raw,
        "asset_id": str(row.asset_id) if row.asset_id else None,
        # `DEF-MET-4101`, the same fault on the staging preview: the PARSED date
        # is a calendar date (`_parse_date`, midnight UTC), and step 4 drew it a
        # day early beside `read_at_raw` — the clerk's own cell, verbatim. The two
        # are meant to be read against each other, so a one-day drift between them
        # is the worst possible place for it.
        "read_at": row.read_at.date().isoformat() if row.read_at else None,
        "read_at_raw": row.read_at_raw,
        "channel": row.channel,
        "value": str(row.value) if row.value is not None else None,
        "raw_value": str(row.raw_value) if row.raw_value is not None else None,
        "service": row.service,
        # The EFFECTIVE method for this row - the batch tag it inherited, or
        # its own override (BR-MET-014). Resolved at stage time, so step 4
        # shows the clerk what will actually be committed.
        "read_method": row.read_method,
        "note": row.note,
        "severity": row.severity,
        "rule_outcomes": row.rule_outcomes or [],
        "disposition": row.disposition,
        "disposition_reason": row.disposition_reason,
        # BR-MET-051 (CR-038 W4) — the staged row's reset, SERVED. A screen
        # cannot show, and a clerk cannot correct, what is not on the wire.
        "demand_reset_noted": row.demand_reset_noted,
        # CR-161-BRC10 W4 — what the row's custom columns said, already checked.
        "custom_data": dict(row.custom_data or {}),
        # The review step offers the reset control on demand rows only, and it
        # asks the SERVER which those are rather than re-deriving the channel
        # vocabulary in the browser (BR-MET-059 is extensible by a value).
        "is_peak": row.channel == models.CHANNEL_DEMAND,
        # ── BR-MET-143 (PO 2026-08-27) — THE UNIT THIS ROW WILL POST IN ──────
        # ⚠ **A UNIT A PERSON CANNOT SEE IS A UNIT NOBODY CAN CHECK.** Until
        # 2026-08-27 the S28 review step served a staged row's `value` as a
        # BARE NUMBER: a clerk approving 1,180 rows saw `412` with nothing
        # beside it, and DEF-797's wrong unit was therefore uncheckable at the
        # one moment a person is looking at the reading before it becomes an
        # issued document. This is the REGISTER's unit (`register_units.
        # register_unit`) — the very string `_post_row` will stamp — so what
        # the clerk approves and what commits are the same fact, not two
        # derivations that can drift (BR-MET-056).
        #
        # `None` is a real answer and stays one: an unknown meter has no UoM to
        # read, and a demand register on a meter whose energy unit declares no
        # demand unit has none either. Both already error `unit_missing`, and
        # the screen shows the absence rather than a plausible label
        # (CLAUDE.md rule 3).
        "unit": register_units.register_unit(
            getattr(row.asset, "unit", None) if row.asset_id else None, row.channel
        ),
        "meter_read_id": str(row.meter_read_id) if row.meter_read_id else None,
    }


def read_batch_counts(batch: Any) -> dict[str, Any]:
    """The step-5 composition (US-MET-010 §5) — it must reconcile with the rows
    exactly, so every row lands in exactly one bucket and the buckets sum to
    `rows`. A row that reached the batch is never absent from this count."""
    rows = list(models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), batch=batch))
    posting = {"accept", "accept_with_flag", "override"}
    counts = {
        "rows": len(rows),
        "passed": sum(1 for r in rows if r.severity == "ok"),
        "warnings": sum(1 for r in rows if r.severity == "warning"),
        "errors": sum(1 for r in rows if r.severity == "error"),
        # A reporting axis, not a bucket: a row can be `ok` AND carry rules
        # that could not run (BR-MET-020 fail-safe). Counted separately so a
        # clean-looking batch still shows how much of the catalog actually ran.
        "rows_with_unevaluated": sum(
            1
            for r in rows
            if any(o.get("severity") == "not_evaluated" for o in (r.rule_outcomes or []))
        ),
        "accepted": sum(1 for r in rows if (r.disposition or "") in posting),
        "rejected": sum(1 for r in rows if r.disposition == "reject"),
        "field_visit": sum(1 for r in rows if r.disposition == "field_visit"),
        "skipped": sum(1 for r in rows if r.disposition == "skip"),
        "estimate_requested": sum(1 for r in rows if r.disposition == "estimate"),
        "undispositioned": sum(1 for r in rows if not r.disposition),
        "posted": sum(1 for r in rows if r.meter_read_id is not None),
    }
    # The row-outcome ledger: every row is accounted for exactly once by
    # severity. A mismatch here is the DEF-016 failure mode (a silently dropped
    # row), so it is asserted rather than trusted.
    counts["severity_total"] = counts["passed"] + counts["warnings"] + counts["errors"]
    counts["reconciles"] = counts["severity_total"] == counts["rows"]
    return counts


def _batch_actor_names(batch: Any) -> dict[str, str]:
    """Uploader/co-signer id → display name, through AUDIT's own published
    seam (BR-MET-163, DEF-899).

    ⚠ **THE COMMENT BELOW USED TO SAY THE SCREEN DID THIS AND THE SCREEN COULD
    NOT.** It read *"The screen resolves people through identity's own
    endpoint, as it already does for the uploader"* — and `GET /users` is
    `SystemAdminOnly`, while the reader who wants to know who uploaded a batch
    is a **Billing Clerk**. So a browser-side lookup would have 403'd for
    exactly the person the field is for, and what shipped instead was the raw
    primary key on screen: `Uploaded by  01a01d99-…`. Hard-won law 1 — a
    comment claiming a guarantee is not the guarantee.

    `apps.audit.selectors.actor_names` is the PUBLISHED per-page resolver the
    audit trail itself uses (B1: cross-module data flows through the owning
    module's selector — the same route `connection_reads` takes to
    `entity_trail`). It is tenant-scoped, takes many ids and runs ONE query;
    with no ids to resolve it is not called at all.
    """
    wanted = [
        actor_id
        for actor_id in (batch.uploaded_by_id, batch.cosigned_by_id)
        if actor_id is not None
    ]
    if not wanted:
        return {}
    from apps.audit import selectors as audit_selectors

    return audit_selectors.actor_names(batch.tenant_id, wanted)


def read_batch_dict(batch: Any) -> dict[str, Any]:
    """The batch + its permanent compliance stamp (BR-MET-017)."""
    names = _batch_actor_names(batch)
    return {
        "id": str(batch.id),
        "batch_no": batch.batch_no,
        "status": batch.status,
        "source_kind": batch.source_kind,
        "source_detail": batch.source_detail,
        "read_method": batch.read_method,  # BR-MET-123 - the stage-1 TAG
        # CR-038 W7 R2 — the stage-1 PREMISE, served on every batch so the
        # wizard can re-open a staged run on the mode it was started with and
        # the receipt can say which mode posted it.
        "write_mode": batch.write_mode,
        "period_month": batch.period_month.isoformat() if batch.period_month else None,
        "cycle_id": str(batch.cycle_id) if batch.cycle_id else None,
        "route_id": str(batch.route_id) if batch.route_id else None,
        "service": batch.service,
        "compliance": {  # US-MET-010 §5 / S29's Compliance metadata block
            "file_name": batch.file_name,
            "file_hash": batch.file_hash,
            "uploaded_by": str(batch.uploaded_by_id) if batch.uploaded_by_id else None,
            # BR-MET-163 (DEF-899) — the NAME rides beside the id; the id keeps
            # its shape so no existing consumer of this contract breaks and the
            # evidence is still served. `None` is not an error: the stamp
            # outlives any user row, which is BR-AUD-003's own posture.
            "uploaded_by_name": (
                names.get(str(batch.uploaded_by_id)) if batch.uploaded_by_id else None
            ),
            "uploaded_at": batch.uploaded_at.isoformat() if batch.uploaded_at else None,
            "session_ref": batch.session_ref,
            "ip": batch.ip,
            "certified": batch.certified_by_uploader,
            "cosigned_by": str(batch.cosigned_by_id) if batch.cosigned_by_id else None,
            # ⚠ THE CO-SIGNER HAD THE SAME BUG AND NOBODY HAD REPORTED IT
            # (DEF-951, found while fixing DEF-899). S29 renders this value
            # under *Approvals*, so the moment a co-signature was ever written
            # the panel would have printed a SECOND raw primary key — the
            # identical defect, one row down, waiting for the writer that
            # landed in CR-038 W7. BR-MET-163 covers both.
            "cosigned_by_name": (
                names.get(str(batch.cosigned_by_id)) if batch.cosigned_by_id else None
            ),
            # ⚠ **THE THREE LINES BELOW EXIST BECAUSE `cosigned_by` ABOVE WAS
            # SERVED FOR SIXTEEN DAYS WITH NOTHING ABLE TO WRITE IT** (hard-won
            # law 2; CR-038 W7 task 5). An id with no DATE cannot be rendered as
            # a signature, so the screen had nothing to draw even once a writer
            # existed. `cosigned_at` lands with the writer.
            #
            # ⚠ **THIS COMMENT WAS FALSE AND IT SHIPPED A DEFECT (DEF-899,
            # 2026-08-27).** It read: *"The NAME is deliberately not served …
            # The screen resolves people through identity's own endpoint, as it
            # already does for the uploader."* The screen did no such thing —
            # it printed the raw primary key — **and it could not have**, because
            # `GET /users` is `SystemAdminOnly` and the reader is a Billing
            # Clerk. Both names ARE served now, resolved through AUDIT's own
            # published `actor_names` seam (`_batch_actor_names` above), which
            # is what B2 §2 actually permits: a cross-module read through the
            # owning module's selector, never its tables. Hard-won law 1.
            #
            # `cosign_blocks_post` states the OTHER half of OQ-042's closure —
            # *"blocks when enabled"* — which is **NOT BUILT** (DEF-815), so it
            # answers a hardcoded `False` and says so in the payload, rather
            # than leaving a screen to assume either way (hard-won law 1).
            "cosigned_at": batch.cosigned_at.isoformat() if batch.cosigned_at else None,
            "cosign_blocks_post": False,
        },
        "counts": batch.counts or read_batch_counts(batch),
        "posted_at": batch.posted_at.isoformat() if batch.posted_at else None,
    }


def read_batch_post_receipt(batch: Any) -> dict[str, Any]:
    """The receipt of a POSTED batch — the batch fresh, plus what its post did.

    `DEF-MET-8106`: a post run in a worker hands its receipt to the screen
    here. `post_receipt` is written in the post's own transaction by the one
    function that builds the synchronous answer, so the two cannot disagree.
    Raises `NotFoundError` for a batch that has not posted, or that posted
    before the column existed — never an empty receipt, which would read as
    *"posted nothing"*.
    """
    from core import errors

    if batch.status != "posted" or not batch.post_receipt:
        raise errors.NotFoundError()
    result = read_batch_dict(batch)
    result.update(batch.post_receipt)
    return result


def read_batch_rows(batch: Any, *, severity: str | None = None) -> list[dict[str, Any]]:
    # `select_related("asset")` since BR-MET-143 (2026-08-27): `read_row_dict`
    # now serves the REGISTER's unit, which is read off the meter. Without the
    # join that is one query per staged row — 1,180 of them on the batch this
    # screen was built for, which is DEF-324 exactly.
    qs = models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), batch=batch).select_related(
        "asset"
    )
    if severity:
        qs = qs.filter(severity=severity)
    return [read_row_dict(row) for row in qs.order_by("row_no")]


# ── the r17.2 value read (US-BIL-028; DB-17) ────────────────────────────────
def custom_data_for_location(unit_id: Any) -> dict[str, Any]:
    """A unit's and its premises' tenant-defined values — PUBLISHED FOR BILLING.

    `apps/billing/custom_snapshot.py` — the one module DB-17 allows to touch
    tenant-defined data inside a money path — resolves this by name, so billing
    reads metering's values through metering rather than importing its models
    (B1 / G6 module boundary).

    BOTH ROWS IN ONE QUERY, along `units.premises_id`, because they are one fact
    from the document's point of view: where the service is. Missing unit ⇒ two
    empty maps, which is the same answer as a unit with nothing defined — see
    the note in customers' twin for why that conflation is deliberate.

    `service_points` is NOT here even though r17.2 covers it: a unit can carry
    several, the snapshot's key space is flat `<entity>.<key>`, and nothing
    ruled how two service points' values share one key. OQ-118.
    """
    row = (
        models.Unit.objects.filter(tenant_id=_tenant_id(), pk=unit_id)
        .values_list("custom_data", "premises__custom_data")
        .first()
    )
    if row is None:
        return {"units": {}, "premises": {}}
    unit_values, premises_values = row
    return {
        "units": unit_values if isinstance(unit_values, dict) else {},
        "premises": premises_values if isinstance(premises_values, dict) else {},
    }


# ── CR-028 AST-W5 (AST-03 map) — the geo seam reads assets consumes ─────────


#: *This unit has a point, or its building does* — `BR-MET-1162`'s predicate,
#: named ONCE so the id-only read below and the full index above cannot drift
#: apart about what "geocoded" means (hard-won law 5).
_HAS_A_POINT = Q(lat__isnull=False, lng__isnull=False) | Q(
    premises__lat__isnull=False, premises__lng__isnull=False
)


def geocoded_unit_ids() -> list[str]:
    """Every unit that HAS a point — IDS ONLY, one query, no per-unit dict.

    `CR-092` wave C lane 3. `GET /assets/geo` needs to know which units are
    placed BEFORE it can find the assets standing on them, and it then needs
    the placement detail of only the page it is about to answer with. Asking
    for the full index to get the first half was what made the map's cost
    O(estate) even for fifty markers.
    """
    return [
        str(unit_id)
        for unit_id in models.Unit.objects.filter(tenant_id=_tenant_id())
        .filter(_HAS_A_POINT)
        .values_list("id", flat=True)
    ]


def unit_premises_geo_index(*, unit_ids: Any = None) -> dict[str, dict[str, Any]]:
    """Every unit standing on a GEOCODED premises, keyed by unit id — the
    `GET /assets/geo` seam (B16 §4.6). ONE query for the whole map (the
    DEF-324 discipline), read-only; assets asks, it never joins (B1).

    Coordinates serve as their STORED NUMERIC(9,6) strings — the wire carries
    what the column holds, never a float. `area` is the premises' EXISTING
    BR-MET-071 area NAME (no second area vocabulary exists — see the
    metering 0018 migration docstring). A unit with no point of its own AND a
    premises without coordinates is simply absent: no marker is ever invented.

    ⚠ **CR-089 wave A `PUJ-49` — A UNIT'S OWN POINT WINS, AND THAT IS WHAT THE
    MAP WAS ACTUALLY GETTING WRONG.** `BR-MET-1162` (PO 2026-09-08) lets a unit
    carry its own `lat`/`lng`; before that ruling every unit read its
    building's, so **a park of twelve cabins drew ONE pin at the site office
    with eleven markers stacked underneath it** — twelve meters at twelve
    places, all reported as one. The fallback is unchanged for every unit that
    has no point of its own, which is all 1,109 of them today, so this changes
    no existing pin and is ready for the first cabin park that gets one.

    ⚠ **AND THE FILTER HAD TO MOVE WITH IT.** It read
    `premises__lat__isnull=False`, which would have EXCLUDED a unit that has its
    own point on a building that has none — the exact case the ruling was
    written for (a pad on an unplaced parcel), silently, with the map looking
    healthy. The predicate is now *this unit has a point, or its building does*.

    The two SQL `COALESCE`s keep it ONE query for the whole map (the DEF-324
    discipline); doing the pick in Python would need the four columns anyway and
    the arithmetic is the same, but the `WHERE` could not then be pushed down.
    """
    queryset = models.Unit.objects.filter(tenant_id=_tenant_id()).filter(_HAS_A_POINT)
    if unit_ids is not None:
        # `CR-092` wave C lane 3 / `DEF-MET-4962`: ONE PAGE's units. Without it
        # the map read built a dict for every geocoded unit in the tenant before
        # it knew which fifty it was going to answer with — correct at 1,109
        # units and 21 MB of dictionaries at the top of the stated market.
        # `None` and `[]` are DIFFERENT answers here: `None` is "the whole
        # estate, as before" and `[]` is "these zero units", and conflating them
        # is how a narrowing accidentally serves everything.
        queryset = queryset.filter(id__in=list(unit_ids))
    rows = (
        queryset
        .annotate(
            point_lat=Coalesce("lat", "premises__lat"),
            point_lng=Coalesce("lng", "premises__lng"),
        )
        .values_list(
            "id",
            "label",
            "premises__address_line",
            "point_lat",
            "point_lng",
            "premises__area__name",
            "lat",
        )
    )
    return {
        str(unit_id): {
            "unit": label,
            "premises": address,
            "lat": _coord_str(lat),
            "lng": _coord_str(lng),
            "area": area_name,
            # Which of the two this pin is, on the row rather than derived by
            # the map: `BR-MET-1162` requires the screen to say which point it
            # is showing, and a client comparing coordinates to work that out
            # would be a second definition of the fallback (hard-won law 1).
            "point_source": "unit" if own_lat is not None else "premises",
        }
        for unit_id, label, address, lat, lng, area_name, own_lat in rows
    }


def latest_reads_for_assets(asset_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """`latest_read_for_asset`'s shape for MANY assets in ONE query — the map
    popup's "last read" line must not cost a query per marker (DEF-324).
    Newest committed lineage head per asset; an asset with no committed read
    is absent, and the popup renders the quiet dash — never a zero."""
    wanted = {str(asset_id) for asset_id in asset_ids}
    if not wanted:
        return {}
    out: dict[str, dict[str, Any]] = {}
    rows = (
        _read_heads()
        .filter(asset_id__in=list(wanted))
        .order_by("asset_id", "-read_at", "-id")
        # `current_value` travels with the rest (`DEF-MET-5862`) — see the
        # singular for WHY the reading is not the usage. Selected in the same
        # `values_list` so the batch still costs ONE query (`DEF-324`).
        .values_list("id", "asset_id", "current_value", "consumption", "unit", "read_at")
    )
    for read_id, asset_id, current_value, consumption, unit, read_at in rows:
        key = str(asset_id)
        if key in out:  # ordered newest-first within each asset
            continue
        out[key] = {
            "read_id": str(read_id),
            # ⚠ **THE TWO PATHS MUST STAY BYTE-IDENTICAL.** This function
            # publishes `latest_read_for_asset`'s own shape and `asset_dict`
            # relies on that equality — `test_def5745_registry_row_batching`
            # compares a page row against a single row key for key, so a field
            # added to one and not the other turns that test red rather than
            # drifting quietly.
            "current_value": str(current_value) if current_value is not None else None,
            "consumption": str(consumption) if consumption is not None else None,
            "unit": unit,
            "read_at": read_at.date().isoformat() if read_at else None,
        }
    return out


def register_heads_for_assets(
    asset_ids: list[Any], *, on: Any = None
) -> dict[tuple[str, str], dict[str, Any]]:
    """The newest committed lineage head **per (asset, REGISTER)** for MANY
    assets, in ONE query — `reads_for_unit`'s reduction, at cycle scale.

    **WHY THIS EXISTS BESIDE `reads_for_unit` (CR-054 W1 task 4).** That
    function answers the same question and answers it for ONE UNIT. The
    generated reading sheet asks it for a whole cycle — up to a few thousand
    meters behind one download button — and calling a per-unit selector in a
    loop is a query per unit, which is DEF-324 exactly. So the SET is widened
    and the shape kept: same `_read_heads()` (tenant-scoped, lineage heads
    only, BR-MET-016/053), same newest-first-within-key reduction, same
    `read_is_estimated` derivation. `reads_for_unit` stays the published
    customers seam and its payload does not move.

    Two fields this returns that `reads_for_unit` does not, both because a
    reading SHEET is not a usage report:

      * **`current_value` — the REGISTER's own figure**, which is what a clerk
        compares against the dial and what the route sheet already prints
        (`route_sheet.meter_dict`'s `last_value`). `consumption` is the delta
        between two reads and is the wrong number to put in a column headed
        *previous reading*.
      * **`estimated`**, because BR-MET-028 gives an estimate a consumption and
        **no `current_value`** — nobody read the dial — so the sheet must be
        able to say why the cell is a dash rather than leaving it blank.

    `on` is AS-OF (BR-TEN-043 — the event date is an argument), the same
    meaning `reads_for_unit` gives it. A (asset, register) pair with no head is
    simply ABSENT from the map: a register never read is ABSENT, never a zero
    (BR-MET-106), and every caller renders that absence itself.
    """
    wanted = [str(asset_id) for asset_id in asset_ids]
    if not wanted:
        return {}
    rows = _read_heads().filter(asset_id__in=wanted)
    if on is not None:
        rows = rows.filter(read_at__lt=_day_after(on))
    rows = rows.order_by("asset_id", "channel", "-read_at", "-id").values_list(
        "id",
        "asset_id",
        "channel",
        "current_value",
        "consumption",
        "unit",
        "read_at",
        "status",
        "disposition",
    )
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for read_id, asset_id, channel, current_value, consumption, unit, read_at, status, disp in rows:
        key = (str(asset_id), channel)
        if key in out:  # ordered newest-first within each (asset, channel)
            continue
        out[key] = {
            "read_id": str(read_id),
            "channel": channel,
            # Decimals, not strings: the caller formats through
            # `quantity_display.quantity_text` (BR-MET-144), and pre-stringing
            # them here would make that the second formatter in the path.
            "current_value": current_value,
            "consumption": consumption,
            "unit": unit,  # rule 3 — never separated from the number
            "read_at": read_at.date().isoformat() if read_at else None,
            "estimated": read_is_estimated(status, disp),
        }
    return out


# ── CR-038 W9 task 2 — the unit-reads seam target (customers → metering) ────
#: `DEF-CUS-9753` — the asset-type categories whose devices are READ. Defined
#: once in `completeness` (which this module imports) and named here too.
READ_DEVICE_CATEGORIES: tuple[str, ...] = completeness.READ_DEVICE_CATEGORIES


def _is_read_device(row: dict[str, Any]) -> bool:
    """Is this `assets_on_unit(s)` row a device somebody reads? (`DEF-CUS-9753`)

    Read off the row's `tab` — the asset TYPE's category (BR-AST-004), never
    the service name, so a tenant's own types (BR-TEN-036) answer correctly.
    """
    return row.get("tab") in READ_DEVICE_CATEGORIES


def reads_for_unit(unit_id: Any, *, on: Any = None, since: Any = None) -> dict[str, Any]:
    """Every committed lineage head at a unit, per meter and per register.

    **PUBLISHED FOR `apps.customers.seams.reads_for_unit` (CR-038 W9 task 2)**
    — the read seam `apps/customers/move_reads.py` §4 named as missing, which
    left the move worklists' READS / FINAL READ cells and the `FINAL READS DUE`
    tile as stated absences. Customers asks; it never joins (B1). The shape is
    `latest_read_for_asset`'s (DEF-592), widened per the consumer's need:
    `source`, `lifecycle` and the estimation marker travel with each head.

    THE CONTRACT:

        reads_for_unit(unit_id, on=date|None) -> {
            "unit_id": str,
            "as_of":   "YYYY-MM-DD" | None,   # echoes `on`; None = uncapped
            "meters": [                        # every asset CURRENTLY assigned
                {"asset_id", "asset_no", "type", "qualifier",
                 "latest_read_at": "YYYY-MM-DD" | None,   # max across registers
                 "registers": [                # newest head per channel
                     {"read_id", "channel",
                      "current_value": str | None,              # THE READING
                      "consumption": str | None, "unit": str,   # rule 3 — together
                      "read_at": "YYYY-MM-DD",
                      "source", "lifecycle",
                      "estimated": bool, "estimation_method": str | None,
                      "event_context": str | None}, …]},
                …]}

    · **Only READ devices** (`DEF-CUS-9753`): meters and sub-meters by their
      type's category. A cart standing on the unit is not a meter and was
      held as an unread one, so a move-in waited on it for ever.
    · **The meter set is the registry's own** — `seams.assets_on_unit`, the
      published S15 "Meters" read over current assignments (BR-AST-028's one
      registry), reached through this module's OWN seam because assets owns the
      rows (B2 r4). A unit with nothing assigned answers `meters: []`, which a
      consumer must state, never score.
    · **Heads only** (BR-MET-016/053): `_read_heads()` — tenant-scoped, and
      `superseded_by_id__isnull=True` so a corrected read is represented by its
      correction and a closed row is invisible, not demoted.
    · **`on` is AS-OF** (BR-TEN-043 — the event date is an argument): heads
      at/limited to that date, so a caller can ask what was known on the day.
      `None` means the latest heads outright, which is what the move worklists
      compare against their own event dates.
    · **`since` is FIRST-ON-OR-AFTER (`DEF-CUS-9726`, CR-171-BRC10).** With a
      date, each register answers its OLDEST head dated on/after that day
      instead of its newest, and a register with none is absent. It is the
      move-in's *opening read* — the first read of the tenancy — which neither
      the newest head (a cycle read twenty days later) nor an as-of head (the
      previous occupant's last read) is. `as_of` still echoes `on`.
    · **A register with no head is ABSENT, not zero**: `registers` simply lacks
      the channel, and `latest_read_at: None` means "never read" — nothing
      downstream may treat either as a measured 0 (the `latest_read_for_asset`
      posture, stated again because this payload feeds a KPI).
    · **ONE `meter_reads` query for the whole unit** however many meters it
      holds (DEF-324): newest-first within (asset, channel), reduced in Python
      — the `latest_reads_for_assets` pattern. No money, no derivation beyond
      the per-meter max; `estimated` is `read_is_estimated`, the same
      derivation billing reads.
    """
    meters = [row for row in seams.assets_on_unit(unit_id) if _is_read_device(row)]
    heads_by_asset: dict[str, list[dict[str, Any]]] = {}
    asset_ids = [row["id"] for row in meters]
    if asset_ids:
        rows = _read_heads().filter(asset_id__in=asset_ids)
        if on is not None:
            rows = rows.filter(read_at__lt=_day_after(on))
        if since is not None:
            rows = rows.filter(read_at__gte=_day_start(_as_day(since)))
        newest_first = ("-read_at", "-id") if since is None else ("read_at", "id")
        rows = rows.order_by("asset_id", "channel", *newest_first).values_list(
            "id",
            "asset_id",
            "channel",
            "current_value",
            "consumption",
            "unit",
            "read_at",
            "source",
            "lifecycle",
            "status",
            "disposition",
            "estimation_method",
            "event_context",
        )
        seen: set[tuple[str, str]] = set()
        for (
            read_id,
            asset_id,
            channel,
            current_value,
            consumption,
            unit,
            read_at,
            source,
            lifecycle,
            status,
            disposition,
            estimation_method,
            event_context,
        ) in rows:
            key = (str(asset_id), channel)
            if key in seen:  # newest-first (oldest-first with `since`) per (asset, channel)
                continue
            seen.add(key)
            heads_by_asset.setdefault(str(asset_id), []).append(
                {
                    "read_id": str(read_id),
                    "channel": channel,
                    # ── THE READING ITSELF (`DEF-CUS-5910`) ────────────────
                    #
                    # ⚠ **THIS SHAPE CARRIED THE USAGE AND NOT THE READING,
                    # AND ON AN OPENING READ THAT IS NOTHING AT ALL.** It is
                    # `DEF-MET-5862` exactly one selector over, and the
                    # reasoning is `latest_read_for_asset`'s, unchanged:
                    # `consumption` is the DELTA between two reads, so the
                    # FIRST read on a register has `prior_value` null and
                    # `consumption` null. **Measured on the move-in scenario
                    # suite's `S5`:** the register a clerk really read holds
                    # `current_value=41680.000000` — the blueprint's own drawn
                    # `41,680` — with `consumption=None`, so the move record
                    # showed it as `Not estimated` and **counted it among the
                    # UNREAD registers**. Two, where one register was unread.
                    #
                    # ⚠ **INDEPENDENTLY NULLABLE FROM `consumption`, AND BOTH
                    # DIRECTIONS HAPPEN.** A first read has a reading and no
                    # usage; an ESTIMATE has a usage and NO reading at all
                    # (`BR-MET-028` — nobody read the dial). Neither is derived
                    # from the other and neither is ever defaulted to zero
                    # (`BR-MET-106`, `DEF-079`: absent is not a measurement).
                    "current_value": (
                        str(current_value) if current_value is not None else None
                    ),
                    "consumption": str(consumption) if consumption is not None else None,
                    "unit": unit,  # rule 3 — never separated from the number
                    "read_at": read_at.date().isoformat() if read_at else None,
                    "source": source,
                    "lifecycle": lifecycle,
                    "estimated": read_is_estimated(status, disposition),
                    "estimation_method": estimation_method,
                    # `DEF-CUS-9765` — the lifecycle event the reading was
                    # entered for (`EVENT_CONTEXTS`: `move_in` …), or None for
                    # an ordinary read. Image 24's SOURCE column.
                    "event_context": event_context,
                }
            )
    out_meters: list[dict[str, Any]] = []
    for meter in meters:
        registers = heads_by_asset.get(str(meter["id"]), [])
        dates = [head["read_at"] for head in registers if head["read_at"]]
        out_meters.append(
            {
                "asset_id": str(meter["id"]),
                "asset_no": meter["asset_no"],
                "type": meter.get("type"),
                "qualifier": meter.get("qualifier"),
                "registers": registers,
                # ISO dates compare lexically == chronologically; derived ONCE
                # here so no consumer re-reduces across registers its own way.
                "latest_read_at": max(dates) if dates else None,
            }
        )
    return {
        "unit_id": str(unit_id),
        "as_of": on.isoformat() if on is not None else None,
        "meters": out_meters,
    }


def latest_read_dates_for_units(unit_ids: Any) -> dict[str, dict[str, Any]]:
    """`reads_for_unit`'s `meters[].latest_read_at`, for MANY units, in a
    bounded number of queries — `CR-171-BRC10` P1.04.

    **PUBLISHED FOR `apps.customers.seams.latest_read_dates_for_units`.** The
    Move-ins list must tell a committed move-in that is still *waiting on a
    read* from one that is *completed*, as a FILTER and a TILE over every live
    move-in, not just the page — and `reads_for_unit` is a per-unit read, so a
    sweep of it is one round trip per unit (the `DEF-324` / `CR-131` shape).
    Here: `assets_on_units` (three queries, whatever the size) and ONE grouped
    `MAX(read_at)` over the same committed heads `reads_for_unit` reads.

    The shape is a SUBSET of `reads_for_unit`'s, key for key, so
    `customers.move_reads.unit_reads_cell` reads either without a branch:
    `{unit_id: {"unit_id", "as_of": None, "meters": [{"asset_id", "asset_no",
    "type", "qualifier", "registers": [], "latest_read_at"}]}}`. `registers`
    is EMPTY on purpose — the list needs the date, not the figures, and a
    caller that wants figures calls `reads_for_unit`. Every unit asked about is
    present (an empty `meters` list is the *no meters* answer, never absence).

    ⚠ **THE MAX OVER ALL OF AN ASSET'S HEADS IS THE MAX OVER ITS PER-REGISTER
    HEADS**: `reads_for_unit` keeps the newest head per (asset, channel) and
    then takes the max of those dates, which is the newest head of the asset.
    `tests/test_cr171_p1_04_move_ins_list.py` holds the two equal.
    """
    from django.db.models import Max

    ids = [str(u) for u in (unit_ids or []) if u not in (None, "")]
    out: dict[str, dict[str, Any]] = {
        uid: {"unit_id": uid, "as_of": None, "meters": []} for uid in dict.fromkeys(ids)
    }
    if not ids:
        return out
    # `DEF-CUS-9753` — read devices only, exactly as `reads_for_unit`.
    by_unit = {
        uid: [row for row in rows if _is_read_device(row)]
        for uid, rows in seams.assets_on_units(ids).items()
    }
    asset_ids = [row["id"] for rows in by_unit.values() for row in rows]
    latest: dict[str, str] = {}
    if asset_ids:
        for asset_id, newest in (
            _read_heads()
            .filter(asset_id__in=asset_ids)
            .order_by()
            .values("asset_id")
            .annotate(newest=Max("read_at"))
            .values_list("asset_id", "newest")
        ):
            if newest is not None:
                latest[str(asset_id)] = newest.date().isoformat()
    for uid, rows in by_unit.items():
        bucket = out.setdefault(str(uid), {"unit_id": str(uid), "as_of": None, "meters": []})
        for meter in rows:
            bucket["meters"].append(
                {
                    "asset_id": str(meter["id"]),
                    "asset_no": meter["asset_no"],
                    "type": meter.get("type"),
                    "qualifier": meter.get("qualifier"),
                    "registers": [],
                    "latest_read_at": latest.get(str(meter["id"])),
                }
            )
    return out


def export_rollup_last_month(today: Any = None) -> dict[str, Any]:
    """CR-028 debt sweep D4 — the BTM tab's "Exported · <month>" KPI figure.

    The sum of EXPORT-channel quantities (`consumption`, committed lineage
    heads only — BR-MET-016/053) whose `read_at` falls inside the LAST
    COMPLETE month of the tenant's own calendar (BR-TEN-020 — never a wall
    clock; `today` is a test pin). Export records exist only on net-metering
    assets (BR-AST-029 refuses them anywhere else), so "total exported by
    exporting devices" needs no asset join. ONE query (the DEF-324 posture).

    Grouped BY UNIT (CLAUDE.md rule 3): a quantity never travels without its
    unit, and two units are two totals — never added together. `totals` is
    empty when the month holds no export record; the KPI then renders its
    quiet dash, and nothing may treat that as a measured zero. The 0-value
    `status="missing"` placeholders BR-AST-029 mints contribute exactly their
    recorded 0 — they are committed records, not guesses. QUANTITIES ONLY —
    no money, no rate, no credit (BR-AST-025).
    """

    if today is None:
        today = seams.tenant_today()
    month_end = today.replace(day=1) - timedelta(days=1)  # last day of the prior month
    month_start = month_end.replace(day=1)
    # ⚠ SUMMED IN PYTHON, NOT `.values("unit").annotate(Sum(...))`:
    # `_read_heads()` keeps only the reading that COUNTS on a same-day pair
    # (BR-MET-1189) through a window, and Django groups an aggregate over a
    # window-filtered queryset by the window columns too — the totals come out
    # per reading. The rows are one month of export reads.
    totals: dict[Any, Any] = {}
    for unit, consumption in (
        _read_heads()
        .filter(
            channel=models.CHANNEL_EXPORT,
            read_at__gte=_day_start(month_start),
            read_at__lt=_day_after(month_end),
        )
        .values_list("unit", "consumption")
    ):
        if consumption is None:
            totals.setdefault(unit, None)
            continue
        totals[unit] = (totals.get(unit) or 0) + consumption
    grouped = [{"unit": unit, "quantity": totals[unit]} for unit in sorted(totals, key=str)]
    from decimal import Decimal

    return {
        "month": month_start.isoformat(),
        "totals": [
            # Canonical 6 dp, as stored consumption strings serve everywhere
            # (sqlite's Sum drops trailing places; Postgres keeps them — the
            # quantize makes both serve one spelling).
            {
                "quantity": str(Decimal(row["quantity"]).quantize(Decimal("0.000001"))),
                "unit": row["unit"],
            }
            for row in grouped
            if row["quantity"] is not None
        ],
    }


# ── CR-030 W5 tasks 5.2 / 5.3 — the move-in wizard's two unit READS ─────────
#
# B18 §5.5.5 adds `GET /units/{id}/assets` (step 3) and `GET /units/{id}/pricing`
# (step 4). Both are READS and both are assembled HERE so `api.py` stays thin
# (LAW 0). Neither writes anything, and neither computes money.
#
# ⚠ **NEITHER OF THESE TOUCHES ANOTHER MODULE'S ORM.** Assets and rating both
# own their tables (B2 §2); everything below arrives through
# `apps/metering/seams.py` — either one of its documented callables or its
# `resolve()` late binding, the shape `units_list`'s meter search already uses
# for `unit_ids_for_asset_search`. A neighbour that publishes nothing yields a
# STATED ABSENCE with a reason code, never a fabricated value.

#: B18 §5.5.5: *"everything at the unit, grouped meters / sub-meters /
#: behind-the-meter"*. These are `assets.asset_types.category` verbatim
#: (BR-AST-004 — exactly one tab per asset), in the order the panel draws them.
#: A row whose type resolves to none of the three is served under
#: `unclassified` rather than being dropped or forced into `meters`.
UNIT_ASSET_GROUPS = ("meters", "sub_meters", "behind_the_meter")

#: DEF-495 (OPEN): `tenant_services.metered` — BR-RAT-081's declaration of
#: whether a service is measured at all — HAS NO READER ANYWHERE IN THE
#: PRODUCT. So this payload cannot say which of a unit's assets a reading is
#: expected for (B18 TC-MVI-4's *"a reading is asked for the billable meters
#: only"*), and it says THAT instead of guessing. Deriving it from the asset
#: category would be a guess: a sub-meter is read and a cart is not, and both
#: are known only through the declaration nothing reads.
READING_EXPECTED_TRACKS = "DEF-495"


def _asset_type_index() -> dict[str, dict[str, Any]]:
    """`type code -> {name, category}` from the assets registry's own catalog.

    ONE read for the whole panel (DEF-324's rule: never ask a screen-shaped
    question once per row). `{}` while assets publishes no catalog, which the
    caller renders as `unclassified` — an honest "we could not classify this"
    rather than a group the asset may not belong in.
    """
    fn = seams.resolve("assets", "asset_types", kind="selectors")
    if fn is None:
        return {}
    return {
        str(row.get("code")): {"name": row.get("name"), "category": row.get("category")}
        for row in fn()
        if row.get("code")
    }


def _service_code_by_asset(unit_id: Any) -> dict[str, str]:
    """`asset id -> service code`, resolved through METERING'S OWN service points.

    The chain is metering's: a unit has service points, a service point names a
    service, and an asset stands on a service point (the reviewed cross-module
    FK, B2 §2). So the service is answered from this module's rows plus the
    already-documented `asset_ids_for_service_point` seam, and assets is never
    asked to re-state a fact metering owns.
    """
    out: dict[str, str] = {}
    for point in service_points_for(unit_id):
        code = point.get("service")
        if not code:
            continue
        for asset_id in seams.asset_ids_for_service_point(point["id"]):
            out[str(asset_id)] = code
    return out


def _last_read_position(asset_id: Any) -> dict[str, Any] | None:
    """The newest COMMITTED lineage head on one asset — what a start read follows.

    Step 3 asks the clerk for a reading, so the useful fact is where the
    register stood when it was last read, not only how much was consumed.
    Both are served and **consumption never travels without its unit**
    (hard rule 3); `None` means no committed read exists and NOTHING downstream
    may read that as a zero.

    ⚠ **THE TOTAL REGISTER FIRST (`DEF-MET-10094`, 2026-10-12).** A demand meter
    is read on two channels the same day (`total` kWh and `demand` kW), and
    ordering by `read_at, id` alone picked whichever row was inserted last. The
    move-out and move-in reading rows prefill from this answer, and the event
    door they post through writes `channel=total` when a row names none — so a
    row opened on `Demand 11 kW` posted `11` against a 21,502 kWh register and
    was refused as negative usage. The register the door writes is the one this
    answers; another channel is the fallback only when total was never read.
    """
    heads = _read_heads().filter(asset_id=asset_id).order_by("-read_at", "-id")
    row = heads.filter(channel=models.CHANNEL_TOTAL).first() or heads.first()
    if row is None:
        return None
    return {
        "read_id": str(row.id),
        "read_at": row.read_at.date().isoformat() if row.read_at else None,
        "channel": row.channel,
        "current_value": str(row.current_value) if row.current_value is not None else None,
        # DEF-1086 / BR-SHL-250 — the reading, composed with its unit exactly
        # once. `UnitAssetsPanel` printed `str(row.current_value)` straight into
        # a span, so this panel read `42864.000000` where RDS-01 now reads
        # `42864 kWh`.
        "current_value_display": (quantity_display.quantity_with_unit(row.current_value, row.unit)),
        "consumption": str(row.consumption) if row.consumption is not None else None,
        "unit": row.unit,
    }


def _unit_ref(unit: models.Unit) -> dict[str, Any]:
    """The header both W5 panels draw above their content."""
    return {
        "id": str(unit.id),
        "unit_no": unit.unit_no,
        "label": unit.label,
        "premises_id": str(unit.premises_id),
        "premise_no": unit.premises.premise_no,
        "premise_address": unit.premises.address_line,
    }


def unit_assets(unit_id: Any) -> dict[str, Any]:
    """B18 W5 task 5.2 — move-in step 3's asset panel, POST-CR-028.

    *"Every meter, sub-meter and behind-the-meter device at the unit"*
    (B18 §5.5.3 step 3). CR-030 step 4 correction 2 is explicit that this must
    be specified against the model CR-028 reshaped, so the grouping key is
    `asset_types.category` — BR-AST-004's *exactly one tab per asset* — and NOT
    the `(sub)/(master)` qualifier the S15 cell uses. The two disagree on the
    case the test asks about: a behind-the-meter inverter hangs off its meter
    by `parent_asset`, so the qualifier calls it a sub-meter and the category
    calls it a device. TC-MVI-4's four assets group 2 / 1 / 1 only on the
    category.

    An empty unit is an EMPTY PANEL, never an error: a unit with nothing
    installed is a real and common state at move-in.

    ⚠ **WHAT THIS DELIBERATELY DOES NOT SERVE.** `reading_expected` — which of
    these a reading is asked for — is stated as an ABSENCE carrying `DEF-495`,
    because BR-RAT-081's metered/unmetered declaration has no reader in this
    product and no other fact answers the question (see
    `READING_EXPECTED_TRACKS`). No money of any kind appears here.
    """
    unit = unit_row(unit_id)
    types = _asset_type_index()
    services = _service_code_by_asset(unit.id)
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in UNIT_ASSET_GROUPS}
    grouped["unclassified"] = []
    for row in seams.assets_on_unit(unit.id):
        asset_id = str(row.get("id"))
        type_code = row.get("type")
        catalog = types.get(str(type_code), {})
        category = catalog.get("category")
        bucket = category if category in UNIT_ASSET_GROUPS else "unclassified"
        grouped[bucket].append(
            {
                "id": asset_id,
                "asset_no": row.get("asset_no"),
                "type": type_code,
                "type_name": catalog.get("name"),
                "category": category,
                # The S15 cell's (sub)/(master) tag, kept beside the category
                # rather than instead of it — a master meter is a `meters` row
                # that other rows hang off, which is two facts, not one.
                "qualifier": row.get("qualifier"),
                "service": services.get(asset_id),
                "last_read": _last_read_position(asset_id),
            }
        )
    return {
        "unit": _unit_ref(unit),
        "groups": [
            {"category": name, "assets": grouped[name]}
            for name in (*UNIT_ASSET_GROUPS, "unclassified")
        ],
        "counts": {
            **{name: len(grouped[name]) for name in (*UNIT_ASSET_GROUPS, "unclassified")},
            "total": sum(len(rows) for rows in grouped.values()),
        },
        "reading_expected": {
            "served": False,
            "reason": "metered_declaration_has_no_reader",
            "tracks": READING_EXPECTED_TRACKS,
        },
    }


def _service_priced_on(service_code: Any) -> dict[str, Any]:
    """**WHAT DECIDES THIS SERVICE'S CHARGE, AS A SHAPE THE SCREEN CAN SAY OUT
    LOUD** — `CR-089` wave H `H3` / `PUJ-35`, and the rule the decision log of
    2026-09-08 records with no home until `BR-MET-1166`.

    **THE PROBLEM, IN ONE ROW.** The Plan tab prints `Fire · $0.00` beside
    `Water · $8.00`, and a zero there is CORRECT: fire is priced by the size of
    the line multiplied by how many there are (`CR-063`), trash per cart, solar
    by capacity. Three of six services on the Product Owner's own screen read
    `$0.00` with nothing to say whether that means FREE or PRICED SOME OTHER
    WAY, and *"a fire customer's `$0.00` base is right and reads as broken."*

    ⚠ **THIS COMPUTES NO MONEY AND READS NO PRICE.** It answers one question —
    *what AXIS prices this service* — and the answer is `apps.tenancy`'s ratified
    law, not an inference of ours. B4/B5 are ❄️ FROZEN and nothing here goes
    near them.

    ⚠ **THE BANDED TEST IS `apps.rating.resolution.service_prices_by_size_class`
    AND IS NOT REWRITTEN HERE, WHICH IS THE WHOLE POINT OF IMPORTING IT.** That
    function's own docstring records `DEF-3098`: three places in this product
    needed to know whether a service is priced BY BAND and all three asked
    *"does it have any size class rows?"* instead — a proxy that was sound until
    `CR-062` gave solar, battery, storm water and broadband a CATALOGUE of
    installable equipment, at which point a battery schedule stating no per-size
    rows *"flipped from one ladder at the blank size to no size priced at all"*
    and no battery or solar customer could be billed. A fourth place asking the
    old question would be that defect a fourth time. It is a pure function over
    two `service_size_classes` lookups — no model, no query — which is the same
    local-import precedent `bills_one_line_per_size` above already sets.

    **THREE SHAPES, EACH A DIFFERENT RULED FACT:**

        capacity      solar, battery, storm water, broadband — the size classes
                      ARE quantities and the billable amount is their SUM. The
                      unit rides along, because *"the kW installed"* says
                      something *"by capacity"* does not.
        size_bands    water, electric, gas, trash, FIRE — the band picks a rate
                      and the COUNT multiplies it. Fire's own worked figure: a
                      6" line and two 2" lines is `1 x $60.00 + 2 x $12.00`.
        no_size_axis  sewer — ruled to have no size class at all (`BR-RAT-015`:
                      a share of the water usage charge).

    ⚠ **AND A FOURTH ANSWER THAT IS NOT A SHAPE: `not_ruled`.** Thermal steam's
    bands were never put to the Product Owner (`OQ-560`) and
    `size_class_records_for_service` RAISES for it by name. The prime directive
    forbids resolving that by choosing a value, so it is forwarded as the
    absence it is and the screen says so. A `KeyError` — a code that is not one
    of the eleven — takes the same branch and for the same reason: this is a
    read on a screen, and neither is worth a 500.

    ⚠ **NO SERVICE IS NAMED IN THIS FUNCTION**, deliberately, exactly as
    `bills_one_line_per_size` says of itself: the twelfth service lands on
    whichever side its own ratified rows put it, with no edit here.
    """
    from apps.rating.resolution import service_prices_by_size_class
    from apps.tenancy import service_size_classes

    code = str(service_code or "")
    try:
        rows = service_size_classes.size_class_records_for_service(code)
        capacity_uom = service_size_classes.capacity_uom_for_service(code)
        banded = service_prices_by_size_class(code)
    except (service_size_classes.SizeClassNotRuled, KeyError):
        return {"shape": "not_ruled", "capacity_uom": None, "size_count": None}
    # ⚠ **THE BANDED QUESTION IS ASKED FIRST, AND THE ORDER IS THE GUARD RATHER
    # THAN A STYLE CHOICE (found by running the red proof, 2026-09-09).** The
    # first draft tested `capacity_uom is not None` first and fell through to
    # `banded`, which made `service_prices_by_size_class` UNREACHABLE for every
    # capacity service — so swapping in `DEF-3098`'s old proxy question changed
    # nothing and the test written to catch that swap stayed green. A check that
    # cannot fail is worse than no check, because it is trusted (hard-won law
    # 7). Asking the ruled question first means the proxy misclassifies solar,
    # battery, storm water and broadband as banded and the suite says so.
    if banded:
        shape = "size_bands"
    elif capacity_uom is not None:
        shape = "capacity"
    else:
        shape = "no_size_axis"
    return {"shape": shape, "capacity_uom": capacity_uom, "size_count": len(rows)}


def _rating_read(name: str) -> Any:
    """One rating SELECTOR, late-bound. None while rating publishes nothing."""
    return seams.resolve("rating", name, kind="selectors")


def _rate_schedule_card(tariff_id: Any, as_of: date | None = None) -> dict[str, Any] | None:
    """One plan rate schedule projected onto what step 4 draws, AS OF ONE DATE.

    `schedule_detail` is rating's own read and carries the WHOLE filing history
    (`versions`, with a person resolved per row). Step 4 shows what a customer
    will be charged, so the in-force version and its blocks are forwarded and
    the history is not — a wizard step is not the rate-case screen.

    Every figure here is rating's string, forwarded VERBATIM. Nothing is
    re-rounded, re-quantized or summed: money is stored to 4 decimals and
    percentages to 6 (PO re-sign 2026-08-22) and this module does no money math.

    ⚠ **`as_of` IS THE SERVICE DATE, AND `None` IS THE TENANT'S TODAY** — which
    is what this function has always asked for implicitly, so passing nothing
    resolves the same version it always did. BR-RAT-007 is why it is now
    sayable: the version in force on the SERVICE date is what prices a period,
    and a screen that always asked about today would show next month's rates as
    this month's the day a filing takes effect. Rating narrows it
    (`in_force_version`); nothing here picks a version.
    """
    fn = _rating_read("schedule_detail")
    if fn is None:
        return None
    try:
        card = fn(tariff_id, as_of)
    except errors.NotFoundError:
        return None
    return {
        "id": card.get("id"),
        "name": card.get("name"),
        "service": card.get("service"),
        "service_name": card.get("service_name"),
        "structure": card.get("structure"),
        "status": card.get("status"),
        "effective_from": card.get("effective_from"),
        "block_count": card.get("block_count"),
        "season_labels": card.get("season_labels"),
        "window_count": card.get("window_count"),
        "size_count": card.get("size_count"),
        # The blocks themselves — the in-force version's own structure.
        "current_version": card.get("current_version"),
        # BR-RAT-038: a schedule priced in a unit the service does not bill in
        # is a bill that cannot be produced. Step 4 must be able to say so.
        "uom_gate": card.get("uom_gate"),
    }


#: CR-034 (b) · WHERE THE PERIOD CAME FROM, as a value rather than a sentence,
#: because the screen prints a different heading for each and a client must not
#: infer which one it is holding from whether `start` happens to be null.
PERIOD_FROM_CALLER = "caller"
PERIOD_DEFAULTS_TO_TODAY = "not_supplied_defaults_to_today"


def unit_pricing(
    unit_id: Any,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, Any]:
    """B18 W5 task 5.3 + **CR-034 (b)** — what this unit is priced on, FOR A
    STATED PERIOD: *"what exactly will be use from plan for this unit when
    billing happens"*.

    🔒 **HUMAN-REVIEW-PENDING** — AI-authored beside a sensitive path under the
    PO ruling of 2026-08-09 (*"AI will do it; we will review it later as
    human"*). ⚠ **AND THE MARKER IS NOT ENOUGH ON ITS OWN, WHICH IS STATED
    RATHER THAN LEFT TO LOOK COVERED (hard-won law 1):**
    `10-scripts/gates/human_owned.txt` matches NO glob against
    `apps/metering/selectors.py`, so **G7 does not read this line** — it is a
    note to a human, not a guard. Adding a glob is a process event and the PO's
    call, not a lane's (the guard file's own `apps/rating/selectors.py`
    precedent), so it is put to the review ledger instead of taken here.

    🔒 **THIS READ TOUCHES RATING MATH AND DELIBERATELY PERFORMS NONE OF IT.**
    B4 and B5 are ❄️ FROZEN and GT-1..61 are the billing-math contract. Every
    figure below is a STORED value read back through rating's own selectors and
    forwarded verbatim — no sum, no rounding, no proration, no tax. A second
    implementation of billing math is the worst outcome available on this
    endpoint, so there is not one. **`minimum_charges` is an ASSEMBLY of three
    strings rating already served into one section — not a sum, not a `min()`,
    not a comparison.** The moment this function picks the smaller of two
    floors, it has implemented BR-RAT-016/028 outside the engine.

    ── THE PERIOD, AND WHY NONE IS INVENTED (CR-034 (b)) ──────────────────────
    The PO asked for the period to be stated: *"showing in - what period you
    are reporting data for"*. So the caller supplies one, and **`as_of` is its
    END date** — BR-RAT-007's own pivot, quoted by `rating.resolution
    .resolve_plan`: *"the plan version in force on the SERVICE-PERIOD END
    DATE"*. Every dated narrowing below happens on that one date.

    ⚠ **A CALLER THAT SUPPLIES NOTHING GETS `period: null` AND `as_of` = THE
    TENANT'S TODAY — never a default month.** The defaulted answer is
    byte-identical to what this endpoint served before CR-034 (b), which is the
    point: the move-in wizard's step 4 is unchanged. And the alternative was
    tested against a calendar before being declined — on the 25th, a default
    period of *the current month* makes `as_of` the 31st, which resolves a rate
    version **effective the 28th that is not in force today**, and a customer
    signing up is shown next month's prices as the ones that will bill them.
    Choosing a default period is a product decision with that consequence, so
    it goes to the PO rather than into a constant here.

    ── R1 OVER A PERIOD: THE SPLIT IS REPORTED, NEVER COLLAPSED ───────────────
    A unit's plan can CHANGE inside a period (BR-RAT-114 / DEF-504 — a customer
    who moved plans on the 15th is gathered once per stretch, each on ITS plan).
    `plan_history.stretches` reports every stretch overlapping the window from
    rating's own `unit_plan_assignments_in`, and `splits_at` names the dates a
    real bill would split on. **Nothing here picks one stretch and prints it as
    "the plan".** The sections below resolve on `as_of` — one DATE, which R1's
    law answers with exactly one plan — and the screen says which date that was
    and that the period contains others.

    An EMPTY history is not "no plan" (rating's own words): a unit assigned
    before the table existed has no rows, and the fallback is the unit's current
    plan, exactly as `billing/gather.py` has always fallen back.

    ── WHAT CANNOT BE ANSWERED FROM A UNIT, AND IS SAID RATHER THAN GUESSED ───
    **Discounts.** `plan_discount_rules` is what the plan **OFFERS**
    (BR-RAT-110) **and, since CR-034 §7's amendment of 2026-08-26, what a
    customer must satisfy to avail each one** — `offered[].terms`, rating's own
    stored conditions, forwarded whole. The PO, verbatim: *"We should show all
    discount plan offer and what condition are required to avail that discount ;
    when account is attached it will avail those discounts"*. ⚠ **What a screen
    may NOT say is that any of it is CHECKED**: `eligibility_rule` is advisory
    and nothing in this product evaluates it, so `terms.eligibility_checked` is
    a stated absence. The **GRANT** is the only thing that reduces a bill
    (BR-RAT-069 — binding a discount to a plan grants it to nobody; a bill run
    reads `discount_enrolments`), and an enrolment belongs to an ACCOUNT, which
    a unit does not have. So `discounts.granted` is a stated absence, exactly
    the shape `rating.resolution.DiscountResolution.modelled` uses for the same
    class of fact: *"this product cannot express it"* and *"this customer has
    none"* are different, and so are *"offered"* and *"granted"*.

    ⚠ **RATING'S `enrolled` COUNT IS DROPPED RATHER THAN LABELLED.** It is
    TENANT-WIDE, not plan-scoped and certainly not unit-scoped (rating says so
    in `plan_discount_rules`' own docstring), and a number rendered on a unit
    screen is read as that unit's however the caption is worded. An absent
    figure is safer than a correctly-labelled misleading one.

    **Taxes.** What is served is the plan's BINDINGS (BR-RAT-096) and
    ATTACHMENTS (BR-RAT-113) — **not R7's narrowing**, which also needs the
    account's customer class (DEF-273: three of r10's five Texas rates scope by
    class). `taxes.narrowing` says so, so nothing reads this list as the final
    set of tax lines.

    **Contract.** No contract object exists in this product. Served as an
    absence with `tracks: null` — an OQ is OWED and is REPORTED rather than
    minted in code (the prime directive; and DEF-445: an absence citing a
    fabricated id is worse than one citing none).

    ⚠ **THE WORKED MONTH IS STILL NOT SERVED AND STILL SAYS SO (OQ-363).** The
    PO re-scoped CR-034 (b) away from it; the two blockers it names are
    unchanged, and **(b) — no signed rule states the consumption — survives (a)
    being solved.** DO NOT "fix" it by summing the base charges below: that is
    BR-RAT-005's tax base reimplemented outside the ❄️ FROZEN engine.
    """
    unit = unit_row(unit_id)
    supplied = period_start is not None and period_end is not None
    # The END date, because BR-RAT-007 prices a period on its service date and
    # `resolve_plan` reads that as the period END. `tenant_today` (BR-TEN-043)
    # is the tenant's clock, never the server's.
    as_of: date = period_end if supplied and period_end is not None else seams.tenant_today()
    payload: dict[str, Any] = {
        "unit": {
            **_unit_ref(unit),
            "rate_plan_id": str(unit.rate_plan_id) if unit.rate_plan_id else None,
            "plan_effective_from": (
                unit.plan_effective_from.isoformat() if unit.plan_effective_from else None
            ),
            "plan_locked": unit.plan_locked,
        },
        # ⚠ SECTION 1 — what window this answer is about. Served on EVERY
        # response including the absences below, so a screen can print its
        # heading before it knows whether there is a plan to describe.
        "period": {
            "start": period_start.isoformat() if supplied and period_start else None,
            "end": period_end.isoformat() if supplied and period_end else None,
            #: The one date every narrowing below was resolved on.
            "as_of": as_of.isoformat(),
            "supplied": supplied,
            "source": PERIOD_FROM_CALLER if supplied else PERIOD_DEFAULTS_TO_TODAY,
        },
        # BR-RAT-114 — reported, never collapsed. See the docstring.
        "plan_history": {
            "served": False,
            "reason": "period_not_supplied",
            "tracks": None,
            "stretches": [],
            "splits_at": [],
        },
        "plan": None,
        "plan_absent": None,
        "services": [],
        "rate_schedules": [],
        "minimum_charges": {"plan": None, "services": [], "schedules": []},
        "charge_codes": [],
        "discounts": {
            "offered": [],
            # BR-RAT-069 — the only figure that reduces a bill, and a unit
            # cannot answer it. Never `[]`, which would read as "none".
            "granted": {
                "served": False,
                "reason": "unit_has_no_account",
                "tracks": None,
            },
        },
        "taxes": {"jurisdiction_rules": [], "attachments": [], "narrowing": None},
        "penalty_rule": None,
        # ⚠ NO CONTRACT OBJECT EXISTS IN THIS PRODUCT, AND THE ROW THAT SAYS SO
        # ALREADY EXISTS — `CR-020`, captured 2026-08-20 from the PO's own words
        # (*"we will need another tab where we attach contracts required for
        # various plans … this requirement is not yet handled"*) and then HELD by
        # them on 2026-08-21, verbatim: *"hold on dont proceed"*.
        #
        # So no open question is owed here after all. This lane's first draft
        # served `tracks: null` and was going to report an OQ as owed; the row
        # was found by reading `rating.selectors`, which states the same fact one
        # module over (*"CR-020, deferred by the PO. None means THE PRODUCT HAS
        # NO CONTRACTS, which is a different statement from 0"*). Minting an OQ
        # beside a live CR would have been the duplicate-id failure OQ-197
        # records, from the other direction.
        #
        # `tracks` stays NULL because it is typed for a DEF or an OQ — an EXPIRY
        # row — and `change_request` carries the CR beside it rather than
        # smuggling a CR id into a field that means something else.
        "contract": {
            "served": False,
            "reason": "captured_and_held_by_the_product_owner",
            "tracks": None,
            "change_request": "CR-020",
        },
        # ⚠ `tracks` NAMES OQ-363, MINTED ON MERGE 2026-08-25. The lane that
        # wrote this refused to invent an id and left None, which was right —
        # an absence citing a fabricated row is worse than one citing none
        # (DEF-445). The row now exists, so the absence names it.
        #
        # TWO blockers, and only ONE of them is an engine. (a) Nothing prices a
        # plan outside a bill run: `engine.price_bill`/`price_period` are pure,
        # and every assembly feeding them is keyed on an ACCOUNT, which a
        # move-in draft does not have. (b) No signed rule says what a brand-new
        # tenant is assumed to CONSUME — typical household, the last tenant's
        # usage, or nothing at all, which are three different dollar figures on
        # the same screen. **(b) stands even if (a) were solved**, so this is a
        # question before it is a gap.
        #
        # ⚠ DO NOT "FIX" THIS BY SUMMING THE BASE CHARGES HERE. A base-only
        # month looks like arithmetic this module may do and is not: it is
        # BR-RAT-005's tax base reimplemented outside the ❄️ frozen engine.
        "worked_month": {
            "served": False,
            "reason": "no_service_prices_a_plan_outside_a_bill_run",
            "tracks": "OQ-363",
        },
    }
    plan_id: Any = unit.rate_plan_id
    if supplied and period_start is not None and period_end is not None:
        plan_id = _plan_history(payload, unit_id, period_start, period_end, as_of, plan_id)
    if plan_id is None:
        # BR-MET-100's own case: a unit with no plan is COUNTED AND FINDABLE,
        # not an error. Step 4 draws the reason and offers the picker.
        payload["plan_absent"] = {"reason": "unit_has_no_plan", "tracks": None}
        return payload
    detail_fn = _rating_read("plan_detail")
    if detail_fn is None:
        payload["plan_absent"] = {"reason": "rating_not_wired", "tracks": None}
        return payload
    try:
        # ⚠ `as_of` REACHES ONE THING — which DISCOUNT VERSION's value and
        # conditions are served (CR-034 §7). Everything else in `plan_detail` is
        # dateless plan content. Passed so the discounts on this screen are the
        # ones in force on the SAME service date as the plan and the rate
        # schedules above them, rather than as of the day the screen is open.
        plan = detail_fn(plan_id, as_of)
    except errors.NotFoundError:
        # The unit names a plan this tenant cannot read. The UNIT still exists,
        # so this is a stated absence on the panel and never a 404 on the unit.
        payload["plan_absent"] = {"reason": "plan_not_found", "tracks": None}
        return payload
    payload["plan"] = {
        "id": plan.get("id"),
        "code": plan.get("code"),
        "name": plan.get("name"),
        "description": plan.get("description"),
        "status": plan.get("status"),
        "version": plan.get("version"),
        "effective_from": plan.get("effective_from"),
        "effective_to": plan.get("effective_to"),
        # BR-RAT-027's DERIVED Σ of the plan's base charges, as RATING computes
        # and serves it. Forwarded, never recomputed here.
        "base_charges": plan.get("base_charges"),
        "minimum_bill_amount": plan.get("minimum_bill_amount"),
        "budget_billing": plan.get("budget_billing"),
        #: WHICH DATE resolved this plan, carried beside it so a reader never
        #: has to assume the answer is about today (DEF-276's reasoning: a
        #: figure has to be able to name its own inputs).
        "resolved_on": as_of.isoformat(),
    }
    # ── CR-089 wave H · `H3` (`PUJ-35`, `BR-MET-1166`) ───────────────────
    # RATING's rows, forwarded verbatim, with ONE key added beside each: what
    # AXIS prices that service. A `$0.00` base is correct for fire, trash and
    # solar and reads as broken without it. Nothing here is a figure and
    # nothing here is money — see `_service_priced_on`.
    payload["services"] = [
        {**row, "priced_on": _service_priced_on(row.get("service"))}
        for row in (plan.get("services") or [])
    ]
    payload["charge_codes"] = plan.get("charge_rules") or []
    payload["discounts"]["offered"] = _offered_discounts(plan.get("discounts") or [])
    payload["taxes"] = {
        # BR-RAT-096 jurisdiction BINDINGS and BR-RAT-113 explicit attachments
        # are different sentences and stay two lists — see rating's own note.
        "jurisdiction_rules": plan.get("tax_rules") or [],
        "attachments": plan.get("tax_attachments") or [],
        # ⚠ DEF-273 — these are the plan's, NOT R7's answer. Three of r10's five
        # Texas rates scope by customer class, which is an ACCOUNT fact.
        "narrowing": {
            "final": False,
            "reason": "narrows_by_customer_class_at_bill_time",
            "tracks": None,
        },
    }
    payload["penalty_rule"] = plan.get("penalty_rule")
    schedules = []
    for row in plan.get("rate_schedules") or []:
        card = _rate_schedule_card(row.get("tariff_id"), as_of)
        schedules.append(
            {
                "service": row.get("service"),
                "tariff_id": row.get("tariff_id"),
                "tariff_name": row.get("tariff_name"),
                "schedule": card,
                # A plan line whose schedule cannot be read is REPORTED on its
                # own row; the other services still price on screen.
                "absent": None if card is not None else {"reason": "schedule_not_readable"},
            }
        )
    payload["rate_schedules"] = schedules
    payload["minimum_charges"] = _minimum_charges(plan, schedules, unit_id)
    return payload


def _plan_history(
    payload: dict[str, Any],
    unit_id: Any,
    period_start: date,
    period_end: date,
    as_of: date,
    fallback_plan_id: Any,
) -> Any:
    """BR-RAT-114 — every plan stretch overlapping the period, and the ONE plan
    that R1 resolves on `as_of`. Fills `payload["plan_history"]` in place.

    ⚠ **THE SPLIT IS REPORTED AND NEVER COLLAPSED.** A period containing a plan
    change would be BILLED as two stretches, each on its own plan (DEF-504), so
    a screen that named one plan as *the* plan for the period would be stating
    something no bill will do. Every stretch travels; `splits_at` names the
    dates a bill would break on; and the sections resolve on `as_of`, which is
    ONE DATE and therefore has exactly one answer under R1.

    ⚠ **AN EMPTY HISTORY IS NOT "NO PLAN"** — rating's own words on
    `unit_plan_assignments_in`. A unit assigned before that table existed has no
    rows, so the fallback is the unit's current plan, exactly as
    `billing/gather.py` has always fallen back. A history that exists but whose
    stretches all end before `as_of` falls back the same way rather than
    refusing: the caller asked about a window this unit's recorded history does
    not cover, which is an absence of evidence and not evidence of absence.

    Nothing is computed here. `splits_at` is a DATE FILTER over stretch starts —
    which of them fall inside the window — and clipping is explicitly the
    caller's per rating's docstring. No money, no days, no proration.
    """
    history_fn = _rating_read("unit_plan_assignments_in")
    if history_fn is None:
        payload["plan_history"] = {
            "served": False,
            "reason": "rating_not_wired",
            "tracks": None,
            "stretches": [],
            "splits_at": [],
        }
        return fallback_plan_id
    rows = history_fn(unit_id, period_start=period_start, period_end=period_end) or []
    ref_fn = _rating_read("plan_ref")
    stretches = []
    resolved: Any = None
    for row in rows:
        assigned_from = row.get("assigned_from")
        assigned_to = row.get("assigned_to")
        ref = ref_fn(row.get("rate_plan_id")) if ref_fn else None
        stretches.append(
            {
                "rate_plan_id": row.get("rate_plan_id"),
                # None when the plan is no longer published (BR-RAT-030 —
                # `plan_ref` filters to published). The id still travels, so the
                # row is drawn rather than dropped.
                "plan_name": ref.get("name") if ref else None,
                "plan_code": ref.get("code") if ref else None,
                # BR-CUS-013's SNAPSHOT integer, as stored on the assignment —
                # not the plan's current version, which may have moved since.
                "plan_version": row.get("plan_version"),
                "assigned_from": assigned_from.isoformat() if assigned_from else None,
                "assigned_to": assigned_to.isoformat() if assigned_to else None,
                "source": row.get("source"),
            }
        )
        # The stretch that CONTAINS `as_of`. Half-open at the top exactly as
        # `unit_plan_assignments_in` stores it: `assigned_to` NULL is open.
        if assigned_from is not None and assigned_from <= as_of:
            if assigned_to is None or assigned_to >= as_of:
                resolved = row.get("rate_plan_id")
    payload["plan_history"] = {
        "served": True,
        "reason": None,
        "tracks": None,
        "stretches": stretches,
        # The dates a real bill for this period would split on (BR-RAT-114): a
        # stretch that BEGINS inside the window. A stretch that merely overlaps
        # from before it does not split anything.
        "splits_at": [
            row["assigned_from"]
            for row in stretches
            if row["assigned_from"] is not None and row["assigned_from"] > period_start.isoformat()
        ],
    }
    return resolved if resolved is not None else fallback_plan_id


def _offered_discounts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the PLAN offers (BR-RAT-110) — the grant is a different fact.

    ⚠ **`enrolled` IS DELIBERATELY DROPPED.** Rating serves it and it is
    TENANT-WIDE (its own docstring: *"`discount_enrolments.account_id` is a
    deferred FK into the CUSTOMERS module, so rating cannot ask which plan an
    account is on"*). On a UNIT screen a count is read as this unit's however it
    is captioned, so it is not forwarded at all. The absence is safer than a
    correctly-labelled misleading number, and `discounts.granted` says in words
    what cannot be answered here.

    `value_display` is rating's own string and is forwarded verbatim — never
    `value`, which stores percentage POINTS and renders `15` as `1500.00%`
    through a fraction formatter (rating's DEF-291 note).

    ⚠ **`terms` IS THE CONDITIONS HALF (CR-034 §7, PO 2026-08-26)** and it is
    forwarded WHOLE rather than unpacked here: every key is one stored column of
    the discount version in force, and a second vocabulary for them in this
    module is how two screens start disagreeing about one programme. What it
    deliberately does NOT carry, and why, is in `rating._discount_terms` — the
    short version is that a cap on THIS customer's reduction is a condition, and
    a programme's tenant-wide budget is not.
    """
    return [
        {
            "discount_id": row.get("discount_id"),
            "code": row.get("code"),
            "name": row.get("name"),
            "status": row.get("status"),
            "type": row.get("type"),
            "value_display": row.get("value_display"),
            "eligibility": row.get("eligibility"),
            # ── CR-034 §7 (PO 2026-08-26) · WHAT MUST BE SATISFIED TO GET IT ─
            # *"We should show all discount plan offer and what condition are
            # required to avail that discount ; when account is attached it will
            # avail those discounts"*. Rating's own `terms` object, forwarded
            # WHOLE and unread: the caps, the floor, the scope, the proof, the
            # recertification and the stacking are all stored columns, and this
            # module neither compares them, sums them nor decides which binds.
            #
            # ⚠ IT CONTAINS NO PROGRAMME-WIDE FIGURE. `budget_cap` is omitted at
            # source for the same reason `enrolled` is dropped below — a
            # tenant-wide number on a unit screen is read as this unit's.
            "terms": row.get("terms"),
            # ⚠ WHEN THIS PLAN OFFERS IT — null means "for as long as the
            # discount itself is available". It is NOT the discount's own
            # effective window and must never be printed as one (rating's note).
            "available_from": row.get("available_from"),
            "available_to": row.get("available_to"),
        }
        for row in rows
    ]


def _minimum_charges(
    plan: dict[str, Any], schedules: list[dict[str, Any]], unit_id: Any
) -> dict[str, Any]:
    """The three places a FLOOR is stored, gathered into one section.

    🔒 **AN ASSEMBLY, NOT ARITHMETIC.** Every string here was already in this
    payload, served by rating; this puts them under one heading because the PO
    asked to see the minimum charges for a unit and they were scattered across
    three sections of the same screen. **Nothing is summed, nothing is compared,
    and no "effective minimum" is derived** — which of these floors wins is
    BR-RAT-016/028, it is PROPOSED on GT-13 rather than frozen, and deriving it
    here would be billing math in a second place where no golden test can see
    it. The screen shows three labelled figures and says they are three.

    A null is a real answer and stays null: r10's electric matrix draws an
    em-dash in the minimum column for every size, and `0.00` is a different
    fact (DEF-277, one column across).
    """
    return {
        "plan": {
            "amount": plan.get("minimum_bill_amount"),
            "source": "plan",
        },
        "services": [
            {
                "service": row.get("service"),
                "name": row.get("name"),
                # ⚠ **READ THROUGH FROM THE RATE SCHEDULE SINCE 2026-09-10** —
                # PO ruling, *"set it in rates and use it in plans"*. The plan's
                # own `minimum_amount` column is gone (`rating/0030`+`0031`) and
                # `plan_detail` now serves `schedule_minimum_amount`, resolved
                # from the version in force. The KEY here is unchanged because
                # it is this screen's own contract; the `source` is not, because
                # it was the one thing on the row that claimed where the figure
                # came from and that claim is now false.
                #
                # ⚠ **AND THIS ROW AND THE `schedules` ROW BELOW NOW STATE THE
                # SAME FIGURE FROM THE SAME PLACE** — two of the three labelled
                # sources this docstring promises have become one. Filed as a
                # defect rather than deleted in passing: which of the two the
                # screen keeps is a layout decision, and this is a money read.
                "minimum_amount": row.get("schedule_minimum_amount"),
                "currency": row.get("currency"),
                "source": "rate_schedule",
            }
            for row in (plan.get("services") or [])
        ],
        # ⚠ **`DEF-MET-8823` · THE SIZE'S MINIMUM, NOT THE VERSION'S.** PO
        # 2026-10-01, option A: *"A · Minimum per size - this is correct"*.
        # `rating/0053` moved the floor onto `rate_size_rows` and billing reads
        # it there for the connection's size (`rating.selectors.pricing_inputs`
        # → `minimum_bill`). This row read `current_version.minimum_bill` until
        # then — a figure no bill charges. See `_size_floor`.
        "schedules": [
            _size_floor(row, unit_id) for row in schedules if row.get("schedule") is not None
        ],
    }


#: `minimum_charges.schedules[].minimum_state` — why the Minimum cell reads what
#: it reads. Values, not sentences: the screen owns the words.
MINIMUM_FROM_SIZE = "size_minimum"
MINIMUM_SIZE_HAS_NONE = "size_has_no_minimum"
MINIMUM_NO_SIZE_RECORDED = "no_size_recorded"


def _size_floor(row: dict[str, Any], unit_id: Any) -> dict[str, Any]:
    """One schedule's floor FOR THIS UNIT: the minimum its in-force version's
    size row states for the size this unit's connection has (`DEF-MET-8823`).

    Worked, Water Residential — 5/8" `$15.00`, 1" `$25.00`, 2" `$40.00`: a unit
    on one 1" connection shows **$25.00**, the figure billing tops it up to.

    The outcomes are billing's own (`rating.selectors._size_minimum`):

        a row for the size, amount stated   -> that amount
        a row with no amount, or no row     -> None, "No minimum"
        no recorded size                    -> None (PO 2026-10-01: a meter
                                               with no recorded size gets no
                                               minimum)

    ⚠ **NO SECOND VERSION LOOKUP, AND NO SECOND SIZE ANSWER.** The version is
    the one `_rate_schedule_card` already resolved on the service date, and its
    `size_rows` are already on that card — so G142's question is untouched. The
    size is `connection_size_for`, the seam `billing.gather` reads, so two
    meters that disagree read as *no size* here exactly as they do on a bill.
    Nothing is computed: the strings are rating's, forwarded.
    """
    version = row["schedule"]["current_version"] or {}
    service = row.get("service")
    size = connection_size_for(unit_id, str(service)) if service else None
    size_rows = version.get("size_rows") or []
    match = next((sr for sr in size_rows if size and sr.get("size_class") == size), None) or {}
    minimum = match.get("minimum_bill")
    if size is None:
        state = MINIMUM_NO_SIZE_RECORDED
    elif minimum is None:
        state = MINIMUM_SIZE_HAS_NONE
    else:
        state = MINIMUM_FROM_SIZE
    return {
        "service": service,
        "tariff_id": row.get("tariff_id"),
        "tariff_name": row.get("tariff_name"),
        "version_id": version.get("id"),
        "minimum_bill": minimum,
        "minimum_bill_display": match.get("minimum_bill_display") if minimum is not None else None,
        "currency": match.get("currency") or version.get("currency"),
        # B14 rule 31 — the size's NAME for the screen, never its code.
        "size_label": service_size_class_labels(str(service)).get(size, size) if size else None,
        "minimum_state": state,
        # DEF-360's per-size floors, forwarded as rating serves them.
        "size_rows": size_rows,
        "source": "rate_size_row",
    }


# ── S64 · Read validation & estimation rules (CR-038 A1) ────────────────────

_S64_FIGURE_FIELDS = (
    "high_pct",
    "high_abs_value",
    "high_abs_unit",
    "low_pct",
    "zero_scope",
    "days_flag_min",
    "days_flag_max",
    "days_hard_min",
    "days_hard_max",
    "mismatch_pct",
    "tou_sum_tolerance_pct",
)


def _s64_str(value: Any) -> Any:
    """Decimals as canonical 6dp STRINGS end to end (CLAUDE.md rule 2 — the
    client never parses one into a number; the STORED scale rides the wire on
    every vendor and every write path, and 2dp is the SCREEN's display job)."""
    from decimal import Decimal

    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.000001")))
    return value


def _rule_switch_map(row: Any) -> dict[str, bool]:
    """The BR-MET-136 ENABLED map, EXPANDED to every judgment rule.

    The column stores only the CHOICES a tenant made (absent = enabled — see
    `models.ReadValidationServiceSettings.rule_enabled`). The wire states all
    of them explicitly, so S64 never has to know the convention and cannot draw
    "off" for a rule that is simply unmentioned. `row is None` — a service with
    no row at all — is ALL ENABLED, which is clause 2 made visible: an
    unconfigured service still runs every check it has figures for.
    """
    from apps.metering import validation

    stored = getattr(row, validation.SWITCH_FIELD, None) or {} if row is not None else {}
    return {rule: bool(stored.get(rule, True)) for rule in validation.JUDGMENT_RULES}


def read_validation_service_dict(row: models.ReadValidationServiceSettings) -> dict[str, Any]:
    """One per-service settings row, decimals as canonical strings."""
    return {
        "service": row.service.code,
        "source": "service",
        "rule_enabled": _rule_switch_map(row),
        **{f: _s64_str(getattr(row, f)) for f in _S64_FIGURE_FIELDS},
    }


def _legacy_figures(general: Any, service_code: str) -> dict[str, Any] | None:
    """The legacy tenant-wide row RESTATED in the per-service shape — what an
    UNCONFIGURED electric/water panel honestly runs on (the engine's
    `LEGACY_FALLBACK_SERVICES` fallback). The floor column is the service's
    own (high_abs_kwh → kWh, high_abs_kgal → kgal), which is exactly how
    `validation._FLOOR_COLUMN_BY_UNIT` reads it."""
    if general is None:
        return None
    floor_by_service = {"electric": ("high_abs_kwh", "kWh"), "water": ("high_abs_kgal", "kgal")}
    column, unit = floor_by_service[service_code]
    return {
        "high_pct": _s64_str(general.high_pct),
        "high_abs_value": _s64_str(getattr(general, column)),
        "high_abs_unit": unit,
        "low_pct": _s64_str(general.low_pct),
        "zero_scope": general.zero_scope,
        "days_flag_min": general.days_flag_min,
        "days_flag_max": general.days_flag_max,
        "days_hard_min": general.days_hard_min,
        "days_hard_max": general.days_hard_max,
        "mismatch_pct": _s64_str(general.mismatch_default_pct),
        "tou_sum_tolerance_pct": _s64_str(general.tou_sum_tolerance_pct),
    }


def read_validation_overview() -> dict[str, Any]:
    """`GET /settings/read-validation` — the WHOLE S64 picture (CR-038 A1):
    the tenant-wide estimation panel, one entry per ENABLED service in catalog
    order with the figures that actually judge its reads and WHERE they come
    from, and the locked integrity vocabulary — served from the engine's own
    tuple so the screen and the engine cannot disagree about what is beyond
    editing.

    `source` per service is the fail-safe made visible:
      · "service"          — a (tenant, service) row exists; its figures rule;
      · "tenant_fallback"  — electric/water with no row yet: the legacy
                             tenant-wide figures rule (existing behavior);
      · "none"             — no figure anywhere: threshold rules are SKIPPED
                             AND REPORTED for this service (BR-MET-020 /
                             US-MET-011 TC-9), and the screen says so instead
                             of drawing an inviting blank as if it were zero.
    """
    from apps.metering import seams, validation

    general = models.ReadValidationSettings.objects.filter(tenant_id=_tenant_id()).first()
    rows = {
        row.service.code: row
        for row in models.ReadValidationServiceSettings.objects.filter(
            tenant_id=_tenant_id()
        ).select_related("service")
    }
    services: list[dict[str, Any]] = []
    for code in seams.enabled_service_codes_ordered():
        row = rows.get(code)
        if row is not None:
            entry = read_validation_service_dict(row)
        elif code in validation.LEGACY_FALLBACK_SERVICES:
            figures = _legacy_figures(general, code)
            # BR-MET-136 clause 2: no per-service row means no switch was ever
            # set, which means EVERY rule runs — stated, never left implicit.
            entry = (
                {
                    "service": code,
                    "source": "tenant_fallback",
                    "rule_enabled": _rule_switch_map(None),
                    **figures,
                }
                if figures is not None
                else {"service": code, "source": "none", "rule_enabled": _rule_switch_map(None)}
            )
        else:
            entry = {"service": code, "source": "none", "rule_enabled": _rule_switch_map(None)}
        if entry["source"] == "none":
            # The unit the service's floor would be expressed in, for the
            # create form's prefill — the tenant's OWN configured billed UoM,
            # never an invented one; None renders as "enter the unit".
            entry["unit_hint"] = seams.service_billed_uom(code)[0]
        services.append(entry)
    return {
        "general": {
            "present": general is not None,
            "est_method": general.est_method if general else None,
            "est_max_consecutive": general.est_max_consecutive if general else None,
        },
        "services": services,
        "integrity_rules": list(validation.INTEGRITY_RULES),
        # BR-MET-136 clause 1: the SWITCHABLE vocabulary, served from the
        # engine's own tuple for the same reason `integrity_rules` is — a
        # screen that hard-coded either list would disagree with the engine the
        # first time a rule is added, and disagree silently.
        "judgment_rules": list(validation.JUDGMENT_RULES),
        "legacy_fallback_services": list(validation.LEGACY_FALLBACK_SERVICES),
    }


# ── CR-075 wave Q′ · the two reads runbook 20 makes (US-RBS-032) ───────────
#
# ⚠ **THEY LIVE HERE BECAUSE THE MODULE THAT OWNS THE TABLE PUBLISHES THE
# READ.** `apps/runbooks/seams/metering_seam.py` may only resolve
# `apps.metering.selectors.<name>` or `apps.metering.services.<name>` — `G20`'s
# R1 is exactly the *wrong kind* defect (`DEF-035`), where a seam pointed at
# `services` for something that lived in `selectors` and got `None` for ever,
# and read `None` as *no findings*. `import_runs.py` is a THIRD kind that no
# resolver looks in (the `13-selector-inventory.md` W-1 shape), so the staged
# batch is re-exported from here rather than reached for across the seam.


def gis_reconciliation_set(*, include_sample: bool = False) -> dict[str, Any]:
    """Our whole register in TWO queries, for one City snapshot to be matched against.

    ── 2026-09-17 · `BR-INT-073` ───────────────────────────────────────────────
    PO ruling 4 of that day, verbatim: *"please ensure you dont call ArcGis Apis
    for every Premsies or unit again and again - they might return you all the
    gis ids from there tbale in 1 go - these can be uptp 70,000 … and against
    thse format match in loop with our premsies and units"*. **So the City is
    read once and OUR side is read once**, and the matching is arithmetic over
    two lists in memory. Two queries for 40,000 premises and their units, never
    two queries per premises.

    ⚠ **A SEPARATE SELECTOR FROM `premises_reconciliation_set` BELOW, AND
    DELIBERATELY SO.** That one is `RB-120`'s and carries the six fields its
    disposition table names plus `external_ref` as a match key. This one carries
    the **GIS** columns — which are different columns for a different fact
    (`BR-MET-1173`) — and it carries UNITS, which that one has never needed.
    Widening the existing selector would have changed the shape the runbook
    reads on a wave that was not about the runbook.

    `is_sample` travels rather than being filtered away by default, for
    `premises_reconciliation_set`'s own reason: a guard applied inside a read
    cannot be SEEN on the screen that draws it (`BR-RBS-012`).
    """
    tenant_id = _tenant_id()
    rows = models.Premises.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True)
    if not include_sample:
        rows = rows.filter(is_sample=False)
    premises = [
        {
            "id": str(row.id),
            "premise_no": row.premise_no,
            "label": row.premise_no or row.address_line,
            "address_line": row.address_line,
            "city": row.city,
            "state": row.state,
            "postal_code": row.postal_code,
            "lat": row.lat,
            "lng": row.lng,
            "gis_parcel_id": row.gis_parcel_id,
            "gis_parcel_id_was": row.gis_parcel_id_was,
            "gis_status": row.gis_status,
            "gis_verified": row.gis_verified,
            "is_sample": row.is_sample,
        }
        for row in rows.only(
            "id", "premise_no", "address_line", "city", "state", "postal_code",
            "lat", "lng", "gis_parcel_id", "gis_parcel_id_was", "gis_status",
            "gis_verified", "is_sample",
        )
    ]
    keep = {one["id"] for one in premises}
    units: dict[str, list[dict[str, Any]]] = {}
    unit_rows = models.Unit.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).only(
        "id", "premises_id", "label", "lat", "lng", "gis_point_id", "gis_point_id_was",
        "gis_status", "gis_verified",
    )
    for row in unit_rows:
        premises_id = str(row.premises_id)
        if premises_id not in keep:
            continue
        units.setdefault(premises_id, []).append(
            {
                "id": str(row.id),
                "label": row.label,
                "lat": row.lat,
                "lng": row.lng,
                "gis_point_id": row.gis_point_id,
                "gis_point_id_was": row.gis_point_id_was,
                "gis_status": row.gis_status,
                "gis_verified": row.gis_verified,
            }
        )
    return {"premises": premises, "units_by_premises": units}


def premises_reconciliation_set(*, include_sample: bool = False) -> list[dict[str, Any]]:
    """Every premises with the fields an outside parcel feed can disagree about.

    ONE query for the whole estate. `RB-120` compares a landed parcel batch
    against *"premises with a parcel id"*, and the comparison needs the six
    columns the card's disposition table names plus the two keys it matches on.

    ⚠ **THE ADDRESS COMES FROM HERE AND FROM NOWHERE ELSE** (CLAUDE.md hard
    rule 8, `BR-MET-1161`). `premises` is the product's one address home, so a
    reconciliation that corrects an address here corrects the account, the
    route, the cycle, the invoice, the work order and the map pin at once —
    which is also why a bulk change through it is capped and planned first.

    ⚠ **`is_sample` TRAVELS RATHER THAN BEING FILTERED AWAY BY DEFAULT.**
    `RB-120`'s scope says *Never include: Sample*, and a guard that is applied
    inside a read cannot be SEEN on the screen that draws it (`BR-RBS-012`,
    `RBS-004.4` — a guard is drawn disabled with its reason, never hidden). So
    the flag crosses and the runbook's own guard decides.
    """
    rows = models.Premises.objects.filter(tenant_id=_tenant_id()).select_related("premises_type")
    if not include_sample:
        rows = rows.filter(is_sample=False)
    return [
        {
            "premises_id": str(row.id),
            "label": row.premise_no or row.address_line,
            "premise_no": row.premise_no,
            "external_ref": row.external_ref,
            "address_line": row.address_line,
            "city": row.city,
            "state": row.state,
            "postal_code": row.postal_code,
            "owner_manager": row.owner_manager,
            # ⚠ **THE CODE IS WHAT COMPARES AND THE NAME IS WHAT A CLERK
            # READS, AND BOTH TRAVEL.** An import maps a file's *"Single-family"*
            # onto this tenant's own type CODE, so a comparison against the
            # display name would report a difference on every row of a file the
            # importer had understood perfectly.
            "premises_type": (row.premises_type.code if row.premises_type_id else None),
            "premises_type_label": (
                row.premises_type.name if row.premises_type_id else None
            ),
            "inside_city_limits": row.inside_city_limits,
            "lat": None if row.lat is None else str(row.lat),
            "lng": None if row.lng is None else str(row.lng),
            "gis_unchecked": bool(row.gis_unchecked),
            "is_sample": bool(row.is_sample),
        }
        for row in rows.order_by("premise_no", "address_line")
    ]


def staged_import_batch(target: str, run_id: Any = None) -> dict[str, Any] | None:
    """A file somebody uploaded for `target` that is STAGED and not yet loaded.

    The run's own rows, `raw` as extracted and `mapped` after transform, with
    NOTHING written: `ImportRun` at status `validated` (or `transformed`) is a
    file that has been read and judged and not committed, which is exactly what
    *a landed batch* means to a runbook that plans before it acts.

    ⚠ **`loaded` AND `rolled_back` ARE REFUSED BY THE FILTER, NOT BY THE
    CALLER.** A run that has already been loaded is not a batch waiting to be
    reconciled — its rows are premises now — and offering one would let a
    runbook plan changes against a file the importer already applied.

    Returns `None` when there is none, which is a real state and the sentence a
    runbook stops on; it is never an empty batch, because *"nothing has landed"*
    and *"a batch of nothing landed"* are different things to say to a clerk.
    """
    runs = models.ImportRun.objects.filter(
        tenant_id=_tenant_id(), target=str(target), status__in=("transformed", "validated")
    )
    if run_id is not None:
        runs = runs.filter(pk=run_id)
    run = runs.order_by("-created_at").first()
    if run is None:
        return None
    rows = models.ImportRunRow.objects.filter(tenant_id=run.tenant_id, run=run).order_by("row_no")
    return {
        "run_id": str(run.id),
        "target": run.target,
        "status": run.status,
        "file_name": run.file_name,
        "batch_label": run.batch_label,
        "is_sample": bool(run.is_sample),
        "rows": [
            {
                "row_no": row.row_no,
                "source_key": row.source_key,
                "raw": dict(row.raw or {}),
                "mapped": dict(row.mapped or {}),
                "outcome": row.outcome,
                "is_sample": bool(row.is_sample),
            }
            for row in rows
        ],
    }


# ── CR-075 wave S · the estate-wide reads runbooks 5, 18 and 19 make ──────
#
# `13-selector-inventory.md` rows **S-2**, **S-3**, **S-6**, **S-7** and **S-8**,
# and its own warning about them: *"S-1 through S-5 are one body of work, not
# five. Every one of them is this meter's own history, summarised. A module that
# adds them one at a time will write the same window query five times."* So
# there are TWO functions here and not five — one walk of the estate's chain and
# one walk of its reads — and the SUMMARIES (a median, a spike, three zeros in a
# row) are the runbook's, because they are judgments and this module owns rows.


def meter_lifecycle_census(*, include_sample: bool = True) -> dict[str, Any]:
    """EVERY meter with its age, its last test, and the unit it stands on.

    Added for `CR-075` runbook 28, *Meters past change-out age or never tested*.
    Assets holds the dates; metering holds the service point and therefore the
    unit, and a runbook may not ask assets directly — `metering` owns assets
    (B2 r4) and every runbook read of one comes through here.

    ⚠ **THREE QUERIES FOR THE WHOLE FLEET, NOT ONE PER METER.** `NFR-3` and
    `NFR-5` bind every list this product adds and the ICP's top is 40,000
    accounts; `asset_ids_for_service_point` answers one point at a time, which
    is the cost `premises_meter_census` already states and does not need to be
    paid twice.

    ⚠ **`meters_answered: False` MEANS ASSETS ANSWERED NOTHING, WHICH IS NOT
    *this utility owns no meters*.** `DEF-075`'s exact shape — `None` read as
    *"this module has nothing"* when it meant *"this module cannot answer"* —
    and the caller must be able to tell a clean fleet from an unreachable one.

    ⚠ **`is_sample` TRAVELS AND NOTHING IS FILTERED AWAY BY DEFAULT** when
    `include_sample` is left alone: a guard applied inside a read cannot be seen
    on the screen that draws it (`BR-RBS-012`), so the flag crosses and the
    runbook's guard decides.
    """
    fn = seams.resolve("assets", "meter_lifecycle_census", kind="selectors")
    meters = list(fn() if fn is not None else [])
    answered = fn is not None
    if not include_sample:
        meters = [one for one in meters if not one.get("is_sample")]

    point_ids = [one["service_point_id"] for one in meters if one.get("service_point_id")]
    unit_by_point: dict[str, str] = {}
    if point_ids:
        unit_by_point = {
            str(point_id): str(unit_id)
            for point_id, unit_id in models.ServicePoint.objects.filter(
                tenant_id=_tenant_id(), pk__in=point_ids, deleted_at__isnull=True
            ).values_list("id", "unit_id")
        }
    codes = service_codes_for_points(point_ids) if point_ids else {}

    for one in meters:
        point = one.get("service_point_id")
        one["unit_id"] = unit_by_point.get(str(point)) if point else None
        one["service_code"] = codes.get(str(point)) if point else None
    return {"meters": meters, "meters_answered": answered}


def premises_meter_census(*, include_sample: bool = True) -> dict[str, Any]:
    """THE CHAIN, ONE WALK: premises → units → service points → meters.

    `RB-119` steps 2, 3 and 4 (*premises with no meter · meters with no premise
    · accounts with no unit*) and `RB-118` step 1 (*vacant premises with a
    meter*) are the same walk asked four ways, and asking it four times would be
    four chances to disagree about which units are in scope — the reason
    `service_point_graph` is one function in the runbooks seam.

    ⚠ **FOUR QUERIES FOR THE WHOLE ESTATE, NOT ONE PER PREMISES.** `NFR-3` and
    `NFR-5` bind every list this product adds and the ICP's top is 40,000
    accounts; a per-premises walk is correct at 3,000 and 13× short at 40,000
    (`DEF-PAY-4221`'s shape). The meters arrive from `assets.meter_census`,
    which is one query of its own.

    ⚠ **AN EMPTY `by_service_point` MEANS *assets ANSWERED NOTHING*, WHICH IS
    NOT *this utility owns no meters*.** The two are told apart by
    `meters_answered`, which is `False` when the seam resolves nothing at all —
    hard-won law 1, and `DEF-075`'s exact shape: `None` read as *"this module
    has nothing"* when it meant *"this module cannot answer"*.

    ⚠ **`is_sample` TRAVELS AND NOTHING IS FILTERED AWAY BY DEFAULT** — a guard
    applied inside a read cannot be seen on the screen that draws it
    (`BR-RBS-012`), so the flag crosses and the runbook's guard decides.
    """
    premises_rows = models.Premises.objects.filter(tenant_id=_tenant_id())
    if not include_sample:
        premises_rows = premises_rows.filter(is_sample=False)
    premises_rows = list(premises_rows.order_by("premise_no", "address_line"))
    premises_ids = [row.id for row in premises_rows]

    units = list(
        models.Unit.objects.filter(
            tenant_id=_tenant_id(), premises_id__in=premises_ids
        ).order_by("unit_no", "id")
    )
    points = list(
        models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(),
            unit_id__in=[unit.id for unit in units],
            deleted_at__isnull=True,
        ).select_related("service")
    )
    fn = seams.resolve("assets", "meter_census", kind="selectors")
    census = fn() if fn is not None else None
    by_point = dict((census or {}).get("by_service_point") or {})
    orphans = list((census or {}).get("without_a_service_point") or [])

    points_by_unit: dict[str, list[Any]] = {}
    for point in points:
        points_by_unit.setdefault(str(point.unit_id), []).append(point)
    units_by_premises: dict[str, list[Any]] = {}
    for unit in units:
        units_by_premises.setdefault(str(unit.premises_id), []).append(unit)

    out: list[dict[str, Any]] = []
    for row in premises_rows:
        held = units_by_premises.get(str(row.id)) or []
        point_rows = [one for unit in held for one in points_by_unit.get(str(unit.id), [])]
        meters = [
            meter
            for point in point_rows
            for meter in by_point.get(str(point.id), [])
            # `behind_the_meter` is a solar inverter or a battery, not a meter
            # this utility reads for billing (BR-AST-004's three tabs).
            if meter.get("category") in ("meters", "sub_meters")
        ]
        out.append(
            {
                "premises_id": str(row.id),
                # B14 rule 31 — the premises NUMBER or its address, never the id.
                "label": row.premise_no or row.address_line,
                "address_line": row.address_line,
                "city": row.city,
                "state": row.state,
                "postal_code": row.postal_code,
                "is_sample": bool(row.is_sample),
                "unit_ids": [str(unit.id) for unit in held],
                "unit_labels": {str(unit.id): (unit.unit_no or unit.label) for unit in held},
                "service_points": [
                    {
                        "id": str(point.id),
                        "unit_id": str(point.unit_id),
                        "service": point.service.code if point.service_id else None,
                    }
                    for point in point_rows
                ],
                "meters": meters,
            }
        )
    return {
        "premises": out,
        "meters_answered": census is not None,
        "meters_without_a_service_point": [
            one for one in orphans if one.get("category") in ("meters", "sub_meters")
        ],
    }


def meter_read_history(
    *,
    asset_ids: Any = None,
    unit_ids: Any = None,
    service_code: str | None = None,
    since: Any = None,
    limit_per_meter: int = 60,
) -> list[dict[str, Any]]:
    """EACH METER'S OWN HISTORY — committed heads, oldest first, with its unit.

    `13-selector-inventory.md` **S-2**, **S-3** and **S-7** in one read:
    `RB-105` needs twelve periods per meter with the estimates marked (steps
    1–7) and `RB-118` needs three consecutive zeros on an active account's meter
    (step 3). Both are *this meter's own history*, which is why one selector
    serves them and neither gets a fleet average — `RBR-09`: **every threshold
    is relative to the meter's own history, never to a fleet average**, and a
    selector that returned a fleet median would make breaking that rule the easy
    path.

    ⚠ **NO SUMMARY IS COMPUTED HERE, DELIBERATELY.** A median, a spike
    threshold and *four identical reads* are `RB-105`'s judgments; this module
    owns the rows. A `median` field here would be a rule living where the
    runbook's reviewers never read it.

    ⚠ **COMMITTED LINEAGE HEADS ONLY** (`BR-MET-016`/`053`) — a superseded read
    is history of the correction, not of the meter, and counting one would
    report a spike that a clerk already fixed.

    ⚠ **CONSUMPTION CARRIES ITS UNIT AND NEVER TRAVELS WITHOUT ONE** (hard rule
    3). A head with `consumption` NULL is an estimate or an unmeasured row and
    is KEPT with `consumption: None` — dropping it would silently shorten a
    meter's year and turn *"four identical reads"* into *"three"*.
    """
    heads = _read_heads().select_related("asset")
    if asset_ids is not None:
        heads = heads.filter(asset_id__in=[one for one in asset_ids if one])
    if unit_ids is not None:
        # ⚠ NARROWED IN SQL AND NEVER IN PYTHON. `RB-104` asks about ONE
        # account's meter, and pulling every head this tenant holds to keep a
        # handful is `NFR-3`'s shape — correct at 3,000 accounts and 13× short
        # at 40,000 (`DEF-PAY-4221`).
        heads = heads.filter(
            asset__service_point__unit_id__in=[one for one in unit_ids if one]
        )
    if since is not None:
        heads = heads.filter(read_at__gte=_day_start(since))
    rows = list(heads.order_by("asset_id", "read_at", "id"))

    # The chain a read hangs off, one query rather than one per read: the
    # asset's service point names the service and the unit, and the unit names
    # the premises — the address home (hard rule 8).
    point_ids = {row.asset.service_point_id for row in rows if row.asset.service_point_id}
    points = {
        str(point.id): point
        for point in models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(), id__in=point_ids
        ).select_related("service", "unit")
    }

    by_asset: dict[str, dict[str, Any]] = {}
    for row in rows:
        point = points.get(str(row.asset.service_point_id)) if row.asset.service_point_id else None
        code = point.service.code if point is not None and point.service_id else None
        if service_code and code != service_code:
            continue
        key = str(row.asset_id)
        entry = by_asset.setdefault(
            key,
            {
                "asset_id": key,
                "asset_no": row.asset.asset_no,
                "service": code,
                "unit_id": str(point.unit_id) if point is not None else None,
                "premises_id": (
                    str(point.unit.premises_id) if point is not None and point.unit_id else None
                ),
                "is_sample": bool(getattr(row.asset, "is_sample", False)),
                "reads": [],
            },
        )
        if len(entry["reads"]) >= limit_per_meter:
            continue
        entry["reads"].append(
            {
                "read_id": str(row.id),
                "on": row.read_at.date().isoformat() if row.read_at else None,
                "channel": row.channel,
                "consumption": (None if row.consumption is None else str(row.consumption)),
                "current_value": (
                    None if row.current_value is None else str(row.current_value)
                ),
                # ⚠ **THE FACTOR THAT WAS USED, NOT THE ONE IN FORCE TODAY**
                # (`BR-MET-056`). `RB-104` step 6 asks whether the multiplier
                # CHANGED between two bills, and only the figure stored on each
                # read can answer that — the meter's current multiplier answers
                # a different question and would report *unchanged* on every
                # bill ever raised under an old one.
                "multiplier": (None if row.multiplier is None else str(row.multiplier)),
                "unit": row.unit,
                "estimated": read_is_estimated(row.status, row.disposition),
                "account_id": str(row.account_id) if row.account_id else None,
                "is_sample": bool(row.is_sample),
            }
        )
    return sorted(by_asset.values(), key=lambda one: (one["asset_no"] or "", one["asset_id"]))

# ════════════════════════════════════════════════════════════════════════════
# CR-075 WAVE R′ — THE READS RUNBOOKS 11 AND 21 MAKE
#
# `13-selector-inventory.md` rows **S-1** (a meter's own 90-day average),
# **S-4** (a meter's last good day) and **S-5** (interval gaps inside a day, and
# meters silent all day), plus the interval batch those two runbooks start from.
#
# ⚠ **EVERY QUANTITY BELOW CROSSES WITH ITS EXPLICIT UNIT, AND NONE IS EVER
# INFERRED** (CLAUDE.md hard rule 3, `BR-MET-143`). This is the one place in the
# module where 176,640 numbers are added together, so it is the place the rule
# most matters: the unit travels on the ROLLED-UP row, and a meter-day whose own
# intervals disagree about their unit is REPORTED with `unit_conflict` and its
# total refused, never summed into a number nobody can check.
#
# ⚠ **THE UNIT OF WORK IS THE METER-DAY AND THE ROLLUP HAPPENS HERE**
# (`BR-RBS-019`, `RBR-18`). A runbook that walked the interval would open
# 176,640 savepoints; these return one row per meter-day and the runbook never
# sees an interval. Doing it on the far side of the seam would mean 176,640 rows
# crossing so that 1,840 could be kept.
# ════════════════════════════════════════════════════════════════════════════

#: The AMI transport. `SOURCE_KINDS` holds three words and this is the one that
#: means *a head-end sent us intervals*; `csv` is a person with a file and
#: `manual` is a person with a clipboard, and neither is an interval batch.
INTERVAL_SOURCE_KIND = "ami_replay"

#: A batch that has LANDED and is not yet reads. `posted` rows are `meter_reads`
#: already and `discarded` ones were thrown away — offering either would let a
#: runbook validate a file the importer has already applied, which is the same
#: refusal `staged_import_batch` makes for the generic importer above.
INTERVAL_BATCH_STATUSES = ("staged", "validated")


def _interval_unit(asset: Any, channel: str) -> str | None:
    """The unit this register's readings are in — EXPLICIT, never inferred.

    ⚠ **`None` IS NOT A UNIT AND IS NEVER READ AS ONE.** A meter with no UoM on
    file is one nobody can bill and nobody can compare; it travels as `None`,
    the runbook counts it, and no arithmetic is done on its rows. The
    alternative — defaulting to the service's usual unit — is precisely the
    assumption hard rule 3 forbids, and it is how a gas meter reading in CCF
    ends up added to one reading in therms.
    """
    stored = getattr(asset, "unit", None) if asset is not None else None
    if not stored:
        return None
    try:
        return register_units.register_unit(stored, channel or models.CHANNEL_TOTAL)
    except Exception:  # pragma: no cover — a channel the unit table cannot map
        return stored


def _day_of(stamp: datetime) -> date:
    """The tenant-local calendar day a timestamp falls on.

    A meter-day is a DAY, so the boundary is the tenant's midnight and not
    UTC's. Reading it as UTC would put a 19:00 interval in the wrong day for
    every utility west of Greenwich, which is all of them.
    """
    return timezone.localtime(stamp).date() if timezone.is_aware(stamp) else stamp.date()


def interval_batch(batch_id: Any = None) -> dict[str, Any] | None:
    """The interval batch that landed, ROLLED UP TO THE METER-DAY. One query.

    *"96 intervals become one meter-day; the run is 1,840 records, not
    176,640"* — `RB-121` step 1, and `BR-RBS-019` in one sentence.

    Returns `None` when no interval batch is waiting. That is a real state and
    the sentence a runbook stops on — never an empty batch, because *"nothing
    has landed"* and *"a batch of nothing landed"* are different things to say
    to a clerk.

    Each meter-day carries:

    * `intervals` — how many rows rolled into it, so a short day is VISIBLE
      rather than inferred, which is what `RB-121` step 3 reads gaps from;
    * `first_at` / `last_at` — the window the readings actually cover;
    * `quantity` **with `unit`** — the day's total in the register's own unit
      (hard rule 3). `unit` is `None` when the meter states none and
      `unit_conflict` is True when one meter-day's rows disagree; both are
      reported and neither is guessed;
    * `zero_intervals` / `nonzero_intervals` — what *continuous flow* is read
      from, counted once here rather than by a second pass;
    * `is_sample` — from the ASSET's own flag (`BR-TEN-057`: the tag lives on
      the owning row). ⚠ It TRAVELS rather than being filtered away, because a
      guard applied inside a read cannot be seen on the screen that draws it
      (`BR-RBS-012`) and a guard nobody can see is a check that never fires.
    """
    tenant_id = _tenant_id()
    batches = models.ReadImportBatch.objects.filter(
        tenant_id=tenant_id,
        source_kind=INTERVAL_SOURCE_KIND,
        status__in=INTERVAL_BATCH_STATUSES,
    )
    if batch_id is not None:
        batches = batches.filter(pk=batch_id)
    batch = batches.order_by("-created_at").first()
    if batch is None:
        return None

    # ⚠ **THE WALK TO THE PREMISES IS DONE HERE, IN ONE JOIN, BECAUSE THE
    # PREMISES IS THE PRODUCT'S ONE ADDRESS HOME** (CLAUDE.md hard rule 8,
    # `BR-MET-1161`). A meter has no address column and neither does a service
    # point, a unit or an account; the leak alert's text names an address, so
    # the id it walks to travels here rather than being fetched per meter on the
    # far side of the seam — which at 1,840 meters is 1,840 round trips.
    rows = (
        models.ReadImportRow.objects.filter(tenant_id=tenant_id, batch=batch)
        .select_related("asset__service_point__unit")
        .order_by("row_no")
    )

    days: dict[tuple[str, str, str], dict[str, Any]] = {}
    intervals = 0
    unreadable = 0
    for row in rows:
        intervals += 1
        if row.asset_id is None or row.read_at is None:
            # A row whose meter or whose timestamp would not parse is not a
            # meter-day at all — it is an import error the importer already
            # owns. It is COUNTED so the two figures on the screen reconcile
            # (176,640 in, 1,840 out, N unusable) and never silently dropped:
            # a difference with no number beside it is indistinguishable from
            # no difference at all.
            unreadable += 1
            continue
        asset = row.asset
        channel = row.channel or models.CHANNEL_TOTAL
        day = _day_of(row.read_at)
        key = (str(row.asset_id), channel, day.isoformat())
        unit = _interval_unit(asset, channel)
        point = getattr(asset, "service_point", None) if asset is not None else None
        connection = getattr(point, "unit", None) if point is not None else None
        bucket = days.get(key)
        if bucket is None:
            bucket = days[key] = {
                "asset_id": str(row.asset_id),
                "meter_no": (asset.asset_no if asset is not None else None) or row.meter_no_raw,
                # The two ids a caller walks to reach an account and an address.
                # NEITHER is ever drawn (B14 rule 31) — `meter_no` is what a
                # clerk reads and the address is resolved from `premises_id`.
                "unit_id": None if connection is None else str(connection.id),
                "premises_id": (
                    None if connection is None else str(connection.premises_id)
                ),
                "channel": channel,
                "day": day.isoformat(),
                "intervals": 0,
                "zero_intervals": 0,
                "nonzero_intervals": 0,
                "quantity": Decimal("0"),
                "unit": unit,
                "unit_conflict": False,
                "first_at": None,
                "last_at": None,
                "service": row.service or batch.service,
                "is_sample": bool(asset.is_sample) if asset is not None else False,
            }
        if bucket["unit"] is None:
            bucket["unit"] = unit
        elif unit is not None and unit != bucket["unit"]:
            # ⚠ TWO UNITS INSIDE ONE METER-DAY. Adding them produces a number
            # with no meaning, so the day is marked and its total refused.
            bucket["unit_conflict"] = True
        value = row.value
        bucket["intervals"] += 1
        if value is not None:
            bucket["quantity"] += value
            if value == 0:
                bucket["zero_intervals"] += 1
            else:
                bucket["nonzero_intervals"] += 1
        stamp = row.read_at
        if bucket["first_at"] is None or stamp < bucket["first_at"]:
            bucket["first_at"] = stamp
        if bucket["last_at"] is None or stamp > bucket["last_at"]:
            bucket["last_at"] = stamp

    meter_days = [
        {
            **bucket,
            "quantity": None if bucket["unit_conflict"] else str(bucket["quantity"]),
            "first_at": None if bucket["first_at"] is None else bucket["first_at"].isoformat(),
            "last_at": None if bucket["last_at"] is None else bucket["last_at"].isoformat(),
        }
        for bucket in days.values()
    ]
    meter_days.sort(key=lambda one: (str(one["meter_no"] or ""), one["day"], one["channel"]))
    return {
        "batch_id": str(batch.id),
        "batch_no": batch.batch_no,
        "file_name": batch.file_name,
        "status": batch.status,
        "source_kind": batch.source_kind,
        "source_detail": batch.source_detail,
        "service": batch.service,
        "intervals": intervals,
        "intervals_unreadable": unreadable,
        "meters": len({one["asset_id"] for one in meter_days}),
        "meter_days": meter_days,
    }


def meter_normals(
    asset_ids: Any, *, as_of: Any = None, days: int = 90
) -> dict[str, dict[str, Any]]:
    """Each meter's **own** normal and its **last good day** — S-1 and S-4, one query.

    ⚠ **ITS OWN NORMAL, NEVER A FLEET NUMBER** (`RB-111` step 2). A block of
    flats and a bungalow share nothing; a fleet average would alert on every
    large customer every day and never on a small one with a running tap.

    The normal is the mean DAILY consumption over the window, from the meter's
    own committed reads (lineage heads, estimates INCLUDED — an estimate is what
    the utility believes was used, and dropping them would make a seasonal gap
    read as a collapse). It carries its unit; a meter whose reads disagree about
    the unit gets `None` and says so, because a mean over two units is not a
    number (hard rule 3).

    `last_good_day` is **S-4** — the most recent day carrying a committed read
    at status `ok`. Every exception row on `RB-121` carries it: it is what a
    field crew needs and what a clerk deciding whether to estimate needs, and
    the same fact serves both.

    ⚠ **NO NORMAL IS NOT ZERO.** A meter with nothing behind it has no normal
    and `average_per_day` stays `None`. Reporting `0` would make every reading
    infinitely above its own normal — `DEF-127`'s shape, arriving on a
    customer's phone at 07:30.

    `as_of` is STATED by the caller and never read from a clock (`BR-TEN-043`,
    gate `G6`): a runbook knows the day its run is FOR, and a selector reading
    `today` would give two answers for one pinned scope.
    """
    wanted = [str(one) for one in (asset_ids or []) if one]
    if not wanted:
        return {}
    end = as_of.date() if isinstance(as_of, datetime) else as_of
    if not isinstance(end, date):
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-TEN-043",
            message_key="metering.meter_normals.as_of_required",
            params={},
        )
    tenant_id = _tenant_id()
    start = end - timedelta(days=int(days))

    rows = (
        models.MeterRead.objects.filter(
            tenant_id=tenant_id,
            asset_id__in=wanted,
            superseded_by_id__isnull=True,
            # A datetime RANGE on the partition key, never `__date` (DEF-BIL-8490):
            # the same calendar days, and PostgreSQL can prune to them.
            read_at__gte=_day_start(start),
            read_at__lt=_day_after(end),
        )
        .values("asset_id", "read_at", "consumption", "unit", "status", "days_since_prior")
        .order_by("asset_id", "read_at")
    )

    out: dict[str, dict[str, Any]] = {
        one: {
            "average_per_day": None,
            "unit": None,
            "unit_conflict": False,
            "reads_seen": 0,
            "days_covered": 0,
            "last_good_day": None,
            "window_days": int(days),
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
        }
        for one in wanted
    }
    totals: dict[str, Decimal] = {}
    stated_span: dict[str, int] = {}
    first_day: dict[str, date] = {}
    last_day: dict[str, date] = {}
    for row in rows:
        key = str(row["asset_id"])
        bucket = out.get(key)
        if bucket is None:  # pragma: no cover — the filter cannot return one
            continue
        bucket["reads_seen"] += 1
        unit = row["unit"] or None
        if unit is not None:
            if bucket["unit"] is None:
                bucket["unit"] = unit
            elif unit != bucket["unit"]:
                bucket["unit_conflict"] = True
        read_day = _day_of(row["read_at"])
        if (row["status"] or "ok") == "ok":
            seen = bucket["last_good_day"]
            if seen is None or read_day.isoformat() > seen:
                bucket["last_good_day"] = read_day.isoformat()
        if key not in first_day or read_day < first_day[key]:
            first_day[key] = read_day
        if key not in last_day or read_day > last_day[key]:
            last_day[key] = read_day
        consumption = row["consumption"]
        if consumption is None:
            continue
        totals[key] = totals.get(key, Decimal("0")) + consumption
        stated = row["days_since_prior"]
        if stated:
            stated_span[key] = stated_span.get(key, 0) + int(stated)

    for key, bucket in out.items():
        # ⚠ **TWO WAYS TO COUNT THE DAYS AND THE STATED ONE WINS.** A read's
        # `days_since_prior` is what its consumption ACTUALLY covers; falling
        # back to the span between the first and last read in the window is
        # right only when nothing states it. Dividing three monthly reads by
        # three would report a daily normal ninety times too small, and every
        # meter on the estate would then be *far above its own normal*.
        span = stated_span.get(key) or (
            (last_day[key] - first_day[key]).days if key in first_day else 0
        )
        bucket["days_covered"] = span
        if bucket["unit_conflict"] or span <= 0 or key not in totals:
            continue
        bucket["average_per_day"] = str(
            (totals[key] / Decimal(span)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        )
    return out


# ── CR-179-BRC10 · THE RATE IMPACT REPORT'S THREE METERING READS ────────────
#
# `apps/reports/rate_impact.py` is the only caller, through
# `apps/reports/report_seams.py`. Read-only; each answers for MANY units or
# accounts in one call so the report's caller holds one seam per question
# rather than a per-row loop of its own.


def monthly_usage_by_account(
    account_ids: Any, service_code: str, start_month: date, end_month: date
) -> dict[str, list[dict[str, Any]]]:
    """`{account_id: [{month, quantity, unit}, ...]}` — BR-MET-106's stored months.

    The SAME rows the bill prints as its usage history: lineage HEADS only
    (`superseded_by_id IS NULL`), so a restated month is read once, at its
    latest figure. Months are `period_month` (the first of the month) in
    `[start_month, end_month]`, oldest first.

    ⚠ **AN UNREAD MONTH IS ABSENT, NEVER `0`** (BR-MET-106): an account with no
    stored month in the window is simply not a key here, and the caller says
    so (*No usage in the period*) rather than pricing a zero.

    ⚠ **THE UNIT TRAVELS WITH EVERY MONTH** (hard rule 3). Two months of one
    account in two different units are both returned as they are stored; the
    caller decides that it cannot add them.
    """
    ids = [str(one) for one in account_ids or () if one is not None]
    if not ids:
        return {}
    rows = (
        models.MonthlyUsage.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=ids,
            service__code=service_code,
            superseded_by_id__isnull=True,
            period_month__gte=start_month,
            period_month__lte=end_month,
        )
        .order_by("account_id", "period_month", "id")
        .values_list("account_id", "period_month", "quantity", "unit")
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for account_id, month, quantity, unit in rows:
        out.setdefault(str(account_id), []).append(
            {"month": month, "quantity": quantity, "unit": unit}
        )
    return out


def connection_sizes_for_units(unit_ids: Any, service_code: str) -> dict[str, str | None]:
    """`{unit_id: size code or None}` — `connection_size_for`, for many units.

    ⚠ **IT IS A LOOP OVER THE ONE READ BILLING SIZES FROM, DELIBERATELY.**
    `connection_size_for` carries the sub-meter and two-meter rulings
    (`DEF-MET-9773`, decision log 2026-08-27); a second, set-based copy of that
    logic here would be a second answer to *"what size is this connection"*,
    which is how a report and a bill come to disagree about one customer. One
    place to make it set-based later; today's cost is one call per unit.
    """
    out: dict[str, str | None] = {}
    for unit_id in dict.fromkeys(str(one) for one in unit_ids or () if one is not None):
        size = connection_size_for(unit_id, service_code)
        out[unit_id] = (str(size).strip() or None) if size else None
    return out


def billable_size_groups_for_units(
    unit_ids: Any, service_code: str, as_of: date
) -> dict[str, dict[str | None, int] | None]:
    """`{unit_id: {size: count} or None}` — `billable_size_groups`, for many units.

    The items (carts, fire lines) of a COUNTING capacity service on each unit
    on `as_of`, by size — the same population and the same date rule a bill
    counts (`BR-RAT-090`, `CR-063`). `None` keeps its meaning: *do not group*
    or *nobody looked*, never zero. A loop over the one read, for the reason
    `connection_sizes_for_units` gives.
    """
    out: dict[str, dict[str | None, int] | None] = {}
    for unit_id in dict.fromkeys(str(one) for one in unit_ids or () if one is not None):
        groups = billable_size_groups(unit_id, service_code, as_of)
        out[unit_id] = None if groups is None else dict(groups)
    return out


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-001@d76f5b4 (story+rules snapshot hash — EP-MET-01 lead story; co-packet EP-MET-02@8f2ab3c)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-22 by the CR-028 AST-W1 lane (latest_read_for_asset published for the assets seam (DEF-592) — newest committed head, quantity+unit+date, read-only) · AMENDED 2026-08-22 by the CR-028 AST-W2 lane (DEF-475 closed: READ_FILTERS gains `asset` + the read_list branch, so a list CAN be narrowed to one meter; typed_reads_for_asset additionally carries `source` for the S50 Reads tab — additive, the pinned set is asserted as a subset) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (unit_premises_geo_index + latest_reads_for_assets — the AST-03 geo seam, ONE query each (DEF-324); coordinates serve as their stored NUMERIC(9,6) strings; `area` is the EXISTING BR-MET-071 area name, no second vocabulary) · AMENDED 2026-08-22 by the CR-028 debt-sweep lane (D4: export_rollup_last_month — the BTM "Exported · <month>" KPI's figure: last complete tenant-calendar month's export-channel sum, lineage heads only, grouped by explicit unit (rule 3), ONE query (DEF-324); quantities only, no money (BR-AST-025). The demo seed still carries NO export read — assigning M-NET-01 would mint an electric service point in the ready-to-run July batch (the W0 fixture note's phantom-missing-read argument), so the math is proven on committed-read fixtures in tests/test_cr028_export_rollup.py) · AMENDED 2026-08-25 by the CR-030 W5 P2 lane (B18 W5 tasks 5.2/5.3 — `GET /units/{id}/assets` groups on the POST-CR-028 `asset_types.category` (BR-AST-004), never on the (sub)/(master) qualifier, and states `reading_expected`'s absence against DEF-495; `GET /units/{id}/pricing` forwards rating's own plan/schedule/charge/tax strings VERBATIM and computes NO money — B18's worked month is NOT served and says so, because nothing prices a plan outside a bill run and no signed rule states the consumption it would be priced at. An OQ is OWED for that; the absence carries `tracks: null` rather than a fabricated id) · AMENDED 2026-08-26 by the CR-034 (b) WORKEDMONTH lane (CR-034 (b) — `unit_pricing` answers FOR A STATED PERIOD: `period` (`as_of` = the period END, BR-RAT-007; NO period is invented when the caller states none), `plan_history` (BR-RAT-114 stretches + `splits_at`, reported never collapsed), `minimum_charges` (an ASSEMBLY of three already-served strings — no sum, no min, no comparison; which floor wins is BR-RAT-016/028 and is NOT decided here), `discounts` (the plan's OFFER; the GRANT is a stated absence because an enrolment belongs to an ACCOUNT — BR-RAT-069 — and rating's tenant-wide `enrolled` count is DROPPED rather than captioned), `taxes.narrowing` (DEF-273 — the plan's bindings are not R7's final set) and `contract` (no such object exists — and NO OQ IS OWED: the row already existed as `CR-020`, the PO's own contracts-on-plans request, HELD by them 2026-08-21 *"hold on dont proceed"*, cited rather than duplicated). Still zero arithmetic) · AMENDED 2026-08-26 by the CR-034 §7 DISCCOND lane (`_offered_discounts` forwards rating's `terms` WHOLE — the conditions to avail each discount — and `unit_pricing` passes `as_of` into `plan_detail` so the discounts resolve on the SAME service date as the plan and the rate schedules above them. Still zero arithmetic; the GRANT is still `{served:false, reason:"unit_has_no_account"}` and the tenant-wide `enrolled` count is still dropped) · AMENDED 2026-08-26 by the CR-038 W9-seam lane (task 2: `reads_for_unit` — the published target of `apps.customers.seams.reads_for_unit`, the seam `move_reads.py` §4 named as missing. Committed lineage HEADS per meter/register over the unit's CURRENT assignments (`seams.assets_on_unit` — B2 r4, assets owns the rows), quantity WITH its explicit unit (rule 3), `on` as-of capping (BR-TEN-043), ONE `meter_reads` query per unit (DEF-324, the `latest_reads_for_assets` reduction). `read_is_estimated` extracted from `billing_reads_for_unit`'s inline expression so the two consumers share ONE estimate derivation (law 5); that line now calls it — behaviour identical)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ pytest tests/test_us_met_*.py 56 passed/0 skipped · tests/test_us_ast_*.py 73 passed/0 skipped (13 of the 129 are @pytest.mark.isolation, green on sqlite, deselected from the suite run and re-run under -m isolation: 13 passed, 20 postgres-only skipped) · suite `pytest tests -m "not golden and not isolation"` 566 passed, 9 skipped, 44 deselected✔ (shared tree — the concurrent rating lane's tests included; 365 was the pre-lane baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: [net-pair lane 2026-08-16] `net_meter_pair` is the READ half of
#         US-AST-011/012's missing surface — the rule was enforced in
#         validation.py and invisible on every screen. It returns BOTH channels
#         of one cycle and **never a netted figure and never a currency field**
#         (BR-AST-025): subtracting export from import IS rating's credit math
#         (EP-RAT-06, gated by OQ-001). A flat meter answers `is_net_meter:
#         false` with a reason rather than an empty pair, so no screen can draw
#         "Export: 0" over a register that does not exist (BR-AST-010)
# exceptions: [US-MET-013 dispute lane 2026-08-16] `dispute_holds_for_unit` is
#         PUBLISHED FOR BILLING and takes NO PERIOD ARGUMENT — the OQ-043
#         closure holds the account until the dispute is CLEARED, not until the
#         disputed read's period has passed, and scoping it to the run's window
#         would silently release the account next month. `read_list` gained a
#         `disputed` filter and READ_FILTERS declares it: the S25 chip counted
#         markers with no drill-in because BE-05 IGNORES an undeclared `f.`
#         param, so the button would have returned the WHOLE list looking
#         filtered (RED-PROVED: with the clause disabled the TC-4 slice returned
#         4 rows against a count of 1 — `AssertionError: assert 1 == 4`)
# exceptions: collected/progress/last_completion are NULL while the W2 reads lane is unwired (BR-MET-011 — a fabricated 0 would be a different claim) · occupancy resolves "vacant" because customers owns no tables yet, true BY CONSTRUCTION · service id→code resolved by a read-only platform-catalog probe (Eng disposition, identity precedent)
# exceptions: [CR-038 W1 lane 2026-08-26, US-MET-018] `needs_attention_counts.missing` is REAL — the BR-MET-049 plan-driven count (missing required RECORDS, meter × channel, open windows only per BR-MET-057/US-MET-019 §5) via apps/metering/completeness; `missing_unavailable_reason` is GONE with the absence it named, and `missing_unresolved_meters` rides along so a count over unresolvable meters cannot read as "all clear". What the chip shows BETWEEN window close and bill day is unstated in the spec — REPORTED for an OQ (the module docstring argues both readings).
# exceptions: [DEF-1813 unmetered-count lane 2026-08-28, BR-MET-710]
#         `billing_reads_for_unit` publishes `asset_count` and `billable_asset_count`
#         answers the same question for a caller holding no row — BR-RAT-090's
#         OBSERVED quantity, at the SERVICE-PERIOD END DATE. **Worked, ratified:
#         3 carts x $15.00 = $45.00; remove one and the next bill is $30.00.**
#         ⚠ `None` IS NEVER `0`: `0` is the utility having looked and found no
#         carts (a real answer that bills nothing for carts), `None` is nobody
#         having looked, and the row's reason becomes
#         `READ_ABSENT_ASSET_COUNT_UNAVAILABLE` so the account STOPS. The count
#         crosses WITHOUT a unit — a count is not a measure (BR-RAT-036's own
#         row) — and billing attaches the tariff's `billed_unit` where the
#         tariff is in hand. A declared-unmetered point holding CARTS now
#         answers `service_not_metered` rather than `no_read`; the two branches
#         DEF-161's ruling calls the deliverable are untouched and asserted
#         (`tests/test_def_161_designed_absence_bills.py` tc2/tc3). ONE extra
#         read per unit and only on a tenant that has declared something
#         unmetered, so every other tenant prices byte-identically. 🔒 The two
#         money decisions this adds are matched by no `human_owned.txt` glob —
#         `DEF-2313`, raised for the PO rather than taken.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
