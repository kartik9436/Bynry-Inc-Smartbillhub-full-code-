# ── Trace ──────────────────────────────────────────────
# Defects: DEF-484 (gather passes no connection size) · DEF-514 (nothing
#          RECORDS a connection size, so there is nothing to pass) · DEF-466
#          (R5's factor can never be anything but 1.0) · DEF-515 (nothing
#          writes the plan's factor either) · DEF-517 (nothing writes the
#          premises flag either)
# Rules:   BR-RAT-101 (the inside/outside-city flag lives on the PREMISES and
#          billing resolves it Account → Unit → Premises; `None` is a THIRD
#          STATE) · BR-RAT-102 (the PLAN decides whether an outside-city
#          surcharge applies and how much; a plan stating a factor over a
#          `None` premises STOPS THE BILL) · BR-RAT-032 as amended by DEF-433
#          (NULL is "every size"; a size_class group is the exception) ·
#          BR-RAT-007 (the version in force at the SERVICE date) · BR-BIL-055
#          (a break never blocks the run) · B4 ❄️ (money math)
# Tests:   this file
# Impacts: apps/billing/gather.py · apps/rating/selectors.pricing_inputs ·
#          apps/rating/selectors.plan_jurisdiction_pricing · apps/billing/runs.py
# ───────────────────────────────────────────────────────
"""THE TWO FACTS THE LIVE PATH NOW HANDS THE ENGINE — and what each one costs.

Both halves of this file exist because a multiplication that changes nothing is
invisible, and both of them were exactly that until 2026-08-21:

  * **the connection SIZE** selects which tier ladder prices the bill, and
    `gather` passed none, so a schedule with a 2" override billed the base
    ladder (DEF-484);
  * **the jurisdiction FACTOR** multiplies every base line and every usage line,
    and `gather` never set it, so every bill this product has ever issued priced
    at exactly `1.0` (DEF-466).

⚠ **NEITHER HALF MOVES A SINGLE FIGURE ON THE SHIPPED TENANT, AND THAT IS
ASSERTED HERE RATHER THAN ASSUMED.** Every tier in the database carries
`size_class` NULL, so the ladder selection returns the same rows at the same
prices; every `rate_plans.outside_city_factor` is NULL, so `money_factor`
short-circuits to `1` and the premises is never consulted. The tests named
`..._byte_identical_...` are that proof, and they are the reason B4/B5 ❄️ and
`tests/golden` stay green: nothing here changes billing arithmetic, it changes
which INPUTS reach it.

WHAT IS PROVED AND WHAT IS ONLY WIRED
--------------------------------------
The SOURCES of both facts are still missing, each with its own defect row, and
this file states which is which rather than letting a green run imply more than
it should:

  * `metering.connection_size_for` does not exist — **no row in this product
    records a connection's size** (DEF-514). So `_connection_size_for` returns
    None on every real bill, and the test that proves the hop is live PUBLISHES
    the seam. What is proved is the HOP; what is missing is the SOURCE.
  * ⚠ AMENDED 2026-08-27 — both columns HAVE writers now (CR-039 wave C tasks
    10 and 11 closed the write halves of DEF-515 and DEF-517); what remains of
    DEF-515 is the PLN-03 wizard control. This file still injects, because it
    tests the ARITHMETIC and `tests/test_cr039_c11_seeded_surcharge.py` tests
    the sourcing. As written, the two columns had no writer at any layer, so both
    are written here through the ORM. **That is precisely the shape DEF-466
    warns about** — *"the engine's own tests pass a tariff carrying the factor
    directly, so the arithmetic is proven and the SOURCING is untested"* — and
    it is why the two defect rows exist rather than a comment.

THE FIGURES ARE SILVER CREEK'S OWN, never retyped
--------------------------------------------------
`core/sample_fixture.py` prices residential water at a `$8.00` base over tiers
`4.00 / 6.50 / 8.00`. An 11 kgal household is `5 × 4.00 + 6 × 6.50 = $59.00` of
usage — **which is BR-RAT-102's own worked example**, so the rule's `$67.85` at
a factor of `1.15` is reproduced here from the fixture rather than asserted from
the rule text.
"""

from __future__ import annotations

import re

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather, rating_seam, runs
from apps.billing.contracts import ServiceReading
from apps.billing.stages.measure_consumption import measure_consumption
from apps.billing.stages.resolve_subscription import resolve_subscription
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.tenancy import models as tenancy_models
from core import sample_fixture as fixture

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
SERVICE_DATE = PERIOD_END
CYCLE_DAYS = 31

#: Silver Creek's own base and ladder, read from the fixture (B12 §No hard-coded
#: values). A literal here would be a second source of truth for the figure this
#: file exists to check.
WATER_BASE = Decimal(fixture.WATER_BASE)

#: An 11 kgal household: 5 kgal in the first block and 6 in the second.
#: `5 × 4.00 + 6 × 6.50 = 59.00` — BR-RAT-102's own worked example, derived from
#: the fixture rather than copied out of the rule.
PRIOR_READ = "1150"
CURRENT_READ = "1161"
USAGE_KGAL = Decimal("11")
EXPECTED_USAGE = (
    Decimal("5") * Decimal(fixture.WATER_TIERS[0][2])
    + Decimal("6") * Decimal(fixture.WATER_TIERS[1][2])
)

#: r10's 2" water row — the override DEF-433 made storable and DEF-484 found
#: unreachable. Prices 3.45 / 5.10 / 7.70 against 3.20 / 4.80 / 7.20 everywhere
#: else; here it sits over Silver Creek's own 4.00 / 6.50 / 8.00 base ladder so
#: the two can never be confused for one another in a failure message.
TWO_INCH = "W-2"
TWO_INCH_PRICES = ("3.450000", "5.100000", "7.700000")

#: BR-RAT-102's own figure: *"a plan stating `1.15`, at an outside-city premises,
#: bills $67.85"*.
FACTOR = Decimal("1.15")


# ══════════════════════════════════════════════════════════════════════════
# Fixture — Silver Creek's shape on real rows, four modules deep
# ══════════════════════════════════════════════════════════════════════════


def _water_plan(tenant, *, factor=None, exempt_services=()):
    """A published, DATED water plan priced the way rating really stores an
    inclining ladder — the prices are TIERS (BR-RAT-032), not a column.

    `factor` writes `rate_plans.outside_city_factor` DIRECTLY. ⚠ **THIS
    PARAGRAPH SAID "nothing in the product can write it" AND THAT IS NO LONGER
    TRUE (CR-039 wave C task 11, 2026-08-27):** `PLAN_FIELDS` carries
    `outside_city_factor` and `PLAN_SERVICE_FIELDS` carries
    `outside_city_exempt`, so `create_plan`/`update_plan` write both. The ORM
    write is KEPT here on purpose — `make_plan` builds this fixture's plan
    without a services payload, and routing the factor through the validator
    would make these tests depend on a write path they do not exist to test.
    What is still missing is DEF-515's other half: no PLN-03 wizard control.
    """
    plan = make_plan(tenant, name="Silver Creek Residential", services=("water",))
    rating_models.RatePlan.objects.filter(pk=plan.id).update(
        effective_from=date(2026, 1, 1),
        effective_to=None,
        outside_city_factor=factor,
    )
    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=WATER_BASE,
            uom=fixture.WATER_UOM,
            currency="USD",
            effective_from=date(2026, 1, 1),
        )
        for seq, (from_qty, to_qty, price) in enumerate(fixture.WATER_TIERS, start=1):
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=seq,
                from_qty=Decimal(from_qty),
                to_qty=None if to_qty is None else Decimal(to_qty),
                unit_price=Decimal(price),
            )
        # `make_plan` writes the SCHEDULE BINDING and no `plan_services` row, so
        # the plan's declared base would be absent and `gather._base_charge_for`
        # would silently fall back to the schedule's column — DEF-154's exact
        # shape. Written here so the base under test is the PLAN's.
        rating_models.PlanService.objects.update_or_create(
            tenant=tenant,
            rate_plan_id=plan.id,
            service_id=row["service_id"],
            defaults={
                "base_charge": WATER_BASE,
                "outside_city_exempt": row["service_code"] in exempt_services,
            },
        )
    # ── `DEF-BIL-7170` · WHAT ACTUALLY PRICES THE BASE FROM 2026-09-28 ───────
    # ⚠ **THE COMMENT ABOVE SAYS *"so the base under test is the PLAN's"*, AND
    # THE PLAN'S IS NO LONGER READ.** PO 2026-09-28: *"we will never take
    # default value from plan $8.0 - that is retired"*. Without an `is_base`
    # charge code every case in this file refuses with *"No base charge for
    # water. Declare one on Charge codes."* — and the jurisdiction factor this
    # file exists to measure multiplies a base that never arrives.
    #
    # The code states the SAME `WATER_BASE` the plan does, unscoped
    # (`BR-RAT-108`: `[]` is every class), so **no figure in this file moves**.
    base_code, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code="BASE-W-484",
        defaults=dict(
            name="Water base",
            charge_type="recurring",
            service=tenancy_models.Service.objects.get(code="water"),
            amount_rule="flat",
            amount=WATER_BASE,
            is_base=True,
            applies_to_customer_classes=[],
        ),
    )
    # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES it; unnamed bills $0.00.
    from tests.base_code_naming import name_base_code

    name_base_code(tenant, base_code)
    return plan


def _two_inch_override(plan):
    """Add r10's 2" ladder beside the base one, on every version this plan binds.

    A version then carries SIX tier rows in one ascending sequence, which is the
    state DEF-433's ladder selection exists for and the state DEF-484 says never
    reaches a bill.

    ⚠ `seq` CONTINUES GLOBALLY rather than restarting at 1 for the new group,
    because `uq_rate_tiers_version_seq` is unique on (version, seq) and does NOT
    include `size_class` — `services._write_version` renumbers across every
    group for exactly that reason. Restarting at 1 raises an IntegrityError, so
    this fixture reproduces what the writer really stores rather than what the
    matrix column header shows.
    """
    for row in rating_selectors.plan_rate_schedules(plan.id):
        for version in rating_models.TariffVersion.objects.filter(tariff=row["tariff"]):
            offset = rating_models.RateTier.objects.filter(tariff_version=version).count()
            for index, price in enumerate(TWO_INCH_PRICES, start=1):
                rating_models.RateTier.objects.create(
                    tenant=version.tenant,
                    tariff_version=version,
                    seq=offset + index,
                    size_class=TWO_INCH,
                    from_qty=Decimal("0") if index == 1 else Decimal((index - 1) * 5),
                    to_qty=None if index == len(TWO_INCH_PRICES) else Decimal(index * 5),
                    unit_price=Decimal(price),
                )


def _account_on(tenant, actor, plan, *, inside=None, address="4 Quarry Hill Rd", account_no="SCW-0001", asset_no="M-9001", cycle=None, size_class=None):
    """One account, one unit, one water meter, one committed read — and the
    premises' city-limits flag written DIRECTLY.

    `inside` goes onto the row through the ORM. ⚠ **THIS PARAGRAPH SAID
    "nothing in the product can write it" AND THAT IS NO LONGER TRUE (CR-039
    wave C task 10, 2026-08-27):** `create_premises`/`update_premises` accept
    the three states and `JurisdictionField` draws them on two screens. The ORM
    write is kept because `make_premises` here is a fixture helper and the
    write path has its own file
    (`tests/test_cr039_c10_premises_jurisdiction_write.py`); the SEEDED-data
    proof lives in `tests/test_cr039_c11_seeded_surcharge.py`.
    `None` is not a "default" here — it is still the shipped state of a premises
    nobody has been asked about, which is why BR-RAT-101 insists it stay a third
    state.
    """
    premises = make_premises(actor, address_line=address, services_available=["water"])
    if inside is not None:
        metering_models.Premises.objects.filter(pk=premises["id"]).update(
            inside_city_limits=inside
        )
    unit = make_unit(actor, premises["id"], label="Unit A", services=["water"])
    asset = a_meter(
        actor,
        asset_no=asset_no,
        service="water",
        uom=fixture.WATER_UOM,
        multiplier="1",
        unit_id=unit["id"],
        # BR-AST-500 (2026-08-27) — the connection size, which DID NOT EXIST as
        # a column when this helper was written. It defaults to None, which is
        # what every meter in every existing database still carries, so every
        # case in this file that does not ask for a size is byte-identical.
        size_class=size_class,
    )
    if cycle is not None:
        metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
            cycle=cycle
        )
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    commit_read(
        actor,
        asset["id"],
        day="2026-07-28",
        value=CURRENT_READ,
        prior_value=PRIOR_READ,
        # BR-MET-019 — what metering itself stores, ALREADY post-multiplier.
        consumption=USAGE_KGAL,
        unit=fixture.WATER_UOM,
        multiplier="1",
    )
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.first(),
    )


def _readings_for(account):
    """Metering's own seam, exactly as `apps/billing/runs.py` calls it."""
    from apps.metering import selectors as metering_selectors

    rows = metering_selectors.billing_reads_for_unit(
        account.unit_id, period_start=PERIOD_START, period_end=PERIOD_END
    )
    return tuple(
        ServiceReading(
            service_code=row["service_code"],
            service_id=row["service_id"],
            consumption=(
                None
                if row["consumption"] is None
                else rating_seam.Quantity(amount=row["consumption"], unit=row["unit"])
            ),
            estimated=row["estimated"],
            absent_reason=row["absent_reason"],
            prior_read=row["prior_value"],
            current_read=row["current_value"],
            read_id=row["read_id"],
        )
        for row in rows
    )


def _gather(account):
    """THE PATH A CUSTOMER CAN REACH — billing's own function, its own arguments."""
    return gather.gather_account(
        account=account,
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=CYCLE_DAYS,
        readings=_readings_for(account),
    )


def _priced(data):
    """Stages 1 → 2 → 3-5 over gathered data. The run's own sequence, minus the
    write: `runs.calculate_account` does exactly this and then drafts a bill,
    and a draft is not what these assertions are about."""
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


def _amounts(priced):
    """`{kind: amount}` over the priced lines — base and usage, which are the two
    things R5 multiplies."""
    out: dict[str, Decimal] = {}
    for line in priced.lines:
        out[line.kind] = out.get(line.kind, Decimal("0")) + Decimal(str(line.amount))
    return out


# ══════════════════════════════════════════════════════════════════════════
# HALF A · the connection size
# ══════════════════════════════════════════════════════════════════════════


def test_half_a_the_size_is_none_on_every_real_bill_because_nothing_records_one(brazos, dana):
    """DEF-514 — THE FINDING, AND THE RE-PROOF THIS TEST ITSELF DEMANDED.

    ⚠ **THIS CASE FIRED ON 2026-08-27 AND ITS OWN MESSAGE SAID WHAT TO DO.** As
    written it asserted `gather._resolve("metering", "connection_size_for") is
    None` and carried the instruction *"metering now publishes
    `connection_size_for` — DEF-514 may be closed, and the size the bill will
    now use must be re-proved rather than assumed"*. BR-AST-500 published it.
    This is that re-proof, and it is deliberately BOTH halves, because the
    dangerous outcome was never *"the size stays None"* — it was **a size
    appearing unannounced on a money path**.

    So: a meter with no size recorded still answers `None` — which is every
    meter in every existing database, and is why not one bill moves — and a
    meter WITH a size recorded answers **that size and no other**. Neither
    answer is a default, and there is no third case.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        assert gather._resolve("metering", "connection_size_for") is not None, (
            "metering has STOPPED publishing connection_size_for — DEF-514 has "
            "regressed and every per-size ladder is silently unreachable again"
        )

        # ── Half 1: unrecorded stays unrecorded. Nothing appears unannounced.
        plain = _account_on(brazos, dana, plan)
        assert gather._connection_size_for(plain.unit_id, "water") is None

        # ── Half 2: recorded reaches the caller, verbatim and unchanged.
        sized = _account_on(
            brazos,
            dana,
            plan,
            address="6 Quarry Hill Rd",
            account_no="SCW-0002",
            asset_no="M-9002",
            size_class="W-58",  # BR-TEN-171's ratified 5/8" water code
        )
        assert gather._connection_size_for(sized.unit_id, "water") == "W-58"


def test_half_a_byte_identical_today_the_ladder_is_the_same_rows_at_the_same_prices(brazos, dana):
    """⚠ THE PROOF THAT NOTHING MOVES, AND IT IS THE POINT OF THE WHOLE HALF.

    No seeded schedule carries an override, so the NULL group IS every tier the
    version has and the fallback is the WHOLE answer. Asserted three ways, from
    the selector out to the gathered config: the same count, the same order, the
    same prices, and Silver Creek's own base beside them.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account = _account_on(brazos, dana, plan)
        row = rating_selectors.plan_rate_schedules(plan.id)[0]

        unsized = rating_selectors.pricing_inputs(row["tariff"], SERVICE_DATE)
        with_none = rating_selectors.pricing_inputs(row["tariff"], SERVICE_DATE, None)
        assert unsized["tiers"] == with_none["tiers"]
        assert unsized["size_groups"] == []  # the version treats no size differently

        config = _gather(account).tariffs[0]
        assert [tier.unit_price for tier in config.tiers] == [
            Decimal(price) for _lo, _hi, price in fixture.WATER_TIERS
        ]
        assert config.base_charge == WATER_BASE


def test_half_a_byte_identical_today_the_money_is_the_fixtures_own_figure(brazos, dana):
    """The same proof one layer up, in dollars: base `$8.00`, usage `$59.00`.

    This is the BEFORE figure both halves of this file are measured against, and
    it comes out of `core/sample_fixture.py` rather than out of a expectation
    somebody typed.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account = _account_on(brazos, dana, plan)
        amounts = _amounts(_priced(_gather(account)))
        assert amounts["base"] == Decimal("8.00")
        assert amounts["usage"] == EXPECTED_USAGE == Decimal("59.00")


def test_half_a_the_hop_is_live_a_published_seam_reaches_the_tier_ladder(brazos, dana, monkeypatch):
    """⚠ HARD-WON LAW 2 — *"built is not wired"* — ANSWERED WITH A TEST.

    `_connection_size_for` returns None on every real bill, which is exactly the
    shape of the dead wiring the law forbids: a hop nothing exercises passes
    forever. So this PUBLISHES the missing seam and follows the size the whole
    way — `metering.connection_size_for` → `gather` → `pricing_inputs` → the
    `TariffConfig` the engine prices from.

    The 2" ladder is r10's `3.45 / 5.10 / 7.70`; Silver Creek's base ladder is
    `4.00 / 6.50 / 8.00`. Neither can be mistaken for the other in a failure.
    """
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "connection_size_for",
        lambda _unit_id, _service: TWO_INCH,
        raising=False,
    )
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        _two_inch_override(plan)
        account = _account_on(brazos, dana, plan)
        data = _gather(account)
        config = data.tariffs[0]
        amounts = _amounts(_priced(data))

    # THREE blocks, never six — the ladder was SELECTED, not concatenated.
    assert len(config.tiers) == 3
    assert [tier.unit_price for tier in config.tiers] == [
        Decimal(price) for price in TWO_INCH_PRICES
    ]
    # AND THE MONEY MOVES, which is the assertion with teeth: the same 11 kgal
    # priced on the 2" ladder is `5 × 3.45 + 5 × 5.10 + 1 × 7.70 = $50.45`,
    # against `$59.00` on the every-size ladder the bill would have used.
    #
    # ⚠ HERE THE FALLBACK OVER-CHARGES BY `$8.55`, WHICH IS THE POINT AND NOT AN
    # ODDITY. r10's own pairing (2" at 3.45/5.10/7.70 over a base ladder of
    # 3.20/4.80/7.20) runs the other way and the fallback UNDER-charges — about
    # $12/month, which is the figure DEF-484 was filed on. A size-blind ladder is
    # wrong in whichever direction the utility typed, and nothing on the document
    # says which.
    assert amounts["usage"] == Decimal("50.45")
    assert amounts["usage"] != EXPECTED_USAGE  # not the every-size answer
    assert amounts["base"] == Decimal("8.00")  # the base is not the size axis here


def test_half_a_a_sized_schedule_with_no_resolvable_size_refuses_by_name(brazos, dana):
    """DEF-484's second half: **the fallback stops being silent.**

    A version that names sizes and a connection whose size cannot be stated is
    the one case where the NULL ladder is a GUESS rather than the rule. Before
    this commit the bill was produced on the base ladder — $12/month short on
    r10's own 10/20/5 usage, on a document that looks entirely ordinary. It now
    refuses, names the sizes the schedule prices differently, and names the
    defect a human has to clear.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        _two_inch_override(plan)
        account = _account_on(brazos, dana, plan)
        with pytest.raises(gather.GatherProblem) as refusal:
            _gather(account)

    assert refusal.value.reason == gather.GATHER_SIZE_UNRESOLVED
    assert refusal.value.service_code == "water"
    assert TWO_INCH in str(refusal.value)  # WHICH sizes, for the person fixing it
    # ⚠ **THE ASSERTION THAT CANNOT GO STALE — `DEF-BIL-6760`.** This read
    # `assert "DEF-514" in str(refusal.value)`, pinning a DEFECT ID inside a
    # sentence a clerk reads. It was written to prove the refusal says WHY, and
    # it outlived the why: `DEF-514` was CLOSED on 2026-08-27 at `2.79.5` — the
    # column, its publications and `metering.connection_size_for` all landed —
    # so the message went on telling a clerk *"nothing in this product records
    # one yet"* about a fact the product had recorded for a month, and the test
    # held that falsehood GREEN. It also broke B14 rule 32 (no internal code in
    # clerk-facing copy) on a string that reaches the move-out wizard verbatim.
    # The assertion now names the PROPERTY instead of the content: no defect or
    # rule id may appear in this sentence, ever, whatever it comes to say.
    assert not re.search(r"\b(?:DEF|BR|OQ|GT|US|EP)-[A-Z]*-?\d", str(refusal.value)), (
        "B14 rule 32 — this sentence reaches a clerk on the move-out wizard and "
        f"the bill run exception tab; it may carry no internal id. got {refusal.value}"
    )


def test_half_a_a_schedule_with_no_override_is_never_refused(brazos, dana):
    """The refusal is narrow ON PURPOSE, and this is the assertion that keeps it
    that way: every schedule in every tenant today names no size, so the guard
    above fires on nothing and no run gains a single exception row."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account = _account_on(brazos, dana, plan)
        assert _gather(account).tariffs[0].base_charge == WATER_BASE  # no refusal


# ══════════════════════════════════════════════════════════════════════════
# HALF B · the outside-city factor
# ══════════════════════════════════════════════════════════════════════════


def test_half_b_a_plan_with_no_factor_never_consults_the_premises(brazos, dana):
    """⚠ THE ASSERTION THAT STOPS THIS COMMIT REFUSING EVERY BILL IN THE PRODUCT.

    A premises nobody has been asked about holds `inside_city_limits = None`,
    and a naive wiring — read the flag, decide — would refuse every account of
    every tenant on day one. (Until 2026-08-27 this sentence read *"every seeded
    premises"*; CR-039 wave C task 11 states the flag on all 44 rows of the
    sample estate, and the guarantee below is unchanged for every premises that
    is still unstated.) BR-RAT-102 puts the plan's gate FIRST:
    *"A plan stating NO factor never consults the premises at all"*, so a
    utility that does not price by jurisdiction can never be refused by R5.

    Byte-identical: `$8.00` base and `$59.00` usage, the same two figures as
    before the factor existed.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)  # factor NULL — the shipped state
        account = _account_on(brazos, dana, plan, inside=None)
        data = _gather(account)
        amounts = _amounts(_priced(data))

    assert data.tariffs[0].jurisdiction_factor == Decimal("1")
    assert amounts["base"] == Decimal("8.00")
    assert amounts["usage"] == Decimal("59.00")


def test_half_b_outside_the_city_the_base_and_the_usage_BOTH_move(brazos, dana):
    """BR-RAT-102's own worked example, reproduced from the fixture.

    *"Silver Creek's residential water at `$59.00` on a plan stating `1.15`, at
    an outside-city premises, bills `$67.85`."* And the base moves with it,
    which is the second half of the PO's correction of 2026-08-19 — *"you will
    have to add rate changes in base charges and rates"*: `$8.00 → $9.20`.

    A failure here is a bill that is wrong by a third of every line.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, factor=FACTOR)
        account = _account_on(brazos, dana, plan, inside=False)
        data = _gather(account)
        amounts = _amounts(_priced(data))

    assert data.tariffs[0].jurisdiction_factor == FACTOR
    assert amounts["usage"] == Decimal("67.85")  # 59.00 × 1.15, BR-RAT-102's figure
    assert amounts["base"] == Decimal("9.20")  # 8.00 × 1.15
    # And the whole of it: what the customer used to pay, and what they pay now.
    assert amounts["base"] + amounts["usage"] == Decimal("77.05")


def test_half_b_inside_the_city_nothing_moves_even_on_a_surcharging_plan(brazos, dana):
    """The other side of the same line. Same plan, same factor, same usage — the
    premises is inside, so the surcharge does not apply and the bill is the one
    the customer has always had."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, factor=FACTOR)
        account = _account_on(brazos, dana, plan, inside=True)
        data = _gather(account)
        amounts = _amounts(_priced(data))

    assert data.tariffs[0].jurisdiction_factor == Decimal("1")
    assert amounts["base"] == Decimal("8.00")
    assert amounts["usage"] == Decimal("59.00")


def test_half_b_an_unstated_jurisdiction_refuses_that_account_and_names_the_premises(brazos, dana):
    """⚠ THE THIRD STATE, AND WHY IT REFUSES RATHER THAN DEFAULTING.

    BR-RAT-101: `True` inside, `False` outside, **`None` nobody recorded it**.
    BR-RAT-102: *"a plan stating a factor over a premises whose flag is `None`
    STOPS THE BILL … the factor changes every line, so a guess is a wrong bill
    rather than a partial one."*

    Assuming *inside* under-charges a customer the utility may be entitled to
    surcharge; assuming *outside* over-charges one who never agreed to it. Both
    are pricing decisions taken on data nobody entered.

    The refusal must be ACTIONABLE, so it names the premises by its address and
    says what to set.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, factor=FACTOR)
        account = _account_on(brazos, dana, plan, inside=None, address="9 Quarry Hill Rd")
        with pytest.raises(gather.GatherProblem) as refusal:
            _gather(account)

    assert refusal.value.reason == gather.GATHER_JURISDICTION_UNSTATED
    assert refusal.value.service_code == "water"
    message = str(refusal.value)
    assert "9 Quarry Hill Rd" in message  # WHICH premises
    assert "1.15" in message  # by HOW MUCH, so the stake is visible
    assert "BR-RAT-101" in message  # and WHAT to set


def test_half_b_the_refusal_blocks_one_account_and_the_rest_of_the_run_bills(brazos, dana):
    """BR-BIL-055 — **a break never blocks the run**, checked on this refusal
    specifically rather than on the class in general.

    A jurisdiction refusal that killed a 500-account run would be a worse defect
    than the under-charge it prevents. `prepare_run` catches `GatherProblem` per
    account, records it in `blocked` with its reason code — which the S31.2
    exception tab groups on — and carries on with the next account.
    """
    with tenant_ctx(brazos):
        cycle = metering_models.Cycle.objects.create(
        tenant=brazos,
        code="07-A",
        # W5-T2 — the ruled fields (metering 0021 dropped the date pair).
        start_day=PERIOD_START.day,
        days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
        )
        plan = _water_plan(brazos, factor=FACTOR)
        _account_on(
            brazos, dana, plan, inside=False, address="4 Quarry Hill Rd",
            account_no="SCW-0001", asset_no="M-9001", cycle=cycle,
        )
        _account_on(
            brazos, dana, plan, inside=None, address="9 Quarry Hill Rd",
            account_no="SCW-0002", asset_no="M-9002", cycle=cycle,
        )
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert [d.account_no for d in prepared.ready] == ["SCW-0001"]
    assert [p.account_no for p in prepared.blocked] == ["SCW-0002"]
    problem = prepared.blocked[0]
    assert problem.reason == gather.GATHER_JURISDICTION_UNSTATED
    # The screen needs a tab for it, and a "retry now" button would always fail.
    assert problem.stage == "resolve-subscription"
    assert gather.GATHER_JURISDICTION_UNSTATED in runs.NOT_RETRYABLE_HERE
    assert gather.GATHER_SIZE_UNRESOLVED in runs.NOT_RETRYABLE_HERE
    # The one that IS billable still prices at the surcharge, so "the run
    # continued" is not "the run continued and quietly stopped surcharging".
    assert prepared.ready[0].tariffs[0].jurisdiction_factor == FACTOR


def test_half_b_a_stored_factor_of_one_is_the_same_statement_as_none(brazos, dana):
    """BR-RAT-102, verbatim: *"absent or `1` = this plan does not surcharge"*.

    Two spellings of one fact, and the distinction matters because a plan
    stating `1` must not consult the premises either — otherwise a utility could
    refuse its whole run by typing a `1`.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, factor=Decimal("1"))
        assert rating_selectors.plan_jurisdiction_pricing(plan.id)["outside_city_factor"] is None
        account = _account_on(brazos, dana, plan, inside=None)
        data = _gather(account)  # not refused
        assert data.tariffs[0].jurisdiction_factor == Decimal("1")
        assert _amounts(_priced(data))["usage"] == Decimal("59.00")


def test_half_b_an_exempt_service_is_flat_everywhere(brazos, dana):
    """§A4 S2, verbatim: *"BASE-S $8.00 (flat everywhere — the multiplier does
    NOT touch sewer)"*.

    The exemption is per SERVICE and lives on the plan's own service line, so
    one plan can surcharge electric and leave sewer alone. Proved on water here
    because that is the service this fixture prices; the mechanism is the same
    list.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, factor=FACTOR, exempt_services=("water",))
        assert rating_selectors.plan_jurisdiction_pricing(plan.id)["exempt_services"] == ("water",)
        account = _account_on(brazos, dana, plan, inside=False)
        data = _gather(account)
        amounts = _amounts(_priced(data))

    assert data.tariffs[0].jurisdiction_factor == Decimal("1")
    assert amounts["base"] == Decimal("8.00")
    assert amounts["usage"] == Decimal("59.00")


def test_half_b_the_plan_seam_reports_the_shipped_state_rather_than_a_default(brazos, dana):
    """DEF-515, asserted so a green suite cannot imply the surcharge is
    reachable: a plan created the way the product creates one carries NO factor
    and NO exempt service, because nothing at any layer can set either."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        assert rating_selectors.plan_jurisdiction_pricing(plan.id) == {
            "outside_city_factor": None,
            "exempt_services": (),
        }


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-484 · DEF-466 · BR-RAT-101 · BR-RAT-102 (both CONFIRMED
#         2026-08-21) · BR-RAT-032 as amended by DEF-433 · §A4 S2 ·
#         `apps/rating/resolution.money_factor`'s own contract · B4 ❄️
# generated: 2026-08-21 by the DEF-438 cutover step-5 lane
# checklist: A✔ B✔ C✔ D=n/a(no API half) E=n/a(no frontend half) F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: ruff✔ · 10-scripts/03-golden-verify.py exit 0✔ · tests/golden
#         unchanged✔ · tests/test_def_438_parity.py unchanged✔
# exceptions: (1) the plan's factor and the premises' flag are written through
#         the ORM because NOTHING IN THE PRODUCT CAN WRITE EITHER (DEF-515,
#         DEF-517). Stated loudly in the fixture docstrings rather than hidden,
#         because it is the exact shape DEF-466 names — a proven arithmetic over
#         an untested sourcing. (2) the connection-size seam is monkeypatched in
#         one test, for the same reason and with the same row (DEF-514); every
#         other test asserts the shipped answer, which is None. (3) the exempt
#         case is proved on water rather than on §A4 S2's sewer, because this
#         fixture prices one service — the list is the same list.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
