# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W5 — the RDS-01 header button "Route sheet PDF", which has
#           rendered DISABLED with its reason since S25 shipped (2026-08-11).
#           Screens: S25 (the button) · SET-06D (the walk order it prints)
# Rules:    D11 (*"Per premises"* — a stop is a PREMISES; a three-unit building
#           is ONE stop, because a reader climbs those steps once) ·
#           BR-MET-033 (membership) · BR-MET-016/053 (the last read is the
#           lineage HEAD) · CLAUDE.md rule 1 (tenant scoping — HR-1 one 404) ·
#           rule 3 (a consumption never travels without its unit) ·
#           DEF-324 (one bounded query per fact, never one per stop)
# Tests:    06-backend/tests/test_cr038_w5_reads_surface.py
# ───────────────────────────────────────────────────────
"""The printable route sheet — what a reader carries on the walk.

**SERVED AS PRINT-READY HTML, DELIBERATELY NOT AS PDF BYTES.** No PDF library
is a dependency of this backend (pyproject dependencies: django · DRF ·
spectacular · psycopg · celery · environ · gunicorn · cryptography), and
adding one is not a lane's call. The one PDF writer in the product —
`apps/billing/documents.py`, which hand-writes the byte container with the
standard library — is billing's own module, scoped by its own docstring to the
bill document; importing its internals here would be a cross-module reach (B1)
for a page a browser prints perfectly well itself. So this route answers a
self-contained HTML page with a print stylesheet: File → Print (or Save as
PDF) is the PDF, and the r10 button copy stays honest.

WHAT PRINTS, AND FROM WHERE — every fact is a stored one:

  · the STOPS are `walk_order.premises_order_for_route` — the ruled per-
    premises walk (D11), current members only, saved order first and
    unsequenced members appended, exactly what SET-06D shows on screen;
  · the METERS at each stop are the assets whose service point is stamped
    with this route (BR-MET-033's membership stamp — the same fact the reads
    list filters on);
  · the LAST READ is the newest lineage head on any of the meter's registers
    (BR-MET-016/053), printed WITH ITS UNIT (rule 3) and its date. A meter
    never read prints a dash — an em-dash is "unknown", a zero would be a
    different and false claim.

FOUR BOUNDED QUERIES for the whole sheet — stops, premises, assets, heads —
never one per stop (DEF-324's discipline). A route is at most a few hundred
stops in this product's own sizing (<3,000 connections).

NO MONEY appears on a route sheet (BR-MET-078's spirit): it is the sequence a
crew walks in, with the register they will read.
"""

from __future__ import annotations

from html import escape
from typing import Any
from uuid import UUID

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from apps.metering import models, walk_order
from apps.metering import quantity_display
from core import errors
from core import tenancy as core_tenancy

__all__ = [
    "route_sheet_data",
    "render_route_sheet",
    "cycle_sheet_data",
    "render_cycle_sheet",
]


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _route_row(route_id: Any) -> models.Route:
    """This tenant's route, or ABSENT — HR-1: an unknown id, a malformed id and
    another tenant's id are ONE 404 (the same posture walk_order takes)."""
    try:
        return models.Route.objects.select_related("cycle", "assigned_to", "service").get(
            tenant_id=_tenant_id(), pk=route_id
        )
    except (models.Route.DoesNotExist, DjangoValidationError, ValueError, TypeError):
        raise errors.NotFoundError(audit_br_ref="BR-MET-073") from None


def route_sheet_data(route_id: Any) -> dict[str, Any]:
    """The sheet's facts: the route, its cycle, and the ordered stops — each
    with its premises, its meters and each meter's last committed read."""
    route = _route_row(route_id)
    stops = walk_order.premises_order_for_route(route_id)

    premises_ids = [stop["premises_id"] for stop in stops]
    premises_by_id = {
        str(row.id): row
        for row in models.Premises.objects.filter(tenant_id=route.tenant_id, id__in=premises_ids)
    }

    # The route's meters, grouped by the premises their unit stands on — ONE
    # query, along the same membership stamp the reads list filters by.
    assets = list(
        django_apps.get_model("assets", "Asset")
        .objects.filter(tenant_id=route.tenant_id, service_point__route_id=route.id)
        .select_related("service_point__unit")
        .order_by("asset_no", "id")
    )
    meters_by_premises: dict[str, list[Any]] = {}
    for asset in assets:
        unit = asset.service_point.unit
        meters_by_premises.setdefault(str(unit.premises_id), []).append(asset)

    # Newest head per asset, ONE query: ordered so the first row seen per
    # asset IS its latest read on any register (BR-MET-016 heads only).
    last_read: dict[Any, Any] = {}
    heads = (
        models.MeterRead.objects.filter(
            tenant_id=route.tenant_id,
            superseded_by_id__isnull=True,
            asset_id__in=[asset.id for asset in assets],
        )
        .order_by("asset_id", "-read_at", "-id")
        .only("asset_id", "read_at", "current_value", "consumption", "unit")
    )
    for row in heads:
        last_read.setdefault(row.asset_id, row)

    def meter_dict(asset: Any) -> dict[str, Any]:
        read = last_read.get(asset.id)
        return {
            "asset_no": asset.asset_no,
            "unit_label": asset.service_point.unit.label,
            # ── DEF-894: the FIELD AGENT reads this on paper ────────────────
            # Both figures print at the DISPLAY precision the PO ruled on
            # 2026-08-27 — at most two decimals, trailing zeros trimmed — and
            # not at BR-MET-019's storage precision. This sheet printed
            # `1016.000000 · 8.000000 kgal` on all 41 stops, which is six
            # characters of noise per figure on the one artefact somebody
            # carries around a route in the rain.
            "last_value": quantity_display.quantity_text(
                read.current_value if read is not None else None
            ),
            # rule 3 — the quantity and its unit travel together or not at all.
            "last_usage": (
                quantity_display.quantity_with_unit(read.consumption, read.unit)
                if read is not None
                else None
            ),
            "last_read_at": (
                read.read_at.date().isoformat() if read is not None and read.read_at else None
            ),
        }

    return {
        "route": {
            "code": route.code,
            "name": route.name,
            "route_type": route.route_type,
            "assigned_to": (
                route.assigned_to.full_name or route.assigned_to.email
                if route.assigned_to_id and route.assigned_to
                else None
            ),
            "service": route.service.code if route.service_id else None,
            "cycle": route.cycle.code if route.cycle_id else None,
        },
        "generated_at": timezone.now().isoformat(),
        "stops": [
            {
                "position": stop["walk_order"],
                "premise_no": stop["premise_no"],
                "address": (
                    premises_by_id[stop["premises_id"]].address_line
                    if stop["premises_id"] in premises_by_id
                    else None
                ),
                "units": stop["units"],
                "meters": [
                    meter_dict(asset) for asset in meters_by_premises.get(stop["premises_id"], [])
                ],
            }
            for stop in stops
        ],
    }


def _cell(value: Any) -> str:
    """Escaped text, or the em-dash for an absent fact — never a blank that
    reads as 'nothing here' and never a zero that claims a measurement."""
    return escape(str(value)) if value not in (None, "") else "—"


# Self-contained: no external asset may be required to print a sheet in the
# field. The @media print block is what the RDS-01 button's "PDF" promise
# resolves to — the browser's own Print / Save as PDF.
_STYLE = """
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         margin: 24px; color: #111; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  h2 { font-size: 15px; margin: 24px 0 4px; }
  .sheet-sub { color: #555; margin: 0 0 16px; font-size: 13px; }
  .leg-sub { color: #555; margin: 0 0 8px; font-size: 12px; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th, td { border: 1px solid #999; padding: 6px 8px; text-align: left;
           vertical-align: top; }
  th { background: #eee; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .meter-row { white-space: nowrap; }
  .write-in { min-width: 110px; }
  @media print {
    body { margin: 8mm; }
    thead { display: table-header-group; }
    tr { break-inside: avoid; }
  }
"""


def _route_title(route: dict[str, Any]) -> str:
    """`R-1 · Downtown`, escaped, with the name dropped when there is none."""
    return " · ".join(escape(bit) for bit in (route["code"], route["name"]) if bit)


def _route_facts(route: dict[str, Any], stop_count: int) -> str:
    """The one-line facts under a route's heading.

    ⚠ `Generated …` is deliberately NOT here. On a CYCLE sheet (BR-MET-162) it
    belongs to the sheet and is printed ONCE, not repeated under each of the
    cycle's route sections — five identical timestamps read as five sheets.
    """
    return " · ".join(
        part
        for part in (
            f"Cycle {_cell(route['cycle'])}" if route["cycle"] else None,
            f"Service {_cell(route['service'])}" if route["service"] else None,
            (
                f"Assigned to {_cell(route['assigned_to'])}"
                if route["assigned_to"]
                else "System (auto-pull)"
            ),
            f"{stop_count} stop(s)",
        )
        if part
    )


def _stops_table(stops: list[dict[str, Any]], *, empty_line: str) -> str:
    """ONE route's walk, as the table a reader carries.

    Extracted from `render_route_sheet` for BR-MET-162 so the cycle sheet
    prints the SAME table per route rather than a second one that could drift.
    `empty_line` is the sentence that prints when a route has no stops — never
    an empty table, which reads as a bug rather than as an empty route.
    """
    rows: list[str] = []
    for stop in stops:
        meters = stop["meters"]
        meter_lines = (
            "<br>".join(
                '<span class="meter-row">'
                + _cell(meter["asset_no"])
                + (f" ({escape(meter['unit_label'])})" if meter["unit_label"] else "")
                + "</span>"
                for meter in meters
            )
            or "—"
        )
        last_lines = (
            "<br>".join(
                '<span class="meter-row">'
                + (
                    f"{_cell(meter['last_value'])} · {_cell(meter['last_usage'])}"
                    f" · {_cell(meter['last_read_at'])}"
                    if meter["last_usage"] or meter["last_value"]
                    else "—"
                )
                + "</span>"
                for meter in meters
            )
            or "—"
        )
        rows.append(
            "<tr>"
            f"<td class=\"num\">{_cell(stop['position'])}</td>"
            f"<td>{_cell(stop['address'])}<br><small>{_cell(stop['premise_no'])}"
            f" · {stop['units']} unit(s)</small></td>"
            f"<td>{meter_lines}</td>"
            f"<td>{last_lines}</td>"
            '<td class="write-in"></td>'
            "</tr>"
        )

    body_rows = "\n".join(rows) or f'<tr><td colspan="5">{escape(empty_line)}</td></tr>'
    return f"""<table>
<thead>
<tr>
<th class="num">#</th>
<th>Premise</th>
<th>Meter</th>
<th>Last read</th>
<th>New read</th>
</tr>
</thead>
<tbody>
{body_rows}
</tbody>
</table>"""


def _page(*, title: str, heading: str, sub: str, body: str) -> str:
    """The self-contained printable page every sheet is served as."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{_STYLE}</style>
</head>
<body>
<h1>{heading}</h1>
<p class="sheet-sub">{sub}</p>
{body}
</body>
</html>
"""


def render_route_sheet(route_id: Any) -> str:
    """The printable page for ONE route. Every value is escaped; nothing here
    computes."""
    data = route_sheet_data(route_id)
    route = data["route"]
    title = _route_title(route)
    generated = f"Generated {escape(data['generated_at'][:16].replace('T', ' '))} UTC"
    header_facts = " · ".join(
        part for part in (_route_facts(route, len(data["stops"])), generated) if part
    )
    return _page(
        title=f"Route sheet · {title}",
        heading=f"Route sheet · {title}",
        sub=header_facts,
        body=_stops_table(data["stops"], empty_line="This route has no premises on it yet."),
    )


# ── BR-MET-162 · THE CYCLE SHEET (DEF-898) ─────────────────────────────────
#
# PO 2026-08-27, looking at the route-sheet dialog: *"allow route of Cycle -
# both"*. The sheet already PRINTED its cycle in the header — `Cycle SCW-M ·
# System (auto-pull) · 41 stop(s)` — so the cycle was a first-class fact of the
# artefact with no way to ask for one. A monthly walk is organised by cycle as
# often as by route.
#
# ⚠ **WHY NOTHING CAUGHT IT.** The feature works perfectly for the case it was
# built for: every test asks for a route sheet by route and gets one. A missing
# ENTRY POINT is invisible to any test that only exercises the entry point that
# exists.
#
# **A CYCLE SHEET IS NOT A RE-SEQUENCED MERGE.** A walk order belongs to a
# ROUTE (D11), there is no ruled ordering ACROSS routes, and inventing one
# would print a sequence nobody walks. So the sheet is SECTIONED by route, in
# `code` order so two prints of the same cycle are identical, and each section
# is that route's own walk in its own order — the same table
# `render_route_sheet` prints, from the same function.
#
# **A PREMISES ON TWO ROUTES APPEARS ONCE PER ROUTE**, with that route's
# meters: a reader really does visit it on both walks, and de-duplicating would
# drop a register from one of them.
#
# **QUERY COST, STATED.** Four bounded queries PER ROUTE in the cycle — not per
# stop, which is what DEF-324 forbids. A cycle in this product's own sizing
# (<3,000 connections) holds a handful of routes, and each one of them is a
# separate walk being printed.


def _cycle_row(cycle_id: Any) -> models.Cycle:
    """This tenant's cycle, or ABSENT — HR-1, exactly as `_route_row`: an
    unknown id, a malformed id and another tenant's id are ONE 404."""
    try:
        return models.Cycle.objects.get(tenant_id=_tenant_id(), pk=cycle_id)
    except (models.Cycle.DoesNotExist, DjangoValidationError, ValueError, TypeError):
        raise errors.NotFoundError(audit_br_ref="BR-MET-073") from None


def cycle_sheet_data(cycle_id: Any) -> dict[str, Any]:
    """The cycle, and one route-sheet payload per ACTIVE route on it.

    BR-MET-076: a DRAFT route stamps no service point, so Reads cannot see it,
    and an INACTIVE route is one nobody walks — neither is printed. BR-MET-010
    is what makes `routes.cycle_id` the whole membership question: a route
    belongs to one cycle at a time.
    """
    cycle = _cycle_row(cycle_id)
    routes = models.Route.objects.filter(
        tenant_id=cycle.tenant_id, cycle_id=cycle.id, status="active"
    ).order_by("code", "id")
    return {
        "cycle": {"code": cycle.code, "name": getattr(cycle, "name", None)},
        "generated_at": timezone.now().isoformat(),
        "routes": [route_sheet_data(route.id) for route in routes],
    }


def render_cycle_sheet(cycle_id: Any) -> str:
    """The printable page for a whole CYCLE — one section per route."""
    data = cycle_sheet_data(cycle_id)
    cycle = data["cycle"]
    title = " · ".join(escape(bit) for bit in (cycle["code"], cycle["name"]) if bit)
    stop_total = sum(len(route_data["stops"]) for route_data in data["routes"])
    header_facts = " · ".join(
        (
            f"{len(data['routes'])} route(s)",
            f"{stop_total} stop(s)",
            f"Generated {escape(data['generated_at'][:16].replace('T', ' '))} UTC",
        )
    )

    sections: list[str] = []
    for route_data in data["routes"]:
        route = route_data["route"]
        sections.append(
            f"<h2>{_route_title(route)}</h2>"
            f'<p class="leg-sub">{_route_facts(route, len(route_data["stops"]))}</p>'
            + _stops_table(route_data["stops"], empty_line="This route has no premises on it yet.")
        )
    # An empty cycle is a STATED absence with its cause, never a blank page:
    # a cycle with no active routes is a configuration fact somebody must fix.
    body = "\n".join(sections) or (
        "<p>This cycle has no active routes on it yet, so there is nothing to walk.</p>"
    )
    return _page(
        title=f"Cycle sheet · {title}",
        heading=f"Cycle sheet · {title}",
        sub=header_facts,
        body=body,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W5 (Reads list + detail page lane) — RDS-01 header button
# screens: S25 · SET-06D
# generated: 2026-08-26 by the CR-038 W5 lane
# checklist: A✔ B=this IS the surface (the S25 button opens it) C✔(tests/test_cr038_w5_reads_surface.py — RED first: 404, no such path) D✔ E✔ F✔ G✔ H=deferred(not a 🔒 path — no money, no RLS policy authored here)
# gates: see the lane report
# exceptions: (1) print-ready HTML, NOT PDF bytes — no PDF library is a backend
#   dependency and adding one is not this lane's call (module docstring);
#   REPORTED · (2) the sheet's labels are server-side English like the bill
#   document's (apps/billing/documents.py precedent) — the IS-8 catalogue
#   serves SPA screens, and no ruling extends it to print artifacts; REPORTED ·
#   (3) a "New read" write-in column is printed — a walk sheet exists to be
#   written on; it prints EMPTY, never a suggested value
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
