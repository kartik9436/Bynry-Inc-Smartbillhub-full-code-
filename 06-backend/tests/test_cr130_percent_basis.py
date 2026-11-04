# ── Trace ──────────────────────────────────────────────
# Change:   CR-130-BRC07 — a percentage of another service can be a percentage
#           of its MONEY or of its METER, and the meter basis may be priced
#           through a LADDER. PO ruling 2026-09-22.
# Rules:    BR-RAT-1030 (NEW — the two bases and what each requires) ·
#           BR-RAT-015 ❄️ SUPERSEDED 2026-09-08 by CR-081 · BR-RAT-026/032
#           (every unit bills through a tier; one price is ONE 0→∞ block) ·
#           BR-RAT-003 (a plugin never rounds) · CLAUDE.md hard rule 3
# Golden:   ❄️ GT-17 ($36.00) · GT-20 ($54.00) · GT-25 ($27.00) · GT-26
#           ($27.00) — all on the `usage` basis, all re-signed 2026-09-08, and
#           NONE of them moves. Asserted directly below rather than assumed.
# Tests:    this file · tests/test_us_rat_012_percent_of_service.py (the usage
#           basis through the engine) · tests/test_cr081_sewer_volume_basis.py
#           (the stored half)
# ───────────────────────────────────────────────────────
"""CR-130-BRC07 — the Product Owner's two worked figures, and what guards them.

THE TWO FIGURES ARE THE ACCEPTANCE TEST AND THEY ARE ASSERTED FIRST
--------------------------------------------------------------------
    "if water charge is $100, and %age is 80% then sewer cahrge will be $80"
    "if Water usage will be 100 gallan %age is 80% then sewer uage will be 80
     gallan = sewer charge will be 80 X { flat rate or tiered rate}"

Everything else in this file exists because one of those two sentences has a
way of going quietly wrong:

  * **the basis can be dropped in transit.** `percent_basis` crosses four hops
    — column → `pricing_inputs` → `gather` → `normalize` → plugin — and a hop
    that loses it would reach the plugin as None. On GT-17's own bill the two
    bases are **$36.00** and **$35.55**: both plausible, neither flagged. So
    the plugin REFUSES a None, and that refusal is asserted here.
  * **the ladder can be silently truncated.** `pricing_inputs` read
    `tiers[0].unit_price` and discarded the rest — correct while nothing could
    create a second block, and a wrong-money bug the moment one can. The
    five-block case below is the one that would have gone wrong.
  * **the rate can be accepted where it means nothing.** A price per gallon on
    the charge basis is a number the tenant states, the screen shows, and the
    engine drops. Refused by name at both layers.
  * **the frozen figures can move.** They are re-asserted here from raw
    inputs, because `10-scripts/03-golden-verify.py` checks documents against
    themselves and *cannot* see the engine drift (CLAUDE.md, DEF-2846).

HUMAN-REVIEW-PENDING 🔒 — money math. Row in
12-governance/09-human-review-ledger.md.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating import engine, models, selectors, services
from apps.rating.pricing import errors
from apps.tenancy import models as tenancy_models
from core import sample_fixture as fixture

from tests.test_us_rat_helpers import *  # noqa: F401,F403
from tests.test_us_rat_helpers import provisioned_tenant, tenant_ctx

#: Every case here touches the database or the engine's sample tenant, and the
#: pure-engine ones cost nothing extra by carrying the mark.
pytestmark = pytest.mark.django_db

USD = "USD"
ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=31, service_days=31)

#: The PO's charge-basis figure needs a basis service whose usage charge is
#: **exactly $100.00**, so the arithmetic on screen is the arithmetic in the
#: test: 100 gallons at $1.00.
WATER_100 = rating_seam.TariffConfig(
    service="water",
    model="flat",
    billed_unit="gal",
    # The base is here ON PURPOSE. `BR-RAT-015`'s exclusions are the whole
    # arithmetic of the charge basis, and an excluded number that is not on the
    # bill is not excluded by anything.
    base_charge=Decimal("25.00"),
    unit_price=Decimal("1.00"),
)
HUNDRED_GAL = rating_seam.Quantity(amount=Decimal("100"), unit="gal")


def _sewer(**overrides):
    fields = {
        "service": "sewer",
        "model": "percent_of_service",
        "billed_unit": "gal",
        "percent": Decimal("80"),
        "basis_service": "water",
    }
    fields.update(overrides)
    return rating_seam.TariffConfig(**fields)


def bill(services_, **kwargs):
    return engine.price_bill(services=services_, period=FULL_MONTH, account=ACCOUNT, **kwargs)


def _sewer_line(priced):
    (line,) = [row for row in priced.lines_of("usage") if row.service == "sewer"]
    return line


def _sewer_lines(priced):
    return [row for row in priced.lines_of("usage") if row.service == "sewer"]


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE TWO FIGURES THE PRODUCT OWNER GAVE
# ══════════════════════════════════════════════════════════════════════════


def test_cr130_the_charge_basis_bills_eighty_dollars():
    """*"if water charge is $100, and %age is 80% then sewer cahrge will be
    $80"* → **$80.00**.

    The water BASE of $25.00 is on this bill and is not in the basis: 80% of
    $125.00 would be $100.00. `engine._usage_dollars` filters by line KIND,
    which is `BR-RAT-015`'s three exclusions restored with the arithmetic they
    belong to.
    """
    priced = bill(((WATER_100, HUNDRED_GAL), (_sewer(percent_basis="charge"), HUNDRED_GAL)))

    (water_usage,) = [row for row in priced.lines_of("usage") if row.service == "water"]
    assert water_usage.amount == Decimal("100.00")
    (water_base,) = [row for row in priced.lines_of("base") if row.service == "water"]
    assert water_base.amount == Decimal("25.00")

    sewer = _sewer_line(priced)
    assert sewer.amount == Decimal("80.00")
    assert sewer.taxable  # B4.2 — the sewer line is itself in the tax base
    # A percentage of MONEY prints no consumption. Inventing one (0.8 x 100 gal)
    # would state a volume nobody metered — this file's own plugin says so.
    assert sewer.quantity is None
    assert sewer.unit is None
    assert "80.00% of water usage charges" in sewer.description


def test_cr130_the_usage_basis_bills_eighty_gallons_at_this_schedules_own_rate():
    """*"if Water usage will be 100 gallan %age is 80% then sewer uage will be
    80 gallan = sewer charge will be 80 X { flat rate }"*.

    80 gallons at $0.50 = **$40.00**, and the LINE says 80 gal so the customer
    can check it — there is no sewer meter to read it off.
    """
    priced = bill(
        (
            (WATER_100, HUNDRED_GAL),
            (_sewer(percent_basis="usage", unit_price=Decimal("0.5000")), HUNDRED_GAL),
        )
    )
    sewer = _sewer_line(priced)
    assert (sewer.quantity, sewer.unit) == (Decimal("80.0"), "gal")
    assert sewer.unit_price == Decimal("0.5000")
    assert sewer.amount == Decimal("40.00")
    assert "80.00% of water volume" in sewer.description


def test_cr130_the_same_two_numbers_bill_differently_on_the_two_bases():
    """**THE REASON THE BASIS IS STORED AND NEVER INFERRED.** One water bill,
    one percentage, two answers — $80.00 and $40.00 — and each is right for the
    basis the tenant chose. Nothing on the bill distinguishes them afterwards.
    """
    charged = bill(((WATER_100, HUNDRED_GAL), (_sewer(percent_basis="charge"), HUNDRED_GAL)))
    used = bill(
        (
            (WATER_100, HUNDRED_GAL),
            (_sewer(percent_basis="usage", unit_price=Decimal("0.5000")), HUNDRED_GAL),
        )
    )
    assert _sewer_line(charged).amount == Decimal("80.00")
    assert _sewer_line(used).amount == Decimal("40.00")


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE ❄️ FROZEN FIGURES, RE-ASSERTED FROM RAW INPUTS
# ══════════════════════════════════════════════════════════════════════════

#: ❄️ GT-17's own water schedule ([W] §1) and its $8.00 base.
GT17_WATER = rating_seam.TariffConfig(
    service="water",
    model="tiered",
    billed_unit="kgal",
    base_charge=Decimal("8.00"),
    tiers=(
        rating_seam.Tier(upper=Decimal("5"), unit_price=Decimal("4.00")),
        rating_seam.Tier(upper=Decimal("15"), unit_price=Decimal("6.50")),
        rating_seam.Tier(upper=None, unit_price=Decimal("8.00")),
    ),
)
GT17_SEWER = rating_seam.TariffConfig(
    service="sewer",
    model="percent_of_service",
    billed_unit="kgal",
    percent=Decimal("90"),
    basis_service="water",
    percent_basis="usage",
    unit_price=Decimal("5.0000"),
)


@pytest.mark.parametrize(
    ("gt", "kgal", "expected"),
    [
        ("GT-17 (WE-1)", Decimal("8"), Decimal("36.00")),
        ("GT-20 (WE-4)", Decimal("12"), Decimal("54.00")),
        ("GT-25 (WE-9)", Decimal("6"), Decimal("27.00")),
        ("GT-26 (WE-10)", Decimal("6"), Decimal("27.00")),
    ],
)
def test_cr130_the_four_re_signed_sewer_figures_do_not_move(gt, kgal, expected):
    """❄️ RE-SIGNED 2026-09-08 under HUMAN-GUIDE §6. **THIS CHANGE IS ADDITIVE.**

    ⚠ **`10-scripts/03-golden-verify.py` CANNOT GUARD THESE AGAINST AN ENGINE
    DRIFT** — it recomputes B4/B5's own figures from fixtures and imports no
    application code, so it goes red when a document contradicts itself and
    never when the engine moves (CLAUDE.md, `DEF-2846`). This runs the engine.
    """
    priced = bill(
        (
            (GT17_WATER, rating_seam.Quantity(amount=kgal, unit="kgal")),
            (GT17_SEWER, rating_seam.Quantity(amount=kgal, unit="kgal")),
        )
    )
    assert _sewer_line(priced).amount == expected, gt


def test_cr130_the_charge_basis_would_have_moved_gt17_and_does_not():
    """**WHAT THE WRONG BASIS COSTS, MEASURED ON THE SIGNED BILL ITSELF.**

    GT-17's water usage lines are $20.00 + $19.50 = $39.50, so 90% of the
    MONEY is **$35.55** where 90% of the VOLUME is **$36.00**. Forty-five cents
    a month, on a document that foots against itself either way — which is
    precisely why `rating/0043` writes `'usage'` onto every existing row by
    name instead of letting a default answer for them.
    """
    moved = bill(
        (
            (GT17_WATER, rating_seam.Quantity(amount=Decimal("8"), unit="kgal")),
            (
                rating_seam.TariffConfig(
                    service="sewer",
                    model="percent_of_service",
                    billed_unit="kgal",
                    percent=Decimal("90"),
                    basis_service="water",
                    percent_basis="charge",
                ),
                rating_seam.Quantity(amount=Decimal("8"), unit="kgal"),
            ),
        )
    )
    assert _sewer_line(moved).amount == Decimal("35.55")


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE LADDER, AND THE DISCARD IT REPLACES
# ══════════════════════════════════════════════════════════════════════════


def test_cr130_the_derived_quantity_walks_the_ladder_block_by_block():
    """*"80 X { flat rate or **tiered rate** }"*.

    100 gallons of water at 80% is 80 gallons of sewer. Through a ladder of
    0–30 at $1.00 · 30–60 at $2.00 · 60+ at $3.00 that is
    **30.00 + 60.00 + 60.00 = $150.00** on three lines, not 80 x $1.00 = $80.00
    on one — which is exactly what `pricing_inputs`' `tiers[0]` read would have
    produced, with no error anywhere.
    """
    ladder = _sewer(
        percent_basis="usage",
        tiers=(
            rating_seam.Tier(upper=Decimal("30"), unit_price=Decimal("1.00")),
            rating_seam.Tier(upper=Decimal("60"), unit_price=Decimal("2.00")),
            rating_seam.Tier(upper=None, unit_price=Decimal("3.00")),
        ),
    )
    priced = bill(((WATER_100, HUNDRED_GAL), (ladder, HUNDRED_GAL)))
    lines = _sewer_lines(priced)
    assert [line.amount for line in lines] == [
        Decimal("30.00"),
        Decimal("60.00"),
        Decimal("60.00"),
    ]
    assert sum(line.amount for line in lines) == Decimal("150.00")
    assert [line.quantity for line in lines] == [
        Decimal("30"),
        Decimal("30"),
        Decimal("20.0"),
    ]
    # EVERY rung says where the quantity came from. A customer reading three
    # sewer lines and no sewer meter has no other way to see it.
    for line in lines:
        assert "80.00% of water volume" in line.description


def test_cr130_pricing_inputs_no_longer_discards_the_blocks_after_the_first():
    """**THE MONEY FIX, AT THE PROJECTION.** Five blocks in, five blocks out.

    ⚠ **PROVED IN BOTH DIRECTIONS.** The one-block case must still publish
    `unit_price` and an EMPTY tier list — that is what keeps ❄️ GT-17 at
    $36.00, because `unit_price` is the field `flat` uses and the one
    `gather._tariff_config_for` already copies.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        one = _stored_sewer(tenant, blocks=[(None, "5.0000")])
        many = _stored_sewer(
            tenant,
            blocks=[
                ("10", "1.0000"),
                ("20", "2.0000"),
                ("30", "3.0000"),
                ("40", "4.0000"),
                (None, "5.0000"),
            ],
        )
        one_inputs = selectors.pricing_inputs_for_version(one, one.effective_from)
        many_inputs = selectors.pricing_inputs_for_version(many, many.effective_from)

    assert one_inputs["unit_price"] == Decimal("5.000000")
    assert one_inputs["tiers"] == []

    assert many_inputs["unit_price"] is None
    assert [tier["unit_price"] for tier in many_inputs["tiers"]] == [
        Decimal("1.000000"),
        Decimal("2.000000"),
        Decimal("3.000000"),
        Decimal("4.000000"),
        Decimal("5.000000"),
    ]
    # The open-ended top block is served as `upper=None`, never as zero.
    assert many_inputs["tiers"][-1]["upper"] is None


def test_cr130_the_screen_gets_the_basis_back_when_it_reopens_a_schedule():
    """**THE READ HALF, WHICH IS THE ONE THAT GOES MISSING** (hard-won law 2).

    `selectors.version_structure` is what the wizard reloads a saved schedule
    from. Without `percent_basis` on it, a `charge` schedule reopens drawn as a
    `usage` one and a clerk who presses save has changed the basis without
    being told — with `tsc` and every test green, because nothing is broken: a
    field is simply absent.

    Both values are asserted, because a projection that always answers `usage`
    would satisfy a one-sided test and be exactly the bug.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        used = selectors.version_structure(_stored_sewer(tenant, blocks=[(None, "5.0000")]))
        charged = selectors.version_structure(_stored_sewer(tenant, blocks=[], basis="charge"))
    assert used["percent_basis"] == "usage"
    assert used["basis_service"] == "water"
    assert charged["percent_basis"] == "charge"


def test_cr130_the_charge_basis_publishes_neither_a_price_nor_a_ladder():
    """A percentage of money has no rate of its own, and the projection says so
    by publishing nothing rather than by publishing an empty something."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        version = _stored_sewer(tenant, blocks=[], basis="charge")
        inputs = selectors.pricing_inputs_for_version(version, version.effective_from)
    assert inputs["percent_basis"] == "charge"
    assert inputs["unit_price"] is None
    assert inputs["tiers"] == []


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE REFUSALS — ONE PER BASIS, AND NEITHER EVER ANSWERS $0.00
# ══════════════════════════════════════════════════════════════════════════


def test_cr130_a_missing_basis_refuses_rather_than_defaulting_to_usage():
    """**THE HOP THAT MATTERS.** Every stored row names a basis, so a None here
    is a seam that dropped the column — and on GT-17's bill the two answers are
    $36.00 and $35.55, neither of which announces itself as wrong.
    """
    with pytest.raises(errors.TariffConfigError) as excinfo:
        bill(((WATER_100, HUNDRED_GAL), (_sewer(unit_price=Decimal("0.5000")), HUNDRED_GAL)))
    assert "percentage OF WHAT" in str(excinfo.value)


def test_cr130_an_unknown_basis_refuses_by_name():
    """There is no third basis. A value nobody recognises is refused, never
    read as the nearest one."""
    with pytest.raises(errors.TariffConfigError) as excinfo:
        bill(
            (
                (WATER_100, HUNDRED_GAL),
                (
                    _sewer(
                        percent_basis="volume",
                        unit_price=Decimal("0.5"),
                    ),
                    HUNDRED_GAL,
                ),
            )
        )
    assert "'volume'" in str(excinfo.value)


def test_cr130_a_rate_on_the_charge_basis_is_refused_by_name_not_ignored():
    """A price per gallon on a percentage of MONEY is a number the tenant
    states, the screen shows, and the engine would silently drop."""
    for extra in (
        {"unit_price": Decimal("0.5000")},
        {"tiers": (rating_seam.Tier(upper=None, unit_price=Decimal("0.5000")),)},
    ):
        with pytest.raises(errors.TariffConfigError) as excinfo:
            bill(
                (
                    (WATER_100, HUNDRED_GAL),
                    (_sewer(percent_basis="charge", **extra), HUNDRED_GAL),
                )
            )
        assert "REFUSED rather than silently dropped" in str(excinfo.value)


def test_cr130_the_charge_basis_refuses_when_the_basis_service_is_absent():
    """80% of an unavailable number is not $0.00 — CLAUDE.md's seam rule, on
    the basis that did not exist when that rule was written for this file."""
    with pytest.raises(errors.BasisUnavailable) as excinfo:
        bill(((_sewer(percent_basis="charge"), HUNDRED_GAL),))
    message = str(excinfo.value)
    assert "water" in message
    assert "0.00" in message  # the refusal SAYS what it declined to do


def test_cr130_the_charge_basis_refuses_a_basis_service_held_base_only():
    """A vacation hold (BR-BIL-028) leaves the water base billing and no usage
    line at all. There is no usage charge to take a percentage of, so the sewer
    line refuses instead of quietly becoming free."""
    with pytest.raises(errors.BasisUnavailable):
        engine.price_bill(
            services=((_sewer(percent_basis="charge"), HUNDRED_GAL),),
            base_only_services=(WATER_100,),
            period=FULL_MONTH,
            account=ACCOUNT,
        )


def test_cr130_a_metered_zero_is_a_real_basis_on_both_bases():
    """**THE OTHER SIDE OF THE REFUSAL, AND IT MUST NOT REFUSE.** A customer who
    used no water owes no sewer: 80% x $0.00 = $0.00 and 80% x 0 gal = 0 gal
    are the right answers, and are a different fact from *"water was never
    billed"*. The engine's `not base_only` gate is what keeps them apart.
    """
    nothing = rating_seam.Quantity(amount=Decimal("0"), unit="gal")
    charged = bill(((WATER_100, nothing), (_sewer(percent_basis="charge"), nothing)))
    assert _sewer_line(charged).amount == Decimal("0.00")

    used = bill(
        (
            (WATER_100, nothing),
            (_sewer(percent_basis="usage", unit_price=Decimal("0.5000")), nothing),
        )
    )
    assert _sewer_line(used).amount == Decimal("0.00")


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE STORED HALF — THE COLUMN, ITS BACKFILL AND ITS VALIDATION
# ══════════════════════════════════════════════════════════════════════════


def _stored_sewer(tenant, *, blocks, basis="usage"):
    """A sewer version written straight through the ORM.

    Deliberately NOT through `create_rate_schedule`, for the reason
    `test_cr081_sewer_volume_basis._sewer_version` gives: that path also drags
    in `BR-RAT-088`'s base-charge-code gate, which is a different rule with its
    own tests.
    """
    water = tenancy_models.Service.objects.get(code="water")
    sewer = tenancy_models.Service.objects.get(code="sewer")
    tariff = models.Tariff.objects.create(
        tenant=tenant, name=f"CR-130 sewer {basis} {len(blocks)}", service=sewer
    )
    version = models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model=services.MODEL_PERCENT,
        currency="USD",
        uom=fixture.WATER_UOM,
        percent=Decimal("90"),
        basis_service=water,
        percent_basis=basis,
        effective_from="2026-06-01",
    )
    lower = Decimal("0")
    for seq, (upper, price) in enumerate(blocks, start=1):
        models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=seq,
            from_qty=lower,
            to_qty=None if upper is None else Decimal(upper),
            unit_price=Decimal(price),
        )
        lower = Decimal(upper or 0)
    return version


def test_cr130_the_seeded_sewer_structure_validates_and_stores_the_basis():
    """The seeder's own sewer structure, pushed through the REAL validator.

    ⚠ **THIS TEST ASKED THE WRONG QUESTION FIRST AND ITS OWN GUARD CAUGHT IT.**
    It read every `percent_of_service` version on a provisioned tenant and
    asserted they all said `usage`. `provisioned_tenant()` provisions and does
    NOT plant the sample estate — that is a queued job — so the set was EMPTY,
    and `all([])` would have passed over nothing at all. The guard
    (`assert rows, "...this assertion is vacuous"`) failed instead: hard-won
    law 7's *ask what would make this check pass wrongly*, answered by the
    check rather than by its author. A second draft skipped when the estate
    sells no sewer, which on this fixture is ALWAYS — a check that cannot fail
    is worse than none.

    So it asserts the thing that is true of every tenant: **the three constants
    the seeder writes are accepted by `_validate_structure` and come back out
    as the basis, the factor and one unbounded rate block.** No estate, no
    queued job, nothing to skip over.

    ⚠ The REACH of `rating/0043`'s backfill over rows that already exist is a
    PostgreSQL question — SQLite has no row-level security to hide a row from
    it — and that migration's own docstring says so rather than letting a green
    suite stand in for it.
    """
    assert fixture.SEWER_PERCENT_BASIS == "usage"
    tenant, _ = provisioned_tenant()
    fe: list = []
    with tenant_ctx(tenant):
        structure = services._validate_structure(
            services.MODEL_PERCENT,
            {
                "service": "sewer",
                "structure": {
                    "percent": fixture.SEWER_PERCENT_OF_WATER,
                    "basis_service": "water",
                    "percent_basis": fixture.SEWER_PERCENT_BASIS,
                    "unit_price": fixture.SEWER_RATE_PER_UNIT,
                },
            },
            fe,
            service_code="sewer",
        )
    assert fe == [], fe
    assert structure["percent_basis"] == "usage"
    assert structure["percent"] == Decimal(fixture.SEWER_PERCENT_OF_WATER)
    # BR-RAT-032 — one price is ONE 0→∞ block, which is how ❄️ GT-17 reaches
    # the engine as `unit_price` rather than as a ladder.
    (block,) = structure["tiers"]
    assert (block["from_qty"], block["to_qty"]) == (Decimal("0"), None)
    assert block["unit_price"] == Decimal(fixture.SEWER_RATE_PER_UNIT)


def test_cr130_the_column_is_never_null_on_a_written_version():
    """The model's default and `_write_version`'s fallback, together: a FLAT
    schedule writes no percent structure at all and must still land a lawful
    row, because the column is NOT NULL."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        water = tenancy_models.Service.objects.get(code="water")
        tariff = models.Tariff.objects.create(tenant=tenant, name="CR-130 flat", service=water)
        version = models.TariffVersion.objects.create(
            tenant=tenant, tariff=tariff, model="flat", currency="USD", uom="kgal"
        )
    assert version.percent_basis == "usage"


def test_cr130_the_charge_basis_is_complete_without_a_rate():
    """`BR-RAT-031`'s activation gate, on the basis that has no rate by design.

    ⚠ **PROVED IN BOTH DIRECTIONS.** A gate that only ever answers `None` is
    indistinguishable from a gate nobody wired up, so the USAGE basis with no
    rate is asserted to still be incomplete in the same test.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assert services._missing_structure(_stored_sewer(tenant, blocks=[], basis="charge")) is None
        assert (
            services._missing_structure(_stored_sewer(tenant, blocks=[], basis="usage")) == "rate"
        )


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE DERIVED "BASED ON" LIST — NO SERVICE CODE IN ANY CONDITION
# ══════════════════════════════════════════════════════════════════════════


def test_cr130_the_basis_list_is_derived_from_what_the_tenant_switched_on():
    """PO ruling 2026-09-22: *"dont hard code anything - use logic to derive it
    so that it is flexible and handle any scenario."*

    The `charge` list is every enabled service but this one. The `usage` list
    narrows it to the ones the utility declares it METERS
    (`tenant_services.billing_basis`, `BR-TEN-1180`).

    ⚠ **THE NARROWING IS PROVED BY CHANGING A DECLARATION, NOT BY READING THE
    FIXTURE.** A first draft asserted `usage < charge` on the seeded tenant and
    failed: both of its enabled services are metered, so the two lists are
    EQUAL and a proper-subset assertion was simply wrong. Worse, had the
    fixture happened to enable one non-metered service the same assertion would
    have passed while proving nothing about WHICH service was dropped. So this
    flips one service's declaration and watches it leave one list and stay on
    the other — which no hard-coded pair could reproduce, and which is the
    ruling itself.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        enabled = list(selectors.seams.enabled_service_codes())
        assert len(enabled) >= 2, f"need two enabled services to narrow between: {enabled}"
        subject, victim = enabled[0], enabled[1]

        before_usage = {row["code"] for row in selectors.percent_basis_options(subject, "usage")}
        before_charge = {row["code"] for row in selectors.percent_basis_options(subject, "charge")}
        assert subject not in before_usage  # never a percentage of itself
        assert subject not in before_charge
        assert victim in before_usage

        # The utility declares that it does NOT read a register for `victim`.
        tenancy_models.TenantService.objects.filter(tenant=tenant, service__code=victim).update(
            billing_basis=tenancy_models.BILLING_BASIS_SHARE
        )

        after_usage = {row["code"] for row in selectors.percent_basis_options(subject, "usage")}
        after_charge = {row["code"] for row in selectors.percent_basis_options(subject, "charge")}

    # It leaves the USAGE list — there is no quantity to take a percentage of.
    assert victim not in after_usage
    assert after_usage == before_usage - {victim}
    # And it stays on the CHARGE list — it can still put money on a bill.
    assert victim in after_charge
    assert after_charge == before_charge


def test_cr130_an_unknown_basis_offers_nothing_rather_than_guessing():
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assert selectors.percent_basis_options("sewer", "volume") == []
        # No basis at all answers the USAGE list, which is what every stored
        # schedule in the product is on.
        assert selectors.percent_basis_options("sewer") == selectors.percent_basis_options(
            "sewer", "usage"
        )


def test_cr130_no_service_code_appears_in_the_derivation():
    """**THE RULING, ASSERTED AGAINST THE SOURCE RATHER THAN AGAINST THE
    OUTPUT.** A list that happens to come out right today can still be built
    from a hard-coded pair, and the next service the platform adds is when
    anybody finds out (hard-won law 2: *"an eleventh service does NOT appear on
    screen on its own and it fails SILENTLY"*).

    So this reads the function's own source and refuses a service code in it.
    The eleven names come from the platform catalogue at run time, so the test
    cannot itself hard-code the list it forbids.
    """
    import inspect

    source = inspect.getsource(selectors.percent_basis_options)
    body = source.split('"""')[2]  # everything after the docstring
    codes = list(tenancy_models.Service.objects.filter(active=True).values_list("code", flat=True))
    assert codes, "the platform catalogue is empty; this assertion would be vacuous"
    for code in codes:
        assert f'"{code}"' not in body and f"'{code}'" not in body, code


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-130-BRC07 §3 (the wire contract) + the PO's two worked figures, verbatim
# generated: 2026-09-22 by the CR-130-BRC07 rating-backend lane (wave A)
# checklist: A✔ B=deferred(no-frontend-half — wave B) C✔ D✔ E=deferred(see B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every case here was PROVED RED first: the two PO figures against the pre-change plugin, the ladder against `tiers[0]`, and each refusal against a plugin with that branch removed
# exceptions: the CHARGE basis has NO ❄️ frozen golden test behind it — `$80.00` is the PO's own figure and is asserted here, but it is not B5-signed. The review-ledger row for this change puts it to them in plain English with the number. · `test_cr130_no_service_code_appears_in_the_derivation` reads a function's SOURCE, which is unusual and is deliberate: the ruling is about how the answer is computed, and an output-only assertion cannot see a hard-coded pair that is currently correct.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
