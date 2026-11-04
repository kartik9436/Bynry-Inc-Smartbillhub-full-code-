# ── Trace ──────────────────────────────────────────────
# Change:  CR-156-BRC10 (PO 2026-10-01 — "logical kill", "we will need start
#          and effective date", option A "All sizes", "3 kinds")
# Rules:   BR-RAT-1048 · BR-RAT-1049 · BR-RAT-1051 · CLAUDE.md 🔒 migration
#          ordering
# Tests:   06-backend/tests/test_cr156_charge_prices.py ·
#          06-backend/tests/test_cr156_charge_prices_pg.py
# ───────────────────────────────────────────────────────
"""rating 0050 — the price table gains its dates and its killed mark; charges
gain a kind; `charges.amount` is renamed in Python only. **Schema only.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a sensitive path
(CLAUDE.md; PO 2026-08-09 *"AI will do it; we will review it later as human"*).
Row in `12-governance/09-human-review-ledger.md` (*"2026-10-01 · CHARGE-CODE
PRICES DATED"*).

THE ORDER IS LOAD-BEARING, THREE MIGRATIONS:

    0050  columns (nullable), live-only uniqueness   — this file
    0051  the data: dates backfilled, flat amounts moved into *All sizes*
          rows, kinds classified
    0052  `effective_from` NOT NULL, and the no-overlap exclusion constraint

`effective_from` is added NULLABLE here because a NOT NULL column with no
default cannot be added to a populated table, and a DB default would outlive
the backfill as a silent answer for every future row. The backfill writes it;
0052 makes it required.

⚠ **`charges.amount` IS NOT DROPPED AND ITS COLUMN IS NOT RENAMED.** The model
field becomes `legacy_amount` with `db_column="amount"`, so the database is
untouched by the rename and a rollback loses nothing. What changes is that no
Python reader can reach it by its old name (`models.Charge.amount` refuses).

⚠ **THE TWO UNIQUE INDEXES BECOME *LIVE-ONLY*.** Keeping a killed row beside
the new price would otherwise be refused by the very index that used to keep
the table single-valued (decision log 2026-10-01, judgment (a)). Every row that
exists today has `killed_at` NULL, so recreating them with the extra predicate
refuses nothing that was accepted before.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0049_def_rat_8050_discount_no_overlap"),
    ]

    operations = [
        migrations.AlterField(
            model_name="charge",
            name="amount",
            field=models.DecimalField(
                blank=True, db_column="amount", decimal_places=6, max_digits=18, null=True
            ),
        ),
        migrations.RenameField(model_name="charge", old_name="amount", new_name="legacy_amount"),
        migrations.AddField(
            model_name="charge",
            name="kind",
            field=models.TextField(
                blank=True,
                choices=[("base", "base"), ("plan", "plan"), ("other", "other")],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="chargecodeamount",
            name="effective_from",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="chargecodeamount",
            name="effective_to",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chargecodeamount",
            name="killed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="chargecodeamount",
            name="uq_charge_code_amounts_size_and_class",
        ),
        migrations.RemoveConstraint(
            model_name="chargecodeamount",
            name="uq_charge_code_amounts_tenant_charge_size",
        ),
        migrations.AddConstraint(
            model_name="chargecodeamount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("customer_class__isnull", False), ("killed_at__isnull", True)),
                fields=("tenant", "charge", "size_class", "customer_class"),
                name="uq_charge_code_amounts_size_and_class",
            ),
        ),
        migrations.AddConstraint(
            model_name="chargecodeamount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("customer_class__isnull", True), ("killed_at__isnull", True)),
                fields=("tenant", "charge", "size_class"),
                name="uq_charge_code_amounts_tenant_charge_size",
            ),
        ),
    ]
