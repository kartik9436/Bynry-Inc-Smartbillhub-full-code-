#!/usr/bin/env python3
"""CR-171-BRC10 P4.01 (lane MVI-E2E-SEED) — the starting world for the move-in
end-to-end matrix M1–M7, on a FRESH lane database.

The PO's scope (decision log *"THE END-TO-END SCOPE IS ACCEPTED AND WIDENED"*):
*"inlcude all types of customer categoties, accounts, utilitu services - 5 to 6
or 7 of them; ensure all data in DB is correctly set and all action after
submission are correctly completed and data is refelcted in Units, Assets,
Accounts, Payments, Cycle Route etc"*.

WHY A UTILITY OF ITS OWN AND NOT BRAZOS BEND
--------------------------------------------
Brazos Bend (`seed_demo`) sells electric and water only, and its charge codes,
plans and rates stop there. The matrix needs EIGHT services — electric, water,
gas, sewer, trash, storm water, solar and fire — so this signs a utility up
through the real signup (`tenancy.services.provision_tenant`) with exactly those
eight, then loads its sample set through `load_sample_data` (the same
orchestrator Settings' Sample data panel calls). The signup's own sample plans
(`SCW-RES`, `SCW-COM`, `SCW-IND`) already price all eight, fire's six sizes
included (`FL-2` $12.00 … `FL-12` $230.00), and its sample set brings the
crews, technicians, work-order templates, cycle `CY-001`, routes and message
templates the after-submit checks walk. Same reasoning as
`10-scripts/seed_six_service_one_time.py`, whose helpers this reuses.

Utility **Cedar Ford Utilities** (`mvimatrix`). Owner Marcus Lee (System Admin);
the matrix is driven by **Jo Ramirez, a Billing Clerk** — because the PO ruled
on 2026-10-05 that billing clerks record a move-in's discounts and tax
exemptions themselves (decision log *"FOUR PO RULINGS IN ONE REPLY"* (2)), and
only a clerk's session proves it. Both sign in with `S3cure!passw0rd` (a lane
fixture credential, never production).

WHAT IT ADDS, through the owning modules' services wherever one exists
----------------------------------------------------------------------
* One new premises per case, each with ONE vacant unit carrying exactly the
  case's service points and equipment (§`CASES`), on the case's plan, on cycle
  `CY-001` and on route *Matrix walk*. Every meter carries one committed read
  dated 2026-09-30 in ITS OWN unit — water and sewer in **kgal**, gas in
  **ccf**, electric in kWh (the known trap: the test read helper defaults to
  kWh, so the unit is passed every time).
* Deposit rules (`PlanDepositRule`): Residential $150.00 on `SCW-RES`,
  Commercial $300.00 on `SCW-COM`, Industrial $500.00 on `SCW-IND`. Government
  has no rule, so M7 owes no deposit.
* Fees: `CONN` Connection charge $25.00 named by all three plans (locked plan
  row); `RUSH` Same-day turn-on $40.00 as a code a clerk may add.
* Discounts offered on every plan: `AUTOPAY`, `PAPERLESS`; `CAP` (low-income
  credit) on `SCW-RES` for M3.
* A **city tax**: *City of Cedar Ford utility tax* 2.00% on commercial and
  government accounts, on all three plans, with two exemption categories that
  ask for a certificate — `RELIGIOUS` (the church, M5) and `GOVERNMENT` (the
  school, M7). M5's and M7's premises are inside city limits.
* **Rosa Delgado**, a returning person (SSN 512-44-7781, born 1979-04-12) with
  TWO accounts and **$84.20** outstanding between them ($50.00 + $34.20, posted
  as cutover opening balances through `ledger.opening_balances` — DR AR / CR
  opening clearing, the ledger posting service's own pair). M2 links her.
* **Northgate Provisions LLC**, a company on file with Tax ID 74-3051190 and
  one account, so M4's *Search customer ID* answers *Existing customer*.

Every name, number, date and price here is an ILLUSTRATION (B14 rule 37) except
fire's six prices, which are the signup's seeded defaults, and the $84.00 the
fire line must price to, which is CLAUDE.md's signed worked figure.

USAGE (a fresh, MIGRATED lane database; it writes real rows):

    cd 06-backend && DATABASE_URL=postgres://postgres@127.0.0.1:55433/<lane db> \\
        DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        python ../10-scripts/cr171_e2e_matrix_world.py setup
    … python ../10-scripts/cr171_e2e_matrix_world.py world   # JSON: the cases as seeded

`setup` is idempotent: a second run finds what it wrote and writes nothing
twice. `world` reads only, and is what `cr171_e2e_matrix_run.mjs` asks for.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ["E2E_TENANT"] = "mvimatrix"

SUBDOMAIN = "mvimatrix"
PASSWORD = "S3cure!passw0rd"  # lane fixture credential — never production
OWNER_EMAIL = "marcus@cedarford.example"
CLERK_EMAIL = "jo.ramirez@cedarford.example"
SIGNUP = {
    "name": "Cedar Ford Utilities",
    "subdomain": SUBDOMAIN,
    "state": "Texas",
    "services": ["electric", "water", "gas", "sewer", "trash", "storm_water", "solar", "fire"],
    "currency": "USD",
    "plan": "growth",
    "load_defaults": True,
    "owner": {"full_name": "Marcus Lee", "email": OWNER_EMAIL, "password": PASSWORD,
              "phone": "+1 (512) 555-0140"},
}
READ_ON = "2026-09-30"
ROUTE_NAME = "Matrix walk"
CYCLE_CODE = "CY-001"
DEPOSITS = {("SCW-RES", "residential"): "150.0000", ("SCW-COM", "commercial"): "300.0000",
            ("SCW-IND", "industrial"): "500.0000"}
CONNECT, RUSH = Decimal("25.0000"), Decimal("40.0000")
CITY_TAX = "City of Cedar Ford utility tax"
CITY_RATE = "0.02"

#: The seven cases. `equipment` rows: (asset_no, type, service, unit, size, last read, parent, note).
#: A meter's `last read` is committed on READ_ON in its own unit; None = not a meter.
CASES = {
    "M1": {
        "title": "Residential · Single-family · person — Electric, Water, Sewer, Trash · new customer · field visit · pay by check",
        "address": "41 Larkspur Lane", "premises_type": "single_family", "unit": "Unit 1",
        "plan": "SCW-RES", "account_type": "residential", "subtype": "single_family",
        "services": ["electric", "water", "sewer", "trash"], "inside_city": False,
        "equipment": [
            ("E-M1", "meter", "electric", "kWh", "E-1P-200", "4210", None, None),
            ("W-M1", "meter", "water", "kgal", "W-58", "312.4", None, None),
            ("TR-M1-1", "container_cart", "trash", "cart", "CART-96", None, None, None),
        ],
    },
    "M2": {
        "title": "Residential · Multi-family · person + co-owner — Water (meter + irrigation sub-meter + backflow), Sewer · returning customer linked · add to bill",
        "address": "300 Willow Court", "premises_type": "apartment_complex", "unit": "Apt 2B",
        "plan": "SCW-RES", "account_type": "residential", "subtype": "multi_family",
        "services": ["water", "sewer"], "inside_city": False,
        "equipment": [
            ("W-M2", "meter", "water", "kgal", "W-34", "118.0", None, None),
            ("SW-M2", "sub_meter", "water", "kgal", "W-58", "41.0", "W-M2", "Irrigation"),
            ("BF-M2", "backflow", "water", None, None, None, "W-M2", None),
        ],
    },
    "M3": {
        "title": "Residential · Senior/Low-income · person — Electric, Gas · assistance discount with evidence · part payment",
        "address": "18 Juniper Street", "premises_type": "single_family", "unit": "Unit 1",
        "plan": "SCW-RES", "account_type": "residential", "subtype": "senior_low_income",
        "services": ["electric", "gas"], "inside_city": False,
        "equipment": [
            ("E-M3", "meter", "electric", "kWh", "E-1P-100", "8820", None, None),
            ("G-M3", "meter", "gas", "ccf", "G-250", "1530", None, None),
        ],
    },
    "M4": {
        "title": "Commercial · Small commercial · company with owners — Electric, Water, Sewer, Trash, Storm water · Tax ID match · card",
        "address": "900 Commerce Row", "premises_type": "commercial_building", "unit": "Suite 110",
        "plan": "SCW-COM", "account_type": "commercial", "subtype": "small_commercial",
        "services": ["electric", "water", "sewer", "trash", "storm_water"], "inside_city": False,
        "equipment": [
            ("E-M4", "meter", "electric", "kWh", "E-3P-200", "15022", None, None),
            ("W-M4", "meter", "water", "kgal", "W-1", "640.5", None, None),
            ("TR-M4-1", "container_cart", "trash", "cart", "CART-96", None, None, None),
            ("TR-M4-2", "container_cart", "trash", "cart", "CART-96", None, None, None),
        ],
    },
    "M5": {
        "title": "Commercial · Institutional & non-profit (church) — Water, Sewer, Fire (one 6\" + two 2\" lines) · tax exempt with certificate · Fire $84.00 on one line",
        "address": "12 Chapel Road", "premises_type": "commercial_building", "unit": "Sanctuary",
        "plan": "SCW-COM", "account_type": "commercial", "subtype": "institutional_non_profit",
        "services": ["water", "sewer", "fire"], "inside_city": True,
        "equipment": [
            ("W-M5", "meter", "water", "kgal", "W-2", "88.0", None, None),
            ("FL-M5-6", "fire_line", "fire", "connection", "FL-6", None, None, None),
            ("FL-M5-2A", "fire_line", "fire", "connection", "FL-2", None, None, None),
            ("FL-M5-2B", "fire_line", "fire", "connection", "FL-2", None, None, None),
        ],
    },
    "M6": {
        "title": "Industrial · Light industrial · company — Electric, Gas, Water, Solar (inverter behind the meter) · two work orders",
        "address": "5 Foundry Way", "premises_type": "commercial_building", "unit": "Bay 3",
        "plan": "SCW-IND", "account_type": "industrial", "subtype": "light_industrial",
        "services": ["electric", "gas", "water", "solar"], "inside_city": False,
        "equipment": [
            ("E-M6", "meter", "electric", "kWh", "E-3P-400", "52310", None, None),
            ("G-M6", "meter", "gas", "ccf", "G-630", "7710", None, None),
            ("W-M6", "meter", "water", "kgal", "W-2", "203.0", None, None),
            ("PV-M6", "pv", "solar", "kW", "SOL-P8", None, "E-M6", "Inverter behind the meter"),
        ],
    },
    "M7": {
        "title": "Government · Schools — Water, Sewer, Trash · government exemption · PO number on bills",
        "address": "77 School Lane", "premises_type": "government_building", "unit": "Main campus",
        "plan": "SCW-COM", "account_type": "government", "subtype": "schools",
        "services": ["water", "sewer", "trash"], "inside_city": True,
        "equipment": [
            ("W-M7", "meter", "water", "kgal", "W-3", "1450.0", None, None),
            ("TR-M7-1", "container_cart", "trash", "cart", "CART-96", None, None, None),
            ("TR-M7-2", "container_cart", "trash", "cart", "CART-96", None, None, None),
            ("TR-M7-3", "container_cart", "trash", "cart", "CART-96", None, None, None),
        ],
    },
}

#: The people already on file (the "returning" side of M2 and M4).
ROSA = {"name": "Rosa Delgado", "ssn": "512-44-7781", "dob": "1979-04-12", "phone": "(512) 555-0161",
        "email": "rosa.delgado@example.invalid",
        "accounts": [("2 Aspen Row", "Unit 1", "50.0000"), ("4 Aspen Row", "Unit 1", "34.2000")]}
NORTHGATE = {"name": "Northgate Provisions LLC", "tax_id": "74-3051190", "contact": "Hal Brennan",
             "address": "6 Aspen Row", "unit": "Unit 1"}
OUTSTANDING = Decimal("84.2000")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _setup_django():
    sjf = _load("seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py")
    sjf.django_setup()
    return sjf


# ── 1 · the utility, its sample set, its clerk ─────────────────────────────


def provision() -> list[str]:
    from django.core.management import call_command

    from apps.tenancy import models as tm
    from apps.tenancy import services as tsvc

    notes = []
    if not tm.Tenant.objects.filter(subdomain=SUBDOMAIN).exists():
        # With JOBS_EAGER off the signup only ENQUEUES its sample plant (and logs
        # that no broker answered); `load_sample_data` below is the same plant.
        tsvc.provision_tenant({**SIGNUP, "owner": dict(SIGNUP["owner"])})
        notes.append(f"signed up ................ {SIGNUP['name']} ({SUBDOMAIN})")
    tenant = tm.Tenant.objects.get(subdomain=SUBDOMAIN)
    from core import tenancy as core_tenancy
    from apps.metering import models as mm

    with core_tenancy.tenant_context(tenant.id):
        has_sample = mm.Premises.objects.filter(tenant=tenant, is_sample=True).exists()
    if not has_sample:
        call_command("load_sample_data", tenant=SUBDOMAIN)
        notes.append("sample set loaded ........ load_sample_data")
    return notes


def ensure_clerk(tenant):
    from django.contrib.auth.hashers import make_password
    from django.utils import timezone as dj_tz

    from apps.identity import models as im

    user = im.User.objects.filter(tenant=tenant, email__iexact=CLERK_EMAIL).first()
    if user is None:
        user = im.User.objects.create(
            tenant=tenant, email=CLERK_EMAIL, full_name="Jo Ramirez", phone="(512) 555-0142",
            password_hash=make_password(PASSWORD), must_change_password=False,
            password_changed_at=dj_tz.now(),
        )
        im.TenantMembership.objects.create(
            tenant=tenant, user=user, role=im.Role.objects.get(code="billing_clerk"),
            status=im.TenantMembership.STATUS_ACTIVE,
        )
    return user


# ── 2 · rating: deposits, fees, discounts, the city tax ───────────────────


def ensure_rating(tenant, actor) -> list[str]:
    from apps.customers import models as cm
    from apps.rating import discounts as dm
    from apps.rating import models as rm
    from apps.rating import services as rsvc

    fees = _load("cr171_fee_fixture", BACKEND / "tests/test_cr171_p1_12_move_in_fees.py")
    notes = []
    plans = {p.code: p for p in rm.RatePlan.objects.filter(tenant=tenant, code__in=["SCW-RES", "SCW-COM", "SCW-IND"])}
    for (plan_code, type_code), amount in DEPOSITS.items():
        at = cm.AccountType.objects.get(tenant_id=tenant.id, code=type_code)
        rm.PlanDepositRule.objects.update_or_create(
            tenant=tenant, rate_plan=plans[plan_code], account_type_id=at.id,
            defaults={"amount": Decimal(amount), "currency": "USD"},
        )
    notes.append("deposits ................. RES residential $150.00 · COM commercial $300.00 · IND industrial $500.00")

    conn = fees._code(tenant, "CONN", CONNECT, name="Connection charge")
    rush = fees._code(tenant, "RUSH", RUSH, name="Same-day turn-on")
    # A code with no GL is refused at the first bill's draft (§9.MONEY): both
    # borrow the tenant's own one-time revenue account from a sibling code.
    gl = (rm.Charge.objects.filter(tenant=tenant, charge_type="one_time", gl_account_id__isnull=False)
          .exclude(code__in=["CONN", "RUSH"]).values_list("gl_account_id", flat=True).first())
    for row in (conn, rush):
        if row.gl_account_id is None and gl is not None:
            row.gl_account_id = gl
            row.save(update_fields=["gl_account_id"])
    for plan in plans.values():
        rm.PlanChargeRule.objects.get_or_create(tenant=tenant, rate_plan=plan, charge=conn,
                                                defaults={"role": "charge"})
        for code in ("AUTOPAY", "PAPERLESS") + (("CAP",) if plan.code == "SCW-RES" else ()):
            discount = dm.Discount.objects.get(tenant=tenant, code=code)
            dm.PlanDiscountRule.objects.get_or_create(tenant=tenant, rate_plan=plan, discount=discount)
    notes.append("fees ..................... CONN $25.00 on every plan · RUSH $40.00 a clerk adds")
    notes.append("discounts ................ AUTOPAY, PAPERLESS on every plan · CAP on SCW-RES")

    tax = rm.Tax.objects.filter(tenant=tenant, name=CITY_TAX, deleted_at__isnull=True).first()
    if tax is None:
        city = rm.TaxJurisdiction.objects.filter(tenant=tenant, level="city").first()
        created = rsvc.create_tax(actor, {
            "name": CITY_TAX, "kind": "percent", "rate": CITY_RATE,
            "jurisdiction": str(city.id),
            "applies_to_customer_classes": ["commercial", "government", "municipal"],
            "effective_from": "2026-01-01",
        })
        tax = rm.Tax.objects.get(pk=created["id"])
    # Lane MVI-E2E-3 (M7): `government` was a LEGACY category no form could pick (BR-CUS-094), so a
    # school district moved in as MUNICIPAL. ⚠ Since DEF-CUS-9808 the utility offers Government again
    # (`offer_government`) and M7 moves in as Government · Schools; Municipal stays on the City tax
    # because a public body may be filed under either. Illustration (rule 37).
    # A world built before this line has the tax IN FORCE, which `update_tax` rightly refuses
    # (BIZ-IMMUTABLE); no bill exists in a fresh world, so the fixture widens its own seed row.
    classes = list(tax.applies_to_customer_classes or [])
    if "municipal" not in classes:
        rm.Tax.objects.filter(pk=tax.pk).update(applies_to_customer_classes=classes + ["municipal"])
        tax.refresh_from_db()
    for plan in plans.values():
        # A plan names a JURISDICTION (or one tax, never both — ck_plan_tax_rules_one_source);
        # the City row brings every in-force tax of the city with it.
        if not rm.PlanTaxRule.objects.filter(tenant=tenant, rate_plan=plan, jurisdiction=tax.jurisdiction).exists():
            rm.PlanTaxRule.objects.create(tenant=tenant, rate_plan=plan, jurisdiction=tax.jurisdiction)
    for code, name, proof in (("RELIGIOUS", "Religious organisation", "Proof of 501(c)(3)"),
                              ("GOVERNMENT", "Government entity", "Government exemption letter")):
        if not rm.TaxExemptionCategory.objects.filter(tenant=tenant, tax=tax, code=code, deleted_at__isnull=True).exists():
            rsvc.create_exemption_category(actor, str(tax.id), {
                "code": code, "name": name, "requires_certificate": True, "certificate_requirement": proof})
    notes.append(f"city tax ................. {CITY_TAX} 2.00% commercial + government · RELIGIOUS, GOVERNMENT exemptions")
    return notes


def offer_government(tenant) -> list[str]:
    """Lane DEF-9786-9788 (`DEF-CUS-9786`, `DEF-CUS-9808`) — the PO's M7 is Government · Schools.

    `government` is seeded LEGACY (BR-CUS-094), so no form offers it. The PO ruled on 2026-09-18
    that any tenant admin may clear that flag on any row (OQ-CUS-12407 option a), and on 2026-09-23
    that sub-categories come from Settings → Reference data, no seed row moved (OQ-CUS-12618). So a
    utility that bills a school district does exactly this on Settings → Reference data → Account
    types → *Offer again*, through the card's own handler — and the seeded Schools sub-type under
    Government becomes pickable. Before `DEF-CUS-9808` the handler ignored the key and this was a
    no-op, which is why the line below READS THE ROW BACK instead of trusting the call."""
    from apps.customers import lookups as customer_lookups
    from apps.customers import models as customer_models

    row = customer_models.AccountType.objects.get(tenant=tenant, code="government")
    if row.legacy:
        customer_lookups.AccountTypeLookupHandler().update(row, {"legacy": False})
        row.refresh_from_db()
    return [f"account types ............ Government offered on new accounts: {not row.legacy} "
            "(Settings › Account types › Offer again)"]


# ── 3 · the seven units ─────────────────────────────────────────────────────


def _premises(tenant, actor, address, ptype, services, inside_city):
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from tests.test_us_met_helpers import make_premises

    row = mm.Premises.objects.filter(tenant=tenant, address_line=address).first()
    if row is None:
        created = make_premises(actor, address_line=address, city="Cedar Ford", state="TX",
                                postal_code="78610", services_available=services,
                                owner_manager="Cedar Ford Holdings")
        row = mm.Premises.objects.get(pk=created["id"])
    wanted = {"inside_city_limits": inside_city}
    ptype_row = mm.PremisesType.objects.filter(tenant=tenant, code=ptype).first() if ptype else None
    if ptype_row is not None:
        wanted["premises_type_id"] = ptype_row.id
    dirty = [k for k, v in wanted.items() if getattr(row, k) != v]
    if dirty:
        for k in dirty:
            setattr(row, k, wanted[k])
        row.save(update_fields=dirty)
    return row


def _unit(tenant, actor, premises, label, services, plan):
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from tests.test_us_met_helpers import make_unit

    unit = mm.Unit.objects.filter(tenant=tenant, premises=premises, label=label).first()
    if unit is None:
        created = make_unit(actor, str(premises.id), label=label, services=services,
                            unit_type="commercial" if premises.premises_type_id and
                            premises.premises_type.code != "single_family" and
                            premises.premises_type.code != "apartment_complex" else "residential")
        unit = mm.Unit.objects.get(pk=created["id"])
    if unit.rate_plan_id is None:
        msvc.assign_unit_plan(actor, str(unit.id), {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
        unit.refresh_from_db()
    return unit


def _equipment(tenant, actor, unit, rows):
    from apps.assets import models as am
    from apps.assets import services as asvc

    seeded = []
    for asset_no, kind, service, uom, size, last_read, parent, note in rows:
        found = am.Asset.objects.filter(tenant=tenant, asset_no=asset_no).first()
        if found is None:
            payload = {"type": kind, "asset_no": asset_no, "service": service,
                       "unit_id": str(unit.id), "install_date": "2026-01-05", "status": "active"}
            if kind in ("meter", "sub_meter"):
                payload.update({"unit": uom, "multiplier": "1", "register_digits": 6,
                                "read_method": "manual"})
            elif uom:
                payload["unit"] = uom
            if size:
                payload["size_class"] = size
            if parent:
                payload["parent_asset_no"] = parent
            if note:
                payload["location_note"] = note
            if kind == "backflow":
                payload.update({"last_test_date": "2026-03-15", "test_interval_months": 12})
            found = am.Asset.objects.get(pk=asvc.create_asset(actor, payload)["id"])
        seeded.append(found)
        if last_read is not None:
            _read(tenant, actor, found, last_read, uom)
    return seeded


def _read(tenant, actor, asset, value, uom):
    from apps.metering.models import MeterRead
    from tests.test_us_met_reads_helpers import at, commit_read

    if MeterRead.objects.filter(tenant=tenant, asset_id=asset.id, channel="total").exists():
        return
    # ⚠ THE UNIT IS PASSED EVERY TIME: `commit_read` saves kWh when told
    # nothing, and a water meter read in kWh is a different meter.
    commit_read(actor, str(asset.id), day=READ_ON, value=str(value), unit=uom)


def ensure_route(tenant, actor, premises_ids, services):
    from apps.metering import models as mm
    from apps.metering import services as msvc

    cycle = mm.Cycle.objects.get(tenant=tenant, code=CYCLE_CODE)
    route = mm.Route.objects.filter(tenant=tenant, name=ROUTE_NAME, deleted_at__isnull=True).first()
    if route is None:
        msvc.create_route(actor, {"name": ROUTE_NAME, "route_type": "walk", "service_codes": services,
                                  "cycle_id": str(cycle.id), "premises_ids": [str(p) for p in premises_ids]})
        route = mm.Route.objects.get(tenant=tenant, name=ROUTE_NAME, deleted_at__isnull=True)
    mm.ServicePoint.objects.filter(tenant=tenant, unit__premises_id__in=premises_ids).update(cycle=cycle)
    return route, cycle


def ensure_units(tenant, actor) -> list[str]:
    from apps.rating import models as rm

    notes = []
    plans = {p.code: p for p in rm.RatePlan.objects.filter(tenant=tenant, code__in=["SCW-RES", "SCW-COM", "SCW-IND"])}
    premises_ids = []
    for key, case in CASES.items():
        premises = _premises(tenant, actor, case["address"], case["premises_type"], case["services"],
                             case["inside_city"])
        unit = _unit(tenant, actor, premises, case["unit"], case["services"], plans[case["plan"]])
        assets = _equipment(tenant, actor, unit, case["equipment"])
        premises_ids.append(premises.id)
        notes.append(f"{key} ....................... {unit.unit_no} {case['address']} · {case['unit']} · "
                     f"{case['plan']} · {','.join(case['services'])} · {', '.join(a.asset_no for a in assets)}")
    all_services = sorted({s for c in CASES.values() for s in c["services"]})
    route, cycle = ensure_route(tenant, actor, premises_ids, all_services)
    notes.append(f"route .................... {route.code} {route.name} on {cycle.code}")
    return notes


# ── 4 · the people already on file ─────────────────────────────────────────


def _history_unit(tenant, actor, address, label, services, plan):
    premises = _premises(tenant, actor, address, "single_family", services, False)
    return _unit(tenant, actor, premises, label, services, plan)


def ensure_people(tenant, actor) -> list[str]:
    from apps.customers import models as cm
    from apps.customers import services as csvc
    from apps.ledger import opening_balances as ob
    from apps.rating import models as rm

    notes = []
    res = rm.RatePlan.objects.get(tenant=tenant, code="SCW-RES")
    com = rm.RatePlan.objects.get(tenant=tenant, code="SCW-COM")
    rosa_accounts = []
    for address, label, balance in ROSA["accounts"]:
        unit = _history_unit(tenant, actor, address, label, ["water"], res)
        account = cm.Account.objects.filter(tenant=tenant, unit_id=unit.id).first()
        if account is None:
            payload = {"account_type": "residential", "opened_at": "2025-03-01",
                       "contact": {"full_name": ROSA["name"], "email": ROSA["email"], "phone": ROSA["phone"]}}
            existing = cm.Customer.objects.filter(tenant=tenant, display_name=ROSA["name"]).first()
            if existing is None:
                payload["customer"] = {"kind": "person", "display_name": ROSA["name"],
                                       "identity": {"ssn": ROSA["ssn"], "date_of_birth": ROSA["dob"],
                                                    "phone": ROSA["phone"]}}
            else:
                payload["customer"] = {"customer_id": str(existing.id), "kind": "person",
                                       "display_name": ROSA["name"]}
            account = cm.Account.objects.get(pk=csvc.move_in_to_unit(actor, unit.id, payload)["id"])
        rosa_accounts.append((account, Decimal(balance)))
    for account, balance in rosa_accounts:
        ob.post_opening_balance(
            ob.OpeningAccount(account_id=account.id, balance=balance, account_ref=account.account_no),
            batch_id="cr171-e2e-matrix-rosa", cutover_on=date(2026, 8, 31),
            imported_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc), currency="USD", actor=actor,
        )
    notes.append(f"returning person ......... {ROSA['name']} SSN …{ROSA['ssn'][-4:]} · "
                 + " + ".join(f"{a.account_no} ${b:.2f}" for a, b in rosa_accounts) + f" = ${OUTSTANDING:.2f}")

    unit = _history_unit(tenant, actor, NORTHGATE["address"], NORTHGATE["unit"], ["water"], com)
    account = cm.Account.objects.filter(tenant=tenant, unit_id=unit.id).first()
    if account is None:
        account = cm.Account.objects.get(pk=csvc.move_in_to_unit(actor, unit.id, {
            "account_type": "commercial", "opened_at": "2025-06-01",
            "contact": {"full_name": NORTHGATE["contact"], "job_title": "Owner",
                        "email": "hal@northgate.example.invalid", "phone": "(512) 555-0177", "contact_by": "email"},
            "customer": {"kind": "company", "display_name": NORTHGATE["name"],
                         "identity": {"tax_id": NORTHGATE["tax_id"]}},
            "company": {"trading_as": "Northgate Market", "business_type": "llc", "registered_in": "TX"},
        })["id"])
    notes.append(f"company on file .......... {NORTHGATE['name']} Tax ID …{NORTHGATE['tax_id'][-4:]} · {account.account_no}")
    return notes


# ── P4.26 (lane MVI-E2E-3): two move-in REQUESTS, To approve ───────────────
#
# A request is what a customer or the counter SENDS; the path under test is what
# the clerk then does with it on the details view (Ask for more → Approve → Start
# → Complete; and Decline). So the two requests are seeded through the request's
# own writers — exactly `tests/test_cr171_move_in_request_view.py::_to_approve`'s
# walk: create → attach a photo ID → submit → resolve the address → no customer
# linked → verify the document. No outcome is decided: the details view's
# Approve sends `outcome: move_in` itself (CR-171 §9.REQ). Each request resolves
# to its OWN vacant unit, built here, so M1–M7's units are never touched.
#
# Run AFTER `setup`, on a world kept for P4.26 alone: `… world.py requests`.
REQUESTS = {
    "R1": {"address": "21 Lantern Way", "unit": "Unit 1", "meter": ("W-R1", "96.0"),
           "applicant": "Maya Okonkwo", "email": "maya.okonkwo@example.invalid",
           "phone": "(512) 555-0131", "what": "Moving into 21 Lantern Way on the 12th"},
    "R2": {"address": "23 Lantern Way", "unit": "Unit 1", "meter": ("W-R2", "54.0"),
           "applicant": "Victor Hale", "email": "victor.hale@example.invalid",
           "phone": "(512) 555-0136", "what": "Need water on at 23 Lantern Way"},
}
REQUEST_START = "2026-10-12"


def ensure_requests(tenant, actor) -> list[str]:
    from apps.customers import models as cm
    from apps.customers import service_request_service as sr
    from apps.metering import models as mm
    from apps.rating import models as rm

    notes = []
    res = rm.RatePlan.objects.get(tenant=tenant, code="SCW-RES")
    cycle = mm.Cycle.objects.get(tenant=tenant, code=CYCLE_CODE)
    for key, spec in REQUESTS.items():
        premises = _premises(tenant, actor, spec["address"], "single_family", ["water", "sewer"], False)
        unit = _unit(tenant, actor, premises, spec["unit"], ["water", "sewer"], res)
        meter, last = spec["meter"]
        _equipment(tenant, actor, unit, [(meter, "meter", "water", "kgal", "W-58", last, None, None)])
        mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit.id).update(cycle=cycle)
        found = cm.ServiceRequest.objects.filter(tenant=tenant, applicant_name=spec["applicant"]).first()
        if found is None:
            request = sr.create_request(actor, {
                "channel": "counter", "applicant_kind": "person", "applicant_name": spec["applicant"],
                "applicant_email": spec["email"], "applicant_phone": spec["phone"],
                "address_as_given": str(unit.unit_no), "property_type": "standalone_owner_occupied",
                "requested_start": REQUEST_START, "what_they_said": spec["what"],
            })
            sr.set_customer_category(actor, request.id, account_type_code="residential")
            doc = sr.attach_document(actor, request.id, doc_type=cm.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY,
                                     name="photo-id.jpg", storage_ref="s3://e2e3/photo-id.jpg")
            sr.submit(actor, request.id)
            sr.resolve_address(actor, request.id)
            sr.link_customer(actor, request.id, customer_id=None)
            sr.verify_document(actor, doc.id)
            found = sr.request_row(request.id)
        notes.append(f"{key} request ............... {found.request_no} {spec['applicant']} → {unit.unit_no} "
                     f"{spec['address']} · {found.state}")
    return notes


# ── the world, read back (for the runner) ──────────────────────────────────


def world(tenant) -> dict:
    from apps.assets import models as am
    from apps.metering import models as mm

    out = {"tenant": SUBDOMAIN, "clerk": CLERK_EMAIL, "owner": OWNER_EMAIL, "password": PASSWORD,
           "returning": {"name": ROSA["name"], "ssn": ROSA["ssn"], "dob": ROSA["dob"],
                         "outstanding": f"{OUTSTANDING:.2f}"},
           "company": {"name": NORTHGATE["name"], "tax_id": NORTHGATE["tax_id"]}, "cases": {},
           "requests": {}}
    from apps.customers import models as cm

    for key, spec in REQUESTS.items():  # P4.26 (lane MVI-E2E-3); absent until `requests` ran
        row = cm.ServiceRequest.objects.filter(tenant=tenant, applicant_name=spec["applicant"]).first()
        unit = mm.Unit.objects.filter(tenant=tenant, premises__address_line=spec["address"], label=spec["unit"]).first()
        if row is not None and unit is not None:
            out["requests"][key] = {"request_no": row.request_no, "id": str(row.id), "state": row.state,
                                    "applicant": spec["applicant"], "unit_no": unit.unit_no,
                                    "unit_id": str(unit.id), "address": spec["address"],
                                    "meter": spec["meter"][0], "last_read": spec["meter"][1]}
    for key, case in CASES.items():
        unit = mm.Unit.objects.filter(tenant=tenant, premises__address_line=case["address"], label=case["unit"]).first()
        out["cases"][key] = {
            **{k: case[k] for k in ("title", "address", "unit", "plan", "account_type", "subtype", "services")},
            "unit_no": unit.unit_no if unit else None,
            "unit_id": str(unit.id) if unit else None,
            "assets": [{"asset_no": r[0], "type": r[1], "service": r[2], "unit": r[3], "size": r[4],
                        "last_read": r[5], "parent": r[6],
                        "exists": am.Asset.objects.filter(tenant=tenant, asset_no=r[0]).exists()}
                       for r in case["equipment"]],
        }
    return out


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "setup"
    sjf = _setup_django()
    from django.db import transaction

    from core import tenancy as core_tenancy

    notes = provision() if command == "setup" else []
    from apps.tenancy import models as tm

    tenant = tm.Tenant.objects.get(subdomain=SUBDOMAIN)
    _tenant, actor = sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        if command == "world":
            print(json.dumps(world(tenant), indent=2))
            return 0
        if command == "requests":  # P4.26 (lane MVI-E2E-3), after `setup`
            with transaction.atomic():
                notes = ensure_requests(tenant, actor)
            print("CR-171 move-in matrix — P4.26's two requests:")
            for line in notes:
                print("  " + line)
            return 0
        with transaction.atomic():
            ensure_clerk(tenant)
            # The people already on file moved in BEFORE the deposit rules
            # existed, as a real history would have it — their move-ins are not
            # the subject here, and a rule they predate asks them nothing.
            notes += ensure_people(tenant, actor)
            notes += ensure_rating(tenant, actor)
            notes += offer_government(tenant)  # M7 (lane DEF-9786-9788)
            notes += ensure_units(tenant, actor)
    print("CR-171 move-in matrix world (Cedar Ford Utilities, mvimatrix):")
    for line in notes:
        print("  " + line)
    print(f"  sign in .................. {CLERK_EMAIL} (Billing Clerk) / {OWNER_EMAIL} (System Admin)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
