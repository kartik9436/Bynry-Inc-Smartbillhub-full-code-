# ── Trace ──────────────────────────────────────────────
# Change:  **CR-062 group E (E1–E8) + D8** (2026-09-02). Six services that
#          billed $0.00 because nothing priced them now carry the Product
#          Owner's own figures, and the two constants that held the placeholder
#          zero and its invented unit are retired TOGETHER.
# Rules:   CLAUDE.md hard rule 2 (money stored to 4 decimals, percentages to 6,
#          both DISPLAYED to 2) · hard rule 3 (a quantity always carries its
#          unit) · BR-MET-108 (a service whose pricing characteristic nobody
#          recorded bills as ZERO — which is what these six STOP doing today) ·
#          BR-RAT-090 (an unmetered service's quantity) · BR-RAT-015 ❄️ /
#          GT-17 ❄️ (water $39.50, sewer $15.80) · GT-15 ❄️ (solar $40.00,
#          battery $24.00) · BR-TEN-060 (a gap is NAMED, never a silent zero)
# Defect:  DEF-497 (a schedule reading $15.00 per MONTH against a quantity of
#          3 CARTS — hard rule 3 satisfied in FORM and wrong in SUBSTANCE).
#          This file is that defect's prevention on four more money paths.
# Tests:   this file
# Impacts: core/sample_fixture.py · apps/rating/sample_data.py
# ───────────────────────────────────────────────────────
"""**THE SIX RATES, AND THE UNIT EACH ONE IS QUOTED PER.**

WHAT WAS WRONG, MEASURED BEFORE THIS LANE STARTED
--------------------------------------------------
`core/sample_fixture.CAPACITY_UNPRICED` was the string `"0"` and it was the
price of **every** capacity service alike, so solar, battery, storm water and
broadband each billed `$0.00` on a correctly-shaped line. Electric's usage was
`BACKBONE_USAGE_UNPRICED`, also `"0"`, so a tenant paying its signed `$12.00`
base drew 800 kWh and was charged nothing for them. Thermal was the same.

None of that was a bug in the engine and none of it was an accident: the zeros
were `BR-MET-108`'s **ruled** zero, standing in for prices nobody had signed
while `OQ-370` and `OQ-1290` were open. The PO signed them on 2026-09-02 and
this file is what asserts the figures.

WHY THE PRICE AND THE UNIT ARE ONE COMMIT AND NOT TWO
------------------------------------------------------
`CAPACITY_UOM` was the string `"month"`, and its own docstring said exactly what
would happen if a lane moved the price without it::

    **So the price and the unit are ONE decision and must move in ONE commit**:
    the day `OQ-370` closes and a per-characteristic figure is signed, a lane
    that changes the price and leaves `month` here has rebuilt `DEF-497` on a
    live money path.

`DEF-497` was a trash schedule reading **$15.00 per MONTH against a quantity of
3 CARTS** — every rule satisfied in form, the money wrong. It was inert here
only because both factors were zero, and `0 × $0.0000` is `$0.00` in any unit at
all. **Seeding a price is what would have armed it**, which is why `CR-062` task
D8 retires the two constants together and why `_capacity_uom` now REFUSES rather
than defaulting. Part 1 §4 below is the case that would have caught it.

⚠ WHAT THIS FILE DELIBERATELY DOES NOT ASSERT — THE SOLAR QUANTITY
-------------------------------------------------------------------
The PO's worked example is three panels of 2 kW, 4 kW and 8 kW on one unit at
`$14.00` per kW = **`$196.00`**. **Only the `$14.00` half of that is this
lane's.** The quantity reaching the bill is still `BR-RAT-090`'s observed COUNT
of assets, so three panels bill as **3** and the line comes out at `$42.00`.
Making it a SUM of installed capacity is `CR-062` tasks **D1/H2** (🔒 rating
math) and is a different lane's work, in files this lane does not touch.

So the `$196.00` case below is asserted as **arithmetic over the seeded rate**,
and it says so in its own name. It goes RED if anyone changes the rate, which is
the half this lane is responsible for. The end-to-end `$196.00` on an issued
bill is `CR-062` F3 and belongs to the lane that lands the sum.

⚠ AND THE PO'S OWN ARITHMETIC IS OFF BY ONE PRODUCT
-----------------------------------------------------
They wrote *"14 X 14 = 156 $"*. Fourteen kW at `$14.00` is **`$196.00`**; they
were told so in the same session and did not dispute it. `test_pure_the_wrong_
figure_156_is_nowhere_in_the_seed` asserts the repo never learns the wrong one —
a wrong figure copied into a fixture becomes a wrong figure asserted by a test,
and then it is the product's answer.

RED PROVED FIRST (law 7), against the tree at this lane's base
---------------------------------------------------------------
Every case below was run on the branch tip BEFORE a line of the fix was written,
in a detached worktree at that commit. The failures are quoted in the lane's
report and in `12-governance/02-decision-log.md`; the shape of them was::

    AttributeError: module 'core.sample_fixture' has no attribute
    'CAPACITY_UNIT_PRICES'

for the pure cases, and, for the live ones, every seeded capacity schedule
carrying `Decimal('0.000000')` where a signed figure now stands.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.rating import sample_data as rating_sample_data
from apps.tenancy import sample_data as tenancy_sample_data
from apps.tenancy.services import SERVICE_DEFAULT_UOMS
from core import sample_fixture as fixture

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

#: ⚠ **NO MODULE-LEVEL `django_db` MARK, for `test_cr062_c`'s own reason.** Part
#: 1 is pure arithmetic over constants and needs no database; marking the module
#: would make every cheap case pay for a test database it never reads, and the
#: whole argument for splitting the layers is that the cheap half fails first.
_live = pytest.mark.django_db


#: **THE SIX FIGURES THE PRODUCT OWNER SIGNED ON 2026-09-02, IN ONE PLACE.**
#:
#: Written out as literals rather than read from the fixture, and that is the
#: point: a test that asserts `fixture.X == fixture.X` cannot fail. These are
#: what was put to the PO in plain English, so these are what the test pins. If
#: a figure below and the fixture disagree, one of them moved without a ruling.
SIGNED_CAPACITY_PRICES: dict[str, str] = {
    "solar": "14.0000",  # PO verbatim: *"rate will be for 1 Kw = 14 $ per KW"*
    "battery": "3.0000",
    "storm_water": "4.5000",
    "broadband": "0.1000",
}

#: The unit each of those prices is quoted per — the service's OWN
#: characteristic, never `month`. This is the `DEF-497` guard's expectation.
SIGNED_CAPACITY_UNITS: dict[str, str] = {
    "solar": "kW",
    "battery": "kW",
    "storm_water": "ERU",
    "broadband": "Mbps",
    # CR-080 (PO 2026-09-07) — thermal arrived on the capacity side and is
    # quoted per CONNECTED REFRIGERATION TON. It is in this map for the same
    # reason the other four are: `DEF-497` is a price quoted per a unit the
    # quantity is not in, and `$12.50 per month` against 100 tons would be it.
    "thermal_heat": "ton",
}

#: Electric's ladder (E1) and thermal's flat rate (E6).
SIGNED_ELECTRIC_TIERS: tuple[tuple[str, str | None, str], ...] = (
    ("0", "500", "0.1100"),
    ("500", "1000", "0.1350"),
    ("1000", None, "0.1600"),
)
#: ⚠ **`SIGNED_THERMAL_PER_TON_HR = "0.0450"` WAS HERE AND IS RETIRED —
#: `CR-080`, 2026-09-07, AND IT IS THE ONE PO-APPROVED FIGURE THAT CR REMOVES.**
#: `$0.045` per ton-hour was put to the PO in plain English with a worked figure
#: and approved (`CR-062` E6, step 5 judgment 3). The PO then ruled thermal
#: capacity-based — *"connected tonnage - it is capacity not metering; i will
#: ahve 100 tonne or 200 tonne etc"* — and **a capacity service has no
#: ton-hour**, so the figure has nothing left to multiply.
#:
#: What replaces it is a per-ton MONTHLY rate in `CAPACITY_UNIT_PRICES`,
#: researched under the PO's own delegation (*"you can research in amrket at
#: Municiapl utility in north amrica and put it there"*) and recorded as a lane
#: judgment rather than a signature. The trade is stated in the review ledger,
#: because a figure the PO personally approved may not retire in silence.
_E6_RETIRED_NAMES = ("SIGNED_THERMAL_PER_TON_HR",)


# ══════════════════════════════════════════════════════════════════════════
# PART 1 · THE PURE LAYER — no database, milliseconds, fails first
# ══════════════════════════════════════════════════════════════════════════


def test_pure_every_capacity_service_carries_the_pos_signed_price():
    """**E2–E5 · the four capacity prices, exactly as signed.**"""
    for code, expected in SIGNED_CAPACITY_PRICES.items():
        actual = fixture.CAPACITY_UNIT_PRICES[code]
        assert actual == expected, (
            f"{code} is seeded at {actual!r} and the Product Owner signed "
            f"{expected!r} on 2026-09-02. A seeded price moves only by a ruling"
        )


def test_pure_the_solar_rate_is_the_pos_own_figure_and_14kw_makes_196():
    """**E3 · `$14.00` per kW, and 14 kW of it is `$196.00`.**

    ⚠ **THIS IS ARITHMETIC OVER THE SEEDED RATE, NOT AN END-TO-END BILL.** The
    quantity half — three panels of 2 + 4 + 8 kW summing to 14 kW rather than
    counting as 3 — is `CR-062` D1/H2 and belongs to another lane. What this
    asserts is the half this lane owns: the RATE the PO gave, and the product it
    makes with their own worked quantity.
    """
    rate = Decimal(fixture.CAPACITY_UNIT_PRICES["solar"])
    assert rate == Decimal("14.0000")
    installed_kw = Decimal("2") + Decimal("4") + Decimal("8")
    assert installed_kw == Decimal("14"), "the PO's own three panels"
    assert installed_kw * rate == Decimal("196.0000"), (
        "14 kW at $14.00 per kW is $196.00 — the PO's message says '14 X 14 = "
        "156 $' and that arithmetic is off by one product"
    )


def test_pure_the_wrong_figure_156_is_nowhere_in_the_seed():
    """**The PO's slip must not become the product's answer.**

    A wrong figure copied into a fixture becomes a wrong figure asserted by a
    test, and then it is what the product charges. `$156` is not a number this
    change may produce from the PO's own example, so it is not a number the
    solar rate may combine with 14 kW to make.
    """
    rate = Decimal(fixture.CAPACITY_UNIT_PRICES["solar"])
    assert Decimal("14") * rate != Decimal("156.00")


def test_pure_electric_tiers_are_the_signed_ladder():
    """**E1 · 0–500 at `$0.1100`, 500–1,000 at `$0.1350`, 1,000+ at `$0.1600`.**"""
    assert fixture.ELECTRIC_TIERS == SIGNED_ELECTRIC_TIERS, (
        "electric's seeded ladder is not the one the PO signed. The PO chose "
        "TIERED over time-of-use (CR-062 judgment 2)"
    )


def test_pure_electric_prices_800_kwh_at_95_50_and_the_bill_at_107_50():
    """**E1 worked · the reference unit's 800 kWh, and the bill it makes.**

    Unit 0 draws `8 × 100 = 800 kWh` in June (`CONSUMPTION_SCALE`). The tier
    boundary convention is `WATER_TIERS`' — each tier's `to` is the next tier's
    `from` — which is the same convention that reproduces `GT-17`'s ❄️ water
    `$39.50`, so it is not a convention this test invents.
    """
    charged = Decimal("0")
    remaining = Decimal("800")
    for lo, hi, price in fixture.ELECTRIC_TIERS:
        if remaining <= 0:
            break
        span = (Decimal(hi) - Decimal(lo)) if hi is not None else remaining
        take = min(span, remaining)
        charged += take * Decimal(price)
        remaining -= take
    assert charged == Decimal("95.50"), (
        "800 kWh should price at 500 x $0.1100 ($55.00) + 300 x $0.1350 "
        f"($40.50) = $95.50, and it priced at ${charged}"
    )
    assert charged + Decimal(fixture.ELECTRIC_BASE) == Decimal("107.50"), (
        "the usage line plus the signed $12.00 base is $107.50"
    )


def test_pure_thermal_is_priced_by_the_connected_ton_and_no_longer_by_the_hour():
    """**`CR-080` · E6's figure is RETIRED and this asserts the retirement.**

    ⚠ **THIS CASE ASSERTED `$0.045` PER TON-HOUR UNTIL 2026-09-07.** The PO
    ruled thermal capacity-based on connected tonnage that day, so there is no
    ton-hour to price. **`$0.045` was a figure the PO personally approved**, so
    the case is rewritten to record its retirement rather than deleted — a
    figure that simply vanishes reads like one nobody ever signed.

    **The E8 four-decimal argument this case carried is UNCHANGED and is
    asserted below on the new figure**, which is the half worth keeping: money
    is stored to 4 decimals and displayed to 2 (CLAUDE.md hard rule 2).
    """
    assert "thermal_heat" not in fixture.METERED_USAGE_PRICES, (
        "thermal still carries a per-ton-hour price. A capacity service has no "
        "ton-hour: that is DEF-497 on a live money path"
    )
    # ⚠ **AND THE MAP IS NOT EMPTY, WHICH A FIRST DRAFT OF THIS CASE ASSERTED.**
    # `gas` landed in it HOURS BEFORE thermal left it, on the same day, from a
    # different lane (`DEF-RAT-4516`, closing `OQ-1290`). Both stand: gas is a
    # flat-priced METERED service and is exactly what the map is for.
    assert set(fixture.METERED_USAGE_PRICES) == {"gas"}, (
        f"METERED_USAGE_PRICES holds {sorted(fixture.METERED_USAGE_PRICES)}; a NEW "
        "entry here is a flat-priced metered service somebody has to have signed"
    )
    rate = fixture.CAPACITY_UNIT_PRICES["thermal_heat"]
    assert rate == "12.5000", f"thermal is seeded at {rate}"
    assert len(rate.split(".")[1]) == 4, "hard rule 2 — money is STORED to four"
    # The PO's own two numbers, priced. *"i will ahve 100 tonne or 200 tonne"*.
    assert (Decimal("100") * Decimal(rate)).quantize(Decimal("0.01")) == Decimal("1250.00")
    assert (Decimal("200") * Decimal(rate)).quantize(Decimal("0.01")) == Decimal("2500.00")


def test_pure_every_seeded_figure_is_written_to_four_decimal_places():
    """**E8 · money stored to 4 decimals, and never a float.**

    CLAUDE.md hard rule 2. Asserted on the SPELLING as well as the value,
    because the spelling is what a later reader copies: `"0.10"` invites a
    two-decimal sibling and `"0.1000"` does not.
    """
    figures: dict[str, str] = {
        **{f"capacity:{k}": v for k, v in fixture.CAPACITY_UNIT_PRICES.items() if v != "0"},
        **{f"metered:{k}": v for k, v in fixture.METERED_USAGE_PRICES.items()},
        **{f"tier:{lo}": price for lo, _hi, price in fixture.ELECTRIC_TIERS},
    }
    assert figures, "no figures found — the maps are empty and this test is asleep"
    for name, raw in figures.items():
        assert isinstance(raw, str), f"{name} is {type(raw)}, and money is never a float"
        assert "." in raw, f"{name} = {raw!r} states no decimal places"
        places = len(raw.split(".")[1])
        assert places == 4, (
            f"{name} = {raw!r} is written to {places} decimal place(s); money is "
            "stored to 4 (CLAUDE.md hard rule 2) and DISPLAYED to 2"
        )


def test_pure_d8_the_two_placeholder_constants_are_retired_together():
    """**D8 · `CAPACITY_UNPRICED` and `CAPACITY_UOM` are both GONE.**

    The old constant's own docstring required them to move in ONE commit. This
    asserts they did — and asserts it on BOTH, because retiring only the price
    is precisely the `DEF-497` re-run the docstring warned about.
    """
    assert not hasattr(fixture, "CAPACITY_UNPRICED"), (
        "CAPACITY_UNPRICED still resolves, so a lane can still reach for a "
        "single price for every capacity service"
    )
    assert not hasattr(fixture, "CAPACITY_UOM"), (
        "CAPACITY_UOM still resolves. A price that can still travel without "
        "its unit is DEF-497 waiting to happen — that is the whole of task D8"
    )


def test_pure_no_capacity_price_is_quoted_per_month():
    """**The `DEF-497` guard, stated as the thing that must never be true.**

    Each capacity service's unit is its own characteristic, declared in the
    platform's seed map — never `month`, which is what the retired fallback
    would have supplied. Read from `SERVICE_DEFAULT_UOMS` rather than from a
    list kept here, so the day the seed map changes this case moves with it.
    """
    for code, expected in SIGNED_CAPACITY_UNITS.items():
        declared = SERVICE_DEFAULT_UOMS[code].primary
        assert declared == expected, f"{code} declares {declared!r}, expected {expected!r}"
        assert declared != "month", (
            f"{code} would be priced per MONTH against a quantity measured in "
            f"{expected} — that is DEF-497 on a live money path"
        )


def test_pure_fire_is_not_priced_by_this_change():
    """**CR-063's eleventh service keeps the ruled zero, and keeps it stated.**

    Fire arrived hours after these six were signed and no price for it has been
    put to the PO (`OQ-1360`). Its `"0"` is `BR-MET-108`'s ruled zero — a stored
    zero is a PRICE and prints `$0.00`, where an OMISSION means *this size is
    not served* and stops the bill (`CR-013` part 1 / `DEF-277`) — so the key
    must be PRESENT and must be zero.
    """
    assert "fire" in fixture.CAPACITY_UNIT_PRICES, (
        "fire must be a stated zero, not an absent key — an omission is a "
        "refusal that stops the bill (DEF-277)"
    )
    assert Decimal(fixture.CAPACITY_UNIT_PRICES["fire"]) == Decimal("0")


def test_pure_every_capacity_service_the_fixture_speaks_has_a_price():
    """**Nothing in the capacity list may be missing from the price map.**

    A `KeyError` at seed time fails a whole block; more to the point, a service
    added to `CAPACITY_ESTATE_SERVICES` without a decision about its price is
    exactly how `fire` would have silently inherited `$14.00` if the map had a
    default. It has none, on purpose, and this is the case that says so.
    """
    missing = [
        code
        for code in fixture.CAPACITY_ESTATE_SERVICES
        if code not in fixture.CAPACITY_UNIT_PRICES
    ]
    assert not missing, (
        f"{missing} ride the capacity estate and no price is stated for them. "
        "State a signed figure, or a ruled zero with the question that holds it"
    )


def test_pure_gas_left_group_es_boundary_and_is_now_priced():
    """**Group E priced six services and gas was not one of them — until the
    PO asked for it directly on 2026-09-07 (`DEF-RAT-4516`).**

    ⚠ **THIS CASE ASSERTED `"gas" not in METERED_USAGE_PRICES` AND IS FLIPPED
    DELIBERATELY.** Its reasoning was a SCOPE boundary and was correct as such:
    `[W] §1` signs gas at `$1.15` per `ccf`, the seed map had just moved to
    `ccf` so it *could* have been seeded, but `E1`–`E6` name electric, storm
    water, solar, broadband, battery and thermal — and seeding a seventh would
    have been the `CR-062` lane widening its own scope on a money path. It was
    recorded as a boundary rather than left for the next reader to wonder about,
    which is exactly right.

    **A boundary is not a rule, and this one was crossed by the person entitled
    to cross it**: PO 2026-09-07, *"please fix this gap - One real gap, and it
    is money. Gas bills $0.00 usage"*. Nothing about group E moved; a service
    outside it was priced from its own signed figure.
    """
    assert fixture.METERED_USAGE_PRICES["gas"] == "1.1500", (
        "gas left METERED_USAGE_PRICES again — that is DEF-RAT-4516 returning, "
        "and it ships a $0.00 usage line on every seeded gas bill"
    )
    assert Decimal(fixture.METERED_USAGE_PRICES["gas"]) == Decimal(fixture.GAS_FLAT_PER_CCF)
    # ⚠ **THE LINE THAT STOOD HERE ASSERTED THERMAL'S `$0.045` PER TON-HOUR
    # AND IT RETIRED HOURS LATER THE SAME DAY (`CR-080`).** Gas arrived in
    # this map and thermal left it, independently, within one afternoon: the
    # PO signed gas's workbook figure and ruled thermal capacity-based on
    # connected tonnage. **The map's own rule is unchanged and is why gas
    # belongs and thermal no longer does** — it holds a flat price for a
    # METERED service, and a capacity service has no register to read.
    assert "thermal_heat" not in fixture.METERED_USAGE_PRICES, (
        "thermal still carries a per-ton-hour price. A capacity service has "
        "no ton-hour: that is DEF-497 on a live money path"
    )
    assert fixture.BACKBONE_USAGE_UNPRICED == "0", (
        "the placeholder is kept as the `.get()` default for a metered service "
        "with no signed price; no seeded service lands on it now"
    )


# ══════════════════════════════════════════════════════════════════════════
# PART 2 · THE LIVE RUN — two provisionings, on real PostgreSQL
# ══════════════════════════════════════════════════════════════════════════

#: A tenant that sells electric, water, sewer and solar. It carries E1 (the
#: tiers), E3 (solar), ❄️ GT-17 (water/sewer unmoved), and — because it sells
#: neither battery nor broadband nor storm water — the E7 negative case.
SHAPE_A: tuple[str, ...] = ("electric", "water", "sewer", "solar")

#: The other four signed services, so all six rates are proved on a real seed.
SHAPE_B: tuple[str, ...] = ("storm_water", "broadband", "battery", "thermal_heat")


def _payload(slug: str, services: list[str]) -> dict:
    data = dict(brazosbend_payload())
    data["subdomain"] = slug
    data["name"] = f"CR-062 E {slug}"
    data["services"] = services
    owner = dict(data["owner"])
    owner["email"] = f"owner@{slug}.test"
    data["owner"] = owner
    return data


def _plant(services: list[str]):
    """A tenant through the REAL signup service, then planted.

    The actor is the provisioning OWNER and not `admin_actor()` — `DEF-2722`'s
    trap: an invented uuid is stripped by `tenancy.sample_data._attributed`,
    `BR-BIL-058`'s release gate then refuses to issue anything, and every money
    block fails for a reason unrelated to this change.
    """
    tenant, result = provisioned_tenant(_payload(f"cr062e-{uuid.uuid4().hex[:10]}", services))
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
def shape_a_tenant(django_db_setup, django_db_blocker):
    """ONE electric + water + sewer + solar utility for the whole file."""
    with django_db_blocker.unblock():
        yield _plant(list(SHAPE_A))


@pytest.fixture(scope="module")
def shape_b_tenant(django_db_setup, django_db_blocker):
    """ONE storm water + broadband + battery + thermal utility."""
    with django_db_blocker.unblock():
        yield _plant(list(SHAPE_B))


def _seeded_prices(tenant) -> dict[str, list[tuple[Decimal, str | None]]]:
    """`service code -> [(unit_price, uom), …]` over every seeded schedule.

    Reads the ACTIVE versions' tier rows, which is where both a flat schedule
    (a single 0→∞ row, `BR-RAT-032`) and a tiered one land, so the two shapes
    are read by one query rather than by two branches that could disagree.
    """
    out: dict[str, list[tuple[Decimal, str | None]]] = {}
    versions = (
        rating_models.TariffVersion.objects.filter(
            tenant_id=tenant.id, tariff__is_sample=True
        )
        .exclude(effective_from=None)
        .select_related("tariff", "tariff__service")
    )
    for version in versions:
        code = version.tariff.service.code
        tiers = rating_models.RateTier.objects.filter(
            tenant_id=tenant.id, tariff_version_id=version.id
        ).order_by("seq")
        for tier in tiers:
            out.setdefault(code, []).append((tier.unit_price, version.uom))
    return out


def _schedule_prices(tenant, schedule_name: str) -> list[Decimal]:
    """The active tier prices of ONE named seeded schedule, in row order.

    `_seeded_prices` above answers per SERVICE, which stopped being enough on
    2026-09-02: `CR-062` addendum J4 gives electric two schedules — the household
    ladder and the industrial flat rate — and a per-service list cannot tell a
    second schedule from a fourth rung on the first one.
    """
    version = (
        rating_models.TariffVersion.objects.filter(
            tenant_id=tenant.id, tariff__is_sample=True, tariff__name=schedule_name
        )
        .exclude(effective_from=None)
        .first()
    )
    if version is None:
        return []
    return [
        tier.unit_price
        for tier in rating_models.RateTier.objects.filter(
            tenant_id=tenant.id, tariff_version_id=version.id
        ).order_by("seq")
    ]


@_live
@requires_postgres
def test_live_the_capacity_rates_reach_a_real_seeded_schedule(
    shape_a_tenant, shape_b_tenant
):
    """**E2–E5 · solar, battery, storm water and broadband, on a real tenant.**

    RED before this lane: every one of these was `Decimal('0.000000')`.
    """
    prices: dict[str, list[tuple[Decimal, str | None]]] = {}
    for tenant, _actor, _summary in (shape_a_tenant, shape_b_tenant):
        with tenant_ctx(tenant):
            prices.update(_seeded_prices(tenant))
    for code, expected in SIGNED_CAPACITY_PRICES.items():
        assert code in prices, f"{code} has no seeded rate schedule at all"
        rates = {rate for rate, _uom in prices[code]}
        assert rates == {Decimal(expected)}, (
            f"{code} is seeded at {rates} and the PO signed ${expected}"
        )


@_live
@requires_postgres
def test_live_each_capacity_price_is_quoted_per_its_own_unit_not_month(
    shape_a_tenant, shape_b_tenant
):
    """**D8 / `DEF-497` · the unit that reaches the database beside the price.**

    This is the case the retired `CAPACITY_UOM` fallback would have failed. It
    reads the `uom` the seeded schedule actually stores, not the map it was
    supposed to come from — a guarantee stated in prose and delivered by no code
    is hard-won law 1.
    """
    seen: dict[str, set[str | None]] = {}
    for tenant, _actor, _summary in (shape_a_tenant, shape_b_tenant):
        with tenant_ctx(tenant):
            for code, rows in _seeded_prices(tenant).items():
                seen.setdefault(code, set()).update(uom for _rate, uom in rows)
    for code, expected in SIGNED_CAPACITY_UNITS.items():
        assert seen.get(code) == {expected}, (
            f"{code}'s seeded schedule is quoted per {seen.get(code)} and its "
            f"price is stated per {expected}. A price per 'month' against a "
            f"quantity in {expected} is DEF-497 on a live money path"
        )


@_live
@requires_postgres
def test_live_thermal_is_seeded_at_12_50_per_connected_ton(shape_b_tenant):
    """**`CR-080` · thermal's per-ton rate reaches a schedule, at four decimals,
    quoted per `ton` and never per `month`.**

    ⚠ **THIS CASE EXPECTED `$0.045` PER `ton-hr` UNTIL 2026-09-07** and was
    named for it. The PO ruled thermal capacity-billed on connected tonnage, so
    the schedule it looks at is a CAPACITY schedule now — which is why the unit
    half of the assertion matters more than it did: `$12.50 per month` against a
    quantity of 100 tons is `DEF-497` exactly, and `_capacity_uom` refuses
    rather than falling back precisely to stop it.
    """
    tenant, _actor, _summary = shape_b_tenant
    with tenant_ctx(tenant):
        prices = _seeded_prices(tenant)
    assert "thermal_heat" in prices, "thermal has no seeded rate schedule"
    rates = {rate for rate, _uom in prices["thermal_heat"]}
    assert rates == {Decimal("12.5")}, f"thermal is seeded at {rates}, expected $12.50"
    uoms = {uom for _rate, uom in prices["thermal_heat"]}
    assert uoms == {"ton"}, f"thermal is quoted per {uoms}, expected ton"


@_live
@requires_postgres
def test_live_electric_is_seeded_as_the_three_signed_tiers(shape_a_tenant):
    """**E1 · the ladder reaches the database as three rows, in order.**

    ⚠ **AMENDED 2026-09-02 (`CR-062` addendum J4), AND IT WENT RED FIRST, WHICH
    IS THIS CASE WORKING.** It read every seeded electric price into one list and
    asserted the list was the three-rung ladder — true while electric had exactly
    one schedule. J4 seeds a SECOND: the industrial flat rate at `$0.0850`, which
    `BR-RAT-108` requires to be a separate schedule because one service's several
    prices are separated by CLASS and a shared name would collide on
    `uq_tariffs_tenant_name_service`. The failure was exact and said so:

        electric's seeded tiers are [0.110000, 0.135000, 0.160000, 0.085000]

    **The assertion is SHARPENED rather than widened.** It now names both — the
    residential ladder in order, and the industrial rate as the one flat row —
    so an accidental fourth rung on the household ladder still goes red, which a
    set-membership check would have stopped catching.
    """
    tenant, _actor, _summary = shape_a_tenant
    with tenant_ctx(tenant):
        prices = _seeded_prices(tenant)
        ladder = _schedule_prices(tenant, rating_sample_data.backbone_schedule_name("electric"))
        industrial = _schedule_prices(tenant, rating_sample_data.SCHEDULE_ELECTRIC_IND)
    assert "electric" in prices, "electric has no seeded rate schedule"
    assert ladder == [Decimal("0.11"), Decimal("0.135"), Decimal("0.16")], (
        f"electric's household ladder is {ladder}; the PO signed $0.1100 / $0.1350 / $0.1600"
    )
    assert industrial == [Decimal("0.085")], (
        f"the industrial electric schedule prices {industrial}; the PO ruled "
        "$0.0850 per kWh for the usage line (CR-062 addendum J4)"
    )
    uoms = {uom for _rate, uom in prices["electric"]}
    assert uoms == {"kWh"}, f"electric is quoted per {uoms}, expected kWh"


@_live
@requires_postgres
def test_live_e7_a_service_the_tenant_did_not_enable_gets_no_rate_at_all(
    shape_a_tenant,
):
    """**E7 · nothing is seeded for a service the tenant did not tick.**

    PO verbatim: *"all these prices shoudl take effect if Utility services are
    enbaled by user at the time of Tenant creations"*.

    ⚠ **THE ASSERTION IS "NO ROW", NOT "A ZERO ROW", AND THAT IS THE WHOLE
    CASE.** A zero-priced schedule for a service the utility does not sell is
    not a smaller version of the right answer — it is a rate on a screen for a
    service that is not on offer, and `CR-062` §6b rule 1 says *"Not a meter,
    not a rate, not a `$0.00` line"*. This tenant sells solar and does NOT sell
    battery, broadband or storm water, so those three must be absent entirely.
    """
    tenant, _actor, _summary = shape_a_tenant
    with tenant_ctx(tenant):
        prices = _seeded_prices(tenant)
    assert "solar" in prices, "the tenant DOES sell solar and must have its rate"
    for code in ("battery", "broadband", "storm_water", "thermal_heat"):
        assert code not in prices, (
            f"the tenant did not enable {code} at signup and a rate schedule was "
            f"seeded for it anyway ({prices.get(code)}). CR-062 section 6b rule 1: "
            "'Not a meter, not a rate, not a $0.00 line'"
        )


@_live
@requires_postgres
def test_live_electric_bills_95_50_of_usage_and_107_50_with_its_base(shape_a_tenant):
    """**E1 end to end · 800 kWh on the reference unit's issued bill.**

    The figure that was `$0.00` on this exact line before this lane, while the
    customer paid the signed `$12.00` base for the privilege.
    """
    tenant, _actor, _summary = shape_a_tenant
    with tenant_ctx(tenant):
        unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[
            fixture.CASE_REFERENCE_BILL
        ]
        unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
        account = customer_models.Account.objects.get(tenant_id=tenant.id, unit_id=unit.id)
        invoice = (
            billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=account.id)
            .order_by("period_start")
            .first()
        )
        assert invoice is not None, "the reference account produced no bill"
        lines = list(
            billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, invoice_id=invoice.id
            ).select_related("service")
        )

    def total(service: str, kind: str) -> Decimal:
        return sum(
            (
                line.amount
                for line in lines
                if line.service_id is not None
                and line.service.code == service
                and line.kind == kind
            ),
            Decimal("0"),
        )

    usage = total("electric", "usage")
    base = total("electric", "base")
    assert usage == Decimal("95.50"), (
        f"800 kWh at the signed tiers is $95.50 and the bill says ${usage}"
    )
    assert base == Decimal("12.00"), f"the signed electric base is $12.00, got ${base}"
    assert usage + base == Decimal("107.50")


@_live
@requires_postgres
def test_live_gt17_is_unmoved_by_every_rate_this_lane_seeded(shape_a_tenant):
    """**F5 / ❄️ · water `$39.50` and sewer `$15.80`, on the same bill.**

    This is the guard the whole change rests on. `GT-17`'s reference bill is
    asserted as PER-LINE figures, so adding priced electric and solar lines to
    the same bill ADDS lines and moves neither; sewer is 40% of the WATER usage
    charge, so it is unaffected too. **If this case fails, the change STOPS** —
    a frozen figure moves only by a finance re-sign (HUMAN-GUIDE §6), never by
    a lane.
    """
    tenant, _actor, _summary = shape_a_tenant
    with tenant_ctx(tenant):
        unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[
            fixture.CASE_REFERENCE_BILL
        ]
        unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
        account = customer_models.Account.objects.get(tenant_id=tenant.id, unit_id=unit.id)
        invoice = (
            billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=account.id)
            .order_by("period_start")
            .first()
        )
        assert invoice is not None, "the GT-17 reference account produced no bill"
        lines = list(
            billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, invoice_id=invoice.id
            ).select_related("service")
        )

    def total(service: str, kind: str) -> Decimal:
        return sum(
            (
                line.amount
                for line in lines
                if line.service_id is not None
                and line.service.code == service
                and line.kind == kind
            ),
            Decimal("0"),
        )

    assert total("water", "usage") == Decimal("39.50"), (
        "❄️ GT-17's water usage line moved. STOP — this is a finance re-sign "
        "(HUMAN-GUIDE §6), never an inline edit"
    )
    assert total("sewer", "usage") == Decimal("15.80"), (
        "❄️ GT-17's sewer line moved. STOP — finance re-sign (HUMAN-GUIDE §6)"
    )


@_live
@requires_postgres
def test_live_what_each_priced_service_actually_bills_today(shape_b_tenant):
    """**THE HONEST END STATE, RECORDED SO IT GOES RED WHEN IT CHANGES.**

    ⚠ **A CORRECT PRICE IS NOT A NON-ZERO BILL, AND CONFLATING THEM IS HOW A
    LANE REPORTS WORK IT DID NOT DO.** This lane seeded six rates and every one
    of them reaches a real schedule (the cases above prove it). Only the two
    METERED services turn into money on a seeded tenant, because only they have
    a quantity: their meters are read.

    ⚠ **UPDATED 2026-09-02 WHEN `CR-062` D3–D5 LANDED — AND THAT IS THIS CASE
    DOING EXACTLY WHAT IT WAS WRITTEN TO DO.** It was written asserting that all
    four capacity services billed `$0.00` *on purpose*, so that the day the
    equipment was planted it would go RED and name itself as the thing to
    update. It did: **battery and broadband went red together** when
    `capacity_equipment_plan()` put two batteries and three broadband lines on
    the estate. The assertion is UPDATED and not deleted, which is what the old
    text asked for in its own words.

    **THREE OF THE FOUR NOW BILL REAL MONEY** (solar on the other shape;
    battery and broadband here), because the price, the arithmetic AND the
    equipment are finally all present at once — no one of the three lanes
    produced a dollar on its own.

    **STORM WATER STILL BILLS `$0.00`, AND THE REASON IS NO LONGER THE ONE
    ABOVE.** Its `$4.5000` per ERU is seeded and its five property sizes are
    ratified; what is missing is somewhere to put the ERU. A capacity total is
    read off `Asset.size_class` through the asset's service point, and none of
    `BR-AST-042`'s ratified twelve asset types is a storm-water connection —
    an impervious-area assessment is not equipment. `DEF-2388` carries the three
    options. **That zero is asserted here on purpose for the same reason the
    other three were: the day storm water is planted, this goes RED and says so.**
    """
    tenant, _actor, _summary = shape_b_tenant
    with tenant_ctx(tenant):
        billed: dict[str, Decimal] = {}
        for line in billing_models.InvoiceLine.objects.filter(
            tenant_id=tenant.id, invoice__status="issued"
        ).select_related("service"):
            if line.service_id is None:
                continue
            billed[line.service.code] = billed.get(line.service.code, Decimal("0")) + line.amount

    assert billed, "the tenant issued no bill lines at all"
    # ⚠ **THERMAL CHANGED SIDES HERE ON 2026-09-07 (`CR-080`) AND STILL HAS TO
    # BILL.** It used to read *"thermal is METERED: its meters are read, so its
    # signed $0.045 per ton-hour becomes real money"*. It is capacity-billed on
    # connected tonnage now, and `_seed_cr080_thermal_tonnage` records that
    # tonnage on the unit — so a `$0.00` here means the tonnage did not reach
    # this tenant, which is `DEF-2388`'s exact shape and is why the assertion
    # stays rather than being softened to "a line exists".
    for code in ("battery", "broadband", "thermal_heat"):
        assert billed.get(code, Decimal("0")) > 0, (
            f"{code} bills {billed.get(code)}. Its price is seeded and CR-062 "
            "D3-D5 plants its equipment, so it must bill something — a $0.00 "
            "here means the equipment did not reach this tenant"
        )
    # Storm water is the one that could not be planted: an ERU has no device to
    # sit on and none of the twelve ratified asset types is a storm-water
    # connection (DEF-2388). Asserted at zero ON PURPOSE, so the day it is
    # planted this goes red and names itself as the thing to update.
    if "storm_water" in billed:
        assert billed["storm_water"] == Decimal("0"), (
            f"storm water now bills {billed['storm_water']}. That is DEF-2388 "
            "closing — UPDATE this case and the D6 sentence in CR-062 beside it; "
            "do not delete the assertion"
        )


@_live
@requires_postgres
def test_live_a_capacity_uom_that_is_not_declared_is_refused_by_name(shape_a_tenant):
    """**D8 · the refusal that replaced the `month` default, proved to bite.**

    Hard-won law 7 in miniature: a guard trusted green is not a guard. This
    clears the tenant's declared units for solar and asserts the seeder REFUSES
    by name rather than quoting `$14.00` per some invented unit.

    The write is rolled back — the case runs inside the test transaction and
    the module-scoped tenant is read by later cases.
    """
    from django.db import transaction

    from apps.tenancy import models as tenancy_models

    tenant, _actor, _summary = shape_a_tenant
    with tenant_ctx(tenant):
        try:
            with transaction.atomic():
                tenancy_models.TenantService.objects.filter(
                    tenant_id=tenant.id, service__code="solar"
                ).update(billed_uom=None, primary_uom=None)
                with pytest.raises(rating_sample_data.CapacityUomNotDeclared) as excinfo:
                    rating_sample_data._capacity_uom("solar")
                assert "solar" in str(excinfo.value)
                assert "DEF-497" in str(excinfo.value), (
                    "the refusal must name the defect it prevents, so the next "
                    "reader knows why a default would be wrong"
                )
                raise _Rollback()
        except _Rollback:
            pass


class _Rollback(Exception):
    """Sentinel that unwinds the atomic block above without failing the test."""
