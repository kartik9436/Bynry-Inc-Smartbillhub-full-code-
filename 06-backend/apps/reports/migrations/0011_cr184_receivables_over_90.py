"""reports 0011 — the platform definition `receivables_over_90_by_service` (CR-184-BRC10).

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path, and this
migration lifts `FORCE ROW LEVEL SECURITY` round one insert (hard rule 1).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-14 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHAT IT ADDS
────────────
ONE platform row (`tenant_id IS NULL`) in `report_definitions`: **Receivables
over 90 days by service**, group `receivables`, sub-group `receivables_arrears`
— beside AR Ageing, the report it is a slice of. It is served by the module
viewer `apps/reports/receivables_by_service.py` through `runner.queries_for`.

**The dataset is `receivables`** — the tenth dataset, added by the same change
— and this row is also what makes `test_p0_6__every_definition_names_one_of_
the_nine_datasets` hold: every dataset is reached by at least one platform
report. **The basis is `posting`, labelled *Posting date*** (BR-REP-001), the
ageing's own.

⚠ **FORCE IS LIFTED ROUND THE INSERT, EXACTLY AS `0003`, `0007`, `0008` AND
`0010` LIFT IT, AND FOR THEIR REASON**: a platform row carries `tenant_id IS
NULL`, which `0002`'s `WITH CHECK` refuses for every role under FORCE, the
migration role included. SQLite has no row-level security and
`PostgresOnlySQL` skips there.

**A reviewer should check, in one sentence:** that the reverse re-enables
`FORCE`, and that both directions touch the platform row only (`tenant_id IS
NULL`) — a utility's own copy of this report is never rewritten or deleted.

**Rollback:** reverse this migration — the row goes and the card goes.
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

KEY = "receivables_over_90_by_service"
DEFINITION = {
    "name": "Receivables over 90 days by service",
    "dataset": "receivables",
    "group_code": "receivables",
    "sub_group_code": "receivables_arrears",
    "columns": [],
    "filters": {"basis": "posting", "basis_label": "Posting date"},
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
    # ⚠ `0010` was the single `reports` leaf at authoring time (checked on the
    # branch tip 696b826f1, `ls-tree origin/claude/serene-noether-71ie5b`).
    dependencies = [("reports", "0010_cr179_rate_impact")]

    operations = [
        PostgresOnlySQL(NO_FORCE, reverse_sql=FORCE),
        migrations.RunPython(_seed, _unseed),
        PostgresOnlySQL(FORCE, reverse_sql=NO_FORCE),
    ]
