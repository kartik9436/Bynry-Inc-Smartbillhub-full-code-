"""billing 0042 — `correction_jobs` + `correction_job_bills` (`DEF-BIL-10091`).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering and an RLS policy are
CLAUDE.md 🔒 paths. AI-authored 2026-10-13 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

WHAT IT ADDS. A bulk Fix a bill preview, Send and Approve-and-issue each took
about three minutes on 38 bills, against a sixty-second web worker; decision
log 2026-10-13 moves all three into background jobs with progress on screen.
The job kernel's `jobs` row carries status and progress; `correction_jobs`
carries what one act is about and what it produced, and
`correction_job_bills` holds a preview's per-bill rows so a page is one
indexed read (`NFR-3`). See `correction_models.CorrectionJob`.

NO MONEY. Nothing here posts, issues or allocates; the figures are a preview's,
as `correction_cases.preview` already holds them after Send.

THE POLICY IS THE SIGNED B2 §3 TEMPLATE, VERBATIM — ENABLE + FORCE,
`tenant_id = current_setting('app.tenant_id')`, the shape of `0041`.

DOWN PATH. Reversible: dropping both tables loses only previews and the record
of which job opened or issued a case; every case, bill and figure lives on the
correction tables.

Postgres only for the policy: SQLite has no RLS.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

TABLES = ("correction_jobs", "correction_job_bills")


def _policy(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""


def _drop(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


def apply_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(_policy(table))


def drop_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(_drop(table))


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0041_cr180_correction_case_items"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorrectionJob",
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
                ("job_id", models.UUIDField(blank=True, null=True)),
                ("act", models.TextField()),
                ("scope", models.JSONField(default=dict)),
                ("items", models.JSONField(default=list)),
                ("as_of", models.DateField(blank=True, null=True)),
                ("preview_hash", models.TextField(blank=True, null=True)),
                ("answer", models.JSONField(blank=True, null=True)),
                ("built", models.JSONField(blank=True, null=True)),
                ("refusal", models.JSONField(blank=True, null=True)),
                ("result", models.JSONField(blank=True, null=True)),
                ("created_by_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "case",
                    models.ForeignKey(
                        blank=True,
                        db_column="case_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="billing.correctioncase",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        db_column="source_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="billing.correctionjob",
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
                "db_table": "correction_jobs",
            },
        ),
        migrations.CreateModel(
            name="CorrectionJobBill",
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
                ("position", models.IntegerField()),
                ("seq", models.IntegerField()),
                ("invoice_id", models.UUIDField()),
                ("row", models.JSONField(default=dict)),
                ("impact", models.JSONField(default=dict)),
                (
                    "job",
                    models.ForeignKey(
                        db_column="correction_job_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bills",
                        to="billing.correctionjob",
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
                "db_table": "correction_job_bills",
            },
        ),
        migrations.AddIndex(
            model_name="correctionjob",
            index=models.Index(fields=["tenant", "job_id"], name="ix_corr_jobs_job"),
        ),
        migrations.AddIndex(
            model_name="correctionjob",
            index=models.Index(fields=["tenant", "case"], name="ix_corr_jobs_case"),
        ),
        migrations.AddConstraint(
            model_name="correctionjob",
            constraint=models.CheckConstraint(
                condition=models.Q(("act__in", ("preview", "send", "approve_issue"))),
                name="ck_correction_job_act",
            ),
        ),
        migrations.AddConstraint(
            model_name="correctionjobbill",
            constraint=models.UniqueConstraint(
                fields=("tenant", "job", "position"), name="uq_correction_job_bill_position"
            ),
        ),
        migrations.RunPython(apply_policy, drop_policy),
    ]
