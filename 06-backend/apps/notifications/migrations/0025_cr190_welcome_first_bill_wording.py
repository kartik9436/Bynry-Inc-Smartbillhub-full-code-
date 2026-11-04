# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 MOVEIN-MSG — PO ruling 2026-10-22, verbatim: *"give the
#           activation date , first bill date and no due date required"*.
# Defect:   DEF-NOT-10440
# Rules:    BR-BIL-026 (an edit is a NEW append-only version; one ordinary
#           published version per variant — the previous one is archived) ·
#           A19 rule 6 (every template version is audit-logged) · CLAUDE.md
#           hard rule 1 (tenant scoping) · hard-won law 14 (a per-tenant
#           savepoint, proved on PostgreSQL)
# Tests:    tests/test_cr190_movein_messages.py
# ───────────────────────────────────────────────────────
"""notifications 0025 — the welcome email stops promising a due date.

RENUMBERED 2026-10-22 at merge (lane MERGE-EMAILS): written as `0023` beside
CR-188's own `0023`; applied by no shared database, so it moved to `0025`, after
`0024_cr189_portal_email_update`. Nothing else in it changed.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

WHAT IT DOES, IN ONE SENTENCE
────────────────────────────────────────────────────────────────────────────
For every utility whose PUBLISHED, undated `email_welcome` version is still
byte-for-byte the wording the platform seeded (subject AND body), it publishes
ONE new version with the new wording — *"We will send your first bill on
{first_bill_date}."* as its own paragraph — and archives the old one, exactly as
a System Admin pressing Publish would (`template_service.publish`).

WHY ONLY A BYTE-IDENTICAL COPY — the posture of `0021`, ruled there by the PO
────────────────────────────────────────────────────────────────────────────
There is no "touched" column on a template version, so the CONTENT is the only
evidence: a copy that differs by one byte is the utility's own wording and is
left alone, and LOGGED, never rewritten (*"never overwrite a utility's edit"*).
A utility on its own edited wording keeps saying *"due around"* until it edits
it; the first bill date token still fills, because the context now carries it.

WHY PUBLISHED AND NOT A DRAFT (unlike 0021)
────────────────────────────────────────────────────────────────────────────
0021 wrote a draft because a CONTRACT needs an effective date only a person
chooses (BR-NOT-002). `email_welcome` is an ordinary class: the seeder itself
publishes it undated with no person (`seed_templates._seed_one`), so a new
utility gets the new wording published on day one, and an existing utility on
the untouched seed is given the same — otherwise the old sentence, now with a
real date in it, would tell a new customer their first bill is *due* on its
issue day.

IDEMPOTENT — after one pass the published body is the new wording, so it no
longer matches and a second pass writes nothing.

ROLLBACK (`migrate notifications 0024`) — FORWARD-ONLY, and said so. The old
wording is never removed: it is the archived version directly below ours, and a
System Admin can republish it from Settings → Templates in one action. A reverse
that deleted a PUBLISHED version would be refused by `0006`'s trigger the moment
any welcome had been queued against it (a pinned version is history), so the
reverse writes nothing and logs that.
"""

import logging

from django.db import migrations, transaction
from django.utils import timezone

logger = logging.getLogger("smartbillhub.notifications")

CODE = "email_welcome"
JOB = "notifications 0025 · CR-190-BRC10 · PO 2026-10-22 'no due date required'"
AUDIT_ENTITY = "notification_template_version"
AUDIT_PUBLISHED = "template.published"

#: The nil sentinel, never `''` (assets/0003, OQ-354).
NO_TENANT = "00000000-0000-0000-0000-000000000000"

#: FROZEN here rather than imported, for `assets/0011`'s reason: a migration must
#: keep doing what it did when the seed later moves. A test pins NEW_BODY to
#: `seed_templates.EMAIL_WELCOME_BODY` today.
SUBJECT = "Welcome to {utility_name}"

OLD_BODY = """Welcome, {first_name}.

Your service at {service_address} starts on {service_start_date}.

Your account number is {account_no}. It is worth keeping somewhere handy — we will
ask for it whenever you call.

Your first bill is due around {first_bill_date}. At {utility_website} you can see
your bills and your usage, go paperless, and set up autopay.

If anything about your service or your address looks wrong, call {support_phone}
now. It is far easier to fix at the start than after the first bill.

{utility_name}"""

NEW_BODY = """Welcome, {first_name}.

Your service at {service_address} starts on {service_start_date}.

Your account number is {account_no}. It is worth keeping somewhere handy — we will
ask for it whenever you call.

We will send your first bill on {first_bill_date}.

At {utility_website} you can see your bills and your usage, go paperless, and set
up autopay.

If anything about your service or your address looks wrong, call {support_phone}
now. It is far easier to fix at the start than after the first bill.

{utility_name}"""


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
                for template in Template.objects.filter(tenant_id=tenant_id, code=CODE):
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
                    if live.body != OLD_BODY or (live.subject or "") != SUBJECT:
                        if live.body != NEW_BODY:
                            left += 1
                            logger.info(
                                "notifications 0025: tenant %s %s/%s/%s v%s is the utility's "
                                "own wording and is left exactly alone",
                                tenant_id,
                                template.code,
                                template.category,
                                template.language,
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
                "notifications 0025: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "notifications 0025: %d welcome email(s) given the first-bill wording; "
        "%d edited copy(ies) left alone",
        moved,
        left,
    )


def forward_only(apps, schema_editor):
    logger.info(
        "notifications 0025 reverse: nothing removed — the old welcome wording is the "
        "archived version below the new one and can be republished from Settings → Templates"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0024_cr189_portal_email_update"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(republish_unedited, forward_only),
    ]
