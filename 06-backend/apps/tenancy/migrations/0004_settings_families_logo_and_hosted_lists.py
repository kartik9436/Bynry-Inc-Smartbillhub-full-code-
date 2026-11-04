"""tenancy 0004 — the storage half of three ratified-but-unbuilt Settings surfaces:
the five S63–S71 rule-page documents, the BR-TEN-019 logo bytes, and the two
Reference-data tables tenancy HOSTS (`reason_codes`, `payment_methods`) plus their
RLS ENABLE+FORCE. HUMAN-OWNED (migration ordering AND RLS policies are CLAUDE.md
rule-1 🔒 paths).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing SIGNED rules only
(BR-MET-020/025/026/027/052 · BR-BIL-001/002/008/013/014/017/018/021/029 ·
BR-PAY-010/013/016/017/018/019 · BR-REP-022 · BR-CUS-050 · BR-TEN-019/031/036) and
applying the SIGNED B2 §3 policy template verbatim for the two new tables. Row per
file in 12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

WHY IT EXISTS: 11b §2.3 ratified `GET|PUT /settings/{read-validation,billing-defaults,
budget-billing,collections,finance-controls}` and `POST /settings/company/logo`, and
the S8 card grid has declared `reason_codes` and `payment_methods` since W0 — none of
them had anywhere to store a byte. The W0 fixture even seeds twelve rows for those two
lists, which were being SKIPPED at every provisioning because their owning modules
(billing, payments per BR-TEN-031) have no tables and no seeder.

⚠ FOR THE REVIEWER — five things worth your eyes:
1. STORAGE CHOICE. The five rule pages are five jsonb columns on `tenant_settings`,
   the row that already holds this tenant's grouped config, NOT five new tables.
   Consequence worth knowing: B2 r16 #6 PM-proposes `read_validation_settings` as a
   METERING-owned table. Creating a table inside another module's app is a
   cross-module write this lane may not make, and 11b §2.3 puts the endpoint on the
   tenancy Settings surface — so the S64 document lives here, with B2 r5 #15's own
   field names inside it. Re-homing later is one migration.
2. THREE S66 PARAMETERS ARE NOT IN THE DOCUMENT. `late_grace_mode`, `late_grace_days`
   (B2 header late-fee settings) and `deposit_interest_rate_annual` (r9 #5, tagged
   "(S66)" in the schema itself) already existed as typed columns and stay the source
   of truth; the endpoint surfaces them alongside the document. Duplicating them into
   jsonb would have created two homes for one rule.
3. DATA STEPS, AND WHY EACH IS SAFE.
   (a) Django's AddField writes each jsonb column's default into existing rows, so
       every tenant_settings row is born holding the ratified seeded defaults — that
       is deliberate, because BR-MET-020/US-MET-011 TC-9 require engines to read
       CONFIG, never built-in numbers, and a NULL document would push them back onto
       constants.
   (b) `backfill_grace_defaults` fills NULL late_grace_days/late_grace_mode with
       BR-BIL-008's ratified 5 / calendar for the same reason. No consumer reads those
       columns today, so nothing changes behavior; it makes the DB the source.
   (c) `seed_hosted_reference_lists` seeds the twelve fixture rows for EXISTING
       tenants — but ONLY for a tenant that already has a `reference_seed_runs` row,
       i.e. one that provisioned with "Load standard reference data" ON (BR-TEN-012:
       seeding only when the toggle is on). A tenant that opted out stays empty, which
       is what US-TEN-009 TC-6 asserts. Each seeded list also gets its own seed-run
       row at the tenant's own fixture version, so a later provisioning replay is
       still idempotent (US-TEN-002 TC-3).
   The seed values are duplicated here rather than imported from the fixture file on
   purpose — a migration must keep working when that file's next version lands. Both
   copies carry the same W0 fixture values; if they ever diverge, the fixture is the
   tiebreaker for NEW tenants and this file is history for old ones.
4. THE DATA STEP RUNS UNDER RLS. It enumerates tenants from the RLS-exempt platform
   table and sets `app.tenant_id` before touching any tenant table (CLAUDE.md rule 1).
   On sqlite there is no RLS and no set_config — skipped honestly, same ORM path.
5. THE POLICY SQL IS INLINE HERE, not in 06-backend/db/rls_tenancy_w0.sql, because
   db/ is outside this lane's territory. It is the B2 §3 template VERBATIM for the two
   new tables. FLAGGED FOR RELOCATION at human review — the identity lane's
   0004_rls_security_policies.py made the same call for the same reason, and the two
   should be moved together so one file per module holds all policy text.

Postgres-only for the policy half — live isolation proofs run in the G5 suite
(NFR-10, zero tolerance, release blocker).
"""

import apps.tenancy.settings_families
import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

# B2 §3 template, VERBATIM, for the two tables this migration creates. Deny by
# default: with app.tenant_id unset or empty the predicate is NULL, which is not
# TRUE, so no row is visible.
#
# ⚠ THIS MIGRATION WAS EDITED AFTER IT WAS COMMITTED — the ONLY one in this repo,
# under a ONE-TIME exception the Product Owner granted on 2026-08-24 in exactly
# those words. It is recorded in `12-governance/02-decision-log.md` and pinned by
# content hash in `.github/workflows/migration-guard.yml`, so this file cannot be
# edited again without the guard failing.
#
# WHY IT COULD NOT BE FIXED FROM OUTSIDE (DEF-639). These four predicates used to
# read the bare `current_setting('app.tenant_id')::uuid`, which RAISES when the
# marker is empty rather than simply not matching. This migration creates the two
# tables, enables FORCE RLS on them, runs a seed that ends by clearing
# `app.tenant_id`, and then exits — at which point Django creates and VALIDATES
# the foreign keys it deferred. That validation scan is subject to these very
# policies, so it died on `invalid input syntax for type uuid: ""` and a fresh
# database could not be built past this step.
#
# `audit.0005_rls_deny_on_unset_tenant` normalises every policy that already
# EXISTS, which fixes the whole class — but it cannot reach a policy that this
# file creates and then poisons within a single migration. No external runner can
# get between the parts. Hence the exception, and hence its narrowness: four
# literals, one substitution, nothing else in the file touched.
HOSTED_LIST_POLICIES = """
ALTER TABLE reason_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE reason_codes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reason_codes_tenant_isolation ON reason_codes;
CREATE POLICY reason_codes_tenant_isolation ON reason_codes
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE payment_methods ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_methods FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_methods_tenant_isolation ON payment_methods;
CREATE POLICY payment_methods_tenant_isolation ON payment_methods
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""

# W0 fixture (apps/tenancy/fixtures/lookup_defaults.json, version 2026.08) —
# duplicated per reviewer note 3. reason codes: US-TEN-010 §4 signed test data;
# payment methods: the prototype S8 card's six + `wire` (BR-PAY-026) and
# `money_order` (BR-TEN-041 settings-audit upgrade).
SEED_REASON_CODES = (
    ("BILLERR", "Billing error correction"),
    ("METERR", "Meter error"),
    ("LEAK", "Leak credit"),
    ("GOODWILL", "Goodwill credit"),
    ("DISPUTE", "Dispute resolution"),
)
SEED_PAYMENT_METHODS = (
    ("ach", "ACH"),
    ("card", "Card"),
    ("check", "Check"),
    ("cash", "Cash"),
    ("lockbox", "Lockbox"),
    ("wire", "Wire"),
    ("money_order", "Money order"),
)
HOSTED_SEEDS = (
    ("reason_codes", "ReasonCode", SEED_REASON_CODES),
    ("payment_methods", "PaymentMethod", SEED_PAYMENT_METHODS),
)

# BR-BIL-008 / BR-BIL-002 ratified defaults for the two pre-existing S66 columns.
GRACE_DAYS_DEFAULT = 5
GRACE_MODE_DEFAULT = "calendar"


def _enter_tenant(connection, tenant_id):
    """CLAUDE.md rule 1: never touch a tenant table without app.tenant_id set."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


# ⚠ AMENDED 2026-08-24 — OQ-354, RULED BY THE PO, OPTION (A). Third of three
# identical call sites; the full reasoning is in
# `apps/assets/migrations/0003_meter_types_and_read_methods.py`.
#
# ⚠ THIS FILE IS ALSO THE ONE COMMITTED MIGRATION THAT DEF-639 EDITED EARLIER
# TODAY, under the same append-only exception mechanism. So it now carries TWO
# recorded exceptions, and the hash pinned in
# `.github/workflows/migration-guard.yml` moves with this commit — a hash pinned
# to the DEF-639 content would reject this change, which is the mechanism
# working rather than a problem to route around.
#
# In short: `set_config(..., false)` is SESSION level, so clearing to the EMPTY
# STRING here outlived this migration and every later one inherited it, and a
# deferred FOREIGN KEY validation scan is evaluated against the B2 §3 policy —
# where `''::uuid` raises and blocks a first deploy outright. The nil sentinel
# casts under both the original and DEF-639's repaired policy and matches no row
# under either.
#
# Runtime is untouched: `core/tenancy.py` still clears a REQUEST's context to
# `''` deliberately, because there a failed cast is the desired denial.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    # The nil sentinel, NOT '' — see the note above. Castable, matches nothing.
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def backfill_grace_defaults(apps, schema_editor):
    """Reviewer note 3(b): NULL → BR-BIL-008's ratified 5 calendar days."""
    TenantSettings = apps.get_model("tenancy", "TenantSettings")
    Tenant = apps.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _enter_tenant(connection, tenant_id)
        TenantSettings.objects.filter(tenant_id=tenant_id, late_grace_days__isnull=True).update(
            late_grace_days=GRACE_DAYS_DEFAULT
        )
        TenantSettings.objects.filter(tenant_id=tenant_id, late_grace_mode__isnull=True).update(
            late_grace_mode=GRACE_MODE_DEFAULT
        )
    _leave_tenant(connection)


def seed_hosted_reference_lists(apps, schema_editor):
    """Reviewer note 3(c): the W0 fixture rows for tenants that opted in."""
    Tenant = apps.get_model("tenancy", "Tenant")
    ReferenceSeedRun = apps.get_model("tenancy", "ReferenceSeedRun")
    connection = schema_editor.connection

    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _enter_tenant(connection, tenant_id)
        existing_run = ReferenceSeedRun.objects.filter(tenant_id=tenant_id).order_by("seeded_at")
        first_run = existing_run.first()
        if first_run is None:
            continue  # provisioned with the toggle OFF (BR-TEN-012) — leave it empty
        version = first_run.fixture_version
        for list_code, model_name, entries in HOSTED_SEEDS:
            if ReferenceSeedRun.objects.filter(
                tenant_id=tenant_id, list_code=list_code, fixture_version=version
            ).exists():
                continue
            model = apps.get_model("tenancy", model_name)
            created = 0
            for code, name in entries:
                if not model.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
                    model.objects.create(
                        tenant_id=tenant_id, code=code, name=name, is_system=True, active=True
                    )
                    created += 1
            ReferenceSeedRun.objects.create(
                tenant_id=tenant_id,
                list_code=list_code,
                fixture_version=version,
                seeded_count=created,
            )
    _leave_tenant(connection)


def unseed_hosted_reference_lists(apps, schema_editor):
    """Reverse: drop only the seed-run RECORDS this migration minted — the rows
    themselves go with the tables Django drops when reversing CreateModel."""
    Tenant = apps.get_model("tenancy", "Tenant")
    ReferenceSeedRun = apps.get_model("tenancy", "ReferenceSeedRun")
    connection = schema_editor.connection
    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _enter_tenant(connection, tenant_id)
        ReferenceSeedRun.objects.filter(
            tenant_id=tenant_id, list_code__in=[code for code, _model, _rows in HOSTED_SEEDS]
        ).delete()
    _leave_tenant(connection)


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0003_rls_w0_policies"),
    ]

    operations = [
        # ── BR-TEN-019 logo storage (no object store exists — see the model) ──
        migrations.AddField(
            model_name="tenant",
            name="logo_bytes",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="logo_content_type",
            field=models.TextField(blank=True, null=True),
        ),
        # ── the five S63–S71 rule-page documents, born holding their defaults ──
        migrations.AddField(
            model_name="tenantsettings",
            name="billing_defaults",
            field=models.JSONField(
                blank=True, default=apps.tenancy.settings_families.default_billing_defaults
            ),
        ),
        migrations.AddField(
            model_name="tenantsettings",
            name="budget_billing",
            field=models.JSONField(
                blank=True, default=apps.tenancy.settings_families.default_budget_billing
            ),
        ),
        migrations.AddField(
            model_name="tenantsettings",
            name="collections",
            field=models.JSONField(
                blank=True, default=apps.tenancy.settings_families.default_collections
            ),
        ),
        migrations.AddField(
            model_name="tenantsettings",
            name="finance_controls",
            field=models.JSONField(
                blank=True, default=apps.tenancy.settings_families.default_finance_controls
            ),
        ),
        migrations.AddField(
            model_name="tenantsettings",
            name="read_validation",
            field=models.JSONField(
                blank=True, default=apps.tenancy.settings_families.default_read_validation
            ),
        ),
        # ── the two Reference-data tables tenancy HOSTS (BR-TEN-031/036) ──────
        migrations.CreateModel(
            name="PaymentMethod",
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
                "db_table": "payment_methods",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_payment_methods_tenant_code_ci",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ReasonCode",
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
                "db_table": "reason_codes",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_reason_codes_tenant_code_ci",
                    )
                ],
            },
        ),
        # ── RLS for the two new tenant tables (reviewer note 5) ───────────────
        PostgresOnlySQL(
            sql=HOSTED_LIST_POLICIES,
            reverse_sql=migrations.RunSQL.noop,  # policies are never rolled back silently
        ),
        # ── data (reviewer notes 3 + 4) ───────────────────────────────────────
        migrations.RunPython(backfill_grace_defaults, migrations.RunPython.noop),
        migrations.RunPython(seed_hosted_reference_lists, unseed_hosted_reference_lists),
    ]
