# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W3b item 1:
#           `PUT /routes/{id}/premises-order`, **the walk-order writer**.
#           B17 §5 gap G5 — *"`walk_order` exists with a uniqueness constraint
#           and NO WRITER"* — closes here.
#           Screens: SET-06D (Premises tab · drag-to-reorder · route sheet)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3, §6
# Rules:    D3 (*"Confirmed"* — build the ordering surface) · D11 (*"Per
#           premises"*) · BR-MET-033 (membership) · BR-MET-035b (config writes
#           are System Admin) · BR-MET-048 (route changes are audited) ·
#           CLAUDE.md rule 1 (tenant scoping · RLS FORCE) · rule 6
#           (idempotency) · rule 7 (every action is audited)
# Tests:    06-backend/tests/test_cr029_rcw3b_walk_order.py
# ───────────────────────────────────────────────────────
"""The walking order of a route — written once, at the grain the PO ruled.

**D11, VERBATIM: *"Per premises"*.** A three-unit building is ONE stop at ONE
sequence number, because a reader climbs those steps once. The screenshot that
numbers 1408 Elm's units 0142/0143/0144 is the wrong reading; Cedar Ct's three
units sharing 0145 is the right one, and B17 §3 records the ruling.

**WHAT THIS CLOSES.** RC-W1 landed `route_premises_orders` and RC-W3 landed the
drag-to-reorder that fills it, and between them sat nothing: the Save button
posted to a path that answered 404, which SET-06D says out loud rather than
pretending the edit stuck. A table plus a screen is not a feature.

⚠ **THE ORDER IS REPLACED, NOT PATCHED, AND THE CONSTRAINT IS THE REASON.**
`uq_route_premises_orders_walk_order` — *one position, one stop, because a
printed route sheet with two number 3s is a sheet a reader cannot follow* — is
not deferrable, so swapping two stops by updating rows in place collides
half-way through. Inside one transaction the route's stops are deleted and
rewritten, which is also what makes a retry land on exactly the same rows.

⚠ **THE PAYLOAD IS THE WHOLE WALK.** A list that omits a member is a premises
nobody visits, and a list that repeats one is a stop read twice; both are
refused before anything is written. This is stricter than the table (which
would happily hold a partial order) because the SHEET is printed from it.

⚠ **THE SUPERSEDED PER-UNIT COLUMN IS KEPT IN STEP, DELIBERATELY (a lane
judgment — REPORTED).** `route_memberships.walk_order` is superseded by D11 and
has never had a writer, and `selectors.route_members` still ORDERS BY it — which
is what `premisesStops()` on SET-06D folds into stops. Writing only the ruled
table would leave the screen re-reading the OLD order the moment it refreshed:
the save would appear to undo itself, with every test green. So the per-unit
column is written here as a PROJECTION of the ruled per-premises order — the
units of stop 1 first, then stop 2 — and its value is never rendered anywhere.
RC-W5 drops the column; until then a projection is what keeps the two
generations from disagreeing on screen.

⚠ **A STOP THAT LEAVES THE ROUTE IS NOT DELETED HERE.** Membership changes go
through `services.update_route`, which knows nothing about this table, so a
stored order can outlive its membership. The read below therefore filters to
CURRENT members and appends any unsequenced member at the end, rather than a
cascade this CR never ruled: a stale row is invisible and self-healing, and the
next save rewrites the set.

⚠ **WHY THIS IS NOT IN `services.py`** — the `import_runs.py` / `read_windows.py`
posture, stated there and reused here: LAW 0 is a MODULE boundary, so a metering
module may hold its own ORM against metering's OWN tables, and keeping a new
writer out of the 5,000-line shared file means a lane editing `services.py` and
this lane never touch one file (hard-won law 11). No table outside metering is
written here.

**NO MONEY** (BR-MET-078): a walk order is the sequence a crew walks in.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.metering import models
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import SYSTEM_ADMIN, require_role

__all__ = ["save_premises_order", "premises_order_for_route"]

#: **THE SHAPE REFUSAL, AND IT STAYS SHARED ON PURPOSE** — *"We couldn't read
#: that change. Nothing was saved."* A body that is not a list, an entry that is
#: neither an id nor an object, and a stop that names no premises are one thing
#: to the person who sent them: the request could not be read. B17 §7 W5-T5 says
#: so in as many words, and `tests/test_cr029_rcw5_message_keys.py` holds it so
#: the four keys below do not grow into seven.
_SHAPE_REFUSAL_KEY = "metering.payload_not_object"

#: The four refusals that are about the ORDER rather than the payload, each with
#: the sentence RC-W3c minted in all eleven catalogues (W5-T5 pointed the call
#: sites here). None of them interpolates anything — the sentence carries the
#: whole meaning — so `_refuse` needs no `params` change to serve them.
#:
#:   duplicate premises  "A premises appears twice in the walking order. Each
#:                        stop appears once."
#:   duplicate position  "Two stops claim the same position. Give each stop its
#:                        own number."
#:   not a member        "Some of those stops are not on this route. Only its
#:                        own premises can be ordered."
#:   incomplete          "The walking order leaves out some of this route's
#:                        premises. Every stop has to be in it."
_KEY_DUPLICATE_PREMISES = "metering.route.walk_order_duplicate_premises"
_KEY_DUPLICATE_POSITION = "metering.route.walk_order_duplicate_position"
_KEY_NOT_A_MEMBER = "metering.route.walk_order_not_a_member"
_KEY_INCOMPLETE = "metering.route.walk_order_incomplete"


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _route_row(route_id: Any) -> models.Route:
    """This tenant's route, or ABSENT.

    HR-1 / CLAUDE.md rule 1: an unknown id, a malformed id and another tenant's
    id are ONE answer, and the row is resolved through a tenant-scoped read
    before anything is written — a foreign key alone would not stop an order
    being written against another tenant's route.
    """
    try:
        return models.Route.objects.get(tenant_id=_tenant_id(), pk=route_id)
    except (models.Route.DoesNotExist, DjangoValidationError, ValueError, TypeError):
        raise errors.NotFoundError(audit_br_ref="BR-MET-073") from None


def _refuse(code: str, detail: str, message_key: str = _SHAPE_REFUSAL_KEY) -> None:
    """One refusal shape, and the KEY is the call site's to choose.

    ⚠ **THE PARAMETER IS NAMED `message_key` AND THAT NAME IS LOAD-BEARING.**
    G18 reads backend keys with `ast`, and one of the four forms it understands
    is a POSITIONAL argument to a helper declared in this file whose parameter
    is named `message_key`. Called it `key` and the gate cannot see the four
    constants below — they stay counted as dead catalogue entries while being
    raised on every refusal, which is the exact false reading W5-T5 exists to
    remove.

    `detail` stays on every one of them: it is the English the server logs and
    the developer reads, and the four ordering keys carry no interpolation, so
    passing it costs nothing and losing it would cost the log line.
    """
    raise errors.ValidationError(
        errors.VAL_FORMAT if code == errors.VAL_FORMAT else code,
        message_key=message_key,
        params={"detail": detail},
        field_errors=[
            {
                "field": "order",
                "code": code,
                "message_key": message_key,
                "params": {"detail": detail},
            }
        ],
    )


def _member_premises(route: models.Route) -> dict[str, list[str]]:
    """The route's CURRENT stops: premises id → its member unit ids.

    BR-MET-033 — membership is the unit-grain selection, and a stop is the
    premises those units stand on. Ordered by premise number so an unsequenced
    route still reads as a list somebody could walk.
    """
    stops: dict[str, list[str]] = {}
    rows = (
        models.RouteMembership.objects.filter(tenant_id=route.tenant_id, route=route)
        .select_related("unit", "unit__premises")
        .order_by("unit__premises__premise_no", "unit__premises_id", "unit__label", "id")
    )
    for row in rows:
        stops.setdefault(str(row.unit.premises_id), []).append(str(row.unit_id))
    return stops


def _requested_stops(order: Any, stops: dict[str, list[str]]) -> list[tuple[str, int]]:
    """The payload, validated against the membership, as (premises_id, position).

    Two forms are accepted, because both are honest ways to say the same thing:
      · `["<premises id>", …]`                      — position IS the index
      · `[{"premises_id": …, "walk_order": N}, …]`  — what SET-06D sends
    """
    if not isinstance(order, (list, tuple)):
        _refuse(errors.VAL_FORMAT, "The walking order must be a list of stops.")

    requested: list[tuple[str, int]] = []
    for index, entry in enumerate(order):
        if isinstance(entry, str):
            requested.append((entry, index + 1))
            continue
        if not isinstance(entry, dict):
            _refuse(errors.VAL_FORMAT, "Each stop is a premises id, or an object naming one.")
        premises_id = entry.get("premises_id")
        if premises_id in (None, ""):
            _refuse(errors.VAL_REQUIRED, "Each stop names the premises it visits.")
        raw = entry.get("walk_order", index + 1)
        try:
            position = int(str(raw))
        except (TypeError, ValueError):
            position = 0
        if position < 1:
            _refuse(errors.VAL_RANGE, "A stop number starts at 1.")
        requested.append((str(premises_id), position))

    ids = [premises_id for premises_id, _ in requested]
    if len(set(ids)) != len(ids):
        _refuse(
            errors.VAL_FORMAT,
            "A premises appears twice in the walking order.",
            _KEY_DUPLICATE_PREMISES,
        )
    positions = [position for _, position in requested]
    if len(set(positions)) != len(positions):
        # The sheet's own constraint, refused before the database has to.
        _refuse(
            errors.VAL_FORMAT,
            "Two stops claim the same position.",
            _KEY_DUPLICATE_POSITION,
        )

    unknown = sorted(set(ids) - set(stops))
    if unknown:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            f"{len(unknown)} of the stops are not on this route.",
            _KEY_NOT_A_MEMBER,
        )
    missing = sorted(set(stops) - set(ids))
    if missing:
        _refuse(
            errors.VAL_REQUIRED,
            f"The walking order leaves out {len(missing)} of this route's premises.",
            _KEY_INCOMPLETE,
        )
    return sorted(requested, key=lambda pair: pair[1])


def _stop_dicts(route: models.Route, sequence: list[tuple[str, int]]) -> list[dict[str, Any]]:
    """The served stop rows — the ruled grain, with the facts SET-06D prints."""
    premises_ids = [premises_id for premises_id, _ in sequence]
    numbers = dict(
        models.Premises.objects.filter(tenant_id=route.tenant_id, id__in=premises_ids).values_list(
            "id", "premise_no"
        )
    )
    stops = _member_premises(route)
    return [
        {
            "premises_id": premises_id,
            "premise_no": numbers.get(UUID(premises_id)) if _is_uuid(premises_id) else None,
            "walk_order": position,
            "units": len(stops.get(premises_id, [])),
        }
        for premises_id, position in sequence
    ]


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def premises_order_for_route(route_id: Any) -> list[dict[str, Any]]:
    """SET-06D's Premises tab, in the order a crew walks it.

    CURRENT members only, sequenced first and unsequenced after — a stop that
    left the route is not printed on the sheet, and a member added since the
    last save is not silently dropped from it either.
    """
    route = _route_row(route_id)
    stops = _member_premises(route)
    stored = {
        str(row.premises_id): row.walk_order
        for row in models.RoutePremisesOrder.objects.filter(
            tenant_id=route.tenant_id, route=route
        ).order_by("walk_order", "id")
    }
    sequenced = sorted(
        ((premises_id, stored[premises_id]) for premises_id in stops if premises_id in stored),
        key=lambda pair: pair[1],
    )
    unsequenced = [premises_id for premises_id in stops if premises_id not in stored]
    sequence = [
        (premises_id, index + 1)
        for index, (premises_id, _) in enumerate(
            [*sequenced, *[(premises_id, 0) for premises_id in unsequenced]]
        )
    ]
    return _stop_dicts(route, sequence)


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def save_premises_order(actor: Any, *, route_id: Any, order: Any) -> dict[str, Any]:
    """Write the route's walking order. Idempotent, audited, per premises.

    Returns the stored order plus `resequenced` (how many stops it holds — the
    count SET-06D's change log renders as *"Walking order changed · 4 members
    resequenced"*) and `changed`, which is False when the route already walked
    in exactly this order and nothing was written.

    ⚠ A NO-OP WRITES NO AUDIT ROW. Rule 7 records what happened; a row that
    says the order changed when it did not is a trail that lies, and the
    idempotency posture (rule 6) is that a retry finds the answer rather than
    manufacturing a second event.
    """
    route = _route_row(route_id)
    stops = _member_premises(route)
    sequence = _requested_stops(order, stops)

    with transaction.atomic():
        before = {
            str(row.premises_id): row.walk_order
            for row in models.RoutePremisesOrder.objects.filter(
                tenant_id=route.tenant_id, route=route
            )
        }
        wanted = {premises_id: position for premises_id, position in sequence}
        changed = before != wanted
        if changed:
            # REPLACE, never patch: the position constraint is not deferrable
            # and a swap would collide half-way through (see the module note).
            models.RoutePremisesOrder.objects.filter(
                tenant_id=route.tenant_id, route=route
            ).delete()
            models.RoutePremisesOrder.objects.bulk_create(
                [
                    models.RoutePremisesOrder(
                        tenant_id=route.tenant_id,
                        route=route,
                        premises_id=premises_id,
                        walk_order=position,
                    )
                    for premises_id, position in sequence
                ]
            )
            _project_onto_membership(route, sequence, stops)

        served = {
            "route_id": str(route.id),
            "order": _stop_dicts(route, sequence),
            "resequenced": len(sequence),
            "changed": changed,
        }
        if changed:
            # CLAUDE.md rule 7 / BR-MET-048 — who resequenced it, when, and
            # from what. `before` is the positions that were stored, so an
            # auditor can see the walk that was replaced and not merely that
            # one was.
            core_audit.write_row(
                action="route.premises_order_changed",
                entity_type="route",
                entity_id=route.id,
                actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
                before={"order": before} if before else None,
                after=served,
            )
    return served


def _project_onto_membership(
    route: models.Route, sequence: list[tuple[str, int]], stops: dict[str, list[str]]
) -> None:
    """Keep the SUPERSEDED per-unit column in step with the ruled order.

    See the module docstring: `selectors.route_members` orders by this column
    and SET-06D folds those rows into stops, so a save that left it alone would
    read back in the old order. The units of stop 1 take 1…n, stop 2 continues
    from there — unique within the route (`uq_route_memberships_walk_order`)
    and never rendered as a number anywhere.

    Cleared FIRST, in the same transaction, because the uniqueness constraint
    is not deferrable and the new numbers overlap the old ones.
    """
    memberships = models.RouteMembership.objects.filter(tenant_id=route.tenant_id, route=route)
    memberships.update(walk_order=None)
    position = 0
    for premises_id, _ in sequence:
        for unit_id in stops.get(premises_id, []):
            position += 1
            memberships.filter(unit_id=unit_id).update(walk_order=position)


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 §3/§6 (D3 + D11) + the CR-029 record in 12-governance/11-change-requests.md
# screens: SET-06D
# generated: 2026-08-23 by the CR-029 RC-W3b lane
# checklist: A✔ B=deferred(SET-06D shipped in RC-W3-T3; this lane serves the path it already calls) C✔(tests/test_cr029_rcw3b_walk_order.py — RED first: `ImportError: cannot import name 'walk_order' from 'apps.metering'`) D✔ E✔ F✔ G✔ H=deferred(not a 🔒 path — no money, no rate, no RLS policy, no idempotency KEY: the uniqueness is the schema's, landed in W1-T4)
# gates: ruff✔ black✔
# exceptions: (1) every refusal REUSES `metering.payload_not_object` because G32 is a zero-baseline ratchet and the eleven catalogues are frontend files this lane may not edit — the machine-readable half is in `field_errors[].code`; REPORTED so a catalogue-owning lane can write the four sentences · (2) the SUPERSEDED `route_memberships.walk_order` is written as a PROJECTION of the ruled per-premises order, because `selectors.route_members` orders by it and SET-06D reads that order back — a lane judgment, REPORTED · (3) a stop whose premises later leaves the route is not cascaded away (no ruling exists); the read filters to current members instead · (4) this module holds its own ORM against metering's own tables rather than routing through `services.py` — the `read_windows.py` posture, so two lanes never edit one file (hard-won law 11)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
