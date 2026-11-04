"""notifications 0034 — `provider_status_events` (`CR-198-BRC10`).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-29 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Additive: one new table, nothing
existing moves. Its RLS policy is 0035, on its own step like every RLS
migration in this module.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0033_def_pay_10651_past_due_letter"),
        ("tenancy", "0066_def_cus_10445_service_request_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderStatusEvent",
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
                ("provider", models.TextField()),
                ("event_key", models.TextField()),
                ("kind", models.TextField(default="status")),
                ("provider_reference", models.TextField()),
                ("outcome", models.TextField()),
                ("error_code", models.TextField(blank=True, null=True)),
                ("received_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "message",
                    models.ForeignKey(
                        blank=True,
                        db_column="message_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
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
                "db_table": "provider_status_events",
                "indexes": [
                    models.Index(
                        fields=["tenant", "provider_reference"], name="ix_provider_status_ref"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "provider", "event_key"),
                        name="uq_provider_status_events_key",
                    )
                ],
            },
        ),
    ]
