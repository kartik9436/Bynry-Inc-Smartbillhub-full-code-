# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-018 (S24 payment-plan wizard: amount & term → editable
#           schedule → agreement & activation)   Screens: S24 (entry S21;
#           payments' S34 bulk uses the same wizard)
# Rules:    BR-CUS-043 (schedule = (total − down) ÷ n, 2dp half-up, remainder
#           on the FINAL instalment; step-2 edits must re-sum exactly; one live
#           plan per account; while active and current, dunning and disconnect
#           pause; late-fee suspension is a per-plan election) · BR-CUS-044
#           (agreement renders from the S67 template, e-sign via the DocuSign
#           seam, states proposed → agreement_sent → active(on signature
#           ALONE) → closed. ⚠ ITS `defaulted` STATE AND ITS {missed_count}
#           DEFAULT CLAUSE ARE **SUPERSEDED** — PO 2026-08-11, "nodrop we chase
#           for payments until write off") · BR-CUS-037 (this module writes NO
#           financial table; the plan rows are payments' and are reached
#           through the seam) · BR-BIL-073 (A PLAN DOES NOT SUSPEND THE
#           CURRENT BILL — PO 2026-08-11, OQ-138 CLOSED) · BR-BIL-001 as
#           amended 2026-08-11 (the $25.00 balance floor — REUSED from
#           apps/billing/late_fee.py through the seam, never restated here) ·
#           BR-TEN-043 (event time is an argument, never a clock) ·
#           CLAUDE.md rule 2 (money is Decimal, never float)
# Golden:   PE-13 → **GT-47** (B5 ❄️ FROZEN 2026-08-08, mechanical allocation
#           "PE-n → GT-(34+n)"; 10-scripts/03-golden-verify.py checks it):
#           267.30 − 50.00 down over 6 → **5 × 36.22 + 36.20**.
# Tests:    06-backend/tests/test_us_cus_018_payment_plan.py ·
#           06-backend/tests/golden/test_gt47_payment_plan_schedule.py
# Impacts:  apps/customers/seams.py (the payments handoff + the billing
#           late-fee read) · apps/payments (owns `payment_plans` +
#           `payment_plan_installments` — B2 §2; NOT written from here)
# ───────────────────────────────────────────────────────
"""The S24 payment-plan wizard: the maths, the rules, and the handoff.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math: this decides what a
customer in arrears is asked to pay and when, and its figures are frozen in B5
as GT-47. AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

────────────────────────────────────────────────────────────────────────────
A PLAN DOES NOT SUSPEND THE CURRENT BILL — PO ruling 2026-08-11, OQ-138 CLOSED
────────────────────────────────────────────────────────────────────────────
PO verbatim: **"no there is monthly charges that thye have to pay nad it is due
every month"**.

Worked, on the frozen PE-13 plan: the instalment is **$36.22** and October's
ordinary cycle bill is **$184.20**, so the customer owes **$220.42** in October
— not $36.22.

**THIS CLOSES A LIVE DEFECT, NOT A GAP** (DEF-061). Treating the plan as
satisfying the account means a customer on a plan can stop paying current bills
for six months and nothing chases them: the dunning pause BR-CUS-043 grants was
read as covering everything the account owes. It does not. The pause covers the
**ARREARS the plan is spreading** — that is the debt the customer agreed a
schedule for — and the current month's bill is chased like anybody else's.
`amount_due_this_month()` is that rule, and `plan_pauses_current_bill()`
returns False so a caller cannot get the old answer by accident.

The late-fee half rides the same line and is NOT restated here: `suspend_late_fees`
is a per-plan election over the plan's own arrears (BR-CUS-043), and the current
bill's fee is `apps.billing.services.assess_late_fee` unchanged — including the
PO's $25.00 balance floor of 2026-08-11, which lives in
`apps/billing/late_fee.py` and is reached through the seam rather than copied.
A second copy of a ruled figure is how two figures start disagreeing.

────────────────────────────────────────────────────────────────────────────
NOBODY IS DROPPED OFF A PLAN — PO ruling 2026-08-11, OQ-141 CLOSED
────────────────────────────────────────────────────────────────────────────
PO verbatim: **"nodrop we chase for payments until write off"**.

BR-CUS-044 carried a template default clause — *"plan voids on {missed_count}
missed → full balance due; fees resume"* — with a PROPOSED `defaulted` state
and a default of 2; BR-PAY-016 said the same thing as *"2nd miss VOIDS plan"*;
J13 is a journey literally titled *born to die*. **All three are SUPERSEDED.**

So `PLAN_STATUSES` has four values and not five. There is no `defaulted`, no
`void`, no `missed_count` threshold and no auto-transition — and their absence
is the rule rather than work left undone, which is why `record_missed_instalment`
exists and deliberately changes no state: a miss is a fact worth recording so
collections can CHASE it, and chasing is now the whole of what happens.

An account that never pays reaches write-off through the ordinary collections
path (BR-BIL-006), and write-off is a decision with a human on it.

────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE REFUSES TO DECIDE
────────────────────────────────────────────────────────────────────────────
* ~~**OQ-139** — the allocation order between the instalment and the current
  bill.~~ **CLOSED 2026-08-12, PO verbatim: _"plan first"_.** The instalment is
  met first and `split_payment_between` implements it. This paragraph used to
  say the module refused to decide it, and leaving that sentence here would be
  hard-won law 1 — a file describing a refusal it no longer makes.

  **It is a NAMED EXCEPTION to BR-PAY-010's oldest-invoice-first**, and the
  exception is the whole point: for a customer on a plan the oldest open invoice
  is one of the ARREARS THE PLAN ALREADY COVERS, so paying exactly what they
  agreed would leave the current month unpaid and get them chased for money they
  had just sent.
* **The plan ROWS.** `payment_plans` and `payment_plan_installments` are
  payments-owned (B2 §2) and BR-CUS-037 forbids customers writing them. The
  wizard computes and validates; `apps/customers/seams.py` hands the result to
  payments' service BY NAME, and reports honestly while that lane has not
  published one. Nothing here writes another module's table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from core import money

ZERO = Decimal("0")

#: A5 / BR-CUS-044 as the PO's ruling of 2026-08-11 leaves it. FOUR states.
#: `defaulted` and `void` are ABSENT and their absence is the rule — see the
#: module docstring. A plan ends by being PAID (closed), never by being broken.
PLAN_PROPOSED = "proposed"
PLAN_AGREEMENT_SENT = "agreement_sent"
PLAN_ACTIVE = "active"
PLAN_CLOSED = "closed"
PLAN_STATUSES = (PLAN_PROPOSED, PLAN_AGREEMENT_SENT, PLAN_ACTIVE, PLAN_CLOSED)

#: The three states in which a plan is LIVE — US-CUS-018 TC-7's "exactly one
#: live plan per account" (A3's "usually 1 active", enforced).
LIVE_PLAN_STATUSES = (PLAN_PROPOSED, PLAN_AGREEMENT_SENT, PLAN_ACTIVE)

#: S24 step 1's cadence picker, prototype-verbatim.
CADENCE_MONTHLY = "monthly"
CADENCE_BIWEEKLY = "biweekly"
CADENCE_WEEKLY = "weekly"
CADENCES = (CADENCE_MONTHLY, CADENCE_BIWEEKLY, CADENCE_WEEKLY)

#: S24 step 3's channel elections. At least one is required (US-CUS-018 §5).
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"
CHANNEL_PRINT = "print"
AGREEMENT_CHANNELS = (CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_PRINT)


class PaymentPlanRuleError(ValueError):
    """A payment-plan rule refused. Raised with the sentence the wizard shows."""


@dataclass(frozen=True)
class Installment:
    """One scheduled row: `#`, due date, amount, remaining after it (S24 step 2)."""

    seq: int
    due_date: date
    amount: Decimal
    remaining: Decimal
    final: bool = False


@dataclass(frozen=True)
class Schedule:
    """The whole generated schedule, and what it is spreading."""

    total: Decimal
    down_payment: Decimal
    spread: Decimal
    installments: tuple[Installment, ...]

    @property
    def count(self) -> int:
        return len(self.installments)


def next_due_date(previous: date, cadence: str) -> date:
    """The next instalment date under one of S24's three cadences.

    MONTHLY keeps the DAY OF MONTH and clamps to the month's length, so a plan
    starting on the 31st falls due on the 30th of April rather than skipping
    into May. A schedule that silently moves a due date has moved a customer's
    obligation.
    """
    if cadence == CADENCE_WEEKLY:
        return previous + timedelta(days=7)
    if cadence == CADENCE_BIWEEKLY:
        return previous + timedelta(days=14)
    if cadence != CADENCE_MONTHLY:
        raise PaymentPlanRuleError(
            f"unknown instalment cadence {cadence!r}; S24 offers {CADENCES}. A cadence "
            "the code does not implement stops the wizard rather than falling through "
            "to monthly."
        )
    month = previous.month + 1
    year = previous.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = previous.day
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


def build_schedule(
    *,
    total: Decimal,
    down_payment: Decimal = ZERO,
    installments: int,
    cadence: str,
    first_due_date: date,
) -> Schedule:
    """BR-CUS-043 / A7 (EXPLICIT): `(total − down) ÷ n`, 2dp half-up, remainder
    on the **FINAL** instalment.

    ❄️ **GT-47 (PE-13, frozen):** 267.30 with 50.00 down over 6 → 217.30 ÷ 6 =
    36.21666… → half-up **36.22** for instalments 1–5, and the final absorbs
    217.30 − 181.10 = **36.20**.

    Prototype fixture (US-CUS-018 TC-1): 247.30 over 4 → 61.83 · 61.83 · 61.83 ·
    **61.81**, with the remaining column 185.47 / 123.64 / 61.81 / 0.00.

    THE REMAINDER GOES ON THE FINAL ROW AND NOWHERE ELSE. Spreading the cent
    across the earlier rows would make five different instalment amounts out of
    one agreement, and A7 states the rule as "balance ÷ installments, remainder
    on final" in those words. The final row is also the one a customer reads
    last, so a schedule that ends at exactly 0.00 is the one they can check.
    """
    total = money.finalize(total)
    down_payment = money.finalize(down_payment)
    if total <= ZERO:
        raise PaymentPlanRuleError(
            "there is nothing to spread: the balance to spread must be more than "
            "0.00 (US-CUS-018 TC-6)."
        )
    if down_payment < ZERO:
        raise PaymentPlanRuleError("a down payment cannot be negative.")
    if down_payment >= total:
        raise PaymentPlanRuleError(
            f"a down payment of {down_payment} settles the whole {total} balance, so "
            "there is nothing left to spread — take the payment instead of writing a "
            "plan for it."
        )
    if installments < 1:
        raise PaymentPlanRuleError(
            f"a payment plan needs at least one instalment; {installments} was asked "
            "for (US-CUS-018 TC-6)."
        )

    spread = money.finalize(total - down_payment)
    each = money.finalize(spread / Decimal(installments))
    rows: list[Installment] = []
    due = first_due_date
    remaining = spread
    for seq in range(1, installments + 1):
        is_final = seq == installments
        # The FINAL instalment is what is LEFT, never the rounded quotient —
        # that is what makes Σ equal the spread to the cent under any rounding.
        amount = remaining if is_final else each
        remaining = money.finalize(remaining - amount)
        rows.append(
            Installment(seq=seq, due_date=due, amount=amount, remaining=remaining, final=is_final)
        )
        if not is_final:
            due = next_due_date(due, cadence)

    schedule = Schedule(
        total=total, down_payment=down_payment, spread=spread, installments=tuple(rows)
    )
    # The invariant the whole story rests on, asserted at the point of
    # construction rather than trusted: J13's INVARIANCE row is "the schedule
    # always re-sums to 267.30".
    validate_schedule(schedule=schedule)
    return schedule


def validate_schedule(*, schedule: Schedule) -> None:
    """BR-CUS-043: Σ instalments (+ down payment) must equal the total EXACTLY.

    US-CUS-018 TC-5 — edits summing to 240.00 against a 247.30 total — blocks
    Continue with this refusal, and nothing is sent. A schedule that does not
    re-sum is an agreement whose own numbers disagree, and the customer signs it.
    """
    total_scheduled = sum((row.amount for row in schedule.installments), ZERO)
    if money.finalize(total_scheduled + schedule.down_payment) != schedule.total:
        raise PaymentPlanRuleError(
            f"the schedule must equal the total to spread: {schedule.count} instalment(s) "
            f"totalling {money.finalize(total_scheduled)} plus a down payment of "
            f"{schedule.down_payment} comes to "
            f"{money.finalize(total_scheduled + schedule.down_payment)}, and the balance "
            f"is {schedule.total} (BR-CUS-043)."
        )
    if any(row.amount <= ZERO for row in schedule.installments):
        raise PaymentPlanRuleError(
            "every instalment must be more than 0.00 — a zero or negative row is a "
            "date on a schedule with no payment behind it (BR-CUS-043)."
        )


def apply_edits(
    *,
    schedule: Schedule,
    amounts: dict[int, Decimal] | None = None,
    due_dates: dict[int, date] | None = None,
) -> Schedule:
    """S24 step 2's per-row edits, re-summed and re-checked.

    US-CUS-018 TC-3: raising instalment 1 to $100.00 recomputes the remaining
    column and the FINAL row absorbs the difference, so Σ is still 247.30
    exactly. Rebalancing onto the final row is BR-CUS-043's own rule applied to
    an edit rather than to a generation — the alternative, refusing every edit
    until the clerk makes the arithmetic work by hand, is the behaviour TC-3
    describes as "the system rebalances or flags".

    An edit that cannot be absorbed — because it would leave the final row at or
    below zero — is REFUSED rather than silently dropping a row.
    """
    amounts = amounts or {}
    due_dates = due_dates or {}
    rows = list(schedule.installments)
    edited = [
        Installment(
            seq=row.seq,
            due_date=due_dates.get(row.seq, row.due_date),
            amount=money.finalize(amounts.get(row.seq, row.amount)),
            remaining=ZERO,
            final=row.final,
        )
        for row in rows
    ]
    # Absorb on the final row (BR-CUS-043), unless the clerk edited that row
    # themselves — in which case their number stands and the schedule is
    # validated as typed, which is what makes TC-5's refusal reachable.
    if edited and schedule.count not in amounts:
        head = sum((row.amount for row in edited[:-1]), ZERO)
        final_amount = money.finalize(schedule.spread - head)
        if final_amount <= ZERO:
            raise PaymentPlanRuleError(
                f"those edits total {money.finalize(head)} of a {schedule.spread} spread, "
                "which leaves nothing for the final instalment. Reduce an earlier row or "
                "remove an instalment (BR-CUS-043)."
            )
        edited[-1] = Installment(
            seq=edited[-1].seq,
            due_date=edited[-1].due_date,
            amount=final_amount,
            remaining=ZERO,
            final=True,
        )

    remaining = schedule.spread
    rebuilt: list[Installment] = []
    for row in edited:
        remaining = money.finalize(remaining - row.amount)
        rebuilt.append(
            Installment(
                seq=row.seq,
                due_date=row.due_date,
                amount=row.amount,
                remaining=remaining,
                final=row.final,
            )
        )
    result = Schedule(
        total=schedule.total,
        down_payment=schedule.down_payment,
        spread=schedule.spread,
        installments=tuple(rebuilt),
    )
    validate_schedule(schedule=result)
    return result


# ── the rulings of 2026-08-11 ───────────────────────────────────────────────
def plan_pauses_current_bill() -> bool:
    """**False.** PO 2026-08-11: *"there is monthly charges that thye have to pay
    nad it is due every month"*.

    A function rather than a constant so a caller has to ask the question in
    words, and so the rejected answer has one place to be tested against. The
    dunning pause BR-CUS-043 grants covers the ARREARS the plan spreads; the
    current month's bill is chased like anybody else's.
    """
    return False


def amount_due_this_month(
    *,
    installment_amount: Decimal,
    current_bill_amount: Decimal,
) -> Decimal:
    """**THE INSTALMENT PLUS THE CURRENT BILL.** PO 2026-08-11, OQ-138 CLOSED.

    ❄️ Worked, on the frozen PE-13 plan: instalment **36.22** and October's bill
    **184.20** → **220.42**. Not 36.22, which is what a product that treats the
    plan as satisfying the account asks for, and not 184.20 either.

    Both halves are due in the same month and neither excuses the other. What
    this deliberately does NOT do is decide which of the two a partial payment
    meets — that is OQ-139 and `split_payment_between` raises on it.
    """
    return money.finalize(installment_amount + current_bill_amount)


def split_payment_between(
    *,
    amount: Decimal,
    installment_amount: Decimal,
    current_bill_amount: Decimal = ZERO,
) -> tuple[Decimal, ...]:
    """**THE PLAN INSTALMENT IS MET FIRST.** PO 2026-08-12, OQ-139 CLOSED.

    PO verbatim: *"plan first"*. Returns `(to_instalment, to_current_bill)`.

    `current_bill_amount` is a PARAMETER rather than an assumption because
    without it this function cannot cap the second figure, and an uncapped
    second figure would report a surplus as though it had been allocated to the
    bill — which is the shape of defect this repo keeps finding. It defaults to
    zero so a caller asking only *"how much of this reaches the instalment?"*
    gets a truthful answer instead of a wrong one.

    **THIS IS A NAMED EXCEPTION TO OLDEST-INVOICE-FIRST, and the exception is the
    point.** BR-PAY-010's default sends money to the oldest open invoice — which,
    for a customer on a plan, is one of the ARREARS BILLS THE PLAN ALREADY
    COVERS. So a customer who pays exactly what they agreed would have it spent
    on the debt the plan is already spreading, fall behind on the current month,
    and be chased for money they had just sent. That is the defect this ruling
    closes, and it is why the rule lives here rather than in payments' ordinary
    allocation order.

    ❄️ Worked, on the frozen PE-13 plan and OQ-138's October:

        instalment 36.22 · current bill 184.20 · total due 220.42

        pays 220.42 → (36.22, 184.20)   both met
        pays 100.00 → (36.22,  63.78)   the plan is whole, the bill part-paid
        pays  20.00 → (20.00,   0.00)   short of the instalment: none reaches
                                        the bill, because a part-paid instalment
                                        is still a missed instalment and the
                                        customer needs to know that
        pays 300.00 → (36.22, 184.20)   the surplus 79.58 is NOT allocated here

    THE SURPLUS IS DELIBERATELY NOT PLACED. Anything beyond the instalment and
    the current bill is an overpayment, and where an overpayment goes is
    payments' rule (BR-PAY-012's credit) — not this module's. Returning it as a
    third element would invite a caller to treat it as allocated. The caller
    subtracts: `amount - sum(result)`.
    """
    if amount < ZERO:
        raise PaymentPlanRuleError(
            f"a payment of {amount} is negative. Money coming back OUT of an account is a "
            "refund or a reversal, each of which is its own recorded event (BR-PAY-014) — "
            "it is never a payment with a minus sign (BR-PAY-014)."
        )
    if installment_amount < ZERO:
        raise PaymentPlanRuleError(
            f"an instalment of {installment_amount} is negative; BR-CUS-043 requires every "
            "instalment to be more than 0.00."
        )
    if current_bill_amount < ZERO:
        raise PaymentPlanRuleError(
            f"a current bill of {current_bill_amount} is negative. A credit balance is not a "
            "bill and is not settled by a payment (BR-PAY-012)."
        )
    to_installment = min(amount, installment_amount)
    to_current_bill = min(amount - to_installment, current_bill_amount)
    return (to_installment, to_current_bill)


def record_missed_instalment(*, missed_count: int) -> str:
    """A missed instalment is CHASED. It does not end the plan. PO 2026-08-11.

    Verbatim: *"nodrop we chase for payments until write off"*. BR-CUS-044's
    template default clause (*"plan voids on {missed_count} missed → full
    balance due; fees resume"*), its PROPOSED `defaulted` state and BR-PAY-016's
    *"2nd miss VOIDS plan"* are all SUPERSEDED by that sentence.

    So this returns the plan's UNCHANGED status and takes no action beyond the
    count. It exists rather than being deleted for the same reason
    `late_fee.PaymentReceipt.recorded_on` exists: the transition the PO ruled
    against is one a test can assert the absence of, where a function nobody
    wrote is a rule nobody can see. The tenth miss returns `active` exactly as
    the first does.
    """
    if missed_count < 0:
        raise PaymentPlanRuleError("a missed-instalment count cannot be negative.")
    return PLAN_ACTIVE


# ── the wizard's own validation ─────────────────────────────────────────────
def validate_proposal(
    *,
    balance_to_spread: Decimal,
    account_balance: Decimal,
    installments: int,
    cadence: str,
    first_due_date: date,
    as_of: date,
    live_plan_exists: bool,
) -> None:
    """S24 step 1's refusals — US-CUS-018 TC-6 and TC-7.

    `as_of` is an argument, never a clock (BR-TEN-043): a wizard that read the
    system date could not be tested against a plan proposed on a Tuesday in 2026
    and would behave differently in a preview than in the commit it previews.
    """
    if live_plan_exists:
        raise PaymentPlanRuleError(
            "this account already has a live payment plan. One live plan per account "
            "(BR-CUS-043 / A3) — a second would give the same arrears two schedules "
            "and no rule for which one the customer signed."
        )
    if balance_to_spread > account_balance:
        raise PaymentPlanRuleError(
            f"the balance to spread ({balance_to_spread}) is more than the account owes "
            f"({account_balance}). A plan spreads a debt that exists (US-CUS-018 TC-6)."
        )
    if installments < 1:
        raise PaymentPlanRuleError(
            "a payment plan needs at least one instalment (US-CUS-018 TC-6)."
        )
    if cadence not in CADENCES:
        raise PaymentPlanRuleError(
            f"unknown instalment cadence {cadence!r}; S24 offers {CADENCES}."
        )
    if first_due_date <= as_of:
        raise PaymentPlanRuleError(
            f"the first instalment falls on {first_due_date}, which is not after "
            f"{as_of}. A schedule whose first row is already due is one the customer "
            "is late on before they sign it (US-CUS-018 §5)."
        )


def validate_agreement_channels(channels: tuple[str, ...]) -> None:
    """S24 step 3: at least one channel, and each one a channel S24 offers."""
    unknown = [channel for channel in channels if channel not in AGREEMENT_CHANNELS]
    if unknown:
        raise PaymentPlanRuleError(
            f"unknown agreement channel(s) {unknown}; S24 offers {AGREEMENT_CHANNELS}."
        )
    if not channels:
        raise PaymentPlanRuleError(
            "choose at least one way to send the agreement — email for e-signature, "
            "an SMS signing link, or print for counter signature (US-CUS-018 §5). A "
            "plan whose agreement is never sent can never activate, because activation "
            "is the customer's signature (BR-CUS-044)."
        )


def next_status_on_send(current: str) -> str:
    """`proposed → agreement_sent` (US-CUS-018 §1 exit)."""
    if current != PLAN_PROPOSED:
        raise PaymentPlanRuleError(
            f"an agreement is sent from {PLAN_PROPOSED!r}; this plan is {current!r}."
        )
    return PLAN_AGREEMENT_SENT


def next_status_on_signature(current: str) -> str:
    """`agreement_sent → active`, **on the customer's signature ALONE**.

    BR-CUS-044 as amended: *"executes via CUSTOMER E-SIGNATURE ALONE — no
    utility countersignature or any other signature required (supersedes the
    A19 §3 countersign block)"*. A plan activated before signature would pause
    dunning on a debt nobody agreed to.
    """
    if current != PLAN_AGREEMENT_SENT:
        raise PaymentPlanRuleError(
            f"a plan activates on signature from {PLAN_AGREEMENT_SENT!r}; this plan is "
            f"{current!r}. Activation is the CUSTOMER's signature and nothing else "
            "(BR-CUS-044)."
        )
    return PLAN_ACTIVE


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-018@bbed56d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/05-golden-tests.md · 04-docs/05-modules/03-customers/06-epics/EP-CUS-06-payment-plan.md · 04-docs/05-modules/03-customers/02-business-rules.md · 08-qa/01-e2e/journeys/J13-payment-plan-life.md)
# generated: 2026-08-11 by story-coder (W4 payment-plan lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S24 has no endpoint: the plan ROWS are payments-owned (BR-CUS-037) and `payment_plans` does not exist, so a POST here would have nowhere to write; REPORTED) E=deferred(no-frontend-half — S24 is not built) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) NO `defaulted`, NO `void`, NO `missed_count` threshold and no
#         auto-transition — PO 2026-08-11 "nodrop we chase for payments until
#         write off" SUPERSEDES BR-CUS-044's default clause, its PROPOSED
#         `defaulted` state, and BR-PAY-016's "2nd miss VOIDS plan".
#         `record_missed_instalment` records and returns `active` unchanged.
#         (2) `split_payment_between` raises OQ-139 — the PO closed "both are
#         due" and left the allocation ORDER open in the same breath.
#         (3) THE PLAN ROWS ARE NOT WRITTEN HERE. `payment_plans` /
#         `payment_plan_installments` are payments-owned (B2 §2, EP-PAY-05) and
#         BR-CUS-037 forbids customers writing them; apps/payments has no such
#         table yet and belongs to another lane in this session. The handoff is
#         `apps/customers/seams.propose_payment_plan`, resolved BY NAME, which
#         REPORTS rather than falling back — so the wizard's arithmetic is live
#         and tested and its persistence is honestly absent (hard-won law 2:
#         reported, not papered over).
#         (4) The $25.00 late-fee floor is NOT restated: the current bill's fee
#         is billing's own `assess_late_fee` through the seam.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
