# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W4 — five more record types a utility may define
#           its own fields on: customers, work orders, readings, routes and
#           areas. PO 2026-10-02 (commit `aa4d30f8b`), Part 1 rows 2 and 10–13,
#           each *"Not offered"* until this wave.
# Rules:    BR-TEN-046 (as amended 2026-10-02 — the W4 record types join the
#           entity list) · BR-TEN-048 (UNCHANGED — never a charge, a tax, a
#           posting or a payment allocation; Part 2 row 11 adds for readings
#           *"Never used in the bill calculation"*) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_cr161_w4_custom_fields.py
# Impacts:  apps/tenancy/models.CUSTOM_FIELD_ENTITIES · apps/tenancy/models.Area ·
#           apps/metering/migrations/0067_cr161_w4_custom_data.py (the other
#           four storage columns)
# ───────────────────────────────────────────────────────
"""tenancy 0057 — `ck_custom_field_entity` admits five more names, and
`areas` gets its `custom_data` column.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-02 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

WHAT CHANGES, IN ONE SENTENCE
-----------------------------
A utility can now define a field such as *Patrol day* on an area (typed on the
Areas card's add/edit dialog, *North district → Patrol day = Tuesday*), and the
definition table accepts the five W4 record types by name.

The CHECK is `entity IN (<CUSTOM_FIELD_ENTITIES>)` (0007), rebuilt from the
tuple's literal value AT THIS MIGRATION — never from the live tuple — exactly as
0056 did, so a later wave writes its own migration and this one keeps meaning
what it meant. No row moves.

WHY THE DATABASE DEFAULT IS SET BY HAND
---------------------------------------
`JSONField(default=dict)` is a PYTHON default; the reference-data seeder, the
reference sweep and raw fixture INSERTs would otherwise meet NOT NULL instead of
`{}`. A constant default is a catalogue change on PostgreSQL 11+, not a rewrite.

RLS: none needed — `areas` and `custom_fields` already carry their policies; a
policy is per TABLE, not per column.

ROLLBACK: the reverse restores 0056's nine-name CHECK and drops the column.
PostgreSQL refuses the CHECK while any definition on a W4 record type exists —
the honest answer: a utility that has defined such fields cannot silently lose
them by an unapply.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: 0056's tuple, literal.
BEFORE = (
    "premises",
    "units",
    "service_points",
    "assets",
    "accounts",
    "contacts",
    "addresses",
    "service_agreements",
    "payments",
)
AFTER = (*BEFORE, "customers", "work_orders", "meter_reads", "routes", "areas")

SET_DEFAULT_SQL = "ALTER TABLE areas ALTER COLUMN custom_data SET DEFAULT '{}'::jsonb;"
DROP_DEFAULT_SQL = "ALTER TABLE areas ALTER COLUMN custom_data DROP DEFAULT;"


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0056_cr161_w5_payments_custom_field_entity"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="customfield",
            name="ck_custom_field_entity",
        ),
        migrations.AddConstraint(
            model_name="customfield",
            constraint=models.CheckConstraint(
                condition=models.Q(("entity__in", AFTER)),
                name="ck_custom_field_entity",
            ),
        ),
        migrations.AddField(
            model_name="area",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        PostgresOnlySQL(sql=SET_DEFAULT_SQL, reverse_sql=DROP_DEFAULT_SQL),
    ]
