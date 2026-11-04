"""reports 0010 — the platform definition `rate_impact` (CR-179-BRC10).

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path, and this
migration lifts `FORCE ROW LEVEL SECURITY` round one insert (hard rule 1).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-12 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHAT IT ADDS
────────────
ONE platform row (`tenant_id IS NULL`) in `report_definitions`: **Rate Impact**,
group `billing`, sub-group `billing_readiness` — the PO's own placement,
*"We want to create new report under this section -> Billing · Readiness ·
Bills · Delivery"* (CR-179 §0). It is served by the module viewer
`apps/reports/rate_impact.py` through `runner.queries_for`, so the catalogue
draws it AVAILABLE (`catalogue_read` asks the same `queries_for`, and
`queries.definition_refusal` lets a module-owned viewer win exactly as
`queries_for` does).

**The dataset is `rate_schedules`** because a definition must name an
executable dataset for `runner.bind` to resolve it, and the report is about
rate schedules. The dataset's own query never sees the call — the viewer wins
— and its one measure (`versions`) shares no name with this report's columns
or totals, so `runner._shaped`'s additivity footer leaves every figure alone.

**The basis is `event`, labelled *Period end*** — BR-REP-001 makes every money
report state one, and a billed line counts in the month its service period
ENDS (CR-179 confirmed rule 1), which is neither a posting nor a clearing date.

⚠ **FORCE IS LIFTED ROUND THE INSERT, EXACTLY AS `0003`, `0007` AND `0008` LIFT
IT, AND FOR THEIR REASON.** A platform row carries `tenant_id IS NULL`; `0002`'s
`WITH CHECK` is `tenant_id = <the session's tenant>`, so a platform row is
readable by every tenant and writable by none — the migration role included,
because `FORCE` applies to the table's owner. `SET CONSTRAINTS ALL IMMEDIATE`
before the re-`FORCE` is `0003`'s finding (*"cannot ALTER TABLE … because it
has pending trigger events"*). ⚠ **SQLITE SHOWS NONE OF THIS**: there is no
row-level security there and `PostgresOnlySQL` skips — the insert runs on both,
and the RLS half was proved on PostgreSQL 16 (see the test file's docstring).

**A reviewer should check, in one sentence:** that the reverse re-enables
`FORCE`, and that both directions touch the platform row only (`tenant_id IS
NULL`) — a utility's own `rate_impact` copy is never rewritten or deleted.

**Rollback:** reverse this migration — the row goes, the card goes, and the
viewer becomes unreachable from the catalogue (`GET /reports/rate_impact` then
answers *unknown report*). Undoing CR-179 also means removing
`rate_impact.MODULE_VIEWERS`, for the reason `statement.py` gives about `0007`.
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

KEY = "rate_impact"
DEFINITION = {
    "name": "Rate Impact",
    "dataset": "rate_schedules",
    "group_code": "billing",
    "sub_group_code": "billing_readiness",
    "columns": [],
    "filters": {"basis": "event", "basis_label": "Period end"},
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
    # ⚠ `0009` was the single `reports` leaf at authoring time (checked on the
    # branch tip, `ls-tree origin/claude/serene-noether-71ie5b`).
    dependencies = [("reports", "0009_cr142_p4_14_destinations")]

    operations = [
        PostgresOnlySQL(NO_FORCE, reverse_sql=FORCE),
        migrations.RunPython(_seed, _unseed),
        PostgresOnlySQL(FORCE, reverse_sql=NO_FORCE),
    ]
