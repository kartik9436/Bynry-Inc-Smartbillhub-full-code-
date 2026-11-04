#!/usr/bin/env python3
"""Run runbooks 28 and 33 for real, store their runs, and print their ids.

`CR-075` — `US-RBS-043` (runbook 28, *Meters past change-out age or never
tested*) and `US-RBS-044` (runbook 33, *Budget billing re-level*): the half a
browser cannot do.

WHY THIS IS A SCRIPT AND NOT A MANAGEMENT COMMAND
--------------------------------------------------
`G115` would refuse it, correctly. Enrolling an account on budget billing needs
`apps.billing` and `apps.identity`, and **nothing under
`06-backend/apps/runbooks/` may import another module outside `seams/*_seam.py`
and `ports/*_ports.py`** (`BR-RBS-039`). A fixture is not an exception to a
boundary; it lives outside the module instead, exactly as `rbs_q_seed_sync.py`
and `rbs_p_seed_money.py` do.

WHAT IT SEEDS, AND WHY EACH PIECE IS THERE
--------------------------------------------
1. **A run of runbook 28 over the whole fleet.** Nothing is staged: the seeded
   utility already carries 128 meters, of which 3 are past their expected life
   and 128 have no test on file. ⚠ **THE GUARDS ARE NOT LIFTED HERE** — the
   shipped runbook walks 8 meters on this tenant because 119 are sample records,
   and a fixture that quietly widened the scope would walk a screen no clerk
   will ever see. The wider figures are measured separately and are in the lane
   report and on `RB-128`.
2. **Twelve accounts enrolled on budget billing, through `budget_service.enroll`
   — billing's own service.** Nothing is typed into a level: `enroll` computes
   it with ❄️ `GT-24`'s own arithmetic and writes the append-only event and the
   audit row. Half are enrolled on the two months they had at enrolment (the
   older bill, twice — the ordinary case of a level set before this year's usage
   arrived) and half on the current window, so the run finds a MIX rather than a
   uniform answer.
3. **The tenant's own S69 settings lowered**, through tenancy's own
   `save_settings_family`: the averaging window to 2 months and the drift band
   to 5%. ⚠ **THIS IS A TENANT SETTING AND NOT A CODE CHANGE**, and
   `US-BIL-018` TC-2 lowers the same window to 9 for the same reason — to prove
   the twelve is a seed and not a constant. The seeded utility carries two
   cycles of bills, so a twelve-month window would leave every account with too
   little history and the screen would show one outcome instead of four.

⚠ **THE RUNS ARE EXECUTED, NOT INSERTED**, and the reports are composed by
`report()` at close and frozen by `services.close_run`. A fixture that typed a
block list would let the walkthrough pass over a broken runbook —
`DEF-RBS-4291` exactly.

⚠ **WHAT THIS FIXTURE CANNOT DO, SAID OUT LOUD.** **Nothing here can make the
level actually move**: no port applies a budget level (`OQ-RBS-1760`), so every
row of runbook 33 reads *"has to be changed by hand"* and no notice is queued.
That IS the screen this build ships, and the walkthrough's job is to say whether
it reads as a designed answer rather than as a failure.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/smartbillhub" \\
      python3.12 10-scripts/render-checks/rbs_2833_seed.py --tenant brazosbend

It prints `SMOKE_METERS_RUN_ID` and `SMOKE_BUDGET_RUN_ID` for the browser check.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import sys
from decimal import Decimal
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db.models import Count  # noqa: E402

from apps.billing import budget_service  # noqa: E402
from apps.billing import selectors as billing_selectors  # noqa: E402
from apps.billing.models import AccountBudgetStatus, Invoice  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.definitions import budget_relevel, meter_change_out  # noqa: E402
from apps.runbooks.engine import executor  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: How many accounts to enrol. Twelve gives four that move, eight inside the
#: band — enough for the Records table to be a table rather than one row.
ENROL = 12

#: The tenant's own S69 figures, lowered so two cycles of seeded bills are
#: enough to compute a level against. See the module docstring.
WINDOW_MONTHS = 2
CADENCE_MONTHS = 1
DRIFT_PCT = "5"

#: How long ago each account was enrolled. ⚠ **PAST THE CADENCE ON PURPOSE**, so
#: the cadence gate does not swallow every account and hide the drift gate.
ENROLLED_DAYS_AGO = 200


def an_admin(tenant):
    """The owner's id carrying the SYSTEM_ADMIN role.

    ⚠ **THE ROLE LIVES ON THE MEMBERSHIP AND NOT ON THE USER ROW**, so a
    `User` instance handed to `@require_role(SYSTEM_ADMIN)` is refused with
    `AUTH-002` and the message points at permissions rather than at the shape.
    `seed_demo` builds its actor exactly this way and this follows it.
    """
    user = (
        identity_models.User.objects.filter(tenant_id=tenant.id)
        .order_by("created_at")
        .first()
    )
    if user is None:
        raise SystemExit("no user on this tenant — run seed_demo first")
    return SimpleNamespace(id=user.id, pk=user.id, role="system_admin")


def adopt(tenant, definition) -> runbook_models.Runbook:
    """The runbook row `POST /runbooks` would write, from the SHIPPED definition.

    Every field is the definition's own; nothing here invents a name, a kind or
    a category. `template_key` is set because without it
    `accept_template_update` is a silent no-op and `open_run` refuses every run
    for ever once the code moves past the stored version (`BR-RBS-038`).
    """
    runbook = runbook_models.Runbook.objects.filter(
        tenant=tenant, key=definition.key
    ).first()
    if runbook is None:
        print(f"── no runbook row for {definition.key!r}; adding the shipped one")
        runbook = runbook_models.Runbook.objects.create(
            tenant=tenant,
            key=definition.key,
            name=definition.name,
            kind=definition.kind,
            category=definition.category,
            subject_type=definition.subject_type,
            unit_of_work=definition.unit_of_work,
            tags=list(definition.tags),
            origin=runbook_models.ORIGIN_SHIPPED,
            template_key=definition.key,
            trigger_kind=runbook_models.TRIGGER_MANUAL,
            enabled=True,
            cap=100,
        )
    if not runbook.template_key:
        runbook_models.Runbook.objects.filter(pk=runbook.pk).update(
            template_key=definition.key
        )
        runbook.template_key = definition.key
    accepted = services.accept_template_update(runbook)
    if accepted is not None:
        print(f"── accepted the template update for {definition.key!r} → v{accepted.version}")
    return runbook


def run_it(tenant, definition) -> tuple[str, object]:
    """Open, execute, close. The report is composed at close and frozen."""
    runbook = adopt(tenant, definition)
    run = services.open_run(runbook, definition)
    params = {p.name: p.default for p in definition.parameters}
    result = executor.execute(
        definition, tenant_id=tenant.id, run_id=run.pk, params=params
    )
    closed = services.close_run(
        run, result, status=runbook_models.RUN_STATUS_AWAITING_APPROVAL
    )
    return str(closed.pk), result


def enrol_the_programme(tenant, admin) -> int:
    """Twelve accounts on budget billing, through billing's own service.

    ⚠ **IDEMPOTENT BY CHECKING, NOT BY CATCHING.** `enroll` refuses a second
    live status per account by name (`BR-BIL-017`), and catching that refusal
    would make a re-run silently do nothing while reporting success. It asks
    `status_for` first.
    """
    already = AccountBudgetStatus.objects.filter(
        tenant_id=tenant.id, status="enrolled"
    ).count()
    if already >= ENROL:
        print(f"── {already} accounts already on the programme; nothing to enrol")
        return already

    tenancy_services.save_settings_family(
        admin,
        "budget-billing",
        {
            "eligibility_months": WINDOW_MONTHS,
            "relevel_cadence_months": CADENCE_MONTHS,
            "relevel_drift_pct": DRIFT_PCT,
        },
    )
    print(
        f"── S69 set for this fixture: window {WINDOW_MONTHS} months · "
        f"cadence {CADENCE_MONTHS} · drift {DRIFT_PCT}%"
    )

    counts = (
        Invoice.objects.filter(tenant_id=tenant.id, status__in=("issued", "paid"))
        .values("account_id")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    on_date = dt.date.today() - dt.timedelta(days=ENROLLED_DAYS_AGO)
    made = 0
    for row in counts:
        account_id = row["account_id"]
        if budget_service.status_for(account_id) is not None:
            continue
        history = billing_selectors.budget_history_for(account_id, months=WINDOW_MONTHS)
        actuals = history["actuals"]
        if history["months_of_history"] < WINDOW_MONTHS or len(actuals) < 2:
            continue
        # Half enrolled on the two months they had AT ENROLMENT (the older bill,
        # twice) and half on the current window — so the run finds a mix.
        trailing = (
            (Decimal(actuals[-1]), Decimal(actuals[-1]))
            if made % 2 == 0
            else tuple(Decimal(one) for one in actuals[:2])
        )
        status = budget_service.enroll(
            actor=admin,
            account_id=account_id,
            trailing_actuals=trailing,
            months_of_history=history["months_of_history"],
            plan_offers_budget=True,
            currency=history["currency"] or "USD",
            on_date=on_date,
        )
        made += 1
        print(f"   enrolled {status.account.account_no} at level {status.level}")
        if made >= ENROL:
            break
    if made == 0:
        raise SystemExit(
            "nothing could be enrolled — this tenant has no account with two issued "
            "bills. Run seed_demo and load_sample_data first."
        )
    return made


def figures(result, definition) -> dict:
    """What the run produced, read from the FROZEN report rather than recomputed.

    A fixture that recomputed its own figures could disagree with the screen and
    the walkthrough would never know.
    """
    out: dict = {"records": len(result.records), "guarded": len(result.guarded)}
    for block in result.report:
        if block["block"] == "verdict":
            out["verdict"] = block["payload"]["word"]
            out["count"] = block["payload"]["count"]
        if block["block"] == "kpis":
            out["tiles"] = {
                tile["id"]: tile["value"].get("text") or tile["value"].get("amount")
                for tile in block["payload"]["tiles"]
            }
        if block["block"] == "records":
            out["rows"] = block["payload"]["total"]
    out["findings"] = len(result.findings)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        raise SystemExit(f"no tenant with subdomain {args.tenant!r} — run seed_demo first")

    with core_tenancy.tenant_context(tenant.id):
        admin = an_admin(tenant)

        print("\n── runbook 28 · Meters past change-out age or never tested ──")
        meters_run, meters_result = run_it(tenant, meter_change_out.RUNBOOK)
        print("   ", figures(meters_result, meter_change_out.RUNBOOK))

        print("\n── runbook 33 · Budget billing re-level ──")
        enrolled = enrol_the_programme(tenant, admin)
        print(f"   {enrolled} account(s) on the programme")
        budget_run, budget_result = run_it(tenant, budget_relevel.RUNBOOK)
        print("   ", figures(budget_result, budget_relevel.RUNBOOK))

    print()
    print(f"SMOKE_METERS_RUN_ID={meters_run}")
    print(f"SMOKE_BUDGET_RUN_ID={budget_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
