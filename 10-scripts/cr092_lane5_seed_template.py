#!/usr/bin/env python3
"""ONE published work-order template on `brazosbend`, so screen 27 can be WALKED.

⚠ **THE WHOLE DATABASE HOLDS ZERO `work_order_templates`, ON EVERY TENANT.**
Measured 2026-09-13 with `app.tenant_id` set (RLS `FORCE` is on, so an unscoped
count reads 0 and looks like an empty table either way):

    select tenant_id, count(*) from work_order_templates group by 1   ->   []

So *"No template applies to this kind of asset."* is the ONLY state screen 27
(`/:tenant/assets/:assetId/work-orders/new`) has ever had in the running stack,
and the drawn state of blueprint figure 42 — a chosen template, a live submit —
could not be reached by anybody, ever. That is a demo-fixture gap rather than a
screen defect, and it is why this file exists instead of a paragraph saying the
happy path "should" work.

**UNRESTRICTED ON PURPOSE.** `apps/work/asset_door.templates_for_asset` reads
*this template names this asset's type, or it names no types at all* — a
template naming no asset types is not one that applies to none, it is one
nobody has restricted. Naming none is therefore the smallest seed that reaches
every asset, and it exercises the same code path a real utility's first
template takes.

**PUBLISHED, NOT DRAFT.** `version` 0 IS the draft state (`BR-WRK-011`), and
both `templates_for_asset` and `create_work_order` refuse a draft
(`BR-WRK-008`/`BR-WRK-012`). A seed at version 0 would have produced the same
empty picker with a different cause — a fixture that cannot tell a working read
from a broken one.

⚠ **`--drop` DEACTIVATES; IT DOES NOT DELETE.** Once an order has been raised
from a template the order's `template_id` references it under `on_delete=PROTECT`
(`BR-WRK-008` — the order remembers WHICH VERSION it came from, by copy rather
than by link), so a delete is refused by the database and should be. A
deactivated template is invisible to `templates_for_asset` by
`BR-WRK-012`/`BR-WRK-016`, which is the state this screen was in before, so the
undo is complete as far as any screen is concerned.

    python3 10-scripts/cr092_lane5_seed_template.py          # seed
    python3 10-scripts/cr092_lane5_seed_template.py --drop   # put it back

Run with the backend's own interpreter:
    DJANGO_SETTINGS_MODULE=config.settings.local \\
      /home/user/.venv-sbh/bin/python 10-scripts/cr092_lane5_seed_template.py
"""

from __future__ import annotations

import sys

import django

django.setup()

from django.db import connection  # noqa: E402

TENANT = "brazosbend"
NAME = "Annual backflow test"

#: The meter the walkthrough opens. Its test cadence is set BACKWARDS so that
#: `selectors.test_due` (BR-AST-007, `last_test_date + test_interval_months`
#: elapsed) answers true and the five-slot header's ATTENTION STRIP renders.
#:
#: ⚠ **NO ASSET ON THIS DATABASE CARRIES A `certification_due` OR A
#: `warranty_end` — 12 of 12 are NULL on the only tenant there is.** So
#: `assetAttention` answers `null` on every asset in the product and the strip
#: figure 42 draws has never been rendered by anybody. Proving it MOUNTS
#: therefore needs this row, and `--drop` puts all three columns back to the
#: NULL they hold today.
WALK_ASSET = "M-7001"


def main() -> int:
    drop = "--drop" in sys.argv
    with connection.cursor() as cur:
        cur.execute("select id from tenants where subdomain = %s", [TENANT])
        row = cur.fetchone()
        if row is None:
            print(f"no tenant {TENANT!r}")
            return 1
        tenant_id = row[0]
        # RLS FORCE is on: every read and write below needs the scope set.
        cur.execute("select set_config('app.tenant_id', %s, false)", [str(tenant_id)])
        if drop:
            cur.execute(
                "update work_order_templates set active = false "
                "where tenant_id = %s and name = %s",
                [tenant_id, NAME],
            )
            removed = cur.rowcount
            cur.execute(
                """
                update assets
                   set last_test_date = null,
                       test_interval_months = null,
                       certification_due = null
                 where tenant_id = %s and asset_no = %s
                """,
                [tenant_id, WALK_ASSET],
            )
            print(f"deactivated {removed} template(s); {WALK_ASSET} cadence cleared")
            return 0
        cur.execute(
            # `services` is a PLATFORM table — it has no tenant column at all
            # (the eleven service codes are the platform's, per the seed order
            # in CLAUDE.md). Take the first active one by its own sort.
            "select id from services where active order by sort limit 1"
        )
        service = cur.fetchone()
        if service is None:
            print("no active service on the platform")
            return 1
        # ⚠ **IDEMPOTENT, AND THE FIRST DRAFT WAS NOT.** It returned early on
        # *"already seeded"* — which after a `--drop` left the row present but
        # INACTIVE and skipped the cadence half entirely, so the tool reported
        # success and did nothing. That is hard-won law 7's *incapable of
        # failing* shape in four lines. Re-running now re-activates and re-sets
        # the cadence whatever state it finds.
        cur.execute(
            "update work_order_templates set active = true, version = 1 "
            "where tenant_id = %s and name = %s",
            [tenant_id, NAME],
        )
        existed = cur.rowcount > 0
        if not existed:
            cur.execute(
            """
            insert into work_order_templates
                (id, tenant_id, service_id, sequence, name, scope, is_gate,
                 is_sample, crew_size, version, active, created_at, updated_at)
                values (gen_random_uuid(), %s, %s, 1, %s, 'premise', false,
                        false, 1, 1, true, now(), now())
                """,
                [tenant_id, service[0], NAME],
            )
        cur.execute(
            """
            update assets
               set last_test_date = current_date - interval '13 months',
                   test_interval_months = 12,
                   certification_due = current_date - interval '11 days'
             where tenant_id = %s and asset_no = %s
            """,
            [tenant_id, WALK_ASSET],
        )
        verb = "re-activated" if existed else "seeded"
        print(f"{verb} {NAME!r} on {TENANT} (version 1, active, unrestricted)")
        print(f"{WALK_ASSET}: test overdue, certification due 11 days ago")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
