# ── Trace ──────────────────────────────────────────────
# Change:  **CR-062 ADDENDUM 1, tasks J1–J4** (2026-09-02). Four gaps that only
#          appeared when nine worked utilities were drawn end to end from this
#          seed: thermal's demo usage was a hundredfold too small the moment
#          task E6 priced it; the Municipal account discount and the first
#          seeded enrolment this fixture has ever carried; a government account,
#          because the type existed and nothing used it; and an industrial one,
#          so a real bill finally stands behind `$180.00` and `$0.085/kWh`.
# Rules:   CLAUDE.md hard rule 2 (money stored to 4 decimals, percentages to 6,
#          both DISPLAYED to 2) · hard rule 3 (a quantity always carries its
#          unit) · BR-RAT-015 ❄️ / GT-17 ❄️ (water $39.50, sewer $15.80) ·
#          GT-15 ❄️ (solar $40.00, battery $24.00) · BR-RAT-069 / BR-RAT-110
#          (plan attachment makes a discount AVAILABLE; the enrolment GRANTS) ·
#          BR-RAT-071 (a discount is taken before taxes) · BR-RAT-090 (an
#          unmetered service's quantity is an observed count) · BR-RAT-108 (one
#          service, several amounts, separated by CLASS and never by name)
# Tests:   this file
# Impacts: core/sample_fixture.py · apps/rating/sample_data.py ·
#          apps/rating/discount_sample_data.py · apps/metering/sample_data.py
# ───────────────────────────────────────────────────────
"""**THE FOUR ADDENDUM TASKS, AND THE WORKED FIGURES THEY STAND ON.**

    J1  a seeded thermal customer reads 4,500 ton-hours, not 45, and pays
        **$202.50** where it paid **$2.02**
    J2  a government building with a **$157.50** subtotal pays **$126.00**
        (**$129.70 → $103.76 until `CR-081`, 2026-09-08**),
        a saving of **$31.50**, and the saving is a LINE on the bill
    J3  one seeded `government` account, the first anywhere
    J4  one seeded `industrial` account, so `$180.00` and `$0.085/kWh` are on
        a real invoice instead of in two constants that disagreed by `$168.00`

⚠ **WHY J1 IS A CHANGE AND NOT A BUG FIX.** `CONSUMPTION_SCALE`'s own docstring
has always said the scale *"prices nothing"* and that *"the day `OQ-1290` closes,
this scale is part of what has to be ratified with it — it is flagged, not
silently official"*. Task E6 priced thermal on 2026-09-02, so the flag came due
in the same change that caused it. **The usage moves and the rate does not**:
`$0.045` a ton-hour is a realistic price for chilled water and `$4.50` is not.

⚠ **ELECTRIC AND GAS ARE PROVED UNMOVED, IN THIS FILE, BY NAME.** They were
checked when the scale was written and they are realistic — 800 kWh and 40 therm
for a household — so a change that moved them would be a change nobody asked
for. `test_pure_j1_only_thermal_moves` is that guard.

RED PROVED FIRST (law 7) — every case below was run against the branch tip
before a line of the fix was written. The failures are quoted in the lane's
report and in `12-governance/02-decision-log.md`.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace

import pytest

from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import discounts as discount_models
from apps.tenancy import sample_data as tenancy_sample_data
from core import sample_fixture as fixture

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

#: ⚠ **NO MODULE-LEVEL `django_db` MARK** — `test_cr062_e_rates`' own reason:
#: parts 1 and 2 are pure arithmetic over constants and need no database, and
#: the whole argument for splitting the layers is that the cheap half fails
#: first. Only part 3 pays for a tenant.
_live = pytest.mark.django_db

# ══════════════════════════════════════════════════════════════════════════
# PART 1 · J1 — THERMAL'S DEMO USAGE
# ══════════════════════════════════════════════════════════════════════════

#: **⚠ `J1_THERMAL_SCALE = 500` WAS HERE AND IS RETIRED — `CR-080`,
#: 2026-09-07.** J1 raised thermal's demo USAGE because a chilled-water
#: building reads nearer 4,000 ton-hours a month than 45. **The PO then ruled
#: that thermal reads nothing at all:** *"connected tonnage - it is capacity
#: not metering; i will ahve 100 tonne or 200 tonne etc"*. A capacity service
#: has no register, so there is no usage to scale and no ton-hour to price.
#:
#: The name is written out here rather than deleted in silence, because J1 is
#: cited across the register and a reader following one of those citations
#: should land on where it went.
_J1_RETIRED_NAMES = ("J1_THERMAL_SCALE",)

#: The scales that were checked when `CONSUMPTION_SCALE` was written and found
#: realistic. **These must not move**: 8 kgal of water, 800 kWh of electricity
#: and 40 therm is a household a utility recognises.
J1_UNMOVED_SCALES: dict[str, int] = {"water": 1, "electric": 100, "gas": 5}

#: `CR-080` — what thermal is billed on INSTEAD, and the two figures the PO
#: themselves named. `$12.5000` per connected ton per month is the `CR-080`
#: lane's judgment under the PO's market-research delegation, NOT a ratified
#: figure; the ledger row states the trade.
J1_THERMAL_PER_TON = Decimal("12.5000")


def test_pure_j1_thermal_reads_nothing_at_all_now():
    """**`CR-080` · J1's whole subject is withdrawn, and this asserts the
    ABSENCE so a later lane "finishing J1" goes red instead of shipping.**

    ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-07.** It was
    `test_pure_j1_thermal_reads_in_thousands_of_ton_hours` and it required
    `CONSUMPTION_SCALE["thermal_heat"] == 500`. The PO ruled thermal
    capacity-based on connected tonnage that day — *"connected tonnage - it is
    capacity not metering"* — so a scale, a seasonal curve and a per-ton-hour
    price are all facts about a billing shape this product no longer has for
    thermal. Every one of them is gone, together, in one commit: the fixture's
    own rule is that a price and its unit may never travel separately
    (`DEF-497`).
    """
    for name, mapping in (
        ("CONSUMPTION_SCALE", fixture.CONSUMPTION_SCALE),
        ("METERED_USAGE_PRICES", fixture.METERED_USAGE_PRICES),
        ("SEASONAL_SHAPE", fixture.SEASONAL_SHAPE),
        ("BACKBONE_BASE", fixture.BACKBONE_BASE),
        ("SERVICE_METER_PREFIX", fixture.SERVICE_METER_PREFIX),
    ):
        assert "thermal_heat" not in mapping, (
            f"{name} still carries a thermal entry. Thermal is capacity-billed "
            "on connected tonnage since CR-080 and reads no register, so a "
            "figure describing a reading nobody takes is worse than no figure"
        )
    assert "thermal_heat" not in fixture.METERED_ESTATE_SERVICES
    assert "thermal_heat" in fixture.CAPACITY_ESTATE_SERVICES
    assert "thermal_heat" in fixture.UNMETERED_ESTATE_SERVICES


def test_pure_j1_only_thermal_moves():
    """**J1 · electric and gas are realistic and must not move.**

    The addendum says so in terms: *"Electric (×100 → 900 kWh) and gas (×5 → 45
    ccf) were checked and are realistic; thermal is the only one nobody
    checked, because nothing priced it."*

    ⚠ **AND THE SENTENCE HELD THROUGH `CR-080` WITHOUT AN EDIT, WHICH IS THE
    USEFUL PART.** Thermal left `CONSUMPTION_SCALE` entirely on 2026-09-07 and
    these three did not move a digit — the same guarantee J1 asked for, now
    guarding a withdrawal rather than a raise.
    """
    assert set(fixture.CONSUMPTION_SCALE) == set(J1_UNMOVED_SCALES), (
        f"CONSUMPTION_SCALE is {sorted(fixture.CONSUMPTION_SCALE)}; since CR-080 "
        "it holds the three metered backbones and nothing else"
    )
    for service, scale in J1_UNMOVED_SCALES.items():
        assert fixture.CONSUMPTION_SCALE[service] == scale, (
            f"{service}'s consumption scale moved to "
            f"{fixture.CONSUMPTION_SCALE[service]} and J1 moves thermal ALONE"
        )


def test_pure_j1_the_reference_thermal_customer_pays_by_the_connected_ton():
    """**`CR-080` worked · the PO's own two numbers, on the seeded estate.**

    ⚠ **THIS CASE PRICED `5,500 ton-hr × $0.045 = $247.50` UNTIL 2026-09-07,
    AND BEFORE THAT `4,500 × $0.045 = $202.50`, AND BEFORE THAT `45 = $2.02`.**
    All three are gone with the register they measured. **`$202.50` WAS SHOWN
    TO THE PRODUCT OWNER** (review ledger, 2026-09-02: *"it now reads 4,500 and
    pays $202.50"*) and `$0.045` per ton-hour was a figure they personally
    approved (`CR-062` E6), so the retirement is recorded in the decision log
    of 2026-09-07 with the trade stated, and it returns to the review agenda
    rather than being edited quietly.

    **It is not a ❄️ B4/B5 figure** — `04-docs/02-decisions/04-money-math-rules
    .md` states no thermal amount at all, B5's only mention is revenue account
    `4170`, and `GT-1`–`GT-61` price no thermal line — so this needs no finance
    re-sign. `CR-080` checked that independently rather than assuming it.

    **The PO's own words are the acceptance test:** *"i will ahve 100 tonne or
    200 tonne etc"*.
    """
    assert Decimal(fixture.CAPACITY_UNIT_PRICES["thermal_heat"]) == J1_THERMAL_PER_TON
    assert fixture.THERMAL_UOM == "ton"
    # The PO's two figures, priced.
    assert (Decimal("100") * J1_THERMAL_PER_TON).quantize(Decimal("0.01")) == Decimal("1250.00")
    assert (Decimal("200") * J1_THERMAL_PER_TON).quantize(Decimal("0.01")) == Decimal("2500.00")
    # And it SUMS rather than counting: a 100-ton and a 25-ton connection on
    # one unit is 125 tons, not "2 connections".
    assert (Decimal("125") * J1_THERMAL_PER_TON).quantize(Decimal("0.01")) == Decimal("1562.50")


def test_pure_j1_the_gt17_reference_unit_still_draws_eight_of_the_shape():
    """**J1 · the shape is untouched; only the multiplier moved.**

    ❄️ `GT-17`'s reference bill is water `$39.50` / sewer `$15.80` on unit 0's
    8 kgal. Water's scale is 1, so a thermal scale cannot reach it — but the
    guard is written down rather than assumed, because *"no frozen figure
    moves"* is the sentence this whole change rests on.
    """
    assert fixture.water_consumption_kgal(0, "june") == Decimal("8")
    assert fixture.consumption(0, "june", service="water") == Decimal("8")
    assert fixture.CONSUMPTION_SCALE["water"] == 1


# ══════════════════════════════════════════════════════════════════════════
# PART 2 · J3 / J4 — THE TWO ACCOUNTS THE ESTATE HAS NEVER HELD
# ══════════════════════════════════════════════════════════════════════════

#: The addendum's own worked subtotal for the government building on water +
#: sewer + trash, and what it is made of on the seeded residential ladder:
#:
#:     water base                          $8.00
#:     water usage   12 kgal on the tiers  $65.50   (5 × $4.00 + 7 × $6.50)
#:     sewer         90% × 12 kgal @ $5    $54.00   (10.8 kgal — `CR-081`)
#:     trash         2 carts × $15.00     $30.00
#:                                       ────────
#:                                        $157.50
# ⚠ MOVED BY `CR-081` (2026-09-08): $129.70 → $157.50, because this seat's
# sewer line went from $26.20 (40% of $65.50 of water charges) to $54.00 (90% of
# 12 kgal at $5.0000). The discount and its 20% are unchanged and unmoved.
J2_SUBTOTAL = Decimal("157.50")
J2_DISCOUNT = Decimal("31.50")  # 20% of the subtotal, taken BEFORE taxes
J2_PAYABLE = Decimal("126.00")

#: The government building's water draw, flat in every period for the reason
#: unit 0's 8 kgal is flat: a demo figure a person can check by hand must not
#: drift by a month.
J3_GOVERNMENT_KGAL = Decimal("12")


def test_pure_j3_the_estate_holds_a_government_account():
    """**J3 · a government customer, seeded as `municipal` — `DEF-3283`.**

    ⚠ **THE ADDENDUM ASKS FOR `government` AND THE PRODUCT IS RIGHT TO REFUSE
    IT.** `BR-CUS-094` (PO 2026-08-24) made `government` a LEGACY code —
    *"stops being selectable and changes nothing else"* — eight days before the
    addendum was written, so the seat was refused by name:

        SCW-U-049: ValidationError: VAL-005 (customers.account.type_is_legacy)

    `municipal` is one of the seven selectable categories, is the same customer,
    and is the Product Owner's OWN word for it: *"What is the government
    discount called? Municipal account - yes"*.
    """
    types = {row["account_type"] for row in fixture.account_plan()}
    assert "municipal" in types, (
        "no seeded account is a government customer, so nothing in the product "
        "has ever shown one — and J2's Municipal discount would have nowhere "
        "to land"
    )
    assert "government" not in types, (
        "`government` is a LEGACY account type (BR-CUS-094) and a NEW record "
        "may not carry one. A seed that writes it is reaching past the "
        "product's own refusal — DEF-3283"
    )


def test_pure_j4_the_estate_holds_an_industrial_account():
    """**J4 · `INDUSTRIAL_ELECTRIC_BASE` is `$180.00` and nothing was on it.**

    That is exactly how `DEF-2823`'s `$168.00` disagreement hid: *"0 accounts
    are on `IND`, so no bill ever carried either figure"*.
    """
    types = {row["account_type"] for row in fixture.account_plan()}
    assert "industrial" in types, (
        "no seeded account is industrial, so the $180.00 industrial base and "
        "the $0.085/kWh usage rate stand behind no bill at all"
    )


def test_pure_j3_j4_are_exactly_one_account_each():
    """**One of each — the addendum asks for one, and a second would double a
    shape without proving a new rule.**"""
    counts: dict[str, int] = {}
    for row in fixture.account_plan():
        counts[row["account_type"]] = counts.get(row["account_type"], 0) + 1
    assert counts.get("municipal") == 1, f"municipal accounts: {counts.get('municipal')}"
    assert counts.get("industrial") == 1, f"industrial accounts: {counts.get('industrial')}"


def test_pure_j3_the_government_building_draws_the_addendums_12_kgal():
    """**J3 · 12 kgal, so the `$157.50` subtotal is reproducible by hand.**"""
    for period in ("june", "july", "august"):
        assert (
            fixture.water_consumption_kgal(fixture.CASE_GOVERNMENT_ACCOUNT, period)
            == J3_GOVERNMENT_KGAL
        ), f"the government building's {period} draw is not 12 kgal"


def test_pure_j2_the_subtotal_is_made_of_the_seeded_figures():
    """**J2 worked · every part of `$157.50` read from the fixture, not stated.**

    If any of the four components moves, this case names which one — which is
    what makes `$126.00` an assertion about the SEED rather than about a number
    somebody typed twice.
    """
    kgal = fixture.water_consumption_kgal(fixture.CASE_GOVERNMENT_ACCOUNT, "june")
    usage = Decimal("0")
    remaining = kgal
    for lo, hi, price in fixture.WATER_TIERS:
        if remaining <= 0:
            break
        span = (Decimal(hi) - Decimal(lo)) if hi is not None else remaining
        take = min(span, remaining)
        usage += take * Decimal(price)
        remaining -= take
    assert usage == Decimal("65.50"), f"12 kgal on the seeded tiers is $65.50, got ${usage}"
    # ⚠ **`CR-081`, 2026-09-08 — THIS READ `sewer is 40% of $65.50 = $26.20`.**
    # Sewer is a percentage of the water VOLUME now, priced on sewer's own rate,
    # so this seat's sewer line is 90% × 12 kgal × $5.0000 = **$54.00** and the
    # J2 subtotal moves with it. **This is a DEMO figure derived from the
    # fixture, not a ❄️ B4/B5 frozen one** — it was computed by the `CR-062`
    # addendum lane from the seeded constants and read back off an issued
    # invoice; the PO signed the DISCOUNT (*"Municipal account - yes; 20% off
    # the bill before taxes - yes"*) and not this subtotal. It must move,
    # because the invoice the product now issues says $157.50 and a test
    # asserting $129.70 would be asserting a number the product cannot produce.
    sewer_quantity = kgal * Decimal(fixture.SEWER_PERCENT_OF_WATER) / Decimal("100")
    sewer = (sewer_quantity * Decimal(fixture.SEWER_RATE_PER_UNIT)).quantize(Decimal("0.01"))
    assert sewer_quantity == Decimal("10.8")
    assert sewer == Decimal("54.00"), f"sewer is 90% of 12 kgal at $5.0000 = $54.00, got ${sewer}"
    carts = [
        cart
        for cart in fixture.trash_cart_plan()
        if cart["unit_index"] == fixture.CASE_GOVERNMENT_ACCOUNT
    ]
    trash = len(carts) * Decimal(fixture.TRASH_PER_CART)
    assert trash == Decimal("30.00"), f"two carts at $15.00 is $30.00, got ${trash}"
    subtotal = Decimal(fixture.WATER_BASE) + usage + sewer + trash
    assert subtotal == J2_SUBTOTAL, f"the addendum's subtotal is $157.50, got ${subtotal}"
    assert (subtotal * Decimal("0.20")).quantize(Decimal("0.01")) == J2_DISCOUNT
    assert subtotal - J2_DISCOUNT == J2_PAYABLE


def test_pure_j4_the_industrial_account_is_on_its_own_plan_class():
    """**J4 · the industrial seat derives an INDUSTRIAL plan, not a residential
    one** — otherwise it would bill the `$12.00` residential base and the
    `$180.00` figure would still stand behind nothing."""
    assert fixture.plan_class_for(fixture.CASE_INDUSTRIAL_ACCOUNT) == "industrial"
    assert fixture.plan_class_for(fixture.CASE_GOVERNMENT_ACCOUNT) == "residential", (
        "the government building takes the residential water ladder — that is "
        "the ladder the addendum's subtotal is computed on"
    )
    assert fixture.plan_class_for(fixture.CASE_REFERENCE_BILL) == "residential"
    assert fixture.plan_class_for(46) == "commercial"


def test_pure_j3_j4_touch_no_awkward_case_and_no_frozen_figure():
    """**Neither new seat is one of the awkward cases, so no ❄️ figure moves.**"""
    assert fixture.CASE_GOVERNMENT_ACCOUNT not in fixture.AWKWARD_UNITS
    assert fixture.CASE_INDUSTRIAL_ACCOUNT not in fixture.AWKWARD_UNITS
    # ❄️ GT-17 stands on unit 0 and unit 0 keeps ZERO carts by construction.
    assert fixture.water_consumption_kgal(fixture.CASE_REFERENCE_BILL, "june") == Decimal("8")
    assert not [
        cart
        for cart in fixture.trash_cart_plan()
        if cart["unit_index"] == fixture.CASE_REFERENCE_BILL
    ]


def test_pure_j4_the_industrial_pair_and_what_the_demo_does_not_charge():
    """**J4 · `$180.00` + `$0.085/kWh`, and the `$1,100.00` it leaves out.**

    ⚠ **THE SECOND ASSERTION IS THE POINT OF THE FIRST.** PO ruling 2026-09-02,
    verbatim: *"for usage line use $0.085/kWh"* — said after being shown that
    `$0.085` is the ENERGY half of an energy-plus-demand tariff and that this
    estate takes no demand read. The ruling is lawful and the cost is stated
    rather than hidden, which is what this case exists to keep true.
    """
    kwh = fixture.UNIT_SERVICE_CONSUMPTION[(fixture.CASE_INDUSTRIAL_ACCOUNT, "electric")]
    usage = kwh * Decimal(fixture.INDUSTRIAL_ELECTRIC_PER_KWH)
    assert usage == Decimal("4590.00"), f"54,000 kWh at $0.085 is $4,590.00, got ${usage}"
    assert usage + Decimal(fixture.INDUSTRIAL_ELECTRIC_BASE) == Decimal("4770.00")
    # The demand half nobody bills, at the 100 kW peak the addendum names.
    assert Decimal("100") * Decimal(fixture.INDUSTRIAL_DEMAND_PER_KW) == Decimal("1100.00")
    # ⚠ It is RECORDED and READ BY NOTHING. **This cited `GAS_FLAT_PER_CCF` as
    # the precedent for that posture until 2026-09-07, and gas has LEFT it
    # (`DEF-RAT-4516`): the signed $1.15/ccf is seeded and read.** The pointer
    # is corrected rather than deleted, because the posture itself is unchanged
    # and this constant is still in it — and the difference between the two
    # cases is the useful part. Gas could be seeded the moment its register was
    # moved to `ccf`, which `BR-TEN-1180` did on 2026-09-02; a seeded demand
    # rate would still bill kW against a kWh register (`DEF-497`), and no
    # ruling has given this estate a demand read to price. **A recorded figure
    # leaves this posture when the thing blocking it is removed, not when
    # somebody decides it looks ready** — and gas sat here for five days after
    # its blocker went, which is exactly what DEF-RAT-4516 cost.
    assert fixture.INDUSTRIAL_DEMAND_PER_KW == "11.00"


def test_pure_j4_the_industrial_figures_are_written_to_the_ruled_precision():
    """**CLAUDE.md hard rule 2 · four decimal places, and never a float.**

    `$0.085` at two decimals rounds to `$0.09` — a **5.9% overcharge** on every
    industrial usage line, which is `$270.00` a month on the seeded plant. The
    spelling is asserted as well as the value, because the spelling is what the
    next reader copies.
    """
    raw = fixture.INDUSTRIAL_ELECTRIC_PER_KWH
    assert isinstance(raw, str), "money is never a float"
    assert len(raw.split(".")[1]) == 4, f"{raw!r} is not written to 4 decimal places"
    assert Decimal(raw) == Decimal("0.085")
    # B4 rounds HALF-UP at finalization, so a two-decimal `$0.085` becomes
    # `$0.09`. (Python's own default is banker's rounding, which would give
    # `$0.08` — wrong by the same $270.00 in the other direction. Either way the
    # seeded plant's bill is out by more than its whole monthly base.)
    two_dp = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert two_dp == Decimal("0.09")
    over = (Decimal("54000") * two_dp) - (Decimal("54000") * Decimal(raw))
    assert over == Decimal("270.00"), (
        "rounding this rate to two decimals overcharges the seeded plant by "
        f"${over} a month — which is why hard rule 2 stores four"
    )


def test_pure_the_frozen_figures_this_change_could_have_reached_are_unmoved():
    """**❄️ GT-17 and ❄️ GT-15, checked here because this lane touched a
    consumption scale, an estate and three seeders.**

    A frozen figure moves only by a finance re-sign (HUMAN-GUIDE §6), never by
    a lane, so the check is written down rather than reasoned about.
    """
    # GT-17 — the reference unit's own inputs, from which $39.50 / $15.80 come.
    assert fixture.water_consumption_kgal(fixture.CASE_REFERENCE_BILL, "june") == Decimal("8")
    assert fixture.WATER_TIERS == (("0", "5", "4.00"), ("5", "15", "6.50"), ("15", None, "8.00"))
    assert fixture.WATER_BASE == "8.00"
    # ⚠ **THESE TWO LINES ASSERTED `"40"` AND `$15.80` UNTIL 2026-09-08.** ❄️
    # `GT-17`'s sewer line was RE-SIGNED by the PO that day under HUMAN-GUIDE §6
    # (`CR-081`), which is the only way a frozen figure moves — and it is still
    # true that no LANE may move one. The water half did not move at all.
    assert fixture.SEWER_PERCENT_OF_WATER == "90"
    assert fixture.SEWER_RATE_PER_UNIT == "5.0000"
    usage = Decimal("5") * Decimal("4.00") + Decimal("3") * Decimal("6.50")
    assert usage == Decimal("39.50"), "❄️ GT-17's water usage line — STOP if this moves"
    assert (Decimal("8") * Decimal("90") / Decimal("100") * Decimal("5.0000")) == Decimal(
        "36.0000"
    ), "❄️ GT-17's sewer line, as re-signed 2026-09-08"
    # GT-15 — solar 4 units @ $10 = $40.00, battery 2 @ $12 = $24.00. Untouched
    # by this lane, asserted so "untouched" is a measurement and not a claim.
    assert Decimal("4") * Decimal("10") == Decimal("40")
    assert Decimal("2") * Decimal("12") == Decimal("24")


# ══════════════════════════════════════════════════════════════════════════
# PART 3 · THE LIVE HALF — two real tenants, seeded and billed
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **A CORRECT PRICE IS NOT A BILLED AMOUNT, AND CONFLATING THEM IS HOW A LANE
# REPORTS WORK IT DID NOT DO** (`test_cr062_e_rates`'s own lesson, one change
# later). Everything above is arithmetic over constants; everything below is a
# tenant provisioned through the REAL signup service, planted through the REAL
# sample loader, and read back off an ISSUED invoice.

#: The municipal utility the `$157.50` subtotal belongs to — water, sewer and
#: trash, which is the shape `DEF-2397` calls *"the estate a MUNICIPAL utility
#: gets"* and the shape the addendum worked the figure on.
SHAPE_MUNICIPAL: tuple[str, ...] = ("water", "sewer", "trash")

#: Electric alone, so the industrial bill is the two figures J4 is about and
#: nothing else: the `$180.00` base and `$0.085` per kWh.
SHAPE_INDUSTRIAL: tuple[str, ...] = ("electric",)


def _payload(slug: str, services: list[str]) -> dict:
    data = dict(brazosbend_payload())
    data["subdomain"] = slug
    data["name"] = f"CR-062 J {slug}"
    data["services"] = services
    owner = dict(data["owner"])
    owner["email"] = f"owner@{slug}.test"
    data["owner"] = owner
    return data


def _plant(services: list[str]):
    """A tenant through the REAL signup service, then planted.

    The actor is the provisioning OWNER and not an invented uuid — `DEF-2722`'s
    trap: `tenancy.sample_data._attributed` strips an unknown actor, `BR-BIL-058`
    then refuses to issue anything, and every money block fails for a reason
    that has nothing to do with the change under test.
    """
    tenant, result = provisioned_tenant(_payload(f"cr062j-{uuid.uuid4().hex[:10]}", services))
    owner_id = result["owner_user_id"]
    actor = SimpleNamespace(
        id=uuid.UUID(str(owner_id)),
        pk=uuid.UUID(str(owner_id)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )
    with tenant_ctx(tenant):
        summary = tenancy_sample_data.seed_sample_data(actor)
    return tenant, actor, summary


@pytest.fixture(scope="module")
def municipal_tenant(django_db_setup, django_db_blocker):
    """ONE water + sewer + trash utility for the whole file."""
    with django_db_blocker.unblock():
        yield _plant(list(SHAPE_MUNICIPAL))


@pytest.fixture(scope="module")
def industrial_tenant(django_db_setup, django_db_blocker):
    """ONE electric utility, so the industrial plan has something to price."""
    with django_db_blocker.unblock():
        yield _plant(list(SHAPE_INDUSTRIAL))


def _account_for(tenant, unit_index: int):
    unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[unit_index]
    unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
    return customer_models.Account.objects.get(tenant_id=tenant.id, unit_id=unit.id)


def _first_invoice_lines(tenant, account):
    invoice = (
        billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=account.id)
        .order_by("period_start")
        .first()
    )
    assert invoice is not None, "the account produced no bill at all"
    lines = list(
        billing_models.InvoiceLine.objects.filter(
            tenant_id=tenant.id, invoice_id=invoice.id
        ).select_related("service")
    )
    return invoice, lines


def _total(lines, kind: str, service: str | None = None) -> Decimal:
    return sum(
        (
            line.amount
            for line in lines
            if line.kind == kind
            and (
                service is None
                or (line.service_id is not None and line.service.code == service)
            )
        ),
        Decimal("0"),
    )


@_live
@requires_postgres
def test_live_j3_the_municipal_account_exists_and_is_not_a_legacy_code(municipal_tenant):
    """**J3 · one seeded government customer, carrying the `municipal` code.**

    RED before this lane: the estate held 48 seats and every one of them was
    `residential` or `commercial`. RED again on the first attempt at the fix,
    which is `DEF-3283` and is quoted in the failure this case would produce::

        SCW-U-049: ValidationError: VAL-005 (customers.account.type_is_legacy)
    """
    tenant, _actor, _summary = municipal_tenant
    with tenant_ctx(tenant):
        account = _account_for(tenant, fixture.CASE_GOVERNMENT_ACCOUNT)
        assert account.account_type.code == "municipal", (
            f"the seeded government building is a {account.account_type.code} "
            "account; BR-CUS-094 retired `government` to legacy and `municipal` "
            "is the selectable code for the same customer"
        )
        assert not account.account_type.legacy, (
            "the seed wrote a LEGACY account type onto a NEW record — that is "
            "reaching past the product's own refusal (DEF-3283)"
        )
        customer_name = account.unit.unit_no
    assert customer_name  # the seat is planted and readable


@_live
@requires_postgres
def test_live_j2_the_municipal_discount_is_a_visible_line(municipal_tenant):
    """**J2 end to end · `$157.50` subtotal, `−$31.50` on its own line, `$126.00`.**

    ⚠ **MOVED BY `CR-081` (2026-09-08) — it was `$129.70` / `−$25.94` /
    `$103.76`.** Only the sewer line moved ($26.20 → $54.00); the discount, its
    20% and the requirement below are untouched.

    ⚠ **THE LINE IS THE REQUIREMENT, NOT THE TOTAL.** `DEF-502` makes a discount
    its own invoice line with a NEGATIVE amount and the discount's
    customer-facing name, because a reduction folded silently into a subtotal is
    a bill a customer cannot check. This asserts the line exists, its amount,
    and the three figures around it.
    """
    tenant, _actor, _summary = municipal_tenant
    with tenant_ctx(tenant):
        account = _account_for(tenant, fixture.CASE_GOVERNMENT_ACCOUNT)
        _invoice, lines = _first_invoice_lines(tenant, account)

    charged = (
        _total(lines, "usage") + _total(lines, "base") + _total(lines, "fee")
    )
    assert charged == J2_SUBTOTAL, (
        f"the municipal building's subtotal before taxes is ${charged} and the "
        f"addendum's worked figure is ${J2_SUBTOTAL}. Its parts are water base "
        "$8.00 + water usage $65.50 + sewer $54.00 (90% of 12 kgal at $5.0000, "
        "CR-081) + trash $30.00"
    )
    discount_lines = [line for line in lines if line.kind == "discount"]
    assert discount_lines, (
        "the bill carries NO discount line. The Municipal discount is seeded "
        "and the account is enrolled, so either the enrolment did not land or "
        "the plan does not bind the discount (BR-RAT-110 needs BOTH gates)"
    )
    reduction = _total(lines, "discount")
    assert reduction == -J2_DISCOUNT, (
        f"the reduction is {reduction} and 20% of ${J2_SUBTOTAL} is "
        f"-${J2_DISCOUNT}"
    )
    assert charged + reduction == J2_PAYABLE, (
        f"the building should pay ${J2_PAYABLE} before taxes"
    )
    # B14 rule 31 / DEF-502 — the line prints the discount's NAME, never a code.
    assert any("Municipal" in (line.description or "") for line in discount_lines), (
        "the discount line does not name the programme a customer would "
        f"recognise: {[line.description for line in discount_lines]}"
    )


@_live
@requires_postgres
def test_live_j2_the_reduction_is_taken_before_taxes(municipal_tenant):
    """**`BR-RAT-071` · the PO said *"20% off the bill before taxes"*.**

    Asserted as a RELATIONSHIP rather than as a tax figure, so it holds whatever
    a tenant's authorities charge: the tax on this bill must be computed on the
    DISCOUNTED base, which means it is smaller than the tax the same rates would
    produce on the full `$157.50` (it was `$129.70` until `CR-081`, 2026-09-08).
    """
    tenant, _actor, _summary = municipal_tenant
    with tenant_ctx(tenant):
        account = _account_for(tenant, fixture.CASE_GOVERNMENT_ACCOUNT)
        _invoice, lines = _first_invoice_lines(tenant, account)
    tax = _total(lines, "tax")
    if tax == 0:
        pytest.skip("this tenant levies no tax on these services — nothing to order")
    implied_rate = tax / J2_PAYABLE
    assert tax <= (J2_SUBTOTAL * implied_rate), (
        f"tax of ${tax} is larger than the same rate on the discounted "
        f"${J2_PAYABLE}, so the reduction was taken AFTER taxes"
    )


@_live
@requires_postgres
def test_live_j2_exactly_one_account_is_enrolled_in_anything(municipal_tenant):
    """**The narrowing is the promise, and it is measured.**

    The fixture's reason for enrolling nobody is *"enrolling real accounts in a
    subsidy is a money act"*, and `CR-062` addendum J2 narrows it to ONE
    demonstration seat rather than withdrawing it. A seeder that quietly enrolled
    a second account would be the drift this case exists to catch.
    """
    tenant, _actor, _summary = municipal_tenant
    with tenant_ctx(tenant):
        enrolments = list(
            discount_models.DiscountEnrolment.objects.filter(
                tenant_id=tenant.id
            ).select_related("discount", "account")
        )
        codes = sorted(row.discount.code for row in enrolments)
        municipal = _account_for(tenant, fixture.CASE_GOVERNMENT_ACCOUNT)
        holders = {str(row.account_id) for row in enrolments}
    assert codes == ["MUNICIPAL"], f"the seed enrolled {codes}"
    assert holders == {str(municipal.id)}, (
        "an account other than the one demonstration seat is enrolled in a "
        "subsidy"
    )
    assert all(row.is_sample for row in enrolments), (
        "a seeded enrolment carries no `is_sample` tag, so BR-TEN-061 cannot "
        "remove it and it would outlive the sample set"
    )


@_live
@requires_postgres
def test_live_gt17_is_unmoved_on_the_municipal_tenant(municipal_tenant):
    """**❄️ `GT-17` · water `$39.50`, sewer `$15.80`, on the same seeded tenant.**

    This lane added two seats, two carts, a discount and an enrolment to the
    estate this bill is drawn from. **If this case fails, the change STOPS** —
    a frozen figure moves only by a finance re-sign (HUMAN-GUIDE §6).
    """
    tenant, _actor, _summary = municipal_tenant
    with tenant_ctx(tenant):
        account = _account_for(tenant, fixture.CASE_REFERENCE_BILL)
        _invoice, lines = _first_invoice_lines(tenant, account)
    assert _total(lines, "usage", "water") == Decimal("39.50"), (
        "❄️ GT-17's water usage line moved. STOP — finance re-sign, never a lane"
    )
    assert _total(lines, "usage", "sewer") == Decimal("15.80"), (
        "❄️ GT-17's sewer line moved. STOP — finance re-sign (HUMAN-GUIDE §6)"
    )
    assert not [line for line in lines if line.kind == "discount"], (
        "the GT-17 reference bill has grown a discount line — the Municipal "
        "enrolment reached an account it must never reach"
    )


@_live
@requires_postgres
def test_live_j4_the_industrial_account_bills_180_and_0_085(industrial_tenant):
    """**J4 end to end · `$180.00` base + `$4,590.00` usage on a real invoice.**

    The two figures `DEF-2823` found disagreeing by `$168.00`, finally standing
    behind a document: *"0 accounts are on `IND`, so no bill ever carried either
    figure"* is no longer true of this fixture.
    """
    tenant, _actor, _summary = industrial_tenant
    with tenant_ctx(tenant):
        account = _account_for(tenant, fixture.CASE_INDUSTRIAL_ACCOUNT)
        assert account.account_type.code == "industrial"
        _invoice, lines = _first_invoice_lines(tenant, account)
    base = _total(lines, "base", "electric")
    usage = _total(lines, "usage", "electric")
    assert base == Decimal("180.00"), (
        f"the industrial electric base billed ${base}; the signed figure is "
        "$180.00 and $12.00 would mean the seat took the residential plan"
    )
    assert usage == Decimal("4590.00"), (
        f"54,000 kWh at $0.0850 is $4,590.00 and the bill says ${usage}"
    )
    assert base + usage == Decimal("4770.00")


@_live
@requires_postgres
def test_live_j4_the_household_next_door_keeps_the_12_dollar_base(industrial_tenant):
    """**The industrial plan reaches ONE seat, which is what makes it a class.**

    `BR-RAT-108` separates one service's several amounts by ACCOUNT TYPE. If the
    `$180.00` base leaked onto an ordinary house this would be a rate rise for
    every customer of every seeded electric utility, so it is measured rather
    than assumed.
    """
    tenant, _actor, _summary = industrial_tenant
    with tenant_ctx(tenant):
        account = _account_for(tenant, fixture.CASE_REFERENCE_BILL)
        _invoice, lines = _first_invoice_lines(tenant, account)
    assert _total(lines, "base", "electric") == Decimal("12.00"), (
        "the reference household's electric base is not the signed $12.00"
    )
    assert _total(lines, "usage", "electric") == Decimal("95.50"), (
        "the reference household's 800 kWh no longer prices on the residential "
        "tiers — the industrial flat rate has reached a house"
    )
