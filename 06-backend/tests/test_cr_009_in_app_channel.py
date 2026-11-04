# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — the in-app channel end to end: queue → route →
#           render → dispatch → inbox → read)   Screens: shell-chrome · S8
# Rules:    BR-NOT-019 (in-app is a real channel and the PLATFORM is its
#           provider) · BR-NOT-005 + A11 r2 §4 (queue only — no send route) ·
#           BR-NOT-013 (the OTHER three channels still have no adapter, and this
#           must not quietly change) · BR-TEN-017 (delivered artifact is a
#           snapshot) · CLAUDE.md rule 6 (one delivery per message per inbox)
# ───────────────────────────────────────────────────────
"""The PO's own acceptance test, as code.

PO, 2026-08-17: *"We can confirm it whether it is working on not if we get in
APp Notifcaition, which does not require any integration and it is proof that
notification is working."*

So the test to read first is
`test_us_not_018_tc3__a_staff_event_travels_queue_to_inbox_and_can_be_read`. It fires a
real bulk operation, drains the REAL dispatcher, and then asserts a person can
read the message and mark it read. Everything else here guards one link of that
chain against being quietly weakened.

⚠ **THE SECOND-MOST IMPORTANT TEST IS THE ONE ABOUT THE OTHER CHANNELS.**
`test_us_not_018_tc2__the_other_three_channels_are_unchanged` exists because the easiest
way to make in-app "work" would have been to loosen `channel_route` or to stub an
adapter, and BR-NOT-013 forbids exactly that: *"no lane is to build or fake an
adapter to turn a test green."* Email, SMS and print must still refuse, for the
same reasons, on the same codes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest
from django.urls import Resolver404, resolve

from apps.notifications import (
    bulk_summary,
    dispatch_config,
    dispatcher,
    in_app,
    in_app_api,
    models,
    provider_seam,
    rendering,
    seed_templates,
)

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

FINISHED_AT = datetime(2026, 8, 17, 21, 40, tzinfo=dt_timezone.utc)


def _call(view, method, tenant, actor, role="system_admin", **kwargs):
    return api_call(
        view, method, user=getattr(actor, "user", None), role=role, tenant=tenant, **kwargs
    )


def _seeded(actor):
    """Publish the platform bodies, the way provisioning does. The in-app class
    is seeded like every other one — a template a lane special-cased for its own
    test would prove nothing about a real tenant."""
    seed_templates.seed_notice_templates(actor, on_date=FINISHED_AT.date())


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE CHANNEL EXISTS AND IS THE FIRST ONE THAT CAN DELIVER
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_018_tc1__in_app_is_the_fourth_channel_and_the_only_dispatchable_one(brazos, dana):
    """BR-NOT-019. Until 2026-08-17 `models.CHANNELS` was exactly three and
    `rule_catalog` recorded the honest reason — *"there is no in-app
    notification surface"*. The FACT that changed is asserted here.

    ⚠ **THE COUNT MOVED 4 → 5 ON 2026-09-07 (`CR-084`) AND THE NAME OF THIS TEST
    IS NOW HALF WRONG.** In-app is still the fourth channel; it is no longer the
    ONLY dispatchable one, because the customer portal joined it as a second
    platform-delivered channel. The name is kept rather than corrected, because
    renaming a test loses the history of what it was written to catch — the
    figure it asserts is what has to be true, and it is asserted below.

    ⚠ **AND THIS TEST WAS RED FROM 2026-09-04 TO 2026-09-07 (`DEF-NOT-4532`)**
    on the `route.dispatchable` assertion five lines down, with the message its
    own docstring predicted — *"NOTHING in this product can deliver"*. Six of
    this file's twelve tests were red and three lanes ran the suite past them.
    That is hard-won law 7's *proved red, then never read*: the guard did its
    job perfectly and nobody was reading its output.
    """
    assert models.CHANNEL_IN_APP in models.CHANNELS
    assert len(models.CHANNELS) == 5

    with tenant_ctx(brazos):
        settings = dispatch_config.dispatch_settings()
        assert settings.channel_is_active(models.CHANNEL_IN_APP) is True
        route = provider_seam.channel_route(models.CHANNEL_IN_APP, active=True)

    assert route.dispatchable is True, (
        "in-app is the first channel whose route is dispatchable. If this goes red, the "
        "platform adapter stopped resolving and NOTHING in this product can deliver."
    )
    assert route.problem is None


def test_us_not_018_tc2__the_other_three_channels_are_unchanged(brazos, dana):
    """BR-NOT-013, verbatim: *"no lane is to build or fake an adapter to turn a
    test green."* In-app must not have loosened anybody else's verdict."""
    with tenant_ctx(brazos):
        print_route = provider_seam.channel_route(models.CHANNEL_PRINT, active=True)
        email_route = provider_seam.channel_route(models.CHANNEL_EMAIL, active=False)
        sms_route = provider_seam.channel_route(models.CHANNEL_SMS, active=False)

    assert print_route.dispatchable is False
    # ⚠ **AMENDED 2026-09-07 — THIS ASSERTION WENT STALE AND WAS RED, NOT WRONG.**
    # It expected `provider_status_unknown`, which was the honest answer while
    # `apps/integrations` knew no PRINT category and `provider_connection_status`
    # could not answer at all. `CR-069` F1 (`93356954`, 2026-09-05) gave print a
    # category, so integrations now answers a real *not connected*, which is a
    # BETTER answer and the one this route should give. The verdict — print is
    # not dispatchable — has not moved, and that is what this test is for.
    # Found while fixing `DEF-NOT-4532`, in the same three-day-old red.
    #
    # ⚠ **AND AMENDED AGAIN 2026-09-30 — THAT READING WAS `DEF-NOT-8451`.**
    # A print CATEGORY exists, but no print ADAPTER is bound to any manifest in
    # it, so every connect a utility tries answers *Cannot be connected yet.* A
    # *not connected* that nobody can ever make connected sends a clerk to
    # Settings → Integrations for a fix that is not theirs — the confusion the
    # two codes exist to prevent (`provider_seam.channel_route`'s own detail
    # says so), and against `US-NOT-003` TC-1's PO-ruled reading (2026-08-15:
    # no print adapter exists or is coming this release). Integrations now says
    # whether a channel's kind can be connected at all, and print is the
    # PLATFORM's gap again. The first assertion is the hold: the day a print
    # adapter is bound it goes red, and this line should become NOT_CONNECTED.
    assert provider_seam.provider_status(models.CHANNEL_PRINT)["connectable"] is False
    assert print_route.problem["code"] == provider_seam.ROUTE_PROVIDER_STATUS_UNKNOWN
    assert email_route.dispatchable is False
    assert email_route.problem["code"] == provider_seam.ROUTE_CHANNEL_DEFERRED
    assert email_route.problem["deferred_until"] == "W6"
    assert sms_route.dispatchable is False
    # `CR-198-BRC10` (2026-10-29): SMS is no longer deferred to v1.1 — a
    # switched-off text channel is simply off for this tenant, still not dispatchable.
    assert sms_route.problem["deferred_until"] is None


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE WHOLE CHAIN — THE PO'S ACCEPTANCE
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_018_tc3__a_staff_event_travels_queue_to_inbox_and_can_be_read(brazos, dana):
    """**THE ACCEPTANCE TEST.** A staff event fires → a queue row is written →
    the dispatcher drains it → it lands in the recipient's inbox → the bell has
    a count → opening it marks it read.

    Nothing is stubbed. `dispatch_cycle` is the real dispatcher, the pin is
    resolved by the real template service, the body is rendered by the real
    renderer and the hand-off goes through `provider_seam.dispatch_batch` — the
    same function a transactional ESP would be called through.
    """
    with tenant_ctx(brazos):
        _seeded(dana)

        # ── a staff event fires ──────────────────────────────────────────
        summary = bulk_summary.queue_bulk_summary(
            operation="Billing run",
            operation_id=uuid.uuid4(),
            total_count=1204,
            failed_count=3,
            finished_at=FINISHED_AT,
            actor=dana,
        )
        assert summary.created is True

        # ── a queue row exists, queued, unsent ───────────────────────────
        row = models.OutboundMessage.objects.get(pk=summary.message_id)
        assert row.channel == models.CHANNEL_IN_APP
        assert row.status == models.STATUS_QUEUED
        assert row.recipient_address == str(dana.user.id)
        # Nothing is in any inbox yet: queueing is not delivering (BR-NOT-005).
        assert in_app.unread_count(actor=dana) == 0

        # ── the dispatcher drains it ─────────────────────────────────────
        result = dispatcher.dispatch_cycle(
            now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana
        )
        assert result.sent == 1, f"nothing was dispatched: {result.problems}"

        row.refresh_from_db()
        assert row.status == models.STATUS_SENT
        # BR-NOT-013 is INTACT: the platform accepted the message, it did not
        # receive a delivery confirmation from anybody.
        assert row.status != models.STATUS_DELIVERED
        assert row.sent_at is not None

        # ── the bell has a count, and the message says something ─────────
        assert in_app.unread_count(actor=dana) == 1
        items = in_app.inbox(actor=dana)
        assert len(items) == 1
        body = items[0].body
        assert "Billing run" in body
        assert "1204" in body
        assert "3" in body
        assert rendering.ABSENT_MARK not in body, (
            "the message rendered with named absences — a clerk would read "
            f"'—— processed · —— failed'. Body was: {body!r}"
        )
        assert items[0].read is False

        # ── opening it marks it read ─────────────────────────────────────
        opened = in_app.mark_read(actor=dana, message_id=items[0].id)
        assert opened.read is True
        assert in_app.unread_count(actor=dana) == 0


def test_us_not_018_tc4__a_second_dispatch_cycle_does_not_deliver_a_second_copy(brazos, dana):
    """CLAUDE.md rule 6 at the DELIVERY end. `uq_in_app_msgs_message_user` is
    what makes a re-run harmless; without it a retried cycle would put the same
    run summary in a clerk's inbox twice."""
    with tenant_ctx(brazos):
        _seeded(dana)
        bulk_summary.queue_bulk_summary(
            operation="Payment import",
            operation_id=uuid.uuid4(),
            total_count=40,
            failed_count=0,
            finished_at=FINISHED_AT,
            actor=dana,
        )
        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)
        before = models.InAppMessage.objects.count()

        # Force the row back onto the queue the way a re-queue action would, and
        # drain again. The DELIVERY constraint, not the queue key, is what is
        # under test here.
        row = models.OutboundMessage.objects.get(channel=models.CHANNEL_IN_APP)
        models.OutboundMessage.objects.filter(pk=row.pk).update(
            status=models.STATUS_QUEUED, batch_id=None, sent_at=None
        )
        again = dispatcher.dispatch_cycle(
            now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana
        )

        assert models.InAppMessage.objects.count() == before == 1
        # ⚠ AND IT IS REPORTED AS **SENT**, NOT AS A FAILURE — which is the half
        # of this that a count alone cannot see. The message IS in the
        # recipient's inbox, which is what the queue row asked for; answering
        # `failed` would retry forever against a constraint that will refuse it
        # every time. Without the `IntegrityError` handler the constraint's
        # violation escapes to the dispatcher's per-batch guard and this reads 0.
        assert again.sent == 1
        assert again.batches[0].failed == 0


# ══════════════════════════════════════════════════════════════════════════
# 3 · WHOSE INBOX — THE ISOLATION THAT RLS CANNOT ENFORCE
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_018_tc10__one_clerks_message_is_not_in_another_clerks_inbox(brazos, dana):
    """`apps/notifications/in_app.py`: not one function accepts a user id from a
    caller. A message addressed to Dana is invisible to Marcus, and Marcus
    cannot mark it read even holding its id."""
    marcus = staff_actor(brazos, "billing_clerk", "marcus-inbox@brazosbendutilities.test")
    with tenant_ctx(brazos):
        _seeded(dana)
        bulk_summary.queue_bulk_summary(
            operation="Billing run",
            operation_id=uuid.uuid4(),
            total_count=10,
            failed_count=1,
            finished_at=FINISHED_AT,
            actor=dana,
        )
        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)

        dana_items = in_app.inbox(actor=dana)
        assert len(dana_items) == 1
        assert in_app.inbox(actor=marcus) == ()
        assert in_app.unread_count(actor=marcus) == 0

        with pytest.raises(in_app.InboxRefused):
            in_app.mark_read(actor=marcus, message_id=dana_items[0].id)
        # And Dana's message is still unread — a refused read must not have
        # marked anything.
        assert in_app.unread_count(actor=dana) == 1


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE ADAPTER'S OWN CONTRACT
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_018__the_adapter_refuses_a_message_with_no_recipient(brazos, dana):
    """A message addressed to nobody is `failed` and NOT retryable: it will not
    acquire a recipient by waiting, and three retries would hide it behind a
    counter instead of putting it on the dispatch home."""
    with tenant_ctx(brazos):
        answers = in_app.deliver_batch(
            models.CHANNEL_IN_APP,
            ({"id": str(uuid.uuid4()), "address": None, "artifact": {"body": "x"}},),
        )
    answer = next(iter(answers.values()))
    assert answer["status"] == models.STATUS_FAILED
    assert answer["retryable"] is False


def test_us_not_018__the_adapter_refuses_an_empty_body(brazos, dana):
    """A blank line in a clerk's inbox is not a notification."""
    with tenant_ctx(brazos):
        answers = in_app.deliver_batch(
            models.CHANNEL_IN_APP,
            ({"id": str(uuid.uuid4()), "address": str(dana.user.id), "artifact": {"body": ""}},),
        )
    answer = next(iter(answers.values()))
    assert answer["status"] == models.STATUS_FAILED
    assert answer["retryable"] is False


def test_us_not_018__the_platform_adapter_answers_for_in_app_only(brazos, dana):
    """A platform module quietly answering for a PROVIDER channel would report
    messages as sent that nobody sent."""
    with tenant_ctx(brazos), pytest.raises(in_app.InboxRefused):
        in_app.deliver_batch(models.CHANNEL_EMAIL, ())


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE SURFACE — AND THE ABSENCE THAT MUST STAY
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_018__all_three_inbox_paths_resolve_through_the_root_urlconf():
    """DEF-112 / DEF-128, four times in this repo: a view nothing routes to is a
    feature that does not exist."""
    base = "/api/brazosbend/in-app-messages"
    assert resolve(base).func is in_app_api.in_app_messages
    assert resolve(f"{base}/read-all").func is in_app_api.mark_all_in_app_messages_read
    assert resolve(f"{base}/{uuid.uuid4()}/read").func is in_app_api.mark_in_app_message_read


def test_us_not_018_tc12__no_send_route_is_minted_by_the_in_app_surface():
    """BR-NOT-005 / A11 Addendum r2 §4. **In-app is the first channel where a
    synchronous send route would actually have delivered something**, which is
    precisely why this absence has to be asserted rather than assumed."""
    for path in ("send", "test-send", "deliver"):
        with pytest.raises(Resolver404):
            resolve(f"/api/brazosbend/in-app-messages/{path}")


def test_us_not_018_tc11__the_inbox_endpoint_serves_the_badge_and_the_list_together(brazos, dana):
    """One request, because a count fetched separately from the list it counts
    is a count that can disagree with what is on screen."""
    with tenant_ctx(brazos):
        _seeded(dana)
        bulk_summary.queue_bulk_summary(
            operation="Billing run",
            operation_id=uuid.uuid4(),
            total_count=7,
            failed_count=2,
            finished_at=FINISHED_AT,
            actor=dana,
        )
        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)
        response = _call(in_app_api.in_app_messages, "get", brazos, dana)

    assert response.status_code == 200
    assert response.data["unread"] == 1
    assert response.data["count"] == 1
    # BR-NOT-013 travels with the messages: a reader of this response must not
    # conclude that email or SMS went out too.
    assert "no provider adapter" in response.data["channel_note"]

    message_id = response.data["results"][0]["id"]
    with tenant_ctx(brazos):
        opened = _call(
            in_app_api.mark_in_app_message_read, "post", brazos, dana, message_id=message_id
        )
    assert opened.status_code == 200
    assert opened.data["read"] is True
    assert opened.data["unread"] == 0


def test_us_not_018_tc13__a_billing_clerk_may_read_their_own_inbox(brazos):
    """BR-IDN-009 governs what a person may do to the TENANT'S data. A clerk who
    cannot read the summary of the run they started is the exact failure
    BR-NOT-020 exists to prevent."""
    marcus = staff_actor(brazos, "billing_clerk", "marcus-own@brazosbendutilities.test")
    with tenant_ctx(brazos):
        response = _call(in_app_api.in_app_messages, "get", brazos, marcus, role="billing_clerk")
    assert response.status_code == 200
    assert response.data["unread"] == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 fourth ruling set · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-019/BR-NOT-020 · apps/notifications/in_app.py · apps/notifications/provider_seam.py)
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(the screen half is 07-frontend/src/components/AppShell.test.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: EVERY GUARD HERE WAS PROVED RED FIRST (hard-won law 7) — transcripts in the lane report. The four: (a) removing CHANNEL_IN_APP from PLATFORM_ADAPTERS made the acceptance test fail with `nothing was dispatched: [{'code': 'provider_status_unknown', ...}]`; (b) clearing `render_context` on the queue row made the body assertion fail reading "—— processed · —— failed"; (c) dropping `uq_in_app_msgs_message_user` made the re-dispatch test find 2 rows where it asserts 1; (d) letting `mark_read` filter on pk alone made the cross-clerk test fail with DID NOT RAISE.
# exceptions: (1) THE ISOLATION TIER IS A SEPARATE FILE (test_cr_009_in_app_isolation.py) because RLS is Postgres-only and this file runs on both. (2) `delivered` IS ASSERTED ABSENT rather than asserted present — BR-NOT-013 keeps it a provider confirmation nothing here can write, and the in-app adapter does not become one by being local.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
