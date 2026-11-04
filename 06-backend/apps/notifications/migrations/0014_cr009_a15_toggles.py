# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (Settings → Notifications config half — CR-009 C-13:
#           the four A15 "(opt)" send-time elections)   Screens: S8
# Rules:    BR-NOT-022 (the four A15 toggles ship DEFAULT ON — PO 2026-08-17,
#           OQ-205 CLOSED) · BR-PAY-024 (receipt auto-queue, whose staff
#           election the first toggle is) · BR-LED-020 (bookkeeper copies) ·
#           BR-TEN-016 (a settings edit is audited)
# ───────────────────────────────────────────────────────
"""notifications 0014 — the four A15 "(opt)" toggles, DEFAULT ON.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-18 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

THE DEFAULT IS A RULING, NOT A COLUMN CONVENIENCE. OQ-205 refused to ship these
columns for three days precisely because `default=True` decides, for every
utility on the platform, that recording a payment sends the customer a receipt
without anybody choosing it. **The PO chose it — 2026-08-17, C-13 verbatim:
"keep them default to start with Utility will amake them off" — and the ruling
REVERSED the off-by-default recommendation put to them.** So `default=True`
here is the ratified figure, and a test asserts it so drift goes RED.

THE SAME DEFAULT ANSWERS OQ-216's POSTURE FOR PRE-TOGGLE TENANTS. Every tenant
provisioned before this migration gains all four columns as TRUE — *"treated
as ON"* — with no data migration and no backfill, because a Django AddField
with a default writes it onto every existing row.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0013_cr009_render_context"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationsettings",
            name="receipt_on_record_payment",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="notificationsettings",
            name="credit_notice_email",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="notificationsettings",
            name="bookkeeper_copies",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="notificationsettings",
            name="lockbox_receipts",
            field=models.BooleanField(default=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-004@cr009c13 (12-governance/02-decision-log.md → 2026-08-17 C-13 verbatim · 12-governance/01-open-questions.md OQ-205/OQ-216 closures · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-022 · apps/notifications/dispatch_config.py, the one write path)
# generated: 2026-08-18 by story-coder (CR-009 C-section lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI here — the S8 elections card) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_cr_009_c13_a15_toggles.py asserts all four seed TRUE (the ratified figure) — red-proved by flipping one default to False and reading the failure
# exceptions: (1) DEFAULT TRUE IS THE PO'S FIGURE (C-13), not hard-won law 3's fail-closed — the ruling overrides the heuristic and is quoted in the module docstring. (2) NO CONSUMER COLUMN and no per-toggle audit table: the consumers read the flags through the published notifications read, and the edit is audited on the one settings row like every other field.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
