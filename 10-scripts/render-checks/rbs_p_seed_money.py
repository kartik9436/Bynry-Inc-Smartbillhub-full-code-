#!/usr/bin/env python3
"""Run the two MONEY runbooks for real, store their runs, and prove nothing moved.

CR-075 wave P (`US-RBS-022` · `US-RBS-026`), the half a browser cannot do.

WHY THIS IS A SEPARATE SCRIPT AND NOT A MANAGEMENT COMMAND
-----------------------------------------------------------
It was a management command first, and **`G115` refused it, correctly.** Staging
a lockbox file needs `apps.payments`, `apps.customers` and `apps.identity`, and
nothing under `06-backend/apps/runbooks/` may import another module outside
`seams/*_seam.py` and `ports/*_ports.py` (`BR-RBS-039`). A fixture is not an
exception to a boundary; it lives outside the module instead, exactly as
`rbs_c_seed_run.py` does for wave C.

WHAT IT SEEDS, AND THE FIRST ONE IS THE ONE THAT MATTERS
----------------------------------------------------------
1. **A STOPPED run of each runbook, with nothing to work on.** No payment
   connection, no accounting connection, no uploaded file — which is the screen
   a real utility meets on day one. The Product Owner ruled on 2026-09-06 that
   this is *"a valid case and state for us"*, so it must read as a **designed
   answer** rather than a failure, and only a browser can tell you whether it
   does.
2. **A lockbox file, staged and validated through `payments`' OWN import path,
   and a second run of cash application over it.** Three cheques: one naming a
   real account, one naming nothing at all, one naming an account this utility
   does not hold.

⚠ **THE RUNS ARE EXECUTED, NOT INSERTED**, and the reports are composed by
`report()` at close and frozen by `services.close_run`. A fixture that typed a
block list would let the walkthrough pass over a broken runbook — which is
`DEF-RBS-4291`'s shape exactly, where `started_at` was never stamped and every
run's *Started* and *Took* column was blank for ever with nothing red.

⚠ **THE FILE IS STAGED THROUGH `stage_import` + `validate_batch`, NEVER
INSERTED.** The match states runbook 10 reports are
`payment_import._match_row`'s own; rows written directly would let this pass
over a broken matcher, and the matcher is the thing runbook 10 reads.

⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** (hard-won law 7's second habit):

  * **counting outside the tenant context**, where RLS `FORCE` shows a session
    with the default marker NOTHING — so every table reads 0 before and 0 after
    and *"nothing moved"* is true of an empty view rather than of the database.
    That fired on `rbs_c_seed_run.py` and is why `counts()` sets the GUC.
  * **counting only the tables I remember** — so it counts EVERY table in the
    schema and derives the runbooks seven by name.
  * **a fixture too thin to conclude from** — a table empty before and after
    proves nothing, so the summary prints how many tables outside this module
    carry any rows at all.
  * **reporting the stop when the stop is a MISTAKE** — a run that stopped
    because the file id was mistyped looks exactly like a run that stopped
    because nothing was uploaded. So the file run asserts a NON-empty subject
    list, and the script fails if the batch it just staged resolves to nothing.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/smartbillhub" \\
      python3.12 10-scripts/render-checks/rbs_p_seed_money.py --tenant brazosbend

It prints `SMOKE_STOPPED_RUN_ID`, `SMOKE_BANKREC_RUN_ID` and
`SMOKE_APPLIED_RUN_ID` for the browser check.
"""

from __future__ import annotations

import argparse
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

from apps.customers import models as customer_models  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.payments import payment_import  # noqa: E402
from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.definitions import bank_reconciliation, cash_application  # noqa: E402
from apps.runbooks.engine import executor  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The seven tables this module owns. Everything else in the schema belongs to
#: another module, and an Action with no writer bound may not touch any of it.
RUNBOOKS_TABLES = {
    "runbooks",
    "runbook_versions",
    "runbook_runs",
    "runbook_run_records",
    "work_items",
    "cutover_plans",
    "cutover_plan_items",
}

#: One cheque per line, in the column names `lockbox.REMITTANCE_COLUMN_ALIASES`
#: accepts. The header is NAMED and never positional (`BR-PAY-023`): a file
#: whose columns cannot be named is refused rather than half-understood.
REMITTANCE = (
    "account_ref,payer_name,amount,paid_on,reference\n"
    "{account},Alvarez M,{amount},2026-09-05,88213\n"
    ",Two Candidates,60.00,2026-09-05,88240\n"
    "NOT-ON-FILE-HERE,Okonkwo D,1204.05,2026-09-05,88199\n"
)


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
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # noqa: S608 — from the catalog
            out[table] = cursor.fetchone()[0]
    return out


def adopt(tenant, definition) -> runbook_models.Runbook:
    """The runbook row `POST /runbooks` will write, from the SHIPPED definition.

    Nothing here invents a name, a kind or a category — every field is the
    definition's own. `cap` is typed because `runbooks.cap` still has NO column
    default: `OQ-RBS-1731` closed on 2026-09-06 at **100** and wave `L4` carries
    that change, so a fixture that pre-empted it would hide the gap.
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
        cap=100,
    )


def run_it(tenant, definition, params) -> tuple[str, str, dict]:
    """Open, execute, close — and close STOPPED when step 1 stopped it.

    ⚠ **`services.close_run` TAKES THE STATUS AND `run_to_completion` DOES
    NOT.** A stopped run closed as `done` would be a lie in the one column the
    run history sorts and filters on, so the status is decided here from what
    step 1 actually returned rather than defaulted.
    """
    runbook = adopt(tenant, definition)
    run = services.open_run(runbook, definition)
    result = executor.execute(definition, tenant_id=tenant.id, run_id=run.pk, params=params)
    stop = (result.set_results.get(definition.steps[0].key) or {}).get("stop")
    closed = services.close_run(
        run,
        result,
        status=(
            runbook_models.RUN_STATUS_STOPPED
            if stop
            else runbook_models.RUN_STATUS_AWAITING_APPROVAL
        ),
    )
    return str(closed.pk), closed.status, (stop or {})


def a_paying_account(tenant):
    """An account that actually OWES something, and what it owes.

    ⚠ **THE FIRST VERSION TOOK THE FIRST ACCOUNT BY NUMBER AND THE WHOLE
    WALKTHROUGH WAS WEAKER FOR IT.** `A-10432` owes nothing on the seeded
    tenant, so a $182.40 cheque against it came out as *"182.40 USD more than
    this account owes"* — a perfectly correct overpayment, and a screen on which
    NOTHING was ever planned. A fixture where the happy path cannot happen
    cannot tell a working plan from a broken one, which is hard-won law 7's
    shape at the fixture layer.

    So it walks accounts until one has an open balance and pays it EXACTLY. If
    no account owes anything, that is said out loud rather than papered over —
    the run is still valid, it just proves less.
    """
    from apps.payments import open_bills

    for account in customer_models.Account.objects.filter(tenant=tenant).order_by("account_no")[
        :50
    ]:
        try:
            position = open_bills.open_bill_position(account_id=account.pk)
        except Exception:  # noqa: BLE001 — an account whose books will not open
            continue
        owed = position.get("total_open")
        if owed and Decimal(str(owed)) > 0:
            return account, Decimal(str(owed))
    return None, None


def stage_a_file(tenant) -> str:
    """A three-row lockbox file, through `payments`' own staging and validation."""
    account, owed = a_paying_account(tenant)
    if account is None:
        account = (
            customer_models.Account.objects.filter(tenant=tenant).order_by("account_no").first()
        )
        print(
            "── ⚠ no account on this tenant owes anything, so the first cheque will read as "
            "an overpayment. The run is valid and proves less."
        )
        owed = Decimal("182.40")
    if account is None:
        raise SystemExit(
            "⛔ this tenant has no accounts, so a remittance file would match nothing and "
            "the run would prove nothing. Run seed_demo first."
        )
    actor = identity_models.User.objects.filter(tenant=tenant).order_by("created_at").first()
    payload = REMITTANCE.format(
        account=account.account_no, amount=f"{owed.quantize(Decimal('0.01'))}"
    ).encode("utf-8")
    staged = payment_import.stage_import(
        actor, file_name="lockbox-2026-09-05.csv", payload=payload, source_kind="lockbox"
    )
    payment_import.validate_batch(actor, batch_id=staged.batch_id)
    print(
        f"── staged {staged.rows} rows against account {account.account_no}, "
        f"which owes {owed}"
    )
    return staged.batch_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend", help="the tenant's subdomain")
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        print(
            f"⛔ REFUSED: this is running on {connection.vendor!r}.\n"
            "   The tenant policies these runbooks read under do not exist on SQLite, so a\n"
            "   green result here would mean nothing (hard-won law 7 — G5 called 192 skips\n"
            "   a pass).",
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

    with core_tenancy.tenant_context(tenant.id):
        stopped_id, stopped_status, stop = run_it(tenant, cash_application.RUNBOOK, {})
        print(f"── cash application, nothing to work on : {stopped_status} — {stop.get('headline')}")

        bankrec_id, bankrec_status, bankrec_stop = run_it(
            tenant, bank_reconciliation.RUNBOOK, {}
        )
        print(
            f"── bank reconciliation, nothing imported: {bankrec_status} — "
            f"{bankrec_stop.get('headline')}"
        )

        batch_id = stage_a_file(tenant)
        applied_id, applied_status, applied_stop = run_it(
            tenant, cash_application.RUNBOOK, {"batch": batch_id}
        )
        print(f"── cash application over the file       : {applied_status}")

    after = counts(tables, tenant.id)

    # `payment_import` LEGITIMATELY writes its own two staging tables and one
    # audit row — a person uploading a file is a PERSON's write, not the
    # runbook's — so they are excluded from "nothing moved" BY NAME and the
    # exclusion is printed beside the result.
    #
    # ⚠ **`audit_log` IS PARTITIONED AND THE FIRST VERSION OF THIS LIST NAMED
    # ONLY THE PARENT.** The write landed in `audit_log_2026_09` and the check
    # reported *"an Action wrote outside its module with no writer bound"* over
    # a row `stage_import` had every right to write. It was the guard being
    # WRONG rather than the code being wrong — and it is left in the file
    # because the fix is the interesting part: a table-name allow-list has to
    # know about partitions, and a check that does not is a check that cries
    # wolf until somebody switches it off.
    STAGING_PREFIXES = ("payment_import_batches", "payment_import_rows", "audit_log")
    moved_outside = {
        t: (before[t], after[t])
        for t in others
        if before[t] != after[t] and not t.startswith(STAGING_PREFIXES)
    }
    moved_inside = {
        t: (before.get(t), after.get(t)) for t in RUNBOOKS_TABLES if before.get(t) != after.get(t)
    }
    populated = sum(1 for t in others if before[t] > 0)

    print(f"── runbooks tables that moved : {sorted(moved_inside)}")
    print(f"── other tables that moved    : {sorted(moved_outside)}")
    print(f"── excluded, a person's write : {sorted(STAGING_PREFIXES)} (and partitions)")
    print(f"── other tables with any rows : {populated} of {len(others)}")

    if applied_stop:
        print(
            "\n⛔ THE FILE RUN STOPPED. The batch was staged one line earlier, so this is a\n"
            "   mistyped id or a broken seam rather than the designed 'nothing to work on'.\n"
            "   A stop that is a MISTAKE reads exactly like a stop that is an ANSWER, which\n"
            "   is why this is asserted rather than eyeballed.",
            file=sys.stderr,
        )
        return 1

    if moved_outside:
        print(
            "\n⛔ AN ACTION WROTE OUTSIDE ITS MODULE WITH NO WRITER BOUND. Every port is a\n"
            "   declaration until CR-075 task L2 binds one, so this is not a permission bug:\n"
            "   it is a write that reached the database by some other path.",
            file=sys.stderr,
        )
        for table, (was, now) in sorted(moved_outside.items()):
            print(f"   · {table}: {was} → {now}", file=sys.stderr)
        return 1

    if not moved_inside:
        print(
            "\n⛔ THE RUNS WROTE NOTHING IN THEIR OWN MODULE EITHER. A run that stored no row\n"
            "   is a broken fixture, not a clean Action. Nothing is concluded.",
            file=sys.stderr,
        )
        return 1

    if populated < 10:
        print(
            f"\n⚠ ONLY {populated} TABLES OUTSIDE THIS MODULE HAVE ANY ROWS AT ALL.\n"
            "   'nothing changed' over an empty database is not evidence. Seed a real\n"
            "   utility before reading this as a pass.",
            file=sys.stderr,
        )

    print()
    print(f"SMOKE_STOPPED_RUN_ID={stopped_id}")
    print(f"SMOKE_BANKREC_RUN_ID={bankrec_id}")
    print(f"SMOKE_APPLIED_RUN_ID={applied_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
