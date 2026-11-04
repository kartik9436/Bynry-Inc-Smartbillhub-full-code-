# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10534 — mail server settings typed in two places; only the
#           Connectors connection was ever read by the email adapter.
# Ruling:   PO 2026-10-22, verbatim: *"We have to move everything in connector
#           not any other place"* (decision log 2026-10-22, *Corrected bills*
#           Q4, and the lane SETTINGS-MOVE judgments entry, item 7).
# Rules:    BR-INT-005 (the tenant connects its OWN mailbox) · CLAUDE.md hard
#           rule 1 (tenant scoping — `app.tenant_id` is set per tenant) · rule 7
#           (audited) · hard-won law 14 (a per-tenant SAVEPOINT, proved on
#           PostgreSQL)
# Tests:    06-backend/tests/test_settings_move_smtp_in_connectors.py
# Impacts:  apps/notifications/models.py (the five columns, read by nothing
#           from this commit and listed for removal) ·
#           apps/notifications/sender_config.py (reads the connector)
# ───────────────────────────────────────────────────────
"""integrations 0016 — the mail server typed on Notifications moves to Connectors.

HUMAN-OWNED (migration ordering is a 🔒 sensitive path, CLAUDE.md).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-22 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*), with a row in
`12-governance/09-human-review-ledger.md`.

WHAT IT DOES, ONCE
------------------
`0004_c35_fold_sender_secret_ref` already moved the tenants that had named a
mail PASSWORD, and it SKIPPED every tenant that already had a Custom SMTP
connection. So two kinds of value could still be held only on Notifications:

  * a tenant that typed a host / port / user / sender and never named a
    password (0004 only looked at rows with `smtp_secret_ref`);
  * a tenant whose connection already existed but lacked a field the form held
    (0004 skipped it whole).

For each tenant whose `notification_settings` holds any of `smtp_host`,
`smtp_port`, `smtp_username`, `sender_from_address`:

  * **a Custom SMTP connection exists** (production first) → each of `host`,
    `port`, `username`, `send_from` that the connection LACKS (absent or empty)
    is copied in. **A value the connection already has wins** and is left
    exactly alone — it is what a person typed on Connectors, the newer truth;
  * **none exists** → one is created, production, `not_set_up`, switched OFF,
    no credential — 0004's absent-password shape, because those columns never
    held a password.

Every tenant changed writes ONE audit row, `integration_connection.smtp_settings_moved`,
with before/after of the copied fields only. The source columns are NOT cleared
and NOT dropped: they are read by nothing from this commit, and a column
dropped in the commit that stops reading it leaves no way back if the copy was
wrong (0004's reason, kept).

WORKED FIGURE (decision log): Springfield's connector holds host
`smtp.office365.com` and no sender; Notifications held host
`mail.springfield.example` and sender `billing@springfieldwater.example` → the
connector keeps `smtp.office365.com` and gains the sender. Re-running changes
nothing, because every field it would copy is then present.

⚠ THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE (hard-won law 14). A
tenant whose row cannot be moved is logged and the others go on; on PostgreSQL
a failed statement outside a nested `atomic()` would abort the whole migration.
"""

from __future__ import annotations

import logging
import uuid

from django.db import migrations, transaction

logger = logging.getLogger("smartbillhub.integrations")

PROVIDER_KEY = "email_smtp"
PRODUCTION = "production"
NO_TENANT = "00000000-0000-0000-0000-000000000000"
AUDIT_ACTION = "integration_connection.smtp_settings_moved"
AUDIT_ENTITY = "integration_connection"
JOB = "integrations/0016_def_not_10534_smtp_settings_to_connector"

#: notification_settings column → the connector's config key.
FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("smtp_host", "host"),
    ("smtp_port", "port"),
    ("smtp_username", "username"),
    ("sender_from_address", "send_from"),
)


def _set_tenant(connection, tenant_id):
    """Hard rule 1. On sqlite there is no RLS and no `set_config`."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _held(row) -> dict[str, str]:
    """What the old Notifications form holds, as connector config values."""
    held: dict[str, str] = {}
    for column, key in FIELD_MAP:
        value = getattr(row, column, None)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            held[key] = text
    return held


def move_tenant(apps, tenant_id) -> str:
    """Move one tenant. Answers `created`, `filled` or `unchanged`."""
    Settings = apps.get_model("notifications", "NotificationSettings")
    Connection = apps.get_model("integrations", "IntegrationConnection")
    AuditLog = apps.get_model("audit", "AuditLog")

    row = Settings.objects.filter(tenant_id=tenant_id).first()
    if row is None:
        return "unchanged"
    held = _held(row)
    if not held:
        return "unchanged"

    rows = list(Connection.objects.filter(tenant_id=tenant_id, provider_key=PROVIDER_KEY))
    rows.sort(key=lambda one: 0 if one.environment == PRODUCTION else 1)
    target = rows[0] if rows else None

    if target is None:
        created = Connection.objects.create(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            provider_key=PROVIDER_KEY,
            label=None,
            environment=PRODUCTION,
            status="not_set_up",  # no password was ever held here
            enabled=False,
            cadence="manual",
            next_run_at=None,
            config={"port": "587", **held},
            connected_at=None,
        )
        after = dict(held)
        before: dict[str, str | None] = {key: None for key in held}
        entity_id = created.pk
        outcome = "created"
    else:
        config = dict(target.config or {})
        before = {}
        after = {}
        for key, value in held.items():
            if str(config.get(key) or "").strip():
                continue  # the connector's own value wins
            before[key] = config.get(key)
            after[key] = value
            config[key] = value
        if not after:
            return "unchanged"
        target.config = config
        target.save(update_fields=["config", "updated_at"])
        entity_id = target.pk
        outcome = "filled"

    AuditLog.objects.create(
        tenant_id=tenant_id,
        actor_user_id=None,  # an unnamed system job, named in `after`
        action=AUDIT_ACTION,
        entity_type=AUDIT_ENTITY,
        entity_id=entity_id,
        before=before,
        after={**after, "outcome": outcome, "source": JOB},
    )
    return outcome


def move(apps, schema_editor):
    connection = schema_editor.connection
    tally = {"created": 0, "filled": 0, "unchanged": 0}
    tenant_ids = list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))
    for tenant_id in tenant_ids:
        _set_tenant(connection, tenant_id)
        try:
            # ⚠ THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE (law 14).
            with transaction.atomic():
                tally[move_tenant(apps, tenant_id)] += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "integrations 0016: tenant %s could not be moved; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "integrations 0016: %(created)d Custom SMTP connection(s) created, %(filled)d "
        "filled in, %(unchanged)d tenant(s) unchanged",
        tally,
    )


def forward_only(apps, schema_editor):
    """Nothing to undo: the source columns were never cleared, and a value
    copied into a connector is now the connector's — removing it could take a
    person's own later edit with it."""


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0015_cr173_file_delivery_and_credential_slot"),
        ("notifications", "0027_def_bil_10530_fail_stuck_bill_emails"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [migrations.RunPython(move, forward_only)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: decision log 2026-10-22 (Corrected bills Q4 · SETTINGS-MOVE judgments item 7) · integrations/0004 (the first half of this move)
# generated: 2026-10-22 by lane SETTINGS-MOVE
# checklist: A✔ B✔ C✔ D=n/a(a migration has no route) E✔(Configure → Notifications reads the connector this fills) F✔ G✔ H=PENDING(🔒 — human sign-off owed, row in 09-human-review-ledger.md)
# gates: makemigrations --check · pytest tests/test_settings_move_smtp_in_connectors.py (sqlite AND PostgreSQL)
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
