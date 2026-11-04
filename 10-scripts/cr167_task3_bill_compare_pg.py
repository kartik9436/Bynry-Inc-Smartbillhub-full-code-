"""CR-167-BRC10 round 2 task 3 (lane PLAN-API) — NO FIGURE MAY MOVE: price every
account of a tenant before and after the plan-version migrations and compare.

For every open account of the tenant, prices TWO periods with billing's one-time
PREVIEW (the bill engine, read-only — run inside a transaction that is rolled
back): the period of the account's latest issued bill, and October 2026 (an
unbilled month). Writes every line (service, kind, description, amount) or the
refusal to a JSON file.

USAGE (PostgreSQL 16 — law 14)
    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python 10-scripts/cr167_task3_bill_compare_pg.py snap <subdomain> <out.json>
    ... compare <before.json> <after.json>     (exit 1 on any difference)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")


def _lines(body):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "kind" in node and "amount" in node and "description" in node:
                found.append(
                    [
                        str(node.get("service") or "-"),
                        str(node.get("kind")),
                        str(node.get("description")),
                        str(node.get("amount")),
                    ]
                )
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(body)
    return sorted(found)


def snap(subdomain: str, out: str) -> int:
    import django

    django.setup()
    from django.db import transaction

    from apps.billing import models as billing_models
    from apps.billing import one_time
    from apps.customers import models as customer_models
    from apps.tenancy import models as tenancy_models
    from core import tenancy as core_tenancy

    tenant = tenancy_models.Tenant.objects.get(subdomain=subdomain)
    core_tenancy.set_current_tenant(tenant.id)
    result: dict[str, object] = {}
    accounts = customer_models.Account.objects.filter(tenant_id=tenant.id).order_by("account_no")
    for account in accounts:
        last = (
            billing_models.Invoice.objects.filter(
                tenant_id=tenant.id, account_id=account.id, status="issued"
            )
            .order_by("-period_end")
            .first()
        )
        periods = [(date(2026, 10, 1), date(2026, 10, 31))]
        if last is not None and last.period_start and last.period_end:
            periods.insert(0, (last.period_start, last.period_end))
        for start, end in periods:
            key = f"{account.account_no} {start}..{end}"
            request = one_time.OneTimeRequest(
                account_id=str(account.id), kind="interim", period_start=start, period_end=end
            )
            try:
                with transaction.atomic():
                    body = one_time.preview(request)
                    result[key] = {"lines": _lines(body)}
                    transaction.set_rollback(True)
            except Exception as exc:  # noqa: BLE001 — a refusal IS the measurement
                result[key] = {"refused": f"{type(exc).__name__}: {str(exc)[:300]}"}
    Path(out).write_text(json.dumps(result, indent=1, sort_keys=True))
    priced = sum(1 for v in result.values() if "lines" in v)
    total = sum(
        (Decimal(line[3]) for v in result.values() for line in v.get("lines", [])), Decimal("0")
    )
    print(f"{subdomain}: {len(result)} account-periods, {priced} priced, "
          f"{len(result) - priced} refused, sum of all lines {total:.2f} -> {out}")
    return 0


def compare(before: str, after: str) -> int:
    a = json.loads(Path(before).read_text())
    b = json.loads(Path(after).read_text())
    diffs = [key for key in sorted(set(a) | set(b)) if a.get(key) != b.get(key)]
    total_a = sum((Decimal(l[3]) for v in a.values() for l in v.get("lines", [])), Decimal("0"))
    total_b = sum((Decimal(l[3]) for v in b.values() for l in v.get("lines", [])), Decimal("0"))
    print(f"before: {len(a)} account-periods, sum {total_a:.2f}")
    print(f"after:  {len(b)} account-periods, sum {total_b:.2f}")
    print(f"differences: {len(diffs)}")
    for key in diffs[:20]:
        print(f"  {key}\n    before {a.get(key)}\n    after  {b.get(key)}")
    return 1 if diffs else 0


if __name__ == "__main__":
    if sys.argv[1] == "snap":
        sys.exit(snap(sys.argv[2], sys.argv[3]))
    sys.exit(compare(sys.argv[2], sys.argv[3]))
