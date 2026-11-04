# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-013 (the platform delivery dashboard + re-queue) ·
#           US-NOT-014 (bounces + returned mail feeding the bad-address flow) ·
#           US-NOT-015 (queue read-models for reports + the W6 email consumers)
#           Screens: S8 · S30 · S35 · S46
# Rules:    BR-NOT-005 (per-run dashboard + re-queue; forward-only statuses) ·
#           BR-TEN-041 #8 (Settings → Notifications is the dispatch home) ·
#           BR-PAY-018 (returned mail → bad-address → paper suppressed until
#           verified; balances unaffected) · BR-REP-007 (read-models over the
#           queue) · BR-REP-017 / BR-LED-020 (report + bookkeeper emails ride
#           the queue) · B1 (notifications EMITS the return event)
# ───────────────────────────────────────────────────────
"""Delivery ops — and the one line of code without which nothing ever moves.

THE CASE THIS FILE EXISTS FOR is
`test_us_not_013_tc3__requeue_clears_the_batch_id_or_a_crashed_row_never_moves`.
The dispatcher, by ruling, never re-selects a row it has claimed: a cycle that
crashes between the claim and the provider answer leaves rows `queued` WITH a
batch id, matching neither branch of its selection predicate, forever. Its own
trailer names the recovery and the requirement — *"the recovery is US-NOT-013's
re-queue … which must clear `batch_id` when it is"*. A re-queue that reset only
the STATUS would look correct on every screen and fix nothing at all.

⚠ TWO DASHBOARD COLUMNS ARE STRUCTURALLY EMPTY AND THAT IS ASSERTED, NOT
GLOSSED. `delivered` and `bounced` are provider facts; no provider adapter
exists on any channel (PO ruling 2026-08-15 — delivery is out of this release),
so nothing in this repo can write either. `queue_health()` reports that as DATA
and a case below asserts the report, because "delivered: 0" beside "sent: 142"
reads as a delivery failure when the truth is that nobody is reporting.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import delivery_ops, dispatcher, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 8, 9, 15, 0, tzinfo=dt_timezone.utc)


def an_account(actor, tenant, *, account_no="A-11455"):
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line=f"{account_no} Route 4")
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def a_row(tenant, **overrides):
    values = dict(
        tenant_id=tenant.id,
        source_type="invoice",
        source_id=uuid.uuid4(),
        channel=models.CHANNEL_PRINT,
        template_code="bill_residential",
        template_id=uuid.uuid4(),
        template_version=2,
        recipient_address="1901 Bluestem Ln",
        status=models.STATUS_QUEUED,
    )
    values.update(overrides)
    return models.OutboundMessage.objects.create(**values)


# ── US-NOT-013 TC-1 · the counts tie to the rows ────────────────────────────
def test_us_not_013_tc1__the_dashboard_counts_tie_to_the_rows_exactly(brazos):
    """US-NOT-013 TC-1: *"Counts tie to rows exactly: … totals per type ×
    channel × status."* US-NOT-015 TC-1 asks the same question for the canned
    health report and gets the same answer from the same function — two counters
    over one table is how a dashboard and a report come to disagree about the
    same day."""
    with tenant_ctx(brazos):
        for _ in range(6):
            a_row(brazos, status=models.STATUS_FAILED, attempts=3, last_error="provider timeout")
        for _ in range(4):
            a_row(brazos)
        a_row(brazos, source_type="payment", channel=models.CHANNEL_EMAIL)

        health = delivery_ops.queue_health()

    assert health.totals[models.STATUS_FAILED] == 6
    assert health.totals[models.STATUS_QUEUED] == 5
    assert health.retry_exhausted == 6
    invoice_print_failed = [
        entry
        for entry in health.counts
        if entry["source_type"] == "invoice"
        and entry["channel"] == models.CHANNEL_PRINT
        and entry["status"] == models.STATUS_FAILED
    ]
    assert invoice_print_failed[0]["count"] == 6


def test_us_not_013_the_two_provider_statuses_are_reported_as_unpopulated(brazos):
    """⚠ The honesty case. `delivered` and `bounced` are provider facts and NO
    provider adapter exists on any channel — delivery is out of this release by
    PO ruling (2026-08-15). Their counts are structurally zero here.

    A dashboard rendering "delivered: 0" next to "sent: 142" tells a utility its
    post is failing when the truth is that nobody is reporting. The read-model
    says which statuses cannot be populated, as DATA, so the screen can render
    "not reported" — the same distinction `apps/billing/release.py` insists on
    for mandate coverage.
    """
    with tenant_ctx(brazos):
        a_row(brazos)
        health = delivery_ops.queue_health()

    assert health.unpopulated_statuses == (models.STATUS_DELIVERED, models.STATUS_BOUNCED)
    assert "provider_statuses_never_written" in {p["code"] for p in health.problems}
    assert health.totals.get(models.STATUS_DELIVERED, 0) == 0


# ── US-NOT-013 TC-3 · THE case ──────────────────────────────────────────────
def test_us_not_013_tc3__requeue_clears_the_batch_id_or_a_crashed_row_never_moves(
    brazos, dana, audit_rows
):
    """US-NOT-013 TC-3: *"Re-queue 6 failed rows (bulk) → Status → queued; next
    dispatcher batch picks them within normal batch pacing; `audit_log`
    `delivery.requeued` per row."*

    ⚠ **THE ASSERTION THAT MATTERS IS `batch_id is None`, NOT the status.**
    `apps/notifications/dispatcher.py` selects rows matching
    `(batch_id IS NULL AND next_attempt_at IS NULL) OR next_attempt_at <= now`,
    and by ruling it never re-selects a row it has claimed — rule 6 outranks
    liveness, because re-sending a batch a process died inside would post a
    second 48-hour disconnect notice. A crashed hand-off therefore leaves rows
    `queued` WITH a batch id, matching neither branch, forever.

    PROVED RED by deleting `row.batch_id = None` from `requeue`: the status went
    back to `queued`, the audit row was written, the toast read "Re-queued 2 ✓"
    — and the following dispatch cycle claimed ZERO of them. The failure was
    `assert 0 == 2` on the claimed count, and every screen in the product would
    have said the operator's fix had worked.
    """
    with tenant_ctx(brazos):
        crashed = a_row(brazos, batch_id=uuid.uuid4(), attempts=1, last_attempt_at=NOW)
        failed = a_row(
            brazos,
            status=models.STATUS_FAILED,
            attempts=3,
            batch_id=uuid.uuid4(),
            last_error="provider timeout",
        )

        outcome = delivery_ops.requeue(message_ids=(crashed.pk, failed.pk), actor=dana)

        crashed.refresh_from_db()
        failed.refresh_from_db()
        assert len(outcome.requeued) == 2
        assert crashed.batch_id is None and failed.batch_id is None
        assert crashed.next_attempt_at is None and failed.next_attempt_at is None
        assert failed.status == models.STATUS_QUEUED
        assert failed.last_error is None
        # attempts are NOT reset — BR-NOT-005 counts PROVIDER attempts, and
        # zeroing them would hand a chronically failing address three fresh
        # tries on every click.
        assert failed.attempts == 3

        # The proof that the clear MATTERS: the dispatcher can now see them.
        _batch_id, claimed, _seen = dispatcher._claim(
            tenant_id=brazos.id, channel=models.CHANNEL_PRINT, now=NOW, limit=500
        )
        assert len(claimed) == 2

    assert delivery_ops.AUDIT_REQUEUED in [row["action"] for row in audit_rows]


def test_us_not_013_tc4__a_held_row_is_never_requeued(brazos, dana):
    """US-NOT-013 TC-4, verbatim: *"Re-queue attempted on a HELD row (bad-address
    suppression) → Rejected with reason — held rows release only via address
    verification (BR-PAY-018), not re-queue."*

    A held row is a letter to an address the customer's own mail already came
    back from. Re-queueing it posts it there again.
    """
    with tenant_ctx(brazos):
        held = a_row(brazos, held=True, held_reason=delivery_ops.HELD_BAD_ADDRESS)
        outcome = delivery_ops.requeue(message_ids=(held.pk,), actor=dana)

        held.refresh_from_db()
        assert outcome.requeued == ()
        assert outcome.refused[0]["code"] == "held_row_not_requeueable"
        assert held.held is True


def test_us_not_013_a_sent_row_is_never_requeued(brazos, dana):
    """Forward-only, from the operator's side (BR-NOT-005). Re-queueing a `sent`
    row would be a SECOND copy of a message the customer already has, and the
    ratified door for a deliberate extra copy is a NEW row with `copy_no` > 0
    (US-NOT-011's re-send) — which records that a human asked for it."""
    with tenant_ctx(brazos):
        sent = a_row(brazos, status=models.STATUS_SENT, sent_at=NOW)
        outcome = delivery_ops.requeue(message_ids=(sent.pk,), actor=dana)
        assert outcome.refused[0]["code"] == "already_sent_not_requeueable"
        sent.refresh_from_db()
        assert sent.status == models.STATUS_SENT


def test_us_not_013_tc5__a_forged_row_id_from_another_tenant_is_refused(brazos, lonestar, dana):
    """US-NOT-013 TC-5: *"Re-queue via forged row ids from another tenant →
    Rejected — server-validated scope."* HR-1: a cross-tenant id is
    indistinguishable from an absent one, so the refusal says "not in this
    tenant" and never confirms the row exists elsewhere."""
    with tenant_ctx(lonestar):
        theirs = a_row(lonestar)
    with tenant_ctx(brazos):
        outcome = delivery_ops.requeue(message_ids=(theirs.pk,), actor=dana)
    assert outcome.requeued == ()
    assert outcome.refused[0]["code"] == "not_found_in_this_tenant"
    theirs.refresh_from_db()
    assert theirs.status == models.STATUS_QUEUED


# ── US-NOT-014 · returned mail ──────────────────────────────────────────────
def test_us_not_014_tc1_tc2__marking_returned_stamps_the_row_and_emits_the_event(
    brazos, dana, audit_rows
):
    """US-NOT-014 TC-1: *"Priya marks A-11455's bill letter returned → Queue row
    → returned state + `delivery.returned` audit; delivery-return event emitted;
    US-PAY-016 consumes → bad_address set."* TC-2: bulk, 14 letters.

    ⚠ THE EVENT IS RETURNED, NOT CONSUMED. `accounts.bad_address` is payments'
    column (r12 #8) and B1 forbids the cross-module write, so this asserts the
    event this module EMITS. A caller that ignores it leaves the account
    unflagged and no test here can catch that — REPORTED.

    The STATUS does not move, deliberately: a returned letter was genuinely
    sent, and overwriting that would destroy the fact an auditor needs.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        row = a_row(brazos, account_id=account.pk, status=models.STATUS_SENT, sent_at=NOW)

        events, refused = delivery_ops.mark_returned(message_ids=(row.pk,), at=NOW, actor=dana)

        row.refresh_from_db()
        assert refused == ()
        assert row.returned_at == NOW
        assert row.status == models.STATUS_SENT  # it WAS sent; that stays true
        assert len(events) == 1 and events[0].account_id == account.pk

        # Idempotent (TC-6): the same row twice emits no second event, so a
        # double-clicked bulk action never flags an account twice.
        again, _ = delivery_ops.mark_returned(message_ids=(row.pk,), at=NOW, actor=dana)
        assert again == ()

    assert delivery_ops.AUDIT_RETURNED in [entry["action"] for entry in audit_rows]


def test_us_not_014_tc6__an_email_row_cannot_be_marked_returned(brazos, dana):
    """US-NOT-014 TC-6: *"Mark-returned attempted on an email row → Rejected —
    paper-channel rows only."*

    An email that did not arrive comes back as a provider BOUNCE on a webhook —
    a fact from the ESP, not something a clerk can observe about an envelope.
    Letting staff mark one would put a hand-typed value where a provider's
    answer belongs.

    PROVED RED by deleting the channel check: an email row took a `returned_at`
    stamp and emitted a delivery-return event, so a clerk's guess would have
    flagged a customer's address as bad.
    """
    with tenant_ctx(brazos):
        row = a_row(brazos, channel=models.CHANNEL_EMAIL, recipient_address="x@example.test")
        events, refused = delivery_ops.mark_returned(message_ids=(row.pk,), at=NOW, actor=dana)
        row.refresh_from_db()

    assert events == ()
    assert refused[0]["code"] == "not_a_paper_row"
    assert row.returned_at is None


def test_us_not_014_tc3_tc4__paper_is_held_then_released_on_verification(brazos, dana, audit_rows):
    """US-NOT-014 TC-3: *"Suppression ON: next disconnect notice for A-11455 →
    Paper row written with HELD marker — dispatcher skips it; email/SMS rows
    unaffected; nothing lost."* TC-4: *"Address verified → Held rows released;
    next batch dispatches them; release audited."*

    The rows are KEPT throughout — written, held, released. Nothing is deleted
    and nothing is re-created, so the pin and the recipient snapshot the message
    was made with survive the whole round trip (BR-TEN-017).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11455b")
        paper = a_row(brazos, account_id=account.pk)
        email = a_row(
            brazos,
            account_id=account.pk,
            channel=models.CHANNEL_EMAIL,
            recipient_address="x@example.test",
        )

        assert delivery_ops.paper_suppression_active() is True  # S70 seed, read not assumed
        held_ids = delivery_ops.hold_paper_for_accounts(account_ids=(account.pk,), actor=dana)

        paper.refresh_from_db()
        email.refresh_from_db()
        assert held_ids == (str(paper.pk),)
        assert paper.held is True and email.held is False  # own rails, untouched

        # The dispatcher does not see it — the whole point of the marker.
        _batch, claimed, _seen = dispatcher._claim(
            tenant_id=brazos.id, channel=models.CHANNEL_PRINT, now=NOW, limit=500
        )
        assert claimed == []

        released = delivery_ops.release_held_for_accounts(account_ids=(account.pk,), actor=dana)
        paper.refresh_from_db()
        assert released == (str(paper.pk),)
        assert paper.held is False
        assert paper.status == models.STATUS_QUEUED  # nothing lost, nothing re-made

        _batch, claimed_after, _seen = dispatcher._claim(
            tenant_id=brazos.id, channel=models.CHANNEL_PRINT, now=NOW, limit=500
        )
        assert len(claimed_after) == 1

    actions = [entry["action"] for entry in audit_rows]
    assert delivery_ops.AUDIT_HELD in actions and delivery_ops.AUDIT_RELEASED in actions


def test_us_not_014_holding_refuses_when_the_tenant_switched_suppression_off(brazos, dana):
    """BR-PAY-018 makes the suppression CONFIG. A tenant with it OFF has chosen
    to keep posting; holding anyway would stop bills reaching customers the
    utility deliberately kept posting to, and nothing would say so."""
    from apps.tenancy import services as tenancy_services

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11455c")
        a_row(brazos, account_id=account.pk)
        tenancy_services.save_settings_family(
            dana, "collections", {"suppress_paper_on_bad_address": False}
        )
        assert delivery_ops.paper_suppression_active() is False
        with pytest.raises(delivery_ops.DeliveryOpsRefused, match="OFF"):
            delivery_ops.hold_paper_for_accounts(account_ids=(account.pk,), actor=dana)


# ── US-NOT-015 · the read-models and the deferred backlog ───────────────────
def test_us_not_015_tc2__the_returned_mail_read_model_feeds_the_canned_report(brazos, dana):
    """US-NOT-015 TC-2: *"The A-11455 return events + flagged-account linkage
    surface for the canned report (read-only)."* TC-5 is the reason it is a
    FUNCTION: *"Reports module attempts a direct SELECT on `outbound_messages` →
    Forbidden — cross-module reads via service functions only."*"""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11455d")
        row = a_row(brazos, account_id=account.pk, status=models.STATUS_SENT, sent_at=NOW)
        delivery_ops.mark_returned(message_ids=(row.pk,), at=NOW, actor=dana)

        feed = delivery_ops.returned_mail_read_model()

    assert len(feed) == 1
    assert feed[0]["account_id"] == str(account.pk)
    assert feed[0]["returned_at"] == NOW
    # BR-AUD-006's posture on a report feed: an identifier, never a name.
    assert "customer_name" not in feed[0]


def test_us_not_015_tc6__a_deferred_email_row_is_never_shown_as_sent(brazos):
    """US-NOT-015 TC-6: *"Scheduled-report email requested in v1 with expectation
    of delivery → Row queues deferred; no false 'sent' status ever shown."*

    On this deployment that is true of EVERY channel, not only the deferred
    ones: nothing dispatches at all (PO ruling 2026-08-15). The backlog count is
    what a dashboard badges, and it counts what is actually there.
    """
    with tenant_ctx(brazos):
        a_row(
            brazos,
            source_type="report",
            channel=models.CHANNEL_EMAIL,
            recipient_address="priya@brazosbend.example",
        )
        a_row(
            brazos,
            source_type="ledger",
            channel=models.CHANNEL_EMAIL,
            recipient_address="books@brazosbend.example",
        )
        a_row(brazos)

        backlog = delivery_ops.deferred_backlog()
        health = delivery_ops.queue_health(source_type="report")

    assert backlog[models.CHANNEL_EMAIL] == 2
    assert backlog[models.CHANNEL_PRINT] == 1
    assert health.totals == {models.STATUS_QUEUED: 1}
    assert health.totals.get(models.STATUS_SENT, 0) == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-013@6c2a90f (the four sources — EP-NOT-04 US-NOT-013/014/015 §1/§3/§5 · 10-notifications/02-business-rules.md · 04-flows.md §4 + §6 · J18-returned-mail-tuesday.md + J17-delivery-life.md)
# generated: 2026-08-15 by story-coder (W3/W4 notifications CONTENT lane — delivery ops)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S8 dashboard endpoints are not in this lane) E=deferred(no-frontend-half — S8 lives under features/tenancy/, which this lane may not touch; REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · THREE guards proved RED before green (hard-won law 7) —
#         the `batch_id` clear (a crashed-claim row stayed invisible to the
#         dispatcher while every screen said it had been re-queued), the
#         held-row refusal, and the paper-only mark-returned. Transcripts in the
#         lane report
# exceptions: (1) `delivered` AND `bounced` ARE NEVER PRODUCED by anything in
#         this repo — provider facts, no adapter, delivery out of this release by
#         PO ruling. A case asserts the read-model REPORTS that rather than
#         showing zero.
#         (2) THE DELIVERY-RETURN EVENT IS ASSERTED AS EMITTED, NOT CONSUMED —
#         `accounts.bad_address` is payments' column and B1 forbids the write. A
#         caller that drops the event leaves the account unflagged and no test
#         here catches it. REPORTED.
#         (3) `dispatcher._claim` IS CALLED DIRECTLY in two cases, deliberately:
#         a full `dispatch_cycle` stops at the missing provider adapter before
#         selection tells us anything, and what these cases must prove is which
#         rows the dispatcher can SEE.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
