# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-001 (EP-WRK-01) — the raise that accepts an order with no
#           connection: a leak investigation on an existing meter can be
#           recorded at all. US-WRK-005 — this file is where the boundary gate
#           is shown RED (TC-3: one foreign write added here fails G78).
# Rules:    BR-WRK-006 (an order may exist without a connection; premises,
#           account and asset anchors beside it; at least one anchor) ·
#           BR-WRK-002 (the write goes through metering's own door, by name) ·
#           BR-MET-109 (a clerk raises as many orders as they want) ·
#           CLAUDE.md hard rule 7 (the audit row is metering's, and names the
#           anchor)
# Tests:    06-backend/tests/test_us_wrk_001_anchors.py ·
#           tests/test_us_wrk_001_anchor_check_pg.py (the CHECK, on PostgreSQL)
# Impacts:  apps/work/seams/metering_seam.py (the door) · wave B mounts
#           `POST /work-orders` onto this (07-endpoints.md §1 row 14)
# ───────────────────────────────────────────────────────
"""work write side — phase 0 holds ONE act, and it is a call through a door.

`raise_work_order(actor, payload)` is *"the one raise every door uses"*
(07-endpoints.md §1 row 14): the connection detail's *Add work order* (wave
B), the Assets door (wave M), the Customers move-out door (wave M) and the
rules engine (wave M) all arrive here. In wave A it is reached from the
terminal — the demo script's step 4 — and from the tests; the HTTP route lands
in wave B with the screen that presses it, because a route with no screen and
a screen with no route are the two halves of hard-won law 2.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
No ORM call. This module owns no table in phase 0 (`work_orders` is
metering's until 03-field-map.md §4 is decided after §16), and G78 fails the
first `.objects.create(` / `.update(` / `.delete(` / `.save(` on another
module's model anywhere under `apps/work/` — proved RED on this very file
before the gate was trusted (US-WRK-005 TC-3).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.work import models, selectors
from apps.work.seams import metering_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy


def raise_work_order(actor: Any, payload: Any) -> dict[str, Any]:
    """Raise one order on at least one anchor — connection · premises ·
    account · asset (BR-WRK-006).

    The answer is metering's: `{"id", "order_no", "connection_id",
    "premises_id", "account_id", "asset_id", "warnings"}`. An order naming no
    anchor is refused in Python with a sentence a clerk can read
    (`work.order.anchor_required`), and — should anything ever reach the table
    around that refusal — by the database's own CHECK
    (`ck_work_orders_has_anchor`, metering/0044, proved on PostgreSQL).
    """
    return metering_seam.raise_work_order(actor, payload)


# ── Reference data (wave C) ─────────────────────────────────────────────────
#: Which of this module's lists tenancy may ask us to seed, and where each
#: list's ratified rows live when the platform fixture carries none. The
#: fixture DELIBERATELY carries no `work_*` entries — the `premises_types`
#: posture (`DEF-026`): the module's own constant is the single source, so
#: there is no second copy in a versioned JSON file to drift away from it.
_SEED_FALLBACKS: dict[str, Any] = {
    "work_order_types": models.SEED_TYPES,
    "work_priorities": models.SEED_PRIORITIES,
    "work_skills": models.SEED_SKILLS,
    "work_safety_kits": models.SEED_SAFETY_KITS,
    "work_parts_categories": models.SEED_PART_CATEGORIES,
    "work_hold_reasons": models.SEED_HOLD_REASONS,
}


def seed_reference_list(list_code: str, entries: list[dict[str, Any]], fixture_version: str) -> int:
    """Seed one Work reference list for the tenant in context — tenancy's seam.

    Reached from `apps.tenancy.seams.seed_reference_list`, which is called by
    `ensure_reference_catalogs()` during provisioning and by the reference
    sweep. Raises `KeyError` for a list this module does not own, which is the
    contract every other owner follows (tenancy reads it as *"not mine"* and
    falls through to its hosted table).

    ⚠ **PRIORITIES BEFORE TYPES, AND IT IS NOT ALPHABETICAL LUCK.** A seeded
    type names its default priority BY CODE (`SEED_TYPES`), so the priorities
    must already be rows when the types are written or every type lands with a
    NULL default and the eight defaults r10 draws quietly disappear.
    `SEED_LIST_OWNERS` lists the five in that order and this docstring is why;
    a lane re-ordering that tuple alphabetically would break it silently, and
    `test_us_wrk_007_types.py` asserts the eight defaults so it would not stay
    broken.
    """
    from apps.work.lookups import WORK_LOOKUP_HANDLERS

    handler = WORK_LOOKUP_HANDLERS.get(list_code)
    if handler is None:
        raise KeyError(f"work owns no reference list {list_code!r}")
    tenant_id = core_tenancy.current_tenant_id()
    rows = list(entries) or [dict(row) for row in _SEED_FALLBACKS[list_code]]
    return handler().seed(tenant_id, rows)


def stock_position(part_id: Any) -> dict[str, Any]:
    """How many of this part are on hand, and where — **UNANSWERED**.

    ⚠ **NOTHING CALLS THIS, AND NOTHING EVER WILL — `OQ-WRK-1490` WAS RULED
    ON 2026-09-04 TO OPTION (a): NO STOCK.**
    The wireframe `Work-025` draws a stock register — *`MTR-W58 · Water meter
    5/8" · Yard · On hand 184 · Reorder at 60 · In cover`*, the same part on
    *Van 12* as a second row, a banner reading *"Reorder — 2 parts at or below
    reorder level"* and the sentence *"Issues deduct stock the moment they are
    recorded."* Every card that specifies the same feature says the opposite —
    *"No stock levels, no reorder points"* — because `CR-028` §11-D5 parked a
    parts-stock table when Assets was ruled into scope. The contradiction is
    filed as `DEF-WRK-3550`, and whether such a table may exist at all was
    `OQ-WRK-1490` — closed on 2026-09-04 in the Product Owner's own words,
    *"(a) — stock control is an inventory system, and the asset-maintenance
    precedent already parked it"*. **The contradiction resolves in favour of the
    cards, not the wireframe.**

    **What ships is option (a): the register and no stock.** `parts` carries no
    `on_hand`, no `reorder_at` and no `location`; `GET /work/parts` publishes
    no such key and `US-WRK-010` TC-5 asserts their absence by name. This
    function is the boundary made visible — the one place a lane reaching for
    a stock figure lands. ⚠ **IT IS A DELIBERATE ABSENCE, NOT A STUB AWAITING A
    RULING**, and the difference decides what the next lane does with it: a stub
    invites unblocking, a deliberate absence does not. The message below names
    the ruling instead of a question so nobody has to look it up to find out.
    """
    raise NotImplementedError(
        "ruled 2026-09-04: Work keeps a parts register and an issue log and no "
        "stock at all — no on-hand, no reorder point, no location, no deduction"
    )

# ── Work-025 · the parts register — the only Work-owned CRUD in wave C ──────
#: Four decimals stored, two displayed (CLAUDE.md hard rule 2). The scale is
#: checked BEFORE quantizing, so `92.40004` is REFUSED rather than silently
#: rounded to `92.4000` — `US-WRK-010` TC-3. A price quietly changed by the
#: thing that stored it is the shape of a defect nobody finds for a year.
UNIT_COST_PLACES = 4


def _part_field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse_part(field_errors: list[dict[str, Any]]) -> None:
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key=field_errors[0]["message_key"],
            params=field_errors[0]["params"],
            field_errors=field_errors,
        )


def _clean_part(payload: dict[str, Any], *, partial: bool, exclude_pk: Any = None) -> dict[str, Any]:
    """`BR-WRK-019` in one place: part no · name · category · unit · unit cost.

    ⚠ **AND NOTHING ELSE — an unknown field is REFUSED, not ignored.** That is
    what makes `on_hand`, `reorder_at` and `location` unreachable through this
    door rather than merely unlisted: a lane adding one to a request body gets
    a refusal naming the field, and `US-WRK-010` TC-5 asserts the answer
    carries no such key either. `OQ-WRK-1490` is OPEN and this is its edge.
    """
    from decimal import Decimal, InvalidOperation

    from apps.work import models as work_models

    tenant_id = core_tenancy.current_tenant_id()
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    allowed = {"part_no", "name", "category", "unit_of_measure", "unit_cost", "active"}
    for field in sorted(set(payload) - allowed):
        fe.append(_part_field_error(field, errors.VAL_FORMAT, "work.lookups.unknown_field"))

    # CR-168 · `DEF-WRK-9579` (P3.9) — a part is switched off and on from the
    # register. An EDIT only: a new part is in use, so `create_part` writes
    # `active=True` itself and refuses the field (below). A true boolean and
    # nothing else — `"maybe"` is refused rather than read as truthy.
    if "active" in payload:
        if not partial:
            fe.append(_part_field_error("active", errors.VAL_FORMAT, "work.lookups.unknown_field"))
        elif isinstance(payload["active"], bool):
            out["active"] = payload["active"]
        else:
            fe.append(_part_field_error("active", errors.VAL_FORMAT, "work.parts.active_yes_no"))

    for field in ("part_no", "name", "unit_of_measure"):
        if field in payload:
            value = str(payload[field] or "").strip()
            if not value:  # US-WRK-010 TC-4 — hard rule 3 for unit_of_measure
                fe.append(_part_field_error(field, errors.VAL_REQUIRED, "work.lookups.required"))
            elif len(value) > 60:
                fe.append(
                    _part_field_error(field, errors.VAL_RANGE, "work.lookups.too_long", max=60)
                )
            else:
                out[field] = value
        elif not partial:
            fe.append(_part_field_error(field, errors.VAL_REQUIRED, "work.lookups.required"))

    if "unit_cost" in payload or not partial:
        raw = str(payload.get("unit_cost", "0")).strip() or "0"
        try:
            cost = Decimal(raw)
        except (InvalidOperation, ValueError):
            fe.append(_part_field_error("unit_cost", errors.VAL_FORMAT, "work.parts.cost_number"))
        else:
            if cost < 0:
                fe.append(_part_field_error("unit_cost", errors.VAL_RANGE, "work.parts.cost_negative"))
            elif -cost.as_tuple().exponent > UNIT_COST_PLACES:
                fe.append(
                    _part_field_error(
                        "unit_cost", errors.VAL_RANGE, "work.parts.cost_places", max=UNIT_COST_PLACES
                    )
                )
            else:
                out["unit_cost"] = cost

    if "category" in payload:
        wanted = str(payload.get("category") or "").strip()
        if wanted == "":
            out["category"] = None
        else:
            categories = list(work_models.PartCategory.objects.filter(tenant_id=tenant_id))
            match = next((c for c in categories if c.name.lower() == wanted.lower()), None)
            if match is None:
                match = next((c for c in categories if c.code.lower() == wanted.lower()), None)
            if match is None:
                fe.append(
                    _part_field_error(
                        "category",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "work.parts.category_unknown",
                        allowed=[c.name for c in categories],
                    )
                )
            else:
                out["category"] = match

    if "part_no" in out:
        clash = work_models.Part.objects.filter(
            tenant_id=tenant_id, part_no__iexact=out["part_no"]
        )
        if exclude_pk is not None:
            clash = clash.exclude(pk=exclude_pk)
        existing = clash.first()
        if existing is not None:
            fe.append(
                _part_field_error(
                    "part_no",
                    errors.VAL_FORMAT,
                    "work.parts.duplicate_no",
                    existing=existing.part_no,
                )
            )
    _refuse_part(fe)
    return out


def create_part(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Add one part to the register (`Work-025`, `US-WRK-010` TC-1).

    Hard rule 7 — a unit cost is money, so the write carries an audit row with
    the price it was created at.
    """
    from apps.work import models as work_models

    cleaned = _clean_part(dict(payload or {}), partial=False)
    with transaction.atomic():
        row = work_models.Part.objects.create(
            tenant_id=core_tenancy.current_tenant_id(), is_system=False, active=True, **cleaned
        )
        core_audit.write_row(
            action="work.part.created",
            entity_type="part",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            after={
                "part_no": row.part_no,
                "name": row.name,
                "unit_of_measure": row.unit_of_measure,
                "unit_cost": f"{row.unit_cost:.4f}",
            },
        )
    return selectors.part(row.id)


def update_part(actor: Any, part_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Edit one part. Money moves, so before/after names the price both ways."""
    from apps.work import models as work_models

    row = work_models.Part.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=part_id
    ).first()
    if row is None:  # a cross-tenant id is INDISTINGUISHABLE from an absent one
        raise errors.NotFoundError()
    cleaned = _clean_part(dict(payload or {}), partial=True, exclude_pk=row.pk)
    if not cleaned:
        return selectors.part(row.id)
    before = {"part_no": row.part_no, "unit_cost": f"{row.unit_cost:.4f}", "active": row.active}
    with transaction.atomic():
        for field, value in cleaned.items():
            setattr(row, field, value)
        row.save(update_fields=[*cleaned.keys(), "updated_at"])
        core_audit.write_row(
            action="work.part.updated",
            entity_type="part",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            before=before,
            after={"part_no": row.part_no, "unit_cost": f"{row.unit_cost:.4f}", "active": row.active},
        )
    return selectors.part(row.id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-001@87b94265 · US-WRK-005@87b94265 (EP-WRK-01) · 07-endpoints.md §1 row 14
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D=deferred(wave B mounts POST /work-orders — 07-endpoints.md §1 row 14; the terminal is the door in wave A, by the plan's own demo script) E=deferred(same — the connection detail's Add work order is wave B's Work-002) F✔ G✔ H=n/a
# gates: G78 shown RED on this file first (US-WRK-005 TC-3), then green · pytest tests/test_us_wrk_001_anchors.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# CR-070 wave N · what a job cost — `US-WRK-050`, `051`, `053`
# ══════════════════════════════════════════════════════════════════════════

#: A rate is money: four decimals stored, two displayed (hard rule 2). Same
#: posture as `UNIT_COST_PLACES` above — the scale is checked BEFORE
#: quantizing, so `48.50004` is REFUSED rather than silently rounded. A price
#: quietly changed by the thing that stored it is a defect nobody finds for a
#: year, and this one would be found by a supervisor wondering why a report
#: disagrees with the screen they typed it on.
RATE_PLACES = 4


def _clean_labour_rate(payload: dict[str, Any]) -> dict[str, Any]:
    """`BR-WRK-020` in one place: role · hourly · overtime · threshold · from.

    ⚠ **AND NOTHING ELSE — an unknown field is REFUSED, not ignored**, the
    shape `_clean_part` uses one screen along. It is what keeps a
    `technician_id` out of this table by the door as well as by the schema:
    `WM-45` says a rate is per ROLE and never per person because *"a
    per-person rate is a salary, it belongs in payroll"*.
    """
    from decimal import Decimal, InvalidOperation

    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    allowed = {
        "role",
        "role_label",
        "hourly",
        "overtime_hourly",
        "overtime_after_hours",
        "effective_from",
    }
    for key in payload:
        if key not in allowed:
            fe.append(
                _part_field_error(key, errors.VAL_FORMAT, "work.labour_rate_unknown_field")
            )
    _refuse_part(fe)

    role = str(payload.get("role") or "").strip()
    if not role:
        fe.append(_part_field_error("role", errors.VAL_REQUIRED, "work.labour_rate_role_required"))
    out["role"] = role
    out["role_label"] = str(payload.get("role_label") or "").strip()

    def _money(field: str, *, required: bool) -> Any:
        raw = payload.get(field)
        if raw in (None, ""):
            if required:
                fe.append(
                    _part_field_error(field, errors.VAL_REQUIRED, "work.labour_rate_required")
                )
            #: ⚠ NULL, NOT ZERO. A contractor's overtime is a DASH — `BR-WRK-020`,
            #: *"an agency invoices its own overtime… The dash is the honest
            #: value"* — and a `0` default would give the agency free overtime.
            return None
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, ValueError):
            fe.append(_part_field_error(field, errors.VAL_FORMAT, "work.labour_rate_not_a_number"))
            return None
        if value < 0:
            fe.append(_part_field_error(field, errors.VAL_RANGE, "work.labour_rate_negative"))
            return None
        #: `US-WRK-051` TC-4 — five decimals is REFUSED, never rounded.
        if -value.as_tuple().exponent > RATE_PLACES:
            fe.append(_part_field_error(field, errors.VAL_FORMAT, "work.labour_rate_too_precise"))
            return None
        return value.quantize(Decimal(1).scaleb(-RATE_PLACES))

    out["hourly"] = _money("hourly", required=True)
    out["overtime_hourly"] = _money("overtime_hourly", required=False)

    threshold = payload.get("overtime_after_hours")
    if threshold in (None, ""):
        out["overtime_after_hours"] = None
    else:
        try:
            out["overtime_after_hours"] = Decimal(str(threshold))
        except (InvalidOperation, ValueError):
            fe.append(
                _part_field_error(
                    "overtime_after_hours", errors.VAL_FORMAT, "work.labour_rate_not_a_number"
                )
            )

    raw_from = payload.get("effective_from")
    if not raw_from:
        fe.append(
            _part_field_error("effective_from", errors.VAL_REQUIRED, "work.labour_rate_required")
        )
    else:
        parsed = parse_date(str(raw_from)) if isinstance(raw_from, str) else raw_from
        if parsed is None:
            fe.append(
                _part_field_error(
                    "effective_from", errors.VAL_FORMAT, "work.labour_rate_bad_date"
                )
            )
        else:
            out["effective_from"] = parsed

    _refuse_part(fe)
    return out


def create_labour_rate(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """A rate change is a NEW ROW — `BR-WRK-020`, `US-WRK-051` TC-3.

    ⚠ **NEVER AN UPDATE OF THE OLD ROW.** The old one is stamped
    `superseded_on` and stays exactly as it was, because `WO-4822` closed on
    15 March must still price at `48.5000` after the rate moves to `50.0000`
    on 1 April — and so must the 184 exchanges that closed before it. Editing
    in place would silently reprice work that is already done, which is hard
    rule 4's shape one table along from a bill.

    ⚠ **AND THE ORDER KEEPS ITS OWN SNAPSHOT ANYWAY**
    (`work_orders.labour_rate_snapshot`), so a report is reproducible even if
    every row here were deleted. Two mechanisms rather than one, because the
    thing being protected is a figure on a document somebody signed.

    Hard rule 7 — a rate is money, so the write carries an audit row naming
    the price both ways.
    """
    from apps.work import models as work_models

    cleaned = _clean_labour_rate(dict(payload or {}))
    tenant_id = core_tenancy.current_tenant_id()
    with transaction.atomic():
        current = (
            work_models.LabourRate.objects.select_for_update()
            .filter(tenant_id=tenant_id, role=cleaned["role"], superseded_on__isnull=True)
            .first()
        )
        before = None
        if current is not None:
            before = {"hourly": f"{current.hourly:.4f}", "effective_from": str(current.effective_from)}
            #: The OLD row is stamped, not edited: `superseded_on` is the only
            #: column that moves, and it records WHEN it stopped being current
            #: rather than changing what it ever said.
            current.superseded_on = cleaned["effective_from"]
            current.save(update_fields=["superseded_on", "updated_at"])
        row = work_models.LabourRate.objects.create(tenant_id=tenant_id, **cleaned)
        core_audit.write_row(
            action="work.labour_rate.created",
            entity_type="labour_rate",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            before=before,
            after={
                "role": row.role,
                "hourly": f"{row.hourly:.4f}",
                "overtime_hourly": (
                    f"{row.overtime_hourly:.4f}" if row.overtime_hourly is not None else None
                ),
                "effective_from": str(row.effective_from),
            },
        )
    return selectors.labour_rate(row.id)


def create_part_issue(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """One movement of stores — `BR-WRK-049`, `US-WRK-050` TC-1 and TC-7.

    ⚠ **THIS MOVES NO COUNT ANYWHERE, BECAUSE NO COUNT LAWFULLY EXISTS.**
    `OQ-WRK-1490` closed 2026-09-04 to option (a): the register and the log,
    and no stock at all. D. Ortiz issuing two water meters from Van 12 against
    `WO-4821` writes ONE ROW and nothing decrements.

    ⚠ **A RETURN IS A NEW POSITIVE ROW, NEVER A DELETION OF THE ISSUE**
    (TC-7): `+4 · R. Patel · return · Unused on job`. Deleting the issue would
    make the log say the parts were never taken, which is not what happened.

    `order_ref` is plain text by design (`WM-22`) — a store-keeper writes *Van
    restock* or *Exchanges on Route 2 (ref WO-4821)*, neither of which is one
    order, and the register does not know what a work order is.
    """
    from decimal import Decimal, InvalidOperation

    from apps.work import models as work_models

    data = dict(payload or {})
    fe: list[dict[str, Any]] = []
    allowed = {
        "part_id",
        "qty",
        "issued_to_technician_id",
        "issued_to_crew_id",
        "purpose",
        "order_ref",
        "at",
    }
    for key in data:
        if key not in allowed:
            fe.append(
                _part_field_error(key, errors.VAL_FORMAT, "work.part_issue_unknown_field")
            )
    #: ⚠ THE THREE STOCK KEYS CANNOT ARRIVE FROM THE OTHER SIDE EITHER. An
    #: unknown field is refused by name, so `on_hand` in a request body gets a
    #: refusal rather than being quietly dropped — the same door `_clean_part`
    #: closes for the register.
    _refuse_part(fe)

    tenant_id = core_tenancy.current_tenant_id()
    part = work_models.Part.objects.filter(tenant_id=tenant_id, id=data.get("part_id")).first()
    if part is None:
        fe.append(_part_field_error("part_id", errors.VAL_REQUIRED, "work.part_issue_no_part"))
    try:
        qty = Decimal(str(data.get("qty")))
    except (InvalidOperation, ValueError, TypeError):
        qty = None
        fe.append(_part_field_error("qty", errors.VAL_FORMAT, "work.part_issue_not_a_number"))
    if qty is not None and qty == 0:
        #: A movement of nothing is a mis-keyed row. The CHECK refuses it in
        #: the database too, so this is the message and not the guarantee.
        fe.append(_part_field_error("qty", errors.VAL_RANGE, "work.part_issue_qty_zero"))
    tech_id = data.get("issued_to_technician_id") or None
    crew_id = data.get("issued_to_crew_id") or None
    if tech_id and crew_id:
        #: *"D. Ortiz and Crew 2"* is not an answer to *who has this part*.
        fe.append(
            _part_field_error(
                "issued_to_crew_id", errors.VAL_RANGE, "work.part_issue_one_holder"
            )
        )
    _refuse_part(fe)

    at = data.get("at")
    parsed_at = parse_datetime(str(at)) if isinstance(at, str) else at
    with transaction.atomic():
        row = work_models.PartIssue.objects.create(
            tenant_id=tenant_id,
            part=part,
            qty=qty,
            issued_to_technician_id=tech_id,
            issued_to_crew_id=crew_id,
            purpose=str(data.get("purpose") or "").strip(),
            order_ref=str(data.get("order_ref") or "").strip(),
            recorded_by_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            #: WHEN IT HAPPENED, which is not when the row was typed. A clerk
            #: catching up on Monday must not restamp Saturday's issue to
            #: Monday (`BR-TEN-043` — an event date, never a wall clock).
            at=parsed_at or timezone.now(),
        )
        core_audit.write_row(
            action="work.part_issue.recorded",
            entity_type="part_issue",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            after={"part_no": part.part_no, "qty": f"{row.qty:.4f}", "order_ref": row.order_ref},
        )
    return selectors.part_issue(row.id)


def reopened_after_acceptance(order_id: Any) -> bool:
    """True when the office has reopened this order AFTER an acceptance — PO
    answer 11 (2026-10-21) — so the next Accept is a RE-acceptance.

    Read from the reopen history (`work_order_reopens`, append-only): an
    `office_reopen` row whose `prior` carries an `accepted_at`. That row is
    written in the same transaction as metering's send-back clears the
    acceptance (`field_reopen._office_reopen`), so it is the one fact that
    says *this job was accepted once already*. Few rows per order; filtered in
    Python so the test is the same on SQLite and PostgreSQL.
    """
    from apps.work.field_order_models import REOPEN_BY_OFFICE, WorkOrderReopen

    priors = WorkOrderReopen.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        work_order_id=order_id,
        kind=REOPEN_BY_OFFICE,
    ).values_list("prior", flat=True)
    return any((prior or {}).get("accepted_at") for prior in priors)


def generate_work_order_report(actor: Any, order: Any) -> dict[str, Any] | None:
    """The report — **generated ONCE PER ACCEPTANCE, by Accept, never by completion**.

    ⚠ **THE NEXT VERSION, AFTER AN OFFICE REOPEN (PO answer 11, 2026-10-21).**
    The office may now reopen an accepted job. The frozen report is NEVER
    edited (`work/0011`'s trigger refuses it): the next acceptance writes
    version `latest + 1` BESIDE it, with its own cost lines tagged
    `report_version = latest + 1` (`work/0045`), and every reader takes the
    latest version's lines. A version is written only when an office reopen
    happened AFTER the latest report was generated — so a plain second call
    still produces nothing (`US-WRK-053` TC-5's backstop is unchanged).

    `BR-WRK-050`. *"It is generated on approval and not on completion, because
    until a person accepts the field data nothing on the page is final"*
    (`WM-47`). A report produced at completion would carry a total a
    supervisor had not yet agreed to.

    ⚠ **THIS IS CALLED FROM `metering.connections.accept_field_result` AND
    FROM NOWHERE ELSE** — `US-WRK-053` TC-7 asserts there is no other call
    site. A second Accept is already refused upstream; the unique key on
    (tenant, order, version) is the backstop, in the shape hard rule 6 uses
    for a bill run, so no second `v1` can exist even if a caller tried.

    ⚠ **THE COST LINES ARE PERSISTED, NOT RECOMPUTED ON READ.** A rate is
    superseded and a part's unit cost is edited; a report that recomputed
    would silently change after it was signed. `work/0011`'s freeze trigger
    holds both the report and its lines for the same reason.

    ⚠ **NO DOCUMENT YET.** The PDF is stored through tenancy's
    `stored_documents` under kind `work_order_report`, which wave `K` adds
    (`03-field-map.md` row 28, 33 → 36) and which has not landed. The row, its
    lines and its total ship now and `document_id` is filled the moment the
    kind exists — what is NOT deferred is the freeze, so the total on `-v1`
    cannot move in the meantime.
    """
    from apps.work import costing
    from apps.work import models as work_models

    from apps.work.field_order_models import REOPEN_BY_OFFICE, WorkOrderReopen

    tenant_id = core_tenancy.current_tenant_id()
    latest = (
        work_models.WorkOrderReport.objects.filter(tenant_id=tenant_id, work_order_id=order.id)
        .order_by("-version")
        .first()
    )
    if latest is not None:
        reopened_since = WorkOrderReopen.objects.filter(
            tenant_id=tenant_id,
            work_order_id=order.id,
            kind=REOPEN_BY_OFFICE,
            at__gt=latest.generated_at,
        ).exists()
        if not reopened_since:
            #: A second Accept produces NOTHING — not an error here, because the
            #: acceptance itself already refused; this is the belt to that brace.
            return None
    version = 1 if latest is None else latest.version + 1

    lines, total = costing.work_order_cost_lines(order)
    with transaction.atomic():
        report = work_models.WorkOrderReport.objects.create(
            tenant_id=tenant_id,
            work_order_id=order.id,
            version=version,
            generated_at=timezone.now(),
            generated_by_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            total=total,
        )
        for index, line in enumerate(lines):
            work_models.WorkOrderCostLine.objects.create(
                tenant_id=tenant_id,
                work_order_id=order.id,
                kind=line.kind,
                description=line.description,
                qty=line.qty,
                unit=line.unit,
                rate=line.rate,
                amount=line.amount,
                sequence=index,
                report_version=version,
            )
        core_audit.write_row(
            action="work.report.generated",
            entity_type="work_order_report",
            entity_id=report.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            after={
                "version": version,
                "total": f"{total:.2f}",
                "lines": len(lines),
                **({"supersedes_version": latest.version} if latest is not None else {}),
            },
        )
    return {
        "id": str(report.id),
        "version": version,
        "total": f"{total:.2f}",
        "lines": len(lines),
    }


def snapshot_labour_rate_at_close(order: Any) -> None:
    """Stamp what the labour line needs onto the order at CLOSE — `US-WRK-051`
    TC-2.

    `labour_rate_snapshot = 48.5000`, `labour_role = field_technician`, and the
    `minutes_on_site` those are multiplied by. After this the order prices
    itself and never consults `labour_rates` again.

    ⚠ **THIS FUNCTION HAD NO CALLER AT ALL UNTIL `DEF-WRK-4124`.** It was
    written, documented at length, and referenced by exactly one line in the
    whole repository: its own `def`. So `labour_rate_snapshot` was NULL on every
    order ever closed, and — with `minutes_on_site` having no column either —
    the labour line was doubly unreachable. `submit_field_result` calls it now,
    at the close, which is where `BR-WRK-020` says the rate is fixed.

    ⚠ **THE ROLE IS DERIVED FROM THE ASSIGNED TECHNICIAN'S TYPED LABEL**, and
    that is a judgment this lane made rather than a rule it was given (logged
    in `12-governance/02-decision-log.md`, 2026-09-05). `technicians.role_label`
    is prose a utility types — *Field technician*, *Senior technician* — and
    `labour_rates.role` is a code. Slugifying the label to match is what lets a
    tenant name its own roles without a second table mapping one to the other;
    a utility that types *Field Technician* and *field technician* still lands
    on one rate. When neither matches, NOTHING is stamped: an order with no
    snapshot yields no labour line at all, which reads as *we cannot say* on
    the report rather than as *free*.
    """
    from apps.work import field_labour
    from apps.work import models as work_models

    # CR-187-BRC10 T-38 — a second technician's rate is fixed at the SAME close
    # (`BR-WRK-020`); helpers only, so the lead's stamp below is untouched.
    field_labour.snapshot_rates_at_close(order)
    if getattr(order, "labour_rate_snapshot", None) is not None:
        # ⚠ **THE RATE STAYS FIXED; THE MINUTES FOLLOW THE LATEST CLOSE
        # (`DEF-WRK-4127`).** A job the office sent back is closed again with
        # the technician's corrected times, and those — not the first close's —
        # are what the frozen report prices at Accept. `BR-WRK-020` fixes the
        # RATE at the first close, never the duration.
        order.minutes_on_site = _minutes_on_site(order)
        order.save(update_fields=["minutes_on_site", "updated_at"])
        return
    tenant_id = core_tenancy.current_tenant_id()
    technician = getattr(order, "assignee_technician", None)
    crew = getattr(order, "assignee_crew", None)
    role = None
    if technician is not None and getattr(technician, "role_label", ""):
        role = technician.role_label.strip().lower().replace(" ", "_")
    elif crew is not None:
        role = work_models.LabourRate.ROLE_NETWORK_CREW
    if not role:
        return
    rate = work_models.LabourRate.objects.filter(
        tenant_id=tenant_id, role=role, superseded_on__isnull=True
    ).first()
    if rate is None:
        return
    order.labour_rate_snapshot = rate.hourly
    order.labour_role = role
    order.minutes_on_site = _minutes_on_site(order)
    order.save(
        update_fields=[
            "labour_rate_snapshot",
            "labour_role",
            "minutes_on_site",
            "updated_at",
        ]
    )


def _minutes_on_site(order: Any) -> int | None:
    """How long the crew were there — `completed_at` minus the last ARRIVAL.

    ⚠ **THIS IS A JUDGMENT THIS LANE MADE, AND IT IS LOGGED** (decision log,
    2026-09-06). No signed rule says which two moments bound *on site*;
    `costing.py`'s own docstring names the source and stops short of the
    arithmetic — *"`started_at` IS WAVE `J`'s `arrive` ASSIGNMENT ROW and is not
    on the order yet. Where a real arrival time comes from is the phone's."*
    So: the LAST `arrive` row before the close, to `completed_at`.

    **The last arrival and not the first**, because `work_order_assignments` is
    a history and a job that was visited, left and revisited has two; charging
    from the first would bill the customer for the gap between visits. A job
    reassigned mid-visit likewise has the arrival that matters last.

    ⚠ **NO ARRIVAL MEANS NONE, NEVER A GUESS.** `created_at` would price a job
    at however long it sat in a queue — `costing.py` says so in as many words —
    and a plausible-looking wrong duration on a frozen money report is worse
    than an absent labour line, which at least reads as *we cannot say*.

    ⚠ **AND A NEGATIVE OR ZERO SPAN YIELDS `None`.** A clock that disagrees with
    itself must not produce a credit on a cost report.
    """
    from apps.work import models as work_models

    # ── `DEF-WRK-4127` · THE TECHNICIAN'S OWN TWO TIMES COME FIRST ──────────
    # PO 2026-10-05: *"allow technicain to fill in time"*. An offline day's
    # `arrive` row is stamped when it SYNCS (`at` is auto_now_add on an
    # append-only table), so it can fall after the close and price nothing.
    # The close now carries *Arrived* and *Finished* as confirmed on the phone
    # (`mobile.labour_time_record`, validated there: finished after arrived,
    # neither in the future); where it does, those ARE the span.
    data = getattr(order, "field_data", None)
    entered = data.get("labour_time") if isinstance(data, dict) else None
    if isinstance(entered, dict) and entered.get("minutes"):
        minutes = int(entered["minutes"])
        return minutes if minutes > 0 else None

    completed_at = getattr(order, "completed_at", None)
    if completed_at is None:
        return None
    arrival = (
        work_models.WorkOrderAssignment.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            work_order_id=order.id,
            act=work_models.WorkOrderAssignment.ACT_ARRIVE,
            at__lte=completed_at,
        )
        .order_by("-at")
        .first()
    )
    if arrival is None:
        return None
    seconds = (completed_at - arrival.at).total_seconds()
    if seconds <= 0:
        return None
    return int(round(seconds / 60))


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE M · THE SAMPLE-DATA SEAM (DEF-WRK-4085)
# ══════════════════════════════════════════════════════════════════════════
#
# `apps/tenancy/seams.resolve` looks a block up as
# `apps.<module>.services.<seam>` and nowhere else, so the NAME lives here and
# the CODE lives in `sample_data.py` — the same split `apps/assets/services.py`
# and every other seeding module already uses. The import is inside each
# function because `sample_data` imports this module.


def seed_sample_records(actor: Any) -> int:
    """BR-TEN-056/057 — this module's block of the sample set: the seven rules
    of `Work-026`, six of them on. See `apps/work/sample_data.py`."""
    from apps.work import sample_data

    return sample_data.seed_sample_records(actor)


def seed_sample_workforce(actor: Any) -> int:
    """BR-TEN-056/057 — the crew, the register and the rates: three crew rows,
    four technicians with skills and certificates, ten parts and four labour
    rates. See `apps/work/sample_workforce.py`, which measures what was missing
    and why each number is that number."""
    from apps.work import sample_workforce

    return sample_workforce.seed_sample_records(actor)


def seed_sample_field_work(actor: Any) -> int:
    """BR-TEN-056/057 — the six published templates filled with tasks, parts,
    readings, safety steps and help, and one work order assigned, worked and
    costed end to end. See `apps/work/sample_field_work.py`."""
    from apps.work import sample_field_work

    return sample_field_work.seed_sample_records(actor)


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/066 — remove what is free, report the rest BY NAME. A rule
    that has already raised orders is switched off and RETAINED, because
    deleting it would delete the sweep's memory and re-raise the work.

    ⚠ **REMOVAL IS KEYED ON THE MODULE AND NOT ON THE BLOCK** —
    `apps/tenancy/sample_data.remove_sample_data` resolves
    `apps.<module>.services.remove_sample_records` ONCE per module, however
    many blocks that module owns. Work owns three, so this one function must
    cover all three or a block's rows would survive `--remove` with nothing
    reporting it. They run in `BR-TEN-061`'s reverse order: the field work
    first (it holds assignments and materials), then the workforce (crews are
    PROTECTed by technicians), then the rules."""
    from apps.work import sample_data, sample_field_work, sample_workforce

    removed = 0
    retained: list[dict[str, Any]] = []
    for module in (sample_field_work, sample_workforce, sample_data):
        outcome = module.remove_sample_records()
        removed += int(outcome.get("removed") or 0)
        retained.extend(outcome.get("retained") or ())
    return {"removed": removed, "retained": retained}


def sample_record_count() -> int:
    """How many sample rows this module holds right now, read live — across
    all THREE of Work's blocks, for `remove_sample_records`' reason."""
    from apps.work import sample_data, sample_field_work, sample_workforce

    return (
        sample_data.sample_record_count()
        + sample_workforce.sample_record_count()
        + sample_field_work.sample_record_count()
    )
