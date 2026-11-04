"""notifications 0024 — the portal email-change templates on every existing utility.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

`CR-189-BRC10` (PO 2026-10-22): `portal_email_change_code` (the code to the new
address) and `portal_email_changed_notice` (the notice to the old one), plus the
wording `portal_enrolment_code` never had (`DEF-CWP-10402`), all in the
Account access category, seeded natively in every written language. New
utilities get them at provisioning (`seed_templates.seed_notice_templates`);
this plants them on the ones that already exist through the SAME insert-missing
seeder (`seed_templates.ensure_seeded`), one tenant at a time under its own
`app.tenant_id` and SAVEPOINT (hard-won law 14). A variant a utility already
published is never touched. The portal also calls `ensure_seeded` at queue
time, so a tenant this misses is planted on first use.

**DEPENDENCY RE-POINTED AT MERGE (2026-10-22, lane MERGE-ACCESS).** Written on
a tip whose leaf was `0022`; it now follows `0023_cr188_priority_and_account_access`,
the ONE 0023 left once PORTAL-RESET's own 0023 folded into it, so the graph has
a single leaf. It adds no column and no table, so the order has no schema
effect; the seeder writes audit rows, hence the audit dependency.

Rollback: a no-op. A published version may already be pinned on a queued
email (BR-BIL-026), so deleting it would orphan the pin.
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger("smartbillhub.notifications")

CODES = ("portal_enrolment_code", "portal_email_change_code", "portal_email_changed_notice")


def plant(apps, schema_editor):
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
                "notifications 0024: tenant %s could not be seeded; the queue-time "
                "ensure_seeded will plant it on first use",
                tenant_id,
            )
    logger.info("notifications 0024: portal email-change templates checked on %d utility(ies)", planted)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0023_cr188_priority_and_account_access"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(plant, migrations.RunPython.noop),
    ]
