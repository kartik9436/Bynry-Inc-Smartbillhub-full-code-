"""CR-157-BRC10 wave C — the rate-schedule walk's DATABASE and BILLING probe.

`10-scripts/rate_schedule_wave_c_walk.mjs` drives the screens as a clerk; this
answers, for each schedule it saved, the three questions a screen cannot:

  * what the database holds (`tariffs` / `tariff_versions` and the method's
    own rows: `rate_tiers`, `rate_size_rows`, `rate_seasons`,
    `time_of_use_windows`, `capacity_rates`, `demand_rate_config`);
  * which version BILLING picks for a service date — `selectors.in_force_versions`
    (every live version whose window holds the date) and `in_force_version`
    (the one that prices, `BR-RAT-1055`);
  * what billing's own projection hands the engine for a date and a size —
    `selectors.pricing_inputs`, the ONE projection the bill run, the one-time
    bill and the impact analysis all read (its docstring says so). Its
    `version_id` is the version that travels onto the invoice line, and its
    `minimum_bill` is the per-size minimum billing applies (`DEF-RAT-8737`).

It writes NOTHING. It is a long-lived process speaking one JSON object per line
on stdin/stdout, so the walk pays Django's start-up once rather than per row.

Run by the walk; by hand:
    DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
      python 10-scripts/rswalk_probe.py <<< '{"op":"facts","tariff_id":"…"}'
"""

from __future__ import annotations

import json
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

from apps.rating import models as rm  # noqa: E402
from apps.rating import selectors as rs  # noqa: E402
from apps.tenancy import models as tm  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

TENANT = tm.Tenant.objects.get(subdomain=os.environ.get("RSW_TENANT", "brazosbend"))


def _s(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _rows(model, version, fields):
    if model is None:
        return []
    return [
        {f: _s(getattr(row, f, None)) for f in fields}
        # Tiers in their ladder order (`seq`), as the engine reads them; row
        # ids are not an order (a new version's rows may be written top first).
        for row in model.objects.filter(tariff_version=version).order_by(
            *(("seq", "pk") if model is rm.RateTier else ("pk",))
        )
    ]


def facts(tariff_id: str) -> dict:
    tariff = rm.Tariff.objects.get(pk=tariff_id)
    versions = []
    for v in rm.TariffVersion.objects.filter(tariff=tariff).order_by("created_at", "pk"):
        versions.append(
            {
                "id": str(v.pk),
                "model": v.model,
                "uom": v.uom,
                "effective_from": _s(v.effective_from),
                "effective_to": _s(v.effective_to),
                "superseded_by": _s(getattr(v, "superseded_by_id", None)),
                "corrects": _s(getattr(v, "corrects_id", None)),
                "minimum_bill": _s(v.minimum_bill),
                "change_reason": v.change_reason,
                "correction_reason": getattr(v, "correction_reason", None),
                "tiers": _rows(rm.RateTier, v, ("seq", "from_qty", "to_qty", "unit_price", "season", "size_class")),
                "size_rows": _rows(rm.RateSizeRow, v, ("size_class", "minimum_bill")),
                "seasons": _rows(getattr(rm, "RateSeason", None), v, ("label", "start_month", "start_day", "end_month", "end_day")),
                "windows": _rows(getattr(rm, "TimeOfUseWindow", None), v, ("label", "day_type", "start_time", "end_time", "unit_price", "channel")),
                "capacity": _rows(getattr(rm, "CapacityRate", None), v, ("unit_label", "rate_per_unit")),
                "demand": _rows(getattr(rm, "DemandRateConfig", None), v, ("energy_rate_per_kwh", "demand_rate_per_kw")),
            }
        )
    return {
        "tariff": {
            "id": str(tariff.pk),
            "name": tariff.name,
            "service": tariff.service.code,
            "account_type_id": _s(tariff.account_type_id),
        },
        "versions": versions,
    }


def in_force(tariff_id: str, dates: list[str], size: str | None) -> dict:
    tariff = rm.Tariff.objects.get(pk=tariff_id)
    answer = {}
    for raw in dates:
        day = date.fromisoformat(raw)
        every = rs.in_force_versions(tariff, day)
        one = rs.in_force_version(tariff, day)
        inputs = rs.pricing_inputs(tariff, day, size)
        answer[raw] = {
            "in_force_versions": [str(v.pk) for v in every],
            "in_force_version": None if one is None else str(one.pk),
            "pricing": None
            if inputs is None
            else {
                "version_id": inputs.get("version_id"),
                "model": inputs.get("model"),
                "minimum_bill": _s(inputs.get("minimum_bill")),
                "tiers": [
                    {k: _s(v) for k, v in tier.items()} for tier in (inputs.get("tiers") or [])
                ],
                "keys": sorted(inputs.keys()),
                "raw": {k: _s(v) for k, v in inputs.items() if not isinstance(v, (list, dict))},
            },
        }
    return answer


def audit(tariff_id: str) -> dict:
    """`audit_log` rows written about the schedule and its versions (hard rule 7:
    every money action writes one)."""
    from django.db import connection

    ids = [tariff_id] + [
        str(pk) for pk in rm.TariffVersion.objects.filter(tariff_id=tariff_id).values_list("pk", flat=True)
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT action FROM audit_log WHERE entity_id = ANY(%s::uuid[]) ORDER BY created_at",
            [ids],
        )
        actions = [row[0] for row in cursor.fetchall()]
    return {"count": len(actions), "actions": actions}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            ask = json.loads(line)
            with tenant_context(TENANT.id):
                if ask["op"] == "facts":
                    out = facts(ask["tariff_id"])
                elif ask["op"] == "audit":
                    out = audit(ask["tariff_id"])
                elif ask["op"] == "in_force":
                    out = in_force(ask["tariff_id"], ask["dates"], ask.get("size"))
                else:
                    out = {"error": f"unknown op {ask['op']}"}
        except Exception as exc:  # the walk records it as a finding
            out = {"error": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(out, default=str) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
