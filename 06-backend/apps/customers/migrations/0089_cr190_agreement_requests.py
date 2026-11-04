"""customers 0089 — `agreement_requests` (CR-190-BRC10), with its RLS policy.

One request to accept one agreement by one single-use, expiring link (PO
2026-10-22, decision log *"Click-to-accept agreements: the design confirmed
with four answers"*). The policy is `0085`'s word for word: hard rule 1 admits
no tenant table without one; the `NULLIF` form per DEF-639; `PostgresOnlySQL`
skips honestly on sqlite.

HUMAN-OWNED (migration ordering and RLS policies are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-22 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

Rollback: reverse this migration (the table goes; nothing references it by FK —
the stored PDFs and filing cards it names stay, as every stored document does).
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "agreement_requests"
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0088_def_cus_10250_request_applicant_ssn_last4"),
        ("tenancy", "0064_def_rat_10220_size_class_capacity"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgreementRequest",
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
                ("template_code", models.TextField()),
                ("template_id", models.UUIDField()),
                ("template_version", models.IntegerField()),
                ("template_language", models.TextField()),
                ("effective_from", models.DateField(blank=True, null=True)),
                ("agreement_name", models.TextField()),
                ("rendered_body", models.TextField()),
                ("token_hash", models.CharField(max_length=64)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("status", models.TextField(default="pending")),
                ("origin", models.TextField()),
                ("origin_id", models.UUIDField(blank=True, null=True)),
                ("issued_by", models.UUIDField(blank=True, null=True)),
                ("issued_by_process", models.TextField(blank=True, null=True)),
                ("sent_document_id", models.UUIDField(blank=True, null=True)),
                ("email_message_id", models.UUIDField(blank=True, null=True)),
                ("letter_message_id", models.UUIDField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_name", models.TextField(blank=True, null=True)),
                ("accepted_date", models.DateField(blank=True, null=True)),
                ("accepted_ip", models.TextField(blank=True, null=True)),
                ("accepted_user_agent", models.TextField(blank=True, null=True)),
                ("accepted_filing_id", models.UUIDField(blank=True, null=True)),
                ("expired_at", models.DateTimeField(blank=True, null=True)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                ("voided_by", models.UUIDField(blank=True, null=True)),
                ("replaced_by_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="agreement_requests",
                        to="customers.account",
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
                "db_table": "agreement_requests",
                "indexes": [
                    models.Index(
                        fields=["tenant", "account", "-issued_at"], name="ix_agreement_req_account"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("token_hash",), name="uq_agreement_requests_token"
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("origin", "move_in")),
                        fields=("tenant", "origin_id", "template_code"),
                        name="uq_agreement_requests_move_in",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("status__in", ("pending", "accepted", "expired", "voided"))
                        ),
                        name="ck_agreement_requests_status",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("origin__in", ("move_in", "resend", "staff"))),
                        name="ck_agreement_requests_origin",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("status", "accepted"), _negated=True),
                            models.Q(
                                ("accepted_at__isnull", False),
                                ("accepted_date__isnull", False),
                                ("accepted_name__isnull", False),
                                models.Q(("accepted_name", ""), _negated=True),
                            ),
                            _connector="OR",
                        ),
                        name="ck_agreement_requests_accepted_proof",
                    ),
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
