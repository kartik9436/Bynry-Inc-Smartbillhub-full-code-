# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 after close (lane PLAN-TAIL) — DEF-RAT-9519.
# Proves:  the combined tax figure a plan shows equals what a REAL bill on it
#          charges, on PostgreSQL 16: a Residential plan (2.00 %) and a
#          Commercial one (8.25 %), each with TX State Utility Tax (commercial
#          and industrial only) and Bexar County attached.
# ───────────────────────────────────────────────────────
"""cr167_plantail_taxes_pg — run after `cr167_planwalk_world.py setup`.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=false python ../10-scripts/cr167_plantail_taxes_pg.py

Creates `PT-RESD` and `PT-COMD` through `plan_writes.create` (the New plan
form's write), puts the world's walk units on them (`assign`), runs and issues
the November 2026 cycle, then prints, per plan, what the plan read says
(*combined*, each tax's `reaches_plan_classes`) beside each bill's tax lines and
the rate they come to. Exits 1 if any bill's rate differs from the plan's
combined figure.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("world", HERE / "cr167_planwalk_world.py")
world = importlib.util.module_from_spec(spec)
spec.loader.exec_module(world)  # type: ignore[union-attr]

from django.db import transaction  # noqa: E402

PLANS = {
    "PT-RESD": ("residential", "Sample — Residential water (inclining tiers)"),
    "PT-COMD": ("commercial", "Sample — Commercial water (flat)"),
}


def make_plans() -> None:
    from apps.rating import models as rm
    from apps.rating import plan_reads, plan_writes, seams

    tenant, actor, ctx = world._ctx()
    with ctx(), transaction.atomic():
        for code, (klass, water) in PLANS.items():
            class_id = str(seams.account_type_id_by_code(klass))
            options = plan_reads.form_options(classes=[class_id])
            # The world's accounts take the plan's deposit as REQUIRED, so the
            # plan asks one (DEP-SIZE for homes, DEPOSIT for the café).
            wanted = "DEP-SIZE" if klass == "residential" else "DEPOSIT"
            deposits = [row["ref"]["id"] for row in options["deposit_codes"] if row["ref"]["code"] == wanted]
            if rm.RatePlan.objects.filter(tenant=tenant, code=code).exists():
                print("exists", code)
                continue
            by_name = {row["ref"]["name"]: row["ref"]["id"] for row in options["schedules"]}
            taxes = [row["ref"]["id"] for row in options["taxes"]]
            plan_writes.create(actor, {
                "details": {"name": f"Plan tail · {klass} · {code}", "code": code, "customer_classes": [class_id]},
                "services": [
                    {"service": "water", "schedule": by_name[water], "surcharged": False},
                    {"service": "sewer", "schedule": by_name["Sample — Sewer (% of water)"], "surcharged": False},
                ],
                "charge_codes": [], "taxes": [{"tax": one} for one in taxes], "deposits": deposits, "discounts": [],
                "minimum_bill_amount": "0.00", "effective_from": "2026-11-01", "publish": True,
            })
            print("created", code, "taxes", [row["ref"]["name"] for row in options["taxes"]])


def compare() -> int:
    from apps.billing import models as bm
    from apps.customers import models as cm
    from apps.rating import models as rm
    from apps.rating import plan_reads

    tenant, _actor, ctx = world._ctx()
    bad = 0
    with ctx():
        for code in PLANS:
            plan = rm.RatePlan.objects.get(tenant=tenant, code=code)
            sections = plan_reads.plan_sections(plan.id)
            combined = sections["combined_tax_rate_display"]
            print(f"PLAN {code}: combined {combined} · " + ", ".join(
                f"{row['ref']['name']} {row['rate_display']} reaches={row['reaches_plan_classes']}" for row in sections["taxes"]))
            for acct in cm.Account.objects.filter(tenant=tenant, unit__rate_plan_id=plan.id).order_by("account_no"):
                for inv in bm.Invoice.objects.filter(account=acct).order_by("period_end"):
                    lines = list(bm.InvoiceLine.objects.filter(invoice=inv))
                    taxed = [line for line in lines if line.kind == "tax"]
                    base = sum((Decimal(line.amount) for line in lines if line.kind != "tax" and getattr(line, "taxable", False)), Decimal("0"))
                    tax = sum((Decimal(line.amount) for line in taxed), Decimal("0"))
                    rate = (tax / base * 100).quantize(Decimal("0.01"), ROUND_HALF_UP) if base else None
                    print(f"  BILL {acct.account_no} {inv.invoice_no} {inv.status} taxable {base:.2f} tax {tax:.2f} "
                          f"= {rate}% · lines " + "; ".join(f"{line.description} {Decimal(line.amount):.2f}" for line in taxed))
                    if combined is None or rate is None or f"{rate}%" != combined:
                        bad += 1
                        print("    ✗ differs from the plan's combined figure")
                    else:
                        print("    ✓ equals the plan's combined figure")
    return bad


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("all", "plans"):
        make_plans()
        for code in PLANS:
            world.assign(code)
    if step in ("all", "run"):
        world.run("2026-11-01", "2026-11-30")
    if step in ("all", "compare"):
        sys.exit(1 if compare() else 0)
