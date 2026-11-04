"""tenancy 0055 — `job_artifacts`, the record of one export file, and its isolation.

HUMAN-OWNED (RLS policies AND migration ordering are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

PO ruling 2026-10-02 (decision log, *"EXPORT FILES MOVE FROM THE SHARED DISK TO
S3 — THE DESIGN IS APPROVED"*): *"A database record per export file: which
utility, its exact storage path, file name, size and status"*, in a
tenant-scoped table with FORCE row-level security. Why it is not a
`stored_documents` row is in `apps/tenancy/export_models.py`.

THE POLICY LANDS WITH THE TABLE (CLAUDE.md rule 1, DEF-027's lesson): the
CreateModel and the B2 §3 policy are one migration, taken from
`core.rls.tenant_isolation_policy_sql` — not one character of the predicate is
this lane's. Unlike 0026 there is NO write-once trigger: a row moves
pending → stored → deleted, and that is the point of having it.

POSTGRES ONLY for the policy (SQLite has no RLS); the isolation is proved on a
live cluster as a NOSUPERUSER NOBYPASSRLS role in
tests/test_s3a_job_artifacts.py.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields
from core.migrationtools import PostgresOnlySQL
from core.rls import tenant_isolation_policy_sql

POLICY_SQL = tenant_isolation_policy_sql("job_artifacts")
REVERSE_POLICY_SQL = """
DROP POLICY IF EXISTS job_artifacts_tenant_isolation ON job_artifacts;
ALTER TABLE job_artifacts NO FORCE ROW LEVEL SECURITY;
ALTER TABLE job_artifacts DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0054_def_not_8450_twelve_message_kinds"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobArtifact",
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
                ("tenant_folder", models.TextField()),
                ("storage_key", models.TextField()),
                ("storage_backend", models.TextField()),
                ("display_name", models.TextField()),
                ("content_type", models.TextField()),
                ("byte_length", models.BigIntegerField(blank=True, null=True)),
                ("content_hash", models.TextField(blank=True, null=True)),
                ("status", models.TextField(default="pending")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("stored_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by_process", models.TextField(blank=True, null=True)),
                (
                    "job",
                    models.OneToOneField(
                        db_column="job_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="artifact",
                        to="tenancy.job",
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
                "db_table": "job_artifacts",
                "indexes": [
                    models.Index(
                        fields=["tenant", "status", "created_at"], name="ix_job_artifacts_sweep"
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ("pending", "stored", "deleted"))),
                        name="ck_job_artifacts_status",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("storage_key__regex", "^t/[a-z0-9][a-z0-9-]{1,61}[a-z0-9]/export/")
                        ),
                        name="ck_job_artifacts_export_key",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("status", "stored"), _negated=True),
                            models.Q(
                                ("byte_length__isnull", False),
                                ("content_hash__isnull", False),
                                ("stored_at__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="ck_job_artifacts_stored_facts",
                    ),
                    models.UniqueConstraint(
                        fields=("tenant", "storage_key"), name="uq_job_artifacts_key"
                    ),
                ],
            },
        ),
        # CLAUDE.md rule 1 — the policy lands WITH the table. B2 §3's signed
        # template via core.rls.
        PostgresOnlySQL(sql=POLICY_SQL, reverse_sql=REVERSE_POLICY_SQL),
    ]
