# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6376 — a service request's *Record what was handed over* is
#           not the Record-a-payment form: no posting date, no memo, a
#           hand-typed three-tender list, and an endpoint that took neither a
#           date nor a memo. PO, on SR-26-0016: *"this screens takes the payment
#           it should be similar to record payment form so pasting date, type
#           of payment , memo and it will take only application fee"*.
#           DEF-CUS-6374 — the same door took cash with no open till.
# Rules:    CLAUDE.md hard rules 2 (money a string, never a float) · 4 (the
#           receipt's evidence is frozen) · 5 (only the ledger writes journal
#           lines) · 7 (every money act writes audit_log) · BR-TEN-081 (a typed
#           date is the TENANT's day, never UTC's) · BR-CUS-090 (the counter
#           accepts what is handed over) · BR-PAY-1186 / PO ruling 2026-09-23
#           §3.4 (*"(a) Refuse it. \"Start your counter first.\""*) and
#           OQ-PAY-12601 (anyone keying money opens a till) · decision log
#           2026-09-19 OPTION A2 (the ledger posts at collection; the payment
#           row is written when the account exists)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The request fee is taken the way Record a payment takes money.

WHAT THIS FILE PINS, IN ONE PARAGRAPH
-------------------------------------
Dana takes **$70.00** for an application on 21 September and types it in on the
22nd. The endpoint now carries the day she names — **the posting date** — and it
is the day the ledger books (`entry_date`), the day the receipt says it counts
for, and the day the payment row is dated when the account finally exists (A2).
Her memo and the check's reference travel the same way. Before this, the entry
was dated `taken_at.date()` of a UTC clock, so money taken after 7 pm in Chicago
was booked to TOMORROW — asserted here across the Chicago midnight.

⚠ **AND CASH WITH NO OPEN TILL IS REFUSED AT THIS DOOR TOO.** The rule has one
implementation (`counters.assert_till_open_for_tender`); this is a second call
site, reached through the customers → payments seam, and the request's own
spelling `cheque` is the tender `check`, which needs a till exactly as cash does.

WHAT WOULD MAKE THESE PASS WRONGLY (hard-won law 7, habit 2)
-----------------------------------------------------------
* *The date reaches the receipt* passes on a column nobody reads — so the
  ledger's `entry_date` is asserted, which is what a period close reads.
* *Cash with no till is refused* passes on an endpoint that refuses EVERYTHING —
  so card with no till, and cash WITH a till, are asserted to succeed.
* *Nothing is written on a refusal* is asserted on BOTH halves: no receipt row
  and no `fee_collected` on the request.

⚠ **SQLITE CANNOT SEE THE FREEZE.** `payments/0042` adds the three new columns
to `counter_receipts`' frozen list, and a trigger does not exist on SQLite; that
half is proved against a real PostgreSQL (hard-won law 14), not here.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone as django_timezone

from apps.customers import service_request_api as api
from apps.customers import service_request_service as sr
from apps.ledger import models as ledger_models
from apps.payments import counter_receipt_models as cr_models
from apps.payments import counter_receipts
from apps.payments import counters
from apps.payments import models as payments_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content_models as content_models

from tests.fee_quote_helpers import quote_fee  # DEF-CUS-6416: the catalogue prices the line
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, marcus, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

SEVENTY = "70.00"
SLIP = "RCP-26-0016"
CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "applicant_email": "david@example.test",
    "address_as_given": "14 Willow Bend, Springfield",
}


@pytest.fixture()
def centre(brazos):
    """A counter for the till to be at."""
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos,
            slug="req-fee-window",
            name="Main office",
            address="101 Bend Road, Brazos Bend, TX 77422",
        )


def _open_till(actor, centre):
    with tenant_ctx(centre.tenant):
        return counters.open_counter(
            actor,
            service_centre_id=centre.pk,
            opening_float=Decimal("0.0000"),
            opened_at=django_timezone.now(),
        )


def _request(actor, tenant, quoted="70.00"):
    with tenant_ctx(tenant):
        request = sr.create_request(actor, dict(CAPTURE))
        quote_fee(actor, request.id, charge_code="CC-REQFEE", unit_amount=Decimal(quoted))
        return request


def _post(actor, tenant, request, **body):
    return api_call(
        api.service_request_fee_collection,
        "post",
        f"/api/brazos/service-requests/{request.id}/fee-collection",
        user=actor.user,
        role=actor.role,
        tenant=tenant,
        data=body,
        request_id=str(request.id),
    )


def _receipt(tenant, request):
    with tenant_ctx(tenant):
        return cr_models.CounterReceipt.objects.filter(tenant=tenant, source_id=request.id).first()


def _collection_entry(tenant, receipt):
    with tenant_ctx(tenant):
        return ledger_models.JournalEntry.objects.get(pk=receipt.collection_entry_id)


def _chicago(tenant):
    with tenant_ctx(tenant):
        tenancy_models.TenantSettings.objects.filter(tenant_id=tenant.id).update(
            timezone="America/Chicago"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE POSTING DATE IS A MONEY FACT — it is the day the books say
# ═══════════════════════════════════════════════════════════════════════════
def test_the_posting_date_and_memo_reach_the_receipt_the_ledger_and_the_trail(
    brazos, dana, centre, audit_rows
):
    """$70.00 cash, posted for 21 September, with a memo and a reference.

    The ledger's `entry_date` is the day she typed — which is what a period
    close and every finance screen read — and hard rule 7's two audit rows (the
    request's and payments') both carry the date and the memo.
    """
    request = _request(dana, brazos)
    _open_till(dana, centre)
    response = _post(
        dana,
        brazos,
        request,
        amount=SEVENTY,
        method="cash",
        receipt_no=SLIP,
        posted_at="2026-09-21",
        memo="Paid by her daughter",
        confirmation="SLIP-7",
    )
    assert response.status_code == 200, response.data
    assert response.data["collected"]["display"] == "70.00"

    receipt = _receipt(brazos, request)
    assert receipt is not None
    assert receipt.amount == Decimal("70.0000")
    assert receipt.posted_on == date(2026, 9, 21)
    assert receipt.memo == "Paid by her daughter"
    assert receipt.confirmation == "SLIP-7"
    assert _collection_entry(brazos, receipt).entry_date == date(2026, 9, 21)

    served = counter_receipts.receipt_dict(receipt)
    assert served["posted_on"] == "2026-09-21"
    assert served["memo"] == "Paid by her daughter"
    assert served["confirmation"] == "SLIP-7"

    by_action = {row.get("action"): row.get("after") or {} for row in audit_rows}
    for action in ("service_request.fee_collected", "counter_receipt.collected"):
        assert action in by_action, f"no {action} among {sorted(by_action)}"
        assert by_action[action].get("posted_on") == "2026-09-21", action
        assert by_action[action].get("memo") == "Paid by her daughter", action


def test_a_posting_date_left_out_is_the_TENANTS_today_not_UTCs(brazos, dana, centre, monkeypatch):
    """**BR-TEN-081 across the Chicago midnight.**

    At 00:30 UTC on 23 September it is still 19:30 on the 22nd in Chicago. The
    entry used to be dated `taken_at.date()` of a UTC `now()` — the 23rd, a day
    the utility has not reached. Left out, the posting date is the TENANT's
    today, which is what the form proposes too.
    """
    _chicago(brazos)
    straddle = datetime(2026, 9, 23, 0, 30, tzinfo=dt_timezone.utc)
    request = _request(dana, brazos)
    _open_till(dana, centre)
    monkeypatch.setattr(django_timezone, "now", lambda: straddle)
    response = _post(dana, brazos, request, amount=SEVENTY, method="cash", receipt_no=SLIP)
    assert response.status_code == 200, response.data
    receipt = _receipt(brazos, request)
    assert straddle.date() == date(2026, 9, 23)  # …what UTC says
    assert receipt.posted_on == date(2026, 9, 22)
    assert _collection_entry(brazos, receipt).entry_date == date(2026, 9, 22)


def test_a_posting_date_that_is_not_a_date_is_refused_by_name(brazos, dana, centre):
    request = _request(dana, brazos)
    _open_till(dana, centre)
    response = _post(
        dana, brazos, request, amount=SEVENTY, method="cash", receipt_no=SLIP, posted_at="21/09/26"
    )
    assert response.status_code == 422
    assert response.data["message_key"] == "customers.serviceRequest.dateFormat"
    assert _receipt(brazos, request) is None


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE TILL RULE AT THIS DOOR — DEF-CUS-6374
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("method", ["cash", "cheque", "check", "money_order"])
def test_money_through_hands_with_no_open_till_is_refused_and_nothing_is_written(
    brazos, marcus, method
):
    """*"(a) Refuse it. \\"Start your counter first.\\""* — and OQ-PAY-12601:
    anyone keying money opens a till. `cheque` is the request's own spelling of
    the tender `check`, so it is refused exactly as cash is."""
    request = _request(marcus, brazos)
    response = _post(marcus, brazos, request, amount=SEVENTY, method=method, receipt_no=SLIP)
    assert response.status_code == 422, response.data
    assert response.data["message_key"] == "payments.counter.till_required"
    assert response.data["br_ref"] == "BR-PAY-1186"
    assert _receipt(brazos, request) is None
    with tenant_ctx(brazos):
        assert sr.request_row(request.id).fee_collected is None


def test_the_same_money_with_a_till_open_is_taken(brazos, marcus, centre):
    """The green half. A rule that refuses everything is not a rule."""
    request = _request(marcus, brazos)
    _open_till(marcus, centre)
    response = _post(marcus, brazos, request, amount=SEVENTY, method="cash", receipt_no=SLIP)
    assert response.status_code == 200, response.data
    assert _receipt(brazos, request).amount == Decimal("70.0000")


def test_a_card_needs_no_till(brazos, marcus):
    """A card banks under the system till (§3.4 names it among the four)."""
    request = _request(marcus, brazos)
    response = _post(marcus, brazos, request, amount=SEVENTY, method="card", receipt_no=SLIP)
    assert response.status_code == 200, response.data


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE METHOD LIST IS THE TENANT'S, THE SAME ONE RECORD A PAYMENT OFFERS
# ═══════════════════════════════════════════════════════════════════════════
def test_a_tenant_method_code_is_accepted_and_names_its_tender(brazos, marcus, centre):
    """`money_order` is one of the tenant's served methods. It used to be
    refused here as *not a way of paying*, because this door checked a
    hand-typed `cash · card · cheque`."""
    request = _request(marcus, brazos)
    _open_till(marcus, centre)
    response = _post(marcus, brazos, request, amount=SEVENTY, method="money_order", receipt_no=SLIP)
    assert response.status_code == 200, response.data
    receipt = _receipt(brazos, request)
    with tenant_ctx(brazos):
        assert receipt.method is not None and receipt.method.code == "money_order"


def test_a_code_that_is_no_tender_is_still_refused(brazos, marcus):
    request = _request(marcus, brazos)
    response = _post(marcus, brazos, request, amount=SEVENTY, method="bitcoin", receipt_no=SLIP)
    assert response.status_code == 422
    assert response.data["message_key"] == "customers.serviceRequest.feeMethodUnknown"
    assert _receipt(brazos, request) is None


# ═══════════════════════════════════════════════════════════════════════════
# 4 · A2 — THE PAYMENT ROW, WHEN THE ACCOUNT EXISTS, CARRIES THE SAME FACTS
# ═══════════════════════════════════════════════════════════════════════════
def test_the_payment_written_at_attach_is_dated_the_posting_day_in_the_tenants_zone(brazos, dana):
    """A2's second half. `attach_to_account` has no production caller yet
    (`DEF-PAY-5394`), so this pins what it will write when it does: the posting
    date as MIDNIGHT IN THE TENANT'S ZONE (BR-TEN-081), the clerk's reference,
    and the memo beside the slip number."""
    _chicago(brazos)
    with tenant_ctx(brazos):
        request = sr.create_request(dana, dict(CAPTURE))
        receipt = counter_receipts.record_counter_receipt(
            source_type=cr_models.SOURCE_SERVICE_REQUEST,
            source_id=request.id,
            source_ref=request.request_no,
            receipt_no=SLIP,
            amount=Decimal("70.00"),
            currency="USD",
            method_code="check",
            taken_at=datetime(2026, 9, 22, 15, 0, tzinfo=dt_timezone.utc),
            taken_by_id=dana.id,
            posted_on=date(2026, 9, 21),
            confirmation="10241",
            memo="Paid by her daughter",
            actor=dana,
        )
        cr_models.CounterReceipt.objects.filter(pk=receipt["id"]).update(
            state=cr_models.RECEIPT_APPLIED
        )
        account = an_account(dana, brazos, account_no="A-REQFEE-1")
        counter_receipts.attach_to_account(
            source_type=cr_models.SOURCE_SERVICE_REQUEST,
            source_id=request.id,
            account_id=account.pk,
            actor=dana,
            attached_at=django_timezone.now(),
        )
        payment = payments_models.Payment.objects.get(account_id=account.pk)
    assert payment.posted_at == datetime(2026, 9, 21, tzinfo=ZoneInfo("America/Chicago"))
    assert payment.confirmation == "10241"
    assert SLIP in payment.memo and "Paid by her daughter" in payment.memo


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-6376 · DEF-CUS-6374 · decision log 2026-09-19 (A2) · PO
#   2026-09-23 §3.4 and OQ-PAY-12601 · BR-TEN-081
# generated: 2026-09-23 by LANE REQ-FEE
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=pending(🔒 counter_receipts is HUMAN-REVIEW-PENDING)
# gates: pytest this file on SQLite, and the ledger + refusal cases on real
#   PostgreSQL through 10-scripts/proof-db.sh clone (hard-won law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
