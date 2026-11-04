# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-013 (S30 One-time bill tab, kind = catch-up with a past
#           period · S31 single-account mode — ONE bill, period-labeled line
#           groups, each priced on the tariff version in force THEN)
#           Screens: S30 · S31
# Rules:    BR-BIL-018 (back-bills: arbitrary past period via the single-account
#           flow; usage priced per sub-period against the tariff version in
#           force THEN; window capped by tenant setting, default 12 months,
#           theft cases EXEMPT — OQ-071 CLOSED; reason-coded + approval-gated) ·
#           BR-BIL-014 (the approval gate — the corrections gate; v1 ALL need
#           System Admin approval, OQ-072 CLOSED; no money-bearing write before
#           approval) · BR-RAT-007 (a bill prices on the version in force at the
#           SERVICE date — never today's) · BR-RAT-017 (7-year reproducibility) ·
#           BR-RAT-002 (tiers reset per bill; thresholds scale with the prorated
#           period) · BR-BIL-015 (a missing read is a human decision) ·
#           BR-BIL-023 (a re-run REPLACES its draft) · BR-BIL-004 (a draft is
#           not money) · BR-TEN-043 (event-time law — no clock in this file)
# Tests:    06-backend/tests/test_us_bil_013_backbill.py
# Impacts:  apps/billing/penalty.py (US-BIL-014 prices assessed reads through
#           THIS module, cap-exempt) · S30's One-time bill tab
# ───────────────────────────────────────────────────────
"""Back-bill: one bill for a past window, each sub-period on ITS OWN tariff version.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 rating math and money rounding. ENROLLED
2026-08-12, and the reason is a change this file underwent rather than a
reclassification: implementing the PO's "split by days" ruling made this module
choose THE SHAPE OF THE TAX PASS. Unequal segments force one `price_bill` call
per proration factor, and the decision that every other call prices with no
taxes while its finalized lines are carried into the tax-bearing call — so the
bill is taxed once over Σ(rounded taxable lines), B4.2 exactly — is money law
being APPLIED here. The worked cent it turns on is 6.24 in one pass against
6.23 taxed per segment. The lane that wrote it reported that this file was on
no guard glob and correctly did not add itself; row in
12-governance/09-human-review-ledger.md.

WHAT GOES WRONG IF THIS FILE IS CARELESS, stated first because it is the
reason the story exists. A six-month catch-up priced in one pass uses ONE
tariff version — today's. Every line looks plausible, the bill foots, the
customer pays it, and the utility has charged 2026 prices for 2025 water.
Nobody notices until a customer compares two bills or a regulator asks. That is
BR-RAT-007's failure mode and it is silent by construction, so the guard cannot
be "remember to pass the right date": it has to be the shape of the code.

THE SHAPE, then:

  1. The window arrives as SUB-PERIODS (the unbilled periods being recovered —
     WE-10's six months) and the tariff-version timeline is discovered across
     it by bisecting rating's own `pricing_inputs`, one probe per candidate
     day rather than one per day.
  2. Every sub-period is CUT at each reprice inside it, into day-weighted
     segments (`groups_split_by_days`).
  3. Each group is GATHERED AT ITS OWN SERVICE DATE, so `gather` resolves the
     version in force THEN through that same read — the one the cycle run uses,
     at a different date. There is no new pricing path.
  4. Every group's start and end are ASSERTED to resolve to the SAME version
     (`_assert_one_version_per_group`). A group that straddled a boundary would
     otherwise price its whole span on one side's prices, silently and
     plausibly — the original defect in miniature.
  5. The groups are priced one call per proration factor and TAXED ONCE
     (`price_day_weighted`).

A boundary that lands ON a sub-period edge (WE-10's Apr 1 against monthly
periods) needs no cut at all: Jan–Mar are v3's and Apr–Jun are v4's, and step 4
proves it. A boundary that lands INSIDE a stated sub-period is SPLIT BY DAYS —
the Product Owner's ruling of 2026-08-12 closing OQ-155, worked out in
`groups_split_by_days`.

WHY ONE TAX PASS AND NOT ONE PER GROUP — this is arithmetic, not taste. B4.2
computes tax ONCE over Σ(rounded taxable lines) for the whole bill. WE-10 (❄️
GT-26, machine-verified by 10-scripts/03-golden-verify.py) freezes taxable
**278.82** → tax **26.36** → total **305.18**. Taxing each month separately and
summing gives **26.37** — one cent out, every time, forever. So the groups are
priced per group and TAXED as one bill, which is exactly what `price_bill`
already does across services; this file feeds it (tariff, consumption) pairs
that vary by PERIOD as well as by service. Where the periods carry DIFFERENT
proration factors the seam forces a call per factor, and `price_day_weighted`
still lets exactly one of those calls carry the taxes — see its docstring.

WHERE THE SUB-PERIODS COME FROM — the caller, and that is deliberate. `cycles`
is a single window with no recurrence rule (B2), so "the six months Jan–Jun"
cannot be derived from anything in this database; the wizard knows which
periods were missed. A default of "the whole window as one group" would be the
worst possible guess: 18 kgal of water priced as ONE period puts 13 kgal in the
top tier (104.50) where six monthly groups put 6 (79.50). Nothing here invents
a cadence.

PARTIAL GROUPS — which arise two ways, a reprice landing mid-sub-period and an
account that opened or closed inside the window — USED TO BE REFUSED HERE with a
`NotImplementedError` naming the question below. That refusal was correct for
as long as that question stood: B4.3 read literally prorated a split period's
base across its slices while WE-18, the only worked mid-cycle rate boundary,
charged the base ONCE and said nothing about tier ladders, and choosing between
two defensible readings of signed law is not this module's decision to make.

**The Product Owner ruled on 2026-08-12, verbatim: _"Split by days"_**, and the
refusal is gone. A partial group is now priced the way B4.3 has always priced a
partial period — day-weighted, at the version in force on those days — and this
module states the day counts while `apps.rating` derives the factor from them.
The engineering half of OQ-155 was reported alongside the finance half and is
still true of the seam (`price_bill` takes ONE `BillingPeriod` per call, so
slices of unequal length need a call each); `price_day_weighted` makes one call
per FACTOR and lets exactly one of them carry the bill's taxes, so the ruling is
implemented without moving WE-10's 26.36 by the cent a call-per-slice would.

A CUT SEGMENT WITH NO READ OF ITS OWN — OQ-191, and the second thing this file
USED TO REFUSE. For a few hours on 2026-08-12 a segment whose days nobody read
raised BR-BIL-015 by name ("no usable read for water in 2026-02-01..2026-02-14").
**That refusal was right while the question stood**, and the reasoning was not
careless: *"split by days"* prorates MONEY, the ruling's own example STATED
3 kgal in each half rather than deriving them, B4.3 as amended 2026-08-11 says a
metered usage WITH a read is never prorated, and estimates belong to metering
(BR-MET-026). What it also did was make back-billing fail in exactly the case it
exists for — a six-month catch-up will almost never have a read on the reprice
day — and that was reported to the Product Owner the same day.

**The Product Owner ruled, verbatim: _"B is correct; and if required give option
C also as backup ; I will make B default and C as option for user"_.** So:

  * **DEFAULT** — the stated sub-period's own measured usage is DAY-WEIGHTED
    into each segment (`_estimate_read_less_segments`). The ruling's figure: a
    tariff changing 15 Feb over a 1–28 Feb period of **6 kgal** gives
    **14/28 × 6 = 3 kgal** each side. Every such segment is **MARKED ESTIMATED**,
    and the flag travels to the customer's document (`documents._services`
    prints *"estimated read"*) and to the run's report.
  * **OPTION** — a tenant may instead ask METERING for the estimate under its
    own rules (BR-MET-026). Estimates are metering's, which is why this is the
    better answer wherever it can be had; the read-only seam it needs is
    documented at `METERING_ESTIMATE_ATTRIBUTE` and metering does not publish it
    yet, which is REPORTED rather than faked.
  * **THE REFUSAL SURVIVES** as the behaviour when NEITHER estimate can be
    produced, and it moved EARLIER — to prepare, before a draft exists.

The choice is a tenant setting on S71 (`back_bill_segment_estimate_source`),
seeded to the day weight, read through `segment_estimate_source`.

APPROVAL. BR-BIL-018 is approval-gated by BR-BIL-014's corrections gate, and
TC-3 places it precisely: *"Draft + impact preview exist first; System Admin
approves; only then issue"*. So drafting here is legitimate before approval — a
draft is not money (BR-BIL-004) — and the gate belongs at ISSUE. **That gate is
not implemented anywhere**: US-BIL-017's machinery does not exist and
`apps/billing/issue.py` has no approval check. This module records the approval
mode it read and REPORTS the gap rather than claiming a guarantee it does not
provide (hard-won law 1).

`DEF-BIL-8566` (PO 2026-10-01, *"A · Cart shrinks too: $9.00"*): a counted
service's per-cart charge in each split segment now takes that segment's
day share, like the base — done in the engine's usage stage
(`rating/pricing/stages/price_usage.py`), so nothing here changed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any

from apps.billing import (
    bill_warnings,
    counted_service_line,
    gather,
    models,
    rating_seam,
    runs,
    settings_seam,
    single,
)
from apps.billing.contracts import AccountBillingData, MeasuredUsage
from apps.billing.exceptions import BillingRuleError
from apps.billing.stages import measure_consumption as measure_consumption_stage
from apps.billing.stages.assemble_document import assemble_document
from apps.billing.stages.measure_consumption import measure_consumption
from apps.billing.stages.resolve_subscription import resolve_subscription
from core import tenancy as core_tenancy

#: Why a back-bill is refused. VALUES, not prose — S30 groups on them.
BACKBILL_NO_REASON_CODE = "back_bill_reason_code_required"
BACKBILL_OVER_CAP = "back_bill_window_exceeds_tenant_cap"
BACKBILL_NO_SUB_PERIODS = "back_bill_sub_periods_required"
BACKBILL_BAD_SUB_PERIODS = "back_bill_sub_periods_overlap_or_reversed"
BACKBILL_SPLIT_BROKEN = "back_bill_group_spans_two_tariff_versions"
BACKBILL_NO_VERSION = "back_bill_group_has_no_tariff_version"
#: OQ-191's LAST RESORT — a cut segment whose usage NEITHER estimator can
#: produce. This is what the refusal that shipped on 2026-08-12 became.
BACKBILL_NO_ESTIMATE = "back_bill_segment_usage_cannot_be_estimated"
#: The tenant could not be asked which estimator to use, so no segment is
#: estimated by either. Same posture as an unreadable cap (settings_seam.py).
BACKBILL_NO_ESTIMATE_SOURCE = "back_bill_segment_estimate_source_unreadable"

# ── OQ-191: where a cut segment's USAGE comes from (PO 2026-08-12) ──────────
#: Option B, THE DEFAULT. Billing weights the STATED sub-period's own measured
#: usage by the segment's days — 14/28 × 6 kgal = 3 kgal.
ESTIMATE_DAY_WEIGHTED = "day_weighted"
#: Option C, the tenant OPTION. Ask metering for an estimate under ITS rules
#: (BR-MET-026). Estimates are metering's, which is why this is the better
#: answer wherever it can be had.
ESTIMATE_METERING = "metering"
#: MIRRORED into `apps.tenancy.settings_families.BACK_BILL_SEGMENT_ESTIMATE_
#: SOURCES`, which is the tenant-facing choice list; a test asserts the two are
#: equal, because a value the screen offers and the engine cannot spell would
#: keep day-weighting while the tenant believed otherwise.
SEGMENT_ESTIMATE_SOURCES = (ESTIMATE_DAY_WEIGHTED, ESTIMATE_METERING)
#: The S71 key the tenant's answer lives under (apps.tenancy.settings_families).
KEY_SEGMENT_ESTIMATE_SOURCE = "back_bill_segment_estimate_source"

#: THE METERING SEAM OPTION C ASKS FOR, named once so the contract is greppable
#: from both sides of the boundary (the `settings_seam.py` precedent).
#:
#:     apps.metering.selectors.back_bill_segment_estimate(
#:         unit_id, *, service_code, period_start, period_end
#:     ) -> dict   # metering's own EstimationResult.as_dict() shape:
#:                 # {"estimated": bool, "consumption": str|None, "unit": str|None,
#:                 #  "method": str|None, "reason": str|None, …}
#:
#: ⚠ **METERING PUBLISHES NO SUCH READ TODAY, and that is REPORTED rather than
#: papered over.** The pieces all exist inside metering — `estimation.estimate`
#: is the arithmetic, `services._trailing_actuals` / `_standing_estimates` /
#: `_read_config` assemble its input — but the only entry point is
#: `services.estimate_missing_read`, which WRITES a `meter_reads` row. A phase-1
#: prepare pass writes nothing (that is the whole promise of `PreparedBackBill`),
#: so billing needs the read-only half and cannot build it from here: assembling
#: that input would mean billing reading metering's tables, which B1 forbids and
#: which would put a second copy of BR-MET-026's basis in this module.
#:
#: Resolved at call time, so the day metering authors it every option-C tenant
#: starts using it with no re-wiring step (hard-won law 2). While it is dark,
#: option C produces the PO's ruled DEFAULT and RECORDS that it did — see
#: `_segment_estimate`.
METERING_ESTIMATE_MODULE = "metering"
METERING_ESTIMATE_KIND = "selectors"
METERING_ESTIMATE_ATTRIBUTE = "back_bill_segment_estimate"
#: What the fallback record says when the seam above is not published.
ESTIMATE_METERING_NOT_PUBLISHED = "metering_estimate_seam_not_published"

#: The declared scale of a consumption column, NUMERIC(18,6) — the same scale
#: `apps/metering/estimation.py` quantizes its own estimates to, and what
#: Postgres stores on INSERT regardless. Stated here rather than imported
#: because billing may not import metering (B1).
#:
#: ⚠ THIS IS NOT B4.4 MONEY ROUNDING. Nothing in the day-weighting produces a
#: currency figure: it divides a QUANTITY and hands the result to the engine,
#: which prices and rounds it under BR-RAT-003 exactly as it prices a read.
QUANTITY_SCALE = Decimal("0.000001")


@dataclass(frozen=True)
class BackBillGroup:
    """One period-labeled group: a window, its service date, and its versions.

    `service_date` is the group's FIRST day. Start and end resolve to the same
    version by construction (the split guarantees it and
    `_assert_one_version_per_group` proves it), so either end would price the
    same; the start is the one a human reads as "this group is January's".

    `tariff_version_ids` is `{service_code: version_id}` — the evidence
    US-BIL-013 §5 asks for, captured here from rating's own `pricing_inputs`.

    ⚠ **THE REASON THIS EXISTED HAS HALF GONE AWAY, AND THE FIELD STAYS**
    (amended 2026-08-19, hard-won law 1). It read *"because
    `rating_seam.TariffConfig` does not carry a version id and
    `invoice_lines.tariff_version_id` is therefore never written"*. Both clauses
    are now false: DEF-276 put `version_id` on `TariffConfig`, the engine stamps
    it on every priced line, and stage 6 writes it. So a back bill's LINES now
    name their own versions and `tests/test_us_bil_013_backbill.py` asserts the
    two of them.

    It is kept, and not because it is harmless: this record also carries the
    group WINDOW and the estimator (OQ-191), which `invoice_lines` still cannot
    express — every line of a back bill carries the whole window. Two routes to
    the same version ids is a duplication worth removing the day the line-level
    period labels land; until then removing it would take the group evidence
    with it.

    `cycle_days` is the STATED SUB-PERIOD's length and `days` is this group's
    own — the two numbers B4.3 divides to weight a segment by days (OQ-155, PO
    2026-08-12). They are equal for a group that spans a whole stated
    sub-period, which is every group on a catch-up of whole billing periods, so
    that bill's factor is 1 throughout.
    """

    period_start: date
    period_end: date
    service_date: date
    cycle_days: int
    tariff_version_ids: dict[str, str]
    data: AccountBillingData
    #: `DEF-BIL-8561` (2026-09-30) — the STATED sub-period this group was cut
    #: from (the month the clerk typed on step 1). A July cut at a price change
    #: is two groups and ONE stated period; the bill prints and stores the
    #: month. `None` on a group built before this field existed reads as its
    #: own window.
    owner_start: date | None = None
    owner_end: date | None = None

    def stated_window(self) -> tuple[date, date]:
        """The month this group bills, as the clerk stated it (`DEF-BIL-8561`)."""
        return (self.owner_start or self.period_start, self.owner_end or self.period_end)

    @property
    def days(self) -> int:
        return (self.period_end - self.period_start).days + 1

    def label(self) -> str:
        return f"{self.period_start.isoformat()}..{self.period_end.isoformat()}"


@dataclass(frozen=True)
class SegmentEstimate:
    """One segment's usage that was DERIVED rather than read (OQ-191).

    It exists so the estimate can be SEEN, in both places the ruling names: the
    S30 impact preview a clerk approves from, and the bill's locked payload a
    reprint reads in 2033. A quantity that arrived on a bill without a record of
    where it came from would be indistinguishable from a meter reading, which is
    the defect this whole product is careful about.

    `quantity` carries `unit` and never travels without it (CLAUDE.md rule 3).
    `days`/`cycle_days` are the weight it was derived on, so the arithmetic is
    re-checkable from the record alone. `source` is which estimator ANSWERED —
    not which one the tenant chose, because those differ whenever option C's
    seam is dark, and `fallback_reason` says why.
    """

    period_start: date
    period_end: date
    service_code: str
    quantity: Decimal
    unit: str
    days: int
    cycle_days: int
    source: str
    fallback_reason: str | None = None
    #: The meter, where metering split a point per meter (two meters = two
    #: lines). None on a one-meter point.
    asset_id: str | None = None
    #: 🔒 `DEF-BIL-8564` (2026-09-30) — True only where NO reading measured this
    #: stretch and the quantity is the METER'S OWN ESTIMATE (step 2 of
    #: `_fill_never_read_stretches`). That is the one estimate issue saves into
    #: Meter Reads as an estimated reading (`metering_seam.record_billed_
    #: estimates`). A day-weighted SHARE of a real reading is False and is never
    #: saved: the reading it is a share of is already in Meter Reads, and saving
    #: the share too would make the next true-up subtract the same usage twice.
    unmeasured: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "service_code": self.service_code,
            "quantity": str(self.quantity),
            "unit": self.unit,
            "days": self.days,
            "cycle_days": self.cycle_days,
            "source": self.source,
            "fallback_reason": self.fallback_reason,
            "asset_id": self.asset_id,
            "unmeasured": self.unmeasured,
        }


@dataclass(frozen=True)
class PreparedBackBill:
    """Phase 1 of a back-bill — every group gathered, nothing written.

    Same promise `prepare_run` makes and for the same reason: the PO's flow
    looks before it commits, and a prepare pass that wrote would make looking a
    committing action.

    `estimate_source` is what the TENANT chose (OQ-191) and `estimates` is what
    was actually derived, one row per (segment, service). Both are on the
    preview deliberately: a clerk who approves a six-month catch-up without
    being told which of its segments carry derived usage has approved something
    they were not shown.
    """

    account_id: str
    account_no: str
    period_start: date
    period_end: date
    reason_code: str
    theft: bool
    cap_months: int
    approval_mode: str
    groups: tuple[BackBillGroup, ...] = ()
    estimate_source: str = ESTIMATE_DAY_WEIGHTED
    estimates: tuple[SegmentEstimate, ...] = ()

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def estimated_segment_count(self) -> int:
        """How many (segment, service) usages on this bill were DERIVED."""
        return len(self.estimates)


# ── the version timeline, discovered through rating's published read ────────


def _pricing_inputs() -> Any:
    inputs = gather._resolve("rating", "pricing_inputs")
    if inputs is None:
        raise gather.GatherProblem(
            gather.GATHER_NO_VERSION,
            "rating has not published pricing_inputs, so the tariff versions in force "
            "across this window cannot be found. Nothing is guessed — a back-bill that "
            "cannot see the version timeline would price every month at one rate.",
        )
    return inputs


def _version_id_at(tariff: Any, day: date) -> str | None:
    """The version id in force for this tariff on this day, or None if there is none.

    Rating's own `pricing_inputs` (BR-RAT-007) — the SAME read the gather step
    uses to price. Asking a second source what the version timeline looks like
    is how the timeline used for splitting and the timeline used for pricing
    come to disagree.
    """
    inputs = _pricing_inputs()(tariff, day)
    return None if inputs is None else str(inputs["version_id"])


def _boundaries_between(
    tariff: Any, lo: date, hi: date, lo_id: str | None, hi_id: str | None, found: list[date]
) -> None:
    """Bisect (lo, hi] for every day whose version differs from the day before.

    A version's effective window is a single contiguous block (B2's EXCLUDE
    constraint: windows never overlap, BR-RAT-037 — every change is a NEW row),
    so a range whose ends carry the same version carries it throughout and a
    range whose ends differ contains at least one boundary. Divide and conquer
    therefore finds every boundary and can miss none.

    Roughly `k · log(days)` probes for k boundaries — nine for a year — against
    a window the tenant cap holds to twelve months. The alternative, walking
    day by day, is 365 queries per tariff for the same answer.
    """
    if lo_id == hi_id or lo >= hi:
        return
    if (hi - lo).days == 1:
        found.append(hi)
        return
    mid = lo + timedelta(days=(hi - lo).days // 2)
    mid_id = _version_id_at(tariff, mid)
    _boundaries_between(tariff, lo, mid, lo_id, mid_id, found)
    _boundaries_between(tariff, mid, hi, mid_id, hi_id, found)


def version_boundaries(tariff: Any, *, period_start: date, period_end: date) -> tuple[date, ...]:
    """Every day inside (period_start, period_end] on which this tariff repriced.

    Returned as the FIRST day of each new version's stretch, which is what a
    split needs: a boundary of Apr 1 cuts Jan 1–Jun 30 into Jan 1–Mar 31 and
    Apr 1–Jun 30 (WE-10 exactly).
    """
    found: list[date] = []
    _boundaries_between(
        tariff,
        period_start,
        period_end,
        _version_id_at(tariff, period_start),
        _version_id_at(tariff, period_end),
        found,
    )
    return tuple(sorted(set(found)))


def _plan_tariffs(unit_id: Any) -> list[dict[str, Any]]:
    """The plan's per-service tariff ROWS, resolved exactly as `gather` does.

    Same seams, same reason CODES on refusal (`unit_has_no_plan`,
    `plan_has_no_tariff_for_service`), so a back-bill's exceptions group with
    the run's on the same screen instead of introducing a second vocabulary for
    the same facts.
    """
    unit_row = gather._resolve("metering", "unit_row")
    schedules = gather._resolve("rating", "plan_rate_schedules")
    if unit_row is None or schedules is None:
        raise gather.GatherProblem(
            gather.GATHER_NO_TARIFF,
            "metering/rating have not published unit_row/plan_rate_schedules, so this "
            "unit's rate schedules cannot be resolved. No service is dropped quietly.",
        )
    plan_id = getattr(unit_row(unit_id), "rate_plan_id", None)
    if plan_id is None:
        raise gather.GatherProblem(
            gather.GATHER_NO_PLAN,
            f"unit {unit_id} has no plan (BR-MET-040), so there is no version timeline "
            "to split this back-bill on.",
        )
    rows = list(schedules(plan_id))
    if not rows:
        raise gather.GatherProblem(
            gather.GATHER_NO_TARIFF,
            f"plan {plan_id} resolves to no tariff for any service. A back-bill with no "
            "services is not a $0.00 bill — it is a configuration problem a human sees.",
        )
    return rows


# ── the window: sub-periods in, groups out ──────────────────────────────────


def months_spanned(period_start: date, period_end: date) -> int:
    """How many calendar months this window TOUCHES (BR-BIL-018's cap unit).

    The rule states a cap in months and no signed document defines the count,
    so this file states it once, conservatively, and it is recorded as a
    judgment call in 12-governance/02-decision-log.md (2026-08-11): a window
    that reaches into a thirteenth calendar month is 13 months against a
    12-month cap, even if it is a day long there. Conservative is the correct
    direction of error for a consumer-protection limit — it refuses a case a
    human can approve as theft or shorten, where the permissive reading would
    silently allow a longer reach back than the tenant configured.

    Worked: Jan 1 → Jun 30 = 6 (WE-10, inside a 12-month cap). Jan 1 2025 →
    Feb 28 2026 = 14 (US-BIL-013 TC-4, refused unless theft-coded).
    """
    return (period_end.year - period_start.year) * 12 + (period_end.month - period_start.month) + 1


def _checked_sub_periods(sub_periods: Any) -> tuple[tuple[date, date], ...]:
    """The caller's segmentation, validated. Never defaulted — see the docstring."""
    windows = tuple((start, end) for start, end in sub_periods or ())
    if not windows:
        raise gather.GatherProblem(
            BACKBILL_NO_SUB_PERIODS,
            "a back-bill needs its sub-periods stated: the unbilled periods being "
            "recovered (WE-10's six months). They are not defaulted to one whole-window "
            "group, because tiers reset PER BILLING PERIOD (BR-RAT-002) — 18 kgal priced "
            "as one period puts 13 kgal in the top tier where six monthly groups put 6, "
            "and the difference lands on a customer's bill.",
        )
    previous_end: date | None = None
    for start, end in windows:
        if end < start:
            raise gather.GatherProblem(
                BACKBILL_BAD_SUB_PERIODS,
                f"sub-period {start} → {end} ends before it begins.",
            )
        if previous_end is not None and start <= previous_end:
            raise gather.GatherProblem(
                BACKBILL_BAD_SUB_PERIODS,
                f"sub-period starting {start} overlaps the one ending {previous_end}. "
                "Overlapping groups bill the same days twice on one bill, which no "
                "correction can unpick cleanly.",
            )
        previous_end = end
    return windows


def charge_price_cuts(
    service_codes: Any, *, period_start: date, period_end: date
) -> set[date]:
    """🔒 `CR-156-BRC10` — the days in (period_start, period_end] on which a
    BASE charge code's price changes for these services, read from rating's
    published `charge_price_boundaries`.

    PO 2026-10-01, option A, ruled (4): *"a period crossing a change is split
    by days"*. Every splitting path cuts at these days beside its tariff-version
    cuts — this back-bill's `groups_split_by_days`, the ordinary bill's
    `midperiod.split_boundaries`, and the interim bill's price-only split — so
    each part is gathered on its own first day and reads the price row in force
    then. **Defensive on absence**: a rating half that publishes no reader, or
    no service list, yields no cut and the bill prices exactly as before.
    """
    codes = tuple(sorted({code for code in (service_codes or ()) if code}))
    if not codes:
        return set()
    read = gather._resolve("rating", "charge_price_boundaries")
    if read is None:
        return set()
    return set(read(codes, period_start=period_start, period_end=period_end))


def charge_price_cuts_by_service(
    service_codes: Any, *, period_start: date, period_end: date
) -> dict[str, set[date]]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-9012` — `charge_price_cuts`, asked
    ONE SERVICE AT A TIME, so a caller knows WHOSE price changed on each day.

    PO 2026-10-01, option A (decision log *"A BILL CUT AT ONE CHARGE CODE'S
    PRICE CHANGE SPLITS ONLY THE SERVICE WHOSE PRICE CHANGED"*): *"Split only
    the service whose price changed. Electric stays $12.00, and only water is
    split."* The union `charge_price_cuts` answers cannot say that, so every
    splitting path cut every service at a water reprice. Only days inside
    (period_start, period_end] are kept; defensive on absence exactly like the
    union (no reader → `{}` → nothing cut).
    """
    codes = sorted({str(code) for code in (service_codes or ()) if code})
    out: dict[str, set[date]] = {}
    for code in codes:
        cuts = {
            cut
            for cut in charge_price_cuts([code], period_start=period_start, period_end=period_end)
            if period_start < cut <= period_end
        }
        if cuts:
            out[code] = cuts
    return out


def cut_groups(
    service_codes: Any,
    *,
    common_cuts: Any,
    service_cuts: dict[str, set[date]],
    linked: dict[str, str] | None = None,
) -> tuple[tuple[tuple[str, ...] | None, tuple[date, ...]], ...]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-9012` — which services are cut where.

    **PO 2026-10-01, option A, verbatim: *"Split only the service whose price
    changed. Electric stays $12.00, and only water is split."*** Ruled: (1) a
    cut at a charge code's price change applies only to the lines priced by
    THAT code; (2) every other service is priced over the period as ONE part,
    exactly as if no cut existed; (3) the changed service's own split is
    unchanged.

    `common_cuts` are the cuts that still cut EVERY service — a plan
    reassignment and a rate-schedule (tariff) version boundary (`BR-RAT-114`,
    untouched by this ruling, which is about the charge code's dated price
    alone). `service_cuts` is `charge_price_cuts_by_service`'s answer.

    Returns `(services, cuts)` pairs. **`services` is `None` when every service
    shares one set of cuts** — the identity: the caller gathers every service
    together exactly as it did before this ruling, so a bill with one service,
    or with no charge-code change, or whose services all repriced on the same
    day, walks byte-for-byte the path it walked. Otherwise one pair per
    distinct cut set, the group with the FEWEST cuts first (an uncut group —
    priced whole — is therefore always first, which `midperiod.price_split_bill`
    relies on so that its unstamped lines are never stamped with another part's
    dates).

    `linked` (`{percent-of-service: basis}`, `gather._percent_of_service_bases`)
    keeps a percentage-of-service in its basis's group: sewer priced as 60% of
    water is priced in the same call as the water it is a percentage of, so a
    water reprice moves sewer with it and a sewer reprice cuts water too.

    WORKED, the PO's case: bill 10/16–11/15, water $8.00 → $9.00 from 11/01,
    electric $12.00 unchanged → `((("electric",), ()), (("water",), (11/01,)))`:
    electric one part, 31 days over the bill's own denominator = **$12.00**
    (it was 16/31 × 12 + 15/30 × 12 = $6.19 + $6.00 = **$12.19**); water
    16/31 × 8 + 15/30 × 9 = $4.13 + $4.50 = **$8.63**.
    """
    codes = sorted({str(code) for code in (service_codes or ()) if code})
    common = frozenset(common_cuts or ())
    if not codes:
        return ((None, tuple(sorted(common))),)
    # Union the cut sets across every percent-of-service link (transitively).
    parent: dict[str, str] = {code: code for code in codes}

    def root(code: str) -> str:
        while parent[code] != code:
            parent[code] = parent[parent[code]]
            code = parent[code]
        return code

    for child, basis in (linked or {}).items():
        if child in parent and basis in parent:
            parent[root(child)] = root(basis)
    component_cuts: dict[str, set[date]] = {}
    for code in codes:
        component_cuts.setdefault(root(code), set()).update(service_cuts.get(code, ()))
    by_cuts: dict[frozenset[date], list[str]] = {}
    for code in codes:
        by_cuts.setdefault(common | frozenset(component_cuts[root(code)]), []).append(code)
    if len(by_cuts) == 1:
        (only,) = by_cuts
        return ((None, tuple(sorted(only))),)
    ordered = sorted(by_cuts.items(), key=lambda item: (len(item[0]), sorted(item[0]), item[1]))
    return tuple((tuple(group), tuple(sorted(cuts))) for cuts, group in ordered)


def _narrowed_scope(
    scope_services: tuple[str, ...] | None, group: tuple[str, ...] | None
) -> tuple[str, ...] | None:
    """The caller's service scope narrowed to one `cut_groups` group.

    `group is None` (every service shares the cuts) returns the caller's scope
    UNCHANGED — the identity. `()` means the caller's scope excludes every
    service of this group, and the group is skipped."""
    if group is None:
        return scope_services
    return tuple(code for code in group if scope_services is None or code in scope_services)


def groups_split_by_days(
    windows: tuple[tuple[date, date], ...], tariffs: list[dict[str, Any]]
) -> tuple[tuple[date, date, date, date, tuple[str, ...] | None], ...]:
    """Every stated sub-period, CUT at each reprice into day-weighted segments.

    Returns `(segment_start, segment_end, period_start, period_end)` — the last
    pair being the STATED SUB-PERIOD the segment was cut out of. Its LENGTH is
    the proration denominator the segment carries into `gather_single`: a
    segment of 14 days out of a stated 28-day February arrives at the engine as
    `service_days=14, cycle_days=28`, and B4.3's calendar-day factor (½) is
    derived by `apps.rating.proration` from those two numbers — this module
    states the day counts and performs no proration arithmetic of its own.

    The sub-period is returned WHOLE rather than as a day count because OQ-191
    needs its window, not only its length: a segment with no read of its own is
    day-weighted from what that SUB-PERIOD measured, and the caller has to be
    able to ask metering about those dates (`_estimate_read_less_segments`).

    The boundaries are computed across every service on the plan, because a
    plan is a bundle: a water reprice on Apr 1 cuts the segment for the WHOLE
    bill, so that every line in a segment belongs to one set of prices. Cutting
    per service would produce overlapping segments and a period-labeled bill
    would carry two different labels for the same days.

    WHEN A BOUNDARY FALLS ON A SUB-PERIOD EDGE — WE-10's Apr 1 against monthly
    periods — there is nothing to cut: Jan–Mar are already v3's and Apr–Jun are
    already v4's. Such a sub-period comes back as ONE segment whose length is
    its own denominator, so its factor is exactly 1 and WE-10's frozen figures
    are reached by the same arithmetic as before.

    WHEN IT FALLS INSIDE ONE, **OQ-155 rules how it is priced and the ruling is
    "Split by days"** (Product Owner, 2026-08-12, verbatim; recorded in
    12-governance/02-decision-log.md). Until 2026-08-12 this refused with
    `NotImplementedError`, because two signed rules pointed different ways and
    choosing between them was not this code's call. The PO chose, and the choice
    was the reading B4.3 already carries: each segment is priced at the version
    in force on ITS days, day-weighted, exactly as any other partial period is.

    WORKED, on WE-10's own water tariff (the PO's own example): a February
    back-bill group of 6 kgal that reprices on Feb 15, 3 kgal in each half.

        v3 (T1 4.00 / T2 6.50 / base 8.00), 14 days of 28 — base 8.00 × 14/28 =
           **4.00**; the 5 kgal first block scales with the period to 2.5 kgal
           (BR-RAT-002), so 2.5 × 4.00 = **10.00** and 0.5 × 6.50 = **3.25**.
        v4 (4.25 / 6.85 / 8.50), 14 days of 28 — base **4.25**; 2.5 × 4.25 =
           10.625 → **10.63** and 0.5 × 6.85 = 3.425 → **3.43**.
        group — **35.56**.

    The group total is 35.56 and NOT the 35.55 written into OQ-155's option (a):
    BR-RAT-003 (B4.4, finance-signed) rounds PER LINE, and the OQ's illustration
    summed a half's two tier amounts before rounding. The ruled RULE is what is
    implemented; the cent is the signed rounding law, REPORTED here rather than
    adjusted for.

    NOTHING IS SPLIT THAT THE TARIFF DID NOT SPLIT. A sub-period with no reprice
    inside it is untouched, so a catch-up of whole billing periods walks exactly
    the path it walked before this function was renamed.

    ⚠ **AMENDED 2026-10-01 (`DEF-BIL-9012`, PO option A) — A CHARGE CODE'S
    PRICE CHANGE CUTS ONLY THE SERVICE IT PRICES.** The paragraph above about a
    plan being a bundle stays true of a TARIFF VERSION boundary, which still
    cuts every service. A base charge code's dated price (`CR-156-BRC10`) cuts
    only its own service's lines; every other service in the sub-period is ONE
    segment over the whole sub-period, as if nothing had changed. Each row
    therefore carries a fifth element, the services it gathers — `None` (every
    service, the identity) whenever all services share one set of cuts, which
    is every sub-period with no charge-code change in it.
    """
    out: list[tuple[date, date, date, date, tuple[str, ...] | None]] = []
    services = [row.get("service_code") for row in tariffs]
    for start, end in windows:
        common: set[date] = set()
        for row in tariffs:
            common |= set(version_boundaries(row["tariff"], period_start=start, period_end=end))
        common = {cut for cut in common if start < cut <= end}
        # CR-156-BRC10 — and at every day a base charge code's price changes,
        # for THAT code's service only (DEF-BIL-9012, PO 2026-10-01 option A).
        groups = cut_groups(
            services,
            common_cuts=common,
            service_cuts=charge_price_cuts_by_service(services, period_start=start, period_end=end),
            linked=_percent_links(tariffs, start, end),
        )
        for group, cuts in groups:
            segment_start = start
            for cut in cuts:
                out.append((segment_start, cut - timedelta(days=1), start, end, group))
                segment_start = cut
            out.append((segment_start, end, start, end, group))
    return tuple(out)


def _percent_links(tariffs: list[dict[str, Any]], start: date, end: date) -> dict[str, str]:
    """`{percent-of-service: basis}` on this plan, read on both edges of the
    window — `gather._percent_of_service_bases` resolved per tariff row rather
    than per plan, because this module holds tariff rows. Defensive on absence
    (no reader → `{}`), so a link nobody can read simply does not join groups."""
    pricing = gather._resolve("rating", "pricing_inputs")
    if pricing is None:
        return {}
    links: dict[str, str] = {}
    for row in tariffs:
        code = row.get("service_code")
        if not code or row.get("tariff") is None:
            continue
        for day in (start, end):
            try:
                inputs = gather._call_pricing_inputs(pricing, row["tariff"], day, None)
            except Exception:  # noqa: BLE001 — discovery only; pricing refuses on its own path
                inputs = None
            if inputs and inputs.get("model") == "percent_of_service" and inputs.get("basis_service"):
                links[str(code)] = str(inputs["basis_service"])
    return links


def _assert_one_version_per_group(
    tariffs: list[dict[str, Any]], period_start: date, period_end: date
) -> dict[str, str]:
    """Every service's version id for this group — and proof there is only one.

    THE GUARD THIS FILE EXISTS FOR. If the split ever missed a boundary, the
    group's first and last day would resolve to different versions and the
    whole group would price on whichever date was passed — silently, and
    plausibly. It refuses instead, by name.
    """
    versions: dict[str, str] = {}
    for row in tariffs:
        code = row["service_code"]
        at_start = _version_id_at(row["tariff"], period_start)
        at_end = _version_id_at(row["tariff"], period_end)
        if at_start is None or at_end is None:
            raise gather.GatherProblem(
                BACKBILL_NO_VERSION,
                f"service {code!r} has no tariff version in force across "
                f"{period_start} → {period_end}. BR-RAT-007: there is no fallback to "
                "today's prices, because that would silently re-price history.",
                service_code=code,
            )
        if at_start != at_end:
            raise gather.GatherProblem(
                BACKBILL_SPLIT_BROKEN,
                f"service {code!r} changes tariff version inside the group "
                f"{period_start} → {period_end} ({at_start} → {at_end}). The window was "
                "not cut at that boundary, so pricing the group would apply ONE set of "
                "prices to days that had two.",
                service_code=code,
            )
        versions[code] = at_start
    return versions


# ── OQ-191: a cut segment nobody read (PO 2026-08-12) ───────────────────────


def segment_estimate_source() -> str:
    """WHICH estimator this tenant chose for a read-less cut segment (OQ-191).

    Read, never defaulted here. The ratified default (`day_weighted`) lives once
    in `apps.tenancy.settings_families` as a seeded `Param` and is merged in by
    tenancy's own read — a `.get(key, "day_weighted")` in this module would be a
    second copy of a PO-ruled answer, free to drift from the one S71 shows.
    That is `settings_seam.py`'s whole posture and it is followed rather than
    re-argued.

    REFUSES on a missing or unrecognised value rather than falling back: an
    unreadable setting is not the default, and quietly day-weighting for a
    tenant who asked for metering's estimate would decide a customer's billed
    usage on a value nobody could read.
    """
    values = settings_seam.finance_controls()
    if KEY_SEGMENT_ESTIMATE_SOURCE not in values:
        raise gather.GatherProblem(
            BACKBILL_NO_ESTIMATE_SOURCE,
            f"the tenant's finance-controls settings carry no "
            f"{KEY_SEGMENT_ESTIMATE_SOURCE!r}, so where a split segment's usage comes "
            "from (OQ-191) cannot be established. The ratified default lives in "
            "apps.tenancy.settings_families and is merged in by tenancy's own read; a "
            "default substituted here would be a second copy of a PO-ruled answer.",
        )
    chosen = str(values[KEY_SEGMENT_ESTIMATE_SOURCE])
    if chosen not in SEGMENT_ESTIMATE_SOURCES:
        raise gather.GatherProblem(
            BACKBILL_NO_ESTIMATE_SOURCE,
            f"the tenant's {KEY_SEGMENT_ESTIMATE_SOURCE} is {chosen!r}, which is not one "
            f"of the two the Product Owner ruled ({', '.join(SEGMENT_ESTIMATE_SOURCES)}, "
            "OQ-191 2026-08-12). The back-bill is refused rather than run on an "
            "estimator nobody defined.",
        )
    return chosen


def _day_weighted_quantity(period_amount: Decimal, *, days: int, cycle_days: int) -> Decimal:
    """OPTION B, the PO's DEFAULT: the period's usage, weighted by the segment's days.

        segment usage = period usage × segment days ÷ stated sub-period days

    **Worked, the PO's own:** a tariff changes 15 Feb, the sub-period is 1–28
    Feb and measured **6 kgal**; each 14-day segment gets 6 × 14/28 =
    **3.000000 kgal**.

    A QUANTITY and nothing else — no rate is read here and no currency figure is
    produced. Pricing it is the engine's, which weights the BASE CHARGE and the
    TIER LADDER from the same day counts (B4.3 / BR-RAT-002) and rounds per line
    (BR-RAT-003). Quantized to the consumption column's own NUMERIC(18,6) scale,
    which is what makes 6 × 14/28 reproduce as `3.000000` rather than as a
    repeating tail; `Decimal` throughout, never a binary float.
    """
    return (period_amount * Decimal(days) / Decimal(cycle_days)).quantize(QUANTITY_SCALE)


def _metering_estimate(
    unit_id: Any,
    *,
    service_code: str,
    period_start: date,
    period_end: date,
    asset_id: Any = None,
) -> tuple[Decimal | None, str | None, str | None]:
    """OPTION C: ask metering for this segment's usage under BR-MET-026.

    Returns `(quantity, unit, reason)` — a quantity with its unit when metering
    answers, and `(None, None, reason)` when it will not. The reason is
    metering's OWN (`no_history`, `consecutive_estimate_cap_reached`,
    `demand_never_estimated`, …) and is carried verbatim onto the estimate
    record, because "no history — field visit" is a next step a clerk can act on
    where "metering declined" is not.

    RESOLVED AT CALL TIME through the same `gather._resolve` idiom every other
    cross-module read in this file uses (`pricing_inputs`, `unit_row`,
    `plan_rate_schedules`). No import binds billing to metering's internals and
    nothing here re-implements BR-MET-026's basis.

    ⚠ **NOT PUBLISHED TODAY** — see `METERING_ESTIMATE_ATTRIBUTE`. The absence
    is reported as `ESTIMATE_METERING_NOT_PUBLISHED`, never as a metering
    refusal: "metering says no estimate is lawful here" and "nobody has written
    the read yet" are different facts and only one of them is about this
    customer.
    """
    estimate = gather._resolve(
        METERING_ESTIMATE_MODULE, METERING_ESTIMATE_ATTRIBUTE, METERING_ESTIMATE_KIND
    )
    if estimate is None:
        return None, None, ESTIMATE_METERING_NOT_PUBLISHED
    answer = estimate(
        unit_id,
        service_code=service_code,
        period_start=period_start,
        period_end=period_end,
        asset_id=asset_id,
    )
    if not answer or not answer.get("estimated"):
        reason = (answer or {}).get("reason") or "metering_declined_without_a_reason"
        return None, None, str(reason)
    amount = answer.get("consumption")
    unit = answer.get("unit")
    if amount is None or not unit:
        # CLAUDE.md rule 3. Metering never emits a unitless quantity, so this
        # means the contract changed — and a quantity billed against the
        # tariff's assumed unit is unfixable once the bill is issued.
        return None, None, "metering_estimate_carried_no_quantity_or_unit"
    return Decimal(str(amount)), str(unit), None


def _estimate_read_less_segments(
    scope: Any,
    gathered: list[tuple[date, date, dict[str, str], AccountBillingData]],
    *,
    sub_start: date,
    sub_end: date,
    source: str,
    scope_services: tuple[str, ...] | None,
) -> tuple[
    list[tuple[date, date, dict[str, str], AccountBillingData]], tuple[SegmentEstimate, ...]
]:
    """Fill in the usage of a CUT sub-period's segments that nobody read.

    **PO ruling 2026-08-12, verbatim: _"B is correct; and if required give
    option C also as backup ; I will make B default and C as option for user"_**
    (OQ-191, recorded in 12-governance/02-decision-log.md).

    THE DECISION IS ABOUT THE SUB-PERIOD, NOT ABOUT ONE SEGMENT, and that is the
    whole shape of this function. In the PO's example the meter was read on the
    1st and the 28th: the 28th's read exists inside the second segment, but what
    it MEASURES is the whole month, so billing 6 kgal to Feb 15–28 and 3 kgal to
    Feb 1–14 would charge 9 kgal for a month that used 6. So when ANY segment of
    a cut sub-period has no read, that service's usage is day-weighted across
    EVERY segment of it — **14/28 × 6 = 3 kgal each side**, which is the ruling's
    own figure — and every one of them is marked ESTIMATED.

    WHEN EVERY SEGMENT HAS ITS OWN READ, NOTHING HAPPENS HERE. That is the
    ruling's negative half (EP-BIL-03 TC-11): day-weighting applies to the base
    charge and the tier ladder, never to metered usage that was actually
    measured (B4.3 as amended 2026-08-11 — "the reading IS the consumption").

    OPTION C FALLS BACK TO OPTION B, AND SAYS SO. Where the tenant chose
    metering and metering cannot answer — the seam is unpublished, or
    BR-MET-026/027/062 refuse — the segment takes the PO's ruled DEFAULT and the
    record carries `source=day_weighted` with `fallback_reason` naming what
    happened. That is the ruling read as written ("refusal remains only where
    NEITHER estimate can be produced") and it is the opposite of a silent
    substitution: nothing claims metering produced a figure it did not.

    THE REFUSAL SURVIVES as the last resort. With no measurement anywhere in the
    sub-period there is nothing to weight and metering has nothing to work from,
    so this raises `BACKBILL_NO_ESTIMATE` naming the SEGMENT — at PREPARE, before
    a draft exists or an invoice number is spent.

    A BASE-ONLY service is untouched: BR-CUS-055 says that account is not being
    billed usage at all, and estimating one for it would invent a charge.

    ⚠ **AND NEITHER IS ANY OTHER SERVICE THAT WAS NEVER OWED A READ
    (`DEF-BIL-5326`, 2026-09-15).** This set read `!= ABSENT_BASE_ONLY` and so
    put a PERCENT-OF-SERVICE sewer on the list of services to go and estimate.
    Nothing can ever be estimated for one: BR-RAT-015 prices sewer as a
    percentage of WATER, its `consumption` is `None` by design and for ever, and
    a sewer service point commonly has no meter at all. So a back-bill over a
    sub-period the tariff had CUT would refuse with `BACKBILL_NO_ESTIMATE`
    naming sewer — the same defect as the one `_measured` carried, wearing a
    different refusal.

    ⚠ **AND IT IS ASKED OF THE TARIFF, NOT OF THE READING'S `absent_reason`,
    WHICH IS THE PART THAT COST A CYCLE TO FIND.** The two carry DIFFERENT
    VOCABULARIES for one service. Measured on account `E11-0001`: sewer's
    READING says `no_meter` — metering's honest answer, since there is no sewer
    meter — while the SERVICE that `measure_consumption` derives from the same
    data says `tariff_prices_no_consumption`. Only the second is on
    `EXEMPT_FROM_MISSING_READ`, so filtering this set by the reading's reason
    exempts trash and leaves sewer exactly where it was. Whether a read was ever
    OWED is a fact about the TARIFF's pricing model, which metering cannot know
    and which `data.tariffs` states right here.
    """
    # DEF-BIL-8310 — `TariffConfig`'s field is `.service`. This read
    # `.service_code`, which only the SimpleNamespace tariffs of the tests
    # carried, so every real catch-up and penalty preview answered 500.
    never_read = {
        tariff.service
        for _s, _e, _v, data in gathered
        for tariff in data.tariffs
        if measure_consumption_stage.prices_no_consumption(tariff)
        or measure_consumption_stage.bills_base_only(tariff)
    }
    # 2026-09-30 — keyed by (service, METER). Two meters on one metered
    # service are two readings (PO: "both meter should be build … as a
    # speearte line"); keyed by the code alone, the second meter's period
    # quantity overwrote the first and BOTH meters were apportioned it. A
    # reading naming no meter keys as (code, None): byte-identical before.
    # `DEF-BIL-8323` — a service NOT IN SERVICE (no point, or a point with no
    # asset: BR-BIL-300/301, PO 2026-09-30) prints no line and is never owed a
    # read. Metering still reports its point as `no_meter`, so without this it
    # was listed as short and refused the whole catch-up — the same exclusion
    # `runs._decisions_for` makes for the same reason.
    not_in_service = {
        str(code)
        for _s, _e, _v, data in gathered
        for code in (getattr(data, "unconnected_services", ()) or ())
    }
    short = {
        (reading.service_code, getattr(reading, "asset_id", None))
        for _s, _e, _v, data in gathered
        for reading in data.readings
        if reading.consumption is None
        and reading.service_code not in never_read
        and reading.service_code not in not_in_service
        and reading.absent_reason not in measure_consumption_stage.EXEMPT_FROM_MISSING_READ
    }
    if not short:
        return gathered, ()

    # WHAT THE STATED SUB-PERIOD MEASURED — read through the same helper
    # `gather_single` uses, so "what does metering say about this window" has
    # one implementation and one handling of a unitless quantity (rule 3).
    period_readings, _unmeasured = runs.readings_for_account(
        scope.account,
        period_start=sub_start,
        period_end=sub_end,
        scope_services=scope_services,
    )
    measured = {
        (reading.service_code, getattr(reading, "asset_id", None)): reading.consumption
        for reading in period_readings
        if reading.consumption is not None
    }
    cycle_days = (sub_end - sub_start).days + 1

    out: list[tuple[date, date, dict[str, str], AccountBillingData]] = []
    made: list[SegmentEstimate] = []
    for seg_start, seg_end, versions, data in gathered:
        days = (seg_end - seg_start).days + 1
        label = f"{seg_start.isoformat()}..{seg_end.isoformat()}"
        readings: list[Any] = []
        for reading in data.readings:
            key = (reading.service_code, getattr(reading, "asset_id", None))
            if key not in short:
                readings.append(reading)
                continue
            quantity, unit, fallback = (None, None, None)
            if source == ESTIMATE_METERING:
                quantity, unit, fallback = _metering_estimate(
                    scope.unit_id,
                    service_code=reading.service_code,
                    period_start=seg_start,
                    period_end=seg_end,
                    asset_id=getattr(reading, "asset_id", None),
                )
            if quantity is None:
                period_quantity = measured.get(key)
                if period_quantity is None:
                    # ⚠ `DEF-BIL-8324` (PO 2026-09-30, option A). This RAISED
                    # `BACKBILL_NO_ESTIMATE` here. A sub-period that measured
                    # nothing is a stretch NOBODY READ, and the whole catch-up
                    # decides it (`_fill_never_read_stretches`): a later read
                    # that measured it is shared by days, and failing that the
                    # meter's own estimate. The segment is left as it was.
                    readings.append(reading)
                    continue
                quantity = _day_weighted_quantity(
                    period_quantity.amount, days=days, cycle_days=cycle_days
                )
                unit = period_quantity.unit  # rule 3 — the period's own unit, never assumed
                used = ESTIMATE_DAY_WEIGHTED
            else:
                used = ESTIMATE_METERING
            readings.append(
                replace(
                    reading,
                    consumption=rating_seam.Quantity(amount=quantity, unit=unit),
                    # THE FLAG. It is not decoration: it changes what the bill
                    # says (`documents._services` prints "estimated read"), and
                    # it is the difference between telling a customer their
                    # usage was derived and letting them read it as a meter
                    # reading.
                    estimated=True,
                    absent_reason=None,
                )
            )
            made.append(
                SegmentEstimate(
                    period_start=seg_start,
                    period_end=seg_end,
                    service_code=reading.service_code,
                    quantity=quantity,
                    unit=unit,
                    days=days,
                    cycle_days=cycle_days,
                    source=used,
                    fallback_reason=fallback if used != source else None,
                    asset_id=getattr(reading, "asset_id", None),
                )
            )
        out.append((seg_start, seg_end, versions, replace(data, readings=tuple(readings))))
    return out, tuple(made)


# ── DEF-BIL-8324: a stretch of the catch-up nobody read (PO 2026-09-30) ─────

#: The one absence a catch-up may fill: metering says there is NO READ. A read
#: that exists and is flagged (`read_flagged`) is a human's judgment and is left
#: for BR-BIL-015; a keyed value that could not be read is left too.
NEVER_READ_REASONS = frozenset({"no_read"})


def _fill_never_read_stretches(
    scope: Any,
    gathered: list[list[Any]],
    *,
    waiting_ok: bool = False,
) -> tuple[SegmentEstimate, ...]:
    """Price every stretch of the catch-up where a meter was never read.

    **PO ruling 2026-09-30, verbatim: *"A for catch-up estimate"*** (BR-BIL-018,
    `DEF-BIL-8324`). Walked over the WHOLE catch-up, one meter at a time, in
    date order — because whether a month was measured is a question about the
    months after it, not about the month alone.

    **1 · A READ THAT MEASURED THE STRETCH IS USED FIRST.** A read taken after a
    month nobody read counts up from the last read before it
    (`measured_from`), so it measured that month too. It is SHARED by days
    across every segment it measured — OQ-191's day-weighting, the ruled
    DEFAULT — and each share is marked estimated. Billing it whole in its own
    month while the empty month is estimated again would bill the same usage
    twice. A reading the clerk typed on step 2 arrives here as exactly such a
    read (`keyed_reads`), which is the *"used first"* half of the ruling.
    Worked: read on Feb 28 and Apr 30, none in March, 6 kgal measured → March
    6 × 31/61, April 6 × 30/61.

    **2 · WHAT NO READ MEASURED TAKES THE METER'S OWN ESTIMATE** — metering's,
    from the meter's reading history under BR-MET-026 (OQ-191's option C, as
    the fallback the PO ruled), marked estimated, and the bill line carries the
    estimated flag and the step's warning.

    **3 · AND THE REFUSAL SURVIVES** where neither exists: no covering read and
    no history. It names the segment and metering's own reason. ⚠ Except in the
    one-time PREVIEW (`waiting_ok`), where the stretch is left WAITING for a
    reading instead: refusing there would stop step 1 before the clerk can type
    the reading on step 2 that the ruling says is used first (`DEF-BIL-8300`'s
    shape). The draft is never `waiting_ok` and still refuses.

    `gathered` is edited in place: `[start, end, versions, data, period_days]`.
    """
    never_read = {
        tariff.service
        for _s, _e, _v, data, _d in gathered
        for tariff in data.tariffs
        if measure_consumption_stage.prices_no_consumption(tariff)
        or measure_consumption_stage.bills_base_only(tariff)
    }
    not_in_service = {
        str(code)
        for _s, _e, _v, data, _d in gathered
        for code in (getattr(data, "unconnected_services", ()) or ())
    }

    def short(reading: Any) -> bool:
        return (
            reading.consumption is None
            and reading.service_code not in never_read
            and reading.service_code not in not_in_service
            and reading.absent_reason in NEVER_READ_REASONS
        )

    def key_of(reading: Any) -> tuple[str, Any]:
        return (reading.service_code, getattr(reading, "asset_id", None))

    keys: list[tuple[str, Any]] = []
    for _s, _e, _v, data, _d in gathered:
        for reading in data.readings:
            if short(reading) and key_of(reading) not in keys:
                keys.append(key_of(reading))
    if not keys:
        return ()

    made: list[SegmentEstimate] = []

    def put(index: int, key: tuple[str, Any], new: Any) -> None:
        start, end, versions, data, days = gathered[index]
        readings = tuple(new if key_of(r) == key else r for r in data.readings)
        gathered[index] = [start, end, versions, replace(data, readings=readings), days]

    def reading_at(index: int, key: tuple[str, Any]) -> Any:
        return next((r for r in gathered[index][3].readings if key_of(r) == key), None)

    for key in keys:
        pending: list[int] = []
        unmeasured: list[int] = []
        for index in range(len(gathered)):
            reading = reading_at(index, key)
            if reading is None:
                continue
            if short(reading):
                pending.append(index)
                continue
            measured_from = getattr(reading, "measured_from", None)
            if (
                pending
                and reading.consumption is not None
                and not reading.estimated
                and measured_from is not None
                and measured_from < gathered[pending[0]][0]
            ):
                # 1 · this read measured the pending stretch — share it by days.
                covered = pending + [index]
                total_days = (gathered[index][1] - measured_from).days
                amount = reading.consumption.amount
                unit = reading.consumption.unit  # rule 3 — the read's own unit
                for j in covered:
                    seg_start, seg_end = gathered[j][0], gathered[j][1]
                    seg_days = (seg_end - seg_start).days + 1
                    share = _day_weighted_quantity(amount, days=seg_days, cycle_days=total_days)
                    before = reading_at(j, key)
                    put(
                        j,
                        key,
                        replace(
                            before,
                            consumption=rating_seam.Quantity(amount=share, unit=unit),
                            estimated=True,
                            absent_reason=None,
                            # The register pair measured the WHOLE stretch; on a
                            # share it would print a pair that does not foot.
                            prior_read=None,
                            current_read=None,
                        ),
                    )
                    made.append(
                        SegmentEstimate(
                            period_start=seg_start,
                            period_end=seg_end,
                            service_code=key[0],
                            quantity=share,
                            unit=unit,
                            days=seg_days,
                            cycle_days=total_days,
                            source=ESTIMATE_DAY_WEIGHTED,
                            asset_id=key[1],
                        )
                    )
                pending = []
                continue
            unmeasured.extend(pending)
            pending = []
        unmeasured.extend(pending)

        # 2 · what nothing measured — the meter's own estimate, or 3 · refuse.
        for index in unmeasured:
            seg_start, seg_end = gathered[index][0], gathered[index][1]
            before = reading_at(index, key)
            quantity, unit, reason = _metering_estimate(
                scope.unit_id,
                service_code=key[0],
                period_start=seg_start,
                period_end=seg_end,
                asset_id=key[1],
            )
            if quantity is None:
                if waiting_ok:
                    continue  # the preview waits for step 2's reading
                data = gathered[index][3]
                raise gather.GatherProblem(
                    BACKBILL_NO_ESTIMATE,
                    f"account {data.account_no}: {key[0]} has no read in "
                    f"{seg_start.isoformat()}..{seg_end.isoformat()}, no later read "
                    f"measured it, and metering could not estimate it ({reason}). "
                    "BR-BIL-018 as ruled 2026-09-30 prices a stretch nobody read on the "
                    "meter's own estimate; with no history there is nothing to estimate "
                    "from. Read this meter and re-run.",
                    service_code=key[0],
                )
            put(
                index,
                key,
                replace(
                    before,
                    consumption=rating_seam.Quantity(amount=quantity, unit=unit),
                    estimated=True,
                    absent_reason=None,
                ),
            )
            made.append(
                SegmentEstimate(
                    period_start=seg_start,
                    period_end=seg_end,
                    service_code=key[0],
                    quantity=quantity,
                    unit=unit,
                    days=(seg_end - seg_start).days + 1,
                    cycle_days=(seg_end - seg_start).days + 1,
                    source=ESTIMATE_METERING,
                    asset_id=key[1],
                    unmeasured=True,
                )
            )
    return tuple(made)


def prepare_back_bill(
    *,
    account_id: Any,
    sub_periods: Any,
    reason_code: str,
    theft: bool = False,
    scope_services: tuple[str, ...] | None = None,
    keyed_reads: Any = None,
    waiting_ok: bool = False,
) -> PreparedBackBill:
    """Phase 1: cut the window, gather every group at ITS date. Writes nothing.

    `keyed_reads` — `DEF-BIL-8324` (PO 2026-09-30): the readings a clerk typed
    on step 2 of the one-time page, for the END of the catch-up. They overlay
    the LAST segment only (metering's provisional overlay; a committed read in
    it always wins), and `_fill_never_read_stretches` then uses them FIRST —
    shared by days across the stretch they measured — before any estimate.
    Only the preview passes them; a draft is priced from saved readings.

    `reason_code` is REQUIRED (BR-BIL-018 "reason-coded"). It is not yet
    validated against reference data, so any non-empty code is accepted. ⚠ The
    sentence here used to say the lookup *"has no table in this repository"* —
    false (corrected 2026-09-30, build plan B13): `tenancy.models.ReasonCode` is
    that table. The check against its ACTIVE rows is build-plan task A2.

    `theft` exempts the window from the cap (OQ-071 CLOSED) — and only from the
    cap. A theft case is still approval-gated and still reason-coded.
    """
    if not (reason_code or "").strip():
        raise gather.GatherProblem(
            BACKBILL_NO_REASON_CODE,
            "a back-bill must carry a reason code (BR-BIL-018). Charging a customer for "
            "a period they were never billed for is a decision someone made for a "
            "reason, and the bill is the only place that reason survives.",
        )
    windows = _checked_sub_periods(sub_periods)
    period_start = min(start for start, _ in windows)
    period_end = max(end for _, end in windows)

    cap_months = settings_seam.back_bill_cap_months()
    exempt = theft and settings_seam.back_bill_theft_exempt()
    span = months_spanned(period_start, period_end)
    if span > cap_months and not exempt:
        raise gather.GatherProblem(
            BACKBILL_OVER_CAP,
            f"this back-bill spans {span} months ({period_start} → {period_end}) and the "
            f"tenant's back-bill window is capped at {cap_months} months "
            f"({settings_seam.KEY_BACK_BILL_CAP_MONTHS}, Settings → Finance controls). "
            "BR-BIL-018: only a theft-coded case is exempt.",
        )

    scope = single.billable_account(account_id)
    tariffs = _plan_tariffs(scope.unit_id)
    # OQ-191: asked ONCE, before any gathering, so a tenant whose setting cannot
    # be read finds out before six months of reads have been walked.
    source = segment_estimate_source()
    segments = groups_split_by_days(windows, tariffs)

    groups: list[BackBillGroup] = []
    estimates: list[SegmentEstimate] = []
    everything: list[list[Any]] = []
    # `DEF-BIL-8561` — the stated sub-period of each row of `everything`, kept
    # BESIDE it rather than in it: `_fill_never_read_stretches` edits those rows
    # in place as five-element lists.
    owners: list[tuple[date, date]] = []
    for sub_start, sub_end in windows:
        period_days = (sub_end - sub_start).days + 1
        gathered: list[tuple[date, date, dict[str, str], AccountBillingData]] = []
        for start, end, owner_start, owner_end, group in segments:
            if (owner_start, owner_end) != (sub_start, sub_end):
                continue
            # DEF-BIL-9012 (PO 2026-10-01, option A) — a segment cut only for
            # ANOTHER service's price change does not hold this one: `group`
            # names the services this segment gathers, `None` = every service.
            group_scope = _narrowed_scope(scope_services, group)
            if group_scope == ():
                continue
            versions = _assert_one_version_per_group(
                [row for row in tariffs if group is None or row.get("service_code") in group],
                start,
                end,
            )
            data = single.gather_single(
                scope,
                keyed_reads=keyed_reads if end == period_end else None,
                period_start=start,
                period_end=end,
                # THE LEVER (BR-RAT-007). The group's OWN first day, so `gather`
                # resolves the version in force THEN. Passing the run date here
                # — or the window's end — is the silent-overcharge defect, and
                # tc1/tc6 fail on exactly that mutation.
                service_date=start,
                # THE DAY WEIGHT (B4.3, OQ-155 "split by days"). The denominator
                # is the STATED sub-period, so a segment of a repriced period
                # arrives as service_days/cycle_days and the engine derives the
                # factor. An unsplit sub-period passes its own length and
                # weighs 1.
                cycle_days=period_days,
                scope_services=group_scope,
            )
            gathered.append((start, end, versions, data))

        if len(gathered) > 1:
            # OQ-191 (PO 2026-08-12). ONLY a sub-period the tariff CUT can have a
            # segment with no read of its own, so an unsplit period — every group
            # of an ordinary catch-up — walks past this untouched and keeps
            # BR-BIL-015's refusal for a month nobody read (tc10).
            gathered, made = _estimate_read_less_segments(
                scope,
                gathered,
                sub_start=sub_start,
                sub_end=sub_end,
                source=source,
                scope_services=scope_services,
            )
            estimates.extend(made)

        everything.extend([start, end, versions, data, period_days] for start, end, versions, data in gathered)
        owners.extend((sub_start, sub_end) for _ in gathered)

    # `DEF-BIL-8324` — the stretches of the WHOLE catch-up nobody read.
    estimates.extend(_fill_never_read_stretches(scope, everything, waiting_ok=waiting_ok))
    estimates.sort(key=lambda row: (row.period_start, row.service_code))

    for (start, end, versions, data, period_days), (owner_start, owner_end) in zip(everything, owners):
        groups.append(
            BackBillGroup(
                period_start=start,
                period_end=end,
                service_date=start,
                cycle_days=period_days,
                tariff_version_ids=versions,
                data=data,
                owner_start=owner_start,
                owner_end=owner_end,
            )
        )

    return PreparedBackBill(
        account_id=scope.account_id,
        account_no=scope.account_no,
        period_start=period_start,
        period_end=period_end,
        reason_code=reason_code,
        theft=theft,
        cap_months=cap_months,
        approval_mode=settings_seam.correction_approval_mode(),
        groups=tuple(groups),
        estimate_source=source,
        estimates=tuple(estimates),
    )


def _measured(group: BackBillGroup) -> MeasuredUsage:
    """Stages 1 and 2 for one group, with the group's window in the refusal.

    An unresolved missing read refuses here for the same reason it refuses in
    `runs.calculate_account` — BR-BIL-015 makes "bill without this service" a
    human's choice — but the message names the GROUP. On a six-month bill,
    "no usable read for water" sends a clerk through six months of history;
    "no usable read for water in 2026-03-01..2026-03-31" does not.

    WHAT THIS REFUSAL IS STILL FOR, since OQ-191 closed. It is a whole stated
    sub-period nobody read — the missing March of a six-month catch-up — and it
    stays a human's decision, unchanged. What it is NO LONGER for is a SEGMENT
    of a period the tariff cut: `prepare_back_bill` has already day-weighted
    those (or asked metering) and marked them estimated, so by the time this
    runs they carry a quantity. A cut segment reaches this line only when
    neither estimate could be produced, and `_estimate_read_less_segments`
    refuses first — at prepare, before a number is spent.
    """
    subscription = resolve_subscription(group.data)
    usage = measure_consumption(subscription, group.data)
    # ⚠ **`DEF-BIL-5326` (2026-09-15) — THIS LINE READ
    # `!= ABSENT_BASE_ONLY` AND EXEMPTED ONE REASON WHERE THE INTERIM PATH
    # EXEMPTS FOUR.** `runs.calculate_account` and `midperiod._measured_segment`
    # both carried the full list; this pass — which prices a BACK-BILL and a
    # PENALTY bill — carried a copy that had fallen three reasons behind, and
    # nothing could see it because every suite that exercises this path uses
    # METERED services only. Measured before the fix: account `E11-0001` over
    # 2026-08-16 → 2026-09-15 priced 24 lines totalling `$573.33` as an interim
    # bill including *"sewer usage — 60.00% of water volume"* `$28.35`, and
    # refused as a back-bill naming sewer — a service that prices a percentage
    # of water (BR-RAT-015) and has no reading of its own to be missing.
    # The list now has ONE name and one home, so a fifth reason cannot reach the
    # interim path and miss this one.
    unresolved = tuple(
        service
        for service in usage.unmeasured
        if service.absent_reason not in measure_consumption_stage.EXEMPT_FROM_MISSING_READ
    )
    if unresolved:
        names = ", ".join(service.service_code for service in unresolved)
        raise gather.GatherProblem(
            runs.CALC_UNRESOLVED_READ,
            f"account {group.data.account_no}: {names} has no usable read in "
            f"{group.label()} and no decision. BR-BIL-015 makes that a choice — "
            "estimate it, hold the period, or bill without the service — and billing "
            "the other groups would be taking the third one silently.",
            service_code=unresolved[0].service_code,
        )
    return usage


def _weight_buckets(usages: list[MeasuredUsage]) -> list[tuple[Any, list[MeasuredUsage]]]:
    """The groups collected by proration FACTOR, in first-appearance order.

    The factor is the number, not the day counts it came from. WE-10's six
    months are 31, 28, 31, 30, 31 and 30 days long and every one of them is a
    whole period: 31/31 and 28/28 are the same factor (1) and price
    identically, so they collect into ONE bucket and the bill is priced in one
    call exactly as it always was. Comparing the day-count PAIRS instead of the
    factor would put February in a bucket of its own for being February — which
    is what the first cut of this code did, and what tc1/tc2 caught.

    Factors DIFFER for two reasons, and since OQ-155 closed both are priced
    rather than refused: a reprice inside a stated sub-period (`groups_split_by_
    days` cuts 90/181 and 91/181 out of a Jan–Jun window) and an account that
    opened or closed inside the window (a tenancy beginning mid-March inside a
    January–June catch-up owns 17/31 of March and 30/30 of April).
    """
    buckets: list[tuple[Any, list[MeasuredUsage]]] = []
    seen: dict[Fraction, int] = {}
    for usage in usages:
        period = usage.subscription.period
        key = Fraction(period.service_days, period.cycle_days)
        if key not in seen:
            seen[key] = len(buckets)
            buckets.append((period, []))
        buckets[seen[key]][1].append(usage)
    return buckets


def _priced_pass(
    period: Any,
    usages: list[MeasuredUsage],
    first: Any,
    *,
    taxes: Any,
    fees: Any,
    discounts: Any = (),
) -> Any:
    """One `price_bill` call for every group that shares `period`'s factor.

    `discounts` is BILL-LEVEL and travels the same way `taxes` and `fees` do:
    empty on every carrying pass, real on the final one, so R6 runs ONCE over
    the whole bill. DEF-537 — this call passed no discounts at all, so a
    back-billed period for an enrolled account re-priced at full tariff while
    the customer's ordinary bills carried their reduction.
    """
    services: list[tuple[Any, Any]] = []
    base_only: list[Any] = []
    for usage in usages:
        services.extend((service.tariff, service.consumption) for service in usage.measured)
        base_only.extend(service.tariff for service in usage.unmeasured)
    return rating_seam.price_bill(
        services=tuple(services),
        base_only_services=tuple(base_only),
        period=period,
        account=rating_seam.AccountContext(currency=first.currency, tax_exempt=first.tax_exempt),
        taxes=taxes,
        fees=fees,
        discounts=discounts,
    )


def price_day_weighted(usages: list[MeasuredUsage], *, extra_fees: tuple[Any, ...] = ()) -> Any:
    """Price every group on its own day weight, and TAX THE BILL EXACTLY ONCE.

    ⚠ **ONE CALL PER GROUP, NOT ONE PER PRORATION FACTOR — `DEF-BIL-8560`
    (2026-09-30, J74).** The text below says groups that share a factor *"ride
    in one call"*. They did, and on a bill with sewer that was a money defect:
    the engine takes a percent-of-service line's BASIS as the whole call's water
    (`rating.engine`'s `basis_volumes`), so August and September — both factor
    1 — were each billed sewer on BOTH months' water. J74 case 6 charged
    **$59.39 twice** where the two months together come to $59.39 (Aug $30.18,
    Sep $29.21), and case 7 **$98.80 twice** (Aug $51.80 + Sep $47.00). Each
    group is now its own call, so every month's sewer is a share of THAT
    month's water. **The tax still runs ONCE**, on the final call, over every
    carried line — so WE-10's 26.36 (❄️ GT-26) cannot move by the cent a
    tax-per-slice would, and the carried lines are the same finalized lines a
    shared call produced for every service that is not priced off another.

    `price_bill` prices every (tariff, consumption) pair against ONE
    `BillingPeriod`, because B4.3's proration factor and BR-RAT-002's tier
    scaling are one number for one bill. Groups that share a factor therefore
    ride in one call, and a catch-up of whole billing periods — every group at
    factor 1 — is one call and one tax pass, byte for byte what it was before
    OQ-155 closed.

    OQ-155's ENGINEERING HALF was that unequal segments cannot share a call: a
    Feb 10 reprice gives 10/28 and 18/28, and the two need different factors.
    That half was reported to the PO alongside the finance question and it is
    still true of the seam — `rating_seam.price_bill` takes one period, and
    giving it one per priced entry is a change inside `apps/rating`, which is
    🔒 human-owned money math. So the call is made ONCE PER FACTOR:

      * every bucket but the first is priced with NO taxes and NO fees, which
        yields its lines already finalized once (BR-RAT-003);
      * those lines are then handed to the FIRST bucket's call on the seam's
        bill-level line channel, alongside the bill's real fees, and that call
        carries the bill's taxes.

    So the tax pass runs once, over Σ(rounded taxable lines) for the WHOLE bill,
    which is B4.2 exactly — and NOT once per bucket. That difference is the cent
    OQ-155 warned about and it is asserted, not asserted-about: on tc6c's
    90/181 + 91/181 bill, one pass over 75.59 at 8.25% is **6.24** where taxing
    each segment (36.76 → 3.03, 38.83 → 3.20) and summing is **6.23**. It is the
    same cent WE-10's frozen 26.36 turns on.

    NOTHING IS ROUNDED TWICE. A carried line is already at 2dp and the final
    call finalizes it again with the same half-up law, which returns it
    unchanged (`core.money.finalize` is idempotent at 2dp); the bill-level
    channel carries `kind` and `taxable` faithfully, so a carried usage line
    enters the tax base as a usage line and never as a fee — `fee_total` counts
    kind `fee` only. tc6c is the guard on all of that: if that channel ever
    stopped carrying the kind, the carried lines would drop out of the tax base
    and tc6c would go RED on the tax total rather than shipping a quiet
    undercharge.

    LINE ORDER follows the buckets, not the calendar, when a bill mixes factors:
    the first bucket's lines, then the remaining buckets in the order their
    first group appeared. Every group's own window, day weight and version id is
    in `bill_payload` in calendar order regardless (`_group_snapshot`), which is
    where a reprint reads them from — `invoice_lines` carries no per-group
    period at all today (trailer exception 2).
    """
    return _price_by_group(usages, extra_fees=extra_fees)[0]


def _line_key(line: Any) -> tuple[Any, ...]:
    """What a line IS apart from its meter — the carried channel drops `asset_id`."""
    return (
        getattr(line, "kind", None),
        getattr(line, "description", None),
        getattr(line, "amount", None),
        getattr(line, "taxable", None),
        getattr(line, "quantity", None),
        getattr(line, "unit", None),
        getattr(line, "unit_price", None),
        getattr(line, "service", None),
        getattr(line, "tariff_version_id", None),
    )


def _price_by_group(
    usages: list[MeasuredUsage], *, extra_fees: tuple[Any, ...] = ()
) -> tuple[Any, tuple[int | None, ...]]:
    """`DEF-BIL-8560`/`8561` — one call per group, taxed once, each line traced.

    Every group but the first is priced WITHOUT taxes, fees or discounts and its
    finalized lines ride the bill-level channel into the first group's call,
    which carries the bill's taxes, fees and discounts (the shape the docstring
    above argues for). The final call prints its OWN services' lines first, then
    the carried lines in the order they were carried, then the bill-level lines
    (fees, discounts) and the tax — measured on J74 case 7's 50 stored lines.

    So the second value is, for every line of the answer, the index of the
    GROUP it was priced for, or None for a bill-level line (a fee, a discount,
    a tax). It is found by locating the carried run inside the answer — every
    carried line matched on everything but its meter — and it is REFUSED rather
    than guessed if the run is not there: a line attributed to the wrong month
    on an immutable bill is worse than a line attributed to none.

    The carried channel drops `asset_id` (the J74 walk found 12 of 16 water
    lines on case 6 naming no meter), so each carried line gets its meter back
    from the group's own call — the ONLY field restored; every amount is the
    engine's, copied.
    """
    first = usages[0].subscription
    carried_by_group: list[tuple[Any, ...]] = [()]
    for usage in usages[1:]:
        carried_by_group.append(
            tuple(
                _priced_pass(usage.subscription.period, [usage], first, taxes=(), fees=()).lines
            )
        )
    carried = [(index, line) for index, lines in enumerate(carried_by_group) for line in lines]
    priced = _priced_pass(
        usages[0].subscription.period,
        [usages[0]],
        first,
        taxes=first.taxes,
        # `extra_fees` rides the FINAL call only, exactly as the carried lines
        # and the bill's own fees do, so the tax pass and the discount pass each
        # run ONCE over the whole bill (B4.2 / BR-RAT-071). A charge-code line
        # arrives `taxable=False` from `fee_bill.charge_code_line`, so it does
        # not enter the tax base — see `OQ-812`.
        fees=tuple(line for _, line in carried) + tuple(first.fees) + tuple(extra_fees),
        # DEF-537 — ON THE FINAL CALL ONLY, for the same reason the taxes ride
        # here: R6 is bill-level (BR-RAT-071); the carried lines reach this call
        # on the bill-level channel with their `kind` intact, which puts them
        # inside `apply_discounts`' DISCOUNTABLE_KINDS and the tax base.
        discounts=tuple(getattr(first, "discounts", ()) or ()),
    )
    lines = tuple(getattr(priced, "lines", ()) or ())
    owners: list[int | None] = [None] * len(lines)
    wanted = [_line_key(line) for _, line in carried]
    # Searched from the END: the carried run sits between the first group's
    # own lines and the bill-level lines, and a first month identical to a
    # later one (same usage, same price) would match at the front too.
    start = None if wanted else len(lines)
    for at in range(len(lines) - len(wanted), -1, -1) if wanted else ():
        if [_line_key(line) for line in lines[at : at + len(wanted)]] == wanted:
            start = at
            break
    if start is None:
        raise BillingRuleError(
            "the catch-up's later months did not come back from the taxed pricing call "
            "in the order they were carried, so no line could be dated to its month. "
            "Refused rather than guessed: a line put in the wrong month on an issued "
            "bill cannot be corrected by an UPDATE (DEF-BIL-8561)."
        )
    restored = list(lines)
    for offset in range(start):
        if getattr(lines[offset], "kind", None) != "tax":
            owners[offset] = 0
    for offset, (index, source) in enumerate(carried):
        at = start + offset
        owners[at] = index
        meter = getattr(source, "asset_id", None)
        if meter and not getattr(lines[at], "asset_id", None):
            restored[at] = replace(lines[at], asset_id=meter)
    if restored != list(lines):
        priced = replace(priced, lines=tuple(restored))
    return priced, tuple(owners)


def calculate_back_bill(
    prepared: PreparedBackBill,
    *,
    bill_run: models.BillRun,
    service_date: date | None = None,
    bill_type: str = "backbill",
    extra_snapshot: dict | None = None,
    extra_fees: tuple[Any, ...] = (),
) -> models.Invoice:
    """Phase 2: price every group on its own version, tax ONCE, draft ONE bill.

    `service_date` defaults to the window's LAST day and is what
    `invoices.service_date` records. That column's usual meaning ("join the
    version where service_date ∈ [effective_from, effective_to)") does not
    survive a bill that spans versions BY DESIGN, which is why every group's
    version ids are stamped into `bill_payload`. Since DEF-276 (2026-08-19) the
    LINES carry their own version too, so `invoices.service_date` is no longer
    the only thing a reprint could join on — it was never able to be, which is
    what made this bill type the sharpest case for that defect.

    `bill_type` is `backbill` or `penalty` and nothing else. US-BIL-014's
    theft bill IS this pricing pass — BR-BIL-019 says assessed reads are
    *"priced by back-billing"* — and giving it its own pricing path would be
    the second implementation this module exists to avoid. The type changes
    what the document is called, never how it is priced.
    """
    if bill_type not in ("backbill", "penalty"):
        raise BillingRuleError(
            f"a back-bill pass produces a 'backbill' or a 'penalty' document, not "
            f"{bill_type!r}. Every other type in B2 r10 #12 has its own entry point "
            "with its own rules."
        )
    if not prepared.groups:
        raise BillingRuleError(
            "this back-bill has no groups, so there is nothing to price. A prepared "
            "back-bill always carries at least one group; none means the window was "
            "never cut."
        )
    pass_ = price_back_bill(
        prepared, bill_type=bill_type, extra_snapshot=extra_snapshot, extra_fees=extra_fees
    )
    return assemble_document(
        usage=pass_.usage,
        priced=pass_.priced,
        tenant_id=core_tenancy.current_tenant_id(),
        account_id=prepared.account_id,
        bill_run=bill_run,
        period_start=prepared.period_start,
        period_end=prepared.period_end,
        service_date=service_date or prepared.period_end,
        bill_type=bill_type,
        # `DEF-BIL-8561` — each line stored with the month it bills.
        line_windows=pass_.line_windows,
    )


@dataclass(frozen=True)
class PricedBackBill:
    """A back-bill priced and **not written** — the two arguments stage 6 takes.

    Held together for `runs.PricedAccount`'s own stated reason: there is no way
    to obtain one without the other, so no caller can assemble a document from
    a snapshot that does not belong to the figures beside it.
    """

    usage: MeasuredUsage
    priced: Any
    #: PO ruling 2026-09-30 — every group's named warnings, each once (six
    #: monthly groups that each find no electric base say so ONCE). Frozen
    #: into the draft's `bill_payload["warnings"]` beside the group record.
    warnings: tuple[dict, ...] = ()
    #: `DEF-BIL-8561` — for every line of `priced.lines`, the STATED sub-period
    #: (the month) it bills, or None for a bill-level line (a fee, a discount,
    #: a tax), which bills the whole window. Stage 6 writes it onto
    #: `invoice_lines.period_start/period_end`; Review groups by it.
    line_windows: tuple[tuple[date, date] | None, ...] = ()


def price_back_bill(
    prepared: PreparedBackBill,
    *,
    bill_type: str = "backbill",
    extra_snapshot: dict | None = None,
    extra_fees: tuple[Any, ...] = (),
) -> PricedBackBill:
    """Every group priced on its own version, taxed ONCE, and **no write**.

    ⚠ **EXTRACTED SO THAT A SECOND CATCH-UP PRICING PATH CANNOT EXIST**
    (`CR-108` wave 1, the one-time tab's step 3), which is `runs.price_account`'s
    reason word for word: a clerk approving a six-month catch-up must be shown
    the LINES before anything is drafted, and this module's whole argument is
    that a back-bill and a theft bill are priced by one pass. A preview that
    re-priced the groups would be exactly the second implementation the module
    docstring forbids — and it would be invisible, because a back-bill foots
    either way (18 kgal as one period puts 13 kgal in the top tier where six
    monthly groups put 6: **$25.00** of a customer's money).

    So `calculate_back_bill` is now this function plus stage 6, and the One-time
    tab's preview is this function and nothing else. **DO NOT INLINE IT BACK.**

    The snapshot is built here rather than at assembly because it is part of
    what was priced: the group labels and their tariff versions are the record
    of HOW these figures were reached (US-BIL-013 §5).
    """
    usages = [_measured(group) for group in prepared.groups]
    first = usages[0].subscription
    # ⚠ **`extra_fees` IS A BILL-LEVEL CHANNEL FOR ALREADY-BUILT LINES AND NOT A
    # WAY TO PUT MONEY ON A BILL (`DEF-BIL-5317`, 2026-09-15).** A `RatedLine`
    # is only ever produced by `fee_bill.charge_code_line` from the TENANT's own
    # charge-code row (BR-BIL-007), so the figure is theirs and no caller of
    # this function has anywhere to type one. It exists because BR-BIL-019 says
    # a penalty bill is made of exactly two ingredients — assessed reads that
    # BACK-BILLING prices, which is every line above, and charge-code lines,
    # which is this — and the second had no way onto the document at all.
    priced, owners = _price_by_group(usages, extra_fees=extra_fees)
    # DEF-BIL-8733 — PO 2026-09-30 (*"per service"*): a counted service (trash,
    # fire) prints as ONE line per MONTH, as every other kind prints it one line
    # (DEF-BIL-8151's join, which `runs.price_account` applies and this pass,
    # pricing through `rating_seam.price_bill`, never reached). Layout only.
    priced, owners = counted_service_line.one_line_per_counted_service_per_window(
        priced,
        owners,
        counted_service_line.counted_services(
            service.tariff for usage in usages for service in usage.services
        ),
    )
    line_windows = tuple(
        None if owner is None else prepared.groups[owner].stated_window() for owner in owners
    )

    snapshot = _group_snapshot(prepared, usages, bill_type=bill_type)
    snapshot.update(extra_snapshot or {})
    # PO ruling 2026-09-30 — the `$0.00`-base (and any other) warnings of
    # every group. `_group_snapshot` REPLACES the gathered snapshot rather than
    # extending it, so `runs.price_account`'s route onto the payload does not
    # reach a back-bill; this is that route for this pass. No warnings, no key.
    warnings = bill_warnings.merged(
        *(getattr(group.data, "warnings", ()) or () for group in prepared.groups)
    )
    if warnings:
        snapshot["warnings"] = [dict(row) for row in warnings]
    combined = MeasuredUsage(
        subscription=replace(first, snapshot=snapshot),
        services=tuple(service for usage in usages for service in usage.services),
    )
    return PricedBackBill(usage=combined, priced=priced, warnings=warnings, line_windows=line_windows)


def _group_snapshot(
    prepared: PreparedBackBill, usages: list[MeasuredUsage], *, bill_type: str = "backbill"
) -> dict:
    """The period-labeled group record, frozen into the bill's locked payload.

    US-BIL-013 §5 puts the group label and the tariff version on
    `invoice_lines` (`period_start`/`period_end`/`tariff_version_id` per group).
    **Half of that landed on 2026-08-19 (DEF-276): the version id is now written
    per line and a back bill's lines name the two versions that priced them.**
    The PERIOD half has not — stage 6 still writes ONE period for every line —
    so the group WINDOW still has to exist somewhere immutable, because
    BR-BIL-030 locks `bill_payload` at issue and a reprint in 2033 must be able
    to show which prices applied to which month. This is that record, and it is
    written at draft time with the rest of the snapshot.

    IT ALSO CARRIES THE ESTIMATES (OQ-191, PO 2026-08-12): which estimator the
    tenant chose, and one row per derived (segment, service) with its quantity,
    unit, day weight and — where option C fell back — why. A customer disputing
    a back-bill in 2033 asks "was that a reading?", and the answer has to be in
    the document rather than in a setting that has since been changed.
    """
    return {
        **dict(usages[0].subscription.snapshot),
        "bill_type": bill_type,
        "back_bill": {
            "reason_code": prepared.reason_code,
            "theft_case": prepared.theft,
            "cap_months": prepared.cap_months,
            # OQ-191 — what the tenant chose, and what was actually derived.
            "estimate_source": prepared.estimate_source,
            "estimates": [estimate.as_dict() for estimate in prepared.estimates],
            "window": {
                "start": prepared.period_start.isoformat(),
                "end": prepared.period_end.isoformat(),
                "months_spanned": months_spanned(prepared.period_start, prepared.period_end),
            },
            "groups": [
                {
                    "period_start": group.period_start.isoformat(),
                    "period_end": group.period_end.isoformat(),
                    "service_date": group.service_date.isoformat(),
                    # The DAY WEIGHT this group was priced on (OQ-155). Frozen
                    # into the payload with everything else because a reprint in
                    # 2033 has to be able to show not only WHICH prices applied
                    # to which days but what share of the period those days were.
                    "days": group.days,
                    "cycle_days": group.cycle_days,
                    "tariff_version_ids": dict(group.tariff_version_ids),
                    "services": [
                        {
                            "code": service.service_code,
                            "measured": service.consumption is not None,
                            # OQ-191 — MEASURED and ESTIMATED are different
                            # facts and a bill that showed only the first would
                            # present a derived quantity as a meter reading.
                            "estimated": bool(service.estimated),
                            "quantity": (
                                str(service.consumption.amount)
                                if service.consumption is not None
                                else None
                            ),
                            "unit": (
                                service.consumption.unit
                                if service.consumption is not None
                                else None
                            ),
                        }
                        for service in usage.services
                    ],
                }
                for group, usage in zip(prepared.groups, usages)
            ],
        },
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-013@f0a3c21 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane — US-BIL-011..014)
# amended:   2026-08-12 by story-coder (OQ-191 lane) — a CUT segment with no read of its
#            own is ESTIMATED rather than refused (PO ruling of the same day, verbatim in
#            exception (9)): day-weighted by default, metering's estimate as a tenant
#            option, refusal kept as the last resort and moved to prepare. The estimate is
#            MARKED and the mark reaches the customer's document. One new tenant setting
#            (`back_bill_segment_estimate_source`, S71, seeded `day_weighted`).
#            NO MIGRATION: `merge` supplies a new Param's default at READ time.
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S30's One-time tab is unbuilt) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_013_backbill.py 14 passed · pytest tests 2010 passed/118 skipped/1 xfailed · golden-verify 33 PASS/0 FAIL
# amended-gates: see the OQ-191 lane report — tests/test_us_bil_013_backbill.py 15 passed +
#            tests/test_po_20260812_backbill_segment_estimate.py 15 passed; PROVED RED
#            FIRST, twice: (a) all 15 new/rewritten cases against the refusing build, the
#            customer-document one failing on the superseded refusal itself
#            (`GatherProblem: account A-13103: water has no usable read in
#            2026-02-01..2026-02-14 and no decision`); (b) the flag mutated to
#            `estimated=False`, which leaves every money assertion green and turns the
#            rendered bill from "estimated read" to "read" — 3 failed, 27 passed.
# exceptions: (1) THE FROZEN WE-10 FIGURES ARE ONLY PARTIALLY REPRODUCIBLE
#         TODAY, and the reason is not in this file: WE-10's 45.10/47.84 months
#         include a SEWER line priced as 40% of the water usage-$, and the
#         rating engine does not implement percent-of-service pricing (its own
#         docstring lists it as unimplemented, with no frozen figure to bind
#         to). What IS reproduced exactly, and asserted per group, are WE-10's
#         water figures on their own versions — v3 usage **26.50** + base
#         **8.00**, v4 usage **28.10** + base **8.50** — which is the half of
#         WE-10 that proves the rule this story exists for. The sewer half is
#         REPORTED, not approximated: a fabricated sewer tariff would make a
#         green test that proves nothing about a frozen number.
#         (2) ⚠ HALF CLOSED 2026-08-19 — DEF-276. This read: *"`invoice_lines
#         .period_start/period_end` carry the WHOLE window on every line and
#         `invoice_lines.tariff_version_id` is never written — stage 6 writes one
#         period for all lines and `rating_seam.RatedLine` carries no version.
#         REPORTED to the lane that owns `stages/assemble_document.py` +
#         `rating_seam.py`"*. THAT LANE LANDED IT: `RatedLine` carries
#         `tariff_version_id`, the engine stamps it in `pricing/stages/
#         price_usage.py`, and stage 6 writes it — so **US-BIL-013 TC-6's version
#         stamp is now checkable and is checked**, on the case that needed it
#         most (six months, two water versions, one bill;
#         `tests/test_us_bil_013_backbill.py` tc2, whose `== {None}` assertion
#         was INVERTED rather than deleted). STILL OPEN: the PERIOD half —
#         every line still carries the whole window rather than its group's
#         month, so the group record (window, service date, quantity + unit) is
#         still frozen into `bill_payload`, which BR-BIL-030 locks at issue.
#         (3) THE SUB-PERIODS ARE THE CALLER'S and are never defaulted — a
#         single whole-window group would reset tiers once instead of per period
#         (BR-RAT-002) and overcharge on any inclining block. `cycles` carries
#         no recurrence rule, so nothing in this database can derive them.
#         (4) PARTIAL GROUPS ARE SPLIT BY DAYS — OQ-155 CLOSED, Product Owner
#         2026-08-12, verbatim *"Split by days"* (12-governance/02-decision-log.md).
#         Until that date both forms — a version boundary landing INSIDE a
#         stated sub-period, and an account opening or closing inside the
#         window — REFUSED as `NotImplementedError`, because the finance rule
#         for a split billing period was unruled (B4.3 read literally prorates
#         the base across the slices; WE-18, the only worked mid-cycle rate
#         boundary, charges it once and is silent on tier ladders). That refusal
#         was right while the question stood and is gone now the PO has ruled:
#         `groups_split_by_days` cuts the sub-period at each reprice and each
#         segment carries `service_days`/`cycle_days` into the engine, which
#         derives B4.3's factor — no proration arithmetic exists in this module.
#         WORKED (the PO's own example, WE-10's water tariff repricing on Feb
#         15, 6 kgal, 3 in each half): v3 base 8.00 × 14/28 = **4.00**, first
#         block 5 → 2.5 kgal so **10.00** + **3.25**; v4 base **4.25**, 2.5 ×
#         4.25 = 10.625 → **10.63** and 0.5 × 6.85 = 3.425 → **3.43**; group
#         **35.56**. That is 35.56 and not the 35.55 in OQ-155's option (a),
#         because BR-RAT-003 rounds PER LINE and the OQ's illustration summed a
#         half's tier amounts first — the ruled rule is implemented and the cent
#         is the signed rounding law, REPORTED not adjusted.
#         The ENGINEERING half of OQ-155 is unchanged and still true:
#         `price_bill` takes ONE period per call, so segments of unequal length
#         need a call each. `price_day_weighted` therefore calls once per
#         proration FACTOR and hands every other call's finalized lines to the
#         one that carries the taxes, on the seam's bill-level line channel — so
#         the tax pass still runs ONCE over Σ(rounded taxable lines) and WE-10's
#         26.36 does not move. tc6c pins that at 6.24 (one pass) against 6.23
#         (per segment) and is the guard on the channel: if it ever stopped
#         carrying a line's KIND, the carried lines would leave the tax base and
#         tc6c goes RED rather than a bill quietly undercharging. A per-entry
#         period on the rating seam (🔒 human-owned) would remove the need for
#         the multi-call shape entirely and is REPORTED to that lane.
#         A back-bill of whole billing periods is one call and one tax pass,
#         unchanged.
#         (5) THE APPROVAL GATE IS NOT ENFORCED HERE OR ANYWHERE. BR-BIL-014's
#         machinery (US-BIL-017) does not exist and `issue.py` has no approval
#         check, so nothing stops an approved-by-nobody back-bill being ISSUED.
#         This module reads and records the tenant's approval MODE and states
#         the gap; it does not claim to be the gate. Drafting before approval is
#         correct (TC-3: "draft + impact preview exist first").
#         ⚠ 2026-09-30 (build plan B10): there is NO record anywhere that a
#         DRAFT was approved, so the gate cannot be built without inventing
#         one — asked as OQ-BIL-12781 rather than chosen here.
#         (6) The reason code is required but NOT YET validated against
#         reference data. ⚠ CORRECTED 2026-09-30 (build plan B13): this read
#         *"the r10 #13 lookup has no table"* — `tenancy.models.ReasonCode` is
#         that table; the check against it is build-plan task A2.
#         (7) `months_spanned` counts calendar months TOUCHED, conservatively.
#         No signed document defines the count; the judgment call is recorded in
#         12-governance/02-decision-log.md (2026-08-11) and errs toward refusing.
#         (8) WHAT "SPLIT BY DAYS" DAY-WEIGHTS. The BASE CHARGE and the TIER
#         LADDER are day-weighted BY THE ENGINE, from the service/cycle day
#         counts this module states — B4.3 + BR-RAT-002, OQ-155's option (a),
#         which the PO ruled. Where a segment HAS a read measuring its own days
#         that read is used as-is and is never prorated (B4.3 as amended
#         2026-08-11 — "the reading IS the consumption"); EP-BIL-03 TC-11 is
#         that negative and tc6b/tc6c are its tests.
#         (9) A CUT SEGMENT WITH NO READ OF ITS OWN IS ESTIMATED — OQ-191
#         CLOSED, Product Owner 2026-08-12, verbatim *"B is correct; and if
#         required give option C also as backup ; I will make B default and C as
#         option for user"* (12-governance/02-decision-log.md).
#         ⚠ THIS ENTRY REPLACES A REFUSAL THIS FILE SHIPPED HOURS EARLIER THE
#         SAME DAY, and the refusal is described in the PAST TENSE deliberately:
#         it WAS correct while OQ-191 stood. It read *"split by days"* as
#         prorating MONEY (which it does), noted that the ruling's own example
#         STATED 3 kgal per half rather than deriving them, and refused a
#         read-less segment through BR-BIL-015 naming it — "no usable read for
#         water in 2026-02-01..2026-02-14". What it also did was make
#         back-billing fail in exactly the case it exists for, since a six-month
#         catch-up will almost never have a read on the reprice day. That was
#         REPORTED to the PO, who ruled.
#         DEFAULT (option B): the STATED SUB-PERIOD's own measured usage is
#         day-weighted into every segment of it — the ruling's figure, on
#         WE-10's tariff repricing 15 Feb over a 1–28 Feb period of 6 kgal, is
#         **14/28 × 6 = 3.000000 kgal** each side, and it prices to the SAME
#         **35.56** two real reads produce (tc6d against tc6b). The decision is
#         about the SUB-PERIOD and not one segment: the Feb 28 read exists
#         inside the second segment but MEASURES the whole month, so weighting
#         only the first would bill 9 kgal for a month that used 6.
#         OPTION (C): ask metering under BR-MET-026 —
#         `apps.metering.selectors.back_bill_segment_estimate`, read-only,
#         resolved at call time. ⚠ METERING DOES NOT PUBLISH IT. Its only entry
#         point (`services.estimate_missing_read`) WRITES a meter_reads row, and
#         a prepare pass writes nothing; billing cannot build the read-only half
#         without reading metering's tables (B1) or copying BR-MET-026's basis.
#         So option C falls back to the ruled DEFAULT and RECORDS it —
#         `source=day_weighted`, `fallback_reason=metering_estimate_seam_not_
#         published` — on the preview and on the locked payload. Nothing claims
#         metering produced a figure it did not.
#         ⚠ G20 DOES NOT SEE THAT CONTRACT: the gate harvests only `*seam*.py`
#         files and this declaration lives in `backbill.py`, next to the rule it
#         serves and following this file's own `gather._resolve` idiom. So the
#         seam is NOT auto-checked and the `seam_known_gaps.txt` row it deserves
#         is REPORTED to the lane that owns 10-scripts/ rather than written from
#         here. Named so a reviewer does not assume the gate is covering it.
#         REFUSAL survives as the last resort (`BACKBILL_NO_ESTIMATE`) — a cut
#         sub-period that measured nothing at all — and it moved EARLIER, to
#         prepare, so nothing is drafted and no invoice number is spent. tc6e.
#         THE ESTIMATE IS MARKED, and that flag is the point: it reaches the
#         CUSTOMER's document (`documents._services` prints "estimated read"),
#         the group record and the `back_bill.estimates` list in the payload
#         BR-BIL-030 locks at issue. Proved by mutation — flipping the flag to
#         False leaves every money assertion green and turns the customer's own
#         page from "estimated read" to "read", which is the defect the mark
#         exists to prevent.
#         (10) THE TYPED READER FOR THE NEW SETTING IS IN THIS FILE
#         (`segment_estimate_source`) and NOT in `apps/billing/settings_seam.py`
#         beside `back_bill_cap_months` / `back_bill_theft_exempt`, where the
#         pattern puts it. Reason: that file belongs to another lane this
#         session and was left untouched. It reads through the seam's PUBLIC
#         `finance_controls()` and keeps the same no-local-default discipline —
#         a missing or unrecognised value REFUSES. Moving it is a lift-and-shift
#         with no behaviour change; REPORTED so it happens deliberately.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
