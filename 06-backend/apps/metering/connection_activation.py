# ── Trace ──────────────────────────────────────────────
# Change:   CR-162-BRC10 items 3, 5, 6, 36, 38 — Approve / Activate a New
#           Connection per unit and service.
# Ruling:   decision log 2026-10-02, "NEW CONNECTION — THE PO'S SCREEN-BY-SCREEN
#           REVIEW BECOMES ONE PROGRAMME" (commit 56eb54ba9) — Q2 and
#           "Approval / activation (Table 2 items 3–6, 16–17)".
# Rules:    BR-MET-104 (service transitions) · BR-MET-108 (the gate) ·
#           BR-MET-110 (a human accepts) · BR-MET-115 (the messages) ·
#           BR-CUS-1114 / BR-MET-116 (the owner's master account) ·
#           CLAUDE.md hard rules 1 (tenant scoping), 4, 7 (audit) ·
#           hard-won law 14 (no swallowed database error on this path)
# Blueprint: 04-docs/05-modules/03-customers/blueprint/07-new-connect-wizard.md
#           L725-743 ("Partly activated is a state, not a warning") and
#           L891-895 ("Activate units — and the gate that stops it").
# Tests:    06-backend/tests/test_cr162_activation.py
# ───────────────────────────────────────────────────────
"""**Approve a New Connection — one, several or every unit and service that is
ready — and what that switches on.**

HUMAN-OWNED (listed in `10-scripts/gates/human_owned.txt`).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md` (`CR-162-BRC10`).

PO 2026-10-02, verbatim, the ruling this module builds:

    *"activate one, several or all services/units whose work orders are
    complete; open orders listed in a warning and stay pending (Partly
    activated); on activation service point → Activated, asset → Installed
    (date, asset id), unit → active when all its services are, premises +
    master account + customer → Active on the first activation, request →
    Partly activated / Activated, messages sent."*

    **Q2** — *"a gate inspection that has not passed blocks activation of its
    unit; every other open work order only warns."*

The blueprint says the same in its own words (p. L725-743): *"'Partly
activated' is a state, not a warning … A build completes one unit at a time"*,
and (L891-895) *"Activate units is the one that ends the build, and it is
terminal per service — there is no transition back out of activated."*

────────────────────────────────────────────────────────────────────────────
WHAT "READY" MEANS — three judgments where the ruling stops (law 13; decision
log 2026-10-02, CR-162-BRC10 row, judgments (b)–(d))
────────────────────────────────────────────────────────────────────────────
A row is ONE service at ONE unit (`connection_services`). An order applies to
it when it is raised for that unit (or for the whole build) and for that
service (or for no particular service).

  (b) **A row is READY when every order raised for ITS UNIT is complete.** An
      order on the WHOLE BUILD (no unit) does not hold any one unit back — it
      is listed in the warning like every other open order and, per Q2, only
      warns. Otherwise one open site survey would make *"Activate what is
      ready"* activate nothing on every build, and the PO's own worked case —
      Unit 1's orders complete, Unit 2's open → Unit 1 activates — could never
      happen on a build that also carries a whole-build order.
  (c) **A GATE has passed when its order is complete with no failing
      outcome** (`failed`, `partially_done`, `waiting_on_someone_else`,
      `cancelled`). A gate raised for a unit blocks that unit; a gate raised
      for the whole build blocks every unit of its service (every unit when it
      names none). A row's own `gate_order_id` (`BR-MET-108`) counts too.
      Templates mark a gate with `is_gate`, stamped onto the order at raise;
      a build with no gate order has nothing that blocks.
  (d) **Open to-dos are listed and never block** (`BR-MET-114`: *"none of
      them block"*).

────────────────────────────────────────────────────────────────────────────
ONE TRANSACTION PER PRESS, AND EVERY WRITE THROUGH ITS OWNER'S DOOR
────────────────────────────────────────────────────────────────────────────
  * the service row → `connections.transition_service`, the one write path for
    a service's state (it also re-derives the request's state);
  * its assets → `assets.services.install_build_assets` (stage Installed,
    dated today in the utility's timezone) — `DEF-AST-5443`'s missing half;
  * the premises → `active`, metering's own row, audited here;
  * the owner's master account → `customers.services.
    activate_pending_master_account` (its customer has no stored status: it
    reads its accounts, so it is Active when its master account is);
  * the messages → `connection_messages.fire_on_approval`.

Idempotent: a row already activated is reported `already_activated` and
nothing about it is written again; a premises or master account already active
is left alone.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.metering import connection_messages
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import seams
from core import errors

#: An order outcome that means the job did NOT pass, so a gate with it holds.
NOT_PASSED_OUTCOMES = frozenset(
    {
        work_tables.OUTCOME_FAILED,
        work_tables.OUTCOME_PARTIALLY_DONE,
        work_tables.OUTCOME_WAITING,
        work_tables.OUTCOME_CANCELLED,
    }
)

UNIT_PENDING = "pending"
UNIT_PARTLY = "partly_activated"
UNIT_ACTIVATED = "activated"


def _order_open(order: Any) -> bool:
    return order.state not in (work_tables.WO_COMPLETED, work_tables.WO_CANCELLED)


def _gate_passed(order: Any) -> bool:
    return order.state == work_tables.WO_COMPLETED and (order.outcome or "") not in NOT_PASSED_OUTCOMES


def _order_row(order: Any) -> dict[str, Any]:
    return {
        "id": str(order.id),
        "order_no": order.order_no,
        "type": order.type,
        "state": order.state,
        "outcome": order.outcome,
        "is_gate": bool(order.is_gate),
        "unit_label": order.unit.label if order.unit_id else None,
        "service": order.service.code if order.service_id else None,
    }


def _applies(order: Any, row: Any) -> bool:
    """Does this order bear on this unit × service row? See the docstring."""
    if order.unit_id is not None and order.unit_id != row.unit_id:
        return False
    return order.service_id is None or order.service_id == row.service_id


def activation_readiness(connection_id: Any) -> dict[str, Any]:
    """`GET /connections/{id}/activation` — every unit × service row of the
    build with what stands on it, its orders, whether it is ready, and what
    the warning will list. The Units tab and the Approve dialog both read it,
    so the table and the button cannot disagree."""
    connection = w6._connection_or_404(connection_id)
    return _readiness(connection)


def _readiness(connection: Any) -> dict[str, Any]:
    tenant_id = connection.tenant_id
    rows = list(
        work_tables.ConnectionService.objects.filter(tenant_id=tenant_id, connection_id=connection.id)
        .exclude(state=work_tables.SVC_CANCELLED)
        .select_related("unit", "service")
        .order_by("unit__label", "service__code", "id")
    )
    orders = list(
        work_tables.WorkOrder.objects.filter(tenant_id=tenant_id, connection_id=connection.id)
        .exclude(state=work_tables.WO_CANCELLED)
        .select_related("unit", "service")
        .order_by("order_no", "id")
    )
    by_id = {order.id: order for order in orders}
    points = {
        (str(unit_id), str(service_id)): str(point_id)
        for point_id, unit_id, service_id in metering_models.ServicePoint.objects.filter(
            tenant_id=tenant_id,
            unit_id__in=[row.unit_id for row in rows if row.unit_id],
            deleted_at__isnull=True,
        ).values_list("id", "unit_id", "service_id")
    }
    assets = seams.build_asset_rows(list(points.values()))

    out_rows: list[dict[str, Any]] = []
    for row in rows:
        point_id = points.get((str(row.unit_id), str(row.service_id)))
        mine = [order for order in orders if _applies(order, row)]
        own_open = [o for o in mine if o.unit_id is not None and _order_open(o)]
        gates = [o for o in mine if o.is_gate]
        if row.gate_order_id and row.gate_order_id in by_id:
            gates.append(by_id[row.gate_order_id])
        holding_gate = next((g for g in gates if not _gate_passed(g)), None)
        activated = row.state == work_tables.SVC_ACTIVATED
        standing = assets.get(point_id or "", [])
        out_rows.append(
            {
                "id": str(row.id),
                "unit_id": str(row.unit_id) if row.unit_id else None,
                "unit_label": row.unit.label if row.unit_id else None,
                "unit_type": row.unit.unit_type if row.unit_id else None,
                "service": row.service.code,
                "state": row.state,
                "activated_at": row.activated_at.isoformat() if row.activated_at else None,
                "assets": standing,
                "qty": len(standing),
                "work_orders": [_order_row(o) for o in mine],
                "open_orders": [o.order_no for o in own_open],
                "blocked_by_gate": holding_gate.order_no if holding_gate is not None else None,
                "ready": (not activated) and not own_open and holding_gate is None,
            }
        )

    units: dict[str, list[str]] = {}
    for one in out_rows:
        units.setdefault(one["unit_id"] or "", []).append(one["state"])
    unit_states = {
        unit_id: (
            UNIT_ACTIVATED
            if states and all(s == work_tables.SVC_ACTIVATED for s in states)
            else UNIT_PARTLY
            if any(s == work_tables.SVC_ACTIVATED for s in states)
            else UNIT_PENDING
        )
        for unit_id, states in units.items()
    }
    for one in out_rows:
        one["unit_state"] = unit_states.get(one["unit_id"] or "", UNIT_PENDING)

    open_orders = [_order_row(o) for o in orders if _order_open(o)]
    todos = [
        {"id": str(t.id), "title": t.title}
        for t in work_tables.ConnectionTodo.objects.filter(
            tenant_id=tenant_id, connection_id=connection.id, closed_at__isnull=True
        )
        .exclude(kind=work_tables.ConnectionTodo.KIND_NOTE)
        .order_by("created_at", "id")
    ]
    return {
        "connection_id": str(connection.id),
        "connection_no": connection.connection_no,
        "state": connection.state,
        # The accounts a clerk would have to close if this build were
        # cancelled (PO 2026-10-02: *"show a warning listing the account(s) to
        # close. Do not auto-close."*) — read here so the Cancel dialog can
        # list them BEFORE the press.
        "accounts_on_units": accounts_on_build_units(connection.id),
        "can_activate": _refusal(connection) is None,
        "refusal": _refusal(connection),
        "rows": out_rows,
        "ready_ids": [one["id"] for one in out_rows if one["ready"]],
        "orders_total": len(orders),
        "open_orders": open_orders,
        "open_todos": todos,
    }


def accounts_on_build_units(connection_id: Any) -> list[dict[str, Any]]:
    """The accounts open on this build's units — a move-in before approval
    (ruled B) leaves one. Read through customers' own selector
    (`accounts_for_units`), never its tables. Each row names the account by
    its NUMBER (B14 rule 31); `id` is for the link only."""
    unit_rows = list(
        work_tables.ConnectionService.objects.filter(
            tenant_id=w6._tenant_id(), connection_id=connection_id, unit_id__isnull=False
        )
        .values_list("unit_id", "unit__label")
        .distinct()
    )
    labels = {str(unit_id): label for unit_id, label in unit_rows}
    held = seams.accounts_for_units(list(labels))
    return [
        {
            "id": str(account.get("id")),
            "account_no": account.get("account_no"),
            "customer_name": account.get("customer_name"),
            "unit_label": labels.get(unit_id),
        }
        for unit_id, account in sorted(held.items(), key=lambda pair: labels.get(pair[0]) or "")
    ]


def _refusal(connection: Any) -> str | None:
    """Why NOTHING on this build can activate, as a catalogue key, or `None`."""
    if connection.cancelled_at is not None:
        return "metering.activation.build_cancelled"
    if connection.submitted_at is None:
        return "metering.activation.build_is_a_draft"
    if connection.held_at is not None:
        return "metering.activation.build_on_hold"
    return None


def activate(
    actor: Any,
    connection_id: Any,
    *,
    service_ids: Any,
    acknowledge_open_orders: bool = False,
) -> dict[str, Any]:
    """`POST /connections/{id}/activate` — switch on the chosen rows.

    `service_ids` names the unit × service rows (from `activation_readiness`).
    Refused, before anything is written, with a sentence a clerk can act on:

      * the build is a draft, cancelled or on hold (`metering.activation.*`);
      * a chosen row is held by a gate that has not passed (Q2 — 409, naming the
        unit and the order);
      * a chosen row's own unit still has an open order (409, naming them) —
        the screen offers only ready rows, so this is the server's own check;
      * the build has open orders and the caller did not acknowledge the
        warning (409 `metering.activation.open_orders_unacknowledged`, the
        list attached) — the dialog's *Activate what is ready* sends the
        acknowledgement.
    """
    if not isinstance(service_ids, (list, tuple)) or not service_ids:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="metering.activation.nothing_chosen",
            field_errors=[
                {"field": "service_ids", "message_key": "metering.activation.nothing_chosen"}
            ],
        )
    chosen = [str(one) for one in service_ids]
    with transaction.atomic():
        connection = (
            work_tables.Connection.objects.select_for_update()
            .filter(tenant_id=w6._tenant_id(), pk=connection_id)
            .first()
        )
        if connection is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        refusal = _refusal(connection)
        if refusal is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-104",
                message_key=refusal,
                params={"connection_no": connection.connection_no or ""},
            )
        read = _readiness(connection)
        by_id = {row["id"]: row for row in read["rows"]}
        unknown = [one for one in chosen if one not in by_id]
        if unknown:
            raise errors.deny_as_not_found("BR-TEN-003")
        for one in chosen:
            row = by_id[one]
            if row["state"] == work_tables.SVC_ACTIVATED:
                continue
            if row["blocked_by_gate"] is not None:
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-MET-108",
                    message_key="metering.activation.gate_not_passed",
                    params={"unit": row["unit_label"] or "", "order_no": row["blocked_by_gate"]},
                )
            if row["open_orders"]:
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-MET-110",
                    message_key="metering.activation.unit_orders_open",
                    params={"unit": row["unit_label"] or "", "orders": row["open_orders"]},
                )
        if read["open_orders"] and not acknowledge_open_orders:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-110",
                message_key="metering.activation.open_orders_unacknowledged",
                params={
                    "open": len(read["open_orders"]),
                    "total": read["orders_total"],
                    "orders": [o["order_no"] for o in read["open_orders"]],
                },
            )

        first = not any(row["state"] == work_tables.SVC_ACTIVATED for row in read["rows"])
        today = seams.tenant_today()
        switched: list[dict[str, Any]] = []
        already: list[str] = []
        installed: list[dict[str, Any]] = []
        for one in chosen:
            row = by_id[one]
            if row["state"] == work_tables.SVC_ACTIVATED:
                already.append(one)
                continue
            w6.transition_service(
                actor, one, work_tables.SVC_ACTIVATED, reason="activated_on_approval"
            )
            point_ids = _service_point_ids(row)
            fitted = seams.install_build_assets(
                actor, service_point_ids=point_ids, install_date=today
            )
            if fitted is None:
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="CR-162-BRC10",
                    message_key="metering.activation.assets_unwired",
                    params={},
                )
            installed.extend(fitted)
            switched.append(
                {"id": one, "unit_label": row["unit_label"], "service": row["service"]}
            )

        premises = None
        master = None
        if switched:
            premises = _activate_premises(actor, connection)
            if connection.owner_account_id:
                master = seams.activate_pending_master_account(
                    actor, connection.owner_account_id
                )
        connection.refresh_from_db()
        messages = (
            connection_messages.fire_on_approval(
                actor, connection, first=first, activated=switched
            )
            if switched
            else None
        )
        w6._audit(
            actor,
            "connection.activated",
            "connection",
            connection.id,
            after={
                "activated": [row["id"] for row in switched],
                "already_activated": already,
                "assets_installed": [a["asset_no"] for a in installed],
                "acknowledged_open_orders": [o["order_no"] for o in read["open_orders"]]
                if acknowledge_open_orders
                else [],
                "connection_state": connection.state,
                "br_ref": "CR-162-BRC10",
            },
        )
    return {
        "id": str(connection.id),
        "connection_no": connection.connection_no,
        "connection_state": connection.state,
        "activated": switched,
        "already_activated": already,
        "assets_installed": installed,
        "premises": premises,
        "master_account": master,
        "messages": messages,
    }


def _service_point_ids(row: dict[str, Any]) -> list[str]:
    if not row.get("unit_id"):
        return []
    return [
        str(pk)
        for pk in metering_models.ServicePoint.objects.filter(
            tenant_id=w6._tenant_id(),
            unit_id=row["unit_id"],
            service__code=row["service"],
            deleted_at__isnull=True,
        ).values_list("id", flat=True)
    ]


def _activate_premises(actor: Any, connection: Any) -> dict[str, Any] | None:
    """The premises a New Connection created PENDING becomes ACTIVE on the
    build's first activation (PO 2026-10-02: *"it will be activated at the time
    of approval of new conenct request"*). Metering's own row, audited. A
    premises in any other status — an address already in service, or one a
    clerk deactivated — is left exactly as it is."""
    if connection.premises_id is None:
        return None
    premises = (
        metering_models.Premises.objects.select_for_update()
        .filter(tenant_id=connection.tenant_id, pk=connection.premises_id)
        .first()
    )
    if premises is None:
        return None
    if premises.status != "pending":
        return {"id": str(premises.id), "status": premises.status, "changed": False}
    premises.status = "active"
    premises.save(update_fields=["status", "updated_at"])
    w6._audit(
        actor,
        "premises.activated",
        "premises",
        premises.id,
        before={"status": "pending"},
        after={"status": "active", "connection_no": connection.connection_no, "br_ref": "CR-162-BRC10"},
    )
    return {"id": str(premises.id), "status": "active", "changed": True}
