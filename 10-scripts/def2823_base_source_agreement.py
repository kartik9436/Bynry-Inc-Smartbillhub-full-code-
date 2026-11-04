#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2823 — R3 reads its per-size base from `tariff_versions
#          .base_charge`, the column BR-RAT-088 retired and the S11 wizard has
#          had no control for since, so the ruled chain refuses every
#          connection size of every tenant that has done what the ruling told
#          it to do. Fixing it means MOVING WHERE THE BASE IS READ FROM, on
#          both paths, and "moving where money comes from" is a claim about
#          money — hard-won law 1 forbids leaving that in a comment.
# Rules:   BR-RAT-088 (PO 2026-08-20 — the CHARGE CODE owns the base amount; a
#          plan displays it, never defines it) · BR-RAT-012 / BR-RAT-027 (both
#          SUPERSEDED by it — the plan-owns-the-base rules the live path still
#          implements) · PO 2026-08-19 ruling 1, verbatim *"no plan cannot
#          override prices"* (so `plan_charge_rules.amount_override` is NOT a
#          third source) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2
#          (money DISPLAYS at 2dp; nothing here re-rounds one)
# Impacts: nothing. It writes no row — `prepare_run` writes nothing by its own
#          contract and the whole pass is additionally rolled back.
# ───────────────────────────────────────────────────────
"""DO THE TWO BASE-CHARGE SOURCES AGREE, ACCOUNT BY ACCOUNT AND PLAN BY PLAN?

This is the safety argument for `DEF-2823`, and it is the WHOLE of it: where
the plan and the charge code state the same figure, switching which one the
code reads **cannot move a bill**. Where they differ, or where the charge code
states nothing, switching moves money and the difference must be reported and
ruled on rather than silently preferred — which is exactly how `DEF-154` put
`$0.00` on every bill this product produced.

⚠ **IT PRINTS EVERY PAIR, NOT A COUNT.** A count can be satisfied by two
errors that cancel. The counts are printed too, at the end, because that is the
figure a person quotes.

TWO POPULATIONS, AND THE SECOND IS THE ONE THAT FINDS THINGS
------------------------------------------------------------
**(1) THE RUN.** Every account `prepare_run` makes ready, per service: the
figure the LIVE path resolves today (`TariffConfig.base_charge`, sourced from
`plan_services.base_charge` through `gather._base_charge_for`) beside the
figure the CHARGE CODE states for that account's service, customer class and
connection size — resolved through the chain's OWN R4 narrowing
(`resolve_charge_codes` → `resolve_base_charge`), never a hand-rolled query,
so the amount compared is the one that would actually bill.

**(2) THE CONFIGURATION.** Every `(plan, service)` row the tenant has, whether
or not any account in this cycle uses it. An account population can be silent
about a plan nobody is on today and loud about it next month. The run's
accounts are all on ONE plan/service pair on the shipped fixture, so
population (1) alone would report total agreement over a configuration that
disagrees by `$168.00` on another plan.

WHAT THE TRAVERSAL IS, AND WHY `plan_charge_rules` IS NOT IT
-------------------------------------------------------------
The PO's own sentence is *"plan → charges code → base scharges"*. The plan is
the BINDING and this script follows it exactly: the account resolves to a plan
(R1), the plan lists its SERVICES, and each service's base is the charge code
that DECLARES itself that service's base (`charges.is_base`, BR-RAT-088 —
never inferred from the code string), narrowed by the account's customer class
and its connection size.

`plan_charge_rules` is the plan's binding for every OTHER charge code, and the
repo already says so in its own words: `rating.selectors.billable_charge_codes`
excludes `is_base` rows by name — *"the base charge already reaches the bill as
the service's base through R4 … the base has its own route"* — and
`PlanWizard.servicesMissingBaseCharge` finds a service's base code by
`is_base` + `service` over the tenant's catalogue rather than through any
binding row. This script reports the measured state of that table too, so the
reading is evidence and not an assertion.

`plan_charge_rules.amount_override` is NOT consulted, and that is a signed
ruling rather than an omission: PO 2026-08-19 ruling 1, verbatim *"no plan
cannot override prices"* — *"no per-plan amount override"*, in the ruling's own
words. The column survives so no stored figure is destroyed.

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=postgres://…/<db>?sslmode=disable \
    JOBS_EAGER=false \
    python3 10-scripts/def2823_base_source_agreement.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402

settings.DEBUG = False

from apps.billing import resolution_shadow as shadow  # noqa: E402
from apps.billing import runs  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.rating import models as rating_models  # noqa: E402
from apps.rating import resolution, resolution_catalogue  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
SERVICE_DATE = date(2026, 7, 1)

AGREE = "agree"
DISAGREE = "disagree"
CODE_SILENT = "charge_code_states_nothing"
CODE_REFUSED = "charge_code_refused"
PLAN_SILENT = "plan_states_nothing"


def _money(amount: Decimal | None) -> str:
    """CLAUDE.md hard rule 2 — money DISPLAYS at 2 decimals, and a figure that
    is NOT exact at 2dp is printed unrounded and named rather than quietly
    rounded into agreement."""
    if amount is None:
        return "—"
    value = Decimal(str(amount))
    two = value.quantize(Decimal("0.01"))
    return f"${two}" if two == value else f"${value}(NOT-2dp)"


def _dec(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


class _Done(Exception):
    def __init__(self, payload: dict[str, Any]):
        super().__init__("done")
        self.payload = payload


def _code_base_for_account(data: Any, account: Any) -> tuple[Decimal | None, str, dict[str, Any]]:
    """The CHARGE CODE's answer for one account, through the chain's own R4.

    Returns `(amount_by_service, note, detail)`. The narrowing is
    `resolve_charge_codes` verbatim — service, customer class, the recurrence
    gate and the connection size — so what comes back is what would bill, not
    what a catalogue row happens to hold.
    """
    inputs = shadow.adapt(data, account=account)
    if inputs.blocked_reason is not None:
        return {}, f"inputs_blocked:{inputs.blocked_reason}", {}
    catalogue = resolution_catalogue.build_catalogue(
        plan_id=inputs.plan_id,
        service_date=SERVICE_DATE,
        unmetered_services=inputs.unmetered_services,
    )
    sizes = {meter.service: meter.connection_size for meter in inputs.meters}
    for counts in inputs.asset_counts:
        sizes.setdefault(counts.service, getattr(counts, "size_class", None) or "")
    services = tuple(sizes)
    try:
        resolved_codes = resolution.resolve_charge_codes(catalogue, inputs.account, services, sizes)
    except Exception as refusal:  # the chain's own refusal, carried whole
        return {}, f"R4_refused:{type(refusal).__name__}:{refusal}", {}
    answer: dict[str, Decimal | None] = {}
    for service in services:
        answer[service] = resolution.resolve_base_charge(resolved_codes, service)
    return answer, "", {"sizes": sizes, "class": inputs.account.customer_class}


def _run_population() -> dict[str, Any]:
    lines: list[str] = []
    verdicts: Counter[str] = Counter()
    accounts_seen = 0
    for cycle in metering_models.Cycle.objects.order_by("code"):
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        for data in sorted(prepared.ready, key=lambda d: d.account_no):
            accounts_seen += 1
            account = customer_models.Account.objects.filter(id=data.account_id).first()
            if account is None:
                lines.append(f"{data.account_no}  (account row not readable)")
                verdicts["account_not_readable"] += 1
                continue
            by_service, note, detail = _code_base_for_account(data, account)
            for config in sorted(data.tariffs, key=lambda c: c.service):
                plan_amount = _dec(config.base_charge)
                if note:
                    lines.append(
                        f"{data.account_no}  {config.service:<10} plan {_money(plan_amount):>9}  "
                        f"code    n/a   {CODE_REFUSED}  {note}"
                    )
                    verdicts[CODE_REFUSED] += 1
                    continue
                code_amount = by_service.get(config.service)
                size = (detail.get("sizes") or {}).get(config.service, "—")
                klass = detail.get("class")
                if plan_amount is None and code_amount is None:
                    verdict = PLAN_SILENT
                elif code_amount is None:
                    verdict = CODE_SILENT
                elif plan_amount is None:
                    verdict = PLAN_SILENT
                elif plan_amount == code_amount:
                    verdict = AGREE
                else:
                    verdict = DISAGREE
                verdicts[verdict] += 1
                lines.append(
                    f"{data.account_no}  {config.service:<10} plan {_money(plan_amount):>9}  "
                    f"code {_money(code_amount):>9}  {verdict:<26} "
                    f"size={size} class={klass}"
                )
    return {"lines": lines, "verdicts": verdicts, "accounts": accounts_seen}


def _configuration_population() -> dict[str, Any]:
    """Every `(plan, service)` the tenant configures, account population aside.

    ⚠ **THE PLAN'S CLASS IS A PROXY AND IT IS OFTEN ABSENT — SO THIS COMPARES
    AGAINST EVERY CLASS THE SERVICE IS PRICED FOR.** `rate_plans
    .account_type_id` is NULL on every seeded plan (`DEF-452`), so narrowing by
    the PLAN's class would report *"the charge code states nothing"* for a
    service that is priced perfectly well — the base is narrowed at bill time
    by the ACCOUNT's class (`BR-RAT-108`), not the plan's.

    So: where the plan names a class, that class decides. Where it does not,
    the plan's figure AGREES if any `is_base` code for that service states it,
    and the classes are named beside it so a reader can see which account would
    resolve which figure. A plan figure NO code states is a real disagreement
    either way — that is the `$180.00` / `$12.00` electric gap this script was
    written to find.
    """
    lines: list[str] = []
    verdicts: Counter[str] = Counter()
    class_by_id: dict[Any, str] = {}
    for row in customer_models.AccountType.objects.all():
        class_by_id[str(row.id)] = row.code
    codes = list(
        rating_models.Charge.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), is_base=True, deleted_at__isnull=True
        ).select_related("service")
    )
    for link in (
        rating_models.PlanService.objects.filter(tenant_id=core_tenancy.current_tenant_id())
        .select_related("rate_plan", "service")
        .order_by("rate_plan__code", "service__code")
    ):
        plan = link.rate_plan
        service = link.service.code
        plan_class = class_by_id.get(str(plan.account_type_id)) if plan.account_type_id else None
        matches = [
            code
            for code in codes
            if code.service_id
            and code.service.code == service
            and (
                # The plan names no class (DEF-452 — none of them do), so every
                # code that prices this service is a candidate and the ACCOUNT's
                # class picks one at bill time.
                plan_class is None
                or not (code.applies_to_customer_classes or [])
                or plan_class in code.applies_to_customer_classes
            )
        ]
        plan_amount = _dec(link.base_charge)
        stated: list[tuple[str, Decimal | None, str]] = []
        for code in matches:
            sized = list(
                rating_models.ChargeCodeAmount.objects.filter(
                    tenant_id=core_tenancy.current_tenant_id(), charge_id=code.id
                ).order_by("size_class")
            )
            scope = ",".join(code.applies_to_customer_classes or []) or "every class"
            if sized:
                for row in sized:
                    stated.append(
                        (f"{code.code}[{scope}]", _dec(row.amount), f"size {row.size_class}")
                    )
            else:
                stated.append((f"{code.code}[{scope}]", _dec(code.amount), "flat"))
        if not stated:
            verdicts[CODE_SILENT] += 1
            lines.append(
                f"{plan.code:<9} {service:<10} plan {_money(plan_amount):>9}  code       —  "
                f"{CODE_SILENT:<26} plan_class={plan_class} candidates=[]"
            )
            continue
        figures = ", ".join(
            f"{label} {_money(amount)} ({shape})" for label, amount, shape in stated
        )
        if plan_amount is None:
            verdict = PLAN_SILENT
        elif plan_amount in {amount for _label, amount, _shape in stated}:
            verdict = AGREE
        else:
            verdict = DISAGREE
        verdicts[verdict] += 1
        lines.append(
            f"{plan.code:<9} {service:<10} plan {_money(plan_amount):>9}  "
            f"{verdict:<26} plan_class={plan_class}  codes: {figures}"
        )
    return {"lines": lines, "verdicts": verdicts}


def _binding_population() -> list[str]:
    """What `plan_charge_rules` actually binds — the evidence for the reading
    that the base does NOT travel through it."""
    out: list[str] = []
    for rule in (
        rating_models.PlanChargeRule.objects.filter(tenant_id=core_tenancy.current_tenant_id())
        .select_related("rate_plan", "charge")
        .order_by("rate_plan__code", "charge__code")
    ):
        out.append(
            f"{rule.rate_plan.code:<9} binds {rule.charge.code:<10} "
            f"is_base={rule.charge.is_base}  amount_override="
            f"{_money(_dec(rule.amount_override))}  recurrence={rule.recurrence}"
        )
    return out


def main() -> int:
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        raise SystemExit("no tenant on this database")

    try:
        with transaction.atomic():
            with core_tenancy.tenant_context(tenant.id):
                payload = {
                    "run": _run_population(),
                    "config": _configuration_population(),
                    "bindings": _binding_population(),
                }
            raise _Done(payload)
    except _Done as done:
        payload = done.payload

    print("═" * 78)
    print("DEF-2823 · DO THE PLAN AND THE CHARGE CODE STATE THE SAME BASE?")
    print("BR-RAT-088: the charge code owns the base; a plan displays it, never defines it")
    print("═" * 78)
    print()
    print("(1) THE RUN — every ready account, every service, both figures")
    print("─" * 78)
    for line in payload["run"]["lines"]:
        print(line)
    print("─" * 78)
    run_verdicts = payload["run"]["verdicts"]
    for verdict, count in sorted(run_verdicts.items()):
        print(f"  {verdict:<30} {count}")
    print(f"  {'accounts in the ready set':<30} {payload['run']['accounts']}")
    print()
    print("(2) THE CONFIGURATION — every (plan, service) the tenant has")
    print("─" * 78)
    for line in payload["config"]["lines"]:
        print(line)
    print("─" * 78)
    for verdict, count in sorted(payload["config"]["verdicts"].items()):
        print(f"  {verdict:<30} {count}")
    print()
    print("(3) plan_charge_rules — what the plan's charge BINDING actually holds")
    print("─" * 78)
    for line in payload["bindings"]:
        print(line)
    base_bindings = sum(1 for line in payload["bindings"] if "is_base=True" in line)
    print("─" * 78)
    print(f"  {'binding rows':<30} {len(payload['bindings'])}")
    print(f"  {'of which is_base':<30} {base_bindings}")
    print()
    disagreements = run_verdicts.get(DISAGREE, 0) + payload["config"]["verdicts"].get(DISAGREE, 0)
    print(f"TOTAL DISAGREEMENTS ACROSS BOTH POPULATIONS: {disagreements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2823 · BR-RAT-088 · PO ruling 2026-08-31 (*"just correct the
#         logic and we are good to go"* — nothing is live, so this measures a
#         fixture and never a customer's history)
# generated: 2026-08-31 by the DEF-2823 lane (claude)
# gates: reads only; `prepare_run` writes nothing and the pass is rolled back.
# ──────────────────────────────────────────────────────────
