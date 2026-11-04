"""reports 0012 — the platform definition `owner_summary` (CR-185-BRC10 D4).

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path, and this
migration lifts `FORCE ROW LEVEL SECURITY` round one insert (hard rule 1).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-14 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHAT IT ADDS
────────────
ONE platform row (`tenant_id IS NULL`) in `report_definitions`: **Owner
summary**, group `customers`, sub-group `customers_statements` — it is a
statement (PO 2026-10-14 D4: *"one monthly statement with a section per
property and a grand total"*). It is served by the module viewer
`apps/reports/owner_summary.py` through `runner.queries_for`, so the catalogue
draws it AVAILABLE.

**The dataset is `invoices`** because a definition must name an executable
dataset for `runner.bind` to resolve it, the report is about the owner's
BILLS, and that dataset's `from`/`to`/`period` filters are the window the
viewer reads. The dataset's own query never sees the call — the viewer wins.

**The basis is `posting`, labelled *Issue date*** — BR-REP-001; a bill counts
in the period it was ISSUED, the owner accounts' own bills read as sent.

⚠ **FORCE IS LIFTED ROUND THE INSERT, EXACTLY AS `0003`, `0007`, `0008` AND
`0010`/`0011` LIFT IT, AND FOR THEIR REASON** — a platform row is writable by no
tenant, the migration role included, while `FORCE` is on. ⚠ SQLITE SHOWS NONE
OF THIS; the RLS half is proved on PostgreSQL 16.

**A reviewer should check, in one sentence:** that the reverse re-enables
`FORCE`, and that both directions touch the platform row only (`tenant_id IS
NULL`).

**Rollback:** reverse this migration and remove `owner_summary` from
`runner._OWNING_MODULES` and `exports.RESOURCES`.
"""

from __future__ import annotations

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

PLATFORM_TABLES = ("report_definitions",)

NO_FORCE = "\n".join(
    f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;" for table in PLATFORM_TABLES
)
FORCE = "SET CONSTRAINTS ALL IMMEDIATE;\n" + "\n".join(
    f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" for table in PLATFORM_TABLES
)

KEY = "owner_summary"
DEFINITION = {
    "name": "Owner summary",
    "dataset": "invoices",
    "group_code": "customers",
    "sub_group_code": "customers_statements",
    "columns": [],
    "filters": {"basis": "posting", "basis_label": "Issue date"},
    "group_by": [],
    "sort": [],
    "service_codes": [],
    "visibility": "shared",
    "owner_user_id": None,
    "version": 1,
}


def _seed(apps, schema_editor):
    model = apps.get_model("reports", "ReportDefinition")
    model.objects.update_or_create(tenant_id=None, key=KEY, defaults=dict(DEFINITION))


def _unseed(apps, schema_editor):
    model = apps.get_model("reports", "ReportDefinition")
    model.objects.filter(tenant_id=None, key=KEY).delete()


class Migration(migrations.Migration):
    # ⚠ Renumbered 0011 → 0012 on 2026-10-14 (coordinator): CR-184's
    # `0011_cr184_receivables_over_90` landed first and is the single leaf.
    dependencies = [("reports", "0011_cr184_receivables_over_90")]

    operations = [
        PostgresOnlySQL(NO_FORCE, reverse_sql=FORCE),
        migrations.RunPython(_seed, _unseed),
        PostgresOnlySQL(FORCE, reverse_sql=NO_FORCE),
    ]
