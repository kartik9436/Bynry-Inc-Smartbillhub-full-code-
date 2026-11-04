# ── Trace ──────────────────────────────────────────────
# Journey:  J72 — the bulk bill run, redesigned (E1–E11) ·
#           08-qa/01-e2e/journeys/J72-bulk-bill-run-redesign.md
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md §E
# Spec:     07-frontend/e2e/J72-bulk-bill-run.spec.ts (the walk that reads this world)
# Pattern:  10-scripts/seed_j70_one_time_bill.py (the one-time lane's seed)
# ───────────────────────────────────────────────────────
"""seed_j72_bulk_run — a cycle whose accounts hit every Check tag J72 walks.

Run AFTER `manage.py migrate` and `manage.py seed_demo` (Brazos Bend, owner
Dana Whitfield), on PostgreSQL, with the settings the stack runs under:

    cd 06-backend && DATABASE_URL=postgres://…/sbh_j72 \\
        DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        python manage.py seed_j72_bulk_run

IDEMPOTENT: every row is looked up by its natural key (asset number, unit label,
account's unit, run key) before it is written, so a second run adds nothing and
prints the same roster. TENANT-SCOPED: everything runs inside
`core.tenancy.tenant_context(brazos)`; there is no cross-tenant query.

THE WORLD — cycle `J72-RIVERSIDE` ("Riverside"), monthly, bill day 1, 21 days
to pay, 12 units at 2200 Riverside Dr, 11 accounts, one vacant unit:

    unit  account  who               what Check finds on Sep 1 – Sep 30, bill Oct 1
    101   …        Maria Alvarez     clean (water 482.0 → 492.0 kgal)
    102   …        Omar Haddad       clean
    103   …        Priya Natarajan   NO READING (no Sep read)            → noReading
    104   …        Luis Alvarez      NO PLAN on the unit                 → noPlan
    105   …        Grace Okafor      NO PLAN + a DISPUTED Sep reading    → noPlan · disputedReading
    106   …        Tom Becker        last bill July; HELD in August      → no tag; bills Aug 1 – Sep 30
    107   …        Hannah Lee        $120.00 posted Oct 1 (after cut-off) → paidAfterCutoff
    108   …        Diego Ramos       electric with NO base charge code   → base $0.00 warning
    109   …        Sara Cohen        last bill Jul 1 – Jul 31, not held  → gapOrOverlap (gap)
    110   …        Wendy Park        already billed Sep 1 – Sep 30       → gapOrOverlap (overlap)
    111   …        Ivan Petrov       vacation hold                        → standingChargesOnly (Waive)
    112   —        nobody            vacant, nobody to bill               → Scope warning

PREVIOUS RUN: a REAL cycle run for Aug 1 – Aug 31 is created, prepared,
calculated and issued through `runs` / `decisions` / `issue`, so the September
run is *continuous* with it and its saved bills prove Scope's "last run" counts.
The August run holds unit 106 (its missing read is answered `hold`), which is
what makes 106 a HELD account (fixed-charge case 3: its last bill is a
one-time interim for July, so September prepares it for Aug 1 – Sep 30 with
one base — measured on PostgreSQL 16). Units 104, 105, 109 and 110
join the cycle only AFTER the August run, so they are not in it: 109's last bill
is a one-time interim for July and 110's a one-time interim for September, each
created and sent through `one_time` / `one_time_send` — the product's own path.

HOW IT WRITES: premises, units, meters, reads, plan assignment, accounts and
their activation, the dispute and the payment go through the owning modules'
services (`metering.services`, `assets.services` via the test helpers the J70
seed also uses, `customers.services`, `payments.services`). Rate VERSIONS,
tiers, the base charge code and the cycle are written with the ORM under
`app.tenant_id`, the shape every billing test builds them in (there is no
service that writes a version's tiers in one call). The August issue passes
`require_release=False`: the seed stands in for a run a clerk already sent,
and the release confirmations are what E1.6 walks, not what this seeds.

⚠ **WHAT IT DOES NOT SEED, AND WHY** (each is recorded in J72's results):
  * no MASTER account — the J72 table's `AC-2026-00110` master; the Check tags
    this lane was asked for do not need one and `DEF-BIL-8285` shows the master
    fixture is not yet a safe thing to copy;
  * no unitless electric reading (J72's Tom Becker) — metering refuses a read
    with no unit on the way in, so it can only be produced by a test double;
  * no CANCELLED September run (J72's BR-0229) — a run's idempotency key is
    cycle + period and the scope check refuses a duplicate key whatever its
    status, so a cancelled Sep 1 – Sep 30 run would make E1 an "already run"
    refusal rather than the continuous run the journey describes.

Figures are J72's fixture VALUES, not signed law; no ❄️ B4/B5 figure is touched.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

REPO = Path(__file__).resolve().parents[5]

PLAN_NAME = "Residential Standard (Riverside J72)"
PLAN_CODE = "RES-STD-J72"
PLAN_E_NAME = "Residential Water + Electric (Riverside J72)"
PLAN_E_CODE = "RES-WE-J72"
SERVICES = ("water", "electric")
CYCLE_CODE = "J72-RIVERSIDE"
CYCLE_NAME = "Riverside"
ADDRESS = "2200 Riverside Dr"
ACCOUNT_TYPE = "institutional"  # the J70 compromise, for J70's reason (see below)
DUE_DAYS = 21
WATER_V1 = (("0", None, "3.2500"),)  # to Sep 30, 2026
WATER_V2 = (("0", None, "3.5000"),)  # from Oct 1, 2026 — must NOT reach a Sep bill
ELECTRIC_RATE = "0.1245"
WATER_BASE = Decimal("8.0000")
AUGUST = (date(2026, 8, 1), date(2026, 8, 31))
AUG_BILL_DATE = date(2026, 9, 1)
PAID_AFTER_CUTOFF = Decimal("120.0000")

#: label, name, phone, email, services on the unit, has plan, joins the cycle
#: before the August run, reads (water) as ((day, value, prior), …)
ROSTER: tuple[dict[str, Any], ...] = (
    {
        "unit": "101",
        "name": "Maria Alvarez",
        "tag": "clean",
        "reads": (
            ("2026-07-31", "472.0", "462.0"),
            ("2026-08-31", "482.0", "472.0"),
            ("2026-09-30", "492.0", "482.0"),
        ),
    },
    {
        "unit": "102",
        "name": "Omar Haddad",
        "tag": "clean",
        "reads": (
            ("2026-07-31", "300.0", "290.0"),
            ("2026-08-31", "308.0", "300.0"),
            ("2026-09-30", "316.5", "308.0"),
        ),
    },
    {
        "unit": "103",
        "name": "Priya Natarajan",
        "tag": "noReading",
        "reads": (("2026-07-31", "150.0", "140.0"), ("2026-08-31", "158.0", "150.0")),
    },
    {
        "unit": "104",
        "name": "Luis Alvarez",
        "tag": "noPlan",
        "plan": False,
        "late": True,
        "reads": (("2026-08-31", "210.0", None), ("2026-09-30", "219.0", "210.0")),
    },
    {
        "unit": "105",
        "name": "Grace Okafor",
        "tag": "noPlan+disputedReading",
        "plan": False,
        "late": True,
        "dispute": True,
        "reads": (("2026-08-31", "400.0", None), ("2026-09-30", "412.0", "400.0")),
    },
    {
        "unit": "106",
        "name": "Tom Becker",
        "tag": "held (August)",
        "hold_in_august": True,
        # A July bill (one-time interim) so the August hold sits inside a gap
        # after a real last bill — fixed-charge case 3 needs both to apply.
        "interim": ("2026-07-01", "2026-07-31"),
        "reads": (
            ("2026-06-30", "490.0", "480.0"),
            ("2026-07-31", "500.0", "490.0"),
            ("2026-09-30", "521.0", "500.0"),
        ),
    },
    {
        "unit": "107",
        "name": "Hannah Lee",
        "tag": "paidAfterCutoff",
        "paid_after_cutoff": True,
        "reads": (
            ("2026-07-31", "610.0", "600.0"),
            ("2026-08-31", "618.0", "610.0"),
            ("2026-09-30", "627.0", "618.0"),
        ),
    },
    {
        "unit": "108",
        "name": "Diego Ramos",
        "tag": "baseZero (electric)",
        "electric": True,
        "reads": (
            ("2026-07-31", "700.0", "690.0"),
            ("2026-08-31", "709.0", "700.0"),
            ("2026-09-30", "718.0", "709.0"),
        ),
        "e_reads": (
            ("2026-07-31", "10200", "9600"),
            ("2026-08-31", "10800", "10200"),
            ("2026-09-30", "11400", "10800"),
        ),
    },
    {
        "unit": "109",
        "name": "Sara Cohen",
        "tag": "gapOrOverlap (gap)",
        "late": True,
        "interim": ("2026-07-01", "2026-07-31"),
        "reads": (
            ("2026-06-30", "800.0", "790.0"),
            ("2026-07-31", "808.0", "800.0"),
            ("2026-08-31", "816.0", "808.0"),
            ("2026-09-30", "825.0", "816.0"),
        ),
    },
    {
        "unit": "110",
        "name": "Wendy Park",
        "tag": "gapOrOverlap (overlap)",
        "late": True,
        "interim": ("2026-09-01", "2026-09-30"),
        "reads": (("2026-08-31", "900.0", "890.0"), ("2026-09-30", "909.0", "900.0")),
    },
    {
        "unit": "111",
        "name": "Ivan Petrov",
        "tag": "standingChargesOnly (Waive)",
        "status": "vacation_hold",
        "reads": (
            ("2026-07-31", "1000.0", "1000.0"),
            ("2026-08-31", "1000.0", "1000.0"),
            ("2026-09-30", "1000.0", "1000.0"),
        ),
    },
    {"unit": "112", "name": None, "tag": "nobody to bill (vacant)", "reads": ()},
)


def _sjf():
    spec = importlib.util.spec_from_file_location(
        "seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _version(tenant, tariff, *, model, uom, effective_from, effective_to=None, tiers=(), **extra):
    from apps.rating import models as rm

    found = rm.TariffVersion.objects.filter(
        tenant=tenant, tariff=tariff, effective_from=effective_from
    ).first()
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


def _water_base(tenant):
    """ONE water base code for the institutional class.

    ⚠ The J70 seed mints `BASE-W-J70` ($8.00, institutional) for the same reason
    this one needs a code — `seed_demo`'s `BASE-W` is scoped to residential — so
    on a database where J70 already ran, that code IS the answer and a second one
    would make every water bill refuse as *"2 base charge codes for water"*.
    """
    from apps.rating import models as rm
    from apps.tenancy import models as tm

    water = tm.Service.objects.get(code="water")
    for charge in rm.Charge.objects.filter(tenant=tenant, service=water, is_base=True):
        if ACCOUNT_TYPE in (charge.applies_to_customer_classes or []):
            return charge
    return rm.Charge.objects.create(
        tenant=tenant,
        code="BASE-W-J72",
        name="Water base (Riverside J72)",
        charge_type="recurring",
        service=water,
        amount_rule="flat",
        amount=WATER_BASE,
        is_base=True,
        kind="base",
        applies_to_customer_classes=[ACCOUNT_TYPE],
    )


def _water_versions(tenant, tariff, base):
    w1 = _version(
        tenant,
        tariff,
        model="tiered",
        uom="kgal",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 9, 30),
        tiers=WATER_V1,
        base_charge_code=base,
    )
    w2 = _version(
        tenant,
        tariff,
        model="tiered",
        uom="kgal",
        effective_from=date(2026, 10, 1),
        tiers=WATER_V2,
        base_charge_code=base,
    )
    for version in (w1, w2):
        state_size_axis_for(version, "water")


def state_size_axis_for(version, service_code):
    from tests.test_us_met_helpers import state_size_axis

    state_size_axis(version, service_code)


def ensure_plans(tenant):
    """TWO plans, so no unit holds a plan service it has no point for.

    One plan with water AND electric on a water-only unit puts a *service not
    connected* row on every account's review list — true, and noise for a walk
    whose subject is the Check tags. So the water units hold a water-only plan
    and unit 108 (Diego Ramos) a water + electric one.
    """
    from apps.rating import selectors as rsel
    from tests.test_us_met_helpers import make_plan

    base = _water_base(tenant)
    water_plan = make_plan(tenant, name=PLAN_NAME, code=PLAN_CODE, services=("water",))
    tariffs = {
        row["service_code"]: row["tariff"] for row in rsel.plan_rate_schedules(water_plan.id)
    }
    _water_versions(tenant, tariffs["water"], base)

    both = make_plan(tenant, name=PLAN_E_NAME, code=PLAN_E_CODE, services=SERVICES)
    tariffs = {row["service_code"]: row["tariff"] for row in rsel.plan_rate_schedules(both.id)}
    _water_versions(tenant, tariffs["water"], base)
    # Electric: NO base charge code for this class — Diego Ramos's $0.00 warning.
    e = _version(
        tenant,
        tariffs["electric"],
        model="flat",
        uom="kWh",
        effective_from=date(2026, 1, 1),
        tiers=(("0", None, ELECTRIC_RATE),),
    )
    state_size_axis_for(e, "electric")
    return water_plan, both


def ensure_cycle(tenant):
    from apps.metering import models as mm

    cycle, _ = mm.Cycle.objects.get_or_create(
        tenant=tenant,
        code=CYCLE_CODE,
        defaults={
            "name": CYCLE_NAME,
            "frequency": "Monthly",
            "start_day": 1,
            "days_to_complete": 30,
            "bill_day": 1,
            "due_days": DUE_DAYS,
            "first_run_date": date(2026, 8, 1),
        },
    )
    return cycle


def _plan_dropped(tenant, unit_id) -> bool:
    """A no-plan unit this seed already cleared on an earlier pass — never re-plan it."""
    from apps.rating import models as rm

    return rm.UnitPlanAssignment.objects.filter(tenant=tenant, unit_id=unit_id).exists()


def _meter(tenant, actor, asset_no, service, uom, unit_id):
    from apps.assets import models as am
    from tests.test_us_met_reads_helpers import a_meter

    row = am.Asset.objects.filter(tenant=tenant, asset_no=asset_no).first()
    if row is not None:
        return str(row.id)
    return a_meter(actor, asset_no=asset_no, service=service, uom=uom, unit_id=unit_id)["id"]


def _read(tenant, actor, asset_id, day, value, prior, unit):
    from apps.metering.models import MeterRead
    from tests.test_us_met_reads_helpers import at, commit_read

    existing = MeterRead.objects.filter(
        tenant=tenant, asset_id=asset_id, read_at=at(day), channel="total"
    ).first()
    if existing is not None:
        return existing
    consumption = None if prior is None else Decimal(value) - Decimal(prior)
    commit_read(
        actor,
        asset_id,
        day=day,
        value=str(value),
        prior_value=None if prior is None else str(prior),
        consumption=None if consumption is None else str(consumption),
        unit=unit,
    )
    return MeterRead.objects.filter(
        tenant=tenant, asset_id=asset_id, read_at=at(day), channel="total"
    ).first()


def _account(tenant, actor, unit_id, unit_label, name, status):
    from apps.customers import models as cm
    from apps.customers import services as csvc

    existing = cm.Account.objects.filter(tenant=tenant, unit_id=unit_id).first()
    if existing is not None:
        return existing
    slug = name.lower().replace(" ", ".")
    phone = f"+1 (281) 555-07{unit_label[-2:]}"
    created = csvc.create_account(
        actor,
        {
            "unit_id": str(unit_id),
            "account_type": ACCOUNT_TYPE,
            "opened_at": "2025-07-01",
            "contact": {"full_name": name, "phone": phone, "email": f"{slug}.j72@example.com"},
            "customer": {"display_name": name, "kind": "person", "identity": {"phone": phone}},
            "addresses": [{"kind": "mailing", "line1": ADDRESS, "city": "Katy", "state": "TX"}],
        },
    )
    csvc.activate_account(actor, created["id"], {"status": status} if status else None)
    return cm.Account.objects.get(pk=created["id"])


def _template():
    from apps.billing import template_models as tpl
    from core import tenancy as core_tenancy

    row = (
        tpl.BillTemplateVersion.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            status=tpl.VERSION_PUBLISHED,
            template__template_type=tpl.TYPE_BILL,
        )
        .order_by("template__name", "-version_no")
        .first()
    )
    if row is None:
        raise CommandError(
            "no published bill template on the tenant — seed_demo publishes one; re-run it."
        )
    return row.template_id, int(row.version_no)


def _august_run(tenant, actor, cycle, accounts):
    """BR-…: Aug 1 – Aug 31, sent. Unit 106's missing read is answered HOLD."""
    from apps.billing import decisions, issue, runs
    from apps.billing import models as bm
    from apps.tenancy import selectors as tsel

    key_run = bm.BillRun.objects.filter(
        tenant=tenant,
        cycle=cycle,
        period_start=AUGUST[0],
        period_end=AUGUST[1],
        parent_run__isnull=True,
    ).first()
    if (
        key_run is not None
        and bm.Invoice.objects.filter(bill_run=key_run).exclude(status="draft").exists()
    ):
        # DEF-BIL-8690 — idempotent and never regresses, so a world seeded
        # before the fix is corrected by seeding it again.
        runs.record_run_outcome(key_run, actor=getattr(actor, "user", None))
        return key_run
    template_id, template_version = _template()
    run = key_run or runs.create_run(
        cycle_id=cycle.id,
        period_start=AUGUST[0],
        period_end=AUGUST[1],
        bill_date=AUG_BILL_DATE,
        due_days=DUE_DAYS,
        label="August 2026 · Riverside",
        template_id=template_id,
        run_by=getattr(actor, "user", None),
    )
    prepared = runs.prepare_run(
        cycle_id=cycle.id, period_start=AUGUST[0], period_end=AUGUST[1], service_date=AUG_BILL_DATE
    )
    water = tsel.service_ids_by_code()["water"]
    for row in prepared.decisions:
        account_id = str(row.account_id)
        if account_id == str(accounts["106"].id) and row.reason == "missing_read":
            decisions.record_decision(
                bill_run=run,
                account_id=account_id,
                case="missing_read",
                choice="hold",
                service_id=water,
                reason="Meter access — field visit",
            )
        elif row.reason == "base_only_billing":
            decisions.record_decision(
                bill_run=run, account_id=account_id, case="base_only_billing", choice="include"
            )
    runs.calculate_run(decisions.apply_decisions(prepared, bill_run=run), bill_run=run)
    issue.issue_run(
        run,
        issued_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        template_id=template_id,
        template_version=template_version,
        require_release=False,
        actor=getattr(actor, "user", None),
    )
    # DEF-BIL-8690 — `issue_run` alone leaves the run's STATUS at `draft`
    # (BR-BIL-1045 gives the column one writer, which `release.release_run`
    # calls; this seed stands in for a release and so must call it too), and
    # Scope's Previous runs then listed a sent run as *Draft*.
    runs.record_run_outcome(run, actor=getattr(actor, "user", None))
    run.refresh_from_db()
    return run


def _interim(tenant, actor, account, window):
    """A one-time INTERIM bill for `window`, created and sent the product's way."""
    from apps.billing import models as bm
    from apps.billing import one_time, one_time_send, release

    start, end = (date.fromisoformat(d) for d in window)
    done = (
        bm.Invoice.objects.filter(
            tenant=tenant, account=account, period_start=start, period_end=end
        )
        .exclude(status="draft")
        .first()
    )
    if done is not None:
        return done
    body = one_time.create(
        one_time.OneTimeRequest(
            account_id=str(account.id),
            kind=one_time.KIND_INTERIM,
            period_start=start,
            period_end=end,
            bill_date=end,
            due_days=DUE_DAYS,
        ),
        run_by=getattr(actor, "user", None),
        actor=getattr(actor, "user", None),
    )
    invoice = bm.Invoice.objects.get(pk=body["invoice_id"])

    template_id, template_version = _template()
    one_time_send.send(
        invoice.bill_run,
        delivery="email",
        sent_at=datetime.combine(end, datetime.min.time(), tzinfo=UTC),
        template_id=template_id,
        template_version=template_version,
        template_pin_explicit=False,
        approved_by=None,
        # The five Send confirmations became required on 2026-09-30 (PO option
        # B, `7d75bd7d2`; DEF-BIL-8550); the seed stands in for a clerk who ticked all five.
        confirmations=release.Confirmations(
            compliance=True, email_mandate=True, sms_mandate=True, autopay_mandate=True, final=True
        ),
        confirmed_by=getattr(actor, "id", None),
        actor=getattr(actor, "user", None),
    )
    return bm.Invoice.objects.get(pk=invoice.pk)


def seed(tenant, actor, out, *, month_two: bool = False) -> list[str]:
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.payments import models as pm
    from apps.payments import services as psvc
    from tests.journey_cohort_fixtures import _premises_for, _unit_on, ensure_services_enabled

    notes: list[str] = []
    ensure_services_enabled(tenant, actor, *SERVICES)
    water_plan, both_plan = ensure_plans(tenant)
    cycle = ensure_cycle(tenant)
    premises_id = _premises_for(tenant, actor, ADDRESS, list(SERVICES))

    units: dict[str, str] = {}
    meters: dict[str, dict[str, str]] = {}
    for row in ROSTER:
        label = f"Unit {row['unit']}"
        points = ["water", "electric"] if row.get("electric") else ["water"]
        unit_id = _unit_on(tenant, actor, premises_id, label, points)
        units[row["unit"]] = unit_id
        # Every unit gets the plan first: activation refuses an account on a
        # plan-less unit (BR-MET-040 via `customers.plan_required_at_activation`).
        # 104 and 105 LOSE it below, after activation — see the no-plan note.
        if mm.Unit.objects.get(
            tenant=tenant, pk=unit_id
        ).rate_plan_id is None and not _plan_dropped(tenant, unit_id):
            plan = both_plan if row.get("electric") else water_plan
            msvc.assign_unit_plan(
                actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
            )
        m = {"water": _meter(tenant, actor, f"W-72{row['unit']}", "water", "kgal", unit_id)}
        if row.get("electric"):
            m["electric"] = _meter(tenant, actor, f"E-72{row['unit']}", "electric", "kWh", unit_id)
        meters[row["unit"]] = m
        if not row.get("late"):
            mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)

    # Reads up to Aug 31 first; September's reads land after the August run.
    def reads(until: str) -> None:
        for row in ROSTER:
            m = meters[row["unit"]]
            for day, value, prior in row["reads"]:
                if day <= until:
                    _read(tenant, actor, m["water"], day, value, prior, "kgal")
            for day, value, prior in row.get("e_reads", ()):
                if day <= until:
                    _read(tenant, actor, m["electric"], day, value, prior, "kWh")

    reads("2026-08-31")

    accounts: dict[str, Any] = {}
    for row in ROSTER:
        if row["name"] is None:
            continue
        accounts[row["unit"]] = _account(
            tenant, actor, units[row["unit"]], row["unit"], row["name"], row.get("status")
        )

    # 109 and 110 get their one-time bills before they join the cycle.
    for row in ROSTER:
        if row.get("interim") and row["interim"][1] <= "2026-08-31":
            _interim(tenant, actor, accounts[row["unit"]], row["interim"])

    august = _august_run(tenant, actor, cycle, accounts)
    notes.append(f"August run ............. {august.run_no or august.pk} · {august.status}")

    reads("2026-09-30")
    for row in ROSTER:
        if row.get("interim") and row["interim"][1] > "2026-08-31":
            _interim(tenant, actor, accounts[row["unit"]], row["interim"])
    for row in ROSTER:
        if row.get("late"):
            mm.ServicePoint.objects.filter(tenant=tenant, unit_id=units[row["unit"]]).update(
                cycle=cycle
            )

    # 104, 105 — NO PLAN. ⚠ THE ONE ORM WRITE TO A UNIT IN THIS FILE, AND WHY:
    # no service removes a unit's plan (BR-MET-040 makes one REQUIRED, and
    # activation refuses without one), so the only way a live account meets
    # `unit_has_no_plan` is data that predates the rule — an import, a legacy
    # row. The Check engine's own tests build it the same way (an ORM account
    # on a plan-less unit). This clears the unit's current-plan pointer and
    # nothing else, so the assignment history still says it once had one.
    for row in ROSTER:
        if not row.get("plan", True):
            mm.Unit.objects.filter(tenant=tenant, pk=units[row["unit"]]).update(rate_plan_id=None)

    # 105 — the September reading is disputed (BR-MET-024), through Meter Reads.
    grace = next(r for r in ROSTER if r.get("dispute"))
    sep = _read(
        tenant, actor, meters[grace["unit"]]["water"], "2026-09-30", "412.0", "400.0", "kgal"
    )
    if sep is not None and sep.disputed_at is None:
        msvc.dispute_read(actor, sep.id, {"reason": "Customer says the meter reads high"})

    # 107 — $120.00 posted Oct 1, after the Sep 30 cut-off and on the bill date.
    hannah = accounts[next(r for r in ROSTER if r.get("paid_after_cutoff"))["unit"]]
    if not pm.Payment.objects.filter(
        tenant=tenant, account=hannah, amount=PAID_AFTER_CUTOFF
    ).exists():
        # DEF-BIL-8651 — CLEARED the same day: a `processing` payment meets no
        # bill, so *Apply to this bill* is refused for it; the walk's case is
        # money that has arrived after the cut-off and goes on this bill.
        psvc.record_payment(
            getattr(actor, "user", actor),
            account_id=hannah.id,
            amount=PAID_AFTER_CUTOFF,
            posted_at=datetime(2026, 10, 1, 15, 0, tzinfo=UTC),
            cleared_at=datetime(2026, 10, 1, 15, 0, tzinfo=UTC),
            confirmation="J72-107",
            memo="J72 paid after cut-off",
        )

    for row in ROSTER:
        acct = accounts.get(row["unit"])
        notes.append(
            f"Unit {row['unit']} · {acct.account_no if acct else '—':<14} · {row['name'] or 'nobody':<16} · {row['tag']}"
        )
    notes.append(f"cycle .................. {cycle.code} ({cycle.id})")
    if month_two:
        notes.extend(seed_month_two(tenant, actor, meters, accounts))
    return notes


# ── --e11-states: the three drawn states the plain world cannot reach (DEF-BIL-8689) ──
#
# E11 put every bulk-run state beside its D1 drawing and could not reach three
# on the plain world. OPT-IN, like every other flag here, because each adds a
# unit to the cycle and so moves the figures `J72-bulk-bill-run.spec.ts` asserts:
#
#   unit 113 · vacant, WATER CONNECTED AND NO METER → Scope's *Missing meter*
#              warning and its panel (D1 08);
#   unit 114 · Kim Nguyen, a water meter that records GALLONS on a plan priced
#              in kgal → rating refuses the unit at Calculate (BR-RAT-038 holds
#              no factor), so the bill FAILS TO DRAFT (D1 30) — or, if the Check
#              already prices it, a blocking *Pricing refused* fixed in Plans &
#              Rates; the walk records which;
#   unit 115 · Ana Ruiz, a reading AND a meter that record NO unit → the Check
#              BLOCKS it and it is fixed in Meter Reads, never on the row (D1 14).
#              ⚠ The two ORM writes below are the only way a live account meets
#              it: metering refuses a unitless reading on the way in (rule 3), so
#              the case is data that predates the rule, built the way the
#              Check engine's own tests build it.
E11_UNITS: tuple[dict[str, Any], ...] = (
    {"unit": "113", "name": None},
    {"unit": "114", "name": "Kim Nguyen", "uom": "gal"},
    {"unit": "115", "name": "Ana Ruiz", "uom": "kgal", "unitless": True},
)


def seed_e11_states(tenant, actor) -> list[str]:
    from apps.assets import models as am
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from tests.journey_cohort_fixtures import _premises_for, _unit_on

    water_plan, _both = ensure_plans(tenant)
    cycle = ensure_cycle(tenant)
    premises_id = _premises_for(tenant, actor, ADDRESS, list(SERVICES))
    notes: list[str] = []
    for row in E11_UNITS:
        label = f"Unit {row['unit']}"
        unit_id = _unit_on(tenant, actor, premises_id, label, ["water"])
        if mm.Unit.objects.get(tenant=tenant, pk=unit_id).rate_plan_id is None:
            msvc.assign_unit_plan(
                actor, unit_id, {"tariff_id": str(water_plan.id), "effective_from": "2026-01-01"}
            )
        meter = None
        if row["name"] is not None:
            meter = _meter(tenant, actor, f"W-72{row['unit']}", "water", row["uom"], unit_id)
            unit = row["uom"]
            factor = Decimal(1000) if unit == "gal" else Decimal(1)
            august = _read(tenant, actor, meter, "2026-08-31", str(500 * factor), None, unit)
            if row.get("unitless"):
                # A committed reading is immutable (BR-MET-053's trigger), so the
                # unitless September row is INSERTED as legacy data rather than
                # edited, and the meter's own unit is cleared beside it.
                from tests.test_us_met_reads_helpers import at
                from core.dbfields import uuid7

                if not mm.MeterRead.objects.filter(tenant=tenant, asset_id=meter, read_at=at("2026-09-30")).exists():
                    fields = mm.MeterRead.objects.filter(tenant=tenant, id=august.id).values().first()
                    fields.update(
                        id=uuid7(),
                        read_at=at("2026-09-30"),
                        prior_value=Decimal(500),
                        current_value=Decimal(509),
                        consumption=Decimal(9),
                        unit="",
                        period_start=date(2026, 9, 1),
                        period_end=date(2026, 9, 30),
                    )
                    fields.pop("created_at", None)
                    fields.pop("updated_at", None)
                    mm.MeterRead.objects.create(**fields)
                am.Asset.objects.filter(tenant=tenant, pk=meter).update(unit=None)
            else:
                _read(tenant, actor, meter, "2026-09-30", str(509 * factor), str(500 * factor), unit)
            _account(tenant, actor, unit_id, row["unit"], row["name"], None)
        mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
        notes.append(f"E11 unit {row['unit']} ........... {row['name'] or 'vacant, no meter'}")
    return notes


# ── --never-read: a meter nobody has ever read (changes row 44, 2026-10-01) ──
#
# Row 44 (PO 2026-09-30): *"no multiplier → Hold (default) / Bill with
# multiplier 1"*. Metering answers a multiplier from a meter's latest read, so a
# meter never read has none — and the ruled path refused that as *"ruled path
# refused"* before the clerk could answer. The plain world reads every meter, so
# the case is unreachable there. OPT-IN, like every flag here, because the unit
# joins the cycle and would move the figures the J72 specs assert:
#
#   unit 116 · Rosa Delgado, water meter W-72116 installed and NEVER READ →
#              Check › Meter history › *Meter never read*, opening on Hold.
NEVER_READ_UNIT = {"unit": "116", "name": "Rosa Delgado"}


def seed_never_read(tenant, actor) -> list[str]:
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from tests.journey_cohort_fixtures import _premises_for, _unit_on

    water_plan, _both = ensure_plans(tenant)
    cycle = ensure_cycle(tenant)
    premises_id = _premises_for(tenant, actor, ADDRESS, list(SERVICES))
    row = NEVER_READ_UNIT
    unit_id = _unit_on(tenant, actor, premises_id, f"Unit {row['unit']}", ["water"])
    if mm.Unit.objects.get(tenant=tenant, pk=unit_id).rate_plan_id is None:
        msvc.assign_unit_plan(
            actor, unit_id, {"tariff_id": str(water_plan.id), "effective_from": "2026-01-01"}
        )
    _meter(tenant, actor, f"W-72{row['unit']}", "water", "kgal", unit_id)
    _account(tenant, actor, unit_id, row["unit"], row["name"], None)
    mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
    return [f"never read unit {row['unit']} ... {row['name']} · W-72{row['unit']} has no reading"]


# ── --month-two: what the ACCURACY walk's check A5 needs (2026-09-30) ──────────
#
# Clerk check A5 (`04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md`)
# runs OCTOBER after September on the same accounts and reads the PO's worked
# figures off the October bills. The September world above has no October
# readings and no payment plan, so without these rows October is ten *no
# reading* accounts and case 5 has nothing to skip. OPT-IN, deliberately: the
# plan instalment adds a Check tag to unit 108's account, which moves the
# September tiles `J72-bulk-bill-run.spec.ts` E4 asserts — so the default world
# is exactly what it was, and only `J72-bulk-bill-run-accuracy.spec.ts` seeds
# with the flag.
#
#   unit 101 · a reading on Oct 17 — the walk sends a one-time interim bill
#              for Oct 1 – Oct 17 between the runs, so October bills Oct 18 –
#              Oct 31: 14 days, base $8.00 × 14/30 = $3.73 (case 4);
#   unit 103 · Oct 31 reads 173.0 — September ESTIMATES this meter (no
#              reading), so October bills 173.0 − 158.0 − September's
#              estimate = the true-up (7 kgal when the estimate is 8.0).
#              ⚠ NOT PLANTED HERE (DEF-BIL-8420): Meter Reads trues a reading
#              up against the estimates standing when it is COMMITTED, and
#              September's estimate exists only once September is SENT (B22).
#              Planted up front, October billed all 15 kgal. The walk plants it
#              between the runs with `--late-october-read`, through Meter
#              Reads' own commit (stage, validate, post), so the true-up is
#              Meter Reads' real one;
#   unit 108 · a payment plan, 7 instalments of $45.00 ($315.00) from Sep 15 —
#              September SKIPS one, and the plan is still 7 × $45 ending one
#              month later (case 5), never $90 in one month;
#   all      · an Oct 31 reading on every metered unit, ~8–9 kgal a month.
MONTH_TWO_READS: dict[str, tuple[tuple[str, str], ...]] = {
    "101": (("2026-10-17", "497.0"), ("2026-10-31", "502.0")),
    "102": (("2026-10-31", "324.5"),),
    "104": (("2026-10-31", "228.0"),),
    "105": (("2026-10-31", "421.0"),),
    "106": (("2026-10-31", "530.0"),),
    "107": (("2026-10-31", "636.0"),),
    "108": (("2026-10-31", "727.0"),),
    "109": (("2026-10-31", "834.0"),),
    "110": (("2026-10-31", "918.0"),),
    "111": (("2026-10-31", "1000.0"),),
}
MONTH_TWO_E_READS: dict[str, tuple[tuple[str, str], ...]] = {"108": (("2026-10-31", "12000"),)}
#: DEF-BIL-8420 — unit 103's October reading, planted AFTER September is sent.
LATE_READ_UNIT = "103"
LATE_READ = ("2026-10-31", "173.0")


def plant_late_october_read(tenant, actor) -> str:
    """Unit 103's Oct 31 reading, through METER READS' OWN COMMIT — the same
    three services the quick single-read modal and a CSV use (stage, validate,
    post), so BR-MET-029's true-up against September's billed estimate is
    Meter Reads' real one, not a value this seed computed. Idempotent: a
    reading already on that day is left alone."""
    from apps.metering import services as msvc
    from apps.metering.models import MeterRead
    from tests.test_us_met_reads_helpers import at

    meter_no = f"W-72{LATE_READ_UNIT}"
    day, value = LATE_READ
    if MeterRead.objects.filter(
        tenant=tenant, asset__asset_no=meter_no, read_at=at(day), channel="total"
    ).exists():
        return f"late October read ...... {meter_no} {day} already there"
    batch = msvc.stage_read_batch(
        actor,
        {
            "source_kind": "manual",
            "period_month": "2026-10-01",
            "rows": [
                {"meter_id": meter_no, "read_date": day, "reading": value, "channel": "total"}
            ],
        },
    )
    msvc.validate_read_batch(actor, batch["id"])
    posted = msvc.commit_read_batch(actor, batch["id"], {"certified": True}, defer=False)
    read = (
        MeterRead.objects.filter(
            tenant=tenant, asset__asset_no=meter_no, read_at=at(day), channel="total"
        )
        .order_by("-id")
        .first()
    )
    return (
        f"late October read ...... {meter_no} {day} = {value} · posted "
        f"{posted.get('posted_reads')} · consumption "
        f"{None if read is None else read.consumption} {None if read is None else read.unit}"
    )
PLAN_UNIT = "108"
PLAN_INSTALMENT = Decimal("45.0000")
PLAN_COUNT = 7


def seed_month_two(tenant, actor, meters, accounts) -> list[str]:
    """October's readings and unit 108's payment plan, through their owners."""
    from apps.metering.models import MeterRead
    from apps.payments import plans as payment_plans
    from tests.test_us_met_reads_helpers import at

    def last_value(asset_id):
        # The last REAL reading: an estimate carries no current value.
        row = (
            MeterRead.objects.filter(
                tenant=tenant, asset_id=asset_id, channel="total", current_value__isnull=False
            )
            .order_by("-read_at")
            .first()
        )
        return None if row is None else str(row.current_value)

    for service, table in (("water", MONTH_TWO_READS), ("electric", MONTH_TWO_E_READS)):
        uom = "kgal" if service == "water" else "kWh"
        for unit, reads in table.items():
            asset = meters[unit][service]
            for day, value in reads:
                if MeterRead.objects.filter(
                    tenant=tenant, asset_id=asset, read_at=at(day), channel="total"
                ).exists():
                    continue
                _read(tenant, actor, asset, day, value, last_value(asset), uom)

    account = accounts[PLAN_UNIT]
    user = getattr(actor, "user", actor)
    plan = payment_plans.live_plan_for(account.id)
    if plan is None:
        # Sep 15, Oct 15 … Mar 15: seven months, the first one due in September.
        schedule = tuple(
            (seq, date(2026 + (7 + seq) // 12, (7 + seq) % 12 + 1, 15), PLAN_INSTALMENT)
            for seq in range(1, PLAN_COUNT + 1)
        )
        made = payment_plans.propose_payment_plan(
            actor=user,
            account_id=account.id,
            total_amount=PLAN_INSTALMENT * PLAN_COUNT,
            installments=PLAN_COUNT,
            schedule=schedule,
            proposed_on=date(2026, 8, 20),
        )
        payment_plans.activate_payment_plan(
            actor=user, plan_id=made["id"], signed_on=date(2026, 8, 21)
        )
        plan = payment_plans.live_plan_for(account.id)
    return [
        "month two .............. an Oct 31 reading on every metered unit; unit 101 also Oct 17",
        f"payment plan ........... {account.account_no} · {PLAN_COUNT} × $45.00 from 2026-09-15"
        f" · {plan.status if plan else '—'}",
    ]


class Command(BaseCommand):
    help = "Seed the J72 bulk bill run world (run after seed_demo; idempotent; PostgreSQL)."

    def add_arguments(self, parser):
        # ── J73 — breakdown (F) and scale (S) fixtures, each behind its flag ──
        # 08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md; the code
        # is `_j73_scale.py` beside this file. Without a flag this command
        # seeds exactly the J72 world it always did.
        parser.add_argument(
            "--accounts",
            type=int,
            default=0,
            help="J73 S1–S4: add N scale accounts to the Riverside cycle (10000 or 40000).",
        )
        parser.add_argument(
            "--send-failure",
            action="store_true",
            help="J73 F3: clear electric's revenue account so unit 108's bill (the one electric bill) breaks at Send.",
        )
        parser.add_argument(
            "--second-clerk",
            action="store_true",
            help="J73 F4: a second Billing Clerk who can sign in (Marcus Webb).",
        )
        parser.add_argument(
            "--late-october-read",
            action="store_true",
            help=(
                "ONLY plant unit 103's Oct 31 reading through Meter Reads' commit; run it "
                "AFTER September is sent (DEF-BIL-8420: the true-up needs the estimate first)."
            ),
        )
        parser.add_argument(
            "--month-two",
            action="store_true",
            help="Also seed October readings and a payment plan (the accuracy walk's A5).",
        )
        parser.add_argument(
            "--never-read",
            action="store_true",
            help=(
                "Changes row 44: unit 116 - a water meter that has never been read, so it "
                "has no multiplier (Check: Meter never read, Hold / Bill with multiplier 1)."
            ),
        )
        parser.add_argument(
            "--e11-states",
            action="store_true",
            help=(
                "E11 (DEF-BIL-8689): units 113-115 - a service with no meter, a meter in "
                "gallons on a kgal plan, a reading and meter with no unit."
            ),
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from django.db import connection

        if not settings.DEBUG:
            raise CommandError(
                "refusing to run: DEBUG is off — this seeds fixture rows (seed_demo's rule)."
            )
        if connection.vendor != "postgresql":
            raise CommandError(
                "refusing to run: J72 is walked on PostgreSQL only (hard-won law 14)."
            )
        sjf = _sjf()
        from core import tenancy as core_tenancy

        import time

        from apps.tenancy.management.commands import _j73_scale

        tenant, actor = sjf.tenant_and_actor()
        if options.get("late_october_read"):
            with core_tenancy.tenant_context(tenant.id):
                self.stdout.write(plant_late_october_read(tenant, actor))
            return
        started = time.perf_counter()
        with core_tenancy.tenant_context(tenant.id):
            with transaction.atomic():
                notes = seed(tenant, actor, self.stdout, month_two=options["month_two"])
                if options.get("e11_states"):
                    notes.extend(seed_e11_states(tenant, actor))
                if options.get("never_read"):
                    notes.extend(seed_never_read(tenant, actor))
                if options.get("send_failure") or options.get("second_clerk"):
                    from apps.customers import models as cm

                    accounts = {
                        row["unit"]: cm.Account.objects.get(
                            tenant=tenant,
                            unit__premises__address_line=ADDRESS,
                            unit__label=f"Unit {row['unit']}",
                        )
                        for row in ROSTER
                        if row["name"] is not None
                    }
                    # DEF-BIL-8421 — breaks one bill at Send for real (_j73_scale.seed_send_failure).
                    if options.get("send_failure"):
                        notes.append(_j73_scale.seed_send_failure(tenant, accounts, actor))
                    if options.get("second_clerk"):
                        notes.append(_j73_scale.seed_second_clerk(tenant, actor))
            notes.append(f"J72 world ............... {time.perf_counter() - started:.1f}s")
            if options.get("accounts"):
                timings = _j73_scale.seed_scale(
                    tenant, actor, ensure_cycle(tenant), int(options["accounts"]), self.stdout
                )
                notes.append(f"J73 scale ............... {timings}")
        self.stdout.write("J72 bulk bill run world seeded:")
        for line in notes:
            self.stdout.write("  " + line)
