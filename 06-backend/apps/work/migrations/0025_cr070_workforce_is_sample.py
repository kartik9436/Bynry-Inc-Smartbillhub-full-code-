# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (the sample set) · US-WRK-020 · US-WRK-010 · US-WRK-051
# Rules:    BR-TEN-057 (a sample row is TAGGED on its own table, and removal is
#           keyed on the tag) · BR-TEN-061 (removal walks the blocks backwards)
#           · CLAUDE.md 🔒 migration ordering
# Tests:    06-backend/tests/test_cr070_sample_workforce.py
# ───────────────────────────────────────────────────────
"""work 0025 — `is_sample` on the four tables the workforce block writes.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY
───
`BR-TEN-057` puts the sample tag ON THE OWNING ROW, and `apps/tenancy/
sample_data.SampleModule.tables` quotes the tables a block needs it on so that
a missing column is NAMEABLE rather than merely absent. `work_order_rules`
already carries it (`work/0020`). `crews`, `technicians`, `parts` and
`labour_rates` did not, and the workforce block writes all four.

Without the column, removal would have to key on the seeded NAMES — which is
the narrower fallback `wizard_parks` uses and states as a divergence. That is
the right answer when a column cannot be added; here it can, and keying on a
name has a real cost: a utility that renames *Field crew A* to *North crew*
keeps a row `--remove` can no longer find, and a utility that happens to name
its own crew *Field crew A* loses it.

⚠ **SCHEMA ONLY, AND NO DATA — deliberately, and it is `0031_br_ten_1180_
backfill`'s own rule.** Schema and data on one table in one migration works on
SQLite and fails on PostgreSQL. Nothing here needs a backfill anyway: every
existing row predates the block, so `false` is the true answer for all of them,
which is exactly what a column default writes.

⚠ **NO RLS WORK.** All four tables already carry ENABLE + FORCE from their
creating migrations and a new column inherits the table's policy; adding one
does not touch the policy at all.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0024_br_wrk_058_scope_water_sub_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="crew",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="technician",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="part",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="labourrate",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-070 · US-TEN-019 · BR-TEN-057
# generated: 2026-09-07 by the CR-070 work sample-data lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a (no policy written; the four
#         tables already carry ENABLE + FORCE and a column inherits it)
# gates: makemigrations --check --dry-run · migrate against real PostgreSQL 16
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
