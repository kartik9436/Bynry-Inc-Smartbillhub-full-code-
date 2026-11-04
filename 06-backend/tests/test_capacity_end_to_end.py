# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-014 (capacity charges) · US-RAT-012 (percent-of-service) ·
#           US-BIL-029 (the run's stages over an account)   Screens: S31.2, S21
# Rules:    BR-RAT-018/019/022 (capacity: tenant-defined unit + rate) ·
#           BR-RAT-029 (taxable LIKE BASE) · BR-RAT-090 (an UNMETERED service's
#           quantity is a COUNT of its assets on the unit) · BR-RAT-081 (the
#           utility declares a service metered or not) · BR-RAT-015 (sewer is a
#           percent of WATER usage-charge dollars) · BR-RAT-003 (round per line)
#           · CLAUDE.md hard rule 2 (money 4dp / percent 6dp / DISPLAY 2) and
#           hard rule 3 (a quantity always carries its unit)
# Golden:   GT-15 (solar 4 x $10.00 = $40.00) · GT-17 (= WE-1, the same $40.00
#           solar line inside the frozen taxable base) — B5 ❄️ / GT-15 PROPOSED
# Tests:    this file
# Impacts:  apps/rating/pricing/models/capacity.py 🔒 · apps/billing/gather.py ·
#           apps/billing/stages/measure_consumption.py
# ───────────────────────────────────────────────────────
"""CAPACITY PRICING, DRIVEN THROUGH THE WHOLE CHAIN AND NOT AT THE ENGINE.

WHY THIS FILE EXISTS, IN THE PRODUCT OWNER'S OWN WORDS (2026-09-01)
-------------------------------------------------------------------
    "we never tested capacility based- there are 3 types Meter based, %age of
     another service and capacity based. we tested Meter and %of service, never
     capacity based. hence ensure you create test scenarios, data and test
     billing logic work for all cases"

⚠ **`tests/test_us_rat_014_capacity.py` ALREADY TESTS CAPACITY AND IT IS NOT
WHAT THE PO ASKED FOR.** That file hands a hand-built `TariffConfig` straight to
`rating_seam.price_period` and asserts $40.00. It imports no model, opens no
transaction and touches no row — 16 cases in 0.16s. So it proves the ARITHMETIC
and it cannot see a single joint in front of it: whether a solar service point
exists, whether an asset stands on it, whether the count reaches the tariff,
whether the rate the database holds is the rate the engine gets.

**That gap is exactly DEF-2414's shape, one service over** — the trash lane found
the engine correct and the chain into it broken, and no unit test could see it.
So this file starts at a PROVISIONED TENANT and ends at priced lines, through
`gather_account` → `resolve_subscription` → `measure_consumption` →
`price_bill`, which is the sequence `runs.calculate_account` itself runs.

WHERE A CAPACITY QUANTITY ACTUALLY COMES FROM — THREE CANDIDATES, ONE WIRED
---------------------------------------------------------------------------
`capacity.py`'s own docstring names `account_capacities.units` as the source.
**That table has no DDL, no model and no migration** — `apps/customers/services`
records it: *"`account_capacities` has no DDL in any signed document"*. So the
source the plugin names cannot supply anything.

The source the PO RULED is a characteristic on the unit (BR-MET-104, 2026-08-24,
verbatim *"(a) a characteristic on the service point - we ahve it on unit"*).
`metering.connections.ServiceCharacteristic` is built — and its own reader says
in as many words: *"⚠ UNWIRED (hard-won law 2). Nothing in `rating` or `billing`
calls this yet"*. So that one is storage with no consumer.

**The one that works is BR-RAT-090's asset count**, and it is what this file
drives: the utility declares solar unmetered (`tenant_services.metered = False`),
metering stamps `asset_count` on the read row, and `measure_consumption` turns it
into a `Quantity` carrying the TARIFF's billed unit. Four PV assets on the unit
bill four panels. That is the chain a real utility has today, so it is the chain
the test uses; the other two are recorded above rather than worked around.

BOTH HALVES OF GT-15 NOW REACH A BILL (DEF-2408, 2026-09-01)
-------------------------------------------------------------
This file shipped on 2026-09-01 with solar billing `$40.00` and **battery
billing nothing at all**: `gather_account` raised `SizeClassNotRuled("OQ-561")`
on the first battery account, because `apps/tenancy/service_size_classes.py`
listed battery among the dimensions *nobody has ruled* — five days after the PO
had DISSOLVED that very question. Section 3 below now asserts GT-15's other
figure, **2 kW blocks × `$12.00` = `$24.00`**, on the identical chain.

**The mechanism deserves naming because it will recur:** the placeholder case
was written to go RED the day the ruling reached the code, and that is exactly
how the fix was found. Nothing in this repo re-reads a CLOSED open question
against the code that still cites it, so a dissolved `OQ` can go on refusing
bills indefinitely with every gate green — a test that asserts today's wrong
answer, and says in its own docstring that it must be deleted when it changes,
is the only thing that caught it.

WHAT THIS FILE DELIBERATELY DOES NOT DO
----------------------------------------
It does not choose a value for anything unruled. OQ-235's one-cent fork (two
prorated capacity lines rounding per line at $20.64 or once at $20.65) is left
where it is — OPEN, non-blocking, with per-line already what BR-RAT-003 requires
— and no case here puts two prorated capacity services on one bill. Battery's
bands were not invented either: `OQ-561` was answered by removing its subject
(*"multiplier replaces bands for capacity services"*), so battery is now `()` —
*ruled to have none* — and thermal STEAM, whose `OQ-560` was superseded rather
than dissolved, still raises.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather, rating_seam
from apps.billing.contracts import ServiceReading
from apps.billing.stages.measure_consumption import measure_consumption
from apps.billing.stages.resolve_subscription import resolve_subscription
from apps.customers import models as customer_models
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    brazosbend_payload,
    make_plan,
    make_premises,
    make_unit,
    provisioned_tenant,
    seeding_ctx,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
CYCLE_DAYS = 31

#: B5 GT-15's own inputs, verbatim: *"solar 4 units @ $10 + battery 2 @ $12 →
#: $40.00 + $24.00 lines"*. ⚠ **BOTH HALVES NOW REACH A BILL (`DEF-2408`,
#: 2026-09-01).** This comment read *"the battery half … does NOT reach a bill"*
#: until the PO's dissolution of `OQ-561` reached the code.
SOLAR_UNIT_LABEL = "panel"
SOLAR_RATE = Decimal("10.00")
SOLAR_PANELS = 4
GT15_SOLAR = Decimal("40.00")

BATTERY_UNIT_LABEL = "kW block"
BATTERY_RATE = Decimal("12.00")
BATTERY_BLOCKS = 2
GT15_BATTERY = Decimal("24.00")


# ══════════════════════════════════════════════════════════════════════════
# Fixture — a solar co-op on real rows, five modules deep
# ══════════════════════════════════════════════════════════════════════════
def _capacity_tenant(services=("solar",)):
    """A provisioned utility selling capacity-priced services and nothing else.

    Every step below is a step a real utility performs, in the order the product
    makes it perform them, and each one was found by the run REFUSING without it
    — which is the point of driving the chain rather than the engine.
    """
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Sunridge Energy Co-op",
            subdomain="sunridge",
            services=list(services),
        )
    )
    return tenant


def _declare_unmetered(actor, *codes):
    """BR-TEN-1180 — the utility says this service is priced by CAPACITY.

    Without it the service is `metered`, metering stamps no `asset_count`, and
    the capacity tariff reaches `measure_consumption` with no quantity at all.
    `metered` is the safe default (hard-won law 3) and this is a utility typing
    the unsafe option, once, on Settings > Services.

    ⚠ **IT WRITES `capacity`, NOT `metered=False` — BR-TEN-1180 (PO 2026-09-02)
    SUPERSEDES BR-RAT-081's boolean.** `capacity` is precisely what the false
    side of that boolean MEANT here: a COUNT of the unit's assets (BR-RAT-090).
    The third value, `share`, is the one this helper must never write — sewer is
    a percentage of the water usage charge and has no assets to count.
    """
    from apps.tenancy import services as tenancy_services

    for code in codes:
        tenancy_services.update_tenant_service(actor, code, {"billing_basis": "capacity"})


def _base_charge_code(tenant, code, amount=Decimal("0")):
    """BR-RAT-088's base charge code, which R4 refuses the account without.

    ⚠ **AN EXPLICIT ZERO, AND IT IS NOT THE SAME AS LEAVING IT BLANK.** The run
    says so itself when the row is missing: *"a blank base means THIS SIZE IS NOT
    SERVED, so the bill refuses rather than charging $0.00 for something the
    utility has never priced"*. A capacity service's whole price IS its capacity
    line, so the utility states a base of zero deliberately.
    """
    from apps.tenancy import models as tenancy_models

    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=f"BASE-{code[:3].upper()}",
        name=f"{code.title()} base service",
        charge_type="recurring",
        amount_rule="flat",
        amount=amount,
        service=tenancy_models.Service.objects.get(code=code),
        is_base=True,
    )


def _capacity_plan(tenant, specs):
    """A published plan whose schedules price each service as `capacity`.

    `specs` is `{service_code: (unit_label, rate)}`. The rate lands in
    `rating.CapacityRate`, the real table `pricing_inputs` reads, so the figure
    the engine prices with is the figure the DATABASE holds — which is the whole
    difference between this file and the engine test.
    """
    plan = make_plan(tenant, name="Sunridge Rooftop", services=tuple(specs))
    with seeding_ctx(tenant):
        rating_models.RatePlan.objects.filter(pk=plan.id).update(
            effective_from=date(2026, 1, 1), effective_to=None
        )
        for row in rating_selectors.plan_rate_schedules(plan.id):
            label, rate = specs[row["service_code"]]
            version = rating_models.TariffVersion.objects.create(
                tenant=tenant,
                tariff=row["tariff"],
                model="capacity",
                base_charge=None,
                # The tariff's BILLED UNIT is the tenant's own word, and it is
                # what `measure_consumption` puts on the counted quantity —
                # hard rule 3 held at the one place the tariff is in hand.
                uom=label,
                currency="USD",
                effective_from=date(2026, 1, 1),
            )
            rating_models.CapacityRate.objects.create(
                tenant=tenant,
                tariff_version=version,
                unit_label=label,
                rate_per_unit=rate,
                currency="USD",
            )
            rating_models.PlanService.objects.update_or_create(
                tenant=tenant,
                rate_plan_id=plan.id,
                service_id=row["service_id"],
                defaults={"base_charge": Decimal("0")},
            )
    return plan


def _unit_with_assets(actor, plan, counts):
    """One premises, one unit, and `counts[service]` assets standing on it.

    ⚠ **THE ASSET MUST CARRY THE SERVICE OR IT IS NOT COUNTED.**
    `assets.billable_asset_count` filters on
    `asset__service_point__service__code`, so a PV panel created without
    `"service": "solar"` sits on the unit, is in service, and counts ZERO. Both
    facts are individually correct and the bill is silently short.
    """
    from apps.assets import services as asset_services
    from apps.metering import services as metering_services

    codes = list(counts)
    premises = make_premises(actor, address_line="9 Mesa Vista", services_available=codes)
    unit = make_unit(actor, premises["id"], label="Unit A", services=codes)
    for code, count in counts.items():
        kind = "pv" if code == "solar" else "battery"
        for n in range(count):
            asset_services.create_asset(
                actor,
                {
                    "type": kind,
                    "asset_no": f"{kind.upper()}-{code[:2].upper()}{n + 1:03d}",
                    "service": code,
                    "unit_id": unit["id"],
                    "install_date": "2026-01-05",
                    "status": "active",
                },
            )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    return unit


def _account_on(tenant, unit, account_no="SUN-0001"):
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.first(),
    )


def _readings_for(unit):
    """Metering's own seam, carrying `asset_count` exactly as `runs._readings_for`
    does. A copy that dropped that key would pass every assertion below at zero
    lines and read as a green suite (hard-won law 2)."""
    from apps.metering import selectors as metering_selectors

    rows = metering_selectors.billing_reads_for_unit(
        unit["id"], period_start=PERIOD_START, period_end=PERIOD_END
    )
    return tuple(
        ServiceReading(
            service_code=row["service_code"],
            service_id=row["service_id"],
            consumption=(
                None
                if row.get("consumption") is None
                else rating_seam.Quantity(amount=row["consumption"], unit=row["unit"])
            ),
            estimated=bool(row.get("estimated")),
            absent_reason=row.get("absent_reason"),
            prior_read=row.get("prior_value"),
            current_read=row.get("current_value"),
            read_id=row.get("read_id"),
            asset_count=row.get("asset_count"),
        )
        for row in rows
    )


def _priced(account, unit):
    """THE PATH A CUSTOMER'S BILL TAKES — billing's own functions, its own
    arguments, in `runs.calculate_account`'s own order, minus the draft write."""
    data = gather.gather_account(
        account=account,
        service_date=PERIOD_END,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=CYCLE_DAYS,
        readings=_readings_for(unit),
    )
    subscription = resolve_subscription(data)
    usage = measure_consumption(subscription, data)
    return rating_seam.price_bill(
        services=tuple((service.tariff, service.consumption) for service in usage.measured),
        base_only_services=tuple(service.tariff for service in usage.unmeasured),
        period=subscription.period,
        account=rating_seam.AccountContext(
            currency=subscription.currency, tax_exempt=subscription.tax_exempt
        ),
        taxes=subscription.taxes,
        fees=subscription.fees,
    )


@pytest.fixture()
def solar_bill():
    """A solar co-op billing one rooftop — the whole chain, once, for the cases
    below to read."""
    tenant = _capacity_tenant(services=("solar",))
    with tenant_ctx(tenant):
        actor = staff_actor(tenant, email="ops@sunridge.test")
        _declare_unmetered(actor, "solar")
        plan = _capacity_plan(tenant, {"solar": (SOLAR_UNIT_LABEL, SOLAR_RATE)})
        with seeding_ctx(tenant):
            _base_charge_code(tenant, "solar")
        unit = _unit_with_assets(actor, plan, {"solar": SOLAR_PANELS})
        account = _account_on(tenant, unit)
        yield _priced(account, unit)


def _capacity_lines(bill, service):
    return [line for line in bill.lines if line.service == service and line.quantity is not None]


# ══════════════════════════════════════════════════════════════════════════
# 1 · CAPACITY REACHES A BILL — GT-15's $40.00, from the database
# ══════════════════════════════════════════════════════════════════════════
def test_capacity_prices_gt15s_forty_dollars_through_the_whole_chain(solar_bill):
    """GT-15's solar figure, produced from rows rather than from a fixture.

    Every number here travelled: `$10.00` came out of `rating.CapacityRate`, the
    `4` was COUNTED from four PV assets standing on the unit (BR-RAT-090), and
    `panel` is the tenant's own word for its unit, carried from the tariff onto
    the quantity by `measure_consumption`.
    """
    (solar,) = _capacity_lines(solar_bill, "solar")
    assert solar.amount == GT15_SOLAR
    assert solar.quantity == Decimal(SOLAR_PANELS)
    assert solar.unit == SOLAR_UNIT_LABEL


def test_capacity_is_taxable_like_base_on_the_real_chain(solar_bill):
    """BR-RAT-029 — and it is the KIND that puts it in B4.2's tax base, so a
    mis-seeded flag could not move it either way."""
    (solar,) = _capacity_lines(solar_bill, "solar")
    assert solar.kind == "base"
    assert solar.taxable
    assert solar_bill.taxable_subtotal == GT15_SOLAR


def test_the_count_is_observed_not_typed_so_a_fifth_panel_bills_fifty(solar_bill):
    """PO ruling 2026-08-20: the quantity is *"a COUNT OF ITS ASSETS ON THE
    UNIT"*, OBSERVED. This is the half a fixture-fed engine test cannot state:
    the bill moves because the estate moved, with nobody typing a quantity."""
    (solar,) = _capacity_lines(solar_bill, "solar")
    assert solar.quantity * SOLAR_RATE == solar.amount


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT THE CUSTOMER READS — DEF-968's defect, in the two models CR-043
#     could not see
# ══════════════════════════════════════════════════════════════════════════
def test_the_capacity_line_shows_its_rate_at_four_places_not_six(solar_bill):
    """A tariff RATE displays at exactly 4dp — PO 2026-08-27 closing OQ-620(a),
    verbatim: *"What does a tariff rate show? Four ($0.1420). A rate is not
    money and not a quantity - 4 decimal places"*.

    ⚠ **THIS IS DEF-968 AGAIN AND IT WAS INVISIBLE FOR THE SAME REASON.**
    CR-043 fixed `tiered.py` and `percent_of_service.py` — the two the PO had
    read on the live deployment — and `wording.py`'s own Impacts header still
    names only those two. `capacity.py` interpolates the rate RAW, so a
    `NUMERIC(18,6)` column reaches the customer as **`@ 10.000000`**, and the
    engine test asserting `"4 panel @ 10.00"` passes because its own fixture
    types `Decimal("10.00")` and never a stored one.

    ⚠ **THE ASSERTION IS AN EQUALITY AND THAT IS DELIBERATE (DEF-182's shape).**
    The first draft read `assert "4 panel @ 10.0000" in description` and PASSED
    on the broken sentence, because `10.0000` is a substring of `10.000000` — a
    check that cannot tell pass from fail is worse than no check, since it is
    trusted. The whole sentence is pinned instead.

    ⚠ AMENDED 2026-10-02 — PO: *"Show unit prices with up to 4 decimals and
    keep every total at 2."* The rate now prints `10.00` (it printed
    `10.0000`); still never the six stored places.
    """
    (solar,) = _capacity_lines(solar_bill, "solar")
    assert solar.description == "solar capacity \u2014 4 panel @ 10.00"


# ══════════════════════════════════════════════════════════════════════════
# 3 · BATTERY BILLS — GT-15's OTHER half, and the ruling has reached the code
# ══════════════════════════════════════════════════════════════════════════
def test_battery_bills_gt15s_twenty_four_dollars_through_the_whole_chain():
    """**GT-15's battery figure — 2 kW blocks at `$12.00` = `$24.00`** — from
    database rows, through the same chain the solar case above uses.

    ⚠ **THIS CASE REPLACES A PLACEHOLDER THAT ASSERTED THE OPPOSITE, and the
    replacement is the defect closing (`DEF-2408`, 2026-09-01).** Until today it
    read `test_battery_still_refuses_on_a_question_the_po_dissolved` and put
    `pytest.raises(SizeClassNotRuled)` around this very call, because
    `apps/tenancy/service_size_classes.py` still listed battery in
    `UNBANDED_SERVICE_DIMENSIONS`: **a battery account could not be billed at
    all.** Its own docstring said what to do — *"THIS CASE IS A PLACEHOLDER FOR
    A DEFECT AND MUST BE DELETED WHEN IT CLOSES, not left asserting a refusal
    that is no longer correct"* — and it did its job exactly as designed: the
    moment the ruling reached the code this file went

        FAILED tests/test_capacity_end_to_end.py::
          test_battery_still_refuses_on_a_question_the_po_dissolved
          — DID NOT RAISE <class 'apps.tenancy.service_size_classes.
            SizeClassNotRuled'>

    which is the RED that made somebody read the paragraph. **That is the whole
    proof for this case: it is the same call, and the refusal is gone.**

    **WHAT CHANGED IS ONE FACT, NOT A BAND.** `OQ-561` was DISSOLVED by the PO
    on 2026-08-27 — *"(a) multiplier replaces bands for capacity services
    (solar, battery, thermal); bands stay for pipe/amp/CFH - this si corect"* —
    so battery is not banded AT ALL, and `size_classes_for_service("battery")`
    now returns `()`, this module's own word for *ruled to have none* (sewer's
    answer). No boundary was invented; the question was answered by removing its
    subject.

    Every number here travelled, exactly as the solar case's do: `$12.00` came
    out of `rating.CapacityRate`, the `2` was COUNTED from two battery assets
    standing on the unit (`BR-RAT-090`), and `kW block` is the tenant's own word
    for its unit.
    """
    tenant = _capacity_tenant(services=("battery",))
    with tenant_ctx(tenant):
        actor = staff_actor(tenant, email="ops@sunridge.test")
        _declare_unmetered(actor, "battery")
        plan = _capacity_plan(tenant, {"battery": (BATTERY_UNIT_LABEL, BATTERY_RATE)})
        with seeding_ctx(tenant):
            _base_charge_code(tenant, "battery")
        unit = _unit_with_assets(actor, plan, {"battery": BATTERY_BLOCKS})
        account = _account_on(tenant, unit)
        bill = _priced(account, unit)

    (battery,) = _capacity_lines(bill, "battery")
    assert battery.amount == GT15_BATTERY
    assert battery.quantity == Decimal(BATTERY_BLOCKS)
    assert battery.unit == BATTERY_UNIT_LABEL
    # `DEF-2407`'s wording rule on the OTHER capacity model's line: a rate is
    # four decimal places (`OQ-620(a)`), never the six the column stores.
    assert battery.description == "battery capacity — 2 kW block @ 12.00"


def test_the_battery_refusal_escapes_gather_as_a_raw_notimplementederror():
    """⚠ **AND IT REFUSES IN THE SHAPE `gather` SAYS IT MUST NOT.**

    `gather._base_charge_for` states the module's posture in its own words: an
    unruled question refuses *"as a `GatherProblem` and not as
    `NotImplementedError`: a raise here would take down a 500-account run on its
    first account, where a named break stops one account and lets the other 493
    bill (BR-BIL-055)"*. `SizeClassNotRuled` subclasses `NotImplementedError`
    and travels out of `gather_account` uncaught, so it is the shape that rule
    forbids. `runs._calculate_run`'s blanket `except Exception` is what keeps a
    run alive today — a backstop, not the stated contract.
    """
    from apps.tenancy.service_size_classes import SizeClassNotRuled

    assert issubclass(SizeClassNotRuled, NotImplementedError)
    assert not issubclass(SizeClassNotRuled, gather.GatherProblem)
