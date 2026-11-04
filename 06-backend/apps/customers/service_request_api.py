# ── Trace ──────────────────────────────────────────────
# Change:   CR-031 (PO 2026-08-24) · B19 = 04-docs/02-decisions/19-cr031-
#           service-request-capture.md   Screens: REQ-01 list · REQ-02 detail ·
#           REQ-03.1..6 capture · REQ-03.sent confirmation
# Rules:    BR-CUS-079 · BR-CUS-080 · BR-CUS-070 · B18 §4.6 ·
#           BR-CUS-090 (quoted · collected · outstanding) · BR-CUS-091 (a
#           customer MAY request a disconnect; staff may raise one) ·
#           BR-CUS-093 (numbered AT CREATION) · BR-CUS-094 (seven categories,
#           `government` legacy) · BR-CUS-095 (the tenant's document checklist,
#           shipping unticked) · BR-SHL-025 / BR-IDN-009 (server-enforced RBAC)
#           · CLAUDE.md rules 1 · 2 · 6 · 7
# Questions: OQ-355 · OQ-356 (OPEN — served as stated absences) · OQ-357 ✅ CLOSED
#           2026-09-23 as "both" (remove while a draft, waive after)
# Tests:    06-backend/tests/test_cr031_service_request_api.py
# Impacts:  config/urls.py (the include) · 06-backend/openapi/schema.json (the
#           committed contract snapshot — BE-11 TC05 diffs it) · the W4
#           frontend, which had NOTHING to call before this file
# ───────────────────────────────────────────────────────
"""`/service-requests` — the HTTP surface for the object the product did not have.

THIN by law (B8/LAW 0): every write goes through `service_request_service` (the
sole writer), every read through `service_request_reads`, **no ORM here and no
arithmetic here**, and every refusal is a catalog exception the BE-02 handler
renders (G9).

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS — HARD-WON LAW 2, FOR THE SIXTH TIME IN THIS PRODUCT
════════════════════════════════════════════════════════════════════════════
`service_request.py` + `service_request_service.py` + `service_request_reads.py`
landed on 2026-08-24 as ~2,700 lines over five tables and eleven states, with
RLS, audit, idempotent numbering and a full read model for three screens — and
**not one route named any of it.** Its own lane report said so: *"no endpoints
exist yet — `config/urls.py` and `openapi/schema.json` were outside the lane's
scope"*. So a clerk could not raise a service request, and the whole W4 frontend
had nothing to call.

That is the same defect `config/urls.py` already records five times over
(billing corrections, payments, ledger, notifications, ledger cost capture), and
G13/G25 exist because of it. **Built is not wired.**

════════════════════════════════════════════════════════════════════════════
ROLE POSTURE
════════════════════════════════════════════════════════════════════════════
A4 gives Executive VIEW on the Premises/Accounts family, so **reads are open to
any tenant role and every write is `AdminOrClerk`** — the identical posture
`apps/customers/api.py` takes, and the service layer re-checks with its own
`@require_role` (defence in depth, BR-SHL-025).

**ONE surface is System Admin only: the BR-CUS-095 checklist.** It is a tenant
SETTING — ticking `proof_of_identity` for `move_in` changes what every future
approval demands — so it sits where the lookups and policy screens sit, not
where the capture form does.

════════════════════════════════════════════════════════════════════════════
WHAT THIS SURFACE WILL NOT DO, EACH BY NAME
════════════════════════════════════════════════════════════════════════════
Served on every detail response as `unavailable`, so a caller never has to infer
an absence from a missing key and a reviewer never has to take a docstring's
word for it (the `BUDGET_UNAVAILABLE` discipline, G38's on the server side).

  · **No identifier is accepted.** BR-CUS-092 ruled the SSN and driving licence
    capturable THROUGH an app-layer encryptor that does not exist yet; the
    capture path refuses those field names by name rather than dropping them
    silently, and clause (d) keeps *"stored encrypted"* off the screen until it
    is live.
  · ✅ ~~No fee line is removed~~ — **OQ-357 closed 2026-09-23 as "both"**: a
    draft's line is removed (`DELETE …/fees/{id}`), a submitted request's is
    waived with a reason.
  · **No receipt is allocated and no payment row is written.** `collect_fee`
    records the number the counter wrote on the slip; payments owns the `RCT-`
    series (hard rule 5).
  · **Nothing posts to the ledger** (B18 §4.6). The fees are a quote.
  · **No customer is matched automatically** — the detail's `Matched on: ID
    number and date of birth` names two fields this schema does not carry. A
    clerk links a customer explicitly.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from core import errors
from core.pagination import StandardPagination, parse_list_params
from core.permissions import AdminOrClerk, AnyTenantRole, SystemAdminOnly
from core.tenancy import current_tenant_id, require_tenant, tenant_path

from apps.customers import applicant_messages
from apps.customers import move_in_request
from apps.customers import notifications_seam
from apps.customers import owner_lookup
from apps.customers import payments_seam
from apps.customers import request_extra_messages
from apps.customers import request_jobs
from apps.customers import seams
from apps.customers import service_request as rules
from apps.customers import service_request_documents as doc_files
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as writes
from apps.customers import service_request_steps as steps
from apps.metering import interruption_service
from apps.metering import interruptions as interruption_models

logger = logging.getLogger(__name__)

#: What this surface cannot answer, carried on every detail response.
SERVICE_REQUEST_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    # ⚠ **`detail` IS SCREEN COPY; `br_ref` CARRIES THE PROVENANCE.** G28/CR-016:
    # an internal id on a utility user's screen is noise to them and a leak to
    # us. So the ids, the quotes and the reasoning live in `br_ref` and in these
    # comments, and `detail` says only what a person needs to know. Keep the
    # honesty, drop the provenance.
    # ✅ **`applicant_drivers_licence_not_captured` LEFT THIS LIST ON 2026-09-15,
    # AND IT LEFT BECAUSE THE FACT ARRIVED RATHER THAN BECAUSE ANYBODY TIDIED.**
    # PO ruling of that date finishing BR-CUS-092(a), verbatim: *"ensure user is
    # able to inputs both these on step 1 - Date of birth and driver's licence on
    # step 1"*. The licence is captured, encrypted at rest under
    # `service_requests.drivers_licence`, served as its last four, and clause
    # (d)'s hold on the *"stored encrypted"* sentence is lifted for it.
    #
    # ⚠ **A STATED ABSENCE IS RETIRED IN THE COMMIT THAT MAKES IT FALSE, AND
    # NOT ONE COMMIT LATER.** An entry here is a REFUSAL a clerk reads; a refusal
    # that has stopped being true is the mirror of dead UI and nothing in this
    # repo can see it (CLAUDE.md hard-won law 2, `DEF-CWP-3925`). The test that
    # fired when this hold expired is `test_proof2c` in
    # `tests/test_br_cus_092_ssn_capture.py`, and it now asserts the ABSENCE of
    # this code.
    {
        # The detail's Customer match panel is badged Strong and states
        # "Matched on: ID number and date of birth". This schema carries
        # neither (DEF-632 · DEF-638 12.b), and BR-CUS-089 lets a strong match
        # MOVE MONEY, so a tier derived from weaker evidence is a money bug.
        "code": "no_customer_matcher",
        "br_ref": "DEF-632 · DEF-638 · BR-CUS-089",
        "detail": "Nothing matches an applicant to an existing customer automatically. "
        "Search for them and link them yourself, so the person whose deposit or arrears "
        "may follow them is one somebody has actually identified.",
    },
    # ⛔ **`fee_line_cannot_be_removed` IS RETIRED — 2026-09-23, `DEF-CUS-6418`.**
    # It read *"A fee line cannot be deleted. Waive it instead"*, under OQ-357.
    # OQ-357 closed that day as "both" (the PO approved the step-5 fee table
    # carrying a Waive tick AND a remove icon): a DRAFT's line is removed
    # (`remove_fee_line`), a submitted request's is waived. A stated absence is
    # retired in the commit that makes it false.
    {
        # OQ-355 — the Conditions panel prints "4 of 5 conditions clear" and
        # only four can be named. Serving `total: 4` with the gap stated beats
        # printing a 5 nothing can itemise.
        "code": "fifth_approval_condition_unnamed",
        "br_ref": "OQ-355",
        "detail": "Four approval conditions are checked and listed. The design shows a "
        "fifth and does not say what it is, so it is not counted here rather than being "
        "claimed as checked.",
    },
    {
        # OQ-356 — the decision panel's badges are drawn for ONE evidence state.
        # Every other combination is `possible`, never an inverted sentence.
        "code": "undrawn_verdicts_are_possible_not_ruled",
        "br_ref": "OQ-356",
        "detail": "Where the evidence neither fits an outcome nor rules it out, it is "
        "offered without a recommendation. The choice is yours.",
    },
    # ⛔ **`acknowledgement_cannot_be_queued` IS RETIRED — 2026-09-23,
    # `DEF-CUS-6418` — AND IT HAD BEEN FALSE FOR EIGHT DAYS.** It read *"No
    # acknowledgement has been sent to the applicant and none is waiting to be
    # sent"*, because notifications had no `service_request` source kind.
    # `DEF-CUS-5389` added the kind on 2026-09-15 and `submit` has queued the
    # acknowledgement ever since (`send_acknowledgement`, `ACK_SOURCE_TYPE_UNKNOWN`'s
    # own note says so) — while this static list went on telling every
    # confirmation screen that nothing was waiting. The REAL answer is per
    # request, in `decision.acknowledgement` (`state` · `reason`), and the
    # confirmation reads that now.
)


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id from the session user,
    ROLE SERVER-ATTACHED by the identity layer (BE-04), never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="customers.payload_not_object")
    return data


def _required_text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.fieldRequired",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    return value.strip()


def _money_field(payload: dict[str, Any], name: str) -> Decimal:
    """A money argument as a STRING → Decimal. **A JSON float is REFUSED.**

    CLAUDE.md rule 2. By the time a JSON number reaches this function it is an
    IEEE double: `25.10` arrives as `25.099999999999998` and would be stored to
    four places as exactly that. On a counter-collection endpoint that is a
    customer's cash, so the refusal names the field rather than coercing.
    """
    raw = payload.get(name)
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.serviceRequest.moneyMustBeString",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        )
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.fieldRequired",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.serviceRequest.moneyMustBeString",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _optional_date(payload: dict[str, Any], name: str) -> date | None:
    raw = payload.get(name)
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.serviceRequest.dateFormat",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


# ⚠ **`_paginated` LIVED HERE AND WAS CALLED BY NOTHING — REMOVED 2026-09-18
# (DEF-CUS-5752).** It took a BUILT LIST and handed it to
# `paginate_queryset`, so every row of the match set was constructed before
# fifty were drawn — the `NFR-3` breach `_prepaged` in `api.py` documents at
# length. It had been dead since the file was written: `service_requests`
# below has always paged `reads.list_queryset` in SQL and set `kpis` on the
# envelope afterwards.
#
# It is called out rather than silently deleted because **another module named
# it as the pattern to copy**: `apps/metering/api.py`'s `_connections_envelope`
# says *"`kpis` rides alongside exactly as REQ-01's strip does in
# `service_request_api._paginated`"*. The live example of that is
# `service_requests` itself — `response.data["kpis"] = reads.kpi_strip()` after
# `get_paginated_response` over a QUERYSET — and re-pointing that citation is
# the metering owner's to make.


# ═══════════════════════════════════════════════════════════════════════════
# REQ-01 — the list, and creating a draft
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # read: all three roles; the POST re-checks
def service_requests(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return _create(request)
    segment = str(request.query_params.get("segment") or "open")
    if segment not in rules.SEGMENT_STATES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.segmentUnknown",
            params={"value": segment},
        )
    q = request.query_params.get("q") or None
    # ── `BR-CUS-1046` / `DEF-CUS-5060` — the sort, and the page in SQL ────────
    # ⚠ **THE PAGE IS TAKEN IN THE DATABASE (`NFR-3`).** This handler used to
    # build a row for EVERY matching request and let the paginator slice the
    # list afterwards, which is `O(tenant)` on a worklist that only ever shows
    # fifty. `paginate_queryset` over the queryset is the idiom `GET /invoices`
    # and `GET /payments` already use — *"the page is taken in the DATABASE:
    # only the rows on screen are serialized"* — and it comes for free now that
    # the ordering is an `ORDER BY` instead of a fixed one.
    params = parse_list_params(
        request.query_params,
        allowed_sorts=tuple(reads.SORTS),
        default_sort=reads.DEFAULT_SORT,
        default_dir=reads.DEFAULT_DIR,
    )
    queryset = reads.list_queryset(segment=segment, q=q, sort=params.sort, dir=params.dir)
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    # The utility's own clock, read ONCE for the page rather than once per row
    # (`DEF-CUS-6433` — the AGE column is counted in the tenant's day).
    zone = seams.tenant_timezone()
    # `CR-183-BRC10` — the TYPE of a temporary-stop or restart ask, for the
    # whole page in two queries rather than two per row.
    from apps.customers import temporary_stop

    kinds = temporary_stop.kinds_for([row.id for row in (page or [])])
    response = paginator.get_paginated_response(
        [reads.list_row(row, zone=zone, kinds=kinds) for row in (page or [])]
    )
    response.data["kpis"] = reads.kpi_strip()
    response.data["segment"] = segment
    # BR-SHL-010 — the screen never invents a control: the sort names it may
    # offer are the server's, served beside the rows exactly as `filters` and
    # `states` already are on the sibling worklists.
    response.data["sorts"] = list(reads.SORTS)
    return response


def _create(request: Any) -> Response:
    """`POST /service-requests` — open a draft, **and it comes back numbered**.

    BR-CUS-093 (PO 2026-08-24): *"At creation — every draft is numbered."* The
    201 carries `request_no` because that is the number the clerk is about to
    read down the phone, and `draft_footer` carries the copy consequence (b):
    every capture step used to read *"Step N of 6 · nothing is created until you
    submit"*, which is now FALSE, and becomes ***"Step N of 6 · saved as draft
    SR-26-0048"***.
    """
    if not isinstance(getattr(request, "user", None), object):  # pragma: no cover
        raise errors.AuthError(errors.AUTH_UNAUTHENTICATED)
    _require_write_role(request)
    # ⚠ **STEP 1 COMES FROM THE DOOR** (`service_request_steps`, the
    # `DEF-MET-7690` shape). Everything this door accepts is typed on the
    # applicant step and nowhere else, so wrapping the CALL says *step 1* about
    # exactly the right set — a list of field names to match would be a second
    # copy of the mapping that drifts the day a field is added.
    with steps.on_step(steps.STEP_APPLICANT):
        created = writes.create_request(_actor(request), _payload(request))
    body = reads.detail(created.id)
    response = Response(body, status=201)
    response["Location"] = tenant_path(request, f"/service-requests/{created.id}")
    return response


def _require_write_role(request: Any) -> None:
    """A4 gives Executive VIEW only, so a write from one is refused here as well
    as in the service (defence in depth, BR-SHL-025). `AnyTenantRole` guards the
    method-multiplexed views; this is the second half."""
    if not AdminOrClerk().has_permission(request, None):
        raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-SHL-025")


# ═══════════════════════════════════════════════════════════════════════════
# REQ-02 — the detail
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])
def service_request_item(request: Any, request_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        _require_write_role(request)
        writes.update_request(_actor(request), request_id, _payload(request))
    return Response(_detail(request_id))


def _detail(request_id: Any) -> dict[str, Any]:
    return {**reads.detail(request_id), "unavailable": list(SERVICE_REQUEST_UNAVAILABLE)}


# ═══════════════════════════════════════════════════════════════════════════
# THE LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_submit(request: Any, request_id: str) -> Response:
    """`POST .../submit` — **idempotent, BR-CUS-093 consequence (e)**.

    *"`submit` no longer allocates anything, so a repeated submit is a state
    transition on a row that already has its identity — the idempotency key is
    the request itself."* A second call answers 200 with
    `idempotent_replay: true` and sends the customer nothing twice.
    """
    require_tenant(request)
    result = writes.submit(_actor(request), request_id)
    return Response(
        {
            "request": _row_after_a_committed_submit(result["request"]),
            "acknowledgement": result["acknowledgement"],
            "idempotent_replay": result.get("idempotent_replay", False),
        }
    )


def _row_after_a_committed_submit(row: Any) -> dict[str, Any]:
    """The list row for a request that HAS ALREADY BEEN SUBMITTED, built so that
    describing it can never undo it — **`DEF-CUS-6178`, PO report 2026-09-22.**

    ⚠ **THE COMMIT IS BEHIND US BY THE TIME THIS RUNS.** `writes.submit` moves
    the state, writes the timeline row, writes `audit_log` and queues the
    acknowledgement, and every one of those is committed before the response is
    composed. So a raise HERE — in code whose entire job is to DESCRIBE what
    happened — answers `500` over a state change that stands, and the screen
    tells the clerk *"Nothing was saved"* about an application that was. A
    clerk who believes that re-enters the whole thing.

    **So the describing is allowed to fail and is not allowed to deny.** The
    fallback is the three facts a caller actually needs after a submit: which
    request, what number, what state. Nothing is invented — every one of them is
    read off the row that has just been written.

    ⚠ **IT IS LOGGED WITH ITS TRACEBACK AND NOT SWALLOWED (hard-won law 1).** A
    bare `except` here would turn a real, repeating server fault into silence,
    and the next person to look would find a product that works and a screen
    that is subtly thin. `logger.exception` puts the stack where an operator
    reads it while the clerk gets the truthful answer.

    ⚠ **THIS IS NOT A LICENCE TO WIDEN.** It covers ONE call on ONE endpoint,
    the one that runs after an irreversible act. Everywhere else a broken read
    model should still be a loud 500, because there a 500 costs a retry rather
    than a lie.
    """
    try:
        return reads.list_row(row)
    except Exception:  # noqa: BLE001 — see the docstring: describe, never deny
        logger.exception(
            "service_request.submit: the row could not be described after the "
            "state had already moved; answering with the state itself "
            "(DEF-CUS-6178)",
        )
        return {
            "id": str(getattr(row, "id", "") or ""),
            "request_no": getattr(row, "request_no", None),
            "state": getattr(row, "state", None),
        }


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_transition(request: Any, request_id: str) -> Response:
    """`POST .../transitions` — every lifecycle move except approve and refuse,
    which have their own doors because each carries a guard this one does not
    (the condition gate; the reason code)."""
    require_tenant(request)
    payload = _payload(request)
    action = _required_text(payload, "action")
    # ── CR-070 wave P · routing has its own door now (US-WRK-039) ──────────
    #
    # `route` is still one of this endpoint's actions — no route moves and no
    # screen changes its call — but it goes through `writes.route`, which moves
    # the state and then offers the field work. Every other action is unchanged.
    # ⚠ The jobs are on the RESPONSE and not only in the database: a raise that
    # failed has to reach the screen as a sentence (`BR-WRK-055`), and a result
    # that lived only inside a service call is a result nobody can see again
    # (hard-won law 2, applied to a response).
    if action == "route":
        outcome = writes.route(
            _actor(request), request_id, template_ids=(payload.get("field_visit") or {}).get(
                "template_ids"
            )
        )
        return Response(
            {
                **_detail(request_id),
                "work_orders": outcome["work_orders"],
                "warnings": outcome["warnings"],
            }
        )
    # ⚠ `info_needed` and `message_to_applicant` are read for EVERY action and
    # used by one, which is deliberate: `writes.transition` decides, and a door
    # that filtered the payload by action here would be a second opinion about
    # which action owns which field (`DEF-CUS-5389`).
    moved = writes.transition(
        _actor(request),
        request_id,
        action,
        reason=payload.get("reason"),
        info_needed=payload.get("info_needed"),
        message_to_applicant=payload.get("message_to_applicant"),
    )
    return Response(_with_applicant_message(moved, _detail(request_id)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_approve(request: Any, request_id: str) -> Response:
    """`POST .../approve` — gated by the outcome AND every blocking condition.

    A blocked approval answers a `BIZ-COMPLETENESS` refusal naming the condition,
    **not a move to `Refused`**: *"Nothing is refused — it simply cannot be
    approved yet."* Conflating the two would put a reason on a customer's record
    that nobody gave.

    ⚠ **IT TAKES AN OPTIONAL `outcome` SINCE 2026-09-16 (`DEF-CUS-5427`).** The
    Approve dialog sends the radio the clerk picked, and the outcome and the
    approval then commit or roll back together. `POST .../decision` is untouched
    and is still the Decision tab's own door.

    ⚠ **SINCE `CR-094-BRC01` IT ALSO RAISES THE JOB** — PO 2026-09-15, *"pass all
    information to create the new connect requets or move -in request based on
    selction"*, drawn on p083–p084 as `Approve and raise the build`. The response
    carries `job`, which holds EITHER `raised` (what was created, its reference
    and the queue it is on) OR `not_raised` (why nothing was, by name). Never
    both and never neither, so a screen cannot render a job that does not exist.
    """
    require_tenant(request)
    payload = _payload(request)
    answer = writes.approve_and_raise(
        _actor(request),
        request_id,
        note=payload.get("note"),
        # ⚠ OPTIONAL, AND IT IS THE WHOLE OF `DEF-CUS-5427`'s FIX. When the
        # caller sends it, the outcome is written inside the SAME transaction as
        # the guards, so a refused approval leaves no outcome behind. Absent, the
        # route behaves exactly as it did and the outcome must already be stored.
        outcome=payload.get("outcome"),
        # ⊕ `DEF-CUS-6350` — the clerk's *It's a new address*, answering a near
        # match in Premises. Only a literal `true` counts: a string `"false"` is
        # truthy in Python, and reading it as a yes would clear the one check
        # that stops a duplicate address being built.
        address_is_new=payload.get("address_is_new") is True,
        # ⊕ `CR-161-BRC10` W6 — R5's pick per conflicting answer,
        # `{entity: {key: "existing" | "requested"}}`. Absent keeps every
        # existing value, which is the pre-selection the review draws.
        custom_field_picks=payload.get("custom_field_picks"),
    )
    return Response({**_detail(request_id), "job": answer["job"]})


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def service_request_approval_preview(request: Any, request_id: str) -> Response:
    """`GET .../approval-preview?outcome=…` — `WHAT APPROVING WILL DO`.

    **This is what the Approve modal prints, and the modal computes none of it.**
    Drawn p083–p084 of the Accounts blueprint (read as images, scale 2): five
    `THEN` / `WHAT` rows, of which two change with the chosen radio. The payload
    carries those rows as KEYS, what will be created, the queue it lands on, and
    the outstanding money that travels with it.

    `outcome` is optional and defaults to the request's own committed pick, so
    the same route answers *what did this become* and *what would it become*.
    The whole set also rides on the detail's decision tab
    (`what_approving_will_do`), keyed by outcome, so the modal can redraw the
    table as a radio moves without a round trip.

    ⚠ **A PREVIEW IS NOT A PROMISE THE APPROVAL KEEPS BY ITSELF.** `blockers`
    lists what would stop the job being raised — no resolved premises, no live
    account, a job already linked — and **none of them blocks the approval**:
    the drawn callout is *"the money does not gate approval and the documents
    do"*, and a request whose job cannot be raised is still approved with the
    reason named.
    """
    require_tenant(request)
    row = writes.request_row(request_id)
    return Response(
        request_jobs.approval_preview(row, request.query_params.get("outcome") or None)
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_refuse(request: Any, request_id: str) -> Response:
    """`POST .../refuse` — the register's reason, the utility's code, and the
    one sentence the APPLICANT reads.

    ⚠ **`message_to_applicant` IS THE BLUEPRINT'S `What to tell them`**, whose
    helper line reads *"Goes into the refusal letter."* It is the letter's body.
    `reason` stays internal and `reason_code` is what the refusal is FILED
    under, now one of five (`DEF-CUS-5389`). None of the three is the same
    audience, and the response carries `applicant_message` so the screen can say
    whether the letter was queued rather than assume it.
    """
    require_tenant(request)
    payload = _payload(request)
    refused = writes.refuse_request(
        _actor(request),
        request_id,
        reason=_required_text(payload, "reason"),
        reason_code=payload.get("reason_code"),
        message_to_applicant=payload.get("message_to_applicant"),
    )
    return Response(_with_applicant_message(refused, _detail(request_id)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_resend_ask(request: Any, request_id: str) -> Response:
    """`POST .../resend-ask` — *Resend the ask* (`CR-171-BRC10` P1.06, image 05).

    Takes NO body: the words are the stored ask's, never the caller's, so a
    resend cannot become a different message wearing the old one's history.
    Answers the detail plus `applicant_message` — whether the letter was
    queued, by the same shape `refuse` and `transitions` answer with.
    """
    require_tenant(request)
    resent = writes.resend_the_ask(_actor(request), request_id)
    return Response(_with_applicant_message(resent, _detail(request_id)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_reopen(request: Any, request_id: str) -> Response:
    """`POST .../reopen` — *Reopen* on a declined move-in request (image 08;
    PO 2026-10-05, `OQ-CUS-12789` → (a)). Body `{"reason"}` — REQUIRED
    (`BR-CUS-072`); it lands on the timeline row beside the decline. Answers the detail: `header.state` is
    `submitted` (*To approve*). A request that is not a declined MOVE-IN is
    refused by name (`transitionNotAllowed` / `reopenNotAMoveIn`)."""
    require_tenant(request)
    reason = _payload(request).get("reason") or ""
    move_in_request.reopen(_actor(request), request_id, reason=reason)
    return Response(_detail(request_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def service_request_messages(request: Any, request_id: str) -> Response:
    """`GET .../messages?page=&per=` — the request's *Messages* tab (image 22).

    Every letter queued to the applicant for THIS request, newest first, paged
    in SQL (`NFR-3`). Rows: `template_code` (the message, named by the
    catalogue) · `to_name` · `to_address` · `channel` · `status` ·
    `queued_at` · `sent_at`. `unavailable` is set, and the page empty, only when
    notifications publishes no read — never inferred from an empty table.
    """
    require_tenant(request)
    row = writes.request_row(request_id)
    found = notifications_seam.request_messages(reads.message_source_ids(row))
    paginator = StandardPagination()
    if found is None:
        response = paginator.get_paginated_response(paginator.paginate_queryset([], request) or [])
        response.data["unavailable"] = "notifications_publishes_no_message_read"
        return response
    queryset, serialise = found
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        [reads.message_row(serialise(one)) for one in (page or [])]
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def service_request_audit(request: Any, request_id: str) -> Response:
    """`GET .../audit?page=&per=&f.kind=all|changes|messages` — the request's
    *Audit* tab on the move-in view (image 23: When · Who · What), paged in SQL
    (`NFR-3`). Rows are `history_tab`'s shape; the WHAT is composed by the
    catalogue from `kind` / `to_state` / `note_type`, never sent as prose."""
    require_tenant(request)
    row = writes.request_row(request_id)
    kind = str(request.query_params.get("f.kind") or "all")
    if kind not in move_in_request.AUDIT_KINDS:
        kind = "all"
    paginator = StandardPagination()
    page = paginator.paginate_queryset(reads.timeline_queryset(row, kind=kind), request)
    response = paginator.get_paginated_response(
        [reads.history_row(one, row) for one in (page or [])]
    )
    response.data["kind"] = kind
    return response


@api_view(["GET", "PUT"])
@permission_classes([AnyTenantRole])
def service_request_move_in_form(request: Any, request_id: str) -> Response:
    """`GET|PUT .../move-in-form` — *Edit* on a move-in request opens the
    four-step ADD form filled from it (`CR-171-BRC10` P1.08, J3; PO *"on edit
    of Move in request use same form Add form to edit"*).

    **GET** answers `{request, park_id, step, values}`: the request's own facts
    laid over whatever was parked. **PUT** `{step, values}` is *Save draft &
    exit*: the request's own fields are written back through the request's
    writers, the rest is parked in one `move_in` draft, and NOTHING is
    approved. See `move_in_request` for which fields are whose.
    """
    require_tenant(request)
    if request.method == "PUT":
        _require_write_role(request)
        return Response(move_in_request.save_form(_actor(request), request_id, _payload(request)))
    return Response(move_in_request.form(request_id))


def _with_applicant_message(moved: Any, detail: dict[str, Any]) -> dict[str, Any]:
    """Put the letter's outcome on the response, or say nothing was attempted.

    ⚠ **A RESULT THAT LIVES ONLY INSIDE A SERVICE CALL IS A RESULT NOBODY CAN
    SEE AGAIN** (hard-won law 2, applied to a response — the same reasoning the
    `route` endpoint above carries for its work orders). *"A refusal letter is
    queued to the applicant"* is drawn as a promise on the Refuse dialog, so
    whether it was kept has to reach the screen as a fact and not be inferred
    from a 200.
    """
    outcome = getattr(moved, "applicant_message", None)
    return {**detail, "applicant_message": outcome}


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_decision(request: Any, request_id: str) -> Response:
    """`POST .../decision` — `WHAT SHOULD THIS BECOME?`

    ✅ **`disconnect` IS ONE OF THE FIVE — BR-CUS-091**, *"Yes customer can
    request it"*. ⚠ And it is NOT a move-out: a move-out closes the account and
    settles the deposit (BR-CUS-030), a disconnect leaves it open and accruing
    (BR-MET-105). This route stores exactly what the clerk sent and maps
    nothing.
    """
    require_tenant(request)
    payload = _payload(request)
    writes.decide_outcome(
        _actor(request),
        request_id,
        outcome=_required_text(payload, "outcome"),
        note=payload.get("note"),
    )
    return Response(_detail(request_id))


@api_view(["GET", "PUT"])
@permission_classes([AnyTenantRole])
def service_request_applicant_messages(request: Any, request_id: str) -> Response:
    """`GET|PUT .../applicant-messages` — the drawn `What goes out to the applicant`.

    Capture step 6, p080, read as an image: five rows under `SEND · WHAT IT SAYS
    · TO · CHANNEL · TEMPLATE · WHEN`, three of them ticked.

    **GET** answers the five rows in the drawing's order, whether or not
    anything has been stored — the defaults are a constant, so a request nobody
    has touched and a request that predates the table both answer correctly
    rather than answering empty.

    **PUT** stores what the clerk ticked and picked. A row is refused by name
    for a template that is not this occasion's, for a DRAFT (p081: *"The draft
    version is listed and cannot be picked"*), and for a variant that cannot be
    read as writing on the decision row (*"A text never replaces a posted
    notice"*).

    ⚠ **THE PAYLOAD SAYS NOTHING IS SENT AND MEANS IT.** `delivery` carries
    `BR-NOT-013` — no provider adapter exists on any channel — so a screen built
    on this must say QUEUED and never *sent*. The drawing's own last line is the
    standing rule: *"Everything here is queued, and nothing is sent."*
    """
    require_tenant(request)
    if request.method == "PUT":
        _require_write_role(request)
        return Response(
            applicant_messages.save_block(
                _actor(request), request_id, _payload(request).get("rows")
            )
        )
    writes.request_row(request_id)
    return Response(applicant_messages.block_for(request_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def service_request_message_templates(request: Any, request_id: str) -> Response:
    """`GET .../applicant-message-templates?occasion=…&search=…` — the picker.

    Drawn beneath the block as `Choosing a template`: a search box helped
    *"Searches the name a human gave it."* and a table of
    `TEMPLATE · GROUP · CHANNEL · VARIANT · VERSION` with a radio per row.

    ⚠ **A DRAFT ROW IS RETURNED AND MUST BE RENDERED**, disabled, carrying
    `pickable: false` and its reason. p081: *"Hiding it sends a clerk looking
    for something they can see exists; offering it would queue a letter nobody
    has approved."* Filtering it out on the screen is the behaviour that rule
    exists to forbid.
    """
    require_tenant(request)
    writes.request_row(request_id)
    return Response(
        applicant_messages.templates_for(
            request.query_params.get("occasion") or applicant_messages.DECISION,
            search=request.query_params.get("search"),
        )
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def service_request_customer_search(request: Any, request_id: str) -> Response:
    """`GET .../customer-search` — the Approve dialog's *Search customer*
    (`DEF-CUS-10043`): the move-in's *Search customer ID* asked with the
    identity this request already holds. Found, possible or new — Q5's rule,
    unchanged. A READ: nothing is linked or written, so no audit row; the
    identifiers never leave the server (last four only)."""
    require_tenant(request)
    return Response(owner_lookup.search_for_request(writes.request_row(request_id)))


@api_view(["GET", "PUT"])
@permission_classes([AnyTenantRole])
def service_request_extra_messages(request: Any, request_id: str) -> Response:
    """`GET|PUT .../extra-messages` — the messages a CLERK added to *What the
    customer is told* (`DEF-CUS-10042`, PO 2026-10-11). PUT replaces the unfired
    rows whole: `{"rows": [{"template_code", "channel", "to_address",
    "send_when"}]}`. Nothing is sent — email reaches the outbound queue and
    stops there (`BR-NOT-013`)."""
    require_tenant(request)
    if request.method == "PUT":
        _require_write_role(request)
        return Response(
            {
                "rows": request_extra_messages.save(
                    _actor(request), request_id, _payload(request).get("rows")
                ),
                "templates": request_extra_messages.template_choices(),
            }
        )
    writes.request_row(request_id)
    return Response(
        {
            "rows": request_extra_messages.rows_for(request_id),
            "templates": request_extra_messages.template_choices(),
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_park(request: Any, request_id: str) -> Response:
    require_tenant(request)
    payload = _payload(request)
    writes.park(
        _actor(request),
        request_id,
        waiting_on=_required_text(payload, "waiting_on"),
        note=payload.get("note"),
        remind_on=_optional_date(payload, "remind_on"),
    )
    return Response(_detail(request_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_resume(request: Any, request_id: str) -> Response:
    require_tenant(request)
    writes.resume(_actor(request), request_id, note=_payload(request).get("note"))
    return Response(_detail(request_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_notes(request: Any, request_id: str) -> Response:
    """`Add a note`, badged **`Internal · never shown to the customer`**. There
    is no customer-visible path and there must not be one — the portal is out of
    v1 scope, so a visibility flag would be a permission with nothing to permit.
    """
    require_tenant(request)
    payload = _payload(request)
    writes.add_note(
        _actor(request),
        request_id,
        note=_required_text(payload, "note"),
        note_type=payload.get("note_type"),
    )
    return Response({"history": reads.history_tab(writes.request_row(request_id))})


# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE — category, services, address, the customer link
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def service_request_categories(request: Any) -> Response:
    """`GET /service-requests/categories` — the categories THIS utility uses.

    ⚠ **IT SERVED SEVEN, FROM A TUPLE, AND SILENTLY DROPPED EVERY ROW A TENANT
    ADDED (`DEF-CUS-5647`).** It read the live rows into a dict and then
    iterated `AccountType.SEVEN_CATEGORIES` over it, so a row outside that
    tuple could not appear however active it was. That was defensible while
    `account_types` was a PLATFORM table whose seven codes were a signed
    vocabulary; the PO ruling of 2026-09-17 — *"utility can get their own
    account types"* — makes it a real bug, and this is the fix. **The picker
    now offers every ACTIVE, non-legacy row of this tenant's own list.**

    Served as two lists rather than one flag, because the difference is the
    whole of `BR-CUS-094`:

      · `selectable` — every active, non-legacy row a new record may pick.
      · `legacy` — `government` on a seeded list, and whatever else a tenant has
        retired from new business. A legacy code **stops being selectable and
        changes nothing else**: still a valid FK, still filterable, still
        priceable, every existing account keeps it and bills exactly as it did.
        Re-pointing it to Municipal or Institutional is a HUMAN act per record,
        because the stored value cannot tell a city water department from a
        state university.

    ⚠ **THE ORDER IS A STORED FACT NOW, NOT AN ITERATION ORDER.** REQ-03.2 draws
    the chips as Residential · Commercial · Industrial · Agricultural ·
    Institutional · Municipal · Builder or developer and `BR-CUS-094` lists them
    in exactly that order, so sorting by `code` would put Agricultural first and
    quietly re-order a screen the PO drew. The seeded seven therefore carry that
    order in `account_types.sort_order` as 10..70 (`customers.0054`), the legacy
    slot is 900, and **a row the tenant ADDS is appended at `max + 10`** — so
    the drawn order survives and new rows land behind it, in the order the
    utility created them. `code` is the tiebreak so two rows sharing a slot
    still sort deterministically (IS-2).

    ⚠ **`/lookups/account_types` (the S8 card) now serves `legacy` too**, so a
    picker built against either surface can tell a retired code from a live one.
    """
    require_tenant(request)
    from apps.customers import models as customer_models

    rows = list(
        customer_models.AccountType.objects.filter(tenant_id=current_tenant_id()).order_by(
            "sort_order", "code", "id"
        )
    )
    selectable = [r for r in rows if r.active and not r.legacy]
    return Response(
        {
            "selectable": [{"code": r.code, "name": r.name} for r in selectable],
            "legacy": [
                {
                    "code": r.code,
                    "name": r.name,
                    "br_ref": "BR-CUS-094",
                    "why": "unselectable_on_new_records_valid_everywhere_else",
                }
                for r in rows
                if r.legacy
            ],
        }
    )


#: How many WORKING days ahead a new request's `Connection date` opens on.
#:
#: ⚠ **PO RULING 2026-09-22, verbatim: _"make it default add 15 working days"_**,
#: answering whether `Connection date` could be removed with option (b): *"Keep
#: both, make one fill the other — the per-service dates default from the job
#: date, and a clerk overrides where a service differs. Keeps the rule and kills
#: the conflict"*.
#:
#: ⚠ **IT IS A DEFAULT AND NOT A FLOOR.** Nothing refuses an earlier date, here
#: or downstream, and no caller may add one on the strength of this constant —
#: `cut_date`'s own *"IT COMPUTES AND IT DOES NOT REFUSE"* posture, for the same
#: reason: a floor would be this product asserting a rule nobody has ruled.
#:
#: ⚠ **NO LONGER A CONSTANT — `DEF-CUS-10445`, 2026-10-22.** This line read
#: `CONNECTION_DATE_WORKING_DAYS = 15`. The PO ruled the same day that the
#: acknowledgement's default target is *"Default 15 days"* and *"don't do any
#: hardcoding"*: it is the same fact (when service is aimed at, absent a date the
#: customer chose), so both now read ONE Settings number,
#: `service_request_default_target_days` (tenancy's `service-requests` family,
#: seeded 15, counted in working days). The PO's 15 is unchanged for every
#: utility that never opens the card.


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def service_request_capture_defaults(request: Any) -> Response:
    """`GET /service-requests/capture-defaults` — what a NEW request opens on.

    ⚠ **THE DATE IS COMPUTED HERE AND NOT IN THE BROWSER, AND THAT IS THE WHOLE
    REASON THIS ENDPOINT EXISTS.** Fifteen WORKING days means weekends out AND
    **this tenant's own public holidays** out (`BR-TEN-039`,
    `holiday_calendars`), and the browser holds neither the calendar nor the
    tenant's timezone. A front end counting weekdays by itself would answer a
    different date from every other business-day figure in this product, wrong
    by exactly one day per holiday in the window.

    ⚠ **IT REUSES `cut_date.business_days_after` AND WRITES NO ARITHMETIC OF ITS
    OWN.** That function carries `BR-BIL-002`'s convention — the start day is
    never one of the counted days — and `late_fee._business_days_between` shares
    it. **Two ways to count working days is two things that can disagree about
    when a customer gets service**, so a second counter is not an option.

    ⚠ **THE CALENDAR IS AN ARGUMENT, NEVER A QUERY INSIDE THE COUNTER**
    (`BR-TEN-043`). `seams.tenant_holidays()` is what refuses an unreachable
    calendar, and an EMPTY set is a legitimate answer meaning *this utility
    keeps no calendar*, never *we could not look*.

    **Worked, on the demo tenant, 2026-09-22 (a Tuesday), 22 holiday rows:**
    15 working days lands on **2026-10-14**. Without the calendar it would be
    2026-10-13 — Columbus Day (2026-10-12) falls inside the window and pushes it
    one day, which is the difference this endpoint exists to get right.
    """
    require_tenant(request)
    from apps.customers import cut_date, seams

    # ⚠ Read ONCE. `tenant_holidays()` is a seam call, and calling it twice
    # would let the date and the count it is reported beside come from two
    # different reads — small, and exactly the kind of disagreement a screen
    # then prints as a fact.
    holidays = seams.tenant_holidays()
    working_days = seams.service_request_default_target_days()
    return Response(
        {
            # ⚠ The key is `requested_start` because that is the COLUMN the
            # wizard PUTs it back into — `ServiceRequest.requested_start`, the
            # whole job's date. Calling it `connection_date` here would be a
            # second spelling of one field, which is how a payload and a form
            # come to disagree about which of them is authoritative.
            "requested_start": (
                cut_date.business_days_after(
                    seams.tenant_today(), working_days, holidays
                ).isoformat()
                if working_days is not None
                else None
            ),
            "working_days": working_days,
            # Stated so nothing downstream has to guess whether the figure above
            # counted a calendar or only weekends. They are different facts and
            # a clerk should never have to work out which one they are seeing.
            "holidays_counted": len(holidays),
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_category(request: Any, request_id: str) -> Response:
    require_tenant(request)
    payload = _payload(request)
    # ⚠ **CATEGORY AND SUB-CATEGORY MOVED TO THE APPLICANT** — PO 2026-09-29,
    # *"move this to appliant sicne it is applicant - arrtributes"*. They were
    # step 2's; a refusal here now names step 1.
    with steps.on_step(steps.STEP_APPLICANT):
        writes.set_customer_category(
            _actor(request),
            request_id,
            account_type_code=_required_text(payload, "account_type_code"),
            account_subtype_id=payload.get("account_subtype_id"),
        )
    return Response(_detail(request_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_services(request: Any, request_id: str) -> Response:
    """`POST .../services` — the capture wizard's step 3, replacing the set.

    ⚠ **STEP 3 SINCE 2026-09-29 AND STEP 2 BEFORE IT.** The six-step wizard put
    the services on their own screen; the four-step drawing merges them with
    the fees and the payment (PO: *"can we merge this two and create table
    array for this"*).

    ✅ **BR-CUS-1070 — AN ENTRY MAY CARRY ITS OWN START.** `services` is a list
    whose members are either a bare code (`"electric"`, the shape every caller
    sent until 2026-09-15, meaning *this service, no date given*) or an object
    `{"code": "electric", "requested_start": "2026-12-05"}`. A mixed list is
    fine; the old shape is not deprecated and nothing was migrated, because the
    join table held **0 rows** across the demo tenant's 8 requests when this
    landed.

    ⚠ **THE SHAPE CHECK STAYS HERE AND THE VALUE CHECKS STAY IN THE SERVICE.**
    This view answers *is `services` a list of things that could be services*;
    an unknown code, a repeated code and an unparseable date are each refused BY
    NAME by `set_services`, which is the door every caller goes through —
    including the ones that never touch HTTP.
    """
    require_tenant(request)
    payload = _payload(request)
    codes = payload.get("services")
    # ⚠ **THE SERVICES TABLE IS STEP 3 NOW AND WAS STEP 2.** PO 2026-09-29,
    # *"can we merge this two and create table array for this"* — the services
    # table, the fees table and the payment are one screen.
    with steps.on_step(steps.STEP_SERVICE):
        if not isinstance(codes, list) or any(
            not isinstance(entry, (str, dict)) for entry in codes
        ):
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="customers.serviceRequest.fieldRequired",
                params={"field": "services"},
                field_errors=[{"field": "services", "code": errors.VAL_REQUIRED}],
            )
        writes.set_services(_actor(request), request_id, codes)
    return Response(_detail(request_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_resolve_address(request: Any, request_id: str) -> Response:
    """`POST .../resolve-address` — the resolver writes EVIDENCE, never a
    decision. BR-CUS-070: `address_as_given` is untouched and the resolved ids
    land in their own columns beside it."""
    require_tenant(request)
    # ⚠ **THE ADDRESS SEARCH IS STEP 2 NOW AND WAS STEP 3.**
    with steps.on_step(steps.STEP_PROPERTY):
        writes.resolve_address(_actor(request), request_id)
    return Response(_detail(request_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_customer_link(request: Any, request_id: str) -> Response:
    """`customer_id: null` records **"searched, and there is no prior
    customer"** — a real answer, and what clears the arrears condition for a
    genuine first-time applicant."""
    require_tenant(request)
    payload = _payload(request)
    # The prior-customer search sits beside the applicant's own fields — step 1.
    with steps.on_step(steps.STEP_APPLICANT):
        writes.link_customer(
            _actor(request),
            request_id,
            customer_id=payload.get("customer_id"),
            tier=payload.get("tier"),
            basis=payload.get("basis"),
        )
    return Response(_detail(request_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_child_link(request: Any, request_id: str) -> Response:
    """BR-CUS-080 — one SR produces ONE live child per decision, and the SR alone
    answers *"what happened to this application"*."""
    require_tenant(request)
    payload = _payload(request)
    writes.link_child(
        _actor(request),
        request_id,
        child_ref=_required_text(payload, "child_ref"),
        child_kind=payload.get("child_kind"),
    )
    return Response(_detail(request_id))


# ═══════════════════════════════════════════════════════════════════════════
# DOCUMENTS — two gates
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@permission_classes([AnyTenantRole])
def service_request_documents(request: Any, request_id: str) -> Response:
    """**GATE ONE: attaching never blocks CREATION** — REQ-03.4's `NOT BLOCKING`
    callout. The POST lands `not_checked`, always.

    ⚠ **TWO POSTS, ONE ADDRESS, TOLD APART BY WHETHER A FILE CAME WITH IT.**

      * **With a `file` part** — the bytes go to the document store and the row
        gets `name`, `size`, `storage_ref`, `uploaded_by` and `uploaded_at`.
        This is what the PO ruled in with *"you will have to reduce the size and
        save them on cloud container etc"*; the capture screen's step 4 said
        *"We cannot take a file yet — there is nowhere to store it"* until it
        landed, and that sentence was true.
      * **Without one** — the JSON path that has always been here: a clerk TICKS
        what the applicant is expected to bring, and the request records it. It
        is untouched, and it is deliberately still reachable. ⚠ **THIS SAID
        the beta's six rows were ticks of exactly this kind; they are SEEDED
        PLACEHOLDERS pointing at nothing (`DEF-CUS-5872`)**, which is a
        different fact and was never measured before it was written.

    They are one endpoint rather than two because they produce the same row on
    the same tab, and a second address would make *"attach a document"* two
    things a screen has to choose between.

    ⚠ **413 AND 415 ARE CAUGHT HERE AND NOT RAISED AS CATALOG REFUSALS.**
    `HTTP_STATUS_BY_CODE` maps a B12 §3 code to a status and neither transport
    row has one, so a `ValidationError` would answer 422 to a file over the cap
    (B12 r1's HTTP-series rows; 11b G11). The body is the SHARED envelope
    `core.errors.http_series_refusal_body`, exactly as the account-documents
    door already answers.

    ⚠ **THE FILE PART IS NEVER READ AS A FORM FIELD.** `request.data` on a
    multipart request carries the upload too; `file` is stripped out of the
    payload dict so a clerk cannot smuggle a value into a column by naming a
    part after it.
    """
    require_tenant(request)
    if request.method == "POST":
        _require_write_role(request)
        upload = request.FILES.get("file") if hasattr(request, "FILES") else None
        payload = _payload(request)
        # ⚠ **DOCUMENTS ARE STEP 1 NOW AND WERE STEP 4.** PO 2026-09-29; the
        # `Documents` panel sits under the applicant's own fields. A refusal
        # from either route — with bytes or without — names step 1.
        #
        # ⚠ **THE 413/415 PATH IS DELIBERATELY OUTSIDE THE STAMP.** It is not a
        # catalogue refusal at all: it answers the shared HTTP-series envelope
        # with its own status, carries no `params` a wizard reads, and
        # `on_step` catches only `ValidationError` and `BizError`. Wrapping it
        # would claim a step on a body that has nowhere to put one.
        if upload is not None:
            payload = {k: v for k, v in (payload or {}).items() if k != "file"}
            try:
                with steps.on_step(steps.STEP_APPLICANT):
                    doc_files.attach_file(_actor(request), request_id, payload, upload)
            except doc_files.UploadRefused as refusal:
                return Response(
                    errors.http_series_refusal_body(
                        refusal.message_key, br_ref=refusal.br_ref, **refusal.params
                    ),
                    status=refusal.status,
                )
        else:
            with steps.on_step(steps.STEP_APPLICANT):
                writes.attach_document(
                    _actor(request),
                    request_id,
                    doc_type=_required_text(payload, "doc_type"),
                    name=payload.get("name"),
                    storage_ref=payload.get("storage_ref"),
                    size=payload.get("size"),
                    what_it_proves=payload.get("what_it_proves"),
                    document_number=payload.get("document_number"),
                    required=bool(payload.get("required", False)),
                )
    return Response(reads.documents_tab(writes.request_row(request_id)))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def service_request_document_download(
    request: Any, request_id: str, document_id: str
) -> Response:
    """`GET /service-requests/{id}/documents/{docId}/download` — a link that dies.

    ⚠ **THE ROW IS RESOLVED UNDER THIS TENANT FIRST, AND THE URL IS MINTED
    SECOND.** A link is never issued for a document the caller could not have
    found; another utility asking for this file gets a **404**, the same answer
    as for one that never existed (`BR-TEN-003`, HR-1 — existence must not
    leak). The order is `account_documents.document_link`'s and `work.evidence`'s.

    ⚠ **FOUR HOURS, AND IT IS A BEARER TOKEN** (PO ruling 2026-08-30). Whoever
    holds this URL reads this one document with no session until it expires. Do
    not put one in an email that outlives it — issue a new link instead.

    ⚠ **`AnyTenantRole`, NOT `AdminOrClerk`** — this is a READ. An Executive who
    may see the request may see what was filed on it; the split `POST` makes is
    about who may FILE (`BR-SHL-031`, *"v1 uploads staff-mediated"*).
    """
    require_tenant(request)
    return Response(doc_files.document_link(request_id, document_id))


#: The policy and the disposition builder MOVED to `core.document_response` on
#: 2026-10-02 (`DEF-CWP-9166`) when the portal's applicant needed the same
#: serving code to open their own file — B14 rule 43, one copy. Re-exported
#: under the old names so `customers/api.py` and every test are unchanged.
from core.document_response import DOCUMENT_CSP  # noqa: E402
from core.document_response import content_disposition as _content_disposition  # noqa: E402
from core.document_response import document_http_response  # noqa: E402


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def service_request_document_content(
    request: Any, request_id: str, document_id: str
) -> Any:
    """`GET /service-requests/{id}/documents/{docId}/content?as=view|download`
    — the file itself, for a clerk to open or save (`CR-158-BRC10`).

    ⚠ **THE HEADERS ARE THE SAFETY, AND EACH ONE IS THERE FOR A REASON:**
      * `Content-Disposition` — `inline` only for a PDF, PNG or JPEG asked for
        with `as=view`; everything else is `attachment`, so a browser saves it
        rather than rendering it;
      * `X-Content-Type-Options: nosniff` — the browser draws the type we
        declare and never guesses a more dangerous one from the bytes;
      * `Content-Security-Policy` — no script runs inside a served file
        (`DOCUMENT_CSP`);
      * `Cache-Control: private, no-store` — a stranger's licence is not kept
        in a shared cache or on the clerk's disk by the browser.

    Resolved under this tenant first; another utility gets 404. Audited, one row
    per open or download (`document_content`).
    """
    require_tenant(request)
    mode = str(request.query_params.get("as") or doc_files.CONTENT_VIEW)
    served = doc_files.document_content(_actor(request), request_id, document_id, mode)
    return document_http_response(
        payload=served["payload"],
        content_type=served["content_type"],
        name=served["name"],
        inline=served["inline"],
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_document_verify(request: Any, request_id: str, document_id: str) -> Response:
    """**GATE TWO: verifying is what unblocks APPROVAL.** *"Attaching a file is
    not the same as verifying it."* A document with no file cannot be verified —
    that would be a clerk certifying nothing."""
    require_tenant(request)
    writes.verify_document(_actor(request), document_id)
    return Response(reads.documents_tab(writes.request_row(request_id)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_document_reject(request: Any, request_id: str, document_id: str) -> Response:
    require_tenant(request)
    writes.reject_document(
        _actor(request), document_id, reason=_required_text(_payload(request), "reason")
    )
    return Response(reads.documents_tab(writes.request_row(request_id)))


# ═══════════════════════════════════════════════════════════════════════════
# BR-CUS-095 — THE SETTINGS CHECKLIST. System Admin only, ships UNTICKED
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "PUT"])
@permission_classes([SystemAdminOnly])
def service_request_document_requirements(request: Any) -> Response:
    """`/service-request-settings/document-requirements` — *"Settings grows a
    checklist — for each request type, tick which documents are required."*

    ⚠ **THE GET RETURNS THE WHOLE GRID, TICKED OR NOT.** A checklist that listed
    only what somebody had already touched could never be ticked for the first
    time. `configured: false` is how the screen tells *"nobody has looked"* from
    *"we said no"*.

    ⚠ **AND THE SHIPPED ANSWER IS EVERY CELL UNTICKED.** BR-CUS-095's sharpest
    clause: *"We ship with nothing ticked, and a utility that configures nothing
    blocks nothing."* No pre-tick of `proof_of_identity`, however reasonable it
    looks — the product ships with no opinion about any jurisdiction's law.

    **System Admin only**: this changes what every future approval of that job
    type demands, which is a settings act, not a capture act.
    """
    require_tenant(request)
    if request.method == "PUT":
        payload = _payload(request)
        writes.set_document_requirement(
            _actor(request),
            request_type=_required_text(payload, "request_type"),
            doc_type=_required_text(payload, "doc_type"),
            required=bool(payload.get("required", False)),
        )
    return Response(
        {
            "requirements": writes.document_requirements(
                request.query_params.get("request_type") or None
            ),
            "ships_unticked": True,
            "br_ref": "BR-CUS-095",
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# FEES — a QUOTE, and what the counter took (BR-CUS-090)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def service_request_fees(request: Any, request_id: str) -> Response:
    require_tenant(request)
    if request.method == "POST":
        _require_write_role(request)
        payload = _payload(request)
        # ⚠ **THE FEES TABLE IS STEP 3 NOW AND WAS STEP 5.**
        with steps.on_step(steps.STEP_SERVICE):
            writes.add_fee_line(
                _actor(request),
                request_id,
                charge_code=_required_text(payload, "charge_code"),
                unit_amount=_money_field(payload, "unit_amount"),
                quantity=(
                    _money_field(payload, "quantity")
                    if payload.get("quantity") is not None
                    else Decimal("1")
                ),
                basis=payload.get("basis"),
                description=payload.get("description"),
                charge_code_id=payload.get("charge_code_id"),
            )
    return Response(reads.fees_tab(writes.request_row(request_id)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_fee_waive(request: Any, request_id: str, fee_id: str) -> Response:
    """`Waive the fee` — *"A reason is required and recorded against your
    name."* Both halves are enforced. ⚠ A waiver is NOT what a shortfall at the
    counter becomes (BR-CUS-090); that stays an open balance."""
    require_tenant(request)
    with steps.on_step(steps.STEP_SERVICE):
        writes.waive_fee_line(
            _actor(request), fee_id, reason=_required_text(_payload(request), "reason")
        )
    return Response(reads.fees_tab(writes.request_row(request_id)))


@api_view(["DELETE"])
@permission_classes([AdminOrClerk])
def service_request_fee_line(request: Any, request_id: str, fee_id: str) -> Response:
    """`DELETE .../fees/{fee_id}` — the fee table's remove icon on capture step
    3 (step 5 until the four-step redraw of 2026-09-29), **OQ-357 closed
    2026-09-23 as "both"**: a line is removed while the
    request is a DRAFT and waived, with a reason, after. Every refusal is the
    service's, by name (`remove_fee_line`). Answers with the whole fees tab, so
    the reply IS the new table."""
    require_tenant(request)
    with steps.on_step(steps.STEP_SERVICE):
        writes.remove_fee_line(_actor(request), fee_id, request_id=request_id)
    return Response(reads.fees_tab(writes.request_row(request_id)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def service_request_fee_collection(request: Any, request_id: str) -> Response:
    """`POST .../fee-collection` — **BR-CUS-090, the counter takes the WHOLE
    application fee, or the fee is waived (`OQ-CUS-12624`, 2026-09-24).**

    PO verbatim: *"all or waived"*. `amount` must equal the fee still owing;
    anything else is refused before a row is written (422, `BIZ-COMPLETENESS`,
    `customers.serviceRequest.feeTakeInFull`, params `amount` and `currency`).
    The way out of a fee not paid in full is BR-CUS-073's waiver, with a
    reason, on a line.

    **Worked:** quoted $130.00, `{"amount": "25.00", "method": "cash",
    "receipt_no": "RCP-26-4471"}` → refused, *"Take the full $130.00. Or waive
    it."*; `{"amount": "130.00", …}` → *$130.00 collected · $0.00
    outstanding*.

    ⛔ SUPERSEDED 2026-09-24: *"A shortfall is never refused here"* (BR-CUS-090's
    2026-08-24 desk clause, *"we acept it and in finance we will reconcile"*).

    ⚠ `amount` must be a STRING. A JSON float is refused, not coerced (rule 2).
    ⚠ Idempotent on the receipt number (rule 6) — the desk is exactly where a
    double-click happens. A repeat with the same receipt is a no-op; a second
    collection with a different receipt is refused rather than summed.

    ⚠ **AND SINCE 2026-09-15 IT POSTS (PO ruling).** *"payemnt should show in
    payments, in ledge and in fiannce books"*. One `counter_receipts` row in
    payments and one balanced journal entry — DR the tender's clearing account,
    else `1010 Undeposited funds` · CR `2400 Customer credit balances` — in the
    same transaction as the columns above. Still no invoice and still no
    customer account: there is neither at capture, and a balanced pair needs
    neither.

    ⚠ **THE TENDER DETAIL IS OPTIONAL AND TYPED, AND THE CARD NUMBER IS NOT IN
    IT.** PO: *"we need to allow to take payment detials, card detial scheck
    details here curerntly is is not taking inputs"*. Two optional objects, and
    a body that sends neither behaves exactly as it did yesterday:

        "card":   {"last4": "4242", "brand": "visa", "auth_code": "A19422"}
        "check":  {"number": "10241", "bank": "First National",
                   "date": "2026-05-12"}

    The full card number is **never** accepted. Last four, brand and the
    terminal's authorisation code are what match our line to the bank's; the
    number itself is read by nothing in this product and would put the whole
    database under card-industry rules.

    **Worked, the drawn case:** `{"amount": "25.00", "method": "cash",
    "receipt_no": "RCP-26-4471"}` → $25.00 recorded, `DR 1010 25.0000 · CR 2400
    25.0000`, and the request reads *$25.00 collected · $0.00 outstanding*.
    """
    require_tenant(request)
    payload = _payload(request)
    # ── DEF-CUS-6376 · RECORD A PAYMENT'S THREE FACTS ─────────────────────
    # PO, on SR-26-0016: *"it should be similar to record payment form so
    # pasting date, type of payment , memo and it will take only application
    # fee"*. `posted_at` is a `YYYY-MM-DD` CALENDAR DATE — the business day the
    # money counts for and the ledger entry's date — read as the TENANT's day
    # (BR-TEN-081); absent, `collect_fee` takes the tenant's today. `memo` and
    # `confirmation` (the instrument's own number) are optional text. Written
    # as comments rather than into the docstring above, which is the committed
    # OpenAPI description (hard-won law 5: one generated file).
    # ⚠ **THE PAYMENT IS STEP 3 NOW AND WAS STEP 5** — `When is it being paid?`
    # sits under the fees table on one screen. Both refusal families are inside
    # the stamp on purpose: the till rule below is a `BizError` and a clerk
    # sent to the wrong screen by it is no better off than one sent by a
    # `ValidationError`.
    with steps.on_step(steps.STEP_SERVICE):
        return _collect_the_fee(request, request_id, payload)


def _collect_the_fee(request: Any, request_id: str, payload: dict[str, Any]) -> Response:
    """The body of `POST .../fee-collection`, so one `with` covers all of it."""
    amount = _money_field(payload, "amount")
    method = _required_text(payload, "method")
    receipt_no = _required_text(payload, "receipt_no")
    posted_on = _optional_date(payload, "posted_at")
    # ── DEF-CUS-6374 · A HAND TENDER NEEDS AN OPEN TILL ───────────────────
    # PO ruling 2026-09-23 §3.4, verbatim: *"(a) Refuse it. \"Start your
    # counter first.\" One press, then take the money. It is the only option
    # where every cash dollar belongs to somebody"* — and OQ-PAY-12601 (closed
    # the same day): anyone keying money opens a till. This door took $70.00 in
    # notes from a clerk with no till open. The rule has ONE implementation
    # (`payments.counters.assert_till_open_for_tender`); this is a call site,
    # through the seam, AFTER the body is known to be well-formed and BEFORE
    # anything is written. At the endpoint and not in `collect_fee`, for
    # `P2.23`'s reason: the sample data seeds a collection with no clerk.
    refusal = payments_seam.till_refusal(_actor(request), method)
    if refusal is not None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-PAY-1186",
            # A LITERAL key at the raise site — the one Record a payment's door
            # raises, so a clerk reads the same words at both counters.
            message_key="payments.counter.till_required",
            params={"detail": refusal},
        )
    writes.collect_fee(
        _actor(request),
        request_id,
        amount=amount,
        method=method,
        receipt_no=receipt_no,
        card=_tender_detail(payload, "card", ("last4", "brand", "auth_code")),
        # ⚠ **`check` IS THE KEY AND `cheque` IS ACCEPTED** — PO 2026-09-29,
        # *"use american english check = not cheque"*. The drawn step-3 fields
        # are `Check number · Check bank · Check date`. The keyword going the
        # other way stays `cheque=` because that is PAYMENTS' contract
        # (`record_counter_receipt`) and this module does not get to rename a
        # neighbour's parameter — the spelling that moved is ours.
        cheque=(
            _tender_detail(payload, "check", ("number", "bank", "date"))
            or _tender_detail(payload, "cheque", ("number", "bank", "date"))
        ),
        posted_on=posted_on,
        confirmation=payload.get("confirmation"),
        memo=payload.get("memo"),
    )
    return Response(reads.fees_tab(writes.request_row(request_id)))


def _tender_detail(
    payload: dict[str, Any], name: str, allowed: tuple[str, ...]
) -> dict[str, Any] | None:
    """One optional tender object, narrowed to the keys we agreed to keep.

    ⚠ **IT IS AN ALLOW LIST AND NOT A PASS-THROUGH, WHICH IS THE WHOLE POINT.**
    A client sending `{"number": "4242424242424242"}` under `card` gets it
    DROPPED here rather than stored — the boundary refuses what we decided not
    to hold, instead of trusting every future caller to send only the three
    fields. A pass-through would make the card-data decision a property of
    whatever front end happens to be calling.

    A missing object, a null, or anything that is not a JSON object answers
    `None`, which is the ordinary case: cash carries no detail.
    """
    value = payload.get(name)
    if not isinstance(value, dict):
        return None
    kept = {key: value.get(key) for key in allowed if value.get(key) not in (None, "")}
    return kept or None


# ═══════════════════════════════════════════════════════════════════════════
# THE INTERRUPTION A CLERK OPENS FROM A REPORT — CR-068 wave B, amended by
# CR-072 (2026-09-04): the report no longer raises one, a person does
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ **WHY IT HANGS OFF A SERVICE REQUEST AND HAS NO SCREEN OF ITS OWN.** The
# clerk who moves a burst main to *crew on site* is reading the request the
# report raised; `10-execution-plan.md` §0 row 22 records that no staff screen
# owns that write, and the ruling `R13` keeps screen numbers the PO's, so the
# control is a SECTION of the existing request detail rather than a new `S`-id.
# The interruption belongs to `metering` and is written through ITS service
# (`BR-CWP-012`, B2 §2): this file calls a door, it does not touch a table.


def _interruption_of(request: Any) -> Any:
    """The CONFIRMED interruption this report is about, or None.

    ⚠ **THE LINK REVERSED ON 2026-09-04 (`CR-072`).** This used to read
    `Interruption.objects.filter(service_request_id=…)` — a one-to-one FK on the
    METERING row, which is what forced a second interruption per report. The
    request now carries the pointer, and MANY of them may carry the same one.
    """
    if not request.interruption_id:
        return None
    return interruption_models.Interruption.objects.filter(id=request.interruption_id).first()


def _interruption_view(row: Any) -> dict[str, Any] | None:
    """The operational record itself, or None when a clerk has not opened one."""
    if row is None:
        return None
    affected = interruption_service.affected_set(row.id)
    return {
        "id": str(row.id),
        "reference": row.reference,
        "kind": row.kind,
        "status": row.status,
        "location_text": row.location_text,
        "affected_area": row.affected_area,
        "expected_back_on": row.expected_back_on.isoformat() if row.expected_back_on else None,
        "reported_at": row.reported_at.isoformat() if row.reported_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        # ⚠ `statuses` moved UP to the section on 2026-09-04 (CR-072): the
        # screen needs the vocabulary whether or not a record exists yet.
        "affected_premises": affected["premises"],
        "affected_premises_count": affected["premises_count"],
        "affected_unit_count": affected["unit_count"],
    }


def _section_view(sr: Any) -> dict[str, Any]:
    """The whole Interruption section: the REPORT, the record it is about (or
    the absence of one), and the open interruption on the same street if there
    is one.

    ⚠ **THE SHAPE CHANGED ON 2026-09-04 (`CR-072`) AND IT HAD TO.** This
    endpoint used to answer the interruption alone, or 404. A report no longer
    OPENS an interruption — a clerk does, when the reports are real — so a
    report with none is now the ordinary case, and 404 for it would have left
    the clerk no way to open one at all. That is hard-won law 2 in advance:
    moving the write without moving the screen would have shipped a section
    that renders for nobody.
    """
    row = _interruption_of(sr)
    return {
        "report": {
            "kind": sr.problem_kind,
            "location_text": sr.address_as_given,
            "reported_at": sr.received_at.isoformat() if sr.received_at else None,
        },
        "interruption": _interruption_view(row),
        # ⚠ **A SUGGESTION, NEVER A DECISION.** `street_words` is a deliberately
        # small rule and its own docstring limits it to ONE sentence on a
        # confirmation screen; this is the same weight of claim — *somebody has
        # already reported this street* — offered to a clerk who then decides.
        # It does not pick, attach or merge anything.
        "already_open_nearby": _nearby_view(sr) if row is None else None,
        "statuses": list(interruption_models.STATUSES),
    }


def _nearby_view(sr: Any) -> dict[str, Any] | None:
    """An interruption already open on this report's street, offered to the
    clerk as *attach to this one instead*, or None."""
    if not sr.problem_kind:
        return None
    found = interruption_service.open_on_street(sr.tenant_id, sr.address_as_given)
    if found is None:
        return None
    return {
        "id": str(found.id),
        "reference": found.reference,
        "location_text": found.location_text,
        "status": found.status,
    }


@api_view(["GET", "POST", "PATCH"])
@permission_classes([AdminOrClerk])
def service_request_interruption(request: Any, request_id: str) -> Response:
    """`GET/POST/PATCH .../interruption` — open one, move it, set the stretch.

    **`GET`** answers the section. A request that is neither a report nor
    attached to an interruption answers **404**, not an empty object — a section
    that rendered for every request would be an empty frame on every move-in in
    the product (`BR-CWP-093` in the staff app's dialect).

    **`POST`** is `BR-CWP-101`: a clerk judges the reports real and opens the
    operational record. With `interruption_id` in the body it ATTACHES to one
    already open — that is how twelve reports of one burst main become twelve
    requests pointing at one interruption. With no body it OPENS a new one from
    the report's own kind and its own words.

    **`PATCH`** may carry `status`, `affected_area` or `expected_back_on`, in
    any combination; each reaches its own service door and each writes its own
    audit row. It refuses with 404 while nothing is attached, because there is
    nothing to move.
    """
    require_tenant(request)
    sr = writes.request_row(request_id)
    row = _interruption_of(sr)
    if row is None and not sr.problem_kind:
        raise errors.deny_as_not_found("BR-CWP-012")

    if request.method == "POST":
        payload = _payload(request)
        attach_to = payload.get("interruption_id")
        if not attach_to:
            opened = interruption_service.create_interruption(
                _actor(request),
                kind=sr.problem_kind,
                location_text=sr.address_as_given,
                reporter_name=sr.applicant_name,
                reporter_phone=sr.applicant_phone,
            )
            attach_to = opened.id
        writes.attach_interruption(_actor(request), sr.id, interruption_id=attach_to)
        sr.refresh_from_db(fields=["interruption_id"])
        return Response(_section_view(sr), status=201)

    if request.method == "PATCH":
        if row is None:
            raise errors.deny_as_not_found("BR-CWP-012")
        payload = _payload(request)
        if "status" in payload:
            interruption_service.set_status(
                _actor(request), row.id, status=payload.get("status")
            )
        if "affected_area" in payload or "expected_back_on" in payload:
            interruption_service.set_affected_area(
                _actor(request),
                row.id,
                area=payload.get("affected_area", row.affected_area),
                expected_back_on=payload.get("expected_back_on"),
            )
    return Response(_section_view(sr))


urlpatterns = [
    # ⚠ ORDER IS LOAD-BEARING. `service-requests/categories` is ALL-STATIC and
    # is declared ABOVE `service-requests/<str:request_id>`, or the word
    # "categories" resolves as a request id and the picker 404s. Same reason
    # `accounts/master` sits above `accounts/<id>` in apps/customers/api.py.
    path("service-requests", service_requests),
    path("service-requests/categories", service_request_categories),
    # Same ORDER rule as `categories` above — all-static, so it must sit ahead
    # of `<str:request_id>` or "capture-defaults" resolves as a request id.
    path("service-requests/capture-defaults", service_request_capture_defaults),
    path("service-requests/<str:request_id>", service_request_item),
    path("service-requests/<str:request_id>/submit", service_request_submit),
    path("service-requests/<str:request_id>/transitions", service_request_transition),
    path("service-requests/<str:request_id>/approve", service_request_approve),
    path(
        "service-requests/<str:request_id>/approval-preview",
        service_request_approval_preview,
    ),
    path("service-requests/<str:request_id>/refuse", service_request_refuse),
    # ⊕ `CR-171-BRC10` P1.06–P1.08 — the move-in view's request half.
    path("service-requests/<str:request_id>/resend-ask", service_request_resend_ask),
    path("service-requests/<str:request_id>/reopen", service_request_reopen),
    path("service-requests/<str:request_id>/messages", service_request_messages),
    path("service-requests/<str:request_id>/audit", service_request_audit),
    path("service-requests/<str:request_id>/move-in-form", service_request_move_in_form),
    path("service-requests/<str:request_id>/decision", service_request_decision),
    path(
        "service-requests/<str:request_id>/applicant-messages",
        service_request_applicant_messages,
    ),
    path(
        "service-requests/<str:request_id>/applicant-message-templates",
        service_request_message_templates,
    ),
    path(
        "service-requests/<str:request_id>/extra-messages",
        service_request_extra_messages,
    ),
    path(
        "service-requests/<str:request_id>/customer-search",
        service_request_customer_search,
    ),
    path("service-requests/<str:request_id>/park", service_request_park),
    path("service-requests/<str:request_id>/resume", service_request_resume),
    path("service-requests/<str:request_id>/notes", service_request_notes),
    path("service-requests/<str:request_id>/interruption", service_request_interruption),
    path("service-requests/<str:request_id>/category", service_request_category),
    path("service-requests/<str:request_id>/services", service_request_services),
    path("service-requests/<str:request_id>/resolve-address", service_request_resolve_address),
    path("service-requests/<str:request_id>/customer-link", service_request_customer_link),
    path("service-requests/<str:request_id>/child-link", service_request_child_link),
    path("service-requests/<str:request_id>/documents", service_request_documents),
    path(
        "service-requests/<str:request_id>/documents/<str:document_id>/download",
        service_request_document_download,
    ),
    path(
        "service-requests/<str:request_id>/documents/<str:document_id>/content",
        service_request_document_content,
    ),
    path(
        "service-requests/<str:request_id>/documents/<str:document_id>/verify",
        service_request_document_verify,
    ),
    path(
        "service-requests/<str:request_id>/documents/<str:document_id>/reject",
        service_request_document_reject,
    ),
    path("service-requests/<str:request_id>/fees", service_request_fees),
    path("service-requests/<str:request_id>/fees/<str:fee_id>/waive", service_request_fee_waive),
    path("service-requests/<str:request_id>/fees/<str:fee_id>", service_request_fee_line),
    path(
        "service-requests/<str:request_id>/fee-collection",
        service_request_fee_collection,
    ),
    # The BR-CUS-095 checklist is a SETTING, so it lives on its own prefix
    # rather than under a request: it is not about any one request.
    path("service-request-settings/document-requirements", service_request_document_requirements),
]
