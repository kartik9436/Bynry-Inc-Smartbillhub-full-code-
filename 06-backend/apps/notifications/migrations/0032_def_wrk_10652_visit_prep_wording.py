"""notifications 0032 — the visit messages carry the job's preparation text, and
*Work order logged* is planted on every existing utility.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-29 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

`DEF-WRK-10652` (PO 2026-10-29, *"1A 2A 3B 4A, start"*):

1. **Plant** `service_work_order_logged` and `sms_work_order_logged` (ruling 1A)
   through the insert-missing seeder (`seed_templates.ensure_seeded`, `0024`'s
   precedent). New utilities get them at provisioning; `work_customer_messages`
   also plants them at queue time, so a tenant this misses is planted on use.
2. **Republish** `service_appointment`, `service_visit_moved` and
   `sms_visit_booked` with the `{prep_instructions}` paragraph (ruling 3B) — but
   ONLY where the published, undated version is still BYTE-FOR-BYTE the wording
   the platform seeded (`0025`'s posture, ruled there by the PO: *"never
   overwrite a utility's edit"*). A copy that differs by one byte is the
   utility's own and is left alone and LOGGED; the token is offered on its
   palette and they may add it themselves.

The old bodies are FROZEN here rather than imported (`assets/0011`'s reason: a
migration keeps doing what it did when the seed later moves); a test pins the
NEW bodies to `seed_templates` today.

IDEMPOTENT — after one pass the published body is the new wording, so it no
longer matches and a second pass writes nothing; the seeder is insert-missing.

ROLLBACK (`migrate notifications 0031`) — FORWARD-ONLY, and said so: the old
wording is the archived version directly below the new one and can be
republished from Settings → Templates; a published version may already be pinned
on a queued message (BR-BIL-026), so the reverse deletes nothing.

RLS AND FAILURE — every read and write happens with `app.tenant_id` set to that
tenant, each tenant in its own SAVEPOINT (hard-won law 14).
"""

import logging

from django.db import migrations, transaction
from django.utils import timezone

logger = logging.getLogger("smartbillhub.notifications")

JOB = "notifications 0032 · DEF-WRK-10652 · PO 2026-10-29 '1A 2A 3B 4A'"
AUDIT_ENTITY = "notification_template_version"
AUDIT_PUBLISHED = "template.published"
NO_TENANT = "00000000-0000-0000-0000-000000000000"
PLANT = ("service_work_order_logged", "sms_work_order_logged")

OLD_APPOINTMENT = """Hi {first_name},

We have booked a visit to {service_address}.

What we are doing {work_type}
Date {appointment_date}
Arrival window {appointment_window}

Please make sure we can get to the meter — an unlocked gate and nothing parked over
the lid is usually all it takes.

If that time does not work for you, call {support_phone} and we will move it.

{utility_name}"""

NEW_APPOINTMENT = """Hi {first_name},

We have booked a visit to {service_address}.

What we are doing {work_type}
Date {appointment_date}
Arrival window {appointment_window}

Before we arrive: {prep_instructions}

If that time does not work for you, call {support_phone} and we will move it.

{utility_name}"""

OLD_MOVED = """Hi {first_name},

Your visit to {service_address} has a new time.

What we are doing {work_type}
Date {appointment_date}
Arrival window {appointment_window}

If the new time does not work for you, call {support_phone} and we will move it.

{utility_name}"""

NEW_MOVED = """Hi {first_name},

Your visit to {service_address} has a new time.

What we are doing {work_type}
Date {appointment_date}
Arrival window {appointment_window}

Before we arrive: {prep_instructions}

If the new time does not work for you, call {support_phone} and we will move it.

{utility_name}"""

OLD_SMS_BOOKED = (
    "{utility_name}: your visit is booked for {appointment_date}, "
    "{appointment_window}. To change it call {support_phone}."
)
NEW_SMS_BOOKED = OLD_SMS_BOOKED + "\n\n{prep_instructions}"

#: code → (the seeded body this replaces, the new body)
REWORD = {
    "service_appointment": (OLD_APPOINTMENT, NEW_APPOINTMENT),
    "service_visit_moved": (OLD_MOVED, NEW_MOVED),
    "sms_visit_booked": (OLD_SMS_BOOKED, NEW_SMS_BOOKED),
}


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    """Hard rule 1. On sqlite there is no RLS and no `set_config`."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _reword_tenant(apps, tenant_id, now):
    Template = apps.get_model("notifications", "NotificationTemplate")
    Version = apps.get_model("notifications", "NotificationTemplateVersion")
    AuditLog = apps.get_model("audit", "AuditLog")
    moved = left = 0
    for code, (old_body, new_body) in REWORD.items():
        for template in Template.objects.filter(tenant_id=tenant_id, code=code):
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
            if live is None or live.body == new_body:
                continue
            if live.body != old_body:
                left += 1
                logger.info(
                    "notifications 0032: tenant %s %s/%s/%s v%s is the utility's own "
                    "wording and is left exactly alone",
                    tenant_id, template.code, template.category, template.language, live.version,
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
    return moved, left


def forward(apps, schema_editor):
    from apps.notifications import seed_templates
    from core import tenancy as core_tenancy

    connection = schema_editor.connection
    now = timezone.now()
    moved = left = planted = 0
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        try:
            # ⚠ THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE (law 14).
            with transaction.atomic():
                m, lft = _reword_tenant(apps, tenant_id, now)
                moved, left = moved + m, left + lft
            with core_tenancy.tenant_context(tenant_id):
                with transaction.atomic():
                    for code in PLANT:
                        seed_templates.ensure_seeded(code)
                    planted += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0032: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint), and the queue-time seeder plants the "
                "logged wording on first use",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "notifications 0032: %d visit wording(s) given the preparation paragraph; %d edited "
        "copy(ies) left alone; logged wording checked on %d utility(ies)",
        moved, left, planted,
    )


def forward_only(apps, schema_editor):
    logger.info(
        "notifications 0032 reverse: nothing removed — the old visit wording is the archived "
        "version below the new one and can be republished from Settings → Templates"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0031_def_not_10649_service_state_wording"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, forward_only),
    ]
