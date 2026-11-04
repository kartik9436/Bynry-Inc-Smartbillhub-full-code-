# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-012 (EP-RBS-04) — CR-075 wave L task L5, on the vendor that
#           will run it.
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction; a SAVEPOINT is the ONLY option, and the
#           suite is SQLite, which cannot see the difference) · hard rule 6
#           (idempotency by a UNIQUE index, not by application code) · hard rule
#           1 (tenant scoping; RLS FORCE) · hard-won law 7 (a check that cannot
#           fail is the defect)
# Tests:    this file
# Impacts:  apps/runbooks/engine/acts.py
# ───────────────────────────────────────────────────────
"""The two guarantees SQLite cannot hold — and this file SKIPS rather than lying.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_rbs_012_pg.py

⚠ **WHY THIS FILE EXISTS, IN ONE SENTENCE:** `config/settings/test.py` hardcodes
in-memory SQLite, which has **no aborted-transaction state at all**, so the
broken form of `acts.plan` —

    try:
        row = RunbookRunRecord.objects.create(...)
    except IntegrityError:
        return already            # ← WRONG, and green on every machine

— passes the ENTIRE default suite and loses the run the first time a real key
collides in production. On PostgreSQL that refused INSERT aborts the whole
transaction, and every later record is lost at COMMIT however carefully the
exception was caught. Two lanes found this independently on 2026-08-29, in
different modules, weeks apart; it is hard-won law 14.

Every case here carries `requires_postgres` and **SKIPS** on the default suite.
`G5` once ran the isolation suite on SQLite and called 192 skips a pass — that
is the failure this file is shaped to avoid, and the skip says so out loud.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import transaction

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    Block,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.engine import acts, duplicates, executor
from core import audit as core_audit
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana

SUBJECTS = tuple(
    SubjectRef(subject_type="account", subject_id=f"bbbbbbbb-0000-4000-8000-00000000000{n}")
    for n in range(1, 5)
)


@pytest.fixture(autouse=True)
def real_audit_sink():
    """audit's OWN sink, so `acts` writes reach `audit_log` (see the acts suite)."""
    from apps.audit import services as audit_services

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


def _runbook(tenant, key="collections_ladder"):
    return models.Runbook.objects.create(
        tenant=tenant,
        key=key,
        name="Collections ladder",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="past due",
    )


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


def _definition(run_step):
    return RunbookDefinition(
        key="collections_ladder",
        name="Collections ladder",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="past due",
        resolve=lambda ctx: list(SUBJECTS),
        report=lambda view: [Block(block="kpis", payload={})],
        steps=(Step(key="s", label="s", mode=MODE_PER_RECORD, run=run_step, writes=True),),
        ports=("queue_notice",),
    )


def _request(subject, *, discriminator="first_10_day"):
    return acts.ActRequest(
        port="queue_notice",
        action_kind="queue_notice",
        subject=subject,
        planned_action="Queue the 10-day notice",
        discriminator=discriminator,
        decided_by_rule="The collection ladder",
        amount=Decimal("184.2000"),
        currency="USD",
        payload={},
    )


# ── hard rule 6: the UNIQUE INDEX is the guarantee ────────────────────────


@requires_postgres
@pytest.mark.django_db
def test_the_second_run_of_the_ladder_queues_NOTHING_and_the_run_survives(brazos):
    """**`TC-RBS-4`: 4 records in total, not 8 — and the transaction lives.**

    This is the case the default suite cannot run. On PostgreSQL the second
    run's INSERT is refused by `uq_runbook_run_records_idem`, and **without the
    nested `transaction.atomic()` in `acts.plan` that refusal aborts everything
    after it**: subjects 2, 3 and 4 would raise `InFailedSqlTransaction`, the
    run would be lost at COMMIT, and every test on SQLite would still be green.

    Scaled to the fixture in `L9`: 248 accounts due the 10-day notice on Monday
    receive **248 notices in total, not 496**, and the second Done screen reads
    *0 queued* while naming the 248 already sent.
    """
    from core import tenancy as core_tenancy

    def step(ctx, subject):
        result = acts.perform(ctx, _request(subject))
        return {"outcome": result.outcome}

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        definition = _definition(step)

        first = _run(brazos, runbook)
        with transaction.atomic():
            first_result = executor.execute(
                definition, tenant_id=brazos.id, run_id=first.pk, mode="dry"
            )
        assert [r.outcome for r in first_result.records] == [acts.OUTCOME_PLANNED] * 4

        second = _run(brazos, runbook)
        with transaction.atomic():
            second_result = executor.execute(
                definition, tenant_id=brazos.id, run_id=second.pk, mode="dry"
            )

        # ⚠ EVERY subject reached — which is what the savepoint buys. Without
        # it the first refusal poisons the transaction and subjects 2–4 raise.
        assert [r.outcome for r in second_result.records] == [acts.OUTCOME_ALREADY] * 4
        assert models.RunbookRunRecord.objects.count() == 4, (
            "two runs of the same ladder wrote FOUR records, not eight"
        )


@requires_postgres
@pytest.mark.django_db
def test_one_refused_record_leaves_the_others_committed(brazos):
    """`TC-RBS-5` / `BR-RBS-007` — one failure never aborts the run.

    Subject 2 collides on a key planted before the run; the other three commit.
    **On the `except IntegrityError: continue` build this is 1 committed record
    and three `InFailedSqlTransaction` failures**, and the default suite reports
    it green.
    """
    from core import tenancy as core_tenancy

    def step(ctx, subject):
        return {"outcome": acts.perform(ctx, _request(subject)).outcome}

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        planted = _run(brazos, runbook)
        models.RunbookRunRecord.objects.create(
            tenant=brazos,
            run=planted,
            subject_type="account",
            subject_id=SUBJECTS[1].subject_id,
            planned_action="Queue the 10-day notice",
            idempotency_key=acts.idempotency_key(
                runbook_key="collections_ladder",
                action_kind="queue_notice",
                subject=SUBJECTS[1],
                discriminator="first_10_day",
            ),
        )

        run = _run(brazos, runbook)
        with transaction.atomic():
            result = executor.execute(
                _definition(step), tenant_id=brazos.id, run_id=run.pk, mode="dry"
            )

        outcomes = [r.outcome for r in result.records]
        assert outcomes.count(acts.OUTCOME_ALREADY) == 1
        assert outcomes.count(acts.OUTCOME_PLANNED) == 3
        # 1 planted + 3 new = 4. The refused one wrote nothing and cost nothing.
        assert models.RunbookRunRecord.objects.count() == 4


# ── hard rule 1: another utility's rows are not visible, under RLS ────────


@requires_postgres
@pytest.mark.django_db
def test_another_utility_cannot_see_this_runs_records_under_row_security(
    brazos, lonestar, rls
):
    """Hard rule 1 with `FORCE ROW LEVEL SECURITY` on, under the probe role.

    ⚠ **RUN UNDER A NON-SUPERUSER**, because the connected role may BYPASS row
    security and a green obtained as a superuser would be a green over a
    guarantee that was never tested. `tests/isolation_helpers.py` fails rather
    than skips when the role can bypass, so this cannot silently degrade.
    """
    from core import tenancy as core_tenancy

    def step(ctx, subject):
        return {"outcome": acts.perform(ctx, _request(subject)).outcome}

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        run = _run(brazos, runbook)
        with transaction.atomic():
            executor.execute(_definition(step), tenant_id=brazos.id, run_id=run.pk, mode="dry")

    with live_tenant_context(lonestar.id):
        assert models.RunbookRunRecord.objects.count() == 0, (
            "the other utility read this utility's runbook records"
        )
    with live_tenant_context(brazos.id):
        assert models.RunbookRunRecord.objects.count() == 4


@requires_postgres
@pytest.mark.django_db
def test_the_run_level_check_does_not_see_another_utilitys_run(brazos, lonestar, rls):
    """`OQ-RBS-1737`'s check, scoped. Two utilities running the same ladder at
    07:00 must not stop each other."""
    now = dt.datetime.now(dt.timezone.utc)
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(lonestar.id):
        theirs = _runbook(lonestar)
        _run(lonestar, theirs, status=models.RUN_STATUS_DONE)
    with live_tenant_context(brazos.id):
        mine = _runbook(brazos)
        verdict = duplicates.check(tenant_id=brazos.id, runbook_id=mine.pk, now=now)
    assert verdict.verdict == duplicates.VERDICT_NONE


# ── the audit row survives the same trip ──────────────────────────────────


@requires_postgres
@pytest.mark.django_db
def test_every_record_of_a_dry_run_leaves_a_NAMED_audit_row(brazos):
    """Hard rule 7 — including the `planned` ones.

    *The automation decided to write to this customer and was held* is exactly
    the fact a disputing customer asks about six weeks later, and writing the
    row only on success would leave the whole dry cycle — the thing wave `M`
    soaks for a month — invisible to the trail.
    """
    from apps.audit import models as audit_models
    from core import tenancy as core_tenancy

    def step(ctx, subject):
        return {"outcome": acts.perform(ctx, _request(subject)).outcome}

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        run = _run(brazos, runbook)
        with transaction.atomic():
            executor.execute(_definition(step), tenant_id=brazos.id, run_id=run.pk, mode="dry")
        rows = list(audit_models.AuditLog.objects.filter(action=acts.AUDIT_ACTION))

    assert len(rows) == 4
    assert {row.actor_kind for row in rows} == {core_audit.ACTOR_KIND_RUNBOOK}
    assert {row.actor_label for row in rows} == {"Collections ladder"}
    assert {row.actor_version for row in rows} == {"1"}
    assert {row.actor_user_id for row in rows} == {None}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-012 (EP-RBS-04; CR-075 wave L task L5)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H✔(proves the 🔒 idempotency key on the vendor that will run it)
# gates: DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=... pytest tests/test_us_rbs_012_pg.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
