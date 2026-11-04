# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10531 — the bill-ready email said "it is attached to this
#           email" and nothing was attached
# Ruling:   PO 2026-10-22, decision log *"Bill email sends a link instead of the
#           PDF"* and *"The bill email's link opens the bill PDF directly, with
#           no sign-in"* (*"b direct PDF link"*)
# Rules:    BR-BIL-026 (an edit is a NEW append-only version; one ordinary
#           published version per variant — the previous one is archived) ·
#           A19 rule 6 (every template version is audit-logged) · CLAUDE.md
#           hard rule 1 (tenant scoping) · hard-won law 14 (a per-tenant
#           savepoint, proved on PostgreSQL)
# Tests:    tests/test_def_bil_10531_bill_link.py ·
#           tests/test_def_bil_10531_bill_link_pg.py
# ───────────────────────────────────────────────────────
"""notifications 0030 — the bill emails carry a link instead of promising an attachment.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09.

WHAT IT DOES
────────────────────────────────────────────────────────────────────────────
1. For every utility whose PUBLISHED, undated `email_bill_ready` or
   `email_corrected_bill` `default` version is still byte-for-byte the wording
   the platform seeded (subject AND body), it publishes ONE new version — the
   `en` wording of `bill_email_wording`, with the link line in place of the
   attachment sentence — and archives the old one, exactly as a System Admin
   pressing Publish would (`0026`'s pattern, two classes).
2. It plants the language variants beside each (`seed_templates
   .seed_language_variants`, insert-missing — `0028`'s pattern).

A COPY THAT DIFFERS BY ONE BYTE IS THE UTILITY'S OWN WORDING AND IS LEFT ALONE.
Its tokens still fill: the catalogue now allows `{bill_link}` and
`{link_expires_on}`, so a utility can add the link line itself.

IDEMPOTENT — after one pass the published body is the new wording, so it no
longer matches, and the variants are insert-missing.

ROLLBACK — FORWARD-ONLY, and said so. The old wording is the archived version
directly below ours and a System Admin can republish it from Settings →
Templates in one action.
"""

import logging

from django.db import migrations, transaction
from django.utils import timezone

logger = logging.getLogger("smartbillhub.notifications")

JOB = "notifications 0030 · DEF-BIL-10531 · PO 2026-10-22 bill email link"
AUDIT_ENTITY = "notification_template_version"
AUDIT_PUBLISHED = "template.published"
SEEDED_VARIANT = "default"

#: The nil sentinel, never `''` (assets/0003, OQ-354).
NO_TENANT = "00000000-0000-0000-0000-000000000000"

#: FROZEN here rather than imported (`assets/0011`'s reason: a migration must
#: keep doing what it did when the seed later moves). A test pins each NEW body
#: to `bill_email_wording` today and each OLD body to the 2026-08-15 seed.
BILL_READY_SUBJECT = "Your {utility_name} bill is ready — {total_due} due {due_date}"

BILL_READY_OLD = """Hi {first_name},

Your bill for {service_address} is ready, and it is attached to this email.

Bill {bill_no}, billed {bill_date}
Service period {period_start} to {period_end}

Previous balance {prev_balance}
Payments received {payments}
Current charges {current_charges}
Total due {total_due} by {due_date}

You can view it or pay at {utility_website}.

If anything on it looks wrong, call {support_phone} or write to {support_email}. We
would much rather explain a charge than have you wonder about it.

{utility_name}"""

BILL_READY_NEW = """Hi {first_name},

Your bill for {service_address} is ready.

Bill {bill_no}, billed {bill_date}
Service period {period_start} to {period_end}

Previous balance {prev_balance}
Payments received {payments}
Current charges {current_charges}
Total due {total_due} by {due_date}

View or download your bill: {bill_link}
This link works until {link_expires_on}.

You can view it or pay at {utility_website}.

If anything on it looks wrong, call {support_phone} or write to {support_email}. We
would much rather explain a charge than have you wonder about it.

{utility_name}"""

CORRECTED_SUBJECT = "We have corrected your {utility_name} bill {bill_no}"

CORRECTED_OLD = """Hi {first_name},

We have corrected bill {bill_no} for {service_address}. The corrected bill is
attached and it replaces the one we sent you.

What changed: {correction_reason}
Original total {original_total}
Corrected total {total_due}

Your due date is still {due_date}. If you pay by autopay, we will collect the
corrected amount.

Sorry for the confusion. If the new figure still does not look right, call
{support_phone} and we will go through the reads with you.

{utility_name}"""

CORRECTED_NEW = """Hi {first_name},

We have corrected bill {bill_no} for {service_address}. The corrected bill
replaces the one we sent you.

View or download the corrected bill: {bill_link}
This link works until {link_expires_on}.

What changed: {correction_reason}
Original total {original_total}
Corrected total {total_due}

Your due date is still {due_date}. If you pay by autopay, we will collect the
corrected amount.

Sorry for the confusion. If the new figure still does not look right, call
{support_phone} and we will go through the reads with you.

{utility_name}"""

#: code → (subject, old body, new body)
CHANGES = {
    "email_bill_ready": (BILL_READY_SUBJECT, BILL_READY_OLD, BILL_READY_NEW),
    "email_corrected_bill": (CORRECTED_SUBJECT, CORRECTED_OLD, CORRECTED_NEW),
}


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    """Hard rule 1. On sqlite there is no RLS and no `set_config`."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def republish(apps, tenant_id, now, code):
    """1 for a moved default, 0 for an edited or absent one."""
    subject, old_body, new_body = CHANGES[code]
    Template = apps.get_model("notifications", "NotificationTemplate")
    Version = apps.get_model("notifications", "NotificationTemplateVersion")
    AuditLog = apps.get_model("audit", "AuditLog")
    template = Template.objects.filter(
        tenant_id=tenant_id, code=code, category=SEEDED_VARIANT, language=SEEDED_VARIANT
    ).first()
    if template is None:
        return 0
    live = (
        Version.objects.filter(
            tenant_id=tenant_id, template=template, status="published", effective_from__isnull=True
        )
        .order_by("-version")
        .first()
    )
    if live is None or live.body != old_body or (live.subject or "") != subject:
        return 0
    highest = (
        Version.objects.filter(tenant_id=tenant_id, template=template)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
    )
    live.status = "archived"
    live.archived_at = now
    live.save(update_fields=["status", "archived_at", "updated_at"])
    row = Version.objects.create(
        tenant_id=tenant_id,
        template=template,
        version=int(highest) + 1,
        status="published",
        subject=live.subject,
        preheader=live.preheader,
        body=new_body,
        effective_from=None,
        created_by=None,
        published_by=None,
        published_at=now,
    )
    AuditLog.objects.create(
        tenant_id=tenant_id,
        actor_user_id=None,  # an unnamed system job, named in `after`
        action=AUDIT_PUBLISHED,
        entity_type=AUDIT_ENTITY,
        entity_id=row.pk,
        before=None,
        after={
            "code": code,
            "category": template.category,
            "language": template.language,
            "version": row.version,
            "status": "published",
            "auto_archived_versions": [live.version],
            "changed_fields": ["body"],
            "affects": "future renders only",
            "source": JOB,
        },
    )
    return 1


def forward(apps, schema_editor):
    from apps.notifications import seed_templates
    from core import tenancy as core_tenancy

    connection = schema_editor.connection
    moved = planted = 0
    now = timezone.now()
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        try:
            # ⚠ THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE (law 14).
            with transaction.atomic():
                for code in CHANGES:
                    moved += republish(apps, tenant_id, now, code)
            with core_tenancy.tenant_context(tenant_id):
                with transaction.atomic():
                    for code in CHANGES:
                        seed_templates.seed_language_variants(code)
                    planted += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0030: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "notifications 0030: %d bill email(s) given the link wording; language variants "
        "checked on %d utility(ies)",
        moved,
        planted,
    )


def forward_only(apps, schema_editor):
    logger.info(
        "notifications 0030 reverse: nothing removed — the old bill email wording is the "
        "archived version below the new one and can be republished from Settings → Templates"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0029_def_bil_4454_correction_reason_wording"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, forward_only),
    ]
