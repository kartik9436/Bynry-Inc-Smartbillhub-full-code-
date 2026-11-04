#!/usr/bin/env python3
"""Execute runbook 1, store the run, and PROVE the Check wrote nothing else.

CR-075 wave C task `C8`, the half a browser cannot do.

WHY THIS IS A SEPARATE SCRIPT
-----------------------------
`rbs-c-can-we-bill.mjs` drives the screen. Two of `C8`'s requirements are not
screen facts at all:

  * **there has to BE a run to look at**, and `POST /runbooks/{key}/runs` is
    task `L` — phase 2, the acting half. Every runbooks route that exists today
    is a `GET`, deliberately (`api.py`'s own docstring, and `BR-RBS-002`). So
    the run is made here, through the same engine call the future endpoint will
    make, rather than by pretending the button exists.
  * **"diff the database: nothing outside the seven tables changed"**, which is
    the only place `BR-RBS-002` is tested against a real database instead of
    against a mock.

⚠ **`BR-RBS-002` IS A CONSTRUCTION FACT, NOT A RUNTIME REFUSAL** — *"a Check is
constructed with no writer, so a write is unavailable rather than refused at
runtime"*. That makes it the kind of guarantee that is easy to believe and hard
to check: there is no exception to catch and no error to assert, because the
capability is simply absent. A row count either moved or it did not, and this
script is what looks.

⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY**, asked because a check you cannot
describe a false pass for is one you do not understand (hard-won law 7):

  * counting only the tables I remember — so it counts EVERY table in the
    schema and derives the runbooks seven by NAME, rather than listing the rest
    by hand;
  * counting on SQLite, where the tenant policies this runs under do not exist
    at all — so it REFUSES to run anywhere but PostgreSQL. `G5` once ran the
    isolation suite on sqlite and called 192 skips a pass;
  * a table that is empty before AND after, which proves nothing about whether
    a write was possible — so the summary prints how many tables actually
    carried rows, and a run where that number is small is a run whose fixture
    is too thin to conclude from.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/smartbillhub_rbsc" \\
      python3 10-scripts/render-checks/rbs_c_seed_run.py --tenant brazosbend

It prints the run id, which is `SMOKE_RUN_ID` for the browser check.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.registry import registry  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The seven tables this module owns (`03-field-map.md`). Everything else in the
#: schema is another module's and a Check may not touch it.
RUNBOOKS_TABLES = {
    "runbooks",
    "runbook_versions",
    "runbook_runs",
    "runbook_run_records",
    "runbook_schedules",
    "runbook_work_items",
    "runbook_cutover_plans",
}


def every_table() -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
        return [row[0] for row in cursor.fetchall()]


def counts(tables: list[str], tenant_id) -> dict[str, int]:
    """Row counts AS THE TENANT, which is the only way they are real.

    ⚠ **THIS COUNTED OUTSIDE THE TENANT CONTEXT IN ITS FIRST VERSION AND THE
    WHOLE CHECK WAS VACUOUS.** Row-level security is FORCE'd on every tenant
    table, and a session with the database's default marker
    (`00000000-0000-0000-0000-000000000000`) sees NOTHING. So every tenant table
    counted 0 before and 0 after, "nothing moved" was true of an empty view
    rather than of the database, and the script printed a confident pass over a
    run that had just written three rows.

    It was caught by reading the output rather than the exit code: the summary
    said `runbooks tables that moved : []` immediately after creating a runbook
    and executing a run, which cannot both be true. **That is this file's own
    docstring question — "what would make this check pass wrongly" — answered by
    a mode I had not listed.** The three I did list are still there; this is the
    fourth, and it is the one that actually fired.
    """
    out: dict[str, int] = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
        for table in tables:
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # noqa: S608 — names from the catalog
            out[table] = cursor.fetchone()[0]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend", help="the tenant's subdomain")
    parser.add_argument("--runbook", default="configuration_check")
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

    with core_tenancy.tenant_context(tenant.id):
        definition = registry.get(args.runbook)
        # ⚠ `services.run_to_completion`, NOT `executor.execute`. THE EXECUTOR
        # WRITES NO ROW AT ALL — its own docstring says so: it pins a scope,
        # walks steps and composes a report, and something else opens, stamps
        # and closes the run. A first draft of this script called the executor
        # and would have printed `SMOKE_RUN_ID=None`, leaving the browser check
        # with nothing to open — the assumption was checked rather than shipped.
        runbook = runbook_models.Runbook.objects.filter(
            tenant=tenant, key=definition.key
        ).first()
        if runbook is None:
            # ⚠ **ADDED HERE, BECAUSE NOTHING ELSE CAN ADD IT YET.** Putting a
            # shipped runbook on a tenant is `POST /runbooks` — wave `E1` — and
            # `seed_demo` creates none (verified: 79 premises and 137 assets on
            # the seeded tenant, and 0 runbooks). Without this the walkthrough
            # could not run at all until phase 1 closes.
            #
            # It writes the row the endpoint will write, from the SHIPPED
            # definition's own metadata — nothing here invents a name, a kind or
            # a category. `origin` is `shipped` because that is what it is: this
            # is the template being adopted, not a tenant's clone.
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
                trigger_kind=runbook_models.TRIGGER_MANUAL,
                enabled=True,
            )
        run, _result = services.run_to_completion(runbook, definition)

    after = counts(tables, tenant.id)

    moved_outside = {t: (before[t], after[t]) for t in others if before[t] != after[t]}
    moved_inside = {
        t: (before[t], after[t]) for t in RUNBOOKS_TABLES if before.get(t) != after.get(t)
    }
    # A table empty before AND after proves nothing about whether a write was
    # possible. Say how much of the schema actually carried rows, so a thin
    # fixture cannot read as a strong result.
    populated = sum(1 for t in others if before[t] > 0)

    print(f"── runbooks tables that moved : {sorted(moved_inside)}")
    print(f"── other tables that moved    : {sorted(moved_outside)}")
    print(f"── other tables with any rows : {populated} of {len(others)}")

    if moved_outside:
        print(
            "\n⛔ A CHECK WROTE OUTSIDE ITS MODULE. `BR-RBS-002` says a Check is "
            "CONSTRUCTED\n   with no writer — the capability is absent, not refused — so this "
            "is not a\n   permission bug, it is a runbook that was given a port it may not hold.",
            file=sys.stderr,
        )
        for table, (was, now) in sorted(moved_outside.items()):
            print(f"   · {table}: {was} → {now}", file=sys.stderr)
        return 1

    if not moved_inside:
        print(
            "\n⛔ THE RUN WROTE NOTHING IN ITS OWN MODULE EITHER. A run that stored no row\n"
            "   is a broken fixture, not a clean Check — and it is exactly how this script\n"
            "   passed vacuously before it counted as the tenant. Nothing is concluded.",
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

    print(f"\n✓ nothing outside the seven runbooks tables changed")
    print(f"SMOKE_RUN_ID={run.pk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
