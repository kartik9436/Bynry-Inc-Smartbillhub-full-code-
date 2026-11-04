# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-013 (catch-up) · US-BIL-014 (penalty)   Screens: S30
# Defect:   DEF-BIL-8310 — every catch-up and penalty preview answered 500
# Rules:    BR-BIL-018 (a cut segment nobody read is day-weighted)
# ───────────────────────────────────────────────────────
"""DEF-BIL-8310 — the read-less-segment estimate is asked of a REAL tariff.

`backbill._estimate_read_less_segments` built its *never owed a read* set from
`tariff.service_code`, and `rating_seam.TariffConfig` has no such attribute —
the field is `.service`. Every test that reached the function carried a
`SimpleNamespace` tariff that happened to have `service_code`, so the real
object was never passed through it, and the J70 browser walk found every
catch-up and penalty preview answering `500 SYS-INTERNAL`.

This test hands the function the engine's own `TariffConfig` — a flat water
tariff and a percent-of-service sewer — and asserts the sewer is exempt (it is
never owed a read) while nothing else is estimated when every reading is on
file.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from apps.billing import backbill, rating_seam
from apps.billing.contracts import ServiceReading


def _gathered():
    water = rating_seam.TariffConfig(
        service="water", model="flat", billed_unit="kgal", unit_price=Decimal("3.2500")
    )
    sewer = rating_seam.TariffConfig(service="sewer", model="percent_of_service", billed_unit="kgal")
    data = SimpleNamespace(
        tariffs=(water, sewer),
        readings=(
            ServiceReading(
                service_code="water",
                consumption=rating_seam.Quantity(Decimal("6.1"), "kgal"),
            ),
            # Sewer is priced off water and is never read — the set this
            # function builds from the TARIFF must exempt it.
            ServiceReading(service_code="sewer", consumption=None, absent_reason="no_meter"),
        ),
    )
    return [(date(2026, 7, 1), date(2026, 7, 15), {}, data)]


def test_def_bil_8310__a_real_tariff_config_passes_through_the_segment_estimate():
    gathered = _gathered()
    out, made = backbill._estimate_read_less_segments(
        SimpleNamespace(account=None),
        gathered,
        sub_start=date(2026, 7, 1),
        sub_end=date(2026, 7, 31),
        source="day_weighted",
        scope_services=None,
    )
    # Nothing was short: water is read, sewer is never owed a read.
    assert made == ()
    assert out is gathered


def test_def_bil_8323__a_service_not_in_service_is_never_estimated():
    """Gas with NO meter on the unit is not in service (BR-BIL-301): no line,
    and never a usage to estimate. Listed as short, it refused the whole
    catch-up or penalty (J70 re-walk, penalty on Unit F)."""
    gathered = _gathered()
    data = gathered[0][3]
    data.readings = data.readings + (
        ServiceReading(service_code="gas", consumption=None, absent_reason="no_meter"),
    )
    data.unconnected_services = ("gas",)
    out, made = backbill._estimate_read_less_segments(
        SimpleNamespace(account=None),
        gathered,
        sub_start=date(2026, 7, 1),
        sub_end=date(2026, 7, 31),
        source="day_weighted",
        scope_services=None,
    )
    assert made == ()
    assert out is gathered
