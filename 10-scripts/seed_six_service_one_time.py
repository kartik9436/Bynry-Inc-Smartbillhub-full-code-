#!/usr/bin/env python3
"""seed_six_service_one_time — a utility with SIX services, for the J75 one-time bill walk.

Journey `08-qa/01-e2e/journeys/J75-six-service-one-time-bill.md` · spec
`07-frontend/e2e/J75-six-service-one-time-bill.spec.ts` · verifier
`10-scripts/verify_j74_one_time_bill.py --world j75`.

PO 2026-10-01, verbatim: *"when you complete this please run end to end run for all
one tim ebill scenarios with utility ahving 6 utility services - Water, Sewer, trash,
Fire, Battery and Solar - and see we are able to create one time bill for this
utility if you face bugs fix them - we already done end to end run before you can
use that"*.

WHY A NEW UTILITY AND NOT BRAZOS BEND
-------------------------------------
Brazos Bend (`seed_demo`) runs electric, gas, broadband and more. The ask is a
utility with EXACTLY six services, so this signs one up through the real signup
service (`tenancy.services.provision_tenant`) with those six and nothing else —
`Six Rivers Utility`, subdomain `sixrivers`, owner Priya Shah — exactly what a
utility gets at S114, its sample set included. Then it adds, through the owning
modules' services where one exists, the walk world below. It REUSES J70/J74's
helpers (`seed_j70_one_time_bill.py`: rate versions, reads, meters, the walk month).

Run on a MIGRATED, otherwise empty database (nothing else is needed):

    cd 06-backend && DATABASE_URL=postgres://…/sbh_six DJANGO_SETTINGS_MODULE=config.settings.local \\
        python ../10-scripts/seed_six_service_one_time.py

THE PRICES (fixture values, not signed law — no ❄️ B4/B5 figure is touched)
---------------------------------------------------------------------------
Plan `SRU-RES` "Six Rivers Residential", every version from 2026-01-01:
  water   tiered kgal 0–5 $4.00 · 5–15 $6.50 · 15+ $8.00   base BASE-W W-58 $8.00 (the signup's own)
  sewer   90% of water × $5.00/kgal                          base BASE-S $9.00 flat (the signup's own)
  trash   per container by size: CART-35 $10 · CART-64 $12 · CART-96 $15 · DUMP-4 $85
          base BASE-T BY SIZE: CART-64 $2.00 · CART-96 $3.00 · DUMP-4 $10.00 · CART-35 NOT PRICED
  fire    per line by size (the signup's own): FL-2 $12 · FL-4 $30 · FL-6 $60 …   base BASE-FIRE $0.00
  battery $3.00 per kW summed                                base BASE-BAT BY SIZE: BAT-5 $2 · BAT-10 $4 · BAT-15 NOT PRICED
  solar   $14.00 per kW summed                               base BASE-SOL BY SIZE: SOL-P2 $1 · SOL-P4 $2 · SOL-P8 $3 · SOL-P6 NOT PRICED
Tax: the signup's own — Local · Bexar County 2.00% on every usage and base line for a
residential account (TX State 6.25% names commercial and industrial only). CONN, the
deposit, RECON and TAMPER are not taxable (the signup's own codes).
Cycle `SRU-MONTHLY`, monthly from 2026-01-01, 21 days to pay. Deposit rule $150.00.

THE UNITS (1200 Confluence Ave, Katy TX), each an account carrying several services
----------------------------------------------------------------------------------
  Unit 1  Ana Ruiz      all six: W-2001; 2 × CART-96 + 1 × CART-35; FL-6 + 2 × FL-2; BAT-10; SOL-P2 + SOL-P4 + SOL-P8
  Unit 2  Ben Okoro     water, sewer, trash DUMP-4, battery BAT-15 — no reading since Aug 31 (estimated)
  Unit 3  Carla Mendes  first bill, moved in 09/12: W-2003 (move-in read on file); CART-64; FL-4; BAT-5; SOL-P6
  Unit 4  Dev Patel     final, $50.00 deposit: W-2004; CART-96; FL-2; BAT-10; SOL-P4
  Unit 5  Elena Brooks  final, $200.00 deposit: same as Unit 4 (W-2005 …)
  Unit 6  Femi Adeyemi  catch-up Jul–Sep: W-2006 read monthly; CART-96; FL-2; BAT-5; SOL-P2
  Unit 7  Gita Rao      penalty Jul–Sep: W-2007 read monthly; CART-64; FL-4; BAT-10; SOL-P2 + SOL-P4
  Unit 8  Hugo Lind     fee (RECON): W-2008; CART-96
"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ["E2E_TENANT"] = "sixrivers"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


sjf = _load("seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py")
j70 = _load("seed_j70_one_time_bill", REPO / "10-scripts/seed_j70_one_time_bill.py")

SIGNUP = {
    "name": "Six Rivers Utility",
    "subdomain": "sixrivers",
    "state": "Texas",
    "services": ["water", "sewer", "trash", "fire", "battery", "solar"],
    "currency": "USD",
    "plan": "growth",
    "load_defaults": True,
    "owner": {
        "full_name": "Priya Shah",
        "email": "priya@sixriversutility.com",
        "password": "S3cure!passw0rd",  # walk fixture credential — never prod
        "phone": "+1 (281) 555-0190",
    },
}
SERVICES = ("water", "sewer", "trash", "fire", "battery", "solar")
POINTS = ["water", "trash", "fire", "battery", "solar"]  # sewer follows water (no point), as J70
PLAN_NAME, PLAN_CODE = "Six Rivers Residential", "SRU-RES"
ADDRESS = "1200 Confluence Ave"
ACCOUNT_TYPE = "residential"
CYCLE_CODE = "SRU-MONTHLY"
DEPOSIT = Decimal("150.0000")
JAN1 = date(2026, 1, 1)

WATER_TIERS = (("0", "5", "4.0000"), ("5", "15", "6.5000"), ("15", None, "8.0000"))
SEWER_PERCENT, SEWER_RATE = Decimal("90.000000"), Decimal("5.0000")
TRASH_EACH = {"CART-35": "10.0000", "CART-64": "12.0000", "CART-96": "15.0000", "DUMP-4": "85.0000"}
FIRE_EACH = {"FL-2": "12.0000", "FL-4": "30.0000", "FL-6": "60.0000", "FL-8": "100.0000",
             "FL-10": "160.0000", "FL-12": "230.0000"}
BATTERY_PER_KW, SOLAR_PER_KW = "3.0000", "14.0000"
#: base codes priced BY SIZE — a size missing here is deliberately unpriced ($0.00 + warning)
SIZE_BASES = {
    "BASE-T": {"CART-64": "2.0000", "CART-96": "3.0000", "DUMP-4": "10.0000"},  # CART-35 unpriced
    "BASE-BAT": {"BAT-5": "2.0000", "BAT-10": "4.0000"},  # BAT-15 unpriced
    "BASE-SOL": {"SOL-P2": "1.0000", "SOL-P4": "2.0000", "SOL-P8": "3.0000"},  # SOL-P6 unpriced
}
REASONS = (("MISSED", "Missed billing"), ("TAMPER", "Tamper"))

#: unit → (customer, phone, opened_at, water meter, [(asset type, service, size)], deposit)
UNITS = {
    "1": ("Ana Ruiz", "+1 (281) 555-0201", "2025-07-01", "W-2001",
          [("container_cart", "trash", "CART-96"), ("container_cart", "trash", "CART-96"),
           ("container_cart", "trash", "CART-35"), ("fire_line", "fire", "FL-6"),
           ("fire_line", "fire", "FL-2"), ("fire_line", "fire", "FL-2"),
           ("battery", "battery", "BAT-10"),
           ("pv", "solar", "SOL-P2"), ("pv", "solar", "SOL-P4"), ("pv", "solar", "SOL-P8")], None),
    "2": ("Ben Okoro", "+1 (281) 555-0202", "2025-07-01", "W-2002",
          [("container_cart", "trash", "DUMP-4"), ("battery", "battery", "BAT-15")], None),
    "3": ("Carla Mendes", "+1 (281) 555-0203", "2026-09-12", "W-2003",
          [("container_cart", "trash", "CART-64"), ("fire_line", "fire", "FL-4"),
           ("battery", "battery", "BAT-5"), ("pv", "solar", "SOL-P6")], None),
    "4": ("Dev Patel", "+1 (281) 555-0204", "2025-07-01", "W-2004",
          [("container_cart", "trash", "CART-96"), ("fire_line", "fire", "FL-2"),
           ("battery", "battery", "BAT-10"), ("pv", "solar", "SOL-P4")], Decimal("50.0000")),
    "5": ("Elena Brooks", "+1 (281) 555-0205", "2025-07-01", "W-2005",
          [("container_cart", "trash", "CART-96"), ("fire_line", "fire", "FL-2"),
           ("battery", "battery", "BAT-10"), ("pv", "solar", "SOL-P4")], Decimal("200.0000")),
    "6": ("Femi Adeyemi", "+1 (281) 555-0206", "2025-07-01", "W-2006",
          [("container_cart", "trash", "CART-96"), ("fire_line", "fire", "FL-2"),
           ("battery", "battery", "BAT-5"), ("pv", "solar", "SOL-P2")], None),
    "7": ("Gita Rao", "+1 (281) 555-0207", "2025-07-01", "W-2007",
          [("container_cart", "trash", "CART-64"), ("fire_line", "fire", "FL-4"),
           ("battery", "battery", "BAT-10"), ("pv", "solar", "SOL-P2"), ("pv", "solar", "SOL-P4")], None),
    "8": ("Hugo Lind", "+1 (281) 555-0208", "2025-07-01", "W-2008",
          [("container_cart", "trash", "CART-96")], None),
}
#: history reads (day, register) per water meter; the first carries no prior
READS = {
    "W-2001": (("2026-07-31", "488.0"), ("2026-08-31", "500.0")),
    "W-2002": (("2026-06-30", "300.0"), ("2026-07-31", "306.2"), ("2026-08-31", "312.4")),
    "W-2003": (("2026-09-12", "100.0"),),  # the move-in read
    "W-2004": (("2026-07-31", "394.0"), ("2026-08-31", "400.0")),
    "W-2005": (("2026-07-31", "394.0"), ("2026-08-31", "400.0")),
    "W-2006": (("2026-05-31", "200.0"), ("2026-06-30", "206.0"), ("2026-07-31", "213.0"), ("2026-08-31", "221.0")),
    "W-2007": (("2026-05-31", "590.0"), ("2026-06-30", "600.0"), ("2026-07-31", "610.0"),
               ("2026-08-31", "621.0"), ("2026-09-30", "630.0")),
    "W-2008": (("2026-07-31", "50.0"), ("2026-08-31", "55.0")),
}


def provision() -> None:
    from apps.tenancy import models as tm
    from apps.tenancy import services as tsvc

    if tm.Tenant.objects.filter(subdomain=SIGNUP["subdomain"]).exists():
        return
    result = tsvc.provision_tenant({**SIGNUP, "owner": dict(SIGNUP["owner"])})
    print(f"  signed up ............... {result['subdomain']} ({result['id']})")


def _charge(tenant, code):
    from apps.rating import models as rm

    return rm.Charge.objects.get(tenant=tenant, code=code, deleted_at__isnull=True)


def price_bases_by_size(tenant) -> None:
    """Trash, battery and solar bases priced BY SIZE (BR-BIL-1067), one size left unpriced each."""
    from apps.rating import models as rm

    for code, amounts in SIZE_BASES.items():
        charge = _charge(tenant, code)
        if charge.amount is not None:
            charge.amount = None
            charge.save(update_fields=["amount"])
        for size, amount in amounts.items():
            rm.ChargeCodeAmount.objects.get_or_create(
                tenant=tenant, charge=charge, size_class=size, defaults={"amount": Decimal(amount)}
            )


def _sized_version(tenant, tariff, *, uom, prices, base):
    """A per-size (counting) schedule: one tier row per size, as the signup's fire schedule."""
    from apps.rating import models as rm

    found = rm.TariffVersion.objects.filter(tenant=tenant, tariff=tariff, effective_from=JAN1).first()
    if found is not None:
        return found
    version = rm.TariffVersion.objects.create(
        tenant=tenant, tariff=tariff, model="tiered", uom=uom, currency="USD",
        effective_from=JAN1, base_charge_code=base,
    )
    for seq, (size, price) in enumerate(prices.items(), start=1):
        rm.RateTier.objects.create(
            tenant=tenant, tariff_version=version, seq=seq, size_class=size,
            from_qty=Decimal("0"), to_qty=None, unit_price=Decimal(price),
        )
    return version


def ensure_plan(tenant, actor):
    from apps.rating import models as rm
    from apps.rating import selectors as rsel
    from apps.tenancy import models as tm

    from tests.test_us_met_helpers import make_plan, state_size_axis

    plan = make_plan(tenant, name=PLAN_NAME, code=PLAN_CODE, services=SERVICES)
    tariffs = {row["service_code"]: row["tariff"] for row in rsel.plan_rate_schedules(plan.id)}
    w = j70._version(tenant, tariffs["water"], model="tiered", uom="kgal", effective_from=JAN1,
                     tiers=WATER_TIERS, base_charge_code=_charge(tenant, "BASE-W"))
    s = j70._version(tenant, tariffs["sewer"], model="percent_of_service", uom="kgal", effective_from=JAN1,
                     tiers=(("0", None, str(SEWER_RATE)),), percent=SEWER_PERCENT,
                     basis_service=tm.Service.objects.get(code="water"), percent_basis="usage",
                     base_charge_code=_charge(tenant, "BASE-S"))
    t = _sized_version(tenant, tariffs["trash"], uom="cart", prices=TRASH_EACH, base=_charge(tenant, "BASE-T"))
    f = _sized_version(tenant, tariffs["fire"], uom="connection", prices=FIRE_EACH,
                       base=_charge(tenant, "BASE-FIRE"))
    b = j70._version(tenant, tariffs["battery"], model="flat", uom="kW", effective_from=JAN1,
                     tiers=(("0", None, BATTERY_PER_KW),), base_charge_code=_charge(tenant, "BASE-BAT"))
    so = j70._version(tenant, tariffs["solar"], model="flat", uom="kW", effective_from=JAN1,
                      tiers=(("0", None, SOLAR_PER_KW),), base_charge_code=_charge(tenant, "BASE-SOL"))
    for version, svc in ((w, "water"), (s, "sewer"), (t, "trash"), (f, "fire"), (b, "battery"), (so, "solar")):
        state_size_axis(version, svc)
    # Tax: the signup's own jurisdictions, copied from its sample residential plan.
    source = rm.RatePlan.objects.filter(tenant=tenant, code="SCW-RES").first()
    for rule in rm.PlanTaxRule.objects.filter(tenant=tenant, rate_plan=source):
        rm.PlanTaxRule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, jurisdiction=rule.jurisdiction, tax=rule.tax
        )
    return plan


def ensure_cycle(tenant):
    from apps.metering import models as mm

    cycle, _ = mm.Cycle.objects.get_or_create(
        tenant=tenant, code=CYCLE_CODE,
        defaults={"name": "Six Rivers monthly", "frequency": "Monthly", "start_day": 1,
                  "days_to_complete": 30, "due_days": 21, "first_run_date": JAN1},
    )
    return cycle


def _asset(tenant, actor, asset_no, kind, service, size, unit_id):
    from apps.assets import models as am
    from apps.assets import services as asvc

    if am.Asset.objects.filter(tenant=tenant, asset_no=asset_no).exists():
        return
    asvc.create_asset(actor, {"type": kind, "asset_no": asset_no, "service": service,
                              "unit_id": str(unit_id), "size_class": size, "install_date": "2026-01-05"})


def _account(tenant, actor, unit_id, label, name, phone, opened_at):
    from apps.customers import models as cm
    from apps.customers import services as csvc

    existing = cm.Account.objects.filter(tenant=tenant, unit_id=unit_id).first()
    if existing is not None:
        return existing
    email = name.lower().replace(" ", ".") + "@example.com"
    created = csvc.create_account(actor, {
        "unit_id": str(unit_id), "account_type": ACCOUNT_TYPE, "opened_at": opened_at,
        "contact": {"full_name": name, "phone": phone, "email": email},
        "customer": {"display_name": name, "kind": "person", "identity": {"phone": phone}},
        "addresses": [{"kind": "mailing", "line1": f"{ADDRESS}, {label}", "city": "Katy", "state": "TX"}],
    })
    csvc.activate_account(actor, created["id"])
    return cm.Account.objects.get(pk=created["id"])


def seed(tenant, actor) -> list[str]:
    from apps.customers import models as cm
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.rating import models as rm
    from apps.tenancy import models as tm
    from apps.tenancy import services as tsvc

    from tests.journey_cohort_fixtures import _account_type, _premises_for, _unit_on

    notes: list[str] = []
    enabled = sorted(tm.TenantService.objects.filter(tenant=tenant, enabled=True)
                     .values_list("service__code", flat=True))
    notes.append(f"services on .............. {', '.join(enabled)}")
    tsvc.save_company_profile(actor, {"mailing_address": "400 River Rd, Katy, TX 77494",
                                      "support_phone": "+1 (281) 555-0100"})
    for code, name in REASONS:
        tm.ReasonCode.objects.get_or_create(tenant=tenant, code=code, defaults={"name": name})
    price_bases_by_size(tenant)
    plan = ensure_plan(tenant, actor)
    cycle = ensure_cycle(tenant)
    premises_id = _premises_for(tenant, actor, ADDRESS, list(SERVICES))
    accounts = {}
    for label_no, (name, phone, opened, meter, equipment, deposit) in UNITS.items():
        label = f"Unit {label_no}"
        points = POINTS if label_no not in ("2", "8") else (
            ["water", "trash", "battery"] if label_no == "2" else ["water", "trash"])
        unit_id = _unit_on(tenant, actor, premises_id, label, points)
        mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
        if mm.Unit.objects.get(tenant=tenant, pk=unit_id).rate_plan_id is None:
            msvc.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
        water = j70._meter(tenant, actor, meter, "water", "kgal", unit_id)
        for n, (kind, service, size) in enumerate(equipment, start=1):
            _asset(tenant, actor, f"SR{label_no}-{service[:3].upper()}{n}", kind, service, size, unit_id)
        prior = None
        for day, value in READS[meter]:
            j70._read(tenant, actor, water, day, value, prior, "kgal")
            prior = value
        accounts[label_no] = _account(tenant, actor, unit_id, label, name, phone, opened)
    rm.PlanDepositRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, account_type_id=_account_type(ACCOUNT_TYPE).id,
        defaults={"amount": DEPOSIT, "currency": "USD"},
    )
    for label_no, (_n, _p, _o, _m, _e, deposit) in UNITS.items():
        acct = accounts[label_no]
        if deposit is not None and Decimal(acct.deposit_on_file) != deposit:
            acct.deposit_on_file = deposit
            acct.deposit_received_on = date(2025, 7, 1)
            acct.save(update_fields=["deposit_on_file", "deposit_received_on", "updated_at"])
        agreements = sorted(cm.ServiceAgreement.objects.filter(tenant=tenant, account=acct)
                            .values_list("service_point__service__code", flat=True))
        notes.append(f"Unit {label_no} ................... {acct.account_no} {acct.deposit_on_file} · {agreements}")
    notes.append(j70.keep_walk_month_open(tenant, actor) or "walk month open ........... 2026-09-01 … 2026-09-30")
    return notes


def main() -> int:
    sjf.django_setup()
    provision()
    from django.db import transaction

    from core import tenancy as core_tenancy

    tenant, actor = sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        with transaction.atomic():
            notes = seed(tenant, actor)
    print("J75 six-service world seeded (Six Rivers Utility):")
    for line in notes:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
