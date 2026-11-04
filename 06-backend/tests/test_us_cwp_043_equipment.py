# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-043 (EP-CWP-08) — *Meters and equipment at the property*.
#           Screen: CWP-037 (blueprint `P23`)
# Rules:    BR-CWP-073 (equipment is what an unmeasured service is billed on) ·
#           B14 rule 31 (no database id is ever a visible value — TC-5) ·
#           BR-AST-007 (the test cadence is DERIVED; the stored status never
#           moves) · BR-AST-017 (only the CURRENT assignment) · BR-CWP-010
#           (tenant AND account set, in the query) · BR-CWP-093 (an empty state,
#           never a blank table)
# Tests:    this file — `US-CWP-043` §3 TC-1 … TC-8
# Impacts:  apps/assets/equipment_reads.py · apps/metering/portal_reads.py ·
#           apps/portal/seams/metering_seam.py · apps/portal/selectors.py
# ───────────────────────────────────────────────────────
"""`US-CWP-043`'s eight cases. **Four of them are absences and they are the point.**

TC-2 (a cart has no last read and the cell is EMPTY, not zero), TC-4 (a
sub-meter on another unit is absent), TC-5 (every identifier is a serial) and
TC-8 (an empty state, never a blank table) are all about something NOT being
there — which is what `BR-CWP-093` and B14 rule 31 are for.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.portal import selectors
from core.tenancy import tenant_context

from tests.test_us_cwp_usage_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_usage_helpers import (
    BACKFLOW_SERIAL,
    CART_SERIAL,
    WATER_SERIAL,
    a_backflow_device,
    a_read,
    a_refuse_cart,
    a_water_meter,
    elm_unit_with_services,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 9, 2)


class _Principal:
    def __init__(self, tenant_id, account_ids):
        self.tenant_id = tenant_id
        self.account_ids = tuple(str(one) for one in account_ids)
        self.accounts = ()


def a_property_with_three_things(tenant, actor):
    """`US-CWP-043` §4 — the meter, the cart and the backflow device."""
    account = elm_unit_with_services(tenant, actor)
    meter = a_water_meter(tenant, actor, account.unit_id)
    a_refuse_cart(tenant, actor, account.unit_id)
    a_backflow_device(tenant, actor, account.unit_id)
    a_read(tenant, account, meter["id"], day=date(2026, 8, 31),
           current="153040", consumption="4820")
    return account, meter


def read(tenant, account):
    with tenant_context(tenant.id):
        return selectors.account_equipment(
            _Principal(tenant.id, [account.pk]), account, today=TODAY
        )


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · THREE ITEMS, EACH WITH WHERE IT IS AND WHAT STATE IT IS IN
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__three_items_each_with_where_and_status(pine_hill, sarah):
    account, _meter = a_property_with_three_things(pine_hill, sarah)
    rows = read(pine_hill, account)["equipment"]

    by_serial = {row["serial_no"]: row for row in rows}
    assert set(by_serial) == {WATER_SERIAL, CART_SERIAL, BACKFLOW_SERIAL}

    water = by_serial[WATER_SERIAL]
    assert water["where"] == "Front boundary box"
    assert water["fitted_on"] == "2021-03-04"
    assert water["status"], "the tenant's own lifecycle word, never one we invented"
    assert water["last_read_on"] == "2026-08-31"

    cart = by_serial[CART_SERIAL]
    assert cart["where"] == "Rear alley"
    assert cart["fitted_on"] == "2024-01-15"


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · negative — THE CART HAS NO LAST READ AND THE CELL IS EMPTY, NOT ZERO
# ══════════════════════════════════════════════════════════════════════════
def test_tc2__the_cart_has_no_last_read_and_it_is_none_never_zero(pine_hill, sarah):
    """⚠ **`0` WOULD TELL A CUSTOMER THEIR CART MEASURED NOTHING.** It measures
    nothing at all — it is billed by being there (`BR-RAT-090`)."""
    account, _meter = a_property_with_three_things(pine_hill, sarah)
    rows = read(pine_hill, account)["equipment"]
    cart = next(row for row in rows if row["serial_no"] == CART_SERIAL)
    assert cart["last_read_on"] is None
    assert cart["last_read_on"] != 0 and cart["last_read_on"] != "0"


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · THE BACKFLOW DEVICE SHOWS ITS TEST DUE, FROM THE EXISTING CADENCE
# ══════════════════════════════════════════════════════════════════════════
def test_tc3__the_backflow_device_reports_its_next_test_from_the_cadence(pine_hill, sarah):
    """`BR-AST-007` — DERIVED from `last_test_date + test_interval_months`.
    14 Nov 2025 + 12 months = **14 Nov 2026**, which is the screen's *TEST DUE
    NOV*; the DATE travels and the catalogue writes the month."""
    account, _meter = a_property_with_three_things(pine_hill, sarah)
    rows = read(pine_hill, account)["equipment"]
    device = next(row for row in rows if row["serial_no"] == BACKFLOW_SERIAL)
    assert device["test_due_on"] == "2026-11-14"
    #: Not due yet on 2 September — the chip says *due*, not *overdue*.
    assert device["test_due"] is False


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · negative — A SUB-METER ON ANOTHER UNIT IS ABSENT
# ══════════════════════════════════════════════════════════════════════════
def test_tc4__equipment_on_another_unit_never_appears(pine_hill, sarah):
    """Absent BY CONSTRUCTION: the read is the unit's current assignments, so
    there is no filter here for a later lane to widen."""
    from apps.metering import models as metering_models

    account, _meter = a_property_with_three_things(pine_hill, sarah)
    # ⚠ Unit `B` at `1408 Elm St` ALREADY EXISTS — `seed_street` creates the
    # whole address, not just the flat Maria lives in. Creating a second one is
    # refused by name (`metering.unit.label_duplicate`), which is the product
    # being right; the fixture uses the neighbour that is really there.
    with tenant_context(pine_hill.id):
        other = metering_models.Unit.objects.filter(
            premises_id=account.unit.premises_id, label="B"
        ).first()
    assert other is not None, "the fixture's own street seeds 1408 Elm St · B"
    a_water_meter(pine_hill, sarah, other.id, serial="99-00001", asset_no="M-99000")

    serials = {row["serial_no"] for row in read(pine_hill, account)["equipment"]}
    assert "99-00001" not in serials
    assert WATER_SERIAL in serials


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · negative — EVERY IDENTIFIER IS A SERIAL, NEVER A ROW ID
# ══════════════════════════════════════════════════════════════════════════
def test_tc5__no_database_id_is_served_at_all(pine_hill, sarah):
    """B14 rule 31, and `DEF-3158`'s clause: eight characters of a uuid is the
    same breach as a whole one, so the safest shape is a payload that carries
    NO id — this one asserts the key is simply not there."""
    account, meter = a_property_with_three_things(pine_hill, sarah)
    rows = read(pine_hill, account)["equipment"]
    for row in rows:
        assert "asset_id" not in row
        assert "id" not in row
        #: …and no VALUE on the row is the asset's uuid either.
        assert str(meter["id"]) not in {str(value) for value in row.values()}


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · tenant isolation — PINE HILL ASSETS ONLY
# ══════════════════════════════════════════════════════════════════════════
def test_tc6__an_oak_ridge_session_reads_none_of_pine_hills_equipment(
    pine_hill, sarah, oak_ridge, elena
):
    """⚠ **THE SEAM REFUSES A MISMATCH BY NAME** (`BR-CWP-005`), rather than
    quietly answering with the tenant that happens to be in context."""
    account, _meter = a_property_with_three_things(pine_hill, sarah)
    with tenant_context(oak_ridge.id):
        with pytest.raises(RuntimeError, match="BR-CWP-005"):
            selectors.account_equipment(
                _Principal(pine_hill.id, [account.pk]), account, today=TODAY
            )


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · negative — A PROPERTY WITH NO RECORDED EQUIPMENT
# ══════════════════════════════════════════════════════════════════════════
def test_tc8__no_equipment_is_an_empty_list_the_screen_states(pine_hill, sarah):
    """`BR-CWP-093` — an empty state naming what will fill it, never a blank
    table of dashes. The READ's job is to answer `[]` honestly."""
    account = elm_unit_with_services(pine_hill, sarah)
    assert read(pine_hill, account)["equipment"] == []
