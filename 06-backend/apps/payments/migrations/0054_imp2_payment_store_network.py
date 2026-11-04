# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10759 (L1-02 (a)+(b) — every imported payment banked under
#           one 'lockbox' channel)
# Ruling:   decision log 2026-10-30 "Eight open payment questions answered
#           (PO)" — Q6: *"can you add network name as part of csv file / excel
#           file do not add it on screen"*
# Tests:    06-backend/tests/test_imp2_store_network.py ·
#           06-backend/tests/test_imp2_store_network_pg.py
# ───────────────────────────────────────────────────────
"""payments 0054 — a payment remembers the store network a file row named.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING
— AI-authored 2026-10-30 (lane IMP-2); row in
`12-governance/09-human-review-ledger.md` (Q6 store network).

Adds ONE nullable text column, `payments.store_network`. Nothing else: no
constraint, no index, no trigger change. The immutability trigger
(`payments/0014` → `0052`) compares `to_jsonb(OLD)` with `to_jsonb(NEW)` minus
its allow lists, so the new column is frozen after INSERT without touching it
(proved on PostgreSQL in the `_pg` test). RLS covers the column with the row.

ROLLBACK: drop the column. Payments written since lose their network name; their
deposit batches keep the channel they were stamped into (`store:<name>`), so
nothing already banked moves.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0053_lbx05_returned_line_matches"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="store_network",
            field=models.TextField(blank=True, null=True),
        ),
    ]
