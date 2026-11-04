# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-012 · US-RBS-014 (EP-RBS-04) — CR-075 wave L tasks L2 + L5.
# Rules:    BR-RBS-004 (a plan first, always) · BR-RBS-015 / BR-AUD-019 (the
#           runbook is the audit actor, named and versioned, never a person) ·
#           BR-RBS-003 (dry and live are one path) · CLAUDE.md hard rule 6
#           (idempotency) · hard rule 7 (every money action writes audit_log) ·
#           OQ-RBS-1737 CLOSED
# Tests:    this file · 06-backend/tests/test_us_rbs_012_pg.py (the UNIQUE index
#           and the savepoint, neither of which SQLite can prove)
# Impacts:  apps/runbooks/engine/acts.py
# ───────────────────────────────────────────────────────
"""The engine's two acts — the plan, the audit row, and the per-record key.

⚠ **WHAT THIS FILE CANNOT PROVE, SAID FIRST.** It runs on the default suite,
which is in-memory SQLite. The UNIQUE index refusal takes a different path there
and the per-record SAVEPOINT cannot be observed at all, because SQLite has no
aborted-transaction state (hard-won law 14). Both are in
`tests/test_us_rbs_012_pg.py`, which **SKIPS** here rather than passing
vacuously — `G5` once ran the isolation suite on SQLite and called 192 skips a
pass.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.runbooks import interfaces, models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    Block,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.engine import acts, executor
from core import audit as core_audit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def real_audit_sink():
    """Put audit's OWN sink back for the duration of every case in this file.

    ⚠ **WITHOUT THIS, `test_the_audit_row_names_the_runbook…` IS RED FOR THE
    WRONG REASON — AND ITS FIRST RUN WAS** (`0 == 1`, an empty table). The
    shared metering helpers swap `core.audit`'s sink for a capture list, so a
    row written through the kernel under them never reaches `audit_log`: the
    assertion then fails on an absence that has nothing to do with the rule it
    is pointed at, which hard-won law 7 counts as no check at all.
    `test_us_aud_010_audit_actor.py` solves it exactly this way and says so;
    this is that fixture, restoring rather than clearing so a later test still
    sees the sink it expects.
    """
    from apps.audit import services as audit_services

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


SUBJECT = SubjectRef(subject_type="account", subject_id="8b1d6c0e-0000-4000-8000-000000000001")


def _request(**over):
    base = dict(
        port="queue_notice",
        action_kind="queue_notice",
        subject=SUBJECT,
        planned_action="Queue the 10-day notice",
        discriminator="first_10_day",
        decided_by_rule="The collection ladder",
        amount=Decimal("184.2000"),
        currency="USD",
        payload={},
    )
    base.update(over)
    return acts.ActRequest(**base)


def _runbook(tenant):
    return models.Runbook.objects.create(
        tenant=tenant,
        key="collections_ladder",
        name="Collections ladder",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="past due",
    )


def _ctx(tenant, *, run=None, mode="dry"):
    definition = RunbookDefinition(
        key="collections_ladder",
        name="Collections ladder",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="past due",
        resolve=lambda ctx: [SUBJECT],
        report=lambda view: [Block(block="kpis", payload={})],
        steps=(
            Step(key="s", label="s", mode=MODE_PER_RECORD, run=lambda ctx, s: "done", writes=True),
        ),
        ports=("queue_notice",),
    )
    return executor.build_context(
        definition,
        tenant_id=tenant.id,
        run_id=run.pk if run is not None else None,
        mode=mode,
    )


def _bound_ctx(tenant, *, run=None, answer=None, calls=None):
    """A context whose `queue_notice` port has a REAL writer behind it.

    ⚠ **THE FILE HAD NO SUCH HELPER UNTIL 2026-09-07 AND THAT IS WHY
    `test_the_same_act_twice…` PROVED THE WRONG THING** (hard-won law 7,
    *looking at the wrong thing*). Every case here used `_ctx`, whose ports are
    writer-less, so the first `perform` produced outcome `planned` — *nothing
    was written* — and the "no double-send" case was asserting that a PLAN
    blocks a later act. It does not, and it must not: wave `M` left 878 such
    rows on a real tenant and the live half would have queued 0 for ever
    (`DEF-RBS-4347`). The guarantee `TC-RBS-4` measures is about an act that
    HAPPENED, so proving it needs a writer.
    """
    from dataclasses import replace

    ctx = _ctx(tenant, run=run, mode="live")
    def writer(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return dict(answer or {"queued": True})

    ctx.ports = {
        name: replace(port, writer=writer) for name, port in ctx.ports.items()
    }
    return ctx


def _run(tenant, runbook, *, status=models.RUN_STATUS_RUNNING):
    from django.utils import timezone

    return models.RunbookRun.objects.create(
        tenant=tenant,
        runbook=runbook,
        version=1,
        mode=models.MODE_DRY,
        status=status,
        started_at=timezone.now(),
    )


# ── the key ───────────────────────────────────────────────────────────────


def test_the_key_does_not_carry_the_run():
    """`OQ-RBS-1737` / `TC-RBS-4` — **248 notices in total, not 496.**

    With the run in the key a retry mints a fresh key for every record and the
    guarantee is void **exactly when it is needed**, because a retry that
    matters IS a second run. Asserted as a substring test on the run id rather
    than by re-deriving the composition, so a lane that adds the run to the
    key cannot make this pass by editing the same helper twice.
    """
    key = acts.idempotency_key(
        runbook_key="collections_ladder",
        action_kind="queue_notice",
        subject=SUBJECT,
        discriminator="first_10_day",
    )
    assert key == "collections_ladder|queue_notice|account|" + SUBJECT.subject_id + "|first_10_day"


def test_the_rung_changes_the_key_and_that_is_the_thirty_day_answer():
    """A customer chased in September must be chaseable in October.

    Drop the discriminator and *runbook + record + action kind* means the ladder
    can never write to the same account twice — **ever**. The rung is what makes
    reminder → 10-day → 5-day → certified possible over one debt, which is
    `definitions/dunning.py`'s worked figure: **four letters over 45 days, not
    thirty over thirty.**
    """
    def key(rung):
        return acts.idempotency_key(
            runbook_key="collections_ladder",
            action_kind="queue_notice",
            subject=SUBJECT,
            discriminator=rung,
        )

    assert len({key(r) for r in ("friendly", "first_10_day", "second_5_day", "final_48_hour")}) == 4


def test_a_blank_component_is_refused_rather_than_collapsing_two_acts():
    """A blank runbook or action kind would put two different acts on one key."""
    with pytest.raises(acts.ActRefused):
        acts.idempotency_key(
            runbook_key="", action_kind="queue_notice", subject=SUBJECT, discriminator="x"
        )


# ── plan, then act ────────────────────────────────────────────────────────


def test_br_rbs_004_the_plan_row_is_written_before_anything_is_acted_on(brazos):
    """An Action always produces a PLAN first — there is no route without one."""
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        run = _run(brazos, runbook)
        ctx = _ctx(brazos, run=run)
        planned = acts.plan(ctx, _request())

    row = models.RunbookRunRecord.objects.get(pk=planned.record_id)
    assert row.planned_action == "Queue the 10-day notice"
    assert row.outcome is None, "the plan is written BEFORE the act, so the outcome is empty"
    assert row.decided_by_rule == "The collection ladder"
    # Money never travels without its currency (hard rule 2).
    assert row.amount == Decimal("184.2000")
    assert row.currency == "USD"


def test_a_dry_act_records_planned_and_calls_no_writer(brazos):
    """`BR-RBS-003` — the same statements, and the port simply has no writer.

    ⚠ `queue_notice` IS bound in the registry, so this cannot pass by accident
    on a port with nothing behind it.
    """
    from core import tenancy as core_tenancy

    assert interfaces.PORTS["queue_notice"].is_bound
    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        run = _run(brazos, runbook)
        ctx = _ctx(brazos, run=run, mode="dry")
        result = acts.perform(ctx, _request())

    assert result.outcome == acts.OUTCOME_PLANNED
    row = models.RunbookRunRecord.objects.get(pk=result.record_id)
    assert row.outcome == acts.OUTCOME_PLANNED
    # Nothing was queued anywhere.
    from apps.notifications import models as notification_models

    assert notification_models.OutboundMessage.objects.count() == 0


def test_the_same_act_twice_writes_ONE_record_and_the_second_says_already(brazos):
    """Hard rule 6, at the record. The second run queues nothing and SAYS SO.

    ⚠ **THE FIRST ACT MUST REACH A BOUND WRITER OR THIS CASE PROVES NOTHING.**
    Until 2026-09-07 it used `_ctx`, whose ports carry no writer, so the row it
    was asserting against had outcome `planned` — a plan, not an act — and the
    case was green over a build in which **a dry run silences the live one for
    ever** (`DEF-RBS-4347`). The writer below is what makes the first outcome
    `done`, which is the only state `TC-RBS-4`'s *248 not 496* is about.
    """
    from core import tenancy as core_tenancy

    calls: list = []
    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        first_run = _run(brazos, runbook)
        first = acts.perform(_bound_ctx(brazos, run=first_run, calls=calls), _request())
        second_run = _run(brazos, runbook)
        again = acts.perform(_bound_ctx(brazos, run=second_run, calls=calls), _request())

    assert first.outcome == acts.OUTCOME_DONE
    assert again.already is True
    assert again.outcome == acts.OUTCOME_ALREADY
    assert len(calls) == 1, "the writer was called twice — that is 496 notices, not 248"
    assert models.RunbookRunRecord.objects.count() == 1, (
        "a second run of the same ladder on the same day must add NO record — "
        "248 notices in total, not 496 (TC-RBS-4)"
    )


def test_a_DRY_plan_does_not_block_the_LIVE_act_that_follows_it(brazos):
    """`DEF-RBS-4347` — **the whole of phase 2 rests on this one sentence.**

    Wave `M` ran the collections ladder dry for a month on a real tenant and
    left **878 record rows with outcome `planned`**, which means the step
    reached the port and the port had no writer: nothing was queued, nothing was
    recorded, no customer was told anything. Read *a row exists* as *the act
    happened* and turning the runbook live the next morning queues **0 notices
    for ever**, with a Done screen reading *"0 queued · 878 already sent"* about
    letters that were never written.

    Shown RED first on the build that read the row's existence: `already` was
    True, the writer was never called and the record count stayed 1 with
    outcome `planned`.
    """
    from core import tenancy as core_tenancy

    calls: list = []
    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        dry_run = _run(brazos, runbook)
        dry = acts.perform(_ctx(brazos, run=dry_run), _request())
        live_run = _run(brazos, runbook)
        live = acts.perform(_bound_ctx(brazos, run=live_run, calls=calls), _request())
        row = models.RunbookRunRecord.objects.get()

    assert dry.outcome == acts.OUTCOME_PLANNED
    assert live.already is False, (
        "the live run treated the dry run's PLAN as an act already performed. "
        "Every customer wave M planned for would never be written to again."
    )
    assert live.outcome == acts.OUTCOME_DONE
    assert len(calls) == 1
    assert models.RunbookRunRecord.objects.count() == 1, (
        "the plan and the act are the two halves of ONE row (BR-RBS-004)"
    )
    assert str(row.run_id) == str(live_run.pk), (
        "the resumed row still names the planning run, so the audit answers "
        "'what did it say it would do versus what it did' about the wrong pass"
    )


def test_a_HELD_act_is_retried_and_an_ALREADY_is_never_resumed(brazos):
    """The two edges of the resume rule, asserted BY NAME.

    `held` means the owning module refused — a template nobody had published,
    say — and that customer must not be excluded from every future run because
    of a fault somebody has since fixed. `already` is the word `act()` stamps
    when it refused ON THIS RULE, so resuming it would make the refusal
    self-clearing and the second run would send.
    """
    assert acts.OUTCOME_HELD not in acts.OUTCOMES_SPENT
    assert acts.OUTCOME_FAILED not in acts.OUTCOMES_SPENT
    assert acts.OUTCOME_PLANNED not in acts.OUTCOMES_SPENT
    assert acts.OUTCOME_DONE in acts.OUTCOMES_SPENT
    assert acts.OUTCOME_ALREADY in acts.OUTCOMES_SPENT

    from core import tenancy as core_tenancy

    calls: list = []
    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        first = _run(brazos, runbook)

        def refuse(**kwargs):
            raise RuntimeError("no template is published for this rung")

        from dataclasses import replace

        ctx = _bound_ctx(brazos, run=first)
        ctx.ports = {n: replace(p, writer=refuse) for n, p in ctx.ports.items()}
        held = acts.perform(ctx, _request())
        second = _run(brazos, runbook)
        retried = acts.perform(_bound_ctx(brazos, run=second, calls=calls), _request())

    assert held.outcome == acts.OUTCOME_HELD
    assert retried.outcome == acts.OUTCOME_DONE, (
        "a refusal the utility has since fixed must be retryable, or one bad "
        "afternoon excludes those customers from the ladder permanently"
    )
    assert len(calls) == 1


# ── the audit row (BR-RBS-015 / hard rule 7) ──────────────────────────────


def test_the_audit_row_names_the_runbook_and_its_version_and_no_person(brazos):
    """`BR-RBS-015` — *"Collections ladder, version 1"*, and `actor_user_id` NULL.

    ⚠ **THIS IS THE ROW THAT DID NOT EXIST UNTIL `US-AUD-010` (2026-09-06).**
    Before it, a NULL `actor_user_id` meant *"system job"* and every automation
    in the product was indistinguishable — a runbook would have had to borrow a
    staff login, and a person would appear to have personally sent 812 letters
    at 07:00 on a Monday.
    """
    from apps.audit import models as audit_models
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        run = _run(brazos, runbook)
        acts.perform(_ctx(brazos, run=run), _request())
        rows = list(
            audit_models.AuditLog.objects.filter(action=acts.AUDIT_ACTION).order_by("created_at")
        )

    assert len(rows) == 1
    row = rows[0]
    assert row.actor_kind == core_audit.ACTOR_KIND_RUNBOOK
    assert row.actor_label == "Collections ladder"
    assert row.actor_version == "1"
    assert row.actor_user_id is None, "a runbook never borrows a user identity (BR-RBS-015)"
    assert row.after["port"] == "queue_notice"
    assert row.after["outcome"] == acts.OUTCOME_PLANNED


def test_a_named_actor_that_also_carries_a_user_id_is_refused_by_the_writer(brazos):
    """The platform half, asserted here too because this is its first real caller."""
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        with pytest.raises(core_audit.AuditWriteError):
            core_audit.write_row(
                action="runbook.port_write",
                entity_type="x",
                entity_id="1",
                actor_user_id="11111111-1111-4111-8111-111111111111",
                automation=core_audit.AutomationActor(
                    kind=core_audit.ACTOR_KIND_RUNBOOK, name="Collections ladder", version="1"
                ),
            )


def test_a_plan_without_tenant_context_is_refused(brazos):
    """Hard rule 1 — never touch a tenant table without `app.tenant_id` set."""
    definition_ctx = _ctx(brazos)
    definition_ctx.tenant_id = None
    with pytest.raises(acts.ActRefused):
        acts.plan(definition_ctx, _request())


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-012 · US-RBS-014 (EP-RBS-04; CR-075 wave L tasks L2 + L5)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_012_acts.py · pytest tests/test_us_rbs_012_pg.py (PostgreSQL)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
