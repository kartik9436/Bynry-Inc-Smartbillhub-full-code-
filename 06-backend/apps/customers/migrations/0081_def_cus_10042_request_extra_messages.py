"""customers 0081 — `service_request_extra_messages` (`DEF-CUS-10042`).

PO 2026-10-11, on New request step 4's *What the customer is told*: *"use table
array componnet and allow user to add more communcation to user"*. The five
automatic rows live on `service_request_messages` and are untouched; this is
the table a clerk's ADDED rows land in, shaped as `move_extra_messages` is.

⚠ **MIGRATION ORDERING IS A 🔒 SENSITIVE PATH (CLAUDE.md).** An ordinary
`CreateModel`: no data step, no backfill — every existing request simply has no
added messages. RLS is `0082`, the next file.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-11 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0080_cr171_p1_01_move_in_redesign"),
        ("tenancy", "0061_cr172_logo_to_document_store"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceRequestExtraMessage",
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
                ("seq", models.SmallIntegerField()),
                ("template_code", models.TextField()),
                ("channel", models.TextField()),
                ("to_address", models.TextField()),
                ("send_when", models.TextField()),
                ("fired_at", models.DateTimeField(blank=True, null=True)),
                ("fired_state", models.TextField(blank=True, null=True)),
                ("fired_reason", models.TextField(blank=True, null=True)),
                ("notification_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "request",
                    models.ForeignKey(
                        db_column="request_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="extra_messages",
                        to="customers.servicerequest",
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
                "db_table": "service_request_extra_messages",
                "indexes": [
                    models.Index(fields=["tenant", "request"], name="ix_sr_extra_messages_request")
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("channel__in", ("email", "text"))),
                        name="ck_sr_extra_messages_channel",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("send_when__in", ("on_submit", "on_approve", "on_refuse"))
                        ),
                        name="ck_sr_extra_messages_send_when",
                    ),
                    models.UniqueConstraint(
                        fields=("request", "seq"), name="uq_sr_extra_messages_seq"
                    ),
                ],
            },
        ),
    ]
