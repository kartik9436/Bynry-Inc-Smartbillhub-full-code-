# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-007 (enable/disable services per tenant, S8) ·
#           US-TEN-008 (edit UoM per service, S8)
# Rules:    BR-TEN-016 · BR-TEN-024 · BR-TEN-025 (closed catalog) · BR-TEN-026
#           (guarded soft disable) · BR-TEN-027 (UoM forward-only) · BR-TEN-029
# Note:     rate-schedule / account counts come from DOCUMENTED seams
#           (rating/customers — unwired lanes → stubs here; guard TCs against
#           the real counts are skip-until-wired by construction).
# ───────────────────────────────────────────────────────
"""US-TEN-007 / US-TEN-008 — Services & UoM tab services."""

import pytest

import apps.customers.services as customers_services
import apps.rating.services as rating_services
from apps.tenancy import api, models, selectors, services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    audit_actions,
    clerk_actor,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── US-TEN-007 — enable / disable ───────────────────────────────────────────
def test_us_ten_007_tc1__enable_gas_defaults_ccf_therm_from_seed(
    growth_plan, identity_seam, audit_rows
):
    """US-TEN-007 TC-1 — enabling Gas takes BOTH units from the seed.

    ⚠ **THE PAIR IS `ccf` PRIMARY / `therm` ALTERNATE, AND IT WAS `therm` /
    `ccf` UNTIL 2026-09-02 (`BR-TEN-1180`, closing `DEF-2409` and the PO-filed
    `DEF-3230`; the assertion moved 2026-09-07 as `DEF-TEN-4505`).** The PO
    filed the seed itself as a defect — *"this is problem with every Utility
    services - why dont you se the correct data in Seed data and fix it"* —
    because the seeded gas register read `therm` while the only signed gas
    price in the repo is the billing workbook `[W] §1`'s *"Gas flat
    $1.15/ccf"*. `therm` is declared ENERGY and `ccf` VOLUME
    (`metering.register_units.DIMENSION_OF`), so no conversion factor can ever
    reconcile them and the signed price was unusable against the seeded
    register. Swapping the two makes the seed agree with the signed figure.

    ⚠ **THE TC's OWN WORDS SURVIVE THE SWAP AND ONLY THIS CONCRETE CHOICE
    MOVED.** `EP-TEN-06` TC-1 reads *"row turns On (ccf / therm defaults from
    seed)"* — it names the PAIR, and the pair is unchanged; both units have
    been ratified for gas and offered on S8 since the map was written.

    ⚠ **THIS ASSERTION WAS RED FOR FIVE DAYS AND COST A FALSE ACCUSATION.** It
    went red the moment the seed moved and hid among other reds, and a lane
    reading it as current concluded the LIVE SEED was wrong and filed
    `DEF-TEN-4504` against the ruling — which is marked INVALID. A test
    asserting a superseded value is worse than no test, because it manufactures
    false alarms in the direction of accusing whoever made the ruled change.
    """
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    with tenant_ctx(tenant):
        row = services.update_tenant_service(admin_actor(), "gas", {"enabled": True})
    assert row["enabled"] is True
    # US-TEN-007 TC-1: defaults from seed — SERVICE_DEFAULT_UOMS["gas"], swapped
    # to ("ccf", "therm") by BR-TEN-1180 / DEF-3230 on 2026-09-02.
    assert row["primary_uom"] == "ccf"
    assert row["alt_uom"] == "therm"
    assert "settings.service.enabled" in audit_actions(audit_rows)


def test_us_ten_007_tc2__disable_unused_service_is_soft(growth_plan, identity_seam, audit_rows):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.update_tenant_service(admin_actor(), "gas", {"enabled": True})
        audit_rows.clear()
        row = services.update_tenant_service(admin_actor(), "gas", {"enabled": False})
    assert row["enabled"] is False
    stored = models.TenantService.objects.get(tenant=tenant, service__code="gas")
    assert stored.enabled is False and stored.disabled_at is not None  # history kept
    assert "settings.service.disabled" in audit_actions(audit_rows)


def test_us_ten_007_tc3__disable_blocked_while_referenced_counts_named(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    tenant, _ = provisioned_tenant()
    monkeypatch.setattr(
        rating_services,
        "rate_schedule_count",
        lambda **kw: 3 if kw.get("service_code") == "electric" else 0,
        raising=False,
    )
    monkeypatch.setattr(
        customers_services,
        "active_account_count",
        lambda code: 612 if code == "electric" else 0,
        raising=False,
    )
    audit_rows.clear()
    with tenant_ctx(tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.update_tenant_service(admin_actor(), "electric", {"enabled": False})
    assert excinfo.value.code == errors.BIZ_STATE
    assert excinfo.value.br_ref == "BR-TEN-026"
    assert excinfo.value.params == {
        "service": "electric",
        "rate_schedules": 3,
        "active_accounts": 612,
    }
    stored = models.TenantService.objects.get(tenant=tenant, service__code="electric")
    assert stored.enabled is True  # no state change
    assert "settings.service.disabled" not in audit_actions(audit_rows)  # no audit row


def test_us_ten_007_tc4__clerk_rejected_server_side_reads_allowed(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.AuthError):
            services.update_tenant_service(clerk_actor(), "gas", {"enabled": True})
    # API: the tab is readable by any tenant role (read-only render, IS-6)…
    view = api_call(
        api.services_settings, "get", user=FakeUser(), role="billing_clerk", tenant=tenant
    )
    assert view.status_code == 200
    assert {r["service"] for r in view.data} >= {"electric", "water", "gas"}
    # …the write endpoint denies the clerk
    denied = api_call(
        api.service_update,
        "put",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        data={"enabled": True},
        service="gas",
    )
    assert denied.status_code == 403


def test_us_ten_007_tc5__service_toggle_is_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(brazos):
        services.update_tenant_service(admin_actor(), "water", {"enabled": False})
    with tenant_ctx(lonestar):
        assert selectors.service_row("water")["enabled"] is True  # unaffected
    with tenant_ctx(brazos):
        assert selectors.service_row("water")["enabled"] is False


def test_us_ten_007_tc1b__unknown_service_type_is_404_closed_catalog(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.NotFoundError):  # BR-TEN-025: no tenant-added types
            services.update_tenant_service(admin_actor(), "cable_tv", {"enabled": True})


# ── US-TEN-008 — edit UoM per service ───────────────────────────────────────
def test_us_ten_008_tc1__primary_change_warns_with_affected_schedules(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    tenant, _ = provisioned_tenant()
    monkeypatch.setattr(
        rating_services,
        "rate_schedule_count",
        lambda **kw: 2 if kw.get("uom_code") == "kgal" else 0,
        raising=False,
    )
    audit_rows.clear()
    with tenant_ctx(tenant):
        row = services.update_tenant_service(
            admin_actor(), "water", {"primary_uom": "ccf", "alt_uom": "kgal"}
        )
    assert row["primary_uom"] == "ccf"
    assert row["warnings"] == {"rate_schedules_in_old_unit": 2}  # named, not converted
    saves = [r for r in audit_rows if r["action"] == "settings.service_uom.updated"]
    assert len(saves) == 1
    assert saves[0]["before"]["primary_uom"] == "kgal"
    assert saves[0]["after"]["primary_uom"] == "ccf"


def test_us_ten_008_tc2__uom_change_touches_only_tenant_services_row(growth_plan, identity_seam):
    """BR-TEN-027 tenancy half: historical reads/lines keep their stored unit —
    those tables belong to metering/billing (unwired); what this lane proves is
    the change writes NOTHING beyond the tenant_services columns."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        uoms_before = list(models.Uom.objects.filter(tenant=tenant).values())
        services.update_tenant_service(
            admin_actor(), "water", {"primary_uom": "ccf", "alt_uom": "kgal"}
        )
        assert list(models.Uom.objects.filter(tenant=tenant).values()) == uoms_before


def test_us_ten_008_tc3__electric_alt_uom_kw_demand(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = services.update_tenant_service(
            admin_actor(), "electric", {"primary_uom": "kWh", "alt_uom": "kW"}
        )
    assert row["alt_uom"] == "kW"


def test_us_ten_008_tc4__deactivated_uom_excluded_from_new_picks(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        therm = models.Uom.objects.get(tenant=tenant, code="therm")
        services.set_lookup_entry_active(admin_actor(), "uoms", therm.pk, False)
        services.update_tenant_service(admin_actor(), "gas", {"enabled": True})
        with pytest.raises(errors.ValidationError) as excinfo:
            # ⚠ **`alt_uom` IS SENT EXPLICITLY, AND WITHOUT IT THIS CASE STOPPED
            # TESTING WHAT IT IS NAMED FOR (`DEF-RAT-4516`, 2026-09-07).** The
            # seed is `primary=ccf, alt=therm` since `BR-TEN-1180` (2026-09-02),
            # and an OMITTED key means *keep what is on file* — so picking
            # `therm` as the PRIMARY collided with the `therm` already sitting
            # in the alternate slot and `BR-TEN-027`'s `alt_equals_primary`
            # (`VAL-002`) refused FIRST. The refusal this case exists to prove —
            # `VAL_UNKNOWN_LOOKUP` on a DEACTIVATED entry — was never reached,
            # so the assertion below failed with `VAL-002 == VAL-005` and the
            # deactivation guard was untested for five days.
            services.update_tenant_service(
                admin_actor(), "gas", {"primary_uom": "therm", "alt_uom": "ccf"}
            )
    assert excinfo.value.code == errors.VAL_UNKNOWN_LOOKUP
    # ⚠ AMENDED 2026-08-18 (New mandate 4, PO 2026-08-17): the gas row now
    # exists FROM PROVISIONING with its default UoM assigned — the seeded pair
    # was ACTIVE at that moment, so the stored assignment lawfully remains after
    # the deactivation (US-TEN-008's standing rule: deactivation excludes an
    # entry from NEW picks and never touches existing assignments). What this
    # test guards is unchanged and still asserted above: a NEW pick of the
    # deactivated unit is refused by name.
    # ⚠ AMENDED 2026-09-07 (DEF-TEN-4505): the seeded PRIMARY is `ccf` since
    # BR-TEN-1180 swapped the pair; `therm` is the ALTERNATE and is the unit
    # this case deactivates, which is what makes the refusal above meaningful.
    stored = models.TenantService.objects.get(tenant=tenant, service__code="gas")
    assert stored.primary_uom is not None and stored.primary_uom.code == "ccf"
    assert stored.alt_uom is not None and stored.alt_uom.code == "therm"


def test_us_ten_008_tc5__primary_required_and_alt_must_differ(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as required:
            services.update_tenant_service(admin_actor(), "water", {"primary_uom": None})
        with pytest.raises(errors.ValidationError) as same:
            services.update_tenant_service(
                admin_actor(), "water", {"primary_uom": "kgal", "alt_uom": "kgal"}
            )
    assert required.value.code == errors.VAL_REQUIRED
    assert {fe["field"] for fe in same.value.field_errors} == {"alt_uom"}


def test_us_ten_008_tc6__uom_defaults_are_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(brazos):
        services.update_tenant_service(
            admin_actor(), "water", {"primary_uom": "ccf", "alt_uom": "kgal"}
        )
    with tenant_ctx(lonestar):
        assert selectors.service_row("water")["primary_uom"] == "kgal"  # own default
    with tenant_ctx(brazos):
        assert selectors.service_row("water")["primary_uom"] == "ccf"
