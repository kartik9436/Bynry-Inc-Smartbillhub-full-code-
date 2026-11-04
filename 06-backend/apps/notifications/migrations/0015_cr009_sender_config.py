# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (Settings → Notifications — CR-009 C-12: the tenant
#           SMTP sender config)   Screens: S8
# Rules:    BR-NOT-023 (SMTP-first with ESP fallback — PO 2026-08-17, C-12) ·
#           BR-NOT-013 (no live send: these columns change WHAT WOULD BE USED,
#           never WHETHER anything sends) · 🔒 webhook-keys class (the secret
#           column stores a REFERENCE, never a credential)
# ───────────────────────────────────────────────────────
"""notifications 0015 — the tenant SMTP sender columns, all NULL by default.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-18 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

⚠ `smtp_secret_ref` HOLDS A REFERENCE, NEVER A PASSWORD. No crypto kernel
exists in this repo; rather than extend the `tenants.ein` "plain for now"
posture to a live mailbox credential, the column stores the NAME of a secret
in the deployment's own store and `sender_config.py` refuses values that look
like pasted passwords. The reasoning, the cost and the review flag live there.

NULL everywhere is the shipped state and is itself an answer under C-12's
rule: no tenant SMTP configured → the platform ESP, when that lands.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0014_cr009_a15_toggles"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationsettings",
            name="smtp_host",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationsettings",
            name="smtp_port",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationsettings",
            name="smtp_username",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationsettings",
            name="smtp_secret_ref",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationsettings",
            name="sender_from_address",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="notificationsettings",
            constraint=models.CheckConstraint(
                condition=Q(smtp_port__isnull=True) | Q(smtp_port__gte=1, smtp_port__lte=65535),
                name="ck_notification_settings_smtp_port",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-004@cr009c12 (12-governance/02-decision-log.md → 2026-08-17 C-12 verbatim · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-023 · apps/notifications/sender_config.py, the one write path)
# generated: 2026-08-18 by story-coder (CR-009 C-section lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI here — the S8 sender card) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_cr_009_c12_sender_config.py; `makemigrations --check` clean
# exceptions: (1) NO SECRET COLUMN — `smtp_secret_ref` is a reference by design; see the module docstring. (2) ALL NULLABLE with no seeded value: an unconfigured sender is a lawful, stated state (platform-ESP-pending), not a gap.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
