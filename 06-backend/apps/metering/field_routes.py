# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — `07-endpoints.md` N5: *"`GET work/mobile/routes` +
#           `GET work/mobile/routes/{id}` — the assigned routes with stops
#           (premises, point, walk order …), meters (with sub-meters, last
#           read, expected range) and the stamped account, paged"*.
# Story:    US-FLD-053 · US-FLD-054 (downloaded whole, at the depot) ·
#           US-FLD-055 (the stop is the address) · US-FLD-057 (previous
#           reading AND expected range) · US-FLD-058 (customer name, unit
#           label, account number at the stop) · US-FLD-062 (one reader per
#           route, nothing that forbids splitting)
#           Screens: RW-01, RW-02, RW-03, RW-05, RW-06, RW-09
# Rules:    BR-FLD-00074 (R74 — the stop is the address; walk order per
#           premises, `BR-MET-033`) · BR-FLD-00076 (R76 — every premises
#           carries its own point) · BR-FLD-00078 (R78, PO — previous AND
#           expected) · BR-FLD-00079 (R79, PO — the customer's name) ·
#           BR-FLD-00087 (R87) · BR-MET-1162 (a unit's own point, else its
#           building's, and which one is said) · CLAUDE.md hard rule 3 (a unit
#           on every figure) · hard rule 8 (the address from the premises) ·
#           NFR-3 / NFR-5 (paged, no cap)
# Tests:    06-backend/tests/test_cr187_reads_routes.py
# ───────────────────────────────────────────────────────
"""The reader's routes, and one route's stops — what RW-01 … RW-06 draw.

EVERYTHING HERE IS ASKED OF THE PRODUCT'S OWN ANSWERS, NOTHING IS RE-DERIVED
────────────────────────────────────────────────────────────────────────────
* **Who is on the route right now** is `selectors.route_members` — the derived
  membership (`CR-029` D4, PO *"member resolve at run time"*), carrying the
  STOP's walk order from `route_premises_orders` (D11). Stops are those units
  grouped by premises, in that order.
* **Which meters stand on those units** is `seams.assets_on_units` (three
  queries for the whole page, `CR-131-BRC07`), narrowed to the devices
  somebody READS (`selectors._is_read_device`) and less this route's
  exclusions (`BR-MET-075`).
* **Who is on supply** is `seams.accounts_for_units` — the occupying account
  NOW, which is what the stop shows (R79). The reading itself is stamped with
  the account at COLLECTION by `_post_row` (`collection_account_id`), never
  from this.
* **The previous reading** is the newest committed head per register
  (`selectors._read_heads()` — heads only, the counted one, BR-MET-1189).
* **The expected range** is the engine's OWN high/low thresholds over the
  engine's OWN trailing average — see `_expected`. It is a HINT for a person
  about to type (R78); the judging still happens at post, unchanged.

PAGED BY STOP, NEVER CAPPED
────────────────────────────────────────────────────────────────────────────
A page is a slice of STOPS (premises) in walk order, sized by
`core.pagination.clamp_page_size` (50 · 100 · 200 · 500 · 1000). Every meter,
account and history read is for that slice only, in a fixed number of queries.
The membership resolution itself is whole-route — it is a fixed number of
queries whatever the route's size (`derivation`'s own contract).
"""

from __future__ import annotations

import math
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any
from uuid import UUID

from django.apps import apps as django_apps

from apps.metering import (
    models,
    read_formats,
    register_units,
    seams,
    selectors,
    services,
    validation,
)
from core import errors
from core import permissions as core_permissions
from core import tenancy as core_tenancy
from core.pagination import clamp_page_size

#: How many trailing actual reads the expected range averages — the
#: `services._trailing_actuals` default, which is OQ-002's flag basis.
TRAILING_WINDOW = 12


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def is_field_technician(actor: Any) -> bool:
    return getattr(actor, "role", None) == core_permissions.FIELD_TECHNICIAN


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def route_for_reader(actor: Any, route_id: Any) -> models.Route:
    """This tenant's route, or ONE 404 (HR-1).

    ⚠ **A FIELD TECHNICIAN REACHES THE ROUTES ASSIGNED TO THEM, AND NO OTHER.**
    Another reader's route is the SAME 404 as a route that does not exist — the
    `mobile.require_own_job` posture. An office role is not narrowed: it may
    open any route of its own tenant the way it opens the route sheet.

    R87: *"the assignment stays a row that could become many"*. The check is
    `assigned_to == me` today and is written as ONE predicate in ONE place
    (`reader_routes`), so a second reader is a change to that predicate and to
    nothing else.
    """
    if not _is_uuid(route_id):
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    qs = models.Route.objects.filter(tenant_id=_tenant_id(), pk=route_id, deleted_at__isnull=True)
    if is_field_technician(actor):
        qs = reader_routes(actor, qs)
    route = qs.select_related("cycle", "area", "service").first()
    if route is None:
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    return route


def reader_routes(actor: Any, qs: Any = None) -> Any:
    """R87's one predicate: the routes this reader is assigned to."""
    if qs is None:
        qs = models.Route.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
    return qs.filter(assigned_to_id=_actor_id(actor))


def window_for(route: models.Route, on_day: date) -> tuple[date, date] | None:
    """The read window `on_day` falls in, from the route's cycle schedule —
    `services._cycle_window_for`, the product's one derivation. None when the
    route has no cycle or the cycle has no schedule; never invented."""
    return services._cycle_window_for(route.cycle, on_day) if route.cycle_id else None


# ── the route's meters, grouped into stops ─────────────────────────────────


def route_stops(route: models.Route) -> list[dict[str, Any]]:
    """Every stop on the route, in walk order: `{premises_id, premise_no,
    position, unit_ids}`. The stop is a PREMISES (R74); its units are the
    derived members standing on it."""
    members = selectors.route_members(route.id)
    stops: dict[str, dict[str, Any]] = {}
    for member in members:
        stop = stops.setdefault(
            member["premises_id"],
            {
                "premises_id": member["premises_id"],
                "premise_no": member["premise_no"],
                "walk_order": member.get("walk_order"),
                "unit_ids": [],
            },
        )
        stop["unit_ids"].append(member["unit_id"])
    sequenced = sorted(
        (s for s in stops.values() if s["walk_order"] is not None),
        key=lambda s: s["walk_order"],
    )
    unsequenced = sorted(
        (s for s in stops.values() if s["walk_order"] is None),
        key=lambda s: (s["premise_no"] or "", s["premises_id"]),
    )
    ordered = [*sequenced, *unsequenced]
    for index, stop in enumerate(ordered, start=1):
        stop["position"] = index
    return ordered


def _excluded(route: models.Route) -> set[str]:
    return set(selectors.route_excluded_asset_ids(route.id))


def meters_on_units(unit_ids: list[str], *, excluded: set[str]) -> dict[str, list[dict[str, Any]]]:
    """unit id → the meters read there (BR-AST-004 categories), less the
    route's exclusions. Three queries for any number of units."""
    out: dict[str, list[dict[str, Any]]] = {}
    for unit_id, rows in seams.assets_on_units(unit_ids).items():
        kept = [
            row for row in rows if selectors._is_read_device(row) and row["id"] not in excluded
        ]
        if kept:
            out[str(unit_id)] = kept
    return out


def route_meter_ids(route: models.Route) -> set[str]:
    """Every meter this route reads right now — the off-route question (R84)."""
    unit_ids = [unit for stop in route_stops(route) for unit in stop["unit_ids"]]
    return {
        row["id"]
        for rows in meters_on_units(unit_ids, excluded=_excluded(route)).values()
        for row in rows
    }


# ── previous reading and expected range ────────────────────────────────────


def _heads_and_history(asset_ids: list[str]) -> tuple[dict, dict]:
    """`(latest head per (asset, register), trailing consumptions per (asset,
    register))` in ONE query over the page's meters.

    Heads only, the counted one (`selectors._read_heads()`), so the previous
    reading is the one billing would price from and the average is the one the
    HIGH/LOW rules judge by (`services._trailing_actuals` takes the same set).
    """
    latest: dict[tuple[str, str], Any] = {}
    history: dict[tuple[str, str], list[Decimal]] = {}
    if not asset_ids:
        return latest, history
    rows = (
        selectors._read_heads()
        .filter(asset_id__in=asset_ids)
        .order_by("asset_id", "channel", "-read_at", "-id")
        .only(
            "id",
            "asset_id",
            "channel",
            "read_at",
            "current_value",
            "consumption",
            "unit",
            "multiplier",
            "status",
        )
    )
    for row in rows:
        key = (str(row.asset_id), row.channel)
        if row.current_value is not None:
            latest.setdefault(key, row)
        if row.current_value is not None and row.consumption is not None:
            bucket = history.setdefault(key, [])
            if len(bucket) < TRAILING_WINDOW:
                bucket.append(row.consumption)
    return latest, history


def _expected(
    head: Any, consumptions: list[Decimal], config: Any, multiplier: Any
) -> tuple[dict[str, Any] | None, str | None]:
    """The dial range the HIGH and LOW rules would let through without a flag.

    ``low  = previous + average × low_pct  ÷ 100 ÷ multiplier``
    ``high = previous + average × high_pct ÷ 100 ÷ multiplier``

    where `average` is the mean of the trailing actual consumptions and the two
    percentages are the tenant's own (`validation.resolve_config` for the
    meter's service — the per-service row first, BR-MET-020). Rounded OUTWARD
    to whole dial units (low down, high up), because it is drawn as
    *40,000–56,000* and a range rounded inward would warn a reader about a
    figure the engine will accept.

    ⚠ **A HINT, NEVER A THRESHOLD.** The high rule ALSO needs the absolute floor
    (OQ-002), which a range of dial figures cannot express; the reading is
    judged at post by the engine, unchanged. R80: warned, never blocked.

    Returns `(range, None)` or `(None, reason)` — never a guessed range.
    """
    if head is None:
        return None, "no_previous_reading"
    if not consumptions:
        return None, validation.REASON_NO_HISTORY
    if config is None:
        return None, validation.REASON_NO_CONFIG
    low_pct = getattr(config, "low_pct", None)
    high_pct = getattr(config, "high_pct", None)
    if low_pct is None or high_pct is None:
        return None, validation.REASON_NO_CONFIG
    average = sum(consumptions, Decimal("0")) / Decimal(len(consumptions))
    if average <= 0:
        return None, validation.REASON_NO_HISTORY
    factor = Decimal(str(multiplier)) if multiplier not in (None, 0, "") else Decimal("1")
    if factor <= 0:
        factor = Decimal("1")
    previous = head.current_value
    low = previous + average * Decimal(str(low_pct)) / Decimal(100) / factor
    high = previous + average * Decimal(str(high_pct)) / Decimal(100) / factor
    return (
        {
            "low": str(low.quantize(Decimal("1"), rounding=ROUND_FLOOR)),
            "high": str(high.quantize(Decimal("1"), rounding=ROUND_CEILING)),
            "basis": {
                "trailing_reads": len(consumptions),
                "average_consumption": str(average.quantize(Decimal("0.01"))),
                "low_pct": str(low_pct),
                "high_pct": str(high_pct),
            },
        },
        None,
    )


def _point(lat: Any, lng: Any) -> dict[str, str] | None:
    if lat is None or lng is None:
        return None
    return {"lat": str(lat), "lng": str(lng)}


# ── the two reads ──────────────────────────────────────────────────────────


def _route_summary(route: models.Route, on_day: date, stops: list[dict[str, Any]], meters: int) -> dict[str, Any]:
    window = window_for(route, on_day)
    return {
        "id": str(route.id),
        "code": route.code,
        "name": route.name,
        "route_type": route.route_type,
        "services": selectors.route_service_codes(route.id)
        or ([route.service.code] if route.service_id else []),
        "area": route.area.name if route.area_id else None,
        "cycle": route.cycle.code if route.cycle_id else None,
        "notes": route.notes,
        "window": (
            {"start": window[0].isoformat(), "end": window[1].isoformat()} if window else None
        ),
        "stops": len(stops),
        "meters": meters,
        # MQ-033 (`CR-192-BRC10`, `BR-MET-1212`) — per service the route reads,
        # the read format resolved route → cycle → service (or none), named by
        # its VERSION id so the handset caches it once per version.
        "read_formats": read_formats.route_formats(route),
    }


def my_routes(actor: Any, *, on: Any = None, page: Any = None, per: Any = None) -> dict[str, Any]:
    """`GET work/mobile/routes` — the routes assigned to the signed-in reader,
    for the window `on` falls in (default: the tenant's today). RW-01.

    Paged like every list (NFR-3) though a reader holds one to three; each
    route carries its stop and meter counts so RW-01's *47 stops · 151 of 153
    meters* needs no second call, and what this reader has already sent in the
    window (`sent`), so *0 read* is the server's count and not a guess.
    """
    on_day = _parse_day(on)
    size = clamp_page_size(per)
    qs = reader_routes(actor).filter(status="active").select_related("cycle", "area", "service")
    total = qs.count()
    number = _page_number(page, total, size)
    rows = list(qs.order_by("code", "id")[(number - 1) * size : number * size])
    from apps.metering import field_read_models as frm

    out = []
    for route in rows:
        stops = route_stops(route)
        unit_ids = [unit for stop in stops for unit in stop["unit_ids"]]
        meters = sum(len(v) for v in meters_on_units(unit_ids, excluded=_excluded(route)).values())
        summary = _route_summary(route, on_day, stops, meters)
        sent = frm.FieldRead.objects.filter(
            tenant_id=_tenant_id(), route=route, reader_id=_actor_id(actor)
        )
        window = window_for(route, on_day)
        if window:
            sent = sent.filter(
                received_at__date__gte=window[0], received_at__date__lte=window[1]
            )
        summary["sent"] = sent.count()
        out.append(summary)
    return {
        "on": on_day.isoformat(),
        "count": total,
        "page": number,
        "per": size,
        "next_page": number + 1 if number * size < total else None,
        "results": out,
    }


def route_page(actor: Any, route_id: Any, *, on: Any = None, page: Any = None, per: Any = None) -> dict[str, Any]:
    """`GET work/mobile/routes/{id}?page=&per=` — one page of STOPS, in walk
    order, each with every meter read there. RW-03's *"47 stops in order ·
    151 meters, with last month's reads · customer names and accounts"*.

    Per meter: its number and serial (the screen shows *MTR-0471 · badge
    88241*), master/sub qualifier and parent, service, the unit label and the
    customer and account on supply (R79), and per REGISTER its unit (hard rule
    3), the previous reading with its date, and the expected range or the
    reason there is none (R78).

    Per stop: the premises' address and point (hard rule 8, R76); per meter the
    UNIT's own point where it has one and the building's otherwise, saying
    which (`BR-MET-1162`).

    ⚠ **NOT SERVED, AND SAID:** premises-level access notes, hazards and gate
    codes (RW-07) have no server home yet — `03-field-map.md` §2.4 marks them
    NEW (metering). `route.notes` is served at route level. Badge and device
    id are not served because which asset field IS the badge is undecided
    (`03-field-map.md` §2.2, an OQ-FLD still to be minted).
    """
    route = route_for_reader(actor, route_id)
    on_day = _parse_day(on)
    size = clamp_page_size(per)
    stops = route_stops(route)
    excluded = _excluded(route)
    all_units = [unit for stop in stops for unit in stop["unit_ids"]]
    total_meters_by_unit = meters_on_units(all_units, excluded=excluded)
    number = _page_number(page, len(stops), size)
    slice_ = stops[(number - 1) * size : number * size]

    page_units = [unit for stop in slice_ for unit in stop["unit_ids"]]
    meters_by_unit = {u: total_meters_by_unit.get(u, []) for u in page_units}
    asset_ids = [row["id"] for rows in meters_by_unit.values() for row in rows]
    Asset = django_apps.get_model("assets", "Asset")
    assets = {
        str(a.id): a
        for a in Asset.objects.filter(tenant_id=_tenant_id(), id__in=asset_ids).select_related(
            "service_point__service", "parent_asset", "read_method"
        )
    }
    premises = {
        str(p.id): p
        for p in models.Premises.objects.filter(
            tenant_id=_tenant_id(), id__in=[stop["premises_id"] for stop in slice_]
        )
    }
    units = {
        str(u.id): u for u in models.Unit.objects.filter(tenant_id=_tenant_id(), id__in=page_units)
    }
    accounts = seams.accounts_for_units(page_units)
    latest, history = _heads_and_history(asset_ids)
    config = services._config_set()

    def registers_for(asset: Any) -> list[dict[str, Any]]:
        mine = sorted(
            ((channel, head) for (aid, channel), head in latest.items() if aid == str(asset.id)),
            key=lambda pair: pair[0],
        )
        if not mine:
            mine = [(models.CHANNEL_TOTAL, None)]
        service_code = (
            asset.service_point.service.code
            if asset.service_point_id and asset.service_point.service_id
            else None
        )
        resolved = validation.resolve_config(config, service_code)
        out = []
        for channel, head in mine:
            unit = (head.unit if head is not None else None) or register_units.register_unit(
                asset.unit, channel
            )
            expected, absent = _expected(
                head,
                history.get((str(asset.id), channel), []),
                resolved,
                head.multiplier if head is not None and head.multiplier else asset.multiplier,
            )
            out.append(
                {
                    "register": channel,
                    "unit": unit,  # hard rule 3 — never separated from its figures
                    "previous": (
                        {
                            "value": str(head.current_value),
                            "read_on": head.read_at.date().isoformat(),
                        }
                        if head is not None
                        else None
                    ),
                    "expected": expected,
                    "expected_absent_reason": absent,
                }
            )
        return out

    served_stops = []
    for stop in slice_:
        place = premises.get(stop["premises_id"])
        meters = []
        for unit_id in stop["unit_ids"]:
            unit = units.get(unit_id)
            account = accounts.get(unit_id) or {}
            for row in meters_by_unit.get(unit_id, []):
                asset = assets.get(row["id"])
                if asset is None:  # pragma: no cover — the seam read the same rows
                    continue
                own = _point(getattr(unit, "lat", None), getattr(unit, "lng", None))
                meters.append(
                    {
                        "asset_id": str(asset.id),
                        "meter_no": asset.asset_no,
                        "serial_no": asset.serial_no,
                        "qualifier": row.get("qualifier"),
                        "parent_meter_no": (
                            asset.parent_asset.asset_no if asset.parent_asset_id else None
                        ),
                        "service": (
                            asset.service_point.service.code
                            if asset.service_point_id and asset.service_point.service_id
                            else None
                        ),
                        "size_class": asset.size_class,
                        "unit_of_measure": asset.unit,
                        "register_digits": asset.register_digits,
                        "multiplier": str(asset.multiplier) if asset.multiplier is not None else None,
                        "read_method": asset.read_method.code if asset.read_method_id else None,
                        "location_note": asset.location_note,
                        "unit_id": unit_id,
                        "unit_label": getattr(unit, "label", None),
                        "point": own
                        or _point(getattr(place, "lat", None), getattr(place, "lng", None)),
                        "point_source": (
                            "unit"
                            if own
                            else ("premises" if place is not None and place.lat is not None else None)
                        ),
                        "account_no": account.get("account_no"),
                        "customer_name": account.get("customer_name"),
                        "registers": registers_for(asset),
                    }
                )
        served_stops.append(
            {
                "premises_id": stop["premises_id"],
                "premise_no": stop["premise_no"],
                "position": stop["position"],
                "walk_order": stop["walk_order"],
                # Hard rule 8 — the ONE place an address lives, read by walking.
                "address": (
                    {
                        "line": place.address_line,
                        "city": place.city,
                        "state": place.state,
                        "postal_code": place.postal_code,
                    }
                    if place is not None
                    else None
                ),
                "point": _point(getattr(place, "lat", None), getattr(place, "lng", None)),
                "meters": meters,
            }
        )
    total_meters = sum(len(v) for v in total_meters_by_unit.values())
    summary = _route_summary(route, on_day, stops, total_meters)
    return {
        "route": summary,
        # MQ-033 — the resolved versions WITH their questions, on every page so
        # a handset that fetched page 3 first still has them; each also at
        # `GET work/mobile/read-formats/versions/{id}`.
        "read_format_versions": read_formats.versions_for_handset(
            [(entry["read_format"] or {}).get("version_id") for entry in summary["read_formats"]]
        ),
        "count": len(stops),
        "page": number,
        "per": size,
        "next_page": number + 1 if number * size < len(stops) else None,
        "stops": served_stops,
    }


def _parse_day(raw: Any) -> date:
    text = str(raw or "").strip()
    if not text:
        return seams.tenant_today()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="errors.val-002",
            field_errors=[
                {
                    "field": "on",
                    "code": errors.VAL_FORMAT,
                    "message_key": "errors.val-002",
                    "params": {},
                }
            ],
        ) from None


def _page_number(raw: Any, total: int, size: int) -> int:
    """BR-SHL-011 — a garbage or out-of-range page clamps, never errors."""
    try:
        number = int(str(raw))
    except (TypeError, ValueError):
        number = 1
    last = max(math.ceil(total / size), 1) if size else 1
    return min(max(number, 1), last)


__all__ = [
    "my_routes",
    "route_page",
    "route_for_reader",
    "route_meter_ids",
    "route_stops",
    "meters_on_units",
    "window_for",
    "is_field_technician",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-FLD-054@fa5746815 (CR-187-BRC10 route-reading server lane — 07-endpoints.md N5)
# generated: 2026-10-21 by the CR-187 reads server lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the native app lanes build RW-01…RW-06) F✔ G✔ H=deferred(no 🔒 path in this file)
# gates: see the lane report
# exceptions: the expected range is a DERIVATION of the engine's own thresholds, rounded outward — REPORTED · access notes/hazards/gate code and the badge are not served (no server home; badge field undecided) — REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
