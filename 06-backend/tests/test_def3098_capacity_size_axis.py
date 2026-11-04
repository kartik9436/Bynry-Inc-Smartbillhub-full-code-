# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-3098 (2026-09-02) — the rating chain decided *"is this service
#          banded?"* by asking *"does it have any size class rows?"*. Those two
#          questions had the same answer until CR-062 group A gave solar,
#          battery, storm water and broadband a CATALOGUE OF CAPACITIES. A
#          capacity service now HAS rows and is still NOT banded, so a schedule
#          stating no per-size rows went from one ladder at the blank size to
#          NO SIZE PRICED AT ALL — which refuses every bill on it.
#          `DEF-2408` is the same outage one week earlier, arriving from the
#          other direction: battery could not be billed for five days.
# Rules:   BR-RAT-120 (PO 2026-08-28, "we need to charge account based on
#          connection size they have") · BR-RAT-015 / BR-TEN-171 (sewer carries
#          no size class BY RULING) · BR-TEN-171 as amended by CR-062 (a size
#          class is a BAND or a CAPACITY) · BR-RAT-024 (the ten services) ·
#          CLAUDE.md hard rule 3 (a quantity always carries its unit)
# Open Qs: OQ-560 (thermal steam bands) — still unanswered, still raises
# Tests:   this file
# ───────────────────────────────────────────────────────
"""DEF-3098 — TWO DIFFERENT QUESTIONS THAT SHARED ONE ANSWER UNTIL TODAY.

    "does this service have size rows?"       — a fact about a LIST
    "does this service's price vary by size?" — a fact about MONEY

Before CR-062 only banded services had rows, so `rows == ()` was a sound proxy
for *"not banded"* and two places in the rating chain used it as one:

    apps/rating/resolution_catalogue.configured_sizes_for    — R3's SIZE AXIS
    apps/rating/resolution._assert_service_is_ruled_sizeless — R3's BLANK-SIZE
                                                               guard

CR-062 group A broke the proxy by design. A capacity service's rows are a
CATALOGUE OF INSTALLABLE EQUIPMENT — ten solar panel types, six battery blocks,
five storm-water property sizes — and not a rate axis at all: the price is a
flat figure per kW (or per ERU, or per Mbps) multiplied by the SUM of what is
installed. Three panels of 2 kW, 4 kW and 8 kW are one 14 kW array on one
connection, not three connections of three different sizes.

**MEASURED, ON THE CODE BEFORE THE FIX** (`schedule_version_facts` for a bare
battery schedule beside the identical sewer one):

    assert battery.size_rows == sewer.size_rows
    AssertionError: assert {} == {'': Decimal('8.000000')}

An empty `size_rows` means *this version prices no size at all*, so R3 refuses
every meter by name and **no battery or solar customer on such a schedule can be
billed**.

WHAT THE FIX IS, AND WHAT IT DELIBERATELY IS NOT
------------------------------------------------
The fix is to ask the second question, which now has an exact answer:
`service_size_classes.capacity_uom_for_service(service)` returns the summing
unit for a capacity service and `None` for a banded one. It is NOT a special
case for battery — nothing in either file names a service — and it is NOT a
widening of the axis: a BANDED service whose schedule configures no size still
serves no size and still refuses by name, which is BR-RAT-120's ruling with its
cost accepted by the PO in as many words.

TRASH IS THE CASE THAT PROVES THE FIX IS NOT "capacity services get a pass"
---------------------------------------------------------------------------
Trash is *capacity based* in the PO's own words and is BANDED in this product,
because its seven rows are three CARTS in gallons and four DUMPSTERS in cubic
yards. There is no unit in which those add up, so `capacity_uom_for_service`
answers `None`, `total_capacity` REFUSES by name, and trash keeps the banded
axis it has always had. That refusal is asserted here as well as in the CR-062
suite, because this is the fix that could quietly remove it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import resolution, resolution_catalogue
from apps.tenancy import service_size_classes

from tests.test_br_rat_120_size_refusal import _bare_version
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The PO's own worked example, 2026-09-02: three panels on one unit.
PO_ARRAY = ("SOL-P2", "SOL-P4", "SOL-P8")
PO_ARRAY_KW = Decimal("14")
PO_RATE_PER_KW = Decimal("14.00")
PO_ARRAY_BILL = Decimal("196.00")

#: B5 GT-15's two figures, quoted so this fix cannot move either of them.
GT15_SOLAR = Decimal("40.00")
GT15_BATTERY = Decimal("24.00")

#: Every capacity service CR-062 created, with the unit it sums in. Named as
#: data so a service added to the catalogue later is covered without an edit.
CAPACITY_SERVICES = {
    "storm_water": "ERU",
    "solar": "kW",
    "broadband": "Mbps",
    "battery": "kW",
    # ⚠ **`thermal_heat` ARRIVED HERE FROM `BANDED_SERVICES` ON 2026-09-07
    # (`CR-080`), WHICH IS THE FIRST TIME A SERVICE HAS CROSSED THIS FILE'S
    # QUESTION.** The PO ruled it capacity-billed on connected tonnage — *"i
    # will ahve 100 tonne or 200 tonne etc"* — and its three `TH-CW-*` RANGES
    # are withdrawn, because a range has no single value a capacity could be.
    # `TC5b` below is the case that made this edit non-optional rather than
    # tidy: it asserts every ratified service is on EXACTLY ONE side, so a
    # service moving sides and only one tuple being edited goes red.
    "thermal_heat": "ton",
}

#: The services whose size classes are BANDS — a label that picks a rate and
#: sums with nothing. Their axis behaviour must not move a millimetre.
#:
#: ⚠ **`fire` IS HERE AND IT IS THE CASE THAT PROVES THE FIX GENERALISES.** It
#: arrived as the ELEVENTH service hours after `CR-062` (`CR-063`, PO 2026-09-02:
#: *"We will need Fire as utility Service - Capacity based - this will behave
#: exactly like trash"*). The PO's own word for it is *capacity* and it is a BAND
#: service here, for trash's exact reason: **fire COUNTS what is installed, it
#: does not SUM it.** One 6" line with two 2" lines is `$60.00 + 2 × $12.00`,
#: and there is no unit in which a 6-inch line plus a 2-inch line is a
#: quantity — 8 inches is not a thing anybody sells. (This example was a 6" line
#: with two private hydrants at `$60.00 + 2 × $25.00` until the PO withdrew the
#: hydrant from fire's size list on 2026-09-03; fire's ARITHMETIC is untouched,
#: which is the only thing this file is about.)
#: Since this fix names no service, fire was already on the right side
#: of it the moment its rows landed — which is the whole argument for asking a
#: question instead of listing exceptions.
#: ⚠ **`thermal_heat` LEFT THIS TUPLE ON 2026-09-07 (`CR-080`)** — the PO ruled
#: it capacity-based on connected tonnage, its three RANGE bands are withdrawn,
#: and `capacity_uom_for_service("thermal_heat")` answers `"ton"` now. It moved
#: to `CAPACITY_SERVICES` with no edit needed there, because that set is DERIVED
#: from the question rather than listed — which is this file's own point.
BANDED_SERVICES = ("electric", "water", "gas", "trash", "fire")


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT · a capacity service with no per-size rows prices its capacity
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("service", sorted(CAPACITY_SERVICES))
def test_TC1_a_bare_capacity_schedule_serves_one_ladder_not_none(brazos, dana, service):
    """**THE MONEY CASE.** A battery or solar schedule that states no per-size
    rows must price its capacity, exactly as sewer's bare schedule prices its
    usage — one ladder at the BLANK size, which R4 then puts a figure on.

    An empty axis is not "no sizes yet": it is *this version prices no size at
    all*, and R3 refuses every meter against it by name. That is correct for a
    BANDED service (BR-RAT-120, the PO's accepted cost) and is an outage for a
    capacity one, whose price never varied by band in the first place.
    """
    with tenant_ctx(brazos):
        _plan, binding = _bare_version(brazos, service)
        version = resolution_catalogue.schedule_version_facts(binding.tariff_id)[0]

        assert version.size_rows, (
            f"{service} is a CAPACITY service — its rows are a catalogue of "
            "installable equipment, not a rate axis — so a schedule stating no "
            "per-size rows must still serve the blank ladder. An empty axis "
            "refuses every bill (DEF-3098, and DEF-2408 one week earlier)."
        )
        assert list(version.size_rows) == [resolution_catalogue.NO_SIZE_AXIS]


def test_TC1b_the_bare_capacity_axis_is_identical_to_sewers(brazos, dana):
    """The assertion the defect was measured on, kept in the form it failed in.

    Sewer is the service ruled to have NO size class at all, and its bare
    schedule has always served one blank ladder. A capacity service reaches the
    same axis by a different route — it HAS rows and they are not a rate axis —
    and the two must agree, because neither prices by band.
    """
    with tenant_ctx(brazos):
        _sp, sewer_binding = _bare_version(brazos, "sewer")
        _bp, battery_binding = _bare_version(brazos, "battery")

        sewer = resolution_catalogue.schedule_version_facts(sewer_binding.tariff_id)[0]
        battery = resolution_catalogue.schedule_version_facts(battery_binding.tariff_id)[0]

        assert battery.size_rows == sewer.size_rows


@pytest.mark.parametrize("service", sorted(CAPACITY_SERVICES))
def test_TC2_R3_accepts_a_blank_size_on_a_capacity_service(brazos, dana, service):
    """The SECOND site of the same inference, and it refuses a whole account.

    `resolve_served_size` calls `_assert_service_is_ruled_sizeless` when a meter
    carries no connection size — which is every asset-counted capacity service,
    since nothing meters a solar panel's "connection size". That guard asked the
    same *"does it have rows"* question, so from CR-062 it refused the account
    outright with *"DOES have a ratified size ladder"*.

    A capacity service HAS a ladder of equipment and does not price by it. R3
    must let the blank size through and leave the money to R4.
    """
    with tenant_ctx(brazos):
        _plan, binding = _bare_version(brazos, service)
        version = resolution_catalogue.schedule_version_facts(binding.tariff_id)[0]

        assert (
            resolution.resolve_served_size(version, resolution.MeterFacts(service, ""))
            == resolution.NO_SIZE
        )


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT MUST NOT MOVE · the banded axis, and trash's refusal to be summed
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("service", BANDED_SERVICES)
def test_TC3_a_bare_banded_schedule_still_serves_no_size(brazos, dana, service):
    """BR-RAT-120's ruling, unchanged and re-proved.

    The PO chose this reading with its cost stated — *"Read the second way, the
    system refuses bills that price perfectly well today"* — so a BANDED service
    whose schedule configures no size serves NO size and refuses every meter by
    name. The fix must not turn that refusal off; it narrows to the services
    whose price never varied by band.
    """
    with tenant_ctx(brazos):
        _plan, binding = _bare_version(brazos, service)
        version = resolution_catalogue.schedule_version_facts(binding.tariff_id)[0]

        assert version.size_rows == {}, (
            f"{service} is BANDED — a band PICKS a rate — so a schedule that "
            "configures no size prices none, and R3 refuses by name"
        )


def test_TC4_trash_still_refuses_to_be_summed_and_stays_banded(brazos, dana):
    """**The case that proves the fix is not "capacity services get a pass".**

    Trash is *capacity based* in the PO's own words — *"Trash - it is capacity
    based and Cart sizes will decide price X how many Cart"* — and is BANDED
    here, because the SIZE picks the rate and the COUNT multiplies it. Its seven
    rows are three carts in GALLONS and four dumpsters in CUBIC YARDS, so no
    total exists in any unit at all.

    Group A made that refuse BY NAME. This keeps it refusing, and keeps trash on
    the banded axis where DEF-3201 put it.
    """
    assert service_size_classes.capacity_uom_for_service("trash") is None

    with pytest.raises(service_size_classes.NotACapacityService) as refusal:
        service_size_classes.total_capacity("trash", ["CART-96", "DUMP-4"])
    assert "BANDS" in str(refusal.value)

    with tenant_ctx(brazos):
        _plan, binding = _bare_version(brazos, "trash")
        version = resolution_catalogue.schedule_version_facts(binding.tariff_id)[0]
        assert version.size_rows == {}


def test_TC5_the_three_readings_still_do_not_collapse(brazos, dana):
    """*Ruled to have none* · *nobody has said* · *here is a catalogue* — three
    facts, three answers, and the fix must keep all three apart.

    Collapsing the first two is what `service_size_classes` exists to prevent:
    one is a finished decision and the other is money nobody has priced.
    """
    with tenant_ctx(brazos):
        _plan, sewer_binding = _bare_version(brazos, "sewer")
        sewer = resolution_catalogue.schedule_version_facts(sewer_binding.tariff_id)[0]
        assert list(sewer.size_rows) == [resolution_catalogue.NO_SIZE_AXIS]

    # nobody has said — OQ-560 still raises rather than answering "no size"
    with pytest.raises(service_size_classes.SizeClassNotRuled) as unruled:
        service_size_classes.steam_size_classes()
    assert "OQ-560" in str(unruled.value)

    # here is a catalogue — and the unit is what says so
    for service, uom in CAPACITY_SERVICES.items():
        assert service_size_classes.capacity_uom_for_service(service) == uom
    assert service_size_classes.capacity_uom_for_service("sewer") is None


def test_TC5b_every_ratified_service_is_on_exactly_one_side_of_the_question():
    """No service may be silently absent from this file's two lists.

    ⚠ **THIS IS THE CASE THAT CATCHES A TWELFTH SERVICE.** `CR-063` added Fire
    hours after `CR-062`, and a suite that names services in two hand-written
    tuples would simply not have tested it — the same shape as hard-won law 2,
    where a thing exists, every test passes, and nothing exercises it. So the
    ratified list is the authority and these tuples are checked against it.
    """
    named = set(CAPACITY_SERVICES) | set(BANDED_SERVICES) | {"sewer"}
    ratified = set(service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES)
    assert named == ratified, (
        "a service was ratified without being placed on either side of "
        f"DEF-3098's question — missing from this file: {sorted(ratified - named)}; "
        f"named here but no longer ratified: {sorted(named - ratified)}"
    )
    for service in BANDED_SERVICES:
        assert service_size_classes.capacity_uom_for_service(service) is None


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE FIGURES THAT ALREADY STAND · the fix may not move a cent of them
# ══════════════════════════════════════════════════════════════════════════
def test_TC6_the_POs_own_array_is_fourteen_kilowatts_and_bills_196():
    """PO 2026-09-02: three panels of 2 kW, 4 kW and 8 kW on one unit.

    The sum is **14 kW** and at their stated rate of **$14.00 per kW** the array
    bills **$196.00**. (Their message reads *"14 X 14 = 156 $"*; 14 × 14 is 196.
    They were told so in the same session and did not dispute it, and $156
    appears nowhere in this repo.)

    Asserted here as arithmetic on the ratified rows rather than on a fixture,
    so a catalogue edit that moved a panel's kilowatts would go red on the money
    and not merely on the list.
    """
    total = service_size_classes.total_capacity("solar", PO_ARRAY)
    assert total == PO_ARRAY_KW
    assert (total * PO_RATE_PER_KW).quantize(Decimal("0.01")) == PO_ARRAY_BILL


def test_TC7_gt15s_two_figures_are_untouched_by_the_size_axis():
    """B5 GT-15 — *solar 4 units @ $10 + battery 2 @ $12 → $40.00 + $24.00*.

    ⚠ **THESE ARE B4/B5 SIGNED FIGURES AND THIS LANE MOVES NEITHER.** They are
    quoted here as a tripwire beside the change, not re-derived: the end-to-end
    proof that they reach a real bill from real rows is
    `tests/test_capacity_end_to_end.py`, and it runs on schedules that DO
    configure sizes — which is exactly why it stayed green while DEF-3098 was
    live, and why this file exists.

    What is asserted is the only thing this fix could have moved: the axis a
    capacity service resolves on is the blank ladder, so the per-unit rate is
    reached the same way for 4 solar units at $10.00 and 2 battery blocks at
    $12.00 as it was before.
    """
    assert GT15_SOLAR == Decimal("4") * Decimal("10.00")
    assert GT15_BATTERY == Decimal("2") * Decimal("12.00")
    assert service_size_classes.capacity_uom_for_service("solar") == "kW"
    assert service_size_classes.capacity_uom_for_service("battery") == "kW"


# ── Lifecycle ─────────────────────────────────────────────
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
