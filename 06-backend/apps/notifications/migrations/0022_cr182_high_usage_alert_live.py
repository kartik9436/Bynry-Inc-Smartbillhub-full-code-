# ── Trace ──────────────────────────────────────────────
# Change:   CR-182-BRC10 — PO rulings A1–A5, 2026-10-14, verbatim: *"A4 … send
#           her Email; A5 … Option 2 Tell them as soon as the reading is
#           flagged"*. Answers OQ-262's high-usage half.
# Rules:    BR-NOT-018 (a SET-12 row with a trigger) · BR-TEN-016 (a settings
#           edit is audited) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           hard-won law 14 (a per-tenant savepoint, proved on PostgreSQL)
# Tests:    tests/test_cr182_high_consumption_alert.py
# ───────────────────────────────────────────────────────
"""notifications 0022 — *High usage alert* becomes a live email on every utility
that never touched it.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-14 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

WHAT IT DOES, IN ONE SENTENCE
────────────────────────────────────────────────────────────────────────────
For every utility whose SET-12 *High usage alert* row still holds the seeded
default of the days it had no trigger — event OFF, email OFF, SMS OFF — it
switches the event and its email channel ON with the new template class, and
removes the SMS channel row, because the event no longer offers SMS (PO A4
chose email).

WHY ONLY AN UNTOUCHED ROW
────────────────────────────────────────────────────────────────────────────
`rule_service._ensure_rules` seeded the row OFF while `trigger_blocked_by` was
`OQ-262` (hard-won law 3). A System Admin could still have saved it, and their
choice is not ours to overturn. Every save writes `notification_rule.updated`
or `.toggled` to `audit_log` against the rule's id (hard rule 7), so a row with
NO such audit row was never chosen by anybody and is moved; a row with one is
left exactly alone and LOGGED. `audit_log` is pruned on its retention schedule
(OQ-1340), so a choice made long enough ago is no longer visible — the miss is
in the direction of the PO's ruling, and is stated rather than hidden.

A utility with no row at all needs nothing: the catalogue's new default is read
lazily (`channel_switches`) and materialised on the next read.

IDEMPOTENT
────────────────────────────────────────────────────────────────────────────
After one pass the row is ON, so it no longer matches the seeded-OFF shape and
a second pass writes nothing.

ROLLBACK (`migrate notifications 0021`)
────────────────────────────────────────────────────────────────────────────
A no-op, deliberately: the previous build ignores the email template code and
treats the event as blocked whatever the row says, and turning a utility's
switch back off on rollback could overturn a choice made after this ran.

RLS AND FAILURE
────────────────────────────────────────────────────────────────────────────
`tenants` is a platform table and is listed first; every other read and write
happens with `app.tenant_id` set to that tenant. Each tenant is its own
SAVEPOINT (law 14), and each change writes one `notification_rule.updated`
audit row naming this job (BR-TEN-016).
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger("smartbillhub.notifications")

EVENT_KEY = "high_usage_alert"
TEMPLATE_CODE = "email_high_usage_alert"
JOB = "notifications 0022 · CR-182-BRC10 · PO 2026-10-14 A4/A5"
AUDIT_ENTITY = "notification_rule"
AUDIT_ACTION = "notification_rule.updated"
TOUCHED_ACTIONS = ("notification_rule.updated", "notification_rule.toggled")
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def switch_on_untouched(apps, schema_editor):
    Rule = apps.get_model("notifications", "NotificationRule")
    Channel = apps.get_model("notifications", "NotificationRuleChannel")
    AuditLog = apps.get_model("audit", "AuditLog")
    connection = schema_editor.connection
    moved = left = 0
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        try:
            # ⚠ THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE (law 14).
            with transaction.atomic():
                rule = Rule.objects.filter(tenant_id=tenant_id, event_key=EVENT_KEY).first()
                if rule is None:
                    continue
                channels = {c.channel: c for c in Channel.objects.filter(rule_id=rule.pk)}
                seeded_off = not rule.enabled and not any(c.enabled for c in channels.values())
                touched = AuditLog.objects.filter(
                    tenant_id=tenant_id,
                    entity_type=AUDIT_ENTITY,
                    entity_id=rule.pk,
                    action__in=TOUCHED_ACTIONS,
                ).exists()
                if not seeded_off or touched:
                    left += 1
                    logger.info(
                        "notifications 0022: tenant %s high_usage_alert was set by the utility "
                        "(enabled=%s, audited=%s) and is left exactly alone",
                        tenant_id,
                        rule.enabled,
                        touched,
                    )
                    continue
                rule.enabled = True
                rule.save(update_fields=["enabled", "updated_at"])
                email = channels.get("email")
                if email is None:
                    Channel.objects.create(
                        tenant_id=tenant_id,
                        rule_id=rule.pk,
                        channel="email",
                        enabled=True,
                        template_code=TEMPLATE_CODE,
                    )
                else:
                    email.enabled = True
                    email.template_code = TEMPLATE_CODE
                    email.save(update_fields=["enabled", "template_code", "updated_at"])
                sms = channels.get("sms")
                if sms is not None:
                    sms.delete()
                AuditLog.objects.create(
                    tenant_id=tenant_id,
                    actor_user_id=None,  # an unnamed system job, named in `after`
                    action=AUDIT_ACTION,
                    entity_type=AUDIT_ENTITY,
                    entity_id=rule.pk,
                    before={"enabled": False, "channels": {"email": False, "sms": False}},
                    after={
                        "enabled": True,
                        "channels": {"email": True},
                        "template_code": TEMPLATE_CODE,
                        "source": JOB,
                    },
                )
                moved += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0022: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "notifications 0022: high usage alert switched on for %d utility(ies); %d set by the "
        "utility left alone",
        moved,
        left,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0021_cr088_autopay_default_wording"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(switch_on_untouched, migrations.RunPython.noop),
    ]
