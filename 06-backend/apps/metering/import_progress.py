# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 runner)   Change: CR-026 second half (PO
#           2026-08-22 — *"the sizes of CSV file scan be 50,000 or 100,000
#           units or premises at a time; how you will hnadle such volume in
#           upload"*)   Screens: WFL-01.premises.2-4 (the stage rail), PRM-04
# Rules:    BR-MET-090 (the RUN's record is what it did; this is a gauge and is
#           never read by a receipt) · BR-MET-096 (one runner, every target
#           inherits this) · CLAUDE.md rule 1 (tenant scoping — the second
#           connection sets `app.tenant_id` before it touches a tenant table)
# Tests:    06-backend/tests/test_cr026_background_stages.py
# Impacts:  apps/metering/import_runs.py (the only caller) ·
#           apps/metering/models.ImportRunProgress (the only table) ·
#           metering 0017 (creates it, with its RLS policy)
# ───────────────────────────────────────────────────────
"""HOW A RUNNING IMPORT STAGE SAYS HOW FAR IT HAS GOT — CR-026.

r10's stage rail draws *"Validating… 62,000 of 100,000"*. Making that sentence
true **while the stage runs** is harder than it looks, and this module exists
for exactly one reason:

⚠ **A PROGRESS WRITE ON THE STAGE'S OWN CONNECTION IS INVISIBLE UNTIL THE STAGE
FINISHES.** Every stage runs inside one `transaction.atomic()` — the load
because it must be all-or-nothing (CR-026's recorded judgment, decision log
2026-08-22), transform and validate because `DEF-529` correctly put their
`SELECT … FOR UPDATE` inside a transaction. Anything they write is unreadable
by a poller until commit, so a progress figure written that way can only ever
be 0% and then 100%: the two numbers nobody needs.

⚠ **AND THE RUN ROW ITSELF CANNOT CARRY IT**, for the mirror-image reason: that
row is the one the stage holds `FOR UPDATE`, so an UPDATE aimed at it from any
other connection **waits for the stage to commit**. Hence a separate row, in a
separate table (`import_run_progress`), written on a **separate autocommit
connection**. That is the whole design and each half is load-bearing.

WHAT THIS COSTS AND WHY IT IS ACCEPTABLE
----------------------------------------
* **One extra database connection per worker process**, opened lazily on the
  first progress write of a deferred run and reused after that. A synchronous
  run never opens it — progress is emitted only for runs that went to a worker
  (the same 5,000-row bar the deferral uses), so a 3-row import pays nothing.
* **The write can be lost.** Every failure here is caught and logged, never
  raised: a stage that walked 100,000 rows must not die because a progress bar
  could not be updated. Losing every row in this table costs a screen its
  gauge; nothing audited, financial or idempotent reads it (BR-MET-090 — what
  a run DID is `import_runs.counts` and the receipt).
* **It is throttled** — at most one write per 1,000 rows AND per second,
  whichever is slower. At 100,000 rows that is ~100 UPDATEs against 100 seconds
  of work, which is noise beside the work itself and is what keeps the gauge
  from becoming the bottleneck it measures.

⚠ **`IMPORT_PROGRESS_ISOLATED=False` TURNS THE SECOND CONNECTION OFF.** ⚠ This
sentence went on *"and the test settings do exactly that"* until 2026-09-30,
and NO settings file sets it (`DEF-MET-8400`): under the suite the gauge is
written on the second connection, which cannot see the test's own uncommitted
rows, and the write is dropped without a word (it never raises, by design). A
test that asserts a gauge sets the flag itself (`settings.IMPORT_PROGRESS_
ISOLATED = False`, as `tests/test_def_met_8106_read_post_job.py` does). With
the flag off, the rows are written through the ordinary
ORM on the caller's own connection — same table, same shape, visible to a test
that asserts them and rolled back with the test's transaction. It is NOT a
production posture: with it off, a poller sees the gauge only after the stage
commits, which is the uselessness described above. Stated as a setting rather
than a `if running_tests` because a deployment without it (a single-connection
demo box, a pooler that refuses a second session) is a legitimate configuration
and must degrade to something honest rather than to an exception.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from django.conf import settings
from django.db import connections
from django.utils import timezone

from apps.metering import models
from core.dbfields import uuid7

logger = logging.getLogger("smartbillhub.metering.import")

#: Write at most one gauge update per this many rows …
ROWS_PER_WRITE = 1_000
#: … and never more than one per this many seconds, whichever is slower. Both
#: bars, because a 1,000-row chunk of a cheap stage can pass in milliseconds.
SECONDS_PER_WRITE = 1.0

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"

#: The upsert. `ON CONFLICT (run_id)` names `uq_import_run_progress_run` — one
#: row per run, overwritten in place, because this is a gauge and not a history.
_UPSERT_SQL = """
INSERT INTO import_run_progress
    (id, tenant_id, run_id, stage, done, total, state, message, job_id,
     created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (run_id) DO UPDATE SET
    stage      = EXCLUDED.stage,
    done       = EXCLUDED.done,
    total      = EXCLUDED.total,
    state      = EXCLUDED.state,
    message    = EXCLUDED.message,
    job_id     = EXCLUDED.job_id,
    updated_at = CURRENT_TIMESTAMP
"""

#: Set `app.tenant_id` on the writer's own session — CLAUDE.md rule 1. The
#: parameterized `set_config` form, never a formatted `SET` (core/tenancy.py
#: states why: a GUC value interpolated into SQL is an injection surface).
_SET_TENANT_SQL = "SELECT set_config('app.tenant_id', %s, false)"

_local = threading.local()


def isolated_enabled() -> bool:
    """Whether the gauge gets its own connection. See the module docstring."""
    return bool(getattr(settings, "IMPORT_PROGRESS_ISOLATED", True))


def _isolated_connection() -> Any:
    """The writer's own connection to the same database, created once per
    thread and kept. `create_connection` builds a NEW wrapper from the same
    `DATABASES['default']` settings, so it has its own session, its own
    autocommit, and — critically — its own view of what is committed."""
    existing = getattr(_local, "connection", None)
    if existing is not None:
        return existing
    fresh = connections.create_connection("default")
    _local.connection = fresh
    return fresh


def _close_isolated() -> None:
    existing = getattr(_local, "connection", None)
    _local.connection = None
    if existing is not None:
        try:
            existing.close()
        except Exception:  # noqa: BLE001 — closing a broken connection is fine
            logger.debug("import progress: could not close the gauge connection", exc_info=True)


def _write_isolated(row: dict[str, Any]) -> None:
    """The production path: upsert on a second, autocommit session."""
    conn = _isolated_connection()
    with conn.cursor() as cursor:
        cursor.execute(_SET_TENANT_SQL, [str(row["tenant_id"])])
        cursor.execute(
            _UPSERT_SQL,
            [
                str(uuid7()),  # DB-2: the same canonical uuidv7 the column stores
                str(row["tenant_id"]),
                str(row["run_id"]),
                row["stage"],
                row["done"],
                row["total"],
                row["state"],
                row["message"],
                str(row["job_id"]) if row["job_id"] else None,
            ],
        )


def _write_orm(row: dict[str, Any]) -> None:
    """The `IMPORT_PROGRESS_ISOLATED=False` path: the same row, through the
    ORM, on the caller's own connection — so a test can assert it and a
    single-connection deployment still records where a stage got to."""
    models.ImportRunProgress.objects.update_or_create(
        run_id=row["run_id"],
        defaults={
            "tenant_id": row["tenant_id"],
            "stage": row["stage"],
            "done": row["done"],
            "total": row["total"],
            "state": row["state"],
            "message": row["message"],
            "job_id": row["job_id"],
        },
    )


def write(
    *,
    tenant_id: Any,
    run_id: Any,
    stage: str,
    done: int,
    total: int | None,
    state: str,
    message: str | None = None,
    job_id: Any = None,
) -> None:
    """Record the gauge. **Never raises** — see the module docstring."""
    row = {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "stage": stage,
        "done": int(done),
        "total": None if total is None else int(total),
        "state": state,
        "message": message,
        "job_id": job_id,
    }
    try:
        if isolated_enabled():
            _write_isolated(row)
        else:
            _write_orm(row)
    except Exception:  # noqa: BLE001 — a gauge never fails the work it measures
        logger.warning(
            "import progress: could not record %s %s/%s for run %s",
            stage,
            done,
            total,
            run_id,
            exc_info=True,
        )
        if isolated_enabled():
            # A broken second connection stays broken until it is replaced;
            # dropping it means the NEXT chunk gets a fresh session rather than
            # every remaining chunk logging the same dead socket.
            _close_isolated()


#: DEF-MET-8106 — a JOB's own progress, written on the same second connection.
#: `jobs.progress` is the `{done, total}` that `GET /jobs/{id}` serves; this is
#: `core.jobs.record_progress`'s write, minus the load-check-save round trip,
#: aimed at a row nobody else is holding a lock on.
_JOB_PROGRESS_SQL = """
UPDATE jobs SET progress = %s::jsonb, updated_at = CURRENT_TIMESTAMP
WHERE id = %s AND tenant_id = %s AND status = 'running'
"""


def write_job_progress(*, tenant_id: Any, job_id: Any, done: int, total: int | None) -> None:
    """Move a running job's `{done, total}` WHILE its work is still inside one
    open transaction — the read-batch post (`DEF-MET-8106`) is exactly that: one
    transaction by design (a killed worker leaves nothing), so a progress write
    on its own connection would be invisible until the bar was already full.

    Same two paths as `write`: the isolated autocommit connection in production,
    and `core.jobs.record_progress` on the caller's connection when isolation is
    off (the test settings), where a test can read it back. **Never raises.**
    """
    import json

    from core import jobs as core_jobs

    try:
        if isolated_enabled():
            conn = _isolated_connection()
            with conn.cursor() as cursor:
                cursor.execute(_SET_TENANT_SQL, [str(tenant_id)])
                cursor.execute(
                    _JOB_PROGRESS_SQL,
                    [
                        json.dumps({"done": int(done), "total": total}),
                        str(job_id),
                        str(tenant_id),
                    ],
                )
        else:
            # ⚠ A SAVEPOINT, because this path runs on the POST's connection,
            # inside its transaction: a failed statement here without one would
            # abort the whole post on PostgreSQL (CLAUDE.md law 14).
            from django.db import transaction

            with transaction.atomic():
                core_jobs.record_progress(str(job_id), int(done), total)
    except Exception:  # noqa: BLE001 — a gauge never fails the work it measures
        logger.warning(
            "job progress: could not record %s/%s for job %s", done, total, job_id, exc_info=True
        )
        if isolated_enabled():
            _close_isolated()


class Reporter:
    """The handle a stage holds while it walks its rows.

    `total` is the denominator the screen prints; `step(done)` moves the
    numerator and throttles itself (see `ROWS_PER_WRITE` / `SECONDS_PER_WRITE`),
    so a caller may call it as often as it likes — once per row if that reads
    best — without thinking about write volume.
    """

    def __init__(
        self,
        *,
        tenant_id: Any,
        run_id: Any,
        stage: str,
        total: int | None,
        job_id: Any = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.run_id = run_id
        self.stage = stage
        self.total = total
        self.job_id = job_id
        self._last_done = -1
        self._last_at = 0.0

    # ── the enabled/disabled seam ──────────────────────────────────────────
    @property
    def enabled(self) -> bool:
        return True

    def _emit(self, done: int, state: str, message: str | None) -> None:
        write(
            tenant_id=self.tenant_id,
            run_id=self.run_id,
            stage=self.stage,
            done=done,
            total=self.total,
            state=state,
            message=message,
            job_id=self.job_id,
        )
        self._last_done = done
        self._last_at = time.monotonic()

    def start(self, message: str | None = None) -> None:
        self._emit(0, RUNNING, message)

    def mark(self, done: int, message: str | None = None) -> None:
        """A milestone that is written whatever the throttle says — used where
        the SENTENCE changes (*"Saving the mapped rows"*) rather than the
        number, because a throttled-away message is a screen that lies about
        which half of a stage it is in."""
        self._emit(done, RUNNING, message)

    def step(self, done: int, message: str | None = None) -> None:
        now = time.monotonic()
        if done - self._last_done < ROWS_PER_WRITE and now - self._last_at < SECONDS_PER_WRITE:
            return
        self._emit(done, RUNNING, message)

    def finished(self, done: int | None = None, message: str | None = None) -> None:
        self._emit(self.total if done is None else done, DONE, message)

    def failed(self, message: str) -> None:
        self._emit(max(self._last_done, 0), FAILED, message)


class NullReporter(Reporter):
    """What a SYNCHRONOUS run gets: a reporter that writes nothing.

    A run below the deferral bar answers inside the request — there is no
    moment at which anyone could poll it, so the gauge would be a table write
    nobody ever reads. Same object shape so the stage bodies carry no `if`.
    """

    def __init__(self) -> None:  # noqa: D107 — see the class docstring
        super().__init__(tenant_id=None, run_id=None, stage="", total=None)

    @property
    def enabled(self) -> bool:
        return False

    def _emit(self, done: int, state: str, message: str | None) -> None:
        return None


NULL = NullReporter()


def queued(run: Any, stage: str, total: int | None, job_id: Any) -> None:
    """Written by the ENDPOINT the moment a stage is handed to a worker, so the
    first poll after the 202 has something true to say instead of an empty
    gauge that reads as "nothing is happening"."""
    write(
        tenant_id=run.tenant_id,
        run_id=run.id,
        stage=stage,
        done=0,
        total=total,
        state=QUEUED,
        message=None,
        job_id=job_id,
    )


#: How long a stage may sit `queued` before the screen says so out loud, in
#: seconds. A worker that is running claims a message in well under a second, so
#: thirty is not a threshold anyone healthy crosses — it is the point past which
#: *"queued"* has stopped being a status and started being a symptom.
#:
#: ⛔ **`DEF-2487` — WHY A NUMBER AT ALL.** `_refuse_no_worker` asks before
#: accepting, but a worker can die in the second AFTER it answered the ping, and
#: `tasks.send` swallows a broker failure by design so the record simply rests
#: `queued`. Without this the operator watches a progress bar that will never
#: move and has nothing to read. The number is small enough to be useful and
#: large enough that a slow start is not reported as a fault.
STALLED_AFTER_SECONDS = 30


def read(run: Any) -> dict[str, Any] | None:
    """The gauge as an API payload — `None` when this run has never had one
    (every synchronous run, and every run before its first deferred stage)."""
    row = models.ImportRunProgress.objects.filter(tenant_id=run.tenant_id, run_id=run.id).first()
    if row is None:
        return None
    total = row.total
    # ⚠ **COMPUTED HERE RATHER THAN ON THE SCREEN**, for `pct`'s own reason one
    # line down: two clients would otherwise each pick their own idea of how
    # long is too long, and the screen has no way to know what the server thinks
    # a worker's dispatch latency looks like.
    stalled = row.state == QUEUED and (
        (timezone.now() - row.updated_at).total_seconds() > STALLED_AFTER_SECONDS
    )
    return {
        # DEF-2487 — "queued, and nothing has picked it up". `state` alone
        # cannot say this: a job queued half a second ago and a job queued on a
        # deployment with no worker running are the same word.
        "stalled": bool(stalled),
        "stalled_after_seconds": STALLED_AFTER_SECONDS,
        "stage": row.stage,
        "done": row.done,
        "total": total,
        "state": row.state,
        "message": row.message,
        "job_id": str(row.job_id) if row.job_id else None,
        # Served rather than left to the screen: two clients would otherwise
        # each divide by zero their own way on a 0-row file.
        "pct": (int(row.done * 100 / total) if total else None),
        "updated_at": row.updated_at,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-004@8bf4be8 — extended by CR-026 second half (PO 2026-08-22)
# generated: 2026-08-22 by the CR-026 background-stages lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — the polling screen belongs to the frontend lane; this lane serves `progress` on every import payload so it has something to poll) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the test module's trailer
# exceptions: `connections.create_connection` is a Django internal (django/utils/connection.py) rather than a published API — used because a second alias in `DATABASES` would need a router, a test-database entry and a migration target for a table that is a progress bar. If it ever moves, the fallback is already built and one setting away (`IMPORT_PROGRESS_ISOLATED=False`) · the writer swallows every exception BY DESIGN (a gauge never fails the work it measures) and logs at WARNING so a broken gauge is findable
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
