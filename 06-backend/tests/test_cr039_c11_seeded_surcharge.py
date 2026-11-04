# ── Trace ──────────────────────────────────────────────
# Change:  CR-039 wave C task 11 — *"seed it so the surcharge path is
#          exercised"*
# Defect:  DEF-515 (nothing writes `rate_plans.outside_city_factor`) ·
#          DEF-517 (nothing writes `premises.inside_city_limits`) ·
#          DEF-466 (the multiplier that could never be anything but 1.0)
# Rules:   BR-RAT-101 (the flag) · BR-RAT-102 (the two gates and the factor) ·
#          BR-RAT-015 ❄️ (sewer is 40% of the water usage charge)
# Question: OQ-424 (does the outside-city multiplier flow into the
#          percent-of-water sewer charge?)
# ───────────────────────────────────────────────────────
"""The seeded estate EXERCISES the surcharge — both gates, on real rows.

⚠ **PROVED RED FIRST, TWICE, AND THE SECOND ONE IS THE ONE THAT MATTERS (2d).**

**Sabotage 1 — both seeders and the fixture reverted to `0899de8`:** 4 failed,
1 passed. The load-bearing line, verbatim:

    >   assert rows.count(None) == 0
    E   assert 44 == 0
    E    +  where 44 = [None, None, None, None, None, None, ...].count(None)

Forty-four seeded premises, every one of them holding *nobody recorded it* —
`DEF-517` printed as a number.

**Sabotage 2 — the FLAGS seeded and only `apps/rating/sample_data.py` reverted,
so the premises say where they are and the plan states no factor:** 2 failed,
3 passed, and it fails in dollars rather than in an `AttributeError`:

    E   AssertionError: CR-039 C11: 161 Silver Creek Rd bills water usage
    E   109.000000 and BR-RAT-102 says 163.500 — 109.00 x 1.5, r10's own
    E   multiplier
    E   assert Decimal('109.000000') == Decimal('163.500')

    E   AssertionError: assert None == Decimal('1.5')

**That is the whole of BR-RAT-102's two gates in one run.** Gate 2 open and gate
1 shut prices at exactly `1`, silently, on a real invoice line — which is
`DEF-466`'s original finding (*"a multiplier that defaults to the identity is
invisible when it is dead"*) reproduced deliberately so this file can be trusted
green.

WHY A SEEDED-DATA TEST AND NOT ANOTHER UNIT ONE
-----------------------------------------------
`tests/test_def_484_size_and_jurisdiction.py` already proves the arithmetic, and
proves it on data it writes into the two columns THROUGH THE ORM — which is
precisely the untested-sourcing shape DEF-466 was filed for: *"the engine's own
tests pass a tariff carrying the factor directly, so the arithmetic is proven
and the SOURCING is untested."* This file asserts the sourcing: that the tenant
a utility is actually handed carries both facts, written by the product's own
write paths, and that a real bill moves because of them.
"""

from decimal import Decimal

import pytest

from apps.metering import models as metering_models
from apps.metering import sample_data as metering_sample
from apps.rating import sample_data as rating_sample
from apps.rating import selectors as rating_selectors
from core import sample_fixture as fixture

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    seed_physical_series,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def silver_creek(growth_plan, identity_seam):  # noqa: F405 — W0 helper fixtures
    """A tenant that sells WATER · SEWER · TRASH — the estate the fixture
    describes, and the only shape on which the surcharge can be priced at all.

    ⚠ `apps/rating/sample_data` seeds schedules for water, sewer and trash and
    for NOTHING ELSE — `core/sample_fixture` says so in its own words: *"there
    is no signed figure for an electric or gas tariff … so a non-water estate's
    reads are consumption with a unit and no price."* CR-039 wave A made the
    ESTATE service-shaped; it did not make the MONEY service-shaped, because
    the money is not ours to invent. So a surcharge can only be exercised where
    a priced plan exists, and that is a water tenant. Stated here rather than
    discovered by a later lane wondering why an electric demo shows no
    surcharge.
    """
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Silver Creek Water",
            subdomain="silvercreekwater",
            services=["water", "sewer", "trash"],
        )
    )
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def seeded(silver_creek):
    """Rating then metering, in the orchestrator's own order — the plans have to
    exist before a unit can carry one (BR-MET-040). Through each module's REAL
    seam, so this file cannot drift from what a tenant receives."""
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        rating_sample.seed_sample_records(actor)
        metering_sample.seed_sample_records(actor)
    return silver_creek, actor


@pytest.fixture()
def billed(seeded):
    """The whole plant, in `apps.tenancy.sample_data.SAMPLE_MODULES` order,
    down to issued bills. Slow on purpose: the figure this file exists to show
    is on an INVOICE LINE, and every shortcut to it would be a second
    implementation of the bill run."""
    from apps.assets import sample_data as assets_sample
    from apps.billing import sample_data as billing_sample
    from apps.customers import sample_data as customers_sample

    tenant, actor = seeded
    with tenant_ctx(tenant):
        assets_sample.seed_sample_records(actor)
        customers_sample.seed_sample_records(actor)
        metering_sample.seed_sample_reads(actor)
        billing_sample.seed_sample_records(actor)
    return tenant, actor


def _water_usage_inside(unit_index: int, period_key: str) -> Decimal:
    """What this unit's water USAGE bills INSIDE the city, from the fixture's
    own ladder — never a number typed into this file.

    `WATER_TIERS` is `[W] §1`'s inclining ladder (`0-5 @ 4.00`, `5-15 @ 6.50`,
    `15+ @ 8.00`) and `consumption()` is the fixture's own reading, so this is
    the figure the product has always billed at this address.
    """
    remaining = Decimal(fixture.consumption(unit_index, period_key, service="water"))
    total = Decimal("0")
    for from_qty, to_qty, price in fixture.WATER_TIERS:
        lower = Decimal(from_qty)
        upper = None if to_qty is None else Decimal(to_qty)
        band = remaining - lower if upper is None else min(remaining, upper) - lower
        if band <= 0:
            continue
        total += band * Decimal(price)
    return total


# ── GATE 2 · the premises states which side of the line it is on ───────────


def test_cr039_c11__the_seeded_estate_states_a_jurisdiction_on_every_premises(seeded):
    """⚠ **ZERO UNRECORDED, AND THAT IS THE LOAD-BEARING HALF.**

    BR-RAT-102's fourth case refuses an account whose premises flag is `None`
    when its plan states a factor. The residential plan now states one, so a
    single unstated address is a named exception row on the demo's ready-to-run
    billing month instead of a bill.
    """
    tenant, _ = seeded
    # ⚠ NARROWED TO `premises_plan()`'s OWN ADDRESSES. `seed_sample_records`
    # also plants the CR-030 onboarding estate and the CR-028 register shapes,
    # which are separate fixtures with their own counts; asserting over every
    # `is_sample` row would make this test fail the day another block grows.
    addresses = [entry["address_line"] for entry in fixture.premises_plan()]
    with tenant_ctx(tenant):
        rows = list(
            metering_models.Premises.objects.filter(
                tenant_id=tenant.id, address_line__in=addresses
            ).values_list("inside_city_limits", flat=True)
        )
    assert len(rows) == fixture.PREMISES_COUNT
    assert rows.count(None) == 0
    assert rows.count(False) == len(fixture.OUTSIDE_CITY_PREMISES_INDEXES)
    assert rows.count(True) == fixture.PREMISES_COUNT - len(fixture.OUTSIDE_CITY_PREMISES_INDEXES)


def test_cr039_c11__the_two_outside_premises_are_the_ones_the_fixture_names(seeded):
    """Named by ADDRESS, so a reordering of `premises_plan()` that silently
    moved the surcharge to two different customers fails here."""
    tenant, _ = seeded
    plan = fixture.premises_plan()
    expected = sorted(plan[i]["address_line"] for i in fixture.OUTSIDE_CITY_PREMISES_INDEXES)
    with tenant_ctx(tenant):
        actual = sorted(
            metering_models.Premises.objects.filter(
                tenant_id=tenant.id, inside_city_limits=False
            ).values_list("address_line", flat=True)
        )
    assert actual == expected


# ── GATE 1 · the plan states the factor ────────────────────────────────────


def test_cr039_c11__the_residential_plan_states_r10s_factor(seeded):
    """r10, verbatim: *"Premises outside city limits multiply base and variable
    by 1.5 — set on the premise record."* Written through `create_plan`, not
    through the ORM: the seeder may not reach past the validated write path on
    a money column (🔒 sensitive path)."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        pricing = rating_selectors.plan_jurisdiction_pricing(rating_sample.residential_plan_id())
    assert pricing["outside_city_factor"] == Decimal(fixture.OUTSIDE_CITY_FACTOR)
    assert set(pricing["exempt_services"]) == set(fixture.OUTSIDE_CITY_EXEMPT_SERVICES)


def test_cr039_c11__the_commercial_plan_states_none__so_it_never_asks_the_premises(seeded):
    """BR-RAT-102's first gate, demonstrated rather than described: *"a plan
    stating NO factor never consults the premises at all"*. A fixture where
    every plan surcharges cannot show a utility what protects them."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        pricing = rating_selectors.plan_jurisdiction_pricing(rating_sample.commercial_plan_id())
    assert pricing["outside_city_factor"] is None


# ── THE WORKED FIGURE · both gates open and a real bill moves ──────────────


def test_cr039_c11__the_outside_city_bill_carries_r10s_multiplier(billed):
    """⚠ **THIS IS THE ASSERTION CR-039 TASK 11 EXISTS FOR.**

    A jurisdiction column with a value in it and nothing pricing off it is the
    built-not-wired shape one level down. So this reads an ISSUED INVOICE at one
    of the two outside-city addresses and requires the two lines BR-RAT-102
    moves — the base and the usage — to be `×1.5` the figures the same account
    billed before the factor existed.

    **The worked figure, in full**, for the June period at the first address in
    `OUTSIDE_CITY_PREMISES_INDEXES`:

        water usage, inside the city   `_water_usage_inside(30, "june")`
        water base,  inside the city   `fixture.WATER_BASE`  ($8.00)
        × 1.5 (r10, outside the city)  both lines
        unit                           kgal on the usage, a flat monthly
                                       amount on the base (CLAUDE.md rule 3)

    …and the exact dollars are printed by the assertion messages below rather
    than frozen into a literal here, because a literal in a test is a second
    place for the ladder to live (DEF-154's shape).
    """
    from apps.billing import models as billing_models
    from apps.customers import models as customers_models

    tenant, _ = billed
    index = fixture.OUTSIDE_CITY_PREMISES_INDEXES[0]
    address = fixture.premises_plan()[index]["address_line"]
    factor = Decimal(fixture.OUTSIDE_CITY_FACTOR)

    with tenant_ctx(tenant):
        premises = metering_models.Premises.objects.get(tenant_id=tenant.id, address_line=address)
        unit = metering_models.Unit.objects.filter(tenant_id=tenant.id, premises=premises).first()
        account = customers_models.Account.objects.filter(
            tenant_id=tenant.id, unit_id=unit.id
        ).first()
        invoice = (
            billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=account.id)
            .order_by("period_start")
            .first()
        )
        assert invoice is not None, (
            f"CR-039 C11: {address} is outside the city on a plan stating a factor and "
            "has no bill at all — BR-RAT-102's refusal, not its surcharge"
        )
        lines = [
            (row.service.code if row.service_id else None, row.kind, Decimal(row.amount))
            for row in billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, invoice_id=invoice.id
            ).select_related("service")
        ]

    period_key = fixture.PERIODS[0]["key"]
    water = [line for line in lines if line[0] == "water"]
    base = sum((amount for _code, kind, amount in water if kind == "base"), Decimal("0"))
    usage = sum((amount for _code, kind, amount in water if kind == "usage"), Decimal("0"))

    # ⚠ THE PREMISES ORDINAL **IS** THE UNIT INDEX here, and only here: the
    # first 36 rows of `premises_plan()` are single-family with one unit each,
    # which is exactly why `OUTSIDE_CITY_PREMISES_INDEXES` was chosen inside
    # that run. Anywhere past row 36 the two numbers diverge.
    inside_usage = _water_usage_inside(index, period_key)
    expected_usage = inside_usage * factor
    expected_base = Decimal(fixture.WATER_BASE) * factor
    assert usage == expected_usage, (
        f"CR-039 C11: {address} bills water usage {usage} and BR-RAT-102 says "
        f"{expected_usage} — {inside_usage} x {factor}, r10's own multiplier"
    )
    assert base == expected_base, (
        f"CR-039 C11: {address} bills a water base of {base} and BR-RAT-102 says "
        f"{expected_base} — {fixture.WATER_BASE} x {factor}. The PO's correction of "
        "2026-08-19 is that the factor moves the BASE as well as the rates"
    )

    # ⚠ **OQ-424 — WHAT THE SEWER LINE DOES, PINNED AND NOT RULED.**
    #
    # `sewer` is on `OUTSIDE_CITY_EXEMPT_SERVICES`, so R5 hands it a factor of
    # `1` — §A4 S2's *"BASE-S $8.00 (flat everywhere — the multiplier does NOT
    # touch sewer)"*. But Silver Creek's sewer has NO base: BR-RAT-015 ❄️
    # prices it as 40% of the WATER USAGE CHARGE, and the water usage charge at
    # this address is now the SURCHARGED one. So the exemption reaches a `$0.00`
    # base and the sewer line rises anyway, by composition.
    #
    # **Neither document is wrong and they have never met before.** §A4's estate
    # has a sewer BASE and no percent-of-water sewer; Silver Creek has the
    # reverse. Whether *"flat everywhere"* was meant to cover a derived charge
    # is the PO's to say — `OQ-424`. NOT stubbed with `NotImplementedError`,
    # because no new code makes this happen: it is what two signed rules already
    # compose to, and a stub would break a bill to ask a question. The figure is
    # asserted here so the day the PO rules, this is what goes red.
    sewer_usage = sum(
        (amount for code, kind, amount in lines if code == "sewer" and kind == "usage"),
        Decimal("0"),
    )
    sewer_share = Decimal(fixture.SEWER_PERCENT_OF_WATER) / Decimal("100")
    expected_sewer = expected_usage * sewer_share
    assert sewer_usage == expected_sewer, (
        f"CR-039 C11 / OQ-424: {address} bills sewer usage {sewer_usage}. "
        f"BR-RAT-015 is 40% of the water usage charge and that charge is now "
        f"{expected_usage}, so the composed answer is {expected_sewer}"
    )


# ── THE GUARD AGAINST WHAT THIS CHANGE COULD HAVE BROKEN ───────────────────


def test_cr039_c11__no_seeded_premises_on_a_SURCHARGING_plan_is_left_unstated(billed):
    """⚠ **THE ONE THIS CHANGE COULD HAVE BROKEN, AND IT WOULD HAVE BEEN
    SILENT.**

    Opening BR-RAT-102's first gate on the residential plan makes the SECOND
    gate live for every account on it — and `metering.seed_sample_records`
    plants more than `premises_plan()`'s 44. The CR-030 onboarding estate is
    the one that matters: `_cr030_plan_id`'s own docstring says its units carry
    **the residential plan**, and this lane just gave that plan a factor. A
    premises there with `inside_city_limits = None` refuses its account's bill
    by name (`premises_jurisdiction_unstated`), and BR-BIL-055 makes that ONE
    exception row rather than a failed run — so the demo would look healthy and
    quietly not bill some of its customers.

    This asserts the invariant directly, at the data level, so it holds however
    many blocks the seeder grows: **every premises whose units sit on a plan
    that states a factor has an ANSWER.** A premises on a factor-less plan may
    be `None` for ever, which is BR-RAT-102's first gate doing its job.
    """
    from apps.rating import models as rating_models

    tenant, _ = billed
    with tenant_ctx(tenant):
        surcharging = {
            str(pk)
            for pk in rating_models.RatePlan.objects.filter(tenant_id=tenant.id)
            .exclude(outside_city_factor__isnull=True)
            .exclude(outside_city_factor=Decimal("1"))
            .values_list("id", flat=True)
        }
        assert surcharging, (
            "CR-039 C11: no seeded plan states a factor, so this guard is vacuous — "
            "which is DEF-466's own shape and the reason it exists"
        )
        exposed = sorted(
            metering_models.Premises.objects.filter(
                tenant_id=tenant.id,
                inside_city_limits__isnull=True,
                unit__rate_plan_id__in=surcharging,
            )
            .distinct()
            .values_list("address_line", flat=True)
        )
    assert exposed == [], (
        "CR-039 C11: these seeded addresses sit on a plan that surcharges outside the "
        f"city and record no side of the line, so BR-RAT-102 refuses their bills: "
        f"{exposed}. Either state the flag where they are seeded, or take the factor off "
        "the plan their units carry — never leave the third state under an open gate."
    )
