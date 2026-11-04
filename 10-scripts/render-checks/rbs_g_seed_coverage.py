#!/usr/bin/env python3
"""Run runbook 24 for real on the seeded utility, and fill the work list.

CR-075 wave G task `G5` and wave H task `H5` — the half a browser cannot do.

WHY THIS IS A SEPARATE SCRIPT AND NOT A MANAGEMENT COMMAND
-----------------------------------------------------------
`G115` refuses a foreign import anywhere under `06-backend/apps/runbooks/`
outside `seams/*_seam.py` and `ports/*_ports.py` (`BR-RBS-039`), and this script
reads `apps.customers` and `apps.rating` to REPORT what the grid found and to
change a rate. A fixture is not an exception to a boundary; it lives outside the
module, exactly as `rbs_f_seed_test_bill.py` and `rbs_c_seed_run.py` do.

WHAT IT DOES
------------
1. **Runs runbook 1 (*Can we bill?*)**, which raises its findings into
   `work_items` at close — the `J-RBS-1` half.
2. **Runs runbook 24 (the Coverage grid)**, which runs runbook 23 on each cell
   as a real CHILD RUN and raises one work item per cell that did not price
   cleanly — the `J-RBS-2` half.
3. **Prints the two run ids and the grid's own counts**, which the browser check
   opens and reads off the screen.
4. **Optionally re-runs both** (`--again`) so the walkthrough can watch a work
   item close itself when its finding stops recurring.

⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** (hard-won law 7's second habit):

  * **Counting outside the tenant context.** RLS `FORCE` shows a session with
    the default marker NOTHING, so every table reads 0 before and 0 after and
    *"nothing moved"* is true of an empty view rather than of the database.
    Every count here is taken inside `tenant_context`.
  * **A grid with one cell.** One clean cell reads *1 clean* and looks perfect.
    So the script REFUSES when the grid drew fewer than two cells, and prints
    how many plan-and-cycle combinations the estate actually holds beside how
    many were drawn.
  * **A grid whose cells link nowhere.** Every cell's address is resolved back
    to a `runbook_runs` row here, so the browser check is opening runs that
    exist rather than asserting that a string looks like an address.
  * **Running on SQLite**, where the tenant policies a Check runs under do not
    exist at all. It refuses any vendor but PostgreSQL.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/sbh_rbsgh" \\
      python3.12 10-scripts/render-checks/rbs_g_seed_coverage.py --tenant brazosbend

It prints `SMOKE_RUN_GRID`, `SMOKE_RUN_CHECK` and `SMOKE_CELL_RUN`, which the
browser check opens, and the figures it expects to read off each screen.
"""

from __future__ import annotations

import argparse
import json
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
from apps.runbooks import selectors as runbook_selectors  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.registry import registry  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

GRID = "coverage_grid"
CHECK = "configuration_check"
TEST_BILL = "test_bill"


def ensure_runbook(tenant, key):
    """The tenant's row for this shipped runbook, **added the way a clerk adds it**.

    ⚠ **`services.add_template`, NOT `Runbook.objects.create` — `DEF-RBS-4370`.**
    A hand-built row carries no `template_key`, and that one absent column makes
    the runbook PERMANENTLY UNRUNNABLE the moment the definition document moves:
    `open_run` refuses with *Template updated · Review →* while
    `selectors.pending_template_update` answers `None`, because only the offer
    requires the column. The refusal names an act nobody can perform. Wave T
    added two fields to `Parameter` on 2026-09-07 and every stored version moved
    at once, which is how this was found — three walkthrough seeds write rows
    this way and all three are in it.

    **The fixture presses the product's own button.** That is also the honest
    shape of the walkthrough: an implementer adds the template from the library.
    """
    row = runbook_models.Runbook.objects.filter(tenant=tenant, key=key).first()
    if row is not None:
        return row
    print(f"── no runbook row for {key!r}; adding it through services.add_template")
    return services.add_template(tenant.id, key)


def promote_real_accounts(tenant, how_many: int) -> int:
    """Give this utility some accounts of its OWN — `DEF-RBS-4369`.

    ⚠ **`seed_demo` MARKS EVERY ACCOUNT `is_sample=True`, SO THE COVERAGE GRID
    CORRECTLY DRAWS NOTHING ON IT.** `BR-RBS-014` — *a sample record is never
    picked* — is a GUARD, evaluated before any step, and it fired on all 72
    accounts of the demo tenant the first time this script ran. The grid was
    right and the fixture was the problem: a go-live artefact is a utility's own
    estate, and the demo estate is entirely demonstration data.

    So this promotes a few accounts to real ones, which is the honest shape of
    what an implementer's utility looks like. It clears the flag on the OWNING
    row, which is where `BR-TEN-057` puts it, and it says out loud how many it
    moved — a fixture that silently reshaped the estate would make the count on
    screen unreadable.

    ⚠ **IT PICKS BY ACCOUNT NUMBER, DETERMINISTICALLY**, so re-running this
    script promotes the same accounts and the grid's own determinism is not
    hidden behind a fixture that moves.
    """
    from apps.customers import models as customers_models

    already = customers_models.Account.objects.filter(is_sample=False).count()
    if already >= how_many:
        print(f"── {already} account(s) already belong to the utility; promoting none")
        return 0
    ids = list(
        customers_models.Account.objects.filter(is_sample=True)
        .exclude(unit_id=None)
        .order_by("account_no", "id")
        .values_list("id", flat=True)[: how_many - already]
    )
    moved = customers_models.Account.objects.filter(id__in=ids).update(is_sample=False)
    print(
        f"── promoted {moved} demo account(s) to the utility's OWN "
        f"(DEF-RBS-4369: seed_demo marks all {already + moved + 0} of them sample, and "
        "BR-RBS-014 correctly excludes a sample record from the pick)"
    )
    return moved


def take_the_offered_update(tenant, key) -> None:
    """Press *Review →* on this runbook's pending template update.

    ⚠ **A PENDING TEMPLATE UPDATE STOPS A RUN, INCLUDING A CHILD RUN**
    (`BR-RBS-038`, wave `E2`): the stored version and the live module have
    diverged, so pinning the stored number would put a version on a report that
    did not produce it. On a database seeded before today's definition changes
    that is exactly the state runbook 23 is in, and the grid's cells inherit the
    refusal — which is `DEF-RBS-4363`, found by this script on its first real
    run.

    **The fixture presses the button rather than reaching past the rule**, which
    is what an implementer would do, and it is the one act that clears it.
    """
    runbook = ensure_runbook(tenant, key)
    version = services.accept_template_update(runbook)
    if version is not None:
        print(f"── {key}: took the offered template update → version {version.version}")


def run(tenant, key, *, params=None):
    definition = registry.get(key)
    runbook = ensure_runbook(tenant, key)
    defaults = {p.name: p.default for p in definition.parameters if p.default is not None}
    defaults.update(params or {})
    return services.run_to_completion(runbook, definition, params=defaults)


def block(report, name):
    for entry in report or []:
        if entry.get("block") == name:
            return entry.get("payload") or {}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--cells", type=int, default=25)
    parser.add_argument(
        "--promote",
        type=int,
        default=40,
        help=(
            "how many demo accounts to make the utility's OWN before running. "
            "seed_demo marks every account sample and BR-RBS-014 excludes those from "
            "the pick, so a grid over the demo estate is correctly empty (DEF-RBS-4365)"
        ),
    )
    parser.add_argument(
        "--again",
        action="store_true",
        help="run both a second time, so a work item that stopped recurring can be watched closing",
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

    with core_tenancy.tenant_context(tenant.id):
        ensure_runbook(tenant, TEST_BILL)
        for key in (TEST_BILL, CHECK, GRID):
            take_the_offered_update(tenant, key)
        promote_real_accounts(tenant, args.promote)

        check_run, _check_result = run(tenant, CHECK)
        grid_run, grid_result = run(tenant, GRID, params={"accounts": args.cells})

        picked = grid_result.set_results.get("pick") or {}
        records = block(grid_run.report, "records")
        rows = records.get("rows") or []
        tiles = block(grid_run.report, "kpis").get("tiles") or []
        sentence = block(grid_run.report, "sentence").get("text", "")

        cell_runs = []
        for row in rows:
            link = (row.get("cells") or {}).get("open") or {}
            to = str(link.get("to") or "")
            run_id = to.rsplit("/", 1)[-1]
            child = runbook_models.RunbookRun.objects.filter(pk=run_id).first()
            cell_runs.append(
                {
                    "to": to,
                    "exists": child is not None,
                    "runbook": None if child is None else child.runbook.key,
                    "parent": None if child is None else str(child.parent_run_id),
                }
            )

        work = runbook_selectors.work_items_page(tenant.id, per=200)
        counts = runbook_selectors.work_item_counts(tenant.id)

        again = None
        if args.again:
            again_run, _again = run(tenant, GRID, params={"accounts": args.cells})
            again = {
                "run_id": str(again_run.pk),
                "counts": dict(again_run.counts or {}),
            }

    if len(rows) < 2:
        print(
            f"⛔ REFUSED: the grid drew {len(rows)} cell(s). One clean cell reads '1 clean' and\n"
            f"   looks perfect; this estate holds {picked.get('groups_found')} plan-and-cycle\n"
            "   combination(s). A walkthrough over one cell proves nothing (hard-won law 7).",
            file=sys.stderr,
        )
        return 2

    dead = [cell for cell in cell_runs if not cell["exists"]]
    if dead:
        print(
            f"⛔ REFUSED: {len(dead)} cell(s) point at a run that does not exist. A cell that "
            "opens onto nothing is the defect this runbook was built to avoid.",
            file=sys.stderr,
        )
        return 2

    print("\n── the grid, as a clerk reads it ──────────────────────────────")
    for tile in tiles:
        # `KpisPayload.tiles[].value` is a `ReportValue` — `{kind, text}` — and
        # not a bare string (`DEF-RBS-4375`, which is what a bare string cost on
        # screen). Printed as its text, so this script says the same number the
        # strip draws.
        print(f"   {tile['value']['text']:>4}  {tile['label']}")
    print(f"   sentence: {sentence}")
    print(f"   cells found {picked.get('groups_found')} · drawn {picked.get('cells_drawn')} · "
          f"left out {picked.get('cells_left_out')} · sample excluded {picked.get('excluded_sample')} "
          f"· no unit {picked.get('excluded_no_unit')}")
    print(f"   run counts: {json.dumps(dict(grid_run.counts or {}), sort_keys=True)}")

    print("\n── the work list ─────────────────────────────────────────────")
    print(f"   chips: {json.dumps(counts, sort_keys=True)}")
    for row in work["rows"][:10]:
        print(f"   [{row['weight_pill']:>16}] {row['from'] or 'a person'} · {row['title'][:70]}")
    if again is not None:
        print(f"\n── the second grid run: {json.dumps(again, sort_keys=True)}")

    print("\n── for the browser check ─────────────────────────────────────")
    print(f"SMOKE_RUN_GRID={grid_run.pk}")
    print(f"SMOKE_RUN_CHECK={check_run.pk}")
    print(f"SMOKE_CELL_RUN={cell_runs[0]['to'].rsplit('/', 1)[-1]}")
    print(f"SMOKE_CELLS={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
