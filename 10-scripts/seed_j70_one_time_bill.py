#!/usr/bin/env python3
"""seed_j70_one_time_bill — the `OTB` world journey J70 (E1–E10) clicks through.

Journey: `08-qa/01-e2e/journeys/J70-one-time-bill-redesign.md` · build plan
`04-docs/05-modules/07-billing/12-one-time-bill-build-plan.md` E1–E11 · spec
`07-frontend/e2e/J70-one-time-bill.spec.ts`.

Run it on a stack that `manage.py migrate` and `manage.py seed_demo` have
already built (Brazos Bend, owner Dana Whitfield), with the same environment
Django runs under:

    cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
        python ../10-scripts/seed_j70_one_time_bill.py

WHAT IT BUILDS, AND WHY SIX UNITS INSTEAD OF ONE
------------------------------------------------
J70 says every E-case after E1 starts from a *fresh seed* of the same account.
One database cannot be fresh six times over, so each kind gets its own copy of
the J70 unit at the same premises — the same services, the same two water
meters, the same electric meter, one trash cart, gas and fire points with NO
asset, broadband offered and not taken, sewer with NO service point:

    Unit A  Maria Alvarez   — E1 interim · E7 problems · E8 already billed · E10 below-last · E6 fee
    Unit B  Dana Brooks     — E9: water + electric + trash, NO service agreements
    Unit C  Maria Alvarez   — E2 first bill (moved in Sep 12; W-…43 has no move-in read)
    Unit D  Maria Alvarez   — E3 final (move-out Sep 18; $150.00 deposit on file)
    Unit E  Maria Alvarez   — E4 catch-up (billed Jul–Sep, August being closed; July unread on the second water meter)
    Unit F  Maria Alvarez   — E5 penalty (Jun–Sep read; billed Jul–Sep, see below)
    Unit I  Hannah Ortiz    — J74 case 2: water only, one meter, unread since Aug 31
    Unit J  Samuel Okafor   — J74 case 4: final, a $50.00 deposit LESS than the bill
    Unit K  Nina Castillo   — the PO-reports walk: its plan's only water rate ends Jul 31
    Unit L  John Mauli      — the PO-reports walk: on NO billing cycle (DEF-BIL-8330)

(Units G and H are J70's P4/P5 accounts; J74 — `08-qa/01-e2e/journeys/
J74-one-time-bill-end-to-end.md` — bills A, C, D, E, F and H as well.)

Meter numbers carry the unit's letter (`W-10442` on A, `W-10442C` on C …)
because `assets.asset_no` is unique per tenant.

HOW IT WRITES — through the owning modules' services wherever one exists
------------------------------------------------------------------------
Premises, units, meters, plan assignment, accounts and their activation go
through `metering.services`, `assets.services` and `customers.services`, the
same calls `tests/journey_cohort_fixtures.py` and the CR-062 capacity suite use.
Rate VERSIONS, tiers, base charge codes, cycles and history reads are written
with the ORM under `app.tenant_id` (the shape every billing test builds them in:
there is no service that writes a version's tiers in one call). No raw SQL.

The figures are J70's fixture VALUES (EP-BIL-03 `OTB`), not signed law; no ❄️
B4/B5 figure is touched.
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

_spec = importlib.util.spec_from_file_location(
    "seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py"
)
sjf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sjf)  # type: ignore[union-attr]

PLAN_NAME = "Residential Standard (Elm St)"  # seed_demo already owns "Residential Standard"
PLAN_CODE = "RES-STD-J70"
SERVICES = ("water", "electric", "trash", "sewer", "gas", "fire", "broadband")
UNIT_POINTS = ["water", "electric", "trash", "gas", "fire", "broadband"]  # no sewer point
ADDRESS = "1408 Elm St"

WATER_TIERS_V1 = (("0", "5", "3.0000"), ("5", None, "4.2500"))  # to Jul 15
WATER_TIERS_V2 = (("0", "5", "3.2500"), ("5", None, "4.5000"))  # from Jul 16 (E4's split)
ELECTRIC_RATE = Decimal("0.1245")
TRASH_PER_CART = Decimal("15.0000")
SEWER_PERCENT = Decimal("40.000000")  # percent POINTS, as rating stores them (40 = 40%)
SEWER_RATE = Decimal("5.0000")
BASES = {"water": ("BASE-W-J70", "8.0000"), "trash": ("BASE-T", "3.0000"), "sewer": ("BASE-S", "6.0000")}
DEPOSIT = Decimal("150.0000")
#: J74 case 4 — a final bill whose deposit is LESS than it owes.
J74_SMALL_DEPOSIT = Decimal("50.0000")
#: ⚠ THE ELM ST ACCOUNTS ARE `institutional`, AND THAT IS THE ONE FIXTURE
#: COMPROMISE IN THIS FILE. J70's electric has NO base charge code (E1:
#: "$0.00 + a warning"), but `seed_demo` already mints `BASE-E` ($12.00) for
#: every RESIDENTIAL account, so a residential account can never meet an
#: electric service with no base. Rather than delete or rescope a row seed_demo
#: owns, these accounts carry a customer class no seeded base code names, and
#: water's $8.00 base is minted here scoped to that class (`BASE-W-J70`). Trash
#: and sewer bases are unscoped. Every figure J70 asserts is unchanged.
ACCOUNT_TYPE = "institutional"
CYCLE_CODE = "J70-MONTHLY"
#: DEF-BIL-8333 — the cycle's first run (its calendar anchor). Monthly from day 1.
CYCLE_FIRST_RUN = date(2026, 1, 1)
#: DEF-BIL-8334 (coordinator ruling 2026-10-01) — the month the J70/J74 walk world is
#: PINNED to. Every walk bill is dated in it and every worked figure depends on its
#: length (Sep 12–30 is 19/30; on October dates the same case is 19/31), so it is
#: never re-dated relative to today, and a walk database leaves it OPEN.
WALK_MONTH = (date(2026, 9, 1), date(2026, 9, 30))
WALK_MONTH_REOPEN_REASON = (
    "J70/J74 walk world is pinned to September 2026 (DEF-BIL-8334): the demo's rolling "
    "calendar closed it, and the walk's bills are dated in it."
)
DUE_DAYS = 21
REASONS = (("MISSED", "Missed billing"), ("METER-FAULT", "Meter fault"), ("THEFT", "Theft"), ("TAMPER", "Tamper"))


def _version(tenant, tariff, *, model, uom, effective_from, effective_to=None, tiers=(), **extra):
    from apps.rating import models as rm

    found = rm.TariffVersion.objects.filter(tenant=tenant, tariff=tariff, effective_from=effective_from).first()
    if found is not None:
        return found
    version = rm.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model=model,
        uom=uom,
        currency="USD",
        effective_from=effective_from,
        effective_to=effective_to,
        **extra,
    )
    for seq, (lo, hi, price) in enumerate(tiers, start=1):
        rm.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=seq,
            from_qty=Decimal(lo),
            to_qty=None if hi is None else Decimal(hi),
            unit_price=Decimal(price),
        )
    return version


def _base_code(tenant, service_code, code, amount):
    from apps.rating import models as rm
    from apps.tenancy import models as tm

    charge, _ = rm.Charge.objects.get_or_create(
        tenant=tenant,
        code=code,
        defaults=dict(
            name=f"{service_code.title()} base",
            charge_type="recurring",
            service=tm.Service.objects.get(code=service_code),
            amount_rule="flat",
            amount=Decimal(amount),
            is_base=True,
            applies_to_customer_classes=[ACCOUNT_TYPE] if service_code == "water" else [],
        ),
    )
    return charge


def ensure_plan(tenant, actor):
    from apps.rating import models as rm
    from apps.rating import selectors as rsel
    from apps.tenancy import models as tm
    from tests.test_us_met_helpers import make_plan, state_size_axis

    plan = make_plan(tenant, name=PLAN_NAME, code=PLAN_CODE, services=SERVICES)
    tariffs = {row["service_code"]: row["tariff"] for row in rsel.plan_rate_schedules(plan.id)}
    jan1, jul15, jul16 = date(2026, 1, 1), date(2026, 7, 15), date(2026, 7, 16)
    bases = {svc: _base_code(tenant, svc, code, amt) for svc, (code, amt) in BASES.items()}

    w1 = _version(tenant, tariffs["water"], model="tiered", uom="kgal", effective_from=jan1,
                  effective_to=jul15, tiers=WATER_TIERS_V1, base_charge_code=bases["water"])
    w2 = _version(tenant, tariffs["water"], model="tiered", uom="kgal", effective_from=jul16,
                  tiers=WATER_TIERS_V2, base_charge_code=bases["water"])
    for v in (w1, w2):
        state_size_axis(v, "water")
    # Electric: NO base charge code defined or bound (J70 — "$0.00 + a warning").
    e = _version(tenant, tariffs["electric"], model="flat", uom="kWh", effective_from=jan1,
                 tiers=(("0", None, str(ELECTRIC_RATE)),))
    state_size_axis(e, "electric")
    t = _version(tenant, tariffs["trash"], model="tiered", uom="cart", effective_from=jan1,
                 tiers=(("0", None, str(TRASH_PER_CART)),), base_charge_code=bases["trash"])
    state_size_axis(t, "trash")
    _version(tenant, tariffs["sewer"], model="percent_of_service", uom="kgal", effective_from=jan1,
             tiers=(("0", None, str(SEWER_RATE)),), percent=SEWER_PERCENT,
             basis_service=tm.Service.objects.get(code="water"), percent_basis="usage",
             base_charge_code=bases["sewer"])
    for svc, uom in (("gas", "therm"), ("fire", "line"), ("broadband", "month")):
        v = _version(tenant, tariffs[svc], model="flat", uom=uom, effective_from=jan1,
                     tiers=(("0", None, "1.0000"),))
        state_size_axis(v, svc)
    # Tax: the SAME jurisdictions seed_demo binds to its own "Residential
    # Standard" (Texas State 6.25% + Local 2.00% = J70's 8.25%), copied rather
    # than restated so the two plans cannot disagree about who taxes them.
    source = rm.RatePlan.objects.filter(tenant=tenant, name="Residential Standard").first()
    for rule in rm.PlanTaxRule.objects.filter(tenant=tenant, rate_plan=source):
        rm.PlanTaxRule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, jurisdiction=rule.jurisdiction, tax=rule.tax
        )
    # ⚠ seed_demo leaves every tax's liability account NULL (its summary says
    # GL mappings are not seeded), and ISSUE refuses a bill whose tax line has
    # no liability account to stamp — so no taxed bill on this tenant can be
    # SENT. Each authority mints its own 2200-series account through the one
    # ledger service that may (B5 line 74, the journey cohorts' own path).
    from apps.ledger import services as ledger_services

    for tax in rm.Tax.objects.filter(tenant=tenant, liability_gl_account_id__isnull=True):
        account = ledger_services.create_tax_authority_account(
            name=f"Tax payable — {tax.name}", actor=getattr(actor, "user", actor)
        )
        rm.Tax.objects.filter(pk=tax.pk).update(liability_gl_account_id=account.id)
    return plan


def keep_walk_month_open(tenant, actor) -> str | None:
    """`DEF-BIL-8334` — leave `WALK_MONTH` open on a walk database. Returns a note line.

    The main demo's calendar rolls with today (`core.sample_fixture`), so `seed_demo`
    run on 1 October closes SEPTEMBER — and every J70/J74 bill is dated in September,
    so Send refused them all. The ruling pins the walk world rather than moving it,
    and changes ONLY the walk world: the main demo keeps rolling and still closes the
    month it closes; this seed, which only a walk database runs, reopens its own walk
    month through ledger's own door (`close.reopen_period`, reason and audit row,
    BR-LED-006) when — and only when — the demo closed it. A demo seeded in September
    closes August and this does nothing.
    """
    from django.utils import timezone

    from apps.ledger import close as ledger_close

    start, end = WALK_MONTH
    if not ledger_close.is_period_closed(start, end):
        return None
    # The ACTOR, not its user row: `reopen_period` is System-Admin-only
    # (BR-LED-006) and `require_role` reads `actor.role`, which the user row lacks.
    ledger_close.reopen_period(
        actor,
        period_start=start,
        period_end=end,
        # A seed, not a money path: the reopen is stamped when the walk database is built.
        reopened_at=timezone.now(),
        reason=WALK_MONTH_REOPEN_REASON,
    )
    return f"walk month reopened ...... {start} … {end} (the demo's rolling calendar had closed it)"


def ensure_cycle(tenant):
    from apps.metering import models as mm

    # ⚠ `DEF-BIL-8333` (coordinator ruling 2026-09-30) — a FIRST RUN DATE, as
    # every cycle made in Settings has. Without it metering cannot say how long
    # the cycle is (`billing_period_for_unit` → None), so every first and final
    # bill in this demo silently charged WHOLE bases instead of prorating
    # (B4.3 / BR-BIL-012 / BR-BIL-1047). And an existing demo database is
    # REPAIRED on a re-run: `get_or_create` alone would leave its old row as it was.
    cycle, _ = mm.Cycle.objects.get_or_create(
        tenant=tenant,
        code=CYCLE_CODE,
        defaults={
            "frequency": "Monthly",
            "start_day": 1,
            "days_to_complete": 30,
            "due_days": DUE_DAYS,
            "first_run_date": CYCLE_FIRST_RUN,
        },
    )
    if cycle.first_run_date is None:
        cycle.first_run_date = CYCLE_FIRST_RUN
        cycle.save(update_fields=["first_run_date"])
    return cycle


def _unit(tenant, actor, premises_id, label, points):
    from tests.journey_cohort_fixtures import _unit_on

    return _unit_on(tenant, actor, premises_id, label, points)


def _meter(tenant, actor, asset_no, service, uom, unit_id):
    from apps.assets import models as am
    from tests.test_us_met_reads_helpers import a_meter

    row = am.Asset.objects.filter(tenant=tenant, asset_no=asset_no).first()
    if row is not None:
        return str(row.id)
    return a_meter(actor, asset_no=asset_no, service=service, uom=uom, unit_id=unit_id)["id"]


def _router(tenant, actor, asset_no, unit_id):
    from apps.assets import models as am
    from apps.assets import services as asvc

    row = am.Asset.objects.filter(tenant=tenant, asset_no=asset_no).first()
    if row is not None:
        return str(row.id)
    return asvc.create_asset(
        actor,
        {
            "type": "modem_cpe",
            "asset_no": asset_no,
            "service": "broadband",
            "unit_id": str(unit_id),
            "install_date": "2026-01-05",
        },
    )["id"]


def _cart(tenant, actor, asset_no, unit_id):
    from apps.assets import models as am
    from apps.assets import services as asvc

    row = am.Asset.objects.filter(tenant=tenant, asset_no=asset_no).first()
    if row is not None:
        return str(row.id)
    return asvc.create_asset(
        actor,
        {
            "type": "container_cart",
            "asset_no": asset_no,
            "service": "trash",
            "unit_id": str(unit_id),
            "size_class": "CART-96",
            "install_date": "2026-01-05",
        },
    )["id"]


def _read(tenant, actor, asset_id, day, value, prior, unit):
    from apps.metering.models import MeterRead
    from tests.test_us_met_reads_helpers import at, commit_read

    if MeterRead.objects.filter(tenant=tenant, asset_id=asset_id, read_at=at(day), channel="total").exists():
        return
    consumption = None if prior is None else Decimal(value) - Decimal(prior)
    # The day count and the start day a real posting stamps (`_post_row`):
    # metering's estimate averages consumption over `days_since_prior`, and a
    # history row with no day count reads as 10.4 kgal over 0 days and refuses
    # (DEF-BIL-8324 walk, 2026-09-30). Test data, made faithful to a real read.
    previous = (
        MeterRead.objects.filter(tenant=tenant, asset_id=asset_id, channel="total", read_at__lt=at(day))
        .order_by("-read_at")
        .first()
    )
    commit_read(actor, asset_id, day=day, value=str(value),
                prior_value=None if prior is None else str(prior),
                consumption=None if consumption is None else str(consumption), unit=unit,
                days_since_prior=(at(day) - previous.read_at).days if previous else None,
                period_start=previous.read_at.date() if previous else None)


def _account(tenant, actor, unit_id, name, phone, opened_at, email):
    from apps.customers import models as cm
    from apps.customers import services as csvc

    existing = cm.Account.objects.filter(tenant=tenant, unit_id=unit_id).first()
    if existing is not None:
        return existing
    created = csvc.create_account(
        actor,
        {
            "unit_id": str(unit_id),
            "account_type": ACCOUNT_TYPE,
            "opened_at": opened_at,
            "contact": {"full_name": name, "phone": phone, "email": email},
            "customer": {"display_name": name, "kind": "person", "identity": {"phone": phone}},
            "addresses": [{"kind": "mailing", "line1": ADDRESS, "city": "Katy", "state": "TX"}],
        },
    )
    csvc.activate_account(actor, created["id"])
    return cm.Account.objects.get(pk=created["id"])


def seed(tenant, actor) -> list[str]:
    from apps.customers import models as cm
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.rating import models as rm
    from apps.tenancy import models as tm
    from tests.journey_cohort_fixtures import _account_type, _premises_for, ensure_services_enabled

    notes: list[str] = []
    turned_on = ensure_services_enabled(tenant, actor, *SERVICES)
    tm.TenantService.objects.filter(tenant=tenant, service__code__in=["trash", "fire"]).update(
        billing_basis="capacity"
    )
    notes.append(f"services on .............. {', '.join(SERVICES)} (turned on now: {turned_on or 'none'})")
    for code, name in REASONS:
        tm.ReasonCode.objects.get_or_create(tenant=tenant, code=code, defaults={"name": name})
    # J70's charge codes: RECON is TAXABLE (E6 — $75.00 → $81.19 at 8.25% under
    # the B4.2 re-sign of 2026-09-30); seed_demo ships it non-taxable.
    rm.Charge.objects.filter(tenant=tenant, code="RECON").update(taxable_default=True)
    plan = ensure_plan(tenant, actor)
    cycle = ensure_cycle(tenant)
    premises_id = _premises_for(tenant, actor, ADDRESS, list(SERVICES))

    worlds = [
        # letter, name, phone, opened_at, email, agreements?
        ("A", "Maria Alvarez", "+1 (281) 555-0142", "2025-07-01", "maria.alvarez@example.com"),
        ("C", "Maria Alvarez", "+1 (281) 555-0143", "2026-09-12", "maria.alvarez.c@example.com"),
        ("D", "Maria Alvarez", "+1 (281) 555-0144", "2025-07-01", "maria.alvarez.d@example.com"),
        ("E", "Maria Alvarez", "+1 (281) 555-0145", "2025-07-01", "maria.alvarez.e@example.com"),
        ("F", "Maria Alvarez", "+1 (281) 555-0146", "2025-07-01", "maria.alvarez.f@example.com"),
    ]
    made = {}
    for letter, name, phone, opened, email in worlds:
        suffix = "" if letter == "A" else letter
        unit_id = _unit(tenant, actor, premises_id, f"Unit {letter}", UNIT_POINTS)
        mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
        unit_row = mm.Unit.objects.get(tenant=tenant, pk=unit_id)
        if unit_row.rate_plan_id is None:
            msvc.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
        w1 = _meter(tenant, actor, f"W-10442{suffix}", "water", "kgal", unit_id)
        w2 = _meter(tenant, actor, f"W-10443{suffix}", "water", "kgal", unit_id)
        el = _meter(tenant, actor, f"E-55120{suffix}", "electric", "kWh", unit_id)
        _cart(tenant, actor, f"CART-J70{letter}1", unit_id)
        # Broadband is CONNECTED (a router on the unit, the drawing's R-2201)
        # and NOT TAKEN by the account — J70 E1.4's "Not taken" row. Without
        # the router it is "Not in service", which is a different fact.
        _router(tenant, actor, f"R-2201{suffix}", unit_id)
        made[letter] = dict(unit_id=unit_id, w1=w1, w2=w2, el=el, name=name, phone=phone, opened=opened, email=email)

    # History reads per world.
    a = made["A"]
    for w in ("A", "D"):
        m = made[w]
        _read(tenant, actor, m["w1"], "2026-07-31", "476.2", "470.0", "kgal")
        _read(tenant, actor, m["w1"], "2026-08-31", "482.3", "476.2", "kgal")
        _read(tenant, actor, m["w2"], "2026-07-31", "125.0", "120.0", "kgal")
        _read(tenant, actor, m["w2"], "2026-08-31", "130.6", "125.0", "kgal")
        _read(tenant, actor, m["el"], "2026-07-31", "17820", "17200", "kWh")
        _read(tenant, actor, m["el"], "2026-08-31", "18420", "17820", "kWh")
    c = made["C"]  # first bill: move-in reads on W-10442C and E-55120C only
    _read(tenant, actor, c["w1"], "2026-09-12", "479.8", None, "kgal")
    _read(tenant, actor, c["el"], "2026-09-12", "18500", None, "kWh")
    e = made["E"]  # catch-up: Jun–Aug; W-10443E has no July read
    for asset, series in (
        (e["w1"], (("2026-05-31", "440.0"), ("2026-06-30", "452.1"), ("2026-07-31", "466.0"))),
        (e["w2"], (("2026-05-31", "100.0"), ("2026-06-30", "110.4"))),
        (e["el"], (("2026-05-31", "16000"), ("2026-06-30", "16700"), ("2026-07-31", "17400"))),
    ):
        prior = None
        for day, value in series:
            _read(tenant, actor, asset, day, value, prior, "kgal" if asset != e["el"] else "kWh")
            prior = value
    # penalty: Jun–Sep read. E5 bills Jul–Sep so the bill is dated in SEPTEMBER:
    # `seed_demo` closes August (the integrations sample's export batch needs a
    # closed month), and a bill dated Aug 31 is refused by the books (BR-LED-006).
    # That was the test data, not the product (J70 E5, 2026-09-30).
    f = made["F"]
    for asset, series in (
        (f["w1"], (("2026-05-31", "440.0"), ("2026-06-30", "452.1"), ("2026-07-31", "466.0"), ("2026-08-31", "482.3"), ("2026-09-30", "496.5"))),
        (f["w2"], (("2026-05-31", "100.0"), ("2026-06-30", "110.4"), ("2026-07-31", "121.0"), ("2026-08-31", "130.6"), ("2026-09-30", "139.9"))),
        (f["el"], (("2026-05-31", "16000"), ("2026-06-30", "16700"), ("2026-07-31", "17400"), ("2026-08-31", "18420"), ("2026-09-30", "19310"))),
    ):
        prior = None
        for day, value in series:
            _read(tenant, actor, asset, day, value, prior, "kgal" if asset != f["el"] else "kWh")
            prior = value

    # Accounts (before the deposit rule, so the S18 door is not asked a deposit).
    accounts = {}
    for letter, m in made.items():
        acct = _account(tenant, actor, m["unit_id"], m["name"], m["phone"], m["opened"], m["email"])
        accounts[letter] = acct
        # Broadband is offered at the unit and NOT taken (BR-CUS-1101).
        cm.ServiceAgreement.objects.filter(
            tenant=tenant, account=acct, service_point__service__code="broadband"
        ).delete()

    # E9 — Dana Brooks, Unit B: water + electric + trash, NO service agreements.
    unit_b = _unit(tenant, actor, premises_id, "Unit B", ["water", "electric", "trash"])
    mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_b).update(cycle=cycle)
    if mm.Unit.objects.get(tenant=tenant, pk=unit_b).rate_plan_id is None:
        msvc.assign_unit_plan(actor, unit_b, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
    wb = _meter(tenant, actor, "W-10450", "water", "kgal", unit_b)
    eb = _meter(tenant, actor, "E-55121", "electric", "kWh", unit_b)
    _cart(tenant, actor, "CART-J70B1", unit_b)
    _read(tenant, actor, wb, "2026-07-31", "204.0", "198.0", "kgal")
    _read(tenant, actor, wb, "2026-08-31", "210.0", "204.0", "kgal")
    _read(tenant, actor, eb, "2026-07-31", "9300", "8800", "kWh")
    _read(tenant, actor, eb, "2026-08-31", "9800", "9300", "kWh")
    brooks = _account(tenant, actor, unit_b, "Dana Brooks", "+1 (281) 555-0190", "2025-07-01",
                      "dana.brooks@example.com")
    cm.ServiceAgreement.objects.filter(tenant=tenant, account=brooks).delete()
    accounts["B"] = brooks

    # ── 2026-09-30 defect-fix lane: the PO's reports on 2.411.4 ──────────────
    # Unit G — Omar Grant, a first bill for an account with NO move-in date on
    # record (DEF-BIL-8281: Plan and Cycle must still show; only the move-in
    # field asks). Unit H — John Robert, meters read only to Jun 30: a catch-up
    # over Jul–Sep and a penalty with the PO's overlapping periods.
    for letter, name, phone, email in (
        ("G", "Omar Grant", "+1 (281) 555-0171", "omar.grant@example.com"),
        ("H", "John Robert", "+1 (281) 555-0172", "john.robert@example.com"),
    ):
        unit_id = _unit(tenant, actor, premises_id, f"Unit {letter}", UNIT_POINTS)
        mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
        if mm.Unit.objects.get(tenant=tenant, pk=unit_id).rate_plan_id is None:
            msvc.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
        w1 = _meter(tenant, actor, f"W-10442{letter}", "water", "kgal", unit_id)
        w2 = _meter(tenant, actor, f"W-10443{letter}", "water", "kgal", unit_id)
        el = _meter(tenant, actor, f"E-55120{letter}", "electric", "kWh", unit_id)
        _cart(tenant, actor, f"CART-J70{letter}1", unit_id)
        _read(tenant, actor, w1, "2026-06-30", "452.1", "440.0", "kgal")
        _read(tenant, actor, w2, "2026-06-30", "110.4", "100.0", "kgal")
        _read(tenant, actor, el, "2026-06-30", "16700", "16000", "kWh")
        acct = _account(tenant, actor, unit_id, name, phone, "2025-07-01", email)
        if letter == "G":
            cm.Account.objects.filter(tenant=tenant, pk=acct.pk).update(opened_at=None)
        accounts[letter] = acct

    # ── J74 (2026-09-30): the two cases J70's units cannot carry ──────────────
    # (Before the deposit rule below, like every account here: after it, the
    # account-opening door asks for the plan's deposit and refuses.)
    # Unit I — Hannah Ortiz: ONE service (water, one meter), read to Aug 31 and
    #   not since: J74 case 2, an interim with no reading in the period.
    # Unit J — Samuel Okafor: the J70 unit, final, holding a $50.00 deposit —
    #   LESS than the bill, so a balance is still due (J74 case 4). Unit D keeps
    #   the $150.00 deposit that is MORE than the bill (case 5).
    unit_i = _unit(tenant, actor, premises_id, "Unit I", ["water"])
    mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_i).update(cycle=cycle)
    if mm.Unit.objects.get(tenant=tenant, pk=unit_i).rate_plan_id is None:
        msvc.assign_unit_plan(actor, unit_i, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
    wi = _meter(tenant, actor, "W-10460", "water", "kgal", unit_i)
    # The FIRST read carries no prior: a consumption with no day count would read
    # to Meter Reads as 6.0 kgal over 0 days and skew its own estimate (J74 case 2).
    _read(tenant, actor, wi, "2026-06-30", "300.0", None, "kgal")
    _read(tenant, actor, wi, "2026-07-31", "306.2", "300.0", "kgal")
    _read(tenant, actor, wi, "2026-08-31", "312.4", "306.2", "kgal")
    accounts["I"] = _account(tenant, actor, unit_i, "Hannah Ortiz", "+1 (281) 555-0174", "2025-07-01",
                             "hannah.ortiz@example.com")

    unit_j = _unit(tenant, actor, premises_id, "Unit J", UNIT_POINTS)
    mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_j).update(cycle=cycle)
    if mm.Unit.objects.get(tenant=tenant, pk=unit_j).rate_plan_id is None:
        msvc.assign_unit_plan(actor, unit_j, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
    j1 = _meter(tenant, actor, "W-10442J", "water", "kgal", unit_j)
    j2 = _meter(tenant, actor, "W-10443J", "water", "kgal", unit_j)
    je = _meter(tenant, actor, "E-55120J", "electric", "kWh", unit_j)
    _cart(tenant, actor, "CART-J70J1", unit_j)
    _router(tenant, actor, "R-2201J", unit_j)
    _read(tenant, actor, j1, "2026-07-31", "476.2", "470.0", "kgal")
    _read(tenant, actor, j1, "2026-08-31", "482.3", "476.2", "kgal")
    _read(tenant, actor, j2, "2026-07-31", "125.0", "120.0", "kgal")
    _read(tenant, actor, j2, "2026-08-31", "130.6", "125.0", "kgal")
    _read(tenant, actor, je, "2026-07-31", "17820", "17200", "kWh")
    _read(tenant, actor, je, "2026-08-31", "18420", "17820", "kWh")
    okafor = _account(tenant, actor, unit_j, "Samuel Okafor", "+1 (281) 555-0175", "2025-07-01",
                      "samuel.okafor@example.com")
    cm.ServiceAgreement.objects.filter(
        tenant=tenant, account=okafor, service_point__service__code="broadband"
    ).delete()
    if Decimal(okafor.deposit_on_file) != J74_SMALL_DEPOSIT:
        okafor.deposit_on_file = J74_SMALL_DEPOSIT
        okafor.deposit_received_on = date(2025, 7, 1)
        okafor.save(update_fields=["deposit_on_file", "deposit_received_on", "updated_at"])
    accounts["J"] = okafor

    # ── 2026-09-30 · the PO's own reports, walked in a browser (J70 §"PO reports walk") ──
    # Unit K — Nina Castillo, on a water-only plan whose ONLY water rate ends Jul 31:
    # an interim bill for Aug 1–31 has no Water rate on its last day (DEF-BIL-8287,
    # "No Water rate on Aug 31, 2026. Add one in Plans & Rates.").
    # Unit L — John Mauli, on NO billing cycle (DEF-BIL-8330, PO ruling option A):
    # a first bill is stopped at step 1 with "No billing cycle. Assign one on the account."
    from tests.test_us_met_helpers import make_plan, state_size_axis
    from apps.rating import selectors as rsel

    lapsed = make_plan(tenant, name="Water Only (rate ends Jul 31)", code="WTR-LAPSED-J70", services=("water",))
    lapsed_water = {r["service_code"]: r["tariff"] for r in rsel.plan_rate_schedules(lapsed.id)}["water"]
    lapsed_version = _version(tenant, lapsed_water, model="tiered", uom="kgal", effective_from=date(2026, 1, 1),
                              effective_to=date(2026, 7, 31), tiers=WATER_TIERS_V1,
                              base_charge_code=_base_code(tenant, "water", *BASES["water"]))
    state_size_axis(lapsed_version, "water")
    unit_k = _unit(tenant, actor, premises_id, "Unit K", ["water"])
    mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_k).update(cycle=cycle)
    if mm.Unit.objects.get(tenant=tenant, pk=unit_k).rate_plan_id is None:
        msvc.assign_unit_plan(actor, unit_k, {"tariff_id": str(lapsed.id), "effective_from": "2026-01-01"})
    wk = _meter(tenant, actor, "W-10470", "water", "kgal", unit_k)
    _read(tenant, actor, wk, "2026-07-31", "304.0", "298.0", "kgal")
    _read(tenant, actor, wk, "2026-08-31", "311.0", "304.0", "kgal")
    accounts["K"] = _account(tenant, actor, unit_k, "Nina Castillo", "+1 (281) 555-0176", "2025-07-01",
                             "nina.castillo@example.com")

    unit_l = _unit(tenant, actor, premises_id, "Unit L", ["water"])
    # NO cycle: the service point is left off every cycle on purpose.
    if mm.Unit.objects.get(tenant=tenant, pk=unit_l).rate_plan_id is None:
        msvc.assign_unit_plan(actor, unit_l, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
    wl = _meter(tenant, actor, "W-10471", "water", "kgal", unit_l)
    _read(tenant, actor, wl, "2026-06-30", "120.0", "110.0", "kgal")
    accounts["L"] = _account(tenant, actor, unit_l, "John Mauli", "+1 (281) 555-0177", "2026-07-01",
                             "john.mauli@example.com")

    # Deposits: the plan asks $150.00 of a residential account; E3's account holds it.
    rm.PlanDepositRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, account_type_id=_account_type(ACCOUNT_TYPE).id,
        defaults={"amount": DEPOSIT, "currency": "USD"},
    )
    d = accounts["D"]
    if Decimal(d.deposit_on_file) != DEPOSIT:
        d.deposit_on_file = DEPOSIT
        d.deposit_received_on = date(2025, 7, 1)
        d.save(update_fields=["deposit_on_file", "deposit_received_on", "updated_at"])

    for letter in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"):
        acct = accounts[letter]
        agreements = sorted(
            cm.ServiceAgreement.objects.filter(tenant=tenant, account=acct)
            .values_list("service_point__service__code", flat=True)
        )
        notes.append(f"Unit {letter} ................... {acct.account_no} · agreements {agreements or 'NONE'}")
    # DEF-BIL-8334 — the walk month must be open for Send; reopened only if the demo closed it.
    reopened = keep_walk_month_open(tenant, actor)
    notes.append(reopened or f"walk month open ........... {WALK_MONTH[0]} … {WALK_MONTH[1]}")
    return notes


def main() -> int:
    sjf.django_setup()
    from core import tenancy as core_tenancy

    tenant, actor = sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        from django.db import transaction

        with transaction.atomic():
            notes = seed(tenant, actor)
    print("J70 one-time bill world seeded:")
    for line in notes:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
