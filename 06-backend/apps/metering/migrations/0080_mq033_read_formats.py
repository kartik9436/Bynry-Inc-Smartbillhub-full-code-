"""metering 0080 — MQ-033 utility-defined meter-read FORMATS (`CR-192-BRC10`,
task 10 of 13, lane MQ033-SERVER, 2026-10-24).

HUMAN-OWNED (migration ordering and RLS are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-24 under the PO ruling of
2026-08-09; the `12-governance/09-human-review-ledger.md` row is written in
the same commit.

FIVE NEW TABLES, EACH WITH ONE RLS POLICY (ENABLE + FORCE), THREE NULLABLE
COLUMNS ON EXISTING TABLES, NO BACKFILL, NOTHING SEEDED.

  * `read_formats`          — a utility's named format for one service.
  * `read_format_versions`  — the questions as they stood; immutable once
                              published (enforced by the service), at most
                              one draft per format (partial unique).
  * `read_format_questions` — the questions of one version.
  * `read_format_defaults`  — the per-service default, unique per service.
  * `read_answers`          — one answer per (field reading, question),
                              stamped with its version.
  * `routes.read_format_id`, `cycles.read_format_id` — nullable pointers
    (*"route → cycle → service"*). NULL is what every existing row gets, which
    is exactly "no format": a route reads as it did before.
  * `field_reads.read_format_version_id` + `answers_need_review` (default
    false) — the stamp and the flag.

PO, verbatim: *"this is all user defined we dont have to provide anything
readymade"* — so no data migration, no sample format, no sample question.
"""


import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: The same expression every other policy in this module uses (0077, 0079).
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
TABLES = (
    "read_formats",
    "read_format_versions",
    "read_format_questions",
    "read_format_defaults",
    "read_answers",
)


def _policy(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""


def _reverse(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0015_field_app_pins"),
        ("metering", "0079_cr187_field_read_photos"),
        ("tenancy", "0066_def_cus_10445_service_request_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="fieldread",
            name="answers_need_review",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="ReadFormat",
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
                ("name", models.TextField()),
                ("status", models.TextField(default="draft")),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="created_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        db_column="service_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
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
                "db_table": "read_formats",
            },
        ),
        migrations.AddField(
            model_name="cycle",
            name="read_format",
            field=models.ForeignKey(
                blank=True,
                db_column="read_format_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="metering.readformat",
            ),
        ),
        migrations.AddField(
            model_name="route",
            name="read_format",
            field=models.ForeignKey(
                blank=True,
                db_column="read_format_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="metering.readformat",
            ),
        ),
        migrations.CreateModel(
            name="ReadFormatVersion",
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
                ("state", models.TextField(default="draft")),
                ("version_no", models.IntegerField(blank=True, null=True)),
                ("change_note", models.TextField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "published_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="published_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "read_format",
                    models.ForeignKey(
                        db_column="read_format_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="versions",
                        to="metering.readformat",
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
                "db_table": "read_format_versions",
            },
        ),
        migrations.CreateModel(
            name="ReadFormatQuestion",
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
                ("seq", models.IntegerField(default=0)),
                ("key", models.TextField()),
                ("label", models.TextField()),
                ("help_text", models.TextField(blank=True, null=True)),
                ("data_type", models.TextField()),
                ("options", models.JSONField(blank=True, null=True)),
                ("is_required", models.BooleanField(default=False)),
                ("asked_when", models.TextField(default="every_reading")),
                ("show_if", models.JSONField(blank=True, null=True)),
                ("raise_work", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        db_column="version_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="metering.readformatversion",
                    ),
                ),
            ],
            options={
                "db_table": "read_format_questions",
            },
        ),
        migrations.AddField(
            model_name="readformat",
            name="current_version",
            field=models.ForeignKey(
                blank=True,
                db_column="current_version_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="metering.readformatversion",
            ),
        ),
        migrations.CreateModel(
            name="ReadAnswer",
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
                ("question_key", models.TextField()),
                ("value", models.JSONField(blank=True, null=True)),
                ("value_text", models.TextField(blank=True, null=True)),
                ("photo_id", models.UUIDField(blank=True, null=True)),
                ("issue", models.TextField(blank=True, null=True)),
                ("work_finding_key", models.TextField(blank=True, null=True)),
                ("work_order_id", models.UUIDField(blank=True, null=True)),
                ("work_order_no", models.TextField(blank=True, null=True)),
                ("work_raise_error", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "field_read",
                    models.ForeignKey(
                        db_column="field_read_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="metering.fieldread",
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
                    "version",
                    models.ForeignKey(
                        blank=True,
                        db_column="version_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="metering.readformatversion",
                    ),
                ),
            ],
            options={
                "db_table": "read_answers",
            },
        ),
        migrations.AddField(
            model_name="fieldread",
            name="read_format_version",
            field=models.ForeignKey(
                blank=True,
                db_column="read_format_version_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="metering.readformatversion",
            ),
        ),
        migrations.CreateModel(
            name="ReadFormatDefault",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "read_format",
                    models.ForeignKey(
                        db_column="read_format_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="metering.readformat",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        db_column="service_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
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
                "db_table": "read_format_defaults",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "service"), name="uq_read_format_defaults_service"
                    )
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="readformatversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("state__in", ("draft", "published"))),
                name="ck_read_format_versions_state",
            ),
        ),
        migrations.AddConstraint(
            model_name="readformatversion",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("published_at__isnull", True),
                        ("state", "draft"),
                        ("version_no__isnull", True),
                    ),
                    models.Q(
                        ("published_at__isnull", False),
                        ("state", "published"),
                        ("version_no__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="ck_read_format_versions_published",
            ),
        ),
        migrations.AddConstraint(
            model_name="readformatversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("version_no__isnull", False)),
                fields=("read_format", "version_no"),
                name="uq_read_format_versions_no",
            ),
        ),
        migrations.AddConstraint(
            model_name="readformatversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("state", "draft")),
                fields=("read_format",),
                name="uq_read_format_versions_one_draft",
            ),
        ),
        migrations.AddIndex(
            model_name="readformatquestion",
            index=models.Index(fields=["version", "seq"], name="ix_read_format_questions_seq"),
        ),
        migrations.AddConstraint(
            model_name="readformatquestion",
            constraint=models.UniqueConstraint(
                fields=("version", "key"), name="uq_read_format_questions_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="readformatquestion",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "asked_when__in",
                        ("every_reading", "out_of_range", "cant_read", "once_per_stop"),
                    )
                ),
                name="ck_read_format_questions_asked_when",
            ),
        ),
        migrations.AddIndex(
            model_name="readformat",
            index=models.Index(
                fields=["tenant", "service", "status"], name="ix_read_formats_service"
            ),
        ),
        migrations.AddConstraint(
            model_name="readformat",
            constraint=models.UniqueConstraint(
                fields=("tenant", "name"), name="uq_read_formats_name"
            ),
        ),
        migrations.AddConstraint(
            model_name="readformat",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ("draft", "published", "retired"))),
                name="ck_read_formats_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="readformat",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("current_version__isnull", True), ("status", "draft")),
                    models.Q(
                        ("current_version__isnull", False), ("status__in", ("published", "retired"))
                    ),
                    _connector="OR",
                ),
                name="ck_read_formats_current_version",
            ),
        ),
        migrations.AddIndex(
            model_name="readanswer",
            index=models.Index(
                fields=["tenant", "question_key", "value_text"], name="ix_read_answers_filter"
            ),
        ),
        migrations.AddConstraint(
            model_name="readanswer",
            constraint=models.UniqueConstraint(
                fields=("field_read", "question_key"), name="uq_read_answers_question"
            ),
        ),
        migrations.AddConstraint(
            model_name="readanswer",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("issue__isnull", True),
                    (
                        "issue__in",
                        (
                            "unknown_question",
                            "wrong_type",
                            "not_an_option",
                            "not_asked",
                            "not_shown",
                            "required_missing",
                            "version_unknown",
                        ),
                    ),
                    _connector="OR",
                ),
                name="ck_read_answers_issue",
            ),
        ),
        *[PostgresOnlySQL(_policy(t), reverse_sql=_reverse(t)) for t in TABLES],
    ]
