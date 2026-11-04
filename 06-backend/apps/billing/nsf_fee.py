# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10698 (a bounce never charged the NSF penalty)
# Rules:    BR-PAY-013 (NSF charge code auto-added on a bounce) · BR-BIL-007
#           (the fee is the tenant's charge code, the LINE WRITE is billing's)
#           · BR-BIL-019/020 (no hand-typed amount on any bill) · CLAUDE.md
#           rules 2, 4, 5, 7
# Ruling:   PO 2026-10-30, decision log "The NSF penalty is charged on a
#           bounce, priced Account › Unit › Plan › Charge code, never
#           hard-coded" and "NSF penalty can be unticked with a reason"
# Tests:    06-backend/tests/test_def_pay_10698_nsf_fee.py
# ───────────────────────────────────────────────────────
"""The NSF penalty a bounce charges: found through the plan, raised as a fee bill.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (CLAUDE.md 🔒 — this decides what a
customer is charged). Row in `12-governance/09-human-review-ledger.md`,
*"2026-10-30 · THE NSF PENALTY IS CHARGED ON A BOUNCE"*.

PO 2026-10-30, verbatim: *"Do not hardcode check NSF Account> Unit> Plan>
Charge code"*. So the amount is found by a WALK and never typed:

    account ──unit_id──▶ unit ──rate_plan_id──▶ plan
            ──the plan's Charges list, the code DECLARED `is_nsf_fee`──▶ code
            ──`rating.charge_by_code`, on the bounce date──▶ amount

The first two hops are the walk `fee_bill._fee_bill_taxes` and `gather` already
make (a master account with no unit of its own reads the first unit it covers,
`BR-CUS-1010`); the third is rating's `plan_nsf_charge`; the fourth is the
one charge-code pricer every fee bill uses. **Nothing here prices anything.**

Worked (decision log): cheque 4102 $76.40 bounces on an account whose unit's
plan lists `NSF` at $30.00 → one fee bill of **$30.00**, issued → the account
owes $76.40 + $30.00 = **$106.40**.

THE FEE IS RAISED THROUGH THE DOOR THE RECONNECTION FEE USES
(`fee_bill.raise_and_issue_charge_fee`, DEF-708): a `fee` bill, drafted and
ISSUED in one act, so it is a receivable the moment the bounce is recorded;
issue stamps the code's GL and hands the posting to the ledger (rule 5). It is a
NEW invoice — nothing already issued is touched (rule 4). `due_days=0`: the
penalty is owed the day the item came back, the posture `BR-CUS-104` takes for
the reconnection fee owed at the cut.

ONE FEE PER BOUNCED PAYMENT (`DEF-PAY-10740`, PO 2026-10-30, decision log *"One
NSF fee per bounced payment"*, item 1 — *"Two bounces on the same day: A"*).
That door is keyed (account, `fee`, day), which is right for a cut and was
wrong here: a second cheque bouncing on the same account the same day charged
nothing and reported `nsf_fee_not_raised`. So this module passes the BOUNCED
PAYMENT's id as the run key's source (`nsf:<payment uuid>`). Worked: Clara
Castillo's cheques $76.40 and $40.00 both return on 31 Oct, plan NSF $30.00 →
two fee bills, **$60.00**; the same payment asked again (a replay, a second
partial) → the same key → still one. The reconnection fee passes no source
and keeps its key byte for byte.

EVERY ABSENCE IS NAMED, NEVER A $0.00. `quote_nsf_fee` answers one of:

  * `charged` — a code was found and priced; `amount` is what will be billed;
  * `nsf_fee_not_set_on_plan` — the plan lists no NSF code (an ordinary state:
    the utility charges no NSF fee on that plan);
  * `nsf_fee_ambiguous_on_plan` — the plan lists two; never resolved by order;
  * `nsf_fee_no_plan` — the account's unit stands on no plan;
  * `nsf_fee_cannot_be_priced` — the ACCOUNT cannot be billed (outside the
    billable set, `DEF-PAY-10746`), or the code is found and refuses to price (no GL
    account, a percent rule, a retired code …); `detail` carries fee_bill's own
    sentence.

The same answer is the PREVIEW (the Reverse dialog's "+$30.00 NSF fee" before
Confirm) and the input to the WRITE, so the figure a clerk is shown is the
figure the bill carries — `fee_bill.price_charge_fee`'s own reason for
existing.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.billing import fee_bill, gather
from apps.billing.exceptions import BillingRuleError
from core.errors import NotFoundError
from core.money_fields import AMOUNT_QUANTUM

__all__ = ["quote_nsf_fee", "raise_nsf_fee"]

CHARGED = "charged"
NOT_SET_ON_PLAN = "nsf_fee_not_set_on_plan"
AMBIGUOUS_ON_PLAN = "nsf_fee_ambiguous_on_plan"
NO_PLAN = "nsf_fee_no_plan"
CANNOT_BE_PRICED = "nsf_fee_cannot_be_priced"
NOT_RAISED = "nsf_fee_not_raised"


def _plan_id_of(account_row: Any) -> Any:
    """account → unit → plan, the walk `fee_bill._fee_bill_taxes` makes."""
    unit_id = getattr(account_row, "unit_id", None)
    if unit_id is None:
        covered = gather.covered_units(account_row)
        unit_id = covered[0] if covered else None
    unit_row = gather._resolve("metering", "unit_row")
    if unit_row is None or unit_id is None:
        return None
    unit = unit_row(unit_id)
    return getattr(unit, "rate_plan_id", None) if unit is not None else None


def quote_nsf_fee(account_id: Any, *, on_date: date) -> dict[str, Any]:
    """What a bounce on `on_date` would charge this account — writes nothing.

    `{"status", "code", "name", "amount", "currency", "detail"}`. `amount` is
    the fee bill's TOTAL (a code the tenant marked taxable carries its tax, as
    every fee bill does since the ❄️ B4.2 re-sign) and is `None` unless
    `status == "charged"`.

    ⚠ **THE ACCOUNT READ IS A REFUSAL LIKE ANY OTHER (`DEF-PAY-10746`).** A
    fee bill verifies its account through `one_time.single.billable_account`,
    which REFUSES an account outside the billable set (pending activation,
    closed — BR-CUS-055) and an unknown id. Until 2026-10-30 that refusal
    escaped this function, so a bounce on such an account raised out of
    `reverse_payment` and the REVERSAL never happened — against the PO's
    ruling that the reversal stands whatever becomes of the fee. It is now
    `nsf_fee_cannot_be_priced` with billing's own sentence in `detail`: no fee
    can be priced for that account, and the clerk is told so.
    """
    try:
        account = fee_bill._account_facts(account_id, on_date=on_date)
    except (BillingRuleError, NotFoundError) as refused:
        return {
            "status": CANNOT_BE_PRICED,
            "code": None,
            "name": None,
            "amount": None,
            "currency": None,
            "detail": str(refused) or "the account cannot be billed",
        }
    answer: dict[str, Any] = {
        "status": NO_PLAN,
        "code": None,
        "name": None,
        "amount": None,
        "currency": account.currency,
        "detail": None,
    }
    plan_id = _plan_id_of(account.row)
    if plan_id is None:
        return answer
    lookup = gather._resolve("rating", "plan_nsf_charge")
    if lookup is None:  # pragma: no cover - rating always publishes it
        answer.update(status=NOT_SET_ON_PLAN)
        return answer
    found = lookup(plan_id, on_date)
    code = found.get("code")
    if not code:
        answer.update(
            status=found.get("reason") or NOT_SET_ON_PLAN,
            detail=", ".join(found.get("codes") or ()) or None,
        )
        return answer
    answer.update(code=code, name=found.get("name"))
    try:
        priced = fee_bill.price_charge_fee(
            account_id=account_id,
            charge_code=code,
            on_date=on_date,
            description=found.get("name"),
        )
    except BillingRuleError as refused:
        answer.update(status=CANNOT_BE_PRICED, detail=str(refused))
        return answer
    # Hard rule 2 — money is stated at four places; display rounds to two.
    answer.update(status=CHARGED, amount=Decimal(priced.priced.total).quantize(AMOUNT_QUANTUM))
    return answer


def raise_nsf_fee(
    actor: Any,
    *,
    account_id: Any,
    on_date: date,
    payment_id: Any,
    issued_at: datetime | None = None,
) -> dict[str, Any]:
    """Charge the NSF penalty — the quote above, raised and ISSUED as a fee bill.

    `payment_id` is the BOUNCED payment (the original, never the reversing
    row) and is REQUIRED: it keys the fee bill, so one bounced payment carries
    at most one NSF fee however often it is asked (`DEF-PAY-10740`).

    Returns the quote plus `invoice_id` / `invoice_no` when a bill was raised.
    **It never raises on a fee that cannot be charged**: the caller is a bounce,
    and the PO's ruling is that the reversal stands whether or not a fee can be
    added (*"the reversal still goes through and the screen says no NSF fee is
    set on that plan"*). So every refusal comes back as a named `status`.

    ⚠ **THE WRITE RUNS INSIDE A SAVEPOINT, AND THAT IS THE ONLY WAY IT CAN BE
    SKIPPED (CLAUDE.md law 14).** The caller's transaction holds the reversing
    rows; a failed INSERT here (the one-time run's unique key, a refused issue)
    would otherwise ABORT that transaction on PostgreSQL and lose the reversal
    at COMMIT, while SQLite — the default suite — would carry on green. Proved
    on PostgreSQL in the lane's report.
    """
    if payment_id is None or not str(payment_id).strip():
        raise BillingRuleError(
            "an NSF fee is charged per BOUNCED PAYMENT (PO 2026-10-30, DEF-PAY-10740), so "
            "it needs the payment that bounced; without it two bounces on one day would "
            "share one key."
        )
    answer: dict[str, Any] = {
        "status": CANNOT_BE_PRICED,
        "code": None,
        "name": None,
        "amount": None,
        "currency": None,
        "detail": None,
        "invoice_id": None,
        "invoice_no": None,
    }
    # ⚠ THE QUOTE IS INSIDE THE SAVEPOINT TOO (`DEF-PAY-10746`): every read and
    # write on the fee path either answers or is rolled back to this point, so
    # nothing it does can abort the caller's transaction and lose the reversal.
    try:
        with transaction.atomic():
            answer.update(quote_nsf_fee(account_id, on_date=on_date))
            if answer["status"] != CHARGED:
                return answer
            invoice = fee_bill.raise_and_issue_charge_fee(
                actor,
                account_id=account_id,
                charge_code=answer["code"],
                on_date=on_date,
                due_days=0,
                description=answer.get("name"),
                issued_at=issued_at,
                run_key_source=f"nsf:{payment_id}",
            )
    except BillingRuleError as refused:
        # `runs.DuplicateRun` is a BillingRuleError: an NSF fee bill already
        # raised for THIS bounced payment (`one_time_run_key`, source
        # `nsf:<payment uuid>`) refuses a second (DEF-PAY-10740).
        answer.update(
            status=NOT_RAISED if answer["status"] == CHARGED else CANNOT_BE_PRICED,
            amount=None,
            detail=str(refused),
        )
        return answer
    answer.update(
        invoice_id=str(invoice.pk),
        invoice_no=invoice.invoice_no,
        amount=Decimal(invoice.total).quantize(AMOUNT_QUANTUM),
    )
    return answer
