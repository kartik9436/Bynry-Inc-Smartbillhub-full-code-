"""CR-167-BRC10 round 1 (lane PLAN-SRV) — the README's two checks, on REAL bills.

  (a) *"BASE-S and BASE-FIRE show both under base and in the charge-code list
      today. Check whether they are counted twice on a bill."*
  (b) *"A residential plan's water base shows '8.00 · 10.00 · 8.00 from BASE-W ·
      BASE-W1 · BASE-W-COM · BASE-W-FIRE'. Find out why four base codes resolve."*

WHAT IT DOES, on ONE throwaway probe utility (never a shared tenant), PostgreSQL 16:

  1. picks the published plan that carries sewer AND fire and an account on it
     that has an ISSUED bill, and prints that bill's lines (the real bill);
  2. prices the same account and period with the one-time PREVIEW (the engine
     that produces the bill; it writes nothing) — the baseline;
  3. attaches the plan's sewer and fire BASE codes as ordinary plan charge codes
     through `services.update_plan` (exactly what the PO's plan holds), prices
     again, and prints the difference — check (a);
  4. adds two more water base codes the way the PO's utility has them (one for
     every class at $10.00, one priced by size), prints what today's plan screen
     rule shows (every active `is_base` code of the service), what the server's
     live base read answers for the plan's class (schedule names nothing, then
     names the $10.00 code), and prices the bill each way — check (b).

Step 4 names the schedule's base code with a direct column write on the probe
tenant's in-force schedule version: the measurement needs the binding a utility
makes on the rate schedule's own screen, and that screen's write path is not
under test here. It is stated, not hidden.

USAGE
    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> \\
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    /tmp/venv_a5c/bin/python 10-scripts/cr167_base_checks_pg.py <probe-subdomain>
"""

from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from apps.billing import models as billing_models  # noqa: E402
from apps.billing import one_time  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.rating import models, selectors, services  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def _actor(tenant_id) -> SimpleNamespace:
    owner = (
        identity_models.User.objects.filter(tenant_id=tenant_id)
        .order_by("created_at")
        .values_list("id", flat=True)
        .first()
    )
    return SimpleNamespace(
        id=uuid.UUID(str(owner)),
        pk=uuid.UUID(str(owner)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )


def _lines(body) -> list[tuple[str, str, str, str]]:
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "kind" in node and "amount" in node and "description" in node:
                found.append(
                    (
                        str(node.get("service") or "-"),
                        str(node.get("kind")),
                        str(node.get("description"))[:60],
                        str(node.get("amount")),
                    )
                )
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(body)
    return found


def _price(account_id, start, end, label):
    request = one_time.OneTimeRequest(
        account_id=str(account_id), kind="interim", period_start=start, period_end=end
    )
    try:
        body = one_time.preview(request)
    except Exception as exc:  # noqa: BLE001 — a refusal IS the measurement
        print(f"   [{label}] REFUSED: {type(exc).__name__}: {str(exc)[:300]}")
        return None
    lines = _lines(body)
    total = sum((Decimal(a) for _, _, _, a in lines), Decimal("0"))
    print(f"   [{label}] {len(lines)} line(s), sum of lines {total:.2f}")
    for line in lines:
        print(f"      {line[0]:8} {line[1]:10} {line[3]:>10}  {line[2]}")
    if not lines:
        print(f"   [{label}] keys: {sorted(body)}")
        for key in ("problems", "gaps", "refusals", "blocked", "exceptions", "errors", "stops"):
            if body.get(key):
                print(f"   [{label}] {key}: {str(body[key])[:600]}")
    problems = body.get("problems") or body.get("refusals") or body.get("exceptions")
    if problems:
        print(f"   [{label}] problems: {str(problems)[:400]}")
    return lines


def main(subdomain: str) -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain=subdomain)
    core_tenancy.set_current_tenant(tenant.id)
    actor = _actor(tenant.id)

    plan = None
    for candidate in models.RatePlan.objects.filter(tenant_id=tenant.id, status="published"):
        codes = set(
            models.PlanRateSchedule.objects.filter(rate_plan=candidate).values_list(
                "service__code", flat=True
            )
        )
        if {"sewer", "fire"} <= codes:
            plan = candidate
            break
    if plan is None:
        print("no published plan binds both sewer and fire on this tenant")
        return 1
    print(f"PLAN {plan.code} '{plan.name}' classes={plan.account_type_ids}")

    # An account on this plan with an issued bill carrying the most services.
    invoices = billing_models.Invoice.objects.filter(tenant_id=tenant.id, status="issued")
    best = None
    for invoice in invoices.order_by("-period_end"):
        services_on = set(
            billing_models.InvoiceLine.objects.filter(invoice=invoice).values_list(
                "service__code", flat=True
            )
        )
        unit_id = (
            customer_models.Account.objects.filter(pk=invoice.account_id)
            .values_list("unit_id", flat=True)
            .first()
        )
        unit_plan = (
            models.UnitPlanAssignment.objects.filter(unit_id=unit_id, assigned_to__isnull=True)
            .values_list("rate_plan_id", flat=True)
            .first()
        )
        if {"sewer", "fire"} <= services_on and str(unit_plan) == str(plan.id):
            best = invoice
            break
    if best is None:
        print("no issued bill carries both sewer and fire")
        return 1
    print(
        f"\n(a) THE REAL BILL: invoice {best.id} account {best.account_id}"
        f" period {best.period_start}..{best.period_end} total {getattr(best, 'total', None)}"
    )
    for line in billing_models.InvoiceLine.objects.filter(invoice=best).select_related(
        "service", "charge"
    ).order_by("service__code", "kind"):
        print(
            f"      {getattr(line.service, 'code', '-'):8} {line.kind:10} {line.amount:>12.2f}"
            f"  {getattr(line.charge, 'code', '-'):10} {line.description[:60]}"
        )

    start, end = best.period_start, best.period_end
    before = _price(best.account_id, start, end, "preview, plan as seeded")

    base_codes = {
        row.service.code: row
        for row in models.Charge.objects.filter(
            tenant_id=tenant.id, is_base=True, deleted_at__isnull=True,
            service__code__in=["sewer", "fire"],
        ).select_related("service")
    }
    print(f"\n(a) attaching as plan charge codes: {[c.code for c in base_codes.values()]}")
    existing = [
        {"charge": str(rule.charge_id), "recurrence": rule.recurrence, "taxable": rule.taxable}
        for rule in models.PlanChargeRule.objects.filter(rate_plan=plan)
    ]
    attach = existing + [
        {"charge": str(code.id), "recurrence": "recurring", "taxable": False}
        for code in base_codes.values()
        if str(code.id) not in {row["charge"] for row in existing}
    ]
    try:
        with transaction.atomic():
            services.update_plan(
                actor, plan.id, {"charge_rules": attach, "reason": "CR-167 probe: check (a)"}
            )
        print("   update_plan ACCEPTED the base codes as plan charge codes")
    except Exception as exc:  # noqa: BLE001
        print(f"   update_plan REFUSED: {type(exc).__name__}: {str(exc)[:300]}")
    after = _price(best.account_id, start, end, "preview, base codes ALSO on the charge list")
    if before is not None and after is not None:
        print(f"   (a) lines before {len(before)} after {len(after)};"
              f" identical: {sorted(before) == sorted(after)}")

    # ── (b) ────────────────────────────────────────────────────────────────
    print("\n(b) four water base codes")
    water = tenancy_models.Service.objects.get(code="water")
    # The PO's utility stored its four water base codes BEFORE the 2026-10-01
    # overlap guard (`rating.charges.base_already_covered`, `services.py:6956`),
    # which refuses a NEW overlapping base code and touches nothing stored. So
    # each code is created through `create_charge` on a class nobody else
    # covers, then widened to every class with a column write — the stored
    # shape such a utility holds today. Probe tenant only; stated, not hidden.
    for code, name, scratch_class, payload in (
        ("BASE-W-FIRE", "Water base — fire service line, by size", "builder_developer",
         {"amount_rule": "flat", "size_amounts": [
             {"size_class": "W-1", "amount": "12.00"}, {"size_class": "W-2", "amount": "20.00"}]}),
        ("BASE-W1", "Water base — every class", "agricultural",
         {"amount_rule": "flat", "amount": "10.00"}),
    ):
        if not models.Charge.objects.filter(tenant_id=tenant.id, code=code).exists():
            try:
                with transaction.atomic():
                    services.create_charge(
                        actor,
                        {"code": code, "name": name, "service": "water", "kind": "base",
                         "is_base": True, "charge_type": "recurring",
                         "applies_to_customer_classes": [scratch_class], **payload},
                    )
                print(f"   created {code} ({payload}), then widened to every class")
            except Exception as exc:  # noqa: BLE001
                print(f"   create {code} refused: {type(exc).__name__}: {str(exc)[:300]}")
    models.Charge.objects.filter(
        tenant_id=tenant.id, code__in=["BASE-W1", "BASE-W-FIRE"]
    ).update(applies_to_customer_classes=[])
    active = list(
        models.Charge.objects.filter(
            tenant_id=tenant.id, is_base=True, deleted_at__isnull=True, service=water
        ).order_by("code")
    )
    print(f"   today's plan screen rule (every active is_base code of water): "
          f"{[c.code for c in active]}")
    classes = [selectors.seams.account_type_code_by_id(v) for v in (plan.account_type_ids or [])]
    print(f"   plan classes: {classes or ['every class']}")
    for customer_class in classes or [None]:
        answer = selectors.base_charge_from_charge_code(
            "water", customer_class=customer_class, size_class="W-34"
        )
        print(f"   live base read, class {customer_class}, schedule names nothing: {answer}")
        answer = selectors.base_charge_from_charge_code(
            "water", customer_class=customer_class, named_code="BASE-W1", size_class="W-34"
        )
        print(f"   live base read, class {customer_class}, schedule names BASE-W1: {answer}")
    _price(best.account_id, start, end, "preview, extra water base code, schedule names nothing")
    bound = models.PlanRateSchedule.objects.get(rate_plan=plan, service=water)
    version = selectors.in_force_version(bound.tariff, end)
    w1 = models.Charge.objects.get(tenant_id=tenant.id, code="BASE-W1")
    models.TariffVersion.objects.filter(pk=version.pk).update(base_charge_code=w1)
    print(f"   (probe shortcut) schedule '{bound.tariff.name}' version from"
          f" {version.effective_from} now NAMES BASE-W1")
    _price(best.account_id, start, end, "preview, schedule names BASE-W1")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
