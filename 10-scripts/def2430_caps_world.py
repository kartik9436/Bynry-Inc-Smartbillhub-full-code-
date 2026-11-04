# ── Trace ──────────────────────────────────────────────
# Defects: DEF-2430 / DEF-BIL-5341 (discount grants never recorded at issue, so
#          yearly caps and budgets never count down) · DEF-RAT-9366 (the cap
#          year had no end) · DEF-RAT-9367 (a budget overspent by the run that
#          crosses it)
# Ruling:  PO 2026-10-03, decision log "FOUR PO ANSWERS" (5): *"A · Yearly caps
#          don't count down - a"* — "its worked figures go to the PO before it
#          ships". This script PRODUCES those figures on REAL ISSUED runs.
# Shape:   copied from `cr166_discwalk_world.py` (the discounts web walk).
# ───────────────────────────────────────────────────────
"""def2430_caps_world — the yearly-cap worked figures, on PostgreSQL, on real runs.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=false python ../10-scripts/def2430_caps_world.py setup
    … python ../10-scripts/def2430_caps_world.py year          # 14 issued runs
    … python ../10-scripts/def2430_caps_world.py correct DC-CAP25 2027-12-15
    … python ../10-scripts/def2430_caps_world.py bills

Run after `manage.py migrate` + `manage.py seed_demo` (Brazos Bend).

THE WORLD. Water only, its own plan `DC-RES`: base `BASE-W` $8.00 + 0–10 kgal at
$4.20 + above at $5.00, and every account reads **16 kgal a month**, so every
bill is **$8.00 + $42.00 + $30.00 = $80.00** before any discount (no tax bound).
Cycle `DISCCAPS`, bill day 15: a bill's period runs the 16th to the 15th and
its SERVICE DATE is the 15th.

  DC-PLAIN   no discount                                   — a control
  DC-SENIOR  Senior 10 % (no cap)                          — must never move
  DC-CAP25   CAP credit $25.00 a bill, $300.00 a year      — the PO's figure
  DC-CAP35   CAP-35 credit $35.00 a bill, $300.00 a year   — the uneven crossing
  DC-FUND-A  Fund credit $10.00 a bill, $45.00 annual budget, suspend
  DC-FUND-B  (same programme) — the budget is shared by both accounts

`year` issues 14 runs, service dates 12/15/2026 … 01/15/2028, so the calendar
year 2027 holds twelve bills and 2028 starts with the thirteenth.
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

CYCLE_CODE = "DISCCAPS"
PLAN_CODE = "DC-RES"
PLAN_NAME = "Caps walk · Residential"
TIERS = (("0", "10", "4.2000"), ("10", None, "5.0000"))
UNIT_LABEL = "Main"
#: key, display name, street, programme code or None
ACCOUNTS = (
    ("DC-PLAIN", "Paula Plain", "31 Caps Walk Way", None),
    ("DC-SENIOR", "Sam Senior", "33 Caps Walk Way", "DCSENIOR"),
    ("DC-CAP25", "Carl Cap", "35 Caps Walk Way", "DCCAP25"),
    ("DC-CAP35", "Cora Cap", "37 Caps Walk Way", "DCCAP35"),
    ("DC-FUND-A", "Fay Fund", "39 Caps Walk Way", "DCFUND"),
    ("DC-FUND-B", "Finn Fund", "41 Caps Walk Way", "DCFUND"),
)
PROGRAMMES = {
    "DCSENIOR": {"name": "Senior 10%", "discount_type": "percentage", "value": "10"},
    "DCCAP25": {
        "name": "CAP credit",
        "discount_type": "fixed_amount",
        "value": "25",
        "cap_per_year": "300",
    },
    "DCCAP35": {
        "name": "CAP-35 credit",
        "discount_type": "fixed_amount",
        "value": "35",
        "cap_per_year": "300",
    },
    "DCFUND": {
        "name": "Fund credit",
        "discount_type": "fixed_amount",
        "value": "10",
        "budget_cap": "45",
        "budget_period": "annual",
        "exhaustion_behaviour": "suspend",
    },
}


def _reads():
    """11/15/2026 … 01/15/2028, +16 kgal a month."""
    out, (year, month, value) = [], (2026, 11, Decimal("100"))
    while (year, month) <= (2028, 1):
        out.append((date(year, month, 15).isoformat(), value))
        value += Decimal("16")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


def _periods():
    """(start, end) for the 14 runs: 11/16/2026–12/15/2026 … 12/16/2027–01/15/2028."""
    days = [date.fromisoformat(d) for d, _v in _reads()]
    return [(days[i].replace(day=16), days[i + 1]) for i in range(len(days) - 1)]


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


def _plan(tenant):
    from apps.rating import models as rm
    from apps.rating import selectors as rsel
    from tests.test_us_met_helpers import make_plan, state_size_axis

    plan = rm.RatePlan.objects.filter(tenant=tenant, code=PLAN_CODE).first()
    if plan is not None:
        return plan
    plan = make_plan(tenant, name=PLAN_NAME, code=PLAN_CODE, services=("water",))
    tariff = {r["service_code"]: r["tariff"] for r in rsel.plan_rate_schedules(plan.id)}["water"]
    base = rm.Charge.objects.get(tenant=tenant, code="BASE-W")
    version = rm.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model="tiered",
        uom="kgal",
        currency="USD",
        effective_from=date(2026, 1, 1),
        base_charge_code=base,
    )
    for seq, (lo, hi, price) in enumerate(TIERS, start=1):
        rm.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=seq,
            from_qty=Decimal(lo),
            to_qty=None if hi is None else Decimal(hi),
            unit_price=Decimal(price),
        )
    state_size_axis(version, "water")
    return plan


def _programme(actor, plan, code):
    from apps.rating import discount_services
    from apps.rating import discounts as dm

    row = dm.Discount.objects.filter(code=code).first()
    if row is None:
        spec = dict(PROGRAMMES[code])
        payload = {
            "code": code,
            "name": spec.pop("name"),
            "program_owner": "billing",
            "applies_to": dm.SCOPE_WHOLE_BILL,
            "effective_from": "2026-11-01",
            "enrolment_mode": dm.ENROLMENT_APPLY_AND_APPROVE,
            "verification_method": dm.VERIFY_ONE_TIME_PROOF,
            "eligibility": "household_income_limit",
            **spec,
        }
        made = discount_services.create_discount(actor, payload)
        discount_services.submit_discount(actor, made["id"])
        discount_services.approve_discount(actor, made["id"])
        row = dm.Discount.objects.get(pk=made["id"])
    if not dm.PlanDiscountRule.objects.filter(rate_plan=plan, discount=row).exists():
        discount_services.attach_discount_to_plan(actor, plan.id, row.id)
    return row


def setup() -> None:
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.rating import discount_services
    from apps.rating import discounts as dm
    from core import partitioning
    from tests.journey_cohort_fixtures import (
        _premises_for,
        _unit_on,
        ensure_services_enabled,
    )
    from tests.test_us_met_reads_helpers import a_meter, at, commit_read

    for table in ("meter_reads",):
        print(
            "partitions:",
            partitioning.ensure_partitions_cover(table, date(2026, 11, 1), date(2028, 2, 28)),
        )
    tenant, actor, ctx = _ctx()
    with ctx, transaction.atomic():
        print("services on:", ensure_services_enabled(tenant, actor, "water"))
        plan = _plan(tenant)
        cycle, _ = mm.Cycle.objects.get_or_create(
            tenant=tenant,
            code=CYCLE_CODE,
            defaults={
                "name": "Caps walk",
                "frequency": "Monthly",
                "start_day": 16,
                "days_to_complete": 30,
                "bill_day": 15,
                "due_days": 21,
                "first_run_date": date(2026, 11, 16),
            },
        )
        from apps.assets import models as am
        from apps.customers import services as csvc

        reads = _reads()
        for key, display, street, programme in ACCOUNTS:
            premises_id = _premises_for(tenant, actor, street, ["water"])
            unit_id = _unit_on(tenant, actor, premises_id, UNIT_LABEL, ["water"])
            unit = mm.Unit.objects.get(tenant=tenant, pk=unit_id)
            if unit.rate_plan_id is None:
                msvc.assign_unit_plan(
                    actor,
                    unit_id,
                    {"tariff_id": str(plan.id), "effective_from": "2026-01-01"},
                )
            meter_no = f"W-{key}"
            meter = am.Asset.objects.filter(tenant=tenant, asset_no=meter_no).first()
            meter_id = (
                str(meter.id)
                if meter
                else a_meter(
                    actor,
                    asset_no=meter_no,
                    service="water",
                    uom="kgal",
                    unit_id=unit_id,
                )["id"]
            )
            mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
            prior = None
            for day, value in reads:
                if not mm.MeterRead.objects.filter(
                    tenant=tenant, asset_id=meter_id, read_at=at(day), channel="total"
                ).exists():
                    commit_read(
                        actor,
                        meter_id,
                        day=day,
                        value=str(value),
                        prior_value=None if prior is None else str(prior),
                        consumption=None if prior is None else str(value - prior),
                        unit="kgal",
                    )
                prior = value
            acct = _account(tenant, street)
            if acct is None:
                slug = display.lower().replace(" ", ".")
                created = csvc.create_account(
                    actor,
                    {
                        "unit_id": str(unit_id),
                        "account_type": "residential",
                        "opened_at": "2026-01-01",
                        "autopay": False,
                        "contact": {
                            "full_name": display,
                            "phone": "+1 (641) 555-0171",
                            "email": f"{slug}@capswalk.example",
                        },
                        "customer": {
                            "display_name": display,
                            "kind": "person",
                            "identity": {"phone": "+1 (641) 555-0171"},
                        },
                        "addresses": [
                            {
                                "kind": "mailing",
                                "line1": street,
                                "city": "Ottumwa",
                                "state": "IA",
                            }
                        ],
                    },
                )
                csvc.activate_account(actor, created["id"], None)
                acct = _account(tenant, street)
            if programme:
                discount = _programme(actor, plan, programme)
                if not dm.DiscountEnrolment.objects.filter(
                    discount=discount, account=acct, ended_on__isnull=True
                ).exists():
                    row = discount_services.enrol_account(
                        actor, discount.id, acct.id, enrolled_on=date(2026, 11, 1)
                    )
                    discount_services.verify_enrolment(
                        actor,
                        row["id"],
                        proof_kind="income_statement",
                        verified_on=date(2026, 11, 1),
                    )
        print("SETUP done")


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
    return row.template_id, int(row.version_no)


def run(start: date, end: date) -> None:
    from apps.billing import decisions, issue, runs
    from apps.billing import models as bm
    from apps.metering import models as mm

    tenant, actor, ctx = _ctx()
    with ctx, transaction.atomic():
        cycle = mm.Cycle.objects.get(tenant=tenant, code=CYCLE_CODE)
        template_id, template_version = _template()
        user = getattr(actor, "user", None)
        bill_run = runs.create_run(
            cycle_id=cycle.id,
            period_start=start,
            period_end=end,
            bill_date=end,
            due_days=21,
            label=f"Caps walk {end}",
            template_id=template_id,
            run_by=user,
        )
        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=start, period_end=end, service_date=end
        )
        for row in prepared.decisions:
            if row.reason == "base_only_billing":
                decisions.record_decision(
                    bill_run=bill_run,
                    account_id=str(row.account_id),
                    case="base_only_billing",
                    choice="include",
                )
        runs.calculate_run(
            decisions.apply_decisions(prepared, bill_run=bill_run), bill_run=bill_run
        )
        for brk in bm.BillRunBreak.objects.filter(bill_run=bill_run):
            print(
                f"  BREAK {end} account={brk.account_id} {getattr(brk, 'reason', '')} {getattr(brk, 'detail', '')}"[
                    :400
                ]
            )
        _end_enrolment_between_draft_and_issue(tenant, end)
        issue.issue_run(
            bill_run,
            issued_at=datetime.combine(end, datetime.min.time(), tzinfo=UTC),
            template_id=template_id,
            template_version=template_version,
            require_release=False,
            actor=user,
        )
        runs.record_run_outcome(bill_run, actor=user)
    print(f"RUN {start}..{end} issued")


def _end_enrolment_between_draft_and_issue(tenant, period_end) -> None:
    """`DEF-RAT-9522` proof. `CAPS_END_AT=<period end>:<account key>:<ended on>`
    ends that account's enrolment, back-dated, AFTER its bill is drafted and
    BEFORE it issues — the bill must still issue (PO 2026-10-04)."""
    spec = os.environ.get("CAPS_END_AT")
    if not spec:
        return
    at, key, ended_on = spec.split(":")
    if date.fromisoformat(at) != period_end:
        return
    from apps.rating import discounts as dm

    street = {k: s for k, _n, s, _p in ACCOUNTS}[key]
    acct = _account(tenant, street)
    n = dm.DiscountEnrolment.objects.filter(account=acct, ended_on__isnull=True).update(
        ended_on=date.fromisoformat(ended_on), end_reason="withdrawn"
    )
    print(f"  ENDED {key} enrolment(s)={n} on {ended_on}, after drafting {period_end}")


def year() -> None:
    for start, end in _periods():
        run(start, end)
    bills()


def correct(account_key: str, period_end: str) -> None:
    """Restate ONE issued bill through the product's own correction
    (`corrections.execute_restatement`) — a credit note, the original's grants
    given back, and a rebill priced on the caps as they then stand."""
    from apps.billing import corrections
    from apps.billing import models as bm

    tenant, actor, ctx = _ctx()
    street = {k: s for k, _n, s, _p in ACCOUNTS}[account_key]
    with ctx, transaction.atomic():
        acct = _account(tenant, street)
        inv = bm.Invoice.objects.get(
            account=acct,
            period_end=date.fromisoformat(period_end),
            status=bm.INVOICE_ISSUED,
        )
        preview = corrections.recompute(inv)
        print(
            "PREVIEW",
            [(ln.kind, str(ln.amount)) for ln in preview.lines if ln.kind == "discount"],
            "total",
            preview.total,
        )
        impact = corrections.build_impact(
            inv,
            reason_codes=("meter_read_error",),
            correction_class=corrections.CLASS_RESTATEMENT,
            corrected=preview,
        )
        template_id, template_version = _template()
        user = getattr(actor, "user", None)
        out = corrections.execute_restatement(
            inv,
            impact=impact,
            reason="meter_read_error",
            issued_at=datetime.combine(
                date.fromisoformat(period_end), datetime.min.time(), tzinfo=UTC
            ),
            on_date=date.fromisoformat(period_end),
            template_id=template_id,
            template_version=template_version,
            actor=user,
        )
        print("CORRECTED", out)
    bills()


def bills() -> None:
    from apps.billing import models as bm
    from apps.rating import discounts as dm

    tenant, _actor, ctx = _ctx()
    out = []
    with ctx:
        for key, _name, street, programme in ACCOUNTS:
            acct = _account(tenant, street)
            for inv in bm.Invoice.objects.filter(account=acct).order_by("period_end", "created_at"):
                lines = list(bm.InvoiceLine.objects.filter(invoice=inv).order_by("kind", "id"))
                disc = sum((ln.amount for ln in lines if ln.kind == "discount"), Decimal("0"))
                before = sum((ln.amount for ln in lines if ln.kind != "discount"), Decimal("0"))
                out.append(
                    {
                        "account": key,
                        "service_date": inv.service_date.isoformat(),
                        "status": inv.status,
                        "invoice": inv.invoice_no,
                        "before": f"{before:.2f}",
                        "discount": f"{disc:.2f}",
                        "total": f"{Decimal(inv.total):.2f}",
                        "lines": [
                            [
                                ln.kind,
                                f"{Decimal(ln.amount):.2f}",
                                getattr(ln, "discount_code", None),
                            ]
                            for ln in lines
                        ],
                    }
                )
                print(
                    f"BILL {key:<10} {inv.service_date} {inv.status:<9} {inv.invoice_no or '-':<16} "
                    f"before {before:>7.2f} discount {disc:>7.2f} total {Decimal(inv.total):>7.2f}"
                )
        rows = dm.DiscountGrant.objects.filter(discount__code__startswith="DC").order_by(
            "granted_at", "id"
        )
        print("GRANTS", rows.count())
        for g in rows:
            rev = getattr(g, "reverses_grant_id", None)
            print(
                f"  GRANT {g.discount.code:<9} {g.period_end} {Decimal(g.amount):>8.2f}{'  (reversal)' if rev else ''}"
            )
    Path(os.environ.get("CAPS_OUT", "/dev/null")).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if command == "setup":
        setup()
    elif command == "year":
        year()
    elif command == "run":
        run(date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3]))
    elif command == "correct":
        correct(sys.argv[2], sys.argv[3])
    elif command == "bills":
        bills()
    else:
        raise SystemExit(f"unknown command {command}")
