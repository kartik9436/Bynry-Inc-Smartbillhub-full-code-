# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10530 — a bill's email pinned to the bill LAYOUT sat at
#           "Waiting · 0 tries" forever
# Ruling:   PO 2026-10-22, asked what happens to rows already stuck: (A) send
#           them now, or (B) mark them failed — verbatim *"mark them failed"*
#           (decision log "2026-10-22 — Bill emails stuck at 'Waiting · 0
#           tries' are marked FAILED, not sent")
# Rules:    BR-NOT-005 (forward-only: queued → failed is lawful) · CLAUDE.md
#           hard rule 1 (tenant scoping) · rule 7 (audited) · BR-AUD-006 (no
#           PII in the trail) · hard-won law 14 (a per-tenant savepoint)
# Tests:    tests/test_def_bil_10530_bill_email_pin.py
# ───────────────────────────────────────────────────────
"""notifications 0027 — queued messages that can never render are marked FAILED.

RENUMBERED 2026-10-22 at merge (lane MERGE-EMAILS): written as `0023` beside
CR-188's and CR-190's own `0023`s; applied by no shared database, so it moved to
`0027`, after `0026_def_cus_10445_service_request_ack_wording`. Nothing else in
it changed.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

WHAT IT DOES
────────────────────────────────────────────────────────────────────────────
Finds every `outbound_messages` row that is still `queued` on a WORDING channel
(email, text, in-app) and whose pin names a `(template_id, version)` that is NOT
a notification template version in that tenant — in practice a bill's email or
text pinned to the bill's PDF layout. Each one is set `failed` with
`last_error = 'stuck_wrong_template_pin_2026_10_22'` and gets ONE
`outbound_message.failed` audit row naming this job. **None is sent**, and its
try count is left as it is.

WHY ONLY THOSE ROWS
────────────────────────────────────────────────────────────────────────────
A print or portal row of a bill is pinned to the bill layout BY DESIGN (it
carries the document), so those channels are never touched. A wording-channel
row whose pin DOES load is a healthy message waiting its turn and is never
touched. A wording row with no pin at all is a different fault (queued before
its template was published) and is left for the dispatcher, which now fails it
by name on its next attempt.

IDEMPOTENT · ROLLBACK
────────────────────────────────────────────────────────────────────────────
A second pass finds nothing: the rows are no longer `queued`. Rollback
(`migrate notifications 0026`) is a no-op on purpose — moving a failed row back
to queued is the backwards status move BR-NOT-005 forbids, and the row would
only loop again. A clerk's *Try again* on the queue screen is the way back.

RLS AND FAILURE
────────────────────────────────────────────────────────────────────────────
`tenants` is a platform table and is listed first; every other read and write
happens with `app.tenant_id` set to that tenant. Each tenant is its own
SAVEPOINT (law 14): one tenant's failure is logged and every other tenant is
unaffected.
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger("smartbillhub.notifications")

REASON = "stuck_wrong_template_pin_2026_10_22"
JOB = "notifications 0027 · DEF-BIL-10530 · PO 2026-10-22 'mark them failed'"
WORDING_CHANNELS = ("email", "sms", "in_app")
AUDIT_ACTION = "outbound_message.failed"
AUDIT_ENTITY = "outbound_message"
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def stuck_rows(apps, tenant_id):
    """The rows this migration fails, for one tenant (also read by its tests)."""
    Message = apps.get_model("notifications", "OutboundMessage")
    Version = apps.get_model("notifications", "NotificationTemplateVersion")
    candidates = Message.objects.filter(
        tenant_id=tenant_id,
        status="queued",
        channel__in=WORDING_CHANNELS,
        template_id__isnull=False,
        template_version__isnull=False,
    )
    known = set(Version.objects.filter(tenant_id=tenant_id).values_list("template_id", "version"))
    return [row for row in candidates if (row.template_id, row.template_version) not in known]


def fail_stuck(apps, schema_editor):
    AuditLog = apps.get_model("audit", "AuditLog")
    connection = schema_editor.connection
    failed = 0
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        try:
            # ⚠ THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE (law 14).
            with transaction.atomic():
                for row in stuck_rows(apps, tenant_id):
                    row.status = "failed"
                    row.last_error = REASON
                    row.next_attempt_at = None
                    row.batch_id = None
                    row.save(
                        update_fields=[
                            "status",
                            "last_error",
                            "next_attempt_at",
                            "batch_id",
                            "updated_at",
                        ]
                    )
                    AuditLog.objects.create(
                        tenant_id=tenant_id,
                        actor_user_id=None,  # an unnamed system job, named in `after`
                        action=AUDIT_ACTION,
                        entity_type=AUDIT_ENTITY,
                        entity_id=row.pk,
                        before={"status": "queued"},
                        after={
                            "status": "failed",
                            "last_error": REASON,
                            "channel": row.channel,
                            "source_type": row.source_type,
                            "account_id": str(row.account_id) if row.account_id else None,
                            "source": JOB,
                        },
                    )
                    failed += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0027: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info("notifications 0027: %d stuck message(s) marked failed, none sent", failed)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0026_def_cus_10445_service_request_ack_wording"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(fail_stuck, migrations.RunPython.noop),
    ]
