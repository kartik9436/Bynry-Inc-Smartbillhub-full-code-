# ── Trace ──────────────────────────────────────────────
# Change:  CR-080 — 2026-09-07. THERMAL/HEAT stops being a metered service and
#          becomes a CAPACITY one, billed on CONNECTED TONNAGE.
# Rules:   BR-TEN-1180 (a service is metered, a share, or capacity-based) ·
#          BR-TEN-171 (the ratified size classes) · BR-MET-108 (an absent
#          characteristic bills as ZERO) · BR-TEN-071 (seed data inserts if
#          absent; it never UPDATEs and never DELETEs) · CLAUDE.md hard rule 2
#          (money to 4 decimals) · hard rule 3 (a quantity carries its unit)
# Open Qs: OQ-560 (thermal STEAM's bands) — STILL OPEN, and this file asserts
#          that it is, because a CR that moved the whole service's basis is
#          exactly the change that could close it by accident.
# ───────────────────────────────────────────────────────
"""CR-080 — thermal/heat is capacity-based, on connected tonnage.

**THE RULING, PO verbatim 2026-09-07:** *"connected tonnage - it is capacity
not metering; i will ahve 100 tonne or 200 tonne etc"*, and in the same message
*"it is capacity based - please make a note and figure out the impact - if you
ahve to write a CR to ahndle this please write"*. Confirmed the same day in
their eleven-service walk: *"Thermal — basis disputed - this si correct"*.

⚠ **IT IS A DEBT BEING CALLED IN, NOT A NEW RULING.** The PO already ruled on
**2026-08-27**: *"(a) multiplier replaces bands for capacity services (solar,
battery, thermal); bands stay for pipe/amp/CFH - this si corect"*. Thermal was
named in that sentence and was the one of the three never executed;
`apps/tenancy/service_size_classes.py` recorded the omission against itself for
six days — *"the debt solar just paid, thermal still owes"*. **What this CR
reverses is a LANE judgment made because a ruling had not reached the code.**

WHY THIS FILE IS PURE ARITHMETIC OVER CONSTANTS
------------------------------------------------
`test_cr062_e_rates`' own reason, kept: the cheap half must fail first. Nothing
here needs a database, so a lane that breaks the ladder or the price learns it
in milliseconds rather than after a 130-second migration build. The LIVE halves
are asserted where they already live — `test_cr062_e_rates` for the seeded
schedule and the issued bill, `test_service_billing_coverage` for the estate.

WHAT IS *NOT* RATIFIED HERE, AND MUST NOT BE READ AS IF IT WERE
-----------------------------------------------------------------
The eight tonnages and the `$12.5000` per connected ton are **this lane's
proposal**, authored under the PO's standing delegation for base charges (*"you
can research in amrket at Municiapl utility in north amrica and put it there"*).
The PO named two of the values — 100 and 200 — and invited the rest (*"etc"*).
They are seeded DEFAULTS a tenant edits on Settings → Service sizes, exactly as
fire's six are (`OQ-1360`), and no screen, document or report may present them
as anybody's tariff.
"""

from decimal import Decimal

import pytest

from apps.metering import connections
from apps.tenancy import service_size_classes as ssc
from apps.tenancy.services import SEEDED_UOM_SERVICE_SCOPE, SERVICE_DEFAULT_UOMS
from core import sample_fixture as fixture

#: The eight, in ladder order, with what each is worth. Written out rather than
#: read from the module under test: importing the ladder would assert that it
#: equals itself, which is the shape of a check that cannot fail.
RATIFIED_TONNAGES: tuple[tuple[str, int], ...] = (
    ("TH-T5", 5),
    ("TH-T10", 10),
    ("TH-T25", 25),
    ("TH-T50", 50),
    ("TH-T100", 100),
    ("TH-T200", 200),
    ("TH-T400", 400),
    ("TH-T800", 800),
)

#: The three that are WITHDRAWN. Each was a RANGE, which is precisely why none
#: of them could survive a ruling that makes the service capacity-based.
WITHDRAWN_BANDS = ("TH-CW-25", "TH-CW-25-100", "TH-CW-100P")

#: The lane's proposed rate. NOT a ratified figure — see the module docstring.
PROPOSED_PER_TON_PER_MONTH = Decimal("12.5000")


# ── 1 · THE BASIS AND THE UNIT, WHICH MOVED TOGETHER ──────────────────────
def test_thermal_declares_capacity_in_connected_tons():
    """**The ruling itself.** `metered`/`ton-hr` → `capacity`/`ton`.

    ⚠ **THE TWO MOVE TOGETHER OR NOT AT ALL**, which is the map's own rule:
    *"a service cannot be capacity-based and carry a period as its unit"*.
    `ton-hr` is an ENERGY — a ton of cooling delivered for an hour — so a
    capacity service priced per ton-hour quotes a rate in a unit its quantity
    is not in. That is `DEF-497`, and it is a live money path.

    RED PROVED FIRST — against the pre-CR-080 code:

        AssertionError: assert 'metered' == 'capacity'
        AssertionError: assert 'ton-hr' == 'ton'
    """
    row = SERVICE_DEFAULT_UOMS["thermal_heat"]
    assert row.basis == "capacity"
    assert row.primary == "ton"


def test_klb_stays_and_oq_560_is_not_closed_by_this_change():
    """**`OQ-560` — thermal STEAM's bands — STAYS OPEN, and this asserts it.**

    A change that moves a whole service's basis is exactly the change that
    could settle half of an open question by accident, so the absence is
    checked rather than trusted.

    **`klb` (thousand pounds of steam) keeps the ALT slot deliberately.** It is
    the unit of thermal's steam half, whose boundaries were put to the PO as a
    dimension with no numbers and were never ruled. Dropping it would leave
    `SERVICE_DEFAULT_UOMS` silent about steam, which reads like steam was
    settled — and it would remove the DERIVED half of `klb`'s scope, leaving
    only the fixture's stated one.
    """
    assert SERVICE_DEFAULT_UOMS["thermal_heat"].alt == "klb"
    assert SEEDED_UOM_SERVICE_SCOPE["klb"] == "thermal_heat"
    with pytest.raises(ssc.SizeClassNotRuled) as excinfo:
        ssc.steam_size_classes()
    assert "OQ-560" in str(excinfo.value)


def test_ton_hr_leaves_the_map_and_stays_in_the_catalogue():
    """⚠ **THE BRIEFING'S WORRY, CHECKED RATHER THAN ACCEPTED — AND IT DOES NOT
    HOLD.** `CR-080` was raised with a warning that `_derive_uom_service_scope`
    derives a unit's scope FROM `SERVICE_DEFAULT_UOMS`, so removing a unit there
    would *"silently rescope a catalogue entry"*.

    It cannot, for `ton-hr` OR `klb`, and the reason is one line of `_seed_uoms`:
    it resolves a row as `stated or SEEDED_UOM_SERVICE_SCOPE.get(code)`, and
    **both units STATE `"service": "thermal_heat"` in `lookup_defaults.json`**,
    where the fixture wins. So `ton-hr` leaves the map, keeps its stated scope,
    and `BR-TEN-071` deletes it from nobody — a utility that meters
    chilled-water energy still has the unit to pick.

    Asserted here so the finding survives this session (hard-won law 10): the
    next lane to move a unit between services should not have to re-derive it.
    """
    assert SEEDED_UOM_SERVICE_SCOPE.get("ton-hr") is None, (
        "the DERIVATION no longer claims ton-hr — thermal declares `ton` now"
    )
    fixture_uoms = {row["code"]: row for row in _fixture_json()["uoms"]}
    assert fixture_uoms["ton-hr"]["service"] == "thermal_heat", (
        "the FIXTURE still states it, which is what actually seeds the scope"
    )
    assert fixture_uoms["ton"]["service"] == "thermal_heat"
    assert SEEDED_UOM_SERVICE_SCOPE["ton"] == "thermal_heat", (
        "and the two statements agree for `ton`, so neither can move the other"
    )


def _fixture_json():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "apps/tenancy/fixtures/lookup_defaults.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ── 2 · THE LADDER ────────────────────────────────────────────────────────
def test_the_three_ranges_are_withdrawn():
    """**A RANGE HAS NO SINGLE VALUE A CAPACITY COULD BE**, which is why these
    three could not survive the ruling — and it is the same argument
    `service_size_classes.py` used to give for KEEPING them.

    `BR-TEN-071` deletes them from NOBODY: a tenant that already holds them
    keeps them and may deactivate them on S8. What this asserts is that no NEW
    tenant receives them, which is the only mechanism seed data has — the same
    posture as `E-3P`, solar's four inverter bands and `HYD`.
    """
    seeded = {row["code"] for row in ssc.seed_entries()}
    for code in WITHDRAWN_BANDS:
        assert code not in seeded, f"{code} is a RANGE and is withdrawn by CR-080"
    assert {row["code"] for row in _fixture_json()["service_size_classes"]} == seeded, (
        "the fixture is a MIRROR of the ratified map (BR-TEN-171) and it drifted"
    )


def test_the_eight_connected_tonnages_are_capacities_with_their_unit():
    """Each row is a NUMBER with a UNIT, never a label — the `CR-062` shape.

    The PO's own two figures are in the ladder by name (*"i will ahve 100 tonne
    or 200 tonne etc"*), and **25 and 100 are deliberately kept**: they were the
    boundaries of the three withdrawn ranges, so a tenant reading its own list
    sees the numbers it already had, now as capacities it can multiply.
    """
    rows = {row.code: row for row in ssc.size_class_records_for_service("thermal_heat")}
    assert tuple(rows) == tuple(code for code, _tons in RATIFIED_TONNAGES)
    for code, tons in RATIFIED_TONNAGES:
        assert rows[code].capacity == Decimal(tons), f"{code} is not {tons} ton"
        assert rows[code].capacity_uom == "ton", "hard rule 3 — a quantity carries its unit"
        assert rows[code].is_capacity and not rows[code].is_band


def test_the_display_names_still_say_chilled_water_because_steam_is_unruled():
    """A row reading *"Thermal 100 tons"* would imply the list covers thermal,
    and it covers half of it. `CR-080` moved the service's BASIS and settled
    nothing about steam's boundaries."""
    for row in ssc.size_class_records_for_service("thermal_heat"):
        assert row.name.startswith("Thermal chilled water "), row.name


def test_thermal_sums_and_does_not_count():
    """**THE ARITHMETIC, AND IT IS THE WHOLE OF *"multiplier replaces bands"*.**

    Thermal is solar's shape, not trash's: a building with a 100-ton connection
    and a 25-ton connection has **125 tons** of connected capacity, and 125 ×
    the per-ton rate is what it owes. A COUNT would say *"2"* and price a
    125-ton building exactly like two 5-ton ones.

    The mechanical test a later reader should trust over any comment:
    `capacity_uom_for_service` answers the summing unit for a capacity service
    and `None` for a banded one. If this ever flips, thermal has been turned
    back into bands and that is a conversation, not a merge.
    """
    assert ssc.capacity_uom_for_service("thermal_heat") == "ton"
    assert ssc.total_capacity("thermal_heat", ["TH-T100", "TH-T25"]) == Decimal("125")
    # …and the two services that COUNT still refuse to be summed.
    assert ssc.capacity_uom_for_service("trash") is None
    assert ssc.capacity_uom_for_service("fire") is None


# ── 3 · THE PRICE ─────────────────────────────────────────────────────────
def test_the_per_ton_rate_replaces_the_retired_per_ton_hour_one():
    """**THE ONE PO-APPROVED FIGURE THIS CR REMOVES, AND ITS REPLACEMENT.**

    `$0.045` per ton-hour was put to the PO in plain English with a worked
    figure and approved (`CR-062` E6). A capacity service has no ton-hour, so it
    retires. **`$12.5000` per connected ton per month is NOT a signature** — it
    is this lane's judgment under the PO's market-research delegation, and the
    review-ledger row states the trade so the PO sees what was taken away.

    **Worked, on the PO's own numbers:** 100 tons is `$1,250.00` a month; 200
    tons is `$2,500.00`.
    """
    # ⚠ **THE MAP IS NOT EMPTY AND A FIRST DRAFT OF THIS CASE SAID IT WOULD BE.**
    # `gas` was seeded into it hours earlier the same day by a different lane
    # (`DEF-RAT-4516`, closing `OQ-1290`), and the two changes are independent:
    # gas is a flat-priced METERED service, which is what this map is for, and
    # thermal stopped being one. Asserting emptiness would have made this case
    # fail on a sibling's correct change.
    assert "thermal_heat" not in fixture.METERED_USAGE_PRICES, (
        "the ton-hour price is retired — a capacity service has no ton-hour"
    )
    assert set(fixture.METERED_USAGE_PRICES) == {"gas"}
    rate = fixture.CAPACITY_UNIT_PRICES["thermal_heat"]
    assert Decimal(rate) == PROPOSED_PER_TON_PER_MONTH
    assert len(rate.split(".")[1]) == 4, "hard rule 2 — money is STORED to four"
    assert (Decimal(100) * Decimal(rate)).quantize(Decimal("0.01")) == Decimal("1250.00")
    assert (Decimal(200) * Decimal(rate)).quantize(Decimal("0.01")) == Decimal("2500.00")


def test_the_price_is_quoted_per_the_unit_the_quantity_is_in():
    """`DEF-497`'s guard, one service over: `$12.50 per month` against a
    quantity of 100 tons is a well-formed schedule and a wrong bill."""
    assert fixture.THERMAL_UOM == ssc.capacity_uom_for_service("thermal_heat")
    assert fixture.THERMAL_UOM == SERVICE_DEFAULT_UOMS["thermal_heat"].primary


# ── 4 · WHERE THE QUANTITY COMES FROM ─────────────────────────────────────
def test_the_tonnage_is_a_unit_fact_and_not_a_device():
    """**NOBODY INSTALLS A TON**, which is storm water's own argument.

    A connected tonnage is the size of the building's SERVICE CONNECTION; the
    chiller is the utility's, in the plant, serving hundreds of buildings.
    Route thermal down the equipment path and `billable_asset_size_classes`
    returns an empty list on every unit, `total_installed_capacity` sums to `0`,
    and every thermal line prints `$0.00` on a document that foots perfectly —
    `DEF-2388` exactly, one service over, and no gate in this repo can see it.

    Two services answer a unit key now; the other nine still ask the equipment,
    and that half is asserted here so a later "consistency" change cannot make
    solar read a unit field without going red.
    """
    assert connections.unit_capacity_key("thermal_heat") == "connected_capacity"
    assert connections.unit_capacity_key("storm_water") == "assessment"
    for other in ("solar", "battery", "broadband", "trash", "fire"):
        assert connections.unit_capacity_key(other) is None, (
            f"{other} carries its size on a DEVICE and must keep asking the equipment"
        )


def test_the_estate_stops_planting_a_register_and_starts_recording_tonnage():
    """**A thermal tenant loses 48 meters, an opening read and three months of
    readings, and gains a service point per unit with its tonnage on it.**

    The `THERMAL_UNIT_WITH_NONE` seat is the point of the last assertion: a
    `$0.00` line standing beside real numbers on a real document is what proves
    `BR-MET-108`'s ruled zero REACHES a bill rather than falling into a silence.
    """
    assert "thermal_heat" not in fixture.METERED_ESTATE_SERVICES
    assert "thermal_heat" in fixture.CAPACITY_ESTATE_SERVICES
    assert "thermal_heat" not in fixture.SERVICE_METER_PREFIX
    assert "thermal_heat" not in fixture.CONSUMPTION_SCALE
    assert "thermal_heat" not in fixture.SEASONAL_SHAPE
    assert "thermal_heat" not in fixture.BACKBONE_BASE

    plan = fixture.thermal_tonnage_plan()
    connected = fixture.thermal_connected_unit_indexes()
    assert len(plan) == fixture.UNIT_COUNT - 1, (
        "every unit but one is connected; the exception is the ruled zero"
    )
    assert fixture.THERMAL_UNIT_WITH_NONE not in connected
    ratified = {code for code, _tons in RATIFIED_TONNAGES}
    assert {row["size_class"] for row in plan} <= ratified


def test_the_estate_is_1025_connected_tons_and_bills_12812_50():
    """**THE WORKED ESTATE FIGURE, stated so a person can check it by hand.**

    45 houses at 5 tons + 2 commercial at 100 + the depot at 200 + the mill at
    400 = **1,025 tons**, and `1,025 × $12.5000` = **`$12,812.50`** a month
    before `BR-RAT-101`'s outside-city 1.5x reaches two of the houses.

    ⚠ It is DERIVED from the ladder and the plan rather than typed, which is
    `STORM_WATER_ESTATE_ERU`'s lesson read forward: a literal total went stale
    the afternoon `CR-062`'s addendum appended two units, with a green suite
    behind it (`DEF-2368`).
    """
    total = sum(
        ssc.total_capacity("thermal_heat", [row["size_class"]])
        for row in fixture.thermal_tonnage_plan()
    )
    assert total == Decimal("1025")
    monthly = (total * Decimal(fixture.CAPACITY_UNIT_PRICES["thermal_heat"])).quantize(
        Decimal("0.01")
    )
    assert monthly == Decimal("12812.50")


def test_the_pos_own_two_figures_are_on_the_seeded_estate():
    """*"i will ahve 100 tonne or 200 tonne etc"* — both, by name, so the demo
    bill a person opens shows the numbers they used."""
    by_unit = {row["unit_index"]: row["size_class"] for row in fixture.thermal_tonnage_plan()}
    assert by_unit[fixture.CASE_GOVERNMENT_ACCOUNT] == "TH-T200"
    commercial = {by_unit[i] for i in by_unit if by_unit[i] == "TH-T100"}
    assert commercial == {"TH-T100"}
    assert sum(1 for code in by_unit.values() if code == "TH-T100") == 2


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-080@thermal-capacity
# generated: 2026-09-07 by the CR-080 lane
# checklist: A✔ B✔ C=n/a(pure — no database, no tenant, no query) D=n/a E=n/a
#         F✔ (every case was shown RED against the pre-CR-080 tree before the
#         code changed; the two that name their red quote it) G✔ H=deferred
# exceptions: the eight tonnages and the $12.50 are the lane's proposal under
#         the PO's market-research delegation and are asserted as SEEDED
#         DEFAULTS, never as ratified figures — the module docstring says so
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
