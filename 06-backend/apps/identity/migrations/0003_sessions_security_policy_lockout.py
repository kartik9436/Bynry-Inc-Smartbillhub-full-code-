"""identity 0003 — EP-IDN service-lane tables/columns, story-anchored only.
HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), implementing the
story-anchored PROPOSED-SCHEMA shapes VERBATIM, nothing invented:
- `users.failed_attempts` + `users.locked_until` — US-IDN-001 §5 lockout
  counter (BR-IDN-025: 5 failed → 15-minute lock).
- `sessions` — US-IDN-003 §5 platform table (id, user_id, tenant_id,
  persistent, created_at, last_seen_at, expires_at, revoked_at, ip inet,
  user_agent). RLS-EXEMPT per that mapping ("platform table"): the row must
  be readable to ESTABLISH tenant context; tenant binding is enforced in the
  auth layer (BR-IDN-006) and probed by the G5 isolation suite.
- `security_policies` — US-IDN-010 §5 tenant-scoped record, one row per
  tenant (OneToOne = UNIQUE(tenant_id)); RLS lands in 0004 (🔒 file).
  `ip_allowlist` anchored `cidr[]` is Postgres-only — stored as JSON list of
  CIDR strings for the two-vendor W0 lane (Eng disposition, models docstring).
- Seeds the 9 A4-addendum permission rows and the non-"—" cells as
  `role_permissions` memberships (US-IDN-007 lane — the identity 0001
  docstring left exactly this to this lane). The matrix CELL VALUES have no
  B2 column (gap reported, not invented) — they render from models.A4_MATRIX,
  which transcribes the signed A4 grid.

Row per file in 12-governance/09-human-review-ledger.md; not RATIFIED
without human sign-off.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields

# A4 addendum grid seed — duplicated from models.A4_MATRIX by design (Django
# migrations never import live models; historical copies are the convention).
PERMISSION_SEED = [
    ("settings_lookups", "Settings & lookup tables"),
    ("user_management", "User management"),
    ("plans_rates", "Plans & Rates"),
    ("premises_accounts", "Premises / Accounts"),
    ("reads_billing_runs", "Reads & Billing runs"),
    ("payments_record", "Payments (record)"),
    ("adjustment_approval", "Adjustment / write-off approval"),
    ("finance_reconcile_export", "Finance / reconcile / export"),
    ("reports", "Reports"),
]
# (permission_code, role_code) pairs for every non-"—" A4 cell.
ROLE_PERMISSION_SEED = [
    ("settings_lookups", "system_admin"),
    ("settings_lookups", "executive"),
    ("user_management", "system_admin"),
    ("plans_rates", "system_admin"),
    ("plans_rates", "billing_clerk"),
    ("plans_rates", "executive"),
    ("premises_accounts", "system_admin"),
    ("premises_accounts", "billing_clerk"),
    ("premises_accounts", "executive"),
    ("reads_billing_runs", "system_admin"),
    ("reads_billing_runs", "billing_clerk"),
    ("reads_billing_runs", "executive"),
    ("payments_record", "system_admin"),
    ("payments_record", "billing_clerk"),
    ("payments_record", "executive"),
    ("adjustment_approval", "system_admin"),
    ("adjustment_approval", "billing_clerk"),
    ("adjustment_approval", "executive"),
    ("finance_reconcile_export", "system_admin"),
    ("finance_reconcile_export", "executive"),
    ("reports", "system_admin"),
    ("reports", "billing_clerk"),
    ("reports", "executive"),
]


def seed_permissions(apps_registry, schema_editor):
    """Idempotent platform seed (upsert by code) — BR-IDN-014 catalog rows."""
    permission_model = apps_registry.get_model("identity", "Permission")
    role_model = apps_registry.get_model("identity", "Role")
    role_permission_model = apps_registry.get_model("identity", "RolePermission")
    for code, description in PERMISSION_SEED:
        permission_model.objects.update_or_create(code=code, defaults={"description": description})
    for permission_code, role_code in ROLE_PERMISSION_SEED:
        role_permission_model.objects.get_or_create(
            permission=permission_model.objects.get(code=permission_code),
            role=role_model.objects.get(code=role_code),
        )


def unseed_permissions(apps_registry, schema_editor):
    permission_model = apps_registry.get_model("identity", "Permission")
    role_permission_model = apps_registry.get_model("identity", "RolePermission")
    codes = [c for c, _ in PERMISSION_SEED]
    role_permission_model.objects.filter(permission__code__in=codes).delete()
    permission_model.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0002_rls_w0_policies"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="failed_attempts",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="locked_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="Session",
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
                ("persistent", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, null=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sessions",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "sessions",
            },
        ),
        migrations.CreateModel(
            name="SecurityPolicy",
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
                ("pw_min_length", models.IntegerField(default=8)),
                ("pw_require_mixed", models.BooleanField(default=True)),
                ("pw_require_symbol", models.BooleanField(default=False)),
                ("pw_expiry_days", models.IntegerField(blank=True, null=True)),
                ("session_timeout_minutes", models.IntegerField(default=60)),
                ("ip_allowlist", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.OneToOneField(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="security_policy",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "security_policies",
            },
        ),
        # PLATFORM seed: the 9 A4 permission rows + non-"—" cells (BR-IDN-014).
        migrations.RunPython(seed_permissions, unseed_permissions),
    ]
