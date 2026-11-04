# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-001 (S31.1 scope) · US-BIL-002 (S31.2 — the prepare pass)
#           Screens: S31.1 · S31.2 · S31.3
# Rules:    BR-BIL-015 (a missing input is an EXCEPTION a human decides) ·
#           BR-CUS-055 (behaviour classes decide who is billed) · BR-MET-033
#           (cycle membership) · BR-RAT-007 (price on the SERVICE date) ·
#           CLAUDE.md rule 3 (a quantity carries its unit)
# ───────────────────────────────────────────────────────
"""Phase 1 end to end, on real rows: the run's scope, its data, its problems.

These tests drive the REAL selectors in four modules — metering's scope and
reads, customers' account set, rating's prices, billing's gather — against
rows built through the real services. Nothing is stubbed. That is deliberate:
the gather's own tests publish a fake seam by design, and the whole point of
this file is the question a fake cannot answer, *do the modules actually fit*.

The property under test throughout is the one the PO's flow rests on: **a run
never hides an account.** Ready and blocked come back together, a missing read
is a decision rather than a silent skip, and a unit with usage and no customer
is visible rather than absent.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import runs
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import models as rating_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_plan,
    make_premises,
    make_unit,
    state_size_axis,
    tenant_ctx,
)
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
SERVICE_DATE = date(2026, 6, 30)


#: The base every fixture plan in this file bills, per service. One figure, so
#: the version's retired column and the charge code that owns it cannot drift.
FIXTURE_BASE = Decimal("18.500000")


def a_priced_plan(
    tenant,
    name="Residential Standard",
    services=("electric",),
    price="0.120000",
    *,
    base_code=True,
):
    """A published plan whose tariff has a version IN FORCE on the service date.

    Built the way rating really stores a flat rate — the price is one 0→∞ tier
    (BR-RAT-032), not a column on the version — so these tests exercise the
    same storage a real tenant has.

    ⚠ **AND IT NOW STATES A SIZE AXIS, BECAUSE R3 IS SWITCHED ON (`DEF-3227`).**
    The Product Owner ruled on 2026-08-28 that *"we need to charge account based
    on connection size they have"* (`BR-RAT-120`), and on 2026-09-01 ruled the
    step live — *"Can you wire them in now - R3 and R4"* — so
    `BILLING_RESOLUTION_STEPS` ships `"R3,R4"` and the connection-size step
    prices real bills. A schedule version that states NO size axis therefore
    refuses **every** account on it by name, which is the PO's own choice with
    its cost stated (`resolution_catalogue.configured_sizes_for` case 3,
    `DEF-2816`): *"Read the second way, the system refuses bills that price
    perfectly well today."*

    This fixture predates that switch. It built a version with one 0→∞ tier and
    no size rows, so from 2026-09-01 every account it priced came back as
    `ruled_path_refused` — *"R3: connection size 'E-1P-100' has no row on the
    rate schedule version …"* — and **11 of this file's 15 cases were red at the
    tip.** Nothing in the product is wrong: the fixture was describing a world
    the PO has since changed. `state_size_axis` is the shared helper written for
    exactly this (`tests/test_us_met_helpers.py`), and it takes its rows from
    `apps.rating.sample_data.sample_size_rows` so a fixture axis and a seeded
    axis cannot drift. It states MEMBERSHIP and no price — every `minimum_bill`
    is NULL — so it moves no money and no figure in this file changed.

    ⚠ **AND IT NOW STATES ITS BASE ON A CHARGE CODE (`DEF-BIL-8671`, red since
    `6057f1c6a`, 2026-09-28).** PO ruling 2026-09-28, verbatim: *"we ahve to
    take ot from Charge code … we will never take default value from plan $8.0
    - that is retired"* (`DEF-BIL-7170`, `gather._base_charge_for`). From that
    commit the `base_charge` on the version below is never read, so this
    fixture's `$18.50` base stopped reaching any bill: first every account
    refused, then — after the 2026-09-30 ruling that a base nobody defined bills
    `$0.00` with a warning (`18e1069f2`) — `tc1` gathered `0.0000` and `tc16`
    drafted `$49.44` against its documented `$67.94`. Same repair the
    2026-09-28 lane made to six other fixtures (`0ee4cccc9`) and `cd0b3abb2`
    made to the master-bill file: the SAME `$18.50` is declared, unscoped, as
    the service's `is_base` charge code, so no asserted figure moves. The
    version keeps its `base_charge` because the column still exists and is
    still written by the product; it is simply not a source.

    `base_code=False` is for a caller that mints its OWN base code for the
    service — a second one would be `DEF-468`'s ambiguity and refuse the bill.
    """
    from apps.rating import selectors as rating_selectors
    from apps.tenancy import models as tenancy_models

    plan = make_plan(tenant, name=name, services=services)
    if base_code:
        for service_code in services:
            rating_models.Charge.objects.get_or_create(
                tenant=tenant,
                code=f"BASE-{service_code.upper()}-FIXTURE",
                defaults=dict(
                    name=f"{service_code.title()} base",
                    charge_type="recurring",
                    amount_rule="flat",
                    amount=FIXTURE_BASE,
                    service=tenancy_models.Service.objects.get(code=service_code),
                    is_base=True,
                ),
            )
    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="flat",
            # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES its base code —
            # an unnamed schedule bills `$0.00`, so the `$18.50` is reached by
            # the ruled chain and no asserted figure moves.
            base_charge_code=(
                rating_models.Charge.objects.filter(
                    tenant=tenant, code=f"BASE-{row['tariff'].service.code.upper()}-FIXTURE"
                ).first()
                if base_code
                else None
            ),
            base_charge=FIXTURE_BASE,
            uom="kWh",
            currency="USD",
            effective_from=date(2026, 1, 1),
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=Decimal(price),
        )
        state_size_axis(version, row["service_code"])
    return plan


def a_cycle(tenant, code="06-A"):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        # W5-T2 — the ruled fields (metering 0021 dropped the date pair).
        start_day=PERIOD_START.day,
        days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
    )


def an_account(tenant, unit_id, account_no, status_code="active"):
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit_id,
        account_no=account_no,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code=status_code),
        account_type=customer_models.AccountType.objects.first(),
    )


def a_billed_unit(
    actor,
    tenant,
    cycle,
    plan,
    *,
    asset_no,
    label,
    consumption="412.000000",
    read_last_month=False,
):
    """One unit, metered, on the cycle, with a plan and a committed read.

    Returns the unit dict. The cycle stamp goes onto the SERVICE POINT because
    that is where metering keys a bill run's scope — a unit is in the run
    because one of its metered services is.

    `read_last_month=True` commits a May read (13,800 kWh, ×1) BEFORE this
    period, so `consumption=None` then builds **a meter that was read last
    month and missed this one** — the S31.2 missing-read case (`DEF-BIL-8671`).
    Without it, `consumption=None` builds a meter that has NEVER been read, and
    since R3 + R4 went live (`e998f92b1`, PO 2026-09-01 *"Can you wire them in
    now - R3 and R4"*) that is a different fact: the ruled path asks metering
    for the meter's multiplier, metering answers it from the newest read
    (`billing_multiplier_for`), a meter with no read has none, and an absent
    factor is never 1 (`resolution.MeterMultiplierUnstated`, BR-MET-056) — so
    the account is held as `ruled_path_refused` before a missing-read decision
    can be raised. The bulk-run changes table row 44 (PO 2026-09-30) makes *no
    multiplier* a clerk DECISION (Hold / Bill with multiplier 1) rather than a
    block; that row is "To build" on the prepare path.
    """
    premises = make_premises(actor, address_line=f"{asset_no} Bluestem Ln")
    unit = make_unit(actor, premises["id"], label=label, services=["electric"])
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    if read_last_month:
        commit_read(
            actor,
            asset["id"],
            day="2026-05-28",
            value="13800",
            prior_value="13400",
            consumption="400.000000",
            unit="kWh",
        )
    if consumption is not None:
        commit_read(
            actor,
            asset["id"],
            day="2026-06-28",
            value="14212",
            prior_value="13800",
            consumption=consumption,
            unit="kWh",
        )
    return unit


def test_us_bil_001_tc1__the_run_gathers_every_account_in_the_cycle(brazos, dana):
    """The happy path across FOUR modules' real selectors.

    Metering answers who is in the cycle and what they measured, customers
    answers who is billed, rating answers what it costs, billing assembles it.
    Each of those was proved in isolation; this is the first test that proves
    they fit together, which is the only thing a bill run actually needs.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7101", label="Unit A")
        an_account(brazos, unit["id"], "A-10001")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert prepared.account_count == 1
    assert prepared.blocked == ()
    data = prepared.ready[0]
    assert data.account_no == "A-10001"
    assert data.rate_plan_name == "Residential Standard"
    assert data.currency == "USD"
    assert data.cycle_days == 30  # the period's own length, June
    assert data.service_days == 30
    # The read came through metering POST-multiplier, carrying its unit.
    reading = data.readings[0]
    assert reading.service_code == "electric"
    assert reading.consumption.amount == Decimal("412.000000")
    assert reading.consumption.unit == "kWh"  # rule 3 — never a bare number
    assert reading.absent_reason is None
    # And rating's prices resolved at the SERVICE date (BR-RAT-007).
    assert data.tariffs[0].base_charge == Decimal("18.500000")
    assert data.tariffs[0].unit_price == Decimal("0.120000")


def test_us_bil_001_tc2__one_broken_account_never_hides_the_others(brazos, dana):
    """THE CASE THIS MODULE'S SHAPE EXISTS FOR.

    Raising on the first ungatherable account is the obvious implementation
    and it is wrong: a run of 500 where account 7 has no plan would show the
    clerk nothing about the other 493, and "how many are ready" — the number
    they act on — would not exist. Both halves come back, always.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        good = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7102", label="Unit A")
        an_account(brazos, good["id"], "A-10002")

        # A second unit in the same cycle whose plan was never assigned.
        premises = make_premises(dana, address_line="1500 Bluestem Ln")
        planless = make_unit(dana, premises["id"], label="Unit B", services=["electric"])
        a_meter(dana, asset_no="M-7103", unit_id=planless["id"])
        metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=planless["id"]).update(
            cycle=cycle
        )
        an_account(brazos, planless["id"], "A-10003")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert [d.account_no for d in prepared.ready] == ["A-10002"]
    assert len(prepared.blocked) == 1
    problem = prepared.blocked[0]
    assert problem.account_no == "A-10003"
    assert problem.reason == "unit_has_no_plan"  # a CODE — the screen groups on it
    # The denominator counts both, or "1 of 1" would be a true-looking lie.
    assert prepared.account_count == 2


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-3221 — since R3/R4 were switched on (PO, 2026-09-01) an account whose "
        "meter was simply NOT READ is refused out of the run entirely, with a "
        "sentence blaming a missing meter multiplier. Strict, on the "
        "test_def_438_parity precedent: the day the gap closes this XPASSES and "
        "fails the suite, so the file cannot go on describing a gap that is gone."
    ),
)
def test_us_bil_001_tc3__a_missing_read_is_a_decision_not_a_zero(brazos, dana):
    """BR-BIL-015. The account stays in the run, carrying the absence.

    Two wrong answers this rules out. Dropping the account bills nobody and
    tells nobody. Substituting `Quantity(0)` bills the base charge and states
    on the customer's bill that their meter was read and showed no usage —
    which is a different, checkable, and false claim.

    ⚠ **THIS IS THE RULE, AND THE PRODUCT NO LONGER DOES IT — `DEF-3221`, LIVE.**
    With `BILLING_RESOLUTION_STEPS` shipping `"R3,R4"` (PO, 2026-09-01), a unit
    with a meter and no committed read comes back in `prepared.blocked` as
    `ruled_path_refused`, not in `prepared.ready` with `("missing_read",
    "electric")` on the decisions list. **Both surfaces put a row in front of a
    human — the account is not hidden — but only the old one offers the clerk
    the estimate-or-skip choice this rule is about.** And the sentence they are
    shown is the wrong one: *"billing's read seam publishes no meter
    multiplier"*, because `metering.billing_multiplier_for` answers `None` both
    for a genuinely unrecorded factor and for a meter nobody has read, and
    `resolution_shadow` only tells `no_meter` apart from those two (`DEF-2875`
    taught it that much and stopped there).

    **NOT SILENTLY REWRITTEN TO MATCH THE PRODUCT.** Whether an unread meter
    should refuse an account is a rule question against `BR-BIL-015` and against
    the estimation flow, it was never put to the Product Owner, and answering it
    by editing an assertion is what `resolution_switch.py`'s own decision log
    warns about: *"A lane that makes the disagreements go away has destroyed the
    evidence this job exists to produce."*
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-7104", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-10004")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert prepared.blocked == ()  # not an error
    data = prepared.ready[0]  # still in the run
    assert data.readings[0].consumption is None  # NOT Decimal("0")
    assert data.readings[0].absent_reason == "no_read"
    # And it is on the decisions list, because billing it without anyone
    # looking would be a decision taken by omission.
    assert [(d.reason, d.service_code) for d in prepared.decisions] == [
        ("missing_read", "electric")
    ]


def test_us_bil_001_tc4__a_base_only_account_is_flagged_never_filtered(brazos, dana):
    """PO ruling 2026-08-11 — opt in or opt out, at prepare time, on screen.

    BR-CUS-055 says a vacation-hold account bills base charges. What it does
    NOT say is that this run must bill it, and the PO ruled that explicitly a
    staff choice. So it is gathered (it can be billed) and listed (someone must
    say so).
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7105", label="Unit A")
        an_account(brazos, unit["id"], "A-10005", status_code="vacation_hold")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert [d.account_no for d in prepared.ready] == ["A-10005"]  # not filtered out
    assert prepared.ready[0].behavior_class == "billable_base_only"
    assert [d.reason for d in prepared.decisions] == ["base_only_billing"]


def test_us_bil_001_tc5__a_closed_account_is_out_of_scope_and_not_an_exception(brazos, dana):
    """The other half of BR-CUS-055, and the one that keeps the screen usable.

    A closed account is not a problem to clear — it is correctly not in this
    run. Putting 300 of them on the exceptions screen every month is how a
    screen that matters stops being read. But its UNIT is still in the cycle
    with meters on it, so the run reports THAT: usage is being recorded
    against nobody.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7106", label="Unit A")
        an_account(brazos, unit["id"], "A-10006", status_code="closed")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert prepared.ready == ()
    assert [p.reason for p in prepared.blocked] == ["unit_has_no_billable_account"]
    assert prepared.blocked[0].unit_id == unit["id"]
    assert prepared.blocked[0].account_no is None  # the UNIT is the subject


def test_us_bil_001_tc6__an_empty_cycle_says_so_rather_than_returning_nothing(brazos, dana):
    """A run over a cycle nobody attached a service point to.

    Zero bills from an empty scope and zero bills from a successful run look
    identical on a screen that reports only counts. This one names the reason,
    so "nothing to bill" is a statement someone made rather than one the
    absence of data implied.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="06-EMPTY")
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert prepared.ready == ()
    assert [p.reason for p in prepared.blocked] == ["cycle_has_no_service_points"]
    assert prepared.account_count == 0


def test_us_bil_001_tc7__the_service_scope_narrows_the_run_and_is_recorded(brazos, dana):
    """US-BIL-001 §5 — an unchecked service is an EXPLICIT choice.

    A water-only run over an electric-only cycle covers nothing, and says so.
    The alternative — treating an empty scope match as "no scope, bill
    everything" — would bill every service on a run the staff had narrowed.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7107", label="Unit A")
        an_account(brazos, unit["id"], "A-10007")

        electric = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
            scope_services=("electric",),
        )
        water = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
            scope_services=("water",),
        )

    assert [d.account_no for d in electric.ready] == ["A-10007"]
    assert electric.scope_services == ("electric",)  # recorded, not inferred
    assert water.ready == ()
    assert [p.reason for p in water.blocked] == ["cycle_has_no_service_points"]


def test_us_bil_001_tc8__the_prepare_pass_writes_nothing(brazos, dana):
    """The PO's flow looks before it commits, so looking must not commit.

    A prepare that wrote a draft, an exclusion or a status change would make
    "let me check this first" an action with consequences — and a clerk who
    opened the screen twice would have done something twice.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7108", label="Unit A")
        an_account(brazos, unit["id"], "A-10008")

        runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

        assert billing_models.Invoice.objects.count() == 0
        assert billing_models.BillRun.objects.count() == 0
        assert billing_models.BillRunExclusion.objects.count() == 0
        assert billing_models.BillRunDecision.objects.count() == 0


def test_us_bil_004_tc16__calculate_turns_prepared_data_into_a_draft_bill(brazos, dana):
    """PHASE 2, end to end: stages 1 → 2 → 3-5 → 6, on real rows.

    412 kWh × 0.12 = 49.44 usage + 18.50 base = 67.94 taxable, no tax rule on
    this plan, so the draft totals 67.94. Every figure is the engine's; nothing
    here recomputes money, which is the only way this test can catch the engine
    changing.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7109", label="Unit A")
        an_account(brazos, unit["id"], "A-10009")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        invoice = runs.calculate_account(prepared.ready[0], service_date=SERVICE_DATE)

        assert invoice.status == billing_models.INVOICE_DRAFT
        # BR-BIL-063 (PO 2026-08-11): the draft carries its number. The PO was
        # shown that a re-run replaces the draft and spends another, and ruled
        # the gaps acceptable — *"if not use thats okay we will lose it."*
        assert invoice.invoice_no is not None
        assert invoice.due_date is None  # BR-BIL-024 — derived AT ISSUE
        assert invoice.subtotal == Decimal("67.940000")
        assert invoice.total == Decimal("67.940000")
        assert invoice.currency == "USD"

        lines = billing_models.InvoiceLine.objects.filter(invoice=invoice).order_by("kind")
        assert [(line.kind, line.amount) for line in lines] == [
            ("base", Decimal("18.500000")),
            ("usage", Decimal("49.440000")),
        ]
        usage_line = lines.get(kind="usage")
        assert usage_line.quantity == Decimal("412.000000")
        assert usage_line.unit == "kWh"  # rule 3, all the way onto the line
        # BR-BIL-010: the GL account is stamped AT ISSUE, not on a draft that
        # may never become a bill.
        assert usage_line.gl_account_id is None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-3221 — the same live gap as tc3, one phase along: the account never "
        "reaches `prepared.ready`, so `calculate_account` is never asked and "
        "`CALC_UNRESOLVED_READ` is never raised. Strict, so a fix XPASSES here."
    ),
)
def test_us_bil_004_tc17__an_undecided_missing_read_breaks_rather_than_bills(brazos, dana):
    """BR-BIL-015 — the run does not take the clerk's decision for them.

    Billing the remaining services would BE the "bill without this service"
    choice, silently, with nobody's name on it. The account breaks instead, and
    phase 3 puts it in front of a human.

    ⚠ **`DEF-3221` AGAIN, AND IT FAILS EARLIER THAN THE ASSERTION.** The account
    with no read is refused by the ruled path during PREPARE, so
    `prepared.ready` is empty and `prepared.ready[0]` raises `IndexError` before
    `calculate_account` is reached at all. The refusal is real and a human does
    see it; what this case pins is that the refusal comes from the CLERK'S
    undecided read rather than from the pricing chain, and that distinction is
    the whole of `BR-BIL-015`. See tc3 for why it is not rewritten.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-7110", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-10010")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        with pytest.raises(runs.GatherProblem) as raised:
            runs.calculate_account(prepared.ready[0], service_date=SERVICE_DATE)

    assert raised.value.reason == runs.CALC_UNRESOLVED_READ
    assert raised.value.service_code == "electric"


def test_us_bil_004_tc18__a_second_calculate_replaces_the_draft_rather_than_adding_one(
    brazos, dana
):
    """BR-BIL-023 — a draft is discardable free, so a re-run REPLACES.

    Accumulating would give the account two drafts for one period, and the
    summary would count both. The immutability trigger is what makes this safe
    to do bluntly: an ISSUED bill is refused by the database, so "delete the
    drafts" can never reach a real one.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7111", label="Unit A")
        account = an_account(brazos, unit["id"], "A-10011")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        runs.calculate_account(prepared.ready[0], service_date=SERVICE_DATE)
        second = runs.calculate_account(prepared.ready[0], service_date=SERVICE_DATE)

        drafts = billing_models.Invoice.objects.filter(account=account)
        assert drafts.count() == 1
        assert drafts.first().pk == second.pk
        assert billing_models.InvoiceLine.objects.filter(invoice__account=account).count() == 2


def test_us_bil_029_tc13__a_re_run_spends_another_number_and_the_first_is_lost(brazos, dana):
    """THE COST THE PO WAS SHOWN AND ACCEPTED, asserted so nobody rediscovers it.

    BR-BIL-063 allocates the number at draft creation; BR-BIL-023 makes a
    re-run REPLACE the draft. Both are ruled, and together they mean the
    replaced draft's number is simply gone. On a 500-account run re-run three
    times that is 1,500 numbers spent on 500 bills, and the series has gaps
    nobody can account for from the bills alone.

    The PO ruled that acceptable in the same sentence that ordered the change —
    *"if not use thats okay we will lose it; its okay; dont over complicate,
    keep it simple."* This test exists so the cost is VISIBLE in the suite
    rather than surfacing as an auditor's question, and so that anyone who
    later decides gaps are unacceptable finds the decision instead of a bug.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7112", label="Unit A")
        an_account(brazos, unit["id"], "A-10012")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        first = runs.calculate_account(prepared.ready[0], service_date=SERVICE_DATE).invoice_no
        second = runs.calculate_account(prepared.ready[0], service_date=SERVICE_DATE).invoice_no

    assert first is not None and second is not None
    assert first != second  # the re-run did NOT reuse the replaced draft's number
    # BR-TEN-035: "a number is never reused". The first is not re-issued to
    # anyone; it is spent.


# ── BR-MET-024 / OQ-043 — a disputed reading holds the account out ──────────
def test_us_met_013_tc3__a_disputed_read_holds_the_account_out_of_the_run(brazos, dana, marcus):
    """OQ-043's closure, verbatim: *"record+flag, hold account from run until
    SysAdmin clears (PO R6)"*; BR-MET-024 the same.

    **THIS IS THE HALF THAT MATTERS AND IT IS PROVED FROM THE BILLING SIDE.**
    Metering can record a marker all day; the rule is about what the BILL RUN
    does with it. Before 2026-08-16 there was no writer at all (DEF-046), so a
    reading a customer had told the utility was wrong was priced onto a bill as
    though they had agreed it — and no test could catch that, because no test
    could create the state.

    Also asserts what is NOT lost: the OTHER account in the same cycle bills
    normally. A hold that emptied the run would be a worse defect than the one
    it fixes.
    """
    from apps.metering import services as metering_services

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        held_unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7333", label="Unit A")
        quiet_unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7101", label="Unit B")
        an_account(brazos, held_unit["id"], "A-10001")
        an_account(brazos, quiet_unit["id"], "A-10002")

        # Both bill, before anyone disputes anything.
        before = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        assert sorted(d.account_no for d in before.ready) == ["A-10001", "A-10002"]
        assert before.blocked == ()

        read = metering_models.MeterRead.objects.get(asset__asset_no="M-7333")
        metering_services.dispute_read(
            marcus, read.id, {"reason": "customer reports vacant since July"}
        )

        after = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    # The disputed account is OUT of the run…
    assert [d.account_no for d in after.ready] == ["A-10002"]
    assert [p.account_no for p in after.blocked] == ["A-10001"]
    problem = after.blocked[0]
    assert problem.reason == runs.RUN_ACCOUNT_HELD_BY_DISPUTE
    # …and the exception says WHICH reading, WHY, and the quantity WITH ITS UNIT
    # (CLAUDE.md rule 3 — DEF-060's lesson: readings are for humans to read).
    assert "M-7333" in problem.detail
    # ⚠ **AMENDED 2026-08-30 — THIS READ `"412.000000 kWh"`, WHICH IS THE
    # STORAGE PRECISION AND IS NO LONGER WHAT A PERSON IS SHOWN.** BR-MET-144,
    # PO ruling 2026-08-27 on the live app, verbatim: *"decimal places and any
    # other issues you observe"* → *"2 decimals max, trailing zeros trimmed -
    # this is correct"*. `apps/metering/quantity_display.quantity_text` is that
    # rule, `usage_display` runs every quantity through it, and BR-MET-019's
    # six-place STORAGE is unchanged — only the last step before a human moved.
    # So a whole number now keeps no point at all: `412.000000` → `412`.
    # The unit is still asserted, because hard rule 3 is untouched by the
    # ruling and is the half this line exists for.
    assert "412 kWh" in problem.detail
    assert "412.000000" not in problem.detail, (
        "BR-MET-144: a quantity reaches a person at two decimals with trailing "
        "zeros trimmed, never at its storage precision"
    )
    assert "vacant since July" in problem.detail
    assert "System Admin" in problem.detail
    # BR-BIL-040: it lands on the Reads tab, beside the missing reads.
    assert problem.stage == "measure-consumption"
    # The denominator still counts it — "1 of 2" is only honest if the 2 counts
    # the held one (PreparedRun.account_count).
    assert after.account_count == 2


def test_us_met_013_tc3__clearing_the_dispute_returns_the_account_to_the_run(brazos, dana, marcus):
    """The other half of the same rule: *"until a System Admin clears"*."""
    from apps.metering import services as metering_services

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7333", label="Unit A")
        an_account(brazos, unit["id"], "A-10001")
        read = metering_models.MeterRead.objects.get(asset__asset_no="M-7333")
        metering_services.dispute_read(marcus, read.id, {"reason": "reads too high"})
        assert (
            runs.prepare_run(
                cycle_id=cycle.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                service_date=SERVICE_DATE,
            ).ready
            == ()
        )

        metering_services.clear_read_dispute(dana, read.id, {"resolution": "re-read confirmed"})

        released = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert [d.account_no for d in released.ready] == ["A-10001"]
    assert released.blocked == ()


def test_us_met_013_tc3__an_unpublished_dispute_seam_holds_rather_than_bills(
    brazos, dana, monkeypatch
):
    """A seam that cannot answer must not read as "no dispute".

    DEF-046's chip stuck at zero is the same failure one layer up: a silent zero
    reads as good news. If metering stops publishing the hold, the run says it
    could not check — it does not bill everyone as though nothing were disputed.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7101", label="Unit A")
        an_account(brazos, unit["id"], "A-10001")

        real_resolve = runs._resolve

        def _dark(module, attribute, kind="selectors"):
            if attribute == "dispute_holds_for_unit":
                return None
            return real_resolve(module, attribute, kind)

        monkeypatch.setattr(runs, "_resolve", _dark)
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert prepared.ready == ()
    assert prepared.blocked[0].reason == runs.RUN_ACCOUNT_HELD_BY_DISPUTE
    assert "has not published dispute_holds_for_unit" in prepared.blocked[0].detail


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-001@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — the PO's phase 1)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔
# exceptions: these prove PHASE 1 only — scope, gather, and what the screen is
#         shown. Nothing here prices a bill, writes a draft or releases
#         anything, because phases 2–5 do not exist yet. Stated so the file is
#         not read as proof that the run works
#         · `commit_read` writes a read row directly rather than through the
#         import wizard (the reads lane's own helper, same reasoning): these
#         rows are the past a run starts from, not the behaviour under test
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
