# ── Trace ──────────────────────────────────────────────
# Rule:     BR-RAT-114 (AN ORDINARY BILL SPLITS AT A MID-PERIOD RATE OR PLAN
#           CHANGE — one bill, priced per sub-period, each sub-period at the
#           version in force; consumption evenly by day unless an actual read
#           dates the boundary; one line per sub-period per charge naming its
#           rate and dates)   PO ruling 2026-08-22 · DEF-503 · DEF-504.
# Rules:    BR-RAT-007 (the version in force at the SERVICE date, never
#           today's) · BR-RAT-002 (tier thresholds scale with the prorated
#           period) · B4.2 (ONE tax pass over Σ(rounded taxable lines)) · B4.3
#           (day-weighted proration — the engine derives the factor from day
#           counts stated here) · BR-BIL-015 (a missing read stays a human
#           decision) · BR-CUS-013 (`unit_plan_assignments` is the dated plan
#           history) · CLAUDE.md rule 3 (a quantity travels with its unit)
# Pin:      10 kgal evenly over a period whose change lands at its midpoint at
#           $2.00→$2.20/kgal = $10.00 + $11.00 = **$21.00** — the PO's own
#           figure, asserted by tests/test_br_rat_114_midperiod_split.py tc1,
#           which was written first and proved RED (22.00) before this file.
# Tests:    06-backend/tests/test_br_rat_114_midperiod_split.py
# Impacts:  apps/billing/runs.py (prepare_run attaches; calculate_account
#           delegates) · apps/billing/single.py (the single cycle bill) ·
#           apps/billing/backbill.py (the working precedent this reuses —
#           version_boundaries, _assert_one_version_per_group,
#           SegmentEstimate) · DEF-554 (the carried-line version fix this
#           module's lines ride on)
# ───────────────────────────────────────────────────────
"""BR-RAT-114 — an ORDINARY bill splits at a mid-period rate or plan change.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 rating math. AI-authored 2026-08-22
under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements the signed rule of
2026-08-22, invents nothing; the four places the rule ran out are decided in
12-governance/02-decision-log.md (same date) and restated where they land
below.

WHAT GOES WRONG WITHOUT THIS FILE, stated first because it is why the rule
exists (DEF-503/DEF-504). The ordinary run gathers ONE tariff version at the
run's service date and ONE plan from the unit's current row, and prices the
whole period on them. A rate rising on the 15th therefore over-charges every
day before it — or under-charges every day after, depending on where the
service date falls — by the full difference, on every affected account, on a
bill that foots perfectly. The back-bill path has priced per sub-period since
it shipped (BR-BIL-018); this module brings the ordinary run into agreement
with it, reusing its machinery rather than re-implementing it.

THE SHAPE — the back-bill's, applied to one stated period:

  1. BOUNDARIES are discovered inside the period: every tariff-version
     reprice (bisected through rating's own `pricing_inputs`, via
     `backbill.version_boundaries` — the same read that prices) and every
     plan-assignment change (`unit_plan_assignments.assigned_from`, read
     through rating's `unit_plan_assignments_in`). No boundary → NO SPLIT:
     the account walks exactly the path it always walked, byte for byte,
     which is what keeps every ❄️ B5 frozen figure frozen.
     ⚠ AMENDED 2026-10-12 (`DEF-BIL-10067`, BR-RAT-114 as amended): a
     tariff-version boundary cuts ONLY ITS OWN SERVICE (`split_plan`); a plan
     reassignment or plan-version start still cuts every one; one base row per
     service unless the base price changed (`_single_base_keys`); a demand
     peak is charged once on the last part; each TOU window is split by days.
  2. The period is CUT at each boundary into segments, and each segment is
     GATHERED AT ITS OWN SERVICE DATE (its first day) on ITS OWN PLAN, with
     `cycle_days` held to the caller's — so the engine derives each segment's
     B4.3 factor and BR-RAT-002's tier scaling from the same two numbers a
     partial period has always stated.
  3. Every segment's window is ASSERTED to resolve to ONE version per service
     (`backbill._assert_one_version_per_group`) — the guard that makes a
     missed cut refuse loudly instead of pricing two versions' days on one.
  4. CONSUMPTION apportions to segments EVENLY BY DAY unless an actual read
     dates the boundary — the read wins (the rule, verbatim). A segment with
     its own read keeps it untouched (B4.3 as amended 2026-08-11: the reading
     IS the consumption); when any segment of a measured service lacks one,
     the PERIOD's measured usage is day-weighted across ALL of them (the
     PO-ruled back-bill reasoning: the period-end read MEASURES the whole
     period, so mixing it with a derived half would double-charge), each
     derived quantity MARKED ESTIMATED all the way to the customer's
     document. A service the period never measured is left alone —
     consumption None in every segment — so BR-BIL-015's human decision
     arrives exactly as it always has; the split never mints a new refusal
     for it (decision log 2026-08-22, judgment 3).
  5. Each segment is PRICED at its own versions and the bill is TAXED ONCE:
     one `price_bill` call per segment with no taxes and no fees, the
     finalized lines carried into the first segment's call on the seam's
     bill-level line channel, which alone carries the bill's taxes, fees and
     discounts — Σ(rounded taxable lines), B4.2 exactly, the same shape
     `backbill.price_day_weighted` proved (its 6.24-vs-6.23 cent). Taxes,
     fees and discounts are the PARENT gather's — resolved at the run's
     service date, exactly as today; the split re-prices usage and base ONLY
     (decision log 2026-08-22, judgment 2, worked: the $21.00 pin under
     8.25% carries tax 1.73 in one pass, never 0.83 + 0.91 = 1.74).
  6. The bill carries ONE LINE PER SUB-PERIOD PER CHARGE, each naming its
     rate and its dates — the version id on the line (DEF-276, and DEF-554's
     fix for the carried ones) and the window stamped into the description,
     because a split a customer cannot see is a number they cannot check.
     The full split record (windows, plans, versions, day weights, derived
     quantities) is frozen into `bill_payload`, which BR-BIL-030 locks.

WHAT DOES NOT SPLIT, and why that is the rule rather than a gap:

  * A PLAN-VERSION (filing) change: `plan_versions` carries NO effective date
    BY DESIGN (OQ-324 open — ⚠ CLOSED 2026-10-03 as (B), BR-RAT-1066: a plan
    version now HAS a window and its start IS a cut, see `split_plan`), so it cannot define a dated boundary; a plan
    content change that moves PRICES lands as tariff-version rows, which DO
    split (decision log 2026-08-22, judgment 1).
  * Taxes, fees, discounts: bill-level, one pass, resolved at the run's
    service date — unchanged (judgment 2).
  * Non-cycle documents: back-bill and penalty already split under
    BR-BIL-018/019; final and one-time bills keep their own rules
    (judgment 4).
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.billing import backbill, gather, rating_seam
from apps.billing.contracts import AccountBillingData, MeasuredUsage
from apps.billing.stages import measure_consumption as measure_consumption_stage
from apps.billing.stages.measure_consumption import measure_consumption
from apps.billing.stages.resolve_subscription import resolve_subscription


#: The description stamp: " · <start> to <end>", ISO dates. Chosen so no
#: engine-emitted description can collide with it (no pricing model emits an
#: ISO-dated suffix), which is what lets `_price_split` tell a carried line
#: from a fresh one deterministically — see `price_split_bill`.
def _segment_label(period_start: date, period_end: date) -> str:
    return f" · {period_start.isoformat()} to {period_end.isoformat()}"


@dataclass(frozen=True)
class SplitSegment:
    """One sub-period of a split ordinary bill — BR-RAT-114's unit of pricing.

    `plan_id` is the plan in force on these days (None = the unit's current
    plan, which is every segment of a bill split only by a rate change).
    `tariff_version_ids` is `{service_code: version_id}`, captured from
    rating's own `pricing_inputs` and proved single-valued across the window.
    `estimates` are the quantities DERIVED for this segment (evenly by day)
    rather than read — `backbill.SegmentEstimate` rows, marked so the derived
    half can never be mistaken for a meter reading.
    """

    period_start: date
    period_end: date
    plan_id: str | None
    tariff_version_ids: dict[str, str]
    data: AccountBillingData
    estimates: tuple[backbill.SegmentEstimate, ...] = ()

    @property
    def days(self) -> int:
        return (self.period_end - self.period_start).days + 1

    def label(self) -> str:
        return f"{self.period_start.isoformat()}..{self.period_end.isoformat()}"


# ── boundary discovery ──────────────────────────────────────────────────────


def _plan_stretches(
    unit_id: Any, period_start: date, period_end: date
) -> list[tuple[date, date, str | None]]:
    """The period, cut into plan-assignment stretches. `None` = current plan.

    Read from `unit_plan_assignments_in` (rating's dated history, DEF-504).
    ABSENCE OF HISTORY IS NOT A REFUSAL: a unit assigned before gap-1 closed
    has no rows, and the fallback is the unit's current plan — exactly what
    `gather` has always billed, so an account with no history prices exactly
    as before. A leading uncovered gap (days before the first recorded
    assignment) merges into the first recorded stretch for the same reason:
    nothing recorded a different plan for those days, and inventing a
    boundary there would split a bill on no evidence.
    """
    timeline = gather._resolve("rating", "unit_plan_assignments_in")
    rows = timeline(unit_id, period_start=period_start, period_end=period_end) if timeline else []
    if not rows:
        return [(period_start, period_end, None)]
    stretches: list[tuple[date, date, str | None]] = []
    for index, row in enumerate(rows):
        start = period_start if index == 0 else max(period_start, row["assigned_from"])
        end = min(period_end, row["assigned_to"] or period_end)
        if end < start:
            continue
        plan_id = str(row["rate_plan_id"])
        if stretches and stretches[-1][2] == plan_id:
            stretches[-1] = (stretches[-1][0], end, plan_id)
        else:
            stretches.append((start, end, plan_id))
    if not stretches:
        return [(period_start, period_end, None)]
    # A trailing uncovered gap (the last row closed inside the period with no
    # successor) merges into the last stretch, symmetrically with the leading
    # one: no evidence of a different plan is not evidence of a boundary.
    stretches[-1] = (stretches[-1][0], period_end, stretches[-1][2])
    return stretches


def _tariff_rows_for(unit_id: Any, plan_id: str | None) -> list[dict[str, Any]]:
    """The per-service tariff rows for a stretch's plan.

    `None` (current plan) goes through `backbill._plan_tariffs`, which is the
    read the back-bill path already trusts; a dated plan id goes through the
    same `plan_rate_schedules` selector that function uses underneath.
    """
    if plan_id is None:
        return backbill._plan_tariffs(unit_id)
    schedules = gather._resolve("rating", "plan_rate_schedules")
    if schedules is None:
        raise gather.GatherProblem(
            gather.GATHER_NO_TARIFF,
            "rating has not published plan_rate_schedules, so the plan in force "
            "during part of this period cannot be resolved. Nothing is guessed.",
        )
    rows = list(schedules(plan_id))
    if not rows:
        raise gather.GatherProblem(
            gather.GATHER_NO_TARIFF,
            f"plan {plan_id} (assigned during this period) resolves to no tariff "
            "for any service. The account belongs in the run's exception list.",
        )
    return rows


def split_boundaries(
    unit_id: Any, *, period_start: date, period_end: date, price_only: bool = False
) -> tuple[date, ...]:
    """Every day inside (period_start, period_end] on which the bill must cut.

    A cut is the FIRST day of a new stretch: a plan assignment beginning, or a
    tariff version becoming effective (discovered per plan stretch, so a rate
    change on a plan the unit had already left does not cut anything).

    DEFENSIVE ON ABSENCE, LOUD ON EVIDENCE: an unpublished selector or an
    empty timeline yields no boundaries — the account prices exactly as
    today — but once a boundary IS found, every downstream refusal
    (`_assert_one_version_per_group`, a segment with no version) propagates
    by name, because the alternative is DEF-503 itself.
    """
    cuts: set[date] = set()
    for _services, group_cuts in split_plan(
        unit_id, period_start=period_start, period_end=period_end, price_only=price_only
    ):
        cuts |= set(group_cuts)
    return tuple(sorted(cuts))


def split_plan(
    unit_id: Any, *, period_start: date, period_end: date, price_only: bool = False
) -> tuple[tuple[tuple[str, ...] | None, tuple[date, ...]], ...]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-9012` — WHICH services are cut on
    which days: `backbill.cut_groups`'s `(services, cuts)` pairs.

    A plan reassignment and a plan-version start still cut EVERY service
    (`BR-RAT-114`, unchanged). ⚠ **A TARIFF-VERSION boundary cuts ONLY ITS OWN
    SERVICE since 2026-10-12** (`DEF-BIL-10067`, BR-RAT-114 as amended (1) —
    *"why 3 it is only 2 cuts"*); until then it cut every service and this
    sentence said so. A base charge code's price change
    (`CR-156-BRC10`) cuts ONLY the service that code prices — **PO 2026-10-01,
    option A: *"Split only the service whose price changed. Electric stays
    $12.00, and only water is split."*** Every service sharing one set of cuts
    → one pair with `services=None`, which is the path every bill walked
    before this ruling.
    """
    stretches = _plan_stretches(unit_id, period_start, period_end)
    common: set[date] = set()
    if not price_only:
        for start, _end, _plan in stretches[1:]:
            common.add(start)
    per_service: dict[str, set[date]] = {}
    services: list[str] = []
    linked: dict[str, str] = {}
    # 🔒 `BR-RAT-1066` (`CR-167-BRC10`) — a PLAN VERSION START inside a stretch
    # cuts every service (a new plan version is a plan change, `BR-RAT-114`),
    # and each piece reads ITS version's schedules. A plan with one version
    # states no start inside any period, so nothing new is cut and every bill
    # walks exactly the path it walked before.
    starts_of = gather._resolve("rating", "plan_version_starts", "plan_versioning")
    pricing_day = gather._resolve("rating", "pricing_day", "plan_versioning")
    pieces: list[tuple[date, date, str | None]] = []
    for start, end, plan_id in stretches:
        cuts_here: list[date] = []
        if starts_of is not None:
            cuts_here = [
                day
                for day in starts_of(plan_id, unit_id=unit_id, period_start=start, period_end=end)
                if start < day <= end
            ]
        if not price_only:
            common.update(cuts_here)
        edges = [start, *cuts_here]
        for index, piece_start in enumerate(edges):
            piece_end = edges[index + 1] - timedelta(days=1) if index + 1 < len(edges) else end
            pieces.append((piece_start, piece_end, plan_id))
    for start, end, plan_id in pieces:
        try:
            if pricing_day is not None:
                with pricing_day(end):
                    rows = _tariff_rows_for(unit_id, plan_id)
            else:
                rows = _tariff_rows_for(unit_id, plan_id)
        except gather.GatherProblem:
            # Detection must not newly block an account today's gather accepts
            # (it will refuse, or not, on its own path); the split simply has
            # no timeline to cut on.
            continue
        if not price_only:
            # 🔒 `DEF-BIL-10067` · BR-RAT-114 AMENDED 2026-10-12 (1) — a tariff
            # version boundary cuts ONLY ITS OWN SERVICE. PO verbatim: *"why 3
            # it is only 2 cuts … since ther eis only 1 change in that period
            # for given utility service"*. Until that ruling these days went
            # into `common`, so water re-priced on 15 Sep and storm water on
            # 20 Sep cut EVERY service — trash included — at both days: three
            # parts each, a base row per part, and a cart billed three times
            # at a third. A plan reassignment and a plan-version start (above)
            # still cut every service; a percentage-of-service still travels
            # with its basis (`linked`, `cut_groups`), so sewer follows water.
            for row in rows:
                code = row.get("service_code")
                days = set(
                    backbill.version_boundaries(row["tariff"], period_start=start, period_end=end)
                )
                if not days:
                    continue
                if code:
                    per_service.setdefault(str(code), set()).update(days)
                else:  # pragma: no cover — a row naming no service cuts all
                    common |= days
        codes = [row.get("service_code") for row in rows]
        services.extend(str(code) for code in codes if code)
        # ── CR-156-BRC10 · A BASE CHARGE CODE'S PRICE CHANGE CUTS TOO ───────
        # PO 2026-10-01: *"a period crossing a change is split by days"*. The
        # charge code owns the base (BR-RAT-088) and its price rows are dated
        # now, so a base repriced on the 1st cuts a period exactly as a tariff
        # version would; each segment is gathered on its own first day and
        # reads the row in force then. ⚠ DEF-BIL-9012 — read PER SERVICE, so
        # the cut lands on that service's lines only.
        for code, cuts in backbill.charge_price_cuts_by_service(
            codes, period_start=start, period_end=end
        ).items():
            per_service.setdefault(code, set()).update(cuts)
        linked.update(backbill._percent_links(rows, start, end))
    common = {cut for cut in common if period_start < cut <= period_end}
    per_service = {
        code: {cut for cut in cuts if period_start < cut <= period_end}
        for code, cuts in per_service.items()
    }
    return backbill.cut_groups(
        services, common_cuts=common, service_cuts=per_service, linked=linked
    )


# ── gathering the segments ──────────────────────────────────────────────────


def gather_split(
    account: Any,
    *,
    period_start: date,
    period_end: date,
    cycle_days: int,
    scope_services: tuple[str, ...] | None = None,
    price_only: bool = False,
    cycle_days_for: Any = None,
    reads_from: date | None = None,
    keyed_reads: Any = None,
) -> tuple[SplitSegment, ...]:
    """The period's segments, each gathered at its own date on its own plan —
    or EMPTY when nothing repriced and nothing was reassigned, which is the
    identity: the caller then attaches nothing and the pipeline never sees
    this module.

    Raises `gather.GatherProblem` (reason-coded) once a boundary exists and a
    segment cannot be priced lawfully — the orchestrator turns it into the
    account's exception row, exactly as it does for the unsplit gather.

    `reads_from` and `keyed_reads` (`DEF-BIL-8749`, CR-156-BRC10) carry the
    FIRST and FINAL bills' own readings window into the parts: a first bill's
    readings open the day after move-in (`DEF-BIL-8563`) and a final bill's
    preview prices the move-out wizard's keyed reads (`DEF-CUS-5931`). `None`
    on every other caller — byte-identical to before.
    """
    from apps.billing import runs  # local import — runs imports this module

    unit_id = getattr(account, "unit_id", None)
    if unit_id is None:
        return ()
    try:
        plan = split_plan(
            unit_id, period_start=period_start, period_end=period_end, price_only=price_only
        )
        cuts = tuple(sorted({cut for _group, group_cuts in plan for cut in group_cuts}))
    except Exception:
        # Discovery is best-effort by design (see split_boundaries); a broken
        # timeline read must not block a run that today succeeds. A boundary
        # that WAS found is past this point and refuses loudly below.
        return ()
    if not cuts:
        return ()

    # ⚠ BR-CUS-068 × BR-RAT-114 — A MULTI-UNIT ACCOUNT'S SPLIT IS UNRULED
    # (OQ-336). Everything above reads ONE unit's plan history, and every
    # segment's readings below are read from that same unit — the ANCHOR. On a
    # master account covering several common areas that is two wrong answers at
    # once: the other areas' boundaries are invisible, and their usage vanishes
    # from every segment (which is DEF-571 again, one layer in). Nothing signed
    # says whose history cuts the period when three covered units each have
    # one, so the account REFUSES BY NAME rather than being billed an
    # anchor-only split. A master account whose period holds NO boundary never
    # reaches this line — `cuts` is empty and the split was already skipped —
    # which is every master account today.
    covered = gather.covered_units(account)
    if len(covered) > 1:
        raise gather.GatherProblem(
            gather.GATHER_COVERAGE_MULTI_PLAN,
            f"account {getattr(account, 'account_no', '?')} covers {len(covered)} units "
            "(BR-CUS-068) and this period contains a plan or rate boundary. BR-RAT-114 "
            "cuts a period on ONE unit's dated history, and no signed rule says whose "
            "history cuts it when each covered common area has its own — OQ-336 carries "
            "that to the Product Owner. The bill refuses rather than being priced on the "
            "anchor's boundaries with every other covered area's usage missing from every "
            "segment. The run continues for every other account.",
        )

    stretches = _plan_stretches(unit_id, period_start, period_end)

    def plan_at(day: date) -> str | None:
        for start, end, plan_id in stretches:
            if start <= day <= end:
                return plan_id
        return None

    # ⚠ DEF-BIL-9012 (PO 2026-10-01, option A) — one list of windows PER
    # GROUP of services that share their cuts. A service whose charge code did
    # not change price is ONE window over the whole period, gathered with the
    # caller's own `cycle_days` — exactly what an unsplit bill gathers — so
    # electric at $12.00 beside a water reprice bills $12.00, not 16/31 × 12 +
    # 15/30 × 12 = $12.19. `group is None` (every service shares the cuts) is
    # the path every split walked before the ruling.
    parts: list[tuple[date, date, tuple[str, ...] | None]] = []
    for group, group_cuts in plan:
        segment_start = period_start
        for cut in group_cuts:
            parts.append((segment_start, cut - timedelta(days=1), group))
            segment_start = cut
        parts.append((segment_start, period_end, group))

    gathered: list[tuple[date, date, str | None, dict[str, str], AccountBillingData]] = []
    for start, end, group in parts:
        part_scope = backbill._narrowed_scope(scope_services, group)
        if part_scope == ():
            continue
        whole = (start, end) == (period_start, period_end)
        plan_id = plan_at(start)
        rows = _tariff_rows_for(unit_id, plan_id)
        versions = backbill._assert_one_version_per_group(
            [row for row in rows if group is None or row.get("service_code") in group], start, end
        )
        readings, _unmeasured = runs._readings_for(
            unit_id,
            period_start=max(start, reads_from) if reads_from else start,
            period_end=end,
            scope_services=part_scope,
            **({"keyed_reads": keyed_reads} if keyed_reads else {}),
        )
        data = gather.gather_account(
            account=account,
            # THE LEVER (BR-RAT-007): the segment's OWN first day, so gather
            # resolves the version — and the plan — in force THEN. Passing the
            # run's service date here is DEF-503's mechanism, and the pin test
            # fails on exactly that mutation.
            service_date=start,
            period_start=start,
            period_end=end,
            # THE DAY WEIGHT (B4.3): the denominator is the caller's cycle, so
            # a segment arrives as service_days/cycle_days and the engine
            # derives the factor — no proration arithmetic exists here.
            # ⚠ CR-156-BRC10 — an INTERIM bill crossing a price change states
            # each part over its OWN cycle (`cycle_days_for`, the account's
            # cycle length on the part's last day — `BR-BIL-1066`'s rule,
            # applied per part): 10/16–10/31 over 31, 11/01–11/15 over 30.
            # ⚠ DEF-BIL-9012 — a WHOLE part (a service no cut touched) takes
            # the caller's own denominator, as if nothing had been cut.
            cycle_days=cycle_days_for(start, end) if cycle_days_for and not whole else cycle_days,
            readings=readings,
            scope_services=part_scope,
            rate_plan_id=plan_id,
        )
        gathered.append((start, end, plan_id, versions, data))

    apportioned, estimates_by_part = _apportion_evenly_by_day(
        unit_id,
        gathered,
        period_start=period_start,
        period_end=period_end,
        scope_services=scope_services,
        reads_from=reads_from,
        keyed_reads=keyed_reads,
    )
    return tuple(
        SplitSegment(
            period_start=start,
            period_end=end,
            plan_id=plan_id,
            tariff_version_ids=versions,
            data=data,
            estimates=estimates_by_part.get(index, ()),
        )
        for index, (start, end, plan_id, versions, data) in enumerate(apportioned)
    )


def _apportion_evenly_by_day(
    unit_id: Any,
    gathered: list[tuple[date, date, str | None, dict[str, str], AccountBillingData]],
    *,
    period_start: date,
    period_end: date,
    scope_services: tuple[str, ...] | None,
    reads_from: date | None = None,
    keyed_reads: Any = None,
) -> tuple[
    list[tuple[date, date, str | None, dict[str, str], AccountBillingData]],
    dict[int, tuple[backbill.SegmentEstimate, ...]],
]:
    """BR-RAT-114's apportionment, verbatim: consumption apportions to
    sub-periods EVENLY BY DAY unless an actual read dates the boundary — then
    the read wins.

    THE READ WINS = every segment holds its own measured quantity, and nothing
    here touches any of them (B4.3 as amended 2026-08-11: a reading is never
    prorated). EVENLY BY DAY = when any segment of a service lacks a read, the
    PERIOD's own measured quantity is day-weighted into EVERY segment of that
    service — the whole-period reasoning the PO ruled for back-bills (OQ-191):
    the period-end read MEASURES the whole period, so keeping it on one side
    and deriving the other would bill more water than the meter turned.

    A service the PERIOD never measured is LEFT ALONE — None in every segment,
    BR-BIL-015's decision, never a new refusal (decision log 2026-08-22,
    judgment 3). OQ-191's tenant setting does not reach here: the rule states
    the apportionment itself, so there is nothing left for a setting to choose
    (judgment 4). The arithmetic is `backbill._day_weighted_quantity` — the
    PO's own 14/28 × 6 = 3 kgal, quantized to the consumption column's
    NUMERIC(18,6); a QUANTITY, no money, no rounding law.
    """
    from apps.billing import runs  # local import — runs imports this module

    # 2026-09-30 — keyed by (service, METER). Two meters on one metered
    # service are two readings (PO: "both meter should be build … as a
    # speearte line"); keyed by the code alone, the second meter's period
    # quantity overwrote the first and BOTH meters were apportioned it. A
    # reading naming no meter keys as (code, None): byte-identical before.
    short = {
        (reading.service_code, getattr(reading, "asset_id", None))
        for _s, _e, _p, _v, data in gathered
        for reading in data.readings
        if reading.consumption is None
        and reading.absent_reason != measure_consumption_stage.ABSENT_BASE_ONLY
    }
    measured: dict[tuple[str, Any], Any] = {}
    # 🔒 `DEF-BIL-10067` (PO 2026-10-12, *"the draft is priced on the reading
    # entered"*) — on the ONE-TIME BILL a typed reading measures the WHOLE
    # period, so each part of a cut service is a DAY SHARE of it, exactly as a
    # period-end read with no read on the change day is (the PO's 2.9 → 4.6 =
    # 1.7 → 0.79 + 0.91). Each part's own read, below, came through the same
    # overlay with the part's dates and therefore carries the WHOLE typed
    # quantity — or, where a committed read sits in that part, the committed
    # figure the clerk replaced — so neither may stand: kept, a typed 60 kgal
    # beside a committed 100 kgal part billed 160. `typed` is the set of meters
    # whose whole-period quantity the overlay computed; `None` (every caller
    # but the one-time bill) leaves this function byte-identical.
    typed_win = runs.typed_reads_win(keyed_reads)
    typed: dict[tuple[str, Any], Any] = {}
    if short or typed_win:
        period_readings, _unmeasured = runs._readings_for(
            unit_id,
            period_start=reads_from or period_start,
            period_end=period_end,
            scope_services=scope_services,
            **({"keyed_reads": keyed_reads} if keyed_reads else {}),
        )
        measured = {
            (reading.service_code, getattr(reading, "asset_id", None)): reading.consumption
            for reading in period_readings
            if reading.consumption is not None
        }
        if typed_win:
            typed = {
                (reading.service_code, getattr(reading, "asset_id", None)): reading
                for reading in period_readings
                if getattr(reading, "provisional", False) and reading.consumption is not None
            }
            # Only a meter CUT into two or more parts is shared out; one that
            # was not cut is one whole part, already priced on the typed value,
            # and stays un-flagged (no "estimated read" on its line).
            parts: dict[tuple[str, Any], int] = {}
            for _s, _e, _p, _v, data in gathered:
                for reading in data.readings:
                    key = (reading.service_code, getattr(reading, "asset_id", None))
                    parts[key] = parts.get(key, 0) + 1
            typed = {key: reading for key, reading in typed.items() if parts.get(key, 0) > 1}
            short |= set(typed)
        # Only a service the period MEASURED can be apportioned; the rest keep
        # their absence and their reason, exactly as an unsplit bill would.
        short &= set(measured)

    # 🔒 `DEF-BIL-10067` · BR-RAT-114 AMENDED 2026-10-12, Q-d — the month's
    # peak kW is charged ONCE, at the rate in force at the END of the period
    # (PO: *"i am ok with your reco"*). The peak is a fact about the WHOLE
    # period, so it rides only the LAST part of its service; every earlier part
    # carries a ZERO peak in the same unit, which `price_split_bill` drops from
    # that part's lines (`_drop_deferred_peaks`). Where each part was read, the
    # month's peak is the LARGEST of their peaks — never their sum.
    last_part: dict[tuple[str, Any], int] = {}
    parts_of: dict[tuple[str, Any], int] = {}
    peaks: dict[tuple[str, Any], Any] = {}
    for index, (seg_start, _e, _p, _v, data) in enumerate(gathered):
        for reading in data.readings:
            key = (reading.service_code, getattr(reading, "asset_id", None))
            parts_of[key] = parts_of.get(key, 0) + 1
            if key not in last_part or seg_start >= gathered[last_part[key]][0]:
                last_part[key] = index
            demand = getattr(reading.consumption, "demand", None)
            if demand is not None and key not in short:
                held = peaks.get(key)
                peaks[key] = demand if held is None or demand.amount > held.amount else held
    for key in short:
        demand = getattr(measured[key], "demand", None)
        if demand is not None:
            peaks[key] = demand
    peaks = {key: peak for key, peak in peaks.items() if parts_of.get(key, 0) > 1}
    if not short and not peaks:
        return gathered, {}

    cycle_days = (period_end - period_start).days + 1
    out: list[tuple[date, date, str | None, dict[str, str], AccountBillingData]] = []
    estimates: dict[int, tuple[backbill.SegmentEstimate, ...]] = {}
    allocated: dict[Any, Decimal] = {}
    # Parts of one service arrive in date order (`gather_split` builds them
    # cut by cut), so the LAST part is reached after every earlier one.
    for index, (seg_start, seg_end, plan_id, versions, data) in enumerate(gathered):
        days = (seg_end - seg_start).days + 1
        readings: list[Any] = []
        made: list[backbill.SegmentEstimate] = []
        for reading in data.readings:
            key = (reading.service_code, getattr(reading, "asset_id", None))
            peak = None
            if key in peaks:
                held = peaks[key]
                peak = (
                    held
                    if last_part.get(key) == index
                    else rating_seam.Quantity(amount=Decimal("0"), unit=held.unit)
                )
            if key not in short:
                if peak is not None and reading.consumption is not None:
                    reading = dataclasses.replace(
                        reading, consumption=dataclasses.replace(reading.consumption, demand=peak)
                    )
                readings.append(reading)
                continue
            period_quantity = measured[key]
            last = last_part.get(key) == index
            whole = typed.get(key)
            if whole is not None:
                # 🔒 DEF-BIL-10067 — the share names the reading the WHOLE
                # period was priced on (the saved typed one on a draft, none on
                # a preview), never a committed read inside this part, so issue
                # locks what the bill used. The register pair is the whole
                # period's and is not printed against a part's share.
                reading = dataclasses.replace(
                    reading,
                    read_id=whole.read_id,
                    chain_read_ids=tuple(getattr(whole, "chain_read_ids", ()) or ()),
                    provisional=True,
                    prior_read=None,
                    current_read=None,
                )
            quantity = _share(
                allocated, (key, None), period_quantity.amount, days, cycle_days, last=last
            )
            unit = period_quantity.unit  # rule 3 — the period's own unit
            readings.append(
                dataclasses.replace(
                    reading,
                    consumption=rating_seam.Quantity(
                        amount=quantity,
                        unit=unit,
                        # 🔒 `DEF-BIL-10067` Q-c — EACH time-of-use window's
                        # register is split by days too, and priced at this
                        # part's window prices. Until 2026-10-12 the windows
                        # were dropped here and a TOU account crossing a rate
                        # change refused (`MissingWindowQuantity`).
                        windows=tuple(
                            rating_seam.WindowQuantity(
                                channel=window.channel,
                                quantity=rating_seam.Quantity(
                                    amount=_share(
                                        allocated,
                                        (key, window.channel),
                                        window.quantity.amount,
                                        days,
                                        cycle_days,
                                        last=last,
                                    ),
                                    unit=window.quantity.unit,
                                ),
                            )
                            for window in (getattr(period_quantity, "windows", ()) or ())
                        ),
                        # Q-d — the peak, on the last part only (see above).
                        demand=peak,
                    ),
                    # THE FLAG (OQ-191's, reused): it reaches the customer's
                    # document ("estimated read") and the locked payload, so a
                    # derived quantity can never be read as a meter reading.
                    estimated=True,
                    absent_reason=None,
                )
            )
            made.append(
                backbill.SegmentEstimate(
                    period_start=seg_start,
                    period_end=seg_end,
                    service_code=reading.service_code,
                    quantity=quantity,
                    unit=unit,
                    days=days,
                    cycle_days=cycle_days,
                    source=backbill.ESTIMATE_DAY_WEIGHTED,
                )
            )
        out.append(
            (
                seg_start,
                seg_end,
                plan_id,
                versions,
                dataclasses.replace(data, readings=tuple(readings)),
            )
        )
        if made:
            estimates[index] = tuple(made)
    return out, estimates


def _share(
    allocated: dict[Any, Decimal],
    key: Any,
    period_amount: Decimal,
    days: int,
    cycle_days: int,
    *,
    last: bool,
) -> Decimal:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10067` — one part's day share of the
    period's measured quantity, and the LAST part takes the REMAINDER.

    Each share is quantized to the consumption column's 6 places
    (`backbill._day_weighted_quantity`), so three day shares of 800 kWh —
    373.333333 + 133.333333 + 293.333333 — added back to **799.999999 kWh**
    on the draft (walk of 2026-10-12). Usage is shown at the meter's own
    precision: the last part is `period − Σ(earlier parts)`, so the parts add
    back EXACTLY to what the meter turned (373.333333 + 133.333333 +
    293.333334 = 800). Every earlier part is unchanged, and so is any split
    whose shares already added back (the PO's 0.793333 + 0.906667 = 1.7; the
    BR-RAT-114 pin's 5 + 5 = 10).
    """
    if last:
        share = period_amount - allocated.get(key, Decimal("0"))
        return share.quantize(backbill.QUANTITY_SCALE)
    share = backbill._day_weighted_quantity(period_amount, days=days, cycle_days=cycle_days)
    allocated[key] = allocated.get(key, Decimal("0")) + share
    return share


# ── pricing and assembly ────────────────────────────────────────────────────


def _measured_segment(segment: SplitSegment, parent: AccountBillingData) -> MeasuredUsage:
    """Stages 1 and 2 for one segment, with the segment's window in any refusal.

    The exempt absences are `calculate_account`'s own pair (DEF-161): a
    base-only account (BR-CUS-055) and a service whose tariff measures no
    usage of its own (BR-RAT-015). Anything else unresolved refuses exactly as
    the unsplit path refuses — same reason code, the window added.
    """
    from apps.billing import runs  # local import — runs imports this module

    subscription = resolve_subscription(segment.data)
    usage = measure_consumption(subscription, segment.data)
    # BR-RAT-090 (DEF-1813) — the same named refusal `runs.calculate_account`
    # raises, in the same order and for the same reason: a split period must not
    # tell a clerk to estimate a register when the work is to count the carts.
    counted = tuple(
        service
        for service in usage.unmeasured
        if service.absent_reason
        in (
            measure_consumption_stage.ABSENT_ASSET_COUNT_UNAVAILABLE,
            measure_consumption_stage.ABSENT_ASSET_COUNT_UNIT_UNSTATED,
        )
    )
    if counted:
        names = ", ".join(service.service_code for service in counted)
        raise gather.GatherProblem(
            runs.CALC_ASSET_COUNT_UNAVAILABLE,
            f"account {parent.account_no}: {names} is billed by a COUNT of its "
            f"assets on the unit (BR-RAT-090) and no count could be determined "
            f"in {segment.label()}. The bill refuses rather than billing zero — "
            "'no carts recorded' and 'zero carts' are different facts.",
            service_code=counted[0].service_code,
        )
    # ⚠ **THE FOUR EXEMPT REASONS AND THE ARGUMENT FOR EACH ONE LIVE IN
    # `measure_consumption.EXEMPT_FROM_MISSING_READ`** — they were spelled out
    # here, in `runs` and (three reasons short) in `backbill` until
    # `DEF-BIL-5326` on 2026-09-15, when the sub-period path's stale copy was
    # found refusing a percent-of-service sewer that this list has exempted
    # since DEF-161. Three literal copies of one money rule is how that
    # happened; read the tuple, and add a reason THERE or in none of them.
    unresolved = tuple(
        service
        for service in usage.unmeasured
        if service.absent_reason not in measure_consumption_stage.EXEMPT_FROM_MISSING_READ
    )
    if unresolved:
        names = ", ".join(service.service_code for service in unresolved)
        raise gather.GatherProblem(
            runs.CALC_UNRESOLVED_READ,
            f"account {parent.account_no}: {names} still has no usable read in "
            f"{segment.label()} and no decision. BR-BIL-015 makes that a choice — "
            "estimate it, hold the account, or bill without the service — and "
            "billing the rest would be taking the third one silently.",
            service_code=unresolved[0].service_code,
        )
    return usage


#: Matches ANY segment stamp at the end of a description — not one specific
#: window. The final tax-bearing call re-emits the CARRIED lines (already
#: stamped with THEIR OWN windows) beside the first segment's fresh ones, so
#: the post-call stamp must skip a line wearing any stamp, not merely the
#: first segment's: matching only the first window would stamp a June-16..30
#: line a second time with June 1..15's dates — two windows on one line, the
#: customer-facing confusion this whole mechanism exists to prevent.
_STAMP_RE = re.compile(r" · \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}$")


def _stamped(lines: Any, period_start: date, period_end: date) -> list[Any]:
    """The segment's dates onto its usage/base lines — requirement (4)'s
    customer-visible half. Money untouched: description only. A line already
    wearing a stamp (a carried line, in the final call) is left alone."""
    label = _segment_label(period_start, period_end)
    return [
        (
            dataclasses.replace(line, description=f"{line.description}{label}")
            if line.kind in ("usage", "base") and not _STAMP_RE.search(line.description)
            else line
        )
        for line in lines
    ]


def price_split_bill(
    usages: list[MeasuredUsage],
    segments: tuple[SplitSegment, ...],
    parent: AccountBillingData,
) -> Any:
    """Every segment priced at its own versions; the BILL taxed exactly once.

    One `price_bill` call PER SEGMENT — not per proration factor, as
    `backbill.price_day_weighted` buckets — because BR-RAT-114 requires each
    line to name its segment's dates, and two same-factor segments sharing a
    call would emerge indistinguishable (the $21.00 pin is exactly that case:
    15/30 and 15/30). The line arithmetic is identical either way: the engine
    prices each (tariff, consumption) pair independently against its call's
    period, and rounds per line (BR-RAT-003), so call granularity cannot move
    a line amount. What MUST NOT run per segment is the tax pass — B4.2
    computes tax once over Σ(rounded taxable lines) — so every call but the
    first prices with NO taxes and NO fees, and its finalized lines ride the
    first call's bill-level line channel, which alone carries the bill's
    taxes, fees and discounts. That is `price_day_weighted`'s proven shape
    (its worked cent: 6.24 one-pass vs 6.23 per-segment), reused with segment
    granularity.

    TAXES, FEES AND DISCOUNTS ARE THE PARENT'S — the whole-period gather at
    the run's service date, exactly what an unsplit bill uses (decision log
    2026-08-22, judgment 2). The per-segment gathers' tax rows are
    deliberately unread: the split re-prices usage and base only.

    THE FIRST SEGMENT'S FRESH LINES are stamped AFTER the call (the engine
    emits them; a carried line arrives already stamped, and no engine
    description ends in an ISO-dated stamp — see `_segment_label`), so every
    usage/base line on the bill names its dates.
    """
    # ⚠ DEF-BIL-9012 (PO 2026-10-01, option A) — a WHOLE part (services no
    # charge-code change touched, priced over the bill's own period as ONE
    # part) wears NO date stamp, exactly as on an unsplit bill, and is priced
    # FIRST: the final call stamps its own fresh lines and skips only lines
    # already stamped, so an unstamped carried line would otherwise be given
    # the first part's dates.
    def is_whole(segment: Any) -> bool:
        return (segment.period_start, segment.period_end) == (parent.period_start, parent.period_end)

    order = sorted(range(len(segments)), key=lambda index: not is_whole(segments[index]))
    usages = [usages[index] for index in order]
    segments = tuple(segments[index] for index in order)

    # 🔒 `DEF-BIL-10067` · BR-RAT-114 AMENDED 2026-10-12 (2), Q-a — ONE BASE
    # ROW PER SERVICE, two only when the base price itself changed. See
    # `_single_base_keys` for which services, and the call order below for how.
    single_base = _single_base_keys(usages, segments, is_whole)
    if single_base:
        usages = [_without_base(usage, single_base) for usage in usages]
    deferred = _deferred_peaks(usages, segments)

    def stamp(lines: Any, segment: Any) -> list[Any]:
        if is_whole(segment):
            return list(lines)
        return _stamped(lines, segment.period_start, segment.period_end)

    account = rating_seam.AccountContext(currency=parent.currency, tax_exempt=parent.tax_exempt)

    def part(usage: MeasuredUsage) -> Any:
        return rating_seam.price_bill(
            services=tuple((service.tariff, service.consumption) for service in usage.measured),
            base_only_services=tuple(service.tariff for service in usage.unmeasured),
            period=usage.subscription.period,
            account=account,
            taxes=(),
            fees=(),
        )

    if single_base:
        # EVERY part is priced untaxed and carried; the ONE tax-bearing call is
        # the whole-period base-only call, so its fresh lines — the one base
        # row per service — are whole-month lines and wear no part's dates.
        # B4.2 is untouched: one tax pass over Σ(rounded taxable lines), the
        # carried parts included, exactly as before.
        carried: list[Any] = []
        for index, (usage, segment) in enumerate(zip(usages, segments)):
            priced = part(usage)
            carried.extend(stamp(_drop_deferred_peaks(priced.lines, deferred[index]), segment))
        return rating_seam.price_bill(
            services=(),
            base_only_services=tuple(_base_only_tariff(t) for t in single_base.values()),
            period=resolve_subscription(parent).period,
            account=account,
            taxes=parent.taxes,
            fees=tuple(carried) + tuple(parent.fees),
            discounts=tuple(getattr(parent, "discounts", ()) or ()),
        )

    first_usage = usages[0]
    first_segment = segments[0]
    carried = []
    for index, (usage, segment) in enumerate(zip(usages[1:], segments[1:]), start=1):
        priced = part(usage)
        carried.extend(stamp(_drop_deferred_peaks(priced.lines, deferred[index]), segment))

    priced = rating_seam.price_bill(
        services=tuple((service.tariff, service.consumption) for service in first_usage.measured),
        base_only_services=tuple(service.tariff for service in first_usage.unmeasured),
        period=first_usage.subscription.period,
        account=account,
        taxes=parent.taxes,
        fees=tuple(carried) + tuple(parent.fees),
        discounts=tuple(getattr(parent, "discounts", ()) or ()),
    )
    # A deferred peak on the FIRST part is a $0.00 line (its peak is zero by
    # construction), so dropping it after the tax pass moves no tax.
    lines = _drop_deferred_peaks(priced.lines, deferred[0])
    return dataclasses.replace(priced, lines=tuple(stamp(lines, first_segment)))


def _service_key(service: Any) -> tuple[str, Any]:
    return (str(service.service_code), getattr(service, "asset_id", None))


#: What makes two parts' base charges THE SAME charge: the amount, the code it
#: came from (BR-RAT-088), and the two factors `price_usage._base_lines`
#: multiplies it by. Any difference → the base price changed → two rows.
def _base_identity(tariff: Any) -> tuple[Any, ...]:
    return (
        getattr(tariff, "base_charge", None),
        getattr(tariff, "base_charge_code", None),
        getattr(tariff, "jurisdiction_factor", None),
        getattr(tariff, "occupancy_factor", None),
    )


def _single_base_keys(
    usages: list[MeasuredUsage], segments: tuple[Any, ...], is_whole: Any
) -> dict[tuple[str, Any], Any]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10067` — the services whose base is
    ONE row over the whole period: `{(service, meter): the last part's tariff}`.

    BR-RAT-114 AMENDED 2026-10-12 (2), Q-a, PO verbatim on the review: *"one
    base row per service, two only if the base price changed"*. A service cut
    because its USAGE rate changed (a tariff version) still pays ONE month's
    base: on the PO's water, $8.00 — not 14/30 × $8.00 + 16/30 × $8.00 =
    $3.73 + $4.27, which foots to the same $8.00 and says the customer was
    charged a base twice.

    A key qualifies when it is priced in two or more CUT parts and every one of
    them states the same base (`_base_identity`). A base charge code repriced
    inside the period (DEF-BIL-9012's case) differs → not here → two rows,
    each at its own price, exactly as before. A service with a MINIMUM charge
    is left as it was: its floor is applied per call against that call's lines,
    and lifting the base out of a part would move what the floor tops up.
    """
    seen: dict[tuple[str, Any], list[tuple[date, Any]]] = {}
    for usage, segment in zip(usages, segments):
        if is_whole(segment):
            continue
        for service in usage.services:
            seen.setdefault(_service_key(service), []).append((segment.period_start, service.tariff))
    out: dict[tuple[str, Any], Any] = {}
    for key, parts in seen.items():
        if len(parts) < 2:
            continue
        tariffs = [tariff for _start, tariff in sorted(parts, key=lambda item: item[0])]
        if getattr(tariffs[-1], "base_charge", None) is None:
            continue
        if any(getattr(tariff, "minimum_amount", None) is not None for tariff in tariffs):
            continue
        if len({_base_identity(tariff) for tariff in tariffs}) != 1:
            continue
        out[key] = tariffs[-1]
    return out


def _without_base(usage: MeasuredUsage, keys: dict[tuple[str, Any], Any]) -> MeasuredUsage:
    """The part with its base lifted out for `keys` — `base_charge=None` is the
    engine's own *"no base line"* (price_usage._base_lines), never a zero."""
    return dataclasses.replace(
        usage,
        services=tuple(
            dataclasses.replace(service, tariff=dataclasses.replace(service.tariff, base_charge=None))
            if _service_key(service) in keys
            else service
            for service in usage.services
        ),
    )


def _base_only_tariff(tariff: Any) -> Any:
    """The service's BASE and nothing else, for the one whole-period call.

    The engine prices a base-only service by normalising a zero quantity
    through the tariff's model and dropping the usage lines; a percentage of
    service, a demand or a time-of-use model would refuse that zero for want of
    a basis, a peak or a window. So the model is stated as `flat` at no unit
    price — every input the base reads (`base_charge`, its code, the
    jurisdiction and occupancy factors, the meter, the version) is the
    service's own and untouched; only the usage half, which is dropped anyway,
    is neutral."""
    return dataclasses.replace(
        tariff,
        model="flat",
        unit_price=Decimal("0"),
        tiers=(),
        windows=(),
        season=None,
        season_days=(),
        season_tiers=(),
        season_span=None,
        capacity=None,
        energy_rate_per_kwh=None,
        demand_rate_per_kw=None,
        ratchet_enabled=False,
        pf_penalty_enabled=False,
        percent=None,
        basis_service=None,
        percent_basis=None,
        per_size_line=False,
        installed_sum_line=False,
        minimum_amount=None,
    )


def _deferred_peaks(
    usages: list[MeasuredUsage], segments: tuple[Any, ...]
) -> list[set[tuple[str, str]]]:
    """Per part, the `(service, peak unit)` whose demand line belongs to a
    LATER part (Q-d — `_apportion_evenly_by_day` put the month's peak there and
    a zero here). Empty for every part of every bill with no demand tariff."""
    latest: dict[tuple[str, Any], date] = {}
    for usage, segment in zip(usages, segments):
        for service in usage.measured:
            if getattr(service.consumption, "demand", None) is not None:
                key = _service_key(service)
                latest[key] = max(latest.get(key, segment.period_start), segment.period_start)
    out: list[set[tuple[str, str]]] = []
    for usage, segment in zip(usages, segments):
        here: set[tuple[str, str]] = set()
        for service in usage.measured:
            demand = getattr(service.consumption, "demand", None)
            if demand is not None and segment.period_start < latest[_service_key(service)]:
                here.add((str(service.service_code), str(demand.unit)))
        out.append(here)
    return out


def _drop_deferred_peaks(lines: Any, deferred: set[tuple[str, str]]) -> list[Any]:
    if not deferred:
        return list(lines)
    return [
        line
        for line in lines
        if not (
            line.kind == "usage"
            and (str(getattr(line, "service", "")), str(getattr(line, "unit", ""))) in deferred
        )
    ]


def split_snapshot(
    parent: AccountBillingData,
    segments: tuple[SplitSegment, ...],
    usages: list[MeasuredUsage],
) -> dict:
    """The split record, frozen into the payload BR-BIL-030 locks at issue.

    A reprint in 2033 must show which prices applied to which days, what share
    of the period each stretch was, which plan covered it, and which
    quantities were DERIVED rather than read — the same obligations
    `backbill._group_snapshot` states, met the same way.
    """
    return {
        "rule": "BR-RAT-114",
        "segments": [
            {
                "period_start": segment.period_start.isoformat(),
                "period_end": segment.period_end.isoformat(),
                "service_date": segment.period_start.isoformat(),
                "days": segment.days,
                "cycle_days": segment.data.cycle_days,
                "rate_plan_id": segment.data.rate_plan_id,
                "rate_plan_name": segment.data.rate_plan_name,
                "rate_plan_version": segment.data.rate_plan_version,
                "tariff_version_ids": dict(segment.tariff_version_ids),
                "services": [
                    {
                        "code": service.service_code,
                        "measured": service.consumption is not None,
                        "estimated": bool(service.estimated),
                        "quantity": (
                            str(service.consumption.amount)
                            if service.consumption is not None
                            else None
                        ),
                        "unit": (
                            service.consumption.unit if service.consumption is not None else None
                        ),
                    }
                    for service in usage.services
                ],
            }
            for segment, usage in zip(segments, usages)
        ],
        "estimates": [estimate.as_dict() for segment in segments for estimate in segment.estimates],
    }


def calculate_split_account(
    data: AccountBillingData,
    *,
    bill_run: Any,
    service_date: date,
    bill_type: str = "cycle",
) -> Any:
    """Phase 2 for ONE split account: segments priced, ONE tax pass, ONE draft.

    The document's header facts — plan, period shape, taxes, account
    snapshot — are the PARENT's, exactly as an unsplit bill's are; the split
    detail lives per line (dates + version id) and in the locked
    `mid_period_split` record. `assemble_document` is the same stage 6 every
    bill goes through; nothing here writes.
    """
    from apps.billing.stages.assemble_document import assemble_document
    from core import tenancy as core_tenancy

    combined, priced = price_split_account(data)
    return assemble_document(
        usage=combined,
        priced=priced,
        tenant_id=core_tenancy.current_tenant_id(),
        account_id=data.account_id,
        bill_run=bill_run,
        period_start=data.period_start,
        period_end=data.period_end,
        service_date=service_date,
        bill_type=bill_type,
    )


def price_split_account(data: AccountBillingData) -> tuple[MeasuredUsage, Any]:
    """The split account's stages 1–5, with **nothing written** (CR-075 wave F).

    Extracted from `calculate_split_account` unchanged, for the reason
    `runs.price_account` states in full: runbook 23 prices an account exactly
    as the run does and writes nothing, and the only way to make *identical to
    four decimals* true by CONSTRUCTION rather than by assertion is for both
    callers to be this one function. `calculate_split_account` is now that
    function plus stage 6, which is the only line that ever wrote.
    """
    segments = tuple(data.split_segments)
    usages = [_measured_segment(segment, data) for segment in segments]
    priced = price_split_bill(usages, segments, data)

    parent_subscription = resolve_subscription(data)
    snapshot = dict(parent_subscription.snapshot)
    snapshot["mid_period_split"] = split_snapshot(data, segments, usages)
    combined = MeasuredUsage(
        subscription=dataclasses.replace(parent_subscription, snapshot=snapshot),
        services=tuple(service for usage in usages for service in usage.services),
    )
    return combined, priced


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-RAT-114@2026-08-22 (the ruling row in 04-docs/05-modules/06-rating/
#         02-business-rules.md · the decision-log rows of 2026-08-22 · DEF-503 ·
#         DEF-504 · apps/billing/backbill.py as the working precedent)
# generated: 2026-08-22 by the BR-RAT-114 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the split rides the existing run
#         endpoints) E=deferred(no-frontend-half — S31.2 renders the stamped
#         lines; a dedicated split panel is unruled) F✔ G✔ H=deferred(PO
#         2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row updated)
# gates: see tests/test_br_rat_114_midperiod_split.py (the $21.00 pin proved RED
#         first: [22.000000] against [10.00, 11.00]) · golden-verify 33/33
#         before AND after (no B5 fixture carries a mid-period change; every
#         unsplit account walks the untouched path)
# exceptions: (1) PER-LINE PERIOD COLUMNS still carry the WHOLE period —
#         `invoice_lines.period_start/period_end` are stage-6-stamped once per
#         bill, the same open half as backbill's exception (2). The dates a
#         customer checks ride the DESCRIPTION and the locked split record;
#         moving them into the columns needs the per-line period contract that
#         DEF-276's version id got, REPORTED not begun here.
#         (2) `plan_versions` (the filing table) defines no boundary — it has
#         no effective date BY DESIGN (OQ-324). ⚠ HISTORY: OQ-324 CLOSED 2026-10-03
#         as (B) — a plan version start now cuts (BR-RAT-1066). A plan content change splits
#         through the tariff-version timeline, where its prices live.
#         (3) A tax rule changing INSIDE the period does not split the tax:
#         B4.2's single pass runs on the parent's rules at the run's service
#         date, unchanged from today. The back-bill path uses its FIRST group's
#         rules; with rules constant across the window the two agree (asserted
#         by the two-paths test). A mid-period TAX change is unruled either
#         way and is left exactly as found.
#         (4) Discovery is DEFENSIVE (unpublished selector / broken timeline →
#         no split, today's path) while a FOUND boundary refuses loudly
#         (`_assert_one_version_per_group`) — the split never silently prices
#         across a boundary it has seen, and never newly blocks an account it
#         cannot see a boundary for.
# exceptions: [DEF-1813 2026-08-28, BR-BIL-710] a split period raises the SAME
#         named refusal `runs.calculate_account` raises for an absent asset
#         count, in the same order and for the same reason: a clerk must not be
#         told to estimate a register when the work is to count the carts.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
