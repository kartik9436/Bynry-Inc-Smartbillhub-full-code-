"""CR-167-BRC10 follow-up (lane PLAN-MONEY) — `DEF-RAT-9335` on the worked
account, on PostgreSQL 16: a residential water bill whose schedule NAMES its
base code (`BASE-W1`, $10.00) while another water base code (`BASE-W-FIRE`,
priced only for 1" and 2") reaches the account.

PO ruling 2026-10-03, verbatim: *"(a) Fix it: use the base the schedule names.
Bills refused today start going out; bills already issued don't change."*
Worked figure shown: September water $146.50 + $10.00 base = **$156.50**.

Run AFTER `cr167_money_world.py` and `cr167_base_checks_pg.py` (which create
`BASE-W1` and `BASE-W-FIRE` and widen them to every class). This script names
`BASE-W1` on the water schedule of plan `SCW-RES` (a column write on the
probe tenant — the same stated probe shortcut as `cr167_base_checks_pg.py`)
and dates the two codes' prices 2026-01-01 (shortcut 2, stated at the write),
picks the first `SCW-RES` account with a 5/8" water connection and an issued
bill, and prices that bill's period with the one-time PREVIEW (the bill engine;
read-only, rolled back). Run it once with the tip's code and once with the
fix: before, REFUSED by `BASE-W-FIRE`; after, the bill.

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python 10-scripts/cr167_def_rat_9335_probe_pg.py plansrv-rcp [AC-2026-00025]
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from apps.billing import models as billing_models  # noqa: E402
from apps.billing import one_time  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.metering import selectors as metering_selectors  # noqa: E402
from apps.rating import models, selectors  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def _lines(body):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "kind" in node and "amount" in node and "description" in node:
                found.append((str(node.get("service") or "-"), str(node["kind"]), str(node["amount"]), str(node["description"])))
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(body)
    return sorted(found)


def main(subdomain: str, account_no: str | None = None) -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain=subdomain)
    core_tenancy.set_current_tenant(tenant.id)
    plan = models.RatePlan.objects.get(tenant_id=tenant.id, code="SCW-RES")
    water = tenancy_models.Service.objects.get(code="water")
    bound = models.PlanRateSchedule.objects.get(rate_plan=plan, service=water)
    w1 = models.Charge.objects.get(tenant_id=tenant.id, code="BASE-W1")
    account = None
    for row in customer_models.Account.objects.filter(tenant_id=tenant.id).order_by("account_no"):
        if row.unit_id is None or (account_no and row.account_no != account_no):
            continue
        unit_plan = (
            models.UnitPlanAssignment.objects.filter(unit_id=row.unit_id, assigned_to__isnull=True)
            .values_list("rate_plan_id", flat=True)
            .first()
        )
        if str(unit_plan) != str(plan.id):
            continue
        if metering_selectors.connection_size_for(row.unit_id, "water") != "W-58":
            continue
        last = (
            billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=row.id, status="issued")
            .order_by("-period_end")
            .first()
        )
        if last is not None:
            account = (row, last)
            break
    if account is None:
        print("no SCW-RES account with a 5/8\" water connection and an issued bill")
        return 1
    row, last = account
    # Probe shortcut 2, stated: `cr167_base_checks_pg.py` creates BASE-W1 and
    # BASE-W-FIRE with no `effective_from`, so their prices start on the day
    # it runs and price no day of a September bill. The PO's utility priced
    # them long before; their rows are dated 2026-01-01 here (a column write
    # on the probe tenant only) so the September bill sees what it would.
    models.ChargeCodeAmount.objects.filter(
        tenant_id=tenant.id, charge__code__in=["BASE-W1", "BASE-W-FIRE"]
    ).update(effective_from="2026-01-01")
    version = selectors.in_force_version(bound.tariff, last.period_end)
    models.TariffVersion.objects.filter(pk=version.pk).update(base_charge_code=w1)
    print(f"plan {plan.code}; water schedule '{bound.tariff.name}' (from {version.effective_from}) NAMES BASE-W1")
    print(f"account {row.account_no}, 5/8\" water; issued bill {last.period_start}..{last.period_end}")
    codes = list(
        models.Charge.objects.filter(tenant_id=tenant.id, is_base=True, service=water, deleted_at__isnull=True)
        .order_by("code")
        .values_list("code", "applies_to_customer_classes")
    )
    print(f"water base codes: {codes}")
    request = one_time.OneTimeRequest(
        account_id=str(row.id), kind="interim", period_start=last.period_start, period_end=last.period_end
    )
    try:
        with transaction.atomic():
            body = one_time.preview(request)
            transaction.set_rollback(True)
    except Exception as exc:  # noqa: BLE001 — a refusal is the measurement
        print(f"REFUSED: {type(exc).__name__}: {str(exc)[:400]}")
        return 0
    if body.get("blocked"):
        print(f"BLOCKED: {body['blocked']}")
    lines = _lines(body)
    for service, kind, amount, description in lines:
        print(f"   {service:8} {kind:8} {Decimal(amount):>10.2f}  {description}")
    untaxed = sum((Decimal(a) for s, k, a, _d in lines if k != "tax"), Decimal("0"))
    water_lines = sum((Decimal(a) for s, k, a, _d in lines if s == "water"), Decimal("0"))
    print(f"water lines {water_lines:.2f}; all lines before tax {untaxed:.2f}; with tax "
          f"{sum((Decimal(a) for *_x, a, _d in lines), Decimal('0')):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
