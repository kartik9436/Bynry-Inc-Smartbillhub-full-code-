# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-014 (EP-INT-05) — the guarantees only PostgreSQL gives.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE; no tenant → nothing) · BR-INT-025
#           (one active credential, by the database) · BR-INT-039 (append-only
#           once finished) · hard-won law 14 (proved on PostgreSQL, never faked
#           on SQLite)
# Tests:    this file — TC-1 (EXCLUDE), TC-2 (zero rows on all five without
#           context, under the non-superuser probe role), TC-4 (the trigger),
#           plus the partition shape (two guarded children)
# Impacts:  apps/integrations/migrations/0001_initial.py · 0002_rls_force.py
# ───────────────────────────────────────────────────────
"""US-INT-014 on PostgreSQL — the three things SQLite cannot hold.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_int_014_pg.py

Every case carries `requires_postgres` and SKIPS on the default SQLite suite
rather than passing vacuously (hard-won law 14). The RLS half runs under the
suite's NON-SUPERUSER probe role (`tests/isolation_helpers.py`), because the
connected role may bypass row security and a green under it would prove
nothing.
"""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.integrations import models, services
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

FIVE = models.TENANT_TABLES


def _smtp(actor, tenant):
    return services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key="email_smtp",
        environment="production",
        label=f"{tenant.name} mailbox",
        config={"host": "smtp.example", "port": 587},
    )


@requires_postgres
@pytest.mark.django_db
def test_us_int_014_tc1_the_database_refuses_a_second_active_credential(brazos, dana):
    """BR-INT-025 — EXCLUDE (connection_id WITH =) WHERE (is_active), below the app."""
    with live_tenant_context(brazos.id):
        row = _smtp(dana, brazos)
        services.record_credential(
            actor=dana, connection=row, payload="one", masked_hint="••••0001"
        )
        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO integration_credential "
                        "(id, tenant_id, connection_id, version, is_active, payload_enc, "
                        " masked_hint, created_at) "
                        "VALUES (gen_random_uuid(), %s, %s, 99, true, 'x', '••••0002', now())",
                        [str(brazos.id), str(row.id)],
                    )
        assert "ex_integration_credential_one_active" in str(refused.value)


@requires_postgres
@pytest.mark.django_db
def test_us_int_014_tc2_with_no_tenant_context_all_five_tables_answer_zero_rows(
    rls, brazos, dana, lonestar, erin
):
    """Hard rule 1 — the isolation probe on every table this module owns."""
    with live_tenant_context(brazos.id):
        row = _smtp(dana, brazos)
        services.record_credential(
            actor=dana, connection=row, payload="one", masked_hint="••••0001"
        )
        run = services.start_run(
            connection=row, operation="send_message", direction="outbound", trigger="manual"
        )
        services.finish_run(run, attempted=1, succeeded=1, failed=0, skipped=0, confirmed=True)
        models.IntegrationTargetReference.objects.create(
            tenant=brazos,
            target_key="kiosk",
            entity_type="tender",
            local_value="bank_transfer",
            external_value="ACHCHECK",
        )
    with live_tenant_context(lonestar.id):
        _smtp(erin, lonestar)

    # 1 · no context → zero rows on all five (deny-by-default)
    assert_denied_without_context(rls, *FIVE)

    # 2 · under each tenant, only its own rows; a cross-tenant write refused by the policy
    for table in ("integration_connection", "integration_credential", "integration_run"):
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
    assert_no_foreign_rows_anywhere(rls, lonestar, FIVE)
    message = assert_write_into_other_tenant_refused(
        rls, "integration_connection", owner=brazos, intruder=lonestar
    )
    assert "row-level security" in message


@requires_postgres
@pytest.mark.django_db
def test_us_int_014_tc4_a_finished_run_cannot_be_updated_or_deleted(brazos, dana):
    """BR-INT-039 — the trigger, below the service layer."""
    with live_tenant_context(brazos.id):
        row = _smtp(dana, brazos)
        run = services.start_run(
            connection=row, operation="send_message", direction="outbound", trigger="manual"
        )
        services.finish_run(run, attempted=93, succeeded=86, failed=7, skipped=0, confirmed=True)
        assert run.outcome == "partial"
        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE integration_run SET succeeded = 93 "
                        "WHERE finished_at IS NOT NULL AND id = %s",
                        [str(run.id)],
                    )
        assert "BR-INT-039" in str(refused.value)
        with pytest.raises(DatabaseError) as deleted:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM integration_run WHERE id = %s", [str(run.id)])
        assert "never deleted" in str(deleted.value)
        # an OPEN run may still be finished — that is the one lawful update
        open_run = services.start_run(
            connection=row, operation="send_message", direction="outbound", trigger="manual"
        )
        services.finish_run(open_run, attempted=1, succeeded=1, failed=0, skipped=0, confirmed=True)


@requires_postgres
@pytest.mark.django_db
def test_us_int_014_the_run_table_is_a_yearly_partitioned_parent_with_guarded_children():
    with connection.cursor() as cursor:
        cursor.execute("SELECT relkind::text FROM pg_class WHERE relname = 'integration_run'")
        assert cursor.fetchone()[0] == "p"
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
            "  (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) "
            "FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
            "JOIN pg_class par ON par.oid = i.inhparent "
            "WHERE par.relname = 'integration_run' ORDER BY c.relname"
        )
        children = cursor.fetchall()
    assert len(children) >= 2, children  # this year + one ahead (create_ahead = 1)
    for name, enabled, forced, policies in children:
        assert name.startswith("integration_run_"), name
        assert enabled and forced and policies == 1, (name, enabled, forced, policies)


@requires_postgres
@pytest.mark.django_db
def test_us_int_014_all_five_tables_carry_rls_force():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname FROM pg_class WHERE relrowsecurity AND relforcerowsecurity "
            "AND relname = ANY(%s)",
            [list(FIVE)],
        )
        guarded = {one[0] for one in cursor.fetchall()}
    assert guarded == set(FIVE)
