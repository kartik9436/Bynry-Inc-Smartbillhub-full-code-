# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-10155 — after a cycle bill had priced a unit's last water
#           reading, a unit with a never-read sub-meter (and the building's
#           master on its point) could not be moved out: step 3 always said
#           "reading needed" (AC-2026-00041, Mill Pond Apt 101).
#           DEF-BIL-10156 (money) — Apt 104's final bill priced water from a
#           SUB-METER (SM-7201, 5 → 6, 1 kgal) instead of the unit's own meter
#           (W-5043, 2,639 → 2,645, 6 kgal); sewer at 90% followed it.
# Rules:    `assets.billing_asset_ids_for_service_point` (the unit's own meter
#           measures its service; a sub-meter or the building's master does
#           not, unless the point has nothing else) · DEF-BIL-10128/10129 ·
#           DEF-CUS-5931 (price what is keyed, commit at the close) ·
#           DEF-CUS-10093 (Complete drafts the final bill) · law 14
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**One service point, three meters: the unit's own meter prices the bill.**

The fixture is a Mill Pond unit re-cast on this suite's electric fixtures: a
unit meter read 13,800 → 14,100 BEFORE the closing period (the cycle bill has
already billed it), a sub-meter under it, and the building's MASTER meter on
the same point with a sub-meter of its own. At move-out the clerk keys the
unit meter **14,160** (60 kWh) and answers the others as step 2 lets them.

  * a never-read sub-meter keyed, the master ticked *Estimate*  → PRICED, 60 kWh
    (was: *"reading needed"* — DEF-BIL-10155);
  * a sub-meter that WAS read (5) keyed 6                        → 60 kWh, not 1
    (DEF-BIL-10156), and the DRAFT Complete raises prices 60 too — the
    committed path is the cycle bill's path;
  * the unit meter NOT keyed                                    → still refused:
    the meter the bill prices still blocks;
  * a point whose ONLY device is a sub-meter                    → priced from it.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a fix that dropped
sub-meters from the row by IGNORING every keyed value would pass the first
case and fail the third — so the third asserts the refusal still names the
service; and asserting `priced` without the QUANTITY would pass on 1 kgal —
every priced case asserts 60.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.assets import services as asset_services
from apps.billing import final_bill
from apps.billing import models as billing_models
from apps.customers import services as customer_services
from tests.test_def_bil_10052_move_out_draft_bill_values import _unread_account
from tests.test_us_bil_011_final_bill import MOVE_OUT
from tests.test_us_bil_001_prepare import PERIOD_START
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _days_to_pay(monkeypatch):
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "06-S", "name": "Cycle 06", "due_days": 21},
    )


def _sub_meter(actor, *, asset_no, parent_no, unit_id):
    return asset_services.create_asset(
        actor,
        {
            "type": "sub_meter",
            "asset_no": asset_no,
            "parent_asset_no": parent_no,
            "service": "electric",
            "unit": "kWh",
            "read_method": "walk_by",
            "multiplier": "1",
            "register_digits": 5,
            "unit_id": unit_id,
            "install_date": "2026-01-05",
            "status": "active",
            "size_class": asset_models.Asset.objects.filter(asset_no=parent_no)
            .values_list("size_class", flat=True)
            .first(),
        },
    )


def _mill_pond_unit(brazos, dana, monkeypatch, *, n):
    """A unit meter `M-95n0` (read before the period), its sub-meter `S-95n1`,
    the building's master `M-95n2` on the same point and its sub `S-95n3`."""
    unit_meter = f"M-95{n}0"
    account = _unread_account(
        brazos, dana, monkeypatch, asset_no=unit_meter, account_no=f"A-1550{n}"
    )
    unit_id = str(account.unit_id)
    master = a_meter(dana, asset_no=f"M-95{n}2", unit_id=unit_id)
    master_type = asset_models.MeterType.objects.filter(tenant=brazos, code="master").first()
    if master_type is None:  # the tenant's catalog row, as BR-AST-044 seeds it
        master_type = asset_models.MeterType.objects.create(
            tenant=brazos, code="master", name="Master"
        )
    asset_models.Asset.objects.filter(pk=master["id"]).update(meter_type=master_type)
    _sub_meter(dana, asset_no=f"S-95{n}1", parent_no=unit_meter, unit_id=unit_id)
    _sub_meter(dana, asset_no=f"S-95{n}3", parent_no=f"M-95{n}2", unit_id=unit_id)
    return account, unit_meter


def _electric_kwh(body):
    return sum(
        Decimal(str(line["quantity"]))
        for line in body["lines"]
        if line.get("service") == "electric" and line.get("quantity") not in (None, "")
    )


def test_a_never_read_sub_meter_and_an_estimated_master_do_not_block(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account, unit_meter = _mill_pond_unit(brazos, dana, monkeypatch, n=1)
        keyed = [
            {"meter_no": unit_meter, "value": "14160"},
            {"meter_no": "S-9511", "value": "10"},  # never read: no prior
            {"meter_no": "M-9512", "estimate": True},  # no history
        ]
        body = final_bill.preview_final_bill(
            account_id=account.id, moved_out_on=MOVE_OUT, period_start=PERIOD_START, keyed_reads=keyed
        )
    assert body["priced"] is True, body.get("priced_unavailable")
    assert _electric_kwh(body) == Decimal("60"), body["lines"]


def test_the_unit_meter_not_the_sub_meter_prices_the_final_bill(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account, unit_meter = _mill_pond_unit(brazos, dana, monkeypatch, n=2)
        sub = asset_models.Asset.objects.get(tenant=brazos, asset_no="S-9523")
        commit_read(dana, sub.id, day="2026-05-31", value="5", unit="kWh")
        keyed = [
            {"meter_no": unit_meter, "value": "14160"},
            {"meter_no": "S-9521", "value": "7"},
            {"meter_no": "S-9523", "value": "6"},  # keyed LAST — it used to win
        ]
        step3 = final_bill.preview_final_bill(
            account_id=account.id, moved_out_on=MOVE_OUT, period_start=PERIOD_START, keyed_reads=keyed
        )
        assert step3["priced"] is True, step3.get("priced_unavailable")
        assert _electric_kwh(step3) == Decimal("60"), step3["lines"]

        # Complete commits all three on the move day and drafts the bill from
        # the COMMITTED reads — the cycle bill's own path.
        result = customer_services.move_out(
            dana,
            account.id,
            {"moved_out_on": MOVE_OUT.isoformat(), "final_reads": keyed},
        )
        assert result["final_bill"]["outcome"] == "drafted", result["final_bill"]
        (invoice,) = billing_models.Invoice.objects.filter(account_id=account.id, bill_type="final")
        quantities = sum(
            line.quantity or Decimal("0")
            for line in invoice.lines.all()
            if line.unit == "kWh" and line.quantity is not None
        )
    # stored at 6 dp per tier line (rule 2), so the tiers sum to 60 at 2 dp
    assert quantities.quantize(Decimal("0.01")) == Decimal("60.00"), quantities
    assert invoice.total == Decimal(step3["total"])


def test_the_meter_the_bill_prices_still_blocks_when_it_is_not_read(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account, _unit_meter = _mill_pond_unit(brazos, dana, monkeypatch, n=3)
        keyed = [{"meter_no": "S-9531", "value": "10"}, {"meter_no": "M-9532", "estimate": True}]
        body = final_bill.preview_final_bill(
            account_id=account.id, moved_out_on=MOVE_OUT, period_start=PERIOD_START, keyed_reads=keyed
        )
    assert body["priced"] is False
    gap = body["priced_unavailable"]
    assert gap["reason"] == final_bill.PREVIEW_VALUES_MISSING
    assert [row["service"] for row in gap["missing"]] == ["electric"]
    assert gap["missing"][0]["what"] == "reading"


def test_a_point_whose_only_device_is_a_sub_meter_is_billed_from_it(brazos, dana, monkeypatch):
    """The narrowing only ever removes a sub-meter or a master BESIDE a unit
    meter; a sub-metered apartment with nothing else is billed from its sub."""
    from apps.assets import selectors as asset_selectors

    with tenant_ctx(brazos):
        account, unit_meter = _mill_pond_unit(brazos, dana, monkeypatch, n=4)
        meter = asset_models.Asset.objects.get(tenant=brazos, asset_no=unit_meter)
        point = meter.service_point_id
        everything = asset_selectors.asset_ids_for_service_point(point)
        billing = asset_selectors.billing_asset_ids_for_service_point(point)
        assert billing == [str(meter.id)], (everything, billing)
        # Take the unit meter and the master off the point: only subs remain.
        asset_models.Asset.objects.filter(asset_no__in=[unit_meter, "M-9542"]).update(
            service_point_id=None
        )
        only_subs = asset_selectors.billing_asset_ids_for_service_point(point)
    assert sorted(only_subs) == sorted(asset_selectors_ids(["S-9541", "S-9543"]))


def asset_selectors_ids(numbers):
    return [
        str(pk) for pk in asset_models.Asset.objects.filter(asset_no__in=numbers).values_list("pk", flat=True)
    ]
