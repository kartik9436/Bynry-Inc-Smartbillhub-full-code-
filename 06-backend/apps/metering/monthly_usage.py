# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W3 task 3.8 — the ACC-01 **Usage** tab (chart + 5-metric
#           strip). Design: 04-docs/02-decisions/18-cr030-onboarding-design.md
#           §5.2.2, Usage row. Reference drawing:
#           05-prototype/r10-2026-08-16/SMARTBillHub.dc.html, account detail.
#           Screens: S21 (Usage tab)
# Story:    US-CUS-011 (the S21 operational tabs — Usage is the first of five)
# Rules:    BR-MET-106 (the month is computed from reads, STORED, restated on a
#           correction, ABSENT when unread, and marks its estimates — PO
#           2026-08-24, quoted VERBATIM below) · BR-MET-028 (an estimate carries
#           consumption and NO current_value) · BR-MET-055 (why storing it is
#           worth doing) · contrast BR-CUS-016 (ageing: derived, NEVER stored) ·
#           CLAUDE.md hard rule 3 (an explicit unit, always) · hard rule 4
#           (corrections are new rows)
# Questions: OQ-358 (a month whose reads for ONE service disagree about the unit)
# Tests:    06-backend/tests/test_br_met_106_monthly_usage.py
# Impacts:  apps/metering/monthly_usage_service.py (the sole writer) ·
#           apps/metering/monthly_usage_reads.py (the Usage tab's read model)
# ───────────────────────────────────────────────────────
"""BR-MET-106 — the monthly-usage JUDGMENTS, with no database in them.

Same shape as `apps/customers/service_request.py` and
`apps/customers/payment_plan.py`: everything a test should be able to ask
without a tenant, a row or a transaction lives here; the write path next door
does the ORM, the audit and the restatement.

────────────────────────────────────────────────────────────────────────────
THE RULE, VERBATIM (BR-MET-106, CONFIRMED PO 2026-08-24, CR-030 W3 T3.8)
────────────────────────────────────────────────────────────────────────────
PO verbatim: *"based on meter reading calculate monthly useage and save them
and display them"*.

    "The figure is `Σ MeterRead.consumption` over the reads whose `read_at`
     falls in the calendar month, grouped by account and service, **carrying
     its unit explicitly** (hard rule 3 — kWh, kgal and therms are never added
     together and a stored quantity without its unit is unreadable). …
     **Corrections RESTATE, they never edit:** a superseded or late read
     (BR-MET-051's lineage shape) writes a NEW monthly row for that month,
     carrying `computed_at` and the read-lineage heads it summed, and the chart
     reads the latest — the same supersede discipline the reads themselves use,
     for the same reason. **An unread month is ABSENT, never `0`:** zero usage
     and no read are different claims about a customer, and the account-detail
     Usage tab states the absence rather than drawing a zero bar (hard-won
     law 1). **Estimates count and are marked** — BR-MET-028 estimates carry
     consumption with no `current_value`, so the month includes them and
     records that it did, because a customer looking at a 628 kWh month is
     entitled to know part of it was estimated."

────────────────────────────────────────────────────────────────────────────
WHY THIS ONE IS STORED WHEN BR-CUS-016's AGEING IS NOT
────────────────────────────────────────────────────────────────────────────
The rule states the distinction and it is the entire justification, so it is
repeated here where the code lives rather than left in the register:

  * **Ageing is a function of TODAY.** It changes with no new data, so a stored
    ageing is wrong the morning after it is written. BR-CUS-016 says *never
    stored* for that reason.
  * **A month's usage is a function of THAT MONTH'S READS ONLY.** Once the
    month is closed and its reads are in, the figure cannot drift on its own.

⚠ **THIS IS NOT A LICENCE TO STORE OTHER DERIVED FIGURES.** The test a future
lane must pass before storing one is the sentence above — *can this change
without new data?* — and for almost everything on a customer screen (a balance,
an ageing bucket, a days-past-due, a credit tier) the answer is yes.

────────────────────────────────────────────────────────────────────────────
THE ONE THING THIS MODULE REFUSES TO ANSWER, BY NAME
────────────────────────────────────────────────────────────────────────────
**`OQ-358` — a month whose reads for ONE account and ONE service do not agree
about the unit.** BR-MET-106 says the figure carries its unit explicitly and
that kWh, kgal and therms are never added together; it does not say what a
month looks like when its own inputs disagree. Three readings are all
defensible and none is signed — refuse the month outright, publish one row per
unit (and let the chart draw two series), or take the meter's own UoM as
authoritative and convert. Converting is the one that would quietly change a
customer's number, so nothing here guesses: `summarise()` raises
`NotImplementedError("OQ-358")` and the caller stops.

That is a REACHABLE state, not a theoretical one: `meter_reads.unit` is stamped
per ASSET (`MeterRead` docstring law 3), and one account can hold two assets on
one service — a replaced meter re-registered in different units, or a
sub-metered common area, is enough.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Sequence

#: The zero of a consumption sum, at `meter_reads.consumption`'s own precision.
#: B4.4: unrounded until display — this module never rounds a quantity.
ZERO = Decimal("0.000000")

#: Percentages are computed to 6 and displayed at 2 (CLAUDE.md hard rule 2, PO
#: re-sign 2026-08-22). The YoY metric is the only percentage on this screen.
PERCENT_PLACES = 6


@dataclass(frozen=True)
class ReadFact:
    """One read, reduced to the six things a month cares about.

    Deliberately NOT a `MeterRead`: this module holds no ORM, and the writer
    next door is what turns rows into these. `read_id` is the LINEAGE HEAD's
    id — BR-MET-106 asks the stored month to carry the heads it summed.

    ⚠ **`asset_id` AND `channel` JOINED THIS RECORD ON 2026-08-26 (DEF-798),
    AND THEY ARE NOT DECORATION.** A month's figure was Σ over every usable
    read of an account and a service, register-blind, so a demand meter's kW
    peak-delta was added to its own kWh energy total and a TOU meter's three
    window reads were counted a second time on top of its `total`. Measured on
    the probe that found it: **684 + 14 = 698 kWh where the truth is 684 kWh.**
    Which register a read came off is the fact that was missing, and
    `select_consumption_facts` below is the judgment that needs it.

    Both carry defaults so a caller that genuinely has one register (a unit
    test over a flat meter) stays readable — but the ORM writer next door
    always supplies them, and `select_consumption_facts` groups on `asset_id`,
    so a caller that leaves them blank gets one bucket and the `total`
    behaviour it had before.
    """

    read_id: str
    read_at: datetime
    consumption: Decimal
    unit: str
    is_estimate: bool
    asset_id: str = ""
    channel: str = "total"
    #: `DEF-MET-10163` — the day an ACTUAL reading measures FROM (its prior
    #: reading's date, `meter_reads.period_start`). `None` on an estimate and on
    #: an opening reading; read only by `drop_covered_estimates`.
    measured_from: date | None = None
    #: `DEF-MET-10163` — the estimates this actual's BR-MET-029 true-up already
    #: subtracted (`meter_reads.trues_up_read_ids`). Those are NOT double counted.
    trues_up: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MonthFigure:
    """One (account, service, month) statement, before it is a row."""

    period_month: date
    quantity: Decimal
    unit: str
    read_count: int
    estimated_read_count: int
    source_read_ids: tuple[str, ...]

    @property
    def has_estimate(self) -> bool:
        """BR-MET-106: the month *records that it did* include an estimate."""
        return self.estimated_read_count > 0

    @property
    def fingerprint(self) -> str:
        return fingerprint(self)


class MixedUnitMonth(NotImplementedError):
    """OQ-358 — one account, one service, one month, two units.

    A `NotImplementedError` subclass on purpose: G8 reads the OQ id out of the
    raise, and the prime directive says a lane meeting an unruled case stubs at
    the boundary rather than choosing a value.
    """


def month_of(read_at: datetime) -> date:
    """The calendar month a read falls in, as its FIRST DAY.

    ⚠ **No timezone conversion happens here, and that is a property of the
    stored column rather than a shortcut.** `meter_reads.read_at` is stamped at
    00:00Z of the read DATE (`MeterRead`'s own field comment), so its UTC date
    IS the read date; converting it into a tenant timezone would move reads
    taken on the 1st into the previous month for every tenant west of UTC and
    invent a boundary the reads do not have. If that stamping ever changes,
    this function is the first thing that has to change with it.
    """
    return date(read_at.year, read_at.month, 1)


class UnclassifiedChannel(NotImplementedError):
    """A register nobody has told this module how to treat (DEF-798's sequel).

    The channel vocabulary is deliberately extensible — BR-MET-059 / B2 r8, PO
    RD-1 option B: *"adding a register means adding a string"*. That is exactly
    why a consumption sum may not have an ELSE branch. `generation` was minted
    on 2026-08-26 and BR-MET-135 says in as many words that it is *"never
    summed with consumption"*; had this function guessed, a solar device's
    612 kWh of production would have been added to the site's usage the day the
    string landed, and nothing would have failed.

    So the classification is TOTAL, a listed TOU window, or a listed
    never-consumption register — and a fourth kind stops the month rather than
    joining the sum by default.
    """


def select_consumption_facts(
    reads: Sequence[ReadFact],
    *,
    total_channel: str,
    tou_windows: Sequence[str],
    never_consumption: Sequence[str],
) -> list[ReadFact]:
    """The reads that ARE this period's consumption — DEF-798, the whole fix.

    ────────────────────────────────────────────────────────────────────────
    WHAT WENT WRONG, WITH THE NUMBER
    ────────────────────────────────────────────────────────────────────────
    DEF-798, verbatim: *"monthly_usage.month_figure adds consumption over every
    usable read for the account, so a demand peak-delta lands in the ENERGY
    total and TOU window reads are double-counted against total. Measured:
    684 + 14 = 698 kWh where the truth is 684 kWh."*

    The mixed-unit guard (OQ-358) could not see it and never could: every
    channel on one meter is stamped with the SAME asset UoM (`MeterRead`
    docstring law 3), so a kW peak and a kWh total are the same string to a
    check that compares units. **A unit test is not a register test.**

    ────────────────────────────────────────────────────────────────────────
    THE THREE RULES, AND WHY EACH IS PER-ASSET
    ────────────────────────────────────────────────────────────────────────
    1. **A never-consumption register is dropped outright** — `export`
       (BR-AST-029: a net meter's grid-push) and `generation` (BR-MET-135: a
       device's own production), plus `demand`, whose figure is a delta between
       two MAXIMA in kW and is not a quantity anybody consumed (BR-RAT-014).
       `selectors._channel_quantities` already excludes the same set on the
       money path; this is the same law on the display path.

    2. **`total` OR the TOU windows, never both.** A TOU meter's `tou_on +
       tou_mid + tou_off` IS its total; a meter that reports both reports one
       month's energy twice. Where an asset has a `total` head in the month,
       the windows are dropped; where it has no `total`, the windows ARE the
       month and are summed.

    3. **The choice is made PER ASSET, not per account and not per service.**
       One account can hold a flat meter and a TOU meter on one service (a
       replaced meter, a sub-metered common area — the same reachable state
       OQ-358 names). Choosing once for the whole service would drop the flat
       meter's `total` because a different meter reported windows, and lose a
       real month of a real customer's usage.

    Everything about which STRING means what is passed in by the caller, so the
    vocabulary has exactly one declaration (`apps.metering.models`) and this
    module stays free of the ORM. A read whose channel matches nothing raises
    `UnclassifiedChannel` — see that class for why there is no default branch.
    """
    windows = set(tou_windows)
    excluded = set(never_consumption)

    by_asset: dict[str, list[ReadFact]] = {}
    for read in reads:
        if read.channel in excluded:
            continue
        if read.channel != total_channel and read.channel not in windows:
            raise UnclassifiedChannel(
                f"DEF-798: register {read.channel!r} is neither {total_channel!r}, nor a "
                f"time-of-use window, nor a declared never-consumption register. A "
                f"consumption sum has no default branch — classify it where the channel "
                f"vocabulary is declared, in the commit that mints it (BR-MET-059)."
            )
        by_asset.setdefault(read.asset_id, []).append(read)

    kept: list[ReadFact] = []
    for asset_reads in by_asset.values():
        has_total = any(r.channel == total_channel for r in asset_reads)
        for read in asset_reads:
            if has_total and read.channel in windows:
                continue  # rule 2 — the windows ARE the total; do not add both
            kept.append(read)
    return kept


def covered_estimate_ids(
    estimates: Iterable[ReadFact], actuals: Iterable[ReadFact]
) -> set[str]:
    """The estimates a LATER actual reading already counts — `DEF-MET-10163`.

    PO ruling 2026-10-15, verbatim *"go with 1 and 3"*; option 1 as put:
    *"once an actual reading covers an estimate's days, the estimate stops
    counting in monthly usage"*. Ruled clause: *"an estimate whose days are
    covered by a later actual reading on the same meter/register (the actual's
    prior-read date is on or before the estimate's date) no longer counts"*.

    Worked (AC-2026-00049, electric): actual 09/24 1,200 kWh · bill-run
    estimate 09/30 560 kWh · actual 10/06 measured from 09/24, 1,200 kWh.
    September summed 1,200 + 560 = **1,760**; the 10/06 actual counts
    09/24–10/06 in October, so the 560 was counted twice. With the estimate
    covered, September is **1,200** and October stays 1,200.

    An estimate E is covered by an actual A when all four hold:

      1. same meter (`asset_id`) and same register (`channel`);
      2. A is LATER — `A.read_at > E.read_at`;
      3. A's interval spans E — `A.measured_from <= E.read_at`'s date;
      4. **A did NOT true E up** — `E.read_id not in A.trues_up`.

    ⚠ **CLAUSE 4 IS OURS, AND WITHOUT IT THE RULE WOULD UNDERCOUNT EVERY
    ORDINARY ESTIMATE.** When an estimate is on file BEFORE the next actual is
    posted, BR-MET-029's true-up writes the actual's consumption NET of it and
    names it in `trues_up_read_ids` — and that actual still measures from the
    reading before the estimate, so clauses 1–3 hold for it too. There the
    estimate and the actual together equal the register difference and nothing
    is counted twice; dropping the estimate would lose its days entirely. The
    ruling's subject is the double count (*"NOT COUNTED TWICE"*), and only an
    actual written WITHOUT knowledge of the estimate — which is what a bill
    run's estimate dated behind an already-posted reading is — double counts.

    Neither row is edited or deleted (hard rule 4 — the estimate may sit on an
    issued bill); this only decides which rows a month's SUM contains.
    """
    by_register: dict[tuple[str, str], list[ReadFact]] = {}
    for actual in actuals:
        if actual.is_estimate or actual.consumption is None or actual.measured_from is None:
            continue
        by_register.setdefault((actual.asset_id, actual.channel), []).append(actual)
    covered: set[str] = set()
    for estimate in estimates:
        if not estimate.is_estimate:
            continue
        day = estimate.read_at.date()
        for actual in by_register.get((estimate.asset_id, estimate.channel), ()):
            if (
                actual.read_at > estimate.read_at
                and actual.measured_from <= day  # type: ignore[operator]
                and estimate.read_id not in actual.trues_up
            ):
                covered.add(estimate.read_id)
                break
    return covered


def summarise(period_month: date, reads: Sequence[ReadFact]) -> MonthFigure | None:
    """Σ over one month's reads for one account and one service.

    Returns **`None` for a month with no reads** — BR-MET-106's *"an unread
    month is ABSENT, never `0`"*. A `MonthFigure` carrying `Decimal("0")` is a
    different claim (the meter was read and did not move) and is returned when
    that is what the reads say.

    A read whose `consumption` is NULL contributes NOTHING and is not counted:
    it is a register reading with no computed usage (an opening read has no
    prior), and counting it would inflate `read_count` into a claim that a
    figure was derived from more evidence than it was.

    Raises `MixedUnitMonth` (OQ-358) when the reads disagree about the unit.
    """
    usable = [r for r in reads if r.consumption is not None]
    if not usable:
        return None

    units = {r.unit for r in usable}
    if len(units) > 1:
        raise MixedUnitMonth(
            f"OQ-358: {period_month:%Y-%m} carries reads in {sorted(units)} for one "
            "account and one service. BR-MET-106 says a month's figure carries ONE "
            "unit explicitly and that kWh, kgal and therms are never added together; "
            "it does not say what a month looks like when its own reads disagree. "
            "Refuse the month, publish one row per unit, or convert? Converting "
            "would silently change a customer's number, so nothing is guessed here."
        )

    quantity = ZERO
    for r in usable:
        quantity += r.consumption

    return MonthFigure(
        period_month=period_month,
        quantity=quantity,
        unit=units.pop(),
        read_count=len(usable),
        estimated_read_count=sum(1 for r in usable if r.is_estimate),
        # Sorted so the fingerprint is stable across query orderings — two
        # recomputes that saw the same reads must produce the same string.
        source_read_ids=tuple(sorted(str(r.read_id) for r in usable)),
    )


def group_by_month(reads: Iterable[ReadFact]) -> dict[date, list[ReadFact]]:
    """The reads of one account and one service, bucketed by calendar month.

    Months with no reads simply do not appear — the absence is the absence
    (BR-MET-106), and no caller has to remember to strip a zero.
    """
    buckets: dict[date, list[ReadFact]] = {}
    for read in reads:
        buckets.setdefault(month_of(read.read_at), []).append(read)
    return buckets


def fingerprint(figure: MonthFigure) -> str:
    """A content address for one month's INPUTS — CLAUDE.md rule 6.

    Rule 6 names bill runs and payment webhooks, where a CALLER supplies an
    idempotency key. Nobody submits a "monthly usage request": the recompute is
    something the product does to itself, so the key has to come from the
    content. Two recomputes that saw the same lineage heads, summed to the same
    quantity, in the same unit, produce the same string and the second writes
    nothing.

    The quantity and the unit are inside the hash as well as the read ids,
    because a read can be EDITED in the one way B2 r8 allows — a supersede —
    and a lane that later changed how consumption is derived would otherwise
    recompute a different figure over an identical id set and store neither.
    """
    parts = [
        figure.period_month.isoformat(),
        str(figure.quantity),
        figure.unit,
        str(figure.estimated_read_count),
        *figure.source_read_ids,
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# THE 5-METRIC STRIP — r10's own labels, computed over PRESENT months only
# ═══════════════════════════════════════════════════════════════════════════
# r10 draws: `Avg / month 628 kWh · last 12 months` · `Peak month 842 kWh ·
# Jul 2026` · `Low month 412 kWh · Feb 2026` · `YoY change +8.2% · vs prior
# year` · `Water avg 3.42 kgal · last 12 months`.
#
# ⚠ **AN ABSENT MONTH IS EXCLUDED FROM EVERY ONE OF THEM, NOT COUNTED AS ZERO.**
# Averaging over absent months divides by a denominator that includes months
# nobody read, which is the zero bar BR-MET-106 forbids wearing a different
# hat: it would quietly pull a real average down and print a number no read
# supports. So `average_over` divides by the number of months that HAVE a
# figure, and says how many that was, so the screen can qualify the number.


@dataclass(frozen=True)
class MonthPoint:
    """One point of the chart: a month, and either a figure or an absence."""

    period_month: date
    quantity: Decimal | None
    unit: str | None
    estimated_read_count: int = 0
    read_count: int = 0

    @property
    def present(self) -> bool:
        return self.quantity is not None


@dataclass(frozen=True)
class Average:
    quantity: Decimal | None
    unit: str | None
    months_counted: int
    months_absent: int


def average_over(points: Sequence[MonthPoint]) -> Average:
    """`Avg / month`. `None` when NO month in the window has a figure."""
    present = [p for p in points if p.present]
    absent = len(points) - len(present)
    if not present:
        return Average(quantity=None, unit=None, months_counted=0, months_absent=absent)
    total = ZERO
    for p in present:
        total += p.quantity  # type: ignore[operator]
    return Average(
        quantity=total / Decimal(len(present)),
        unit=present[0].unit,
        months_counted=len(present),
        months_absent=absent,
    )


def peak_of(points: Sequence[MonthPoint]) -> MonthPoint | None:
    """`Peak month`. Ties go to the EARLIER month, so the answer is stable."""
    present = [p for p in points if p.present]
    if not present:
        return None
    return max(sorted(present, key=lambda p: p.period_month), key=lambda p: p.quantity)


def low_of(points: Sequence[MonthPoint]) -> MonthPoint | None:
    """`Low month`. Ties go to the EARLIER month, for the same reason."""
    present = [p for p in points if p.present]
    if not present:
        return None
    return min(sorted(present, key=lambda p: p.period_month), key=lambda p: p.quantity)


@dataclass(frozen=True)
class YoyChange:
    """`YoY change`, or the reason there is not one."""

    percent: Decimal | None
    this_year_total: Decimal | None
    prior_year_total: Decimal | None
    absent_reason: str | None


def yoy_change(this_year: Sequence[MonthPoint], prior_year: Sequence[MonthPoint]) -> YoyChange:
    """(Σ this year − Σ prior year) / Σ prior year, as a percentage at 6 dp.

    Three ways there is no answer, and each is REPORTED rather than rendered as
    0.0%, because "no change" and "we cannot say" are different claims:

      * no month of this year has a figure       → `no_current_reads`
      * no month of the prior year has a figure  → `no_prior_reads`
      * the prior year read exactly zero         → `prior_year_zero`
        (the division is undefined; a percentage change from nothing is not
        infinity, it is unanswerable)

    ⚠ **BOTH SIDES ARE SUMS OVER THE MONTHS THAT ARE PRESENT** — not averages
    scaled up, and not zero-filled. Comparing a full year against a part year
    therefore compares less usage against more, which is TRUE of the reads and
    is why `months_compared` travels with the answer in the read model.
    """
    current = [p for p in this_year if p.present]
    prior = [p for p in prior_year if p.present]
    if not current:
        return YoyChange(None, None, None, "no_current_reads")
    if not prior:
        return YoyChange(None, None, None, "no_prior_reads")

    current_total = ZERO
    for p in current:
        current_total += p.quantity  # type: ignore[operator]
    prior_total = ZERO
    for p in prior:
        prior_total += p.quantity  # type: ignore[operator]

    if prior_total == 0:
        return YoyChange(None, current_total, prior_total, "prior_year_zero")

    percent = (current_total - prior_total) / prior_total * Decimal(100)
    return YoyChange(
        percent=percent.quantize(Decimal(1).scaleb(-PERCENT_PLACES)),
        this_year_total=current_total,
        prior_year_total=prior_total,
        absent_reason=None,
    )


@dataclass(frozen=True)
class PeriodChange:
    """One month measured against ONE other month, or the reason there is not one.

    ⚠ **THIS IS A MONTH AGAINST A MONTH, WHICH IS NOT WHAT `YoyChange` DOES.**
    `yoy_change` compares two twelve-month TOTALS and answers a percentage over
    a year; both comparisons here answer *how does this month compare with that
    one*, which is the question a person actually arrives with and which no
    total can answer. The two live side by side deliberately.

    ⚠ **THE DIFFERENCE AND THE PERCENTAGE ARE BOTH SERVED, AND THEY ARE NOT
    THE SAME FACT.** `CPB-06` states its answer in the unit — *86 kWh more
    than August 2025* — and `CPB-07` states its answer as a percentage —
    *5% less than July*. A screen showing one of them needs the other absent
    rather than recomputed, so both travel.

    ⚠ **`direction` IS A CODE AND THE CATALOGUE WRITES THE WORD** (B14 rule
    35). `more` · `less` · `same`, and `same` is a THIRD value rather than a
    signed zero, because *0% more* is not a sentence anybody says.

    ⚠ **EVERY QUANTITY CARRIES ITS UNIT** (CLAUDE.md hard rule 3): `unit` is
    the unit of `difference`, and two months that disagree about theirs have
    no difference at all rather than a bare number.
    """

    this_month: date | None
    against_month: date | None
    difference: Decimal | None
    unit: str | None
    percent: Decimal | None
    direction: str | None
    absent_reason: str | None


def _no_change(reason: str, this_month: date | None = None) -> PeriodChange:
    return PeriodChange(
        this_month=this_month,
        against_month=None,
        difference=None,
        unit=None,
        percent=None,
        direction=None,
        absent_reason=reason,
    )


def _direction_of(difference: Decimal) -> str:
    if difference > 0:
        return "more"
    if difference < 0:
        return "less"
    return "same"


def _compare(this: MonthPoint, against: MonthPoint, reason_if_zero: str) -> PeriodChange:
    """The shared arithmetic of both comparisons — subtract, then divide.

    ⚠ **THE UNIT IS CHECKED BEFORE ANYTHING IS SUBTRACTED** (hard rule 3).
    `800 kWh − 714 kgal` is not `86` of anything, and a screen handed a bare
    number would print it under a heading that names one of the two units.

    ⚠ **AN EARLIER MONTH OF EXACTLY ZERO KILLS THE PERCENTAGE AND NOT THE
    DIFFERENCE.** *A percentage change from nothing is not infinity, it is
    unanswerable* — `yoy_change`'s own words for `prior_year_zero` — but
    `+800 kWh more than July` is still a true sentence, so it is still served.
    """
    if this.unit != against.unit:
        return _no_change("mixed_units", this.period_month)
    difference = this.quantity - against.quantity  # type: ignore[operator]
    if against.quantity == 0:
        return PeriodChange(
            this_month=this.period_month,
            against_month=against.period_month,
            difference=difference,
            unit=this.unit,
            percent=None,
            direction=_direction_of(difference),
            absent_reason=reason_if_zero,
        )
    percent = difference / against.quantity * Decimal(100)  # type: ignore[operator]
    return PeriodChange(
        this_month=this.period_month,
        against_month=against.period_month,
        difference=difference,
        unit=this.unit,
        # CLAUDE.md rule 2: percentages are CARRIED at six places. The display
        # rounding to two is the read model's job, once, exactly as `yoy` does it.
        percent=percent.quantize(Decimal(1).scaleb(-PERCENT_PLACES)),
        direction=_direction_of(difference),
        absent_reason=None,
    )


def month_on_month(points: Sequence[MonthPoint]) -> PeriodChange:
    """`CPB-07` — the latest stated month against the one before it.

    The blueprint's sentence is *"The Usage screen reads '5% less than July'
    under the big number, and a clerk looking at the same account sees the same
    5%."* The second half is why this arithmetic is HERE: `monthly_usage_reads`
    serves it to the staff Usage tab and, through the portal's metering seam,
    to `CWP-033`, so there is one subtraction and not two.

    ⚠ **AN ABSENT MONTH IS SKIPPED AND THE ANSWER NAMES WHAT IT ACTUALLY
    USED.** `BR-MET-106` makes an unread month ABSENT rather than `0`, so
    subtracting from the month before regardless would tell a customer they
    used nothing in a month nobody walked. Walking back to the nearest month
    that HAS a figure and reporting `against_month` is the only reading that
    invents no data — the screen names the month, so *5% less than June* is
    unambiguous where a bare *5% less than last month* would not be.
    **Recorded 2026-09-08 rather than put to the Product Owner (hard-won law
    13): nothing signed rules it and it collides with no signed rule.**
    """
    present = [p for p in points if p.present]
    if not present:
        return _no_change("no_current_reads")
    latest = present[-1]
    if len(present) < 2:
        return _no_change("no_earlier_month", latest.period_month)
    return _compare(latest, present[-2], "earlier_month_zero")


def same_month_last_year(points: Sequence[MonthPoint]) -> PeriodChange:
    """`CPB-06` — the latest stated month against the SAME month a year before.

    The blueprint's sentence is *"The Usage screen reads '800 kWh · 86 kWh more
    than August 2025' beside the chart, rather than the sentence saying there
    is nothing to compare with."*

    ⚠ **IT IS THE SAME CALENDAR MONTH OR IT IS NOTHING.** This comparison
    exists because usage is SEASONAL — an August against an August holds the
    weather roughly still, which is the entire reason a customer asks it. July
    2025 is not an answer to *how does this August compare*, so an absent
    August 2025 is REPORTED (`no_same_month_last_year`) and never substituted
    with the nearest month to hand. That is the opposite choice from
    `month_on_month` above and it is deliberate: there, the nearest earlier
    month IS the question; here, only one month is.

    ⚠ **DIFFERENT FROM `yoy_change`, WHICH IS TWELVE MONTHS AGAINST TWELVE.**
    `yoy_change` answers *is this year heavier than last year* and is unchanged;
    this answers *is this August heavier than last August*. The decision log of
    2026-09-04 recorded that the product implements only the first and that
    *"whoever wants the drawing's number must change the ARITHMETIC or the
    DRAWING, not the fixture"* — this is that arithmetic.
    """
    present = [p for p in points if p.present]
    if not present:
        return _no_change("no_current_reads")
    latest = present[-1]
    wanted = date(latest.period_month.year - 1, latest.period_month.month, 1)
    against = next((p for p in present if p.period_month == wanted), None)
    if against is None:
        return _no_change("no_same_month_last_year", latest.period_month)
    return _compare(latest, against, "same_month_last_year_zero")


def window_months(latest: date, count: int) -> list[date]:
    """The `count` calendar months ending at `latest`, oldest first.

    The chart's x-axis. It is built from the CALENDAR and not from the rows,
    which is the only way an unread month can be drawn as absent at all — a
    window derived from the rows contains no gaps by construction.
    """
    months: list[date] = []
    year, month = latest.year, latest.month
    for _ in range(count):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-011@a1fbf3f (the S21 operational tabs; BR-MET-106 snapshot 2026-08-24)
# generated: 2026-08-24 by the CR-030 W3 task 3.8 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — this module is rules only; the endpoint is in api.py) E=deferred(no-frontend-half — AccountUsageTab.tsx is the same lane's separate file) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_br_met_106_monthly_usage.py · run_gates no new failure
# exceptions: E3 `MixedUnitMonth` subclasses NotImplementedError rather than raising a catalog BizError — an unruled case is a STUB (prime directive), not a refusal the product has decided to make · E3 r10's `+8.2%` YoY is screen copy over a fixture this repo does not hold; the strip computes the figure from the account's own months and displays it at 2 dp per hard rule 2, so a real account will not print 1 dp
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
