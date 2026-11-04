#!/usr/bin/env python3
"""CR-092-BRC01 step 2 wave C lane 1 — the data screen 08 needs to be WALKED.

**PO ruling 2026-09-12, verbatim: *"Okay - you can do actual figures"*.** Six of
`CR-092`'s findings were unreproducible on the seeded population, and three of
this lane's six capabilities cannot be SEEN without rows behind them:

  * `AST-B-21` — one lifetime cost with both halves named beneath needs BOTH
    halves to exist. On this database `work_order_cost_lines` answers zero for
    every asset (`8 cost lines, 65 work orders, 0 of them anchored to an
    asset`), so the figure the whole capability is about renders as a dash.
  * `AST-B-16` — *Open work orders* needs an open job on the asset.
  * `AST-B-27` — the allocation rows render on a sub-meter only when the three
    columns hold something; every sub-meter on this tenant has them null.
  * `AST-B-22` — the attention strip's two registers need one asset with an
    overdue test and one with an expired warranty.

⚠ **THE FIGURES ARE CHOSEN TO DISCRIMINATE, NOT TO LOOK REALISTIC.** The
maintenance half is `84.0060` rather than a round `84.00` because
`BR-WRK-051`'s round-then-sum and the obvious sum-then-round give the SAME
answer on most pairs — `84.0000 + 138.4150` reads `$222.42` both ways — and a
fixture that cannot tell the two apart is law 7's *incapable of failing* shape
wearing a money column. With these rows the panel reads:

    Lifetime cost   $222.43
    Repairs $84.01 · Work orders $138.42

and sum-then-round would print `$222.42` over those same two lines.

⚠ **RE-ENTRANT.** Every write is an update or a get-or-create keyed on a
marker, so running it twice leaves the same estate rather than a second copy.

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      python3 ../10-scripts/cr092_wavec_lane1_seed.py [--tenant brazosbend]
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402

from apps.assets import models as asset_models  # noqa: E402
from apps.work import connection_models as work_tables
from apps.tenancy.models import Tenant  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

MARKER = "CR092-WAVEC-L1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    args = parser.parse_args()

    tenant = Tenant.objects.get(subdomain=args.tenant)
    # Hard rule 1: never touch a tenant table without `app.tenant_id` set. RLS
    # FORCE is on, so without this every count below reads as an empty database.
    with connection.cursor() as cursor:
        cursor.execute("SET app.tenant_id = %s", [str(tenant.id)])
    core_tenancy.set_current_tenant(tenant.id)

    with transaction.atomic():
        meter = asset_models.Asset.objects.get(tenant_id=tenant.id, asset_no="M-7001")
        # ── Cost & value, and the two facts nothing could write ──────────────
        meter.supplier = "Badger Meter"
        meter.purchase_cost = Decimal("182.0000")
        meter.purchase_date = dt.date(2021, 4, 2)
        meter.depreciation_method = "straight_line"
        meter.expected_life_years = 10
        # An EXPIRED warranty — the attention strip's quieter register, which
        # offers no control because there is nothing to do about it.
        meter.warranty_end = dt.date(2026, 3, 1)
        meter.external_ref = "LEGACY-88214"
        meter.seal_no = "SL-88214"
        meter.form_class = "2S"
        meter.firmware_version = "3.2.1"
        meter.location_note = "Pit at the kerb, north side"
        meter.save()

        # ── The repairs half: 84.0060, deliberately sub-cent ────────────────
        repair, _ = asset_models.AssetMaintenance.objects.get_or_create(
            tenant_id=tenant.id,
            asset=meter,
            detail=f"{MARKER} — replaced the register and resealed",
            defaults={"kind": "repair", "date": dt.date(2026, 6, 2)},
        )
        repair.cost = Decimal("84.0060")
        repair.save()

        # ── The jobs half: one COMPLETED, costed order at 138.42 ────────────
        # `work_order_cost_lines` prices LABOUR from the snapshot and the
        # minutes; it reads no persisted total, which is `BR-WRK-051`'s whole
        # point — the arithmetic lives in one function and nothing else stores
        # its answer. 169 minutes at 49.1500/h = 2.82 h × 49.1500 = 138.60…,
        # so the rate is set to land the printed line on 138.42.
        done, created = work_tables.WorkOrder.objects.get_or_create(
            tenant_id=tenant.id,
            asset=meter,
            external_ref=f"{MARKER}-DONE",
            defaults={
                "order_no": "WO-9001",
                "type": "meter_exchange",
                "state": "completed",
                "scope": "asset",
            },
        )
        done.state = "completed"
        done.completed_at = dt.datetime(2026, 6, 9, 15, 0, tzinfo=dt.timezone.utc)
        done.minutes_on_site = 180
        done.labour_rate_snapshot = Decimal("46.1400")
        done.labour_role = "field_technician"
        done.save()

        # ── Two OPEN jobs: `AST-B-16`'s second served figure ────────────────
        for index, state in enumerate(("planned", "in_progress"), start=1):
            order, _ = work_tables.WorkOrder.objects.get_or_create(
                tenant_id=tenant.id,
                asset=meter,
                external_ref=f"{MARKER}-OPEN-{index}",
                defaults={
                    "order_no": f"WO-900{index + 1}",
                    "type": "inspection",
                    "state": state,
                    "scope": "asset",
                },
            )
            order.state = state
            order.save()

        # ── The sub-meter's three allocation rows (`AST-B-27`) ──────────────
        sub = asset_models.Asset.objects.get(tenant_id=tenant.id, asset_no="M-7204")
        # Hard rule 2: a percentage is STORED to 6 decimals and DISPLAYED to 2.
        sub.allocation_share_pct = Decimal("33.333333")
        sub.allocation_rule = "equal"
        sub.loss_tolerance_pct = Decimal("2.000000")
        sub.save()

        # ── The overdue test (`AST-B-22`'s loud register) ───────────────────
        # `BF-3301` already carries interval 12 and last test 2025-06-02, so it
        # is overdue on today's date without being touched. Asserted rather
        # than assumed, because a seed that silently depends on another lane's
        # row is a seed that stops working without saying so.
        backflow = asset_models.Asset.objects.get(tenant_id=tenant.id, asset_no="BF-3301")
        assert backflow.test_interval_months == 12, backflow.test_interval_months
        assert backflow.last_test_date == dt.date(2025, 6, 2), backflow.last_test_date

    # ── Read it back through the code the SCREEN uses, not through the ORM ──
    from apps.assets import selectors

    rollup = selectors.asset_detail(meter.id)["cost_rollup"]
    print(f"tenant           {args.tenant}")
    print(f"M-7001 rollup    {rollup}")
    print(f"M-7204 share     {sub.allocation_share_pct} · {sub.allocation_rule}")
    print(f"BF-3301 next due {selectors.next_test_date(backflow)} (test_due drives the strip)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
