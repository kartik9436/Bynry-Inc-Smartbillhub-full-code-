# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-170 (a master's bill is its premises' common areas PLUS the
#           base charges of every unit with NO OCCUPYING ACCOUNT, and an
#           occupied unit is excluded by the PRESENCE OF ITS OWN ACCOUNT, never
#           by a flag — PO ruling 2026-08-27 closing OQ-531 parts 3 and 4)
# Pin:      **$69.60 stays $69.60, and the moment a unit empties the owner owes
#           $81.60 — one more base charge, no usage line.** ⚠ AMENDED
#           2026-08-27 by the bill-omissions lane: the bill PRICES that base
#           charge now (DEF-990 fixed). It used to REFUSE by name, because
#           `TariffConfig` carried no per-tariff base-only flag and one bill
#           could not hold two base charges for one service. tc3 was the
#           refusal and is now the figure.
# Rules:    BR-CUS-068 as AMENDED 2026-08-27 (attachment stays common-areas-only;
#           COVERAGE widens) · BR-CUS-055 (`base_charges_only` — base and no
#           usage) · BR-BIL-028 (a base-only service is not a missing read) ·
#           BR-BIL-055 (a named break stops ONE account, not the run) ·
#           BR-MET-040 (a unit without a plan has no price)
# Defects:  DEF-990 (the priced half — FIXED 2026-08-27, `gather
#           ._unbilled_unit_tariffs` + `rating_seam.TariffConfig.base_only`) ·
#           DEF-571 (the shape this exists to stop recurring: a document that
#           foots and is short by a covered unit) · DEF-1060 (the same silence
#           one layer up — a service the UNIT takes and the plan never priced)
# OQs:      OQ-334 / OQ-335 (the two coverage refusals that already existed) ·
#           OQ-531 (CLOSED 2026-08-27)
# CR:       CR-040 task B6 — *"one consolidated master bill"*, CORRECTED by the
#           ruling: the master is NOT a consolidator (part 4).
# Impacts:  apps/customers/selectors.py · apps/billing/gather.py
# ───────────────────────────────────────────────────────
"""BR-CUS-170 — what a landlord actually owes.

PO, 2026-08-27: *"when bill is generated for A - we should consider common
areas and U6 to U10 base charges ; U1 to U5 bill be send to Accounts assocaited
with U1 to U5"*.

**TWO THINGS ARE BEING PINNED AND THEY PULL IN OPPOSITE DIRECTIONS.**

**(1) The signed figure does not move.** BR-CUS-068's worked case — 1408 Elm,
hallway lighting **$41.20** + shared irrigation **$28.40** = **$69.60** on one
owner bill — has three ordinary units that are unplanned and unmetered, so
there is no base charge to omit and the widening reaches nothing. tc1 asserts
that, because a rule amendment that quietly moves a signed number is the thing
CLAUDE.md calls a STOP.

**(2) The moment an ordinary unit on that premises is PLANNED, METERED and
EMPTY, the same bill is wrong.** The owner owes the hallway, the irrigation AND
that unit's electric base — **$69.60 + $12.00 = $81.60** — and the product
produced $69.60. That is DEF-571's shape one rule-widening later.

⚠ **tc3 WAS THE REFUSAL AND IS NOW THE FIGURE (DEF-990, fixed 2026-08-27).**
It asserted that the bill stopped by name rather than issuing a document short
by $12.00; the three obstacles it named have been removed and the bill is
produced. The RED proof is the change itself: with `TariffConfig.base_only`
absent this test fails on `DID NOT RAISE` in one direction and on `81.60 !=
69.60` in the other — the same fixture, the same $12.00, and no way to pass it
without both halves of the fix.

**AND THE EXCLUSION TEST IS THE ACCOUNT (tc4).** Give that same unit a tenant
and it leaves the owner's coverage on the day the tenant activates — no flag is
set, no column is written, nothing is un-ticked. That is the half of the ruling
that stops the obvious wrong build: *"U1 to U5 bill be send to Accounts
assocaited with U1 to U5"*.
"""

from decimal import Decimal

import pytest

from apps.billing import gather, models as billing_models, runs
from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import services as metering_services

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_premises,
    make_unit,
    tenant_ctx,
)
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

#: The electric base charge `_priced_plan` types onto the Small Commercial
#: bundle. An EMPTY unit on that plan brings this and no usage line.
ELECTRIC_BASE = Decimal("12.00")
#: BR-CUS-170's own worked figure: the signed $69.60 plus one empty unit's base.
OWNER_WITH_ONE_EMPTY_UNIT = COMMON_BILL + ELECTRIC_BASE  # 81.60


def _planned_metered_unit(actor, tenant, cycle, plan, premises, *, label, asset_no):
    """An ORDINARY unit that could be billed: it has a plan and a connection.

    This is exactly the unit `1408 Elm`'s Unit A/B/C are NOT — they are created
    with no `services` and no plan assignment, which is why the signed $69.60
    survives the amendment untouched.
    """
    from apps.metering import models as metering_models
    from tests.test_us_met_reads_helpers import a_meter

    unit = make_unit(actor, premises["id"], label=label, services=["electric"])
    a_meter(actor, asset_no=asset_no, unit_id=unit["id"], service="electric", uom="kWh")
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    return unit


def _run_readings(master):
    """What `runs.readings_for_account` collects for the owner — the covered
    units' reads, never an empty unit's (DEF-BIL-8724)."""
    readings, _unmeasured = runs.readings_for_account(
        master, period_start=PERIOD_START, period_end=PERIOD_END, scope_services=None
    )
    return readings


def _occupy(actor, unit, *, name="Elena Rivera"):
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": PERIOD_START.isoformat(),
            "contact": {"full_name": name},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
            "addresses": [
                {"kind": "mailing", "line1": "1408 Elm St", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    return customer_models.Account.objects.get(pk=created["id"])


# ══════════════════════════════════════════════════════════════════════════
# (1) THE SIGNED FIGURE DOES NOT MOVE
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_170_tc1__the_signed_69_60_is_untouched_by_the_widening(brazos, dana):
    """BR-CUS-068's $41.20 + $28.40 = **$69.60**, after the amendment.

    1408 Elm's three ordinary units carry no plan and no service point, so
    BR-CUS-170's widening reaches nothing on them: there is no base charge
    being omitted and therefore nothing to refuse.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "MA-170-1")
        plan = _priced_plan(brazos)
        premises, hallway, irrigation = elm_1408(dana, brazos, cycle, plan)
        master_dict = a_master(dana, premises)
        master = customer_models.Account.objects.get(pk=master_dict["id"])

        # NON-VACUOUS FIRST (DEF-828's shape): the premises really does hold
        # three ordinary units, so the empty answer below is a measurement
        # rather than a query that found nothing to look at.
        assert customer_selectors._units_on_premises(premises["id"]).__len__() == 5
        assert customer_selectors.base_charge_only_coverage(master) != []
        priceable = [
            entry
            for entry in customer_selectors.base_charge_only_coverage(master)
            if entry["has_plan"] and entry["service_point_count"]
        ]
        assert priceable == []

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        invoice = runs.calculate_account(
            prepared.ready[0], bill_run=_run(brazos, cycle, "ma-170-1"), service_date=SERVICE_DATE
        )
        assert _by_service(invoice) == {"electric": HALLWAY, "water": IRRIGATION}
        assert invoice.total == COMMON_BILL
        assert hallway["id"] != irrigation["id"]


def test_br_cus_170_tc2__an_ordinary_account_answers_no_coverage_and_issues_no_query(brazos, dana):
    """Every non-master bill in the product is byte-identical.

    `base_charge_only_coverage` short-circuits on `kind`, so an ordinary
    account never reaches the premises walk — which is why no ❄️ B5 golden
    figure can move.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "MA-170-2")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        unit = _planned_metered_unit(
            dana, brazos, cycle, plan, premises, label="Unit D", asset_no="M-4191"
        )
        tenant_account = _occupy(dana, unit)

        assert customer_selectors.base_charge_only_coverage(tenant_account) == []
        assert gather.base_charge_only_units(tenant_account) == ()


# ══════════════════════════════════════════════════════════════════════════
# (2) THE MOMENT A PLANNED, METERED UNIT IS EMPTY, THE OWNER OWES MORE
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_170_tc3__an_empty_planned_unit_puts_its_base_charge_on_the_owners_bill(
    brazos, dana
):
    """**$81.60 is owed and $81.60 is what the product now produces (DEF-990).**

    PO 2026-08-27: *"we should consider common areas and U6 to U10 base
    charges"*. `Unit D` is planned, connected and occupied by nobody, so its
    **$12.00** electric base belongs on the owner's bill beside the hallway's
    $41.20 and the irrigation's $28.40 — **$69.60 + $12.00 = $81.60**.

    ⚠ **THE THREE ASSERTIONS BELOW ARE THREE DIFFERENT WAYS TO GET THIS WRONG,
    and each was a named obstacle in DEF-990.**

    * **The TOTAL is $81.60** — one bill holds TWO base charges for one service
      (the hallway's electric prices usage AND base; Unit D's electric prices
      base alone). Before `TariffConfig.base_only` existed it could not.
    * **The electric line count is TWO and the kWh billed do not double.** A
      base-only tariff never reaches `measure_consumption._reading_for`, which
      matches on the service CODE and would have handed Unit D's tariff the
      HALLWAY's reading — a plausible document, footing perfectly, charging the
      hallway's kWh twice.
    * **Unit D's own meter is never read.** `runs.readings_for_account` walks
      `covered_units`, which does not contain it, so no usage the PO did not ask
      for can arrive: *"U6 to U10 BASE charges"*.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "MA-170-3")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        _planned_metered_unit(
            dana, brazos, cycle, plan, premises, label="Unit D", asset_no="M-4192"
        )
        master = customer_models.Account.objects.get(pk=a_master(dana, premises)["id"])

        coverage = customer_selectors.base_charge_only_coverage(master)
        empty = [entry for entry in coverage if entry["label"] == "Unit D"]
        assert len(empty) == 1, coverage
        assert empty[0]["has_plan"] is True
        assert empty[0]["service_point_count"] == 1

        # The gather now carries the empty unit's base as its OWN tariff, flagged
        # base-only, beside the two common areas' full tariffs.
        gathered = gather.gather_account(
            account=master,
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=(PERIOD_END - PERIOD_START).days + 1,
            # DEF-BIL-8724 — the readings the RUN hands the gather. With none,
            # the ruled path's adapter (which builds its meters from these
            # rows) saw every metered service as meterless and refused R3
            # "the unit has no meter for it" for the HALLWAY's electric.
            readings=_run_readings(master),
        )
        base_only = [config for config in gathered.tariffs if config.base_only]
        assert len(base_only) == 1, gathered.tariffs
        assert base_only[0].service == "electric"
        assert base_only[0].base_charge == ELECTRIC_BASE
        # TWO electric tariffs on ONE bill — the thing DEF-990 said could not be.
        assert [config.service for config in gathered.tariffs].count("electric") == 2

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        owner = next(row for row in prepared.ready if row.account_no == master.account_no)
        invoice = runs.calculate_account(
            owner, bill_run=_run(brazos, cycle, "ma-170-3"), service_date=SERVICE_DATE
        )
        # ❄️ THE FIGURE, and it is the whole point of the rule.
        assert invoice.total == OWNER_WITH_ONE_EMPTY_UNIT == Decimal("81.60")
        assert invoice.total - COMMON_BILL == ELECTRIC_BASE

        # And the empty unit brought a BASE charge and NOT a usage line: the
        # hallway's kWh are billed once, not twice.
        base_lines = billing_models.InvoiceLine.objects.filter(
            invoice=invoice, kind="base"
        ).count()
        electric_usage = billing_models.InvoiceLine.objects.filter(
            invoice=invoice, kind="usage", service__code="electric"
        ).count()
        assert base_lines == 3, "hallway electric + irrigation water + Unit D electric"
        # ONE electric usage line, not two. This is the assertion that would have
        # caught `_reading_for` handing Unit D's tariff the HALLWAY's reading.
        assert electric_usage == 1


# ══════════════════════════════════════════════════════════════════════════
# (3) THE EXCLUSION TEST IS THE ACCOUNT, NOT A FLAG
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_170_tc4__a_tenant_moving_in_removes_the_unit_from_the_owners_bill(brazos, dana):
    """**THE HALF THAT STOPS THE OBVIOUS WRONG BUILD.**

    PO 2026-08-27: *"U1 to U5 bill be send to Accounts assocaited with U1 to
    U5"*. A master is NOT a consolidator. The same unit, same plan, same meter
    — the only thing that changes is that somebody now lives there, and the
    owner's coverage drops it. **No flag is set and no column is written**, so
    nobody can forget to maintain it.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "MA-170-4")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        unit = _planned_metered_unit(
            dana, brazos, cycle, plan, premises, label="Unit D", asset_no="M-4193"
        )
        master = customer_models.Account.objects.get(pk=a_master(dana, premises)["id"])

        before = [entry["label"] for entry in customer_selectors.base_charge_only_coverage(master)]
        assert "Unit D" in before

        tenant_account = _occupy(dana, unit, name="Elena Rivera")

        after = [entry["label"] for entry in customer_selectors.base_charge_only_coverage(master)]
        assert "Unit D" not in after
        # …and the owner's bill is billable again, because nothing is omitted.
        gathered = gather.gather_account(
            account=master,
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=(PERIOD_END - PERIOD_START).days + 1,
            # DEF-BIL-8724 — the readings the RUN hands the gather. With none,
            # the ruled path's adapter (which builds its meters from these
            # rows) saw every metered service as meterless and refused R3
            # "the unit has no meter for it" for the HALLWAY's electric.
            readings=_run_readings(master),
        )
        assert gathered.account_no == master.account_no
        # The tenant is the master's CHILD (BR-CUS-171) and pays their OWN bill.
        # ⚠ The link is DECLARED on the premises since DEF-650 (PO 2026-08-27,
        # *"Premises -> owner = Master account"*) and named directly since
        # BR-MET-1181 (2026-09-22); nothing is inferred from the hallway any
        # more, and `create_master_account` declares nothing. So the fixture
        # declares it, the way the premises screen does (DEF-BIL-8724 triage).
        from apps.metering import models as metering_models

        metering_models.Premises.objects.filter(pk=premises["id"]).update(
            master_account_id=master.id
        )
        assert customer_selectors.master_account_for(tenant_account).id == master.id


def test_br_cus_170_tc5__a_common_area_is_never_double_counted(brazos, dana):
    """Common areas ride the master's own service agreements (BR-CUS-068's
    signed linkage), so they must NOT also appear in the base-charges-only
    list — pricing them twice would double the $41.20."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "MA-170-5")
        plan = _priced_plan(brazos)
        premises, hallway, irrigation = elm_1408(dana, brazos, cycle, plan)
        master = customer_models.Account.objects.get(pk=a_master(dana, premises)["id"])

        covered = set(customer_selectors.covered_unit_ids(master))
        assert covered == {hallway["id"], irrigation["id"]}
        coverage_ids = {
            entry["unit_id"] for entry in customer_selectors.base_charge_only_coverage(master)
        }
        assert coverage_ids.isdisjoint(covered)
