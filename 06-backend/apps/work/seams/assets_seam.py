# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-005 (EP-WRK-01) — the assets seam: a meter or a device by
#           id, so a job on an asset can name what it is for.
# Rules:    BR-WRK-002 (read-only) · BR-WRK-006 (an asset is an anchor —
#           `work_orders.asset_id` exists and this module writes it through
#           metering's door, never the asset row) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_wrk_005_module.py (TC-6 · TC-7)
# Impacts:  apps/work/selectors.py
# ───────────────────────────────────────────────────────
"""work → assets: one asset by id. READ ONLY.

Wave M's Assets door (Work-028) hands an asset id across and Work reads its
number, type and install date here; the asset row itself is never touched —
`AssetMaintenance.cost` stays *"captured and posted nowhere"* on the assets
side (CR-028 D3), and G78 is what fails a lane that forgets.
"""

from __future__ import annotations

import uuid
from typing import Any

from core import tenancy as core_tenancy


#: Lifecycle stage CODES that mean *this device is out of the ground*. An asset
#: at one of these is never "past its certification life" in any sense a crew
#: could act on — see `assets_past_certification`.
RETIRED_STAGE_CODES: tuple[str, ...] = ("retired", "disposed", "scrapped")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _installed_q() -> Any:
    """An asset INSTALLED at a premises — `CR-168-BRC10` §30, PO answer (3) of
    2026-10-05, verbatim: *"(b) Only raise jobs for meters that are
    installed."*

    The same two ways `connections._asset_walk` stands an asset on a unit (and
    so on its premises): a SERVICE POINT (every point sits on a unit), or, for a
    device that measures nothing, its OPEN `asset_assignments` row
    (`DEF-WRK-9660`, `BR-AST-017`). An asset with neither is in the warehouse:
    a job raised on it would have no address to send anybody to. Both
    certification readers below filter on this, so the rule's preview, its
    *Tonight* and the sweep count the same subjects (`DEF-WRK-9661`'s shape:
    one reader, never a copy). Jobs already raised on a warehouse meter are
    left exactly as they are — this decides only what is FOUND.
    """
    from django.db.models import Exists, OuterRef, Q

    from apps.assets import models as assets_models

    seated = assets_models.AssetAssignment.objects.filter(
        tenant_id=_tenant_id(), asset_id=OuterRef("pk"), to_date__isnull=True
    )
    return Q(service_point__isnull=False) | Q(Exists(seated))


def asset(asset_id: Any) -> dict[str, Any] | None:
    """One asset of the tenant in context, or None."""
    from apps.assets import models as assets_models

    row = assets_models.Asset.objects.filter(tenant_id=_tenant_id(), pk=asset_id).first()
    if row is None:
        return None
    return {
        "id": str(row.id),
        "asset_no": row.asset_no,
        # `assets.status` is a lookup row (BR-AST-031), so its CODE is what travels.
        "status": getattr(getattr(row, "status", None), "code", None),
        "install_date": row.install_date.isoformat() if row.install_date else None,
    }


def meter(asset_id: Any) -> dict[str, Any] | None:
    """The meter a READS field visit is raised for — its number and where it
    stands. READ ONLY (the Reads→Work door, PO ruling 2026-09-14).

    ⚠ **IT ANSWERS THE SERVICE-POINT ID AND WALKS NO FURTHER, DELIBERATELY.**
    Where that point IS — its unit, its premises, its service — belongs to
    metering, and `metering_seam.service_point_anchor` is what reads it. Joining
    `service_point__unit__premises` from here would be one query and would put
    metering's column names in the assets seam, which is the difference between
    *one read-only seam file per module* (`BR-WRK-002`) and two files that both
    know the whole schema.

    `asset_no` is the number a clerk quotes and the only identity of this meter
    that ever reaches a screen or a `source_ref` (B14 rule 31); the uuid stays
    in `id`, which the caller uses as an ANCHOR and never prints.
    """
    from apps.assets import models as assets_models

    row = assets_models.Asset.objects.filter(tenant_id=_tenant_id(), pk=asset_id).first()
    if row is None:
        return None
    return {
        "id": str(row.id),
        "asset_no": row.asset_no,
        "service_point_id": str(row.service_point_id) if row.service_point_id else None,
    }


def job_meter(asset_id: Any) -> dict[str, Any] | None:
    """The meter a job's card names on the phone — `DEF-FLD-10582` (MQ-015):
    FF-15's *W-4471 · Neptune T-10 · 5/8"* and FF-25's *Meter W-4471*. READ
    ONLY, read at use and never copied onto the order (`BR-WRK-008` freezes
    what the job involves, not which meter stands there today).

    `{id, asset_no, serial_no, model, size_class, service_point_id}` or None.
    The SERVICE the meter runs is metering's to say, so the caller asks
    `metering_seam.service_point_anchor` with the point this returns — the same
    two-hop split as `meter` above.

    ⚠ **NO BADGE IS SERVED, DELIBERATELY.** Which asset field IS the badge is
    undecided (`apps/metering/field_reads.BADGE_FIELD_QUESTION`, and the route
    page withholds it for the same reason); a value guessed here would be the
    one the scan then matches on.
    """
    from apps.assets import models as assets_models

    if not asset_id:
        return None
    row = (
        assets_models.Asset.objects.filter(tenant_id=_tenant_id(), pk=asset_id)
        .values("id", "asset_no", "serial_no", "model", "size_class", "service_point_id")
        .first()
    )
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "asset_no": row["asset_no"],
        "serial_no": row["serial_no"],
        "model": row["model"],
        "size_class": row["size_class"],
        "service_point_id": str(row["service_point_id"]) if row["service_point_id"] else None,
    }


def asset_on_unit_by_no(unit_id: Any, asset_no: Any) -> dict[str, Any] | None:
    """The asset numbered `asset_no` that stands on `unit_id` TODAY (an open
    `asset_assignments` row), whatever its stage — `{id, asset_no, status}` —
    or None. `CR-171-BRC10` lane MVI-WIZ-UNIT: the *For* column of a flow's
    *Field visit* names the meter by its number (B14 rule 31) and the raise
    puts the job on it only when it is on the flow's own unit. A meter still
    In stock is answered on purpose: fitting it is what the visit is for
    (`DEF-AST-9712`). READ ONLY."""
    from apps.assets import models as assets_models

    if not unit_id or not asset_no:
        return None
    row = (
        assets_models.Asset.objects.filter(
            tenant_id=_tenant_id(),
            asset_no=str(asset_no),
            assetassignment__unit_id=unit_id,
            assetassignment__to_date__isnull=True,
        )
        .select_related("status")
        .first()
    )
    if row is None:
        return None
    return {
        "id": str(row.id),
        "asset_no": row.asset_no,
        "status": getattr(getattr(row, "status", None), "code", None),
    }


def in_service_meters_on_points(service_point_ids: Any) -> list[dict[str, Any]]:
    """The IN-SERVICE meters standing on these service points — id, number and
    point. READ ONLY (`DEF-WRK-9620`).

    The predicate is `assets.selectors.in_service_meter_counts_for_points`'
    own — category `meters` or `sub_meters`, lifecycle stage `in_service` by
    `behavior_class` (BR-AST-031) — so *"the meter on this point"* means here
    what it means on the bill run's Scope step. Ordered by number, so two reads
    give the same list.
    """
    from apps.assets import models as assets_models

    ids = [str(pid) for pid in (service_point_ids or ()) if pid]
    if not ids:
        return []
    rows = (
        assets_models.Asset.objects.filter(
            tenant_id=_tenant_id(),
            service_point_id__in=ids,
            status__behavior_class="in_service",
            type__category__in=("meters", "sub_meters"),
        )
        .order_by("asset_no", "id")
        .values("id", "asset_no", "service_point_id")
    )
    return [
        {
            "id": str(row["id"]),
            "asset_no": row["asset_no"],
            "service_point_id": str(row["service_point_id"]),
        }
        for row in rows
    ]


def assets_past_certification(
    *, as_of: Any = None, asset_type_ids: list[Any] | None = None
) -> list[dict[str, Any]]:
    """Assets whose certification life has run out. READ ONLY.

    Wave M's `asset_past_certification_life` trigger — the one the demo drives
    and the one `AST-04412` is the fixture for.

    ⚠ **TWO WAYS AN ASSET CAN BE PAST ITS LIFE, AND BOTH COUNT.** `assets.py`
    itself says so at the column (`certification_due`, CR-028 §BR-AST-047):
    *"explicit (import CERT_DUE); when unset the display derives last_test_date
    + interval"*. So a utility that imported a certification date has the date;
    a utility that did not has `purchase_date` (or `install_date`) plus
    `expected_life_years`, which is the same fact arrived at by arithmetic.
    **Reading only the explicit column would silently exempt every meter a
    utility never got round to importing a CERT_DUE for** — which on a small
    utility is most of them, and the rule would look like it was working.

    ⚠ **A WAREHOUSE ASSET IS NEVER A SUBJECT** (`CR-168-BRC10` §30, PO answer
    (3) of 2026-10-05): only an asset installed at a premises — `_installed_q`.

    ⚠ **A RETIRED ASSET IS NEVER PAST ITS LIFE.** A meter already pulled out of
    the ground does not need a crew sent to exchange it. `status.code` is a
    lookup row (BR-AST-031), so the CODE is what travels and the retired and
    disposed stages are excluded by name.
    """
    from datetime import date as _date

    from apps.assets import models as assets_models

    today = as_of or _date.today()
    qs = assets_models.Asset.objects.filter(tenant_id=_tenant_id())
    if asset_type_ids:
        qs = qs.filter(type_id__in=list(asset_type_ids))
    qs = qs.exclude(status__code__in=RETIRED_STAGE_CODES)
    # §30 — a meter on the shelf is never a subject (see `_installed_q`).
    qs = qs.filter(_installed_q())

    out: list[dict[str, Any]] = []
    for row in qs.select_related("status", "type").order_by("asset_no"):
        due = row.certification_due
        if due is None and row.expected_life_years:
            started = row.purchase_date or row.install_date
            if started is not None:
                try:
                    due = started.replace(year=started.year + int(row.expected_life_years))
                except ValueError:
                    # 29 February plus N years. A meter installed on a leap day
                    # is not a reason to skip it, so it falls back to the 28th.
                    due = started.replace(
                        year=started.year + int(row.expected_life_years), day=28
                    )
        if due is None or due > today:
            continue
        out.append(
            {
                "id": str(row.id),
                "asset_no": row.asset_no,
                "asset_type_id": str(row.type_id) if row.type_id else None,
                "certification_due": due.isoformat(),
                "service_point_id": (
                    str(row.service_point_id) if row.service_point_id else None
                ),
            }
        )
    return out


def _certification_due(row: Any) -> Any:
    """The date an asset's certification runs out — explicit, else derived
    from its start plus its expected life (`assets_past_certification`'s two
    ways, shared so the two readers can never disagree)."""
    due = row.certification_due
    if due is None and row.expected_life_years:
        started = row.purchase_date or row.install_date
        if started is not None:
            try:
                due = started.replace(year=started.year + int(row.expected_life_years))
            except ValueError:
                due = started.replace(year=started.year + int(row.expected_life_years), day=28)
    return due


def assets_due_within(
    *, days_ahead: int, as_of: Any = None, asset_type_ids: list[Any] | None = None
) -> list[dict[str, Any]]:
    """Assets whose certification runs out in the next `days_ahead` days — not
    yet, but soon. READ ONLY. `CR-168-BRC10` P3.32, the `compliance_calendar`
    process (WS-26's *Backflow test due*).

    The same fact as `assets_past_certification`, read AHEAD of the date: an
    asset already past its date is that reader's subject and never this one's,
    so the two processes on one rule cannot both fire on one asset the same
    night. A retired asset is never due.
    """
    from datetime import date as _date, timedelta

    from apps.assets import models as assets_models

    today = as_of or _date.today()
    horizon = today + timedelta(days=max(1, int(days_ahead)))
    qs = assets_models.Asset.objects.filter(tenant_id=_tenant_id())
    if asset_type_ids:
        qs = qs.filter(type_id__in=list(asset_type_ids))
    qs = qs.exclude(status__code__in=RETIRED_STAGE_CODES)
    # §30 — a meter on the shelf is never a subject (see `_installed_q`).
    qs = qs.filter(_installed_q())
    out: list[dict[str, Any]] = []
    for row in qs.select_related("status", "type").order_by("asset_no"):
        due = _certification_due(row)
        if due is None or due <= today or due > horizon:
            continue
        out.append(
            {
                "id": str(row.id),
                "asset_no": row.asset_no,
                "asset_type_id": str(row.type_id) if row.type_id else None,
                "certification_due": due.isoformat(),
            }
        )
    return out


def asset_type_id(asset_id: Any) -> str | None:
    """One asset's TYPE id, or None. READ ONLY.

    Kept separate from `asset()` rather than added to its dict, because that
    dict is already read in three places and widening a shared answer to serve
    one caller is how a payload becomes a bag. The Assets door needs exactly
    this one field, to filter templates by `wot_asset_types`.
    """
    from apps.assets import models as assets_models

    row = (
        assets_models.Asset.objects.filter(tenant_id=_tenant_id(), pk=asset_id)
        .values_list("type_id", flat=True)
        .first()
    )
    return str(row) if row else None


def asset_type_ids_of_names(names: list[str]) -> list[str]:
    """The tenant's asset-type ids for a list of type NAMES. READ ONLY.

    A rule is written by a supervisor picking *Water meter*, and what the rule
    stores is the id. This is the lookup that turns one into the other at seed
    time; nothing on the hot path calls it.
    """
    from apps.assets import models as assets_models

    rows = assets_models.AssetType.objects.filter(tenant_id=_tenant_id(), name__in=names)
    return [str(row.id) for row in rows]



def assets_on_points_queryset(
    point_ids: list[Any], *, asset_type_id: Any = None, q: str | None = None
) -> Any:
    """`CR-168-BRC10` P2.16/ruling 22 — the assets standing on these service
    points, for the raise's *Assets* table. A QUERYSET the caller pages in SQL
    (NFR-3). `q` matches the asset number, the serial and *where* (the
    location note) — ruling 22's three. Retired stages are not offered: nobody
    is sent to a meter already pulled out. READ ONLY.
    """
    from django.db.models import Q

    from apps.assets import models as assets_models

    qs = (
        assets_models.Asset.objects.filter(tenant_id=_tenant_id(), service_point_id__in=point_ids)
        .exclude(status__code__in=RETIRED_STAGE_CODES)
        .select_related("type")
    )
    if asset_type_id:
        qs = qs.filter(type_id=asset_type_id)
    if q:
        qs = qs.filter(
            Q(asset_no__icontains=q) | Q(serial_no__icontains=q) | Q(location_note__icontains=q)
        )
    return qs.order_by("asset_no", "id")


#: The asset columns the field search reads, in the scan order `BR-FLD-00043`
#: (R43) gives — *"serial, then badge, then device ID"*. ⚠ **`assets` HOLDS NO
#: BADGE AND NO DEVICE-ID COLUMN** (`apps/assets/models.py`, read 2026-10-21),
#: so those two legs cannot be searched and the answer says so by name
#: (`FIELD_SEARCH_NOT_HELD`) rather than returning a silently partial result
#: (R42). Adding them is the assets module's change, never this seam's. The
#: utility's own asset number (`asset_no`, B14 rule 31's visible reference) is
#: searched next, then the address and the account number (requirement 37).
FIELD_SEARCH_NOT_HELD: tuple[str, ...] = ("badge", "device_id")


def field_search_queryset(
    text: str,
    *,
    address_point_ids: Any,
    address_unit_ids: Any,
    account_point_ids: Any,
    account_unit_ids: Any,
) -> Any:
    """`CR-187-BRC10` T-40 — every asset of the tenant matching `text`, as a
    QUERYSET the caller pages in SQL (`NFR-3`; no cap — `NFR-5`). READ ONLY.

    The four `*_ids` are SUBQUERIES the caller built through the metering and
    customers seams (service points and units at a matching address, and on a
    unit whose account number matches) — this seam never joins
    `service_point__unit__premises` itself, for the reason `meter()` gives.

    Annotated with `match_rank` (lower is better — the R43 scan order: exact
    serial, exact asset number, then prefixes, then contains, then the address
    and account legs), `match_on` (which leg matched) and `seat_unit_id` (the
    unit an OPEN `asset_assignments` row seats it on, for a device with no
    service point). Every stage, retired included: a technician holding a pulled
    meter's sticker is still asking where it went.
    """
    from django.db.models import Case, CharField, Exists, IntegerField, OuterRef, Q, Subquery, Value, When

    from apps.assets import models as assets_models

    seated = assets_models.AssetAssignment.objects.filter(
        tenant_id=_tenant_id(), asset_id=OuterRef("pk"), to_date__isnull=True
    )
    by_address = Q(service_point_id__in=address_point_ids) | Q(
        Exists(seated.filter(unit_id__in=address_unit_ids))
    )
    by_account = Q(service_point_id__in=account_point_ids) | Q(
        Exists(seated.filter(unit_id__in=account_unit_ids))
    )

    legs = [
        (Q(serial_no__iexact=text), 0, "serial"),
        (Q(asset_no__iexact=text), 1, "asset_no"),
        (Q(serial_no__istartswith=text), 2, "serial"),
        (Q(asset_no__istartswith=text), 3, "asset_no"),
        (Q(serial_no__icontains=text), 4, "serial"),
        (Q(asset_no__icontains=text), 5, "asset_no"),
        (by_address, 6, "address"),
        (by_account, 7, "account_no"),
    ]
    matches = legs[0][0]
    for condition, _rank, _leg in legs[1:]:
        matches |= condition
    return (
        assets_models.Asset.objects.filter(tenant_id=_tenant_id())
        .filter(matches)
        .select_related("type", "status", "parent_asset")
        .annotate(
            match_rank=Case(
                *[When(condition, then=Value(rank)) for condition, rank, _leg in legs],
                default=Value(99),
                output_field=IntegerField(),
            ),
            match_on=Case(
                *[When(condition, then=Value(leg)) for condition, _rank, leg in legs],
                default=None,
                output_field=CharField(),
            ),
            seat_unit_id=Subquery(seated.order_by("-from_date").values("unit_id")[:1]),
        )
        .order_by("match_rank", "asset_no", "id")
    )


def field_search_row(row: Any) -> dict[str, Any]:
    """One asset as FF-41 draws its card — *W-4471 · 1400 Elm Street · Unit A ·
    Neptune T-10 · 5/8"* or *Sub-meter*. Names, never ids on screen (B14 rule
    31): `id` is here only so the phone can open the asset."""
    kind = getattr(row, "type", None)
    parent = getattr(row, "parent_asset", None)
    return {
        "id": str(row.id),
        "asset_no": row.asset_no,
        "serial": row.serial_no,
        "type": None if kind is None else kind.name,
        "manufacturer": row.manufacturer,
        "model": row.model,
        "size_class": row.size_class,
        "sub_meter": row.parent_asset_id is not None,
        "parent_asset_no": None if parent is None else parent.asset_no,
        "status": getattr(getattr(row, "status", None), "code", None),
        "match_on": getattr(row, "match_on", None),
        "service_point_id": str(row.service_point_id) if row.service_point_id else None,
        # Normalised through `uuid.UUID`: a subquery annotation comes back as
        # SQLite's bare 32-hex text but PostgreSQL's dashed form, and the caller
        # keys a dict by it.
        "seat_unit_id": (
            str(uuid.UUID(str(row.seat_unit_id))) if getattr(row, "seat_unit_id", None) else None
        ),
    }


def asset_raise_row(row: Any) -> dict[str, Any]:
    """One asset as the raise's table shows it — names, never ids on screen."""
    kind = getattr(row, "type", None)
    return {
        "id": str(row.id),
        "asset_no": row.asset_no,
        "serial": row.serial_no,
        # The on-site note (image 15's WHERE, *Front boundary box*).
        "location": row.location_note,
        "type": None if kind is None else {"id": str(kind.id), "name": kind.name},
        "service_point_id": str(row.service_point_id) if row.service_point_id else None,
    }

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-005@87b94265 (EP-WRK-01)
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: G78 · pytest tests/test_us_wrk_005_module.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
