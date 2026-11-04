"""tenancy 0001 — W0 tables, first in the B2 §7 migration order. HUMAN-OWNED
(migration ordering is a CLAUDE.md 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), implementing the SIGNED
schema only: B2 §2 tenancy DDL + addenda r5 #1/#3, r6.0, r6.4, r9 #5, r12 #15,
r15, anchored on Addendum r16 (newest-wins) + the B11 18-item checklist —
NEVER raw §2/§3 (r16 #8). Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

Ordering law (B2 §7: platform → tenancy → identity → … → audit): this file
runs FIRST; identity 0001 depends on it. `user_preferences` (FK → users) is
deliberately NOT here — it lands in 0002_user_preferences after identity, the
B11 F-3 deferred-FK pass pattern for forward references.

Extensions: pgcrypto + citext created here (Postgres only — the sqlite test
DB gets plain tables; RLS/extension behavior is asserted by the G5 isolation
suite, never faked on sqlite). uuidv7 PK defaults are app-side (O-1 residue,
core/dbfields.py); pg_uuidv7 remains a deploy-time option (000_extensions.sql).

Seeds: the PLATFORM 10-service catalog (r5 #1 codes, BR-RAT-024 CONFIRMED) —
platform reference data, code-defined like the roles catalog. default_uom /
color stay NULL for the US-TEN-007 lane; nothing is invented.
"""

import apps.tenancy.models
import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from decimal import Decimal
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

# r5 #1 / BR-RAT-024 (CONFIRMED): the 10-service platform catalog, seed order
# as ruled. (code, name) — default_uom/color are the US-TEN-007 lane's fields.
SERVICE_SEED = [
    ("electric", "Electric"),
    ("water", "Water"),
    ("gas", "Gas"),
    ("sewer", "Sewer"),
    ("trash", "Trash"),
    ("storm_water", "Storm water"),
    ("solar", "Solar"),
    ("broadband", "Broadband"),
    ("thermal_heat", "Thermal/Heat"),
    ("battery", "Battery"),
]


def seed_services(apps_registry, schema_editor):
    """Idempotent platform seed (BR-TEN-012 spirit: upsert by code)."""
    service_model = apps_registry.get_model("tenancy", "Service")
    for sort, (code, name) in enumerate(SERVICE_SEED, start=1):
        service_model.objects.update_or_create(
            code=code, defaults={"name": name, "sort": sort, "active": True}
        )


def unseed_services(apps_registry, schema_editor):
    service_model = apps_registry.get_model("tenancy", "Service")
    service_model.objects.filter(code__in=[c for c, _ in SERVICE_SEED]).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # Postgres prerequisites (B2 §2 prerequisites block; citext for DB-15
        # email columns). No-op on sqlite by design — recorded, not hidden.
        PostgresOnlySQL(
            sql="CREATE EXTENSION IF NOT EXISTS pgcrypto;\n"
            "CREATE EXTENSION IF NOT EXISTS citext;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="Service",
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
                ("code", models.TextField(unique=True)),
                ("name", models.TextField()),
                ("default_uom", models.TextField(blank=True, null=True)),
                ("color", models.TextField(blank=True, null=True)),
                ("sort", models.IntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "services",
            },
        ),
        migrations.CreateModel(
            name="SubscriptionPlan",
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
                ("code", models.TextField(unique=True)),
                ("name", models.TextField()),
                ("price_month", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("min_accounts", models.IntegerField()),
                ("max_accounts", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "subscription_plans",
            },
        ),
        migrations.CreateModel(
            name="Tenant",
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
                ("subdomain", models.TextField(unique=True)),
                ("state", models.TextField(blank=True, null=True)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("tax_region", models.TextField(blank=True, null=True)),
                ("provisioned_at", models.DateTimeField(blank=True, null=True)),
                ("checklist_state", models.JSONField(blank=True, null=True)),
                ("legal_name", models.TextField(blank=True, null=True)),
                ("dba_name", models.TextField(blank=True, null=True)),
                ("ein", models.TextField(blank=True, null=True)),
                ("state_utility_id", models.TextField(blank=True, null=True)),
                ("mailing_address", models.TextField(blank=True, null=True)),
                ("support_phone", models.TextField(blank=True, null=True)),
                ("support_email", core.dbfields.CITextField(blank=True, null=True)),
                ("website", models.TextField(blank=True, null=True)),
                ("logo_file_id", models.TextField(blank=True, null=True)),
                ("brand_primary_hex", models.CharField(blank=True, max_length=7, null=True)),
                ("brand_accent_hex", models.CharField(blank=True, max_length=7, null=True)),
                ("remit_to_address", models.TextField(blank=True, null=True)),
                ("remit_payable_to", models.TextField(blank=True, null=True)),
                ("service_hours", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "tenants",
            },
        ),
        migrations.CreateModel(
            name="Subscription",
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
                ("status", models.TextField(default="trial")),
                ("trial_ends_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        db_column="plan_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.subscriptionplan",
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
                "db_table": "subscriptions",
            },
        ),
        migrations.CreateModel(
            name="TenantSettings",
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
                ("country", models.TextField(blank=True, null=True)),
                ("timezone", models.TextField(blank=True, null=True)),
                ("language", models.TextField(blank=True, null=True)),
                ("first_day_of_week", models.TextField(blank=True, null=True)),
                ("number_format", models.TextField(blank=True, null=True)),
                ("date_format", models.TextField(blank=True, null=True)),
                ("time_format", models.TextField(blank=True, null=True)),
                ("fy_start_month", models.IntegerField(blank=True, null=True)),
                ("fy_start_day", models.IntegerField(blank=True, null=True)),
                ("accounting_method", models.TextField(blank=True, null=True)),
                ("close_cadence", models.TextField(blank=True, null=True)),
                ("close_day", models.TextField(blank=True, null=True)),
                ("lock_closed_periods", models.BooleanField(default=False)),
                ("late_grace_mode", models.TextField(blank=True, null=True)),
                ("late_grace_days", models.IntegerField(blank=True, null=True)),
                (
                    "deposit_interest_rate_annual",
                    models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=18),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.OneToOneField(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "tenant_settings",
            },
        ),
        migrations.CreateModel(
            name="Uom",
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
                "db_table": "uoms",
            },
        ),
        migrations.CreateModel(
            name="TenantService",
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
                ("disabled_at", models.DateTimeField(blank=True, null=True)),
                (
                    "conversion_factor",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                (
                    "alt_uom",
                    models.ForeignKey(
                        blank=True,
                        db_column="alt_uom_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="alt_for_services",
                        to="tenancy.uom",
                    ),
                ),
                (
                    "billed_uom",
                    models.ForeignKey(
                        blank=True,
                        db_column="billed_uom_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billed_for_services",
                        to="tenancy.uom",
                    ),
                ),
                (
                    "primary_uom",
                    models.ForeignKey(
                        blank=True,
                        db_column="primary_uom_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="primary_for_services",
                        to="tenancy.uom",
                    ),
                ),
            ],
            options={
                "db_table": "tenant_services",
            },
        ),
        migrations.CreateModel(
            name="ReferenceSeedRun",
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
                ("list_code", models.TextField()),
                ("fixture_version", models.TextField()),
                ("seeded_count", models.IntegerField(default=0)),
                ("seeded_at", models.DateTimeField(auto_now_add=True)),
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
                "db_table": "reference_seed_runs",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "list_code", "fixture_version"), name="uq_seed_runs"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="NumberSeries",
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
                ("series", models.TextField()),
                ("format", models.TextField()),
                ("next_number", models.BigIntegerField(default=1)),
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
                "db_table": "number_series",
                "constraints": [
                    models.UniqueConstraint(fields=("tenant", "series"), name="uq_number_series"),
                    models.CheckConstraint(
                        condition=models.Q(("next_number__gte", 1)),
                        name="ck_number_series_next_ge_1",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Job",
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
                ("kind", models.TextField()),
                ("status", models.TextField(default="queued")),
                ("progress", models.JSONField(default=apps.tenancy.models.job_progress_default)),
                ("checkpoint", models.JSONField(blank=True, null=True)),
                ("result_link", models.TextField(blank=True, null=True)),
                ("error", models.TextField(blank=True, null=True)),
                ("scope_key", models.TextField(blank=True, null=True)),
                ("payload", models.JSONField(default=dict)),
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
                "db_table": "jobs",
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("status__in", ["queued", "running"]), ("scope_key__isnull", False)
                        ),
                        fields=("tenant", "kind", "scope_key"),
                        name="uq_jobs_active_scope",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="HolidayCalendar",
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
                ("holiday_date", models.DateField()),
                ("label", models.TextField()),
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
                "db_table": "holiday_calendars",
                "constraints": [
                    models.UniqueConstraint(fields=("tenant", "holiday_date"), name="uq_holidays")
                ],
            },
        ),
        migrations.CreateModel(
            name="BellEvent",
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
                ("event", models.TextField()),
                ("subject_type", models.TextField()),
                ("subject_id", models.TextField()),
                ("summary_key", models.TextField()),
                ("params", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
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
                "db_table": "bell_events",
                "indexes": [
                    models.Index(fields=["tenant", "-created_at"], name="ix_bell_tenant_created")
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="uom",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_uoms_tenant_code_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="tenantservice",
            constraint=models.UniqueConstraint(
                fields=("tenant", "service"), name="uq_tenant_services"
            ),
        ),
        # PLATFORM seed: 10-service catalog (r5 #1, BR-RAT-024 — code-defined
        # platform reference, same posture as the roles catalog in identity 0001).
        migrations.RunPython(seed_services, unseed_services),
    ]
