# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (bulk run · Check) — plan B28, changes row 55
# Rules:    decision log 2026-09-30 *"BULK CHECK BATCH SIZE = 500 ACCOUNTS"* ·
#           *"PER-UTILITY CAP ON PARALLEL CHECK BATCHES = HALF THE BILLING
#           WORKERS, NEVER FEWER THAN 1, AS A PLATFORM SETTING"* · CLAUDE.md
#           hard rules 1 and 6 · hard-won law 14
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B28
# Proof:    10-scripts/b28_parallel_check_proof.py (PostgreSQL 16, 40,000)
# ───────────────────────────────────────────────────────
"""The Check in parallel batches of 500 under one coordinator (B28).

Written BEFORE the code, as r11 step 2c asks, one test per promise of changes
row 55: split by 500 with one code path for every size; totals counted once
after every batch; progress summed across batches; a crash resumes per batch;
the per-utility cap; the tenant inside every batch worker; and a finished batch
dispatched again writes nothing.

HOW A "WORKER" IS PLAYED HERE. A recording dispatcher replaces the transport,
so a dispatched batch is a record in a list, and the test runs it — in the
order it chooses — through `core.jobs.run_pending`, the same entry point a
Celery worker uses. That is how two batches finishing out of order, a batch
crashing, and a slot freeing are all made to happen deterministically on
SQLite. The batch size is patched down (500 accounts would make each case a
minute of fixtures) — the split itself is proved at 500 by the pure planner.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test import override_settings

from apps.billing import check_models, check_store, run_jobs
from core import jobs as core_jobs
from core import tenancy as core_tenancy

from tests.test_bbr_check_engine import BILL_DATE, PERIOD_END, PERIOD_START, a_cycle
from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ── the world ───────────────────────────────────────────────────────────────
def a_run(cycle, label="June 2026 · B28"):
    from apps.billing import runs

    return runs.create_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=BILL_DATE,
        label=label,
    )


def n_accounts(tenant, actor, n, *, code="06-B28", prefix="B28"):
    """`n` billable accounts on one cycle, numbered so the run walks them in
    the order they were made (`<prefix>-00`, `-01`, …)."""
    cycle = a_cycle(tenant, code=code)
    plan = a_priced_plan(tenant, name=f"Plan {code}")
    accounts = []
    for i in range(n):
        unit = a_billed_unit(
            actor, tenant, cycle, plan, asset_no=f"M-{prefix}{i:02d}", label=f"{prefix} {i:02d}"
        )
        accounts.append(an_account(tenant, unit["id"], f"{prefix}-{i:02d}"))
    return cycle, accounts


class Workers:
    """The transport, played by the test: dispatched records wait in `queue`."""

    def __init__(self) -> None:
        self.queue: list[dict] = []
        self.dispatched: list[dict] = []

    def __call__(self, record: dict) -> None:
        self.queue.append(record)
        self.dispatched.append(record)

    def batches(self) -> list[dict]:
        from apps.billing import check_batches

        return [r for r in self.queue if r["kind"] == check_batches.CHECK_BATCH_JOB]

    def take(self, kind: str | None = None, index: int | None = None) -> dict:
        for record in list(self.queue):
            if kind is not None and record["kind"] != kind:
                continue
            if index is not None and (record.get("payload") or {}).get("index") != index:
                continue
            self.queue.remove(record)
            return record
        raise AssertionError(f"nothing queued for kind={kind} index={index}: {self.queue}")

    def run(self, record: dict) -> None:
        """One delivery, the way the Celery task does it: no ambient tenant."""
        core_tenancy.clear_current_tenant()
        try:
            core_jobs.run_pending(record["id"])
        finally:
            core_tenancy.clear_current_tenant()

    def drain(self, limit: int = 500) -> int:
        ran = 0
        while self.queue and ran < limit:
            record = self.queue.pop(0)
            try:
                self.run(record)
            except Exception:  # noqa: BLE001 — the record says failed
                pass
            ran += 1
        return ran


@pytest.fixture()
def workers():
    previous = core_jobs._dispatcher
    played = Workers()
    core_jobs.set_job_dispatcher(played)
    try:
        yield played
    finally:
        core_jobs.set_job_dispatcher(previous)


@pytest.fixture()
def riverbend(growth_plan, identity_seam):
    """A SECOND electric utility (the shared `lonestar` is water-only, and the
    billed-unit fixture meters electric), with its own System Admin."""
    from tests.test_us_met_helpers import seed_physical_series, staff_actor
    from tests.test_us_ten_helpers import lonestarridge_payload, provisioned_tenant

    tenant, _result = provisioned_tenant(
        lonestarridge_payload(
            name="River Bend Electric (B28)",
            subdomain="riverbendb28",
            services=["electric", "water"],
            owner={
                "full_name": "Ana Ruiz",
                "email": "ana.ruiz@riverbend-b28.test",
                "password": "Th1rd!passw0rd",
                "phone": None,
            },
        )
    )
    seed_physical_series(tenant)
    return tenant, staff_actor(tenant, "system_admin", "admin@riverbend-b28.test")


@pytest.fixture()
def batch_of(monkeypatch):
    def set_size(size: int) -> None:
        from apps.billing import check_batches

        monkeypatch.setattr(check_batches, "BATCH_SIZE", size)

    return set_size


def start_check(tenant, run, workers):
    with tenant_ctx(tenant):
        record = run_jobs.enqueue_check(run, actor_user_id=None)
    coordinator = workers.take(kind=run_jobs.CHECK_JOB)
    workers.run(coordinator)
    return record["id"]


def job(tenant, job_id):
    with tenant_ctx(tenant):
        return core_jobs.current(job_id)


def active_batches(tenant) -> int:
    from apps.billing import check_batches

    with tenant_ctx(tenant):
        return len(core_jobs.active_records(check_batches.CHECK_BATCH_JOB))


# ══════════════════════════════════════════════════════════════════════════
# 1 · split by 500 — one code path for every size
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
@pytest.mark.parametrize("accounts,batches", [(300, 1), (1_000, 2), (40_000, 80), (501, 2)])
def test_b28_1__the_check_is_split_into_batches_of_500(accounts, batches):
    from apps.billing import check_batches

    assert check_batches.BATCH_SIZE == 500
    numbers = [f"AC-{i:06d}" for i in range(accounts)]
    plan = check_batches.plan_ranges(numbers)
    assert len(plan) == batches
    # Contiguous, nothing between two batches and nothing outside the first
    # and last: the first opens at the start, the last runs to the end.
    assert plan[0]["after"] is None and plan[-1]["through"] is None
    for left, right in zip(plan, plan[1:]):
        assert right["after"] == left["through"]
    # Every batch but the last is exactly 500 accounts.
    for i, batch in enumerate(plan[:-1]):
        assert batch["through"] == numbers[(i + 1) * 500 - 1]


# BULK-CHG-55
def test_b28_1__the_inline_check_walks_the_same_batches(brazos, dana, batch_of, monkeypatch):
    """300 accounts = 1 batch inline as in a worker: ONE code path."""
    from apps.billing import check_batches

    batch_of(2)
    seen: list[list[str]] = []
    real = check_batches.check_batch

    def spy(run, batch, **kwargs):
        prepared = real(run, batch, **kwargs)
        seen.append(sorted(str(a) for a in prepared.findings))
        return prepared

    monkeypatch.setattr(check_batches, "check_batch", spy)
    with tenant_ctx(brazos):
        cycle, accounts = n_accounts(brazos, dana, 5)
        run = a_run(cycle)
        summary = check_store.check_run(run)
    assert summary["accounts"] == 5
    assert [len(one) for one in seen] == [2, 2, 1]


# ══════════════════════════════════════════════════════════════════════════
# 2 · totals counted ONCE, after every batch
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
def test_b28_2__the_run_totals_are_counted_once_after_the_last_batch(
    brazos, dana, workers, batch_of, monkeypatch
):
    from apps.billing import check_batches

    batch_of(2)
    events: list[str] = []
    real_counts = check_store.counts
    real_batch = check_batches.check_batch

    def counting(run):
        events.append("counts")
        return real_counts(run)

    def batching(run, batch, **kwargs):
        events.append("batch")
        return real_batch(run, batch, **kwargs)

    monkeypatch.setattr(check_store, "counts", counting)
    monkeypatch.setattr(check_batches, "check_batch", batching)
    with override_settings(BILLING_CHECK_BATCHES_PER_UTILITY=2):
        with tenant_ctx(brazos):
            cycle, _accounts = n_accounts(brazos, dana, 5)
            run = a_run(cycle)
        coordinator = start_check(brazos, run, workers)
        workers.drain()
    assert events.count("batch") == 3
    assert events.count("counts") == 1
    last_batch = max(i for i, e in enumerate(events) if e == "batch")
    assert events.index("counts") > last_batch
    assert job(brazos, coordinator)["status"] == core_jobs.SUCCEEDED
    with tenant_ctx(brazos):
        run.refresh_from_db()
        assert run.findings_summary["accounts"] == 5
        assert run.findings_summary["job_id"] == coordinator


# ══════════════════════════════════════════════════════════════════════════
# 3 · progress n of N is the SUM of every batch
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
def test_b28_3__progress_adds_up_every_batch_in_any_order(brazos, dana, workers, batch_of):
    batch_of(2)
    with override_settings(BILLING_CHECK_BATCHES_PER_UTILITY=3):
        with tenant_ctx(brazos):
            cycle, _accounts = n_accounts(brazos, dana, 5)
            run = a_run(cycle)
        coordinator = start_check(brazos, run, workers)
        assert job(brazos, coordinator)["progress"] == {"done": 0, "total": 5}
        assert sorted(r["payload"]["index"] for r in workers.batches()) == [0, 1, 2]
        # The SECOND batch finishes first — progress is a sum, not a cursor.
        workers.run(workers.take(index=1))
        assert job(brazos, coordinator)["progress"] == {"done": 2, "total": 5}
        workers.run(workers.take(index=0))
        assert job(brazos, coordinator)["progress"] == {"done": 4, "total": 5}
        assert job(brazos, coordinator)["status"] == core_jobs.RUNNING
        workers.run(workers.take(index=2))
    after = job(brazos, coordinator)
    assert after["status"] == core_jobs.SUCCEEDED
    assert after["progress"] == {"done": 5, "total": 5}


# ══════════════════════════════════════════════════════════════════════════
# 4 · a crash in batch 3 of 5 — resume does only 3 to 5
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
def test_b28_4__a_crash_in_batch_3_of_5_resumes_only_batches_3_to_5(
    brazos, dana, workers, batch_of, monkeypatch
):
    from apps.billing import check_engine

    batch_of(2)
    real_save = check_store.save_account_check
    crash = {"on": "B28-05"}  # the SECOND account of the third batch

    def save(run, checked, **kwargs):
        if checked.account_no == crash["on"]:
            raise RuntimeError("worker lost mid-batch")
        return real_save(run, checked, **kwargs)

    monkeypatch.setattr(check_store, "save_account_check", save)
    with override_settings(BILLING_CHECK_BATCHES_PER_UTILITY=1):
        with tenant_ctx(brazos):
            cycle, _accounts = n_accounts(brazos, dana, 10)
            run = a_run(cycle)
        coordinator = start_check(brazos, run, workers)
        workers.run(workers.take(index=0))
        workers.run(workers.take(index=1))
        with pytest.raises(RuntimeError):
            workers.run(workers.take(index=2))
        assert job(brazos, coordinator)["status"] == core_jobs.FAILED
        assert workers.queue == []  # nothing dispatched past the crash
        with tenant_ctx(brazos):
            saved = set(
                check_models.BillRunAccountCheck.objects.filter(bill_run=run).values_list(
                    "account_no", flat=True
                )
            )
        assert saved == {"B28-00", "B28-01", "B28-02", "B28-03", "B28-04"}

        crash["on"] = None
        checked: list[str] = []
        real_check = check_engine.check_account

        def spy(account, context, **kwargs):
            checked.append(account.account_no)
            return real_check(account, context, **kwargs)

        monkeypatch.setattr(check_engine, "check_account", spy)
        # The clerk's Resume: the coordinator goes back to a worker.
        with tenant_ctx(brazos):
            core_jobs.redispatch(coordinator, stalled_after=0)
        workers.drain()
    assert checked == ["B28-05", "B28-06", "B28-07", "B28-08", "B28-09"]
    after = job(brazos, coordinator)
    assert after["status"] == core_jobs.SUCCEEDED
    assert after["progress"] == {"done": 10, "total": 10}
    with tenant_ctx(brazos):
        assert check_models.BillRunAccountCheck.objects.filter(bill_run=run).count() == 10


# ══════════════════════════════════════════════════════════════════════════
# 5 · the cap — per utility, a platform setting, never blocking another
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "workers_n,explicit,cap", [(8, 0, 4), (2, 0, 1), (1, 0, 1), (0, 0, 1), (8, 3, 3), (16, 0, 8)]
)
# BULK-CHG-55
def test_b28_5__the_cap_is_half_the_billing_workers_never_fewer_than_one(workers_n, explicit, cap):
    from apps.billing import check_batches

    with override_settings(BILLING_WORKERS=workers_n, BILLING_CHECK_BATCHES_PER_UTILITY=explicit):
        assert check_batches.batch_cap() == cap


# BULK-CHG-55
def test_b28_5__one_utility_never_runs_more_batches_than_its_cap(
    brazos, riverbend, dana, workers, batch_of
):
    other_utility, ana = riverbend
    batch_of(1)
    with override_settings(BILLING_CHECK_BATCHES_PER_UTILITY=2):
        with tenant_ctx(brazos):
            cycle, _accounts = n_accounts(brazos, dana, 5)
            run = a_run(cycle)
            cycle_b, _more = n_accounts(brazos, dana, 2, code="06-B28B", prefix="B28B")
            second = a_run(cycle_b, label="June 2026 · B28 second")
        first = start_check(brazos, run, workers)
        assert len(workers.batches()) == 2 and active_batches(brazos) == 2
        # A second run in the SAME utility waits for a slot …
        later = start_check(brazos, second, workers)
        assert len(workers.batches()) == 2
        # … while ANOTHER utility is not held back by this one's cap.
        with tenant_ctx(other_utility):
            cycle_l, _l = n_accounts(other_utility, ana, 2, code="06-B28L", prefix="B28L")
            other = a_run(cycle_l, label="June 2026 · River Bend")
        elsewhere = start_check(other_utility, other, workers)
        theirs = [r for r in workers.batches() if str(r["tenant_id"]) == str(other_utility.id)]
        assert len(theirs) == 2
        peak = 0
        while workers.queue:
            workers.run(workers.queue.pop(0))
            peak = max(peak, active_batches(brazos))
            assert active_batches(brazos) <= 2
    assert peak <= 2
    for tenant, coordinator in ((brazos, first), (brazos, later), (other_utility, elsewhere)):
        assert job(tenant, coordinator)["status"] == core_jobs.SUCCEEDED


# ══════════════════════════════════════════════════════════════════════════
# 6 · tenant isolation inside every batch worker (hard rule 1)
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
def test_b28_6__every_batch_runs_under_its_own_utility(
    brazos, lonestar, dana, workers, batch_of, monkeypatch
):
    from apps.billing import check_batches

    batch_of(2)
    inside: list[tuple] = []
    real = check_batches.check_batch

    def spy(run, batch, **kwargs):
        guc = None
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.tenant_id', true)")
                guc = cursor.fetchone()[0]
        inside.append((str(core_tenancy.current_tenant_id()), guc))
        return real(run, batch, **kwargs)

    monkeypatch.setattr(check_batches, "check_batch", spy)
    with override_settings(BILLING_CHECK_BATCHES_PER_UTILITY=3):
        with tenant_ctx(brazos):
            cycle, _accounts = n_accounts(brazos, dana, 5)
            run = a_run(cycle)
        coordinator = start_check(brazos, run, workers)
        # The worker process last served ANOTHER utility: the batch must not
        # inherit it. Delivered through the real Celery task body, which takes
        # the tenant from the message (B3) — called in-process, no broker.
        from apps.tenancy import tasks as tenancy_tasks

        for record in list(workers.queue):
            workers.queue.remove(record)
            core_tenancy.set_current_tenant(lonestar.id)
            tenancy_tasks.run_pending_job(
                str(record["id"]), str(record["tenant_id"]), kind=record["kind"]
            )
            core_tenancy.clear_current_tenant()
    assert len(inside) == 3
    for python_side, database_side in inside:
        assert python_side == str(brazos.id)
        if connection.vendor == "postgresql":
            assert database_side == str(brazos.id)
    assert job(brazos, coordinator)["status"] == core_jobs.SUCCEEDED


# ══════════════════════════════════════════════════════════════════════════
# 7 · idempotency — a finished batch dispatched again writes nothing
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
def test_b28_7__a_finished_batch_dispatched_again_writes_nothing(
    brazos, dana, workers, batch_of, monkeypatch
):
    from apps.billing import check_engine

    batch_of(2)
    with override_settings(BILLING_CHECK_BATCHES_PER_UTILITY=3):
        with tenant_ctx(brazos):
            cycle, _accounts = n_accounts(brazos, dana, 5)
            run = a_run(cycle)
        coordinator = start_check(brazos, run, workers)
        first = workers.take(index=0)
        workers.run(first)
        workers.drain()
    with tenant_ctx(brazos):
        before = dict(
            check_models.BillRunAccountCheck.objects.filter(bill_run=run).values_list(
                "account_no", "checked_at"
            )
        )
        findings_before = check_models.BillRunFinding.objects.filter(bill_run=run).count()
    writes: list[str] = []
    checks: list[str] = []
    real_save = check_store.save_account_check
    real_check = check_engine.check_account
    monkeypatch.setattr(
        check_store,
        "save_account_check",
        lambda run, checked, **kw: writes.append(checked.account_no) or real_save(run, checked, **kw),
    )
    monkeypatch.setattr(
        check_engine,
        "check_account",
        lambda account, ctx, **kw: checks.append(account.account_no) or real_check(account, ctx, **kw),
    )
    # (a) the transport delivers the finished batch again: refused at start.
    with pytest.raises(core_jobs.JobsError):
        workers.run(first)
    # (b) the BODY itself, handed the finished batch's record: nothing to do.
    with tenant_ctx(brazos):
        record = core_jobs.current(first["id"])
        run_jobs.run_check_batch_job(record)
    assert writes == [] and checks == []
    with tenant_ctx(brazos):
        after = dict(
            check_models.BillRunAccountCheck.objects.filter(bill_run=run).values_list(
                "account_no", "checked_at"
            )
        )
        assert after == before
        assert check_models.BillRunFinding.objects.filter(bill_run=run).count() == findings_before
    assert job(brazos, coordinator)["status"] == core_jobs.SUCCEEDED


# ══════════════════════════════════════════════════════════════════════════
# 8 · JOBS_EAGER — the batches run in order, in process (dev server, tests)
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
def test_b28_8__eager_runs_every_batch_in_order_in_process(brazos, dana, batch_of, monkeypatch):
    from apps.billing import check_batches

    batch_of(2)
    order: list[int] = []
    real = check_batches.run_batch

    def spy(record):
        order.append(record["payload"]["index"])
        return real(record)

    monkeypatch.setattr(check_batches, "run_batch", spy)
    with override_settings(JOBS_EAGER=True, BILLING_CHECK_BATCHES_PER_UTILITY=3):
        with tenant_ctx(brazos):
            cycle, _accounts = n_accounts(brazos, dana, 5)
            run = a_run(cycle)
            record = run_jobs.enqueue_check(run, actor_user_id=None)
            after = core_jobs.current(record["id"])
            run.refresh_from_db()
    assert order == [0, 1, 2]
    assert after["status"] == core_jobs.SUCCEEDED
    assert after["progress"] == {"done": 5, "total": 5}
    assert run.findings_summary["accounts"] == 5
