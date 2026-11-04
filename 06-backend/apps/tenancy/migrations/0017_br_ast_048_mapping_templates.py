# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W3-T8 — BR-AST-048 (PO 2026-08-22): seeded default
#           mapping templates, tenant copy-on-write. Screens: SET-04
#           (import_mappings list) · WFL-01.*.1 ("Header row recognised as …")
# Rules:    BR-AST-048 · DEF-512 (the table's own docstring said "saved ETL
#           column mappings" and no column could hold one — closed here)
# Tests:    06-backend/tests/test_cr028_mapping_templates.py
# Impacts:  apps/tenancy/services.py (handler + seed) · apps/metering/
#           import_runs.py (recognition + save-template)
# ───────────────────────────────────────────────────────
"""tenancy 0017 — the ImportMapping content columns (BR-AST-048 / DEF-512).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-22 under the PO ruling of 2026-08-09.

Three nullable columns: `target` (which runner target a template maps),
`mapping` (the saved column map itself — the column DEF-512 reported missing),
`last_used_at` (BR-AST-048's most-recently-used tie-breaker). All NULLable so
every legacy row stays lawful: a pre-BR-AST-048 row simply names no target and
is never auto-recognised. No backfill; rollback is a clean drop.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0016_br_rat_081_service_metered"),
    ]

    operations = [
        migrations.AddField(
            model_name="importmapping",
            name="target",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importmapping",
            name="mapping",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importmapping",
            name="last_used_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028/BR-AST-048@2026-08-22 (04-docs/05-modules/05-assets/02-business-rules.md) · AST-W3-T8
# generated: 2026-08-22 by the CR-028 AST-W3 lane
# checklist: A✔ B✔ C✔ D=deferred(the surfaces land in the same lane) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: migration-guard · makemigrations --check · test_cr028_mapping_templates.py
# exceptions: none — three nullable columns, no backfill, rollback is a clean drop
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
