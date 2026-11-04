# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-9004 — straight after Start checking (and Check again) the
#           step drew 'Checked 0 accounts · Saved' and an ENABLED
#           'Price 0 accounts' while the Check job was already queued
# Story:    US-BIL-037 · plan A3 (start / progress) · B28
# Tracker:  BULK-CHG-20
# ───────────────────────────────────────────────────────
"""The run names its Check job the moment the job is ASKED FOR, not when a
worker first picks it up.

ROOT CAUSE. `GET …/check` reads the job from `bill_runs.findings_summary
["job_id"]`, and that was written by the coordinator (`check_batches.
_point_summary_at`) only once a worker started it. Between the press and the
worker — 20 s and more at 40,015 accounts — the read answered `job: null`
(first Check) or the PREVIOUS, finished job (Check again). The screen then
drew the saved counts (all 0, or the old ones) with Price enabled.

RED FIRST: on 2.437.5 `job` is None in the GET straight after the POST.
"""

from __future__ import annotations

import pytest

from apps.billing import check_api, run_jobs
from core import jobs as core_jobs

from tests.test_bbr_check_engine import three_accounts
from tests.test_bbr_check_store import a_run
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _no_worker_yet(monkeypatch):
    """A worker is up (so the press is accepted as background) but has not
    picked the job up yet: the dispatcher hands it to nobody."""
    monkeypatch.setattr(run_jobs, "would_run", lambda: (True, None))
    monkeypatch.setattr(core_jobs, "_dispatcher", lambda record: None)


def _start_then_read(brazos, run, clerk):
    started = api_call(
        check_api.run_check,
        "post",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        data={"background": True},
        run_id=str(run.pk),
    )
    assert started.status_code == 202, started.data
    state = api_call(
        check_api.run_check,
        "get",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        run_id=str(run.pk),
    )
    return started, state


def test_def_bil_9004__the_check_read_names_the_queued_job_straight_after_start(
    brazos, dana, monkeypatch
):
    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        clerk = an_actor_user(brazos)
    _no_worker_yet(monkeypatch)
    started, state = _start_then_read(brazos, run, clerk)
    job = state.data["job"]
    assert job is not None, "the read answered job: null — the screen draws 0 tiles and Price 0"
    assert job["id"] == started.data["job_id"]
    assert job["status"] == core_jobs.QUEUED


def test_def_bil_9004__check_again_names_the_new_job_not_the_finished_one(
    brazos, dana, monkeypatch
):
    from apps.billing import check_store
    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        clerk = an_actor_user(brazos)
        check_store.check_run(run)  # a finished Check, saved
    _no_worker_yet(monkeypatch)
    started, state = _start_then_read(brazos, run, clerk)
    assert state.data["job"]["id"] == started.data["job_id"]
    assert state.data["job"]["status"] == core_jobs.QUEUED


def test_def_bil_9004__the_run_read_names_a_live_check_so_a_reopen_stays_on_check(
    brazos, dana, monkeypatch
):
    """Check again on a run that already holds drafts read `phase: calculated`,
    so the page re-opened on Sign off with dashes while 40,015 accounts were
    being re-checked. The run read now carries the live Check job."""
    from apps.billing import check_store
    from apps.billing import selectors as billing_selectors
    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        clerk = an_actor_user(brazos)
        check_store.check_run(run)
        assert billing_selectors.run_detail_dict(run).get("checking") is None
    _no_worker_yet(monkeypatch)
    started, _state = _start_then_read(brazos, run, clerk)
    with tenant_ctx(brazos):
        run.refresh_from_db()
        live = billing_selectors.run_detail_dict(run).get("checking")
    assert live is not None, "a live Check is invisible to a re-opened run"
    assert live["id"] == started.data["job_id"]
