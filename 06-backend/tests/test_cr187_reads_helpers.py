# ── Trace ──────────────────────────────────────────────
# Component: shared fixtures for the CR-187-BRC10 route-reading server tests
#            (`test_cr187_reads_sync.py`, `…_routes.py`, `…_pg.py`). Layers on
#            the Brazos Bend world `tests/test_us_met_reads_helpers.py` builds,
#            through the real services — no second invented universe.
# Note:      the figures are the RW boards' (*1318 Maple*, `MTR-0471`, unit A,
#            Carla Ruiz) used as TEST DATA only (B14 rule 37).
# ───────────────────────────────────────────────────────
"""A route of three stops, four meters on it, one meter off it, a reader."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace

from apps.metering import models as metering_models
from apps.metering import seams as metering_seams
from apps.metering import services as metering_services

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    make_premises,
    make_unit,
    seed_service_config,
    staff_actor,
    tenant_ctx,
)

#: The engine's two thresholds, set explicitly so the expected range is a
#: number this file can state (BR-MET-020 — the engine reads the row, never a
#: constant). 50 % … 150 % of the trailing average.
LOW_PCT = Decimal("50")
HIGH_PCT = Decimal("150")
#: Twelve months of 700 kWh, ending 30 days before today.
MONTHLY = Decimal("700")
LAST_DIAL = Decimal("47700")


def reader_actor(tenant, email="ray.reader@brazosbendutilities.test"):
    """A FIELD TECHNICIAN login backed by a real `users` row (the reader)."""
    actor = staff_actor(tenant, "field_technician", email)
    return SimpleNamespace(id=actor.id, pk=actor.id, role="field_technician", user=actor.user)


def today():
    return metering_seams.tenant_today()


def captured(day_offset=0, hour=10):
    """An ISO device clock WITH its zone, `day_offset` days from today."""
    day = today() + timedelta(days=day_offset)
    return datetime.combine(day, time(hour, 42, 18), tzinfo=dt_timezone.utc).isoformat()


def build_route(tenant, admin, reader, *, history=True, code="WLK-07"):
    """1318 Maple (units A + B), 1320 Maple (unit A), 1322 Maple (unit A) on
    route WLK-07, assigned to `reader`; 1206 Maple (MTR-0533) is NOT on it.

    Returns a namespace of ids and meter numbers.
    """
    seed_service_config("electric", low_pct=LOW_PCT, high_pct=HIGH_PCT)
    p1 = make_premises(admin, address_line="1318 Maple St", services_available=["electric"])
    u1a = make_unit(admin, p1["id"], label="Unit A", services=["electric"])
    u1b = make_unit(admin, p1["id"], label="Unit B", services=["electric"])
    p2 = make_premises(admin, address_line="1320 Maple St", services_available=["electric"])
    u2a = make_unit(admin, p2["id"], label="Unit A", services=["electric"])
    p3 = make_premises(admin, address_line="1322 Maple St", services_available=["electric"])
    u3a = make_unit(admin, p3["id"], label="Unit A", services=["electric"])
    off = make_premises(admin, address_line="1206 Maple St", services_available=["electric"])
    uoff = make_unit(admin, off["id"], label="Unit A", services=["electric"])
    m1 = a_meter(admin, "MTR-0471", unit_id=u1a["id"])
    m2 = a_meter(admin, "MTR-0472", unit_id=u1b["id"])
    m3 = a_meter(admin, "MTR-0473", unit_id=u2a["id"])
    m4 = a_meter(admin, "MTR-0474", unit_id=u3a["id"])
    m_off = a_meter(admin, "MTR-0533", unit_id=uoff["id"])
    cycle = metering_services.create_cycle(
        admin, {"code": f"CY-{code}", "name": "Cycle 10-A", "frequency": "monthly"}
    )
    route = metering_services.create_route(
        admin,
        {
            "code": code,
            "name": "Maple Heights",
            "service_code": "electric",
            "premises_ids": [p1["id"], p2["id"], p3["id"]],
            "cycle_id": cycle["id"],
        },
    )
    metering_models.Route.objects.filter(pk=route["id"]).update(assigned_to_id=reader.id)
    if history:
        for meter in (m1, m2, m3, m4, m_off):
            twelve_months(meter["id"])
    return SimpleNamespace(
        route_id=route["id"],
        cycle_id=cycle["id"],
        premises=[p1["id"], p2["id"], p3["id"]],
        off_premises=off["id"],
        meters={"MTR-0471": m1, "MTR-0472": m2, "MTR-0473": m3, "MTR-0474": m4, "MTR-0533": m_off},
    )


def twelve_months(asset_id):
    """Twelve committed reads of 700 kWh, 30 days apart, the last 30 days ago
    — the engine's own history for the HIGH/LOW rules and the expected range."""
    start = Decimal("40000")
    for k in range(12, 0, -1):
        day = today() - timedelta(days=30 * k)
        index = 12 - k
        commit_read(
            None,
            asset_id,
            day=day.isoformat(),
            value=str(start + MONTHLY * index),
            consumption=MONTHLY if index else None,
            days_since_prior=30 if index else None,
            prior_value=str(start + MONTHLY * (index - 1)) if index else None,
            unit="kWh",
        )


def a_reading(key, meter_no, value, *, route_id, premises_id=None, unit="kWh", **extra):
    """One captured route reading, as a handset sends it."""
    item = {
        "key": key,
        "kind": "reading",
        "route_id": str(route_id),
        "meter_no": meter_no,
        "identified_by": "scan",
        "reader_status": "read",
        "value": str(value),
        "unit": unit,
        "position": {"lat": "29.785100", "lng": "-95.824500", "accuracy_m": "4", "fix_quality": "good"},
        "captured_at": captured(),
        "remark_source": "voice",
    }
    if premises_id is not None:
        item["premises_id"] = str(premises_id)
    item.update(extra)
    return item


def a_cant_read(key, meter_no, reason, *, route_id, **extra):
    item = {
        "key": key,
        "kind": "reading",
        "route_id": str(route_id),
        "meter_no": meter_no,
        "identified_by": "listed",
        "reader_status": "could_not_read",
        "cant_read_reason": reason,
        "captured_at": captured(),
    }
    item.update(extra)
    return item
