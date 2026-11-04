# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (bulk run · Check) — plan B28, changes row 55
# Rules:    decision log 2026-09-30 *"BULK CHECK BATCH SIZE = 500 ACCOUNTS"*
#           (PO: *"Batch size: my pick is 500 - this size is okay"*) ·
#           *"PER-UTILITY CAP ON PARALLEL CHECK BATCHES = HALF THE BILLING
#           WORKERS, NEVER FEWER THAN 1, AS A PLATFORM SETTING"* · CLAUDE.md
#           hard rules 1 (tenant scoping) and 6 (idempotency) · hard-won law 14
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B28
# Tests:    06-backend/tests/test_b28_parallel_check_batches.py ·
#           10-scripts/b28_parallel_check_proof.py (PostgreSQL 16, 40,000)
# ───────────────────────────────────────────────────────
"""THE CHECK IN PARALLEL BATCHES OF 500, UNDER ONE COORDINATOR (B28).

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file carries IDEMPOTENCY KEYS (each batch's
scope key, `billing:check-batch:<coordinator>:<index>`, and the resume-per-batch
skip that makes a re-delivered batch write nothing), a CLAUDE.md 🔒 path. AI-
authored 2026-10-01 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

WHAT CHANGES ROW 55 ASKED FOR, AND WHERE EACH IS
------------------------------------------------
* **One code path for every size** — `plan` cuts the run's accounts into
  batches of `BATCH_SIZE` (500) in account-number order: 300 accounts = 1
  batch, 1,000 = 2, 40,000 = 80. The INLINE Check (`check_store.check_run`)
  walks the same plan, one batch after another, and calls the same
  `check_batch` and `finalize_summary`; the worker path differs only in WHO
  runs each batch.
* **A per-utility cap** — `batch_cap()`: half the billing workers, never fewer
  than 1, from two platform settings (`BILLING_WORKERS`,
  `BILLING_CHECK_BATCHES_PER_UTILITY`), so it moves without a code change.
  `pump` never lets one utility hold more batch jobs (queued or running) than
  that, across ALL its runs. Another utility's batches are counted under its
  own tenant and its own lock, so one utility's cap never holds another back.
* **Run totals counted once, after every batch** — a batch saves its accounts
  and nothing else; `_finalize` (run by whichever batch finishes LAST, inside
  the utility's lock, so exactly one does) deletes accounts no longer in scope,
  stores the opening answers, finds the units nobody bills and counts the
  tiles — ONCE.
* **Progress adds up all batches** — the coordinator's `done` is the number of
  accounts THIS pass has saved (`job_id` on the saved row), counted in the
  database, so two batches finishing out of order still read *n of N*.
* **A crash resumes per batch** — each batch skips the accounts this pass
  already saved; a resumed coordinator re-dispatches only the batches that did
  not finish (a failed batch, or a running one whose worker is gone).

HOW THE WORK MOVES, ON THE EXISTING JOB MACHINERY (no new queue technology)
--------------------------------------------------------------------------
The Check job (`run_jobs.CHECK_JOB`) is the COORDINATOR. It plans, writes the
plan to its checkpoint, dispatches up to the cap of batch jobs
(`CHECK_BATCH_JOB`, billing's own queue), and returns `core.jobs.HANDED_OFF`:
its record stays `running` while the batches work, so the screen polling it
keeps reading *n of N*, and it holds NO worker — a coordinator that waited for
its batches would hold a worker slot, and with two slots two utilities would
deadlock. Each batch, when it ends, succeeds itself and PUMPS: it dispatches
the next batch into the freed slot, or — when every batch is done —
finalizes and succeeds the coordinator.

Under `JOBS_EAGER` (the dev server, demo box and eager tests) the dispatcher
runs a batch in-process the moment it is dispatched, so `pump` loops: it
dispatches, the batch runs to its end, and the loop dispatches the next. The
batches run in order, one at a time, in the caller's process. A batch's own
end-of-batch pump finds the loop already on the stack and leaves the next
step to it (`_local`), so nothing recurses 80 deep.

⚠ **EVERY WRITE TO A COORDINATOR'S RECORD HAPPENS INSIDE `tenant_lock`.** The
job store saves a WHOLE record, so two batches each loading the coordinator,
adding their own fact and saving would lose one — a finished batch forgotten,
or a succeeded coordinator written back to `running`. The lock is a
PostgreSQL transaction-level advisory lock on the utility, so two utilities
never wait for each other; on SQLite (one writer) it is the transaction alone.
Records are DISPATCHED only after the lock's transaction commits, so a worker
never reads a record it cannot yet see and an eager batch never runs inside
the lock.

THE STALE-READ WINDOWS (`DEF-BIL-8600`, `DEF-BIL-8601`) ARE NOT WIDENED.
Each batch still opens its own read (`CheckContext.batches`) and stamps every
account it saves with THAT batch's read time, exactly as one 500-account chunk
of the single pass did; a batch dispatched ten minutes into the pass stamps ten
minutes later, as the eleventh chunk always did. Running batches side by side
changes when a chunk runs, never which moment its accounts are stamped with.
Neither window is closed here either: 8600 is the partial re-check path, which
this file does not touch, and 8601 needs the database's snapshot boundary
rather than the application clock — both stay open on their own rows.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from django.db import connection, transaction

from apps.billing import check_models, runs
from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.billing")

#: PO 2026-09-30, verbatim: *"Batch size: my pick is 500 - this size is
#: okay"*. The same figure the engine already reads a chunk in
#: (`runs.ACCOUNT_CHUNK`, `check_engine.CHUNK`), so one batch is one read.
BATCH_SIZE = 500

#: The batch's job kind, on billing's own queue (`run_jobs.register`).
CHECK_BATCH_JOB = "billing.run.check_batch"

#: How often a batch writes its heartbeat and the coordinator's *n of N*, in
#: accounts — `run_jobs.PROGRESS_EVERY`'s figure: ~1–2 s of work at the B27
#: rate, far inside `BILLING_JOB_STOPPED_FLOOR_SECONDS` (20 s).
PROGRESS_EVERY = 25

#: A pass whose scope holds no account still runs ONE (empty) batch, so the
#: run's refusals (a one-time run, a missing bill date) and its unavailable
#: facts are reached exactly as the one-pass Check reached them.
EMPTY_BATCH: dict[str, Any] = {"index": 0, "after": None, "through": None, "ids": [], "size": 0}


# ── the cap ─────────────────────────────────────────────────────────────────
def batch_cap() -> int:
    """How many batch jobs ONE utility may have queued or running at once.

    Decision log 2026-09-30: half the billing workers, never fewer than 1, a
    platform setting. `BILLING_CHECK_BATCHES_PER_UTILITY` above 0 is an
    explicit cap; otherwise `max(1, BILLING_WORKERS // 2)` — 8 workers → 4,
    2 → 1. Both are declared in `config/settings/base.py` (DEF-2806: a setting
    no module declares is an override nobody can make)."""
    from django.conf import settings

    explicit = int(getattr(settings, "BILLING_CHECK_BATCHES_PER_UTILITY", 0) or 0)
    if explicit > 0:
        return explicit
    workers = int(getattr(settings, "BILLING_WORKERS", 2) or 0)
    return max(1, workers // 2)


# ── the plan ────────────────────────────────────────────────────────────────
def plan_ranges(account_nos: list[str], size: int | None = None) -> list[dict[str, Any]]:
    """Cut an account-number-ordered list into batches of `size` (500).

    Each batch is a RANGE — accounts numbered after `after` and up to
    `through` — not a list of ids, so 80 batches fit in a few kilobytes of the
    coordinator's checkpoint. The first opens at the start (`after` None) and
    the last runs to the end (`through` None), so an account added while the
    pass runs falls into exactly one batch and none is left between two.
    The comparison is the DATABASE's (`account_no__gt`/`__lte` on the same
    ordering the list came from), never Python's, so a collation that sorts
    differently from `str` cannot open a gap."""
    size = size or BATCH_SIZE
    total = len(account_nos)
    count = (total + size - 1) // size
    return [
        {
            "index": i,
            "after": account_nos[i * size - 1] if i else None,
            "through": account_nos[(i + 1) * size - 1] if i < count - 1 else None,
            "ids": None,
            "size": min(size, total - i * size),
        }
        for i in range(count)
    ]


def _scope_services(run: Any) -> tuple[str, ...] | None:
    scope = run.scope_services
    return None if scope is None else tuple(scope)


def plan(run: Any, only_accounts: Any = None) -> dict[str, Any]:
    """`{"batches": [...], "total": N}` for a whole pass (ranges) or a pass
    over NAMED accounts (each batch carries its ≤ 500 ids). Resolves the scope
    through `runs.scope_accounts` — the pass's own two seams, every refusal a
    `UtilityWideStop` — and reads only account numbers (or ids), never rows."""
    if run.cycle_id is None:
        # A one-time run has no population; `prepared_for` owns that refusal.
        from apps.billing import selectors

        selectors.prepared_for(run, only_accounts=[])
    accounts = runs.scope_accounts(run.cycle_id, _scope_services(run))
    if not hasattr(accounts, "filter"):
        return {"batches": [], "total": 0}
    if only_accounts is None:
        numbers = list(accounts.values_list("account_no", flat=True))
        return {"batches": plan_ranges(numbers), "total": len(numbers)}
    wanted = sorted({str(one) for one in only_accounts if one})
    ids = [str(one) for one in accounts.filter(pk__in=wanted).values_list("id", flat=True)]
    size = BATCH_SIZE
    batches = [
        {
            "index": i,
            "after": None,
            "through": None,
            "ids": ids[i * size : (i + 1) * size],
            "size": len(ids[i * size : (i + 1) * size]),
        }
        for i in range((len(ids) + size - 1) // size)
    ]
    return {"batches": batches, "total": len(ids)}


def _batch_ids(run: Any, batch: dict[str, Any], scope: Any) -> list[str]:
    if batch.get("ids") is not None:
        return [str(one) for one in batch["ids"]]
    accounts = scope[1]
    if not hasattr(accounts, "filter"):
        return []
    if batch.get("after") is not None:
        accounts = accounts.filter(account_no__gt=batch["after"])
    if batch.get("through") is not None:
        accounts = accounts.filter(account_no__lte=batch["through"])
    return [str(one) for one in accounts.values_list("id", flat=True)]


def check_batch(
    run: Any,
    batch: dict[str, Any],
    *,
    on_account: Any = None,
    skip_saved_by: Any = None,
    resume_skip: Any = None,
) -> Any:
    """Check ONE batch: the same `selectors.prepared_for` → `runs.prepare_run`
    → `check_engine` pass, narrowed to the batch's accounts (so no run-shape
    rows — those are `_finalize`'s, once). Answers the `PreparedRun`, or None
    when there was nothing left to do.

    `skip_saved_by` — the coordinator's id — is RESUME PER BATCH: the accounts
    this pass already saved are skipped, so a batch delivered again after a
    crash carries on after its last saved account, and a batch that finished
    writes nothing at all (hard rule 6: the saved row is the record of the
    work, `uq_brac_once` keeps it one row an account)."""
    from apps.billing import selectors

    # The cycle's units are resolved ONCE for the batch and reused by its pass
    # (`runs.open_scope_units` — ~1 s a call on the 40,000-account world).
    scope = runs._run_scope(run.cycle_id, _scope_services(run))
    ids = _batch_ids(run, batch, scope)
    skip = resume_skip
    if skip_saved_by is not None and ids:
        done = {
            str(one)
            for one in check_models.BillRunAccountCheck.objects.filter(
                tenant_id=core_tenancy.current_tenant_id(),
                bill_run=run,
                job_id=skip_saved_by,
                account_id__in=ids,
            ).values_list("account_id", flat=True)
        }
        if done >= set(ids):
            return None
        if done:

            def skip(account_id: Any, _account_no: Any) -> bool:
                return str(account_id) in done

    token = runs.open_scope_units(run.cycle_id, _scope_services(run), scope[0])
    try:
        return selectors.prepared_for(
            run, only_accounts=ids, on_account=on_account, resume_skip=skip
        )
    finally:
        runs.close_scope_units(token)


def unavailable_of(prepared: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in (getattr(prepared, "unavailable", None) or ())]


def _distinct(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(sorted((str(k), str(v)) for k, v in row.items()))
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def finalize_summary(
    run: Any, *, job_id: Any, whole: bool, unavailable: list[dict[str, Any]]
) -> dict[str, Any]:
    """THE RUN'S TOTALS, COUNTED ONCE, after every batch.

    For a WHOLE pass: the saved accounts no longer in the run's scope are
    deleted (the one-pass Check deleted those it had not seen — the same set
    once the pass is complete), the opening answers are stored (BR-BIL-1040),
    and the units nobody bills are found over the whole scope. Then the tiles
    are counted (`check_store._record_summary`) — the one count of the pass."""
    from apps.billing import check_store

    extra = None
    if whole:
        scope = runs.scope_accounts(run.cycle_id, _scope_services(run))
        saved = check_models.BillRunAccountCheck.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), bill_run=run
        )
        if hasattr(scope, "values"):
            saved.exclude(account_id__in=scope.values("id")).delete()
        else:
            saved.delete()
        check_store.store_opening_answers(run)
        nobody = runs.unbilled_unit_ids(run.cycle_id, _scope_services(run))
        extra = {
            "units_with_nobody_to_bill": len(nobody),
            "units_nobody_ids": nobody,
            "unavailable": _distinct(unavailable),
        }
    return check_store._record_summary(run, job_id=job_id, extra=extra)


# ══════════════════════════════════════════════════════════════════════════
# THE WORKER PATH — coordinator, batches, pump
# ══════════════════════════════════════════════════════════════════════════
@contextmanager
def tenant_lock() -> Iterator[None]:
    """A transaction holding the CURRENT utility's Check lock (see the module
    docstring). PostgreSQL: `pg_advisory_xact_lock`, released at commit or
    rollback — never by hand, so an exception cannot leave it held."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise core_jobs.JobsError("no tenant context for the Check's batch lock (B3)")
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"billing.check:{tenant_id}"]
                )
        yield


def _saved_count(run_id: Any, coordinator_id: Any) -> int:
    return check_models.BillRunAccountCheck.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), bill_run_id=run_id, job_id=coordinator_id
    ).count()


def _run(run_id: Any) -> Any:
    from apps.billing import selectors

    return selectors.run_or_404(run_id)


def _total(record: dict[str, Any]) -> Any:
    return (record.get("progress") or {}).get("total")


def _point_summary_at(run: Any, coordinator_id: str) -> None:
    """The run's summary names THIS job from its first moment, so the screen's
    poll (`GET …/check`) reads its *n of N* and can see it stop — the one-pass
    Check named its job only when it had finished."""
    summary = dict(run.findings_summary or {})
    summary["job_id"] = coordinator_id
    summary["stop"] = None
    run.findings_summary = summary
    run.save(update_fields=["findings_summary", "updated_at"])


def start(record: dict[str, Any]) -> Any:
    """The COORDINATOR's body (`run_jobs.run_check_job`). Plans on its first
    delivery; on a resumed one takes back the batches that stopped. Then pumps
    and hands off — see the module docstring for why it does not wait."""
    from apps.billing import check_store

    coordinator_id = str(record["id"])
    payload = record.get("payload") or {}
    run = _run(payload["run_id"])
    checkpoint = record.get("checkpoint") or {}
    if not checkpoint.get("batches"):
        only = payload.get("account_ids")
        if only is None and getattr(run, "parent_run_id", None) is not None:
            # A CATCH-UP run checks its parent's still-held accounts, fresh, in
            # its own record (PO 2026-09-30) — as `check_store.check_run` does.
            from apps.billing import pending

            only = sorted(pending.held_account_ids(run.parent_run))
        check_store.refuse_if_sent(run)
        try:
            planned = plan(run, only)
        except runs.UtilityWideStop as stop:
            check_store._record_summary(run, stop=stop.as_dict(), job_id=coordinator_id)
            raise
        checkpoint = {
            "batches": planned["batches"] or [dict(EMPTY_BATCH)],
            "total": planned["total"],
            "whole": only is None,
            "jobs": {},
            "finished": [],
        }
        with tenant_lock():
            core_jobs.record_progress(
                coordinator_id, done=0, total=planned["total"], checkpoint=checkpoint
            )
            _point_summary_at(run, coordinator_id)
    else:
        _take_back_stopped(run, coordinator_id)
    pump()
    return core_jobs.HANDED_OFF


def _stall_thresholds() -> tuple[float, float]:
    from django.conf import settings

    return (
        float(getattr(settings, "BILLING_JOB_STALL_SECONDS", 300)),
        float(getattr(settings, "BILLING_JOB_STOPPED_FLOOR_SECONDS", 20)),
    )


def _take_back_stopped(run: Any, coordinator_id: str) -> None:
    """A RESUMED coordinator: a batch that finished is marked finished; one
    that failed, or whose worker is gone, is forgotten so `pump` dispatches it
    again (a NEW record under the same scope key — the old one is no longer
    active) and it carries on after its last saved account. A batch still
    waiting for a worker, or still being worked, is left alone."""
    stall, floor = _stall_thresholds()
    with tenant_lock():
        record = core_jobs.current(coordinator_id)
        if record["status"] != core_jobs.RUNNING:
            return
        checkpoint = dict(record.get("checkpoint") or {})
        jobs = dict(checkpoint.get("jobs") or {})
        finished = list(checkpoint.get("finished") or [])
        for index, job_id in list(jobs.items()):
            if int(index) in finished:
                continue
            batch = core_jobs.current(job_id)
            if batch["status"] == core_jobs.SUCCEEDED:
                finished.append(int(index))
            elif batch["status"] == core_jobs.FAILED:
                del jobs[index]
            elif batch["status"] == core_jobs.RUNNING and core_jobs.is_abandoned(
                job_id, stalled_after=stall, stopped_floor=floor
            ):
                core_jobs.reclaim(job_id, reason="its Check was resumed and no worker is on it")
                del jobs[index]
        checkpoint["jobs"], checkpoint["finished"] = jobs, finished
        core_jobs.record_progress(
            coordinator_id,
            done=_saved_count(run.pk, coordinator_id),
            total=checkpoint.get("total"),
            checkpoint=checkpoint,
        )


_local = threading.local()


def pump() -> None:
    """Fill the CURRENT utility's free batch slots, and finalize every Check of
    it whose batches are all done. See the module docstring for the eager
    loop and why dispatch happens after the lock's commit."""
    if getattr(_local, "pumping", False):
        _local.again = True
        return
    _local.pumping = True
    try:
        while True:
            _local.again = False
            with tenant_lock():
                ready = _dispatchable()
            for record in ready:
                try:
                    core_jobs.dispatch(record)
                except Exception:  # noqa: BLE001 — the record stays queued; Resume re-sends
                    logger.exception("could not hand Check batch %s to a worker", record["id"])
            if not ready and not getattr(_local, "again", False):
                break
    finally:
        _local.pumping = False


def _dispatchable() -> list[dict[str, Any]]:
    """Inside `tenant_lock`: create the next batch records up to the cap, in
    the order the Checks were started, and finalize the finished ones."""
    slots = batch_cap() - len(core_jobs.active_records(CHECK_BATCH_JOB))
    from apps.billing import run_jobs

    ready: list[dict[str, Any]] = []
    for coordinator in core_jobs.active_records(run_jobs.CHECK_JOB):
        if coordinator["status"] != core_jobs.RUNNING:
            continue
        checkpoint = dict(coordinator.get("checkpoint") or {})
        batches = checkpoint.get("batches")
        if not batches:
            continue  # not planned yet, or a partial re-check (one pass)
        jobs = dict(checkpoint.get("jobs") or {})
        finished = set(checkpoint.get("finished") or [])
        pending = [b for b in batches if str(b["index"]) not in jobs]
        if not pending:
            if finished >= {b["index"] for b in batches}:
                _finalize_guarded(coordinator, checkpoint)
            continue
        added = False
        for batch in pending:
            if slots <= 0:
                break
            record = core_jobs.enqueue(
                CHECK_BATCH_JOB,
                payload={
                    "run_id": coordinator["payload"]["run_id"],
                    "coordinator": coordinator["id"],
                    "index": batch["index"],
                    "batch": batch,
                },
                scope_key=f"billing:check-batch:{coordinator['id']}:{batch['index']}",
                dispatch=False,
            )
            jobs[str(batch["index"])] = record["id"]
            ready.append(record)
            slots -= 1
            added = True
        if added:
            checkpoint["jobs"] = jobs
            core_jobs.record_progress(
                coordinator["id"],
                done=(coordinator.get("progress") or {}).get("done") or 0,
                total=_total(coordinator),
                checkpoint=checkpoint,
            )
    return ready


def _finalize_guarded(coordinator: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    """`_finalize` in its own SAVEPOINT (hard-won law 14): a refusal while
    counting must not poison the lock's transaction, which may already hold
    another Check's new batch records. A utility-wide stop is recorded on the
    run and fails the Check with a sentence; anything else fails it too."""
    from apps.billing import check_store

    try:
        with transaction.atomic():
            _finalize(coordinator, checkpoint)
    except Exception as broken:  # noqa: BLE001 — the Check fails with a sentence
        core_jobs.reraise_if_time_limit(broken)
        logger.exception("Check %s could not count its totals", coordinator["id"])
        if isinstance(broken, runs.UtilityWideStop):
            check_store._record_summary(
                _run(coordinator["payload"]["run_id"]),
                stop=broken.as_dict(),
                job_id=coordinator["id"],
            )
        core_jobs.fail(coordinator["id"], core_jobs.failure_text(broken))


def _finalize(coordinator: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    run = _run(coordinator["payload"]["run_id"])
    unavailable: list[dict[str, Any]] = []
    for job_id in (checkpoint.get("jobs") or {}).values():
        unavailable.extend((core_jobs.current(job_id).get("checkpoint") or {}).get("unavailable") or [])
    finalize_summary(run, job_id=coordinator["id"], whole=bool(checkpoint.get("whole")), unavailable=unavailable)
    final = _saved_count(run.pk, coordinator["id"])
    core_jobs.record_progress(
        coordinator["id"], done=final, total=final, checkpoint={**checkpoint, "counted": True}
    )
    core_jobs.succeed(coordinator["id"])


def _heartbeat(batch_id: str, coordinator_id: str, run_id: Any, done: int, size: int) -> None:
    with tenant_lock():
        own = core_jobs.current(batch_id)
        if own["status"] == core_jobs.RUNNING:
            core_jobs.record_progress(batch_id, done=done, total=size)
        coordinator = core_jobs.current(coordinator_id)
        if coordinator["status"] == core_jobs.RUNNING:
            core_jobs.record_progress(
                coordinator_id, done=_saved_count(run_id, coordinator_id), total=_total(coordinator)
            )


def _stop_the_check(run: Any, coordinator_id: str, broken: BaseException) -> None:
    """A batch failed: the Check stops with a sentence, and a utility-wide
    stop is recorded on the run (B21) exactly as the one-pass Check did. The
    other batches already running finish; nothing new is dispatched until a
    Resume, which re-dispatches only what did not finish."""
    from apps.billing import check_store

    try:
        with tenant_lock():
            if isinstance(broken, runs.UtilityWideStop):
                check_store._record_summary(run, stop=broken.as_dict(), job_id=coordinator_id)
            if core_jobs.current(coordinator_id)["status"] == core_jobs.RUNNING:
                core_jobs.fail(coordinator_id, core_jobs.failure_text(broken))
    except Exception:  # noqa: BLE001 — the batch's own failure is what is raised
        logger.exception("could not stop Check %s after a batch failed", coordinator_id)


def run_batch(record: dict[str, Any]) -> Any:
    """ONE BATCH's body (`run_jobs.run_check_batch_job`), in its own utility's
    context — `core.jobs.run_job` entered it from the record (B3), so
    `app.tenant_id` is the batch's utility whatever the worker ran before."""
    from apps.billing import check_store

    payload = record.get("payload") or {}
    coordinator_id = str(payload["coordinator"])
    batch = payload["batch"]
    run = _run(payload["run_id"])
    batch_id = str(record["id"])
    size = int(batch.get("size") or 0)
    done = [0]

    def on_account(checked: Any) -> None:
        check_store.save_account_check(run, checked, job_id=coordinator_id)
        done[0] += 1
        if done[0] % PROGRESS_EVERY == 0:
            _heartbeat(batch_id, coordinator_id, run.pk, done[0], size)

    try:
        prepared = check_batch(run, batch, on_account=on_account, skip_saved_by=coordinator_id)
    except Exception as broken:
        if core_jobs.is_time_limit(broken):
            core_jobs.release_interrupted_connection(record.get("tenant_id"))
        _stop_the_check(run, coordinator_id, broken)
        raise
    with tenant_lock():
        own = core_jobs.current(batch_id)
        if own["status"] == core_jobs.RUNNING:
            core_jobs.record_progress(
                batch_id,
                done=done[0],
                total=size,
                checkpoint={"checked": done[0], "unavailable": unavailable_of(prepared)},
            )
            core_jobs.succeed(batch_id)
            coordinator = core_jobs.current(coordinator_id)
            if coordinator["status"] == core_jobs.RUNNING:
                checkpoint = dict(coordinator.get("checkpoint") or {})
                finished = list(checkpoint.get("finished") or [])
                if int(payload["index"]) not in finished:
                    finished.append(int(payload["index"]))
                checkpoint["finished"] = finished
                core_jobs.record_progress(
                    coordinator_id,
                    done=_saved_count(run.pk, coordinator_id),
                    total=_total(coordinator),
                    checkpoint=checkpoint,
                )
    pump()
    return core_jobs.HANDED_OFF


def chain_stalled(record: dict[str, Any]) -> bool:
    """Is this HANDED-OFF Check stopped — the screen's question
    (`run_jobs.job_is_abandoned`)? Not while a batch waits for a worker or is
    being worked; yes when none is and the Check is still not counted (a batch
    whose worker died, or a pump that never ran). With no batch dispatched yet
    the coordinator is still planning, and the ordinary question is asked."""
    stall, floor = _stall_thresholds()
    checkpoint = record.get("checkpoint") or {}
    finished = set(checkpoint.get("finished") or [])
    alive = False
    for index, job_id in (checkpoint.get("jobs") or {}).items():
        if int(index) in finished:
            continue
        try:
            batch = core_jobs.current(job_id)
        except core_jobs.JobsError:
            continue
        idle = core_jobs.seconds_idle(job_id)
        if batch["status"] == core_jobs.QUEUED and (idle is None or idle < stall):
            alive = True
        elif batch["status"] == core_jobs.RUNNING and (
            (idle is not None and idle < floor)
            or not core_jobs.is_abandoned(job_id, stalled_after=stall, stopped_floor=floor)
        ):
            alive = True
        if alive:
            return False
    return core_jobs.is_abandoned(str(record["id"]), stalled_after=stall, stopped_floor=floor)


__all__ = [
    "BATCH_SIZE",
    "CHECK_BATCH_JOB",
    "batch_cap",
    "chain_stalled",
    "check_batch",
    "finalize_summary",
    "plan",
    "plan_ranges",
    "pump",
    "run_batch",
    "start",
    "tenant_lock",
]
