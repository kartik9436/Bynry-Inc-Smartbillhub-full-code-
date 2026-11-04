# ── Trace ──────────────────────────────────────────────
# Change:   CR-062 group A (tasks A1–A6) — 12-governance/11-change-requests.md
# Rules:    BR-TEN-171 (the ratified utility-service size classes) ·
#           CLAUDE.md hard rule 3 (a quantity always carries an explicit unit) ·
#           CLAUDE.md hard rule 2 (never float; Decimal from a string)
# Tests:    this file is the RED-first proof for CR-062 A1–A6. Every case here
#           was run against the pre-CR code and failed before a line of
#           `service_size_classes.py` was changed — see the lifecycle trailer.
# Impacts:  06-backend/apps/tenancy/service_size_classes.py (the source) ·
#           apps/tenancy/fixtures/lookup_defaults.json (the mirror)
# ───────────────────────────────────────────────────────
"""CR-062 group A — solar, battery and storm water are sized by CAPACITY, and a
capacity is a NUMBER WITH A UNIT that can be added up.

WHAT THE PRODUCT OWNER ASKED FOR, VERBATIM (2026-09-02)
--------------------------------------------------------
    "for panels you will need various capacityes similarly the capacities we
     have created for Trash cart - you need to do it for Solar, Battery and
     Strom water also - show me all that youa re going to include in settings"

    "In solar youa re still not doing it correctly - For example We have 10
     Types of Solar panel with various capaity 1 Kw, 2Kw 3Kw 4Kw so and SO
     forth ; on given Unit we have installed 3 panels with 2Kw, 4Kw and 8 Kw ,
     it means the totla capacity will be 14 Kw ; rate will be for 1 Kw = 14 $
     per KW then bill should be 14 X 14 = 156 $"

⚠ **THE ARITHMETIC IN THAT SECOND QUOTE IS OFF BY ONE PRODUCT AND THIS FILE
ASSERTS THE CORRECT FIGURE.** 14 kW at $14.00 per kW is **$196.00**, not $156.
The PO was told so in the same session and did not dispute it. `$156` appears
nowhere in this repo's code or fixtures, deliberately: a wrong figure copied
into a fixture becomes a wrong figure asserted by a test, and then it is the
product's answer. This file asserts the **14 kW** half — the sum — and the money
half (`14 × $14.00 = $196.00`) belongs to the lane seeding the rate.

WHY A COUNT IS NOT A SUM, AND WHY THAT IS THE WHOLE POINT
---------------------------------------------------------
Trash's answer is *"Cart sizes will decide price X how many Cart"* — the size
picks a rate and the COUNT multiplies it. Solar's answer is the opposite: three
panels of 2 kW, 4 kW and 8 kW are **14 kW**, not **3**. Under a count model that
array would price identically to three 1 kW panels.

So "capacity based" is not one billing shape but TWO, and the difference is
arithmetic rather than labelling. `test_trash_counts_and_refuses_to_be_summed`
is the case that keeps them apart: it asserts that asking trash for a total
capacity REFUSES, because 35 gallons + 2 cubic yards is not a quantity.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.tenancy import service_size_classes as ssc

# ── A1 · the ten solar panel types, as put to the PO ──────────────────────
SOLAR_EXPECTED = tuple((f"SOL-P{n}", f"Solar panel {n} kW", Decimal(n)) for n in range(1, 11))

# ── A2 · the six battery types ────────────────────────────────────────────
BATTERY_EXPECTED = tuple(
    (f"BAT-{n}", f"Battery {n} kW", Decimal(n)) for n in (5, 10, 15, 20, 25, 30)
)

# ── A3 · the five storm water sizes, by property shape ────────────────────
STORM_WATER_EXPECTED = (
    ("SW-SF", "Single-family home", Decimal(1)),
    ("SW-DUP", "Two-unit home", Decimal(2)),
    # PO 2026-10-03 (option A) — one flat of a block, charged per unit.
    ("SW-FLAT", "Flat", Decimal(2)),
    ("SW-APT", "Apartment building", Decimal(6)),
    ("SW-COM-S", "Small commercial", Decimal(4)),
    ("SW-COM-L", "Large commercial", Decimal(10)),
)

#: A4 + A3's reversal — the eight codes this CR WITHDRAWS. Solar's four were
#: already superseded on 2026-08-27 and never removed; storm water's four are a
#: genuine reversal of a signed list, which the PO was shown and did not decline.
WITHDRAWN_CODES = (
    "SOL-5",
    "SOL-5-10",
    "SOL-10-25",
    "SOL-25P",
    "SW-1ERU",
    "SW-2-5",
    "SW-6-20",
    "SW-20P",
)

#: The services sized by a summable capacity, and the ONE unit each sums in.
#: Broadband is here because its three ratified rows already STATE their
#: capacity in their own names ("Broadband 100 Mbps") — the number is
#: transcribed, not chosen, and no code, name or count moves.
CAPACITY_SERVICE_UOMS = {
    "storm_water": "ERU",
    "solar": "kW",
    "broadband": "Mbps",
    "battery": "kW",
    # CR-080 (PO 2026-09-07) — thermal/heat, in CONNECTED REFRIGERATION TONS.
    # It arrived here from `BANDED_SERVICES` below, which is the whole change.
    "thermal_heat": "ton",
}

#: The services sized by a BAND — a label that picks a rate and cannot be added
#: to another label. Trash is the load-bearing one: its carts are gallons and
#: its dumpsters are cubic yards, so there is no unit in which "a 96-gallon cart
#: plus a 4 cu-yd dumpster" is a quantity at all.
#: ⚠ **`thermal_heat` LEFT THIS TUPLE ON 2026-09-07 (`CR-080`).** The PO ruled
#: it capacity-based on connected tonnage, so its three RANGE bands are
#: withdrawn and eight capacities in `ton` take their place. It is in
#: `CAPACITY_SERVICE_UOMS` above now, and `test_a6` below — which asserts that a
#: band carries NO capacity — would fail on it correctly if it stayed here.
BANDED_SERVICES = ("electric", "water", "gas", "trash")

#: BR-TEN-171's arithmetic for THIS CR, as a subtraction and an addition rather
#: than as a total. 40 rows becomes 53: eight are withdrawn (solar's four bands,
#: storm water's four) and twenty-one arrive (10 solar + 5 storm water + 6
#: battery). 40 − 8 + 21 = 53.
#:
#: ⚠ **THE TOTAL ITSELF IS NOT PINNED HERE ANY MORE, AND `DEF-3085` IS WHY.**
#: This constant was `RATIFIED_TOTAL_AFTER_CR062 = 53` and the guard below
#: asserted the delivered length against it. `CR-063` then appended fire's seven
#: bands hours later — an entirely lawful, entirely unrelated change — and this
#: file went RED with `assert 60 == 53` while nothing it is about had moved. It
#: is `DEF-3104`'s lesson one file along: **a row COUNT is allocation, not law,
#: and pinning it turns every later service into a failure in an unrelated
#: suite.**
#:
#: What replaces it is strictly stronger, not weaker. The guard now asserts the
#: RELATIONSHIP — the delivered fixture rows ARE the ratified law, row for row —
#: so a content change with no fixture regeneration still fails loudly and by
#: name, while a TWELFTH service costs this file nothing. The eight withdrawals
#: and the twenty-one arrivals are still asserted BY CODE, which is where this
#: CR's actual content lives.
CR062_WITHDRAWN = 8
CR062_ADDED = 21


def _records(service: str):
    """The full ratified rows for one service, capacity included."""
    return ssc.size_class_records_for_service(service)


# ── A1 ─────────────────────────────────────────────────────────────────────
def test_a1__solar_has_ten_panel_types_from_one_to_ten_kilowatts():
    """*"We have 10 Types of Solar panel with various capaity 1 Kw, 2Kw 3Kw
    4Kw so and SO forth"*.

    Asserted by code, name AND number, because the number is the whole point of
    this CR: a display name reading "Solar panel 4 kW" is a label, and a label
    cannot be added to another label.
    """
    rows = _records("solar")
    assert len(rows) == 10
    assert tuple((r.code, r.name, r.capacity) for r in rows) == SOLAR_EXPECTED
    assert {r.capacity_uom for r in rows} == {"kW"}


# ── A2 ─────────────────────────────────────────────────────────────────────
def test_a2__battery_has_six_types_from_five_to_thirty_kilowatts():
    """Battery had NO list at all before this CR — `()`, *"ruled to have none"*.

    ⚠ **THAT RULING IS NOT REOPENED AND THIS CASE MUST NOT BE READ AS
    REOPENING IT.** `OQ-561` was DISSOLVED by the PO on 2026-08-27, not
    answered: *"there are no kW boundaries to state, because battery is not
    banded at all"*. These six rows state no boundary — nobody is being asked
    where one price stops and the next begins. They are a catalogue of the
    equipment a utility installs, which is exactly what the PO asked for on
    2026-09-02 and is the same ruling read forward, not reversed.
    See `test_a5__battery_gained_a_catalogue_and_did_not_gain_bands`.
    """
    rows = _records("battery")
    assert len(rows) == 6
    assert tuple((r.code, r.name, r.capacity) for r in rows) == BATTERY_EXPECTED
    assert {r.capacity_uom for r in rows} == {"kW"}


# ── A3 ─────────────────────────────────────────────────────────────────────
def test_a3__storm_water_has_five_property_sizes_in_equivalent_residential_units():
    """*"Storm water - it is capacity based not unmetered , capaicyt is decided
    based on sizes of propoerty"*.

    ⚠ **THIS REPLACES A RATIFIED LIST AND IS A REVERSAL, NOT A TIDY-UP.** Storm
    water's four ERU BANDS were signed on 2026-08-27 and were NOT covered by
    the capacity-multiplier ruling of that day, which named only solar, battery
    and thermal. The PO was shown this change explicitly on 2026-09-02, told
    they could decline it, and said to execute.

    The names are what a clerk sees, so they name the PROPERTY and not the
    arithmetic — B14 rule 32's description budget, and rule 31's ban on showing
    an internal code as a field's value.
    """
    rows = _records("storm_water")
    assert len(rows) == 6  # + SW-FLAT, PO 2026-10-03
    assert tuple((r.code, r.name, r.capacity) for r in rows) == STORM_WATER_EXPECTED
    assert {r.capacity_uom for r in rows} == {"ERU"}


# ── A4 ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("code", WITHDRAWN_CODES)
def test_a4__the_superseded_bands_are_gone_from_every_ratified_list(code):
    """Solar's four bands were superseded on 2026-08-27 and never withdrawn.

    The file said so itself, in its own words: *"the supersession stands and is
    owed"*. This CR pays that debt, and takes storm water's four with it for the
    reason recorded on `test_a3`.

    A withdrawn code must be gone from BOTH the law and the fixture it feeds —
    it may not linger in one and not the other, which is what
    `test_a6__the_fixture_still_mirrors_the_law` checks from the other side.
    """
    seeded = {row["code"] for row in ssc.seed_entries()}
    assert code not in seeded


def test_a4__nothing_else_left_the_ratified_set():
    """The reversal is EIGHT codes and no more.

    Written as a subtraction rather than as a list of survivors, because a
    withdrawal that quietly took a ninth code with it is exactly the kind of
    loss that reads as a register and not as an error (CLAUDE.md law 11's
    arithmetic clause, applied to data).
    """
    seeded = {row["code"] for row in ssc.seed_entries()}
    # ⚠ `TH-CW-25` WAS IN THIS LIST UNTIL 2026-09-07 AND IS NOW WITHDRAWN
    # ITSELF (`CR-080`), so it can no longer stand as proof that CR-062's
    # reversal stopped where it said it did. `BAT-5` replaces it — a row CR-062
    # ADDED, which is the same guarantee read from the other side.
    for keep in ("W-5", "CART-96", "G-250", "E-CT", "BB-100", "BAT-5"):
        assert keep in seeded, f"{keep} was not part of this reversal"


# ── A5 ─────────────────────────────────────────────────────────────────────
def test_a5__battery_gained_a_catalogue_and_did_not_gain_bands():
    """`OQ-561` stays DISSOLVED. This case exists so the next reader cannot
    mistake six equipment capacities for six price boundaries.

    The distinction is mechanical and this asserts it mechanically: a BAND
    service answers `None` when asked what unit it sums in, because it does not
    sum. Battery answers `kW`. If a later lane ever turns these six back into
    bands, `capacity_uom_for_service("battery")` becomes `None` and this goes
    RED — which is the conversation that should happen before it ships.
    """
    assert ssc.capacity_uom_for_service("battery") == "kW"
    assert "battery" not in ssc.UNBANDED_SERVICE_DIMENSIONS
    assert ssc.size_classes_for_service("battery") != ()


# ── A6 · the structural half ───────────────────────────────────────────────
def test_a6__the_POs_own_example_adds_up_to_fourteen_kilowatts():
    """*"on given Unit we have installed 3 panels with 2Kw, 4Kw and 8 Kw , it
    means the totla capacity will be 14 Kw"*.

    **This is the case the whole CR exists for.** Under the old structure a size
    class was a code and a display name, so the only answer the product could
    give for three panels was **3**. The money half — 14 kW at $14.00 per kW is
    **$196.00** — is asserted by the lane that seeds the rate; what is proved
    here is that the quantity reaching it is 14 and not 3.
    """
    total = ssc.total_capacity("solar", ["SOL-P2", "SOL-P4", "SOL-P8"])
    assert total == Decimal("14")
    assert ssc.capacity_uom_for_service("solar") == "kW"


def test_a6__a_capacity_is_a_decimal_and_never_a_float():
    """CLAUDE.md hard rule 2 forbids float for money, and a capacity is
    MULTIPLIED BY a money figure — so a float here is a money error one
    operation later. Every capacity is a `Decimal` built from an exact value.
    """
    for service in CAPACITY_SERVICE_UOMS:
        for row in _records(service):
            assert isinstance(row.capacity, Decimal), f"{row.code} is not a Decimal"
            assert not isinstance(row.capacity, float)
            assert row.capacity > 0


def test_a6__a_capacity_never_travels_without_its_unit():
    """CLAUDE.md hard rule 3: a quantity always carries an explicit unit, never
    assumed. Enforced as a BIDIRECTIONAL invariant — a number without a unit and
    a unit without a number are both refused — because the dangerous direction
    is the one a reader would not think to check.
    """
    for service in ssc.SERVICE_ORDER:
        if service in ssc.UNBANDED_SERVICE_DIMENSIONS:
            continue
        for row in _records(service):
            assert (row.capacity is None) == (row.capacity_uom is None), (
                f"{row.code} carries one half of a quantity: "
                f"capacity={row.capacity!r} unit={row.capacity_uom!r}"
            )


def test_a6__one_service_sums_in_exactly_one_unit():
    """You cannot add kW to Mbps. A service whose rows disagreed about their
    unit would produce a total that is a number with no meaning, and nothing
    downstream could detect it — the sum would simply be wrong.
    """
    for service, expected in CAPACITY_SERVICE_UOMS.items():
        units = {r.capacity_uom for r in _records(service)}
        assert units == {expected}, f"{service} sums in {units}, expected {expected}"


@pytest.mark.parametrize("service", BANDED_SERVICES)
def test_a6__a_band_carries_no_capacity_at_all(service):
    """A band is a LABEL that picks a rate. Electric's `E-1P-200` is a service
    entrance rating, water's `W-2` is a pipe diameter, trash's `CART-96` is a
    container — none of the three is a quantity you can add to another one.

    ⚠ **THERMAL'S `TH-CW-25` USED TO BE THE THIRD EXAMPLE HERE, *"a RANGE with
    no single value"*, AND THAT IS EXACTLY WHY IT COULD NOT SURVIVE `CR-080`.**
    The PO ruled thermal capacity-based on 2026-09-07; a capacity is a number
    you multiply, and *"25–100"* is not one. The three ranges are withdrawn and
    eight connected tonnages replace them.

    They are `None` rather than `0`, and the difference matters: a zero would
    sum silently to a wrong answer, and `None` refuses.
    """
    rows = _records(service)
    assert rows, f"{service} seeds no rows at all"
    assert all(r.capacity is None for r in rows)
    assert all(r.capacity_uom is None for r in rows)
    assert ssc.capacity_uom_for_service(service) is None


def test_a6__trash_counts_and_refuses_to_be_summed():
    """**The case that keeps the two billing shapes apart**, and the reason
    `capacity` is `None` for a band instead of the cart's gallon figure.

    PO, statement (3): *"Trash - it is capacity based and Cart sizes will decide
    price X how many Cart"* — the size picks the rate and the COUNT multiplies.
    A 96-gallon cart therefore has no summable capacity, and this asserts that
    asking for one is refused by name rather than answered wrongly.

    ⚠ It is also physically impossible: trash's seven rows are three CARTS in
    gallons and four DUMPSTERS in cubic yards, so there is no unit in which the
    sum exists.
    """
    with pytest.raises(ssc.NotACapacityService) as caught:
        ssc.total_capacity("trash", ["CART-96", "CART-96", "DUMP-4"])
    assert "trash" in str(caught.value)

    # …and the count that trash DOES bill on is untouched by any of this.
    assert len(_records("trash")) == 7


def test_a6__summing_a_code_that_is_not_this_services_size_is_refused():
    """A solar total may not be assembled out of battery codes. Both sum in
    `kW`, so the arithmetic would SUCCEED and produce a plausible wrong number —
    which is the failure mode worth a test.
    """
    with pytest.raises(KeyError):
        ssc.total_capacity("solar", ["BAT-10"])


def test_a6__the_fixture_still_mirrors_the_law():
    """BR-TEN-171's mirror guard — and it now reads the FIXTURE, which the
    version it replaces never did (`DEF-3085`).

    The fixture is a flat delivery list and stays exactly that — this CR changes
    the CONTENT it carries and not its SHAPE, so `_seed_reference_data` needs no
    change to deliver it.

    ⚠ **THE OLD VERSION OF THIS CASE COUNTED THE LAW AND CALLED IT THE MIRROR.**
    It asserted `len(ssc.seed_entries()) == 53` and opened
    `apps/tenancy/fixtures/lookup_defaults.json` nowhere at all, so the one
    thing its name promises — that the two agree — was never checked, and the
    only thing it could ever fail on was a lawful row somebody appended. Both
    halves are fixed here: the count is DERIVED and the file is actually opened.
    """
    law = ssc.seed_entries()

    codes = [row["code"] for row in law]
    assert len(codes) == len(set(codes)), "a code is seeded twice"

    fixture = (
        Path(__file__).resolve().parents[1] / "apps" / "tenancy" / "fixtures" / "lookup_defaults.json"
    )
    delivered = json.loads(fixture.read_text(encoding="utf-8"))["service_size_classes"]

    # The MIRROR, row for row and in order — not a count. A fixture that has
    # gained, lost or renamed a row fails here and NAMES the row, which a length
    # comparison could never do.
    assert delivered == law, (
        "apps/tenancy/fixtures/lookup_defaults.json no longer mirrors "
        "service_size_classes.seed_entries(). The fixture is REGENERATED from the "
        "law (BR-TEN-077) — regenerate it and bump the serial rather than editing "
        "either side by hand."
    )


def test_a6__this_crs_own_arithmetic_is_still_true():
    """`CR-062`'s change, stated as the subtraction and addition it actually is.

    Eight codes leave and twenty-one arrive. This is what
    `RATIFIED_TOTAL_AFTER_CR062 = 53` was really trying to say, and saying it
    this way survives an eleventh service, a twelfth, and a tenant-authored size
    list — none of which is this CR, and none of which should be able to make
    this file red.
    """
    seeded = {row["code"] for row in ssc.seed_entries()}

    assert len(WITHDRAWN_CODES) == CR062_WITHDRAWN
    for code in WITHDRAWN_CODES:
        assert code not in seeded, f"{code} was withdrawn by CR-062 and is back"

    arrived = (
        [code for code, _name, _capacity in SOLAR_EXPECTED]
        + [code for code, _name, _capacity in BATTERY_EXPECTED]
        # `SW-FLAT` arrived later (PO 2026-10-03), not with CR-062's twenty-one.
        + [code for code, _name, _capacity in STORM_WATER_EXPECTED if code != "SW-FLAT"]
    )
    assert len(arrived) == CR062_ADDED
    for code in arrived:
        assert code in seeded, f"{code} is one of CR-062's twenty-one and is missing"


def test_a6__the_ruled_empty_and_the_never_ruled_are_still_different_facts():
    """The distinction this module exists to protect, re-asserted because this
    CR moves a service ACROSS it — battery leaves *"ruled to have none"* for a
    real list, and the two remaining answers must not blur behind it.

    Sewer is still `()` — RULED to have none, because it is a share of the water
    usage charge and reads no register. Thermal steam still RAISES — nobody has
    ever put its boundaries to the PO. One is a finished decision; the other is
    money nobody has priced.
    """
    assert ssc.size_classes_for_service("sewer") == ()
    with pytest.raises(ssc.SizeClassNotRuled) as caught:
        ssc.steam_size_classes()
    assert "OQ-560" in str(caught.value)


# ── The three import-time invariants, each proved to BITE ──────────────────
#
# Hard-won law 7: a new guard is proved RED on the edit it was written for
# before it is trusted green. These five cases are that proof made PERMANENT,
# because a guard nobody re-proves is a guard nobody can trust later — and
# `_validate_ratified_rows` runs at IMPORT, where a silent failure would not
# look like a test failure at all, it would look like the module working.
#
# Each case is the realistic bad edit, not an arbitrary one: a lane adding a
# number and forgetting the unit, a lane "completing" trash by giving a cart
# its gallons, a lane copying a row between services.


def _validate_with(service, rows):
    """Run the real import-time validator over one substituted service."""
    original = dict(ssc.RATIFIED_SERVICE_SIZE_CLASSES)
    try:
        ssc.RATIFIED_SERVICE_SIZE_CLASSES[service] = rows
        ssc._validate_ratified_rows()
    finally:
        ssc.RATIFIED_SERVICE_SIZE_CLASSES.clear()
        ssc.RATIFIED_SERVICE_SIZE_CLASSES.update(original)


@pytest.mark.parametrize(
    ("label", "row"),
    [
        ("a number with no unit", ssc.SizeClass("SOL-P1", "Solar panel 1 kW", Decimal(1), None)),
        ("a unit with no number", ssc.SizeClass("SOL-P1", "Solar panel 1 kW", None, "kW")),
    ],
)
def test_guard_bites__a_quantity_never_travels_without_its_unit(label, row):
    """CLAUDE.md hard rule 3, enforced in BOTH directions.

    The second direction is the one a reader would not think to check, and it
    is the more dangerous of the two: a unit with no number reads as a capacity
    row at a glance and sums as nothing.
    """
    with pytest.raises(ValueError) as caught:
        _validate_with("solar", (row,))
    assert "one half of a quantity" in str(caught.value), label


def test_guard_bites__a_capacity_must_be_positive():
    """A zero capacity is not a small one — it is a row that adds nothing to
    every total it appears in, silently. `None` is how this module says *"no
    capacity"*; `0` would be a claim that the equipment is there and free.
    """
    with pytest.raises(ValueError) as caught:
        _validate_with("solar", (ssc.SizeClass("SOL-P1", "Solar panel 1 kW", Decimal(0), "kW"),))
    assert "positive quantity" in str(caught.value)


def test_guard_bites__a_service_may_not_mix_bands_with_capacities():
    """**The realistic bad edit this one exists for: somebody "finishes" trash
    by giving a 96-gallon cart its 96 gallons.**

    It looks like an improvement and it is not: three of trash's rows are carts
    in gallons and four are dumpsters in cubic yards, so the service would then
    hold two rows that sum and five that cannot, with nothing on a bill saying
    which a given customer got.
    """
    mixed = ssc.size_class_records_for_service("trash")[:6] + (
        ssc.SizeClass("CART-96", "Trash 96-gallon cart", Decimal(96), "gal"),
    )
    with pytest.raises(ValueError) as caught:
        _validate_with("trash", mixed)
    assert "mixes bands" in str(caught.value)


def test_guard_bites__a_service_sums_in_exactly_one_unit():
    """You cannot add kW to Mbps. Without this, a copied row between two
    capacity services produces a total that is a number with no meaning, and
    nothing downstream could detect it — the sum would simply be wrong.
    """
    wrong_unit = ssc.size_class_records_for_service("solar")[:9] + (
        ssc.SizeClass("SOL-P10", "Solar panel 10 kW", Decimal(10), "Mbps"),
    )
    with pytest.raises(ValueError) as caught:
        _validate_with("solar", wrong_unit)
    assert "more than one unit" in str(caught.value)


def test_the_real_ratified_data_passes_its_own_validator():
    """The other half of every case above: the guards bite on a bad edit AND
    the shipped data is clean. A guard that bites on everything is no guard.
    """
    ssc._validate_ratified_rows()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-062 group A (A1–A6) @556658f5
# generated: 2026-09-02 by the CR-062 group A lane
# gates: the 26 cases above were shown RED on the pre-CR-062 code (three named
#        AttributeErrors: size_class_records_for_service / total_capacity /
#        NotACapacityService); the five guard-bites cases were each shown RED on
#        the realistic bad edit they name, and the shipped data passes. Golden
#        unmoved — 33 document self-consistency checks, and 14 of the 61 signed
#        GTs engine-verified. Proved on SQLite and on real PostgreSQL 16.13.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
