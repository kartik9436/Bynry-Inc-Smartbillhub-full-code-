# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-040 (bulk run · Send) · US-BIL-005 (issue)
# Defects:  DEF-BIL-8726 (a 40,000-bill Send ran as ONE task inside an 8,520 s
#           time limit) · DEF-BIL-8710 (a Send whose worker died never resumed,
#           and its progress restarted at 0) · DEF-BIL-8747 (a fault of the
#           deployment broke 22,640 bills one by one and the release completed)
# Pattern:  apps/billing/check_batches.py (B28 — the Check in batches of 500)
# Rules:    CLAUDE.md hard rules 1 (tenant scoping), 4 (an issued bill is never
#           issued again), 6 (idempotency) · BR-BIL-055 (a break never blocks
#           the run) · BR-BIL-058 (the release gate) · hard-won law 14
# Tests:    06-backend/tests/test_def_bil_8726_send_batches.py ·
#           06-backend/tests/test_def_bil_8710_send_resume_pg.py (a real kill) ·
#           06-backend/tests/test_def_bil_8747_send_circuit_breaker.py
# Proof:    10-scripts/j73_scale_proof.py send / send-resume (PostgreSQL 16, 40,000)
# ───────────────────────────────────────────────────────
"""THE SEND IN BATCHES OF 500, UNDER ONE COORDINATOR — B28's shape, for issue.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file carries IDEMPOTENCY KEYS (each
batch's scope key, `billing:issue-batch:<coordinator>:<index>`) and decides when
a release is COMPLETED (`released_at`, the run's status, the release's audit
row), on the path where a draft becomes an immutable bill — CLAUDE.md 🔒 paths.
AI-authored 2026-10-01 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md (*"2026-10-01 · SEND AT SCALE"*).

WHY IT EXISTS, MEASURED
-----------------------
Until this file the worker's Send was ONE task: `release.release_run` over every
draft of the run. Celery gives a task `CELERY_TASK_TIME_LIMIT` = 8,520 s, and at
the measured 1.9 bills a second a 40,008-bill Send would have been stopped by
its own limit after about 16,000 bills (`DEF-BIL-8726`). And a Send whose
worker died stayed `running` for ever: nothing handed it back, a second press
re-attached to the stuck job, and a hand-back by hand restarted its progress at
0 while 1,527 bills were already out (`DEF-BIL-8710`). The Check had both
cures since B28 (2026-10-01); the Send had neither.

WHAT IT DOES
------------
* **The coordinator** (`run_jobs.ISSUE_JOB`) plans the Send as batches of
  `BATCH_SIZE` (500) drafts, in id order, as RANGES of ids — 81 for 40,008
  bills, a few kilobytes of checkpoint. A Send of NAMED bills (*Retry failed*
  sends none; a caller may) carries its ids, ≤ 500 a batch. It writes the plan,
  dispatches up to the per-utility cap and HANDS OFF (`core.jobs.HANDED_OFF`):
  its record stays `running` and holds no worker, exactly as the Check's does.
* **A batch** (`SEND_BATCH_JOB`) issues the drafts STILL DRAFTS in its range
  through `issue.issue_run(..., finish_run=False)` — the same per-bill
  transaction, row lock, GL stamp, posting and delivery as ever — files its
  send breaks, succeeds itself and pumps the next.
* **The last batch to finish** completes the release ONCE, inside the utility's
  lock: the run-wide close (`issue.finish_issue_pass`), then
  `release.complete_release` — the run's status word, `released_at`, the
  release's audit row, the staff summary — the same code an inline release
  runs, after every bill that could issue has issued.
* **A per-utility cap**, its own platform setting
  (`BILLING_SEND_BATCHES_PER_UTILITY`, 0 = half the billing workers, never
  fewer than 1 — the Check's ruled formula). The Send's batches are counted
  apart from the Check's: one run never Checks and Sends at once
  (`check_store.refuse_if_sent`), and sharing one count would let a utility's
  Check of next month starve its Send of this month.

WHY NOTHING CAN BE ISSUED TWICE — THREE LAYERS, NONE NEW
---------------------------------------------------------
1. **The selection.** A batch selects the drafts that are STILL drafts in its
   range, so a batch delivered again after a crash carries on after its last
   issued bill and a finished batch issues nothing (US-BIL-005 TC-6, per batch).
2. **The row lock.** `issue.issue_invoice` locks each draft and re-reads its
   status under the lock, so two passes meeting one bill issue it once — proved
   on PostgreSQL by `test_bbr_f4_two_sends_pg.py` (clerk check F4).
3. **The number is the draft's.** A bill keeps the invoice number its draft was
   given at Calculate; issue verifies it and allocates nothing, so a resumed
   Send cannot use a number twice.

PROGRESS CONTINUES, IT DOES NOT RESTART
---------------------------------------
The coordinator's *n of N* is COUNTED IN THE DATABASE: the bills of the Send's
scope that are no longer drafts, of all the bills in it. A resumed Send whose
first worker issued 1,527 reads *1,527 of 40,008* the moment it is handed back,
because those 1,527 are issued bills — never a counter that a new pass starts
at zero.

A WORKER THAT DIES IS HANDED BACK — `run_jobs.job_is_abandoned`
---------------------------------------------------------------
A handed-off coordinator is executed by no worker by design, so it is asked of
its batches (`check_batches.chain_stalled`, which reads only the checkpoint's
`jobs`/`finished` and is shared as it stands). The Send screen polls
`GET …/issue/progress` and pressing Send again posts `…/issue`; both hand an
abandoned Send back through `run_jobs.resume_job`, as the Check's poll does
(DEF-BIL-8511). The resumed coordinator takes back each batch whose worker is
gone and re-dispatches it under the same scope key.

THE SAME FAULT ON BILL AFTER BILL STOPS THE SEND — `SAME_FAULT_LIMIT` (DEF-BIL-8747)
-----------------------------------------------------------------------------------
On `sbh_send40k` the code ran one migration ahead of its database. Every bill
then failed the same way (`column invoice_lines.pricing_trace does not exist`),
B11 filed each as a send break, 22,640 bills were listed *not sent* in about
five minutes, and the release COMPLETED with them all still drafts. Nothing
went out wrongly — but a fault of the SYSTEM was told to the clerk as 22,640
faults of bills, and the Send claimed to be done.

So a batch passes `issue_run` `stop_after_same_fault=SAME_FAULT_LIMIT` (10).
When ten bills IN A ROW fail with the same unexpected fault — the innermost
cause's class, `issue.fault_signature` — the pass raises `IssuePassStopped`
and the batch STOPS THE SEND (`_stop_the_send`):

* the coordinator is FAILED with a named stop in its checkpoint (`stopped`:
  `STOP_SAME_FAULT`, the catalogue key `STOP_MESSAGE_KEY`, the bill count and
  the fault's class for support), which the Send screen's read
  (`GET …/issue/progress`) returns and the screen shows as *Send stopped*;
* the release is NOT completed — `released_at` stays NULL, so the release row
  is still the pending one that authorises the next Send;
* the ten bills of the streak are still drafts with NO break (each one's
  savepoint rolled it back) and every bill after them was never attempted;
* a genuine break met BEFORE the streak is still filed (`partial`).

Pressing Send again once the fault is fixed starts a new coordinator over the
drafts still drafts; `run_jobs.resume_job` on the stopped one re-dispatches its
unfinished batches. Either way the three layers below make each bill go once.

**WHY TEN, AND WHY "IN A ROW".** A bill that issues resets the count, and so
does a different fault, so it fires only when nothing is getting through. A
named rule refusal (`BillingRuleError`) is a bill's own break and neither
counts nor resets. Ten is ~1.5 s of a batch at the measured 6.5 bills a second:
the cost of the stop is ten bills tried and not filed. In every healthy proof
on this branch the unexpected-fault count was ZERO (40,008 bills at the
re-time), so ten consecutive ones of one class is not a bad patch of accounts
but a fault somebody must fix before the Send can mean anything; a lower
figure (3) would stop a Send over a few genuinely broken bills sorted next to
each other, and a higher one only delays the same stop. A false stop costs a
pause and a Resume; a missed stop cost 22,640 false *not sent* rows. The
breaker counts per batch, so with four batches running at once at most forty
bills are tried before every one of them has stopped. A batch with fewer than
ten drafts left cannot trip it — those bills are filed as breaks as before.
**It is a Send rule only:** `issue_run`'s default never stops, so the inline
release and every other caller keep B11 exactly.

EVERY WRITE TO A COORDINATOR'S RECORD IS INSIDE `check_batches.tenant_lock`,
the utility's advisory lock — the same lock the Check's coordinator and
`resume_job` use, for the reason `check_batches` gives: the job store saves a
whole record, so two batches each adding their own fact would lose one.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from django.db import transaction

from apps.billing import models
from apps.billing.check_batches import chain_stalled, tenant_lock
from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.billing")

#: The Check's ruled batch size (PO 2026-09-30, *"Batch size: my pick is 500"*),
#: carried to the Send so one figure governs both halves of a bulk run. At the
#: rate measured after `DEF-BIL-8708`'s index (6.5 bills a second) a batch is
#: about 77 s of work, two orders of magnitude inside a task's time limit.
BATCH_SIZE = 500

#: DEF-BIL-8747 — bills IN A ROW failing with the same unexpected fault before
#: the Send stops (module docstring, *"WHY TEN"*; the decision log row of
#: 2026-10-01, *"SEND CIRCUIT BREAKER"*).
SAME_FAULT_LIMIT = 10

#: The stop's code, and the catalogue key the Send screen shows for it.
STOP_SAME_FAULT = "same_fault_on_bill_after_bill"
STOP_MESSAGE_KEY = "billing.bulkRun.send.stoppedSameFault"

#: The batch's job kind, on billing's own queue (`run_jobs.register`).
SEND_BATCH_JOB = "billing.run.issue_batch"

#: How often a batch writes its heartbeat and the coordinator's *n of N*, in
#: bills: ~4 s at 6.5 bills a second, ~13 s at 1.9 — inside
#: `BILLING_JOB_STOPPED_FLOOR_SECONDS` (20 s) either way, so a working batch is
#: never judged abandoned between two heartbeats.
PROGRESS_EVERY = 25

#: A Send with no draft left still runs ONE empty batch, so the release is
#: completed by the same path whatever the run holds.
EMPTY_BATCH: dict[str, Any] = {"index": 0, "after": None, "through": None, "ids": [], "size": 0}

#: The coordinator payload fields a batch needs, copied onto it at dispatch.
_CARRIED = (
    "issued_at",
    "released_at",
    "template_id",
    "template_version",
    "dispatch_not_before",
    "actor_user_id",
    "template_pin_explicit",
)


# ── the cap ─────────────────────────────────────────────────────────────────
def batch_cap() -> int:
    """How many Send batch jobs ONE utility may have queued or running at once.

    `BILLING_SEND_BATCHES_PER_UTILITY` above 0 is an explicit cap; otherwise
    the Check's ruled formula, `max(1, BILLING_WORKERS // 2)` — 8 workers → 4,
    2 → 1. Both are declared in `config/settings/base.py` (DEF-2806)."""
    from django.conf import settings

    explicit = int(getattr(settings, "BILLING_SEND_BATCHES_PER_UTILITY", 0) or 0)
    if explicit > 0:
        return explicit
    workers = int(getattr(settings, "BILLING_WORKERS", 2) or 0)
    return max(1, workers // 2)


# ── the plan ────────────────────────────────────────────────────────────────
def plan_ranges(ids: list[str], size: int | None = None) -> list[dict[str, Any]]:
    """Cut an id-ordered list of drafts into batches of `size` (500).

    Each batch is a RANGE of ids — after `after`, up to and including
    `through` — not a list, so 81 batches fit in a few kilobytes. The first
    opens at the start and the last runs to the end, so no draft can fall
    between two. The comparison is the DATABASE's (`pk__gt`/`pk__lte` on the
    ordering the list came from), never Python's."""
    size = size or BATCH_SIZE
    total = len(ids)
    count = (total + size - 1) // size
    return [
        {
            "index": i,
            "after": ids[i * size - 1] if i else None,
            "through": ids[(i + 1) * size - 1] if i < count - 1 else None,
            "ids": None,
            "size": min(size, total - i * size),
        }
        for i in range(count)
    ]


def _bills(run: Any) -> Any:
    return models.Invoice.objects.filter(tenant_id=core_tenancy.current_tenant_id(), bill_run=run)


def _scope(run: Any, invoice_ids: Any) -> Any:
    bills = _bills(run)
    return bills if invoice_ids is None else bills.filter(pk__in=[str(one) for one in invoice_ids])


def plan(run: Any, invoice_ids: Any = None) -> dict[str, Any]:
    """`{"batches", "total", "sent_at_plan"}` for a Send of the whole run's
    remaining drafts (ranges) or of NAMED bills (each batch carries ≤ 500 ids).

    `total` is every bill in the Send's scope and `sent_at_plan` those already
    not drafts, so the coordinator's *n of N* starts where the bills are."""
    scope = _scope(run, invoice_ids)
    total = scope.count()
    sent = scope.exclude(status=models.INVOICE_DRAFT).count()
    if invoice_ids is None:
        drafts = [
            str(one)
            for one in scope.filter(status=models.INVOICE_DRAFT)
            .order_by("id")
            .values_list("id", flat=True)
        ]
        return {"batches": plan_ranges(drafts), "total": total, "sent_at_plan": sent}
    # NAMED bills: every id asked for travels, so `issue_run` answers for each
    # one exactly as it always has (already issued, or not in this run).
    wanted = sorted({str(one) for one in invoice_ids if one})
    size = BATCH_SIZE
    batches = [
        {
            "index": i,
            "after": None,
            "through": None,
            "ids": wanted[i * size : (i + 1) * size],
            "size": len(wanted[i * size : (i + 1) * size]),
        }
        for i in range((len(wanted) + size - 1) // size)
    ]
    return {"batches": batches, "total": total, "sent_at_plan": sent}


def batch_invoice_ids(run: Any, batch: dict[str, Any]) -> list[str]:
    """The bills ONE batch issues: its named ids, or the drafts STILL drafts in
    its range — which is what makes a re-delivered batch carry on after its
    last issued bill (layer 1 of the module docstring)."""
    if batch.get("ids") is not None:
        return [str(one) for one in batch["ids"]]
    drafts = _bills(run).filter(status=models.INVOICE_DRAFT)
    if batch.get("after") is not None:
        drafts = drafts.filter(pk__gt=batch["after"])
    if batch.get("through") is not None:
        drafts = drafts.filter(pk__lte=batch["through"])
    return [str(one) for one in drafts.order_by("id").values_list("id", flat=True)]


# ── reading a coordinator ───────────────────────────────────────────────────
def _instant(payload: dict[str, Any], name: str) -> datetime | None:
    value = payload.get(name)
    if value is None:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _run(run_id: Any) -> Any:
    from apps.billing import selectors

    return selectors.run_or_404(run_id)


def _actor(payload: dict[str, Any]) -> Any:
    from apps.billing.run_jobs import _JobActor

    user_id = payload.get("actor_user_id")
    return None if user_id is None else _JobActor(user_id)


def _sent_count(run: Any, payload: dict[str, Any]) -> int:
    """Bills of the Send's scope no longer drafts — the coordinator's `done`."""
    return _scope(run, payload.get("invoice_ids")).exclude(status=models.INVOICE_DRAFT).count()


def _total(record: dict[str, Any]) -> Any:
    return (record.get("progress") or {}).get("total")


def send_job_for(run: Any, job_id: Any = None) -> dict[str, Any] | None:
    """The run's Send job: the one named (refused unless it IS this run's Send)
    or, with none named, the run's active one. None when there is none."""
    from apps.billing import run_jobs

    if job_id is not None:
        try:
            record = core_jobs.current(str(job_id))
        except core_jobs.JobsError:
            return None
        payload = record.get("payload") or {}
        if record.get("kind") != run_jobs.ISSUE_JOB or str(payload.get("run_id")) != str(run.pk):
            return None
        return record
    for record in core_jobs.active_records(run_jobs.ISSUE_JOB):
        if str((record.get("payload") or {}).get("run_id")) == str(run.pk):
            return record
    return None


# ══════════════════════════════════════════════════════════════════════════
# THE WORKER PATH — coordinator, batches, pump
# ══════════════════════════════════════════════════════════════════════════
def start(record: dict[str, Any], release_row: Any) -> Any:
    """The COORDINATOR's body (`run_jobs.run_issue_job`, which has already
    found the authorised, unreleased `release_row`). Plans on its first
    delivery; on a resumed one takes back the batches whose worker is gone."""
    coordinator_id = str(record["id"])
    payload = record.get("payload") or {}
    run = _run(payload["run_id"])
    checkpoint = record.get("checkpoint") or {}
    if not checkpoint.get("batches"):
        planned = plan(run, payload.get("invoice_ids"))
        checkpoint = {
            "batches": planned["batches"] or [dict(EMPTY_BATCH)],
            "total": planned["total"],
            "sent_at_plan": planned["sent_at_plan"],
            "release_id": str(release_row.pk),
            "jobs": {},
            "finished": [],
        }
        with tenant_lock():
            core_jobs.record_progress(
                coordinator_id,
                done=planned["sent_at_plan"],
                total=planned["total"],
                checkpoint=checkpoint,
            )
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
    """A RESUMED coordinator: a batch that finished is marked finished; one that
    failed, or whose worker is gone, is forgotten so `pump` dispatches it again
    (a NEW record under the same scope key) and it issues only what is still a
    draft. A batch still queued, or still being worked, is left alone. The
    progress is re-counted from the bills, so it reads where the Send is."""
    stall, floor = _stall_thresholds()
    with tenant_lock():
        record = core_jobs.current(coordinator_id)
        if record["status"] != core_jobs.RUNNING:
            return
        checkpoint = dict(record.get("checkpoint") or {})
        # DEF-BIL-8747 — a resumed Send is no longer stopped.
        checkpoint.pop("stopped", None)
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
                core_jobs.reclaim(job_id, reason="its Send was resumed and no worker is on it")
                del jobs[index]
        checkpoint["jobs"], checkpoint["finished"] = jobs, finished
        core_jobs.record_progress(
            coordinator_id,
            done=_sent_count(run, record.get("payload") or {}),
            total=checkpoint.get("total"),
            checkpoint=checkpoint,
        )


_local = threading.local()


def pump() -> None:
    """Fill the CURRENT utility's free Send batch slots, and complete every Send
    whose batches are all done. Dispatch happens after the lock's commit, and
    under `JOBS_EAGER` the loop runs each batch in-process, in order — see
    `check_batches.pump`, whose loop this is."""
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
                except Exception:  # noqa: BLE001 — the record stays queued; the poll hands it back
                    logger.exception("could not hand Send batch %s to a worker", record["id"])
            if not ready and not getattr(_local, "again", False):
                break
    finally:
        _local.pumping = False


def _dispatchable() -> list[dict[str, Any]]:
    """Inside `tenant_lock`: create the next batch records up to the cap, in
    the order the Sends were started, and complete the finished ones."""
    from apps.billing import run_jobs

    slots = batch_cap() - len(core_jobs.active_records(SEND_BATCH_JOB))
    ready: list[dict[str, Any]] = []
    for coordinator in core_jobs.active_records(run_jobs.ISSUE_JOB):
        if coordinator["status"] != core_jobs.RUNNING:
            continue
        checkpoint = dict(coordinator.get("checkpoint") or {})
        batches = checkpoint.get("batches")
        if not batches:
            continue  # not planned yet
        jobs = dict(checkpoint.get("jobs") or {})
        finished = set(checkpoint.get("finished") or [])
        pending = [b for b in batches if str(b["index"]) not in jobs]
        if not pending:
            if finished >= {b["index"] for b in batches}:
                _complete_guarded(coordinator, checkpoint)
            continue
        payload = coordinator.get("payload") or {}
        added = False
        for batch in pending:
            if slots <= 0:
                break
            record = core_jobs.enqueue(
                SEND_BATCH_JOB,
                payload={
                    "run_id": payload["run_id"],
                    "coordinator": coordinator["id"],
                    "index": batch["index"],
                    "batch": batch,
                    **{name: payload.get(name) for name in _CARRIED},
                },
                scope_key=f"billing:issue-batch:{coordinator['id']}:{batch['index']}",
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


def _complete_guarded(coordinator: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    """`_complete` in its own SAVEPOINT (hard-won law 14): a failure while
    completing the release must not poison the lock's transaction, which may
    already hold another Send's new batch records. It fails the Send with a
    sentence; a Resume then completes it again — every step is idempotent and
    `released_at` is checked under a row lock first."""
    try:
        with transaction.atomic():
            _complete(coordinator, checkpoint)
    except Exception as broken:  # noqa: BLE001 — the Send fails with a sentence
        core_jobs.reraise_if_time_limit(broken)
        logger.exception("Send %s could not complete its release", coordinator["id"])
        core_jobs.fail(coordinator["id"], core_jobs.failure_text(broken))


def close_breaks_of_sent_bills(run: Any) -> int:
    """DEF-BIL-8746 — close every OPEN send break whose account's bill on this
    run is no longer a draft. Answers how many it closed.

    A batch closes the breaks of the bills IT issued (`release.record_send_breaks`),
    after its issue pass. A batch KILLED between the two has issued bills that
    no later pass lists as its own — the re-dispatched batch re-selects only
    the drafts — so their breaks stayed open: 985 at 40,000, each a bill that
    went out and that Sent called *not sent*. This asks the bills instead of a
    pass's answer, once, at completion. Idempotent (`runs.clear_break` moves an
    open row only)."""
    from apps.billing import runs as billing_runs

    tenant_id = core_tenancy.current_tenant_id()
    open_accounts = set(
        str(one)
        for one in models.BillRunBreak.objects.filter(
            tenant_id=tenant_id,
            bill_run=run,
            stage=models.BREAK_STAGE_SEND,
            resolution__isnull=True,
        ).values_list("account_id", flat=True)
    )
    if not open_accounts:
        return 0
    bills = _bills(run).filter(account_id__in=sorted(open_accounts))
    still_draft = set(
        str(one)
        for one in bills.filter(status=models.INVOICE_DRAFT).values_list("account_id", flat=True)
    )
    went = set(
        str(one)
        for one in bills.exclude(status=models.INVOICE_DRAFT).values_list("account_id", flat=True)
    )
    closed = 0
    for account_id in sorted(went - still_draft):
        closed += billing_runs.clear_break(
            run, account_id, resolution=models.BREAK_RESOLUTION_ISSUED
        )
    return closed


def _complete(coordinator: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    """The release, completed ONCE after the last batch — the end of
    `release.release_run`, run on the bills rather than on one pass's answer."""
    from apps.billing import issue, release

    payload = coordinator.get("payload") or {}
    run = _run(payload["run_id"])
    total = int(checkpoint.get("total") or 0)
    release_row = (
        models.BillRunRelease.objects.select_for_update()
        .filter(tenant_id=core_tenancy.current_tenant_id(), pk=checkpoint.get("release_id"))
        .first()
    )
    if release_row is not None and release_row.released_at is None:
        actor = _actor(payload)
        issued_at = _instant(payload, "issued_at")
        issue.finish_issue_pass(bill_run=run, issued_at=issued_at, actor=actor)
        close_breaks_of_sent_bills(run)
        scope = _scope(run, payload.get("invoice_ids"))
        sent_now = scope.exclude(status=models.INVOICE_DRAFT).count()
        sent_at_plan = int(checkpoint.get("sent_at_plan") or 0)
        named = payload.get("invoice_ids") is not None
        release.complete_release(
            bill_run=run,
            release_row=release_row,
            released_at=_instant(payload, "released_at") or issued_at,
            actor=actor,
            issued_count=max(0, sent_now - sent_at_plan),
            # A Send of NAMED bills reports the ones already bills, as
            # `issue_run` does; a whole-run Send selects only drafts.
            already_issued_count=sent_at_plan if named else 0,
            broken_count=scope.filter(status=models.INVOICE_DRAFT).count(),
        )
    else:
        logger.info(
            "Send %s: its release is already completed — nothing completed twice",
            coordinator["id"],
        )
    core_jobs.record_progress(
        coordinator["id"],
        done=total,
        total=total,
        checkpoint={**checkpoint, "completed": True},
    )
    core_jobs.succeed(coordinator["id"])


def _heartbeat(batch_id: str, coordinator_id: str, run: Any, done: int, size: int) -> None:
    with tenant_lock():
        own = core_jobs.current(batch_id)
        if own["status"] == core_jobs.RUNNING:
            core_jobs.record_progress(batch_id, done=done, total=size)
        coordinator = core_jobs.current(coordinator_id)
        if coordinator["status"] == core_jobs.RUNNING:
            core_jobs.record_progress(
                coordinator_id,
                done=_sent_count(run, coordinator.get("payload") or {}),
                total=_total(coordinator),
            )


def _stop_the_send(
    coordinator_id: str, broken: BaseException, stopped: dict[str, Any] | None = None
) -> None:
    """A batch failed (not a bill — a bill that breaks is a break and the batch
    goes on, BR-BIL-055): the Send stops with a sentence. Batches already
    running finish; nothing new is dispatched until it is handed back, which
    re-dispatches only what did not finish.

    `stopped` (DEF-BIL-8747) is the named stop the Send screen reads, written
    into the coordinator's checkpoint before it is failed — `fail` keeps the
    checkpoint, which is also what a resume reads."""
    try:
        with tenant_lock():
            coordinator = core_jobs.current(coordinator_id)
            if coordinator["status"] == core_jobs.RUNNING:
                if stopped is not None:
                    core_jobs.record_progress(
                        coordinator_id,
                        done=(coordinator.get("progress") or {}).get("done") or 0,
                        total=_total(coordinator),
                        checkpoint={**(coordinator.get("checkpoint") or {}), "stopped": stopped},
                    )
                core_jobs.fail(coordinator_id, core_jobs.failure_text(broken))
    except Exception:  # noqa: BLE001 — the batch's own failure is what is raised
        logger.exception("could not stop Send %s after a batch failed", coordinator_id)


def _file_before_the_stop(run: Any, stop: Any) -> None:
    """DEF-BIL-8747 — file the genuine breaks a stopped pass met BEFORE its
    streak (and close those of the bills it issued), in a SAVEPOINT (law 14):
    the stop may be a database that is going away, and failing to file must
    neither poison the transaction the stop is written in nor hide the stop."""
    from apps.billing import release

    try:
        with transaction.atomic():
            release.record_send_breaks(run, stop.partial)
    except Exception:  # noqa: BLE001 — the stop is what is reported
        logger.exception("Send stopped: could not file the breaks met before the stop")


def run_batch(record: dict[str, Any]) -> Any:
    """ONE BATCH's body (`run_jobs.run_issue_batch_job`), in its own utility's
    context — `core.jobs.run_job` entered it from the record (B3)."""
    from apps.billing import issue, release

    payload = record.get("payload") or {}
    coordinator_id = str(payload["coordinator"])
    batch_id = str(record["id"])
    run = _run(payload["run_id"])
    if core_jobs.current(coordinator_id)["status"] == core_jobs.SUCCEEDED:
        # A late re-delivery of a batch whose Send is complete: its release is
        # stamped, so the gate would refuse — and there is nothing left to do.
        return None
    batch = payload["batch"]
    size = int(batch.get("size") or 0)

    def on_progress(done: int, _total_in_batch: int, _invoice_no: str) -> None:
        if done % PROGRESS_EVERY == 0:
            _heartbeat(batch_id, coordinator_id, run, done, size)

    try:
        ids = batch_invoice_ids(run, batch)
        outcome = issue.issue_run(
            run,
            issued_at=_instant(payload, "issued_at"),
            template_id=payload["template_id"],
            template_version=int(payload["template_version"]),
            invoice_ids=tuple(ids),
            actor=_actor(payload),
            dispatch_not_before=_instant(payload, "dispatch_not_before"),
            on_progress=on_progress,
            template_pin_explicit=bool(payload.get("template_pin_explicit", False)),
            finish_run=False,
            # DEF-BIL-8747 — the same fault on ten bills in a row stops the Send.
            stop_after_same_fault=SAME_FAULT_LIMIT,
        )
        # DEF-BIL-8421 — this batch's bills that could not go are FILED now,
        # so a crash in a later batch loses none of them.
        release.record_send_breaks(run, outcome)
    except issue.IssuePassStopped as stop:
        _file_before_the_stop(run, stop)
        _stop_the_send(
            coordinator_id,
            stop,
            stopped={
                "code": STOP_SAME_FAULT,
                "message_key": STOP_MESSAGE_KEY,
                "params": {"count": stop.bills},
                "bills": stop.bills,
                "fault": stop.fault,
                "batch": int(payload["index"]),
            },
        )
        raise
    except Exception as broken:
        if core_jobs.is_time_limit(broken):
            core_jobs.release_interrupted_connection(record.get("tenant_id"))
        _stop_the_send(coordinator_id, broken)
        raise
    with tenant_lock():
        own = core_jobs.current(batch_id)
        if own["status"] == core_jobs.RUNNING:
            core_jobs.record_progress(
                batch_id,
                done=len(ids),
                total=size,
                checkpoint={
                    "issued": outcome.issued_count,
                    "already_issued": len(outcome.already_issued),
                    "broken": len(outcome.broken),
                },
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
                    done=_sent_count(run, coordinator.get("payload") or {}),
                    total=_total(coordinator),
                    checkpoint=checkpoint,
                )
    pump()
    return core_jobs.HANDED_OFF


__all__ = [
    "BATCH_SIZE",
    "SAME_FAULT_LIMIT",
    "SEND_BATCH_JOB",
    "STOP_MESSAGE_KEY",
    "STOP_SAME_FAULT",
    "batch_cap",
    "batch_invoice_ids",
    "close_breaks_of_sent_bills",
    "chain_stalled",
    "plan",
    "plan_ranges",
    "pump",
    "run_batch",
    "send_job_for",
    "start",
]
