# ── Trace ──────────────────────────────────────────────
# Component: BE-07 job RUNNER — the live store (apps.tenancy.JobStore over the
#            `jobs` table), the handler registry, and the eager execution path
#            that lets a 202 finish with no broker (JOBS_EAGER). The in-memory
#            kernel TCs stay in tests/test_be07_jobs.py; these are the wired
#            halves that file could not exercise ("live table + worker TCs land
#            with the job-table story").
#            The registered rate-change body (US-RAT-011 / BR-RAT-040) is
#            exercised here for its REPLAY behavior — a re-run must not
#            double-apply. The rest of that story's TCs stay in
#            tests/test_us_rat_versioning.py.
# ───────────────────────────────────────────────────────
"""BE-07 runner TCs: enqueue → run → succeeded, with a real row behind it.

Numbering continues tests/test_be07_jobs.py (tc01–tc17); nothing there moves.

Two mechanics stated rather than hidden:
- JOBS_EAGER is FALSE in the test settings on purpose (config/settings/test.py):
  the suite enqueues and runs as two deliberate steps, and several ratified TCs
  run a body by hand after the accept. Every eager TC below turns it on for
  itself with override_settings, which is exactly how the switch is meant to be
  read at dispatch time.
- The store fixture registers the REAL store and restores whatever was
  registered before it, because other test modules legitimately swap in fakes.
"""

from decimal import Decimal

import pytest
from django.test import override_settings

from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared W0/W1 fixtures
from tests.test_us_rat_helpers import (  # noqa: F401 — named for readability
    RES_ELECTRIC_TIERS,
    env,
    growth_plan,
    other_env,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

KIND = "test_probe"  # a job kind owned by nobody — registered per test


@pytest.fixture()
def live_store():
    """The real BE-07 store (apps.tenancy) — the one AppConfig.ready registers."""
    previous = core_jobs._store
    store = tenancy_services.JobStore()
    core_jobs.set_job_store(store)
    yield store
    core_jobs.set_job_store(previous)


@pytest.fixture()
def eager(live_store):
    """Store + transport wired exactly as startup wires them."""
    previous = core_jobs._dispatcher
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield live_store
    core_jobs.set_job_dispatcher(previous)


@pytest.fixture()
def probe_handler():
    """Register a body for KIND and take it back off at the end."""

    def register(handler):
        core_jobs.set_job_handler(KIND, handler)
        return handler

    yield register
    core_jobs.set_job_handler(KIND, None)


def job_row(job_id):
    return tenancy_models.Job.objects.get(id=job_id)


# ── the live store answers the three kernel questions ───────────────────────
def test_be07_tc18_enqueue_writes_a_real_row_the_poll_can_find(env, live_store):
    with tenant_ctx(env.tenant):
        record = core_jobs.enqueue(KIND, payload={"cycle": "08-A"})
        row = job_row(record["id"])
        assert row.tenant_id == env.tenant.id
        assert row.kind == KIND and row.status == core_jobs.QUEUED
        assert row.progress == {"done": 0, "total": None}
        assert row.payload == {"cycle": "08-A"}
        # The record the kernel handed back and the record the store reads
        # back are the same dict — the 202's job_id polls to this row.
        assert live_store.get(record["id"]) == record


def test_be07_tc19_the_scope_keyed_fold_in_still_holds_against_a_real_table(env, live_store):
    with tenant_ctx(env.tenant):
        first = core_jobs.enqueue("bill_run", scope_key="mixed:2026-08")
        second = core_jobs.enqueue("bill_run", scope_key="mixed:2026-08")
        assert second["id"] == first["id"]  # NFR-16: one active job per scope
        assert tenancy_models.Job.objects.filter(kind="bill_run").count() == 1
        # A finished scope may lawfully run again (the kernel's TC-7, now on a
        # real table where the partial unique index is what allows it).
        core_jobs.start(first["id"])
        core_jobs.succeed(first["id"])
        third = core_jobs.enqueue("bill_run", scope_key="mixed:2026-08")
        assert third["id"] != first["id"]
        assert tenancy_models.Job.objects.filter(kind="bill_run").count() == 2


def test_be07_tc20_one_tenants_scope_key_never_folds_into_anothers(env, other_env, live_store):
    with tenant_ctx(env.tenant):
        mine = core_jobs.enqueue("bill_run", scope_key="mixed:2026-08")
    with tenant_ctx(other_env.tenant):
        theirs = core_jobs.enqueue("bill_run", scope_key="mixed:2026-08")
    assert mine["id"] != theirs["id"]  # HR-1: scope keys are per tenant
    assert job_row(theirs["id"]).tenant_id == other_env.tenant.id


# ── run_pending: the body comes from the record's kind ──────────────────────
def test_be07_tc21_run_pending_runs_the_registered_body_and_records_success(
    env, live_store, probe_handler
):
    seen = []
    probe_handler(lambda record: seen.append(record["id"]) or "/probes/1")
    with tenant_ctx(env.tenant):
        record = core_jobs.enqueue(KIND)
    finished = core_jobs.run_pending(record["id"])
    assert seen == [record["id"]]
    assert finished["status"] == core_jobs.SUCCEEDED
    row = job_row(record["id"])
    assert row.status == core_jobs.SUCCEEDED and row.result_link == "/probes/1"
    assert row.error is None


def test_be07_tc22_a_kind_with_no_registered_body_refuses_loudly(env, live_store):
    with tenant_ctx(env.tenant):
        record = core_jobs.enqueue("nobody_owns_this")
    with pytest.raises(core_jobs.JobsError):
        core_jobs.run_pending(record["id"])
    assert job_row(record["id"]).status == core_jobs.QUEUED  # nothing pretended to run


# ── the eager path: a 202 that actually finishes (R1, no broker) ────────────
@override_settings(JOBS_EAGER=True)
def test_be07_tc23_eager_enqueue_runs_the_job_and_leaves_a_result_link(env, eager, probe_handler):
    probe_handler(lambda record: f"/probes/{record['payload']['n']}")
    with tenant_ctx(env.tenant):
        record = core_jobs.enqueue(KIND, payload={"n": 7})
        body = core_jobs.accepted(record)
    row = job_row(record["id"])
    assert body == {"job_id": record["id"], "status_url": f"/api/jobs/{record['id']}"}
    assert row.status == core_jobs.SUCCEEDED
    assert row.result_link == "/probes/7"


@override_settings(JOBS_EAGER=True)
def test_be07_tc24_a_failing_body_records_failed_and_never_raises_into_the_caller(
    env, eager, probe_handler
):
    """The accept already answered 202; the failure belongs on the RECORD, not
    on the caller's response (core/jobs.run_eager)."""

    def boom(record):
        raise RuntimeError("export blew up")

    probe_handler(boom)
    with tenant_ctx(env.tenant):
        record = core_jobs.enqueue(KIND)  # no exception escapes this line
    row = job_row(record["id"])
    assert row.status == core_jobs.FAILED
    assert row.error == "RuntimeError: export blew up"
    assert row.result_link is None


@override_settings(JOBS_EAGER=True)
def test_be07_tc25_eager_puts_the_callers_tenant_context_back(env, eager, probe_handler):
    """run_job clears context on its way out (B3). The caller is mid-request and
    still has work to do — the audit row after an enqueue is the live example."""
    probe_handler(lambda record: None)
    with tenant_ctx(env.tenant):
        core_jobs.enqueue(KIND)
        from core import tenancy as core_tenancy

        assert core_tenancy.current_tenant_id() == env.tenant.id


@override_settings(JOBS_EAGER=True)
def test_be07_tc26_an_unrunnable_kind_is_recorded_failed_not_left_queued(env, eager):
    """In eager mode no worker is coming, so `queued` forever would be a lie."""
    with tenant_ctx(env.tenant):
        record = core_jobs.enqueue("nobody_owns_this")
    row = job_row(record["id"])
    assert row.status == core_jobs.FAILED
    assert "no handler registered" in row.error


@override_settings(JOBS_EAGER=False)
def test_be07_tc27_with_the_broker_switch_the_record_rests_queued(env, eager, probe_handler):
    """JOBS_EAGER off (production/TD-17): dispatch does nothing here — the job
    waits for a worker, and the record says so honestly."""
    probe_handler(lambda record: "/probes/never")
    with tenant_ctx(env.tenant):
        record = core_jobs.enqueue(KIND)
    assert job_row(record["id"]).status == core_jobs.QUEUED


# ── the registered rate-change body is idempotent (BR-RAT-040) ──────────────
def _bulk_payload(env):
    schedule = env.tiered_schedule("Res Electric · Tiered", "electric", RES_ELECTRIC_TIERS)
    return {
        "entities": [{"type": "schedule", "id": schedule["id"]}],
        "change": {"kind": "percent", "value": "3.0"},
        "effective_from": "2027-01-01",
        "reason": "Board order 2026-12 annual adjustment",
    }


@override_settings(JOBS_EAGER=True)
def test_be07_tc28_the_rate_change_body_is_registered_and_applies_once(env, eager):
    """POST /rate-changes → 202 → the batch is actually applied (this is the
    end-to-end gap the runner closes), and the fingerprint keeps it at once."""
    payload = _bulk_payload(env)
    with tenant_ctx(env.tenant):
        from apps.rating import services as rating_services

        assert core_jobs.job_handler(rating_services.RATE_CHANGE_JOB) is not None
        accepted = rating_services.request_rate_change_batch(env.admin, payload)
        batch = rating_models.RateChangeBatch.objects.get()  # applied, not pending
        job = job_row(accepted["job_id"])
        tier = (
            rating_models.RateTier.objects.filter(tariff_version__effective_from="2027-01-01")
            .order_by("seq")
            .first()
        )
    assert job.status == core_jobs.SUCCEEDED
    assert job.result_link == f"/rate-changes/{batch.id}"
    assert tier.unit_price == Decimal("0.113300")  # 0.11 × 1.03


def test_be07_tc29_re_delivering_the_same_job_id_applies_nothing_twice(env, live_store):
    """CELERY_TASK_ACKS_LATE means a worker crash CAN re-deliver a task. The
    kernel's first answer is the state machine: `succeeded` is terminal, so the
    second delivery of a finished job runs no body at all."""
    from apps.rating import services as rating_services

    payload = _bulk_payload(env)  # built outside the context: the builders open their own
    with tenant_ctx(env.tenant):
        accepted = rating_services.request_rate_change_batch(env.admin, payload)
    core_jobs.run_pending(accepted["job_id"])
    with tenant_ctx(env.tenant):
        versions_after_first = rating_models.TariffVersion.objects.count()
        assert rating_models.RateChangeBatch.objects.count() == 1

    with pytest.raises(core_jobs.JobsError):
        core_jobs.run_pending(accepted["job_id"])  # the SAME job, delivered twice

    with tenant_ctx(env.tenant):
        assert rating_models.RateChangeBatch.objects.count() == 1  # not two
        assert rating_models.TariffVersion.objects.count() == versions_after_first
    assert job_row(accepted["job_id"]).status == core_jobs.SUCCEEDED  # untouched


def test_be07_tc30_a_second_job_for_the_same_batch_refuses_on_the_fingerprint(env, live_store):
    """BR-RAT-040: the BODY carries its own guard, not just the state machine.

    A brand-new job record for an already-applied batch (a re-enqueue once the
    first job finished — the scope-key fold-in only covers ACTIVE work) finds
    the batch's fingerprint and refuses. One batch row, one new version, and
    the refusal is recorded on the second job rather than swallowed.
    """
    from apps.rating import services as rating_services
    from core import errors

    payload = _bulk_payload(env)
    with tenant_ctx(env.tenant):
        accepted = rating_services.request_rate_change_batch(env.admin, payload)
    core_jobs.run_pending(accepted["job_id"])
    first_payload = live_store.get(accepted["job_id"])["payload"]
    with tenant_ctx(env.tenant):
        versions_after_first = rating_models.TariffVersion.objects.count()
        replay = core_jobs.enqueue(
            rating_services.RATE_CHANGE_JOB,
            payload=dict(first_payload),
            scope_key=first_payload["fingerprint"],
        )

    with pytest.raises(errors.BizError) as refusal:
        core_jobs.run_pending(replay["id"])

    assert refusal.value.code == errors.BIZ_IDEMPOTENT
    assert refusal.value.br_ref == "BR-RAT-040"
    with tenant_ctx(env.tenant):
        assert rating_models.RateChangeBatch.objects.count() == 1
        assert rating_models.TariffVersion.objects.count() == versions_after_first
    failed = job_row(replay["id"])
    assert failed.status == core_jobs.FAILED and "BizError" in failed.error


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-011@f69a661 (the registered body this file replays — EP-RAT-04; the runner itself is component packet BE-07@05736ee, B13 §3)
# generated: 2026-08-10 by story-coder v1 (job-runner lane — the wiring BE-07 documented and no lane had built) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the endpoint TCs live in tests/test_be07_jobs_endpoint.py) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_be07_job_runner.py✔ · suite `pytest tests -m "not golden and not isolation"` 713 passed / 7 skipped / 47 deselected (682 was the baseline when this lane started; the 31 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: the RLS half of tc20 (one tenant's job row invisible to another under app.tenant_id) belongs to the G5 isolation suite — sqlite cannot enforce RLS; the app-filter half is asserted here · JOBS_EAGER is off in the test settings and each eager TC turns it on for itself (config/settings/test.py records why) · [path-tenancy lane 2026-08-10] status_url is `/api/jobs/{id}` — the platform poll path carries no tenant segment
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
