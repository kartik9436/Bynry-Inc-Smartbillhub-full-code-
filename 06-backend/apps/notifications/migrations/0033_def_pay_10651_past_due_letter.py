# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10651 — the automatic past-due reminder; the printed letter
#           for a customer with no email and no SMS consent
# Ruling:   PO 2026-10-29, *"1A 2A 3A 4B, start"* (2A: seed the letter,
#           editable, 11 languages) — decision log entry of that date
# Rules:    BR-NOT-006 (language variants) · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard-won law 14 (a per-tenant savepoint)
# Tests:    tests/test_def_pay_10651_past_due_reminder.py
# ───────────────────────────────────────────────────────
"""notifications 0033 — the printed past-due reminder letter, in every language.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-29 under the PO ruling of 2026-08-09.

New utilities get the `dunning` letter's language variants at provisioning
(`seed_templates.seed_notice_templates`, through `LANGUAGE_WORDING`); this plants
them on the ones that already exist — `0023`'s pattern exactly: the SAME
insert-missing seeder per tenant, under its own `app.tenant_id` and its own
SAVEPOINT. A variant a utility already published is never touched, and the
`default` variant (A13's quoted sentence) is planted only where it is missing.

⚠ **IT CALLS LIVE CODE, AND SAYS SO** (`customers/0003`'s precedent). On a fresh
database there are no tenants and the loop is empty. Rolling back is a no-op:
the planted rows are ordinary, editable template rows.
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger("smartbillhub.notifications")

CODES = ("dunning",)


def plant_past_due_letter(apps, schema_editor):
    from apps.notifications import seed_templates
    from core import tenancy as core_tenancy

    tenant_ids = list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))
    planted = 0
    for tenant_id in tenant_ids:
        try:
            with core_tenancy.tenant_context(tenant_id):
                with transaction.atomic():  # SAVEPOINT — law 14, not tidiness
                    for code in CODES:
                        seed_templates.ensure_seeded(code)
                    planted += 1
        except Exception:  # pragma: no cover — logged; the others go on
            logger.exception(
                "notifications 0033: tenant %s could not be seeded with the past-due letter",
                tenant_id,
            )
    logger.info("notifications 0033: past-due letter checked on %d utility(ies)", planted)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0032_def_wrk_10652_visit_prep_wording"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(plant_past_due_letter, migrations.RunPython.noop),
    ]
