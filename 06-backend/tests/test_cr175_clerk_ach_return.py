# ── Trace ──────────────────────────────────────────────
# Change:   CR-175-BRC10 — a billing clerk may mark an ACH payment returned, on
#           any day, with a reason and the bank's return code (PO 2026-10-07,
#           option (a)); the returned-payments runbook picks up a clerk's
#           return and a US Payments return alike.
# Rules:    BR-PAY-1070 (as amended 2026-10-07 for this one case) · BR-PAY-013 ·
#           BR-PAY-011 · BR-PAY-028 · OQ-PAY-12603 (c) unchanged · CR-174-BRC10 ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 6, 7 · law 14
# Tests:    this file.
# Impacts:  apps/payments/reversal.py (mark_ach_returned) ·
#           apps/payments/reversal_api.py (POST /payments/{id}/mark-returned) ·
#           apps/payments/payment_detail.py (actions.mark_returned) ·
#           apps/payments/runbook_reads.py (returned_items_landed) ·
#           apps/runbooks/definitions/returned_payments.py
# ───────────────────────────────────────────────────────
"""Dana marks Rosa's $100 ACH returned — and the fee and notice follow either way.

The PO's own case: Rosa's bill is **$277.89**. On 7 Oct she pays **$100.00**
by ACH, so she owes **$177.89**. On 10 Oct Dana, a BILLING CLERK, sees on the
bank statement that it came back **R01**. She marks it returned; the $100 is
owed again (**$277.89**) and the returned-payments runbook then drafts the fee
and handles the notice exactly as it does for a return US Payments sent us.

⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY** (hard-won law 7, habit 2):

* **A clerk test that never tried another day.** OQ-PAY-12603 (c) already lets
  a clerk reverse a SAME-DAY payment in principle, so every ACH case here is
  dated days after the payment.
* **A refusal asserted only by "it raised".** The card and cash cases assert
  the clerk is refused on the TENDER, and the reverse door still refuses the
  clerk outright — a widened `reverse_payment` would pass a bare `raises`.
* **A runbook test that monkeypatches the read.** The whole question is what
  the REAL read finds, so the runbook case runs the real seam on PostgreSQL.
"""

from __future__ import annotations

import datetime as dt
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from apps.payments import models as payment_models
from apps.payments import payment_detail, reversal, reversal_api, services
from apps.payments.exceptions import PaymentRuleError
from core import errors
from tests.test_cr174_us_payments import (  # noqa: F401 — fixtures
    _bill,
    _call,
    _method,
    _payment,
    _return,
    rosa,
    usp,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

requires_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="CLAUDE.md law 14 — the runbook's read and the reversal are proved on PostgreSQL.",
)

PAID_ON = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
RETURNED_ON = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def _open(invoice):
    from apps.payments import billing_seam

    return invoice.total - billing_seam.allocated_so_far(invoice.pk)


@pytest.fixture()
def rosa_owes(brazos, dana):
    """Rosa's account and her one $277.89 bill — the PO's figure."""
    with tenant_ctx(brazos):
        for code, name in (("ach", "ACH"), ("card", "Card"), ("cash", "Cash"), ("check", "Check")):
            _method(brazos, code, name)
        account = an_account(dana, brazos, account_no="00077889")
        bill = _bill(
            brazos,
            account,
            number="BL-2610-0001",
            total="277.8900",
            issued_on=date(2026, 10, 1),
            due_on=date(2026, 10, 25),
        )
    return account, bill


def _paid(tenant, actor, account, *, method="ach", amount="100.00", on=PAID_ON):
    with tenant_ctx(tenant):
        recorded = services.record_payment(
            actor,
            account_id=account.pk,
            amount=Decimal(amount),
            posted_at=on,
            cleared_at=on,
            method_code=method,
            idempotency_reference=str(uuid.uuid4()),
        )
    return payment_models.Payment.objects.get(pk=recorded.payment_id)


def _mark(actor, tenant, payment, **overrides):
    values = {
        "payment_id": payment.pk,
        "returned_on": RETURNED_ON,
        "reason": payment_models.REVERSAL_REASON_NSF,
        "return_code": "R01",
        "idempotency_reference": str(uuid.uuid4()),
    }
    values.update(overrides)
    with tenant_ctx(tenant):
        return reversal.mark_ach_returned(actor, **values)


# ══════════════════════════════════════════════════════════════════════════
# The ruling: a clerk, an ACH payment, another day
# ══════════════════════════════════════════════════════════════════════════


def test_a_clerk_marks_an_ach_payment_from_another_day_returned(brazos, marcus, rosa_owes, audit_rows):
    """$277.89 → $177.89 on 7 Oct → $277.89 again on 10 Oct, by a BILLING CLERK."""
    account, bill = rosa_owes
    payment = _paid(brazos, marcus, account)
    with tenant_ctx(brazos):
        assert _open(bill) == Decimal("177.8900")
    result = _mark(marcus, brazos, payment)
    assert result.created is True
    with tenant_ctx(brazos):
        reversing = payment_models.Payment.objects.get(pk=result.reversal_id)
        assert reversing.reverses_payment_id == payment.pk, "the original is kept"
        assert reversing.amount == Decimal("-100.0000")
        assert reversing.return_code == "R01", "the column US Payments writes"
        assert reversing.reversal_reason == payment_models.REVERSAL_REASON_NSF
        assert _open(bill) == Decimal("277.8900"), "owed again"
        payment.refresh_from_db()
        # CR-186-BRC10 — recorded `posted`; a return never edits it (hard rule 4).
        assert payment.status == payment_models.PAYMENT_POSTED, "never edited (hard rule 4)"
    nsf = [row for row in audit_rows if row["action"] == reversal.AUDIT_NSF]
    assert len(nsf) == 1 and nsf[0]["after"]["return_code"] == "R01", "hard rule 7"


def test_the_code_is_upper_cased_and_kept(brazos, marcus, rosa_owes):
    account, _bill_ = rosa_owes
    result = _mark(marcus, brazos, _paid(brazos, marcus, account), return_code=" r10 ",
                   reason=payment_models.REVERSAL_REASON_NSF)
    with tenant_ctx(brazos):
        assert payment_models.Payment.objects.get(pk=result.reversal_id).return_code == "R10"


@pytest.mark.parametrize("tender", ["card", "cash", "check"])
def test_a_clerk_is_refused_on_any_other_tender_from_another_day(brazos, marcus, rosa_owes, tender):
    account, bill = rosa_owes
    payment = _paid(brazos, marcus, account, method=tender)
    with pytest.raises(PaymentRuleError) as caught:
        _mark(marcus, brazos, payment)
    assert "ACH" in str(caught.value)
    with tenant_ctx(brazos):
        assert _open(bill) == Decimal("177.8900"), "nothing reversed"
        assert not payment_models.Payment.objects.filter(reverses_payment=payment).exists()


def test_the_general_reverse_is_still_refused_to_a_clerk(brazos, marcus, rosa_owes):
    """`BR-PAY-1070` stands for everything but this one case."""
    account, _bill_ = rosa_owes
    payment = _paid(brazos, marcus, account)
    with tenant_ctx(brazos), pytest.raises(errors.AuthError):
        reversal.reverse_payment(marcus, payment_id=payment.pk, returned_on=RETURNED_ON,
                                 return_code="R01")


@pytest.mark.parametrize("code", [None, "", "   "])
def test_the_bank_code_is_required(brazos, marcus, rosa_owes, code):
    account, _bill_ = rosa_owes
    with pytest.raises(PaymentRuleError) as caught:
        _mark(marcus, brazos, _paid(brazos, marcus, account), return_code=code)
    assert "return code" in str(caught.value)


@pytest.mark.parametrize("code", ["X01", "R1", "R001", "01", "R-1"])
def test_the_bank_code_must_be_a_nacha_code(brazos, marcus, rosa_owes, code):
    account, _bill_ = rosa_owes
    with pytest.raises(PaymentRuleError) as caught:
        _mark(marcus, brazos, _paid(brazos, marcus, account), return_code=code)
    assert "is not a bank return code" in str(caught.value)


@pytest.mark.parametrize("reason", ["data_entry_error", "customer_dispute", "", "made_up"])
def test_the_reason_is_one_a_bank_return_can_carry(brazos, marcus, rosa_owes, reason):
    account, _bill_ = rosa_owes
    with pytest.raises(PaymentRuleError):
        _mark(marcus, brazos, _paid(brazos, marcus, account), reason=reason)


def test_a_chargeback_on_a_paid_bill_still_needs_an_approval_as_for_us_payments(
    brazos, marcus, rosa_owes
):
    """Recorded, not decided here: `BR-PAY-011` treats a chargeback as a staff
    reason, so on a payment that paid a bill it needs an approval — for a clerk
    exactly as for US Payments' R02 (DEF-PAY-10012). The day that is ruled
    otherwise, this test goes red and names the change."""
    account, bill = rosa_owes
    with pytest.raises(PaymentRuleError) as caught:
        _mark(marcus, brazos, _paid(brazos, marcus, account),
              reason=payment_models.REVERSAL_REASON_BANK_CHARGEBACK, return_code="R02")
    assert "needs an approval" in str(caught.value)
    with tenant_ctx(brazos):
        assert _open(bill) == Decimal("177.8900")


def test_a_payment_already_returned_cannot_be_returned_again(brazos, marcus, rosa_owes):
    account, bill = rosa_owes
    payment = _paid(brazos, marcus, account)
    first_key = str(uuid.uuid4())
    _mark(marcus, brazos, payment, idempotency_reference=first_key)
    with pytest.raises(PaymentRuleError) as caught:
        _mark(marcus, brazos, payment)
    assert "already" in str(caught.value)
    # The SAME submit again is a replay, not a second return (hard rule 6).
    replay = _mark(marcus, brazos, payment, idempotency_reference=first_key)
    assert replay.created is False
    with tenant_ctx(brazos):
        assert payment_models.Payment.objects.filter(reverses_payment=payment).count() == 1
        assert _open(bill) == Decimal("277.8900"), "owed once, not twice"


def test_a_system_admin_keeps_every_reversal_it_had(brazos, dana, rosa_owes):
    """The Admin's general Reverse — a card payment, no code — is unchanged,
    and the Admin may use the new door too."""
    account, bill = rosa_owes
    card = _paid(brazos, dana, account, method="card", amount="50.00")
    with tenant_ctx(brazos):
        done = reversal.reverse_payment(dana, payment_id=card.pk, returned_on=RETURNED_ON)
        assert done.created is True
        assert payment_models.Payment.objects.get(pk=done.reversal_id).return_code is None
    ach = _paid(brazos, dana, account, amount="25.00")
    assert _mark(dana, brazos, ach).created is True


def test_another_role_is_refused_by_the_service(brazos, rosa_owes, dana):
    account, _bill_ = rosa_owes
    payment = _paid(brazos, dana, account)
    executive = staff_actor(brazos, "executive", "exec@brazosbendutilities.test")
    with pytest.raises(errors.AuthError):
        _mark(executive, brazos, payment)


# ══════════════════════════════════════════════════════════════════════════
# The door and the detail read
# ══════════════════════════════════════════════════════════════════════════


def _door(actor, tenant, payment, *, role, data):
    return api_call(
        reversal_api.payment_mark_returned,
        "post",
        user=actor.user,
        role=role,
        tenant=tenant,
        data=data,
        payment_id=str(payment.pk),
    )


def _body(**overrides):
    values = {
        "returned_on": RETURNED_ON.isoformat(),
        "reason": "nsf",
        "return_code": "R01",
        "idempotency_key": str(uuid.uuid4()),
    }
    values.update(overrides)
    return values


def test_the_door_answers_a_clerk_with_the_reversal_and_its_code(brazos, marcus, rosa_owes):
    account, _bill_ = rosa_owes
    payment = _paid(brazos, marcus, account)
    response = _door(marcus, brazos, payment, role="billing_clerk", data=_body())
    assert response.status_code == 201, response.data
    assert Decimal(str(response.data["amount"])) == Decimal("-100.0000")
    # The old door is unchanged: a clerk is still refused there.
    old = api_call(
        reversal_api.payment_reverse, "post", user=marcus.user, role="billing_clerk",
        tenant=brazos, data=_body(), payment_id=str(payment.pk),
    )
    assert old.status_code == 403


def test_the_door_refuses_a_missing_code_by_field(brazos, marcus, rosa_owes):
    account, _bill_ = rosa_owes
    payment = _paid(brazos, marcus, account)
    response = _door(marcus, brazos, payment, role="billing_clerk", data=_body(return_code=""))
    assert response.status_code == 422, "VAL_REQUIRED, by field"
    response = _door(marcus, brazos, payment, role="billing_clerk", data=_body(reason=""))
    assert response.status_code == 422, "VAL_REQUIRED, by field"


def test_the_door_refuses_an_executive(brazos, dana, rosa_owes):
    account, _bill_ = rosa_owes
    payment = _paid(brazos, dana, account)
    executive = staff_actor(brazos, "executive", "exec2@brazosbendutilities.test")
    assert _door(executive, brazos, payment, role="executive", data=_body()).status_code == 403


def test_the_detail_offers_mark_returned_on_ach_only(brazos, dana, rosa_owes):
    account, _bill_ = rosa_owes
    ach = _paid(brazos, dana, account)
    card = _paid(brazos, dana, account, method="card", amount="10.00")
    with tenant_ctx(brazos):
        assert payment_detail.action_availability(ach)["mark_returned"] == {
            "offered": True, "allowed": True, "reason": None,
        }
        assert payment_detail.action_availability(card)["mark_returned"]["offered"] is False
    _mark(dana, brazos, ach)
    with tenant_ctx(brazos):
        ach.refresh_from_db()
        state = payment_detail.action_availability(ach)["mark_returned"]
        assert state["allowed"] is False and state["reason"] == "already_returned"


def test_the_door_is_mounted():
    from django.urls import resolve

    match = resolve("/api/brazos/payments/11111111-1111-1111-1111-111111111111/mark-returned")
    assert match.func is reversal_api.payment_mark_returned


# ══════════════════════════════════════════════════════════════════════════
# The returned-payments runbook picks up BOTH returns, the same way (PG16)
# ══════════════════════════════════════════════════════════════════════════


def _runbook_run(tenant):
    from apps.runbooks import models as rb_models
    from apps.runbooks.definitions import returned_payments as rp

    runbook = rb_models.Runbook.objects.create(
        tenant=tenant,
        key=rp.RUNBOOK_KEY,
        name=rp.RUNBOOK.name,
        kind=rp.RUNBOOK.kind,
        category=rp.RUNBOOK.category,
        subject_type=rp.RUNBOOK.subject_type,
        unit_of_work=rp.RUNBOOK.unit_of_work,
    )
    return rb_models.RunbookRun.objects.create(
        tenant=tenant,
        runbook=runbook,
        version=1,
        mode=rb_models.MODE_DRY,
        status=rb_models.RUN_STATUS_RUNNING,
        started_at=timezone.now(),
    )


@requires_postgres
def test_the_runbook_picks_up_a_clerk_return_and_a_us_payments_return_alike(
    brazos, dana, marcus, rosa, rosa_owes
):
    from apps.runbooks.definitions import returned_payments as rp
    from apps.runbooks.engine import executor

    # US Payments: Rosa (00012345) pays $147.85 by ACH and it comes back R01.
    assert _call(brazos, "payments", body=_payment(amount=147.85, method="ACHCHECK")).status_code == 200
    assert _call(brazos, "returns", body=_return(amount=147.85, code="R01")).status_code == 200
    # A clerk: the other Rosa pays $100.00 by ACH on 7 Oct; Dana marks it R01 on 10 Oct.
    account, _bill_ = rosa_owes
    clerk_return = _mark(marcus, brazos, _paid(brazos, marcus, account))

    with tenant_ctx(brazos):
        run_row = _runbook_run(brazos)
        ctx = executor.build_context(
            rp.RUNBOOK,
            tenant_id=run_row.tenant_id,
            run_id=run_row.pk,
            params={
                "as_of": dt.date(2026, 10, 10).isoformat(),
                "window_days": 3,
                "returned_payment_charge_code": "NSF",
            },
        )
        result = executor.execute(rp.RUNBOOK, ctx=ctx)

    gathered = result.set_results[rp.STEP_GATHER]
    assert not gathered.get("stop"), gathered.get("stop")
    found = {str(one["item_id"]): one for one in gathered["items"]}
    assert clerk_return.reversal_id in found, "the clerk's return is picked up"
    assert len(found) == 2, "and the US Payments return beside it"
    assert {one["return_code"] for one in found.values()} == {"R01"}

    fee = {one.subject.subject_id: one for one in result.records if one.step_key == rp.STEP_FEE}
    assert set(fee) == set(found)
    assert {one.data["fee"] for one in fee.values()} == {"planned"}, "a fee for each, the same way"
    assert len({one.data["notice"] for one in fee.values()}) == 1, "the notice handled the same way"
    reverse = [one for one in result.records if one.step_key == rp.STEP_REVERSE]
    assert {one.outcome for one in reverse} == {rp.OUTCOME_ALREADY_REVERSED}
