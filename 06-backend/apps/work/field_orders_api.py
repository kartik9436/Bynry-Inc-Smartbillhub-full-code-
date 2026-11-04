# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13, lane S-ORDER — the routes for T-36, T-37,
#           T-38, T-39, T-42 and the FF-58 hand-back (`07-endpoints.md` N8,
#           N15, N16, N17, N19, N20, N21) plus the office surfaces they feed
#           (Walkthrough §4: acceptance queue, field-raised queue).
# Rules:    `07-endpoints.md` §0 — rule 1 ADDITIVE ONLY (every route here is
#           new; no existing route, field or kind changes) · rule 3 (the tenant
#           comes from the path and the session, never the body) · rule 7
#           (idempotent on a key minted at capture) · rule 9 (paged, no cap) ·
#           rule 10 (a technician sees only their own: 404, never 403) ·
#           rule 11 (money is read, never written) · hard rule 1
# Tests:    06-backend/tests/test_cr187_order_*.py
# Impacts:  apps/work/api.py (`urlpatterns += field_api.urlpatterns`, one line)
# ───────────────────────────────────────────────────────
"""The field app's order acts, as routes — in their own file, on purpose.

`apps/work/api.py` is 2,600 lines that several lanes edit in the same week.
These views live here and are appended to its `urlpatterns` by ONE line, so a
merge touches one line of the shared file rather than two hundred (hard-won
law 11: a commit is a statement about files).

Every route here is NEW. The old web field app keeps calling exactly what it
called (`07-endpoints.md` §0 rule 1).

Mobile routes use `FieldAppRole` (office roles and the field technician,
`DEF-WRK-9593`) and scope to the technician's own job inside the service —
never a technician id from the request. Office routes use the classes the
office's own work routes use.
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.work import field_dispatch, field_labour, field_outcomes, field_raise, field_reopen, mobile
from apps.work.api import _actor, _envelope, _payload
from core.pagination import parse_list_params
from core.permissions import AnyTenantRole, FieldAppRole, WorkOrdersReadAnyWriteAdminOrClerk
from core.tenancy import require_tenant


def _door(request: Any) -> tuple[Any, dict[str, Any]]:
    """`(actor, body)` for an own-door act from the handset's outbox
    (`CR-187-BRC10`, lane S-GAPS): the act is the CAPTOR's when the body
    carries a `capture_token`, the session's otherwise (`mobile.door_actor`);
    the token never reaches the service."""
    payload = _payload(request)
    return mobile.door_actor(_actor(request), payload), mobile.without_capture_token(payload)


# ── mobile: the job ───────────────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_reopen(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/reopen` — `{reason, note?, key?}` (FF-36,
    R22). `reason`: `wrong_outcome · missed_step · missing_evidence`."""
    require_tenant(request)
    return Response(field_reopen.technician_reopen(_actor(request), order_id, _payload(request)))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_hand_back(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/hand-back` — `{reason, note?, key?,
    capture_token?}` (FF-58, R106, R107). Back to Queued, unassigned; an
    emergency is refused. A replayed `key` answers `duplicate: true`."""
    require_tenant(request)
    actor, body = _door(request)
    return Response(field_dispatch.hand_back(actor, order_id, body))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_claim(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/claim` — no body (FF-12, R27). Online
    only. Skill advice in the answer; never a refusal for a skill."""
    require_tenant(request)
    return Response(field_dispatch.claim(_actor(request), order_id))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_crew(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/crew` — `{technician_id, key?,
    capture_token?}` (FF-29, R8). The lead adds a second technician; 201 when
    added, 200 when the same person or key was already there. `{act: "leave",
    technician_id, ended_at?}` stops a helper's clock (FF-29's ×), 200."""
    require_tenant(request)
    actor, body = _door(request)
    answer = field_labour.crew_door(actor, order_id, body)
    return Response(answer, status=201 if answer.get("created") else 200)


@api_view(["GET", "PUT"])
@permission_classes([FieldAppRole])
def mobile_labour(request: Any, order_id: Any) -> Response:
    """`GET /work/mobile/jobs/{id}/labour` — everybody's time and the cost ·
    `PUT` — `{depart_at?, arrive_at?, start_at?, end_at?, technician_id?,
    capture_token?}`, the caller's OWN clocks (R9), or the lead correcting a
    helper's (FF-29 *Correct their time*)."""
    require_tenant(request)
    if request.method == "PUT":
        actor, body = _door(request)
        return Response(field_labour.record_time(actor, order_id, body))
    return Response(field_labour.labour_of(_actor(request), order_id))


# ── mobile: raising work ──────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_templates(request: Any) -> Response:
    """`GET /work/mobile/templates?q=&page=&page_size=` — every published
    template, the caller's recently used first (FF-62, R112, N8)."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = field_raise.templates_catalogue(
        _actor(request), q=params.q, page=params.page, per=params.per
    )
    return Response(_envelope(request, result))


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_template(request: Any, template_id: Any) -> Response:
    """`GET /work/mobile/templates/{id}` — one published template, whole."""
    require_tenant(request)
    return Response(field_raise.template_body(template_id))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_orders(request: Any) -> Response:
    """`POST /work/mobile/orders` — a field-raised order (FF-37, N16). 201
    with the number the server allocated; a replayed `key` answers 200 with
    the same order and `duplicate: true`. A `capture_token` raises it as its
    captor (`mobile.door_actor`)."""
    require_tenant(request)
    actor, body = _door(request)
    answer = field_raise.raise_from_field(actor, body)
    return Response(answer, status=200 if answer.get("duplicate") else 201)


# ── office: the queues and the decisions ──────────────────────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def acceptance_queue(request: Any) -> Response:
    """`GET /work/acceptance-queue?outcome=&accepted=&page=&page_size=` —
    finished jobs with their outcome, reason, blocker, remaining steps and
    cost (T-36). `tally` counts every outcome over the whole queue."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = field_outcomes.office_queue(
        outcome=request.query_params.get("outcome"),
        accepted=request.query_params.get("accepted"),
        page=params.page,
        per=params.per,
    )
    return Response({**_envelope(request, result), "tally": result["tally"]})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_outcome(request: Any, order_id: Any) -> Response:
    """`GET /work-orders/{id}/outcome` — one job's outcome and its cost."""
    require_tenant(request)
    return Response(field_outcomes.order_outcome(order_id))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_come_back(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/come-back` — `{decision: reopen | follow_on,
    reason, note?, template_id?, key?}` (T-37, E2E-17/18)."""
    require_tenant(request)
    return Response(field_reopen.office_decide(_actor(request), order_id, _payload(request)))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_come_backs(request: Any, order_id: Any) -> Response:
    """`GET /work-orders/{id}/come-backs` — the reopen / follow-on history."""
    require_tenant(request)
    return Response(field_reopen.history(order_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def field_raised(request: Any) -> Response:
    """`GET /work/field-raised?status=pending|accepted|refused|all` — the
    office's queue of orders raised on site (E2E-16)."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = field_raise.field_raised_queue(
        status=request.query_params.get("status"), page=params.page, per=params.per
    )
    return Response({**_envelope(request, result), "counts": result["counts"]})


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_field_raise(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/field-raise` — `{decision: accept | refuse,
    reason?}`: the office's acceptance of a field-raised order (R23)."""
    require_tenant(request)
    return Response(field_raise.decide(_actor(request), order_id, _payload(request)))


urlpatterns = [
    path("work/mobile/jobs/<uuid:order_id>/reopen", mobile_reopen, name="mobile_reopen"),
    path("work/mobile/jobs/<uuid:order_id>/hand-back", mobile_hand_back, name="mobile_hand_back"),
    path("work/mobile/jobs/<uuid:order_id>/claim", mobile_claim, name="mobile_claim"),
    path("work/mobile/jobs/<uuid:order_id>/crew", mobile_crew, name="mobile_crew"),
    path("work/mobile/jobs/<uuid:order_id>/labour", mobile_labour, name="mobile_labour"),
    path("work/mobile/templates", mobile_templates, name="mobile_templates"),
    path("work/mobile/templates/<uuid:template_id>", mobile_template, name="mobile_template"),
    path("work/mobile/orders", mobile_orders, name="mobile_orders"),
    path("work/acceptance-queue", acceptance_queue, name="work_acceptance_queue"),
    path("work/field-raised", field_raised, name="work_field_raised"),
    path("work-orders/<uuid:order_id>/outcome", work_order_outcome, name="work_order_outcome"),
    path(
        "work-orders/<uuid:order_id>/come-back", work_order_come_back, name="work_order_come_back"
    ),
    path(
        "work-orders/<uuid:order_id>/come-backs",
        work_order_come_backs,
        name="work_order_come_backs",
    ),
    path(
        "work-orders/<uuid:order_id>/field-raise",
        work_order_field_raise,
        name="work_order_field_raise",
    ),
]
