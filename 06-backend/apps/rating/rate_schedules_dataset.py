# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `rate_schedules` DATASET QUERY (brief §7.1 —
#           "datasets are code, definitions are data"; §7.2 — one dataset
#           states ONE grain; §7.5 — the two read paths).
#           Drawings read as IMAGES (B14 rule 42): p066–p067 (R37 Rate Change
#           History and its warning), p083–p086 (§7.2/§7.2.1/§7.2.1B/§7.2.2 —
#           the dimension model and additivity), p087 (§7.5 the read path).
# Story:    R37 `rate_change_history` — Compliance › Changes · rating + audit ·
#           Effective date (`reports/migrations/0003_seed_catalogue.py` 255).
#           ⚠ **REFUSED BY NAME AT THIS GRAIN — see the docstring.**
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `current_tenant_id()` on
#           every queryset, RLS FORCE underneath) · **hard rule 2 — money
#           stored to 4 decimals, percentages to 6, BOTH DISPLAY 2; every
#           figure here leaves as an exact `Decimal` and NOTHING is rounded for
#           display in this file** · hard rule 4 (append-only: a correction is
#           a NEW version row, never an UPDATE — nothing here writes at all) ·
#           NFR-3 (pagination in SQL) · NFR-5 (no hard caps) · BR-RAT-007
#           (history bills on ITS version, never the current one) · BR-RAT-031
#           (a NULL `effective_from` IS the resumable draft) · BR-RAT-087 +
#           `OQ-620(a)` (the display precisions — see the docstring) ·
#           BR-REP-001 (a money report names its basis) · BR-REP-002 (read
#           models only) · BR-REP-024 (never a 0 where a figure could not be
#           computed) · BR-TEN-043 (the business date is an argument)
# Tests:    06-backend/tests/test_rep_rate_schedules_dataset.py
#           10-scripts/ds_rate_schedules_dataset_cost.py (PostgreSQL)
# Impacts:  apps/reports/datasets.py (`RATE_SCHEDULES.grain`, `.columns`) ·
#           apps/reports/queries.py (REP-UNBLOCK registers nothing for R37) ·
#           apps/reports/report_seams.py (the cross-module caller)
# ───────────────────────────────────────────────────────
"""THE `rate_schedules` DATASET — **one row per RATE-SCHEDULE VERSION**.

🔒 SENSITIVE PATH · HUMAN-OWNED · HUMAN-REVIEW-PENDING — this reads rating math. It computes
none: every figure below is served exactly as it is STORED, and the one thing
this file is careful about is not rounding a signed rate. Row in
`12-governance/09-human-review-ledger.md`, written before the review.

═══════════════════════════════════════════════════════════════════════════════
ONE REPORT IS SEEDED ON THIS DATASET AND THIS DATASET CANNOT STATE ITS GRAIN
═══════════════════════════════════════════════════════════════════════════════
`reports/migrations/0003_seed_catalogue.py` seeds exactly one definition whose
`dataset` is `rate_schedules`: **R37 `rate_change_history` Rate Change
History**, Compliance › Changes · **rating + audit** · Effective date.

**IT IS NOT SERVED FROM HERE, AND THE REFUSAL IS THE DELIVERABLE.**

Read its drawing (p066–p067, as an image) rather than its seed row. Every drawn
row is **ONE COMPONENT OF ONE SCHEDULE MOVING**:

    EFFECTIVE   SCHEDULE     SERVICE  COMPONENT     WAS      NOW      CHANGE   BY
    01/10/2026  RES-W-2026   Water    Usage tier 1  0.0142   0.0154   +8.5%    M. Okonkwo
    01/07/2026  RES-S-2026   Sewer    Base charge  20.0000  22.0000  +10.0%    M. Okonkwo
    01/01/2026  COM-W-2026   Water    Usage flat    0.0138   0.0142   +2.9%    Platform

`apps/reports/datasets.py` declares this dataset's grain as **"one rate-schedule
version"**, and a version is not a component. **Measured, not assumed:** a
`TariffVersion` owns `base_charge` (one), `RateTier.unit_price` (**many** — one
per tier, per season, per size class), `RateSizeRow`, `CapacityRate`,
`TimeOfUseWindow` and `DemandRateConfig` rows. So a four-tier residential
schedule whose tiers all move on 1 October is **FOUR drawn rows and ONE row at
this grain**, and the dataset declares a **single** `unit_rate` column with
nowhere to say which of the four it is.

Serving R37 from here would put one of a version's several rates into a column
labelled *the* rate, to four decimals, with no component named — a
precise-looking wrong number on a **compliance report an auditor reads**. That
is the invisible wrong answer §7.2 exists to refuse: real rows, a footing count
and an answer to a question nobody asked.

**Two further facts, each of which would refuse it on its own:**

**① `WAS` AND `NOW` ARE A DIFF, AND NOTHING HERE DECLARES ONE.** A component's
previous value lives on the version this one supersedes
(`TariffVersion.superseded_by` / `corrects_version_id`), and the dataset
declares no `was`, no `now` and no `change_pct`. Serving `NOW` alone under a
`CHANGE` heading would print a movement nobody computed.

**② THE DRAWN SOURCE SAYS `rating + audit`, AND THE `audit` HALF MUST NOT BE
BUILT.** `apps/rating/models.py`'s own comment on `TariffVersion.corrected_by`
rules it, verbatim: *"NOT read back out of `audit_log`: that table is pruned on
a retention schedule (hard rule 4's 2026-09-02 narrowing), so a rate history
sourced from there would lose its `BY` column silently."* `OQ-1340` closed that
retention question on 2026-09-23 with **no row type exempt**. So `BY` is
rating's own `submitted_by` / `corrected_by` / `approved_by` — which is what
this query serves — and the drawing's second source is a route this repo has
already ruled against. Nothing is escalated: it is ruled, in the module that
owns it (hard-won law 13).

The refusal travels as `GAP_R37_IS_A_DIFFERENT_GRAIN` on every result, carrying
the grain and the reads a rate-change report actually needs.

═══════════════════════════════════════════════════════════════════════════════
⚠ THE DRAWN PRECISION WARNING IS HALF LAW AND HALF A FILED DEFECT — DO NOT
RECONCILE IT HERE
═══════════════════════════════════════════════════════════════════════════════
p067, verbatim: *"**Rates show four decimals and percentages six, displayed at
the precision the rule stores** — hard rule 2, and the one report where trimming
to two decimals would misstate a tariff."*

`04-docs/05-modules/12-reports/02-business-rules.md` already splits it and the
split is signed:

  * **RATE HALF = LAW.** `OQ-620(a)`, CLOSED 2026-08-27, PO verbatim: *"Four
    ($0.1420). A rate is not money and not a quantity."* So a unit rate is
    served and displayed at **four** decimals. `RATE_SCHEDULES` declares
    `Column(name="unit_rate", type=TYPE_MONEY, money_basis=BASIS_EVENT,
    scale=4)` for exactly that reason.
  * **PERCENT HALF = A FILED DEFECT AGAINST THE DRAWING**, `DEF-REP-6829`:
    `BR-RAT-087` (PO 2026-08-20, built) and CLAUDE.md hard rule 2 both say a
    percentage is stored to six and **DISPLAYS 2**.

**This file displays nothing and rounds nothing.** Every figure leaves as an
exact `Decimal` at its stored scale and the renderer applies the display rule —
which is the only posture that keeps a ❄️ FROZEN B4/B5 figure safe, because a
rounding done here would be a rate change nobody signed. **No figure below is
reconciled against a signed one and none is edited.**

═══════════════════════════════════════════════════════════════════════════════
`Effective date` IS THE BASIS, AND THE DRAWING SAYS WHY
═══════════════════════════════════════════════════════════════════════════════
p067: *"The future-dated row is why the effective date, not the entry date, is
this report's basis."* A rise typed on 12 September to take effect on 1 October
is September's entry and October's rate, and a compliance reader wants the
second one. So `start`/`end` filter `effective_from` and **never** `created_at`.

⚠ **A NULL `effective_from` IS THE RESUMABLE DRAFT (`BR-RAT-031`) AND IS
EXCLUDED BY DEFAULT.** A half-built structure on a dateless row is not a rate
change; it is a wizard somebody has not finished. It is excluded rather than
dated `None` and sorted to one end, and the count of them travels so a reader
knows the fleet of drafts exists.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND THE EXPORT TAKES NO `page` AND NO `per`
═══════════════════════════════════════════════════════════════════════════════
`per` cuts the page with `[offset:offset + limit]` — one `LIMIT`/`OFFSET` — and
`sort` is `order_by(*order_terms(...))`. Nothing is sorted or sliced in Python.
`rate_schedules_dataset_stream()` is a SEPARATE function with no `page` and no
`per`, so an export has no argument through which to inherit a screen's page.
`NFR-5` — no cap on either path.

═══════════════════════════════════════════════════════════════════════════════
ADDITIVITY (brief §7.2.2, read as an image on p085)
═══════════════════════════════════════════════════════════════════════════════
`RATE_SCHEDULES` declares ONE measure — `versions`, COUNT, **FULLY ADDITIVE** —
and that is right: versions effective in July plus versions effective in August
is versions effective over the two months. Each is an EVENT, not a balance.

⚠ **A RATE IS NOT A MEASURE AND IS NEVER TOTALLED.** `unit_rate` and
`percentage` are declared as COLUMNS and not as measures, and `totals` below
publishes no sum, no average and no minimum of either. §7.2.2's rule for
non-additive figures applies twice over here: the mean of four tariffs' base
charges is not a utility's base charge, and a column of water rates added to a
column of sewer rates is not a number at all. `additivity` states
`not_summable` for both so the footer refusal a sibling built prints an em-dash
and its reason rather than a figure.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing** and **it computes nothing.** No INSERT, UPDATE, DELETE or
`save()`; no rounding, no reconciliation, no derived rate. Hard rule 4 makes a
correction a NEW version row, and this file has no opinion about that either.

**It never falls back to zero.** A tariff version with no stated base charge has
`base_charge = NULL`, which since 2026-08-19 (`DEF-277`, `CR-013` part 1) means
*this size is not served* and is a different fact from `0` meaning *served, and
free*. Serving `0.0000` for the first would put a price on a bill on the
strength of a guess. It is served as `None` with `base_charge_absence` saying
which kind of absence it is.

**It states no clock.** `start`, `end` and `as_of` are arguments (BR-TEN-043).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q

from apps.rating import models
from core.pagination import order_terms
from core.tenancy import current_tenant_id

#: BR-REP-001. A unit rate is dated by the day it TAKES EFFECT, which is the
#: seeded basis (`EVENT · "Effective date"`) and the drawing's own argument:
#: *"the future-dated row is why the effective date, not the entry date, is this
#: report's basis."*
BASIS = "effective"

#: Hard rule 2, as narrowed for a rate by `OQ-620(a)` (PO 2026-08-27, verbatim
#: *"Four ($0.1420). A rate is not money and not a quantity"*). STORED scale —
#: this module does not round to it and does not round away from it; it records
#: what the column holds so a renderer that must display knows the precision it
#: is displaying FROM.
RATE_SCALE = 4
#: Hard rule 2 — a percentage is STORED to six. ⚠ Its DISPLAY is 2, per
#: `BR-RAT-087` and hard rule 2, and the drawing's *"percentages six"* is
#: `DEF-REP-6829` against the drawing rather than a rule to build to. Nothing
#: here displays, so nothing here is trimmed.
PERCENT_SCALE = 6

#: What a caller may order by. ⚠ **EVERY TUPLE ENDS IN `id`** — a bulk rate
#: update (`RateChangeBatch`, `BR-RAT-040`) stamps one `effective_from` across
#: every schedule it touches, so `effective_from` alone is emphatically not a
#: total order and a page over it would show one version twice and another
#: never.
RATE_SCHEDULE_SORTS: tuple[str, ...] = (
    "effective_from",
    "effective_to",
    "schedule_code",
    "service_code",
    "structure",
)
RATE_SCHEDULE_DEFAULT_SORT = "effective_from"
RATE_SCHEDULE_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "effective_from": ("effective_from", "id"),
    "effective_to": ("effective_to", "effective_from", "id"),
    # B14 rule 31 — the schedule's own name, never the uuid.
    "schedule_code": ("tariff__name", "effective_from", "id"),
    "service_code": ("tariff__service__code", "effective_from", "id"),
    "structure": ("model", "effective_from", "id"),
}

#: `RATE_SCHEDULES.filters` exactly — all five applied below.
RATE_SCHEDULE_FILTERS: tuple[str, ...] = ("as_of", "from", "to", "service", "plan")


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_R37_IS_A_DIFFERENT_GRAIN = {
    "code": "rate_change_history_is_one_component_change_not_one_version",
    "br_ref": "brief §7.2 · §7.2.1B · BR-RAT-007 · DEF-REP-6829",
    "detail": (
        "R37 Rate Change History is seeded onto this dataset and this dataset cannot state "
        "its grain. Its drawing (p066-p067) puts one COMPONENT of one schedule on each row "
        "- 'Usage tier 1', 'Base charge', 'Usage flat' - with WAS, NOW and CHANGE beside "
        "it. This dataset states one rate-schedule VERSION, and a version owns many priced "
        "components: base_charge, one RateTier.unit_price per tier per season per size "
        "class, RateSizeRow, CapacityRate and TimeOfUseWindow rows. A four-tier schedule "
        "whose tiers all move on one date is four drawn rows and one row here, and the "
        "dataset declares a single `unit_rate` column with nowhere to name which of the "
        "four it holds. WAS and NOW are additionally a diff against the superseded "
        "version, for which no column is declared. The drawn second source 'audit' must "
        "NOT be built: apps/rating/models.py rules that a rate history sourced from "
        "audit_log loses its BY column silently, because audit_log is pruned with no row "
        "type exempt (OQ-1340, closed 2026-09-23). BY is rating's own submitted_by / "
        "corrected_by / approved_by and is served as such."
    ),
    "wanted_reads": (
        "a dataset at COMPONENT grain over tariff_versions x {base_charge, rate_tiers, "
        "rate_size_rows, capacity_rates, charge_code_amounts}, diffed against "
        "TariffVersion.superseded_by, with BY from rating and never from audit_log",
    ),
}

GAP_BASE_CHARGE_ABSENCE_HAS_TWO_MEANINGS = {
    "code": "a_null_base_charge_is_not_served_not_free",
    "br_ref": "DEF-277 · CR-013 part 1 · BR-REP-024",
    "detail": (
        "`tariff_versions.base_charge` has been NULLABLE since 2026-08-19 and the NULL "
        "means something: PO verbatim, 'Blank base = size not served'. A stored 0 means "
        "stated, and free, and every historic zero keeps billing $0.00 by the same ruling. "
        "The two are served apart - `base_charge` is None with `base_charge_absence` = "
        "'not_served' for the first and Decimal('0') for the second - because a report "
        "that printed 0.0000 for both would put a price on a size the utility refuses to "
        "serve."
    ),
    "wanted_reads": (),
}

GAP_SCHEDULE_IS_ON_SEVERAL_PLANS = {
    "code": "one_schedule_serves_more_than_one_plan",
    "br_ref": "brief §7.2 · BR-RAT-007",
    "detail": (
        "`plan_rate_schedules` is unique on (rate_plan, service), so a PLAN has one "
        "schedule per service - but a SCHEDULE may be bound to several plans. Joining to "
        "the plan would fan one version into one row per plan and the version count would "
        "over-report. The join is not made: `plan_code` and `plan_name` are served only "
        "where exactly one plan binds the schedule, `plan_count` travels on every row, and "
        "where it is greater than one both are None rather than one plan picked "
        "arbitrarily."
    ),
    "wanted_reads": (),
}

GAP_DRAFTS_EXCLUDED = {
    "code": "dateless_draft_versions_are_not_rate_changes",
    "br_ref": "BR-RAT-031",
    "detail": (
        "A NULL `effective_from` IS the resumable draft (BR-RAT-031; "
        "uq_tariff_versions_one_draft is PARTIAL on exactly that predicate). A half-built "
        "structure on a dateless row is a wizard somebody has not finished, not a rate "
        "that took effect, so it is excluded from the rows and from every total. The count "
        "travels as `drafts` so the absence is stated rather than silent."
    ),
    "wanted_reads": (),
}

ABSENCE_NOT_SERVED = "not_served"


@dataclass(frozen=True)
class RateScheduleFactRow:
    """One rate-schedule version, in the dataset's own declared column names.

    ⚠ **EVERY FIGURE IS THE STORED `Decimal`, UNROUNDED.** Hard rule 2 puts
    DISPLAY at two decimals for money and for percentages and puts a RATE at
    four (`OQ-620(a)`); this row does none of that, because rounding a signed
    rate to make a column fit is a rate change nobody signed and B4/B5 are ❄️
    FROZEN. `rate_scale` and `percent_scale` travel so the renderer knows what
    precision it is displaying from.

    ⚠ **`base_charge` IS `None` FOR *NOT SERVED* AND `Decimal('0')` FOR *FREE*
    (`DEF-277`).** `base_charge_absence` says which. They are the same pixel on
    a screen and opposite facts on a bill.

    ⚠ **`changed_by` COMES FROM RATING, NEVER FROM `audit_log`.** The drawing
    dates this report `rating + audit`; `TariffVersion.corrected_by`'s own rule
    is that a rate history sourced from the audit table loses this column
    silently when retention prunes it, with no row type exempt (`OQ-1340`).
    `changed_by_role` says which of the three stamps answered, so a reader can
    tell a correction from an approval from a submission.
    """

    version_id: str
    schedule_code: str | None
    schedule_name: str | None
    service_code: str | None
    service_name: str | None
    structure: str | None
    plan_code: str | None
    plan_name: str | None
    plan_count: int
    effective_from: date | None
    effective_to: date | None
    is_in_effect: bool
    is_future_dated: bool
    base_charge: Decimal | None
    base_charge_absence: str | None
    unit_rate: Decimal | None
    unit_rate_component: str | None
    rate_scale: int
    percentage: Decimal | None
    percent_scale: int
    priced_components: int
    changed_by: str | None
    changed_by_role: str | None
    change_reason: str | None
    correction_reason: str | None
    corrects_version_id: str | None
    superseded_by_version_id: str | None
    entered_at: date | None


def _tenant_id() -> Any:
    return current_tenant_id()


def _base(
    *,
    start: date | None = None,
    end: date | None = None,
    service: str | None = None,
    plan: Any = None,
    include_drafts: bool = False,
) -> Any:
    """The filtered set, as a QuerySet — every criterion a `WHERE`.

    ⚠ **THE WINDOW IS ON `effective_from`, NEVER ON `created_at`.** The
    drawing's own argument: *"the future-dated row is why the effective date,
    not the entry date, is this report's basis."* A rise typed on 12 September
    to take effect on 1 October is October's rate.

    ⚠ **DRAFTS ARE EXCLUDED** (`BR-RAT-031`: a NULL `effective_from` IS the
    resumable draft), unless a caller asks for them by name.
    """
    rows = models.TariffVersion.objects.filter(tenant_id=_tenant_id())
    if not include_drafts:
        rows = rows.filter(effective_from__isnull=False)
    if start is not None:
        rows = rows.filter(effective_from__gte=start)
    if end is not None:
        rows = rows.filter(effective_from__lte=end)
    if service:
        rows = rows.filter(tariff__service__code__iexact=service)
    if plan:
        # Through the binding table rather than by a join on the row, so the
        # grain is untouched: this NARROWS to the versions of the schedules
        # that plan uses and fans nothing out.
        tariff_ids = models.PlanRateSchedule.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=plan
        ).values_list("tariff_id", flat=True)
        rows = rows.filter(tariff_id__in=list(tariff_ids))
    return rows.select_related(
        "tariff__service", "submitted_by", "approved_by", "corrected_by"
    )


def _plans_for(tariff_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """A PAGE's plan bindings — ONE query, never one per row.

    ⚠ **THIS IS A LOOKUP AND NOT A JOIN, AND THE DIFFERENCE IS THE GRAIN.**
    A schedule may be bound to several plans, so joining would fan one version
    into one row per plan and the `versions` count would over-report. The map
    is built here and the row takes a plan from it only when there is exactly
    one.
    """
    if not tariff_ids:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    rows = models.PlanRateSchedule.objects.filter(
        tenant_id=_tenant_id(), tariff_id__in=list({str(t) for t in tariff_ids})
    ).select_related("rate_plan")
    for row in rows:
        out.setdefault(str(row.tariff_id), []).append(
            {"code": row.rate_plan.code, "name": row.rate_plan.name}
        )
    return out


def _component_counts(version_ids: list[Any]) -> dict[str, int]:
    """How many PRICED COMPONENTS each version owns — FIVE bounded queries.

    ⚠ **THIS NUMBER IS THE REFUSAL, MADE VISIBLE.** It is exactly the reason
    R37 cannot be served at this grain: a version with `priced_components = 4`
    is four rows on R37's drawing and one row here. A reader meeting it in the
    payload meets the argument rather than having to re-derive it.

    Five `values(...).annotate(Count)` calls over five tables, each bounded by
    the page's version ids — never one query per row.
    """
    if not version_ids:
        return {}
    wanted = [str(v) for v in version_ids]
    counts: dict[str, int] = {key: 0 for key in wanted}
    # ⚠ **`ChargeCodeAmount` IS DELIBERATELY ABSENT AND THAT IS MEASURED, NOT
    # ASSUMED.** It carries no `tariff_version_id` at all — it hangs off
    # `charge` and is keyed by `size_class` — so it is not a component OF a
    # version and counting it here would raise rather than over-report.
    # `DemandRateConfig` is a `OneToOneField`, so it can add at most one and is
    # counted separately below.
    tables = (
        models.RateTier,
        models.RateSizeRow,
        models.CapacityRate,
        models.TimeOfUseWindow,
    )
    for table in tables:
        rows = (
            table.objects.filter(tenant_id=_tenant_id(), tariff_version_id__in=wanted)
            .values("tariff_version_id")
            .annotate(n=Count("id"))
        )
        for row in rows:
            key = str(row["tariff_version_id"])
            counts[key] = counts.get(key, 0) + int(row["n"])
    for version_id in models.DemandRateConfig.objects.filter(
        tenant_id=_tenant_id(), tariff_version_id__in=wanted
    ).values_list("tariff_version_id", flat=True):
        key = str(version_id)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _changed_by(version: Any) -> tuple[str | None, str | None]:
    """WHO moved this rate — from RATING's own stamps, never from `audit_log`.

    The order is the specific first: a CORRECTION names who filed it, an
    activation names who approved it, and the submission is the fallback. Each
    is a different act and the role travels so a compliance reader is not
    shown three facts under one word.
    """
    for attribute, role in (
        ("corrected_by", "corrected"),
        ("approved_by", "approved"),
        ("submitted_by", "submitted"),
    ):
        if getattr(version, f"{attribute}_id", None):
            user = getattr(version, attribute)
            name = (getattr(user, "full_name", "") or "").strip()
            return (name or None), role
    return None, None


def _shape(
    version: Any,
    *,
    as_of: date,
    plans: dict[str, list[dict[str, Any]]],
    components: dict[str, int],
) -> RateScheduleFactRow:
    """One stored version, in the dataset's declared column names. No query."""
    bindings = plans.get(str(version.tariff_id), [])
    one_plan = bindings[0] if len(bindings) == 1 else None

    base = version.base_charge
    # DEF-277 — a NULL is *not served* and a 0 is *served, and free*. They are
    # never collapsed, here or anywhere downstream.
    base_absence = ABSENCE_NOT_SERVED if base is None else None

    changed_by, changed_by_role = _changed_by(version)
    effective_from = version.effective_from
    effective_to = version.effective_to
    in_effect = bool(
        effective_from is not None
        and effective_from <= as_of
        and (effective_to is None or effective_to >= as_of)
    )
    service = getattr(version.tariff, "service", None)

    return RateScheduleFactRow(
        version_id=str(version.id),
        # ⚠ `tariffs` carries a NAME and no CODE column — `schedule_code` is
        # the dataset's declared name for it and both are served from the one
        # value rather than a code being invented. B14 rule 31: never the uuid.
        schedule_code=version.tariff.name,
        schedule_name=version.tariff.name,
        service_code=getattr(service, "code", None),
        service_name=getattr(service, "name", None),
        structure=version.model,
        plan_code=one_plan["code"] if one_plan else None,
        plan_name=one_plan["name"] if one_plan else None,
        plan_count=len(bindings),
        effective_from=effective_from,
        effective_to=effective_to,
        is_in_effect=in_effect,
        is_future_dated=bool(effective_from is not None and effective_from > as_of),
        base_charge=base,
        base_charge_absence=base_absence,
        # ⚠ **SERVED ONLY WHERE THE VERSION HAS EXACTLY ONE PRICED FIGURE.**
        # `unit_rate` is a single declared column and a version may hold many
        # rates; naming one of several under an unqualified heading is the
        # wrong answer this whole file refuses. Where the structure is flat and
        # the base charge is the only priced figure, it IS the unit rate and
        # the component is named beside it; otherwise both are None.
        unit_rate=(base if components.get(str(version.id), 0) == 0 else None),
        unit_rate_component=(
            "base_charge" if components.get(str(version.id), 0) == 0 and base is not None else None
        ),
        rate_scale=RATE_SCALE,
        # No percentage is stored ON a version — `percent_basis` names what a
        # percent-of-service schedule prices AGAINST, which is not a figure.
        # BR-REP-024: absent rather than a plausible 0.000000.
        percentage=None,
        percent_scale=PERCENT_SCALE,
        priced_components=components.get(str(version.id), 0),
        changed_by=changed_by,
        changed_by_role=changed_by_role,
        change_reason=version.change_reason,
        correction_reason=version.correction_reason,
        # ⚠ **THE ORM NAME IS `corrects_id`, NOT `corrects_version_id`.** The
        # column is `corrects_version_id` and the FIELD is `corrects`, so the
        # two disagree by design. The first draft used the column name, which
        # Django refused with `FieldError` — and it refused on PostgreSQL in
        # the measurement rather than in the SQLite suite, because the suite
        # never reached this aggregate. Hard-won law 14's shape for a field
        # name rather than for a transaction.
        corrects_version_id=(str(version.corrects_id) if version.corrects_id else None),
        superseded_by_version_id=(
            str(version.superseded_by_id) if version.superseded_by_id else None
        ),
        entered_at=version.created_at.date() if version.created_at else None,
    )


def rate_schedules_dataset(
    *,
    as_of: date | None = None,
    start: date | None = None,
    end: date | None = None,
    service: str | None = None,
    plan: Any = None,
    include_drafts: bool = False,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = "desc",
) -> dict[str, Any]:
    """THE dataset query. One row per rate-schedule version, paged in SQL.

    ⚠ **R37 IS NOT SERVED FROM THIS** — see the module docstring and
    `GAP_R37_IS_A_DIFFERENT_GRAIN`, which travels on every result.

    `per=None` is the whole filtered set. The CALLER clamps `per`; no cap is
    invented here (`NFR-5`). For an export call `rate_schedules_dataset_stream()`,
    which takes no `page` and no `per`.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET**, never over the
    page, and it publishes **no sum or average of any rate** — §7.2.2, and the
    mean of four tariffs' base charges is not a utility's base charge.
    """
    effective_as_of = as_of or _tenant_today() or date.today()
    if hasattr(effective_as_of, "date"):
        effective_as_of = effective_as_of.date()

    rows = _base(
        start=start, end=end, service=service, plan=plan, include_drafts=include_drafts
    )

    aggregated = rows.aggregate(
        versions=Count("id"),
        in_effect=Count(
            "id",
            filter=Q(effective_from__lte=effective_as_of)
            & (Q(effective_to__isnull=True) | Q(effective_to__gte=effective_as_of)),
        ),
        future_dated=Count("id", filter=Q(effective_from__gt=effective_as_of)),
        corrections=Count("id", filter=Q(corrects_id__isnull=False)),
        base_not_served=Count("id", filter=Q(base_charge__isnull=True)),
    )
    # Drafts are outside `rows` by construction, so they are counted separately
    # and stated rather than silently absent (BR-RAT-031).
    drafts = (
        models.TariffVersion.objects.filter(
            tenant_id=_tenant_id(), effective_from__isnull=True
        ).count()
        if not include_drafts
        else 0
    )

    total = int(aggregated["versions"] or 0)
    problems: list[dict[str, Any]] = [dict(GAP_R37_IS_A_DIFFERENT_GRAIN)]
    if aggregated["base_not_served"]:
        problems.append(dict(GAP_BASE_CHARGE_ABSENCE_HAS_TWO_MEANINGS))
    if drafts:
        problems.append(dict(GAP_DRAFTS_EXCLUDED))

    ordered = rows.order_by(
        *order_terms(
            sort,
            direction,
            columns=RATE_SCHEDULE_SORT_COLUMNS,
            default=RATE_SCHEDULE_DEFAULT_SORT,
        )
    )
    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total // size)) if total else 1
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    materialised = list(window)
    plans = _plans_for([v.tariff_id for v in materialised])
    components = _component_counts([v.id for v in materialised])
    shaped = tuple(
        _shape(v, as_of=effective_as_of, plans=plans, components=components)
        for v in materialised
    )
    if any(row.plan_count > 1 for row in shaped):
        problems.append(dict(GAP_SCHEDULE_IS_ON_SEVERAL_PLANS))

    return {
        "basis": BASIS,
        "as_of": effective_as_of,
        "grain": "one rate-schedule version",
        "rows": shaped,
        "totals": {
            # Fully additive — each version is an EVENT, not a balance.
            "versions": total,
            "in_effect": int(aggregated["in_effect"] or 0),
            "future_dated": int(aggregated["future_dated"] or 0),
            "corrections": int(aggregated["corrections"] or 0),
            "drafts": drafts,
            # ⚠ NO SUM, NO AVERAGE AND NO MINIMUM OF ANY RATE IS PUBLISHED.
            # See `additivity` below and §7.2.2.
        },
        "additivity": {
            "versions": "full",
            "in_effect": "semi",
            "future_dated": "semi",
            "corrections": "full",
            "unit_rate": "not_summable",
            "base_charge": "not_summable",
            "percentage": "not_summable",
        },
        "precision": {
            # Hard rule 2 as narrowed by `OQ-620(a)` — STORED scales, recorded
            # so a renderer knows what it is displaying from. Nothing here is
            # rounded; `DEF-REP-6829` is the defect on the drawn display rule.
            "rate_scale": RATE_SCALE,
            "percent_scale": PERCENT_SCALE,
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total,
        "problems": tuple(problems),
    }


def _tenant_today() -> Any:
    """The tenant's own business date (BR-TEN-043), through the seam.

    `date.today()` is the fallback of last resort and is never the first
    choice: a read that consulted the server's clock could not be asked for
    yesterday's rates and would give a scheduled run a different answer from
    the screen it is meant to reproduce.
    """
    from importlib import import_module

    try:
        tenancy = import_module("apps.tenancy.selectors")
    except ImportError:  # pragma: no cover — tenancy always present
        return None
    fn = getattr(tenancy, "tenant_today", None)
    return fn() if callable(fn) else None


#: A fetch buffer, not a cap (`NFR-5`).
STREAM_CHUNK = 2_000


def rate_schedules_dataset_stream(
    *,
    as_of: date | None = None,
    start: date | None = None,
    end: date | None = None,
    service: str | None = None,
    plan: Any = None,
    include_drafts: bool = False,
    sort: str | None = None,
    direction: str = "desc",
) -> Iterator[RateScheduleFactRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    The absence of those two parameters is the whole design: an export cannot
    inherit a screen's fifty rows because there is no argument through which to
    pass them. `NFR-5` — no cap anywhere on this path; `STREAM_CHUNK` is a
    fetch buffer and bounds the two batched lookups per chunk.
    """
    effective_as_of = as_of or _tenant_today() or date.today()
    if hasattr(effective_as_of, "date"):
        effective_as_of = effective_as_of.date()

    rows = _base(
        start=start, end=end, service=service, plan=plan, include_drafts=include_drafts
    ).order_by(
        *order_terms(
            sort,
            direction,
            columns=RATE_SCHEDULE_SORT_COLUMNS,
            default=RATE_SCHEDULE_DEFAULT_SORT,
        )
    )

    buffer: list[Any] = []

    def _flush(batch: list[Any]) -> Iterator[RateScheduleFactRow]:
        plans = _plans_for([v.tariff_id for v in batch])
        components = _component_counts([v.id for v in batch])
        for version in batch:
            yield _shape(version, as_of=effective_as_of, plans=plans, components=components)

    for version in rows.iterator(chunk_size=STREAM_CHUNK):
        buffer.append(version)
        if len(buffer) >= STREAM_CHUNK:
            yield from _flush(buffer)
            buffer = []
    if buffer:
        yield from _flush(buffer)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · lane DS-SMALL (the `rate_schedules` dataset)
# screens: none of its own — 2·1 and 2·2 render every dataset
# generated: 2026-09-27 by lane DS-SMALL
# exceptions: (1) R37 `rate_change_history` is the ONLY definition seeded onto
#   this dataset and is REFUSED BY NAME — its drawn grain is one COMPONENT
#   change and this dataset states one VERSION; `GAP_R37_IS_A_DIFFERENT_GRAIN`
#   carries the grain and the reads it needs · (2) the drawn source's `audit`
#   half is deliberately NOT built — `TariffVersion.corrected_by`'s own rule is
#   that a rate history read out of `audit_log` loses its BY column silently
#   (`OQ-1340` closed 2026-09-23, no row type exempt) · (3) the drawn
#   *"percentages six"* is `DEF-REP-6829` against the drawing; hard rule 2 and
#   `BR-RAT-087` both say DISPLAY 2 and this file displays nothing · (4) no
#   figure is rounded, reconciled or derived — every value is the stored
#   `Decimal`, which is what keeps a ❄️ FROZEN B4/B5 figure safe
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
