# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-011 (S20 move-out step 3 "Final bill & deposit" · S30 —
#           immediate at move-out, deposit auto-applies FIRST, then exactly ONE
#           settlement path)   Screens: S20 · S30
# Rules:    BR-BIL-013 (final bill: immediate at move-out, billed through the
#           move day; deposit+interest applies FIRST, then exactly ONE of
#           refund · collect · transfer-to-master · payment plan ·
#           small-balance write-off — OQ-069/OQ-070 CLOSED) · BR-BIL-011
#           (a transfer is a BALANCED transaction, audited) · BR-CUS-056
#           (billed THROUGH the move day) · BR-CUS-057 (deposit interest =
#           tenant simple annual rate from the original receipt date) ·
#           BR-CUS-031 (the move-out handoff billing consumes) · BR-CUS-055
#           (behaviour classes) · BR-BIL-004 (issued bills are immutable) ·
#           CLAUDE.md rule 2 (money is Decimal + currency, never float)
# Golden:   GT-23 (= WE-7, ❄️ B5 FROZEN, finance-signed 2026-08-08, recomputed
#           by 10-scripts/03-golden-verify.py): deposit $150 held 14 months @
#           2% simple → interest **3.50** → credit **153.50** applies first;
#           Case A charges 142.30 → refund **11.20**; Case B charges 289.40 →
#           due **135.90**.
# Tests:    06-backend/tests/test_us_bil_011_final_bill.py
# Impacts:  apps/payments (the refund handoff — payments EXECUTES it) ·
#           apps/ledger (deposit-liability DR / AR CR, and the write-off GL) ·
#           S20's step 3, which renders exactly this
# ───────────────────────────────────────────────────────
"""The last bill of a tenancy, and the one arithmetic that must not be sloppy.

A final bill is an ordinary bill with an extraordinary consequence: after it,
nobody is watching the account. BR-BIL-013's shape follows from that — *"so
that a closed account never lingers with an ambiguous balance"*:

    charges  −  (deposit + its interest)  =  remainder
    remainder decides ONE settlement path, and exactly one.

WE-7 (❄️ GT-23) is the whole rule in three numbers. A $150 deposit held 14
months at 2% simple earns **3.50**, so **153.50** applies BEFORE any path is
chosen. Against Case A's charges of 142.30 that leaves **−11.20** → a refund.
Against Case B's 289.40 it leaves **135.90** → collect, transfer or a payment
plan. Two mistakes are available here and both are one character wide:

  * applying the credit TWICE (`charges - credit - credit`) turns Case B's
    135.90 into −17.60 and hands the customer a refund they are not owed;
  * not applying it at all (`remainder = charges`) bills 289.40 and keeps money
    that belongs to the customer.

`test_us_bil_011_final_bill.py` was run with each of those mutations in place
before this file was trusted, and each turns the WE-7 assertions RED — the
figures are in the Lifecycle trailer, from the run, not predicted.

DEPOSIT INTEREST IS NOT COMPUTED HERE, and that is a boundary, not a gap in
this story. BR-CUS-057 is a CUSTOMERS rule and its accrual engine is US-CUS-023
§7; `apps/customers/services.py` says so in as many words, in the move-out
handoff it publishes today (`deposit_interest_accrued: None`,
`deposit_interest_unavailable: "BR-CUS-057"`). GT-61 freezes the arithmetic
($150 @ 2.0%, 89 months → $22.25) and nothing implements it. So this module
READS the accrued figure through a named seam and REFUSES when it cannot —
because the alternative, applying the principal alone, quietly under-credits
every closing customer by their interest and the bill still foots. A refusal is
visible; a silent 3.50 short is not.

WHAT THIS MODULE DOES NOT PERSIST, and it is the story's largest gap: **there
is no `final_settlements` table.** US-BIL-011 §5 names one (path enum, actor,
when), r10 #10/#11 name the balance-transfer transaction and write-off support,
and `apps/billing/models.py` carries none of the three. So `settle()` computes
the settlement and returns it; nothing here writes it, and "exactly ONE
settlement path per final bill" is therefore enforced *within* a call and not
across calls. REPORTED to the lane that owns `models.py` rather than forced
into a table that means something else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.billing import gather, models, runs, settings_seam, single
from apps.billing.contracts import AccountBillingData
from apps.billing.exceptions import BillingRuleError
from core import money

#: `DEF-BIL-8330`'s key, shared with the first bill (`one_time.NO_BILLING_CYCLE_KEY`
#: reads this): *"No billing cycle. Assign one on the account."* — PO 2026-10-01,
#: *"same as first bill"*. Defined here because `one_time` imports this module.
NO_BILLING_CYCLE_KEY = "billing.oneTime.err.noBillingCycle"

#: BR-BIL-013's settlement matrix (r1.1). A CLOSED set: a sixth path would be a
#: new way for a closed account to end up with an unexplained balance.
PATH_REFUND = "refund"
PATH_COLLECT = "collect"
PATH_TRANSFER = "transfer"
PATH_PAYMENT_PLAN = "payment_plan"
PATH_WRITE_OFF = "write_off"
SETTLEMENT_PATHS = (
    PATH_REFUND,
    PATH_COLLECT,
    PATH_TRANSFER,
    PATH_PAYMENT_PLAN,
    PATH_WRITE_OFF,
)

#: Why a final bill is refused. VALUES — S20's step 3 groups on them.
FINAL_ACCOUNT_ALREADY_CLOSED = "account_already_closed_for_billing"
FINAL_DEPOSIT_INTEREST_UNAVAILABLE = "deposit_interest_not_accrued"
FINAL_PATH_UNAVAILABLE = "settlement_path_not_available"

#: The customers reads this module depends on. Named once so the contract is
#: greppable from both sides of the boundary (the tenancy_seam.py precedent).
DEPOSIT_INTEREST_READ = "deposit_interest_accrued"
MASTER_ACCOUNT_READ = "master_billing_account_for_unit"


@dataclass(frozen=True)
class DepositCredit:
    """What the customer's deposit is worth on the day the tenancy ends.

    `principal` is the held deposit (`accounts.deposit_on_file`, customers'
    stored NUMERIC(18,6)); `interest` is BR-CUS-057's accrual, computed by
    customers and never here. Both travel with the currency (rule 2), and
    `total` is their sum and nothing else — no rounding happens in this class,
    because both components are already finalized figures.
    """

    principal: Decimal
    interest: Decimal
    currency: str
    received_on: date | None = None

    @property
    def total(self) -> Decimal:
        """WE-7: 150.00 + 3.50 = **153.50**, the credit that applies FIRST."""
        return self.principal + self.interest

    @property
    def exists(self) -> bool:
        return self.principal != 0 or self.interest != 0


@dataclass(frozen=True)
class Settlement:
    """What happens to the remainder — one path, or the staff's pending choice.

    `path` is None in exactly two situations and they are different: the
    remainder is zero (`settled` is True — nothing is owed in either direction,
    so no path applies) or a staff choice is outstanding (`settled` is False,
    `available` lists what they may pick). A screen that conflated them would
    either nag about a settled account or quietly close an unsettled one.
    """

    charges: Decimal
    deposit: DepositCredit
    remainder: Decimal
    path: str | None
    automatic: bool
    available: tuple[str, ...]
    currency: str
    write_off_threshold: Decimal
    master_account_id: str | None = None
    transfer_unavailable: str | None = None

    @property
    def settled(self) -> bool:
        return self.path is not None or self.remainder == 0

    @property
    def refund_amount(self) -> Decimal:
        """The money owed BACK to the customer (WE-7 Case A: **11.20**)."""
        return -self.remainder if self.remainder < 0 else Decimal("0")

    @property
    def amount_due(self) -> Decimal:
        """The money still owed BY the customer (WE-7 Case B: **135.90**)."""
        return self.remainder if self.remainder > 0 else Decimal("0")


# ── the deposit position (customers-owned; billing reads, never computes) ───


def _money(value: Any, what: str) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BillingRuleError(
            f"{what} arrived as {value!r}, which is not a money amount. CLAUDE.md rule "
            "2: money is NUMERIC(18,6) and is never coerced through float."
        ) from exc


def deposit_credit_for(account_id: Any, as_of: Any = None) -> DepositCredit:
    """The deposit + BR-CUS-057 interest, as customers reports them.

    REFUSES when a deposit exists and its accrued interest cannot be read.
    That refusal is the point of the function: `deposit_on_file` alone is
    available today and using it alone would short every closing customer by
    their interest — WE-7's 3.50 on a 14-month $150 deposit, GT-61's 22.25 on
    an 89-month one — with a bill that foots perfectly and a balance nobody
    queries because the account is closed.

    An account with NO deposit answers zero without consulting the interest
    seam: there is nothing to accrue on, and blocking those final bills on an
    unbuilt engine would be a refusal with no rule behind it.

    ⚠ **THE ENGINE EXISTS FROM 2026-09-03 (CR-059 CS-20) AND THIS REFUSAL IS
    UNCHANGED — only what triggers it has widened.** `apps.customers.selectors.
    deposit_interest_accrued` now answers, and it takes the DAY the interest
    accrues to, because BR-TEN-043 and gate G6 keep a clock out of a money
    path. So there are two ways the figure can still be unreadable and both
    refuse identically: the seam is not published at all, or it answers `None`
    — which it does when no day was stated, when the deposit carries no receipt
    date, or when the tenant's rate could not be read. A `None` treated as zero
    here would be the principal-only settlement this function exists to prevent,
    arriving through the door that was opened to fix it.
    """
    detail = gather._resolve("customers", "account_detail")
    if detail is None:
        raise BillingRuleError(
            "customers has not published account_detail, so the deposit position "
            "cannot be read and no final bill can be settled."
        )
    row = detail(account_id)
    principal = _money(row.get("deposit_on_file"), "the account's deposit_on_file")
    received_raw = row.get("deposit_received_on")
    received_on = date.fromisoformat(received_raw) if received_raw else None
    currency = row.get("currency") or ""

    if principal == 0:
        return DepositCredit(
            principal=Decimal("0"),
            interest=Decimal("0"),
            currency=currency,
            received_on=received_on,
        )

    accrued = gather._resolve("customers", DEPOSIT_INTEREST_READ)
    if accrued is None:
        raise gather.GatherProblem(
            FINAL_DEPOSIT_INTEREST_UNAVAILABLE,
            f"apps.customers.selectors.{DEPOSIT_INTEREST_READ} is not published, so the "
            f"interest accrued on this account's {principal} deposit cannot be read. "
            "BR-CUS-057 makes it a tenant simple annual rate from the original receipt "
            "date and US-CUS-023 §7 owns the accrual; billing does not compute it here. "
            "The deposit is NOT applied principal-only: WE-7's $150 held 14 months at "
            "2% earns $3.50, so a principal-only credit of 150.00 instead of 153.50 "
            "would keep $3.50 of the customer's money on a bill that foots and an "
            "account nobody will look at again.",
        )
    answered = accrued(account_id, as_of)
    if answered is None:
        # The SAME refusal, for the same reason, from the other side: the seam
        # is published and could not answer. See the docstring — a None read as
        # zero is exactly the principal-only credit this refuses.
        raise gather.GatherProblem(
            FINAL_DEPOSIT_INTEREST_UNAVAILABLE,
            f"apps.customers.selectors.{DEPOSIT_INTEREST_READ} could not work out the "
            f"interest accrued on this account's {principal} deposit — either no business "
            "day was stated to accrue to, or the deposit carries no receipt date, or the "
            "tenant's rate could not be read. BR-CUS-057 makes it a tenant simple annual "
            "rate from the original receipt date and US-CUS-023 §7 owns the accrual; "
            "billing does not compute it here. The deposit is NOT applied principal-only: "
            "WE-7's $150 held 14 months at 2% earns $3.50, so a principal-only credit of "
            "150.00 instead of 153.50 would keep $3.50 of the customer's money on a bill "
            "that foots and an account nobody will look at again.",
        )
    return DepositCredit(
        principal=principal,
        interest=_money(answered, "the accrued deposit interest"),
        currency=currency,
        received_on=received_on,
    )


def master_account_for(unit_id: Any) -> tuple[str | None, str | None]:
    """The unit's designated master billing account, or (None, why not).

    BR-BIL-013's transfer path has a PREREQUISITE the closure states plainly —
    *"unit/premises linked to a master billing account under the
    landlord-agreement flag"* (OQ-069). No such link exists in this repository:
    there is no landlord-agreement flag, no master designation and no seam.

    So this answers None with a REASON, and the transfer path is simply not
    offered. That is the safe direction of the unknown: the failure mode of a
    missing link is a path that cannot be chosen, where the failure mode of
    assuming one is a customer's closing balance moved onto a stranger's
    account. The transfer target is ALWAYS this function's answer and never a
    caller-supplied id, which is what makes US-BIL-011 TC-6's "transfer forged
    to an arbitrary account" unrepresentable rather than merely rejected.
    """
    read = gather._resolve("customers", MASTER_ACCOUNT_READ)
    if read is None:
        return None, (
            f"apps.customers.selectors.{MASTER_ACCOUNT_READ} is not published — the "
            "landlord-agreement link and the master-account designation (OQ-069's "
            "prereq, r10 #10) have no table in this repository, so no unit can be "
            "shown to be linked and the transfer path is not offered."
        )
    master = read(unit_id)
    if not master:
        return None, "this unit is not linked to a master billing account (BR-BIL-013)."
    return str(master), None


# ── the settlement matrix (BR-BIL-013 r1.1) ─────────────────────────────────


def settle(
    *,
    charges: Decimal,
    deposit: DepositCredit,
    write_off_threshold: Decimal,
    currency: str,
    master_account_id: str | None = None,
    transfer_unavailable: str | None = None,
    chosen: str | None = None,
) -> Settlement:
    """Apply the deposit FIRST, then resolve exactly one path. Pure — no writes.

    THE ORDER IS THE RULE. BR-BIL-013 says the deposit and its interest apply
    *first*, before any path is chosen, and that is not a preference: the
    remainder is what selects the path, so applying the credit afterwards would
    let a $142.30 bill covered by a $153.50 deposit be sent to collections.

    The branches, in the order they are tested and why:

      1. `|remainder| <= threshold` → **write_off**, automatically, in BOTH
         directions (US-BIL-011 TC-5: a 3.20 remainder either way). Tested
         first because a small overpayment is a write-off, not a refund — a
         $0.40 cheque costs more to issue than it returns.
      2. `remainder < 0` → **refund** (WE-7 Case A: 11.20). Automatic: nobody
         chooses whether to give back money that is not theirs.
      3. otherwise → the staff pick ONE of collect / payment plan / transfer
         (WE-7 Case B: 135.90). Transfer appears only when the unit is linked.
      4. `remainder == 0` → settled, no path. Not a fifth outcome — an account
         that owes nothing in either direction has no ambiguity to resolve,
         which is the whole objective of the rule.

    `chosen` is ONE value. "Two settlement paths attempted on one final bill"
    (TC-6) is not rejected by a validation; it is unrepresentable, and a
    `chosen` that contradicts an automatic outcome refuses by name.
    """
    if deposit.currency and currency and deposit.currency != currency:
        raise BillingRuleError(
            f"the deposit is held in {deposit.currency!r} and the final bill is in "
            f"{currency!r}. Money never changes currency between the two (rule 2)."
        )
    remainder = charges - deposit.total

    automatic: str | None = None
    available: tuple[str, ...] = ()
    if remainder == 0:
        automatic = None
    elif abs(remainder) <= write_off_threshold:
        automatic = PATH_WRITE_OFF
    elif remainder < 0:
        automatic = PATH_REFUND
    else:
        available = (PATH_COLLECT, PATH_PAYMENT_PLAN)
        if master_account_id:
            available = available + (PATH_TRANSFER,)

    if automatic is not None:
        if chosen is not None and chosen != automatic:
            raise gather.GatherProblem(
                FINAL_PATH_UNAVAILABLE,
                f"this final bill settles automatically as {automatic!r} (remainder "
                f"{remainder} against a {write_off_threshold} write-off threshold), so "
                f"{chosen!r} is not one of its paths. BR-BIL-013 allows exactly ONE "
                "settlement path per final bill.",
            )
        return Settlement(
            charges=charges,
            deposit=deposit,
            remainder=remainder,
            path=automatic,
            automatic=True,
            available=(automatic,),
            currency=currency,
            write_off_threshold=write_off_threshold,
            master_account_id=master_account_id,
            transfer_unavailable=transfer_unavailable,
        )

    if chosen is not None and chosen not in available:
        why = ""
        if chosen == PATH_TRANSFER:
            why = f" {transfer_unavailable or 'no master account is linked to this unit.'}"
        elif chosen == PATH_WRITE_OFF:
            why = (
                f" The remainder {remainder} is above the tenant's write-off threshold "
                f"of {write_off_threshold} (0–50, BR-BIL-013), so it cannot be written "
                "off — that is the greyed-out option in US-BIL-011 TC-3."
            )
        elif chosen not in SETTLEMENT_PATHS:
            why = f" BR-BIL-013 defines exactly {SETTLEMENT_PATHS}."
        raise gather.GatherProblem(
            FINAL_PATH_UNAVAILABLE,
            f"{chosen!r} is not an available settlement path for a remainder of "
            f"{remainder} {currency}; the choices are {available or '(none)'}.{why}",
        )

    return Settlement(
        charges=charges,
        deposit=deposit,
        remainder=remainder,
        path=chosen,
        automatic=False,
        available=available,
        currency=currency,
        write_off_threshold=write_off_threshold,
        master_account_id=master_account_id,
        transfer_unavailable=transfer_unavailable,
    )


def settle_account(
    *,
    account_id: Any,
    unit_id: Any,
    charges: Decimal,
    currency: str,
    as_of: date | None = None,
    chosen: str | None = None,
) -> Settlement:
    """`settle` with every input READ rather than passed — the wired entry point.

    The threshold comes from the tenant's own Finance-controls setting (never a
    constant — BR-BIL-013 makes it config 0–50), the deposit from customers and
    the master account from the landlord link. A caller cannot supply any of
    the three, which is what stops a settlement being computed against a
    threshold or a deposit somebody typed.

    ⚠ **`as_of` IS THE ONE THING THE CALLER MUST SUPPLY, AND UNTIL 2026-09-04
    NOBODY DID — SO EVERY DEPOSIT-HOLDING ACCOUNT REFUSED TO SETTLE
    (`DEF-CWP-3842`).** `deposit_interest_accrued` answers `None` when no day
    was stated, deliberately: *"gate G6 keeps a clock out of a money path, and a
    figure accrued to a day nobody named is a figure nobody can check."*
    `deposit_credit_for` then refuses BY NAME, correctly — but the sentence it
    prints blames an unreadable accrual when the truth is that this line asked
    for one without naming a day. The engine had been live since 2026-09-03 and
    the caller had never been given the argument, so `surface_debt.txt`'s claim
    that closing a deposit-holding account was *"unblocked"* was true of the
    ENGINE and false of the PRODUCT.
    **It is still not defaulted here.** `None` reaches `deposit_credit_for` and
    refuses exactly as it did; what changed is that `settle_final_bill` now has
    a business date to pass and passes it.
    """
    deposit = deposit_credit_for(account_id, as_of)
    master_account_id, transfer_unavailable = master_account_for(unit_id)
    return settle(
        charges=charges,
        deposit=deposit,
        write_off_threshold=settings_seam.write_off_threshold(),
        currency=currency,
        master_account_id=master_account_id,
        transfer_unavailable=transfer_unavailable,
        chosen=chosen,
    )


# ── the bill itself: through the move day (BR-CUS-056) ──────────────────────


def moving_out_account(account_id: Any) -> single.SingleScope:
    """The account being closed — resolved WITHOUT the billable-set filter.

    `single.billable_account` narrows to the classes a cycle run bills, and a
    final bill is precisely the bill for an account leaving that set. So this
    reads the row directly (customers' own `account_or_404`, so unknown,
    malformed and cross-tenant stay one answer) and lets stage 1 rule on the
    behaviour class — see `prepare_final_bill`, which turns that refusal into a
    sentence a clerk can act on.
    """
    account_or_404 = gather._resolve("customers", "account_or_404")
    if account_or_404 is None:
        raise BillingRuleError(
            "customers has not published account_or_404, so the closing account cannot "
            "be resolved. Nothing is assumed."
        )
    row = account_or_404(account_id)
    unit_id = getattr(row, "unit_id", None)
    if not unit_id:
        raise gather.GatherProblem(
            gather.GATHER_NO_UNIT,
            f"account {getattr(row, 'account_no', account_id)!r} has no unit, so there "
            "is nothing to bill a final period for (BR-CUS-017).",
        )
    return single.SingleScope(
        account_id=str(row.id),
        account_no=row.account_no,
        unit_id=str(unit_id),
        account=row,
    )


#: `DEF-CUS-5932` — the behaviour classes stage 1 will price (BR-CUS-055).
#: Named once because the check now runs TWICE in this module's call path: here,
#: before the gather, and inside `resolve_subscription` where it always ran. Two
#: spellings of one set is how they come to disagree about `billable_base_only`.
BILLABLE_CLASSES = ("billable", "billable_base_only")


def _closing_cycle_days(unit_id: Any, *, as_of: date) -> int | None:
    """B4.3's ❄️ DENOMINATOR for a CLOSING period — the customer's cycle length.

    HUMAN-REVIEW-PENDING · 🔒 money path — AI-authored 2026-09-20 under the PO
    ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*)
    and the PO ruling of 2026-09-20 (*"okay we have to buld it there will ebe
    code to reuse"*). A row in `12-governance/09-human-review-ledger.md` states
    in plain English what it does and with which figures.

    ════════════════════════════════════════════════════════════════════════
    THIS IS IMPLEMENTATION OF SIGNED LAW, NOT A RE-SIGN — AND IT WAS
    ESTABLISHED BEFORE A LINE WAS WRITTEN
    ════════════════════════════════════════════════════════════════════════
    B4.3, CONFIRMED: *"proration is by **calendar days**. The **base charge is
    always prorated**."* **GT-3, ❄️ B5 FROZEN 2026-08-08**, states the
    denominator outright: *"move-in day 16 of 30; base $30.50. Base proration
    **15/30** × 30.50 = **15.25**"* — the numerator is the days served and the
    denominator is the **cycle's own calendar length**. A mid-cycle move-OUT is
    the mirror of that mid-cycle move-IN, so the frozen arithmetic already
    carries the term and only the computation was missing. Nothing here moves a
    frozen figure; if B4.3 had NOT given the denominator, a Product Owner
    saying *build it* would be the REQUEST for a finance re-sign and never a
    substitute for one (HUMAN-GUIDE §6).

    **The worked case, on the account the PO was shown:** a **12-day** closing
    window on a **30-day** cycle carried the whole **$18.50** base charge;
    12/30 × 18.50 is **$7.40**, so a customer who is leaving was billed
    **$11.10 too much** on the last bill anybody will ever read.

    ════════════════════════════════════════════════════════════════════════
    ⚠ `OQ-242`'s WITHDRAWAL IS NOT TOUCHED, AND THE SCOPING IS THE WHOLE POINT
    ════════════════════════════════════════════════════════════════════════
    `OQ-242` was CLOSED–WITHDRAWN on 2026-08-23 — *"its proration denominator
    (the current guess OVER-CHARGES while it stands). - this is not required"*
    — and it asked about a **CYCLE-LESS** one-time bill, which has no cycle to
    read a denominator from at all. `one_time._cycle_days` still answers `None`
    for every kind, an interim, back-bill, penalty or fee bill still carries a
    full base charge by that ruling, and
    `tests/test_cr029_rcw2_due_from_the_run.py::…_no_proration_denominator_is_
    invented_for_a_cycle_less_run` still pins it.

    **This function is reached from `prepare_final_bill` and from nowhere
    else**, which is what scopes it to the final bill BY CONSTRUCTION rather
    than by a `kind ==` test that a later lane could widen. **That claim is
    checkable in one command and is why the name is private:**
    `grep -rn '_closing_cycle_days' 06-backend/apps/` returns this definition
    and one call. A second caller is not a refactor, it is a change to which
    bills prorate, and `OQ-242` is the ruling it would have to reverse.
    ⚠ **SO THE SECOND CALLER CAME WITH ITS OWN AUTHORITY (2026-09-30,
    `DEF-BIL-8331`):** `one_time.first_bill_cycle_days` reads it on the MOVE-IN
    day, under BR-BIL-012 (*"prorated from move-in day"*) and B5 GT-3 ❄️ (15/30 ×
    30.50 = 15.25) — signed law for the FIRST bill, recorded in the decision log.
    `grep` now returns this definition and TWO calls; OQ-242's cycle-less
    interim, back-bill, penalty and fee bills are still not among them. A
    closing account
    on a real billing cycle is not the cycle-less case that was withdrawn: the
    cycle exists, the calendar exists, and metering has published the read
    since `DEF-2708`.

    ════════════════════════════════════════════════════════════════════════
    THE CODE IS REUSED, AND THIS IS NOT A THIRD IMPLEMENTATION
    ════════════════════════════════════════════════════════════════════════
    The calendar is `metering.period_engine.billing_period` — *"B4.3's
    DENOMINATOR, LOCATED ON A CALENDAR"*, which handles `OQ-339`'s month-end
    clamp and `OQ-340`'s anchor — served through
    `metering.selectors.billing_period_for_unit`. The factor is
    `rating.proration.proration_factor`, *"the only proration number in the
    engine"*. Neither is copied here.

    What IS written here is the four-line READ, and only because a module
    boundary forbids importing the one that exists:
    `customers.disconnects._cycle_days_for` is the identical read for the
    disconnection's cut bill, and B1 / gate G6 forbid billing importing a
    customers module. So this asks metering directly, through billing's own
    `gather._resolve`, for the same seam customers asks through its own. **The
    scar it carries is the same one:** `A-11488`, cut 18 August on a **$40.00**
    monthly base, was charged **$40.00** where 18 days of 31 is **$23.23** —
    **$16.77 too much on a real customer's final bill** — until that seam was
    published on 2026-08-31.

    ⚠ **`None` IS PART OF THE REUSE AND IT TRAVELS** (`DEF-2708`'s rule, one
    bill type along). A unit on no cycle, a pre-`CR-029` cycle with no
    frequency or first run, an `as_of` before the cycle's first run, and a unit
    on TWO cycles all answer `None` — **nothing here assumes a 30-day month**,
    because that would be money invented from a calendar nobody configured.
    `prepare_final_bill` falls back to the window's own length, which is
    exactly the behaviour every final bill had before this function existed, so
    an unreadable cycle can never make a bill WORSE than it already was.

    ⚠ **AND THAT FALLBACK IS NOT STATED ON THE PAYLOAD, WHICH IS A REPORTED
    GAP AND NOT A SHRUG — `DEF-BIL-5987`.** `cut_bill` says the same thing out
    loud (`CUT_BILL_DENOMINATOR_ABSENT`) and this path does not, so a tenant
    whose cycle cannot be read gets a full base charge on a closing bill with
    nothing on screen saying why. It is not fixed HERE because the two ways to
    say it are both bigger than this fix: a second `billing_period_for_unit`
    read inside one payload is how two figures about one customer's money come
    to disagree on one screen, and the alternative widens `AccountBillingData`,
    a FROZEN contract every billing stage consumes. `cycle_days` and
    `service_days` are both already on the preview's wire, so the arithmetic is
    visible even while the REASON is not.

    ⚠ **`as_of` IS THE MOVE-OUT DAY, NOT A CLOCK (BR-TEN-043 / G6).** A move-out
    on 18 February keyed by a clerk in March must divide by February's 28 days
    and not March's 31 — on a $40.00 base that is $25.71 against $23.23. The
    event date is the account's, so it is passed; nothing here reads today.
    """
    period_for = gather._resolve("metering", "billing_period_for_unit")
    if period_for is None:
        # Unpublished reads as *unreadable*, not as a guess. The caller's
        # fallback is the pre-existing behaviour, so this degrades to what the
        # product did yesterday rather than to a number nobody configured.
        return None
    window = period_for(unit_id, as_of=as_of)
    if not window:
        return None
    try:
        start = date.fromisoformat(str(window["start"]))
        end = date.fromisoformat(str(window["end"]))
    except (KeyError, TypeError, ValueError):  # pragma: no cover - defensive
        return None
    days = (end - start).days + 1
    return days if days > 0 else None


def prepare_final_bill(
    *,
    account_id: Any,
    period_start: date,
    moved_out_on: date,
    cycle_days: int | None = None,
    scope_services: tuple[str, ...] | None = None,
    keyed_reads: Any = None,
) -> AccountBillingData:
    """Gather the closing period — THROUGH the move day. Writes nothing.

    BR-CUS-056 is explicit and the move-out handoff repeats it (`bill_through`,
    `bill_through_br_ref: "BR-CUS-056"`): the OUTGOING account pays the move
    day, so `period_end` IS `moved_out_on` and never the day before. The
    incoming account starts the day after, from the same reading — no gap, no
    double (US-BIL-010's half of the same rule).

    `cycle_days` defaults to the CYCLE's length when the caller states it, not
    the closing period's: a tenancy ending on the 12th of a 31-day cycle owns
    12 of 31 days, and defaulting the denominator to 12 would charge a full
    month's base charge for twelve days.

    ⚠ **AND IT IS NOW READ WHEN THE CALLER DOES NOT STATE IT (PO 2026-09-20,
    *"okay we have to buld it there will ebe code to reuse"*).** Every caller
    of this function stated `None` — `one_time._cycle_days` answers `None` for
    every kind and `preview_final_bill` defaults to it — so the sentence above
    described a parameter nobody passed and a closing customer served 12 days
    of a 30-day cycle was billed the whole **$18.50** base where 12/30 gives
    **$7.40**: **$11.10 too much**, on the last bill anybody will ever read.
    `_closing_cycle_days` supplies it from the account's own cycle now, and the
    three-way order is deliberate:

      1. a STATED `cycle_days` still wins, so a caller that knows the
         denominator is never overruled by a read;
      2. otherwise the CYCLE's own calendar length, B4.3's ❄️ term as GT-3
         states it (*"Base proration 15/30 × 30.50 = 15.25"*);
      3. and only when the cycle cannot be read, the window's own length —
         which is exactly what every final bill did before, so an unreadable
         cycle degrades to yesterday's behaviour and never to a guess.

    ⚠ **THIS IS THE ONE PLACE THE FINAL BILL'S DENOMINATOR IS DECIDED, AND
    THAT IS WHY IT IS HERE AND NOT IN `one_time`.** The One-time tab's preview,
    the move-out wizard's preview and the DRAFTED invoice all reach this
    function — `one_time.preview(kind='final')`, `preview_final_bill` and
    `one_time._draft_for(kind='final')` — so they move together **by
    construction** rather than by three edits that a later lane could make two
    of. A preview that prorated while the draft did not would show a clerk one
    figure and raise another, which is the exact drift `runs.price_account` was
    extracted to make impossible.
    """
    if moved_out_on < period_start:
        raise BillingRuleError(
            f"the move-out date {moved_out_on} is before the period start "
            f"{period_start}. A final bill covers the days the customer held the "
            "service, and a negative window has none.",
            # `DEF-BIL-10052` follow-up (walk, 2026-10-11) — this sentence
            # reached the move-out screen verbatim with ISO dates; the clerk
            # reads a catalogue sentence and goes back to the date on step 2.
            message_key="billing.finalPreview.moveOutBeforePeriod",
        )
    scope = moving_out_account(account_id)
    # ── `DEF-BIL-8702` · AN ACCOUNT ON NO CYCLE IS REFUSED HERE, AT EVERY DOOR ──
    # PO ruling 2026-10-01, verbatim: *"show warning and A · Refuse until the
    # account has a cycle (same as first bill)"*. The One-time tab asked
    # `one_time.refuse_a_bill_with_no_cycle` before reaching this function; the
    # move-out wizard's preview (`preview_final_bill`) did not, and priced the
    # base WHOLE for a part month — Maria's ten days charged the month's $30.50.
    # Asked HERE, the one function all three doors share, with the same seam,
    # key and sentence, so the preview, the One-time tab and the draft cannot
    # disagree. Lazy: `one_time` imports this module.
    from apps.billing import one_time

    one_time.refuse_a_bill_with_no_cycle(account_id, kind=one_time.KIND_FINAL)
    days = cycle_days
    if days is None:
        # BR-TEN-043 / G6 — the MOVE-OUT day, never a clock. A February
        # move-out keyed in March divides by February's 28 days.
        days = _closing_cycle_days(scope.unit_id, as_of=moved_out_on)
    if days is None:
        # Reached ONLY by an account that IS on one cycle whose calendar cannot
        # be read — a pre-`CR-029` cycle with no `frequency`/`first_run_date`
        # (`tc12d`). An account on NO cycle was refused above. The window's own
        # length is what every final bill did before 2026-09-20, so an
        # unreadable calendar degrades to that and never to a guessed 30.
        days = (moved_out_on - period_start).days + 1
    # ── `DEF-CUS-5932` · THE CLASS IS READ BEFORE THE GATHER, NOT AFTER ──────
    # ⚠ **THIS CHECK STOOD BELOW `gather_single` UNTIL 2026-09-20 AND WAS
    # THEREFORE UNREACHABLE IN THE PRODUCT.** Closing an account removes its
    # plan resolution, so the gather refused first: a clerk who committed the
    # move-out and then asked for the final bill was told *"no plan version in
    # force on 2026-01-28 (BR-RAT-007)"* — true, and about tariff versions,
    # when what they need to know is that the bill had to be raised BEFORE the
    # close and now cannot be raised at all. The branch was proved reachable by
    # a unit test that constructed the behaviour class directly and was
    # unreachable from the state a clerk is actually in: hard-won law 7's
    # fourth shape, in an error path, on the last bill of a tenancy.
    #
    # `gather._behavior_class` is reached rather than re-read off the status
    # row, for the reason `single.gather_single` gives for reaching into
    # `runs._readings_for`: the alternative is a second reading of BR-CUS-055
    # — *"never guessed from a status NAME, because a tenant may add statuses"*
    # — and one of the two copies would eventually be the wrong one.
    behavior_class = gather._behavior_class(scope.account)
    if behavior_class not in BILLABLE_CLASSES:
        raise gather.GatherProblem(
            FINAL_ACCOUNT_ALREADY_CLOSED,
            f"account {scope.account_no} is already {behavior_class!r}, and stage 1 "
            "refuses to price an account that is not billable (BR-CUS-055). The final "
            "bill therefore has to be produced BEFORE the move-out writes the close — "
            "which is the order S20's wizard uses (step 3 'Final bill & deposit', then "
            "publish). If the product wants the handoff order instead (customers closes, "
            "billing bills), stage 1 needs a stated final-bill exception; that is a "
            "change to apps/billing/stages/resolve_subscription.py and to the customers "
            "sequencing, and it is REPORTED rather than made here.",
        )
    data = single.gather_single(
        scope,
        period_start=period_start,
        period_end=moved_out_on,  # BR-CUS-056 — THROUGH the move day
        service_date=moved_out_on,
        cycle_days=days,
        scope_services=scope_services,
        # `DEF-CUS-5931` — step 2's capture, priced here and written at step 6.
        keyed_reads=keyed_reads,
    )
    # ── `DEF-BIL-8749` (CR-156-BRC10) · A CHARGE-CODE PRICE CHANGE CUTS IT ───
    # Asked HERE, the one function all three doors share (One-time tab preview
    # and draft, move-out wizard), so they cannot disagree. Each part divides
    # by the cycle's length on the part's own last day — the read above,
    # applied per part — unless the caller STATED a denominator, which still
    # wins for every part. No change inside the window → untouched.
    def per_part(part_start: date, part_end: date) -> int:
        if cycle_days is not None:
            return cycle_days
        return _closing_cycle_days(scope.unit_id, as_of=part_end) or days

    return single.with_price_split(
        data,
        scope,
        period_start=period_start,
        period_end=moved_out_on,
        cycle_days=days,
        cycle_days_for=per_part,
        scope_services=scope_services,
        keyed_reads=keyed_reads,
    )


def calculate_final_bill(
    data: AccountBillingData,
    *,
    bill_run: models.BillRun,
    service_date: date | None = None,
) -> models.Invoice:
    """Stages 1 → 6 for the closing period. ONE draft, typed `final`.

    The same `runs.calculate_account` a cycle run uses — a final bill is priced
    by the same engine on the same rules, and the only thing that makes it
    final is what happens to its remainder afterwards.
    """
    return runs.calculate_account(
        data,
        bill_run=bill_run,
        service_date=service_date or data.period_end,
        bill_type="final",
    )


def settle_final_bill(invoice: models.Invoice, *, chosen: str | None = None) -> Settlement:
    """The settlement for a drafted final bill (`invoices.total` are its charges).

    Reads the charges off the bill rather than taking them as an argument, so
    the figure the deposit is applied to is the figure the customer was billed
    — the two cannot drift apart between the draft and the settlement screen.

    **THE DEPOSIT SETTLES THE WHOLE CLOSING POSITION — PO 2026-08-12, OQ-158
    CLOSED.** Verbatim: *"everything outstanding"*.

    BR-BIL-013 settles *"the remainder"*, and the two readings of that word
    differ by every dollar the customer already owed. Worked, on the prototype's
    own move-out step 3: a **$120.84** prior balance beside final charges, inside
    a *Final amount due* of **$184.20**. Under the BILL-ONLY reading a WE-7
    deposit would REFUND **$90.14** to a customer who still owes **$120.84** on
    an account that is now closed — the product would post a cheque to somebody
    who is in debt to it. The whole-position reading is what BR-BIL-013 exists
    for, and it agrees with the PO's OQ-179 ruling of the same day: the deposit
    settles ONCE, at closure, against everything.

    ❄️ **WE-7's frozen figures are unaffected and that is checkable, not
    asserted:** its account carries no arrears, so `prior_balance` is zero and
    the two readings produce the identical number. The frozen example was never
    the ambiguous case.

    This function REFUSED here until the ruling landed, and the refusal was
    right: the difference is real money on a closed account, where there is no
    next month in which to correct it.
    """
    if invoice.bill_type != "final":
        raise BillingRuleError(
            f"invoice {invoice.pk} is typed {invoice.bill_type!r}, not 'final'. The "
            "deposit settles ONCE, on the final bill (BR-BIL-013); applying it to an "
            "ordinary cycle bill would credit the customer twice over the tenancy."
        )
    return settle_closing_position(
        account_id=invoice.account_id,
        total=invoice.total,
        currency=invoice.currency,
        # ⚠ **THE DAY THE INTEREST ACCRUES TO IS THE MOVE-OUT DAY, AND IT IS
        # READ OFF THE BILL RATHER THAN OFF A CLOCK** (`DEF-CWP-3842`, and gate
        # G6's rule that a money path reads no wall clock). `BR-CUS-056` and
        # `prepare_final_bill` both put it there in as many words: *"the
        # OUTGOING account pays the move day, so `period_end` IS
        # `moved_out_on`"* — which is the day the deposit stops being held and
        # therefore the day `BR-CUS-057`'s accrual ends. A settlement re-opened
        # next month recomputes to the SAME figure, because the date is a
        # stored business fact and not today.
        moved_out_on=invoice.period_end,
        chosen=chosen,
    )


def settle_closing_position(
    *,
    account_id: Any,
    total: Decimal,
    currency: str,
    moved_out_on: date,
    chosen: str | None = None,
) -> Settlement:
    """`settle_final_bill` with the bill's TOTAL passed instead of read. Pure.

    ⚠ **EXTRACTED FOR THE ONE-TIME TAB'S STEP 3** (`CR-108` wave 1). The tab
    shows a clerk *Deposit and its interest, applied first* and *Still due · to
    collect* BEFORE anything is drafted, and there is no invoice to read a total
    off at that moment — the figure is `runs.price_account`'s, from stages 1–5.

    Everything else is identical and deliberately so: the same `_prior_balance`,
    the same `money.finalize(total + prior)` composition the PO's OQ-158 ruling
    requires (*"everything outstanding"*), the same unit, the same threshold and
    the same `as_of`. A preview that added the prior balance itself would be a
    second reading of BR-BIL-013's word *remainder*, and the two readings differ
    by every dollar the customer already owed — **$120.84** on the prototype's
    own move-out, which is the difference between collecting and posting a
    cheque to somebody in debt to the utility.
    """
    unit_id = getattr(moving_out_account(account_id), "unit_id", None)
    prior_balance = _prior_balance(account_id)
    return settle_account(
        account_id=account_id,
        unit_id=unit_id,
        # PO 2026-08-12: the final CHARGES plus everything already outstanding.
        charges=money.finalize(total + prior_balance),
        currency=currency,
        as_of=moved_out_on,
        chosen=chosen,
    )


def _prior_balance(account_id: Any) -> Decimal:
    """What this account owed BEFORE its final bill — the LEDGER's position.

    ⚠ **AMENDED 2026-08-16 (DEF-127). THIS DOCSTRING USED TO READ "customers'
    cached balance", and the caveat under it no longer applies** — it said the
    cache was *"used here for a REFUSAL and never for an arithmetic"*, which
    stopped being true when the PO closed OQ-158 on 2026-08-12 (*"everything
    outstanding"*) and this figure went INTO the settled base. `account_detail`
    now serves the ledger's own Σ over posted journal lines, so this reads the
    books rather than a column nothing writes — which is the only reason the
    arithmetic OQ-158 asks for is sound at all.

    **A BALANCE THAT COULD NOT BE READ REFUSES THE SETTLEMENT.** `_money`
    answers `Decimal("0")` for None, which was safe while the value came from a
    NOT NULL column and is not safe now: since DEF-127 the read is null whenever
    the books cannot be asked, and a settlement that treated that as zero would
    **refund a deposit to a customer who still owes money**, on an account that
    has just closed and that nobody will look at again. That is DEF-127's own
    shape moved into a write path, so it is refused here by name rather than
    left to `_money`'s zero.

    A draft final bill is not in the position — a draft posts nothing
    (BR-BIL-004) — so a non-zero answer is genuinely prior.
    """
    detail = gather._resolve("customers", "account_detail")
    if detail is None:  # pragma: no cover — `deposit_credit_for` refuses first
        raise BillingRuleError(
            "customers has not published account_detail, so the closing balance cannot "
            "be read and no final bill can be settled."
        )
    row = detail(account_id)
    balance = row.get("balance")
    if balance is None:
        reasons = "; ".join(str(gap.get("code")) for gap in (row.get("balance_unavailable") or ()))
        raise BillingRuleError(
            f"the closing balance of account {account_id} could not be read from the books"
            + (f" ({reasons})" if reasons else "")
            + ". PO 2026-08-12 (OQ-158) settles *everything outstanding*, so the prior "
            "balance is part of the settled base and a final bill cannot be computed "
            "without it. Refused rather than read as 0.00 — a zero here refunds the "
            "deposit of a customer who is in debt to the utility, on an account that has "
            "just closed (DEF-127)."
        )
    return _money(balance, "the account's balance")


# ── the PREVIEW: price the final bill, write nothing (S20 step 3) ───────────
#: What `preview_final_bill` refuses with when the account has already been
#: closed. VALUES — S20's step 3 groups on them, exactly as the three above.
PREVIEW_PERIOD_START_UNDERIVABLE = "final_bill_period_start_not_derivable"


def _preview_refusal(refusal: Exception, fallback_reason: str) -> dict[str, Any]:
    """`priced_unavailable` for a refusal: the code, the engine's sentence and,
    where the refusal names one, its CLERK sentence's catalogue key.

    `DEF-BIL-8702`: the move-out wizard reads `message_key`/`message_params`
    (`moveShared.tsx`, `refusalSentence`) and this payload never sent them, so a
    refusal with a clerk sentence — *"No billing cycle. Assign one on the
    account."* — could only reach step 3 as the engine's English. Sent now
    whenever the refusal carries a key; absent otherwise, so nothing changes for
    a refusal that names none.
    """
    body: dict[str, Any] = {
        "reason": getattr(refusal, "reason", fallback_reason),
        "detail": str(refusal),
    }
    message_key = getattr(refusal, "message_key", None)
    if message_key:
        body["message_key"] = message_key
        params = getattr(refusal, "params", None)
        if params:
            body["message_params"] = dict(params)
    return body


PREVIEW_VALUES_MISSING = "values_missing"


def missing_values(data: AccountBillingData, *, account_id: Any) -> list[dict[str, Any]]:
    """Every metered service the engine would refuse for want of a usage figure.

    `DEF-BIL-10052`. The test is the engine's own — stages 1 and 2 run as
    `runs.price_account` runs them, then its unresolved-read filter
    (`_unresolved_services`, `DEF-BIL-10128`) — so this names exactly what
    the engine would refuse on, all at once. Each
    entry carries the service, the unit's meter numbers for it (from metering,
    never an id — B14 rule 31) and WHAT is missing: `reading`, or
    `estimate_no_history` when the clerk asked for an estimate metering could
    not give.
    """
    from apps.billing import metering_seam

    gaps = _unresolved_services(data)
    if not gaps:
        return []
    unit_id = single.billable_account(account_id).unit_id
    try:
        meters = metering_seam.meter_numbers_for_units([unit_id]).get(str(unit_id), {})
    except Exception:  # a name is a courtesy; the list is still true without it
        meters = {}
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for service in gaps:
        what = (
            "estimate_no_history"
            if str(service.absent_reason or "").startswith("estimate_unavailable:")
            else "reading"
        )
        key = (service.service_code, str(getattr(service.tariff, "asset_id", "") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "service": service.service_code,
                "meters": list(meters.get(service.service_code, [])),
                "what": what,
            }
        )
    return out


def _unresolved_services(data: AccountBillingData) -> list[Any]:
    """🔒 `DEF-BIL-10128` — the services `runs.price_account` would refuse for
    want of a usage figure, decided by the ENGINE'S OWN stages 1 and 2.

    ⚠ **NOT A SECOND COPY OF THE RULE, WHICH IS WHAT THE DEFECT WAS.** This
    function first read each gathered READING's `absent_reason` against
    `EXEMPT_FROM_MISSING_READ`. But whether a read was ever OWED is partly a
    fact about the TARIFF, not the reading: sewer priced as a percentage of
    water (BR-RAT-015, `measure_consumption.prices_no_consumption`) has no
    register, so metering's reading honestly says `no_meter` — not exempt —
    while stage 2 turns the same service into `tariff_prices_no_consumption`,
    which is. So on Ottumwa Water Works the draft said *"Sewer: reading
    needed"* for a service billed as *90.00% of Water usage* that the engine
    would have priced. `backbill` (`DEF-BIL-8310`) and `one_time`
    (`DEF-BIL-9750`) had each already met this exact vocabulary split.

    So the answer is computed the way `price_account` computes it: run
    `resolve_subscription` and `measure_consumption` (both PURE — BR-BIL-039,
    no write, no clock), and keep `usage.unmeasured` whose reason is not on
    `EXEMPT_FROM_MISSING_READ` — `price_account`'s own filter, verbatim. A
    base-only tariff, a percent-of-service tariff, a declared-unmetered
    service and a counted service all fall out of the stage exactly as they do
    on the bill; **a metered service with no read is still listed**, which is
    the half BR-BIL-015 exists for. A split period asks the same question of
    each sub-period, as `midperiod._measured_segment` does.

    A stage-1 refusal (no plan, an unbilled class) returns nothing here: the
    engine raises it with its own sentence one step later, and this list is
    about missing VALUES, not about every reason a bill can refuse.
    """
    from apps.billing.stages import measure_consumption as stage
    from apps.billing.stages.resolve_subscription import resolve_subscription

    segments = tuple(getattr(data, "split_segments", ()) or ())
    sources = [segment.data for segment in segments] if segments else [data]
    out: list[Any] = []
    for source in sources:
        try:
            usage = stage.measure_consumption(resolve_subscription(source), source)
        except BillingRuleError:
            return []
        out.extend(
            service
            for service in usage.unmeasured
            if service.absent_reason not in stage.EXEMPT_FROM_MISSING_READ
        )
    return out


#: The reason `metering.selectors.provisional_reads_for_unit` puts on a meter
#: the clerk keyed as an ESTIMATE: "the preview does not run the estimator".
KEYED_ESTIMATE_REASON = "provisional_estimate_not_computed"


def with_keyed_estimates(
    data: AccountBillingData, *, account_id: Any, period_start: date, period_end: date
) -> AccountBillingData:
    """🔒 `DEF-BIL-10052` — a move-out meter ticked *Estimate*, priced on its OWN estimate.

    PO 2026-10-11, verbatim: *"our goal should be to generate the draft bill and
    show it on the screen … we have done this in one time bill - final bill - it
    is working there"*. So this is `one_time.with_clerk_estimates`
    (`DEF-BIL-8562`) applied to the move-out preview: the quantity is
    METERING's (`backbill._metering_estimate` → BR-MET-026's write-nothing
    `back_bill_segment_estimate`) for exactly this window and meter, the
    reading is marked `estimated=True`, and nothing is written. A meter
    metering will not estimate (no history) keeps its absence, and the step
    says so in words. A committed or keyed reading always wins — only a row
    carrying `KEYED_ESTIMATE_REASON` is touched.
    """
    from dataclasses import replace

    from apps.billing import backbill, rating_seam

    readings = list(getattr(data, "readings", ()) or ())
    wanted = [
        index
        for index, reading in enumerate(readings)
        if reading.consumption is None and reading.absent_reason == KEYED_ESTIMATE_REASON
    ]
    if not wanted:
        return data
    unit_id = single.billable_account(account_id).unit_id
    for index in wanted:
        reading = readings[index]
        quantity, unit, reason = backbill._metering_estimate(
            unit_id,
            service_code=reading.service_code,
            period_start=period_start,
            period_end=period_end,
            asset_id=getattr(reading, "asset_id", None),
        )
        if quantity is not None:
            readings[index] = replace(
                reading,
                consumption=rating_seam.Quantity(amount=quantity, unit=unit),
                estimated=True,
                absent_reason=None,
            )
        elif reason:
            readings[index] = replace(reading, absent_reason=f"estimate_unavailable:{reason}")
    return replace(data, readings=tuple(readings))


def estimate_closing_usage(*, account_id: Any, meter_no: str, moved_out_on: date) -> dict[str, Any]:
    """`DEF-BIL-10052` task 5 — the estimate step 2 shows when *Estimate* is ticked.

    PO 2026-10-11: ticking Estimate fills the Reading with the estimate, marked
    *Estimated*. It is computed by the SAME path the draft bill prices it on —
    `prepare_final_bill` with this one meter keyed as an estimate, then
    `with_keyed_estimates` — so the figure shown on step 2 is the figure step 3
    bills, never a second arithmetic. WRITES NOTHING.

    Answers `{estimated: true, consumption, unit, service}` or
    `{estimated: false, reason}` (`no_history` and metering's other reasons).
    """
    from apps.billing import cut_bill

    try:
        period_start = cut_bill.first_unbilled_day(account_id)
        data = prepare_final_bill(
            account_id=account_id,
            period_start=period_start,
            moved_out_on=moved_out_on,
            keyed_reads=[{"meter_no": meter_no, "estimate": True}],
        )
    except (gather.GatherProblem, BillingRuleError) as refusal:
        return {"estimated": False, "reason": getattr(refusal, "reason", "not_prepared")}
    data = with_keyed_estimates(
        data, account_id=account_id, period_start=period_start, period_end=moved_out_on
    )
    # Which service this meter measures, so a reading the period ALREADY holds
    # can be named (a committed read always wins over a keyed estimate, so the
    # draft prices it — and step 2 must say so rather than "not available").
    from apps.billing import metering_seam

    unit_id = single.billable_account(account_id).unit_id
    try:
        by_service = metering_seam.meter_numbers_for_units([unit_id]).get(str(unit_id), {})
    except Exception:  # the name is a courtesy; the answer is still true without it
        by_service = {}
    service_of_meter = next(
        (service for service, numbers in by_service.items() if meter_no in numbers), None
    )
    # ⚠ `DEF-BIL-10129` — **OF THIS METER, NOT OF ITS SERVICE.** A billing
    # reading is one row per SERVICE POINT, so matched by service alone the
    # water point's committed read (W-5040's) was claimed for a master meter
    # and a sub-meter on the same point that had never been read, and step 2
    # printed *"Already read: 22 kgal billed."* beside *"Not enough history to
    # estimate."* in one row. Metering says which meter each read is on.
    ever_read = True
    for reading in data.readings:
        if (
            service_of_meter is not None
            and reading.service_code == service_of_meter
            and reading.read_id is not None
            and reading.consumption is not None
        ):
            read_ids = (reading.read_id, *(getattr(reading, "chain_read_ids", ()) or ()))
            ever_read, its_own = metering_seam.meter_reads_state(meter_no, read_ids)
            if not its_own:
                continue
            return {
                "estimated": False,
                "reason": "read_on_file",
                "service": reading.service_code,
                "consumption": str(reading.consumption.amount),
                "unit": reading.consumption.unit,
            }
    for reading in data.readings:
        if getattr(reading, "estimated", False) and reading.consumption is not None:
            return {
                "estimated": True,
                "service": reading.service_code,
                "consumption": str(reading.consumption.amount),
                "unit": reading.consumption.unit,
                "period_start": period_start.isoformat(),
            }
        reason = str(reading.absent_reason or "")
        if reason.startswith("estimate_unavailable:"):
            return {"estimated": False, "reason": reason.split(":", 1)[1]}
    if service_of_meter is not None and not ever_read:
        # `DEF-BIL-10129` — a meter on this unit that has never been read has
        # no history to estimate from; that is the true reason, and saying
        # *"not on this account"* of a meter listed on the account's unit
        # would be a second false fact.
        return {"estimated": False, "reason": "no_history"}
    return {"estimated": False, "reason": "meter_not_on_this_account"}


def preview_final_bill(
    *,
    account_id: Any,
    moved_out_on: date,
    period_start: date | None = None,
    cycle_days: int | None = None,
    scope_services: tuple[str, ...] | None = None,
    keyed_reads: Any = None,
) -> dict[str, Any]:
    """S20 step 3's figure: **what the final bill will contain, priced, unissued.**

    HUMAN-REVIEW-PENDING · 🔒 money path — AI-authored 2026-09-19 under the PO
    ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*).
    A row in `12-governance/09-human-review-ledger.md` states in plain English
    what this does and with which figures. Not RATIFIED without a recorded
    human sign-off.

    ════════════════════════════════════════════════════════════════════════
    PRICE, DO NOT POST — THE BLUEPRINT SETTLES IT ITSELF
    ════════════════════════════════════════════════════════════════════════
    The Billing blueprint, p112, in a dashed panel, verbatim: **"NO BILL IS
    ISSUED BY THIS SCREEN. Billing raises the final bill; this wizard prices
    what it will contain and posts nothing. The figures above are a settlement
    position, not an invoice, and the account closes owing what the invoice
    will say."**

    So this writes **no invoice, no invoice line, no journal line, no payment,
    no ledger entry and no bill number**. Stage 6 — `assemble_document` — is
    where a draft is written and where `core.numbering` spends a number
    (BR-BIL-063), and it is **not on this path**. That is precisely what makes
    the figure safe to compute inside a wizard a clerk may abandon halfway: a
    preview that wrote would make *looking* a committing action, and a clerk
    who backed out of step 3 would leave a spent bill number and a draft behind
    on a tenancy that never ended.

    ⚠ **IT IS NOT A SECOND ENGINE, AND IT MUST NEVER BECOME ONE.** Every figure
    here is `runs.price_account`'s — stages 1→5 of the run's own
    `calculate_account`, extracted line for line by `CR-075` wave F so that a
    figure could be shown without a draft. `calculate_account` **is**
    `price_account` followed by stage 6, so the lines a clerk approves at step 3
    and the lines Billing later raises **cannot differ, by construction rather
    than by assertion**. A copy of those five stages anywhere else is how a
    utility discovers that the figure shown before go-live is not the figure on
    the bill. `one_time.preview(kind='final')` reaches the same two calls for
    the One-time tab; this function is the move-out wizard's door to them, and
    the window is the only thing it adds.

    ════════════════════════════════════════════════════════════════════════
    WHY THE WINDOW IS DERIVED HERE AND NOT ASKED FOR
    ════════════════════════════════════════════════════════════════════════
    The wizard knows ONE date — the move-out day the clerk stated at step 2.
    The other end of the window is a money decision and is **never the front
    end's to guess**: `cut_bill.first_unbilled_day` is the day after the
    account's last ISSUED bill's period end (BR-BIL-004 — an issued bill is
    never re-billed), or its `opened_at` when nothing has ever issued, and it
    **REFUSES** an account with neither rather than assuming the first of the
    month. That refusal is carried out to the screen by name: a guessed start
    bills a customer for days that are not theirs, and the move-out day itself
    would bill them for none of the days they used.

    `period_start` may be STATED to re-price a window a clerk corrected; absent
    is the normal case and `period_start_derived` says which happened.

    ⚠ **`cycle_days` STILL DEFAULTS TO `None`, AND SINCE 2026-09-20 THAT MEANS
    *READ IT FROM THE ACCOUNT'S CYCLE* RATHER THAN *CHARGE THE BASE WHOLE*.**
    B4.3 ❄️ prorates a base charge by `service_days / cycle_days`.
    ✅ **THIS PARAGRAPH SAID THE OPPOSITE UNTIL 2026-09-20 AND THE FIGURE IS
    WHY IT MOVED:** a 12-day closing window carried `$18.50` whole where
    12/30 gives **`$7.40`** — **`$11.10` too much on a customer who is
    leaving**, on the last bill anybody will ever read. The PO was shown that
    case and ruled, verbatim: *"okay we have to buld it there will ebe code to
    reuse"*.
    **It needed no finance re-sign and that was ESTABLISHED, not assumed:**
    GT-3, ❄️ B5 FROZEN, states the denominator outright — *"move-in day 16 of
    30; base $30.50. Base proration **15/30** × 30.50 = **15.25**"* — so the
    frozen arithmetic already carried the term and only the computation was
    missing. A mid-cycle move-OUT is the mirror of that mid-cycle move-IN.
    **`prepare_final_bill` owns the read** (`_closing_cycle_days`), which is
    what keeps this door, `one_time.preview(kind='final')` and the DRAFTED
    invoice on one number by construction: a preview that prorated while the
    draft did not would show a clerk `$43.40` while Billing raised `$54.50`,
    the exact drift `runs.price_account` was extracted to make impossible.
    ⚠ **`OQ-242`'s WITHDRAWAL IS UNTOUCHED** — *"its proration denominator (the
    current guess OVER-CHARGES while it stands). - this is not required"*, PO
    2026-08-23 — because it answered a **CYCLE-LESS** one-time bill, which has
    no cycle to read a denominator from. `one_time._cycle_days` still answers
    `None` for every kind and an interim, back-bill, penalty or fee bill still
    carries its base charge whole.
    ⚠ **BOTH ARE PINNED, AND THEY ARE CITED BY FILE RATHER THAN BY CASE NUMBER
    ON PURPOSE — `DEF-GOV-5989`.** This docstring used to say *"`tc12` pins
    it"*, and there are THREE live tests answering to `tc12` on this path: the
    prorated final bill is
    `tests/test_br_bil_013_final_bill_preview.py::test_preview_tc12`, the
    cycle-less bill is
    `tests/test_cr029_rcw2_due_from_the_run.py::test_w2_t4__no_proration_
    denominator_is_invented_for_a_cycle_less_run`, and they are different bills
    rather than two readings of one rule. A bare `tcN` is a LOCAL label — every
    test file in this repo restarts at `tc1` — so using one as a global id is
    `DEF-2804`'s category error in another family, and on 2026-09-20 it told a
    lane to keep unchanged the very case the ruling required it to amend.

    **BR-CUS-056 puts the other end on the move day itself** — `period_end` IS
    `moved_out_on` and never the day before, because the OUTGOING account pays
    the move day and the incoming one starts from the same reading the next
    day. `prepare_final_bill` enforces it; this function passes it and does not
    re-decide it.

    ════════════════════════════════════════════════════════════════════════
    IT PRICES THE READS THE CLERK KEYED, WHICH NOBODY HAS COMMITTED
    ════════════════════════════════════════════════════════════════════════
    **PO ruling 2026-09-20, verbatim: *"option b is correct"*** — *price from
    what's keyed, commit at the close* (`DEF-CUS-5931`). Step 2 asks for the
    closing register and step 6 writes it, so when this function runs the
    closing read does not exist: `billing_reads_for_unit` answers `no_read`
    with no factor and `resolution.MeterMultiplierUnstated` refused **every
    move-out in the product** — `BR-MET-056` stores the factor USED and an
    absent factor is not 1.

    The rejected option was committing the reads at step 2. Its cost is the
    case the PO was shown: a clerk keys a closing electric read of **52,410**
    on the 28th, reaches step 4, is called away and never finishes — and a live
    meter now carries a committed final reading that the next bill run uses,
    for a move-out that never happened. `Save & exit` is on every step of this
    flow by the PO's own ruling of the same week, so abandonment is a designed
    path and not an edge case.

    **The commit order does not move**, and p111 is why: *"The reads are
    committed with the close, not before it. The whole move-out is one
    transaction, so a refused reading rolls the close back with it and
    everything stays on screen."* `keyed_reads` is READ here and written by
    nobody; `metering.provisional_reads_for_unit` overlays it and writes
    nothing.

    ⚠ **AND THE PAYLOAD SAYS SO, BECAUSE IT IS A DIFFERENT CLAIM.** A figure
    priced from a committed read is priced from a fact; this one is priced from
    what somebody typed and may still change before step 6. `priced_from_
    uncommitted_reads` and the services it names are on the wire so the screen
    can state it in its own words — B14 rule 33 caps HOW that is said, never
    whether. A committed read always wins: where the period already carries a
    head, this prices exactly what it priced before this ruling.

    ════════════════════════════════════════════════════════════════════════
    THE ORDER TRAP — THIS RUNS ON AN ACCOUNT THAT IS STILL OPEN
    ════════════════════════════════════════════════════════════════════════
    `prepare_final_bill` refuses an account whose behaviour class has left the
    billable set (BR-CUS-055), and says why in as many words: *"The final bill
    therefore has to be produced BEFORE the move-out writes the close."* A
    preview runs mid-wizard, on an account that has **not** been closed yet, so
    it is on the correct side of that trap by construction — and it **does not
    move the trap**, because it writes nothing at all. Nothing it does makes
    the later real bill impossible; running it twice, or not at all, leaves the
    account in exactly the state it found it.
    A clerk who has ALREADY committed the move-out gets
    `FINAL_ACCOUNT_ALREADY_CLOSED` here, returned rather than raised, with the
    engine's own sentence — which is the true state of that account and is the
    thing they need to be told.

    ════════════════════════════════════════════════════════════════════════
    WHAT IT DOES NOT APPLY, AND THAT IS THE POINT OF THE SPLIT
    ════════════════════════════════════════════════════════════════════════
    ⚠ **THE UNBANKED EXPORT CREDIT IS NOT SUBTRACTED HERE AND MUST NOT BE.**
    p112 draws it as a row of the final-bill table and draws *Final bill, net*
    beneath it, but BR-MET-107's credit is **metering's fact applied by the
    SETTLEMENT**: `customers.move_out_settlement` reads it and computes
    `final_bill_net = final_bill − export_credit` itself, and serves both on
    `GET /accounts/{id}/close-impact`. The billing engine prices no export
    credit line at all (measured 2026-09-19: zero occurrences of
    `export_credit` anywhere in `apps/billing/`). So `total` below is the
    CHARGES, it is exactly what `?final_bill=` wants, and a subtraction here
    would be a **second reading of BR-MET-107 that double-counts the credit** —
    the customer credited twice for the same exported kWh, on a closed account
    nobody re-reads.
    **The drawn table is therefore assembled from the two calls together:** the
    priced rows from here, the *Unbanked export credit* row and *Final bill,
    net* from `close-impact`'s `everything_outstanding`. Neither half computes
    the other's figure.

    The deposit is likewise **not** applied here. BR-BIL-013 applies it FIRST
    and the remainder is what selects the settlement path; that arithmetic is
    `settle_closing_position`'s and the wizard reaches it through
    `close-impact`, which applies the deposit, its BR-CUS-057 interest and the
    prior balance in one place. Two subtractions of one deposit inside one
    screen is how the *Deposit applied* row and the settlement row come to state
    different figures about the same customer's money.

    ════════════════════════════════════════════════════════════════════════
    NO `audit_log` ROW, AND THAT IS A DECISION RATHER THAN AN OMISSION
    ════════════════════════════════════════════════════════════════════════
    Hard rule 7 — *every money action writes `audit_log`* — is about money
    ACTIONS. **This moves no money, records no decision and changes no row**,
    so there is no act to audit; it is a read, and it takes the same posture
    `account_close_impact` already states for the same screen (*"A READ — no
    `audit_log` row, because nothing moved"*) and that `one_time.preview` takes
    for the identical pricing pass on the One-time tab. Auditing it would fill
    the log a clerk uses to reconstruct a money path with one row per keystroke
    of a wizard they may abandon, and would make the genuine rows — the
    shortfall decision, the refund, the issue — harder to find rather than
    easier. The three acts that DO move money each write their own, inside
    their own services.

    ════════════════════════════════════════════════════════════════════════
    GOLDEN COVERAGE, STATED HONESTLY
    ════════════════════════════════════════════════════════════════════════
    `10-scripts/03-golden-verify.py` reports **33 document self-consistency
    checks** and **imports no application code**, so it can never go red when
    this engine drifts. `06-backend/tests/golden/` is **engine-verified at 14 of
    the 61 signed GTs** (GT-1..11, 16, 24, 47). **GT-23 — WE-7, the final-bill
    settlement, ❄️ B5 FROZEN — is NOT among the fourteen**: no test in
    `tests/golden/` runs the engine over it. What guards these figures is
    `test_us_bil_011_final_bill.py`'s TC-1..TC-12 and this function's own tests;
    that is a real gap in the frozen contract and it is named here rather than
    left for a reader to discover from a directory listing.

    Returns a payload and **never raises for a pricing refusal** — a clerk who
    cannot be shown the lines can still be shown the account, the window and
    what is blocking it, which is `_priced_body`'s posture and for the same
    reason. `priced: false` carries **no total at all**: a `0.00` there is a
    money claim about a customer, and on a final bill it is the claim that they
    owe nothing.
    """
    # Lazy — `cut_bill` imports `one_time`, which imports this module, so a
    # module-level import here would close a cycle. The same idiom
    # `first_unbilled_day` itself uses for `billing.selectors`.
    from apps.billing import cut_bill, one_time

    body: dict[str, Any] = {
        "account_id": str(account_id),
        "period_end": moved_out_on.isoformat(),  # BR-CUS-056 — THROUGH the move day
        # p112's dashed panel, on the wire, so a screen cannot render this
        # payload as an invoice by accident and a reader of the API knows
        # before they look at the figures.
        "issues_nothing": True,
        "writes": [],
    }

    if period_start is None:
        try:
            period_start = cut_bill.first_unbilled_day(account_id)
        except BillingRuleError as refusal:
            body.update(
                {
                    "priced": False,
                    "lines": [],
                    "period_start": None,
                    "period_start_derived": True,
                    "priced_unavailable": {
                        "reason": PREVIEW_PERIOD_START_UNDERIVABLE,
                        "detail": str(refusal),
                    },
                }
            )
            return body
        body["period_start_derived"] = True
    else:
        body["period_start_derived"] = False
    body["period_start"] = period_start.isoformat()

    try:
        data = prepare_final_bill(
            account_id=account_id,
            period_start=period_start,
            moved_out_on=moved_out_on,
            cycle_days=cycle_days,
            scope_services=scope_services,
            keyed_reads=keyed_reads,
        )
    except (gather.GatherProblem, BillingRuleError) as refusal:
        # Returned, not raised — see the docstring. `FINAL_ACCOUNT_ALREADY_
        # CLOSED` arrives here on an account whose move-out is already
        # committed, carrying the engine's own sentence about bill-before-close.
        body.update(
            {
                "priced": False,
                "lines": [],
                "priced_unavailable": _preview_refusal(refusal, "not_prepared"),
            }
        )
        return body

    # ⚠ **STATED FROM WHAT THE ENGINE ACTUALLY PRICED, NEVER FROM WHAT WAS
    # PASSED IN.** A clerk may key a register on a meter whose closing read is
    # already committed, or on a meter that stands on another unit; in both
    # cases nothing provisional reaches the bill and the screen must not say it
    # did. `ServiceReading.provisional` is set by metering's overlay on the rows
    # it actually laid over, so this counts the engine's answer.
    # `DEF-BIL-10052` (PO 2026-10-11) — a meter the clerk ticked *Estimate* on
    # is priced on the meter's OWN estimate, the one-time bill's way, instead
    # of refusing the whole draft.
    data = with_keyed_estimates(
        data, account_id=account_id, period_start=period_start, period_end=moved_out_on
    )
    # `DEF-BIL-10052` (PO 2026-10-11) — *"if you dont get all those values - not
    # just 1 if 2, or 3 or 4 or any number then you should show bill is not
    # genertaed because all these valaues are missing"*. Every missing value is
    # named at once, before the engine is asked, so the clerk fixes them in one
    # pass instead of meeting them one refusal at a time.
    missing = missing_values(data, account_id=account_id)
    if missing:
        body.update(
            {
                "account_no": data.account_no,
                "priced": False,
                "lines": [],
                "priced_unavailable": {
                    "reason": PREVIEW_VALUES_MISSING,
                    "detail": "the draft bill is not generated: values are missing",
                    "message_key": "billing.finalPreview.notGenerated",
                    "missing": missing,
                },
            }
        )
        return body
    uncommitted = tuple(
        reading.service_code
        for reading in data.readings
        if getattr(reading, "provisional", False) and reading.consumption is not None
    )
    body.update(
        {
            "account_no": data.account_no,
            "service_days": data.service_days,
            "cycle_days": data.cycle_days,
            "priced_from_uncommitted_reads": bool(uncommitted),
            "uncommitted_read_services": list(uncommitted),
        }
    )

    try:
        priced_account = runs.price_account(data)
    except (gather.GatherProblem, BillingRuleError) as refusal:
        body.update(
            {
                "priced": False,
                "lines": [],
                "priced_unavailable": _preview_refusal(refusal, "not_priced"),
            }
        )
        return body

    priced = priced_account.priced
    # p112 draws *Water · 14 kgal · estimated*. BR-MET-029's flag is a fact
    # about the READ and lives on stage 2's `MeasuredService`, not on the rated
    # line, so it is joined back on the service CODE — the same key the
    # ledger's service→revenue map is keyed on. A line whose service did not
    # measure (a base-only or a tax line) is not estimated and says False.
    estimated_by_service = {
        service.service_code: bool(getattr(service, "estimated", False))
        for service in getattr(priced_account.usage, "measured", ())
    }
    lines = []
    for line in getattr(priced, "lines", ()):
        # ⚠ **`one_time._line_body` DELIBERATELY, NOT A SECOND SERIALIZER.**
        # The One-time tab and this wizard show the SAME bill; two copies of
        # the line shape is how they come to disagree about what a line is
        # (hard-won law 5 — one source, derive views on demand).
        row = one_time._line_body(line)
        row["estimated"] = estimated_by_service.get(row.get("service"), False)
        lines.append(row)
    body.update(
        {
            "priced": True,
            "lines": lines,
            # rule 2 — money travels as TEXT, never a float, and is the
            # ENGINE's own finalized figure passed through untouched. ⚠ **IT
            # IS NOT RE-QUANTIZED HERE AND THIS COMMENT DOES NOT PROMISE A
            # NUMBER OF DECIMALS** (hard-won law 1 — a comment claiming a
            # guarantee is not the guarantee). B4 rounds per line AT
            # finalization (BR-RAT-003), so a rated line's amount arrives
            # already finalized: measured 2026-09-19, `36.00` / `18.50` /
            # `54.50` on the seeded utility, at two decimals. Quantizing to
            # four here would make this payload disagree with the drafted
            # invoice it is previewing, which is the one thing it may never do.
            # The same four keys `one_time.preview` and the drafted bill
            # return, so one shape is read before and after a write that this
            # function does not make. A SCREEN still displays at 2 (rule 2).
            "subtotal": str(getattr(priced, "taxable_subtotal", 0)),
            "tax_total": str(getattr(priced, "tax_total", 0)),
            #: **THE FIGURE `?final_bill=` WANTS.** The CHARGES, with no export
            #: credit and no deposit subtracted — see the docstring.
            "total": str(getattr(priced, "total", 0)),
            "currency": getattr(priced, "currency", None),
            "split": priced_account.split,
        }
    )
    return body


# ── DEF-CUS-10093 · THE MOVE-OUT'S COMPLETE DRAFTS THE FINAL BILL ───────────

#: The marker a move-out's final DRAFT carries in `bill_payload`. It is what
#: `move_out_final_draft` reads to allow the ONE carve-out the PO ruled — a
#: final draft created by a move-out may be sent after that move-out closed the
#: account — and nothing else in billing reads it.
MOVE_OUT_DRAFT_MARKER = "created_by_move_out"

#: The answer when every day up to the move day is already on an issued bill.
MOVE_OUT_NOTHING_TO_BILL = "nothing_to_bill"
MOVE_OUT_DRAFTED = "drafted"
MOVE_OUT_REFUSED = "refused"


def draft_move_out_final_bill(
    actor: Any,
    *,
    account_id: Any,
    moved_out_on: date,
) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-CUS-10093` — Complete drafts the final bill.

    **PO ruling 2026-10-13, option B, verbatim:** *"Go with this - I recommend
    B: nothing can be forgotten, readings are typed once, and the clerk still
    reviews the bill before it goes out."* So the move-out's Complete calls
    this INSIDE its own transaction, AFTER the closing reads are committed and
    BEFORE `closed_at` is written. A refusal raises, and the caller's
    transaction rolls back the reads and the close with it.

    ⚠ **NOT A SECOND ENGINE.** This is `one_time.create` for `kind='final'` —
    the run row, `_draft_for` → `prepare_final_bill` → `calculate_final_bill`,
    and the `invoice.drafted` audit row — over the SAME window step 3's
    `preview_final_bill` priced: `cut_bill.first_unbilled_day` through the move
    day (BR-CUS-056), on the cycle's own denominator (`_closing_cycle_days`,
    B4.3 / GT-3). Step 3 priced the reads the clerk KEYED; by the time this
    runs those same reads are COMMITTED, and a committed read always wins, so
    the draft prices the same dials. `tests/test_def_cus_10093_move_out_drafts
    _the_final_bill.py` pins draft total = step 3 total.

    **It DRAFTS and never issues** — p112's *"NO BILL IS ISSUED BY THIS
    SCREEN"* holds, because a draft is not an issued bill. The clerk sends it
    from Billing (Approve / Cancel draft, 2.570.0).

    **The terms (a judgment, decision log 2026-10-13):** the bill date is the
    move-out date — `cut_bill.raise_and_issue_cut_bill`'s precedent for the
    other closing event (*"BR-BIL-070 — the date the event happened is the
    bill's date"*) — and the due days are the account's cycle's (BR-BIL-024,
    *"bill date + the cycle's due-days"*), the same default the One-time tab
    pre-fills. A final bill is refused without a cycle (PO 2026-10-01), so
    there is always one to read. Nothing here reads a clock (BR-TEN-043 / G6).

    Answers `{"outcome": "drafted", invoice_id, invoice_no, total, …}`,
    `{"outcome": "nothing_to_bill", …}` when an issued bill already covers the
    move day (BR-BIL-004 — never re-billed), or `{"outcome": "refused",
    reason, message_key, params, detail}` with the engine's own refusal — a
    window that cannot be derived, no cycle, a missing value, or a final run
    already raised for this window (BR-BIL-005). A refusal is RETURNED rather
    than raised so customers never has to import a billing exception (B1); it
    then refuses the whole move-out, which rolls back the reads it committed.

    ⚠ **ONE SAVEPOINT AROUND ALL OF IT — HARD-WON LAW 14.** On PostgreSQL a
    caught database error aborts the enclosing transaction; the savepoint is
    what lets the refusal travel back as an answer while the move-out's own
    transaction is still usable for the refusal it raises next.
    """
    from django.db import transaction

    from apps.billing import cut_bill, one_time, one_time_answer, runs as run_module

    try:
        with transaction.atomic():
            return _draft_move_out_final_bill(
                actor, account_id=account_id, moved_out_on=moved_out_on
            )
    except run_module.DuplicateRun as duplicate:
        params = one_time_answer.duplicate_params(duplicate.original)
        return {
            "outcome": MOVE_OUT_REFUSED,
            "reason": "final_bill_already_raised_for_this_window",
            "message_key": (
                "billing.oneTime.duplicateDraft"
                if one_time_answer.is_draft_duplicate(params)
                else "billing.oneTime.duplicate"
            ),
            "params": params,
            "detail": str(duplicate),
        }
    except (gather.GatherProblem, BillingRuleError) as refusal:
        return {
            "outcome": MOVE_OUT_REFUSED,
            "reason": str(getattr(refusal, "reason", None) or "final_bill_refused"),
            "message_key": getattr(refusal, "message_key", None),
            "params": dict(
                getattr(refusal, "message_params", None) or getattr(refusal, "params", None) or {}
            ),
            "detail": str(refusal),
        }


def _draft_move_out_final_bill(actor: Any, *, account_id: Any, moved_out_on: date) -> dict[str, Any]:
    """`draft_move_out_final_bill`'s body, inside its savepoint."""
    from apps.billing import cut_bill, one_time, one_time_answer

    period_start = cut_bill.first_unbilled_day(account_id)
    if period_start > moved_out_on:
        return {
            "outcome": MOVE_OUT_NOTHING_TO_BILL,
            "period_start": period_start.isoformat(),
            "period_end": moved_out_on.isoformat(),
        }
    scope = moving_out_account(account_id)
    terms = one_time_answer._cycle_terms(scope.unit_id) or {}
    due_days = terms.get("due_days")
    request = one_time.OneTimeRequest(
        account_id=str(account_id),
        kind=one_time.KIND_FINAL,
        period_start=period_start,
        period_end=moved_out_on,
        bill_date=moved_out_on,
        due_days=None if due_days is None else int(due_days),
    )
    body = one_time.create(request, run_by=actor, actor=actor)
    invoice = models.Invoice.objects.get(pk=body["invoice_id"])
    payload = dict(invoice.bill_payload or {})
    payload[MOVE_OUT_DRAFT_MARKER] = {
        "moved_out_on": moved_out_on.isoformat(),
        "br_ref": "DEF-CUS-10093 · PO 2026-10-13 option B",
    }
    invoice.bill_payload = payload
    invoice.save(update_fields=["bill_payload", "updated_at"])
    return {
        "outcome": MOVE_OUT_DRAFTED,
        "invoice_id": body["invoice_id"],
        "invoice_no": body.get("invoice_no"),
        "bill_run_id": body["run_id"],
        "status": body.get("status"),
        "total": body["total"],
        "currency": body.get("currency"),
        "period_start": body["period_start"],
        "period_end": body["period_end"],
    }


def move_out_final_draft(invoice: Any) -> bool:
    """True for a FINAL draft a move-out created — the ruled carve-out, and only it.

    PO 2026-10-13: *"Sending a draft whose account the move-out has since
    closed must be ALLOWED … That is the only carve-out, and only for a final
    draft created by a move-out."* Both halves are read off the bill itself.
    """
    return getattr(invoice, "bill_type", None) == "final" and bool(
        (getattr(invoice, "bill_payload", None) or {}).get(MOVE_OUT_DRAFT_MARKER)
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-011@f0a3c21 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane — US-BIL-011..014)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S20 step 3 / S30 are unbuilt) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_011_final_bill.py
# exceptions: (1) NO `final_settlements` TABLE EXISTS. US-BIL-011 §5 names one
#         (path enum, actor, when) and r10 #10/#11 name the balance-transfer
#         transaction and write-off support; `apps/billing/models.py` has
#         none of them and belongs to another lane. So `settle()` COMPUTES and
#         returns; nothing is written, no audit row is raised (there is no money
#         action to record yet), and "exactly ONE path per final bill" holds
#         within a call rather than across calls. REPORTED.
#         (2) DEPOSIT INTEREST IS READ, NEVER COMPUTED. BR-CUS-057 belongs to
#         customers (US-CUS-023 §7, unbuilt — its own move-out handoff says so).
#         A deposit whose interest cannot be read REFUSES; principal-only would
#         short every closing customer by WE-7's 3.50 on a bill that foots.
#         An account with NO deposit answers zero without the seam.
#         (3) THE TRANSFER PATH CAN NEVER BE OFFERED TODAY. OQ-069's prereq —
#         the landlord-agreement flag and the master-account designation — has
#         no table, no flag and no seam anywhere in this repository (measured:
#         one prose mention of "landlord" in a docstring). `master_account_for`
#         answers None WITH A REASON; the target is never a caller-supplied id,
#         so TC-6's forged transfer is unrepresentable rather than rejected.
#         (4) THE REFUND AND WRITE-OFF EXECUTIONS ARE NOT HERE. Payments owns
#         `refunds` (r1.1 path 1: "billing records the handoff only") and ledger
#         owns the deposit-liability DR / AR CR and the 6900 write-off posting
#         (J08 steps 1 and 5). Both are other lanes' files.
#         (5) A CLOSED ACCOUNT CANNOT BE BILLED, and the sequencing question is
#         REPORTED not decided: stage 1 refuses a `terminal` behaviour class
#         (BR-CUS-055) while BR-CUS-030/031 closes the account and THEN hands
#         off to billing. The happy path is the wizard's order (bill, then
#         close) and it works end to end; the handoff order needs a stated
#         final-bill exception in stages/resolve_subscription.py.
#         (6) The write-off threshold, the deposit and the master account are
#         all READ inside `settle_account` — a caller cannot supply them, which
#         is what stops a settlement being computed against a hand-typed
#         threshold or a hand-typed deposit.
#         (7) A CLOSING ACCOUNT WITH ARREARS SETTLES THE WHOLE POSITION — PO
#         2026-08-12, "everything outstanding". This paragraph described a
#         refusal until then and is rewritten rather than left standing, because
#         a trailer describing a refusal the code no longer makes is hard-won
#         law 1. The divergence was found by diffing this flow against
#         `05-prototype/UtilityBilling.html` (hard-won law 6): the prototype's
#         move-out step 3 settles a *Final amount due* of **184.20** that
#         INCLUDES a **120.84** prior balance, while WE-7 settles final CHARGES
#         alone; the bill-only reading refunded **90.14** to a customer still
#         **120.84** in arrears on a closed account. WE-7's own account has no
#         arrears, so its frozen figures are produced identically either way.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
