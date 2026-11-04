# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10536 — the move-out final bill email
# Ruling:   PO 2026-10-22, decision log *"Move-out final bill email: sent at
#           completion with the draft figures, at normal priority (no instant
#           email); details and PDF filled in"* (and the judgments entry after
#           it, point 6)
# Rules:    BR-BIL-026 (an edit is a NEW append-only version; one ordinary
#           published version per variant — the previous one is archived) ·
#           A19 rule 6 (every template version is audit-logged) · CLAUDE.md
#           hard rule 1 (tenant scoping) · hard-won law 14 (a per-tenant
#           savepoint, proved on PostgreSQL)
# Tests:    tests/test_def_not_10536_move_out_final_email.py
# ───────────────────────────────────────────────────────
"""notifications 0028 — the move-out email names every closing read, in every language.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09.

WHAT IT DOES
────────────────────────────────────────────────────────────────────────────
1. For every utility whose PUBLISHED, undated `email_move_out_final` `default`
   version is still byte-for-byte the wording the platform seeded (subject AND
   body), it publishes ONE new version — the `en` wording of
   `move_out_wording` — and archives the old one, exactly as a System Admin
   pressing Publish would (`0026`'s pattern).
2. It plants the language variants beside it (`seed_templates
   .seed_language_variants`, insert-missing — `0023`'s pattern).

A COPY THAT DIFFERS BY ONE BYTE IS THE UTILITY'S OWN WORDING AND IS LEFT ALONE.
Its tokens still fill: the catalogue still allows `{final_read}` and `{unit}`.

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

JOB = "notifications 0028 · DEF-NOT-10536 · PO 2026-10-22 move-out final bill email"
AUDIT_ENTITY = "notification_template_version"
AUDIT_PUBLISHED = "template.published"
CODE = "email_move_out_final"
SEEDED_VARIANT = "default"

#: The nil sentinel, never `''` (assets/0003, OQ-354).
NO_TENANT = "00000000-0000-0000-0000-000000000000"

#: FROZEN here rather than imported (`assets/0011`'s reason: a migration must
#: keep doing what it did when the seed later moves). A test pins NEW to
#: `move_out_wording` today.
SUBJECT = "Your final {utility_name} bill for {service_address}"

OLD_BODY = """Hi {first_name},

Your service at {service_address} ended on {service_end_date}. Your final bill is
attached.

Closing meter read {final_read} {unit}
Total due {total_due} by {due_date}

Please make sure we have an address that reaches you, in case anything needs to
come back to you after you have gone.

Questions about the final bill? Call {support_phone}. It is much easier to go
through it with you now than in a few months.

{utility_name}"""

NEW_BODY = """Hi {first_name},

Your service at {service_address} ended on {service_end_date}.

Your final bill is attached. Total due {total_due} by {due_date}.

Closing meter readings:
{final_read}

Please make sure we have an address that reaches you, in case anything needs to come back to you after you have gone.

Questions about your final bill? Call {support_phone}. It is much easier to go through it with you now than in a few months.

{utility_name}"""


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    """Hard rule 1. On sqlite there is no RLS and no `set_config`."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _republish(apps, tenant_id, now):
    """1 for a moved default, 0 for an edited or absent one."""
    Template = apps.get_model("notifications", "NotificationTemplate")
    Version = apps.get_model("notifications", "NotificationTemplateVersion")
    AuditLog = apps.get_model("audit", "AuditLog")
    template = Template.objects.filter(
        tenant_id=tenant_id, code=CODE, category=SEEDED_VARIANT, language=SEEDED_VARIANT
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
    if live is None or live.body != OLD_BODY or (live.subject or "") != SUBJECT:
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
        body=NEW_BODY,
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
            "code": CODE,
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
                moved += _republish(apps, tenant_id, now)
            with core_tenancy.tenant_context(tenant_id):
                with transaction.atomic():
                    seed_templates.seed_language_variants(CODE)
                    planted += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0028: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "notifications 0028: %d move-out email(s) given the new wording; language variants "
        "checked on %d utility(ies)",
        moved,
        planted,
    )


def forward_only(apps, schema_editor):
    logger.info(
        "notifications 0028 reverse: nothing removed — the old move-out wording is the "
        "archived version below the new one and can be republished from Settings → Templates"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0027_def_bil_10530_fail_stuck_bill_emails"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, forward_only),
    ]
