# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-025 (the payments→queue consumer) × US-NOT-017 (SET-12 /
#           SET-12D, the rule) × US-PAY-009 TC-4 (the returned-payment letter)
#           CR-048 wave B, tasks B1 (payments half) + B3
#           Screens: S22 (record payment) · S33 (reverse) · S8 · SET-12D
# Rules:    BR-NOT-017 (ONE HOME for every notification rule — and, from CR-048,
#           one place that READS it) · BR-NOT-018 (an event this platform cannot
#           fire is named, never guessed) · BR-PAY-024 (a receipt is auto-queued
#           on a recorded payment) · BR-NOT-022 (the A15 receipt election ships
#           DEFAULT ON) · BR-PAY-013 (the bounce, and the customer's letter) ·
#           BR-NOT-005 (queue only; nothing here sends) · BR-NOT-013 (no
#           provider adapter on any channel) · CLAUDE.md rule 6 (idempotency) ·
#           rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""Payments names its two events, so the settings screen finally decides something.

CR-048's headline is that **the queue never read the notification rule**. Wave A
made `queue_document` read it — but only for a caller that NAMES the event, and
on the day A1 landed every writer in the product still passed a source type and
nothing else. Its own trailer says so: *"THE JOIN IS BUILT AND NOTHING FEEDS IT
YET … the settings screen is still decoration until CR-048 wave B."*

This file is payments' half of the feeding, and its four sections are the four
things that had to stay true.

────────────────────────────────────────────────────────────────────────────
WHY AN EVENT KEY AND NOT A GUESS FROM `source_type`
────────────────────────────────────────────────────────────────────────────
`source_type` is one-to-MANY onto events: `payment` is `payment_received` OR
`payment_failed`, two different rows on SET-12 with two different sets of
switches. Deriving one from the other would answer a utility with a question
they were never asked. So each call site says which it is, from a fact payments
already holds — **money being recorded** is `payment_received`, and **a payment
that came back with reason `nsf`** is `payment_failed`. Neither is a new flag.

────────────────────────────────────────────────────────────────────────────
THE RED PROOF (hard-won law 7), RUN BEFORE ANY OF THIS WAS TRUSTED GREEN
────────────────────────────────────────────────────────────────────────────
`test_cr048_b3__switching_payment_received_email_off_stops_the_email_receipt`
was run against a `receipts.py` whose queue call omitted `event_key` — the state
of the world before B1 — and it FAILED, on the email row queued in spite of a
utility that had switched *Payment received — email* off. The failure is quoted
in the lane report. The event key is what closes it, and removing that one
argument turns this file red again.

NOTHING HERE SENDS. Every row rests `queued` (BR-NOT-013).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import connection

from apps.notifications import models as notification_models
from apps.notifications import rule_catalog, rule_service
from apps.notifications import services as notification_services
from apps.payments import models as payment_models
from apps.payments import notices, receipts, reversal
from apps.payments import services as payment_services

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 18, 10, 30, tzinfo=UTC)
RETURNED_ON = datetime(2026, 8, 29, 11, 15, tzinfo=UTC)
#: OQ-205's own worked figure (PMT-2608-0455), reused so the numbers in this
#: file and in `test_cr_009_c13_a15_toggles.py` are the same payment.
AMOUNT = Decimal("247.30")

EMAIL = notification_models.CHANNEL_EMAIL
PRINT = notification_models.CHANNEL_PRINT
#: ⚠ **ADDED 2026-08-30 — CR-048 wave B task B11.** `payment_received` gained a
#: THIRD surface, and deliberately not a third EVENT: *"the payment receipt now
#: also goes by text as well as by post and email"*. `sms_payment_received` sits
#: beside `email_payment_receipt` on the one event exactly as `sms_bill_ready`
#: sits beside `email_bill_ready` on `bill_ready`, because a text is not a
#: different MOMENT — minting `payment_received_sms` would have put a second row
#: on SET-12 for one thing that happens, and a utility switching *Payment
#: received* off would then have to find and switch off a second row to stop
#: being in touch about it.
SMS = notification_models.CHANNEL_SMS


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


def _rows(tenant, *, channel=None, source_id=None):
    """The queue, as a dispatcher would find it."""
    query = notification_models.OutboundMessage.objects.filter(
        tenant_id=tenant.pk, source_type="payment"
    )
    if channel is not None:
        query = query.filter(channel=channel)
    if source_id is not None:
        query = query.filter(source_id=source_id)
    return query


def _switch(actor, event_key, channel, *, on):
    """Do to the rule exactly what a System Admin does on SET-12D.

    Through `rule_service.update_rule` — the ONE write path into the rule
    tables — never through the ORM, so these cases exercise the same stored
    state the screen produces and cannot drift from it.
    """
    return rule_service.update_rule(
        event_key=event_key, actor=actor, channels={channel: {"enabled": on}}
    )


def _codes(result):
    return {problem["code"] for problem in result.problems}


# ══════════════════════════════════════════════════════════════════════════
# 0 · THE VOCABULARY IS READ, NEVER SPELLED (BR-NOT-018)
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b3__the_two_event_keys_payments_fires_exist_in_the_catalogue():
    """A key this platform cannot fire is refused at the queue by name, so a
    typo in payments would be a refusal on a live payment rather than a wrong
    send. This asserts the spelling against the catalogue itself — the only
    place events are defined — so a rename there goes RED here and not in
    production.

    ⚠ **AMENDED 2026-08-30 — `payment_received` OFFERS TWO CHANNELS NOW, NOT
    ONE (CR-048 wave B task B11).** This asserted `channels == (EMAIL,)` and the
    answer is `(EMAIL, SMS)`. See the `SMS` constant above for why the text
    joined the EXISTING event rather than getting one of its own.
    """
    assert receipts.EVENT_PAYMENT_RECEIVED in rule_catalog.EVENT_KEYS
    assert receipts.EVENT_PAYMENT_FAILED in rule_catalog.EVENT_KEYS
    # …and the channels each event actually offers, because the call sites below
    # ask for exactly those and nothing else.
    assert rule_catalog.EVENTS_BY_KEY[receipts.EVENT_PAYMENT_RECEIVED].channels == (EMAIL, SMS)
    assert EMAIL in rule_catalog.EVENTS_BY_KEY[receipts.EVENT_PAYMENT_FAILED].channels


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE POINT OF THE TASK — the switch decides, and the money is untouched
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b3__switching_payment_received_email_off_stops_the_email_receipt(
    brazos, marcus, dana
):
    """CR-048's headline, on payments: *"switching an event's email off on the
    settings screen changes nothing at all"*.

    A System Admin switches *Payment received — email* off. A clerk records
    $247.30. **No email row is written — and the payment is recorded anyway**,
    which is the half that matters more: a notification setting is not allowed
    to have an opinion about whether money was taken.

    THE RED PROOF: run with `event_key` removed from `receipts._queue_one` and
    this fails on `1 != 0` — the email row queued in spite of the switch.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        _switch(dana, receipts.EVENT_PAYMENT_RECEIVED, EMAIL, on=False)

        result = _record(marcus, account)

        assert result.created is True, "the payment must record whatever the rule says"
        assert _rows(brazos, channel=EMAIL, source_id=result.payment_id).count() == 0
        # Not queued means NOT QUEUED — no row, not a row carrying a reason. A
        # row would be a message waiting for a dispatcher that must never take
        # it, which is a different failure from the one this closes.
        assert _rows(brazos, channel=PRINT, source_id=result.payment_id).count() == 1

    # …and the suppression is REPORTED. A rule obeyed so quietly that nobody can
    # say why a customer with an email address got no email is the opposite
    # failure, and S22's result panel groups on these codes.
    suppressed = [
        problem
        for problem in result.problems
        if problem["code"] == notification_services.QUEUE_CHANNEL_SWITCHED_OFF
    ]
    assert suppressed, _codes(result)
    assert suppressed[0]["channel"] == EMAIL
    assert suppressed[0]["event_key"] == receipts.EVENT_PAYMENT_RECEIVED
    assert "Settings → Notifications" in suppressed[0]["detail"]


def test_cr048_b3__with_the_switch_on_a_recorded_payment_queues_both_receipts(brazos, marcus):
    """The other half, and it is what makes the case above non-vacuous: with the
    utility's shipped default the SAME payment queues an email row.

    Two rows, two templates, one event. The print row is BR-PAY-024's own
    document and the email row is the one SET-12 governs — and they carry
    DIFFERENT template codes, because a queue write pins one template for every
    channel it names and an email pinned to the print class would render the
    wrong document.

    ⚠ **AMENDED 2026-08-30 — THERE ARE THREE ROWS NOW (CR-048 wave B task
    B11).** The receipt also goes by text, on the SAME event, so `_record`
    queues print · email · sms and the set assertion moved from two to three.
    **The three-template rule is what the case was really pinning and it now has
    a third case to prove it on:** the idempotency key is `(tenant, source_type,
    source_id, channel, copy_no)` and all three share the first three, so the
    CHANNEL is the only thing separating them — which is exactly why each must
    carry its own class and an SMS pinned to the print body would text a
    customer a letter.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        result = _record(marcus, account)

        rows = {row.channel: row for row in _rows(brazos, source_id=result.payment_id)}

    assert set(rows) == {PRINT, EMAIL, SMS}
    assert rows[PRINT].template_code == receipts.RECEIPT_TEMPLATE_CODE
    assert rows[EMAIL].template_code == receipts.EMAIL_RECEIPT_TEMPLATE_CODE
    assert rows[SMS].template_code == receipts.SMS_RECEIPT_TEMPLATE_CODE
    # Three documents about one payment, three DISTINCT classes — never two rows
    # sharing a body.
    assert len({row.template_code for row in rows.values()}) == 3
    # Queueing is not sending (BR-NOT-013): all three rows rest.
    assert {row.status for row in rows.values()} == {"queued"}
    assert {
        receipts.RECEIPT_QUEUED,
        receipts.RECEIPT_EMAIL_QUEUED,
        receipts.RECEIPT_SMS_QUEUED,
    } <= _codes(result)


def test_cr048_b3__the_print_receipt_survives_the_event_being_switched_off_entirely(
    brazos, marcus, dana
):
    """SET-12's master toggle turns off what a utility may turn off.

    `payment_received` has no PRINT switch — the platform prints a receipt
    because BR-PAY-024 says so, not because a utility asked — so switching the
    whole notification off stops the email and leaves the paper. Suppressing an
    unruled channel would remove a document nobody could ever switch back on."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        rule_service.update_rule(
            event_key=receipts.EVENT_PAYMENT_RECEIVED, actor=dana, enabled=False
        )
        result = _record(marcus, account)

        assert _rows(brazos, channel=PRINT, source_id=result.payment_id).count() == 1
        assert _rows(brazos, channel=EMAIL, source_id=result.payment_id).count() == 0
    assert result.created is True


# ══════════════════════════════════════════════════════════════════════════
# 2 · A PAYMENT IS NEVER LOST TO A NOTIFICATION PROBLEM
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b3__a_rule_read_that_raises_cannot_fail_the_payment(brazos, marcus, monkeypatch):
    """A1 put a tenant-table READ between a clerk pressing *Record* and the money
    being recorded. This is the guard that it cannot cost a payment.

    The rule read is made to raise the way a bug in it would — not the owner's
    own `QueueWriteRefused`, which was already caught, but an ordinary
    `RuntimeError` that the old narrow `except` re-raised straight through the
    money path."""

    def explode(_event_key):
        raise RuntimeError("the rule read is broken (test)")

    monkeypatch.setattr(rule_service, "channel_switches", explode)
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        result = _record(marcus, account)
        recorded = payment_models.Payment.objects.filter(pk=result.payment_id).count()

    assert result.created is True
    assert recorded == 1, "the money is recorded; the notification is the thing that failed"
    assert receipts.RECEIPT_QUEUE_ERROR in _codes(result)
    assert "the rule read is broken" in " ".join(p.get("detail", "") for p in result.problems)


@requires_postgres
def test_cr048_b3__a_database_error_in_the_rule_path_cannot_fail_the_payment(
    brazos, marcus, monkeypatch
):
    """⚠ THIS CASE ONLY MEANS ANYTHING ON POSTGRESQL, and that is the finding.

    A statement that errors inside a Postgres transaction ABORTS the whole
    transaction: catching the exception is not enough, because the payment's own
    INSERT is already doomed and the COMMIT fails afterwards with *"current
    transaction is aborted"*. SQLite has no such state, so a `try/except` alone
    passes there and loses money here.

    So the queue write is wrapped in its OWN savepoint. This drives a real
    database error out of the rule path and asserts the payment still commits —
    which is the only way to prove the savepoint is doing the work rather than
    the `except`."""

    def bad_sql(_event_key):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 / 0")

    monkeypatch.setattr(rule_service, "channel_switches", bad_sql)
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        result = _record(marcus, account)

    with tenant_ctx(brazos):
        # Read it back in a NEW transaction: the point is that it committed.
        assert payment_models.Payment.objects.filter(pk=result.payment_id).count() == 1
    assert result.created is True
    assert receipts.RECEIPT_QUEUE_ERROR in _codes(result)


def test_cr048_b3__a_queue_refusal_is_still_told_apart_from_a_fault(brazos, marcus, monkeypatch):
    """Broadening the catch must not blur the two answers. A refusal is the
    queue saying no for a reason a human can act on; a fault is a bug. They
    carry different codes so a screen and a report can group on the
    difference."""

    def refuse(**_kwargs):
        raise notification_services.QueueWriteRefused("the queue is on fire (test)")

    monkeypatch.setattr(notification_services, "queue_document", refuse)
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        result = _record(marcus, account)

    assert result.created is True
    assert receipts.RECEIPT_QUEUE_REFUSED in _codes(result)
    assert receipts.RECEIPT_QUEUE_ERROR not in _codes(result)


# ══════════════════════════════════════════════════════════════════════════
# 3 · IDEMPOTENCY STILL HOLDS (CLAUDE.md rule 6)
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b3__a_replayed_record_queues_no_second_row_on_either_channel(brazos, marcus):
    """The queue is keyed `(tenant, source_type, source_id, channel, copy_no)`,
    and B3 added a channel under the same source id. A double click must still
    cost two rows in total, not four — asserted per channel, because a count
    over both would pass on one channel doubling while the other lost a row."""
    key = str(uuid.uuid4())
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        first = _record(marcus, account, idempotency_reference=key)
        again = _record(marcus, account, idempotency_reference=key)

        assert again.created is False
        assert again.payment_id == first.payment_id
        assert _rows(brazos, channel=PRINT, source_id=first.payment_id).count() == 1
        assert _rows(brazos, channel=EMAIL, source_id=first.payment_id).count() == 1


def test_cr048_b3__the_bounce_letter_does_not_collide_with_the_email_receipt(brazos, marcus, dana):
    """The letter is keyed on the REVERSING row and not on the original, and this
    is the case that says why.

    The original payment already owns an `email` row under its own id — its
    emailed receipt. Keying the bounce letter on the original would produce the
    same tuple, so the letter would silently dedupe INTO the receipt: one row,
    the wrong document, nothing anywhere reporting a problem. Two ids, two rows,
    two templates."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        recorded = _record(marcus, account)
        bounce = reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=RETURNED_ON,
            reason=payment_models.REVERSAL_REASON_NSF,
            idempotency_reference=str(uuid.uuid4()),
        )

        receipt_row = _rows(brazos, channel=EMAIL, source_id=recorded.payment_id).get()
        letter_row = _rows(brazos, channel=EMAIL, source_id=bounce.reversal_id).get()

    assert receipt_row.pk != letter_row.pk
    assert receipt_row.template_code == receipts.EMAIL_RECEIPT_TEMPLATE_CODE
    assert letter_row.template_code == receipts.FAILED_PAYMENT_TEMPLATE_CODE


# ══════════════════════════════════════════════════════════════════════════
# 4 · `payment_failed` — the returned-payment letter
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b3__an_nsf_bounce_queues_the_returned_payment_letter(brazos, marcus, dana):
    """US-PAY-009 TC-4's queue half, which `REVERSE_UNAVAILABLE` reported as
    missing since 2026-08-11: *"nothing is queued and nothing is sent"*.

    One email row on the reversing payment's own id, template
    `email_payment_failed`, resting queued."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        recorded = _record(marcus, account)
        bounce = reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=RETURNED_ON,
            reason=payment_models.REVERSAL_REASON_NSF,
            idempotency_reference=str(uuid.uuid4()),
        )
        row = _rows(brazos, channel=EMAIL, source_id=bounce.reversal_id).get()

    assert row.template_code == receipts.FAILED_PAYMENT_TEMPLATE_CODE
    assert row.status == "queued"
    codes = {problem["code"] for problem in bounce.problems}
    assert receipts.FAILED_NOTICE_QUEUED in codes
    # The claim that USED to ride every bounce is gone, because it is now false.
    assert "no_nsf_notice_queued" not in codes


def test_cr048_b3__switching_payment_failed_email_off_stops_the_letter_not_the_bounce(
    brazos, marcus, dana
):
    """The same proof as section 1, on the second event: a utility that has
    switched *Payment failed — email* off gets no letter, and the money still
    comes back — the reversing row, its allocations and the ledger mirror are
    exactly what they would have been.

    ⛔ **THIS CASE IS RED ON PURPOSE AND IT IS NOT A STALE ASSERTION — IT IS
    `DEF-2473`, FILED 2026-08-30.** Read this before "fixing" the assertion.

    `queue_failed_payment_notice` asks `_queue_one` for ONE channel — email,
    template `email_payment_failed` — and BR-NOT-024's print floor (PO
    2026-08-29, *"don't switch of print for any document it is awayls on"*)
    adds `pdf_print` to the SAME queue write. Measured on the branch tip with
    the email switch OFF: **one row, channel `pdf_print`, template_code
    `email_payment_failed`, status `queued`.** So two things are wrong and the
    line below catches the second of them:

      1. a PRINTED letter is pinned to an EMAIL class — the receipt path one
         function up gets this right, calling `_queue_one` once per channel with
         `receipt` / `email_payment_receipt` / `sms_payment_received`, and the
         bounce path was never given the same treatment;
      2. `_queue_one` reports `queued_code` with `channel=email` whenever ANY
         row was written, so this utility's outcome carries
         `payment_failed_notice_queued channel=email` **beside**
         `channel_switched_off_by_rule channel=email`, with no email row in the
         table. S22's result panel groups on exactly these codes.

    The assertion is left exactly as written, because it is correct: with email
    switched off, no `payment_failed_notice_queued` **for email** should be
    reported. Making it green would mean either weakening the case or changing
    payments' queue behaviour — a money-adjacent path, and the print class the
    real fix needs does not exist in `catalogs.LISTINGS` yet. Both halves and a
    proposed patch are on the defect row.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        recorded = _record(marcus, account)
        _switch(dana, receipts.EVENT_PAYMENT_FAILED, EMAIL, on=False)

        bounce = reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=RETURNED_ON,
            reason=payment_models.REVERSAL_REASON_NSF,
            idempotency_reference=str(uuid.uuid4()),
        )

        assert bounce.created is True
        assert bounce.journal_entry_id, "the bounce reached the books"
        assert _rows(brazos, channel=EMAIL, source_id=bounce.reversal_id).count() == 0

    codes = {problem["code"] for problem in bounce.problems}
    assert notification_services.QUEUE_CHANNEL_SWITCHED_OFF in codes
    assert receipts.FAILED_NOTICE_QUEUED not in codes


def test_cr048_b3__a_staff_reversal_is_not_a_failed_payment_and_writes_no_letter(
    brazos, marcus, dana
):
    """The event is decided by the REVERSAL REASON — the same fact that already
    decides whether BR-PAY-013's count runs — and not by a flag invented for
    this change.

    A staff-initiated reversal is our correction, not the customer's payment
    failing, and a letter would tell them about a fault they do not have. Today
    only `nsf` has a write path (US-PAY-010 is unbuilt), so this asserts the
    boundary at the only place it can be observed: the reason on the reversing
    row is what the notice path reads."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        recorded = _record(marcus, account)
        for reason in payment_models.REVERSAL_REASONS:
            if reason == payment_models.REVERSAL_REASON_NSF:
                continue
            with pytest.raises(Exception):  # noqa: B017 — refused by name, US-PAY-010
                reversal.reverse_payment(
                    dana,
                    payment_id=recorded.payment_id,
                    returned_on=RETURNED_ON,
                    reason=reason,
                    idempotency_reference=str(uuid.uuid4()),
                )
        # No reversing row exists, so no letter can: the boundary holds by
        # construction while the other three reasons have no path.
        assert _rows(brazos, channel=EMAIL).exclude(source_id=recorded.payment_id).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# 5 · A CALL SITE WITH NO EVENT IS BYTE-IDENTICAL TO TODAY
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b3__a_payments_call_site_that_names_no_event_is_untouched(brazos, marcus, dana):
    """`notices.send_disconnect_notices` still passes a source type and no
    event, and must behave exactly as it did — B10/B11 own the events those
    documents will one day name, and `payment_received` is emphatically not one
    of them.

    ⚠ RE-POINTED 2026-10-29 (`DEF-PAY-10651`). This case used
    `send_reminders`, which now reads its own rule (`past_due_reminder`, PO
    ruling 1A) and so is no longer a writer that names no event. Its source
    filter also read `source_id=account.pk`, which no collections notice has
    used since `DEF-PAY-4357` keyed them on the occasion.

    Proved the way it can actually go wrong: the `payment_received` email switch
    is turned OFF, and the notice is queued regardless, because nothing on
    that path reads a rule at all."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        _switch(dana, receipts.EVENT_PAYMENT_RECEIVED, EMAIL, on=False)

        result = notices.send_disconnect_notices(
            account_ids=(account.pk,),
            tier="first_10_day",
            cut_date=POSTED_AT.date(),
            on_date=POSTED_AT.date(),
            channels=(PRINT, EMAIL),
            actor=marcus,
        )

        rows = notification_models.OutboundMessage.objects.filter(
            tenant_id=brazos.pk,
            source_type="notice",
            source_id=notices.ladder_notice_source_id(account.pk, "disconnect", "first_10_day"),
        )
        assert {row.channel for row in rows} == {PRINT, EMAIL}

    assert len(result.sent) == 1
    # No rule was consulted, so none of the join's codes can appear.
    codes = {problem["code"] for problem in result.problems}
    assert notification_services.QUEUE_CHANNEL_SWITCHED_OFF not in codes
    assert notification_services.QUEUE_CHANNEL_UNRULED not in codes


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 B1+B3 (12-governance/11-change-requests.md → CR-048 step 5 wave B · apps/notifications/rule_catalog.py EVENTS · apps/notifications/services.channel_decision + queue_document · apps/payments/receipts.py · apps/payments/reversal.py)
# generated: 2026-08-29 by the CR-048 payments lane
# checklist: A✔ B=n/a(no new HTTP surface — record_payment and reverse_payment carry the outcome rows on their existing results) C✔ D=deferred(no-frontend-half — S22's problem list already renders these codes) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST and quoted in the lane report — the section-1 case was run against a receipts.py with `event_key` removed and failed on the email row queued in spite of the switch; the section-2 Postgres case was run without the savepoint and failed the payment outright with "current transaction is aborted".
# exceptions: (1) THE `notice_history` HALF OF US-PAY-009 TC-4 IS NOT ASSERTED because it is not built — NOTICE_TYPES has no member for a returned payment and minting one would define a collections notice type from inside a bounce. It rides every bounce as `no_nsf_notice_history_row`. (2) THE STAFF-REVERSAL CASE asserts the boundary by construction rather than behaviourally, because only `nsf` has a write path today (US-PAY-010 unbuilt); when the other three reasons gain one, that case gains a real assertion.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
