# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 · T-41 — lane S-FIND (the field app's alert
#           kinds, the emergency acknowledgement, R28's five minutes)
# Rules:    BR-FLD-00028 (R28) · BR-FLD-00029 (R29) · CLAUDE.md 🔒 migration
#           ordering
# Tests:    06-backend/tests/test_cr187_find_alerts.py ·
#           tests/test_cr187_find_pg.py (PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""work 0041 — NEW `work_field_alerts`: one alert a dispatcher sent to one
technician's handset, and its answer.

* `kind` CHECK — `urgent_assignment · emergency · schedule_change ·
  dispatch_message` (T-41's four).
* `ack_required` / `ack_due_at` (sent + 5 min, R28) / `acknowledged_at` /
  `escalated_at` (dispatch told) / `dispatch_told` (notifications' answer code).
* unique `(tenant, key)` where `key` is set — the sender's idempotency key.
* partial index on `(tenant, ack_due_at)` over the unanswered, unescalated
  emergencies — what the per-minute sweep's `EXISTS` reads.

RLS + FORCE in `work/0042`, the next migration (the repo's convention for a new
table). Additive; nothing backfilled. **Down:** drops the table — and with it
every alert's record of who was told what and when, which the audit rows
(`work.alert.*`) still carry.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-21 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); the review-ledger row
is owed by the coordinator (this lane may not edit shared registers).
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

#: Frozen here, never imported: a migration states the schema of its day.
ALERT_KINDS = ("urgent_assignment", "emergency", "schedule_change", "dispatch_message")


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0010_def_idn_10023_password_history"),
        ("metering", "0076_def_wrk_6737_outcome_check"),
        ("tenancy", "0064_def_rat_10220_size_class_capacity"),
        ("work", "0040_rls_force_money_pushes"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkFieldAlert",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("kind", models.TextField()),
                ("message", models.TextField(blank=True, default="")),
                ("sent_at", models.DateTimeField()),
                ("key", models.TextField(blank=True, null=True)),
                ("ack_required", models.BooleanField(default=False)),
                ("ack_due_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("escalated_at", models.DateTimeField(blank=True, null=True)),
                ("dispatch_told", models.TextField(blank=True, null=True)),
                ("devices_attempted", models.IntegerField(blank=True, null=True)),
                ("pushed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "acknowledged_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="acknowledged_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "sent_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="sent_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "technician",
                    models.ForeignKey(
                        db_column="technician_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="field_alerts",
                        to="work.technician",
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
                (
                    "work_order",
                    models.ForeignKey(
                        blank=True,
                        db_column="work_order_id",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="field_alerts",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_field_alerts",
                "indexes": [
                    models.Index(
                        fields=["tenant", "technician", "sent_at"], name="ix_work_field_alerts_tech"
                    ),
                    models.Index(
                        condition=models.Q(
                            ("ack_required", True),
                            ("acknowledged_at__isnull", True),
                            ("escalated_at__isnull", True),
                        ),
                        fields=["tenant", "ack_due_at"],
                        name="ix_work_field_alerts_due",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("kind__in", ALERT_KINDS)), name="ck_work_field_alerts_kind"
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("key__isnull", False)),
                        fields=("tenant", "key"),
                        name="uq_work_field_alerts_tenant_key",
                    ),
                ],
            },
        ),
    ]
