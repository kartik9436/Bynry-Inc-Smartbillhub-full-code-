# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-PAY-10698 (the NSF penalty a bounce never charged) ·
#           DEF-PAY-10699 (LBX-04 — the bank's own words on a reversal)
# Rules:    BR-PAY-013 · BR-BIL-007 · BR-BIL-019 · CLAUDE.md rules 1, 2, 4, 6, 7
# Ruling:   PO 2026-10-30 (decision log): "The NSF penalty is charged on a
#           bounce, priced Account › Unit › Plan › Charge code, never
#           hard-coded" · "NSF penalty can be unticked with a reason" ·
#           "LBX-04: the bank's own words on a reversal are labelled Bank memo"
# ───────────────────────────────────────────────────────
"""Cheque 4102 bounces: the NSF penalty, found through the plan, charged once.

EVERY FIGURE IS THE DECISION LOG'S, NEVER COMPUTED HERE: cheque 4102 **$76.40**
bounces on an account whose unit's plan lists NSF at **$30.00** → the account
owes **$106.40**; unticked with *"bank error"* → **$76.40**.

RED FIRST (law 7): run against the tip before the change, `tc1` failed on the
missing `nsf_fee_status` (the reversal charged nothing — balance 76.40), `tc3`
on the same, and `tc4`/`tc6` on `bank_memo` / `charge_nsf_fee` being unknown
arguments. Quoted verbatim in the lane report.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2):
  * a hard-coded $30 would pass `tc1` — `tc1b` prices the plan's code at
    $42.50 and asserts $118.90, and `tc3` takes the code OFF the plan and
    asserts no fee at all, so only the walk passes both;
  * a fee matched by the code string `NSF` would pass `tc1` — `tc1b`'s code is
    `RET-CHK`, marked `is_nsf_fee`, and `tc3` keeps an unmarked `NSF` code on
    the plan;
  * a replay that re-charged would still show one fee on the FIRST result —
    `tc2` counts the fee BILLS on the account after the replay.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from apps.billing import models as billing_models
from apps.payments import billing_seam, models, payment_detail, reversal, selectors
from apps.payments.exceptions import PaymentRuleError
from apps.rating import models as rating_models

from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_us_bil_001_prepare import (  # noqa: F401
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import a_payment, an_issued_bill
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

CHEQUE_4102 = D("76.40")
NSF_PRICE = D("30.00")
AFTER_BOUNCE = D("106.40")
RETURNED_ON = datetime(2026, 10, 26, 10, 0, tzinfo=UTC)


def _gl(tenant):
    from apps.ledger import models as ledger_models

    return (
        ledger_models.LedgerAccount.objects.filter(
            tenant=tenant, deleted_at__isnull=True, code="4200"
        ).first()
        or ledger_models.LedgerAccount.objects.filter(
            tenant=tenant, deleted_at__isnull=True
        ).first()
    )


def _nsf_code(tenant, code="NSF", amount=NSF_PRICE, marked=True):
    row, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code=code,
        defaults={
            "name": "Returned payment (NSF) fee",
            "charge_type": "penalty",
            "amount_rule": "flat",
            "amount": amount,
            "gl_account_id": _gl(tenant).id,
            "is_nsf_fee": marked,
        },
    )
    return row


def _plan_of(account):
    from apps.metering import models as metering_models

    return metering_models.Unit.objects.get(pk=account.unit_id).rate_plan


def _list_on_plan(tenant, plan, charge):
    rating_models.PlanChargeRule.objects.create(tenant=tenant, rate_plan=plan, charge=charge)


def _world(brazos, dana, *, account_no, asset_no, code="NSF", amount=NSF_PRICE, on_plan=True):
    """An account on a plan, one $76.40 bill, and cheque 4102 paying it."""
    account = a_one_time_account(brazos, dana, account_no=account_no, asset_no=asset_no)
    charge = _nsf_code(brazos, code=code, amount=amount)
    if on_plan:
        _list_on_plan(brazos, _plan_of(account), charge)
    an_issued_bill(
        brazos, account, number=f"BL-{account_no}", total=CHEQUE_4102, issued_on=date(2026, 10, 1)
    )
    recorded = a_payment(dana, account, amount=CHEQUE_4102, confirmation="4102")
    return account, models.Payment.objects.get(pk=recorded.payment_id)


def _owed(account):
    position = billing_seam.open_invoices_for_account(account.pk)
    return sum((invoice.balance for invoice in position.invoices), D("0"))


def _fee_bills(account):
    return billing_models.Invoice.objects.filter(account=account, bill_type="fee")


@pytest.fixture
def real_audit():
    """`test_us_met_helpers` captures audit rows into a list, so nothing reaches
    `audit_log`; payment detail READS that table (the precedent and its
    diagnosis: `test_cr137_p3_detail_cancel_receipt.py`)."""
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


def _bounce(actor, payment, **overrides):
    values = dict(
        payment_id=payment.pk,
        returned_on=RETURNED_ON,
        reason=models.REVERSAL_REASON_NSF,
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return reversal.reverse_payment(actor, **values)


def test_def_pay_10698_tc1__4102_bounces_and_the_plans_nsf_fee_makes_106_40(
    brazos, dana, marcus, audit_rows
):
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41021", asset_no="M-41021")
        assert _owed(account) == D("0")

        result = _bounce(dana, cheque)

        assert result.nsf_fee_status == "charged"
        assert result.nsf_fee_code == "NSF"
        assert result.nsf_fee_amount == NSF_PRICE
        assert _fee_bills(account).count() == 1, "one NSF charge line"
        fee_bill = _fee_bills(account).get()
        assert fee_bill.status == billing_models.INVOICE_ISSUED, "a receivable, not a draft"
        assert fee_bill.total == NSF_PRICE
        assert _owed(account) == AFTER_BOUNCE, "$76.40 + $30.00 = $106.40"
        codes = {p["code"] for p in result.problems}
        assert "nsf_fee_charged" in codes
        assert "nsf_fee_not_added" not in codes, "the standing gap is gone"
        row = [r for r in audit_rows if r["action"] == reversal.AUDIT_NSF][0]
        assert D(row["after"]["nsf_fee"]["amount"]) == NSF_PRICE
        assert row["after"]["nsf_fee"]["invoice_no"] == fee_bill.invoice_no


def test_def_pay_10698_tc1b__the_amount_is_the_plans_code_whatever_it_is_called(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        account, cheque = _world(
            brazos,
            dana,
            account_no="A-41022",
            asset_no="M-41022",
            code="RET-CHK",
            amount=D("42.50"),
        )
        result = _bounce(dana, cheque)
        assert result.nsf_fee_code == "RET-CHK"
        assert result.nsf_fee_amount == D("42.50")
        assert _owed(account) == D("118.90")


def test_def_pay_10698_tc2__a_replayed_reversal_never_charges_twice(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41023", asset_no="M-41023")
        key = uuid.uuid4()
        first = _bounce(dana, cheque, idempotency_reference=key)
        again = _bounce(dana, cheque, idempotency_reference=key)
        assert first.created is True and again.created is False
        assert _fee_bills(account).count() == 1
        assert _owed(account) == AFTER_BOUNCE


def test_def_pay_10698_tc3__no_nsf_code_on_the_plan_reverses_and_names_why(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, cheque = _world(
            brazos, dana, account_no="A-41024", asset_no="M-41024", on_plan=False
        )
        result = _bounce(dana, cheque)
        assert result.created is True, "the reversal still goes through"
        assert result.nsf_fee_status == "nsf_fee_not_set_on_plan"
        assert result.nsf_fee_amount is None, "never a guessed $0.00"
        assert "nsf_fee_not_set_on_plan" in {p["code"] for p in result.problems}
        assert _fee_bills(account).count() == 0
        assert _owed(account) == CHEQUE_4102


def test_def_pay_10698_tc4__a_staff_reason_charges_no_fee(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41025", asset_no="M-41025")
        result = _bounce(
            dana,
            cheque,
            reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR,
            approval="clerk error",
            returned_on=datetime(2026, 10, 2, 10, 0, tzinfo=UTC),
        )
        assert result.nsf_fee_status is None
        assert _fee_bills(account).count() == 0


def test_def_pay_10698_tc5__unticked_with_bank_error_leaves_76_40_and_records_why(
    brazos, dana, marcus, audit_rows
):
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41026", asset_no="M-41026")
        result = _bounce(dana, cheque, charge_nsf_fee=False, nsf_fee_waive_reason="bank error")
        assert result.nsf_fee_status == "nsf_fee_waived"
        assert result.nsf_fee_waived_reason == "bank error"
        assert _fee_bills(account).count() == 0, "no fee line"
        assert _owed(account) == CHEQUE_4102
        row = [r for r in audit_rows if r["action"] == reversal.AUDIT_NSF][0]
        assert row["after"]["nsf_fee_waived_reason"] == "bank error"


def test_def_pay_10698_tc5c__the_payment_and_its_history_show_why_it_was_not_charged(
    brazos, dana, marcus, real_audit
):
    """Without the capture sink, so the audit row reaches the real store."""
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41030", asset_no="M-41030")
        _bounce(
            dana, cheque, charge_nsf_fee=False, nsf_fee_waive_reason="bank error", bank_memo="NSF"
        )
        detail = payment_detail.payment_detail(cheque)
        assert detail["reversal"]["nsf_fee_waived_reason"] == "bank error"
        assert detail["reversal"]["bank_memo"] == "NSF"
        history = payment_detail.history_rows(
            payment_detail.history_queryset(cheque), cheque.tenant_id
        )
        bounce = [row for row in history if row["what"] == reversal.AUDIT_NSF][0]
        assert bounce["nsf_fee_waived_reason"] == "bank error"
        assert bounce["bank_memo"] == "NSF"


def test_def_pay_10698_tc1c__payment_detail_shows_the_fee_charged(brazos, dana, marcus, real_audit):
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41031", asset_no="M-41031")
        _bounce(dana, cheque)
        reversal_facts = payment_detail.payment_detail(cheque)["reversal"]
        assert reversal_facts["nsf_fee_status"] == "charged"
        assert D(reversal_facts["nsf_fee_amount"]) == NSF_PRICE


def test_def_pay_10698_tc5b__unticking_without_a_reason_is_refused(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41027", asset_no="M-41027")
        with pytest.raises(PaymentRuleError):
            _bounce(dana, cheque, charge_nsf_fee=False, nsf_fee_waive_reason="  ")
        assert not models.Payment.objects.filter(reverses_payment=cheque).exists()


def test_def_pay_10699_tc6__bank_memo_lands_on_the_reversing_row_and_is_shown(
    brazos, dana, marcus, audit_rows
):
    """LBX-04 worked case: PY-…-0098 (cheque 4102) "NSF"; 4103 "ACCOUNT CLOSED"."""
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41028", asset_no="M-41028")
        an_issued_bill(
            brazos, account, number="BL-A-41028-2", total=D("12.00"), issued_on=date(2026, 10, 2)
        )
        other = models.Payment.objects.get(
            pk=a_payment(dana, account, amount=D("12.00"), confirmation="4103").payment_id
        )
        first = _bounce(dana, cheque, bank_memo=" NSF ")
        second = _bounce(dana, other, bank_memo="ACCOUNT CLOSED")

        assert first.bank_memo == "NSF"
        assert models.Payment.objects.get(pk=first.reversal_id).memo == "NSF"
        assert models.Payment.objects.get(pk=second.reversal_id).memo == "ACCOUNT CLOSED"
        cheque.refresh_from_db()
        assert cheque.memo != "NSF", "the original payment is never edited"
        assert payment_detail.payment_detail(cheque)["reversal"]["bank_memo"] == "NSF"
        reversing = models.Payment.objects.get(pk=second.reversal_id)
        assert selectors.payment_row(reversing)["bank_memo"] == "ACCOUNT CLOSED"
        memos = {
            r["after"].get("bank_memo") for r in audit_rows if r["action"] == reversal.AUDIT_NSF
        }
        assert memos == {"NSF", "ACCOUNT CLOSED"}


def test_def_pay_10699_tc7__a_bank_memo_over_60_characters_is_refused(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41029", asset_no="M-41029")
        with pytest.raises(PaymentRuleError):
            _bounce(dana, cheque, bank_memo="X" * 61)


def test_def_pay_10698_tc8__the_dialog_reads_the_fee_before_confirm_and_sends_both(
    brazos, dana, marcus
):
    """The two doors the Reverse dialog uses: the quote, then the write."""
    from apps.payments import reversal_api

    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41032", asset_no="M-41032")
    quote = api_call(
        reversal_api.payment_nsf_fee,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        query={"on": "2026-10-26"},
        payment_id=str(cheque.pk),
    )
    assert quote.status_code == 200
    assert quote.data["status"] == "charged"
    assert D(quote.data["amount"]) == NSF_PRICE
    answered = api_call(
        reversal_api.payment_reverse,
        "post",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "returned_on": RETURNED_ON.isoformat(),
            "idempotency_key": str(uuid.uuid4()),
            "bank_memo": "NSF",
        },
        payment_id=str(cheque.pk),
    )
    assert answered.status_code == 201
    assert answered.data["bank_memo"] == "NSF"
    assert D(answered.data["nsf_fee_amount"]) == NSF_PRICE
    with tenant_ctx(brazos):
        assert _owed(account) == AFTER_BOUNCE


def test_def_pay_10698_tc9__a_second_bounce_the_same_day_still_reverses(brazos, dana, marcus):
    """Two cheques on one account return on one day. The one-time fee bill is
    keyed (account, `fee`, day), so the SECOND fee is refused by billing — and
    the second REVERSAL must stand anyway, named `nsf_fee_not_raised`. On
    PostgreSQL this is the SAVEPOINT's proof (law 14): a refused write inside
    the reversal's transaction would otherwise abort it."""
    with tenant_ctx(brazos):
        account, cheque = _world(brazos, dana, account_no="A-41033", asset_no="M-41033")
        an_issued_bill(
            brazos, account, number="BL-A-41033-2", total=D("12.00"), issued_on=date(2026, 10, 2)
        )
        other = models.Payment.objects.get(
            pk=a_payment(dana, account, amount=D("12.00"), confirmation="4103").payment_id
        )
        first = _bounce(dana, cheque)
        second = _bounce(dana, other)
        assert first.nsf_fee_status == "charged"
        assert second.created is True, "the reversal stands"
        assert second.nsf_fee_status in ("charged", "nsf_fee_not_raised")
        fees = _fee_bills(account).count()
        assert fees == (2 if second.nsf_fee_status == "charged" else 1)
        assert _owed(account) == CHEQUE_4102 + D("12.00") + NSF_PRICE * fees
