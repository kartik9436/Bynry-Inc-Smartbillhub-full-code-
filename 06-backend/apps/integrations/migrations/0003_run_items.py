# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 (EP-INT-06) — *"the last twenty runs … each row opening a
#           run with its per-item results"*. Frame 51.1, *THE SEVEN IT COULD NOT
#           SEND*. Screens: S142
# Rules:    BR-INT-040 (P4 — per-item results, never a batch boolean) ·
#           BR-INT-039 (append-only; the trigger installed in 0001 is not
#           touched here) · CLAUDE.md hard rule 1 (RLS FORCE, set in 0002 and
#           inherited by every partition — a column adds no policy)
# Tests:    06-backend/tests/test_us_int_020_runs.py ·
#           06-backend/tests/test_us_int_020_pg.py (the column exists on every
#           partition and the append-only trigger still refuses)
# Impacts:  apps/integrations/models.py (IntegrationRun.items) ·
#           apps/integrations/services.py (`finish_run(items=…)`) ·
#           04-docs/05-modules/13-integrations/03-field-map.md (the DDL block)
# ───────────────────────────────────────────────────────
"""integrations 0003 — the items a run could not do. HUMAN-OWNED (migration
ordering is a 🔒 sensitive path, CLAUDE.md).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*), with a row in
`12-governance/09-human-review-ledger.md` stating in plain English what a
reviewer is owed and with which figures.

ONE COLUMN, NOT A SIXTH TABLE — and the arithmetic that decided it
------------------------------------------------------------------
`US-INT-020` sizes this product's run volume out loud: *"720,000 rows a year
for email alone at 60,000 accounts"*. A per-item TABLE would multiply that by
the batch size — 93 messages a run on the fixture utility, so roughly 67
million rows a year for one operation — to store, for almost every one of
them, the fact that a message went out fine. **The rows that say a message
went out fine already exist**: they are the notification queue rows the
dispatcher writes, and wave F's `US-INT-023` maps this run's per-item results
onto them. Duplicating them here buys nothing and costs a partitioned table.

So the run keeps the items it COULD NOT DO — the seven a clerk has to go and
fix — as a JSON array on the run itself. Seven rows, not ninety-three. The
successes stay a COUNT, which is what `succeeded` has always been.

⚠ ADDING A COLUMN TO A PARTITIONED PARENT IS ONE `ALTER TABLE` AND
POSTGRESQL CASCADES IT TO EVERY PARTITION — including partitions
`core/partitioning.py` creates later, which inherit the parent's shape. There
is no per-partition step here and there must not be one; a loop over
partitions would go stale the first time the maintenance job runs.

⚠ AND IT IS NOT AN UPDATE, SO THE APPEND-ONLY TRIGGER IS NOT IN THE WAY. The
trigger installed by 0001 is `BEFORE UPDATE OR DELETE … FOR EACH ROW`; DDL is
neither. Existing rows take the default and no row is rewritten.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0002_rls_force"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationrun",
            name="items",
            field=models.JSONField(blank=True, default=list),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-020 (EP-INT-06 §1 + §5 field table) · 03-field-map.md integration_run DDL
# generated: 2026-09-04 by the CR-069 wave C build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 row in 09-human-review-ledger.md)
# gates: applied forward and backward on PostgreSQL 16 (migrate → migrate integrations 0002 → migrate) · makemigrations --check clean on SQLite · tests/test_us_int_020_pg.py (the column on the parent AND on a partition; the trigger still refuses)
# exceptions: none — one AddField, no data migration, no policy change
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
