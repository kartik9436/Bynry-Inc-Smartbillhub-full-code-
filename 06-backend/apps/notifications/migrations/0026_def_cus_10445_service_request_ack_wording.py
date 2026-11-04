# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10445 — the service request acknowledgement names no
#           service type and no target date
# Ruling:   PO 2026-10-22, decision log *"Service request acknowledgement:
#           target date, default 15 days, service type name"*
# Rules:    BR-BIL-026 (an edit is a NEW append-only version; one ordinary
#           published version per variant — the previous one is archived) ·
#           A19 rule 6 (every template version is audit-logged) · CLAUDE.md
#           hard rule 1 (tenant scoping) · hard-won law 14 (a per-tenant
#           savepoint, proved on PostgreSQL)
# Tests:    tests/test_def_cus_10445_service_request_acknowledgement.py
# ───────────────────────────────────────────────────────
"""notifications 0026 — the acknowledgement says what was asked for, and when.

RENUMBERED 2026-10-22 at merge (lane MERGE-EMAILS): written as `0024` beside
CR-189's own `0024`; applied by no shared database, so it moved to `0026`, after
`0025_cr190_welcome_first_bill_wording`. Nothing else in it changed.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09.

WHAT IT DOES, IN ONE SENTENCE
────────────────────────────────────────────────────────────────────────────
For every utility whose PUBLISHED, undated `service_request_acknowledgement` or
`service_request_acknowledgement_fee` version is still byte-for-byte the
wording the platform seeded (subject AND body), it publishes ONE new version
naming `{service_type}` and `{target_date}` and archives the old one, exactly
as a System Admin pressing Publish would — `0025`'s pattern, two classes.

A COPY THAT DIFFERS BY ONE BYTE IS THE UTILITY'S OWN WORDING AND IS LEFT ALONE
────────────────────────────────────────────────────────────────────────────
There is no "touched" column on a template version, so the content is the only
evidence. An edited copy — the utility that wrote *"We received your request
for {service_type} on …"* is one — is never rewritten; it is logged, and its
tokens now fill because the class allows them and the caller passes them.

Only the `default` category and language variant is seeded, so only that is
compared; a variant a utility made itself was never ours to change.

IDEMPOTENT — after one pass the published body is the new wording, so it no
longer matches and a second pass writes nothing.

ROLLBACK (`migrate notifications 0025`) — FORWARD-ONLY, and said so. The old
wording is the archived version directly below ours and a System Admin can
republish it from Settings → Templates in one action; a reverse that deleted a
PUBLISHED version would be refused by `0006`'s trigger once any acknowledgement
had been queued against it.
"""

import logging

from django.db import migrations, transaction
from django.utils import timezone

logger = logging.getLogger("smartbillhub.notifications")

JOB = "notifications 0026 · DEF-CUS-10445 · PO 2026-10-22 service type and target date"
AUDIT_ENTITY = "notification_template_version"
AUDIT_PUBLISHED = "template.published"

#: The nil sentinel, never `''` (assets/0003, OQ-354).
NO_TENANT = "00000000-0000-0000-0000-000000000000"

#: FROZEN here rather than imported (`assets/0011`'s reason: a migration must
#: keep doing what it did when the seed later moves). A test pins each NEW body
#: to `seed_templates` today.
SUBJECT = "We have your request {request_no}"

OLD_ACK = """Thank you, {applicant_name}.

We have your request for service at {service_address}. Its number is {request_no} —
please quote it when you call us.

Nothing is charged for making a request. We will look at it and come back to you,
and if we need anything more from you we will ask.

Questions? Call {support_phone} or email {support_email}.

{utility_name}"""

NEW_ACK = """Thank you, {applicant_name}.

We have your request for {service_type} at {service_address}. Its number is
{request_no} — please quote it when you call us.

Our target date for it is {target_date}.

Nothing is charged for making a request. We will look at it and come back to you,
and if we need anything more from you we will ask.

Questions? Call {support_phone} or email {support_email}.

{utility_name}"""

OLD_ACK_FEE = """Thank you, {applicant_name}.

We have your request for service at {service_address}. Its number is {request_no} —
please quote it when you call us.

You paid {fee_amount} by {fee_method}. Your receipt number is {receipt_no}. Please
keep this message with it.

We will look at your request and come back to you, and if we need anything more
from you we will ask.

Questions? Call {support_phone} or email {support_email}.

{utility_name}"""

NEW_ACK_FEE = """Thank you, {applicant_name}.

We have your request for {service_type} at {service_address}. Its number is
{request_no} — please quote it when you call us.

Our target date for it is {target_date}.

You paid {fee_amount} by {fee_method}. Your receipt number is {receipt_no}. Please
keep this message with it.

We will look at your request and come back to you, and if we need anything more
from you we will ask.

Questions? Call {support_phone} or email {support_email}.

{utility_name}"""

#: code → (old body, new body)
WORDING = {
    "service_request_acknowledgement": (OLD_ACK, NEW_ACK),
    "service_request_acknowledgement_fee": (OLD_ACK_FEE, NEW_ACK_FEE),
}

SEEDED_VARIANT = "default"


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    """Hard rule 1. On sqlite there is no RLS and no `set_config`."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def republish_unedited(apps, schema_editor):
    Template = apps.get_model("notifications", "NotificationTemplate")
    Version = apps.get_model("notifications", "NotificationTemplateVersion")
    AuditLog = apps.get_model("audit", "AuditLog")
    connection = schema_editor.connection
    moved = left = 0
    now = timezone.now()
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        try:
            # ⚠ THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE (law 14).
            with transaction.atomic():
                templates = Template.objects.filter(
                    tenant_id=tenant_id,
                    code__in=list(WORDING),
                    category=SEEDED_VARIANT,
                    language=SEEDED_VARIANT,
                )
                for template in templates:
                    old_body, new_body = WORDING[template.code]
                    live = (
                        Version.objects.filter(
                            tenant_id=tenant_id,
                            template=template,
                            status="published",
                            effective_from__isnull=True,
                        )
                        .order_by("-version")
                        .first()
                    )
                    if live is None:
                        continue
                    if live.body != old_body or (live.subject or "") != SUBJECT:
                        if live.body != new_body:
                            left += 1
                            logger.info(
                                "notifications 0026: tenant %s %s v%s is the utility's own "
                                "wording and is left exactly alone",
                                tenant_id,
                                template.code,
                                live.version,
                            )
                        continue
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
                            "code": template.code,
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
                    moved += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0026: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "notifications 0026: %d acknowledgement(s) given the service-type and target-date "
        "wording; %d edited copy(ies) left alone",
        moved,
        left,
    )


def forward_only(apps, schema_editor):
    logger.info(
        "notifications 0026 reverse: nothing removed — the old acknowledgement wording is "
        "the archived version below the new one and can be republished from Settings → "
        "Templates"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0025_cr190_welcome_first_bill_wording"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(republish_unedited, forward_only),
    ]
