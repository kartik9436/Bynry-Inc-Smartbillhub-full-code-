# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (the one-time bill preview) · CR-171-BRC10 P4.02 (M1)
# Defects:  DEF-BIL-9750 — a move-in that starts sewer can never get a
#           first-bill preview: sewer's `no_meter` read as a missing read
# ───────────────────────────────────────────────────────
"""Sewer priced as a share of water is never WAITING for a read of its own.

BR-RAT-015: sewer bills as a percent of water, so it has no register to read
and metering honestly answers `no_meter` for its service point. The back-bill
path (`backbill._never_read`) already asks the TARIFF whether a read was ever
owed; the preview's `_waits_for_a_reading` asked only the reading's reason, so
every move-in starting sewer answered *"a metered service has no reading in
the window yet"* with both meters read. Pure function — no database.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from apps.billing.one_time import _waits_for_a_reading


def _reading(code, consumption, absent_reason=None):
    return SimpleNamespace(
        service_code=code,
        consumption=consumption,
        asset_count=None,
        absent_reason=absent_reason,
    )


def _data(*readings, tariffs=()):
    return SimpleNamespace(readings=readings, tariffs=tariffs, unconnected_services=())


SEWER_SHARE = SimpleNamespace(service="sewer", model="percent_of_service")
WATER = SimpleNamespace(service="water", model="tiered")


def test_sewer_billed_as_share_of_water_does_not_wait():
    data = _data(
        _reading("water", Decimal("2.6")),
        _reading("sewer", None, "no_meter"),
        tariffs=(WATER, SEWER_SHARE),
    )
    assert _waits_for_a_reading(data) is False


def test_a_metered_service_with_no_read_still_waits():
    # The half that is the deliverable: a meter nobody read still waits.
    data = _data(
        _reading("water", None, "no_reading"),
        _reading("sewer", None, "no_meter"),
        tariffs=(WATER, SEWER_SHARE),
    )
    assert _waits_for_a_reading(data) is True


def test_sewer_with_a_consumption_priced_tariff_and_no_meter_still_waits():
    # BR-MET-134 / DEF-161: only the pricing MODEL exempts it; a flat or
    # tiered sewer with no meter is a human's exception.
    data = _data(
        _reading("water", Decimal("2.6")),
        _reading("sewer", None, "no_meter"),
        tariffs=(WATER, SimpleNamespace(service="sewer", model="flat")),
    )
    assert _waits_for_a_reading(data) is True
