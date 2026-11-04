# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-019 (EP-RBS-05) — CR-075 wave S: runbook 4, *Why is this bill
#           higher?* — seven read steps over one account and two bills, ranked
#           by the dollars each cause contributed.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-009
#           (scope resolved ONCE and pinned) · BR-RBS-010 (every record states
#           the rule that decided it, in words a clerk can read) · BR-RBS-011 (a
#           failure names its fix route) · BR-RBS-019 (the declared unit of
#           work) · BR-RBS-020 (the report is composed at close and frozen) ·
#           BR-RBS-021 (twelve blocks) · BR-RBS-023 (a step declares its mode) ·
#           BR-RBS-027 (a stopped run reads *Never reached* on every later step)
#           · BR-RBS-039 (every foreign read through a seam this module owns) ·
#           BR-BIL-004 (a draft is freely replaced; an ISSUED bill is what a
#           customer received) · BR-MET-056 (the multiplier USED is stored on
#           the read) · CLAUDE.md hard rule 2 (money 4 stored / 2 shown) · hard
#           rule 3 (a quantity carries its unit) · B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_019_why_higher.py ·
#           06-backend/tests/test_rbs_check_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/billing_seam.py ·
#           apps/runbooks/seams/metering_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-104-why-is-this-bill-higher.md
# ───────────────────────────────────────────────────────
"""Runbook 4 — **Why is this bill higher?**

The most common call a small utility takes, answered in one screen: two bills,
side by side, and an explanation **ranked by how much each cause contributed**.

⚠ **THE DELIVERABLE IS A SENTENCE A CLERK READS DOWN THE PHONE**, not a table.
`RB-104`'s design note: *"Read this aloud is the deliverable: it is written for
the phone, in the customer's own units, and it can be copied straight into a
note or a reply."* Everything else on the screen exists to let a clerk check it.

THE CAUSES SUM TO THE CHANGE, BY CONSTRUCTION — AND THE CARD HAD TO CORRECT
ITSELF ON EXACTLY THIS
---------------------------------------------------------------------------
`RB-104`'s own *Open questions* section records it: *"Corrected in this pass. The
ranked causes summed to $92.20 against a change of $82.20; they now sum to
$82.20 and agree with the side-by-side table."*

So the money-bearing causes here are **line-group deltas and nothing else** —
every line of both bills is folded into a group, the groups' deltas are the
causes, and their sum is the total change with no arithmetic left over. A cause
computed any other way (a re-priced usage figure, an apportioned tier estimate)
would produce a number that looks right and does not add up, which is the
failure the card already had once.

⚠ **A RATE CHANGE AND A METER CHANGE ARE REPORTED, NEVER PRICED.** Attributing
dollars to *the rate moved* needs the old usage re-priced under the new tariff,
and this Check does not re-price a customer's issued bill: `BR-BIL-004` makes an
issued bill the document they received, and a second arithmetic for it is a
second answer to *what do you owe*. Both rows therefore appear in the ranked
list carrying **$0.00 when nothing changed** — which is the card's own worked
example, *"Rate change (none between the two bills) $0.00"* — and, when
something DID change, a row that says so in words and states that its dollars
are already inside the usage lines above.

WHAT *NORMALISE FOR DAYS* IS FOR, AND WHY THE CARD SINGLES IT OUT
------------------------------------------------------------------
`RB-104`: *"Normalise for days matters more than it looks: a 34-day period
against a 28-day one explains a surprising share of 'my bill went up' calls on
its own."* With the toggle on, the usage comparison also reports what the same
daily rate would have produced over the OTHER period's length, so a clerk can
say *"six of those extra days are why"* instead of arguing about gallons.

⚠ **THE WITHDRAWN SWITCH — DO NOT BUILD IT.** The card draws a fourth parameter,
*Write to account notes*, struck through and marked **WITHDRAWN, do not build**:
a Check is constructed with no writer (`BR-RBS-002`), and adding the explanation
to the account's notes is the clerk's act from the result screen, performed by
the customers module. ⚠ **AND THE QUESTION BEHIND IT HAS SINCE BEEN ANSWERED IN
A WAY THAT DOES *NOT* REOPEN THIS ONE.** `OQ-RBS-1734` closed on 2026-09-06 —
PO verbatim, *"(b) yes … but note should be short and to the point"* — and the
resolution ratified the same day makes a note an **ENGINE act** (`BR-RBS-040`),
the third after raising work items and writing audit rows. So a note may one day
be written when this run closes; **it is still not a port and this runbook still
declares none**, and nothing here writes one today.

"ONLY ONE BILL" IS AN ANSWER, AND IT IS STEP 1
------------------------------------------------
A new connection has one bill and nothing to compare it against. That is a
designed state and not a failure (PO ruling 2026-09-06, on connections and
feeds: *"in absence of API conenctions you will not find anything and you can
stop the job saying APi or conenct not available; that is a valid case and state
for us"*). Step 1 stops, names what is missing in one sentence, and every later
step reads **Never reached** (`BR-RBS-027`). No KPI strip is drawn over a run
that compared nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_MONEY,
    PARAM_REF_OBJECT,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import billing_seam, customers_seam, metering_seam

KEY = "why_higher"

ZERO = Decimal("0")

# ── the seven steps, in the card's own order ──────────────────────────────

STEP_FETCH = "fetch_both_bills"
STEP_USAGE = "compare_usage"
STEP_RATES = "compare_rates"
STEP_CHARGES = "compare_charges"
STEP_ONE_OFFS = "find_one_offs"
STEP_METER = "check_the_meter"
STEP_RANK = "rank_the_causes"

STEP_LABELS = {
    STEP_FETCH: "Fetch both bills",
    STEP_USAGE: "Compare usage",
    STEP_RATES: "Compare rates",
    STEP_CHARGES: "Compare charges",
    STEP_ONE_OFFS: "Find one-offs",
    STEP_METER: "Check the meter",
    STEP_RANK: "Rank the causes",
}

# ── what a bill may be compared WITH ──────────────────────────────────────
#
# The card's own three: *Previous · Aug · $132.40*, and *"Also offered: same
# month last year and 12-month average."*
COMPARE_PREVIOUS = "previous"
COMPARE_SAME_MONTH_LAST_YEAR = "same_month_last_year"
COMPARE_TWELVE_MONTH_AVERAGE = "twelve_month_average"
COMPARISONS = (COMPARE_PREVIOUS, COMPARE_SAME_MONTH_LAST_YEAR, COMPARE_TWELVE_MONTH_AVERAGE)

COMPARISON_LABELS = {
    COMPARE_PREVIOUS: "the previous bill",
    COMPARE_SAME_MONTH_LAST_YEAR: "the same month last year",
    COMPARE_TWELVE_MONTH_AVERAGE: "the last twelve months' average",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# Verified against `07-frontend/src/routing/` on 2026-09-07; tenant-relative,
# because the shell prefixes `/:tenant/` (`DEF-RBS-4329`).
FIX_BILLING = "billing"
FIX_ACCOUNTS = "accounts"
FIX_READS = "reads"

#: The line kinds `billing` writes, grouped by what a customer calls them.
#: ⚠ `minimum` is billing's own kind and is a CHARGE, not a fee — a minimum
#: charge is what the utility bills when usage is below the floor, and calling
#: it a one-off on a screen would send a clerk looking for something that was
#: never added.
KIND_USAGE = "usage"
KIND_BASE = "base"
KIND_FEE = "fee"
KIND_TAX = "tax"
KIND_ADJUSTMENT = "adjustment"
KIND_MINIMUM = "minimum"

#: What a clerk calls each kind, for the cause line. Never the machine word.
KIND_WORDS = {
    KIND_USAGE: "used",
    KIND_BASE: "Base charge",
    KIND_FEE: "Fee",
    KIND_TAX: "Tax on the above",
    KIND_ADJUSTMENT: "Adjustment",
    KIND_MINIMUM: "Minimum charge",
}

#: The kinds that are ONE-OFFS — step 5's *catch-up read, corrected estimate,
#: back-bill, late fee*. A one-off is a line that appears on one bill and not
#: the other, and only these kinds can be one.
ONE_OFF_KINDS = (KIND_FEE, KIND_ADJUSTMENT)


@dataclass
class _StepResult:
    """What every set step returns — what it found, and what it LOOKED AT.

    `reached` is `False` on every step after a stop — what the chain draws as
    `notReached`, rather than a blank cell, which reads as *nothing wrong*.
    """

    reached: bool = True
    stop: dict[str, Any] | None = None
    found: dict[str, Any] = field(default_factory=dict)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "reached": self.reached,
            "found": dict(self.found),
            "checked": dict(self.checked),
        }
        if self.stop is not None:
            out["stop"] = dict(self.stop)
        return out


# ── money, and the two jobs it does ───────────────────────────────────────


def _money(raw: Any) -> Decimal:
    """A stored money string as a `Decimal`. ⚠ **NEVER `float(...)`** (rule 2)."""
    if raw in (None, ""):
        return ZERO
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return ZERO


def _stored(amount: Decimal) -> str:
    """As it is STORED — four decimals. The renderer shows two (hard rule 2)."""
    return str(amount.quantize(Decimal("0.0001")))


def _shown(amount: Decimal, currency: str) -> str:
    """As a CLERK READS IT — two decimals, with its currency code.

    ⚠ **AND IT DOES NOT INVENT A SYMBOL**, which is `cash_application._shown`'s
    reasoning taken as the module's convention: `$` is a formatting decision the
    tenant's regional settings own and the renderer applies. A sentence composed
    here carries the CHAR(3) code; a money CELL — which does get the symbol — is
    used everywhere the value is a column rather than prose.

    ⚠ Wave `P` shipped `182.400000` into a clerk's sentence, which is hard rule
    2 breached in its display half. Every figure in a CELL is carried at four
    and shown at two by the renderer; this is the one place prose rounds.
    """
    return f"{amount.quantize(Decimal('0.01'))} {currency}".strip()


def _signed(amount: Decimal, currency: str) -> str:
    """*+82.20 USD* — the sign is the answer, so it is never dropped."""
    figure = amount.quantize(Decimal("0.01"))
    return f"{'+' if figure > 0 else ''}{figure} {currency}".strip()


def _quantity(raw: Any) -> str:
    """A measured quantity as a person reads it — **never in exponent form**.

    ⚠ **`Decimal.normalize()` ALONE PRODUCES `1.5E+3`, AND THAT REACHED A
    CLERK-FACING SENTENCE ON THE FIRST RUN OF THIS RUNBOOK.** The walkthrough
    read *"You used 1E+2 kWh more of electric"*. It is the same class as wave
    `P`'s `182.400000` — a stored representation in prose — and the cure is the
    `f` presentation type, which never uses an exponent.
    """
    value = _money(raw).normalize()
    text = format(value, "f")
    return text


def _plural(count: int, word: str) -> str:
    """*1 more day* · *4 more days*. A sentence a clerk reads aloud has to be
    written like English, and `f"{n} days"` is where that stops being true."""
    return f"{count} {word}" if abs(count) == 1 else f"{count} {word}s"


def _days(bill: dict[str, Any]) -> int:
    """How many days the bill covers, INCLUSIVE of both ends.

    ⚠ **INCLUSIVE, BECAUSE A BILL FOR 1 – 31 AUGUST IS 31 DAYS AND NOT 30.** The
    card's worked example turns on this figure — *"34 vs 30 days"* — and an
    exclusive count would quietly under-report every period by one day and make
    the daily average wrong on every bill.
    """
    start, end = _period(bill)
    if start is None or end is None:
        return 0
    return (end - start).days + 1


def _period(bill: dict[str, Any]) -> tuple[date | None, date | None]:
    def _parse(value: Any) -> date | None:
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None

    return _parse(bill.get("period_start")), _parse(bill.get("period_end"))


def _period_words(bill: dict[str, Any]) -> str:
    """*Sep 2026* — what a customer calls the bill, never its number or its id."""
    _start, end = _period(bill)
    return end.strftime("%b %Y") if end else str(bill.get("invoice_no") or "")


# ── grouping: the one decision every figure on this screen rests on ───────


def _group_key(line: dict[str, Any]) -> tuple[str, str, str]:
    """How two lines from two different bills are recognised as *the same line*.

    ⚠ **KIND, SERVICE AND DESCRIPTION — AND THE DESCRIPTION IS LOAD-BEARING.**
    A water bill carries *Water 0–5,000 gal* and *Water over 5,000 gal* as two
    separate usage lines, and folding them together by service would hide the
    single most useful thing this runbook says: **the customer crossed into the
    higher block**. The card's worked example is exactly that — *"Reached tier 2
    (usage above 5,000 gal priced higher) +$14.80"*.

    ⚠ **AND IT IS WHY A RE-WORDED TARIFF READS AS TWO CAUSES.** If a utility
    renames a block between two bills, one line ends and another begins, and the
    two show up as a fall and a rise of the same size. That is visible and
    self-explaining on the side-by-side table; a fold that hid it would produce
    a confident total change with no cause under it.
    """
    return (
        str(line.get("kind") or ""),
        str(line.get("service") or ""),
        str(line.get("description") or ""),
    )


def _group_label(key: tuple[str, str, str]) -> str:
    kind, service, description = key
    if description:
        return description
    if service:
        return f"{service.title()} {KIND_WORDS.get(kind, kind)}".strip()
    return KIND_WORDS.get(kind, kind or "Other")


def _totals_by_group(bill: dict[str, Any]) -> dict[tuple[str, str, str], Decimal]:
    out: dict[tuple[str, str, str], Decimal] = {}
    for line in bill.get("lines") or []:
        key = _group_key(line)
        out[key] = out.get(key, ZERO) + _money(line.get("amount"))
    return out


def _usage_by_service(bill: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """How much was measured, per service, WITH ITS UNIT (hard rule 3).

    ⚠ **A LINE WITH NO UNIT IS NOT ADDED IN.** `invoice_lines.unit` is explicit
    whenever a line is usage-based, and a quantity with no unit is a number this
    product refuses to assume the meaning of. Those lines are COUNTED, so a
    service whose usage cannot be summed says so rather than reading as zero.
    """
    out: dict[str, dict[str, Any]] = {}
    for line in bill.get("lines") or []:
        if str(line.get("kind")) != KIND_USAGE or line.get("quantity") is None:
            continue
        service = str(line.get("service") or "")
        unit = str(line.get("unit") or "")
        entry = out.setdefault(
            service, {"quantity": ZERO, "unit": unit, "lines": 0, "lines_with_no_unit": 0}
        )
        if not unit:
            entry["lines_with_no_unit"] += 1
            continue
        if entry["unit"] and unit != entry["unit"]:
            # Two units on one service inside one bill is a fact this runbook
            # reports rather than converts (`BR-RAT-038` refuses rather than
            # converts, and this is a Check with less standing than that).
            entry["lines_with_no_unit"] += 1
            continue
        entry["unit"] = unit
        entry["quantity"] += _money(line.get("quantity"))
        entry["lines"] += 1
    return out


# ── step 1 · both bills ───────────────────────────────────────────────────


def _bills(ctx) -> list[dict[str, Any]]:
    cached = ctx.set_results.get("_bills")
    if cached is None:
        account_id = ctx.params.get("account")
        cached = (
            billing_seam.issued_bills_for_account(account_id, limit=14) if account_id else []
        )
        ctx.set_results["_bills"] = cached
    return list(cached)


def _average_bill(bills: list[dict[str, Any]], currency: str) -> dict[str, Any]:
    """A synthetic bill: **the mean of up to twelve**, line group by line group.

    The card offers *12-month average* as a comparison, and an average is not a
    document — so this builds one whose every group is the mean over the bills
    that carried it. ⚠ **THE DIVISOR IS THE NUMBER OF BILLS, NEVER THE NUMBER
    THAT CARRIED THE LINE.** A late fee on one bill in twelve averages to a
    twelfth of itself, which is the true monthly figure; dividing by one would
    say the customer pays it every month.

    ⚠ **`Decimal`, QUANTIZED TO FOUR** (hard rule 2). The average is a computed
    figure and is still money, so it is stored to four and shown to two like
    every other.
    """
    window = bills[:12]
    count = Decimal(len(window) or 1)
    groups: dict[tuple[str, str, str], Decimal] = {}
    for bill in window:
        for key, amount in _totals_by_group(bill).items():
            groups[key] = groups.get(key, ZERO) + amount
    lines = [
        {
            "kind": key[0],
            "service": key[1],
            "description": key[2],
            "amount": _stored(amount / count),
            "quantity": None,
            "unit": None,
            "unit_price": None,
            "taxable": False,
            "tariff_version_id": None,
        }
        for key, amount in groups.items()
    ]
    total = sum((_money(one["amount"]) for one in lines), ZERO)
    days = sum(_days(one) for one in window)
    return {
        "bill_id": None,
        "invoice_no": None,
        "status": "average",
        "period_start": window[-1].get("period_start") if window else None,
        "period_end": window[0].get("period_end") if window else None,
        "issued_on": None,
        "currency": currency,
        "subtotal": _stored(total),
        "tax_total": "0.0000",
        "total": _stored(total),
        "lines": lines,
        "is_average": True,
        "averaged_over": len(window),
        "average_days": (days // len(window)) if window else 0,
    }


def step_fetch_both_bills(ctx, subjects) -> dict[str, Any]:
    """1 · Line by line, as issued — and the run STOPS when there is only one.

    ⚠ **ISSUED, NEVER A DRAFT** (`BR-BIL-004`). What a customer means by *my
    bill* is the document they received.
    """
    bills = _bills(ctx)
    wanted = ctx.params.get("this_bill")
    compare_with = str(ctx.params.get("compare_with") or COMPARE_PREVIOUS)
    checked: dict[str, Any] = {
        "issued_bills_on_file": len(bills),
        "compare_with": compare_with,
    }

    if not bills:
        return _StepResult(
            stop={
                "headline": "No bill to explain.",
                "detail": (
                    "This account has no issued bill yet, so there is nothing to compare. "
                    "Open the account to see where it is in the billing cycle."
                ),
                "fix_route": FIX_ACCOUNTS,
                "fix_label": "Open the account",
            },
            checked=checked,
        ).as_dict()

    this = next((one for one in bills if str(one["bill_id"]) == str(wanted)), bills[0])
    older = [one for one in bills if str(one["bill_id"]) != str(this["bill_id"])]
    currency = str(this.get("currency") or "")
    checked["this_bill"] = _period_words(this)

    other: dict[str, Any] | None = None
    if compare_with == COMPARE_TWELVE_MONTH_AVERAGE:
        other = _average_bill(older, currency) if older else None
    elif compare_with == COMPARE_SAME_MONTH_LAST_YEAR:
        _start, end = _period(this)
        if end is not None:
            for candidate in older:
                _s, candidate_end = _period(candidate)
                if (
                    candidate_end is not None
                    and candidate_end.month == end.month
                    and candidate_end.year == end.year - 1
                ):
                    other = candidate
                    break
    else:
        # PREVIOUS — the newest bill whose period ENDS before this one starts.
        # ⚠ Ordered by period, never by when it was issued: a bill raised late
        # is still the bill for its own month, and a re-issue would otherwise
        # read as *the previous bill*.
        start, _end = _period(this)
        for candidate in older:
            _s, candidate_end = _period(candidate)
            if start is not None and candidate_end is not None and candidate_end < start:
                other = candidate
                break

    if other is None:
        return _StepResult(
            stop={
                "headline": "Only one bill to compare.",
                "detail": (
                    f"There is no {COMPARISON_LABELS.get(compare_with, 'earlier bill')} on "
                    "this account. Pick a different comparison, or come back after the next "
                    "bill run."
                ),
                "fix_route": FIX_BILLING,
                "fix_label": "Open billing",
            },
            checked=checked | {"bills_available_to_compare": len(older)},
        ).as_dict()

    checked["other_bill"] = _period_words(other)
    checked["other_is_an_average"] = bool(other.get("is_average"))
    checked["lines_this_bill"] = len(this.get("lines") or [])
    checked["lines_other_bill"] = len(other.get("lines") or [])
    return _StepResult(found={"this": this, "other": other}, checked=checked).as_dict()


# ── the reads every later step makes ──────────────────────────────────────


def _stopped(ctx) -> dict[str, Any] | None:
    first = ctx.set_results.get(STEP_FETCH) or {}
    stop = first.get("stop")
    return dict(stop) if stop else None


def _never_reached(stop: dict[str, Any]) -> dict[str, Any]:
    return _StepResult(
        reached=False, checked={"never_reached_because": stop["headline"]}
    ).as_dict()


def _pair(view_or_ctx) -> tuple[dict[str, Any], dict[str, Any]]:
    found = (view_or_ctx.set_results.get(STEP_FETCH) or {}).get("found") or {}
    return dict(found.get("this") or {}), dict(found.get("other") or {})


# ── step 2 · usage ────────────────────────────────────────────────────────


def step_compare_usage(ctx, subjects) -> dict[str, Any]:
    """2 · Days in period, units used, daily average — per service.

    ⚠ **NORMALISE FOR DAYS IS THE POINT OF THIS STEP** and the card says why: a
    34-day period against a 28-day one explains a surprising share of these
    calls on its own. With the toggle on, the step also reports what THIS bill's
    daily rate would have produced over the OTHER bill's length, so a clerk can
    separate *you used more* from *this bill covers more days*.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    this, other = _pair(ctx)
    normalise = bool(ctx.params.get("normalise_for_days", True))
    this_days = _days(this)
    other_days = other.get("average_days") or _days(other)
    this_usage = _usage_by_service(this)
    other_usage = _usage_by_service(other)

    services: list[dict[str, Any]] = []
    for service in sorted(set(this_usage) | set(other_usage)):
        now = this_usage.get(service) or {"quantity": ZERO, "unit": "", "lines_with_no_unit": 0}
        was = other_usage.get(service) or {"quantity": ZERO, "unit": "", "lines_with_no_unit": 0}
        moved = now["quantity"] - was["quantity"]
        percent = (
            (moved / was["quantity"] * Decimal(100)).quantize(Decimal("0.000001"))
            if was["quantity"]
            else None
        )
        normalised = None
        if normalise and this_days and other_days:
            # What THIS bill's daily rate would have produced over the OTHER
            # bill's length. The difference between that and what was actually
            # used last time is the part days do NOT explain.
            normalised = (
                now["quantity"] / Decimal(this_days) * Decimal(other_days)
            ).quantize(Decimal("0.0001"))
        services.append(
            {
                "service": service,
                "unit": now["unit"] or was["unit"],
                "now": _stored(now["quantity"]),
                "was": _stored(was["quantity"]),
                "moved": _stored(moved),
                # ⚠ SIX DECIMALS STORED, TWO SHOWN (hard rule 2's percent half).
                "percent": None if percent is None else str(percent),
                "at_the_same_daily_rate": None if normalised is None else str(normalised),
                "lines_with_no_unit": now.get("lines_with_no_unit", 0)
                + was.get("lines_with_no_unit", 0),
            }
        )
    return _StepResult(
        found={"services": services},
        checked={
            "days_this_bill": this_days,
            "days_other_bill": other_days,
            "more_days": this_days - other_days,
            "normalise_for_days": normalise,
            "services_measured": len(services),
        },
    ).as_dict()


# ── step 3 · rates ────────────────────────────────────────────────────────


def step_compare_rates(ctx, subjects) -> dict[str, Any]:
    """3 · Did a rate version change between the two?

    ⚠ **THE ONLY HONEST ANSWER IS THE VERSION THE BILL WAS PRICED ON.**
    `invoice_lines.tariff_version_id` is stamped at issue and frozen, so two
    bills carrying different versions for one service is a change that actually
    reached the customer. Comparing today's in-force version against both would
    report a change on every bill raised before the last edit — true of the
    tariff, false of the customer's two bills.

    ⚠ **AND A LINE WITH NO VERSION IS NOT A CHANGE.** A base charge or a fee
    carries no tariff version at all, and treating a `None` as *different* would
    report a rate change on every bill that carries a fee.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    this, other = _pair(ctx)

    def _versions(bill: dict[str, Any]) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for line in bill.get("lines") or []:
            version = line.get("tariff_version_id")
            if not version:
                continue
            out.setdefault(str(line.get("service") or ""), set()).add(str(version))
        return out

    now, was = _versions(this), _versions(other)
    changed = sorted(
        service
        for service in set(now) | set(was)
        if now.get(service) and was.get(service) and now[service] != was[service]
    )
    unknown = sorted(
        service for service in set(now) | set(was) if not now.get(service) or not was.get(service)
    )
    return _StepResult(
        found={"changed": changed, "not_comparable": unknown},
        checked={
            "services_with_a_priced_line_on_both": len(set(now) & set(was)),
            "rate_changed_for": changed,
            "could_not_be_compared": unknown,
            "comparison_is": "the tariff version each bill was priced on, as issued",
        },
    ).as_dict()


# ── step 4 · charges ──────────────────────────────────────────────────────


def step_compare_charges(ctx, subjects) -> dict[str, Any]:
    """4 · Base, each block, taxes, fees, adjustments — line group by line group.

    This step builds the side-by-side table AND the money-bearing causes, from
    one calculation, because the card's own correction is what happens when the
    two are computed separately: the causes summed to $92.20 against a change of
    $82.20.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    this, other = _pair(ctx)
    now = _totals_by_group(this)
    was = _totals_by_group(other)
    rows: list[dict[str, Any]] = []
    for key in sorted(set(now) | set(was), key=lambda one: (one[0], one[1], one[2])):
        moved = now.get(key, ZERO) - was.get(key, ZERO)
        rows.append(
            {
                "kind": key[0],
                "service": key[1],
                "label": _group_label(key),
                "now": _stored(now.get(key, ZERO)),
                "was": _stored(was.get(key, ZERO)),
                "moved": _stored(moved),
                "only_on_this_bill": key not in was,
                "only_on_the_other": key not in now,
            }
        )
    total_now = _money(this.get("total"))
    total_was = _money(other.get("total"))
    change = total_now - total_was
    # ⚠ **THE TIE-OUT, ASSERTED HERE RATHER THAN ASSUMED.** The card's own
    # correction is this arithmetic going wrong once; the difference between the
    # line deltas and the bill totals is REPORTED, so a bill whose lines do not
    # sum to its own total is visible rather than silently absorbed into a cause.
    from_lines = sum((_money(row["moved"]) for row in rows), ZERO)
    return _StepResult(
        found={"rows": rows},
        checked={
            "groups_compared": len(rows),
            "total_this_bill": _stored(total_now),
            "total_other_bill": _stored(total_was),
            "change": _stored(change),
            "change_from_the_lines": _stored(from_lines),
            "lines_tie_to_the_totals": from_lines == change,
        },
    ).as_dict()


# ── step 5 · one-offs ─────────────────────────────────────────────────────


def step_find_one_offs(ctx, subjects) -> dict[str, Any]:
    """5 · Catch-up read, corrected estimate, back-bill, late fee.

    ⚠ **A ONE-OFF IS A LINE ON ONE BILL AND NOT THE OTHER**, and only a fee or
    an adjustment can be one. A usage block that appears for the first time is
    NOT a one-off — it is the customer crossing into a higher tier, which is a
    different sentence with a different fix, and the card's worked example keeps
    the two apart (*"Reached tier 2"* beside *"Late fee"*).
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    rows = ((ctx.set_results.get(STEP_CHARGES) or {}).get("found") or {}).get("rows") or []
    added = [
        row
        for row in rows
        if row["only_on_this_bill"] and row["kind"] in ONE_OFF_KINDS and _money(row["moved"])
    ]
    gone = [
        row
        for row in rows
        if row["only_on_the_other"] and row["kind"] in ONE_OFF_KINDS and _money(row["moved"])
    ]
    return _StepResult(
        found={"added": added, "gone": gone},
        checked={
            "one_offs_added": len(added),
            "one_offs_no_longer_charged": len(gone),
            "kinds_that_can_be_a_one_off": list(ONE_OFF_KINDS),
        },
    ).as_dict()


# ── step 6 · the meter ────────────────────────────────────────────────────


def step_check_the_meter(ctx, subjects) -> dict[str, Any]:
    """6 · Multiplier change, exchange, rollover.

    ⚠ **THE MULTIPLIER COMPARED IS THE ONE EACH READ WAS COMPUTED WITH**
    (`BR-MET-056`), never the meter's current factor: a bill raised under an old
    multiplier must still read as *unchanged* when the multiplier has not moved
    between these two periods, and as *changed* when it has.

    ⚠ **AN ACCOUNT WITH NO UNIT HAS NO METER TO CHECK, AND THAT IS AN ANSWER.**
    A master account is anchored to a premises and no unit (`BR-CUS-1010`), so
    this step reports *not applicable* with its reason rather than reading a
    silent zero — hard-won law 7, the difference between *nothing changed* and
    *nothing was looked at*.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    this, other = _pair(ctx)
    facts = customers_seam.account_facts(ctx.params.get("account")) or {}
    unit_id = facts.get("unit_id")
    start, _end = _period(other)
    if not unit_id:
        return _StepResult(
            found={"multiplier_changed": False, "meter_exchanged": False, "rollovers": 0},
            checked={
                "meters_looked_at": 0,
                "not_checked_because": "this account is not anchored to a unit",
            },
        ).as_dict()

    history = metering_seam.meter_read_history(unit_ids=[unit_id], since=start)
    multipliers: set[str] = set()
    by_service: dict[str, set[str]] = {}
    rollovers = 0
    reads = 0
    for meter in history:
        by_service.setdefault(str(meter.get("service") or ""), set()).add(str(meter["asset_id"]))
        previous: Decimal | None = None
        for read in meter.get("reads") or []:
            reads += 1
            if read.get("multiplier") is not None:
                multipliers.add(str(read["multiplier"]))
            current = read.get("current_value")
            if current is not None:
                value = _money(current)
                if previous is not None and value < previous:
                    rollovers += 1
                previous = value
    # ⚠ **AN EXCHANGE IS TWO METERS ON ONE SERVICE, NOT TWO METERS ON THE UNIT** —
    # and the first build got this wrong on the first real account it ran
    # against. A unit that takes electricity and water has two meters by design,
    # so `len(history) > 1` reported *"More than one meter served this unit"* on
    # an ordinary two-service connection: a cause a clerk would have read out to
    # a customer, over nothing that happened.
    exchanged = sorted(
        service for service, meters in by_service.items() if len(meters) > 1
    )
    return _StepResult(
        found={
            "multiplier_changed": len(multipliers) > 1,
            "meter_exchanged": bool(exchanged),
            "exchanged_for": exchanged,
            "rollovers": rollovers,
        },
        checked={
            "meters_looked_at": len(history),
            "reads_looked_at": reads,
            "services_with_more_than_one_meter": exchanged,
            "multipliers_seen": sorted(multipliers),
            "window_starts": start.isoformat() if start else None,
            "multiplier_compared_is": "the factor each read was computed with",
        },
    ).as_dict()


# ── step 7 · the causes, largest first ────────────────────────────────────


def _causes(ctx_or_view) -> list[dict[str, Any]]:
    """Every cause, largest dollars first — and they SUM TO THE CHANGE.

    The money-bearing causes are the line-group deltas from step 4 and nothing
    else; the rate and meter rows are reports rather than prices (see the module
    docstring). Sorting is by ABSOLUTE dollars, so a large fall ranks with a
    large rise: a customer asking *why is this higher* is served by seeing that
    something also went down.
    """
    charges = (ctx_or_view.set_results.get(STEP_CHARGES) or {}).get("found") or {}
    rates = (ctx_or_view.set_results.get(STEP_RATES) or {}).get("found") or {}
    meter = (ctx_or_view.set_results.get(STEP_METER) or {}).get("found") or {}
    usage = (ctx_or_view.set_results.get(STEP_USAGE) or {}).get("found") or {}
    by_service = {one["service"]: one for one in (usage.get("services") or [])}

    causes: list[dict[str, Any]] = []
    for row in charges.get("rows") or []:
        moved = _money(row["moved"])
        if not moved:
            continue
        detail = ""
        if row["kind"] == KIND_USAGE:
            measured = by_service.get(row["service"])
            if measured and measured.get("unit"):
                detail = (
                    f"{_quantity(measured['now'])} {measured['unit']} "
                    f"against {_quantity(measured['was'])} {measured['unit']}"
                )
            if row["only_on_this_bill"]:
                # The single most useful sentence this runbook produces.
                detail = (detail + " · this block was not charged last time").strip(" ·")
        elif row["kind"] == KIND_TAX:
            detail = "Follows the charges"
        elif row["only_on_this_bill"]:
            detail = "Not on the other bill"
        causes.append(
            {
                "label": row["label"],
                "detail": detail,
                "amount": row["moved"],
                "kind": row["kind"],
            }
        )
    causes.sort(key=lambda one: abs(_money(one["amount"])), reverse=True)

    # The two structural rows, always drawn and always last — the card's own
    # worked example carries both at $0.00 when nothing changed.
    changed = list(rates.get("changed") or [])
    causes.append(
        {
            "label": "Rate change",
            "detail": (
                f"The price of {', '.join(changed)} changed — the difference is inside the "
                "charges above"
                if changed
                else "None between the two bills"
            ),
            "amount": "0.0000",
            "kind": "rate",
        }
    )
    exchanged = bool(meter.get("meter_exchanged"))
    multiplier = bool(meter.get("multiplier_changed"))
    causes.append(
        {
            "label": "Meter",
            "detail": (
                " · ".join(
                    part
                    for part in (
                        (
                            f"More than one meter served {', '.join(meter.get('exchanged_for') or [])}"
                            if exchanged
                            else ""
                        ),
                        "The multiplier changed" if multiplier else "",
                        f"{meter.get('rollovers')} rollover(s)" if meter.get("rollovers") else "",
                    )
                    if part
                )
                or "Same meter, same multiplier"
            ),
            "amount": "0.0000",
            "kind": "meter",
        }
    )
    return causes


def step_rank_the_causes(ctx, subject) -> dict[str, Any]:
    """7 · By dollars contributed, largest first — the run's one record.

    ⚠ **THE ONLY PER-RECORD STEP, WHICH IS THE CARD'S OWN *per record (1)*.**
    The subject is the account, so this runs once, inside its own savepoint
    (hard-won law 14 — the executor's nested `transaction.atomic()` is what lets
    a run continue after a refused row on PostgreSQL, and the suite's SQLite
    cannot see the difference).
    """
    stop = _stopped(ctx)
    if stop:
        return {
            "outcome": "skipped",
            "reason": stop["headline"],
            "decided_by_rule": "A required step failing makes every later step Never reached",
            "fix_route": stop["fix_route"],
        }

    this, other = _pair(ctx)
    currency = str(this.get("currency") or "")
    change = _money(this.get("total")) - _money(other.get("total"))
    above = _money(ctx.params.get("show_causes_above") or "2.0000")
    causes = _causes(ctx)
    shown = [
        one
        for one in causes
        if abs(_money(one["amount"])) >= above or one["kind"] in ("rate", "meter")
    ]
    return {
        "outcome": "explained" if change else "unchanged",
        "reason": (
            f"{_signed(change, currency)} against {_period_words(other)}."
            if change
            else f"The same as {_period_words(other)}."
        ),
        "decided_by_rule": "Every cause is a line the two bills priced differently",
        "fix_route": FIX_BILLING,
        "data": {
            "causes_found": len(causes),
            "causes_shown": len(shown),
            "below_the_threshold": len(causes) - len(shown),
            "change": _stored(change),
            "currency": currency,
            # ⚠ **THE THRESHOLD TRAVELS ON THE RECORD BECAUSE `report()` CANNOT
            # SEE THE RUN'S PARAMETERS.** `executor._ReportView` carries the
            # definition, the subjects, the records, the counts and the set
            # results — and NOT `ctx.params`. So a report composed from a
            # parameter must be handed it by a step, and reading the
            # definition's DEFAULT instead is the silent version of this: it
            # renders correctly for every run that left the box alone and
            # ignores the number a clerk typed. That is what the first build did
            # and a test caught it (`show_causes_above` set to 20.00 changed
            # nothing on screen).
            "show_causes_above": _stored(above),
        },
    }


# ── the report ────────────────────────────────────────────────────────────


def _chain(stop: dict[str, Any]) -> Block:
    cells = [
        {
            "id": key,
            "position": index,
            "label": STEP_LABELS[key],
            "state": "bad" if index == 1 else "notReached",
            "note": stop["headline"] if index == 1 else "Never reached",
        }
        for index, key in enumerate(STEP_LABELS, start=1)
    ]
    return Block(block="chain", payload={"label": "The run stopped at step 1.", "cells": cells})


def _read_aloud(view) -> str:
    """The sentence a clerk says down the phone, in the customer's own units.

    ⚠ **NO RULE ID, NO SCREEN CODE, NO INTERNAL WORD** (B14 rule 32). It is
    written for someone who has never seen this product, and every figure in it
    is shown at two decimals with its currency code (hard rule 2's display
    half).
    """
    this, other = _pair(view)
    currency = str(this.get("currency") or "")
    change = _money(this.get("total")) - _money(other.get("total"))
    usage = (view.set_results.get(STEP_USAGE) or {}).get("found") or {}
    checked = (view.set_results.get(STEP_USAGE) or {}).get("checked") or {}
    rates = (view.set_results.get(STEP_RATES) or {}).get("found") or {}
    one_offs = (view.set_results.get(STEP_ONE_OFFS) or {}).get("found") or {}

    direction = "higher" if change > 0 else ("lower" if change < 0 else "the same")
    if change:
        # The comparison is named the way a customer would say it — *than the
        # previous bill*, *than the same month last year* — and falls back to
        # the period itself, never to an internal word.
        against = COMPARISON_LABELS.get(
            str(((view.set_results.get(STEP_FETCH) or {}).get("checked") or {}).get("compare_with")),
            _period_words(other),
        )
        parts = [
            f"Your {_period_words(this)} bill is {_shown(abs(change), currency)} {direction} "
            f"than {against}."
        ]
    else:
        parts = [f"Your {_period_words(this)} bill is the same as {_period_words(other)}."]

    for service in usage.get("services") or []:
        moved = _money(service["moved"])
        if not moved or not service.get("unit"):
            continue
        percent = service.get("percent")
        more = "more" if moved > 0 else "less"
        sentence = (
            f"You used {_quantity(abs(moved))} {service['unit']} {more} "
            f"{service['service']}"
        )
        if percent is not None:
            sentence += f" — {abs(Decimal(percent)).quantize(Decimal('0.01'))}%"
        days = int(checked.get("more_days") or 0)
        if days:
            sentence += (
                f" over {abs(days)} {'more' if days > 0 else 'fewer'} "
                f"{'day' if abs(days) == 1 else 'days'}"
            )
        parts.append(sentence + ".")

    for row in one_offs.get("added") or []:
        parts.append(
            f"{row['label']} of {_shown(_money(row['moved']), currency)} was added this time."
        )

    changed = list(rates.get("changed") or [])
    parts.append(
        f"The price of {', '.join(changed)} changed between the two bills."
        if changed
        else "Your rate did not change."
    )
    return " ".join(parts)


def report(view) -> list[Block]:
    """Composed at CLOSE and frozen (`BR-RBS-020`).

    Two compositions, because a stopped run and a finished one are two states:

    * **stopped** — `Verdict` · `Sentence` · `Chain` · `Facts`. **No KPI strip**:
      a strip reading *+0.00 · 0% · 0 days* over a run that compared nothing is
      indistinguishable from a bill that did not move, which is precisely the
      failure hard-won law 7 is about.
    * **finished** — `Verdict` · `KPIs` · `Sentence` · `Ranked` · `Reconciled` ·
      `Facts`, which is `RB-104`'s own block list plus the verdict the header
      consumes.
    """
    stop = (view.set_results.get(STEP_FETCH) or {}).get("stop")
    if stop:
        return [
            Block(
                block="verdict",
                payload={
                    "word": "Stopped",
                    "tone": "warning",
                    "count": stop["headline"],
                    "detail": stop["detail"],
                },
            ),
            Block(
                block="sentence",
                payload={"tone": "muted", "label": "What to do", "text": stop["detail"]},
            ),
            _chain(stop),
            Block(
                block="facts",
                payload={
                    "heading": "What was looked at",
                    "rows": [
                        {
                            "id": "bills",
                            "label": "Issued bills on file",
                            "value": {
                                "kind": "text",
                                "text": str(
                                    (
                                        (view.set_results.get(STEP_FETCH) or {}).get("checked")
                                        or {}
                                    ).get("issued_bills_on_file", 0)
                                ),
                            },
                        }
                    ],
                },
            ),
        ]

    this, other = _pair(view)
    currency = str(this.get("currency") or "")
    change = _money(this.get("total")) - _money(other.get("total"))
    usage = (view.set_results.get(STEP_USAGE) or {}).get("found") or {}
    usage_checked = (view.set_results.get(STEP_USAGE) or {}).get("checked") or {}
    rates = (view.set_results.get(STEP_RATES) or {}).get("found") or {}
    meter = (view.set_results.get(STEP_METER) or {}).get("found") or {}
    charges = (view.set_results.get(STEP_CHARGES) or {}).get("found") or {}
    # ⚠ **THE RUN'S OWN THRESHOLD, HANDED HERE BY STEP 7** — see that step's
    # `data`. The report view carries no parameters, and reading the
    # definition's default here would ignore whatever a clerk typed.
    above = _money(
        (view.records[0].data.get("show_causes_above") if view.records else None) or "2.0000"
    )

    biggest = next(
        (one for one in (usage.get("services") or []) if one.get("percent") is not None), None
    )
    causes = _causes(view)
    shown = [
        one
        for one in causes
        if abs(_money(one["amount"])) >= above or one["kind"] in ("rate", "meter")
    ]
    weight_of = max(
        [abs(_money(one["amount"])) for one in shown] + [Decimal("1")]
    )

    return [
        Block(
            block="verdict",
            payload={
                "word": "Higher" if change > 0 else ("Lower" if change < 0 else "Unchanged"),
                "tone": "warning" if change > 0 else "success",
                "count": (
                    f"{_signed(change, currency)} · {_shown(_money(other.get('total')), currency)} "
                    f"in {_period_words(other)} → {_shown(_money(this.get('total')), currency)} "
                    f"in {_period_words(this)}"
                ),
                "detail": f"{len(shown)} causes, largest first.",
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "change",
                        "label": "Change",
                        "value": {
                            "kind": "money",
                            "amount": _stored(change),
                            "currency": currency,
                        },
                        # ⚠ **`posting`, AND THE LABEL IS THE WHOLE OF
                        # `DEF-RBS-4350`.** Both figures come from ISSUED bills,
                        # so the basis is the date they were posted. The test
                        # bill drew its total under *Posting date* while posting
                        # nothing at all; a money tile that cannot say which
                        # date it is about is an unlabelled money number
                        # (`BR-REP-001`).
                        "basis": "posting",
                    },
                    {
                        "id": "usage",
                        "label": "Usage",
                        "value": (
                            {
                                "kind": "percent",
                                "value": str(biggest["percent"]),
                                # PERCENT POINTS, not a fraction: `7.142857`
                                # means 7.14%. The product stores both shapes,
                                # which is why the convention is required rather
                                # than inferred.
                                "basis": "points",
                                "direction": (
                                    "up"
                                    if _money(biggest["percent"]) > 0
                                    else ("down" if _money(biggest["percent"]) < 0 else "flat")
                                ),
                                "signed": True,
                            }
                            if biggest
                            else {"kind": "text", "text": "—"}
                        ),
                        "detail": (biggest or {}).get("service") or "Nothing measured",
                    },
                    {
                        "id": "days",
                        "label": "Days",
                        "value": {
                            "kind": "text",
                            "text": (
                                f"{usage_checked.get('days_this_bill', 0)} vs "
                                f"{usage_checked.get('days_other_bill', 0)}"
                            ),
                        },
                    },
                    {
                        "id": "rate",
                        "label": "Rate",
                        "value": {
                            "kind": "text",
                            "text": "Changed" if rates.get("changed") else "Same",
                        },
                        "detail": ", ".join(rates.get("changed") or []) or None,
                    },
                ]
            },
        ),
        Block(
            block="sentence",
            payload={
                # ⚠ **`success`, AND THE THREE TONES ARE NOT THE VERDICT'S
                # THREE.** `OutcomeTone` is `success | danger | muted` where
                # `VerdictTone` is `success | warning | danger`, and the renderer
                # looks its class up in a `Record` — so a fourth word renders the
                # card with **no rail and no tint at all**, silently, with every
                # backend check green (`validate_report` asks for the FIELD
                # `tone` and never what is in it). This card is the explanation
                # itself, which is `OutcomeCard`'s own description of `success`:
                # *"something happened or will happen and it is fine"*.
                "tone": "success",
                "label": "Read this aloud",
                "text": _read_aloud(view),
            },
        ),
        Block(
            block="ranked",
            payload={
                "heading": "What caused it · largest first",
                "rows": [
                    {
                        "id": f"cause-{index}",
                        "label": one["label"],
                        "detail": one["detail"] or None,
                        # `weight` is the BAR, scaled against the largest cause;
                        # the figure beside it is the label (`RB-104`: one hue,
                        # no legend, no colour meaning).
                        "weight": float(
                            (abs(_money(one["amount"])) / weight_of).quantize(Decimal("0.0001"))
                        ),
                        "value": {
                            "kind": "money",
                            "amount": one["amount"],
                            "currency": currency,
                        },
                    }
                    for index, one in enumerate(shown, start=1)
                ],
            },
        ),
        Block(
            block="reconciled",
            payload={
                "heading": "Side by side",
                # ⚠ **B14 RULE 34'S PAIR — *Recorded* / *In the books* — DOES NOT
                # APPLY HERE, AND SAYING SO IS CHEAPER THAN A REVIEWER
                # REDISCOVERING IT.** That rule fixes the words for *held here*
                # versus *in the books*, which is a money tie-out between two
                # ledgers. These two columns are two BILLING PERIODS of one
                # account, so the headings are the periods themselves — which is
                # also what `RB-104`'s own table draws (*Line · Aug · Sep ·
                # Change*).
                "columns": [
                    {"key": "line", "label": "Line"},
                    {"key": "was", "label": _period_words(other), "numeric": True},
                    {"key": "now", "label": _period_words(this), "numeric": True},
                    {"key": "moved", "label": "Change", "numeric": True},
                ],
                "rows": [
                    {
                        "id": f"line-{index}",
                        "cells": {
                            "line": {"kind": "text", "text": row["label"]},
                            "was": {
                                "kind": "money",
                                "amount": row["was"],
                                "currency": currency,
                            },
                            "now": {
                                "kind": "money",
                                "amount": row["now"],
                                "currency": currency,
                            },
                            "moved": {
                                "kind": "money",
                                "amount": row["moved"],
                                "currency": currency,
                            },
                        },
                        "meta": {"kind": row["kind"], "service": row["service"] or None},
                    }
                    for index, row in enumerate(charges.get("rows") or [], start=1)
                ],
                "tiesLabel": "Same",
            },
        ),
        Block(
            block="facts",
            payload={
                "heading": "The two bills",
                "rows": [
                    {
                        "id": "period",
                        "label": "Periods",
                        "value": {
                            "kind": "text",
                            "text": f"{_period_words(other)} → {_period_words(this)}",
                        },
                    },
                    {
                        "id": "days",
                        "label": "Days billed",
                        "value": {
                            "kind": "text",
                            "text": (
                                f"{usage_checked.get('days_other_bill', 0)} → "
                                f"{usage_checked.get('days_this_bill', 0)}"
                            ),
                        },
                    },
                ]
                + [
                    {
                        "id": f"usage-{one['service']}",
                        "label": f"{one['service'].title()} used",
                        "value": {
                            "kind": "unit",
                            "quantity": one["now"],
                            "unit": one["unit"] or "",
                        },
                    }
                    for one in (usage.get("services") or [])
                    if one.get("unit")
                ]
                + [
                    {
                        "id": "rate",
                        "label": "Rate",
                        "value": {
                            "kind": "text",
                            "text": (
                                f"Changed for {', '.join(rates.get('changed') or [])}"
                                if rates.get("changed")
                                else "Unchanged between the two bills"
                            ),
                        },
                    },
                    {
                        "id": "meter",
                        "label": "Meter",
                        "value": {
                            "kind": "text",
                            "text": (
                                "Same meter, same multiplier"
                                if not (meter.get("meter_exchanged") or meter.get("multiplier_changed"))
                                else "Changed — see the causes"
                            ),
                        },
                    },
                ],
            },
        ),
    ]


# ── the pinned scope ──────────────────────────────────────────────────────


def resolve(ctx):
    """The pinned set: **one account** (`BR-RBS-019`, `BR-RBS-009`).

    ⚠ **AN ACCOUNT THIS TENANT DOES NOT HOLD RESOLVES TO NOTHING, AND THAT IS
    NOT AN ERROR.** `account_facts` answers `None` for an id this tenant cannot
    see — identically to an absent one, which is `HR-1` and hard rule 1 — so the
    run pins an empty scope, no step walks anything, and the report says so.
    A `resolve()` that raised would turn a tenancy boundary into a stack trace.
    """
    facts = customers_seam.account_facts(ctx.params.get("account"))
    if facts is None:
        return []
    return [
        SubjectRef(
            subject_type="account",
            subject_id=str(ctx.params.get("account")),
            # B14 rule 31 — the customer's name, or the account NUMBER, never
            # the row's id.
            label=str(facts.get("label") or facts.get("account_no") or ""),
        )
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Why is this bill higher?",
    kind=models.KIND_CHECK,
    category="billing",
    subject_type="account",
    unit_of_work="one account and two bills",
    triggers=(models.TRIGGER_MANUAL,),
    tags=("Customer portal",),
    parameters=(
        Parameter(
            name="account",
            type=PARAM_REF_OBJECT,
            label="Account",
            required=True,
        ),
        Parameter(
            name="this_bill",
            type=PARAM_REF_OBJECT,
            label="This bill",
            required=True,
            # Unset, step 1 takes the newest ISSUED bill — which is what a clerk
            # taking the call is looking at.
        ),
        Parameter(
            name="compare_with",
            type=PARAM_ENUM,
            label="Compared with",
            default=COMPARE_PREVIOUS,
            choices=COMPARISONS,
        ),
        Parameter(
            name="show_causes_above",
            type=PARAM_MONEY,
            label="Show causes above",
            # ⚠ A STRING, NEVER A FLOAT — `Parameter` refuses a float on a money
            # parameter because this value lives in `jsonb`, where no column
            # type can catch it (hard rule 2).
            default="2.0000",
        ),
        Parameter(
            name="normalise_for_days",
            type=PARAM_TOGGLE,
            label="Normalise for days",
            default=True,
        ),
        Parameter(
            name="include_one_off_items",
            type=PARAM_TOGGLE,
            label="Include one-off items",
            default=True,
        ),
        # ⚠ **THE CARD'S FOURTH ROW IS *WITHDRAWN, DO NOT BUILD* AND IT IS NOT
        # DECLARED HERE.** *Write to account notes* was struck through by the
        # specification itself to keep `BR-RBS-002` intact. It is named in this
        # comment rather than left out silently, so the next reader can see it
        # was considered and refused — which is what the card asks for: *"it
        # stays visible on the build sheet so a builder does not build it."*
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_FETCH, label=STEP_LABELS[STEP_FETCH], mode=MODE_SET, run=step_fetch_both_bills),
        Step(key=STEP_USAGE, label=STEP_LABELS[STEP_USAGE], mode=MODE_SET, run=step_compare_usage),
        Step(key=STEP_RATES, label=STEP_LABELS[STEP_RATES], mode=MODE_SET, run=step_compare_rates),
        Step(
            key=STEP_CHARGES,
            label=STEP_LABELS[STEP_CHARGES],
            mode=MODE_SET,
            run=step_compare_charges,
        ),
        Step(
            key=STEP_ONE_OFFS,
            label=STEP_LABELS[STEP_ONE_OFFS],
            mode=MODE_SET,
            run=step_find_one_offs,
        ),
        Step(key=STEP_METER, label=STEP_LABELS[STEP_METER], mode=MODE_SET, run=step_check_the_meter),
        # ⚠ THE ONLY PER-RECORD STEP — the card's own *per record (1)*.
        Step(key=STEP_RANK, label=STEP_LABELS[STEP_RANK], mode=MODE_PER_RECORD, run=step_rank_the_causes),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-019 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, prices nothing and posts no ledger line)
# gates: pytest tests/test_us_rbs_019_why_higher.py · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G20 (the seam implementers)
# exceptions: a rate change and a meter change are REPORTED and never PRICED — attributing dollars to either needs the old usage re-priced under the new tariff, and this Check does not re-price an issued bill (`BR-BIL-004`) · the *Write to account notes* parameter is WITHDRAWN by the card and is not declared · the 12-month average is a computed comparison rather than a document, and its divisor is the number of BILLS (a late fee on one bill in twelve averages to a twelfth) · `this_bill` and `account` are `ref:object` with no tenant-resolved DOMAIN, which is wave `T`'s to add (`BR-RBS-042`) — the domains this runbook needs are `account` and a new `bill` one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
