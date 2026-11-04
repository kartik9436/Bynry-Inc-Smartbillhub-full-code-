"""CR-157-BRC10 wave C part 2 — make every matrix row billable on ONE account.

The wave C walk previews a one-time bill for AC-2026-00001 (`brazosbend`). On
the sample data that account bills only electric, water, sewer (as a share of
water) and trash, its meters carry no time-of-use or demand register, and it
has no gas, fire, broadband, storm water, solar, thermal or battery service it
can be billed for. This puts the missing facts on it, in a PRIVATE walk
database only — it is a fixture for the walk, never a seed change:

  * Settings › Services: sewer's billing basis `metered` (a utility that reads
    a sewer meter; a percent-of-water schedule still follows its basis) —
    through the Settings API, as a clerk.
  * Assets › Add asset, as a clerk (`POST /assets`, S51): a gas meter, a sewer
    meter, and one counted asset with a recorded size for fire, storm water,
    solar, thermal/heat and battery; broadband's existing modem gets its size.
    The size is the FIRST size the walk's schedules price for the service, so
    the minimum per size is on the bill.
  * The account's service agreements for every point on its unit that has
    none — there is no clerk door that adds a service to an open account, so
    this is written through the model, the way the seeders write it.
  * Committed reads for 09-30, 10-31 and 11-30 on every meter (total, and the
    time-of-use and peak-demand registers), so October and November each bill
    their own month: electric 500 / 600 kWh (on-peak 150 / 180, off-peak
    350 / 420, peak 12.5 / 14.0 kW), water 1 + 5 then 2 + 10 kgal, gas 40 / 50
    ccf, sewer 4 / 5 kgal.

  * Storm water and thermal/heat are SUMMED from a fact on the UNIT, not
    from the asset (`metering.connections.UNIT_CAPACITY_CHARACTERISTIC`):
    without it their bill line reads 0 ERU / 0 ton. Recorded as a clerk,
    `PUT /connections/{premises}/units/{unit}/characteristics/assessment`
    (6 ERU, SW-APT's capacity) and `.../connected_capacity` (5 ton, TH-T5).

⚠ Run on 2026-10-01, the Settings and Add-asset halves below refused outside
a request (`AUTH-002` — no request context for the permission check), so
those were done through the same API calls a clerk's screen makes: sewer's
basis, the premises' services, the seven assets and the two characteristics.
The agreements and the reads are this script's own work.

Run once, idempotently, against the walk database:
    DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
      python 10-scripts/rswalk_billable_setup.py
"""

from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.assets import models as am  # noqa: E402
from apps.assets import services as asset_services  # noqa: E402
from apps.customers import models as cm  # noqa: E402
from apps.identity import models as im  # noqa: E402
from apps.metering import models as mm  # noqa: E402
from apps.tenancy import models as tm  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

TENANT = tm.Tenant.objects.get(subdomain="brazosbend")
ACCOUNT_NO = "AC-2026-00001"

# service → (asset type, asset no, unit, size)
NEW_ASSETS = {
    "gas": ("meter", "G-WC-1", "ccf", "G-250"),
    "sewer": ("meter", "S-WC-1", "kgal", None),
    "fire": ("fire_line", "FL-WC-1", "connection", "FL-2"),
    "storm_water": ("meter", "SW-WC-1", "ERU", "SW-APT"),
    "solar": ("pv", "PV-WC-1", "kW", "SOL-P1"),
    "thermal_heat": ("meter", "TH-WC-1", "ton", "TH-T5"),
    "battery": ("battery", "BAT-WC-1", "kW", "BAT-5"),
}
# meter → {channel: (09-30, 10-31, 11-30)}
READS = {
    "E-55120": {"total": (18900, 19400, 20000), "tou_on": (5000, 5150, 5330), "tou_off": (9000, 9350, 9770), "demand": (11.0, 12.5, 14.0)},
    "W-10442": {"total": (483.0, 484.0, 486.0), "tou_on": (10, 10.4, 11.2), "tou_off": (20, 20.6, 21.8), "demand": (1.0, 1.2, 1.5)},
    "W-10443": {"total": (131.0, 136.0, 146.0), "tou_on": (10, 12, 16), "tou_off": (20, 23, 29), "demand": (1.0, 1.3, 1.6)},
    "G-WC-1": {"total": (1000, 1040, 1090), "tou_on": (100, 112, 127), "tou_off": (200, 228, 263), "demand": (2.0, 2.5, 3.0)},
    "S-WC-1": {"total": (100, 104, 109), "tou_on": (10, 11, 13), "tou_off": (20, 23, 26), "demand": (0.5, 0.6, 0.7)},
}
UNITS = {"E-55120": "kWh", "W-10442": "kgal", "W-10443": "kgal", "G-WC-1": "ccf", "S-WC-1": "kgal"}
DAYS = ("2026-09-30", "2026-10-31", "2026-11-30")


def main() -> None:
    with tenant_context(TENANT.id):
        actor = im.User.objects.get(email="dana@brazosbendutilities.com")
        account = cm.Account.objects.get(account_no=ACCOUNT_NO)
        unit_id = str(account.unit_id)

        # Settings › Services — sewer read from a meter (the clerk's setting).
        ts = tm.TenantService.objects.get(tenant=TENANT, service__code="sewer")
        if ts.billing_basis != tm.BILLING_BASIS_METERED:
            tenancy_services.update_tenant_service(actor, "sewer", {"billing_basis": "metered"})
            print("sewer billing basis -> metered")

        # Assets › Add asset (S51), the clerk's service.
        for service, (kind, asset_no, uom, size) in NEW_ASSETS.items():
            if am.Asset.objects.filter(asset_no=asset_no).exists():
                continue
            payload = {
                "type": kind, "asset_no": asset_no, "service": service, "unit": uom,
                "unit_id": unit_id, "install_date": "2026-01-05", "status": "active",
            }
            if kind in ("meter",):
                payload.update({"read_method": "manual", "multiplier": "1", "register_digits": 6})
            if size:
                payload["size_class"] = size
            asset_services.create_asset(actor, payload)
            print("asset", asset_no, service, size)
        modem = am.Asset.objects.get(asset_no="R-2201")
        if not modem.size_class:
            modem.size_class = "BB-100"
            modem.save(update_fields=["size_class", "updated_at"])
            print("R-2201 size BB-100")

        # The account takes every service its unit is connected for.
        for sp in mm.ServicePoint.objects.filter(unit_id=unit_id, deleted_at__isnull=True):
            if not cm.ServiceAgreement.objects.filter(account=account, service_point=sp, ended_on__isnull=True).exists():
                cm.ServiceAgreement.objects.create(
                    tenant=TENANT, account=account, service_point=sp, started_on=date(2025, 7, 1)
                )
                print("agreement", sp.service.code)

        # Committed reads, one month each.
        for asset_no, channels in READS.items():
            asset = am.Asset.objects.get(asset_no=asset_no)
            for channel, values in channels.items():
                unit = "kW" if channel == "demand" else UNITS[asset_no]
                prior = None
                for day, value in zip(DAYS, values):
                    when = tm_datetime(day)
                    if mm.MeterRead.objects.filter(asset=asset, read_at=when, channel=channel).exists():
                        prior = Decimal(str(value))
                        continue
                    current = Decimal(str(value))
                    consumption = None
                    if channel == "demand":
                        consumption = current
                    elif prior is not None:
                        consumption = current - prior
                    mm.MeterRead.objects.create(
                        tenant=TENANT, asset=asset, read_at=when, channel=channel,
                        prior_value=prior, current_value=current, multiplier=Decimal("1"),
                        consumption=consumption, unit=unit, source="manual", status="ok",
                        lifecycle="committed", period_start=None if prior is None else date.fromisoformat(DAYS[DAYS.index(day) - 1]),
                    )
                    prior = current
            print("reads", asset_no)


def tm_datetime(day: str):
    from datetime import datetime, timezone

    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)


if __name__ == "__main__":
    main()
