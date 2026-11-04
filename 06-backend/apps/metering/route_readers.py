# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10591 — no screen could assign a route's reader, so the
#           phone's Reads tab was empty for every technician (beta MQ-033).
# Ruling:   PO 2026-10-24, decision log "MQ-033: METER-READ FORMAT TEMPLATES
#           (option B), AND READER ASSIGNMENT ON THE CYCLE'S ROUTES TAB" —
#           *"i have given you a screen from where assign/reassign should be
#           done"*. SUPERSEDES, for Reads → cycle → Routes ONLY, `CR-029` D6 and
#           `OQ-343`; Settings → Routes stays reader-free.
# Rules:    BR-FLD-00087 (R87 — one reader per route for now; nothing assumes
#           it: the phone's visibility is ONE predicate, `field_routes.
#           reader_routes`) · BR-FLD-00104 (R104 — the whole route on the
#           phone before the walk) · CLAUDE.md hard rules 1 (tenant scoping),
#           7 (every change audited) · B2 §2 (`routes.assigned_to` is the
#           reviewed cross-module FK to `identity.User`; identity is READ
#           through `seams`, never written) · NFR-3 / NFR-5 (the picker pages,
#           nothing caps)
# Tests:    06-backend/tests/test_mq033_route_readers.py ·
#           06-backend/tests/test_def_met_10606_route_push.py (the push,
#           DEF-MET-10606)
# ───────────────────────────────────────────────────────
"""Who reads a route: set, change or clear the reader on one or many routes.

THE ONE WRITE
─────────────
`set_reader(actor, {"route_ids": [...], "reader_id": <uuid> | None})` writes
`routes.assigned_to` on every named route of THIS tenant and one `audit_log`
row per route that actually changed (`route.reader_changed`, before → after,
with the reader's NAME beside the id so the trail reads without a join). A
route whose reader is already the one asked for is left alone and counted as
unchanged — re-saving is not an event.

* **The reader must be an ACTIVE field technician of this tenant**
  (`seams.field_technician`). A clerk, an invited or deactivated login and
  another tenant's user are all the SAME refusal, on `reader_id`, so a probe
  learns nothing about who exists elsewhere (HR-1).
* **Every route id must be this tenant's and live.** One foreign or unknown
  id refuses the WHOLE request as one 404 (`deny_as_not_found`) — a bulk
  assign half-applied over a typo would leave the clerk guessing which half.
* **`reader_id: null` unassigns.** The route then reaches no phone at all
  (R87's predicate matches nobody), which is what *Unassign* means.

WHAT THE PHONE SEES, AND WHEN
─────────────────────────────
The phone lists its routes from `field_routes.reader_routes` — R87's ONE
predicate, `assigned_to == me`: the new reader gains the route and the old
reader's phone drops it (`field-app/src/sync/routes.ts`, `DEF-FLD-10592`),
keeping it while it holds readings not yet sent.

**AND EVERY READER AFFECTED IS RUNG (`DEF-MET-10606`, PO 2026-10-26: *"we will
send this in notification"*, then *"yes do it"*).** This paragraph read *"THE
WAKE UP AND SYNC PUSH IS ABSENT"* until that ruling, because no work door let
metering ask for one. There is one now: `seams.notify_route_readers` hands
`{reader: {gained, lost}}` to work's `route_push.notify_routes_changed` ON
COMMIT, so a rolled-back assignment rings nobody. **One push per reader per
request** — a bulk of five to Mia is one *5 new routes*, and Ray, who lost
them, gets one *5 routes removed*. The push carries counts and, for a single
route, its code and name; the phone renders the words and downloads its routes
(`field-app/src/sync/routeWake.ts`). It is the doorbell, never the parcel: a
push lost on the way leaves the change to the next sync, exactly as before.
This file imports nothing of work's — the door is metering's own seam.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import transaction

from apps.metering import models, seams
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

#: The audit action one changed route writes.
AUDIT_ACTION = "route.reader_changed"


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _uuid_or_none(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _refuse(field: str, code: str, message_key: str) -> errors.ValidationError:
    return errors.ValidationError(
        code,
        message_key=message_key,
        field_errors=[{"field": field, "code": code, "message_key": message_key, "params": {}}],
    )


def _route_ids(payload: dict[str, Any]) -> list[UUID]:
    raw = payload.get("route_ids")
    if not isinstance(raw, list) or not raw:
        raise _refuse("route_ids", errors.VAL_REQUIRED, "metering.routeReader.noRoutes")
    ids: list[UUID] = []
    for value in raw:
        parsed = _uuid_or_none(value)
        if parsed is None:
            # A malformed id is the same answer as a foreign one (HR-1).
            raise errors.deny_as_not_found(br_ref="BR-TEN-003")
        if parsed not in ids:
            ids.append(parsed)
    return ids


def _reader(payload: dict[str, Any]) -> dict[str, Any] | None:
    if "reader_id" not in payload:
        raise _refuse("reader_id", errors.VAL_REQUIRED, "metering.routeReader.notTechnician")
    raw = payload.get("reader_id")
    if raw is None or raw == "":
        return None
    parsed = _uuid_or_none(raw)
    reader = seams.field_technician(parsed) if parsed is not None else None
    if reader is None:
        raise _refuse("reader_id", errors.VAL_UNKNOWN_LOOKUP, "metering.routeReader.notTechnician")
    return reader


def set_reader(actor: Any, payload: Any) -> dict[str, Any]:
    """Set (or, with `reader_id: null`, clear) the reader on every named route.

    Returns `{updated, unchanged, routes: [{id, code, reader}]}` — `reader` is
    `{id, name}` or None, the shape `route_dict` serves, so the screen can
    redraw the rows it changed without a second read.
    """
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="metering.payload_not_object")
    route_ids = _route_ids(payload)
    reader = _reader(payload)
    new_id = UUID(reader["id"]) if reader is not None else None
    actor_id = getattr(actor, "id", None) or getattr(actor, "pk", None)

    with transaction.atomic():
        rows = list(
            models.Route.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), pk__in=route_ids, deleted_at__isnull=True)
            .order_by("code", "id")
        )
        if len(rows) != len(route_ids):
            raise errors.deny_as_not_found(br_ref="BR-TEN-003")
        names = seams.user_display_names([row.assigned_to_id for row in rows])
        updated = 0
        # Who to ring, and about what: ONE entry per reader however many
        # routes moved (DEF-MET-10606).
        changes: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for row in rows:
            old_id = row.assigned_to_id
            if old_id == new_id:
                continue
            row.assigned_to_id = new_id
            row.save(update_fields=["assigned_to", "updated_at"])
            updated += 1
            moved = {"code": row.code, "name": row.name or None}
            if new_id is not None:
                changes.setdefault(str(new_id), {"gained": [], "lost": []})["gained"].append(moved)
            if old_id is not None:
                changes.setdefault(str(old_id), {"gained": [], "lost": []})["lost"].append(moved)
            core_audit.write_row(
                action=AUDIT_ACTION,
                entity_type="route",
                entity_id=row.id,
                actor_user_id=actor_id,
                before={
                    "route": row.code,
                    "assigned_to": str(old_id) if old_id else None,
                    "reader": names.get(str(old_id)) if old_id else None,
                },
                after={
                    "route": row.code,
                    "assigned_to": str(new_id) if new_id else None,
                    "reader": reader["name"] if reader is not None else None,
                },
            )
        # Inside the block on purpose: the seam schedules on COMMIT, so a
        # rollback anywhere above (or in the caller's transaction) rings nobody.
        seams.notify_route_readers(changes, actor_id=actor_id)
    return {
        "updated": updated,
        "unchanged": len(rows) - updated,
        "routes": [{"id": str(row.id), "code": row.code, "reader": reader} for row in rows],
    }


def reader_choices_queryset(q: str | None = None) -> Any:
    """The picker's population: active field technicians of this tenant, by
    name, `q` matching name or email. Paged by the caller (NFR-3)."""
    _tenant_id()
    return seams.field_technicians_queryset(q)


def reader_choice_row(membership: Any) -> dict[str, Any]:
    """One picker row. `id` is the anchor posted back, never drawn (B14 rule
    31); `name` falls back to the email for a login not yet named."""
    user = membership.user
    return {"id": str(user.id), "name": user.full_name or user.email, "email": user.email}

# ── Lifecycle ─────────────────────────────────────────────
# packet: MQ-033 (PO 2026-10-24, decision log "MQ-033 task (9) BUILT") · DEF-MET-10591
# generated: 2026-10-24 by the MQ-033 task-9 lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(no 🔒 path: no money, rate, RLS policy or idempotency key) F✔ G✔ H=n/a
# gates: ruff✔ · pytest tests/test_mq033_route_readers.py 18 passed (guards proved red first)
# exceptions: none — the wake-up push to the old and new reader is BUILT (DEF-MET-10606, 2026-10-26; tests/test_def_met_10606_route_push.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
