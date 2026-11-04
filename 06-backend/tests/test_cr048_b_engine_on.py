# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-002 (the dispatcher) × US-NOT-017 (SET-12 / SET-12D) ×
#           US-NOT-018 (ONE message per bulk action)
#           CR-048 wave B, tasks B4 · B5 · B7 · B8 · B9   Screens: S8 · SET-12
# Rules:    BR-NOT-020 (one message per bulk action, whatever the item count) ·
#           BR-NOT-021 (the ruled staff audience: the initiator, plus every
#           System Admin on failure) · BR-NOT-019 (in_app is a real channel and
#           the one that delivers) · BR-NOT-017 (ONE HOME — the rule the queue
#           now reads) · BR-NOT-013 (no provider adapter on print, email or
#           SMS — they rest queued with a reason) · BR-NOT-005 (queue only, no
#           synchronous send anywhere) · BR-TEN-043 (no wall clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency)
# ───────────────────────────────────────────────────────
"""CR-048 wave B — **the first thing in this product that works end to end.**

The CR's own summary of where this module stood: *"in-app is the one channel
that genuinely delivers today … The gap is not quality; it is the last hop and
one missing join."* Wave A closed the join. This file is the last hop.

FIVE TASKS, AND WHAT EACH ONE HAS TO PROVE

**B4 · the two staff events fire in-app.** A bulk action queues ONE message as
its SET-12 event, the utility's rule is read on the way, and the message lands
in the bell. The end-to-end case below runs a two-hundred-item bulk action,
asserts the bell is EMPTY, runs one dispatch cycle, and asserts the bell holds
exactly one row — which is the whole product in six lines.

**B5 · the dispatcher has a schedule.** Asserted twice, because "the schedule is
correct" and "the schedule is installed" are two different claims and hard-won
law 2 is the gap between them: the entry's shape, and its presence on the celery
app after `AppConfig.ready()` has run.

**B7 · Send test.** ⚠ **ALREADY BUILT before this wave** — `rule_service.
queue_test` and `POST /notification-rules/{event}/queue-test` both shipped with
CR-009 and DEF-265. Nothing here rebuilds it; the cases below PIN the behaviour
CR-048 B7 asks for, so that the thing already true stays true.

**B8 · the provider boundary still refuses.** Print, email and SMS rest
`queued`, each with the seam's own reason, so nobody later mistakes a queued row
for a sent one. A test and not a change.

**B9 · coverage as data.** Three counts on the wire. The third is DERIVED and
the case below proves the derivation rather than the number: if a future event
names one of the sixteen classes, the count must fall on its own.

NOTHING HERE SENDS ANYTHING TO ANYBODY OUTSIDE THIS BUILDING. Every case that
dispatches restricts itself to `in_app`, the platform's own adapter, or asserts
that the other three channels did not move.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import (
    bulk_summary,
    dispatcher,
    in_app,
    models,
    provider_seam,
    rule_catalog,
    rule_service,
    schedule,
    seed_templates,
    services,
)

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — the moment is NAMED, never read from a clock, so every window
#: and schedule decision in these cases is made against the same instant.
FINISHED_AT = datetime(2026, 8, 29, 18, 5, tzinfo=dt_timezone.utc)

#: The size of the bulk action. Big enough that "one row per item" would be
#: unmistakable in the count, and it is the CR's own example shape.
BULK_ITEMS = 200


def _seeded(actor):
    seed_templates.seed_notice_templates(actor, on_date=FINISHED_AT.date())


def _a_bill_run(actor, *, failed: int = 0, run_id=None):
    """A REAL bulk action: iterate, count, and then ONCE say what happened.

    The loop is the point. Every bulk caller in the product has this shape, and
    the thing BR-NOT-020 forbids is a `queue_document` inside it.
    """
    processed = 0
    failures = 0
    for index in range(BULK_ITEMS):
        processed += 1
        if index < failed:
            failures += 1
    return bulk_summary.queue_billing_run_summary(
        run_id=run_id or uuid.uuid4(),
        total_count=processed,
        failed_count=failures,
        finished_at=FINISHED_AT,
        actor=actor,
    )


# ══════════════════════════════════════════════════════════════════════════
# B4 · THE TWO STAFF EVENTS FIRE, IN-APP, END TO END
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b4__the_event_keys_are_the_catalogue_s_and_not_the_cr_s(brazos, dana):
    """**The CR calls it `billing_run_finished`. SET-12 has no such row.**

    The catalogue is a CONSTANT — *"a tenant cannot invent an event, because
    only a writer in this codebase can fire one"* — and a writer cannot invent
    one either. A lane that took the CR's own spelling literally would have
    queued nothing and found out at the end of a thousand-account bill run,
    because `queue_document` refuses an unknown key.

    So both keys this module fires are checked against the vocabulary here, at
    the cheapest possible moment.
    """
    assert bulk_summary.EVENT_BILLING_RUN in rule_catalog.EVENT_KEYS
    assert bulk_summary.EVENT_RECONCILIATION in rule_catalog.EVENT_KEYS
    assert "billing_run_finished" not in rule_catalog.EVENT_KEYS

    for key in (bulk_summary.EVENT_BILLING_RUN, bulk_summary.EVENT_RECONCILIATION):
        event = rule_catalog.event(key)
        assert event.audience == rule_catalog.AUDIENCE_STAFF
        assert models.CHANNEL_IN_APP in event.channels, (
            f"{key} must offer the in-app channel — it is the one channel that "
            "delivers, and firing a staff event on a channel that rests queued "
            "would be a notification nobody ever sees."
        )


def test_cr048_b4__a_bill_run_puts_exactly_one_message_in_the_bell(brazos, dana):
    """**THE HEADLINE CASE. Empty bell → a bulk action → one row in the bell.**

    Nothing is stubbed: the real queue write, the real rule read, the real
    dispatcher, the real in-app adapter, the real inbox read the shell's bell
    calls. Two hundred accounts processed, one message.

    The three assertions in order are the three things that were each separately
    missing before this wave: the bell is empty because nothing fired the event;
    ONE row is queued because BR-NOT-020 says so; and the row REACHES the bell
    because a cycle ran.
    """
    with tenant_ctx(brazos):
        _seeded(dana)

        # 1 · Today, before anything fires: the bell is empty.
        assert in_app.unread_count(actor=dana) == 0

        # 2 · A bulk action over two hundred accounts. ONE queue row.
        before = models.OutboundMessage.objects.count()
        summary = _a_bill_run(dana, failed=3)
        queued = models.OutboundMessage.objects.count() - before
        assert queued == 1, (
            f"a bill run over {BULK_ITEMS} accounts queued {queued} messages. "
            "BR-NOT-020 allows exactly one — a clerk who receives two hundred "
            "notifications switches the event off, and the three failures they "
            "needed to see are the ones they never get."
        )
        assert summary.event_key == bulk_summary.EVENT_BILLING_RUN
        assert summary.created is True
        assert in_app.unread_count(actor=dana) == 0, (
            "a queued message is not a delivered one — the bell must still be "
            "empty until a dispatch cycle runs."
        )

        # 3 · One cycle. The message arrives.
        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)
        assert in_app.unread_count(actor=dana) == 1
        items = in_app.inbox(actor=dana)
        assert len(items) == 1
        body = items[0].body
        assert str(BULK_ITEMS) in body, (
            "the summary must state how many records the run touched — "
            f"expected {BULK_ITEMS} in: {body!r}"
        )
        assert "3" in body, (
            "BR-NOT-020's other half: *'where the operation had failures it must "
            "say HOW MANY'*. A summary that hides the failure count is the same "
            f"failure as sending two hundred messages. Body was: {body!r}"
        )


def test_cr048_b4__switching_the_event_off_stops_the_message(brazos, dana):
    """**CR-048's headline, applied to the one channel that delivers.**

    *"Switching 'Bill ready — email' off on the settings screen changes nothing
    at all"* was the finding. Here it changes everything: a System Admin who
    switches the billing-run notification off stops receiving it, and the run
    is TOLD that is what happened rather than the message vanishing.

    This is also the RED/GREEN pair for B4's join. Before the event key was
    passed, this case queued a message with the rule switched off.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        rule_service.update_rule(
            event_key=bulk_summary.EVENT_BILLING_RUN, actor=dana, enabled=False
        )

        before = models.OutboundMessage.objects.count()
        summary = _a_bill_run(dana, failed=0)
        assert models.OutboundMessage.objects.count() == before, (
            "the utility switched this notification off and a message was queued "
            "anyway — which is the defect CR-048 exists to fix, in the one place "
            "where it can actually be seen."
        )
        assert summary.message_id is None
        assert summary.suppressed_by_rule is True
        assert summary.problems, (
            "a suppressed message must SAY it was suppressed. A rule obeyed so "
            "quietly that a run report cannot mention it is the same screen "
            "lying in the other direction."
        )
        detail = " ".join(problem["detail"] for problem in summary.problems)
        assert "Settings" in detail, (
            "the reason must tell a person what to do about it, in their own "
            f"words. Got: {detail!r}"
        )

        # And nothing reaches the bell either, which is the point of the whole
        # exercise: the setting screen now governs a real delivery.
        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)
        assert in_app.unread_count(actor=dana) == 0


def test_cr048_b4__the_reconciliation_event_fires_the_same_way(brazos, dana):
    """The second staff event, through its own named entry point.

    Zero exceptions is still ONE message: a clerk who sees nothing cannot tell a
    clean reconciliation from one that never ran.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        before = models.OutboundMessage.objects.count()
        summary = bulk_summary.queue_reconciliation_summary(
            run_id=uuid.uuid4(),
            total_count=48,
            failed_count=0,
            finished_at=FINISHED_AT,
            actor=dana,
        )
        assert models.OutboundMessage.objects.count() - before == 1
        assert summary.event_key == bulk_summary.EVENT_RECONCILIATION
        assert summary.operation == bulk_summary.OPERATION_RECONCILIATION

        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)
        assert in_app.unread_count(actor=dana) == 1


def test_cr048_b4__a_retried_run_still_says_it_once(brazos, dana):
    """CLAUDE.md rule 6 survives the event key.

    The join added a read; it must not have added a write path. A resumed or
    retried bill run finds its own message and writes nothing — the DATABASE
    refuses the second, which is the only guarantee that holds for a retry that
    never called this function twice at all.
    """
    run_id = uuid.uuid4()
    with tenant_ctx(brazos):
        _seeded(dana)
        first = _a_bill_run(dana, failed=1, run_id=run_id)
        before = models.OutboundMessage.objects.count()
        second = _a_bill_run(dana, failed=1, run_id=run_id)

        assert models.OutboundMessage.objects.count() == before
        assert second.created is False
        assert second.message_id == first.message_id


def test_cr048_b4__a_caller_that_names_no_event_is_unchanged(brazos, dana):
    """The pre-B4 call shape still means exactly what it meant.

    `manage.py send_bulk_summary` and every CR-009 test call
    `queue_bulk_summary` with no event key, and the rule join must be invisible
    to them — the same contract wave A wrote for `queue_document`. Read this
    case as the guard on a promise, not as an endorsement: it asserts that no
    rule is consulted, which is TODAY's behaviour for a caller that has not been
    wired yet.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        rule_service.update_rule(
            event_key=bulk_summary.EVENT_BILLING_RUN, actor=dana, enabled=False
        )
        summary = bulk_summary.queue_bulk_summary(
            operation="Billing run",
            operation_id=uuid.uuid4(),
            total_count=10,
            failed_count=0,
            finished_at=FINISHED_AT,
            actor=dana,
        )
        assert summary.event_key is None
        assert summary.message_id is not None, (
            "a caller that names no event must be byte-identically unaffected by "
            "the rule join, switched-off event or not."
        )
        assert summary.suppressed_by_rule is False


# ══════════════════════════════════════════════════════════════════════════
# B5 · THE DISPATCHER HAS A SCHEDULE
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b5__the_schedule_names_the_fanout_task_and_an_interval():
    """The schedule's SHAPE, with no celery and no broker in sight.

    A beat entry that named a task nobody registered would be a message beat
    publishes and no worker consumes — and the broker reports that as success.
    """
    entry = schedule.beat_schedule(every_seconds=300)[schedule.BEAT_ENTRY]
    assert entry["task"] == schedule.FANOUT_TASK
    assert entry["schedule"] == 300.0
    assert schedule.dispatch_every_seconds() == schedule.DEFAULT_DISPATCH_EVERY_SECONDS


def test_cr048_b5__a_nonsense_interval_is_ignored_rather_than_obeyed(monkeypatch):
    """`0` would be beat firing continuously — the platform-speed burst
    BR-NOT-005 exists to forbid, arriving through a typo in an environment
    file. It falls back to the default and logs, rather than pacing at no pace.
    """
    monkeypatch.setenv(schedule.DISPATCH_EVERY_SECONDS_ENV, "0")
    assert schedule.dispatch_every_seconds() == schedule.DEFAULT_DISPATCH_EVERY_SECONDS
    monkeypatch.setenv(schedule.DISPATCH_EVERY_SECONDS_ENV, "not-a-number")
    assert schedule.dispatch_every_seconds() == schedule.DEFAULT_DISPATCH_EVERY_SECONDS
    monkeypatch.setenv(schedule.DISPATCH_EVERY_SECONDS_ENV, "60")
    assert schedule.dispatch_every_seconds() == 60


def test_cr048_b5__the_schedule_is_actually_installed_on_the_celery_app():
    """**Hard-won law 2 — built is not wired, asserted as two claims.**

    The case above proves the schedule is correct. This one proves something
    calls it: `NotificationsConfig.ready()` runs on every process that could be
    beat, and without that line the entry is a dict nobody reads while
    `docker-compose.yml`'s *"it has nothing to fire yet"* stays true.

    RED PROOF: with the `schedule.install()` call removed from `ready()`, this
    read `KeyError: 'notifications.dispatch'`.
    """
    from config.celery import app

    installed = dict(getattr(app.conf, "beat_schedule", None) or {})
    assert schedule.BEAT_ENTRY in installed, (
        "celery beat has no dispatch entry, so the queue never drains on its own "
        "and the bell fills only when an operator types a command."
    )
    assert installed[schedule.BEAT_ENTRY]["task"] == schedule.FANOUT_TASK
    assert app.tasks.get(schedule.FANOUT_TASK) is not None, (
        "beat would publish a message no worker consumes, and the broker would "
        "report that as success."
    )
    assert app.tasks.get(schedule.DISPATCH_TASK) is not None


def test_cr048_b5__with_no_tenant_configured_the_firing_says_so(monkeypatch):
    """An empty fan-out must REPORT, not look healthy.

    This module cannot ask *"who are all the tenants?"* — B1 forbids reading
    `tenancy.Tenant` from here and tenancy publishes no live-tenant read, which
    is why `dispatch_outbound` has no `--all-tenants` either. So the list is
    operator configuration, and an unset one is the state DEF-320 was: a path
    that looked provisioned and consumed nothing.

    The sentence carries no id and no code, because whoever reads it is
    wondering why their bell is empty.
    """
    monkeypatch.delenv(schedule.DISPATCH_TENANTS_ENV, raising=False)
    result = schedule.dispatch_all()
    assert result["dispatched"] == 0
    assert result["problem"] == schedule.NO_TENANTS_CONFIGURED
    for forbidden in ("BR-", "OQ-", "DEF-", "_", "()"):
        assert forbidden not in schedule.NO_TENANTS_CONFIGURED, (
            "a refusal a person reads must be plain words — no ids, no codes: "
            f"found {forbidden!r} in {schedule.NO_TENANTS_CONFIGURED!r}"
        )


def test_cr048_b5__the_configured_tenants_are_read_in_order_and_deduplicated(monkeypatch):
    """The same subdomain twice would be two cycles per interval for one utility
    and nothing downstream would notice — each cycle claims its own batch
    perfectly legitimately."""
    monkeypatch.setenv(schedule.DISPATCH_TENANTS_ENV, " Silver-Creek , brazos,silver-creek ,, ")
    assert schedule.scheduled_subdomains() == ("silver-creek", "brazos")


# ══════════════════════════════════════════════════════════════════════════
# B7 · SEND TEST — ALREADY BUILT. THESE CASES PIN IT.
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b7__send_test_writes_one_real_row_to_the_signed_in_user(brazos, dana):
    """*"Writes ONE real queue row addressed to the signed-in user."*

    Not a preview and not a simulation: the real single write path, the real
    template pin, a real row on `outbound_messages`. `in_app` is used because it
    is the channel with an address that always exists — the signed-in user's own
    id (DEF-265 fixed exactly this: the one channel that delivers was the one
    channel the test button refused).
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        before = models.OutboundMessage.objects.count()
        result = rule_service.queue_test(
            event_key=bulk_summary.EVENT_BILLING_RUN,
            channel=models.CHANNEL_IN_APP,
            actor=dana,
        )
        assert models.OutboundMessage.objects.count() - before == 1
        assert result.queued is True
        assert result.message_id is not None
        assert result.recipient_address == in_app.address_for(dana), (
            "a test goes to YOU and to nobody else — a test send that reached a "
            "customer would be a real message with the word 'test' in it."
        )


def test_cr048_b7__send_test_reports_that_it_will_not_be_delivered_and_why(brazos, dana):
    """*"…and reports back that it will not be delivered, and why."*

    `will_be_delivered` is `provider_seam`'s own verdict rather than a sentence
    this surface wrote. A result reading only *"queued: true"* would tell a
    System Admin who just clicked the button that a test email is on its way.

    ⚠ **THIS DOCSTRING SAID "False on EVERY channel" AND WAS WRONG ABOUT ONE OF
    THE FOUR (`DEF-NOT-4525`, 2026-09-07).** It is False on mail, text message
    and print, which have no provider connected — this case asserts EMAIL and is
    unchanged. It was never true of `in_app`, where this application is the
    provider (BR-NOT-019), and the wire said so anyway because the field was a
    literal. It is read off `dispatchable` now.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        wire = rule_service.queue_test(
            event_key="bill_ready", channel=models.CHANNEL_EMAIL, actor=dana
        ).as_wire()

    assert wire["will_be_delivered"] is False
    assert wire["dispatchable"] is False
    assert wire["problem"] is not None
    assert wire["problem"]["detail"], "a refusal with no reason is not a refusal"


def test_cr048_b7__send_test_is_reachable_over_http_and_no_send_route_exists(brazos, dana):
    """The route is `queue-test` because it QUEUES. BR-NOT-005 and A11 r2 §4 make
    a synchronous send endpoint a gate failure, so the absence is asserted
    alongside the presence — a name is a contract here."""
    from django.urls import Resolver404, resolve

    from apps.notifications import rules_api

    paths = {str(entry.pattern) for entry in rules_api.urlpatterns}
    assert "notification-rules/<str:event_key>/queue-test" in paths

    for forbidden in ("send", "test-send"):
        with pytest.raises(Resolver404):
            resolve(f"/api/{brazos.subdomain}/notification-rules/bill_ready/{forbidden}")


# ══════════════════════════════════════════════════════════════════════════
# B8 · THE PROVIDER BOUNDARY STILL REFUSES
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "channel",
    [models.CHANNEL_PRINT, models.CHANNEL_EMAIL, models.CHANNEL_SMS],
)
def test_cr048_b8__the_three_provider_channels_are_not_dispatchable(brazos, channel):
    """Each of the three, with its own reason, from the seam itself.

    `active=True` is deliberate — this asks *"if a utility switched this channel
    ON, would anything leave?"* and the answer must still be no, because the
    absence is the PLATFORM having no adapter rather than the tenant having no
    provider. The two are counted apart so a utility is never told to fix a
    connection that is not theirs to fix.
    """
    with tenant_ctx(brazos):
        route = provider_seam.channel_route(channel, active=True)
    assert route.dispatchable is False
    assert route.problem is not None
    assert route.problem["detail"], (
        f"{channel} refuses without saying why, so a queued row and a lost row "
        "look identical on the dispatch home."
    )


def test_cr048_b8__only_in_app_has_an_adapter(brazos):
    """The one channel that delivers, and the three that do not — as values.

    BR-NOT-019: this application IS the provider for `in_app`, so its adapter
    always exists. `apps/integrations` holds three docstrings and no code, so
    the other three resolve to None.
    """
    with tenant_ctx(brazos):
        assert provider_seam.adapter(models.CHANNEL_IN_APP) is not None
        for channel in (
            models.CHANNEL_PRINT,
            models.CHANNEL_EMAIL,
            models.CHANNEL_SMS,
        ):
            assert provider_seam.adapter(channel) is None


def test_cr048_b8__a_queued_print_row_rests_queued_after_a_full_cycle(brazos, dana):
    """**The case that stops a queued row being mistaken for a sent one.**

    A print row is written, a full four-channel cycle runs, and the row is still
    `queued` afterwards — with the cycle naming the reason. Nothing is lost,
    nothing is failed, and nothing left the building. That is the correct
    finished state of a bill run on this deployment, not a backlog.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        write = services.queue_document(
            source_type="notice",
            source_id=uuid.uuid4(),
            channels=(models.CHANNEL_PRINT,),
            template=services.TemplatePin(code="dunning"),
            recipients=(
                services.Recipient(channel=models.CHANNEL_PRINT, address="1 Mill Road, Brazos"),
            ),
            actor=dana,
            job="cr048_b8",
        )
        row_id = write.messages[0].id

        result = dispatcher.dispatch_cycle(now=FINISHED_AT, actor=dana, job="cr048_b8")
        row = models.OutboundMessage.objects.get(pk=row_id)

    assert row.status == models.STATUS_QUEUED, (
        f"a {models.CHANNEL_PRINT} row moved to {row.status!r} on a deployment "
        "with no print vendor. Somebody would read that as posted."
    )
    codes = {problem["code"] for problem in result.problems}
    assert codes, "a cycle that moved nothing must say why it moved nothing"
    for batch in result.batches:
        if batch.channel == models.CHANNEL_IN_APP:
            continue
        assert batch.sent == 0, (
            f"{batch.channel} reported {batch.sent} sent, and no adapter exists "
            "for it on this deployment."
        )


# ══════════════════════════════════════════════════════════════════════════
# B9 · COVERAGE, AS DATA
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b9__the_three_counts_are_on_the_wire():
    """*"as data in the response, not a note somebody remembers."*"""
    coverage = rule_catalog.coverage()
    # ⚠ THE FIRST AND THIRD FIGURES MOVED TWICE ON 2026-08-30, AND THAT IS THE
    # POINT OF THEM. They read 15 and 16 when B9 landed; wave B10 added three
    # events (`move_in_welcome`, `move_out_final_bill`,
    # `payment_plan_instalment_missed`) and the pair became 18 and 13; wave B11
    # then adopted the remaining thirteen classes and the pair became **30 and
    # 0**, with nobody editing a number — which is exactly what the case below
    # exists to guarantee. The figures are asserted rather than derived here so
    # that a movement is DELIBERATE: a lane that closes a gap updates this line
    # and says which event closed it.
    #
    # **WHICH EVENTS CLOSED WHICH GAP, so the movement is checkable and not
    # merely asserted.** B11 added TWELVE events and one channel:
    #   · billing      — `statement_ready` (email_statement, refused: OQ-1160)
    #   · payments     — `refund_issued` (email_refund_issued, live) ·
    #                    `credit_issued` (email_credit_issued, live) ·
    #                    `autopay_enrolled` (email_autopay, refused: OQ-1162) ·
    #                    and SMS added to the EXISTING `payment_received`, which
    #                    is what adopts `sms_payment_received` without a new row
    #   · collections  — `payment_plan_instalment_upcoming` (plan_notice_upcoming,
    #                    live) · `payment_plan_voided` (plan_notice_void,
    #                    refused: OQ-1163) · `write_off_approved`
    #                    (writeoff_notice, live)
    #   · field work   — `door_hanger_left` (service_door_hanger, refused:
    #                    OQ-249) · `planned_outage_notice`
    #                    (service_outage_notice, refused: OQ-1161)
    #   · lifecycle    — `account_closed` (email_account_closed, live) ·
    #                    `deposit_received` (email_deposit, live) ·
    #                    `rate_plan_changed` (email_plan_change, live)
    # 18 + 12 = 30, and 13 − 13 = 0.
    # ⚠ **31 SINCE 2026-09-23.** `CR-136-BRC07` `P2.11` added
    # `counter_left_open` — staff & system, LIVE, reusing the
    # `staff_bulk_summary` class the other two bulk events already name. It
    # adds no SEEDED WORDING, so `seeded_wording_without_rule_count` below is
    # untouched by it: 30 + 1 = 31, and the tie-out one line down still stands.
    assert coverage["built_event_count"] == 31
    assert coverage["requirement_claims_event_count"] == 16
    assert coverage["seeded_wording_without_rule_count"] == 0
    # The derived figure and the 2026-08-29 teardown's own figure PARTED COMPANY
    # on 2026-08-30, and that is progress rather than drift — the teardown
    # counted a gap of 16 and three of them now have rules. This used to assert
    # the two were EQUAL; equality was the right check only while nothing had
    # been closed, and left as it was it would have gone red on the first lane
    # that did its job. So it reconciles instead: the teardown's figure minus
    # what has since been adopted must be what is left.
    # 3 (B10) + 13 (B11) = 16, so this side of the tie-out is now the whole of
    # the teardown's own figure and the derived side is zero. Both ends of the
    # bridge are exercised for the first time on this commit.
    adopted_since_the_teardown = 16
    assert (
        coverage["seeded_wording_without_rule_count"] + adopted_since_the_teardown
        == coverage["teardown_claims_seeded_wording_without_rule_count"]
    ), (
        "the gap and the teardown's figure no longer reconcile. The DERIVED one "
        "is the true one — but the difference must be explainable by rules that "
        "were ADDED, and a lane that adopts a seeded wording bumps the number "
        "above. An unexplained difference means a wording was renamed or "
        "dropped, which is a different thing entirely and worth stopping for."
    )


def test_cr048_b9__the_third_count_is_derived_and_not_typed_in():
    """**The count must fall on its own when wave B10/B11 lands.**

    B10 adds three events and B11 adds thirteen, and each that names a seeded
    class takes that class out of the gap. A hardcoded 16 would have to be
    edited sixteen more times by sixteen different hands; the one that is
    forgotten leaves the settings screen reporting a gap already closed.

    Proved by simulating exactly that: name one of the sixteen from a fake event
    and watch the count drop to fifteen, with that class gone from the list.
    """
    # ⚠ RE-POINTED TWICE ON 2026-08-30, THE SECOND TIME BY THIS CASE'S OWN
    # INSTRUCTION AND FROM THE OTHER DIRECTION. It probed with `email_welcome`
    # (adopted by B10), then with `email_deposit` (adopted by B11) — and B11
    # closed the gap COMPLETELY, so there is no longer any class left in it to
    # point at. The docstring's *"re-point at a class that is"* has run out of
    # classes, which is success and not breakage.
    #
    # **So the probe is INVERTED and it defends the same property harder.**
    # Instead of adding an event and watching the gap FALL, it removes the event
    # that names a class and watches the gap RISE from zero to one, with that
    # exact class in the list. A hardcoded number could not do this either way,
    # and this direction has a bonus the old one did not: it proves the gap is
    # genuinely EMPTY rather than merely reported as empty, because a derivation
    # that had silently stopped measuring would stay at zero here.
    before = rule_catalog.seeded_wording_without_rule()
    assert before == (), (
        "wave B11 closed this gap to zero on 2026-08-30 and it is "
        f"{sorted(before)} now. If a NEW wording has been seeded, give it an "
        "event row and append it to ADOPTED_SINCE_TEARDOWN; if a rule was "
        "removed, that is what this case is telling you."
    )

    original = rule_catalog.EVENTS
    dropped = "email_deposit"
    try:
        rule_catalog.EVENTS = tuple(
            row for row in original if dropped not in row.template_classes.values()
        )
        assert len(rule_catalog.EVENTS) == len(original) - 1, (
            f"exactly one event should name {dropped!r}; the probe removed "
            f"{len(original) - len(rule_catalog.EVENTS)}."
        )
        after = rule_catalog.seeded_wording_without_rule()
    finally:
        rule_catalog.EVENTS = original

    assert after == (dropped,), (
        f"removing the only event that names {dropped!r} should put exactly that "
        f"class back in the gap; it reported {sorted(after)}. A count that does "
        "not move when its input does is a typed-in number wearing a function."
    )
    assert (
        rule_catalog.seeded_wording_without_rule() == before
    ), "the probe leaked — the catalogue must be back exactly as it was."


def test_cr048_b9__every_writer_reached_class_is_still_a_class_we_seed():
    """The exclusion list cannot rot silently.

    `WRITER_REACHED_CLASSES` names four classes that a live writer sends by some
    route other than a SET-12 rule. If one is renamed or dropped, the entry
    stops excluding anything and the count quietly grows by one with no defect
    anywhere — so the list is checked against the seed catalogue instead.
    """
    seeded = {seed.code for seed in seed_templates.SEEDABLE}
    unknown = sorted(set(rule_catalog.WRITER_REACHED_CLASSES) - seeded)
    assert not unknown, (
        f"{unknown} are excluded from the coverage gap as 'a live writer sends "
        "them', and this platform no longer seeds wording for them. Either the "
        "class was renamed or the writer is gone; both make the count wrong."
    )
    for code, reason in rule_catalog.WRITER_REACHED_CLASSES.items():
        assert len(reason) > 40, (
            f"{code} is excluded from the count with no explanation worth "
            "reading. An unexplained exclusion is how a count starts lying."
        )


def test_cr048_b9__the_coverage_block_reaches_the_settings_response(brazos, dana):
    """It has to be on the RESPONSE, not merely computable.

    Hard-won law 2 again: a derivation nothing serves is a note in a nicer
    format.
    """
    from apps.notifications import rules_api

    with tenant_ctx(brazos):
        posture = rules_api._release_posture()

    coverage = posture["coverage"]
    assert coverage["built_event_count"] == rule_catalog.BUILT_EVENT_COUNT
    assert coverage["seeded_wording_without_rule_count"] == len(
        coverage["seeded_wording_without_rule"]
    ), "the count and the list must be the same fact, not two facts"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B tasks B4/B5/B7/B8/B9 (12-governance/11-change-requests.md → CR-048 steps 4 and 5 · apps/notifications/bulk_summary.py BR-NOT-020 · apps/notifications/rule_catalog.py the fifteen events · apps/notifications/provider_seam.py channel_route · apps/notifications/services.py channel_decision, CR-048 wave A)
# generated: 2026-08-29 by story-coder (CR-048 wave B notifications lane)
# checklist: A✔ B=deferred(no-API-half — this is the test half) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every case proved RED before green (hard-won law 7); the four proofs are quoted in the lane report — B4's end-to-end read `assert 0 == 1` on the bell with no trigger; B4's rule case queued a message with the event switched off; B5's install case read `KeyError: 'notifications.dispatch'` with the `ready()` line removed; B9's derivation case read `assert 15 == 16` with the non-message kind counted.
# exceptions: (1) B7 WAS ALREADY BUILT. `rule_service.queue_test` and `POST /notification-rules/{event}/queue-test` shipped with CR-009 and DEF-265; nothing in this wave rebuilt them and these cases PIN the behaviour B7 asks for rather than proving new work. Said plainly because a lane reporting B7 as delivered without saying so would be claiming somebody else's work.
#         (2) NO CALLER IN BILLING OR PAYMENTS YET. B4 builds the two named entry points and proves them end to end; the bill run and the reconciliation run that will call them live in sibling modules this lane does not own. REPORTED — hard-won law 2, and the honest half of "visibly working from day one".
#         (3) NOTHING HERE SENDS. Every dispatching case restricts itself to `in_app` or asserts the other three channels did not move (B8).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
