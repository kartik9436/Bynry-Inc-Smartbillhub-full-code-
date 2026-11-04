# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-9222 — a thermal tonnage or storm-water class picked on
#           New Connection step 3 was dropped at Create, so the unit carried no
#           `connected_capacity` / `assessment` and both services billed $0.00.
# Found:    the New Connection end-to-end web walk, 2026-10-02 / 03.
# Rules:    CR-062 D6 (storm water's size is a UNIT fact, PO 2026-09-02) ·
#           CR-080 (thermal tonnage is capacity, PO 2026-09-07) · BR-MET-108
#           (a characteristic carries its unit of measure)
# Front:    07-frontend/src/features/customers/newConnectUnitCapacity9222.test.ts
# ───────────────────────────────────────────────────────
"""What Create records for a unit whose size no device carries.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): asserting that a
characteristic ROW exists would pass over a value recorded in the wrong unit
(`2450 sqft` read as `2450 ERU`). So each case reads the value back through
`characteristic_for_pricing` — the call the bill makes — and asserts the NUMBER
and the UNIT OF MEASURE the ratified ladder gives the picked class.
"""

from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.tenancy import services as tenancy_services
from core import errors
from tests.test_def_met_5441_the_commit_door import _wizard_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _sells(actor, *codes):
    for code in codes:
        tenancy_services.update_tenant_service(actor, code, {"enabled": True})


def _unit(connection_id, label):
    connection = work_tables.Connection.objects.get(pk=connection_id)
    return metering_models.Unit.objects.get(premises_id=connection.premises_id, label=label)


def test_thermal_tonnage_and_storm_class_are_recorded_on_the_unit(dana, brazos):
    """S2 / S7 in miniature: Apt 1 takes 10 tons of thermal and is an
    *Apartment building* for storm water (6 ERU); Apt 2 takes 25 tons and is a
    *Single-family home* (1 ERU).

    RED PROVED: on the tip before this fix both readings came back `absent`,
    `priced_at_zero` — the `$0.00` the walk found.
    """
    with tenant_ctx(brazos):
        _sells(dana, "thermal_heat", "storm_water")
        plan = _wizard_plan(
            premises={
                **_wizard_plan()["premises"],
                "services_available": ["thermal_heat", "storm_water"],
            },
            units=[{"label": "Apt 1"}, {"label": "Apt 2"}],
            unit_services=[
                {"unit_label": "Apt 1", "service": "thermal_heat", "equipment": [], "size_class": "TH-T10"},
                {"unit_label": "Apt 2", "service": "thermal_heat", "equipment": [], "size_class": "TH-T25"},
                {"unit_label": "Apt 1", "service": "storm_water", "equipment": [], "size_class": "SW-APT"},
                {"unit_label": "Apt 2", "service": "storm_water", "equipment": [], "size_class": "SW-SF"},
            ],
        )
        built = w6.commit_new_connect(dana, plan)
        apt1, apt2 = _unit(built["id"], "Apt 1"), _unit(built["id"], "Apt 2")
        read = {
            (label, service): w6.characteristic_for_pricing(unit.id, service, key)
            for label, unit in (("Apt 1", apt1), ("Apt 2", apt2))
            for service, key in (("thermal_heat", "connected_capacity"), ("storm_water", "assessment"))
        }

    assert {k: (r.value, r.unit_of_measure, r.absent) for k, r in read.items()} == {
        ("Apt 1", "thermal_heat"): (Decimal("10"), "ton", False),
        ("Apt 2", "thermal_heat"): (Decimal("25"), "ton", False),
        ("Apt 1", "storm_water"): (Decimal("6"), "ERU", False),
        ("Apt 2", "storm_water"): (Decimal("1"), "ERU", False),
    }


def test_a_class_the_service_does_not_have_is_refused_by_name(dana, brazos):
    """A storm-water row sent a THERMAL code is refused, never recorded as a
    plausible number — and the whole build goes with it (`BR-MET-112`)."""
    with tenant_ctx(brazos):
        _sells(dana, "storm_water")
        plan = _wizard_plan(
            premises={**_wizard_plan()["premises"], "services_available": ["storm_water"]},
            unit_services=[
                {"unit_label": "Apt 1", "service": "storm_water", "equipment": [], "size_class": "TH-T10"}
            ],
        )
        with pytest.raises(errors.ApiError) as refused:
            w6.commit_new_connect(dana, plan)
    assert refused.value.message_key == "metering.connection_unit_size_unknown"


def test_a_row_with_no_size_records_nothing(dana, brazos):
    """No size sent is BR-MET-108's absence — the ruled `$0.00`, stamped —
    never a size nobody chose."""
    with tenant_ctx(brazos):
        _sells(dana, "thermal_heat")
        plan = _wizard_plan(
            premises={**_wizard_plan()["premises"], "services_available": ["thermal_heat"]},
            unit_services=[{"unit_label": "Apt 1", "service": "thermal_heat", "equipment": []}],
        )
        built = w6.commit_new_connect(dana, plan)
        reading = w6.characteristic_for_pricing(
            _unit(built["id"], "Apt 1").id, "thermal_heat", "connected_capacity"
        )
    assert reading.absent is True
