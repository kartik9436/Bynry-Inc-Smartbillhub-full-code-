# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · AMENDMENT 1, seed task — "we will provide default value to
#           start with on all these rules" (PO 2026-08-26), for tenants that
#           ALREADY EXIST.   Screens: S64
# Rules:    BR-MET-020 (a missing figure fails safe; a SEEDED default is written
#           at row creation and never read from code) · CLAUDE.md hard rule 1
#           (tenant scoping — every write here happens under the row's own
#           tenant context) · hard-won law 3 (defaults fail closed)
# Tests:    06-backend/tests/test_cr038_s64_service_settings.py (the backfill
#           cases call these functions directly, sqlite path; the ratified
#           figure MIRROR is asserted equal to services.RATIFIED_SERVICE_SEED)
# ───────────────────────────────────────────────────────
"""The CR-038 A1 per-service settings backfill, as importable functions.

HUMAN-OWNED (🔒 migration ordering + it writes under per-tenant RLS context).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-26 under the PO ruling of
2026-08-09; the review-ledger row is the orchestrator's to write (this lane
may not edit 12-governance/) and is flagged in the lane report.

WHY THIS IS A MODULE AND NOT A `RunPython` BODY — the `_0018_helpers` reason,
verbatim in spirit: the migration-guard blocks modifying a committed
migration, so logic that can be IMPORTED can be tested before it is committed
and re-run by hand on a host where it half-ran. 0031 is a thin file that calls
these.

WHY THE RATIFIED FIGURES ARE **MIRRORED** HERE AND NOT IMPORTED FROM
`apps.metering.services` — a committed migration must stay runnable against
the code of ANY future day, and a live-code import ties it to names a refactor
may move (the `ALLOCATION_CLASS_SEQUENCE` posture: mirror + an equality test,
so a drift goes RED in `test_cr038_s64_service_settings.py` instead of
breaking a three-month-old migration).

WHAT IT DOES, PER TENANT — exactly what `services.service_seed_figures` does
at provisioning, so the two paths cannot disagree:

  · for each of the tenant's ENABLED services among the RATIFIED set —
    electric/water (OQ-002) plus gas, sewer, solar, thermal_heat and battery
    (BR-MET-120, PO 2026-08-26: "I agree with all your recomendation - please
    mark them as rule"); trash/storm_water are never read and broadband is
    deferred with Open 7, so those three stay absent ON PURPOSE — create the
    per-service row IF MISSING;
  · electric/water figures come from the tenant's OWN legacy
    `read_validation_settings` row
    where one exists — a tuned tenant keeps judging reads by exactly the
    numbers that governed yesterday — else the ratified constants (identical
    values on any tenant the provisioning seed touched);
  · a tenant with NO legacy row is SKIPPED and NAMED on stdout: its
    electric/water reads are skip-and-report today and stay so — creating
    figures for it would silently switch rules ON, and the repair door
    (`seed_demo --tenant <sub>`) is the deliberate act for that.

⚠ TENANT CONTEXT (CLAUDE.md hard rule 1, DEF-639). The new table's policy is
ENABLE+FORCE from metering 0030, so every INSERT must satisfy WITH CHECK under
the row's own `app.tenant_id`. On Postgres this module:

  1. reads the GUC it ARRIVED with (`current_setting('app.tenant_id', true)`);
  2. sets it per tenant with `set_config(..., false)` while working;
  3. restores the ARRIVAL value on the way out — never leaves `''` behind it
     that was not already there (the DEF-639 poison), and never RESETs a value
     someone upstream set on purpose.

On sqlite there is no RLS and no GUC; the ORM writes run bare, which is the
same honesty `PostgresOnlySQL` applies one migration earlier.
"""

from decimal import Decimal
from typing import Any

#: MIRROR of `apps.metering.services.RATIFIED_SERVICE_SEED` — see the module
#: docstring for why it is a copy. A test asserts the two are EQUAL.
RATIFIED_SERVICE_SEED: dict[str, dict[str, Any]] = {
    "electric": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("50"),
        "high_abs_unit": "kWh",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "water": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("1"),
        "high_abs_unit": "kgal",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "gas": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("20"),
        "high_abs_unit": "ccf",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "sewer": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("1"),
        "high_abs_unit": "kgal",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "solar": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("50"),
        "high_abs_unit": "kWh",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "thermal_heat": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("10"),
        "high_abs_unit": "therm",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "battery": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("50"),
        "high_abs_unit": "kWh",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
}

#: The legacy row's floor column per service — the same mapping
#: `services.service_seed_figures` and `validation._FLOOR_COLUMN_BY_UNIT` use.
_FLOOR_BY_SERVICE = {"electric": ("high_abs_kwh", "kWh"), "water": ("high_abs_kgal", "kgal")}


def figures_from_legacy(legacy_row: Any, code: str) -> dict[str, Any]:
    """The tenant's own governing figures, restated in the per-service shape."""
    column, unit = _FLOOR_BY_SERVICE[code]
    return {
        "high_pct": legacy_row.high_pct,
        "high_abs_value": getattr(legacy_row, column),
        "high_abs_unit": unit,
        "low_pct": legacy_row.low_pct,
        "zero_scope": legacy_row.zero_scope,
        "days_flag_min": legacy_row.days_flag_min,
        "days_flag_max": legacy_row.days_flag_max,
        "days_hard_min": legacy_row.days_hard_min,
        "days_hard_max": legacy_row.days_hard_max,
        "mismatch_pct": (
            legacy_row.mismatch_default_pct
            if hasattr(legacy_row, "mismatch_default_pct")
            else legacy_row.mismatch_pct
        ),
        "tou_sum_tolerance_pct": legacy_row.tou_sum_tolerance_pct,
    }


def backfill_tenant(apps: Any, tenant_id: Any) -> int:
    """Seed the missing electric/water rows for ONE tenant (context already
    set by the caller on Postgres). Returns rows created. Never overwrites."""
    TenantService = apps.get_model("tenancy", "TenantService")
    Legacy = apps.get_model("metering", "ReadValidationSettings")
    PerService = apps.get_model("metering", "ReadValidationServiceSettings")

    legacy_row = Legacy.objects.filter(tenant_id=tenant_id).first()
    if legacy_row is None:
        return -1  # sentinel: skip-and-name — see the module docstring
    created = 0
    enabled = TenantService.objects.filter(
        tenant_id=tenant_id,
        enabled=True,
        service__active=True,
        service__code__in=sorted(RATIFIED_SERVICE_SEED),
    ).select_related("service")
    for enablement in enabled:
        code = enablement.service.code
        # electric/water carry the tenant's OWN tuned figures forward from the
        # legacy row; the BR-MET-120 services (gas/sewer/solar/thermal_heat/
        # battery) have no legacy columns to inherit, so they take the ratified
        # constants verbatim — the PO's 2026-08-26 table, nothing invented.
        if code in _FLOOR_BY_SERVICE:
            defaults = figures_from_legacy(legacy_row, code)
        else:
            defaults = dict(RATIFIED_SERVICE_SEED[code])
        # Historical models carry no custom manager tricks; get_or_create
        # keeps this idempotent on a half-run host (hard-won law: re-runnable).
        _row, was_created = PerService.objects.get_or_create(
            tenant_id=tenant_id,
            service_id=enablement.service_id,
            defaults=defaults,
        )
        created += 1 if was_created else 0
    return created


def run_backfill(apps: Any, schema_editor: Any) -> None:
    """The RunPython forward: every tenant, each under its own context."""
    Tenant = apps.get_model("tenancy", "Tenant")
    is_postgres = schema_editor.connection.vendor == "postgresql"
    connection = schema_editor.connection

    arrival: str | None = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    skipped: list[str] = []
    total = 0
    try:
        # `tenants` is RLS-exempt by signed law (db/rls_tenancy_w0.sql header),
        # so the registry scan itself needs no context.
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            outcome = backfill_tenant(apps, tenant_id)
            if outcome == -1:
                skipped.append(str(tenant_id))
            else:
                total += outcome
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                # Restore EXACTLY the arrival state: a value goes back verbatim;
                # a never-set GUC is RESET (its post-RESET reading may be ''
                # rather than NULL on some hosts — both deny under the NULLIF
                # policies, and neither is a value someone upstream chose).
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    print(f"cr038 a1 backfill: {total} per-service row(s) created")
    if skipped:
        print(
            "cr038 a1 backfill: SKIPPED (no read_validation_settings row — "
            "electric/water stay skip-and-report; run `seed_demo --tenant <sub>` "
            "to seed deliberately): " + ", ".join(skipped)
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 Amendment 1 (12-governance/11-change-requests.md, 2026-08-26)
# generated: 2026-08-26 by the CR-038 A1 S64 lane
# checklist: A✔ B=deferred(data-move half) C✔ D=deferred(no-API-half)
#         E=deferred(no-frontend-half) F✔ G✔ H=PENDING(🔒 — ledger row is the
#         orchestrator's; flagged in the lane report)
# gates: exercised by tests/test_cr038_s64_service_settings.py on sqlite; the
#         Postgres GUC path is NOT provable in this container (no Postgres) and
#         is stated rather than implied (hard-won law 1)
# exceptions: RATIFIED_SERVICE_SEED mirrored from services.py, equality-tested,
#         for the migration-longevity reason the docstring states
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
