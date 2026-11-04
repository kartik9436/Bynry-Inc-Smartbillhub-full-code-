# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-016 (bulk corrections — the case, the pinned bill set, the
#           per-bill results) · US-BIL-031 (the reissued document instance)
#           Screens: S30
# Rules:    BR-BIL-014 (the correction workflow) · BR-BIL-041/042 (the derived
#           class) · BR-BIL-044 (the persisted, content-hashed preview) ·
#           BR-BIL-045 (the resolved posting period) · BR-BIL-046 (the PINNED
#           bill list) · BR-BIL-047 (per-bill atomicity + results) · BR-BIL-048
#           (one open case per chain) · BR-BIL-030 (the frozen payload, which is
#           why a document fix is a NEW instance) · B2 Addendum r10 #9 (the
#           table) · r10 #15 (exact DDL = Eng-Lead-owned) · CLAUDE.md rule 2
#           (money NUMERIC(18,6) + CHAR(3))
# ───────────────────────────────────────────────────────
"""billing 0014 — the corrections workflow's three tables (r10 #9 + EP-BIL-04).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and `correction_case_bills`
carries the money a correction moves). HUMAN-REVIEW-PENDING — AI-authored
2026-08-11 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

`correction_cases` is Addendum r10 #9; every column beyond r10's one-line
description cites the rule that puts it there, in `apps/billing/correction_models.py`.
`invoice_document_instances` is NOT in r10 — it is the table OQ-103's closure
created (PO 2026-08-11, option (a) REISSUE), an Eng-Lead DDL call under r10 #15,
recorded in 12-governance/02-decision-log.md rather than only here.

WHAT IS DELIBERATELY ABSENT: a `corrects_invoice_id` column on `invoices`.
EP-BIL-04 §5 asks for one and BR-BIL-064 needs the chain — and the PO ruled the
storage on 2026-08-11: *"in Histrory log only - at account level"* (OQ-120). A
lane implementing BR-BIL-064 must not add it, and this migration does not.

RLS is 0015, not this migration: policy SQL is its own 🔒 review surface, and
mixing DDL with policy in one file has meant, twice in this repo, that a table
shipped and its policy did not.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0013_rls_budget_billing"),
        ("customers", "0008_rls_account_notes"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorrectionCase",
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
                ("case_no", models.TextField(blank=True, null=True)),
                ("reason_codes", models.JSONField(default=list)),
                ("correction_class", models.TextField()),
                ("scope_kind", models.TextField(default="single")),
                ("scope", models.JSONField(default=dict)),
                ("status", models.TextField(default="preview")),
                ("preview", models.JSONField(default=dict)),
                ("preview_hash", models.TextField(blank=True, null=True)),
                ("posting_period", models.DateField(blank=True, null=True)),
                ("approved_on", models.DateField(blank=True, null=True)),
                ("executed_on", models.DateField(blank=True, null=True)),
                ("closed_reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="approved_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="correction_cases_approved",
                        to="identity.user",
                    ),
                ),
                (
                    "closed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="closed_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="correction_cases_closed",
                        to="identity.user",
                    ),
                ),
                (
                    "initiated_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="initiated_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="correction_cases_initiated",
                        to="identity.user",
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
                "db_table": "correction_cases",
            },
        ),
        migrations.CreateModel(
            name="InvoiceDocumentInstance",
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
                ("instance_no", models.IntegerField(default=1)),
                ("payload", models.JSONField()),
                ("payload_version", models.IntegerField(default=1)),
                ("template_id", models.UUIDField(blank=True, null=True)),
                ("template_version", models.IntegerField(blank=True, null=True)),
                ("template_language", models.TextField(blank=True, null=True)),
                ("reason_codes", models.JSONField(default=list)),
                ("master_data_ref", models.TextField(blank=True, null=True)),
                ("changed_fields", models.JSONField(default=dict)),
                ("reissued_on", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "case",
                    models.ForeignKey(
                        blank=True,
                        db_column="case_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_instances",
                        to="billing.correctioncase",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="created_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        db_column="invoice_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_instances",
                        to="billing.invoice",
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
                "db_table": "invoice_document_instances",
            },
        ),
        migrations.CreateModel(
            name="CorrectionCaseBill",
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
                ("impact", models.JSONField(default=dict)),
                ("delta_amount", models.DecimalField(decimal_places=6, default=0, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("direction", models.TextField(default="zero")),
                ("warnings", models.JSONField(default=list)),
                ("status", models.TextField(default="queued")),
                ("failure_reason", models.TextField(blank=True, null=True)),
                ("executed_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.account",
                    ),
                ),
                (
                    "case",
                    models.ForeignKey(
                        db_column="case_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bills",
                        to="billing.correctioncase",
                    ),
                ),
                (
                    "credit_note",
                    models.ForeignKey(
                        blank=True,
                        db_column="credit_note_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="billing.creditnote",
                    ),
                ),
                (
                    "goodwill_adjustment",
                    models.ForeignKey(
                        blank=True,
                        db_column="goodwill_adjustment_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="billing.adjustment",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        db_column="invoice_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="billing.invoice",
                    ),
                ),
                (
                    "rebill_invoice",
                    models.ForeignKey(
                        blank=True,
                        db_column="rebill_invoice_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="correction_rebill_rows",
                        to="billing.invoice",
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
                    "document_instance",
                    models.ForeignKey(
                        blank=True,
                        db_column="document_instance_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="billing.invoicedocumentinstance",
                    ),
                ),
            ],
            options={
                "db_table": "correction_case_bills",
            },
        ),
        migrations.AddIndex(
            model_name="correctioncase",
            index=models.Index(fields=["tenant", "status"], name="ix_corr_cases_status"),
        ),
        migrations.AddIndex(
            model_name="correctioncase",
            index=models.Index(fields=["tenant", "created_at"], name="ix_corr_cases_created"),
        ),
        migrations.AddConstraint(
            model_name="correctioncase",
            constraint=models.UniqueConstraint(
                condition=models.Q(("case_no__isnull", False)),
                fields=("tenant", "case_no"),
                name="uq_correction_cases_no",
            ),
        ),
        migrations.AddIndex(
            model_name="invoicedocumentinstance",
            index=models.Index(fields=["tenant", "invoice"], name="ix_doc_instances_invoice"),
        ),
        migrations.AddConstraint(
            model_name="invoicedocumentinstance",
            constraint=models.UniqueConstraint(
                fields=("tenant", "invoice", "instance_no"), name="uq_doc_instance_per_invoice"
            ),
        ),
        migrations.AddConstraint(
            model_name="invoicedocumentinstance",
            constraint=models.CheckConstraint(
                condition=models.Q(("instance_no__gte", 1)), name="ck_doc_instance_no_positive"
            ),
        ),
        migrations.AddIndex(
            model_name="correctioncasebill",
            index=models.Index(fields=["tenant", "case", "status"], name="ix_corr_bills_case"),
        ),
        migrations.AddIndex(
            model_name="correctioncasebill",
            index=models.Index(fields=["tenant", "invoice"], name="ix_corr_bills_invoice"),
        ),
        migrations.AddConstraint(
            model_name="correctioncasebill",
            constraint=models.UniqueConstraint(
                fields=("tenant", "case", "invoice"), name="uq_correction_case_bill"
            ),
        ),
        migrations.AddConstraint(
            model_name="correctioncasebill",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "queued")),
                fields=("tenant", "invoice"),
                name="uq_correction_bill_in_flight",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-016@c41f9a2 (ships with apps/billing/correction_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — DDL only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: APPLIED TO POSTGRES, not only to the SQLite test tier (DEF-064) — see
#         the lane report for the verbatim `migrate` output
# exceptions: (1) `invoice_document_instances` is not in Addendum r10 — it is
#         OQ-103's closure made into a table, an Eng-Lead DDL call under r10 #15.
#         (2) NO `invoices.corrects_invoice_id` — the PO ruled the rebill link
#         lives in the account-level history log (OQ-120, 2026-08-11).
#         (3) The append-only trigger on `invoice_document_instances` is in
#         0015 with the RLS, because both are policy-shaped 🔒 surfaces.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
