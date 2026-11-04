#!/usr/bin/env python3
"""Run runbook 23 for real on the seeded utility — one priced, one refused.

CR-075 wave F task `F4`, the half a browser cannot do.

WHY THIS IS A SEPARATE SCRIPT AND NOT A MANAGEMENT COMMAND
-----------------------------------------------------------
`G115` refuses a foreign import anywhere under `06-backend/apps/runbooks/`
outside `seams/*_seam.py` and `ports/*_ports.py` (`BR-RBS-039`), and choosing
which seeded account to price needs `apps.customers` and `apps.billing`. A
fixture is not an exception to a boundary; it lives outside the module, exactly
as `rbs_c_seed_run.py` and `rbs_p_seed_money.py` do.

WHAT IT DOES, AND THE THIRD THING IS THE ONE THAT MATTERS
----------------------------------------------------------
1. **Runs the test bill on an account that prices**, and stores the run. The
   report is composed by `report()` at close and frozen by `services.close_run`
   — a fixture that TYPED a block list would let the browser check pass over a
   broken runbook, which is `DEF-RBS-4291`'s shape exactly.
2. **Runs it on an account that cannot be priced**, and stores that run too.
   *"No connection / no data"* is a **valid outcome** (PO ruling 2026-09-06:
   *"that is a valid case and state for us"*), so the refusal has to be looked
   at in a browser like any other result, not inferred from a log line.
3. **Re-prices a period the utility has already ISSUED a bill for, and compares
   line by line at FOUR decimals.** `TC-RBS-004.3` proves that identity on a
   built fixture; this proves it on the **seeded utility's own data**, against
   a document that was written weeks of fixture-time ago by the real pipeline.
   It is the difference between *"the code agrees with itself"* and *"the code
   agrees with a bill that already exists"*.

⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** (hard-won law 7's second habit):

  * **Counting outside the tenant context.** RLS `FORCE` shows a session with
    the default marker NOTHING, so every table reads 0 before and 0 after and
    *"nothing moved"* is true of an empty view rather than of the database.
    That fired on `rbs_c_seed_run.py`; `counts()` sets the GUC.
  * **Counting only the tables I remember.** So it counts EVERY table in the
    schema and derives this module's seven by name.
  * **Comparing a bill with itself.** If the account chosen for step 3 had no
    issued bill, an empty-to-empty comparison would pass. So the script REFUSES
    when it finds no issued bill with lines, and prints how many it considered.
  * **Comparing at two decimals.** `$0.0025` a unit is a real tariff rate and is
    invisible at two. Every figure here is quantized to FOUR (hard rule 2:
    stored 4, displayed 2) and the script says so in its output.
  * **Running on SQLite**, where the tenant policies a Check runs under do not
    exist at all. It refuses any vendor but PostgreSQL.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/sbh_rbsf" \\
      python3.12 10-scripts/render-checks/rbs_f_seed_test_bill.py --tenant brazosbend

It prints `SMOKE_RUN_PRICED` and `SMOKE_RUN_REFUSED`, which the browser check
opens, and the figures it expects to read off each screen.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from decimal import Decimal

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.billing import models as billing_models  # noqa: E402
from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.registry import registry  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The seven tables this module owns (`03-field-map.md`). Everything else in the
#: schema belongs to another module and a Check may not touch it.
RUNBOOKS_TABLES = {
    "runbooks",
    "runbook_versions",
    "runbook_runs",
    "runbook_run_records",
    "runbook_schedules",
    "runbook_work_items",
    "runbook_cutover_plans",
}

RUNBOOK_KEY = "test_bill"


def four(value) -> Decimal:
    """A money figure at its STORED scale — hard rule 2, four decimals not two."""
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def every_table() -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
        return [row[0] for row in cursor.fetchall()]


def counts(tables: list[str], tenant_id) -> dict[str, int]:
    """Row counts AS THE TENANT, which is the only way they are real."""
    out: dict[str, int] = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
        for table in tables:
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # noqa: S608 — catalog names
            out[table] = cursor.fetchone()[0]
    return out


def ensure_runbook(tenant, definition):
    """The tenant's row for this shipped runbook, added if it is not there.

    Written from the SHIPPED definition's own metadata — nothing here invents a
    name, a kind or a category — and `origin` is `shipped` because that is what
    it is: the template being adopted, not a tenant's clone.
    """
    runbook = runbook_models.Runbook.objects.filter(tenant=tenant, key=definition.key).first()
    if runbook is not None:
        return runbook
    print(f"── no runbook row for {definition.key!r}; adding the shipped one")
    return runbook_models.Runbook.objects.create(
        tenant=tenant,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
        tags=list(definition.tags),
        origin=runbook_models.ORIGIN_SHIPPED,
        trigger_kind=runbook_models.TRIGGER_MANUAL,
        enabled=True,
    )


def issued_bills(limit: int):
    """Issued bills with lines, newest period first — the comparison candidates."""
    return list(
        billing_models.Invoice.objects.exclude(status=billing_models.INVOICE_DRAFT)
        .order_by("-period_end", "id")[:limit]
    )


def invoice_lines(invoice):
    return [
        (row.kind, row.description, four(row.amount))
        for row in billing_models.InvoiceLine.objects.filter(invoice_id=invoice.pk).order_by(
            "created_at", "id"
        )
    ]


def accounts_never_billed(limit: int):
    """Accounts this utility has never issued a bill for — the refusal candidates.

    ⚠ **THIS IS WHERE THE SECOND HALF OF THE GOAL SENTENCE LIVES, AND IT IS NOT
    AN ERROR CASE.** *"No connection / no data"* is a **valid outcome** (PO
    ruling 2026-09-06: *"in absence of API conenctions you will not find
    anything and you can stop the job saying APi or conenct not available; that
    is a valid case and state for us"*). An account that has never been billed
    is the honest place to find one on a seeded utility — it was left out of
    every run for a reason the runbook can now say out loud.
    """
    from apps.customers import models as customers_models

    billed = billing_models.Invoice.objects.values_list("account_id", flat=True)
    return list(
        customers_models.Account.objects.exclude(id__in=list(billed)).order_by("account_no")[:limit]
    )


def run_once(runbook, definition, *, account_id, period_start, period_end, as_at=None):
    """One stored run of runbook 23.

    ⚠ **`as_at` IS THE DATE THAT DECIDES THE PRICE, AND IT IS NOT THE PERIOD
    END** (`BR-RAT-007`, judgment J9). A cycle run prices on its BILL DAY: the
    seeded July bills carry `service_date = 2026-08-02`, and a water rate change
    falls between that and 31 July. Comparing a re-price at the period end with
    a bill issued on 2 August compares two different questions — which is
    exactly what the first run of this script did, reporting all twelve sampled
    accounts as disagreeing with their own bills. So the comparison passes the
    ISSUED BILL'S OWN service date, and the script ALSO runs the default once,
    to SHOW the gap rather than hide it.
    """
    period: dict[str, str] = {
        "start": period_start.isoformat(),
        "end": period_end.isoformat(),
    }
    if as_at is not None:
        period["as_at"] = as_at.isoformat()
    return services.run_to_completion(
        runbook,
        definition,
        params={
            "account": str(account_id),
            "period": period,
            "compare_with": "last_issued_bill",
            "show": "every_line_explained",
        },
    )


def main() -> int:  # noqa: C901 — one linear script, read top to bottom
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument(
        "--candidates",
        type=int,
        default=40,
        help="how many issued bills to consider before giving up",
    )
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        print(
            f"⛔ REFUSED: this is running on {connection.vendor!r}.\n"
            "   The tenant policies a Check runs under do not exist on SQLite, so a green\n"
            "   result here would mean nothing (hard-won law 7 — G5 called 192 skips a pass).",
            file=sys.stderr,
        )
        return 2

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        print(f"⛔ no tenant with subdomain {args.tenant!r} — seed_demo first", file=sys.stderr)
        return 2

    tables = every_table()
    others = [t for t in tables if t not in RUNBOOKS_TABLES]
    print(f"── {len(tables)} tables in the schema · {len(others)} outside this module")
    before = counts(tables, tenant.id)

    priced_run = None
    refused_run = None
    priced_summary: dict[str, object] = {}
    refused_summary: dict[str, object] = {}
    agreements: list[dict[str, object]] = []
    as_at_gaps: list[dict[str, object]] = []
    considered = 0

    with core_tenancy.tenant_context(tenant.id):
        definition = registry.get(RUNBOOK_KEY)
        runbook = ensure_runbook(tenant, definition)

        for invoice in issued_bills(args.candidates):
            considered += 1
            theirs = invoice_lines(invoice)
            if not theirs:
                continue

            run, result = run_once(
                runbook,
                definition,
                account_id=invoice.account_id,
                period_start=invoice.period_start,
                period_end=invoice.period_end,
                as_at=invoice.service_date,
            )
            step2 = result.set_results["price"]
            if step2["priced"] is None:
                if refused_run is None:
                    refusal = step2["refusal"]
                    sentence = next(
                        (b for b in run.report if b["block"] == "sentence"), {"payload": {}}
                    )["payload"]
                    refused_run = run
                    refused_summary = {
                        "run_id": str(run.pk),
                        "account_no": result.set_results["load"].get("account_no"),
                        "reason": refusal.get("reason"),
                        "service": refusal.get("service_code"),
                        "sentence": sentence.get("text"),
                        "blocks": [b["block"] for b in run.report],
                    }
                continue

            mine = [
                (line["kind"], line["description"], four(line["amount"]))
                for line in step2["priced"]["lines"]
            ]
            agreement = {
                "account_no": result.set_results["load"].get("account_no"),
                "period": f"{invoice.period_start} → {invoice.period_end}",
                "priced_as_at": str(invoice.service_date),
                "test_bill_lines": len(mine),
                "issued_lines": len(theirs),
                "identical": mine == theirs,
                "test_bill_total": str(four(step2["priced"]["total"])),
                "issued_total": str(four(invoice.total)),
                "totals_agree": four(step2["priced"]["total"]) == four(invoice.total),
            }
            agreements.append(agreement)

            # ── JUDGMENT J9, DEMONSTRATED RATHER THAN ASSERTED ────────────
            # The SAME account and the SAME period, priced at the period end
            # instead of at the bill day. Where a tariff version boundary falls
            # between the two dates the answer moves, and printing the pair is
            # what shows a reader that BOTH figures are right and that the
            # screen therefore has to say which date it used.
            if len(as_at_gaps) < 2:
                _default_run, default_result = run_once(
                    runbook,
                    definition,
                    account_id=invoice.account_id,
                    period_start=invoice.period_start,
                    period_end=invoice.period_end,
                )
                other = default_result.set_results["price"]["priced"]
                if other is not None and four(other["total"]) != four(step2["priced"]["total"]):
                    as_at_gaps.append(
                        {
                            "account_no": agreement["account_no"],
                            "period": agreement["period"],
                            "at_the_bill_day": (
                                f"{invoice.service_date} → {four(step2['priced']['total'])}"
                            ),
                            "at_the_period_end": (
                                f"{invoice.period_end} → {four(other['total'])}"
                            ),
                        }
                    )

            if priced_run is None:
                priced_run = run
                priced_summary = {
                    "run_id": str(run.pk),
                    "account_no": agreement["account_no"],
                    "period": agreement["period"],
                    "total": agreement["test_bill_total"],
                    "lines": len(mine),
                    "blocks": [b["block"] for b in run.report],
                    "line_amounts": [str(a) for _k, _d, a in mine],
                }
            if priced_run is not None and refused_run is not None and len(agreements) >= 3:
                break

        # ── THE REFUSAL, WHICH IS HALF THE GOAL SENTENCE ──────────────────
        # Every account that already HAS a bill prices again, which is the
        # right outcome and leaves the walkthrough with no stop to look at. So
        # the never-billed accounts are asked next; one of them will say which
        # service it could not price and why, and THAT is the screen a clerk
        # meets on day one.
        if refused_run is None and priced_run is not None:
            window = issued_bills(1)[0] if issued_bills(1) else None
            reasons_seen: dict[str, int] = {}
            for account in accounts_never_billed(30):
                run, result = run_once(
                    runbook,
                    definition,
                    account_id=account.id,
                    period_start=window.period_start,
                    period_end=window.period_end,
                    as_at=window.service_date,
                )
                step2 = result.set_results["price"]
                if step2["priced"] is not None:
                    continue
                refusal = step2["refusal"]
                reason = str(refusal.get("reason"))
                reasons_seen[reason] = reasons_seen.get(reason, 0) + 1
                sentence = next(
                    (b for b in run.report if b["block"] == "sentence"), {"payload": {}}
                )["payload"]
                candidate = {
                    "run_id": str(run.pk),
                    "account_no": result.set_results["load"].get("account_no"),
                    "reason": reason,
                    "service": refusal.get("service_code"),
                    "sentence": sentence.get("text"),
                    "words_in_the_sentence": len(str(sentence.get("text") or "").split()),
                    "blocks": [b["block"] for b in run.report],
                }
                # ⚠ **PREFER A REFUSAL THAT NAMES ITS SERVICE**, because that is
                # the goal sentence `US-RBS-004` promises — *"one refusal
                # sentence naming the service and the date"*. Some refusals are
                # account-level and the engine names no service for them; the
                # runbook then says so honestly rather than guessing one, and
                # this picks the more informative screen where the fixture has
                # one to offer.
                if refused_run is None or (
                    refused_summary.get("service") is None and candidate["service"] is not None
                ):
                    refused_run, refused_summary = run, candidate
                if refused_summary.get("service") is not None:
                    break
            if reasons_seen:
                print(f"── refusals found on never-billed accounts: {reasons_seen}")

    after = counts(tables, tenant.id)
    moved_outside = {t: (before[t], after[t]) for t in others if before[t] != after[t]}
    moved_inside = {
        t: (before[t], after[t]) for t in RUNBOOKS_TABLES if before.get(t) != after.get(t)
    }
    populated = sum(1 for t in others if before[t] > 0)

    print(f"── issued bills considered    : {considered}")
    print(f"── runbooks tables that moved : {sorted(moved_inside)}")
    print(f"── other tables that moved    : {sorted(moved_outside)}")
    print(f"── other tables with any rows : {populated} of {len(others)}")

    print("\n── TC-RBS-004.3 ON THE SEEDED UTILITY'S OWN ISSUED BILLS, AT FOUR DECIMALS")
    for row in agreements:
        mark = "✓" if row["identical"] and row["totals_agree"] else "⛔"
        print(
            f"   {mark} {row['account_no']}  {row['period']}  as at {row['priced_as_at']}  ·  "
            f"test bill {row['test_bill_total']} over {row['test_bill_lines']} lines  ·  "
            f"issued {row['issued_total']} over {row['issued_lines']} lines"
        )

    if as_at_gaps:
        print(
            "\n── THE SAME ACCOUNTS PRICED AT THE PERIOD END INSTEAD OF THE BILL DAY.\n"
            "   Both figures are right and they answer different questions: BR-RAT-007\n"
            "   prices on the SERVICE date, and a rate-version boundary falls between the\n"
            "   two. This is why the screen carries a *Priced as at* tile (judgment J9)."
        )
        for row in as_at_gaps:
            print(
                f"   · {row['account_no']}  {row['period']}:  "
                f"{row['at_the_bill_day']}   vs   {row['at_the_period_end']}"
            )

    if moved_outside:
        print(
            "\n⛔ A CHECK WROTE OUTSIDE ITS MODULE. `BR-RBS-002` says a Check is CONSTRUCTED\n"
            "   with no writer — the capability is absent, not refused — so this is not a\n"
            "   permission bug, it is a runbook that was given a port it may not hold.",
            file=sys.stderr,
        )
        for table, (was, now) in sorted(moved_outside.items()):
            print(f"   · {table}: {was} → {now}", file=sys.stderr)
        return 1

    if priced_run is None:
        print(
            "\n⛔ NO ACCOUNT PRICED. Every issued bill considered refused when re-priced,\n"
            "   so there is nothing for the browser check to read and nothing is concluded.",
            file=sys.stderr,
        )
        return 1

    if not moved_inside:
        print(
            "\n⛔ THE RUN WROTE NOTHING IN ITS OWN MODULE EITHER. A run that stored no row\n"
            "   is a broken fixture, not a clean Check.",
            file=sys.stderr,
        )
        return 1

    if populated < 10:
        print(
            f"\n⚠ ONLY {populated} TABLES OUTSIDE THIS MODULE HAVE ANY ROWS AT ALL.\n"
            "   'nothing changed' over an empty database is not evidence.",
            file=sys.stderr,
        )

    print("\n── what the browser check should read off the screens")
    print(json.dumps({"priced": priced_summary, "refused": refused_summary}, indent=2))
    print(f"\nSMOKE_RUN_PRICED={priced_summary['run_id']}")
    if refused_run is not None:
        print(f"SMOKE_RUN_REFUSED={refused_summary['run_id']}")
    else:
        # Stated rather than substituted: on a utility where every account
        # prices, there is no refusal to look at and the browser check must be
        # told so rather than opening a run that does not exist.
        print(
            "SMOKE_RUN_REFUSED=\n"
            "⚠ no account in the sample refused. The refusal half of the walkthrough "
            "has nothing to open — that is a fact about this fixture, not a pass."
        )

    disagreements = [r for r in agreements if not (r["identical"] and r["totals_agree"])]
    if disagreements:
        print(
            f"\n⛔ {len(disagreements)} OF {len(agreements)} ACCOUNTS DISAGREE WITH THEIR OWN "
            "ISSUED BILL.\n   The test bill and the bill run must produce an identical line "
            "set and identical\n   amounts to four decimals (`TC-RBS-004.3`). A disagreement "
            "here is a defect in\n   this runbook, never a reason to move a B4 figure.",
            file=sys.stderr,
        )
        for row in disagreements:
            print(f"   · {row}", file=sys.stderr)
        return 1

    print(f"\n✓ {len(agreements)} account(s) re-priced identically to their issued bill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
