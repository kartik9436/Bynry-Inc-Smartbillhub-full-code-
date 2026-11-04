# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-037 (EP-INT-10) — the two guarantees only PostgreSQL gives.
# Rules:    BR-INT-032 (UNIQUE on the EXTERNAL side, held by the database; a
#           fourth partner costs rows and no migration; the chart's two vendor
#           columns are READ, never widened — OQ-INT-1480) · CLAUDE.md hard-won
#           law 14 (proved on PostgreSQL, never faked on SQLite)
# Tests:    this file — TC-2 (a second `ACHCHECK` row is refused by the UNIQUE)
#           · TC-3 (Aclarian's rows under `target_key = aclarian`,
#           `ledger_accounts` unchanged, the migration count unchanged)
# Impacts:  apps/integrations/migrations/0001_initial.py (the constraint) ·
#           apps/integrations/mappings.py
# ───────────────────────────────────────────────────────
"""US-INT-037 on PostgreSQL — the UNIQUE, and a fourth partner with no migration.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_int_037_pg.py

Every case carries `requires_postgres` and SKIPS on SQLite rather than passing
vacuously (law 14). A failed statement poisons a PostgreSQL transaction, so the
refused insert sits inside its own `transaction.atomic()` savepoint.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction

from apps.integrations import mappings, models, services
from apps.ledger.models import LedgerAccount
from apps.tenancy.models import PaymentMethod
from tests.isolation_helpers import live_tenant_context, requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana

KIOSK = "payments_kiosk"


def _bank_transfer(tenant):
    row, _ = PaymentMethod.objects.update_or_create(
        tenant=tenant, code="bank_transfer", defaults={"name": "Bank transfer", "active": True}
    )
    return row


@requires_postgres
@pytest.mark.django_db
def test_us_int_037_tc2_a_second_row_for_achcheck_is_refused_by_the_unique_on_the_external_side(
    brazos, dana
):
    """One of their words means exactly one of ours — the DATABASE says so."""
    with live_tenant_context(brazos.id):
        bank = _bank_transfer(brazos)
        services.set_mappings(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=KIOSK,
            rows=[
                {
                    "entity_type": "tender",
                    "external_value": "ACHCHECK",
                    "local_value": "bank_transfer",
                }
            ],
        )
        cash, _ = PaymentMethod.objects.update_or_create(
            tenant=brazos, code="cash", defaults={"name": "Cash", "active": True}
        )
        with pytest.raises(IntegrityError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO integration_target_reference "
                        "(id, tenant_id, target_key, entity_type, entity_id, local_value, "
                        " external_value) "
                        "VALUES (gen_random_uuid(), %s, %s, 'tender', %s, 'cash', 'ACHCHECK')",
                        [str(brazos.id), KIOSK, str(cash.id)],
                    )
        assert "uq_integration_target_ref_external" in str(refused.value)
        # …and the one row still means what it meant.
        assert mappings.local_for(brazos.id, KIOSK, "tender", "ACHCHECK")["id"] == bank.id
        # two of THEIRS may share one of ours — that direction is allowed.
        services.set_mappings(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=KIOSK,
            rows=[
                {
                    "entity_type": "tender",
                    "external_value": "ACHSAVINGS",
                    "local_value": "bank_transfer",
                }
            ],
        )
        assert (
            models.IntegrationTargetReference.objects.filter(
                tenant_id=brazos.id, target_key=KIOSK, entity_id=bank.id
            ).count()
            == 2
        )


@requires_postgres
@pytest.mark.django_db
def test_us_int_037_tc3_a_fourth_accounting_partner_costs_rows_and_no_migration(brazos, dana):
    """Aclarian wants our accounts in its words: `1200 → 001.100.11200`,
    `4100 → 001.100.44100`. Rows under `target_key = aclarian`; the chart's
    columns are untouched and no migration exists for the third vendor."""
    with live_tenant_context(brazos.id):
        for code, name in (("1200", "Accounts receivable"), ("4100", "Water sales")):
            LedgerAccount.objects.update_or_create(
                tenant=brazos, code=code, defaults={"name": name, "designation": None}
            )
        before_columns = _columns("ledger_accounts")
        services.set_mappings(
            actor=dana,
            tenant_id=brazos.id,
            provider_key="accounting_file",
            target_key="aclarian",
            rows=[
                {
                    "entity_type": "ledger_account",
                    "external_value": "001.100.11200",
                    "local_value": "1200",
                },
                {
                    "entity_type": "ledger_account",
                    "external_value": "001.100.44100",
                    "local_value": "4100",
                },
            ],
        )
        assert mappings.external_for(brazos.id, "aclarian", "ledger_account", "4100") == (
            "001.100.44100"
        )
        assert mappings.external_for(brazos.id, "aclarian", "ledger_account", "6900") is None
        served = mappings.view(brazos.id, "accounting_file", target_key="aclarian")
        assert served["counts"] == {"rows": 2, "unmapped": 0}
        assert served["types"][0]["beside_the_chart"] is True
    # the chart is exactly as it was: the same columns, still the two vendor refs, no third
    assert _columns("ledger_accounts") == before_columns
    assert {"qbo_ref", "xero_ref"} <= set(before_columns)
    assert not [
        one for one in before_columns if one.endswith("_ref") and one not in ("qbo_ref", "xero_ref")
    ]
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM django_migrations WHERE app = 'integrations'")
        assert cursor.fetchone()[0] == 2, "the fourth partner ran no migration"


@requires_postgres
@pytest.mark.django_db
def test_us_int_037_the_two_vendor_columns_are_read_not_widened(brazos, dana):
    """`qbo` and `xero` answer from the chart's own columns (OQ-INT-1480: read,
    never widened); `aclarian` answers from a row."""
    with live_tenant_context(brazos.id):
        account, _ = LedgerAccount.objects.update_or_create(
            tenant=brazos,
            code="4100",
            defaults={
                "name": "Water sales",
                "designation": None,
                "qbo_ref": "42",
                "xero_ref": "200",
            },
        )
        assert mappings.external_for(brazos.id, "qbo", "ledger_account", "4100") == "42"
        assert mappings.external_for(brazos.id, "xero", "ledger_account", "4100") == "200"
        assert mappings.external_for(brazos.id, "aclarian", "ledger_account", "4100") is None
        assert mappings.LEDGER_COLUMN_TARGETS == {"qbo": "qbo_ref", "xero": "xero_ref"}


def _columns(table: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s "
            "ORDER BY ordinal_position",
            [table],
        )
        return [row[0] for row in cursor.fetchall()]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-037@87b94265 (EP-INT-10 story + BR-INT-032 verbatim; 03-field-map.md §5 DDL)
# generated: 2026-09-03 by the CR-069 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_037_pg.py under config.settings.local + DATABASE_URL (PostgreSQL 16)
# exceptions: skips on SQLite by design — never faked (law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
