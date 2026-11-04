#!/usr/bin/env python3
"""Put `RBS-001`'s three states into a database, so the browser check has
something to look at.

CR-075 wave D task `D2`, the half a browser cannot do for itself.

WHY THIS EXISTS BESIDE `rbs_c_seed_run.py` RATHER THAN INSIDE IT
---------------------------------------------------------------
`rbs_c_seed_run.py` executes runbook 1 once and proves a Check wrote nothing
outside its own module. That is `C8`'s question and it is unchanged. `RBS-001`
needs something different: **several runs, in several states**, because the
screen's whole job is to sort them into *needs you*, *running now* and
*finished recently*.

⚠ **TWO OF THE FIVE ROWS ARE WRITTEN IN A STATE NO PRODUCT CODE CAN PRODUCE
TODAY, AND THAT IS SAID HERE RATHER THAN LEFT TO BE DISCOVERED.**
`services.open_run` opens a run at `running` and `close_run` lands it on `done`
or `failed`; nothing writes `awaiting_approval`, and a `running` row only exists
for the microseconds of its own request, because a Check runs synchronously
through `run_to_completion`. Those two statuses arrive with the acting half —
`CR-075` phase 2, waves `L`–`N`.

So this script **stamps them by hand**, exactly as `rbs_c_seed_run.py` writes
the `runbooks` row that `POST /runbooks` will one day write, and for the same
reason: without them the walkthrough could only ever see one of the screen's
three states, and *"the Needs you table draws nothing"* would be indisent from
*"the Needs you table is broken"*.

**What that costs, stated plainly:** this fixture proves the SCREEN can draw a
run awaiting approval. It does not prove the product can produce one. The
second half is wave `L`'s walkthrough, and pretending otherwise would be a
walkthrough that passes over a feature nobody has written.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/smartbillhub_rbsd2" \\
      python3 10-scripts/render-checks/rbs_d2_seed_home.py --tenant brazosbend

It prints the run ids the browser check reads back.
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
from django.utils import timezone  # noqa: E402

from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.registry import registry  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def ensure_runbook(tenant, definition):
    """The tenant's row for a shipped runbook, added if it is not there.

    `POST /runbooks` is wave `E1` and `seed_demo` creates no runbook at all, so
    without this the fixture has nothing to run. Every field comes from the
    SHIPPED definition's own metadata — nothing here invents a name, a kind or
    a category, and `origin` is `shipped` because that is what it is.
    """
    runbook = runbook_models.Runbook.objects.filter(tenant=tenant, key=definition.key).first()
    if runbook is not None:
        return runbook
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--runbook", default="configuration_check")
    parser.add_argument("--finished", type=int, default=3, help="how many real runs to execute")
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        print(
            f"⛔ REFUSED: running on {connection.vendor!r}. The tenant policies these rows live "
            "under do not exist on SQLite, so a green result here would mean nothing "
            "(hard-won law 7 — G5 once called 192 skips a pass).",
            file=sys.stderr,
        )
        return 2

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        print(f"⛔ no tenant with subdomain {args.tenant!r} — seed_demo first", file=sys.stderr)
        return 2

    with core_tenancy.tenant_context(tenant.id):
        definition = registry.get(args.runbook)
        runbook = ensure_runbook(tenant, definition)

        finished = []
        for _ in range(max(1, args.finished)):
            run, _result = services.run_to_completion(runbook, definition)
            finished.append(run)

        # ── the two states no product code writes yet — see this file's header
        waiting = services.open_run(runbook, definition)
        runbook_models.RunbookRun.objects.filter(pk=waiting.pk).update(
            status=runbook_models.RUN_STATUS_AWAITING_APPROVAL
        )
        in_flight = services.open_run(runbook, definition)
        runbook_models.RunbookRun.objects.filter(pk=in_flight.pk).update(
            status=runbook_models.RUN_STATUS_RUNNING,
            started_at=timezone.now(),
        )

        total = runbook_models.RunbookRun.objects.filter(tenant=tenant).count()

    print(f"── {len(finished)} finished run(s) executed through the engine")
    print("── 1 run stamped awaiting_approval and 1 stamped running (see the header)")
    print(f"SMOKE_TOTAL_RUNS={total}")
    print(f"SMOKE_AWAITING_ID={waiting.pk}")
    print(f"SMOKE_RUNNING_ID={in_flight.pk}")
    print(f"SMOKE_FINISHED_ID={finished[-1].pk}")
    print(f"SMOKE_RUNBOOK_KEY={runbook.key}")
    print(f"SMOKE_RUNBOOK_NAME={runbook.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-003 (CR-075 wave D task D2)
# generated: 2026-09-06 by the CR-075 wave D task D2 build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: run on real PostgreSQL only — it REFUSES SQLite by name
# exceptions: two rows are stamped into statuses no product code writes yet; the header says so and says what that costs
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
