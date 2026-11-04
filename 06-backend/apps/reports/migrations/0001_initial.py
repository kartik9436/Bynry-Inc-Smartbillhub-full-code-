"""reports 0001 — the three tables the Reports module owns. RLS follows in 0002.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`
guards every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-26 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md`, shared with `0002_rls_force` and
`0003_seed_catalogue` because a reviewer of this wall wants the tables, the
policy and what is seeded into them in front of them at once. None of the three
is RATIFIED without a recorded sign-off.

`CR-142-BRC07` Phase 0 · `P0.1` · `P0.2` · `P0.3`.

THREE NEW TABLES AND NOT ONE EXISTING COLUMN ALTERED
─────────────────────────────────────────────────────
`report_definitions` · `report_categories` · `report_tenant_settings`. The
reports module has never had a table at all — `apps/reports/migrations/`
contained only `__init__.py` before this file. Nothing this migration does can
break a running product, because nothing reads these tables yet: `GET /reports`
still serves `apps/reports/catalog.py`'s tuple and Phase 0 deliberately does not
switch it (see that file's amended docstring, and `P1.1`, which owns the switch
together with the catalogue screen that renders the result).

⚠ `report_schedules` IS NOT HERE. `CR-142` §3 lists four tables; the fourth is
phase 5's and a lane adding it now would be building past the phase boundary.

⚠ `report_runs` IS NOT HERE AND NEVER WILL BE. §05 of the brief: an export
inserts a `jobs` row in tenancy and *"the job record IS the run record"*. A
second table recording the same act is two answers to one question.

WHAT THE THREE COLUMNS THAT LOOK ODD ARE FOR
────────────────────────────────────────────
`report_definitions.tenant_id` and `report_categories.tenant_id` are
**NULLABLE**, and a NULL is a PLATFORM row: shipped by us, readable by every
tenant, writable by none. That is the copy-on-write mechanism the whole
framework rests on and it is why `0002`'s policy on these two tables is not the
policy every other tenant table in this product takes. `report_tenant_settings`
is the ordinary shape — an overlay is always somebody's.

`report_definitions.visibility` is a **CHECK constraint** and the category list
is a **TABLE**, which is the brief's own ⚠ on `P0.1`: a CHECK makes a third
value a migration, which is right for a signed two-value enum (who may see a
report is a security statement) and wrong for a catalogue grouping a utility
must be able to extend without a release.

MONEY AND UNITS (CLAUDE.md hard rules 2 and 3)
──────────────────────────────────────────────
**No money column and no quantity column is created here**, deliberately.
Reports owns no business data — every number on every one of the 46 definitions
is somebody else's row, read through a seam. Where money precision and units ARE
expressed is `apps/reports/datasets.py`, whose `_validate()` refuses at import a
quantity column with no unit and a money column with no date basis.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportCategory",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("name_i18n", models.JSONField(blank=True, default=dict)),
                ("parent_code", models.TextField(blank=True, null=True)),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        db_column="tenant_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "report_categories"},
        ),
        migrations.CreateModel(
            name="ReportDefinition",
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
                ("key", models.TextField()),
                ("name", models.TextField()),
                ("name_i18n", models.JSONField(blank=True, default=dict)),
                ("dataset", models.TextField()),
                ("group_code", models.TextField()),
                ("sub_group_code", models.TextField(blank=True, null=True)),
                ("columns", models.JSONField(blank=True, default=list)),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("group_by", models.JSONField(blank=True, default=list)),
                ("sort", models.JSONField(blank=True, default=list)),
                ("service_codes", models.JSONField(blank=True, default=list)),
                ("visibility", models.TextField(default="shared")),
                ("owner_user_id", models.UUIDField(blank=True, null=True)),
                ("version", models.IntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        db_column="tenant_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "report_definitions"},
        ),
        migrations.CreateModel(
            name="ReportTenantSetting",
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
                ("enabled", models.BooleanField(default=True)),
                ("pinned", models.BooleanField(default=False)),
                ("display_order", models.IntegerField(default=0)),
                ("name_override", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "definition",
                    models.ForeignKey(
                        db_column="definition_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tenant_settings",
                        to="reports.reportdefinition",
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
            options={"db_table": "report_tenant_settings"},
        ),
        migrations.AddIndex(
            model_name="reportcategory",
            index=models.Index(
                fields=["tenant", "parent_code"], name="ix_rep_cat_tenant_parent"
            ),
        ),
        migrations.AddConstraint(
            model_name="reportcategory",
            constraint=models.UniqueConstraint(
                fields=("tenant", "code"), name="uq_report_categories_tenant_code"
            ),
        ),
        migrations.AddConstraint(
            model_name="reportcategory",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tenant__isnull", True)),
                fields=("code",),
                name="uq_report_categories_platform_code",
            ),
        ),
        migrations.AddIndex(
            model_name="reportdefinition",
            index=models.Index(
                fields=["tenant", "dataset"], name="ix_rep_def_tenant_dataset"
            ),
        ),
        migrations.AddIndex(
            model_name="reportdefinition",
            index=models.Index(
                fields=["tenant", "group_code"], name="ix_rep_def_tenant_group"
            ),
        ),
        migrations.AddConstraint(
            model_name="reportdefinition",
            constraint=models.UniqueConstraint(
                fields=("tenant", "key"), name="uq_report_definitions_tenant_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="reportdefinition",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tenant__isnull", True)),
                fields=("key",),
                name="uq_report_definitions_platform_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="reportdefinition",
            constraint=models.CheckConstraint(
                check=models.Q(visibility__in=("private", "shared")),
                name="ck_report_definitions_visibility",
            ),
        ),
        migrations.AddConstraint(
            model_name="reporttenantsetting",
            constraint=models.UniqueConstraint(
                fields=("tenant", "definition"),
                name="uq_report_tenant_settings_tenant_definition",
            ),
        ),
    ]
