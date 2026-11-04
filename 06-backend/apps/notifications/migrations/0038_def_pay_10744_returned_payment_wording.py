# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10744 — the returned-payment (NSF) email said "Nothing has
#           changed on your account" after a bounce; the printed letter was blank
# Ruling:   PO 2026-10-30, decision log *"Payments audit by level (L1/L2/L3, 31
#           issues): what is fixed, set up, skipped"* — L2-04 under *"Rest we
#           will fix"* (a proper NSF email and letter)
# Rules:    BR-BIL-026 (an edit is a NEW append-only version; one ordinary
#           published version per variant — the previous one is archived) ·
#           A19 rule 6 (every template version is audit-logged) · CLAUDE.md
#           hard rule 1 (tenant scoping) · hard-won law 14 (a per-tenant
#           savepoint)
# Tests:    tests/test_def_pay_10744_returned_payment_letter.py
# ───────────────────────────────────────────────────────
"""notifications 0038 — the returned-payment email tells the truth, and the letter has words.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-30 (lane PAY-G) under the PO ruling of 2026-08-09.

WHAT IT DOES — `0028`'s pattern, for two classes
────────────────────────────────────────────────────────────────────────────
1. For every utility whose PUBLISHED, undated `email_payment_failed` `default`
   version is still byte-for-byte the wording the platform seeded (subject AND
   body — the one that said *"Nothing has changed on your account"*), it
   publishes ONE new version — the `en` wording of `payment_returned_wording` —
   and archives the old one, exactly as a System Admin pressing Publish would.
2. It plants what is missing for BOTH classes (`seed_templates.ensure_seeded`,
   insert-missing): the printed letter's `default` variant, which was never
   seeded (`DEF-2473` left it blank), and the language variants of both.

A COPY THAT DIFFERS BY ONE BYTE IS THE UTILITY'S OWN WORDING AND IS LEFT ALONE.

IDEMPOTENT — after one pass the published body is the new wording, so it no
longer matches, and the seeding is insert-missing.

ROLLBACK — FORWARD-ONLY, and said so. The old email wording is the archived
version directly below ours and a System Admin can republish it from Settings →
Templates in one action; the letter's variants can be archived the same way.
"""

import logging

from django.db import migrations, transaction
from django.utils import timezone

logger = logging.getLogger("smartbillhub.notifications")

JOB = "notifications 0038 · DEF-PAY-10744 · PO 2026-10-30 returned-payment email and letter"
AUDIT_ENTITY = "notification_template_version"
AUDIT_PUBLISHED = "template.published"
EMAIL_CODE = "email_payment_failed"
LETTER_CODE = "payment_failed_letter"
SEEDED_VARIANT = "default"

#: The nil sentinel, never `''` (assets/0003, OQ-354).
NO_TENANT = "00000000-0000-0000-0000-000000000000"

#: FROZEN here rather than imported (`assets/0011`'s reason: a migration must
#: keep doing what it did when the seed later moves). A test pins NEW to
#: `payment_returned_wording` today.
OLD_SUBJECT = "Your {utility_name} payment of {amount} did not go through"
OLD_BODY = """Hi {first_name},

Your payment of {amount} on {date} did not go through.

Method {method}
What we were told {failure_reason}

Nothing has changed on your account. Your balance is {balance} and your due date is
still {due_date}.

You can try again at {utility_website}, or call {support_phone} if you would like a
hand or would rather pay a different way.

{utility_name}"""

NEW_SUBJECT = "Your {utility_name} payment of {amount} was returned by your bank"
NEW_BODY = (
    "Hi {first_name},\n\n"
    "Your payment of {amount} on {date} was returned by your bank, so it has been "
    "taken off your account.\n\n"
    "Check or reference {confirmation}\n\n"
    "Bank memo {bank_memo}\n\n"
    "Returned payment fee {nsf_fee}\n\n"
    "Your balance is now {balance}.\n\n"
    "Please pay by {due_date}.\n\n"
    "You can pay at {utility_website}, or call {support_phone} to pay another way.\n\n"
    "{utility_name}"
)


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
        tenant_id=tenant_id, code=EMAIL_CODE, category=SEEDED_VARIANT, language=SEEDED_VARIANT
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
    if live is None or live.body != OLD_BODY or (live.subject or "") != OLD_SUBJECT:
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
        subject=NEW_SUBJECT,
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
            "code": EMAIL_CODE,
            "category": template.category,
            "language": template.language,
            "version": row.version,
            "status": "published",
            "auto_archived_versions": [live.version],
            "changed_fields": ["subject", "body"],
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
                    seed_templates.ensure_seeded(EMAIL_CODE)
                    seed_templates.ensure_seeded(LETTER_CODE)
                    planted += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0038: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "notifications 0038: %d returned-payment email(s) given the new wording; letter and "
        "language variants checked on %d utility(ies)",
        moved,
        planted,
    )


def forward_only(apps, schema_editor):
    logger.info(
        "notifications 0038 reverse: nothing removed — the old returned-payment wording is the "
        "archived version below the new one and can be republished from Settings → Templates"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0037_cr199_template_body_format"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, forward_only),
    ]
