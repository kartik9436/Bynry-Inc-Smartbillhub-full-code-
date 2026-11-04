# ── Trace ──────────────────────────────────────────────
# Story:    CR-028 AST-W3-T1 (the sub-meters import target — B16 §4.7b:
#           "Sub-meters target adds PARENT_MTR … ALLOC_PCT (blank = metered,
#           not allocated)")   Screens: WFL-01.submeters.2 (the field map),
#           AST-02 sub-meter detail ("allocation share" — B16 §5.1b)
# Rules:    B16 §4.7b (ALLOC_PCT is a field of the sub-meters target) ·
#           CLAUDE.md rule 2 (percentages STORED 6dp) · BR-AST-014
#           (capture-only — nothing prices off this column)
# Tests:    06-backend/tests/test_cr028_import_targets.py (the ALLOC_PCT rows)
# Impacts:  apps/assets/services (create/import payloads) · the assets_submeters
#           import target (apps/metering/import_runs.py)
# ───────────────────────────────────────────────────────
"""assets 0008 — the sub-meter allocation share column (CR-028 AST-W3).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-22 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human").

ONE nullable NUMERIC(18,6) column. B16 §4.7b puts `ALLOC_PCT` in the
sub-meters import's field map with "blank = metered, not allocated", and
BR-MET-088 forbids offering a mapping target with no column behind it — so the
column must exist before the target can offer the field. It is a PERCENTAGE
(rule 2: 6dp stored) and not money; no rating, billing or ledger path reads
it. NULL = the sub bills its own register. No backfill; rollback is a clean
drop.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0007_cr028_valuation"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="allocation_share_pct",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028/B16@2026-08-22 (04-docs/02-decisions/16-cr028-assets-design.md §4.7b) · AST-W3-T1
# generated: 2026-08-22 by the CR-028 AST-W3 lane
# checklist: A✔ B✔ C✔ D=deferred(the import target lands in the same lane) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: migration-guard · makemigrations --check · test_cr028_import_targets.py
# exceptions: none — one nullable column, no backfill, rollback is a clean drop
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
