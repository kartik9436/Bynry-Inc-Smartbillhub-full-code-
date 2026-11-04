#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-6759 — a counting capacity service on the plan with no
#          service point on the unit refuses the WHOLE bill.
# Ruling:  PO 2026-09-25, option (b): *"Bill it at $0.00, and say so"*.
# Rules:   BR-BIL-300 edge 2 · BR-MET-108 · OQ-670 · CLAUDE.md law 14
#          (measured on real PostgreSQL, never the SQLite default).
# ───────────────────────────────────────────────────────
"""MEASURE ALL 75 ACCOUNTS ON A WATER + SEWER + FIRE TENANT, BEFORE AND AFTER.

    DATABASE_URL=postgres://... python3.12 \
        10-scripts/def_bil_6759_zero_line_measure.py --label before

It provisions (idempotently) one tenant that sells water, sewer and fire,
prepares a real bill run over every cycle, and writes ONE JSON record per
account: whether it priced or was refused, the refusal's reason code, and —
for a priced account — every line's description and amount to FOUR DECIMALS.

**THE POINT IS THE DIFF, NOT THE RUN.** `--label before` and `--label after`
write two files; `--compare` reads both and reports, per account, whether it
moved. A single moved cent on an account that already priced is a regression,
not a side effect, and this script is what says so.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

settings.DEBUG = False

from django.core.management import call_command  # noqa: E402

from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import jobs as core_jobs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

SUBDOMAIN = os.environ.get("TENANT", "zerobill-fire")
OUT = Path(os.environ.get("OUTDIR", "/tmp/claude-0/zerobill-wt/.measure"))

PAYLOAD = {
    "name": "ZEROBILL Fire Utility",
    "subdomain": SUBDOMAIN,
    "owner": {
        "email": f"owner@{SUBDOMAIN}.test",
        "full_name": "ZEROBILL Owner",
        "password": "S3cure!passw0rd",
    },
    "country": "US",
    "state": "TX",
    "timezone": "America/Chicago",
    "currency": "USD",
    # Water is required for sewer (`core.sample_fixture._SEWER_NEEDS_WATER`);
    # fire is the counting capacity service whose schedule names six sizes and
    # therefore arms DEF-484's size gate — the whole subject of this defect.
    "services": ["water", "sewer", "fire"],
    "load_defaults": True,
}


def provision():
    existing = tenancy_models.Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if existing is not None:
        print(f"tenant {SUBDOMAIN} already exists — reusing it")
        return existing
    previous = core_jobs._dispatcher  # noqa: SLF001
    core_jobs.set_job_dispatcher(lambda _record: None)
    try:
        result = tenancy_services.provision_tenant(PAYLOAD)
    finally:
        core_jobs.set_job_dispatcher(previous)
    tenant = tenancy_models.Tenant.objects.get(pk=result["id"])
    plant = result.get("sample_plant")
    if plant is not None:
        with core_tenancy.tenant_context(str(tenant.id)):
            from apps.tenancy import sample_data as tenancy_sample_data

            core_jobs.run_job(plant["job_id"], tenancy_sample_data.run_provisioning_plant)
    print(f"provisioned {SUBDOMAIN}")
    call_command("seed_demo", tenant=SUBDOMAIN)
    call_command("load_sample_data", tenant=SUBDOMAIN)
    return tenant


def _money(value):
    return format(Decimal(str(value)).quantize(Decimal("0.0001")), "f")


def measure(tenant) -> dict:
    """EVERY account, gathered and priced through the money path itself.

    ⚠ **DELIBERATELY NOT `prepare_run` ALONE, AND THE FIRST DRAFT'S MISTAKE IS
    WORTH THE PARAGRAPH (hard-won law 7).** A run's population is the accounts
    seated in the CYCLE, and every account carrying this defect sits one join
    outside it: measured on this tenant, all **20** accounts whose plan prices
    fire over a unit with no fire service point are in the `A-1nnnn` import
    series and **not one of them is in `CY-001`**. A `prepare_run` measurement
    therefore reports a clean 34 priced / 17 refused and **cannot contain the
    failing case** — which is exactly how it read before this was fixed. The
    PO's own report came through `final_bill.preview_final_bill`, which
    gathers ONE account directly, so that is what this measures.
    """
    from apps.billing import gather as gather_mod
    from apps.billing import runs
    from apps.customers import models as customer_models
    from apps.metering import models as metering_models

    records: dict[str, dict] = {}
    period_start = date(2026, 9, 1)
    period_end = date(2026, 9, 30)
    service_date = period_end
    with core_tenancy.tenant_context(str(tenant.id)):
        cycle_days = (period_end - period_start).days + 1
        accounts = list(
            customer_models.Account.objects.filter(tenant_id=tenant.id).order_by(
                "account_no"
            )
        )
        print(f"{len(accounts)} accounts")
        for account in accounts:
            key = str(account.account_no)
            try:
                readings, _unmeasured = runs.readings_for_account(
                    account,
                    period_start=period_start,
                    period_end=period_end,
                    scope_services=None,
                    anchor_to_last_billed=True,
                )
                data = gather_mod.gather_account(
                    account=account,
                    service_date=service_date,
                    period_start=period_start,
                    period_end=period_end,
                    cycle_days=cycle_days,
                    readings=readings,
                )
                priced = runs.price_account(data)
            except gather_mod.GatherProblem as problem:
                records[key] = {
                    "outcome": "refused",
                    "reason": str(getattr(problem, "reason", "")),
                    "detail": str(problem)[:400],
                }
                continue
            except Exception as exc:  # noqa: BLE001 — recorded, never hidden
                records[key] = {
                    "outcome": "error",
                    "reason": type(exc).__name__,
                    "detail": str(exc)[:400],
                }
                continue
            lines = []
            for line in getattr(priced.priced, "lines", ()) or ():
                lines.append(
                    {
                        "kind": str(getattr(line, "kind", "")),
                        "service": str(getattr(line, "service", "") or ""),
                        "description": str(getattr(line, "description", "") or ""),
                        "amount": _money(getattr(line, "amount", 0) or 0),
                    }
                )
            records[key] = {
                "outcome": "priced",
                "total": _money(getattr(priced.priced, "total", 0) or 0),
                "lines": lines,
            }
    return records


def estate(tenant) -> dict:
    """PER ACCOUNT: which PLAN services the unit has NO service point for.

    The correlation `DEF-BIL-6759` asserts, recomputed from the estate rather
    than taken on trust — and the thing that says whether an account that
    PRICES today is at risk from the change (it is, exactly when this list is
    non-empty for it).
    """
    from apps.customers import models as customer_models
    from apps.metering import models as metering_models
    from apps.rating import selectors as rating_selectors

    out: dict[str, list[str]] = {}
    with core_tenancy.tenant_context(str(tenant.id)):
        plan_cache: dict = {}
        for account in customer_models.Account.objects.filter(
            tenant_id=tenant.id
        ).select_related("unit"):
            unit = account.unit
            if unit is None:
                continue
            taken = set(
                metering_models.ServicePoint.objects.filter(
                    tenant_id=tenant.id, unit_id=unit.id
                ).values_list("service__code", flat=True)
            )
            plan_id = getattr(unit, "rate_plan_id", None)
            if plan_id is None:
                out[str(account.account_no)] = ["(no plan)"]
                continue
            if plan_id not in plan_cache:
                plan_cache[plan_id] = [
                    row.get("service_code")
                    for row in rating_selectors.plan_rate_schedules(plan_id) or ()
                ]
            out[str(account.account_no)] = sorted(
                str(code) for code in plan_cache[plan_id] if code and code not in taken
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default=None)
    parser.add_argument("--compare", nargs=2, default=None, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    if args.compare:
        before = json.loads((OUT / f"{args.compare[0]}.json").read_text())
        after = json.loads((OUT / f"{args.compare[1]}.json").read_text())
        return compare(before, after)

    tenant = provision()
    records = measure(tenant)
    gaps = estate(tenant)
    for key, missing in gaps.items():
        records.setdefault(key, {"outcome": "not-in-run", "reason": ""})
        records[key]["unconnected_plan_services"] = missing
    label = args.label or "run"
    (OUT / f"{label}.json").write_text(json.dumps(records, indent=1, sort_keys=True))
    summary: dict[str, int] = {}
    for record in records.values():
        summary[record["outcome"]] = summary.get(record["outcome"], 0) + 1
    print(f"\n── {label}: {len(records)} accounts ─────────────────────────")
    for outcome, count in sorted(summary.items()):
        print(f"  {outcome:10} {count}")
    reasons: dict[str, int] = {}
    for record in records.values():
        if record["outcome"] in {"refused", "error"}:
            reasons[record["reason"]] = reasons.get(record["reason"], 0) + 1
    for reason, count in sorted(reasons.items()):
        print(f"    reason {reason}: {count}")
    print("\n── THE CORRELATION ──────────────────────────────────────────")
    for outcome in ("priced", "refused", "silent", "error"):
        rows = [r for r in records.values() if r["outcome"] == outcome]
        if not rows:
            continue
        with_gap = [r for r in rows if r.get("unconnected_plan_services")]
        print(
            f"  {outcome:8} {len(rows):3}  of which a plan service has NO "
            f"service point: {len(with_gap)}"
        )
        seen: dict[str, int] = {}
        for r in with_gap:
            for code in r["unconnected_plan_services"]:
                seen[code] = seen.get(code, 0) + 1
        for code, count in sorted(seen.items()):
            print(f"      {code}: {count}")
    print(f"written to {OUT / (label + '.json')}")
    return 0


def compare(before: dict, after: dict) -> int:
    """Per account: did it move? Reported as ARITHMETIC, never as a glance."""
    keys = sorted(set(before) | set(after))
    moved, fixed, regressed, same = [], [], [], 0
    for key in keys:
        b, a = before.get(key), after.get(key)
        if b is None or a is None:
            moved.append((key, "present in only one run"))
            continue
        if b["outcome"] == "priced" and a["outcome"] == "priced":
            if b["total"] != a["total"] or b["lines"] != a["lines"]:
                regressed.append((key, f"{b['total']} → {a['total']}"))
            else:
                same += 1
        elif b["outcome"] != "priced" and a["outcome"] == "priced":
            fixed.append((key, f"{b['outcome']}/{b['reason']} → priced {a['total']}"))
        elif b["outcome"] == "priced" and a["outcome"] != "priced":
            regressed.append((key, f"priced {b['total']} → {a['outcome']}/{a['reason']}"))
        else:
            same += 1
    print("── BEFORE → AFTER ──────────────────────────────────────────")
    print(f"  accounts ................. {len(keys)}")
    print(f"  identical ................ {same}")
    print(f"  refused → priced ......... {len(fixed)}")
    print(f"  MOVED (regression) ....... {len(regressed)}")
    for key, note in fixed:
        print(f"    fixed   {key}: {note}")
    for key, note in regressed + moved:
        print(f"    ⚠ MOVED {key}: {note}")
    return 1 if (regressed or moved) else 0


if __name__ == "__main__":
    raise SystemExit(main())
