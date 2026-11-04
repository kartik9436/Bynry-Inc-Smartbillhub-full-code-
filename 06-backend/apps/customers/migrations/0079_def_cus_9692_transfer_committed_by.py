"""customers 0079 — `DEF-CUS-9692`: who committed a sale, on the sale's own row.

A transfer record read *Committed by: Not recorded* over a sale a clerk had
just committed in the wizard (TRF-26-0001, lane WALK-B), because `transfers`
kept the moment (`committed_at`) and not the person. The name lives in
`audit_log`, which is pruned on a retention schedule (CLAUDE.md hard rule 4,
`OQ-1340`), so it is never read from there. This column is the committer, kept
the way `move_records.performed_by` keeps a move's.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path.

🔒 HUMAN-REVIEW-PENDING — migration ordering
(`12-governance/09-human-review-ledger.md`, `DEF-CUS-9692`).

RAW DDL BECAUSE THE TABLE IS (`transfers.Transfer` is `managed = False`, created
by `0021`'s DDL), so a model `AddField` would change no database. ADDITIVE AND
SAFE ON EVERY EXISTING ROW: one nullable column, NULL on every sale committed
before this migration — and the record says *not stored* for those rather than
guessing. No foreign key, like every other id on this unmanaged table. RLS is
on the TABLE and is untouched.

Rollback: reverse this migration; the committers recorded since are lost and
the record goes back to *not stored*.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0078_def_cus_9521_deposit_size_pick"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE transfers ADD COLUMN committed_by uuid NULL",
            reverse_sql="ALTER TABLE transfers DROP COLUMN committed_by",
        ),
    ]
