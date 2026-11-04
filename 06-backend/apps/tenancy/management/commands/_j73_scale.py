# ── Trace ──────────────────────────────────────────────
# Journey:  J73 — the bulk bill run, breakdown and scale (F1–F5, S1–S4) ·
#           08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md
# Criteria: 04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md §3–§4
# Command:  seed_j72_bulk_run --accounts N (this file is its scale half; the
#           leading underscore keeps Django from listing it as a command)
# Pattern:  10-scripts/seed_j70_one_time_bill.py (four-service plan, carts,
#           sewer as a share of water) · 10-scripts/cr051_run_benchmark.py
#           (`_clone`, the billable subtree of one account)
# ───────────────────────────────────────────────────────
"""The Riverside cycle at the size of the utility: N more accounts, 10,000 or 40,000.

WHAT ONE SCALE ACCOUNT IS. A residential account on its own unit, holding a
four-service plan — **water** on one meter (three in four accounts) or two
meters (one in four), **electric** on one meter, **trash** with one or two
96-gallon carts, and **sewer** as 40% of the water usage — with readings on Jul
31, Aug 31 and Sep 30, so a September run over Riverside finds a clean,
priceable account. One account in ten carries a payment posted in September.
The consumption varies account by account (a deterministic spread, not a
constant), so no two drafts are the same number and a sum cannot pass by
coincidence.

HOW IT IS WRITTEN, AND WHY IT IS TWO HALVES.

1. **THE TEMPLATES GO THROUGH THE OWNING MODULES' SERVICES**, exactly as the
   base J72 world does: premises and units through metering, meters and carts
   through assets, reads through `commit_read`, plan assignment through
   `metering.services.assign_unit_plan`, the account and its activation
   through `customers.services`. There are four templates (1 or 2 water
   meters × 1 or 2 carts). If the services refuse a template, the seed stops
   there, before a single clone exists — a clone of a refused shape is 40,000
   refused shapes.

2. **THE N CLONES ARE BULK INSERTS OF THOSE TEMPLATES' ROWS**, one table at a
   time, a thousand accounts per statement batch. There is no module service
   that creates ten thousand accounts, units or reads in one call (the import
   pipelines are file-driven and per row), and one service call per row
   measured ~1.2 s per account here — 13 hours at 40,000. So the rows each
   service wrote for a template are copied field by field (`_clone`, the
   `cr051_run_benchmark.py` precedent), with every identity, number and
   foreign key re-pointed at the copy. **A clone never crosses a tenant**: every
   row is copied inside `tenant_context` from a row of the same tenant.

   ⚠ **THE PAYMENTS ARE THE EXCEPTION AND GO THROUGH THE SERVICE, ONE BY ONE**
   (`payments.services.record_payment`), because a payment posts to the
   ledger and only the ledger posting service writes journal lines (hard rule
   5). A cloned payment row would be a payment with no journal — a world no
   product path could make. That is why only one account in ten has one.

WHAT IT DOES NOT CLAIM. The clones are a synthetic customer base on real
product shapes: the Check, the price and the send see the same statements
against the same tables as a real 40,000-account utility, which is what S1–S4
measure. They are NOT a demo fixture and carry the account-number prefix
`J73S-` so they can never be mistaken for one.

IDEMPOTENT: a second run tops the scale population up to N and adds nothing
when it is already there. TENANT-SCOPED: every statement runs inside the
caller's `tenant_context`. POSTGRESQL ONLY: the command refuses anything else
before this module is imported.

Figures are fixture VALUES, not signed law; no ❄️ B4/B5 figure is touched.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

SCALE_PREFIX = "J73S"
PLAN_NAME = "Residential Four-Service (Riverside J73)"
PLAN_CODE = "RES-4S-J73"
SERVICES = ("water", "electric", "trash", "sewer")
TEMPLATE_ADDRESS = "2300 Riverside Dr"
ACCOUNT_TYPE = "residential"
TRASH_PER_CART = "15.0000"
SEWER_PERCENT = Decimal("40.000000")  # percent POINTS, as rating stores them
SEWER_RATE = "5.0000"
ELECTRIC_RATE = "0.1245"
WATER_V1 = (("0", None, "3.2500"),)  # to Sep 30, 2026
WATER_V2 = (("0", None, "3.5000"),)  # from Oct 1, 2026
READ_DAYS = ("2026-07-31", "2026-08-31", "2026-09-30")
PAYMENT_EVERY = 10
PAYMENT_AMOUNT = Decimal("45.0000")
BATCH = 1000

#: (label, water meters, carts) — the four shapes every clone is one of.
TEMPLATES = (
    ("T1", 1, 1),
    ("T2", 1, 2),
    ("T3", 1, 1),
    ("T4", 2, 1),
)


# ── the plan ────────────────────────────────────────────────────────────────
def _base_code(tenant, service_code: str, code: str, amount: str):
    """The residential base code for a service: seed_demo's where it has one
    (BASE-W, BASE-E), minted here for trash and sewer where it does not. Two
    base codes covering one class would refuse every bill as ambiguous, so an
    existing one always wins."""
    from apps.rating import models as rm
    from apps.tenancy import models as tm

    service = tm.Service.objects.get(code=service_code)
    for charge in rm.Charge.objects.filter(tenant=tenant, service=service, is_base=True):
        classes = charge.applies_to_customer_classes or []
        if not classes or ACCOUNT_TYPE in classes:
            return charge
    return rm.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=f"{service_code.title()} base (Riverside J73)",
        charge_type="recurring",
        service=service,
        amount_rule="flat",
        amount=Decimal(amount),
        is_base=True,
        kind="base",
        applies_to_customer_classes=[ACCOUNT_TYPE],
    )


def ensure_plan(tenant):
    from apps.rating import selectors as rsel
    from apps.tenancy import models as tm
    from apps.tenancy.management.commands.seed_j72_bulk_run import _version, state_size_axis_for
    from tests.test_us_met_helpers import make_plan

    plan = make_plan(tenant, name=PLAN_NAME, code=PLAN_CODE, services=SERVICES)
    tariffs = {row["service_code"]: row["tariff"] for row in rsel.plan_rate_schedules(plan.id)}
    bases = {
        "water": _base_code(tenant, "water", "BASE-W-J73", "8.0000"),
        "electric": _base_code(tenant, "electric", "BASE-E-J73", "12.0000"),
        "trash": _base_code(tenant, "trash", "BASE-T-J73", "3.0000"),
        "sewer": _base_code(tenant, "sewer", "BASE-S-J73", "6.0000"),
    }
    jan1 = date(2026, 1, 1)
    w1 = _version(
        tenant,
        tariffs["water"],
        model="tiered",
        uom="kgal",
        effective_from=jan1,
        effective_to=date(2026, 9, 30),
        tiers=WATER_V1,
        base_charge_code=bases["water"],
    )
    w2 = _version(
        tenant,
        tariffs["water"],
        model="tiered",
        uom="kgal",
        effective_from=date(2026, 10, 1),
        tiers=WATER_V2,
        base_charge_code=bases["water"],
    )
    for version in (w1, w2):
        state_size_axis_for(version, "water")
    e = _version(
        tenant,
        tariffs["electric"],
        model="flat",
        uom="kWh",
        effective_from=jan1,
        tiers=(("0", None, ELECTRIC_RATE),),
        base_charge_code=bases["electric"],
    )
    state_size_axis_for(e, "electric")
    t = _version(
        tenant,
        tariffs["trash"],
        model="tiered",
        uom="cart",
        effective_from=jan1,
        tiers=(("0", None, TRASH_PER_CART),),
        base_charge_code=bases["trash"],
    )
    state_size_axis_for(t, "trash")
    _version(
        tenant,
        tariffs["sewer"],
        model="percent_of_service",
        uom="kgal",
        effective_from=jan1,
        tiers=(("0", None, SEWER_RATE),),
        percent=SEWER_PERCENT,
        basis_service=tm.Service.objects.get(code="water"),
        percent_basis="usage",
        base_charge_code=bases["sewer"],
    )
    return plan


# ── the templates (through the services) ───────────────────────────────────
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
    """One reading through Meter Reads, stamped with its day count and start
    day as a real posting is (the J70 seed's `_read`, DEF-BIL-8324)."""
    from apps.metering.models import MeterRead
    from tests.test_us_met_reads_helpers import at, commit_read

    if MeterRead.objects.filter(
        tenant=tenant, asset_id=asset_id, read_at=at(day), channel="total"
    ).exists():
        return
    previous = (
        MeterRead.objects.filter(
            tenant=tenant, asset_id=asset_id, channel="total", read_at__lt=at(day)
        )
        .order_by("-read_at")
        .first()
    )
    consumption = None if prior is None else Decimal(value) - Decimal(prior)
    commit_read(
        actor,
        asset_id,
        day=day,
        value=str(value),
        prior_value=None if prior is None else str(prior),
        consumption=None if consumption is None else str(consumption),
        unit=unit,
        days_since_prior=(at(day) - previous.read_at).days if previous else None,
        period_start=previous.read_at.date() if previous else None,
    )


def build_templates(tenant, actor, cycle, plan) -> list[Any]:
    """The four template accounts, through the services. Returns the Accounts."""
    from apps.customers import models as cm
    from apps.customers import services as csvc
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.tenancy import models as tm
    from apps.tenancy.management.commands.seed_j72_bulk_run import _meter
    from tests.journey_cohort_fixtures import _premises_for, _unit_on, ensure_services_enabled

    ensure_services_enabled(tenant, actor, *SERVICES)
    tm.TenantService.objects.filter(tenant=tenant, service__code="trash").update(
        billing_basis="capacity"
    )
    premises_id = _premises_for(tenant, actor, TEMPLATE_ADDRESS, list(SERVICES))
    accounts = []
    for label, water_meters, carts in TEMPLATES:
        unit_id = _unit_on(tenant, actor, premises_id, f"Template {label}", list(SERVICES))
        if mm.Unit.objects.get(tenant=tenant, pk=unit_id).rate_plan_id is None:
            msvc.assign_unit_plan(
                actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
            )
        waters = [
            _meter(tenant, actor, f"W-73{label}{n}", "water", "kgal", unit_id)
            for n in range(1, water_meters + 1)
        ]
        electric = _meter(tenant, actor, f"E-73{label}", "electric", "kWh", unit_id)
        for n in range(1, carts + 1):
            _cart(tenant, actor, f"CART-73{label}{n}", unit_id)
        for n, meter in enumerate(waters):
            base = Decimal(100 + 50 * n)
            values = [base, base + 9, base + 18, base + 27]
            for i, day in enumerate(READ_DAYS):
                _read(tenant, actor, meter, day, values[i + 1], values[i], "kgal")
        evalues = [Decimal(5000), Decimal(5600), Decimal(6200), Decimal(6800)]
        for i, day in enumerate(READ_DAYS):
            _read(tenant, actor, electric, day, evalues[i + 1], evalues[i], "kWh")
        mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
        existing = cm.Account.objects.filter(tenant=tenant, unit_id=unit_id).first()
        if existing is None:
            name = f"Template {label} Riverside"
            phone = f"+1 (281) 555-73{label[-1]}0"
            created = csvc.create_account(
                actor,
                {
                    "unit_id": str(unit_id),
                    "account_type": ACCOUNT_TYPE,
                    "opened_at": "2025-07-01",
                    "contact": {
                        "full_name": name,
                        "phone": phone,
                        "email": f"template.{label.lower()}.j73@example.com",
                    },
                    "customer": {
                        "display_name": name,
                        "kind": "person",
                        "identity": {"phone": phone},
                    },
                    "addresses": [
                        {
                            "kind": "mailing",
                            "line1": TEMPLATE_ADDRESS,
                            "city": "Katy",
                            "state": "TX",
                        }
                    ],
                },
            )
            csvc.activate_account(actor, created["id"])
            existing = cm.Account.objects.get(pk=created["id"])
        accounts.append(existing)
    return accounts


# ── F3 · one bill that breaks at Send, for a stated reason ─────────────────
F3_UNIT = "108"  # Diego Ramos — the ONE J72 account that sells electric
F3_SERVICE = "electric"


def seed_send_failure(tenant, accounts: dict[str, Any], actor) -> str:
    """Diego Ramos's bill will not issue: ELECTRIC has no revenue account.

    ⚠ **THIS FLAG USED TO PIN OMAR HADDAD'S ACCOUNT TO AN UNPUBLISHED TEMPLATE,
    AND THAT BROKE NOTHING (DEF-BIL-8421).** Since BR-BIL-1041 (2026-09-30) a
    bulk run carries a REQUIRED, published template, and `issue_run` treats a
    run's template as an explicit pin that governs every bill — so the
    account's override was never read and Send issued all eight bills. The
    walk found it; the seed now breaks a bill the way a utility actually does.

    WHY THIS BREAK. Every usage and base line is stamped at ISSUE with the
    revenue account its service maps to (`issue._gl_account_for`, BR-BIL-010:
    *"A human sets this on the GL mapping page; nothing here picks a bucket for
    it"*). With electric's mapping cleared, the one bill carrying an electric
    line — unit 108's, the only electric account in the J72 world — is refused
    inside its own savepoint and every other bill goes (BR-BIL-055). Nothing at
    Check, Calculate or Sign off reads the GL map, so the clerk meets it first
    at Send, which is F3's point. The break's sentence names the service and
    the page that fixes it.

    ⚠ **IT CLEARS A TENANT-WIDE MAPPING** — `tenant_services` is tenancy's own
    table and this is tenancy's command, so it is an ORM write to the module's
    own row. Any other electric bill on this walk database breaks the same way,
    which is why the flag is for the plain J72 world and not with `--accounts`.
    Re-map it on Settings → GL mapping (or re-seed) to undo it.
    """
    from apps.tenancy import models as tm

    cleared = tm.TenantService.objects.filter(
        tenant_id=tenant.id, service__code=F3_SERVICE
    ).update(revenue_account_id=None, base_revenue_account_id=None)
    account = accounts[F3_UNIT]
    return (
        f"F3 send failure ......... {account.account_no}: {F3_SERVICE} revenue account cleared "
        f"({cleared} service row) — its bill breaks at Send"
    )


# ── F4 · a second clerk with billing rights ────────────────────────────────
F4_EMAIL = "marcus.webb.j73@brazosbendutilities.com"
F4_NAME = "Marcus Webb"
F4_PASSWORD = "S3cure!passw0rd"  # the e2e harness's own password (support/app.ts)


def seed_second_clerk(tenant, actor) -> str:
    """Marcus Webb, Billing Clerk, signed-in-able — through identity's services.

    `add_user` mints the invited membership and a one-time temp password;
    `change_password` is the forced first-sign-in change that ACTIVATES it
    (BR-IDN-011/022). So the second clerk is made the way a System Admin makes
    one on S-users and signs in with the harness's password, which is what F4
    needs: two real browsers on one run.
    """
    from apps.identity import models as im
    from apps.identity import selectors as isel
    from apps.identity import services as isvc

    # `add_user` records who invited whom (BR-IDN-011), so the actor must be a
    # real `users` row carrying its role — identity's own sample seam does the
    # same (`sample_data._owner_as_actor`).
    user = getattr(actor, "user", actor)
    user.role = getattr(actor, "role", None)
    existing = isel.user_by_email(tenant.id, F4_EMAIL)
    if existing is None:
        clerk, _membership, temp = isvc.add_user(
            actor=user,
            tenant_id=tenant.id,
            full_name=F4_NAME,
            email=F4_EMAIL,
            role_code=im.BILLING_CLERK,
        )
        clerk.refresh_from_db()
        isvc.change_password(
            actor=clerk,
            new_password=F4_PASSWORD,
            confirm_password=F4_PASSWORD,
            current_password=temp,
        )
        existing = clerk
    return f"F4 second clerk .......... {F4_NAME} <{F4_EMAIL}> · billing_clerk"


# ── the clones (bulk inserts) ──────────────────────────────────────────────
FIRST = (
    "Ana",
    "Ben",
    "Carla",
    "Dev",
    "Elena",
    "Farid",
    "Grace",
    "Hugo",
    "Iris",
    "Jamal",
    "Kira",
    "Luis",
    "Mona",
    "Nate",
    "Olga",
    "Pavel",
    "Quinn",
    "Rosa",
    "Sami",
    "Tara",
)
LAST = (
    "Adams",
    "Brooks",
    "Chen",
    "Diaz",
    "Evans",
    "Fischer",
    "Garcia",
    "Hughes",
    "Ibrahim",
    "Jones",
    "Khan",
    "Lopez",
    "Moreno",
    "Nguyen",
    "Okafor",
    "Patel",
    "Reyes",
    "Silva",
    "Tran",
    "Walsh",
)
UNITS_PER_PREMISES = 25
TABLES = (
    "premises",
    "units",
    "service_points",
    "assets",
    "asset_assignments",
    "unit_plan_assignments",
    "customers",
    "accounts",
    "customer_accounts",
    "contacts",
    "addresses",
    "service_agreements",
    "meter_reads",
)


def _models() -> dict[str, Any]:
    from django.apps import apps

    return {m._meta.db_table: m for m in apps.get_models()}


def _clone(row, **overrides):
    """A new row with the same concrete field values and a fresh id — the
    `cr051_run_benchmark._clone` rule: field by field, so a column added
    tomorrow is carried; the primary key is SKIPPED rather than nulled because
    `meter_reads` has a composite key over its partition column."""
    from core.dbfields import uuid7

    fresh = row.__class__()
    for field in row._meta.concrete_fields:
        if field.primary_key:
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        setattr(fresh, field.attname, getattr(row, field.attname))
    fresh.id = uuid7()
    for name, value in overrides.items():
        setattr(fresh, name, value)
    fresh._state.adding = True
    return fresh


class _Template:
    """Every row one template account's services wrote, loaded once."""

    def __init__(self, tenant, account, t: dict[str, Any]) -> None:
        tid = tenant.id
        self.account = account
        self.unit = t["units"].objects.get(pk=account.unit_id)
        self.premises = t["premises"].objects.get(pk=self.unit.premises_id)
        self.points = list(
            t["service_points"].objects.filter(
                tenant_id=tid, unit_id=self.unit.id, deleted_at__isnull=True
            )
        )
        self.assignments = list(
            t["asset_assignments"].objects.filter(
                tenant_id=tid, unit_id=self.unit.id, to_date__isnull=True
            )
        )
        self.assets = {
            str(a.id): a
            for a in t["assets"].objects.filter(pk__in=[x.asset_id for x in self.assignments])
        }
        self.plans = list(
            t["unit_plan_assignments"].objects.filter(tenant_id=tid, unit_id=self.unit.id)
        )
        self.links = list(
            t["customer_accounts"].objects.filter(tenant_id=tid, account_id=account.id)
        )
        self.customers = {
            str(c.id): c
            for c in t["customers"].objects.filter(pk__in=[x.customer_id for x in self.links])
        }
        self.contacts = list(t["contacts"].objects.filter(tenant_id=tid, account_id=account.id))
        self.addresses = list(t["addresses"].objects.filter(tenant_id=tid, account_id=account.id))
        self.agreements = list(
            t["service_agreements"].objects.filter(tenant_id=tid, account_id=account.id)
        )
        self.reads: dict[str, list[Any]] = {}
        for read in (
            t["meter_reads"]
            .objects.filter(
                tenant_id=tid, asset_id__in=list(self.assets), superseded_by_id__isnull=True
            )
            .order_by("read_at")
        ):
            self.reads.setdefault(str(read.asset_id), []).append(read)


def _spread(index: int, meter: int, k: int, service: str) -> Decimal:
    """A deterministic, varied consumption: water 5–13 kgal, electric 450–750 kWh."""
    if service == "electric":
        return Decimal(600 + (((index * 13 + k * 5 + meter) % 21) - 10) * 15)
    return Decimal(9 + ((index * 7 + k * 3 + meter) % 9) - 4)


def scale_count(tenant) -> int:
    from apps.customers import models as cm

    return cm.Account.objects.filter(
        tenant=tenant, account_no__startswith=f"{SCALE_PREFIX}-"
    ).count()


def clone_batch(tenant, templates, t, start: int, stop: int, service_by_asset) -> None:
    """Accounts `start`..`stop-1` of the scale population, one bulk insert per table."""
    rows: dict[str, list[Any]] = {name: [] for name in TABLES}
    premises_by_block: dict[int, Any] = {}
    wanted = sorted({i // UNITS_PER_PREMISES for i in range(start, stop)})
    for existing in t["premises"].objects.filter(
        tenant_id=tenant.id, premise_no__in=[f"{SCALE_PREFIX}-P{b:05d}" for b in wanted]
    ):
        premises_by_block[int(existing.premise_no.rsplit("P", 1)[1])] = existing
    for i in range(start, stop):
        tpl = templates[i % len(templates)]
        block = i // UNITS_PER_PREMISES
        street = f"{3000 + block} Riverside Dr"
        premises = premises_by_block.get(block)
        if premises is None:
            premises = _clone(
                tpl.premises,
                premise_no=f"{SCALE_PREFIX}-P{block:05d}",
                address_line=street,
                external_ref=None,
                master_account_id=None,
                gis_parcel_id=None,
            )
            premises_by_block[block] = premises
            rows["premises"].append(premises)
        unit = _clone(
            tpl.unit,
            premises_id=premises.id,
            unit_no=f"{SCALE_PREFIX}-U{i:06d}",
            label=f"Unit {i % UNITS_PER_PREMISES + 1:02d}",
            external_ref=None,
        )
        rows["units"].append(unit)
        point_map = {}
        for point in tpl.points:
            fresh = _clone(point, unit_id=unit.id)
            point_map[str(point.id)] = fresh
            rows["service_points"].append(fresh)
        asset_map = {}
        ordered = sorted(tpl.assets.items(), key=lambda kv: kv[1].asset_no)
        for n, (old_id, asset) in enumerate(ordered):
            sp = point_map.get(str(asset.service_point_id))
            fresh = _clone(
                asset,
                asset_no=f"{SCALE_PREFIX}-{i:06d}-{n}",
                serial_no=f"{SCALE_PREFIX}{i:06d}{n}",
                external_ref=None,
                service_point_id=None if sp is None else sp.id,
            )
            asset_map[old_id] = fresh
            rows["assets"].append(fresh)
        for assignment in tpl.assignments:
            rows["asset_assignments"].append(
                _clone(assignment, unit_id=unit.id, asset_id=asset_map[str(assignment.asset_id)].id)
            )
        for plan in tpl.plans:
            rows["unit_plan_assignments"].append(_clone(plan, unit_id=unit.id))
        name = f"{FIRST[i % len(FIRST)]} {LAST[(i // len(FIRST)) % len(LAST)]}"
        customer_map = {}
        for old_id, customer in tpl.customers.items():
            fresh = _clone(
                customer,
                display_name=name,
                external_ref=None,
                customer_no=f"{SCALE_PREFIX}-C{i:06d}",
            )
            customer_map[old_id] = fresh
            rows["customers"].append(fresh)
        account = _clone(
            tpl.account,
            unit_id=unit.id,
            premises_id=premises.id,
            account_no=f"{SCALE_PREFIX}-{i:06d}",
            external_ref=None,
        )
        rows["accounts"].append(account)
        for link in tpl.links:
            rows["customer_accounts"].append(
                _clone(
                    link, account_id=account.id, customer_id=customer_map[str(link.customer_id)].id
                )
            )
        for contact in tpl.contacts:
            fresh = _clone(contact, account_id=account.id)
            if hasattr(fresh, "full_name"):
                fresh.full_name = name
            rows["contacts"].append(fresh)
        for address in tpl.addresses:
            rows["addresses"].append(_clone(address, account_id=account.id, line1=street))
        for agreement in tpl.agreements:
            sp = point_map.get(str(agreement.service_point_id))
            if sp is not None:
                rows["service_agreements"].append(
                    _clone(agreement, account_id=account.id, service_point_id=sp.id)
                )
        for meter_no, (old_id, reads) in enumerate(sorted(tpl.reads.items())):
            service = service_by_asset.get(old_id, "water")
            value = Decimal(reads[0].prior_value or 0) + (i % 997) * 10
            for k, read in enumerate(reads):
                used = _spread(i, meter_no, k, service)
                rows["meter_reads"].append(
                    _clone(
                        read,
                        asset_id=asset_map[old_id].id,
                        account_id=account.id,
                        prior_value=value,
                        current_value=value + used,
                        consumption=used,
                    )
                )
                value += used
    for table in TABLES:
        if rows[table]:
            t[table].objects.bulk_create(rows[table], batch_size=2000)


def seed_scale(tenant, actor, cycle, target: int, out) -> dict[str, Any]:
    """Top the Riverside scale population up to `target`; return the timings."""
    from django.db import transaction

    from apps.customers import models as cm
    from apps.payments import models as pm
    from apps.payments import services as psvc

    timings: dict[str, Any] = {"target": target}
    started = time.perf_counter()
    with transaction.atomic():
        plan = ensure_plan(tenant)
        accounts = build_templates(tenant, actor, cycle, plan)
    timings["templates_s"] = round(time.perf_counter() - started, 1)
    t = _models()
    templates = [_Template(tenant, account, t) for account in accounts]
    service_by_asset = {}
    for tpl in templates:
        for asset_id, asset in tpl.assets.items():
            point = next((p for p in tpl.points if p.id == asset.service_point_id), None)
            service_by_asset[asset_id] = "water" if point is None else point.service.code
    have = scale_count(tenant)
    timings["already"] = have
    clone_started = time.perf_counter()
    for start in range(have, target, BATCH):
        stop = min(start + BATCH, target)
        with transaction.atomic():
            clone_batch(tenant, templates, t, start, stop, service_by_asset)
        out.write(f"  cloned {stop:>6} of {target} · {time.perf_counter() - clone_started:7.1f}s")
    timings["clone_s"] = round(time.perf_counter() - clone_started, 1)

    # Payments through the payments service, one by one — hard rule 5.
    pay_started = time.perf_counter()
    paid = 0
    user = getattr(actor, "user", actor)
    already = set(
        pm.Payment.objects.filter(
            tenant=tenant, confirmation__startswith=f"{SCALE_PREFIX}-PAY-"
        ).values_list("confirmation", flat=True)
    )
    due = (
        cm.Account.objects.filter(tenant=tenant, account_no__startswith=f"{SCALE_PREFIX}-")
        .order_by("account_no")
        .values_list("id", "account_no")
    )
    for account_id, account_no in list(due):
        index = int(account_no.rsplit("-", 1)[1])
        confirmation = f"{SCALE_PREFIX}-PAY-{index:06d}"
        if index % PAYMENT_EVERY or confirmation in already:
            continue
        with transaction.atomic():
            psvc.record_payment(
                user,
                account_id=account_id,
                amount=PAYMENT_AMOUNT,
                posted_at=datetime(2026, 9, 15, 15, 0, tzinfo=UTC),
                confirmation=confirmation,
                memo="J73 scale — September payment",
            )
        paid += 1
    timings["payments"] = paid
    timings["payments_s"] = round(time.perf_counter() - pay_started, 1)
    timings["total_s"] = round(time.perf_counter() - started, 1)
    timings["scale_accounts"] = scale_count(tenant)
    return timings
