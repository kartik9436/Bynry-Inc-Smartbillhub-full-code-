# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-012 (EP-RBS-04) — CR-075 wave L task L5: *"Stop, reachable
#           at every moment"*.
# Rules:    BR-RBS-007 (every record executes in its own savepoint; one failure
#           never aborts the run) · US-RBS-012's acceptance sentence
#           (*"stopping halts before the next record; records already acted
#           stay acted and are listed"*) · CLAUDE.md hard rule 4 (what was
#           done stays done — a stop never un-writes anything)
# Tests:    06-backend/tests/test_us_rbs_012_stop.py (TC-RBS-9, shown RED on a
#           stop that only sets a flag)
# Impacts:  apps/runbooks/engine/executor.py (the per-record loop asks this)
# ───────────────────────────────────────────────────────
"""Is somebody trying to stop this run? Asked FRESH, before every record.

WHY THIS IS ITS OWN FILE AND WHY IT RE-READS THE ROW EVERY TIME
----------------------------------------------------------------
`US-RBS-012`: *"Stopping halts before the next record; records already acted
stay acted and are listed."* Two halves, and the second is free — nothing here
un-writes anything, because hard rule 4 means a queued notice stays queued and
a fee stays applied. **The first half is the whole difficulty**, and it has one
failure mode with a name: `EP-RBS-04` calls it *a stop that only sets a flag*.

A stop that sets a flag the loop never reads is a button that reports success
and changes nothing — the clerk watches 812 letters continue after pressing it.
So the question is asked **from the database, on every record**, and never from
a value captured when the run started: the person pressing Stop is in a
different process, and a cached status cannot see them.

That costs one indexed primary-key read per record. On the ladder's own worst
case — 1,004 accounts — that is 1,004 reads, which is the price of the button
working. **A version that read it once per hundred records would halve the cost
and make the promise *"halts before the next record"* false**, so it is not
done: the sentence on the screen is the specification.

⚠ WHAT WOULD MAKE THIS CHECK PASS WRONGLY (hard-won law 7, habit 2)
--------------------------------------------------------------------
* **`run.refresh_from_db()` on a row the caller holds.** It re-reads inside the
  SAME transaction, and on PostgreSQL a `READ COMMITTED` transaction opened
  before the Stop was committed still cannot see it. → This queries by primary
  key and reads only the status column, so the read is as fresh as the
  isolation level allows; and `run_to_completion` opens its transaction around
  the walk, which is why `TC-RBS-9` is proved with the stop written from a
  separate connection on PostgreSQL rather than from the same one.
* **Returning False when the run row is missing.** A deleted or mis-typed run
  id would then be *"not stopped"* for ever. → A missing row is reported as
  stopped=False and the caller is told the run was not found, because a run
  that does not exist cannot be halted and pretending otherwise would silently
  end every run that has no row (a runbook exercised from a test, say).
* **Asking after the record instead of before it.** The record has already been
  written; *"halts before the next record"* becomes *"halts after the next
  one"*, which is one letter more than the clerk agreed to. → The executor's
  loop asks at the TOP of each iteration and the test asserts the count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.runbooks import models


@dataclass(frozen=True)
class StopState:
    """Whether the run is stopped, and enough to say so in words."""

    stopped: bool
    run_found: bool = True
    stopped_by_id: Any = None

    @property
    def message(self) -> str:
        """The sentence the Records block draws against the records not walked."""
        if not self.stopped:
            return ""
        return "somebody stopped this run; the records after this point were not looked at."


NOT_STOPPED = StopState(stopped=False)


def state(run_id: Any) -> StopState:
    """Read the run's status FRESH. `run_id` None means *nothing to stop*.

    `values_list` rather than a model instance on purpose: this runs once per
    record and building a `RunbookRun` object 1,004 times to read one column is
    work nobody asked for.
    """
    if run_id is None:
        return NOT_STOPPED
    row = (
        models.RunbookRun.objects.filter(pk=run_id)
        .values_list("status", "stopped_by_id")
        .first()
    )
    if row is None:
        return StopState(stopped=False, run_found=False)
    status, stopped_by_id = row
    return StopState(
        stopped=status == models.RUN_STATUS_STOPPED,
        stopped_by_id=stopped_by_id,
    )


def stopped(ctx: Any) -> bool:
    """The one-line form the executor's loop calls. Reads `ctx.run_id`."""
    return state(getattr(ctx, "run_id", None)).stopped


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-012 (EP-RBS-04; CR-075 wave L task L5)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(the POST .../stop route is L3 and lives in a sibling's api.py — see this lane's report) E=n/a(no screen — L7 is another lane's) F✔ G✔ H=n/a(no 🔒 path: this composes no key, reads one status column and writes nothing)
# gates: pytest tests/test_us_rbs_012_stop.py · G115
# exceptions: nothing here WRITES the stopped status — the endpoint that does is L3's and belongs to apps/runbooks/api.py, which this lane may not edit
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
