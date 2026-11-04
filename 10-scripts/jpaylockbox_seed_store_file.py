#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Journey:  08-qa/01-e2e/journeys/JPAYLOCKBOX-a-store-file-on-a-monday-morning.md
# Change:   `CR-135-BRC07` `P1.14` — the store file this journey is walked with.
# Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output, so the walk
#           is run against a booted stack) · law 14 (a savepoint check needs a
#           REAL PostgreSQL) · B14 rule 37 (a figure in a drawing is an
#           ILLUSTRATION — every number below is MEASURED off the tenant and
#           written into the manifest, never hardcoded into an assertion)
# ───────────────────────────────────────────────────────
"""Build Ruiz Grocery's weekend file for `JPAYLOCKBOX`, against a real tenant.

⚠ **THE FIXTURE IS SIZED TO THE TENANT, AND THE JOURNEY'S 1,431 IS NOT.**
The journey declares a 1,431-row file. `seed_demo` ships `brazosbend` with
**72 accounts**, so 1,408 clean rows would mean ~20 payments per household in
one weekend — and, worse, check C (*the bills it met are closed*) could not be
judged, because most rows would land as credit on an account with no bill. So
this emits **one clean row per account** and the journey's own **twenty-three**
problem rows, and the manifest carries every figure it produced. The journey
says so itself: *"every assertion below is written against the FIXTURE, never
against a number."*

⚠ **TWO FILES ARE EMITTED, AND THE SECOND ONE IS A FINDING RATHER THAN A
CONVENIENCE.** `…-as-sent.csv` is the file the journey describes, in the
store's own spelling: `PAID` carries *"a leading `$` and thousands separators"*
and `WHEN` carries *"`09/19/26`, the store's own two-digit year"*. Measured on
the tip, BOTH are refused, for two different reasons:

  · the amount — stage 2 strips the comma and **refuses the `$`**
    (`Decimal("$1234.50")` raises), so the row is rejected `PAY.VALUES_PARSE`;
  · the date — `BR-MET-117` forbids sniffing and matches the tenant's ONE
    declared format, and `DATE_FORMAT_PATTERNS` offers **no two-digit-year
    slash format at all** (`MM/DD/YY` is not one of `tenancy.services`'
    seven), so `09/19/26` matches nothing.

`…-repaired.csv` is the same file with the currency symbol removed and the
year widened to four digits — **which is exactly the hand edit a clerk has to
make to 1,431 rows in a spreadsheet before this product will read the file.**
Walk BOTH: the first is what the journey's fixture actually does, the second
is how the remaining thirteen checks get reached.

⚠ **ELEVEN ACCOUNTS GET AN `external_ref` AND THAT IS FIXTURE PREP, NOT A
PRODUCT CHANGE.** `payments.import_writer.match_account` matches a payer name
against ONE thing — an account's `external_ref`, *"a legacy reference where the
'number' was often the household's name"*, in its own words. `seed_demo` sets
none, so with the shipped seed all eleven name-only rows would be refused
`no_identifier` and the `PAY.NAME_ONLY_MATCH` rung the journey exists to test
would never be reached. These eleven are written as the legacy references a
migrated utility would carry.

USAGE (a PostgreSQL clone, never the shared database):

    eval "$(10-scripts/proof-db.sh clone lockbox --export)"
    DJANGO_SETTINGS_MODULE=config.settings.local \
      python3 ../10-scripts/jpaylockbox_seed_store_file.py --out /tmp/lockbox

It prints the manifest path. Re-running it is safe: the `external_ref` writes
are idempotent and the CSVs are rewritten from the tenant as it is NOW.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

# ⚠ The store's own column names, and they are the point of the journey: not
# one of them is ours. §Fixture's table, verbatim.
STORE_COLUMNS = ["CUST REF", "PAID", "WHEN", "TILL SLIP", "NAME ON STUB", "STORE"]

#: The legacy references the eleven name-only rows are written against. A
#: household name where the old system's "number" was a name.
LEGACY_NAMES = [
    "J RIVERA",
    "M OKONKWO",
    "T NGUYEN",
    "B CASTILLO",
    "A WHITFIELD",
    "D PRZYBYLSKI",
    "L MARCHETTI",
    "S ABERNATHY",
    "R DELACROIX",
    "K OYELARAN",
    "F BAUMGARTNER",
]

STORES = ["RUIZ-01", "RUIZ-02", "RUIZ-03"]


def money(value) -> str:
    """The store's own spelling: `$1,234.50`. Thousands separators and all."""
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    return "$" + f"{amount:,.2f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/claude-0/lane-p01/fixture")
    parser.add_argument("--tenant", default="brazosbend")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "06-backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django

    django.setup()
    from django.db import connection

    from apps.tenancy.models import Tenant

    tenant = Tenant.objects.get(subdomain=args.tenant)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with connection.cursor() as cur:
        # Hard rule 1 — nothing is read or written without the tenant set.
        cur.execute("set app.tenant_id = %s", [str(tenant.pk)])

        # ⚠ **OUTSTANDING, NOT THE INVOICE TOTAL — AND THE FIRST DRAFT USED
        # THE TOTAL, WHICH COST A FALSE CHECK-C FAILURE ON 16 ACCOUNTS.**
        # `seed_demo` ships invoices that are already fully allocated and still
        # carry `status = 'issued'`, so a fixture that pays their TOTAL pays
        # money that is not owed: `billing_seam.open_invoices_for_account`
        # correctly answers *no open invoice*, the payment correctly becomes an
        # account credit, and the readback correctly reports *allocated to
        # nothing*. Every step was right and the fixture was wrong — which is
        # exactly the shape a walkthrough must not blame on the product.
        cur.execute(
            """
            select a.id, a.account_no,
                   coalesce(sum(greatest(
                     case when i.status in ('issued','partially_paid','overdue')
                          then i.total else 0 end
                     - coalesce((select sum(al.amount) from allocations al
                                  where al.invoice_id = i.id), 0), 0)), 0) as open_total,
                   count(case when i.status in ('issued','partially_paid','overdue')
                              and i.total > coalesce((select sum(al.amount) from allocations al
                                                       where al.invoice_id = i.id), 0)
                              then 1 end) as open_bills
              from accounts a
              left join invoices i on i.account_id = a.id
             group by a.id, a.account_no
             order by a.account_no
            """
        )
        accounts = [
            {
                "id": str(row[0]),
                "account_no": row[1],
                "open_total": Decimal(row[2] or 0),
                "open_bills": int(row[3] or 0),
            }
            for row in cur.fetchall()
        ]

        # The eleven legacy references. Written onto accounts that DO have an
        # open bill, so a clerk resolving one in step 6 has something to place
        # the money against.
        with_bills = [a for a in accounts if a["open_bills"] > 0]
        legacy_targets = with_bills[: len(LEGACY_NAMES)]
        if len(legacy_targets) < len(LEGACY_NAMES):
            print(
                f"REFUSED: the tenant has {len(with_bills)} account(s) with an open bill "
                f"and the fixture needs {len(LEGACY_NAMES)}.",
                file=sys.stderr,
            )
            return 2
        for account, name in zip(legacy_targets, LEGACY_NAMES):
            cur.execute(
                "update accounts set external_ref = %s where id = %s and tenant_id = %s",
                [name, account["id"], str(tenant.pk)],
            )
            account["external_ref"] = name

    # ── the rows ────────────────────────────────────────────────────────────
    # A clean row per account. Where the account has an open bill the amount is
    # EXACTLY what is open, so check C can be judged: the bill it met closes.
    clean: list[dict] = []
    for index, account in enumerate(accounts):
        amount = account["open_total"] if account["open_bills"] else Decimal("25.00")
        if amount <= 0:
            amount = Decimal("25.00")
        clean.append(
            {
                "CUST REF": account["account_no"],
                "amount": amount,
                # Two of the store's three trading days, so check B cannot pass
                # by accident on one date.
                "WHEN": "09/19/26" if index % 2 == 0 else "09/20/26",
                "TILL SLIP": f"RG{100000 + index}",
                "NAME ON STUB": "",
                "STORE": STORES[index % len(STORES)],
                "_expect": "loaded",
                "_account_no": account["account_no"],
                "_account_id": account["id"],
                "_meets_bill": account["open_bills"] > 0,
            }
        )

    problems: list[dict] = []
    # 9 · `CUST REF` names an account this utility does not have → REFUSE
    for n in range(9):
        problems.append(
            {
                "CUST REF": f"OLD-{77000 + n}",
                "amount": Decimal("41.50") + n,
                "WHEN": "09/19/26",
                "TILL SLIP": f"RG{200000 + n}",
                "NAME ON STUB": "",
                "STORE": STORES[n % len(STORES)],
                "_expect": "rejected:account_not_on_file",
            }
        )
    # 11 · `CUST REF` blank, only `NAME ON STUB` filled → FLAG for a person
    for n, account in enumerate(legacy_targets):
        problems.append(
            {
                "CUST REF": "",
                "amount": Decimal("63.20") + n,
                "WHEN": "09/20/26",
                "TILL SLIP": f"RG{300000 + n}",
                "NAME ON STUB": account["external_ref"],
                "STORE": STORES[n % len(STORES)],
                "_expect": "flagged:name_only_match",
                "_suggests": account["account_no"],
            }
        )
    # 3 · `PAID` blank, `0.00`, `-12.40` → REFUSE
    for n, bad in enumerate(["", "0.00", "-12.40"]):
        problems.append(
            {
                "CUST REF": accounts[n]["account_no"],
                "amount": bad,
                "WHEN": "09/19/26",
                "TILL SLIP": f"RG{400000 + n}",
                "NAME ON STUB": "",
                "STORE": STORES[n % len(STORES)],
                "_expect": "rejected:amount",
            }
        )

    rows = clean + problems

    def write(path: Path, *, repaired: bool) -> None:
        """`repaired=False` is the store's own spelling; `True` is the hand
        edit a clerk must make today — no `$`, and a four-digit year."""
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=STORE_COLUMNS)
            writer.writeheader()
            for row in rows:
                raw = row["amount"]
                if isinstance(raw, Decimal):
                    cell = f"{raw.quantize(Decimal('0.01')):,.2f}" if repaired else money(raw)
                else:
                    # The three bad-amount cells travel exactly as the store
                    # typed them, in both files.
                    cell = raw
                when = row["WHEN"]
                if repaired:
                    month, day, year = when.split("/")
                    when = f"{month}/{day}/20{year}"
                writer.writerow(
                    {
                        "CUST REF": row["CUST REF"],
                        "PAID": cell,
                        "WHEN": when,
                        "TILL SLIP": row["TILL SLIP"],
                        "NAME ON STUB": row["NAME ON STUB"],
                        "STORE": row["STORE"],
                    }
                )

    as_sent = out / "ruiz-grocery-as-sent.csv"
    repaired = out / "ruiz-grocery-repaired.csv"
    write(as_sent, repaired=False)
    write(repaired, repaired=True)

    manifest = {
        "tenant": args.tenant,
        "tenant_id": str(tenant.pk),
        "file_as_sent": str(as_sent),
        "file_repaired": str(repaired),
        "hand_edits_the_product_requires": [
            "remove the currency symbol from every PAID cell",
            "widen every WHEN cell from a two-digit year to a four-digit one",
        ],
        "columns": STORE_COLUMNS,
        "rows_total": len(rows),
        "rows_clean": len(clean),
        "rows_problem": len(problems),
        "expect_loaded": len(clean),
        "expect_rejected_unknown_account": 9,
        "expect_flagged_name_only": 11,
        "expect_rejected_amount": 3,
        "expect_rejected_total": 9 + 3 + 11,
        "clean_rows": [
            {
                "account_no": row["_account_no"],
                "account_id": row["_account_id"],
                "amount": str(row["amount"].quantize(Decimal("0.01"))),
                "paid_on": ("2026-09-19" if row["WHEN"] == "09/19/26" else "2026-09-20"),
                "reference": row["TILL SLIP"],
                "meets_bill": row["_meets_bill"],
            }
            for row in clean
        ],
        "legacy_refs": [
            {"account_no": a["account_no"], "external_ref": a["external_ref"]}
            for a in legacy_targets
        ],
        "unknown_refs": [row["CUST REF"] for row in problems if row["_expect"].startswith("rejected:account")],
        "bad_amount_cells": ["", "0.00", "-12.40"],
        "store_date_format_as_sent": "MM/DD/YY (offered by nothing)",
        "tenant_date_format": "MM/DD/YYYY",
    }
    path = out / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"file as the store sends it : {as_sent}  ({len(rows)} rows)")
    print(f"file after the hand edits  : {repaired}")
    print(f"manifest                   : {path}")
    print(
        f"expected: {len(clean)} loaded · 9 unknown account · 11 name-only · 3 bad amount"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
