# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10694 (lockbox audit LBX-05)
# Ruling:   decision log 2026-10-30 "Lockbox audit: what is fixed, what is not,
#           and three answers (PO)" — Q1 = A, batch decision G3 RULED
# Tests:    06-backend/tests/test_lbx05_09_statement_lines_post.py ·
#           06-backend/tests/test_lbx05_statement_lines_pg.py
# ───────────────────────────────────────────────────────
"""payments 0053 — a returned statement line is matched to ONE reversal.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING
— AI-authored 2026-10-30 (lane LBX-B); row in
`12-governance/09-human-review-ledger.md` (lockbox audit LBX-05). The markers
were added by lane FINAL-WALK the same day (`DEF-PAY-10761`, gate G07).

Adds `bank_rec_resolutions.reversal_payment_id` (nullable, line rows only) and
three partial uniques: one explanation per bank line, one line per reversal,
and one line per journal entry (a bank fee posted on a Reverse is claimed by at
most one statement line). The table stays append-only (`payments/0005`'s
trigger is untouched); RLS covers the new column with the row. Rollback drops
the column and the four constraints; rows written since lose their link to the
reversal and keep their journal entry.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0016_def_fld_10580_activation_code_register"),
        ("payments", "0052_cr186_unreconcile_unclears"),
        ("tenancy", "0067_cr199_brand_logo_link_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankrecresolution",
            name="reversal_payment",
            field=models.ForeignKey(
                blank=True,
                db_column="reversal_payment_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bank_line_matches",
                to="payments.payment",
            ),
        ),
        migrations.AddConstraint(
            model_name="bankrecresolution",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("reversal_payment__isnull", True),
                    ("bank_line__isnull", False),
                    _connector="OR",
                ),
                name="ck_bank_rec_resolutions_reversal_on_line",
            ),
        ),
        migrations.AddConstraint(
            model_name="bankrecresolution",
            constraint=models.UniqueConstraint(
                condition=models.Q(("bank_line__isnull", False)),
                fields=("tenant", "bank_line"),
                name="uq_bank_rec_resolutions_line",
            ),
        ),
        migrations.AddConstraint(
            model_name="bankrecresolution",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reversal_payment__isnull", False)),
                fields=("tenant", "reversal_payment"),
                name="uq_bank_rec_resolutions_reversal",
            ),
        ),
        migrations.AddConstraint(
            model_name="bankrecresolution",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("bank_line__isnull", False), ("journal_entry_id__isnull", False)
                ),
                fields=("tenant", "journal_entry_id"),
                name="uq_bank_rec_resolutions_line_entry",
            ),
        ),
    ]
