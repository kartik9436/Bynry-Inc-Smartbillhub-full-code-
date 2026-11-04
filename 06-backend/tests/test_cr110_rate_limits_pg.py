# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave D — the two migrations, on the vendor that can
#           actually hold their guarantees.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE — the sixth tenant table) ·
#           hard-won law 14 (a caught database error and a `continue` is a
#           SAVEPOINT or it is data loss, and SQLite cannot see the difference)
#           · 🔒 migration ordering + RLS policies
# Impacts:  apps/integrations/migrations/0009_cr110_rate_limit_store.py ·
#           0010_cr110_key_scope.py · services.ensure_rate_limits
# ───────────────────────────────────────────────────────
"""The two migrations on PostgreSQL — the policy, the CHECK, and the savepoint.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_cr110_rate_limits_pg.py

⚠ **THE CASE THIS FILE EXISTS FOR IS
`test_a_duplicate_limit_row_does_not_abort_the_whole_transaction`, AND IT IS
HARD-WON LAW 14 EXACTLY.** `services.ensure_rate_limits` catches
`IntegrityError` on a row that is already there and carries on. On SQLite that
works whatever you write; on PostgreSQL a failed statement ABORTS THE
TRANSACTION, so the obvious version — `try: create() except IntegrityError:
continue` — would skip the duplicate and then silently discard the connection
row, the audit row and everything else in flight, at COMMIT. **The broken
version passes the entire default suite, green, on every machine.** This case
is the only place the difference is visible, and it is written so that removing
the nested `transaction.atomic()` makes it red.

Every case carries `requires_postgres` and SKIPS on SQLite rather than passing
vacuously.
"""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.integrations import models, services
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

TABLE = "integration_rate_limit"


def _kiosk(actor, tenant):
    """The kiosk network — three operations a partner may call, so three
    seeded limit rows."""
    return services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key="payments_kiosk",
        environment="production",
        label=f"{tenant.name} kiosks",
    )


# ══════════════════════════════════════════════════════════════════════════
# Migration 0009 — the table, its policy and its CHECK
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_the_sixth_tenant_table_is_named_in_the_one_list():
    """`models.TENANT_TABLES` is what the isolation probe walks. A seventh
    table added without being named there is a table nothing proves."""
    assert TABLE in models.TENANT_TABLES
    assert len(models.TENANT_TABLES) == 6


@requires_postgres
@pytest.mark.django_db
def test_the_limit_table_shows_nothing_without_a_tenant_context(rls_probe_role, brazos, dana):
    """Hard rule 1 on the sixth table, under the NON-SUPERUSER probe role —
    the connected role may bypass row security and a green under it would prove
    nothing. The policy is in `0009` itself rather than in `0002_rls_force`,
    so this is the case that proves it went on at all."""
    with live_tenant_context(brazos.id):
        _kiosk(dana, brazos)
        assert models.IntegrationRateLimit.objects.count() == 3
    assert_denied_without_context(TABLE)


@requires_postgres
@pytest.mark.django_db
def test_one_utility_cannot_see_anothers_ceilings(rls_probe_role, brazos, lonestar, dana, erin):
    with live_tenant_context(brazos.id):
        _kiosk(dana, brazos)
    with live_tenant_context(lonestar.id):
        _kiosk(erin, lonestar)
        assert models.IntegrationRateLimit.objects.count() == 3
        assert (
            models.IntegrationRateLimit.objects.exclude(tenant_id=lonestar.id).count() == 0
        )


@requires_postgres
@pytest.mark.django_db
def test_the_database_refuses_a_ceiling_of_no_calls(brazos, dana):
    """A ceiling of zero is a connector that can never be called, and it would
    arrive as a typo rather than as a decision. The CHECK is in the database
    as well as in the registry's loader, so neither a manifest nor a hand-typed
    row can carry it."""
    with live_tenant_context(brazos.id):
        row = _kiosk(dana, brazos)
        for bad in (0, -1):
            with pytest.raises(DatabaseError):
                with transaction.atomic():
                    models.IntegrationRateLimit.objects.create(
                        tenant_id=brazos.id,
                        connection=row,
                        operation=f"invented_{bad}",
                        calls_per_minute=bad,
                    )


@requires_postgres
@pytest.mark.django_db
def test_one_connection_cannot_hold_two_ceilings_for_one_operation(brazos, dana):
    with live_tenant_context(brazos.id):
        row = _kiosk(dana, brazos)
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                models.IntegrationRateLimit.objects.create(
                    tenant_id=brazos.id, connection=row, operation="payments", calls_per_minute=50
                )


@requires_postgres
@pytest.mark.django_db
def test_a_duplicate_limit_row_does_not_abort_the_whole_transaction(brazos, dana):
    """⚠ **HARD-WON LAW 14, AND THE ONLY PLACE IT IS VISIBLE.**

    `ensure_rate_limits` is called a second time on a connection that already
    has its rows. Every `create()` raises `IntegrityError`; each one is inside
    its own nested `transaction.atomic()`, so each is rolled back to a
    SAVEPOINT and the outer transaction survives. Then a write AFTER the loop
    must still succeed — that is the assertion that fails if somebody
    'simplifies' the nested atomic away, because on PostgreSQL the transaction
    would be aborted and the write would raise
    `InFailedSqlTransaction: current transaction is aborted`.
    """
    with live_tenant_context(brazos.id):
        row = _kiosk(dana, brazos)
        assert models.IntegrationRateLimit.objects.filter(connection=row).count() == 3

        with transaction.atomic():
            written = services.ensure_rate_limits(row)
            assert written == 0
            # The transaction is STILL USABLE. On the naive version this line
            # raises InFailedSqlTransaction.
            models.IntegrationConnection.objects.filter(pk=row.pk).update(label="still writable")

        row.refresh_from_db()
        assert row.label == "still writable"
        assert models.IntegrationRateLimit.objects.filter(connection=row).count() == 3


@requires_postgres
@pytest.mark.django_db
def test_re_seeding_never_resets_a_ceiling_somebody_negotiated(brazos, dana):
    """A utility that bought a bigger quota must not have it reset to the
    manifest's default by a housekeeping call."""
    with live_tenant_context(brazos.id):
        row = _kiosk(dana, brazos)
        models.IntegrationRateLimit.objects.filter(connection=row, operation="payments").update(
            calls_per_minute=5000
        )
        services.ensure_rate_limits(row)
        assert (
            models.IntegrationRateLimit.objects.get(
                connection=row, operation="payments"
            ).calls_per_minute
            == 5000
        )


@requires_postgres
@pytest.mark.django_db
def test_an_ORM_delete_takes_the_ceilings_and_a_RAW_delete_is_refused(brazos, dana):
    """⚠ **THIS CASE COST THREE ROUNDS AND IS THE MOST USEFUL ONE IN THE FILE,
    BECAUSE WHAT IT PROVED IS THE OPPOSITE OF WHAT IT WAS WRITTEN TO PROVE.**

    It was written to assert `ON DELETE CASCADE` in the database, which the
    migration's docstring and the database-design brief both claimed. It failed
    three times, for three different reasons, and the third one was the truth:

      1. `assert 3 == 0` — the cascade was Django's, not the database's;
      2. `assert 3 == 0` again — the `ALTER TABLE` that was meant to fix it had
         picked the `tenant_id` foreign key, because the lookup asked for
         `contype = 'f'` and took the first row;
      3. `assert 3 == 0` a third time — the `ALTER TABLE` found NO constraint
         at all, because Django creates a `CreateModel`'s foreign keys through
         `deferred_sql`, flushed only after every operation in the migration
         has run.

    So the claim came out of the docstring and the brief instead, and this case
    now asserts **what is actually true**, both halves of it:

      * an **ORM** delete removes the ceilings — Django issues the child DELETE
        itself, which is the ordinary path and the one `disconnect()` would use;
      * a **RAW** delete does NOT, and is **REFUSED** when the deferred
        constraint is checked. That is a safe direction — nothing silently
        loses a ceiling — and asserting it is what stops a later lane
        "restoring" a cascade that cannot be written where it tried to write it.
    """
    with live_tenant_context(brazos.id):
        row = _kiosk(dana, brazos)
        assert models.IntegrationRateLimit.objects.filter(connection=row).count() == 3

        # The RAW half: refused, not silently orphaned.
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM integration_connection WHERE id = %s", [str(row.id)]
                    )
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

        # The ORM half: the ceilings go with it.
        assert models.IntegrationRateLimit.objects.filter(connection=row).count() == 3
        models.IntegrationCredential.objects.filter(connection=row).delete()
        row.delete()
        assert models.IntegrationRateLimit.objects.filter(connection_id=row.id).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# Migration 0010 — the scope column
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_a_credential_written_without_a_scope_grants_nothing(brazos, dana):
    """The column is NOT NULL with a default of `[]`. There is no third state
    — *nobody said* — for a later reader to decide meant everything."""
    with live_tenant_context(brazos.id):
        row = _kiosk(dana, brazos)
        credential = services.record_credential(
            actor=dana, connection=row, payload="x", masked_hint="••••0001"
        )
        credential.refresh_from_db()
        assert credential.scope == []


@requires_postgres
@pytest.mark.django_db
def test_a_raw_insert_that_forgets_the_scope_gets_nothing_rather_than_an_error(brazos, dana):
    """⚠ **THE THIRD GUARD, AND IT WAS A SENTENCE UNTIL A SIBLING'S TEST SAID
    SO.** `0010`'s docstring promises that a row written by some future path
    that forgets the scope *arrives powerless rather than omnipotent*. Django
    uses a field default to BACKFILL an `AddField` and then DROPS the database
    default, so that promise was false: a raw `INSERT` got `null value in
    column "scope" … violates not-null constraint`.

    It surfaced through `test_us_int_014_pg.py::…_tc1_…`, a case about a
    completely different guarantee whose raw `INSERT` omitted a column that did
    not exist when it was written. **Reading a failure I did not expect is what
    found it** — law 7's first habit.

    This case is the one that will go red if somebody removes
    `restore_scope_default`.
    """
    with live_tenant_context(brazos.id):
        row = _kiosk(dana, brazos)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO integration_credential
                    (id, tenant_id, connection_id, version, is_active, payload_enc,
                     masked_hint, created_at)
                VALUES (gen_random_uuid(), %s, %s, 7, false, 'x', '••••0007', now())
                """,
                [str(brazos.id), str(row.id)],
            )
        # ⚠ `values_list`, NOT `.get()`. The raw INSERT above puts a plain `'x'`
        # into `payload_enc`, which is an `EncryptedTextField`; loading the
        # whole row would raise `FieldDecryptionError` — correctly, because a
        # high-sensitivity column holding a plain value is a defect and
        # `core/crypto.py` refuses to return it as cleartext. Selecting one
        # column asks the only question this case is about.
        written = models.IntegrationCredential.objects.filter(
            connection=row, version=7
        ).values_list("scope", flat=True)
        assert list(written) == [[]], "a forgotten scope must grant NOTHING, not raise"


@requires_postgres
@pytest.mark.django_db
def test_the_scope_column_is_covered_by_the_credential_tables_existing_policy(
    rls_probe_role, brazos, dana
):
    """`0002_rls_force` put the policy on the TABLE, and a policy is over the
    ROW rather than over a column list — so a column added later is covered the
    moment it exists. `0010` re-states nothing, and this is the case that says
    so out loud."""
    with live_tenant_context(brazos.id):
        row = _kiosk(dana, brazos)
        services.record_credential(
            actor=dana, connection=row, payload="x", masked_hint="••••0001", scope=["payments"]
        )
    assert_denied_without_context("integration_credential")
