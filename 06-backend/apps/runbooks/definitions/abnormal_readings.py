# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-020 (EP-RBS-05) — CR-075 wave S: runbook 5, *Abnormal
#           readings* — eight read steps over each meter's own twelve months,
#           ranked by revenue at risk.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-009 ·
#           BR-RBS-010 · BR-RBS-011 · BR-RBS-019 (the unit is the METER, never
#           the read) · BR-RBS-020 · BR-RBS-021 · BR-RBS-022 (a work item is the
#           ENGINE's act) · BR-RBS-023 · BR-RBS-035 · BR-RBS-039 · RBR-09
#           (every threshold is relative to the meter's OWN history) ·
#           BR-MET-016 / BR-MET-053 (committed lineage heads only) ·
#           CLAUDE.md hard rule 2 (money 4 stored / 2 shown) · hard rule 3 (a
#           quantity carries its unit) · B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_020_abnormal_readings.py ·
#           06-backend/tests/test_rbs_check_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py · apps/runbooks/seams/
#           metering_seam.py · apps/runbooks/seams/customers_seam.py ·
#           apps/runbooks/seams/billing_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-105-abnormal-readings.md
# ───────────────────────────────────────────────────────
"""Runbook 5 — **Abnormal readings**.

*Which meters are behaving oddly, by pattern, over the last year?* Grouped by
the kind of oddness and ranked by revenue at risk.

⚠ **EVERY THRESHOLD IS RELATIVE TO THE METER'S OWN HISTORY, NEVER TO A FLEET
AVERAGE** (`RBR-09`, and the card's own *Why the card reads this way*): *"A
restaurant and a retired couple are both normal at wildly different volumes; a
fixed threshold would flag one and miss the other."* The seam this runbook reads
returns rows per meter and computes no summary at all, precisely so breaking
that rule is not the easy path.

THE UNIT OF WORK IS THE METER AND NOT THE READ
------------------------------------------------
`BR-RBS-019`. The card's own scope line is *2,842 meters with 31,904 reads*: one
record per meter, one savepoint per meter, and the twelve periods are computed
inside it. A runbook that walked the read would be correct and unusable.

WHAT *REVENUE AT RISK* IS, AND WHY IT IS AN ESTIMATE WITH ITS METHOD STATED
----------------------------------------------------------------------------
The card ranks by money and shows *$1,180.00* against a flat-lined apartment
block. **Nothing in this product prices unmeasured usage**, and this Check may
not: pricing is billing's act and a Check holds no writer at all. So the figure
is built from two measured facts and its method is written on the screen:

    at risk  =  the units this meter did NOT record
                × what this account last PAID per unit for that service

The second half comes from the account's most recent issued bill — the usage
lines' amount over their quantity — so it is a price the customer has actually
been charged rather than a tariff this runbook looked up and re-interpreted.
**A meter whose account has never billed has no price**, and its row reads `—`
rather than `$0.00`: an unknown is not a zero, and a zero would sort it to the
bottom of a list ranked by money.

⚠ **ONLY THREE PATTERNS CARRY MONEY, WHICH IS THE CARD'S OWN TABLE.** A flat
line and a zero streak are under-billing; a spike is over-billing. A rollover
and an over-estimated meter carry **$0.00** — exactly as `RB-105`'s worked run
shows them (*WM-00517 · ↺ Rollover · Aug · $0.00* and *WM-03390 · ≈ Estimated ·
6 of 12 · $0.00*) — because neither says how much was mis-measured.

WHAT THIS RUNBOOK CANNOT SEE, EACH WITH ITS NUMBER
----------------------------------------------------
1. **Out of season needs more than twelve months** (step 7). With a
   twelve-month window a meter has exactly one same-month sample, and one
   sample is not a history. The step reports how many meters HAD a comparison
   rather than reporting *"none out of season"* over a question nobody could
   ask.
2. **A period is the gap between two committed reads**, so a meter with one
   read has no period at all and cannot be judged. Those are counted as
   *too little history* rather than as *normal*.
3. **`Ignore usage under` carries no unit of its own.** The card's value is
   *200 gal*, and the unit belongs to the METER's own readings (hard rule 3), so
   the threshold is compared against each meter's quantities in ITS unit and the
   unit is reported beside the count. A tenant billing water in kgal and gas in
   ccf sets one number that means two things, which is stated rather than
   silently averaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_INTEGER,
    PARAM_PERCENT,
    PARAM_WINDOW,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import billing_seam, customers_seam, metering_seam, tenancy_seam

KEY = "abnormal_readings"

ZERO = Decimal("0")

# ── the eight steps, in the card's own order ──────────────────────────────

STEP_YEAR = "build_each_meters_year"
STEP_SPIKES = "spikes"
STEP_DROPS = "drops_and_zeros"
STEP_FLAT = "flat_lines"
STEP_ROLLOVER = "rollovers_and_negatives"
STEP_ESTIMATED = "over_estimated"
STEP_SEASON = "out_of_season"
STEP_RANK = "rank_by_revenue_at_risk"

STEP_LABELS = {
    STEP_YEAR: "Build each meter's year",
    STEP_SPIKES: "Spikes",
    STEP_DROPS: "Drops and zeros",
    STEP_FLAT: "Flat lines",
    STEP_ROLLOVER: "Rollovers and negatives",
    STEP_ESTIMATED: "Over-estimated",
    STEP_SEASON: "Out of season",
    STEP_RANK: "Rank by revenue at risk",
}

# ── the six patterns, in the card's own order ─────────────────────────────

PATTERN_SPIKE = "spike"
PATTERN_FLAT = "flat"
PATTERN_ZERO = "zero"
PATTERN_ESTIMATED = "estimated"
PATTERN_ROLLOVER = "rollover"
PATTERN_SEASON = "out_of_season"
PATTERN_NORMAL = "normal"
PATTERN_TOO_LITTLE = "too_little_history"

#: What a clerk calls each pattern. ⚠ **THE WORD IS THE SIGNAL AND THE COLOUR IS
#: NOT** — `RB-105`: *"the pattern is named in words beside it, so the colour is
#: never the only signal."*
PATTERN_LABELS = {
    PATTERN_SPIKE: "Spike",
    PATTERN_FLAT: "Flat",
    PATTERN_ZERO: "Zero",
    PATTERN_ESTIMATED: "Estimated",
    PATTERN_ROLLOVER: "Rollover",
    PATTERN_SEASON: "Out of season",
    PATTERN_NORMAL: "Normal",
    PATTERN_TOO_LITTLE: "Too little history",
}

#: The order a meter's patterns are reduced to ONE for its row. ⚠ A meter can
#: match several — a stuck meter reads flat AND zero — and the table is one row
#: per meter, so the FIRST match in this order wins and the rest travel in the
#: row's `meta`. The order is the card's chip row: the pattern that costs money
#: first, then the ones that do not.
PATTERN_ORDER = (
    PATTERN_FLAT,
    PATTERN_ZERO,
    PATTERN_SPIKE,
    PATTERN_ROLLOVER,
    PATTERN_ESTIMATED,
    PATTERN_SEASON,
)

#: What a clerk does about each — `BR-RBS-011`, and every route is one this
#: product mounts (verified against `07-frontend/src/routing/`, 2026-09-07).
FIX_READS = "reads"
FIX_ASSETS = "assets"
FIX_ACCOUNTS = "accounts"

FIX_FOR_PATTERN = {
    PATTERN_FLAT: (FIX_ASSETS, "Order a test →"),
    PATTERN_ZERO: (FIX_ACCOUNTS, "Confirm vacancy →"),
    PATTERN_SPIKE: (FIX_ACCOUNTS, "Check for leak →"),
    PATTERN_ROLLOVER: (FIX_READS, "Confirm rollover →"),
    PATTERN_ESTIMATED: (FIX_READS, "Fix access →"),
    PATTERN_SEASON: (FIX_READS, "Compare the year →"),
    PATTERN_NORMAL: (FIX_READS, "Open the reads →"),
    PATTERN_TOO_LITTLE: (FIX_READS, "Open the reads →"),
}


@dataclass
class _StepResult:
    found: dict[str, Any] = field(default_factory=dict)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"reached": True, "found": dict(self.found), "checked": dict(self.checked)}


# ── numbers ───────────────────────────────────────────────────────────────


def _decimal(raw: Any) -> Decimal | None:
    """A stored quantity or money string as a `Decimal`, or `None`.

    ⚠ **`None` IS NOT ZERO ANYWHERE IN THIS FILE.** A read with no consumption
    is an estimate or an unmeasured row; counting it as `0` would manufacture a
    zero streak out of a gap in the data and send a crew to confirm a vacancy
    at an occupied house.
    """
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _stored(amount: Decimal) -> str:
    """Money as it is STORED — four decimals (hard rule 2)."""
    return str(amount.quantize(Decimal("0.0001")))


def _median(values: list[Decimal]) -> Decimal | None:
    """The meter's OWN median. `None` where there is nothing to take one of.

    ⚠ **THE MEDIAN AND NOT THE MEAN, WHICH IS `RB-105`'s WHOLE POINT.** One
    spike drags a mean far enough to hide the next one; a median of twelve
    periods is unmoved by a single month. `RBR-09` says *relative to the meter's
    own history*, and this is that history's middle.
    """
    usable = sorted(one for one in values if one is not None)
    if not usable:
        return None
    middle = len(usable) // 2
    if len(usable) % 2:
        return usable[middle]
    return (usable[middle - 1] + usable[middle]) / 2


# ── step 1 · each meter's year ────────────────────────────────────────────


def _history(ctx) -> list[dict[str, Any]]:
    """The fleet's committed reads, read ONCE per run and cached.

    ⚠ **ONE QUERY FOR THE ESTATE, NOT ONE PER METER.** `NFR-3` binds every list
    this product adds and the ICP's top is 40,000 accounts; a per-meter read is
    correct at 3,000 and 13× short at 40,000 (`DEF-PAY-4221`'s shape).
    """
    cached = ctx.set_results.get("_history")
    if cached is None:
        cached = metering_seam.meter_read_history(
            service_code=str(ctx.params.get("service") or "") or None,
            since=_window_start(ctx),
            limit_per_meter=int(ctx.params.get("periods") or 12) + 1,
        )
        ctx.set_results["_history"] = cached
    return list(cached)


def _window_start(ctx):
    """The first day this run's reads may come from — the tenant's OWN today.

    ⚠ **`BR-TEN-043`: THE BUSINESS DATE IS AN INPUT AND NOT A CLOCK A RUNBOOK
    READS.** A run re-taken for last quarter must take last quarter's answer.
    """
    months = int(ctx.params.get("window_months") or 12)
    today = tenancy_seam.today()
    year = today.year - (1 if today.month <= months % 12 or months >= 12 else 0)
    month = today.month - (months % 12)
    if month <= 0:
        month += 12
    if months >= 12:
        year = today.year - (months // 12)
    return today.replace(year=year, month=month, day=1)


def _periods(meter: dict[str, Any]) -> list[dict[str, Any]]:
    """One meter's year, oldest first — **a period is a gap between two reads**.

    ⚠ **THE CONSUMPTION IS METERING'S, NEVER RE-DERIVED HERE.**
    `meter_reads.consumption` is `(current − prior) × multiplier`, unrounded,
    computed by the module that owns the meter and the multiplier
    (`BR-MET-056`). A runbook that subtracted two register values itself would
    be a second implementation of a money-path calculation, living where
    metering's reviewers never read it.
    """
    out: list[dict[str, Any]] = []
    for read in meter.get("reads") or []:
        out.append(
            {
                "on": read.get("on"),
                "quantity": _decimal(read.get("consumption")),
                "register": _decimal(read.get("current_value")),
                "unit": read.get("unit"),
                "estimated": bool(read.get("estimated")),
            }
        )
    return out


def step_build_each_meters_year(ctx, subjects) -> dict[str, Any]:
    """1 · Twelve periods, actual and estimated marked.

    Every later step reads what this one built, so the fleet's history is walked
    once and every threshold below is compared against the SAME twelve periods.
    """
    history = {str(one["asset_id"]): one for one in _history(ctx)}
    years: dict[str, dict[str, Any]] = {}
    reads = 0
    too_little = 0
    for subject in subjects:
        meter = history.get(str(subject.subject_id))
        if meter is None:
            continue
        periods = _periods(meter)
        reads += len(periods)
        measured = [one["quantity"] for one in periods if one["quantity"] is not None]
        if len(measured) < 2:
            too_little += 1
        years[str(subject.subject_id)] = {
            "asset_no": meter.get("asset_no"),
            "service": meter.get("service"),
            "unit_id": meter.get("unit_id"),
            "unit": next((one["unit"] for one in periods if one["unit"]), ""),
            "periods": periods,
            "median": _median(measured),
            "measured_periods": len(measured),
            "estimated_periods": len([one for one in periods if one["estimated"]]),
        }
    return _StepResult(
        found={"years": years},
        checked={
            "meters": len(years),
            "reads": reads,
            "meters_with_too_little_history": too_little,
            "window_starts": _window_start(ctx).isoformat(),
            "consumption_is": "metering's own figure, never re-derived here",
        },
    ).as_dict()


def _years(ctx_or_view) -> dict[str, dict[str, Any]]:
    return ((ctx_or_view.set_results.get(STEP_YEAR) or {}).get("found") or {}).get("years") or {}


def _floor(ctx) -> Decimal:
    """`Ignore usage under` — the card's *200 gal*.

    ⚠ **IT EXISTS SO A VACANT UNIT AT 40 GALLONS A MONTH DOES NOT PRODUCE
    SPECTACULAR PERCENTAGES THAT MEAN NOTHING**, which is the card's own reason.
    """
    # ⚠ **THE FALLBACK IS THE DECLARED DEFAULT, NOT ZERO.** `run_parameters`
    # merges every declared default before a real run starts, so this only
    # fires when a caller builds a context by hand — and a zero floor there
    # would turn *"ignore a vacant unit at 40 gallons"* into *"flag everything"*
    # in exactly the harness a lane tests with.
    return _decimal(ctx.params.get("ignore_usage_under")) or Decimal("200")


# ── steps 2 to 7 · the six patterns ───────────────────────────────────────


def step_spikes(ctx, subjects) -> dict[str, Any]:
    """2 · Above 300% of the meter's OWN median.

    ⚠ **A METER WITH NO MEDIAN IS NOT A SPIKE, IT IS UNJUDGEABLE.** A first
    build that treated `None` as `0` would find every meter's first month
    infinitely above its median — a fleet-wide alert on the day a utility goes
    live.
    """
    above = _decimal(ctx.params.get("spike_above_own_median")) or Decimal("300")
    floor = _floor(ctx)
    found: dict[str, dict[str, Any]] = {}
    unjudgeable = 0
    for asset_id, year in _years(ctx).items():
        median = year["median"]
        if median is None or median <= ZERO:
            unjudgeable += 1
            continue
        for index, period in enumerate(year["periods"]):
            quantity = period["quantity"]
            if quantity is None or quantity < floor:
                continue
            if quantity * Decimal(100) > median * above:
                found[asset_id] = {
                    "at": index,
                    "on": period["on"],
                    "quantity": str(quantity),
                    "median": str(median),
                    "unit": year["unit"],
                }
    return _StepResult(
        found={"spikes": found},
        checked={
            "threshold_percent_of_own_median": str(above),
            "meters_spiking": len(found),
            "meters_with_no_median_to_judge": unjudgeable,
            "ignore_usage_under": str(floor),
        },
    ).as_dict()


def step_drops_and_zeros(ctx, subjects) -> dict[str, Any]:
    """3 · Below 20% of its own median, **or three zero reads running**.

    Two findings in one step because the card puts them in one step, and they
    are the same question asked at two depths: a meter that fell and a meter
    that stopped.
    """
    below = _decimal(ctx.params.get("drop_below_own_median")) or Decimal("20")
    zeros_needed = int(ctx.params.get("zero_reads_in_a_row") or 3)
    floor = _floor(ctx)
    drops: dict[str, dict[str, Any]] = {}
    zeros: dict[str, dict[str, Any]] = {}
    for asset_id, year in _years(ctx).items():
        median = year["median"]
        run = 0
        best = 0
        first_zero = None
        for index, period in enumerate(year["periods"]):
            quantity = period["quantity"]
            if quantity is not None and quantity == ZERO:
                run += 1
                if run == 1:
                    first_zero = index
                best = max(best, run)
            else:
                run = 0
        if best >= zeros_needed:
            zeros[asset_id] = {
                "at": first_zero,
                "in_a_row": best,
                "on": year["periods"][first_zero]["on"] if first_zero is not None else None,
            }
            continue
        if median is None or median <= floor:
            continue
        for index, period in enumerate(year["periods"]):
            quantity = period["quantity"]
            if quantity is None or quantity == ZERO:
                continue
            if quantity * Decimal(100) < median * below:
                drops[asset_id] = {
                    "at": index,
                    "on": period["on"],
                    "quantity": str(quantity),
                    "median": str(median),
                    "unit": year["unit"],
                }
                break
    return _StepResult(
        found={"drops": drops, "zeros": zeros},
        checked={
            "threshold_percent_of_own_median": str(below),
            "zero_reads_in_a_row": zeros_needed,
            "meters_dropping": len(drops),
            "meters_with_a_zero_streak": len(zeros),
        },
    ).as_dict()


def step_flat_lines(ctx, subjects) -> dict[str, Any]:
    """4 · Four identical reads — a stuck meter.

    ⚠ **IDENTICAL AND NON-ZERO.** Four zeros are a zero streak, which step 3
    already found and which means something different: a stuck meter is still
    reporting a number, and a vacant house is not. Counting them here as well
    would double-count the same meter under two patterns that carry two
    different fixes.
    """
    needed = int(ctx.params.get("identical_reads_in_a_row") or 4)
    found: dict[str, dict[str, Any]] = {}
    for asset_id, year in _years(ctx).items():
        run = 1
        previous: Decimal | None = None
        started = 0
        for index, period in enumerate(year["periods"]):
            quantity = period["quantity"]
            if quantity is None or quantity == ZERO:
                run, previous = 1, None
                continue
            if previous is not None and quantity == previous:
                run += 1
            else:
                run, started = 1, index
            previous = quantity
            if run >= needed:
                found[asset_id] = {
                    "at": started,
                    "in_a_row": run,
                    "quantity": str(quantity),
                    "unit": year["unit"],
                }
    return _StepResult(
        found={"flat": found},
        checked={"identical_reads_in_a_row": needed, "meters_flat": len(found)},
    ).as_dict()


def step_rollovers_and_negatives(ctx, subjects) -> dict[str, Any]:
    """5 · A read lower than the one before.

    ⚠ **THE REGISTER, NOT THE CONSUMPTION.** A meter rolls over when its DIAL
    passes its maximum and starts again, so the fact is a `current_value` lower
    than the previous one. Consumption is already `(current − prior) ×
    multiplier` and metering's own estimation may have made it positive; asking
    the derived figure would miss the very case this step exists for.
    """
    found: dict[str, dict[str, Any]] = {}
    for asset_id, year in _years(ctx).items():
        previous: Decimal | None = None
        for index, period in enumerate(year["periods"]):
            register = period["register"]
            if register is None:
                continue
            if previous is not None and register < previous:
                found[asset_id] = {
                    "at": index,
                    "on": period["on"],
                    "from": str(previous),
                    "to": str(register),
                }
                break
            previous = register
    return _StepResult(
        found={"rollovers": found},
        checked={
            "meters_rolling_over": len(found),
            "compared_on": "the register reading, never the consumption",
        },
    ).as_dict()


def step_over_estimated(ctx, subjects) -> dict[str, Any]:
    """6 · More than four of twelve estimated."""
    limit = int(ctx.params.get("estimated_more_than") or 4)
    found: dict[str, dict[str, Any]] = {}
    for asset_id, year in _years(ctx).items():
        if year["estimated_periods"] > limit:
            found[asset_id] = {
                "estimated": year["estimated_periods"],
                "of": len(year["periods"]),
            }
    return _StepResult(
        found={"estimated": found},
        checked={"estimated_more_than": limit, "meters_over_estimated": len(found)},
    ).as_dict()


def step_out_of_season(ctx, subjects) -> dict[str, Any]:
    """7 · Against the meter's own same-month history.

    ⚠ **WITH A TWELVE-MONTH WINDOW THERE IS EXACTLY ONE SAME-MONTH SAMPLE, AND
    ONE SAMPLE IS NOT A HISTORY.** So this reports how many meters HAD a
    comparison to make rather than reporting *"none out of season"* over a
    question that could not be asked — hard-won law 7's *reporting zero over a
    scope it silently excludes*, which is the shape that is hardest to see
    because the check is not lying.
    """
    found: dict[str, dict[str, Any]] = {}
    comparable = 0
    for asset_id, year in _years(ctx).items():
        by_month: dict[str, list[Decimal]] = {}
        for period in year["periods"]:
            if period["quantity"] is None or not period["on"]:
                continue
            by_month.setdefault(str(period["on"])[5:7], []).append(period["quantity"])
        pairs = {month: values for month, values in by_month.items() if len(values) > 1}
        if not pairs:
            continue
        comparable += 1
        for month, values in sorted(pairs.items()):
            newest, older = values[-1], _median(values[:-1])
            if older is None or older <= ZERO:
                continue
            if newest > older * Decimal(2) or newest * Decimal(2) < older:
                found[asset_id] = {
                    "month": month,
                    "now": str(newest),
                    "then": str(older),
                    "unit": year["unit"],
                }
                break
    return _StepResult(
        found={"out_of_season": found},
        checked={
            "meters_with_a_same_month_comparison": comparable,
            "meters_out_of_season": len(found),
            # The number beside the blind spot: a twelve-month window gives one
            # sample per month, and this says how many meters had two.
            "window_gives_one_sample_per_month": True,
        },
    ).as_dict()


# ── step 8 · the money, per meter ─────────────────────────────────────────


def _price_per_unit(account_id: Any, service: str) -> Decimal | None:
    """WHAT THIS ACCOUNT LAST PAID PER UNIT for this service, or `None`.

    Measured from the account's most recent ISSUED bill: the usage lines'
    amount over their quantity. It is a price the customer has actually been
    charged, not a tariff this runbook looked up and re-interpreted — which
    matters because re-interpreting a tariff is rating's job and this is a
    Check.

    `None` where the account has never billed, where the bill carries no usage
    line for the service, or where the quantity is zero. **`None` is never
    `0.0000`**: an unknown price sorts to the bottom of a list ranked by money
    and would hide the very meter a clerk should see first.
    """
    if not account_id or not service:
        return None
    bills = billing_seam.issued_bills_for_account(account_id, limit=1)
    if not bills:
        return None
    amount = quantity = ZERO
    for line in bills[0].get("lines") or []:
        if str(line.get("kind")) != "usage" or str(line.get("service") or "") != service:
            continue
        this_quantity = _decimal(line.get("quantity"))
        if this_quantity is None or this_quantity <= ZERO:
            continue
        amount += _decimal(line.get("amount")) or ZERO
        quantity += this_quantity
    if quantity <= ZERO:
        return None
    return amount / quantity


def _pattern_of(ctx_or_view, asset_id: str) -> tuple[str, dict[str, Any], list[str]]:
    """The ONE pattern this meter's row carries, and every one it matched.

    A stuck meter reads flat AND zero; the table is one row per meter, so the
    first match in `PATTERN_ORDER` wins and the others travel in `meta`.
    """
    hits: dict[str, dict[str, Any]] = {}
    steps = (
        (STEP_FLAT, "flat", PATTERN_FLAT),
        (STEP_DROPS, "zeros", PATTERN_ZERO),
        (STEP_SPIKES, "spikes", PATTERN_SPIKE),
        (STEP_ROLLOVER, "rollovers", PATTERN_ROLLOVER),
        (STEP_ESTIMATED, "estimated", PATTERN_ESTIMATED),
        (STEP_SEASON, "out_of_season", PATTERN_SEASON),
    )
    for step, key, pattern in steps:
        rows = ((ctx_or_view.set_results.get(step) or {}).get("found") or {}).get(key) or {}
        if asset_id in rows:
            hits[pattern] = rows[asset_id]
    for pattern in PATTERN_ORDER:
        if pattern in hits:
            return pattern, hits[pattern], sorted(hits)
    return PATTERN_NORMAL, {}, []


def step_rank_by_revenue_at_risk(ctx, subject) -> dict[str, Any]:
    """8 · Under-billed first, then over-billed — one record per meter.

    ⚠ **THE ONLY PER-RECORD STEP, AND IT IS WHERE THE MONEY IS COMPUTED.** One
    meter, one savepoint (hard-won law 14), one row on the screen. The ORDER the
    card asks for is applied when the report is composed, because a per-record
    step sees one meter and cannot rank anything — stated here so the next
    reader does not go looking for a sort that is not in this function.
    """
    asset_id = str(subject.subject_id)
    year = _years(ctx).get(asset_id) or {}
    pattern, detail, every = _pattern_of(ctx, asset_id)
    unit = year.get("unit") or ""
    median = year.get("median")
    account_id = (ctx.set_results.get("_accounts") or {}).get(asset_id)
    at_risk: Decimal | None = None
    missing: Decimal | None = None
    price: Decimal | None = None

    if not year.get("periods"):
        pattern = PATTERN_TOO_LITTLE
    elif pattern in (PATTERN_FLAT, PATTERN_ZERO, PATTERN_SPIKE) and median is not None:
        months = int(detail.get("in_a_row") or 1)
        if pattern == PATTERN_SPIKE:
            # Over-billed: what was charged above this meter's own normal.
            missing = (_decimal(detail.get("quantity")) or ZERO) - median
        else:
            # Under-billed: the months it did not measure, at its own normal.
            missing = median * Decimal(months)
        price = _price_per_unit(account_id, str(year.get("service") or ""))
        if price is not None and missing is not None:
            at_risk = (missing * price).copy_abs()

    route, label = FIX_FOR_PATTERN.get(pattern, FIX_FOR_PATTERN[PATTERN_NORMAL])
    return {
        "outcome": pattern,
        "reason": _pattern_words(pattern, detail, unit),
        "decided_by_rule": (
            "Every threshold is measured against this meter's own history"
        ),
        "fix_route": route,
        "data": {
            "asset_no": year.get("asset_no"),
            "service": year.get("service"),
            "unit": unit,
            "fix_label": label,
            "pattern": pattern,
            "also_matched": every,
            "at": _mark_at(year, detail.get("at")),
            # ⚠ **MEASURED PERIODS ONLY, AND A `None` IS NOT PLOTTED AS ZERO.**
            # A meter's first read has no prior and therefore no consumption, so
            # a list that turned every `None` into `0.0` drew a dive to the floor
            # on the left of every sparkline in the fleet — a shape a clerk
            # reads as *"it stopped"* over a meter that had simply just been
            # installed. `Sparkline` takes numbers and cannot express a gap, so
            # the gap is left out and counted instead.
            "points": [
                float(one["quantity"])
                for one in (year.get("periods") or [])
                if one["quantity"] is not None
            ],
            "periods_with_no_reading": len(
                [one for one in (year.get("periods") or []) if one["quantity"] is None]
            ),
            "estimated_periods": year.get("estimated_periods", 0),
            "at_risk": None if at_risk is None else _stored(at_risk),
            "units_at_risk": None if missing is None else str(missing),
            "price_per_unit": None if price is None else _stored(price),
            "over_billed": pattern == PATTERN_SPIKE,
        },
    }


def _mark_at(year: dict[str, Any], index: Any) -> int | None:
    """Translate a period index into the SPARKLINE's index.

    The sparkline plots measured periods only (see `points`), so the dot that
    marks the spike has to be counted in the same list. Marking the raw index
    would put the dot on the wrong month whenever a meter has a gap — and the
    dot IS the finding.
    """
    if index is None:
        return None
    periods = year.get("periods") or []
    if index >= len(periods):
        return None
    return len([one for one in periods[:index] if one["quantity"] is not None])


def _pattern_words(pattern: str, detail: dict[str, Any], unit: str) -> str:
    """What the row says, in words a clerk reads — never a code (B14 rule 32)."""
    if pattern == PATTERN_FLAT:
        return f"{detail.get('in_a_row', 0)} identical reads in a row."
    if pattern == PATTERN_ZERO:
        return f"{detail.get('in_a_row', 0)} zero reads in a row."
    if pattern == PATTERN_SPIKE:
        return f"Used {detail.get('quantity')} {unit} against a usual {detail.get('median')}."
    if pattern == PATTERN_ROLLOVER:
        return "The dial went backwards."
    if pattern == PATTERN_ESTIMATED:
        return f"{detail.get('estimated', 0)} of {detail.get('of', 0)} reads estimated."
    if pattern == PATTERN_SEASON:
        return f"Far from this meter's own usual for that month."
    if pattern == PATTERN_TOO_LITTLE:
        return "Not enough readings yet to judge."
    return "Nothing unusual."


# ── the report ────────────────────────────────────────────────────────────


def _columns() -> list[dict[str, Any]]:
    return [
        {"key": "meter", "label": "Meter"},
        {"key": "account", "label": "Account"},
        {"key": "pattern", "label": "Pattern"},
        {"key": "year", "label": "Twelve months"},
        {"key": "at_risk", "label": "At risk", "numeric": True, "sortable": True},
        {"key": "fix", "label": "Fix"},
    ]


def report(view) -> list[Block]:
    """`RB-105`'s own blocks — **KPIs · Records (sparkline) · Action ·
    Downloads** — plus the verdict the header consumes.

    ⚠ **THE DEFAULT SORT IS REVENUE AT RISK, AND IT IS APPLIED HERE.** The card:
    *"Default sort is revenue at risk, so the flat-lined apartment block is at
    the top rather than the vacant unit."* A meter whose price is unknown sorts
    after every priced one rather than with the zeros.
    """
    counted = view.set_results
    currency = str((counted.get("_currency") or "") or "")
    flagged = [
        record
        for record in view.records
        if record.outcome not in (PATTERN_NORMAL, PATTERN_TOO_LITTLE)
    ]
    by_pattern: dict[str, int] = {}
    for record in view.records:
        by_pattern[record.outcome] = by_pattern.get(record.outcome, 0) + 1

    total_at_risk = sum(
        (Decimal(record.data["at_risk"]) for record in flagged if record.data.get("at_risk")),
        ZERO,
    )
    unpriced = len([one for one in flagged if one.data.get("at_risk") is None])

    ranked = sorted(
        flagged,
        key=lambda record: (
            Decimal(record.data["at_risk"]) if record.data.get("at_risk") else Decimal("-1")
        ),
        reverse=True,
    )
    accounts = counted.get("_account_labels") or {}

    return [
        Block(
            block="verdict",
            payload={
                "word": "Worth a look" if flagged else "Nothing odd",
                "tone": "warning" if flagged else "success",
                "count": f"{len(flagged)} meters worth a look.",
                "detail": (
                    f"{len(view.records)} meters examined · "
                    f"{(counted.get(STEP_YEAR) or {}).get('checked', {}).get('reads', 0)} reads."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": pattern,
                        "label": PATTERN_LABELS[pattern],
                        "value": {"kind": "text", "text": str(by_pattern.get(pattern, 0))},
                    }
                    for pattern in PATTERN_ORDER
                ]
                + [
                    {
                        "id": "at_risk",
                        "label": "Revenue at risk",
                        # ⚠ **`—` WHEN NOTHING COULD BE PRICED, NEVER `0.00`.**
                        # A money tile reading zero over a list where no account
                        # has ever billed is hard-won law 7's *reporting zero
                        # over a scope it silently excludes*: the check is not
                        # lying and the reader is still misled.
                        "value": (
                            {
                                "kind": "money",
                                "amount": _stored(total_at_risk),
                                "currency": currency,
                            }
                            if flagged and unpriced < len(flagged)
                            else {"kind": "text", "text": "—"}
                        ),
                        # ⚠ `priced` AND NOT `posting` — this money was never
                        # posted anywhere. It is an estimate priced from what
                        # each account last paid per unit, and a tile labelled
                        # *Posting date* over it is `DEF-RBS-4350` exactly.
                        "basis": "priced",
                        "detail": (
                            f"{unpriced} of {len(flagged)} could not be priced"
                            if unpriced
                            else "At what each account last paid per unit"
                        ),
                    },
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _columns(),
                "rows": [
                    {
                        "id": f"meter-{index}",
                        "cells": {
                            "meter": {
                                "kind": "text",
                                "text": str(record.data.get("asset_no") or ""),
                            },
                            "account": {
                                "kind": "text",
                                "text": str(
                                    accounts.get(str(record.subject.subject_id)) or "—"
                                ),
                            },
                            "pattern": {
                                "kind": "text",
                                "text": PATTERN_LABELS.get(record.outcome, record.outcome),
                            },
                            "year": {
                                "kind": "sparkline",
                                "points": list(record.data.get("points") or []),
                                # Hard rule 3 — the label carries the unit.
                                "label": (
                                    f"{record.data.get('service') or 'Usage'} · "
                                    f"{record.data.get('unit') or ''}"
                                ).strip(" ·"),
                                "source": (
                                    "estimated"
                                    if record.data.get("estimated_periods")
                                    else "read"
                                ),
                                **(
                                    {"markAt": record.data["at"]}
                                    if record.data.get("at") is not None
                                    else {}
                                ),
                            },
                            "at_risk": (
                                {
                                    "kind": "money",
                                    "amount": record.data["at_risk"],
                                    "currency": currency,
                                }
                                if record.data.get("at_risk")
                                # ⚠ AN EM DASH AND NEVER `0.00`. An unknown price
                                # is not a zero risk, and a zero would sort this
                                # meter to the bottom of a money-ranked list.
                                else {"kind": "text", "text": "—"}
                            ),
                            "fix": {
                                "kind": "link",
                                "label": str(record.data.get("fix_label") or "Open →"),
                                "to": record.fix_route,
                            },
                        },
                        "meta": {
                            "decided_by_rule": record.decided_by_rule,
                            "pattern": record.outcome,
                            "also_matched": ", ".join(record.data.get("also_matched") or []),
                            "why": record.reason,
                        },
                    }
                    for index, record in enumerate(ranked, start=1)
                ],
                "total": len(ranked),
                "chips": [
                    {"id": "all", "label": "All", "count": len(flagged)},
                ]
                + [
                    {
                        "id": pattern,
                        "label": PATTERN_LABELS[pattern],
                        "count": by_pattern.get(pattern, 0),
                    }
                    for pattern in PATTERN_ORDER
                    if by_pattern.get(pattern)
                ],
                "empty": {
                    "title": "Every meter looks normal.",
                    "helper": (
                        f"{len(view.records)} meters examined against their own histories."
                    ),
                },
            },
        ),
        Block(
            block="action",
            payload={
                "label": "Raise work items",
                "tier": "secondary",
                "enabled": False,
                # B14 rule 33 — five or six words.
                "reason": "The work list is not built yet",
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "all_flagged", "label": "All flagged", "format": "csv"},
                    {"id": "by_pattern", "label": "By pattern", "format": "csv"},
                ]
            },
        ),
    ]


# ── the guard and the pinned scope ────────────────────────────────────────

SAMPLE_KEYS = "_sample_meter_ids"


def _is_sample(ctx, subject) -> bool:
    """`BR-TEN-057`'s tag, read off the meter's own row.

    ⚠ **`RB-105`'s SCOPE ROWS DO NOT NAME A SAMPLE EXCLUSION AND THIS GUARD IS
    HERE ANYWAY — WHICH IS A DIVERGENCE, SO IT IS WRITTEN DOWN.** Runbooks 12,
    18 and 19 all carry *Never include: Sample*; this card's scope panel names
    Service, Window, Routes and Meter types and stops. `BR-RBS-014` binds only
    ACTIONS, so nothing forces it here either.
    **It is guarded because a demo meter's stuck reading is a finding about the
    seed rather than about the utility**, and because a guarded subject is still
    pinned and still COUNTED (`BR-RBS-012`, `BR-RBS-035`) — so the screen says
    *"126 sample meters excluded"* instead of quietly showing 126 findings
    nobody can act on.
    """
    return str(subject.subject_id) in (ctx.set_results.get(SAMPLE_KEYS) or frozenset())


def resolve(ctx):
    """The pinned set: **one subject per METER** (`BR-RBS-019`).

    ⚠ **THE COUNT ON THE SETUP SCREEN IS THIS FUNCTION'S ANSWER** — *"Matches
    2,842 meters with 31,904 reads"* — because `resolve()` is ONE function that
    also answers the count (`contract.RunbookDefinition`).

    ⚠ **RESOLVED ONCE AND FROZEN** (`BR-RBS-009`): a read that lands mid-run is
    not in this run's history and the fingerprint proves the set did not move.
    """
    history = metering_seam.meter_read_history(
        service_code=str(ctx.params.get("service") or "") or None,
        since=_window_start(ctx),
        limit_per_meter=int(ctx.params.get("periods") or 12) + 1,
    )
    ctx.set_results["_history"] = history
    ctx.set_results[SAMPLE_KEYS] = frozenset(
        str(one["asset_id"]) for one in history if one.get("is_sample")
    )
    # The account each meter's reads belong to, and its LABEL — B14 rule 31,
    # so the Account column reads a name rather than a handle.
    account_by_meter: dict[str, str] = {}
    for meter in history:
        for read in meter.get("reads") or []:
            if read.get("account_id"):
                account_by_meter[str(meter["asset_id"])] = str(read["account_id"])
                break
    # ⚠ **AND WHERE THE READ NAMES NO ACCOUNT, WALK THE METER'S UNIT.**
    # `meter_reads.account_id` is nullable, so a fleet whose reads were imported
    # without one would draw `—` in every Account cell — a column with a heading
    # and no content. One bulk read answers the whole estate.
    by_unit = customers_seam.accounts_for_units(
        [one.get("unit_id") for one in history if one.get("unit_id")]
    )
    for meter in history:
        asset_id = str(meter["asset_id"])
        if asset_id in account_by_meter:
            continue
        occupant = by_unit.get(str(meter.get("unit_id") or ""))
        if occupant:
            account_by_meter[asset_id] = str(occupant["id"])
    ctx.set_results["_accounts"] = account_by_meter
    labels: dict[str, str] = {}
    for asset_id, account_id in account_by_meter.items():
        facts = customers_seam.account_facts(account_id) or {}
        labels[asset_id] = str(facts.get("label") or facts.get("account_no") or "")
    ctx.set_results["_account_labels"] = labels
    ctx.set_results["_currency"] = tenancy_seam.currency()
    return [
        SubjectRef(
            subject_type="meter",
            subject_id=str(one["asset_id"]),
            # B14 rule 31 — the meter's NUMBER, never its id.
            label=str(one.get("asset_no") or ""),
        )
        for one in history
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Abnormal readings",
    kind=models.KIND_CHECK,
    category="reads",
    subject_type="meter",
    unit_of_work="a meter's twelve months",
    # The card's own trigger row: *Schedule · manual*.
    triggers=(models.TRIGGER_SCHEDULE, models.TRIGGER_MANUAL),
    tags=("Assets",),
    parameters=(
        Parameter(
            name="service",
            type=PARAM_ENUM,
            label="Service",
            # ⚠ **NO `choices` AND NO DOMAIN YET.** The list of services is the
            # TENANT's — eleven in the catalogue, some enabled — which is
            # `BR-RBS-042`'s `service` domain and wave `T`'s to attach. An enum
            # with choices typed here would be a second, drifting copy of the
            # service catalogue (`SignupWizard.tsx` and `ratingShared.tsx` are
            # what that costs: an eleventh service that never appears).
            choices=("water",),
            default="water",
        ),
        Parameter(
            name="window_months",
            type=PARAM_WINDOW,
            label="Window",
            default=12,
        ),
        Parameter(
            name="spike_above_own_median",
            type=PARAM_PERCENT,
            label="Spike above own median",
            # A STRING, never a float — this value lives in `jsonb` where no
            # column type can catch one (hard rule 2, and `Parameter` refuses).
            default="300.000000",
        ),
        Parameter(
            name="drop_below_own_median",
            type=PARAM_PERCENT,
            label="Drop below own median",
            default="20.000000",
        ),
        Parameter(
            name="zero_reads_in_a_row",
            type=PARAM_INTEGER,
            label="Zero reads in a row",
            default=3,
        ),
        Parameter(
            name="identical_reads_in_a_row",
            type=PARAM_INTEGER,
            label="Identical reads in a row",
            default=4,
        ),
        Parameter(
            name="estimated_more_than",
            type=PARAM_INTEGER,
            label="Estimated more than",
            default=4,
        ),
        Parameter(
            name="ignore_usage_under",
            type=PARAM_INTEGER,
            label="Ignore usage under",
            # ⚠ **NO UNIT ON THE PARAMETER, AND THAT IS A STATED GAP.** The card
            # reads *200 gal*; the eleven parameter types have no quantity type
            # and hard rule 3 says a quantity carries its unit. The threshold is
            # therefore compared in each METER's own unit and the unit is
            # reported beside the count — see the module docstring's third
            # blind spot.
            default=200,
        ),
    ),
    guards=(Guard(key="sample", label="Never include: Sample", applies=_is_sample),),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_YEAR, label=STEP_LABELS[STEP_YEAR], mode=MODE_SET, run=step_build_each_meters_year),
        Step(key=STEP_SPIKES, label=STEP_LABELS[STEP_SPIKES], mode=MODE_SET, run=step_spikes),
        Step(key=STEP_DROPS, label=STEP_LABELS[STEP_DROPS], mode=MODE_SET, run=step_drops_and_zeros),
        Step(key=STEP_FLAT, label=STEP_LABELS[STEP_FLAT], mode=MODE_SET, run=step_flat_lines),
        Step(
            key=STEP_ROLLOVER,
            label=STEP_LABELS[STEP_ROLLOVER],
            mode=MODE_SET,
            run=step_rollovers_and_negatives,
        ),
        Step(key=STEP_ESTIMATED, label=STEP_LABELS[STEP_ESTIMATED], mode=MODE_SET, run=step_over_estimated),
        Step(key=STEP_SEASON, label=STEP_LABELS[STEP_SEASON], mode=MODE_SET, run=step_out_of_season),
        # ⚠ THE ONLY PER-RECORD STEP — one meter, one savepoint, one row.
        Step(key=STEP_RANK, label=STEP_LABELS[STEP_RANK], mode=MODE_PER_RECORD, run=step_rank_by_revenue_at_risk),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-020 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_020_abnormal_readings.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G20
# exceptions: *revenue at risk* is an ESTIMATE with its method on screen — the units a meter did not record, priced at what that account last PAID per unit on its most recent issued bill; a meter whose account never billed reads `—` and never `$0.00` · only flat lines, zero streaks and spikes carry money, exactly as the card's own table shows (a rollover and an over-estimated meter are `$0.00` there) · *out of season* needs more than twelve months and the step reports how many meters had a same-month comparison rather than reporting none out of season · `Ignore usage under` carries no unit because the eleven parameter types have none, so it is compared in each meter's own unit · a sample guard is declared although this card's scope rows do not name one — recorded as a divergence in `_is_sample` · `service` is an enum with a single choice until wave `T` attaches `BR-RBS-042`'s tenant-resolved `service` domain
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
