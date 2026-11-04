"""notifications 0023 — `outbound_messages.priority`, and the Account access
templates planted on every existing utility.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

`CR-188-BRC10`, two PO rulings of 2026-10-22:

1. *"this should be on highest priority in quesu this should be instant email"*
   → `priority` (SMALLINT, default 0; PostgreSQL 16 adds it without a rewrite).
   An account-access email carries `models.PRIORITY_IMMEDIATE` and the cycle
   claims highest priority first.
2. The two staff Account access templates (`staff_user_invite`,
   `staff_password_reset_link`) are seeded *"natively in all 11 languages"* for
   every utility. New utilities get them at provisioning
   (`seed_templates.seed_notice_templates`); this plants them on the ones that
   already exist, by calling the SAME insert-missing seeder per tenant under its
   own `app.tenant_id` and its own SAVEPOINT (hard-won law 14). A variant a
   utility already published is never touched.
3. `DEF-CWP-10381` (PO report 2026-10-22, lane PORTAL-RESET): the customer
   portal's reset-link wording, `portal_password_reset`, is planted the same
   way. That lane wrote its own `0023_def_cwp_10381_portal_password_reset` in
   this exact shape; at merge (2026-10-22, lane MERGE-ACCESS) the code joined
   `CODES` here and the file went, so the graph has one leaf. Neither 0023 had
   been applied to any kept database (the dev database stood at 0022), so
   folding is safe; on a database that had applied this file without the
   third code, the portal's queue-time `ensure_seeded` plants it on first use.

⚠ **IT CALLS LIVE CODE, AND SAYS SO.** `customers/0003` set the precedent. On a
fresh database there are no tenants when this runs, so the loop is empty and
the provisioning seeder does the work; on an existing database it runs once,
against the schema this release ships. Rolling back removes the column and
leaves the planted template rows (they are ordinary, editable template rows).
"""

import logging

from django.db import migrations, models, transaction

logger = logging.getLogger("smartbillhub.notifications")

CODES = ("staff_user_invite", "staff_password_reset_link", "portal_password_reset")
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def plant_account_access(apps, schema_editor):
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
                "notifications 0023: tenant %s could not be seeded; the queue-time "
                "ensure_seeded will plant it on first use",
                tenant_id,
            )
    logger.info("notifications 0023: Account access templates checked on %d utility(ies)", planted)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0022_cr182_high_usage_alert_live"),
        # The seeder writes audit rows (`seed_templates`, rule 7), so the audit
        # table must exist first — the portal lane's dependency, kept at merge.
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="outboundmessage",
            name="priority",
            field=models.SmallIntegerField(default=0),
        ),
        migrations.RunPython(plant_account_access, migrations.RunPython.noop),
    ]
