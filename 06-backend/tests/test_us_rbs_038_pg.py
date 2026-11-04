# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-038 · US-RBS-040 (EP-RBS-01) — CR-075 wave E task E2: the
#           append-only half of `BR-RBS-038`, on the vendor that enforces it.
# Rules:    BR-RBS-038 (a run pins the version that produced it and its stored
#           plan and report NEVER change) · CLAUDE.md hard rule 1 (RLS FORCE;
#           a cross-tenant write is refused by the database) · hard-won law 14
#           (the suite is SQLite and cannot hold either guarantee) · hard-won
#           law 7 (a check that cannot fail is the defect)
# Tests:    this file — the append-only trigger and the cross-tenant write, both
#           under the NON-SUPERUSER probe role
# Impacts:  apps/runbooks/migrations/0003_cr075_wave_e_definition_surface.py
# ───────────────────────────────────────────────────────
"""US-RBS-038 on PostgreSQL — what `runbook_versions` promised and now enforces.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_rbs_038_pg.py

⚠ **WHY THIS FILE EXISTS SEPARATELY, IN ONE SENTENCE:** `config/settings/test.py`
hardcodes in-memory SQLite, the trigger below is PostgreSQL-only, and a test for
it that ran there would report green over a guarantee that is not present. Every
case carries `requires_postgres` and SKIPS rather than passing vacuously —
hard-won law 14, and `G5` once ran the isolation suite on SQLite and **called
192 skips a pass**.

⚠ **WHAT `DEF-RBS-4307` WAS: A PROMISE WITH NOTHING BEHIND IT.** `RunbookVersion`
has said in its own docstring since wave A that *a later edit never rewrites
history*, and until `migrations/0003` a `.save()`, a `QuerySet.update()`, a data
fix or a management command could rewrite the exact document a past run pinned.
Hard-won law 1: a comment claiming a guarantee is not the guarantee.
`apps/billing/0002` had made the same promise for issued invoices WITH a trigger
since 2026-08-11, so the precedent was in the repo and was not looked for.

PROVED RED BEFORE GREEN (hard-won law 7), on the live cluster, through the
service layer that will run it rather than through a `psql` session:

    with the trigger dropped   UPDATE runbook_versions SET definition = '{}'  → UPDATE 1
    with the trigger in place  the same statement                             → ERROR:
        BR-RBS-038: runbook version 1 cannot be updated. A run pins the version
        that produced it and its stored definition never changes; edit the
        runbook and a new version is written.
"""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.runbooks import models, services
from apps.runbooks.contract import MODE_SET, Block, RunbookDefinition, Step, SubjectRef
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin


def _subjects(ctx, **params):
    return [SubjectRef(subject_type="tenant", subject_id=str(ctx.tenant_id), label="This utility")]


def _report(ctx, outcome):
    return [Block(block="kpis", payload={"tiles": []})]


def _definition() -> RunbookDefinition:
    return RunbookDefinition(
        key="stand_in",
        name="Stand in",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="config graph",
        resolve=_subjects,
        report=_report,
        steps=(Step(key="one", label="One", mode=MODE_SET, run=lambda ctx, s: "ok"),),
    )


def _seed(tenant) -> models.RunbookVersion:
    runbook = models.Runbook.objects.create(
        tenant=tenant,
        key="stand_in",
        name="Stand in",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="config graph",
        template_key="stand_in",
        cap=100,
    )
    return services.ensure_version(runbook, _definition())


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_038_a_version_cannot_be_updated_on_postgresql(brazos):
    """`BR-RBS-038` — the document a past run pinned is frozen, by the database.

    ⚠ **THE ASSERTION IS THAT THE BYTES DID NOT MOVE, NOT MERELY THAT SOMETHING
    RAISED.** A refusal that rolled back only the statement and left the row
    edited would satisfy `pytest.raises` and lose the guarantee, so the document
    is re-read afterwards and compared with what it was.
    """
    with live_tenant_context(brazos.id):
        version = _seed(brazos)
        before = dict(version.definition)

        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                models.RunbookVersion.objects.filter(pk=version.pk).update(
                    definition={"steps": []}
                )
        assert "BR-RBS-038" in str(refused.value)

        version.refresh_from_db()
        assert version.definition == before


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_038_a_version_a_run_pinned_cannot_be_deleted(brazos):
    """DELETE is refused for a version A RUN PINNED — and for nothing else.

    ⚠ **THE SECOND HALF IS WHY THIS CASE EXISTS, AND THE FIRST DRAFT OF THE
    TRIGGER FAILED IT ON THE LIVE CLUSTER.** `on_delete=CASCADE` is emulated by
    Django in PYTHON: it deletes the child rows first, in their own statement,
    **while the parent runbook is still there**. So the obvious wording —
    *refuse a DELETE while the runbook exists* — fires on every legitimate
    teardown, and `Runbook.objects.delete()` answers a foreign-key violation
    instead. Both halves are asserted here so a lane that "tightens" the trigger
    back to the obvious form meets a red rather than a support call.
    """
    with live_tenant_context(brazos.id):
        version = _seed(brazos)
        runbook_id = version.runbook_id

        # Nothing has pinned it yet: deleting it rewrites no history.
        assert models.RunbookVersion.objects.filter(pk=version.pk).delete()[0] == 1

        version = services.ensure_version(
            models.Runbook.objects.get(pk=runbook_id), _definition()
        )
        models.RunbookRun.objects.create(
            tenant=brazos,
            runbook_id=runbook_id,
            version=version.version,
            status=models.RUN_STATUS_DONE,
        )
        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                models.RunbookVersion.objects.filter(pk=version.pk).delete()
        assert "BR-RBS-038" in str(refused.value)
        assert models.RunbookVersion.objects.filter(pk=version.pk).exists()


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_038_a_runbook_with_no_runs_can_still_be_torn_down(brazos):
    """The teardown the first draft of the trigger broke, asserted on its own.

    A fixture, a test database rollback and a tenant teardown all do this, and
    every one of them would have met a foreign-key violation naming a constraint
    rather than a rule. `RunbookRun.runbook` is `PROTECT`, so a runbook that HAS
    runs cannot be deleted at all — which is why the narrower trigger costs
    nothing.
    """
    with live_tenant_context(brazos.id):
        version = _seed(brazos)
        runbook_id = version.runbook_id
        models.Runbook.objects.filter(pk=runbook_id).delete()
        assert not models.RunbookVersion.objects.filter(runbook_id=runbook_id).exists()
        assert not models.Runbook.objects.filter(pk=runbook_id).exists()


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_038_the_trigger_is_what_refuses_it_and_not_the_service(brazos, rls):
    """The guarantee holds for a caller that never goes near `services.py`.

    ⚠ **THIS IS THE CASE THAT DISTINGUISHES A TRIGGER FROM A CONVENTION.** Every
    other case above goes through the ORM, which the service layer also uses —
    so a reader could reasonably wonder whether Python is doing the refusing.
    Raw SQL under the NON-SUPERUSER probe role answers it: the statement never
    passes through this codebase at all, and it is still refused.

    ⚠ **THE FIXTURE IS `rls`, NOT `rls_probe_role`, AND THE DIFFERENCE MATTERS.**
    `rls_probe_role` is the session-scoped fixture that CREATES the role and
    returns its NAME — a string. `rls` is the per-test probe built on it, and it
    calls `assert_is_a_real_proof()` for you: a role that could bypass row
    security FAILS the test rather than skipping it, so this file cannot
    silently degrade into a green obtained under a superuser. The first draft
    took `rls_probe_role` and got `AttributeError: 'str' object has no attribute
    'assert_is_a_real_proof'` — loudly, which is the right way for that mistake
    to end.
    """
    with live_tenant_context(brazos.id):
        version = _seed(brazos)
        message = rls.refused(
            "UPDATE runbook_versions SET definition = %s::jsonb WHERE id = %s",
            ["{}", str(version.pk)],
        )
    assert "BR-RBS-038" in message


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_038_another_tenants_runbook_is_invisible_to_the_edit_path(
    brazos, lonestar, rls
):
    """Hard rule 1 at the write path: RLS answers nothing, so the edit finds nothing.

    ⚠ **THE ROUTE'S 404 IS ASSERTED ON SQLITE AND THAT PROVES ONLY THE PYTHON
    FILTER.** SQLite has no row-level security at all, so the case in
    `test_us_rbs_038_definition_surface.py` shows that `selectors.runbook_by_key`
    passes a tenant id. **This** shows the floor underneath it: under Lone Star
    Ridge's context, Brazos Bend's runbook is not merely filtered out, it is not
    visible to the connection.
    """
    with live_tenant_context(brazos.id):
        _seed(brazos)
        assert rls.count("runbooks", "key = %s", ["stand_in"]) == 1
    with live_tenant_context(lonestar.id):
        assert rls.count("runbooks", "key = %s", ["stand_in"]) == 0
        assert rls.count("runbook_versions") == 0


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_038_the_trigger_exists_by_name_on_this_database(brazos):
    """A named-object check, so a migration that silently no-ops is visible.

    ⚠ **`RunPython` ON A NON-POSTGRESQL VENDOR RETURNS EARLY, AND THAT IS EXACTLY
    THE SHAPE OF A GUARD THAT CANNOT FAIL.** The three cases above would all skip
    on SQLite whether or not the migration ran, so this one asks the catalogue
    directly: is the trigger here, under this name, on the database these tests
    are actually running against?
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_trigger WHERE tgname = %s AND NOT tgisinternal",
            ["trg_runbook_version_append_only"],
        )
        assert cursor.fetchone()[0] == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-038 · US-RBS-040 (EP-RBS-01; CR-075 wave E task E2)
# generated: 2026-09-06 by the CR-075 wave E build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — this file tests the floor under one) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_038_pg.py under config.settings.local with a PostgreSQL DATABASE_URL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
