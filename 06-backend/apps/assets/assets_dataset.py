# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `assets` DATASET QUERY (brief §7.1 — "datasets
#           are code, definitions are data"; §7.2 — one dataset states ONE
#           grain; §7.5 — the two read paths).
#           Drawings read as IMAGES (B14 rule 42): p064 (R31 Meter Fleet, and
#           R30's warning above it), p083–p086 (§7.2/§7.2.1/§7.2.1B/§7.2.2 —
#           the dimension model and additivity), p087 (§7.5 the read path).
# Story:    R31 `meter_fleet` — Operations › Assets · assets · As at
#           (`reports/migrations/0003_seed_catalogue.py` line 249).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `current_tenant_id()` on
#           every queryset, RLS FORCE underneath) · hard rule 3 (every quantity
#           carries its unit — `size` carries `size_unit`, never a bare number)
#           · hard rule 8 (an address is walked to `premises`; an asset
#           declares no address column of its own) · NFR-3 (universal server
#           pagination — limit/offset/sort applied IN SQL) · NFR-5 (no hard
#           caps anywhere) · BR-AST-031 (a lifecycle stage carries a BEHAVIOUR
#           CLASS and every filter keys off the class, never the label) ·
#           BR-AST-004/009 (asset types, tenant-extensible) · BR-REP-002 (read
#           models only) · BR-REP-024 (never a 0 where a figure could not be
#           computed) · BR-TEN-043 (the business date is an argument, never a
#           clock) · B1 (metering owns `meter_reads`; assets asks through its
#           own seam and never joins)
# Tests:    06-backend/tests/test_rep_assets_dataset.py
#           10-scripts/ds_assets_dataset_cost.py (the PostgreSQL measurement —
#           hard-won law 14: the suite runs on in-memory SQLite)
# Impacts:  apps/reports/datasets.py (`ASSETS.grain`, `.columns`,
#           `.paginates`) · apps/reports/queries.py (REP-UNBLOCK registers the
#           viewer) · apps/reports/report_seams.py (the cross-module caller) ·
#           apps/assets/seams.py (`latest_reads_for_assets`, `unit_refs`)
# ───────────────────────────────────────────────────────
"""THE `assets` DATASET — **one row per ASSET**, paged and sorted in SQL.

═══════════════════════════════════════════════════════════════════════════════
ONE REPORT IS SEEDED ON THIS DATASET AND IT IS A REPORT ABOUT ASSETS
═══════════════════════════════════════════════════════════════════════════════
`reports/migrations/0003_seed_catalogue.py` seeds exactly one definition whose
`dataset` is `assets`: **R31 `meter_fleet` Meter Fleet**, Operations › Assets ·
`assets` · **As at**.

Its drawing (p064, read as an image) states one row per METER: `METER · TYPE ·
SIZE · PREMISES · INSTALLED · AGE · LAST READ · STATUS`, with the tiles
`Meters 1,988 · In service 1,947 · Spare 29 · Due for change 84 (4.2%)` and a
footer `Total 1,988`. That is this dataset's declared grain exactly — *one
asset* — and it is the reason this is the one of my four block's datasets whose
report needs no argument. **Served.**

⚠ **THE DATASET IS `assets`, THE DJANGO APP IS `apps.assets`, AND
`apps/reports/datasets.py` DECLARES `owner_module="metering"`.** That is not a
contradiction and nothing here should be "fixed" to match: B2 r4 gives METERING
the ownership of assets as a product module, the Django app that holds the rows
is `apps.assets`, and `datasets.py`'s own docstring already works the split
through (*"metering then owns TWO, because §7.2's own rule is that a dataset
states ONE grain and metering's row owns meter reads · assets — two grains, one
row per read and one row per meter"*). The query lives beside the rows.

═══════════════════════════════════════════════════════════════════════════════
THE DRAWN WARNING IS A RULE ABOUT ABSENCE, AND IT IS THE HARDEST PART TO BUILD
═══════════════════════════════════════════════════════════════════════════════
p064, verbatim: *"**A spare meter has no premises and no read, and both cells
show an em-dash rather than a blank.** Blank reads as missing data; the dash
reads as* not applicable*, which is the fact."*

A spare is `behavior_class = "available"` — it is in the store room. It has no
service point, so no unit, so no premises; and it has never been read. **Those
two absences are LAWFUL and are a different fact from a data gap**, which is why
this query publishes `premises_absence` and `read_absence` per row rather than
two bare `None`s. `"not_applicable"` is the dash; `"unknown"` is the blank. A
renderer that could not tell them apart would print a dash over a meter whose
premises we simply failed to walk to, which is the same class of wrong answer
`BR-REP-025`/`026` already carry for the service mix (an absent row and a
printed `$0.00` look identical and mean opposite things).

═══════════════════════════════════════════════════════════════════════════════
`As at` IS A REAL BASIS AND IT IS NOT `date.today()`
═══════════════════════════════════════════════════════════════════════════════
R31 is seeded `EVENT · "As at"` and its drawn bar's first control is
`As of 09/25/2026`. `as_of` is therefore an ARGUMENT (BR-TEN-043) and never a
clock: a supervisor asking for the fleet as at the end of last quarter and a
scheduled run taking the same figure at 00:02 must be able to get the same
answer.

It does two things and only two, because only two are honest:

  * an asset **INSTALLED AFTER** `as_of` is not in the fleet yet, and
  * an asset **RETIRED ON OR BEFORE** `as_of` is not in it any more.

⚠ **IT DOES NOT RECONSTRUCT A PAST LIFECYCLE STAGE, AND SAYS SO.**
`assets.status` is a pointer that a transition OVERWRITES — there is no
effective-dated stage history on this table. So `STATUS`, and the `In service`
and `Spare` tiles that key off it, describe the stage the asset is in **NOW**,
even when `as_of` is six months back. That is §7.2.4's as-is/as-was fault line
on a different table, and it is published as `GAP_STATUS_IS_AS_IS_NOT_AS_WAS`
rather than left for a reader to assume. Inferring a past stage from
`install_date` and `retire_date` would be a guess with a date on it.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND THE EXPORT TAKES NO `page` AND NO `per`
═══════════════════════════════════════════════════════════════════════════════
`per` cuts the page with `[offset:offset + limit]` on a QuerySet — one
`LIMIT`/`OFFSET` — and `sort` is `order_by(*order_terms(...))`. **Nothing is
sorted or sliced in Python anywhere in this file.**

`assets_dataset_stream()` is a SEPARATE function with no `page` and no `per`, so
an export has no argument through which to inherit a screen's fifty rows. A flag
would have had that bug; a missing parameter cannot. `NFR-5` forbids a ceiling
and there is none.

⚠ **LAST READ IS BATCHED PER PAGE, NOT ONE QUERY PER ROW.**
`apps/assets/seams.latest_read_for_asset` is the SINGULAR and is what the
registry row uses; `apps.metering.selectors.latest_reads_for_assets` answers a
whole set in ONE query and has since `DEF-324`. At 40,000 meters the singular is
40,000 round trips for one column — the identical trap `DEF-MET-4995` measured
at 64 queries for 61 seats and `P2.21` measured again on the payments contact
name. The dedupe is bounded by `per` on the page path and by `STREAM_CHUNK` on
the export path, which is `NFR-3`'s actual requirement: a cost that does not
move with the tenant.

⚠ **NO MODEL OF ANOTHER MODULE IS NAMED IN THIS FILE.** Reads, units and
premises arrive through `apps/assets/seams.py`, which is where they may be
named and nowhere else (B1).

═══════════════════════════════════════════════════════════════════════════════
ADDITIVITY (brief §7.2.2, read as an image on p085)
═══════════════════════════════════════════════════════════════════════════════
`apps/reports/datasets.py` declares ONE measure on this dataset — `assets`,
COUNT, **SEMI-ADDITIVE** — and that declaration is right, which is worth saying
because a count of things feels fully additive.

**A COUNT OF METERS IS A BALANCE AS AT A DATE.** §7.2.2: *"AR balance · deposits
held · **accounts active** — semi-additive — sums across accounts, never across
time."* Meters in service in July plus meters in service in August is not meters
in service over the two months; it is most of the same meters counted twice.
Across ROUTE, AREA, TYPE and SERVICE it sums freely. `forbidden_across` is
derived from `ADD_SEMI` in `datasets.py` and resolves to `(DIM_TIME,)`, so the
refusal the sibling built prints an em-dash and its reason on a time total
rather than a number.

⚠ **`due_for_change_pct` IS NON-ADDITIVE** — a percentage is recomputed from its
components, never averaged, so both components travel beside it.

⚠ **`size` IS A QUANTITY AND CARRIES ITS OWN UNIT, PER ROW (hard rule 3).**
`ASSETS` declares `Column(name="size", type=TYPE_QUANTITY, unit_from="size_unit")`
— `unit_from`, not `unit`, because a fleet holds a 5/8" water meter beside a
kW-rated inverter and one column-level unit would be a lie about one of them.
**`size` IS NEVER SUMMED**: adding `2"` to `5/8"` is the gallons-plus-kilowatt-
hours error hard rule 3 forbids, stated as metadata, so no total is published
for it at all.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing.** No INSERT, UPDATE, DELETE or `save()`, on any table.

**It never falls back to zero.** BR-REP-024: an underivable figure is `None`
beside a named reason in `problems`.

**It states no clock.** `as_of` is an argument.

**It serves no address column of its own.** `premises_no` and `premises_address`
are walked — asset → service point → unit → premises (hard rule 8).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q

from apps.assets import models, seams
from core.pagination import order_terms
from core.tenancy import current_tenant_id

#: This dataset serves NO money column, so `BR-REP-001` has no basis to name and
#: none is invented. The report's DATE basis is the seeded `As at`, which is the
#: `as_of` argument and what `BASIS_DATE` records for a caller labelling the
#: window. `purchase_cost` and `book_value_amount` exist on the table and are
#: deliberately NOT served: `BR-AST-025` keeps money off the asset surfaces, and
#: R31 draws none.
BASIS_DATE = "as_at"

#: `BR-AST-031`'s four behaviour classes. ⚠ **EVERY FILTER AND EVERY TILE KEYS
#: OFF THE CLASS, NEVER OFF THE LABEL** — a tenant may rename *Inventory/Spare*
#: to *Store room* and a report matching on the label would silently report a
#: fleet of zero spares. Read from the stage row, which is the one place the
#: mapping lives.
CLASS_AVAILABLE = "available"
CLASS_IN_SERVICE = "in_service"
CLASS_OUT_OF_SERVICE = "out_of_service"
CLASS_TERMINAL = "terminal"

#: Days in a year, for AGE. A `Decimal` because `7.5 yr` on the drawing is one
#: decimal place of a real division and `365` as an int would floor it to 7.
DAYS_PER_YEAR = Decimal("365.25")

#: What a caller may order by. ⚠ **EVERY TUPLE ENDS IN `id`** — a page is a
#: window over an ORDER, and a fleet imported in one batch shares an
#: `install_date` across thousands of rows, so a non-total order would show one
#: meter twice and another never. `core.pagination.order_terms` refuses to add a
#: tiebreak silently, so it stays the caller's stated decision.
#:
#: `AGE` and `LAST READ` are drawn columns with no entry here on purpose: age is
#: a monotone function of `install_date` and sorts identically to it, and the
#: last read is resolved through a seam per page rather than joined, so there is
#: no SQL order for it. Offering a sort this query cannot honour would be a live
#: caret over a dead control — hard-won law 2's mirror (`DEF-CWP-3925`).
ASSET_SORTS: tuple[str, ...] = (
    "asset_no",
    "asset_type",
    "installed_on",
    "status",
    "size",
)
ASSET_DEFAULT_SORT = "asset_no"
ASSET_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    # B14 rule 31 — the user-facing asset number, never the uuid.
    "asset_no": ("asset_no", "id"),
    "asset_type": ("type__name", "asset_no", "id"),
    "installed_on": ("install_date", "asset_no", "id"),
    "status": ("status__name", "asset_no", "id"),
    "size": ("size_class", "asset_no", "id"),
}

#: The filters this dataset accepts — `ASSETS.filters` exactly, all six applied
#: below. A filter the dataset declares and the query drops shows the WHOLE set
#: under a chip that says otherwise.
ASSET_FILTERS: tuple[str, ...] = ("as_of", "service", "asset_type", "status", "route", "area")


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_STATUS_IS_AS_IS_NOT_AS_WAS = {
    "code": "lifecycle_stage_is_today_s_even_when_as_of_is_not",
    "br_ref": "brief §7.2.4 · BR-AST-031 · BR-REP-024",
    "detail": (
        "`as_of` narrows the fleet by INSTALL and RETIRE dates, which are stored dates, "
        "and it cannot narrow the lifecycle STAGE, which is not effective-dated: a "
        "transition overwrites `assets.status_id` and the only trace is `audit_log`, "
        "pruned on a schedule with no row type exempt. So STATUS, In service and Spare "
        "describe the stage each asset is in NOW. This is §7.2.4's as-is/as-was fault "
        "line on the asset table, and the honest answer is to say so rather than to "
        "infer a past stage from the two dates, which would be a guess with a date on it."
    ),
    "wanted_reads": ("an effective-dated lifecycle-stage history on `assets`",),
}

GAP_DUE_FOR_CHANGE_NEEDS_AN_INTERVAL = {
    "code": "due_for_change_is_undefined_without_a_test_interval",
    "br_ref": "BR-REP-024 · BR-AST-015",
    "detail": (
        "Due for change reads `certification_due` and NOTHING ELSE, because that is the "
        "one rule the tile is struck with in SQL and a row reporting a different rule "
        "would not foot to the tile above it. An asset with no stated certification date "
        "carries no promise of a change, so it is counted in `due_unknown` and excluded "
        "from BOTH sides of the percentage rather than counted as not-due, which would "
        "flatter the figure. The percentage is null, never 0.0, when no meter in the "
        "fleet states one at all. `test_cadence_only` counts the meters that carry a TEST "
        "interval and no stated change date; each is served with `test_due_on` beside it, "
        "answering the different question BR-AST-015 actually asks."
    ),
    "wanted_reads": (),
}

GAP_READS_UNWIRED = {
    "code": "the_meter_reads_seam_did_not_answer",
    "br_ref": "B1 · BR-REP-024",
    "detail": (
        "LAST READ is metering's fact, asked for through `apps/assets/seams."
        "latest_reads_for_assets`. When that seam does not answer, every row's read "
        "absence is `unknown` rather than `not_applicable`: an empty dict from an "
        "unwired seam and a fleet of never-read meters are opposite facts, and the dash "
        "the drawing calls for means the second one. DEF-475's posture, applied to a page."
    ),
    "wanted_reads": ("apps.metering.selectors.latest_reads_for_assets",),
}

#: The two words a renderer needs to tell the drawn em-dash from a blank.
ABSENCE_NOT_APPLICABLE = "not_applicable"
ABSENCE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class AssetFactRow:
    """One asset, in the dataset's own declared column names.

    ⚠ **`premises_absence` AND `read_absence` ARE THE DRAWN WARNING, BUILT.**
    p064: *"A spare meter has no premises and no read, and both cells show an
    em-dash rather than a blank. Blank reads as missing data; the dash reads as
    not applicable, which is the fact."* A `None` alone cannot carry that
    distinction, so each absence says which kind it is:
    `not_applicable` → the em-dash · `unknown` → the blank · `None` → the cell
    has a value.

    ⚠ **`size` AND `size_unit` TRAVEL TOGETHER, ALWAYS (hard rule 3).** A 5/8"
    water meter and a 25 kW inverter are both in this fleet and one column-level
    unit would be a lie about one of them, which is why `ASSETS` declares
    `unit_from="size_unit"` rather than `unit=`. The pair is never summed.

    ⚠ **`age_years` IS AGAINST `as_of`, NEVER AGAINST A CLOCK** (BR-TEN-043).
    """

    asset_id: str
    asset_no: str
    asset_type: str | None
    asset_category: str | None
    make_model: str | None
    status: str | None
    status_class: str | None
    installed_on: date | None
    retired_on: date | None
    age_years: Decimal | None
    last_read_on: date | None
    read_absence: str | None
    premises_no: str | None
    premises_address: str | None
    unit_label: str | None
    premises_absence: str | None
    service_code: str | None
    size: str | None
    size_unit: str | None
    due_for_change_on: date | None
    is_due_for_change: bool | None
    test_due_on: date | None
    is_test_due: bool | None


def _tenant_id() -> Any:
    return current_tenant_id()


def _base(
    *,
    as_of: date | None = None,
    service: str | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    route: Any = None,
    area: Any = None,
) -> Any:
    """The filtered set, as a QuerySet — every criterion a `WHERE`.

    Hard rule 1: `tenant_id=_tenant_id()` on the queryset, with RLS FORCE
    underneath it. No cross-tenant queryset is constructible from here.

    ⚠ **`status` MATCHES THE BEHAVIOUR CLASS FIRST AND THE CODE SECOND, NEVER
    THE LABEL.** `BR-AST-031`: a tenant may rename *Inventory/Spare* to *Store
    room*, and a filter matching on `name` would report a fleet of zero spares
    the day it did. The four classes are the stable vocabulary.
    """
    rows = models.Asset.objects.filter(tenant_id=_tenant_id())
    if as_of is not None:
        # In the fleet AS AT the date: installed by then, not retired by then.
        # An asset with no `install_date` is kit that exists and has never been
        # dated — it stays in, because excluding it would silently shrink the
        # fleet against a date that says nothing about it.
        rows = rows.filter(Q(install_date__isnull=True) | Q(install_date__lte=as_of))
        rows = rows.filter(Q(retire_date__isnull=True) | Q(retire_date__gt=as_of))
    if service:
        rows = rows.filter(service_point__service__code__iexact=service)
    if asset_type:
        rows = rows.filter(Q(type__code__iexact=asset_type) | Q(type__category__iexact=asset_type))
    if status:
        rows = rows.filter(
            Q(status__behavior_class__iexact=status) | Q(status__code__iexact=status)
        )
    if route:
        rows = rows.filter(service_point__route_id=route)
    if area:
        # Hard rule 8's walk again: an area is a property of the PREMISES, not
        # of the meter bolted to it.
        rows = rows.filter(service_point__unit__premises__area_id=area)
    return rows.select_related("type", "status", "service_point__service")


def _test_due_on(asset: Any) -> date | None:
    """When this asset's next TEST falls due — `last_test_date` + its interval.

    ⚠ **THIS IS NOT *DUE FOR CHANGE*, AND CONFLATING THE TWO IS A FOOTING
    FAILURE THIS FILE ALREADY COMMITTED ONCE.** The first draft used
    `certification_due` where a tenant had set one and FELL BACK to this
    derivation where it had not — while the `Due for change` tile counted only
    `certification_due`, in SQL. So a row could read *due* and the tile above it
    could decline to count it, and the two would differ by however many meters
    carry a test cadence and no stated certification date. Measured on the
    PostgreSQL fixture: the tile said **1** over **30,055** meters whose rows
    said otherwise.

    §7.2's whole argument is that a tile and the rows under it are struck over
    the same set. So there is now ONE rule for *due for change* — the tenant's
    own `certification_due`, which is what the tile counts — and this
    derivation is served BESIDE it under its own name, answering the different
    question it actually answers. `BR-AST-015`'s test cadence tells you when to
    TEST a meter; whether to CHANGE it is the tenant's stated date.
    """
    if asset.last_test_date and asset.test_interval_months:
        months = int(asset.test_interval_months)
        year = asset.last_test_date.year + (asset.last_test_date.month - 1 + months) // 12
        month = (asset.last_test_date.month - 1 + months) % 12 + 1
        # Clamp the day rather than overflow — 31 Jan + 1 month is 28/29 Feb.
        day = min(asset.last_test_date.day, _days_in_month(year, month))
        return date(year, month, day)
    return None


def _as_date(value: Any) -> date | None:
    """A `date`, from a `date`, a `datetime` or an ISO string — or `None`."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:  # pragma: no cover — metering writes ISO
            return None
    if hasattr(value, "date") and not isinstance(value, date):
        return value.date()
    return value if isinstance(value, date) else None


def _days_in_month(year: int, month: int) -> int:
    from calendar import monthrange

    return monthrange(year, month)[1]


def _premises_of(asset: Any, unit_refs: dict[str, dict[str, Any]]) -> tuple[Any, Any, Any, str]:
    """Where this asset IS — walked, never a column of its own (hard rule 8).

    asset → service point → unit → premises. The unit's label and its premises
    come from metering through the seam, batched for the whole page.

    Returns the absence KIND as its fourth value, which is the drawn warning:
    an asset with no service point is a SPARE in the store room and its premises
    is `not_applicable` (the em-dash). An asset that HAS a service point whose
    unit the seam could not resolve is `unknown` (the blank) — that one is a
    real gap and must not wear the dash.
    """
    if not asset.service_point_id:
        return None, None, None, ABSENCE_NOT_APPLICABLE
    unit_id = str(asset.service_point.unit_id) if asset.service_point.unit_id else None
    ref = unit_refs.get(unit_id or "") or {}
    if not ref:
        return None, None, None, ABSENCE_UNKNOWN
    return (
        ref.get("premise_no"),
        ref.get("premise_address"),
        ref.get("label"),
        "",
    )


def _shape(
    asset: Any,
    *,
    as_of: date,
    unit_refs: dict[str, dict[str, Any]],
    last_reads: dict[str, dict[str, Any]],
    reads_wired: bool,
) -> AssetFactRow:
    """One stored asset, in the dataset's declared column names. No query."""
    premises_no, premises_address, unit_label, premises_absence = _premises_of(asset, unit_refs)

    read = last_reads.get(str(asset.id)) or {}
    # ⚠ `latest_reads_for_assets` publishes `read_at` as an ISO DATE STRING —
    # `read_at.date().isoformat()` in metering's own selector — and a string is
    # not a date. A row carrying `"2026-11-09"` where a caller expects a `date`
    # sorts as text and formats as a foreign locale, so it is parsed HERE, once,
    # rather than left for each renderer to guess at.
    last_read_on = _as_date(read.get("read_at"))
    if last_read_on is not None:
        read_absence = None
    elif not reads_wired:
        # The seam did not answer. "Never read" and "we could not ask" are
        # opposite facts and only the first one earns the dash.
        read_absence = ABSENCE_UNKNOWN
    elif not asset.service_point_id:
        # A spare has no read because it is in the store room — the drawing's
        # own case, and the em-dash.
        read_absence = ABSENCE_NOT_APPLICABLE
    else:
        read_absence = ABSENCE_UNKNOWN

    age_years = None
    if asset.install_date and asset.install_date <= as_of:
        age_years = (Decimal((as_of - asset.install_date).days) / DAYS_PER_YEAR).quantize(
            Decimal("0.1")
        )

    due_on = asset.certification_due
    test_due = _test_due_on(asset)
    return AssetFactRow(
        asset_id=str(asset.id),
        # B14 rule 31 — the user-facing number, never the uuid.
        asset_no=asset.asset_no,
        asset_type=getattr(asset.type, "name", None),
        asset_category=getattr(asset.type, "category", None),
        make_model=" ".join(part for part in (asset.manufacturer, asset.model) if part) or None,
        status=getattr(asset.status, "name", None),
        # BR-AST-031 — the CLASS travels beside the label, so a caller filters
        # and buckets on the stable word and renders the tenant's own.
        status_class=getattr(asset.status, "behavior_class", None),
        installed_on=asset.install_date,
        retired_on=asset.retire_date,
        age_years=age_years,
        last_read_on=last_read_on,
        read_absence=read_absence,
        premises_no=premises_no,
        premises_address=premises_address,
        unit_label=unit_label,
        premises_absence=premises_absence or None,
        service_code=(
            getattr(getattr(asset.service_point, "service", None), "code", None)
            if asset.service_point_id
            else None
        ),
        # Hard rule 3 — the pair, never the number alone, and never summed.
        size=asset.size_class,
        size_unit=asset.unit,
        due_for_change_on=due_on,
        # ⚠ The SAME rule the `due_for_change` tile is struck with, so the row
        # and the tile above it cannot disagree. `None` means the tenant has
        # stated no change date for this meter — never *not due*.
        is_due_for_change=None if due_on is None else due_on <= as_of,
        test_due_on=test_due,
        is_test_due=None if test_due is None else test_due <= as_of,
    )


def _labels_for(materialised: list[Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any], bool]:
    """A PAGE's unit refs and last reads — TWO batched seam calls, never per row.

    Bounded by `per` on the page path and by `STREAM_CHUNK` on the export path,
    which is `NFR-3`'s actual requirement: a cost that does not move with the
    tenant. The singular `latest_read_for_asset` is 40,000 round trips on a
    top-of-ICP fleet and is not used here.
    """
    unit_ids = [
        str(asset.service_point.unit_id)
        for asset in materialised
        if asset.service_point_id and asset.service_point.unit_id
    ]
    asset_ids = [str(asset.id) for asset in materialised]
    unit_refs = seams.unit_refs(unit_ids) if unit_ids else {}
    batched = seams.resolve("metering", "latest_reads_for_assets", kind="selectors")
    if batched is None:
        return unit_refs, {}, False
    return unit_refs, {str(k): v for k, v in (batched(asset_ids) or {}).items()}, True


def assets_dataset(
    *,
    as_of: date | None = None,
    service: str | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    route: Any = None,
    area: Any = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict[str, Any]:
    """THE dataset query. One row per asset, paged and sorted in SQL.

    `as_of` is REQUIRED in meaning and optional in signature: when a caller
    states none, the tenant's own business date is asked for through the seam
    (`BR-TEN-043`) rather than `date.today()` being reached for here, and the
    date actually used is published in the result so a reader can see which
    fleet they are looking at.

    `per=None` is the whole filtered set. `per` is an integer page size; the
    CALLER clamps it and this function invents no cap (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `assets_dataset_stream()`** — no `page`, no `per`.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER THE
    PAGE**, so R31's four tiles foot to the report whether a page is cut or not.
    """
    effective_as_of = as_of or seams.tenant_today()
    if effective_as_of is None:  # pragma: no cover — tenancy always answers
        effective_as_of = date.today()
    if hasattr(effective_as_of, "date"):
        effective_as_of = effective_as_of.date()

    rows = _base(
        as_of=effective_as_of,
        service=service,
        asset_type=asset_type,
        status=status,
        route=route,
        area=area,
    )

    # ⚠ ONE aggregate call, so every tile is struck over the same snapshot.
    # The three counts key off `behavior_class` (BR-AST-031) and never off the
    # tenant's own label for the stage.
    aggregated = rows.aggregate(
        assets=Count("id"),
        in_service=Count("id", filter=Q(status__behavior_class=CLASS_IN_SERVICE)),
        spare=Count("id", filter=Q(status__behavior_class=CLASS_AVAILABLE)),
        out_of_service=Count("id", filter=Q(status__behavior_class=CLASS_OUT_OF_SERVICE)),
        retired=Count("id", filter=Q(status__behavior_class=CLASS_TERMINAL)),
        # DUE FOR CHANGE — the stated date where a tenant set one, in SQL.
        due_stated=Count("id", filter=Q(certification_due__lte=effective_as_of)),
        # ⚠ BOTH KEY OFF `certification_due` ALONE, which is the one rule the
        # tile is struck with and the row now reports. A denominator counting
        # meters the numerator cannot reach is how a percentage comes out
        # wrong in a direction nobody can see.
        has_promise=Count("id", filter=Q(certification_due__isnull=False)),
        due_unknown=Count("id", filter=Q(certification_due__isnull=True)),
        test_due=Count("id", filter=Q(certification_due__isnull=True, last_test_date__isnull=False)),
    )

    total_assets = int(aggregated["assets"] or 0)
    has_promise = int(aggregated["has_promise"] or 0)
    due_stated = int(aggregated["due_stated"] or 0)
    due_unknown = int(aggregated["due_unknown"] or 0)

    problems: list[dict[str, Any]] = [dict(GAP_STATUS_IS_AS_IS_NOT_AS_WAS)]
    if due_unknown:
        problems.append(dict(GAP_DUE_FOR_CHANGE_NEEDS_AN_INTERVAL))

    # ⚠ NON-ADDITIVE (§7.2.2) — recomputed from its components, never averaged,
    # and both components travel beside it. BR-REP-024: null, never 0.0, when
    # nothing in the fleet states an interval at all — "no meter is due" and
    # "no meter has a test cadence" are opposite facts.
    due_for_change_pct = (
        None
        if not has_promise
        else (Decimal(due_stated) * 100 / Decimal(has_promise)).quantize(Decimal("0.000001"))
    )

    # ── the page, cut in SQL ────────────────────────────────────────────────
    ordered = rows.order_by(
        *order_terms(sort, direction, columns=ASSET_SORT_COLUMNS, default=ASSET_DEFAULT_SORT)
    )
    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_assets // size)) if total_assets else 1
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    materialised = list(window)
    unit_refs, last_reads, reads_wired = _labels_for(materialised)
    if materialised and not reads_wired:
        problems.append(dict(GAP_READS_UNWIRED))
    shaped = tuple(
        _shape(
            asset,
            as_of=effective_as_of,
            unit_refs=unit_refs,
            last_reads=last_reads,
            reads_wired=reads_wired,
        )
        for asset in materialised
    )

    return {
        "basis": BASIS_DATE,
        "as_of": effective_as_of,
        "grain": "one asset",
        "rows": shaped,
        "totals": {
            # ⚠ SEMI-ADDITIVE — sums across route, area, type and service;
            # NEVER across time. A count of meters is a balance as at a date.
            "assets": total_assets,
            "in_service": int(aggregated["in_service"] or 0),
            "spare": int(aggregated["spare"] or 0),
            "out_of_service": int(aggregated["out_of_service"] or 0),
            "retired": int(aggregated["retired"] or 0),
            "due_for_change": due_stated,
            "due_unknown": due_unknown,
            "test_cadence_only": int(aggregated["test_due"] or 0),
            # Non-additive, published WITH its components.
            "due_for_change_pct": due_for_change_pct,
            "due_for_change_of": has_promise,
        },
        "additivity": {
            "assets": "semi",
            "in_service": "semi",
            "spare": "semi",
            "out_of_service": "semi",
            "retired": "semi",
            "due_for_change": "semi",
            "test_cadence_only": "semi",
            "due_for_change_pct": "non",
            # Hard rule 3 — a size is never summed at all.
            "size": "not_summable",
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_assets,
        "problems": tuple(problems),
    }


#: A fetch buffer, not a cap (`NFR-5`). The generator runs until the cursor is
#: exhausted and there is no number any row can be beyond; this only stops a
#: 40,000-row file becoming 40,000 dataclasses in memory at once, and bounds the
#: two batched seam calls per chunk.
STREAM_CHUNK = 2_000


def assets_dataset_stream(
    *,
    as_of: date | None = None,
    service: str | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    route: Any = None,
    area: Any = None,
    sort: str | None = None,
    direction: str = "asc",
) -> Iterator[AssetFactRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    The absence of those two parameters is the whole design: an export cannot
    inherit a screen's fifty rows because there is no argument through which to
    pass them. `NFR-5` — no cap anywhere on this path.

    The order is applied IN SQL, through the same `order_terms` the page uses,
    so the file and the screen sort identically. Labels are resolved per CHUNK,
    batched, never one query per row.
    """
    effective_as_of = as_of or seams.tenant_today()
    if effective_as_of is None:  # pragma: no cover
        effective_as_of = date.today()
    if hasattr(effective_as_of, "date"):
        effective_as_of = effective_as_of.date()

    rows = _base(
        as_of=effective_as_of,
        service=service,
        asset_type=asset_type,
        status=status,
        route=route,
        area=area,
    ).order_by(
        *order_terms(sort, direction, columns=ASSET_SORT_COLUMNS, default=ASSET_DEFAULT_SORT)
    )

    buffer: list[Any] = []

    def _flush(batch: list[Any]) -> Iterator[AssetFactRow]:
        unit_refs, last_reads, reads_wired = _labels_for(batch)
        for asset in batch:
            yield _shape(
                asset,
                as_of=effective_as_of,
                unit_refs=unit_refs,
                last_reads=last_reads,
                reads_wired=reads_wired,
            )

    for asset in rows.iterator(chunk_size=STREAM_CHUNK):
        buffer.append(asset)
        if len(buffer) >= STREAM_CHUNK:
            yield from _flush(buffer)
            buffer = []
    if buffer:
        yield from _flush(buffer)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · lane DS-SMALL (the `assets` dataset query)
# screens: none of its own — 2·1 and 2·2 render every dataset
# generated: 2026-09-27 by lane DS-SMALL
# exceptions: (1) `as_of` narrows by the two STORED dates and cannot narrow the
#   lifecycle stage, which is not effective-dated — published as
#   `GAP_STATUS_IS_AS_IS_NOT_AS_WAS` rather than inferred · (2) `age_years`,
#   `premises_address`, `status_class`, `read_absence` and `premises_absence`
#   are served and are not declared columns on `ASSETS`; each is drawn on R31
#   or is the drawn absence warning made machine-readable — REPORTED for
#   `datasets.py`, whose owner declares columns once · (3) no money column is
#   served at all (`BR-AST-025`), so `BR-REP-001` has no basis to name here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
