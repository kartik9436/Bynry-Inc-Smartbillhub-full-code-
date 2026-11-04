# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-3500 — ONB-04.5 stops following the seeding run after three
#          minutes and then NAVIGATES on that timeout, so steps 14–18 are
#          never seen.
#          DEF-3501 — a finished plant that never REACHED some steps reports
#          `ready`, because the screen counted `failed` and `skipped` and not
#          `not_started`.
# Change:  CR-064 (PO 2026-09-02, the eighteen named steps) task A3/A4
# Rules:   BR-TEN-063 (atomic per module) · BR-TEN-060 (a block that did not
#          seed is a NAMED line) · CLAUDE.md hard-won law 14 (prove it on real
#          PostgreSQL)
# ───────────────────────────────────────────────────────
"""DEF-3500 — walk a real run to the end and prove every step lands terminal.

**WHY A BACKEND CASE FOR A SCREEN DEFECT.** The screen can only draw what the
poll serves it, and the Product Owner's sentence is about the END of the run:

    "I want to complete all 18 steps on this screen itself; and see all jobs are
     completed"

`SignupPlantFollowThrough.dom.test.tsx` proves the screen follows a run to the
end; it drives a STUB. This proves the other half — that a real plant, run
through the real job harness, leaves `job_poll` answering with **every one of
the eighteen in a terminal outcome and none of them un-run**. If the server ever
stops saying so, the screen has nothing to draw and no frontend case can see it.

⚠ **THE COUNT IS `len(SAMPLE_MODULES)` AND IS NEVER TYPED (DEF-3320).** Five
sentences in `sample_data.py` said SEVENTEEN one function away from a catalogue
returning eighteen, and every backend test stayed green through it precisely
because they all assert against the constant. This one does too, and adds the
assertion those could not make: that the number of steps the run RECORDED equals
the number the catalogue declares.

RUN IT ON POSTGRESQL as well as on the default suite (hard-won law 14 — the
per-block savepoint is the thing that lets a run continue after a refusal, and
SQLite has no aborted-transaction state to prove it against):

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
      SBH_TEST_DB_NAME=test_sbh_def3500 JOBS_EAGER=false \\
      python -m pytest tests/test_def3500_plant_walks_to_terminal.py --reuse-db -q
"""

import pytest

from apps.tenancy import models, sample_data, selectors
from core import jobs as core_jobs

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

#: What the poll may say about a step once the run has stopped. `not_started` is
#: absent DELIBERATELY: it is an honest word DURING a run and a defect after one.
TERMINAL_OUTCOMES = {
    sample_data.OUTCOME_SEEDED,
    sample_data.OUTCOME_SKIPPED,
    sample_data.OUTCOME_FAILED,
}


def _plant_job(result):
    plant = result.get("sample_plant")
    assert plant is not None, "provisioning asked for no sample plant"
    return plant


def test_def3500_tc1_a_real_run_leaves_every_step_terminal():
    """Run the plant through the REAL job harness and read the poll the screen
    reads. Every one of the eighteen is `seeded`, `skipped` or `failed`, and the
    job itself is terminal.

    RED-PROVED (law 7) by cutting the walk short — `SAMPLE_MODULES[:13]`
    monkeypatched in, which is the run the Product Owner watched:

        AssertionError: 5 of 18 steps are still not_started after the run
        finished: metering:seed_sample_next_cycle_reads,
        payments:seed_sample_cycle_collections,
        customers:seed_sample_payment_plans,
        payments:seed_sample_plan_payments,
        customers:seed_sample_wizard_parks
    """
    tenant, result = provisioned_tenant()
    plant = _plant_job(result)
    total = len(sample_data.SAMPLE_MODULES)
    assert plant["total"] == total
    assert len(plant["steps"]) == total, "the catalogue served at commit is short"

    with tenant_ctx(tenant):
        job = models.Job.objects.get(pk=plant["job_id"])
        if job.status == core_jobs.QUEUED:
            core_jobs.run_pending(str(job.id))

    with tenant_ctx(tenant):
        polled = selectors.job_poll(plant["job_id"])
        assert polled is not None
        assert polled["status"] in (core_jobs.SUCCEEDED, core_jobs.FAILED), polled["status"]

        steps = polled["steps"]
        assert len(steps) == total, f"the poll serves {len(steps)} steps, the catalogue has {total}"

        unrun = [s["key"] for s in steps if s["outcome"] == sample_data.OUTCOME_NOT_STARTED]
        assert not unrun, (
            f"{len(unrun)} of {total} steps are still not_started after the run "
            f"finished: {', '.join(unrun)}"
        )
        stray = {s["outcome"] for s in steps} - TERMINAL_OUTCOMES
        assert not stray, f"a step ended in a non-terminal outcome: {stray}"


def test_def3500_tc2_every_step_that_did_not_seed_carries_a_sentence():
    """The Product Owner's other sentence, from 2026-09-02: *"if step breaks -
    then show the reason behind it at that step itself , if you skip the step,
    then show the reason for that step also"*.

    So a step whose outcome is not `seeded` must have `detail` — the server's own
    words. A screen cannot invent one, and a silent line is the whole complaint.
    """
    tenant, result = provisioned_tenant()
    plant = _plant_job(result)
    with tenant_ctx(tenant):
        job = models.Job.objects.get(pk=plant["job_id"])
        if job.status == core_jobs.QUEUED:
            core_jobs.run_pending(str(job.id))
    with tenant_ctx(tenant):
        steps = selectors.job_poll(plant["job_id"])["steps"]
        silent = [
            s["key"]
            for s in steps
            if s["outcome"] != sample_data.OUTCOME_SEEDED and not (s.get("detail") or "").strip()
        ]
        assert not silent, f"these steps did not seed and say nothing about why: {silent}"


def test_def3500_tc3_the_progress_count_reaches_the_total():
    """`progress.done` is what the summary row above the eighteen reads, and it
    must land on the same number the list does — a run that ticks 13 of 18 and
    then stops is exactly the report."""
    tenant, result = provisioned_tenant()
    plant = _plant_job(result)
    total = len(sample_data.SAMPLE_MODULES)
    with tenant_ctx(tenant):
        job = models.Job.objects.get(pk=plant["job_id"])
        if job.status == core_jobs.QUEUED:
            core_jobs.run_pending(str(job.id))
    with tenant_ctx(tenant):
        polled = selectors.job_poll(plant["job_id"])
        assert polled["progress"]["done"] == total, polled["progress"]
        assert polled["progress"]["total"] == total, polled["progress"]
        # DEF-3280 — the label the run was last on, served rather than dropped.
        assert polled["checkpoint"] == sample_data.SAMPLE_MODULES[-1].label
