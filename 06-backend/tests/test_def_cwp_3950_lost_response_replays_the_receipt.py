# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-3950 — a lost response on a guest payment tells the
#           customer there is NOTHING TO PAY instead of handing back the
#           receipt they already earned. The worst available wrong answer on a
#           money path: it invites a second payment.
# Rules:    CLAUDE.md hard rule 6 (idempotency on inbound money) · BR-CWP-058
#           (the payability re-read) · BR-CWP-028 (a guest receipt is six keys)
#           · BR-PAY-003 (an approved debit that could not be recorded is NOT a
#           receipt) · B14 rule 31 (no database id is a visible value)
# Cases:    the replay · the ORDER (it beats both the payability guard and the
#           amount guard) · a delivery that produced no payment is not a
#           receipt · a different visit is not a replay · the pair is still
#           required
# ───────────────────────────────────────────────────────
"""**WHAT THE PERSON SEES ON THE RETRY** — which no test in this repo asked.

⚠ **EVERY EXISTING CHECK ASKS HOW MANY PAYMENTS EXIST, AND THEY ARE ALL
RIGHT.** Hard rule 6 is genuinely satisfied: sequential retries stopped at the
payability guard and concurrent ones were collapsed by `settle_charge`'s
composed key — `test_two_attempts_in_flight_at_once_settle_onto_one_payment`
asserts exactly that. One payment, every way in. **The RECORD was never wrong.
The RESPONSE was**, and the gap is on the customer's side of a lost response,
where this repo had no case at all.

The worked figure: a guest pays `$142.18` against `BL-2608-0141`, the payment
commits, the response is lost, and the browser resends the SAME
`attempt_token`. Before this fix that answered `409 portal.quickPay.notPayable`
— *"There is nothing to pay"* — about the payment they had just made.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.payments import models as payments_models
from apps.portal import guest_api
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)
from tests.test_us_ten_helpers import api_call

AUGUST = date(2026, 8, 30)
DUE = date(2026, 9, 14)
BILL = "BL-2608-0141"
POSTCODE = "78702"
OWING = "142.1800"
PAID_REFERENCE = "PAY-26-08841"
TOKEN = "5f8c0f1e-0000-4000-8000-0000000008841"
INSTRUMENT = {"token": "tok_sandbox_8812", "brand": "visa", "last_four": "8812"}
ADDRESS = "203.0.113.7"


def _pay(tenant, number, body):
    return api_call(
        guest_api.bill_pay,
        "post",
        f"/api/{tenant.subdomain}/portal/public/bills/{number}/pay",
        tenant=tenant,
        data=body,
        headers={"X-Forwarded-For": ADDRESS},
        number=number,
    )


def _body(**overrides):
    body = {
        "postcode": POSTCODE,
        "amount": OWING,
        "instrument": dict(INSTRUMENT),
        "receipt_email": None,
        "attempt_token": TOKEN,
    }
    body.update(overrides)
    return body


def _a_paid_bill_and_its_delivery(tenant, actor, *, payment_id_on_delivery=True, paid_no=PAID_REFERENCE):
    """The world as it is one millisecond after the response was lost.

    The payment EXISTS, the bill is settled, and the delivery row carries the
    attempt key — which is what `webhooks.settle_charge` stores as `event_id`.
    """
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        bill = an_issued_bill(
            tenant, account, number=BILL, total=OWING, issued_on=AUGUST, due_on=DUE
        )
        payment = payments_models.Payment.objects.create(
            tenant=tenant,
            account=account,
            payment_no=paid_no,
            amount=Decimal(OWING),
            currency="USD",
            status=payments_models.PAYMENT_CLEARED,
            posted_at=datetime(2026, 9, 2, 9, 47, tzinfo=UTC),
        )
        payments_models.Allocation.objects.create(
            tenant=tenant, payment=payment, invoice=bill, amount=Decimal(OWING)
        )
        payments_models.PaymentWebhookEvent.objects.create(
            tenant=tenant,
            provider="sandbox",
            # ⚠ EXACTLY WHAT THE EDGE MINTS — `_attempt_key`'s own composition.
            # Typing the string by hand here rather than calling the function
            # is deliberate: it freezes the shape, so a change to the key that
            # would break the replay in production breaks this case too.
            event_id=f"guestpay:{tenant.id}:{BILL}:{TOKEN}",
            event_type="charge.settled",
            received_at=datetime(2026, 9, 2, 9, 47, tzinfo=UTC),
            payment_id=payment.pk if payment_id_on_delivery else None,
        )
    return account, bill, payment


@pytest.mark.django_db
def test_def_cwp_3950_a_retry_after_a_lost_response_gets_THE_RECEIPT(pine_hill, sarah):
    """The defect itself, and the whole of it in one assertion pair."""
    _a_paid_bill_and_its_delivery(pine_hill, sarah)
    answer = _pay(pine_hill, BILL, _body())

    assert answer.status_code == 200, answer.data
    # ⚠ **200 AND NOT 201.** Nothing was created — a 201 would say a second
    # payment was taken, which is the one thing that did not happen.
    assert answer.data["reference"] == PAID_REFERENCE
    assert answer.data["amount"]["amount"] == OWING
    assert answer.data["against"] == BILL
    # ⚠ **THE MOMENT THE MONEY WAS TAKEN, NOT THE MOMENT OF THE RETRY.** A
    # replayed receipt stamped with today's clock is how a customer concludes
    # they have paid twice.
    assert answer.data["paid_at"].startswith("2026-09-02T09:47")


@pytest.mark.django_db
def test_def_cwp_3950_the_ORDER_is_the_fix_and_it_beats_BOTH_later_guards(pine_hill, sarah):
    """⚠ **TWO GUARDS WOULD HAVE LIED, WITH TWO DIFFERENT SENTENCES.**

    After a successful payment the bill is settled — so `BR-CWP-058`'s
    payability re-read refuses with *"There is nothing to pay"* — AND what is
    owed has moved, so the amount check one line further on refuses with *"the
    amount has changed"*. Both are true statements about the world and both are
    the wrong answer to *did my money arrive*. This retry sends the amount the
    person originally agreed to, which is now stale, so it would fail the
    second guard even if it somehow passed the first."""
    _a_paid_bill_and_its_delivery(pine_hill, sarah)
    answer = _pay(pine_hill, BILL, _body(amount=OWING))
    assert answer.status_code == 200, answer.data
    assert answer.data["reference"] == PAID_REFERENCE


@pytest.mark.django_db
def test_def_cwp_3950_a_delivery_that_recorded_NO_payment_is_not_a_receipt(pine_hill, sarah):
    """`BR-PAY-003` — the provider approved the debit and we could not record
    it. The delivery row STANDS so the money can be found, and it is not a
    receipt: replaying one would tell somebody they had paid when nothing was
    recorded, which is this defect's own lie pointing the other way."""
    _a_paid_bill_and_its_delivery(pine_hill, sarah, payment_id_on_delivery=False)
    answer = _pay(pine_hill, BILL, _body())
    assert answer.status_code != 200
    assert answer.data.get("reference") is None


@pytest.mark.django_db
def test_def_cwp_3950_a_payment_with_no_human_number_is_not_replayed(pine_hill, sarah):
    """B14 rule 31 — a receipt whose reference was a row id would be a database
    id on a screen. The edge falls through to its ordinary refusal instead of
    inventing one."""
    _a_paid_bill_and_its_delivery(pine_hill, sarah, paid_no="")
    answer = _pay(pine_hill, BILL, _body())
    assert answer.status_code != 200


@pytest.mark.django_db
def test_def_cwp_3950_a_DIFFERENT_visit_is_not_a_replay(pine_hill, sarah):
    """The key carries the browser's per-visit token, so somebody genuinely
    paying a second time on a new visit is NOT handed the first receipt."""
    _a_paid_bill_and_its_delivery(pine_hill, sarah)
    answer = _pay(pine_hill, BILL, _body(attempt_token="a-different-visit-0000-0000-000000000001"))
    assert answer.status_code != 200, "a new attempt must not replay an old receipt"


@pytest.mark.django_db
def test_def_cwp_3950_the_replay_still_costs_the_POSTCODE(pine_hill, sarah):
    """⚠ **GUARD 5½ SITS AFTER GUARDS 1–5 AND THAT PLACEMENT IS A SECURITY
    FACT.** Moving the lookup any earlier would turn `attempt_token` into a way
    of asking whether a payment exists, with no pair to prove and no counter
    burning. A wrong postcode gets step 1's own sentence, unchanged."""
    _a_paid_bill_and_its_delivery(pine_hill, sarah)
    answer = _pay(pine_hill, BILL, _body(postcode="78704"))
    assert answer.status_code != 200
    assert answer.data.get("reference") is None
