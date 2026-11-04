# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-4454 — *What changed* had no customer sentence
# Ruling:   PO 2026-10-22, decision log *"Corrected bills: … 'What changed'
#           gets one sentence per reason"*, Q3; our judgments in *"Building
#           the corrected-bill rulings Q1–Q3"*, point 6
# Rules:    BR-NOT-006 (language variants) · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard-won law 14 (a per-tenant savepoint)
# Tests:    tests/test_def_bil_10535_corrected_bill_channels.py
# ───────────────────────────────────────────────────────
"""notifications 0029 — the *What changed* sentences on every existing utility.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

One class per seeded correction reason (`correction_reason_<code>`), its
`default` variant and one per registry language, through the SAME
insert-missing seeder provisioning uses (`seed_templates.ensure_seeded`), one
tenant at a time under its own `app.tenant_id` and SAVEPOINT (law 14). A
variant a utility already published is never touched. New utilities get them
at provisioning (`seed_notice_templates` walks `LANGUAGE_WORDING`).

A utility this misses still gets a sentence: `correction_reason_wording
.sentences_for` falls back to the platform wording when nothing is published.

IDEMPOTENT (insert-missing). ROLLBACK: a no-op — a published version may be
pinned in a queued email's render already, and nothing reads the rows if the
code is rolled back.

⚠ **DEPENDENCY TO RE-POINT AT MERGE** if a sibling lane lands another `0029`:
this adds no column and no table, so the order has no schema effect.
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger("smartbillhub.notifications")


def plant(apps, schema_editor):
    from apps.notifications import correction_reason_wording, seed_templates
    from core import tenancy as core_tenancy

    tenant_ids = list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))
    planted = 0
    for tenant_id in tenant_ids:
        try:
            with core_tenancy.tenant_context(tenant_id):
                with transaction.atomic():  # SAVEPOINT — law 14, not tidiness
                    for code in correction_reason_wording.WORDING:
                        seed_templates.ensure_seeded(code)
                    planted += 1
        except Exception:  # pragma: no cover — logged; the others go on
            logger.exception(
                "notifications 0029: tenant %s could not be seeded; its corrected-bill "
                "email falls back to the platform wording",
                tenant_id,
            )
    logger.info("notifications 0029: What-changed sentences checked on %d utility(ies)", planted)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0028_def_not_10536_move_out_final_wording"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(plant, migrations.RunPython.noop),
    ]
