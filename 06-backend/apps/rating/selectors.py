# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-001 (Plans tab list + header roll-up, S9) · US-RAT-002/003
#           (plan detail for the S10 wizard + version history) · US-RAT-004
#           (Rate schedules card grid with structure preview + usage counts) ·
#           US-RAT-005/006/007 (structure previews: tiers · TOU · seasons ·
#           demand · capacity · %-of-water) · US-RAT-008 (charge-code catalog) ·
#           US-RAT-009 (taxes & fees list + jurisdictions) · US-RAT-010/011
#           (S9 History over the append-only rate_change_log)
#           Screens: S9 · S10 · S11 · S12 · S13
# Rules:    BR-RAT-027 (plan base is DERIVED Σ, never stored) · BR-RAT-030
#           (lifecycle filter) · BR-RAT-031 (schedule status derived from the
#           in-force version; DRAFTS — dateless versions — excluded from
#           in-force resolution, history and the plan-builder picker) ·
#           BR-RAT-043 (advisory plan eligibility, read back never as a gate) ·
#           BR-RAT-035 (charge-code used-by counts) ·
#           BR-RAT-036 (tax forms) · BR-RAT-037 (append-only history) ·
#           BR-RAT-038 (UoM gate status) · BR-RAT-007 (in-force version by
#           service date) · BR-SHL-011 (list param grammar via BE-05)
# Tests:    06-backend/tests/test_us_rat_plans.py · test_us_rat_schedules.py ·
#           test_us_rat_charges_taxes.py · test_us_rat_versioning.py ·
#           test_def_rat_5742_rating_lists_page_in_sql.py (NFR-3)
# Impacts:  apps/rating/api.py (every read) · apps/tenancy seams
#           (rate_schedule_count for BR-TEN-026/027/029) · the W3 engine, which
#           consumes in_force_version() rather than re-implementing the join
# ───────────────────────────────────────────────────────
"""rating read path (LAW 0: api thin → services sole writer → selectors read).

Everything here is read-only and tenant-scoped through app.tenant_id context
(RLS FORCE on Postgres; the explicit tenant filters keep the same law true on
the sqlite test DB — no cross-tenant queryset, CLAUDE.md rule 1).

Money is serialized as the EXACT NUMERIC(18,6) string (e.g. "18.500000") — no
rounding happens on the read path; half-up 2dp is a finalization/display
concern the client owns (BR-RAT-003). Sums that the design calls "derived"
(the plan base, BR-RAT-027) are computed here at read time and never stored.

No pricing math lives here: tier/TOU/seasonal/demand COMPUTATION is the W3
engine's 🔒 kernel (apps/rating/engine.py). This module only reads the stored
structure rows back out for the S9 preview cards.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING (added 2026-08-16, CLAUDE.md rating math)
-----------------------------------------------------------------------------
This file joined the G7 guard list on 2026-08-16 because a READ path was
DECIDING MONEY. **That is no longer true, and the paragraph below records both
states because the reason a guard can be lifted is worth more than the guard.**

WHAT IT USED TO DO. `rate_structure` / `pricing_inputs` served every time-of-use
window's `unit_price`, ordered by season, day type and start time. Nothing in
the schema recorded which of a meter's registers belonged to which configured
window, so this module matched them BY PRICE RANK (`_window_channels`),
following the signed rule that a holiday bills at "the off-peak (lowest-price)
window". **The ORDER and the PRICES this file returned therefore decided which
register was billed at which rate.** Paired the wrong way round the reference
electric bill goes 88.60 → 122.40 — a 38% overcharge with nothing on screen
looking wrong.

WHAT IT DOES NOW. PO ruling 2026-08-16, verbatim: *"make the rate wizard say
which register is which"* (OQ-236 CLOSED → BR-RAT-067). `time_of_use_windows`
carries a `channel` the UTILITY stated on S11. `pricing_inputs` READS that
column. `_window_channels` and its rank table are DELETED — there is no code
here that can rank prices to place a kWh, so reordering the prices cannot move a
bill, which is asserted by
`tests/test_us_rat_012_tou.py::test_us_rat_012_tc5_price_order_does_not_decide_the_bill`.
A window whose register was never stated is served as `channel=None` and the
engine REFUSES BY NAME; this file never substitutes a value for it.

**The file is left ON the guard list all the same.** Editing `human_owned.txt`
is itself a process event (the same rule that stopped the lane which first
reported this gap from closing it), so the removal is put to the PO in the
review ledger rather than taken here. What changed is the CLAIM: this is an
ordinary tenant-scoped read again, and the money decision it used to make is now
a stored fact somebody typed.

"""

import hashlib
import json
import uuid
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace
from typing import Any

from django.db.models import Count, Exists, Max, OuterRef, Q, QuerySet, Subquery, Sum, TextField
from django.db.models.functions import Cast, Coalesce

from apps.rating import discounts as discount_models
from apps.rating import charge_prices, engine, impact, models, plan_versioning, resolution, schedule_reads, seams
from apps.rating.constants import ALL_SIZES
from apps.rating.pricing import percent_basis
from apps.rating.pricing import wording
from core import errors
from core import batch_reads
from core import tenancy as core_tenancy
from core.pagination import ListParams, filter_values

ZERO = Decimal("0")
SIX_PLACES = Decimal("0.000001")  # DB-3 column precision (see _money)

# Capability-matrix vocabularies (BR-SHL-010: one per list screen; BE-05 falls
# back to the default for anything outside the set).
#: ⚠ **`base_charges` WAS HERE UNTIL 2026-09-27 AND IS WITHDRAWN BY RULING —
#: `BR-RAT-1040`, `DEF-RAT-6927`. DO NOT PUT IT BACK.** PO verbatim: *"a is
#: good"*, on the option that trades the sort for a correct figure. The
#: `Monthly base total` read `$0.00` on every plan because it summed
#: `plan_services.base_charge`, the column `BR-RAT-088` retired when the charge
#: code took the base over — and that same annotation was this sort's SQL key,
#: so the ORDER was as meaningless as the figure and merely looked plausible.
#: Resolving the figure honestly means walking the charge codes narrowed by
#: class and size (`_plan_base_total` below): a Python walk, never a subquery.
#:
#: ⚠ **`NFR-3` IS NOT WEAKENED AND NOBODY MAY READ IT THAT WAY.** The Plans
#: list still PAGES and SORTS in SQL — name, accounts and status are columns
#: and annotations and are untouched. ONE sort OPTION is withdrawn because the
#: value behind it cannot be computed in the database. A plan list is ten or
#: twenty rows at a utility of this size, so sorting by base charge is a
#: convenience; a wrong number on a pricing screen is not.
#: `CR-167-BRC10` §7.3 (image 01) adds `version`, `effective_from`,
#: `effective_to` and `units` — every one a column or the existing count
#: annotation, so the page is still a SQL `LIMIT` (`NFR-3`). `base_charges` is
#: NOT added: it is a walk, not a column (`BR-RAT-1040`), and the list lane draws
#: that head unsortable.
PLAN_SORTS: tuple[str, ...] = (
    "name",
    "accounts",
    "status",
    "version",
    "effective_from",
    "effective_to",
    "units",
)
PLAN_DEFAULT_SORT = "name"
PLAN_FILTERS: tuple[str, ...] = ("status", "service", "customer_class")

# DEF-441 — r10 line 764 draws the rate schedules as a NINE-COLUMN TABLE
# (Schedule · Svc · Structure · Sizes · Seasons · Plans · Accounts · Effective ·
# Status) and the PO asked for SORTABLE headers on all nine. Three of these keys
# existed; six are added here.
#
# ⚠ A HEADER THAT LOOKS SORTABLE AND ISN'T IS THE FAILURE THIS AVOIDS. Before
# this change `schedule_list` mapped any unrecognised sort key back to `name`
# (`{...}.get(params.sort, "name")`), so a `Plans ▲` header would have re-sorted
# by name and reported success. Six of the nine columns are DERIVED per card
# rather than stored, so they sort in Python over the built card list — the same
# place `status` has always sorted — and `_SCHEDULE_DERIVED_SORTS` below is the
# one list of which key reads which derived field.
SCHEDULE_SORTS: tuple[str, ...] = (
    "name",
    "service",
    "structure",
    "sizes",
    "seasons",
    "plans",
    "accounts",
    "effective",
    "status",
)
SCHEDULE_DEFAULT_SORT = "name"
SCHEDULE_FILTERS: tuple[str, ...] = ("service", "structure", "status")

CHARGE_SORTS: tuple[str, ...] = ("code", "description", "type", "amount", "kind")
CHARGE_DEFAULT_SORT = "code"
CHARGE_FILTERS: tuple[str, ...] = ("type", "service", "status", "kind")

TAX_SORTS: tuple[str, ...] = ("name", "rate", "remittance")
TAX_DEFAULT_SORT = "name"
#: `versions` (CR-165-BRC10 round 2): `all` lists every version row; absent,
#: the list shows ONE row per tax — the version current today
#: (`_current_chain_rows_only`).
#: `over_20` (CR-165 §9, the list lane, 2026-10-03): `1` narrows to the
#: percentage taxes above 20% that are active or scheduled — the banner's
#: *Show them*.
TAX_FILTERS: tuple[str, ...] = (
    "level",
    "service",
    "remittance",
    "status",
    "versions",
    "over_20",
)

#: The rate above which the list warns (CR-165 ruled point 2: *"over 20%
#: warns"*). A stored FRACTION, like `taxes.rate` — 20% is `0.20`.
OVER_20_RATE = Decimal("0.20")

#: `GET /tax-jurisdictions` (`DEF-RAT-5754`, `NFR-3`). All three live on
#: `tax_jurisdictions` itself, so every request this endpoint can be sent is
#: SQL-pageable and there is NO `jurisdiction_list_is_sql_pageable` predicate —
#: unlike taxes, schedules and discounts, which each keep a derived path.
#: `name` stays the default, and the default ORDER is byte-for-byte what
#: `jurisdiction_list` has served since US-RAT-009: a pager may not reorder a
#: picker under the clerk using it.
#:
#: ⚠ **`reference_no` IS SEARCHABLE AND NOT SORTABLE, WHICH IS DELIBERATE.**
#: A permit number is a thing a clerk PASTES to find one row; ordering a
#: catalogue by it groups nothing a person would look for, and `DISCOUNT_SORTS`
#: above records why a sort nobody can use is worse than an absent one.
JURISDICTION_SORTS: tuple[str, ...] = ("name", "authority", "level")
JURISDICTION_DEFAULT_SORT = "name"
#: NO filters. `level` is the obvious candidate and is deliberately NOT declared:
#: nothing asks for one, and BE-05 ignores an undeclared `f.*` silently, so a
#: filter declared here with no caller is a surface that can rot unwatched
#: (LAW 0 — an unused wrapper is not coverage). Adding one later is three lines.
JURISDICTION_FILTERS: tuple[str, ...] = ()

#: DIS-01 (`09-screen-inventory.md` §18 row 10). The three sortable columns are
#: the three that live on `discounts` itself — code, the bill-line name, and the
#: status. **Type, Value, Eligibility and Verification are DELIBERATELY ABSENT
#: from this tuple**: every one of them lives on `discount_versions`, so sorting
#: by them means ordering the identity table by a correlated subquery over
#: whichever version is in force, and "in force" is a date question. Declaring
#: them here and quietly ordering by `code` instead would put a live-looking
#: sort arrow over a column that never moves — the failure BR-SHL-010 exists to
#: prevent. Reported rather than half-built.
DISCOUNT_SORTS: tuple[str, ...] = ("code", "name", "status")
DISCOUNT_DEFAULT_SORT = "code"
#: `status` is the DISCOUNT's own column and filters in the database; `type` and
#: `verification` are the VERSION's and are applied to the built rows, exactly as
#: `tax_list` already does for `service`.
DISCOUNT_FILTERS: tuple[str, ...] = ("status", "type", "verification")

HISTORY_SORTS: tuple[str, ...] = ("changed_at", "entity", "actor")
HISTORY_DEFAULT_SORT = "changed_at"
HISTORY_FILTERS: tuple[str, ...] = ("entity_type", "batch", "actor", "from", "to")

MIN_SEARCH_CHARS = 2  # IS-3: server-side search from 2 characters


# ── tenant-scoped helpers ───────────────────────────────────────────────────
def _tenant_id() -> uuid.UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _money(value: Decimal | None) -> str | None:
    """The NUMERIC(18,6) string, normalized to the column's six places so a
    freshly-created row and a re-read row serialize identically. This is
    STORAGE precision (DB-3), NOT money rounding — half-up 2dp happens only at
    invoice-line finalization (BR-RAT-003)."""
    if value is None:
        return None
    return str(Decimal(value).quantize(SIX_PLACES, rounding=ROUND_HALF_UP))


def _outside_city_percent_value(factor: Decimal | None) -> Decimal | None:
    """BR-RAT-102's multiplier, read back as the PERCENT a clerk typed.

    CR-087 D1. `1.150000` in, `15.000000` out — the exact inverse of what
    `services._validate_plan` does on the way in, so a plan saved from step 2
    re-opens on the number that was typed rather than on the number the engine
    multiplies by.

    ⚠ **`None` IS NOT `0`.** A plan with no factor does not surcharge and never
    consults the premises flag (BR-RAT-101); a plan storing `1` has been told to
    surcharge by nothing extra. `plan_detail` refuses to collapse those two for
    the factor and this refuses it for the percent.
    """
    if factor is None:
        return None
    return ((Decimal(factor) - Decimal("1")) * PERCENT_SCALE).quantize(SIX_PLACES)


def _outside_city_percent(factor: Decimal | None) -> str | None:
    """The six-place STORAGE string, the same shape `_money` serves."""
    value = _outside_city_percent_value(factor)
    return None if value is None else str(value)


TWO_PLACES = Decimal("0.01")  # BR-RAT-087 display precision (PO ruling 2026-08-20)
#: A stored fraction is a fraction of ONE; a percent is per HUNDRED. Named
#: because `* 100` in the body reads as a magic number and this is the only
#: thing it can mean.
PERCENT_SCALE = Decimal("100")


def _gl_display(account_id: Any) -> tuple[str | None, str | None]:
    """The chart CODE and NAME behind a `gl_account_id`, for a SCREEN.

    B14 rule 31 — no database id is ever the visible value of a field — and the
    PO's ruling of 2026-09-17: *"dont show uuiD- shoe actual 3 of gL code 4000,
    4010 something liek this and its name … if GL code is not map then dont show
    it"*. `(None, None)` is the whole empty state and it covers three different
    facts deliberately: nothing is mapped, the ledger cannot resolve it, or the
    ledger publishes no such read. All three render nothing.

    ⚠ **ONE SEAM CALL PER ROW, WHICH IS AN N+1 ON A LIST.** It is accepted here
    and said out loud rather than hidden: these three lists are catalogue reads
    bounded by `per`, the query is a single indexed primary-key lookup, and the
    alternative — a batched pre-fetch — would put a second copy of the ledger's
    liveness rule in this module, which is what the seam exists to prevent. If a
    tenant's catalogue ever makes this measurable, the fix is a seam that takes
    a LIST of ids, not a join written here.
    """
    shown = seams.ledger_account_display(account_id)
    if shown is None:
        return None, None
    return shown["code"], shown["name"] or None


def _display_money(value: Decimal | None) -> str | None:
    """BR-RAT-087, the DISPLAY half: *"display 2 decimal - amount and percetnage
    both."* Served BESIDE the stored value, never instead of it.

    ⚠ **WHY THE SERVER DOES THIS AND THE CLIENT MUST NOT.** `ChargeCodesTab` and
    `TaxesFeesTab` each carry a note explaining that they render the raw stored
    value because *"converting to 1.5 on screen would be client-side money
    arithmetic on a value the server owns"*. That reasoning is correct and is B4's
    rule. The half nobody built was the consequence: **if the client may not
    format, the server must.** So a percent shipped as `0.015000` and a customer
    read `0.015000` (DEF-364; DEF-291 caught one instance of it nine days ago).

    **This is not money rounding.** `finalize()` is what rounds a bill line
    half-up at issue (BR-RAT-003). This is a presentation string, and the stored
    six-place value it sits beside is untouched — which is what keeps ❄️ FROZEN
    B4 out of this change entirely.
    """
    if value is None:
        return None
    return str(Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def _display_percent(value: Decimal | None) -> str | None:
    """A stored FRACTION rendered as the percent a human reads: `0.015` -> `1.50%`.

    The x100 is a unit conversion the server owns for the same reason as
    `_display_money` — and it is the specific conversion the two tab files
    correctly refused to do client-side.
    """
    if value is None:
        return None
    scaled = Decimal(value) * PERCENT_SCALE
    # ⚠ THE SYMBOL AND THE SEPARATOR ARE en-US AND THAT IS A KNOWN LIMIT, NOT AN
    # ASSUMPTION NOBODY MADE (DEF-365). IS-8 renders numbers per the tenant's
    # Regional settings and this product ships ELEVEN catalogs; French writes
    # `1,50 %` — comma, and a space before the sign. BR-RAT-087 ruled the
    # PRECISION ("display 2 decimal") and said nothing about locale, so the
    # precision is law here and the formatting is not yet.
    #
    # It is written this way deliberately rather than half-localised: a formatter
    # that guessed at separators would be wrong in a way no test could see,
    # because every catalog would still render a well-formed string. The tenant's
    # locale does not reach this layer at all today — that is the actual gap.
    return f"{scaled.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)}%"


def _display_percent_points(value: Decimal | None) -> str | None:
    """A value already stored in PERCENTAGE POINTS, rendered as a percent:
    `15` -> `15.00%`, `0.5` -> `0.50%`.

    ⚠ **READ THIS BEFORE REACHING FOR `_display_percent` ON A DISCOUNT.** The two
    helpers differ by a factor of one hundred and BOTH produce a well-formed
    string, so picking the wrong one is invisible to every gate in this repo —
    which is precisely the shape of DEF-364, in reverse.

    **Two storage conventions live in this module and neither is wrong.**
    `charges.percent` and `taxes.rate` store a FRACTION OF ONE — `0.015` is
    1.5% — so `_display_percent` scales up. `discount_versions.value` stores
    PERCENTAGE POINTS: `apps/rating/discount_pricing._raw_reduction` computes
    `base * rule.value / HUNDRED`, the seed writes `Decimal("15")` for SENIOR's
    −15% and `Decimal("0.5")` for AUTOPAY's −0.5%, and CR-013 part 3 states
    AUTOPAY as *"−0.5%"* in the same breath as *"rates store to six decimals"*.
    Handing `15` to `_display_percent` would serve **`1500.00%`** for a
    fifteen-percent discount.

    It is built ON TOP of `_display_percent` rather than beside it so there is
    still exactly ONE percent formatter: the divide names the unit conversion,
    and the precision, the symbol and DEF-365's known en-US limit all continue
    to live in one place.
    """
    if value is None:
        return None
    return _display_percent(Decimal(value) / PERCENT_SCALE)


def _uuid_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _valid_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def etag_for(payload: Any) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f'"{digest[:16]}"'


def _page(rows: list[dict[str, Any]], params: ListParams) -> list[dict[str, Any]]:
    """Deliberately NOT paginating here — the `*_list` selectors are the WHOLE
    ordered result set, which is what `apps/rating/exports.py`, `seed_demo`,
    `sample_data` and the two published `customers` seams read.

    ⚠ **A SCREEN MUST NOT COME THROUGH HERE ANY MORE (`NFR-3`,
    `DEF-RAT-5742`).** Until 2026-09-18 every list endpoint in this module
    did: `api._paginated` was handed one of these lists and DRF sliced it, so
    forty thousand rows were built to draw fifty. The `*_page` functions below
    are what an endpoint calls now; this one stays because six non-screen
    callers genuinely want every row.
    """
    return rows


def _sql_page(
    qs: QuerySet,
    params: ListParams,
    build: Callable[[list[Any]], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], int]:
    """`(one page of rows, the whole result set's count)`, taken IN THE DATABASE.

    ⚠ **THE TWO STATEMENTS ARE THE POINT.** `qs.count()` is a `COUNT(*)` over
    the whole filtered set — so the envelope's `count` is the truth and a clerk
    on page 1 of 40,000 is told there are 40,000 — and the slice is a SQL
    `LIMIT`/`OFFSET`, so `build` is handed the PAGE and never the tenant. The
    old shape built every row and threw all but `per` away, which is the
    `NFR-3` breach `DEF-RAT-5742` records and `BR-CUS-1046` already fixed one
    module over.

    ⚠ **NO CAP OF ANY KIND (`NFR-5`).** `per` is the IS-2 page size the caller
    asked for and `page` is whatever it asked for; nothing here refuses a row
    that exists, and an out-of-range page is clamped by the API layer
    (`BR-SHL-011`) rather than emptied here.
    """
    total = qs.count()
    start = max(params.page - 1, 0) * params.per
    return build(list(qs[start : start + params.per])), total


def _built_page(
    rows: list[dict[str, Any]], params: ListParams
) -> tuple[list[dict[str, Any]], int]:
    """The SAME pair, sliced from rows that were already built — the DERIVED path.

    ⚠ **THIS IS `O(tenant)` AND SAYS SO.** It is reached only when a request
    sorts or filters over a figure that is DERIVED rather than stored — a tax's
    status, a schedule's structure — where a SQL `WHERE` would be a SECOND
    implementation of a rule that already has one, free to disagree with the
    cell the same response renders (`DEF-387`'s own reasoning, kept). Each
    list's `*_is_sql_pageable` names exactly which requests land here, so the
    exception is counted rather than hidden.
    """
    start = max(params.page - 1, 0) * params.per
    return rows[start : start + params.per], len(rows)


# ── S9 header roll-up (US-RAT-001 §5) ───────────────────────────────────────
def rating_rollup() -> dict[str, Any]:
    """The Plans & Rates summary line, and it counts SIX things, not three.

    ⚠ **WIDENED 2026-08-21 (DEF-458).** The PO put our header beside r10's:
    *"Summary line has 3 counts, r10 has 6 — missing discounts, taxes & fees,
    contracts."* r10's own line reads **"6 plans · 7 rate schedules · 13 charge
    codes · 5 discounts · 6 taxes & fees · 5 contracts · effective Aug 1,
    2026"**, and ours stopped after charge codes — so a tenant with 23 charge
    codes and zero configured taxes read a header that could not tell them so.

    Two of the three missing counts are added here. **`contracts` is NOT**, and
    the reason is recorded rather than left as a silent gap: contracts are
    `CR-020`, captured 2026-08-20 and DEFERRED by the PO in their own words
    (*"just keep a note of this we will handle it in the end"*). There is no
    `contracts` table to count. The key is served as **`None`** rather than
    omitted or zeroed — `0` would state that this tenant has no contracts,
    which is a claim about their data, where `None` states that the PRODUCT
    does not yet hold contracts. The screen renders the difference.

    Every number is the SERVER's, per US-RAT-001 §5: a client-side count drifts
    the moment a filter is applied.
    """
    tenant_id = _tenant_id()
    today = seams.tenant_today()
    effective = (
        models.TariffVersion.objects.filter(tenant_id=tenant_id, effective_from__lte=today)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .order_by("-effective_from")
        .values_list("effective_from", flat=True)
        .first()
    )
    return {
        "plans": models.RatePlan.objects.filter(tenant_id=tenant_id).count(),
        "rate_schedules": models.Tariff.objects.filter(
            tenant_id=tenant_id, deleted_at__isnull=True
        ).count(),
        "charge_codes": models.Charge.objects.filter(
            tenant_id=tenant_id, deleted_at__isnull=True
        ).count(),
        # DEF-458. `Discount` carries no `deleted_at` — its lifecycle is the
        # four-value `status` and a retired discount is still a configured one,
        # so every row counts. `Tax` does soft-delete and is filtered like the
        # two counts above it.
        "discounts": discount_models.Discount.objects.filter(tenant_id=tenant_id).count(),
        "taxes": models.Tax.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).count(),
        # CR-020, deferred by the PO. None means THE PRODUCT HAS NO CONTRACTS,
        # which is a different statement from 0 — see the docstring.
        "contracts": None,
        "effective_from": effective.isoformat() if effective else None,
    }


# ── Plans (US-RAT-001/002/003) ──────────────────────────────────────────────
def _plan_accounts_subquery() -> Any:
    # ⚠ `DEF-RAT-9026` — COALESCED TO 0 IN SQL. A plan nobody is on has no
    # assignment row, so the bare subquery is NULL, and PostgreSQL sorts NULL
    # FIRST under DESC: *Accounts, most first* opened on a plan with none
    # (sqlite sorts NULL as smallest, so the default suite never saw it). The
    # value sorted must be the value shown, and the screen shows 0.
    return Coalesce(
        Subquery(
            models.UnitPlanAssignment.objects.filter(
                rate_plan=OuterRef("pk"), assigned_to__isnull=True, tenant_id=_tenant_id()
            )
            .values("rate_plan")
            .annotate(total=Count("id"))
            .values("total")[:1]
        ),
        0,
    )


def plan_queryset() -> QuerySet:
    # ⚠ **`base_total=_plan_base_subquery()` WAS HERE AND IS DELETED —
    # `BR-RAT-1040`, 2026-09-27.** It summed `plan_services.base_charge`, the
    # column `BR-RAT-088` retired, and it was the SQL key behind the withdrawn
    # `base_charges` sort. It is removed rather than left unread so that
    # restoring the sort is a visible piece of work with a ruling to read,
    # instead of one line in a dictionary (hard-won law 2's mirror: a live
    # annotation nobody consults is where a wrong figure waits).
    return models.RatePlan.objects.filter(tenant_id=_tenant_id()).annotate(
        account_count=_plan_accounts_subquery(),
    )


def plan_list_queryset(params: ListParams) -> QuerySet:
    """US-RAT-001's S9 Plans tab AS A QUERYSET: search plan name/code, filter
    status/service/customer class, default sort name asc with a stable
    secondary by id (IS-2/IS-3/IS-4).

    ⚠ **SPLIT OUT OF `plan_list` FOR `NFR-3` (`DEF-RAT-5742`), AND NOT ONE
    PREDICATE MOVED.** Every plan filter and every plan sort is a column or an
    annotation, so the whole of *which rows match* and *in what order* is SQL —
    which is what lets `plan_page` take the page in a `LIMIT` instead of
    building the tenant. Two callers now want different amounts of the same
    query, so the query has a name.
    """
    qs = plan_queryset()
    term = params.q.strip()
    if len(term) >= MIN_SEARCH_CHARS:
        qs = qs.filter(Q(name__icontains=term) | Q(code__icontains=term))

    status = params.filters.get("status")
    if status and status.lower() != "all":
        qs = qs.filter(status=status.lower())
    # OQ-306 (PO 2026-10-02): several services at once, OR-combined.
    services = filter_values(params.filters.get("service"))
    if services:
        qs = qs.filter(planservice__service__code__in=services).distinct()
    customer_class = params.filters.get("customer_class")
    if customer_class and _valid_uuid(customer_class):
        qs = _plans_reaching_class(qs, customer_class)

    field = {
        "name": "name",
        # ⚠ **NO `base_charges` ENTRY — `BR-RAT-1040`, 2026-09-27.** It mapped
        # onto `base_total`, the Σ of a RETIRED column, so the list ordered
        # itself by a number that was `0.00` everywhere. The figure moved to
        # `_plan_base_total`, which cannot be expressed as a subquery, so the
        # sort went rather than the correctness. An unknown sort falls back to
        # `name` here, which is what a stale client asking for the old one now
        # gets. **`NFR-3` is intact: every remaining sort is still SQL.**
        "accounts": "account_count",
        "units": "account_count",
        "status": "status",
        "version": "version",
        "effective_from": "effective_from",
        "effective_to": "effective_to",
    }.get(params.sort or PLAN_DEFAULT_SORT, "name")
    prefix = "-" if params.dir == "desc" else ""
    return qs.order_by(f"{prefix}{field}", "id")  # IS-2 stable secondary sort


def _plans_reaching_class(qs: QuerySet, account_type_id: str) -> QuerySet:
    """S9's `customer_class` filter — **plans that NAME this class, plus plans
    that name NONE, because naming none means naming every one.**

    `DEF-RAT-5768`, PO ruling 2026-09-19: *"your understanding is correct - we
    have all option anyway in drop down list - that is default"*. The column
    was `account_type_id`, one uuid, and the filter was
    `qs.filter(account_type_id=<uuid>)`. **The second arm below did not exist
    as a concept under that column and is not a port — it is the ruling.** A
    plan for every class IS a plan for Residential, and leaving it out would
    hide, from a clerk filtering on Residential, every plan that serves them.

    ⚠ **IT IS NOT `account_type_ids__contains`, AND THAT IS NOT A STYLE
    CHOICE.** Django's JSONField `contains` lookup **raises
    `NotSupportedError` on SQLite**, measured rather than remembered, and
    `config/settings/test.py` hardcodes in-memory SQLite — so the obvious
    spelling would pass review, work on PostgreSQL, and take this list down on
    every single test run. That is CLAUDE.md hard-won law 14's trap with the
    two databases the other way round.

    **So the column is CAST TO TEXT and the uuid matched inside it.** It is
    valid SQL on both backends, and it is EXACT rather than a heuristic: a
    uuid is 36 fixed-length characters and no uuid is a substring of another,
    so a hit means the list holds that id and nothing else can produce one.

    ⚠ **NFR-3 — THIS STAYS IN SQL.** Narrowing in Python would mean reading
    every plan before paginating, which is the breach `DEF-PAY-4221` records
    on four other lists.
    """
    return qs.annotate(_classes_text=Cast("account_type_ids", TextField())).filter(
        Q(_classes_text__contains=str(account_type_id))
        | Q(account_type_ids__isnull=True)
        | Q(account_type_ids=[])
    )


def plan_list(params: ListParams) -> list[dict[str, Any]]:
    """EVERY matching S9 plan row, ordered — the stable API and the CSV export.

    ⚠ **PREFER `plan_page` FOR ANYTHING A PERSON IS LOOKING AT.** This is
    `O(tenant)` by construction and `plan_row` costs TWO statements per plan
    (`PlanService` and `PlanRateSchedule` are read per row), so a thousand
    plans is about two thousand round trips. It stays because six callers
    genuinely want the whole set: `exports.py`'s CSV, `seed_demo`,
    `sample_data` and the published `customers` seam.
    """
    return _page([plan_row(plan) for plan in plan_list_queryset(params)], params)


def plan_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """`(one page of S9 plan rows, the whole result set's count)` — `NFR-3`.

    There is no derived path here and there cannot be one: every declared plan
    sort and every declared plan filter is a column or an annotation, so the
    page is ALWAYS a SQL `LIMIT`/`OFFSET` and the count always a `COUNT(*)`.
    """
    return _sql_page(
        plan_list_queryset(params), params, lambda plans: [plan_row(plan) for plan in plans]
    )


#: `BR-RAT-1040`'s reasons, served beside a `null` base total so a screen can
#: say WHICH absence it is met. Each is a different fact about the tenant's own
#: configuration and `$0.00` is a wrong answer to every one of them.
BASE_TOTAL_NO_SCHEDULE = "no_rate_schedule"
BASE_TOTAL_NO_BASE_CODE = "no_base_charge_code"
BASE_TOTAL_REFUSED = "base_charge_refused"
BASE_TOTAL_CLASS_UNKNOWN = "customer_class_not_resolvable"
BASE_TOTAL_DIFFERS_BY_CLASS = "differs_by_customer_class"


def _plan_base_total(plan: Any, schedules: list[Any]) -> tuple[Any, str | None]:
    """🔒 HUMAN-REVIEW-PENDING — the REAL monthly base a plan carries.

    **`BR-RAT-1040`, PO ruling 2026-09-27** (verbatim: *"a is good"*), closing
    `DEF-RAT-6927`.

    ⚠ **WHAT THIS REPLACED, BECAUSE THE OLD ANSWER LOOKED FINE.** Until today
    the figure was `Sum(plan_services.base_charge)` — the column `BR-RAT-088`
    (PO 2026-08-20, *"the CHARGE CODE owns the base amount; a plan displays it,
    never defines it"*) retired, and `DEF-422` removed the control that wrote.
    The column is still WRITTEN — `PlanServiceDraft.base_charge` is preserved
    and re-posted on purpose — so nothing was null, nothing raised, and the
    total was arithmetically correct over its own input. **It was simply the
    wrong input: every plan written since `BR-RAT-088` has `base_charge` NULL,
    so the total read `$0.00` on all of them**, and `$0.00` is a
    plausible-looking figure rather than a visible gap. The worked case the PO
    was shown: *"ten plans all reading `$0.00`, and a clerk clicks the column
    to sort by base charge"*.

    ── THE CHAIN, AND IT IS THE RULED ONE ──────────────────────────────────
    `BR-RAT-1025` (PO 2026-09-19): *"plan → rate schedule -> charge code →
    base charges"*. So: the plan's `PlanRateSchedule` rows give a service and a
    schedule; the schedule's in-force version may NAME the base code; and
    `base_charge_from_charge_code` — **the live path, not a second
    implementation** — answers for that service at the plan's customer class.
    A second narrowing written here would be the defect `DEF-RAT-6960` is
    about, one screen further out.

    ── WHY IT CANNOT BE A SUBQUERY, WHICH IS THE WHOLE OF THE RULING ────────
    The answer needs the charge codes narrowed by CUSTOMER CLASS
    (`applies_to_customer_classes`, a JSON inclusion list) and by SIZE, plus
    the schedule's named-code binding resolved as of a date. That is a walk.
    `NFR-3` requires the Plans list to page and sort in SQL, so the figure and
    a sort by it cannot both live in the database — and the PO chose the
    figure. **`NFR-3` is intact**: the walk runs over the PAGE the `LIMIT`
    already cut, never over the tenant, so its cost is bounded by
    `params.per` and not by the account count.

    ⚠ **AN ABSENCE IS RETURNED AS `None` WITH A NAMED REASON, NEVER AS
    `0.00`.** That is the entire lesson of the defect being closed: a wrong
    figure that looks like a figure is worse than a stated gap, and this repo
    has the same rule at `impact.summarise` (*"never `0.00`, which reads as
    'no effect' to every person and every screen that sees it"*). The reason
    is for the CODE and the register — `B14` rule 33 puts rationale at zero
    words on screen, and every reader of this key already renders a plain
    dash for `null` (`PlansTab` `cells.base`, `PlanDetail`'s `Amount absent=`).

    ⚠ **A PLAN NAMING SEVERAL CLASSES IS RESOLVED AT EACH AND MUST AGREE.**
    `rate_plans.account_type_ids` is a LIST since `DEF-RAT-5768` and `[]` means
    EVERY class. Where the classes disagree there is no single monthly base for
    the plan, and picking one would be `DEF-468`'s shape — billing by list
    ORDER. It answers `differs_by_customer_class` instead.
    """
    if not schedules:
        return None, BASE_TOTAL_NO_SCHEDULE

    class_ids = list(plan.account_type_ids or [])
    if class_ids:
        class_codes = [seams.account_type_code_by_id(value) for value in class_ids]
        if any(code is None for code in class_codes):
            return None, BASE_TOTAL_CLASS_UNKNOWN
    else:
        # `[]` means EVERY class (BR-RAT-108's inclusion list read from the
        # other end), and `None` is what the live path already passes for an
        # account whose class narrows nothing.
        class_codes = [None]

    today = seams.tenant_today()
    versions = {
        str(bound.service_id): in_force_version(bound.tariff, today) for bound in schedules
    }
    totals: list[Any] = []
    for customer_class in class_codes:
        running = ZERO
        for bound in schedules:
            version = versions.get(str(bound.service_id))
            named = getattr(version, "base_charge_code", None) if version is not None else None
            answer = base_charge_from_charge_code(
                bound.service.code,
                customer_class=customer_class,
                named_code=named.code if named is not None else None,
            )
            if answer.get("refusal_reason") == BASE_NOT_NAMED:
                # `DEF-RAT-9832` (PO 2026-10-06) — the schedule names no base
                # code, so the bill charges `$0.00` for this service, and so
                # does this total. The *Choose a base code* warning lives on the
                # plan's own screens and the Rate schedules notice.
                continue
            if answer.get("refusal"):
                return None, BASE_TOTAL_REFUSED
            amount = answer.get("amount")
            if amount is None:
                # ⚠ NOT ZERO. `amount is None` with no refusal means THIS
                # TENANT HAS DECLARED NO BASE CODE FOR THIS SERVICE — the
                # function's own words — which is a tenant that has not adopted
                # `BR-RAT-088`, not a service that is free.
                return None, BASE_TOTAL_NO_BASE_CODE
            running += amount
        totals.append(running)
    if len({str(total) for total in totals}) != 1:
        return None, BASE_TOTAL_DIFFERS_BY_CLASS
    return totals[0], None


def plan_row(plan: Any) -> dict[str, Any]:
    """One S9 Plans-tab row.

    ⚠ **`base_charges` IS THE BASE THE CHARGE CODES ACTUALLY STATE SINCE
    2026-09-27 — `BR-RAT-1040`, closing `DEF-RAT-6927`.** It was
    `Sum(plan_services.base_charge)`, a column `BR-RAT-088` retired, and it
    read `$0.00` on every plan written since. `_plan_base_total` above has the
    chain, the reasoning and why it cannot be a subquery; **`base_charges` is
    now `null` where the figure cannot be stated honestly**, which every
    existing reader already renders as a dash.
    """
    accounts = getattr(plan, "account_count", None)
    if accounts is None:
        accounts = models.UnitPlanAssignment.objects.filter(
            rate_plan=plan, assigned_to__isnull=True, tenant_id=_tenant_id()
        ).count()
    services = list(
        models.PlanService.objects.filter(rate_plan=plan, tenant_id=_tenant_id())
        .select_related("service")
        .order_by("service__sort", "service__code")
    )
    schedules = list(
        models.PlanRateSchedule.objects.filter(rate_plan=plan, tenant_id=_tenant_id())
        .select_related("service", "tariff")
        .order_by("service__sort", "service__code")
    )
    # BR-RAT-1040. Resolved from the `schedules` already fetched above, so the
    # walk costs no extra round trip for the plan's own bindings.
    base_total, base_unavailable = _plan_base_total(plan, schedules)
    return {
        "id": str(plan.id),
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "status": plan.status,
        "version": plan.version,
        # DEF-RAT-5768 — the LIST, and `[]` means EVERY class. A legacy NULL
        # (a row written before `rating/0038`) reads as `[]`: the same fact.
        "account_type_ids": list(plan.account_type_ids or []),
        # ⚠ **A DERIVED, READ-ONLY BRIDGE — NOT A SECOND SOURCE OF TRUTH, AND
        # IT IS ON ITS WAY OUT (`DEF-RAT-5798`).** There is no
        # `rate_plans.account_type_id` column any more; this is the FIRST id
        # of the list, or `null` when the plan names every class.
        #
        # **WHY IT IS HERE AT ALL:** two screens owned by another lane read
        # `plan.account_type_id` to choose between *audience not set* and
        # *audience we cannot name* — `PlanDetail.tsx:920` and `:1253`.
        # Removing the key without them would make both read *unnamed* for
        # every plan on every tenant, with `tsc` and every test green: the
        # exact shape `DEF-CUS-3653` records, where retiring `kind='service'`
        # silently emptied an account header line. Serving the derived value
        # keeps both screens saying the true thing until `DEF-RAT-5798` moves
        # them onto the list.
        #
        # ⚠ **IT IS READ-ONLY AND CANNOT DRIFT.** `PLAN_FIELDS` does not
        # accept `account_type_id` — a payload sending it is refused BY NAME —
        # so nothing can write a value that disagrees with the list.
        "account_type_id": (list(plan.account_type_ids or []) or [None])[0],
        "account_subtype_id": _uuid_or_none(plan.account_subtype_id),
        "budget_billing": plan.budget_billing,
        # US-RAT-002 §5: the step-5 boxes, stored on the plan. ADVISORY ONLY
        # (BR-RAT-043) — nothing downstream may read this as a gate.
        "eligibility": plan.eligibility or {},
        "minimum_bill_amount": _money(plan.minimum_bill_amount),
        # ⚠ **BR-RAT-102's FACTOR, SERVED AS THE COLUMN STANDS — `None` IS NOT
        # `1`.** `plan_jurisdiction_pricing` folds a stored `1` into `None`
        # because to the PRICING they are one statement; this projection is what
        # a SCREEN and the audit snapshot read, and there the two differ: `None`
        # is *this plan does not surcharge*, a stored `1` is *somebody typed one*
        # and the form must re-open on what they typed. Collapsing it here would
        # make an edit look like it did not save.
        "outside_city_factor": _money(plan.outside_city_factor),
        # ── CR-087 D1 · THE SAME FACT, ON THE SCALE THE SCREEN ASKS FOR ──────
        # The wizard's step 2 asks for a PERCENT now (PO ruling 2026-09-08), and
        # the form has to re-open on what the clerk typed. Derived from the
        # stored multiplier here rather than scaled in the browser: a scale
        # conversion written into a screen is exactly the trap the ruling
        # removed, one layer up.
        #
        # ⚠ **NULL TRAVELS ALL THE WAY THROUGH.** `None` is *this plan does not
        # surcharge* and a stored `1` is *somebody typed nothing extra* — the
        # comment above says why this projection must not collapse them, and the
        # percent inherits the same distinction: `None` and `0.000000`.
        "outside_city_percent": _outside_city_percent(plan.outside_city_factor),
        # BR-RAT-087 / CLAUDE.md hard rule 2 — percentages STORE to six and
        # DISPLAY to two. Served beside the six-place value so no client guesses.
        "outside_city_percent_display": _display_percent_points(
            _outside_city_percent_value(plan.outside_city_factor)
        ),
        "effective_from": plan.effective_from.isoformat() if plan.effective_from else None,
        "effective_to": plan.effective_to.isoformat() if plan.effective_to else None,
        "services": [row.service.code for row in services],
        # BR-RAT-1040 — the REAL figure, or `null` and a named reason. Never
        # `0.00`: a wrong number on a pricing screen is not a convenience.
        "base_charges": _money(base_total) if base_total is not None else None,
        "base_charges_display": _display_money(base_total),
        "base_charges_unavailable": base_unavailable,
        "rate_schedules": [
            {
                "service": row.service.code,
                "tariff_id": str(row.tariff_id),
                "tariff_name": row.tariff.name,
            }
            for row in schedules
        ],
        "accounts": int(accounts or 0),
    }


def _charge_size_amounts(
    charge_ids: list[Any], as_of: date | None = None
) -> dict[Any, list[dict[str, Any]]]:
    """DEF-431's per-size table for MANY charge codes, in ONE query.

    Batched rather than read per code (DEF-324's rule): a plan with a dozen
    charge rules would otherwise cost a dozen round trips to answer one screen.
    The projection is `charge_row`'s own, field for field, so the per-size
    amounts a plan shows and the ones the charge catalogue shows are the same
    strings and cannot drift.

    A code with no rows is ABSENT from the mapping, and the caller reads that as
    `[]` — *"this code does not vary by size"*, which is what every charge code
    in the database says today.
    """
    if not charge_ids:
        return {}
    # CR-156-BRC10 — read through the ONE lookup, on the day asked (default
    # the tenant's today). The every-class *All sizes* row is the code's
    # `amount` and is served there, not as a size; a class-priced *All sizes*
    # row IS listed here, under its class.
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for charge_id, rows in charge_prices.rows_in_force(
        charge_ids, as_of, with_versions=True
    ).items():
        for row in rows:
            if row.is_flat and row.customer_class is None:
                continue
            grouped.setdefault(charge_id, []).append(_price_row_json(row))
    return grouped


def _price_row_json(row: Any) -> dict[str, Any]:
    """ONE projection of a price row for every screen (`CR-156-BRC10`), so the
    plan detail, the charge row and the price history cannot drift — the
    `size_amounts` shape plus the row's dates and its killed mark."""
    return {
        "id": str(row.id),
        "size_class": row.size_class,
        # CR-087 A1 — NULL means EVERY class, never "no class".
        "customer_class": row.customer_class,
        "amount": _money(row.amount),
        # BR-RAT-087: the client never formats money.
        "amount_display": _display_money(row.amount),
        "currency": row.currency,
        "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "killed": row.killed_at is not None,
        # PO 2026-10-01 — v1, v2 … per (code, size, class) in date order,
        # counted by `charge_prices` so no screen works it out; None for a row
        # superseded before it began (it prices no day).
        "version": row.version,
        # DEF-RAT-8753 — a penalty's TERMS row (percent + minimum for one
        # class) carries these and a null amount; every other row null.
        "percent": _money(getattr(row, "percent", None)),
        "percent_display": _display_percent(getattr(row, "percent", None)),
        "min_amount": _money(getattr(row, "min_amount", None)),
        "min_amount_display": _display_money(getattr(row, "min_amount", None)),
    }


def plan_detail(plan_id: Any, as_of: date | None = None) -> dict[str, Any]:
    """The S10 wizard's full bundle (r5 #6–#11): services + schedules + charge /
    deposit / penalty / tax rules. Discounts are the negative-amount charge
    rules (BR-RAT-043) — the same rows, no separate shape.

    `as_of` is BR-RAT-007's service date and reaches ONE thing: which DISCOUNT
    VERSION's value and conditions are served. It defaults to `None` — the
    tenant's today, byte-identical to every answer this gave before it took a
    date — and exists so a caller that has already narrowed the plan and the
    rate schedules to a service date does not then describe the discounts as of
    a different one (`unit_pricing`, CR-034)."""
    plan = plan_or_404(plan_id)
    row = plan_row(plan)
    # ── PO ruling 2026-09-10 · ONE PLACE TO SET, EVERYWHERE ELSE SHOWS ────────
    # Verbatim: *"set it in rates and use it in plans - thats it - this is rule
    # - when you do the final review on plan you show all values - coming from
    # rate schedule; and when we view plan details you show the details again
    # coming from rate schedule"*. The plan's own `minimum_amount` column is
    # gone (`rating/0030`+`0031`); the figure the review step and the plan's
    # page must SHOW is the attached schedule's, resolved at the service date
    # like everything else `BR-RAT-007` governs.
    #
    # ⚠ **SERVED UNDER A DIFFERENT NAME ON PURPOSE.** It is
    # `schedule_minimum_amount`, not `minimum_amount`. A reader that still asks
    # for the old key now gets a `tsc` error at every call site instead of
    # `undefined` rendered as a blank cell — which is the failure that has cost
    # this repository most (`DEF-CUS-3653`: an account header composed from a
    # retired address kind returned null forever, with every test green). The
    # name also says where the number came from, which is the whole ruling.
    #
    # One extra query per plan service line, batched here rather than resolved
    # in a loop by the caller.
    _minimum_by_service = {
        str(bound.service_id): in_force_version(bound.tariff, as_of or seams.tenant_today())
        for bound in models.PlanRateSchedule.objects.filter(
            tenant_id=_tenant_id(), rate_plan=plan
        ).select_related("tariff")
    }

    def _schedule_minimum(service_id: Any) -> Any:
        # `DEF-RAT-8759` · PO 2026-10-01, option A — **THE MINIMUM IS SET PER
        # METER SIZE**, and `rating/0053` emptied `tariff_versions.minimum_bill`,
        # so reading the version here showed *no minimum* on a plan whose every
        # size floors the bill. This line holds ONE figure, so it shows the
        # per-size minimum where the in-force version's rows all state the same
        # one, and nothing otherwise: a single number for sizes that differ
        # would be a floor no size actually has. Worked: rows 5/8" `$15.00`,
        # 1" `$15.00` → `$15.00`; rows 5/8" `$15.00`, 2" `$40.00` → nothing.
        version = _minimum_by_service.get(str(service_id))
        if version is None:
            return None
        figures = list(
            models.RateSizeRow.objects.filter(
                tenant_id=_tenant_id(), tariff_version=version
            ).values_list("minimum_bill", flat=True)
        )
        if not figures or any(figure is None for figure in figures):
            return None
        return figures[0] if len(set(figures)) == 1 else None

    def _base_charge_code(service_id: Any) -> str | None:
        # ⊕ `CR-164-BRC10` item 12 — New Connection step 2's pricing table
        # names the charge code the schedule bills its base from. A READ of the
        # in-force version's own `base_charge_code`, resolved above at the same
        # service date; it prices nothing and moves no figure.
        version = _minimum_by_service.get(str(service_id))
        code = getattr(version, "base_charge_code", None) if version is not None else None
        return getattr(code, "code", None)

    row["services"] = [
        {
            "service": item.service.code,
            "name": item.service.name,
            "base_charge": _money(item.base_charge),
            "base_charge_code": _base_charge_code(item.service_id),
            "currency": item.currency,
            # READ THROUGH from the rate schedule — never the plan's own, which
            # no longer exists. `None` where no schedule is attached yet or the
            # attached one states no floor; both are "no minimum", which is what
            # `BR-RAT-028` makes NULL mean, and neither is `0`.
            "schedule_minimum_amount": _money(_schedule_minimum(item.service_id)),
            # BR-RAT-087 / CLAUDE.md hard rule 2 — the client never formats
            # money; stored to four, shown to two.
            "schedule_minimum_amount_display": _display_money(_schedule_minimum(item.service_id)),
            "gl_account_id": _uuid_or_none(item.gl_account_id),
            # BR-RAT-102 — which of the plan's services escape the factor.
            # §A4 S2: *"BASE-S $8.00 (flat everywhere — the multiplier does NOT
            # touch sewer)"*.
            "outside_city_exempt": item.outside_city_exempt,
        }
        for item in models.PlanService.objects.filter(rate_plan=plan, tenant_id=_tenant_id())
        .select_related("service")
        .order_by("service__sort", "service__code")
    ]
    # ── CR-034 (b) · THE CODE'S OWN AMOUNT, BESIDE THE PLAN'S OVERRIDE ───────
    # This projection served `amount_override` and NOTHING ELSE about the code,
    # so every reader that met a NULL override had a name and no figure. The
    # unit Plan tab rendered that as the sentence *"At the charge code's own
    # amount"* — a promise of a number with the number withheld, which is worse
    # than saying nothing, because a reader concludes the amount is unknowable
    # rather than merely unfetched. It was never unknowable: `charge_row` has
    # served all of it since DEF-364/DEF-431.
    #
    # ADDITIVE — every existing key keeps its name, its type and its meaning, so
    # no current reader changes behaviour. The new keys are `charge_row`'s OWN
    # names rather than new ones, because two vocabularies for one column is how
    # two screens start disagreeing about a charge (DEF-291's shape).
    #
    # ⚠ THE OVERRIDE AND THE CODE'S AMOUNT ARE TWO FACTS AND BOTH TRAVEL. A NULL
    # override means *"this plan does not restate the price"* and the code's own
    # amount is what bills; collapsing them here into one "effective amount"
    # would be the plan/code precedence rule (DEF-154's shape) reimplemented in a
    # read, in a second place. The precedence stays where it is written and this
    # serves both figures so a screen can SAY which one applies.
    charge_rules = list(
        models.PlanChargeRule.objects.filter(rate_plan=plan, tenant_id=_tenant_id())
        .select_related("charge", "charge__service")
        .order_by("charge__code")
    )
    rule_size_amounts = _charge_size_amounts([rule.charge_id for rule in charge_rules], as_of)
    # CR-156-BRC10 — the code's FLAT amount is its every-class *All sizes* row
    # on the day asked; one query for every rule.
    rule_flat = charge_prices.flat_amounts([rule.charge_id for rule in charge_rules], as_of)
    row["charge_rules"] = [
        {
            "id": str(rule.id),
            "charge_id": str(rule.charge_id),
            "code": rule.charge.code,
            "name": rule.charge.name,
            "amount_override": _money(rule.amount_override),
            # BR-RAT-087 — the two-place string a screen renders, beside (never
            # instead of) the six-place value anything that computes reads.
            "amount_override_display": _display_money(rule.amount_override),
            "recurrence": rule.recurrence,
            "taxable": rule.taxable,
            # ── the CODE's own row, forwarded verbatim ───────────────────────
            # NULL service is the spec's *"Any"* (CR-013 part 2: *"Svc is `—`
            # for account-level codes (late fee, NSF)"*) and is served as null,
            # never as a string, so a screen draws the em-dash rather than a
            # service named "any" that no catalogue contains.
            "service": rule.charge.service.code if rule.charge.service_id else None,
            "charge_type": rule.charge.charge_type,
            # BR-RAT-088 — DECLARED, never inferred from the code string. A
            # reader needs it: an `is_base` code is the service's base and
            # reaches a bill through R4, NOT as a fee line (`billable_charge_
            # codes` excludes it for that reason), so a screen listing it beside
            # the fees without saying so states that it bills twice.
            "is_base": rule.charge.is_base,
            "amount_rule": rule.charge.amount_rule,
            "amount": _money(rule_flat.get(rule.charge_id)),
            "amount_display": _display_money(rule_flat.get(rule.charge_id)),
            "percent_display": _display_percent(_penalty_pair_today(rule.charge)[0]),
            "min_amount_display": _display_money(_penalty_pair_today(rule.charge)[1]),
            "max_amount_display": _display_money(rule.charge.max_amount),
            # BR-RAT-108 — served as itself, not normalised: an EMPTY list
            # ("every class") and a NAMED list are different facts, exactly as
            # `charge_row` puts it.
            "applies_to_customer_classes": list(rule.charge.applies_to_customer_classes or []),
            # DEF-431 — r10's water matrix prices 5/8" at $12.00 and 2" at
            # $64.00. An EMPTY list means the code does not vary by size and the
            # scalar above is the amount; a row present with a NULL amount says
            # the utility does not serve that size and R4 refuses (DEF-277).
            "size_amounts": rule_size_amounts.get(rule.charge_id, []),
        }
        for rule in charge_rules
    ]
    row["deposit_rules"] = [
        {
            "account_type_id": str(rule.account_type_id),
            "amount": _money(rule.amount),
            "currency": rule.currency,
        }
        for rule in models.PlanDepositRule.objects.filter(rate_plan=plan, tenant_id=_tenant_id()).order_by(
            "account_type_id"
        )
    ]
    # ── BR-RAT-1011 (`CR-078`) — WHICH CHARGE CODE THIS PLAN'S LATE FEE COMES
    # FROM, served as an OBJECT and never as a bare id (B14 rule 31: no
    # database id is ever the visible value of a field). `None` is the ruled
    # ZERO — *"if plan doent provide you that charge code then you have to put
    # zero on late payment"* — so the screen has to be able to say *this plan
    # charges no late fee* rather than draw an empty box that reads as "not
    # loaded". A RETIRED code is served as absent, because that is what it is
    # to the engine (IS-1) and a screen showing the name of a code that charges
    # nothing would be worse than showing nothing.
    late_fee_charge = plan.late_fee_charge if plan.late_fee_charge_id else None
    if late_fee_charge is not None and late_fee_charge.deleted_at is not None:
        late_fee_charge = None
    row["late_fee_charge"] = (
        None
        if late_fee_charge is None
        else {
            "id": str(late_fee_charge.id),
            "code": late_fee_charge.code,
            "name": late_fee_charge.name,
            "amount_rule": late_fee_charge.amount_rule or "flat",
            # DISPLAY 2 (CLAUDE.md rule 2) — the stored value is 6dp and 4dp
            # respectively and neither is what a clerk reads.
            "percent_display": _display_percent(_penalty_pair_today(late_fee_charge)[0]),
            "min_amount_display": _display_money(_penalty_pair_today(late_fee_charge)[1]),
        }
    )
    penalty = models.PlanPenaltyRule.objects.filter(rate_plan=plan, tenant_id=_tenant_id()).first()
    row["penalty_rule"] = (
        None
        if penalty is None
        else {
            "late_fee_min": _money(penalty.late_fee_min),
            "late_fee_pct": _money(penalty.late_fee_pct),
            "grace_days": penalty.grace_days,
            "grace_mode": penalty.grace_mode,
        }
    )
    # Shape 1 rows only — the jurisdiction BINDINGS (BR-RAT-096). The shape is
    # unchanged so every existing reader keeps its meaning; the BR-RAT-113
    # attachments are their own list below, because "this plan binds the state
    # of Texas" and "this plan attaches the PUC Regulatory Fee" are different
    # sentences and a screen must be able to say which one it is making.
    row["tax_rules"] = [
        {
            "jurisdiction_id": str(rule.jurisdiction_id),
            "jurisdiction": rule.jurisdiction.name,
            "rate_override": _money(rule.rate_override),
        }
        for rule in models.PlanTaxRule.objects.filter(rate_plan=plan, tax__isnull=True, tenant_id=_tenant_id())
        .select_related("jurisdiction")
        .order_by("jurisdiction__name")
    ]
    # Shape 2 — the EXPLICIT attachments (BR-RAT-113: *"staff need to pick up
    # and attach taxes and fees on the plan"*). `rate_display`, never `rate`
    # (BR-RAT-087/DEF-291), and no rate override exists to serve (BR-RAT-094).
    row["tax_attachments"] = [
        {
            "tax_id": str(rule.tax_id),
            "name": rule.tax.name,
            "kind": rule.tax.kind,
            "rate_display": _display_percent(rule.tax.rate),
            "flat_amount_display": _display_money(rule.tax.flat_amount),
            "jurisdiction": (
                jurisdiction_row(rule.tax.jurisdiction)
                if rule.tax.jurisdiction_id is not None
                else None
            ),
        }
        for rule in models.PlanTaxRule.objects.filter(rate_plan=plan, tax__isnull=False, tenant_id=_tenant_id())
        .select_related("tax", "tax__jurisdiction")
        .order_by("tax__name")
    ]
    # ── PRB-19 · ONE READ SERVES THE ROW **AND** ITS CELLS ───────────────────
    # `tax_rules` above names an AUTHORITY and `tax_attachments` names a TAX,
    # and neither carries the level, the authority's own name or the rate — so
    # every screen drawing the plan's taxes had to scan `GET /taxes` separately
    # and JOIN in the browser. That scan is `CATALOGUE_SCAN_PER` rows deep, so a
    # tax beyond the first page produced a cell reading *"this was not in the
    # list this page read"* — the apology the blueprint names on three tabs at
    # once. `tax_lines` is that join done where the data is.
    #
    # ⚠ **ADDITIVE.** `tax_rules` and `tax_attachments` keep their names, their
    # shapes and their meanings; nothing that reads them changes behaviour.
    row["tax_lines"] = plan_tax_lines(plan)
    row["combined_tax_rate_display"] = plan_combined_tax_rate_display(plan)
    row["discounts"] = plan_discount_rules(plan, as_of)
    row["versions"] = plan_versions(plan)
    return row


def plan_tax_lines(plan: models.RatePlan) -> list[dict[str, Any]]:
    """Every tax that reaches this plan, as ONE row per tax, level first.

    ── WHAT A ROW IS ────────────────────────────────────────────────────────
    A LEVEL (state · county · city · special_district), the AUTHORITY that
    levies it, the tax's own name, its rate as the SERVER's display string, and
    what it applies to. That is the four-column table the plan's page and the
    wizard's review both draw, and it is served once so the two cannot lay the
    same figure out differently.

    ── THE TWO SENTENCES A PLAN CAN MAKE, FOLDED INTO ONE LIST ──────────────
    `BR-RAT-096` binds an AUTHORITY (*"this plan binds the state of Texas"*) and
    `BR-RAT-113` attaches ONE tax (*"this plan attaches the PUC Regulatory
    Fee"*). Those are different sentences, and `plan_detail` keeps them as
    different lists for the screens that must say which one is being made. This
    read answers a THIRD question — *what is this customer taxed* — for which
    the distinction does not matter, so both arrive here and a tax reached by
    both routes appears ONCE.

    ⚠ **IT STATES NO PRECEDENCE AND APPLIES NO RULE.** Which premises actually
    attracts a tax is `premises_in_scope`'s decision on a real bill, and a
    second implementation of that predicate is exactly what
    `premises_geography_rows` refused to become.
    """
    return [_tax_line(tax) for tax in _plan_taxes(plan)]


def _plan_taxes(plan: models.RatePlan) -> list[models.Tax]:
    """The LIVE taxes this plan is bound to or has attached, level first.

    ⚠ **LIVENESS IS `tax_status`, NEVER A COLUMN (DEF-387).** `taxes` has no
    `status` column: the four-value lifecycle is DERIVED from `is_draft`,
    `deleted_at` and the effective window against the tenant's own today, and
    filtering on a stored value here would be a second implementation of that
    derivation — the way a list and a detail start disagreeing about one row.
    So the derivation is CALLED, once per candidate, exactly as `tax_list` does.
    """
    seen: set[str] = set()
    taxes: list[models.Tax] = []

    def _take(tax: models.Tax) -> None:
        key = str(tax.id)
        if key in seen or tax_status(tax) != "active":
            return
        seen.add(key)
        taxes.append(tax)

    bound = [
        rule.jurisdiction_id
        for rule in models.PlanTaxRule.objects.filter(rate_plan=plan, tax__isnull=True, tenant_id=_tenant_id())
    ]
    if bound:
        for tax in models.Tax.objects.filter(
            tenant_id=_tenant_id(), jurisdiction_id__in=bound
        ).select_related("jurisdiction"):
            _take(tax)
    for rule in models.PlanTaxRule.objects.filter(
        rate_plan=plan, tax__isnull=False, tenant_id=_tenant_id()
    ).select_related("tax", "tax__jurisdiction"):
        _take(rule.tax)

    #: The order a bill and a tariff sheet are both read in — biggest authority
    #: first. A level this product does not know sorts last rather than being
    #: dropped, because an unrecognised level is still a tax somebody charges.
    order = {"federal": 0, "state": 1, "county": 2, "city": 3, "special_district": 4}
    taxes.sort(
        key=lambda tax: (
            order.get(
                (tax.jurisdiction.level or "") if tax.jurisdiction_id else "",
                9,
            ),
            tax.name or "",
        )
    )
    return taxes


def _tax_line(tax: models.Tax) -> dict[str, Any]:
    jurisdiction = tax.jurisdiction if tax.jurisdiction_id else None
    return {
        # A VOCABULARY value the screen translates, never a sentence, so eleven
        # catalogues can each name the level themselves.
        "level": None if jurisdiction is None else jurisdiction.level,
        # The AUTHORITY that levies it, falling back to the jurisdiction's own
        # name where no separate authority is recorded — *Bexar County — Local*
        # is one authority written two ways, and a screen must not print an
        # em-dash for it.
        "authority": (
            None if jurisdiction is None else (jurisdiction.authority or jurisdiction.name)
        ),
        "name": tax.name,
        #: BR-RAT-036's computation form: percent | flat_per_bill | per_unit |
        #: per_meter. The card needs it because only ONE of the four is a rate.
        "kind": tax.kind,
        # BR-RAT-087 — the server's own percent string. `taxes.rate` is a
        # FRACTION and scaling it in a browser is the client-side money
        # arithmetic that rule exists to remove.
        "rate_display": _display_percent(tax.rate),
        "flat_amount_display": _display_money(tax.flat_amount),
        # `[]` is *every service*, which the screen says in words rather than
        # leaving an empty cell.
        "applies_to_services": list(tax.applies_to_services or []),
    }


def plan_combined_tax_rate_display(
    plan: models.RatePlan, class_codes: list[str] | None = None
) -> str | None:
    """PRB-19 — what the PERCENTAGE taxes on this plan come to, added up HERE.

    The PO's own case: 6.25% and 1.0% is 7.25%, and it is *"a sum a clerk was
    doing in their head on every call"*. The base total is worked out on save
    for exactly the same reason.

    ⚠ **THE SUM IS THE SERVER'S BECAUSE ADDING TWO DECIMAL STRINGS IN A BROWSER
    IS WHAT CLAUDE.md RULE 2 FORBIDS.** It is done on the STORED six-place
    fractions and rendered ONCE through `_display_percent`, so the total is
    rounded to two places once — rather than being the sum of two figures each
    already rounded, which is a different number and an unsigned second money
    implementation.

    ⚠ **ONLY THE PERCENT FORM IS SUMMABLE, AND THE OTHER THREE ARE NOT
    DROPPED — THEY ARE SIMPLY NOT A PERCENTAGE.** A flat `$2.00 per bill` and a
    `$1.25 per meter` fee (BR-RAT-036's four forms) cannot be added to a rate,
    so they keep their own rows on the card, which is where a reader meets them.

    ⚠ **`None` WHEN THERE IS NOTHING TO ADD, NEVER `"0.00%"`.** *not set* and
    *zero* are different facts — the whole of the PO's E2 ruling, one layer
    down — and a served `"0.00%"` reads on screen as a tax of zero on a plan
    nobody has bound a tax to.
    """
    # ⊕ `DEF-CUS-9836` — `class_codes` is ONE ACCOUNT's class (New Connect
    # step 2 reads the plan with `?classes=`): the figure is then what a bill
    # for THAT account charges, which a single class always has. Absent, the
    # plan's own classes, exactly as before.
    wanted = [code for code in (class_codes or []) if code]
    classes = wanted or plan_class_codes(plan)
    percent = [tax for tax in _plan_taxes(plan) if tax.kind == "percent" and tax.rate is not None]
    reach = {str(tax.id): tax_reach_of_classes(tax, classes) for tax in percent}
    # `DEF-RAT-9519` — the figure is what a bill on this plan CHARGES. A tax
    # none of the plan's classes pays is not in it; and where the classes pay
    # DIFFERENT taxes (a commercial-only tax on an every-class plan) no one
    # figure is true, so none is served — the base total's own
    # `differs_by_customer_class` answer, one section down.
    if any(value == TAX_REACH_SOME for value in reach.values()):
        return None
    rates = [tax.rate for tax in percent if reach[str(tax.id)] == TAX_REACH_ALL]
    if not rates:
        return None
    total = Decimal("0")
    for rate in rates:
        total += Decimal(rate)
    return _display_percent(total)


#: `DEF-RAT-9519` — does a tax reach the customer classes a plan is for?
#: `all` every class the plan names pays it · `some` only some do (or the plan
#: is for every class and the tax is not) · `none` no class the plan names pays
#: it. Listed and MARKED on the plan, never refused: a utility may attach a tax
#: now and widen the plan's classes later (our judgment, decision log
#: *"A TAX THE PLAN'S CLASSES DO NOT PAY"*, 2026-10-03).
TAX_REACH_ALL = "all"
TAX_REACH_SOME = "some"
TAX_REACH_NONE = "none"


def plan_class_codes(plan: models.RatePlan) -> list[str] | None:
    """The plan's customer classes as `account_types.code` values, or `None`
    for EVERY class (`account_type_ids` `[]`). An id the tenant cannot name is
    left out; if none can be named the plan is read as every class, which is
    the reading that can only mark LESS (`some`, never `none`)."""
    return class_codes_of_ids(list(plan.account_type_ids or []))


def class_codes_of_ids(ids: list[Any]) -> list[str] | None:
    codes = [seams.account_type_code_by_id(one) for one in ids]
    named = [str(code) for code in codes if code]
    return named or None


def tax_reach_of_classes(tax: models.Tax, class_codes: list[str] | None) -> str:
    """`all` | `some` | `none` — the CLASS gate of `tax_applies_to`, asked of
    every class the plan names, with that gate's own comparison (case-folded
    codes), so the screen and the bill cannot disagree about who pays."""
    wanted = {str(code).strip().lower() for code in (tax.applies_to_customer_classes or [])}
    if not wanted:
        return TAX_REACH_ALL
    if class_codes is None:
        every = {str(code).strip().lower() for code in seams.account_type_names_by_code()}
        return TAX_REACH_ALL if every and every <= wanted else TAX_REACH_SOME
    hits = [str(code).strip().lower() in wanted for code in class_codes]
    if all(hits):
        return TAX_REACH_ALL
    return TAX_REACH_SOME if any(hits) else TAX_REACH_NONE


# ── CR-087 D5 / PRB-21 · THE UNITS A PLAN PRICES ────────────────────────────


def plan_units_queryset(plan_id: Any) -> QuerySet:
    """The CURRENT unit→plan assignments for one plan, ordered for a screen.

    ⚠ **A QUERYSET, DELIBERATELY, AND THIS IS THE WHOLE OF `NFR-3` FOR THIS
    SCREEN.** Every other list selector in this module hands back a built list
    and lets the API paginate it — which is correct at T7 and is exactly the
    shape `GET /outstandings` and `GET /cheques` are breaching at T5, where the
    same code path materialises every row of the set to render fifty of them.
    Returning the queryset means DRF's paginator issues a SQL `COUNT` over the
    whole set and a SQL `LIMIT`/`OFFSET` for the page, so:

      · the TOTAL is the whole set rather than the page — or the tile reading
        *74 units* and the table under it disagree the moment a plan passes one
        page, which is the failure `PRB-21` names in its own sentence;
      · nothing caps the set. A plan on a 40,000-unit tenant costs the same
        request as a plan on three (`NFR-5` — no hard cap anywhere, and no
        maximum that would have to be removed when T4 arrives).

    **CURRENT means `assigned_to IS NULL`**, the same predicate
    `_plan_accounts_subquery` counts with, so this list and the count on the
    tile can never mean two different things. `unit_plan_assignments` is
    append-only history: a closed row is where a unit USED to be.

    Ordered by premises then unit label — the blueprint's own *"sorted by
    premises so the units of one building sit together"* — with the row id last
    as `IS-2`'s stable secondary sort, so paging cannot show one unit twice and
    skip another.
    """
    if not _valid_uuid(plan_id):
        return models.UnitPlanAssignment.objects.none()
    return (
        models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=plan_id, assigned_to__isnull=True
        )
        .select_related("unit")
        .order_by("unit__premises__address_line", "unit__label", "id")
    )


def plan_unit_rows(assignments: list[Any]) -> list[dict[str, Any]]:
    """ONE PAGE of assignments, enriched into the rows the Units tab draws.

    `PRB-21`, and the PO of 2026-09-08: *"second tab can be units"*. The plan
    counted 74 and never said 74 of WHAT; a plan attaches to a UNIT, so it is
    units.

    ⚠ **IT TAKES THE PAGE, NOT THE PLAN.** The caller has already paged in SQL;
    handing this a plan id would mean deciding the paging a second time, in a
    second place, and the two would drift. It is also why the cross-module read
    below is bounded by construction rather than by a limit somebody remembered.

    ── WHAT EACH COLUMN IS, AND WHY ─────────────────────────────────────────
    **`unit_label` + `premises_address`** — two different facts. A unit refines
    a premises by LABEL (CLAUDE.md hard rule 8), so the address is the PREMISES'
    own, walked, and no unit carries a copy of one.

    **`services`** — service CODES, so the screen draws the coloured badge the
    product already ships. Never spelled-out names: six of the eleven services
    collide on their initial, so the letter cannot be derived from the name and
    the screen's own map is the only place that decides it.

    **`account_no` + `vacant`** — the row this tab exists for. A vacant unit has
    no account, no customer and a base charge that STILL reaches the owner's
    bill, so `vacant` is served as its own boolean and the screen states what it
    means. A clerk who reads a blank Account cell concludes nothing is billed,
    which is the opposite of the truth.

    **`account_closed`** — served with the number rather than as a blank,
    because *closed* and *never had one* are different facts about a bill.

    ⚠ **NO DATABASE ID IS A VISIBLE VALUE** (B14 rule 31). `unit_id` travels so
    a screen can key a row and link to the unit; every column a clerk READS is a
    name, a label or an address.
    """
    if not assignments:
        return []
    facts = seams.plan_unit_facts([row.unit_id for row in assignments])
    rows: list[dict[str, Any]] = []
    for row in assignments:
        fact = facts.get(str(row.unit_id), {})
        account_no = fact.get("account_no")
        rows.append(
            {
                "unit_id": str(row.unit_id),
                "unit_label": fact.get("label"),
                "unit_no": fact.get("unit_no"),
                "premises_address": fact.get("premises_address"),
                "premises_city": fact.get("premises_city"),
                # `DEF-RAT-9353` (CR-167 r3 task 7, ruling 13: every name is a
                # link) — the premises and the account a row LINKS to. Keys for
                # an address, never a visible value (B14 rule 31).
                "premises_id": str(fact["premises_id"]) if fact.get("premises_id") else None,
                "account_id": str(fact["account_id"]) if fact.get("account_id") else None,
                "services": fact.get("services", []),
                "account_no": account_no,
                "account_closed": bool(fact.get("account_closed")),
                #: NOT `account_no is None` computed on the screen: the SAME
                #: absence has to mean the same thing on the tile, in the list
                #: and in a future report, and a boolean served once is how it
                #: can (`DEF-CUS-3653`'s lesson — an absence is invisible to
                #: every check this repo has).
                #: `DEF-RAT-9361` — vacant = no OPEN account, the definition
                #: the occupancy filter's sub-select uses
                #: (`seams.ACCOUNT_CLOSED_CLASS`); a closed account is still
                #: named, with `account_closed`.
                "vacant": account_no is None or bool(fact.get("account_closed")),
                # `CR-167-BRC10` §7.3 — the customer by NAME (B14 rule 31).
                "customer_name": fact.get("customer_name"),
                "assigned_from": row.assigned_from,
            }
        )
    return rows


# ── A PLAN IS TOLD WHEN WHAT IT BINDS CHANGES (PO ruling 2026-09-18) ─────────
#
# PO, verbatim: *"yes we should build this. It measn every time Rate, taxes,
# Charge code, Discounts are changed, at apporval we need to take action to
# inform Plan about it - Fix this"*.
#
# ⚠ **THE VIEW IS DERIVED AND NEVER STORED, WHICH IS THE WHOLE DESIGN.**
# `rate_change_log` already carries `entity_type`, `entity_id`, `before`,
# `after`, `reason`, the actor and the timestamp. A derived view is right by
# construction; a copied one is right only until something fails to copy, and a
# push that fails to fire is invisible for ever (hard-won law 2's shape).
#
# ⚠ **AND IT CAN ANSWER FOR TWO OF THE FOUR KINDS THE PO NAMED. THAT IS STATED
# HERE, COUNTED IN THE PAYLOAD AND SAID ON THE SCREEN — `DEF-RAT-5738`.** Only
# three entity types are ever written to that table from anywhere in this
# module: `schedule`, `charge` and `plan`. **No tax path and no discount path
# writes one** — not `update_tax`, not `correct_tax`, not any discount service;
# the literal set in the module is exhaustive. So a tax that moved yesterday
# leaves nothing for this to find, and a view that simply showed an empty list
# would be truthful about what it can see and FALSE ABOUT THE WORLD. That is
# hard-won law 7's *reporting zero over a scope it silently excludes*, and the
# cure that law prescribes is the one taken here: **print what was skipped
# beside what was checked.**

#: The `entity_type` values this view can actually resolve, and the ones it
#: cannot. Served to the client rather than hardcoded on the screen, so the day
#: `DEF-RAT-5738` is fixed the sentence disappears on its own instead of being
#: a second place somebody has to remember.
BOUND_CHANGE_KINDS_COVERED = ("schedule", "charge")
BOUND_CHANGE_KINDS_UNCOVERED = ("tax", "discount")


def plan_bound_entity_ids(plan: models.RatePlan) -> dict[str, list[Any]]:
    """The ids of the priced objects this plan BINDS, by `rate_change_log` kind.

    ⚠ **A `schedule` ROW CARRIES THE TARIFF's ID, NOT A VERSION's** — checked
    against all three writers rather than assumed, because a version id here
    would match nothing and the view would be silently empty rather than wrong,
    which is the harder failure to notice.

    The charge set is BOTH doors a plan has onto the catalogue: the codes
    attached through `PlanChargeRule`, and the late-fee code the plan names
    directly (`BR-RAT-1011`). Reading only the first would miss the one charge
    code every plan has.
    """
    tenant = _tenant_id()
    schedules = list(
        models.PlanRateSchedule.objects.filter(tenant_id=tenant, rate_plan=plan)
        .values_list("tariff_id", flat=True)
        .distinct()
    )
    charges = list(
        models.PlanChargeRule.objects.filter(tenant_id=tenant, rate_plan=plan)
        .values_list("charge_id", flat=True)
        .distinct()
    )
    if plan.late_fee_charge_id is not None and plan.late_fee_charge_id not in charges:
        charges.append(plan.late_fee_charge_id)
    return {"schedule": schedules, "charge": charges}


def plan_bound_changes_queryset(plan_id: Any) -> QuerySet:
    """Every recorded change to something this plan binds, NEWEST FIRST.

    ⚠ **A QUERYSET, DELIBERATELY — `NFR-3` AND `NFR-5`.** The paginator is
    handed the queryset, so the count is a SQL `COUNT` over the whole set and
    the page is a SQL `LIMIT`/`OFFSET`. A change to ONE tax or ONE charge code
    reaches EVERY plan that binds it, so this set grows with the estate and not
    with the plan — the exact shape that is correct at T7 and 13× short at T5.
    Nothing here caps it and nothing loops per plan.

    ⚠ **IT EXCLUDES `entity_type='plan'`, AND THAT IS NOT AN OVERSIGHT.** A
    change to the PLAN is the Audit tab's subject and it is already drawn there
    in full. This view answers the other question — *what moved underneath me* —
    and folding the two together would make a plan's own edits drown the one
    signal it was built to carry.

    A plan that binds nothing returns an EMPTY queryset rather than the whole
    tenant's log: `entity_id__in=[]` is the safe form, and building the filter
    from an empty pair list without it would match every row.
    """
    plan = plan_or_404(plan_id)
    bound = plan_bound_entity_ids(plan)
    predicate = Q(pk__in=[])  # matches nothing — the honest empty, never "all"
    for kind in BOUND_CHANGE_KINDS_COVERED:
        ids = bound.get(kind) or []
        if ids:
            predicate = predicate | Q(entity_type=kind, entity_id__in=ids)
    return (
        models.RateChangeLog.objects.filter(tenant_id=_tenant_id())
        .filter(predicate)
        # `-id` is IS-2's stable secondary: two rows written in one batch share
        # a timestamp, and without it a page boundary can show one row twice.
        .order_by("-created_at", "-id")
    )


def plan_bound_change_rows(entries: list[Any]) -> list[dict[str, Any]]:
    """One page of `plan_bound_changes_queryset`, as a screen reads it.

    ⚠ **IT NAMES THE OBJECT, NEVER ITS ID** (B14 rule 31). `entity_name` is
    lifted from the snapshot the log already stored — `after` first, because the
    current name is what a clerk is looking for — so no join is needed and a row
    whose object has since been renamed still reads as it did when it changed.
    `entity_id` travels so a screen can link, and is never a visible value.

    ⚠ **NO MONEY IS RECOMPUTED ON THE WAY TO THE SCREEN.** `before` and `after`
    are handed over exactly as stored, at the precision they were stored with
    (hard rule 2 — 4 places for money, 6 for a percentage, and the DISPLAY
    decision belongs to the screen, never to a record).
    """
    if not entries:
        return []
    names = seams.user_display_names([entry.actor_id for entry in entries])
    return [
        {
            "id": str(entry.id),
            "changed_at": entry.created_at.isoformat() if entry.created_at else None,
            "entity_type": entry.entity_type,
            "entity_id": str(entry.entity_id),
            "entity_name": (entry.after or entry.before or {}).get("name"),
            "before": entry.before,
            "after": entry.after,
            #: AUTHORED — the operator's own sentence about why. Required on
            #: every writer, so an absence here means the row predates the rule
            #: rather than that nobody had a reason.
            "reason": entry.reason,
            #: DEF-367 — `{id, name}`, so a person is never a uuid on a screen.
            "actor": _actor_ref(entry.actor_id, names),
            "batch_id": _uuid_or_none(entry.batch_id),
        }
        for entry in entries
    ]


def plan_bound_change_coverage() -> dict[str, Any]:
    """WHAT THIS VIEW CANNOT SEE, served as data beside what it can.

    ⚠ **A DECLARED BLIND SPOT WITH NO NUMBER ATTACHED IS INDISTINGUISHABLE FROM
    AN EMPTY ONE** (hard-won law 7, `G32`'s own lesson: it reported 0 unresolved,
    truthfully, over 21 live refusals it could not see). So the answer carries
    the kinds it resolved AND the kinds it could not, by name, and the screen
    says so where a clerk reads it — rather than drawing an empty tax section
    that looks like good news.

    It is DATA and not a sentence on the server, because the day `DEF-RAT-5738`
    is fixed the uncovered list becomes empty and the screen stops saying
    anything, with nobody having to remember to delete a string.
    """
    return {
        "covered": list(BOUND_CHANGE_KINDS_COVERED),
        "uncovered": list(BOUND_CHANGE_KINDS_UNCOVERED),
        "uncovered_defect": "DEF-RAT-5738",
    }


def plan_discount_rules(plan: models.RatePlan, as_of: date | None = None) -> list[dict[str, Any]]:
    """What this plan OFFERS — BR-RAT-110, PLN-03 step 6 / PLN-02's Discounts tab.

    ⚠ **AND, SINCE CR-034 §7's AMENDMENT, WHAT A CUSTOMER MUST SATISFY TO AVAIL
    IT** — `terms`, see `_discount_terms`. The PO, verbatim 2026-08-26: *"We
    should show all discount plan offer and what condition are required to avail
    that discount"*. Additive: every key that was here keeps its name and its
    meaning.

    `as_of` is BR-RAT-007's service date, and it resolves the VERSION whose
    numbers and conditions are served. It defaults to `None`, which resolves
    exactly what this selector always resolved (the tenant's today) — the same
    posture `schedule_detail` took for the same reason on this same CR.

    ⚠ **`enrolled` IS THE OTHER GATE AND IT IS SERVED BESIDE THE OFFER ON
    PURPOSE** (BR-RAT-069). Binding a discount to a plan grants it to nobody: a
    bill run reads `discount_enrolments`. The two numbers sit in one row so the
    difference is visible on the screen where an operator is binding —
    *available* on the left, *how many accounts actually receive it* on the
    right. A screen that showed only the binding would let a reader conclude the
    plan discounts its 842 accounts, and it discounts 0 of them.

    ⚠ **NO VALUE IS SERVED FROM THE RULE ROW because the row has none.** The
    figure shown is the DISCOUNT's own, through `discount_value_display` —
    `value_display`, never `value`, because `discount_versions.value` stores
    percentage POINTS and rendering `15` through a fraction formatter prints
    `1500.00%`.

    ⚠ **`enrolled` IS TENANT-WIDE, NOT PLAN-SCOPED**, and the field name says
    `enrolled` rather than `enrolled_on_this_plan` for that reason.
    `discount_enrolments.account_id` is a deferred FK into the CUSTOMERS module
    (B2 §2), so rating cannot ask which plan an account is on without a seam
    that does not exist. It is the same number `DiscountRow.enrolled` serves on
    DIS-01, which is why the two screens agree.
    """
    resolved_on = as_of or seams.tenant_today()
    # ⚖️ PO ruling 2026-10-03 (2), closing `OQ-322`: taking a discount off a
    # plan ENDS its binding the day before (`services._close_dropped_discounts`)
    # rather than deleting it, so a past bill still finds it. An ENDED binding
    # is history: it is not what the plan offers, and serving it here would put
    # it back on the wizard's step 6 and re-post it on the next save.
    rules = (
        discount_models.PlanDiscountRule.objects.filter(tenant_id=_tenant_id(), rate_plan=plan)
        .filter(Q(available_to__isnull=True) | Q(available_to__gte=resolved_on))
        .select_related("discount")
        .order_by("discount__code")
    )
    out: list[dict[str, Any]] = []
    for rule in rules:
        version = discount_version_in_force(rule.discount, as_of)
        out.append(
            {
                "id": str(rule.id),
                "discount_id": str(rule.discount_id),
                "code": rule.discount.code,
                "name": rule.discount.name,
                "status": rule.discount.status,
                "type": version.discount_type if version else None,
                # BR-RAT-087 — the string a screen prints, never the stored value.
                # BR-RAT-960 — and an allowance carries the unit it resolved to,
                # HERE TOO. This is the plan's Discounts tab, so a clerk binding
                # a programme to a plan reads `2.00 kgal` and not a bare `2.00`;
                # serving the unit on one screen and not the other is how the
                # same figure comes to mean two things.
                "value_display": discount_value_display(
                    version.discount_type if version else None,
                    version.value if version else None,
                    discount_allowance_unit(version),
                    version.currency if version else None,
                ),
                "eligibility": version.eligibility_summary if version else None,
                # ── CR-034 §7 (PO 2026-08-26) · THE CONDITIONS TO AVAIL IT ──
                # `null` when this discount has no version at all — a discount
                # nobody has filled in states no conditions, which is a
                # different fact from stating none. See `_discount_terms`.
                "terms": _discount_terms(version, resolved_on),
                # ⚠ AVAILABILITY dates — when THIS PLAN offers it. Null means
                # "for as long as the discount itself is available"; it is not
                # the discount's own effective window and must never be printed
                # as one.
                "available_from": (
                    rule.available_from.isoformat() if rule.available_from else None
                ),
                "available_to": (rule.available_to.isoformat() if rule.available_to else None),
                # ⚠ THE GRANT (BR-RAT-069) — the only one of these numbers that
                # reduces a bill. Since the PO's ruling of 2026-10-03 (`OQ-322`
                # CLOSED) a non-zero count no longer blocks taking the discount
                # off the plan: those enrolments end the day before.
                "enrolled": discount_enrolled_count(rule.discount),
            }
        )
    return out


def _discount_terms(version: Any, resolved_on: date) -> dict[str, Any] | None:
    """WHAT A CUSTOMER MUST SATISFY TO AVAIL THIS DISCOUNT — CR-034 §7, amended
    2026-08-26 by the PO: *"We should show all discount plan offer and what
    condition are required to avail that discount ; when account is attached it
    will avail those discounts"*.

    ⚠ **THE CONDITIONS ARE STORED, AND THEY ARE NOT `rate_plans.eligibility`.**
    The plan's own `eligibility` jsonb is a different object one level up, and
    every field below belongs to the DISCOUNT VERSION — the row an operator
    filled in on DIS-02 steps 2 and 3. Nothing here is derived, defaulted or
    inferred: each key is one stored column, forwarded.

    ⚠ **AND ONE OF THEM IS NOT A CONDITION, WHICH IS WHY IT IS NOT SERVED AS
    ONE.** `eligibility_rule` is the DIS-02 rule builder's document and
    **nothing in this product evaluates it** (`discounts.py`'s own note, and
    `discount_services`' *"It does not evaluate eligibility"*). Rendering it as
    a checked condition would tell a clerk the product enforces something it
    does not — the expensive direction of wrong. So this serves whether a rule
    was RECORDED (`eligibility_rule_recorded`) and states the evaluation as an
    absence beside it; the sentence a human wrote (`eligibility_summary`) is
    what the screen shows, and it is a description, never a gate.

    ⚠ **NO PROGRAMME-WIDE FIGURE IS SERVED — no `budget_cap`, no `enrolled`.**
    Both are TENANT-WIDE and a number rendered on a UNIT screen is read as that
    unit's however the caption is worded (`_offered_discounts`' own reasoning
    one module over, and the reason rating's `enrolled` count is dropped rather
    than labelled). The caps below are different: `cap_per_bill` and its
    siblings are limits on THIS customer's own reduction, which is exactly the
    condition a person reading a discount needs.

    Money is served as the DISPLAY string only (hard rule 2: stored 4/6, both
    DISPLAY 2) beside its `CHAR(3)` currency, the same posture `value_display`
    takes — and a client that never receives a six-place figure cannot do
    arithmetic on one.
    """
    if version is None:
        return None
    service = version.applies_to_service if version.applies_to_service_id else None
    return {
        #: WHICH filing these terms come from, so a reader can tell that a
        #: discount whose value changed on Jan 1 has different conditions too.
        "version_no": version.version_no,
        "version_status": version.status,
        "effective_from": (version.effective_from.isoformat() if version.effective_from else None),
        "effective_to": version.effective_to.isoformat() if version.effective_to else None,
        #: The date this version was resolved on — BR-RAT-007's service date
        #: when a caller stated a period, the tenant's today otherwise.
        "resolved_on": resolved_on.isoformat(),
        # ── who qualifies ───────────────────────────────────────────────────
        #: The plain-English sentence a human wrote (r10's `Age 65+`). A
        #: DESCRIPTION of the condition, not the condition itself.
        "eligibility_summary": version.eligibility_summary,
        "eligibility_rule_recorded": version.eligibility_rule is not None,
        #: ⛔ NOT BUILT — and it is stated rather than implied, because a
        #: screen that lists conditions has to say whether anything checks
        #: them. `eligibility_rule` is ADVISORY: stored as authored, read by
        #: nobody. Automatic evaluation is EP-RAT-12's remainder.
        "eligibility_checked": {
            "served": False,
            "reason": "no_code_evaluates_a_discount_eligibility_rule",
            "tracks": None,
        },
        # ── how it is obtained, and what proof it takes ─────────────────────
        "enrolment_mode": version.enrolment_mode,
        "verification_method": version.verification_method,
        "proof_required": version.proof_required,
        #: The accepted document kinds. An EMPTY list is *"the programme states
        #: none"*, which `_validate_version` only allows beside
        #: `proof_required: false` — the two are one fact read together.
        "accepted_proof_kinds": list(version.accepted_proof_kinds or []),
        #: A MONEY rule, not a formality: TRUE means an unverified enrolment
        #: reduces nothing, FALSE means the reduction starts and the proof is
        #: chased.
        "proof_before_first_reduction": version.proof_before_first_reduction,
        # ── how it is KEPT once granted ─────────────────────────────────────
        "recertification_months": version.recertification_months,
        "recertification_notice_days": version.recertification_notice_days,
        "recertification_grace_days": version.recertification_grace_days,
        "lapse_behaviour": version.lapse_behaviour,
        # ── what it reduces, and by how much at most ────────────────────────
        "applies_to": version.applies_to,
        "applies_to_service": service.code if service is not None else None,
        "applies_to_service_name": service.name if service is not None else None,
        "applies_to_charge_codes": list(version.applies_to_charge_codes or []),
        "currency": version.currency,
        #: NULL is UNCAPPED and stays null — a decision the operator can see,
        #: never a `0.00`, which would say the discount reduces nothing.
        "cap_per_bill_display": _display_money(version.cap_per_bill),
        "cap_per_year_display": _display_money(version.cap_per_year),
        "cap_lifetime_display": _display_money(version.cap_lifetime),
        #: BR-RAT-074. The default is `0.000000` and that is the whole of the
        #: *"unless allowed"*: a discount may take a bill to zero and never
        #: below, because a negative bill is a CREDIT — a different object with
        #: a different ledger posting.
        "bill_floor_amount_display": _display_money(version.bill_floor_amount),
        # ── whether it can be had alongside another ─────────────────────────
        "stacks_with_others": version.stacks_with_others,
        #: r10's SENIOR detail, verbatim: *"Not with CAP credit · One assistance
        #: program per account — the larger applies."* Two discounts sharing a
        #: group are mutually exclusive on one account.
        "exclusivity_group": version.exclusivity_group,
        #: BR-RAT-073 — order is DATA, lowest applies first. Served because
        #: *"percentage-of-usage after a usage allowance gives a different
        #: number than the reverse"*, so which discount goes first is part of
        #: what a customer gets.
        "stacking_precedence": version.stacking_precedence,
    }


def plan_versions(plan: models.RatePlan) -> list[dict[str, Any]]:
    """The plan's filing record, NEWEST FIRST — BR-RAT-111, PLN-02's Versions tab.

    Descending because §10 requires it of every one of the five Versions tabs
    (*"ordered by effective date descending, not by status"*) and because the
    question a person opens this tab with is *"what changed last"*.

    ⚠ **`changes` IS COMPUTED HERE AND NOT STORED**, which is the opposite of
    `change_reason`. The reason is AUTHORED — a human's sentence about why —
    and the diff is DERIVED from two snapshots that are already on disk. Storing
    a derived diff would create a second copy free to disagree with the
    snapshots it summarises (hard-won law 5's shape).

    ⚠ **THE DIFF IS COMPONENT-LEVEL, WHICH IS WHAT CR-013 PART 5 ASKED FOR** —
    *"Versions with component-level diff"*. It names the PATH that moved and
    both values (`services.water.base_charge 8.000000 → 9.500000`), so a reader
    can act on it. It does not attempt a prose sentence; that is what
    `change_reason` is.

    ⚠ **A PLAN WITH NO ROWS IS NORMAL AND MUST NOT READ AS "NOTHING EVER
    CHANGED".** `plan_versions` is not backfilled — the same posture migration
    0019 took for the schedule's three filing columns, and for the same reason:
    a backfill would have to invent a submitter and a snapshot for a version
    written before the table existed. Every plan on disk before 2026-08-21
    therefore has an empty history until its next publish or change, and the
    screen states that rather than drawing an empty table.
    """
    rows = list(
        # `BR-RAT-1066` — a DRAFT version row (a draft plan's v1, or a saved new
        # version not yet published) is not a filing; `plan_reads` lists it.
        models.PlanVersion.objects.filter(tenant_id=_tenant_id(), rate_plan=plan)
        .exclude(status="draft")
        .order_by(
            # ── `OQ-RAT-12409` OPTION A — WHY THERE IS A SECOND SORT KEY ─────
            # `-version_no` alone was TOTAL until migration 0036, because the
            # unique key made one row per number. A correction is a second row
            # carrying the SAME `version_no`, so on its own `-version_no` now
            # leaves the pair in whatever order the database returns them — and
            # this function's diff reads `rows[index + 1]` as "the previous
            # row", so an unstable order does not merely reorder the table, it
            # inverts the arithmetic under it and prints the correction's own
            # fix backwards.
            #
            # `-created_at` puts the CORRECTION directly above the row it
            # corrects, which is what makes `rows[index + 1]` go on meaning
            # "what this row changed" for a correction as it already did for a
            # version. `-id` is IS-2's stable tie-break beneath both, because
            # two rows written in one transaction can share a timestamp.
            "-version_no",
            "-created_at",
            "-id",
        )
    )
    names = seams.user_display_names(
        # `corrected_by` is the THIRD person this table can name (`rating/0036`),
        # and it is batched with the other two rather than resolved per row —
        # `version_row` takes the same posture for the same reason.
        [row.submitted_by_id for row in rows] + [row.corrected_by_id for row in rows]
    )
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        # The NEXT row in a descending list is the PREVIOUS version, so the diff
        # on each line answers "what did this version change", which is the
        # question the row is read for. The oldest row has no predecessor and
        # carries no diff — an empty list, never a made-up one.
        #
        # ⚠ **AND FOR A CORRECTION IT ANSWERS A DIFFERENT QUESTION IN THE SAME
        # ARITHMETIC: *what did this correction FIX*.** The row beneath a
        # correction is the row it corrects — guaranteed by the sort above, not
        # hoped for — so the same subtraction names the leaf that was recorded
        # wrongly. The screen labels it as a fix rather than as a change, which
        # is `corrects` below doing that job; the numbers are the same numbers.
        previous = rows[index + 1].snapshot if index + 1 < len(rows) else None
        out.append(
            {
                "id": str(row.id),
                "version_no": row.version_no,
                # ⚠ NO `version_label`. `09-screen-inventory.md` §10: *"Do not
                # normalise the other four up to seven columns — a discount has
                # no docket"*, and neither does a plan. `FILED AS` is the rate
                # schedule's alone.
                "change_reason": row.change_reason,
                # DEF-367's `{id, name}`, batched — the same shape
                # `apps/audit/selectors` and `version_row` serve, so a person is
                # never a uuid on a screen.
                "submitted_by": _actor_ref(row.submitted_by_id, names),
                "created_at": row.created_at.isoformat(),
                "changes": _plan_snapshot_diff(previous, row.snapshot),
                # ── `OQ-RAT-12409` OPTION A · `BR-RAT-1016` VERB 2 ───────────
                # ⚠ **ALL FOUR, SO A SCREEN CAN TELL THREE STATES APART WITHOUT
                # A SECOND REQUEST** — `version_row`'s own words for the same
                # four columns on a tariff version, and the sameness is the
                # point (`BR-RAT-1016`: one rule, one shape, five objects).
                # The three states are: a plain version; a version that HAS
                # been corrected, which no longer states what the plan says;
                # and the correction that restated it.
                #
                # ⚠ **SERVING ONLY `correction_reason` WOULD LEAVE A SUPERSEDED
                # ROW LOOKING LIVE**, which is the exact misreading this whole
                # question was raised about — two rows at `v1`, one of them
                # wrong, and nothing on screen saying which.
                "corrects": str(row.corrects_id) if row.corrects_id else None,
                "superseded_by": (
                    str(row.superseded_by_id) if row.superseded_by_id else None
                ),
                "correction_reason": row.correction_reason,
                "corrected_by": _actor_ref(row.corrected_by_id, names),
            }
        )
    return out


#: How many changed components one version row carries before the rest are
#: counted rather than listed. A plan re-posted through the wizard can touch
#: dozens of leaves at once, and a cell holding forty paths is a cell nobody
#: reads — the same judgement `BLOCKING_PLAN_NAMES_SHOWN` makes above, and the
#: count travels beside the list so the number stays true.
PLAN_VERSION_CHANGES_SHOWN = 8


def _plan_snapshot_diff(before: Any, after: Any) -> dict[str, Any]:
    """Component-level diff of two `_plan_snapshot` blobs — CR-013 part 5.

    Returns `{"fields": [{path, before, after}], "total": n}` where `total` is
    the number of changed leaves and `fields` is the first
    `PLAN_VERSION_CHANGES_SHOWN` of them. `before` of `None` means there is no
    predecessor, which is the oldest recorded version, and it yields no fields
    rather than reporting the whole plan as new — the row already says it is the
    first one recorded.

    Leaves are compared as the JSON blob holds them, so money arrives as the
    six-place decimal STRING it was stored as and nothing here parses it into a
    number. A diff that re-formatted `8.000000` to `8.00` would be making a
    display decision inside a record.
    """
    fields: list[dict[str, Any]] = []
    if before is None:
        return {"fields": fields, "total": 0}

    def walk(prefix: str, old: Any, new: Any) -> None:
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(set(old) | set(new)):
                walk(f"{prefix}.{key}" if prefix else str(key), old.get(key), new.get(key))
            return
        if isinstance(old, list) and isinstance(new, list):
            # Child sets are REPLACED wholesale by `_apply_plan_children`, so
            # index-wise comparison is what the write path actually does. A
            # key-wise match would invent an identity the writer does not use
            # and would report a reorder as a change of content.
            for index in range(max(len(old), len(new))):
                walk(
                    f"{prefix}[{index}]",
                    old[index] if index < len(old) else None,
                    new[index] if index < len(new) else None,
                )
            return
        if old != new:
            fields.append({"path": prefix, "before": old, "after": new})

    # `DEF-RAT-10031` — the copy's schema flag is not plan content.
    flag = plan_versioning.TERMS_RECORDED_KEY
    walk(
        "",
        {k: v for k, v in before.items() if k != flag} if isinstance(before, dict) else before,
        {k: v for k, v in after.items() if k != flag} if isinstance(after, dict) else after,
    )
    return {"fields": fields[:PLAN_VERSION_CHANGES_SHOWN], "total": len(fields)}


def plan_or_404(plan_id: Any) -> models.RatePlan:
    """Current-tenant row or 404 — a cross-tenant id is ABSENT here, so the
    body equals a plain not-found (HR-1/G4)."""
    if not _valid_uuid(plan_id):
        raise errors.NotFoundError()
    plan = plan_queryset().filter(pk=plan_id).first()
    if plan is None:
        raise errors.NotFoundError()
    return plan


def plan_account_count(plan: models.RatePlan) -> int:
    """BR-RAT-030/IS-1 input: units currently assigned to the plan."""
    return models.UnitPlanAssignment.objects.filter(
        rate_plan=plan, assigned_to__isnull=True, tenant_id=_tenant_id()
    ).count()


# ── Rate schedules (US-RAT-004..007) ────────────────────────────────────────
def tariff_or_404(tariff_id: Any) -> models.Tariff:
    if not _valid_uuid(tariff_id):
        raise errors.NotFoundError()
    row = models.Tariff.objects.filter(tenant_id=_tenant_id(), pk=tariff_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def tariff_version_labels(version_ids: Any) -> dict[str, str]:
    """`{version id: "Sample — Water (Residential) · from 2026-06-01"}`.

    ⚠ **PUBLISHED FOR DEF-937 (CR-043 finding 3, PO 2026-08-27).** The bill's
    Charges tab printed a raw uuid in a column headed RATE VERSION, on every
    line of every bill, and DEF-206's rule is one sentence: never print the raw
    key at a person. `apps/billing/selectors.invoice_line_row` served
    `tariff_version_label: None` under the comment *"rating stores no version
    LABEL: a `tariff_versions` row carries dates and a model, and no column an
    ordinal 'v3' could honestly be read from"*.

    **THAT COMMENT IS STILL TRUE AND ITS CONCLUSION DOES NOT FOLLOW.** There is
    no ordinal — and there is no need for one. BR-RAT-007 identifies the version
    that priced a bill by exactly two facts: WHICH SCHEDULE and WHEN IT TOOK
    EFFECT. Both are columns on the row. So the label is built from what the
    database actually holds rather than from an ordinal nobody stores, and no
    "v3" is invented.

    **WHAT IT DELIBERATELY DOES NOT SAY.** No "current"/"superseded" word: that
    is a fact about TODAY and this column is about the version that priced a
    bill possibly years ago, so a pill saying "superseded" would read as a
    warning about the bill. `schedule_state` is where liveness is answered.

    A dateless row is BR-RAT-031's resumable DRAFT and can never have priced
    anything, so it labels as the schedule name alone — visible rather than
    hidden, because a bill line pointing at a draft version is a defect somebody
    needs to see.

    Ids belonging to another tenant are simply absent from the result: the
    queryset is tenant-scoped (hard rule 1) and the caller falls back to the id.
    """
    wanted = {str(one) for one in (version_ids or ()) if one}
    if not wanted:
        return {}
    rows = models.TariffVersion.objects.filter(
        tenant_id=_tenant_id(), id__in=wanted
    ).select_related("tariff")
    labels: dict[str, str] = {}
    for row in rows:
        name = getattr(row.tariff, "name", None) or str(row.tariff_id)
        labels[str(row.id)] = (
            f"{name} · from {row.effective_from.isoformat()}"
            if row.effective_from is not None
            else name
        )
    return labels


def tariff_version_effective_from(version_ids: Any) -> dict[str, str]:
    """`{version id: "2026-07-16"}` — the day each version took effect.

    `DEF-BIL-8316` (2026-09-30): the one-time bill's Rates table draws a SHORT
    price-version cell (the service and when its prices started), where
    `tariff_version_labels` answers the schedule's long name. No ordinal is
    invented (that function's docstring says why there is none to read); the
    screen composes the short cell from the service and this date. A dateless
    draft version is absent. Tenant-scoped (hard rule 1).
    """
    wanted = {str(one) for one in (version_ids or ()) if one}
    if not wanted:
        return {}
    return {
        str(version_id): effective_from.isoformat()
        for version_id, effective_from in models.TariffVersion.objects.filter(
            tenant_id=_tenant_id(), id__in=wanted, effective_from__isnull=False
        ).values_list("id", "effective_from")
    }


def version_or_404(tariff: models.Tariff, version_id: Any) -> models.TariffVersion:
    """One version OF THIS TARIFF, or 404 — never a version of another schedule
    and never one of another tenant (hard rule 1; the filter names both)."""
    if not _valid_uuid(version_id):
        raise errors.NotFoundError()
    row = models.TariffVersion.objects.filter(
        tenant_id=_tenant_id(), tariff=tariff, pk=version_id
    ).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def version_issued_bill_count(version: models.TariffVersion) -> int | None:
    """DEF-RAT-5715 · **HOW MANY BILLS THIS VERSION HAS ALREADY PRICED.**

    ⚠ **THIS IS THE PRECISE TEST AND NOT THE CONSERVATIVE ONE, AND THE
    DIFFERENCE WAS MEASURED RATHER THAN ASSUMED (2026-09-17).** The obvious
    safe answer is *"any issued invoice whose period overlaps this window"*,
    which refuses more often than it needs to. The precise answer reads the
    stamp `DEF-276` put on every priced line — and hard-won law 1 says a
    docstring claiming a stamp is not the stamp, so it was read back off a real
    tenant before this function was written: **92 issued invoices, 732 lines,
    456/456 `usage` lines and 184/184 `base` lines carrying
    `tariff_version_id`, 0 orphans.** The 92 lines without one are `tax` lines,
    which are priced by a tax and not by a rate schedule version — an absence
    that is correct rather than missing.

    ⚠ **IT COUNTS INVOICES, NOT LINES.** A tiered bill has one line per block,
    so a line count would tell an operator that correcting one month of one
    schedule touches three times as many customers as it does.

    The statuses are the ISSUED ones: a draft bill has not reached anybody and
    is re-priced by the next run, so counting it would overstate what a
    correction cannot undo (hard rule 4 — bills lock at issue).
    """
    return seams.tariff_version_issued_bills(version.id)


def activated_versions(tariff: models.Tariff) -> QuerySet:
    """Every version that HAS left draft. BR-RAT-031: a version with no
    effective_from is the resumable draft — it is not history, it has never
    been in force, and no read path below may treat it as either.

    ⚠ **A SUPERSEDED ROW IS STILL HISTORY AND IS STILL RETURNED HERE.** It is
    excluded from PRICING by `in_force_version` alone (DEF-RAT-5715). The two
    are different questions: *"what does a regulator see when they ask what this
    schedule has ever said"* keeps the corrected row for ever — that is the whole
    of BR-RAT-104 — while *"what prices this service date"* must answer with the
    correction. A filter here would take the corrected row off the filings table
    and out of the history a bill issued under it is reproduced from
    (BR-RAT-017's seven years).
    """
    return models.TariffVersion.objects.filter(
        tenant_id=_tenant_id(), tariff=tariff, effective_from__isnull=False
    )


def tariff_versions(tariff: models.Tariff) -> list[models.TariffVersion]:
    """The version HISTORY (activated only — the draft is `draft_version`)."""
    return list(activated_versions(tariff).order_by("effective_from", "created_at"))


def draft_version(tariff: models.Tariff) -> models.TariffVersion | None:
    """BR-RAT-031 save-draft resumable: THE draft — the one dateless version
    row (uq_tariff_versions_one_draft) whose structure children reload as-is."""
    return (
        models.TariffVersion.objects.filter(
            tenant_id=_tenant_id(), tariff=tariff, effective_from__isnull=True
        )
        .order_by("created_at")
        .first()
    )


def _in_force_candidates(tariff: models.Tariff, service_date: date) -> QuerySet:
    """BR-RAT-007: the versions whose window contains the SERVICE date, never
    the current one. The W3 engine consumes this — it does not re-derive it.
    Drafts are excluded explicitly (BR-RAT-031): a dateless row has no window
    and must never price anything."""
    return (
        activated_versions(tariff)
        .filter(effective_from__lte=service_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=service_date))
        # ⚠ DEF-RAT-5715 — **A CORRECTED ROW STOPS PRICING, AND THIS ONE LINE IS
        # THE WHOLE MECHANISM.** BR-RAT-104: a correction restates the SAME
        # window, so for any date in that window there are now TWO rows whose
        # window contains it. Without this filter the order-by decides which one
        # prices — by `effective_from`, which is IDENTICAL on both — so the
        # answer would be whichever the database happened to return first. That
        # is not a tie-break, it is a coin toss on a money path.
        # The corrected row keeps its rate, its dates and its trail and stays in
        # `activated_versions`; it simply stops being the answer to *"what prices
        # this date"*, which is exactly what `Tax.superseded_by` means on the
        # other object this rule governs.
        .filter(superseded_by__isnull=True)
    )


def in_force_versions(tariff: models.Tariff, service_date: date) -> list[models.TariffVersion]:
    """🔒 HUMAN-REVIEW-PENDING · `BR-RAT-1055` — EVERY live version of this
    schedule whose window contains the SERVICE date, **the one that prices
    FIRST**, ordered by `resolution.in_force_precedence`.

    One row on every schedule written since `rating/0047` — the database
    refuses a second in-force window at COMMIT. More than one is a LEGACY
    overlap written before that constraint (`DEF-RAT-8004`): the first row
    prices, by the PO's ruling of 2026-10-01 (option A, verbatim *"we have to
    return only 1 row; A · Use the newest everywhere, and flag it on Check"*),
    and the rest are what the bill-run Check names
    (`schedule_versions_overlap`).

    ⚠ **THE ORDER IS PICKED IN PYTHON THROUGH THE CHAIN'S OWN FUNCTION, NOT BY
    AN `order_by` HERE.** Until 2026-10-01 this module ordered by
    `-effective_from` alone — on a same-date tie, the database's choice — and
    the chain refused instead of ordering at all. One function now answers
    both (`resolution.pick_in_force`), so the nightly run and the one-time /
    move-out / correction paths cannot disagree about which row prices. The
    candidate set is at most a handful of rows; sorting them is free.
    """
    return resolution.ordered_in_force(_in_force_candidates(tariff, service_date))


def in_force_version(tariff: models.Tariff, service_date: date) -> models.TariffVersion | None:
    """BR-RAT-007: the version whose window contains the SERVICE date, never
    the current one — and, where a legacy overlap leaves more than one,
    the ONE `BR-RAT-1055` names (newest `effective_from`, then newest
    `created_at`, then id). See `in_force_versions`."""
    return resolution.pick_in_force(_in_force_candidates(tariff, service_date))


def latest_version(tariff: models.Tariff) -> models.TariffVersion | None:
    """The newest ACTIVATED version (drafts excluded — BR-RAT-031).

    ── ⚠ **IT HAS NO `superseded_by` FILTER, AND THAT WAS ASKED RATHER THAN
    ASSUMED (`BR-RAT-1044` lane, 2026-09-29).** ──────────────────────────────
    Its two siblings both filter — `in_force_version` since `DEF-RAT-5715`,
    `resolution_catalogue.schedule_version_facts` since `DEF-RAT-8002` — so
    the absence here reads like the third instance of the same miss. **It is
    not, and the reason is the ORDERING rather than the name.**

    A CORRECTION copies the original's `effective_from` (BR-RAT-104 /
    BR-RAT-1016 verb 2 — that single property is what makes it a correction),
    so the corrected row and its replacement always TIE on the first sort key
    and are always separated by the second: `created_at`, which is
    `auto_now_add` and is therefore strictly later on the row written second.
    **So the live row always sorts first and a superseded row is never
    returned.** Worked through for the three shapes that could break it and
    pinned in `tests/test_br_rat_1044_correction_closes_the_window.py`:
    correcting the newest version · correcting a correction (a chain) ·
    correcting a version that is NOT the newest.

    ⚠ **`-created_at` IS THEREFORE LOAD-BEARING AND NOT A TIE-BREAK FOR
    TIDINESS.** Drop it and every one of this function's twelve call sites can
    be handed a row that no longer prices — `previous` for a rate change, the
    base charge code carried forward, the window that gets closed. The test
    above asserts it is still in the ordering and says why.

    ⚠ **WHAT IS NOT GUARANTEED, STATED RATHER THAN LEFT TO BE FOUND:** two
    rows written inside one microsecond would tie on BOTH keys and the answer
    would be whichever the database returned first. Nothing in this repo can
    produce that — the two writes are separate ORM saves — and it is recorded
    here because *"safe by the ordering"* is a weaker promise than *"safe by a
    predicate"*, and the next reader is entitled to know which one they have.

    ⚠ **A BLANKET FILTER WAS CONSIDERED AND NOT APPLIED.** Ten of the twelve
    call sites want the newest LIVE row and would be unchanged by it. **Two
    ask a different question** — `update_rate_schedule`'s two
    `latest_version(tariff) is not None` guards ask *has this schedule ever
    gone live*, which is a property of the SCHEDULE, and a corrected row is
    a perfectly good answer to it. Adding the predicate would make those two
    read *is there a live version*, a question that happens to have the same
    answer today only because a correction always leaves one behind. Changing
    a 🔒 money-path selector under twelve callers to make two of them mean
    something subtly different is a worse trade than writing this down.

    `BR-RAT-1044` stamps a corrected row's `effective_to`; this ordering reads
    `effective_from` and `created_at` and **never `effective_to`**, so that
    change cannot move what this returns. Asserted, not assumed.
    """
    return activated_versions(tariff).order_by("-effective_from", "-created_at").first()


def _base_codes_by_service() -> dict[Any, list[list[str]]]:
    """Each service's live base codes, as their class scopes (empty = every class)."""
    out: dict[Any, list[list[str]]] = {}
    for service_id, classes in models.Charge.objects.filter(
        tenant_id=_tenant_id(), is_base=True, deleted_at__isnull=True, service_id__isnull=False
    ).values_list("service_id", "applies_to_customer_classes"):
        out.setdefault(service_id, []).append([str(one) for one in (classes or [])])
    return out


def schedule_needs_a_named_base(
    tariff: models.Tariff, version: Any, by_service: dict[Any, list[list[str]]] | None = None
) -> bool:
    """`DEF-RAT-9797` (PO ruling 2026-10-06) — a LIVE schedule whose version
    names no base code while TWO OR MORE of its service's base codes could serve
    it (the class test of `services._code_admits_class`: a code with no classes,
    or a schedule with no class, admits). It still bills as it always did (the
    pooled, class-narrowed code) and is LISTED for a System Admin to choose;
    nothing chooses for them. One candidate needs no choice — the next saved
    version names it — so it is not listed."""
    if tariff.deleted_at is not None or version is None or version.effective_from is None:
        return False
    if getattr(version, "base_charge_code_id", None):
        return False
    pool = by_service if by_service is not None else _base_codes_by_service()
    scopes = pool.get(tariff.service_id, [])
    class_code = (
        seams.account_type_code_by_id(tariff.account_type_id) if tariff.account_type_id else None
    )
    candidates = [
        scope for scope in scopes if not scope or class_code is None or class_code in scope
    ]
    return len(candidates) > 1


def schedules_needing_a_named_base(today: date | None = None) -> list[models.Tariff]:
    """Every live schedule `schedule_needs_a_named_base` lists, by name. Bounded
    by the tenant's schedules (tens), read for the Rate schedules notice."""
    today = today or seams.tenant_today()
    pool = _base_codes_by_service()
    out = []
    for tariff in (
        models.Tariff.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True, service_id__in=list(pool)
        )
        .select_related("service")
        .order_by("name", "id")
    ):
        version = in_force_version(tariff, today) or latest_version(tariff)
        if schedule_needs_a_named_base(tariff, version, pool):
            out.append(tariff)
    return out


def schedule_state(tariff: models.Tariff, today: date | None = None) -> dict[str, Any]:
    """US-RAT-004 §5 status pill, DERIVED (no status column exists, by design):
    a version in force → active · none → draft (whether the schedule is
    identity-only or carries a saved draft structure — BR-RAT-031) · a
    future-effective version adds the "Change scheduled — effective <date>"
    note. There is NO approval-pending state (BR-RAT-031 as-modified)."""
    today = today or seams.tenant_today()
    if tariff.deleted_at is not None:
        status = "archived"
    elif in_force_version(tariff, today) is not None:
        status = "active"
    else:
        status = "draft"
    scheduled = (
        activated_versions(tariff)
        .filter(effective_from__gt=today)
        .order_by("effective_from")
        .values_list("effective_from", flat=True)
        .first()
    )
    return {
        "status": status,
        "scheduled_change": scheduled.isoformat() if scheduled else None,
        "has_draft": draft_version(tariff) is not None,
    }


def version_structure(version: models.TariffVersion | None) -> dict[str, Any]:
    """The S9 card's structure preview — stored rows read back verbatim.
    No pricing is computed here (that is the 🔒 engine, EP-RAT-05/06)."""
    if version is None:
        return {}
    tenant_id = _tenant_id()
    seasons = list(
        models.RateSeason.objects.filter(tenant_id=tenant_id, tariff_version=version).order_by(
            "start_month", "start_day", "id"
        )
    )
    season_labels = {season.id: season.label for season in seasons}
    # ── DEF-1121 · WHAT THE TIER FIGURES ARE MEASURED AND PRICED IN ──────────
    #
    # `_money()` below serves every tier figure at BR-RAT-003's STORAGE scale —
    # its docstring says so and is right about why — so `from_qty`, `to_qty` and
    # `unit_price` all arrive as six-place strings. Three screens interpolated
    # them straight into a cell, and the Product Owner's own complaint about
    # decimals was live on Plans & Rates the whole time: a water tier read
    # `0.000000 – 5.000000` priced at `8.290000`.
    #
    # The two halves of that row obey DIFFERENT rules (BR-SHL-250), which is
    # exactly why it needed a ruling before it could be fixed:
    #   · the BOUNDS are a QUANTITY  → at most 2dp, zeros TRIMMED, and a unit
    #     (BR-MET-144 + hard rule 3) → `0 – 5 kgal`
    #   · the PRICE is a RATE        → exactly 4dp, zeros KEPT, and a currency
    #     (OQ-620(a), PO 2026-08-27) → `$8.2900`
    #
    # The unit is composed HERE because a quantity cannot be rendered without it
    # and the client is not sent the service's UoM anywhere else; the CURRENCY
    # travels raw because money and rates are formatted client-side, where the
    # tenant's number format lives (BR-SHL-250 again — `$8.2900` in en-US and
    # `8,2900 $` elsewhere is not a decision this layer can make).
    structure: dict[str, Any] = {
        "model": version.model,
        "unit": version.uom,
        "currency": version.currency,
    }
    tiers = list(
        models.RateTier.objects.filter(tenant_id=tenant_id, tariff_version=version).order_by(
            "seq", "id"
        )
    )
    if tiers:
        structure["tiers"] = [
            {
                "seq": tier.seq,
                "season": season_labels.get(tier.season_id),
                # DEF-433 · the third per-size column of r10's rate matrix, and
                # it was UNREACHABLE: `RateTier.size_class` existed, nothing
                # wrote it and nothing served it, so the 2" water row — `3.45 /
                # 5.10 / 7.70` where every other size prices `3.20 / 4.80 /
                # 7.20` — could not be expressed at all.
                #
                # NULL means "every size" and is the FALLBACK group, not an
                # unanswered question: every tier written before this column
                # existed reads back as `null` here and prices exactly as it
                # always did. A screen groups on this key and draws one matrix
                # row per group, with the null group as the row that prices
                # every size it does not name.
                "size_class": tier.size_class,
                "from_qty": _money(tier.from_qty),
                "to_qty": _money(tier.to_qty),
                "unit_price": _money(tier.unit_price),
                # DEF-1121 — the composed bounds. `None` when the figure is
                # absent (the last tier's open `to_qty`) OR when the version
                # records no UoM: hard rule 3 refuses a bare number rather than
                # printing digits a reader must guess the unit of, and the cell
                # draws its own "open-ended" sentence for the first case.
                "from_qty_display": wording.quantity_with_unit(tier.from_qty, version.uom),
                "to_qty_display": wording.quantity_with_unit(tier.to_qty, version.uom),
            }
            for tier in tiers
        ]
    if seasons:
        structure["seasons"] = [
            {
                "label": season.label,
                "start_month": season.start_month,
                "start_day": season.start_day,
                "end_month": season.end_month,
                "end_day": season.end_day,
            }
            for season in seasons
        ]
    windows = list(
        models.TimeOfUseWindow.objects.filter(tenant_id=tenant_id, tariff_version=version).order_by(
            "season__start_month", "day_type", "start_time", "id"
        )
    )
    if windows:
        structure["windows"] = [
            {
                "label": window.label,
                "season": season_labels.get(window.season_id),
                "day_type": window.day_type,
                "start_time": window.start_time.strftime("%H:%M"),
                "end_time": window.end_time.strftime("%H:%M"),
                "unit_price": _money(window.unit_price),
                # BR-RAT-067. Served as None for a window configured before the
                # column existed, and the S11 card draws that as an unanswered
                # required field rather than picking one — the whole point of
                # the ruling is that this answer is the utility's.
                "channel": window.channel,
            }
            for window in windows
        ]
    capacity = models.CapacityRate.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ).first()
    if capacity is not None:
        structure["capacity"] = {
            "unit_label": capacity.unit_label,
            "rate_per_unit": _money(capacity.rate_per_unit),
            "currency": capacity.currency,
        }
    demand = models.DemandRateConfig.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ).first()
    if demand is not None:
        structure["demand"] = {
            "energy_rate_per_kwh": _money(demand.energy_rate_per_kwh),
            "demand_rate_per_kw": _money(demand.demand_rate_per_kw),
            "peak_window_label": demand.peak_window_label,
            "ratchet_enabled": demand.ratchet_enabled,
            "ratchet_pct": _money(demand.ratchet_pct),
            "pf_penalty_enabled": demand.pf_penalty_enabled,
            "pf_penalty_rate_per_kw": _money(demand.pf_penalty_rate_per_kw),
        }
    if version.percent is not None:
        structure["percent"] = _money(version.percent)
        structure["basis_service"] = (
            version.basis_service.code if version.basis_service_id else None
        )
        # `CR-130-BRC07` — A PERCENTAGE OF WHAT, served to the SCREEN.
        #
        # ⚠ **THIS IS THE READ HALF AND IT IS THE ONE THAT GOES MISSING**
        # (CLAUDE.md hard-won law 2). The write lands, the column stores, the
        # engine prices — and a wizard reopening the schedule draws its card on
        # whatever it defaults to, so a `charge` schedule silently reopens as a
        # `usage` one and a clerk who presses save has changed the basis without
        # being told. `tsc` and every test pass over that, because nothing is
        # broken: a field is simply absent.
        structure["percent_basis"] = version.percent_basis
    return structure


def size_rows(version: models.TariffVersion) -> list[dict[str, Any]]:
    """DEF-360 · the schedule's per-connection-size rows, in size order.

    **Only the columns §A3 gives the SCHEDULE.** The matrix a screen draws is
    `size · base · min · t1 · t2 · t3`, and the base is not in this list: the
    charge code owns it (BR-RAT-088) and the schedule *"shows it read-only,
    attributed"* by reading the charge instead. Serving a base from here would
    hand a screen the second source of truth the ruling exists to remove.

    `minimum_bill` is `null` for a size that has a row and no floor — r10's
    electric matrix draws an em-dash in that column for every size. A screen
    renders the absence; it must not render `0.00` (DEF-277's distinction, one
    column across).
    """
    return [
        {
            "size_class": row.size_class,
            "minimum_bill": _money(row.minimum_bill),
            # BR-RAT-087: the client never formats money. Served beside the
            # stored value, exactly as `charge_row` does.
            "minimum_bill_display": _display_money(row.minimum_bill),
            "currency": row.currency,
        }
        for row in models.RateSizeRow.objects.filter(
            tenant_id=_tenant_id(), tariff_version=version
        ).order_by(
            "size_class", "id"
        )  # IS-2 stable secondary
    ]


def _actor_ref(user_id: Any, names: dict[str, str] | None = None) -> dict[str, Any] | None:
    """DEF-367 · a user id served as `{"id", "name"}`, or null for nobody.

    The shape is `apps/audit/selectors._actor_payload`'s, verbatim, and copying
    it is the point: a uuid at a person is DEF-206's lesson, and a bare name
    with no id cannot be traced back when two staff share a first name. `name`
    is null when the row is gone (BR-IDN-030 keeps user rows; a version outlives
    any of them), and the screen says so rather than printing the id.

    `names` is the batched map for a page. Passing None resolves this one id on
    its own, which is right for a single card and wrong for a table.
    """
    if user_id is None:
        return None
    key = str(user_id)
    resolved = names if names is not None else seams.user_display_names([user_id])
    return {"id": key, "name": resolved.get(key)}


def named_base_charge_code(version: models.TariffVersion | None) -> str | None:
    """`BR-RAT-1025` — the `charges.code` this rate schedule version BINDS its
    service's base to, or `None` when it names nothing.

    ⚠ **ONE EXPRESSION, BECAUSE THREE DOORS NOW READ THE BINDING AND THEY MUST
    NOT DISAGREE ABOUT WHAT IT IS (`DEF-RAT-6960`).** The bill reads it off
    `pricing_inputs_for_version`; the rate-change impact analysis reads the
    same projection; the customer portal's standing charge holds the VERSION
    itself and had no projection to read. A fourth hand-written
    `version.base_charge_code.code if version.base_charge_code_id else None`
    is how two of those start answering differently — which is the defect this
    function is part of the fix for, one object up.

    ⚠ **THE CODE'S `charges.code`, NEVER ITS ID.** `base_charge_from_charge_code`
    narrows on `row.code == named_code`, so a uuid here matches nothing and
    falls through to the INFERRED code — silently, on a money path, producing a
    well-formed bill from a code no screen shows.

    ⚠ **IT ANSWERS FOR A SOFT-DELETED CODE TOO**, for `_base_charge_code_ref`'s
    recorded reason: a code that has since been retired is still what this
    version NAMES, and the live read must REFUSE by that name rather than
    infer another (`DEF-RAT-6918`). Reading `None` here would turn the refusal
    back into the silent wrong bill.
    """
    if version is None or not version.base_charge_code_id:
        return None
    return version.base_charge_code.code


def _base_charge_code_ref(version: models.TariffVersion) -> dict[str, Any] | None:
    """`CR-120-BRC06` · `BR-RAT-1025` — the named base charge code as
    `{id, code, name}`, or None.

    **`{id, code, name}` AND NOT A BARE UUID, for `DEF-367`'s recorded reason
    one field across:** a bare id *"no screen could print at a person"*. B14
    rule 31 says no database id is ever the visible value of a field, so a
    screen handed only the id has nothing it is allowed to draw.

    ⚠ **IT READS THE ROW RATHER THAN A CACHE, AND IT ANSWERS FOR A SOFT-DELETED
    CODE TOO.** A code that has since been soft-deleted is still what this
    version NAMES, and saying so is the truth; an em-dash would tell a clerk the
    schedule names nothing while `_guard_bound_base_charge_code` refuses its
    next activation for naming something gone. The screen and the refusal have
    to be describing the same world.
    """
    if not version.base_charge_code_id:
        return None
    code = version.base_charge_code
    return {"id": str(code.id), "code": code.code, "name": code.name}


def version_row(
    version: models.TariffVersion | None, names: dict[str, str] | None = None
) -> dict[str, Any] | None:
    if version is None:
        return None
    if names is None:
        # One read for the two people this row can name, so a caller that has
        # not batched still costs one query rather than two.
        names = seams.user_display_names(
            [version.submitted_by_id, version.approved_by_id, version.corrected_by_id]
        )
    return {
        "id": str(version.id),
        # ── DEF-RAT-5715 · BR-RAT-104, the correction chain ───────────────
        # Served so a screen can tell the three states apart WITHOUT a second
        # request: a plain version, a row that HAS been corrected (and so no
        # longer prices), and the row that corrected it. Rendering only the
        # reason would leave a superseded row looking live.
        "corrects": str(version.corrects_id) if version.corrects_id else None,
        "superseded_by": str(version.superseded_by_id) if version.superseded_by_id else None,
        "correction_reason": version.correction_reason,
        "corrected_by": _actor_ref(version.corrected_by_id, names),
        # `DEF-RAT-9003` — when the version was SAVED. The screens number
        # versions in this order, so a number once shown never moves.
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "model": version.model,
        "uom": version.uom,
        "currency": version.currency,
        "base_charge": _money(version.base_charge),
        # ── `CR-120-BRC06` · `BR-RAT-1025` — THE CODE THE SCHEDULE NAMES ─────
        # PO ruling 2026-09-19: *"plan → rate schedule -> charge code → base
        # charges"*. Two keys, and they answer two different questions:
        #   `base_charge_code`      the id, for the picker on step 1 to re-select
        #   `base_charge_code_ref`  `{id, code, name}`, for anything that PRINTS
        #                           it — B14 rule 31: no database id is ever the
        #                           visible value of a field, so a screen that
        #                           had only the id would have nothing to show.
        # ⚠ **NEITHER IS AN AMOUNT AND NEITHER MAY BECOME ONE.** `base_charge`
        # one line up is the RETIRED decimal; this is a pointer at `charges`,
        # which is where the figure lives (`BR-RAT-088`, unmoved).
        "base_charge_code": (
            str(version.base_charge_code_id) if version.base_charge_code_id else None
        ),
        "base_charge_code_ref": _base_charge_code_ref(version),
        "minimum_bill": _money(version.minimum_bill),
        # BR-RAT-087 — the two-place strings a screen renders, beside (never
        # instead of) the six-place values anything that computes reads.
        "base_charge_display": _display_money(version.base_charge),
        "minimum_bill_display": _display_money(version.minimum_bill),
        # DEF-360. An empty list means "one row prices every size", which is
        # what every version written before this column existed says.
        "size_rows": size_rows(version),
        # BR-RAT-082 — captured, kept, and read by nothing (see the model).
        "filing_authority": version.filing_authority,
        "filed_on": version.filed_on.isoformat() if version.filed_on else None,
        "regulator_approved_on": (
            version.regulator_approved_on.isoformat() if version.regulator_approved_on else None
        ),
        "regulator_approver": version.regulator_approver,
        # NULL = the draft (BR-RAT-031); the row is otherwise read back verbatim.
        "effective_from": (version.effective_from.isoformat() if version.effective_from else None),
        "effective_to": version.effective_to.isoformat() if version.effective_to else None,
        # DEF-367 — WAS a bare uuid string, which no screen could print at a
        # person. Now the `{id, name}` pair the audit trail has always served.
        # ⚠ A CONTRACT CHANGE, not an addition: a client reading `approved_by`
        # as a string reads an object from this commit. There is exactly one —
        # `RateScheduleDetail`'s versions table, which rendered the absence and
        # never the value — and it is updated in the same commit.
        "approved_by": _actor_ref(version.approved_by_id, names),
        # DEF-367 — the OTHER person, and the one §10's BY column asks for.
        # BR-RAT-083 splits them: anyone drafts, an Owner/Admin activates.
        "submitted_by": _actor_ref(version.submitted_by_id, names),
        # DEF-369 — the FILED label, stored. Null means the utility never stated
        # one and the screen falls back to a derived ordinal, saying that it is
        # derived; it never presents a position as an identifier.
        "version_label": version.version_label,
        # DEF-280 — BR-RAT-037's authored reason, on the version it describes.
        "change_reason": version.change_reason,
        "regulator_ref": version.regulator_ref,
        "notify_customers": version.notify_customers,
        "publish_public": version.publish_public,
        "structure": version_structure(version),
    }


def schedule_used_by_plans(tariff: models.Tariff) -> int:
    return models.PlanRateSchedule.objects.filter(tenant_id=_tenant_id(), tariff=tariff).count()


#: How many blocking plan NAMES a refusal carries. DEF-278: the refusal used to
#: say "referenced by 3 plans" and the user could not find out which three, so
#: the only way to act on it was to open every plan by hand. Five is a cap and
#: not a page size — the count travels beside the names, so a tenant with sixty
#: blocking plans reads "60 plans … including <five>" rather than a comma list
#: nobody can read, and the number stays true.
BLOCKING_PLAN_NAMES_SHOWN = 5


def schedule_blocking_plan_names(tariff: models.Tariff) -> list[str]:
    """DEF-278 — the plans that block this schedule's archive, BY NAME.

    The count (`schedule_used_by_plans`) and this list are the same query with a
    different projection, which is the whole finding: the refusal already knew
    which plans they were and threw the names away at `.count()`. Ordered by
    name so two reads of the same refusal print the same sentence.
    """
    return list(
        models.PlanRateSchedule.objects.filter(tenant_id=_tenant_id(), tariff=tariff)
        .order_by("rate_plan__name")
        .values_list("rate_plan__name", flat=True)[:BLOCKING_PLAN_NAMES_SHOWN]
    )


def schedule_applied_to_accounts(tariff: models.Tariff) -> int:
    """Units on a current assignment whose plan attaches this schedule."""
    plan_ids = models.PlanRateSchedule.objects.filter(
        tenant_id=_tenant_id(), tariff=tariff
    ).values_list("rate_plan_id", flat=True)
    return models.UnitPlanAssignment.objects.filter(
        tenant_id=_tenant_id(), rate_plan_id__in=list(plan_ids), assigned_to__isnull=True
    ).count()


# ── CR-013 part 1 step 4 · THE MANDATORY IMPACT ANALYSIS (DEF-434) ──────────
#: A full, unprorated cycle. Both sides of the comparison use the SAME period,
#: so B4.3's factor is exactly 1 (`proration.proration_factor` returns
#: `Decimal(1)` when service_days == cycle_days) and proration cannot move the
#: percentage in either direction. Thirty is a shape, not a calendar: nothing
#: here reads a clock (BR-TEN-043) and no month length changes the answer.
IMPACT_CYCLE_DAYS = 30

#: How many affected accounts one analysis prices. A rate schedule at a small
#: utility reaches a few thousand connections and each one is two engine calls,
#: so the read is bounded rather than open-ended — and the bound is REPORTED in
#: the answer (`accounts_sampled`), never applied silently, because a worst case
#: taken over half the accounts is not the worst case.
IMPACT_MAX_ACCOUNTS = 5000


def _impact_period() -> Any:
    """The period shape `engine.price_period` reads. Structural, like the seam."""
    return SimpleNamespace(cycle_days=IMPACT_CYCLE_DAYS, service_days=IMPACT_CYCLE_DAYS)


def _engine_tariff(inputs: dict[str, Any], service_code: str, base_charge: Decimal | None) -> Any:
    """One stored version, projected onto what the ENGINE reads.

    Field for field the same projection `apps/billing/gather._tariff_config_for`
    makes, and from the same source — `pricing_inputs_for_version`, which is
    `pricing_inputs`' own body. The engine reads its tariff STRUCTURALLY (see
    `pricing/stages/normalize.py`: *"Inputs are read STRUCTURALLY (by
    attribute), not by importing billing's dataclasses"*), which is precisely
    what lets rating hand it one without depending on billing.

    NO `multiplier` is set, ever. The engine REFUSES a tariff carrying one (PO
    ruling 2026-08-11) and it is right to: metering applies the meter multiplier
    one module upstream, and a second application turns a 1,247-dial delta at
    ×40 into a $194,113 bill that looks structurally perfect.
    """
    capacity = inputs.get("capacity")
    return SimpleNamespace(
        service=service_code,
        model=inputs["model"],
        billed_unit=inputs["billed_unit"] or "",
        base_charge=base_charge,
        unit_price=inputs["unit_price"],
        tiers=tuple(
            SimpleNamespace(upper=tier["upper"], unit_price=tier["unit_price"])
            for tier in inputs["tiers"]
        ),
        windows=tuple(
            SimpleNamespace(
                label=window["label"],
                unit_price=window["unit_price"],
                channel=window.get("channel"),
                season=window.get("season"),
                day_type=window.get("day_type") or "weekday",
            )
            for window in inputs.get("windows") or ()
        ),
        season=inputs.get("season"),
        # BR-RAT-034 (2026-10-01) — carried for parity with `gather`'s
        # projection. The impact analysis passes no period, so `season_days` is
        # `[]` and every account prices on ONE season, as it always has.
        season_days=tuple(
            SimpleNamespace(season=share.get("season"), days=share["days"])
            for share in inputs.get("season_days") or ()
        ),
        season_tiers=tuple(
            SimpleNamespace(
                season=ladder["season"],
                tiers=tuple(
                    SimpleNamespace(upper=tier["upper"], unit_price=tier["unit_price"])
                    for tier in ladder["tiers"]
                ),
            )
            for ladder in inputs.get("season_tiers") or ()
        ),
        capacity=(
            None
            if not capacity
            else SimpleNamespace(
                unit_label=capacity["unit_label"], rate_per_unit=capacity["rate_per_unit"]
            )
        ),
        energy_rate_per_kwh=inputs.get("energy_rate_per_kwh"),
        demand_rate_per_kw=inputs.get("demand_rate_per_kw"),
        ratchet_enabled=bool(inputs.get("ratchet_enabled")),
        pf_penalty_enabled=bool(inputs.get("pf_penalty_enabled")),
        percent=inputs.get("percent"),
        basis_service=inputs.get("basis_service"),
        # CR-130-BRC07 — carried here for the same reason `gather` carries it:
        # this projection and that one are the SAME projection of the same
        # source, and a field present in one and absent from the other is how
        # a bill and an impact analysis come to price one version differently.
        # The impact analysis prices ONE service at a time through
        # `price_period`, which supplies no basis at all, so a percent schedule
        # refuses there whichever basis it is on — `_price_one`'s scope, not a
        # gap this field opens.
        percent_basis=inputs.get("percent_basis"),
        version_id=inputs.get("version_id"),
    )


def _price_one(tariff_config: Any, quantity: Decimal, unit: str, currency: str) -> Decimal:
    """One service point, one period, through the REAL engine. Returns the total.

    No taxes and no fees are passed, and that is the analysis's stated scope
    (OQ-319): BR-RAT-091's ratified example moves an 11 kgal household
    `$59.00 → $62.54`, which is exactly `+6%` — a whole-bill figure could not be.
    r10 labels its own panel the same way: *"Typical bill · this service's
    portion"*.
    """
    priced = engine.price_period(
        tariff=tariff_config,
        consumption=SimpleNamespace(amount=quantity, unit=unit, windows=(), demand=None),
        period=_impact_period(),
        account=SimpleNamespace(currency=currency, tax_exempt=False),
    )
    return priced.total


def _baseline_version(
    tariff: models.Tariff, proposed: models.TariffVersion, effective_from: date
) -> models.TariffVersion | None:
    """WHAT THE PROPOSED VERSION REPLACES — the "before" side of the comparison.

    A DRAFT (`effective_from` NULL, BR-RAT-031) is compared against whatever is
    in force on the date it would take effect. An already-dated version is
    compared against the version whose window closed for it — strictly earlier,
    never itself, because a version compared with itself reports `0.00%` and
    that is the one answer this analysis must never invent.
    """
    if proposed.effective_from is None:
        return in_force_version(tariff, effective_from)
    return (
        activated_versions(tariff)
        .filter(effective_from__lt=proposed.effective_from)
        .order_by("-effective_from", "-created_at")
        .first()
    )


def rate_change_impact(
    tariff_id: Any,
    *,
    effective_from: date | None = None,
    proposed_version_id: Any = None,
) -> dict[str, Any]:
    """CR-013 part 1 step 4's four figures, against the tenant's REAL accounts.

    Part 1, verbatim: *"effective/end dates plus mandatory impact analysis:
    accounts affected by plan, average and worst-case bill change per class,
    annualised revenue change, accounts over threshold."* Part 1's gloss makes
    the shape binding: *"The impact analysis is MANDATORY and is four figures,
    not a warning banner."*

    **DEF-434, and what it cost.** Until this function existed, `GET
    /rate-schedules/{id}` served `used_by_plans` and `applied_to_accounts` and
    nothing else; RAT-03 step 4 drew four figures of which three were stated
    absences, and BR-RAT-091 clause 2's gate — *"worst-case bill change above
    `10%`"* — read a number nobody computed, so it could not fire. The rule's
    own sentence claimed *"RAT-03 step 4's mandatory impact analysis already
    computes the figure the gate reads"* and it did not (DEF-435).

    HOW EACH ACCOUNT IS PRICED
    --------------------------
    Twice, through `engine.price_period` — the same call a bill makes — with the
    tariff built by `pricing_inputs_for_version`, which IS `pricing_inputs`'
    body. One projection, one engine, so a bill and an impact analysis cannot
    price the same version differently. The quantity is the unit's own most
    recent metered consumption (`seams.recent_consumption_by_unit`); the base
    charge is resolved by billing's own `_base_charge_for` across the seam, so
    the DEF-154 precedence (the plan's figure where it states one, the
    schedule's where it does not) is not copied here.

    WHAT IS COUNTED BUT NOT PRICED, AND WHY IT IS SEPARATE
    -----------------------------------------------------
    An account with no read, a read in the wrong unit (BR-RAT-038 refuses rather
    than converts), a base billing would refuse (DEF-277 / OQ-238), a rate shape
    needing registers this analysis does not split, a `$0.00` before-price — each
    is counted in `accounts_unpriced` with its reason, and NONE of them is priced
    at zero. Averaging an unmeasurable account in as `0.00%` drags the worst case
    toward the middle, which is the one direction a rate-change gate must never
    be wrong in.

    THE FOUR FIGURES CARRY A `*_display` COMPANION (BR-RAT-087) and the percent
    stores six decimals (BR-RAT-092 / OQ-286). Money is `Decimal` throughout —
    never float, never cents.
    """
    tariff = tariff_or_404(tariff_id)
    service_code = tariff.service.code if tariff.service_id else ""
    today = seams.tenant_today()
    proposed: models.TariffVersion | None
    if proposed_version_id is not None:
        proposed = (
            models.TariffVersion.objects.filter(
                tenant_id=_tenant_id(), tariff=tariff, id=proposed_version_id
            ).first()
            if _valid_uuid(proposed_version_id)
            else None
        )
        if proposed is None:
            raise errors.NotFoundError()
    else:
        proposed = draft_version(tariff) or latest_version(tariff)
    if effective_from is None:
        effective_from = (proposed.effective_from if proposed else None) or today

    baseline = _baseline_version(tariff, proposed, effective_from) if proposed else None
    figures, accounts, unpriced_reasons, by_plan = impact_figures(
        tariff, service_code, baseline, proposed, effective_from
    )
    required, threshold = impact.second_approval_required(figures.worst_case_pct)
    return {
        "tariff_id": str(tariff.id),
        "service": service_code,
        "effective_from": effective_from.isoformat(),
        # WHICH TWO VERSIONS produced these numbers. A figure a utility files a
        # rate case on has to name its own inputs — DEF-276's reasoning, one
        # object up: *"travels onto the bill line — provable prices"*.
        "baseline_version_id": str(baseline.id) if baseline else None,
        "proposed_version_id": str(proposed.id) if proposed else None,
        "comparable": baseline is not None and proposed is not None,
        "accounts_affected": figures.accounts_affected,
        "accounts_priced": figures.accounts_priced,
        "accounts_unpriced": figures.accounts_unpriced,
        "accounts_sampled": len(accounts),
        "accounts_by_plan": by_plan,
        "unpriced_reasons": unpriced_reasons,
        "worst_case_pct": _money(figures.worst_case_pct),
        "worst_case_pct_display": _display_percent_points(figures.worst_case_pct),
        "average_pct": _money(figures.average_pct),
        "average_pct_display": _display_percent_points(figures.average_pct),
        "average_change": _money(figures.average_change),
        "average_change_display": _display_money(figures.average_change),
        "monthly_revenue_change": _money(figures.monthly_revenue_change),
        "monthly_revenue_change_display": _display_money(figures.monthly_revenue_change),
        "annualised_revenue_change": _money(figures.annualised_revenue_change),
        "annualised_revenue_change_display": _display_money(figures.annualised_revenue_change),
        "currency": proposed.currency if proposed else None,
        # BR-RAT-091 clause 2. `null` is the THIRD state and never `false`:
        # nothing may report an unmeasured filing as clear (DEF-434, OQ-320).
        "second_approval_required": required,
        "second_approval_threshold_pct": _money(threshold),
        "second_approval_threshold_pct_display": _display_percent_points(threshold),
        # ⚠ NOT SERVED, and named rather than relabelled: CR-013 part 1 asks for
        # the average and worst case *"per class"*, and no read joins customers'
        # `account_types` to an affected unit. The by-PLAN breakdown above is a
        # different cut and is not offered as this one (OQ-319).
        "by_class_unavailable_reason": "OQ-319",
    }


def impact_figures(
    tariff: models.Tariff,
    service_code: str,
    baseline: models.TariffVersion | None,
    proposed: models.TariffVersion | None,
    effective_from: date,
) -> tuple[impact.ImpactFigures, list[Any], dict[str, int], list[dict[str, Any]]]:
    """The I/O half: gather the affected accounts, price each pair, summarise.

    Split from `rate_change_impact` so the SERVICE-layer gate can call it
    without building an HTTP answer — BR-RAT-091's refusal needs the worst case
    and nothing else, and a gate that re-derived its own figure would be the
    second implementation this whole module exists to avoid.
    """
    plan_rows = list(
        models.PlanRateSchedule.objects.filter(
            tenant_id=_tenant_id(), tariff=tariff
        ).select_related("rate_plan")
    )
    plan_names = {str(row.rate_plan_id): row.rate_plan.name for row in plan_rows}
    plan_ids = list({row.rate_plan_id for row in plan_rows})
    assignments = list(
        models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id__in=plan_ids, assigned_to__isnull=True
        ).values_list("unit_id", "rate_plan_id")[:IMPACT_MAX_ACCOUNTS]
    )
    accounts_affected = schedule_applied_to_accounts(tariff)
    by_plan: dict[str, int] = {}
    for _unit_id, plan_id in assignments:
        key = str(plan_id)
        by_plan[key] = by_plan.get(key, 0) + 1
    breakdown = [
        {"plan_id": plan_id, "plan_name": plan_names.get(plan_id, ""), "accounts": count}
        for plan_id, count in sorted(by_plan.items(), key=lambda row: plan_names.get(row[0], ""))
    ]
    if baseline is None or proposed is None or not assignments:
        # Nothing to compare, or nobody to compare it for. NOT zero — see
        # `impact.summarise`: every aggregate comes back None (OQ-320).
        return (
            impact.summarise((), accounts_affected),
            [],
            {} if assignments else {"no_affected_accounts": accounts_affected},
            breakdown,
        )

    # ⚠ **`plan_base` WAS BUILT HERE AND IS DELETED (`DEF-BIL-7170`).** It read
    # `plan_services.base_charge` — RETIRED by the PO on 2026-09-28 — for the
    # two `seams.base_charge_for` calls below, and neither takes it any more.
    before_inputs = pricing_inputs_for_version(baseline, effective_from)
    after_inputs = pricing_inputs_for_version(proposed, effective_from)
    usage = seams.recent_consumption_by_unit(service_code, [unit_id for unit_id, _p in assignments])
    reasons: dict[str, int] = {}

    def _note(reason: str) -> None:
        reasons[reason] = reasons.get(reason, 0) + 1

    if not usage["wired"]:
        # Hard-won law 1, and the seam's own two-key shape: "the read does not
        # exist" is not "nobody has used any water".
        _note("consumption_read_unwired")
        return impact.summarise((), accounts_affected), [], reasons, breakdown

    changes: list[impact.AccountChange] = []
    for unit_id, plan_id in assignments:
        row = usage["rows"].get(str(unit_id))
        if row is None:
            _note("no_metered_consumption")
            continue
        # ── `BR-RAT-1025` · THE SCHEDULE'S BINDING, ON BOTH SIDES OF THE
        # COMPARISON (`DEF-RAT-6960`) ────────────────────────────────────────
        # This seam exists so an impact figure cannot differ from the bill —
        # its own docstring says *"a second implementation of pricing is how
        # two screens start disagreeing about a figure"*. From `DEF-RAT-5782`
        # the BILL honours the code the rate schedule names, and these two
        # calls did not, so a utility with more than one `is_base` code for a
        # service had every account counted `base_charge_refused` while its
        # bills were produced from the named code perfectly well.
        #
        # ⚠ **EACH SIDE TAKES ITS OWN VERSION'S BINDING, AND THAT IS THE
        # POINT OF READING IT OFF THE TWO PROJECTIONS.** A filing that MOVES
        # the base from one code to another is exactly the change an impact
        # analysis is asked to price; one binding used for both halves would
        # report that change as costing nothing.
        # ⚠ **THE PLAN'S AND THE VERSION'S OWN BASE FIGURES ARE NO LONGER
        # HANDED DOWN — `DEF-BIL-7170`, PO 2026-09-28.** Both columns are
        # RETIRED (*"we will never take default value from plan $8.0 - that is
        # retired"*), so the bill reads neither; an impact analysis that went
        # on passing them would be pricing a source the bill cannot charge
        # from, which is the one thing this seam exists to prevent.
        # CR-156-BRC10 — both sides priced on the day the change takes effect,
        # so a charge-code price scheduled for that day is the one measured.
        base = seams.base_charge_for(
            service_code,
            named_code=before_inputs["base_charge_code"],
            on_date=effective_from,
        )
        base_after = seams.base_charge_for(
            service_code,
            named_code=after_inputs["base_charge_code"],
            on_date=effective_from,
        )
        if base["refusal"] or base_after["refusal"]:
            # A bill would REFUSE this account. An impact figure that priced it
            # anyway would be money nobody will ever be billed (DEF-277/OQ-238).
            _note("base_charge_refused")
            continue
        try:
            before = _price_one(
                _engine_tariff(before_inputs, service_code, base["amount"]),
                row["amount"],
                row["unit"],
                baseline.currency,
            )
            after = _price_one(
                _engine_tariff(after_inputs, service_code, base_after["amount"]),
                row["amount"],
                row["unit"],
                proposed.currency,
            )
        except Exception as problem:  # the engine's own named refusal, counted
            _note(f"engine:{type(problem).__name__}")
            continue
        change = impact.AccountChange(
            unit_id=str(unit_id),
            plan_id=str(plan_id),
            plan_name=plan_names.get(str(plan_id), ""),
            quantity=row["amount"],
            unit=row["unit"],
            before=before,
            after=after,
        )
        if change.pct is None:
            # A `$0.00` before-price has no percentage (see `bill_change_pct`).
            _note("no_percentage_from_zero_before")
            continue
        changes.append(change)
    return impact.summarise(tuple(changes), accounts_affected), changes, reasons, breakdown


def _block_count(tiers: list[dict[str, Any]]) -> int:
    """DEF-485 · r10's "3 blocks" — how many blocks the deepest LADDER has.

    A version's tier rows are one ladder per (season, size) pair: a summer/winter
    rate stores its three blocks twice, and DEF-433's 2" override stores a third
    copy. A count of rows says 6 or 9 for a rate every utility calls three-block,
    so the rows are grouped by the pair that defines a ladder and the largest
    group wins. MAX rather than the first group's length because a size override
    is allowed to have a different number of blocks from the base ladder — the
    schedule's shape is the most any customer can be charged through.
    """
    if not tiers:
        return 0
    ladders: dict[tuple[Any, Any], int] = {}
    for tier in tiers:
        key = (tier.get("season"), tier.get("size_class"))
        ladders[key] = ladders.get(key, 0) + 1
    return max(ladders.values())


def schedule_card(tariff: models.Tariff, today: date | None = None) -> dict[str, Any]:
    today = today or seams.tenant_today()
    current = in_force_version(tariff, today) or latest_version(tariff)
    # ⚠ DEF-368 — THIS READ `draft_version(tariff) if current is None else None`
    # AND THE CONDITION IS DELETED, NOT LOOSENED.
    #
    # The rule it protected is real and is kept below: BR-RAT-031 says a draft
    # has never been in force, so `current_version` must never be filled from
    # one and `preview` falls back to a draft only when there is nothing live.
    # Both of those are about the two fields under them. The CONDITION was about
    # a third thing — whether `draft_version` is served at all — and there it
    # was simply wrong: a schedule with a rate in force AND a rate case in
    # preparation is not an edge case, it is what CR-013 part 1 calls the whole
    # point of the object (*"a rate case becomes a future-dated draft sitting
    # alongside the active version"*), and the card answered `null` for it. So
    # the filings table on RAT-02 could not draw the pending filing, and §10
    # draws exactly that as its normal case: *"a draft future version is listed
    # ABOVE the current one"*.
    #
    # Correct for a CARD (one preview, and a draft preview IS the resume view),
    # wrong the moment a DETAIL asked for the whole chain — which is the defect's
    # own diagnosis, and the reason the fix is here rather than in the detail:
    # one selector serves both, and a second draft read in `schedule_detail`
    # would be two answers to one question.
    draft = draft_version(tariff)
    # `current` first, always: a dateless row prices nothing and must not read
    # as what is in force (BR-RAT-031).
    preview = current or draft
    state = schedule_state(tariff, today)
    current_row = version_row(current)
    draft_row = version_row(draft)
    # DEF-441 · the five columns r10 draws that nothing served. Every one is
    # DERIVED FROM ROWS THIS SELECTOR ALREADY READ — no new table, no new query
    # shape, and no number that is not a count of stored rows. They are served
    # from HERE rather than counted on the client for two reasons: a client
    # count cannot be sorted by the server (the PO asked for sortable headers on
    # all nine), and the CSV export and the screen must agree by construction
    # rather than by two implementations happening to match.
    preview_row = current_row or draft_row
    structure = preview_row["structure"] if preview_row else {}
    # r10: "5 sizes". DEF-360 — an EMPTY size axis means "one row prices every
    # connection size", which is not the same as zero sizes; the screen renders
    # that distinction, this only counts.
    size_count = len(preview_row["size_rows"]) if preview_row else 0
    seasons = structure.get("seasons", [])
    tiers = structure.get("tiers", [])
    windows = structure.get("windows", [])
    return {
        "id": str(tariff.id),
        "name": tariff.name,
        "service": tariff.service.code,
        "service_name": tariff.service.name,
        "account_type_id": _uuid_or_none(tariff.account_type_id),
        "structure": preview.model if preview else None,
        "status": state["status"],
        "scheduled_change": state["scheduled_change"],
        "current_version": current_row,
        "draft_version": draft_row,
        "used_by_plans": schedule_used_by_plans(tariff),
        "applied_to_accounts": schedule_applied_to_accounts(tariff),
        # ── DEF-441's five ──────────────────────────────────────────────────
        "size_count": size_count,
        # r10 draws this column BOTH ways — "2 seasons" on one row and
        # "Summer / Winter" on another — so the labels travel and the screen
        # decides which form fits. A count alone could not produce r10's own
        # cell text.
        "season_labels": [season["label"] for season in seasons],
        # r10: "Tiered · 3 blocks".
        #
        # ⚠ DEF-485 — THIS READ `len({tier["seq"] for tier in tiers})` AND THE
        # COMMENT BESIDE IT NAMED THE EXACT FAILURE IT DID NOT PREVENT: *"the
        # BLOCK count is the distinct seq, not the row count — otherwise a
        # 3-block summer/winter water rate reads 6 blocks"*. True of the `seq`
        # `_validate_tiers` hands back (1..3 within each season) and false of the
        # `seq` that is STORED: `_write_version` renumbers every tier of a
        # version with ONE running counter, because `uq_rate_tiers_version_seq`
        # is kept verbatim. So summer got 1,2,3 and winter got 4,5,6 and the
        # distinct-seq trick counted rows after all. Hard-won law 1 — a comment
        # claiming a guarantee is not the guarantee.
        #
        # Counted from the STRUCTURE instead: how many blocks does the deepest
        # ladder have. Right for all three shapes at once — 3 for a flat-season
        # 3-block rate, 3 for the same rate split summer/winter, and 3 for one
        # carrying DEF-433's 2" size override, which would otherwise have made
        # the same cell read 6 for a second, unrelated reason.
        "block_count": _block_count(tiers),
        # r10: "TOU · 2 periods". Same reasoning: Peak and Off-peak repeat per
        # season and per day type, and the PERIOD is the label.
        "window_count": len({window["label"] for window in windows}),
        # r10's Effective column. The IN-FORCE version's date — a draft has none
        # and r10 draws an em-dash for exactly that row.
        "effective_from": current_row["effective_from"] if current_row else None,
        # CR-157-BRC10 wave B — the drawing's Customer class · Base code ·
        # Sizes `5 of 5` (`01-list-all.png`). Names, never ids (B14 rule 31).
        **schedule_reads.card_extras(tariff, current or draft, today),
    }


# DEF-441 · which sort key reads which DERIVED field. Six of r10's nine columns
# are computed per card rather than stored, so they cannot be an `order_by`;
# they sort here, over the built list, exactly as `status` always has.
_SCHEDULE_DERIVED_SORTS: dict[str, Any] = {
    "structure": lambda card: card["structure"] or "",
    "sizes": lambda card: card["size_count"],
    "seasons": lambda card: len(card["season_labels"]),
    "plans": lambda card: card["used_by_plans"],
    "accounts": lambda card: card["applied_to_accounts"],
    # "" sorts a dateless draft to the top ascending — which is where r10's own
    # em-dash row belongs, and never a fabricated date.
    "effective": lambda card: card["effective_from"] or "",
    "status": lambda card: card["status"],
}


def schedule_list_queryset(params: ListParams) -> QuerySet:
    """The rate-schedule set and its ordering — the half a DATABASE can answer.

    ⚠ **SPLIT OUT OF `schedule_list` FOR `NFR-3` (`DEF-RAT-5742`), AND IT IS
    ONLY HALF THE READ.** Search and the `service` filter are columns, and so
    are two of r10 nine sorts; the other seven columns are DERIVED per card
    (`_SCHEDULE_DERIVED_SORTS`), and `structure` and `status` filter on the
    CURRENT VERSION model rather than on anything stored. So this queryset is
    the whole answer only for the requests `schedule_list_is_sql_pageable`
    names, and `schedule_page` asks it before using this.

    The ordering is UNCHANGED, including the deliberate refusal to apply a
    `desc` to a derived sort here: that direction belongs to the Python sort
    that actually answers it, and flipping the fetch order would make the
    stable tiebreak depend on the direction of the thing above it.
    """
    qs = models.Tariff.objects.filter(tenant_id=_tenant_id()).select_related("service")
    term = params.q.strip()
    if len(term) >= MIN_SEARCH_CHARS:
        qs = qs.filter(name__icontains=term)
    services = filter_values(params.filters.get("service"))  # OQ-306 — ANY of
    if services:
        qs = qs.filter(service__code__in=services)
    sort = params.sort or SCHEDULE_DEFAULT_SORT
    # Only the two STORED columns can be an order_by. Everything else orders by
    # name here and is re-sorted in `schedule_list`, which also gives the
    # derived sorts a deterministic base to be stable over.
    field = {"name": "name", "service": "service__code"}.get(sort, "name")
    stored_sort = sort in ("name", "service")
    prefix = "-" if params.dir == "desc" and stored_sort else ""
    return qs.order_by(f"{prefix}{field}", "id")


def schedule_list_is_sql_pageable(params: ListParams) -> bool:
    """Can THIS request page in the database? (`NFR-3`, `DEF-RAT-5742`)

    ⚠ **YES FOR EVERY REQUEST A CLERK MAKES BY OPENING THE SCREEN**, and no
    only for one they make deliberately. Three things force the O(tenant)
    path, and each is a figure derived from the version in force rather than
    stored on `tariffs`:

      * `f.structure` — the CURRENT version model (US-RAT-004 TC-2);
      * `f.status`    — `schedule_state`, which reads the tenant own today;
      * any of the seven `_SCHEDULE_DERIVED_SORTS` keys.

    None of the three is re-implemented in SQL, on `DEF-387` reasoning: a
    second implementation of a derivation is how a list and a detail end up
    disagreeing about the same row. The exception is NAMED here instead, so it
    can be counted.
    """
    if params.filters.get("structure"):
        return False
    status = params.filters.get("status")
    if status and status.lower() != "all":
        return False
    return (params.sort or SCHEDULE_DEFAULT_SORT) not in _SCHEDULE_DERIVED_SORTS


def schedule_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """`(one page of schedule cards, the whole result set count)` — `NFR-3`."""
    if not schedule_list_is_sql_pageable(params):
        return _built_page(schedule_list(params), params)
    today = seams.tenant_today()
    return _sql_page(
        schedule_list_queryset(params),
        params,
        lambda tariffs: [schedule_card(tariff, today) for tariff in tariffs],
    )


def schedule_list(params: ListParams) -> list[dict[str, Any]]:
    """US-RAT-004 / DEF-441: the nine-column table — search name, filter
    service/structure/status, sort on any of r10's nine headers.

    ⛔ **THERE IS NO `code` LEG HERE AND THERE CANNOT BE ONE (CR-045 wave B
    task B.3 — DEF-1705).** B.3 is listed under *"copy only, where the server
    is already right"* and reads *"Rate schedules: name `code`, which the
    server already matches"*. **`Tariff` HAS NO `code` COLUMN.** Its fields are
    tenant, name, service, account_type_id, is_sample and the timestamps; the
    `code` the CR is thinking of belongs to `Plan` and to `Charge`, which are
    different tables that really do search `code | name`.

    So B.3 is not copy: naming `code` on the prompt would be D-2 — a field the
    server does not match — and MAKING it true is a column, a migration, a
    per-tenant uniqueness rule and a decision about what code the existing rows
    get. That is a change with a schema in it, and it is filed rather than
    taken here (prime directive: never resolve an open question by choosing a
    value).

    The prompt and `searchFields: ["name"]` are therefore CORRECT as they
    stand, and are deliberately left alone.
    """
    today = seams.tenant_today()
    sort = params.sort or SCHEDULE_DEFAULT_SORT
    structure = params.filters.get("structure")
    status = params.filters.get("status")
    cards = []
    for tariff in schedule_list_queryset(params):
        card = schedule_card(tariff, today)
        if structure and card["structure"] != structure:
            continue  # filtered on the CURRENT version's model (US-RAT-004 TC-2)
        if status and status.lower() != "all" and card["status"] != status.lower():
            continue
        cards.append(card)
    derived = _SCHEDULE_DERIVED_SORTS.get(sort)
    if derived is not None:
        # IS-2's stable secondary, done in two passes because Python's sort is
        # stable: name ascending first, then the chosen key. The old one-pass
        # `(status, name)` tuple reversed the TIE-BREAK too, so descending by
        # status listed equal rows Z→A — the secondary sort is not the user's
        # choice and must not flip with it.
        cards.sort(key=lambda card: card["name"])
        cards.sort(key=derived, reverse=params.dir == "desc")
    return _page(cards, params)


def schedule_detail(tariff_id: Any, as_of: date | None = None) -> dict[str, Any]:
    """The schedule as of ONE DATE — `as_of`, defaulting to the tenant's today.

    ⚠ **`as_of` IS ADDITIVE AND ITS DEFAULT IS THE BEHAVIOUR THIS FUNCTION HAS
    ALWAYS HAD** (CR-034 (b)). `schedule_card` has taken a date since it was
    written and this caller never passed one, so every existing call resolves
    `in_force_version(tariff, seams.tenant_today())` exactly as before — the
    same version, the same blocks, the same card.

    What it makes possible is BR-RAT-007: *"a June bill prices on June's terms
    whether the run happens in July or in 2031"*. A screen asking *"what applies
    to this unit for THIS period"* must narrow on the service date, not on the
    day the screen is open, or it shows a customer the rates of the wrong month
    and calls them the ones that will bill.

    ⚠ **THE DATE IS NARROWED ON, NEVER CLAMPED.** A future `as_of` legitimately
    resolves a future-dated activated version — that is what BR-RAT-007 means by
    the version in force ON the service date, and a caller asking about next
    month is asking exactly that. Drafts are still excluded (BR-RAT-031), by
    `in_force_version` and not by anything added here.
    """
    tariff = tariff_or_404(tariff_id)
    card = schedule_card(tariff, as_of)
    versions = tariff_versions(tariff)
    # DEF-367 — ONE read of identity for the whole filings table, not one per
    # row. `apps/audit/selectors` batches for the same reason on the same table.
    names = seams.user_display_names(
        [version.submitted_by_id for version in versions]
        + [version.approved_by_id for version in versions]
    )
    card["versions"] = [version_row(version, names) for version in versions]
    card["uom_gate"] = uom_gate(tariff)
    # DEF-RAT-5715 · 2.5 — HOW MANY BILLS THE VERSION IN FORCE HAS ALREADY
    # PRICED, so the screen can say what a correction cannot reach before the
    # operator commits one (hard rule 4).
    #
    # ⚠ ON THE DETAIL AND NOT ON EVERY `version_row`, deliberately: this is one
    # cross-module count, and hanging it on the row serializer would make it one
    # count PER VERSION — a filings table with nine rows would issue nine
    # queries into billing to draw a figure only one of them needs.
    # `None` means billing could not answer and the screen says so; it is never
    # flattened to 0, which is the distinction DEF-079 cost.
    #
    # ⚠ DEF-RAT-8705 — **IT COUNTS THE ROW THE SCREEN CORRECTS, WHICH IS
    # `current_version`, AND THAT IS A FALLBACK** (`in_force_version(today) or
    # latest_version(tariff)` — `schedule_card` above, and `DEF-RAT-5831`
    # recorded the same trap on RAT-02). This read `in_force_version` alone and
    # answered `None` whenever nothing was in force today, so a schedule FILED
    # AHEAD OF TIME — whose only live version starts tomorrow — printed *"We
    # could not count the bills."* twice on the wizard the PO used on
    # 2026-10-01: a `None` that meant *"there was no row to ask about"* drawn as
    # *"billing did not answer"*. A version that has not started has priced no
    # bill, and billing says so (0). `None` is again reserved for the one case
    # its docstring names.
    corrected = in_force_version(tariff, as_of or seams.tenant_today()) or latest_version(
        tariff
    )
    card["current_version_issued_bills"] = (
        version_issued_bill_count(corrected) if corrected is not None else None
    )
    # ── DEF-RAT-5718 · THE WINDOW A NEW VERSION WILL CLOSE ────────────────
    #
    # `create_rate_schedule_version` closes the previous window the day before
    # the new one opens — correct, and required by BR-RAT-037 (windows never
    # overlap) — and **nothing on any screen said so.** PO, in the beta: *"i
    # want to change the rate from tomorrow - eisting rates say it is valid
    # until 31 dec"*. A rate that says it runs to 31 December stops on the 17th
    # of September, and the clerk finds out afterwards.
    #
    # ⚠ **IT IS `latest_version` AND NOT `current_version`, BECAUSE THAT IS THE
    # ROW THE SERVER ACTUALLY CLOSES.** They are the same row on most schedules
    # and they are NOT the same when a future-dated version is already filed:
    # `current_version` is then the one in force today and `latest_version` is
    # the future one. Serving the wrong one would put a real date, belonging to
    # a real row, in a sentence about a different row — which is worse than
    # saying nothing.
    #
    # Two scalars rather than the row, because the screen needs exactly the two
    # the server's own condition reads:
    # `effective_to IS NULL OR effective_to >= new_from`.
    # ── `DEF-RAT-8004` · PO ruling 2026-10-01, option A — THE SCREEN SAYS IT TOO
    # *"flag it on Check"* and, in the same ruling, *"the rate schedule screen
    # shows the same"*: a legacy overlap of live versions, named here so the
    # View details page can draw a *Versions overlap* band. `[]` on every
    # schedule written since `rating/0047`.
    card["versions_overlap"] = versions_overlap(versions)
    closing = latest_version(tariff)
    card["closing_version_effective_from"] = (
        closing.effective_from.isoformat() if closing and closing.effective_from else None
    )
    card["closing_version_effective_to"] = (
        closing.effective_to.isoformat() if closing and closing.effective_to else None
    )
    return card


def versions_overlap(versions: Sequence[models.TariffVersion]) -> list[dict[str, Any]]:
    """🔒 HUMAN-REVIEW-PENDING · `BR-RAT-1055` — every stretch where MORE THAN
    ONE live version of this schedule is in force, each with its versions in
    the order they win (the first one prices) — VALUES, never ids.

    Read from the history the detail already holds (no query). A stretch
    starts on a version's `effective_from`, so asking each start date is
    enough to find every overlap; two dates finding the SAME set of rows are
    one stretch. Drafts and corrected rows price nothing and are left out,
    exactly as `in_force_version` leaves them out.
    """
    live = [v for v in versions if v.effective_from is not None and v.superseded_by_id is None]
    found: list[dict[str, Any]] = []
    seen: set[frozenset[str]] = set()
    for start in sorted({v.effective_from for v in live}):
        here = [
            v for v in live
            if v.effective_from <= start and (v.effective_to is None or v.effective_to >= start)
        ]
        key = frozenset(str(v.pk) for v in here)
        if len(here) < 2 or key in seen:
            continue
        seen.add(key)
        found.append(
            {
                "on": start.isoformat(),
                "versions": [
                    {
                        "label": v.version_label or None,
                        "effective_from": v.effective_from.isoformat(),
                        "effective_to": v.effective_to.isoformat() if v.effective_to else None,
                    }
                    for v in resolution.ordered_in_force(here)
                ],
            }
        )
    return found


def uom_gate(tariff: models.Tariff, version: models.TariffVersion | None = None) -> dict[str, Any]:
    """BR-RAT-038: the schedule's unit must be the unit the meter reads, or a
    per-service conversion factor must carry one to the other EXPLICITLY.

    A draft is gated too, so the wizard warns before activation, not after.
    The verdict itself is `uom_gate_for` — this is the stored-version door onto
    it, and a caller holding a PENDING unit (a save that has not written a row
    yet) asks that function directly.
    """
    version = version or latest_version(tariff) or draft_version(tariff)
    return uom_gate_for(tariff.service.code, version.uom if version else None)


def percent_basis_options(
    service_code: str | None = None,
    basis: str | None = None,
) -> list[dict[str, Any]]:
    """**WHAT A PERCENT SCHEDULE MAY BE A PERCENTAGE OF — DERIVED, NEVER A
    NAMED PAIR.** `CR-130-BRC07` §3 · PO ruling 2026-09-22.

    HUMAN-REVIEW-PENDING 🔒 — this decides which service's number a money line
    is computed from. Row in `12-governance/09-human-review-ledger.md`.

    ⚖️ **PO RULING 2026-09-22, VERBATIM**, answering whether the charge basis
    should be restricted to pairs that make sense:

        "youa re correct - however dont hard code anything - use logic to derive
         it so that it is flexible and handle any scenario. that the objective."

    ⚠ **NO SERVICE CODE APPEARS IN ANY CONDITION BELOW, ON EITHER BASIS.** Not
    `water`, not `sewer`, not a pair and not a list of sensible combinations.
    *Electric as a percentage of gas* is not forbidden here — it is simply
    never configured, and the product spends no line of code preventing a
    utility from doing something we have not thought of.

    **THE TWO DERIVATIONS, AND WHAT EACH ONE IS ASKING:**

      `usage`   enabled · not this service · **meters a quantity**
                The answer is a QUANTITY in that service's own unit, so a
                service that meters nothing has no quantity to take a
                percentage of (CLAUDE.md hard rule 3 — the unit travels and is
                never assumed).

      `charge`  enabled · not this service
                The answer is MONEY, and anything that can put a usage charge
                on a bill can supply it.

    **"Meters a quantity" is the TENANT'S OWN DECLARATION, read through
    `seams.service_bills_from_a_register`** — `tenant_services.billing_basis`,
    whose three ruled values are `metered` · `share` · `capacity`
    (`BR-TEN-1180`, PO 2026-09-02). It is not a list this module keeps: a
    utility that declares its own basis on S8 is honoured, and an eleventh
    catalogue service is classified by its own seed. That seam's docstring
    records the first draft of a neighbouring fix carrying the classification
    as a frozenset in this very file, and why it was wrong.

    ⚠ **A SERVICE WITH NO `tenant_services` ROW ANSWERS *metered* AND SO
    APPEARS ON THE `usage` LIST** — the seam's declared safe direction. Here
    that is the right way round too: offering a service that turns out to meter
    nothing produces a REFUSAL at bill time with a sentence naming the basis
    service (`BasisUnavailable`), which a clerk can act on. Hiding a service
    the utility does meter produces a screen with a missing option and no
    explanation anywhere.

    `basis` None returns the `usage` list, which is what every stored schedule
    in the product is on. An unknown `basis` returns `[]` rather than guessing —
    the caller asked a question with no answer.

    Ordering is the platform catalogue's own `sort`, which is the order every
    other screen already uses (`seams.enabled_service_codes`).
    """
    wanted = basis or percent_basis.PERCENT_BASIS_USAGE
    if wanted not in percent_basis.PERCENT_BASES:
        return []
    rows: list[dict[str, Any]] = []
    for code in seams.enabled_service_codes():
        if service_code and code == service_code:
            # A schedule may not be a percentage of ITSELF. Nothing in the
            # engine would terminate: `engine.price_bill` writes the basis
            # record in pass A only, so self-reference resolves to "not on this
            # bill" and refuses — but refusing at bill time what can be refused
            # on the screen is a bill nobody gets.
            continue
        catalog = seams.service_catalog_row(code)
        if catalog is None:
            # Enabled for the tenant and not ACTIVE in the platform catalogue.
            # Skipped rather than offered: a schedule may not be priced off a
            # service the platform has withdrawn.
            continue
        if wanted == percent_basis.PERCENT_BASIS_USAGE and not (
            seams.service_bills_from_a_register(code)
        ):
            continue
        rows.append({"code": code, "name": catalog["name"]})
    return rows


def uom_gate_for(service_code: str, schedule_uom: str | None) -> dict[str, Any]:
    """**THE INVARIANT, FOR ONE SERVICE AND ONE SCHEDULE UNIT.** Pure of the
    stored version — it takes the unit as a STRING so the same verdict answers a
    stored schedule, a draft, and a unit a clerk is in the middle of typing.

    HUMAN-REVIEW-PENDING 🔒 — this decides whether a price may be multiplied by
    a quantity, which is money. Row in `12-governance/09-human-review-ledger.md`.

    ⚖️ **PO RULING 2026-09-02, VERBATIM:** *"for Gas unit on rate schedule and
    unit on meter read should match otherwise it is a problem ; same principle
    is applied to all meter services and hence we have unit and multiplier
    factor"*. It generalises `BR-MET-143` (PO 2026-08-27) from the reading side
    to the PRICE side, and it is CLAUDE.md hard rule 3 applied to the other
    factor in the product: rule 3 forbids an assumed unit on a QUANTITY, and
    this forbids one on the PRICE that quantity is multiplied by.

    ⚠ **THIS FUNCTION READ `billed_uom` ALONE UNTIL 2026-09-02 AND WAS BLIND ON
    EVERY TENANT ALIVE.** `tenant_services.billed_uom` is NULLABLE by `B2 r6.4`
    and **nothing seeds it** — `tenancy.services` provisions `primary_uom` and
    `alt_uom` and leaves `billed_uom` NULL, so every provisioned tenant in this
    product carried NULL there. The old branch read that NULL as *"nothing to
    contradict yet"* and returned `satisfied=True`, which is the exact OPPOSITE
    of what the column's own reader says NULL means:
    `tenancy.selectors.service_billed_uoms` — *"a fresh tenant carries NULLs —
    which means 'the register's own unit is what is billed' and NOT
    'unconfigured, refuse'"*.

    **So the gate compared a schedule against a column that was always empty,
    and reported SATISFIED over every mismatch there was.** Measured on the
    seeded gas tenant: the billing workbook signs *"Gas flat $1.15/ccf"* while
    `SERVICE_DEFAULT_UOMS["gas"]` planted a register reading **therm**; a `ccf`
    schedule over that register returned `{"satisfied": True, "reason":
    "unconfigured"}` and the wizard drew no warning at all. Pricing a therm
    read at a per-ccf price is roughly **4% over on every gas line** — one
    therm is about `0.9643 ccf` of pipeline gas, so `42` units priced at
    `$1.15` bills **$48.30** where the same gas correctly converted is about
    **$46.58**, `$1.72` a month on one meter, on a document that foots.

    **THE EFFECTIVE BILLED UNIT IS `billed_uom` OR, WHERE THAT IS NULL, THE
    REGISTER'S OWN `primary_uom`** — which is what NULL means, and it is the
    unit the meter actually reads (`core.sample_fixture.estate_plan` builds the
    meter from exactly this column). That one substitution is what makes the
    gate able to fail at all.

    **THE SCALE / DIMENSION SPLIT IS `BR-MET-143`'s AND IT IS NOT RE-DECIDED
    HERE.** `seams.unit_reconciliation` is rating's door onto
    `metering.register_units.reconciliation`, the one implementation of that
    rule, and it answers MATCH / SCALE / DIMENSION / UNKNOWN_DIMENSION. It
    matters because a conversion factor is a **scale** and cannot cross a
    dimension: `therm` is declared ENERGY and `ccf` is declared VOLUME, so no
    number reconciles them — the conversion needs a heating value, which is a
    physical fact about the gas and not a column on this table. A gate that
    answered *"a factor would fix it"* there would send a clerk to type a number
    that cannot work, which is the failure `ChargeCodeAmountMissing` records as
    worse than a long refusal: a refusal naming the wrong remedy.

    Six verdicts, and `satisfied` is the only one a caller must read:

        no_register         this service reads no register at all, so there is
                            nothing for the schedule's unit to be compared
                            AGAINST. `DEF-3201`, and it is decided on the
                            SERVICE before either unit is read, from the
                            tenant's own `billing_basis` declaration
                            (`BR-TEN-1180`: metered · share · capacity) — see
                            `seams.service_bills_from_a_register`.
        unconfigured        one side states no unit — nothing to contradict.
                            A NULL **or a blank**: `DEF-3201` — the branch tests
                            falsiness, because the schedule's `uom` column is
                            nullable AND blankable and the two say one thing.
                            The ABSENCE is CLAUDE.md rule 3's business one step
                            earlier (`estate_plan` refuses a service with no
                            declared unit), never this gate's.
        match               the same unit. Nothing to reconcile.
        conversion_factor   different units of the SAME dimension, and the
                            tenant has declared the factor (`B2 r6.4`,
                            register→billed). US-RAT-005 TC-7's ratified
                            behaviour, unchanged.
        mismatch_no_factor  different units of the same dimension, no factor.
                            `B2 r6.4`: *"Mismatch without factor → block rating
                            + user message"*. TC-7's first half, unchanged.
        dimension_mismatch  different KINDS of quantity. NEW 2026-09-02, and it
                            is NOT satisfied even when a factor is on file,
                            because the factor cannot be honest.

    ⚠ **WHAT THIS GATE DOES NOT DO, STATED SO NOBODY READS IT AS A GUARANTEE
    (hard-won law 1).** It does not convert, and neither does anything else:
    `conversion_factor` is read by `metering.validation` for the high-usage
    floor and by NOTHING in `apps/billing/` or `apps/rating/pricing/`. So a
    `conversion_factor` verdict says *the tenant has declared the factor B2 r6.4
    asks for*, and the engine's own gate
    (`rating.pricing.stages.normalize._gate_uom`, `BR-RAT-038`) still refuses
    the bill because the quantity reaching it was never converted. That
    disagreement is REAL and is filed rather than papered over here.
    """
    configured = seams.billed_uom(service_code)
    billed = configured["billed_uom"]
    register = configured["primary_uom"]
    factor = configured["conversion_factor"]
    # NULL `billed_uom` MEANS the register's own unit is what is billed — see
    # `tenancy.selectors.service_billed_uoms`. Reading it as "unconfigured" is
    # what made this gate blind on every tenant.
    priced_against = billed or register
    # The reading's unit against the unit of the thing that PRICES it — that is
    # BR-MET-143's own framing and the argument order it names.
    verdict = seams.unit_reconciliation(priced_against, schedule_uom)
    kinds = seams.unit_reconciliation_kinds()
    kind = verdict["kind"]
    if not seams.service_bills_from_a_register(service_code):
        # ⚠ **A SERVICE WITH NO REGISTER IS OUTSIDE THIS RULE — `DEF-3201`.**
        # Answered FIRST and on the SERVICE alone, before either unit is looked
        # at, because that is what makes it a STATEMENT rather than an accident
        # of both sides happening to be blank. Trash is the proof: it declared
        # `month` while its schedule declared `cart` (`BR-RAT-090` prices trash
        # per CART — three carts at `$15.00` is `$45.00`), so both units were
        # present, both were correct, and the gate answered
        # `mismatch_no_factor` — a red *"a bill cannot be produced"* strip on a
        # service that bills perfectly well. Measured on PostgreSQL 16.13
        # through `provision_tenant` before the fix: `priced_against='month'`,
        # `schedule_uom='cart'`, `satisfied=False`.
        #
        # The answer is the TENANT's own `billing_basis` declaration
        # (`BR-TEN-1180`), read through the seam — never a list this module
        # keeps. See `seams.service_bills_from_a_register` for the ruling per
        # basis and for why a missing row answers "gated".
        satisfied, reason = True, "no_register"
    elif not (schedule_uom or "").strip() or not (priced_against or "").strip():
        # ⚠ **FALSINESS AND WHITESPACE, NOT IDENTITY — `DEF-3201`.** This read
        # `is None` until 2026-09-02.
        # `rate_schedule_versions.uom` is `TextField(null=True,
        # blank=True)`, so an EMPTY STRING is a lawful stored value for the
        # schedule side, and a blank is the same fact as a NULL: nobody has
        # said what this is priced in. An identity test lets `""` past, and
        # what it reaches is `unit_reconciliation("month", "")` →
        # `unknown_dimension` → `mismatch_no_factor`: a REFUSAL, with the empty
        # string interpolated into the clerk's sentence — *"this schedule
        # prices in  and the service is billed in month"*.
        #
        # ⚠ **AND IT STRIPS, BECAUSE `"   "` IS TRUTHY AND METERING ALREADY
        # FOLDS.** A whitespace unit passes a bare falsiness test, reaches
        # `reconciliation`, whose own `fold()` reduces it to `""` — and that
        # function reads a blank pricing unit as **MATCH**, by design and
        # correctly for its own purpose. So the verdict came back `match`: a
        # POSITIVE claim that two units agree, made about a unit nobody ever
        # stated. Safe in its arithmetic and wrong on a screen, which is the
        # DEF-3201 shape one more time. Measured before the strip:
        # `uom_gate_for("water", "   ")["reason"] == "match"`.
        #
        # ⚠ **AND THE BLANK THE PO ACTUALLY SAW WAS NOT THIS ONE, WHICH IS THE
        # part worth reading.** Measured on PostgreSQL 16.13 through
        # `provision_tenant`, all ten services: `priced_against` is `'kWh'`,
        # `'kgal'`, `'therm'`, `'month'`, `'ton-hr'` or `None` — **never
        # `""`** — because it comes off a UoM row's `code` through an FK, and
        # `services._text` turns a blank payload field into `None` before it
        # can be stored. The blank on the unit screen came from the FRONTEND
        # reading `billed_uom`, the raw column, which is NULL on every tenant
        # ever provisioned (`UnitPricingPanel.tsx`, and the same on S11 and the
        # schedule detail). So this branch is DEFENCE, correctly placed, and it
        # is not what was reported — see `DEF-3201` for both halves.
        satisfied, reason = True, "unconfigured"
    elif kind == kinds["match"]:
        satisfied, reason = True, "match"
    elif kind == kinds["dimension"]:
        # A factor is a SCALE. It never crosses a dimension, so this one stays
        # closed whatever is on file — the fix is a different unit, not a number.
        satisfied, reason = False, "dimension_mismatch"
    elif factor is not None:
        satisfied, reason = True, "conversion_factor"
    else:
        satisfied, reason = False, "mismatch_no_factor"
    return {
        "satisfied": satisfied,
        "reason": reason,
        "schedule_uom": schedule_uom,
        # The CONFIGURED column, unchanged in meaning — a caller that asks "what
        # did this tenant declare" still gets the declaration and not a derived
        # stand-in. `priced_against` is the derived one, and it is named.
        "billed_uom": billed,
        "register_uom": register,
        "priced_against": priced_against,
        "reconciliation": verdict,
        "conversion_factor": None if factor is None else str(factor),
    }


def plan_builder_queryset() -> QuerySet:
    """BR-RAT-031: the plan builder's schedule picker set — LIVE schedules that
    have an activated version. A draft (identity-only, or a dateless version
    holding a half-built structure) is invisible here until it is activated."""
    tenant_id = _tenant_id()
    activated = models.TariffVersion.objects.filter(
        tenant_id=tenant_id, effective_from__isnull=False
    ).values_list("tariff_id", flat=True)
    return models.Tariff.objects.filter(
        tenant_id=tenant_id, deleted_at__isnull=True, pk__in=list(activated)
    ).select_related("service")


def plan_builder_schedules(service_code: str | None = None) -> list[dict[str, Any]]:
    """S10 step-3 picker rows (US-RAT-002 §5 "Rate schedule per service")."""
    qs = plan_builder_queryset()
    if service_code:
        qs = qs.filter(service__code=service_code)
    return [
        {"id": str(tariff.id), "name": tariff.name, "service": tariff.service.code}
        for tariff in qs.order_by("name", "id")
    ]


def schedule_is_activated(tariff: models.Tariff) -> bool:
    """The picker predicate, applied server-side on the plan write path too —
    the rule is a rule, not a UI filter (BR-RAT-031)."""
    return plan_builder_queryset().filter(pk=tariff.pk).exists()


def rate_schedule_count(service_code: str | None = None, uom_code: str | None = None) -> int:
    """The tenancy seam contract (BR-TEN-026 disable guard · BR-TEN-027 change
    warning · BR-TEN-029 used-by): live count of live schedules touching a
    service and/or priced in a UoM."""
    qs = models.Tariff.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
    if service_code:
        qs = qs.filter(service__code=service_code)
    if uom_code:
        version_ids = models.TariffVersion.objects.filter(
            tenant_id=_tenant_id(), uom=uom_code
        ).values_list("tariff_id", flat=True)
        qs = qs.filter(pk__in=list(version_ids))
    return qs.count()


def tax_pricing_gap() -> dict[str, int]:
    """How many tax authorities this tenant has, and how many are PRICED —
    the tenancy seam behind S62's `rates_taxes` item (`DEF-254`).

    ⚠ **THIS EXISTS BECAUSE THE PRODUCT COULD NOT SEE ITS OWN SILENCE.** Tax
    JURISDICTIONS are seeded at provisioning — `tenancy.services
    .tax_jurisdiction_entries` writes the NAMES — and tax RATES are not: the
    `taxes` rows on the live estate were created by the RATING SAMPLE-DATA
    block, and `create_tax` is called from nowhere else. **So a tenant that
    declines the sample data has authorities and no rates, issues every bill
    with no tax at all, and nothing anywhere says so.**
    `apps/billing/issue.py` refuses a tax LINE whose authority has no liability
    account, BY NAME — and it cannot refuse a line that does not exist. No plan
    tax rule means no tax line means no refusal, so the gap is invisible
    precisely because it is an absence rather than a wrong value.

    ⚠ **A COUNT, NOT A JUDGEMENT, AND IT NEVER INVENTS A RATE.** The rate-less
    scaffold is a correct PO ruling — *a wrong rate charges real customers real
    money* — and this read must not be mistaken for permission to fill it in.
    `0 priced` is REPORTED so a human decides; a utility that genuinely charges
    no tax reads the same notice and does nothing, which is why the caller warns
    rather than refusing (decision log 2026-08-28).

    Live rows only on the priced side: a soft-deleted tax is not a price anybody
    charges. `tax_jurisdictions` carries no `deleted_at` column, so its count is
    every row it has.
    """
    tenant_id = _tenant_id()
    return {
        "jurisdictions": models.TaxJurisdiction.objects.filter(tenant_id=tenant_id).count(),
        "priced": models.Tax.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).count(),
    }


# ── Charge codes (US-RAT-008) ───────────────────────────────────────────────
def charge_or_404(charge_id: Any) -> models.Charge:
    if not _valid_uuid(charge_id):
        raise errors.NotFoundError()
    row = models.Charge.objects.filter(tenant_id=_tenant_id(), pk=charge_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


#: `CHG-01`'s Plans tab — how a charge code reaches a customer, and there are
#: exactly two ways. Served on every row so the screen prints a WORD and never
#: derives one from a blank column.
CHARGE_REACH_NAMED = "named"
CHARGE_REACH_BASE = "base"


def charge_reach_plan_ids(charge: models.Charge) -> tuple[set[Any], set[Any]]:
    """The two routes, as two sets of `rate_plans.id`, kept apart.

    **`CR-087` · `CHG-01` Plans tab.** A charge code reaches a customer by two
    routes and until today only one of them was ever counted:

      · **NAMED ON THE PLAN** — a `plan_charge_rules` row. This is what
        {@link charge_used_by} counts, and it is the whole of what the Overview
        tile has ever meant by *Plans carrying it*.
      · **THE BASE OF A RATE SCHEDULE** — `BR-RAT-088`, PO 2026-08-20: *"the
        CHARGE CODE owns the base amount; a plan displays it, never defines
        it."* A code that DECLARES itself its service's base (`is_base`) is
        read by every plan carrying a rate schedule for that service —
        `apps.billing.gather` walks `plan_rate_schedules(plan_id)` and asks
        `base_charge_from_charge_code(service_code, …)` per service line — and
        that plan names no charge rule at all.

    ⚠ **SO THE COUNT ON THE OVERVIEW TILE READS `0` FOR A CODE THAT PRICES
    EVERY CONNECTION ON ITS SERVICE**, which is the finding the blueprint
    reports in its own words and which is `DEF-RAT-4832`. This function is the
    honest answer; `charge_used_by` is left exactly as it was, because it feeds
    the DELETE lock (`services.delete_charge`) and widening a lock is a
    different decision from widening a screen count.

    **A plan can be on BOTH routes**, and the row says `named` when it is — the
    route a clerk can act on locally is the one worth naming, and the callout
    under the drawn table says the two behave differently under a change.

    ⚠ **THE BASE ROUTE NEEDS `is_base` AND A SERVICE, BOTH.** An account-level
    code (a late fee, an NSF) has no connection and no service, so it can be no
    service's base — `_guard_base_charge_code` already refuses one — and asking
    for its base route would return every plan in the utility.
    """
    named = set(
        models.PlanChargeRule.objects.filter(
            tenant_id=_tenant_id(), charge=charge
        ).values_list("rate_plan_id", flat=True)
    )
    base: set[Any] = set()
    if charge.is_base and charge.service_id is not None:
        base = set(
            models.PlanRateSchedule.objects.filter(
                tenant_id=_tenant_id(), service_id=charge.service_id
            ).values_list("rate_plan_id", flat=True)
        )
    return named, base - named


def charge_reach_queryset(charge: models.Charge) -> QuerySet:
    """Every plan this code reaches, as a QUERYSET, ordered for a screen.

    ⚠ **A QUERYSET, DELIBERATELY, AND FOR `plan_units_queryset`'s REASON —
    `NFR-3`.** DRF's paginator is handed this, so the envelope's `count` is a
    SQL `COUNT` over the WHOLE set and the page is a SQL `LIMIT`/`OFFSET`.
    Building a list here would materialise every plan of a 40,000-account
    tenant to render fifty of them, and the Overview tile's total and this
    table would then agree only by luck.

    ⚠ **NOTHING CAPS THE SET** (`NFR-5`): a code carried by every plan costs
    the same request as one carried by three.

    Ordered by plan NAME with the id last as `IS-2`'s stable secondary sort, so
    paging cannot show one plan twice and skip another.
    """
    named, base = charge_reach_plan_ids(charge)
    reach = named | base
    if not reach:
        return models.RatePlan.objects.none()
    return models.RatePlan.objects.filter(
        tenant_id=_tenant_id(), pk__in=list(reach)
    ).order_by("name", "id")


def charge_reach_rows(charge: models.Charge, plans: list[Any]) -> list[dict[str, Any]]:
    """ONE PAGE of plans, enriched into the rows the Plans tab draws.

    **The drawn four columns:** `PLAN` · `CODE` · `REACHED BY` · `UNITS`, and
    every one of them answers *who does this price change hit?* — which is the
    only question a clerk asks before touching a live amount.

    ⚠ **IT TAKES THE PAGE, NOT THE CHARGE'S WHOLE SET.** The caller has already
    paged in SQL; re-deriving the page here would decide the paging a second
    time, in a second place, and the two would drift (`plan_units_rows` states
    the same rule for the same reason).

    ⚠ **`units` COUNTS UNITS AND SAYS SO.** A plan is assigned to a UNIT —
    `unit_plan_assignments` — and `schedule_applied_to_accounts` next door
    counts exactly this shape under the word *accounts*, a mislabelling that
    reached four screens (`DEF-RAT-4664`). CURRENT means `assigned_to IS NULL`,
    the same predicate every other unit count in this module uses, so this
    table and the plan's own Units tab can never mean two different things.

    ⚠ **`plan_code` IS THE PLAN'S PRINTED REFERENCE, NEVER A DATABASE ID**
    (B14 rule 31). It is `null` on a base-route row on purpose: the plan does
    not NAME this charge code, so printing its own code beside *the base of a
    rate schedule* would read as an attachment that does not exist. The screen
    draws the absence.

    ⚠ **ONE QUERY FOR THE COUNTS, NOT ONE PER ROW.** Fifty plans on a page is
    fifty `COUNT(*)`s if this is written the obvious way; a single grouped
    count over the page's ids is one.
    """
    if not plans:
        return []
    named, _base = charge_reach_plan_ids(charge)
    plan_ids = [plan.id for plan in plans]
    counts: dict[Any, int] = {
        row["rate_plan_id"]: row["n"]
        for row in models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id__in=plan_ids, assigned_to__isnull=True
        )
        .values("rate_plan_id")
        .annotate(n=Count("id"))
    }
    # ── DEF-RAT-8752 (3) · CUSTOMER CLASS and ACCOUNTS (image 20) ───────────
    # The class is the PLAN's own targeting (`account_type_ids`; `[]` = every
    # class), printed by NAME through `seams.account_type_names` (B14 rule 31).
    # ACCOUNTS are the open accounts on the units the plan is assigned to now,
    # counted by customers (`seams.open_account_counts_by_unit`) — one grouped
    # query for the page; `None` when customers cannot answer, never 0.
    unit_rows = list(
        models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id__in=plan_ids, assigned_to__isnull=True
        ).values_list("rate_plan_id", "unit_id")
    )
    per_unit = seams.open_account_counts_by_unit([unit for _plan, unit in unit_rows])
    accounts: dict[Any, int | None] = {}
    for plan_id, unit_id in unit_rows:
        if per_unit is None:
            accounts[plan_id] = None
            continue
        accounts[plan_id] = (accounts.get(plan_id) or 0) + per_unit.get(str(unit_id), 0)
    class_names = seams.account_type_names(
        [one for plan in plans for one in (plan.account_type_ids or [])]
    )
    return [
        {
            "plan_id": str(plan.id),
            "plan_name": plan.name,
            # `named` decides the word AND the code cell, from one set, so the
            # two can never disagree about which route a row is on.
            "plan_code": plan.code if plan.id in named else None,
            "reached_by": CHARGE_REACH_NAMED if plan.id in named else CHARGE_REACH_BASE,
            "units": counts.get(plan.id, 0),
            # `[]` = every class; a class the tenant cannot name is left out.
            "customer_classes": [
                class_names[str(one)]
                for one in (plan.account_type_ids or [])
                if str(one) in class_names
            ],
            "accounts": (
                None if per_unit is None else accounts.get(plan.id, 0)
            ),
        }
        for plan in plans
    ]


def charge_used_by(charge: models.Charge) -> dict[str, Any]:
    """BR-RAT-035 audit-lock inputs: plan attachments (local) + invoice lines.

    ⚠ `invoice_lines` is `int | None` and the None is load-bearing (DEF-079).
    This docstring used to read *"0 while billing is unwired, by construction"*
    — true when written, false since billing grew `invoice_lines`, and while it
    stood the audit lock never engaged on a charge code appearing on real bills.
    None now means *billing could not answer*; `services.delete_charge` LOCKS on
    it and the S9 row renders it absent rather than as a confident 0.
    """
    plans = models.PlanChargeRule.objects.filter(tenant_id=_tenant_id(), charge=charge).count()
    return {
        "plans": plans,
        "invoice_lines": seams.invoice_line_references(charge.id),
        "schedules": _charge_is_base_for_schedules(charge),
    }


def _charge_is_base_for_schedules(charge: models.Charge) -> int:
    """How many rate schedules this code is the BASE for (`CR-087`, `BR-RAT-088`).

    ⚠ **A CODE THAT PRICES EVERY CONNECTION ON A SERVICE READ `0` AND WAS
    DELETABLE.** `charge_used_by` counted `PlanChargeRule` alone — the codes a
    plan ATTACHES by name — and `BR-RAT-088` made a second, larger kind of
    reference that has no row anywhere: *"the CHARGE CODE owns the base
    amount"*, resolved by `is_base` on the SERVICE. So `BASE-W`, the code every
    water schedule reads its base from, was referenced by zero plan-charge rules,
    reported as used by nobody, and the audit lock let it go.

    **What it would have cost, and it is `apps.billing.gather._base_charge_for`'s
    own order rather than a guess:** the charge code states the base *"Full
    stop"*; delete it and the resolution falls through to the plan, then to the
    schedule, then REFUSES — so every bill for that service either silently
    re-prices from a superseded column or stops. `BR-RAT-088`'s own worked
    figure for getting the base wrong on one service is **$23,069.50 a month
    across 1,247 connections**.

    **This counts a REFERENCE, not a row**, which is why it is a count of
    SCHEDULES rather than of some join table: `is_base` is declared per service,
    and every schedule on that service reads it. A code that is nobody's base
    returns 0 and the lock behaves exactly as it did.
    """
    if not charge.is_base or charge.service_id is None:
        return 0
    return models.Tariff.objects.filter(
        tenant_id=_tenant_id(), service_id=charge.service_id
    ).count()


def _penalty_pair_today(charge: models.Charge) -> tuple[Any, Any]:
    """`DEF-RAT-8827` — the (percent, minimum) a penalty code charges EVERY class
    today: its dated every-class terms row in force, else its two columns (the
    terms before any row). Only a percent rule can have one, so a flat code
    costs no query."""
    if charge.amount_rule not in ("percent", "percent_with_minimum"):
        return charge.percent, charge.min_amount
    terms = charge_prices.class_terms_on(charge, None)
    if terms is None:
        return charge.percent, charge.min_amount
    return terms.percent, terms.minimum


def charge_row(charge: models.Charge) -> dict[str, Any]:
    gl_code, gl_name = _gl_display(charge.gl_account_id)
    used = charge_used_by(charge)
    # ── CR-156-BRC10 · THE PRICES, READ THROUGH THE ONE LOOKUP ──────────────
    # `amount` is the every-class *All sizes* row in force TODAY (what the code
    # charges now); `size_amounts` the other rows in force today; `prices` the
    # whole dated history, killed rows included — what *View details → Prices*
    # shows and what makes an audit before/after of a scheduled reprice differ.
    today_rows = charge_prices.rows_in_force([charge], with_versions=True).get(charge.id, [])
    flat_rows = [row for row in today_rows if row.is_flat and row.customer_class is None]
    flat = flat_rows[0].amount if flat_rows else None
    history = charge_prices.history([charge]).get(charge.id, [])
    terms_today = charge_prices.terms_in_force([charge], with_versions=True).get(charge.id, [])
    # DEF-RAT-8827 — a penalty's EVERY-CLASS pair, once edited, is a dated terms
    # row naming no class; today's row (if any) is what the code charges now and
    # the two columns are the terms before any row. `class_terms` stays the
    # per-CLASS rows only, so a screen never reads a class-less row as a class.
    every_class_terms = next((row for row in terms_today if row.customer_class is None), None)
    terms_today = [row for row in terms_today if row.customer_class is not None]
    percent_now = every_class_terms.percent if every_class_terms is not None else charge.percent
    minimum_now = every_class_terms.min_amount if every_class_terms is not None else charge.min_amount
    return {
        "id": str(charge.id),
        "code": charge.code,
        "name": charge.name,
        "charge_type": charge.charge_type,
        "service": charge.service.code if charge.service_id else None,
        # BR-RAT-108 — WHICH customers this code prices. Served as itself, not
        # normalised: an EMPTY list ("every class") and a NAMED list are
        # different facts, and a screen must be able to draw the difference
        # rather than infer it. Same posture `tax_row` takes for its own copy.
        "applies_to_customer_classes": list(charge.applies_to_customer_classes or []),
        "amount_rule": charge.amount_rule,
        "amount": _money(flat),
        "percent": _money(percent_now),
        "min_amount": _money(minimum_now),
        "max_amount": _money(charge.max_amount),
        # BR-RAT-087 (DEF-364). The stored six-place values above are unchanged
        # and remain the contract for anything that computes; these are what a
        # screen renders. Both are served so neither side has to guess.
        "amount_display": _display_money(flat),
        "percent_display": _display_percent(percent_now),
        "min_amount_display": _display_money(minimum_now),
        "max_amount_display": _display_money(charge.max_amount),
        "gl_account_id": _uuid_or_none(charge.gl_account_id),
        # ── WHAT A PERSON SEES INSTEAD OF THAT UUID (PO 2026-09-17) ─────────
        # `gl_account_id` stays on the row: it is the write path's value and the
        # form posts it back. These two are for the SCREEN, and a screen that
        # prints the id instead breaks B14 rule 31.
        "gl_account_code": gl_code,
        "gl_account_name": gl_name,
        # BR-RAT-088 — DECLARED, never inferred from the code string. The column
        # and the activation gate that reads it (`_guard_base_charge_code`) both
        # exist, and until DEF-372 NOTHING SERVED OR ACCEPTED THE FLAG: a tenant
        # could not declare a base at all, so the gate could never fire on any
        # tenant. Hard-won law 2, built-not-wired. Serving it is what lets CHG-02
        # offer the checkbox §A3 requires.
        "is_base": charge.is_base,
        # DEF-431 · §B3's per-size amount table, SERVED. `charge_code_amounts`
        # shipped with migration 0010 and had no reader and no writer, so every
        # screen that draws a base against a connection size drew the ONE scalar
        # above against all of them. r10's water matrix prices 5/8" at $12.00 and
        # 2" at $64.00 — one scalar is wrong by $52.00 a month on the largest
        # size, and the table being EMPTY is what hid it: with no rows, a per-size
        # read and a scalar read agree for every tenant, so no test written today
        # can tell them apart.
        #
        # An EMPTY list means "this code does not vary by size" and the scalar
        # above is the amount — which is what every charge code in the database
        # says today, so this is additive and changes no figure anywhere.
        #
        # ⚠ NULL `amount` ON A ROW IS NOT ZERO, one column across from DEF-277:
        # a row that EXISTS with a null amount says the utility does not serve
        # that size, and R4 refuses rather than billing $0.00 for it. Served as
        # null, never as "0.00", so a screen renders the absence.
        # ⚠ **THIS IS THE SECOND PLACE `size_amounts` IS BUILT AND THE TWO MUST
        # AGREE** — `_charge_size_amounts` above serves the same list for the
        # plan detail's charge rules. CR-087 A1 added `customer_class` and it had
        # to be added TWICE; a reader who adds a third key here and not there
        # ships a field that exists on one screen. Named rather than merged,
        # because merging them is its own change with its own proving run.
        "size_amounts": [
            _price_row_json(row)
            for row in today_rows
            if not (row.is_flat and row.customer_class is None)
        ],
        # CR-156-BRC10 — the KIND (base · plan · other) and the full dated
        # price history. `price_range` is what the list shows instead of a
        # misleading `0.00` for a sized code (decision log 2026-10-01, *"BASE-T
        # reads $9.00 – $40.00"*): the smallest and largest amount in force
        # today, None when the code states no price.
        "kind": charge.kind,
        # DEF-RAT-8753 — a penalty priced BY CUSTOMER CLASS: today's terms
        # rows (percent + minimum per class), `[]` for every other code. The
        # code's own `percent` / `min_amount` above are its ONE-amount terms.
        "class_terms": [_price_row_json(row) for row in terms_today],
        "prices": [_price_row_json(row) for row in history],
        "price_range": _price_range(today_rows),
        "taxable_default": charge.taxable_default,
        "auto_apply": charge.auto_apply,
        "waivable": charge.waivable,
        "separate_line": charge.separate_line,
        # 🔒 PO ruling 2026-10-06 11 (a) — a PENALTY code's late-fee grace, as
        # stored (NULL on every other type). Billing reads it through
        # `plan_late_fee_terms`; the screens print it beside the code.
        "grace_days": charge.grace_days,
        "grace_mode": charge.grace_mode,
        # 🔒 DEF-CUS-9819 (PO 2026-10-06) — the utility's application fee code.
        "is_application_fee": bool(charge.is_application_fee),
        # 🔒 DEF-PAY-10698 (PO 2026-10-30) — a returned-payment (NSF) fee code.
        "is_nsf_fee": bool(charge.is_nsf_fee),
        "status": "inactive" if charge.deleted_at else "active",
        "used_by_plans": used["plans"],
        "used_by_invoice_lines": used["invoice_lines"],
        # ⚠ **`BR-RAT-088`'s ROUTE, SERVED — WITHOUT IT A SCREEN CANNOT TELL
        # THAT A BASE CODE IS IN USE (`BR-RAT-1016`).** `used_by_plans` counts
        # `plan_charge_rules`, the codes a plan NAMES; a code that declares
        # itself its service's base is read by every schedule on that service
        # and names nothing, so it read `0 · 0` here while pricing every
        # connection. `update_charge` now REFUSES a price move on such a code
        # without a written reason, and a screen that cannot see the use cannot
        # offer the box the refusal lands on — which is the road ending, the
        # shape `DEF-384` was filed for one object over.
        "used_by_schedules": used["schedules"],
    }


def base_code_price_rows(service_code: str, on_date: date | None = None) -> list[dict[str, Any]]:
    """`CR-156-BRC10` — every base charge code of a service with its price rows
    in force on `on_date` (default: the tenant's today), each row carrying its
    size, class, amount, **Effective from / Effective to and its version**.

    PO 2026-10-01 (decision log *"BASE CHARGES SHOWS EACH SIZE'S BASE-PRICE
    VERSION AND ITS EFFECTIVE DATES"*): the rate-schedule screen shows, per size
    of the base code, the version and the dates — e.g. BASE-W 5/8" $8.00 v1
    01/01/2026 → No end · 1" $11.50 v2 09/01/2026 → No end — and reads them
    rather than working them out. Retired codes are left out. One query for the
    codes and two for every price row and version (`charge_prices`).
    """
    charges = list(
        models.Charge.objects.filter(
            tenant_id=_tenant_id(),
            is_base=True,
            deleted_at__isnull=True,
            service__code=service_code,
        ).order_by("code", "id")
    )
    rows = charge_prices.rows_in_force(charges, on_date, with_versions=True)
    return [
        {
            "id": str(charge.id),
            "code": charge.code,
            "name": charge.name,
            "customer_classes": list(charge.applies_to_customer_classes or []),
            "prices": [_price_row_json(row) for row in rows.get(charge.id, [])],
        }
        for charge in charges
    ]


def charge_in_use(used: dict[str, Any]) -> bool:
    """Has this code ever priced anything — `BR-RAT-1016`'s boundary, one
    definition (`services.charge_is_in_use` delegates here). A plan names it,
    a schedule reads it as its service's base, or a bill carries it; an
    invoice count billing could not answer (`None`) counts as in use."""
    if used["plans"] or used["schedules"]:
        return True
    lines = used["invoice_lines"]
    return lines is None or lines > 0


def charge_code_picker(kind: str, service: str | None = None) -> list[dict[str, Any]]:
    """`CR-156-BRC10` — the codes the charge-code *Add* picker offers.

    PO 2026-10-01, verbatim: *"when user select code from list show what are
    not in use only"* — **a code already in use is left out entirely, not
    shown disabled.** Worked: a plan charge lists `TRANSFER`, `MOVE-OUT`,
    `CC-CONV`, `PAPER`, `HYDRANT` and leaves out the in-use `CONN`, `DISC`,
    `RECON`, `LATE`, `NSF`, `TAMPER`, `DEPOSIT`; a trash base lists nothing
    while `BASE-T` is in use.

    **The Settings codes ARE the `charges` rows** (`seed_reference_list` and
    the S8 card mint them there, code · name · type), so the picker is that
    table, narrowed:

      * by KIND — the asked kind, or no kind yet (a code minted on Settings and
        never configured here: *"in setting we will not make any change"*);
      * for a BASE, by SERVICE — *"base charge will be for 1 Utility service"*
        — the asked service, or a code naming no service;
      * by USE — `charge_in_use`'s own boundary (a plan names it, a schedule
        reads it, a bill carries it). *"In use"* is read as THIS, the
        product's existing meaning, rather than *"has a price"*: every seeded
        code has a price, and the PO's worked list leaves out exactly the codes
        plans name (`LATE`, `NSF` …) while offering priced ones (`TRANSFER`
        $15.00). Recorded as this lane's reading in the decision log.
      * retired codes are not offered.

    Each code costs one invoice-line count through billing's seam; a tenant's
    catalogue is tens of codes, not thousands (NFR-3 does not bite a picker
    whose rows are bounded by what a utility has minted).
    """
    qs = (
        models.Charge.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .filter(Q(kind=kind) | Q(kind__isnull=True))
        .select_related("service")
        .order_by("code", "id")
    )
    if kind == "base" and service:
        qs = qs.filter(Q(service__code=service) | Q(service__isnull=True))
    out: list[dict[str, Any]] = []
    for charge in qs:
        if charge_in_use(charge_used_by(charge)):
            continue
        out.append(
            {
                "id": str(charge.id),
                "code": charge.code,
                "name": charge.name,
                "charge_type": charge.charge_type,
                "kind": charge.kind,
                "service": charge.service.code if charge.service_id else None,
            }
        )
    return out


def _price_range(rows: list[Any]) -> dict[str, Any] | None:
    amounts = [row.amount for row in rows if row.amount is not None]
    if not amounts:
        return None
    low, high = min(amounts), max(amounts)
    return {
        "low": _money(low),
        "high": _money(high),
        "low_display": _display_money(low),
        "high_display": _display_money(high),
        "priced_by": "size" if any(not row.is_flat for row in rows) else (
            "customer_class" if any(row.customer_class for row in rows) else "flat"
        ),
        "rows": len(rows),
    }


def charge_list_queryset(params: ListParams) -> QuerySet:
    """The S9 Charge-codes tab AS A QUERYSET (`NFR-3`, `DEF-RAT-5742`).

    Every declared charge filter (`type`, `service`, `status`) and every
    declared sort is a column, so the whole read is SQL and `charge_page` has
    no derived path to fall back to.

    ⚠ **`BR-RAT-088` IS UNTOUCHED BY THIS SPLIT.** The charge code still owns
    the base amount; `charge_row` is the one place that answers what a code is
    worth, and it is called with exactly the same rows in exactly the same
    order as before — only fewer of them.
    """
    qs = models.Charge.objects.filter(tenant_id=_tenant_id()).select_related("service")
    term = params.q.strip()
    if len(term) >= MIN_SEARCH_CHARS:
        qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
    charge_type = params.filters.get("type")
    if charge_type and charge_type.lower() != "all":
        qs = qs.filter(charge_type=charge_type.lower())
    services = filter_values(params.filters.get("service"))  # OQ-306 — ANY of
    if services:
        qs = qs.filter(service__code__in=services)
    status = params.filters.get("status")
    if status == "active":
        qs = qs.filter(deleted_at__isnull=True)
    elif status == "inactive":
        qs = qs.filter(deleted_at__isnull=False)
    # CR-156-BRC10 — the list's new *Kind* column filters like the others.
    kind = params.filters.get("kind")
    if kind and kind.lower() != "all":
        qs = qs.filter(kind=kind.lower())
    field = {
        "code": "code",
        "description": "name",
        "type": "charge_type",
        # CR-156-BRC10 — `charges.amount` is no longer the price; the sort
        # reads today's flat row, else the smallest sized row, in SQL (NFR-3)
        # through the one lookup's own expression.
        "amount": "sort_amount",
        # CR-156-BRC10 — the list's *Kind* column sorts like the others.
        "kind": "kind",
    }.get(params.sort or CHARGE_DEFAULT_SORT, "code")
    if field == "sort_amount":
        qs = qs.annotate(sort_amount=charge_prices.amount_sort_expression())
    prefix = "-" if params.dir == "desc" else ""
    return qs.order_by(f"{prefix}{field}", "id")


def charge_kind_counts(params: ListParams) -> dict[str, int]:
    """`CR-156-BRC10` · the list's *All · Base · Plan · Other* chips — how many
    codes of each kind match EVERY OTHER filter and the search, so pressing a
    chip never shows a count the table then contradicts.

    One `GROUP BY` statement over the same queryset the table pages
    (`charge_list_queryset` with the kind filter taken off). A code minted on
    Settings and never configured here has no kind yet: it counts in *All* and
    in no chip, which is what its blank *Kind* cell says.
    """
    unkinded = ListParams(
        q=params.q,
        sort="code",
        dir="asc",
        page=1,
        per=params.per,
        filters={key: value for key, value in params.filters.items() if key != "kind"},
    )
    counts = {"all": 0, "base": 0, "plan": 0, "other": 0}
    rows = charge_list_queryset(unkinded).order_by().values("kind").annotate(n=Count("id"))
    for row in rows:
        counts["all"] += int(row["n"])
        if row["kind"] in counts:
            counts[row["kind"]] += int(row["n"])
    return counts


def _version_figure(row: Any) -> str | None:
    """One price row's figure as the Audit tab prints it: the amount, or for a
    penalty's class terms (`DEF-RAT-8753`) `1.50% · $5.00` (`· —` without a
    floor)."""
    if getattr(row, "percent", None) is None:
        return _display_money(row.amount)
    floor = _display_money(row.min_amount)
    return f"{_display_percent(row.percent)} · {'$' + floor if floor else '—'}"


def charge_versions(charge: models.Charge) -> list[dict[str, Any]]:
    """`CR-156-BRC10` · CHG-01's *Audit* tab — the code's PRICE VERSIONS, newest
    first: one row per date a price started, with its window, its state, what
    moved and who moved it and why.

    Read from the two places that hold it and nothing else: the dated price
    rows (`charge_prices.history`, killed rows included) and `rate_change_log`
    (written for every money change since wave A). A version is the set of rows
    that START on one day; it ends the day before the next one starts. An
    EMPTY row (superseded before it began) prices no day and is no version.

    **Who and why** come from the log row whose save CREATED one of the
    version's rows (a price id in its `after` and not in its `before`); the
    rows a code was created with, or moved in by the one-time backfill, have no
    such log row, so their *who* and *why* are absent rather than invented.
    """
    today = seams.tenant_today()
    rows = [row for row in charge_prices.history([charge]).get(charge.id, []) if not row.is_empty]
    if not rows:
        return []
    by_key: dict[tuple[str, str | None], list[Any]] = {}
    for row in sorted(rows, key=lambda r: r.effective_from):
        by_key.setdefault((row.size_class, row.customer_class), []).append(row)
    starts = sorted({row.effective_from for row in rows})
    logs = list(
        models.RateChangeLog.objects.filter(
            tenant_id=_tenant_id(), entity_type="charge", entity_id=charge.id
        ).order_by("created_at")
    )

    def _price_ids(snapshot: Any) -> set[str]:
        if not isinstance(snapshot, dict):
            return set()
        return {str(p.get("id")) for p in snapshot.get("prices") or [] if isinstance(p, dict)}

    created_by: dict[str, Any] = {}
    for entry in logs:
        for price_id in _price_ids(entry.after) - _price_ids(entry.before):
            created_by.setdefault(price_id, entry)
    names = seams.user_display_names([entry.actor_id for entry in logs if entry.actor_id])
    out: list[dict[str, Any]] = []
    for index, start in enumerate(starts):
        group = [row for row in rows if row.effective_from == start]
        nxt = starts[index + 1] if index + 1 < len(starts) else None
        ends = [row.effective_to for row in group]
        if nxt is not None:
            end = nxt - timedelta(days=1)
        elif ends and all(e is not None for e in ends):
            end = max(e for e in ends if e is not None)
        else:
            end = None
        if start > today:
            state = "scheduled"
        elif end is not None and end < today:
            state = "ended"
        else:
            state = "in_force"
        changes = []
        for row in sorted(group, key=lambda r: (r.size_class, r.customer_class or "")):
            earlier = [
                r for r in by_key[(row.size_class, row.customer_class)]
                if r.effective_from < row.effective_from
            ]
            before = earlier[-1] if earlier else None
            changes.append(
                {
                    "size_class": row.size_class,
                    "customer_class": row.customer_class,
                    "before_display": _version_figure(before) if before else None,
                    "after_display": _version_figure(row),
                    "new": before is None,
                    # DEF-RAT-8753 — a penalty's class terms read `1.50% · $5.00`,
                    # composed here; the screen prints it as it is. The key is
                    # present only on a terms row, so every other change keeps
                    # the shape wave B served.
                    **({"terms": True} if row.percent is not None else {}),
                }
            )
        entry = next((created_by[str(row.id)] for row in group if str(row.id) in created_by), None)
        out.append(
            {
                "effective_from": start.isoformat(),
                "effective_to": end.isoformat() if end else None,
                "state": state,
                "created": index == 0,
                "changes": changes,
                "who": names.get(str(entry.actor_id)) if entry and entry.actor_id else None,
                "why": (entry.reason or None) if entry else None,
            }
        )
    out.reverse()
    return out


def charge_detail(charge: models.Charge) -> dict[str, Any]:
    """`CR-156-BRC10` · `GET /charges/{id}` — the row every save returns, plus
    what only View details draws: last month's tiles (from billing, `None` when
    billing cannot answer) and the price versions of the *Audit* tab. The list
    stays on `charge_row`, so neither read is paid once per list row."""
    row = charge_row(charge)
    usage = seams.charge_usage_last_month(charge.id)
    row["usage"] = (
        None
        if usage is None
        else {
            "bills": usage["bills"],
            "lines": usage["lines"],
            "revenue": _money(usage["revenue"]),
            "revenue_display": _display_money(usage["revenue"]),
        }
    )
    row["versions"] = charge_versions(charge)
    row["size_minimums"] = base_code_size_minimums(charge)
    # 2026-10-06 11 (a) — *"The Settings default stays as the starting value
    # for new codes"*: what the form starts Grace at when Type becomes Penalty.
    default_days, default_mode = seams.late_grace_default()
    row["grace_default"] = {"days": default_days, "mode": default_mode}
    return row


#: `size_minimums[size].state` — why the Minimum cell reads what it reads.
#: Zero words on screen (B14 rule 33): the screen prints a figure, a range or a
#: dash, and these say which, for the code and the tests.
MINIMUM_ONE = "one"  # every schedule on the service states the same figure
MINIMUM_RANGE = "range"  # every schedule states one, and they differ: low – high
MINIMUM_NONE = "none"  # no schedule floors this size
MINIMUM_MIXED = "mixed"  # some schedules floor it and some do not: no figure is true


def base_code_size_minimums(charge: models.Charge, on_date: date | None = None) -> dict[str, Any]:
    """`DEF-RAT-8752` (1) — the read-only *Minimum* beside a base code's size
    prices (images 11 and 51), per size, from the RATE SCHEDULES that use it.

    Since `DEF-RAT-8737` (`2.433.0`, PO 2026-10-01 *"A · Minimum per size -
    this is correct"*) the minimum lives on each schedule version's size rows
    (`rate_size_rows.minimum_bill`, read by billing through `_size_minimum`). A
    base code is read by EVERY schedule on its service (`BR-RAT-088`), so one
    size can carry several minimums. Per size, over the version of each
    schedule in force on `on_date` (default today):

      * all state the same figure → that figure (`one`);
      * all state one and they differ → the range `low – high` (`range`);
      * none states one → no figure (`none`);
      * some do and some do not → no figure (`mixed`): a single number or a
        range would claim every connection of that size is floored, and one
        schedule's connections are not.

    `{}` for a code that is not its service's base. Read-only; never on a
    billing path (billing reads `_size_minimum` per version)."""
    if not charge.is_base or charge.service_id is None:
        return {}
    return service_size_minimums(charge.service_id, on_date)


def service_size_minimums(
    service_id: Any = None, on_date: date | None = None, *, service_code: str | None = None
) -> dict[str, Any]:
    """`base_code_size_minimums`' answer for a SERVICE (by id, or by code) —
    what the Add wizard's step 2 reads before any code is the service's base
    (image 51), served on `GET /charges/picker?kind=base&service=`. Same rule,
    same states."""
    day = on_date or seams.tenant_today()
    stated: dict[str, list[Decimal | None]] = {}
    schedules = 0
    tariffs = models.Tariff.objects.filter(tenant_id=_tenant_id())
    tariffs = (
        tariffs.filter(service__code=service_code)
        if service_code is not None
        else tariffs.filter(service_id=service_id)
    )
    for tariff in tariffs:
        version = in_force_version(tariff, day)
        if version is None:
            continue
        schedules += 1
        for size_class, minimum in models.RateSizeRow.objects.filter(
            tenant_id=_tenant_id(), tariff_version=version
        ).values_list("size_class", "minimum_bill"):
            stated.setdefault(size_class, []).append(minimum)
    out: dict[str, Any] = {}
    for size_class, values in stated.items():
        # A schedule with no row for this size floors nothing for it either.
        values = values + [None] * (schedules - len(values))
        figures = [value for value in values if value is not None]
        if not figures:
            state, low, high = MINIMUM_NONE, None, None
        elif len(figures) < len(values):
            state, low, high = MINIMUM_MIXED, None, None
        else:
            low, high = min(figures), max(figures)
            state = MINIMUM_ONE if low == high else MINIMUM_RANGE
        out[size_class] = {
            "state": state,
            "low": _money(low),
            "high": _money(high),
            "low_display": _display_money(low),
            "high_display": _display_money(high),
            "schedules": schedules,
        }
    return out


def charge_list(params: ListParams) -> list[dict[str, Any]]:
    """EVERY matching charge code, ordered — the stable API and the CSV export.
    `seed_demo` and `sample_data` read it with `per=1000` to index the catalogue;
    a SCREEN wants `charge_page`."""
    return _page([charge_row(row) for row in charge_list_queryset(params)], params)


def charge_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """`(one page of charge-code rows, the whole result set count)` — `NFR-3`."""
    return _sql_page(
        charge_list_queryset(params), params, lambda rows: [charge_row(row) for row in rows]
    )


# ── Taxes & fees (US-RAT-009) ───────────────────────────────────────────────
def tax_or_404(tax_id: Any) -> models.Tax:
    if not _valid_uuid(tax_id):
        raise errors.NotFoundError()
    row = models.Tax.objects.filter(tenant_id=_tenant_id(), pk=tax_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def tax_authority_id_for_tax(tax_id: Any) -> str | None:
    """WHICH AUTHORITY a tax line's money is owed to — `P0.3`, the third stamp.

    **THIS IS THE ONE HOP THAT WAS MISSING, AND IT HAD BEEN ASKED FOR BY NAME
    FOR SIX WEEKS.** `apps/billing/posting_seam.py` has declared this exact
    contract since 2026-08-11 —

        apps.rating.selectors.tax_authority_id_for_tax(tax_id) -> str | None

    — resolves it by name at call time, and reports
    `tax_bucket_names_no_authority` on every issue entry while nothing answers.
    `apps/ledger/posting.py` names the same gap from the other side. The
    result: `journal_lines.tax_authority_id` was **NULL on every line the
    product has ever written** — measured on the seeded database (PostgreSQL
    16.13, 2026-09-24): **0 of 661** — the by-authority tax report could not
    be built from the books, and `US-LED-002` TC-5's refusal could not even be
    written, because there were no rows for it to recognise.

    Nothing on either side of the seam changes: billing already calls it and
    already handles `None`. Publishing this function is the whole change.

    **WHY A TAX ROW AND A JURISDICTION ARE DIFFERENT THINGS.** An invoice line
    names its `taxes` ROW (`invoice_lines.tax_id`, `BR-BIL-069`) — a rate, a
    basis and a period. `journal_lines.tax_authority_id` names the JURISDICTION
    the money is remitted TO. One authority levies several taxes, so the hop is
    real, and only this module can make it (`B1`: billing may not read rating's
    ORM).

    ⚠ **NOT DERIVED FROM THE GL CODE AND NOT PARSED OUT OF A DESCRIPTION.**
    That was option D of `OQ-116` and the PO declined it. It is read off
    `taxes.jurisdiction_id` or it is `None`.

    **`None` IS A REAL ANSWER AND MUST STAY ONE.** A tax whose jurisdiction is
    unset, and a `tax_id` naming nothing in THIS tenant, both return `None`;
    the caller then writes no authority rather than a guess, which is exactly
    what it does today. Tenant-scoped (hard rule 1) — a tax id belonging to
    another tenant is simply not found, never leaked.
    """
    if not _valid_uuid(tax_id):
        return None
    jurisdiction_id = (
        models.Tax.objects.filter(tenant_id=_tenant_id(), pk=tax_id)
        .values_list("jurisdiction_id", flat=True)
        .first()
    )
    return str(jurisdiction_id) if jurisdiction_id else None


def jurisdiction_row(jurisdiction: models.TaxJurisdiction) -> dict[str, Any]:
    return {
        "id": str(jurisdiction.id),
        "name": jurisdiction.name,
        "authority": jurisdiction.authority,
        "level": jurisdiction.level,
        "reference_no": jurisdiction.reference_no,
    }


def jurisdiction_list_queryset(params: ListParams) -> QuerySet:
    """The tenant's jurisdictions AS A QUERYSET (`NFR-3`, `DEF-RAT-5754`).

    Every predicate is a column on `tax_jurisdictions`, so the whole read is
    SQL and `jurisdiction_page` has no derived path to fall back to — the
    charge-codes shape, not the taxes one.

    ⚠ **THE DEFAULT ORDER IS THE ONE THIS ENDPOINT HAS ALWAYS SERVED** —
    `name`, then `id` as the tiebreaker. That is not tidiness: without a total
    order a `LIMIT`/`OFFSET` may return the same row on two pages and omit a
    third, which on a picker means a jurisdiction that exists and cannot be
    chosen. `jurisdiction_list` below reads this same function, so the whole
    set and any page of it can never disagree about order.

    ⚠ **SEARCH REACHES `authority` AND `reference_no`, NOT ONLY `name`.** A
    clerk configuring a tax knows *"Texas Comptroller"* or the permit number
    off the paperwork in front of them; `TaxesFeesTab` already lets the tax
    list be searched by authority THROUGH this FK for exactly that reason, and
    the two searches answering differently about the same object is the
    disagreement `DEF-387` is about.
    """
    qs = models.TaxJurisdiction.objects.filter(tenant_id=_tenant_id())
    term = params.q.strip()
    if len(term) >= MIN_SEARCH_CHARS:
        qs = qs.filter(
            Q(name__icontains=term)
            | Q(authority__icontains=term)
            | Q(reference_no__icontains=term)
        )
    field = {"name": "name", "authority": "authority", "level": "level"}.get(
        params.sort or JURISDICTION_DEFAULT_SORT, "name"
    )
    prefix = "-" if params.dir == "desc" else ""
    return qs.order_by(f"{prefix}{field}", "id")


def jurisdiction_list(params: ListParams | None = None) -> list[dict[str, Any]]:
    """EVERY matching jurisdiction, ordered — BR-TEN-037: tenant-entered, no
    global registry, this tenant's only.

    ⚠ **THE PARAMETER IS OPTIONAL AND THE NO-ARGUMENT CALL IS UNCHANGED**
    (`DEF-RAT-5754`). Five callers read this as the WHOLE set and none of them
    passes anything — `seed_demo` three times, `sample_data` twice — so
    widening the signature rather than replacing it is what keeps them working
    and keeps `jurisdiction_page` from being a second implementation of the
    filter. A SCREEN or a PICKER wants `jurisdiction_page`.
    """
    effective = params or ListParams()
    return _page(
        [jurisdiction_row(row) for row in jurisdiction_list_queryset(effective)], effective
    )


def jurisdiction_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """`(one page of jurisdiction rows, the whole result set count)` — `NFR-3`.

    ⚠ **THE PICKER THAT CONSUMES THIS STILL SEES EVERY ROW, AND THAT IS THE
    POINT OF THE PAIR** (`BR-SHL-033`). `getTaxJurisdictions` follows `count`
    until it holds the whole set, exactly as `/routes` and `/cycles` do, so the
    S13 step-1 type-ahead can still find a jurisdiction that is not on page 1
    and editing a tax still resolves its jurisdiction's LABEL. What changed is
    that no single response is unbounded any more; what did not change is what
    the clerk can choose.
    """
    return _sql_page(
        jurisdiction_list_queryset(params),
        params,
        lambda rows: [jurisdiction_row(row) for row in rows],
    )


#: CR-013 part 4's landing statuses, plus the one the product already had.
#: Part 4 names FOUR — Active / Draft / Scheduled / Expired — and the screen
#: inventory's own note says taxes are *"a FOURTH status set, and it is a
#: different one again"*. `inactive` is the FIFTH value and it is not an
#: invention: IS-1's deactivate-first pattern has served it from this selector
#: since US-RAT-009 shipped, the S13 row action reads it, and dropping it would
#: make a deactivated tax indistinguishable from a live one. `schedule_state`
#: does exactly the same thing one object over, adding `archived` beyond
#: US-RAT-004's ratified set for the same reason.
TAX_STATUSES: tuple[str, ...] = ("active", "draft", "scheduled", "expired", "inactive")


def tax_status(tax: models.Tax, today: date | None = None) -> str:
    """DEF-387 — the four-value lifecycle, DERIVED, like `schedule_state`.

    `tax_row` used to answer `"inactive" if tax.deleted_at else "active"`,
    ignoring `effective_from` and `effective_to` entirely, so *"Save &
    schedule"* had no state to write and the rate-calendar strip nothing to
    read.

    ── WHY DERIVED AND NOT STORED ────────────────────────────────────────────
    A rate schedule's status is derived (`schedule_state`: in-force version →
    active, none → draft, future version → a scheduled note) precisely so that
    a status column can never disagree with the dates the engine actually
    prices from. Four objects in this product have four different status
    vocabularies, each with a reason; they should at least agree on where a
    status COMES FROM. Three of these four are already stored facts.

    ── THE FOURTH IS STORED, AND THAT IS NOT AN INCONSISTENCY ────────────────
    DEF-387's suggested fix read `draft` as *"no effective_from"*. That is
    wrong on this product's own data: the five ruled Texas rates are seeded
    with NO `effective_from` and are pricing bills right now, so it would print
    **Draft** over the State Utility Tax while it charges 6.25 %. "Nobody has
    put this into force yet" is not a date and cannot be recovered from one —
    it is `taxes.is_draft`, a flag that DEFAULTS TO FALSE so that every row any
    code path creates is in force exactly as it is today, and the only way to
    get a draft is to ask for one. The model docstring records why the first
    attempt (a nullable `activated_at`) was the same bug pointing at bills.

    ── ORDER MATTERS, AND IT IS THE ORDER A HUMAN WOULD READ ─────────────────
    Deactivation beats everything (it is a deliberate human act on this row);
    then draft (never in force, so a window on it means nothing); then the
    window, whose ends are checked before its middle. A tax that is both
    expired and scheduled cannot exist — `_validate_tax` refuses an inverted
    window — so no tie needs breaking.

    `today` is the TENANT's (BR-TEN-043: event-time law, read at display time),
    never `date.today()`.

    ── ⚠ THE VOCABULARY MOVED ON 2026-10-03 (CR-165-BRC10 round 2, §9) ──────
    It read `inactive | draft | expired | scheduled | active`. The redesign's
    API contract is `draft | active | scheduled | ended | superseded`:
    *expired* is now **ended** (the drawing's word, and what Retire produces),
    a row a correction replaced reads **superseded** rather than `active` (the
    versions read reported a superseded row as active — CR §6 d), and a
    DEACTIVATED row reads **ended**, because since `DEF-RAT-9279` it prices
    nothing, which is what *ended* means. `active` (the deactivation flag) is
    still served on its own field beside this one.
    """
    today = today or seams.tenant_today()
    if tax.superseded_by_id is not None:
        return "superseded"
    if tax.deleted_at is not None:
        return "ended"
    if tax.is_draft:
        return "draft"
    if tax.effective_to is not None and tax.effective_to < today:
        return "ended"
    if tax.effective_from is not None and tax.effective_from > today:
        return "scheduled"
    return "active"


def tax_in_force(tax: models.Tax, service_date: date | None = None) -> bool:
    """⚠ DEF-483 — DOES THIS TAX PRICE A BILL WHOSE SERVICE DATE IS THIS ONE?

    **The window was stored and never read.** `plan_tax_rules` resolved a tax by
    jurisdiction and kind with no date predicate at all, and its docstring still
    claimed *"taxes carries no effective-dating columns, so there is nothing to
    filter on"* — a sentence that was true when written and had been false since
    r6.5. So a rate saved to start next January was charged on today's bill, and
    one whose `effective_to` had passed kept charging for ever. It was invisible
    because every seeded and fixture tax is UNDATED, which makes the missing
    predicate the identity on all existing data — the same shape as
    BR-RAT-101's `jurisdiction_factor` of 1.0.

    ── WHAT EACH NULL MEANS, AND WHY NO FIGURE MOVES ─────────────────────────
    A NULL bound is **no bound stated**, not a bound of zero: `effective_from`
    NULL = "since always", `effective_to` NULL = "until further notice". That is
    what every existing row carries, so every existing row is in force exactly
    as it was and golden stays 33/33. Only a row somebody DATED changes, and it
    changes to what the utility typed.

    ── WHAT IS DELIBERATELY *NOT* TESTED HERE ────────────────────────────────
    ~~`deleted_at`~~ — ⚠ **THIS PARAGRAPH READ *"`deleted_at`. Whether a
    DEACTIVATED tax should still price a bill is a pre-existing question …
    It stays declined and stays named."* AND IT IS ANSWERED (`DEF-RAT-9279`,
    CR-165-BRC10 round 2, 2026-10-03).** The decline lived only in this
    docstring and was never a register row, so nothing counted it — and the
    redesign's *Retire* would have inherited it: a 2% county tax deactivated on
    10/01/2026 still added **$1.20** to a $60.00 October bill. A deactivated
    row is now NOT in force. *Retire* (`services.retire_tax`) ends the window
    instead of setting `deleted_at`, so a retired tax keeps pricing the bills
    dated before its end — which is what retiring means; deactivation stays the
    blunt instrument it always looked like on screen.
    """
    if tax.deleted_at is not None:
        return False  # DEF-RAT-9279 — deactivated rows price nothing
    if tax.is_draft:
        return False  # nobody has put this into force
    if tax.superseded_by_id is not None:
        return False  # DEF-384 — corrected; the correction row prices instead
    on = service_date or seams.tenant_today()
    if tax.effective_from is not None and tax.effective_from > on:
        return False
    if tax.effective_to is not None and tax.effective_to < on:
        return False
    return True


def tax_row(tax: models.Tax) -> dict[str, Any]:
    gl_code, gl_name = _gl_display(tax.liability_gl_account_id)
    return {
        "id": str(tax.id),
        "name": tax.name,
        "jurisdiction": (
            jurisdiction_row(tax.jurisdiction) if tax.jurisdiction_id is not None else None
        ),
        "kind": tax.kind,
        "rate": _money(tax.rate),
        # BR-RAT-087 (DEF-364 / DEF-291): the Taxes screen stated a rate as
        # "0.062500 of the taxable base". It reads 6.25% now.
        "rate_display": _display_percent(tax.rate),
        "base_includes_usage": tax.base_includes_usage,
        "base_includes_base": tax.base_includes_base,
        "flat_amount": _money(tax.flat_amount),
        "flat_frequency": tax.flat_frequency,
        "per_unit_amount": _money(tax.per_unit_amount),
        "per_unit_uom": tax.per_unit_uom,
        # BR-RAT-036 as amended (DEF-386). Served with its DISPLAY string beside
        # it per BR-RAT-087 — a $1.25 per-meter fee reads "1.25", never
        # "1.250000", and the screen never scales a stored figure itself.
        "per_meter_amount": _money(tax.per_meter_amount),
        "per_meter_amount_display": _display_money(tax.per_meter_amount),
        "applies_above_units": _money(tax.applies_above_units),
        "applies_to_services": list(tax.applies_to_services or []),
        # DEF-273 — the two qualifiers r10's ruled rates come with. Empty list
        # / null both mean "no restriction", and they are served as themselves
        # rather than normalised, so the S13 screen can tell "every class" from
        # "the utility has not said" if it ever needs to.
        "applies_to_customer_classes": list(tax.applies_to_customer_classes or []),
        "premises_scope_kind": tax.premises_scope_kind,
        "premises_scope_value": tax.premises_scope_value,
        "liability_gl_account_id": _uuid_or_none(tax.liability_gl_account_id),
        # The display pair for the id above (PO 2026-09-17 · B14 rule 31).
        "gl_account_code": gl_code,
        "gl_account_name": gl_name,
        "remit_to": tax.remit_to,
        "filing_frequency": tax.filing_frequency,
        "filing_form": tax.filing_form,
        "effective_from": tax.effective_from.isoformat() if tax.effective_from else None,
        "effective_to": tax.effective_to.isoformat() if tax.effective_to else None,
        # ── DEF-385 · the fields TAX-02 collects and had nowhere to put ─────
        # Served as themselves, never defaulted here: `bill_label` NULL means
        # "the screen shows `name`", and a serializer that quietly substituted
        # it would make "the utility has not chosen a bill label" unreadable —
        # the same distinction `applies_to_customer_classes` keeps just above.
        "code": tax.code,
        "bill_label": tax.bill_label,
        "tax_type": tax.tax_type,
        "rounding_rule": tax.rounding_rule,
        "due_date_rule": tax.due_date_rule,
        "remit_method": tax.remit_method,
        "remit_reference": tax.remit_reference,
        "collection_allowance_percent": _money(tax.collection_allowance_percent),
        # BR-RAT-087 (store 4/6, DISPLAY 2): a 0.5 % allowance reads "0.5%",
        # never "0.005000". The screen never scales a stored figure itself.
        "collection_allowance_percent_display": _display_percent(tax.collection_allowance_percent),
        "collection_allowance_gl_account_id": _uuid_or_none(tax.collection_allowance_gl_account_id),
        "interest_penalty_percent": _money(tax.interest_penalty_percent),
        "interest_penalty_percent_display": _display_percent(tax.interest_penalty_percent),
        "interest_penalty_basis": tax.interest_penalty_basis,
        "filing_reminder_recipient": tax.filing_reminder_recipient,
        # DEF-382 — statutory, per authority. Never NULL: the column carries a
        # default so every authority states an answer, and the default is the
        # behaviour the product has always had.
        "discount_treatment": tax.discount_treatment,
        # ── DEF-387 · the lifecycle, derived (CR-165 §9 vocabulary) ────────
        "status": tax_status(tax),
        # ── CR-165-BRC10 round 2 · §9 — what the redesigned screens read ────
        # `version`: 1-based within this tax's chain, stamped at write and never
        # recomputed. `authority_account`: the Settings › Accounting row this
        # tax files under, as `{id, label}` — the label is the authority and the
        # number, which is what a clerk recognises (B14 rule 31: the id is for
        # the round trip, never displayed). `next_filing_due`: the due date of
        # the latest ENDED filing period (`next_filing_due`). `scheduled_next`:
        # the next version of this tax that starts after today, if one is saved.
        "version": tax.version_no,
        "authority_account": (
            {
                "id": str(tax.authority_account_id),
                "label": authority_account_label(tax.authority_account),
            }
            if tax.authority_account_id is not None
            else None
        ),
        "next_filing_due": _iso(next_filing_due(tax.filing_frequency, tax.due_date_rule)),
        "scheduled_next": scheduled_next_version(tax),
        # ⚠ SERVED BESIDE `status` ON PURPOSE. The S13 row action used to read
        # `status !== "active"` to decide between Deactivate and Reactivate, and
        # the moment `status` gained `scheduled`/`draft`/`expired` that test
        # started offering "Reactivate" on a live tax. The two questions are
        # different — *is this row deactivated* is not *where is it in its
        # lifecycle* — so each gets its own field rather than one field being
        # read for both. (Hard-won law 2's neighbour: a control wired to the
        # wrong fact renders fine and every test passes.)
        "active": tax.deleted_at is None,
        # DEF-483 — whether it prices a bill TODAY, which is not the same
        # question as its status word: a deactivated tax still prices (a
        # pre-existing question this lane did not answer), and a superseded one
        # does not even though nothing about it looks unusual on screen.
        "in_force": tax_in_force(tax),
        # ── DEF-384 · the correction chain, so the detail can show history ──
        "corrects_tax_id": str(tax.corrects_id) if tax.corrects_id else None,
        "superseded_by_tax_id": str(tax.superseded_by_id) if tax.superseded_by_id else None,
        "correction_reason": tax.correction_reason,
        # ── DEF-383 · how many exemption categories this authority states ───
        # A COUNT, not the rows: the categories are their own read
        # (`tax_exemption_categories`), and a list screen that eagerly loaded
        # every certificate would fetch a customer list to render a number.
        "exemption_category_count": models.TaxExemptionCategory.objects.filter(
            tenant_id=_tenant_id(), tax_id=tax.id, deleted_at__isnull=True
        ).count(),
        # Both paths a plan has to carry this tax (BR-RAT-113): its authority's
        # binding rows AND its own explicit attachment rows. The jurisdiction
        # half is GUARDED against NULL — with attachment rows in the table,
        # `jurisdiction_id=None` would match every attachment of every tax.
        "used_by_plans": models.PlanTaxRule.objects.filter(tenant_id=_tenant_id())
        .filter(
            (
                Q(jurisdiction_id=tax.jurisdiction_id)
                if tax.jurisdiction_id is not None
                else Q(pk__in=[])
            )
            | Q(tax__chain_id=tax.chain_id or tax.id)  # CR-165: any version of this tax
        )
        # DEF-RAT-9304 — PLANS, not rows: a plan that binds the authority AND
        # attaches the tax holds two rows and is one plan, which is how
        # `tax_plans` lists it (the tab read *Plans 9* over 7 plans).
        .values("rate_plan_id")
        .distinct()
        .count(),
    }


# ══════════════════════════════════════════════════════════════════════════
# CR-165-BRC10 round 2 · task 3 — the reads the redesigned tax screens need
# (`12-governance/change-requests/CR-165-BRC10-taxes-fees-redesign.md` §9)
# ══════════════════════════════════════════════════════════════════════════
def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


#: ── THE SIX DRAWN FILING DUE-DATE RULES, AS CODES (CR-165 §7 item 3) ─────
#: `taxes.due_date_rule` was free text *"until the remittance worksheet needs
#: to compute from it"* (`models.Tax.due_date_rule`). The redesigned details
#: header draws *Filing due* as a DATE, so it needs computing now: the six
#: choices image 13 draws are stored as these codes and `next_filing_due` is
#: the one evaluator. A stored value that is not a code (free text typed before
#: 2026-10-03 — none on the demo tenant) is served back unchanged and computes
#: no date; it is never rewritten.
#:
#: The LABELS are English and are the server's fallback only: the screens
#: render the eleven catalogues' own words keyed on the VALUE (B14 rule 35).
DUE_DATE_RULES: dict[str, str] = {
    "15th_next_month": "15th of the next month",
    "20th_next_month": "20th of the next month",
    "25th_next_month": "25th of the next month",
    "last_day_next_month": "Last day of the next month",
    "30_days_after_quarter": "30 days after the quarter ends",
    "jan_31_next_year": "January 31 of the next year",
}

FILING_FREQUENCY_LABELS: dict[str, str] = {
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "annual": "Annual",
}

#: BR-RAT-036's four computation forms, in the drawing's order and words.
TAX_BASE_LABELS: dict[str, str] = {
    "percent": "Percent of the bill",
    "flat_per_bill": "Fixed amount per bill",
    "per_unit": "Per unit used",
    "per_meter": "Per meter",
}

#: ⚠ **ONLY THE BOUNDARIES THAT BILL TODAY** (PO question pending — CR-165
#: §9 *form-options*; the coordinator's hold, round 2 item D(1)). The engine
#: resolves exactly two premises scopes (`PREMISES_SCOPE_KINDS_RESOLVABLE`:
#: `city_limits`, `state`) plus *everywhere* (no scope). *County*, *taxing
#: district* and *named list* reach nobody, and *outside city limits* and *a
#: named place* do not exist on a tax at all — offering any of them would let a
#: clerk save a tax that bills nobody while the screen says it applies. When the
#: PO answers, this list grows and no screen changes (the form renders it).
#: `everywhere` is the value for *no boundary*; `_validate_tax` stores it as a
#: NULL scope, which is what *everywhere* has always meant.
#:
#: ⚠ **RULED 2026-10-03 (PO, decision log *"THREE PO ANSWERS"*): *"Only what
#: works today. An outside-city charge stays on the plan. - this is correct"*,
#: and NO boundary carries `needs_place: true`.** That removes *In a state*
#: from the list, and the reason is arithmetic rather than taste: a `state`
#: scope matches the premises' state against a TYPED value and reaches NOBODY
#: without one (`premises_in_scope`), so with no place box it would save a tax
#: that bills nobody while the screen said it applied. *Inside city limits*
#: stays because it works without a place — it reads each premises' own
#: city-limits flag first. *Everywhere* is unchanged. A state tax at a
#: single-state utility is *Everywhere*.
TAX_BOUNDARY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("everywhere", "Everywhere"),
    ("city_limits", "Inside city limits"),
)


#: The boundaries the form asks a place name for. EMPTY by the PO's ruling of
#: 2026-10-03 — see `TAX_BOUNDARY_OPTIONS`.
TAX_BOUNDARIES_NEEDING_A_PLACE: frozenset[str] = frozenset()


def tax_form_options() -> dict[str, list[dict[str, Any]]]:
    """`GET /taxes/form-options` — every list the New tax form renders, from the
    server, so no screen hard-codes a choice the engine cannot honour."""

    def rows(pairs: Any) -> list[dict[str, str]]:
        return [{"value": value, "label": label} for value, label in pairs]

    return {
        # `needs_place` (added to CR §9 by the New-form lane, 2026-10-03): the
        # form shows the *Place name* box where it is true. False on every
        # boundary served, by the PO's ruling — see `TAX_BOUNDARY_OPTIONS`.
        "boundaries": [
            {
                "value": value,
                "label": label,
                "needs_place": value in TAX_BOUNDARIES_NEEDING_A_PLACE,
            }
            for value, label in TAX_BOUNDARY_OPTIONS
        ],
        "due_rules": rows(DUE_DATE_RULES.items()),
        "bases": rows(TAX_BASE_LABELS.items()),
        "filing_frequencies": rows(FILING_FREQUENCY_LABELS.items()),
    }


def _month_end(year: int, month: int) -> date:
    following = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return following - timedelta(days=1)


def _latest_ended_period_end(frequency: str, today: date) -> date | None:
    """The last day of the latest filing period that has ENDED before `today`."""
    if frequency == "monthly":
        return date(today.year, today.month, 1) - timedelta(days=1)
    if frequency == "quarterly":
        quarter_start_month = 3 * ((today.month - 1) // 3) + 1
        return date(today.year, quarter_start_month, 1) - timedelta(days=1)
    if frequency == "annual":
        return date(today.year - 1, 12, 31)
    return None


def filing_due_date(rule: str, period_end: date) -> date | None:
    """When a return for the period ending `period_end` is due, by `rule`.

    Worked (CR-165 §9's own example): period ending **09/30/2026** —
    `20th_next_month` → **10/20/2026**; `last_day_next_month` → 10/31/2026;
    `30_days_after_quarter` → 10/30/2026; `jan_31_next_year` → 01/31/2027.
    """
    next_month_year = period_end.year + (period_end.month == 12)
    next_month = 1 if period_end.month == 12 else period_end.month + 1
    if rule in ("15th_next_month", "20th_next_month", "25th_next_month"):
        return date(next_month_year, next_month, int(rule[:2]))
    if rule == "last_day_next_month":
        return _month_end(next_month_year, next_month)
    if rule == "30_days_after_quarter":
        quarter_end_month = 3 * ((period_end.month - 1) // 3) + 3
        return _month_end(period_end.year, quarter_end_month) + timedelta(days=30)
    if rule == "jan_31_next_year":
        return date(period_end.year + 1, 1, 31)
    return None


def next_filing_due(
    frequency: str | None, rule: str | None, today: date | None = None
) -> date | None:
    """🔒 THE ONE CALCULATION OF *Filing due* (CR-165 §7 item 3, §9).

    The due date of the latest ENDED filing period, by the tax's frequency and
    due-date rule, against the TENANT's today (BR-TEN-043). **Worked, the
    contract's own:** monthly + *20th of the next month* on 10/03/2026 — the
    September period ended 09/30 — is **10/20/2026**. Quarterly + *30 days after
    the quarter ends* on the same day is **10/30/2026** (Q3).

    None when either fact is missing or the rule is legacy free text — a date
    nobody can compute is not shown, never guessed.
    """
    if not frequency or not rule or rule not in DUE_DATE_RULES:
        return None
    period_end = _latest_ended_period_end(frequency, today or seams.tenant_today())
    return filing_due_date(rule, period_end) if period_end is not None else None


def _amount_display(tax: models.Tax) -> str | None:
    """A version's figure as a clerk reads it, whatever its form: `6.50%` for a
    percent, the two-place amount for the three money forms (BR-RAT-087)."""
    if tax.kind == "percent":
        return _display_percent(tax.rate)
    if tax.kind == "flat_per_bill":
        return _display_money(tax.flat_amount)
    if tax.kind == "per_unit":
        return _display_money(tax.per_unit_amount)
    if tax.kind == "per_meter":
        return _display_money(tax.per_meter_amount)
    return None


def _live_chain_rows(chain_id: Any) -> QuerySet:
    """The rows of one tax chain that can price — not superseded, not
    deactivated, not a draft. The same predicate `ex_taxes_chain_no_overlap`
    (`rating/0058`) holds non-overlapping."""
    return models.Tax.objects.filter(
        tenant_id=_tenant_id(),
        chain_id=chain_id,
        superseded_by__isnull=True,
        deleted_at__isnull=True,
        is_draft=False,
    )


def scheduled_next_version(tax: models.Tax, today: date | None = None) -> dict[str, Any] | None:
    """The next version of this tax that starts after today — the header's
    *Next: 6.5% from 11/01/2026* (web walk 4.2). None when none is saved."""
    on = today or seams.tenant_today()
    following = (
        _live_chain_rows(tax.chain_id or tax.id)
        .filter(effective_from__gt=on)
        .exclude(pk=tax.pk)
        .order_by("effective_from", "id")
        .first()
    )
    if following is None:
        return None
    return {
        "rate_display": _amount_display(following),
        "effective_from": _iso(following.effective_from),
    }


# ── Settings › Accounting › Authority accounts (CR-165 §7 item 1) ────────────
AUTHORITY_ACCOUNT_SORTS: tuple[str, ...] = ("authority_name", "account_number")
AUTHORITY_ACCOUNT_DEFAULT_SORT = "authority_name"
AUTHORITY_ACCOUNT_FILTERS: tuple[str, ...] = ("active", "jurisdiction")


def authority_account_label(row: models.TaxAuthorityAccount) -> str:
    """`TX Comptroller · 32-1180455` — what a clerk recognises in a picker."""
    return f"{row.authority_name} · {row.account_number}"


def authority_account_row(row: models.TaxAuthorityAccount) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "authority_name": row.authority_name,
        "account_number": row.account_number,
        "jurisdiction_id": str(row.jurisdiction_id) if row.jurisdiction_id else None,
        "active": row.active,
    }


def authority_account_ref(account_id: Any) -> dict[str, str] | None:
    """`{id, label}` for a tax's *Account with the authority*, or None."""
    if account_id is None:
        return None
    row = models.TaxAuthorityAccount.objects.filter(
        tenant_id=_tenant_id(), pk=account_id
    ).first()
    if row is None:
        return None
    return {"id": str(row.id), "label": authority_account_label(row)}


def authority_account_or_404(account_id: Any) -> models.TaxAuthorityAccount:
    if not _valid_uuid(account_id):
        raise errors.NotFoundError()
    row = models.TaxAuthorityAccount.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def authority_account_list_queryset(params: ListParams) -> QuerySet:
    """`GET /settings/authority-accounts` as a queryset — paged in SQL (NFR-3).

    `q` searches the authority name and the number; `f.active` (`true` /
    `false`) and `f.jurisdiction` narrow. Every filter is a column, so this list
    always pages in the database.
    """
    qs = models.TaxAuthorityAccount.objects.filter(tenant_id=_tenant_id())
    term = params.q.strip()
    if term:
        qs = qs.filter(Q(authority_name__icontains=term) | Q(account_number__icontains=term))
    active = str(params.filters.get("active") or "").strip().lower()
    if active in ("true", "false"):
        qs = qs.filter(active=(active == "true"))
    jurisdiction = params.filters.get("jurisdiction")
    if jurisdiction and _valid_uuid(jurisdiction):
        qs = qs.filter(jurisdiction_id=jurisdiction)
    field = params.sort if params.sort in AUTHORITY_ACCOUNT_SORTS else AUTHORITY_ACCOUNT_DEFAULT_SORT
    prefix = "-" if params.dir == "desc" else ""
    return qs.order_by(f"{prefix}{field}", "id")


def authority_account_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    return _sql_page(
        authority_account_list_queryset(params),
        params,
        lambda rows: [authority_account_row(row) for row in rows],
    )


# ── premises reached, for the list and the details header (§9) ────────────────
def tax_reach_counts(taxes: list[models.Tax]) -> dict[str, tuple[int, int]]:
    """`{tax id: (premises reached, premises total)}` for a page of taxes.

    It runs `matched_premises` — the engine's own predicate (BR-RAT-107) —
    once per DISTINCT scope on the page, over ONE read of the premises
    geography, so twenty taxes cost one premises read and not twenty.
    ⚠ NFR-3: this is O(page × premises) in Python. At the top of T5 (40,000
    premises) a 20-row page is 20 × 40,000 predicate calls; it is measured in
    the CR's §10 rather than assumed fine.
    """
    if not taxes:
        return {}
    rows = seams.premises_geography_rows()
    reach: dict[str, Any] | None = None
    by_scope: dict[Any, tuple[int, int]] = {}
    out: dict[str, tuple[int, int]] = {}
    for tax in taxes:
        classes = tuple(tax.applies_to_customer_classes or ())
        services = tuple(tax.applies_to_services or ())
        key = (tax.premises_scope_kind or "", tax.premises_scope_value or "", classes, services)
        if key not in by_scope:
            if (classes or services) and reach is None:
                reach = seams.premises_reach_facts()
            counted = matched_premises(
                tax.premises_scope_kind,
                tax.premises_scope_value,
                customer_classes=classes,
                services=services,
                sample=0,
                _rows=rows,
                _reach=reach,
            )
            by_scope[key] = (int(counted["count"]), int(counted["total"]))
        out[str(tax.id)] = by_scope[key]
    return out


def tax_read_row(
    tax: models.Tax, reach: dict[str, tuple[int, int]] | None = None
) -> dict[str, Any]:
    """`tax_row` plus `premises_reached` / `premises_total` — what the list rows
    and `GET /taxes/{id}` serve (§9). Kept out of `tax_row` itself because
    `tax_row` is also every audit snapshot, and a premises count is not a fact
    about the tax: it moves when a premises is added, and an audit diff must not."""
    row = tax_row(tax)
    counts = (reach or {}).get(str(tax.id))
    if counts is None:
        counts = tax_reach_counts([tax])[str(tax.id)]
    row["premises_reached"], row["premises_total"] = counts
    return row


def _current_chain_rows_only(qs: QuerySet, today: date) -> QuerySet:
    """⚠ THE LIST SHOWS ONE ROW PER TAX (CR-165 §9, the drawn *Version* column).

    Every version of a tax is a row in `taxes`, so a list of rows would show
    v1 and v2 of one tax side by side. The row shown is the version that is
    current TODAY: hidden are (a) every row a correction superseded, (b) an
    ENDED row whose chain has a live row not yet ended, and (c) a SCHEDULED row
    whose chain has a live row in force today — that one is the header's
    `scheduled_next` instead. `f.versions=all` lists every row.
    """
    sibling = models.Tax.objects.filter(
        chain_id=OuterRef("chain_id"),
        superseded_by__isnull=True,
        deleted_at__isnull=True,
        is_draft=False, tenant_id=_tenant_id(),
    ).exclude(pk=OuterRef("pk"))
    not_ended = sibling.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
    in_force_today = not_ended.filter(
        Q(effective_from__isnull=True) | Q(effective_from__lte=today)
    )
    return (
        qs.filter(superseded_by__isnull=True)
        .exclude(Q(effective_to__lt=today) & Exists(not_ended))
        .exclude(Q(effective_from__gt=today) & Exists(in_force_today))
    )


# ── the Audit tab: every change to this tax and its versions (§9) ─────────────
#: The fields an audit entry shows when they CHANGED. A whitelist, because a
#: snapshot carries derived and id-shaped keys (B14 rule 31) that are not a
#: change anybody made.
TAX_AUDIT_FIELDS: tuple[str, ...] = (
    "name",
    "code",
    "bill_label",
    "tax_type",
    "kind",
    "rate_display",
    "flat_amount",
    "per_unit_amount",
    "per_unit_uom",
    "per_meter_amount",
    "applies_above_units",
    "applies_to_services",
    "applies_to_customer_classes",
    "premises_scope_kind",
    "premises_scope_value",
    "effective_from",
    "effective_to",
    "filing_frequency",
    "due_date_rule",
    "filing_form",
    "remit_method",
    "remit_reference",
    "remit_to",
    "filing_reminder_recipient",
    "authority_account",
    "gl_account_code",
    "discount_treatment",
    "status",
    "version",
    "plan",
)


def _audit_view(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    view = {key: payload.get(key) for key in TAX_AUDIT_FIELDS if key in payload}
    account = view.get("authority_account")
    if isinstance(account, dict):
        view["authority_account"] = account.get("label")
    return view


def tax_audit_entry(row: Any, actor: Any) -> dict[str, Any]:
    """One `audit_log` row as the Audit tab's `{at, actor, action, before,
    after, reason}`. On an UPDATE both sides carry only the fields that
    changed; a create carries `before: null` and the whitelisted snapshot."""
    before = _audit_view(row.before) if row.before is not None else None
    after = _audit_view(row.after) if row.after is not None else None
    if before is not None and after is not None:
        changed = [key for key in TAX_AUDIT_FIELDS if before.get(key) != after.get(key)]
        before = {key: before.get(key) for key in changed}
        after = {key: after.get(key) for key in changed}
    raw_after = row.after if isinstance(row.after, dict) else {}
    return {
        "at": row.created_at.isoformat() if row.created_at else None,
        "actor": actor,
        "action": row.action,
        "before": before,
        "after": after,
        "reason": raw_after.get("reason") or raw_after.get("correction_reason"),
    }


def tax_chain_ids(tax: models.Tax) -> list[str]:
    """Every row id of this tax's chain — the entities its Audit tab reads."""
    return [
        str(one)
        for one in models.Tax.objects.filter(
            tenant_id=_tenant_id(), chain_id=tax.chain_id or tax.id
        ).values_list("id", flat=True)
    ]


# ── The two reads the tax detail's Plans and Audit tabs need (CR-087) ───────
#
# PO ruling 2026-09-10, verbatim: *"build"* — asked whether the `Plans` and
# `Audit` tabs on the Taxes & fees detail page should exist at all, given the
# blueprint specifies them across four pages and marks them NO COMMITMENT.
# The ruling's own sizing named exactly what was missing, and these two
# functions are it:
#
#   tax → Plans  *"the reach list needs one `values_list` off an existing
#                 query — the cheapest of the four"*
#   tax → Audit  *"three of four columns are stored per row; a chain read and
#                 the actor are missing"*


#: The two mechanisms `BR-RAT-113` gives a plan for carrying a tax, as the
#: codes the `REACHED BY` column renders. They are not new facts: they are the
#: two arms of `tax_row`'s own `used_by_plans` `Q()`, named instead of counted.
TAX_REACH_MECHANISMS: tuple[str, ...] = ("jurisdiction", "attached")


def tax_plans(tax_id: Any) -> list[dict[str, Any]]:
    """WHICH plans carry this tax, and HOW each one gets it — `CR-087-p034`.

    The tab rendered a sentence saying it could not list what it exists to
    list (*"Naming them one by one needs a read that does not exist yet"*).
    That sentence was true of the ROW read and never of the table: `tax_row`
    already counts these exact plans, over these exact two mechanisms, and
    threw the names away.

    ── WHY `REACHED BY` EARNS A COLUMN, WHICH IS THE PART A COUNT CANNOT SAY ──
    `BR-RAT-113` gives a plan two ways to carry a tax and they behave
    differently when the authority changes: a **jurisdiction binding** carries
    every tax that authority levies, resolved at pricing time and never
    materialised as a row, so a correction the authority files reaches the plan
    with no data fix; an **explicit attachment** carries this one catalogue row
    and nothing else. Blueprint page 35: *"a bound authority and an individual
    attachment behave differently when the authority changes."*

    ⚠ **A PLAN CAN HOLD BOTH, AND THE BINDING IS WHAT IS REPORTED.** The two
    row shapes are mutually exclusive per ROW (the model's own check
    constraint) and not per PLAN, so a plan that binds Texas State *and* ticks
    this Texas State levy has two rows here. The drawn table has one row per
    plan, so one mechanism has to win, and it is the binding: `BR-RAT-113` says
    a jurisdiction-mandated tax stays on the bill *"whether or not anyone
    ticked it"*, so the attachment is the removable half and the binding is the
    fact that survives. Reporting the attachment would tell a clerk they can
    detach a tax they cannot.

    ⚠ **THE COUNT IS UNITS AND ITS NAME SAYS UNITS** — blueprint page 35, *"The
    count is units, not accounts."* A plan is assigned to a UNIT
    (`unit_plan_assignments`, rating-owned per B2 r16 #6), so units is what
    this query can honestly answer for. `discount_offered_unit_count` next door
    counts exactly this shape for exactly this reason, and `DEF-RAT-4664` is
    the same distinction got wrong on four other labels.

    ⚠ **`CR-087-p034-tax-plans.md` §9 SAYS THIS JOIN IS ONE NOBODY OWNS** —
    *"a unit count per plan per tax is a join nothing in the rating module owns
    today"* — and that sentence is STALE rather than wrong: it was true until
    `discount_offered_unit_count` landed with CR-087 C2, in this same module,
    over this same table. Corrected here rather than left standing (hard-won
    law 1); the conformance file is amended in the same commit.

    ⚠ **NFR-3 — THIS LIST IS BOUNDED BY THE TENANT'S PLAN CATALOGUE.** One row
    per RATE PLAN, never per premises, account or unit, and a utility of any
    tier in the ICP authors its plans by hand. It must never grow a row per
    account: that is the unpaginated read the rule forbids.
    """
    tax = tax_or_404(tax_id)
    rules = models.PlanTaxRule.objects.filter(tenant_id=_tenant_id()).filter(
        (
            Q(jurisdiction_id=tax.jurisdiction_id)
            if tax.jurisdiction_id is not None
            else Q(pk__in=[])
        )
        | Q(tax__chain_id=tax.chain_id or tax.id)  # CR-165: an attachment names one version; the plan carries the tax
    )
    # `values_list` and not `select_related`, because the only thing needed off
    # the plan is its name and its id — the ruling's own *"one `values_list`
    # off a query that already runs"*.
    mechanism_by_plan: dict[Any, str] = {}
    for plan_id, jurisdiction_id in rules.values_list("rate_plan_id", "jurisdiction_id"):
        reached = "jurisdiction" if jurisdiction_id is not None else "attached"
        # The binding wins over the attachment when a plan holds both.
        if mechanism_by_plan.get(plan_id) != "jurisdiction":
            mechanism_by_plan[plan_id] = reached
    if not mechanism_by_plan:
        return []
    plan_ids = list(mechanism_by_plan)
    units_by_plan: dict[Any, int] = {}
    for row in (
        models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id__in=plan_ids, assigned_to__isnull=True
        )
        .values("rate_plan_id")
        .annotate(units=Count("id"))
    ):
        units_by_plan[row["rate_plan_id"]] = row["units"]
    # ── CR-165-BRC10 round 2 · §9 — `accounts` BESIDE `units` ──────────────
    # The redesigned Plans tab draws ACCOUNTS; blueprint p35 ruled UNITS. Both
    # are served, so neither ruling is overwritten: `accounts` is the OPEN
    # accounts on this plan's currently-assigned units, counted by customers
    # through `seams.open_account_counts_by_unit` (the charge-code Plans tab's
    # read, DEF-RAT-8752) in one grouped query for every plan here. A vacant
    # unit counts in `units` and not in `accounts`; that is the whole
    # difference, recorded in the decision log 2026-10-03. `None` when
    # customers publishes no such read — the screen draws *—*, never a 0.
    unit_plan_rows = list(
        models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id__in=plan_ids, assigned_to__isnull=True
        ).values_list("rate_plan_id", "unit_id")
    )
    per_unit = seams.open_account_counts_by_unit([unit for _plan, unit in unit_plan_rows])
    accounts_by_plan: dict[Any, int] | None = None
    if per_unit is not None:
        accounts_by_plan = {}
        for plan_id, unit_id in unit_plan_rows:
            accounts_by_plan[plan_id] = accounts_by_plan.get(plan_id, 0) + per_unit.get(
                str(unit_id), 0
            )
    plans = models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk__in=plan_ids).order_by(
        "name", "id"  # IS-2 stable secondary
    )
    return [
        {
            "id": str(plan.id),
            "name": plan.name,
            "reached_by": mechanism_by_plan[plan.id],
            "units": units_by_plan.get(plan.id, 0),
            "accounts": (
                accounts_by_plan.get(plan.id, 0) if accounts_by_plan is not None else None
            ),
        }
        for plan in plans
    ]


def tax_correction_chain(tax_id: Any) -> list[dict[str, Any]]:
    """EVERY DATED ROW OF THIS TAX, NEWEST FIRST — `CR-087-p036`, the Audit tab.

    `taxes` is one row per rate with its own window and `corrects` /
    `superseded_by` link the corrections into a chain (`BR-RAT-104`), so the
    history the tab draws has been stored per row since DEF-384. What was
    missing is a read that returns the CHAIN rather than one row at a time —
    the PO's own sizing of this tab on 2026-09-10.

    ── WHAT EACH DRAWN COLUMN COMES FROM ────────────────────────────────────
    `EFFECTIVE` is `effective_from`; `RATE` is the SERVER's display string
    (`BR-RAT-087` / `DEF-364` — the client never scales a stored fraction);
    `WHY IT CHANGED` is `correction_reason`, free text the operator authored,
    and it is NULL on the row nobody corrected — the screen words that as
    *"First recorded"* rather than this read inventing a sentence; `BY` is
    `corrected_by`, the column rating 0032 added.

    ⚠ **NOT A FILTERED `audit_log` QUERY, AND THE REFUSAL IS OLDER THAN THIS
    FUNCTION.** `DefinitionDetailPage.tsx`'s §10 note and the source-as-text
    guard in `DefinitionDetail.test.tsx` both forbid it: an audit row is an
    actor + action + timestamp the engine never reads, a version row is a
    priced state bills still resolve to. And hard rule 4's 2026-09-02
    narrowing gives the sharper reason — `audit_log` is PRUNED on a retention
    schedule, so a rate history sourced from it loses its authors silently.

    ⚠ **THE WALK IS FENCED AGAINST A CYCLE.** `corrects` and `superseded_by`
    are ordinary self-FKs; nothing in the database prevents a ring, and a ring
    here would hang a request rather than raise. Every step checks the id
    against what it has already seen.

    ⚠ **IT WALKS BOTH WAYS FROM THE ROW ASKED FOR.** A clerk can open a
    superseded row directly from a link or from a bill, and the history of that
    rate is the whole chain — not the half below the row they happened to land
    on.

    ⚠ **NFR-3 — bounded by the number of times one statutory rate has been
    corrected**, which is a handful over a tax's life. Never a row per bill.
    """
    row = tax_or_404(tax_id)
    # ⚠ CR-165-BRC10 round 2 — THE CHAIN IS A COLUMN NOW, NOT A WALK. Every
    # version of a tax shares `chain_id`, whether it CORRECTS a row (same
    # window) or FOLLOWS one (a new rate from a date); the walk over
    # `corrects`/`superseded_by` that stood here could not see a new rate at
    # all. Newest version first. Bounded by the versions of ONE tax (NFR-3).
    chain = list(
        models.Tax.objects.filter(tenant_id=_tenant_id(), chain_id=row.chain_id or row.id)
        .order_by("-version_no", "-created_at", "-id")
    )
    today = seams.tenant_today()
    current = next(
        (entry for entry in chain if tax_in_force(entry, today)),
        next((entry for entry in chain if entry.superseded_by_id is None), chain[0]),
    )
    names = seams.user_display_names([entry.corrected_by_id for entry in chain])
    return [
        {
            "id": str(entry.id),
            "effective_from": (
                entry.effective_from.isoformat() if entry.effective_from else None
            ),
            "effective_to": (entry.effective_to.isoformat() if entry.effective_to else None),
            # BR-RAT-087 — the display string, never the stored fraction. A tax
            # that is not a percentage has no `rate` at all, and null here is
            # the honest answer rather than a "0.00%" that never existed.
            "rate_display": _display_percent(entry.rate),
            "correction_reason": entry.correction_reason,
            "corrected_by": _actor_ref(entry.corrected_by_id, names),
            "status": tax_status(entry),
            "version": entry.version_no,
            "amount_display": _amount_display(entry),  # any form, e.g. 1.25 per meter
            # The version in force TODAY (or, with none in force, the newest not
            # superseded) — so the table can mark it without the client
            # re-deriving the chain's rules. (CR-165: it read `superseded_by is
            # None`, which marked an ended v1 and a scheduled v2 both current.)
            "is_current": entry.id == current.id,
        }
        for entry in chain
    ]


# ── Exemption categories & certificates (CR-013 part 4 · DEF-383) ───────────
def exemption_category_row(category: models.TaxExemptionCategory) -> dict[str, Any]:
    """One category, with the number of accounts holding it.

    Part 4's detail tab asks for *"Exemptions — categories, accounts holding
    each, certificate expiry"*, so the count is part of the row rather than a
    second call: a category with 0 holders and one with 340 are different facts
    about the same authority, and the screen that lists categories is exactly
    where that difference matters.

    `expiring_soon` is the count whose certificates lapse inside 60 days. It is
    here because *"expired certificates reinstate the tax on the next run with
    no exception raised"* — nothing will warn the utility, by ruling, so the
    only place a warning can live is a screen somebody chooses to look at.
    """
    today = seams.tenant_today()
    live = models.TaxExemptionCertificate.objects.filter(
        tenant_id=_tenant_id(), category_id=category.id, revoked_at__isnull=True
    )
    return {
        "id": str(category.id),
        "tax_id": str(category.tax_id),
        "code": category.code,
        "name": category.name,
        "requires_certificate": category.requires_certificate,
        "certificate_requirement": category.certificate_requirement,
        "status": "inactive" if category.deleted_at else "active",
        "accounts_holding": live.filter(
            Q(expires_on__isnull=True) | Q(expires_on__gte=today)
        ).count(),
        "expiring_within_60_days": live.filter(
            expires_on__gte=today, expires_on__lte=today + timedelta(days=60)
        ).count(),
        "expired": live.filter(expires_on__lt=today).count(),
    }


def exemption_categories_for_tax(tax_id: Any) -> list[dict[str, Any]]:
    return [
        exemption_category_row(row)
        for row in models.TaxExemptionCategory.objects.filter(
            tenant_id=_tenant_id(), tax_id=tax_id
        ).order_by("code", "id")
    ]


def exemption_category_or_404(category_id: Any) -> models.TaxExemptionCategory:
    if not _valid_uuid(category_id):
        raise errors.NotFoundError()
    row = models.TaxExemptionCategory.objects.filter(tenant_id=_tenant_id(), pk=category_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def exemption_certificate_row(
    certificate: models.TaxExemptionCertificate, today: date | None = None
) -> dict[str, Any]:
    """One account's claim, with the ONE derived word that matters.

    `state` is `live` | `expired` | `revoked`, derived from the dates exactly as
    `tax_status` derives a tax's — never stored, so it cannot disagree with the
    expiry the bill run reads. `expires_on` NULL is LIVE (a permanent
    exemption), which is the model's own rule and the only reading under which a
    municipality's exemption works at all.
    """
    today = today or seams.tenant_today()
    if certificate.revoked_at is not None:
        state = "revoked"
    elif certificate.expires_on is not None and certificate.expires_on < today:
        state = "expired"
    else:
        state = "live"
    return {
        "id": str(certificate.id),
        "category_id": str(certificate.category_id),
        "account_id": str(certificate.account_id),
        "certificate_ref": certificate.certificate_ref,
        "issued_on": certificate.issued_on.isoformat() if certificate.issued_on else None,
        "expires_on": certificate.expires_on.isoformat() if certificate.expires_on else None,
        "state": state,
    }


def exemption_certificates_for_category(category_id: Any) -> list[dict[str, Any]]:
    today = seams.tenant_today()
    return [
        exemption_certificate_row(row, today)
        for row in models.TaxExemptionCertificate.objects.filter(
            tenant_id=_tenant_id(), category_id=category_id
        ).order_by("expires_on", "id")
    ]


def exemption_certificates_for_account(account_id: Any) -> list[dict[str, Any]]:
    """ONE ACCOUNT'S certificates, each with the TAX it removes — the account
    page's and the move record's read (`DEF-CUS-9774`, `DEF-CUS-9775`).

    ⚠ **WHY THE ACCOUNT PAGE NEEDS THIS AND NOT `accounts.tax_exempt`.** PO
    ruling (A), 2026-10-05 (`DEF-CUS-9724`): *an exemption removes only the tax
    named on its certificate*, so a move-in that records one leaves the blanket
    flag FALSE. The church certified against the City's 2.00% still pays the
    State's 6.25%; its account page read the blanket flag and said *Tax exempt:
    No* over a certificate the bill run was honouring. This row is the one the
    bill run reads (`exemption_certificate_row`'s `state` is derived exactly as
    the run derives it), so the page and the bill cannot disagree.

    Revoked certificates are left out — revocation is the authority saying the
    claim never stood. Expired ones are served with `state: "expired"`; the
    screen decides what to draw. Live first, then by expiry.
    """
    if not _valid_uuid(account_id):
        return []
    today = seams.tenant_today()
    rows = (
        models.TaxExemptionCertificate.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, revoked_at__isnull=True
        )
        .select_related("category__tax")
        .order_by("expires_on", "id")
    )
    out = []
    for row in rows:
        one = exemption_certificate_row(row, today)
        one["category_name"] = row.category.name
        one["tax_id"] = str(row.category.tax_id)
        one["tax_name"] = row.category.tax.name
        out.append(one)
    out.sort(key=lambda one: one["state"] != "live")
    return out


#: The two TAX list filters that are applied to BUILT ROWS rather than to the
#: queryset, so either one forces the whole-tenant build (`DEF-RAT-5742`).
#: `status` is derived from four facts and the tenant own today (`tax_status`,
#: `DEF-387`); `service` reads `applies_to_services` off the built row. Neither
#: is re-implemented in SQL, because two implementations of one derivation is
#: how a list and a detail end up disagreeing about the same row.
TAX_DERIVED_FILTERS: tuple[str, ...] = ("status", "service")


def tax_list_is_sql_pageable(params: ListParams) -> bool:
    """Can THIS request page in the database? (`NFR-3`, `DEF-RAT-5742`)

    Yes unless it asks for one of `TAX_DERIVED_FILTERS`. All three declared tax
    SORTS are columns, so a sort never forces the fallback here — only a filter
    does.
    """
    return not any(params.filters.get(name) for name in TAX_DERIVED_FILTERS)


def tax_list_queryset(params: ListParams) -> QuerySet:
    """The S9 Taxes & fees tab AS A QUERYSET — search, `level`, `remittance`
    and the ordering, which is all of this read a database can answer.

    ⚠ **`status` AND `service` ARE DELIBERATELY ABSENT** — see
    `TAX_DERIVED_FILTERS`. They are applied to built rows in `tax_list`,
    exactly where they have been since `DEF-387`, and `tax_page` refuses the
    SQL path when either is asked for rather than quietly returning rows that
    have not been narrowed.

    ⚠ **HARD RULE 2 IS UNTOUCHED.** No figure is computed here; `tax_row`
    remains the one place a rate is rendered, at its six stored places with its
    two-place display companion, and it is handed the same rows in the same
    order as before.
    """
    qs = models.Tax.objects.filter(tenant_id=_tenant_id()).select_related(
        "jurisdiction", "authority_account"
    )
    today = seams.tenant_today()
    if str(params.filters.get("versions") or "").strip().lower() != "all":
        qs = _current_chain_rows_only(qs, today)
    if str(params.filters.get("over_20") or "").strip().lower() in ("1", "true"):
        qs = qs.filter(_over_20_q(today))
    term = params.q.strip()
    if len(term) >= MIN_SEARCH_CHARS:
        qs = qs.filter(Q(name__icontains=term) | Q(jurisdiction__authority__icontains=term))
    level = params.filters.get("level")
    if level:
        qs = qs.filter(jurisdiction__level=level)
    remittance = params.filters.get("remittance")
    if remittance:
        qs = qs.filter(filing_frequency=remittance)
    # ⚠ DEF-387 — THE STATUS FILTER MOVED OUT OF THE QUERYSET, and it had to.
    # `status` used to be a synonym for `deleted_at IS NULL` and could be a SQL
    # predicate. It is now DERIVED from four facts and the tenant's own today
    # (`tax_status`), and a derived value cannot be filtered in the database
    # without re-implementing the derivation in SQL — two implementations of one
    # rule, which is how a list and a detail end up disagreeing about the same
    # row. So it is applied over the built rows below, exactly where the
    # `service` filter already lives and for the same reason.
    field = {"name": "name", "rate": "rate", "remittance": "filing_frequency"}.get(
        params.sort or TAX_DEFAULT_SORT, "name"
    )
    prefix = "-" if params.dir == "desc" else ""
    return qs.order_by(f"{prefix}{field}", "id")


def tax_rows_filtered(taxes: list[Any], params: ListParams) -> list[dict[str, Any]]:
    """Build these taxes rows and apply the two DERIVED filters to them.

    One implementation, called from both paths, so the SQL page and the
    O(tenant) fallback can never disagree about what `f.status=expired` means.
    """
    # CR-165 §9 — list rows carry `premises_reached` / `premises_total`,
    # counted once per distinct scope on the page (`tax_reach_counts`).
    reach = tax_reach_counts(list(taxes))
    rows = [tax_read_row(row, reach) for row in taxes]
    status = params.filters.get("status")
    if status:
        rows = [row for row in rows if row["status"] == status]
    # OQ-306 — a tax matches when it reaches ANY picked service (or every one).
    services = filter_values(params.filters.get("service"))
    if services:
        rows = [
            row
            for row in rows
            if not row["applies_to_services"]
            or any(one in row["applies_to_services"] for one in services)
        ]
    return rows


def _over_20_q(today: date) -> Q:
    """A percentage tax above 20% that is ACTIVE or SCHEDULED — the same facts
    `tax_status` reads (not superseded, not deactivated, not a draft, not
    ended), stated as one SQL predicate so the count costs one `COUNT(*)`."""
    return (
        Q(kind="percent", rate__gt=OVER_20_RATE, is_draft=False)
        & Q(superseded_by__isnull=True, deleted_at__isnull=True)
        & (Q(effective_to__isnull=True) | Q(effective_to__gte=today))
    )


def tax_over_20_count(params: ListParams) -> int:
    """`over_20_count` beside `count` on `GET /taxes` (CR-165 §9, the list
    lane): over the WHOLE filtered set, never the page. Worked: the web walk's
    150% city fee is 1; corrected to 3% it is 0 (the 150% row is superseded).

    The SQL path is one `COUNT(*)`. With a DERIVED filter (`f.status`,
    `f.service` — `TAX_DERIVED_FILTERS`) the same two predicates `tax_rows_
    filtered` applies are applied to the candidate rows here, without building
    a row each."""
    qs = tax_list_queryset(params).filter(_over_20_q(seams.tenant_today()))
    if tax_list_is_sql_pageable(params):
        return qs.count()
    status = params.filters.get("status")
    services = filter_values(params.filters.get("service"))
    count = 0
    for tax in qs:
        if status and tax_status(tax) != status:
            continue
        reach = list(tax.applies_to_services or [])
        if services and reach and not any(one in reach for one in services):
            continue
        count += 1
    return count


def tax_list(params: ListParams) -> list[dict[str, Any]]:
    """EVERY matching tax row, ordered and derived-filtered — the stable API
    and the CSV export. A SCREEN wants `tax_page`."""
    return _page(tax_rows_filtered(list(tax_list_queryset(params)), params), params)


def tax_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """`(one page of tax rows, the whole result set count)` — `NFR-3`.

    The SQL path is taken unless `f.status` or `f.service` is asked for; both
    read a value that is DERIVED rather than stored, so narrowing them in SQL
    would be a second implementation of `tax_status` and of the service reach.
    """
    if not tax_list_is_sql_pageable(params):
        return _built_page(tax_list(params), params)
    return _sql_page(
        tax_list_queryset(params), params, lambda taxes: tax_rows_filtered(taxes, params)
    )


# ── Discounts (CR-013 part 3 · DIS-01, §18 row 10 · EP-RAT-12) ──────────────
#
# ⚠ SIX TABLES SHIPPED ON 2026-08-19 AND NOTHING COULD READ THEM. Until this
# section existed, `apps/rating/api.py` served 18 handlers and not one of them
# was a discount: `0009_cr013_discounts.py` created `discounts`,
# `discount_versions`, `plan_discount_rules`, `discount_enrolments`,
# `discount_enrolment_documents` and `discount_grants`, the write services and
# the R6 pricing door were built and tested, and a human had no way to see a
# single row. That is hard-won law 2 (built is not wired) at six-table scale.
#
# ⚠ WHAT THIS SECTION DELIBERATELY DOES NOT SERVE, so each absence reads as a
# decision rather than an oversight:
#   * **No enrolment rows and no documents.** BR-RAT-079 restricts income and
#     medical proof by role and excludes it from general document lists. The
#     safest way to honour that in a read written before the role gate exists is
#     to serve NO document and NO enrolled-account identity at all — only
#     COUNTS. A list cannot leak what it never carries.
#   * **No version list.** The definition detail's Versions tab states that no
#     endpoint serves the object's own version history (§10), and that is still
#     true; serving half of it here would make the screen's own sentence a lie.
#   * **No writes.** DIS-02 (§18 row 12, the five-step wizard) is a separate
#     surface. These are reads.
def discount_or_404(discount_id: Any) -> discount_models.Discount:
    if not _valid_uuid(discount_id):
        raise errors.NotFoundError()
    row = discount_models.Discount.objects.filter(tenant_id=_tenant_id(), pk=discount_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def discount_version_or_404(discount_id: Any, version_id: Any) -> Any:
    """The version identified by BOTH ids, or 404 (DEF-400).

    The three lifecycle services (`submit`/`approve`/`activate`) are keyed by
    version id alone and are tenant-scoped, so they are safe on their own. The
    ROUTES that reach them are nested — `/discounts/{id}/versions/{vid}/submit`
    — and a nested path makes a claim: that this version belongs to this
    discount. This is what checks the claim, so a mistyped discount id refuses
    instead of quietly acting on the version the second id names.

    A read, not a rule: it decides nothing about the act, only about whether the
    URL describes a real pair on THIS tenant.
    """
    if not _valid_uuid(version_id):
        raise errors.NotFoundError()
    discount = discount_or_404(discount_id)
    version = discount_models.DiscountVersion.objects.filter(
        tenant_id=_tenant_id(), discount=discount, pk=version_id
    ).first()
    if version is None:
        raise errors.NotFoundError()
    return version


def discount_version_in_force(discount: discount_models.Discount, as_of: date | None = None) -> Any:
    """The version whose numbers a screen should show, or None.

    `as_of` is BR-RAT-007's service date and defaults to `None`, which is the
    tenant's today — exactly what this resolved before it took a date.

    The ACTIVE version in force on that date when there is one, and otherwise the
    LATEST version of any status — because a draft discount (r10 draws MILITARY
    that way) still has a type and a value a person needs to see, and a landing
    row showing em-dashes for a drafted −10% would describe a different object
    than the one on the screen.

    `discount_services.active_version` is REUSED rather than re-queried: it owns
    the effective-window narrowing, and a second copy of that predicate here
    would be a second rulebook over which version prices a bill. The import is
    local because `discount_services` imports `apps.rating.services`, which
    imports this module — at module level it would be an import cycle.
    """
    from apps.rating import discount_services

    return (
        discount_services.active_version(discount, as_of)
        or discount_models.DiscountVersion.objects.filter(tenant_id=_tenant_id(), discount=discount)
        .order_by("-version_no")
        .first()
    )


#: `discount_versions_for_labels` — why a label resolved to no version.
LABEL_UNKNOWN = "no_programme_carries_this_label"
LABEL_AMBIGUOUS = "label_names_several_programmes"
NO_VERSION_IN_FORCE = "no_version_in_force_on_that_day"


def discount_versions_for_labels(labels: Any, on_day: date) -> dict[str, dict[str, Any]]:
    """WHICH PROGRAMME, AND WHICH VERSION OF IT, a bill's discount LINE names.

    `CR-101-BRC03` §06 — the Fix a bill wizard's step 2 shows the discounts on
    the original and the corrected bill *"+ which version"* (p129). A discount
    reaches a bill as a LINE whose label is `Discount.name` (*"the bill line
    label"*, DIS-02 step 1) and nothing else: `invoice_lines` carries no
    discount FK, the engine's priced line carries no code, and `discount_grants`
    — which would have stamped `discount_version_id` at issue — is written by
    nothing on the bill path (its writer `record_grant` has no caller). So the
    label is the only identity a bill's discount has, and this read resolves it
    for the reader: the programme whose `name` is that label, and the version of
    it IN FORCE on `on_day` (BR-RAT-007's pivot, the bill's service date — the
    same day `billable_discount_rules` priced it on).

    **Rows are DICTS, and a miss is a NAMED miss, never an absent key.** Every
    label asked for comes back; one that names no programme, or names two
    (`name` is not unique — only `code` is), or names one with no version in
    force that day, carries `reason` and null version fields. A reader that
    got no row would have to guess which of the three it was.

    Read-only, tenant-scoped explicitly (rule 1) with RLS as the second
    guarantee. `discount_services.active_version` is REUSED for the in-force
    predicate so there is one rulebook over which version prices a bill; local
    import for the same cycle reason `discount_version_in_force` gives.
    """
    from apps.rating import discount_services

    wanted = {str(label) for label in labels if label is not None and str(label).strip()}
    if not wanted:
        return {}
    tenant_id = _tenant_id()
    by_label: dict[str, list[Any]] = {label: [] for label in wanted}
    for discount in discount_models.Discount.objects.filter(
        tenant_id=tenant_id, name__in=sorted(wanted)
    ).order_by("code"):
        by_label.setdefault(discount.name, []).append(discount)

    out: dict[str, dict[str, Any]] = {}
    for label in sorted(wanted):
        matches = by_label.get(label) or []
        row: dict[str, Any] = {
            "label": label,
            "code": None,
            "discount_id": None,
            "version_id": None,
            "version_no": None,
            "effective_from": None,
            "effective_to": None,
            "reason": None,
        }
        if not matches:
            row["reason"] = LABEL_UNKNOWN
        elif len(matches) > 1:
            row["reason"] = LABEL_AMBIGUOUS
        else:
            discount = matches[0]
            row["code"] = discount.code
            row["discount_id"] = str(discount.id)
            version = discount_services.active_version(discount, on_day)
            if version is None:
                row["reason"] = NO_VERSION_IN_FORCE
            else:
                row["version_id"] = str(version.id)
                row["version_no"] = version.version_no
                row["effective_from"] = (
                    version.effective_from.isoformat() if version.effective_from else None
                )
                row["effective_to"] = (
                    version.effective_to.isoformat() if version.effective_to else None
                )
        out[label] = row
    return out


def discount_allowance_unit(version: Any) -> str | None:
    """The unit a `usage_allowance` version RESOLVES to — `BR-RAT-960`.

    ⚖️ PO ruling 2026-08-31, closing `OQ-291`, verbatim: *"a) Take the unit from
    the service it's attached to"*. This is that lookup, and it is the read half
    of the rule whose arithmetic half is `resolution.usage_allowance_units`.

    **THE SERVICE IS THE ONE THE SCOPE NAMES.** `BR-RAT-960`'s second half makes
    a usage allowance a ONE-SERVICE discount — refused at set-up on any other
    scope — so `applies_to_service` is where the service comes from, and there is
    no other candidate to fall back to.

    **THE UNIT IS THE TENANT'S BILLED UNIT, WITH THE REGISTER'S OWN AS THE
    FALLBACK, AND THAT ORDER IS NOT A GUESS.** `apps.tenancy.selectors.
    service_billed_uoms` states what a NULL `billed_uom` means in as many words:
    *"the register's own unit is what is billed"* — not "unconfigured, refuse".
    So `billed_uom or primary_uom`, and `None` only when the tenant has stated
    neither, which is a real answer on four of the ten catalog services (sewer,
    solar, thermal/heat, battery carry no design-stated default).

    ⚠ **IT IS ASKED ONLY FOR AN ALLOWANCE, AND THAT GUARD IS THE WHOLE
    PERFORMANCE STORY.** `discount_row` is a LIST row, so anything unconditional
    here is one query per discount on the DIS-01 landing. `seams.billed_uom` is
    already the cheap singular — one filter, one `select_related`, the shape
    `DEF-1549` built after the old lookup walked the whole S8 screen read per
    call and turned a twenty-row import into a `[CRITICAL] WORKER TIMEOUT`. Even
    so it is asked only for the one type that can use the answer: a catalogue of
    twenty discounts with two allowances costs two queries, not twenty.
    """
    if version is None or version.discount_type != discount_models.DISCOUNT_USAGE_ALLOWANCE:
        return None
    if not version.applies_to_service_id:
        # BR-RAT-960 refuses this combination at set-up, so it is unreachable
        # through any write path. Rows stored BEFORE the rule are not migrated
        # (hard rule 4's posture for history), so the read still has to answer
        # for one — and the honest answer is "no service, no unit", which prints
        # the bare figure rather than a unit nobody chose.
        return None
    configured = seams.billed_uom(version.applies_to_service.code)
    return configured["billed_uom"] or configured["primary_uom"] or None


#: The currencies whose figures print with `$` (`CR-166` §9: *"`value_display`
#: with `$` or `%`"*; PO 2026-10-03 on the list: *"fixed values shown with $
#: (`$25.00`, `$1.00`)"*). The product's ICP is North American (CLAUDE.md), so
#: these are the ones a utility here bills in; any other prints its ISO code
#: after the figure rather than a symbol nobody chose.
DOLLAR_CURRENCIES = frozenset({"USD", "CAD", "MXN", "AUD", "NZD"})


def _display_money_with_symbol(value: Decimal | None, currency: str | None) -> str | None:
    figure = _display_money(value)
    if figure is None:
        return None
    code = (currency or "USD").upper()
    if code in DOLLAR_CURRENCIES:
        return f"-${figure[1:]}" if figure.startswith("-") else f"${figure}"
    return f"{figure} {code}"


def discount_value_display(
    discount_type: str | None,
    value: Decimal | None,
    allowance_unit: str | None = None,
    currency: str | None = None,
) -> str | None:
    """The `Value` column of DIS-01, in the unit its TYPE gives it.

    ⚠ **A TYPE THAT GIVES `value` NO MEANING IS SERVED `null`, NEVER `0`.** A
    charge waiver removes the WHOLE of whatever its scope selected —
    `discount_pricing._raw_reduction` returns `base` and never reads `value` —
    so a waiver's stored value is not a figure, and a screen printing `0.00` for
    it would be stating that the utility waives nothing. It renders an em-dash
    instead. The same holds for a rate override, whose "value" was a schedule
    swap and is now a mechanism the product has ruled out (`BR-RAT-961`).

    The three that DO have a unit:
      * `percentage`      -> percentage points  (`15` -> `15.00%`, BR-RAT-087)
      * `fixed_amount`    -> money              (`25` -> `25.00`, with currency)
      * `usage_allowance` -> a QUANTITY of units, in **the unit of the service it
        is attached to** (`2` -> `2.00 kgal`).

    ⚖️ **THAT LAST LINE IS NEW ON 2026-08-31 AND IS THE VISIBLE HALF OF
    `BR-RAT-960`.** PO ruling, verbatim: *"a) Take the unit from the service it's
    attached to"*, closing `OQ-291`. **This function's own docstring used to be
    the evidence that the question was unanswerable** — `OQ-291` quotes it —
    because it refused to print a unit on the ground that *"inventing `kgal` here
    would be a made-up fact on a bill-affecting screen"*. That reasoning was
    right and it is no longer the situation: the unit is not invented here, it is
    RESOLVED from the service the discount's scope names, and the caller passes
    the resolved answer in.

    ⚠ **PRINTING IT IS NOT COSMETIC — IT IS WHAT KEEPS THE INFERENCE HONEST.**
    The lane recommended storing the unit and was overruled; the PO chose the
    cheaper answer, which means the product now infers a fact rather than being
    told it. An inference a clerk can SEE beside the figure is a different thing
    from one buried in a resolution step: the same stored `2` is worth **`$14.40`**
    on water and **`$0.28`** on electric, and `2.00 kgal` on the screen is how
    somebody notices the discount is attached to the wrong service. A bare
    `2.00` is exactly the row `OQ-291`'s worked failure described.

    **`None` unit prints the bare figure, and that is the honest fallback** — it
    means the service states no unit, which `resolution.usage_allowance_units`
    REFUSES to price rather than defaulting (CLAUDE.md hard rule 3). A screen
    that guessed a unit here would put on a bill-affecting page precisely the
    made-up fact the old docstring was protecting against.
    """
    if value is None or discount_type is None:
        return None
    if discount_type == discount_models.DISCOUNT_PERCENTAGE:
        return _display_percent_points(value)
    if discount_type == discount_models.DISCOUNT_USAGE_ALLOWANCE:
        figure = _display_money(value)
        return f"{figure} {allowance_unit}" if allowance_unit else figure
    if discount_type == discount_models.DISCOUNT_FIXED_AMOUNT:
        # `CR-166` §9 — the dollar sign is the server's, like the `%` above,
        # so no screen formats money itself (BR-RAT-087).
        return _display_money_with_symbol(value, currency)
    return None


def discount_plan_count(discount: discount_models.Discount) -> int:
    """How many plans make this discount AVAILABLE — never how many accounts get
    it (BR-RAT-069). The two counts sit side by side on the row precisely so the
    difference is visible: `plans` is the offer, `enrolled` is the grant."""
    return discount_models.PlanDiscountRule.objects.filter(
        tenant_id=_tenant_id(), discount=discount
    ).count()


def discount_enrolled_count(discount: discount_models.Discount) -> int:
    """⚠ **THE GRANT, AND THE ONLY NUMBER THAT REDUCES A BILL** (BR-RAT-069).
    Open enrolments only — an account that enrolled and left is not enrolled,
    and counting it would overstate a subsidy programme's reach."""
    return discount_models.DiscountEnrolment.objects.filter(
        tenant_id=_tenant_id(), discount=discount, ended_on__isnull=True
    ).count()


def discount_offered_unit_count(discount: discount_models.Discount) -> int:
    """**THE DENOMINATOR TAKE-UP NEEDS** — CR-087 task C2 (`PRB-20`'s half that
    can be computed today).

    Units on a CURRENT plan assignment whose plan carries this discount: the
    population the programme is offered to. `31` enrolled says nothing on its
    own; `31` against `86` is take-up, and low take-up on an assistance
    programme is a finding a finance lead acts on.

    ⚠ **IT COUNTS UNITS AND ITS NAME SAYS UNITS, WHICH IS THE WHOLE POINT OF THE
    NAME.** `schedule_applied_to_accounts` next door counts exactly this shape
    and is called `accounts`, and that mislabelling reached four screens
    (`DEF-RAT-4664`). A plan is assigned to a UNIT — `unit_plan_assignments` —
    so units is what this query can honestly answer for.

    ⚠ **AND IT IS NOT `eligible`, WHICH IS WHY THE SCREEN DOES NOT SAY SO.**
    `PRB-20` asks how many accounts are ELIGIBLE, and eligibility on a discount
    is `eligibility_summary` — free text a person wrote, *"Age 65 or over"* —
    which nothing in this product evaluates. Offered is a fact about plans and
    is computable; eligible is a fact about people and is not. Drawing offered
    under the word *eligible* would be a wrong number rather than a missing one,
    which is the distinction tile 3 was built on (`granted_to_date` vs a
    per-month figure nobody computes).

    ⚠ **NO CROSS-MODULE READ.** `UnitPlanAssignment` is rating-owned (B2 r16 #6),
    so this walks rating's own tables only. Counting the ACCOUNTS on those units
    would be the tighter denominator and needs a customers seam that does not
    exist; it is not invented here for one tile.
    """
    plan_ids = list(
        discount_models.PlanDiscountRule.objects.filter(
            tenant_id=_tenant_id(), discount=discount
        ).values_list("rate_plan_id", flat=True)
    )
    if not plan_ids:
        return 0
    return models.UnitPlanAssignment.objects.filter(
        tenant_id=_tenant_id(), rate_plan_id__in=plan_ids, assigned_to__isnull=True
    ).count()


def discount_row(discount: discount_models.Discount) -> dict[str, Any]:
    """One DIS-01 landing row — r10's own nine columns in r10's own order:
    Code · Discount · Type · Value · Eligibility · Verification · Plans ·
    Enrolled · Status.

    Money and percent are served TWICE (BR-RAT-087 / DEF-364): the stored
    six-place value for anything that computes, and a `*_display` string beside
    it for anything that renders. `charge_row` established the pattern and the
    reason it exists is written out on `_display_money` — if the client may not
    format a money value, the server must.
    """
    from apps.rating import discount_reads

    gl_code, gl_name = _gl_display(discount.gl_account_id)
    version = discount_version_in_force(discount)
    discount_type = version.discount_type if version else None
    value = version.value if version else None
    allowance_unit = discount_allowance_unit(version)
    row = {
        "id": str(discount.id),
        "code": discount.code,
        "name": discount.name,
        # ⚠ `type` and everything under it comes from the VERSION, and is `null`
        # when a discount has no version at all — a shape that exists because
        # `create_discount` accepts no version payload. Null here is "this
        # programme has not been priced yet", which is a real state.
        "type": discount_type,
        "value": _money(value),
        "value_display": discount_value_display(
            discount_type, value, allowance_unit, version.currency if version else None
        ),
        # BR-RAT-960 — the unit the allowance RESOLVED to, served beside the
        # figure rather than only baked into the display string, so a client can
        # render it its own way and a test can assert the resolution directly.
        # `null` for every other type, and for an allowance whose service states
        # no unit (which `resolution.usage_allowance_units` REFUSES to price).
        "allowance_unit": allowance_unit,
        "currency": version.currency if version else None,
        "eligibility": version.eligibility_summary if version else None,
        "verification": version.verification_method if version else None,
        "plans": discount_plan_count(discount),
        "enrolled": discount_enrolled_count(discount),
        "status": discount.status,
        "programme_owner": discount.programme_owner,
        "funding_source": discount.funding_source,
        # CR-066 table 3 — where this discount posts. NULL means nobody has
        # overridden the `discount_contra_revenue` designation, which still
        # answers at issue; it is not a gap in the way an unmapped CHARGE code
        # is one. Served on the row so S8 → Accounting can show it beside the
        # charge codes and the adjustment reasons.
        "gl_account_id": str(discount.gl_account_id) if discount.gl_account_id else None,
        # The display pair for the id above (PO 2026-09-17 · B14 rule 31).
        "gl_account_code": gl_code,
        "gl_account_name": gl_name,
        "applies_to": version.applies_to if version else None,
        "effective_from": (
            version.effective_from.isoformat() if version and version.effective_from else None
        ),
        "version_no": version.version_no if version else None,
        "version_status": version.status if version else None,
        # ⚠ DEF-400: THE ID OF THE VERSION THE STATUS ABOVE DESCRIBES, and it is
        # here so a screen can ACT on it. `version_status` has been served since
        # this row was written and `version_no` beside it, so the definition
        # detail could always SAY "Draft" and could never do anything about it —
        # the three lifecycle services are keyed by version id and no read
        # published one. It is an identifier, not a figure: nothing here decides
        # money, and the acts it addresses each carry their own rule gate in
        # `discount_services` (BR-RAT-077's second approval, BR-RAT-083's
        # Owner/Admin activation).
        "version_id": str(version.id) if version else None,
    }
    # `CR-166-BRC10` §9 — the redesigned screens' fields, on EVERY row (list
    # and detail). ⚠ THREE KEYS CHANGE MEANING, by the contract: `status` is
    # the DERIVED six-value status (`discount_reads`), `eligibility` and
    # `exclusivity_group` are `{value, label}` objects. The stored status stays
    # readable as `stored_status`; `programme_owner` stays the stored code.
    row["stored_status"] = discount.status
    row.update(discount_reads.contract_fields(discount, version))
    return row


def discount_list(params: ListParams) -> list[dict[str, Any]]:
    """BR-SHL-011's `q/sort/dir/page/per/f.<name>`, shaped exactly like
    `charge_list` — search over code and bill-line name from two characters, the
    declared sorts only, and a stable `id` tiebreak so two discounts sharing a
    name do not swap places between pages.

    `type` and `verification` filter the BUILT ROWS rather than the queryset,
    because both live on the version this row resolved; `tax_list` filters
    `service` the same way for the same reason. **Since `DEF-RAT-5742` those two
    live in `discount_rows_filtered` and the queryset in
    `discount_list_queryset`** — one implementation each, shared with
    `discount_page`, so the SQL page and this whole-set read cannot disagree
    about what `f.type=percent` means.

    ⚠ **PREFER `discount_page` FOR A SCREEN.** This is `O(tenant)`; it stays
    because `customers.discounts` resolves it BY NAME across the module seam and
    wants every programme.
    """
    return _page(discount_rows_filtered(list(discount_list_queryset(params)), params), params)


def discount_list_queryset(params: ListParams) -> QuerySet:
    """The DIS-01 set and its ordering — search, `f.status` and the sort, which
    is everything about this read a database can answer (`DEF-RAT-5742`)."""
    from apps.rating import discount_reads

    today = seams.tenant_today()
    # `CR-166-BRC10` §9 — `f.status` is the DERIVED six-value status and
    # `f.type` the shown version's type, both annotated in SQL so the page is
    # still cut by the database (NFR-3). `status` sorts on the derived value too:
    # the value sorted must be the value shown.
    qs = discount_models.Discount.objects.filter(tenant_id=_tenant_id()).annotate(
        derived_status=discount_reads.status_annotation(today),
        shown_type=discount_reads.type_annotation(today),
    )
    term = params.q.strip()
    if len(term) >= MIN_SEARCH_CHARS:
        qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
    status = params.filters.get("status")
    if status and status.lower() != "all":
        qs = qs.filter(derived_status=status.lower())
    wanted_type = params.filters.get("type")
    if wanted_type and wanted_type.lower() != "all":
        qs = qs.filter(shown_type=wanted_type.lower())
    field = {"code": "code", "name": "name", "status": "derived_status"}.get(
        params.sort or DISCOUNT_DEFAULT_SORT, "code"
    )
    prefix = "-" if params.dir == "desc" else ""
    return qs.order_by(f"{prefix}{field}", "id")


#: The two DIS-01 filters applied to BUILT ROWS: both live on the VERSION this
#: row resolved rather than on `discounts`, so either forces the whole-tenant
#: build. `tax_list` filters `service` the same way for the same reason.
DISCOUNT_DERIVED_FILTERS: tuple[str, ...] = ("verification",)


def discount_list_is_sql_pageable(params: ListParams) -> bool:
    """Can THIS request page in the database? (`NFR-3`, `DEF-RAT-5742`)

    Yes unless `f.type` or `f.verification` narrows it — and `all` is not a
    narrowing, exactly as the row filters read it.
    """
    for name in DISCOUNT_DERIVED_FILTERS:
        value = params.filters.get(name)
        if value and value.lower() != "all":
            return False
    return True


def discount_rows_filtered(discounts: list[Any], params: ListParams) -> list[dict[str, Any]]:
    """Build these discount rows and apply the two VERSION-borne filters — one
    implementation, shared by the SQL page and the O(tenant) fallback."""
    rows = [discount_row(row) for row in discounts]
    # `f.type` moved into SQL (`discount_list_queryset`, `CR-166` §9).
    verification = params.filters.get("verification")
    if verification and verification.lower() != "all":
        rows = [row for row in rows if row["verification"] == verification.lower()]
    return rows


def discount_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """`(one page of DIS-01 rows, the whole result set count)` — `NFR-3`.

    ⚠ **BR-RAT-079 IS UNTOUCHED.** This still serves counts and never an
    enrolled account identity or a document; a page of rows cannot leak what the
    row shape never carries.
    """
    if not discount_list_is_sql_pageable(params):
        return _built_page(discount_list(params), params)
    return _sql_page(
        discount_list_queryset(params),
        params,
        lambda discounts: discount_rows_filtered(discounts, params),
    )


def discount_detail(discount_id: Any) -> dict[str, Any]:
    """`GET /discounts/{id}` — the landing row plus everything the definition
    detail's five tabs read.

    ⚠ **EVERY MONEY FIGURE BELOW IS `null` WHEN IT WAS NOT TYPED**, and that is
    the point of this change rather than a nicety. `cap_per_bill`,
    `cap_per_year`, `cap_lifetime` and `budget_cap` are nullable columns and the
    difference between "no cap" and "a cap of zero" decides whether next month's
    bill is reduced at all — a `0.00` where an em-dash belongs is a programme
    that silently pays nothing. `bill_floor_amount` is the one exception and it
    is a real stored default: BR-RAT-074 makes a floor of zero MEAN that a bill
    may reach zero, so `0` there is a decision, not an absence.
    """
    from apps.rating import discount_services

    discount = discount_or_404(discount_id)
    version = discount_version_in_force(discount)
    row = discount_row(discount)
    granted = discount_models.DiscountGrant.objects.filter(
        tenant_id=_tenant_id(), discount=discount
    ).aggregate(total=Sum("amount"))["total"]
    row.update(
        {
            "report_in_assistance_filing": discount.report_in_assistance_filing,
            # BR-RAT-072's fifth status carries a timestamp, because "when did
            # this programme run out of money" is the first question asked about
            # a discount a BILL RUN suspended.
            "funding_exhausted_at": (
                discount.funding_exhausted_at.isoformat() if discount.funding_exhausted_at else None
            ),
            # ⚠ APPEND-ONLY AND THEREFORE COMPLETE. A sum over zero grant rows is
            # a true `0.00` — "no subsidy has been given" — and not a missing
            # value, because `discount_grants` records every reduction that ever
            # reached a bill (hard rule 4). The per-MONTH figure the KPI strip
            # wants is a different question and is NOT served: it needs a
            # period-scoped aggregation over issued bills, and R6 is not wired
            # into `apps/billing` yet.
            "granted_to_date": _money(granted or ZERO),
            "granted_to_date_display": _display_money(granted or ZERO),
            # CR-087 C2 — the denominator take-up needs, and the only half of
            # `PRB-20` that can be answered without an eligibility engine. See
            # `discount_offered_unit_count` for why it is UNITS and why it is
            # not called `eligible`.
            "offered_units": discount_offered_unit_count(discount),
            # DEF-RAT-9792 — TRUE when the version in force today is
            # Automatic: the nightly sync grants and ends it, so the Accounts
            # tab draws no *+ Enroll an account* and the account door refuses
            # one. Read through the ONE reader the move-in uses
            # (`automatic_discount_ids`), never re-derived here.
            "enrolled_automatically": str(discount.id)
            in discount_services.automatic_discount_ids([discount.id], seams.tenant_today()),
            # ⚖️ `DEF-RAT-9833` (PO D2 (b), 2026-10-06: *"clark can add it
            # later also on account"*) — what now hides *+ Enroll an account*:
            # TRUE only for an Automatic discount NO person may add (Municipal
            # account, *Everyone on the plan*). Autopay and Paperless are
            # Automatic AND addable — the add switches the setting On.
            "hand_enrolment_refused": str(discount.id)
            in discount_services.hand_refused_discount_ids([discount.id], seams.tenant_today()),
        }
    )
    if version is None:
        return row
    remaining = discount_services.budget_remaining(version)
    row.update(
        {
            "effective_to": version.effective_to.isoformat() if version.effective_to else None,
            "applies_to_service": (
                version.applies_to_service.code if version.applies_to_service_id else None
            ),
            # ⚠ **`CR-091-BRC01` — THE DETAIL VIEW SHOWED NO SERVICE AT ALL**,
            # which is one of the PO's three asks: *"we will ahve to dsplay in
            # detail view and also allow to enit it duing edit process"*. Served
            # as a LIST always — a null column reads as `[]`, the way a tax's
            # own `applies_to_services` is served — so a caller never handles two
            # shapes of "no services".
            "applies_to_services": list(version.applies_to_services or []),
            "applies_to_charge_codes": list(version.applies_to_charge_codes or []),
            # The three caps — nullable, and null is "uncapped".
            "cap_per_bill": _money(version.cap_per_bill),
            "cap_per_bill_display": _display_money(version.cap_per_bill),
            "cap_per_year": _money(version.cap_per_year),
            "cap_per_year_display": _display_money(version.cap_per_year),
            "cap_lifetime": _money(version.cap_lifetime),
            "cap_lifetime_display": _display_money(version.cap_lifetime),
            # BR-RAT-074: stored, defaulted to zero, and zero MEANS something.
            "bill_floor_amount": _money(version.bill_floor_amount),
            "bill_floor_amount_display": _display_money(version.bill_floor_amount),
            # BR-RAT-073 — order is DATA. Part 3: "percentage-of-usage after a
            # usage allowance gives a different number than the reverse."
            "stacking_precedence": version.stacking_precedence,
            "stacks_with_others": version.stacks_with_others,
            # `exclusivity_group` is NOT restated here: the row already carries
            # it as `{value, label}` (`CR-166` §9, `discount_reads`), and the
            # stored code on its own would overwrite the object.
            "enrolment_mode": version.enrolment_mode,
            "proof_required": version.proof_required,
            # The POLICY list of acceptable proof KINDS — not a document and not
            # a customer's proof. BR-RAT-079 restricts the documents themselves;
            # nothing in this payload is one.
            "accepted_proof_kinds": list(version.accepted_proof_kinds or []),
            "proof_before_first_reduction": version.proof_before_first_reduction,
            "recertification_months": version.recertification_months,
            "recertification_notice_days": version.recertification_notice_days,
            "recertification_grace_days": version.recertification_grace_days,
            "lapse_behaviour": version.lapse_behaviour,
            "budget_cap": _money(version.budget_cap),
            "budget_cap_display": _display_money(version.budget_cap),
            "budget_period": version.budget_period,
            "exhaustion_behaviour": version.exhaustion_behaviour,
            # None when nothing was capped — the same "unbounded, not zero" fact
            # PO ruling 5 of 2026-08-19 turns into a mandatory second approval.
            "budget_remaining": _money(remaining),
            "budget_remaining_display": _display_money(remaining),
            "second_approval_required": version.second_approval_required,
            "second_approval_threshold": _money(version.second_approval_threshold),
            "second_approval_threshold_display": _display_money(version.second_approval_threshold),
            "self_approved": version.self_approved,
            "change_reason": version.change_reason,
            # ── BR-RAT-1016 · WHICH VERB THIS VERSION TAKES ─────────────────
            #
            # ⚠ **WITHOUT THESE FOUR THE SCREEN CANNOT TELL A DRAFT FROM A LIVE
            # ROW, AND THE TWO TAKE OPPOSITE VERBS.** A never-submitted draft
            # edits in place; a live version is CORRECTED over the same window;
            # anything else is a new dated version. The detail served the
            # version's CONTENT and never its identity or its state, so a wizard
            # opened on a discount had exactly one door and had to use it for
            # all three — which is `DEF-RAT-5709`.
            #
            # ⚠ **`version_id`, `version_no` AND `version_status` ARE ALREADY
            # HERE — `discount_row` serves all three and this payload is built
            # on it.** What was missing is the one below, and it is missing
            # BECAUSE the rule is *never been SUBMITTED* rather than *is a
            # draft*. The day a *send back for changes* path exists, a status
            # alone would re-open in-place editing on content an approver has
            # already read, and `BR-RAT-077`'s stored requirement would then
            # describe content that has since moved.
            "version_submitted": version.submitted_at is not None,
            # The correction chain, so a screen can say *corrected* rather than
            # merely *old*.
            "version_corrects": str(version.corrects_id) if version.corrects_id else None,
            "version_correction_reason": version.correction_reason,
            # `CR-166-BRC10` r3 t6 (§9 "Fields added") — the details page draws
            # every money figure WITH its symbol (`$4.00`, `$2,383.00 · Annual`
            # — `DEF-RAT-9291` D27). The bare `*_display` keys above stay as they
            # are for the screens that already read them; these are the same
            # figures through the list's own `_display_money_with_symbol`, so the
            # symbol is decided once, here, beside the utility's currency.
            "money_display": {
                key: _display_money_with_symbol(amount, version.currency)
                for key, amount in (
                    ("cap_per_bill", version.cap_per_bill),
                    ("cap_per_year", version.cap_per_year),
                    ("cap_lifetime", version.cap_lifetime),
                    ("bill_floor_amount", version.bill_floor_amount),
                    ("budget_cap", version.budget_cap),
                    ("budget_remaining", remaining),
                )
            },
        }
    )
    return row


# ── S9 History over the append-only log (US-RAT-010/011) ────────────────────
def history_rows(entries: Any) -> list[dict[str, Any]]:
    """`DEF-RAT-10029` — the rows in a clerk's words (the actor's NAME, a
    field-by-field change list with every id resolved). One function for the
    list and the dialog; it lives in `history_words`."""
    from apps.rating import history_words

    return history_words.history_rows(list(entries))


def history_row(entry: models.RateChangeLog) -> dict[str, Any]:
    return history_rows([entry])[0]


def history_list_queryset(params: ListParams) -> QuerySet:
    """The S9 History set and its ordering — every filter and every sort on
    this list is a column, so the whole read is SQL (`DEF-RAT-5742`).

    ⚠ **THIS IS THE LIST THAT GROWS WITHOUT BOUND.** Plans, charge codes and
    taxes are a catalogue a utility maintains; `rate_change_log` is append-only
    (`BR-RAT-037`) and gains a row per entity per batch, so at the T5 ceiling
    ONE bulk rate update can add tens of thousands. It is the clearest case in
    this module for `NFR-3` and the easiest to serve, because nothing about it
    is derived.

    ⚠ **AND SINCE `DEF-RAT-10032` IT IS ONE SQL `UNION` OF TWO TABLES** (PO
    ruling 2026-10-09, option (a): History lists tax and discount changes too).
    Taxes and discounts write their edits to `audit_log` only, so those rows are
    read through the rating seam (`seams.rating_audit_queryset`, the audit
    module's one query) and joined here in the database: every filter is applied
    to each side, the sort and the page are taken over the union, and the count
    is one `COUNT(*)` of it (`NFR-3`). Which tax and discount acts are listed,
    and why one act is one row, is `history_words.HISTORY_AUDIT_ACTIONS`.
    🔒 HUMAN-REVIEW-PENDING — review row 2026-10-09 (DEF-RAT-10032).
    """
    from django.db.models import Case, DateTimeField, F, Value, When
    from django.db.models.fields.json import KT

    from apps.rating import history_words

    tenant = _tenant_id()
    log = models.RateChangeLog.objects.filter(tenant_id=tenant)
    audit_types = [kind for kind, word in history_words.HISTORY_AUDIT_TYPES.items()]
    audit = seams.rating_audit_queryset(
        Q(entity_type__in=audit_types, action__in=history_words.HISTORY_AUDIT_ACTIONS)
    ).annotate(
        _word=Case(
            *[When(entity_type=kind, then=Value(word)) for kind, word in history_words.HISTORY_AUDIT_TYPES.items()],
            output_field=TextField(),
        ),
        _why=Coalesce(KT("after__reason"), KT("after__correction_reason"), Value(""), output_field=TextField()),
    )
    term = params.q.strip()
    if len(term) >= MIN_SEARCH_CHARS:
        log = log.filter(Q(reason__icontains=term) | Q(entity_type__icontains=term))
        audit = audit.filter(Q(_why__icontains=term) | Q(_word__icontains=term))
    entity_type = params.filters.get("entity_type")
    if entity_type:
        log = log.filter(entity_type=entity_type)
        audit = audit.filter(_word=entity_type)
    batch = params.filters.get("batch")
    if batch and _valid_uuid(batch):
        log = log.filter(batch_id=batch)
        audit = audit.none()  # a bulk change is a rate_change_log batch; no audit row is one
    actor = params.filters.get("actor")
    if actor and _valid_uuid(actor):
        log = log.filter(actor_id=actor)
        audit = audit.filter(actor_user_id=actor)
    date_from = params.filters.get("from")
    if date_from:
        log = log.filter(created_at__date__gte=date_from)
        audit = audit.filter(created_at__date__gte=date_from)
    date_to = params.filters.get("to")
    if date_to:
        log = log.filter(created_at__date__lte=date_to)
        audit = audit.filter(created_at__date__lte=date_to)
    shape = ("_at", "_rid", "_etype", "_eid", "_vid", "_act", "_actor", "_before", "_after", "_reason", "_batch")
    log_rows = log.annotate(
        _at=F("created_at"),
        _rid=Cast("id", TextField()),
        _etype=F("entity_type"),
        _eid=Cast("entity_id", TextField()),
        _vid=Cast("entity_id", TextField()),
        _act=Value(None, output_field=TextField()),
        _actor=Cast("actor_id", TextField()),
        _before=F("before"),
        _after=F("after"),
        _reason=F("reason"),
        _batch=Cast("batch_id", TextField()),
    ).values(*shape)
    # A discount VERSION's row links to its DISCOUNT (what a clerk opens).
    version_owner = Subquery(
        discount_models.DiscountVersion.objects.filter(pk=OuterRef("entity_id")).values("discount_id")[:1]
    )
    audit_rows = audit.annotate(
        _at=Cast("created_at", DateTimeField()),
        _rid=Cast("id", TextField()),
        _etype=F("entity_type"),
        _eid=Case(
            When(entity_type="discount_version", then=Cast(version_owner, TextField())),
            default=Cast("entity_id", TextField()),
            output_field=TextField(),
        ),
        _vid=Cast("entity_id", TextField()),
        _act=F("action"),
        _actor=Cast("actor_user_id", TextField()),
        _before=F("before"),
        _after=F("after"),
        _reason=F("_why"),
        _batch=Value(None, output_field=TextField()),
    ).values(*shape)
    field = {"changed_at": "_at", "entity": "_etype", "actor": "_actor"}.get(
        params.sort or HISTORY_DEFAULT_SORT, "_at"
    )
    # Default sort is changed_at DESC (capability matrix) — BE-05's grammar
    # default is asc, so the History endpoint passes dir explicitly.
    prefix = "-" if params.dir == "desc" else ""
    return log_rows.union(audit_rows, all=True).order_by(f"{prefix}{field}", "_rid")


def history_list(params: ListParams) -> list[dict[str, Any]]:
    """EVERY matching history row, ordered — the stable API and the CSV export.
    Append-only compliance trail (r5 #14): read and export only, there is no
    mutation path anywhere in this module (BR-RAT-037). A SCREEN wants
    `history_page`."""
    return _page(history_rows(history_list_queryset(params)), params)


def history_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """`(one page of history rows, the whole result set count)` — `NFR-3`."""
    return _sql_page(
        history_list_queryset(params), params, history_rows
    )


def batch_row(batch: models.RateChangeBatch) -> dict[str, Any]:
    return {
        "id": str(batch.id),
        "reason": batch.reason,
        "change_spec": batch.change_spec,
        "actor_user_id": _uuid_or_none(batch.actor_id),
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "entities": models.RateChangeLog.objects.filter(
            tenant_id=_tenant_id(), batch=batch
        ).count(),
    }


def batch_by_fingerprint(fingerprint: str) -> models.RateChangeBatch | None:
    """BR-RAT-040: batches are never re-run — an identical apply finds the
    batch that already exists instead of writing a second one."""
    return (
        models.RateChangeBatch.objects.filter(
            tenant_id=_tenant_id(), change_spec__fingerprint=fingerprint
        )
        .order_by("created_at")
        .first()
    )


#: `DEF-771` — which half of a plan a units file's `Plan` cell was read as.
PLAN_MATCH_CODE = "code"
PLAN_MATCH_NAME = "name"
#: The outcomes `assignable_plan_index` can report for one token. Only
#: `published` carries a `plan_id`; the other three are the three DIFFERENT
#: things an operator has to do about it.
PLAN_OUTCOME_PUBLISHED = "published"
PLAN_OUTCOME_DRAFT = "draft"
PLAN_OUTCOME_ARCHIVED = "archived"
PLAN_OUTCOME_AMBIGUOUS = "ambiguous"


def _plan_label(row: dict[str, Any]) -> str:
    """`Name (CODE)` — both halves, always, because the whole of `DEF-771` is
    that a plan has two identifiers and only one of them was ever printed."""
    name = str(row.get("name") or "").strip()
    code = str(row.get("code") or "").strip()
    return f"{name} ({code})" if name and code else (name or code)


def _plan_token_entry(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """One token's verdict, from every plan that answers to it.

    ⚠ **A NAME IS NOT UNIQUE THE WAY A CODE IS.** `uq_rate_plans_tenant_code_ci`
    is `UniqueConstraint(F("tenant"), Lower("code"))` — case-INSENSITIVE, so
    two plans can never share a code once folded. `uq_rate_plans_tenant_name`
    is `UniqueConstraint(fields=["tenant", "name"])` — EXACT, so
    `City Customer Plan` and `city customer plan` are two lawful published
    plans of one tenant and a folded match then has two answers. It REFUSES and
    names both rather than picking: a silently mis-planned unit bills at the
    wrong rate, and that is a wrong invoice rather than a missing one
    (`BR-MET-117`'s posture, ruled 2026-08-26 for dates).

    A token reaching ONE plan by both its code and its name is one plan, not a
    collision — the ids are compared, never the match kind.
    """
    published = {row["id"]: row for row in candidates if row["status"] == PLAN_OUTCOME_PUBLISHED}
    if len(published) == 1:
        only = next(iter(published.values()))
        return {
            "plan_id": only["id"],
            "outcome": PLAN_OUTCOME_PUBLISHED,
            "matched_on": only["matched_on"],
            "plan": _plan_label(only),
            "collisions": [],
        }
    if len(published) > 1:
        return {
            "plan_id": None,
            "outcome": PLAN_OUTCOME_AMBIGUOUS,
            "matched_on": "",
            "plan": "",
            "collisions": sorted(_plan_label(row) for row in published.values()),
        }
    # Nothing PUBLISHED answers to it — so say WHICH plan it is and what state
    # it is in. "No such plan" and "that plan is a draft" need different acts
    # from the operator, and the receipt could not tell them apart before.
    rank = {PLAN_OUTCOME_DRAFT: 0, PLAN_OUTCOME_ARCHIVED: 1}
    pick = sorted(candidates, key=lambda row: (rank.get(row["status"], 2), row["name"]))[0]
    return {
        "plan_id": None,
        "outcome": pick["status"] or PLAN_OUTCOME_ARCHIVED,
        "matched_on": pick["matched_on"],
        "plan": _plan_label(pick),
        "collisions": [],
    }


def assignable_plan_index() -> dict[str, Any]:
    """Lowered token → verdict, for a units file's `Plan` column
    (`BR-MET-096` · `BR-MET-100` · `BR-RAT-030`).

    ⚠ **KEYED BY CODE *AND* BY NAME, AND THAT IS `DEF-771`.** This was
    `assignable_plan_ids_by_code` — `{lowered code: id}`, `.values("id",
    "code")` — while the column it serves is labelled **Plan** and accepts the
    aliases `plan`, `rate plan` and `tariff`, three of which are the words for
    a plan's NAME. A utility uploaded 9,881 units whose cell read
    *"city customer plan"* on every row: every row mapped clean, showed
    `Matched`, and loaded unplanned. The screen asked for one thing and the
    matcher wanted another, and nothing anywhere stated the difference.

    ⚠ **EVERY PLAN IS READ, NOT ONLY THE PUBLISHED ONES — and the gate is
    unchanged.** `BR-RAT-030` still makes only a published plan assignable, so
    only a `published` verdict carries a `plan_id`. A draft or an archived plan
    is in here so the run can say *which* plan it is and *why* it cannot be
    used, because "no such plan" and "that plan is a draft" are two different
    problems with two different fixes and the operator could not tell them
    apart before.

    Read WHOLE, once per run, deliberately: `DEF-324` measured the per-row
    shape at 47 of 118 profiled seconds for one repeated lookup, and a 9,881-row
    units file would ask this 9,881 times. A tenant has tens of plans, not
    thousands.

    Tokens are folded because a customer's export writes `RES-STD`, `res-std`
    and `City Customer Plan` interchangeably with `CITY CUSTOMER PLAN`, and
    none of those is a different plan.
    """
    rows = models.RatePlan.objects.filter(tenant_id=_tenant_id()).values(
        "id", "code", "name", "status"
    )
    tokens: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        plan = {
            "id": str(row["id"]),
            "code": str(row["code"] or ""),
            "name": str(row["name"] or ""),
            "status": str(row["status"] or ""),
        }
        claimed: set[str] = set()
        for kind, raw in ((PLAN_MATCH_CODE, plan["code"]), (PLAN_MATCH_NAME, plan["name"])):
            token = raw.strip().lower()
            if not token or token in claimed:
                continue
            claimed.add(token)
            tokens.setdefault(token, []).append({**plan, "matched_on": kind})
    return {token: _plan_token_entry(candidates) for token, candidates in tokens.items()}


def plan_ref(plan_id: Any) -> dict[str, Any] | None:
    """The reference metering needs to attach a PLAN to a unit (BR-CUS-014).

    Replaces `tariff_ref` as the unit's plan probe, per the PO ruling of
    2026-08-11: **a unit holds a PLAN (the bundle), not a rate schedule (one
    service's prices).** The screen has always said "default plan", the
    change-plan flow picks a plan, and the assignment-history table stores a
    plan — `units.default_tariff_id` was the only artefact in the product
    saying otherwise, and it could not hold a plan covering three services.

    `version` travels with the reference because the history row SNAPSHOTS it
    (BR-CUS-013): a plan edited next year must not silently restate what this
    unit was assigned today.

    Only PUBLISHED plans are assignable (BR-RAT-030): a draft has no prices a
    bill could be produced from, and an archived plan is withdrawn. An
    unpublished id resolves to None, so the caller refuses with its own
    unknown-plan error rather than this function inventing a status message.
    """
    if not _valid_uuid(plan_id):
        return None
    row = (
        models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk=plan_id, status="published")
        .only("id", "code", "name", "version", "status")
        .first()
    )
    if row is None:
        return None
    return {
        "id": str(row.pk),
        "code": row.code,
        "name": row.name,
        "version": row.version,
        "status": row.status,
    }


def plans_changed_since(plan_ids: Any, since: Any) -> dict[str, Any]:
    """`{plan_id: latest change}` for the named plans changed after `since`.

    Billing's bulk Check asks this to re-check exactly the accounts whose plan
    moved (OQ-843 re-ruled 2026-09-30, option C: *"automatically re-check an
    account when its plan … changes"* — e.g. a draft plan six accounts were
    blocked on is PUBLISHED, which saves the plan row). Read-only.

    🔒 **`DEF-BIL-8245` — A NEW PRICE VERSION IS A PLAN CHANGE FOR THIS.** A
    plan prices each service through `plan_rate_schedules` → a rate schedule
    (`tariffs`) → its dated `tariff_versions`, so publishing $0.13/kWh from
    15 June never saves the plan row, and until 2026-09-30 the Check went on
    showing every account on that plan priced at $0.12. Three things now count,
    each as its own `updated_at`, and the plan's answer is the LATEST of them:

      * the plan row itself (published, edited);
      * a plan ↔ schedule link (a schedule attached to or swapped on the plan);
      * a DATED version on any schedule the plan names — activation stamps the
        date on the draft row and saves it (`services.activate_rate_schedule`),
        and a batch or a correction creates a new dated row.

    ⚠ **A DRAFT VERSION (`effective_from IS NULL`, BR-RAT-031) IS NOT A
    CHANGE.** Nothing prices from a draft, and counting one would re-check a
    whole plan's accounts every time somebody saved a half-built schedule.

    Three indexed reads whatever the number of plans; nothing is written.
    A charge amount edited in place on its charge code is NOT seen here — that
    is `DEF-BIL-8640`, filed rather than guessed at.
    """
    ids = [str(one) for one in plan_ids or () if one]
    if not ids or since is None:
        return {}
    tenant_id = _tenant_id()
    changed: dict[str, Any] = {
        str(plan_id): moment
        for plan_id, moment in models.RatePlan.objects.filter(
            tenant_id=tenant_id, pk__in=ids, updated_at__gt=since
        ).values_list("id", "updated_at")
    }

    def later(plan_id: Any, moment: Any) -> None:
        key = str(plan_id)
        if moment is not None and (key not in changed or moment > changed[key]):
            changed[key] = moment

    plans_by_tariff: dict[str, list[str]] = {}
    for plan_id, tariff_id, moment in models.PlanRateSchedule.objects.filter(
        tenant_id=tenant_id, rate_plan_id__in=ids
    ).values_list("rate_plan_id", "tariff_id", "updated_at"):
        plans_by_tariff.setdefault(str(tariff_id), []).append(str(plan_id))
        if moment is not None and moment > since:
            later(plan_id, moment)
    if plans_by_tariff:
        for tariff_id, moment in (
            models.TariffVersion.objects.filter(
                tenant_id=tenant_id,
                tariff_id__in=list(plans_by_tariff),
                effective_from__isnull=False,
                updated_at__gt=since,
            )
            .values("tariff_id")
            .annotate(latest=Max("updated_at"))
            .values_list("tariff_id", "latest")
        ):
            for plan_id in plans_by_tariff.get(str(tariff_id), ()):
                later(plan_id, moment)
    return changed


def plan_services(plan_id: Any) -> list[str]:
    """The services a plan covers — the whole reason a unit holds a plan.

    A house on electric + water + trash is on ONE plan; the plan resolves to a
    rate schedule per service through `plan_rate_schedules`. Returned as
    service ids so metering can check the unit's service points are covered
    without importing rating's models.
    """
    if not _valid_uuid(plan_id):
        return []
    return [
        str(service_id)
        for service_id in models.PlanRateSchedule.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=plan_id
        )
        .order_by("service_id")
        .values_list("service_id", flat=True)
    ]


def pricing_inputs(
    tariff: models.Tariff,
    service_date: date,
    size_class: str | None = None,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, Any] | None:
    """What the ENGINE needs to price this tariff on this date. Rating's shape.

    WHY THIS EXISTS SEPARATELY FROM `version_structure`. That function is the
    S9 card's PREVIEW: it answers "what does this rate look like to a human",
    with season labels, formatted times and display strings. Billing's gather
    step read it by mistake and could not have worked — it returns `from_qty`/
    `to_qty` where the engine wants an upper bound, omits the billed unit and
    the base charge entirely (both live on the version ROW), and a FLAT rate's
    price is not in it at all, because BR-RAT-032 stores flat as ONE 0→∞ tier.

    Caught by an end-to-end test on the commit that introduced it. The lesson
    is the module boundary, not the field names: billing was reading rating's
    STORAGE, and storage is not an interface. This function is, and it is
    rating's to keep correct.

    `service_date` picks the version IN FORCE THEN (BR-RAT-007) — a June bill
    prices on June's rates whether the run happens in July or in 2031. Returns
    None when no version was in force, which the caller turns into a named
    exception rather than a fallback to today's prices.

    ⚠ **`size_class` IS NOT DECORATION — WITHOUT IT THIS FUNCTION WOULD HAVE
    STARTED MIS-PRICING THE DAY DEF-433 LANDED.** A version may now carry more
    than one tier ladder: NULL is *"every size"* and a `size_class` value is the
    override r10's 2" water row needs. Read unfiltered, a schedule with a base
    ladder and one override hands the engine SIX blocks in one ascending
    sequence — `0→10→30→∞` followed by `0→10→30→∞` — and every bill on that
    schedule is wrong, silently, on a document that looks entirely ordinary.
    So the ladder is SELECTED here:

      · a size with its own ladder  → that ladder
      · any other size, or no size  → the NULL ladder (`RateTier`'s own rule:
        *"a schedule states the exception, not the rule"*)

    **Defaulting to None is exactly today's behaviour for every version in the
    database**, because every tier written before DEF-433 has `size_class` NULL
    and the NULL group is therefore the whole set — the same rows, in the same
    order, at the same prices.

    ⚠ **THE CALLER PASSES ONE, AND IT IS A REAL SIZE (DEF-484 → DEF-514,
    2026-08-21, CORRECTED 2026-09-25).** `gather` resolves a
    `metering.connection_size_for` seam by name and hands the answer straight
    here, and that seam is published: `assets.Asset.size_class` is a real
    column (`assets/0010`, `BR-AST-500`), `assets.selectors.assets_on_unit`
    publishes it, and `DEF-1900` added the screen control and the meters-import
    column. **Measured by lane FIRESIZE on a seeded water + sewer + fire tenant
    on PostgreSQL 16, 2026-09-25: of 51 fire service points the seam answers a
    ratified size — `FL-4`, `FL-6`, `FL-8` — on every one that has a fire line
    on it. That count is theirs; the three facts this paragraph turns on were
    re-checked here — `DEF-514` reads `status: fixed`, `assets.Asset.size_class`
    is a declared column, and `connection_size_for` is a defined seam.** A
    connection with nothing recorded still answers `None`, and so does a unit
    with no service point for the service at all; the NULL ladder answers for
    both, which is byte-identical to every bill issued before DEF-433, because
    every tier written before it carries `size_class` NULL.

    ⚠⚠ **THIS PARAGRAPH IS A THREE-DEEP WARNING ABOUT STALE COMMENTS THAT WENT
    STALE ITSELF, WHICH IS WHY IT IS WORTH THE SPACE (`DEF-BIL-6760`).** It
    first said *"the caller does not pass one yet"* and was corrected on
    2026-08-21, citing hard-won law 1 in its own words: *a sentence describing
    an absence outlives the absence exactly as easily as one describing a
    guarantee.* The correction then asserted **"no row in this product records
    a connection's size — `assets.Asset` has no size column, `ServicePoint` has
    none, `Unit` has none, and DEF-255 proved that against the live database"**,
    and **`DEF-514` was CLOSED six days later, on 2026-08-27 at `2.79.5`**, at
    which point every clause of it was false. It stood for a month. **WHAT IT
    COST, measured:** a lane tracing a fire refusal read the sibling copy of
    this claim in `billing/gather.py`, concluded the `W-58` a clerk could see on
    the asset screen came from somewhere else, and the Product Owner reported
    the product broken in a way it is not — a full round trip on a money path.
    **The lesson is not *write it down more carefully*; it is that a paragraph
    asserting an ABSENCE is a claim nothing re-checks, and the only durable
    version of it is a test or a measured figure with a date on it.** Hence the
    date and the count above, rather than another assertion.

    What DID change is that the silence is over: `size_groups` below names the
    sizes a version overrides, and `gather` REFUSES by name when a version
    carries overrides and no size could be resolved, instead of quietly billing
    the base ladder. The save-time notice (`services._schedule_notices`,
    `rating.tiers.size_override_not_billed`) still fires at the moment the
    override is typed.
    """
    # `BR-RAT-1055` — every live candidate, the one that prices FIRST, in ONE
    # read: the winner is what `in_force_version` returns (the same function
    # orders both), and the rest are a legacy overlap the Check must name.
    candidates = in_force_versions(tariff, service_date)
    if not candidates:
        return None
    inputs = pricing_inputs_for_version(
        candidates[0],
        service_date,
        size_class,
        period_start=period_start,
        period_end=period_end,
    )
    if not size_class and _states_a_size_minimum(candidates[0]):
        # ── PO ruling 2026-10-01 · A METER WITH NO RECORDED SIZE GETS NO
        # MINIMUM, AND THE CHECK FLAGS IT (option A). No size was handed in
        # and this version states a minimum for at least one size — the one
        # case `_size_minimum` answers None for want of a SIZE rather than for
        # want of a figure. Published only then, so no other projection moves;
        # `gather` asks metering whether a meter is actually there before it
        # warns (sewer has no meter and must not be flagged).
        inputs["minimum_needs_size"] = True
    if len(candidates) > 1:
        # ── `DEF-RAT-8004` · PO ruling 2026-10-01, option A ─────────────────
        # *"Use the newest everywhere, and flag it on Check"*. Published ONLY
        # when there IS an overlap, so every projection on every schedule
        # written since `rating/0047` is byte-identical to yesterday's.
        # VALUES, never ids (B14 rule 31): what `gather` turns into the
        # `scheduleVersionsOverlap` warning, winner first.
        inputs["versions_in_force"] = {
            "schedule": tariff.name,
            "versions": [_overlap_fact(version) for version in candidates],
        }
    return inputs


def _overlap_fact(version: models.TariffVersion) -> dict[str, Any]:
    """One overlapping version as a clerk can recognise it on the schedule's
    own filings table: its label, its window and the day it was saved."""
    return {
        "label": version.version_label or None,
        "effective_from": version.effective_from,
        "effective_to": version.effective_to,
        "saved_on": version.created_at.date() if version.created_at else None,
    }


def _states_a_size_minimum(version: models.TariffVersion) -> bool:
    """Does this version state a minimum for ANY size? One `EXISTS` read,
    asked only when the connection has no recorded size (PO 2026-10-01: a
    meter with no recorded size gets no minimum, and the Check flags it)."""
    return models.RateSizeRow.objects.filter(
        tenant_id=_tenant_id(), tariff_version=version, minimum_bill__isnull=False
    ).exists()


def _size_minimum(version: models.TariffVersion, size_class: str | None) -> Decimal | None:
    """🔒 rating math · HUMAN-REVIEW-PENDING (*"2026-10-01 · MINIMUM PER METER
    SIZE"* in `12-governance/09-human-review-ledger.md`).

    **BR-RAT-028 mode (A)'s figure for one connection: the minimum the
    schedule's base table states for THIS size, or None.** PO 2026-10-01,
    option A, verbatim: *"A · Minimum per size - this is correct"*. Worked on
    Water — Residential at 1 kgal: 5/8" `$8.00 + $4.4096 = $12.41` under a
    5/8" minimum of `$15.00` bills **$15.00**; 2" `$28.00 + $4.4096 = $32.41`
    under a 2" minimum of `$40.00` bills **$40.00**.

        a row for this size, amount stated -> that amount
        a row for this size, no amount     -> None (*"No minimum"*: not topped up)
        no row for this size / no size     -> None

    ⚠ **THERE IS NO FALLBACK TO `tariff_versions.minimum_bill`, DELIBERATELY.**
    `resolution.resolve_minimum_bill` falls back to it, and the ruling removed
    that figure from billing outright: *"the step 3 per-version minimum is
    removed from screen and stops being billed"*. A fallback here would keep
    billing the very figure the PO took off the screen — a floor no clerk can
    see or change. `rating/0053` copied every stated version minimum onto that
    version's size rows that had none, so a schedule that floored every size
    before still floors every size it names; what it could not place is listed
    by that migration and in the decision log, never silently dropped.

    One read of `rate_size_rows`, inside the projection the bill run already
    memoises per (tariff, date, size) (`billing.seam_batch`), and never a
    second lookup of the VERSION — G142's question is untouched.
    """
    if not size_class:
        return None
    row = (
        models.RateSizeRow.objects.filter(
            tenant_id=_tenant_id(), tariff_version=version, size_class=size_class
        )
        .values_list("minimum_bill", flat=True)
        .first()
    )
    return row


def pricing_inputs_for_version(
    version: models.TariffVersion,
    service_date: date,
    size_class: str | None = None,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, Any]:
    """The SAME projection as `pricing_inputs`, for a version named OUTRIGHT.

    ⚠ **SPLIT OUT 2026-08-21, AND THE SPLIT IS THE WHOLE POINT (DEF-434).** The
    rate-change impact analysis has to price one account TWICE — once under the
    version in force and once under the version being proposed — and the second
    of those is not in force on any date, so `in_force_version` can never reach
    it. The obvious way to get one is to write a second projection of a stored
    version onto the engine's inputs. **That is how two screens start disagreeing
    about a figure**: the projection is thirty lines of `flat`-is-one-0→∞-tier,
    DEF-433's ladder selection and four rate shapes, and a copy of it would drift
    on the first shape that gained a column — silently, because both copies would
    still produce a well-formed bill.

    So `pricing_inputs` is now a two-line date lookup in front of THIS function,
    and there is exactly ONE projection in the product. A bill and an impact
    analysis cannot price the same version differently, by construction.

    `service_date` is still taken, and is still only used to resolve the SEASON
    in force (BR-RAT-021) — the version itself is the caller's choice here.

    ── `period_start` / `period_end` · BR-RAT-034's SPLIT (built 2026-10-01) ──
    🔒 HUMAN-REVIEW-PENDING. The days the bill covers, inclusive — billing's
    served span. When given, a `time_of_use` or `seasonal` version publishes
    `season_days`: the calendar days of that span in each season, counted HERE
    against the stored `rate_seasons` ranges (`_season_days_between`), beside
    the one-season lookup it extends, because the engine is pure and holds no
    calendar (`OQ-234`'s own design note). It is `[]` — and the bill prices
    exactly as before — for a span inside one season, for a version with no
    seasons, and for every caller that passes no span (the impact analysis).
    `OQ-234` was CLOSED by the PO on 2026-09-07, *"please split  swithch it
    on"*; this is that switch, three weeks late (`DEF-RAT-8832`).
    """
    all_tiers = list(
        models.RateTier.objects.filter(tenant_id=_tenant_id(), tariff_version=version).order_by(
            "seq", "id"
        )
    )
    # DEF-433 — ONE ladder reaches the engine, and the fallback is a FALLBACK:
    # a size with no ladder of its own is priced by the NULL group, which is what
    # "a schedule states the exception, not the rule" means in code.
    sized = [tier for tier in all_tiers if tier.size_class == size_class] if size_class else []
    tiers = sized or [tier for tier in all_tiers if tier.size_class is None]
    inputs: dict[str, Any] = {
        "version_id": str(version.id),  # travels onto the bill line — provable prices
        "model": version.model,
        "billed_unit": version.uom,
        "base_charge": version.base_charge,
        # ── `BR-RAT-1025` · WHICH CHARGE CODE OWNS THIS SERVICE'S BASE ──────
        # `DEF-RAT-5782`. The schedule's BINDING, and it is the hop that was
        # missing: `base_charge_from_charge_code` has taken a `named_code`
        # since 2026-09-19 and no caller could pass one, because the only
        # projection of a stored version onto the engine's inputs did not
        # carry it. A binding honoured by the ruled chain and not by the path
        # that bills is a screen and a bill that disagree.
        #
        # ⚠ **THE CODE'S `charges.code`, NEVER ITS ID.** The narrowing
        # downstream compares `row.code == named_code`, so a uuid here would
        # match nothing and would fall through to the INFERRED code —
        # silently, on a money path, producing a well-formed bill from a code
        # no screen shows. Same expression as
        # `resolution_catalogue.charge_code_facts`, so the two narrowings
        # cannot disagree about what the binding IS.
        #
        # ⚠ **PUBLISHED ON EVERY VERSION, NOT ONLY ON BOUND ONES** — the
        # reason `version_id` and `percent_basis` are: a projection that
        # publishes a field conditionally is a projection two callers can
        # read differently. Every version stored before `rating/0037` holds
        # NULL, so this is `None` on every tenant today and no bill moves.
        #
        # ⚠ **IT SITS BESIDE THE COLUMN IT IS THE OPPOSITE OF.** The line
        # above is `tariff_versions.base_charge`, the RETIRED decimal
        # (`BR-RAT-088`); this is a POINTER and holds no money. A lane that
        # reaches for one meaning the other has repurposed a retired column.
        "base_charge_code": named_base_charge_code(version),
        # ── BR-RAT-028 MODE (A) · THE MINIMUM IS THE SIZE'S (PO 2026-10-01) ──
        # `DEF-RAT-8737`, decision log *"RATE SCHEDULES: THE MINIMUM IS SET PER
        # METER SIZE AND BILLING CHARGES IT"*, option A. PO verbatim: *"A ·
        # Minimum per size - this is correct"*. The key keeps its name — it is
        # the seam `gather._tariff_config_for` reads — and its SOURCE moves from
        # the version's scalar `tariff_versions.minimum_bill` (no longer billed)
        # to the `rate_size_rows` row for THIS connection's size. See
        # `_size_minimum` for the three outcomes and why none falls back.
        "minimum_bill": _size_minimum(version, size_class),
        "currency": version.currency,
        "unit_price": None,
        "tiers": [],
        # ⚠ DEF-484 — WHICH SIZES THIS VERSION SAYS SOMETHING SPECIAL ABOUT,
        # published so the caller can tell "the fallback is the whole answer"
        # from "the fallback is a fallback". Added 2026-08-21.
        #
        # The ladder selection above is silent by construction: asked for a size
        # a version does not override, and asked for NO size at all, it returns
        # the same NULL group — which is exactly right for the first case and
        # exactly wrong for the second, and the return value cannot tell them
        # apart. Every version in the database today defines no group at all, so
        # this is `[]` everywhere and no caller's behaviour changes; a version
        # that DOES carry a 2" ladder now says so, and `gather` refuses by name
        # rather than billing the base ladder to a connection whose size nobody
        # can state (DEF-514: no row in this product records one).
        #
        # The NULL group is deliberately NOT listed. It is the rule, not an
        # exception (`RateTier`'s own words: *"a schedule states the exception,
        # not the rule"*), so a version with only NULL tiers is `[]` and reads
        # as "no size is treated differently here".
        "size_groups": sorted({tier.size_class for tier in all_tiers if tier.size_class}),
    }
    # ── WHAT A PERCENT SCHEDULE IS A PERCENTAGE **OF** — `CR-130-BRC07` ──────
    # `BR-RAT-1030`, PO ruling 2026-09-22. Published on EVERY version and not
    # only on percent ones, for the same reason `version_id` is: a projection
    # that publishes a field conditionally is a projection two callers can read
    # differently. Every stored row says `'usage'` or `'charge'` out loud
    # (`rating/0043` writes the first onto every row that predates the column),
    # so this is never None off a real row — and the plugin REFUSES a None
    # rather than defaulting, because a basis guessed on a money path is a
    # wrong bill that looks right.
    inputs["percent_basis"] = version.percent_basis

    if version.model == "flat" or (
        version.model == "percent_of_service"
        and version.percent_basis == percent_basis.PERCENT_BASIS_USAGE
        and len(tiers) <= 1
    ):
        # BR-RAT-032: flat is stored as ONE 0→∞ tier so the engine has a single
        # representation. Unwrapped here so billing never has to know that.
        #
        # ⚠ `percent_of_service` JOINED IT ON 2026-09-08 (`CR-081`). Sewer now
        # prices a VOLUME — 90% of the water it is a percentage of — and it
        # therefore needs a rate of its own, which it had never had on any
        # tenant. **That rate is stored the way `flat` stores one**, as a single
        # 0→∞ `rate_tiers` row, so there is no second column and no second way
        # to say "one price"; a sewer version is a flat schedule with a factor
        # in front of it. The line ABOVE this one used to be `== "flat"` and a
        # sewer version fell into the `else`, publishing an empty tier list and
        # a `unit_price` of None — which is exactly what the engine now refuses
        # by name.
        #
        # ⚠⚠ **`len(tiers) <= 1` IS `CR-130-BRC07`'s FIX AND IT IS A MONEY FIX.**
        # This branch read `tiers[0].unit_price if tiers else None`, which
        # **silently discarded every block after the first**. It was correct
        # while nothing in the product could create a second one: `services
        # ._validate_structure` wrote exactly one 0→∞ row for a percent
        # schedule and the screen had no control for more. The moment the
        # ladder exists — which is this very change — a five-block sewer ladder
        # would have billed every gallon at block one's price, with **no error
        # anywhere and a bill that foots against itself**. The CR names it and
        # requires it be fixed in the same change that opens the door, because
        # a discard fixed afterwards is a discard that shipped.
        #
        # A percent schedule with MANY blocks now falls through to the `else`
        # and publishes `tiers`, the same shape `tiered` publishes — which is
        # what `models/percent_of_service.py` walks through `tiered.price`.
        #
        # ⚠ **AND THE `charge` BASIS PUBLISHES NEITHER**, deliberately: it
        # prices no quantity, so it has no rate. `services._validate_structure`
        # refuses a rate on that basis BY NAME, and the plugin refuses one
        # again at pricing time for a row written by a script or a fixture.
        inputs["unit_price"] = tiers[0].unit_price if tiers else None
    elif (
        version.model == "percent_of_service"
        and version.percent_basis == percent_basis.PERCENT_BASIS_CHARGE
    ):
        # Neither a price nor a ladder: a percentage of MONEY has no rate of its
        # own. Stated as its own branch rather than left to fall through, so a
        # reader can see that the absence is a decision (hard-won law 1 — and
        # the `else` below would have published an empty `tiers` list, which is
        # the same bytes and none of the meaning).
        pass
    else:
        inputs["tiers"] = [
            # `to_qty` NULL is the open-ended top block; the engine reads that
            # as `upper=None`, not as zero.
            {"upper": tier.to_qty, "unit_price": tier.unit_price}
            for tier in tiers
        ]

    # ── The other four rate shapes (added 2026-08-16) ────────────────────────
    # Until this date this function published a flat price, a tier table and a
    # base charge and nothing else, so `time_of_use`, `percent_of_service`,
    # `capacity` and `demand` reached the engine as a model name with no
    # configuration behind it and the run refused at the registry. Every read
    # below is scoped to THIS version — a schedule's structure belongs to the
    # version that priced it, which is the whole of BR-RAT-007's seven-year
    # reproducibility promise.
    if version.model == "time_of_use":
        seasons = {
            season.id: season
            for season in models.RateSeason.objects.filter(
                tenant_id=_tenant_id(), tariff_version=version
            )
        }
        rows = list(
            # Ordered by the window's START TIME so an on/mid/off schedule
            # prints in the order the day runs, which is the order the S9 card
            # previews and the order the tenant built.
            #
            # ⚠ THE ORDER IS PRESENTATION AND NOTHING ELSE, and saying so is the
            # point. Until 2026-08-16 the order and the prices of these rows
            # jointly decided which METER REGISTER each window was billed on
            # (BR-RAT-064, superseded). Now `channel` is read from the row, so a
            # reordering — or a bulk price change that reorders two close
            # windows — cannot move a single cent.
            models.TimeOfUseWindow.objects.filter(
                tenant_id=_tenant_id(), tariff_version=version
            ).order_by("start_time", "id")
        )
        inputs["windows"] = [
            {
                "label": window.label,
                "unit_price": window.unit_price,
                # BR-RAT-067 (PO 2026-08-16, OQ-236): THE UTILITY'S OWN ANSWER,
                # read, never derived. None means it was never stated — served
                # as None so the engine refuses BY NAME rather than this read
                # inventing a register to keep the run going.
                "channel": window.channel,
                "season": (
                    seasons[window.season_id].label if window.season_id in seasons else None
                ),
                "day_type": window.day_type,
            }
            for window in rows
        ]
        # WHICH SEASON, resolved HERE and not in the engine. BR-RAT-021 prices
        # per season and the season is a stored month/day range — the same class
        # of lookup as BR-RAT-007's version window, and the engine is pure.
        inputs["season"] = _season_label_on(version, service_date)
        # 🔒 BR-RAT-034 — the calendar days of the period in each season, when
        # it CROSSES a boundary. Counted HERE and nowhere else (the engine holds
        # no calendar); `[]` inside one season, so that bill does not move.
        inputs["season_days"] = _season_days_between(
            version, period_start, period_end or service_date
        )
    elif version.model == "seasonal":
        # 🔒 BR-RAT-034 · `seasonal` IS PRICED (DEF-RAT-8832, built 2026-10-01).
        # Each season carries its own ladder — season-scoped `rate_tiers`, one
        # 0→∞ block for a flat seasonal price (`services._validate_structure`,
        # r6.7). Until this branch existed the `else` above published EVERY
        # season's blocks as ONE ascending ladder, which no engine could price
        # correctly; the model refused at the registry before it mattered.
        season_rows = {
            season.id: season.label
            for season in models.RateSeason.objects.filter(
                tenant_id=_tenant_id(), tariff_version=version
            )
        }
        ladders: dict[str, list[dict[str, Any]]] = {}
        for tier in tiers:
            label = season_rows.get(tier.season_id)
            if label is None:
                continue
            ladders.setdefault(label, []).append(
                {"upper": tier.to_qty, "unit_price": tier.unit_price}
            )
        inputs["season_tiers"] = [
            {"season": label, "tiers": rows} for label, rows in ladders.items()
        ]
        inputs["season"] = _season_label_on(version, service_date)
        # `tiers` is the service-date season's ladder — the same answer a
        # one-season period prices on — never the merged set above.
        inputs["tiers"] = list(ladders.get(inputs["season"] or "", []))
        inputs["season_days"] = _season_days_between(
            version, period_start, period_end or service_date
        )
    elif version.model == "capacity":
        rate = models.CapacityRate.objects.filter(
            tenant_id=_tenant_id(), tariff_version=version
        ).first()
        inputs["capacity"] = (
            None
            if rate is None
            else {"unit_label": rate.unit_label, "rate_per_unit": rate.rate_per_unit}
        )
    elif version.model == "demand":
        config = models.DemandRateConfig.objects.filter(
            tenant_id=_tenant_id(), tariff_version=version
        ).first()
        if config is not None:
            inputs["energy_rate_per_kwh"] = config.energy_rate_per_kwh
            inputs["demand_rate_per_kw"] = config.demand_rate_per_kw
            # Carried so the ENGINE can refuse rather than silently under-bill:
            # BR-RAT-014's ratchet and power-factor measurement rules are still
            # PROPOSED and no plugin computes them (US-RAT-007 TC-8, "no silent
            # math"). Dropping these flags here would hide the tenant's own
            # configuration from the only code that can act on it.
            inputs["ratchet_enabled"] = config.ratchet_enabled
            inputs["pf_penalty_enabled"] = config.pf_penalty_enabled
    elif version.model == "percent_of_service":
        # PERCENT POINTS, exactly as stored and exactly as the tenant typed them
        # on S11 (`services._validate_structure` refuses <= 0 and confirms above
        # 100 — US-RAT-007 TC-6). The division by 100 happens in the plugin.
        #
        # ⚠ SINCE `CR-081` THIS IS A **RETURN-TO-SEWER FACTOR** — the fraction of
        # metered water that physically reaches the sewer, 90 on every tenant
        # this product seeds — and NOT the price ratio it was until 2026-09-08.
        # The rate it multiplies is published as `unit_price` thirty lines up.
        inputs["percent"] = version.percent
        inputs["basis_service"] = version.basis_service.code if version.basis_service_id else None
    return inputs


def pricing_inputs_for_version_id(
    version_id: Any,
    service_date: date,
    size_class: str | None = None,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, Any] | None:
    """The SAME projection again, for a version named by its **ID**.

    ⚠ **ADDED 2026-08-31 FOR R2's FORK, AND IT IS A LOOKUP IN FRONT OF THE ONE
    PROJECTION — NEVER A SECOND ONE.** `pricing_inputs` is a date lookup in
    front of `pricing_inputs_for_version`; this is an id lookup in front of the
    same function, and for the same reason `DEF-434` gave when it split them:
    *"a copy of it would drift on the first shape that gained a column —
    silently, because both copies would still produce a well-formed bill."*
    There is still exactly ONE projection of a stored version onto the engine's
    inputs in this product.

    **WHO ASKS, AND WHY IT CANNOT ASK BY DATE.** `apps/billing/resolution_switch
    .py` — the R1–R7 cutover's per-step fork. R2 decides *plan version → exactly
    one rate schedule version per service* and hands back a version **ID**, with
    no rates and no tiers on it. Serving R2 means pricing the bill from THAT
    version, and a switch that stamped the id onto prices read from the version
    the bill run resolved would put a lie on the document — every figure
    internally consistent and none of them from the schedule the id names.
    Asking `pricing_inputs` by date would re-run the live path's own narrowing,
    which is the answer R2 is being switched away from.

    **A DRAFT IS NOT A VERSION** (`BR-RAT-031`): a row with no `effective_from`
    has never been in force and may never price anything, so it is refused here
    exactly as `activated_versions` refuses it for every date-based read. An
    unknown id, a draft, and a malformed id all answer `None` — the caller turns
    that into a NAMED refusal rather than a fallback to any other version.

    **`service_date` is still taken and is still only the SEASON lookup**
    (BR-RAT-021), identical to `pricing_inputs_for_version`. The version is the
    caller's choice here; the date does not select it.
    """
    if not _valid_uuid(version_id):
        return None
    version = models.TariffVersion.objects.filter(
        tenant_id=_tenant_id(), pk=version_id, effective_from__isnull=False
    ).first()
    if version is None:
        return None
    # BR-RAT-034 — the same served span, so a swapped version is split over the
    # same days against ITS OWN season calendar (built 2026-10-01).
    return pricing_inputs_for_version(
        version, service_date, size_class, period_start=period_start, period_end=period_end
    )


# ── DELETED 2026-08-16: `_TOU_CHANNELS_BY_RANK` + `_window_channels` ─────────
# The price-rank resolver lived here. It read a season's window prices, sorted
# them, and called the dearest `tou_on`, the cheapest `tou_off` and the middle
# one `tou_mid` (BR-RAT-064, PROPOSED, never ratified).
#
# It is DELETED rather than left behind a flag, and that is the deliverable:
# **PO ruling 2026-08-16, verbatim — *"make the rate wizard say which register
# is which"* (OQ-236 CLOSED → BR-RAT-067).** A dormant fallback is exactly what
# the ruling forbids, because the failure mode it ends is silent: the reference
# bill is 88.60 paired correctly and 122.40 paired backwards, and nothing on
# either document looks wrong. `pricing_inputs` above now reads
# `time_of_use_windows.channel`, which a human typed on S11; a window with no
# stated register is served as None and refused BY NAME by
# `apps/rating/pricing/models/tou.py`, never ranked and never priced at 0.00.
#
# Kept as a comment because four files cited BR-RAT-064 by name and a reader
# arriving from one of them must find the ending, not an absence.
# ─────────────────────────────────────────────────────────────────────────────


def _season_label_on(version: models.TariffVersion, service_date: date) -> str | None:
    """The `rate_seasons` label whose month/day window contains the service date.

    BR-RAT-021 prices TOU per season and BR-RAT-034 requires the seasons to
    cover the year without overlap, so at most one matches. A season may WRAP
    the year end — the demo tenant's own Winter runs Oct 1 to May 31 — which is
    why this compares (month, day) tuples rather than dates and treats a wrapped
    range as "on or after the start OR on or before the end".

    Returns None when the version defines no seasons at all (a TOU schedule with
    one price set all year) and ALSO when the seasons leave the service date
    uncovered. The two look alike here and are told apart by the engine, which
    refuses the second (BR-RAT-033's coverage gap) and prices the first — the
    distinction is "does this tariff have seasons", and that is data the plugin
    already holds in `windows`.
    """
    probe = (service_date.month, service_date.day)
    for season in models.RateSeason.objects.filter(
        tenant_id=_tenant_id(), tariff_version=version
    ).order_by("start_month", "start_day", "id"):
        start = (season.start_month, season.start_day)
        end = (season.end_month, season.end_day)
        covered = start <= probe <= end if start <= end else (probe >= start or probe <= end)
        if covered:
            return season.label
    return None


def _season_days_between(
    version: models.TariffVersion, period_start: date | None, period_end: date | None
) -> list[dict[str, Any]]:
    """🔒 BR-RAT-034 — the CALENDAR days of `[period_start, period_end]` in each
    season, chronological, ONLY when the span crosses a boundary; else `[]`.

    HUMAN-REVIEW-PENDING. Built 2026-10-01 for the PO's ruling of 2026-09-07
    closing `OQ-234` (*"please split  swithch it on"*): a bill period that
    crosses a season boundary splits pro-rata by calendar days (BR-RAT-034,
    CONFIRMED PO R5-7). It is `_season_label_on` asked once per DAY instead of
    once per period — the same stored month/day ranges, the same wrap-the-year
    comparison — so the two can never disagree about which season a day is in.

    WE-18 / GT-34: 15 Sep – 14 Oct with Winter starting 1 Oct →
    `[{"season": "Summer", "days": 16}, {"season": "Winter", "days": 14}]`.

    Days no season covers are a share with `season: None` — BR-RAT-033's gap —
    and the engine refuses it by name, as it refuses an uncovered service date
    today. Shares are grouped by season in order of first appearance, so a
    period long enough to re-enter a season (a back-bill) still prices each
    season once, at its total days.

    `[]` when no span was given, when the version defines no seasons, and when
    every day falls in ONE season — the three cases that must price exactly as
    they did before this function existed.
    """
    if period_start is None or period_end is None or period_end < period_start:
        return []
    seasons = list(
        models.RateSeason.objects.filter(tenant_id=_tenant_id(), tariff_version=version).order_by(
            "start_month", "start_day", "id"
        )
    )
    if not seasons:
        return []

    def _label(day: date) -> str | None:
        probe = (day.month, day.day)
        for season in seasons:
            start = (season.start_month, season.start_day)
            end = (season.end_month, season.end_day)
            covered = start <= probe <= end if start <= end else (probe >= start or probe <= end)
            if covered:
                return season.label
        return None

    counts: dict[str | None, int] = {}
    day = period_start
    while day <= period_end:
        label = _label(day)
        counts[label] = counts.get(label, 0) + 1
        day += timedelta(days=1)
    if len(counts) < 2:
        return []
    return [{"season": label, "days": days} for label, days in counts.items()]


def plan_rate_schedules(plan_id: Any) -> list[dict[str, Any]]:
    """The plan's per-service rate schedules — one tariff per service.

    THE SHAPE OF A PLAN, made concrete. A plan is a BUNDLE (PO ruling
    2026-08-11: a unit holds a plan, not a rate schedule), and this is what
    that means in practice: a house on electric + water + trash is on ONE plan
    which resolves here to three tariffs, one per service.

    Billing's gather step calls this to build its per-service pricing inputs.
    It returns the Tariff ROW rather than a dict because the caller must then
    resolve the version IN FORCE AT THE SERVICE DATE (BR-RAT-007) — and a dict
    would either have to carry every version or silently pick one, which is
    exactly the seven-year-reproducibility mistake.

    D2 (r5 #7) makes it one active schedule per service per plan, enforced by
    a unique constraint, so a service appears at most once.
    """
    if not _valid_uuid(plan_id):
        return []
    rows = (
        models.PlanRateSchedule.objects.filter(tenant_id=_tenant_id(), rate_plan_id=plan_id)
        .select_related("service", "tariff")
        .order_by("service__code")
    )
    # DEF-154 / BR-RAT-012 · BR-RAT-027, both CONFIRMED: **the base charge is a
    # PLAN attribute** — *"defined per service within a plan"* — and it lives in
    # `plan_services`, one row per (plan, service). It was published NOWHERE
    # until 2026-08-16, so billing had nothing to read it from and took the
    # schedule's own `tariff_versions.base_charge` instead. That column defaults
    # to `0` and no tenant had ever typed into it, so **every bill this product
    # produced charged $0.00 for base** while the demo tenant's plan said
    # electric 12.00 and water 8.00.
    #
    # `None` where the plan states NO row for the service — deliberately not
    # `0`. `plan_services.base_charge` is NOT NULL with a `0` default, so a row
    # that exists and says zero is a tenant saying "no base charge for this
    # service", and no row at all is the plan not mentioning it. Those are
    # different facts and collapsing them is the shape of the defect itself.
    #
    # ── BR-RAT-028 · THE TWO MINIMUM-BILL THRESHOLDS (CR-052 task 4) ─────────
    # The same reasoning as `base_charge` above, one rule along, and it had the
    # same consequence: BR-RAT-028 is CONFIRMED (*"both modes built"*) and its
    # field map named `plan_services.minimum_amount` (mode A, per service) and
    # `plans.minimum_bill_amount` (mode B, the plan floor). **Neither was
    # published anywhere**, so billing had nothing to read and the stage that
    # owns the rule said so in its own docstring rather than approximating —
    # and a signed rule with a signed worked example (WE-3: `9.60` against a
    # `15.00` floor → **`+5.40`**, total **`$16.42`**) was charged on no bill
    # this product has ever issued.
    #
    # ⚠ **MODE A NO LONGER COMES FROM HERE — PO ruling 2026-09-10, migrations
    # `rating/0030` + `0031`.** Verbatim: *"set it in rates and use it in plans -
    # thats it - this is rule"*. `plan_services.minimum_amount` is GONE; the
    # per-service floor is `tariff_versions.minimum_bill`, which this module has
    # published on `pricing_inputs` all along and which billing deliberately did
    # not read (`DEF-2446`). Billing reads it now, and it is a VERSION fact, so
    # it must travel on the version and not on this plan-shaped row: publishing
    # it here would pick one version for a bill that may be priced from another
    # (`BR-RAT-007`), which is the seven-year-reproducibility mistake this
    # function's own docstring already refuses to make for the tariff itself.
    # **`minimum_amount` is therefore not in the returned dict at all**, rather
    # than being returned as `None` — an absent key is a shape change a caller
    # notices, and a `None` is a floor of "no minimum" that a caller would
    # silently believe.
    #
    # `None` where the plan states no `plan_services` row for the service — the
    # base charge's own case, unchanged. A floor of zero is a different statement
    # from no floor (it bites on nothing) and the two must not collapse.
    plan_bases = {
        str(row.service_id): row.base_charge
        for row in models.PlanService.objects.filter(tenant_id=_tenant_id(), rate_plan_id=plan_id)
    }
    # Mode B is a PLAN attribute, not a per-service one, so it is read once and
    # repeated onto every row: billing's seam carries it on each `TariffConfig`
    # (a plan is a BUNDLE and its services are how a plan reaches the engine),
    # and the engine refuses a bill whose tariffs state two different floors.
    # `BR-RAT-1066` — the floor of the plan VERSION read on the day.
    _plan = models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk=plan_id).first()
    plan_floor = (
        plan_versioning.terms_on(_plan)["minimum_bill_amount"] if _plan is not None else None
    )
    return [
        {
            "service_code": row.service.code,
            "service_id": str(row.service_id),
            "tariff": row.tariff,
            "tariff_id": str(row.tariff_id),
            "base_charge": plan_bases.get(str(row.service_id)),
            "plan_minimum_bill_amount": plan_floor,
        }
        for row in rows
    ]


@batch_reads.memoised(copy=True)
def unit_plan_assignments_in(
    unit_id: Any, *, period_start: date, period_end: date
) -> list[dict[str, Any]]:
    """The unit's dated plan history overlapping [period_start, period_end] —
    BR-RAT-114's "plan change" boundary source (DEF-504).

    `unit_plan_assignments` is the append-only history `record_unit_plan_
    assignment` writes (BR-CUS-013, gap-1 closed 2026-08-11): each row is one
    stretch of "this unit was on THIS plan", closed by the next assignment. An
    ordinary bill whose period contains an `assigned_from` splits there and
    prices each side on its own plan; this selector is how billing sees those
    stretches without reading rating's table (B2 — the module boundary).

    Ordered by `assigned_from` ascending — calendar order, which is bill order.
    Rows are returned AS STORED, clipping is the caller's: which days of a
    stretch fall inside the billing period is the bill run's arithmetic, not a
    fact about the assignment.

    ⚠ AN EMPTY LIST IS NOT "NO PLAN". History predating the table (or a unit
    assigned before gap-1 closed) has no rows; the caller falls back to the
    unit's CURRENT plan exactly as `gather` always has — absence of history
    means no split evidence, never a refusal. `plan_version` is BR-CUS-013's
    snapshot integer, carried for the record; nothing here resolves plan
    CONTENT by it (OQ-323 is unruled and stays unruled).
    """
    if not _valid_uuid(unit_id):
        return []
    rows = (
        models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_id, assigned_from__lte=period_end
        )
        .filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=period_start))
        .order_by("assigned_from", "created_at")
    )
    return [_plan_assignment_row(row) for row in rows]


def _plan_assignment_row(row: Any) -> dict[str, Any]:
    """ONE row of `unit_plan_assignments_in` — shared with the bulk Check's
    batch read (`prime_check_batch`) so the two cannot drift."""
    return {
        "rate_plan_id": str(row.rate_plan_id),
        "plan_version": row.plan_version,
        "assigned_from": row.assigned_from,
        "assigned_to": row.assigned_to,
        "source": row.source,
    }


def plan_jurisdiction_pricing(plan_id: Any) -> dict[str, Any]:
    """BR-RAT-102 — does THIS plan surcharge outside the city, by how much, and
    which of its services escape it. Billing's seam onto R5's two stored facts.

    PO verbatim (2026-08-21, closing `OQ-308` and the money half of `DEF-466`):
    *"We can have it on plan itself - Plan will decide whether to apply and then
    how much"*. So both facts are the PLAN's — the factor on `rate_plans`, the
    per-service exemption on the plan's own service line — and this returns them
    unchanged. **It applies no rule.** Which premises is outside the city is
    `BR-RAT-101`'s fact and lives on `premises`, a table rating may not read
    (B2), so the two-gate decision belongs to whoever holds both — the bill run.

    ── WHAT EACH ABSENCE MEANS, AND WHY THE DISTINCTION IS THE WHOLE POINT ────
    `outside_city_factor` NULL and `outside_city_factor = 1` mean the same
    thing — *this plan does not price by jurisdiction* — and both are returned
    as `None`. That is not a collapse of two facts: BR-RAT-102 states them as
    one (*"absent or `1` = this plan does not surcharge"*), and it matters
    because a plan that does not surcharge **never consults the premises at
    all**, so a utility with no jurisdiction pricing can never be refused by R5
    over a flag nobody recorded. Returning `Decimal("1")` here instead would
    make the caller test a figure where it should be testing an absence.

    ⚠ **THIS PARAGRAPH SAID "NULL ON EVERY ROW OF EVERY TENANT TODAY" UNTIL
    2026-08-27 (`DEF-515`, CR-039 wave C task 11).** The two columns landed with
    migration 0016 and nothing at any layer wrote them — no `PLAN_FIELDS` entry,
    no serializer, no wizard control, no seeder payload — so this returned
    `{"outside_city_factor": None, "exempt_services": ()}` for every seeded plan
    and not one figure moved.
    **What is true now:** `PLAN_FIELDS` carries `outside_city_factor`,
    `PLAN_SERVICE_FIELDS` carries `outside_city_exempt`, and the sample
    Residential plan states r10's `1.5` with `sewer` exempt. A demo tenant
    therefore prices an outside-city bill — `161 Silver Creek Rd`, June 2026,
    18 kgal: water usage `$109.00 → $163.50`, base `$8.00 → $12.00`.
    **What is STILL missing and is DEF-515's remaining half:** no PLN-03 wizard
    control writes the factor, so a utility can express the surcharge through
    the API and not yet through a screen. Read from the columns rather than
    defaulted, which is why nothing here had to change when the write half
    landed — the same late-binding posture `gather._premises_geography` took.

    ⚠ **`charges.outside_city_applies` IS NOT HERE AND IS NOT MISSING.** That
    column says whether a given CHARGE is subject to the factor and R4 already
    honours it (`resolution.resolve_charge_codes`); this says what the factor
    IS. Two questions, two answers — BR-RAT-102's own words.
    """
    if not _valid_uuid(plan_id):
        return {"outside_city_factor": None, "exempt_services": ()}
    plan = models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk=plan_id).first()
    # `BR-RAT-1066` — the factor of the plan VERSION read on the day (the head's
    # is the plan's own column; another version's is its own copy).
    factor = (
        plan_versioning.terms_on(plan)["outside_city_factor"] if plan is not None else None
    )
    if factor is not None:
        factor = factor if isinstance(factor, Decimal) else Decimal(str(factor))
        if factor == Decimal("1"):
            factor = None  # BR-RAT-102: `1` and absent are the same statement
    return {
        "outside_city_factor": factor,
        # §A4 S2's *"BASE-S $8.00 (flat everywhere — the multiplier does NOT
        # touch sewer)"*. Service CODES, because that is what the bill run
        # narrows by and what `resolution.Catalogue.outside_city_exempt_services`
        # holds; the id would make the caller join back to a table it does not own.
        "exempt_services": tuple(
            sorted(
                row.service.code
                for row in models.PlanService.objects.filter(
                    tenant_id=_tenant_id(), rate_plan_id=plan_id, outside_city_exempt=True
                ).select_related("service")
            )
        ),
    }


def _rides_a_periodic_bill(code: models.Charge) -> bool:
    """`BR-RAT-730` — does THIS charge code's own trigger put it on an ORDINARY
    periodic bill? The TRIGGER half of `billable_charge_codes` (`DEF-RAT-5784`).

    PO 2026-08-22, verbatim: *"ruccuring and Autom apply land on bill"*. PO
    2026-09-19, verbatim: *"the charge code decides / Naming a charge in a plan
    makes it available. Whether it bills monthly is the charge code's own
    setting"*. **Both columns, and the conjunction is the whole of it** — a
    code that is recurring but not auto-apply, or auto-apply but one-time,
    waits for its own trigger, which is what `charge_type` is for.

    ⚠ **THIS RESTATES `resolution.rides_a_periodic_bill` AND DELIBERATELY DOES
    NOT CALL IT.** `base_charge_from_charge_code` below records the reason in
    full: the pricing shadow compares this module's two narrowings at R4, and
    *"a comparison whose two sides are the same function is a check that cannot
    fail"*. So the two are held in step by a TEST that asserts they agree —
    `test_def_rat_5782_plan_named_codes_honour_the_trigger.py` — rather than by
    a call, and the test is what goes red if either drifts.

    ⚠ **TWO DELIBERATE DIVERGENCES FROM R4's VERSION, BOTH PINNED BY THAT SAME
    TEST SO NEITHER CAN BE MISTAKEN FOR DRIFT:**

    * **`is_base` IS NOT CONSIDERED HERE.** R4's version returns `True` for a
      base code, because `resolve_base_charge` reads its output and gating the
      base on `auto_apply` is a base that does not exist (`DEF-154`: `$8.00`
      residential water to `$0.00`). This selector excludes `is_base` by name
      one step earlier — `BR-RAT-088`, the base has its own route, and letting
      it in bills `$12.00` twice — so a base code never reaches this predicate
      and asking the question of it would be meaningless.
    * **AN `auto_apply` NON-RECURRING CODE IS OMITTED, NOT REFUSED.** R4 raises
      `ChargeCodeRecurrenceConflict` — two columns a person filled in that
      contradict each other, *"a `$250.00` tamper fee on one bill or on
      twelve"*. Returning `False` here omits it instead. **That is this
      function's pre-existing behaviour and is NOT changed by `DEF-RAT-5784`**:
      route 1 has always expressed the conjunction as a queryset filter, which
      omits silently, and introducing a new refusal onto the LIVE fee path is a
      different change with a different blast radius — it can stop a bill run,
      and this one must only stop lines that should never have been on a bill.
      **It cannot fire on `brazosbend` today: that tenant holds ZERO
      `auto_apply` codes of any type** (measured 2026-09-19). Filed as
      `OQ-RAT-12464`, OPEN.
    """
    return bool(code.auto_apply) and code.charge_type == "recurring"


def billable_charge_codes(
    plan_id: Any,
    service_date: date,
    *,
    customer_class: str | None = None,
    services: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """`BR-RAT-117` — the charge codes that belong on an ordinary bill.

    🔒 HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.

    PO ruling 2026-08-22, verbatim: *"ruccuring and Autom apply land on
    bill"*. **AVAILABILITY and TRIGGER are two different questions, and this
    function asks both — amended 2026-09-19 (`DEF-RAT-5784`).**

    ⚠ **WHAT THIS USED TO DO, AND WHAT IT COST.** Until 2026-09-19 the two
    routes were unioned and only ONE of them tested the trigger. A code
    arrived because it was `recurring` AND `auto_apply` (route 1), **or
    because the plan named it through `plan_charge_rules` — with no
    `charge_type` test and no `auto_apply` test at all** (route 2). So
    anything a plan named rode every cycle whatever its declared trigger.
    **Measured on the `brazosbend` tenant on 2026-09-19: nine
    `plan_charge_rules` attachments, five distinct codes, every one of them
    `penalty` or `one_time` — `TAMPER` `$250.00`, `NSF` `$30.00`, `CONN`
    `$45.00`, `DISC` `$45.00` and `LATE` — across ten units on three plans.
    `$955.00` a month, `$11,460.00` a year, and a `$250.00` tamper fee billed
    twelve times a year without anyone tampering.** Route 1 selected NOTHING
    on that tenant (it holds no `recurring` + `auto_apply` code at all), so
    **every fee line the product could produce was one of those nine.**

    **THE RULING THIS RESTORES.** PO 2026-09-19, verbatim: *"this is correct
    understanding - option a is ocrect - A — the charge code decides / Naming
    a charge in a plan makes it available. Whether it bills monthly is the
    charge code's own setting"*, and, the same day on the plan wizard, *"plan
    is only binding - even plan should not talk about rules here"*.

    **SO THE SHAPE IS: CANDIDATES, THEN ONE TRIGGER GATE.**
    * **AVAILABILITY** — a code is a candidate because the tenant auto-applies
      it tenant-wide, **or** because this plan names it. That union is
      unchanged, and it is still keyed on the code, so a code reached both
      ways bills ONCE (`BR-RAT-088`'s `$24.00`-for-one-`$12.00`-fee failure).
    * **TRIGGER** — a candidate rides an ordinary periodic bill only when its
      own two columns say so: `charge_type == "recurring"` AND `auto_apply`.
      That is `BR-RAT-117` read literally and `BR-RAT-730` verbatim, and it is
      the predicate `resolution.rides_a_periodic_bill` already applies at R4.

    ⚠ **THIS IS A CORRECTION OF AN OVER-IMPLEMENTATION, NOT A REVERSAL.**
    `BR-RAT-117` (PO 2026-08-22) authorises route 1 in terms — *"a charge code
    marked `recurring` AND `auto_apply` lands on every ordinary bill WITHOUT
    THE PLAN NAMING IT"* — and says nothing that exempts a plan-named code
    from its own trigger. Route 2 was added by `DEF-561` to close a real gap
    (`plan_charge_rules` had no billing reader at all and `gather` left `fees`
    empty) and went further than the words it cited. Nothing signed is
    reversed here; the extra latitude is withdrawn.

    ⚠ **AND THE TRIGGER GATE MAKES ROUTE 2 A SUBSET OF ROUTE 1, WHICH IS
    STATED RATHER THAN HIDDEN.** `auto_apply` is precisely *"rides without the
    plan naming it"*, so a candidate that passes the trigger was already a
    route-1 candidate and **the plan binding selects nothing route 1 has not
    already selected.** The union is kept because it is the honest expression
    of the ruling's two sentences and because `plan_id` is the seam's key —
    not because it adds a row today. **Whether a utility should be able to put
    a monthly fee on ONE plan (a `recurring` code, not auto-applied, named by
    that plan) is a real capability this closes off, and it is `OQ-RAT-12463`,
    OPEN.** It is not decided here: the product has no screen that expresses
    it, and `DEF-RAT-5779`'s step-4 column would print *On every bill: No*
    beside a code that billed monthly — a screen contradicting a bill, which
    the PO ruled against the same day.

    **The narrowing is R4's and is deliberately the same three questions**
    (`resolution.resolve_charge_codes`): the code's service matches or it is
    account-level, and its `applies_to_customer_classes` includes this
    account's class — BR-RAT-108's INCLUSION list, where NULL or `[]` means
    every class.

    ⚠ **`is_base` CODES ARE EXCLUDED, and that is BR-RAT-088 not a
    preference.** The base charge already reaches the bill as the service's
    base through R4, so letting it in here would bill $12.00 twice — the
    exact $23,069.50-a-month failure §A3 priced when it moved the base onto
    the charge code.

    ⚠ **A PER-SIZE CODE REFUSES BY NAME RATHER THAN BILLING A GUESS.** The
    per-size ladder is resolved per SERVICE against a connection size, and
    this reader is handed the account's services but not their sizes; billing
    the flat column instead would charge a 5/8" price to a 2" connection.
    Named, filed, and left refusing — the repo's own posture (`R4`: *"no
    amount refuses"*).
    """
    # ── AVAILABILITY: the two ways a code becomes a CANDIDATE ───────────────
    # The union is keyed on the code, so a code reached BOTH ways is one
    # entry and therefore one line — BR-RAT-088's $24.00-for-one-$12.00-fee.
    codes: dict[Any, models.Charge] = {}
    auto = models.Charge.objects.filter(
        tenant_id=_tenant_id(),
        deleted_at__isnull=True,
        charge_type="recurring",
        auto_apply=True,
    )
    for row in auto:
        codes[row.id] = row
    named = models.Charge.objects.filter(
        tenant_id=_tenant_id(),
        deleted_at__isnull=True,
        id__in=models.PlanChargeRule.objects.filter(rate_plan_id=plan_id, tenant_id=_tenant_id()).values("charge_id"),
    )
    for row in named:
        codes.setdefault(row.id, row)  # the union: already present ⇒ still ONE line

    out: list[dict[str, Any]] = []
    for row in codes.values():
        if row.is_base:
            continue  # BR-RAT-088 — the base has its own route
        if not _rides_a_periodic_bill(row):
            # ── TRIGGER (`DEF-RAT-5784`) ────────────────────────────────────
            # The charge code decides, never the plan that named it. Applied
            # to the WHOLE union rather than inside route 1, because that is
            # the half route 2 was missing and the reason `$955.00` a month of
            # penalties and connection fees rode an ordinary bill.
            #
            # NOT AN ERROR, and that is `BR-RAT-730` in terms: a `one_time`
            # connection fee is a code with a DIFFERENT trigger, not a missing
            # fact. Refusing here would stop every bill on every tenant — 22
            # of `brazosbend`'s 29 codes are `one_time` or `penalty`.
            continue
        service = row.service.code if row.service_id else None
        if service is not None and services and service not in services:
            continue
        classes = row.applies_to_customer_classes or []
        if classes and customer_class not in [str(code) for code in classes]:
            continue
        # CR-156-BRC10 — read through the one lookup, ON THE SERVICE DATE: a
        # code that states sizes on that day (for any class — the old test was
        # any row at all) cannot ride a bill as a fee.
        priced = charge_prices.resolved_tables([row.id], service_date, customer_class).get(
            row.id, {}
        )
        if charge_prices.sized_charge_ids([row.id], service_date):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-117",
                message_key="rating.charges.per_size_not_billable",
                params={"code": row.code},
            )
        out.append(
            {
                # WHICH CODE THIS IS (`DEF-714`, 2026-08-25). The id is what the
                # fee line carries to issue, where BR-BIL-010 resolves the
                # code's own GL account (`gl_account_id_for_charge` below).
                # Without it the line reaches `invoice_lines.charge_id` NULL and
                # the whole bill is refused at issue — a tenant that configured
                # ANY recurring or auto-apply code could issue no bill at all.
                # A string, like every other id this module publishes, so no
                # caller ever holds a live model instance across the seam.
                "id": str(row.id),
                "code": row.code,
                "name": row.name,
                "service": service,
                # CR-156-BRC10 — the *All sizes* row for this customer class
                # (or every class) in force on the bill's service date.
                # DEF-RAT-9807 — a `per_case` code's *All sizes* row is the
                # DEFAULT a clerk starts from (`BR-RAT-1054` AMENDED), never a
                # price this reader may put on a bill nobody typed into: such a
                # code answers None here exactly as it did before it had one.
                "amount": (
                    None
                    if row.amount_rule == "per_case"
                    else (priced[ALL_SIZES].amount if ALL_SIZES in priced else None)
                ),
                "taxable": bool(row.taxable_default),
            }
        )
    return sorted(out, key=lambda entry: entry["code"])


#: `DEF-RAT-9832` — rating's tag for *"the rate schedule names no base code"*.
#: Billing reads `not_set` (and bills `$0.00` with its named warning); the
#: two configuration reads (`_plan_base_total`, `seams` base seam) read THIS
#: tag and state `$0.00`, because that is what the bill charges.
BASE_NOT_NAMED = "base_not_named"


def _no_base_code_named(service_code: str) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING — `DEF-RAT-9832`. **The rate schedule names no
    base code, so the base is `$0.00` — for every account on it, whatever its
    customer class.**

    PO ruling 2026-10-06, verbatim: *"You will take the code from plan -> rate
    schedule -> base charges - in that case if it is provided then you will
    take it if it is not provided then you will take it zeo ; but you cannot
    take W-COM because it is availabel in charge coede - I have provided this
    before also- you have asked again"* — restating 2026-09-30's *"if user did
    not define and bind base charges in rate schedule - then as a default you
    take 0 and complete the bill instead of refusing"*.

    **WHAT THIS REPLACED, AND WHY IT IS GONE RATHER THAN NARROWED:** until
    2026-10-06 a `named_code` of None fell through to a POOL — every live
    `is_base` code of the service, narrowed by the account's customer class —
    and billed whichever survived (W-ALL `$8.00` for a residential account) or
    refused when two did (*"2 base charge codes for water"* for a commercial
    one, `DEF-RAT-9829`). That is a code taken from the charge-code list by
    class, which the ruling forbids by name. Worked: W-ALL `$8.00` (every
    class) + W-COM `$15.00` (Commercial) on a schedule naming none → residential
    `$8.00` → `$0.00`, commercial *refused* → `$0.00`, both warned.

    `not_set` routes it through billing's existing 2026-09-30 path (`$0.00` +
    `billing.oneTime.warn.baseNotSet`) — no second warning is invented. The
    sentence is for the configuration screens only; it never reaches a bill.
    """
    return {
        "amount": None,
        "code": None,
        "refusal": "No base code on the schedule. Choose one there.",
        "refusal_reason": BASE_NOT_NAMED,
        "not_set": True,
    }


def _named_code_cannot_answer(service_code: str, named_code: str) -> dict[str, Any]:
    """The refusal for a binding that cannot price this account (`DEF-RAT-6918`).

    **SIX WORDS A SENTENCE, TWO SENTENCES, STATE THEN REPAIR** — B14 rule 33,
    the same shape as the two refusals beside it. The RATIONALE is zero words
    on screen (rule 33 again) and lives in the caller's comment: the code
    prices another service, it is scoped to other customer classes, or it has
    been retired or un-ticked since the schedule named it.

    **THE REPAIR POINTS AT THE RATE SCHEDULE AND NOT AT CHARGE CODES**, which
    is the one thing that distinguishes it from its neighbours: the binding is
    on the schedule's first step, it is where a person made this choice, and
    it is the only place BOTH cures are available — widen the code or clear the
    binding and let the service's declared base answer.

    ⚠ **NO `refusal_reason`.** That key is a DISCRIMINATOR for the one refusal
    that is a SCOPING fault rather than a tariff fault (`DEF-2381`), and this
    is a tariff fault — it is repaired on a price list, not on an account. It
    therefore reaches the run screen under billing's ordinary tariff reason,
    which is where a clerk already looks for it.
    """
    return {
        "amount": None,
        "code": None,
        "refusal": (
            f"{named_code} cannot price {service_code} here."
            " Change it on the rate schedule."
        ),
        # `BASE_NOT_SET` — PO ruling 2026-09-30, case (b): no base code is
        # BOUND for this account. See `base_charge_from_charge_code`.
        "not_set": True,
    }


@batch_reads.memoised(copy=True)
def base_charge_from_charge_code(
    service_code: str,
    *,
    customer_class: str | None = None,
    size_class: str | None = None,
    named_code: str | None = None,
    on_date: date | None = None,
) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.

    ── `on_date` · THE PRICE IN FORCE ON THE BILL'S DATES (CR-156-BRC10) ─────
    PO 2026-10-01, option A: *"A past bill reads the row in force on its
    dates."* Billing passes the SERVICE date it prices (`gather._tariff_
    config_for`'s `service_date`; each split segment passes its own first
    day). `None` is the tenant's today — the two configuration screens that
    call this (plan list base total, rate-change impact) ask about now. The
    amount comes from `charge_prices.price_on_date`, the one lookup; every
    refusal sentence below is unchanged.

    **`BR-RAT-088` FOR THE LIVE PATH — the base a CHARGE CODE states for one
    service, at one customer class, at one connection size.**

    PO ruling 2026-08-20, verbatim: *"the CHARGE CODE owns the base amount; a
    plan displays it, never defines it."*

    ⚠ **THE SENTENCE THAT FOLLOWED THAT ONE HAS BEEN CORRECTED BY THE PRODUCT
    OWNER (`CR-120-BRC06`, `BR-RAT-1025`, 2026-09-19).** It read: *"PO
    2026-08-31, naming the middle step: `plan -> charges code -> base
    scharges`"* — and that order is not the chain. **CURRENT, PO 2026-09-19:**
    *"no this is not correct ; So: plan → rate schedule -> charge code → base
    charges - this is correct"*. The account resolves to a plan, the plan
    attaches a RATE SCHEDULE per service, and the schedule may NAME the code
    that owns that service's base; where it names none, the base is the code
    that DECLARES itself that service's base, which is what this function
    finds. The SOURCE and the arithmetic are untouched — *"base will come from
    base"*, the same ruling.

    ⚠ **AND THIS FUNCTION IS THE LIVE PATH, WHICH NOW RECEIVES THE BINDING —
    `DEF-RAT-5782`, FIXED 2026-09-27.** This paragraph read *"WHICH DOES NOT
    YET RECEIVE THE BINDING … the binding unblocks it on the ruled chain and
    not yet here"* for eight days, and it was accurate when written: nothing
    passed `named_code`, because `selectors.pricing_inputs_for_version` did
    not publish the schedule's binding at all, so no caller could have passed
    one however carefully it was written. **What it got wrong was the SIZE of
    the consequence.** It said the live path *"cannot BILL a different figure
    from the one the screen shows — it REFUSES"*, and that was true and was
    not harmless: a real utility with three `is_base` water codes could not
    produce a move-out final bill at all, and the product never said that the
    choice on its rate schedule was being ignored. A bounded failure is still
    a failure. **The hop is `pricing_inputs_for_version` →
    `billing.gather._base_charge_code_for` → here.**

    RETURNS `{"amount": Decimal | None, "code": str | None, "refusal": str |
    None}`, plus `"refusal_reason": str` on the ONE refusal that is not a
    tariff fault (see the customer-class entry below). **`amount is None` with
    no refusal means THIS TENANT HAS DECLARED NO BASE CODE FOR THIS SERVICE**
    — not that the base is zero. The caller keeps billing whatever it billed
    before, which is the only thing that lets a tenant provisioned before the
    ruling go on producing bills.

    ⚠ **AND THAT SENTENCE USED TO COVER A SECOND, OPPOSITE CONFIGURATION —
    `DEF-2381`.** *No base code for this service* and *base codes that all name
    other customer types* both arrived here as an empty match set and both got
    the silent fallback. The first is a tenant that has not adopted the ruling;
    the second is a misconfiguration that costs a customer their whole bill.
    They are separated now.

    ⚠ **A REFUSAL IS RETURNED, NOT RAISED, AND THAT IS `BR-BIL-055`.** A raise
    here would stop a 500-account run on its first account; a named reason
    stops ONE account on the exception screen and lets the other 493 bill. The
    caller (`apps.billing.gather`) turns it into a `GatherProblem` carrying
    this sentence whole.

    ── WHY THIS IS A SECOND NARROWING AND NOT A CALL INTO THE CHAIN ──────────
    `resolution.resolve_charge_codes` + `resolve_base_charge` answer the same
    question for the R1–R7 chain. This does NOT call them, deliberately: the
    pricing shadow compares the two answers at **R4**, and a comparison whose
    two sides are the same function is a check that cannot fail — the failure
    class this repo found seven of in one day. Two independent narrowings over
    one table is the same posture `plan_tax_rules` and `resolve_taxes` already
    take at R7, which is the only step that has ever disagreed.

    ── `not_set` · WHICH REFUSALS BILLING NO LONGER REFUSES ON (2026-09-30) ──
    PO ruling 2026-09-30, verbatim: *"if user did not define and bind base
    charges in rate schedule - then as a default you take 0 and complete the
    bill instead of refusing - if you want to show the warning you can display
    it dueing the process"*. The reading recorded in the decision log the same
    day names four cases, and each of them now carries **`"not_set": True`**
    beside its sentence: (b) the schedule NAMED a code that cannot answer for
    this account — no code is bound for it · (c) base codes exist and none of
    them reaches this customer type, or the account states no type · (d) the
    base code states no amount at all. Case (a), no `is_base` code for the
    service, was already `amount is None` with no refusal.

    **THE SENTENCE IS KEPT AND ONLY A FLAG IS ADDED, DELIBERATELY.** This
    function has three callers: billing's gather, which now reads `not_set`
    and bills `$0.00` with a named warning; and two rating screens (the plan
    list's base total and the rate-change impact), which go on treating it as
    *cannot state a base* — correct for a CONFIGURATION surface, where the
    missing binding is exactly what a person should see. The conflicts — two
    codes, an amount AND sizes, an unpriced size, an unrecorded size — carry
    no flag and still refuse everywhere, because each is the utility having
    defined something that contradicts itself, and choosing is a guess about
    money.

    ── `named_code is None` · NO POOL (`DEF-RAT-9832`, PO 2026-10-06) ───────
    ⚠ **EVERY SENTENCE ABOVE THAT SAYS *"where it names none, the base is the
    code that DECLARES itself that service's base"* IS SUPERSEDED.** PO,
    verbatim: *"You will take the code from plan -> rate schedule -> base
    charges - in that case if it is provided then you will take it if it is
    not provided then you will take it zeo ; but you cannot take W-COM because
    it is availabel in charge coede"*. So a schedule naming none answers
    `_no_base_code_named` (`not_set`, `refusal_reason: "base_not_named"`) for
    every account, before any class narrowing: `$0.00` and the warning. The
    branches below that narrow by class now run ONLY under a named code, and
    the `rows`-empty branch (no `is_base` code for the service at all) is
    unchanged — billing already bills it `$0.00` with the same warning.

    ── THE SIX REFUSALS, EACH NAMING WHAT IS ACTUALLY IN THE WAY ────────────
    * **the schedule NAMED a code and that code cannot answer for this
      account** (`BR-RAT-1025`, `DEF-RAT-6918`) — retired, un-ticked as a
      base, pricing another service, or scoped to customer classes this
      account is not in. `_named_code_cannot_answer` above is the sentence.
      **It never falls back to the inferred code**, which would bill a figure
      the schedule's own first step does not show. It is the answer
      `resolution.resolve_base_charge`'s named arm already gives and the one
      `services._guard_bound_base_charge_code` already gives at activation.
    * **base codes exist for this service and none of them names this
      account's customer type** (`DEF-2381`, PO 2026-09-02). The ONE refusal
      here that is not about money: `applies_to_customer_classes` is an
      INCLUSION list, so a type nobody listed matches nothing, and until this
      landed the account fell silently through to the plan or to the retired
      schedule column and its clerk found out when the bill did not arrive.
      It carries `refusal_reason: "customer_class"` so billing can name it
      separately on the run screen — every other refusal here is a tariff
      fault and this one is a scoping fault, and they are repaired in
      different places.
    * **two base codes survive the narrowing** — `charges.is_base` is a bare
      boolean with no uniqueness constraint, so the catalogue can hold two.
      Taking the first would bill by catalogue ORDER (`DEF-468`, PO 2026-08-21).
    * **a code stating BOTH a flat amount and a per-size table** — CR-013 part
      2 gives a code one basis; choosing one would decide what a customer pays.
    * **a per-size code and a size it does not price** — PO ruling 2026-08-28:
      an unpriced size is REFUSED and never substituted. Falling back to the
      flat column would charge a 5/8" price to a 2" connection.
      ⚠ **2026-10-01: STILL RETURNED, NOW TAGGED `refusal_reason:
      "size_not_priced"`** (with `size_class`). The PO ruled that for a
      CAPACITY service a size with no base price bills that size's base at
      `$0.00` with a warning, never a refusal; billing reads the tag and does
      exactly that for capacity services only. Never substituted still holds:
      the zero is not another size's rate. Every sized answer also carries
      `per_size: True`, so billing can multiply a per-size base by the count.
    * **a code that states no amount at all** — priced per case (`per_case`,
      which since `DEF-2340` is how TAP, IMPACT, DAMAGE and BULK-WATER are
      stored), or never priced; neither is an amount, and `$0.00` is a silent
      wrong answer for both.
    """
    tenant_id = _tenant_id()
    # ⚠ **THE ROWS BEFORE THE NARROWING ARE KEPT, AND THAT IS THE WHOLE OF
    # `DEF-2381`.** Until 2026-09-02 this was one comprehension and the two
    # empty answers below were the SAME answer: *no base code survives*. They
    # are opposite facts. A service with no `is_base` code at all belongs to a
    # tenant that has not adopted `BR-RAT-088` and must go on billing from the
    # plan; a service whose codes all name customer types this account is not
    # one of is a MISCONFIGURATION, and it cost a customer their whole bill
    # while the product said nothing.
    rows = list(
        models.Charge.objects.filter(
            tenant_id=tenant_id,
            is_base=True,
            deleted_at__isnull=True,
            service__code=service_code,
        ).select_related("service")
    )
    if named_code is None and rows:
        # ── `DEF-RAT-9832` · PO 2026-10-06 — NO POOL. ─────────────────────────
        # The schedule names no base code, so nothing is taken from the
        # charge-code list by class: the base is `$0.00` with the warning. It
        # stands BEFORE the class narrowing on purpose — a schedule naming none
        # is the same fact for a residential and a commercial account, and the
        # narrowing below is exactly the pool the ruling retires.
        return _no_base_code_named(service_code)
    matches = [
        row
        for row in rows
        # BR-RAT-108 — an INCLUSION list where NULL or `[]` means EVERY CLASS.
        if not (row.applies_to_customer_classes or [])
        or customer_class in [str(code) for code in row.applies_to_customer_classes]
    ]
    if named_code is not None and matches:
        # ── `CR-120-BRC06` · `BR-RAT-1025` — THE SCHEDULE SAID WHICH ONE ─────
        # A caller that knows the rate schedule can hand its binding down, and
        # the binding is what settles `DEF-468`'s ambiguity: a utility with a
        # residential and a commercial base no longer has the catalogue's order
        # deciding what a customer pays, because a person said.
        #
        # ⚠ **NARROWED HERE, AFTER THE CLASS FILTER AND BEFORE THE AMBIGUITY
        # TEST, AND THE POSITION IS THE RULE.** Before the class filter it
        # would hand back a code scoped to somebody else's customer type;
        # after the ambiguity test it would never run, because two codes have
        # already refused. It narrows the SURVIVORS.
        #
        # ⚠ **AN EMPTY RESULT REFUSES, NAMING THE CODE — `DEF-RAT-6918`, AND
        # THIS PARAGRAPH SAID THE OPPOSITE UNTIL 2026-09-27.** It read: *"AN
        # EMPTY RESULT FALLS THROUGH TO THE UNNAMED BRANCHES BELOW AND DOES
        # NOT REFUSE HERE … that branch already says it in the operator's own
        # terms"*. **The branch it pointed at is guarded by `not matches` and
        # cannot run while OTHER codes survive**, which is exactly the case
        # that reached here — so the fall-through landed on the ambiguity
        # count instead, telling a clerk to scope charge codes when the
        # scoping is what they had already done. A comment claiming a
        # guarantee is not the guarantee (hard-won law 1).
        #
        # ⚠ **AND WITH ONE OTHER CODE IN THE CATALOGUE IT WAS WORSE THAN A
        # WRONG SENTENCE: it was a SILENT WRONG BILL.** One survivor means no
        # ambiguity, so the fall-through simply billed the INFERRED code while
        # the schedule's own first step named another — `BR-RAT-088`'s failure
        # shape exactly, a well-formed document nobody can see is wrong.
        #
        # **THIS IS THE SAME ANSWER THE RULED CHAIN ALREADY GIVES.**
        # `resolution.resolve_base_charge`'s named arm refuses by name for
        # these very causes — the code prices another service, it is scoped to
        # other customer classes, or it has been retired or un-ticked since the
        # schedule named it. The two narrowings are deliberately separate
        # implementations (see this function's own docstring) and they must
        # agree on the ANSWER; the shadow compares them at R4.
        #
        # ⚠ **WHAT IS NOT REACHED HERE, AND IS NOT A REGRESSION.** When NO
        # code at all reaches this account's customer class, `matches` is
        # empty and this whole block is skipped — `DEF-2381`'s branch below
        # answers, in the operator's own terms, and it is still the better
        # sentence for that fact. The guard on the `if` is what routes it.
        chosen = [row for row in matches if row.code == named_code]
        if not chosen:
            return _named_code_cannot_answer(service_code, named_code)
        matches = chosen
    if len(matches) > 1:
        return {
            "amount": None,
            "code": None,
            # ⚠ **WHY THIS SENTENCE IS SIX WORDS AND NOT SIXTY —
            # `DEF-CUS-6550`.** Everything this message used to explain is
            # still true and is now HERE rather than on a clerk's screen:
            # the bill refuses rather than charging whichever code the
            # catalogue happened to list first, because the amounts differ
            # and the order of a query would decide what a customer pays
            # (`DEF-468`); exactly one base code must survive the narrowing
            # by service and customer class; and `BR-BIL-055` keeps the run
            # going for every other account. **B14 rule 32 forbids a rule id
            # on a clerk's screen and rule 33 puts RATIONALE at ZERO words**,
            # so what reaches the screen is the STATE and the REPAIR, six
            # words each. The codes themselves are one click away on Charge
            # codes, filtered by this service.
            "refusal": (
                f"{len(matches)} base charge codes for {service_code}."
                " Scope them on Charge codes."
            ),
        }
    if not matches and rows:
        # ── `DEF-2381` · THE CODES EXIST AND NONE OF THEM CLAIMS THIS ACCOUNT ─
        # PO 2026-09-02, on the half of `DEF-3282` the data fix could not
        # reach: *"A utility that adds their own customer type — agricultural,
        # a housing association, anything — hits the same wall on their own
        # data, and the product still won't say a word. It should be a named
        # finding on step 2 … so a clerk sees it in the review step instead of
        # discovering a missing bill later."*
        #
        # ⚠ **IT IS NOT SOFTENED INTO THE FALLBACK ABOVE, AND THAT IS THE
        # DECISION.** Falling through to the plan — or, with the R3/R4 chain
        # served, to `tariff_versions.base_charge`, the column `BR-RAT-088`
        # RETIRED — bills this customer a figure their utility never scoped to
        # them, from an object the ruling says no longer owns the base. It is
        # `DEF-154`'s shape: a well-formed bill produced from whichever number
        # the code happened to reach. One named account on the exception screen
        # is the honest answer and the other 493 still bill (`BR-BIL-055`).
        #
        # `refusal_reason` is a DISCRIMINATOR, not billing's reason code:
        # billing maps it to its own vocabulary and an older billing half that
        # does not read the key simply gets today's generic tariff refusal.
        #
        # ⚠ **THE LIST OF CLASSES THAT *ARE* COVERED CAME OFF THIS SENTENCE ON
        # 2026-09-24 (`DEF-CUS-6550`) AND IS NOT LOST.** It was built here as
        # `", ".join(sorted(applies_to_customer_classes))` and printed inline,
        # which put a 44-word paragraph on a clerk's screen against B14 rule
        # 33's six. Charge codes shows every base charge for this service with
        # its customer-type list beside it, so the fact is one click from the
        # repair rather than recited in front of it.
        if customer_class:
            sentence = (
                f"No {service_code} base charge for {customer_class}."
                " Add that type on Charge codes."
            )
        else:
            # The same finding from the other end: the account states no type,
            # so an inclusion list cannot include it. The repair is on the
            # ACCOUNT rather than on the charge, and the sentence says so —
            # which is the whole of what a clerk needs and is why the two
            # branches survive rule 33's cut rather than collapsing into one.
            sentence = "This account has no customer type. Set it on the account."
        return {
            "amount": None,
            "code": None,
            "refusal": sentence,
            "refusal_reason": "customer_class",
            # PO ruling 2026-09-30, case (c) — no base code for this customer
            # type is *not defined*, so billing takes $0.00 and warns.
            "not_set": True,
        }
    if not matches:
        # NOT AN ERROR. This tenant has not adopted BR-RAT-088 for this service
        # and the caller keeps whatever source it had. Saying "no base" here
        # would be DEF-154 the other way round.
        #
        # ⚠ **THIS BRANCH IS NOW REACHED ONLY WHEN THE SERVICE HAS NO `is_base`
        # CODE AT ALL** (`DEF-2381`). It used to answer for two opposite
        # configurations and the second one is the finding above.
        #
        # ⚠ **AND A SCHEDULE THAT NAMED A CODE IS A THIRD CONFIGURATION,
        # WHICH THE SILENCE ABOVE WOULD GET EXACTLY WRONG (`DEF-RAT-5782`
        # requirement 3).** *Nobody has adopted the ruling* and *the one code
        # this schedule names was retired, or had its base tick taken off*
        # arrive here identically — no `is_base` row for the service — and
        # they are opposite facts. The first must go on billing yesterday's
        # figure; the second is a binding a person made and can still see on
        # the rate schedule's first step, and billing the plan's old figure
        # under it is the silent wrong bill this whole change exists to stop.
        # `services._guard_bound_base_charge_code` refuses this at ACTIVATION;
        # somebody changing the code afterwards is the same fact arriving
        # late, and it fails the same way.
        if named_code is not None:
            return _named_code_cannot_answer(service_code, named_code)
        return {"amount": None, "code": None, "refusal": None}
    charge = matches[0]
    # ── CR-156-BRC10 · THE ONE LOOKUP ───────────────────────────────────────
    # Rules 1–3 (class beats every class · flat OR sized · NULL is not zero)
    # used to be applied here, by a loop over `charge_code_amounts` and a read
    # of `charges.amount`. They live in `charge_prices.answer_from_rows` now,
    # and this function only turns its answer into the sentences billing and
    # the two configuration screens have always shown.
    answer = charge_prices.price_on_date(
        charge, size_class=size_class, customer_class=customer_class, on_date=on_date
    )
    if answer.refusal == charge_prices.FLAT_AND_SIZES:
        return {
            "amount": None,
            "code": charge.code,
            "refusal": (
                f"{charge.code} states an amount and sizes."
                " Clear one on the charge code."
            ),
        }
    if answer.per_size:
        if answer.refusal is not None:
            # A size the code does not price (or does not serve — a NULL row):
            # PO 2026-08-28, refused and never substituted. Tagged
            # `size_not_priced` so billing can bill a CAPACITY service's size
            # at `$0.00` with a warning (PO 2026-10-01). An asset with NO size
            # keeps its named stop and carries no tag.
            result: dict[str, Any] = {
                "amount": None,
                "code": charge.code,
                "per_size": True,
                "refusal": (
                    "This connection's size is not recorded."
                    " Record the connection's size."
                    if size_class is None
                    else f"{charge.code} has no price for {size_class}."
                    " Price it on the charge code."
                ),
            }
            if size_class is not None:
                result["refusal_reason"] = "size_not_priced"
                result["size_class"] = size_class
            return result
        return {
            "amount": answer.amount,
            "code": charge.code,
            "refusal": None,
            "per_size": True,
        }
    if answer.refusal is not None:
        # `DEF-2340`: priced per case, or never priced — neither is an amount,
        # and `$0.00` is a silent wrong answer for both. `not_set` is the PO's
        # 2026-09-30 ruling: billing bills `$0.00` with a named warning.
        return {
            "amount": None,
            "code": charge.code,
            "refusal": (
                f"{charge.code} states no base amount."
                " Price it on the charge code."
            ),
            "not_set": True,
        }
    return {"amount": answer.amount, "code": charge.code, "refusal": None}


def charge_price_boundaries(
    service_codes: Sequence[str], *, period_start: date, period_end: date
) -> tuple[date, ...]:
    """🔒 HUMAN-REVIEW-PENDING — `CR-156-BRC10`. **The days inside a bill
    period on which a BASE charge code's price changes**, for these services.

    PO 2026-10-01, option A, ruled (4): *"billing picks the row in force on the
    bill period's dates, and a period crossing a change is split by days"*.
    Billing cuts the period at each day returned here exactly as it cuts at a
    tariff version (`BR-RAT-114`, `midperiod.split_boundaries`) and at a
    back-bill reprice (`backbill.groups_split_by_days`), and each part is then
    priced on its own first day — which reads the price row in force then.

    A day is in (period_start, period_end] and is a row's `effective_from` or
    the day after its `effective_to`. Every base code of the service counts,
    retired ones included: a code retired mid-period still priced the days
    before. An empty answer — every bill until a price is ever edited — cuts
    nothing, so every bill walks exactly the path it walked before.
    """
    codes = set(service_codes or ())
    if not codes:
        return ()
    charges = list(
        models.Charge.objects.filter(
            tenant_id=_tenant_id(), is_base=True, service__code__in=codes
        ).values_list("id", flat=True)
    )
    return tuple(sorted(charge_prices.boundaries(charges, period_start, period_end)))


class AmbiguousAuthorityTax(RuntimeError):
    """Two of ONE authority's taxes of ONE computation form are in force on one
    service date.

    `DEF-RAT-8051`. Raised instead of picking one, for the reason
    `in_force_version` gives about its own object a few thousand lines up:
    *"That is not a tie-break, it is a coin toss on a money path."*
    `resolution_catalogue.AmbiguousDiscountVersion` is the same shape on the
    third object this rule governs, and this is deliberately its twin rather
    than a third invention.

    ⚠ **IT IS NOT A `ResolutionError`, AND THAT IS A DECISION RATHER THAN AN
    OVERSIGHT.** R7 publishes no refusal class by design — a tax whose
    condition excludes this bill produces NO LINE and never an error
    (`DEF-273`) — and `tests/test_cr052_task20_shadow_measure.py` asserts
    exactly that in one line: *"R7 not in resolution.refusal_steps().values()"*.
    Widening the chain's refusal signature to carry a configuration refusal
    would move a designed invariant in a defect fix. What IS reused is the
    clerk mechanism `DEF-RAT-7991` built: `resolution.clerk_refusal()` reads
    `message_key`, `clerk_detail` and `message_params` off ANY exception with
    `getattr`, so these three fields make this refusal clerk-facing without the
    hierarchy moving at all.

    ⚠ **NOTHING IN BILLING CATCHES IT YET, AND THAT IS FILED RATHER THAN
    IMPLIED — `DEF-RAT-8060`.** `gather._taxes_for` calls this selector through
    the seam and the run loop catches `PricingRefused`, `GatherProblem` and
    `BillingRuleError`; this is none of the three, so a tenant holding two
    overlapping in-force taxes would fail the RUN rather than the ACCOUNT.
    Measured on this branch before the fix landed: **0 such pairs exist on any
    tenant**, which is why the fix ships ahead of the containment rather than
    waiting on it.
    """

    def __init__(
        self,
        message: str,
        *,
        message_key: str | None = None,
        clerk_detail: str | None = None,
        message_params: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message_key = message_key
        self.clerk_detail = clerk_detail
        self.message_params: dict[str, object] = dict(message_params or {})


@batch_reads.memoised
def _authority_tax(
    jurisdiction_id: Any, kind: str, service_date: date | None = None
) -> models.Tax | None:
    """THIS authority's tax row of THIS computation form, or None.

    Lifted out of `plan_tax_rules` because the percent lookup and the flat one
    were the same six lines twice, and DEF-384 needed the same change made to
    both. Two copies of a money lookup is two chances for one of them to keep
    an old rule.

    ── WHAT THE FILTER DOES AND DOES NOT SAY ─────────────────────────────────
    **Deleted rows are still included**, exactly as before: whether a
    DEACTIVATED tax should price a bill is a pre-existing question this module
    has explicitly declined to answer, and it stays declined.

    **Superseded rows are preferred against** (DEF-384). A correction mints a
    NEW row for the same statutory window and marks the old one
    `superseded_by`; without this the oldest row still won on `created_at` and
    a correction would have been recorded, audited, shown on screen — and never
    charged. The fallback to the unfiltered pick keeps BR-BIL-069's promise that
    the identity and the rate name the same row even in the pathological case
    where every row of an authority is superseded; such a row fails
    `tax_in_force`, so it names the authority without producing a line.

    On every row that exists today `superseded_by` is NULL, so the first branch
    answers and the result is byte-identical to the query this replaced.

    ── ⚠ **`service_date` — THE WINDOW IS CONSULTED BEFORE THE PICK, NOT AFTER
    IT (`DEF-RAT-8051`, 2026-09-29)** ───────────────────────────────────────
    **This function used to take no date at all.** It picked the OLDEST
    non-superseded row by `created_at` and handed it to the caller, which then
    asked `tax_in_force(tax, service_date)` a few lines later — so a rate
    change filed the way the model's own comment instructs (*"r6.5; new row per
    change"*) produced **no tax line at all**: not the old rate and not the new
    one.

    **THE WORKED CASE THE PRODUCT OWNER ACCEPTED.** A state utility tax goes
    6.25% -> 7.00% on 2027-01-01. Row A is written in Jan 2024 at 6.25% and
    ends 2026-12-31; row B is written in Dec 2026 at 7.00% and starts
    2027-01-01. Billing a January 2027 period, A won the pick on `created_at`,
    then failed `tax_in_force`, and **the ~$196.00 bill carried $0.00 of tax
    instead of $13.72** — on a bill that looks completely normal. With the date
    in the choice it resolves B and charges $13.72.

    **THE NEW BRANCH IS FIRST AND EVERYTHING BELOW IT IS UNCHANGED.** Where a
    row's window contains the service date it wins; where NONE does, the old
    chain answers exactly as it did, which is what keeps `BR-BIL-069`'s promise
    that the identity and the rate name the same row — that row then fails
    `tax_in_force` in the caller and produces no line while still naming the
    authority.

    **`tax_in_force` IS THE PREDICATE, AND THAT IS ON PURPOSE:** one definition
    of *in force* for the pick and for the gate, or the two drift and this
    defect comes back wearing the opposite sign. It excludes drafts and
    superseded rows and **says nothing about `deleted_at`** — so the declined
    question above stays declined, exactly as declined as it was.

    **A DATELESS CALL IS THE OLD FUNCTION, BYTE FOR BYTE.** `service_date=None`
    skips the whole branch, which is what `services._detach_tax`'s two identity
    lookups want: they ask *which taxes does this authority bring at all*, a
    question with no date in it, and they must not start refusing.

    ⚠ **TWO ROWS IN FORCE ON ONE DATE REFUSE** — `AmbiguousAuthorityTax` above,
    naming both. Picking would be a coin toss on a money path, and `taxes` has
    no uniqueness or exclusion constraint on (tenant, jurisdiction, kind) at
    all, so nothing upstream prevents the shape.

    **MEASURED BEFORE IT SHIPPED: this changes no figure on any existing row.**
    Every tax row in this product is UNDATED (`effective_from` and
    `effective_to` both NULL), so every row is always in force, the window gate
    never bites and the old pick and the new one return the same row — the same
    identity `DEF-483` recorded for the sibling half of this function.
    """
    found = _authority_taxes(jurisdiction_id, kind, service_date)
    return found[0] if found else None


def _chain_in_force(rows: list[models.Tax], service_date: date) -> models.Tax | None:
    """🔒 THE ONE ROW OF ONE TAX CHAIN IN FORCE ON THIS DATE — or None.

    CR-165-BRC10 round 2 (`DEF-RAT-9280`, `DEF-RAT-9282`). Every version of a
    tax shares `chain_id` (`models.Tax.chain_id`), and on any date exactly one
    of them prices: the old rate up to the day before a new one, the new one
    from its start, a correction instead of what it corrected. `tax_in_force`
    is the predicate — drafts, superseded and deactivated rows never price.

    **TWO ROWS OF ONE CHAIN IN FORCE ON ONE DATE STILL REFUSE**
    (`AmbiguousAuthorityTax`), never pick: that is a broken chain, and on
    PostgreSQL `ex_taxes_chain_no_overlap` (`rating/0058`) refuses to store
    it in the first place, so the refusal is the SQLite-and-legacy backstop.
    """
    live = [row for row in rows if tax_in_force(row, service_date)]
    if len(live) > 1:
        authority = getattr(getattr(live[0], "jurisdiction", None), "name", None)
        params: dict[str, object] = {
            "taxes": len(live),
            "authority": authority or "This authority",
            "date": resolution.clerk_date(service_date),
        }
        raise AmbiguousAuthorityTax(
            # THE ENGINEER'S SENTENCE — it names the ids, and it goes to a log
            # and an audit row. B14 rule 31 keeps it off a screen.
            f"R7: {len(live)} versions of tax chain '{live[0].chain_id}' are in "
            f"force on {service_date} ({', '.join(str(row.id) for row in live)}). "
            "Exactly one version of a tax prices a bill; this read never picks.",
            message_key="rating.refusal.taxesAmbiguous",
            clerk_detail=resolution.clerk_sentence("rating.refusal.taxesAmbiguous", **params),
            message_params=params,
        )
    return live[0] if live else None


@batch_reads.memoised
def _authority_taxes(
    jurisdiction_id: Any, kind: str, service_date: date | None = None
) -> tuple[models.Tax, ...]:
    """🔒 THIS AUTHORITY'S TAXES OF THIS FORM — **ONE ROW PER TAX** for the date.

    ⚠ **REPLACES THE ONE-ROW-PER-(AUTHORITY, FORM) PICK OF `DEF-RAT-8051`**
    (CR-165-BRC10 round 2, `DEF-RAT-9280`). That pick returned at most one row
    and refused when two were in force, which was right for two VERSIONS of one
    tax and wrong for two DIFFERENT taxes: a State sales tax at 6.25% and a
    State utility tax at 2%, both percent, refused the bill instead of charging
    **$3.75 + $1.20** on $60.00. Rows had no link saying which were versions of
    which, so the lookup could not tell the two shapes apart. `chain_id` is that
    link, and the answer is now one row per chain.

    **WHAT A CALLER GETS:**
      * with a `service_date` — every chain of this authority and form that has
        a row in force on that date, that ONE row each (`_chain_in_force`),
        ordered by name then chain so two runs list them the same way. A chain
        with two rows in force refuses (`AmbiguousAuthorityTax`).
      * when NO chain has a row in force on the date — the old fallback row,
        alone, exactly as before: it keeps `BR-BIL-069`'s promise that the
        identity and the rate name the same row, and the caller's
        `tax_in_force` gate then produces no line.
      * with no date — the old dateless pick, byte for byte
        (`services.detach_tax_from_plan` asks *which taxes does this authority
        bring at all*, a question with no date in it).

    **Worked, the web walk's phase 5 (`05-prototype/taxes-fees-2026-10-03/
    web-walk.md`):** a State sales tax v1 6.25% ending 10/31/2026 and its v2
    6.5% from 11/01/2026 return ONE row on 10/31 (v1, $3.75 on $60.00) and ONE
    on 11/01 (v2, **$3.90**), never both and never none; a 150% row corrected
    to 3% returns only the 3% row on every date of its window.

    **No existing figure moves.** Every tax row on every tenant was UNDATED and
    its own chain when this landed (`rating/0057`), so each chain has exactly
    one row and it is in force on every date — the same row the old pick chose.
    """
    rows = models.Tax.objects.filter(
        tenant_id=_tenant_id(), jurisdiction_id=jurisdiction_id, kind=kind
    )
    if service_date is not None:
        by_chain: dict[Any, list[models.Tax]] = {}
        for row in rows.select_related("jurisdiction").order_by("created_at", "id"):
            by_chain.setdefault(row.chain_id or row.id, []).append(row)
        chosen = [
            found
            for chain_rows in by_chain.values()
            if (found := _chain_in_force(chain_rows, service_date)) is not None
        ]
        if chosen:
            return tuple(sorted(chosen, key=lambda row: (row.name or "", str(row.chain_id))))
    fallback = (
        rows.filter(superseded_by__isnull=True).order_by("created_at").first()
        or rows.order_by("created_at").first()
    )
    return (fallback,) if fallback is not None else ()


def tax_version_on(tax: models.Tax, service_date: date | None) -> models.Tax | None:
    """🔒 The row of THIS tax's chain that prices on `service_date` — or None.

    What an EXPLICIT PLAN ATTACHMENT resolves through (`DEF-RAT-9282`). An
    attachment names one row; the tax it means is that row's chain. It used to
    follow `superseded_by` only, so a correction reached the plan but a new
    rate from a date did not: the attached row ended on 10/31/2026, nothing
    replaced it, and a November $60.00 bill carried **$0.00** tax instead of
    **$3.90**. Now the chain's row in force on the date answers.

    With no date, the old behaviour: follow `superseded_by` to the newest
    correction (bounded), so a dateless caller sees what it always saw.
    """
    if service_date is None:
        hops = 0
        while tax.superseded_by_id is not None and hops < 10:
            successor = models.Tax.objects.filter(
                tenant_id=_tenant_id(), pk=tax.superseded_by_id
            ).first()
            if successor is None:
                break
            tax = successor
            hops += 1
        return tax
    chain = list(
        models.Tax.objects.filter(tenant_id=_tenant_id(), chain_id=tax.chain_id or tax.id)
        .select_related("jurisdiction")
        .order_by("created_at", "id")
    )
    return _chain_in_force(chain, service_date)


@batch_reads.memoised
def _plan_jurisdiction_rules(plan_id: Any) -> tuple[Any, ...]:
    """`plan_tax_rules`' shape 1 — the plan's jurisdiction bindings (tax IS
    NULL), by jurisdiction name. A PLAN fact: memoised for a bulk Check batch,
    so 500 accounts on one plan read it once (B27). Read-only at every use."""
    return tuple(
        models.PlanTaxRule.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=plan_id, tax__isnull=True
        )
        .select_related("jurisdiction")
        .order_by("jurisdiction__name")
    )


@batch_reads.memoised
def _plan_tax_attachments(plan_id: Any) -> tuple[Any, ...]:
    """`plan_tax_rules`' BR-RAT-113 attachments (tax IS NOT NULL), by tax name —
    a PLAN fact, memoised for a bulk Check batch like the bindings above."""
    return tuple(
        models.PlanTaxRule.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=plan_id, tax__isnull=False
        )
        .select_related("tax", "tax__jurisdiction")
        .order_by("tax__name")
    )


def plan_tax_rules(
    plan_id: Any,
    service_date: date | None = None,
    *,
    customer_class: str | None = None,
    premises: dict[str, Any] | None = None,
    services: tuple[str, ...] | None = None,
    #: DEF-383 — WHOSE bill this is, so a certificate can be found. Optional and
    #: defaulting to None because a caller who cannot name the account is
    #: asking a different question ("which taxes does this plan attract at
    #: all?"), and no certificate is claimed on a bill nobody owns. See
    #: `tax_applies_to` for why this one gate opens where the other three close.
    account_id: Any = None,
) -> list[dict[str, Any]]:
    """The percent taxes this plan attracts, resolved per jurisdiction.

    PO ruling 2026-08-11, verbatim: *"Tax rates are for bill not for service,
    it can be conditional but it is for bill."* So the rate hangs off the PLAN
    and its jurisdictions, never off a service line.

    A plan's rule may carry a `rate_override`; where it does not, the
    jurisdiction's own `taxes.rate` applies (r5 #11 / D8). The override is
    checked first for that reason and NOT merged — a tenant who overrode a
    rate meant to override it.

    **`tax_id` IS RESOLVED WHETHER OR NOT THE RATE CAME FROM THE TAX ROW**
    (BR-BIL-069, PO ruling 2026-08-11 closing OQ-116). The rate and the identity
    are two different questions: an override changes WHAT IS CHARGED, never WHO
    IS OWED. The `taxes` row is where `liability_gl_account_id` lives — the
    authority's own 2200-series account — so a rule with an override must still
    name its tax, or the line it produces cannot be stamped at issue and the
    whole bill refuses (BR-BIL-010). Before this ruling the lookup was skipped
    entirely when an override was present, which would have made an overridden
    tax unbillable for a reason no reader would have guessed.

    `tax_id` is None when the jurisdiction has NO percent `taxes` row at all
    and the rate came from an override alone. That is a real configuration gap
    a human fixes on S13 — and it is left as a gap here rather than closed by
    picking a neighbouring tax row.

    ALL FOUR FORMS ARE RETURNED (per-meter since CR-165-BRC10 round 2,
    `DEF-RAT-9278`), ONE ROW PER TAX (`DEF-RAT-9280` — see `_authority_taxes`).
    BR-RAT-036 defines four forms. The seam's `TaxRule` carried a percent rate
    and nothing else until 2026-08-18, so every other form was skipped; the PO's
    ruled Texas table needs the flat one — **PUC Regulatory Fee $0.85 FLAT PER
    BILL, electric only** — so `flat_amount` travels with the rate and the
    engine bills it as itself.

    ⚠ **THIS PARAGRAPH SAID "PER-UNIT IS STILL SKIPPED" AND WAS FALSE FOR A DAY
    (DEF-2828, 2026-08-31).** It read: *"PER-UNIT still does not: r10's Water
    Conservation Surcharge is `$0.25 / kgal · Tier 3+ usage only` and pricing it
    needs the usage the engine holds and a threshold the tax row would have to
    state; the row IS seeded, carrying its whole condition, and it prices
    nothing until that is built."* **CR-052 W5 task 16 built it** — the row's
    `per_unit_amount`, `per_unit_uom` and BR-RAT-042's marginal
    `applies_above_units` all travel now, through the SAME four gates as the
    other two forms, and `compute_tax` prices them. A sentence describing an
    ABSENCE outlives the absence exactly as easily as one describing a
    guarantee (hard-won law 1, second form) — that is the whole of DEF-2828 and
    it is the fourth occurrence of the shape in this one docstring's file.

    ⚠ **THIS PARAGRAPH READ *"PER-METER is still not priced anywhere … Skipped
    and named, never approximated."* AND IT IS PRICED (`DEF-RAT-9278`,
    2026-10-03).** `per_meter_amount` travels on the row and the engine charges
    it once per meter in the tax's scope — the web walk's $1.25 storm fee on a
    one-meter bill is **$1.25**, not $0.00. The sentence describing the absence
    was the only record of it; it is the fifth occurrence of that shape here.

    ── THE THREE APPLICABILITY QUESTIONS (DEF-273, PO ruling 2026-08-18) ──────
    A rate is not a rule. r10's own table says **who** each rate applies to and
    `taxes` could not express two of the three, so this resolver could only ever
    answer the unconditional case. All three are answered here — at RESOLUTION,
    not in the engine — because the required outcome is **no tax line at all**
    rather than a zero-valued one, and a stage that computes lines cannot decline
    to have one. This is the same posture the account-level exemption takes.

      * **services** — `applies_to_services`. A tax scoped to electric does not
        appear on a water-only bill.
      * **customer class** — `applies_to_customer_classes`, the platform
        `account_types.code`. r10: *"Comm, Industrial only … Residential
        exempt"*, and *"Customer class · All · No residential exemption at
        county level"* for Bexar.
      * **premises geography** — `premises_scope_field` / `premises_scope_value`.
        r10: *"Inside city limits"*, and on the detail drawer *"Premise flag
        selects it at billing time."*

    **EVERY ONE OF THEM FAILS CLOSED** (hard-won law 3, and CLAUDE.md hard rule 2
    read the way a customer would read it). A restriction the caller gave no
    context to evaluate — no class, no premises, no service list — means the
    restricted tax DOES NOT APPLY. Under-charging is recoverable in the next
    cycle; over-charging a real customer is a refund, a support cycle and a
    trust problem. A tax stating NO restriction is unaffected by any of this and
    resolves exactly as it did before, which is why every existing figure holds.

    ── ⚠ `service_date` IS READ NOW, AND THIS PARAGRAPH USED TO SAY IT WAS NOT
    It read: *"`service_date` is accepted and currently unused: `taxes` carries
    no effective-dating columns, so there is nothing to filter on."* That was
    true the day it was written and **had been false since r6.5**, which added
    `effective_from` and `effective_to` to `taxes` — columns `tax_row` has
    served all along. Nobody re-read the sentence, DEF-387 was then filed
    quoting it (*"the engine uses them correctly"*), and the result was
    **DEF-483**: a rate dated to begin next January was charged on today's bill,
    and one whose `effective_to` had passed kept charging for ever.

    A sentence describing an ABSENCE outlives the absence exactly as easily as
    one describing a guarantee — hard-won law 1, in its second form, for the
    third time in this repo in a week.

    The window is now a FOURTH applicability gate beside the three below
    (`tax_in_force`), and it is a gate rather than a queryset filter for the
    reason BR-BIL-069 gives: the identity and the rate must name the same row,
    so the tax is still resolved unconditionally and it is the RULE that is
    withheld. The outcome of a tax outside its window is **no line at all**,
    never a zero-valued one. Every existing row is UNDATED, so every existing
    figure is unchanged.
    """
    if not _valid_uuid(plan_id):
        return []
    # Shape 1 — the jurisdiction bindings (tax IS NULL). The BR-RAT-113
    # attachments are resolved in their own pass below, through the SAME four
    # gates, so an attached tax reaches the bill exactly the way a
    # jurisdiction-brought one does — the SET grows, the mechanism does not.
    rules = _plan_jurisdiction_rules(plan_id)
    resolved: list[dict[str, Any]] = []
    facts = {
        "customer_class": customer_class,
        "premises": premises,
        "services": services,
        "account_id": account_id,
        "on": service_date,
    }
    for rule in rules:
        # ── 🔒 CR-165-BRC10 round 2 — ONE ROW PER TAX, EVERY FORM ────────────
        # `_authority_taxes` answers ONE row per tax CHAIN in force on the date
        # (`DEF-RAT-9280`): two different percent taxes of one authority both
        # price, two versions of one tax never do. The identity and the rate
        # still name the same row (BR-BIL-069), and the DEF-483 window gate and
        # DEF-273's applicability still run on each row, so a tax that does not
        # apply produces NO LINE, never a zero-valued one. Deleted rows are no
        # longer in force (`DEF-RAT-9279`), so a deactivated tax stops pricing.
        percent_rows = _authority_taxes(rule.jurisdiction_id, "percent", service_date)
        several = len(percent_rows) > 1
        if rule.rate_override is not None and several:
            # BR-RAT-094 closed the override's write path; a stored one is
            # still honoured where it can only mean one tax. With two percent
            # taxes it cannot say which, and picking would be a coin toss on a
            # money path — refused by name, the DEF-RAT-8051 sentence.
            params: dict[str, object] = {
                "taxes": len(percent_rows),
                "authority": getattr(rule.jurisdiction, "name", None) or "This authority",
                "date": resolution.clerk_date(service_date) if service_date else "",
            }
            raise AmbiguousAuthorityTax(
                f"R7: plan '{plan_id}' overrides the percent rate of jurisdiction "
                f"'{rule.jurisdiction_id}', which levies {len(percent_rows)} percent "
                "taxes on this date; an override cannot say which one it means.",
                message_key="rating.refusal.taxesAmbiguous",
                clerk_detail=resolution.clerk_sentence("rating.refusal.taxesAmbiguous", **params),
                message_params=params,
            )
        for tax in percent_rows or (None,):
            rate = rule.rate_override
            if rate is None:
                rate = tax.rate if tax is not None else None
            if rate is None:
                # An authority with NO percent rate anywhere is skipped rather
                # than defaulted to zero: zero is a claim.
                continue
            if tax is not None and not (
                tax_in_force(tax, service_date) and tax_applies_to(tax, **facts)
            ):
                continue
            resolved.append(
                {
                    # ONE percent tax keeps the authority's name on the line,
                    # exactly as every bill has read; with SEVERAL, each line
                    # names its own tax, or two lines would read alike.
                    "code": tax.name if (several and tax is not None) else rule.jurisdiction.name,
                    # DEF-RAT-9307 (PO 2026-10-03, "Okay" to "yes, print the
                    # bill label"): what the CUSTOMER reads, when the clerk
                    # typed one. Display only — `code` above still names the
                    # rule in every refusal, and nothing prices off either.
                    "bill_label": tax.bill_label if tax is not None else None,
                    "rate": rate,
                    "flat_amount": None,
                    "jurisdiction_id": str(rule.jurisdiction_id),
                    # BR-BIL-069 — WHOSE money this is.
                    "tax_id": str(tax.id) if tax is not None else None,
                    # DEF-465 — what the percent is a percent OF. Empty = every
                    # service, which keeps every frozen fixture unchanged.
                    "applies_to_services": (
                        list(tax.applies_to_services or []) if tax is not None else []
                    ),
                    "per_unit_amount": None,
                    "per_unit_uom": None,
                    "applies_above_units": None,
                    "per_meter_amount": None,
                }
            )

        # The FLAT-PER-BILL form (BR-RAT-036; the PO's ruled PUC fee) — its own
        # lookup, because `rate_override` is a PERCENT override and must never
        # rewrite a dollar amount (r5 #11 / D8).
        for flat in _authority_taxes(rule.jurisdiction_id, "flat_per_bill", service_date):
            if (
                flat.flat_amount is not None
                and tax_in_force(flat, service_date)
                and tax_applies_to(flat, **facts)
            ):
                resolved.append(_attached_row(flat, str(rule.jurisdiction_id)))

        # The PER-UNIT form (BR-RAT-036 + BR-RAT-042 marginal, CR-052 W5 task
        # 16). Hard rule 3: a per-unit amount with no unit is skipped, never
        # published for the engine to refuse the whole bill over.
        for per_unit in _authority_taxes(rule.jurisdiction_id, "per_unit", service_date):
            if (
                per_unit.per_unit_amount is not None
                and per_unit.per_unit_uom
                and tax_in_force(per_unit, service_date)
                and tax_applies_to(per_unit, **facts)
            ):
                resolved.append(_attached_row(per_unit, str(rule.jurisdiction_id)))

        # ⚠ THE PER-METER FORM — PRICED AT LAST (`DEF-RAT-9278`, CR-165-BRC10
        # round 2). BR-RAT-036 as amended (DEF-386, PO 2026-08-21 option C:
        # *"Per-meter now"*) stored `per_meter_amount` and this function skipped
        # it by kind for six weeks, so the web walk's *$1.25 per meter* storm
        # fee billed **$0.00**. The amount travels like the other three forms;
        # the engine multiplies it by the meters in scope
        # (`compute_tax._meters_in_scope`).
        for per_meter in _authority_taxes(rule.jurisdiction_id, "per_meter", service_date):
            if (
                per_meter.per_meter_amount is not None
                and tax_in_force(per_meter, service_date)
                and tax_applies_to(per_meter, **facts)
            ):
                resolved.append(_attached_row(per_meter, str(rule.jurisdiction_id)))

    # ── Shape 2 · the BR-RAT-113 EXPLICIT ATTACHMENTS (PO 2026-08-21) ────────
    # *"staff need to pick up and attach taxes and fees on the plan"* — one
    # CHOSEN tax, priced through the same gates as a jurisdiction-brought one.
    #
    # DE-DUPLICATION RUNS ONE WAY: a tax that reached `resolved` through its
    # jurisdiction binding is not emitted again for its attachment (bind Texas
    # 6.25% AND attach it: $221.90 is taxed once, $13.87, GT-17's own figure).
    #
    # ⚠ AN ATTACHMENT FOLLOWS ITS TAX'S CHAIN, NOT ONE ROW (`DEF-RAT-9282`).
    # It used to follow `superseded_by` only, so a correction reached the plan
    # and a NEW RATE FROM A DATE did not: the attached row ended on 10/31/2026
    # and a November $60.00 bill carried $0.00 instead of $3.90.
    # `tax_version_on` answers the chain's row in force on the service date.
    emitted: set[str] = {str(row["tax_id"]) for row in resolved if row.get("tax_id")}
    for attachment in _plan_tax_attachments(plan_id):
        tax = tax_version_on(attachment.tax, service_date)
        if tax is None or str(tax.id) in emitted:
            continue
        if tax.kind not in ("percent", "flat_per_bill", "per_unit", "per_meter"):
            continue
        if not tax_in_force(tax, service_date) or not tax_applies_to(tax, **facts):
            continue
        if tax.kind == "percent" and tax.rate is None:
            continue  # an absent rate is skipped, never defaulted — zero is a claim
        if tax.kind == "flat_per_bill" and tax.flat_amount is None:
            continue
        if tax.kind == "per_unit" and (tax.per_unit_amount is None or not tax.per_unit_uom):
            continue  # hard rule 3
        if tax.kind == "per_meter" and tax.per_meter_amount is None:
            continue
        emitted.add(str(tax.id))
        resolved.append(
            _attached_row(
                tax, str(tax.jurisdiction_id) if tax.jurisdiction_id is not None else None
            )
        )
    return resolved


def _attached_row(tax: models.Tax, jurisdiction_id: str | None) -> dict[str, Any]:
    """One resolved rule for ONE tax row, named by the TAX — the shape every
    non-percent binding row and every attachment takes.

    Exactly one of `rate`, `flat_amount`, `per_unit_amount` and
    `per_meter_amount` is set, by `kind` (BR-RAT-036 gives a tax one form);
    the others travel as None so one row shape reaches the seam whatever the
    form, and a reader cannot conclude a field was forgotten.
    """
    kind = tax.kind
    return {
        "code": tax.name,
        # DEF-RAT-9307 — the clerk's Bill label, served as stored (NULL = none).
        "bill_label": tax.bill_label,
        "rate": tax.rate if kind == "percent" else None,
        "flat_amount": tax.flat_amount if kind == "flat_per_bill" else None,
        "jurisdiction_id": jurisdiction_id,
        "tax_id": str(tax.id),
        "applies_to_services": list(tax.applies_to_services or []),
        "per_unit_amount": tax.per_unit_amount if kind == "per_unit" else None,
        "per_unit_uom": tax.per_unit_uom if kind == "per_unit" else None,
        "applies_above_units": tax.applies_above_units if kind == "per_unit" else None,
        "per_meter_amount": tax.per_meter_amount if kind == "per_meter" else None,
    }

def tax_applies_to(
    tax: models.Tax,
    *,
    customer_class: str | None = None,
    premises: dict[str, Any] | None = None,
    services: tuple[str, ...] | None = None,
    account_id: Any = None,
    on: date | None = None,
) -> bool:
    """Does THIS tax row reach a bill with these facts? (DEF-273, 2026-08-18.)

    Published as a named function rather than kept inline because two things
    need the same answer and they must not drift: the bill run (through
    `plan_tax_rules`) and any screen that wants to say *"this rate reaches 1,124
    of your accounts"*, which is a number r10 already draws.

    Read this as three independent gates, ALL of which must open. Each one is
    "the tax states no restriction, OR the fact satisfies it" — and a stated
    restriction the caller cannot evaluate CLOSES the gate. See the caller's
    docstring for why closed is the safe direction.

    ── AND A FOURTH GATE, WHICH RUNS THE OTHER WAY (DEF-383, 2026-08-21) ─────
    `account_id` opens part 4's exemption object: a LIVE certificate against one
    of THIS tax's exemption categories removes this tax from that account's bill
    and leaves every other authority's tax alone.

    ⚠ **AN ABSENT `account_id` MEANS THE TAX APPLIES, WHICH IS THE OPPOSITE
    DIRECTION TO THE THREE GATES ABOVE, AND THAT IS DELIBERATE.** The three are
    RESTRICTIONS STATED ON THE TAX, so a restriction we cannot evaluate must
    close (DEF-273's fail-safe). An exemption is a CLAIM MADE BY A CUSTOMER, and
    a claim nobody has made is not an exemption — reading "I could not check"
    as "exempt" would zero the tax on every bill for every account the moment a
    caller forgot the argument. Both readings protect the same customer; only
    one of them is recoverable.

    ⚠ **THIS IS NOT `accounts.tax_exempt`, AND THE TWO MUST NOT BE MERGED.**
    That flag (read by `apps/billing/gather._tax_exempt_on`) is BLANKET — one
    boolean, one expiry, every authority at once. Part 4's object is PER TAX and
    PER CATEGORY: a church holding a religious exemption against the 6.25 %
    state tax still pays the city's 1.50 % franchise fee, because a city is not
    a state and its statute is its own. Collapsing them would silently widen
    every exemption a utility records to every authority it remits to.
    """
    wanted_services = [str(code) for code in (tax.applies_to_services or [])]
    if wanted_services:
        if services is None:
            return False  # the caller could not say what is on the bill
        if not set(wanted_services) & {str(code) for code in services}:
            return False

    wanted_classes = [str(code).strip().lower() for code in (tax.applies_to_customer_classes or [])]
    if wanted_classes:
        if not customer_class:
            return False  # r10's "residential exempt" cannot be honoured blind
        if str(customer_class).strip().lower() not in wanted_classes:
            return False

    if account_id is not None and account_holds_exemption(tax, account_id, on):
        return False

    return premises_in_scope(tax, premises)


#: The two statutory answers, and there are exactly two (CR-013 part 4 step 2:
#: *"before or after discounts"*). Mirrored by the DB CHECK
#: `ck_taxes_discount_treatment` and by `services.DISCOUNT_TREATMENTS`.
DISCOUNT_TREATMENT_BEFORE = "before"
DISCOUNT_TREATMENT_AFTER = "after"
DISCOUNT_TREATMENTS: tuple[str, ...] = (DISCOUNT_TREATMENT_BEFORE, DISCOUNT_TREATMENT_AFTER)


def taxable_subtotal_for(
    treatment: str | None, subtotal_before: Decimal, subtotal_after: Decimal
) -> Decimal:
    """WHICH subtotal does THIS authority levy on? (DEF-382.)

    CR-013 part 4 step 2, verbatim: *"discount treatment — before or after
    discounts, stated per tax because it's statutory"*. Until this existed the
    product had ONE answer and applied it to every authority — correct for
    Bexar County, an assumption everywhere else, and recorded only in two
    docstrings that named `taxes.discount_treatment` as an unbuilt column
    (hard-won law 1: a comment is a note, never a plan).

    ── THE TWO NAMES ARE ABOUT THE DISCOUNT'S POSITION, NOT THE TAX'S ────────
    `before` = the discount lands BEFORE the tax, so the authority levies on the
    REDUCED subtotal (`subtotal_after`). `after` = the discount lands after, so
    the authority never sees it and levies on the FULL tariff amount
    (`subtotal_before`). The mapping reads inverted at a glance and it is not:
    the word names where the DISCOUNT goes, which is how a statute is written
    and how the PO said it.

    **Worked, and this is the pair DEF-382 protects:** a `$1.00` PAPERLESS
    credit on a Bexar County bill leaves the county line at **`$3.78`** under
    `before` and at **`$3.80`** under `after`. Two cents, per bill, per
    authority, in the direction a regulator audits.

    A NULL or unknown treatment answers `before` — the behaviour every bill this
    product has ever issued had, so nothing moves for a row nobody has restated.

    ⚠ **NO ROUNDING HAPPENS HERE.** This picks a base; B4 ❄️ decides what the
    tax line rounds to, and it decides it in one place (`core.money.finalize`).
    A selector that quantized would be a second money rule.
    """
    if str(treatment or DISCOUNT_TREATMENT_BEFORE) == DISCOUNT_TREATMENT_AFTER:
        return subtotal_before
    return subtotal_after


#: The batch store `prime_check_batch` keeps each account's certificates in.
_EXEMPTIONS = "rating.exemption_certificates"


def prime_check_batch(
    unit_ids: Any, account_ids: Any, *, period_start: date, period_end: date
) -> dict[str, int]:
    """B27 — ONE BULK CHECK BATCH'S PER-ACCOUNT RATING FACTS, IN THREE QUERIES.

    Primes the batch memo (`core.batch_reads`) with, for every unit and
    account of the batch: its dated plan history over the pass's period
    (`unit_plan_assignments_in`), its exemption certificates (read by
    `account_holds_exemption` through the SAME four predicates), and — for an
    account with NO discount enrolment at all — the empty answer of
    `discount_services.discount_rules_for_account` (an account that has one is
    asked on its own, as before). Each list is ordered by the per-account
    read's own `ORDER BY` in the database and split by unit. Nothing is
    primed outside a batch."""
    from apps.rating import discount_services

    if batch_reads.active() is None:
        return {}
    units = sorted({str(u) for u in (unit_ids or ()) if _valid_uuid(u)})
    accounts = sorted({str(a) for a in (account_ids or ()) if _valid_uuid(a)})
    tenant_id = _tenant_id()
    history: dict[str, list[dict[str, Any]]] = {unit: [] for unit in units}
    if units:
        for row in (
            models.UnitPlanAssignment.objects.filter(
                tenant_id=tenant_id, unit_id__in=units, assigned_from__lte=period_end
            )
            .filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=period_start))
            .order_by("unit_id", "assigned_from", "created_at")
        ):
            history.setdefault(str(row.unit_id), []).append(_plan_assignment_row(row))
    for unit in units:
        batch_reads.prime(
            unit_plan_assignments_in,
            history.get(unit, []),
            unit,
            period_start=period_start,
            period_end=period_end,
        )
    if accounts:
        certificates: dict[str, list[tuple[Any, Any, Any, Any]]] = {a: [] for a in accounts}
        for account_id, tax_id, deleted_at, revoked_at, expires_on in (
            models.TaxExemptionCertificate.objects.filter(
                tenant_id=tenant_id, account_id__in=accounts
            ).values_list(
                "account_id", "category__tax_id", "category__deleted_at", "revoked_at", "expires_on"
            )
        ):
            certificates.setdefault(str(account_id), []).append(
                (tax_id, deleted_at, revoked_at, expires_on)
            )
        for account_id, rows in certificates.items():
            batch_reads.put(_EXEMPTIONS, account_id, tuple(rows))
        enrolled = {
            str(one)
            for one in discount_models.DiscountEnrolment.objects.filter(
                tenant_id=tenant_id, account_id__in=accounts
            ).values_list("account_id", flat=True)
        }
        for account_id in accounts:
            if account_id not in enrolled:
                batch_reads.put(discount_services.NO_ENROLMENT, account_id, True)
    return {"units": len(units), "accounts": len(accounts)}


def account_holds_exemption(tax: models.Tax, account_id: Any, on: date | None = None) -> bool:
    """Does this account hold a LIVE certificate against one of this tax's
    exemption categories, on this date? (DEF-383.)

    ⚠ **AN EXPIRED CERTIFICATE JUST STOPS WORKING. NOTHING IS RAISED.**
    CR-013 part 4, shared rules, verbatim: *"Expired exemption certificates
    reinstate the tax on the next run with no exception raised — it's expected
    behaviour."* That is the opposite of this product's usual posture, where a
    bill run stops and names anything that changed underneath it, and it is
    stated here, in the model, in the epic and in a test because it is exactly
    the kind of thing a later reading "fixes" into an exception queue. A utility
    with two staff cannot triage one that refills every January.

    **Worked:** an account holding a religious exemption against a 6.25 % state
    tax on a `$196.37` taxable bill pays `$0.00` while the certificate is live
    and **`$12.27`** on the first run after it expires — no exception, no hold,
    and the reinstatement plainly visible because the tax line is simply back.

    `expires_on` NULL is LIVE, not expired: some exemptions are permanent (a
    municipality does not renew being a municipality), and the model says so at
    the column. A REVOKED certificate is dead whatever its expiry says — an
    authority that disallows a claim does not wait for the paper to run out.

    A category that is soft-deleted no longer exempts anybody: the authority
    withdrew the category, and the certificates under it have nothing left to
    claim against. They are kept rather than deleted so the utility can show an
    auditor why an account stopped being exempt on a particular day.
    """
    on = on or seams.tenant_today()
    loaded = batch_reads.get(_EXEMPTIONS, account_id)
    if loaded is not None:
        # B27 — the batch's one read of its accounts' certificates, judged by
        # the SAME four predicates as the query below.
        return any(
            tax_id == tax.id
            and category_deleted_at is None
            and revoked_at is None
            and (expires_on is None or expires_on >= on)
            for tax_id, category_deleted_at, revoked_at, expires_on in loaded
        )
    live = models.TaxExemptionCertificate.objects.filter(
        tenant_id=_tenant_id(),
        category__tax_id=tax.id,
        category__deleted_at__isnull=True,
        account_id=account_id,
        revoked_at__isnull=True,
    ).filter(Q(expires_on__isnull=True) | Q(expires_on__gte=on))
    return live.exists()


def premises_in_scope(tax: models.Tax, premises: dict[str, Any] | None) -> bool:
    """CR-013 part 4's five scope MECHANISMS, resolved against a premises row.

    PO verbatim (2026-08-18, `TAXES-FEES-BUSINESS-SPEC.md`, TAX-02 step 1):
    *"how the system decides a premise is in scope (city limits, county, state,
    taxing district, explicit premise list)"*, and *"Overlapping jurisdictions
    expected — each attaches independently"*. So this answers ONE tax about ONE
    premises and never arbitrates between two: a premises inside a city and
    inside a county attracts both taxes, which is the ordinary Texas case.

    ── WHAT CAN BE ANSWERED TODAY, AND WHAT CANNOT ───────────────────────────
    `premises` records `city`, `state` and `postal_code` and nothing else
    geographic, and it is metering's table. So:

      * `city_limits` — answered by the premises' own **flag** where one is
        supplied (part 4 downstream: *"premise city-limit flags drive attachment
        and are audit-logged on the premise"*), and by the recorded CITY NAME
        until that flag exists. The flag wins when present: a utility that has
        drawn its boundary is not second-guessed by a spelling.
      * `state` — answered by the recorded state.
      * `county`, `taxing_district`, `premise_list` — **CANNOT be answered.**
        There is no county column, no district table and no premise set. Each
        returns False, so the tax reaches nobody rather than everybody, and each
        is named in the lane's write-back as the story it is. A scope the
        product cannot evaluate must not quietly become "applies to all".
    """
    kind = (tax.premises_scope_kind or "").strip()
    if not kind:
        return True  # no scope stated — the tax applies everywhere in the tenant
    facts = premises or {}
    wanted = (tax.premises_scope_value or "").strip()

    if kind == "city_limits":
        flag = facts.get("inside_city_limits")
        if flag is not None:
            return bool(flag)
        if not wanted:
            # The utility switched the scope on and never named the place. The
            # tax reaches NOBODY until they do — r10's "61 outside-city accounts
            # exempt" is a promise we would otherwise break in the other
            # direction, by charging all of them.
            return False
        return _matches(facts.get("city"), wanted)
    if kind == "state":
        return bool(wanted) and _matches(facts.get("state"), wanted)
    # county · taxing_district · premise_list — no fact exists to answer them.
    return False


#: The scope mechanisms a bill run can actually RESOLVE today, named so the gap
#: is a fact in the code rather than a paragraph in a report (hard-won law 1).
#:
#: ⚠ IT LIVES HERE NOW, BESIDE THE PREDICATE IT DESCRIBES. It was declared in
#: `services.py`, one file away from `premises_in_scope`, which is the function
#: whose behaviour it is a statement ABOUT — so the list and the code it
#: described could drift without either looking wrong. `services` re-exports the
#: name so every existing caller and `test_def_273_tax_conditions` are unchanged.
PREMISES_SCOPE_KINDS_RESOLVABLE: tuple[str, ...] = ("city_limits", "state")

#: How many premises TAX-02 names by address before it stops listing. Three,
#: because the CR asks for *"a sample line"* (singular) and three is the
#: smallest number that reads as a sample rather than as an answer — a wizard
#: that printed 1,247 addresses would have replaced the count it exists to show.
MATCHED_PREMISES_SAMPLE = 3


def matched_premises(
    premises_scope_kind: str | None,
    premises_scope_value: str | None,
    *,
    sample: int = MATCHED_PREMISES_SAMPLE,
    customer_classes: Sequence[str] = (),
    services: Sequence[str] = (),
    _rows: list[dict[str, Any]] | None = None,
    _reach: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """DEF-380 — *"the matched premise count so a wrong boundary is visible
    before rates are entered"*, answered at last.

    Takes the SCOPE rather than a saved tax, because the moment the safeguard
    has to work is step 1 of the wizard, before anything is saved and before any
    rate is entered. The saved-tax variant is one call away
    (`matched_premises(tax.premises_scope_kind, tax.premises_scope_value)`) and
    is what the tax detail's *Where it applies* tab reads.

    ── IT RUNS THE ENGINE'S OWN PREDICATE, NOT A COPY OF IT ──────────────────
    Each premises is evaluated by `premises_in_scope` — the same function
    `plan_tax_rules` calls to decide whether a real bill attracts the tax. A
    count computed any other way would be a second implementation of the rule,
    and a safeguard that can disagree with the thing it is safeguarding is worse
    than no safeguard: it would say "61 premises" on a screen while the bill run
    charged 1,247.

    ── WHAT COMES BACK, AND WHY `resolvable` IS PART OF THE ANSWER ───────────
    `{"count", "total", "sample", "resolvable"}`. Three of the five mechanisms
    — `county`, `taxing_district`, `premise_list` — have no fact to resolve
    against (no county column, no district table, no premise set), so
    `premises_in_scope` returns False for every premises and the honest count is
    **0 of 1,247**. That zero is a TRUE statement about what the product can do
    today and a MISLEADING one about the utility's boundary, so `resolvable:
    False` travels beside it and TAX-02 says which it is. A bare 0 would read as
    "your boundary matches nobody, fix your boundary".

    **Worked, on Silver Creek:** scope `city_limits` = *San Antonio* over 1,247
    premises returns `count: 1,186`, `total: 1,247` — the 61 outside-city
    premises r10 exempts are the difference, and that is the figure the CR's
    safeguard exists to put in front of somebody before they type a rate.
    """
    kind = (premises_scope_kind or "").strip()
    wanted_classes = tuple(str(code).strip() for code in customer_classes if str(code).strip())
    wanted_services = tuple(str(code).strip() for code in services if str(code).strip())
    narrowed = bool(wanted_classes or wanted_services)

    # `_rows` / `_reach`: a caller counting a PAGE of taxes (`tax_reach_counts`)
    # hands in one read of each, so the page costs one premises read, not one
    # per row. Same rows, same predicate — never a second implementation.
    rows = _rows if _rows is not None else seams.premises_geography_rows()
    total = len(rows)

    if not kind and not narrowed:
        # No scope stated AND no other restriction = the tax applies everywhere
        # in the tenant, which is what `premises_in_scope` answers for a blank
        # kind. Said explicitly so the screen can render "every premises" rather
        # than a number that happens to equal the total for a reason nobody can
        # see. ⚠ The two extra reads below are SKIPPED on this path: a count that
        # restricts nothing must not pay for facts it will not read.
        return {
            "count": total,
            "total": total,
            "sample": [_premises_sample_line(row) for row in rows[:sample]],
            "resolvable": True,
            "everywhere": True,
            "narrowed": False,
            # The same keys on both exits, so a reader never has to ask which
            # branch answered. No boundary is stated, so there is no split.
            "matched_by_flag": None,
            "matched_by_name": None,
        }

    probe = models.Tax(
        premises_scope_kind=kind,
        premises_scope_value=premises_scope_value,
        applies_to_customer_classes=list(wanted_classes) or None,
        applies_to_services=list(wanted_services) or None,
    )
    if not narrowed:
        # The boundary alone, exactly as before — `tax_applies_to` on an
        # unrestricted probe reduces to `premises_in_scope`, and taking the
        # shorter road keeps this path byte-for-byte the behaviour every
        # existing figure was measured against.
        matched = [row for row in rows if premises_in_scope(probe, row)]
    else:
        reach = _reach if _reach is not None else seams.premises_reach_facts()
        matched = [row for row in rows if _premises_reaches(probe, row, reach)]

    by_flag, by_name = _city_limits_split(kind, matched)

    return {
        "count": len(matched),
        "total": total,
        # ⚠ **THE SAMPLE DRAWS FROM BOTH GROUPS WHEN THERE ARE TWO**
        # (`DEF-RAT-5806`). Taking the first three in premise-number order is
        # only a sample of the WHOLE when the whole is one kind of thing. Under
        # `city_limits` it is two kinds — premises the utility has FLAGGED, and
        # premises matched on the typed NAME — and on the demo tenant the
        # flagged ones sort last, so scoping to *Katy* listed three Katy
        # addresses beside a count of 77 and named none of the 71 that are the
        # reason it is 77. A clerk reading it concluded the town had 77
        # properties. The sample now alternates between the two groups while
        # both have rows, so it can never describe one of them as if it were
        # the answer.
        "sample": [
            _premises_sample_line(row) for row in _mixed_sample(matched, by_flag, by_name, sample)
        ],
        # ⚠ `resolvable` AND `everywhere` BOTH DESCRIBE THE BOUNDARY AND NOTHING
        # ELSE, and that is deliberate. A clerk who sets the boundary to
        # "Everywhere" and then ticks Commercial has not made the boundary
        # unresolvable — they have narrowed the tax. The screen needs both facts
        # to write the right sentence, so `narrowed` travels beside them rather
        # than being folded into either.
        "resolvable": (not kind) or kind in PREMISES_SCOPE_KINDS_RESOLVABLE,
        "everywhere": not kind,
        "narrowed": narrowed,
        # ⚠ **HOW THE COUNT WAS REACHED, FOR `city_limits` AND NOTHING ELSE
        # (`DEF-RAT-5805` / `DEF-RAT-5806`).** `premises_in_scope` reads the
        # premises' own city-limits FLAG first and falls back to the typed name
        # only where no flag is recorded — signed behaviour (CR-013 part 4:
        # *"premise city-limit flags drive attachment and are audit-logged on
        # the premise"*) and correct. But the SCREEN could not say so: the help
        # under the place box read *"Left blank, this reaches nobody"* while the
        # count four lines below read *"71 of 79 premises match"*, and typing a
        # town of six reached 77. The number was true and unexplainable.
        #
        # These two are FACTS ABOUT ROWS ALREADY MATCHED, never a second
        # implementation of the rule (BR-RAT-107): the predicate above decides
        # membership, and this only asks which of the two ways each member got
        # in. `None` on every other kind, because no other kind has two ways.
        "matched_by_flag": None if by_flag is None else len(by_flag),
        "matched_by_name": None if by_name is None else len(by_name),
    }


def _city_limits_split(
    kind: str, matched: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    """Which matched premises got in by their FLAG, and which by the typed NAME.

    Only `city_limits` has two doors — `premises_in_scope` consults
    `inside_city_limits` first and the recorded city name only where the flag is
    absent — so every other kind answers `(None, None)` and the screen says
    nothing rather than inventing a split that does not exist.

    ⚠ **IT READS A FACT, IT DOES NOT RE-DECIDE ANYTHING.** Every row handed in
    has already been passed by the engine's own predicate. A row carrying a flag
    was admitted BY that flag, because the predicate returns on it before the
    name is looked at; a row with no flag can only have been admitted by the
    name. That is why this is three lines and not a copy of the rule.
    """
    if kind != "city_limits":
        return None, None
    by_flag = [row for row in matched if row.get("inside_city_limits") is not None]
    by_name = [row for row in matched if row.get("inside_city_limits") is None]
    return by_flag, by_name


def _mixed_sample(
    matched: list[dict[str, Any]],
    by_flag: list[dict[str, Any]] | None,
    by_name: list[dict[str, Any]] | None,
    sample: int,
) -> list[dict[str, Any]]:
    """`sample` rows drawn from both groups while both still have rows.

    ⚠ **THERE IS NO SPLIT ON ANY KIND BUT `city_limits`, AND THAT PATH MUST
    RETURN WHAT IT ALWAYS RETURNED.** The first draft of this function returned
    `[]` when the split was `None`, which is not a smaller sample — it is the
    sample line vanishing from every `state`-scoped tax with the count still
    reading correctly beside it. Nothing in the suite compares a sample against
    a previous run, so it would have shipped.
    """
    if by_flag is None or by_name is None:
        return matched[:sample]
    out: list[dict[str, Any]] = []
    left, right = list(by_flag), list(by_name)
    while len(out) < sample and (left or right):
        if left:
            out.append(left.pop(0))
        if len(out) < sample and right:
            out.append(right.pop(0))
    return out


def _premises_reaches(
    probe: models.Tax,
    row: dict[str, Any],
    reach: dict[str, dict[str, tuple[str, ...]]],
) -> bool:
    """Does this tax reach ANY bill at this premises? (`PRB-05`, BR-RAT-107.)

    ⚠ **IT RUNS `tax_applies_to`, THE ENGINE'S OWN PREDICATE, ONCE PER CLASS AT
    THE ADDRESS.** BR-RAT-107 already forbids a second implementation of the
    boundary rule and the reason holds identically for the other two gates: a
    safeguard that can disagree with the thing it safeguards is worse than no
    safeguard. So this function contains no rule of its own — it decides only
    *which facts describe a bill at this address*, and hands each candidate to
    the same function `plan_tax_rules` calls.

    ⚠ **A PREMISES WITH NO ACCOUNT IS TRIED ONCE WITH `customer_class=None`,
    WHICH IS NOT THE SAME AS SKIPPING THE GATE.** An unrestricted tax reaches a
    vacant address (correct — it is a real premises), and a class-restricted one
    does not (DEF-273's fail-safe). Both fall straight out of `tax_applies_to`,
    which is why neither is written here as a branch.

    `account_id` is deliberately NOT passed: an exemption is a claim ONE
    customer has made, and this count answers a question about the tax's reach
    before any rate is entered. Folding exemptions in would make the number
    shrink for a reason that has nothing to do with the boundary a clerk is
    checking.
    """
    facts = reach.get(str(row.get("id")), {})
    services_here = facts.get("services", ())
    classes_here = facts.get("customer_classes", ()) or (None,)
    return any(
        tax_applies_to(probe, customer_class=code, services=services_here, premises=row)
        for code in classes_here
    )


def _premises_sample_line(row: dict[str, Any]) -> dict[str, Any]:
    """One premises, named the way a human would name it on a review step.

    The premise NUMBER and the address only — never the owner, never a
    customer's name. This read exists to prove a BOUNDARY is right, and a
    boundary needs a place, not a person.
    """
    return {
        "id": str(row.get("id")),
        "premise_no": row.get("premise_no"),
        "address_line": row.get("address_line"),
        "city": row.get("city"),
    }


def _matches(actual: Any, wanted: str) -> bool:
    """Case- and whitespace-insensitive, because a clerk types "san antonio".

    A BLANK premises value never matches: an unrecorded geography is the ruled
    fail-safe (DEF-273, PO 2026-08-18), not a wildcard.
    """
    text = str(actual or "").strip()
    return bool(text) and text.casefold() == wanted.casefold()


def liability_gl_account_id_for_tax(tax_id: Any) -> str | None:
    """The 2200-series account THIS tax's authority is owed into, or None.

    ── WHY THIS READ IS RATING'S AND NOT THE LEDGER'S ────────────────────────
    BR-BIL-069 (PO ruling 2026-08-11, closing OQ-116): *"For each atheority have
    separate account and tagging; but also ensure you allow Use to manage it
    since every utility may not have every account."* The mapping lives on
    `taxes.liability_gl_account_id`, a column that already existed, is already
    editable on S13, and is the tenant's own. The PO's declined option B was a
    second, ledger-side table keyed on the authority — a SECOND home for one
    fact, which is how two configuration screens end up disagreeing about which
    account a tax authority is owed into. So the fact stays here and this is
    the read billing asks (`apps/billing/issue._gl_account_for`).

    ── WHAT `None` MEANS, AND WHAT THE CALLER MUST DO WITH IT ────────────────
    Three different situations answer `None`, and every one of them is a
    REFUSAL the caller must honour rather than a value to substitute for:

      * the tax id names no row of this tenant (including another tenant's tax —
        the filter is tenant-scoped, so a crafted id simply is not found);
      * the tenant has not yet minted or mapped that authority's account, which
        is the ordinary state of a fresh tenant and is **OQ-146** — whether the
        product should also refuse this at SETUP time is not settled and is not
        decided here;
      * the line named no tax at all (`tax_id is None`).

    A caller that turned any of them into a stamped account would remit one
    authority's money to another, which is a filing error with a regulator on
    the other end of it. `None` is returned rather than raised for the reason
    `apps/ledger/selectors.py` gives for the same choice: the natural caller
    resolves many lines for one document and wants every gap at once.

    LIVENESS IS NOT CHECKED HERE and that is deliberate: whether a ledger
    account is live is the LEDGER's question about the LEDGER's table (B1), and
    `apps/ledger/selectors.account_is_live` is the one implementation of it.
    The write path (`services._validate_tax`) validates ownership and liveness
    through that seam before storing the pointer, and billing re-checks liveness
    at issue — an account deactivated between the two would otherwise be stamped
    onto an immutable line.
    """
    if not _valid_uuid(tax_id):
        return None
    row = (
        models.Tax.objects.filter(tenant_id=_tenant_id(), pk=tax_id)
        .values_list("liability_gl_account_id", flat=True)
        .first()
    )
    return str(row) if row else None


def tax_authority_label_for_tax(tax_id: Any) -> str | None:
    """WHOSE tax this is, in words a clerk can act on — or None.

    **PO ruling 2026-08-12, OQ-146 CLOSED.** Verbatim: *"let the run report
    it"*. A tax whose authority has no liability account is not blocked at
    SETUP — the run raises it as **a break NAMING THE AUTHORITY** and the other
    accounts in the run continue (BR-BIL-069 (3) · BR-BIL-010 · US-BIL-008
    TC-10).

    That ruling is what this read exists for, and it is a real gap it closes
    rather than ceremony. Billing's refusal used to name the LINE's description
    — `"Tax HARRIS-CO"` — which is a rule CODE, chosen by whoever typed the rate
    in. A clerk reading *"Harris County has no liability account"* knows which
    row of S13 to open; a clerk reading *"Tax HARRIS-CO"* has to go and look the
    code up first, and on a run of 480 bills that is the difference between a
    five-minute fix and a support ticket.

    THREE SOURCES, MOST SPECIFIC FIRST, and the order is the point:

      * `tax_jurisdictions.authority` — *"State of Texas"*, *"Harris County"* —
        which is the body the money is owed to and the name on the return that
        gets filed. US-RAT-009 §5 puts it there for exactly this reason.
      * the jurisdiction's `name` when no authority is recorded, because a
        jurisdiction with a name and no authority is a half-filled row, not an
        empty one.
      * the TAX's own name last, because *"City sales tax"* still tells a human
        more than a uuid does.

    `None` only when the tax id resolves to nothing of this tenant's — a crafted
    id, another tenant's tax (the filter is tenant-scoped, HR-1), or no id at
    all. The caller then says so in those words rather than printing "None":
    see `apps/billing/issue._authority_label`.

    A LABEL, NEVER A KEY. Nothing may map, post or stamp on this string — the
    money-bearing read is `liability_gl_account_id_for_tax` above, keyed on the
    tax id, and matching a tax by its DESCRIPTION was option D of OQ-116 and the
    PO declined it because it misposts silently the first time a tax is renamed
    or a catalogue is translated. This is display text for a refusal message and
    that is all it is.
    """
    if not _valid_uuid(tax_id):
        return None
    row = (
        models.Tax.objects.filter(tenant_id=_tenant_id(), pk=tax_id)
        .values_list("jurisdiction__authority", "jurisdiction__name", "name")
        .first()
    )
    if row is None:
        return None
    for candidate in row:
        text = (candidate or "").strip()
        if text:
            return text
    return None


def deposit_rule_for(
    rate_plan_id: Any,
    account_type_id: Any,
    *,
    unit_id: Any = None,
    account_id: Any = None,
    size_class: str | None = None,
) -> dict[str, Any] | None:
    """The fixed deposit this plan asks of this consumer category — BR-RAT-020/023.

    Published for BILLING: BR-BIL-012 puts the deposit line on the FIRST bill,
    and `plan_deposit_rules` is where the figure lives (rate_plan × account_type,
    r5 #8). US-BIL-010 is the caller. Before this read the row was reachable only
    inside `plan_row`'s detail dict, which billing may not consume — it is a
    screen payload, not a contract, and reading a money figure out of one is how
    a display change silently re-prices a bill.

    ── WHAT `None` MEANS, AND IT IS NOT ZERO ────────────────────────────────
    `None` is *this plan asks no deposit of this category* — a real and common
    configuration, and the caller then emits NO deposit line at all rather than
    a $0.00 one. A zero-valued line on a customer's first bill states that a
    deposit was assessed and waived, which is a different fact from never having
    been assessed. Unknown ids (including another tenant's — the filter is
    tenant-scoped, HR-1) answer `None` the same way, because a deposit rule that
    is not this tenant's simply is not found.

    The CURRENCY travels with the amount (CLAUDE.md rule 2 — money is never a
    bare number), so the caller can refuse a rule denominated in something other
    than the bill's rather than summing two currencies into one line.

    ── `unit_id` / `account_id` · A DEPOSIT PRICED BY SIZE (`OQ-RAT-12786`) ──
    PO 2026-10-03, verbatim: *"(a) Class or size: the deposit table gets a size
    column, like charge codes have."* A deposit code priced by meter size asks
    the size of THIS connection, so the caller says which connection: the unit
    (customers' Deposit step, before an account exists) or the account (the
    first bill, which walks to its unit). Neither is needed for a code priced by
    class. An answer that cannot be priced comes back as `amount: None` with a
    `refusal` (`charge_prices.SIZE_NOT_RECORDED` / `SIZE_NOT_PRICED` /
    `FLAT_AND_SIZES`) and the code and size — **never as `None`**, which would
    say *this plan asks no deposit* and let a customer connect without one.

    ── `size_class` · THE CLERK PICKS THE SIZE WHEN NO METER IS FITTED ───────
    PO 2026-10-04, verbatim: *"(c) Let the clerk pick the size on the Deposit
    step."* (`DEF-CUS-9521`.) Where the connection records no size, the size
    the clerk picked prices the deposit; a RECORDED size always wins. Billing
    passes only the account, so the pick is read back off the account
    (`seams.account_deposit_size_class`) — the first bill asks exactly what
    the counter took.
    """
    if not (_valid_uuid(rate_plan_id) and _valid_uuid(account_type_id)):
        return None
    row = (
        models.PlanDepositRule.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=rate_plan_id, account_type_id=account_type_id
        )
        .values("amount", "currency")
        .first()
    )
    if row is None:
        if account_id is not None and _valid_uuid(account_id):
            if unit_id is None:
                unit_id = seams.account_unit_id(account_id)
            if size_class is None:
                size_class = seams.account_deposit_size_class(account_id)
        return plan_deposit_for(
            rate_plan_id, account_type_id, unit_id=unit_id, size_class=size_class
        )
    return {"amount": row["amount"], "currency": row["currency"]}


def plan_deposit_for(
    rate_plan_id: Any,
    account_type_id: Any,
    *,
    unit_id: Any = None,
    size_class: str | None = None,
) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING — `BR-RAT-023` as amended 2026-10-03
    (`CR-167-BRC10` ruling 9): THE DEPOSIT FROM THE CODES THE PLAN NAMES.

    Read only when the plan carries no typed `plan_deposit_rules` row for the
    class (those still answer first, so not a cent moves for a plan that had
    one — and no seeded tenant has any, measured). The plan version read on
    the day names its deposit codes (`plan_charge_rules`, `role="deposit"`);
    each code that applies to the class answers its CLASS price (or its
    every-class price) on the day. Two codes that both price the class are
    both asked — the plan named both — and their amounts add up (our judgment,
    decision log *"CR-167 TASK 3"*).

    ── A CODE PRICED BY METER SIZE — `OQ-RAT-12786` CLOSED 2026-10-03 ───────
    PO verbatim: *"(a) Class or size: the deposit table gets a size column,
    like charge codes have."* (`BR-RAT-020` SUPERSEDED in part.) The stub that
    raised `NotImplementedError("OQ-RAT-12786")` here is gone: a sized deposit
    code is priced at the connection size of the SERVICE THE CODE NAMES on
    this unit (`seams.connection_size_for`, the seam billing sizes a base
    from), by `charge_prices.answer_from_rows` — the one lookup every charge
    code uses, so a row naming this class beats the every-class row for the
    same size exactly as it does for a base. Worked (the ruling's figures): a
    code at 5/8" **$150.00** and 2" **$600.00** asks a 5/8" connection
    $150.00 and a 2" one $600.00.

    ⚠ **A SIZE THAT CANNOT BE PRICED IS A NAMED REFUSAL, NEVER `None`.** No
    size recorded, a size the code does not price, or a code with BOTH an
    every-size row and size rows comes back as `{"amount": None, "refusal":
    …, "code": …, "size_class": …}`: `None` means *this plan asks no
    deposit*, and reading an unpriced size that way would connect a customer
    with no deposit taken. A code that prices nothing for THIS CLASS is still
    skipped, as before (the plan asks this class nothing through it).

    ── NO METER FITTED: THE CLERK PICKS THE SIZE — `DEF-CUS-9521` ───────────
    PO 2026-10-04, verbatim: *"(c) Let the clerk pick the size on the Deposit
    step."* Where the connection records NO size (no meter fitted, or no
    connection for the code's service), `size_class` — the size the clerk
    picked — prices the code, and the answer says so (`size_picked`,
    `size_class`, `size_label`) so the pick can be stored and audited. A
    RECORDED size always wins over a pick: the ruling keeps *"where a meter
    size IS recorded the amount follows it as today"*. With no size recorded
    and none picked, the refusal (`size_not_recorded`) now carries `sizes`:
    every size this plan prices for this class, each with the TOTAL deposit
    it would ask (`{size_class, label, amount}`), so the step can offer them.
    Worked (the ruling's figures): no meter, 5/8" $150.00 / 2" $600.00
    offered; the clerk picks 2" → **$600.00**.
    """
    code = seams.account_type_code_by_id(account_type_id)
    rules = [
        rule
        for rule in models.PlanChargeRule.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=rate_plan_id, role="deposit"
        ).select_related("charge", "charge__service")
        if rule.charge.deleted_at is None
    ]
    if not rules:
        return None
    day = plan_versioning.binding_day()
    answer = _deposit_from_rules(rules, code, day, unit_id, size_class)
    if (
        answer is not None
        and answer.get("refusal") == charge_prices.SIZE_NOT_RECORDED
        and size_class is None
    ):
        answer["sizes"] = _deposit_size_choices(rules, code, day, unit_id)
    return answer


def _deposit_from_rules(
    rules: list[Any], code: Any, day: Any, unit_id: Any, picked: str | None
) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING — the body of `plan_deposit_for`: each deposit
    code the class pays, priced at the RECORDED size of its service on this
    unit, or at `picked` where none is recorded (`DEF-CUS-9521`)."""
    total = None
    currency = None
    used_pick = None
    for rule in rules:
        charge = rule.charge
        classes = [str(one) for one in (charge.applies_to_customer_classes or [])]
        if classes and code not in classes:
            continue
        rows = charge_prices.rows_in_force([charge.id], day).get(charge.id, [])
        size = None
        if any(not row.is_flat for row in rows) and charge.service_id is not None:
            size = seams.connection_size_for(unit_id, charge.service.code)
            if size is None and picked:
                size = picked
                used_pick = picked
        answer = charge_prices.answer_from_rows(rows, size_class=size, customer_class=code)
        if answer.refusal == charge_prices.NO_PRICE:
            continue  # this code prices nothing for this class (unchanged)
        if not answer.priced or answer.amount is None:
            return {
                "amount": None,
                "currency": None,
                "refusal": answer.refusal or charge_prices.SIZE_NOT_PRICED,
                "code": charge.code,
                "size_class": size,
            }
        total = (total or Decimal("0")) + answer.amount
        currency = answer.row.currency if answer.row is not None else currency
    if total is None:
        return None
    out: dict[str, Any] = {"amount": total, "currency": currency}
    if used_pick is not None:
        out["size_class"] = used_pick
        out["size_label"] = seams.size_class_names([used_pick]).get(used_pick, used_pick)
        out["size_picked"] = True
    return out


def _deposit_size_choices(
    rules: list[Any], code: Any, day: Any, unit_id: Any
) -> list[dict[str, Any]]:
    """The sizes a clerk may pick when no meter is fitted (`DEF-CUS-9521`):
    every size a sized deposit code prices for this class, each answered by
    the SAME body the commit runs — so the figure offered is the figure
    taken, flat codes beside it included. A size that would still refuse is
    not offered. Order is the size code's; the screen orders by the size the
    NAME states (smallest first), as every size list does."""
    candidates: set[str] = set()
    for rule in rules:
        charge = rule.charge
        classes = [str(one) for one in (charge.applies_to_customer_classes or [])]
        if classes and code not in classes:
            continue
        rows = charge_prices.rows_in_force([charge.id], day).get(charge.id, [])
        candidates.update(
            size
            for size in charge_prices.resolve_for_class(rows, code)
            if size != charge_prices.ALL_SIZES
        )
    names = seams.size_class_names(sorted(candidates))
    out: list[dict[str, Any]] = []
    for size in sorted(candidates):
        answer = _deposit_from_rules(rules, code, day, unit_id, size)
        if answer is None or answer.get("amount") is None:
            continue
        out.append(
            {
                "size_class": size,
                "label": names.get(size, size),
                "amount": answer["amount"],
                "currency": answer.get("currency"),
            }
        )
    return out


#: `plan_late_fee_terms` says a plan charges NO late fee. Named rather than
#: served as a bare `None`, because "this plan charges nothing" and "I could not
#: read this plan" are different facts and a caller that flattens them into one
#: is how a read failure becomes a free late fee (DEF-CUS-3653's shape).
LATE_FEE_NO_CHARGE_CODE = "plan_names_no_late_fee_charge_code"
#: The plan names a code that has been RETIRED (IS-1). A different fact from
#: naming none — a utility did point this plan somewhere — and the same money.
LATE_FEE_RETIRED_CHARGE_CODE = "plan_names_a_retired_late_fee_charge_code"


#: DEF-RAT-8753 — the plan's late-fee code is priced BY CUSTOMER CLASS and
#: states no terms for this account's class, and no single percent beside them.
#: NOT the ruled zero (that is a plan naming no code): the utility priced the
#: fee for some classes and not this one, and charging nothing would be a
#: silent free late fee. Billing refuses by this name.
LATE_FEE_CLASS_NOT_PRICED = "late_fee_charge_code_states_no_terms_for_this_class"


def plan_late_fee_terms(
    rate_plan_id: Any, customer_class: str | None = None, on_date: date | None = None
) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING — THE LATE-FEE TERMS A PLAN CHARGES ON, or None.

    **BR-RAT-1011 / `CR-078` (PO ruling 2026-09-07, finance re-signed the same
    day).** PO verbatim: *"you ahve to take late fees form charge code mentione
    din the plan - if plan doent provide you that charge code then you have to
    put zero on late payment. - Logic aplplied ot Minimum late fee $5- - you
    can link these defaults in Charge code - we have a charge code for late
    payment"*.

    Returns the two terms BR-BIL-001's arithmetic needs — `percent` and
    `minimum` — read off the charge code the PLAN names, plus the code's
    identity so the fee books where the code says (BR-BIL-075/BR-BIL-010).

    ⚠⚠ **THREE ANSWERS, NOT TWO, AND COLLAPSING THE FIRST TWO IS THE WHOLE
    DANGER OF THIS CHANGE.** The PO's sentence is *"the charge code mentioned
    in THE PLAN"*, which presupposes a plan; *"if plan doent provide you that
    charge code"* is about a plan that EXISTS and names none.

      * **`None` — THERE IS NO PLAN TO ASK.** The id is absent, not a uuid, or
        names no row of this tenant (HR-1 makes another tenant's the same
        answer). This is a DATA FAULT, never the ruling, and a caller must
        REFUSE rather than charge zero: an account whose plan cannot be read is
        an account nothing could have priced, and answering "no late fee" for
        it would turn a broken account into a free one, silently, on every bill
        it ever gets. That is the exact shape `CR-078`'s ordering exists to
        prevent, reached from the other side.
      * **`{"charge_id": None, "reason": …}` — THE PLAN EXISTS AND CHARGES
        NOTHING.** It names no code, or the code it names was retired (IS-1 — a
        retired charge is not chargeable). **This is the PO's ruled ZERO.**
      * **the full dict — the terms**, `charge_id` set.

    `reason` names which of the zero states it is, so the fee path and the
    screen can SAY it. A silent zero is the failure this whole change was
    ordered to prevent, and CLAUDE.md records the general form: an absence is
    invisible to every check this repo has.

    ⚠ **THIS READ DOES NOT FALL BACK TO `tenant_settings.billing_defaults`, AND
    THAT IS THE WHOLE CHANGE.** `late_pct` (1.5) and `late_min_amount` (5) still
    live on the Billing-defaults screen (S66) and still describe what a utility
    intends; they are no longer what an engine reads. The seeded `LATE` charge
    code carries **the same two figures** — `percent 1.5, min_amount 5`,
    `apps/tenancy/fixtures/lookup_defaults.json` — which is why `GT-10`'s ❄️
    FROZEN **$8.13** is $8.13 either way and why this is a routing change rather
    than a figure change. What DOES change: a plan pointed at a different code
    produces a different fee, so 8.13 is no longer universal. The finance
    re-sign of 2026-09-07 states exactly that and covers exactly that.

    ⚠ **`percent` AND `min_amount` ARE SERVED RAW, NOT ROUNDED.** BR-RAT-003 /
    B4.4 round ONCE, at finalization, inside `assess_late_fee`. Rounding here
    would be a second rounding on a money path.

    ⚠ **`percent` IS A FRACTION, NOT PERCENTAGE POINTS — AND THE FIXTURE READS
    THE OTHER WAY, WHICH IS THE TRAP.** `apps/tenancy/fixtures/
    lookup_defaults.json` writes `"percent": "1.5"` and the seeded ROW holds
    **`0.015000`**; `seed_demo.py` says so at its own line 163 (*"`charges
    .percent` stores a FRACTION"*) and `services._PERCENT_POINTS = 100` is the
    conversion. `amount_rules.rules.percent_with_minimum` multiplies
    `percent × basis` with NO division, and GT-8's ❄️ FROZEN arithmetic is
    written `max(5, 0.015 × 542.10)` — a fraction. So this read serves the
    column through UNTOUCHED. Dividing here, or reading `1.5` off the fixture
    and passing it on, would charge **$8.13 × 100 = $813.15** on the reference
    bill.
    """
    if not _valid_uuid(rate_plan_id):
        return None  # no plan to ask — a data fault, not the ruling
    _plan = models.RatePlan.objects.filter(tenant_id=_tenant_id(), id=rate_plan_id).first()
    if _plan is None:
        return None  # no plan of this tenant by that id — a data fault
    # `BR-RAT-1066` — the late-fee code of the plan VERSION read on `on_date`
    # (the head's is the plan's own column, which is every plan with one
    # version: the same code this read always returned).
    _code_id = plan_versioning.terms_on(_plan, on_date)["late_fee_charge_id"]
    _charge = (
        models.Charge.objects.filter(pk=_code_id, tenant_id=_tenant_id())
        .values(
            "code", "name", "percent", "min_amount", "deleted_at", "tenant_id",
            "grace_days", "grace_mode", "amount_rule",
        )
        .first()
        if _code_id is not None
        else None
    )
    if _code_id is not None and _charge is None:
        return {"charge_id": None, "code": None, "reason": LATE_FEE_NO_CHARGE_CODE}
    row = {
        "late_fee_charge_id": _code_id,
        **{f"late_fee_charge__{key}": value for key, value in (_charge or {}).items()},
    }
    if row["late_fee_charge_id"] is None:
        # THE RULING. The plan is real and names no code: charge zero.
        return {"charge_id": None, "code": None, "reason": LATE_FEE_NO_CHARGE_CODE}
    # IS-1 and HR-1: a retired code, or somebody else's, is not chargeable —
    # and a plan pointed at one charges zero exactly as an unpointed plan does.
    if row["late_fee_charge__deleted_at"] is not None:
        return {"charge_id": None, "code": None, "reason": LATE_FEE_RETIRED_CHARGE_CODE}
    if str(row["late_fee_charge__tenant_id"]) != str(_tenant_id()):
        return {"charge_id": None, "code": None, "reason": LATE_FEE_NO_CHARGE_CODE}
    grace = _late_fee_grace(_plan, row)
    # ── 🔒 HUMAN-REVIEW-PENDING · DEF-BIL-10201 · A FLAT LATE FEE ──────────
    # PO 2026-10-17, verbatim: *"we ahve to allow flat as we wll %age"*. A
    # late-fee code whose amount rule is `flat` charges its FLAT AMOUNT — the
    # code's *All sizes* row in force on `on_date` for this account's class,
    # exactly as `charge_by_code` prices any flat code — and never the percent
    # pair. Until this branch the pair was read for every rule, a flat code
    # states neither column, and both NULLs were served as zero: **a Flat
    # $10.00 code charged $0.00, silently.** Worked: $900.00 overdue past grace
    # on Flat $10.00 → **$10.00**. A flat code stating NO amount for this class
    # is not the ruled zero (that is a plan naming no code) — it refuses by
    # `LATE_FEE_CLASS_NOT_PRICED`, the name a class-priced percent code with no
    # row for the class already refuses by. The percent paths below are
    # unchanged, so ❄️ GT-8's $8.13 cannot move.
    if (row.get("late_fee_charge__amount_rule") or "") == "flat":
        flat = charge_prices.flat_amount(row["late_fee_charge_id"], on_date, customer_class)
        base = {
            "charge_id": str(row["late_fee_charge_id"]),
            "code": row["late_fee_charge__code"],
            "name": row["late_fee_charge__name"],
            "amount_rule": "flat",
            "customer_class": customer_class,
        }
        if flat is None:
            return {**base, "refusal": LATE_FEE_CLASS_NOT_PRICED}
        return {**base, "flat_amount": flat, "percent": None, "minimum": None, **grace}
    # ── 🔒 DEF-RAT-8753 · THE TERMS FOR THIS ACCOUNT'S CLASS ──────────────
    # The PO-approved mock-up prices `LATE` by customer class (Residential
    # 1.50% min $5.00, Commercial 2.00% min $10.00). Where the code states
    # terms rows in force on `on_date` (the assessment day; default the
    # tenant's today), the class's row wins — `charge_prices.class_terms_on`,
    # class beats every class. A code with NO terms rows answers exactly as
    # before from its own two columns, which is why GT-8 / GT-10's ❄️ FROZEN
    # $8.13 cannot move: the seeded `LATE` states no class rows.
    terms_rows = any(charge_prices.terms_in_force([row["late_fee_charge_id"]], on_date).values())
    if terms_rows:
        terms = charge_prices.class_terms_on(row["late_fee_charge_id"], customer_class, on_date)
        if terms is not None:
            return {
                "charge_id": str(row["late_fee_charge_id"]),
                "code": row["late_fee_charge__code"],
                "name": row["late_fee_charge__name"],
                "percent": terms.percent,
                # No floor stated on the class row is a minimum of zero.
                "minimum": terms.minimum if terms.minimum is not None else Decimal("0"),
                "customer_class": customer_class,
                "priced_by": "customer_class",
                "amount_rule": row.get("late_fee_charge__amount_rule") or "percent_with_minimum",
                **grace,
            }
        if row["late_fee_charge__percent"] is None:
            return {
                "charge_id": str(row["late_fee_charge_id"]),
                "code": row["late_fee_charge__code"],
                "name": row["late_fee_charge__name"],
                "refusal": LATE_FEE_CLASS_NOT_PRICED,
                "customer_class": customer_class,
            }
    return {
        "charge_id": str(row["late_fee_charge_id"]),
        "code": row["late_fee_charge__code"],
        "name": row["late_fee_charge__name"],
        # NULL on either term is ZERO for that term, not a fallback: a utility
        # that cleared the percent off its late-fee code has said the fee is the
        # minimum alone, and a utility that cleared both has said there is none.
        "percent": row["late_fee_charge__percent"] or Decimal("0"),
        "minimum": row["late_fee_charge__min_amount"] or Decimal("0"),
        "amount_rule": row.get("late_fee_charge__amount_rule") or "percent_with_minimum",
        **grace,
    }


#: Where the grace a late fee is assessed on came from (PO 2026-10-06 11 (a)).
GRACE_FROM_PLAN = "plan"  # an override the plan stated BEFORE the ruling
GRACE_FROM_CODE = "charge_code"  # the late-fee code's own grace — the rule
GRACE_FROM_DEFAULT = "billing_defaults"  # a penalty code that states none


def _late_fee_grace(plan: models.RatePlan, row: dict[str, Any]) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING (❄️ B4/B5 late fee; finance RE-SIGN owed) — the
    grace days and mode a plan's late fee is assessed on, and where they came
    from.

    PO ruling 2026-10-06 11 (a), verbatim: *"Put grace on the late-fee code.
    When Type is Penalty, the form asks Grace days (default 5) and Calendar /
    Business days, and billing uses the code's grace."* Order, each field on
    its own:

    1. **the plan's own override** (`plan_penalty_rules.grace_days/mode`) where
       the plan states one — OUR JUDGMENT, recorded in the decision log the
       same day: an override stated before the ruling keeps applying until a
       System Admin clears it, so **no customer's late-fee date moves on
       deploy**; the plan form offers no new one;
    2. **the late-fee code's grace** — the ruling;
    3. **Settings → Billing defaults** for a code that states none (one minted
       on Settings after `rating/0066` seeded the existing ones).

    Worked: due 1 Nov, $100.00 unpaid, `LATE` grace 5 calendar days → a $5.00
    fee on the next bill only if still unpaid after 6 Nov; `LATE` grace 10 →
    no fee until after 11 Nov. The arithmetic is `late_fee.grace_has_elapsed`,
    unchanged (GT-8).
    """
    override = (
        models.PlanPenaltyRule.objects.filter(rate_plan=plan, tenant_id=_tenant_id())
        .values("grace_days", "grace_mode")
        .first()
        or {}
    )
    default_days, default_mode = seams.late_grace_default()
    days, days_from = override.get("grace_days"), GRACE_FROM_PLAN
    if days is None:
        days, days_from = row.get("late_fee_charge__grace_days"), GRACE_FROM_CODE
    if days is None:
        days, days_from = default_days, GRACE_FROM_DEFAULT
    mode = override.get("grace_mode") or row.get("late_fee_charge__grace_mode") or default_mode
    return {"grace_days": int(days), "grace_mode": mode, "grace_from": days_from}


def plans_missing_late_fee_charge() -> list[dict[str, Any]]:
    """Every plan of THIS TENANT that names no live late-fee charge code.

    **BR-RAT-1011's visibility half.** A plan with no code charges nothing, which
    is the ruled behaviour and also — left unwatched — indistinguishable from a
    utility whose late fees simply stopped working. So the state is COUNTABLE
    rather than silent: `manage.py cr078_late_fee_codes` prints this per tenant
    and `g121_plans_name_their_late_fee_code.py` fails on a non-empty
    answer for the sample utility.

    Retired codes are included, because a plan pointed at a retired code
    charges zero exactly as an unpointed one does (IS-1) and a report that
    showed only the NULLs would understate the number.
    """
    rows = (
        models.RatePlan.objects.filter(tenant_id=_tenant_id())
        .filter(Q(late_fee_charge__isnull=True) | Q(late_fee_charge__deleted_at__isnull=False))
        .values("id", "code", "name", "status", "late_fee_charge__code")
        .order_by("code")
    )
    return [
        {
            "plan_id": str(row["id"]),
            "code": row["code"],
            "name": row["name"],
            "status": row["status"],
            "reason": (
                "names_no_charge_code"
                if row["late_fee_charge__code"] is None
                else "names_a_retired_charge_code"
            ),
        }
        for row in rows
    ]


def charge_by_code(
    code: str, on_date: date | None = None, customer_class: str | None = None
) -> dict[str, Any] | None:
    """One LIVE charge code of this tenant, by its code — or None.

    Published for BILLING: BR-BIL-012's connection charge and BR-BIL-007's
    *"NSF/reconnect fees are tenant-configured charge codes, never hardcoded"*
    both need to turn a code a caller names into the tenant's own row. The
    amount is a SEED the tenant edits (B4 §NSF), never a constant, which is
    exactly why this read exists rather than a literal at the call site.

    Only `flat` amounts are returned with a figure. A `percent` or
    `percent_with_minimum` rule needs a basis this read has no way to supply,
    and returning its `amount` column would state a flat price for a rule that
    is not one — so `amount` comes back `None` and the caller REFUSES rather
    than charging a number nobody computed.

    `None` for an unknown code, a deactivated one (IS-1 — a retired charge is
    not chargeable) and another tenant's, which are one answer by HR-1.
    """
    if not code:
        return None
    row = (
        models.Charge.objects.filter(tenant_id=_tenant_id(), code=code, deleted_at__isnull=True)
        .values("id", "code", "name", "amount_rule", "gl_account_id", "taxable_default", "charge_type")
        .first()
    )
    if row is None:
        return None
    # DEF-RAT-8753 — `per_case` is served as itself with `amount: None`: the
    # amount is the clerk's, entered when the fee is used (`billing.fee_bill`).
    flat = (row["amount_rule"] or "flat") == "flat"
    # CR-156-BRC10 — the flat amount is the code's *All sizes* row in force on
    # `on_date` (default: the tenant's today — a fee charged now is priced
    # now), for `customer_class` where the code is priced by class.
    amount = charge_prices.flat_amount(row["id"], on_date, customer_class) if flat else None
    # ── 🔒 HUMAN-REVIEW-PENDING · DEF-RAT-9807 · `BR-RAT-1054` AMENDED 2026-10-06 ─
    # A `per_case` code may carry ONE optional default — the figure a clerk's
    # screen starts the fee at. It is served HERE, under its own key, and
    # `amount` stays None: every door that charges a code's own price reads
    # `amount` (service-request fees, the counter, deposits, late fees), and
    # none of them may start charging a per-case code at its default with no
    # clerk looking. `fee_bill.charge_code_line` still takes the clerk's figure.
    per_case = row["amount_rule"] == "per_case"
    default = charge_prices.flat_amount(row["id"], on_date, customer_class) if per_case else None
    return {
        "id": str(row["id"]),
        "code": row["code"],
        "name": row["name"],
        "amount": amount,
        "default_amount": default,
        "amount_rule": row["amount_rule"] or "flat",
        "gl_account_id": str(row["gl_account_id"]) if row["gl_account_id"] else None,
        "taxable_default": bool(row["taxable_default"]),
        # CR-163-BRC10 — read only: a fee added to a build must be a ONE-TIME
        # code, so metering asks the type. It prices nothing.
        "charge_type": row["charge_type"],
    }


def application_fee_charge(on_date: date | None = None) -> dict[str, Any] | None:
    """🔒 `DEF-CUS-9819` (PO rulings 2026-10-06) — the utility's ONE live code
    marked *Application fee*, priced exactly as `charge_by_code` prices it — or
    None when no code is marked.

    Published for CUSTOMERS (every new service request gets this line at its
    live price) and the PORTAL (*What you will pay* shows it before Send). The
    figure is read here and never copied: a utility that moves `APP-FEE` from
    $10.00 to $12.00 has every request created after that carry $12.00, and
    every line already raised keep the figure it was raised at
    (`add_fee_line`'s lock). A `$0.00` price is a real answer (PO: *"we wil
    ahve application fees as zero"*); `amount: None` means the code cannot be
    priced flat today and the caller adds nothing.
    """
    code = (
        models.Charge.objects.filter(
            tenant_id=_tenant_id(), is_application_fee=True, deleted_at__isnull=True
        )
        .values_list("code", flat=True)
        .first()
    )
    return charge_by_code(code, on_date) if code else None


def plan_nsf_charge(plan_id: Any, on_date: date | None = None) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-PAY-10698` — the NSF fee code a PLAN lists.

    PO 2026-10-30, verbatim: *"Do not hardcode check NSF Account> Unit> Plan>
    Charge code"*. Billing walks the account to its unit and the unit to its
    plan; this is the last hop — **which of the plan's codes is its NSF fee**.

        -> {"code": str, "name": str}          one marked code, live
           {"code": None, "reason": "nsf_fee_not_set_on_plan"}
           {"code": None, "reason": "nsf_fee_ambiguous_on_plan", "codes": [...]}

    Read off the plan's Charges list (`plan_charge_rules`, role `charge`) as
    the version in force on `on_date` sees it (`BR-RAT-1066`), keeping the
    codes DECLARED `is_nsf_fee` (never matched by their code string). The
    AMOUNT is not read here: a plan binds and never prices (PO 2026-08-19,
    *"no plan cannot override prices"*), so `amount_override` is not consulted
    and the caller prices the code through `charge_by_code` like any other.

    **Two marked codes on one plan is REFUSED by name, never resolved by
    order** — the customer would otherwise be charged by catalogue order
    (DEF-468's lesson for base codes). None marked is an ordinary state: the
    utility charges no NSF fee on that plan, and the bounce says so.
    """
    not_set = {"code": None, "reason": "nsf_fee_not_set_on_plan"}
    if not _valid_uuid(plan_id):
        return not_set
    version = plan_versioning.version_on(plan_id, on_date)
    rules = (
        models.PlanChargeRule.all_versions.filter(
            tenant_id=_tenant_id(), rate_plan_id=plan_id, plan_version=version
        )
        if version is not None
        else models.PlanChargeRule.objects.filter(tenant_id=_tenant_id(), rate_plan_id=plan_id)
    )
    marked = sorted(
        {
            (row["charge__code"], row["charge__name"])
            for row in rules.filter(
                role="charge", charge__is_nsf_fee=True, charge__deleted_at__isnull=True
            ).values("charge__code", "charge__name")
        }
    )
    if not marked:
        return not_set
    if len(marked) > 1:
        return {
            "code": None,
            "reason": "nsf_fee_ambiguous_on_plan",
            "codes": [code for code, _ in marked],
        }
    return {"code": marked[0][0], "name": marked[0][1]}


# ══════════════════════════════════════════════════════════════════════════
# DISCOUNTS — the bill run's two R6 reads (DEF-502, 2026-08-22)
# ══════════════════════════════════════════════════════════════════════════
# ⚠ A SEPARATE BLOCK, DELIBERATELY, at the end of the file: another lane is
# working in the TAX block above (plan_tax_rules and its neighbours), so
# nothing here edits those functions — `discount_treatments_for_taxes` exists
# precisely so `taxes.discount_treatment` can cross the billing seam WITHOUT
# touching `plan_tax_rules`. Both reads are READ-ONLY.


def billable_discount_rules(
    account_id: Any, plan_id: Any, on_day: date | None = None
) -> list[dict[str, Any]]:
    """The discounts that REACH THIS ACCOUNT'S BILL, both gates applied.

    BR-RAT-069: *"plan attachment makes a discount available, not granted"* —
    the ENROLMENT grants. BR-RAT-110: *"both gates, not one replacing the
    other"* — the plan's binding says which discounts it offers, and the run
    reads the enrolments THROUGH it. An enrolment in a discount the plan does
    not bind therefore reaches no bill, exactly as `resolution
    .resolve_discounts` drops it on the R-chain (*"a discount the account is
    enrolled in but the catalogue does not offer is dropped, not guessed"*),
    which is what `tests/test_def_438_parity.py`'s R6 comparison holds the two
    paths to.

    `on_day` is the bill's SERVICE DATE — the same pivot every tariff version
    resolves on (BR-RAT-007), so a July bill run in August reads July's
    enrolments and the plan-binding window in force in July.

    The heavy lifting — dates, proof, caps netted of grants, budget remaining —
    is `discount_services.discount_rules_for_account`, the DB-backed R6
    resolver built with the arithmetic (2026-08-19) and called by nothing on
    the bill path until DEF-502 closed. This read narrows its answer by the
    plan binding and adds ONE field it does not carry: `name`, the
    customer-facing bill line label (DIS-02 step 1 — the reduction prints as
    its own line and something has to print on it).

    Rows are DICTS, like `plan_tax_rules`' — the seam's shape, so billing
    never imports a rating type (B1). Field names mirror
    `discount_pricing.DiscountRule` one for one.
    """
    # Lazy import: `discount_services` imports `rating.services`, which sits
    # above this module in the import graph — a module-level import would be a
    # cycle waiting for an unlucky ordering.
    from apps.rating import discount_services

    if not _valid_uuid(plan_id) or not account_id:
        return []
    when = on_day or seams.tenant_today()
    rules = discount_services.discount_rules_for_account(account_id, when)
    if not rules:
        return []
    bound: dict[str, str] = {}
    for row in discount_models.PlanDiscountRule.objects.filter(
        tenant_id=_tenant_id(), rate_plan_id=plan_id
    ).select_related("discount"):
        # BR-RAT-110: the binding's window may NARROW the discount's own,
        # never widen it — outside it, the plan does not offer the discount.
        if row.available_from and row.available_from > when:
            continue
        if row.available_to and row.available_to < when:
            continue
        bound[row.discount.code] = row.discount.name
    out: list[dict[str, Any]] = []
    for rule in rules:
        if rule.code not in bound:
            continue  # enrolled but not offered by THIS plan — dropped, not guessed
        out.append(
            {
                "code": rule.code,
                "name": bound[rule.code] or rule.code,
                "discount_type": rule.discount_type,
                "value": rule.value,
                "currency": rule.currency,
                "applies_to": rule.applies_to,
                "verified": rule.verified,
                "proof_before_first_reduction": rule.proof_before_first_reduction,
                "applies_to_service": rule.applies_to_service,
                "applies_to_charge_codes": list(rule.applies_to_charge_codes),
                "cap_per_bill": rule.cap_per_bill,
                "cap_year_remaining": rule.cap_year_remaining,
                "cap_lifetime_remaining": rule.cap_lifetime_remaining,
                "budget_remaining": rule.budget_remaining,
                "exhaustion_behaviour": rule.exhaustion_behaviour,
                "bill_floor_amount": rule.bill_floor_amount,
                "stacking_precedence": rule.stacking_precedence,
                "stacks_with_others": rule.stacks_with_others,
                "exclusivity_group": rule.exclusivity_group,
            }
        )
    return out


def discount_treatments_for_taxes(tax_ids: tuple[Any, ...]) -> dict[str, str]:
    """`taxes.discount_treatment` for a set of tax rows, keyed by id (BR-RAT-106).

    ONE batched read per gathered account, so the statutory before/after answer
    can ride billing's `TaxRule` without this lane touching `plan_tax_rules`
    (another lane's block — see the banner above). Values are the bounded
    vocabulary `DISCOUNT_TREATMENTS` (`ck_taxes_discount_treatment` in the DB);
    an id that resolves to nothing simply has no entry, and the engine then
    reads None as `before` — the column's own default, inert on any bill
    without a discount.
    """
    ids = [tax_id for tax_id in tax_ids if tax_id and _valid_uuid(tax_id)]
    if not ids:
        return {}
    return {
        str(pk): treatment
        for pk, treatment in models.Tax.objects.filter(
            tenant_id=_tenant_id(), pk__in=ids
        ).values_list("id", "discount_treatment")
    }


# ══════════════════════════════════════════════════════════════════════════
# THE CHARGE CODE'S OWN GL ACCOUNT — BR-BIL-010's fee half (DEF-714, 2026-08-25)
# ══════════════════════════════════════════════════════════════════════════
# A SEPARATE BLOCK at the end of the file for the same reason the discount
# block above gives: other lanes are working in the tax and charge blocks, and
# nothing here edits them. READ-ONLY.


def gl_account_id_for_charge(charge_id: Any) -> str | None:
    """The GL account THIS charge code's fee is owed into, or None.

    ── WHY THIS READ IS RATING'S ─────────────────────────────────────────────
    BR-BIL-010: *"charge codes carry their own GL"*, and the column is
    `rating.charges.gl_account_id` — the tenant's own, edited on S13, validated
    against the ledger when it is WRITTEN (`services._validated_gl_account`,
    message key `rating.charges.gl_account_unknown`). One home for the mapping,
    exactly as the PO's OQ-116 closure kept ONE home for a tax authority's
    liability account. This is the read billing asks at issue
    (`apps/billing/issue._gl_account_for`, the `fee` branch).

    Published for **DEF-714**: `gather._charge_fees_for` puts BR-RAT-117's
    recurring and auto-apply codes on every ordinary bill (PO 2026-08-22,
    *"ruccuring and Autom apply land on bill"*), and until 2026-08-25 the fee
    line reached issue naming no code, so issue refused it — unconditionally,
    without reading the `charge_id` it was handed. A tenant that had configured
    any such code could issue NO bill at all.

    ── WHAT `None` MEANS, AND WHAT THE CALLER MUST DO WITH IT ────────────────
    Three situations answer `None`, and every one is a REFUSAL the caller must
    honour rather than a value to substitute for:

      * the charge id names no row of this tenant (another tenant's code is
        simply not found — the filter is tenant-scoped, HR-1);
      * the tenant has not yet pointed that code at an account, which is the
        ordinary state of a freshly configured code and is a one-line fix on
        S13;
      * the line named no charge code at all (`charge_id is None`).

    A caller that turned any of them into a stamped account would post one
    code's revenue into another's bucket, permanently — the stamp freezes with
    the bill (BR-BIL-010).

    ⚠ **A RETIRED CODE STILL ANSWERS, and that is deliberate.**
    `charge_by_code` filters `deleted_at` because it is choosing a code to
    CHARGE, and a retired code is not chargeable (IS-1). This read is the
    opposite question: the line has ALREADY been charged and is asking where
    the money it already carries belongs. Refusing a bill because a clerk
    retired the code between the draft and the release would block a real bill
    for a bookkeeping reason, with no other account to fall back to.

    LIVENESS IS NOT CHECKED HERE, for the reason
    `liability_gl_account_id_for_tax` gives above: whether a ledger account is
    live is the LEDGER's question about the LEDGER's table (B1), and
    `apps.ledger.selectors.account_is_live` is the one implementation of it.
    Billing re-checks it at issue.
    """
    if not _valid_uuid(charge_id):
        return None
    row = (
        models.Charge.objects.filter(tenant_id=_tenant_id(), pk=charge_id)
        .values_list("gl_account_id", flat=True)
        .first()
    )
    return str(row) if row else None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-001@6304a38 (story+rules snapshot hash — EP-RAT-01 lead story; co-packets EP-RAT-02@0b56fac · EP-RAT-03@7d1a8ef · EP-RAT-04@f69a661)
# generated: 2026-08-09 by story-coder v1 (W1 rating feature lane — services/selectors/API); amended 2026-08-09 by story-coder v1 (rating SCHEMA-GAP lane — draft reads + eligibility read) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `plan_tax_rules` resolves the tax id even under a rate_override; `liability_gl_account_id_for_tax` published for billing) · AMENDED 2026-08-15 by Eng-Lead (US-BIL-008 lane — OQ-146's *"let the run report it"*: `tax_authority_label_for_tax` published so billing's break NAMES the authority instead of a rate code; a display read, never a money key) · AMENDED 2026-08-16 by the register lane (BR-RAT-067, PO ruling closing OQ-236 — *"make the rate wizard say which register is which"*: `pricing_inputs` READS `time_of_use_windows.channel` and `_window_channels`, the price-rank resolver, is DELETED; `version_structure` serves the register so the S9 card and the resumed S11 draft can show what the utility said) · AMENDED 2026-08-21 by the DEF-441 lane (r10 line 764 draws the S9 rate schedules as a NINE-COLUMN TABLE, not a card grid — `schedule_card` serves the five columns nothing had a field for: `size_count`, `season_labels`, `block_count`, `window_count`, `effective_from`, every one a count of rows this selector already reads; `SCHEDULE_SORTS` grows 3 → 9 because the PO asked for sortable headers on all nine, and six of them sort in Python over the built card list where `status` already did) · AMENDED 2026-08-26 by the CR-034 (b) WORKEDMONTH lane (`schedule_detail` gained an optional `as_of` and passes it to `schedule_card`, which has taken a date since it was written — BR-RAT-007's service date instead of the day the screen is open; the default is `None` and resolves exactly what it always did. `plan_detail`'s `charge_rules` now carry the CODE's own row beside the plan's override (`service`, `is_base`, `amount_rule`, `amount`(+display), percent/min/max displays, `applies_to_customer_classes`, `size_amounts` batched through `_charge_size_amounts`) — additive, every existing key unchanged; the panel printed *"At the charge code's own amount"* with no amount and this is where the amount was) · AMENDED 2026-08-26 by the CR-034 §7 DISCCOND lane (`_discount_terms` — the CONDITIONS a customer must satisfy to avail a discount, twelve stored columns of the version in force, forwarded and never derived; `plan_discount_rules`, `discount_version_in_force` and `plan_detail` gain an optional `as_of` defaulting to None, which resolves exactly what they always did. ⚠ THREE THINGS ARE DELIBERATELY NOT SERVED: `eligibility_rule` itself, because nothing evaluates it and printing an unevaluated rule as a condition is a false reassurance — `eligibility_checked` states the absence instead; the programme's tenant-wide `budget_cap`, for the reason `enrolled` is dropped on a unit screen; and any six-place money figure, the caps and the floor travelling as DISPLAY strings only) · AMENDED 2026-09-18 by the DEF-RAT-5742 lane (NFR-3 — every list takes its page in the DATABASE: `_paginated` is replaced by `_prepaged` and each selector splits into `<x>_list_queryset` + `<x>_page(params) -> (rows, total)`. Measured on the six endpoints at 60 / 120 / 240 catalogue rows, page 1: plans 209 / 209 / 209 statements, rate schedules 403 / 403 / 403, charges 152 / 152 / 152, taxes 202 / 202 / 202, discounts 252 / 252 / 252, rate-changes 2 / 2 / 2 — flat, where before each grew with the catalogue. The `<x>_list` functions keep their exact behaviour for exports.py, seed_demo, sample_data and the two published customers seams. THREE DERIVED PREDICATES KEEP THEIR O(tenant) PATH AND ARE NOT RE-IMPLEMENTED IN SQL — f.status/f.service on taxes, f.type/f.verification on discounts, f.structure/f.status and the seven derived sorts on schedules — on DEF-387's own reasoning, each NAMED by an `<x>_list_is_sql_pageable` predicate so the exception can be counted rather than hidden) · AMENDED 2026-09-19 by the DEF-RAT-5754 lane (NFR-3 — the jurisdictions read splits like the other six: `jurisdiction_list_queryset(params)` holds every predicate and the ordering in SQL, `jurisdiction_page(params) -> (rows, total)` takes the page with a LIMIT/OFFSET and the count with COUNT(*). `jurisdiction_list` gains an OPTIONAL `params` and its NO-ARGUMENT behaviour is unchanged, because five non-screen callers read it as the whole set — seed_demo three times, sample_data twice. Every predicate is a stored column, so there is NO `_is_sql_pageable` predicate and no derived path — the charge-codes shape. `jurisdiction_row` was NOT opened, so no figure moves. No filter declared and no cap added)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
#         ⚠ AMENDED 2026-08-25 by lane FEELINE (DEF-714 / DEF-201 — `gl_account_id_for_charge` PUBLISHED for billing, the fee half of BR-BIL-010's stamp, and `billable_charge_codes` now returns the row's `id`. Until then a fee line reached issue anonymous and the WHOLE bill refused, so a tenant with any recurring or auto-apply code (BR-RAT-117) could issue none at all. Read-only; no rating math touched; golden 33 PASS/0 FAIL, byte-identical)
# gates: ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ pytest tests/test_us_rat_schedules.py+test_us_rat_plans.py: 65 passed / 2 skipped✔ · full suite -m 'not golden and not isolation': 580 passed / 0 failed / 8 skipped✔ (566 baseline + 14 gap tests; the previously-skipped US-RAT-005 TC-3 draft-structure test is now a real test) · migrate✔ makemigrations --check clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [DEF-RAT-5742 lane 2026-09-18] ruff✔ · black: objects to these files AND to the UNMODIFIED tip's copies of them, in unrelated places — the local black 26.3.1 runs on Python 3.11 against a py3.14 target and says so; a pre-existing environment mismatch, not this change · pytest tests/test_def_rat_5742_rating_lists_page_in_sql.py 38 passed · pytest tests/test_us_rat_charges_taxes.py 27 passed / 3 skipped (unchanged)
# exceptions: PRICE-RANK MATCHING IS GONE FROM THIS FILE (2026-08-16, BR-RAT-067) — `_window_channels` deleted, the deletion left as a comment because four files cite BR-RAT-064 by name · rate-schedule status stays DERIVED (US-RAT-004 §5, no status column) but the DRAFT branch now has storage behind it — a dateless tariff_versions row (migration 0004) is the draft, excluded here from in-force resolution, from the version history list and from the plan-builder picker (BR-RAT-031) · B2 §2's EXCLUDE gist window constraint is still absent from the DB (never materialized by migration 0001; btree_gist not installed) — REPORTED, not resolved · history sort key `changed_at` maps to the stored `created_at` column (r5 #14 names no changed_at) · tax applies-to-service filtering happens in Python (applies_to_services is a JSON list per the models lane's array disposition) · DEF-441: six of the nine sort keys are DERIVED per card and cannot be an `order_by`, so they sort over the built list. The trap this closed is worth naming — `schedule_list` used to map any unrecognised sort key back to `name` (`{...}.get(params.sort, "name")`), so a sortable `Plans` header would have re-sorted by schedule name and reported success. The status sort's old one-pass `(status, name)` tuple also reversed the TIE-BREAK with the user's direction; it is now two stable passes, name ascending underneath, because the secondary sort is not the user's choice (IS-2).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


def base_charge_codes_among(codes: Sequence[str]) -> frozenset[str]:
    """🔒 `DEF-RAT-9327` — which of `codes` can price a BASE line on a bill.

    A code is a base code when it is ticked `is_base` (arm 2 of BR-RAT-1025) or
    a rate schedule NAMES it as its base (`tariff_versions.base_charge_code`,
    arm 1). Those are the two ways `billing.gather` resolves a base, and the
    base line is the only priced line that carries a charge code — so a
    discount scoped to NAMED codes can select nothing else. Read by
    `discount_services._refuse_named_codes_off_the_tariff` at approval. Any
    version of any schedule counts: the question is whether the code CAN be on
    a bill, not which version is in force today.
    """
    wanted = [str(code) for code in codes]
    if not wanted:
        return frozenset()
    tenant_id = core_tenancy.current_tenant_id()
    flagged = models.Charge.objects.filter(
        tenant_id=tenant_id, code__in=wanted, is_base=True
    ).values_list("code", flat=True)
    bound = models.TariffVersion.objects.filter(
        tenant_id=tenant_id, base_charge_code__code__in=wanted
    ).values_list("base_charge_code__code", flat=True)
    return frozenset(flagged) | frozenset(bound)


# ══════════════════════════════════════════════════════════════════════════
# CR-190-BRC10 · A PLAN'S MAIN CHARGES, FOR THE PLAN-CHANGE EMAIL
# ══════════════════════════════════════════════════════════════════════════
#: How a usage charge is STRUCTURED, in this read's own vocabulary. The words a
#: customer reads for each live in `apps/notifications/rate_summary.py`'s
#: catalogue, keyed by these codes, never here.
USAGE_FLAT = "flat"
USAGE_TIERED = "tiered"
USAGE_TIME_OF_DAY = "time_of_day"
USAGE_SEASONAL = "seasonal"


def _usage_floor(version: models.TariffVersion) -> dict[str, Any] | None:
    """`{unit_price, unit, structure}` — the LOWEST stored unit price of this
    version's usage charge and how it is structured, or None (no usage price:
    a percent-of-service schedule, or a version with no priced rows).

    PO ruling 2026-10-22 (decision log *"Plan-change email…"*): a tiered or
    time-of-day charge reads as *its lowest unit price* plus the word for its
    structure. Reads stored rows only; prices nothing (the 🔒 engine is not
    called and no figure is derived).
    """
    tenant_id = _tenant_id()
    unit = version.uom or None
    if version.model == "percent_of_service" and version.percent_basis != (
        percent_basis.PERCENT_BASIS_USAGE
    ):
        return None
    if version.model == "time_of_use":
        prices = [
            price
            for price in models.TimeOfUseWindow.objects.filter(
                tenant_id=tenant_id, tariff_version=version
            ).values_list("unit_price", flat=True)
            if price is not None
        ]
        if not prices:
            return None
        return {"unit_price": min(prices), "unit": unit, "structure": USAGE_TIME_OF_DAY}
    if version.model == "demand":
        demand = models.DemandRateConfig.objects.filter(
            tenant_id=tenant_id, tariff_version=version
        ).first()
        if demand is None or demand.energy_rate_per_kwh is None:
            return None
        return {"unit_price": demand.energy_rate_per_kwh, "unit": unit, "structure": USAGE_FLAT}
    if version.model == "capacity":
        capacity = models.CapacityRate.objects.filter(
            tenant_id=tenant_id, tariff_version=version
        ).first()
        if capacity is None or capacity.rate_per_unit is None:
            return None
        return {
            "unit_price": capacity.rate_per_unit,
            "unit": capacity.unit_label or unit,
            "structure": USAGE_FLAT,
        }
    prices = sorted(
        {
            price
            for price in models.RateTier.objects.filter(
                tenant_id=tenant_id, tariff_version=version
            ).values_list("unit_price", flat=True)
            if price is not None
        }
    )
    if not prices:
        return None
    if len(prices) == 1:
        structure = USAGE_FLAT
    elif version.model == "seasonal":
        structure = USAGE_SEASONAL
    else:
        structure = USAGE_TIERED
    return {"unit_price": prices[0], "unit": unit, "structure": structure}


def plan_charge_summary(
    plan_id: Any, *, on_date: date, customer_class: str | None = None
) -> dict[str, Any] | None:
    """`CR-190-BRC10` — a plan's MAIN CHARGES on a date, per service.

        -> {"plan_name": str, "services": [{
               "service_code", "service_name", "currency",
               "base_amount": Decimal | None,
               "usage": {"unit_price": Decimal, "unit": str | None,
                         "structure": "flat"|"tiered"|"time_of_day"|"seasonal"} | None,
           }]} | None

    PO 2026-10-22, verbatim: *"B. Main charges, one line each — Now: Residential
    Standard: base $12.00 a month, energy $0.0425 per kWh · From 10/31/2026:
    Ayush_Plan: base $14.00 a month, energy $0.0390 per kWh"*. Each figure comes
    from the plan's PUBLISHED rate schedule IN FORCE ON `on_date`
    (`in_force_version`, BR-RAT-007); no price, unit or word is typed here.

    * **base** — `base_charge_from_charge_code`, the live billing path (the
      chain `BR-RAT-1025` rules: plan → rate schedule → charge code), at the
      account's customer class and on the date. A refusal (a per-size code with
      no size, two codes, no amount) or a schedule naming no base gives `None`:
      the line then states the usage charge alone, never a guessed base.
    * **usage** — `_usage_floor`: the lowest stored unit price and its structure.

    `None` for a plan this tenant does not hold (tenant-scoped, RLS FORCE).
    """
    plan = models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk=plan_id).first()
    if plan is None:
        return None
    services: list[dict[str, Any]] = []
    bound_rows = (
        models.PlanRateSchedule.objects.filter(tenant_id=_tenant_id(), rate_plan=plan)
        .select_related("tariff", "service")
        .order_by("service__sort", "service__code")
    )
    for bound in bound_rows:
        version = in_force_version(bound.tariff, on_date)
        if version is None:
            continue
        named = getattr(version, "base_charge_code", None)
        answer = base_charge_from_charge_code(
            bound.service.code,
            customer_class=customer_class,
            named_code=named.code if named is not None else None,
            on_date=on_date,
        )
        base = None if answer.get("refusal") else answer.get("amount")
        usage = _usage_floor(version)
        if base is None and usage is None:
            continue
        services.append(
            {
                "service_code": bound.service.code,
                "service_name": bound.service.name,
                "currency": version.currency,
                "base_amount": base,
                "usage": usage,
            }
        )
    return {"plan_name": plan.name, "services": services}
