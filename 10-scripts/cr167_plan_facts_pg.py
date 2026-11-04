"""CR-167-BRC10 round 1 (lane PLAN-SRV) — what a tenant's PLANS bind, measured.

Read-only. Prints, for one tenant on PostgreSQL 16 (law 14):

  * every plan: status, version, dates, services → bound schedule → the base
    charge code that schedule NAMES (or none), and the in-force schedule version;
  * every plan's charge-code attachments, marking the `is_base` ones (the README's
    check (a): BASE-S / BASE-FIRE listed both as base and as a charge code);
  * every `is_base` code per service with its class scope (check (b): why several
    base codes appear on one service);
  * every plan's `plan_deposit_rules` rows (where deposits live today);
  * `plan_versions` rows per plan (is a plan version dated? no — measured).

USAGE
    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python 10-scripts/cr167_plan_facts_pg.py <subdomain>
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.rating import charge_prices, models, selectors  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def main(subdomain: str) -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain=subdomain)
    core_tenancy.set_current_tenant(tenant.id)
    today = date.today()
    print(f"tenant {subdomain} {tenant.id} today {today}")
    print("\n== is_base charge codes per service (class scope, prices in force today)")
    base = models.Charge.objects.filter(tenant_id=tenant.id, is_base=True, deleted_at__isnull=True)
    tables = charge_prices.rows_in_force(list(base), today, with_versions=True)
    for row in base.select_related("service").order_by("service__code", "code"):
        prices = [
            f"{p.size_class}/{p.customer_class or '*'}={p.amount} v{p.version} from {p.effective_from}"
            for p in tables.get(row.id, [])
        ]
        print(
            f"  {row.service.code if row.service_id else '-':12} {row.code:14}"
            f" classes={row.applies_to_customer_classes or 'ALL'}  {prices[:6]}"
            f"{' …' if len(prices) > 6 else ''}"
        )
    for plan in models.RatePlan.objects.filter(tenant_id=tenant.id).order_by("code"):
        print(
            f"\n== PLAN {plan.code} '{plan.name}' status={plan.status} version={plan.version}"
            f" from={plan.effective_from} to={plan.effective_to} min_bill={plan.minimum_bill_amount}"
            f" surcharge_factor={plan.outside_city_factor} late_fee={getattr(plan.late_fee_charge, 'code', None)}"
        )
        for bound in models.PlanRateSchedule.objects.filter(rate_plan=plan).select_related(
            "service", "tariff"
        ):
            version = selectors.in_force_version(bound.tariff, today)
            named = getattr(getattr(version, "base_charge_code", None), "code", None)
            print(
                f"   service {bound.service.code:12} schedule '{bound.tariff.name}'"
                f" in-force version from {getattr(version, 'effective_from', None)}"
                f" names base code: {named}"
            )
        for rule in models.PlanChargeRule.objects.filter(rate_plan=plan).select_related("charge"):
            flag = "  <-- is_base" if rule.charge.is_base else ""
            print(f"   charge rule {rule.charge.code:12} type={rule.charge.charge_type}{flag}")
        for dep in models.PlanDepositRule.objects.filter(rate_plan=plan):
            print(f"   deposit rule account_type={dep.account_type_id} amount={dep.amount} {dep.currency}")
        versions = models.PlanVersion.objects.filter(rate_plan=plan).order_by("version_no")
        print(f"   plan_versions rows: {[ (v.version_no, bool(v.corrects_id)) for v in versions ]}")
        units = models.UnitPlanAssignment.objects.filter(rate_plan=plan, assigned_to__isnull=True)
        print(f"   current units: {units.count()}  plan_version snapshots: "
              f"{sorted(set(units.values_list('plan_version', flat=True)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "brazosbend"))
