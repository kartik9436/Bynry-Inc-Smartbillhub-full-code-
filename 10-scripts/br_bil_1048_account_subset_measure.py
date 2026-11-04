#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-6823 — an account holding THREE of its unit's SIX services
#          is still billed for all six.
# Rule:    BR-BIL-1048 — a bill charges for the services the ACCOUNT holds.
# Rules:   BR-CUS-1101 (the account's half) · BR-BIL-301 (a plan service with
#          NO connection is a $0.00 line and must stay one) · CLAUDE.md law 14
#          (measured on real PostgreSQL, never the SQLite default).
# ───────────────────────────────────────────────────────
"""NARROW ONE REAL ACCOUNT ON A SIX-SERVICE TENANT AND BILL IT, BEFORE AND AFTER.

    DATABASE_URL=postgres://... 06-backend/.venv/bin/python \
        10-scripts/br_bil_1048_account_subset_measure.py list
    ...                                                   bill  --account AC-2026-00003 --label before
    ...                                                   narrow --account AC-2026-00003 --keep electric,gas,fire
    ...                                                   bill  --account AC-2026-00003 --label after
    ...                                                   all   --label tip|fixed        # every account, for regressions

**ONE ACT PER PROCESS, AND THAT IS NOT TIDINESS.** The first draft did the
narrowing and the billing inside one `tenant_context` and the delete did not
survive the process — it reported three rows dropped and the next `psql` read
still showed six, so the "reproduction" would have measured nothing at all
while looking exactly like a measurement. Each command here commits and exits,
and the register is read back with `psql` between them.

**`narrow` DELETES the agreements rather than ending them**, because
`BR-CUS-1101` writes **no row** for a service the clerk unticked — an absent
agreement is the state a bill actually meets. (Ending one is refused by RLS on
this path anyway: `Save with update_fields did not affect any rows`.)

**THE POINT IS THE DIFF.** `all` writes one JSON record per account — outcome,
total to four decimals, and every line — so `tip` and `fixed` can be compared
account by account. A single moved cent on an account that was NOT narrowed is
a regression, not a side effect, and this is what says so. **Measured
2026-09-26 on 75 accounts: 2 moved, both intended, 73 byte-identical.**
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

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

settings.DEBUG = False

from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

OUT = Path(os.environ.get("OUTDIR", "/tmp/claude-0/BILLNARROW"))
SUB = os.environ.get("TENANT", "billnarrow-six")
PERIOD_START = date(2026, 9, 1)
PERIOD_END = date(2026, 9, 30)


def _money(value):
    return format(Decimal(str(value)).quantize(Decimal("0.0001")), "f")


def bill(account):
    """Gather and price ONE account through the money path itself.

    `PricingRefused` is reported apart from `GatherProblem` because they are
    different stages and `runs.prepare_run` files them as different breaks —
    reporting both as "error" is how a named, readable refusal gets mistaken
    for a crash.
    """
    from apps.billing import gather as gather_mod
    from apps.billing import rating_seam
    from apps.billing import runs

    try:
        readings, _ = runs.readings_for_account(
            account,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            scope_services=None,
            anchor_to_last_billed=True,
        )
        data = gather_mod.gather_account(
            account=account,
            service_date=PERIOD_END,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=30,
            readings=readings,
        )
        priced = runs.price_account(data)
    except gather_mod.GatherProblem as problem:
        return {
            "outcome": "refused",
            "reason": str(getattr(problem, "reason", "")),
            "detail": str(problem)[:900],
        }
    except rating_seam.PricingRefused as refusal:
        return {"outcome": "pricing-refused", "reason": "PricingRefused",
                "detail": str(refusal)[:900]}
    except Exception as exc:  # noqa: BLE001 — recorded, never hidden
        return {"outcome": "error", "reason": type(exc).__name__, "detail": str(exc)[:900]}
    lines = [
        {
            "kind": str(getattr(line, "kind", "")),
            "service": str(getattr(line, "service", "") or ""),
            "description": str(getattr(line, "description", "") or ""),
            "amount": _money(getattr(line, "amount", 0) or 0),
        }
        for line in getattr(priced.priced, "lines", ()) or ()
    ]
    return {"outcome": "priced", "total": _money(priced.priced.total), "lines": lines}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["list", "narrow", "bill", "all"])
    parser.add_argument("--account")
    parser.add_argument("--keep", default="electric,gas,fire")
    parser.add_argument("--label", default="run")
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.get(subdomain=SUB)
    from apps.customers import models as customer_models
    from apps.metering import models as metering_models
    from apps.rating import selectors as rating_selectors

    with core_tenancy.tenant_context(str(tenant.id)):
        if args.cmd == "list":
            # Accounts whose unit has SIX points, on a plan that prices all
            # six, holding six OPEN agreements — the population this defect
            # can be measured on at all.
            for account in (
                customer_models.Account.objects.filter(tenant_id=tenant.id)
                .select_related("unit")
                .order_by("account_no")
            ):
                unit = account.unit
                if unit is None or unit.rate_plan_id is None:
                    continue
                codes = sorted(
                    {
                        point.service.code
                        for point in metering_models.ServicePoint.objects.filter(
                            tenant_id=tenant.id, unit_id=unit.id
                        )
                    }
                )
                plan = sorted(
                    {
                        row.get("service_code")
                        for row in rating_selectors.plan_rate_schedules(unit.rate_plan_id)
                        or ()
                    }
                )
                open_rows = customer_models.ServiceAgreement.objects.filter(
                    tenant_id=tenant.id, account_id=account.id, ended_on__isnull=True
                ).count()
                if len(codes) >= 6 and open_rows >= 6 and len(set(plan) & set(codes)) >= 6:
                    result = bill(account)
                    print(account.account_no, result["outcome"],
                          result.get("total") or result.get("reason"))
            return 0

        if args.cmd == "all":
            records = {}
            for account in customer_models.Account.objects.filter(
                tenant_id=tenant.id
            ).order_by("account_no"):
                result = bill(account)
                records[account.account_no] = {
                    "outcome": result["outcome"],
                    "total": result.get("total"),
                    "reason": result.get("reason"),
                    "lines": [
                        (line["service"], line["description"], line["amount"])
                        for line in result.get("lines", [])
                    ],
                }
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"all_{args.label}.json").write_text(
                json.dumps(records, indent=1, sort_keys=True)
            )
            print("wrote", len(records), "accounts ->", f"all_{args.label}.json")
            return 0

        account = customer_models.Account.objects.get(
            tenant_id=tenant.id, account_no=args.account
        )

        if args.cmd == "narrow":
            keep = set(args.keep.split(","))
            by_point = {
                str(point.id): point.service.code
                for point in metering_models.ServicePoint.objects.filter(
                    tenant_id=tenant.id, unit_id=account.unit_id
                )
            }
            drop = [
                row.id
                for row in customer_models.ServiceAgreement.objects.filter(
                    tenant_id=tenant.id, account_id=account.id
                )
                if by_point.get(str(row.service_point_id)) not in keep
            ]
            deleted = customer_models.ServiceAgreement.objects.filter(
                tenant_id=tenant.id, id__in=drop
            ).delete()
            left = sorted(
                by_point.get(str(row.service_point_id))
                for row in customer_models.ServiceAgreement.objects.filter(
                    tenant_id=tenant.id, account_id=account.id, ended_on__isnull=True
                )
            )
            print("deleted", deleted, "remaining", left)
            return 0

        result = bill(account)
        result["account_no"] = account.account_no
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{args.label}.json").write_text(json.dumps(result, indent=2))
        print(args.label, result["outcome"], result.get("total") or result.get("reason"))
        for line in result.get("lines", []):
            print(f"   {line['service']:9s} {line['description'][:48]:50s} {line['amount']:>10s}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
