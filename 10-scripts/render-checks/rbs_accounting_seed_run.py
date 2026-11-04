#!/usr/bin/env python3.12
"""Execute runbook 36, store the run, and WRITE THE FILE OUT so it can be opened.

The half of the walkthrough a browser cannot do, for the same reason
`rbs_c_seed_run.py` exists: **there has to BE a run to look at**, and
`POST /runbooks/{key}/runs` is task `L` — every runbooks route that exists today
is a `GET`. So the run is made here, through the same engine call the future
endpoint will make, rather than by pretending the button exists.

⚠ **AND IT WRITES THE CSV TO DISK, WHICH IS NOT A CONVENIENCE.** The Product
Owner's definition of done is *open the file*. No address serves a six-column
general journal yet (`DEF-RBS-4312` — the two result files carry the nine RECORD
columns, which hold no date and no account code), so the file is written here
from the run that a clerk's Run ▶ will produce, and the walkthrough opens THAT.
**It is the same bytes `journal_csv()` returns to a future route**, composed by
the same call on the same books; what is missing is the door, not the file.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/<db>" \\
      python3.12 10-scripts/render-checks/rbs_accounting_seed_run.py \\
        --tenant brazosbend --out /tmp/rbs-accounting

It prints the run id (`SMOKE_RUN_ID` for the browser check) and the path of the
CSV it wrote, and it REFUSES to run anywhere but PostgreSQL — the seven tables
are RLS-forced and a green obtained on SQLite would be a green over a guarantee
that does not exist there (`G5` called 192 skips a pass once).
"""

from __future__ import annotations

import argparse
import csv
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

from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.definitions import accounting_export as rb36  # noqa: E402
from core.tenancy import tenant_context, tenant_id_for_slug  # noqa: E402

KEY = "accounting_export"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--out", default="/tmp/rbs-accounting")
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        print(f"REFUSED: vendor is {connection.vendor!r}. The seven tables are RLS-forced and")
        print("         a run stored on SQLite proves nothing about the guarantee.")
        return 2

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    tenant_id = tenant_id_for_slug(args.tenant)
    with tenant_context(tenant_id):
        definition = rb36.RUNBOOK
        runbook = _adopt(definition, tenant_id)
        # ⚠ `services.run_to_completion`, NOT `executor.execute`. **THE EXECUTOR
        # WRITES NO ROW AT ALL** — its own docstring says so: it pins a scope,
        # walks steps and composes a report, and something else opens, stamps
        # and closes the run. A script that called the executor would print
        # `SMOKE_RUN_ID=None` and leave the browser check with nothing to open.
        run, result = services.run_to_completion(runbook, definition)

    state = result.set_results[rb36.STEP_FILE]["checked"]
    csv_path = out / state["file_name"]
    csv_path.write_text(state["csv"], encoding="utf-8")

    rows = list(csv.reader(state["csv"].splitlines()))
    body = rows[1:]
    debits = sum(Decimal(row[3]) for row in body)
    credits = sum(Decimal(row[4]) for row in body)

    print(f"run id     : {run.id}")
    print(f"months     : {', '.join(s.label for s in result.subjects)}")
    print(f"file       : {csv_path}")
    print(f"header     : {','.join(rows[0])}")
    print(f"lines      : {len(body)}")
    print(f"debits     : {debits}")
    print(f"credits    : {credits}")
    print(f"balanced   : {debits == credits}")
    blocked = [
        row
        for key in rb36.STEP_LABELS
        for row in (result.set_results.get(key) or {}).get("blocked") or []
    ]
    print(f"blocked    : {len(blocked)}")
    for row in blocked:
        print(f"   · {row['reason']}  [{row['weight']}]  {row['affects']}")
    return 0


def _adopt(definition, tenant_id):
    """Put the shipped runbook on the tenant — the row `POST /runbooks` writes.

    ⚠ **ADDED HERE BECAUSE NOTHING ELSE CAN ADD IT YET**, exactly as
    `rbs_c_seed_run.py` does for runbook 1: adopting a template is wave `E1`'s
    endpoint and `seed_demo` creates no runbooks at all. Every field comes from
    the SHIPPED definition's own metadata — nothing here invents a name, a kind
    or a category — and `origin` is `shipped`, because this is the template
    being adopted rather than a tenant's clone.
    """
    runbook = runbook_models.Runbook.objects.filter(
        tenant_id=tenant_id, key=definition.key
    ).first()
    if runbook is not None:
        return runbook
    print(f"── no runbook row for {definition.key!r}; adding the shipped one")
    return runbook_models.Runbook.objects.create(
        tenant_id=tenant_id,
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


if __name__ == "__main__":
    raise SystemExit(main())
