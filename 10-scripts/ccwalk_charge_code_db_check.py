#!/usr/bin/env python3
"""ccwalk_charge_code_db_check — what the DATABASE and the ONE lookup say about charge codes.

The database half of `10-scripts/charge_codes_walk33.mjs` (the PO's 2026-10-01
request: *"flat rate and multiple rate cases are correctly saved in dB"* and
*"obne record should be send to billing and change history should be
available"*). The browser walk drives the screens; this reads, for each code
named, what they wrote — through the real reads, never a copy of them:

  * every `charge_code_amounts` row, killed and closed ones included;
  * for each (size, class) the code states and each date asked, how many rows
    are in force (must be exactly one) and what `charge_prices.price_on_date`
    answers — the function every bill asks (gate `G141`);
  * a penalty's per-class terms through `charge_prices.class_terms_on`;
  * how many `audit_log` and `rate_change_log` rows name the code.

Prints one JSON object keyed by code. Writes nothing.

    DATABASE_URL=postgres://…/<your walk db> DJANGO_SETTINGS_MODULE=config.settings.local \\
      python 10-scripts/ccwalk_charge_code_db_check.py --tenant brazosbend \\
        --codes BASE-W,RE-READ --dates 2026-10-15,2026-11-15

Walk database only — never a shared or demo database.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from core import tenancy as core_tenancy  # noqa: E402

from apps.rating import charge_prices, models  # noqa: E402


def _money(value):
    return None if value is None else str(value)


def check(codes: list[str], days: list[date]) -> dict:
    out: dict = {}
    for code in codes:
        charge = (
            models.Charge.objects.filter(code=code, deleted_at__isnull=True).select_related("service").first()
        )
        if charge is None:
            out[code] = {"missing": True}
            continue
        rows = list(
            models.ChargeCodeAmount.objects.filter(charge_id=charge.id).order_by(
                "size_class", "customer_class", "effective_from", "id"
            )
        )
        keys = sorted({(row.size_class, row.customer_class) for row in rows}, key=lambda k: (k[0], k[1] or ""))
        lookups = {}
        for day in days:
            per_day = []
            for size_class, customer_class in keys:
                in_force = [
                    row
                    for row in rows
                    if row.size_class == size_class
                    and row.customer_class == customer_class
                    and row.effective_from <= day
                    and (row.effective_to is None or day <= row.effective_to)
                ]
                terms = in_force and in_force[0].percent is not None
                entry = {
                    "size_class": size_class,
                    "customer_class": customer_class,
                    "rows_in_force": len(in_force),
                }
                if terms:
                    found = charge_prices.class_terms_on(charge, customer_class, day)
                    entry["terms"] = (
                        None
                        if found is None
                        else {"percent": _money(found.percent), "minimum": _money(found.minimum)}
                    )
                else:
                    answer = charge_prices.price_on_date(
                        charge,
                        size_class=None if size_class == charge_prices.ALL_SIZES else size_class,
                        customer_class=customer_class,
                        on_date=day,
                    )
                    entry["amount"] = _money(answer.amount)
                    entry["refusal"] = answer.refusal
                    entry["row_id"] = None if answer.row is None else str(answer.row.id)
                per_day.append(entry)
            lookups[day.isoformat()] = per_day
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from audit_log where entity_id = %s", [str(charge.id)]
            )
            audits = cursor.fetchone()[0]
            cursor.execute(
                "select count(*) from rate_change_log where entity_id = %s", [str(charge.id)]
            )
            changes = cursor.fetchone()[0]
        out[code] = {
            "id": str(charge.id),
            "kind": charge.kind,
            "service": charge.service.code if charge.service_id else None,
            "charge_type": charge.charge_type,
            "amount_rule": charge.amount_rule,
            "is_base": charge.is_base,
            "applies_to_customer_classes": list(charge.applies_to_customer_classes or []),
            "rows": [
                {
                    "id": str(row.id),
                    "size_class": row.size_class,
                    "customer_class": row.customer_class,
                    "amount": _money(row.amount),
                    "percent": _money(row.percent),
                    "min_amount": _money(row.min_amount),
                    "effective_from": row.effective_from.isoformat(),
                    "effective_to": None if row.effective_to is None else row.effective_to.isoformat(),
                    "killed": row.killed_at is not None,
                }
                for row in rows
            ],
            "lookups": lookups,
            "audit_log_rows": audits,
            "rate_change_log_rows": changes,
        }
    return out


def accounts_by_service() -> dict:
    """`{"<service>|<class>": [account id, …]}` — open accounts on a billing cycle
    whose service point on that service carries a live asset, the ones a bill
    preview can price a base for. Assets first, so a sized base has a size."""
    from django.db import connection

    out: dict = {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select s.code, at.code, a.id::text, bool_or(x.id is not null)
              from service_agreements sa
              join accounts a on a.id = sa.account_id
              join service_points sp on sp.id = sa.service_point_id
              join services s on s.id = sp.service_id
              join account_types at on at.id = a.account_type_id
              left join assets x on x.service_point_id = sp.id and x.retire_date is null
             where sa.ended_on is null and sp.cycle_id is not null
             group by 1, 2, 3
             order by 1, 2, 4 desc, 3
            """
        )
        for service, cls, account_id, _has_asset in cursor.fetchall():
            out.setdefault(f"{service}|{cls}", []).append(account_id)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--codes", default="")
    parser.add_argument("--dates", default="")
    parser.add_argument("--accounts", action="store_true")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="answer one request per stdin line ('accounts' or '<codes>|<dates>'), one JSON line each",
    )
    args = parser.parse_args()
    tenant_id = core_tenancy.tenant_id_for_slug(args.tenant)
    days = [date.fromisoformat(d) for d in args.dates.split(",") if d]
    if args.serve:
        # One Django boot for the whole walk; every answer is read fresh.
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            with core_tenancy.tenant_context(tenant_id):
                if line == "accounts":
                    answer = accounts_by_service()
                else:
                    codes, _, dates = line.partition("|")
                    answer = check(
                        [c for c in codes.split(",") if c],
                        [date.fromisoformat(d) for d in dates.split(",") if d],
                    )
            print(json.dumps(answer), flush=True)
        return
    with core_tenancy.tenant_context(tenant_id):
        if args.accounts:
            print(json.dumps(accounts_by_service()))
            return
        print(json.dumps(check([c for c in args.codes.split(",") if c], days)))


if __name__ == "__main__":
    main()
