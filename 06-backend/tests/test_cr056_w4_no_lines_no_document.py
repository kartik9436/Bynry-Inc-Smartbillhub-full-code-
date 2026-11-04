# ── Trace ──────────────────────────────────────────────
# Rules:    BR-BIL-1024 (no lines, no document — decided at the END of the run,
#           after pricing) · BR-BIL-1025 (an account with nothing to bill is
#           SILENT, not an exception; an unoccupied unit that finds no owner
#           account still IS one) · BR-CUS-170 (the empty unit's base charge on
#           the owner's bill) · BR-CUS-1010 (the master account hangs off the
#           address) · OQ-670 (a service the plan prices nowhere bills a $0.00
#           LINE — which is why the test is on LINES and never on the TOTAL)
# Pin:      1408 Elm Street still bills $41.20 + $28.40 = $69.60. Nothing in
#           this file may move it and tc_pin re-measures it here.
# Defects:  DEF-2960 (an unoccupied unit whose base charge IS billed to the
#           owner was reported as a unit with no billable account) · DEF-572
#           (the same false alarm on a COVERED common area, fixed 2026-08-22,
#           whose test passes over the empty-unit half)
# Source:   PO ruling 2026-08-31, CR-056 ruling 1 and its four consequences
# ───────────────────────────────────────────────────────
"""CR-056 W4 — what a run does with an account that has nothing to bill.

The PO ruled on 2026-08-31 that **every address gets its owner a Master
Account**, so accounts that cover nothing now exist on purpose. Three things
follow and each is asserted here:

    19 · no lines, no document — and it is decided AFTER pricing
    20 · a silent account never reaches the exceptions screen
    22 · an unoccupied unit that finds NO owner account still does

`$0.00` is deliberately NOT the test. `OQ-670` puts a `$0.00` line on a real
document, so a suppression keyed on the total would delete the bill that ruling
exists to produce. tc19b is that case, written as the inversion.
"""

from decimal import Decimal

import pytest

from apps.billing import gather, models as billing_models, runs, single
from apps.billing.stages import assemble_document as assemble_stage
from apps.customers import models as customer_models, services as customer_services
from apps.metering import models as metering_models, services as metering_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_us_met_reads_helpers import a_meter, commit_read
from tests.test_br_cus_068_master_bill import (
    COMMON_BILL,
    HALLWAY,
    IRRIGATION,
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    _by_service,
    _cycle,
    _priced_plan,
    _run,
    a_master,
    elm_1408,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _the_ruled_chain_is_off(settings):
    """**THE OFF STATE, STATED RATHER THAN INHERITED** — the idiom
    `test_br_bil_870_resolution_switch.py` established when the PO ruled R3 and
    R4 in on 2026-09-01.

    ⚠ **AND HERE IT IS ALSO A WORK-AROUND FOR A LIVE DEFECT, WHICH IS SAID OUT
    LOUD RATHER THAN LEFT AS A LINE NOBODY EXPLAINS (`DEF-2966`).** `1408 Elm`'s
    fixture writes its `TariffVersion` rows through the ORM and declares no
    `is_base` CHARGE CODE, so with `R3,R4` served — the shipped default since
    `v2.115.0` — the ruled path refuses the account by name before a single line
    is priced, and **`CR-056`'s own signed `$69.60` cannot be measured at all**.
    That is `DEF-2923`'s shape meeting a fixture instead of a tenant.

    **It is not this lane's to fix** (`resolution_switch.py`, `rating/services.py`
    and `config/settings/base.py` all belong to the pricing-switch lane), and it
    is not this lane's to hide either: the state is written down here, filed as
    `DEF-2966`, and reported. What this file measures is what THIS lane's change
    does to the figure, against the path the figure was signed on.
    """
    settings.BILLING_RESOLUTION_STEPS = ""
    return settings


#: The empty flat's standing charge — the electric base of `_priced_plan`.
EMPTY_UNIT_BASE = Decimal("12.00")


def _metered_unit(
    actor,
    tenant,
    cycle,
    plan,
    premises,
    *,
    label,
    asset_no,
    service="electric",
    uom="kWh",
    used="90.000000",
    read=True,
):
    """One ORDINARY unit (not a common area), metered, in the cycle, on the plan."""
    unit = make_unit(actor, premises["id"], label=label, services=[service])
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"], service=service, uom=uom)
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    if read:
        commit_read(
            actor,
            asset["id"],
            day=PERIOD_END.isoformat(),
            value=str(Decimal("1000") + Decimal(used)),
            prior_value="1000",
            consumption=str(used),
            unit=uom,
        )
    return unit


# ══════════════════════════════════════════════════════════════════════════
# THE PIN — CR-056's own regression, re-measured on this lane's code
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w4_pin__1408_elm_still_bills_69_60(brazos, dana):
    """`$41.20` hallway + `$28.40` irrigation = **`$69.60`** on ONE owner
    document, unchanged by everything in this file.

    Re-measured here rather than trusted from `test_br_cus_068_master_bill.py`,
    because the change under test is *when a document is written at all* and a
    figure that is only asserted somewhere else is a figure this lane never
    checked.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "W4-PIN")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        a_master(dana, premises)

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        assert prepared.blocked == (), prepared.blocked
        assert prepared.silent == (), prepared.silent
        invoice = runs.calculate_account(
            prepared.ready[0], bill_run=_run(brazos, cycle, "w4-pin"), service_date=SERVICE_DATE
        )
        assert _by_service(invoice) == {"electric": HALLWAY, "water": IRRIGATION}
        assert invoice.total == COMMON_BILL


# ══════════════════════════════════════════════════════════════════════════
# TASK 19 — NO LINES, NO DOCUMENT
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w4_tc19a__a_bill_with_no_lines_writes_no_invoice_row(brazos, dana):
    """**Stage 6 answers `None` and creates nothing** when the priced bill
    carries no lines (`BR-BIL-1024`).

    Driven at the stage rather than through a whole run, because that is where
    the ruling puts the decision — *"at the END of the run, after pricing"* —
    and because the point of the rule is that NOTHING upstream had to predict
    it. The priced object is a stand-in with an empty `lines`, which is exactly
    what the engine returns for an account with no services at all.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "W4-19A")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        a_master(dana, premises)
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        data = prepared.ready[0]
        bill_run = _run(brazos, cycle, "w4-19a")

        class _NothingPriced:
            currency = "USD"
            taxable_subtotal = Decimal("0")
            tax_total = Decimal("0")
            total = Decimal("0")
            lines = ()

        # The stage takes the usage the run already measured; built the same
        # way `calculate_account` builds it rather than re-derived here.
        from apps.billing.stages.measure_consumption import measure_consumption
        from apps.billing.stages.resolve_subscription import resolve_subscription

        usage = measure_consumption(resolve_subscription(data), data)
        written = assemble_stage.assemble_document(
            usage=usage,
            priced=_NothingPriced(),
            tenant_id=brazos.id,
            account_id=data.account_id,
            bill_run=bill_run,
            period_start=data.period_start,
            period_end=data.period_end,
            service_date=SERVICE_DATE,
        )
        assert written is None
        assert billing_models.Invoice.objects.filter(bill_run=bill_run).count() == 0


def test_cr056_w4_tc19b__a_zero_line_is_still_a_document(brazos, dana):
    """**THE INVERSION, and it is the one that matters.** `OQ-670` (PO
    2026-08-27, *"(b) Bill $0.00"*) puts a `$0.00` LINE on a real document. A
    suppression keyed on the TOTAL rather than on the LINES would delete it —
    silently, for every account whose services all price to nothing.

    Same stage, same empty totals, ONE line. A document is written.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "W4-19B")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        a_master(dana, premises)
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        data = prepared.ready[0]
        bill_run = _run(brazos, cycle, "w4-19b")

        class _ZeroLine:
            kind = "usage"
            # `BR-BIL-010` — a usage line NAMES the service it charged for, or
            # the bill could never be issued and per-service revenue could never
            # be reported from it. The first draft of this stub omitted it and
            # the rule refused the document, correctly.
            service = "electric"
            description = "Electric — priced nowhere"
            quantity = None
            unit = None
            unit_price = None
            amount = Decimal("0")
            taxable = False
            tax_id = None
            tariff_version_id = None
            charge_id = None
            service_code = None

        class _ZeroPriced:
            currency = "USD"
            taxable_subtotal = Decimal("0")
            tax_total = Decimal("0")
            total = Decimal("0")
            lines = (_ZeroLine(),)

        from apps.billing.stages.measure_consumption import measure_consumption
        from apps.billing.stages.resolve_subscription import resolve_subscription

        usage = measure_consumption(resolve_subscription(data), data)
        written = assemble_stage.assemble_document(
            usage=usage,
            priced=_ZeroPriced(),
            tenant_id=brazos.id,
            account_id=data.account_id,
            bill_run=bill_run,
            period_start=data.period_start,
            period_end=data.period_end,
            service_date=SERVICE_DATE,
        )
        assert written is not None, "a $0.00 LINE is a document (OQ-670)"
        assert written.total == Decimal("0")
        assert written.lines.count() == 1


def test_cr056_w4_tc19c__a_rerun_that_now_prices_nothing_leaves_no_stale_draft(brazos, dana):
    """`BR-BIL-023`'s draft replacement happens BEFORE the emptiness is judged.

    An account that drafted last pass and prices nothing this pass must end with
    NO document — not with last pass's, which would be a bill nobody can explain
    and which the next issue would send.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "W4-19C")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        a_master(dana, premises)
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        data = prepared.ready[0]
        bill_run = _run(brazos, cycle, "w4-19c")
        first = runs.calculate_account(data, bill_run=bill_run, service_date=SERVICE_DATE)
        assert first is not None and first.total == COMMON_BILL

        class _NothingPriced:
            currency = "USD"
            taxable_subtotal = Decimal("0")
            tax_total = Decimal("0")
            total = Decimal("0")
            lines = ()

        from apps.billing.stages.measure_consumption import measure_consumption
        from apps.billing.stages.resolve_subscription import resolve_subscription

        usage = measure_consumption(resolve_subscription(data), data)
        again = assemble_stage.assemble_document(
            usage=usage,
            priced=_NothingPriced(),
            tenant_id=brazos.id,
            account_id=data.account_id,
            bill_run=bill_run,
            period_start=data.period_start,
            period_end=data.period_end,
            service_date=SERVICE_DATE,
        )
        assert again is None
        assert billing_models.Invoice.objects.filter(bill_run=bill_run).count() == 0
        assert billing_models.InvoiceLine.objects.filter(invoice__bill_run=bill_run).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# TASKS 20 + 22 — WHAT IS AN EXCEPTION AND WHAT IS NOT
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w4_tc22__an_empty_unit_the_owner_pays_for_is_not_an_exception(brazos, dana):
    """**`DEF-2960`.** An unoccupied unit whose base charge IS billed to the
    owner's master account was reported by every run since 2026-08-27 as
    *"in this cycle but has no billable account"*.

    The fixture is `1408 Elm` with a FOURTH unit that is metered, on the plan,
    in the cycle and occupied by nobody — so `BR-CUS-170` puts its `$12.00`
    electric base on the owner's bill (PO 2026-08-31: the charge is per UNIT).

    RED BEFORE THE FIX: the unit appears in `prepared.blocked` under
    `unit_has_no_billable_account`, on the tab a clerk is meant to act on,
    about a unit that IS billed.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "W4-22")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        empty = _metered_unit(
            dana,
            brazos,
            cycle,
            plan,
            premises,
            label="Unit D (empty)",
            asset_no="M-4111",
            read=False,
        )
        a_master(dana, premises)

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        assert [p.unit_id for p in prepared.blocked] == [], prepared.blocked
        assert prepared.silent == ()

        invoice = runs.calculate_account(
            prepared.ready[0], bill_run=_run(brazos, cycle, "w4-22"), service_date=SERVICE_DATE
        )
        # The owner's document carries the two common areas AND the empty
        # unit's standing charge: $41.20 + $28.40 + $12.00.
        assert invoice.total == COMMON_BILL + EMPTY_UNIT_BASE
        assert customer_models.Account.objects.filter(unit_id=empty["id"]).count() == 0


def test_cr056_w4_tc22b__an_empty_unit_with_no_owner_account_IS_an_exception(brazos, dana):
    """**THE OTHER HALF, and it is task 22's own sentence.** *"No lines because
    nothing falls to it"* and *"no lines although the premises HAS an unoccupied
    unit"* are different facts and only one of them is good news (PO 2026-08-31,
    consequence 3).

    The SAME fixture with NO master account: the empty unit's standing charge
    has nowhere to post, and the run says so.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "W4-22B")
        plan = _priced_plan(brazos)
        premises, hallway, irrigation = elm_1408(dana, brazos, cycle, plan)
        empty = _metered_unit(
            dana,
            brazos,
            cycle,
            plan,
            premises,
            label="Unit D (empty)",
            asset_no="M-4112",
            read=False,
        )
        # No `a_master(...)` — nobody owns an account at this address.

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        reported = {p.unit_id for p in prepared.blocked}
        assert empty["id"] in reported, prepared.blocked
        assert {p.reason for p in prepared.blocked} == {runs.RUN_UNIT_HAS_NO_ACCOUNT}
        # The two common areas are reported for the same reason and that is
        # correct here: with no master account nobody pays for them either.
        assert {hallway["id"], irrigation["id"]} <= reported


def test_cr056_w4_tc20__a_silent_owner_account_is_classified_silent(brazos, dana):
    """**Task 20's classifier, and the door that does not reach it yet.**

    An owner's account at an address he occupies himself covers nothing and has
    no unoccupied unit, so `gather.nothing_to_bill` answers **True** — and the
    run therefore files it as SILENT rather than as an exception. That is the
    assertion this case exists for.

    ⚠ **AND THE SECOND HALF PINS A DEFECT RATHER THAN A DESIGN — `DEF-2967`.**
    Such an account cannot be billed single-account AT ALL today:
    `single.billable_account` refuses on a falsy `unit_id` before any coverage
    is read, citing `BR-CUS-017` as though the rule still said an account holds
    exactly one unit — which `BR-CUS-1010` superseded on 2026-09-01, the same day
    `accounts.unit_id` became nullable. `CR-056` W1 task 8 fixed the CYCLE run's
    scope read and missed this one. **It is asserted here, not worked around**,
    so the day it is fixed this case goes RED and names the row that explains it.
    ⚠ **IT WENT RED, AS DESIGNED, AND IS FLIPPED (2026-09-30):** `DEF-BIL-5457`
    fixed it on 2026-09-16; the second half now asserts the door files it SILENT.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "W4-20")
        plan = _priced_plan(brazos)
        premises = make_premises(
            dana,
            address_line="12 Quiet Lane",
            premises_type="single_family",
            owner_manager="Ajinkya Kulkarni",
            services_available=["electric"],
        )
        house = _metered_unit(
            dana,
            brazos,
            cycle,
            plan,
            premises,
            label="The house",
            asset_no="M-4113",
        )
        # ⚠ **HE HAS TO ACTUALLY LIVE THERE, AND TO BE ACTIVE — two things the
        # first draft of this case got wrong, and the classifier was right about
        # both.** With no occupying account the house is an UNOCCUPIED unit and
        # `BR-CUS-170` puts its standing charge on the owner's bill; and
        # `create_account` opens at `pending_activation`, whose behaviour class
        # is `non_billable`, which `BR-CUS-018` says *"never derives occupancy"*
        # — so an unactivated account leaves the house unoccupied too.
        occupier = customer_services.create_account(
            dana,
            {
                "unit_id": house["id"],
                "account_type": "residential",
                "opened_at": PERIOD_START.isoformat(),
            },
        )
        customer_services.activate_account(dana, occupier["id"])
        # ⛔ `BR-CUS-1114` (PO 2026-10-02) — a master account only on two or more
        # homes, so the house has a LET annex beside it: still nothing shared and
        # nothing empty, which is the silent case this test is about.
        annex = _metered_unit(
            dana, brazos, cycle, plan, premises, label="The annex", asset_no="M-4114"
        )
        lodger = customer_services.create_account(
            dana,
            {
                "unit_id": annex["id"],
                "account_type": "residential",
                "opened_at": PERIOD_START.isoformat(),
            },
        )
        customer_services.activate_account(dana, lodger["id"])
        owner_account = a_master(dana, premises)

        # ── THE ASSERTION THIS CASE EXISTS FOR ──────────────────────────────
        account_row = customer_models.Account.objects.get(pk=owner_account["id"])
        assert account_row.unit_id is None
        assert gather.nothing_to_bill(account_row), (
            "an owner's account covering no unit, at an address whose only unit "
            "he occupies himself, has nothing to bill (BR-BIL-1025)"
        )

        # ── `DEF-2967` · THE DOOR NOW REACHES THE CLASSIFIER ────────────────
        # ⚠ **FLIPPED 2026-09-30.** This half asserted the refusal
        # (`GATHER_NO_UNIT`, *"has no unit"*) so the day `DEF-2967` was fixed it
        # would go RED — and it did: `DEF-BIL-5457` (2026-09-16) let
        # `billable_account` take a unit-less master account, and the single
        # door now files this one SILENT, exactly as the cycle run does.
        prepared = single.prepare_single_bill(
            account_id=owner_account["id"],
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        assert prepared.ready == () and prepared.blocked == ()
        assert [p.reason for p in prepared.silent] == ["account_has_nothing_to_bill"]
