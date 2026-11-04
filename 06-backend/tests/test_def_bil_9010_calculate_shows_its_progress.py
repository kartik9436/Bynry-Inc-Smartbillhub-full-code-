# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-9010 — Calculate read '0 of —' for its first ~11 minutes at
#           40,009 accounts, and a run re-opened mid-Calculate opened on Sign
#           off over half its drafts instead of the progress
# Story:    US-BIL-038 · plan B17 / F13 · clerk check U3, U4
# Tracker:  BULK-CHG-39
# ───────────────────────────────────────────────────────
"""Calculate counts its first pass, and the run read says a Calculate is live.

ROOT CAUSES. (1) `run_calculate_job` reads every account (`prepared_for`)
before it drafts any, and recorded progress only from the drafting loop — so
`progress` stayed `{done: 0, total: null}` for the whole prepare pass. (2) The
run's `phase` reads `calculated` as soon as ONE draft exists, and nothing on
`GET /billing/runs/{id}` said a Calculate was still running.

RED FIRST: on 2.437.5 the first case records no `preparing` progress at all and
the second finds no `calculating` key on the run read.
"""

from __future__ import annotations

import pytest

from apps.billing import run_jobs
from apps.billing import selectors as billing_selectors
from core import jobs as core_jobs

from tests.test_bbr_check_engine import three_accounts
from tests.test_bbr_check_store import a_run
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _queued_calculate(monkeypatch, run):
    monkeypatch.setattr(core_jobs, "_dispatcher", lambda record: None)
    return run_jobs.enqueue_calculate(run)


def test_def_bil_9010__the_prepare_pass_reports_n_of_n_under_its_own_stage(
    brazos, dana, monkeypatch
):
    seen = []
    real = core_jobs.record_progress

    def spy(job_id, done, total=None, checkpoint=None, **kwargs):
        seen.append((done, total, kwargs.get("stage")))
        return real(job_id, done, total, checkpoint, **kwargs)

    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        record = _queued_calculate(monkeypatch, run)
        monkeypatch.setattr(core_jobs, "record_progress", spy)
        core_jobs.start(record["id"])
        run_jobs.run_calculate_job(core_jobs.current(record["id"]))
    preparing = [entry for entry in seen if entry[2] == run_jobs.PREPARING_STAGE]
    assert preparing, f"the prepare pass recorded no progress: {seen}"
    assert preparing[-1][:2] == (3, 3), preparing
    first_preparing = seen.index(preparing[0])
    drafting = [i for i, entry in enumerate(seen) if entry[2] is None]
    assert all(i > first_preparing for i in drafting), "preparing is counted BEFORE drafting"


def test_def_bil_9010__the_run_read_names_a_live_calculate_job(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        assert billing_selectors.run_detail_dict(run).get("calculating") is None
        record = _queued_calculate(monkeypatch, run)
        live = billing_selectors.run_detail_dict(run).get("calculating")
        assert live is not None, "a queued Calculate is invisible to a re-opened run"
        assert live["id"] == record["id"]
        assert live["status"] == core_jobs.QUEUED
