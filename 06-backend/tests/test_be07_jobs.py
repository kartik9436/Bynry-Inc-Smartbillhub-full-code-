# ── Trace ──────────────────────────────────────────────
# Component: BE-07 tests (core/jobs.py) — record contract, idempotent enqueue, resume
#            discipline, tenant-context harness, lazy Celery. Store is an in-memory
#            fake; live job-table + worker TCs land with the job-table story.
# ───────────────────────────────────────────────────────
"""BE-07 unit tests: enqueue mints the 202-able record, scope-keyed re-enqueue
folds into the active job (NFR-16), the state machine resumes failed→running
with its checkpoint intact (TD-17), run_job wraps every runner in ITS tenant's
context, and Celery stays a lazy import so all of this runs broker-less."""

import importlib
import sys
import types
import uuid
from contextlib import contextmanager

import pytest

from core import jobs

TENANT = uuid.UUID("00000000-0000-0000-0000-00000000000a")


class FakeStore:
    """The documented store contract: save/get/find_active, dict-backed."""

    def __init__(self):
        self.rows = {}

    def save(self, record):
        self.rows[record["id"]] = dict(record)

    def get(self, job_id):
        row = self.rows.get(job_id)
        return dict(row) if row else None

    def find_active(self, tenant_id, kind, scope_key):
        for row in self.rows.values():
            if (
                row["tenant_id"] == tenant_id
                and row["kind"] == kind
                and row["scope_key"] == scope_key
                and row["status"] in jobs.ACTIVE_STATUSES
            ):
                return dict(row)
        return None


@pytest.fixture(autouse=True)
def clean_registrations():
    jobs.set_job_store(None)
    jobs.set_job_dispatcher(None)
    yield
    jobs.set_job_store(None)
    jobs.set_job_dispatcher(None)


@pytest.fixture()
def in_tenant(monkeypatch):
    monkeypatch.setattr(jobs, "current_tenant_id", lambda: TENANT)


@pytest.fixture()
def store(in_tenant):
    fake = FakeStore()
    jobs.set_job_store(fake)
    return fake


# ── enqueue → the 202-able record ───────────────────────────────────────────
def test_be07_tc01_enqueue_mints_the_record_contract(store):
    record = jobs.enqueue("bill_run", payload={"cycle": "mixed", "period": "2026-08"})
    assert record["tenant_id"] == TENANT  # from context, never a parameter
    assert record["kind"] == "bill_run"
    assert record["status"] == jobs.QUEUED
    assert record["progress"] == {"done": 0, "total": None}
    assert record["checkpoint"] is None
    assert record["result_link"] is None and record["error"] is None
    assert record["payload"] == {"cycle": "mixed", "period": "2026-08"}
    assert store.rows[record["id"]]["status"] == jobs.QUEUED  # persisted before any 202


def test_be07_tc02_accepted_body_carries_job_id_and_poll_url(store):
    record = jobs.enqueue("import_reads")
    body = jobs.accepted(record)
    assert body == {"job_id": record["id"], "status_url": f"/api/jobs/{record['id']}"}


def test_be07_tc03_no_tenant_context_refuses_loudly(monkeypatch):
    monkeypatch.setattr(jobs, "current_tenant_id", lambda: None)
    jobs.set_job_store(FakeStore())
    with pytest.raises(jobs.JobsError):
        jobs.enqueue("bill_run")


def test_be07_tc04_no_store_refuses_loudly(in_tenant):
    # A 202 promising /jobs/{id} with no row behind it would be a lie.
    with pytest.raises(jobs.JobsError):
        jobs.enqueue("bill_run")


def test_be07_tc05_dispatcher_called_once_with_the_record(store):
    sent = []
    jobs.set_job_dispatcher(sent.append)
    record = jobs.enqueue("archival")
    assert sent == [record]


# ── idempotent enqueue (NFR-16 / BR-BIL-015 scope-key pattern) ──────────────
def test_be07_tc06_scope_keyed_reenqueue_folds_into_the_active_job(store):
    sent = []
    jobs.set_job_dispatcher(sent.append)
    first = jobs.enqueue("bill_run", scope_key="mixed:2026-08")
    second = jobs.enqueue("bill_run", scope_key="mixed:2026-08")
    assert second["id"] == first["id"]  # the SAME job — no double-execution
    assert len(store.rows) == 1
    assert len(sent) == 1  # and no second dispatch


def test_be07_tc07_finished_scope_allows_a_fresh_job(store):
    first = jobs.enqueue("bill_run", scope_key="mixed:2026-08")
    jobs.start(first["id"])
    jobs.succeed(first["id"])
    second = jobs.enqueue("bill_run", scope_key="mixed:2026-08")
    # Idempotency guards ACTIVE work; a completed scope can lawfully run again
    # (whether a story refuses instead is its BIZ-IDEMPOTENT law, not the kernel's).
    assert second["id"] != first["id"]


def test_be07_tc08_jobs_without_scope_key_never_fold(store):
    a = jobs.enqueue("send_batch")
    b = jobs.enqueue("send_batch")
    assert a["id"] != b["id"]


# ── the state machine (resume = failed→running; succeeded is forever) ───────
def test_be07_tc09_lifecycle_queued_running_succeeded(store):
    record = jobs.enqueue("import_reads")
    assert jobs.start(record["id"])["status"] == jobs.RUNNING
    done = jobs.succeed(record["id"], result_link="/imports/batch-7")
    assert done["status"] == jobs.SUCCEEDED
    assert done["result_link"] == "/imports/batch-7"


def test_be07_tc10_progress_and_checkpoint_recorded_while_running(store):
    record = jobs.enqueue("import_reads")
    jobs.start(record["id"])
    updated = jobs.record_progress(record["id"], done=40, total=120, checkpoint="row-40")
    assert updated["progress"] == {"done": 40, "total": 120}
    assert updated["checkpoint"] == "row-40"
    with pytest.raises(jobs.JobsError):  # progress belongs to running jobs only
        jobs.record_progress(jobs.succeed(record["id"])["id"], done=41)


def test_be07_tc11_failed_job_resumes_with_checkpoint_intact(store):
    record = jobs.enqueue("import_reads")
    jobs.start(record["id"])
    jobs.record_progress(record["id"], done=40, total=120, checkpoint="row-40")
    failed = jobs.fail(record["id"], error="ValueError: bad row 41")
    assert failed["status"] == jobs.FAILED and failed["error"] == "ValueError: bad row 41"
    resumed = jobs.start(record["id"])  # TD-17: resumable
    assert resumed["status"] == jobs.RUNNING
    assert resumed["checkpoint"] == "row-40"  # resume reads this to skip done work
    assert resumed["error"] is None  # clean slate for the new attempt


def test_be07_tc12_succeeded_is_terminal_forever(store):
    record = jobs.enqueue("bill_run")
    jobs.start(record["id"])
    jobs.succeed(record["id"])
    for illegal in (jobs.start, lambda i: jobs.fail(i, error="x"), jobs.succeed):
        with pytest.raises(jobs.JobsError):
            illegal(record["id"])


def test_be07_tc13_unknown_job_id_refused(store):
    with pytest.raises(jobs.JobsError):
        jobs.start("no-such-job")


# ── run_job harness (tenant context per record; fail records then re-raises) ──
@pytest.fixture()
def harness_context(monkeypatch):
    entered = []

    @contextmanager
    def fake_tenant_context(tenant_id):
        entered.append(("enter", tenant_id))
        try:
            yield tenant_id
        finally:
            entered.append(("exit", tenant_id))

    monkeypatch.setattr(jobs, "tenant_context", fake_tenant_context)
    return entered


def test_be07_tc14_run_job_runs_the_runner_inside_the_records_tenant(store, harness_context):
    record = jobs.enqueue("bill_run")
    seen = []

    def runner(rec):
        seen.append((rec["status"], harness_context[-1]))
        return "/billing/runs/08-A"

    finished = jobs.run_job(record["id"], runner)
    assert seen == [(jobs.RUNNING, ("enter", TENANT))]  # context held DURING the run
    assert finished["status"] == jobs.SUCCEEDED
    assert finished["result_link"] == "/billing/runs/08-A"
    assert harness_context[-1] == ("exit", TENANT)  # and cleared after


def test_be07_tc15_run_job_records_failure_then_reraises(store, harness_context):
    record = jobs.enqueue("bill_run")

    def runner(rec):
        raise RuntimeError("run blew up")

    with pytest.raises(RuntimeError):
        jobs.run_job(record["id"], runner)
    row = store.get(record["id"])
    assert row["status"] == jobs.FAILED
    assert row["error"] == "RuntimeError: run blew up"
    assert harness_context[-1] == ("exit", TENANT)  # context never leaks past a crash


# ── Celery stays lazy (TD-17 adopted; kernel runs without it) ───────────────
def test_be07_tc16_module_imports_without_celery():
    sys.modules.pop("celery", None)
    importlib.reload(jobs)  # a fresh import of the kernel pulls in NO celery
    assert "celery" not in sys.modules


def test_be07_tc17_tenant_task_class_builds_on_a_fake_celery_and_routes_run_job(
    store, harness_context, monkeypatch
):
    fake_celery = types.ModuleType("celery")

    class Task:  # the only celery surface the base class touches
        pass

    fake_celery.Task = Task
    monkeypatch.setitem(sys.modules, "celery", fake_celery)

    task_class = jobs.tenant_task_class()
    assert issubclass(task_class, Task)

    class ImportTask(task_class):
        def run(self, record):
            return "/imports/batch-9"

    record = jobs.enqueue("import_reads")
    finished = ImportTask()(record["id"])  # __call__(job_id) — the worker entry
    assert finished["status"] == jobs.SUCCEEDED
    assert finished["result_link"] == "/imports/batch-9"
    assert harness_context == [("enter", TENANT), ("exit", TENANT)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-07@05736ee (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-06..BE-09) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest 17/17✔ (this file) · suite 147/147✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (job-status vocabulary absent from A5 · /jobs/{id} endpoint + job-table owner unassigned) · [path-tenancy lane 2026-08-10] status_url is `/api/jobs/{id}`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
