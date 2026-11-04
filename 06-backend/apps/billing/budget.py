# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-018 (enrollment, eligibility, the level computation) ·
#           US-BIL-019 (the budget bill: actuals monthly, variance on every
#           bill, settle-up) · US-BIL-020 (re-level at drift, per-account
#           override ±30%)
#           Screens: S30 (Budget Bills tab) · S66/S69 (the parameter rows)
# Rules:    BR-BIL-017 (level = trailing-12-month average, whole $;
#           eligibility = 12-mo history; variance on every bill; auto re-level
#           at ±20% drift each 6 mo; annual settle-up month; per-account
#           override bounded ±30% — every parameter a tenant setting.
#           ⚠ ITS TWO-MISSED-PAYMENTS DROP-OFF IS **SUPERSEDED** by the PO
#           ruling of 2026-08-11, "nodrop we chase for payments until write
#           off") · BR-BIL-072 (THE LEVEL IS WHAT IS DUE — PO 2026-08-11,
#           OQ-140 CLOSED; see the docstring) · BR-BIL-021 (every budget
#           parameter is tenant config, seeded, nothing hardcoded) ·
#           BR-BIL-011 (the monthly posting is the ACTUALS posting — the level
#           never reaches the ledger as a price) · BR-RAT-043 (budget billing
#           rides the plan flag) · BR-RAT-003 / B4.4 (finalized half-up 2dp,
#           once) · BR-TEN-043 (event time is an argument, never a clock) ·
#           CLAUDE.md rule 2 (money is Decimal, never float)
# Golden:   WE-8 → **GT-24** (B5 ❄️ FROZEN 2026-08-08, mechanical allocation
#           "WE-n → GT-(16+n)"): trailing-12 $2,904 → level **$242**; Jul
#           actual 292.87 → −50.87 · Aug 231.40 → +10.60 · Sep 198.75 →
#           +43.25; running **−50.87 → −40.27 → +2.98**.
# Tests:    06-backend/tests/test_us_bil_018_budget_enrollment.py ·
#           06-backend/tests/test_us_bil_019_budget_bill.py ·
#           06-backend/tests/test_us_bil_020_budget_maintenance.py ·
#           06-backend/tests/golden/test_gt24_budget_chain.py
# Impacts:  apps/billing/budget_service.py (the write path that persists what
#           this computes) · apps/billing/stages/assemble_document.py (stamps
#           the three columns into the bill payload) ·
#           apps/billing/selectors.py (publishes `amount_due` to the product)
# ───────────────────────────────────────────────────────
"""Budget billing (level-pay): the arithmetic. No clock, no query, no writes.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4 / CLAUDE.md sensitive
paths), AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law and the
PO's rulings of 2026-08-11; it invents no rule of its own.

────────────────────────────────────────────────────────────────────────────
THE LEVEL IS WHAT IS DUE — PO ruling 2026-08-11, OQ-140 CLOSED
────────────────────────────────────────────────────────────────────────────
PO verbatim: **"Level is due"**.

Worked, on the frozen WE-8 chain: the July bill's actual is **$292.87** and the
level is **$242**. The customer owes **$242**. Paying $242 settles the month
**IN FULL** — they do not age, they earn no late fee, and they never enter the
collection ladder. The $50.87 difference is not arrears; it accrues to the
variance balance and is settled once a year in the settle-up month.

**THIS CLOSES A LIVE DEFECT RATHER THAN FILLING A GAP** (DEF-062). In the
absence of this rule every path in the product measures a customer against
`invoices.total`, so a budget customer paying exactly the amount the utility
asked them for is $50.87 short every month: they enter the 1–30 aging bucket,
appear on S34's outstandings, earn `max($5, 1.5% × 50.87)` = **$5.00** of late
fee and walk into the dunning ladder. Nobody chose that behaviour; it is what
the code does when nothing tells it otherwise. `amount_due()` is what tells it
otherwise, and `tests/test_us_bil_019_budget_bill.py` drives the defect RED
before it is trusted green.

**WHAT DOES NOT CHANGE, AND IT MATTERS MORE THAN WHAT DOES.** The bill is still
computed as **full actuals** — every normal line, every GL stamp, tax — and the
posting is still the ACTUALS posting (BR-BIL-011). Revenue and tax recognise
monthly on what the customer used. The level is a COLLECTION SCHEDULE, never a
price (WE-8's own words), so nothing in this module touches `invoices.total`,
`invoice_lines`, or anything the ledger reads. `amount_due` is a *second* fact
about the same bill: what we asked them to pay.

────────────────────────────────────────────────────────────────────────────
NOBODY IS DROPPED OFF BUDGET BILLING — PO ruling 2026-08-11, OQ-141 CLOSED
────────────────────────────────────────────────────────────────────────────
PO verbatim: **"nodrop we chase for payments until write off"**.

BR-BIL-017 dropped an account off budget billing after two missed level
payments, and no rule anywhere defined what a missed payment was — payments was
expected to emit an event nobody had specified. **That question is now MOOT
rather than answered: there is no drop-off event, so this module does not
define a miss and must not acquire one.** An account that falls behind is
chased through the ordinary collections path to write-off and stays on its
level while that happens.

So there is no `missed_payment()` here, no counter, and no automatic transition.
`account_budget_status.status` still carries `off_budget` because a human can
still take an account off the programme from S30 ("Remove from budget") — a
staff action with a name on it, which is a different thing entirely from a
silent consequence of two arrears.

────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE REFUSES TO DECIDE
────────────────────────────────────────────────────────────────────────────
* **OQ-142** — which GL account the settle-up line's other side touches. The
  finance-signed chart (B5 line 74) contains no budget or deferral account and
  the eleven designations confirmed on 2026-08-11 do not include one; option
  (c) would need a finance re-sign. `settle_up_gl_account()` raises. The
  billing-side arithmetic below is complete and tested; only the posting is
  blocked, which is exactly where the boundary was drawn.
* **OQ-164** (minted by this lane) — a budget account's FINAL bill. The level
  is a schedule for a continuing relationship; a move-out ends the relationship
  with a variance balance still open. `amount_due` refuses a `final` bill on an
  enrolled account rather than choosing between "the level" and "the whole
  closing position", which differ by every dollar of accumulated variance.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from apps.billing import posting_seam
from core import money

#: BR-BIL-017 "whole $". The only ratified rounding mode — and it is READ from
#: the tenant setting rather than assumed, because BR-BIL-021 makes every budget
#: parameter tenant config. `apps.tenancy.settings_families.LEVEL_ROUNDINGS`
#: holds the same single-value tuple; an unknown mode REFUSES below rather than
#: falling through to this one.
ROUNDING_WHOLE_DOLLAR = "whole_dollar"
LEVEL_ROUNDINGS = (ROUNDING_WHOLE_DOLLAR,)

#: `account_budget_status.status` (B2 r12 #14 item D-5).
#: `off_budget` is reachable ONLY by an explicit staff action since the PO's
#: ruling of 2026-08-11 — see the module docstring.
STATUS_ENROLLED = "enrolled"
STATUS_OFF_BUDGET = "off_budget"
STATUSES = (STATUS_ENROLLED, STATUS_OFF_BUDGET)

#: Why an account is not eligible, as codes a screen groups on rather than
#: prose it would have to parse (the `AccountProblem.reason` precedent).
INELIGIBLE_SHORT_HISTORY = "insufficient_billing_history"
INELIGIBLE_PLAN_NOT_FLAGGED = "plan_does_not_offer_budget_billing"

#: The settle-up line's two directions. Same line class, opposite sign
#: (US-BIL-019 TC-3/TC-4).
SETTLE_COLLECT = "collect"
SETTLE_CREDIT = "credit"

#: B4.2 / WE-8: the settle-up line is **non-taxable AR-timing**. Revenue and tax
#: were already recognised on the monthly actuals, so taxing it would tax the
#: same money twice. Exported as a constant because US-BIL-019 TC-5 is a test
#: that this cannot be forged the other way.
SETTLE_UP_TAXABLE = False

ZERO = Decimal("0")


@dataclass(frozen=True)
class Eligibility:
    """Whether an account may be enrolled, and the sentence S30 shows if not.

    `detail` is deliberately a rendered fact ("9/12 months") and not a
    translation key: US-BIL-018 TC-2 asks for the reason to name the shortfall,
    and the shortfall is two numbers the caller already has.
    """

    eligible: bool
    reason: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class SettleUp:
    """The annual true-up line — B4.2 non-taxable, AR-timing, never revenue.

    `amount` is always POSITIVE; `direction` carries the sign. Two reasons: a
    signed amount on an invoice line means "credit" in one module and "debit
    reduces" in another (`adjustments.direction` exists for exactly this), and a
    screen that must print "we owe you $2.98" needs the direction as a fact
    rather than as the sign of a number it has to interpret.
    """

    direction: str
    amount: Decimal
    taxable: bool = SETTLE_UP_TAXABLE

    @property
    def signed(self) -> Decimal:
        """What the settle-up does to the amount due: + collects, − credits."""
        return self.amount if self.direction == SETTLE_COLLECT else -self.amount


def eligibility(
    *,
    months_of_history: int,
    required_months: int,
    plan_offers_budget: bool,
) -> Eligibility:
    """BR-BIL-017 eligibility: enough billed history, on a plan that offers it.

    `required_months` is the tenant's `eligibility_months` and is an ARGUMENT —
    BR-BIL-021 makes it config, and US-BIL-018 TC-2 lowers it to 9 to prove the
    12 is a seed and not a constant. Nothing here supplies a default: a caller
    that could not read the setting must refuse, not assume twelve.

    The plan flag is checked FIRST because it is the more fundamental refusal:
    an account on a plan that does not offer budget billing is not "nearly
    eligible", and telling them "9/12 months" would send them to wait three
    months for an answer that will still be no.
    """
    if not plan_offers_budget:
        return Eligibility(
            eligible=False,
            reason=INELIGIBLE_PLAN_NOT_FLAGGED,
            detail="the account's plan does not offer budget billing (BR-RAT-043)",
        )
    if months_of_history < required_months:
        return Eligibility(
            eligible=False,
            reason=INELIGIBLE_SHORT_HISTORY,
            detail=f"{months_of_history}/{required_months} months",
        )
    return Eligibility(eligible=True)


def compute_level(
    *,
    trailing_actuals: Iterable[Decimal],
    months: int,
    rounding: str,
) -> Decimal:
    """BR-BIL-017 / WE-8: `round_to_whole_$(Σ trailing actuals ÷ months)`.

    ❄️ GT-24 (frozen): $2,904 ÷ 12 → **$242**.

    `months` is the DIVISOR and it is the tenant's eligibility window, not
    `len(trailing_actuals)`. The two differ the moment a tenant lowers the
    window to 9 (US-BIL-018 TC-2) and a caller hands over twelve bills anyway;
    dividing by the list length would quietly average a different period than
    the tenant configured.

    Refuses an unknown rounding mode rather than falling through to whole
    dollars: a misconfigured tenant setting must stop the enrolment, because a
    level is a number a customer pays for a year.

    Rounding is HALF-UP (B4.4, finance-signed) applied ONCE, to the average. The
    sum is never rounded — CLAUDE.md rule 2's "round only at finalization".
    """
    if rounding not in LEVEL_ROUNDINGS:
        raise ValueError(
            f"unknown budget level rounding {rounding!r}; BR-BIL-017 ratifies "
            f"{LEVEL_ROUNDINGS} and nothing else. A rounding mode the code does not "
            "implement stops the enrolment rather than defaulting to whole dollars."
        )
    if months <= 0:
        raise ValueError(
            f"the budget averaging window is {months} months, which cannot be a "
            "divisor. BR-BIL-021 makes it a tenant setting; a zero or negative one "
            "is a misconfiguration, not an average."
        )
    total = sum(trailing_actuals, ZERO)
    return (total / Decimal(months)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def variance_movement(*, level: Decimal, actual: Decimal) -> Decimal:
    """WE-8: `level − actual`, one bill's contribution to the balance.

    NEGATIVE means the customer used MORE than the level asked for (Jul:
    242 − 292.87 = **−50.87**). Positive means they used less (Sep:
    242 − 198.75 = **+43.25**). That sign convention is WE-8's own and the
    settle-up direction reads it, so it is not free to be flipped for taste.
    """
    return money.finalize(level - actual)


def running_balance(*, opening: Decimal, level: Decimal, actual: Decimal) -> Decimal:
    """The balance after this bill. ❄️ WE-8/GT-24: −50.87 → −40.27 → +2.98."""
    return money.finalize(opening + variance_movement(level=level, actual=actual))


def settle_up(*, balance: Decimal) -> SettleUp | None:
    """The settle-up line for a balance, or None when there is nothing to true up.

    A POSITIVE balance means the levels collected more than the customer used,
    so the utility owes them: **CREDIT** (US-BIL-019 TC-3 — balance +2.98 credits
    2.98). A NEGATIVE balance means they used more than they paid: **COLLECT**
    (TC-4 — balance −40.27 collects 40.27). Same line class, opposite sign.

    Non-taxable by construction, and that is the rule rather than a default:
    B4.2 and WE-8 both state that revenue and tax were recognised on the monthly
    actuals, so this line is AR-TIMING. `SettleUp.taxable` is a frozen field
    fixed at `SETTLE_UP_TAXABLE` precisely so US-BIL-019 TC-5 — "a settle-up
    line forged as taxable" — is a test of something the type cannot express.

    An EXACTLY ZERO balance produces no line at all. A $0.00 charge on a bill is
    a line a customer reads and asks about, and there is nothing to true up.
    """
    balance = money.finalize(balance)
    if balance == ZERO:
        return None
    if balance > ZERO:
        return SettleUp(direction=SETTLE_CREDIT, amount=balance)
    return SettleUp(direction=SETTLE_COLLECT, amount=-balance)


def amount_due(
    *,
    level: Decimal,
    actual: Decimal,
    settlement: SettleUp | None = None,
    bill_type: str = "cycle",
) -> Decimal:
    """**WHAT THE CUSTOMER OWES ON A BUDGET BILL — the LEVEL.** PO 2026-08-11.

    PO verbatim: *"Level is due"*. Worked, ❄️ WE-8: actual **292.87**, level
    **242** → this returns **242.00**, and paying it settles the month in full.
    `actual` is an argument it deliberately does NOT use for the cycle case —
    present because it is the REJECTED reading, and a rejected reading that is
    present and unused is a rule a test can assert (`late_fee.PaymentReceipt.
    recorded_on` carries the identical posture for the identical reason).

    IN THE SETTLE-UP MONTH the level is still due AND the accumulated balance is
    collected or credited on the same bill — that is what BR-BIL-017's
    "collected/credited" means, and a settle-up that did not move what is due
    would never be collected at all. Worked, on the frozen chain: level 242 with
    a **+2.98** balance credits, so **239.02** is due; with the **−40.27**
    fixture it collects, so **282.27** is due.

    **A FINAL BILL IS THE LEVEL ONLY — PO 2026-08-12, OQ-164 CLOSED.** Verbatim:
    *"Level only"*.

    ❄️ Worked, on the frozen WE-8 chain: the level is **242** and the variance
    balance is **−40.27** (the customer has used more than they have paid for).
    The final bill asks for **242.00**, not 282.27. The accumulated variance does
    NOT ride the last level payment; it is settled as its own event, which is
    what keeps the two figures distinguishable on a closing statement — a
    customer disputing $282.27 cannot tell which part is their month and which
    part is a year of under-collection.

    This paragraph used to describe a refusal (*"the two defensible answers …
    differ by every dollar of that balance"*), and the refusal was right to
    exist: the difference is real money on a customer's LAST bill, where nobody
    gets a chance to correct it next month. It was routed, ruled, and is now
    implemented — `bill_type` is still a parameter so the rule stays visible at
    the call site rather than becoming an invisible default.
    """
    if bill_type == "final":
        return money.finalize(level)
    due = level if settlement is None else level + settlement.signed
    return money.finalize(due)


def override_bounds(*, computed_level: Decimal, bound_pct: Decimal) -> tuple[Decimal, Decimal]:
    """BR-BIL-017 / OQ-068: a per-account override is bounded ±`bound_pct`%.

    Worked on the computed 242 with the seeded 30%: **169.40 – 314.60**
    (242 × 0.70 / 242 × 1.30) — US-BIL-020 TC-3's own figures.

    `bound_pct` is the tenant's `override_bound_pct` and is an argument for the
    same reason every other parameter here is (BR-BIL-021).
    """
    factor = bound_pct / Decimal("100")
    low = money.finalize(computed_level * (Decimal("1") - factor))
    high = money.finalize(computed_level * (Decimal("1") + factor))
    return low, high


def validate_override(
    *,
    computed_level: Decimal,
    override: Decimal,
    reason: str | None,
    bound_pct: Decimal,
) -> None:
    """Refuse an out-of-bound override, and refuse a reason-less one.

    Both halves are BR-BIL-017 as OQ-068 closed it: *"allowed with reason +
    audit, bounded ±30% of computed"*. US-BIL-020 TC-4 is both refusals.

    The reason is checked first and separately: "you must say why" and "that
    number is too low" are different corrections for the clerk to make, and one
    message carrying both is one the screen cannot attach to a field.
    """
    if reason is None or not str(reason).strip():
        raise ValueError(
            "a per-account budget level override requires a REASON (BR-BIL-017 as "
            "OQ-068 closed it: 'allowed with reason + audit'). An override with no "
            "reason is an unexplained change to what a customer pays every month."
        )
    low, high = override_bounds(computed_level=computed_level, bound_pct=bound_pct)
    if not low <= override <= high:
        raise ValueError(
            f"a budget level override of {override} is outside the ±{bound_pct}% bound "
            f"{low}–{high} around the computed level {computed_level} (BR-BIL-017, "
            "OQ-068). The bound is what keeps an override an adjustment rather than a "
            "second, unreviewed pricing decision."
        )


def drift_fraction(*, current_level: Decimal, recomputed_level: Decimal) -> Decimal:
    """`|recomputed − current| ÷ current`, as a FRACTION (0.20 = 20%).

    A zero current level cannot be a denominator. It is refused rather than
    treated as infinite drift, because "re-level everything whose level is 0"
    would be a mass change to customers' bills produced by a division rule.
    """
    if current_level == ZERO:
        raise ValueError(
            "drift is measured against the CURRENT level and this account's level is "
            "0.00, which cannot be a denominator (BR-BIL-017). An account with no "
            "level is not drifting — it is unenrolled or misconfigured."
        )
    return abs(recomputed_level - current_level) / current_level


def relevel_due(
    *,
    current_level: Decimal,
    recomputed_level: Decimal,
    drift_pct: Decimal,
    months_since_last_level: int,
    cadence_months: int,
) -> bool:
    """BR-BIL-017: re-level only AT CADENCE and only on a drift BREACH.

    Both gates, and both are tenant settings (±20% each 6 months seeded).
    US-BIL-020 TC-6 is the cadence half: a forged mid-cadence job call is a
    no-op, because a re-level changes what a customer pays and must not be
    triggerable by calling a function more often.

    STRICTLY GREATER than the band, matching US-BIL-020 §7's `> 20%`: a
    recomputed level exactly 20% away is inside the band the tenant configured
    and does not move. (Fixtures: current 242, recomputed 250 → 3.3%, no change;
    recomputed 300 → 24.0%, breach.)
    """
    if months_since_last_level < cadence_months:
        return False
    return drift_fraction(
        current_level=current_level, recomputed_level=recomputed_level
    ) > drift_pct / Decimal("100")


def settle_up_gl_account(*, settlement: SettleUp) -> str:
    """The OTHER side of the settle-up line. **NOT DECIDED — OQ-142.**

    Settled and not re-asked: revenue and tax recognise monthly on the ACTUALS,
    the settle-up line is non-taxable AR-timing, and the frozen chain is
    −50.87 → −40.27 → **+2.98**. Unsettled: which account the line touches. The
    finance-signed chart (B5 line 74) contains no budget or deferral account and
    the eleven designations the PO confirmed on 2026-08-11 (OQ-110) do not
    include one. Three options are live — (a) receivables carry it, (b) the
    already-signed `unbilled_ar` 1210, (c) a NEW signed account, which is a
    finance re-sign via HUMAN-GUIDE §6 and never an inline edit.

    **NARROWED 2026-08-15 BY A PO RULING, AND THE REASON RECORDED HERE UNTIL NOW
    WAS WRONG — read this before re-deriving it.** PO verbatim: *"tax follows the
    amount billed"*. The argument this module and the decision log both carried —
    that revenue must stay on actuals because *a state taxes what was consumed* —
    rests on a premise the PO's own tax authorities do not share. Two corrections
    follow and neither moves a line of code:

      * **Nothing here was ever at risk.** A budget bill carries the FULL ACTUAL
        LINES (see the module docstring), so the amount BILLED is **292.87** and
        **242.00** is only the amount ASKED — `amount_due` is a second fact about
        the same document. Tax on 292.87 is already what the ruling requires.
      * **The revenue-recognition fork is withdrawn.** Moving revenue to the level
        would not have been unlawful either, so tax decides nothing here. Actuals
        stay for two other reasons: a level has no lines (of the reference bill's
        **128.88** only **100.58** is taxable, so a blended 242.00 carries neither
        a taxable base nor BR-BIL-067's per-service revenue split), and a bill
        reading only *242.00* hides consumption from the customer.

    **RULED 2026-08-15 — THE VARIANCE GETS ITS OWN ACCOUNT (OQ-142 CLOSED).** PO
    verbatim: *"Create seperate account"*, choosing option (c) of the three above.

    The question it answered was a REPORTING one, not a tax one — the tax half had
    closed hours earlier. July leaves **50.87** standing: not revenue (counted), not
    tax (taken), not an arrear (OQ-140 stops the late fee and the ladder reaching
    that customer). But it still landed in the **1–30 ageing bucket**, where a
    budget variance is indistinguishable from a delinquency on every ageing report
    and DSO trend the product prints — and across a year the balance runs
    **−50.87 → −40.27 → +2.98**, so it can end as money the utility OWES while
    sitting in a bucket that says the customer is behind.

    **Both cheaper options were offered and both declined**, which is why this does
    not quietly fall back to either: receivables (a) IS the ageing-bucket problem,
    and `unbilled_ar` 1210 (b) also holds month-end accruals — so the balance would
    mix two facts — and is a poor fit besides, because a budget bill IS billed, it
    is merely not fully asked for.

    **SO THIS IS NO LONGER A STUB — IT IS A REFUSAL WAITING ON A SIGNATURE.** The
    account is an addition to **B5 line 74, ❄️ frozen and finance-signed**, so it
    takes the HUMAN-GUIDE §6 re-sign route (B5 is never edited inline). Until a
    human designates one, `posting_seam.budget_variance_account_id` refuses BY NAME
    rather than posting money to a bucket the ruling rejected. Safe to ship that
    way: the settle-up fires at TRUE-UP, six or twelve months after enrolment.

    The settle-up line stays **non-taxable AR-timing** — unchanged by this ruling,
    because revenue and tax were already recognised on the actuals.
    """
    return posting_seam.budget_variance_account_id()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-018@e9d5a48 (sha1[:7] of the four frozen sources this slice was
#         authored from, concatenated in order:
#         04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/05-modules/07-billing/06-epics/EP-BIL-05-budget-billing.md ·
#         04-docs/05-modules/07-billing/02-business-rules.md ·
#         04-docs/05-modules/07-billing/08-worked-examples.md — co-packets
#         US-BIL-019@e9d5a48 · US-BIL-020@e9d5a48)
# generated: 2026-08-11 by story-coder (W4 budget-billing lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure calculation; the write path and its endpoint are budget_service.py) E=deferred(no-frontend-half — S30's Budget Bills tab is not built; REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) `amount_due(actual=...)` never reads `actual` in the cycle case
#         and the argument stays — it is the REJECTED reading the PO ruled
#         against, and a rejected reading that is present-and-unused is a rule a
#         test can assert. (2) NO missed-payment definition, no counter and no
#         automatic drop-off: the PO's "nodrop we chase for payments until write
#         off" makes BR-BIL-017's two-miss clause SUPERSEDED and the undefined
#         "miss" MOOT, so acquiring one here would re-open a question the PO
#         closed. (3) `settle_up_gl_account` raises OQ-142 — the ledger side is
#         the boundary and a finance re-sign may be needed. (4) `amount_due`
#         raises OQ-164 on a FINAL bill: minted by this lane, not answered.
#         (5) Nothing here reads a tenant setting; every parameter is an
#         argument (BR-BIL-021 + the settings_seam precedent — a default
#         substituted here would be a second copy of a ratified figure).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
