"""notifications 0031 — the *Service disconnected* and *Service restored*
templates (email + SMS) planted on every existing utility.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-29 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

`DEF-NOT-10649`, PO 2026-10-29, *"1 A, 2 A, 3 A, 4 A"*: a cut and a
restoration tell the customer, and (4A) each utility edits the default wording
on Settings → Templates. New utilities get the four classes at provisioning
(`seed_templates.seed_notice_templates`); this plants them on the ones that
already exist, so they are on the Templates screen before the first cut rather
than appearing at it. The SAME insert-missing seeder per tenant, under its own
`app.tenant_id` and its own SAVEPOINT (hard-won law 14) — `0023`'s shape. A
variant a utility already published is never touched; the queue-time
`customer_events._ensure_service_state_wording` covers any tenant this misses.

No schema change. Rolling back leaves the planted rows (ordinary, editable
template rows).
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger("smartbillhub.notifications")

CODES = (
    "service_disconnected_guide",
    "sms_service_disconnected",
    "service_restored",
    "sms_service_restored",
)


def forward(apps, schema_editor):
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
                "notifications 0031: tenant %s could not be seeded; the queue-time "
                "ensure_seeded will plant it on first use",
                tenant_id,
            )
    logger.info("notifications 0031: service-state templates checked on %d utility(ies)", planted)


def forward_only(apps, schema_editor):
    """Nothing to undo: the planted rows are ordinary, editable templates."""


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0030_def_bil_10531_bill_email_link_wording"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, forward_only),
    ]
