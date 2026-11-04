# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-017 (EP-INT-05) — zero secret persistence on refusal, on
#           the database that will run it. US-INT-002 TC-3 (the UNIQUE race).
# Rules:    BR-INT-001 · BR-INT-003 · BR-INT-026 · CLAUDE.md hard-won law 14
#           (a failed statement poisons the whole PostgreSQL transaction —
#           the refusal path must leave the connection usable, and SQLite
#           cannot show whether it does)
# Tests:    this file — the byte-for-byte count on all five tables under a
#           live tenant context; the UNIQUE race caught OUTSIDE the atomic
#           block, proved by a query that works afterwards
# ───────────────────────────────────────────────────────
"""US-INT-017 on PostgreSQL — the refusal leaves the database unchanged AND the connection usable.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_int_017_pg.py

Every case carries `requires_postgres` and SKIPS on the SQLite suite rather
than passing vacuously (hard-won law 14).
"""

from __future__ import annotations

import pytest
from django.db import connection, transaction

from apps.integrations import models, services
from tests.isolation_helpers import live_tenant_context, requires_postgres
from tests.test_us_int_helpers_b import *  # noqa: F401,F403
from tests.test_us_int_helpers_b import LOOKS_LIKE_A_KEY, SMTP_FIELDS
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana

FIVE = models.TENANT_TABLES


def _row_counts() -> dict[str, int]:
    with connection.cursor() as cursor:
        found = {}
        for table in FIVE:
            cursor.execute(f"SELECT count(*) FROM {table}")
            found[table] = cursor.fetchone()[0]
    return found


@requires_postgres
@pytest.mark.django_db
def test_us_int_017_pg_a_refused_connect_leaves_all_five_tables_byte_for_byte_unchanged(brazos, dana):
    with live_tenant_context(brazos.id):
        before = _row_counts()
        with pytest.raises(Exception) as refused:
            services.connect_with_fields(
                actor=dana, tenant_id=brazos.id, provider_key="pay_invoicecloud", environment="production",  # payments_card until CR-110-BRC04
                cadence="manual", label=None,
                fields={"merchant_id": "acct_1", "merchant_secret": LOOKS_LIKE_A_KEY, "client_id": "x"},
            )
        assert getattr(refused.value, "message_key", None) == services.REFUSAL_NOT_AVAILABLE
        assert _row_counts() == before
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM integration_credential WHERE payload_enc LIKE %s", [f"%{LOOKS_LIKE_A_KEY[:12]}%"])
            assert cursor.fetchone()[0] == 0


@requires_postgres
@pytest.mark.django_db
def test_us_int_017_pg_the_unique_race_is_refused_outside_the_atomic_block_and_the_connection_still_answers(
    brazos, dana, smtp_adapter, monkeypatch
):
    """Law 14: the IntegrityError is raised INSIDE `transaction.atomic()` and
    caught OUTSIDE it, so PostgreSQL's aborted-transaction state is rolled
    back with the savepoint. A catch inside the block would leave every
    later statement refused with `InFailedSqlTransaction` — the shape SQLite
    can never show."""
    original = services.connect

    def twice(**kwargs):
        first = original(**kwargs)
        original(**kwargs)  # the sibling request that won the race: UNIQUE fires here
        return first

    monkeypatch.setattr(services, "connect", twice)
    with live_tenant_context(brazos.id):
        with pytest.raises(Exception) as refused:
            services.connect_with_fields(
                actor=dana, tenant_id=brazos.id, provider_key="email_smtp", environment="production",
                cadence="nightly", label=None, fields=SMTP_FIELDS,
            )
        assert getattr(refused.value, "message_key", None) == services.REFUSAL_ALREADY_CONNECTED
        # The proof: the connection is usable, and the rolled-back savepoint left nothing.
        assert models.IntegrationConnection.objects.filter(tenant_id=brazos.id).count() == 0
        assert models.IntegrationCredential.objects.count() == 0
        assert not transaction.get_connection().needs_rollback
