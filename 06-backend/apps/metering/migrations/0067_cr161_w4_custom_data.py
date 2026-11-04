# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W4 — routes, work orders and readings carry the
#           utility's own fields. PO 2026-10-02 (commit `aa4d30f8b`), Part 1
#           rows 10–12 (*"Has storage today ❌"*) and Part 2 rows 10–12.
# Rules:    BR-TEN-046 (as amended 2026-10-02) · BR-TEN-048 (UNCHANGED —
#           captured, shown, searched and exported only; Part 2 row 11, for
#           readings: *"Never used in the bill calculation"*) · CLAUDE.md hard
#           rule 1 · hard rule 4 spirit for `meter_reads` (written at INSERT,
#           never by an UPDATE)
# Tests:    06-backend/tests/test_cr161_w4_custom_fields.py
# Impacts:  apps/metering/models.Route / ReadImportRow / MeterRead ·
#           apps/metering/connections.WorkOrder ·
#           apps/tenancy/migrations/0057_cr161_w4_custom_field_entities.py
# ───────────────────────────────────────────────────────
"""metering 0067 — ONE jsonb column, `NOT NULL DEFAULT '{}'`, on four tables:

    routes.custom_data            — typed on the route wizard, shown on the route page
    work_orders.custom_data       — typed on New / Edit work order, shown on its detail
    read_import_rows.custom_data  — a staged reading's answers, checked at stage time
    meter_reads.custom_data       — carried from the staged row by `_post_row`

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-02 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

A WORKED EXAMPLE
----------------
A utility defines *Seal number* on Readings. A meter reader posts M-4021 at
1,284 kWh with *Seal number = S-2207*; the reading detail shows *Seal number
S-2207*, and the bill for that month is computed from 1,284 kWh exactly as it
would be without the field — no rating, estimation, VEE or billing code reads
this column (G6 / DB-17, absolute for `apps/rating/`).

WHY `work_orders` IS HERE AND NOT IN `apps/work/migrations/`
-------------------------------------------------------------
The table is still metering's model (`apps/metering/connections.WorkOrder`,
`16-work/03-field-map.md` §4 is undecided), so its schema moves only through
metering's migrations. Work writes the answers through its seam, never with an
ORM verb of its own (BR-WRK-002, G78).

PARTITIONING — `meter_reads`
----------------------------
`ADD COLUMN` on the partitioned parent reaches every ATTACHED partition. A
DETACHED archive partition does not receive it — the same posture `0032` took
for `read_method` — and `selectors.ReadArchiveResultSet._COLUMNS` therefore does
not name the column: an archived reading shows no answers rather than raising.
A constant default is a catalogue change on PostgreSQL 11+, so no row is
rewritten and `meter_reads_value_immutable` (0007) is never fired by this file.

WHY THE DATABASE DEFAULT IS SET BY HAND
---------------------------------------
`JSONField(default=dict)` is a PYTHON default. Seeders, bulk inserts and
`INSERT … SELECT` corrections would meet NOT NULL instead of `{}`.

RLS: none needed — all four tables carry their policies; a policy is per TABLE.

ROLLBACK
--------
Reverse drops the defaults and the columns. Answers already typed are lost with
them; no money figure depends on any of them.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLES = ("routes", "work_orders", "read_import_rows", "meter_reads")

SET_DEFAULT_SQL = "\n".join(
    f"ALTER TABLE {table} ALTER COLUMN custom_data SET DEFAULT '{{}}'::jsonb;" for table in TABLES
)
DROP_DEFAULT_SQL = "\n".join(
    f"ALTER TABLE {table} ALTER COLUMN custom_data DROP DEFAULT;" for table in TABLES
)


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0066_cr162_premises_type_account_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="route",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="workorder",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="readimportrow",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="meterread",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        PostgresOnlySQL(sql=SET_DEFAULT_SQL, reverse_sql=DROP_DEFAULT_SQL),
    ]
