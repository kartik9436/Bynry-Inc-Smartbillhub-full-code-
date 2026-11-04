# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 · C21 — "Gateway payment webhooks", `CR-060 §0d.1`, labelled
#           *"new — was an undecided absence"*.
# Story:    US-PAY-001   Screens: S33
# Rules:    BR-PAY-003 · BR-PAY-021 · BR-PAY-028 · CLAUDE.md hard rule 1 ·
#           rule 2 · rule 6 · rule 7 · hard-won law 3 (defaults fail closed) ·
#           law 14 (the SAVEPOINT, proved on PostgreSQL)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""C21 — a card payment appears on Record payments, and a retry writes ONE row.

THE ACCEPTANCE LINE, VERBATIM
=============================
*"A card payment from the portal appears on Record payments with no clerk keying
it, marked cleared and allocated; the provider re-sending the same callback
produces ONE payment, not two."*

Both halves are the first two tests in this file, and **the second one is the
primary requirement rather than a footnote.** Payment gateways retry — on
timeouts, on 500s, on their own schedule — and **a duplicate webhook that creates
a second payment is money the customer did not pay, sitting on their account**,
which the allocation engine will then spend on their next bill.

THE TWO GUARDS, ASSERTED SEPARATELY (DEF-058's lesson)
======================================================
    uq_payment_webhook_events_event   has this DELIVERY been seen?
    uq_payments_webhook_key           has this PAYMENT been recorded?

DEF-058 is what happens when one guard silently stands in for another, so guard
1 is switched OFF in `test_c21__the_payment_key_holds_when_guard_one_is_off` and
guard 2 must still write one payment. Neither is trusted because the other
exists.

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
========================================================================
  * With `verify_signature` returning `(True, "")` unconditionally,
    `test_c21__an_unsigned_deployment_refuses_everything` fails with
    `assert 'accepted' == 'refused'` — an unauthenticated endpoint that puts
    money on any account.
  * With `_existing_delivery`'s lookup removed AND the unique constraint
    dropped, `test_c21__a_retry_writes_one_payment` fails with `assert 2 == 1`:
    the customer is charged twice on their account.
  * With `_record`'s nested `transaction.atomic()` removed and run on
    PostgreSQL, `test_c21__a_refused_payment_keeps_its_delivery_row` fails with
    `psycopg.errors.InFailedSqlTransaction` — and the delivery row that was the
    only evidence of the money is gone. **On SQLite that same sabotage passes**,
    which is CLAUDE.md hard-won law 14 exactly.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.payments import models, webhooks
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

PROVIDER = "stripe"
SECRET = "whsec_test_only_never_a_real_one"
SECRETS = {PROVIDER: SECRET}

RECEIVED_AT = datetime(2026, 8, 8, 14, 30, tzinfo=UTC)
PAID_AT = "2026-08-08T14:29:00+00:00"

#: PE-1's own bill and cheque figure, so the money is a figure this repo already
#: recognises rather than one invented for a webhook.
THE_BILL = Decimal("292.87")


def a_body(account, *, amount=THE_BILL, **extra):
    body = {
        "type": "payment_intent.succeeded",
        "account_id": str(account.pk),
        "amount": str(amount),
        "currency": "USD",
        "posted_at": PAID_AT,
        "cleared_at": PAID_AT,
        "reference": "ch_3P9xQ2abc",
    }
    body.update(extra)
    return body


def signed(body):
    """The raw bytes and their signature, exactly as a provider would send them.

    ⚠ **THE SIGNATURE IS OVER THE BYTES**, so the test computes it from the same
    `raw` it hands in. A test that signed a re-serialised dict would pass while
    the production path failed, which is the trap `verify_signature` names.
    """
    raw = json.dumps(body).encode("utf-8")
    signature = hmac.new(SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, f"sha256={signature}"


def deliver(body, *, event_id="evt_1P9xQ2", provider=PROVIDER, signature=None, raw=None):
    computed_raw, computed_signature = signed(body)
    return webhooks.ingest(
        provider=provider,
        event_id=event_id,
        raw_body=raw if raw is not None else computed_raw,
        signature=signature if signature is not None else computed_signature,
        received_at=RECEIVED_AT,
    )


# ══ THE ACCEPTANCE LINE ════════════════════════════════════════════════════


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__a_card_payment_appears_with_no_clerk_keying_it(brazos, dana):
    """**Marked cleared and allocated, with nobody at a keyboard.**

    The payment goes through `services.record_payment` — the ONE inbound write
    path, unchanged — so it meets the account's open bills and posts to the books
    exactly as a counter payment does. That is the whole point of not building a
    second recording path for gateway money.
    """
    from apps.payments import billing_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        bill = an_issued_bill(
            brazos, account, number="BL-0141", total=THE_BILL, issued_on=date(2026, 8, 1)
        )

        result = deliver(a_body(account))

        assert result.status == models.WEBHOOK_ACCEPTED
        assert result.signature_verified is True
        assert result.payment_id is not None
        assert result.payment_no is not None, "it has a PMT- number like any other payment"

        payment = models.Payment.objects.get(pk=result.payment_id)
        # CR-186-BRC10 (PO 2026-10-21): posted at entry, cleared at reconciliation.
        assert payment.status == models.PAYMENT_POSTED, "posted, and applied at once"
        assert payment.amount == THE_BILL
        assert billing_seam.allocated_so_far(bill.pk) == THE_BILL, "and allocated"
        assert payment.journal_entry_id is not None, "and in the books (CLAUDE.md rule 5)"


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__a_retry_writes_one_payment(brazos, dana):
    """⚠ **THE PRIMARY REQUIREMENT.** *"the provider re-sending the same callback
    produces ONE payment, not two."*

    A duplicate webhook that created a second payment would be money the
    customer did not pay, sitting on their account — and the allocation engine
    would spend it on their next bill and nobody would look at it again.

    **RED PROOF:** with guard 1's lookup removed and the unique constraint
    dropped, this fails with `assert 2 == 1`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        an_issued_bill(
            brazos, account, number="BL-0141", total=THE_BILL, issued_on=date(2026, 8, 1)
        )

        first = deliver(a_body(account))
        second = deliver(a_body(account))
        third = deliver(a_body(account))

        assert first.created is True
        assert second.created is False and third.created is False
        assert second.status == models.WEBHOOK_DUPLICATE
        assert (
            models.Payment.objects.filter(account_id=account.pk).count() == 1
        ), "one payment, whatever the provider does"
        assert models.PaymentWebhookEvent.objects.count() == 1, "and one delivery row"
        assert any(
            problem["code"] == "duplicate_delivery_ignored" for problem in second.problems
        ), "and the replay says so rather than looking like a fresh success"


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__the_payment_key_holds_when_guard_one_is_off(brazos, dana, monkeypatch):
    """⚠ **DEF-058's LESSON: EACH GUARD IS ASSERTED WITHOUT THE OTHER.**

    Guard 1 is switched off in process, so the delivery lookup finds nothing and
    the money path runs twice. `uq_payments_webhook_key` — through
    `webhook|stripe:evt_…` — must still leave ONE payment.

    Without this case the two guards would be one guard wearing two names, and
    the day somebody changes the key scheme is the day the other silently stops
    covering it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        an_issued_bill(
            brazos, account, number="BL-0141", total=THE_BILL, issued_on=date(2026, 8, 1)
        )
        deliver(a_body(account))

        monkeypatch.setattr(webhooks, "_existing_delivery", lambda *a, **k: None)
        # The delivery row's own constraint still refuses, which is guard 1's
        # DATABASE half — so this asserts on the PAYMENTS, which is what the
        # customer feels.
        try:
            deliver(a_body(account), event_id="evt_1P9xQ2")
        except Exception:  # the delivery unique index, doing its job
            pass
        assert models.Payment.objects.filter(account_id=account.pk).count() == 1


# ══ HARD-WON LAW 3 · SIGNATURE VERIFICATION FAILS CLOSED ═══════════════════


def test_c21__an_unsigned_deployment_refuses_everything(brazos, dana):
    """No configured secret means NO callbacks. The unsafe option must be typed.

    `PAYMENT_WEBHOOK_SECRETS` is empty by default, and an empty secret is the
    true statement about a product whose card rails are v2: this utility takes
    no gateway callbacks. A default that accepted unsigned deliveries would be
    an unauthenticated endpoint that puts money on any account.

    **RED PROOF:** with `verify_signature` returning `(True, "")`
    unconditionally, this fails with `assert 'accepted' == 'refused'`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        result = deliver(a_body(account))

        assert result.status == models.WEBHOOK_REFUSED
        assert result.outcome == webhooks.REFUSED_NO_SECRET
        assert result.payment_id is None
        assert models.Payment.objects.count() == 0, "no money was put on any account"
        assert models.PaymentWebhookEvent.objects.count() == 1, (
            "and the delivery is RECORDED — a provider misconfiguration and an attack look "
            "identical in an empty log, and the first is far more common at 3am"
        )


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__a_forged_signature_is_refused_and_recorded(brazos, dana):
    """A wrong signature creates no payment and leaves evidence."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        result = deliver(a_body(account), signature="sha256=" + "0" * 64)

        assert result.status == models.WEBHOOK_REFUSED
        assert result.outcome == webhooks.REFUSED_BAD_SIGNATURE
        assert models.Payment.objects.count() == 0
        row = models.PaymentWebhookEvent.objects.get()
        assert row.signature_verified is False
        assert row.body, "the body is kept, so the delivery can be explained and replayed"


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__the_signature_is_over_the_bytes_that_arrived(brazos, dana):
    """Signed over a re-serialised body, the same payload does NOT verify.

    Two JSON encoders disagree about spacing and key order, so a path that
    verified against `json.dumps(parsed)` would fail for a reason nobody can
    debug — and the debugging usually ends with somebody switching verification
    off. This pins the raw-bytes comparison.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        body = a_body(account)
        raw, signature = signed(body)
        respaced = json.dumps(body, indent=2).encode("utf-8")
        assert respaced != raw

        result = deliver(body, raw=respaced, signature=signature)
        assert result.status == models.WEBHOOK_REFUSED
        assert result.outcome == webhooks.REFUSED_BAD_SIGNATURE


# ══ WHAT A BAD CALLBACK DOES, AND WHAT IT MUST NOT DO ══════════════════════


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__a_refused_payment_keeps_its_delivery_row(brazos, dana):
    """An unknown account creates no payment and the delivery STANDS.

    *"The money is real at the gateway; somebody has to see it."* A lost row here
    is a payment nobody knows about, and the provider will stop retrying long
    before anyone notices.
    """
    with tenant_ctx(brazos):
        body = a_body(type("X", (), {"pk": uuid.uuid4()})())
        result = deliver(body)

        assert result.status == models.WEBHOOK_REFUSED
        assert result.outcome == webhooks.REFUSED_RULE
        assert models.Payment.objects.count() == 0
        assert (
            models.PaymentWebhookEvent.objects.count() == 1
        ), "the delivery survives the refused payment — that is the SAVEPOINT's whole job"


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__a_float_amount_is_refused_never_converted(brazos, dana):
    """CLAUDE.md rule 2 at the boundary — the only place a float is still visible."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        # ⚠ **THE BODY MUST CARRY A REAL FLOAT**, which means bypassing
        # `a_body`'s `str()`. A test that stringified it first would prove
        # nothing: the refusal exists for a gateway whose JSON contains
        # `"amount": 292.87` as a NUMBER, and `json.loads` gives that back as a
        # Python float — the one place a float is still visible for what it is.
        body = a_body(account)
        body["amount"] = 292.87
        result = deliver(body)
        assert isinstance(json.loads(json.dumps(body))["amount"], float)
        assert result.status == models.WEBHOOK_REFUSED
        assert "float" in (result.problems[-1]["detail"] or "")


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__a_callback_with_no_dates_is_refused(brazos, dana):
    """BR-PAY-021 — both dates, and the GATEWAY names them. No clock is read.

    A payment stamped with the server's time would be on time or late depending
    on where the server is, and a redelivered callback would stamp a different
    instant from the first — a replay that is not identical.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        body = a_body(account)
        body.pop("posted_at")
        body.pop("cleared_at")
        result = deliver(body)
        assert result.status == models.WEBHOOK_REFUSED
        assert "reads no clock" in (result.problems[-1]["detail"] or "")


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__a_delivery_naming_no_event_is_refused(brazos, dana):
    """Without a provider event id there is nothing to dedupe on.

    A gateway that retried would create a second payment on a customer's
    account, which is the one outcome C21 exists to prevent — so this refuses
    before anything is written rather than accepting an undedupable delivery.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(PaymentRuleError) as refusal:
            deliver(a_body(account), event_id="  ")
        assert "nothing to dedupe on" in str(refusal.value)
        assert models.PaymentWebhookEvent.objects.count() == 0


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__two_providers_may_reuse_one_event_id(brazos, dana):
    """The key is `(tenant, provider, event_id)` — two gateways both number `1`."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        an_issued_bill(
            brazos, account, number="BL-0141", total=THE_BILL, issued_on=date(2026, 8, 1)
        )
        first = deliver(a_body(account), event_id="1")
        assert first.status == models.WEBHOOK_ACCEPTED
        # A second provider is not configured, so its delivery is REFUSED rather
        # than deduped — which is the point: it was not treated as a replay.
        second = deliver(a_body(account), event_id="1", provider="adyen")
        assert second.created is True
        assert second.status == models.WEBHOOK_REFUSED
        assert second.outcome == webhooks.REFUSED_NO_SECRET


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__nothing_here_initiates_a_charge(brazos, dana):
    """⚠ CS-1 and CS-9 are v2 and this is NOT them.

    Stated on every result rather than only in a docstring, because *"a status
    that can express a charge is one some path eventually gets written
    against"* — CS-9's own warning — and the same is true of a function.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        an_issued_bill(
            brazos, account, number="BL-0141", total=THE_BILL, issued_on=date(2026, 8, 1)
        )
        result = deliver(a_body(account))
        assert any(
            problem["code"] == "no_charge_is_ever_initiated_here" for problem in result.problems
        )
        assert (
            models.AutopayCaptureIntent.objects.count() == 0
        ), "and no capture intent is invented on this path"


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__the_delivery_is_audited(brazos, dana, audit_rows):
    """Hard rule 7 — and the ACTOR is a job, because a webhook has no user.

    A service account nobody has ruled on is exactly the shape `reversal.py`
    refuses to pre-empt for CS-1, so none is invented here either: the audit row
    names the job (BR-AUD-003).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        an_issued_bill(
            brazos, account, number="BL-0141", total=THE_BILL, issued_on=date(2026, 8, 1)
        )
        result = deliver(a_body(account))
        # Through this suite's own BE-03 capture sink — see the cheque lane's
        # note in `test_cr059_cs30_cheques.py` for why the live table is the
        # wrong handle for an assertion of this shape.
        written = [row for row in audit_rows if row["action"] == webhooks.AUDIT_RECEIVED]
        assert len(written) == 1
        assert written[0]["after"]["provider"] == PROVIDER
        assert written[0]["after"]["job"] == "payments.webhook"
        assert written[0]["after"]["signature_verified"] is True
        assert result.status == models.WEBHOOK_ACCEPTED


# ══ THE PROOFS THAT ONLY POSTGRESQL CAN GIVE (hard-won law 14) ═════════════


@requires_postgres
@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__a_refused_payment_keeps_its_row_on_postgres(brazos, dana):
    """⚠ **THE CASE CLAUDE.md LAW 14 EXISTS FOR, ON THE DATABASE THAT SHOWS IT.**

    `_record` catches a `PaymentRuleError` and carries on recording the outcome
    on the delivery row. **On PostgreSQL that only works because the payment
    attempt is inside a SAVEPOINT** — without it the failed statement aborts the
    whole transaction, every later query raises `InFailedSqlTransaction`, and
    the delivery row is lost at COMMIT.

    **On SQLite the broken version passes**, because SQLite has no aborted-
    transaction state. So this case is the proof and the green suite is not.
    """
    with tenant_ctx(brazos):
        stranger = uuid.uuid4()
        result = deliver(a_body(type("X", (), {"pk": stranger})()))

        assert result.status == models.WEBHOOK_REFUSED
        assert models.Payment.objects.count() == 0
        row = models.PaymentWebhookEvent.objects.get()
        assert row.status == models.WEBHOOK_REFUSED
        assert row.outcome, "and the reason is on the row, which needed the transaction alive"


@requires_postgres
@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_c21__the_delivery_row_is_append_only(brazos, dana):
    """`payments/0020`'s freeze — only the processing outcome may move.

    The provider, the event id, the body and the moment it arrived are the
    evidence, and evidence that can be edited is not evidence.
    """
    from django.db import DatabaseError, transaction

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        an_issued_bill(
            brazos, account, number="BL-0141", total=THE_BILL, issued_on=date(2026, 8, 1)
        )
        deliver(a_body(account))
        row = models.PaymentWebhookEvent.objects.get()

        row.event_id = "evt_forged"
        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                row.save(update_fields=["event_id", "updated_at"])
        assert "append-only" in str(refused.value)
