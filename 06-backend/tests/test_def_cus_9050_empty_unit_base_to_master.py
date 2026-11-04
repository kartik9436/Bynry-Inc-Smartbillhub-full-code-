# ── Trace ──────────────────────────────────────────────
# Ruling:   PO 2026-10-02, option A (decision log *"AN EMPTY UNIT'S BASE CHARGES
#           ON A MULTI-UNIT BUILDING ARE BILLED TO THE OWNER'S MASTER ACCOUNT
#           UNTIL A TENANT MOVES IN"*): *"in our case master account - this is
#           correct"*. Base charges only; only where a master account exists
#           (two or more homes, BR-CUS-1114); an empty single unit bills nobody;
#           the owner stops paying from the tenant's move-in date, prorated.
# Defects:  DEF-CUS-9050 · DEF-CUS-9082
# Worked:   Oak Court, 4 units, owner's master account, Unit 4 empty, water base
#           $8.00 a unit a month → the owner's bill carries "Unit 4 · water base
#           charge" $8.00 a month ($16.00 over two). A move-in on the 16th of a
#           30-day month → the owner pays 15/30 × $8.00 = $4.00 and the tenant
#           the other $4.00.
# Rules:    BR-CUS-170 (the owner's bill carries the empty units' base) ·
#           B4.3 ❄️ (base prorated by days / days in period) · hard rule 2
# Law 14:   run on PostgreSQL — `--ds=config.settings.pgtest`.
# ───────────────────────────────────────────────────────
"""**An empty home's base charge is the owner's — by the day, and only on a
building with an owner's master account.**

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY:** asserting the bill TOTAL alone (a
second unit's base could land at $8.00 by accident) — so the line is found by
the unit it names; asserting the owner's $4.00 without the tenant's (a bill
that charged the owner $4.00 and the tenant $8.00 would overcharge by $4.00) —
so both halves are asserted and they foot to $8.00.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models, runs
from apps.customers import models as customer_models, services as customer_services
from apps.metering import models as metering_models, services as metering_services
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx  # noqa: F401
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

#: A 30-day month, so the PO's worked figure is exact: 15/30 × $8.00 = $4.00.
START = date(2026, 9, 1)
END = date(2026, 9, 30)
WATER_BASE = Decimal("8.00")


def _water_plan(tenant):
    """Water only, $8.00 base (charge code `BASE-WATER`), $4.00/kgal — the
    shape `test_br_cus_068_master_bill._priced_plan` builds, one service, so no
    other service on the plan asks for a connection these homes do not have."""
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors
    from apps.tenancy import models as tenancy_models

    from tests.test_us_met_helpers import make_plan, state_size_axis

    plan = make_plan(tenant, name="Oak Court Water", services=("water",))
    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=WATER_BASE,
            uom="kgal",
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
            unit_price=Decimal("4.000000"),
        )
        state_size_axis(version, row["service_code"])
    from tests.base_code_naming import name_base_code

    name_base_code(  # DEF-RAT-9832 (PO 2026-10-06) — unnamed bills $0.00
        tenant,
        rating_models.Charge.objects.create(
            tenant=tenant,
            code="BASE-WATER",
            name="Water base service",
            charge_type="recurring",
            amount_rule="flat",
            amount=WATER_BASE,
            service=tenancy_models.Service.objects.get(code="water"),
            is_base=True,
        ),
    )
    return plan


def _cycle(tenant, code):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        start_day=START.day,
        days_to_complete=(END - START).days + 1,
        bill_day=1,
        due_days=21,
    )


def _home(actor, tenant, cycle, plan, premises, *, label, asset_no):
    unit = make_unit(actor, premises["id"], label=label, services=["water"])
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"], service="water", uom="kgal")
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    return unit, asset


def _tenant(actor, unit, asset, *, name, moved_in=START):
    made = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": moved_in.isoformat(),
            "contact": {"full_name": name},
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )
    customer_services.activate_account(actor, made["id"])
    commit_read(
        actor,
        asset["id"],
        day=END.isoformat(),
        value="1002",
        prior_value="1000",
        consumption="2",
        unit="kgal",
    )
    return customer_models.Account.objects.get(pk=made["id"])


def _master(actor, premises):
    made = customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": "2026-08-01",
            "customer": identity_fixtures.customer_block("Jim Park Rentals LLC", kind="company"),
        },
    )
    return customer_models.Account.objects.get(pk=made["id"])


def _oak_court(actor, tenant, code):
    """Oak Court: four homes on water, Units 1–3 let from the 1st, Unit 4 empty,
    and the owner's master account."""
    cycle = _cycle(tenant, code)
    plan = _water_plan(tenant)
    premises = make_premises(
        actor,
        address_line=f"{code} Oak Court",
        premises_type="apartment_complex",
        owner_manager="Jim Park Rentals LLC",
        services_available=["water"],
    )
    homes = [
        _home(actor, tenant, cycle, plan, premises, label=f"Unit {n}", asset_no=f"W-{code}-{n}")
        for n in range(1, 5)
    ]
    for n, (unit, asset) in enumerate(homes[:3], start=1):
        _tenant(actor, unit, asset, name=f"Tenant {n}")
    master = _master(actor, premises)
    return cycle, premises, master, homes[3]


def _bill(tenant, cycle, account, key):
    prepared = runs.prepare_run(
        cycle_id=cycle.id, period_start=START, period_end=END, service_date=END
    )
    row = next((r for r in prepared.ready if r.account_no == account.account_no), None)
    assert row is not None, (
        account.account_no,
        [
            (p.account_no, getattr(p, "reason", None), getattr(p, "detail", None))
            for p in (*prepared.blocked, *prepared.decisions, *prepared.silent)
        ],
    )
    run = billing_models.BillRun.objects.create(
        tenant=tenant, cycle=cycle, period_start=START, period_end=END, idempotency_key=key
    )
    return runs.calculate_account(row, bill_run=run, service_date=END)


def _unit_base_lines(invoice, label):
    return [
        line
        for line in billing_models.InvoiceLine.objects.filter(invoice=invoice, kind="base")
        if label in (line.description or "")
    ]


def test_an_empty_home_puts_its_8_00_base_on_the_owners_bill_naming_the_unit(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _premises, master, _unit4 = _oak_court(dana, brazos, "OC1")
        invoice = _bill(brazos, cycle, master, "oc1")
        lines = _unit_base_lines(invoice, "Unit 4")
        assert [line.amount.quantize(Decimal("0.01")) for line in lines] == [WATER_BASE]
        assert lines[0].service.code == "water"
        # Base only: no usage line for the empty home, and no other home is on it.
        assert not billing_models.InvoiceLine.objects.filter(invoice=invoice, kind="usage").exists()
        assert not _unit_base_lines(invoice, "Unit 1")


def test_a_move_in_on_the_16th_splits_the_8_00_base_4_00_and_4_00(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _premises, master, (unit4, asset4) = _oak_court(dana, brazos, "OC2")
        newcomer = _tenant(dana, unit4, asset4, name="Ava Newcomer", moved_in=date(2026, 9, 16))
        owner_bill = _bill(brazos, cycle, master, "oc2-owner")
        owner_part = sum(line.amount for line in _unit_base_lines(owner_bill, "Unit 4"))
        assert owner_part.quantize(Decimal("0.01")) == Decimal("4.00")  # 15/30 × $8.00

        tenant_bill = _bill(brazos, cycle, newcomer, "oc2-tenant")
        tenant_base = sum(
            line.amount
            for line in billing_models.InvoiceLine.objects.filter(
                invoice=tenant_bill, kind="base", service__code="water"
            )
        )
        assert tenant_base.quantize(Decimal("0.01")) == Decimal("4.00")
        assert owner_part + tenant_base == WATER_BASE


def test_an_empty_single_home_bills_nobody(brazos, dana):
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "OC3")
        plan = _water_plan(brazos)
        premises = make_premises(
            dana,
            address_line="3 Lone Cottage Rd",
            premises_type="single_family",
            owner_manager="Jim Park Rentals LLC",
            services_available=["water"],
        )
        _home(dana, brazos, cycle, plan, premises, label="House", asset_no="W-OC3-1")
        with pytest.raises(errors.BizError) as refused:
            _master(dana, premises)
        assert refused.value.br_ref == "BR-CUS-1114"
        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=START, period_end=END, service_date=END
        )
        assert list(prepared.ready) == []
        assert not customer_models.Account.objects.filter(premises_id=premises["id"]).exists()
