# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (S49 three tabs, search + status filter) · US-AST-002
#           (row lands on the right tab) · US-AST-003 (delete-guard read) ·
#           US-AST-004 (S50 header + Overview, extended specs, Test-due chip) ·
#           US-AST-006 (Assignment history + Maintenance tabs) · US-AST-010
#           (S52 staged preview counts + per-row reasons)
#           Screens: S49, S50, S52, S15 (meters cell via the metering seam)
# Rules:    BR-AST-004 (tab partition by type) · BR-AST-005 (status filter
#           semantics; Unassigned = no current assignment; All includes
#           retired) · BR-AST-006 (row actions by state) · BR-AST-007 ("Test
#           due" DERIVED, never stored) · BR-AST-015 (register digits default
#           9) · BR-AST-016 (no money on any asset read) · BR-AST-017/018
#           (append-only history reads) · BR-AST-026 (internal uuid never the
#           user-facing number) · BR-AST-039 (billing chain) · BR-AST-041
#           (capability row: search/filters/default sort asset_no asc) ·
#           BR-AST-043 (meter_types / read_methods catalogs; read_method is a
#           catalog row, rendered by its code exactly as before) · BR-AST-044
#           (BOTH classifications on every row + the S50 header block; the
#           registry gains an f.meter_type filter per BR-SHL-011)
# Change:   CR-028 AST-W1 (B16 §4.8, 2026-08-22) — the registry row gains the
#           columns r10's three tabs draw: service · export_capacity_kw ·
#           warranty_end · next_test on every row, sub_count on meters rows
#           (the Role column's Master tag), last_read (DEF-592, metering seam)
#           + parent_premises on sub-meter rows. All read-only; no money.
# Change:   CR-028 AST-W5 (B16 §4.4–§4.6, §10 D3/D5/D6/D7 — 2026-08-22) —
#           stock_view (Inventory counts-&-costs, honest-null pricing) ·
#           lifecycle_view (certs due / warranty groups / age forecast + the
#           Asset value panel, NO GL sentence) · geo_view (markers for every
#           non-retired asset on a geocoded premises, no WO fact) · the
#           reserved `f.status=uninstalled` behavior-class filter (the
#           Inventory drill).
# Change:   CR-028 AST-W2 (B16 §5.1/§5.1b, 2026-08-22) — asset_detail gains
#           valuation (BR-AST-047, currency riding with the cost) · lifecycle
#           (age/life/cert-due/forecast) · linked_meter; rows gain
#           parent_asset_id + has_test_cadence; specs gain
#           allocation_share_pct; assignments/maintenance resolve actor NAMES
#           (T6, via the audit actor_names read); maintenance rows carry cost
#           + maintenance_lifetime_cost; asset_reads serves the S50 Reads tab
#           (DEF-475 closed) with BR-AST-029's per-date fold. Still no GL
#           sentence anywhere (§10-D3).
# Tests:    06-backend/tests/test_us_ast_001_003_registry.py ·
#           test_us_ast_004_006_detail.py · test_us_ast_010_import.py
# Impacts:  apps/assets/api.py · apps/metering/selectors.py (S15 meters cell +
#           latest_read_for_asset, the DEF-592 seam)
# ───────────────────────────────────────────────────────
"""assets read path (LAW 0: api thin → services sole writer → selectors read).

Tenant-filtered at the app layer AND backed by RLS on Postgres. No money is
ever rendered here (BR-AST-016/025) — quantities only, each with its explicit
unit (CLAUDE.md rule 3). "Test due" and the row-action set are COMPUTED at
read time; neither is stored (BR-AST-007/006).
"""

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from django.db.models import (
    Count,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    QuerySet,
    Sum,
    Value,
)
from django.db.models.functions import (
    Coalesce,
    ExtractDay,
    ExtractMonth,
    ExtractYear,
    TruncDate,
)

from apps.assets import models, seams
from core import batch_reads
from core import errors
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.pagination import filter_values

#: How many of a run's issued numbers the rehearsal PRINTS. The count and the
#: last number are always exact; this bounds the list so a 9,881-row rehearsal
#: does not ship 9,881 strings to a screen that shows a sentence.
PREVIEW_NUMBERS_SHOWN = 5

# BR-AST-041 capability row: default sort asset_no A→Z, stable secondary by id.
ASSET_SORTS = {
    "asset_no": "asset_no",
    "type": "type__name",
    "installed": "install_date",
    "status": "status__name",
    "parent": "parent_asset__asset_no",
    # `DEF-AST-10178` — the age's START date, never `install_date` alone: a
    # spare bought and never installed ages from its purchase, and a record
    # with neither from the day it was entered. Annotated in `asset_list`
    # (`_age_start_expr`); ascending is OLDEST first, the direction the
    # Premises/Units `created` sort takes (`DEF-MET-10164`).
    "age": "age_start_on",
}
ASSET_DEFAULT_SORT = "asset_no"

#: Where an asset's age counts from (`DEF-AST-10178`, PO 2026-10-17): the
#: install date, else the purchase date, else the day the record was entered.
#: A CODE — the screen turns `purchase` / `record` into its small note.
AGE_FROM_INSTALL = "install"
AGE_FROM_PURCHASE = "purchase"
AGE_FROM_RECORD = "record"
TERMINAL = "terminal"
AVAILABLE = "available"
IN_SERVICE = "in_service"
OUT_OF_SERVICE = "out_of_service"

# DEF-MET-4101: an ISO instant, as `read_at.isoformat()` writes one. Used to
# decide whether a served read date can safely be reduced to its calendar day.
_ISO_INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


#: The biggest id list this module will put inside one `IN (...)`.
#:
#: ⚠ **A CEILING RATHER THAN A TUNING KNOB, AND IT IS `DEF-5744`'S LESSON ONE
#: FUNCTION ALONG.** An `IN` clause holding forty thousand literals is still
#: exactly ONE query, so no query count can ever see it — it surfaces as
#: SQLite's 32,766-variable limit or PostgreSQL's 65,535, i.e. as the list
#: refusing to answer at all, which `NFR-5` calls a hard cap. `per` clamps to
#: 1,000 today (`core/pagination.py`), so the batches below are bounded well
#: under either limit and this is not a live breach; it is what stops the fix
#: from BECOMING one the day that vocabulary grows a bigger step.
_ID_CHUNK = 900


def _chunked(values: Any, size: int = _ID_CHUNK) -> Any:
    """`values` in runs of at most `size`, in the order given."""
    items = list(values)
    for start in range(0, len(items), size):
        yield items[start : start + size]


class _PageReads:
    """Every CROSS-ROW fact one page of registry rows needs, resolved for the
    WHOLE page before a single row is shaped (`DEF-5745`).

    ⚠ **WHY THIS IS A BUNDLE PASSED INTO `asset_dict` RATHER THAN A REWRITE OF
    IT.** `asset_dict` is not only the list row: `services.py` calls it for the
    `before` and `after` of every audited write, and `asset_detail` builds the
    S50 header on top of it — sixteen single-row call sites. The lane that filed
    this defect named that as the reason not to touch it (*"it changes
    `asset_dict`'s contract and every consumer of a registry row"*). So the
    contract does not move: `asset_dict(asset)` costs and answers exactly what
    it did, and `asset_dict(asset, page=<these reads>)` answers the same thing
    out of dictionaries already in memory.
    `tests/test_def5745_registry_row_batching.py` pins both halves — the key set
    per tab as literals, and the VALUES key-for-key against the single-row path,
    which is the pin that cannot be edited into agreement.

    The five reads, and the per-row cost each one replaces:

      * `seats` — the CURRENT assignment per asset. One query (chunked), and
        exact rather than merely equivalent: `asset_assignments` carries
        `uq_asset_assignments_current` (`BR-AST-017`, UNIQUE on `asset` WHERE
        `to_date IS NULL`), so *"the first current row"* and *"the current row"*
        are the same row and the batch cannot pick a different one than
        `.first()` would have.
      * `units` — `seams.unit_refs`, the label and the premises address behind
        each seat. One query.
      * `services` — `seams.service_codes_for_points`, which metering answers in
        TWO for the whole set (the points, then the catalogue) instead of two
        per point.
      * `sub_counts` — the Role column's Master tag, one grouped `COUNT(*)`
        instead of one `COUNT(*)` per meters row.
      * `reads` — `seams.latest_reads_for_assets`, already batched by `CR-089`
        wave C for the meters and still paid per row on the sub-meters.

    ⚠ **THE SEAT MAP COVERS THE PAGE'S MASTERS TOO, NOT ONLY ITS OWN ROWS.** A
    sub-meter's Parent/master cell walks the PARENT's current seat to its
    premises (`_parent_premises`), which is two further reads per sub-meter row
    — the register's *"five per row"* is the meters figure; the sub-meter row
    pays seven. Both are answered out of the one map.
    """

    __slots__ = ("seats", "units", "services", "sub_counts", "reads", "tz")

    def __init__(
        self,
        seats: dict[str, models.AssetAssignment],
        units: dict[str, dict[str, Any]],
        services: dict[str, str | None],
        sub_counts: dict[str, int],
        reads: dict[str, dict[str, Any]],
        tz: Any = None,
    ) -> None:
        self.seats = seats
        self.units = units
        self.services = services
        self.sub_counts = sub_counts
        self.reads = reads
        # `DEF-AST-10178` — the tenant's clock, read ONCE for the page and only
        # when a row on it ages from its record date (`_age_start`).
        self.tz = tz


def _page_reads(rows: list[models.Asset]) -> _PageReads:
    """Build the bundle above for one page.

    ⚠ **TENANT SCOPE COMES FROM THE ROWS, NOT FROM THE SESSION (hard rule 1).**
    Every per-row read this replaces filtered on `asset.tenant_id`; taking
    `_tenant_id()` instead would be a different predicate, and on the day a
    caller shapes rows it fetched under another context it would be a WIDER one.
    The page is always one tenant, so this is one value — it is written as a set
    so that it cannot silently become a cross-tenant queryset if it ever is not.
    """
    tenant_ids = {row.tenant_id for row in rows}
    asset_ids = [row.id for row in rows]
    # The masters a sub-meter row names, so `_parent_premises` reads no further.
    parent_ids = [row.parent_asset_id for row in rows if row.parent_asset_id]
    seats: dict[str, models.AssetAssignment] = {}
    for chunk in _chunked(sorted({*asset_ids, *parent_ids})):
        for seat in models.AssetAssignment.objects.filter(
            tenant_id__in=tenant_ids, asset_id__in=chunk, to_date__isnull=True
        ):
            seats[str(seat.asset_id)] = seat

    units: dict[str, dict[str, Any]] = {}
    unit_ids = {str(seat.unit_id) for seat in seats.values() if seat.unit_id}
    for chunk in _chunked(sorted(unit_ids)):
        units.update(seams.unit_refs(chunk))

    services: dict[str, str | None] = {}
    point_ids = {str(row.service_point_id) for row in rows if row.service_point_id}
    for chunk in _chunked(sorted(point_ids)):
        services.update(seams.service_codes_for_points(chunk))

    # Only the meters tab draws the Master tag, so only meters are counted —
    # the same scoping `_tab_columns` has always had, applied to the page.
    sub_counts: dict[str, int] = {}
    masters = sorted({row.id for row in rows if row.type.category == "meters"})
    for chunk in _chunked(masters):
        for parent_id, total in (
            models.Asset.objects.filter(tenant_id__in=tenant_ids, parent_asset_id__in=chunk)
            # ⚠ `.order_by()` CLEARS the ordering before the GROUP BY. `Asset`
            # declares no `Meta.ordering` today, so this changes nothing today —
            # it is here because the day somebody adds one, Django appends that
            # column to the GROUP BY and this read starts returning a row PER
            # ORDERING VALUE instead of one per parent. The Master tag would
            # then undercount silently, with every test green.
            .order_by()
            .values_list("parent_asset_id")
            .annotate(total=Count("id"))
        ):
            sub_counts[str(parent_id)] = total

    reads: dict[str, dict[str, Any]] = {}
    readable = [row.id for row in rows if row.type.category in ("meters", "sub_meters")]
    for chunk in _chunked(sorted(readable)):
        reads.update(seams.latest_reads_for_assets(chunk))
    # Only a row with neither an install nor a purchase date needs the clock.
    tz = (
        seams.tenant_timezone()
        if any(row.install_date is None and row.purchase_date is None for row in rows)
        else None
    )
    return _PageReads(seats, units, services, sub_counts, reads, tz)


def _age_start(asset: models.Asset, page: _PageReads | None = None) -> tuple[date, str]:
    """Where this asset's AGE counts from, and which date that was
    (`DEF-AST-10178`, PO ruling 2026-10-17 — *"this is all corect"*).

    Install date → else purchase date → else the day the record was entered,
    read on the TENANT's clock (BR-TEN-081): `created_at` is a stamp, and an
    evening entry in Chicago is already tomorrow in UTC. The END of the age is
    not decided here — the row serves `retire_date`, and the screen subtracts
    from the tenant's today, so the server never caches a day that rolls over.
    """
    if asset.install_date is not None:
        return asset.install_date, AGE_FROM_INSTALL
    if asset.purchase_date is not None:
        return asset.purchase_date, AGE_FROM_PURCHASE
    tz = page.tz if page is not None and page.tz is not None else seams.tenant_timezone()
    return asset.created_at.astimezone(tz).date(), AGE_FROM_RECORD


def _age_start_expr() -> Any:
    """`_age_start` in SQL, for the `age` sort — the SAME three-way fallback,
    with `created_at` truncated to a day on the tenant's clock."""
    return Coalesce(
        "install_date",
        "purchase_date",
        TruncDate("created_at", tzinfo=seams.tenant_timezone()),
    )


def age_parts(start: date, end: date) -> tuple[int, int, int]:
    """Whole calendar years, months and days from `start` to `end` — the same
    arithmetic the screen's shared age helper uses, for the download, which
    has no screen to do it. Months are added with `add_months`, so 31 January
    plus one month lands on the last day of February, as everywhere else here."""
    if end < start:
        return 0, 0, 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if add_months(start, months) > end:
        months -= 1
    days = (end - add_months(start, months)).days
    return months // 12, months % 12, days


def _current_assignment(
    asset: models.Asset, page: _PageReads | None = None
) -> models.AssetAssignment | None:
    if page is not None:
        return page.seats.get(str(asset.id))
    return models.AssetAssignment.objects.filter(
        tenant_id=asset.tenant_id, asset=asset, to_date__isnull=True
    ).first()


def add_months(start: date, months: int) -> date:
    """Calendar month addition, clamped to the target month's length — the ONE
    month-arithmetic both the BR-AST-007 derivation and the CR-028 AST-W4
    next-due roll use, so the two can never disagree about what "+12 months"
    lands on."""
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    lengths = [31, 29 if _leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(start.day, lengths[month - 1]))


def _interval_due_date(asset: models.Asset) -> date | None:
    """last_test_date + test_interval_months, or None when either is absent.
    The one derivation both BR-AST-007's chip and the Next-test column read."""
    if not asset.last_test_date or not asset.test_interval_months:
        return None
    return add_months(asset.last_test_date, int(asset.test_interval_months))


def test_due(asset: models.Asset, *, today: date | None = None) -> bool:
    """BR-AST-007: a DERIVED display state — last_test_date +
    test_interval_months elapsed. The stored status never changes."""
    due_on = _interval_due_date(asset)
    if due_on is None:
        return False
    return (today or seams.tenant_today()) >= due_on


#: The whole-month lengths `add_months` clamps to. Named once so the SQL
#: predicate below and the Python derivation above cannot drift apart.
_MONTH_LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _days_in_month(when: date) -> int:
    if when.month == 2 and _leap(when.year):
        return 29
    return _MONTH_LENGTHS[when.month - 1]


def test_due_q(when: date) -> tuple[dict[str, Any], Q]:
    """`test_due()` written as SQL — the annotations it needs and the predicate,
    so a caller can NARROW A QUERYSET instead of filtering a materialised list.

    ⚠ **WHY THIS IS ARITHMETIC AND NOT A DATE FUNCTION (`DEF-MET-4962`).**
    `add_months` clamps the day to the target month's length, and no portable
    ORM expression does that — a `timedelta` of 30 days is a different answer
    and `EXTRACT`/`INTERVAL` spell it differently on Postgres and on the
    SQLite the suite runs (hard-won law 14's shape: the naive version would be
    green on every machine and wrong on the one that matters). So the
    comparison is done in whole months, which both databases can do:

        due = add_months(last_test_date, n)   ⟹   today >= due
        ⟺  elapsed > n  OR  (elapsed == n AND today.day >= min(d.day, dim))

    where `elapsed` is the CALENDAR month difference and `dim` is the length of
    today's month. `today.day >= dim` is only ever true on the last day of the
    month, so that half collapses to a constant the caller already knows — and
    the surviving clause is a plain comparison on the stored day.

    ⚠ **IT IS NOT ASSUMED TO AGREE WITH `test_due()` — IT IS TESTED AGAINST IT**
    (`tests/test_cr092_registry_paging.py::test_sql_test_due_matches_python`,
    which walks every asset in the fixture and compares the two answers row by
    row). A predicate that silently diverged from the derivation would filter
    the wrong rows with every check green, which is the failure this whole
    module keeps having.
    """
    annotations: dict[str, Any] = {
        "_td_months_elapsed": ExpressionWrapper(
            (Value(when.year) - ExtractYear("last_test_date")) * Value(12)
            + (Value(when.month) - ExtractMonth("last_test_date")),
            output_field=IntegerField(),
        ),
        "_td_recorded_day": ExtractDay("last_test_date"),
    }
    # `_interval_due_date` returns None when EITHER is absent, and a 0-month
    # cadence is falsy there too — so it is "no cadence", never "due at once".
    has_cadence = Q(last_test_date__isnull=False) & Q(test_interval_months__gt=0)
    on_the_due_month = Q(_td_months_elapsed=F("test_interval_months"))
    if when.day >= _days_in_month(when):
        # The last day of the month clears every clamped day at once.
        on_the_due_month &= Q()
    else:
        on_the_due_month &= Q(_td_recorded_day__lte=when.day)
    predicate = has_cadence & (
        Q(_td_months_elapsed__gt=F("test_interval_months")) | on_the_due_month
    )
    return annotations, predicate


def _aged_q(when: date, *, months: int) -> tuple[dict[str, Any], Q]:
    """`add_months(purchase_date, months) <= when`, written as SQL.

    `CR-092` wave C lane 3. The Inventory tab's *aged over 12 months* KPI was a
    Python loop over every uninstalled asset in the tenant; this is the same
    comparison as a predicate so the figure is a `COUNT(*)`.

    ⚠ **IT IS THE SAME CLAMPED-MONTH PROBLEM `test_due_q` SOLVES AND IT IS
    SPELLED THE SAME WAY ON PURPOSE.** `add_months` clamps the day to the target
    month's length and no portable ORM expression does; a `timedelta` of 365 days
    is a different answer, and `INTERVAL` differs between PostgreSQL and the
    SQLite the suite runs on — which is hard-won law 14's exact shape, where the
    naive version is green on every machine and wrong on the one that matters.
    So the comparison is done in whole months:

        aged  ⟺  elapsed > months
              OR (elapsed == months AND when.day >= min(purchase.day, dim))

    and `when.day >= dim` is only ever true on the last day of a month, which
    collapses that half to a constant the caller already knows.

    ⚠ **AND IT IS NOT ASSUMED TO AGREE WITH THE PYTHON — IT IS TESTED AGAINST
    IT**, row by row across a year of simulated dates, in
    `tests/test_cr092_asset_paging.py::test_sql_aged_matches_python`. A
    predicate that silently diverged would count the wrong assets with every
    check green, which is how this module keeps failing.
    """
    annotations: dict[str, Any] = {
        "_ag_months_elapsed": ExpressionWrapper(
            (Value(when.year) - ExtractYear("purchase_date")) * Value(12)
            + (Value(when.month) - ExtractMonth("purchase_date")),
            output_field=IntegerField(),
        ),
        "_ag_recorded_day": ExtractDay("purchase_date"),
    }
    on_the_month = Q(_ag_months_elapsed=Value(months))
    if when.day < _days_in_month(when):
        on_the_month &= Q(_ag_recorded_day__lte=when.day)
    predicate = Q(purchase_date__isnull=False) & (
        Q(_ag_months_elapsed__gt=Value(months)) | on_the_month
    )
    return annotations, predicate


def next_test_date(asset: models.Asset) -> str | None:
    """CR-028 AST-W1: the registry's Next-test column. The EXPLICIT
    certification_due wins when captured (the AST-W2 column, fed by the
    CERT_DUE import field); otherwise the BR-AST-007 derivation. None means
    "no test scheduled or derivable" and renders as the quiet dash — never
    an invented date."""
    if asset.certification_due:
        return asset.certification_due.isoformat()
    due_on = _interval_due_date(asset)
    return due_on.isoformat() if due_on else None


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


#: Money serves at its STORED 4-dp shape; percentages at 6 (hard rule 2 —
#: display trims to 2 on the screen, never here).
MONEY_QUANTUM = Decimal("0.0001")
# Hard rule 2: money DISPLAYS at 2 dp. `BR-WRK-051`'s "sum of the rounded
# displayed lines" needs that quantum as a value, not only as a format.
_DISPLAY_CENT = Decimal("0.01")
PCT_QUANTUM = Decimal("0.000001")


def _money_str(value: Decimal | None) -> str | None:
    return str(value.quantize(MONEY_QUANTUM)) if value is not None else None


def _months_between(start: date, end: date) -> int:
    """Whole months elapsed — the Lifecycle panel's Age ('2 yrs 5 mo')."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def asset_book_value(asset: models.Asset, *, as_of: date | None = None) -> dict[str, Any] | None:
    """CR-028 AST-W4 (§10-D3/D4 · BR-AST-047): straight-line book value — a
    COMPUTATION and nothing else. It posts no journal line, names no GL
    account, and nothing in this module imports the ledger (hard rule 5;
    tests/test_cr028_valuation.py asserts the absence).

    The formula, stated so the pinned figures are re-derivable:

        elapsed  = whole months from (install_date, else purchase_date) to
                   as_of — the SAME age base the Lifecycle panel uses
                   (B16 §5.1b: never-installed stock ages from purchase),
                   capped at the asset's whole life
        accum    = purchase_cost × elapsed / (expected_life_years × 12),
                   quantized 4 dp HALF-UP (rule 2 / B4's display rounding)
        book     = purchase_cost − accum   (never negative — the cap above)

    Returns None when no purchase cost or no expected life is recorded — the
    honest "no purchase cost recorded" state, never a fabricated $0.00.

    ⚠ RATIFIED-FIGURE VERDICT: r10's AST-08 draws $19.83/$144.17 for
    $164.00 · 20 yrs · Mar 12 2024 → Aug 16 2026. This arithmetic gives
    $19.8167/$144.1833 (29/240ths of $164) — one display cent apart. The
    delta is REPORTED (test_cr028_valuation.py module docstring), the formula
    is not bent to meet a figure no month arithmetic produces.

    `depreciation_method` is served as stored (nullable): only straight-line
    is computed here whatever the label says — a second method is a new rule,
    not a branch this function invents (BR-AST-047: method OPTIONAL)."""
    cost = asset.purchase_cost
    life_years = asset.expected_life_years
    if cost is None or not life_years:
        return None
    when = as_of or seams.tenant_today()
    base = asset.install_date or asset.purchase_date
    age_months = _months_between(base, when) if base else 0
    life_months = int(life_years) * 12
    elapsed = min(age_months, life_months)
    accumulated = (cost * Decimal(elapsed) / Decimal(life_months)).quantize(
        MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )
    return {
        "purchase_cost": str(cost.quantize(MONEY_QUANTUM)),
        "age_months": age_months,
        "life_months": life_months,
        "accumulated_depreciation": str(accumulated),
        "book_value": str((cost - accumulated).quantize(MONEY_QUANTUM)),
        "depreciation_method": asset.depreciation_method,
    }


def row_actions(asset: models.Asset) -> list[str]:
    """BR-AST-006: the state's action set. UI gating is convenience — the
    services enforce the same law server-side (A4/BR-SHL-025)."""
    behavior = asset.status.behavior_class
    if behavior == TERMINAL:
        return ["view"]
    if behavior == AVAILABLE:
        return ["assign", "edit", "delete"]
    if behavior == "out_of_service":
        return ["view", "log_repair", "reassign", "retire"]
    return ["view", "edit", "reassign", "log_repair", "retire"]


def _parent_premises(asset: models.Asset, page: _PageReads | None = None) -> str | None:
    """The master's premises address, for r10's "Parent / master" cell
    (CR-028 AST-W1 · B16 §4.2). Read through the same metering seam as the
    row's own assignment — never a cross-module join.

    ⚠ **THIS IS THE SIXTH AND SEVENTH READ A SUB-METER ROW PAYS** — the MASTER's
    seat and the master's unit, on top of the row's own five (`DEF-5745`). Both
    come out of `page` when the caller has a page, which is why `_page_reads`
    puts the page's parents into the seat map as well as its own rows."""
    if not asset.parent_asset_id:
        return None
    current = _current_assignment(asset.parent_asset, page)
    if current is None:
        return None
    if page is not None:
        return (page.units.get(str(current.unit_id)) or {}).get("premise_address")
    unit = seams.unit_ref(current.unit_id) or {}
    return unit.get("premise_address")


def _tab_columns(asset: models.Asset, page: _PageReads | None = None) -> dict[str, Any]:
    """CR-028 AST-W1 (B16 §4.1–§4.3): the per-tab facts r10's column sets need
    beyond the base row. Scoped by category so a meters page does not pay for
    sub-meter seam reads and vice versa.

    ⚠ **A MASTER WITH NO CHILDREN COUNTS `0` ON BOTH PATHS AND MUST.** `.count()`
    answers 0; a grouped `COUNT(*)` simply has no row for that parent, so the
    batched form defaults to 0 rather than to `None` — the Role column's Master
    tag is a MEASUREMENT here, and `null` would read as *nobody asked*."""
    category = asset.type.category
    if category == "meters":
        if page is not None:
            return {"sub_count": page.sub_counts.get(str(asset.id), 0)}
        return {
            # The Role column's Master tag — the SERVED child count.
            "sub_count": models.Asset.objects.filter(
                tenant_id=asset.tenant_id, parent_asset=asset
            ).count()
        }
    if category == "sub_meters":
        return {
            # DEF-592: metering's last-read summary, through the seam (RO).
            # `latest_reads_for_assets` publishes `latest_read_for_asset`'s own
            # shape and omits the assets with no committed read, so `.get` is
            # the singular's `None` — the quiet dash, never a zero (DEF-079).
            "last_read": (
                page.reads.get(str(asset.id))
                if page is not None
                else seams.latest_read_for_asset(asset.id)
            ),
            "parent_premises": _parent_premises(asset, page),
        }
    return {}


def asset_dict(asset: models.Asset, page: _PageReads | None = None) -> dict[str, Any]:
    """One registry row. The internal uuid is the `id` the API addresses, and
    it is NEVER the user-facing number — that is `asset_no` (BR-AST-026).

    ⚠ **`page` IS OPTIONAL AND ITS ABSENCE IS THE UNCHANGED CONTRACT
    (`DEF-5745`).** Called with one argument — which is what all sixteen
    single-row call sites do, every audited `before`/`after` in `services.py`
    and the S50 header among them — this function reads and answers exactly what
    it read and answered before. Called with a `_PageReads` it answers the SAME
    ROW out of dictionaries the caller already holds, and the five round trips
    per row become five for the whole page. The equality of the two paths is not
    an argument, it is a test: `test_def5745_registry_row_batching.py::
    test_a_page_row_says_exactly_what_the_single_row_read_says` recomputes both
    sides and compares them key for key, so neither side can drift unnoticed.
    """
    current = _current_assignment(asset, page)
    if current is None:
        unit = None
    elif page is not None:
        unit = page.units.get(str(current.unit_id))
    else:
        unit = seams.unit_ref(current.unit_id)
    age_start, age_source = _age_start(asset, page)
    return {
        "id": str(asset.id),
        "asset_no": asset.asset_no,
        # `CR-161-BRC10` W3 · `DEF-AST-9171` — the tenant's own answers, for
        # Asset detail, Edit asset and the Assets list column. A column already
        # on the row, so the page path and the single-row path agree for free.
        "custom_data": dict(asset.custom_data or {}),
        "serial_no": asset.serial_no,
        # BR-AST-049 — the utility's OWN legacy reference. Served beside the
        # other two identifiers so that a screen can print the number the
        # operator's old system used; it is the only one of the three that
        # WE did not issue and that the manufacturer did not stamp.
        "external_ref": asset.external_ref,
        "type": asset.type.code,
        "type_name": asset.type.name,
        "tab": asset.type.category,  # BR-AST-004: exactly one tab per asset
        "status": asset.status.code,
        "status_name": asset.status.name,
        "behavior_class": asset.status.behavior_class,
        # BR-AST-044: the SECOND classification, beside `type` and read_method.
        # Null on non-measuring assets and on every row that predates the rule.
        "meter_type": asset.meter_type.code if asset.meter_type_id else None,
        "meter_type_name": asset.meter_type.name if asset.meter_type_id else None,
        "read_method": asset.read_method.code if asset.read_method_id else None,
        "read_method_name": asset.read_method.name if asset.read_method_id else None,
        "multiplier": str(asset.multiplier),
        # BR-AST-500 (DEF-514): `service_size_classes.code`, or None where
        # nobody has recorded one. NULL is a real answer — "this connection's
        # size is not recorded", not "this connection has no size" — and the
        # bill run refuses BY NAME rather than picking the every-size ladder.
        "size_class": asset.size_class,
        "unit": asset.unit,  # explicit UoM, always (CLAUDE.md rule 3)
        "net_metering": asset.net_metering,
        "manufacturer": asset.manufacturer,
        "model": asset.model,
        "install_date": asset.install_date.isoformat() if asset.install_date else None,
        "parent_asset_no": asset.parent_asset.asset_no if asset.parent_asset_id else None,
        # CR-028 AST-W2 (B16 §5.1b): the Parent/master cell is a LINK, so the
        # addressing id travels beside the display number (BR-AST-026 — the id
        # is never DISPLAYED, it only addresses the href).
        "parent_asset_id": str(asset.parent_asset_id) if asset.parent_asset_id else None,
        # ...and a device with a test cadence relabels Log repair → "Log test"
        # (B16 §5.1b (A)); the cadence is either an interval or an explicit due.
        "has_test_cadence": bool(asset.test_interval_months or asset.certification_due),
        "service_point_id": str(asset.service_point_id) if asset.service_point_id else None,
        "assigned_unit_id": str(current.unit_id) if current is not None else None,
        # ── `On since` — WHEN THIS THING ARRIVED AT THIS UNIT (`DEF-MET-5861`)
        #
        # ⚠ **THIS IS NOT `install_date` AND THE TWO MUST NOT BE COLLAPSED.**
        # `install_date` is when the physical device was INSTALLED — it is the
        # depreciation age base (`_months_between(a.install_date or …)`), the
        # registry's `Installed` column and the floor the retire wizard bounds
        # against. `from_date` is when the asset ARRIVED AT THE UNIT IT IS ON
        # NOW. A meter moved between units has ONE installation and SEVERAL
        # arrivals, so a column headed `On since` that reads `install_date`
        # answers a different question and, for anything assigned from stock,
        # answers nothing at all: a shelf spare carries no `install_date`
        # (`_validate_asset` requires one only when a unit is given), so the
        # unit's Assets tab drew a dash on every meter a clerk assigned.
        #
        # The unit tab's column is `On since` BY NAME — the blueprint's §14
        # lists `Installed` among the drawn ABSENCES and `On since` as the
        # drawn date column — so the arrival date is what it must show.
        # `AssetFlowPages` reached the same conclusion for the reassign floor
        # and said so: *"`install_date` WOULD HAVE BEEN THE WRONG BOUND …
        # an assignment can start well after installation"*.
        #
        # Null exactly when `assigned` is false, and costs no query: `current`
        # is already read above, on both the single-row and the `_PageReads`
        # path, so a page of rows pays nothing for it.
        "assigned_from": current.from_date.isoformat() if current is not None else None,
        "assigned_to": (unit or {}).get("label") if unit else None,
        "assigned_address": (unit or {}).get("premise_address") if unit else None,
        "assigned": current is not None,
        "test_due": test_due(asset),  # BR-AST-007 derived chip
        "retire_date": asset.retire_date.isoformat() if asset.retire_date else None,
        # ── AGE (`DEF-AST-10178`) — where it starts, which date that was, and
        # where it stops. The screen subtracts from the tenant's today; a
        # retired asset stops ageing on its retire date.
        "age_start": age_start.isoformat(),
        "age_start_source": age_source,
        "age_end": asset.retire_date.isoformat() if asset.retire_date else None,
        "expected_life_years": asset.expected_life_years,
        "retire_reason": asset.retire_reason,
        "replaced_by": asset.replaced_by_asset.asset_no if asset.replaced_by_asset_id else None,
        "actions": row_actions(asset),
        # ── CR-028 AST-W1 (B16 §4.8) — the columns r10's three tabs draw ────
        # Service through the asset's service point (metering seam, RO).
        "service": _service_of(asset, page),
        # A capacity, never money (BR-AST-016/025) — decimal STRING or null.
        "export_capacity_kw": (
            str(asset.export_capacity_kw) if asset.export_capacity_kw is not None else None
        ),
        "warranty_end": asset.warranty_end.isoformat() if asset.warranty_end else None,
        "next_test": next_test_date(asset),
        **_tab_columns(asset, page),
    }


def asset_specs(asset: models.Asset) -> dict[str, Any]:
    """US-AST-004 Overview: the extended capture-only spec set (BR-AST-014)."""
    return {
        "form_class": asset.form_class,
        "register_digits": asset.register_digits,  # BR-AST-015: default 9
        "firmware_version": asset.firmware_version,
        "seal_no": asset.seal_no,
        "warranty_end": asset.warranty_end.isoformat() if asset.warranty_end else None,
        "last_test_date": asset.last_test_date.isoformat() if asset.last_test_date else None,
        "test_interval_months": asset.test_interval_months,
        "location_note": asset.location_note,
        "allocation_rule": asset.allocation_rule,
        "loss_tolerance_pct": (
            str(asset.loss_tolerance_pct) if asset.loss_tolerance_pct is not None else None
        ),
        # CR-028 AST-W2 (B16 §5.1b): the sub-meter's share of its master —
        # a PERCENTAGE at its stored 6 dp (rule 2). NULL means "metered, not
        # allocated" and is served as null, never a zero.
        "allocation_share_pct": (
            str(asset.allocation_share_pct.quantize(PCT_QUANTUM))
            if asset.allocation_share_pct is not None
            else None
        ),
    }


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def asset_row(asset_id: Any) -> models.Asset:
    if not _is_uuid(asset_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    row = (
        models.Asset.objects.filter(tenant_id=_tenant_id(), pk=asset_id)
        .select_related(
            "type", "status", "meter_type", "read_method", "parent_asset", "replaced_by_asset"
        )
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _base_qs() -> QuerySet:
    return models.Asset.objects.filter(tenant_id=_tenant_id()).select_related(
        "type", "status", "meter_type", "read_method", "parent_asset", "replaced_by_asset"
    )


#: `GET /assets/stock`, `/assets/lifecycle` and `/assets/geo` are COMPOSITE
#: payloads — a list beside KPIs, or three lists beside a value panel — so they
#: cannot answer in the `{count, next, previous, results}` envelope a plain list
#: uses without one of the lists stealing the four names from the others. They
#: carry a WINDOW instead: the list keeps its own key and gains a sibling saying
#: how much of it you are holding. That is the shape `GET /imports/{id}` has
#: served since `DEF-766` (`rejects_window`), for the same reason, and it is
#: ADDITIVE — a client that ignores the window reads exactly what it read before,
#: only bounded.
WINDOW_DEFAULT_PER = 50


def page_window(source: Any, *, page: Any = 1, per: Any = WINDOW_DEFAULT_PER) -> tuple[Any, dict]:
    """Slice `source` to one page and describe the window beside it.

    `source` may be a QuerySet — and SHOULD be, because then the `LIMIT` and
    `OFFSET` reach SQL, which is the whole of `NFR-3` and the whole of what
    `DEF-MET-4951` was about. A list is accepted for the one case where the rows
    are a GROUPING the database cannot do for us (stock's per-type roll-up);
    that case bounds the PAYLOAD and says so rather than pretending otherwise.

    `page` and `per` clamp and never raise (`BR-SHL-011`: a list URL can never
    4xx over its params). An out-of-range page clamps to the last one, so a
    client that keeps asking for page 9 of 3 gets page 3, not an error and not
    an empty list it would read as *nothing here*.
    """
    try:
        per_n = max(int(per), 1)
    except (TypeError, ValueError):
        per_n = WINDOW_DEFAULT_PER
    total = source.count() if hasattr(source, "count") and hasattr(source, "query") else len(source)
    pages = max(-(-total // per_n), 1)
    try:
        page_n = min(max(int(page), 1), pages)
    except (TypeError, ValueError):
        page_n = 1
    start = (page_n - 1) * per_n
    return source[start : start + per_n], {
        "total": total,
        "page": page_n,
        "per": per_n,
        "pages": pages,
    }


def asset_page_rows(rows: list[models.Asset]) -> list[dict[str, Any]]:
    """One PAGE of registry rows, with EVERY cross-row read batched for the page.

    ⚠ **THIS FUNCTION USED TO BATCH ONE FIELD OUT OF SIX AND THAT IS THE WHOLE
    OF `DEF-5745`.** `C4` below moved `last_read` up here, correctly and for the
    right reason, and left the other five per-row reads inside `asset_dict`
    where they had always been — the same objection applied to one field and not
    to its five neighbours. Measured on `brazosbend` at `a402238a2`: **201
    queries to shape 40 rows and 1,001 to shape 200**, five per served row on
    the meters tab and seven on the sub-meters. `_page_reads` resolves all six
    for the whole page and `asset_dict` then builds each row out of memory; the
    same two pages cost **6 and 6**.

    ⚠ **NO EXISTING NFR-3 CHECK COULD HAVE SEEN IT, AND BOTH OF THEM ARE
    CORRECT.** `test_cr092_registry_paging.py` measures `asset_list` — the
    QUERYSET — and asserts *the cost did not move with the population*, which is
    true here and always will be, because this cost follows the PAGE and never
    the tenant. `test_def5744_registry_subqueries.py` counts bind parameters,
    which is blind to it by construction. The case that can see it varies the
    PAGE SIZE over one population, and it is in
    `tests/test_def5745_registry_row_batching.py`.

    ⚠ **WHY THIS EXISTS RATHER THAN A LINE IN `_tab_columns` (`CR-089` wave C
    task `C4`, `PUJ-14`).** `last_read` has been served since `CR-028` AST-W1,
    for **sub-meters only**, through `_tab_columns` — one seam call per row.
    `C4` needs it on the METERS too, and a per-row call there would be one
    query per meter on a list that pages up to 200 of them; `DEF-324` is the
    standing objection to exactly that shape. `seams.latest_reads_for_assets`
    already answers the same question for many assets in ONE query — it was
    written for the map's popups for this reason — so the batched read moves up
    here, where the page is, and `asset_dict` stays a function of one row.

    ⚠ **THE SUB-METER ANSWER IS UNCHANGED, BY CONSTRUCTION.** `_tab_columns`
    still sets `last_read` for sub-meters — out of the page bundle since
    `DEF-5745` rather than one seam call per row, which is the same VALUE
    because `latest_reads_for_assets` publishes `latest_read_for_asset`'s own
    shape — and this only fills the key in where it is ABSENT — so a sub-meter row is byte-identical to what it was and no
    existing assertion moves. Meters and net meters are new; behind-the-meter
    rows are left WITHOUT the key, because a fire line or a trash cart has no
    register to read and `null` there would be indistinguishable from *a meter
    nobody has read yet*, which is a different and much worse sentence.
    """
    if not rows:
        return []
    page = _page_reads(rows)
    shaped = [asset_dict(row, page) for row in rows]
    # ── `size_class_name` — THE SIZE AS A CLERK READS IT (`CR-143-BRC07`) ───
    #
    # ⚠ **THE ROW ALREADY CARRIED THE SIZE AND NO SCREEN COULD DRAW IT.**
    # `asset_dict` serves `size_class` as a bare `service_size_classes.code`
    # (BR-AST-500) — `W-58`, `FL-2` — and B14 rule 32 keeps an internal code out
    # of clerk-facing copy, so the registry has never had a value it was allowed
    # to print. The tenant's own vocabulary is what names it, and the name is
    # also the only one of the two that carries a UNIT (`Water 5/8"`, not
    # `W-58`), which CLAUDE.md hard rule 3 asks of any dimension on screen.
    # The portal settled the identical question one module along and its
    # reasoning is reused rather than re-argued (`DEF-CWP-4848`).
    #
    # ⚠ **IT MATTERS ON FIRE AND ON WATER BECAUSE THE SIZE IS THE PRICE.**
    # A capacity service's size class PICKS the base charge and the count
    # multiplies it (CLAUDE.md's fire paragraph: one 6" line is `$60.00`, one 2"
    # line `$12.00`), so a clerk auditing a bill run against this list was being
    # asked to check an arithmetic whose first input the list did not show.
    #
    # ⚠ **ONE LOOKUP FOR THE WHOLE PAGE, AND ONLY WHEN A ROW NEEDS IT**
    # (`DEF-324`'s standing objection, and `DEF-5745`'s measurement of what a
    # per-row read costs here: 201 queries to shape 40 rows). A page whose every
    # size is NULL asks tenancy nothing at all.
    #
    # ⚠ **AN UNNAMED CODE IS LEFT `None`, NEVER FILLED WITH THE CODE.** The
    # fallback would be the breach. `size_class` itself stays on the row
    # untouched, because the walkthroughs, the import and the rate ladder all
    # key on the code — this key is what the SCREEN draws.
    if any(row.size_class for row in rows):
        names = seams.service_size_class_names()
    else:
        names = {}
    for row, payload in zip(rows, shaped, strict=True):
        if row.type.category in ("meters", "sub_meters") and "last_read" not in payload:
            payload["last_read"] = page.reads.get(str(row.id))
        payload["size_class_name"] = names.get(row.size_class or "") or None
    return shaped


def _current_seat_ids() -> QuerySet:
    """The tenant's CURRENT assignments, as a LAZY `values` queryset of
    `asset_id` — the subquery two filters on this screen both narrow by.

    ⚠ **IT RETURNS A QUERYSET SO THE IDS NEVER LEAVE THE DATABASE
    (`DEF-5744`).** `asset_list` used to wrap the same read in `list(...)`, so
    `exclude(id__in=…)` carried one uuid LITERAL per assigned asset: the
    statement grew 4,797 → 10,017 characters for 5 → 150 assigned assets,
    about 36 characters each. At the top of T5 (40,000, ruled 2026-09-06) that
    is roughly 1.4 MB of SQL and 40,000 bind parameters — **past SQLite's
    32,766-variable limit outright**, so the list would have stopped answering
    rather than merely answering slowly. That makes it an `NFR-5` cap as much
    as an `NFR-3` cost.

    ⚠ **AND NO QUERY COUNT CAN EVER SEE IT**, which is why it outlived the lane
    that fixed everything around it: an `IN` clause holding forty thousand
    literals is still exactly ONE query.
    `tests/test_cr092_registry_paging.py` measures queries, correctly, and is
    blind to this by construction. `tests/test_def5744_registry_subqueries.py`
    counts BIND PARAMETERS instead, which is the assertion that can.

    Named once because `f.status=unassigned` and `f.assigned=` are the same
    question asked twice, and two spellings of one predicate is how the two
    directions of a filter drift apart (the `CR-089` G2 fault, in reverse).
    """
    return models.AssetAssignment.objects.filter(
        tenant_id=_tenant_id(), to_date__isnull=True
    ).values("asset_id")


def asset_list(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> QuerySet[models.Asset]:
    """S49. Tab partition by type category (BR-AST-004); status semantics per
    BR-AST-005 — Unassigned = no CURRENT assignment row, All includes retired,
    default excludes the terminal stage. Filters AND-combine with search
    (IS-4); search covers asset_no · serial · manufacturer/model · the
    premises/unit address (BR-AST-041).

    ⚠ **RETURNS A QUERYSET, NOT A LIST (`DEF-MET-4951`).** It is lazy on
    purpose: `api.assets` hands it straight to `paginate_queryset`, so the
    page's `LIMIT`/`OFFSET` reaches SQL. Anything that materialises the WHOLE
    thing — `list(...)`, a `len()` — reads the entire match set, which is
    exactly what `NFR-3` forbids at the top of T5 (40,000). Every existing
    caller iterates it and none of them changes.

    ⚠ **AND LAZY MEANS THE SQL RUNS WHERE THE CALLER ITERATES, NOT WHERE THIS
    FUNCTION WAS CALLED — WHICH IS `DEF-2734`'S TRAP AND IT IS SILENT.** The
    tenant marker is a DATABASE SESSION setting (`app.tenant_id`), cleared the
    moment the request or the job's `tenant_context` exits. Iterate this
    queryset after that and the RLS policy's
    `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL,
    `tenant_id = NULL` is not TRUE, and **you get zero rows and no error.**
    Worse, the suite runs on SQLite, where RLS does not exist, so the broken
    version is green on every machine (hard-won law 14's shape).

    **So: iterate, slice or `list()` it INSIDE the context that opened it.**
    Today's three callers all do — `api.assets` inside the request, the export
    kernel inside the job, `seed_demo` and `sample_data` inside
    `tenant_context`. A future caller that wants to hand it further up the
    stack wants `core.tenancy.stream_within_tenant_context`, which exists for
    exactly this and says so."""
    filters = filters or {}
    qs = _base_qs()
    tab = filters.get("tab")
    if tab:
        qs = qs.filter(type__category=str(tab))
    if type_code := filters.get("type"):
        qs = qs.filter(type__code__iexact=str(type_code))
    if meter_type := filters.get("meter_type"):
        # BR-AST-044: the second classification is a first-class registry
        # filter (`f.meter_type=` per BR-SHL-011), AND-combined with the rest
        # exactly like `f.type`. "none" selects the rows carrying no meter
        # type — the honest way to find what still needs classifying, since
        # migration 0004 backfilled nothing.
        if str(meter_type).lower() == "none":
            qs = qs.filter(meter_type__isnull=True)
        else:
            qs = qs.filter(meter_type__code__iexact=str(meter_type))
    if size_class := filters.get("size_class"):
        # CR-089 G1 / BR-AST-500. `assets.size_class` is TEXT holding a
        # `service_size_classes.code` — never an id — so this is a plain
        # case-insensitive match, and `none` selects the rows where nobody has
        # recorded a size, exactly as `f.meter_type=none` does. Those two spell
        # the same absence and a clerk should not have to learn two words.
        if str(size_class).lower() == "none":
            qs = qs.filter(Q(size_class__isnull=True) | Q(size_class=""))
        else:
            qs = qs.filter(size_class__iexact=str(size_class))
    status = str(filters.get("status") or "").lower()
    if status in ("", "default"):
        qs = qs.exclude(status__behavior_class=TERMINAL)
    elif status == "unassigned":
        # BR-AST-005: no CURRENT assignment row, terminal stage excluded.
        # `DEF-5744` — the seat ids stay in the database as a subselect; the
        # `list(...)` this replaced sent one bind parameter per assigned asset.
        qs = qs.exclude(id__in=_current_seat_ids()).exclude(status__behavior_class=TERMINAL)
    elif status == "uninstalled":
        # CR-028 AST-W5 T1: the Inventory tab's drill ("count 2" → those two
        # rows). A RESERVED value beside "unassigned", keyed off the behavior
        # CLASS `available` (BR-AST-031's own instruction: filters key off the
        # class, never the label) — so the drill survives a tenant who renamed
        # or added stages, which a stage-code link would not.
        qs = qs.filter(status__behavior_class=AVAILABLE)
    elif status != "all":
        qs = qs.filter(status__code__iexact=status)
    if term := (q or "").strip():
        if len(term) >= 2:  # IS-3: server-side, min 2 chars
            matches = (
                Q(asset_no__icontains=term)
                | Q(serial_no__icontains=term)
                | Q(manufacturer__icontains=term)
                | Q(model__icontains=term)
                | Q(parent_asset__asset_no__icontains=term)
            )
            unit_ids = _unit_ids_matching_address(term)
            if unit_ids:
                # `DEF-5744`, the same fix on the address arm (`BR-AST-041`).
                # ⚠ **THE UNIT IDS ARE STILL A LIST AND THAT IS NOT THIS
                # MODULE'S TO CHANGE:** `_unit_ids_matching_address` crosses
                # into metering through a seam whose contract answers a `list`.
                # What stops being materialised here is the ASSET id set built
                # on top of them, which is the larger of the two — a unit holds
                # several assets, and a broad term matches many units.
                matches |= Q(
                    id__in=models.AssetAssignment.objects.filter(
                        tenant_id=_tenant_id(), to_date__isnull=True, unit_id__in=unit_ids
                    ).values("asset_id")
                )
            qs = qs.filter(matches)
    # ── The four filters that used to run in Python (`DEF-MET-4962` / `DEF-MET-4951`) ─
    #
    # ⚠ **EVERY ONE OF THESE WAS A LOOP OVER THE MATCH SET, NOT OVER THE PAGE.**
    # `assigned`, `test_due`, `premises_id` and `service` were applied to a
    # materialised `list(qs)`, three of them with a per-row query or seam call,
    # and the paginator then sliced that list — so no `LIMIT` and no `OFFSET`
    # ever reached SQL. Measured on `pine-hill` (110 meters in the tab) before
    # this change: unfiltered 1 query, `f.assigned=true` **111**,
    # `f.service=water` **209**, the two together **319** to return 53 rows.
    # Correct at T7 and 13× short of the top of T5 — the same shape
    # `DEF-PAY-4221` names on `GET /outstandings`.
    #
    # All four are expressible in SQL through FKs that are already in B2 §2's
    # reviewed cross-module set — `assets.service_point → metering.ServicePoint`
    # and `asset_assignments.unit → metering.Unit` — so this narrows the
    # queryset rather than buying a second read, and no new seam is needed.
    current = _current_seat_ids()
    if filters.get("assigned") in ("true", True):
        qs = qs.filter(id__in=current)
    elif filters.get("assigned") in ("false", False):
        # CR-089 G2. ⚠ **THIS FILTER ONLY EVER WORKED ONE WAY, WHICH IS A CHECK
        # THAT CANNOT FAIL WEARING A FILTER'S CLOTHES:** `f.assigned=false` was
        # accepted by the API, ignored here, and answered the FULL registry —
        # a caller asking for the unattached rows got every row and no error.
        # The unit's inventory picker needs the complement to stand BESIDE a
        # stage filter (`f.status=inventory`), which `status=unassigned` cannot
        # do because both would want the one `status` key.
        qs = qs.exclude(id__in=current)
    if filters.get("test_due") in ("true", True):
        annotations, predicate = test_due_q(seams.tenant_today())
        qs = qs.annotate(**annotations).filter(predicate)
    if premises_id := filters.get("premises_id"):
        # The asset's premises is the CURRENT assignment's unit's premises —
        # one walk (hard rule 8: nothing else declares an address), now as a
        # join instead of `_premises_of` once per row.
        qs = qs.filter(
            id__in=models.AssetAssignment.objects.filter(
                tenant_id=_tenant_id(), to_date__isnull=True, unit__premises_id=premises_id
            ).values("asset_id")
        )
    if unit_id := filters.get("unit_id"):
        # DEF-MET-8362 — the unit's own assets, by its CURRENT seat, as one
        # subselect. The unit Assets tab used to fetch the premises' first 200
        # rows and filter them in the browser, so any unit whose asset numbers
        # sorted past row 200 of its premises drew '—' in every registry
        # column. Tenant-scoped through `_tenant_id()` like the premises arm.
        qs = qs.filter(
            id__in=models.AssetAssignment.objects.filter(
                tenant_id=_tenant_id(), to_date__isnull=True, unit_id=unit_id
            ).values("asset_id")
        )
    if services := filter_values(filters.get("service")):  # OQ-306 — ANY of
        any_of = Q()
        for one in services:
            any_of |= Q(service_point__service__code__iexact=one)
        qs = qs.filter(any_of)
    field = ASSET_SORTS.get(sort or ASSET_DEFAULT_SORT, "asset_no")
    prefix = "-" if direction == "desc" else ""
    if field == "age_start_on":
        qs = qs.annotate(age_start_on=_age_start_expr())
    return qs.order_by(f"{prefix}{field}", "id")


def asset_kpis(tab: str, *, today: date | None = None) -> dict[str, Any] | None:
    """The Meters and Behind-the-meter KPI strips, SERVED (`DEF-MET-4953`).

    ⚠ **THIS REPLACES A COUNT THE BROWSER COULD ALMOST NEVER DO.** The strip
    was built from the rows on the page and `kpiRowsComplete` — correctly —
    refused to show a page's count as the utility's, so it showed a dash
    instead. The gate is right; what was missing is the read. Measured on
    `pine-hill` before this: `?tab=meters` renders **four em-dashes** under
    four headings on first load (110 meters, 50 to a page), and a filter alone
    is enough to dash them even when the whole filtered set is on screen.

    ⚠ **IT COUNTS THE TAB, NOT THE QUERY, AND THAT IS THE EXISTING MEANING
    RATHER THAN A NEW ONE.** *Meters in service* is a fact about the estate;
    the table below it is the question being asked. The client only ever
    showed these figures when there was NO search and NO filter, so the tab's
    own population IS what the cards have always meant — serving them keeps
    that meaning and drops the condition. Narrowing them with the filter would
    make *In inventory* and *Meters in service* mutually exclusive and at most
    one card non-zero, which is not a strip anybody drew.

    Constant cost: **three queries for Meters, one for Behind the meter**,
    whatever the tenant holds. The PO ruling of 2026-09-12 (*"a) Fix the
    figures"*) is what this is — the two tabs stay WORDLESS (D9, 2026-08-22).
    """
    if tab not in ("meters", "behind_the_meter"):
        return None
    when = today or seams.tenant_today()
    # The tab's own population under the DEFAULT status semantics — the exact
    # set `asset_list` answers with no search and no filter, which is the only
    # state the client ever rendered a figure in.
    qs = asset_list(filters={"tab": tab})
    if tab == "behind_the_meter":
        totals = qs.aggregate(
            devices=Count("id"),
            exporting=Count("id", filter=Q(export_capacity_kw__isnull=False)),
        )
        return {"devices": totals["devices"], "exporting": totals["exporting"]}
    annotations, due = test_due_q(when)
    totals = qs.annotate(**annotations).aggregate(
        in_service=Count("id", filter=Q(status__behavior_class=IN_SERVICE)),
        ami=Count(
            "id", filter=Q(status__behavior_class=IN_SERVICE, meter_type__code__iexact="ami")
        ),
        needs_repair=Count("id", filter=Q(status__behavior_class=OUT_OF_SERVICE)),
        in_inventory=Count("id", filter=Q(status__behavior_class=AVAILABLE)),
        past_certification=Count("id", filter=due),
    )
    # A master is a row in THIS tab carrying at least one sub (BR-AST-003), and
    # the sub population is the count of assets whose parent is in the tab —
    # the served form of the client's "sum of `sub_count` over the rows". Both
    # are their own query: folding a reverse join into the aggregate above
    # would fan each master out once per child and silently inflate the five
    # counts beside it.
    base = qs.order_by()
    return {
        "in_service": totals["in_service"],
        "masters": base.filter(sub_assets__isnull=False).distinct().count(),
        "subs": models.Asset.objects.filter(
            tenant_id=_tenant_id(), parent_asset__in=base
        ).count(),
        "ami_pct": (
            None if totals["in_service"] == 0 else round(100 * totals["ami"] / totals["in_service"])
        ),
        "needs_repair": totals["needs_repair"],
        "in_inventory": totals["in_inventory"],
        "past_certification": totals["past_certification"],
    }


# ── CR-089 G1 · the words a clerk is holding, read as filters ──────────────
#
# ⚠ **THE PROBLEM THIS SOLVES IS NOT "SEARCH IS WEAK", IT IS "SEARCH ASKS FOR
# THE ONE THING THE CLERK DOES NOT HAVE".** `q` covers asset_no · serial ·
# manufacturer · model · the assigned address. A meter sitting on a shelf has
# no address, and a person standing in the depot with it in their hand is
# holding a 5/8-inch water meter and NOT a number. The registry has always been
# able to answer *what kind · what size · what stage*; nothing let a person ASK
# it in words.
#
# ⚠ **THE VOCABULARY IS THE TENANT'S OWN, NEVER A LIST OF ENGLISH WORDS.**
# Every term below is a row a tenant can rename on Settings — the asset types,
# the meter classes, the lifecycle stages, the ratified size classes. A
# hardcoded synonym table would be this repo's own language exported to ten
# other catalogues, which is what B14 rule 35 forbids.
#
# ⚠ **SERVICE IS DELIBERATELY NOT ONE OF THE FAMILIES, AND THAT IS A FINDING
# RATHER THAN AN OMISSION.** An asset's service is resolved through its SERVICE
# POINT (`_service_of`), and a shelved asset has none — so `f.service` answers
# `None` for every row an inventory picker can ever show. Putting it in this
# vocabulary would emit a filter that CANNOT return a row, which is hard-won
# law 7's *incapable of passing* shape wearing the clothes of a feature. The
# service word still lands: a size class is named for its service (`W-58` is
# *Water 5/8"*), so `5/8 water` matches ONE size-class term on both words.
#: ⚠ **THE HYPHEN IS A SEPARATOR AND THE SLASH IS NOT, AND BOTH CHOICES WERE
#: MADE BY WATCHING THE RESOLVER GET IT WRONG.** With `-` kept, `CART-35`
#: was one token that `cart` prefix-matched, so typing *96 gallon cart*
#: answered **Trash 35-gallon cart** — more words giving a wronger answer, the
#: opposite of what this feature is for. Splitting on it makes `CART-96` the
#: pair {cart, 96}, which those words match exactly. The slash stays because
#: `5/8` is a size and not two numbers.
_TERM_SPLIT = re.compile(r"[^0-9a-z/\"'’.¼-¾⅐-⅞]+")
#: A typed token shorter than this never prefix-matches — "in" would otherwise
#: claim "Inventory", "In repair" and "Installed" at once.
_MIN_PREFIX = 3


def _term_tokens(text: str) -> list[str]:
    """Lowercase word tokens, with the punctuation a SIZE reads in kept.

    `5/8"` and `1½` are sizes, so `/`, `"` and the vulgar fractions survive the
    split; the quote and full stop are then trimmed from the ends so `5/8"` and
    `5/8` are one token. Everything else that separates words is a separator.
    """
    out: list[str] = []
    for raw in _TERM_SPLIT.split(str(text or "").lower()):
        token = raw.strip("\"'’./-")
        # A token with no letter or digit in it is punctuation that survived
        # the split — the `/` in *Container / Cart*, which is kept as a
        # character because `5/8` needs it and is not a word on its own.
        if token and any(char.isalnum() for char in token):
            out.append(token)
    return out


def _token_matches(typed: str, term: str) -> bool:
    """One typed token against one vocabulary token: equal, or a prefix of it.

    Prefix matching is what lets *invent* find *Inventory*; `_MIN_PREFIX` is
    what stops *in* claiming three stages at once.
    """
    if typed == term:
        return True
    return len(typed) >= _MIN_PREFIX and term.startswith(typed)


def _search_vocabulary() -> list[dict[str, Any]]:
    """Every term this tenant's own catalogues offer, with the filter it sets.

    Four families, each a table a tenant edits on Settings: asset types
    (`f.type`), meter classes (`f.meter_type`), lifecycle stages (`f.status`)
    and the ratified size classes (`f.size_class`).

    ⚠ **A TERM'S NAME AND ITS CODE ARE TWO WAYS IN, NOT ONE LONGER PHRASE.**
    The first draft put both into one token set, so `W-58` demanded *water*,
    *5/8* AND *w-58* together and `5/8 water` matched nothing at all. They are
    ALTERNATIVES: type the name or type the code, either finds the row.
    """
    tenant_id = _tenant_id()
    entries: list[dict[str, Any]] = []

    def add(family: str, key: str, code: str, label: str) -> None:
        alternatives: list[list[str]] = []
        for spelling in (label, code):
            tokens = sorted(set(_term_tokens(spelling)))
            if tokens and tokens not in alternatives:
                alternatives.append(tokens)
        if alternatives:
            entries.append(
                {
                    "family": family,
                    "key": key,
                    "value": code,
                    "label": label,
                    "alternatives": alternatives,
                }
            )

    for row in models.AssetType.objects.filter(tenant_id=tenant_id, active=True):
        add("type", "type", row.code, row.name)
    for row in models.MeterType.objects.filter(tenant_id=tenant_id, active=True):
        add("meter_type", "meter_type", row.code, row.name)
    for row in models.AssetLifecycleStage.objects.filter(tenant_id=tenant_id, active=True):
        add("status", "status", row.code, row.name)
    for code, label in seams.service_size_class_terms():
        add("size_class", "size_class", code, label)
    return entries


def resolve_search_terms(text: str) -> dict[str, Any]:
    """Read free text as registry filters, LONGEST TERM FIRST.

    Answers `{"filters": {...}, "chips": [...], "unmatched": [...]}`.

    ⚠ **THE CHIPS AND THE FILTERS ARE ONE OBJECT AND NOT TWO.** The sibling
    lesson of `BR-MET-1165` — a preview is only true if it walks the same loop
    the thing itself walks — applies exactly: a screen that drew chips from one
    reading and queried with another would show a clerk *Water 5/8"* over rows
    filtered by something else. The caller is handed both halves of one answer.

    ⚠ **LONGEST FIRST, AND THAT IS THE WHOLE OF THE MATCHING RULE.** `water`
    alone is a token of nine water size classes; `5/8 water` is the whole of
    exactly one. Sorting by token count descending means the two-token term
    consumes both words before any one-token term can claim either, so a clerk
    typing more words gets a narrower answer rather than a wronger one.

    ⚠ **ONE VALUE PER FILTER KEY.** `f.status` takes a single stage, so two
    stage words cannot both win; the first (longest, then alphabetical by code)
    takes the key and the loser's words stay UNMATCHED rather than being
    silently dropped. Nothing here invents an OR.
    """
    typed = _term_tokens(text)
    if not typed:
        return {"filters": {}, "chips": [], "unmatched": []}
    remaining = list(typed)
    entries = sorted(
        _search_vocabulary(),
        key=lambda e: (-max(len(alt) for alt in e["alternatives"]), e["key"], e["value"]),
    )
    filters: dict[str, str] = {}
    chips: list[dict[str, str]] = []
    for entry in entries:
        if not remaining:
            break
        if entry["key"] in filters:
            continue  # one value per filter key — see the docstring
        pool: list[str] = []
        taken: list[str] = []
        for alternative in sorted(entry["alternatives"], key=len, reverse=True):
            pool = list(remaining)
            taken = []
            for term_token in alternative:
                hit = next((word for word in pool if _token_matches(word, term_token)), None)
                if hit is None:
                    taken = []
                    break
                pool.remove(hit)
                taken.append(hit)
            if taken:
                break
        if not taken:
            continue
        remaining = pool
        filters[entry["key"]] = entry["value"]
        chips.append(
            {
                "family": entry["family"],
                "key": entry["key"],
                "value": entry["value"],
                "label": entry["label"],
                # The words this chip ate, so a screen can take them back out
                # of the box when the chip's × is pressed.
                "terms": " ".join(taken),
            }
        )
    return {"filters": filters, "chips": chips, "unmatched": remaining}


def _unit_ids_matching_address(term: str) -> list[str]:
    fn = seams.resolve("metering", "unit_ids_matching", kind="selectors")
    return list(fn(term)) if fn is not None else []


def _premises_of(asset: models.Asset) -> str | None:
    current = _current_assignment(asset)
    if current is None:
        return None
    unit = seams.unit_ref(current.unit_id) or {}
    return unit.get("premises_id")


def _service_of(asset: models.Asset, page: _PageReads | None = None) -> str | None:
    """The Service column, read along the asset's SERVICE POINT (metering seam).

    ⚠ **THE SINGULAR COSTS TWO ROUND TRIPS, NOT ONE** — `service_point_ref`
    reads the point and then probes the platform catalogue for its code — which
    is two of `DEF-5745`'s five per row. `service_codes_for_points` is the same
    question for a whole set in two queries total; it has been published since
    `DEF-1549` and `DEF-MET-4962` already pointed the map at it."""
    if not asset.service_point_id:
        return None
    if page is not None:
        return page.services.get(str(asset.service_point_id))
    point = seams.service_point_ref(asset.service_point_id) or {}
    return point.get("service")


def _asset_cost_rollup(asset: Any) -> dict[str, Any]:
    """`AST-B-21` — one lifetime figure and the two halves it is made of.

    See the block in `asset_detail` for the reasoning; this is the arithmetic,
    and it is deliberately only ADDITION. The repairs half is the asset's own
    column; the jobs half is Work's answer through the seam. Neither is priced
    here.
    """
    maintenance = maintenance_lifetime_cost(asset.id)
    work = seams.work_cost_rollup_for_asset(asset.id) or {}
    work_cost = work.get("cost")
    halves = [
        Decimal(value).quantize(_DISPLAY_CENT)
        for value in (maintenance, work_cost)
        if value is not None
    ]
    lifetime = (
        str(sum(halves, Decimal("0")).quantize(MONEY_QUANTUM)) if halves else None
    )
    return {
        "maintenance": maintenance,
        "work": work_cost,
        "lifetime": lifetime,
        "jobs_costed": work.get("jobs_costed", 0),
        # `AST-B-16`'s second fact. 0 is a measurement here and not an absence:
        # the query ran and found no open job, which is exactly what the What's
        # due panel needs to be able to say.
        "open_work_orders": work.get("open_orders", 0),
        "currency": seams.tenant_currency(),
    }


def asset_detail(asset_id: Any) -> dict[str, Any]:
    """S50 header + Overview. BR-AST-039: the header carries the LIVE billing
    chain Premises → Unit → active Account (the account leg is null while the
    customers module owns no tables — W2)."""
    asset = asset_row(asset_id)
    current = _current_assignment(asset)
    unit = seams.unit_ref(current.unit_id) if current is not None else None
    account = seams.active_account_for_unit(current.unit_id) if current is not None else None
    today = seams.tenant_today()
    # Age counts from install; an inventory asset that was never installed
    # counts from purchase (B16 §5.1b — "age counts from purchase").
    age_base = asset.install_date or asset.purchase_date
    # CR-028 AST-W4 T4: buy + present value on the record (BR-AST-047) — the
    # SAME computation retire records at D4, served as-of the tenant's today.
    book = asset_book_value(asset, as_of=today)
    return {
        **asset_dict(asset),
        "specs": asset_specs(asset),
        # BR-AST-044: the S50 header block shows ALL THREE classifications
        # together. The flat keys above stay exactly as they were (the list
        # rows read them); this block is the header's own grouping, so a
        # detail view never has to know which of the three lives where.
        "classifications": {
            "asset_type": {"code": asset.type.code, "name": asset.type.name},
            "meter_type": (
                {"code": asset.meter_type.code, "name": asset.meter_type.name}
                if asset.meter_type_id
                else None
            ),
            "read_method": (
                {"code": asset.read_method.code, "name": asset.read_method.name}
                if asset.read_method_id
                else None
            ),
        },
        "billing_chain": {
            "premises_id": (unit or {}).get("premises_id"),
            "premise_no": (unit or {}).get("premise_no"),
            "premise_address": (unit or {}).get("premise_address"),
            "unit_id": (unit or {}).get("id"),
            "unit_label": (unit or {}).get("label"),
            "account": account,
        },
        "sub_assets": [
            {"id": str(child.id), "asset_no": child.asset_no, "type": child.type.code}
            for child in models.Asset.objects.filter(tenant_id=asset.tenant_id, parent_asset=asset)
            .select_related("type")
            .order_by("asset_no", "id")
        ],
        # ── CR-028 AST-W2 (B16 §5.1/§5.1b · BR-AST-047) ─────────────────────
        # The Warranty & supplier panel. CAPTURED figures, displayed at their
        # stored precision — no GL account, no posting sentence, ever (D3).
        "valuation": {
            "supplier": asset.supplier,
            "purchase_cost": _money_str(asset.purchase_cost),
            "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else None,
            "warranty_end": asset.warranty_end.isoformat() if asset.warranty_end else None,
            # Covered/Expired pill; None = no warranty on record, which is a
            # dash on screen — a third state, never collapsed into "Expired".
            "warranty_covered": (
                None if asset.warranty_end is None else asset.warranty_end >= today
            ),
            "depreciation_method": asset.depreciation_method,
            # ── CR-028 AST-W4 T4 (BR-AST-047: buy + present value) ──────────
            # Present value = straight-line book value as of TODAY; null when
            # no cost or no life is recorded (never a fabricated figure).
            "present_value": book["book_value"] if book else None,
            "accumulated_depreciation": book["accumulated_depreciation"] if book else None,
            "age_months": book["age_months"] if book else None,
            "life_months": book["life_months"] if book else None,
            # The pair retire RECORDED (D4) — null until the asset is retired.
            "book_value_amount": _money_str(asset.book_value_amount),
            "book_value_treatment": asset.book_value_treatment,
            # CHAR(3) rides WITH the amount (rule 2) — the screen formats to
            # 2 dp with it and never assumes a symbol.
            "currency": seams.tenant_currency(),
        },
        # The Lifecycle panel: age · expected life · certification due ·
        # replacement forecast (install year + life — arithmetic on captured
        # figures, the ◑ verdict B16 §7 allows).
        "lifecycle": {
            "age_months": _months_between(age_base, today) if age_base else None,
            "expected_life_years": asset.expected_life_years,
            "certification_due": next_test_date(asset),
            "replacement_year": (
                age_base.year + asset.expected_life_years
                if age_base and asset.expected_life_years
                else None
            ),
        },
        # ── `AST-B-16` / `AST-B-21` (CR-092-BRC01 step 2 wave C lane 1) ────
        # THE TWO FACTS THE OVERVIEW SHOWS THAT NO COLUMN SERVES.
        #
        # The blueprint's own done-test: *"Opening BF-0001 shows Lifetime
        # maintenance $1,284.00 and Open work orders 2 in the Cost & value and
        # What's due panels, both SERVED rather than computed in the browser
        # from a list the page happens to hold."* The third option — counting
        # `state` over rows the Maintenance tab already fetches — is free and
        # is the one the specification rejects by name, because a figure the
        # Overview computes from a list only the Maintenance tab loads is a
        # figure that is right on one tab and absent on the other.
        #
        # ⚠ **ONE LIFETIME COST, TWO HALVES, AND THE HALVES ARE SERVED TOO**
        # (PO ruling 2026-09-12, verbatim: *"a) One lifetime figure, both
        # halves named beneath"*). `maintenance` is what a clerk TYPED on a
        # repair; `work` is what `BR-WRK-051`'s one function worked out for the
        # jobs. Until today the asset showed only the first, so the better a
        # utility used work orders the wronger its own number got.
        #
        # ⚠ **`lifetime` IS THE SUM OF THE TWO *DISPLAYED* HALVES, NOT OF THE
        # TWO STORED ONES** — `BR-WRK-051`: *"the total is the sum of the
        # ROUNDED displayed lines"*. The two halves sit on the same panel
        # directly beneath the total, so a clerk who adds what they can see
        # must get what they are shown. Worked: repairs `84.0060` + jobs
        # `138.4160` → `$84.01 + $138.42 = $222.43`; sum-then-round gives
        # `222.4220` and prints `$222.42` over those same two lines. That one
        # cent is why this is a decision-log row. ⚠ **NOT EVERY PAIR SHOWS IT**
        # — `84.0000` / `138.4150` reads `$222.42` under BOTH rules, which is
        # why a test fixture must be chosen to DISCRIMINATE rather than to look
        # realistic; the first one written here did not, and passed against a
        # deliberately wrong implementation.
        #
        # ⚠ **null IS NOT ZERO, ON ALL THREE.** *Nobody recorded a cost* and
        # *we spent nothing* are different facts (the same discipline
        # `maintenance_lifetime_cost` already applies). A null half is a dash;
        # `lifetime` is null only when BOTH halves are.
        "cost_rollup": _asset_cost_rollup(asset),
        # B16 §5.1b (B): a behind-the-meter device's measuring link — the
        # Export tab reads THIS meter's records ("Measured by M-4310 · net →").
        "linked_meter": (
            {
                "id": str(asset.parent_asset_id),
                "asset_no": asset.parent_asset.asset_no,
                "net_metering": asset.parent_asset.net_metering,
            }
            if asset.type.category == "behind_the_meter" and asset.parent_asset_id
            else None
        ),
    }


def assignments_page(asset_id: Any) -> QuerySet:
    """US-AST-006 Assignment history as a **QuerySet**, newest first — the
    thing `StandardPagination` slices so that `LIMIT`/`OFFSET` reach SQL.

    `CR-092` wave C lane 3 / `DEF-MET-4995` / `NFR-3`. The ORDER BY is here and
    not in Python on purpose: a list sorted after the fact makes the paging a
    lie, which is the fault `DEF-PAY-4221` records against `GET /outstandings`
    and which this lane was told in as many words not to repeat.

    Append-only and non-overlapping (`BR-AST-017`) — the tab never writes.
    """
    asset = asset_row(asset_id)
    return models.AssetAssignment.objects.filter(
        tenant_id=asset.tenant_id, asset=asset
    ).order_by("-from_date", "-created_at")


def assignment_rows(entries: Any) -> list[dict[str, Any]]:
    """The served shape for ONE PAGE of `assignments_page`.

    ⚠ **THIS IS WHERE THE QUERY-PER-ROW WAS, AND NOTHING COULD SEE IT** — the
    loop called `seams.unit_ref` per seat. Measured on pine-hill `M-88402`
    after seeding a history: **64 queries for 61 rows**. Every asset on every
    tenant had exactly one seat, so the loop had never run twice.
    """
    entries = list(entries)
    # CR-028 AST-W2 T6: ONE name lookup for the page (the DEF-324 shape),
    # through the same read the S61 Actor column uses. A raw uuid in the "By"
    # column was the deployed W-5000 defect B16 §4.8 measured.
    names = seams.actor_display_names(
        _tenant_id(), [row.actor_user_id for row in entries if row.actor_user_id]
    )
    units = seams.unit_refs([row.unit_id for row in entries])
    rows = []
    for row in entries:
        unit = units.get(str(row.unit_id)) or {}
        rows.append(
            {
                "id": str(row.id),
                "from_date": row.from_date.isoformat(),
                "to_date": row.to_date.isoformat() if row.to_date else None,
                "current": row.to_date is None,
                "unit_id": str(row.unit_id),
                "unit_label": unit.get("label"),
                "premise_address": unit.get("premise_address"),
                # US-AST-006 §5: "System" when the actor is null. A resolvable
                # actor renders their NAME; a removed/foreign id keeps the id
                # (BR-IDN-030 — the trail outlives any row), never a blank.
                "by": _actor_display(row.actor_user_id, names),
                "final_read_id": str(row.final_read_id) if row.final_read_id else None,
            }
        )
    return rows


def assignments(asset_id: Any) -> list[dict[str, Any]]:
    """Every seat this asset has ever had, in one list.

    ⚠ **NO APPLICATION CODE CALLS THIS ANY MORE** — `GET /assets/{id}/assignments`
    pages through the two functions above — and that is stated rather than left
    for the next reader to discover with a grep (hard-won law 1). It survives as
    the whole-answer form its own test cases are written against, and because a
    caller reasoning over the entire chain (a retire or reassign flow) is a
    legitimate thing to want and would otherwise re-implement the loop. It is
    ONE line over `assignment_rows`, so the two cannot answer differently."""
    return assignment_rows(assignments_page(asset_id))


def _actor_display(actor_id: Any, names: dict[str, str]) -> str:
    if not actor_id:
        return "System"
    return names.get(str(actor_id)) or str(actor_id)


def maintenance(asset_id: Any) -> list[dict[str, Any]]:
    """US-AST-006 Maintenance & repairs: append-only log (BR-AST-018).

    CR-028 AST-W2: rows now carry `cost` (CAPTURED at 4 dp, displayed 2 —
    hard rule 2; NEVER posted, no GL sentence anywhere — §10-D3) and
    `technician`, the tech's display NAME resolved server-side (T6) so a
    Clerk who cannot list users still reads a person. `tech_user_id` stays
    as addressing."""
    return maintenance_rows(maintenance_page(asset_id))


def maintenance_page(asset_id: Any) -> QuerySet:
    """The maintenance log as a **QuerySet**, newest first — `NFR-3`'s half of
    `DEF-MET-4995`. Append-only (`BR-AST-018`); the ORDER BY is SQL's."""
    asset = asset_row(asset_id)
    return (
        models.AssetMaintenance.objects.filter(tenant_id=asset.tenant_id, asset=asset)
        .select_related("resulting_status")
        .order_by("-date", "-created_at")
    )


def maintenance_rows(entries: Any) -> list[dict[str, Any]]:
    """The served shape for ONE PAGE of `maintenance_page`. The technician name
    lookup is one call for the page, never one per row."""
    entries = list(entries)
    names = seams.actor_display_names(
        _tenant_id(), [row.tech_user_id for row in entries if row.tech_user_id]
    )
    return [
        {
            "id": str(row.id),
            "date": row.date.isoformat(),
            "kind": row.kind,
            "detail": row.detail,
            "tech_user_id": str(row.tech_user_id) if row.tech_user_id else None,
            "technician": names.get(str(row.tech_user_id)) or None if row.tech_user_id else None,
            "resulting_status": row.resulting_status.code if row.resulting_status_id else None,
            "closed_at": row.closed_at.isoformat() if row.closed_at else None,
            "cost": _money_str(row.cost),
        }
        for row in entries
    ]


def maintenance_lifetime_cost(asset_id: Any) -> str | None:
    """B16 §7's 'Lifetime maintenance $119.40' line: the SERVER's sum over the
    captured costs, at the stored 4 dp (display trims to 2). None — not zero —
    when no entry carries a cost: 'nobody recorded a cost' must never render
    as '$0.00 spent' (the BR-RAT-021 discipline applied to a display)."""
    asset = asset_row(asset_id)
    costs = [
        row.cost
        for row in models.AssetMaintenance.objects.filter(
            tenant_id=asset.tenant_id, asset=asset, cost__isnull=False
        )
    ]
    if not costs:
        return None
    return str(sum(costs, Decimal("0")).quantize(MONEY_QUANTUM))


# ── the served S50 Reads tab (CR-028 AST-W2 T4 — DEF-475 closed) ────────────
def asset_reads(asset_id: Any) -> list[dict[str, Any]]:
    """US-AST-005, served at last: this asset's committed lineage heads,
    NEWEST FIRST, with BR-AST-029's two typed records FOLDED per read date —
    the Import and Export columns of one row, each quantity with its explicit
    unit (CLAUDE.md rule 3). No money key exists in this payload
    (BR-AST-016/025).

    The fold: at one `read_at`, the export record attaches to the cycle's
    total-register row (`net_meter_pair`'s own pairing rule — one export
    against the total delivered, never one per TOU window); other consumption
    channels stay their own rows. An export with no consumption twin renders
    alone rather than being dropped — it is a measurement, and BR-AST-029
    says a missing twin is a review case, not an invisible one."""
    asset = asset_row(asset_id)
    return _fold_typed(seams.typed_reads_for_asset(asset.id))


def asset_read_dates_page(asset_id: Any) -> QuerySet:
    """The S50 Reads tab's PAGING UNIT — this asset's distinct read instants,
    newest first, as a QuerySet so the page reaches SQL (`NFR-3`).

    ⚠ **THE PAGE IS FIFTY READ DATES, NOT FIFTY ROWS, AND THE DIFFERENCE IS THE
    FOLD.** `asset_reads` folds `BR-AST-029`'s typed pair into the Import and
    Export columns of ONE row per read date, and a three-register meter yields
    three rows for one date. Paging the ROWS would therefore cut a reading event
    across a page boundary — half a meter's registers on page 1 and half on page
    2 — which is a worse answer than a page whose length varies. So `count` on
    this endpoint is the number of READ DATES, and the served contract says so
    rather than leaving a client to discover it.
    """
    asset = asset_row(asset_id)
    return seams.typed_read_dates_for_asset(asset.id)


def asset_reads_on(asset_id: Any, read_ats: Any) -> list[dict[str, Any]]:
    """`asset_reads` for ONE PAGE of `asset_read_dates_page` — the same fold
    over the same row shape, so the paged answer and the whole answer cannot
    disagree about what a read looks like."""
    asset = asset_row(asset_id)
    return _fold_typed(seams.typed_reads_for_asset_on(asset.id, read_ats))


def _fold_typed(typed: Any) -> list[dict[str, Any]]:
    """THE fold, named once (hard-won law 5) — see `asset_reads` for the rule
    it implements. Input is ascending by (read_at, channel); output is newest
    first, which is the r10 Reads tab's order."""
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in typed:  # served ascending (read_at, channel); regrouped here
        key = str(row.get("read_at") or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    out: list[dict[str, Any]] = []
    for key in reversed(order):  # newest first — the r10 Reads tab's order
        rows_at = groups[key]
        exports = [row for row in rows_at if row.get("read_type") == "export"]
        others = [row for row in rows_at if row.get("read_type") != "export"]
        export = exports[0] if exports else None
        if not others and export is not None:
            out.append(_fold_row(export, export=export, export_only=True))
            continue
        primary = next((row for row in others if row.get("channel") == "total"), None)
        if primary is None and others:
            primary = others[0]
        for row in others:
            out.append(_fold_row(row, export=export if row is primary else None))
    return out


def _quantity(value: Any) -> str | None:
    """Decimal → its stored string; None stays None (never a zero)."""
    return str(value) if value is not None else None


def _read_calendar_date(value: Any) -> str | None:
    """A read's date, served as a CALENDAR DATE — never as an instant.

    **DEF-MET-4101, and the whole defect is in this one conversion.** A read's
    date IS a calendar date: `metering.read_import._parse_date` normalises every
    one to `00:00:00Z` on purpose, because that is what makes B2 r8's
    `UNIQUE (asset, read_at, channel)` BE the per-date key `BR-MET-052`
    describes. Every write path in metering goes through it, so the UTC date of
    `read_at` is the read's calendar date, always.

    Serving that value as a raw instant handed the screen a timestamp, and
    `DateCell` — correctly, by its own documented contract — converts an instant
    INTO the tenant's timezone. Brazos Bend is `America/Chicago`, so a read the
    API dated `2026-08-14` was DRAWN as `08/13/2026`, and the whole reads
    history on every screen sat one day early for every tenant west of UTC.
    Taking the date here puts the value on `DateCell`'s *calendar-date* path,
    which formats the digits themselves and routes through no timezone at all —
    so Chicago and Berlin now draw the same day, which is what a calendar date
    means.

    ⚠ **THE FIX BELONGS HERE, ON WHAT WE SERVE, AND NOT ON WHAT WE STORE.**
    The tempting repair at the other end — storing the completion moment rather
    than the date — would make the screen right and would SILENTLY switch off
    the one-read-per-meter-per-date guarantee, because that guarantee IS the
    midnight normalisation. Nothing about the stored row changes here.

    ⚠ **AND NOT IN `metering.selectors.typed_reads_for_asset` EITHER**, which is
    where the string comes from: that is `US-AST-012 TC-3`'s published read
    interface and RATING consumes it. Narrowing a shared contract to fix a
    display is how a money path acquires a defect. This folds for the screen,
    which is what `_fold_row` is for.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    # The seam serves `read_at.isoformat()`, so this is the ordinary path:
    # "2026-08-14T00:00:00+00:00" → "2026-08-14". A value that is not an ISO
    # instant is passed through verbatim rather than truncated to ten
    # characters — a malformed date must stay visibly malformed, never be
    # quietly reshaped into a plausible wrong one.
    text = str(value)
    return text[:10] if _ISO_INSTANT_RE.match(text) else text


def _fold_row(
    row: dict[str, Any], *, export: dict[str, Any] | None, export_only: bool = False
) -> dict[str, Any]:
    exported = None
    if export is not None:
        # The exported QUANTITY: the record's computed consumption when it has
        # one, else its register value. Explicit None checks — a 0 export is a
        # REAL measurement and must survive the fold.
        exported = (
            export.get("consumption")
            if export.get("consumption") is not None
            else export.get("current_value")
        )
    return {
        "read_id": row.get("read_id"),
        # DEF-MET-4101: a CALENDAR DATE, never the raw instant. See
        # `_read_calendar_date` — the reason is written out there.
        "date": _read_calendar_date(row.get("read_at")),
        "channel": row.get("channel"),
        "read_type": row.get("read_type"),
        "reading": _quantity(row.get("current_value")),
        "consumption": None if export_only else _quantity(row.get("consumption")),
        "unit": None if export_only else row.get("unit"),
        "export": _quantity(exported),
        "export_unit": export.get("unit") if export is not None else None,
        "export_read_id": export.get("read_id") if export is not None else None,
        "source": row.get("source"),
        # DEF-WRK-10184 — the event that collected the reading (BR-MET-128):
        # `move_out`, `reconnect` … or None for an ordinary read.
        "event": row.get("event_context"),
        "status": row.get("status"),
        # BR-MET-1189 (PO 2026-10-04, DEF-WRK-9642): where this register holds
        # two readings on one date, which one COUNTS — True / False; None when
        # the reading is alone on its date and there is nothing to mark.
        "counts": row.get("counts"),
    }


@batch_reads.memoised
def billable_asset_count(unit_id: Any, service_code: str, as_of: date) -> int:
    """BR-RAT-090 — how many of this service's assets are on this unit, on a date.

    **The read behind CR-019.** PO ruling 2026-08-20, option A: *"an unmetered
    service's quantity is a COUNT OF ITS ASSETS ON THE UNIT"*, and the count is
    **OBSERVED, never typed** — so three carts on a unit bill three carts and
    adding one in the field changes the next bill by itself. Worked, ratified:
    3 carts x `$15.00` = `$45.00`; remove one and the next bill is `$30.00`.

    **THREE PREDICATES, and each one is load-bearing:**

    * **On this unit on that DATE**, read from `AssetAssignment` — append-only
      and dated (BR-AST-017) — never from wherever the asset sits today. A cart
      delivered on the 20th does not retro-bill the whole cycle, and a cart
      removed mid-cycle still billed while it was there. `as_of` is the
      service-period end date, per BR-RAT-090.
    * **IN SERVICE**, read from the lifecycle stage's `behavior_class` rather
      than its label — BR-AST-031's own rule: *"transitions/filters key off the
      class, never the label"*. A tenant who renames *Installed/Active* to
      *Deployed* must not thereby stop billing.
    * **FOR THIS SERVICE**, through the asset's service point. A unit with three
      carts and a water meter counts three for trash, not four.
    * ⊕ **AND NOT A READ DEVICE** (PO 2026-10-02, `DEF-MET-9037`) — a meter on
      the point is read, never counted. See `_billable_assignments`.

    ⚠ **RETURNS A COUNT, INCLUDING `0`, AND NEVER `None`.** Zero is a real
    answer: the utility looked and this unit has no carts. The *"nobody looked"*
    case is not expressible here and must never be invented as a zero — it is
    the seam's business, and `apps.rating.seams.active_asset_count` carries it
    as the `wired` half for exactly that reason.
    """
    return _billable_assignments(unit_id, service_code, as_of).count()


#: The asset-type CATEGORIES whose devices are READ, never counted or summed —
#: `assets.services.TAB_METERS` / `TAB_SUB_METERS`, the S49 tab partition.
READ_DEVICE_CATEGORIES: tuple[str, ...] = ("meters", "sub_meters")


def _billable_assignments(unit_id: Any, service_code: str, as_of: date) -> Any:
    """**The ONE population `billable_asset_count` counts and
    `billable_asset_size_classes` sums — and it holds no METER.** 🔒 rating
    math. HUMAN-REVIEW-PENDING.

    The three predicates are BR-RAT-090's (on this unit on that DATE · IN
    SERVICE by `behavior_class` · FOR THIS SERVICE through the service point),
    written once here so the two reads cannot drift apart.

    ⚠ **THE FOURTH PREDICATE — A READ DEVICE IS NOT CAPACITY — PO ruling
    2026-10-02 (`DEF-MET-9037`), verbatim:** *"we are not doing net metering
    right now - we are doing capacity based panel - A · The net meter doesn't
    count toward capacity. Capacity is the panels or battery only."* A meter,
    net meter or sub-meter standing on a capacity point is excluded by its
    type's CATEGORY (`meters` / `sub_meters`), never by a code, so a tenant's
    own meter type is excluded too.

    **Worked, and asserted on PostgreSQL**
    (`test_oq_1361_fire_lines_and_no_net_meter_pg.py`): three 4 kW panels and
    an installed, unsized meter on one solar point bill **12 kW × $14.00 =
    `$168.00`**. Before this predicate the meter's empty size sat beside the
    panels and the bill REFUSED (`installed_capacity_undetermined`) — which is
    what every solar or battery build New Connect committed until 2026-10-02
    would have done the day its meter was fitted.

    ⚠ **IT IS NOT NARROWED TO SOLAR AND BATTERY, AND THAT IS DELIBERATE.** A
    meter is read, not counted: a meter on a trash or fire point counted as a
    cart or a fire line would be an overcharge the same way. This read only
    ever answers for a service with no reads (`READ_ABSENT_SERVICE_NOT_METERED`),
    so a metered service's meters are untouched by it.
    """
    return (
        models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(),
            unit_id=unit_id,
            from_date__lte=as_of,
            asset__status__behavior_class="in_service",
            asset__service_point__service__code=service_code,
        )
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=as_of))
        .exclude(asset__type__category__in=READ_DEVICE_CATEGORIES)
    )


@batch_reads.memoised(copy=True)
def billable_asset_size_classes(unit_id: Any, service_code: str, as_of: date) -> list[str | None]:
    """**WHAT each of this service's assets on this unit IS, on a date — the
    SIZE CLASS of every one of them, in a stable order.** `CR-062` D1 / H2.

    HUMAN-REVIEW-PENDING (CLAUDE.md 🔒 — this feeds a money path). Row in
    `12-governance/09-human-review-ledger.md`.

    **THE SAME THREE PREDICATES AS `billable_asset_count` ABOVE**, and they are
    load-bearing for exactly the same reasons: on this unit **on that DATE**
    (`AssetAssignment`, dated and append-only — BR-AST-017), **IN SERVICE** by
    the lifecycle stage's `behavior_class` and never by its label (BR-AST-031),
    and **FOR THIS SERVICE** through the asset's service point. This function
    and that one must answer about the SAME set of assets or a bill would be
    counted from one population and summed from another; they are written as
    two calls over ONE filter (`_billable_assignments`, which since 2026-10-02 also leaves out every read device — `DEF-MET-9037`) for that reason, and
    `test_cr062_d1_installed_capacity_sums` asserts the two agree in length.

    ⚠ **A `None` ENTRY IS A REAL STATE AND MUST NOT BE DROPPED.**
    `Asset.size_class` is nullable by ruling (BR-AST-500: *"a meter is often
    loaded before anyone knows its size"*), so a panel whose type nobody has
    recorded appears here as `None`. **Filtering those out would turn three
    panels of unknown capacity into a total of `0 kW`** — a silent $0.00 solar
    line on a document that foots. The caller decides what an unknown means;
    this function reports it.

    ⚠ **NOTHING HERE KNOWS WHAT A SIZE CLASS IS WORTH.** The capacity a code
    stands for is ratified law in `apps/tenancy/service_size_classes.py` and
    assets may not read tenancy's rules (B1). This returns CODES; the arithmetic
    happens where the law lives, and metering is the module that asks both.

    An empty list is a real answer — the utility looked and this unit has no
    such equipment — exactly as `billable_asset_count`'s `0` is. The *"nobody
    looked"* case is not expressible here and must never be invented as an empty
    list; it is the seam's business (`metering.seams`).
    """
    rows = (
        _billable_assignments(unit_id, service_code, as_of)
        # Ordered so two calls in one bill run cannot disagree about the order
        # a total was assembled in. It changes no sum — addition is commutative
        # — but it makes the published fact reproducible, which is what a
        # reviewer reading a bill against the estate needs.
        .order_by("asset__asset_no", "asset_id")
        .values_list("asset__size_class", flat=True)
    )
    out: list[str | None] = []
    for value in rows:
        text = str(value).strip() if value is not None else ""
        out.append(text or None)
    return out


def billable_asset_size_classes_by_asset(
    unit_id: Any, service_code: str, as_of: date
) -> list[tuple[str, str | None]]:
    """`billable_asset_size_classes`, with each asset's NUMBER beside its size
    class — `[("PV-00020", "SOL-P47.84"), ("PV-00021", None)]`. `DEF-RAT-10220`.

    The same filter (`_billable_assignments`), the same order and the same
    population, so the asset a bill-run Check NAMES is one of exactly the
    assets the total was refused over (PO 2026-10-17: *"the bill run Check
    names the asset whose size has no kW"*). An asset number is what a clerk
    searches the register by — never a database id (B14 rule 31).
    """
    rows = (
        _billable_assignments(unit_id, service_code, as_of)
        .order_by("asset__asset_no", "asset_id")
        .values_list("asset__asset_no", "asset__size_class")
    )
    out: list[tuple[str, str | None]] = []
    for asset_no, value in rows:
        text = str(value).strip() if value is not None else ""
        out.append((str(asset_no or ""), text or None))
    return out


# ── the AST-05 wizard's number probe (CR-028 AST-W4 · BR-AST-026/033) ───────
def asset_no_preview(type_code: str) -> str | None:
    """The add wizard's series SUGGESTION — a PEEK, never an allocation.

    r10's AST-05 step 1 shows the next number before the asset exists; calling
    `suggest_asset_no` per keystroke would BURN a series number per render
    (`core_numbering.next_number` advances the counter). So this reads
    tenancy's own preview contract (BE-06 — "validates + renders only,
    allocates nothing") and applies the SAME BR-AST-026 per-type prefix swap
    the allocator applies, so the preview tells the truth about what a blank
    number will become. None when the tenant has no asset series row — the
    wizard then asks for an explicit number, exactly as the create refusal
    (`assets.asset_no_required_no_series`) would demand."""
    from apps.assets import services

    row = seams.asset_series_preview()
    if not row or not row.get("preview"):
        return None
    preview = str(row["preview"])
    series_format = str(row.get("format") or "")
    prefix = services.ASSET_NO_PREFIXES.get(str(type_code or "").strip().lower())
    literal = series_format.split("{", 1)[0]
    if prefix and literal and preview.startswith(literal):
        return prefix + preview[len(literal) :]
    return preview


def asset_no_preview_run(type_codes: list[str]) -> dict[str, Any] | None:
    """**THE NUMBERS A LOAD WOULD ISSUE, STATED BEFORE IT ISSUES THEM — a PEEK,
    never an allocation** (PO ruling 2026-08-27: *"we have number system set in
    the settings, we shoudl call that function and get unique number and assign
    it"*; the ruling's own last clause is *"the dry run states the numbers it
    will issue rather than echoing the file's"*).

    `type_codes` is one entry PER ROW THAT WILL BE CREATED, in row order,
    because BR-AST-026's prefix is per TYPE while the sequence is shared: a
    devices file of a backflow then a PV inverter takes `BF-00042` and
    `PV-00043` off one counter. Guessing a single prefix for the run would
    print numbers that are not the ones issued.

    Returns `None` when the tenant has no `asset` series row — the caller then
    says so rather than printing an invented range, exactly as the AST-05
    wizard does (`asset_no_preview`).

    ⚠ **NOTHING HERE ADVANCES ANYTHING.** `core_numbering.preview` is the BE-06
    peek contract ("validates + renders only, allocates nothing") and this
    walks it forward by an OFFSET rather than calling `next_number` N times,
    which would burn N numbers per rehearsal — and a rehearsal is allowed to be
    run twice.

    ⚠ **A RESTART PERIOD IS NOT MODELLED HERE, AND THAT IS STATED RATHER THAN
    HIDDEN.** Under a CR-005 restart the counter rolls back to 1 when the
    period turns; a rehearsal on the last day of a period can therefore name
    numbers a commit on the next day would not use. `asset_no_preview` has the
    same limit for the same reason, and both are honest about it: the numbers
    are what the series would issue NOW.
    """
    from apps.assets import services

    row = seams.asset_series_preview()
    if not row or not row.get("format"):
        return None
    series_format = str(row["format"])
    try:
        start = int(row.get("next_number") or 0)
    except (TypeError, ValueError):  # pragma: no cover — tenancy stores an int
        return None
    if start <= 0:
        return None
    issue_date = seams.tenant_today()
    literal = series_format.split("{", 1)[0]

    def rendered_at(offset: int, type_code: str) -> str | None:
        try:
            value = core_numbering.preview(series_format, start + offset, issue_date)
        except Exception:  # a malformed stored format must not break a rehearsal
            return None
        prefix = services.ASSET_NO_PREFIXES.get(str(type_code or "").strip().lower())
        if prefix and literal and value.startswith(literal):
            return prefix + value[len(literal) :]
        return value

    numbers = [
        number
        for offset, code in enumerate(type_codes[:PREVIEW_NUMBERS_SHOWN])
        if (number := rendered_at(offset, code)) is not None
    ]
    last = (
        rendered_at(len(type_codes) - 1, type_codes[-1])
        if type_codes
        else None
    )
    return {
        "series_format": series_format,
        "next_number": start,
        "count": len(type_codes),
        "numbers": numbers,
        "last": last,
    }


def import_outcome_stages() -> dict[str, dict[str, str]]:
    """**THE TWO STAGES AN IMPORTED ASSET CAN LAND IN, IN THE TENANT'S OWN
    WORDS** — CR-046 D2, and OQ-840's *"what status you will ahve on this
    meters - please confirm that"*.

    `services._create_asset_inner` decides it with one expression —
    `stage_code = "active" if unit_id else "inventory"` — so there are exactly
    two, and this reads the tenant's rows for those two codes rather than
    hard-coding the seeded labels. **BR-AST-031 lets a tenant RENAME a stage**,
    so a rehearsal printing *"Installed / Active"* at a utility that calls it
    *"In the field"* would be telling them about a status their product does
    not have.

    Keyed by the code, carrying the label and the behavior class, because the
    class is the fact a rule acts on and the label is the fact a person reads.
    A code the tenant has somehow lost is simply absent — the caller then says
    less rather than inventing a name."""
    from apps.assets import models as asset_models

    out: dict[str, dict[str, str]] = {}
    rows = asset_models.AssetLifecycleStage.objects.filter(
        tenant_id=_tenant_id(), code__in=("active", "inventory")
    )
    for row in rows:
        out[row.code] = {
            "code": row.code,
            "name": row.name,
            "behavior_class": row.behavior_class,
        }
    return out


def asset_no_available(asset_no: str) -> bool:
    """The UNIQUE availability probe behind r10's AST-05 callout — the same
    case-insensitive match BR-AST-033's hard block enforces at create, asked
    early so the clerk learns before the submit, not instead of it."""
    cleaned = str(asset_no or "").strip()
    if not cleaned:
        return False
    return not models.Asset.objects.filter(
        tenant_id=_tenant_id(), asset_no__iexact=cleaned
    ).exists()


def lifecycle_stages() -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "behavior_class": row.behavior_class,
            "active": row.active,
            "is_system": row.is_system,
        }
        for row in models.AssetLifecycleStage.objects.filter(tenant_id=_tenant_id()).order_by(
            "code", "id"
        )
    ]


def asset_types() -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "category": row.category,
            "active": row.active,
            "is_system": row.is_system,
        }
        for row in models.AssetType.objects.filter(tenant_id=_tenant_id()).order_by("name", "id")
    ]


def _flat_catalog(model: Any) -> list[dict[str, Any]]:
    """BR-AST-043 lists are flat named sets — no tab key, no behavior class."""
    return [
        {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "active": row.active,
            "is_system": row.is_system,
        }
        for row in model.objects.filter(tenant_id=_tenant_id()).order_by("code", "id")
    ]


def meter_types() -> list[dict[str, Any]]:
    """The S8 "Meter types" card's content (BR-AST-043 · US-TEN-009 TC-1) and,
    since BR-AST-044, the S51 meter-type picker + the S49 filter's options —
    `assets.meter_type` points at one of these rows."""
    return _flat_catalog(models.MeterType)


def read_methods() -> list[dict[str, Any]]:
    """The S8 "Read methods" card's content + the S51 read-method picker
    (BR-AST-043); `assets.read_method` points at one of these rows."""
    return _flat_catalog(models.ReadMethod)


# ── BR-TEN-162: DOES THIS TENANT ACTUALLY METER THIS SERVICE? (DEF-901) ─────
def metered_service_codes() -> list[str]:
    """The service codes this tenant has AT LEAST ONE MEASURING ASSET on.

    ── WHY THIS READ EXISTS (DEF-901, PO 2026-08-27) ────────────────────────
    The PO asked of the S64 read-validation thresholds, on the live app:
    *"are these settings applicable to sewer"*. They were not. That page drew
    a full threshold form — a high-use threshold, a days window, a zero-read
    rule and a `Save Sewer thresholds` button — for every **ENABLED** service,
    and sewer is normally priced as a percentage of the water usage charge
    (BR-RAT-015) and reads no register at all. Fourteen inputs of
    configuration that can never fire, offered for tuning.

    ⚠ **THE RULE IS NOT "sewer never has meters", AND WRITING IT THAT WAY IS
    THE TRAP.** A utility that genuinely meters sewer exists — the size-class
    discussion in this repo already anticipates one — so a hard-coded list of
    "unmetered services" would be right on today's demo tenant and wrong on
    the first customer who bought a sewer meter, with nothing objecting.
    **BR-TEN-162: the test is the tenant's OWN ESTATE, never the service
    code.** This function is that test, and it is the only one.

    ── WHAT COUNTS AS METERING, AND WHY EACH HALF ──────────────────────────
    * **A MEASURING TYPE** — `apps.assets.services.MEASURING_TYPES`, i.e.
      `meter` · `net_meter` · `sub_meter`, which is BR-AST-009's own set and
      is imported rather than re-listed so the two cannot drift. A trash cart
      and a PV panel are assets and are NOT meters: a cart bills as a COUNT
      (BR-RAT-090) and produces no reading, so a tenant with three carts and
      no water meter still gets no trash threshold form.
    * **ON A SERVICE POINT OF THAT SERVICE** — `asset.service_point.service`,
      the same join `billable_asset_count` uses. A non-measuring behind-the-
      meter type may carry no service point at all (BR-AST-009), and those
      rows are excluded by the type filter before the join ever matters.

    ⚠ **LIFECYCLE STAGE IS DELIBERATELY NOT A PREDICATE, AND THAT IS THE
    OPPOSITE CHOICE FROM `billable_asset_count` FIVE HUNDRED LINES UP.** That
    read prices a bill, so it must ask what was IN SERVICE on a date. This one
    decides whether to SHOW A SETTINGS FORM, and BR-TEN-162 clause 3 says fail
    toward showing: a tenant whose only sewer meter is in the workshop this
    week still validates sewer readings, and hiding the thresholds that judge
    them would be the expensive mistake. Any meter that has ever existed on
    the service answers yes.

    ⚠ **AN EMPTY RESULT IS A POSITIVE ANSWER, NEVER A "COULD NOT TELL".** It
    means: this tenant's asset register contains no measuring asset on any
    service. It is what a brand-new tenant looks like, and the screen says so
    in those words rather than hiding every threshold form as if the page had
    failed to load.

    Sorted, so the wire shape is stable and a snapshot test can hold it.
    """
    from apps.assets.services import MEASURING_TYPES

    return sorted(
        models.Asset.objects.filter(
            tenant_id=_tenant_id(),
            type__code__in=MEASURING_TYPES,
            service_point__isnull=False,
        )
        .values_list("service_point__service__code", flat=True)
        .distinct()
    )


def size_banded_services() -> dict[str, list[str]]:
    """**WHICH OF THIS TENANT'S SERVICES PRICE BY SIZE BAND** — `DEF-AST-7660`.

    The one fact an assign form needs before it can know whether the
    connection size is required: on a BANDED service the size picks the base
    charge (`BR-RAT-108`), so a blank one is not a gap the bill can survive.

    ⚠ **THE BROWSER MUST NOT DERIVE THIS AND CANNOT.** *"Banded"* is
    `apps.rating.resolution.service_prices_by_size_class` — two ruled lookups
    that live on the server — and the obvious client-side substitute (*"the
    tenant has size classes for this service, so it must band"*) is exactly
    `DEF-3098`'s retired proxy, which stopped being true the day solar and
    battery gained a catalogue of installable equipment. A screen that guessed
    it would refuse a solar install for a missing size that does not exist.

    ⚠ **THREE LISTS, NOT TWO, AND `not_ruled` IS NOT `not_banded`.** A caller
    must treat `not_ruled` as *"do not require, and do not claim it is optional
    either"* — the form neither marks the field required nor pretends the
    absence is lawful. **Measured 2026-09-28, `not_ruled` is EMPTY for every
    tenant**, because the one unruled thing is the DIMENSION
    `thermal_heat_steam` and a dimension is not a service code. It is a third
    list rather than a dropped case because the day a twelfth service arrives
    unruled, collapsing it into `not_banded` would silently tell a screen that
    a blank size is lawful on a service nobody has been asked about.

    Scoped to the services this tenant has ENABLED (`BR-RAT-024`), because
    offering an answer about a service the utility does not sell would draw a
    requirement onto a screen that can never show it. Sorted, so the wire shape
    is stable.
    """
    banded: list[str] = []
    not_banded: list[str] = []
    not_ruled: list[str] = []
    for code in sorted(seams.enabled_service_codes()):
        answer = seams.service_prices_by_size_class(code)
        if answer is None:
            not_ruled.append(code)
        elif answer:
            banded.append(code)
        else:
            not_banded.append(code)
    return {"banded": banded, "not_banded": not_banded, "not_ruled": not_ruled}


# ── the S52 staged batch (US-AST-010 · BR-AST-023/034) ──────────────────────
def import_batch(batch_id: Any) -> dict[str, Any]:
    if not _is_uuid(batch_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    batch = models.AssetImportBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id).first()
    if batch is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    rows = list(
        models.AssetImportRow.objects.filter(tenant_id=batch.tenant_id, batch=batch).order_by(
            "row_no"
        )
    )
    return {
        "id": str(batch.id),
        "filename": batch.filename,
        "skip_errors": batch.skip_errors,
        "committed": batch.committed_at is not None,
        "preview": {
            "rows": batch.row_count,
            "valid": batch.valid_count,
            "errors": sum(1 for r in rows if r.errors),
        },
        "rows": [
            {
                "row_no": r.row_no,
                "resolved": (r.raw or {}).get("resolved"),
                "errors": r.errors or [],
                "asset_id": str(r.asset_id) if r.asset_id else None,
            }
            for r in rows
        ],
    }


# ── seam surface consumed by metering (S15 meters cell, unit search) ────────
@batch_reads.memoised(copy=True)
def assets_on_unit(unit_id: Any) -> list[dict[str, Any]]:
    """S15 "Meters" cell: the assets CURRENTLY assigned to the unit, each with
    its (sub)/(master) qualifier (US-MET-002 TC-1).

    ⚠ **`size_class` IS PUBLISHED HERE BECAUSE TWO SCREENS AND ONE BILL RUN
    ALREADY ASKED FOR IT AND GOT NOTHING (DEF-514, BR-AST-500).**
    `metering.selectors.route_meter_picker` has read `asset.get("size_class")`
    out of this very dict since SET-06 step 3 was built, and this dict published
    `id`, `asset_no`, `qualifier` and `type` and no size — so that screen's Size
    column has drawn a permanently empty cell, which reads as *"this meter has
    no size recorded"* rather than *"this product cannot record one"*.
    `metering.selectors.connection_size_for` — the seam
    `billing.gather._connection_size_for` has resolved BY NAME since DEF-484 and
    which has never had a source — now answers from this key.

    None is a real value here and must stay one: it is *"nobody recorded a
    size"*, and the bill run refuses by name on it rather than silently
    selecting the every-size tier ladder (DEF-484)."""
    asset_ids = list(
        models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_id, to_date__isnull=True
        ).values_list("asset_id", flat=True)
    )
    out = []
    for asset in _base_qs().filter(id__in=asset_ids).order_by("asset_no", "id"):
        has_children = models.Asset.objects.filter(
            tenant_id=asset.tenant_id, parent_asset=asset
        ).exists()
        out.append(_asset_on_unit_row(asset, has_children=has_children))
    return out


def _asset_on_unit_row(asset: Any, *, has_children: bool) -> dict[str, Any]:
    """ONE row of `assets_on_unit`/`assets_on_units` — the single builder.

    ⚠ **IT IS SHARED SO THE BATCHED AND UNBATCHED ANSWERS CANNOT DRIFT.** The
    history here is `DEF-514`: `route_meter_picker` read `size_class` out of
    this dict from the day SET-06 step 3 was built and the dict did not publish
    one, so a Size column rendered empty for weeks and read as *"this meter has
    no size"* rather than *"this product cannot record one"*. Two builders is
    the same failure waiting to happen with the next key.
    """
    qualifier = "sub" if asset.parent_asset_id else ("master" if has_children else None)
    return (
            {
                "id": str(asset.id),
                "asset_no": asset.asset_no,
                "qualifier": qualifier,
                "type": asset.type.code,
                # ── CR-089 wave F `F3` — WHICH SIDE OF THE METER THIS IS ─────
                # `BR-AST-004`'s category, the SERVER's own, exactly as
                # `asset_dict` and the registry row publish it under this same
                # name (`"tab": asset.type.category`, one screen up). The unit's
                # Assets tile has to split *what is read and bills* from *what
                # we own and do not read*, and the alternative was inferring it
                # from the TYPE CODE on the client — which is the inference
                # `PremisesDetailPage.isMeteredAsset` was written to avoid, and
                # which goes wrong the first time a tenant adds a type of their
                # own (`BR-TEN-036` says they may).
                #
                # ⚠ **IT COSTS NO QUERY.** `_base_qs` already
                # `select_related("type")` and the line above already reads
                # `asset.type.code` off it, so this is a second attribute of a
                # row already in memory.
                "tab": asset.type.category,
                # BR-AST-500 — `service_size_classes.code` or None. See the
                # docstring: the null is the honest answer, never a default.
                "size_class": asset.size_class,
                # CR-171-BRC10 P1.16 — the meter a sub-meter or device hangs
                # off (BR-AST-003), so the move-in's *See full rates* can draw
                # meter → sub-meter → device. An attribute already on the row:
                # no query.
                "parent_asset_id": str(asset.parent_asset_id) if asset.parent_asset_id else None,
            }
    )


def meter_facts_for_unit(unit_id: Any) -> list[dict[str, Any]]:
    """The facts the move-in's *Services and meters* table draws, per asset
    CURRENTLY on the unit — `CR-171-BRC10` P1.18 (lane MVI-FLOW), image 30–31.

    **PUBLISHED FOR `apps.customers.move_in_unit_read`**, resolved there by
    name (B1: customers asks, assets answers). One query for the assignments,
    one for the assets with their type and parent; no per-row query.

    Each row: `asset_no` · `parent_asset_no` (a sub-meter's or a
    behind-the-meter device's meter, BR-AST-003) · `service_point_id` (which
    service it reads, through metering's point) · `category` (BR-AST-004's tab:
    `meters` | `sub_meters` | `behind_the_meter`) · `type` / `type_name` ·
    `size_class` (None = nobody recorded one, never a default) · `multiplier`
    (6dp string) · `register_digits` (BR-AST-015's read bound) · `unit` (rule 3)
    · `location_note` · `last_test_date` / `test_interval_months` (the device's
    *test due*) · image 31's expand line: `serial_no`, `meter_type_name`,
    `read_method_name`, `install_date`, `manufacturer`, `model`, `seal_no`,
    `certification_due`. Nothing is computed; the caller composes.
    """
    asset_ids = list(
        models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_id, to_date__isnull=True
        ).values_list("asset_id", flat=True)
    )
    out: list[dict[str, Any]] = []
    for asset in _base_qs().filter(id__in=asset_ids).order_by("asset_no", "id"):
        out.append(
            {
                "asset_no": asset.asset_no,
                "parent_asset_no": asset.parent_asset.asset_no if asset.parent_asset_id else None,
                "service_point_id": str(asset.service_point_id) if asset.service_point_id else None,
                "category": asset.type.category,
                "type": asset.type.code,
                "type_name": asset.type.name,
                "size_class": asset.size_class,
                "multiplier": f"{asset.multiplier:.6f}" if asset.multiplier is not None else None,
                "register_digits": asset.register_digits,
                "unit": asset.unit,
                "location_note": asset.location_note,
                "last_test_date": asset.last_test_date.isoformat() if asset.last_test_date else None,
                "test_interval_months": asset.test_interval_months,
                # `CR-171-BRC10` lane MVI-WIZ-UNIT (image 31) — the meter's own
                # facts, drawn on one line when its row is expanded. Catalogue
                # NAMES, never codes or ids (B14 rule 31); None = not recorded.
                "serial_no": asset.serial_no,
                "meter_type_name": asset.meter_type.name if asset.meter_type_id else None,
                "read_method_name": asset.read_method.name if asset.read_method_id else None,
                "install_date": asset.install_date.isoformat() if asset.install_date else None,
                "manufacturer": asset.manufacturer,
                "model": asset.model,
                "seal_no": asset.seal_no,
                "certification_due": (
                    asset.certification_due.isoformat() if asset.certification_due else None
                ),
            }
        )
    return out


def assets_on_units(unit_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """`assets_on_unit`, for MANY units, in a bounded number of queries.

    ⚠ **THIS EXISTS BECAUSE THE PER-UNIT VERSION COSTS 5.1 QUERIES PER UNIT AND
    A ROUTE CAN HOLD 726 OF THEM (`CR-131-BRC07`, measured 2026-09-22 by
    `10-scripts/cr131_scale_measure.py`).** `metering.selectors.route_meter_picker`
    called `assets_on_unit` once per member unit, so SET-06 step 3 cost **3,711
    sequential round trips** at the size the PO actually hit it. Three queries
    now, whatever the size — the assignments, the assets, and the one that says
    which of them have children.

    It is the same fact and the same dict, deliberately: `assets_on_unit` is
    left standing for the single-unit screens, and **both return rows built by
    `_asset_on_unit_row`**, because two builders of one shape is one of them
    silently losing a key. `size_class` went missing from a route's Size column
    for weeks (`DEF-514`) precisely that way.

    A unit with no assignment is ABSENT from the map rather than present with an
    empty list — the caller's `.get(unit_id, [])` is the same answer, and a map
    listing every unit in the tenant is the cost this call exists to avoid.
    """
    ids = [unit_id for unit_id in unit_ids if unit_id not in (None, "")]
    if not ids:
        return {}
    tenant_id = _tenant_id()
    # 1 · the current assignments — which asset stands on which unit.
    pairs = list(
        models.AssetAssignment.objects.filter(
            tenant_id=tenant_id, unit_id__in=ids, to_date__isnull=True
        ).values_list("unit_id", "asset_id")
    )
    if not pairs:
        return {}
    asset_ids = {asset_id for _unit_id, asset_id in pairs}
    # 2 · the assets themselves, with the four joins `_base_qs` already carries.
    assets = {
        asset.id: asset for asset in _base_qs().filter(id__in=list(asset_ids))
    }
    # 3 · which of them are MASTERS — one read instead of one per asset, which
    #     is where most of the 5.1 went.
    parents = set(
        models.Asset.objects.filter(
            tenant_id=tenant_id, parent_asset_id__in=list(asset_ids)
        ).values_list("parent_asset_id", flat=True)
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for unit_id, asset_id in pairs:
        asset = assets.get(asset_id)
        if asset is None:  # pragma: no cover — an assignment to a deleted asset
            continue
        out.setdefault(str(unit_id), []).append(
            _asset_on_unit_row(asset, has_children=asset.id in parents)
        )
    for rows in out.values():
        rows.sort(key=lambda row: (row["asset_no"] or "", row["id"]))
    return out


def asset_counts_for_units(unit_ids: list[Any]) -> dict[str, int]:
    """How many assets each of these units currently holds — ONE query.

    ⚠ **THIS EXISTS BECAUSE OF D7 (CR-029), AND IT IS THE SAME QUESTION
    `assets_on_unit` ANSWERS.** The routes and cycles lists derive their meter
    counts by calling `assets_on_unit` once per member unit, and a route with
    380 members therefore cost 760+ queries to draw one row of a table. The
    caller only ever took `len(...)` of the result, so the count is served
    directly and the per-unit list is left for the screens that render it.

    Units with no assignment are ABSENT from the map rather than present with a
    0 — the caller's `.get(unit_id, 0)` is the same answer, and a map that
    listed every unit in the tenant would be the thing this call avoids.
    """
    ids = [unit_id for unit_id in unit_ids if unit_id not in (None, "")]
    if not ids:
        return {}
    counts: dict[str, int] = {}
    rows = (
        models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(), unit_id__in=ids, to_date__isnull=True
        )
        .values("unit_id")
        .annotate(total=Count("asset_id", distinct=True))
    )
    for row in rows:
        counts[str(row["unit_id"])] = int(row["total"])
    return counts


@batch_reads.memoised(copy=True)
def asset_ids_for_service_point(service_point_id: Any) -> list[str]:
    """The meters standing on one service point — the reads seam's first hop.

    A bill run asks "what did this service measure", and the chain from the
    service point to a read runs through the METER: reads hang off
    `assets.Asset`, and `service_point_id` on the asset is where the two meet
    (the reviewed cross-module FK, B2 §2). Metering owns the service point and
    assets owns the meter, so metering asks rather than joining — that join is
    the boundary B1 draws.

    Retired meters are INCLUDED. A meter replaced mid-cycle still produced the
    reads that half the period is billed on, and filtering it out here would
    silently drop them; whether a read is usable is the READ's status, which
    metering judges, not the meter's lifecycle.
    """
    return [
        str(asset_id)
        for asset_id in models.Asset.objects.filter(
            tenant_id=_tenant_id(), service_point_id=service_point_id
        )
        .order_by("asset_no", "id")
        .values_list("id", flat=True)
    ]


@batch_reads.memoised(copy=True)
def in_service_asset_ids_for_service_point(service_point_id: Any) -> list[str]:
    """The meters on one service point whose lifecycle stage is IN SERVICE.

    PO ruling 2026-09-30: two meters on one METERED service bill as two lines,
    each its own connection. Metering splits a point per meter across THIS
    list and not `asset_ids_for_service_point` above, which deliberately
    INCLUDES retired meters (a meter replaced mid-cycle produced the reads half
    the period bills on) — splitting on that would turn every exchange into
    two connections. Keyed off the stage's `behavior_class`, never its label
    (BR-AST-031), the same predicate `billable_asset_count` uses.

    ⚠ **ONLY A STANDALONE BILLING METER COUNTS — `category='meters'`, NO
    PARENT, NO CHILDREN.** A master meter with sub-meters under it (CR-038 W6)
    and the sub-meters themselves are ONE measured arrangement, not two
    connections, and a behind-the-meter device is not read for billing at all.
    Measured on a seeded PostgreSQL 16 tenant before this clause: 5 of 75
    accounts had a unit meter, the building's master `M-MASTER-01` and a
    sub-meter `SM-7040` on one water point, and splitting across all three
    refused all 5 bills as missing reads on meters nobody reads per unit.
    """
    return [
        str(asset_id)
        for asset_id in models.Asset.objects.filter(
            tenant_id=_tenant_id(),
            service_point_id=service_point_id,
            status__behavior_class="in_service",
            type__category="meters",
            parent_asset__isnull=True,
        )
        .exclude(
            id__in=models.Asset.objects.filter(
                tenant_id=_tenant_id(), parent_asset__isnull=False
            ).values("parent_asset_id")
        )
        .order_by("asset_no", "id")
        .values_list("id", flat=True)
    ]


#: 🔒 `DEF-BIL-10155` / `DEF-BIL-10156` — the meter type a building's MASTER
#: meter declares (BR-AST-044's seeded `master`). A master measures the whole
#: building for reconciliation against its sub-meters; it is never one unit's
#: billing measurement, even where it was attached to a unit's service point.
MASTER_METER_TYPE = "master"


def _is_unit_billing_meter(asset: Any) -> bool:
    """`billing_asset_ids_for_service_point`'s predicate on one loaded row —
    shared with `prime_check_batch` so the batch answer cannot drift from the
    per-point one."""
    category = getattr(getattr(asset, "type", None), "category", None)
    meter_type = getattr(getattr(asset, "meter_type", None), "code", None)
    return category == "meters" and meter_type != MASTER_METER_TYPE


def _billing_ids(assets: list[Any]) -> list[str]:
    own = [str(asset.id) for asset in assets if _is_unit_billing_meter(asset)]
    return own if own else [str(asset.id) for asset in assets]


@batch_reads.memoised(copy=True)
def billing_asset_ids_for_service_point(service_point_id: Any) -> list[str]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10155` / `DEF-BIL-10156` — the meters
    whose readings ARE this service point's billed measurement.

    `asset_ids_for_service_point` above answers *"what stands on the point"*,
    and until this function the reads seam priced the LATEST head among ALL of
    them. On a Mill Pond unit the water point holds the unit's own meter, a
    sub-meter under it, a sub-meter under the building's master and, on Apt
    101, the master itself. A cycle bill never noticed, because only the unit
    meter is ever read on a cycle; a move-out keys every meter on the same day,
    and the latest head was then whichever sub-meter sorted last:
    **AC-2026-00044 was billed 1 kgal off SM-7201 (5 → 6) while its own meter
    W-5043 measured 6 kgal (2,639 → 2,645)**, and sewer at 90% followed the
    wrong figure (0.9 kgal for 5.4). And on Apt 101 a never-read sub-meter or
    the master ticked *Estimate* became the point's reading and refused the
    whole draft.

    **THE RULE: a unit's service is measured by its own meter** — an asset of
    category `meters` whose meter type is not `master`. Sub-meters (category
    `sub_meters`) and a building's master are measurements FOR reconciliation,
    not the unit's bill. ⚠ **AND WHERE THE POINT HOLDS NO SUCH METER, EVERY
    ASSET ON IT COUNTS, exactly as before** — a sub-metered apartment whose
    only device is its sub-meter is billed from that sub-meter, and a common
    area measured by the master alone is billed from the master. So this only
    ever NARROWS a point that has a unit meter, and the cycle bill and the
    final bill now ask the same question of the same list (`DEF-BIL-10156`'s
    *"the run's service-point read choice must be the same for a cycle bill
    and a final bill"*).

    Retired meters stay in, for `asset_ids_for_service_point`'s reason: a
    meter exchanged mid-period produced half the period's reads. Same order.
    """
    return _billing_ids(
        list(
            models.Asset.objects.filter(tenant_id=_tenant_id(), service_point_id=service_point_id)
            .select_related("type", "meter_type")
            .order_by("asset_no", "id")
        )
    )


def prime_check_batch(
    unit_codes: dict[str, tuple[str, ...]],
    service_point_ids: list[Any],
    *,
    as_of: date,
) -> dict[str, list[str]]:
    """B27 — ONE BULK CHECK BATCH'S METERS, IN FOUR QUERIES, NOT ~54 AN ACCOUNT.

    Answers, for a batch of up to 500 accounts, the five per-unit and
    per-point questions the Check asks this module one account at a time —
    `assets_on_unit`, `asset_ids_for_service_point`,
    `in_service_asset_ids_for_service_point`, `billable_asset_count` and
    `billable_asset_size_classes` — and PRIMES the batch memo
    (`core.batch_reads`) with each answer, keyed exactly as the per-account
    call will ask it. Outside a batch it primes nothing and answers the map.

    ⚠ **EACH ANSWER IS THE PER-ACCOUNT ANSWER, BYTE FOR BYTE, AND THE ORDER IS
    THE DATABASE'S.** Every list is taken from ONE query carrying the SAME
    `ORDER BY` as its per-account read and then split by unit or point — so the
    relative order inside each split is the database's own collation, never
    Python's. The predicates are the per-account ones, restated here in one
    place per read and held to them by `test_b27_batch_reads` on a mixed seed.

    `unit_codes` is `{unit_id: the service codes of its live service points}`
    (metering's, which owns the points) — the codes the count and size reads
    will be asked about. Returns `{service_point_id: [asset id, …]}` so the
    caller can read the batch's meters' readings in one query too.
    """
    unit_ids = [u for u in unit_codes if u not in (None, "")]
    point_ids = [p for p in service_point_ids if p not in (None, "")]
    tenant_id = _tenant_id()

    # 1 · assets on each service point — `asset_ids_for_service_point`'s order.
    on_point: dict[str, list[str]] = {str(p): [] for p in point_ids}
    in_service: dict[str, list[str]] = {str(p): [] for p in point_ids}
    assets = list(
        models.Asset.objects.filter(tenant_id=tenant_id, service_point_id__in=point_ids)
        .select_related("status", "type", "meter_type")
        .order_by("asset_no", "id")
    )
    parents = set(
        models.Asset.objects.filter(
            tenant_id=tenant_id, parent_asset_id__in=[a.id for a in assets]
        ).values_list("parent_asset_id", flat=True)
    ) if assets else set()
    for asset in assets:
        key = str(asset.service_point_id)
        on_point.setdefault(key, []).append(str(asset.id))
        if (
            asset.status_id is not None
            and asset.status.behavior_class == "in_service"
            and asset.type_id is not None
            and asset.type.category == "meters"
            and asset.parent_asset_id is None
            and asset.id not in parents
        ):
            in_service.setdefault(key, []).append(str(asset.id))
    by_point: dict[str, list[Any]] = {}
    for asset in assets:
        by_point.setdefault(str(asset.service_point_id), []).append(asset)
    for point in point_ids:
        batch_reads.prime(asset_ids_for_service_point, list(on_point.get(str(point), [])), point)
        # `DEF-BIL-10155` / `10156` — the same rows, the same predicate.
        batch_reads.prime(
            billing_asset_ids_for_service_point, _billing_ids(by_point.get(str(point), [])), point
        )
        batch_reads.prime(
            in_service_asset_ids_for_service_point, list(in_service.get(str(point), [])), point
        )

    # 2 · the assets currently on each unit — `assets_on_unit`'s order.
    if unit_ids:
        current: dict[str, set[Any]] = {str(u): set() for u in unit_ids}
        for unit_id, asset_id in models.AssetAssignment.objects.filter(
            tenant_id=tenant_id, unit_id__in=unit_ids, to_date__isnull=True
        ).values_list("unit_id", "asset_id"):
            current.setdefault(str(unit_id), set()).add(asset_id)
        wanted = {a for ids in current.values() for a in ids}
        rows = (
            list(_base_qs().filter(id__in=list(wanted)).order_by("asset_no", "id"))
            if wanted
            else []
        )
        with_children = set(
            models.Asset.objects.filter(
                tenant_id=tenant_id, parent_asset_id__in=[r.id for r in rows]
            ).values_list("parent_asset_id", flat=True)
        ) if rows else set()
        for unit_id in unit_ids:
            mine = current.get(str(unit_id), set())
            batch_reads.prime(
                assets_on_unit,
                [
                    _asset_on_unit_row(asset, has_children=asset.id in with_children)
                    for asset in rows
                    if asset.id in mine
                ],
                unit_id,
            )

        # 3 · in-service assets on each unit ON `as_of`, per service —
        # `billable_asset_count` and `billable_asset_size_classes`, one filter.
        # ⚠ **AND THE SAME FOURTH PREDICATE (`DEF-MET-9037`, PO 2026-10-02):
        # no read device.** This primes the memo the single-unit reads answer
        # from, so a predicate missing here is missing from every bill run —
        # which is exactly how the first cut of that fix went red.
        sizes: dict[tuple[str, str], list[str | None]] = {}
        for unit_id, code, size_class in (
            models.AssetAssignment.objects.filter(
                tenant_id=tenant_id,
                unit_id__in=unit_ids,
                from_date__lte=as_of,
                asset__status__behavior_class="in_service",
            )
            .filter(Q(to_date__isnull=True) | Q(to_date__gte=as_of))
            .exclude(asset__type__category__in=READ_DEVICE_CATEGORIES)
            .order_by("asset__asset_no", "asset_id")
            .values_list("unit_id", "asset__service_point__service__code", "asset__size_class")
        ):
            text = str(size_class).strip() if size_class is not None else ""
            sizes.setdefault((str(unit_id), code), []).append(text or None)
        for unit_id in unit_ids:
            for code in unit_codes.get(unit_id) or ():
                found = sizes.get((str(unit_id), code), [])
                batch_reads.prime(billable_asset_count, len(found), unit_id, code, as_of)
                batch_reads.prime(billable_asset_size_classes, list(found), unit_id, code, as_of)
    return on_point


def in_service_meter_counts_for_points(service_point_ids: Any) -> dict[str, int]:
    """How many IN-SERVICE meters stand on each of these service points — ONE
    query per 900 points (`_ID_CHUNK`), never one per point (`DEF-BIL-5297`).

    Billing's bulk run Scope step (plan B5, PO 2026-09-30) counts **Missing
    meter** — *"a service point connected with no meter — not billed"* — over a
    whole cycle. The only form of this answer was the per-point
    `in_service_asset_ids_for_service_point` above, which at a 40,000-account
    cycle is ~120,000 round trips to draw one number; `DEF-BIL-5297` recorded
    that the figure was served null for exactly that reason and that *"a bulk
    meters-by-service-point read from assets is what fills them in"*. This is
    that read, published by the owner so billing never joins these tables (B1).

    **WHAT COUNTS AS A METER HERE:** category `meters` or `sub_meters`, lifecycle
    stage `in_service` (by `behavior_class`, never the label — BR-AST-031). A
    master meter and a sub-meter each measure the point, so each counts; a
    behind-the-meter device does not measure a billed service and does not. It
    answers *"is anything reading this point"*, which is a different question
    from `in_service_asset_ids_for_service_point`'s *"how many billing lines"*,
    and is deliberately a separate function so neither can drift into the other.

    A point with no such meter is ABSENT from the map (the caller's
    `.get(point_id, 0)` is the same answer). Tenant-scoped (hard rule 1).
    """
    ids = [str(point_id) for point_id in (service_point_ids or ()) if point_id]
    if not ids:
        return {}
    tenant_id = _tenant_id()
    out: dict[str, int] = {}
    for chunk in _chunked(ids):
        rows = (
            models.Asset.objects.filter(
                tenant_id=tenant_id,
                service_point_id__in=chunk,
                status__behavior_class="in_service",
                type__category__in=("meters", "sub_meters"),
            )
            .values("service_point_id")
            .annotate(total=Count("id"))
            .order_by()
        )
        for row in rows:
            out[str(row["service_point_id"])] = int(row["total"])
    return out


def meter_numbers_for_points(service_point_ids: Any) -> dict[str, list[str]]:
    """`{service_point_id: [asset_no, …]}` — the NUMBERS of the in-service
    meters on each point, in `asset_no` order. ONE query per 900 points
    (`_ID_CHUNK`), never one per point.

    `DEF-BIL-8701`: the bulk run's Check rows write a service with its meter,
    *"Water · W-10442"* (D1 11–14), so a clerk reading *No reading* knows which
    meter to go and read. The NUMBER is the business identifier a clerk reads
    off the meter's face; the asset's database id is never the visible value
    (B14 rule 31) and is not served here at all.

    The same predicate as `in_service_meter_counts_for_points` above — category
    `meters` or `sub_meters`, lifecycle stage `in_service` by `behavior_class`
    (BR-AST-031) — so the count Scope draws and the numbers Check names are one
    set. A point with no such meter is ABSENT from the map. Tenant-scoped (hard
    rule 1).
    """
    ids = [str(point_id) for point_id in (service_point_ids or ()) if point_id]
    if not ids:
        return {}
    tenant_id = _tenant_id()
    out: dict[str, list[str]] = {}
    for chunk in _chunked(ids):
        rows = (
            models.Asset.objects.filter(
                tenant_id=tenant_id,
                service_point_id__in=chunk,
                status__behavior_class="in_service",
                type__category__in=("meters", "sub_meters"),
            )
            .exclude(asset_no__isnull=True)
            .exclude(asset_no="")
            .order_by("asset_no", "id")
            .values_list("service_point_id", "asset_no")
        )
        for point_id, asset_no in rows:
            out.setdefault(str(point_id), []).append(asset_no)
    return out


# ── seam surface consumed by the CR-028 import targets (metering's runner) ──
#
# The ONE workflow runner lives in metering (BR-MET-096) and its three assets
# targets validate against facts only this module can state. Each function
# below is a READ, published so the runner never joins this module's tables —
# the same direction `assets_on_unit` already serves, B1's sanctioned path.


def import_lookup_index(list_code: str) -> dict[str, str]:
    """`code` and `name`, both case-folded, → the code — for the runner's
    stage-2 lookup resolution (the `_premises_type_index` shape, read ONCE per
    run per DEF-324's measured reason).

    `device_types` is the BTM slice of `asset_types` (BR-AST-004's category
    partition): the devices target may only name a behind-the-meter kind, so a
    meters-tab type is deliberately NOT in its index.
    """
    from apps.assets import services

    services.ensure_reference_catalogs()
    if list_code == "meter_types":
        rows = models.MeterType.objects.filter(tenant_id=_tenant_id(), active=True)
    elif list_code == "read_methods":
        rows = models.ReadMethod.objects.filter(tenant_id=_tenant_id(), active=True)
    elif list_code == "device_types":
        rows = models.AssetType.objects.filter(
            tenant_id=_tenant_id(), active=True, category="behind_the_meter"
        )
    else:
        return {}
    index: dict[str, str] = {}
    for row in rows:
        index[row.code.lower()] = row.code
        index[row.name.lower()] = row.code
    return index


def reference_list_options(list_code: str) -> list[dict[str, str]]:
    """`[{code, name}]` for one assets-owned reference list, ACTIVE rows only.

    The PICKER shape, beside `import_lookup_index`'s RESOLVER shape. The index
    answers *"is this written word a valid code"*; this answers *"what may a
    person choose"*, which needs the display name and a stable order and which
    an index keyed by two spellings of every row cannot give.

    Added for CR-038 W3 (2026-08-26): BR-MET-123 makes the read SOURCE a tag
    chosen at upload, and the words it is chosen from are THIS
    module's `read_methods` list (BR-AST-043, tenant-extensible per
    BR-TEN-036). S28 belongs to the Billing Clerk (BR-MET-035) and
    `/lookups/read_methods` is System-Admin-only (DEF-196), so the clerk's own
    wizard cannot read the list through Settings - it asks metering, which asks
    here through the documented seam. READ-ONLY: this lane adds no write path
    into another module's tables.

    Ordered SEEDED-FIRST then by code, so the ratified words lead and a
    tenant's own additions follow rather than interleaving alphabetically.
    ⚠ *"the five ratified words"* until 2026-08-27; BR-MET-142 made it EIGHT,
    and the count is not written here any more because the order is read off
    `SEED_READ_METHODS` rather than from a number in a sentence.

    ⚠ **THIS FUNCTION IS ALSO HOW BR-MET-142's THREE NEW WORDS REACH A TENANT
    THAT ALREADY EXISTS**, which is why no migration ships with them: the
    `ensure_reference_catalogs()` call below is a `get_or_create` per seeded
    row, so the first time anybody opens the S28 read-upload picker the missing
    rows are created. Deleting that call would turn the fixture serial bump
    into the ONLY delivery path and leave any tenant that never sweeps on five.
    """
    from apps.assets import services

    services.ensure_reference_catalogs()
    flat = {"meter_types": models.MeterType, "read_methods": models.ReadMethod}.get(list_code)
    if flat is None:
        return []
    seed_order = {
        "meter_types": [code for code, _name in services.SEED_METER_TYPES],
        "read_methods": [code for code, _name in services.SEED_READ_METHODS],
    }[list_code]
    rows = flat.objects.filter(tenant_id=_tenant_id(), active=True)
    return [
        {"code": row.code, "name": row.name}
        for row in sorted(
            rows,
            key=lambda r: (
                seed_order.index(r.code) if r.code in seed_order else len(seed_order),
                r.code,
            ),
        )
    ]


def asset_import_index() -> dict[str, dict[str, Any]]:
    """Every asset on file, keyed by its LOWERED user number — the import's
    existing-row index (`_existing_index`'s shape for the assets targets).

    ⚠ **AND, SINCE 2026-08-27, A SECOND KEY PER ROW: `ext:<lowered
    external_ref>` (BR-AST-049).** The same dict carries both, namespaced so
    they cannot collide; the reason is written at the assignment below.

    Carries what the runner's dry run, load and rules need and nothing more:
    the id (to address a spec update), the exact number (for sentences), the
    behavior class (a rule about an ACTIVE master must not accept a retired
    one), the type code (only a meter/net_meter may parent a sub), and the
    CURRENT seat (`unit_id`, None when unassigned) — the sub-meters
    same-premises warning compares the master's seat to the sub's.

    ⚠ Two queries TOTAL, never one per asset (DEF-324): the seats are read in
    one pass over the open assignment rows and joined in memory.
    """
    seats = {
        str(asset_id): str(unit_id)
        for asset_id, unit_id in models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(), to_date__isnull=True
        ).values_list("asset_id", "unit_id")
    }
    index: dict[str, dict[str, Any]] = {}
    rows = models.Asset.objects.filter(tenant_id=_tenant_id()).select_related(
        "status", "type", "service_point__service"
    )
    for row in rows:
        entry = {
            "id": str(row.id),
            "asset_no": row.asset_no,
            "external_ref": row.external_ref,
            "behavior_class": row.status.behavior_class,
            "type_code": row.type.code,
            "unit_id": seats.get(str(row.id)),
            # ⛔ Plan U4 (PO 2026-09-30) — the service a parent MEASURES, so a
            # sub-meter or a device naming it can be refused when the two
            # differ (`AST.PARENT_SAME_SERVICE`). Through the service point, as
            # `billable_asset_count` reads it; `None` for an inventory asset,
            # whose service has no column to live in. Same query, one join.
            "service_code": (
                row.service_point.service.code if row.service_point_id else None
            ),
        }
        index[str(row.asset_no).strip().lower()] = entry
        # ── THE SERIAL, AND IT IS THE ONE KEY THAT CAN BE AMBIGUOUS ────────
        # A sub-meter's file names its master, and after the 2026-08-27 ruling
        # a first migration's file cannot name it by OUR number — we issued
        # that number a minute earlier and the operator has never seen it. The
        # serial is one of the two things such a file does hold.
        #
        # ⚠ **`BR-AST-033` MAKES A DUPLICATE SERIAL WARN-BUT-ALLOW**, so two
        # masters may legitimately carry one. A resolver that took the first
        # would hang a sub-meter off the WRONG device, and the only symptom
        # would be a wrong bill months later. So a serial claimed twice is
        # recorded as AMBIGUOUS here and refused by name at the rule, rather
        # than silently resolving.
        serial = str(row.serial_no or "").strip().lower()
        if serial:
            key = f"serial:{serial}"
            held = index.get(key)
            if held is None:
                index[key] = entry
            else:
                names = sorted(
                    {*(held.get("ambiguous_asset_nos") or [held["asset_no"]]), row.asset_no}
                )
                index[key] = {"ambiguous": True, "ambiguous_asset_nos": names}
        # ── BR-AST-049 — THE SECOND KEY, AND WHY IT IS IN THE SAME DICT ─────
        # Under the PO ruling of 2026-08-27 a meter's number is ISSUED by the
        # tenant's series and never taken from a file, so the operator's FIRST
        # migration file carries no `asset_no` at all. Their correction re-run
        # then matches nothing: every row reads as new, and `AST.UNIT_SERVICE_
        # FREE` rejects the lot with *"this unit already has an active water
        # meter"*. Their own legacy reference is the only identifier such a
        # file has, and it is UNIQUE per tenant, so it is a lawful match key.
        #
        # ⚠ **NAMESPACED, NEVER MERGED.** A legacy `M-9001` and one of OUR
        # `M-9001`s must not collide in one flat dict — that would let a
        # legacy string silently address a different asset. The prefix makes
        # the two key spaces disjoint, and `_key_of` builds the same shape.
        if row.external_ref:
            index[f"ext:{str(row.external_ref).strip().lower()}"] = entry
    return index


def active_service_assignments() -> list[dict[str, str]]:
    """`(unit_id · service · asset_no)` for every CURRENTLY assigned, in-service
    METER — the "unit already has an active electric meter" rule's world
    (r10 WFL-01.meters.3 row 588; B16 §4.7a).

    Sub-meters are EXCLUDED on purpose: a sub coexists with the unit's own
    meter by design (the seeded registry holds exactly that shape), and r10's
    sentence names "an active … meter". Devices carry no service at all.
    """
    rows = (
        models.AssetAssignment.objects.filter(tenant_id=_tenant_id(), to_date__isnull=True)
        .select_related("asset", "asset__status", "asset__type", "asset__service_point__service")
        .filter(
            asset__status__behavior_class="in_service",
            asset__type__code__in=("meter", "net_meter"),
        )
    )
    out: list[dict[str, str]] = []
    for row in rows:
        service_point = row.asset.service_point
        if service_point is None or service_point.service is None:
            continue
        out.append(
            {
                "unit_id": str(row.unit_id),
                "service": service_point.service.code,
                "asset_no": row.asset.asset_no,
            }
        )
    return out


def current_unit_for_asset(asset_id: Any) -> str | None:
    """The unit an asset currently sits on, or None — the sub-meters target's
    "unit same premises as master" warning reads the MASTER's seat this way."""
    unit_id = (
        models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(), asset_id=asset_id, to_date__isnull=True
        )
        .values_list("unit_id", flat=True)
        .first()
    )
    return str(unit_id) if unit_id else None


# ═══ CR-028 AST-W5 — the three new tabs' reads (B16 §4.4–§4.6) ══════════════
#
# One posture for all three: AGGREGATES over this module's own rows plus the
# documented metering seams, money at its stored 4 dp (display trims to 2 —
# rule 2), and NULL wherever a figure would be dishonest ("nobody recorded a
# cost" must never render as $0.00). No GL account, no posting sentence, no
# work-order fact anywhere (§10-D3/D7); no reorder/van/yard fact (§10-D5).


def _representative_cost(
    assets: list[models.Asset],
) -> tuple[str | None, str | None, str | None]:
    """(unit_cost · min · max) for one type's assets.

    JUDGMENT, DOCUMENTED (the D5 build instruction left it to the lane): the
    representative unit cost is the cost of the LATEST purchase — what
    restocking the type would cost today, which is the question the Inventory
    tab answers — with the min/max range served beside it whenever costs vary
    so the screen can show the spread instead of implying uniformity. A
    dateless cost sorts earliest, so any dated purchase beats it. None when
    no asset in the group carries a cost."""
    costed = sorted(
        (
            (asset.purchase_date or date.min, asset.purchase_cost)
            for asset in assets
            if asset.purchase_cost is not None
        ),
        key=lambda pair: (pair[0], pair[1]),
    )
    if not costed:
        return (None, None, None)
    values = [cost for _, cost in costed]
    return (_money_str(costed[-1][1]), _money_str(min(values)), _money_str(max(values)))


def stock_view(
    *, today: date | None = None, page: Any = 1, per: Any = WINDOW_DEFAULT_PER
) -> dict[str, Any]:
    """AST-01.inventory (§10-D5 RULED: counts & costs ONLY) — the aggregate
    behind `GET /assets/stock`.

    Uninstalled = behavior CLASS `available` (BR-AST-031 — never the label).
    Aged = 12 whole months elapsed since purchase (the same `add_months`
    arithmetic every other cadence here uses). The KPI's "$ at cost" is the
    sum of the KNOWN purchase costs; a costless asset counts and prices as
    null — visible as a dash on its row, never a fabricated $0.00.

    ⚠ The per-row `services` list is HONEST-EMPTY for never-assigned stock:
    the schema records an asset's service only through the service point
    minted at assignment, so a spare that has never stood anywhere has no
    service on record — r10's per-stock-line service tag has no data source
    (reported in the lane close-out, not invented here)."""
    # ── `DEF-MET-4962` remainder · `NFR-3` ─────────────────────────────────
    #
    # ⚠ **THE THREE KPI FIGURES ARE COMPUTED IN SQL AND NOT OVER A MATERIALISED
    # ESTATE.** The count, the value at cost and the aged count used to be
    # `len()` and two Python loops over every uninstalled asset in the tenant,
    # which is a whole-estate pass to print three numbers. `aged` is the same
    # clamped-month comparison `test_due_q` already had to solve — a purchase
    # twelve whole months old — so it is spelled the same way, in whole months
    # with the recorded day compared against today's, and it is TESTED against
    # the Python derivation rather than assumed to agree with it.
    #
    # ⚠ **AND THE `services` CELL WAS A QUERY PER ROW.** `_service_of(asset)` is
    # a metering seam read, and it sat inside the per-type comprehension — the
    # same `DEF-MET-4951` shape wave B removed from the registry list and the
    # map, still standing here because a demo tenant holds eight spare meters
    # and nobody noticed eight lookups. It is ONE batched call now, for every
    # service point in stock at once.
    #
    # The per-type roll-up still walks the whole available set in PYTHON, and
    # that is stated rather than implied: the row count is bounded by the TYPE
    # CATALOGUE and the payload by the window, but the grouping pass is O(the
    # stock). It walks a three-column `values_list` instead of building a model
    # instance per asset, which is the cheap half of the fix; the expensive half
    # is a stored roll-up, and that is a schema decision rather than this lane's.
    when = today or seams.tenant_today()
    available = _base_qs().filter(status__behavior_class=AVAILABLE)
    kpi_count = available.count()
    kpi_value = available.aggregate(total=Sum("purchase_cost"))["total"]
    aged_annotations, aged_predicate = _aged_q(when, months=12)
    kpi_aged = available.annotate(**aged_annotations).filter(aged_predicate).count()

    stock_rows = list(
        available.values_list(
            "type__code",
            "type__name",
            "type__category",
            "purchase_date",
            "purchase_cost",
            "supplier",
            "service_point_id",
        )
    )
    # ONE seam call for every service point in stock, never one per asset.
    services_by_point = seams.service_codes_for_points(
        [point_id for *_, point_id in stock_rows if point_id]
    )

    groups: dict[str, list[tuple]] = {}
    labels: dict[str, tuple[str, str]] = {}
    for row in stock_rows:
        code = row[0]
        groups.setdefault(code, []).append(row)
        labels.setdefault(code, (row[1], row[2]))

    rows: list[dict[str, Any]] = []
    for type_code in sorted(groups, key=lambda code: labels[code][0]):
        members = groups[type_code]
        type_name, category = labels[type_code]
        # `_representative_cost`'s rule, over tuples: the LATEST dated purchase
        # is the representative unit cost, a dateless cost sorts earliest, and
        # the min/max ride beside it so a screen shows the spread instead of
        # implying uniformity. Kept here in the same order the function used, so
        # the two cannot answer differently for the same stock.
        costed = sorted(
            ((pdate or date.min, cost) for _c, _n, _t, pdate, cost, _s, _p in members
             if cost is not None),
            key=lambda pair: (pair[0], pair[1]),
        )
        values = [cost for _, cost in costed]
        unit_cost = _money_str(costed[-1][1]) if costed else None
        cost_min = _money_str(min(values)) if values else None
        cost_max = _money_str(max(values)) if values else None
        rows.append(
            {
                "type": type_code,
                "type_name": type_name,
                "tab": category,  # the drill's registry tab
                "count": len(members),
                "unit_cost": unit_cost,
                "unit_cost_min": cost_min,
                "unit_cost_max": cost_max,
                "value": _money_str(sum(values, Decimal("0"))) if values else None,
                "suppliers": sorted({row[5] for row in members if row[5]}),
                "services": sorted(
                    {
                        service
                        for service in (
                            services_by_point.get(str(row[6])) if row[6] else None
                            for row in members
                        )
                        if service
                    }
                ),
            }
        )

    page_rows, window = page_window(rows, page=page, per=per)
    return {
        "kpis": {
            "uninstalled": kpi_count,
            # `None` — never `$0.00` — when nothing in stock carries a cost:
            # "nobody recorded a cost" and "it is worth nothing" are different
            # claims, and the second one is never ours to make (BR-RAT-021's
            # discipline applied to a display).
            "value_at_cost": _money_str(kpi_value) if kpi_value is not None else None,
            "aged_over_12_months": kpi_aged,
            "currency": seams.tenant_currency(),
        },
        "rows": list(page_rows),
        "rows_window": window,
    }


#: The due-soon window (r10 draws "Due in 17 days"; ≤ 30 days is the warn band).
DUE_SOON_DAYS = 30


def _requirement_of(asset: models.Asset) -> dict[str, Any]:
    """The Requirement cell, DERIVED FROM DATA — never a hardcoded per-asset
    string (the lane instruction's own words). 12-month cadence = an annual
    test (r10: "Annual test · state mandated" on backflows); any cadence on a
    MEASURING asset = accuracy recertification (BR-AST-027's 96-month meter
    seed is r10's own "Accuracy recertification" row); another cadence on a
    device = a periodic test of its interval; an explicit certification_due
    with no cadence = a certification (r10's "Interconnection inspection"
    wording names a regulation no column records — the honest generic)."""
    interval = asset.test_interval_months
    if interval == 12:
        kind = "annual_test"
    elif interval and asset.type.category in ("meters", "sub_meters"):
        kind = "accuracy_recertification"
    elif interval:
        kind = "periodic_test"
    else:
        kind = "certification"
    return {"kind": kind, "interval_months": int(interval) if interval else None}


def _premises_addresses(assets: list[models.Asset]) -> dict[str, str | None]:
    """asset id → its current premises address, TWO queries + one seam read
    per distinct unit (DEF-324 — never one lookup per asset)."""
    seats = {
        str(asset_id): str(unit_id)
        for asset_id, unit_id in models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(),
            to_date__isnull=True,
            asset_id__in=[a.id for a in assets],
        ).values_list("asset_id", "unit_id")
    }
    address_by_unit: dict[str, str | None] = {}
    for unit_id in set(seats.values()):
        address_by_unit[unit_id] = (seams.unit_ref(unit_id) or {}).get("premise_address")
    return {
        str(asset.id): address_by_unit.get(seats.get(str(asset.id), ""), None) for asset in assets
    }


def lifecycle_view(
    *, today: date | None = None, page: Any = 1, per: Any = WINDOW_DEFAULT_PER
) -> dict[str, Any]:
    """AST-01.lifecycle (§10-D3 RULED) — three derived lists + the Asset value
    panel behind `GET /assets/lifecycle`, in ONE call (B16 §4.8's contract).

    NO finance sidebar: no depreciation-for-the-month, no GL account, no
    posting sentence — the D3 ruling replaced r10's "Cost to Finance" with an
    "Asset value" panel computed from the device records (BR-AST-047), and
    the tests assert the ABSENCE of every banned string."""
    when = today or seams.tenant_today()
    fleet_qs = _base_qs().exclude(status__behavior_class=TERMINAL)
    fleet = list(fleet_qs)

    # 1 · Certifications & tests due — soonest first. Only rows with a
    # COMPUTABLE due date appear: an asset with a cadence but no test on
    # record has nothing derivable, and an invented date would be worse than
    # its absence (it stays findable via the registry's test-due filter).
    # ── `DEF-MET-4962` remainder · `NFR-3` — the ONE list here that grows
    # with the ESTATE is this one, and it is the one that gets a window.
    #
    # The other two are catalogue-shaped: warranty groups key off (type,
    # supplier) and the forecast off type, so both are bounded by how many kinds
    # of thing a utility buys rather than by how many it owns. They are served
    # whole, deliberately, and this comment is the argument rather than an
    # oversight — a page over a four-row roll-up is furniture.
    #
    # ⚠ **THE FILTER IS SQL AND THE SORT IS PYTHON, AND THAT IS A DELIBERATE
    # SPLIT WITH A COST I AM NAMING.** *Has a computable due date* is exactly
    # expressible — an explicit `certification_due`, or a `last_test_date` with
    # a positive cadence — so the ROWS this list may contain are narrowed in the
    # database. Ordering them is the clamped-month problem again
    # (`next_test_date` is `add_months(last_test_date, n)` for most rows) and an
    # ORDER BY that disagreed with the derivation would put a row on the wrong
    # PAGE, which is worse than a slow sort: the row would be missing from one
    # page and duplicated on another, invisibly. So the cadenced set is sorted
    # in Python and then windowed. The residue is real and bounded by the
    # CADENCED population rather than by the estate — on a 40,000-asset utility
    # where every meter has a test cadence that is still 40,000 rows sorted to
    # serve fifty, and closing it needs the clamped due date as a stored
    # column, which is a schema change and not this lane's call. Stated, not
    # smoothed over (hard-won law 1).
    cadenced_qs = fleet_qs.filter(
        Q(certification_due__isnull=False)
        | (Q(last_test_date__isnull=False) & Q(test_interval_months__gt=0))
    )
    cadenced = [a for a in cadenced_qs if next_test_date(a) is not None]
    addresses = _premises_addresses(cadenced)
    certifications: list[dict[str, Any]] = []
    for asset in cadenced:
        due = date.fromisoformat(next_test_date(asset))  # type: ignore[arg-type]
        days = (due - when).days
        if days < 0:
            status = "overdue"
        elif days <= DUE_SOON_DAYS:
            status = "due_soon"
        elif asset.certification_due:
            status = "scheduled"  # an EXPLICIT booked date beyond the window
        else:
            status = "in_date"  # derived cadence, comfortably out
        certifications.append(
            {
                "id": str(asset.id),
                "asset_no": asset.asset_no,
                "type": asset.type.code,
                "type_name": asset.type.name,
                "premises": addresses.get(str(asset.id)),
                "requirement": _requirement_of(asset),
                "due": due.isoformat(),
                "days_until": days,
                "status": status,
            }
        )
    certifications.sort(key=lambda row: (row["due"], row["asset_no"]))
    certifications_page, certifications_window = page_window(certifications, page=page, per=per)

    # 2 · Warranty & supplier — grouped by (type, supplier); an asset with no
    # supplier on record belongs to no group (nothing to write to a supplier
    # about). Status follows the LATEST cover in the group.
    warranty_groups: list[dict[str, Any]] = []
    by_supplier: dict[tuple[str, str], list[models.Asset]] = {}
    for asset in fleet:
        if asset.supplier:
            by_supplier.setdefault((asset.type.code, asset.supplier), []).append(asset)
    for (type_code, supplier), members in sorted(by_supplier.items()):
        covers = [a.warranty_end for a in members if a.warranty_end]
        cover_ends = max(covers) if covers else None
        warranty_groups.append(
            {
                "type": type_code,
                "type_name": members[0].type.name,
                # `DEF-MET-4955` · screens 05b/05c: the row's View action opens the
                # REGISTRY filtered to this group, and a registry filter needs a
                # TAB. The category is the one honest answer and the client
                # cannot derive it — a battery group is not on the meters tab.
                # `stock_view` has carried exactly this field, for exactly this
                # drill, since CR-028 AST-W5 T1.
                "tab": members[0].type.category,
                "supplier": supplier,
                "units": len(members),
                "cover_ends": cover_ends.isoformat() if cover_ends else None,
                "under_warranty": sum(
                    1 for a in members if a.warranty_end and a.warranty_end >= when
                ),
                "status": (
                    None if cover_ends is None else ("covered" if cover_ends >= when else "expired")
                ),
            }
        )

    # 3 · Age & replacement forecast — by type. Age counts from install
    # (purchase for never-installed stock — the B16 §5.1b base every other
    # age here uses); "due within 12 months" INCLUDES what is already past
    # life. Replacement cost = due count × the latest unit cost, null when
    # either half is missing — never a fabricated programme dollar.
    by_type: dict[str, list[models.Asset]] = {}
    for asset in fleet:
        by_type.setdefault(asset.type.code, []).append(asset)
    forecast_rows: list[dict[str, Any]] = []
    programme_units = 0
    programme_cost = Decimal("0")
    programme_priced = False
    for type_code in sorted(by_type, key=lambda code: by_type[code][0].type.name):
        members = by_type[type_code]
        ages = [
            _months_between(a.install_date or a.purchase_date, when)
            for a in members
            if a.install_date or a.purchase_date
        ]
        lives = [a.expected_life_years for a in members if a.expected_life_years]
        life_years = None
        if lives:
            counts: dict[int, int] = {}
            for years in lives:
                counts[years] = counts.get(years, 0) + 1
            life_years = max(counts, key=lambda years: (counts[years], -years))
        past_life = 0
        due_within = 0
        for asset in members:
            base = asset.install_date or asset.purchase_date
            if base is None or not asset.expected_life_years:
                continue
            age = _months_between(base, when)
            life_months = int(asset.expected_life_years) * 12
            if age > life_months:
                past_life += 1
            if age > life_months - 12:
                due_within += 1
        unit_cost, _min_cost, _max_cost = _representative_cost(members)
        replacement = (
            _money_str(Decimal(unit_cost) * due_within)
            if unit_cost is not None and due_within > 0
            else None
        )
        forecast_rows.append(
            {
                "type": type_code,
                "type_name": members[0].type.name,
                # `DEF-MET-4955` — the drill's tab, as on the warranty group above.
                "tab": members[0].type.category,
                "avg_age_months": (sum(ages) // len(ages)) if ages else None,
                "expected_life_years": life_years,
                "past_life": past_life,
                "due_within_12mo": due_within,
                "replacement_cost": replacement,
            }
        )
        programme_units += due_within
        if replacement is not None:
            programme_cost += Decimal(replacement)
            programme_priced = True

    # 4 · The Asset value panel (D3's replacement for r10's finance sidebar):
    # buy + present value COMPUTED FROM THE DEVICE RECORDS (BR-AST-047) —
    # the same asset_book_value retire records and the detail serves.
    buy_total = Decimal("0")
    bought = False
    present_total = Decimal("0")
    valued = False
    for asset in fleet:
        if asset.purchase_cost is not None:
            buy_total += asset.purchase_cost
            bought = True
        book = asset_book_value(asset, as_of=when)
        if book is not None:
            present_total += Decimal(book["book_value"])
            valued = True

    return {
        "certifications": list(certifications_page),
        "certifications_window": certifications_window,
        "warranty_groups": warranty_groups,
        "age_forecast": {
            "rows": forecast_rows,
            "programme": {
                "units": programme_units,
                "cost": _money_str(programme_cost) if programme_priced else None,
            },
        },
        "asset_value": {
            "buy_value": _money_str(buy_total) if bought else None,
            "present_value": _money_str(present_total) if valued else None,
            "currency": seams.tenant_currency(),
        },
    }


def geo_view(*, page: Any = 1, per: Any = WINDOW_DEFAULT_PER) -> dict[str, Any]:
    """AST-03 (§10-D6 RULED) — every non-retired asset standing on a GEOCODED
    premises, behind `GET /assets/geo`.

    Coordinates ride as their stored NUMERIC(9,6) strings. The popup card's
    facts (BR-AST-026: the uuid only ADDRESSES the "Open details →" link,
    `asset_no` is what a human reads) and the filter bar's vocabularies
    (category · behavior class · service · the premises' BR-MET-071 area)
    all travel on the row. NO work-order fact anywhere (§10-D7: Work is R5;
    r10's `WO-####` popup lines are omitted, not faked)."""
    # ── `DEF-MET-4962` remainder · `NFR-3` — THE MAP ANSWERS A PAGE ─────────
    #
    # The order below is the fix, and it reads backwards from what it replaced.
    # It used to build a dict for EVERY geocoded unit in the tenant, then find
    # every asset standing on one, then materialise all of them — three
    # whole-estate passes to draw markers nobody had asked for yet. Now it asks
    # which units are placed (ids only), narrows the ASSETS in SQL, takes the
    # page, and only then asks for the placement detail of that page's units.
    #
    # ⚠ **WHAT THIS DOES NOT DO, NAMED RATHER THAN LEFT TO BE DISCOVERED: IT IS
    # STILL A PAGE AND NOT A VIEWPORT.** `DEF-MET-4301` says what a map actually
    # wants — *"the server takes the bounds it is drawing and answers what is
    # inside them, with a count of what it left outside"* — and it is right: a
    # map of page 1 of 3 is a map of the wrong day. That is a CHANGE to what the
    # map screen does and it belongs with the screen; this bounds the payload so
    # the tab cannot hand a browser 21 MB in the meantime, and `total` is exactly
    # the figure a *"and 38,400 more"* line needs. `DEF-MET-4301` stays OPEN.
    placed_units = seams.geocoded_unit_ids()
    if not placed_units:
        # Through `page_window` rather than a hand-built dict, so `per` is
        # CLAMPED here exactly as it is on every other path — a literal
        # `"per": per` would hand back the caller's raw string on the one
        # branch nobody looks at.
        _empty, window = page_window([], page=page, per=per)
        return {"assets": [], "assets_window": window}
    seats = {
        str(asset_id): str(unit_id)
        for asset_id, unit_id in models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(), to_date__isnull=True, unit_id__in=placed_units
        ).values_list("asset_id", "unit_id")
    }
    marked = (
        _base_qs()
        .filter(id__in=list(seats))
        .exclude(status__behavior_class=TERMINAL)
        .order_by("asset_no", "id")
    )
    page_qs, window = page_window(marked, page=page, per=per)
    rows = list(page_qs)
    # Sub-counts for THIS PAGE's masters only — the loop used to walk every
    # parented asset in the tenant to answer a question about fifty of them.
    sub_counts: dict[str, int] = {}
    for parent_id in models.Asset.objects.filter(
        tenant_id=_tenant_id(), parent_asset__in=[asset.id for asset in rows]
    ).values_list("parent_asset_id", flat=True):
        key = str(parent_id)
        sub_counts[key] = sub_counts.get(key, 0) + 1
    geo = seams.unit_premises_geo_index([seats[str(asset.id)] for asset in rows])
    reads = seams.latest_reads_for_assets([asset.id for asset in rows])
    # ⚠ **THE TWO PER-ROW COSTS THIS LOOP USED TO PAY (`DEF-MET-4962`).**
    # `_service_of(asset)` is TWO metering round trips per marker and
    # `test_due(asset)` asks the seam for the tenant's today once per marker.
    # Measured on `pine-hill`: `geo_view` cost **241 queries** for 110 markers,
    # and step 1 could not see it at all because `brazosbend` has no geocoded
    # premises — its "1 query" reading was the function returning at its first
    # branch. Both are now asked ONCE for the whole set.
    services = seams.service_codes_for_points(
        [asset.service_point_id for asset in rows if asset.service_point_id]
    )
    when = seams.tenant_today()

    out: list[dict[str, Any]] = []
    for asset in rows:
        place = geo.get(seats[str(asset.id)])
        if place is None:
            # The unit lost its point between the id read and the detail read.
            # Dropping the marker is the honest answer — a pin at a guessed
            # coordinate is worse than no pin (BR-AST-026's posture).
            continue
        if asset.parent_asset_id:
            role: dict[str, Any] = {"kind": "sub", "parent": asset.parent_asset.asset_no}
        elif sub_counts.get(str(asset.id), 0) > 0:
            role = {"kind": "master", "count": sub_counts[str(asset.id)]}
        else:
            role = {"kind": "standard"}
        out.append(
            {
                "id": str(asset.id),
                "asset_no": asset.asset_no,
                "tab": asset.type.category,
                "type": asset.type.code,
                "type_name": asset.type.name,
                "role": role,
                "service": services.get(str(asset.service_point_id)),
                "status": asset.status.code,
                "status_name": asset.status.name,
                "behavior_class": asset.status.behavior_class,
                # BR-AST-007's derived state — the legend's "test due" half of
                # needs-attention (never a stored status).
                "test_due": test_due(asset, today=when),
                "lat": place["lat"],
                "lng": place["lng"],
                # CR-089 wave A `PUJ-49` · `BR-MET-1162` — WHICH point this pin
                # is. Metering decides it (`selectors.unit_point` is the one
                # definition of the fallback) and this forwards the answer; the
                # ruling requires any screen showing a point to say which of the
                # two it is showing, and a map is such a screen.
                "point_source": place["point_source"],
                "premises": place["premises"],
                "unit": place["unit"],
                "area": place["area"],
                "last_read": reads.get(str(asset.id)),
            }
        )
    return {"assets": out, "assets_window": window}


def unit_ids_for_asset_search(term: str) -> list[str]:
    """US-MET-002 TC-4: the S15 search finds a unit by its meter number."""
    asset_ids = list(
        models.Asset.objects.filter(tenant_id=_tenant_id(), asset_no__icontains=term).values_list(
            "id", flat=True
        )
    )
    return [
        str(unit_id)
        for unit_id in models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(), asset_id__in=asset_ids, to_date__isnull=True
        ).values_list("unit_id", flat=True)
    ]


def meter_lifecycle_census(*, today: date | None = None) -> list[dict[str, Any]]:
    """EVERY measuring asset with the two dates runbook 28 asks about — ONE query.

    Added for `CR-075` runbook 28, *Meters past change-out age or never tested*.
    `meter_census` above answers *which meters stand where* and carries no date
    at all; this answers *how old is it and when was it last tested*, which is a
    different set of columns over the same rows. They are two functions rather
    than one widened function because `meter_census` is on the hot path of two
    estate-wide Checks and does not need to select `install_date`,
    `expected_life_years`, `last_test_date`, `test_interval_months` or
    `certification_due` to answer its own question.

    ⚠ **THE AGE BASE IS `install_date` AND FALLS BACK TO `purchase_date`, WHICH
    IS `lifecycle_view`'s OWN BASE AND NOT A SECOND RULE** (B16 §5.1b — *"age
    counts from install (purchase for never-installed stock)"*). Two answers to
    *how old is this meter* would let the Assets screen and this runbook
    disagree about the same box in the same yard, which is the whole reason the
    base is stated here rather than re-derived by the caller.

    ⚠ **`expected_life_years` IS THE METER'S OWN CHANGE-OUT AGE AND MAY BE
    `None`, AND THE `None` IS THE POINT.** A meter with no expected life
    recorded can never be found by an age rule, so the caller must be able to
    COUNT them — a runbook reporting *"0 past change-out age"* over a fleet that
    records no lives at all is a clean bill of health that is a lie (hard-won
    law 7: a declared blind spot with no number beside it is indistinguishable
    from an empty one). Nothing is defaulted here.

    ⚠ **`is_sample` AND THE LIFECYCLE STATUS TRAVEL RATHER THAN BEING FILTERED
    AWAY** — the same posture `meter_census` records: a guard applied inside a
    read cannot be SEEN on the screen that draws it (`BR-RBS-012`), and a meter
    in the store room legitimately stands on nothing and has never been tested.
    `behavior_class` is what tells a retired meter from a live one, so it
    crosses and the caller decides.
    """
    when = today or seams.tenant_today()
    rows = (
        models.Asset.objects.filter(
            tenant_id=_tenant_id(), type__category__in=("meters", "sub_meters")
        )
        .select_related("type", "status")
        .order_by("asset_no", "id")
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        base = row.install_date or row.purchase_date
        life_years = int(row.expected_life_years) if row.expected_life_years else None
        age_months = _months_between(base, when) if base is not None else None
        out.append(
            {
                "asset_id": str(row.id),
                "asset_no": row.asset_no,
                "category": row.type.category if row.type_id else None,
                "type_code": row.type.code if row.type_id else None,
                "type_name": row.type.name if row.type_id else None,
                "status": row.status.code if row.status_id else None,
                "behavior_class": row.status.behavior_class if row.status_id else None,
                "service_point_id": (
                    str(row.service_point_id) if row.service_point_id else None
                ),
                "is_sample": bool(getattr(row, "is_sample", False)),
                # The age half. `age_base` says WHICH date was used, so a screen
                # can say "installed" or "purchased" rather than implying one.
                "install_date": row.install_date.isoformat() if row.install_date else None,
                "purchase_date": row.purchase_date.isoformat() if row.purchase_date else None,
                "age_base": (
                    None if base is None else ("install" if row.install_date else "purchase")
                ),
                "age_months": age_months,
                "expected_life_years": life_years,
                "retire_date": row.retire_date.isoformat() if row.retire_date else None,
                # The test half. `next_test` is the SHARED derivation
                # (`next_test_date` above): the explicit `certification_due`
                # wins when captured, else `last_test_date + interval`. A caller
                # that recomputed it would be a second answer to the question
                # the Assets registry already draws in its Next-test column.
                "last_test_date": (
                    row.last_test_date.isoformat() if row.last_test_date else None
                ),
                "test_interval_months": (
                    int(row.test_interval_months) if row.test_interval_months else None
                ),
                "certification_due": (
                    row.certification_due.isoformat() if row.certification_due else None
                ),
                "next_test": next_test_date(row),
                "test_overdue": test_due(row, today=when),
            }
        )
    return out


def meter_census() -> dict[str, Any]:
    """EVERY measuring asset, by the service point it stands on — ONE query.

    Added for `CR-075` wave S: runbook 19 asks *which meters stand nowhere*
    (step 3) and runbook 18 asks *which premises have a meter at all* (step 1),
    and both are estate-wide questions. `asset_ids_for_service_point` answers
    one point at a time, so metering's census would have been one query per
    service point — 40,000 round trips at the top of the ICP for a Check a
    clerk presses on demand (the cost `runbooks/seams/metering_seam.py` already
    states of `service_point_graph` and does not need to repeat).

    ⚠ **`without_a_service_point` IS A METER THAT CANNOT BE BILLED, NOT AN
    ERROR ROW.** A meter in the store room legitimately stands on nothing;
    `BR-AST-005`'s `uninstalled` status is what tells the two apart, so the
    STATUS travels and the caller decides. A selector that decided here would
    be metering's rule living in assets.

    ⚠ **`is_sample` TRAVELS RATHER THAN BEING FILTERED AWAY** — the same
    posture `metering.selectors.premises_reconciliation_set` records: a guard
    applied inside a read cannot be SEEN on the screen that draws it
    (`BR-RBS-012`).
    """
    rows = (
        models.Asset.objects.filter(tenant_id=_tenant_id())
        .select_related("type", "status")
        .order_by("asset_no", "id")
    )
    by_point: dict[str, list[dict[str, Any]]] = {}
    orphans: list[dict[str, Any]] = []
    for row in rows:
        fact = {
            "asset_id": str(row.id),
            "asset_no": row.asset_no,
            "category": row.type.category if row.type_id else None,
            "type_code": row.type.code if row.type_id else None,
            "status": row.status.code if row.status_id else None,
            "service_point_id": str(row.service_point_id) if row.service_point_id else None,
            "is_sample": bool(getattr(row, "is_sample", False)),
        }
        if row.service_point_id:
            by_point.setdefault(str(row.service_point_id), []).append(fact)
        else:
            orphans.append(fact)
    return {"by_service_point": by_point, "without_a_service_point": orphans}

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-001@9d8d058 (story+rules snapshot hash — EP-AST-01 registry story; co-packets EP-AST-02/03/04@9d8d058)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-09 by story-coder (BR-AST-043 reference-data gap lane — meter_types + read_methods) · AMENDED 2026-08-09 by story-coder (BR-AST-044 both-classifications lane) · AMENDED 2026-08-22 by the CR-028 AST-W1 lane (the r10 registry columns: service/export_capacity_kw/warranty_end/next_test on every row, sub_count on meters, last_read+parent_premises on sub-meters (DEF-592 via the metering seam); test_due refactored onto _interval_due_date, semantics unchanged) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (the CR-028 import seam reads: import_lookup_index, asset_import_index, active_service_assignments, current_unit_for_asset) · AMENDED 2026-08-22 by the CR-028 AST-W2 lane (see the second Change block: detail valuation/lifecycle/linked_meter, names not uuids, maintenance cost + lifetime total, asset_reads — tests in tests/test_cr028_ast_w2_detail.py, RED first) · AMENDED 2026-08-22 by the CR-028 AST-W4 lane (asset_book_value — the ONE straight-line computation retire records and the valuation block serves (D3/D4/BR-AST-047; the $19.8167-vs-r10's-$19.83 verdict is stated on the function and pinned in tests/test_cr028_valuation.py); valuation gains present_value/accumulated_depreciation/age·life months + the recorded book_value pair; add_months factored out of _interval_due_date for the T5 next-due roll; asset_no_preview/asset_no_available — the AST-05 number probe, a PEEK never an allocation) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (stock_view/lifecycle_view/geo_view — the three new tab reads (B16 §4.4–§4.6, D3/D5/D7 honoured by construction and asserted by tests/test_cr028_new_tabs.py, RED first); asset_list gains the reserved `uninstalled` status value — behavior class `available`, the Inventory drill's landing state; geo rows carry test_due for the map's needs-attention state)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ migrate-from-empty✔ makemigrations --check✔ · suite `pytest tests -m "not golden and not isolation"` 587 passed / 8 skipped (580 baseline green + the 7 new BR-AST-043 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (13 baseline + 1 new) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · migration 0003 data path exercised on a scratch file-backed sqlite DB seeded at 0002 (ami→AMI, 'AMR'→amr case-insensitively, 'na'→NULL+logged, NULL→NULL; reverse restores the codes and drops both tables) · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [BR-AST-044 lane 2026-08-09] ruff✔(E4/E7/E9/F) black✔ migrate✔ makemigrations --check✔ (hand-written 0004 matches the model state) · suite `pytest tests -m "not golden and not isolation"` 593 passed / 8 skipped (587 baseline green + 6 new BR-AST-044 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (unchanged) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy STILL NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: the billing-chain account leg is null while customers owns no tables (W2) — true by construction, never a fabricated name · US-AST-005 (Reads tab) has NO selector here: meter_reads is the W2 reads lane's table, so the story is SKIPPED rather than served an invented empty history · BR-AST-043 gap lane 2026-08-09: asset_dict renders read_method by its catalog CODE (unchanged wire shape) plus a new read_method_name; meter_types()/read_methods() added for the S8 cards and the S51 picker · BR-AST-044 lane 2026-08-09: asset_dict emits meter_type (code) + meter_type_name beside the read_method pair (both null on non-measuring and on every pre-rule row); asset_detail adds a `classifications` block carrying ALL THREE (asset_type · meter_type · read_method) for the S50 header — the flat row keys are unchanged, so no existing consumer moves; asset_list gains the `f.meter_type` filter (AND-combined like the rest, `none` selects the unclassified rows)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
