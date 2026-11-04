# ── Trace ──────────────────────────────────────────────
# Change:   DEF-RAT-8753 · CR-156-BRC10 wave C (charge codes) — the two
#           pricings the PO-approved mock-up draws and wave B could not store:
#           a penalty priced BY CUSTOMER CLASS (images 31, 61, 67, 77) and an
#           amount ENTERED WHEN USED (images 41, 64, 70; CR-010 A2, PO
#           2026-08-17: "actual cost, entered per case").
# Rules:    BR-RAT-1049 (price rows dated, logically killed) · BR-RAT-1053
#           (penalty terms per class) · BR-RAT-1054 (per_case) · hard rule 2
# Tests:    06-backend/tests/test_def_rat_8753_class_terms_and_per_case.py
# ───────────────────────────────────────────────────────
"""rating 0054 — a price row may carry a PERCENT and a MINIMUM for one class.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-01 under the PO ruling of
2026-08-09. Row *"2026-10-01 · CHARGE CODES WAVE C — PENALTY BY CLASS AND
ENTERED WHEN USED"* in 12-governance/09-human-review-ledger.md.

Additive and empty: two nullable columns on `charge_code_amounts` and one
CHECK that a row is an amount row OR a terms row. Every existing row has both
new columns NULL, so it satisfies the CHECK and prices exactly what it priced.
The no-overlap exclusion (`rating/0052`) already covers a terms row, because it
is keyed on (code, size, class) — a class cannot hold an amount and a percent
on the same day.

`per_case` (the fifth `charges.amount_rule` value) needs no schema change: the
column is free text validated by `services.AMOUNT_RULES`.

Reverse: drops the CHECK and the two columns. A per-class percent saved through
the screens is lost on rollback; nothing billed changes (no issued bill reads
this table).
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0053_def_rat_8737_minimum_per_size"),
    ]

    operations = [
        migrations.AddField(
            model_name="chargecodeamount",
            name="percent",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="chargecodeamount",
            name="min_amount",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddConstraint(
            model_name="chargecodeamount",
            constraint=models.CheckConstraint(
                condition=Q(percent__isnull=True) | Q(amount__isnull=True),
                name="ck_charge_code_amounts_amount_or_terms",
            ),
        ),
    ]
