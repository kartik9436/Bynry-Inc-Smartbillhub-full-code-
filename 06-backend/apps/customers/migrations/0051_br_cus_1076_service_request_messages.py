"""customers 0051 — `service_request_messages` (`BR-CUS-1076`).

THE PO ASKED WHETHER THE APPROVAL NOTIFICATION WORKED, AND IT DID NOT.
─────────────────────────────────────────────────────────────────────────────
2026-09-15, verbatim: *"at the time of approval we are also linking
notification and templates to the modal - are you ensuring it will work?"*

There was no table holding which messages a request would send, no template
choice on a request at all, and approving fired nothing. This is the table the
blueprint's step-6 block `What goes out to the applicant` has always implied
(entry 06, p080–p081, read AS IMAGES): five rows, three ticked, each naming a
moment and a wording.

⚠ **MIGRATION ORDERING IS A 🔒 SENSITIVE PATH (CLAUDE.md).** This one is an
ordinary `CreateModel` with no data step and no backfill: the table starts
empty, and the five drawn DEFAULTS are a constant in
`apps/customers/applicant_messages.py` rather than rows, so every request that
existed before today answers the block read correctly instead of answering it
empty. Nothing needs backfilling, which is the point.

Its RLS policy is `0052`, applied in the same commit — a tenant table without
one is hard rule 1 broken, and the two arrive together for that reason.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path) ·
HUMAN-REVIEW-PENDING — AI-authored 2026-09-15 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0050_br_cus_092_dob_and_drivers_licence"),
        ("tenancy", "0044_cr094_i_account_document_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceRequestMessage",
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
                ("occasion", models.TextField()),
                ("send", models.BooleanField(default=False)),
                ("template_code", models.TextField(blank=True, null=True)),
                ("template_id", models.UUIDField(blank=True, null=True)),
                ("template_version_seen", models.IntegerField(blank=True, null=True)),
                ("fired_at", models.DateTimeField(blank=True, null=True)),
                ("fired_state", models.TextField(blank=True, null=True)),
                ("fired_reason", models.TextField(blank=True, null=True)),
                ("fired_ref", models.TextField(blank=True, null=True)),
                ("fired_template_code", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "request",
                    models.ForeignKey(
                        db_column="request_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="applicant_messages",
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
                "db_table": "service_request_messages",
                "indexes": [
                    models.Index(fields=["tenant", "request"], name="ix_sr_messages_request")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("request", "occasion"), name="ux_sr_messages_request_occasion"
                    )
                ],
            },
        ),
    ]
