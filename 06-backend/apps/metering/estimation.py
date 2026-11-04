# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-014 (auto-estimate missing reads — trailing-3 daily average,
#           max 2 consecutive, PER CHANNEL) · US-MET-015 (true-up at the next
#           actual read)   Screens: S25, S28 step 4, S29, S31.2
# Rules:    BR-MET-026 (daily_avg = Σ last-3 ACTUAL consumptions ÷ Σ their day
#           counts; estimate = daily_avg × days_in_period; NUMERIC(18,6)
#           unrounded; actuals only — estimates never compound; ≥1 actual
#           required; no history → no estimate) · BR-MET-027 (max consecutive
#           estimates = the tenant's `est_max_consecutive`, seeded 2; beyond it
#           a field visit is FORCED) · BR-MET-028 (labeled with method +
#           consecutive number, status `estimated`, NO register current_value) ·
#           BR-MET-029 (true-up by register arithmetic at the next actual) ·
#           BR-MET-058 (PER CHANNEL — a TOU window never borrows another's
#           history) · BR-MET-062 (a missing `demand` value is NEVER estimated)
# Tests:    06-backend/tests/test_us_met_014_estimation.py (GT-9 to the digit,
#           the per-channel fixture, the cap, and the demand refusal) ·
#           06-backend/tests/test_us_met_quantity_seams.py (the published
#           GT-9 seam and the one-implementation proof)
# Impacts:  apps/metering/services.py (the sole writer of estimated rows) ·
#           apps/metering/quantities.py (the published GT-9 seam calls
#           `correction_quantity` — ONE true-up subtraction, not two) ·
#           rating prices the quantity later (GT-9's money side is NOT here)
# ───────────────────────────────────────────────────────
"""Estimation + true-up — QUANTITIES ONLY.

Scope boundary, stated once and obeyed everywhere below: this module computes
consumption quantities in NUMERIC(18,6) and nothing else. It never reads a
rate, never produces an amount, and never rounds — B4.4 puts rounding at
invoice-line finalization, and pricing an estimate is rating's GT-9 money side,
not metering's. If a future edit here would produce a currency figure, it needs
finance re-sign via HUMAN-GUIDE §6, not a decision in this file.

What is SIGNED, and therefore built (OQ-003 CLOSED, PO R6; B4 "Estimation";
GT-9's expected values signed):

    daily_avg = Σ(consumption of last 3 ACTUAL reads) ÷ Σ(their day counts)
    estimate  = daily_avg × days_in_estimated_period
    trued     = (actual_register − last_actual_register) × multiplier
                − Σ estimated consumption since that last actual

Both run inside ONE (meter, channel) lineage (BR-MET-058). GT-9's fixture
reproduces exactly: 612 + 618 + 624 = 1,854 kWh over 90 days → 20.600000/day →
× 30 days = 618.000000 kWh; then (44,182 − 42,864) × 1 − 618 = 700.000000 kWh.

What is REFUSED rather than guessed:
  · no actual history at all → no estimate, field visit (BR-MET-026);
  · consecutive estimates at or beyond the tenant's cap → no estimate, field
    visit FORCED (BR-MET-027) — the cap is read from config, never the literal
    2, so a tenant that sets 3 gets 3 (US-MET-014/TC-6);
  · the `demand` channel, always (BR-MET-062: a peak drives kW dollars and an
    estimated peak is a dispute);
  · a tenant with no `read_validation_settings` row — same fail-safe as the
    flag engine (BR-MET-020): the method and the cap are CONFIG, so with no
    config there is no estimate.

`est_method` is honoured, not assumed: the only SIGNED method is
`trailing_3_daily_avg`. A tenant row naming any other method gets no estimate
and a stated reason, because inventing a second method's arithmetic is exactly
the guess CLAUDE.md's prime directive forbids.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# ── CR-079 · THE SEVEN METHODS A TENANT MAY CHOOSE (PO 2026-09-07) ─────────
#
# PO, verbatim: *"this should be drop down options - give 4 to 5 options here"*,
# then *"we are good with these + add last 6 month avg + Use avg from plan"*.
# BR-MET-026 named exactly ONE method until that day, and this module refused
# every other value by name — correctly, because inventing arithmetic that
# bills a customer is the guess the prime directive forbids.
#
# ⚠ **WHAT CHANGED IS THE WINDOW, NOT THE ARITHMETIC.** Five of the seven are
# BR-MET-026's own formula — Σ consumption ÷ Σ days, × this period's days —
# over a different SELECTION of the same actual reads. Nothing new is
# computed, and `trailing_3_daily_avg` walks a code path whose behaviour is
# byte-for-byte what GT-9 pinned: it is still `SELECTION[…][:3]`, still the
# same `daily_average`, still the same `METHOD_LABEL` on the row.
#
# ⚠ **AND `trailing_3_daily_avg` IS STILL THE DEFAULT AND NOTHING MIGRATES A
# STORED ROW.** Changing how a missing reading is estimated changes what a
# customer is billed; it has to be a choice somebody makes.
#
# ⚠ **TWO OF THE SEVEN HAVE NO INPUT IN THIS PRODUCT AND ARE NOT IMPLEMENTED
# HERE.** `route_peer_average` needs a definition of a peer group that nobody
# has given (OQ-MET-1761) and `plan_average` needs an average held on a rate
# plan, which no table stores (OQ-MET-1762). They are refused by name with
# `estimation_method_not_implemented`, exactly as any unknown method has been
# since this module was written, and the settings screen will not store them.
METHOD_TRAILING_3_DAILY_AVG = "trailing_3_daily_avg"
METHOD_TRAILING_6_DAILY_AVG = "trailing_6_daily_avg"
METHOD_TRAILING_12_DAILY_AVG = "trailing_12_daily_avg"
METHOD_SAME_PERIOD_LAST_YEAR = "same_period_last_year"
METHOD_REPEAT_LAST_ACTUAL = "repeat_last_actual"
METHOD_ROUTE_PEER_AVERAGE = "route_peer_average"  # OQ-MET-1761 — no peer group defined
METHOD_PLAN_AVERAGE = "plan_average"  # OQ-MET-1762 — no plan holds an average

#: Every method the settings screen offers, in the order the PO named them.
EST_METHODS: tuple[str, ...] = (
    METHOD_TRAILING_3_DAILY_AVG,
    METHOD_TRAILING_6_DAILY_AVG,
    METHOD_TRAILING_12_DAILY_AVG,
    METHOD_SAME_PERIOD_LAST_YEAR,
    METHOD_REPEAT_LAST_ACTUAL,
    METHOD_ROUTE_PEER_AVERAGE,
    METHOD_PLAN_AVERAGE,
)

#: The subset this engine can actually RUN. The screen refuses the difference
#: and so does `services.save_read_validation_general`; this tuple is the one
#: place that knows, so the three cannot disagree.
RUNNABLE_EST_METHODS: tuple[str, ...] = (
    METHOD_TRAILING_3_DAILY_AVG,
    METHOD_TRAILING_6_DAILY_AVG,
    METHOD_TRAILING_12_DAILY_AVG,
    METHOD_SAME_PERIOD_LAST_YEAR,
    METHOD_REPEAT_LAST_ACTUAL,
)

#: How many trailing ACTUALS each runnable method averages. `same_period_last_year`
#: is not a window — it is a single period reached by counting back — so it is
#: absent here and handled by `_window_for`.
_TRAILING_WINDOW_BY_METHOD: dict[str, int] = {
    METHOD_TRAILING_3_DAILY_AVG: 3,
    METHOD_TRAILING_6_DAILY_AVG: 6,
    METHOD_TRAILING_12_DAILY_AVG: 12,
    METHOD_REPEAT_LAST_ACTUAL: 1,
}

#: `same_period_last_year` takes the actual ONE YEAR BACK — the 12th period
#: counting back on a monthly cycle — ON ITS OWN, not an average ending there.
#: ⚠ THE READING OF "the same period last year" IS OURS AND IS WRITTEN DOWN
#: (decision log 2026-09-07): twelve PERIODS back, not 365 days back, because
#: `EstimationInput` carries day counts and no dates, and because a utility
#: reading bi-monthly means something different by "last year" than a monthly
#: one does. `OQ-MET-1763` puts the bi-monthly case to the PO.
_SAME_PERIOD_OFFSET = 12
# What BR-MET-028 stamps on the row (US-MET-014 §5 "trailing_3_avg").
METHOD_LABEL = "trailing_3_avg"
METHOD_MANUAL_OVERRIDE = "manual_override"  # US-MET-015 §5 (staff override of an estimate)

TRAILING_WINDOW = 3  # "trailing-3-cycle" — the method's own name, not a threshold

# BR-MET-026 says the estimate is "NUMERIC(18,6) unrounded". Six decimal places
# IS that type's declared scale, and the ratified worked examples are written in
# it (618.000000 · 210.000000 · 118.000000). `354 ÷ 90 × 30` is 117.9999…9 in
# arbitrary precision, so expressing the result at the column's own scale is
# what makes the SIGNED figure reproduce — and it is what Postgres does on
# INSERT regardless. This is NOT B4.4's money rounding: that rounds currency at
# invoice-line finalization, and nothing in this module produces currency.
NUMERIC_18_6 = Decimal("0.000001")

# Refusal reasons (every one surfaces to the clerk verbatim).
REASON_NO_CONFIG = "validation_config_missing"
REASON_NO_HISTORY = "no_history"  # US-MET-014/TC-5 "no history — field visit"
REASON_CAP_REACHED = "consecutive_estimate_cap_reached"  # BR-MET-027
REASON_DEMAND_CHANNEL = "demand_never_estimated"  # BR-MET-062
REASON_UNKNOWN_METHOD = "estimation_method_not_implemented"
REASON_NO_DAYS = "period_days_missing"
REASON_ZERO_DAYS = "trailing_day_count_zero"


@dataclass
class EstimationInput:
    """One (meter, channel) gap to fill. Assembled by the service layer —
    `trailing_actuals` is already filtered to ACTUAL reads of THIS channel
    (BR-MET-026 "actuals only" + BR-MET-058 "never mixed across channels")."""

    channel: str
    unit: str | None  # the asset's EXPLICIT UoM — an estimate carries it too
    days_in_period: int | None
    # Newest first; each entry is (consumption, day_count) of an ACTUAL read.
    trailing_actuals: list[tuple[Decimal, int]] = field(default_factory=list)
    consecutive_estimates: int = 0  # how many estimates already stand since the last actual


@dataclass(frozen=True)
class EstimationResult:
    """Either an estimate with its full working, or a refusal with a reason.
    There is no third state and no silent zero."""

    estimated: bool
    consumption: Decimal | None = None
    unit: str | None = None
    method: str | None = None
    consecutive_no: int | None = None
    daily_average: Decimal | None = None
    days_in_period: int | None = None
    reason: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "estimated": self.estimated,
            "consumption": str(self.consumption) if self.consumption is not None else None,
            "unit": self.unit,
            "method": self.method,
            "consecutive_no": self.consecutive_no,
            "daily_average": str(self.daily_average) if self.daily_average is not None else None,
            "days_in_period": self.days_in_period,
            "reason": self.reason,
            "detail": self.detail,
        }


def _refuse(reason: str, **detail: Any) -> EstimationResult:
    return EstimationResult(estimated=False, reason=reason, detail=detail)


def window_for(method: str, trailing_actuals: list[tuple[Decimal, int]]) -> list[tuple[Decimal, int]]:
    """WHICH actual reads a method averages. The arithmetic never varies — only
    this selection does, which is the whole of CR-079 in one function.

    ⚠ `trailing_3_daily_avg` returns `trailing_actuals[:3]`, which is exactly
    what `daily_average` sliced before this function existed. GT-9 walks that
    branch and nothing about it moved.

    `same_period_last_year` is the odd one: not a window ending at the newest
    read but a SINGLE period reached by counting twelve back. An empty list
    means "this method has no history to work from here", and the caller
    refuses with `no_history` rather than inventing a shorter window — a
    seasonal method quietly falling back to last month is the failure the
    method exists to avoid.
    """
    if method == METHOD_SAME_PERIOD_LAST_YEAR:
        if len(trailing_actuals) < _SAME_PERIOD_OFFSET:
            return []
        return [trailing_actuals[_SAME_PERIOD_OFFSET - 1]]
    size = _TRAILING_WINDOW_BY_METHOD.get(method, TRAILING_WINDOW)
    return trailing_actuals[:size]


def daily_average(
    trailing_actuals: list[tuple[Decimal, int]],
    method: str = METHOD_TRAILING_3_DAILY_AVG,
) -> Decimal | None:
    """BR-MET-026's first half: Σ consumptions ÷ Σ day counts, over the reads
    the METHOD selects (fewer is allowed — "shorter history uses what exists,
    ≥1 actual"). Unrounded NUMERIC(18,6) arithmetic; no float ever touches it.

    ⚠ `method` defaults to the signed one, so every existing caller — GT-9's
    fixture among them — computes exactly what it computed before CR-079.
    """
    window = window_for(method, trailing_actuals)
    if not window:
        return None
    total_days = sum(days for _c, days in window)
    if total_days <= 0:
        return None
    total_consumption = sum((c for c, _d in window), Decimal("0"))
    return total_consumption / Decimal(total_days)


def estimate(spec: EstimationInput, config: Any) -> EstimationResult:
    """BR-MET-026/027/058/062 — the full decision for one (meter, channel).

    Returns an EstimationResult that is either an estimate carrying its own
    working (so S31.2's "3-cycle avg · 1st estimate" renders from storage) or a
    refusal naming why. Never raises for an ordinary refusal: "no history" is a
    legitimate answer a clerk must see next to the row, not an exception.
    """
    # BR-MET-062 — checked FIRST: no config, no history and no cap can make a
    # demand estimate lawful, so nothing else about the row matters.
    if spec.channel == "demand":
        return _refuse(REASON_DEMAND_CHANNEL, channel=spec.channel, rule_ref="BR-MET-062")

    if config is None:
        return _refuse(REASON_NO_CONFIG, rule_ref="BR-MET-020")

    method = (getattr(config, "est_method", None) or "").strip()
    if method not in RUNNABLE_EST_METHODS:
        # Unchanged behaviour for anything this engine cannot run, including
        # the two CR-079 methods with no input in the product: a stated
        # refusal, never a silent fall-through to a different rule. A reading
        # estimated by a rule that quietly became another rule bills a
        # customer under a rule nobody chose.
        return _refuse(REASON_UNKNOWN_METHOD, configured_method=method or None)

    cap = getattr(config, "est_max_consecutive", None)
    if cap is None:
        return _refuse(REASON_NO_CONFIG, rule_ref="BR-MET-027")
    if spec.consecutive_estimates >= int(cap):
        # BR-MET-027 / US-MET-014 TC-4: the disposition is FORCED to field visit.
        return _refuse(
            REASON_CAP_REACHED,
            consecutive_estimates=spec.consecutive_estimates,
            cap=int(cap),
            forced_disposition="field_visit",
        )

    # ⚠ **HISTORY IS ASKED BEFORE DAYS — REORDERED 2026-08-26 (CR-038 W9 task 8).**
    # These two checks were the other way round, and on a meter with NO history
    # at all the days check fired FIRST: `days_in_period` is derived by the
    # caller from the prior actual head, so no history means no prior head means
    # no days, and the refusal came back `period_days_missing` — a symptom,
    # reported as the cause. BR-MET-026's own words are *"no actual history at
    # all → no estimate, field visit"*, and this file's §"What is REFUSED"
    # states it first; `period_days_missing` additionally carries NO
    # `forced_disposition`, so the clerk was told a date was missing and never
    # told to send someone out.
    #
    # RED-FIRST PROOF, verbatim, run against the pre-reorder code
    # (tests/test_w9_event_reads.py::
    #  test_w9_door__task_8_no_history_is_a_refusal_as_data_never_a_zero):
    #     AssertionError: assert 'period_days_missing' == 'no_history'
    #     - no_history
    #     + period_days_missing
    #
    # ONE case changes behaviour and only one: no history AND no days. With
    # history present the window is non-empty and the days check below still
    # answers (a zero-length period still refuses `period_days_missing`), and
    # with days supplied by the caller both orders already answered
    # `no_history`. Nothing in this tree pins `period_days_missing`.
    window = window_for(method, spec.trailing_actuals)
    if not window:
        # CR-079: for `same_period_last_year` this ALSO covers "there is not a
        # year of history yet", and the answer is the same one BR-MET-026 gives
        # for no history at all — no estimate, send somebody out.
        return _refuse(REASON_NO_HISTORY, forced_disposition="field_visit", method=method)

    if spec.days_in_period is None or spec.days_in_period <= 0:
        return _refuse(REASON_NO_DAYS, days_in_period=spec.days_in_period)

    average = daily_average(spec.trailing_actuals, method)
    if average is None:
        return _refuse(REASON_ZERO_DAYS)

    consumption = (average * Decimal(spec.days_in_period)).quantize(NUMERIC_18_6)
    return EstimationResult(
        estimated=True,
        consumption=consumption,
        unit=spec.unit,  # CLAUDE.md rule 3: an estimate is a quantity, so it carries its unit
        # BR-MET-028 stamps the SIGNED method's own short label; every other
        # method stamps its own code, so a reading always says which rule made
        # it and two methods can never be confused in the record.
        method=METHOD_LABEL if method == METHOD_TRAILING_3_DAILY_AVG else method,
        consecutive_no=spec.consecutive_estimates + 1,  # "1st estimate" / "2nd estimate" (A5)
        daily_average=average,
        days_in_period=spec.days_in_period,
        detail={
            "trailing_reads": len(window),
            "trailing_consumptions": [str(c) for c, _d in window],
            "trailing_days": [d for _c, d in window],
            "sum_consumption": str(sum((c for c, _d in window), Decimal("0"))),
            "sum_days": sum(d for _c, d in window),
            "channel": spec.channel,
            "rule_ref": "BR-MET-026 / BR-MET-058 (GT-9)",
            "est_method": method,
        },
    )


@dataclass
class TrueUpInput:
    """One (meter, channel) lineage receiving its next ACTUAL read."""

    channel: str
    unit: str | None
    actual_register: Decimal | None
    last_actual_register: Decimal | None
    multiplier: Decimal | None
    # The estimates standing between the two actuals, on THIS channel only.
    estimated_consumptions: list[Decimal] = field(default_factory=list)
    estimated_read_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TrueUpResult:
    applies: bool
    quantity: Decimal | None = None
    unit: str | None = None
    register_delta: Decimal | None = None
    estimated_total: Decimal | None = None
    corrects_read_ids: list[str] = field(default_factory=list)
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "applies": self.applies,
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "unit": self.unit,
            "register_delta": (
                str(self.register_delta) if self.register_delta is not None else None
            ),
            "estimated_total": (
                str(self.estimated_total) if self.estimated_total is not None else None
            ),
            "corrects_read_ids": list(self.corrects_read_ids),
            "reason": self.reason,
        }


def correction_quantity(actual: Decimal, previously_billed: Decimal) -> Decimal:
    """BR-MET-029's subtraction, in ONE place.

        correction = what the span ACTUALLY measured
                   − what was already billed for that same span

    Both `true_up` below (which derives `actual` from register arithmetic over
    a whole estimate→actual lineage) and the published GT-9 seam in
    `apps/metering/quantities.py` (which is handed the two quantities directly)
    reduce to this one line, so the rule cannot drift into two versions.

    A NEGATIVE result is legitimate and is NOT clamped: an over-estimate owes
    the customer a quantity credit, and clamping would silently keep an
    over-billed customer over-billed (US-MET-015/TC-3).

    Quantized to NUMERIC(18,6) — the column's own declared scale, which is what
    makes the SIGNED figures reproduce exactly. This is NOT B4.4 money
    rounding: no rate is read and no currency figure is produced anywhere in
    this module. Carrying the UNIT is the caller's job (CLAUDE.md rule 3);
    this function sees only the numbers, and it never sees two units at once.
    """
    return (actual - previously_billed).quantize(NUMERIC_18_6)


def true_up(spec: TrueUpInput) -> TrueUpResult:
    """BR-MET-029 register arithmetic, within ONE channel's lineage.

        trued = (actual_register − last_actual_register) × multiplier
                − Σ estimated consumption since that last actual

    A negative result is legitimate and is NOT clamped (US-MET-015/TC-3: an
    over-estimate flows as a quantity credit) — clamping would silently keep an
    over-billed customer over-billed. Pricing that quantity at CURRENT-period
    rates is rating's job; no rate is read here.

    With no estimates standing, this returns `applies=False`: the normal
    consumption path already handled the read and there is nothing to correct
    (US-MET-015/TC-7 — "nothing invented").

    ⚠ ONE HONEST NARROWING, REPORTED: BR-MET-029 says "Σ estimated consumption
    BILLED since that last actual". Billing does not exist yet, so no read can
    carry a billed marker, and this sums every standing estimate on the lineage
    instead. In the ratified flow those sets are identical (an estimate exists
    to be billed); they diverge only for an estimate created and trued up
    inside one un-billed window. When the bill run lands, the filter belongs
    here — it is a one-line change and a named one, not a hidden assumption.
    """
    if spec.actual_register is None or spec.last_actual_register is None:
        return TrueUpResult(applies=False, reason="no_actual_pair")
    if not spec.estimated_consumptions:
        return TrueUpResult(applies=False, reason="no_standing_estimates")
    if spec.multiplier is None:
        return TrueUpResult(applies=False, reason="multiplier_missing")

    register_delta = (
        (spec.actual_register - spec.last_actual_register) * spec.multiplier
    ).quantize(NUMERIC_18_6)
    estimated_total = sum(spec.estimated_consumptions, Decimal("0"))
    return TrueUpResult(
        applies=True,
        quantity=correction_quantity(register_delta, estimated_total),
        unit=spec.unit,  # explicit, always (CLAUDE.md rule 3)
        register_delta=register_delta,
        estimated_total=estimated_total,
        corrects_read_ids=list(spec.estimated_read_ids),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-014@feddf11 (story+rules snapshot — EP-MET-05, co-story US-MET-015; OQ-003 CLOSED, math signed)
# generated: 2026-08-10 by the W2 reads lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — engine module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(N/A — not a 🔒 path: quantities only, no money figure/threshold/key is authored here, so neither a finance re-sign nor a review-ledger row is triggered)
# gates: see the lane report; GT-9's 618.000000 / 700.000000 are asserted to the digit in tests/test_us_met_014_estimation.py
# exceptions: true_up() sums STANDING estimates where BR-MET-029 says BILLED estimates — billing does not exist yet; narrowing is documented in the function docstring and REPORTED · only `trailing_3_daily_avg` is implemented; any other configured method REFUSES rather than improvising · [2026-08-11 quantity-seam lane] BR-MET-029's subtraction was EXTRACTED verbatim into `correction_quantity` so the published GT-9 seam and `true_up` share ONE implementation; no figure moved and the existing GT-9 assertions pass unchanged. Proved RED first: inverting that subtraction makes GT-9 report −82 and both the golden fixture and tests/test_us_met_014_estimation.py fail; restored, they pass.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
