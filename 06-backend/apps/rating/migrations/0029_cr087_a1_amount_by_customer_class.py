# ── Trace ──────────────────────────────────────────────
# Change:  CR-087 task A1 / PRB-01 — `charge_code_amounts` gains a customer
#          class, inside the unique key.
# Rules:   BR-RAT-088 (the base lives on the charge code) · BR-RAT-690 (a
#          per-size table IS the flat amount, stated once per size).
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`,
row of 2026-09-08 (`CR-087` A1).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).

**A MONEY TABLE'S UNIQUE KEY MOVES HERE, WHICH IS WHY THIS FILE IS SENSITIVE.**
Until today `charge_code_amounts` was unique on
`(tenant_id, charge_id, size_class)`, so a $45.00 residential connection fee and
an $85.00 commercial one were THE SAME ROW and a utility that charges both had to
keep two charge codes wearing the same name.

⚠ **TWO CONSTRAINTS REPLACE ONE, AND ONE WOULD NOT HAVE WORKED.** PostgreSQL
treats NULLs as **DISTINCT** in a unique index, so a single constraint over all
four columns would have allowed **two every-class rows for one size** — exactly
the duplicate the old three-column key existed to refuse. So the pair:
`uq_charge_code_amounts_size_and_class` covers the rows that NAME a class, and
`uq_charge_code_amounts_tenant_charge_size` — the old name, deliberately kept, so
anything citing it still finds it — covers the rows that do not.

⚠ **NULL IS NOT A CLASS, IT IS EVERY CLASS.** That is what makes this additive:
every row this database already holds keeps pricing exactly what it priced, and
rolling back one migration under-narrows rather than misprices. Nothing is
refunded and no issued bill changes.

**Reversing is safe and it is one migration back.** Rows written with a class
lose the narrowing and fall back to applying to all.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0028_cr081_sewer_volume_basis"),
        ("tenancy", "0043_cr080_thermal_capacity_basis"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="chargecodeamount",
            name="uq_charge_code_amounts_tenant_charge_size",
        ),
        migrations.AddField(
            model_name="chargecodeamount",
            name="customer_class",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="chargecodeamount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("customer_class__isnull", False)),
                fields=("tenant", "charge", "size_class", "customer_class"),
                name="uq_charge_code_amounts_size_and_class",
            ),
        ),
        migrations.AddConstraint(
            model_name="chargecodeamount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("customer_class__isnull", True)),
                fields=("tenant", "charge", "size_class"),
                name="uq_charge_code_amounts_tenant_charge_size",
            ),
        ),
    ]
