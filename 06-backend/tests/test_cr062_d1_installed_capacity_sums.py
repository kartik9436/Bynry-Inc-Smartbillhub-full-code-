# ── Trace ──────────────────────────────────────────────
# Change:   CR-062 tasks D1 + H2 — 🔒 rating math. The billable quantity of a
#           service whose size classes are CAPACITIES is the SUM of what is
#           installed, not a COUNT of the things it is installed in.
# Rules:    BR-RAT-090 (AMENDED 2026-09-02 — a capacity quantity is a COUNT for
#           a BANDED service and a SUM for a service whose size classes carry a
#           capacity) · BR-TEN-171 (which rows are bands and which are
#           capacities) · BR-MET-710 (metering publishes the observed fact on
#           billing's read seam and never invents one) · BR-MET-108 (the ruled
#           zero — a capacity service with no equipment bills $0.00 and the
#           zero is STAMPED, not silent) · CLAUDE.md hard rule 3 (a quantity
#           always carries an explicit unit; billing never assumes one)
# Tests:    this file
# Impacts:  apps/assets/selectors.billable_asset_size_classes ·
#           apps/metering/seams.py · apps/metering/selectors._stamp_installed_capacity ·
#           apps/billing/contracts.ServiceReading ·
#           apps/billing/stages/measure_consumption.py
# ───────────────────────────────────────────────────────
"""**THREE SOLAR PANELS OF 2 kW, 4 kW AND 8 kW BILL $196.00, NOT $42.00.**

The Product Owner's own worked example, 2026-09-02, verbatim:

    "In solar youa re still not doing it correctly - For example We have 10
     Types of Solar panel with various capaity 1 Kw, 2Kw 3Kw 4Kw so and SO
     forth ; on given Unit we have installed 3 panels with 2Kw, 4Kw and 8 Kw ,
     it means the totla capacity will be 14 Kw ; rate will be for 1 Kw = 14 $
     per KW then bill should be 14 X 14 = 156 $"

14 kW at $14.00 per kW is **$196.00**. Their message reads *156*; they were told
so in the same session and did not dispute it, and `$156` is written nowhere in
this repo — a wrong figure copied into a fixture becomes a wrong figure asserted
by a test, and then it is the product's answer.

**WHAT THIS FILE IS FOR.** `tenancy.service_size_classes.total_capacity` was
written by the CR-062 group A lane, is tested, and gives this exact example in
its own docstring — and **it had no caller outside its own module.** The bill run
still read `reading.asset_count`, so the array above billed **3 × $14.00 =
$42.00**: a 78% undercharge on every solar customer, on a document that foots and
prints. That is hard-won law 2 — *built is not wired* — with money on it.

WHAT DECIDES SUM FROM COUNT, AND WHY IT NAMES NO SERVICE
---------------------------------------------------------
Since CR-062 the phrase *capacity based* covers two arithmetics:

    trash  COUNTS what is installed   3 carts × $15.00       = $45.00
    solar  SUMS what is installed     2 + 4 + 8 kW × $14.00  = $196.00

**The distinction is read off configuration, never off a list of service names.**
Two questions, both already answered by data this product holds:

  1. `service_size_classes.capacity_uom_for_service(service)` — the unit this
     service's size classes SUM in, or `None` when they are BANDS and sum in no
     unit at all. Trash answers `None` (its carts are gallons and its dumpsters
     are cubic yards, so no total exists in any unit); fire answers `None`
     (`CR-063`: *"this will behave exactly like trash"*).
  2. Is that the unit **this tariff's price is quoted per**? A schedule reading
     *$14.00 per kW* bills the kW installed. A schedule reading *$10.00 per
     panel* bills the panels — and billing a kW total against a per-panel price
     would satisfy hard rule 3 in FORM and be wrong in SUBSTANCE, which is
     `DEF-497` one order of magnitude up.

So an ELEVENTH service (fire) landed on the counting side with no edit to any of
this, and a TWELFTH would land on whichever side its own configuration puts it —
`test_a_twelfth_service_needs_no_edit_here` proves that mechanically rather than
by comment.

RED FIRST (r11 step 2d, hard-won law 7). This whole file was run against an
untouched checkout of the branch tip (`758e6799`) in its own worktree, on real
PostgreSQL 16. **5 failed, 5 passed**, and the failures are quoted verbatim:

    tc1  AssertionError: assert Decimal('42.000000') == Decimal('196.00')
    tc4  Failed: DID NOT RAISE Exception
         — three panels of unrecorded type billed a quantity of 3 instead of
           refusing, which is a 30 kW array priced as a 3 kW one
    tc5  KeyError: 'installed_capacity'
    tc6  KeyError: 'installed_capacity'
    tc8  AttributeError: module 'apps.billing.stages.measure_consumption'
         has no attribute 'bills_installed_capacity'

**AND THE FIVE THAT PASSED AT THE TIP MATTER JUST AS MUCH:** `tc2` (trash
`$45.00`), `tc3` and `tc3b` (fire counts, `$110.00`), `tc7` (GT-15's `$40.00`)
and `tc9` (the seeded units agree) were GREEN before this change and are GREEN
after it. They are the half that must not move, and a fix that broke two
services to correct four would have shown up here.

⚠ **`$42.00` IS THIS FILE'S OWN FIXTURE AND NOT WHAT A SEEDED TENANT BILLED
WHEN THIS WAS WRITTEN.** The rate is set here explicitly, on purpose, so that
what is proved is the QUANTITY and nothing else — a test that leaned on the
seeded price would be proving two lanes' work at once and could not say which
one had failed.

⚠ **WHAT A SEEDED TENANT ACTUALLY BILLS, RE-READ FROM THE BRANCH RATHER THAN
ASSUMED (r11 step 0).** `CR-062` task E3 landed on the same day as this change:
`core/sample_fixture.CAPACITY_UNIT_PRICES` now carries the PO's **`$14.00` per
kW** for solar, `$3.00` for battery, `$4.50` per ERU and `$0.10` per Mbps, and
`CAPACITY_UNPRICED` / `CAPACITY_UOM` are retired. **So the price is real and the
quantity is now real, and a seeded solar line still comes out at `$0.00`** — for
a third reason that is neither lane's: **tasks D3–D8 plant no sized capacity
equipment**. The demo's `PV-0001` and `BAT-0001` are behind-the-meter devices
that declare NO service (`BR-AST-009`), so no solar service point holds them,
`installed_capacity` is a real **0 kW**, and the line prices zero honestly. The
day panels are planted with their size classes, this arithmetic bills them with
no further work.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.assets import services as asset_services
from apps.billing import models as billing_models
from apps.billing import gather, runs
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import service_size_classes as sizes

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_br_cus_068_master_bill import _by_service, _cycle

pytestmark = pytest.mark.django_db

# ── THE PO's OWN FIGURES ────────────────────────────────────────────────────
#: CR-062 task E3 — *"rate will be for 1 Kw = 14 $ per KW"*. The one price on
#: this table that came from the Product Owner rather than from this lane.
PER_KW = Decimal("14.000000")
#: 2 + 4 + 8. The array the PO described, panel for panel.
PO_PANELS = ("SOL-P2", "SOL-P4", "SOL-P8")
FOURTEEN_KW = Decimal("14.0000")
#: What this array is worth, and what it was worth before this change.
CORRECT = Decimal("196.00")
UNDERCHARGE = Decimal("42.00")

#: BR-RAT-090 / OQ-303 — trash's ratified price, unchanged by this CR.
PER_CART = Decimal("15.000000")
THREE_CARTS = Decimal("45.00")

AUG_START, AUG_END = date(2026, 8, 1), date(2026, 8, 31)
INSTALL = date(2026, 1, 5)


# ══════════════════════════════════════════════════════════════════════════
# fixture plumbing — one shape, driven by the service under test
# ══════════════════════════════════════════════════════════════════════════
def _declare_capacity(tenant, code):
    """BR-TEN-1180 — the utility declares this service priced by CAPACITY.

    Written on `tenant_services` directly because this file is about what READS
    the declaration, not about the screen that writes it.
    """
    service = tenancy_models.Service.objects.get(code=code)
    updated = tenancy_models.TenantService.objects.filter(tenant=tenant, service=service).update(
        billing_basis="capacity"
    )
    assert updated == 1, f"{code} has no tenant_services row to declare"


def _plan_priced_per(tenant, code, *, uom, rate):
    """ONE plan, ONE service, priced `rate` per `uom` with NO base charge.

    No base on purpose: the bill total IS the capacity line, so a figure below
    can only have come from the quantity. A base would let a wrong quantity hide
    inside a right-looking total.
    """
    plan = make_plan(tenant, name=f"{code} only", services=(code,))
    from apps.rating import selectors as rating_selectors

    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=Decimal("0"),
            # CLAUDE.md rule 3 — the unit the PRICE is quoted per. It is also
            # the question this whole change turns on: is it the unit this
            # service's capacities sum in?
            uom=uom,
            currency="USD",
            effective_from=date(2025, 1, 1),
            effective_to=None,
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=rate,
        )
    return plan


def _base_charge_code(tenant, code):
    """BR-RAT-088's base charge code, which R4 refuses the account without.

    ⚠ **AN EXPLICIT ZERO, AND IT IS NOT THE SAME AS LEAVING IT BLANK.** A blank
    base means *this size is not served* and stops the bill (`DEF-277`); a
    stored zero is a PRICE and prints `$0.00`. A capacity service's whole price
    IS its capacity line, so the utility states a base of zero deliberately —
    and it keeps every total below equal to the quantity times the rate, which
    is what makes a wrong quantity visible instead of hidden inside a subtotal.
    """
    from tests.base_code_naming import name_base_code

    # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES it — an unnamed
    # schedule takes no code from the list — so a price put on it bills.
    return name_base_code(
        tenant,
        rating_models.Charge.objects.create(
            tenant=tenant,
            code=f"BASE-{code[:3].upper()}",
            name=f"{code.title()} base service",
            charge_type="recurring",
            amount_rule="flat",
            amount=Decimal("0"),
            service=tenancy_models.Service.objects.get(code=code),
            is_base=True,
        ),
    )


def _equipment(actor, unit_id, code, kind, specs):
    """The things standing on the unit — `specs` is `(size_class, ...)`.

    A `None` entry is a real state and not a shortcut: a panel loaded before
    anybody recorded which type it is. `BR-AST-500` allows it and this file
    asserts what a bill does about it.
    """
    made = []
    for n, size_class in enumerate(specs, start=1):
        payload = {
            "type": kind,
            "asset_no": f"{kind.upper()}-{code[:2].upper()}{n:03d}",
            "service": code,
            "unit_id": str(unit_id),
            "install_date": INSTALL.isoformat(),
        }
        if size_class is not None:
            payload["size_class"] = size_class
        made.append(asset_services.create_asset(actor, payload))
    return made


def _world(actor, tenant, *, cycle_code, code, kind, uom, rate, specs):
    """A unit taking ONE capacity service, with `specs` equipment on it."""
    from apps.tenancy import services as tenancy_services
    from apps.metering import premises_owners

    tenancy_services.update_tenant_service(actor, code, {"enabled": True})
    _declare_capacity(tenant, code)
    cycle = _cycle(tenant, cycle_code)
    plan = _plan_priced_per(tenant, code, uom=uom, rate=rate)
    _base_charge_code(tenant, code)
    owner = premises_owners.create_premises_owner(
        actor, {"name": f"Mesa Vista {cycle_code}", "category": "landlord"}
    )
    premises = make_premises(
        actor,
        address_line=f"9 Mesa Vista {cycle_code}",
        services_available=[code],
        owner_id=owner["id"],
    )
    unit = make_unit(actor, premises["id"], label="Unit 1", services=[code])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    _equipment(actor, unit["id"], code, kind, specs)
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": AUG_START.isoformat(),
            "contact": {"full_name": "Ana Alvarez", "phone": "555-0100"},
            # BR-CUS-1023 (PO 2026-09-01) — *"Customer ID - minimum name and one
            # ID - minimum"*. A person needs a name AND one identifier, so the
            # account refuses to open without this block and no bill would ever
            # be computed. Nothing in this file turns on WHO the customer is;
            # it is here so the fixture reaches the arithmetic under test.
            "customer": {
                "display_name": "Ana Alvarez",
                "kind": "person",
                "identity": {"phone": "555-0100"},
            },
            "addresses": [
                {"kind": "mailing", "line1": "9 Mesa Vista", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    account = customer_models.Account.objects.get(pk=created["id"])
    return cycle, unit, account


def _bill(tenant, cycle, tag, *, start=AUG_START, end=AUG_END):
    prepared = runs.prepare_run(
        cycle_id=cycle.id, period_start=start, period_end=end, service_date=end
    )
    assert prepared.ready, "the fixture produced no billable account — the test would be vacuous"
    run = billing_models.BillRun.objects.create(
        tenant=tenant, cycle=cycle, period_start=start, period_end=end, idempotency_key=tag
    )
    return runs.calculate_account(prepared.ready[0], bill_run=run, service_date=end)


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DELIVERABLE — the Product Owner's own array bills $196.00
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__two_plus_four_plus_eight_kilowatts_bill_one_hundred_and_ninety_six(brazos, dana):
    """**2 + 4 + 8 kW = 14 kW, at $14.00 per kW = `$196.00`.**

    Produced by the LIVE bill run off real rows: three `pv` assets standing on
    the unit's solar service point, each carrying its ratified panel type. Before
    this change the same account billed **`$42.00`** — the panels were COUNTED,
    so a 14 kW array priced exactly like three 1 kW ones.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(
            dana,
            brazos,
            cycle_code="SOL-1",
            code="solar",
            kind="pv",
            uom="kW",
            rate=PER_KW,
            specs=PO_PANELS,
        )

        invoice = _bill(brazos, cycle, "cr062-d1-tc1")

        assert _by_service(invoice)["solar"] == CORRECT
        assert invoice.total == CORRECT
        assert invoice.total != UNDERCHARGE, (
            "the panels were counted rather than summed — this is the defect, "
            "and $42.00 is a 78% undercharge on the PO's own example"
        )
        # CLAUDE.md rule 3 — the quantity is 14 and it says what 14 of.
        usage = [line for line in invoice.lines.all() if line.quantity is not None]
        assert len(usage) == 1
        assert (usage[0].quantity, usage[0].unit) == (Decimal("14.000000"), "kW")


# ══════════════════════════════════════════════════════════════════════════
# (2) TRASH IS UNCHANGED — the half most easily broken by a careless fix
# ══════════════════════════════════════════════════════════════════════════
def test_tc2__three_carts_still_bill_forty_five_dollars(brazos, dana):
    """**3 × `$15.00` = `$45.00`, still COUNTED.**

    PO verbatim, statement (3): *"Trash - it is capacity based and Cart sizes
    will decide price X how many Cart"*. Trash's seven rows are three CARTS
    measured in gallons and four DUMPSTERS measured in cubic yards, so there is
    no unit in which their total is a quantity — `capacity_uom_for_service`
    answers `None` and this account must keep counting.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(
            dana,
            brazos,
            cycle_code="CART-1",
            code="trash",
            kind="container_cart",
            uom="cart",
            rate=PER_CART,
            specs=("CART-96", "CART-96", "CART-35"),
        )

        invoice = _bill(brazos, cycle, "cr062-d1-tc2")

        assert _by_service(invoice)["trash"] == THREE_CARTS
        usage = [line for line in invoice.lines.all() if line.quantity is not None]
        # ⚠ **AMENDED 2026-09-02 — THE TOTAL IS UNCHANGED AND THE SHAPE IS THE
        # RULING'S.** This asserted ONE line of `3 cart` until the decision log
        # of that day narrowed *"one connection, one size"* to METERED
        # connections: *"For a capacity service billed by a COUNT — today trash
        # and fire — the bill carries ONE LINE PER SIZE, and the quantity on
        # each line is the count of items of that size."* This unit carries two
        # `CART-96` and one `CART-35`, so it is now **two lines** — and the
        # ruled `$45.00` above does not move, because the seeded trash schedule
        # prices every band at `$15.00`.
        #
        # The count is still a COUNT and that is what this case exists to prove:
        # a 96-gallon cart and a 35-gallon one are not `131 gallons` of
        # anything. `total_capacity("trash", …)` still REFUSES (tc3).
        #
        # ⚠ **AMENDED AGAIN 2026-09-30 (`DEF-BIL-8151`) — ONE LINE PER SERVICE.**
        # PO, decision log *"ONE-TIME BILL: SIX ANSWERS"* (5), verbatim: *"per
        # service"* — the per-size lines (and the base) print as ONE trash line
        # whose quantity is the COUNT, `3 cart`, and whose wording names the
        # sizes. It asserted two lines, `1 cart` and `2 cart`, until then; the
        # `$45.00` did not move and the quantity is still a count of carts.
        assert sorted((line.quantity, line.unit) for line in usage) == [
            (Decimal("3.000000"), "cart"),
        ]


# ══════════════════════════════════════════════════════════════════════════
# (3) FIRE IS UNCHANGED — the ELEVENTH service, and it counts
# ══════════════════════════════════════════════════════════════════════════
def test_tc3__fire_still_counts_and_its_price_list_still_multiplies_per_size():
    """**CR-063: *"this will behave exactly like trash"*.**

    Two assertions, and they are the mechanical form of that sentence rather
    than a reading of it: fire SUMS IN NO UNIT, and its price-list arithmetic —
    one 6" line at `$60.00` plus two 2" lines at `$12.00` — is `$84.00`.

    ⚠ **THIS CASE USED TO SAY `$110.00` AND THE FIGURE MOVED BY PO RULING, NOT
    BY A CR-062 CHANGE.** PO 2026-09-03: *"remove private hydrants from list"*.
    The old worked pair was a 6" line and two private hydrants at `$25.00`; the
    hydrant is now an asset rather than a utility-service size, so the same
    warehouse bills **`$60.00`** and this case carries the per-size arithmetic
    on two DIAMETERS instead. **Nothing CR-062 ruled is touched**: fire counts,
    solar sums, and that fence is exactly where it was.
    """
    assert sizes.capacity_uom_for_service("fire") is None
    assert sizes.capacity_uom_for_service("trash") is None
    with pytest.raises(sizes.NotACapacityService):
        sizes.total_capacity("fire", ["FL-6", "FL-2", "FL-2"])
    with pytest.raises(sizes.NotACapacityService):
        sizes.total_capacity("trash", ["CART-96"])
    assert sizes.fire_charge({"FL-6": 1, "FL-2": 2}) == Decimal("84.00")
    assert sizes.fire_charge({"FL-6": 1}) == Decimal("60.00")
    assert sizes.fire_charge({"FL-2": 1}) == Decimal("12.00")


def test_tc3b__a_fire_unit_bills_a_count_through_the_live_run(brazos, dana):
    """Fire's quantity through the bill run is still a COUNT of its connections.

    Three pieces of fire equipment on one unit at `$20.00` each bill `$60.00` —
    the arithmetic trash uses. **Their size classes are DIFFERENT** (`FL-6` and
    two `FL-2`), which is exactly the array that would have been summed if this
    change had reached the wrong side of the fence.

    ⚠ The three used to be a 6" line and two private hydrants; `HYD` left fire's
    size list by PO ruling on 2026-09-03. The fixture prices every band at
    `$20.00`, so **the `$60.00` this case asserts did not move** — only which
    codes stand on the unit did.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(
            dana,
            brazos,
            cycle_code="FIRE-1",
            code="fire",
            kind="backflow",
            uom="connection",
            rate=Decimal("20.000000"),
            specs=("FL-6", "FL-2", "FL-2"),
        )

        invoice = _bill(brazos, cycle, "cr062-d1-tc3b")

        usage = [line for line in invoice.lines.all() if line.quantity is not None]
        # ⚠ **AMENDED 2026-09-02, for the reason `tc2` above records** — one
        # 6" line and two 2" lines are two bill lines now, not one of `3`. This
        # fixture prices every band at `$20.00`, so the `$60.00` is unmoved;
        # `test_cr063_c3_fire_priced` is where the SEEDED per-size prices are
        # asserted (`1 × $60.00 + 2 × $12.00 = $84.00`, since the PO withdrew
        # the private hydrant on 2026-09-03).
        # ⚠ **AND AGAIN 2026-09-30 (`DEF-BIL-8151`)** — PO *"per service"*: the
        # two per-size lines print as ONE fire line of `3 connection`. The
        # `$60.00` is unmoved and the quantity is still a COUNT.
        assert sorted((line.quantity, line.unit) for line in usage) == [
            (Decimal("3.000000"), "connection"),
        ]
        assert _by_service(invoice)["fire"] == Decimal("60.00")


# ══════════════════════════════════════════════════════════════════════════
# (4) A PANEL NOBODY TYPED REFUSES — it is never billed as one kilowatt
# ══════════════════════════════════════════════════════════════════════════
def test_tc4__panels_with_no_recorded_type_refuse_rather_than_bill_a_count(brazos, dana):
    """**Three panels whose type nobody recorded do not bill 3 kW.**

    This is `BR-RAT-090`'s own distinction moved up one level: *"'no carts
    recorded' and 'zero carts' are different facts and only one of them is
    billable"*. A schedule quoting `$14.00 per kW` against three panels of
    unknown capacity has no quantity — inventing `3` would bill a 30 kW array at
    the price of a 3 kW one, on a document that looks entirely normal.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(
            dana,
            brazos,
            cycle_code="SOL-2",
            code="solar",
            kind="pv",
            uom="kW",
            rate=PER_KW,
            specs=(None, None, None),
        )

        with pytest.raises(Exception) as refusal:
            _bill(brazos, cycle, "cr062-d1-tc4")

        assert "solar" in str(refusal.value)


# ══════════════════════════════════════════════════════════════════════════
# (5) THE RULED ZERO SURVIVES — no equipment still bills $0.00, STAMPED
# ══════════════════════════════════════════════════════════════════════════
def test_tc5__a_unit_with_no_equipment_bills_zero_and_never_refuses(brazos, dana):
    """**`BR-MET-108`'s ruled zero — a real answer that BILLS, not an absence.**

    ⚠⚠ **AMENDED 2026-09-30 — SUPERSEDED BY THE PO: NO ASSET = NOT IN SERVICE.**
    PO ruling of that date: *"if unit has 6 utility services and user only add
    1 or 3 assets to it - it means you will consider only 3 service point
    exist"*, and a service not in service prints NO line (*"sane no line - and
    use 0"*). A solar connection with nothing on it is therefore NOT billed at
    all: no line and no base. This world's plan prices solar ALONE, so there is
    nothing left to bill and the account stops on `GATHER_NO_TARIFF` (*"a bill
    with no services is not a $0.00 bill"*), exactly as a unit with no point at
    all does (`test_br_bil_301_*::tc5`). RED against the ruling's code before
    this edit: `the fixture produced no billable account`.

    `DEF-3084` (the zero line the pricing stage dropped) is moot under the
    ruling: there is no line to drop.
    """
    with tenant_ctx(brazos):
        cycle, unit, _account = _world(
            dana,
            brazos,
            cycle_code="SOL-3",
            code="solar",
            kind="pv",
            uom="kW",
            rate=PER_KW,
            specs=(),
        )

        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=AUG_START, period_end=AUG_END, service_date=AUG_END
        )
        assert prepared.ready == ()
        assert [b.reason for b in prepared.blocked] == [gather.GATHER_NO_TARIFF]
        assert [d.reason for d in prepared.decisions if d.reason == "missing_read"] == []


def test_tc6__metering_publishes_the_installed_total_with_its_unit(brazos, dana):
    """`BR-MET-710` — the sum is METERING's published fact, carried with its unit.

    `billing_reads_for_unit` is the one seam billing reads, and a total that
    travelled without its unit would be a number nobody could price (hard rule
    3). The count is published BESIDE it and not instead of it: what a line was
    counted from stays visible even when it is not what was billed.
    """
    with tenant_ctx(brazos):
        _cycle_row, unit, _account = _world(
            dana,
            brazos,
            cycle_code="SOL-4",
            code="solar",
            kind="pv",
            uom="kW",
            rate=PER_KW,
            specs=PO_PANELS,
        )

        rows = metering_selectors.billing_reads_for_unit(
            unit["id"], period_start=AUG_START, period_end=AUG_END
        )
        (solar,) = [row for row in rows if row["service_code"] == "solar"]
        assert solar["installed_capacity"] == FOURTEEN_KW
        assert solar["capacity_uom"] == "kW"
        assert solar["asset_count"] == 3


# ══════════════════════════════════════════════════════════════════════════
# (7) THE SIGNED CAPACITY FIGURES DO NOT MOVE — GT-15
# ══════════════════════════════════════════════════════════════════════════
def test_tc7__gt15s_forty_dollar_solar_and_twenty_four_dollar_battery_are_untouched(brazos, dana):
    """**B5 GT-15 — *solar 4 units @ $10 = $40.00* — priced PER PANEL, unmoved.**

    GT-15's utility quotes its price per `panel`, which is not the unit solar's
    capacities sum in, so its quantity is still the COUNT of panels. That is the
    whole discriminator working in the direction nobody looks at: this change
    adds an arithmetic for schedules priced in the capacity's own unit and takes
    none away from schedules that are not.

    ⚠ GT-15's `$40.00` also sits inside `GT-17`'s ❄️ FROZEN taxable base of
    `221.90`, so moving it would be a finance re-sign (HUMAN-GUIDE §6) and not a
    test edit.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(
            dana,
            brazos,
            cycle_code="SOL-5",
            code="solar",
            kind="pv",
            uom="panel",
            rate=Decimal("10.000000"),
            specs=(None, None, None, None),
        )

        invoice = _bill(brazos, cycle, "cr062-d1-tc7")

        assert _by_service(invoice)["solar"] == Decimal("40.00")
        usage = [line for line in invoice.lines.all() if line.quantity is not None]
        assert (usage[0].quantity, usage[0].unit) == (Decimal("4.000000"), "panel")


# ══════════════════════════════════════════════════════════════════════════
# (8) A TWELFTH SERVICE NEEDS NO EDIT HERE
# ══════════════════════════════════════════════════════════════════════════
def test_tc8__a_twelfth_service_lands_on_the_right_side_with_no_edit(monkeypatch):
    """**No service is named anywhere in this decision, and this proves it.**

    Fire arrived as the eleventh service on 2026-09-02 and landed on the COUNTING
    side with nobody editing a billing file, because *"exactly like trash"* is a
    fact about its ratified size classes. A twelfth arrives the same way: a
    service whose rows carry a capacity SUMS, a service whose rows are labels
    COUNTS, and the code asks the rows rather than the name.
    """
    from apps.billing.stages import measure_consumption as stage

    class _Reading:
        absent_reason = stage.ABSENT_SERVICE_NOT_METERED
        asset_count = 3
        installed_capacity = Decimal("30.0000")
        capacity_uom = "MW"

    class _Tariff:
        service = "hydrogen"
        billed_unit = "MW"

    # A service this repo has never heard of, priced in the unit its capacities
    # sum in, bills the SUM — with no entry in any list in any billing file.
    assert stage.bills_installed_capacity(_Reading(), _Tariff()) is True

    # The same service priced per THING bills the COUNT, for the same reason
    # trash does: a total in MW is not what a per-stack price multiplies.
    class _PerStack(_Tariff):
        billed_unit = "stack"

    assert stage.bills_installed_capacity(_Reading(), _PerStack()) is False

    # And a service whose size classes are BANDS sums in no unit at all, so the
    # question never even arises.
    class _Banded(_Reading):
        installed_capacity = None
        capacity_uom = None

    assert stage.bills_installed_capacity(_Banded(), _Tariff()) is False


def test_tc9__the_ratified_capacity_unit_and_the_seeded_billed_unit_agree():
    """**The seeded product sums by construction, not by luck.**

    `tenancy.services.SERVICE_DEFAULT_UOMS` gives every provisioned tenant its
    primary unit, and `_capacity_uom` builds the seeded capacity schedule from
    it. So for the four summing services that unit MUST equal the unit their
    size classes sum in, or the seeded utility would quietly bill counts. This
    case is what makes the agreement a checked fact rather than a coincidence
    somebody has to keep noticing.
    """
    from apps.tenancy.services import SERVICE_DEFAULT_UOMS

    summing = {
        code: sizes.capacity_uom_for_service(code)
        for code in sizes.SERVICE_ORDER
        if sizes.capacity_uom_for_service(code) is not None
    }
    assert summing == {
        "storm_water": "ERU",
        "solar": "kW",
        "broadband": "Mbps",
        # `DEF-TEN-9021` - the fifth since CR-080 (PO 2026-09-07, *"connected
        # tonnage - it is capacity not metering"*): a 100-ton and a 25-ton
        # connection are 125 tons.
        "thermal_heat": "ton",
        "battery": "kW",
    }
    for code, uom in summing.items():
        assert SERVICE_DEFAULT_UOMS[code].primary == uom, (
            f"{code} sums in {uom} and the seed bills it in "
            f"{SERVICE_DEFAULT_UOMS[code].primary} — a provisioned tenant would count"
        )
