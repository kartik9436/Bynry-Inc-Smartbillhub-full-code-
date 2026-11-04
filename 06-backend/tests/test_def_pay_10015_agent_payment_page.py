"""Four small things the 2026-10-07 end-to-end walk saw on a US Payments payment.

Walked on 2.560.3 (`08-qa/e2e-2026-10-07/README.md`, "Seen, not counted as
failures"), each filed before it was fixed:

  * `DEF-PAY-10015` — the payment's header read *"taken by Nobody named"*; a
    payment agent took it, and the agent is named.
  * `DEF-PAY-10016` — a returned payment still offered *"The money cleared.
    Reverse it instead."* (the Cancel refusal) and nothing near its status said
    it had been returned.
  * `DEF-PAY-10017` — the history's NOTE printed the raw reason word `nsf`.
  * `DEF-INT-10018` — the USPayments connector read *Not tested yet* after three
    APIs had answered calls successfully. A *they call us* connector cannot be
    tested from our side ("Cannot be tested until first use"), so its first
    successful call is the test.

PROVED RED FIRST (hard-won law 7) through pytest against the tip before the fix.
"""

from __future__ import annotations

import pytest

from apps.integrations import models as integration_models
from apps.payments import payment_detail
from tests.test_cr174_us_payments import (  # noqa: F401 — fixtures
    _call,
    _payment,
    _payments,
    _return,
    rosa,
    usp,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _returned(brazos):
    assert _call(brazos, "payments", body=_payment(amount=100.00, method="ACHCHECK")).status_code == 200
    assert _call(brazos, "returns", body=_return(amount=100.00, code="R01")).status_code == 200
    with tenant_ctx(brazos):
        original, reversing = _payments(brazos)
    return original, reversing


def test_def_pay_10015_an_agent_payment_names_the_agent_as_the_taker(brazos, rosa):
    assert _call(brazos, "payments", body=_payment(amount=150.00)).status_code == 200
    with tenant_ctx(brazos):
        (payment,) = _payments(brazos)
        source = payment_detail.payment_detail(payment)["source"]
    assert source["taken_by"] == "USPayments"


def test_def_pay_10015_a_counter_payment_still_names_nobody(brazos, rosa):
    # Law 7 habit 2 — a fix that named the agent on EVERY payment passes the
    # case above; a payment no agent took still has nobody to name.
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        account = rosa[0]
        payment = payment_models.Payment(tenant=brazos, account=account, origin="entry")
        assert payment_detail._source(payment)["taken_by"] is None


def test_def_pay_10016_a_returned_payment_says_so_and_offers_no_second_reversal(brazos, rosa):
    original, _reversing = _returned(brazos)
    with tenant_ctx(brazos):
        detail = payment_detail.payment_detail(original)
    assert detail["reversed_for"] == "nsf"
    assert detail["actions"]["cancel"]["allowed"] is False
    assert detail["actions"]["cancel"]["reason"] == "cancel_refused_already_reversed"


def test_def_pay_10016_a_cleared_payment_nobody_returned_is_unchanged(brazos, rosa):
    assert _call(brazos, "payments", body=_payment(amount=150.00)).status_code == 200
    with tenant_ctx(brazos):
        (payment,) = _payments(brazos)
        detail = payment_detail.payment_detail(payment)
    assert detail["reversed_for"] is None
    # CR-186-BRC10: an agent payment is POSTED until its batch is reconciled,
    # and a posted payment may be cancelled (PO 2026-10-21).
    assert detail["actions"]["cancel"]["reason"] is None


def test_def_pay_10017_a_reason_code_travels_as_a_catalogue_key():
    from types import SimpleNamespace

    # The trail row a return writes: `reason` is a closed code, not words.
    assert payment_detail._note_key_of(SimpleNamespace(after={"reason": "nsf"})) == (
        "payments.reverse.reason.nsf"
    )
    assert payment_detail._note_key_of(SimpleNamespace(after={"reason": "data_entry_error"})) == (
        "payments.reverse.reason.data_entry_error"
    )
    # Words a person typed are still theirs, and get no key.
    assert payment_detail._note_key_of(SimpleNamespace(after={"note": "nsf"})) is None
    assert payment_detail._note_key_of(SimpleNamespace(after={"reason": "called the bank"})) is None


def test_def_int_10018_the_first_successful_call_is_the_test(brazos, rosa, usp):
    with tenant_ctx(brazos):
        integration_models.IntegrationConnection.objects.filter(pk=usp.pk).update(
            status=integration_models.STATUS_UNTESTED
        )
    assert _call(brazos, "payments", body=_payment(amount=150.00)).status_code == 200
    with tenant_ctx(brazos):
        usp.refresh_from_db()
    assert usp.status == integration_models.STATUS_WORKING


def test_def_int_10018_a_refused_call_proves_nothing(brazos, rosa, usp):
    with tenant_ctx(brazos):
        integration_models.IntegrationConnection.objects.filter(pk=usp.pk).update(
            status=integration_models.STATUS_UNTESTED
        )
    # A zero amount is refused (400): the partner reached us, but nothing worked.
    assert _call(brazos, "payments", body=_payment(amount=0)).status_code == 400
    with tenant_ctx(brazos):
        usp.refresh_from_db()
    assert usp.status == integration_models.STATUS_UNTESTED
