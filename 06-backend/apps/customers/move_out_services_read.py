# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10051 — move-out step 2 listed METERS only, so sewer, trash
#           and fire were invisible on the screen that closes them.
# Ruling:   PO 2026-10-11, decision log *"MOVE-OUT STEP 2 — EVERY SERVICE ON
#           THE UNIT, GROUPED BY HOW IT IS BILLED"* — *"this is correct"*.
# Rules:    BR-TEN-1180 (billing_basis: metered · share · capacity — the
#           TENANT's declaration) · BR-RAT-015 / BR-RAT-1030 (a share of
#           another service, by usage or by charge) · BR-RAT-090 (capacity is
#           a COUNT of the unit's assets) · B14 rule 31 (names, never ids)
# Tests:    06-backend/tests/test_def_cus_10051_move_out_services.py
# ───────────────────────────────────────────────────────
"""**Every service on the unit, grouped by how it is billed** — one READ for
move-out step 2. Nothing here writes and nothing here computes money.

Shape (``services_by_basis(unit_id, as_of)``)::

    {
      "unit_id": "<uuid>",
      "as_of": "2026-10-31",                 # the move-out date — billed through
      "services": [{"service": "water", "billing_basis": "metered"}, ...],
      "metered": [{"service": "water", "asset_nos": ["W-5042"]}],
      "share": [{"service": "sewer", "percent": "80.000000",
                 "percent_basis": "usage", "basis_service": "water",
                 "source_asset_nos": ["W-5042"], "terms_absent": null}],
      "capacity": [{"service": "trash", "type_name": "Trash cart",
                    "size_class": "TC-96", "size_name": "96-gal cart",
                    "asset_nos": ["TC-1", "TC-2"], "count": 2}],
    }

⚠ **THE METERED ROWS STILL COME FROM ``GET /units/{id}/assets``.** The move-out
draft (``useReadsDraft``) is keyed on that payload's asset ids, and a second
source of the same meters would be two answers to which registers close the
account. This read says WHICH services are metered; the screen keeps drawing
the meter rows it always drew, and moves a cart or a fire line into the
capacity group by the service it stands on.

⚠ **A SHARE'S PERCENT IS RATING'S STORED FIGURE, FORWARDED VERBATIM** (points:
``80`` is 80%). No plan, or no schedule for the service, is a STATED absence in
``terms_absent`` and never a guessed percent — the screen draws a dash.

⚠ **THE COUNT IS THE ASSETS STANDING ON THE UNIT TODAY**, grouped by service,
type and size class. It is the list a clerk is shown, not a priced quantity:
the bill run asks ``billable_asset_count`` for itself and nothing here feeds it.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from core import errors

from apps.customers import seams

#: BR-TEN-1180's three values, as tenancy declares them. Read from the tenancy
#: module rather than retyped, so a rename there cannot silently empty a group.
CATEGORY_READ = ("meters", "sub_meters")


def _bases() -> tuple[str, str, str]:
    from apps.tenancy import models as tenancy_models

    return (
        tenancy_models.BILLING_BASIS_METERED,
        tenancy_models.BILLING_BASIS_SHARE,
        tenancy_models.BILLING_BASIS_CAPACITY,
    )


def _billing_basis(service_code: str) -> str:
    """The tenant's declaration through tenancy's own ``service_row``. A
    service tenancy cannot describe reads as ``metered`` — tenancy's own
    default, for its own reason (an undeclared service has not declared *no
    register*)."""
    metered, _share, _capacity = _bases()
    fn = seams.resolve("tenancy", "service_row", kind="selectors")
    if fn is None:
        return metered
    try:
        row = fn(service_code)
    except errors.NotFoundError:  # a service tenancy 404s is still drawn
        return metered
    return str(row.get("billing_basis") or metered)


def _size_names() -> dict[str, str]:
    fn = seams.resolve("tenancy", "service_size_class_names", kind="selectors")
    return dict(fn() or {}) if fn is not None else {}


def _share_terms(unit: Any, service_code: str, as_of: date) -> dict[str, Any]:
    """The unit's plan → its schedule for this service → the version in force
    on ``as_of``: ``{percent, percent_basis, basis_service, terms_absent}``."""
    out: dict[str, Any] = {
        "percent": None,
        "percent_basis": None,
        "basis_service": None,
        "terms_absent": None,
    }
    plan_id = getattr(unit, "rate_plan_id", None)
    if plan_id is None:
        out["terms_absent"] = "unit_has_no_plan"
        return out
    plan_fn = seams.resolve("rating", "plan_detail", kind="selectors")
    schedule_fn = seams.resolve("rating", "schedule_detail", kind="selectors")
    if plan_fn is None or schedule_fn is None:
        out["terms_absent"] = "rating_not_wired"
        return out
    try:
        plan = plan_fn(plan_id, as_of)
    except errors.NotFoundError:  # a plan this tenant cannot read
        out["terms_absent"] = "plan_not_found"
        return out
    tariff_id = next(
        (
            row.get("tariff_id")
            for row in plan.get("rate_schedules") or []
            if row.get("service") == service_code
        ),
        None,
    )
    if tariff_id is None:
        out["terms_absent"] = "plan_prices_no_schedule"
        return out
    try:
        card = schedule_fn(tariff_id, as_of)
    except errors.NotFoundError:  # a schedule this tenant cannot read
        out["terms_absent"] = "schedule_not_readable"
        return out
    structure = ((card or {}).get("current_version") or {}).get("structure") or {}
    if structure.get("percent") is None:
        out["terms_absent"] = "schedule_states_no_percent"
        return out
    out["percent"] = structure.get("percent")
    out["percent_basis"] = structure.get("percent_basis")
    out["basis_service"] = structure.get("basis_service")
    return out


def services_by_basis(unit_id: Any, as_of: date | None = None) -> dict[str, Any]:
    _metered, share_basis, capacity_basis = _bases()
    unit = seams.unit_row(unit_id)  # tenant boundary first: 404, never 403
    when = as_of if as_of is not None else seams.tenant_today()
    points = seams.service_points_for(unit_id)
    service_of_point = {str(p.get("id")): p.get("service") for p in points}
    offer: list[str] = []
    for point in points:
        code = point.get("service")
        if code and code not in offer:
            offer.append(code)
    fn = seams.resolve("assets", "meter_facts_for_unit", kind="selectors")
    facts = list(fn(unit_id)) if fn is not None else []

    def _service(fact: dict[str, Any]) -> str | None:
        return service_of_point.get(str(fact.get("service_point_id")))

    read_nos: dict[str, list[str]] = {}
    for fact in facts:
        if fact.get("category") == "meters" and not fact.get("parent_asset_no"):
            code = _service(fact)
            if code:
                read_nos.setdefault(code, []).append(str(fact.get("asset_no")))

    basis_of = {code: _billing_basis(code) for code in offer}
    sizes = _size_names()
    metered: list[dict[str, Any]] = []
    share: list[dict[str, Any]] = []
    capacity: list[dict[str, Any]] = []
    for code in offer:
        basis = basis_of[code]
        if basis == share_basis:
            terms = _share_terms(unit, code, when)
            share.append(
                {
                    "service": code,
                    **terms,
                    "source_asset_nos": list(read_nos.get(terms["basis_service"] or "", [])),
                }
            )
        elif basis == capacity_basis:
            groups: dict[tuple[str, str], dict[str, Any]] = {}
            for fact in facts:
                if _service(fact) != code or fact.get("category") in CATEGORY_READ:
                    continue
                size = fact.get("size_class")
                key = (str(fact.get("type") or ""), str(size or ""))
                group = groups.setdefault(
                    key,
                    {
                        "service": code,
                        "type_name": fact.get("type_name"),
                        "size_class": size,
                        # None when unrecorded OR unnamed — never the code (rule 31).
                        "size_name": sizes.get(str(size)) if size else None,
                        "asset_nos": [],
                        "count": 0,
                    },
                )
                group["asset_nos"].append(fact.get("asset_no"))
                group["count"] += 1
            capacity.extend(groups.values())
        else:
            metered.append({"service": code, "asset_nos": list(read_nos.get(code, []))})
    return {
        "unit_id": str(unit_id),
        "as_of": when.isoformat(),
        "services": [{"service": code, "billing_basis": basis_of[code]} for code in offer],
        "metered": metered,
        "share": share,
        "capacity": capacity,
    }
