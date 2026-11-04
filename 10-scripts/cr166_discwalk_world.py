# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 4 task 9 — the discounts FULL WEB WALK
#          (`05-prototype/discounts-2026-10-03/web-walk.md`). The walk's
#          back-office half: the world it stands on (accounts, plans, meters,
#          reads, Utility B) and the REAL bill runs of steps 8 and 9. Every
#          discount is created, viewed, approved, edited and retired through the
#          screen by `cr166_discwalk.mjs`; nothing here writes a discount except
#          `bind` (plan bindings for discounts the plan wizard is not walked
#          for, said so) and `grants` (the engine-half proof of step 9).
#          Shape copied from `cr165_taxwalk_world.py`.
# ───────────────────────────────────────────────────────
"""cr166_discwalk_world — the walk's world and its bill runs, on PostgreSQL.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=false python ../10-scripts/cr166_discwalk_world.py setup

Run after `manage.py migrate` + `manage.py seed_demo` (Brazos Bend = Utility A).

``setup`` (idempotent):
  * water, sewer, trash and storm water switched on (the Settings act);
  * three water plans, each with its own schedule: base `BASE-W` (residential,
    $8.00) + usage 0–10 kgal at $4.20 and above at $5.00, so a RESIDENTIAL
    account using 12 kgal bills **$8.00 + $42.00 + $10.00 = $60.00** — the walk's
    bill — before any discount (no tax is bound):
      - `DW-RES`  *Discount walk · Residential* — Senior, CAP, Lifeline, Lead
        line waiver and Autopay are offered here;
      - `DW-MUNI` *Discount walk · Municipal* — Municipal account (the
        municipal account has no base: `BASE-W` is residential-only, so it
        bills $52.00; 20% = $10.40, capped at $5.00 per bill all the same);
      - `DW-GARDEN` *Discount walk · Garden* — Garden allowance;
      - the off-plan account sits on `DW-OTHER` *Discount walk · Other*, which
        offers nothing.
  * one cycle `DISCWALK` (bill day 15) and one meter per account reading
    12 kgal a month from 09/15/2026 to 02/15/2027 (the February partition is
    created here: a fresh database is partitioned only to January 2027);
  * the accounts (number printed):
      DW-SENIOR  Ruth Alvarez      residential, autopay ON          DW-RES
      DW-CAP     Carl Jensen       residential                      DW-RES
      DW-MEDIC   Mia Okafor        residential                      DW-RES
      DW-PLAIN   Pat Lindgren      residential                      DW-RES
      DW-OFF     Omar Price        residential                      DW-OTHER
      DW-CITY    City Hall         municipal                        DW-MUNI
      DW-GARDEN  Gail Moreno       residential                      DW-GARDEN
  * Utility B (`riverbend`) with no discounts.

``run <start> <end>`` / ``preview <start> <end>`` — a real cycle run (issued /
rolled back), printing every walk account's bill lines.
``bills`` — every issued bill of every walk account.
``lookup <code> <day>…`` — `rating.selectors.billable_discount_rules`, the seam
billing calls, for every walk account on each day: one line per rule returned.
``grants <code> <amount> <from> <to>`` — engine-half proof for step 9 (see
`grants` below).
``accounts`` — the walk accounts as JSON (for the browser walk).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

CYCLE_CODE = "DISCWALK"
TIERS = (("0", "10", "4.2000"), ("10", None, "5.0000"))
PLANS = {
    "DW-RES": "Discount walk · Residential",
    "DW-MUNI": "Discount walk · Municipal",
    "DW-GARDEN": "Discount walk · Garden",
    "DW-OTHER": "Discount walk · Other",
}
#: key, display name, type, autopay, plan code, street
ACCOUNTS = (
    ("DW-SENIOR", "Ruth Alvarez", "residential", True, "DW-RES", "11 Discount Walk Way"),
    ("DW-CAP", "Carl Jensen", "residential", False, "DW-RES", "13 Discount Walk Way"),
    ("DW-MEDIC", "Mia Okafor", "residential", False, "DW-RES", "15 Discount Walk Way"),
    ("DW-PLAIN", "Pat Lindgren", "residential", False, "DW-RES", "17 Discount Walk Way"),
    ("DW-OFF", "Omar Price", "residential", False, "DW-OTHER", "19 Discount Walk Way"),
    ("DW-CITY", "City Hall", "municipal", False, "DW-MUNI", "21 Discount Walk Way"),
    ("DW-GARDEN", "Gail Moreno", "residential", False, "DW-GARDEN", "23 Discount Walk Way"),
)
UNIT_LABEL = "Main"


def _months():
    """09/15/2026 … 02/15/2027, 12 kgal a month. February 2027 is there for
    step 10 (a bill AFTER Senior's retire date of 01/31/2027); `setup` creates
    the meter_reads partitions the months need (`ensure_partitions_cover`),
    because a fresh database is partitioned only to 01/2027."""
    out = []
    year, month, value = 2026, 9, Decimal("100")
    while (year, month) <= (2027, 2):
        out.append((date(year, month, 15).isoformat(), value))
        value += Decimal("12")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


UTILITY_B = {
    "name": "Riverbend Water",
    "subdomain": "riverbend",
    "state": "Iowa",
    "services": ["water"],
    "currency": "USD",
    "plan": "growth",
    "load_defaults": True,
    "owner": {
        "full_name": "Rae Lindqvist",
        "email": "ops@riverbend.example",
        "password": "S3cure!passw0rd",  # walk fixture credential — never prod
        "phone": "+1 (641) 555-0110",
    },
}


def _sjf():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _ctx():
    from core import tenancy as core_tenancy

    tenant, actor = _sjf().tenant_and_actor()
    return tenant, actor, core_tenancy.tenant_context(tenant.id)


def _account(tenant, street):
    from apps.customers import models as cm

    return cm.Account.objects.filter(
        tenant=tenant, unit__premises__address_line=street, unit__label=UNIT_LABEL
    ).first()


def _plan(tenant, code):
    from apps.rating import models as rm
    from apps.rating import selectors as rsel
    from tests.test_us_met_helpers import make_plan, state_size_axis

    plan = rm.RatePlan.objects.filter(tenant=tenant, code=code).first()
    if plan is not None:
        return plan
    plan = make_plan(tenant, name=PLANS[code], code=code, services=("water",))
    tariff = {r["service_code"]: r["tariff"] for r in rsel.plan_rate_schedules(plan.id)}["water"]
    base = rm.Charge.objects.get(tenant=tenant, code="BASE-W")
    version = rm.TariffVersion.objects.create(
        tenant=tenant, tariff=tariff, model="tiered", uom="kgal", currency="USD",
        effective_from=date(2026, 1, 1), base_charge_code=base,
    )
    for seq, (lo, hi, price) in enumerate(TIERS, start=1):
        rm.RateTier.objects.create(
            tenant=tenant, tariff_version=version, seq=seq, from_qty=Decimal(lo),
            to_qty=None if hi is None else Decimal(hi), unit_price=Decimal(price),
        )
    state_size_axis(version, "water")
    return plan


def setup() -> None:
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.tenancy import models as tm
    from apps.tenancy import services as tsvc
    from tests.journey_cohort_fixtures import _premises_for, _unit_on, ensure_services_enabled
    from tests.test_us_met_reads_helpers import a_meter, at, commit_read

    if not tm.Tenant.objects.filter(subdomain=UTILITY_B["subdomain"]).exists():
        made = tsvc.provision_tenant({**UTILITY_B, "owner": dict(UTILITY_B["owner"])})
        print("Utility B provisioned:", made.get("tenant", {}).get("subdomain", made))
    else:
        print("Utility B exists")

    from core import partitioning

    print("partitions:", partitioning.ensure_partitions_cover("meter_reads", date(2026, 9, 1), date(2027, 2, 28)))
    tenant, actor, ctx = _ctx()
    with ctx, transaction.atomic():
        print("services on:", ensure_services_enabled(tenant, actor, "water", "sewer", "storm_water", "trash"))
        plans = {code: _plan(tenant, code) for code in PLANS}
        cycle, _ = mm.Cycle.objects.get_or_create(
            tenant=tenant, code=CYCLE_CODE,
            defaults={"name": "Discount walk", "frequency": "Monthly", "start_day": 16,
                      "days_to_complete": 30, "bill_day": 15, "due_days": 21,
                      "first_run_date": date(2026, 9, 16)},
        )
        from apps.assets import models as am

        reads = _months()
        for key, display, kind, autopay, plan_code, street in ACCOUNTS:
            premises_id = _premises_for(tenant, actor, street, ["water"])
            unit_id = _unit_on(tenant, actor, premises_id, UNIT_LABEL, ["water"])
            unit = mm.Unit.objects.get(tenant=tenant, pk=unit_id)
            if unit.rate_plan_id is None:
                msvc.assign_unit_plan(actor, unit_id, {"tariff_id": str(plans[plan_code].id), "effective_from": "2026-01-01"})
            meter_no = f"W-{key}"
            meter = am.Asset.objects.filter(tenant=tenant, asset_no=meter_no).first()
            meter_id = str(meter.id) if meter else a_meter(actor, asset_no=meter_no, service="water", uom="kgal", unit_id=unit_id)["id"]
            mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
            prior = None
            for day, value in reads:
                if not mm.MeterRead.objects.filter(tenant=tenant, asset_id=meter_id, read_at=at(day), channel="total").exists():
                    commit_read(actor, meter_id, day=day, value=str(value), prior_value=None if prior is None else str(prior),
                                consumption=None if prior is None else str(value - prior), unit="kgal")
                prior = value
            if _account(tenant, street) is None:
                from apps.customers import services as csvc

                slug = display.lower().replace(" ", ".")
                created = csvc.create_account(actor, {
                    "unit_id": str(unit_id), "account_type": kind, "opened_at": "2026-01-01",
                    "autopay": autopay,
                    "contact": {"full_name": display, "phone": "+1 (641) 555-0170", "email": f"{slug}@discwalk.example"},
                    "customer": {"display_name": display, "kind": "person", "identity": {"phone": "+1 (641) 555-0170"}},
                    "addresses": [{"kind": "mailing", "line1": street, "city": "Ottumwa", "state": "IA"}],
                })
                csvc.activate_account(actor, created["id"], None)
        accounts()


def accounts() -> None:
    tenant, _actor, ctx = _ctx()
    out = {}
    with ctx:
        for key, display, kind, autopay, plan_code, street in ACCOUNTS:
            acct = _account(tenant, street)
            out[key] = {"id": str(acct.id), "number": acct.account_no, "name": display, "plan": PLANS[plan_code],
                        "type": kind, "autopay": autopay}
    print("ACCOUNTS " + json.dumps(out))


def bind(discount_code: str, plan_code: str, available_from: str | None = None) -> None:
    """Bind a discount to a plan through `discount_services.attach_discount_to_plan`
    — the service the plan wizard's step 6 save reaches. Used only for the
    discounts whose binding the walk does not click (said so in the report)."""
    from apps.rating import discount_services
    from apps.rating import discounts as dm
    from apps.rating import models as rm

    tenant, actor, ctx = _ctx()
    with ctx, transaction.atomic():
        plan = rm.RatePlan.objects.get(tenant=tenant, code=plan_code)
        discount = dm.Discount.objects.get(tenant=tenant, code=discount_code)
        kwargs = {}
        if available_from:
            kwargs["available_from"] = date.fromisoformat(available_from)
        print(discount_services.attach_discount_to_plan(actor, plan.id, discount.id, **kwargs))


def _template():
    from apps.billing import template_models as tpl
    from core import tenancy as core_tenancy

    row = (
        tpl.BillTemplateVersion.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), status=tpl.VERSION_PUBLISHED,
            template__template_type=tpl.TYPE_BILL,
        ).order_by("template__name", "-version_no").first()
    )
    return row.template_id, int(row.version_no)


class _Rollback(Exception):
    pass


def run(start: str, end: str, *, preview: bool = False) -> None:
    from apps.billing import decisions, issue, runs
    from apps.metering import models as mm

    period_start, period_end = date.fromisoformat(start), date.fromisoformat(end)
    tenant, actor, ctx = _ctx()
    with ctx, transaction.atomic():
        cycle = mm.Cycle.objects.get(tenant=tenant, code=CYCLE_CODE)
        template_id, template_version = _template()
        user = getattr(actor, "user", None)
        bill_run = runs.create_run(
            cycle_id=cycle.id, period_start=period_start, period_end=period_end, bill_date=period_end,
            due_days=21, label=f"Discount walk {end}", template_id=template_id, run_by=user,
        )
        prepared = runs.prepare_run(cycle_id=cycle.id, period_start=period_start, period_end=period_end,
                                    service_date=period_end)
        for row in prepared.decisions:
            print("  decision asked:", row.account_id, row.reason)
            if row.reason == "base_only_billing":
                decisions.record_decision(bill_run=bill_run, account_id=str(row.account_id),
                                          case="base_only_billing", choice="include")
        runs.calculate_run(decisions.apply_decisions(prepared, bill_run=bill_run), bill_run=bill_run)
        from apps.billing import models as bm

        for model in (bm.BillRunExclusion, bm.BillRunBreak):
            for row in model.objects.filter(bill_run=bill_run):
                fields = {f.name: getattr(row, f.name) for f in model._meta.fields
                          if f.name not in ("tenant", "bill_run", "created_at", "updated_at")}
                print(f"  {model.__name__}: {fields}")
        if preview:
            print(f"PREVIEW {start}..{end} (rolled back, nothing kept):")
            bills(period_end=period_end)
            raise _Rollback
        issue.issue_run(bill_run, issued_at=datetime.combine(period_end, datetime.min.time(), tzinfo=UTC),
                        template_id=template_id, template_version=template_version,
                        require_release=False, actor=user)
        runs.record_run_outcome(bill_run, actor=user)
        print(f"run {bill_run.run_no or bill_run.pk} {start}..{end}")
    bills(period_end=period_end)


def bills(period_end: date | None = None) -> None:
    from apps.billing import models as bm
    from apps.rating import discounts as dm

    tenant, _actor, ctx = _ctx()
    with ctx:
        for key, *_rest, street in ACCOUNTS:
            acct = _account(tenant, street)
            invoices = bm.Invoice.objects.filter(account=acct)
            if period_end is not None:
                invoices = invoices.filter(period_end=period_end)
            for inv in invoices.order_by("period_end", "created_at"):
                lines = list(bm.InvoiceLine.objects.filter(invoice=inv).order_by("kind", "id"))
                before = sum((ln.amount for ln in lines if ln.kind not in ("discount", "tax")), Decimal("0"))
                disc = sum((ln.amount for ln in lines if ln.kind == "discount"), Decimal("0"))
                print(f"BILL {key} {acct.account_no} {inv.invoice_no or inv.pk} · {inv.period_start}..{inv.period_end} · "
                      f"{inv.status} · before {before:.2f} · discounts {disc:.2f} · total {Decimal(inv.total):.2f}")
                for line in lines:
                    print(f"   {line.kind:<10} {line.description!s:<44} qty={line.quantity} {Decimal(line.amount):.4f}")
        print("GRANTS discount_grants rows:", dm.DiscountGrant.objects.count())


def lookup(code: str, *days: str) -> None:
    """`rating.selectors.billable_discount_rules` for every walk account on
    each day — what billing is handed. One line per account per day."""
    from apps.rating import selectors as rsel

    tenant, _actor, ctx = _ctx()
    with ctx:
        for day in days:
            for key, *_rest, street in ACCOUNTS:
                acct = _account(tenant, street)
                # (account, PLAN, day) — the plan is the unit's, as billing passes it
                rows = rsel.billable_discount_rules(acct.id, acct.unit.rate_plan_id, date.fromisoformat(day))
                mine = [r for r in rows if r.get("code") == code]
                found = " | ".join(f"{r.get('value'):.2f}% ({r.get('name')})" for r in mine)
                print(f"LOOKUP {code} {day} {key} rows={len(mine)} {found}")


def grants(code: str, account_key: str, amount: str, period_start: str, period_end: str) -> None:
    """ENGINE-HALF PROOF for step 9, because `DEF-2430` (open): the bill path
    writes no `discount_grants` row, so a yearly cap and a budget never deplete
    from real bills. This appends ONE grant through the product's own
    `discount_services.record_grant` — the row issue WOULD write — so a preview
    run can show what the engine does once grants exist. Printed as such."""
    from apps.rating import discount_services
    from apps.rating import discounts as dm

    tenant, actor, ctx = _ctx()
    street = {k: s for k, *_r, s in ACCOUNTS}[account_key]
    with ctx, transaction.atomic():
        acct = _account(tenant, street)
        enrolment = dm.DiscountEnrolment.objects.filter(
            tenant=tenant, discount__code=code, account_id=acct.id, ended_on__isnull=True
        ).first()
        print("GRANT", discount_services.record_grant(
            actor, enrolment.id, date.fromisoformat(period_start), date.fromisoformat(period_end), Decimal(amount)
        ))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if command == "setup":
        setup()
    elif command == "accounts":
        accounts()
    elif command == "bind":
        bind(*sys.argv[2:])
    elif command == "run":
        run(sys.argv[2], sys.argv[3])
    elif command == "preview":
        try:
            run(sys.argv[2], sys.argv[3], preview=True)
        except _Rollback:
            pass
    elif command == "lookup":
        lookup(sys.argv[2], *sys.argv[3:])
    elif command == "grants":
        grants(*sys.argv[2:])
    elif command == "bills":
        bills()
    else:
        raise SystemExit(f"unknown command {command}")
