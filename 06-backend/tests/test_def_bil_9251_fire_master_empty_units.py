# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-9251 — a master account over a fire build could not take its
#          first bill: the empty-home base path (BR-CUS-170, DEF-CUS-9050) asked
#          for ONE size per connection, and Unit 1's fire connection carries
#          three lines (6" + 2" + 2"), so it refused
#          connection_size_unresolved_for_sized_schedule although every line
#          has a size.
# Rules:   CR-063 (fire is trash's arithmetic: one config per size, a count per
#          size) · PO 2026-09-30 option B (the base is per ASSET) · PO
#          2026-09-30 "per service" (one base line per service) · BR-CUS-170 /
#          PO 2026-10-02 option A (an empty home's BASE is the owner's)
# Tests:   this file — run on PostgreSQL (`--ds=config.settings.pgtest`)
# Impacts: apps/billing/gather.py `_unbilled_unit_tariffs`
# ───────────────────────────────────────────────────────
"""An empty home's fire base is the one the unit-level path computes.

The walk's S2 shape: two empty commercial units under the owner's master
account, Unit 1 carrying a 6" line and two 2" lines, Unit 2 one 6" line.

**Worked, with a fire base of $5.00 a line** (seeded at $0.00, set here so the
base is visible): the unit-level path bills Unit 1's equipment `3 × $5.00 =
$15.00` base plus `$60.00 + 2 × $12.00 = $84.00` usage. The owner's bill for
the SAME equipment on an EMPTY home carries the base only (BR-CUS-170 is base
charges) — `$15.00` for Unit 1 and `$5.00` for Unit 2, `$20.00`. Before the fix:
refused, `$0.00` billed to anybody.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather, models as billing_models, runs
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models

from tests import identity_fixtures
from tests.test_cr063_c3_fire_priced import (
    AUG_END,
    AUG_START,
    _assert_capacity_basis,
    _bill,
    _fire_asset,
    _fire_plan,
    _world,
)
from tests.test_br_cus_068_master_bill import _cycle
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

FIRE_BASE = Decimal("5.00")
CENT = Decimal("0.01")


def _fire_base(amount):
    rows = rating_models.Charge.objects.filter(code="BASE-FIRE")
    assert rows.exists(), "the seeded fire base code is what this case prices"
    rows.update(amount=amount)


def _empty_fire_build(actor, tenant, code):
    from apps.metering import premises_owners
    from apps.tenancy import services as tenancy_services

    tenancy_services.update_tenant_service(actor, "fire", {"enabled": True})
    _assert_capacity_basis(tenant, "fire")
    cycle = _cycle(tenant, code)
    plan = _fire_plan(tenant, actor)
    _fire_base(FIRE_BASE)
    owner = premises_owners.create_premises_owner(
        actor, {"name": f"S2 Owner {code}", "category": "landlord"}
    )
    premises = make_premises(
        actor,
        address_line=f"14 Hydrant Row {code}",
        premises_type="apartment_complex",
        services_available=["fire"],
        owner_id=owner["id"],
    )
    units = []
    for label, sizes in (("Unit 1", ("FL-6", "FL-2", "FL-2")), ("Unit 2", ("FL-6",))):
        unit = make_unit(actor, premises["id"], label=label, services=["fire"])
        metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
            cycle=cycle
        )
        metering_services.assign_unit_plan(
            actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
        )
        for n, size in enumerate(sizes, start=1):
            _fire_asset(actor, unit["id"], len(units) * 10 + n, size)
        units.append(unit)
    made = customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": "2026-07-01",
            "customer": identity_fixtures.customer_block(f"S2 Owner {code}", kind="company"),
        },
    )
    return cycle, customer_models.Account.objects.get(pk=made["id"])


def _fire_base_lines(invoice):
    return {
        line.description: line.amount.quantize(CENT)
        for line in billing_models.InvoiceLine.objects.filter(invoice=invoice, kind="base")
        if line.service_id and line.service.code == "fire"
    }


def test_def_bil_9251_tc1__the_owners_bill_carries_each_empty_homes_fire_base(brazos, dana):
    with tenant_ctx(brazos):
        cycle, master = _empty_fire_build(dana, brazos, "F9251A")

        data = gather.gather_account(
            account=master,
            service_date=AUG_END,
            period_start=AUG_START,
            period_end=AUG_END,
            cycle_days=31,
        )
        fire = [t for t in data.tariffs if t.service == "fire"]
        assert fire and all(t.base_only for t in fire), "an empty home's fire is base only"

        invoice = _bill(brazos, cycle, "def-bil-9251-tc1")
        assert str(invoice.account_id) == str(master.id)
        lines = _fire_base_lines(invoice)
        print("\nPROOF DEF-BIL-9251 owner's fire base lines:", lines)
        unit1 = [amount for text, amount in lines.items() if "Unit 1" in text]
        unit2 = [amount for text, amount in lines.items() if "Unit 2" in text]
        assert unit1 == [Decimal("15.00")], "3 lines × $5.00, ONE base line per service"
        assert unit2 == [Decimal("5.00")]
        # No fire USAGE on the owner's bill — BR-CUS-170 is base charges.
        assert not billing_models.InvoiceLine.objects.filter(
            invoice=invoice, kind="usage", service__code="fire"
        ).exists()


def test_def_bil_9251_tc2__the_unit_level_path_bills_the_same_base_for_the_same_kit(brazos, dana):
    """Parity: the same three lines on an OCCUPIED unit — base `$15.00` (the
    figure the owner pays above) plus the CR-063 usage `$84.00`, joined on ONE
    fire line of `$99.00` (DEF-BIL-8151, *"per service"*)."""
    with tenant_ctx(brazos):
        cycle, _unit, _account, _kit = _world(
            dana, brazos, cycle_code="F9251B", equipment=("FL-6", "FL-2", "FL-2")
        )
        _fire_base(FIRE_BASE)
        invoice = _bill(brazos, cycle, "def-bil-9251-tc2")
        fire = [
            (line.kind, line.amount.quantize(CENT))
            for line in invoice.lines.all()
            if line.service_id and line.service.code == "fire"
        ]
        print("\nPROOF DEF-BIL-9251 unit-level fire:", fire)
        # ONE line per service (DEF-BIL-8151): usage $84.00 + base 3 × $5.00.
        assert fire == [("usage", Decimal("99.00"))]
