# ── Trace ──────────────────────────────────────────────
# Change:   CR-191-BRC10 (PO 2026-10-23) — a portal application whose fee is
#           above $0.00 is paid online by card on its last step and submitted
#           only when the payment succeeds; no "Pay later"; not refunded.
# Rules:    decision log 2026-10-23 "Portal application fee: paid online at
#           submission …" and "… how it is built" (judgments 1–9) · CLAUDE.md
#           hard rules 1, 2, 4, 5, 6, 7 · hard-won law 14
# Impacts:  apps/payments/gateway.py (charge_guest_fee) ·
#           apps/payments/counter_receipts.py (outcome `paid_online`) ·
#           apps/customers/service_request_service.py (_record_online_fee) ·
#           apps/portal/{services,guest_api,availability}.py · portal seams
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-REVIEW-PENDING — **the portal application fee is paid by card before
the application exists.**

PO, verbatim: *"if there is a application or service fee then consumer will
have to pay it online; they can't say pay later"*; *"That is application fee it
is not refunded generally many time utilities charger 0 application fees"*;
*"3A"*.

**Worked, as these cases assert it:** Pine Hill prices `APP-FEE` at `$10.00`
and maps it to `4600`. Daniel Okafor applies for water, sewer and trash and pays
by the sandbox card → ONE request, ONE counter receipt (card, `earned`), DR 1010
10.0000 / CR 2400 10.0000 then DR 2400 10.0000 / CR 4600 10.0000, no `payments`
row, and an acknowledgement reading *"You paid $10.00 by card."*.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
* **"Writes nothing on a decline" would pass if the request were written and
  then deleted** — so the DRAFT is read back and must still be unsent, and the
  request COUNT, the receipt count and the journal count are all read.
* **"Records once" would pass if the retry never reached the write** — so the
  first write is made to FAIL after an approved charge (the provider took the
  money) and the retry must then write exactly one of everything.
* **"Approval does not re-raise" would pass if approval never ran** — so the
  request is walked through the clerk's own doors and approved, and the ledger
  is counted before and after.
* **A $0 fee "showing no payment step" would pass if the server simply ignored
  the card** — so the $0 case also asserts no integration run was asked for.

Runs on SQLite and on PostgreSQL (law 14: the write after an approved charge is
one transaction, and a failure inside it must leave nothing behind).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import service_request_service as sr
from apps.integrations import models as integration_models
from apps.integrations.adapters import payments_sandbox
from apps.ledger import models as ledger_models
from apps.notifications import rendering, seed_templates, service_request_events
from apps.notifications import models as notification_models
from apps.payments import counter_receipt_models as cr_models
from apps.payments import models as payment_models
from apps.portal import availability, guest_api, models as portal_models
from apps.rating import models as rating_models
from apps.rating import services as rating_services
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

TOKEN = "c1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
ATTEMPT = "7a8c0f1e-0000-4000-8000-000000000191"
INSTRUMENT = {"token": "tok_sandbox_4242", "brand": "visa", "last_four": "4242"}
TEN = Decimal("10.0000")

COMPLETE = {
    "address_as_given": "31 Palm Ct",
    "service_codes": ["water", "sewer", "trash"],
    "applicant_kind": "person",
    "first_name": "Daniel",
    "last_name": "Okafor",
    "email": "d.okafor@example.test",
    "phone": "(512) 555-7730",
    "account_type_code": "residential",
    "date_of_birth": "1987-12-04",
}


# ═══════════════════════════════════════════════════════════════════════════
# Fixture — a live portal, a priced application fee mapped to revenue, a card
# provider, and a complete draft
# ═══════════════════════════════════════════════════════════════════════════
def _app_fee(tenant, actor, amount, *, mapped=True):
    with tenant_context(tenant.id):
        row = rating_services.create_charge(
            actor,
            {
                "code": "APP-FEE",
                "name": "Application fee",
                "charge_type": "one_time",
                "amount_rule": "flat",
                "amount": str(amount),
                "kind": "other",
                "is_application_fee": True,
            },
        )
        if mapped:
            account = ledger_models.LedgerAccount.objects.get(tenant=tenant, code="4600")
            rating_models.Charge.objects.filter(pk=row["id"]).update(gl_account_id=account.id)
        return row


def _provider(tenant, behaviour=payments_sandbox.APPROVE):
    with tenant_context(tenant.id):
        return integration_models.IntegrationConnection.objects.create(
            tenant=tenant,
            provider_key=payments_sandbox.PaymentsSandboxAdapter.key,
            label="Test payments",
            environment=integration_models.ENVIRONMENT_SANDBOX,
            status=integration_models.STATUS_WORKING,
            cadence=integration_models.CADENCE_MANUAL,
            config={"behaviour": behaviour},
        )


def _draft(tenant, token=TOKEN):
    api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data={**COMPLETE, "requested_start": (date.today() + timedelta(days=21)).isoformat()},
        token=token,
    )


@pytest.fixture()
def live(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        seed_templates.seed_notice_templates(sarah, on_date=date(2026, 10, 23))
    _draft(pine_hill)
    return pine_hill


def _send(tenant, token=TOKEN, **body):
    data = {"paperless": False, **body}
    return api_call(
        guest_api.submit_application,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/submit",
        tenant=tenant,
        data=data,
        token=token,
    )


def _pay(tenant, **over):
    body = {"instrument": dict(INSTRUMENT), "fee_amount": "10.00", "attempt_token": ATTEMPT}
    body.update(over)
    return _send(tenant, **body)


def _counts(tenant):
    with tenant_context(tenant.id):
        return {
            "requests": customers_models.ServiceRequest.objects.filter(tenant_id=tenant.id).count(),
            "receipts": cr_models.CounterReceipt.objects.filter(tenant_id=tenant.id).count(),
            "entries": ledger_models.JournalEntry.objects.filter(
                tenant=tenant, source_type="counter_receipt"
            ).count(),
            "payments": payment_models.Payment.objects.filter(tenant_id=tenant.id).count(),
            "charges_asked": integration_models.IntegrationRun.objects.filter(
                tenant_id=tenant.id
            ).count(),
        }


def _legs(entry):
    return {
        line.ledger_account.code: (line.side, line.amount)
        for line in ledger_models.JournalLine.objects.filter(journal_entry=entry).select_related(
            "ledger_account"
        )
    }


def _draft_row(tenant, token=TOKEN):
    with tenant_context(tenant.id):
        return portal_models.PortalApplicationDraft.objects.get(token=token)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · A PAID SUBMISSION — one request, one receipt, the revenue posting
# ═══════════════════════════════════════════════════════════════════════════
def test_a_paid_submission_writes_one_request_one_receipt_and_the_revenue_posting(
    live, sarah, audit_rows
):
    _app_fee(live, sarah, "10.00")
    _provider(live)
    before = _counts(live)
    answer = _pay(live)
    assert answer.status_code == 200, answer.data
    body = answer.data
    assert body["reference"].startswith("SR-")
    assert body["fee_paid"]["amount"] == "10.0000"
    assert body["fee_paid"]["display"] == "$10.00"
    after = _counts(live)
    assert after["requests"] == before["requests"] + 1
    assert after["receipts"] == before["receipts"] + 1
    assert after["entries"] == before["entries"] + 2  # collected + released
    # ⚠ NO payment row — an applicant has no account (2026-09-23 ruling).
    assert after["payments"] == before["payments"]

    with tenant_context(live.id):
        request = customers_models.ServiceRequest.objects.get(pk=body["request_id"])
        assert request.fee_collected == TEN
        assert request.fee_method == "card"
        assert request.fee_receipt_no == request.request_no
        assert sr.fee_total_to_collect(request.id)["outstanding"] == Decimal("0.0000")

        receipt = cr_models.CounterReceipt.objects.get(source_id=request.id)
        assert receipt.amount == TEN
        assert receipt.state == cr_models.RECEIPT_EARNED
        assert receipt.earned_amount == TEN
        assert receipt.card_last4 == "4242"
        assert receipt.confirmation.startswith("appfee:")
        # DEF-PAY-10554 — the server's key, kept on the draft: draft id, fee,
        # declines so far; never the browser's token, never the link token.
        draft = portal_models.PortalApplicationDraft.objects.get(token=TOKEN)
        assert receipt.confirmation == draft.fee_idempotency_key
        assert receipt.confirmation == f"appfee:{live.id}:{draft.pk}:10.0000:0"
        assert ATTEMPT not in receipt.confirmation and TOKEN not in receipt.confirmation

        entries = list(
            ledger_models.JournalEntry.objects.filter(
                tenant=live, source_type="counter_receipt", source_id=receipt.id
            ).order_by("posting_key")
        )
        assert [e.posting_key.rsplit("|", 1)[1] for e in entries] == ["collected", "released"]
        collected, released = (_legs(e) for e in entries)
        assert collected["2400"] == ("credit", TEN)
        assert sum(a for s, a in collected.values() if s == "debit") == TEN
        assert released == {"2400": ("debit", TEN), "4600": ("credit", TEN)}

    actions = {row["action"] for row in audit_rows}
    assert {
        "service_request.created_from_portal",
        "service_request.fee_quoted",
        "service_request.fee_paid_online",
        "counter_receipt.collected",
        "counter_receipt.released",
    } <= actions


# ═══════════════════════════════════════════════════════════════════════════
# 2 · A FAILED PAYMENT WRITES NOTHING
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "behaviour,status", [(payments_sandbox.DECLINE, 409), (payments_sandbox.TIMEOUT, 503)]
)
def test_a_declined_or_silent_card_writes_nothing(live, sarah, behaviour, status):
    _app_fee(live, sarah, "10.00")
    _provider(live, behaviour)
    before = _counts(live)
    answer = _pay(live)
    assert answer.status_code == status, answer.data
    after = _counts(live)
    for key in ("requests", "receipts", "entries", "payments"):
        assert after[key] == before[key], key
    draft = _draft_row(live)
    assert draft.submitted_at is None and draft.service_request_id is None


def test_no_card_provider_refuses_before_anything_is_written(live, sarah):
    _app_fee(live, sarah, "10.00")
    with tenant_context(live.id):
        read = availability.availability(live.id, "31 Palm Ct")
    assert read["card_payment_available"] is False
    before = _counts(live)
    answer = _pay(live)
    assert answer.status_code == 409, answer.data
    assert answer.data["message_key"] == "portal.quickPay.cannotPayHere"
    assert _counts(live) == before


def test_a_fee_above_zero_with_no_card_is_refused(live, sarah):
    _app_fee(live, sarah, "10.00")
    _provider(live)
    before = _counts(live)
    answer = _send(live)
    assert answer.status_code == 422, answer.data
    assert answer.data["message_key"] == "portal.quickPay.instrumentRequired"
    assert _counts(live) == before


def test_a_fee_that_moved_is_refused_before_the_card_is_touched(live, sarah):
    _app_fee(live, sarah, "12.00")
    _provider(live)
    before = _counts(live)
    answer = _pay(live, fee_amount="10.00")
    assert answer.status_code == 409, answer.data
    assert answer.data["message_key"] == "portal.quickPay.amountMoved"
    assert _counts(live) == before


def test_a_card_number_is_refused_by_name(live, sarah):
    _app_fee(live, sarah, "10.00")
    _provider(live)
    answer = _pay(live, card_number="4242424242424242")
    assert answer.status_code == 409, answer.data
    assert answer.data["message_key"] == "portal.quickPay.cardNotAccepted"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · A RETRY RECORDS ONCE
# ═══════════════════════════════════════════════════════════════════════════
def test_a_double_press_is_one_request_one_receipt_and_no_second_charge(live, sarah):
    _app_fee(live, sarah, "10.00")
    _provider(live)
    first = _pay(live).data
    runs_after_first = _counts(live)["charges_asked"]
    second = _pay(live)
    assert second.status_code == 200
    assert second.data["idempotent_replay"] is True
    assert second.data["reference"] == first["reference"]
    assert second.data["fee_paid"]["amount"] == "10.0000"
    after = _counts(live)
    assert after["receipts"] == 1 and after["entries"] == 2
    # The replay never reached the provider.
    assert after["charges_asked"] == runs_after_first


def test_a_write_that_fails_after_an_approved_charge_leaves_nothing_and_the_retry_records_once(
    live, sarah, monkeypatch
):
    """The provider took the money and our write failed: nothing is kept, the
    customer reads *"We could not record that payment."*, and the retry from the
    same visit (same key → one debit at the provider) writes ONE of everything."""
    _app_fee(live, sarah, "10.00")
    _provider(live)
    real = sr.create_from_portal
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        made = real(*args, **kwargs)
        if calls["n"] == 1:
            raise RuntimeError("the database went away after the request was written")
        return made

    monkeypatch.setattr(sr, "create_from_portal", flaky)
    before = _counts(live)
    failed = _pay(live)
    assert failed.status_code == 500, failed.data
    assert failed.data["message_key"] == "portal.quickPay.notRecorded"
    after_failure = _counts(live)
    for key in ("requests", "receipts", "entries", "payments"):
        assert after_failure[key] == before[key], key
    assert _draft_row(live).submitted_at is None

    retried = _pay(live)
    assert retried.status_code == 200, retried.data
    done = _counts(live)
    assert done["requests"] == before["requests"] + 1
    assert done["receipts"] == before["receipts"] + 1
    assert done["entries"] == before["entries"] + 2
    # DEF-PAY-10554 — the retry RECORDED the kept approval; it asked nothing.
    assert done["charges_asked"] == after_failure["charges_asked"] == before["charges_asked"] + 1
    with tenant_context(live.id):
        receipt = cr_models.CounterReceipt.objects.get()
        assert receipt.confirmation == _draft_row(live).fee_idempotency_key


# ═══════════════════════════════════════════════════════════════════════════
# 3b · DEF-PAY-10554 — ONE CHARGE PER APPLICATION, EVEN ACROSS A RELOAD
#
# What would make these pass wrongly (law 7, habit 2): "charged once" would
# pass if the sandbox deduped on the key for us — it does not, so the count of
# provider runs IS the count of debits asked for. "Recorded once" would pass if
# the retry never wrote — so requests, receipts and postings are all counted.
# ═══════════════════════════════════════════════════════════════════════════
def _fail_the_first_write(monkeypatch):
    real = sr.create_from_portal
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        made = real(*args, **kwargs)
        if calls["n"] == 1:
            raise RuntimeError("the database went away after the request was written")
        return made

    monkeypatch.setattr(sr, "create_from_portal", flaky)


def test_a_reload_after_an_approved_charge_and_a_failed_write_charges_once_and_records_once(
    live, sarah, monkeypatch
):
    """The bug: approved, write failed, applicant RELOADS (a new browser attempt
    token) and presses again. Before the fix that was a new key and a second
    `$10.00` debit; now the draft's kept approval is recorded instead."""
    _app_fee(live, sarah, "10.00")
    _provider(live)
    _fail_the_first_write(monkeypatch)
    before = _counts(live)
    failed = _pay(live)
    assert failed.status_code == 500, failed.data
    assert failed.data["message_key"] == "portal.quickPay.notRecorded"
    kept = _draft_row(live)
    assert kept.submitted_at is None
    assert kept.fee_charge_approved["amount"] == "10.0000"
    assert kept.fee_charge_approved["reference"] == kept.fee_idempotency_key

    reloaded = _pay(live, attempt_token="0d0d0d0d-1111-4000-8000-00000000r10d")
    assert reloaded.status_code == 200, reloaded.data
    assert reloaded.data["fee_paid"]["amount"] == "10.0000"
    done = _counts(live)
    assert done["charges_asked"] == before["charges_asked"] + 1  # ONE debit asked for
    assert done["requests"] == before["requests"] + 1
    assert done["receipts"] == before["receipts"] + 1
    assert done["entries"] == before["entries"] + 2
    assert done["payments"] == before["payments"]

    # And a third press after it landed is a replay: nothing more anywhere.
    again = _pay(live, attempt_token="0d0d0d0d-2222-4000-8000-00000000r10d")
    assert again.status_code == 200 and again.data["idempotent_replay"] is True
    assert _counts(live) == done


def test_a_double_press_from_two_tabs_is_one_charge(live, sarah):
    """Two presses carrying DIFFERENT browser tokens (two tabs, or a reload) —
    the key is the draft's, so the second is the first one's replay."""
    _app_fee(live, sarah, "10.00")
    _provider(live)
    before = _counts(live)
    first = _pay(live)
    second = _pay(live, attempt_token="0d0d0d0d-3333-4000-8000-0000000tab2")
    assert first.status_code == second.status_code == 200
    assert second.data["reference"] == first.data["reference"]
    done = _counts(live)
    assert done["charges_asked"] == before["charges_asked"] + 1
    assert done["receipts"] == before["receipts"] + 1
    assert done["entries"] == before["entries"] + 2


def test_a_new_draft_charges_normally_under_its_own_key(live, sarah):
    other = "d2b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5e"
    _app_fee(live, sarah, "10.00")
    _provider(live)
    before = _counts(live)
    assert _pay(live).status_code == 200
    _draft(live, token=other)
    answer = _pay(live, token=other)
    assert answer.status_code == 200, answer.data
    done = _counts(live)
    assert done["charges_asked"] == before["charges_asked"] + 2
    assert done["receipts"] == before["receipts"] + 2
    one, two = _draft_row(live), _draft_row(live, other)
    assert one.fee_idempotency_key != two.fee_idempotency_key
    assert two.fee_idempotency_key == f"appfee:{live.id}:{two.pk}:10.0000:0"


def test_a_decline_moves_the_key_on_and_a_timeout_does_not(live, sarah):
    """A provider repeats its FIRST answer to a reused key, so after a decline
    the next press must carry a new key; after a silence it must not."""
    _app_fee(live, sarah, "10.00")
    connection = _provider(live, payments_sandbox.DECLINE)
    assert _pay(live).status_code == 409
    declined = _draft_row(live)
    assert declined.fee_declines == 1 and declined.fee_idempotency_key is None
    assert declined.fee_charge_approved is None

    with tenant_context(live.id):
        connection.config = {"behaviour": payments_sandbox.TIMEOUT}
        connection.save(update_fields=["config"])
    assert _pay(live).status_code == 503
    silent = _draft_row(live)
    assert silent.fee_declines == 1
    assert silent.fee_idempotency_key == f"appfee:{live.id}:{silent.pk}:10.0000:1"

    with tenant_context(live.id):
        connection.config = {"behaviour": payments_sandbox.APPROVE}
        connection.save(update_fields=["config"])
    answer = _pay(live)
    assert answer.status_code == 200, answer.data
    with tenant_context(live.id):
        receipt = cr_models.CounterReceipt.objects.get()
        # The same key the silent attempt carried — one debit at a real provider.
        assert receipt.confirmation == f"appfee:{live.id}:{silent.pk}:10.0000:1"


def test_the_30_day_cleanup_keeps_a_draft_holding_an_unrecorded_approval(live, sarah, monkeypatch):
    from datetime import datetime, timezone as dt_timezone

    from apps.portal import draft_cleanup

    _app_fee(live, sarah, "10.00")
    _provider(live)
    _fail_the_first_write(monkeypatch)
    assert _pay(live).status_code == 500
    later = datetime.now(dt_timezone.utc) + timedelta(days=60)
    with tenant_context(live.id):
        draft_cleanup.purge_unsent_drafts(live.id, now=later)
        assert portal_models.PortalApplicationDraft.objects.filter(token=TOKEN).exists()


def test_the_counter_receipt_door_itself_refuses_a_second_receipt(live, sarah):
    """`uq_counter_receipts_source` + the same slip → the first answer, no row."""
    from apps.payments import counter_receipts

    _app_fee(live, sarah, "10.00")
    _provider(live)
    body = _pay(live).data
    with tenant_context(live.id):
        request = customers_models.ServiceRequest.objects.get(pk=body["request_id"])
        again = counter_receipts.record_counter_receipt(
            source_type="service_request",
            source_id=request.id,
            source_ref=request.request_no,
            receipt_no=request.request_no,
            amount=TEN,
            currency="USD",
            method_code="card",
            taken_at=request.fee_collected_at,
        )
        assert again["state"] == cr_models.RECEIPT_EARNED
    assert _counts(live)["receipts"] == 1 and _counts(live)["entries"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# 4 · A $0.00 FEE — no payment step
# ═══════════════════════════════════════════════════════════════════════════
def test_a_zero_fee_takes_no_card_and_keeps_nothing_is_charged(live, sarah):
    _app_fee(live, sarah, "0.00")
    _provider(live)
    with tenant_context(live.id):
        read = availability.availability(live.id, "31 Palm Ct")
    assert read["application_fee"]["amount"] == "0.0000"
    assert read["card_payment_available"] is False
    before = _counts(live)
    answer = _send(live)
    assert answer.status_code == 200, answer.data
    assert answer.data["fee_paid"] is None
    after = _counts(live)
    assert after["requests"] == before["requests"] + 1
    assert after["receipts"] == before["receipts"]
    assert after["charges_asked"] == before["charges_asked"]
    with tenant_context(live.id):
        request = customers_models.ServiceRequest.objects.get(pk=answer.data["request_id"])
        rows = list(
            notification_models.OutboundMessage.objects.filter(
                source_type=service_request_events.SOURCE_SERVICE_REQUEST,
                source_id=str(request.id),
            )
        )
        assert [row.template_code for row in rows] == [
            service_request_events.TEMPLATE_ACKNOWLEDGEMENT
        ]


def test_a_card_sent_against_a_zero_fee_is_not_charged(live, sarah):
    _app_fee(live, sarah, "0.00")
    _provider(live)
    before = _counts(live)
    answer = _pay(live, fee_amount="0.00")
    assert answer.status_code == 200, answer.data
    after = _counts(live)
    assert after["receipts"] == before["receipts"]
    assert after["charges_asked"] == before["charges_asked"]


# ═══════════════════════════════════════════════════════════════════════════
# 5 · APPROVAL DOES NOT RE-RAISE A PAID FEE
# ═══════════════════════════════════════════════════════════════════════════
def test_approval_and_refusal_move_no_money_on_a_paid_request(live, sarah):
    _app_fee(live, sarah, "10.00")
    _provider(live)
    body = _pay(live).data
    with tenant_context(live.id):
        request_id = body["request_id"]
        lines_before = customers_models.ServiceRequestFee.objects.filter(
            request_id=request_id
        ).count()
        entries_before = ledger_models.JournalEntry.objects.filter(tenant=live).count()
        from apps.customers import service_request as rules

        condition = rules.fee_condition(
            outstanding_lines=sr.outstanding_fee_lines(request_id),
            outstanding_amount=sr.fee_total_to_collect(request_id)["outstanding"],
            currency="USD",
        )
        assert condition.blocking is False
        # Approval's own release, exactly as `approve_and_raise` calls it.
        sr._release_counter_fee(sarah, sr.request_row(request_id), outcome="approved")
        sr._release_counter_fee(sarah, sr.request_row(request_id), outcome="refused")
        assert ledger_models.JournalEntry.objects.filter(tenant=live).count() == entries_before
        assert (
            customers_models.ServiceRequestFee.objects.filter(request_id=request_id).count()
            == lines_before
            == 1
        )
        receipt = cr_models.CounterReceipt.objects.get(source_id=request_id)
        assert receipt.state == cr_models.RECEIPT_EARNED
        # And the request reads nothing to collect — no second ask.
        assert sr.add_application_fee_line(sarah, request_id) is None


# ═══════════════════════════════════════════════════════════════════════════
# 6 · THE ACKNOWLEDGEMENT SAYS THE AMOUNT
# ═══════════════════════════════════════════════════════════════════════════
def test_the_acknowledgement_states_the_fee_received(live, sarah):
    _app_fee(live, sarah, "10.00")
    _provider(live)
    body = _pay(live).data
    with tenant_context(live.id):
        request = customers_models.ServiceRequest.objects.get(pk=body["request_id"])
        rows = list(
            notification_models.OutboundMessage.objects.filter(
                source_type=service_request_events.SOURCE_SERVICE_REQUEST,
                source_id=str(request.id),
            )
        )
        assert len(rows) == 1
        assert rows[0].template_code == service_request_events.TEMPLATE_ACKNOWLEDGEMENT_FEE
        art = rendering.render_for_dispatch(rows[0])
        assert "You paid $10.00 by card." in art.body
        assert f"Your receipt number is {request.request_no}." in art.body
        assert "Nothing is charged" not in art.body


# ═══════════════════════════════════════════════════════════════════════════
# 7 · TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════════
def test_another_utilitys_draft_is_not_found_and_charges_nothing(live, sarah, oak_ridge, elena):
    _app_fee(live, sarah, "10.00")
    _provider(live)
    switch_on(oak_ridge, elena)
    _app_fee(oak_ridge, elena, "10.00")
    _provider(oak_ridge)
    pine_before, oak_before = _counts(live), _counts(oak_ridge)
    answer = _pay(oak_ridge)  # Pine Hill's token, at Oak Ridge
    assert answer.status_code == 404, answer.data
    assert _counts(oak_ridge) == oak_before
    assert _counts(live) == pine_before
    # And Pine Hill's paid receipt is invisible under Oak Ridge.
    _pay(live)
    with tenant_context(oak_ridge.id):
        assert not cr_models.CounterReceipt.objects.filter(tenant_id=live.id).exists() or (
            cr_models.CounterReceipt.objects.filter(tenant_id=oak_ridge.id).count() == 0
        )
        assert cr_models.CounterReceipt.objects.filter(tenant_id=oak_ridge.id).count() == 0
