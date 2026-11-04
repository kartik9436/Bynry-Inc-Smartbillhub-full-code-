# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-001 (`outbound_messages` — the ONLY write path into the
#           platform queue)   Screens: S8 · S30 · S35
# Rules:    BR-NOT-005 (every message is a queue row FIRST; only the dispatcher
#           sends) · BR-BIL-016 (one delivery record per document per channel;
#           mass sends are never synchronous) · BR-BIL-036 (PRINT is the
#           primary channel and the FLOOR; an account with no email address is
#           normal, not an exception) · BR-BIL-026 (template + version pinned) ·
#           BR-NOT-010 (v1 channels are print/email/SMS — no door-hanger) ·
#           BR-AUD-006 (no PII in the trail) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 6 (idempotency) · rule 7 (the queue write is
#           audited)
# ───────────────────────────────────────────────────────
"""The queue WRITE path: what one call leaves behind, and what it refuses.

The table's own guarantees are `test_us_not_001_outbound_queue.py`; its RLS is
`test_us_not_001_outbound_isolation.py`. This file is about the service —
`apps.notifications.services.queue_document`, which every module calls and no
module bypasses.

TWO OF THESE CASES ARE THE ONES A PASSING SUITE COULD MOST EASILY FAKE, so both
were broken deliberately and run before either was trusted green (hard-won law
7); the verbatim failures are in this lane's report and in the review ledger.

  * **Idempotency.** The scenario is not a user double-clicking. It is a
    background job retried after committing, and a retry does not call the
    service with a flag set. So the case asserts the SECOND call writes nothing
    AND that the database itself refuses a duplicate when the service's own
    pre-check is bypassed.
  * **Print is the floor.** BR-BIL-036 is the rule most likely to be
    "optimised" later by someone who notices that a paperless customer has an
    email address. The case asks for email only and asserts paper anyway.

NOTHING HERE SENDS. R2 builds the queue; R4 switches email on. Several cases
assert the absence of a send rather than trusting the docstring — the
dispatcher columns stay empty and every row rests `queued`.
"""

from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction

from apps.notifications import models, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

A_PIN = services.TemplatePin(
    code="bill_residential", template_id=uuid4(), version=3, language="en-US"
)


def an_account(actor, tenant, *, account_no="ACC-1042"):
    """A minimal account. Built through customers' own service would drag in the
    whole activation path; these cases are about the queue write."""
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


def queue_a_bill(**overrides):
    """The call a bill release makes: one invoice, whatever channels it elected."""
    values = dict(
        source_type="invoice",
        source_id=uuid4(),
        channels=(),
        template=A_PIN,
    )
    values.update(overrides)
    return services.queue_document(**values)


# ── CLAUDE.md rule 6 — a replay never queues a second copy ──────────────────
def test_us_not_001_tc5__queueing_the_same_bill_twice_writes_one_row(brazos, dana, audit_rows):
    """CLAUDE.md rule 6 · US-NOT-001 TC-5 · BR-BIL-016 (*"one delivery record per
    document per channel"*).

    A duplicate here is not cosmetic: it is a second paper bill in the post from
    the print vendor, at the vendor's per-piece price, and a customer ringing up
    to ask which one they owe.

    The second call must be a NO-OP that says so — `created=False` — rather than
    silently succeeding, because a caller told "queued" twice would report two
    sends on a dashboard that only ever had one row.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()

        first = queue_a_bill(source_id=invoice_id, account_id=account.pk)
        second = queue_a_bill(source_id=invoice_id, account_id=account.pk)

        assert [message.created for message in first.messages] == [True]
        assert [message.created for message in second.messages] == [False]
        assert second.created == ()
        assert len(second.already_queued) == 1
        assert (
            models.OutboundMessage.objects.filter(
                source_id=invoice_id, channel=models.CHANNEL_PRINT
            ).count()
            == 1
        )
        # …and the trail records ONE queue event, not two (hard rule 7).
        queued = [row for row in audit_rows if row["action"] == services.AUDIT_ACTION]
        assert len(queued) == 1


def test_us_not_001_tc5b__the_database_refuses_the_duplicate_when_the_service_cannot(
    brazos, dana, monkeypatch
):
    """The same law from underneath — because the retry is what actually happens.

    The service's pre-SELECT is the fast path and it is not the guarantee: two
    workers can both find nothing and both try to INSERT. Here that race is
    forced by blinding the pre-check, and what must hold is that the DATABASE
    refuses the second row (`uq_outbound_msgs_source_channel`) and the service
    reports the existing one rather than raising at its caller.

    Proved RED first: with the `except IntegrityError` recovery removed, this
    case failed with `django.db.utils.IntegrityError: UNIQUE constraint failed:
    outbound_messages.tenant_id, outbound_messages.source_type, …` escaping into
    the test — a bill run would have died on a retry.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()
        queue_a_bill(source_id=invoice_id, account_id=account.pk)

        # The other worker's view of the world: it saw nothing already queued.
        monkeypatch.setattr(
            services.models.OutboundMessage.objects,
            "filter",
            _blind_then_real(services.models.OutboundMessage.objects),
        )
        raced = queue_a_bill(source_id=invoice_id, account_id=account.pk)

        assert [message.created for message in raced.messages] == [False]
        assert services.QUEUE_ALREADY_QUEUED in {entry["code"] for entry in raced.problems}
        assert models.OutboundMessage.objects.filter(source_id=invoice_id).count() == 1


def _blind_then_real(manager):
    """A `filter` that answers "nothing queued" ONCE, then behaves normally.

    Forces the racing path without touching the service: the pre-check comes
    back empty, the INSERT hits the unique index, and the recovery read (which
    must NOT be blinded, or the test would prove nothing about recovery) finds
    the row the other worker wrote.
    """
    real = manager.filter
    state = {"blinded": False}

    def fake(*args, **kwargs):
        result = real(*args, **kwargs)
        if not state["blinded"]:
            state["blinded"] = True
            return result.none()
        return result

    return fake


def test_us_not_001_tc5c__a_human_asking_for_another_copy_gets_one(brazos, dana):
    """US-NOT-011 §5 / US-BIL-024 TC-4 against US-NOT-001 TC-5.

    A customer ringing up for another copy of their bill is a real request that
    must produce a real message; a job retry is not. `copy_no` is the door, and
    it opens only when a caller types a number — an automatic writer never does.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()
        queue_a_bill(source_id=invoice_id, account_id=account.pk)

        resend = queue_a_bill(source_id=invoice_id, account_id=account.pk, copy_no=1)

        assert [message.created for message in resend.messages] == [True]
        assert models.OutboundMessage.objects.filter(source_id=invoice_id).count() == 2
        # …and the re-send is itself idempotent: asking twice for copy 1 is copy 1.
        again = queue_a_bill(source_id=invoice_id, account_id=account.pk, copy_no=1)
        assert [message.created for message in again.messages] == [False]


# ── BR-BIL-036 — print is the FLOOR ─────────────────────────────────────────
def test_us_not_001_tc7__a_paperless_customer_still_gets_a_print_row(brazos, dana):
    """BR-BIL-036, the PO's closure of OQ-091 on 2026-08-10:

        PRINT is the primary delivery channel; email and SMS are NOTIFICATIONS
        of the amount, not a replacement for the document. […] An account with
        NO email address is normal, not an exception — delivery must never
        assume one exists, and such an account still bills, still renders and
        still dispatches.

    So a caller that names ONLY email — which is exactly what a paperless
    election looks like — gets email AND paper. The floor lives in the service
    rather than in each writer, because a rule every writer has to remember is
    a rule one writer will eventually drop, and the customer whose paper bill
    stopped arriving is the one who finds out.

    Proved RED first: with `CHANNEL_FLOOR_BY_SOURCE` emptied, this failed with
    `AssertionError: assert ('email',) == ('pdf_print', 'email')` and the print
    row count came back 0 — a paperless account would have received nothing on
    paper at all.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()

        written = queue_a_bill(
            source_id=invoice_id, account_id=account.pk, channels=(models.CHANNEL_EMAIL,)
        )

        assert written.channels == (models.CHANNEL_PRINT, models.CHANNEL_EMAIL)
        assert written.floor_channels_added == (models.CHANNEL_PRINT,)
        assert services.QUEUE_FLOOR_CHANNEL_ADDED in {entry["code"] for entry in written.problems}
        assert (
            models.OutboundMessage.objects.filter(
                source_id=invoice_id, channel=models.CHANNEL_PRINT
            ).count()
            == 1
        )
        # One row per channel (BR-BIL-016), and they are independent rows: the
        # email row's problems can never reach the print row, because they share
        # no column that could carry a failure.
        assert models.OutboundMessage.objects.filter(source_id=invoice_id).count() == 2


def test_us_not_001_tc7b__the_floor_covers_every_customer_document_and_nothing_else(brazos):
    """The floor's other half: it must not over-fire — and what counts as
    "over" was WIDENED by the PO on 2026-08-29 (`BR-NOT-024`).

    ⚠ **THIS TEST WAS NAMED FOR A RULE THAT NO LONGER HOLDS**, and the old name
    is kept here because a superseded assertion is worth seeing:
    `the_floor_is_a_bill_rule_and_is_not_invented_elsewhere`. It asserted
    `channels_for("payment", (email,)) == (email,)` and
    `channels_for("notice", ()) == ()` on the reasoning that BR-BIL-036 speaks
    about BILLS, that a receipt is *"(opt)"* in A15, and that nothing signed
    said a notice must go on paper. **All three statements were true and the
    conclusion was still wrong about the product:** `notice` carries the
    DISCONNECTION LETTER, so a utility could switch off a document the law
    makes a precondition of cutting somebody's water off.

    PO ruling, verbatim: *"this is correct - don't switch of print for any
    document it is awayls on"*. A15's *"(opt)"* is superseded; BR-BIL-036 is
    unchanged and is now the narrowest case of a wider rule.

    **The "must not over-fire" half still matters and is what this now guards:**
    the four kinds with no postal surface — a bell summary for a clerk, an
    internal report, a ledger row, a send-test rehearsal — get NO floor. That is
    not print being switched off; there is no envelope for them to go in.
    """
    assert services.channels_for("invoice", ()) == (models.CHANNEL_PRINT,)
    assert services.channels_for("invoice", (models.CHANNEL_EMAIL,)) == (
        models.CHANNEL_PRINT,
        models.CHANNEL_EMAIL,
    )
    # …and asking for print explicitly does not queue it twice.
    assert services.channels_for("invoice", (models.CHANNEL_PRINT,)) == (models.CHANNEL_PRINT,)

    # BR-NOT-024 — the three kinds that GAINED a floor with the ruling.
    assert services.channels_for("payment", (models.CHANNEL_EMAIL,)) == (
        models.CHANNEL_PRINT,
        models.CHANNEL_EMAIL,
    )
    assert services.channels_for("notice", ()) == (models.CHANNEL_PRINT,)
    assert services.channels_for("plan", ()) == (models.CHANNEL_PRINT,)

    # …and the half that did NOT change: no postal surface, so no floor.
    for kind in ("report", "ledger", "test", "bulk_action"):
        assert models.CHANNEL_PRINT not in services.channels_for(kind, ()), (
            f"{kind} has no envelope to go in — giving it a floor would post a "
            "staff alert (BR-NOT-024)"
        )


# ── a recipient nobody can resolve is RECORDED, never guessed ───────────────
def test_us_not_001_tc8__an_unresolvable_recipient_is_a_row_that_says_so(brazos, dana, monkeypatch):
    """Task rule: an address the system does not have is a REPORTABLE ABSENCE —
    not a skipped row and not a placeholder.

    ⚠ **AMENDED 2026-09-23 (`DEF-PAY-6342`) — THE FIXTURE ACCOUNT IS NO LONGER
    UNRESOLVABLE, AND THAT IS THE FIX RATHER THAN A REGRESSION.** The paragraph
    below says customers *"still cannot render it as an envelope, because
    metering publishes no structured premises-address read"*. Metering publishes
    one now (`envelope_addresses`) and the account's letter goes to its premises
    — `1901 Bluestem Ln · Unit A`, `source: service_address` — which is what
    B2 §2 always said. So the PLATFORM gap this test defends is produced the
    only way it can still arise: metering's read unpublished. The row, the
    reason and the distinction from `no_postal_address` are unchanged, and
    `test_def_pay_6342_service_address.py` owns the addressed case.

    AMENDED 2026-08-11 (W4/W8 customers ACTION lane) — hard-won law 1. This
    docstring used to read *"Customers publishes no
    `delivery_recipients_for_account` on this deployment"*, and it was true from
    W3 until that lane published exactly that read. The claim moved with the
    fact: the read EXISTS and is consulted, so `recipient_read_unpublished` is
    no longer emitted.

    The row is unchanged and it is what this test defends. The fixture account
    has no mailing address, and B2 §2 makes an absent mailing row mean *"same as
    service"* — so the account HAS a postal address and customers still cannot
    render it as an envelope, because metering publishes no structured
    premises-address read. The read says `recipient_not_resolvable` for that
    reason, deliberately.

    The distinction being defended is the one `apps/billing/release.py` defends
    about mandate coverage: *"'0 of 1,122 hold an address' and 'we could not
    count' must never render the same."* `no_postal_address` would be a claim
    about a customer; this is a claim about the platform.
    """
    from apps.customers import seams as customers_seams

    real = customers_seams.resolve

    def metering_cannot_answer(module, attribute, kind="services"):
        return None if attribute == "envelope_addresses" else real(module, attribute, kind)

    monkeypatch.setattr(customers_seams, "resolve", metering_cannot_answer)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()

        written = queue_a_bill(source_id=invoice_id, account_id=account.pk)

        row = models.OutboundMessage.objects.get(source_id=invoice_id)
        assert row.recipient_address is None
        assert row.unavailable_reason == models.REASON_NOT_RESOLVABLE
        assert row.unavailable_reason != models.REASON_NO_POSTAL  # never inferred
        assert row.status == models.STATUS_QUEUED  # written, never skipped
        codes = {entry["code"] for entry in written.problems}
        # The read resolves now, so "nobody could look at all" is gone …
        assert services.QUEUE_RECIPIENT_READ_UNPUBLISHED not in codes
        # … and what remains is the per-channel absence, which is the row above.
        assert services.QUEUE_RECIPIENT_ABSENT in codes


def test_us_not_001_tc8b__the_customers_read_is_used_the_moment_it_exists(
    brazos, dana, monkeypatch
):
    """Hard-won law 2, from the other side: the seam is wired, not decorative.

    The read is resolved BY NAME at call time, so the day customers publishes
    it this path starts using it with no edit here. Both of its answers are
    exercised — an address, and an honest "none on file", which is BR-BIL-036's
    normal case and is recorded with the customer-fact reason rather than the
    platform-fact one.
    """
    from apps.customers import selectors as customer_selectors

    def a_published_read(account_id, channels=()):
        return {
            models.CHANNEL_PRINT: {
                "address": "1901 Bluestem Ln, Unit A\nKaty TX 77494",
                "snapshot": {"name": "Sarah Chen"},
            },
            models.CHANNEL_EMAIL: {"unavailable_reason": models.REASON_NO_EMAIL},
        }

    monkeypatch.setattr(
        customer_selectors, services.RECIPIENT_READ, a_published_read, raising=False
    )
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()

        written = queue_a_bill(
            source_id=invoice_id, account_id=account.pk, channels=(models.CHANNEL_EMAIL,)
        )

        printed = models.OutboundMessage.objects.get(
            source_id=invoice_id, channel=models.CHANNEL_PRINT
        )
        emailed = models.OutboundMessage.objects.get(
            source_id=invoice_id, channel=models.CHANNEL_EMAIL
        )
        assert printed.recipient_address.startswith("1901 Bluestem Ln")
        assert printed.recipient_snapshot["name"] == "Sarah Chen"
        assert printed.unavailable_reason is None
        # BR-BIL-036: the missing email cannot reach the print row.
        assert emailed.recipient_address is None
        assert emailed.unavailable_reason == models.REASON_NO_EMAIL
        assert services.QUEUE_RECIPIENT_ABSENT in {entry["code"] for entry in written.problems}


def test_us_not_001_tc8c__a_read_that_answers_neither_question_is_refused(
    brazos, dana, monkeypatch
):
    """A recipient entry with no address AND no reason is the shape of a
    swallowed exception: the row would look queued, never be delivered, and say
    nothing about why. Refused at the seam rather than written."""
    from apps.customers import selectors as customer_selectors

    monkeypatch.setattr(
        customer_selectors,
        services.RECIPIENT_READ,
        lambda account_id, channels=(): {models.CHANNEL_PRINT: {}},
        raising=False,
    )
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(services.QueueWriteRefused, match="neither an address nor a reason"):
            queue_a_bill(account_id=account.pk)


def test_us_not_001_tc8d__a_caller_that_knows_its_own_recipient_states_it(brazos):
    """US-NOT-015's scheduled-report and bookkeeper rows go to a STAFF address
    and belong to no customer account, so there is nothing to look up. The
    caller wins, and no customers read is consulted."""
    with tenant_ctx(brazos):
        written = services.queue_document(
            source_type="report",
            source_id=uuid4(),
            channels=(models.CHANNEL_EMAIL,),
            template=services.TemplatePin(code="scheduled_report"),
            recipients=(
                services.Recipient(
                    channel=models.CHANNEL_EMAIL,
                    address="bookkeeper@brazosbendutilities.test",
                    snapshot={"name": "Bookkeeper"},
                ),
            ),
        )

        assert written.channels == (models.CHANNEL_EMAIL,)  # no floor on a report
        row = models.OutboundMessage.objects.get(pk=written.messages[0].id)
        assert row.recipient_address == "bookkeeper@brazosbendutilities.test"
        assert row.account_id is None
        assert row.unavailable_reason is None


# ── hard rule 7 — the queue write is audited, without PII ───────────────────
def test_us_not_001_tc9__every_queued_row_writes_one_audit_row_and_no_pii(
    brazos, dana, monkeypatch, audit_rows
):
    """CLAUDE.md rule 7, and BR-AUD-006 over it.

    The trail records THAT a message was queued, on which channel, for which
    document, and whether it had an address — never the address, the phone
    number or the customer's name. Those live on the row, for anyone entitled
    to read it.
    """
    from apps.customers import selectors as customer_selectors

    monkeypatch.setattr(
        customer_selectors,
        services.RECIPIENT_READ,
        lambda account_id, channels=(): {
            channel: {"address": "sarah.chen@example.test", "snapshot": {"name": "Sarah Chen"}}
            for channel in channels
        },
        raising=False,
    )
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()
        queue_a_bill(source_id=invoice_id, account_id=account.pk, channels=(models.CHANNEL_EMAIL,))

        queued = [row for row in audit_rows if row["action"] == services.AUDIT_ACTION]
        assert len(queued) == 2  # one per ROW created — print and email
        assert {row["after"]["channel"] for row in queued} == {"pdf_print", "email"}
        for row in queued:
            assert row["entity_type"] == services.AUDIT_ENTITY
            assert row["after"]["source_id"] == str(invoice_id)
            assert row["after"]["address_present"] is True
            assert row["after"]["dispatched"] is False
            trail = str(row)
            assert "sarah.chen@example.test" not in trail
            assert "Sarah Chen" not in trail


def test_us_not_001_tc9b__a_refused_write_queues_nothing_and_audits_nothing(brazos, audit_rows):
    """The negative half of rule 7: a refusal is not an event.

    A refusal writes no row, so it must write no trail row either — an audit
    row for a message that does not exist is evidence of something that did not
    happen (BR-AUD-003).
    """
    with tenant_ctx(brazos):
        with pytest.raises(services.QueueWriteRefused):
            queue_a_bill(channels=("door_hanger",))
        assert models.OutboundMessage.objects.count() == 0
        assert [row for row in audit_rows if row["action"] == services.AUDIT_ACTION] == []


# ── refusals ────────────────────────────────────────────────────────────────
def test_us_not_001_tc10__the_refusals_that_keep_an_undeliverable_row_out(brazos):
    """Everything that must be true before a row exists, each with its reason.

    None of these is a validation nicety. A row with a channel no adapter
    exists for, a source kind nothing dispatches, or a bill with no template
    pin is a message that can never be sent and can never be explained — and
    the queue is the only place anyone would look for it.
    """
    with tenant_ctx(brazos):
        # BR-NOT-010 — door-hanger is not a channel until v2.
        with pytest.raises(services.QueueWriteRefused, match="unknown delivery channel"):
            queue_a_bill(channels=("door_hanger",))
        # The source vocabulary is a CONSTANT, not a tenant lookup.
        with pytest.raises(services.QueueWriteRefused, match="not a source kind"):
            queue_a_bill(source_type="staff_memo")
        # BR-BIL-026 — a bill queued with no pin could never say what was sent.
        with pytest.raises(services.QueueWriteRefused, match="template VERSION pinned"):
            queue_a_bill(template=services.TemplatePin(code="bill_residential"))
        # …and neither a code nor a pin is nothing to render from at all.
        with pytest.raises(services.QueueWriteRefused, match="template CODE"):
            queue_a_bill(
                source_type="notice",
                channels=(models.CHANNEL_EMAIL,),
                template=services.TemplatePin(),
            )
        # A source kind with no floor and no channel named queues nothing, and
        # says so rather than returning success having delivered nothing.
        # ⚠ THIS CASE READ `source_type="notice"` UNTIL BR-NOT-024 (PO
        # 2026-08-29, *"don't switch of print for any document it is awayls
        # on"*). A notice now carries the print floor, so it can no longer
        # reach this refusal at all — the floor supplies a channel when the
        # caller names none, which is the whole point of a floor. `report` is
        # a staff summary with no envelope to go in, and after that ruling
        # "no floor" means exactly that: no postal surface exists.
        with pytest.raises(services.QueueWriteRefused, match="no channel was named"):
            queue_a_bill(source_type="report", template=services.TemplatePin(code="past_due"))
        with pytest.raises(services.QueueWriteRefused, match="copy_no"):
            queue_a_bill(copy_no=-1)
        assert models.OutboundMessage.objects.count() == 0


def test_us_not_001_tc11__no_tenant_context_is_refused_before_any_query(brazos):
    """CLAUDE.md rule 1. A dispatcher, a maintenance command or a metrics job is
    exactly the kind of caller that runs outside a request — and this table is
    the platform's mailing list. Refused at the door rather than leaving RLS as
    the only thing between one tenant's customers and another's."""
    with pytest.raises(errors.AuthError):
        queue_a_bill()
    assert models.OutboundMessage.objects.count() == 0


# ── R2 queues; R4 sends ─────────────────────────────────────────────────────
def test_us_not_001_tc12__the_write_path_dispatches_nothing(brazos, dana):
    """BR-BIL-016 (*"mass sends are never synchronous"*) and US-NOT-003's
    deferred channels, asserted rather than trusted.

    Every row rests `queued` and every dispatcher-owned column ships empty.
    This is the case that goes red the day somebody adds a send to the write
    path — which is R4's work (email ACTIVATION), not R2's.

    ⚠ **AMENDED 2026-08-17 (CR-009 in-app lane), AND THE ASSERTION IS NARROWED
    TO WHAT IT WAS ALWAYS ABOUT.** It read `set(written.channels) ==
    set(models.CHANNELS)`, which was a correct spelling of *"a bill goes out on
    every channel this platform has"* while all three channels carried
    DOCUMENTS. A fourth arrived — `in_app` (BR-NOT-019) — and it does not carry
    documents: it carries a message to a signed-in member of the utility's own
    STAFF, and **no bill is ever addressed to one.** Left as it was, this case
    would have demanded that every bill be queued into a clerk's bell.

    So the three DOCUMENT channels are named explicitly, which is the fact this
    case is testing (BR-BIL-036's print floor plus the two the caller asked
    for). The rest of the test — every dispatcher-owned column empty — is
    untouched and is still the guard that goes red the day somebody adds a send
    to the write path.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        written = queue_a_bill(
            account_id=account.pk, channels=(models.CHANNEL_EMAIL, models.CHANNEL_SMS)
        )

        assert written.dispatched is False
        assert set(written.channels) == {
            models.CHANNEL_PRINT,
            models.CHANNEL_EMAIL,
            models.CHANNEL_SMS,
        }
        # And in-app is ABSENT rather than merely unasserted — a bill that ever
        # appeared in a staff inbox would be a customer's money in the wrong
        # place, so the negative is stated.
        assert models.CHANNEL_IN_APP not in written.channels
        for message in written.messages:
            row = models.OutboundMessage.objects.get(pk=message.id)
            assert row.status == models.STATUS_QUEUED
            assert row.batch_id is None
            assert row.attempts == 0
            assert (row.sent_at, row.provider_reference, row.provider_response) == (
                None,
                None,
                None,
            )
            assert (row.next_attempt_at, row.last_attempt_at, row.last_error) == (
                None,
                None,
                None,
            )


def test_us_not_001_tc13__a_scheduled_send_rides_the_row_not_a_delay(brazos, dana):
    """S31 step 6's send-now vs scheduled, and BR-NOT-009's quiet hours: both
    are one column the dispatcher honours. The write path never waits — a bill
    run that slept until 08:00 would hold a clerk's browser for nine hours."""
    from datetime import datetime, timezone

    when = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        written = queue_a_bill(account_id=account.pk, dispatch_not_before=when)
        row = models.OutboundMessage.objects.get(pk=written.messages[0].id)
        assert row.dispatch_not_before == when
        assert row.status == models.STATUS_QUEUED


def test_us_not_001_tc14__one_transaction_or_none_of_it(brazos, dana):
    """ "One service function = one transaction boundary."

    A queue write that half-committed would leave a bill with a print row and
    no email row and no record that anything went wrong — the shape nobody
    notices until a customer says they never got the email they signed up for.
    Forced here by making the audit sink fail on the SECOND row, which is also
    hard rule 7 the other way round: no queued message may stand without its
    trail row, so losing the trail loses the message.

    The sink is swapped by hand rather than through `monkeypatch`, because the
    autouse `sqlite_guc` fixture shares that same monkeypatch instance and an
    `undo()` here would rip out the GUC shim mid-test.
    """
    from core import audit as core_audit

    calls = {"n": 0}
    real_sink = core_audit._sink

    def failing_sink(row):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("trail unavailable")
        real_sink(row)

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        core_audit.set_audit_sink(failing_sink)
        try:
            with pytest.raises(RuntimeError), transaction.atomic():
                queue_a_bill(account_id=account.pk, channels=(models.CHANNEL_EMAIL,))
        finally:
            core_audit.set_audit_sink(real_sink)
        assert models.OutboundMessage.objects.count() == 0


def test_us_not_001_tc15__the_key_is_still_the_databases(brazos, dana):
    """A guard-rail on the guard-rail: the service honours the key, and the KEY
    is the table's. If a future refactor moved the uniqueness into Python this
    would still pass and rule 6 would be gone — so the raw INSERT is asserted
    too, exactly as `test_us_not_001_outbound_queue.py` does from the table's
    side."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice_id = uuid4()
        queue_a_bill(source_id=invoice_id, account_id=account.pk)
        with pytest.raises(IntegrityError), transaction.atomic():
            models.OutboundMessage.objects.create(
                tenant=brazos,
                account=account,
                source_type="invoice",
                source_id=invoice_id,
                channel=models.CHANNEL_PRINT,
                template_code="bill_residential",
                recipient_address="1901 Bluestem Ln",
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-001@2e6b19d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — Addendum r10 #8 + r12 #16 + r16 #1/#6/#7 — · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md · 10-notifications/02-business-rules.md · 10-notifications/03-field-map.md)
# generated: 2026-08-11 by story-coder (W3 notifications queue-WRITE lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no notifications endpoints) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST — the idempotency guard and the print floor were each
#         broken deliberately, the suite run, and the measured failure quoted in
#         this lane's report before either was trusted green (hard-won law 7)
# exceptions: SQLite tier — these cases assert the SERVICE and the table's own
#         constraints, both of which run everywhere. Tenant ISOLATION of the
#         write path is `tests/test_us_not_001_queue_write_isolation.py`, which
#         needs live Postgres and a non-superuser probe role · no case asserts
#         anything about DISPATCH: there is no dispatcher (US-NOT-002), and
#         `tc12` asserts precisely that nothing was sent rather than leaving the
#         absence to be inferred
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
