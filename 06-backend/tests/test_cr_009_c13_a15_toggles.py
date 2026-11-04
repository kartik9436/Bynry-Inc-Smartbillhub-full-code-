# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 + US-PAY-025 (CR-009 C-13 — the four A15 "(opt)"
#           send-time elections, DEFAULT ON, and the ONE wired consumer)
#           Screens: S8 (Settings → Notifications) · S22 (record payment)
# Rules:    BR-NOT-022 (the four A15 toggles ship DEFAULT ON — PO 2026-08-17,
#           verbatim "keep them default to start with Utility will amake them
#           off"; OQ-205 CLOSED, the ruling REVERSED the off-by-default
#           recommendation) · BR-PAY-024 (receipt auto-queue on record) ·
#           BR-NOT-005 (queue only) · CLAUDE.md rule 6 (idempotent queue write)
# ───────────────────────────────────────────────────────
"""BR-NOT-022, proved at both ends: the stored default and the wired reader.

The ratified figure is `default=True` × 4 — asserted here so drift goes RED
(the PO ruling protocol's own requirement). The consumer half is the guard
hard-won law 2 demands: a switch was drawn, so something must read it, and the
strongest proof is behavioural — flip the toggle, record a payment, count the
queue.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.notifications import dispatch_config, models as notification_models
from apps.notifications import settings_api
from apps.payments import receipts, services as payment_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 18, 10, 30, tzinfo=UTC)
AMOUNT = Decimal("247.30")  # OQ-205's own worked figure (PMT-2608-0455)

THE_FOUR = (
    "receipt_on_record_payment",
    "credit_notice_email",
    "bookkeeper_copies",
    "lockbox_receipts",
)


def _record(actor, account, **overrides):
    return payment_services.record_payment(
        actor,
        account_id=account.pk,
        amount=overrides.pop("amount", AMOUNT),
        posted_at=POSTED_AT,
        cleared_at=overrides.pop("cleared_at", POSTED_AT),
        method_code="check",
        **overrides,
    )


def _receipt_rows(tenant):
    return notification_models.OutboundMessage.objects.filter(
        tenant_id=tenant.pk, source_type="payment"
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE RATIFIED DEFAULT — ON, all four (the PO's figure, not a convenience)
# ══════════════════════════════════════════════════════════════════════════
def test_c13__all_four_elections_seed_on(brazos):
    """PO 2026-08-17, verbatim: *"keep them default to start with Utility will
    amake them off"*. A tenant that has never opened S8 holds all four ON —
    which is also OQ-216's posture for tenants provisioned before the columns
    existed (AddField default writes TRUE onto every existing row)."""
    with tenant_ctx(brazos):
        settings = dispatch_config.dispatch_settings()
    for field in THE_FOUR:
        assert getattr(settings, field) is True, f"{field} must seed ON (BR-NOT-022)"


def test_c13__each_election_is_editable_and_audited_like_every_other_setting(brazos, dana):
    """The utility "will amake them off" — so OFF must be one audited save away,
    per election, through the one write path."""
    with tenant_ctx(brazos):
        saved = dispatch_config.update_dispatch_settings(
            actor=dana, receipt_on_record_payment=False, bookkeeper_copies=False
        )
        assert saved.receipt_on_record_payment is False
        assert saved.bookkeeper_copies is False
        # The other two are untouched by a save that did not name them.
        assert saved.credit_notice_email is True
        assert saved.lockbox_receipts is True


def test_c13__a_non_boolean_election_is_refused(brazos, dana):
    with tenant_ctx(brazos), pytest.raises(dispatch_config.DispatchConfigRefused):
        dispatch_config.update_dispatch_settings(actor=dana, lockbox_receipts="yes")


def test_c13__the_settings_api_serves_the_four_with_their_consumer_facts(brazos, dana):
    """Mandate 5 (no setting without a screen) needs the WIRE to carry, per
    toggle, whether anything reads it — hard-won law 2 as data, so the S8 card
    can say "nothing reads this yet" instead of implying a live send."""
    response = api_call(
        settings_api.notification_settings,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    for field in THE_FOUR:
        assert response.data[field] is True
    consumers = response.data["election_consumers"]
    assert consumers["receipt_on_record_payment"]["wired"] is True
    for field in ("credit_notice_email", "bookkeeper_copies", "lockbox_receipts"):
        assert consumers[field]["wired"] is False
        assert consumers[field]["detail"]


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE WIRED CONSUMER — flip the toggle, record a payment, count the queue
# ══════════════════════════════════════════════════════════════════════════
def test_c13__recording_a_payment_with_the_election_on_queues_one_print_receipt(brazos, marcus):
    """BR-PAY-024 behind the shipped default: ONE `pdf_print` row, source
    `payment` + the payment's own id, template class `receipt`.

    ⚠ **AMENDED 2026-08-29 (CR-048 B3).** This case asserted `count() - before
    == 1` and read a single row with `rows.get(source_id=...)`. Both were
    statements about the CHANNEL COUNT rather than about this election, and B3
    added a second channel: the emailed receipt, which is what the
    `payment_received` rule on Settings → Notifications actually governs. The
    assertions are now PER CHANNEL, which is what they always meant — the print
    receipt is BR-PAY-024's own document and no notification rule may remove it.
    The email half is asserted in `test_cr048_b3_payments_fires_its_events.py`,
    which owns it.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        before = _receipt_rows(brazos).filter(channel="pdf_print").count()
        result = _record(marcus, account)
        rows = _receipt_rows(brazos)

        assert rows.filter(channel="pdf_print").count() - before == 1
        row = rows.get(source_id=result.payment_id, channel="pdf_print")
        assert row.template_code == "receipt"
        assert row.status == "queued"  # queueing is not sending (BR-NOT-013)
        codes = {p["code"] for p in result.problems}
        assert receipts.RECEIPT_QUEUED in codes


def test_c13__switching_the_election_off_stops_the_receipt_and_says_so(brazos, marcus, dana):
    """The toggle's OTHER half — OFF must be obeyed by the same consumer, and
    the result must SAY the utility elected it (never a silent nothing)."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        dispatch_config.update_dispatch_settings(actor=dana, receipt_on_record_payment=False)
        before = _receipt_rows(brazos).count()
        result = _record(marcus, account)

        assert _receipt_rows(brazos).count() == before
        codes = {p["code"] for p in result.problems}
        assert receipts.RECEIPT_ELECTION_OFF in codes
        assert receipts.RECEIPT_QUEUED not in codes


def test_c13__a_replayed_record_does_not_queue_a_second_receipt(brazos, marcus):
    """Rule 6 twice over: the replay returns the FIRST payment, and even a
    re-driven queue write would find the receipt row under the payment's own
    id. One payment, one receipt."""
    key = str(uuid.uuid4())
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        first = _record(marcus, account, idempotency_reference=key)
        before = _receipt_rows(brazos).count()
        again = _record(marcus, account, idempotency_reference=key)

        assert again.created is False
        assert again.payment_id == first.payment_id
        assert _receipt_rows(brazos).count() == before


def test_c13__a_receipt_failure_never_fails_the_payment(brazos, marcus, monkeypatch):
    """THE ONE LAW of the consumer module. queue_document blowing up must leave
    the money recorded and the failure NAMED on the result."""
    from apps.notifications import services as notification_services

    def explode(**_kwargs):
        raise notification_services.QueueWriteRefused("the queue is on fire (test)")

    monkeypatch.setattr(notification_services, "queue_document", explode)
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        result = _record(marcus, account)

    assert result.created is True
    codes = {p["code"] for p in result.problems}
    assert receipts.RECEIPT_QUEUE_REFUSED in codes
    assert "the queue is on fire" in " ".join(
        p.get("detail", "") for p in result.problems
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-004+US-PAY-025@cr009c13 (12-governance/02-decision-log.md → 2026-08-17 C-13 verbatim · 12-governance/01-open-questions.md OQ-205/OQ-216 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-022 · apps/notifications/dispatch_config.py · apps/payments/receipts.py)
# generated: 2026-08-18 by story-coder (CR-009 C-section lane)
# checklist: A✔ B✔ C✔ D✔(the settings API case) E=deferred(the S8 card's own test is SettingsNotificationsTab.test.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the ON default by flipping one migration default to False; the consumer by running the queue-count case before record_payment called receipts (0 rows, expected 1); the never-fail guard by removing the except and reading QueueWriteRefused through record_payment.
# exceptions: (1) ⚠ [AMENDED 2026-08-29 · CR-048 B3] THIS READ "NO EMAIL-RECEIPT ASSERTION — the emailed receipt is the payment_received SET-12 rule's and is deliberately not this consumer's". THE EMAILED RECEIPT IS THIS CONSUMER'S NOW: CR-048 A1 made the queue read that rule and B3 made this module the writer that names the event, so there is no second writer to double with. This file still asserts only the PRINT half — per channel, since 2026-08-29 — and tests/test_cr048_b3_payments_fires_its_events.py owns the email half and the switch that stops it. (2) THE OTHER THREE ELECTIONS ARE ASSERTED AS STORED + HONESTLY-UNWIRED, never as behaviour, because their consumers do not exist and a behavioural test would have to invent one.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
