#!/usr/bin/env python3
"""Read back what `cr092_lane2_wizard_walkthrough.mjs` created — FROM THE DATABASE.

CR-092-BRC01 step 2 wave C lane 2 · `AST-B-14` · `AST-B-27`.

⚠ **A GREEN SCREEN IS NOT THE PROOF FOR EITHER OF THESE.** The add wizard shows
a success toast whether or not the opening read reached `meter_reads` and
whether or not the allocation share reached `assets`, because both are written
by the server after the payload leaves. So the only honest check is to open the
row with `app.tenant_id` set and look.

⚠ **`app.tenant_id` IS THE WHOLE OF WHY THIS IS A SCRIPT AND NOT A `psql`
ONE-LINER.** RLS `FORCE` is on: without the setting every query here returns
ZERO ROWS, which reads exactly like *"the feature did not write anything"*.

    python3 10-scripts/cr092_lane2_readback.py L2-M-071530-1440 L2-S-071530-1440
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault(
    "DATABASE_URL", "postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub"
)

import django  # noqa: E402

django.setup()

from apps.assets import models as asset_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

TENANT = os.environ.get("TENANT", "brazosbend")


def main(asset_numbers: list[str]) -> int:
    tenant = Tenant.objects.get(code=TENANT)
    bad = 0
    with core_tenancy.tenant_context(str(tenant.id)):
        for asset_no in asset_numbers:
            asset = asset_models.Asset.objects.filter(asset_no=asset_no).first()
            if asset is None:
                print(f"MISSING  {asset_no} — no row")
                bad += 1
                continue
            reads = list(
                metering_models.MeterRead.objects.filter(asset_id=asset.id).order_by("read_at")
            )
            print(f"\n{asset_no}  ({asset.type.code})")
            print(f"  status            {asset.status.code}")
            print(f"  multiplier        {asset.multiplier}   unit {asset.unit}")
            print(f"  install_date      {asset.install_date}")
            print(f"  allocation share  {asset.allocation_share_pct}")
            print(f"  allocation rule   {asset.allocation_rule}")
            print(f"  meter_reads       {len(reads)}")
            for row in reads:
                print(
                    f"    · {row.read_at.date()}  value {row.current_value}"
                    f"  prior {row.prior_value}  unit {row.unit}"
                    f"  source {row.source}/{row.source_detail}  {row.lifecycle}"
                )
    return bad


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(1 if main(sys.argv[1:]) else 0)
