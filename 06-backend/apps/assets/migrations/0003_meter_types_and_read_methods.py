"""assets 0003 — the BR-AST-043 reference catalogs: `meter_types` + `read_methods`,
their RLS ENABLE+FORCE, and the rewire of `assets.read_method` from a plain value
to a PROTECTed FK. HUMAN-OWNED (migration ordering AND RLS policies are CLAUDE.md
rule-1 🔒 paths).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing the SIGNED rule
BR-AST-043 (CONFIRMED, PO 2026-08-09) and applying the SIGNED B2 §3 policy template
verbatim from the marked section of 06-backend/db/rls_assets_w1.sql. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

WHY IT EXISTS: the S8 Reference-data card grid has always ratified a "Meter types"
card with five entries (US-TEN-009 TC-1; prototype values AMI, AMR, walk-by,
sub-meter, master) and tenancy's LOOKUP_LISTS has always declared `meter_types` —
but no table ever existed, so the card was dead. OQ-031 CLOSED → BR-TEN-036 makes
enum-backed reference lists real tenant-scoped tables. BR-AST-043 then splits the
concern in two: meter_types = what the meter IS; read_methods = how the read is
COLLECTED (AMI · AMR · walk-by · Manual · Mobile) — and points `assets.read_method`
at the second catalog, superseding B2 r4's plain value. Neither list is B2's
`meter_source` enum ('ami','manual','import'), which stays on `meter_reads` (W2).

⚠ FOR THE REVIEWER — three things worth your eyes:
1. The read_method rewire is done data-preservingly: rename to `read_method_legacy`,
   add the FK, map values, drop the legacy column. The map is ami→AMI, amr→AMR,
   walk_by→walk-by ONLY. B2 r4's fourth plain value 'na' has no counterpart in the
   PO's ratified five, so an asset carrying it lands NULL and is logged, never
   silently mapped onto a method the rule does not name.
2. The data step runs UNDER RLS: it enumerates tenants from the RLS-exempt platform
   table and sets `app.tenant_id` per tenant before touching any tenant table
   (CLAUDE.md rule 1). On sqlite the set_config calls are skipped — there is no RLS
   there — and the same ORM path runs.
3. The seed set is duplicated here rather than imported from apps.assets.services:
   a migration must keep working when the service's constants later change. Both
   copies carry the SAME ratified values (BR-AST-043); if they ever diverge, the
   rule is the tiebreaker, not either copy.

Postgres-only for the policy half — live isolation proofs run in the G5 suite
(NFR-10, zero tolerance, release blocker).
"""

import logging

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql

logger = logging.getLogger("smartbillhub.assets")

# The policy text lives in ONE reviewable file; 0002 applies everything above the
# marker, this migration everything below it. ValueError here = someone deleted the
# marker: fix the SQL file, never the slice.
SECTION_MARKER = "-- >>> ASSETS-0003 <<<"
_POLICY_FILE = load_db_sql("rls_assets_w1.sql")
CATALOG_POLICIES = _POLICY_FILE[_POLICY_FILE.index(SECTION_MARKER) + len(SECTION_MARKER) :]

# BR-AST-043 CONFIRMED — the ratified five per list, names verbatim from the rule
# (which carries the prototype's own casing). Mirrored in apps/assets/services.py.
SEED_METER_TYPES = (
    ("ami", "AMI"),
    ("amr", "AMR"),
    ("walk_by", "walk-by"),
    ("sub_meter", "sub-meter"),
    ("master", "master"),
)
SEED_READ_METHODS = (
    ("ami", "AMI"),
    ("amr", "AMR"),
    ("walk_by", "walk-by"),
    ("manual", "Manual"),
    ("mobile", "Mobile"),
)
# B2 r4 carried read_method as free text 'ami | amr | walk_by | na'. Only the three
# the ratified catalog also names are mapped; 'na' (and anything a tenant typed) is
# reported and left NULL — inventing a target would be answering an unasked question.
LEGACY_READ_METHOD_MAP = {"ami": "ami", "amr": "amr", "walk_by": "walk_by"}


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table (db/rls_tenancy_w0.sql), so it can
    be enumerated before any tenant context exists."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    """CLAUDE.md rule 1: never touch a tenant table without app.tenant_id set. On
    sqlite (the test DB) there is no RLS and no set_config — skipped honestly."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


# ⚠ AMENDED 2026-08-24 — OQ-354, RULED BY THE PO, OPTION (A). This is one of
# THREE identical call sites (the others are `metering.0016_br_met_101_common_area`
# and `tenancy.0004_settings_families_logo_and_hosted_lists`) and together they
# were the last thing stopping a FIRST DEPLOY. Editing a committed migration is
# blocked by `.github/workflows/migration-guard.yml` as append-only; this change
# carries a recorded exception, pinned there by CONTENT HASH.
#
# It used to clear the GUC to the EMPTY STRING, and the comment beside it was
# right about runtime and wrong about migrate: at runtime `''` makes the
# `::uuid` cast fail and that IS deny-by-default, which is why `core/tenancy.py`
# still clears a request's context to `''` on purpose. But `set_config(..., false)`
# is SESSION level, so during `migrate` the empty string OUTLIVES this migration
# and every later one inherits it — and PostgreSQL validates a newly-created
# FOREIGN KEY with an ordinary scan that the B2 §3 policy is evaluated against.
# This migration poisons ITSELF: its order is CreateModel (Django DEFERS the FK
# constraints) → RunSQL (ENABLE + FORCE RLS) → RunPython (this) → exit, where the
# deferred FKs are created AND VALIDATED against `''`.
#
# Result, on a genuinely empty database:
#   DataError: invalid input syntax for type uuid: ""
#   CONTEXT: SELECT fk."account_id" FROM ONLY "meter_reads_2024_08" fk
#            LEFT OUTER JOIN ONLY "accounts" pk …
#
# THE NIL SENTINEL IS SAFE UNDER BOTH POLICY FORMS, which is the whole reason it
# is the answer rather than a workaround. Under the ORIGINAL policy
# (`current_setting('app.tenant_id')::uuid`) it CASTS, where `''` raises — and it
# matches no row, so deny-by-default is unchanged. Under DEF-639's repaired
# policy (`NULLIF(current_setting('app.tenant_id', true), '')::uuid`) it is
# likewise a real uuid matching nothing. The empty string only ever worked under
# the second, and historical policies are live at this point in a fresh run.
#
# It is also already the database- and role-level default that
# `06-backend/db/001_tenant_context_default.sql` installs, so this restores the
# "no tenant" default rather than inventing a value.
#
# Nothing changes on a host that has already migrated: `RunPython` never runs
# again there. (Hard-won law 4 — such a host needs the two
# `ALTER … SET app.tenant_id` statements by hand, once.)
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    # The nil sentinel, NOT '' — see the note above. Castable, matches nothing.
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def seed_catalogs_and_link_read_methods(apps, schema_editor):
    """Seed both catalogs for every existing tenant and repoint each asset's
    read_method text at its catalog row."""
    MeterType = apps.get_model("assets", "MeterType")
    ReadMethod = apps.get_model("assets", "ReadMethod")
    Asset = apps.get_model("assets", "Asset")
    connection = schema_editor.connection
    unmatched: dict[str, int] = {}

    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        for code, name in SEED_METER_TYPES:
            MeterType.objects.get_or_create(
                tenant_id=tenant_id,
                code=code,
                defaults={"name": name, "is_system": True, "active": True},
            )
        methods = {}
        for code, name in SEED_READ_METHODS:
            row, _created = ReadMethod.objects.get_or_create(
                tenant_id=tenant_id,
                code=code,
                defaults={"name": name, "is_system": True, "active": True},
            )
            methods[code] = row
        for legacy_value, target_code in LEGACY_READ_METHOD_MAP.items():
            Asset.objects.filter(
                tenant_id=tenant_id, read_method_legacy__iexact=legacy_value
            ).update(read_method=methods[target_code])
        leftovers = (
            Asset.objects.filter(tenant_id=tenant_id, read_method__isnull=True)
            .exclude(read_method_legacy__isnull=True)
            .exclude(read_method_legacy="")
            .values_list("read_method_legacy", flat=True)
        )
        for value in leftovers:
            unmatched[str(value)] = unmatched.get(str(value), 0) + 1
    _leave_tenant(connection)

    if unmatched:
        # Loud, not silent: these assets now carry NO read method. BR-AST-043 names
        # exactly five; assigning one of them here would be inventing a mapping.
        logger.warning(
            "assets 0003: %s asset row(s) carried a read_method with no BR-AST-043 "
            "counterpart and were left NULL — %s (report to the PO; do not guess)",
            sum(unmatched.values()),
            ", ".join(f"{value!r}×{count}" for value, count in sorted(unmatched.items())),
        )


def unlink_read_methods(apps, schema_editor):
    """Reverse: copy the catalog CODE back into the legacy text column, so a
    rollback keeps the values it can. Rows already NULL stay NULL."""
    Asset = apps.get_model("assets", "Asset")
    connection = schema_editor.connection
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        for asset in Asset.objects.filter(
            tenant_id=tenant_id, read_method__isnull=False
        ).select_related("read_method"):
            Asset.objects.filter(pk=asset.pk).update(read_method_legacy=asset.read_method.code)
    _leave_tenant(connection)


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0002_rls_w1_policies"),
        ("tenancy", "0003_rls_w0_policies"),
    ]

    operations = [
        migrations.CreateModel(
            name="MeterType",
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
                "db_table": "meter_types",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_meter_types_tenant_code_ci",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ReadMethod",
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
                "db_table": "read_methods",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_read_methods_tenant_code_ci",
                    )
                ],
            },
        ),
        # ── the read_method rewire, data-preserving (see docstring note 1) ──
        migrations.RenameField(
            model_name="asset", old_name="read_method", new_name="read_method_legacy"
        ),
        migrations.AddField(
            model_name="asset",
            name="read_method",
            field=models.ForeignKey(
                blank=True,
                db_column="read_method_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assets",
                to="assets.readmethod",
            ),
        ),
        PostgresOnlySQL(  # RLS before the first INSERT — the seed runs under policy
            sql=CATALOG_POLICIES,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(seed_catalogs_and_link_read_methods, unlink_read_methods),
        migrations.RemoveField(model_name="asset", name="read_method_legacy"),
    ]
