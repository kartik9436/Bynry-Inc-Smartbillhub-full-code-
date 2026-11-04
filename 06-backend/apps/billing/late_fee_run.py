# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-10200 (the bill run never applied a late fee — the formula
#           was built and nothing gathered what it is computed on) ·
#           DEF-BIL-10201 (a Flat late-fee code charged $0.00)
# Rules:    BR-BIL-001 as amended (max(min, pct × overdue) after due + grace;
#           nothing under the $25.00 overdue floor) · BR-BIL-008/002 (grace
#           days and mode, holidays) · BR-BIL-071 (lateness by the date the
#           money ARRIVED) · BR-BIL-003 (a waiver is manual, per account) ·
#           BR-RAT-1011 (the terms come from the code the PLAN names) ·
#           BR-CUS-043 / BR-BIL-073 SUPERSEDED IN PART 2026-10-17 (no late fee
#           while a payment plan is live) · BR-MET-133 clause 2 (a disputed
#           account is held out of the run; the disputed AMOUNT is OQ-420)
# Ruling:   decision log 2026-10-17 *"THE LATE FEE IS APPLIED BY THE BILL RUN,
#           AND MAY BE FLAT OR A PERCENTAGE"* and its two same-day paragraphs
#           (*"once per billing period"*; payment plans *"no"*)
# Golden:   GT-8 ❄️ — $542.10 → $8.13 is `late_fee.assess_late_fee`, called
#           unchanged through `late_fee.assess_late_fee_on_terms`
# Tests:    06-backend/tests/test_def_bil_10200_late_fee_in_the_bill_run.py
# ───────────────────────────────────────────────────────
"""THE LATE FEE THE BILL RUN ADDS — what is overdue, as of the run, per account.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — money math (CLAUDE.md sensitive paths),
AI-authored 2026-10-17 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`. Implements the rulings of
2026-10-17, never invents one: the ARITHMETIC is `late_fee.py`'s, unchanged.

THE RULING (decision log 2026-10-17, verbatim where quoted)
----------------------------------------------------------
*"this is good - we have to fix it"* — the bill run applies the late fee.
*"once per billing period"* — **at most ONE late fee per account per billing
period**: each run checks the account once; if an overdue amount ≥ $25.00 is
past due date + grace (by the date money arrived), one fee is added to that
period's bill, computed on the overdue portion at that run; still overdue at
the next period's run, that period gets its own single fee. Worked: bill A
$100 due 09/21 unpaid, bill B $80 due 10/21 unpaid → October one fee on $100 =
max($5, $1.50) = **$5.00**; November one fee on $180 = max($5, $2.70) =
**$5.00**. Payment plans: *"no"* — an account with a LIVE plan is charged no
late fee at all (Ana, October $62 unpaid past grace → **$0.00**, was $5.00).

WHAT "OVERDUE AT THIS RUN" IS — THREE FACTS, EACH READ FROM ITS OWNER
--------------------------------------------------------------------
For every ISSUED or PAID bill of the account from an EARLIER period whose
grace has run out by the run's bill date (`as_of`):

  * **a bill that went late since the account's previous bill** (its grace ran
    out after that bill's date — the moment the previous run looked) counts
    what was unpaid WHEN GRACE RAN OUT, judged by the date the money arrived
    (`late_fee.overdue_after_grace`). This is the PO's own example: $100.00
    due 09/21, grace to 09/26, paid 10/05 → the October run counts **$100.00**
    and charges **$5.00**, though it is paid by then.
  * **a bill that was already late at the previous run** counts only what is
    STILL unpaid now — so a bill paid late is fined once, by the run after it
    went late, and a bill still unpaid is fined again by each later period,
    exactly as *"that period gets its own single fee"* says.
  * the sum is ONE overdue figure, and ONE fee is computed on it.

The previous run's moment is the bill date (`invoices.service_date`) of the
account's newest locked bill from an earlier period — billing's own column, and
exactly the `as_of` that run assessed on. An account with no earlier bill has
no previous look, so every late bill is new to this run.

NEVER TWO IN ONE PERIOD. The figure is computed once per account per run
(`check_engine` C7 raises ONE `late_fee` finding; `decisions.apply_decisions`
draws at most one line from it), and an account that already holds a locked
bill for this period carrying a fee line on the plan's late-fee code gets
none (a second run over the same period, or a re-prepare after some bills
issued). A re-run or re-prepare therefore recomputes the same one figure and
never adds a second.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
  * **Disputed amounts — OQ-420 is OPEN.** Nothing records HOW MUCH of a bill
    is disputed; BR-MET-133 clause 2 already holds a disputed account out of
    the run (`runs._dispute_hold_for`), so such an account never reaches this
    module, and no disputed figure is invented for one that does.
  * **No waiver.** BR-BIL-003 makes it a person's act, per account, on the
    Check (`decisions.BULK_FORBIDDEN`); this module computes only.
  * **No clock.** `as_of` is the run's bill date, passed in (BR-TEN-043).

READS, BATCHED (NFR-3 / NFR-5 — no cap, no per-account statement for data)
-------------------------------------------------------------------------
`load_inputs` is asked ONCE per Check batch (500 accounts): billing's own
bills and fee lines (two statements), payments' receipts for those bills and
its live plans (two seam reads), the tenant's holidays and floor (once). The
per-account step then reads only the plan's terms, memoised by (plan, class).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from core import money

from apps.billing import late_fee, models, payments_seam

#: The finding code the Check raises — the taxonomy's existing `late_fee` tag
#: (Payments & balances, a decision answered on the Check).
LATE_FEE_CASE = "late_fee"
#: The catalogue sentence a finding row reads (all eleven catalogues).
FOUND_KEY = "billing.check.lateFee.found"
#: Paid bills older than this before the run cannot have gone late since the
#: previous run (grace is at most 30 business days, BR-BIL-008), so they are
#: not read: an open bill is read however old it is.
_PAID_LOOKBACK = timedelta(days=120)
#: The tenant-setting key the floor is read from when the tenant stores one
#: (OQ-157 CLOSED: a per-utility setting, $25.00 the seeded default).
FLOOR_SETTING = "late_fee_balance_floor"
#: What the Check declares when payments cannot say what met the bills.
RECEIPTS_UNAVAILABLE: dict[str, str] = {
    "code": LATE_FEE_CASE,
    "reason": "payments_receipts_not_published",
    "detail": (
        "payments does not publish what met each bill and when the money arrived, "
        "so no late fee was assessed — a bill paid on time cannot be told from one "
        "that was not"
    ),
}
_LATE_STATUSES = (models.INVOICE_ISSUED, models.INVOICE_PAID)


@dataclass(frozen=True)
class EarlierBill:
    """One issued bill of an earlier period, as the late fee needs to see it."""

    invoice_id: str
    invoice_no: str | None
    due_date: date
    amount_due: Decimal
    receipts: tuple[late_fee.PaymentReceipt, ...] = ()
    currency: str = "USD"


@dataclass
class LateFeeInputs:
    """Everything one Check batch shares — read once, per batch."""

    as_of: date
    bills: dict[str, list[EarlierBill]] = field(default_factory=dict)
    previous_look: dict[str, date] = field(default_factory=dict)
    charged_this_period: dict[str, set[str]] = field(default_factory=dict)
    live_plan: set[str] = field(default_factory=set)
    floor: Decimal = late_fee.LATE_FEE_BALANCE_FLOOR
    holidays: frozenset[date] | None = None
    unavailable: bool = False
    _terms: dict[tuple[str, str | None], Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LateFeeAssessment:
    """ONE account's late fee for this run — non-zero, or there is none."""

    account_id: str
    amount: Decimal
    overdue: Decimal
    bills: int
    terms: late_fee.LateFeeTerms
    currency: str = "USD"

    def params(self) -> dict[str, Any]:
        """The finding's facts — strings at stored scale (hard rule 2)."""
        return {
            "amount": str(self.amount),
            "overdue": str(self.overdue),
            "bills": self.bills,
            "code": self.terms.code,
            "name": self.terms.name,
            "charge_id": self.terms.charge_id,
            "amount_rule": self.terms.amount_rule,
            "currency": self.currency,
        }


def _floor() -> Decimal:
    """OQ-157 (CLOSED 2026-08-12) — the utility's own floor where it stores one;
    otherwise the seeded $25.00 the PO ruled. Storage for the key is not built
    yet, so every utility reads $25.00 today."""
    from apps.billing import settings_seam
    from apps.billing.exceptions import BillingConfigError

    try:
        raw = settings_seam.billing_defaults().get(FLOOR_SETTING)
    except BillingConfigError:
        raw = None
    if raw in (None, ""):
        return late_fee.LATE_FEE_BALANCE_FLOOR
    return Decimal(str(raw))


def load_inputs(
    account_ids: list[Any], *, as_of: date, period_start: date, period_end: date
) -> LateFeeInputs:
    """Read ONE batch's late-fee facts (see the module docstring)."""
    from apps.billing import selectors as billing_selectors

    inputs = LateFeeInputs(as_of=as_of)
    keys = [str(one) for one in account_ids]
    if not keys:
        return inputs
    tenant_id = billing_selectors._tenant_id()
    rows = (
        models.Invoice.objects.filter(
            tenant_id=tenant_id,
            account_id__in=keys,
            status__in=_LATE_STATUSES,
            period_end__lt=period_end,
            due_date__isnull=False,
            due_date__lt=as_of,
        )
        .exclude(status=models.INVOICE_PAID, due_date__lt=as_of - _PAID_LOOKBACK)
        .annotate(amount_due=billing_selectors.amount_due_expression())
        .values("id", "account_id", "invoice_no", "due_date", "amount_due", "currency")
        .order_by("due_date", "id")
    )
    bills = list(rows)
    receipts: dict[str, list[dict[str, Any]]] | None = {}
    if bills:
        receipts = payments_seam.receipts_for_invoices([str(row["id"]) for row in bills])
    if receipts is None:
        inputs.unavailable = True
        return inputs
    for row in bills:
        found = tuple(
            late_fee.PaymentReceipt(
                amount=Decimal(str(entry["amount"])),
                arrived_on=entry.get("arrived_on"),
                recorded_on=entry.get("recorded_on") or entry.get("arrived_on") or as_of,
            )
            for entry in receipts.get(str(row["id"]), ())
        )
        inputs.bills.setdefault(str(row["account_id"]), []).append(
            EarlierBill(
                invoice_id=str(row["id"]),
                invoice_no=row["invoice_no"],
                due_date=row["due_date"],
                amount_due=Decimal(str(row["amount_due"] or 0)),
                receipts=found,
                currency=row["currency"] or "USD",
            )
        )
    candidates = sorted(inputs.bills)
    if not candidates:
        return inputs
    # The previous run's look: the bill date of the newest locked bill of an
    # earlier period (void and corrected bills too — that run still looked).
    for account_id, service_date in (
        models.Invoice.objects.filter(
            tenant_id=tenant_id,
            account_id__in=candidates,
            status__in=models.INVOICE_LOCKED_STATUSES,
            period_end__lt=period_end,
        )
        .order_by("account_id", "-service_date")
        .values_list("account_id", "service_date")
    ):
        inputs.previous_look.setdefault(str(account_id), service_date)
    # Never two in one period: fee lines on a locked bill for THIS period.
    for account_id, charge_id in models.InvoiceLine.objects.filter(
        tenant_id=tenant_id,
        invoice__account_id__in=candidates,
        invoice__status__in=_LATE_STATUSES,
        invoice__period_end__gte=period_start,
        invoice__period_start__lte=period_end,
        kind="fee",
        charge_id__isnull=False,
    ).values_list("invoice__account_id", "charge_id"):
        inputs.charged_this_period.setdefault(str(account_id), set()).add(str(charge_id))
    plans = payments_seam.plan_instalments_for_accounts(candidates, due_by=None)
    inputs.live_plan = {str(key) for key in (plans or {})}
    inputs.floor = _floor()
    return inputs


def _holidays(inputs: LateFeeInputs) -> frozenset[date]:
    if inputs.holidays is None:
        from apps.billing import tenancy_seam

        inputs.holidays = tenancy_seam.holiday_dates()
    return inputs.holidays


def _terms(inputs: LateFeeInputs, rate_plan_id: Any, customer_class: str | None) -> Any:
    key = (str(rate_plan_id), customer_class)
    if key not in inputs._terms:
        inputs._terms[key] = late_fee.late_fee_terms_for_plan(
            rate_plan_id, customer_class=customer_class, on_date=inputs.as_of
        )
    return inputs._terms[key]


def _elapsed(bill: EarlierBill, on: date, days: int, mode: str, holidays: Any) -> bool:
    return late_fee.grace_has_elapsed(
        due_date=bill.due_date, as_of=on, grace_days=days, grace_mode=mode, holidays=holidays
    )


def assess_account(
    inputs: LateFeeInputs,
    account_id: Any,
    *,
    rate_plan_id: Any,
    customer_class: str | None,
) -> LateFeeAssessment | None:
    """🔒 HUMAN-REVIEW-PENDING — ONE account's late fee for this run, or None.

    None for: no earlier bill past its due date; a live payment plan (PO
    2026-10-17, *"no"*); a plan naming no late-fee code (BR-RAT-1011's ruled
    zero); a late fee already on a bill for this period; nothing overdue past
    grace; overdue under the floor. Raises `late_fee.LateFeePlanUnreadable` /
    `LateFeeClassNotPriced` (the Check records the account as refused) only
    when there IS something overdue to charge on — a fault in the terms of an
    account owing nothing stops nobody."""
    key = str(account_id)
    bills = inputs.bills.get(key)
    if not bills or inputs.unavailable or key in inputs.live_plan:
        return None
    terms = _terms(inputs, rate_plan_id, customer_class)
    if terms is None:
        return None
    if terms.charge_id in inputs.charged_this_period.get(key, set()):
        return None
    days, mode = late_fee.late_fee_grace_of(terms)
    holidays = _holidays(inputs) if mode == late_fee.GRACE_BUSINESS else None
    looked = inputs.previous_look.get(key)
    overdue = Decimal("0")
    counted: list[EarlierBill] = []
    for bill in bills:
        if not _elapsed(bill, inputs.as_of, days, mode, holidays):
            continue
        newly_late = looked is None or not _elapsed(bill, looked, days, mode, holidays)
        if newly_late:
            part = late_fee.overdue_after_grace(
                amount_billed=bill.amount_due,
                payments=bill.receipts,
                due_date=bill.due_date,
                assessed_on=inputs.as_of,
                grace_days=days,
                grace_mode=mode,
                holidays=holidays,
            )
        else:
            paid = sum(
                (r.amount for r in bill.receipts if r.recorded_on <= inputs.as_of), Decimal("0")
            )
            part = money.finalize(max(bill.amount_due - paid, Decimal("0")))
        if part > 0:
            overdue += part
            counted.append(bill)
    if not counted:
        return None
    amount = late_fee.assess_late_fee_on_terms(
        terms,
        overdue_amount=money.finalize(overdue),
        # Grace has run out on every counted bill; the oldest names the clock.
        due_date=counted[0].due_date,
        as_of=inputs.as_of,
        grace_days=days,
        grace_mode=mode,
        holidays=holidays,
        balance_floor=inputs.floor,
    )
    if amount <= 0:
        return None
    return LateFeeAssessment(
        account_id=key,
        amount=amount,
        overdue=money.finalize(overdue),
        bills=len(counted),
        terms=terms,
        currency=counted[0].currency,
    )
