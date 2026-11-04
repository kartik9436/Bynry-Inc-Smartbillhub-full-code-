# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-014 (EP-INT-05) — the five tables. Screens: S8 · S142
# Rules:    BR-INT-003 · BR-INT-025 · BR-INT-026 · BR-INT-032 · BR-INT-039 ·
#           CLAUDE.md hard rule 1 · hard rule 4's shape
# Tests:    this file — TC-3 (the gate's rule, asserted from the model too),
#           TC-5 (UNIQUE tenant × key × environment), TC-6 (a foreign id is a
#           plain 404 shape — the read model answers nothing), TC-7 (the brief
#           precedes the migration in git log), plus the one-active guard on
#           SQLite and the service-layer append-only refusal. The PostgreSQL
#           half (TC-1 EXCLUDE · TC-2 zero rows without context · TC-4 trigger)
#           is tests/test_us_int_014_pg.py.
# Impacts:  apps/integrations/models.py · services.py · migrations/0001
# ───────────────────────────────────────────────────────
"""US-INT-014 — five tables, one write path, and the guarantees SQLite can hold.

Everything here runs on the default in-memory SQLite suite. The three
guarantees only PostgreSQL gives (the EXCLUDE constraint, RLS FORCE, the
append-only trigger) are asserted in `test_us_int_014_pg.py` and skipped here
rather than faked (hard-won law 14).
"""

import subprocess
from pathlib import Path

import pytest
from django.db import IntegrityError, transaction

from apps.integrations import models, services
from core import crypto
from core.crypto import EncryptedTextField
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

REPO = Path(__file__).resolve().parents[2]


def _smtp(actor, tenant, environment="production", label="Billing mailbox"):
    return services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key="email_smtp",
        environment=environment,
        label=label,
        config={"host": "smtp.example", "port": 587, "username": "billing"},
    )


# ── TC-3 — the connection table holds no secret column ──────────────────────


def test_us_int_014_tc3_the_connection_table_has_no_encrypted_and_no_secret_named_column():
    """The gate G75 reads the source; this reads the model the ORM built —
    two independent statements of one rule."""
    for field in models.IntegrationConnection._meta.get_fields():
        assert not isinstance(field, EncryptedTextField), field.name
        for word in ("secret", "token", "password", "payload"):
            assert word not in field.name.lower(), field.name


def test_us_int_014_the_credential_payload_is_the_encrypted_field_and_only_there():
    field = models.IntegrationCredential._meta.get_field("payload_enc")
    assert isinstance(field, EncryptedTextField)
    assert field.crypto_context == "integration_credential.payload_enc"


# ── TC-5 — production and sandbox are two rows; a second production is refused


@pytest.mark.django_db
def test_us_int_014_tc5_a_second_production_row_is_refused_and_a_sandbox_twin_is_accepted(
    brazos, dana
):
    with tenant_ctx(brazos):
        _smtp(dana, brazos)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _smtp(dana, brazos)
        sandbox = _smtp(dana, brazos, environment="sandbox", label="Sandbox mailbox")
        assert sandbox.environment == "sandbox"
        assert models.IntegrationConnection.objects.filter(tenant=brazos).count() == 2


@pytest.mark.django_db
def test_us_int_014_a_secret_field_may_not_be_written_into_config(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(ValueError, match="BR-INT-003"):
            services.connect(
                actor=dana,
                tenant_id=brazos.id,
                provider_key="email_smtp",
                environment="production",
                config={"host": "smtp.example", "password": "hunter2"},
            )


@pytest.mark.django_db
def test_us_int_014_connect_writes_an_audit_row_with_no_secret_in_it(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        row = _smtp(dana, brazos)
    actions = [one["action"] for one in audit_rows]
    # US-INT-004 TC-1 names the lifecycle rows `integration.connected · test_run
    # · updated · disconnected`; wave B aligned the action to that name.
    assert "integration.connected" in actions
    connect_row = next(one for one in audit_rows if one["action"] == "integration.connected")
    assert connect_row["entity_id"] == row.id
    assert connect_row["after"]["provider_key"] == "email_smtp"
    assert "password" not in str(connect_row)


# ── the credential is versioned, one active, stored encrypted ───────────────


@pytest.mark.django_db
def test_us_int_014_a_credential_is_versioned_never_updated_and_stored_encrypted(
    brazos, dana, audit_rows, settings
):
    with tenant_ctx(brazos):
        connection = _smtp(dana, brazos)
        first = services.record_credential(
            actor=dana, connection=connection, payload="s3cret-one", masked_hint="••••3F9A"
        )
        second = services.record_credential(
            actor=dana, connection=connection, payload="s3cret-two", masked_hint="••••A17C"
        )
    rows = list(
        models.IntegrationCredential.objects.filter(connection=connection).order_by("version")
    )
    assert [one.version for one in rows] == [1, 2]
    assert [one.is_active for one in rows] == [False, True]
    assert rows[0].rotated_at is not None and rows[1].rotated_at is None
    assert first.pk != second.pk
    # the column holds ciphertext; the ORM decrypts on the way out
    from django.db import connection as db

    # Looked up by version and hint rather than by id: SQLite stores a UUID as
    # 32 hex characters and PostgreSQL as a uuid, and a raw `WHERE id = %s`
    # with the hyphenated string matches on one vendor and not the other.
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT payload_enc FROM integration_credential WHERE version = %s AND masked_hint = %s",
            [2, "••••A17C"],
        )
        stored = cursor.fetchone()[0]
    assert crypto.is_ciphertext(stored) and "s3cret-two" not in stored
    assert models.IntegrationCredential.objects.get(pk=second.pk).payload_enc == "s3cret-two"
    # the audit trail carries the hint and the version, never the payload.
    # ⚠ TWO ACTION NAMES SINCE 2026-09-04 (`US-INT-024`): writing the FIRST
    # version is `integration.credential.record` — nothing was replaced, so
    # nothing rotated — and replacing one is `integration.credential_rotated`,
    # which is the row that carries `••••3F9A → ••••A17C`. This assertion reads
    # both, because its subject is what the trail HOLDS, not what it is called.
    trail = str(
        [
            one
            for one in audit_rows
            if one["action"]
            in ("integration.credential.record", services.AUDIT_CREDENTIAL_ROTATED)
        ]
    )
    assert "••••A17C" in trail and "s3cret" not in trail
    assert "••••3F9A → ••••A17C" in trail


@pytest.mark.django_db
def test_us_int_014_the_database_refuses_a_second_active_credential_on_sqlite_too(brazos, dana):
    """The one-active guard on this vendor is a partial unique index — the
    same guarantee the PostgreSQL EXCLUDE gives, asserted there in TC-1."""
    with tenant_ctx(brazos):
        connection = _smtp(dana, brazos)
        services.record_credential(
            actor=dana, connection=connection, payload="one", masked_hint="••••0001"
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.IntegrationCredential.objects.create(
                    tenant=brazos,
                    connection=connection,
                    version=99,
                    is_active=True,
                    payload_enc="two",
                    masked_hint="••••0002",
                )


@pytest.mark.django_db
def test_us_int_014_a_hint_that_could_carry_the_secret_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        connection = _smtp(dana, brazos)
        with pytest.raises(ValueError, match="BR-INT-003"):
            services.record_credential(
                actor=dana, connection=connection, payload="x", masked_hint="hunter2-full"
            )


# ── the run is append-only once finished (service layer; trigger on PG) ─────


@pytest.mark.django_db
def test_us_int_014_a_finished_run_refuses_a_second_finish(brazos, dana):
    with tenant_ctx(brazos):
        connection = _smtp(dana, brazos)
        run = services.start_run(
            connection=connection, operation="send_message", direction="outbound", trigger="manual"
        )
        assert len(run.trace_id) == 8
        services.finish_run(run, attempted=93, succeeded=93, failed=0, skipped=0, confirmed=True)
        assert run.outcome == "succeeded"
        from core import errors

        with pytest.raises(errors.BizError) as refused:
            services.finish_run(
                run, attempted=93, succeeded=86, failed=7, skipped=0, confirmed=True
            )
        assert refused.value.br_ref == "BR-INT-039"


@pytest.mark.django_db
def test_us_int_014_a_run_against_an_undeclared_operation_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        connection = _smtp(dana, brazos)
        with pytest.raises(ValueError, match="declares no operation"):
            services.start_run(
                connection=connection, operation="teleport", direction="outbound", trigger="manual"
            )


# ── TC-6 — a foreign id reads as absent; the read model answers nothing ─────


@pytest.mark.django_db
def test_us_int_014_tc6_lone_star_ridge_cannot_see_brazos_bends_connection_by_id(
    brazos, dana, lonestar
):
    with tenant_ctx(brazos):
        row = _smtp(dana, brazos)
    with tenant_ctx(lonestar):
        # The ORM under the OTHER tenant's context: the row is simply absent —
        # the same shape a genuinely missing id has (deny_as_not_found, HR-1).
        assert not models.IntegrationConnection.objects.filter(
            tenant_id=lonestar.id, pk=row.pk
        ).exists()


# ── TC-7 — the schema brief precedes the migration in git log ───────────────


def test_us_int_014_tc7_the_brief_names_all_five_tables_in_a_commit_before_the_migration():
    brief = "04-docs/02-decisions/02-database-design-brief.md"
    migration = "06-backend/apps/integrations/migrations/0001_initial.py"

    def first_commit_touching(path, needle):
        # oldest commit whose version of the file contains `needle`
        shas = (
            subprocess.check_output(
                ["git", "log", "--reverse", "--format=%H", "--", path], cwd=REPO, text=True
            )
            .strip()
            .splitlines()
        )
        for sha in shas:
            text = subprocess.run(
                ["git", "show", f"{sha}:{path}"], cwd=REPO, capture_output=True, text=True
            ).stdout
            if needle in text:
                return sha
        return None

    brief_sha = first_commit_touching(brief, "### Module: integrations")
    if brief_sha is None:
        pytest.skip("the brief's integrations section is not committed yet in this checkout")
    migration_sha = first_commit_touching(migration, "class Migration")
    if migration_sha is None:
        pytest.skip("integrations/0001 is not committed yet in this checkout")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", brief_sha, migration_sha], cwd=REPO
    )
    assert ancestry.returncode == 0, "the brief must precede the migration (C34, TC-7)"
    assert brief_sha != migration_sha, "the brief and the migration must be separate commits"
    brief_text = subprocess.check_output(
        ["git", "show", f"{brief_sha}:{brief}"], cwd=REPO, text=True
    )
    for table in models.TENANT_TABLES:
        assert f"CREATE TABLE {table}" in brief_text, table
