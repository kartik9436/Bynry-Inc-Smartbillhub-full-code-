# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-040 (bulk run · Send) · US-BIL-005 (issue)
# Defects:  DEF-BIL-8726 (a 40,000-bill Send ran as ONE task inside an 8,520 s
#           time limit) · DEF-BIL-8710 (a Send whose worker died never resumed;
#           a hand-back restarted its progress at 0)
# Pattern:  tests/test_b28_parallel_check_batches.py (the Check's batches)
# Rules:    CLAUDE.md hard rules 1, 4 and 6 · BR-BIL-055 · BR-BIL-058
# Real kill: tests/test_def_bil_8710_send_resume_pg.py (PostgreSQL, SIGKILL)
# ───────────────────────────────────────────────────────
"""The Send in batches of 500 under one coordinator, and handed back when its
worker dies.

Written BEFORE `send_batches.py`, as r11 step 2c asks — one case per promise:
a 40,000-bill Send is cut into batches no larger than 500; a Send through the
batches issues every bill once and completes its release once; the per-utility
cap holds; a Send whose worker died is handed back by the Send screen's poll
and by pressing Send again; its progress continues from the bills already
issued; and under `JOBS_EAGER` the whole Send runs in process.

HOW A "WORKER" IS PLAYED HERE — exactly as B28's file plays it: a recording
dispatcher replaces the transport, and the test runs each dispatched record
through `core.jobs.run_pending`, the entry point a Celery worker uses. A worker
that DIES is a `BaseException` raised from inside the issue pass: `run_job`
catches `Exception` and nothing else, so the record is left `running` with no
one on it — what a SIGKILL leaves. The REAL kill, on PostgreSQL, is
`test_def_bil_8710_send_resume_pg.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.test import override_settings

from apps.billing import issue, run_jobs, send_batches
from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from core import jobs as core_jobs
from core import tenancy as core_tenancy

from tests.test_def_bil_5352_run_status_machine import a_releasable_run, authorise
from tests.test_us_bil_005_issue import TEMPLATE_ID, TEMPLATE_VERSION
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SENT_AT = datetime(2026, 10, 1, 9, 45, tzinfo=UTC)


class Killed(BaseException):
    """A worker that stops mid-bill: not an `Exception`, so `run_job` writes
    nothing and the record is left `running` — what a SIGKILL leaves."""


class Workers:
    """The transport, played by the test: dispatched records wait in `queue`."""

    def __init__(self) -> None:
        self.queue: list[dict] = []
        self.dispatched: list[dict] = []

    def __call__(self, record: dict) -> None:
        self.queue.append(record)
        self.dispatched.append(record)

    def of(self, kind: str) -> list[dict]:
        return [r for r in self.queue if r["kind"] == kind]

    def take(self, kind: str) -> dict:
        for record in list(self.queue):
            if record["kind"] == kind:
                self.queue.remove(record)
                return record
        raise AssertionError(f"nothing queued of kind {kind}: {self.queue}")

    def run(self, record: dict) -> None:
        core_tenancy.clear_current_tenant()
        try:
            core_jobs.run_pending(record["id"])
        finally:
            core_tenancy.clear_current_tenant()

    def drain(self, limit: int = 200) -> int:
        ran = 0
        while self.queue and ran < limit:
            self.run(self.queue.pop(0))
            ran += 1
        return ran


@pytest.fixture()
def workers():
    previous = core_jobs._dispatcher  # noqa: SLF001
    played = Workers()
    core_jobs.set_job_dispatcher(played)
    try:
        yield played
    finally:
        core_jobs.set_job_dispatcher(previous)


@pytest.fixture()
def batch_of(monkeypatch):
    """Batches of `n` bills (500 would make each case a minute of fixtures —
    the split itself is proved at 500 by the pure planner)."""

    def set_size(n: int) -> None:
        monkeypatch.setattr(send_batches, "BATCH_SIZE", n)

    return set_size


def a_signed_off_run(brazos, dana, bills: int, key: str):
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=bills, key=key)
        authorise(run, dana)
        drafts = sorted(
            str(pk)
            for pk in billing_models.Invoice.objects.filter(bill_run=run).values_list(
                "pk", flat=True
            )
        )
    return run, drafts


def press_send(brazos, run):
    with tenant_ctx(brazos):
        return run_jobs.enqueue_issue(
            run,
            issued_at=SENT_AT,
            released_at=SENT_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )


def job(brazos, job_id):
    with tenant_ctx(brazos):
        return core_jobs.current(job_id)


def what_went_out(brazos, run, drafts, audit_rows):
    """Every fact a bill sent twice would change. The audit trail is the
    capture sink every test here writes to (`audit_rows`, autouse)."""
    from apps.ledger import models as ledger_models

    def audits(action, entity_id):
        return sum(
            1
            for row in audit_rows
            if row.get("action") == action and str(row.get("entity_id")) == str(entity_id)
        )

    with tenant_ctx(brazos):
        bills = billing_models.Invoice.objects.filter(pk__in=drafts)
        released = billing_models.BillRunRelease.objects.get(bill_run=run)
        return {
            "statuses": sorted({b.status for b in bills}),
            "numbers": sorted(b.invoice_no for b in bills),
            "entries": sorted(
                ledger_models.JournalEntry.objects.filter(
                    source_type="invoice", source_id=pk
                ).count()
                for pk in drafts
            ),
            "issue_audits": sorted(audits("invoice.issued", pk) for pk in drafts),
            "release_audits": audits("bill_run.released", run.pk),
            "released_at": released.released_at,
            "run_status": billing_models.BillRun.objects.get(pk=run.pk).status,
        }


# ═══════════════════════════════════════════════════════════════════════════
# 1 · DEF-BIL-8726 — no task approaches its time limit at 40,000 bills
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bills,batches", [(1, 1), (500, 1), (501, 2), (40_008, 81)])
def test_8726_1__a_send_is_cut_into_batches_of_at_most_500(bills, batches):
    ids = [f"{i:08d}" for i in range(bills)]
    plan = send_batches.plan_ranges(ids)
    assert len(plan) == batches
    assert max(b["size"] for b in plan) <= 500
    assert sum(b["size"] for b in plan) == bills
    # Open at both ends, so no draft can fall between two batches.
    assert plan[0]["after"] is None and plan[-1]["through"] is None
    for left, right in zip(plan, plan[1:], strict=False):
        assert left["through"] == right["after"]


def test_8726_1__the_worker_send_is_the_coordinator_of_batches(brazos, dana, workers, batch_of):
    """RED before: the worker's Send was `release.release_run` in ONE task —
    the coordinator issued every bill itself and dispatched nothing."""
    batch_of(2)
    run, drafts = a_signed_off_run(brazos, dana, 5, "2026-06|8726-plan")
    coordinator = press_send(brazos, run)
    workers.run(workers.take(run_jobs.ISSUE_JOB))
    record = job(brazos, coordinator["id"])
    assert record["status"] == core_jobs.RUNNING, record
    assert len(record["checkpoint"]["batches"]) == 3
    assert [b["size"] for b in record["checkpoint"]["batches"]] == [2, 2, 1]
    # Nothing issued by the coordinator itself.
    with tenant_ctx(brazos):
        assert (
            billing_models.Invoice.objects.filter(
                pk__in=drafts, status=billing_models.INVOICE_DRAFT
            ).count()
            == 5
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2 · a batched Send issues every bill once and completes its release once
# ═══════════════════════════════════════════════════════════════════════════
def test_8726_2__every_bill_issued_once_and_the_release_completed_once(
    audit_rows, brazos, dana, workers, batch_of
):
    batch_of(2)
    run, drafts = a_signed_off_run(brazos, dana, 5, "2026-06|8726-all")
    with tenant_ctx(brazos):
        numbers_before = sorted(
            billing_models.Invoice.objects.filter(pk__in=drafts).values_list(
                "invoice_no", flat=True
            )
        )
    coordinator = press_send(brazos, run)
    with override_settings(BILLING_SEND_BATCHES_PER_UTILITY=2):
        workers.drain()
    done = job(brazos, coordinator["id"])
    out = what_went_out(brazos, run, drafts, audit_rows)
    print(f"\nPROOF 8726 batched Send: job={done['status']} {done['progress']} {out}")
    assert done["status"] == core_jobs.SUCCEEDED, done
    assert done["progress"] == {"done": 5, "total": 5}
    assert out["statuses"] == [billing_models.INVOICE_ISSUED]
    assert out["numbers"] == numbers_before  # every number the draft's, none twice
    assert out["entries"] == [1] * 5
    assert out["issue_audits"] == [1] * 5
    assert out["release_audits"] == 1
    assert out["released_at"] == SENT_AT
    assert out["run_status"] == billing_runs.RUN_STATUS_ISSUED
    batches = [r for r in workers.dispatched if r["kind"] == send_batches.SEND_BATCH_JOB]
    assert len(batches) == 3


def test_8726_2__a_second_send_after_it_finished_writes_nothing(
    audit_rows, brazos, dana, workers, batch_of
):
    batch_of(2)
    run, drafts = a_signed_off_run(brazos, dana, 3, "2026-06|8726-replay")
    press_send(brazos, run)
    workers.drain()
    before = what_went_out(brazos, run, drafts, audit_rows)
    again = press_send(brazos, run)
    workers.drain()
    assert job(brazos, again["id"])["status"] == core_jobs.SUCCEEDED
    assert what_went_out(brazos, run, drafts, audit_rows) == before


# ═══════════════════════════════════════════════════════════════════════════
# 3 · the per-utility cap — a platform setting, half the workers by default
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("workers_n,explicit,cap", [(2, 0, 1), (8, 0, 4), (8, 3, 3), (1, 0, 1)])
def test_8726_3__the_cap_is_half_the_billing_workers_never_fewer_than_one(workers_n, explicit, cap):
    with override_settings(BILLING_WORKERS=workers_n, BILLING_SEND_BATCHES_PER_UTILITY=explicit):
        assert send_batches.batch_cap() == cap


def test_8726_3__one_utility_never_runs_more_send_batches_than_its_cap(
    audit_rows, brazos, dana, workers, batch_of
):
    batch_of(1)
    run, drafts = a_signed_off_run(brazos, dana, 4, "2026-06|8726-cap")
    press_send(brazos, run)
    most = 0
    with override_settings(BILLING_SEND_BATCHES_PER_UTILITY=2):
        workers.run(workers.take(run_jobs.ISSUE_JOB))
        while workers.queue:
            with tenant_ctx(brazos):
                active = len(core_jobs.active_records(send_batches.SEND_BATCH_JOB))
            most = max(most, active)
            workers.run(workers.queue.pop(0))
    assert most == 2
    assert what_went_out(brazos, run, drafts, audit_rows)["statuses"] == [
        billing_models.INVOICE_ISSUED
    ]


# ═══════════════════════════════════════════════════════════════════════════
# 4 · DEF-BIL-8710 — a Send whose worker died is handed back, and carries on
#     from the bills already issued
# ═══════════════════════════════════════════════════════════════════════════
def _kill_a_batch_after_one_bill(monkeypatch, brazos, run, workers):
    """Run the coordinator, then a batch that dies after issuing ONE bill."""
    workers.run(workers.take(run_jobs.ISSUE_JOB))
    real = issue.issue_invoice
    calls = {"n": 0}

    def dies_on_the_second(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise Killed("SIGKILL")
        return real(*args, **kwargs)

    monkeypatch.setattr(issue, "issue_invoice", dies_on_the_second)
    batch = workers.take(send_batches.SEND_BATCH_JOB)
    with pytest.raises(Killed):
        workers.run(batch)
    monkeypatch.setattr(issue, "issue_invoice", real)
    return batch


@pytest.fixture()
def nobody_working(settings):
    """The workers answer and none of them has the job (a dead worker)."""
    settings.BILLING_JOB_STOPPED_FLOOR_SECONDS = 0
    before = core_jobs._liveness_probe  # noqa: SLF001
    core_jobs.set_liveness_probe(lambda job_id: False)
    try:
        yield
    finally:
        core_jobs.set_liveness_probe(before)


def test_8710_1__the_send_screens_poll_hands_a_dead_send_back_and_progress_continues(
    audit_rows,
    brazos,
    dana,
    workers,
    batch_of,
    monkeypatch,
    nobody_working,
    django_capture_on_commit_callbacks,
):
    """RED before: there was no `…/issue/progress` read (the screen polled
    `GET /jobs/{id}`, which hands nothing back), and a hand-back by hand
    restarted the progress at 0."""
    from apps.billing import api as billing_api
    from tests.test_us_bil_001_003_run_api import an_actor_user
    from tests.test_us_ten_helpers import api_call

    batch_of(3)
    run, drafts = a_signed_off_run(brazos, dana, 5, "2026-06|8710-poll")
    coordinator = press_send(brazos, run)
    batch = _kill_a_batch_after_one_bill(monkeypatch, brazos, run, workers)
    assert job(brazos, batch["id"])["status"] == core_jobs.RUNNING  # nobody on it
    with tenant_ctx(brazos):
        clerk = an_actor_user(brazos)
        issued_before = billing_models.Invoice.objects.filter(
            pk__in=drafts, status=billing_models.INVOICE_ISSUED
        ).count()
    assert issued_before == 1
    workers.queue.clear()  # the other batch's message, lost with the worker
    with django_capture_on_commit_callbacks(execute=True):
        polled = api_call(
            billing_api.run_issue_progress,
            "get",
            user=clerk,
            role="billing_clerk",
            tenant=brazos,
            query={"job": coordinator["id"]},
            run_id=str(run.pk),
        )
    assert polled.status_code == 200, polled.data
    assert polled.data["job"]["id"] == coordinator["id"]
    assert polled.data["job"]["resumed"] is True
    # The resumed coordinator is handed to a worker; it re-reads the bills.
    workers.run(workers.take(run_jobs.ISSUE_JOB))
    resumed = job(brazos, coordinator["id"])
    print(f"\nPROOF 8710 progress at hand-back: {resumed['progress']}")
    assert resumed["progress"]["done"] == 1, resumed["progress"]  # not 0
    assert resumed["progress"]["total"] == 5
    workers.drain()
    done = job(brazos, coordinator["id"])
    out = what_went_out(brazos, run, drafts, audit_rows)
    print(f"PROOF 8710 after the hand-back: job={done['status']} {done['progress']} {out}")
    assert done["status"] == core_jobs.SUCCEEDED
    assert out["statuses"] == [billing_models.INVOICE_ISSUED]
    assert out["entries"] == [1] * 5
    assert out["issue_audits"] == [1] * 5
    assert out["release_audits"] == 1


def test_8710_2__pressing_send_again_on_a_dead_send_hands_it_back(
    audit_rows,
    brazos,
    dana,
    workers,
    batch_of,
    monkeypatch,
    nobody_working,
    django_capture_on_commit_callbacks,
):
    """RED before: the press folded into the stuck record (202, the same job)
    and nothing ever moved it again."""
    from apps.billing import api as billing_api
    from tests.test_us_bil_001_003_run_api import an_actor_user
    from tests.test_us_ten_helpers import api_call

    batch_of(3)
    run, drafts = a_signed_off_run(brazos, dana, 4, "2026-06|8710-again")
    coordinator = press_send(brazos, run)
    _kill_a_batch_after_one_bill(monkeypatch, brazos, run, workers)
    workers.queue.clear()
    with tenant_ctx(brazos):
        clerk = an_actor_user(brazos)
    with django_capture_on_commit_callbacks(execute=True):
        pressed = api_call(
            billing_api.run_issue,
            "post",
            user=clerk,
            role="billing_clerk",
            tenant=brazos,
            data={"issued_at": SENT_AT.isoformat(), "background": True},
            run_id=str(run.pk),
        )
    assert pressed.status_code == 202, pressed.data
    assert pressed.data["job_id"] == coordinator["id"]
    assert pressed.data["resumed"] is True
    workers.drain()
    out = what_went_out(brazos, run, drafts, audit_rows)
    assert out["statuses"] == [billing_models.INVOICE_ISSUED]
    assert out["entries"] == [1] * 4
    assert out["release_audits"] == 1


def test_8746__a_bill_issued_by_a_killed_batch_does_not_stay_listed_not_sent(
    brazos,
    dana,
    audit_rows,
    workers,
    batch_of,
    monkeypatch,
    nobody_working,
    django_capture_on_commit_callbacks,
):
    """DEF-BIL-8746 — RED before: a bill carrying a send break from an earlier
    pass, issued by a batch that is then killed before it files its breaks, was
    never listed as sent by any pass, so its break stayed open (985 of them at
    40,000) and Sent showed it *not sent*."""
    from apps.billing import api as billing_api
    from tests.test_us_bil_001_003_run_api import an_actor_user
    from tests.test_us_ten_helpers import api_call

    batch_of(3)
    run, drafts = a_signed_off_run(brazos, dana, 3, "2026-06|8743")
    with tenant_ctx(brazos):
        first = billing_models.Invoice.objects.filter(pk__in=drafts).order_by("id").first()
        billing_runs.record_break(
            run,
            billing_runs.Break(
                account_id=str(first.account_id),
                account_no=first.invoice_no,
                stage=billing_models.BREAK_STAGE_SEND,
                reason="issue_failed_unexpectedly",
                detail="an earlier pass could not issue it",
                retryable=True,
            ),
        )
        clerk = an_actor_user(brazos)
    coordinator = press_send(brazos, run)
    _kill_a_batch_after_one_bill(monkeypatch, brazos, run, workers)  # issues `first`, then dies
    with tenant_ctx(brazos):
        assert (
            billing_models.Invoice.objects.get(pk=first.pk).status == billing_models.INVOICE_ISSUED
        )
    with django_capture_on_commit_callbacks(execute=True):
        polled = api_call(
            billing_api.run_issue_progress,
            "get",
            user=clerk,
            role="billing_clerk",
            tenant=brazos,
            query={"job": coordinator["id"]},
            run_id=str(run.pk),
        )
    assert polled.data["job"]["resumed"] is True
    workers.drain()
    assert job(brazos, coordinator["id"])["status"] == core_jobs.SUCCEEDED
    with tenant_ctx(brazos):
        still_open = billing_models.BillRunBreak.objects.filter(
            bill_run=run, stage=billing_models.BREAK_STAGE_SEND, resolution__isnull=True
        ).count()
    assert still_open == 0


def test_8710_3__a_send_a_worker_is_still_on_is_left_alone(
    brazos, dana, workers, batch_of, settings
):
    settings.BILLING_JOB_STOPPED_FLOOR_SECONDS = 0
    batch_of(2)
    run, _drafts = a_signed_off_run(brazos, dana, 3, "2026-06|8710-alive")
    coordinator = press_send(brazos, run)
    workers.run(workers.take(run_jobs.ISSUE_JOB))
    batch = workers.take(send_batches.SEND_BATCH_JOB)
    with tenant_ctx(brazos):
        core_jobs.start(batch["id"])  # a worker has it
    before = core_jobs._liveness_probe  # noqa: SLF001
    core_jobs.set_liveness_probe(lambda job_id: True)
    try:
        with tenant_ctx(brazos):
            assert run_jobs.job_is_abandoned(coordinator["id"]) is False
    finally:
        core_jobs.set_liveness_probe(before)


def test_8710_4__a_poll_never_reads_another_runs_send(brazos, dana, workers, batch_of):
    from apps.billing import api as billing_api
    from tests.test_us_bil_001_003_run_api import an_actor_user
    from tests.test_us_ten_helpers import api_call

    batch_of(2)
    run, _ = a_signed_off_run(brazos, dana, 1, "2026-06|8710-mine")
    with tenant_ctx(brazos):
        from tests.test_w3_billing_models import a_run

        other = a_run(brazos, key="2026-07|8710-other")
    theirs = press_send(brazos, other)
    with tenant_ctx(brazos):
        clerk = an_actor_user(brazos)
    polled = api_call(
        billing_api.run_issue_progress,
        "get",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        query={"job": theirs["id"]},
        run_id=str(run.pk),
    )
    assert polled.status_code == 200
    assert polled.data["job"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 5 · under JOBS_EAGER the whole Send runs in process, batch after batch
# ═══════════════════════════════════════════════════════════════════════════
def test_8726_5__eager_runs_every_batch_in_process(audit_rows, brazos, dana, batch_of):
    batch_of(2)
    run, drafts = a_signed_off_run(brazos, dana, 5, "2026-06|8726-eager")
    previous = core_jobs._dispatcher  # noqa: SLF001
    core_jobs.set_job_dispatcher(core_jobs.run_eager)
    try:
        record = press_send(brazos, run)
    finally:
        core_jobs.set_job_dispatcher(previous)
    assert job(brazos, record["id"])["status"] == core_jobs.SUCCEEDED
    out = what_went_out(brazos, run, drafts, audit_rows)
    assert out["statuses"] == [billing_models.INVOICE_ISSUED]
    assert out["release_audits"] == 1
