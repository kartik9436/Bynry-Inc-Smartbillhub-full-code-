# ── Trace ──────────────────────────────────────────────
# Change:   CR-188-BRC10 — PO 2026-10-22, decision log *"Account-access emails
#           are sent instantly, at the highest priority"*
# Rules:    BR-NOT-005 (one dispatch path) · BR-NOT-009 (quiet hours —
#           NARROWED for account-access rows by that ruling)
# ───────────────────────────────────────────────────────
"""`services.send_now`: the row is written first, marked highest priority, and
dispatched on commit by its own job on its own queue — without waiting for a
dispatch cycle and without the quiet-hours hold."""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import dispatch_config, dispatcher, models, send_now, services
from core import jobs as core_jobs

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_cr049_t2_dispatch_freeze import provider_connected  # noqa: F401
from tests.test_us_not_002_dispatcher import (  # noqa: F401 — shared fixtures
    OUTSIDE_WINDOW,
    queue_rows,
    stub_adapter,
    stub_templates,
)

pytestmark = pytest.mark.django_db


def _email_on(dana):
    dispatch_config.update_dispatch_settings(actor=dana, email_dispatch_active=True)


def test_cr188__the_account_access_queue_is_registered_for_the_job():
    assert core_jobs.job_queue(send_now.SEND_NOW_JOB) == send_now.ACCOUNT_ACCESS_QUEUE
    assert core_jobs.job_handler(send_now.SEND_NOW_JOB) is send_now.run_send_now_job


def test_cr188__dispatch_messages_sends_the_named_row_inside_quiet_hours(
    brazos, dana, stub_adapter, stub_templates
):
    """22:15 tenant time: a cycle HOLDS email (BR-NOT-009); the immediate send
    of an account-access row does not, and touches no other row."""
    with tenant_ctx(brazos):
        _email_on(dana)
        (mine,) = queue_rows(brazos, 1, channel=models.CHANNEL_EMAIL, source_type="staff_access")
        others = queue_rows(brazos, 2, channel=models.CHANNEL_EMAIL)

        result = dispatcher.dispatch_messages((mine.pk,), now=OUTSIDE_WINDOW)

        assert [len(messages) for _c, messages in stub_adapter.calls] == [1]
        assert stub_adapter.calls[0][1][0]["id"] == str(mine.pk)
        assert not [p for p in result.problems if p["code"] == dispatcher.CYCLE_QUIET_HOURS_HOLD]
        mine.refresh_from_db()
        assert mine.status == models.STATUS_SENT
        assert {r.status for r in models.OutboundMessage.objects.filter(pk__in=[o.pk for o in others])} == {
            models.STATUS_QUEUED
        }


def test_cr188__no_provider_leaves_the_row_queued_for_the_cycle(brazos, dana, stub_templates):
    with tenant_ctx(brazos):
        _email_on(dana)
        (mine,) = queue_rows(brazos, 1, channel=models.CHANNEL_EMAIL, source_type="staff_access")
        result = dispatcher.dispatch_messages((mine.pk,), now=OUTSIDE_WINDOW)
        mine.refresh_from_db()
        assert mine.status == models.STATUS_QUEUED and mine.attempts == 0
        assert result.problems  # the route's reason travels


def test_cr188__send_now_marks_priority_and_runs_the_job_on_commit_without_a_cycle(
    brazos, dana, stub_adapter, stub_templates, monkeypatch, django_capture_on_commit_callbacks
):
    """Eager transport: the job runs when the callback fires — no
    `dispatch_cycle` is called anywhere in this case."""
    called = []
    monkeypatch.setattr(dispatcher, "dispatch_cycle", lambda **kw: called.append(kw))
    with tenant_ctx(brazos):
        _email_on(dana)
        (mine,) = queue_rows(brazos, 1, channel=models.CHANNEL_EMAIL, source_type="staff_access")
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            services.send_now([mine.pk])
        mine.refresh_from_db()
        assert mine.priority == models.PRIORITY_IMMEDIATE
        assert mine.status == models.STATUS_QUEUED  # nothing inside the transaction
        assert len(callbacks) == 1
        records = []
        monkeypatch.setattr(core_jobs, "_dispatcher", lambda record: records.append(record))
        callbacks[0]()
        (record,) = records
        assert record["kind"] == send_now.SEND_NOW_JOB
        assert record["payload"]["message_ids"] == [str(mine.pk)]
        # What the worker does with that record:
        summary = send_now.run_send_now_job(record)
        mine.refresh_from_db()
        assert mine.status == models.STATUS_SENT
        assert summary.startswith("1 of 1 sent")
    assert called == []


def test_cr188__the_cycle_claims_highest_priority_first(brazos, dana, stub_adapter, stub_templates):
    with tenant_ctx(brazos):
        _email_on(dana)
        dispatch_config.update_dispatch_settings(actor=dana, dispatch_batch_size=1)
        queue_rows(brazos, 2, channel=models.CHANNEL_EMAIL)
        (urgent,) = queue_rows(
            brazos, 1, channel=models.CHANNEL_EMAIL, priority=models.PRIORITY_IMMEDIATE
        )
        inside = datetime(2026, 8, 9, 15, 0, tzinfo=dt_timezone.utc)
        dispatcher.dispatch_cycle(now=inside, channels=(models.CHANNEL_EMAIL,))
        assert stub_adapter.calls[0][1][0]["id"] == str(urgent.pk)
