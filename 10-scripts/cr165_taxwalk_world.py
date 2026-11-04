# ── Trace ──────────────────────────────────────────────
# Change:  CR-165-BRC10 round 4 task 9 — the taxes & fees FULL WEB WALK
#          (`05-prototype/taxes-fees-2026-10-03/web-walk.md`). This is the
#          walk's back-office half: the world it stands on (phase 0) and the
#          REAL bill runs of phase 5. Every tax is created, viewed and edited
#          through the screen by `cr165_taxwalk.mjs`; nothing here writes a tax.
# ───────────────────────────────────────────────────────
"""cr165_taxwalk_world — phase 0 world and phase 5 bill runs, on PostgreSQL.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=false python ../10-scripts/cr165_taxwalk_world.py setup
    … python ../10-scripts/cr165_taxwalk_world.py run 2026-09-16 2026-10-15
    … python ../10-scripts/cr165_taxwalk_world.py bills

Run after `manage.py migrate` + `manage.py seed_demo` (Brazos Bend = Utility A).

``setup`` (idempotent):
  * switches on sewer, storm water and trash beside water (the walk's four
    services) through `tenancy.services.update_tenant_service`, the Settings act;
  * three accounts with the authorities (TX Comptroller, Wapello County, City of
    Ottumwa) through `rating.services`' authority-account service;
  * ONE commercial account billed by cycle `TAXWALK` (bill day 15): water plan
    *Tax walk · Commercial water*, the commercial base code the demo already
    carries at its 5/8" size ($15.00), usage priced 0–10 kgal at $3.50 and above
    at $5.00, so 12 kgal reads **$45.00 + $15.00 = $60.00**, the walk's bill.
    Reads 09/15 100, 10/15 112, 11/15 124 kgal; the premises is inside city
    limits. (The walk table says $40.00 usage + $20.00 base; only the $60.00 the
    taxes are charged on is the walk's figure — the split is this world's.)
  * Utility B (`riverbend`, owner `ops@riverbend.example`) with no taxes,
    provisioned through `tenancy.services.provision_tenant`.

``run <start> <end>`` — a real cycle run for that period with the bill dated
`<end>`: created, prepared, decided, calculated and issued through
`billing.runs` / `decisions` / `issue`, exactly as `seed_j72_bulk_run` sends
its August run. Prints every line of the walk account's bill.

``preview <start> <end>`` — the same run, calculated and then ROLLED BACK.

``bills`` — every issued bill of the walk account and its tax lines.
"""

from __future__ import annotations

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

PLAN_NAME = "Tax walk · Commercial water"
PLAN_CODE = "TAXWALK-COM-W"
CYCLE_CODE = "TAXWALK"
ADDRESS = "1 Tax Walk Way"
UNIT_LABEL = "Suite 1"
METER_NO = "W-TAXWALK-1"
READS = (("2026-09-15", "100.0", None), ("2026-10-15", "112.0", "100.0"), ("2026-11-15", "124.0", "112.0"))
TIERS = (("0", "10", "3.5000"), ("10", None, "5.0000"))
AUTHORITY_ACCOUNTS = (
    ("TX Comptroller", "TX-32-1774410"),
    ("Wapello County Treasurer", "WAP-0091"),
    ("City of Ottumwa Finance", "OTT-0042"),
)
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


def _account(tenant):
    from apps.customers import models as cm

    return cm.Account.objects.filter(
        tenant=tenant, unit__premises__address_line=ADDRESS, unit__label=UNIT_LABEL
    ).first()


def setup() -> None:
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.rating import models as rm
    from apps.rating import selectors as rsel
    from apps.tenancy import models as tm
    from apps.tenancy import services as tsvc
    from tests.journey_cohort_fixtures import _premises_for, _unit_on, ensure_services_enabled
    from tests.test_us_met_helpers import make_plan, state_size_axis
    from tests.test_us_met_reads_helpers import a_meter, at, commit_read

    if not tm.Tenant.objects.filter(subdomain=UTILITY_B["subdomain"]).exists():
        made = tsvc.provision_tenant({**UTILITY_B, "owner": dict(UTILITY_B["owner"])})
        print("Utility B provisioned:", made.get("tenant", {}).get("subdomain", made))
    else:
        print("Utility B exists")

    tenant, actor, ctx = _ctx()
    with ctx, transaction.atomic():
        print("services on:", ensure_services_enabled(tenant, actor, "water", "sewer", "storm_water", "trash"))
        from apps.rating import services as rsvc

        for name, number in AUTHORITY_ACCOUNTS:
            if not rm.TaxAuthorityAccount.objects.filter(tenant=tenant, account_number=number).exists():
                rsvc.create_authority_account(actor, {"authority_name": name, "account_number": number})
        print("authority accounts:", rm.TaxAuthorityAccount.objects.filter(tenant=tenant).count())

        plan = rm.RatePlan.objects.filter(tenant=tenant, code=PLAN_CODE).first()
        if plan is None:
            plan = make_plan(tenant, name=PLAN_NAME, code=PLAN_CODE, services=("water",))
            tariff = {r["service_code"]: r["tariff"] for r in rsel.plan_rate_schedules(plan.id)}["water"]
            base = rm.Charge.objects.get(tenant=tenant, code="BASE-W-COM")
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
        cycle, _ = mm.Cycle.objects.get_or_create(
            tenant=tenant, code=CYCLE_CODE,
            defaults={"name": "Tax walk", "frequency": "Monthly", "start_day": 16,
                      "days_to_complete": 30, "bill_day": 15, "due_days": 21,
                      "first_run_date": date(2026, 9, 16)},
        )
        premises_id = _premises_for(tenant, actor, ADDRESS, ["water"])
        mm.Premises.objects.filter(tenant=tenant, pk=premises_id).update(inside_city_limits=True)
        unit_id = _unit_on(tenant, actor, premises_id, UNIT_LABEL, ["water"])
        unit = mm.Unit.objects.get(tenant=tenant, pk=unit_id)
        if unit.rate_plan_id is None:
            msvc.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"})
        from apps.assets import models as am

        meter = am.Asset.objects.filter(tenant=tenant, asset_no=METER_NO).first()
        meter_id = str(meter.id) if meter else a_meter(actor, asset_no=METER_NO, service="water", uom="kgal", unit_id=unit_id)["id"]
        mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
        for day, value, prior in READS:
            if not mm.MeterRead.objects.filter(tenant=tenant, asset_id=meter_id, read_at=at(day), channel="total").exists():
                commit_read(actor, meter_id, day=day, value=value, prior_value=prior,
                            consumption=None if prior is None else str(Decimal(value) - Decimal(prior)), unit="kgal")
        if _account(tenant) is None:
            from apps.customers import services as csvc

            created = csvc.create_account(actor, {
                "unit_id": str(unit_id), "account_type": "commercial", "opened_at": "2026-01-01",
                "contact": {"full_name": "Riverside Diner", "phone": "+1 (641) 555-0142", "email": "owner@riversidediner.example"},
                "customer": {"display_name": "Riverside Diner", "kind": "person", "identity": {"phone": "+1 (641) 555-0142"}},
                "addresses": [{"kind": "mailing", "line1": ADDRESS, "city": "Ottumwa", "state": "IA"}],
            })
            csvc.activate_account(actor, created["id"], None)
        acct = _account(tenant)
        print(f"walk account {acct.account_no} · plan {plan.name} ({plan.id}) · cycle {cycle.code}")


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
            due_days=21, label=f"Tax walk {end}", template_id=template_id, run_by=user,
        )
        prepared = runs.prepare_run(cycle_id=cycle.id, period_start=period_start, period_end=period_end,
                                    service_date=period_end)
        for row in prepared.decisions:
            print("  decision asked:", row.account_id, row.reason)
            if row.reason == "base_only_billing":
                decisions.record_decision(bill_run=bill_run, account_id=str(row.account_id),
                                          case="base_only_billing", choice="include")
        runs.calculate_run(decisions.apply_decisions(prepared, bill_run=bill_run), bill_run=bill_run)
        if preview:
            print("PREVIEW (rolled back, nothing kept):")
            bills()
            raise _Rollback
        issue.issue_run(bill_run, issued_at=datetime.combine(period_end, datetime.min.time(), tzinfo=UTC),
                        template_id=template_id, template_version=template_version,
                        require_release=False, actor=user)
        runs.record_run_outcome(bill_run, actor=user)
        print(f"run {bill_run.run_no or bill_run.pk} {start}..{end}")
    bills()


def bills() -> None:
    from apps.billing import models as bm

    tenant, _actor, ctx = _ctx()
    with ctx:
        acct = _account(tenant)
        for inv in bm.Invoice.objects.filter(account=acct).order_by("period_end", "created_at"):
            print(f"BILL {inv.invoice_no or inv.pk} · {inv.period_start}..{inv.period_end} · status {inv.status} · total {inv.total}")
            for line in bm.InvoiceLine.objects.filter(invoice=inv).order_by("kind", "id"):
                print(f"   {line.kind:<10} {line.description!s:<48} qty={line.quantity} {line.amount} · tax_id={getattr(line, 'tax_id', None)}")


def lookup(*days: str) -> None:
    """The billing lookup itself — `rating.selectors.plan_tax_rules`, the seam
    `billing.gather._taxes_for` calls — for the walk plan, a commercial water
    account inside city limits, on each day. Prints one line per row returned."""
    from apps.rating import models as rm
    from apps.rating import selectors as rsel

    tenant, _actor, ctx = _ctx()
    with ctx:
        plan = rm.RatePlan.objects.get(tenant=tenant, code=PLAN_CODE)
        for day in days:
            rows = rsel.plan_tax_rules(
                str(plan.id), date.fromisoformat(day), services=("water",),
                customer_class="commercial", premises={"inside_city_limits": True},
            )
            by_chain: dict[str, list[str]] = {}
            for row in rows:
                tax = rm.Tax.objects.get(pk=row["tax_id"])
                amount = row.get("rate") or row.get("per_unit_amount") or row.get("flat_amount") or row.get("per_meter_amount")
                by_chain.setdefault(tax.code, []).append(f"v{tax.version_no} {amount}")
            for code, found in sorted(by_chain.items()):
                print(f"LOOKUP {day} {code} rows={len(found)} {' | '.join(found)}")


def lookup_plan(plan_name: str, day: str) -> None:
    """Every tax row the billing lookup returns for a named plan on a day, for
    a residential account inside city limits on every service (walk 1.8: a
    draft is never among them)."""
    from apps.rating import models as rm
    from apps.rating import selectors as rsel

    tenant, _actor, ctx = _ctx()
    with ctx:
        plan = rm.RatePlan.objects.get(tenant=tenant, name=plan_name)
        rows = rsel.plan_tax_rules(
            str(plan.id), date.fromisoformat(day),
            services=("water", "sewer", "trash", "storm_water", "electric"),
            customer_class="residential", premises={"inside_city_limits": True},
        )
        for row in rows:
            tax = rm.Tax.objects.get(pk=row["tax_id"]) if row.get("tax_id") else None
            print(f"PLANLOOKUP {day} {plan_name} · {tax.name if tax else row['code']} · draft={tax.is_draft if tax else '-'}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if command == "setup":
        setup()
    elif command == "run":
        run(sys.argv[2], sys.argv[3])
    elif command == "preview":
        try:
            run(sys.argv[2], sys.argv[3], preview=True)
        except _Rollback:
            pass
    elif command == "lookup-plan":
        lookup_plan(sys.argv[2], sys.argv[3])
    elif command == "lookup":
        lookup(*sys.argv[2:])
    elif command == "bills":
        bills()
    else:
        raise SystemExit(f"unknown command {command}")
