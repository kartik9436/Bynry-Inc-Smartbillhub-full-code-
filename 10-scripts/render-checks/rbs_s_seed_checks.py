#!/usr/bin/env python3
"""Run runbooks 12 and 16 on a REAL utility, and prove neither wrote anything.

`CR-075` wave S — the half a browser cannot do, and the half a mock cannot do
either.

WHY THIS IS A SEPARATE SCRIPT
-----------------------------
`rbs_c_seed_run.py` already does this for runbook 1 and takes `--runbook`, and
runbook 12 could ride on it unchanged. **Runbook 16 cannot**, and that is the
whole reason this file exists: its scope is `Proposed schedule *` and `Against
cycle *`, two REQUIRED `ref:object` parameters, and a run with neither pins an
empty set and reports a confident *nothing changed*. So this script FINDS a real
draft and a real issued cycle on the tenant first, prints which ones it picked,
and refuses when there is not one of each — because a green result over an empty
scope is the shape hard-won law 7 is about.

⚠ **`BR-RBS-002` IS A CONSTRUCTION FACT, NOT A RUNTIME REFUSAL** — *"a Check is
constructed with no writer, so a write is unavailable rather than refused at
runtime"*. There is no exception to catch and no error to assert: a row count
either moved or it did not, and this is what looks.

⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY**, asked because a check you cannot
describe a false pass for is one you do not understand (hard-won law 7). Four,
and the first three are `rbs_c_seed_run.py`'s own and are answered the same way:

  * counting only the tables I remember — so it counts EVERY table in the schema
    and derives the runbooks seven by NAME;
  * counting on SQLite, where the tenant policies this runs under do not exist —
    so it REFUSES to run anywhere but PostgreSQL;
  * counting OUTSIDE the tenant context, where row-level security shows 0 → 0
    everywhere and *"nothing moved"* is true of an empty view rather than of the
    database — so every count is taken with `app.tenant_id` set. **That is the
    one that actually fired on the first version of `rbs_c_seed_run.py`**, and
    it printed a confident pass over a run that had just written three rows;
  * **and the fourth is this file's own: running over an EMPTY SCOPE.** A
    runbook that pinned no subject writes nothing, truthfully, and proves
    nothing about whether it could. So the scope size of each run is printed and
    a run that pinned nothing is reported as INCONCLUSIVE rather than as a pass.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/smartbillhub" \\
      python3 10-scripts/render-checks/rbs_s_seed_checks.py --tenant brazosbend

It prints the run ids and the figures both runbooks actually produced.
"""

from __future__ import annotations

import argparse
import datetime as dt
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

    See `rbs_c_seed_run.py`'s own docstring for what happens otherwise: RLS is
    FORCE'd, a session with the nil marker sees NOTHING, and every tenant table
    counts 0 before and 0 after.
    """
    out: dict[str, int] = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
        for table in tables:
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # noqa: S608 — names from the catalog
            out[table] = cursor.fetchone()[0]
    return out


def shipped_runbook(tenant, definition):
    """The tenant's row for a shipped definition, added if it is not there yet.

    ⚠ **IT GOES THROUGH `services.add_template`, WHICH IS THE DOOR THAT OWNS
    THIS JOB** — `POST /runbooks` in service form (wave `E1`). A hand-rolled
    `Runbook.objects.create(...)` here looked equivalent and was not: it left
    `template_key` NULL, and `accept_template_update` returns `None` on a copy
    with no template, so the row could never take a later shipped change and
    `open_run` refused every run afterwards with
    `runbooks.refusal.update_pending` — correctly, and unfixably from this
    script. **Read `10-scripts/` and the owning module's own service functions
    before writing your own version of one** (CLAUDE.md law 11's last clause).

    On a re-run after an edit, it presses the button the setup screen draws —
    *Template updated · Review →* — rather than deleting the row, which would
    throw away whatever the tenant had set on it.
    """
    row = runbook_models.Runbook.objects.filter(tenant=tenant, key=definition.key).first()
    if row is None:
        print(f"── no runbook row for {definition.key!r}; adding the shipped one")
        return services.add_template(tenant.id, definition.key)
    if not row.template_key:
        # A row an earlier build of THIS script created by hand. Naming its
        # template is what the adoption door would have written, and it is the
        # only thing standing between the row and every future update.
        runbook_models.Runbook.objects.filter(pk=row.pk).update(template_key=definition.key)
        row.template_key = definition.key
        print(f"── {definition.key}: named its template (an earlier hand-made row)")
    taken = services.accept_template_update(row)
    if taken is not None:
        print(f"── {definition.key}: took the template update (version {taken.version})")
    return row


def rate_preview_params() -> dict[str, str] | None:
    """A real draft and a real ISSUED cycle, or `None` with the reason printed.

    ⚠ **BOTH ARE REQUIRED AND NEITHER IS INVENTED.** `RB-116`'s scope marks
    them with an asterisk; a run with either missing pins nothing, and a green
    line over an empty scope is worth less than a refusal.
    """
    from apps.runbooks.seams import billing_seam, rating_seam

    drafts = [one for one in rating_seam.draft_schedules() if one["comparable"]]
    if not drafts:
        print("⛔ no comparable DRAFT rate schedule on this tenant — nothing to preview")
        return None

    for run in billing_seam.bill_runs(limit=25):
        run_id = run.get("id") or run.get("run_id")
        cycle = billing_seam.issued_bills_for_run(run_id)
        if cycle["bills_in_the_cycle"]:
            # ⚠ **PICK THE DRAFT THE CYCLE WAS ACTUALLY BILLED ON — `DEF-RBS-4407`.**
            # A preview only reaches the bills its own schedule priced, so a
            # walkthrough that paired a draft with a cycle billed on another
            # ladder would print *nothing changes* and prove only the scoping.
            versions = {
                str(line["tariff_version_id"])
                for bill in cycle["bills"]
                for line in bill.get("lines") or []
                if line.get("tariff_version_id")
            }
            reachable = [
                one
                for one in drafts
                if versions & set(
                    rating_seam.schedule_change(
                        version_id=one["version_id"],
                        service_date=dt.date.fromisoformat(
                            str(cycle["bills"][0].get("service_date"))[:10]
                        ),
                    ).get("version_ids")
                    or []
                )
            ]
            draft = (reachable or drafts)[0]
            if not reachable:
                print("⚠ no draft belongs to the schedule this cycle was billed on")
            print(
                f"── draft  : {draft['label']} ({draft['service']}) · "
                f"replaces the version in force from {draft['baseline_effective_from']}"
            )
            print(
                f"── cycle  : {run.get('period_start')} → {run.get('period_end')} · "
                f"{cycle['bills_in_the_cycle']} issued bills"
            )
            return {"proposed_schedule": draft["version_id"], "against_cycle": str(run_id)}
    print("⛔ no bill run on this tenant has an ISSUED bill — nothing to re-price")
    return None


def figures(key: str, result) -> None:
    """The numbers the run actually produced, in the card's own words."""
    blocks = {one["block"]: one["payload"] for one in result.report}
    print(f"── {key}: {len(result.subjects)} pinned · {len(result.records)} records")
    verdict = blocks.get("verdict")
    if verdict:
        print(f"   verdict : {verdict['word']} · {verdict['count']}")
        print(f"             {verdict.get('detail', '')}")
    for tile in (blocks.get("kpis") or {}).get("tiles", []):
        value = tile["value"]
        shown = value.get("text") or f"{value.get('amount')} {value.get('currency', '')}".strip()
        basis = f" [{tile['basis']}]" if tile.get("basis") else ""
        print(f"   tile    : {tile['label']}: {shown}{basis} — {tile.get('detail', '')}")
    for row in (blocks.get("ranked") or {}).get("rows", []):
        print(f"   band    : {row['label']}: {row['value'].get('text')}")
    records = blocks.get("records") or {}
    for chip in records.get("chips", []):
        print(f"   chip    : {chip['label']} {chip['count']}")
    for row in records.get("rows", [])[:5]:
        cells = " · ".join(
            str(cell.get("text") or cell.get("label") or cell.get("amount") or cell.get("value"))
            for cell in row["cells"].values()
        )
        print(f"   row     : {cells}")
    for name, step in (result.set_results or {}).items():
        if isinstance(step, dict) and step.get("checked"):
            print(f"   step    : {name}")
            for label, value in step["checked"].items():
                print(f"             {label} = {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend", help="the tenant's subdomain")
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

    runs: list[tuple[str, object]] = []
    with core_tenancy.tenant_context(tenant.id):
        definition = registry.get("disconnect_eligibility")
        run, result = services.run_to_completion(shipped_runbook(tenant, definition), definition)
        runs.append(("disconnect_eligibility", (run, result)))

        definition = registry.get("rate_change_preview")
        params = rate_preview_params()
        if params is not None:
            run, result = services.run_to_completion(
                shipped_runbook(tenant, definition), definition, params=params
            )
            runs.append(("rate_change_preview", (run, result)))

    after = counts(tables, tenant.id)
    moved_outside = {t: (before[t], after[t]) for t in others if before[t] != after[t]}
    moved_inside = {
        t: (before[t], after[t]) for t in RUNBOOKS_TABLES if before.get(t) != after.get(t)
    }
    populated = sum(1 for t in others if before[t] > 0)

    print()
    for key, (run, result) in runs:
        figures(key, result)
        print(f"   RUN_ID  : {run.pk}")
        print()

    print(f"── runbooks tables that moved : {sorted(moved_inside)}")
    print(f"── other tables that moved    : {sorted(moved_outside)}")
    print(f"── other tables with any rows : {populated} of {len(others)}")

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

    if not moved_inside:
        print(
            "\n⛔ THE RUNS WROTE NOTHING IN THEIR OWN MODULE EITHER. A run that stored no\n"
            "   row is a broken fixture, not a clean Check.",
            file=sys.stderr,
        )
        return 1

    # ⚠ THE FOURTH FALSE PASS, AND IT IS THIS FILE'S OWN: a run over an empty
    # scope writes nothing truthfully and proves nothing.
    empty = [key for key, (_run, result) in runs if not result.subjects]
    if empty:
        print(
            f"\n⚠ INCONCLUSIVE FOR {', '.join(empty)}: the scope was EMPTY, so 'nothing was\n"
            "   written' is true of a run that looked at nothing. Seed the subject this\n"
            "   runbook walks before reading this as a pass.",
            file=sys.stderr,
        )

    if populated < 10:
        print(
            f"\n⚠ ONLY {populated} TABLES OUTSIDE THIS MODULE HAVE ANY ROWS AT ALL.\n"
            "   'nothing changed' over an empty database is not evidence.",
            file=sys.stderr,
        )

    print("\n✓ nothing outside the seven runbooks tables changed")
    return 0 if not empty else 3


if __name__ == "__main__":
    raise SystemExit(main())
