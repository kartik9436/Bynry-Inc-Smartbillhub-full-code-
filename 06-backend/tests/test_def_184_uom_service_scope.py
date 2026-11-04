# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-184 — the Units-of-measure picker is not scoped to the service,
#           so a WATER service can be assigned `therm` or `kWh` on SET-03 and
#           nothing refuses it.   Screens: S8 / r10 SET-03 · SET-04
# Change:   CR-004 task A3 — the optional Utility-service column: a NULLABLE
#           service reference on a lookup entry, `null` = "All services",
#           PER-LIST and OPT-IN (units of measure is the ONLY list switched on).
# Ruling:   PO 2026-08-16, verbatim: *"it's a real field - every entry can be
#           scoped to one service or all - I added it in Unit of measure since
#           unit of measure is for speific service; so when we select service we
#           have specific unit of measure available; currently it is not as per
#           utility service"*
# Rules:    BR-TEN-036 (seeded defaults, tenant may extend) · BR-TEN-029
#           (deactivated entries leave the picker) · BR-TEN-026 (a service must
#           be ENABLED for this tenant) · CLAUDE.md rule 1 (tenant scoping)
# Note:     Written BEFORE the fix and shown RED on the shipped build — hard-won
#           law 7. The RED output of each case is quoted in the lane report.
# ───────────────────────────────────────────────────────
"""DEF-184 — units of measure are scoped to a utility service (or to all)."""

import pytest

from apps.tenancy import models, selectors, services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _codes(rows):
    return {row["code"] for row in rows}


# ── (a) the defect itself: today nothing refuses `therm` on WATER ────────────
def test_def_184_a__water_service_refuses_a_gas_only_unit(growth_plan, identity_seam):
    """THE RED CASE. On the shipped build `uoms` carries no service column and
    `_apply_service_uom` resolves a code by `active` alone, so this assignment
    SUCCEEDS and the tenant's water service is measured in therms."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_tenant_service(admin_actor(), "water", {"primary_uom": "therm"})
    assert excinfo.value.code == errors.VAL_UNKNOWN_LOOKUP
    assert {fe["field"] for fe in excinfo.value.field_errors} == {"primary_uom"}
    # and nothing was written
    stored = models.TenantService.objects.get(tenant=tenant, service__code="water")
    assert stored.primary_uom is None or stored.primary_uom.code != "therm"


def test_def_184_a2__water_service_refuses_an_electric_only_alt_unit(growth_plan, identity_seam):
    """⚠ **THE UNIT MOVED FROM `kW` TO `kWh` ON 2026-09-07 AND THE CLAIM DID
    NOT (`DEF-RAT-4516`).** This case needs an alt unit that is ELECTRIC-ONLY.
    `kW` stopped being one on 2026-09-02: `BR-TEN-1180`/`DEF-3230` seeded solar
    and battery, both priced per `kW`, so THREE services now name it and
    `_derive_uom_service_scope` correctly widens it to NULL — *All services* —
    which means water may lawfully pick it and this case failed with
    `DID NOT RAISE`. `kWh` is still named by electric alone, so substituting it
    keeps the assertion testing exactly what it was written to test. The
    widening is the SAFE direction the derivation's own docstring describes (a
    picker offering too much, never too little); nothing about `DEF-184`'s law
    changed."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_tenant_service(
                admin_actor(), "water", {"primary_uom": "kgal", "alt_uom": "kWh"}
            )
    assert {fe["field"] for fe in excinfo.value.field_errors} == {"alt_uom"}


# ── (b) the picker offers only what is valid for the service ────────────────
def test_def_184_b__water_is_offered_kgal_and_ccf_but_never_therm(growth_plan, identity_seam):
    """⚠ **`kW` LEFT THIS ASSERTION ON 2026-09-07 (`DEF-RAT-4516`) BECAUSE IT IS
    NO LONGER ELECTRIC-ONLY.** Solar and battery are both priced per `kW` since
    `BR-TEN-1180`/`DEF-3230` (2026-09-02), so three services name it and the
    derivation scopes it NULL — *All services* — and every service is offered
    it by design. `kWh` is still electric's alone and is what this line now
    checks. `therm` is still gas's alone: the 2026-09-02 swap moved it from
    gas's PRIMARY to gas's ALTERNATE and `_derive_uom_service_scope` does not
    care which slot a claim comes from, so its scope did not move at all."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        offered = _codes(selectors.uoms_for_service("water"))
    assert {"kgal", "ccf"} <= offered
    assert "therm" not in offered  # gas-only, primary or alt alike (DEF-184)
    assert "kWh" not in offered  # electric-only
    # `kW` IS offered: electric's alt, solar's primary AND battery's primary.
    assert "kW" in offered


def test_def_184_b2__gas_is_offered_therm_electric_is_offered_kwh(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        gas = _codes(selectors.uoms_for_service("gas"))
        electric = _codes(selectors.uoms_for_service("electric"))
    assert "therm" in gas and "kWh" not in gas
    assert {"kWh", "kW"} <= electric and "therm" not in electric


def test_def_184_b3__deactivated_units_leave_the_picker(growth_plan, identity_seam):
    """BR-TEN-029 still holds on the scoped picker — scoping narrows, it does
    not replace the active filter."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        kgal = models.Uom.objects.get(tenant=tenant, code="kgal")
        services.set_lookup_entry_active(admin_actor(), "uoms", kgal.pk, False)
        assert "kgal" not in _codes(selectors.uoms_for_service("water"))


# ── (c) NULL service = "All services" ───────────────────────────────────────
def test_def_184_c__unscoped_units_are_offered_for_every_service(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        entry = services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "GJ", "name": "Gigajoule"}
        )
        assert entry["service"] is None  # opt-in: omitted ⇒ All services
        for code in ("electric", "water", "gas", "sewer", "trash", "battery"):
            assert "GJ" in _codes(selectors.uoms_for_service(code))
    # `month` is named by BOTH trash and broadband, so the seed cannot scope it
    # to one service — it stays NULL and is therefore offered everywhere.
    with tenant_ctx(tenant):
        assert models.Uom.objects.get(tenant=tenant, code="month").service_id is None
        assert "month" in _codes(selectors.uoms_for_service("water"))


def test_def_184_c2__an_entry_can_be_scoped_and_unscoped_again(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        entry = services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "MWh", "name": "Megawatt-hour", "service": "electric"}
        )
        assert entry["service"] == {
            "id": str(models.Service.objects.get(code="electric").pk),
            "code": "electric",
        }
        assert "MWh" not in _codes(selectors.uoms_for_service("water"))
        services.update_lookup_entry(admin_actor(), "uoms", entry["id"], {"service": None})
        assert "MWh" in _codes(selectors.uoms_for_service("water"))


# ── (d) a service this tenant does not sell is refused ──────────────────────
def test_def_184_d__a_service_of_another_tenant_is_refused(growth_plan, identity_seam):
    """`services` is a PLATFORM catalog, so "another tenant's service" is a
    service THIS tenant has not enabled: Lone Star Ridge sells water only, so it
    may not scope a unit to Brazos Bend's electric service (BR-TEN-026)."""
    provisioned_tenant()  # brazosbend: electric + water
    lonestar, _ = provisioned_tenant(lonestarridge_payload())  # water only
    with tenant_ctx(lonestar):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_lookup_entry(
                admin_actor(),
                "uoms",
                {"code": "MWh", "name": "Megawatt-hour", "service": "electric"},
            )
    assert {fe["field"] for fe in excinfo.value.field_errors} == {"service"}
    assert excinfo.value.field_errors[0]["message_key"] == "settings.lookups.service_unknown"
    assert not models.Uom.objects.filter(tenant=lonestar, code="MWh").exists()


def test_def_184_d2__an_unknown_service_code_is_refused(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_lookup_entry(
                admin_actor(), "uoms", {"code": "XX", "name": "Nonsense", "service": "unicorn"}
            )
    assert {fe["field"] for fe in excinfo.value.field_errors} == {"service"}


# ── the seed states the scope; only single-service units may be scoped ──────
def test_def_184_seed__scopes_only_units_named_by_exactly_one_service(growth_plan, identity_seam):
    """AMENDED for CR-010 10.2 (PO 2026-08-17: 26 UoMs, all ten services).

    The six W0 units keep their DERIVED scopes exactly as DEF-184 ruled; the
    twenty CR-010 units carry a STATED scope from the fixture (stated wins —
    the charge_type precedent), except the three deliberately left All-services
    because two services name each. This file was the one place the 26-UoM
    slice missed (found by the CR-008 lane and reported rather than fixed
    across a lane boundary — correctly).
    """
    tenant, _ = provisioned_tenant()
    scope = {
        row.code: (row.service.code if row.service else None)
        for row in models.Uom.objects.filter(tenant=tenant).select_related("service")
    }
    assert scope == {
        # ── the six W0 units: DERIVED scope, DEF-184's own law, unchanged ──
        "kWh": "electric",  # named by electric alone
        # ⚠ **`kW` WIDENED TO ALL SERVICES AND `kgal` NARROWED TO WATER on
        # 2026-09-02 (`BR-TEN-1180` / the PO-filed `DEF-3230`); this map was
        # brought into line 2026-09-07 as `DEF-RAT-4516`.** Both moves are
        # spelled out in `_derive_uom_service_scope`'s own docstring, which is
        # the ratified statement this map is asserting against.
        "kW": None,  # electric's alt AND solar AND battery ⇒ All services
        "therm": "gas",  # named by gas alone — its ALT since 2026-09-02, and
        # the derivation does not care which slot a claim comes from
        # ⚠ **`kgal` WIDENED BACK TO ALL SERVICES on 2026-09-08 (`CR-081`).**
        # Sewer now bills 90% of the water VOLUME at its own rate, so it needs a
        # unit, and the ruled unit is the BASIS SERVICE'S — `kgal` and `ccf`,
        # water's own pair. Two services name `kgal` again, and the derivation's
        # law NULLs any unit two services claim. This is the SAFE direction the
        # derivation's docstring names (a picker offering more, never less) and
        # it is what lets a fresh tenant's sewer schedule state `kgal` at all.
        # It read `"water"` from 2026-09-02 until then.
        "kgal": None,  # water AND sewer ⇒ All services
        "ccf": None,  # water's alt AND gas's primary ⇒ All services
        # `month` is named by NO service now: trash moved to `cart` and
        # broadband to `Mbps`, because a capacity service is priced by a COUNT
        # and a month is a period with nothing to multiply.
        "month": None,
        # ── the twenty CR-010 10.2 units: STATED scope from the fixture ──
        "kVA": "electric",
        "kVArh": "electric",
        "gal": "water",
        "cf": "water",
        "m3": "water",
        "Mcf": "gas",
        "Dth": "gas",
        "MMBtu": None,  # gas AND thermal_heat ⇒ All services, stated by omission
        "EDU": "sewer",
        "cart": "trash",
        "pickup": "trash",
        "yd3": "trash",
        "ERU": "storm_water",
        "ksf": "storm_water",
        "kW-DC": None,  # solar AND battery ⇒ All services, stated by omission
        "Mbps": "broadband",
        "GB": "broadband",
        "ton-hr": "thermal_heat",
        # ⚠ `ton-hr` KEEPS ITS SCOPE THOUGH `SERVICE_DEFAULT_UOMS` NO LONGER
        # CLAIMS IT (`CR-080`, 2026-09-07). Thermal declares `ton` now, so the
        # DERIVATION makes no claim on `ton-hr` at all — and the row is scoped
        # anyway, because the FIXTURE states `"service": "thermal_heat"` on it
        # and `_seed_uoms` resolves `stated or SEEDED_UOM_SERVICE_SCOPE.get
        # (code)`. **Recorded rather than left to be rediscovered: dropping a
        # unit from the map cannot silently re-scope a unit the fixture speaks
        # for.** BR-TEN-071 deletes it from nobody either, so a utility that
        # meters chilled-water energy still has the unit to pick.
        "klb": "thermal_heat",
        # CR-080 — thermal/heat's connected tonnage. The REFRIGERATION ton
        # (12,000 BTU/hr), stated in the fixture and derived here identically.
        "ton": "thermal_heat",
        "day": None,  # every service's prorated flat ⇒ All services
        # ── the CR-063 unit: the ELEVENTH service's own tick ──────────────
        # ⚠ **ADDED 2026-09-07 (`DEF-RAT-4516`) — IT HAS BEEN SEEDED SINCE
        # 2026-09-02 AND THIS MAP NEVER LEARNED IT.** `fire` was appended at
        # position 11 (`CR-063`, PO: *"We will need Fire as utility Service -
        # Capacity based - this will behave exactly like trash"*) and
        # `lookup_defaults.json` V2.48.0.6 grew `uoms` from 26 to 27 with
        # `connection`, SCOPED TO FIRE. The fixture STATES the scope and
        # `_derive_uom_service_scope` independently DERIVES it, because fire is
        # the only service that claims it — the two agree, which is the property
        # this map is here to pin.
        "connection": "fire",
    }


def test_def_184_serialize__the_list_view_renders_the_utility_service_column(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = {row["code"]: row for row in selectors.lookup_page("uoms", None)}
    assert rows["therm"]["service"] == {
        "id": str(models.Service.objects.get(code="gas").pk),
        "code": "gas",
    }
    assert rows["ccf"]["service"] is None  # the screen renders "All services"
