# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · AMENDMENT 1, schema task — the VEE rules become a Settings
#           surface, per utility service.   Screens: S64
# Rules:    BR-MET-020 (thresholds are tenant CONFIG; a missing figure fails
#           SAFE — skipped and reported, never defaulted) · CR-038 A1 ruling
#           (PO 2026-08-26, verbatim: "we will ahev to set these rules in
#           settings and take it from there, we will provide default value to
#           start with on all these rules") · CLAUDE.md hard rule 1 (tenant
#           scoping, RLS FORCE) · hard rule 2 (percentages stored 6dp) ·
#           hard rule 3 (a floor is meaningless without its unit)
# Tests:    06-backend/tests/test_cr038_s64_service_settings.py (per-service
#           resolution red-proof + the RLS isolation probe)
# Impacts:  apps/metering/{models,validation,services,selectors,api}.py ·
#           07-frontend features/tenancy/SettingsReadValidation.tsx (S64)
# ───────────────────────────────────────────────────────
"""metering 0030 — `read_validation_service_settings` + RLS ENABLE+FORCE.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — this migration writes an RLS policy and
sits on the migration-ordering sensitive path (CLAUDE.md 🔒 list), AI-authored
2026-08-26 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"), applying the SIGNED B2 §3 policy template in its DEF-639
`NULLIF` form. The review-ledger row in
`12-governance/09-human-review-ledger.md` is the ORCHESTRATOR's to write
(this lane's worktree may not edit 12-governance/); flagged in the lane report.

⚠ THE FILENAME IS LOAD-BEARING: G7 guards sensitive paths by GLOB and
`06-backend/**/migrations/*rls*` matches a NAME (tenancy 0019 records the
escape that taught this). Do not rename this file.

WHAT THE TABLE IS FOR, IN ONE LINE
----------------------------------
One row per (tenant, enabled service) carrying the VEE thresholds S64 edits and
the validation engine resolves FIRST — electric/water fall back to the legacy
tenant-wide `read_validation_settings` row where no per-service row exists, any
other service without a row keeps BR-MET-020's fail-safe skip-and-report.

⚠ NO THRESHOLD COLUMN HAS A DEFAULT, ON PURPOSE. The ratified figures differ
per service (50 kWh electric vs 1 kgal water) and eight services have NO
ratified figure at all (CR-038 A1 Open 5) — a column default would bake one
service's number into every service's row creation. Seeding is explicit:
`services.ensure_read_validation_settings()` writes the PO-ratified
electric/water rows; migration 0031 backfills existing tenants the same way.

⚠ NO DATA IS WRITTEN BY THIS MIGRATION — 0031 is the backfill, separately,
so the schema half stays reversible without touching rows.

The policy (B2 §3 template, DEF-639 cast repair — `NULLIF` makes an unset or
empty `app.tenant_id` yield NULL, a NULL predicate admits NOTHING, and the cast
can no longer poison a deferred FK-validation scan):

    ALTER TABLE read_validation_service_settings ENABLE ROW LEVEL SECURITY;
    ALTER TABLE read_validation_service_settings FORCE ROW LEVEL SECURITY;
    CREATE POLICY read_validation_service_settings_tenant_isolation
      ON read_validation_service_settings
      USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

The policy runs AFTER `CreateModel` in the same migration (tenancy 0019's
pattern): FORCE applies to a table that already exists and is still EMPTY, so
there is never a window in which a row can be written unguarded.

⚠ FOR THE REVIEWER — the same hosting call metering 0004/0015/0025, customers
0002, identity 0004 and tenancy 0004/0019 each flagged: the policy SQL is
INLINE rather than in `06-backend/db/`, because that directory is outside this
lane's territory. Now the SEVENTH file wanting that one relocation.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proof is the G5 isolation suite; the probe
case for THIS table is
`tests/test_cr038_s64_service_settings.py::test_cr038_rls__scopes_service_settings`.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "read_validation_service_settings"

#: B2 §3 template with DEF-639's cast repair — see the docstring.
PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      ({PREDICATE})
  WITH CHECK ({PREDICATE});
"""

REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0029_br_met_113_owner_account"),
        ("tenancy", "0019_cr035_wizard_parks_rls"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReadValidationServiceSettings",
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
                ("high_pct", models.DecimalField(decimal_places=6, max_digits=18)),
                ("high_abs_value", models.DecimalField(decimal_places=6, max_digits=18)),
                ("high_abs_unit", models.TextField()),
                ("low_pct", models.DecimalField(decimal_places=6, max_digits=18)),
                ("zero_scope", models.TextField()),
                ("days_flag_min", models.IntegerField()),
                ("days_flag_max", models.IntegerField()),
                ("days_hard_min", models.IntegerField()),
                ("days_hard_max", models.IntegerField()),
                ("mismatch_pct", models.DecimalField(decimal_places=6, max_digits=18)),
                ("tou_sum_tolerance_pct", models.DecimalField(decimal_places=6, max_digits=18)),
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
            ],
            options={
                "db_table": "read_validation_service_settings",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "service"), name="uq_read_validation_service_settings"
                    )
                ],
            },
        ),
        # FORCE lands while the table is still empty — see the docstring.
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 Amendment 1 (12-governance/11-change-requests.md, PO ruling
#         2026-08-26 quoted verbatim in the Trace above)
# generated: 2026-08-26 by the CR-038 A1 S64 lane
# checklist: A✔ B=deferred(schema half — engine/API/screen are the same lane's
#         separate files) C✔ D=deferred(no-API-half here) E=deferred(no-
#         frontend-half here) F✔ G✔ H=PENDING(🔒 RLS + migration ordering —
#         ledger row is the orchestrator's to write; flagged in the lane report)
# gates: makemigrations --check clean · sqlite migrate applied (PostgresOnlySQL
#         skips honestly) · NO POSTGRES IN THIS WORKTREE CONTAINER, so the
#         policy is NOT proven against a live database here and that is stated
#         rather than implied (hard-won law 1); the isolation tier
#         (@pytest.mark.isolation + requires_postgres probe) is what proves it.
# exceptions: policy SQL inline rather than 06-backend/db/ (seventh file to
#         flag the same relocation — REPORTED, not resolved here)
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
