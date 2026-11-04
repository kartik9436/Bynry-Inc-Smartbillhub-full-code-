# ── Trace ──────────────────────────────────────────────
# Story:    CR-028 AST-W2-T1 (the schema half of B16 — seven tabs · valuation ·
#           certification)   Screens: S49–S55 (registry + detail + flows),
#           AST-01.inventory / AST-01.lifecycle (the tabs these columns feed)
# Rules:    BR-AST-047 (valuation lives on the device record, optional method &
#           cost, life CALCULABLE, book value computed & treatment RECORDED —
#           and NO finance link now; future linkage is a new CR, note kept by
#           PO instruction) · CR-028 D3/D4/D5/D10 (2026-08-22, verbatim in
#           12-governance/11-change-requests.md) · CLAUDE.md rule 2 (money
#           STORED 4dp, displayed 2) · BR-AST-014 (capture-only, no EAM depth)
# Tests:    06-backend/tests/test_w1_models.py (column halves) ·
#           tests/test_cr028_valuation.py (AST-W4-T6, ratified figures)
# Impacts:  apps/assets/services (create/update/retire payloads) · selectors
#           (detail panels, lifecycle derivations) · sample_data (W0 seed) ·
#           the three CR-028 import targets (CERT_DUE · WARRANTY_END ·
#           SUPPLIER · COST · EXPORT_KW columns land here)
# ───────────────────────────────────────────────────────
"""assets 0007 — CR-028's valuation & certification columns (BR-AST-047).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-22 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

WHAT THIS IS AND, LOUDLY, WHAT IT IS NOT
------------------------------------------
Nine nullable columns and nothing else: no engine, no journal, no GL account
anywhere in this module. The PO ruled the whole valuation set onto the DEVICE
RECORD (*"we can have buy value and present value - but dont link it to
finance yet; we keep everything on devices only for time being"*) and ruled
retire to *"calculate Book value and notify what to do with book value"* — so
`book_value_amount` + `book_value_treatment` are a RECORD of a decision made
at retirement, computed and shown, never posted. Only the ledger posting
service writes journal lines (hard rule 5), and this migration gives it
nothing to write.

Every column is NULLable because every one is OPTIONAL by the same ruling —
a meter with no purchase cost is lawful forever; the surfaces simply show "—"
and the forecast skips it. No backfill, no defaults beyond NULL, so the
migration is instant on any row count and its rollback (drop nine columns) is
total.

Money columns (`purchase_cost` · `book_value_amount` · `asset_maintenance.
cost`) are NUMERIC(18,4) — rule 2's re-signed 4-decimal storage, D10-confirmed
against r10's `Decimal(10,2)` label ("$164.00 on screen either way").
`export_capacity_kw` is NUMERIC(18,6): a physical capacity, not money.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0006_br_ten_057_is_sample"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="supplier",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="asset",
            name="purchase_cost",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="asset",
            name="purchase_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="asset",
            name="depreciation_method",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="asset",
            name="expected_life_years",
            field=models.SmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="asset",
            name="certification_due",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="asset",
            name="export_capacity_kw",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="asset",
            name="book_value_amount",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="asset",
            name="book_value_treatment",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="assetmaintenance",
            name="cost",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028/B16@2026-08-22 (04-docs/02-decisions/16-cr028-assets-design.md §4.8/§6)
# generated: 2026-08-22 by the CR-028 lane (AST-W2-T1)
# checklist: A✔ B✔ C✔ D=deferred(surfaces land in AST-W2/W4/W5) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: migration-guard · test_w1_models column halves
# exceptions: none — nine nullable columns, no backfill, rollback is a clean drop
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
