# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 (EP-INT-06) TC-3 — *"`UPDATE integration_run SET outcome
#           = 'succeeded'` on a finished run → refused by trigger"*. US-INT-021
#           TC-1 on a real database. Screens: S142
# Rules:    BR-INT-039 (append-only; corrections are new rows) · BR-INT-018 ·
#           CLAUDE.md hard rule 1 (RLS FORCE, under the non-superuser probe
#           role) · hard rule 4's shape · hard-won law 14 (a guarantee a
#           database trigger enforces is proved on PostgreSQL or it is not
#           proved: `config/settings/test.py` hardcodes in-memory SQLite, which
#           has no such trigger and never will)
# Tests:    this file. The SQLite half is tests/test_us_int_020_runs.py.
# Impacts:  apps/integrations/migrations/0003_run_items.py (the new column, on
#           the parent AND on every partition) · 0001_initial.py (the trigger
#           this file re-proves against a run that wave C now writes)
# ───────────────────────────────────────────────────────
"""US-INT-020 · US-INT-021 on PostgreSQL — the guarantees SQLite cannot express.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/<db> \\
        pytest tests/test_us_int_020_pg.py

⚠ WHY THIS FILE EXISTS AT ALL, AND IT IS HARD-WON LAW 14 WORD FOR WORD. The
service refuses to finish a run twice on every vendor, and the SQLite suite
proves that. It proves NOTHING about a hand-written `UPDATE` — the shape a
migration, a psql session or a well-meaning data fix takes — because SQLite
carries no trigger. `US-INT-020` TC-3 is exactly that statement, so it is
here, and every case SKIPS rather than passing vacuously on the default suite.
"""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.integrations import models, sample_runs, services
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin


def _smtp(actor, tenant):
    return services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key="email_smtp",
        environment="production",
        label=f"{tenant.name} mailbox",
        config={"host": "smtp.example", "port": 587},
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — a finished run cannot be updated. The exact statement the story names.
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_us_int_020_tc3_a_finished_run_cannot_be_told_it_succeeded(brazos, dana):
    """The story's own statement, run verbatim:

        UPDATE integration_run SET outcome = 'succeeded' WHERE id = <finished>

    It is the most dangerous single statement in this module — it turns an
    honest *Unconfirmed* into a green tick with no trace — and the database
    refuses it. The service refuses it too (tests/test_us_int_020_runs.py),
    but a service cannot be in the way of a psql session and this is.
    """
    with live_tenant_context(brazos.id):
        row = _smtp(dana, brazos)
        run = services.start_run(
            connection=row, operation="send_message", direction="outbound", trigger="scheduled"
        )
        services.finish_run(
            run, attempted=93, succeeded=0, failed=0, skipped=0, confirmed=False,
            summary="We handed over 93 messages and the provider did not say how many it accepted.",
        )
        assert run.outcome == models.OUTCOME_UNCONFIRMED

        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE integration_run SET outcome = 'succeeded' WHERE id = %s",
                        [str(run.id)],
                    )
        assert "BR-INT-039" in str(refused.value)
        assert "append-only" in str(refused.value)

        # …and the row still says what actually happened.
        fresh = models.IntegrationRun.objects.get(tenant_id=brazos.id, id=run.id)
        assert fresh.outcome == models.OUTCOME_UNCONFIRMED


@requires_postgres
@pytest.mark.django_db
def test_us_int_020_tc3_the_items_of_a_finished_run_cannot_be_rewritten(brazos, dana):
    """The new column is inside the same guarantee, not beside it. A row that
    named seven bad addresses cannot be quietly made to name none."""
    with live_tenant_context(brazos.id):
        row = _smtp(dana, brazos)
        run = services.start_run(
            connection=row, operation="send_message", direction="outbound", trigger="scheduled"
        )
        services.finish_run(
            run, attempted=93, succeeded=86, failed=7, skipped=0, confirmed=True,
            items=[
                {"ref": ref, "detail": address, "outcome": "failed", "provider_text": said}
                for ref, address, said in sample_runs.SEVEN
            ],
        )
        assert len(run.items) == 7
        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE integration_run SET items = '[]'::jsonb WHERE id = %s",
                        [str(run.id)],
                    )
        assert "BR-INT-039" in str(refused.value)
        assert len(models.IntegrationRun.objects.get(tenant_id=brazos.id, id=run.id).items) == 7


# ═══════════════════════════════════════════════════════════════════════════
# Migration 0003 — one ALTER TABLE, and PostgreSQL carries it to the children
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_us_int_020_the_items_column_exists_on_the_parent_and_on_every_partition():
    """A column added to a partitioned parent is on every partition, including
    the ones `core/partitioning.py` creates later. Asserted rather than
    assumed — hard-won law 1: a comment claiming a guarantee is not one."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_inherits i "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "WHERE p.relname = 'integration_run' ORDER BY c.relname"
        )
        partitions = [one[0] for one in cursor.fetchall()]
        assert partitions, "integration_run should be a partitioned parent with children"
        for table in ["integration_run", *partitions]:
            cursor.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = 'items'",
                [table],
            )
            found = cursor.fetchone()
            assert found is not None, f"{table} has no `items` column"
            assert found[0] == "jsonb", f"{table}.items is {found[0]}, not jsonb"


# ═══════════════════════════════════════════════════════════════════════════
# The leak path, and tenant isolation, on a database that actually enforces it
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_us_int_020_tc6_the_scrubbed_text_is_what_reaches_the_database(brazos, dana):
    """Read back through a raw cursor, so nothing in the ORM or the read model
    can be the thing doing the masking."""
    with live_tenant_context(brazos.id):
        row = _smtp(dana, brazos)
        run = services.start_run(
            connection=row, operation="send_message", direction="outbound", trigger="manual"
        )
        services.finish_run(
            run, attempted=1, succeeded=0, failed=1, skipped=0, confirmed=True,
            provider_error=sample_runs.LEAK,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT provider_error FROM integration_run WHERE id = %s", [str(run.id)]
            )
            stored = cursor.fetchone()[0]
    assert "4471-0021" not in stored
    assert "Pecan St" not in stored
    assert "Lone Star Ridge" not in stored
    assert "lonestarridge.example" not in stored
    assert "550 5.1.1" in stored  # the provider's own code, kept


@requires_postgres
@pytest.mark.django_db
def test_us_int_020_tc5_a_run_of_another_tenant_is_invisible_to_the_database(
    brazos, lonestar, dana, erin, rls
):
    """TC-5 through the DATABASE, under the non-superuser probe role.

    ⚠ THE ORM IS NOT THE PATH HERE, AND THAT IS THE POINT. The connected role
    on a developer machine is a superuser (`config/settings/base.py` warns
    `core.W001` about it out loud), and a superuser BYPASSES row security — so
    `IntegrationRun.objects.filter(...)` answering nothing would prove only
    that the application's own `tenant_id=` filter works, which SQLite already
    proves. `rls` runs the same statements as `sbh_rls_probe`, a role the
    policies actually apply to.
    """
    with live_tenant_context(brazos.id):
        theirs = services.start_run(
            connection=_smtp(dana, brazos), operation="send_message",
            direction="outbound", trigger="manual",
        )
        services.finish_run(
            theirs, attempted=1, succeeded=1, failed=0, skipped=0, confirmed=True
        )
    with live_tenant_context(lonestar.id):
        _smtp(erin, lonestar)

    assert_rls_scoped(
        rls,
        "integration_run",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(theirs.id)},
    )
