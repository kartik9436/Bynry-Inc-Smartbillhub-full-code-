# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-9015 — a time-of-use or demand schedule was accepted for a
#          service the tenant does not read from a meter, and billing then
#          refused every bill on it.
# Rules:   BR-TEN-1180 (billing_basis: metered · share · capacity, the
#          tenant's own declaration) · BR-RAT-021 (TOU reads arrive split per
#          window) · BR-RAT-031 (one service, one model)
# ───────────────────────────────────────────────────────
"""The save refuses time of use and demand where the service reads no meter.

The SAME service is used on both sides — electric, declared `capacity` and then
`metered` — so the tenant's declaration is the only thing that changes and the
test cannot pass on some other refusal.
"""

from __future__ import annotations

import pytest

from apps.rating import services
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — env
from tests.test_us_rat_helpers import SUMMER, WINTER, tenant_ctx

pytestmark = pytest.mark.django_db

KEY = "rating.schedules.model_needs_meter"


def _declare(env, basis):
    tenancy_models.TenantService.objects.filter(
        tenant=env.tenant, service__code="electric"
    ).update(billing_basis=basis)


def _tou():
    window = {"day_type": "weekday", "season": "Summer", "unit_price": "0.2100"}
    return {
        "name": "Electric TOU · DEF-RAT-9015",
        "service": "electric",
        "model": "time_of_use",
        "uom": "kWh",
        "structure": {
            "seasons": [dict(SUMMER), dict(WINTER)],
            "windows": [
                {**window, "label": "On-peak", "start_time": "14:00", "end_time": "19:00"},
                {**window, "label": "Off-peak", "start_time": "19:00", "end_time": "14:00",
                 "unit_price": "0.0900"},
                {"label": "Off-peak", "season": "Winter", "day_type": "weekday",
                 "start_time": "00:00", "end_time": "00:00", "unit_price": "0.0900"},
            ],
        },
    }


def _demand():
    return {
        "name": "Electric demand · DEF-RAT-9015",
        "service": "electric",
        "model": "demand",
        "uom": "kWh",
        "structure": {"energy_rate_per_kwh": "0.1100", "demand_rate_per_kw": "11.00"},
    }


def _keys(exc):
    return [row["message_key"] for row in exc.field_errors]


@pytest.mark.parametrize("payload", [_tou, _demand], ids=["time_of_use", "demand"])
@pytest.mark.parametrize("basis", ["capacity", "share"])
def test_def_rat_9004__no_meter_refuses_tou_and_demand_on_structure(env, payload, basis):
    _declare(env, basis)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_rate_schedule(env.admin, payload())
    assert KEY in _keys(caught.value)
    assert any(row["field"] == "model" and row["message_key"] == KEY for row in caught.value.field_errors)


@pytest.mark.parametrize("payload", [_tou, _demand], ids=["time_of_use", "demand"])
def test_def_rat_9004__a_metered_service_keeps_both(env, payload):
    _declare(env, "metered")
    with tenant_ctx(env.tenant):
        try:
            services.create_rate_schedule(env.admin, payload())
        except errors.ValidationError as exc:  # another refusal is not this one
            assert KEY not in _keys(exc)


def test_def_rat_9004__flat_is_unaffected_on_a_counted_service(env):
    _declare(env, "capacity")
    with tenant_ctx(env.tenant):
        try:
            services.create_rate_schedule(
                env.admin,
                {"name": "Electric flat · DEF-RAT-9015", "service": "electric", "model": "flat",
                 "uom": "kWh", "structure": {"unit_price": "0.1100"}},
            )
        except errors.ValidationError as exc:
            assert KEY not in _keys(exc)
