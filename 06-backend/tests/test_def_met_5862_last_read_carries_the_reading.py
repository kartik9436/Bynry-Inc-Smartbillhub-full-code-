# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-5862 — the `Last read` summary carried the USAGE and not the
#          READING, so a register's FIRST read (no previous value, therefore no
#          consumption) reached every screen as a bare date over a reading that
#          exists. Reported by the PO on 2026-09-19 against a sub-meter whose
#          reading they could already see on the Reads list and on the asset's
#          own tab; ruled *"fix it"* the same day.
# Screens: PRM-03 Assets tab (S15) · PRM-02 Assets tab · S49 registry · the map
# Rules:   BR-MET-106 / DEF-079 (an unread register is ABSENT, never a zero) ·
#          BR-MET-028 (an ESTIMATE has a consumption and NO current_value) ·
#          BR-MET-016/053 (the newest committed LINEAGE HEAD) ·
#          CLAUDE.md hard rule 3 (a quantity always carries its explicit unit)
# Tests:   this file · 07-frontend/src/features/metering/UnitAssetsColumns.dom.test.tsx
# ───────────────────────────────────────────────────────
"""The reading and the usage are two facts, and either can be absent alone.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — CLAUDE.md hard-won law 7(2).**
*"The payload carries a number"* passes on the consumption it already carried,
which is the defect. So every case below asserts `current_value` BY VALUE, and
the two directions of absence are separate cases rather than one:

  * a **first read** has a reading and NO usage — the PO's reported case;
  * an **estimate** has a usage and NO reading (`BR-MET-028`) — the mirror, and
    the reason the two fields are never derived from each other.

A single case covering only the happy read would pass if `current_value` were
quietly defaulted from `consumption`, which is precisely the collapse this
defect was.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

from apps.metering import models as metering_models  # noqa: E402
from apps.metering import selectors as metering_selectors  # noqa: E402

pytestmark = pytest.mark.django_db


def _commit(tenant, asset_id, *, day, current_value, consumption, unit="kgal"):
    """One committed read, written directly — HISTORY SETUP only, the same
    posture `tests/test_br_met_106_monthly_usage._read` states."""
    return metering_models.MeterRead.objects.create(
        tenant_id=tenant.id,
        asset_id=asset_id,
        read_at=datetime(day[0], day[1], day[2], tzinfo=timezone.utc),
        channel="total",
        current_value=None if current_value is None else Decimal(str(current_value)),
        consumption=None if consumption is None else Decimal(str(consumption)),
        unit=unit,
        source="import",
        status="ok",
        lifecycle="committed",
    )


def _meter(dana, asset_no="W-5042"):
    prem = make_premises(dana, address_line="1408 Bluestem Ln")
    unit = make_unit(dana, prem["id"], label="Apt 103")
    return make_asset(dana, asset_no=asset_no, unit_id=unit["id"], install_date="2026-01-05")


def test_a_first_read_serves_its_reading_and_no_usage(brazos, dana):
    """The PO's case. `brazosbend`'s own `W-5042` is the shape copied here: its
    earliest read holds `current_value=2585.000000` with `consumption=None`,
    because there is no previous value to subtract."""
    with tenant_ctx(brazos):
        asset = _meter(dana)
        _commit(brazos, asset["id"], day=(2026, 5, 27), current_value="2554.000000",
                consumption=None)
        answer = metering_selectors.latest_read_for_asset(asset["id"])

    assert answer is not None, "a committed read must not read as no read at all"
    # ⚠ **THE RED PROOF.** Before this fix the key did not exist and the cell
    # drew a bare date — over a reading the clerk could see on two other screens.
    assert answer["current_value"] == "2554.000000", (
        "the REGISTER's own figure is what a clerk checks against the dial"
    )
    # An absence, never a zero: `0 kgal` would state the meter measured nothing.
    assert answer["consumption"] is None
    assert answer["unit"] == "kgal", "hard rule 3 — a quantity never travels bare"
    assert answer["read_at"] == "2026-05-27"


def test_a_later_read_serves_both_numbers(brazos, dana):
    with tenant_ctx(brazos):
        asset = _meter(dana)
        _commit(brazos, asset["id"], day=(2026, 5, 27), current_value="2554.000000",
                consumption=None)
        _commit(brazos, asset["id"], day=(2026, 8, 11), current_value="2585.000000",
                consumption="10.000000")
        answer = metering_selectors.latest_read_for_asset(asset["id"])

    # The NEWEST head, and both of its facts.
    assert answer["read_at"] == "2026-08-11"
    assert answer["current_value"] == "2585.000000"
    assert answer["consumption"] == "10.000000"


def test_an_estimate_serves_its_usage_and_NO_reading(brazos, dana):
    """`BR-MET-028`'s mirror: nobody read the dial, so there is a consumption
    and no register figure. Neither field may be derived from the other."""
    with tenant_ctx(brazos):
        asset = _meter(dana)
        _commit(brazos, asset["id"], day=(2026, 8, 11), current_value=None,
                consumption="9.500000")
        answer = metering_selectors.latest_read_for_asset(asset["id"])

    assert answer["current_value"] is None, (
        "an estimate has no reading, and inventing one would claim a dial was read"
    )
    assert answer["consumption"] == "9.500000"


def test_the_batched_answer_is_byte_identical_to_the_singular(brazos, dana):
    """⚠ **THE PIN THAT CANNOT BE EDITED INTO AGREEMENT.** `asset_dict` relies
    on `latest_reads_for_assets` publishing `latest_read_for_asset`'s own shape,
    and `asset_page_rows` fills the key from the batch while the single-row path
    calls the singular. A field added to one and not the other would serve two
    different payloads for one row — so both sides are RECOMPUTED here and
    compared, rather than each checked against a literal."""
    with tenant_ctx(brazos):
        first = _meter(dana, asset_no="W-5042")
        second = _meter(dana, asset_no="W-5043")
        _commit(brazos, first["id"], day=(2026, 5, 27), current_value="2554.000000",
                consumption=None)
        _commit(brazos, second["id"], day=(2026, 8, 11), current_value="2585.000000",
                consumption="10.000000")
        singular = {
            str(first["id"]): metering_selectors.latest_read_for_asset(first["id"]),
            str(second["id"]): metering_selectors.latest_read_for_asset(second["id"]),
        }
        batched = metering_selectors.latest_reads_for_assets([first["id"], second["id"]])

    assert batched == singular, (
        "the batched and per-row reads disagree — `asset_page_rows` and "
        "`asset_dict` would then serve two different rows for one asset"
    )
    # And the field this defect added is actually in both, rather than the two
    # agreeing by both being wrong.
    assert all("current_value" in row for row in batched.values())


# packet: DEF-MET-5862 (maintenance lane, PO ruling 2026-09-19 — *"fix it"*)
# generated: 2026-09-19 by the unit-assets maintenance lane. Every case was RED
#   first against the shipped selector, which raised `KeyError: 'current_value'`
#   — the key did not exist on either path.
# ──────────────────────────────────────────────────────────
