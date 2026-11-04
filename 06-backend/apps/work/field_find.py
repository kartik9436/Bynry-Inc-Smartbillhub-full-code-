# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 (the native field app) · Phase 13 · T-40 — lane S-FIND
# Screens:  FF-11 Nearby (04-docs/05-modules/18-field-app/wireframes/phone/
#           FF-11-nearby.png) · FF-41 Asset search (…/FF-41-asset-search.png)
# Rules:    BR-FLD-00002 (R2 — Nearby is a different list, sorted by distance;
#           Today's order untouched) · BR-FLD-00027 (R27 — contractors may claim
#           unassigned nearby work) · BR-FLD-00034 (R34 — radius default 2 mi) ·
#           BR-FLD-00041 (R41 — local first, server on request) · BR-FLD-00042
#           (R42 — a search that cannot see everything says so) · BR-FLD-00043
#           (R43 — serial, then badge, then device ID) · NFR-3 (server paging) ·
#           NFR-5 (no hard caps) · CLAUDE.md hard rules 1 and 8 · BR-MET-1162
# Endpoints: 07-endpoints.md §3 N9 (`GET work/mobile/assets/search`) and N11
#           (`GET work/mobile/nearby`)
# Tests:    06-backend/tests/test_cr187_find_search_nearby.py (SQLite) ·
#           tests/test_cr187_find_pg.py (PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""The field app's two server-side finds: the meter search and Nearby work.

BOTH ARE THE SECOND, DELIBERATE ACT (R41)
-----------------------------------------
The handset answers from what it holds first — FF-41 draws *"3 on this phone ·
Only today's assets are here. A signal searches the whole utility."* These two
routes are the *whole utility*, reached on request. So each answer says what it
covered, in figures, because a result the app cannot qualify is a lie about the
utility's records (R42):

* the asset search answers `count` (every match, not the page), `complete` (the
  WHOLE utility was searched — always true here), `fields_searched` and
  `fields_not_held` — **`assets` has no badge and no device-ID column**, so a
  badge number typed into the box can match nothing, and the app is told so by
  name rather than shown an empty list as though it were the answer;
* Nearby answers `count`, `unassigned` (the header's *3 unassigned*, counted over
  the whole radius, never the page) and `without_location` — open jobs that
  matched every filter but stand on no point and so cannot be measured.
  `complete` is false whenever that number is above zero.

PAGED IN SQL AND CAPPED NOWHERE (NFR-3, NFR-5)
----------------------------------------------
Both are `?page=&per=`, `per` clamped by `core.pagination.clamp_page_size` (50 ·
100 · 200 · 500 · 1000). Nothing counts, sorts or slices in Python: the ranking
and the distance are SQL expressions, so a T5 utility's 40,000 meters cost one
ordered, offset query per page and a count. **No route here enforces a maximum
row count, radius or page number** — T4 must arrive without anything to remove.

THE DISTANCE IS COMPUTED IN SQL WITHOUT TRIGONOMETRY, AND THAT IS DELIBERATE
---------------------------------------------------------------------------
PostgreSQL here has no PostGIS, and SQLite has no trig functions unless Django
registers them. The caller's latitude is a CONSTANT, so its cosine is computed
once in Python and the per-row expression is pure arithmetic — the
equirectangular approximation:

    dy = (lat − lat0) · k        dx = (lng − lng0) · k · cos(lat0)
    d² = (R·dy)² + (R·dx)²       k = π/180, R = 3,958.8 mi

Within the radii the app offers (1 · 2 · 5 · 10 mi, R34) the error against the
great-circle distance is far below the 0.1 mi the card prints (FF-11: *0.2
miles*). Sorting by d² sorts by d; the radius filter is `d² ≤ r²`, behind a
bounding box the database can use first. The miles on each card are computed
from the same formula, so the figure shown is the figure that sorted the row.

THE POINT IS THE PREMISES', AND A UNIT'S OWN WINS (hard rule 8, BR-MET-1162)
---------------------------------------------------------------------------
`metering_seam.nearby_jobs_queryset` walks each job to where it stands —
`selectors._premises_row`'s five anchors, in its order — and takes the unit's
point where the unit has one, the premises' otherwise. Each row says which
(`point_source`). No address or coordinate is copied onto anything.

REFUSALS CARRY THE CODE'S OWN SENTENCE AND A `reason` TOKEN
-----------------------------------------------------------
Every refusal here (and in `field_alerts.py`) is raised WITHOUT a bespoke
`message_key`, so it renders the catalogue's sentence for its code
(`errors.val-001` *This is required.* · `errors.val-003` *That value is out of
range.* · `errors.biz-state` …), and names WHICH refusal it is in
`params.reason` (`nearby_position_required`, `search_text_required`, …). A
bespoke key must exist in all eleven web catalogues (`core.refusal_catalogue`,
G15 parity, B14 rule 35) and this lane may not write them; the native app reads
`params.reason` against its OWN catalogue. Adding specific web keys later is a
copy change, not a contract change.

WHO SEES WHAT
-------------
`FieldAppRole`. *Mine* is the caller's technician profile (`mobile.technician_of`)
— no route takes a technician id (07-endpoints.md §0 rule 10). A job taken by
someone else is SHOWN, greyed, with the taker's name (FF-11's *Taken by R.
Patel*, `US-FLD-023` TC-3), and is never `claimable`. Nothing on either route
carries money (R16, R26).
"""

from __future__ import annotations

import math
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import ExpressionWrapper, F, FloatField, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.work import mobile
from apps.work.seams import assets_seam, customers_seam, metering_seam
from core import errors
from core.pagination import clamp_page_size

#: Mean Earth radius in MILES — the unit is in the name (hard rule 3's habit).
EARTH_RADIUS_MI = 3958.8
#: R34 — *"The nearby radius is a setting inside the app, default 2 miles"*.
DEFAULT_RADIUS_MI = Decimal("2")
#: What `scope` may ask for. `all` is the drawing (FF-11 shows the job R. Patel
#: took, greyed); `unassigned` is the *unassigned only* filter (03-field-map.md
#: §… FF-11 row); `mine` is the caller's own work by distance.
SCOPES: tuple[str, ...] = ("all", "unassigned", "mine")
BR_REF_NEARBY = "BR-FLD-00002"
BR_REF_SEARCH = "BR-FLD-00042"


# ══════════════════════════════════════════════════════════════════════════
# Shared
# ══════════════════════════════════════════════════════════════════════════


def _page(qs: Any, page: Any, per: Any) -> tuple[list[Any], dict[str, Any]]:
    """One page of `qs` and the paging figures — `mobile.readings_page`'s shape,
    so every field-app list pages the same way. `page` clamps, never errors."""
    size = clamp_page_size(per)
    total = qs.count()
    last = max(1, math.ceil(total / size))
    try:
        number = int(str(page or 1))
    except (TypeError, ValueError):
        number = 1
    number = max(1, min(number, last))
    rows = list(qs[(number - 1) * size : number * size])
    return rows, {
        "count": total,
        "page": number,
        "pages": last,
        "per": size,
        "next": number + 1 if number < last else None,
        "previous": number - 1 if number > 1 else None,
    }


def _decimal(raw: Any, *, field: str, br_ref: str) -> Decimal | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        value = None
    if value is None or not value.is_finite():
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref=br_ref,
            params={"reason": "not_a_number", "field": field, "value": str(raw)},
        )
    return value


# ══════════════════════════════════════════════════════════════════════════
# FF-41 — the meter search (N9)
# ══════════════════════════════════════════════════════════════════════════


def search_assets(actor: Any, *, q: Any, page: Any = 1, per: Any = 50) -> dict[str, Any]:
    """`GET /work/mobile/assets/search?q=&page=&per=` — every asset of the
    utility matching `q`, best match first, paged.

    The order is R43's scan order over the columns that EXIST: an exact serial,
    an exact asset number, then prefixes, then any part of either, then the
    premises address, then an account number on the meter's unit. Ties break on
    the asset number, then the id, so a page never reshuffles between two taps.

    An empty `q` is refused by name: *every asset of the utility* is not a
    search, and FF-41's box is the only door to this route.
    """
    text = str(q or "").strip()
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref=BR_REF_SEARCH,
            params={"reason": "search_text_required", "field": "q"},
        )
    account_units = customers_seam.unit_ids_with_account_no(text)
    qs = assets_seam.field_search_queryset(
        text,
        address_point_ids=metering_seam.service_point_ids_at_address(text),
        address_unit_ids=metering_seam.unit_ids_at_address(text),
        account_point_ids=metering_seam.service_point_ids_on_units(account_units),
        account_unit_ids=account_units,
    )
    rows, figures = _page(qs, page, per)
    cards = [assets_seam.field_search_row(row) for row in rows]
    places = metering_seam.places_of(
        [c["service_point_id"] for c in cards], [c["seat_unit_id"] for c in cards]
    )
    for card in cards:
        place = places.get(f"sp:{card['service_point_id']}") or places.get(
            f"unit:{card['seat_unit_id']}"
        )
        # `None` is a meter in the warehouse — it stands nowhere, and the card
        # says so rather than inventing an address (hard rule 8).
        card["place"] = place
        card.pop("service_point_id", None)
        card.pop("seat_unit_id", None)
    return {
        **figures,
        "results": cards,
        "q": text,
        # R42 — what this answer covered. The server searches EVERY asset of
        # the utility, so the result is complete over the records; the two
        # identifiers the assets table does not hold are named, never implied.
        "complete": True,
        "fields_searched": ["serial", "asset_no", "address", "account_no"],
        "fields_not_held": list(assets_seam.FIELD_SEARCH_NOT_HELD),
    }


# ══════════════════════════════════════════════════════════════════════════
# FF-11 — Nearby work (N11)
# ══════════════════════════════════════════════════════════════════════════


def _point(lat: Any, lng: Any) -> tuple[float, float]:
    """The device's position — both halves, in range, or a refusal by name."""
    la = _decimal(lat, field="lat", br_ref=BR_REF_NEARBY)
    lo = _decimal(lng, field="lng", br_ref=BR_REF_NEARBY)
    if la is None or lo is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref=BR_REF_NEARBY,
            params={"reason": "nearby_position_required", "field": "lat" if la is None else "lng"},
        )
    if not (Decimal(-90) <= la <= Decimal(90)) or not (Decimal(-180) <= lo <= Decimal(180)):
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref=BR_REF_NEARBY,
            params={"reason": "nearby_position_out_of_range", "lat": str(la), "lng": str(lo)},
        )
    return float(la), float(lo)


def _radius(raw: Any) -> float:
    """Miles, greater than zero. The app offers 1 · 2 · 5 · 10 (03-field-map.md
    FF-11 row) and the server accepts any positive figure: a ceiling here would
    be a cap T4 has to remove (NFR-5)."""
    value = _decimal(raw, field="radius_mi", br_ref="BR-FLD-00034")
    value = DEFAULT_RADIUS_MI if value is None else value
    if value <= 0:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-FLD-00034",
            params={"reason": "nearby_radius_not_positive", "radius_mi": str(value)},
        )
    return float(value)


def _due_by(raw: Any) -> datetime | None:
    """`due_by` — a date (the END of that day, in the server's zone) or a full
    timestamp. Jobs with no deadline never match a due filter."""
    text = str(raw or "").strip()
    if not text:
        return None
    moment = parse_datetime(text)
    if moment is None:
        day = parse_date(text)
        if day is None:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                br_ref=BR_REF_NEARBY,
                params={"reason": "nearby_due_not_a_date", "due_by": text},
            )
        moment = datetime.combine(day, time.max)
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment


def miles_between(lat0: float, lng0: float, lat: float, lng: float) -> float:
    """The SAME equirectangular figure the SQL sorts by (module docstring)."""
    k = math.pi / 180.0
    dy = (lat - lat0) * k
    dx = (lng - lng0) * k * math.cos(lat0 * k)
    return EARTH_RADIUS_MI * math.sqrt(dy * dy + dx * dx)


def nearby(
    actor: Any,
    *,
    lat: Any,
    lng: Any,
    radius_mi: Any = None,
    scope: Any = None,
    unassigned: Any = None,
    type: Any = None,  # noqa: A002 — the query parameter's own name (N11)
    priority: Any = None,
    due_by: Any = None,
    page: Any = 1,
    per: Any = 50,
) -> dict[str, Any]:
    """`GET /work/mobile/nearby?lat=&lng=&radius_mi=&scope=&type=&priority=&due_by=&page=&per=`.

    Open work within `radius_mi` (default 2, R34) of the device, NEAREST FIRST
    (R2) — then by deadline, then by order number, so equal distances never
    reshuffle. Priority is a pill and a filter, never a sort leg (`BR-WRK-035`
    governs Today; Nearby's one question is distance).

    `scope`: `all` (default — as drawn: unassigned, mine, and others' greyed) ·
    `unassigned` (also `unassigned=true`, N11's spelling) · `mine`.
    `type` matches the job type's code or name; `priority` the priority's code.
    """
    lat0, lng0 = _point(lat, lng)
    radius = _radius(radius_mi)
    chosen = str(scope or "").strip().lower() or (
        "unassigned" if str(unassigned or "").strip().lower() in ("1", "true", "yes") else "all"
    )
    if chosen not in SCOPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref=BR_REF_NEARBY,
            params={"reason": "nearby_scope_unknown", "scope": chosen},
        )
    technician = mobile.technician_of(actor)
    my_id = getattr(technician, "id", None)

    qs = metering_seam.nearby_jobs_queryset()
    type_text = str(type or "").strip()
    if type_text:
        qs = qs.filter(
            Q(type_ref__code__iexact=type_text) | Q(type_ref__name__iexact=type_text) | Q(type__iexact=type_text)
        )
    priority_text = str(priority or "").strip()
    if priority_text:
        qs = qs.filter(priority__code__iexact=priority_text)
    deadline = _due_by(due_by)
    if deadline is not None:
        qs = qs.filter(due_at__lte=deadline)
    unassigned_q = Q(assignee_technician__isnull=True, assignee_crew__isnull=True)
    if chosen == "unassigned":
        qs = qs.filter(unassigned_q)
    elif chosen == "mine":
        qs = qs.filter(assignee_technician_id=my_id) if my_id else qs.none()

    # R42 — what matched every filter but stands on no point.
    without_location = qs.filter(Q(pt_lat__isnull=True) | Q(pt_lng__isnull=True)).count()

    k = math.pi / 180.0
    cos0 = math.cos(lat0 * k)
    # The bounding box first (indexable columns on the walked anchors are not
    # promised, but the comparison is cheap and prunes before the arithmetic).
    dlat = radius / (EARTH_RADIUS_MI * k)
    dlng = radius / (EARTH_RADIUS_MI * k * max(cos0, 1e-9))
    qs = qs.filter(
        pt_lat__gte=lat0 - dlat, pt_lat__lte=lat0 + dlat,
        pt_lng__gte=lng0 - dlng, pt_lng__lte=lng0 + dlng,
    )
    dy = ExpressionWrapper((F("pt_lat") - lat0) * (EARTH_RADIUS_MI * k), output_field=FloatField())
    dx = ExpressionWrapper((F("pt_lng") - lng0) * (EARTH_RADIUS_MI * k * cos0), output_field=FloatField())
    qs = qs.annotate(dy=dy, dx=dx).annotate(
        d2=ExpressionWrapper(F("dy") * F("dy") + F("dx") * F("dx"), output_field=FloatField())
    ).filter(d2__lte=radius * radius)

    unassigned_count = qs.filter(unassigned_q).count()
    qs = qs.order_by("d2", mobile.work_dispatch_nulls_last("due_at"), "order_no", "id")
    rows, figures = _page(qs, page, per)
    return {
        **figures,
        "results": [_nearby_card(row, lat0, lng0, my_id) for row in rows],
        "unassigned": unassigned_count,
        "without_location": without_location,
        "complete": without_location == 0,
        "radius_mi": _miles_text(radius),
        "scope": chosen,
    }


def _miles_text(value: float) -> str:
    """Miles as a 2-place string — a distance, not money, but strings on the
    wire so no client re-rounds a float differently."""
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def _nearby_card(order: Any, lat0: float, lng0: float, my_id: Any) -> dict[str, Any]:
    """One FF-11 card: *0.2 miles · P3 · 1412 Elm Street · WO-4840 · Routine read
    · Due 22 Oct · 10 min · [Claim]* — or greyed, *Taken by R. Patel*."""
    from apps.work import dispatch as work_dispatch

    if order.assignee_technician_id is None and order.assignee_crew_id is None:
        holder = "unassigned"
    elif my_id is not None and order.assignee_technician_id == my_id:
        holder = "mine"
    else:
        holder = "taken"
    taken_by = None
    if holder == "taken":
        if order.assignee_technician_id is not None:
            taken_by = mobile._technician_name(order.assignee_technician) or None
        elif order.assignee_crew_id is not None:
            taken_by = getattr(order.assignee_crew, "name", None)
    return {
        # B14 rule 31 — the visible reference is `order_no`; the uuid is for
        # the phone to open the job and claim it.
        "id": str(order.id),
        "order_no": order.order_no,
        "type": (order.type_ref.name if order.type_ref_id else order.type),
        "premise": work_dispatch._premise_of(order),
        "distance_mi": _miles_text(miles_between(lat0, lng0, order.pt_lat, order.pt_lng)),
        "point_source": order.pt_source,
        "due_at": order.due_at.isoformat() if order.due_at else None,
        "est_minutes": (
            int(order.est_duration.total_seconds() // 60) if order.est_duration else None
        ),
        "priority": work_dispatch._priority_of(order),
        "dispatch_state": order.dispatch_state,
        "holder": holder,
        "taken_by": taken_by,
        # Whether the Claim button is live. The CLAIM itself is T-39's route
        # (N15), which re-checks everything server-side; this is a hint for the
        # card, never the guarantee. A held job is not offered.
        "claimable": holder == "unassigned" and order.dispatch_state != "on_hold",
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-187-BRC10 · 07-endpoints.md N9, N11 · 10-execution-plan.md T-40
# generated: 2026-10-21 by lane S-FIND
# checklist: A✔ B✔ C✔ D✔ E=n/a(no screen — the native app's lanes draw FF-11/FF-41) F✔ G✔ H=n/a(no migration)
# gates: G78 (reads through seams only) · pytest tests/test_cr187_find_* on SQLite and PostgreSQL 16
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
