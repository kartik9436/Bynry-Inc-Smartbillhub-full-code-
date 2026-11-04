# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-002 (the dispatcher: tenant-config batches, provider pacing,
#           retry ×3 with backoff, idempotent dispatch)   Screens: S8 · S30
# Rules:    BR-NOT-005 (batches at the provider's pace; forward-only statuses;
#           retry ×3 backoff) · BR-BIL-016 (batch default 500, tenant-config;
#           mass sends are never synchronous) · BR-NOT-009 (quiet hours;
#           print/PDF exempt) · BR-TEN-043 (event time is the caller's, never a
#           clock read) · CLAUDE.md rule 6 (a replayed or crashed dispatch never
#           sends twice) · rule 7 (the hand-off is audited)
# ───────────────────────────────────────────────────────
"""What one dispatch cycle does — and the four things it must never do.

THE FOUR CASES A GREEN SUITE COULD MOST EASILY FAKE were each broken
deliberately and run before being trusted (hard-won law 7); the verbatim
failures are in the lane report and the review-ledger row.

  * **Pacing.** The rule exists because an ESP cannot absorb platform-speed
    generation. The case queues 1,200 rows and asserts the hand-off carried 500
    — measured at the ADAPTER, not at the dispatcher's own arithmetic.
  * **Idempotency.** Not a double-clicking user: a job that committed and was
    retried. The case runs two cycles over one row and asserts the second sent
    nothing, and the crash case asserts a row claimed by a dead cycle is never
    handed over again.
  * **Quiet hours.** The case fires at 22:15 tenant time and asserts ZERO
    provider calls — the assertion is on the adapter's call log, because a
    dispatcher that "decided not to send" and called anyway is the incident.
  * **Forward-only.** `sent → queued` is refused, which is what makes the
    re-queue ACTION the only reset there is.

TWO TEST DOUBLES, BOTH STANDING IN FOR STORIES THAT ARE NOT BUILT, both named
so nobody reads them as production behaviour:

  `stub_adapter`  — `apps.integrations.services.dispatch_outbound_batch`
                    (US-NOT-003's provider adapter; integrations is three
                    docstrings). The seam idiom `apps/tenancy/seams.py`
                    documents: integration tests re-stub the neighbour.
  `stub_templates`— `rendering.render_for_dispatch` (US-NOT-006's template
                    store). Without it the dispatcher holds every row, which is
                    the RATIFIED behaviour and is asserted on its own below.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from apps.notifications import dispatch_config, dispatcher, models, provider_seam, rendering

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_cr049_t2_dispatch_freeze import provider_connected  # noqa: F401 — shared fixture

pytestmark = pytest.mark.django_db

#: A fixed moment inside Brazos Bend's seeded 08:00–21:00 window. 15:00 UTC is
#: 10:00 in America/Chicago (CDT in August), which is why every case names its
#: moment instead of reading a clock (BR-TEN-043).
INSIDE_WINDOW = datetime(2026, 8, 9, 15, 0, tzinfo=dt_timezone.utc)
#: 03:15 UTC on Aug 10 = 22:15 on Aug 9 in America/Chicago — T5-23's fixture
#: moment, when a clerk fires a bulk reminder run.
OUTSIDE_WINDOW = datetime(2026, 8, 10, 3, 15, tzinfo=dt_timezone.utc)


class StubAdapter:
    """A provider that records what it was handed. US-NOT-003's seam, stubbed.

    It records CALLS, not messages, because the pacing rule is about hand-offs:
    "500 messages in one call" and "500 calls of one message" are the same
    number of messages and opposite compliance with BR-NOT-005.
    """

    def __init__(self, *, outcome="sent", raises=None):
        self.calls: list[tuple[str, tuple]] = []
        self.outcome = outcome
        self.raises = raises

    def __call__(self, channel, messages):
        self.calls.append((channel, messages))
        if self.raises is not None:
            raise self.raises
        if self.outcome == "sent":
            return {
                m["id"]: {"provider_reference": f"prov-{m['id'][:8]}", "status": "sent"}
                for m in messages
            }
        return {
            m["id"]: {"status": "failed", "error": "provider timeout", "retryable": True}
            for m in messages
        }

    @property
    def batch_sizes(self):
        return [len(messages) for _channel, messages in self.calls]


@pytest.fixture()
def stub_adapter(monkeypatch, provider_connected):
    """Publish US-NOT-003's unwritten adapter for the length of one test.

    ⚠ **AND SAY THE TENANT HAS CONNECTED A PROVIDER — `provider_connected`,
    ADDED 2026-09-30.** From 2026-09-04 (`d471e8680`, `CR-069` wave E) the
    route asks two questions, *is there an adapter?* and *has THIS tenant
    connected a provider?*, and a stubbed adapter alone answers only the first.
    Without the second, every row in this file rested `queued` on
    `provider_not_connected` — correct for a real utility with no connection
    (A15 addendum: no shared sender), and fatal to every case here that wanted
    a hand-off. Dated: this file's send-path cases passed at the parent
    `2d771c61d` and failed at `d471e8680`.
    """
    from apps.integrations import services as integrations_services

    adapter = StubAdapter()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    return adapter


@pytest.fixture()
def stub_templates(monkeypatch):
    """Stand in for US-NOT-006's template store, which is not built.

    Returns an artifact with a rendered body so the dispatcher has something to
    hand over. The REAL behaviour without this double — dispatch holds on a
    missing published template — is asserted by
    `test_us_not_002_the_cycle_holds_every_row_while_no_template_store_exists`.
    """

    def render(row):
        return rendering.RenderedArtifact(
            template_code=row.template_code or "receipt",
            template_version=row.template_version or 1,
            language=row.template_language,
            channel=row.channel,
            body="Your balance is 12.00 USD",
        )

    monkeypatch.setattr(rendering, "render_for_dispatch", render)


def queue_rows(tenant, count, *, channel=models.CHANNEL_PRINT, **overrides):
    """`count` queued rows, straight into the table.

    The WRITE path (`services.queue_document`, its print floor and its
    idempotency key) is `test_us_not_001_queue_write.py`'s subject; these cases
    are about what the dispatcher does with rows that already exist, and 1,200
    of them through the service would test the writer twice.
    """
    values = dict(
        tenant_id=tenant.id,
        source_type="invoice",
        channel=channel,
        template_code="bill_residential",
        template_id=uuid.uuid4(),
        template_version=3,
        template_language="en-US",
        recipient_address="1901 Bluestem Ln, Katy TX 77494",
        status=models.STATUS_QUEUED,
    )
    values.update(overrides)
    rows = [models.OutboundMessage(source_id=uuid.uuid4(), **values) for _index in range(count)]
    return models.OutboundMessage.objects.bulk_create(rows)


# ── TC-1 · pacing — the rule's reason to exist ──────────────────────────────
def test_us_not_002_tc1__a_cycle_hands_over_at_most_the_tenant_batch_size(
    brazos, stub_adapter, stub_templates
):
    """US-NOT-002 TC-1 · T5-24 step 2: *"Max messages per provider hand-off ≤
    500 … NEVER one burst."*

    1,200 rows are queued in one generation burst. The cycle hands over 500, in
    ONE call, and leaves the other 700 queued for the next cycle — draining is
    the scheduler's job at the provider's pace, not a loop in the dispatcher.

    PROVED RED by removing the `[:limit]` slice from `_claim`: the adapter then
    recorded a single hand-off of 1,200 and this failed with
    `assert [1200] == [500]`.
    """
    with tenant_ctx(brazos):
        queue_rows(brazos, 1200)
        result = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

        assert result.batch_size == 500  # BR-BIL-016's seeded default
        assert stub_adapter.batch_sizes == [500]
        assert result.sent == 500
        assert models.OutboundMessage.objects.filter(status=models.STATUS_QUEUED).count() == 700
        # Every sent row carries the batch it went out in and when (r10 #8).
        sent = models.OutboundMessage.objects.filter(status=models.STATUS_SENT)
        assert sent.count() == 500
        assert sent.filter(batch_id__isnull=True).count() == 0
        assert sent.filter(sent_at__isnull=True).count() == 0
        assert sent.filter(provider_reference__isnull=True).count() == 0


# ── TC-2 · the size is CONFIG, not a constant ───────────────────────────────
def test_us_not_002_tc2__the_next_cycle_honours_a_changed_batch_size(
    brazos, dana, stub_adapter, stub_templates
):
    """US-NOT-002 TC-2 · T7-17 step 4: *"config read per dispatch cycle"*.

    The batch size moves 500 → 200 between two cycles and the second hand-off
    is 200. The first hand-off is untouched — T7-17 step 3: a batch already
    given to a provider is a fact and is never clawed back or re-cut.
    """
    with tenant_ctx(brazos):
        queue_rows(brazos, 900)
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

        dispatch_config.update_dispatch_settings(actor=dana, dispatch_batch_size=200)
        dispatcher.dispatch_cycle(
            now=INSIDE_WINDOW + timedelta(minutes=1), channels=(models.CHANNEL_PRINT,)
        )

        assert stub_adapter.batch_sizes == [500, 200]


# ── TC-3 · retry ×3 with backoff, then failed with the provider error ───────
def test_us_not_002_tc3__a_failing_provider_is_retried_three_times_then_the_row_fails(
    brazos, monkeypatch, stub_templates, provider_connected
):
    """US-NOT-002 TC-3: *"Retry ×3 with backoff (attempts counter + next-attempt
    time); after the 3rd failure status `failed` + provider error stored."*

    Six rows time out. Cycles 1 and 2 leave them `queued` with a growing
    next-attempt time; cycle 3 rests them at `failed` with the error visible to
    the dashboard.

    PROVED RED by raising `MAX_ATTEMPTS` to 4: the third cycle then left six
    rows `queued` and this failed with `assert 0 == 6` on the failed count.
    """
    from apps.integrations import services as integrations_services

    adapter = StubAdapter(outcome="failed")
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)

    with tenant_ctx(brazos):
        queue_rows(brazos, 6)
        at = INSIDE_WINDOW
        for attempt in (1, 2, 3):
            dispatcher.dispatch_cycle(now=at, channels=(models.CHANNEL_PRINT,))
            rows = list(models.OutboundMessage.objects.all())
            assert {row.attempts for row in rows} == {attempt}
            if attempt < dispatcher.MAX_ATTEMPTS:
                assert {row.status for row in rows} == {models.STATUS_QUEUED}
                # Backoff: the row is not eligible again until its time comes.
                expected = at + timedelta(minutes=dispatcher.BACKOFF_MINUTES[attempt - 1])
                assert {row.next_attempt_at for row in rows} == {expected}
                at = expected
        rows = list(models.OutboundMessage.objects.all())
        assert {row.status for row in rows} == {models.STATUS_FAILED}
        assert {row.last_error for row in rows} == {"provider timeout"}
        # A rested row has no next attempt: only the re-queue ACTION moves it.
        assert {row.next_attempt_at for row in rows} == {None}


def test_us_not_002_tc3b__a_backed_off_row_is_not_selected_before_its_time(
    brazos, monkeypatch, stub_templates, provider_connected
):
    """The other half of the backoff: it must actually hold the row back.

    A second cycle one minute after the failure hands over NOTHING — T5-24 step
    3, *"it does NOT hammer the provider"*.
    """
    from apps.integrations import services as integrations_services

    adapter = StubAdapter(outcome="failed")
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)

    with tenant_ctx(brazos):
        queue_rows(brazos, 3)
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))
        dispatcher.dispatch_cycle(
            now=INSIDE_WINDOW + timedelta(minutes=1), channels=(models.CHANNEL_PRINT,)
        )
        assert adapter.batch_sizes == [3]  # one hand-off, not two


# ── TC-4 · idempotent dispatch (CLAUDE.md rule 6) ───────────────────────────
def test_us_not_002_tc4__a_replayed_cycle_sends_nothing_twice(brazos, stub_adapter, stub_templates):
    """CLAUDE.md rule 6 · US-NOT-002 TC-4: *"Dispatcher crashes mid-batch and
    re-runs → No row sent twice."*

    The scenario is a JOB that committed and was retried — it does not call the
    dispatcher with a flag set, so the guarantee has to live in the claim.

    ⚠ WHAT THE RED PROOF ACTUALLY SHOWED, recorded because it is not what the
    first draft of this docstring claimed. Neutering the `_selectable` predicate
    on the claim UPDATE alone does NOT break this case: the SELECT that picks
    candidates carries the same predicate, so single-threaded the rows are never
    re-offered. That predicate is a RACE guard — it earns its place against a
    concurrent cycle, not against a replay — and saying otherwise would have
    left the wrong line looking load-bearing.

    Neutering the SELECT's two guards (`status = queued` and the
    batch-id/next-attempt branch) is what breaks it, and the failure is worth
    quoting because a SECOND guard caught it:

        E  apps.notifications.dispatcher.ForwardOnlyViolation: a queue row
           cannot move sent → sent. The lifecycle is forward-only (BR-NOT-005) …

    A double-send therefore has to get past selection AND the forward-only
    transition table. `test_us_not_002_tc4b` is the case where the claim's own
    guard is the only thing standing.
    """
    with tenant_ctx(brazos):
        queue_rows(brazos, 3)
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))
        second = dispatcher.dispatch_cycle(
            now=INSIDE_WINDOW + timedelta(minutes=30), channels=(models.CHANNEL_PRINT,)
        )

        assert stub_adapter.batch_sizes == [3]
        assert second.sent == 0
        assert models.OutboundMessage.objects.filter(status=models.STATUS_SENT).count() == 3
        assert {row.attempts for row in models.OutboundMessage.objects.all()} == {1}


def test_us_not_002_tc4b__a_row_claimed_by_a_crashed_cycle_is_never_handed_over_again(
    brazos, stub_adapter, stub_templates
):
    """The crash half of TC-4, and the trade this design makes on purpose.

    A row stamped with a batch id and left `queued` is a hand-off whose outcome
    nobody knows. It is NEVER selected again: re-sending on the chance it did
    not arrive would post a second disconnect notice to a customer who already
    has one (CLAUDE.md rule 6 outranks liveness). The row is stuck until
    US-NOT-013's re-queue exists to clear its batch — REPORTED in the lane
    report and in this module's Lifecycle trailer.

    PROVED RED by replacing the batch-id/next-attempt branch of `_selectable`
    with `Q(pk__isnull=False)`: the crashed row was handed to the provider a
    second time and this failed with

        E  AssertionError: assert [('pdf_print', ({'id': '01a006c5-…',
           'channel': 'pdf_print', 'address': '1901 Bluestem Ln, Katy TX 77494',
           …},))] == []
    """
    with tenant_ctx(brazos):
        [row] = queue_rows(brazos, 1)
        models.OutboundMessage.objects.filter(pk=row.pk).update(
            batch_id=uuid.uuid4(), attempts=1, last_attempt_at=INSIDE_WINDOW
        )
        result = dispatcher.dispatch_cycle(
            now=INSIDE_WINDOW + timedelta(hours=6), channels=(models.CHANNEL_PRINT,)
        )

        assert stub_adapter.calls == []
        assert result.claimed == 0
        row.refresh_from_db()
        assert row.status == models.STATUS_QUEUED


# ── TC-5 · forward-only statuses ────────────────────────────────────────────
def test_us_not_002_tc5__a_status_never_moves_backwards():
    """US-NOT-002 TC-5: *"Direct status write `sent → queued` outside the
    re-queue action → Rejected — forward-only lifecycle."*

    PROVED RED by making `ALLOWED_TRANSITIONS` permissive: `sent → queued` was
    then accepted and this failed with `Failed: DID NOT RAISE`.
    """
    dispatcher.forward_only(models.STATUS_QUEUED, models.STATUS_SENT)
    dispatcher.forward_only(models.STATUS_SENT, models.STATUS_DELIVERED)
    dispatcher.forward_only(models.STATUS_SENT, models.STATUS_BOUNCED)

    # ⚠ **THE FOUR NORMALISED OUTCOMES (`DEF-NOT-5626`, 2026-09-17).** All four
    # are reachable from `sent`, because a provider can only report on a message
    # we handed it.
    for outcome in (
        models.STATUS_BOUNCED_HARD,
        models.STATUS_BOUNCED_SOFT,
        models.STATUS_COMPLAINED,
        models.STATUS_UNSUBSCRIBED,
    ):
        dispatcher.forward_only(models.STATUS_SENT, outcome)

    # ⚠ **AND TWO ARE REACHABLE FROM `delivered`, WHICH IS THE PAIR WORTH
    # ARGUING ABOUT.** A spam complaint and an unsubscribe both need the
    # consumer to have RECEIVED the mail, so the provider reports `delivered`
    # first and the complaint minutes or days later. Refusing that move leaves a
    # complaint on a delivered message with nowhere to go.
    dispatcher.forward_only(models.STATUS_DELIVERED, models.STATUS_COMPLAINED)
    dispatcher.forward_only(models.STATUS_DELIVERED, models.STATUS_UNSUBSCRIBED)

    for current, target in (
        (models.STATUS_SENT, models.STATUS_QUEUED),
        (models.STATUS_DELIVERED, models.STATUS_SENT),
        (models.STATUS_FAILED, models.STATUS_QUEUED),
        (models.STATUS_BOUNCED, models.STATUS_QUEUED),
        # A mailbox cannot both accept a message and refuse it. A provider
        # telling us both about one message is a provider we have misread, and
        # the refusal is how we find out instead of overwriting a delivery.
        (models.STATUS_DELIVERED, models.STATUS_BOUNCED_HARD),
        (models.STATUS_DELIVERED, models.STATUS_BOUNCED_SOFT),
        # Every one of the four is an END. Only the re-queue ACTION reopens a
        # row, and it refuses three of them by vocabulary — see
        # `delivery_ops.REQUEUEABLE_STATUSES`.
        (models.STATUS_BOUNCED_HARD, models.STATUS_QUEUED),
        (models.STATUS_BOUNCED_SOFT, models.STATUS_QUEUED),
        (models.STATUS_COMPLAINED, models.STATUS_QUEUED),
        (models.STATUS_UNSUBSCRIBED, models.STATUS_QUEUED),
    ):
        with pytest.raises(dispatcher.ForwardOnlyViolation):
            dispatcher.forward_only(current, target)


# ── TC-6 · scheduled sends ──────────────────────────────────────────────────
def test_us_not_002_tc6__a_row_scheduled_for_september_is_skipped_in_an_august_cycle(
    brazos, stub_adapter, stub_templates
):
    """US-NOT-002 TC-6: *"Row with dispatch-not-before = Sep 1 in an Aug 9 cycle
    → Skipped — not selected until its time."*
    """
    with tenant_ctx(brazos):
        queue_rows(brazos, 2)
        queue_rows(
            brazos,
            1,
            dispatch_not_before=datetime(2026, 9, 1, 12, 0, tzinfo=dt_timezone.utc),
        )
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

        assert stub_adapter.batch_sizes == [2]
        held = models.OutboundMessage.objects.filter(dispatch_not_before__isnull=False).get()
        assert held.status == models.STATUS_QUEUED
        assert held.batch_id is None
        assert held.attempts == 0


# ── BR-NOT-009 · quiet hours (T5-23) ────────────────────────────────────────
def test_us_not_002_tc7__email_holds_outside_the_send_window_and_print_does_not(
    brazos, dana, stub_adapter, stub_templates
):
    """BR-NOT-009 · T5-23 steps 2–3: at 22:15 tenant time email/SMS HOLD and
    print/PDF is EXEMPT — *"no send attempt, no provider traffic, statuses
    unchanged … retry counters untouched (nothing was attempted)"*.

    The assertion is on the ADAPTER's call log, because a dispatcher that
    decided not to send and called anyway is the incident itself.

    PROVED RED by adding `email` to `QUIET_HOURS_EXEMPT_CHANNELS`: the 22:15
    cycle then handed four email rows to the provider and this failed with
    `assert ['pdf_print', 'email'] == ['pdf_print']`.
    """
    with tenant_ctx(brazos):
        # Email must be switched ON for this case, or the DEFERRAL (US-NOT-003)
        # would hold the rows first and prove nothing about quiet hours.
        dispatch_config.update_dispatch_settings(actor=dana, email_dispatch_active=True)
        queue_rows(brazos, 3, channel=models.CHANNEL_PRINT)
        queue_rows(brazos, 4, channel=models.CHANNEL_EMAIL)

        result = dispatcher.dispatch_cycle(
            now=OUTSIDE_WINDOW, channels=(models.CHANNEL_PRINT, models.CHANNEL_EMAIL)
        )

        assert [channel for channel, _messages in stub_adapter.calls] == [models.CHANNEL_PRINT]
        assert [
            problem["code"]
            for problem in result.problems
            if problem["code"] == dispatcher.CYCLE_QUIET_HOURS_HOLD
        ] == [dispatcher.CYCLE_QUIET_HOURS_HOLD]
        email_rows = models.OutboundMessage.objects.filter(channel=models.CHANNEL_EMAIL)
        assert {row.status for row in email_rows} == {models.STATUS_QUEUED}
        assert {row.attempts for row in email_rows} == {0}


def test_us_not_002_tc8__the_window_in_force_at_dispatch_governs(
    brazos, dana, stub_adapter, stub_templates
):
    """T5-23 step 6 / T7-16 step 3: widening the window releases tonight's held
    queue at the NEW edge — a config edit is future-dispatch-only and is never
    itself a send trigger.

    22:15 holds under 08:00–21:00. Widened to 06:00–23:00, the same moment
    dispatches — proving the window is read at dispatch and not frozen when the
    row was queued.
    """
    from datetime import time

    with tenant_ctx(brazos):
        dispatch_config.update_dispatch_settings(actor=dana, email_dispatch_active=True)
        queue_rows(brazos, 2, channel=models.CHANNEL_EMAIL)
        dispatcher.dispatch_cycle(now=OUTSIDE_WINDOW, channels=(models.CHANNEL_EMAIL,))
        assert stub_adapter.calls == []

        dispatch_config.update_dispatch_settings(
            actor=dana, quiet_hours_start=time(6, 0), quiet_hours_end=time(23, 0)
        )
        result = dispatcher.dispatch_cycle(now=OUTSIDE_WINDOW, channels=(models.CHANNEL_EMAIL,))
        assert stub_adapter.batch_sizes == [2]
        assert result.sent == 2


# ── what this deployment actually does — asserted, not assumed ──────────────
def test_us_not_002_the_cycle_holds_every_row_while_no_template_store_exists(brazos, stub_adapter):
    """Field map N-1: *"dispatch holds safely on missing published template;
    content never invented."*

    WITHOUT the `stub_templates` double, `render_for_dispatch` refuses every
    row — `notification_templates` is US-NOT-006 and is not built. The cycle
    contacts no provider, the rows keep their place, and no attempt is burned:
    a missing template is configuration, not a provider outage, and must never
    walk a row towards `failed`.
    """
    with tenant_ctx(brazos):
        queue_rows(brazos, 4)
        result = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

        assert stub_adapter.calls == []
        assert result.dispatched is False
        assert dispatcher.CYCLE_RENDER_HELD in {problem["code"] for problem in result.problems}
        rows = list(models.OutboundMessage.objects.all())
        assert {row.status for row in rows} == {models.STATUS_QUEUED}
        assert {row.attempts for row in rows} == {0}
        assert {row.batch_id for row in rows} == {None}


def test_us_not_002_nothing_dispatches_at_all_with_no_provider_adapter(brazos, stub_templates):
    """The deployment's real state, asserted rather than described.

    This read, until 2026-09-30: *"`apps/integrations` holds three docstrings
    and no code, so the ONE adapter (TD-8) resolves to nothing for EVERY
    channel — print included."*

    ⚠ **AMENDED 2026-09-30, TWICE, AND THE SECOND AMENDMENT UNDID THE FIRST.**
    That sentence stopped being literally true on 2026-09-04:
    `d471e8680` (`CR-069` wave E) published
    `apps.integrations.services.dispatch_outbound_batch`, and this case went
    red that day because print then reported `provider_not_connected`. The
    first amendment read that as the new truth and moved the assertion to it.
    **It was not the truth — it was `DEF-NOT-8451`.** No print provider can be
    connected on this platform (no adapter is bound to any print manifest, so
    the card answers *Cannot be connected yet.*), so telling a utility its print
    provider is "not connected" sends a clerk to Settings to fix something that
    is not theirs to fix — the confusion the two codes exist to prevent. With
    that defect fixed, print reports `provider_status_unknown` again, which is
    what this case asserted from the start. **So the assertion below is the
    original one, restored, and it is now a guard on `DEF-NOT-8451`.**
    """
    with tenant_ctx(brazos):
        queue_rows(brazos, 5)
        result = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

        assert result.dispatched is False
        codes = {problem["code"] for problem in result.problems}
        assert provider_seam.ROUTE_PROVIDER_STATUS_UNKNOWN in codes
        assert provider_seam.ROUTE_PROVIDER_NOT_CONNECTED not in codes
        assert {row.status for row in models.OutboundMessage.objects.all()} == {
            models.STATUS_QUEUED
        }


def test_us_not_002_a_row_with_no_recipient_address_is_never_selected_and_is_counted(
    brazos, stub_adapter, stub_templates
):
    """BR-BIL-036 · OQ-208 — the gap migration 0001 named as the dispatcher's.

    A row whose recipient could not be resolved has nowhere to go. It is not
    selected (there is no address to send to) and it is COUNTED on the cycle
    result, so a dispatch home can show it rather than leaving a silent
    difference between the queue depth and what moves.
    """
    with tenant_ctx(brazos):
        queue_rows(brazos, 2)
        queue_rows(
            brazos,
            1,
            recipient_address=None,
            unavailable_reason=models.REASON_NOT_RESOLVABLE,
        )
        result = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

        assert stub_adapter.batch_sizes == [2]
        unaddressed = [
            problem
            for problem in result.problems
            if problem["code"] == dispatcher.CYCLE_NO_RECIPIENT
        ]
        assert len(unaddressed) == 1 and unaddressed[0]["count"] == 1


def test_us_not_002_a_raising_provider_backs_the_whole_batch_off_and_loses_nothing(
    brazos, monkeypatch, stub_templates, provider_connected
):
    """T5-24 step 3 — the 429: *"Dispatcher backs off and retries ×3 with
    backoff — it does NOT drop the batch, does NOT hammer the provider, does
    NOT fail the run."*
    """
    from apps.integrations import services as integrations_services

    adapter = StubAdapter(raises=RuntimeError("429 Too Many Requests"))
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)

    with tenant_ctx(brazos):
        queue_rows(brazos, 4)
        result = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

        assert dispatcher.CYCLE_ADAPTER_RAISED in {p["code"] for p in result.problems}
        rows = list(models.OutboundMessage.objects.all())
        assert len(rows) == 4  # nothing dropped
        assert {row.status for row in rows} == {models.STATUS_QUEUED}
        assert {row.attempts for row in rows} == {1}
        assert {row.next_attempt_at for row in rows} == {
            INSIDE_WINDOW + timedelta(minutes=dispatcher.BACKOFF_MINUTES[0])
        }


def test_us_not_002_a_silent_provider_is_a_failure_and_never_a_send(
    brazos, monkeypatch, stub_templates, provider_connected
):
    """Silence is not success — an adapter that answers for no row has told us
    nothing, and marking such a row `sent` would report a delivery on the
    strength of a missing dictionary key."""
    from apps.integrations import services as integrations_services

    monkeypatch.setattr(
        integrations_services,
        "dispatch_outbound_batch",
        lambda channel, messages: {},
        raising=False,
    )

    with tenant_ctx(brazos):
        queue_rows(brazos, 2)
        result = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

        assert result.sent == 0
        assert dispatcher.CYCLE_PROVIDER_SILENT in {p["code"] for p in result.problems}
        assert {row.status for row in models.OutboundMessage.objects.all()} == {
            models.STATUS_QUEUED
        }


def test_us_not_002_a_hand_off_is_audited_without_any_pii(
    brazos, stub_adapter, stub_templates, audit_rows
):
    """Hard rule 7 · BR-AUD-006. One row per HAND-OFF naming the batch, the
    channel and the counts — never an address, a phone number or a name."""
    with tenant_ctx(brazos):
        queue_rows(brazos, 3)
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

    dispatched = [row for row in audit_rows if row["action"] == dispatcher.AUDIT_ACTION]
    assert len(dispatched) == 1
    payload = dispatched[0]["after"]
    assert payload["channel"] == models.CHANNEL_PRINT and payload["sent"] == 3
    assert "1901 Bluestem Ln, Katy TX 77494" not in str(dispatched[0])


def test_us_not_002_a_cycle_without_a_tenant_context_is_refused():
    """CLAUDE.md rule 1. A dispatcher is a JOB — the caller most likely to run
    outside a request — and an unscoped drain would hand one utility's letters
    to another utility's provider."""
    from core import errors

    with pytest.raises(errors.AuthError):
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW)


def test_us_not_002_held_rows_are_skipped_and_counted_on_every_cycle(brazos, dana):
    """⚠ RE-SCOPED 2026-08-15 (notifications CONTENT lane), and the supersession
    is the point of the case.

    This case used to be `test_us_not_002_the_absent_held_marker_is_reported_on_
    every_cycle` and it asserted that every cycle emits
    `held_marker_not_implemented`, because BR-PAY-018's suppression column was
    US-NOT-014's and unbuilt — hard-won law 1: *"a suppression nobody
    implemented and nobody mentioned is how a letter goes to an address already
    known to be wrong."*

    **The column is built now** (migration 0007) and the dispatcher skips held
    rows through `delivery_ops.selectable_filter()`. The report did not go away
    with it: a cycle that holds letters back SILENTLY is only marginally better
    than one that never held them, so the problem row was replaced rather than
    deleted — it now carries the COUNT of what was actually skipped.

    ⚠ WHAT THIS CASE PROVES AND WHAT IT DOES NOT — corrected after MEASURING it,
    which is the reason hard-won law 7 exists. Removing
    `delivery_ops.selectable_filter()` from `_selectable` leaves this case GREEN,
    because a full `dispatch_cycle` on this deployment stops at the missing
    provider adapter BEFORE it ever claims a row: `batch_id is None` here is true
    whether the held filter exists or not. So this case proves the REPORT (the
    count reaches the operator) and nothing more, and the first draft of this
    docstring claimed otherwise.

    The claim-level proof — that the dispatcher cannot SEE a held row — is
    `test_us_not_014_tc3_tc4__paper_is_held_then_released_on_verification` in
    `tests/test_us_not_013_015_delivery_ops.py`, which calls `_claim` directly.
    With the filter removed it fails: `assert [<OutboundMessage …>] == []`.
    """
    from apps.notifications import delivery_ops

    with tenant_ctx(brazos):
        held_row = queue_rows(brazos, 1, channel=models.CHANNEL_PRINT)[0]
        held_row.held = True
        held_row.held_reason = delivery_ops.HELD_BAD_ADDRESS
        held_row.save(update_fields=["held", "held_reason"])

        result = dispatcher.dispatch_cycle(now=INSIDE_WINDOW)

        held_row.refresh_from_db()
        assert held_row.status == models.STATUS_QUEUED
        assert held_row.batch_id is None  # never claimed
        assert held_row.attempts == 0  # nothing was attempted

    reported = [p for p in result.problems if p["code"] == dispatcher.CYCLE_HELD_ROWS_SKIPPED]
    assert reported and reported[0]["count"] == 1
