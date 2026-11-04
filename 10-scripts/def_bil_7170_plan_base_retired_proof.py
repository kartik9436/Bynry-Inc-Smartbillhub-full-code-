#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-7170 (critical) — `gather._base_charge_for` read the RETIRED
#          plan base beside the bound charge code and REFUSED the bill when the
#          two differed, so a tenant whose migration left a stale figure had
#          every bill for that service stopped.
# Ruling:  12-governance/02-decision-log.md, 2026-09-28 — PO, verbatim:
#          *"we ahve to take ot from Charge code - whya re you confuse about it
#          - charge code binded in plan - unitl it is part of plan we cannot
#          take amount from charge code - we will never take default value from
#          plan $8.0 - that is retired"*
# Rules:   BR-RAT-088 (the charge code owns the base) · BR-RAT-1025 (the
#          schedule NAMES the code) · BR-BIL-055 (one account stops, the run
#          goes on) · CLAUDE.md hard rule 2 (money 4 dp stored, 2 dp shown).
# Tests:   06-backend/tests/test_def_bil_7170_plan_base_is_retired.py — the
#          SQLite half. This file is the half a fixture cannot reach: it runs
#          the SEEDED tenant on real PostgreSQL 16 and mutates it, which is the
#          mismatched configuration the 2026-08-31 switch was never proved on.
# ───────────────────────────────────────────────────────
"""`DEF-BIL-7170` — THE PLAN'S RETIRED BASE, PROVED ON POSTGRESQL.

Printed from `apps.billing.gather.gather_account`, the path an invoice is
actually built from — never from a screen — on the seeded `brazosbend` tenant.

  CASE 1  the code and the plan AGREE            -> unchanged, bills 8.00
  CASE 2  the code and the plan DISAGREE         -> was REFUSED; now bills the
                                                    code's 8.00 and ignores the
                                                    plan's 11.50
  CASE 3  the schedule NAMES a code that cannot
          price this account                     -> still refuses, BY ITS OWN
                                                    NAME, from rating
  CASE 4  no `is_base` code for the service at
          all, and the plan still carries 8.00   -> was billed from the retired
                                                    column; now REFUSES

⚠ **CASE 4 IS THE HALF THAT IS NOT THE DEFECT — IT IS THE RULING'S SECOND
SENTENCE.** *"we will never take default value from plan $8.0 - that is
retired"*: not a source and not a fallback, **not even when the charge code is
silent**. It is printed here because it is the only change that stops a bill
that used to be produced, and a reader has to be able to see that figure.

Every case restores what it changed, in a `finally`, so the clone is left as it
was found. It WRITES while it runs, so give it a PRIVATE clone.

RUN:

    10-scripts/proof-db.sh clone bil7170
    cd 06-backend
    DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_bil7170?sslmode=disable" \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      .venv/bin/python ../10-scripts/def_bil_7170_plan_base_retired_proof.py

Exits 1 on any FAIL.
"""

from __future__ import annotations

import logging
import os
import pathlib
import sys
from datetime import date
from decimal import Decimal

BACKEND = pathlib.Path(__file__).resolve().parents[1] / "06-backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()
logging.disable(logging.INFO)

from django.utils import timezone  # noqa: E402

from core import tenancy as core_tenancy  # noqa: E402
from apps.billing import gather as G, runs  # noqa: E402
from apps.customers import models as cm  # noqa: E402
from apps.metering import models as mm  # noqa: E402
from apps.rating import models as rm, selectors as rating_selectors  # noqa: E402
from apps.tenancy import models as tm  # noqa: E402

SUBDOMAIN = os.environ.get("SEED_TENANT", "brazosbend")
ACCOUNT_NO = os.environ.get("PROOF_ACCOUNT", "AC-2026-00001")
PERIOD_START = date(2026, 9, 1)
PERIOD_END = date(2026, 9, 30)

_failures: list[str] = []


def check(label: str, got: object, want: object) -> None:
    ok = str(got) == str(want)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    print(f"        got  {got!r}")
    if not ok:
        print(f"        want {want!r}")
        _failures.append(label)


def water_base(account) -> tuple[str | None, str | None]:
    """`(amount, refusal)` — what the money path says water's base is.

    The figure is `TariffConfig.base_charge` AFTER `resolution_switch.apply`,
    because that is what `price_account` multiplies and what reaches the bill.
    """
    readings, _ = runs.readings_for_account(
        account,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        scope_services=None,
        anchor_to_last_billed=True,
    )
    try:
        data = G.gather_account(
            account=account,
            service_date=PERIOD_END,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=30,
            readings=readings,
        )
    except G.GatherProblem as problem:
        return None, str(problem)
    for config in data.tariffs:
        if config.service == "water":
            return str(config.base_charge), None
    return None, "no water tariff on this account"


def main() -> int:
    tenant = tm.Tenant.objects.get(subdomain=SUBDOMAIN)
    with core_tenancy.tenant_context(str(tenant.id)):
        account = cm.Account.objects.get(tenant_id=tenant.id, account_no=ACCOUNT_NO)
        water = tm.Service.objects.get(code="water")
        # ⚠ **THE PLAN AND THE SCHEDULE ARE DERIVED FROM THE ACCOUNT'S UNIT,
        # NEVER NAMED BY HAND.** `BR-CUS-014` — the account derives its plan
        # from the unit — and a first draft of this file hard-coded `RES-STD`
        # while `AC-2026-00001` sits on `SCW-RES`. It then mutated a plan
        # nothing billed from and printed two confident PASSes over a case it
        # had not actually built (hard-won law 7: ask what would make a check
        # pass WRONGLY).
        unit = mm.Unit.objects.get(id=account.unit_id)
        plan = rm.RatePlan.objects.get(id=unit.rate_plan_id)
        plan_service = rm.PlanService.objects.get(
            tenant_id=tenant.id, service_id=water.id, rate_plan_id=plan.id
        )
        tariff = rm.Tariff.objects.get(
            id=rm.PlanRateSchedule.objects.get(
                tenant_id=tenant.id, rate_plan_id=plan.id, service_id=water.id
            ).tariff_id
        )
        base_w = rm.Charge.objects.get(tenant_id=tenant.id, code="BASE-W")
        base_w_com = rm.Charge.objects.get(tenant_id=tenant.id, code="BASE-W-COM")
        version = rating_selectors.in_force_version(tariff, PERIOD_END)

        print("── THE CONFIGURATION ────────────────────────────────────────")
        print(f"  tenant            {SUBDOMAIN}")
        print(f"  account           {ACCOUNT_NO}  (customer type: residential)")
        print(f"  plan              {plan.code}, water  (from the unit, BR-CUS-014)")
        print(f"  rate schedule     {tariff.name}")
        print(f"  charge code       BASE-W      {base_w.amount}  residential")
        print(f"  charge code       BASE-W-COM  {base_w_com.amount}  commercial")
        print(f"  the plan's own RETIRED column says  {plan_service.base_charge}")
        print()

        # ── CASE 1 · THEY AGREE ─────────────────────────────────────────────
        print("── CASE 1 · the charge code and the plan AGREE ──────────────")
        amount, refusal = water_base(account)
        print(f"  the plan says 8.0000, BASE-W says 8.0000")
        check("water base on the bill", amount or refusal, "8.000000")
        print()

        # ── CASE 2 · THEY DISAGREE ──────────────────────────────────────────
        print("── CASE 2 · the plan carries a STALE 11.50, the code says 8.00 ──")
        before = plan_service.base_charge
        try:
            rm.PlanService.objects.filter(pk=plan_service.pk).update(
                base_charge=Decimal("11.5000")
            )
            amount, refusal = water_base(account)
            check("water base on the bill", amount or refusal, "8.000000")
        finally:
            rm.PlanService.objects.filter(pk=plan_service.pk).update(base_charge=before)
        print()

        # ── CASE 3 · THE NAMED CODE CANNOT PRICE THIS ACCOUNT ───────────────
        print("── CASE 3 · the schedule NAMES BASE-W-COM and this account is residential ──")
        named_before = version.base_charge_code_id
        try:
            rm.TariffVersion.objects.filter(pk=version.pk).update(
                base_charge_code_id=base_w_com.id
            )
            amount, refusal = water_base(account)
            check(
                "the clerk reads",
                amount or refusal,
                "BASE-W-COM cannot price water here. Change it on the rate schedule.",
            )
        finally:
            rm.TariffVersion.objects.filter(pk=version.pk).update(
                base_charge_code_id=named_before
            )
        print()

        # ── CASE 4 · NO BASE CODE AT ALL, PLAN STILL CARRIES 8.00 ───────────
        print("── CASE 4 · every water base code retired; the plan still says 8.0000 ──")
        try:
            rm.Charge.objects.filter(
                pk__in=[base_w.pk, base_w_com.pk]
            ).update(deleted_at=timezone.now())
            amount, refusal = water_base(account)
            check(
                "the clerk reads",
                amount or refusal,
                "No base charge for water. Declare one on Charge codes.",
            )
        finally:
            rm.Charge.objects.filter(pk__in=[base_w.pk, base_w_com.pk]).update(
                deleted_at=None
            )
        print()

        # ── THE CLONE IS AS IT WAS FOUND ────────────────────────────────────
        print("── RESTORED ─────────────────────────────────────────────────")
        amount, refusal = water_base(account)
        check("water base on the bill, after every restore", amount or refusal, "8.000000")

    print()
    if _failures:
        print(f"FAILED: {len(_failures)} — {', '.join(_failures)}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
