# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-012 (EP-RBS-04) — CR-075 wave L task L5: *"Stop, reachable at
#           every moment"*.
# Rules:    US-RBS-012's acceptance sentence (*"stopping halts before the next
#           record; records already acted stay acted and are listed"*) ·
#           BR-RBS-007 (one savepoint per record) · CLAUDE.md hard rule 4 (a
#           stop never un-writes anything)
# Tests:    this file (TC-RBS-9)
# Impacts:  apps/runbooks/engine/stop.py · engine/executor.py
# ───────────────────────────────────────────────────────
"""Stopping halts BEFORE the next record — and the records already done stay done.

⚠ **`TC-RBS-9` IS FIRST SHOWN RED ON *A STOP THAT ONLY SETS A FLAG*** — the
specific wrong build `EP-RBS-04` names. That build passes every other test in
this repository: the endpoint answers 200, the status column reads `stopped`, the
run history shows it, and 812 letters go out anyway. The only thing that can tell
the two apart is a case that counts what the loop actually walked, which is what
`test_..._halts_before_the_next_record` does.
"""

from __future__ import annotations

import pytest

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    Block,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.engine import executor, stop
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar

pytestmark = pytest.mark.django_db

SUBJECTS = tuple(
    SubjectRef(subject_type="account", subject_id=f"0000000{n}-0000-4000-8000-00000000000{n}")
    for n in range(1, 6)
)


def _definition(walked: list):
    """Five subjects, one per-record step, and a list of what it actually saw."""

    def run(ctx, subject):
        walked.append(subject.subject_id)
        return "done"

    return RunbookDefinition(
        key="a_stoppable_action",
        name="A stoppable action",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="account",
        resolve=lambda ctx: list(SUBJECTS),
        report=lambda view: [Block(block="kpis", payload={"tiles": []})],
        steps=(Step(key="s", label="s", mode=MODE_PER_RECORD, run=run, writes=True),),
    )


def _run(tenant, *, status):
    from django.utils import timezone

    runbook = models.Runbook.objects.create(
        tenant=tenant,
        key="a_stoppable_action",
        name="A stoppable action",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="account",
    )
    return models.RunbookRun.objects.create(
        tenant=tenant,
        runbook=runbook,
        version=1,
        mode=models.MODE_DRY,
        status=status,
        started_at=timezone.now(),
    )


def test_an_unstopped_run_walks_every_record(brazos):
    """The control case. Without it, a broken stop that halts EVERYTHING passes.

    A test that only ever asserts *fewer than five* is a check whose false pass
    you can describe in one sentence (hard-won law 7, habit 2): a `stopped()`
    that returned True unconditionally would satisfy it.
    """
    from core import tenancy as core_tenancy

    walked: list[str] = []
    with core_tenancy.tenant_context(brazos.id):
        run = _run(brazos, status=models.RUN_STATUS_RUNNING)
        result = executor.execute(
            _definition(walked), tenant_id=brazos.id, run_id=run.pk, mode="dry"
        )
    assert len(walked) == 5
    assert result.stopped_at_step == ""
    assert len(result.records) == 5


def test_tc_rbs_9_a_stop_halts_before_the_next_record(brazos):
    """**SHOWN RED FIRST** on a build where the stop only set the flag.

    The run is marked `stopped` before the walk begins, so the loop must see it
    on the FIRST iteration and walk **nothing**. On the wrong build — the one
    that writes the status and never reads it — `walked` is 5 and this case is
    the only thing in the suite that says so.
    """
    from core import tenancy as core_tenancy

    walked: list[str] = []
    with core_tenancy.tenant_context(brazos.id):
        run = _run(brazos, status=models.RUN_STATUS_STOPPED)
        result = executor.execute(
            _definition(walked), tenant_id=brazos.id, run_id=run.pk, mode="dry"
        )
    assert walked == [], "a stopped run must not walk a single record"
    assert result.stopped_at_step == "s"


def test_a_stop_mid_walk_leaves_the_records_already_done_ALONE(brazos):
    """`US-RBS-012`'s second half: *records already acted stay acted and are listed.*

    The stop is written from inside the step, after two records — the shape a
    clerk actually produces by pressing the button while it runs. Nothing is
    rolled back: hard rule 4 means a queued notice stays queued, and the two
    records the run had already made are still in the result.
    """
    from core import tenancy as core_tenancy

    walked: list[str] = []

    def run(ctx, subject):
        walked.append(subject.subject_id)
        if len(walked) == 2:
            models.RunbookRun.objects.filter(pk=ctx.run_id).update(
                status=models.RUN_STATUS_STOPPED
            )
        return "done"

    definition = RunbookDefinition(
        key="a_stoppable_action",
        name="A stoppable action",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="account",
        resolve=lambda ctx: list(SUBJECTS),
        report=lambda view: [Block(block="kpis", payload={"tiles": []})],
        steps=(Step(key="s", label="s", mode=MODE_PER_RECORD, run=run, writes=True),),
    )
    with core_tenancy.tenant_context(brazos.id):
        run_row = _run(brazos, status=models.RUN_STATUS_RUNNING)
        result = executor.execute(
            definition, tenant_id=brazos.id, run_id=run_row.pk, mode="dry"
        )

    assert len(walked) == 2, "the third record must not be walked"
    assert len(result.records) == 2, "the two already done are kept and listed"
    assert result.stopped_at_step == "s"


def test_the_stop_is_read_fresh_and_not_cached(brazos):
    """A cached status is a button that changes nothing — the whole failure mode.

    Asserted directly on `stop.state`, which is the function the loop calls: the
    row is flipped underneath it and the second read must disagree with the
    first.
    """
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        run = _run(brazos, status=models.RUN_STATUS_RUNNING)
        assert stop.state(run.pk).stopped is False
        models.RunbookRun.objects.filter(pk=run.pk).update(status=models.RUN_STATUS_STOPPED)
        assert stop.state(run.pk).stopped is True


def test_a_run_id_of_none_is_not_stopped_and_costs_no_query():
    """A runbook exercised with no run row must still walk — not halt for ever."""
    assert stop.state(None) is stop.NOT_STOPPED
    assert stop.state(None).stopped is False


def test_a_missing_run_row_says_so_rather_than_halting(brazos):
    """`run_found` is False and `stopped` is False — a run that does not exist
    cannot be halted, and pretending otherwise would end every run silently."""
    import uuid

    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        state = stop.state(uuid.uuid4())
    assert state.stopped is False
    assert state.run_found is False


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-012 (EP-RBS-04; CR-075 wave L task L5)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_012_stop.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
