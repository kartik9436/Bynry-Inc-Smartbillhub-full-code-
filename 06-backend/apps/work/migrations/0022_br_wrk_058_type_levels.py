# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007 (a work order TYPE catalogue) — amended by the Product
#           Owner's ruling of 2026-09-07.  Screen: Work-018 / S8 Reference data
# Rules:    BR-WRK-058 (a row with no parent IS a type, a row with a parent IS
#           a sub-type; exactly two levels, enforced in the service) ·
#           BR-TEN-036 (a SEEDED row is deactivatable, never deletable) ·
#           BR-TEN-012 (insert-missing; a tenant-touched row is never
#           overwritten) · CLAUDE.md hard rule 1 (every write under
#           `app.tenant_id`; RLS FORCE is on these tables) · hard rule 4
#           (financial immutability — NOT engaged: nothing here touches an
#           invoice, a payment or a journal line)
# Tests:    06-backend/tests/test_cr070_work_order_type_levels.py
# Impacts:  apps/work/migrations/0023 (the data half) · apps/work/models.py
#           (the column and the three seed tuples) · apps/work/lookups.py (the
#           depth refusals and the seeder) · apps/tenancy/services.py (the
#           service-enablement pass)
# ───────────────────────────────────────────────────────
"""work 0022 — `work_order_types.parent_id`. The COLUMN, and only the column.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

⚠ **THE DATA HALF IS `0023` AND THE SPLIT IS NOT TIDINESS — ONE MIGRATION
CANNOT DO BOTH, AND POSTGRESQL IS THE ONLY PLACE THAT SAYS SO.** With the
`AddField` and the `RunPython` in one file, `manage.py migrate` against real
PostgreSQL 16 dies with:

    django.db.utils.OperationalError: cannot CREATE INDEX "work_order_types"
    because it has pending trigger events

Django opens ONE schema editor for a migration's whole operation list and runs
its `deferred_sql` — the foreign-key constraint AND the index for this column —
when that editor CLOSES, which is after the `RunPython`. So the rows are written
first, the deferrable FK constraint is added second and queues its validation
trigger events, and the `CREATE INDEX` that follows on the same table is refused.

**The suite never sees it.** `config/settings/test.py` hardcodes in-memory
SQLite, which has no deferred constraint triggers at all, so the single-file
version applies cleanly and every test passes — hard-won law 14's shape, one
mechanism over. It was found by running `migrate` against a seeded PostgreSQL
database, and by nothing else.

**Do not merge `0023` back into this file.**


WHAT THE PRODUCT OWNER RULED, AND WHY IT IS A SCHEMA CHANGE
-----------------------------------------------------------
This table shipped **eight flat rows**. The PO rejected them in one sentence —
*"this is not correct - you will ahve to think from all Utilty services point
of view - and based on selection you will ahve to add"* — and then supplied the
replacement themselves: **nine types and eighteen sub-types**, plus twenty-four
more hung under the same nine, one group per utility service.

Two levels is a COLUMN. It is not a fixture edit, and mistaking it for one is
the single thing this migration exists to prevent a lane from doing.

RLS IS UNTOUCHED AND THAT IS DELIBERATE
----------------------------------------
`work_order_types` carries `ENABLE` + `FORCE ROW LEVEL SECURITY` (work/0002)
with a policy on `tenant_id`. A new COLUMN inherits it: the policy is a
row-level predicate and knows nothing about which columns a row has. No policy
is written or rewritten here, which is why this file is NOT a 🔒 path and
`0023` — which WRITES rows — is the one that has to set `app.tenant_id`.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # The Work reference tables and their RLS policies.
        ("work", "0021_rls_force_rules"),
    ]

    operations = [
        migrations.AddField(
            model_name="workordertype",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                db_column="parent_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sub_types",
                to="work.workordertype",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-07 (12-governance/02-decision-log.md, three entries) ·
#         BR-WRK-058 · US-WRK-007
# generated: 2026-09-07 by the BR-WRK-058 two-level work order types lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a (no RLS policy is written or
#         changed here — the six policies are work/0002's, and a new COLUMN on a
#         table that already carries ENABLE+FORCE inherits them)
# gates: makemigrations --check --dry-run · migrate against real PostgreSQL 16
# exceptions: the data half is `0023`, and the split is REQUIRED — see the
#         docstring's own section on the pending-trigger-events failure
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
