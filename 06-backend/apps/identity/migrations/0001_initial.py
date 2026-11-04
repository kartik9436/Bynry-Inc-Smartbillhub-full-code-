"""identity 0001 — W0 tables, second in the B2 §7 migration order (after
tenancy). HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), implementing the SIGNED
schema only: B2 §identity as REWRITTEN by Addendum r11 / r16 #2 — `users`
tenant-scoped with case-insensitive UNIQUE (tenant_id, email) (DB-13,
BR-IDN-029); `tenant_memberships` kept as the thin 1:1 role/lifecycle row
(Eng disposition on the r11 open half, recorded in the build report). Row per
file in 12-governance/09-human-review-ledger.md; not RATIFIED without human
sign-off.

Seeds: the 3 predefined platform roles (A4 addendum, BR-IDN-008 CONFIRMED —
System Admin / Billing Clerk / Executive; codes are Eng naming, flagged).
Permission rows + role_permissions content (the 9×3 A4 matrix) land with the
US-IDN-007 lane — the matrix CELL values have no B2 column, reported not
invented.

RLS: users + tenant_memberships get ENABLE+FORCE in 0002_rls_w0_policies
(r16 #2 voids the stale §3 no-RLS listing for users); roles / permissions /
role_permissions are platform catalog — RLS-exempt per B2 §3.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

# A4 addendum (settles O-5): exactly three predefined platform roles.
ROLE_SEED = [
    ("system_admin", "System Admin"),
    ("billing_clerk", "Billing Clerk"),
    ("executive", "Executive"),
]


def seed_roles(apps_registry, schema_editor):
    """Idempotent platform seed (upsert by code)."""
    role_model = apps_registry.get_model("identity", "Role")
    for code, name in ROLE_SEED:
        role_model.objects.update_or_create(code=code, defaults={"name": name})


def unseed_roles(apps_registry, schema_editor):
    role_model = apps_registry.get_model("identity", "Role")
    role_model.objects.filter(code__in=[c for c, _ in ROLE_SEED]).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Permission",
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
                ("description", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "permissions",
            },
        ),
        migrations.CreateModel(
            name="Role",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "roles",
            },
        ),
        migrations.CreateModel(
            name="User",
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
                ("email", core.dbfields.CITextField()),
                ("full_name", models.TextField(default="")),
                ("phone", models.TextField(blank=True, null=True)),
                ("password_hash", models.TextField(blank=True, null=True)),
                ("must_change_password", models.BooleanField(default=False)),
                ("temp_password_expires_at", models.DateTimeField(blank=True, null=True)),
                ("password_changed_at", models.DateTimeField(blank=True, null=True)),
                ("pending_email", core.dbfields.CITextField(blank=True, null=True)),
                ("ui_language", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
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
                "db_table": "users",
            },
        ),
        migrations.CreateModel(
            name="TenantMembership",
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
                ("status", models.TextField(default="invited")),
                ("invited_at", models.DateTimeField(blank=True, null=True)),
                ("last_active_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role",
                    models.ForeignKey(
                        db_column="role_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.role",
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
                    "invited_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="invited_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="memberships_invited",
                        to="identity.user",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "tenant_memberships",
            },
        ),
        migrations.CreateModel(
            name="RolePermission",
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
                    "permission",
                    models.ForeignKey(
                        db_column="permission_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.permission",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        db_column="role_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.role",
                    ),
                ),
            ],
            options={
                "db_table": "role_permissions",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("role", "permission"), name="uq_role_permissions"
                    )
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("email"),
                name="uq_users_tenant_email_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="tenantmembership",
            constraint=models.UniqueConstraint(
                fields=("tenant", "user"), name="uq_tenant_memberships"
            ),
        ),
        # PLATFORM seed: the 3 predefined roles (A4 addendum, BR-IDN-008).
        migrations.RunPython(seed_roles, unseed_roles),
    ]
