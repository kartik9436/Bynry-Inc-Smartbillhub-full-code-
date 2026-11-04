# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-FLOW · P1.17 · P1.18
# Rules:    image 30 (the unit card, Building · Unit · Owner · History, and the
#           Services and meters table) · image 31 (meter facts on expand) ·
#           image 32 (*Below the last read.* inline) · BR-CUS-1101 (the Start
#           tick is the unit's own service offer) · BR-MET-036 (occupancy is
#           derived) · BR-CUS-068 (the owner's master account) · CLAUDE.md
#           hard rule 3 (a reading always carries its unit) · hard rule 8 (an
#           address is walked to the premises)
# Tests:    06-backend/tests/test_cr171_p1_17_18_unit_read.py
# ───────────────────────────────────────────────────────
"""**Step 1 of the four-step move-in, as two reads** — nothing here writes.

* `unit_facts(unit_id)` — the unit card (P1.17): the BUILDING (number, name,
  type, inside city limits, area, parcel and whether it is verified, routes and
  cycles), the UNIT (type, floor, square feet, common area), the OWNER (the
  master account covering it, and whether it bills while vacant) and the
  HISTORY (first occupant or the previous one, and how many times its plan
  changed). Every fact is read from the module that owns it, through a seam:
  metering's unit and premises, rating's plan history, customers' own accounts.
* `services_and_meters(unit_id)` — the table (P1.18): one row per service the
  unit OFFERS (`BR-CUS-1101`'s offer, so the Start tick and the writer cannot
  disagree), each with its meters, a meter's sub-meters and behind-the-meter
  devices nested under it, *reads as* (multiplier · digits), the last reading
  WITH its unit, and whether it needs an opening read.
* `check_opening_reads(unit_id, rows)` — *Below the last read.* per row, BEFORE
  Complete (image 32). Advice only: metering's own rule (`BR-MET-129`) still
  decides at the commit.

⚠ **AN ABSENCE IS SERVED AS ONE, NEVER AS A ZERO.** A plan history rating
cannot read is `plan_changes: None`, not 0; a meter with no reading is
`last_read: None`, not 0; a service with no meter is `metered: False` with no
opening read needed. *Follows water* (sewer priced on water's volume) is a
RATING fact this read does not have; the row says `metered: False` and the
screen draws its own sentence (rule 33: no rationale on screen).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.customers import models, seams, selectors

_EVER_FROM = date(1900, 1, 1)
_EVER_TO = date(9999, 12, 31)

CATEGORY_METER = "meters"
CATEGORY_SUB_METER = "sub_meters"
CATEGORY_DEVICE = "behind_the_meter"


# ═══════════════════════════════════════════════════════════════════════════
# P1.17 · THE UNIT CARD
# ═══════════════════════════════════════════════════════════════════════════
def unit_facts(unit_id: Any) -> dict[str, Any]:
    from apps.customers import unit_account_facts
    from apps.metering import selectors as metering_selectors

    unit = seams.unit_row(unit_id)  # 404, never 403, for another tenant's (HR-1)
    row = seams.unit_dict(unit)
    premises = metering_selectors.premises_row(unit.premises_id)
    building = metering_selectors.premises_detail_dict(premises, with_owner_account=False)
    routes = metering_selectors.premises_routes(premises)
    owner = unit_account_facts.owner_account_for_unit(unit.id)
    return {
        "unit": {
            "id": str(unit.id),
            "unit_no": row.get("unit_no"),
            "label": row.get("label"),
            "unit_type": row.get("unit_type"),
            "floor_label": row.get("floor_label"),
            "square_feet": row.get("square_feet"),
            "is_common_area": bool(row.get("is_common_area")),
            "occupancy": metering_selectors.occupancy_of(unit),
            # Hard rule 8 — the address is the PREMISES', walked to, never a copy.
            "address": {
                "line1": building.get("address_line"),
                "city": building.get("city"),
                "state": building.get("state"),
                "postal_code": building.get("postal_code"),
            },
        },
        "building": {
            "premise_no": building.get("premise_no"),
            "name": building.get("name"),
            "premises_type": building.get("premises_type"),
            "premises_type_name": building.get("premises_type_name"),
            "inside_city_limits": building.get("inside_city_limits"),
            "area_code": building.get("area_code"),
            "area_name": building.get("area_name"),
            "parcel": building.get("gis_parcel_id"),
            "parcel_verified": building.get("gis_verified"),
            "routes": [
                {
                    "code": route.get("code"),
                    "name": route.get("name"),
                    "service": route.get("service"),
                    "cycle_code": route.get("cycle_code"),
                    "cycle_name": route.get("cycle_name"),
                }
                for route in routes
            ],
        },
        "owner": None
        if owner is None
        else {
            "name": owner.get("name"),
            "account_no": owner.get("account_no"),
            "status_name": owner.get("status_name"),
            # The unit's own switch: base charges bill to the owner while it
            # stands empty (*Billed while vacant*, image 30).
            "billed_while_vacant": bool(row.get("vacant_standby_auto")),
        },
        "history": _history(unit.id),
    }


def _history(unit_id: Any) -> dict[str, Any]:
    from apps.customers import move_in_cancel

    accounts = models.Account.objects.filter(unit_id=unit_id)
    lived_in = [a for a in accounts.only("id", "opened_at", "closed_at") if not move_in_cancel.is_cancelled(a)]
    previous = selectors.last_closed_account_for_unit(unit_id)
    if previous is not None and move_in_cancel.is_cancelled(previous):
        previous = None  # a cancelled move-in never lived there
    # CR-181-BRC10 F1 — what the last account still owes, from the LEDGER
    # (DEF-127), so the clerk sees it on step 1 before anyone is searched.
    # `None` = the books cannot say, never a 0.00 nobody derived.
    owed, currency = (None, None)
    if previous is not None:
        from apps.customers import move_in_reopen

        owed, currency = move_in_reopen.outstanding(previous.id)
    return {
        "first_occupant": not lived_in,
        "previous": None
        if previous is None
        else {
            "account_no": previous.account_no,
            "name": selectors.primary_contact_name(previous),
            "closed_at": str(previous.closed_at) if previous.closed_at else None,
            "outstanding": str(owed) if owed is not None else None,
            "currency": currency,
        },
        "plan_changes": _plan_changes(unit_id),
    }


def _plan_changes(unit_id: Any) -> int | None:
    """How many times the unit's plan CHANGED — stretches minus one. `None`
    when rating publishes no history (never 0: *nobody looked* is not *never
    changed*)."""
    fn = seams.resolve("rating", "unit_plan_assignments_in", kind="selectors")
    if fn is None:
        return None
    rows = fn(unit_id, period_start=_EVER_FROM, period_end=_EVER_TO) or []
    return max(len(rows) - 1, 0)


# ═══════════════════════════════════════════════════════════════════════════
# P1.18 · SERVICES AND METERS
# ═══════════════════════════════════════════════════════════════════════════
def _last_reads(unit_id: Any) -> dict[str, dict[str, Any] | None]:
    """`{asset_no: {value, unit, read_at} | None}` — the newest head's reading
    (the meter INDEX, never the usage — DEF-CUS-5910)."""
    answer = seams.reads_for_unit(unit_id, on=None) or {}
    out: dict[str, dict[str, Any] | None] = {}
    for meter in answer.get("meters") or ():
        heads = [r for r in (meter.get("registers") or ()) if r.get("current_value") is not None]
        heads.sort(key=lambda r: str(r.get("read_at") or ""), reverse=True)
        head = heads[0] if heads else None
        out[str(meter.get("asset_no"))] = (
            None
            if head is None
            else {
                "value": head.get("current_value"),
                "unit": head.get("unit"),
                "read_at": head.get("read_at"),
                "channel": head.get("channel"),
            }
        )
    return out


def _size_names() -> dict[str, str]:
    """`code` → the tenant's NAME for a connection size (`W-58` → `Water 5/8"`),
    so the *Size* column prints a size and never a code (B14 rule 31; the
    function's own docstring in tenancy says why a missing code stays absent)."""
    fn = seams.resolve("tenancy", "service_size_class_names", kind="selectors")
    return dict(fn() or {}) if fn is not None else {}


def _meter_row(
    fact: dict[str, Any], last: dict[str, Any] | None, sizes: dict[str, str] | None = None
) -> dict[str, Any]:
    category = fact.get("category")
    reads = category in (CATEGORY_METER, CATEGORY_SUB_METER)
    return {
        "asset_no": fact.get("asset_no"),
        "kind": {
            CATEGORY_METER: "meter",
            CATEGORY_SUB_METER: "sub_meter",
            CATEGORY_DEVICE: "behind_the_meter",
        }.get(category, category),
        "type_name": fact.get("type_name"),
        "location_note": fact.get("location_note"),
        "size_class": fact.get("size_class"),
        # `CR-171-BRC10` lane MVI-WIZ-UNIT — what the Size column prints. None
        # when the size is not recorded OR its code has no name (never the code).
        "size_name": (sizes or {}).get(str(fact.get("size_class"))) if fact.get("size_class") else None,
        "reads_as": None
        if not reads
        else {"multiplier": fact.get("multiplier"), "digits": fact.get("register_digits")},
        "unit": fact.get("unit"),
        "last_read": last if reads else None,
        "needs_opening_read": reads,
        "last_test_date": fact.get("last_test_date"),
        "test_interval_months": fact.get("test_interval_months"),
        # Image 31 — the line under an expanded meter. Each key is absent from
        # the drawing when None (never "unknown", never a zero).
        "facts": {
            "serial_no": fact.get("serial_no"),
            "meter_type_name": fact.get("meter_type_name"),
            "read_method_name": fact.get("read_method_name"),
            "installed_on": fact.get("install_date"),
            "manufacturer": fact.get("manufacturer"),
            "model": fact.get("model"),
            "seal_no": fact.get("seal_no"),
            "certified_to": fact.get("certification_due"),
        },
        "children": [],
    }


def services_and_meters(unit_id: Any) -> dict[str, Any]:
    from apps.customers import services as customer_services

    seams.unit_row(unit_id)  # tenant boundary first
    points = seams.service_points_for(unit_id)
    service_of_point = {str(p.get("id")): p.get("service") for p in points}
    offer = customer_services._unit_service_offer(unit_id)
    fn = seams.resolve("assets", "meter_facts_for_unit", kind="selectors")
    facts = list(fn(unit_id)) if fn is not None else []
    last = _last_reads(unit_id)

    sizes = _size_names()
    rows_by_no = {f["asset_no"]: _meter_row(f, last.get(str(f["asset_no"])), sizes) for f in facts}
    top_by_service: dict[str, list[dict[str, Any]]] = {code: [] for code in offer}
    for fact in facts:
        row = rows_by_no[fact["asset_no"]]
        parent = fact.get("parent_asset_no")
        if parent and parent in rows_by_no:
            rows_by_no[parent]["children"].append(row)
            continue
        code = service_of_point.get(str(fact.get("service_point_id")))
        top_by_service.setdefault(code or "", []).append(row)
    services = [
        {
            "service": code,
            "start": True,  # BR-CUS-1101 — every offered service starts unless unticked
            # `DEF-CUS-9752` — metered means a READ device stands on the
            # service (the asset type's category: meter or sub-meter), never
            # *any* asset: a cart, a fire line or a PV array is equipment the
            # service counts or owns, and it read as *Metered* on step 1.
            "metered": any(row["needs_opening_read"] for row in top_by_service.get(code, [])),
            "meters": top_by_service.get(code, []),
        }
        for code in offer
    ]
    unplaced = top_by_service.get("", [])

    def _walk(rows: list[dict[str, Any]]):
        for r in rows:
            yield r
            yield from _walk(r["children"])

    every = [r for s in services for r in _walk(s["meters"])] + list(_walk(unplaced))
    return {
        "unit_id": str(unit_id),
        "services": services,
        # An asset whose point names no offered service is SHOWN, never dropped.
        "unplaced": unplaced,
        "counts": {
            "services": len(services),
            "meters": sum(1 for r in every if r["kind"] in ("meter", "sub_meter")),
            "devices": sum(1 for r in every if r["kind"] == "behind_the_meter"),
            "opening_reads_needed": sum(1 for r in every if r["needs_opening_read"]),
        },
        "assets_readable": fn is not None,
    }


def check_opening_reads(unit_id: Any, rows: Any) -> dict[str, Any]:
    """Image 32 — *Below the last read.* per row, the moment it is typed.

    `rows` = `[{meter_no, value}]`. Each answer row: `{meter_no, value,
    last_value, unit, below_last_read}` — `below_last_read` is `None` when
    there is nothing to compare (no last read, or a value that is not a
    number), never False by default. Advice: the commit is still metering's
    (`BR-MET-129`)."""
    seams.unit_row(unit_id)
    last = _last_reads(unit_id)
    out: list[dict[str, Any]] = []
    for raw in rows if isinstance(rows, list) else []:
        row = raw if isinstance(raw, dict) else {}
        meter_no = str(row.get("meter_no") or "")
        prior = last.get(meter_no)
        below: bool | None = None
        try:
            if prior is not None and prior.get("value") is not None:
                below = Decimal(str(row.get("value"))) < Decimal(str(prior["value"]))
        except (InvalidOperation, TypeError):
            below = None
        out.append(
            {
                "meter_no": meter_no,
                "value": row.get("value"),
                "last_value": None if prior is None else prior.get("value"),
                "unit": None if prior is None else prior.get("unit"),
                "below_last_read": below,
            }
        )
    return {"rows": out}
