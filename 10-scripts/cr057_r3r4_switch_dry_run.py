#!/usr/bin/env python
# ── Trace ──────────────────────────────────────────────
# Rules:  BR-BIL-873 (R3 and R4 switch TOGETHER — one base charge from the
#         pair) · BR-BIL-872 (a switched rule's refusal refuses the ACCOUNT,
#         with no fallback) · BR-RAT-1010 (the charge code states the size) ·
#         BR-RAT-088 (the charge code states the base amount) · BR-RAT-120
#         (AMENDED 2026-09-01 — the sequencing clause is spent and the chain
#         now HAS a production caller: the shipped default serves R3,R4)
# Defects: DEF-2878 (R3's comparison compared one value with itself, which is
#         why coverage is checked rather than compared)
# CRs:    CR-052 (the six-step cutover) · CR-057 (this check)
# ───────────────────────────────────────────────────────
"""**WOULD SWITCHING R3 + R4 ON CHANGE ANY BILL?** Asked by switching them on.

⚠ **THIS IS THE LAST MEASUREMENT BEFORE THE PAIR CAN BE SWITCHED, AND IT IS A
DIFFERENT QUESTION FROM THE COVERAGE CHECK.**
`cr052_r1r7_shadow_measure.py --tenant all` answers *will R3 REFUSE anybody* —
it reads configuration and needs no bill. This answers *and if it does not
refuse, is the figure the same* — which needs the fork actually turned on.

    coverage check   ->  R3 resolves for every (service · size) carried
    THIS check       ->  ... and the base charge that comes out is the one the
                         bill run was going to use anyway, to the cent

`resolution_switch.apply()` is called with `BILLING_RESOLUTION_STEPS='R3,R4'`
for every ready account of every utility, and the `base_charge` it returns is
compared with the one `gather` had already resolved. **Nothing is written**:
the whole pass runs inside a transaction this script rolls back, and the
setting is overridden for this process only — no deployment is changed and
`SERVED_BY_CHAIN_DEFAULT` stays empty, which is a PO ruling and a deployment
act in that order (`BR-RAT-120`).

**HOW TO READ A REFUSAL HERE.** `BR-BIL-872` makes a switched rule's refusal
refuse the ACCOUNT — no fallback, no partial bill. So a refusal in this table
is not a note, it is *this account stops being billable on the day the pair is
switched on*, and its sentence is the thing to act on.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402
from django.test import override_settings  # noqa: E402

from apps.billing import resolution_switch  # noqa: E402


def _deployment_serves_the_pair() -> bool:
    """Is the pair on for THIS deployment, as opposed to for this process?

    The measurement above runs inside `override_settings`, so asking the switch
    during it always answers yes. The verdict has to describe the DEPLOYMENT, so
    it reads the setting directly instead.
    """
    named = {
        part.strip().upper()
        for part in str(settings.BILLING_RESOLUTION_STEPS).replace(",", " ").split()
    }
    return {"R3", "R4"} <= named


class _Rollback(Exception):
    """Raised at the end of the pass so the transaction unwinds. Nothing here
    writes, and the rollback proves it rather than a docstring claiming it."""
from core import tenancy as core_tenancy  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cr052_r1r7_shadow_measure as harness  # noqa: E402


def _money(value) -> str:
    return "—" if value is None else f"${value:,.2f}"


def _one_tenant(tenant, cycle_code: str | None, sabotage: bool = False) -> dict:
    """Every ready account of every cycle, switched, compared."""
    from apps.billing import runs, shadow_report

    rows = {
        "attempted": 0,
        "same": 0,
        "moved": [],
        "refused": [],
        "no_base": 0,
        "by_service": Counter(),
        "sabotaged": "",
    }
    cycles = list(metering_models.Cycle.objects.order_by("code"))
    if cycle_code:
        cycles = [c for c in cycles if c.code == cycle_code]
    for cycle in cycles:
        period_start, period_end, service_date = harness._period_for(cycle)
        try:
            prepared = runs.prepare_run(
                cycle_id=cycle.id,
                period_start=period_start,
                period_end=period_end,
                service_date=service_date,
            )
        except Exception as exc:  # noqa: BLE001 — a cycle that cannot prepare is not this check's finding
            rows.setdefault("cycles_skipped", []).append(f"{cycle.code}: {exc}")
            continue
        accounts = shadow_report._accounts_by_id(prepared)
        for data in prepared.ready:
            account = accounts.get(str(data.account_id))
            if account is None:
                continue
            rows["attempted"] += 1
            live = {
                getattr(config, "service", ""): getattr(config, "base_charge", None)
                for config in data.tariffs
            }
            if sabotage and not rows["sabotaged"]:
                # ONE account, ONE service, in memory, after `prepare_run` and
                # before the comparison — the same shape every `--sabotage` in
                # the shadow harness takes. No row is written and no pricing
                # code is touched; the figure the LIVE side claims is moved, so
                # the ruled side must disagree with it by exactly $4.00.
                for service, was in live.items():
                    if was is not None:
                        live[service] = was + Decimal("4.00")
                        rows["sabotaged"] = f"{data.account_no} {service}: live {_money(was)} -> {_money(live[service])}"
                        break
            try:
                switched = resolution_switch.apply(
                    data, account=account, service_date=service_date
                )
            except resolution_switch.RuledPathRefused as refusal:
                rows["refused"].append((data.account_no, str(refusal)))
                continue
            moved = False
            for config in switched.tariffs:
                service = getattr(config, "service", "")
                was = live.get(service)
                now = getattr(config, "base_charge", None)
                if was is None and now is None:
                    rows["no_base"] += 1
                    continue
                if was != now:
                    moved = True
                    rows["moved"].append((data.account_no, service, was, now))
                else:
                    rows["by_service"][service] += 1
            if not moved:
                rows["same"] += 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="all")
    parser.add_argument(
        "--steps",
        default="R3,R4",
        help=(
            "which rules to serve from the chain for this dry run. Default is the "
            "ruled pair. `R3` and `R4` may only appear together (BR-BIL-873). A step "
            "with no fork (R3b, R6) is REFUSED by `steps_served_by_chain` rather than "
            "ignored — BR-BIL-874, because a switch that is accepted and does nothing "
            "would be reported as a rule that has been live for a week and never ran."
        ),
    )
    parser.add_argument("--cycle", default=None)
    parser.add_argument(
        "--sabotage",
        action="store_true",
        help=(
            "move ONE account's live base charge by $4.00 in memory before the "
            "comparison, so the verdict must report a moved figure. A check that "
            "has only ever printed one answer is not a check (hard-won law 7)."
        ),
    )
    args = parser.parse_args()

    # The switch is turned on FOR THIS PROCESS ONLY. `steps_served_by_chain`
    # re-reads the setting on every call by design, so an override here reaches
    # every `apply()` below without touching any deployment.
    # ⚠ **READ BEFORE THE OVERRIDE, AND THAT IS THE WHOLE FIX (`DEF-2966`).**
    # The banner below calls this "the DEPLOYMENT default". Read INSIDE the
    # `override_settings` block it is not the deployment's value at all — it is
    # the value this dry run just imposed, so a run with `--steps R1,R2,R3,R4,R5,R7`
    # printed *"the DEPLOYMENT default is 'R1,R2,R3,R4,R5,R7' — … already price
    # real bills here"* while the shipped default was `R3,R4` and four of those
    # six were switched on nowhere. It was very nearly reported to the PO as
    # four rules having gone live.
    #
    # The irony is on the record deliberately: the comment three lines down was
    # written to fix this exact class of fault and then committed it, one
    # variable over. A report that states what it did not read is a check that
    # cannot fail (`DEF-182`) — and reading a setting through a lens that
    # changes it is the same thing wearing a different hat.
    deployment_steps = settings.BILLING_RESOLUTION_STEPS
    deployment_served = sorted(resolution_switch.steps_served_by_chain())

    with override_settings(BILLING_RESOLUTION_STEPS=args.steps):
        served = resolution_switch.steps_served_by_chain()
        wanted = {p.strip() for p in args.steps.replace(",", " ").split() if p.strip()}
        if served != frozenset(wanted):
            print(f"the switch did not take: asked {sorted(wanted)}, served {sorted(served)}")
            return 2
        print(f"SWITCHED ON FOR THIS PROCESS ONLY — {', '.join(sorted(served))}")
        # ⚠ **DERIVED, NEVER ASSERTED (`CR-057`, 2026-09-01).** This line used to
        # read "the deployment default is unchanged and still empty: {…}" and it
        # printed the deployment's value beside the word "empty" — so on the day
        # the pair was switched on it printed `still empty: 'R3,R4'`, a sentence
        # contradicted by its own variable. A report that states what it did not
        # read is the same class of fault as a check that cannot fail (`DEF-182`).
        print(f"  the DEPLOYMENT default is {deployment_steps!r} — "
              + (f"{', '.join(deployment_served)} already price real bills here"
                 if deployment_served else
                 "nothing is served by the chain here, so this is a pure what-if"))
        _extra = sorted(set(served) - set(deployment_served))
        if _extra:
            print(f"  so {', '.join(_extra)} is/are a WHAT-IF in this run and price "
                  "no real bill on this deployment.")
        print()
        try:
            with transaction.atomic():
                total = {"attempted": 0, "same": 0, "moved": 0, "refused": 0}
                for tenant in harness._tenants_to_measure(args.tenant):
                    with core_tenancy.tenant_context(str(tenant.id)):
                        rows = _one_tenant(tenant, args.cycle, sabotage=args.sabotage)
                    print(f"{tenant.name} ({tenant.subdomain})")
                    print(f"  {rows['attempted']} account(s) put through the switched fork")
                    print(f"  {rows['same']} billed the SAME base charge as the live path")
                    print(f"  {len(rows['moved'])} base charge(s) MOVED")
                    for account_no, service, was, now in rows["moved"][:10]:
                        print(f"    {account_no}  {service}: live {_money(was)} -> "
                              f"ruled {_money(now)}")
                    print(f"  {len(rows['refused'])} account(s) the ruled path REFUSED "
                          "(BR-BIL-872: that account would stop being billable)")
                    for account_no, sentence in rows["refused"][:5]:
                        print(f"    {account_no}: {sentence}")
                    if rows["sabotaged"]:
                        print(f"  SABOTAGE IN FORCE — {rows['sabotaged']}")
                    for note in rows.get("cycles_skipped", [])[:3]:
                        print(f"  cycle not prepared — {note}")
                    print()
                    total["attempted"] += rows["attempted"]
                    total["same"] += rows["same"]
                    total["moved"] += len(rows["moved"])
                    total["refused"] += len(rows["refused"])
                raise _Rollback()
        except _Rollback:
            pass

    print("THE VERDICT")
    print(f"  {total['attempted']} account(s) · {total['same']} unchanged · "
          f"{total['moved']} moved · {total['refused']} refused")
    if total["moved"] == 0 and total["refused"] == 0 and total["attempted"]:
        # ⚠ **NAME WHAT WAS SERVED, NOT WHAT THIS SCRIPT WAS BORN FOR
        # (`DEF-2966`).** This sentence was hardcoded to "R3 + R4", so a run
        # serving all six forkable rules printed a clean verdict about a PAIR
        # while having measured six — the reader's takeaway ("that is safe")
        # attaches to the wrong set of rules.
        print(f"  Serving {', '.join(sorted(served))} changes NO bill and refuses NO "
              "account on this database.")
        if _deployment_serves_the_pair():
            print("  The pair is ALREADY ON here (PO ruling 2026-09-01), so this is not a")
            print("  release gate — it is the standing check that this deployment's data")
            print("  still agrees with the rules now pricing it. Rollback, one line and no")
            print("  release: SBH_BILLING_RESOLUTION_STEPS= (empty).")
        else:
            print("  The pair is NOT on for this deployment. The shipped default serves it,")
            print("  so something here has turned it off; turning it back on is a deployment")
            print("  act, and this script does not make one.")
        return 0
    print("  NOT clear to switch. Every moved figure and every refusal above is a bill")
    print("  that would change or stop on the day the pair is switched on.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
