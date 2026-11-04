# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-028 (EP-RBS-05) — CR-075 wave S: runbook 16, *Rate change
#           preview* — six read steps that re-price a real, already-issued cycle
#           against a DRAFT schedule and issue nothing.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-011 ·
#           BR-RBS-012 · BR-RBS-019 · BR-RBS-020 · BR-RBS-021 · BR-RBS-023 (the
#           sums are a set step; the pricing is per record) · BR-RBS-039 ·
#           BR-RAT-031 (a NULL `effective_from` IS the draft) · BR-RAT-007 (the
#           version whose window contains the SERVICE date) · BR-BIL-004 (a
#           draft bill is freely replaced — the comparison is against ISSUED
#           bills) · CLAUDE.md hard rule 2 (money 4, percent 6, both shown 2) ·
#           hard rule 3 · B14 rules 31, 32, 33 · B4/B5 ❄️ FROZEN
# Questions:OQ-319 (whole bill or this schedule's portion — OPEN, and this
#           follows the answer BR-RAT-091's ratified figure was signed on)
# Tests:    06-backend/tests/test_us_rbs_028_rate_change_preview.py
# Impacts:  apps/runbooks/definitions/__init__.py · apps/rating/runbook_reads.py
#           · apps/runbooks/seams/rating_seam.py ·
#           apps/runbooks/seams/billing_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-116-rate-change-preview.md
# ───────────────────────────────────────────────────────
"""Runbook 16 — **Rate change preview**.

*What would this proposed tariff have done to last cycle's bills?* `RB-116`'s
own sentence: **run it before the board meeting, not after.**

⚠ **IT RE-PRICES A PAST CYCLE THROUGH THE REAL ENGINE AND ISSUES NOTHING.** No
bill number is consumed, no invoice moves, and the draft schedule is not made
current. `US-RBS-028`'s own reason is the whole design of this module: *"A second
pricing implementation here would tell a board something the product would not
then do."* Every figure comes out of `apps.rating.engine.price_period` — the same
call a bill makes — pointed at a version that is not in force by
`selectors.pricing_inputs_for_version`, which `DEF-434` split out for exactly
this.

WHAT IS COMPARED, AND WHY IT IS THE SCHEDULE'S OWN PORTION
------------------------------------------------------------
`OQ-319` — *whole bill, or this schedule's own portion?* — is OPEN, and rating
already answers it in shipped, finance-read code: `BR-RAT-091`'s ratified worked
example moves an 11 kgal household `$59.00 → $62.54`, which is `$59.00 × 1.06`
**exactly**, so the signed figure is the service's own portion before taxes,
before discounts and before every other service on the plan. This runbook
FOLLOWS that answer rather than choosing a second one: a rate-change preview and
a rate-change approval gate that measured different things would be two answers
to one question, on the two screens a utility files a rate case from.

So the **August** column is what the customer was actually charged for THIS
service — the issued bill's own usage and base lines — and **Under draft** is
that figure plus the difference the engine computes between the two versions.

⚠ **BOTH SIDES ARE PRICED BY THE ENGINE, AND THAT IS WHAT MAKES THE DIFFERENCE
HONEST.** The baseline is the version in force on the bill's own service date
(`BR-RAT-007`), priced from the bill's own metered quantity; the proposed side is
the draft, priced from the same quantity. Because the DIFFERENCE travels rather
than the proposed total alone, the base-charge precedence (`DEF-154` — the plan's
figure where it states one, the schedule's where it does not) cancels out of the
subtraction instead of appearing as a change nobody proposed.

⚠ **AND THE RUN SAYS HOW WELL IT REPRODUCES THE PAST.** For every bill, the
baseline pass is compared against what the customer was actually charged, and
the count that did not agree to the cent is on the screen. A preview that cannot
state its own error is a preview nobody should show a board — hard-won law 7: *a
declared blind spot with no number attached is indistinguishable from an empty
one.*

THREE THINGS IT DELIBERATELY DOES NOT DO
------------------------------------------
1. **It does not re-compute tax.** That is the stated scope above, and r10
   labels its own panel the same way: *"Typical bill · this service's portion"*.
2. **It does not price a bill the draft does not touch.** A bill with no line of
   this service is still counted — it is *unchanged*, which is a finding, and
   dropping it would make the denominator of every percentage wrong.
3. **It does not adopt anything.** There is no port on a Check; the draft stays
   a draft and `BR-RAT-083`'s activation is a person's act on the Plans & Rates
   screen.
"""

from __future__ import annotations

import datetime as dt
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
    PARAM_REF_OBJECT,
    PARAM_REF_SETTING,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import billing_seam, customers_seam, rating_seam, tenancy_seam

KEY = "rate_change_preview"

ZERO = Decimal("0")
HUNDRED = Decimal("100")

# ── the six steps, in the card's own order ────────────────────────────────

STEP_DRAFT = "load_the_draft_schedule"
STEP_CYCLE = "load_the_cycle_as_it_was_billed"
STEP_REPRICE = "reprice_every_bill_under_the_draft"
STEP_COMPARE = "compare_to_the_issued_bill"
STEP_DISTRIBUTE = "distribute_and_group_the_changes"
STEP_REVENUE = "sum_revenue_by_service"

STEP_LABELS = {
    STEP_DRAFT: "Load the draft schedule",
    STEP_CYCLE: "Load the cycle as it was billed",
    STEP_REPRICE: "Re-price every bill under the draft",
    STEP_COMPARE: "Compare to the issued bill",
    STEP_DISTRIBUTE: "Distribute and group the changes",
    STEP_REVENUE: "Sum revenue by service",
}

# ── the five bands the card draws, in its own order ───────────────────────

BAND_DOWN_LARGE = "down_more_than"
BAND_DOWN = "down_small"
BAND_WITHIN = "within"
BAND_UP = "up_small"
BAND_UP_LARGE = "up_more_than"
BANDS = (BAND_DOWN_LARGE, BAND_DOWN, BAND_WITHIN, BAND_UP, BAND_UP_LARGE)

#: The card's *Down 5–15% · Within 5% · Up 5–15%* — the inner boundary of the
#: distribution. ⚠ **A JUDGMENT, RECORDED IN THE DECISION LOG.** The card fixes
#: the OUTER band at a parameter (*Call it large above ± 15%*) and draws the
#: inner one as a literal `5%` with no knob beside it, so it is a constant here
#: and not an invented parameter; if a tenant ever asks, this is the number it
#: sets.
SMALL_MOVE = Decimal("5")

OUTCOME_UP_LARGE = "up_more_than_the_threshold"
OUTCOME_UP = "up"
OUTCOME_DOWN = "down"
OUTCOME_UNCHANGED = "unchanged"
OUTCOME_NOT_PRICED = "not_priced"

OUTCOME_LABELS = {
    OUTCOME_UP_LARGE: "Up more than the threshold",
    OUTCOME_UP: "Up",
    OUTCOME_DOWN: "Down",
    OUTCOME_UNCHANGED: "Unchanged",
    OUTCOME_NOT_PRICED: "Not priced",
}

#: `BR-RBS-011` — every finding names its fix, tenant-relative (the shell
#: prefixes the utility). `plans-rates` is where a draft is edited or activated
#: and is in `SIDEBAR_DESTINATIONS`; `billing` is where the cycle lives.
#: Verified 2026-09-07.
FIX_PLANS = "plans-rates"
FIX_BILLING = "billing"


def _walked(ctx, subjects) -> list[dict[str, Any]]:
    """The cycle's bills for the subjects a GUARD did not take out.

    ⚠ **`BR-RBS-012`: A GUARD IS EVALUATED BEFORE ANY STEP AND A GUARDED RECORD
    IS SEEN BY NONE OF THEM — AND THIS RUNBOOK BROKE THAT IN THE SAME WAY
    RUNBOOK 12 DID** (`DEF-RBS-4395`, found by running both on a real utility).
    The re-price and the sums walked the whole cycle while the per-record step
    walked the subjects the executor hands in, so on the seeded utility the run
    drew **47 bills up 5–15% and +$339.04 of revenue over a table with no rows
    in it** — every one of those 49 bills belongs to a sample account the guard
    had correctly removed.

    Reading the subjects the executor hands each set step is the fix, and it is
    the only reading that cannot drift: the executor decides who was walked, so
    no step gets to decide it a second time.
    """
    wanted = {str(one.subject_id) for one in subjects}
    return [
        bill
        for bill in ((ctx.set_results.get("_cycle") or {}).get("bills") or [])
        if str(bill.get("bill_id")) in wanted
    ]


@dataclass
class _StepResult:
    found: dict[str, Any] = field(default_factory=dict)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"reached": True, "found": dict(self.found), "checked": dict(self.checked)}


def _decimal(raw: Any) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _stored(amount: Decimal) -> str:
    """Four decimals for money. Display rounds; storage does not (hard rule 2)."""
    return f"{amount.quantize(Decimal('0.0001')):f}"


def _percent(value: Decimal) -> str:
    """Six decimals for a percentage — hard rule 2, displayed at two."""
    return f"{value.quantize(Decimal('0.000001')):f}"


def _date(raw: Any) -> dt.date | None:
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def _days(start: Any, end: Any) -> int:
    """The bill's OWN cycle length, inclusive of both ends.

    ⚠ **HANDED TO THE ENGINE RATHER THAN ASSUMED.** A re-price against a nominal
    30 days misprices every proration and every time-of-use window in the
    ladder, silently, on exactly the bills a board would ask about.
    """
    first, last = _date(start), _date(end)
    if first is None or last is None:
        return 30
    return max((last - first).days + 1, 1)


def _priced_by_this_schedule(bill: dict[str, Any], service: str, versions: set[str]) -> bool:
    """Was this bill's usage for this service priced by the DRAFT's own schedule?

    ⚠ **THE REAL RUN FOUND THIS AND NO TEST COULD HAVE.** On the seeded utility
    the July cycle's water lines carry a version of the *sample* residential
    schedule, and the draft belongs to the utility's own. Re-pricing them
    anyway produced a confident **+$339.04 (+7.2%) across 49 bills** for a
    change none of those customers would ever have seen — and the run's own
    error bar was already saying so, *0 of 49 reproduced*, which is what a
    number beside a claim is for.

    `invoice_lines.tariff_version_id` is stamped at issue and frozen
    (`billing_seam.issued_bills_for_account`'s own note: *"the only honest
    answer to did the rate change"*), so this is read rather than inferred. A
    line carrying no version at all is treated as NOT on this schedule: a
    preview may not claim a bill it cannot place.
    """
    if not versions:
        return False
    return any(
        str(line.get("service") or "") == service
        and str(line.get("kind") or "") == "usage"
        and str(line.get("tariff_version_id") or "") in versions
        for line in (bill.get("lines") or [])
    )


def _usage_of(lines) -> Decimal:
    """What the engine charged for USAGE alone, out of its own lines."""
    return sum(
        (_decimal(one.get("amount")) or ZERO for one in lines if str(one.get("kind")) == "usage"),
        ZERO,
    )


def _portion(bill: dict[str, Any], service: str) -> tuple[Decimal, Decimal | None, str]:
    """WHAT THIS SERVICE COST ON THE BILL AS ISSUED, and what it measured.

    Returns `(amount, quantity, unit)` over the bill's `usage` and `base` lines
    of this service — the schedule's own portion, which is the scope
    `BR-RAT-091`'s ratified `$59.00 → $62.54` was signed on (`OQ-319`).

    ⚠ **A `None` QUANTITY IS NOT A ZERO.** A base line carries no quantity at
    all, and a usage line whose quantity is missing is a bill this preview
    cannot re-price — counted rather than priced at nought, which is
    `rate_change_impact`'s own rule and its reason: averaging an unmeasurable
    row in as `0.00%` drags the worst case toward the middle, *"the one
    direction a rate-change gate must never be wrong in"*.
    """
    amount = ZERO
    quantity: Decimal | None = None
    unit = ""
    for line in bill.get("lines") or []:
        if str(line.get("service") or "") != service:
            continue
        kind = str(line.get("kind") or "")
        if kind not in ("usage", "base"):
            continue
        amount += _decimal(line.get("amount")) or ZERO
        if kind == "usage":
            measured = _decimal(line.get("quantity"))
            if measured is not None:
                quantity = (quantity or ZERO) + measured
                unit = unit or str(line.get("unit") or "")
    return amount, quantity, unit


def _issued_usage(bill: dict[str, Any], service: str) -> Decimal:
    """The USAGE half of what the customer was charged for this service.

    ⚠ **THE REPRODUCTION CHECK COMPARES USAGE WITH USAGE, AND THAT IS WHY IT
    MEANS ANYTHING.** A first build compared the engine's whole priced portion
    against the issued usage AND base, and reported **0 of 49 reproduced** on
    the seeded utility — a true statement about a comparison that could never
    balance. `DEF-154`'s precedence is why: a base charge is the PLAN's figure
    where the plan states one and the schedule's where it does not, so a bill
    charging the plan's `$8.00` and an engine pass carrying the schedule's is a
    fixed offset, not a modelling error. The offset is REPORTED on its own
    rather than folded into an error bar that would then only ever say *no*.
    """
    return sum(
        (
            _decimal(line.get("amount")) or ZERO
            for line in (bill.get("lines") or [])
            if str(line.get("service") or "") == service
            and str(line.get("kind") or "") == "usage"
        ),
        ZERO,
    )


# ── step 1 · the draft ────────────────────────────────────────────────────


def step_load_the_draft_schedule(ctx, subjects) -> dict[str, Any]:
    """1 · **Blocks, base, minimums as drafted** — and what each of them replaces.

    ⚠ **THE CLAUSE LIST IS READ HERE ONCE AND IS THE *Why* ON EVERY MOVER.**
    `RB-116`'s design note: *"Why on each mover names the clause of the draft
    that did it, so a tariff can be adjusted before it is adopted rather than
    defended after."* `TC-RBS-028.1`'s *must first fail on* is **a total with no
    per-clause attribution — a board cannot act on it**.

    ⚠ **A DRAFT WITH NOTHING ACTIVATED BEHIND IT IS A STATED ABSENCE, NOT A
    ZERO.** `_baseline_version`'s own reason: *"a version compared with itself
    reports `0.00%` and that is the one answer this analysis must never
    invent."* The run reports `comparable: False` and prices nothing.
    """
    change = ctx.set_results.get("_change") or {}
    clauses = list(change.get("changes") or [])
    return _StepResult(
        found={"clauses": clauses},
        checked={
            "schedule": change.get("label"),
            "service": change.get("service"),
            "unit": change.get("unit"),
            "comparable": bool(change.get("comparable")),
            "clauses_that_moved": len(clauses),
            "clause_kinds": sorted({str(one.get("clause") or "") for one in clauses}),
            # ⚠ **THE SERVICE IS THE SCHEDULE'S OWN AND THE PARAMETER DOES NOT
            # NARROW IT.** A tariff belongs to exactly one service, so picking a
            # second one on the setup screen could only disagree with the draft.
            # The card draws the dropdown; this says what it does.
            "service_comes_from": "the schedule the draft belongs to",
            "service_asked_for": str(ctx.params.get("services") or ""),
        },
    ).as_dict()


# ── step 2 · the cycle as it was billed ───────────────────────────────────


def step_load_the_cycle_as_it_was_billed(ctx, subjects) -> dict[str, Any]:
    """2 · **Every account's usage, days and plan** — as ISSUED.

    ⚠ **ISSUED, NEVER A DRAFT** (`BR-BIL-004`). A draft bill is freely replaced
    and discarded, so re-pricing one would show a board a proposal against a
    document no customer ever received.

    ⚠ **A BILL WITH NO LINE OF THIS SERVICE IS COUNTED, NOT DROPPED.** It is a
    bill the draft does not touch — the card's own **88 Unchanged** tile — and
    removing it would make the denominator of every percentage on the screen
    wrong.
    """
    cycle = ctx.set_results.get("_cycle") or {}
    service = str((ctx.set_results.get("_change") or {}).get("service") or "")
    bills = _walked(ctx, subjects)
    versions = set(ctx.set_results.get("_schedule_versions") or ())
    on_this_schedule = [one for one in bills if _priced_by_this_schedule(one, service, versions)]
    with_service = sum(1 for one in on_this_schedule if _portion(one, service)[1] is not None)
    no_quantity = sum(
        1
        for one in on_this_schedule
        if _portion(one, service)[1] is None and _portion(one, service)[0] != ZERO
    )
    return _StepResult(
        found={},
        checked={
            "bills_in_the_cycle": cycle.get("bills_in_the_cycle", 0),
            # ⚠ **THE GUARDED ONES ARE COUNTED AND NOT LOOKED AT** (`BR-RBS-012`,
            # `DEF-RBS-4395`). A revenue figure over a cycle that is mostly demo
            # data would be the most convincing wrong number this product could
            # put in front of a board.
            "of_those_a_guard_took_out": cycle.get("bills_in_the_cycle", 0) - len(bills),
            "re_priced_after_the_guards": len(bills),
            # ⚠ **COUNTED, NEVER DROPPED** — `RB-116` declares no *Never
            # include* row and this runbook acts on nothing, so a sample bill is
            # re-priced like any other and the count says how much of the answer
            # is demo data. On a trial tenant that number is most of the cycle,
            # and a board reading the preview needs to know it.
            "bills_belonging_to_a_sample_account": len(
                ctx.set_results.get("_sample_bills") or frozenset()
            ),
            "lines_of_this_service": cycle.get("lines_of_this_service", 0),
            "bills_with_a_metered_quantity": with_service,
            "bills_charged_for_this_service_with_no_quantity": no_quantity,
            # ⚠ **A BILL ON ANOTHER SCHEDULE IS NOT A BILL THIS DRAFT CHANGES**,
            # and it is counted rather than re-priced. Read off
            # `invoice_lines.tariff_version_id`, stamped at issue and frozen.
            "bills_priced_by_this_schedule": len(on_this_schedule),
            "bills_priced_by_another_schedule": len(bills) - len(on_this_schedule),
            "bills_this_draft_does_not_touch": len(bills) - with_service - no_quantity,
            "period_start": cycle.get("period_start"),
            "period_end": cycle.get("period_end"),
            "compare_to": "the bills actually issued",
        },
    ).as_dict()


# ── step 3 · the re-price ─────────────────────────────────────────────────


def step_reprice_every_bill_under_the_draft(ctx, subjects) -> dict[str, Any]:
    """3 · **The real pricing engine, not a spreadsheet** — and both sides of it.

    ⚠ **ONE SEAM CALL FOR THE WHOLE CYCLE, AND THE ENGINE INSIDE IT RUNS ONCE
    PER BILL** (`NFR-3`). The version and its projection are read ONCE; asking
    per bill would be four queries times the biggest cycle a utility has, which
    is `DEF-PAY-4221`'s shape on the screen a rate case is filed from.

    ⚠ **THE COMPARISON ARITHMETIC LIVES HERE, ONCE.** Step 4 draws the row and
    steps 5 and 6 sum it, and all three read THIS map — because the same
    subtraction written in two steps is two implementations of one figure, which
    is the fault this whole runbook exists to avoid one level up.

    ⚠ **`reproduced_the_issued_amount` IS THE RUN'S OWN ERROR BAR.** The
    baseline pass prices what the customer was ALREADY charged; where it does
    not agree to the cent, the preview is modelling something the issued bill
    did differently — a discount, a plan floor, a mid-period change — and the
    count of those is reported rather than absorbed.
    """
    change = ctx.set_results.get("_change") or {}
    service = str(change.get("service") or "")
    bills = _walked(ctx, subjects)
    # ⚠ **THE RE-PRICE HAPPENS HERE AND NOT IN `resolve`, WHICH IS `DEF-RBS-4395`
    # SAID ONCE MORE.** Guards run BETWEEN `resolve` and the first step, so
    # anything priced in `resolve` is priced for records this runbook has been
    # told not to look at — and on the seeded utility that was all 49 of them.
    versions = set(ctx.set_results.get("_schedule_versions") or ())
    rows = []
    for bill in bills:
        if not _priced_by_this_schedule(bill, service, versions):
            continue
        _amount, quantity, unit = _portion(bill, service)
        if quantity is None:
            continue
        rows.append(
            {
                "id": str(bill.get("bill_id")),
                "quantity": str(quantity),
                "unit": unit,
                "currency": bill.get("currency") or "",
                "cycle_days": _days(bill.get("period_start"), bill.get("period_end")),
                "service_days": _days(bill.get("period_start"), bill.get("period_end")),
            }
        )
    answer = (
        rating_seam.reprice_under_draft(
            version_id=ctx.params.get("proposed_schedule"),
            rows=rows,
            service_date=ctx.set_results.get("_service_date"),
        )
        if rows and change.get("comparable")
        else {"priced": {}, "unpriced": {}, "comparable": bool(change.get("comparable"))}
    )
    ctx.set_results["_priced"] = answer
    priced = answer.get("priced") or {}
    unpriced = dict(answer.get("unpriced") or {})
    threshold = _decimal(ctx.params.get("call_it_large_above")) or Decimal("15")

    compared: dict[str, dict[str, Any]] = {}
    reproduced = 0
    not_reproduced = 0
    base_offset = ZERO
    for bill in bills:
        bill_id = str(bill.get("bill_id") or "")
        as_issued, quantity, unit = _portion(bill, service)
        row = priced.get(bill_id)
        if row is None:
            # ⚠ **THREE DIFFERENT SILENCES, AND ONLY ONE OF THEM IS A GAP.** A
            # bill with no usage of this service and a bill priced by ANOTHER
            # schedule are both *unchanged* — the draft does not reach them, and
            # that is a finding. A bill this draft DOES reach and the engine
            # refused is `not_priced`, which is a hole in the answer and is
            # counted as one.
            on_this_schedule = _priced_by_this_schedule(bill, service, versions)
            compared[bill_id] = {
                "outcome": (
                    OUTCOME_NOT_PRICED
                    if on_this_schedule and quantity is not None
                    else OUTCOME_UNCHANGED
                ),
                "as_issued": _stored(as_issued),
                "under_draft": _stored(as_issued),
                "change": _stored(ZERO),
                "change_pct": None,
                "quantity": None if quantity is None else _stored(quantity),
                "unit": unit,
                "reason": unpriced.get(
                    bill_id,
                    "no charge for this service on this bill"
                    if quantity is None
                    else "this bill was priced by another schedule",
                ),
            }
            continue
        change = _decimal(row.get("change")) or ZERO
        under_draft = as_issued + change
        # ⚠ USAGE AGAINST USAGE — see `_issued_usage`. The base charge sits
        # outside the comparison because `DEF-154` makes it the PLAN's figure
        # where the plan states one, and both engine passes carry the
        # SCHEDULE's, so it cancels out of the change and would only ever make
        # this check say *no*.
        baseline = _usage_of(row.get("lines_before") or [])
        billed_usage = _issued_usage(bill, service)
        if abs(baseline - billed_usage) <= Decimal("0.01"):
            reproduced += 1
        else:
            not_reproduced += 1
        base_offset += (as_issued - billed_usage) - _base_of(row.get("lines_before") or [])
        pct = (change / as_issued * HUNDRED) if as_issued > ZERO else None
        compared[bill_id] = {
            "outcome": _band_outcome(pct, threshold),
            "as_issued": _stored(as_issued),
            "under_draft": _stored(under_draft),
            "change": _stored(change),
            "change_pct": None if pct is None else _percent(pct),
            "quantity": _stored(_decimal(row.get("quantity")) or ZERO),
            "unit": row.get("unit") or unit,
            "baseline_priced": row.get("before"),
            "reproduced_the_issued_amount": abs(baseline - billed_usage) <= Decimal("0.01"),
            "lines_before": row.get("lines_before") or [],
            "lines_after": row.get("lines_after") or [],
            "reason": "",
        }
    ctx.set_results["_compared"] = compared
    return _StepResult(
        found={},
        checked={
            "bills_priced": len(priced),
            "bills_that_could_not_be_priced": len(unpriced),
            "why_they_could_not_be_priced": sorted(set(unpriced.values())),
            "priced_by": answer.get("priced_by"),
            "baseline_reproduced_the_issued_usage": reproduced,
            "baseline_did_not_reproduce_the_issued_usage": not_reproduced,
            "agreement_tolerance": "0.01",
            # ⚠ **THE BASE CHARGE THIS PREVIEW DOES NOT MODEL, AS A FIGURE**
            # (`DEF-154`). A plan that states its own base and a schedule that
            # states another are BOTH lawful, and the engine pass here carries
            # the schedule's. It cancels out of every CHANGE — both passes carry
            # it — so it moves no percentage on the screen; it is printed so a
            # reader can see how much of the column is a charge the comparison
            # holds constant rather than one it re-priced.
            "base_charge_held_constant": _stored(base_offset),
        },
    ).as_dict()


def _base_of(lines) -> Decimal:
    """What the engine charged as a BASE charge, out of its own lines."""
    return sum(
        (_decimal(one.get("amount")) or ZERO for one in lines if str(one.get("kind")) == "base"),
        ZERO,
    )


def _band_outcome(pct: Decimal | None, threshold: Decimal) -> str:
    if pct is None or pct == ZERO:
        return OUTCOME_UNCHANGED
    if pct > threshold:
        return OUTCOME_UP_LARGE
    return OUTCOME_UP if pct > ZERO else OUTCOME_DOWN


# ── step 4 · line by line, then total ─────────────────────────────────────


def step_compare_to_the_issued_bill(ctx, subject) -> dict[str, Any]:
    """4 · **Line by line, then total** — one bill, one row.

    ⚠ **THE ONLY PER-RECORD STEP** (`BR-RBS-023`, and `US-RBS-028` §1: *"per-record
    pricing plus a set step for the sums"*) — one bill, one savepoint (hard-won
    law 14), one row on the biggest-movers table.

    ⚠ **THE *Why* NAMES A CLAUSE OF THE DRAFT AND NEVER A RULE ID** (B14 rule
    32). The clause list is step 1's; which of them touched THIS bill is decided
    by where its own metered quantity falls — a block boundary that moved above
    the quantity this account used did not move this bill, and saying it did is
    the kind of wrong a tariff gets defended on.

    ⚠ **NO DATABASE ID REACHES A DRAWN CELL** (B14 rule 31): the account is its
    NAME, the bill is its NUMBER.
    """
    bill_id = str(subject.subject_id)
    compared = (ctx.set_results.get("_compared") or {}).get(bill_id) or {}
    facts = (ctx.set_results.get("_bills") or {}).get(bill_id) or {}
    change = ctx.set_results.get("_change") or {}
    quantity = _decimal(compared.get("quantity"))
    clause = _clause_for(change.get("changes") or [], quantity, compared)
    moved = _lines_that_moved(compared)
    return {
        "outcome": str(compared.get("outcome") or OUTCOME_UNCHANGED),
        "reason": clause,
        "decided_by_rule": (
            "Both sides priced by the rating engine from the quantity the bill was issued on"
        ),
        "fix_route": FIX_PLANS if compared.get("change_pct") else FIX_BILLING,
        "data": {
            "account": facts.get("account_label") or facts.get("invoice_no") or "",
            "account_type": facts.get("account_type") or "",
            "invoice_no": facts.get("invoice_no"),
            "as_issued": compared.get("as_issued"),
            "under_draft": compared.get("under_draft"),
            "change": compared.get("change"),
            "change_pct": compared.get("change_pct"),
            "quantity": compared.get("quantity"),
            "unit": compared.get("unit"),
            "currency": facts.get("currency") or "",
            "clause": clause,
            # Line by line — which charges moved on THIS bill, for the run
            # record and the download. Nothing draws it as a column.
            "lines_that_moved": moved,
            "reproduced_the_issued_amount": compared.get("reproduced_the_issued_amount"),
        },
    }


def _clause_for(clauses, quantity: Decimal | None, compared: dict[str, Any]) -> str:
    """Which clause of the draft moved THIS bill, in the card's own words.

    The clause with the HIGHEST `from_quantity` at or below what this account
    used is the one a customer would point at — a new top block above 20,000
    gallons is the story on a farm and irrelevant on a flat, and both are true
    of the same draft.
    """
    if not compared.get("change_pct") or _decimal(compared.get("change")) == ZERO:
        return "No change under this draft"
    reached = [
        one
        for one in clauses
        if one.get("from_quantity") is None
        or (quantity is not None and quantity >= (_decimal(one.get("from_quantity")) or ZERO))
    ]
    if not reached:
        return "The draft changes nothing this bill reached"
    best = max(
        reached,
        key=lambda one: _decimal(one.get("from_quantity")) or Decimal("-1"),
    )
    return str(best.get("sentence") or "The draft moved this bill")


def _lines_that_moved(compared: dict[str, Any]) -> list[dict[str, Any]]:
    """The engine's own lines, before and after, where the amount is not the same."""
    before = {str(one.get("description")): one for one in compared.get("lines_before") or []}
    after = {str(one.get("description")): one for one in compared.get("lines_after") or []}
    moved: list[dict[str, Any]] = []
    for description in sorted(set(before) | set(after)):
        was = (before.get(description) or {}).get("amount")
        now = (after.get(description) or {}).get("amount")
        if was == now:
            continue
        moved.append({"description": description, "before": was, "after": now})
    return moved


# ── step 5 · the distribution and the grouping ────────────────────────────


def step_distribute_and_group_the_changes(ctx, subjects) -> dict[str, Any]:
    """5 · **By size of change and by account type** — the card's five rows.

    ⚠ **FIVE ROWS RATHER THAN A HISTOGRAM, WHICH IS THE CARD'S OWN DESIGN
    NOTE:** *"a board reads '121 bills go up by more than 15%' faster than a
    chart, and the one accent bar marks the row that will generate calls."*
    """
    threshold = _decimal(ctx.params.get("call_it_large_above")) or Decimal("15")
    compared = ctx.set_results.get("_compared") or {}
    bands = {one: 0 for one in BANDS}
    for row in compared.values():
        pct = _decimal(row.get("change_pct"))
        if pct is None or pct == ZERO:
            bands[BAND_WITHIN] += 1
            continue
        if pct <= -threshold:
            bands[BAND_DOWN_LARGE] += 1
        elif pct <= -SMALL_MOVE:
            bands[BAND_DOWN] += 1
        elif pct < SMALL_MOVE:
            bands[BAND_WITHIN] += 1
        elif pct <= threshold:
            bands[BAND_UP] += 1
        else:
            bands[BAND_UP_LARGE] += 1

    by_type: dict[str, dict[str, Any]] = {}
    facts = ctx.set_results.get("_bills") or {}
    for bill_id, row in compared.items():
        kind = str((facts.get(bill_id) or {}).get("account_type") or "Not set")
        held = by_type.setdefault(kind, {"bills": 0, "as_issued": ZERO, "under_draft": ZERO})
        held["bills"] += 1
        held["as_issued"] += _decimal(row.get("as_issued")) or ZERO
        held["under_draft"] += _decimal(row.get("under_draft")) or ZERO
    grouped = {
        kind: {
            "bills": held["bills"],
            "as_issued": _stored(held["as_issued"]),
            "under_draft": _stored(held["under_draft"]),
            "change_pct": (
                _percent(
                    (held["under_draft"] - held["as_issued"]) / held["as_issued"] * HUNDRED
                )
                if held["as_issued"] > ZERO
                else None
            ),
        }
        for kind, held in sorted(by_type.items())
    }
    ctx.set_results["_bands"] = bands
    ctx.set_results["_by_type"] = grouped
    return _StepResult(
        found={"bands": bands, "by_account_type": grouped},
        checked={
            "call_it_large_above_percent": _percent(threshold),
            "inner_band_percent": _percent(SMALL_MOVE),
            "account_types_grouped": len(grouped),
            # ⚠ COUNTED, hard-won law 7 — an account with no type is a real
            # state (`account_types_for` answers only what customers holds) and
            # a group called *Not set* is honest where silence is not.
            "bills_with_no_account_type": grouped.get("Not set", {}).get("bills", 0),
            "group_by": str(ctx.params.get("group_by") or ""),
        },
    ).as_dict()


# ── step 6 · what the change is worth ─────────────────────────────────────


def step_sum_revenue_by_service(ctx, subjects) -> dict[str, Any]:
    """6 · **What the change is worth, and to whom.**

    ⚠ **ONE SERVICE, BECAUSE A DRAFT BELONGS TO ONE SCHEDULE AND A SCHEDULE TO
    ONE SERVICE.** The card's toggle is *Revenue by service*, and the honest
    answer for a single draft is one row with the service named on it rather
    than a table of eleven with ten zeros in it.

    ⚠ **THE FIGURE IS `priced`, NEVER `posting`.** Nothing here was posted,
    cleared or even issued — `BR-REP-001` makes the basis required on every
    money tile precisely so a preview cannot be read as a book.
    """
    compared = ctx.set_results.get("_compared") or {}
    service = str((ctx.set_results.get("_change") or {}).get("service") or "")
    as_issued = sum((_decimal(one.get("as_issued")) or ZERO for one in compared.values()), ZERO)
    change = sum((_decimal(one.get("change")) or ZERO for one in compared.values()), ZERO)
    pct = (change / as_issued * HUNDRED) if as_issued > ZERO else None
    ctx.set_results["_revenue"] = {
        "service": service,
        "as_issued": _stored(as_issued),
        "change": _stored(change),
        "change_pct": None if pct is None else _percent(pct),
    }
    return _StepResult(
        found={"revenue": ctx.set_results["_revenue"]},
        checked={
            "service": service,
            "revenue_as_issued": _stored(as_issued),
            "revenue_change": _stored(change),
            "revenue_change_percent": None if pct is None else _percent(pct),
            "basis": "priced",
            "revenue_by_service_asked_for": bool(ctx.params.get("revenue_by_service", True)),
            "services_in_this_preview": 1 if service else 0,
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def report(view) -> list[Block]:
    """`RB-116`'s own blocks — **KPIs · Ranked · Records · Breakdown ·
    Downloads** — and no verdict, which is the card's own list.

    ⚠ **THE RECORDS TABLE IS THE *BIGGEST MOVERS*, RANKED BY THE SIZE OF THE
    MOVE AND CAPPED AT THE PARAMETER.** A bill that did not move is counted in
    the tiles and the distribution and is not drawn: the card's own heading is
    *Biggest movers · 50*.
    """
    revenue = view.set_results.get("_revenue") or {}
    bands = view.set_results.get("_bands") or {}
    by_type = view.set_results.get("_by_type") or {}
    change = view.set_results.get("_change") or {}
    currency = str(view.set_results.get("_currency") or "")
    cycle_label = str(view.set_results.get("_cycle_label") or "As issued")
    limit = int(view.set_results.get("_movers") or 50)
    threshold = view.set_results.get("_threshold") or "15"

    by_outcome: dict[str, int] = {}
    for record in view.records:
        by_outcome[record.outcome] = by_outcome.get(record.outcome, 0) + 1
    up = by_outcome.get(OUTCOME_UP, 0) + by_outcome.get(OUTCOME_UP_LARGE, 0)
    down = by_outcome.get(OUTCOME_DOWN, 0)
    # ⚠ **UNCHANGED IS NOT *COULD NOT BE PRICED*, AND FOLDING THE TWO WOULD BE
    # HARD-WON LAW 7 ON THE ONE SCREEN A RATE CASE IS FILED FROM.** A bill the
    # draft does not touch is a finding; a bill the engine refused is a gap, and
    # a board reading one as the other would file on a number that never
    # measured those accounts.
    unchanged = by_outcome.get(OUTCOME_UNCHANGED, 0)
    not_priced = by_outcome.get(OUTCOME_NOT_PRICED, 0)
    large = by_outcome.get(OUTCOME_UP_LARGE, 0)

    movers = sorted(
        (one for one in view.records if one.data.get("change_pct")),
        key=lambda one: abs(_decimal(one.data.get("change_pct")) or ZERO),
        reverse=True,
    )[: max(limit, 1)]

    return [
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "revenue",
                        "label": "Revenue",
                        "value": (
                            {
                                "kind": "money",
                                "amount": str(revenue.get("change")),
                                "currency": currency,
                            }
                            if revenue.get("change") is not None
                            else {"kind": "text", "text": "—"}
                        ),
                        # ⚠ `priced`, NEVER `posting` — nothing here was issued,
                        # posted or cleared (`DEF-RBS-4350`).
                        "basis": "priced",
                        "detail": (
                            f"{revenue.get('change_pct') and _shown(revenue['change_pct'])}%"
                            if revenue.get("change_pct")
                            else "Nothing could be priced"
                        ),
                    },
                    {
                        "id": "up",
                        "label": "Bills up",
                        "value": {"kind": "text", "text": str(up)},
                    },
                    {
                        "id": "down",
                        "label": "Bills down",
                        "value": {"kind": "text", "text": str(down)},
                    },
                    {
                        "id": "unchanged",
                        "label": "Unchanged",
                        "value": {"kind": "text", "text": str(unchanged)},
                        "detail": (
                            f"{not_priced} could not be priced"
                            if not_priced
                            else "This draft does not touch them"
                        ),
                    },
                    {
                        "id": "up_large",
                        "label": f"Up more than {_shown(threshold)}%",
                        "value": {"kind": "text", "text": str(large)},
                        "detail": "The row that will generate calls",
                    },
                ]
            },
        ),
        Block(
            block="ranked",
            payload={
                "heading": "How bills move",
                "rows": [
                    {
                        "id": band,
                        "label": _band_label(band, threshold),
                        "weight": bands.get(band, 0),
                        "value": {"kind": "text", "text": str(bands.get(band, 0))},
                    }
                    for band in BANDS
                ],
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "account", "label": "Account"},
                    {"key": "type", "label": "Type"},
                    {"key": "as_issued", "label": cycle_label, "numeric": True},
                    {"key": "under_draft", "label": "Under draft", "numeric": True},
                    {"key": "change", "label": "Change"},
                    {"key": "why", "label": "Why"},
                ],
                "rows": [
                    {
                        "id": f"bill-{index}",
                        "cells": {
                            "account": {
                                "kind": "text",
                                "text": str(record.data.get("account") or ""),
                            },
                            "type": {
                                "kind": "text",
                                "text": str(record.data.get("account_type") or "—"),
                            },
                            "as_issued": {
                                "kind": "money",
                                "amount": str(record.data.get("as_issued") or "0.0000"),
                                "currency": str(record.data.get("currency") or currency),
                            },
                            "under_draft": {
                                "kind": "money",
                                "amount": str(record.data.get("under_draft") or "0.0000"),
                                "currency": str(record.data.get("currency") or currency),
                            },
                            "change": {
                                "kind": "percent",
                                # PERCENT POINTS: `30.400000` means 30.40%.
                                # Stored to six and displayed at two (hard rule 2).
                                "value": str(record.data.get("change_pct") or "0.000000"),
                                "basis": "points",
                                "direction": _direction(record.data.get("change_pct")),
                                "signed": True,
                            },
                            "why": {"kind": "text", "text": record.reason},
                        },
                        "meta": {
                            "decided_by_rule": record.decided_by_rule,
                            "outcome": record.outcome,
                            "invoice_no": record.data.get("invoice_no"),
                        },
                    }
                    for index, record in enumerate(movers, start=1)
                ],
                "total": len(movers),
                "empty": {
                    "title": "This draft changes nothing on that cycle.",
                    "helper": (
                        f"{len(view.records)} bills were re-priced against "
                        f"{change.get('label') or 'the draft'}."
                    ),
                },
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "By account type",
                "columns": [
                    {"key": "type", "label": "Type"},
                    {"key": "bills", "label": "Bills", "numeric": True},
                    {"key": "as_issued", "label": cycle_label, "numeric": True},
                    {"key": "under_draft", "label": "Under draft", "numeric": True},
                    {"key": "change", "label": "Change"},
                ],
                "rows": [
                    {
                        "id": f"type-{index}",
                        "cells": {
                            "type": {"kind": "text", "text": kind},
                            "bills": {"kind": "text", "text": str(row["bills"])},
                            "as_issued": {
                                "kind": "money",
                                "amount": str(row["as_issued"]),
                                "currency": currency,
                            },
                            "under_draft": {
                                "kind": "money",
                                "amount": str(row["under_draft"]),
                                "currency": currency,
                            },
                            "change": (
                                {
                                    "kind": "percent",
                                    "value": str(row["change_pct"]),
                                    "basis": "points",
                                    "direction": _direction(row["change_pct"]),
                                    "signed": True,
                                }
                                if row.get("change_pct")
                                else {"kind": "text", "text": "—"}
                            ),
                        },
                    }
                    for index, (kind, row) in enumerate(by_type.items(), start=1)
                ],
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "all", "label": "All bills", "format": "csv"},
                    {"id": "movers", "label": "Biggest movers", "format": "csv"},
                ]
            },
        ),
    ]


def _band_label(band: str, threshold: Any) -> str:
    """The card's own five labels, with the tenant's own threshold in them."""
    shown = _shown(threshold)
    return {
        BAND_DOWN_LARGE: f"Down more than {shown}%",
        BAND_DOWN: f"Down {_shown(SMALL_MOVE)}–{shown}%",
        BAND_WITHIN: f"Within {_shown(SMALL_MOVE)}%",
        BAND_UP: f"Up {_shown(SMALL_MOVE)}–{shown}%",
        BAND_UP_LARGE: f"Up more than {shown}%",
    }[band]


def _direction(pct: Any) -> str:
    value = _decimal(pct)
    if value is None or value == ZERO:
        return "flat"
    return "up" if value > ZERO else "down"


def _shown(value: Any) -> str:
    """A percentage a person reads — `15`, never `15.000000` (hard rule 2)."""
    amount = _decimal(value)
    if amount is None:
        return "—"
    trimmed = amount.quantize(Decimal("0.01")).normalize()
    return f"{trimmed:f}"


# ── the pinned scope, and the guard this runbook deliberately has NOT got ──
#
# ⚠ **`RB-116`'s SCOPE TABLE HAS NO *Never include* ROW, AND `RB-112`'s HAS ONE
# — THE ASYMMETRY IS THE CARD'S AND IT IS FOLLOWED RATHER THAN TIDIED AWAY.**
# `BR-RBS-014`'s sample rule is about an ACTION — *a sample record is never
# ACTED ON* — and this runbook acts on nothing at all. Guarding sample bills out
# would have a much worse failure mode than including them: on a trial tenant,
# where 72 of 78 accounts are sample records, every bill of the cycle would be
# removed and the board would be shown **"this draft changes nothing"** — the
# most convincing wrong answer this product could give, over a run that looked
# at nothing.
#
# ⚠ **SO THEY ARE COUNTED INSTEAD, WHICH IS `RB-119`'s POSTURE ONE OBJECT
# ALONG** — *"0 items, and 71 of 72 accounts here are sample records"*. Step 2
# says how many of the cycle's bills belong to sample accounts, so a reader can
# tell a trial tenant's preview from a real utility's without either of them
# being silently short. Recorded in the decision log with the figure it was
# taken on.


def resolve(ctx):
    """The pinned set: **every issued bill of the chosen cycle** (`BR-RBS-019`).

    ⚠ **THE COUNT ON THE SETUP SCREEN IS THIS FUNCTION'S ANSWER** — the card's
    *Re-prices 1,410 bills exactly as issued*.

    ⚠ **EVERY CROSS-MODULE READ THIS RUN MAKES HAPPENS HERE, ONCE** (`NFR-3`):
    the draft and its clause list, the cycle and its lines, the account labels
    and types, and the whole re-price. The steps then walk data rather than the
    database, which is what lets step 4 run once per bill without a query.

    ⚠ **A RUN WITH NO DRAFT OR NO CYCLE PINS NOTHING AND SAYS SO.** Both are
    REQUIRED parameters on the card (`Proposed schedule *`, `Against cycle *`);
    an empty scope produces a report whose own empty state names what is
    missing, rather than a confident *nothing changed*.
    """
    ctx.set_results["_currency"] = tenancy_seam.currency()
    ctx.set_results["_movers"] = int(ctx.params.get("show_biggest_movers") or 50)
    ctx.set_results["_threshold"] = str(ctx.params.get("call_it_large_above") or "15")

    version_id = ctx.params.get("proposed_schedule")
    run_id = ctx.params.get("against_cycle")
    if not version_id or not run_id:
        ctx.set_results["_change"] = {"comparable": False}
        ctx.set_results["_cycle"] = {"bills": [], "bills_in_the_cycle": 0}
        ctx.set_results["_priced"] = {"priced": {}, "unpriced": {}}
        ctx.set_results["_bills"] = {}
        return []

    cycle = billing_seam.issued_bills_for_run(run_id)
    bills = list(cycle.get("bills") or [])
    # The SERVICE DATE the versions are resolved on is the cycle's own, so a
    # baseline is the version that was in force when these bills were priced
    # (`BR-RAT-007`) rather than whatever is in force today.
    service_date = (
        _date(bills[0].get("service_date") or bills[0].get("period_end"))
        if bills
        else tenancy_seam.today()
    ) or tenancy_seam.today()
    change = rating_seam.schedule_change(version_id=version_id, service_date=service_date)
    service = str(change.get("service") or "")

    cycle = billing_seam.issued_bills_for_run(run_id, service_code=service)
    bills = list(cycle.get("bills") or [])
    cycle["period_start"] = bills[0].get("period_start") if bills else None
    cycle["period_end"] = bills[0].get("period_end") if bills else None
    ctx.set_results["_change"] = change
    ctx.set_results["_cycle"] = cycle
    ctx.set_results["_cycle_label"] = _cycle_label(cycle)

    # ⚠ **NOTHING IS PRICED HERE — `DEF-RBS-4395`.** Guards run BETWEEN this
    # function and the first step, so a re-price taken here is a re-price of
    # records the runbook has been told not to look at. Step 3 does it, over the
    # subjects the executor hands it.
    ctx.set_results["_service_date"] = service_date
    ctx.set_results["_schedule_versions"] = frozenset(change.get("version_ids") or ())

    # WHO each bill belongs to — its NAME and its TYPE, never its id (B14 rule
    # 31). Two reads for the whole cycle rather than two per bill.
    account_ids = sorted({str(one.get("account_id")) for one in bills if one.get("account_id")})
    labels = customers_seam.account_names(account_ids) if account_ids else {}
    types = customers_seam.account_types_for(account_ids) if account_ids else {}
    samples = customers_seam.sample_account_ids() if account_ids else frozenset()
    facts: dict[str, dict[str, Any]] = {}
    sample_bills: set[str] = set()
    for bill in bills:
        account_id = str(bill.get("account_id") or "")
        if account_id in samples:
            sample_bills.add(str(bill.get("bill_id")))
        facts[str(bill.get("bill_id"))] = {
            "invoice_no": bill.get("invoice_no"),
            "account_label": labels.get(account_id) or "",
            "account_type": (types.get(account_id) or {}).get("type_name") or "",
            "currency": bill.get("currency") or "",
        }
    ctx.set_results["_bills"] = facts
    ctx.set_results["_sample_bills"] = frozenset(sample_bills)

    return [
        SubjectRef(
            subject_type="bill",
            subject_id=str(bill.get("bill_id")),
            # B14 rule 31 — the number a customer reads off their bill.
            label=str(bill.get("invoice_no") or ""),
        )
        for bill in bills
    ]


def _cycle_label(cycle: dict[str, Any]) -> str:
    """*August* — the column heading the build sheet draws, from the cycle itself.

    The sheet's `August` is a VALUE and not copy: it is the period these bills
    were issued for, and a column headed with a month the utility did not bill
    would be `DEF-RBS-4329`'s shape in a table header.
    """
    end = _date(cycle.get("period_end"))
    return end.strftime("%B") if end else "As issued"


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Rate change preview",
    kind=models.KIND_CHECK,
    category="plans_rates",
    subject_type="bill",
    unit_of_work="a bill of one issued cycle, re-priced against a draft",
    triggers=(models.TRIGGER_MANUAL,),
    tags=("Billing",),
    parameters=(
        Parameter(
            name="proposed_schedule",
            type=PARAM_REF_OBJECT,
            label="Proposed schedule",
            required=True,
            # ⚠ NO DOMAIN, AND THAT IS THE CONTRACT'S OWN CARVE-OUT rather than
            # an omission: `Parameter._check_domain` records that a
            # `ref:object` must name one *"is a true sentence"* which refused
            # four shipped runbooks, because this product publishes no LIST read
            # for these pickers. `rating_seam.draft_schedules` is that list for
            # this one and a `schedule` domain is a wave of its own.
        ),
        Parameter(
            name="against_cycle",
            type=PARAM_REF_OBJECT,
            label="Against cycle",
            required=True,
        ),
        Parameter(
            name="services",
            type=PARAM_ENUM,
            label="Services",
            default="water",
            # Tenant-resolved (`BR-RBS-042` clause 2). ⚠ **DECLARED AND NOT
            # NARROWING**: a tariff belongs to exactly one service, so the
            # service is the SCHEDULE's and step 1 says so rather than letting a
            # dropdown quietly disagree with the draft.
            domain="service",
        ),
        Parameter(
            name="compare_to",
            type=PARAM_REF_SETTING,
            label="Compare to",
            # The card marks it read-only and Settings-owned. What it means is
            # `BR-BIL-004`: the comparison is against ISSUED bills and never
            # drafts, which step 2 applies and states.
            setting_key="billing.rate_preview_compare_to",
        ),
        Parameter(
            name="call_it_large_above",
            type=PARAM_PERCENT,
            label="Call it large above",
            # The card's `± 15%`, as percent POINTS stored to six decimals and
            # shown at two (hard rule 2) — a STRING, never a float, because this
            # value lives in `jsonb` where no column type would catch one.
            default="15.000000",
        ),
        Parameter(
            name="show_biggest_movers",
            type=PARAM_INTEGER,
            label="Show biggest movers",
            default=50,
        ),
        Parameter(
            name="group_by",
            type=PARAM_ENUM,
            label="Group by",
            choices=("account_type",),
            default="account_type",
        ),
        Parameter(
            name="revenue_by_service",
            type=PARAM_TOGGLE,
            label="Revenue by service",
            default=True,
        ),
    ),
    # ⚠ NO GUARD, ON PURPOSE — see the note above `resolve`. `RB-116`'s scope
    # table declares none, this runbook acts on nothing, and a preview that
    # silently dropped a trial tenant's whole cycle would say *nothing changes*
    # over a run that looked at nothing.
    guards=(),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_DRAFT, label=STEP_LABELS[STEP_DRAFT], mode=MODE_SET, run=step_load_the_draft_schedule),
        Step(key=STEP_CYCLE, label=STEP_LABELS[STEP_CYCLE], mode=MODE_SET, run=step_load_the_cycle_as_it_was_billed),
        Step(key=STEP_REPRICE, label=STEP_LABELS[STEP_REPRICE], mode=MODE_SET, run=step_reprice_every_bill_under_the_draft),
        # ⚠ THE ONLY PER-RECORD STEP — one bill, one savepoint, one row.
        Step(key=STEP_COMPARE, label=STEP_LABELS[STEP_COMPARE], mode=MODE_PER_RECORD, run=step_compare_to_the_issued_bill),
        Step(key=STEP_DISTRIBUTE, label=STEP_LABELS[STEP_DISTRIBUTE], mode=MODE_SET, run=step_distribute_and_group_the_changes),
        Step(key=STEP_REVENUE, label=STEP_LABELS[STEP_REVENUE], mode=MODE_SET, run=step_sum_revenue_by_service),
    ),
    # ⚠ **EMPTY** (`BR-RBS-002`, `TC-RBS-028.2`). A Check is CONSTRUCTED with no
    # writer, so no bill is re-issued, no bill number is consumed and no draft
    # is adopted — the capability is absent rather than refused at runtime.
    ports=(),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-028 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, posts no ledger line and adds NO rating math — every figure is `engine.price_period`'s through the one existing projection)
# gates: pytest tests/test_us_rbs_028_rate_change_preview.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G20
# exceptions: the comparison is **this schedule's own portion**, before taxes and fees — `OQ-319` is OPEN and this follows the answer `BR-RAT-091`'s ratified `$59.00 → $62.54` was signed on rather than choosing a second one · the DIFFERENCE the engine computes is applied to what the customer was actually charged, so `DEF-154`'s base-charge precedence cancels out of the subtraction · the run reports how many bills the BASELINE pass failed to reproduce to the cent, which is its own error bar · the inner distribution band (`5%`) is a constant because the card draws it with no knob beside it, while the outer one is the card's parameter · the `services` parameter narrows nothing — a tariff belongs to one service — and step 1 says so · revenue is ONE service because a draft belongs to one schedule
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
