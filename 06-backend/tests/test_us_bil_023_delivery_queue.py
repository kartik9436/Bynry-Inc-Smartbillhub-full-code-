# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-023 (the outbound delivery queue — one record per bill per
#           channel at issue; print/PDF v1, email dispatch deferred → W6)
#           Screens: S31 step 6 · S30
# Rules:    BR-BIL-016 (one delivery record per bill per channel; mass sends
#           are NEVER synchronous) · BR-BIL-036 (PRINT is the primary channel
#           and the FLOOR) · BR-BIL-026 (the queue row carries the bill's pin) ·
#           BR-BIL-055 (a break never blocks the run) · BR-NOT-005 (every
#           message is a queue row first; only the dispatcher sends) ·
#           CLAUDE.md rule 6 (idempotency) · rule 7 (audit)
# ───────────────────────────────────────────────────────
"""What a bill leaves in the delivery queue when it issues — and what it does not.

The queue itself is notifications' (`test_us_not_001_queue_write.py`); this
file is the BILLING half: that issue actually calls the seam, that the rows it
leaves are the ones BR-BIL-016 describes, and that nothing anywhere in the path
sends anything.

WHY "NOTHING WAS SENT" IS ASSERTED AND NOT ASSUMED. R2 builds the queue and R4
switches email on. The failure this file is written against is a future change
that quietly turns a queue write into a send — so `tc6` reads the dispatcher's
own columns back and requires them empty, and every result carries
`dispatched is False` as a value rather than as a sentence in a docstring.

TWO ABSENCES WERE ASSERTED AS ABSENCES and the paragraph here said *"both will
go RED when they are closed, which is exactly when someone should read this
file"*. **ONE OF THEM CLOSED ON 2026-08-31 (CR-052 W4 task 14) AND THIS FILE
WENT RED EXACTLY AS PROMISED**, on

    tc1b  KeyError: 'delivery_election_unreadable'
    tc3   StopIteration on the same code

`accounts.paperless` and `accounts.sms_reminders` are BUILT (migration
`customers 0034`) and `selectors.delivery_channel_election_for_account` is the
read `delivery_seam` had named by string since W3. So the election is now
ANSWERABLE, and the honest answer for every account in the product is *this
customer elected nothing* — `()`, not `None`. `tc1b` and `tc3` below are amended
to assert THAT rather than deleted, so the superseded behaviour stays legible to
the next reader (the posture `US-RAT-008 TC4` took when BR-RAT-094 refused what
it used to allow).

**The RECIPIENT absence is still an absence** and is still asserted as one: an
email address resolves, a postal envelope does not, and an SMS number does not —
`DEF-2700` is why the second and third are stated rather than guessed.
"""

import pytest

from apps.billing import delivery_seam, issue, models
from apps.billing.exceptions import BillingRuleError
from apps.notifications import models as outbound

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
    electric_gl_accounts,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def issue_one(brazos, dana, *, invoice_no="BL-2607-000101", account_no="A-1042", **kwargs):
    """One bill, issued the way the run issues it. Returns the issued row."""
    electric_gl_accounts()
    account = an_account(dana, brazos, account_no=account_no)
    run = an_authorised_run(brazos, dana)
    draft = a_priced_draft(brazos, account, run, invoice_no=invoice_no)
    billed = issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        **kwargs,
    )
    return billed, account, run


def an_election(monkeypatch, channels):
    """A customers module that HAS published the delivery-preference read."""
    from apps.customers import selectors as customer_selectors

    monkeypatch.setattr(
        customer_selectors,
        delivery_seam.ELECTION_READ,
        lambda account_id: channels,
        raising=False,
    )


# ── BR-BIL-016 — issue writes the delivery record ───────────────────────────
def test_us_bil_023_tc1__issuing_a_bill_leaves_a_queue_row_per_channel(brazos, dana):
    """US-BIL-023 TC-1 / J07 step 2 (*"delivery row queued per channel"*).

    The row is the whole point of BR-BIL-016 and it has to carry enough to be
    dispatched later WITHOUT re-reading anything: which document it delivers,
    on which channel, and which pinned template version renders it (BR-BIL-026,
    so a template published next month cannot change a bill already promised).

    ⚠ **THIS SAID *"ONE row today, not two"* UNTIL 2026-09-24 AND HAD BEEN RED
    SINCE `5b6aaa823` ON 2026-09-07 (`DEF-BIL-6456`).** It was true when it was
    written — print was the floor and nothing above it was invented — and
    `CR-084` then put the customer's own copy on the portal beside the paper
    one. The portal is offered by the PLATFORM rather than elected by the
    customer (`notifications/services.py`: *"it needs no address the customer
    had to give us, it costs nothing"*), so **every bill now leaves TWO rows:
    one `pdf_print` and one `portal`**, and this case is amended to name both
    rather than to count them — a bare `== 2` would pass just as well on two
    print rows, which is the duplicate `tc5` exists to forbid.
    """
    with tenant_ctx(brazos):
        billed, account, _run = issue_one(brazos, dana)

        rows = {
            row.channel: row
            for row in outbound.OutboundMessage.objects.filter(source_id=billed.pk)
        }
        assert sorted(rows) == [outbound.CHANNEL_PRINT, outbound.CHANNEL_PORTAL]
        row = rows[outbound.CHANNEL_PRINT]
        assert row.source_type == "invoice"
        assert row.status == outbound.STATUS_QUEUED
        assert row.copy_no == 0  # the delivery record, not an extra copy
        assert row.account_id == account.pk
        # BR-BIL-026 — the BILL's pin, not today's published version.
        assert row.template_id == billed.template_id == TEMPLATE_ID
        assert row.template_version == billed.template_version == TEMPLATE_VERSION
        # The portal copy is the same document on the customer's own screen:
        # same bill, same pin, its own row (CR-084).
        portal = rows[outbound.CHANNEL_PORTAL]
        assert portal.source_type == "invoice"
        assert portal.status == outbound.STATUS_QUEUED
        assert portal.copy_no == 0
        assert portal.account_id == account.pk
        assert portal.template_version == billed.template_version == TEMPLATE_VERSION
        # …and the outcome the caller sees says the same thing.
        assert sorted(billed.delivery.channels) == sorted(
            (outbound.CHANNEL_PRINT, outbound.CHANNEL_PORTAL)
        )
        assert len(billed.delivery.queued) == 2
        assert billed.delivery.already_queued == ()


def test_us_bil_023_tc1b__the_run_reports_its_queue_totals(brazos, dana):
    """`issue_run` counts ROWS, not bills (BR-BIL-016 is per bill per channel),
    and reports the distinct problems once with the number of bills each hit —
    a run of 480 that could resolve no recipient must say that once, not 480
    times."""
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = an_authorised_run(brazos, dana)
        first = an_account(dana, brazos, account_no="A-1042")
        second = an_account(dana, brazos, account_no="A-1043")
        a_priced_draft(brazos, first, run, invoice_no="BL-2607-000101")
        a_priced_draft(brazos, second, run, invoice_no="BL-2607-000102")

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )

        assert len(result.issued) == 2
        # ⚠ **WAS `== 2  # one print row each` UNTIL 2026-09-24 (`DEF-BIL-6456`).**
        # `CR-084` gives every bill a portal copy beside its paper one, so two
        # bills leave FOUR rows — and this counter counts ROWS, which is what
        # the docstring above says and what makes the number move.
        assert result.delivery_queued == 4  # one print row and one portal row each
        assert result.delivery_already_queued == 0
        problems = {entry["code"]: entry for entry in result.delivery_problems}
        # ⚠ THIS ASSERTION READ `problems["delivery_election_unreadable"]["bills"]
        # == 2` UNTIL 2026-08-31 AND IS AMENDED RATHER THAN DELETED (CR-052 task
        # 14). It went RED on `KeyError: 'delivery_election_unreadable'` the
        # moment the election became readable, which is what the file's own
        # header promised would happen. Two accounts that elected nothing are
        # now TWO ANSWERS OF `()`, not two unanswerable questions — so the
        # problem is correctly absent, and the row count is unchanged at two
        # print rows, because print is the floor either way.
        assert "delivery_election_unreadable" not in problems
        assert outbound.OutboundMessage.objects.count() == 4
        assert (
            outbound.OutboundMessage.objects.filter(channel=outbound.CHANNEL_PRINT).count() == 2
        )
        assert (
            outbound.OutboundMessage.objects.filter(channel=outbound.CHANNEL_PORTAL).count() == 2
        )


# ── BR-BIL-036 — print is the floor, through the whole path ─────────────────
def test_us_bil_023_tc2__a_paperless_account_still_gets_its_paper_bill(brazos, dana, monkeypatch):
    """BR-BIL-036 (PO closure of OQ-091): *"PRINT is the primary delivery
    channel; email and SMS are NOTIFICATIONS of the amount, not a replacement
    for the document."*

    This is the case that has to survive the future optimisation. The account
    has elected paperless — the election read says `("email",)` — and it still
    gets a print row, because paperless is a preference about NOTIFICATION and
    not permission to stop sending the document.

    It also proves the election seam is wired rather than decorative
    (hard-won law 2): the moment customers publishes the read, the email row
    appears with no edit in billing.

    Proved RED first: with `CHANNEL_FLOOR_BY_SOURCE` emptied in notifications,
    the print row vanished and this failed with
    `AssertionError: assert ['email'] == ['email', 'pdf_print']`.
    """
    an_election(monkeypatch, (outbound.CHANNEL_EMAIL,))
    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(brazos, dana)

        channels = sorted(
            outbound.OutboundMessage.objects.filter(source_id=billed.pk).values_list(
                "channel", flat=True
            )
        )
        # ⚠ **`portal` JOINED THIS LIST ON 2026-09-07 AND THE CASE WAS RED FOR
        # SEVENTEEN DAYS (`DEF-BIL-6456`).** It changes nothing about what this
        # case defends: the account elected paperless and STILL gets its paper
        # bill. The portal copy is the platform's offer, not the election.
        assert channels == ["email", "pdf_print", "portal"]
        assert sorted(billed.delivery.channels) == ["email", "pdf_print", "portal"]
        # The election was READ, so no unreadable-election problem is reported.
        codes = {entry["code"] for entry in billed.delivery.problems}
        assert "delivery_election_unreadable" not in codes


def test_us_bil_023_tc3__an_account_that_elected_nothing_gets_the_floor_and_only_the_floor(
    brazos, dana
):
    """⚠ **AMENDED 2026-08-31 (CR-052 W4 task 14). WHAT THIS TEST USED TO SAY:**

        *"The absence, reported rather than guessed. `accounts.paperless` and
        `accounts.sms_reminders` are PROPOSED-SCHEMA and unbuilt, and customers
        publishes no selector for them … the bill gets the BR-BIL-036 floor and
        the gap travels with the result."*

    It asserted `delivery_election_unreadable` on the result and went RED on
    `StopIteration` the moment the columns landed. **The behaviour a customer
    sees is IDENTICAL and that is the point of amending rather than rewriting:**
    an account that has elected nothing still gets exactly one row, `pdf_print`,
    and no email. What changed is WHY — the question used to be unanswerable and
    now has the answer `()`, which is a fact about the CUSTOMER rather than
    about the platform, so no problem rides the result.

    The two must not be spelled the same way, which is the distinction
    `elected_channels` is built around, so this asserts the problem is ABSENT.
    """
    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(brazos, dana)

        codes = {entry["code"] for entry in billed.delivery.problems}
        assert "delivery_election_unreadable" not in codes
        assert delivery_seam.elected_channels(billed.account_id) == ((), None)
        assert outbound.OutboundMessage.objects.filter(channel=outbound.CHANNEL_EMAIL).count() == 0
        assert outbound.OutboundMessage.objects.filter(channel=outbound.CHANNEL_PRINT).count() == 1


def test_us_bil_023_tc4__an_unresolvable_recipient_is_recorded_on_the_row(brazos, dana):
    """A channel whose address the platform cannot resolve is a REPORTABLE
    ABSENCE — not a skipped row and not a placeholder.

    `recipient_not_resolvable`, never `no_postal_address`: the first is a fact
    about this platform, the second would be a claim about a customer nobody
    checked. The dispatch home has to be able to count them apart.

    AMENDED 2026-08-11 (W4/W8 customers ACTION lane), and the amendment is
    hard-won law 1. This test used to assert `recipient_read_unpublished` — the
    problem code meaning *"customers publishes no recipient read at all"* — and
    that claim STOPPED BEING TRUE when
    `apps.customers.selectors.delivery_recipients_for_account` landed. The read
    is published now and it is CONSULTED, which is why the code is gone from
    `problems`.

    What has not changed is the ROW, and that is the assertion worth keeping:
    the fixture account has no mailing address, and B2 §2 makes an absent
    mailing row mean *"same as service"* — so the account HAS a postal address
    and customers still cannot render it as an envelope (metering publishes no
    structured premises-address read; `_premise_cell` is a display string for a
    list column). The read therefore answers `recipient_not_resolvable` on
    purpose, and `no_postal_address` — the claim about the customer — is still
    never inferred.

    ⚠ **AMENDED 2026-09-23 (`DEF-PAY-6342`) — THE PARAGRAPH ABOVE IS NO LONGER
    TRUE AND THE ROW IS NOW ADDRESSED.** Metering publishes the structured read
    (`envelope_addresses`), so the fixture account's bill goes to its premises
    with `source: service_address` — B2 §2's *"same as service"*, which the
    recipient read claimed and did not do. What this test still defends is the
    same thing it always did: the print row is WRITTEN and never skipped, and
    never carries `no_postal_address` for an account that has a premises. The
    platform-gap spelling is `test_us_not_001_tc8`'s, produced by unpublishing
    the read. The row is taken by CHANNEL: a bill also queues a portal copy
    (`CR-084`), so `get(source_id=…)` alone had found two rows since then.
    """
    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(brazos, dana)

        row = outbound.OutboundMessage.objects.get(
            source_id=billed.pk, channel=outbound.CHANNEL_PRINT
        )
        assert row.recipient_address
        assert row.unavailable_reason is None
        assert row.recipient_snapshot["source"] == "service_address"
        codes = {entry["code"] for entry in billed.delivery.problems}
        # The read RESOLVES now, so "nobody could look" is no longer emitted.
        assert "recipient_read_unpublished" not in codes


# ── CLAUDE.md rule 6 — a double-clicked release queues nothing twice ────────
def test_us_bil_023_tc5__a_second_release_of_the_same_bill_queues_no_second_copy(brazos, dana):
    """CLAUDE.md rule 6 · US-NOT-001 TC-5.

    Issue itself refuses a bill that is no longer a draft, so the double-click
    that actually reaches the queue is a RE-RELEASE: the same issued bill handed
    to the delivery path again by a retried job or a resumed batch. It must find
    its own row and write nothing.

    A duplicate is not cosmetic — it is a second paper bill from the print
    vendor, at the vendor's per-piece price, and a customer ringing to ask which
    one they owe.

    Proved RED first: with the service's pre-check blinded and its
    `IntegrityError` recovery removed, this failed with
    `django.db.utils.IntegrityError: UNIQUE constraint failed:
    outbound_messages.tenant_id, outbound_messages.source_type,
    outbound_messages.source_id, outbound_messages.channel,
    outbound_messages.copy_no`.

    ⚠ **THE THREE FIGURES BELOW WERE `1` UNTIL 2026-09-24 (`DEF-BIL-6456`) —
    `CR-084`'s portal copy makes every bill two rows.** The guarantee is
    unchanged and is if anything stronger: the re-release finds BOTH of its own
    rows and writes neither.
    """
    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(brazos, dana)
        assert len(billed.delivery.queued) == 2

        again = delivery_seam.queue_bill_delivery(billed)

        assert again.queued == ()
        assert len(again.already_queued) == 2
        assert outbound.OutboundMessage.objects.filter(source_id=billed.pk).count() == 2
        assert sorted(
            outbound.OutboundMessage.objects.filter(source_id=billed.pk).values_list(
                "channel", flat=True
            )
        ) == [outbound.CHANNEL_PRINT, outbound.CHANNEL_PORTAL]


def test_us_bil_023_tc5b__a_staff_re_send_is_a_new_row_and_is_numbered(brazos, dana):
    """US-BIL-024 TC-4 — a deliberate re-send of a delivered bill *"creates new
    queue rows, audited"*, and only a human's explicit copy number opens that
    door. An automatic writer always leaves `copy_no=0` and therefore collides.

    ⚠ **THE RE-SEND IS TWO ROWS SINCE `CR-084`, NOT ONE (`DEF-BIL-6456`).** A
    staff re-send re-queues the bill on every channel the bill goes out on, so
    copy 1 is a paper copy AND a portal copy — asserted by CHANNEL as well as by
    copy number, because `[0, 0, 1, 1]` alone would also be satisfied by two
    paper copies, which is the duplicate `tc5` forbids.
    """
    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(brazos, dana)

        resend = delivery_seam.queue_bill_delivery(billed, copy_no=1)

        assert len(resend.queued) == 2
        rows = outbound.OutboundMessage.objects.filter(source_id=billed.pk).order_by(
            "copy_no", "channel"
        )
        assert [(row.copy_no, row.channel) for row in rows] == [
            (0, outbound.CHANNEL_PRINT),
            (0, outbound.CHANNEL_PORTAL),
            (1, outbound.CHANNEL_PRINT),
            (1, outbound.CHANNEL_PORTAL),
        ]


# ── R2 queues; R4 sends ─────────────────────────────────────────────────────
def test_us_bil_023_tc6__issuing_dispatches_nothing(brazos, dana):
    """US-BIL-023 TC-6 (*"a code path attempts a direct synchronous send at
    issue"* → forbidden) and BR-BIL-016's *"mass sends are never synchronous"*.

    Read from the dispatcher's own columns rather than from a docstring. This
    is the case that goes RED the day a send is added to the issue path — which
    is R4's work (email ACTIVATION on the B12 release table), not R2's, and is
    an outward-facing action a build agent must not take on its own.
    """
    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(brazos, dana)

        assert billed.delivery.dispatched is False
        assert "nothing_was_dispatched" in {entry["code"] for entry in billed.delivery.unavailable}
        # ⚠ **`get(source_id=…)` ALONE RAISED `MultipleObjectsReturned` FROM
        # 2026-09-07 (`DEF-BIL-6456`)** — a bill has a portal row beside its
        # print row since `CR-084`. Both are read, because *nothing was sent*
        # has to be true of BOTH or the rule is only half proved.
        rows = list(outbound.OutboundMessage.objects.filter(source_id=billed.pk))
        assert sorted(row.channel for row in rows) == [
            outbound.CHANNEL_PRINT,
            outbound.CHANNEL_PORTAL,
        ]
        for row in rows:
            assert row.status == outbound.STATUS_QUEUED
            assert row.batch_id is None
            assert row.attempts == 0
            assert (
                row.sent_at,
                row.provider_reference,
                row.provider_response,
                row.last_error,
            ) == (None, None, None, None)


def test_us_bil_023_tc7__a_scheduled_release_carries_its_time_onto_the_rows(brazos, dana):
    """S31 step 6's *"send now vs scheduled"*: either way the queue is the only
    path. The choice rides `dispatch_not_before` on the rows and delays nothing
    else — the bill is billed when it is billed, and only its DELIVERY waits.

    ⚠ **READ BY CHANNEL SINCE 2026-09-24 (`DEF-BIL-6456`)** — `CR-084`'s portal
    copy made the bare `get(source_id=…)` raise `MultipleObjectsReturned`. The
    schedule has to ride EVERY row, so every row is checked rather than the
    first one found."""
    from datetime import UTC, datetime

    when = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(brazos, dana, dispatch_not_before=when)

        rows = list(outbound.OutboundMessage.objects.filter(source_id=billed.pk))
        assert sorted(row.channel for row in rows) == [
            outbound.CHANNEL_PRINT,
            outbound.CHANNEL_PORTAL,
        ]
        for row in rows:
            assert row.dispatch_not_before == when
            assert row.status == outbound.STATUS_QUEUED
        assert billed.issued_at == ISSUED_AT  # the ISSUE was not delayed


# ── the seam's refusals are BILLING's, so one bill never kills a run ────────
def test_us_bil_023_tc8__an_unpublished_queue_refuses_the_issue_as_a_named_break(
    brazos, dana, monkeypatch
):
    """DEF-047's lesson applied to this boundary: a callee's refusal type is
    part of its contract.

    `issue_run` catches `BillingRuleError` and nothing else, so a refusal in
    notifications' own vocabulary would kill a run of five hundred bills over
    one row. Translated at the seam, it is one named break and the run carries
    on (BR-BIL-055).

    The bill must NOT issue: an issued bill is immutable, so one committed
    without its delivery record is a bill nobody would ever be sent and no
    later path would notice.
    """
    monkeypatch.setattr(delivery_seam, "_resolve", lambda *args, **kwargs: None)
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = an_authorised_run(brazos, dana)
        account = an_account(dana, brazos, account_no="A-1042")
        draft = a_priced_draft(brazos, account, run, invoice_no="BL-2607-000101")

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )

        assert result.issued == ()
        assert len(result.broken) == 1
        assert result.broken[0].reason == issue.ISSUE_DELIVERY_UNQUEUEABLE
        assert delivery_seam.QUEUE_WRITE in result.broken[0].detail
        # …and the draft is STILL A DRAFT — the whole transaction rolled back.
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT
        assert outbound.OutboundMessage.objects.count() == 0


def test_us_bil_023_tc9__a_bill_with_no_pin_cannot_be_queued(brazos, dana):
    """BR-BIL-026 from the delivery side. A queue row that cannot name the
    template version it renders from is a row whose document can never be
    reproduced — and the pin freezes with the money, so it can never be added
    afterwards. Refused in billing's own exception type."""
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = an_authorised_run(brazos, dana)
        account = an_account(dana, brazos, account_no="A-1042")
        unpinned = a_priced_draft(brazos, account, run, invoice_no="BL-2607-000101")

        with pytest.raises(BillingRuleError, match="carries no template pin"):
            delivery_seam.queue_bill_delivery(unpinned)
        assert outbound.OutboundMessage.objects.count() == 0


# ── hard rule 7 ─────────────────────────────────────────────────────────────
def test_us_bil_023_tc10__the_queue_write_is_audited_beside_the_issue(brazos, dana, audit_rows):
    """CLAUDE.md rule 7. Issuing a bill is a money action and so is promising to
    deliver it: both trail rows land in the SAME transaction, so neither the
    bill nor its delivery record can stand without evidence of who made it.

    ⚠ **TWO TRAIL ROWS SINCE `CR-084`, NOT ONE (`DEF-BIL-6456`).** Every queue
    row is its own promise to deliver, so the portal copy earns its own audit
    row — and the rule is *every* money action, which is why both are asserted
    rather than the count loosened."""
    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(brazos, dana)

        actions = [row["action"] for row in audit_rows]
        assert "invoice.issued" in actions
        queued = [row for row in audit_rows if row["action"] == "outbound_message.queued"]
        assert len(queued) == 2
        assert sorted(row["after"]["channel"] for row in queued) == [
            outbound.CHANNEL_PRINT,
            outbound.CHANNEL_PORTAL,
        ]
        for row in queued:
            assert row["after"]["source_id"] == str(billed.pk)
            assert row["after"]["dispatched"] is False


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-023@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 #8 ·
#         EP-BIL-06-templates-delivery.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by story-coder (W3 delivery-queue lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — `GET /invoices/{id}/deliveries` is US-BIL-024) E=deferred(no-frontend-half — S30's dashboard is US-BIL-024) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST — the print floor (`CHANNEL_FLOOR_BY_SOURCE` emptied)
#         and the idempotency guard (pre-check blinded + `IntegrityError`
#         recovery removed) were each broken, the suite run, and the measured
#         failure quoted in this lane's report before either was trusted green
# exceptions: (1) EVERY BILL PRODUCES EXACTLY ONE ROW on this deployment — the
#         print floor. `tc2` drives the elected-channel path with a stubbed
#         customers read so the wiring is proved rather than hoped for; the real
#         read (`accounts.paperless`) WAS PROPOSED-SCHEMA and unbuilt; it landed
#         2026-08-31 (migration customers 0034, CR-052 task 14) and tc1b/tc3 are
#         amended to the answer rather than the absence.
#         (2) NO CASE ASSERTS ANYTHING ABOUT DISPATCH. There is no dispatcher
#         (US-NOT-002); `tc6` asserts precisely that nothing was sent rather
#         than leaving the absence to be inferred.
#         (3) TENANT ISOLATION of the write path is
#         `tests/test_us_not_001_queue_write_isolation.py` — it needs live
#         Postgres and a non-superuser probe role, which sqlite cannot give.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
