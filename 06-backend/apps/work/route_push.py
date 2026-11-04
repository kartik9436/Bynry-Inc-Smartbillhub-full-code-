# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10606 — a route assigned or taken away reached the phone
#           only at its next sync; nothing told the technician.
# Ruling:   PO 2026-10-26 (decision log, both 2026-10-26 sections) — *"we will
#           send this in notification"*, then *"yes do it"*: a route's reader
#           assigned, reassigned or unassigned pushes the NEW reader and the
#           OLD reader, as the existing wake-up-and-sync push.
# Rules:    BR-WRK-002 (another module acts on work through a NAMED door, never
#           its private functions) · BR-WRK-025 (the push is a consequence,
#           never a second act) · decision log 2026-10-04 sync design (a push
#           carries nothing that matters if lost; the phone then syncs) ·
#           CLAUDE.md hard rules 1 (tenant scope) and 7 (audit)
# Tests:    06-backend/tests/test_def_met_10606_route_push.py
# Impacts:  apps/metering/seams.py `notify_route_readers` (the only caller) ·
#           apps/work/push.py (`route_change` kind; `register` routes this job)
#           · field-app/src/device/native/notifications.ts (the channel) ·
#           field-app/src/sync/routeWake.ts (the phone downloads its routes)
# ───────────────────────────────────────────────────────
"""`work.route_push` — tell a technician their meter-reading routes changed.

THE DOOR
--------
`notify_routes_changed(changes, actor_id=…)` is the ONE function another module
calls. Metering calls it through `apps/metering/seams.notify_route_readers`,
after the route assignment has COMMITTED (`transaction.on_commit`), so an
assignment that rolls back pushes nobody. `changes` is keyed by the reader's
LOGIN id (routes are assigned to a login, `routes.assigned_to`):

    {user_id: {"gained": [{"code", "name"}, …], "lost": [{"code", "name"}, …]}}

**One job per technician per request**, however many routes moved: a bulk
assign of five routes to Mia is ONE push saying *5 new routes*, and the
reassignment that took them from Ray is ONE push to Ray.

WHAT THE PUSH IS
----------------
The doorbell, never the parcel. `route_message` carries the counts and, when
exactly one route moved, its code and name — no address, no customer, no money
— and the handset renders the words from its own catalogue by `kind` (B14 rule
35). On receipt the phone downloads its routes (`field-app/src/sync/
routeWake.ts`), which is the same download its next sync would have done; a
push lost on the way costs only the delay it was meant to save.

⚠ **THE KIND IS `route_change` AND ITS CHANNEL ID IS A CONTRACT WITH AN
INSTALLED APP** (`push.py` — a kind is added, never renamed).

THE AUDIT LINE
--------------
Written by the JOB, from a COUNT of active devices (the `push.py` rule): a
reader with a registered phone reads *pushed*, one with none — or with no
technician profile at all — reads *waiting for the phone*. Never *pushed* when
nothing was addressed.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from core import audit as core_audit
from core import jobs as core_jobs

logger = logging.getLogger("smartbillhub.work.route_push")

#: The job kind. Rides the `work` queue with `work.push` (`push.register`).
ROUTE_PUSH_JOB = "work.route_push"

#: The push kind (`push.PUSH_KINDS`).
KIND = "route_change"

ACTION_PUSHED = "work.route_change.pushed"
ACTION_WAITING = "work.route_change.waiting_for_phone"


def _routes(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in value or []:
        if isinstance(item, dict) and item.get("code"):
            out.append({"code": str(item["code"]), "name": item.get("name") or None})
    return out


def route_message(*, gained: list[dict[str, Any]], lost: list[dict[str, Any]]) -> dict[str, Any]:
    """The `route_change` push body: counts, and the route when exactly one
    moved in the direction the phone will name (gained first)."""
    from apps.work import push

    gained, lost = _routes(gained), _routes(lost)
    data: dict[str, Any] = {"gained": len(gained), "lost": len(lost)}
    named = gained if gained else lost
    if len(named) == 1:
        data["route"] = named[0]["code"]
        if named[0]["name"]:
            data["route_name"] = named[0]["name"]
    return push.push_message(KIND, data)


def notify_routes_changed(changes: dict[Any, dict[str, Any]], *, actor_id: Any = None) -> list[str]:
    """Enqueue ONE `work.route_push` job per technician named in `changes`.

    Called after the assignment committed, under the tenant in context.
    ⚠ **A FAILURE HERE NEVER UNDOES THE ASSIGNMENT** (`US-WRK-030` TC-3's rule,
    for the same reason): the route is already the reader's, the phone gets it
    on its next sync, and the failure is LOGGED with the reader it was for.
    Returns the job ids enqueued.
    """
    ids: list[str] = []
    for user_id, change in changes.items():
        gained, lost = _routes(change.get("gained")), _routes(change.get("lost"))
        if not user_id or not (gained or lost):
            continue
        payload = {
            "user_id": str(user_id),
            "gained": gained,
            "lost": lost,
            "actor_id": str(actor_id) if actor_id else None,
        }
        try:
            # A key per REQUEST: two quick changes are two pushes, each with
            # its own words, never folded into the first (NFR-16 folds an
            # active job with the same key).
            record = core_jobs.enqueue(
                ROUTE_PUSH_JOB, payload=payload, scope_key=f"routes:{user_id}:{uuid.uuid4()}"
            )
        except Exception as exc:  # noqa: BLE001 — the assignment stands
            logger.warning(
                "work.route_push could not be enqueued for user %s: %r — the route "
                "change stands and the phone gets it on its next sync",
                user_id,
                exc,
            )
            continue
        ids.append(str(record["id"]))
    return ids


def _technician_id(user_id: Any) -> Any:
    from apps.work import models
    from core import tenancy as core_tenancy

    row = (
        models.Technician.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), user_id=user_id
        )
        .values_list("id", flat=True)
        .first()
    )
    return row


def run_route_push_job(record: dict[str, Any]) -> None:
    """The BODY: address the reader's active devices with ONE `route_change`
    message and write the one audit line that is true."""
    from apps.work import push

    payload = record.get("payload") or {}
    user_id = payload.get("user_id")
    gained, lost = _routes(payload.get("gained")), _routes(payload.get("lost"))
    message = route_message(gained=gained, lost=lost)
    technician_id = _technician_id(user_id) if user_id else None
    devices = push._active_devices(technician_id)
    attempted = push._deliver(devices, message, kind=KIND) if devices else 0
    core_audit.write_row(
        action=ACTION_PUSHED if attempted else ACTION_WAITING,
        entity_type="user",
        entity_id=user_id,
        actor_user_id=payload.get("actor_id"),
        after={
            "gained": [r["code"] for r in gained],
            "lost": [r["code"] for r in lost],
            "devices": attempted,
            "kind": KIND,
            "delivery": "pushed to phone" if attempted else "waiting for the phone",
        },
    )
    return None


__all__ = [
    "ACTION_PUSHED",
    "ACTION_WAITING",
    "KIND",
    "ROUTE_PUSH_JOB",
    "notify_routes_changed",
    "route_message",
    "run_route_push_job",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-MET-10606 · PO 2026-10-26 ("we will send this in notification", "yes do it")
# generated: 2026-10-26 by the route-push lane
# checklist: A✔ B✔ C✔ D=n/a(no route — metering's set_reader calls it on commit) E✔(field-app channel + download) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_def_met_10606_route_push.py (red first) · G78 · G109
# exceptions: `push._deliver` addresses no provider today (push.py says so); the phone's download is the delivery
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
