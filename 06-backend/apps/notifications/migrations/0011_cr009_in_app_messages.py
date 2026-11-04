# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — the in-app channel: the per-recipient message
#           store the bell and the inbox read)   Screens: shell-chrome · S8
# Rules:    BR-NOT-019 (in-app is a real delivery channel and the platform is
#           its provider) · BR-NOT-020 (one message per bulk action) ·
#           BR-NOT-005 (queue only; the dispatcher is the sole send path, and
#           this table is written by an adapter behind the ONE provider seam) ·
#           BR-TEN-017 (the delivered artifact is a snapshot, never re-rendered)
#           · CLAUDE.md rule 1 (tenant scoping; RLS FORCE — migration 0012) ·
#           rule 6 (idempotency: one delivery per message per inbox)
# ───────────────────────────────────────────────────────
"""notifications 0011 — `in_app_messages`, the per-recipient mailbox.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-17 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

WHY THIS TABLE EXISTS AT ALL, in the PO's own words (2026-08-17): *"We can
confirm it whether it is working on not if we get in APp Notifcaition, which
does not require any integration and it is proof that notification is working"*.
Every other channel in `models.CHANNELS` waits on a third party. This one waits
on a table, and the table is this one.

WHAT IT IS NOT. It is not a second queue. `outbound_messages` stays the ONE
queue and the ONE record of what the utility undertook to send; nothing here
writes a queue row, advances a queue status or bypasses the dispatcher. Rows
land here only when `apps/notifications/in_app.py` — the delivery adapter
resolved through `provider_seam` exactly like a provider would be — is handed a
batch by the dispatcher. The reasoning for the split, and for `user_id` being a
plain uuid rather than a cross-module FK, is in the model's own docstring.

RLS IS **NOT** IN THIS MIGRATION and that is deliberate, following 0009/0010 and
0003/0004: the table lands here, the policy lands in 0012, so a reviewer reading
a policy diff is never also reading a column diff. **Until 0012 has run this
table has no isolation**, which is why the two ship in one commit.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0010_rls_cr009_notification_rules"),
        ("tenancy", "0015_cr008_payment_method_gl"),
    ]

    operations = [
        migrations.CreateModel(
            name="InAppMessage",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("user_id", models.UUIDField()),
                ("subject", models.TextField(blank=True, null=True)),
                ("body", models.TextField()),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "outbound_message",
                    models.ForeignKey(
                        db_column="outbound_message_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="in_app_deliveries",
                        to="notifications.outboundmessage",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "in_app_messages",
                "indexes": [
                    models.Index(
                        condition=models.Q(("read_at__isnull", True)),
                        fields=["tenant", "user_id"],
                        name="ix_in_app_msgs_unread",
                    ),
                    models.Index(
                        fields=["tenant", "user_id", "-created_at"], name="ix_in_app_msgs_inbox"
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "outbound_message", "user_id"),
                        name="uq_in_app_msgs_message_user",
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 "PO RULINGS 2026-08-17 (fourth set): IN-APP IS THE PROOF CHANNEL, and a bulk action sends ONE message" in full · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-019/BR-NOT-020 · apps/notifications/models.py (CHANNELS, SOURCE_TYPES, OutboundMessage) · apps/notifications/provider_seam.py (the ONE adapter seam this delivers behind))
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved by tests/test_cr_009_in_app_channel.py and tests/test_cr_009_in_app_isolation.py — the isolation tier asserts SHAPE on SQLite and says so rather than implying RLS coverage there
# exceptions: (1) NO RLS HERE — it is migration 0012, following the 0003/0004 and 0009/0010 pairing this module already uses. Both ship in one commit. (2) `user_id` IS NOT A FOREIGN KEY to identity.users: B2 §2's cross-module FK set is a REVIEWED set and this lane does not add to it in passing; the precedent on the row above is `outbound_messages.returned_by`, which records a user the same way and for the same reason. The cost — an orphan row after a hard user delete — is stated on the model rather than implied. (3) NO PARTITION: NFR-24 names five born-partitioned tables and this is not one; a staff mailbox holds tens of rows per user, not millions.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
