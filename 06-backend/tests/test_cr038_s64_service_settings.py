# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · AMENDMENT 1 — the VEE rules become a Settings surface, per
#           utility service (PO 2026-08-26, verbatim: "we will ahev to set
#           these rules in settings and take it from there, we will provide
#           default value to start with on all these rules").  Screens: S64
# Rules:    BR-MET-020 (config or nothing; missing figure = skip-and-report) ·
#           BR-MET-022/056 (outcomes are self-describing and stored — history
#           keeps the threshold it was judged by) · BR-MET-025 · BR-MET-052 ·
#           BR-TEN-024-shaped save (atomic, ONE audit row) · BR-SHL-025 (the
#           service refuses the wrong role no matter the caller) · CLAUDE.md
#           hard rule 1 (tenant scoping/RLS FORCE) · rule 2 (percent 6dp,
#           decimals never floats) · rule 3 (a floor is unit-aware) · rule 7
#           (every settings write audits field/old/new/actor)
# Supersedes: the S64 halves of tests/test_us_ten_settings_rule_pages.py
#           (US-MET-011 TC-7/TC-8/TC-10 + the S64 defaults block) — moved here
#           WITH the surface when CR-038 A1 re-homed it to metering.
# ───────────────────────────────────────────────────────
"""CR-038 A1 — per-(tenant, service) VEE settings: engine resolution
(red-proofed), seeding, the S64 endpoints, history immutability, RLS probe."""

from decimal import Decimal

import pytest
from django.apps import apps as django_apps

from apps.metering import models, selectors, services, validation
from apps.metering import api as metering_api
from apps.metering.migrations import _0031_helpers
from apps.tenancy import models as tenancy_models
from core import errors

from tests.isolation_helpers import (
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    clear_live_guc,
    current_guc,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — reads fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    at,
    brazos,
    commit_read,
    csv_body,
    lonestar,
    marcus,
    seed_config,
    seed_service_config,
    stage,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import FakeUser, api_call, audit_rows  # noqa: F401

pytestmark = pytest.mark.django_db


# ── engine fixtures (pure — no ORM, the validation.py testing style) ────────
def ctx(**kwargs) -> validation.ReadContext:
    return validation.ReadContext(**kwargs)


class LegacyConfig:
    """The tenant-wide row shape, as test_us_met_011_validation.Config does."""

    high_pct = Decimal("200")
    high_abs_kwh = Decimal("50")
    high_abs_kgal = Decimal("1")
    low_pct = Decimal("25")
    zero_scope = "active_non_vacant"
    days_flag_min = 25
    days_flag_max = 35
    days_hard_min = 20
    days_hard_max = 45
    mismatch_default_pct = Decimal("3")
    tou_sum_tolerance_pct = Decimal("1")

    def __init__(self, **overrides):
        for name, value in overrides.items():
            setattr(self, name, value)


class GasServiceConfig:
    """A per-service row shape: ONE unit-aware floor in the service's OWN unit."""

    high_pct = Decimal("200")
    high_abs_value = Decimal("5")
    high_abs_unit = "ccf"
    low_pct = Decimal("25")
    zero_scope = "active_non_vacant"
    days_flag_min = 25
    days_flag_max = 35
    days_hard_min = 20
    days_hard_max = 45
    mismatch_default_pct = Decimal("3")  # the model property's alias shape
    tou_sum_tolerance_pct = Decimal("1")

    def __init__(self, **overrides):
        for name, value in overrides.items():
            setattr(self, name, value)


def _gas_high_ctx() -> validation.ReadContext:
    """A gas read 3× its trailing average: 30 ccf against avg 10 ccf."""
    return ctx(
        value=Decimal("1040"),
        read_at=at("2026-08-01"),
        unit="ccf",
        multiplier=Decimal("1"),
        prior_value=Decimal("1010"),
        prior_read_at=at("2026-07-01"),
        trailing_actuals=[(Decimal("10"), 30), (Decimal("10"), 30)],
        unit_occupied=True,
        service_code="gas",
    )


def _outcome(outcomes, rule):
    return next(o for o in outcomes if o.rule == rule)


# ══════════════════════════════════════════════════════════════════════════
# THE RED-PROOF (task 7): a gas row with a per-service gas floor is judged
# by IT — never by electric's kWh floor, and never skipped.
# ══════════════════════════════════════════════════════════════════════════
def test_cr038_red_proof__a_gas_read_is_judged_by_the_gas_floor():
    """WRITTEN TO FAIL FIRST, and it did. Run against the pre-CR-038 engine
    (`git show a9cc41d:06-backend/apps/metering/validation.py`, which has no
    `ConfigSet`, no `resolve_config` and no `service_code` on ReadContext),
    the assertion below fails as:

        TypeError: ReadContext.__init__() got an unexpected keyword argument
        'service_code'

    and with `service_code` stripped so the old engine can even build the
    context, the old path's verdict on this exact fixture is:

        rule=high severity=not_evaluated
        detail.reason=absolute_floor_unavailable_for_unit

    — the tenant row knows only kWh/kgal floors, `ccf` maps to neither, so
    BR-MET-020's fail-safe SKIPPED the high rule on every gas read forever
    (measured by tests/scratch — quoted in the lane report). The new
    resolution judges the same read by the GAS row's own 5 ccf floor:
    ratio 300% > 200% AND delta 20 ccf > 5 ccf ⇒ WARNING."""
    config_set = validation.ConfigSet(
        tenant_row=LegacyConfig(), service_rows={"gas": GasServiceConfig()}
    )
    _consumption, outcomes = validation.evaluate_row(_gas_high_ctx(), config_set)
    high = _outcome(outcomes, validation.RULE_HIGH)
    assert high.severity == validation.WARNING
    assert high.detail["absolute_floor"] == "5"
    assert high.detail["absolute_floor_unit"] == "ccf"
    assert high.detail["threshold_pct"] == "200"


def test_cr038_red_proof_control__the_old_call_shape_still_skips_gas():
    """The CONTROL: hand the engine the legacy call shape (a bare tenant row,
    exactly what every caller passed before this change) and the gas read is
    skipped with `absolute_floor_unavailable_for_unit` — the old behavior,
    still reachable, still fail-safe. This is the failure the red-proof above
    documents, pinned so the contrast survives in the suite."""
    _consumption, outcomes = validation.evaluate_row(_gas_high_ctx(), LegacyConfig())
    high = _outcome(outcomes, validation.RULE_HIGH)
    assert high.severity == validation.NOT_EVALUATED
    assert high.detail["reason"] == "absolute_floor_unavailable_for_unit"


# ── resolution law (CR-038 A1) ──────────────────────────────────────────────
def test_cr038__per_service_row_wins_over_the_legacy_row_for_electric():
    electric = GasServiceConfig(
        high_abs_unit="kWh", high_abs_value=Decimal("500"), high_pct=Decimal("400")
    )
    config_set = validation.ConfigSet(
        tenant_row=LegacyConfig(), service_rows={"electric": electric}
    )
    resolved = validation.resolve_config(config_set, "electric")
    assert resolved is electric  # not the tenant row


def test_cr038__electric_and_water_fall_back_to_the_legacy_row_only():
    config_set = validation.ConfigSet(tenant_row=LegacyConfig(), service_rows={})
    assert validation.resolve_config(config_set, "electric") is config_set.tenant_row
    assert validation.resolve_config(config_set, "water") is config_set.tenant_row
    for other in (
        "gas",
        "sewer",
        "trash",
        "storm_water",
        "solar",
        "broadband",
        "thermal_heat",
        "battery",
    ):
        assert validation.resolve_config(config_set, other) is None, other
    # A read whose service is UNKNOWN resolves to None too: no service's
    # thresholds can honestly claim it (narrower than the old behavior, and
    # VISIBLY so — the skip is reported per rule).
    assert validation.resolve_config(config_set, None) is None


def test_cr038__a_bare_config_passes_through_unchanged():
    """Legacy callers (and the 23 standing US-MET-011 tests) hand a bare row —
    resolve_config must be a no-op on anything that is not a ConfigSet."""
    row = LegacyConfig()
    assert validation.resolve_config(row, "gas") is row
    assert validation.resolve_config(None, "electric") is None


def test_cr038__skip_and_report_unchanged_for_a_service_with_no_figures():
    """BR-MET-020 / US-MET-011 TC-9, per service: gas with NO gas row and no
    lawful fallback reports `validation_config_missing` — never electric's
    numbers, never a silent green."""
    config_set = validation.ConfigSet(tenant_row=LegacyConfig(), service_rows={})
    _c, outcomes = validation.evaluate_row(_gas_high_ctx(), config_set)
    for rule in (validation.RULE_HIGH, validation.RULE_LOW, validation.RULE_DAYS_THRESHOLD):
        outcome = _outcome(outcomes, rule)
        assert outcome.severity == validation.NOT_EVALUATED
        assert outcome.detail["reason"] == "validation_config_missing"


def test_cr038__tou_sum_sanity_resolves_per_service_too():
    gas = GasServiceConfig(tou_sum_tolerance_pct=Decimal("10"))
    config_set = validation.ConfigSet(tenant_row=LegacyConfig(), service_rows={"gas": gas})
    windows = {"tou_on": Decimal("50"), "tou_mid": Decimal("30"), "tou_off": Decimal("15")}
    # 5% deviation: breaches the tenant row's 1%, sits inside the gas row's 10%.
    by_gas = validation.tou_sum_sanity(windows, Decimal("100"), config_set, service_code="gas")
    by_tenant = validation.tou_sum_sanity(
        windows, Decimal("100"), config_set, service_code="electric"
    )
    assert by_gas.severity == validation.OK
    assert by_gas.detail["tolerance_pct"] == "10"
    assert by_tenant.severity == validation.WARNING
    assert by_tenant.detail["tolerance_pct"] == "1"


# ══════════════════════════════════════════════════════════════════════════
# SEEDING (task 2): ratified figures for electric/water, NOTHING else.
# ══════════════════════════════════════════════════════════════════════════
def test_cr038__provisioning_seeds_electric_and_water_rows_with_the_ratified_figures(brazos):
    """ "we will provide default value to start with" — and the figures are
    EXACTLY the PO-ratified set: 200% / 50 kWh (electric), 200% / 1 kgal
    (water), low 25%, days 25–35 flag / 20–45 hard, mismatch 3%, TOU ±1%."""
    with tenant_ctx(brazos):
        rows = {
            row.service.code: row
            for row in models.ReadValidationServiceSettings.objects.filter(
                tenant_id=brazos.id
            ).select_related("service")
        }
    assert set(rows) == {"electric", "water"}, (
        "electric+water only — the other eight services have NO ratified figure "
        "(CR-038 A1 Open 5) and seeding one would be the guess BR-MET-020 forbids"
    )
    electric, water = rows["electric"], rows["water"]
    assert (electric.high_pct, electric.high_abs_value) == (Decimal("200"), Decimal("50"))
    assert (electric.high_abs_unit, water.high_abs_unit) == ("kWh", "kgal")
    assert water.high_abs_value == Decimal("1")
    for row in (electric, water):
        assert row.low_pct == Decimal("25")
        assert (row.days_flag_min, row.days_flag_max) == (25, 35)
        assert (row.days_hard_min, row.days_hard_max) == (20, 45)
        assert row.mismatch_pct == Decimal("3")
        assert row.tou_sum_tolerance_pct == Decimal("1")
        assert row.zero_scope == "active_non_vacant"


def test_cr038__a_water_only_tenant_gets_a_water_row_only(lonestar):
    with tenant_ctx(lonestar):
        codes = set(
            models.ReadValidationServiceSettings.objects.filter(tenant_id=lonestar.id).values_list(
                "service__code", flat=True
            )
        )
    assert codes == {"water"}


def test_cr038__the_seed_is_idempotent_and_never_overwrites_a_tuned_row(brazos):
    with tenant_ctx(brazos):
        seed_service_config("electric", high_pct=Decimal("321"))
        assert services.ensure_read_validation_service_rows() == 0  # nothing new
        row = models.ReadValidationServiceSettings.objects.get(
            tenant_id=brazos.id, service__code="electric"
        )
        assert row.high_pct == Decimal("321")  # the tuned figure stands


def test_cr038__seeding_copies_a_tuned_legacy_row_so_behavior_is_preserved(brazos):
    """A tenant whose legacy tenant-wide figures were ever tuned keeps judging
    reads by exactly those numbers when the per-service rows materialise —
    the seed copies the tenant's OWN governing row, not the constants."""
    with tenant_ctx(brazos):
        # Tune the legacy row DIRECTLY (seed_config would re-seed the service
        # rows before the override lands — its own docstring's trap), then
        # drop the service rows and let the seed rebuild them from the tune.
        legacy = models.ReadValidationSettings.objects.get(tenant_id=brazos.id)
        legacy.high_pct = Decimal("250")
        legacy.high_abs_kwh = Decimal("75")
        legacy.save()
        models.ReadValidationServiceSettings.objects.filter(tenant_id=brazos.id).delete()
        created = services.ensure_read_validation_service_rows()
        assert created == 2
        electric = models.ReadValidationServiceSettings.objects.get(
            tenant_id=brazos.id, service__code="electric"
        )
        assert electric.high_pct == Decimal("250")
        assert electric.high_abs_value == Decimal("75")
        assert electric.high_abs_unit == "kWh"


# ── the backfill migration's helpers (0031) ─────────────────────────────────
def test_cr038__the_migration_mirror_equals_the_live_seed_constants():
    """`_0031_helpers.RATIFIED_SERVICE_SEED` is a MIRROR (a committed migration
    must not import live names a refactor may move) — this equality is what
    turns a drift between the two copies RED."""
    assert _0031_helpers.RATIFIED_SERVICE_SEED == services.RATIFIED_SERVICE_SEED


def test_cr038__backfill_creates_missing_rows_and_skips_a_tenant_with_no_legacy_row(brazos):
    with tenant_ctx(brazos):
        models.ReadValidationServiceSettings.objects.filter(tenant_id=brazos.id).delete()
    assert _0031_helpers.backfill_tenant(django_apps, brazos.id) == 2
    assert _0031_helpers.backfill_tenant(django_apps, brazos.id) == 0  # idempotent
    with tenant_ctx(brazos):
        models.ReadValidationServiceSettings.objects.filter(tenant_id=brazos.id).delete()
        models.ReadValidationSettings.objects.filter(tenant_id=brazos.id).delete()
    # No legacy row: the tenant is SKIPPED (sentinel -1) — its electric/water
    # reads are skip-and-report today and silently switching rules on is not
    # the backfill's call; the repair door is.
    assert _0031_helpers.backfill_tenant(django_apps, brazos.id) == -1
    assert not models.ReadValidationServiceSettings.objects.filter(tenant_id=brazos.id).exists()


# ══════════════════════════════════════════════════════════════════════════
# THE ENGINE THROUGH THE SERVICE LAYER: a real gas batch, judged by the
# tenant's own gas row (created through the S64 write door).
# ══════════════════════════════════════════════════════════════════════════
def _enable_gas(tenant):
    tenancy_models.TenantService.objects.filter(tenant_id=tenant.id, service__code="gas").update(
        enabled=True
    )


GAS_FIGURES = {
    "high_pct": "200",
    "high_abs_value": "5",
    "high_abs_unit": "ccf",
    "low_pct": "25",
    "zero_scope": "active_non_vacant",
    "days_flag_min": 25,
    "days_flag_max": 35,
    "days_hard_min": 20,
    "days_hard_max": 45,
    "mismatch_pct": "3",
    "tou_sum_tolerance_pct": "1",
}


def test_cr038__a_gas_batch_is_judged_by_the_tenants_own_gas_row(brazos, marcus):
    """End to end: enable gas, create the gas row through the S64 service,
    stage a 3×-average gas read — the stored outcome carries the GAS floor
    (5 ccf), proving services plumb the service code into the engine."""
    admin = staff_actor(brazos, "system_admin", "dana.s64@brazosbendutilities.test")
    with tenant_ctx(brazos):
        _enable_gas(brazos)
        services.save_read_validation_service(admin, "gas", dict(GAS_FIGURES))
        meter = a_meter(marcus, "M-9001", service="gas", uom="ccf", address="9 Flare Ct")
        commit_read(
            marcus,
            meter["id"],
            day="2026-06-01",
            value=1000,
            unit="ccf",
            consumption="10",
            prior_value="990",
        )
        commit_read(
            marcus,
            meter["id"],
            day="2026-07-01",
            value=1010,
            unit="ccf",
            consumption="10",
            prior_value="1000",
        )
        batch = stage(marcus, csv_body("M-9001,2026-08-01,1040,total,gas"))
        summary = services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(tenant_id=brazos.id, batch_id=batch["id"])
    high = next(o for o in row.rule_outcomes if o["rule"] == "high")
    assert high["severity"] == "warning"
    assert high["detail"]["absolute_floor"] == "5.000000"
    assert high["detail"]["absolute_floor_unit"] == "ccf"
    assert summary["validation_config_present"] is True


# ══════════════════════════════════════════════════════════════════════════
# HISTORY UNTOUCHED (task 6): an edit changes only SUBSEQUENT validation.
# ══════════════════════════════════════════════════════════════════════════
def test_cr038__an_edited_threshold_judges_the_next_batch_and_never_history(brazos, marcus):
    """BR-MET-022/056 — outcomes are stored self-describing, so a committed
    read KEEPS the threshold it was judged by. Asserted, not assumed: the
    committed row's stored `rule_outcomes` still say 200 after the tenant
    moves electric's high threshold to 400, and only a batch validated AFTER
    the edit is judged by 400."""
    admin = staff_actor(brazos, "system_admin", "dana.hist@brazosbendutilities.test")
    with tenant_ctx(brazos):
        meter = a_meter(marcus, "M-9002", service="electric", uom="kWh", address="11 Joule Way")
        commit_read(
            marcus, meter["id"], day="2026-06-01", value=1000, consumption="100", prior_value="900"
        )
        commit_read(
            marcus, meter["id"], day="2026-07-01", value=1100, consumption="100", prior_value="1000"
        )
        # 300 kWh against a 100 kWh average: ratio 300% > 200%, delta 200 > 50.
        batch = stage(marcus, csv_body("M-9002,2026-08-01,1400,total,electric"))
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        committed = models.MeterRead.objects.get(
            tenant_id=brazos.id, asset_id=meter["id"], read_at=at("2026-08-01")
        )
        judged = next(o for o in committed.rule_outcomes if o["rule"] == "high")
        assert judged["severity"] == "warning"
        assert judged["detail"]["threshold_pct"] == "200.000000"

        # The tenant raises the threshold — event-time forward.
        services.save_read_validation_service(admin, "electric", {"high_pct": "400"})

        committed.refresh_from_db()
        after_edit = next(o for o in committed.rule_outcomes if o["rule"] == "high")
        assert after_edit == judged, (
            "the committed read's stored outcome must keep the figure it was "
            "JUDGED by — a settings edit re-writing history would make every "
            "past acceptance unexplainable (BR-MET-056)"
        )

        # …and the SAME reading staged tomorrow is judged by the NEW figure.
        meter2 = a_meter(
            marcus,
            "M-9003",
            service="electric",
            uom="kWh",
            address="12 Joule Way",
            unit_label="Unit B",
        )
        commit_read(
            marcus, meter2["id"], day="2026-06-01", value=1000, consumption="100", prior_value="900"
        )
        commit_read(
            marcus,
            meter2["id"],
            day="2026-07-01",
            value=1100,
            consumption="100",
            prior_value="1000",
        )
        batch2 = stage(marcus, csv_body("M-9003,2026-08-01,1400,total,electric"))
        services.validate_read_batch(marcus, batch2["id"])
        row2 = models.ReadImportRow.objects.get(tenant_id=brazos.id, batch_id=batch2["id"])
        high2 = next(o for o in row2.rule_outcomes if o["rule"] == "high")
        assert high2["severity"] == "ok"  # 300% no longer breaches 400%
        assert high2["detail"]["threshold_pct"] == "400.000000"


# ══════════════════════════════════════════════════════════════════════════
# THE S64 ENDPOINTS (task 3): whole picture out, per-service writes, audit.
# ══════════════════════════════════════════════════════════════════════════
def test_cr038__get_serves_the_whole_picture(brazos):
    read = api_call(
        metering_api.read_validation_settings,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
    )
    assert read.status_code == 200
    payload = read.data
    assert payload["general"]["present"] is True
    assert payload["general"]["est_method"] == "trailing_3_daily_avg"
    assert payload["general"]["est_max_consecutive"] == 2
    assert payload["integrity_rules"] == list(validation.INTEGRITY_RULES)
    by_code = {entry["service"]: entry for entry in payload["services"]}
    assert set(by_code) == {"electric", "water"}  # enabled services only
    assert by_code["electric"]["source"] == "service"
    assert by_code["electric"]["high_abs_value"] == "50.000000"
    assert by_code["electric"]["high_abs_unit"] == "kWh"
    assert by_code["water"]["high_abs_value"] == "1.000000"
    # decimals are canonical STRINGS on the wire (CLAUDE.md rule 2)
    assert isinstance(by_code["electric"]["high_pct"], str)


def test_cr038__get_renders_the_fail_safe_state_honestly(brazos):
    """An enabled service with NO figures anywhere serves source="none" — the
    screen renders "no figure — rule skipped and reported", never a zero."""
    with tenant_ctx(brazos):
        _enable_gas(brazos)
    read = api_call(
        metering_api.read_validation_settings,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
    )
    by_code = {entry["service"]: entry for entry in read.data["services"]}
    assert by_code["gas"]["source"] == "none"
    assert "high_pct" not in by_code["gas"]  # no invented figures ride along


def test_cr038__get_renders_the_legacy_fallback_when_a_service_row_is_absent(brazos):
    """Electric with its per-service row deleted (a tenant that enabled the
    service after provisioning, say) is judged by the legacy tenant-wide
    figures — and the GET says so instead of pretending they are per-service."""
    with tenant_ctx(brazos):
        models.ReadValidationServiceSettings.objects.filter(
            tenant_id=brazos.id, service__code="electric"
        ).delete()
    read = api_call(
        metering_api.read_validation_settings,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
    )
    electric = next(e for e in read.data["services"] if e["service"] == "electric")
    assert electric["source"] == "tenant_fallback"
    assert electric["high_abs_value"] == "50.000000"
    assert electric["high_abs_unit"] == "kWh"


def test_cr038__put_updates_one_service_with_one_audit_row(brazos, audit_rows):
    audit_rows.clear()
    saved = api_call(
        metering_api.read_validation_service_settings,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        data={"high_pct": "250"},
        service="electric",
    )
    assert saved.status_code == 200
    assert saved.data["high_pct"] == "250.000000"
    assert saved.data["low_pct"] == "25.000000"  # a partial PUT is not a truncating PUT
    rows = [r for r in audit_rows if r["action"] == "settings.read_validation.service_updated"]
    assert len(rows) == 1  # atomic save = ONE audit row (rule 7: field/old/new/actor)
    assert rows[0]["before"] == {"service": "electric", "high_pct": "200.000000"}
    assert rows[0]["after"] == {"service": "electric", "high_pct": "250.000000"}
    assert rows[0]["actor_user_id"] is not None


def test_cr038__a_no_op_save_writes_nothing_and_audits_nothing(brazos, audit_rows):
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "noop@brazosbendutilities.test")
        audit_rows.clear()
        services.save_read_validation_service(admin, "electric", {"high_pct": "200"})
    assert [r["action"] for r in audit_rows] == []


def test_cr038__creating_a_service_row_requires_every_field(brazos, audit_rows):
    """Gas has NO ratified figure to merge a partial change over — a create
    must state every figure, or it is refused naming what is missing."""
    with tenant_ctx(brazos):
        _enable_gas(brazos)
        admin = staff_actor(brazos, "system_admin", "creator@brazosbendutilities.test")
        audit_rows.clear()
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_read_validation_service(admin, "gas", {"high_pct": "300"})
        missing = {fe["field"] for fe in excinfo.value.field_errors}
        assert "high_abs_value" in missing and "days_hard_max" in missing
        assert not models.ReadValidationServiceSettings.objects.filter(
            tenant_id=brazos.id, service__code="gas"
        ).exists()
        assert [r["action"] for r in audit_rows] == []
        # …and the complete set creates the row, audited as a create.
        created = services.save_read_validation_service(admin, "gas", dict(GAS_FIGURES))
        assert created["source"] == "service"
        assert created["high_abs_unit"] == "ccf"
    rows = [r for r in audit_rows if r["action"] == "settings.read_validation.service_updated"]
    assert len(rows) == 1
    assert rows[0]["before"] == {"service": "gas", "configured": False}


def test_cr038__a_disabled_service_is_refused(brazos):
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "gasless@brazosbendutilities.test")
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_read_validation_service(admin, "gas", dict(GAS_FIGURES))
    assert excinfo.value.field_errors[0]["message_key"] == "metering.service_not_enabled"


@pytest.mark.parametrize(
    "payload,bad_field",
    [
        ({"high_pct": "-10"}, "high_pct"),  # percentages > 0
        ({"high_pct": "0"}, "high_pct"),
        ({"high_abs_value": "-1"}, "high_abs_value"),  # floors >= 0
        ({"low_pct": "150"}, "low_pct"),  # 0 < x <= 100
        ({"zero_scope": "sometimes"}, "zero_scope"),
        ({"days_flag_min": 0}, "days_flag_min"),  # bounds start at 1
        # hard bounds must CONTAIN flag bounds:
        ({"days_hard_min": 30}, "days_flag_min"),
        ({"days_flag_max": 50}, "days_flag_min"),
        # a window must be a window:
        ({"days_flag_min": 40}, "days_flag_max"),
        ({"high_pct_per_service": {"electric": 1}}, "high_pct_per_service"),  # unknown key
    ],
)
def test_cr038__nonsense_is_refused_and_config_unchanged(brazos, audit_rows, payload, bad_field):
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "bounds@brazosbendutilities.test")
        audit_rows.clear()
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_read_validation_service(admin, "electric", payload)
        unchanged = models.ReadValidationServiceSettings.objects.get(
            tenant_id=brazos.id, service__code="electric"
        )
    assert any(fe["field"] == bad_field for fe in excinfo.value.field_errors)
    assert unchanged.high_pct == Decimal("200")
    assert unchanged.days_flag_min == 25
    assert [r["action"] for r in audit_rows] == []  # a refusal writes nothing


def test_cr038__the_general_panel_saves_estimation_params_with_audit(brazos, audit_rows):
    audit_rows.clear()
    saved = api_call(
        metering_api.read_validation_settings,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        data={"est_max_consecutive": 3},
    )
    assert saved.status_code == 200 and saved.data["est_max_consecutive"] == 3
    rows = [r for r in audit_rows if r["action"] == "settings.read_validation.updated"]
    assert len(rows) == 1
    assert rows[0]["before"] == {"est_max_consecutive": 2}
    assert rows[0]["after"] == {"est_max_consecutive": 3}
    with tenant_ctx(brazos):
        assert services._read_config().est_max_consecutive == 3
        admin = staff_actor(brazos, "system_admin", "est@brazosbendutilities.test")
        with pytest.raises(errors.ValidationError):
            services.save_read_validation_general(admin, {"est_method": "rolling_mean"})
        with pytest.raises(errors.ValidationError):
            services.save_read_validation_general(admin, {"est_max_consecutive": 0})


def test_cr038__executive_reads_admin_writes_clerk_denied(brazos):
    """A4 "Settings & lookup tables: Full / — / View", copied to the metering
    home: view class admits Admin+Executive, the SERVICE guard refuses the
    Executive's write (BR-SHL-025 defense in depth)."""
    clerk_get = api_call(
        metering_api.read_validation_settings,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
    )
    exec_get = api_call(
        metering_api.read_validation_settings,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
    )
    exec_put = api_call(
        metering_api.read_validation_service_settings,
        "put",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        data={"high_pct": "250"},
        service="electric",
    )
    admin_put = api_call(
        metering_api.read_validation_service_settings,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        data={"high_pct": "260"},
        service="electric",
    )
    assert clerk_get.status_code == 403 and clerk_get.data["code"] == "AUTH-002"
    assert exec_get.status_code == 200 and "services" in exec_get.data
    assert exec_put.status_code == 403 and exec_put.data["code"] == "AUTH-002"
    assert admin_put.status_code == 200 and admin_put.data["high_pct"] == "260.000000"


def test_cr038__values_are_per_tenant(brazos, lonestar):
    """US-MET-011 TC-10, per service: Lone Star Ridge tunes water low to 40%,
    Brazos Bend keeps 25% — identical readings can flag differently."""
    with tenant_ctx(lonestar):
        erin = staff_actor(lonestar, "system_admin", "erin.s64@lsrwater.test")
        services.save_read_validation_service(erin, "water", {"low_pct": "40"})
    with tenant_ctx(brazos):
        assert models.ReadValidationServiceSettings.objects.get(
            tenant_id=brazos.id, service__code="water"
        ).low_pct == Decimal("25")
    with tenant_ctx(lonestar):
        assert models.ReadValidationServiceSettings.objects.get(
            tenant_id=lonestar.id, service__code="water"
        ).low_pct == Decimal("40")
    # (RLS FORCE half = the probe below, on live Postgres)


def test_cr038__the_overview_selector_orders_services_by_catalog(brazos):
    with tenant_ctx(brazos):
        _enable_gas(brazos)
        overview = selectors.read_validation_overview()
    codes = [entry["service"] for entry in overview["services"]]
    assert codes == ["electric", "water", "gas"]  # the platform seed order


# ══════════════════════════════════════════════════════════════════════════
# RLS PROBE (task 7 second half) — the house tc9b shape, live Postgres only.
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_cr038_rls__scopes_service_settings(brazos, lonestar, rls):  # noqa: F811
    """The DATABASE half, under `sbh_rls_probe` (NOLOGIN NOSUPERUSER
    NOBYPASSRLS — the app role bypasses RLS in CI and proves nothing).

    ⚠ SKIPPED ON THE DEFAULT sqlite RUN (`requires_postgres`) — no Postgres
    exists in this lane's container, so this case is authored RED-UNPROVEN
    here and the G5 isolation sweep is what runs it; stated, not implied
    (hard-won law 1). Deny-by-default is asserted the NULLIF way (zero rows,
    not an exception) — metering 0025's finding: `assert_denied_without_
    context` expects the old cast to RAISE and does not hold for a NULLIF
    policy."""
    # Provisioning seeded per-service rows for both tenants already.
    assert_rls_scoped(
        rls, "read_validation_service_settings", owner=brazos, intruder=lonestar, min_owner_rows=1
    )
    clear_live_guc()
    assert current_guc() == ""
    assert rls.rows("SELECT count(*) FROM read_validation_service_settings") == [(0,)], (
        "deny-by-default: with app.tenant_id unset the table must expose no row "
        "(a NULL policy predicate admits nothing — DEF-639's repaired form)"
    )
    assert_write_into_other_tenant_refused(
        rls, "read_validation_service_settings", owner=brazos, intruder=lonestar
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 Amendment 1 (12-governance/11-change-requests.md, 2026-08-26)
# generated: 2026-08-26 by the CR-038 A1 S64 lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(frontend half = SettingsReadValidation
#         .test.tsx, same lane) F✔ G✔ H=PENDING(🔒 halves — ledger rows are the
#         orchestrator's; flagged in the lane report)
def test_br_met_120__the_ratified_floor_table_is_law_and_drift_goes_red():
    """BR-MET-120 (PO 2026-08-26, verbatim: "I agree with all your
    recomendation - please mark them as rule") — the per-service high floors,
    asserted figure by figure so any drift in the seed constants goes RED
    (sign-off rule 2026-08-11, part 2). Trash and storm water are never read
    and broadband is deferred with Open 7 — their ABSENCE is part of the law.
    """
    ratified = {
        "electric": (Decimal("200"), Decimal("50"), "kWh"),
        "water": (Decimal("200"), Decimal("1"), "kgal"),
        "gas": (Decimal("200"), Decimal("20"), "ccf"),
        "sewer": (Decimal("200"), Decimal("1"), "kgal"),
        "solar": (Decimal("200"), Decimal("50"), "kWh"),
        "thermal_heat": (Decimal("200"), Decimal("10"), "therm"),
        "battery": (Decimal("200"), Decimal("50"), "kWh"),
    }
    assert set(services.RATIFIED_SERVICE_SEED) == set(ratified)
    for code, (pct, floor, unit) in ratified.items():
        row = services.RATIFIED_SERVICE_SEED[code]
        assert row["high_pct"] == pct, (code, row["high_pct"])
        assert row["high_abs_value"] == floor, (code, row["high_abs_value"])
        assert row["high_abs_unit"] == unit, (code, row["high_abs_unit"])
    for absent in ("trash", "storm_water", "broadband"):
        assert absent not in services.RATIFIED_SERVICE_SEED


# gates: pytest (this file + test_us_met_011_validation.py) — output quoted in
#         the lane report; the RLS case runs only under the G5 sweep (no
#         Postgres in this container, stated above)
# exceptions: the red-proof's old-engine run is reproduced from git history in
#         a scratchpad harness (the suite cannot import two versions of one
#         module) — the failure text is pinned in the docstring and the
#         CONTROL test keeps the old call shape's skip behavior pinned forever
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
