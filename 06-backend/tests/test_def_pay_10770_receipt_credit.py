# ── Trace ──────────────────────────────────────────────
# Ruling:   PO 2026-10-30, decision log *"Final-walk questions W1–W4 answered"* —
#           W4 = A: a receipt for an account in credit prints **"Credit on
#           account $68.00"** instead of "Balance remaining $0.00"
# Defect:   DEF-PAY-10770
# Tests:    this file (backend half; the DOM half is
#           07-frontend/src/features/payments/printReceipt.dom.test.tsx)
# ───────────────────────────────────────────────────────
"""Hugo Hollis pays $68.00 cash that meets no bill: the receipt and the account
header give ONE figure, −68.00 (the account is $68.00 in credit).

RED FIRST (law 7), against the tip before the fix — see the decision log entry
for DEF-PAY-10770: the receipt read the receivable (1200) alone, which held
credit never touches, so it served 0.000000.

WHAT WOULD MAKE THIS PASS WRONGLY: a receipt that read the subledger credit
and subtracted it — so the owing case is asserted too ($165.00 bill, $100.00
paid → +65.00), and both figures are compared with the account header's own
(`customers.selectors.account_detail`).
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from apps.customers import selectors as customer_selectors
from apps.payments import detail_api

from tests.test_def_pay_10707_held_credit import _billed, _pay
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def _receipt(tenant, actor, payment_id):
    response = api_call(
        detail_api.payment_receipt_print,
        "get",
        f"/api/brazos/payments/{payment_id}/receipt/print",
        user=actor.user,
        role=actor.role,
        tenant=tenant,
        payment_id=str(payment_id),
    )
    assert response.status_code == 200, response.data
    return response.data


def test_hugo_pays_68_cash_meeting_no_bill_and_the_receipt_reads_credit(brazos, marcus):
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="AC-2026-00008")
        recorded = _pay(marcus, account, "68.00")
        header = customer_selectors.account_detail(account.pk)["balance"]

    body = _receipt(brazos, marcus, recorded.payment_id)
    assert D(body["balance"]) == D("-68.00")
    # One figure on both surfaces: the receipt is the account header's figure.
    assert D(body["balance"]) == D(header)


def test_an_account_still_owing_reads_a_positive_balance_remaining(brazos, marcus):
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="AC-2026-00031")
        _billed(brazos, account, "165.00", number="BL-2610-000931")
        recorded = _pay(marcus, account, "100.00")
        header = customer_selectors.account_detail(account.pk)["balance"]

    body = _receipt(brazos, marcus, recorded.payment_id)
    assert D(body["balance"]) == D("65.00")
    assert D(body["balance"]) == D(header)
