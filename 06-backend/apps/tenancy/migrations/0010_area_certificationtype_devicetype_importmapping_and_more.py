# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009/010/011 (the reference-data grid and the ONE list view
#           these six lists plug into)   Screens: S8 / r10 SET-04
# Rules:    BR-TEN-030 (code unique per tenant, case-insensitive) ·
#           BR-TEN-031 (framework is tenancy's, content belongs to the owner) ·
#           BR-TEN-034 (audit-lock) · BR-TEN-036 (seeded, tenant-extensible) ·
#           BR-TEN-046 / CLAUDE.md rule 1 (tenant tables carry RLS FORCE) ·
#           B2 §3 policy template · B2 §7 (RLS immediately after each table)
# ───────────────────────────────────────────────────────
"""tenancy 0010 — CR-004: the six r10 SET-04 reference tables, + RLS.

HUMAN-OWNED in part (RLS policies are a CLAUDE.md rule-1 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-16 under PO ruling 2026-08-09 ("AI
will do it; we will review it later as human"). The policy text is the SIGNED
B2 §3 template applied verbatim and lives in
06-backend/db/rls_tenancy_cr004_reference_lists.sql, reviewable in one place —
the posture tenancy 0003 established and 0008 followed. Row in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

The tables are hosted here and owned elsewhere (BR-TEN-031): apps/metering and
apps/assets author no lookup CRUD, so each list had a design, a vocabulary from
prototype r10, and nowhere to put a row. Hosting is not owning — when an owning
lane lands it re-homes its table in one migration and the card keeps naming the
true owner throughout, exactly as reason_codes and payment_methods do today.

RLS IS IN THIS MIGRATION AND NOT A LATER ONE, deliberately. B2 §7 wants the
policy immediately after the table: a window in which six tenant-scoped tables
exist unprotected is a window in which a deploy can land, and 'we will add the
policy next' is how hard rule 1 gets broken by scheduling rather than by
intent.

Postgres only: the sqlite test DB cannot exercise RLS — skipped honestly. The
live cross-tenant probes are the G5 isolation suite's job (NFR-10, zero
tolerance, release blocker); tests/test_tenant_isolation.py sweeps every
tenant-scoped table rather than a hand-kept list, so it fails on a table that
reaches the schema without a policy.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Lower

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0009_sample_data_runs"),
    ]

    operations = [
        migrations.CreateModel(
            name="Area",
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
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
            ],
            options={
                "db_table": "areas",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_areas_tenant_code_ci",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="CertificationType",
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
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
            ],
            options={
                "db_table": "certification_types",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_certification_types_tenant_code_ci",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="DeviceType",
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
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
            ],
            options={
                "db_table": "device_types",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_device_types_tenant_code_ci",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ImportMapping",
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
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
            ],
            options={
                "db_table": "import_mappings",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_import_mappings_tenant_code_ci",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MeterSizeClass",
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
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
            ],
            options={
                "db_table": "meter_size_classes",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_meter_size_classes_tenant_code_ci",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="OccupancyStatus",
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
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
            ],
            options={
                "db_table": "occupancy_statuses",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_occupancy_statuses_tenant_code_ci",
                    )
                ],
            },
        ),
        PostgresOnlySQL(
            sql=load_db_sql("rls_tenancy_cr004_reference_lists.sql"),
            reverse_sql=migrations.RunSQL.noop,  # policies are never rolled back silently
        ),
    ]
