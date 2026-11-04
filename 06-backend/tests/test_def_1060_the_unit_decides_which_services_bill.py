# ── Trace ──────────────────────────────────────────────
# Rule:     **BR-BIL-300** — WHICH services a bill charges is derived from the
#           UNIT, not from the plan (PO ruling 2026-08-27, closing OQ-601 on
#           mechanism). The plan supplies the PRICE for each; it no longer
#           supplies the LIST.
# Pin:      **Ana Alvarez's shape.** An account whose unit carries TRASH and
#           whose plan prices water and sewer produced a SIX-line bill of
#           **$64.57** with no trash line, no run exception and no note. It now
#           carries a **SEVENTH line — trash, $0.00** — and the total stays
#           **$64.57**. ⚠ The line count and the zero are asserted SEPARATELY:
#           a test on the total alone passes either way, and the whole thread
#           began with a service disappearing in silence.
# Rules:    OQ-601 edge 2 (*"Plan has a schedule, unit has no service point …
#           we have to bill it"*) — so the unit ADDS services and never REMOVES
#           one, which is why this whole change is additive and no ❄️ B5 figure
#           can move · BR-BIL-015 (a missing input is an EXCEPTION, never a
#           silent skip) · BR-BIL-055 (a named break stops ONE account, not the
#           run) · BR-CUS-015 (the badges come from ACTIVE service agreements) ·
#           CR-013 part 1 / DEF-277 (a blank base means NOT SERVED and refuses;
#           a stored 0.00 still bills $0.00)
# Defects:  DEF-1060 (this one) · DEF-990 (the same silence on a master's bill —
#           `test_br_cus_170_master_covers_the_unbilled.py::tc3`)
# OQs:      **OQ-670, CLOSED 2026-08-27 — (b) BILL `$0.00`.** ⚠ AN OVERRULE.
#           This lane built (a) *refuse by name*, because edge 1 says *bill base
#           only* and on Ana's tenant there is no base, no rate and no billed
#           unit; the PO chose the zero line with the trade stated — that it is
#           *"the same silence you caught, wearing a line item"* — and with the
#           `$720.00` a month in front of them. The refusal tests below became
#           these.
# Impacts:  apps/billing/gather.py
# ───────────────────────────────────────────────────────
"""DEF-1060 — a service cannot leave an account's bill in silence any more.

**THE DEFECT, IN THE PRODUCT OWNER'S OWN WORDS:** *"account has trash - but is
it not charged"* (CR-043 finding 4, measured on the live deployment at
v2.61.1).

**AND IN THE PRODUCT'S:** two independent sources described *this account's
services* and nothing reconciled them.

    badges  ← customers.selectors.service_codes_for → metering's SERVICE POINTS
    bill    ← billing.gather._tariffs_for_plan     → rating's PLAN SCHEDULES

A service in the first and not the second produced **no line, no run exception
and no note anywhere on the bill**. Account `AC-2026-00001` badged WATER ·
SEWER · TRASH; bill `BL-2607-000001` charged **$64.57** across six lines and
never mentioned trash.

**WHY NO TEST CAUGHT IT, WHICH IS THE HALF WORTH KEEPING.** Every billing test
in this repo asserts what the PLAN prices — so a service missing from the plan
is missing from the assertion too, and the fixture and the defect agree with
each other. `gather` raised `GATHER_NO_TARIFF` only when rating published no
resolver at all, never when the resolver returned a SHORTER LIST than the
account holds. **This file is the test written from the other side: it asserts
against the UNIT's service points, which is where the customer's actual
subscription lives.**

**THE THREE CASES BELOW ARE THE THREE THINGS THAT MUST STAY TRUE.** tc1 is the
defect. tc2 is the reason the fix is safe for every existing tenant — the unit
adds and never removes, so a plan that prices MORE than the unit takes is
untouched, which is OQ-601 edge 2 and is also why ❄️ GT-17's five-service
reference bill reproduces byte for byte. tc3 is the degrade: an unpublished
metering seam is the pre-DEF-1060 behaviour and not a new line.

⚠ **AND tc1 IS WRITTEN THE WAY IT IS BECAUSE A `$0.00` LINE IS ONE CARELESS
`if amount:` AWAY FROM BEING THE SILENCE AGAIN.** So it asserts the COUNT (a
seventh line, not six), the line's PRESENCE by service, and its ZERO AMOUNT, as
three separate assertions. The total is asserted too and proves nothing on its
own — `$64.57` is the answer with the line and without it, which is exactly why
nobody noticed for as long as they did.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import gather, rating_seam
from apps.billing.contracts import ServiceReading
from apps.billing.rating_seam import Quantity

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
SERVICE_DATE = date(2026, 6, 30)

#: Ana's June bill, as the Product Owner read it on the live deployment.
ANA_JUNE_BILL = Decimal("64.57")


def an_account(**overrides):
    """Customers' row shape, structurally — gather reads it by attribute."""
    values = dict(
        id="acct-ana",
        account_no="AC-2026-00001",
        unit_id="unit-ana",
        status=SimpleNamespace(behavior_class="billable"),
        tax_exempt=False,
        opened_at=None,
        closed_at=None,
        # AMENDED 2026-10-01 (billing red triage): the row's KIND — gather asks
        # customers which units a bill covers first (`covered_units`,
        # BR-CUS-068), and that read branches on it. A REGULAR account covers
        # its own unit, which is what every case here means.
        kind="regular",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def _gather_without_a_database(monkeypatch, settings):
    """AMENDED 2026-10-01 (billing red triage) — the same stated limit as
    `test_us_bil_002_gather` (read its fixture for the whole argument): this
    file has no database by design, so the base-warning NAME read degrades to
    the code (`tenancy_seam`'s own `{}` answer) and the R1–R7 chain is switched
    off (`SBH_BILLING_RESOLUTION_STEPS` empty). Which services a unit bills —
    this file's subject — is decided in gather BEFORE the switch, which only
    substitutes prices."""
    from apps.billing import tenancy_seam

    monkeypatch.setattr(tenancy_seam, "service_names_by_code", lambda *a, **k: {})
    settings.BILLING_RESOLUTION_STEPS = ""


def _resolver(published: dict):
    """Anything not named resolves to None — a module that has not landed."""

    def resolve(module, attribute, kind="selectors"):
        return published.get(f"{module}.{attribute}")

    return resolve


def _pricing_inputs(tariff, _service_date, *_size):
    """Rating's ENGINE shape. Water is TIERED so the fixture reaches Ana's own
    line SHAPE — two water tiers + water base + sewer usage + sewer base + one
    tax = SIX lines, which is what her June bill had before the zero line.

    ⚠ The RATES are this fixture's, not Silver Creek's, so the total below is
    not `$64.57` and is not asserted to be. What IS asserted is the ruling's
    two claims: one MORE line, and the SAME total.
    """
    if getattr(tariff, "service", None) == "water":
        return {
            "version_id": "v-water",
            "model": "tiered",
            "billed_unit": "kgal",
            "base_charge": "8.00",
            "minimum_bill": None,
            "currency": "USD",
            "unit_price": None,
            "tiers": [{"upper": "3", "unit_price": "3.10"}, {"upper": None, "unit_price": "4.20"}],
        }
    return {
        "version_id": "v-1",
        "model": "flat",
        "billed_unit": "kgal",
        "base_charge": "8.00",
        "minimum_bill": None,
        "currency": "USD",
        "unit_price": "3.10",
        "tiers": [],
    }


def _world(*, plan_services: list[str], unit_services: list[str]):
    """Ana's world, with the two lists held apart so a test can disagree them.

    `plan_services` are the services the PLAN carries a rate schedule for;
    `unit_services` are the service points standing on the UNIT. The whole
    defect is that these two were never compared.
    """
    return {
        "metering.unit_row": lambda _id: SimpleNamespace(
            id="unit-ana", label="Unit 3B", rate_plan_id="plan-res", premises=None
        ),
        "metering.service_points_for": lambda _id: [
            {"id": f"sp-{code}", "service": code, "route_id": None} for code in unit_services
        ],
        "rating.plan_ref": lambda _id: {"id": "plan-res", "name": "Residential", "version": 3},
        "rating.plan_rate_schedules": lambda _id: [
            {"service_code": code, "tariff": SimpleNamespace(id=f"t-{code}", service=code)}
            for code in plan_services
        ],
        "rating.pricing_inputs": _pricing_inputs,
        # ── `DEF-BIL-7170` · THE SEAM THAT NOW DECIDES EVERY BASE ───────────
        # ⚠ **THIS ENTRY IS NEW ON 2026-09-28 AND ITS ABSENCE USED TO BE
        # HARMLESS.** `_resolver` answers None for anything not named here, so
        # this world published no charge-code read and `gather._base_charge_for`
        # fell back to `pricing_inputs`' own `base_charge` of `8.00` — the rate
        # schedule version's RETIRED column. The PO retired it: *"we will never
        # take default value from plan $8.0 - that is retired"*, so a world with
        # no charge-code seam is now a tenant that has declared no base charge
        # code, and every case in this file refused with *"No base charge for
        # water. Declare one on Charge codes."*
        #
        # **The figure is the SAME `8.00`**, stated on the object that owns it,
        # so every assertion in this file about lines and totals is unmoved.
        "rating.base_charge_from_charge_code": lambda service_code, **_kwargs: {
            "amount": "8.00",
            "code": f"BASE-{service_code[:1].upper()}",
            "refusal": None,
        },
        "rating.plan_tax_rules": lambda *_a, **_k: [
            {"code": "STATE+LOCAL", "rate": "0.0825", "tax_id": "TAX-TX"}
        ],
        "tenancy.regional_settings": lambda: {"currency": "USD"},
    }


def _gather(account=None, readings=()):
    return gather.gather_account(
        account=account or an_account(),
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        readings=readings,
    )


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DEFECT — a service the UNIT takes and the PLAN never priced
# ══════════════════════════════════════════════════════════════════════════
def test_def_1060_tc1__trash_on_the_unit_and_not_on_the_plan_bills_a_zero_line(monkeypatch):
    """**Ana Alvarez's shape: badges WATER · SEWER · TRASH, plan prices water
    and sewer — and the bill now says so, at `$0.00`.**

    Before this fix the gather returned two tariffs and the run issued a bill
    for water and sewer. The customer's trash service was not charged, not
    refused, not noted and not visible anywhere.

    **PO ruling 2026-08-27, closing `OQ-670` — option (b), `Bill $0.00`.** ⚠ It
    OVERRULES this lane's recommendation of *refuse by name*, and the PO chose
    it with the trade stated: a zero line is *"the same silence you caught,
    wearing a line item"*, against **`$720.00` a month** across Silver Creek's
    48 trash accounts. The zero makes the gap visible on the document; the money
    is not written off — the day a clerk adds trash to the plan it prices.

    ⚠ **FOUR ASSERTIONS, AND THE ORDER IS THE POINT.** The COUNT catches the
    line being dropped; the PRESENCE catches it being renamed or unlinked from
    its service; the AMOUNT catches it being priced by accident; and the TOTAL
    proves nothing on its own — `$64.57` is the answer with the line and without
    it, which is precisely why the omission survived to production.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(_world(plan_services=["water", "sewer"], unit_services=["water", "sewer", "trash"])),
    )

    data = _gather()

    # The PLAN still supplies the tariffs, unchanged — the unit ADDS, never
    # removes (OQ-601 edge 2), so nothing about water or sewer moved.
    assert [config.service for config in data.tariffs] == ["water", "sewer"]

    # …and trash rides as an already-priced BASE line at zero.
    trash = [line for line in data.fees if line.service == "trash"]
    assert len(trash) == 1, data.fees
    assert trash[0].kind == "base"
    assert trash[0].amount == Decimal("0.0000")
    # Nothing was invented to get it there: no rate, no quantity, no unit. The
    # plan prices this service NOWHERE, so there is no unit a quantity could be
    # quoted in and CLAUDE.md rule 3 forbids assuming one.
    assert trash[0].unit is None
    assert trash[0].unit_price is None
    assert trash[0].quantity is None
    # It says so on the document rather than reading as a free service.
    assert "trash" in trash[0].description


def test_def_1060_tc1b__the_bill_gains_a_SEVENTH_line_and_the_total_does_not_move(monkeypatch):
    """**The worked case the ruling names, end to end through the engine.**

    Ana's June bill `BL-2607-000001` was **`$64.57`** over **SIX** lines with no
    trash — two water tiers, the water base, sewer usage, the sewer base and one
    tax. It now carries a **SEVENTH: trash at `$0.00`**, and the customer owes
    exactly what they owed before.

    ⚠ **THIS IS THE TEST THE WHOLE THREAD EXISTS FOR, AND IT IS WRITTEN TO FAIL
    IN THE ONE WAY THAT MATTERS.** A `$0.00` line is one careless `if amount:`
    away from being the original silence again, and **an assertion on the total
    cannot see the difference** — `$64.57` is the answer with the line and
    without it, which is exactly why nobody noticed for as long as they did. So
    the bill is priced TWICE, with the zero line and without it, and the two are
    compared on both facts the ruling makes: **one more line**, and **the same
    money**.

    ⚠ The RATES here are the fixture's, so the total is not literally `$64.57`
    and is deliberately not asserted to be — that figure belongs to Silver
    Creek's seeded plan. The SHAPE is Ana's: six lines become seven.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(_world(plan_services=["water", "sewer"], unit_services=["water", "sewer", "trash"])),
    )
    data = _gather(readings=(
        ServiceReading(service_code="water", consumption=Quantity(amount=Decimal("5"), unit="kgal")),
        ServiceReading(service_code="sewer", consumption=Quantity(amount=Decimal("5"), unit="kgal")),
    ))

    def _price(fees):
        return rating_seam.price_bill(
            services=tuple(
                (
                    config,
                    next(r.consumption for r in data.readings if r.service_code == config.service),
                )
                for config in data.tariffs
            ),
            period=rating_seam.BillingPeriod(
                start=PERIOD_START, end=PERIOD_END, cycle_days=30, service_days=30
            ),
            account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
            taxes=data.taxes,
            fees=fees,
        )

    without = _price(())          # the bill the product used to produce
    with_zero = _price(data.fees)  # the bill the ruling asks for

    # SIX becomes SEVEN. This is Ana's shape and this assertion is the guard.
    assert len(without.lines) == 6, [(l.kind, l.service) for l in without.lines]
    assert len(with_zero.lines) == 7, [(l.kind, l.service) for l in with_zero.lines]

    # The seventh names its SERVICE — not merely "a line appeared". A line the
    # ledger cannot attribute is a different defect wearing this one's costume.
    trash = [line for line in with_zero.lines if line.service == "trash"]
    assert len(trash) == 1
    # …and it is ZERO. Asserted apart from the count, because a line that
    # appeared with a price on it would satisfy the count and rob a customer.
    assert trash[0].amount == Decimal("0.00")

    # THE MONEY DOES NOT MOVE. Same total, including the tax — a `$0.00` base
    # joins the taxable subtotal and adds nothing to it, which is what makes the
    # zero line safe to ship on 48 live accounts.
    assert with_zero.total == without.total


def test_def_1060_tc1c__every_missing_service_gets_its_own_line(monkeypatch):
    """A clerk who fixes trash must not discover gas the next month.

    Under the refusal this was one message listing both; under the ruling it is
    one LINE each, so a three-service gap is three lines and not one summary a
    reader has to decode.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(_world(plan_services=["water"], unit_services=["water", "trash", "gas"])),
    )
    data = _gather()
    assert sorted(line.service for line in data.fees) == ["gas", "trash"]
    assert all(line.amount == Decimal("0.0000") for line in data.fees)


def test_def_1060_tc1d__a_service_the_run_scope_UNCHECKED_gets_no_line(monkeypatch):
    """US-BIL-001 §5 — an unchecked service is an EXPLICIT recorded choice.

    A clerk who runs a water-only cycle has SAID they are not billing trash this
    time. A `$0.00` trash line on that bill would contradict the choice they
    recorded, and would put a line on every bill of every tenant that bills its
    services on different cycles. The silence here is the clerk's, and written
    down where they made it.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(_world(plan_services=["water"], unit_services=["water", "trash"])),
    )
    data = gather.gather_account(
        account=an_account(),
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        scope_services=("water",),
    )
    assert [config.service for config in data.tariffs] == ["water"]
    assert data.fees == ()


def test_def_1060_tc1e__CR_013_part_1_still_refuses_where_it_always_did(monkeypatch):
    """⚠ **THE SUPERSESSION IS NARROW, ASSERTED AS A SEPARATE CASE.**

    `OQ-670` supersedes CR-013 part 1 ONLY for a service the unit derives that
    the plan prices **nowhere at all**. A blank base charge on a size the plan
    **does** serve is a different fact — *"Blank base = size not served"* (PO
    2026-08-19) — and `_base_charge_for` must go on refusing it by name
    (DEF-277).

    If this test ever goes green on a `$0.00` line instead of a refusal, the
    zero has leaked out of its case and every unpriced size in the product has
    silently become free.
    """
    # ⚠ SUPERSEDED 2026-10-01 (billing red triage) BY THE PO, NOT EDITED TO
    # GREEN. This asserted a REFUSAL — `GATHER_NO_TARIFF`, "No base charge for
    # water" — and the PO reversed that refusal on 2026-09-30, verbatim:
    # *"here we need to builf flexibility - if user did not define and bind
    # base charges in rate schedule - then as a default you take 0 and complete
    # the bill instead of refusing - if you want to show the warning you can
    # display it dueing the process"* (`18e1069f2`; `gather._base_charge_for`'s
    # own docstring). So a base NOBODY bound is `$0.0000` and a named warning,
    # and the case now asserts exactly that. ⚠ The fear in the docstring above
    # — "every unpriced size in the product has silently become free" — is
    # answered elsewhere: a size the schedule does not serve is refused by R3
    # (`resolution.SizeNotServed`) before this function is reached, and that
    # refusal is untouched (`test_br_rat_120_size_refusal`).
    token = gather._BASE_NOT_SET.set([])
    try:
        assert gather._base_charge_for("water", code_base=None) == Decimal("0.0000")
        assert gather._BASE_NOT_SET.get() == ["water"]
    finally:
        gather._BASE_NOT_SET.reset(token)
    # (History, kept: the refusal's sentence.)
    # ⚠ **THIS ASSERTED THE WORDS `NOT SERVED` UNTIL 2026-09-24
    # (`DEF-CUS-6550`).** They came from an 85-word sentence a CLERK reads on
    # ACC-06 step 3 — *"CR-013 part 1 makes a blank base mean THIS SIZE IS NOT
    # SERVED, so the bill refuses rather than charging $0.00 …"* — which is
    # RATIONALE, and B14 rule 33 puts rationale at zero words on screen. The
    # RULE is unchanged and now sits in the code beside the raise.
    # **What this case is for is untouched**: this branch REFUSES rather than
    # billing a `$0.00` line, and it is still the blank-base refusal and not
    # one of its seven siblings. (Superseded 2026-09-30 above: there is no
    # refusal left to carry a sentence.)


# ══════════════════════════════════════════════════════════════════════════
# (2) THE UNIT ADDS AND NEVER REMOVES — OQ-601 edge 2, PO 2026-08-27
# ══════════════════════════════════════════════════════════════════════════
def test_def_1060_tc2__a_plan_that_prices_MORE_than_the_unit_takes_is_untouched(monkeypatch):
    """**PO verbatim: *"2 Plan has a schedule, unit has no service point - this
    will also not happen pratcially; - we have to bill it"*.**

    ⚠ **THIS IS THE ASSERTION THAT MAKES THE WHOLE CHANGE SAFE.** The mechanism
    ruling says the unit decides WHICH services are billed, and read alone that
    sentence would DROP a plan service the unit has no point for — which would
    silently un-bill customers on every tenant whose service points are
    incomplete, and would move ❄️ frozen figures. Edge 2 qualifies it: the unit
    is the source of truth for ADDING a service the plan missed, never for
    removing one the plan carries. So the reconciliation is purely additive, and
    a bill whose plan prices five services and whose unit carries one still
    prices five.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(_world(plan_services=["water", "sewer"], unit_services=["water"])),
    )
    data = _gather()
    # ⚠ SUPERSEDED 2026-10-01 (billing red triage) BY TWO PO RULINGS, NOT
    # EDITED TO GREEN. This asserted `["water", "sewer"]` — edge 2's *"we have
    # to bill it"*. BR-BIL-301 (2026-09-25) made a plan service the unit has no
    # service point for a `$0.00 (not connected)` line, and the PO then took
    # the line away on 2026-09-30, verbatim *"sane no line - and use 0"*
    # (`31358c239`, B3): a service NOT IN SERVICE prints no line and bills
    # `$0`. Sewer here is a TIERED service (not a %-of-water, which would
    # follow its basis — B1), so with no point it is not in service: no
    # tariff, and it is carried on `unconnected_services`, which feeds the
    # clerk's review list. Water — the service the unit takes — is untouched.
    assert [config.service for config in data.tariffs] == ["water"]
    assert data.unconnected_services == ("sewer",)
    assert not [line for line in data.fees if line.service == "sewer"]
    # And nothing on the remaining tariff was touched by the new code path.
    assert all(config.base_only is False for config in data.tariffs)


def test_def_1060_tc2b__a_unit_whose_services_the_plan_all_prices_gathers_unchanged(monkeypatch):
    """Every account this product has ever billed, asserted as a no-op.

    The two sets agree, so the reconciliation finds nothing and the tariffs are
    exactly what `plan_rate_schedules` returned — same order, same count, same
    prices. This is what "no ❄️ B5 figure can move" means in code.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(
            _world(plan_services=["water", "sewer"], unit_services=["water", "sewer"])
        ),
    )
    data = _gather()
    assert [config.service for config in data.tariffs] == ["water", "sewer"]
    assert data.tariffs[0].base_charge == Decimal("8.00")


# ══════════════════════════════════════════════════════════════════════════
# (3) THE DEGRADE — an unpublished seam is the OLD behaviour, not a refusal
# ══════════════════════════════════════════════════════════════════════════
def test_def_1060_tc3__without_metering_the_plans_list_is_still_the_bills_list(monkeypatch):
    """A deployment whose metering lane has not landed must not start refusing.

    `service_points_for` unpublished means *nobody can tell what this unit
    takes*, and inventing a reconciliation from a seam that is not there would
    be a guess about which services a customer holds. So it degrades to the
    pre-DEF-1060 behaviour — the plan's list — which cannot under-bill anything
    that was not already under-billed, and cannot stop a run that was working.
    """
    world = _world(plan_services=["water", "sewer"], unit_services=["water", "sewer", "trash"])
    world.pop("metering.service_points_for")
    monkeypatch.setattr(gather, "_resolve", _resolver(world))

    data = _gather()
    assert [config.service for config in data.tariffs] == ["water", "sewer"]
    assert data.fees == ()


# ══════════════════════════════════════════════════════════════════════════
# (4) THE FLAG ITSELF — base-only is now a fact about a TARIFF (DEF-990)
# ══════════════════════════════════════════════════════════════════════════
def test_def_1060_tc4__a_base_only_tariff_never_consumes_another_connections_read():
    """DEF-990's second named obstacle, asserted at the stage that had it.

    `measure_consumption._reading_for` matches a reading by SERVICE CODE alone.
    Give one bill two electric tariffs and ask for both, and the second gets the
    FIRST connection's reading — a document that foots and bills the same kWh
    twice. A base-only tariff never reaches that lookup.
    """
    from apps.billing.contracts import AccountBillingData, ServiceReading, SubscriptionContext
    from apps.billing.rating_seam import BillingPeriod, Quantity, TariffConfig
    from apps.billing.stages.measure_consumption import (
        ABSENT_TARIFF_BASE_ONLY,
        measure_consumption,
    )

    hallway = TariffConfig(service="electric", model="flat", billed_unit="kWh", base_charge=None)
    empty_unit = TariffConfig(
        service="electric", model="flat", billed_unit="kWh", base_charge=Decimal("12.00"),
        base_only=True,
    )
    reading = ServiceReading(
        service_code="electric", consumption=Quantity(amount=Decimal("684"), unit="kWh")
    )
    data = AccountBillingData(
        account_id="acct-1",
        account_no="MA-1408",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        service_days=30,
        tariffs=(hallway, empty_unit),
        readings=(reading,),
    )
    subscription = SubscriptionContext(
        account_id="acct-1",
        account_no="MA-1408",
        currency="USD",
        tax_exempt=False,
        period=BillingPeriod(start=PERIOD_START, end=PERIOD_END, cycle_days=30, service_days=30),
        rate_plan_id="plan-1",
        rate_plan_name="Small Commercial",
        rate_plan_version=1,
        tariffs=(hallway, empty_unit),
        taxes=(),
        fees=(),
        base_only=False,
        snapshot={},
    )

    usage = measure_consumption(subscription, data)
    # ONE of the two electric services measured — the hallway's. The empty
    # unit's tariff carries the absence with its OWN reason, so the S31.3
    # exception screen never lists it as work a clerk could clear.
    assert len(usage.measured) == 1
    assert usage.measured[0].consumption.amount == Decimal("684")
    assert [service.absent_reason for service in usage.unmeasured] == [ABSENT_TARIFF_BASE_ONLY]


def test_def_1060_tc4b__the_flag_defaults_false_so_every_older_fixture_prices_as_before():
    """A `TariffConfig` built without the field is not base-only.

    Every golden fixture, every §A4 scenario and every gather test predates the
    flag. `bills_base_only` reads it through `getattr` with a default for the
    same reason, so a tariff object from anywhere at all answers False.
    """
    from apps.billing.rating_seam import TariffConfig
    from apps.billing.stages.measure_consumption import bills_base_only

    assert TariffConfig(service="water", model="flat", billed_unit="kgal").base_only is False
    assert bills_base_only(SimpleNamespace(service="water", model="flat")) is False


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-1060 + DEF-990 + OQ-601 (decision log 2026-08-27, three rulings:
#         the mechanism, the four edges, and "not in service" is derived)
# generated: 2026-08-27 by the bill-omissions lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a gather-stage refusal)
#         E✔(the three reason codes carry i18n sentences) F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · NO django_db marker — gather reads through SEAMS, so
#         these publish a fake resolver and touch no database. The real-row
#         proof of the same path is
#         tests/test_br_cus_170_master_covers_the_unbilled.py::tc3, which drives
#         a live premises to $81.60.
# red-proved: tc1 fails `DID NOT RAISE GatherProblem` with the
#         `_refuse_unpriced_unit_services` call removed from `_tariffs_for_plan`
#         — which is exactly the product that shipped Ana's $64.57. tc4 fails
#         `assert 2 == 1` with the `bills_base_only` branch removed from
#         `measure_consumption`, because both electric tariffs then measure 684
#         kWh and the hallway's usage is billed twice.
# exceptions: (1) the refusal in tc1 is a REFUSAL where the PO asked for flow
#         (*"bill base only"*) — the base does not exist on this tenant, so
#         OQ-670 carries the collision and nothing here chooses a figure.
#         (2) the seam resolver is STUBBED, so what is proved is the gather's
#         LOGIC; a fake agreeing with the code proves nothing on its own, which
#         is why tc3 of the BR-CUS-170 file drives real rows.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
