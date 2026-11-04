"""DEF-WRK-9266 — a New Connection proposes only jobs for hardware it fits.

`CR-080` (PO 2026-09-07, *"connected tonnage - it is capacity not metering"*)
took the meter off a THERMAL unit, and `DEF-MET-9037` (PO 2026-10-02, *"we are
not doing net metering right now"*) took the net meter off a SOLAR build. The
seeded work-order starters were never told: step 3 went on proposing a
*Meter set* per thermal unit and a *Net meter swap* per solar unit, and once
`DEF-MET-9223` raised jobs per unit those became real orders for hardware
Create never makes (the re-walk's S2: two of each).

Three things are asserted, each red on the old seed:

1. **The declaration** — no starter of a service that fits no meter names a
   meter, and thermal (which fits no device at all) carries no per-asset job.
2. **Thermal keeps exactly one gate**, and it is *Service connection* — fire's
   own shape for a flat, device-less service (decision log 2026-10-03).
3. **The repair** (`metering/0070`) — a tenant holding the OLD untouched seed
   is corrected, and a tenant that EDITED the same starter is left exactly as
   it was. Never overwrite a tenant's own edits.
"""

from __future__ import annotations

import importlib

import pytest
from django.apps import apps as global_apps

from apps.work import connection_models as work_tables
from apps.metering import sample_data as metering_sample
from apps.tenancy import services as tenancy_services
from apps.work import selectors as work_selectors
from apps.work import templates_svc

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The services Create fits a METER for — `NewConnectShared.METERED_SERVICES`
#: (sewer may carry one by a utility's own choice, never by default).
METERED = {"electric", "water", "gas", "sewer"}

#: The services Create fits NO device for at all: their size sits on the unit
#: (`capacityIsOnTheUnit`) or they derive from another service.
NO_DEVICE = {"thermal_heat", "storm_water"}

def _repair():
    return importlib.import_module("apps.metering.migrations.0070_def_wrk_9266_jobs_match_hardware")


def _declared() -> dict[str, tuple[tuple[str, str, bool], ...]]:
    return dict(metering_sample.W6_TEMPLATE_STARTERS)


def test_no_starter_names_a_meter_on_a_service_that_fits_none():
    offenders = [
        (code, name)
        for code, rows in _declared().items()
        if code not in METERED
        for name, _scope, _gate in rows
        if "meter" in name.lower()
    ]
    assert offenders == [], offenders


def test_a_service_that_fits_no_device_carries_no_per_asset_job():
    offenders = [
        (code, name)
        for code, rows in _declared().items()
        if code in NO_DEVICE
        for name, scope, _gate in rows
        if scope == work_tables.SCOPE_ASSET
    ]
    assert offenders == [], offenders


def test_thermal_keeps_one_gate_and_it_is_the_service_connection():
    gates = [name for name, _scope, is_gate in _declared()["thermal_heat"] if is_gate]
    assert gates == ["Service connection"]


# ══════════════════════════════════════════════════════════════════════════
# THE REPAIR OF A TENANT ALREADY SEEDED
# ══════════════════════════════════════════════════════════════════════════

#: The seed as it stood until 2.467.25, for the two services that change.
OLD_SEED = {
    "thermal_heat": (
        ("Inspection", work_tables.SCOPE_PREMISE, False),
        ("Service connection", work_tables.SCOPE_UNIT, False),
        ("Meter set", work_tables.SCOPE_ASSET, True),
    ),
    "solar": (
        ("Interconnection application", work_tables.SCOPE_PREMISE, False),
        ("Inspection", work_tables.SCOPE_PREMISE, False),
        ("Net meter swap", work_tables.SCOPE_ASSET, False),
        ("Commissioning and witness test", work_tables.SCOPE_ASSET, False),
    ),
}


def _plant_old_seed(actor) -> dict[tuple[str, str], str]:
    """The old starters, written the way the seeder wrote them — draft,
    details row, publish v1, sample tag."""
    ids: dict[tuple[str, str], str] = {}
    for code, rows in OLD_SEED.items():
        tenancy_services.update_tenant_service(actor, code, {"enabled": True})
        for sequence, (name, scope, is_gate) in enumerate(rows, start=1):
            header = templates_svc.create_draft(
                actor,
                {
                    "name": name,
                    "service": code,
                    "scope": scope,
                    "sequence": sequence,
                    "is_gate": is_gate,
                    "no_gate_reason": metering_sample.W6_NO_GATE_REASON.get(code),
                },
            )
            templates_svc.replace_collection(actor, header["id"], "details", {})
            templates_svc.publish(actor, header["id"], change_note="First publish")
            ids[(code, name)] = str(header["id"])
    work_tables.WorkOrderTemplate.objects.filter(pk__in=list(ids.values())).update(is_sample=True)
    return ids


def _row(ids, code, name):
    return work_tables.WorkOrderTemplate.objects.get(pk=ids[(code, name)])


def _proposed_names(codes):
    return {
        (row["service"]["code"] if isinstance(row["service"], dict) else row["service"], row["name"])
        for row in work_selectors.proposed_work_orders(codes)["proposed"]
    }


def test_the_old_untouched_seed_is_corrected(brazos, dana):
    with tenant_ctx(brazos):
        ids = _plant_old_seed(dana)
        before = _proposed_names(["thermal_heat", "solar"])
        assert ("thermal_heat", "Meter set") in before
        assert ("solar", "Net meter swap") in before

        result = _repair().repair_tenant(global_apps, brazos.id)

        assert result == {"retired": 2, "gate_moved": 1, "left_edited": 0}
        after = _proposed_names(["thermal_heat", "solar"])
        assert ("thermal_heat", "Meter set") not in after
        assert ("solar", "Net meter swap") not in after
        assert ("solar", "Commissioning and witness test") in after
        assert _row(ids, "thermal_heat", "Service connection").is_gate is True
        # Deactivated, never deleted: an order already raised from it stays readable.
        assert _row(ids, "thermal_heat", "Meter set").active is False
        assert _row(ids, "solar", "Net meter swap").active is False
        # A replay changes nothing.
        assert _repair().repair_tenant(global_apps, brazos.id) == {
            "retired": 0,
            "gate_moved": 0,
            "left_edited": 0,
        }


def test_a_tenant_that_edited_the_starter_is_left_alone(brazos, dana):
    with tenant_ctx(brazos):
        ids = _plant_old_seed(dana)
        # The utility republished its thermal Meter set as v2 and renamed the
        # solar swap — both are now THEIR templates, not the seed.
        meter_set = ids[("thermal_heat", "Meter set")]
        templates_svc.update_header(dana, meter_set, {"crew_size": 2})
        templates_svc.publish(dana, meter_set, change_note="two-person crew")
        swap = ids[("solar", "Net meter swap")]
        templates_svc.update_header(dana, swap, {"name": "Bi-directional meter swap"})

        result = _repair().repair_tenant(global_apps, brazos.id)

        assert result == {"retired": 0, "gate_moved": 0, "left_edited": 2}
        assert _row(ids, "thermal_heat", "Meter set").active is True
        assert _row(ids, "thermal_heat", "Meter set").is_gate is True
        # The gate does not move while the tenant's own gate still stands.
        assert _row(ids, "thermal_heat", "Service connection").is_gate is False
        assert _row(ids, "solar", "Net meter swap").active is True


@requires_postgres
def test_the_whole_migration_step_runs_under_rls_on_postgres(brazos, dana, capsys):
    """The `RunPython` entry itself — `SET LOCAL app.tenant_id` per tenant
    under `FORCE` RLS — which SQLite cannot exercise (hard-won law 14)."""
    from django.db import connection

    with tenant_ctx(brazos):
        _plant_old_seed(dana)

    class _Editor:
        pass

    editor = _Editor()
    editor.connection = connection
    _repair().repair(global_apps, editor)
    out = capsys.readouterr().out
    assert "2 seeded job(s) for unfitted hardware deactivated" in out, out
    assert "1 thermal gate(s) moved to Service connection" in out, out


def test_a_fresh_seed_proposes_no_hardware_create_does_not_fit(brazos, dana):
    with tenant_ctx(brazos):
        for code in ("thermal_heat", "solar"):
            tenancy_services.update_tenant_service(dana, code, {"enabled": True})
        metering_sample._seed_work_order_template_starters(dana)
        names = _proposed_names(["thermal_heat", "solar"])
    assert ("thermal_heat", "Meter set") not in names
    assert ("solar", "Net meter swap") not in names
    assert ("thermal_heat", "Service connection") in names
