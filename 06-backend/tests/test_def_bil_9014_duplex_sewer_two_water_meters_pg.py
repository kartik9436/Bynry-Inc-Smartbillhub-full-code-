# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-9014 (closed by the save guard in
#          test_def_bil_9014_share_needs_no_meter.py)
# Ruling:  PO 2026-10-02 (decision log, "WATER AT 38% OF ELECTRIC ON TWO WATER
#          METERS IS NOT A VALID CASE"), verbatim: *"this is not valid case …
#          you give me real example"* — and the real example is sewer priced
#          as a share of water on a building with several water meters, which
#          bills as ONE sewer line on the combined water usage (PO 2026-09-30).
# Rules:   BR-RAT-1015 (sewer: a share of the water QUANTITY at sewer's own
#          rate) · BR-BIL-300 (two meters, two water line sets) · CLAUDE.md
#          hard rule 2 (money stored to 4dp) · hard-won law 14
# ───────────────────────────────────────────────────────
"""**THE REAL CASE STILL WORKS, WRITTEN TO POSTGRESQL AND READ BACK.**

A duplex with two water meters reading **6 kgal** and **4 kgal**. Sewer is
**90%** of the water usage at sewer's own **$5.00/kgal**:

    90% × (6 + 4) kgal = 9 kgal × $5.00 = **$45.00, on ONE sewer line**

— never once per meter (that would be 90% × 6 × 5 + 90% × 4 × 5 on two lines
if the split were per meter, or 2 × $45.00 = $90.00 if each meter took the
whole basis, which is `DEF-BIL-9014`'s shape on the invalid case).

The price list is the sibling file's controlled world
(`test_otb_t2_money_paths_pg.py`'s `test_write_*` kind): the engine, the
account, the stage-6 write and the raw-SQL read-back are real. Run it on
PostgreSQL:

    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      DATABASE_URL="postgres://postgres@127.0.0.1:55433/<your db>?sslmode=disable" \\
      pytest -q --reuse-db tests/test_def_bil_9014_duplex_sewer_two_water_meters_pg.py
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from tests import test_br_bil_300_services_rulings_2026_09_30 as rulings
from tests.test_otb_t2_money_paths_pg import (  # noqa: F401 — the fixture is used by name
    FOUR_DP,
    _install,
    _real_account,
    _rolled_back_resolution_chain,
    _rows,
    _stored_total,
    _vendor,
    _write,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SEWER_PERCENT = "90"


def _duplex_world(meter_a: str, meter_b: str):
    world = rulings._world(
        plan_services=["water", "sewer"],
        unit_services=["water"],  # sewer has no meter and no point of its own
        assets={"water": [meter_a, meter_b]},
    )
    inner = world["rating.pricing_inputs"]

    def pricing_inputs(tariff, *args, **kwargs):
        row = inner(tariff, *args, **kwargs)
        if getattr(tariff, "service", None) == "sewer":
            assert row["model"] == "percent_of_service" and row["percent_basis"] == "usage"
            assert row["unit_price"] == "5.00"
            row = {**row, "percent": SEWER_PERCENT}
        return row

    world["rating.pricing_inputs"] = pricing_inputs
    return world


@pytest.mark.usefixtures("_rolled_back_resolution_chain")
def test_duplex_sewer_is_45_00_on_one_line(brazos, dana, monkeypatch):
    """6 + 4 kgal of water; sewer 90% = 9 kgal × $5.00 = **$45.00**, ONE line,
    carrying no meter. Water is two line sets, one per meter (BR-BIL-300):
    6 kgal → 5 × $3.25 + 1 × $4.50 = $20.75 + $8.00; 4 kgal → $13.00 + $8.00.
    Bill: $28.75 + $21.00 + $45.00 + sewer's $5.00 base = **$99.75**."""
    meter_a, meter_b = str(uuid.uuid4()), str(uuid.uuid4())
    with tenant_ctx(brazos):
        real = _real_account(brazos, dana)
        _install(monkeypatch, _duplex_world(meter_a, meter_b))
        data, invoice = _write(
            real,
            [rulings._water(6, asset_id=meter_a), rulings._water(4, asset_id=meter_b)],
        )
        rows = _rows(invoice)
        total = _stored_total(invoice)

    sewer_usage = [(amt, asset) for kind, code, amt, asset in rows if code == "sewer" and kind == "usage"]
    assert sewer_usage == [(Decimal("45.00"), None)], rows
    water_assets = {asset for _k, code, _amt, asset in rows if code == "water"}
    assert water_assets == {meter_a, meter_b}, rows
    assert total == Decimal("99.75"), rows
    assert total == total.quantize(FOUR_DP)
    print(f"PROOF duplex-sewer vendor={_vendor()} rows={rows} total={total}")
