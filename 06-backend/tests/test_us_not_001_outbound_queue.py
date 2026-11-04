# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-001 (`outbound_messages` — the platform-wide queue table)
#           Screens: S8 · S30 · S35
# Rules:    BR-NOT-005 (every message from any module is a queue row FIRST;
#           statuses queued→sent→delivered/failed/bounced) · BR-BIL-016 (one
#           delivery record per document per channel) · BR-BIL-036 (print is the
#           primary channel; an account with NO email address is normal, not an
#           exception) · BR-NOT-006 (language rides the template pin) ·
#           BR-TEN-017 (the recipient is snapshotted, never re-resolved) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency)
# ───────────────────────────────────────────────────────
"""The platform outbound queue: the shape of the table, and the two laws on it.

WHAT RUNS WHERE, stated because it changes what these tests are worth. The unit
test database is SQLite, which has no row-level security. So:

  * SHAPE and CONSTRAINTS (this file) run everywhere — the idempotency key, the
    address-or-reason completeness check, the pinned template tuple, the
    channel independence that keeps a missing email off the print row.
  * TENANT ISOLATION is `tests/test_us_not_001_outbound_isolation.py`, against
    live Postgres under a non-superuser probe role.

Both laws under test here are ones a passing suite could easily fake. The
idempotency case therefore asserts the DATABASE refuses the duplicate, not that
some helper declined to write it — US-NOT-001 TC-5 is about a job retry, and a
job retry does not call the helper twice with a flag set.
"""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction

from apps.notifications import models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def an_account(actor, tenant, *, account_no="ACC-1042"):
    """A minimal account. Built through customers' own service would drag in
    the whole activation path; this test is about the queue table."""
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line="1901 Bluestem Ln")
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    status = customer_models.AccountStatus.objects.filter(tenant=tenant).first()
    account_type = customer_models.AccountType.objects.first()
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=status,
        account_type=account_type,
        account_no=account_no,
    )


def a_bill_row(tenant, *, invoice_id, channel, account=None, **overrides):
    """The row a bill release writes for one bill on one channel.

    Deliberately built from the model rather than from a service: there is no
    queue-write service in this slice (module writers own their own write
    paths), and the guarantees under test are the table's own.
    """
    values = dict(
        tenant=tenant,
        account=account,
        source_type="invoice",
        source_id=invoice_id,
        channel=channel,
        template_code="bill_residential",
        template_id=uuid4(),
        template_version=3,
        template_language="en-US",
        recipient_address="sarah.chen@example.test",
        recipient_snapshot={
            "name": "Sarah Chen",
            "address": "1901 Bluestem Ln, Unit A, Katy TX 77494",
        },
    )
    values.update(overrides)
    return models.OutboundMessage.objects.create(**values)


# ── rule 6: a re-release never queues a second copy ─────────────────────────
def test_us_not_001_tc5__re_releasing_a_bill_cannot_queue_a_second_copy(brazos, dana):
    """CLAUDE.md rule 6 · US-NOT-001 TC-5 · BR-BIL-016 ("one delivery record per
    document per channel").

    The scenario is not a user double-clicking. It is a background job that
    crashed after committing its rows and got retried, or a release re-run after
    a partial failure — the shapes CLAUDE.md rule 6 exists for. The second write
    must be refused by the DATABASE, because the retry does not go through
    whatever guard the first write used.

    A duplicate here is not a cosmetic defect: it is a second paper bill in the
    post from the print vendor, at the vendor's per-piece price, and a customer
    calling to ask which one they owe.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()

        first = a_bill_row(brazos, invoice_id=invoice_id, channel="pdf_print", account=account)
        assert first.status == models.STATUS_QUEUED  # BR-NOT-005 — rests queued
        assert first.copy_no == 0  # the delivery record, not a copy

        with pytest.raises(IntegrityError), transaction.atomic():
            a_bill_row(brazos, invoice_id=invoice_id, channel="pdf_print", account=account)

        assert models.OutboundMessage.objects.filter(source_id=invoice_id).count() == 1


def test_us_not_001_tc5b__the_key_is_per_channel_and_per_source(brazos, dana):
    """The same guarantee's other half: it must not over-fire.

    One bill legitimately produces one row PER CHANNEL (BR-BIL-016), and the
    next bill in the same run is a different source. A key that collapsed either
    of those would silently drop real messages — the failure mode that looks
    like success on a dashboard.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id, other_invoice_id = uuid4(), uuid4()

        # ⚠ AMENDED 2026-08-17 (CR-009 in-app lane): the loop was over
        # `models.CHANNELS` and a fourth channel arrived (BR-NOT-019), which
        # would have made this read "one bill goes out on four channels" —
        # a bill does not. THE THREE CHANNELS A DOCUMENT GOES OUT ON are named
        # explicitly here now, because that is what this test is about:
        # BR-BIL-016's one-row-per-document-per-channel. `in_app` carries a
        # message to a member of STAFF and no bill is ever addressed to one.
        for channel in (models.CHANNEL_PRINT, models.CHANNEL_EMAIL, models.CHANNEL_SMS):
            a_bill_row(brazos, invoice_id=invoice_id, channel=channel, account=account)
        a_bill_row(brazos, invoice_id=other_invoice_id, channel="pdf_print", account=account)

        assert models.OutboundMessage.objects.filter(source_id=invoice_id).count() == 3
        assert models.OutboundMessage.objects.count() == 4

        # …and a different SOURCE KIND sharing an id is still its own message:
        # source_type is part of the key because ids are only unique per table.
        a_bill_row(
            brazos,
            invoice_id=invoice_id,
            channel="pdf_print",
            account=account,
            source_type="payment",
            template_code="receipt",
        )
        assert models.OutboundMessage.objects.count() == 5


def test_us_not_001_tc5c__a_deliberate_resend_is_a_new_row_a_replay_is_not(brazos, dana):
    """US-NOT-011 §5 ("Receipt re-send … new queue rows, audited") against
    US-NOT-001 TC-5 (a replay makes none) — the two ratified behaviours that
    `copy_no` exists to keep apart.

    A customer ringing up to ask for another copy of their bill is a real
    request that must produce a real message. A job retry is not. Without the
    discriminator, honouring the first makes the second impossible to refuse.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()
        a_bill_row(brazos, invoice_id=invoice_id, channel="pdf_print", account=account)

        # The customer asks for another copy: a NEW row, numbered.
        resend = a_bill_row(
            brazos, invoice_id=invoice_id, channel="pdf_print", account=account, copy_no=1
        )
        assert resend.copy_no == 1
        assert models.OutboundMessage.objects.filter(source_id=invoice_id).count() == 2

        # The re-send is itself idempotent — asking twice for copy 1 is still
        # copy 1. Only an explicit next number is a further copy.
        with pytest.raises(IntegrityError), transaction.atomic():
            a_bill_row(
                brazos, invoice_id=invoice_id, channel="pdf_print", account=account, copy_no=1
            )


# ── BR-BIL-036: no email is normal, and it is recorded ──────────────────────
def test_us_not_001_tc7__a_bill_with_no_email_still_queues_its_print_row(brazos, dana):
    """BR-BIL-036, from the PO's closure of OQ-091:

        PRINT is the primary delivery channel; email and SMS are NOTIFICATIONS
        of the amount, not a replacement for the document. […] An account with
        NO email address is normal, not an exception — delivery must never
        assume one exists, and such an account still bills, still renders and
        still dispatches.

    So the print row is complete and untouched, and the email row exists and
    SAYS why it has no address. What must not happen is the shape this test
    would have missed a year from now: the release code wrapping both writes in
    one try block, the email write failing, and the paper bill never going out.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()

        print_row = a_bill_row(
            brazos,
            invoice_id=invoice_id,
            channel=models.CHANNEL_PRINT,
            account=account,
            recipient_address="1901 Bluestem Ln, Unit A\nKaty TX 77494",
        )
        email_row = a_bill_row(
            brazos,
            invoice_id=invoice_id,
            channel=models.CHANNEL_EMAIL,
            account=account,
            recipient_address=None,
            unavailable_reason=models.REASON_NO_EMAIL,
        )

        # The print row is whole: addressed, pinned, queued. Nothing about the
        # missing email reached it — the two rows share no column that could
        # have carried the failure.
        print_row.refresh_from_db()
        assert print_row.status == models.STATUS_QUEUED
        assert print_row.recipient_address.startswith("1901 Bluestem Ln")
        assert print_row.unavailable_reason is None
        assert print_row.template_id is not None and print_row.template_version == 3

        # The absence is a RECORD, not a silence: it is on a row, it names its
        # reason, and the dashboard can count it.
        email_row.refresh_from_db()
        assert email_row.recipient_address is None
        assert email_row.unavailable_reason == "no_email_address"
        assert (
            models.OutboundMessage.objects.filter(unavailable_reason=models.REASON_NO_EMAIL).count()
            == 1
        )


def test_us_not_001_tc7b__a_row_can_never_carry_neither_address_nor_reason(brazos, dana):
    """The completeness check that makes "silently dropped" unrepresentable.

    A row with no address and no reason is exactly what a swallowed exception
    leaves behind: it looks queued, it will never be delivered, and nothing on
    any screen says why. `ck_outbound_msgs_address_or_reason` refuses it, so the
    only way to record a message with no destination is to say what is missing.

    The mirror case is refused too — an address AND a reason is a contradiction
    about the same row, and one of the two would be believed by some later
    reader.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)

        with pytest.raises(IntegrityError), transaction.atomic():
            a_bill_row(
                brazos,
                invoice_id=uuid4(),
                channel=models.CHANNEL_EMAIL,
                account=account,
                recipient_address=None,  # neither…
                unavailable_reason=None,  # …nor
            )

        with pytest.raises(IntegrityError), transaction.atomic():
            a_bill_row(
                brazos,
                invoice_id=uuid4(),
                channel=models.CHANNEL_EMAIL,
                account=account,
                recipient_address="sarah.chen@example.test",  # both
                unavailable_reason=models.REASON_NO_EMAIL,
            )


def test_us_not_001_tc7c__sms_without_an_opt_in_records_the_same_way(brazos, dana):
    """A15 ("SMS requires opt-in") and BR-BIL-036 are the same shape of fact:
    a channel the platform cannot use for this customer right now.

    Recording it identically means the dispatch home answers "why did 47
    accounts get no text?" from the queue itself, instead of from a join
    against a preference table that may have changed since.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        row = a_bill_row(
            brazos,
            invoice_id=uuid4(),
            channel=models.CHANNEL_SMS,
            account=account,
            recipient_address=None,
            unavailable_reason=models.REASON_NO_SMS_OPT_IN,
        )
        assert row.unavailable_reason in models.UNAVAILABLE_REASONS
        assert row.status == models.STATUS_QUEUED  # written from day one (US-NOT-003)


# ── the rest of the row's contract ──────────────────────────────────────────
def test_us_not_001_tc1__a_queued_row_carries_source_pin_snapshot_and_status(brazos, dana):
    """US-NOT-001 §6, all four clauses: *"Given a queue row, Then it carries
    source refs, template version ref, recipient snapshot and status queued."*

    The pin (BR-BIL-026's pattern, plus BR-NOT-006's language) is what stops a
    template published between queueing and dispatch from changing a document
    already promised to a customer. The snapshot (BR-TEN-017) is what stops a
    name change doing the same thing.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()
        row = a_bill_row(brazos, invoice_id=invoice_id, channel="email", account=account)

        stored = models.OutboundMessage.objects.get(pk=row.pk)
        assert (stored.source_type, stored.source_id) == ("invoice", invoice_id)
        assert stored.channel in models.CHANNELS
        assert stored.status == models.STATUS_QUEUED
        assert stored.template_code == "bill_residential"
        assert stored.template_version == 3
        assert stored.template_language == "en-US"  # BR-NOT-006
        assert stored.recipient_snapshot["name"] == "Sarah Chen"
        assert stored.account_id == account.pk


def test_us_not_001_tc2__the_dispatcher_columns_ship_empty(brazos, dana):
    """r10 #8's dispatcher fields exist and are UNWRITTEN.

    US-NOT-001 §1: *"Exit: rows rest `queued` for the dispatcher"*, and
    US-NOT-001 §5 marks batch id, attempts and provider response *"written by
    dispatcher only"* — a service that is US-NOT-002 and is not built.

    Asserting emptiness rather than skipping the columns is the point: it pins
    that this slice queues and does not send, so a future change that starts
    stamping a batch id from the write path is a visible diff here.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        row = a_bill_row(brazos, invoice_id=uuid4(), channel="pdf_print", account=account)

        assert row.batch_id is None
        assert row.attempts == 0
        assert (row.next_attempt_at, row.last_attempt_at, row.sent_at) == (None, None, None)
        assert (row.provider_reference, row.provider_response, row.last_error) == (
            None,
            None,
            None,
        )


def test_us_not_001_tc3__a_row_may_be_scheduled_and_may_have_no_account(brazos, dana):
    """Two independent facts the table has to hold.

    S31 step 6 offers send-now vs scheduled and *"either way the queue is the
    only path"* (US-BIL-023 §1), so `dispatch_not_before` is on the row.

    And US-NOT-015's scheduled-report and bookkeeper rows (W6) are addressed to
    staff and belong to no customer account, which is why `account` is
    nullable — a NOT NULL there would have made those messages unqueueable and
    pushed them back into an inline send, which BR-NOT-005 forbids outright.
    """
    with tenant_ctx(brazos):
        scheduled = models.OutboundMessage.objects.create(
            tenant=brazos,
            source_type="report",
            source_id=uuid4(),
            channel=models.CHANNEL_EMAIL,
            template_code="scheduled_report",
            recipient_address="bookkeeper@brazosbendutilities.test",
            dispatch_not_before=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
        )
        assert scheduled.account_id is None
        assert scheduled.dispatch_not_before.date() == date(2026, 9, 1)
        assert scheduled.status == models.STATUS_QUEUED


def test_us_not_001_tc6__the_queue_table_is_tenant_scoped(brazos):
    """CLAUDE.md rule 1, as a SHAPE check that runs on SQLite too.

    The live policy is the isolation suite's job and cannot run here. What CAN
    run here is the precondition every policy depends on: a table with no
    `tenant_id` cannot be tenant-scoped by any policy. This is the platform
    queue — one table carrying every module's customer names, addresses and
    phone numbers — so the precondition is worth asserting where everyone runs.
    """
    fields = {f.name for f in models.OutboundMessage._meta.get_fields()}
    assert "tenant" in fields, "outbound_messages has no tenant column"


def test_us_not_001_tc4__the_channel_vocabulary_is_the_ratified_three(brazos):
    """r12 #16 ("email + SMS + print") and US-NOT-003 §4's enum, and BR-NOT-010:
    *"door-hanger is NOT a channel until v2"*.

    Pinned as a test because the constant is the only place the vocabulary is
    written down in code, and a fourth value appearing there without a ruling is
    exactly the kind of quiet scope addition BR-NOT-010 was written to stop.

    ⚠ **AMENDED 2026-08-17 (CR-009 in-app lane) — AND THE AMENDMENT IS THIS
    TEST DOING ITS JOB.** A fourth value DID appear, and it came WITH a ruling:
    the PO, 2026-08-17, *"can you build the in-app?"* — because in-app *"does
    not require any integration and it is proof that notification is working"*
    (BR-NOT-019). So the assertion is updated to four and NOT relaxed to a
    membership check: the point of pinning the whole tuple is that the next
    lane to add a channel has to come here, change a literal, and say which
    ruling authorises it. `door_hanger` is still refused (BR-NOT-010) and that
    line is untouched.

    ⚠ **AMENDED AGAIN 2026-09-07 (`CR-084`) — A FIFTH VALUE, AND AGAIN IT CAME
    WITH A RULING.** The PO, pointing at the greyed-out row on Settings →
    Notifications → Bill ready: *"can you swithc on this now - Customer portal"*
    (`BR-NOT-1031`). Like in-app it needs no integration; unlike in-app it
    reaches a CUSTOMER. The tuple is still pinned whole rather than relaxed to a
    membership check, for the reason the paragraph above gives — and this is the
    second time that has made a lane come here and name its ruling.
    """
    assert models.CHANNELS == ("pdf_print", "email", "sms", "in_app", "portal")
    assert "door_hanger" not in models.CHANNELS
    # ⚠ **AMENDED 2026-09-17 (`DEF-NOT-5626`) — FOUR MORE, AND THEY ARE THE
    # SENDGRID/POSTMARK NORMALISED OUTCOME SET.** Two providers, two
    # vocabularies, and NEITHER may escape its adapter: the product sees
    # `delivered · bounced_hard · bounced_soft · complained · unsubscribed ·
    # failed` and nothing else. `bounced` stays LAWFUL and LEGACY — it means *a
    # bounce of unknown kind*, no row was rewritten into one of the two new
    # words, and `apps/notifications/migrations/0018_…` says why in full.
    # Pinned whole rather than relaxed to a membership check, for the reason the
    # CHANNELS paragraphs above give: it is what makes a lane come here and
    # write down what it did.
    assert models.STATUSES == (
        "queued",
        "sent",
        "delivered",
        "failed",
        "bounced",
        "bounced_hard",
        "bounced_soft",
        "complained",
        "unsubscribed",
    )
    # The CONTRACT an email adapter maps onto — six, not nine: `queued` and
    # `sent` are ours and nobody reports them to us, and `bounced` is never
    # written again.
    assert models.PROVIDER_OUTCOME_STATUSES == (
        "delivered",
        "bounced_hard",
        "bounced_soft",
        "complained",
        "failed",
        "unsubscribed",
    )
    # ⚠ A CHOICE IS NOT A FAILURE: `unsubscribed` is deliberately off the list a
    # clerk sees under *failures*, and the partial index under that screen
    # carries the same five.
    assert models.ATTENTION_STATUSES == (
        "failed",
        "bounced",
        "bounced_hard",
        "bounced_soft",
        "complained",
    )
    assert "unsubscribed" not in models.ATTENTION_STATUSES


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-001@2e6b19d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — Addendum r10 #8 + r12 #16 + r16 #1/#6/#7 — · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md · 10-notifications/02-business-rules.md · 10-notifications/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 notifications outbound-queue schema slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — schema slice) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: 11 passed on sqlite and on live Postgres. PROVED RED FIRST: with
#         `uq_outbound_msgs_source_channel` removed from the model and the
#         migration, `test_us_not_001_tc5__re_releasing_a_bill_cannot_queue_a_
#         second_copy` and `test_us_not_001_tc5c__a_deliberate_resend_is_a_new_
#         row_a_replay_is_not` both failed with "Failed: DID NOT RAISE
#         IntegrityError" — the second release INSERTed cleanly. Restored: 11
#         passed. The isolation half is the companion file, which ALSO reads
#         the index out of pg_indexes so a constraint the migration silently
#         failed to apply cannot pass here.
# exceptions: does NOT assert that a bill RELEASE writes these rows — no release
#         path exists (US-BIL-023), and this slice ships the table it will write
#         to. Named here rather than left looking covered · TC numbering follows
#         US-NOT-001 §3 where a case maps to one (TC-5 idempotency, TC-6
#         isolation, TC-1/2/3 the queue-write contract); TC-7 is BR-BIL-036's
#         no-email case, which post-dates the story's §3 table (PO ruling
#         2026-08-10, OQ-091) and has no §3 row to take a number from
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
