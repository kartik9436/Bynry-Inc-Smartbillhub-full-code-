# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-010 (the single rate update — a NEW version with a reason) ·
#           EP-RAT-16 (the approval slice) · EP-RAT-12
#           Screens: RAT-03 step 4 (Effective & approval) · RAT-02
# Change:   CR-013 part 1 step 4, verbatim: *"effective/end dates plus mandatory
#           impact analysis: accounts affected by plan, average and worst-case
#           bill change per class, annualised revenue change, accounts over
#           threshold."* Part 1's own gloss: *"The impact analysis is MANDATORY
#           and is four figures, not a warning banner."*
# Rules:    BR-RAT-091 clause 2 (RATE CHANGE: worst-case bill change above 10%
#           needs a second approval) · BR-RAT-087 (money and percent carry a
#           `*_display` companion) · BR-RAT-092 / OQ-286 (a PERCENT stores six
#           decimals) · BR-RAT-003 (rounding happens once, at finalization) ·
#           CLAUDE.md hard rule 2 (never float, never cents)
# Defects:  DEF-434 (three of the four figures had no endpoint) · DEF-435
#           (clause 2 had no server counterpart — it was a screen constant)
# Questions:OQ-318 (what a filing ABOVE the bar actually does) · OQ-319 (whole
#           bill or this schedule's portion) · OQ-320 (zero affected accounts;
#           unmeasured ≠ clear) · OQ-321 (projection or restatement)
# Tests:    06-backend/tests/test_br_rat_091_rate_change_impact.py
# Impacts:  apps/rating/selectors.rate_change_impact (the I/O half) ·
#           apps/rating/services.create_rate_schedule_version (the gate) ·
#           07-frontend/src/features/rating/RateScheduleWizard.tsx (RAT-03 s4)
# ───────────────────────────────────────────────────────
"""BR-RAT-091 clause 2 — the rate-change second-approval gate, and the four
figures RAT-03 step 4 was built to show and could not.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 rating math (B4 / CLAUDE.md sensitive
paths), AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements signed law, never invents it.

THE RULE, VERBATIM (BR-RAT-091, PO 2026-08-20, closing OQ-284)
--------------------------------------------------------------
    **(2) RATE CHANGE: worst-case bill change above `10%`.** Not annualised
    revenue and not accounts-affected — both were offered. **Worked against our
    own fixture:** the water +6% filing moves an 11 kgal household
    `$59.00 → $62.54`, `+$3.54`/month, `$38,826`/year across 914 accounts — and
    **it FLOWS**, because 6% is under the bar. The threshold is deliberately set
    where a routine annual filing passes and a repricing does not. RAT-03 step
    4's mandatory impact analysis already computes the figure the gate reads.

⚠ **THE LAST SENTENCE OF THAT RULE WAS FALSE WHEN IT WAS WRITTEN, AND THIS
MODULE IS WHAT MAKES IT TRUE (DEF-435).** Nothing computed a worst-case bill
change, so the gate read nothing and could not fire (DEF-434); `10` lived once,
as a constant in a React file, governing a screen and not a write. A two-figure
rule read as done while half of it was decoration. The rule row is amended, dated
2026-08-21, on the commit that landed this file — not before it.

WHY THIS MODULE HOLDS NO PRICING OF ITS OWN
-------------------------------------------
It holds arithmetic over prices that somebody else produced. Every dollar figure
it consumes comes out of `apps.rating.engine.price_period` — the same call the
bill run makes — configured by `selectors.pricing_inputs_for_version`, which is
the same projection a bill uses, extracted so it can be pointed at a version that
is not in force yet. **A second implementation of pricing is how two screens
start disagreeing about a figure**, and the figure they would disagree about here
is the one a utility files a rate case on.

THE THIRD STATE, AND WHY IT IS NOT A BOOLEAN
--------------------------------------------
`second_approval_required(None)` returns **`None`, never `False`**. A filing
whose worst case nobody could measure is not a filing that is under the bar, and
the difference is the whole of DEF-434: a `False` here would let a screen, an API
answer, a stored column and an audit row each report an unmeasured rate change as
CLEAR. Every surface that reads this carries the third state through — the column
is NULL, the JSON is `null`, the screen prints *not computed*. See OQ-320.

WHAT IS RATIFIED AND MUST NOT MOVE
----------------------------------
    +6.00%   $59.00 → $62.54 · +$3.54/mo · $38,826/yr · 914 accounts   FLOWS
    +10.00%  exactly at the bar                                        FLOWS
    +10.50%  above the bar                                             REQUIRES
    unmeasured                                                         null

`10%` exactly FLOWS because the rule says *above*. `test_br_rat_091_rate_change
_impact.py` asserts all four, and `RateScheduleWizard.test.tsx` asserts the same
four on the screen, so drift goes RED on both sides of the wire.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from core.money_fields import PERCENT_PLACES

ZERO = Decimal("0")
HUNDRED = Decimal("100")

#: BR-RAT-092 / OQ-286 (PO 2026-08-20, verbatim *"for perctnage you can have 6
#: decimal places"*). A percentage is a PERCENT, not an amount: six places
#: stored, two displayed. Quantized ONCE, here, so the number the gate compares
#: and the number the screen prints are the same number — a gate reading an
#: unrounded ratio while a screen prints a rounded one is a filing that says
#: `10.00%` and refuses.
PERCENT_QUANTUM = Decimal(1).scaleb(-PERCENT_PLACES)

#: BR-RAT-091 clause 2, and **this is the figure's only home in the product**.
#: It was `RATE_CHANGE_SECOND_APPROVAL_PCT = 10` in `RateScheduleWizard.tsx` and
#: nowhere else (DEF-435), which made it advice rather than a control: a client
#: constant governs what a screen draws and cannot govern what a server writes.
#: The screen now READS this figure off the endpoint's answer; its own constant
#: survives only as the documented mirror, and a test on each side asserts 10.
#:
#: ⚠ **NOT A TENANT SETTING, DELIBERATELY.** BR-RAT-077's discount threshold IS
#: one because the PO ruled it so in as many words (*"okay, but allow user to set
#: it , we can provide default."*). No such ruling exists for the rate half —
#: BR-RAT-091 states `10%` flat — and turning a stated figure into a
#: configurable one is inventing a rule the PO did not make.
RATE_CHANGE_SECOND_APPROVAL_PCT = Decimal("10")

#: BR-RAT-091's ratified arithmetic: `+$3.54`/month across `914` accounts is
#: `$38,826`/year, i.e. one month's measured delta multiplied by twelve. Named
#: rather than typed as `* 12` because it is the ONE thing about the annualised
#: figure that is ratified — whether it should instead restate the last twelve
#: BILLED months is OQ-321, and on a flat year both answers agree.
ANNUALISATION_MONTHS = Decimal("12")


def quantize_percent(value: Decimal) -> Decimal:
    """Six places, half-up. BR-RAT-092's PERCENT precision, applied once."""
    return Decimal(value).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)


def bill_change_pct(before: Decimal | None, after: Decimal | None) -> Decimal | None:
    """`(after − before) / before × 100`, in percentage POINTS, or None.

    Returns **None — never zero —** for the two cases that have no percentage:

      * either side is absent (the account could not be priced under one of the
        two versions, so there is no pair to compare), and
      * `before` is `0.00`, where the ratio is undefined. A household that paid
        nothing and now pays `$5.00` has not experienced a percentage change;
        it has experienced a new charge, and *"+∞%"* is not a figure a rate case
        can carry. The account is counted as affected and UNPRICED instead, so
        it is visible rather than averaged away.

    ⚠ **`0.00` is a real before-price and is treated as one.** DEF-277 draws the
    line this module respects one table over: a stated zero means *"served, and
    free"*, and a missing base means *"not served"* and REFUSES. Both arrive here
    as the absence of a percentage, but only because a percentage of zero cannot
    be written — not because either is being ignored.
    """
    if before is None or after is None:
        return None
    before = Decimal(before)
    if before == ZERO:
        return None
    return quantize_percent((Decimal(after) - before) / before * HUNDRED)


def second_approval_required(worst_case_pct: Decimal | None) -> tuple[bool | None, Decimal]:
    """(required?, the threshold that decided it) — BR-RAT-091 clause 2.

    **The shape is `discount_services.second_approval_required`'s, on purpose.**
    That function is clause 1 of this same rule (`(required, threshold)`, the
    threshold travelling beside the answer so an approver sees the bar that
    judged them). Copying it means BR-RAT-091 has ONE shape across both its
    halves rather than two that happen to agree today.

    **The one difference is the return type, and it is the point.** Clause 1
    always has a figure to compare — a budget cap, or its absence, which
    BR-RAT-077 rules is ALWAYS above the bar. Clause 2 frequently has nothing:
    a schedule on no plan, a tenant that has never taken a read, a rate shape
    the engine cannot price without registers. So `None` in gives `None` out,
    and **nothing anywhere may turn that into `False`** (DEF-434; OQ-320 asks
    the PO whether unmeasured should instead be treated as above the bar, the
    way an uncapped discount is).

    `10%` exactly FLOWS — the rule says *above*, and `Decimal("10") > Decimal(10)`
    is False. That is asserted on both sides of the wire.
    """
    threshold = RATE_CHANGE_SECOND_APPROVAL_PCT
    if worst_case_pct is None:
        return None, threshold
    return Decimal(worst_case_pct) > threshold, threshold


@dataclass(frozen=True)
class AccountChange:
    """One affected account, priced under both versions. Money, never float."""

    unit_id: str
    plan_id: str
    plan_name: str
    quantity: Decimal
    unit: str
    before: Decimal | None
    after: Decimal | None
    #: Why this account has no pair, when it has none. A named reason, never a
    #: silent drop: the count of accounts we could not price is itself one of
    #: the figures a filer needs to judge the analysis they are reading.
    unpriced_reason: str | None = None

    @property
    def change(self) -> Decimal | None:
        if self.before is None or self.after is None:
            return None
        return Decimal(self.after) - Decimal(self.before)

    @property
    def pct(self) -> Decimal | None:
        return bill_change_pct(self.before, self.after)


@dataclass(frozen=True)
class ImpactFigures:
    """CR-013 part 1 step 4's four figures, plus what could not be measured.

    `worst_case_pct` is the figure BR-RAT-091 clause 2's gate reads, and it is
    the **largest signed increase** across the priced accounts — the worst case
    FOR A CUSTOMER. A filing that only reduces bills produces a negative worst
    case, which is not *above* `10%` and therefore flows.

    ⚠ **A LARGE DECREASE THEREFORE NEEDS NO SECOND APPROVAL, AND THAT IS A LANE
    READING OF AN UNSTATED CASE** (decision log 2026-08-21). BR-RAT-091's worked
    example is an increase and the rule says *"worst-case bill change"* without
    a sign; a −40% filing gives away revenue on exactly the scale a +40% filing
    takes it. Read as an absolute value, our own ratified example is unaffected
    (+6% either way), so nothing frozen moves — but a utility cutting rates by a
    third would be gated by one reading and not by the other. Recorded rather
    than resolved quietly; it rides with OQ-318's answer.
    """

    accounts_affected: int
    accounts_priced: int
    accounts_unpriced: int
    worst_case_pct: Decimal | None
    average_pct: Decimal | None
    average_change: Decimal | None
    annualised_revenue_change: Decimal | None
    monthly_revenue_change: Decimal | None


def summarise(changes: tuple[AccountChange, ...], accounts_affected: int) -> ImpactFigures:
    """The four figures, from the priced pairs. Pure: no I/O, no clock.

    `accounts_affected` is passed in rather than derived from `changes` because
    the two are different facts and the difference is the honest part: a
    schedule can affect 914 accounts and be able to price 611 of them. Averaging
    over the 611 and calling it 914 is the shape of error this module exists to
    avoid.

    **Every aggregate is None when nothing could be priced** — never `0.00`,
    which reads as *"no effect"* to every person and every screen that sees it.
    """
    priced = tuple(change for change in changes if change.pct is not None)
    unpriced = accounts_affected - len(priced)
    if not priced:
        return ImpactFigures(
            accounts_affected=accounts_affected,
            accounts_priced=0,
            accounts_unpriced=max(unpriced, 0),
            worst_case_pct=None,
            average_pct=None,
            average_change=None,
            annualised_revenue_change=None,
            monthly_revenue_change=None,
        )
    percentages = [change.pct for change in priced]
    deltas = [change.change for change in priced]
    count = Decimal(len(priced))
    monthly = sum(deltas, ZERO)
    return ImpactFigures(
        accounts_affected=accounts_affected,
        accounts_priced=len(priced),
        accounts_unpriced=max(unpriced, 0),
        worst_case_pct=max(percentages),
        average_pct=quantize_percent(sum(percentages, ZERO) / count),
        average_change=monthly / count,
        # BR-RAT-091's own arithmetic: one month's delta across the affected
        # accounts, multiplied by twelve. `+$3.54 × 914 × 12 = $38,826.72`, the
        # `$38,826`/year the PO was shown. OQ-321 asks whether it should instead
        # restate twelve billed months; on a flat year the two agree.
        annualised_revenue_change=monthly * ANNUALISATION_MONTHS,
        monthly_revenue_change=monthly,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 part 1 step 4 + BR-RAT-091 (02-business-rules.md) + DEF-434/435
#         + 09-screen-inventory.md §8 (RAT-03, five steps)
# generated: 2026-08-21 by the Wave F lane (the mandatory impact analysis)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 rating math, HUMAN-REVIEW-PENDING, ledger row appended)
# gates: see the lane report — ruff✔ black✔ · pytest
#        tests/test_br_rat_091_rate_change_impact.py · 10-scripts/03-golden-verify.py
#        33 PASS / 0 FAIL (this module adds no pricing and touches no frozen figure)
# exceptions: E-A this module performs NO pricing — every dollar it consumes comes
#         from `engine.price_period` through `selectors.pricing_inputs_for_version`,
#         which is the projection a BILL uses · E-A the impact is this SCHEDULE's
#         own portion, before taxes, discounts and every other service on the plan,
#         because BR-RAT-091's ratified $59.00 -> $62.54 is exactly +6% and a
#         whole-bill reading cannot produce that — OQ-319 · E-A the per-CUSTOMER-
#         CLASS breakdown CR-013 part 1 asks for by name is NOT served (no read
#         joins `account_types` to an affected unit); the by-PLAN breakdown is, and
#         the class absence is stated rather than relabelled · E-A a filing ABOVE
#         the bar is REFUSED by `services.create_rate_schedule_version` pending
#         OQ-318, because BR-RAT-031 as-modified left nowhere for a second approval
#         to land · E-A a large DECREASE is not gated (worst case is the largest
#         signed increase) — recorded in the decision log, rides with OQ-318
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
