# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · P1.06 · P1.07 · P1.08, lane MVI-REQ
# Rules:    the PO's eight-status actions table, 2026-10-05 (decision log
#           "MOVE-IN REDESIGN: DETAILS-VIEW ACTIONS BY STATUS RULED AS
#           PROPOSED") · CR-171 §6.1 (one status function) · §6.2 J1–J3 ·
#           BR-SHL-048 (a park changes nothing until executed) · BR-CUS-092
#           (an identifier is served as its last four only) · CLAUDE.md hard
#           rules 1 · 7
# Question: OQ-CUS-12789 (Reopen on a declined move-in request) — CLOSED
#           2026-10-05 → (a); built by lane MVI-FLOW
# Tests:    06-backend/tests/test_cr171_move_in_request_view.py
# Impacts:  service_request_api.py (`/move-in-form`, `/audit`) · CR-171 §9
# ───────────────────────────────────────────────────────
"""A service request seen from the MOVE-INS list — what it is called there,
which buttons it offers, and how the four-step Add form edits it.

**THIS MODULE WRITES NO SERVICE REQUEST.** `service_request_service` is the sole
writer and every write below goes through it (`update_request`,
`set_customer_category`, `set_services`); the park goes through
`apps.tenancy.wizard_parks`, the sole writer of `wizard_parks`. What lives here
is the MAPPING between a request and the move-in form, and the PO's actions
table for the three request statuses — two things that had nowhere to live,
because the request page and the move-in wizard never spoke to each other.

════════════════════════════════════════════════════════════════════════════
THE THREE REQUEST STATUSES (CR-171 §6.1) AND THEIR BUTTONS
════════════════════════════════════════════════════════════════════════════
The PO's table, verbatim in the decision log of 2026-10-05:

  * **To approve** — Approve ✓ · Ask for more… · More: Edit, Decline…
  * **Waiting on customer** — Approve ✓ · Resend the ask · More: Edit, Decline…
  * **Declined** — More: Reopen

Each key names a door that already exists (CR-171 §9 lists them):
`approve` → `POST /service-requests/{id}/approve` with `outcome: move_in`;
`ask_for_more` → `POST …/transitions` (`request_info`); `decline` →
`POST …/refuse`; `resend_ask` → `POST …/resend-ask`; `edit` →
`GET|PUT …/move-in-form`.

`reopen` → `POST …/reopen` (lane MVI-FLOW).

⚠ **`reopen` WAS HELD ON `OQ-CUS-12789` UNTIL 2026-10-05 AND IS NOW BUILT.**
The PO's ruling of 2026-09-19 had retired `reopen` and made a refusal terminal
(*"a reapplication is a NEW request"*); the table of 2026-10-05 drew Reopen on a
declined move-in, and the collision went back to the PO. Answered → (a),
verbatim: *"Reopen: SR-26-0014 goes back to "To approve". Same number, her
documents stay, and the decline stays in its history."* The writer is
`service_request_service.reopen_declined_move_in`; the state table is
`service_request.MOVE_IN_TRANSITIONS` (move-ins ONLY — the generic request
page still cannot reopen anything).

════════════════════════════════════════════════════════════════════════════
EDIT USES THE ADD FORM (J3) — WHICH FACTS ARE THE REQUEST'S
════════════════════════════════════════════════════════════════════════════
`REQUEST_OWNED` is the whole list. A value the form carries under one of those
paths is WRITTEN BACK to the request; every other value is PARKED, in one
`wizard_parks` row (flow `move_in`) tied to the request by a COPIED id in
`subject_ref` (BR-SHL-048 (a) — never a foreign key). The two halves never
overlap: a request-owned key is stripped from the park, so there is one home for
each fact and reopening the form cannot show a stale copy beside the truth.

⚠ **THE PARK CARRIES THE REQUEST'S OWN NUMBER, SO NO MOVE-IN NUMBER IS SPENT.**
`wizard_parks._draft_reference` mints an `MVI-` number for a move-in park that
carries nothing — and approving then raises a job with ANOTHER `MVI-` number,
which is the two-numbers-for-one-move-in shape `BR-SHL-048 (d)` was ruled on
(*"we cannot create two build"*). So the park carries `request_no` as its
reference (`CARRIED_REFERENCE_KEYS`).

⚠ **IT NEVER APPROVES.** Saving writes fields and a draft; the request's state
does not move and no job is raised. `_refuse_unless_editable` (inside every
writer called here) refuses once the request is decided, so a declined or
approved request cannot be edited through this door either.

⚠ **ONE TRANSACTION.** The write-back and the park commit together or not at
all. Every refusal on this path is a Python exception raised BEFORE a failing
statement, so the outer `atomic()` rolls back cleanly on PostgreSQL; nothing
here catches a database error and carries on (hard-won law 14 does not apply,
and the PostgreSQL run of the test file proves it anyway).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from core import errors
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

from apps.customers import models
from apps.customers import service_request as rules
from apps.customers import service_request_service as writes

# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE STATUS AND THE BUTTONS
# ═══════════════════════════════════════════════════════════════════════════
STATUS_TO_APPROVE = "to_approve"
STATUS_WAITING_ON_CUSTOMER = "waiting_on_customer"
STATUS_DECLINED = "declined"

#: A request's state → its status on the Move-ins list (CR-171 §6.1). A state
#: not here (`draft`, `approved`, the retired ones) is not a request ROW on the
#: list: a draft has not been sent, and an approved one IS its job now.
_STATUS_BY_STATE: dict[str, str] = {
    rules.SUBMITTED: STATUS_TO_APPROVE,
    rules.UNDER_REVIEW: STATUS_TO_APPROVE,
    rules.MORE_INFO: STATUS_WAITING_ON_CUSTOMER,
    rules.REFUSED: STATUS_DECLINED,
}

ACTION_APPROVE = "approve"
ACTION_ASK_FOR_MORE = "ask_for_more"
ACTION_RESEND_ASK = "resend_ask"
ACTION_EDIT = "edit"
ACTION_DECLINE = "decline"
ACTION_REOPEN = "reopen"

#: The PO's table, in its order: primary first, then the secondary button,
#: then the More menu. `declined` offers Reopen (`OQ-CUS-12789` → (a)).
_ACTIONS_BY_STATUS: dict[str, tuple[str, ...]] = {
    STATUS_TO_APPROVE: (ACTION_APPROVE, ACTION_ASK_FOR_MORE, ACTION_EDIT, ACTION_DECLINE),
    STATUS_WAITING_ON_CUSTOMER: (ACTION_APPROVE, ACTION_RESEND_ASK, ACTION_EDIT, ACTION_DECLINE),
    STATUS_DECLINED: (ACTION_REOPEN,),
}


def request_status(state: str | None) -> str | None:
    """The Move-ins list's word for a request in `state`, or None."""
    return _STATUS_BY_STATE.get(str(state or ""))


def request_actions(state: str | None) -> tuple[str, ...]:
    """The buttons the details view offers a request in `state`, in order."""
    return _ACTIONS_BY_STATUS.get(request_status(state) or "", ())


def reopen(actor: Any, request_id: Any, *, reason: str) -> models.ServiceRequest:
    """*Reopen* on a declined move-in request — back to *To approve*, same
    number, documents kept, the decline kept in its history (PO 2026-10-05,
    `OQ-CUS-12789` → (a)). A reason is required (`BR-CUS-072`). The one writer
    is the request's own service."""
    return writes.reopen_declined_move_in(actor, request_id, reason=reason)


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE AUDIT TAB'S FILTER (image 29's All · Changes · Messages)
# ═══════════════════════════════════════════════════════════════════════════
AUDIT_KINDS: tuple[str, ...] = ("all", "changes", "messages")

#: The timeline rows that record a message to the applicant. Prefixes, because
#: the rows carry the occasion and the outcome after a colon
#: (`applicant_message:more_info:queued`, `acknowledgement:queued`).
MESSAGE_EVENT_PREFIXES: tuple[str, ...] = ("applicant_message:", "acknowledgement:")


def is_message_event(note_type: str | None) -> bool:
    return str(note_type or "").startswith(MESSAGE_EVENT_PREFIXES)


# ═══════════════════════════════════════════════════════════════════════════
# 3 · EDIT USES THE ADD FORM (J3)
# ═══════════════════════════════════════════════════════════════════════════
#: The form's customer block keys that are the REQUEST'S facts → its column.
#: `ssn` and `driving_licence` are written only when typed (the request serves
#: their last four and the form opens them empty, so empty means unchanged).
CUSTOMER_OWNED: dict[str, str] = {
    "full_name": "applicant_name",
    "email": "applicant_email",
    "phone": "applicant_phone",
    "dob": "date_of_birth",
    "ssn": "ssn",
    "driving_licence": "drivers_licence",
    "mailing_line1": "billing_line1_as_given",
    "mailing_line2": "billing_line2_as_given",
    "mailing_city": "billing_city_as_given",
    "mailing_state": "billing_state_as_given",
    "mailing_postal_code": "billing_postal_code_as_given",
}
#: Customer keys written through their own doors rather than `update_request`.
CUSTOMER_OWNED_ELSEWHERE: tuple[str, ...] = (
    "customer_kind",
    "mailing_same",
    "account_type",
    "account_subtype",
)
#: Top-level form keys that are the request's.
TOP_OWNED: tuple[str, ...] = ("opened_at", "unit_id", "services", "service_request_id")
#: `preferences.preferred_language` is the request's `preferred_language`.
PREFERENCE_OWNED: tuple[str, ...] = ("preferred_language",)

#: The two identifiers are never served back (BR-CUS-092).
_WRITE_ONLY = ("ssn", "driving_licence")

#: The form says `company`; a request says `business` (`APPLICANT_KINDS`).
_KIND_TO_REQUEST = {"person": "person", "company": "business"}
_KIND_TO_FORM = {"person": "person", "business": "company"}


def _iso(value: Any) -> str:
    return value.isoformat() if value is not None else ""


def _request_services(request: models.ServiceRequest) -> list[models.ServiceRequestService]:
    return list(
        models.ServiceRequestService.objects.filter(request=request)
        .select_related("service")
        .order_by("service__code")
    )


def _owned_values(request: models.ServiceRequest) -> dict[str, Any]:
    """The form's values that come FROM the request, keyed as the form keys them."""
    customer: dict[str, Any] = {
        form_key: ("" if form_key in _WRITE_ONLY else _iso_or_text(getattr(request, column)))
        for form_key, column in CUSTOMER_OWNED.items()
    }
    customer["customer_kind"] = _KIND_TO_FORM.get(request.applicant_kind or "", "")
    customer["mailing_same"] = bool(request.billing_address_same)
    customer["account_type"] = (
        request.account_type.code if request.account_type_id is not None else ""
    )
    # ⚠ **THE CODE, NEVER THE ID — `DEF-CUS-10258`.** Move-in's form keys a
    # sub-category by its CODE (`accountSubtypeName`, the list's option values),
    # so an id here opened the Customer step with no choice and printed the
    # row's id on Review. Completion resolves either (`_resolve_account_subtype`)
    # and the write-back below turns the code back into the row.
    customer["account_subtype"] = (
        request.account_subtype.code if request.account_subtype_id is not None else ""
    )
    return {
        "service_request_id": str(request.id),
        "unit_id": str(request.resolved_unit_id) if request.resolved_unit_id else "",
        "opened_at": _iso(request.requested_start),
        "services": [row.service.code for row in _request_services(request)],
        "customer": customer,
        "preferences": {"preferred_language": request.preferred_language or ""},
    }


def _subtype_id(request: models.ServiceRequest, value: str) -> str:
    """The form's sub-category (a CODE — `DEF-CUS-10258`; an id from a draft
    parked before that fix is still read) as the row's id, or `""`. A value
    naming no row of this tenant is passed through unchanged, so the category
    door refuses it by name rather than this quietly dropping it."""
    if value == "":
        return ""
    row = models.AccountSubtype.objects.filter(
        tenant_id=request.tenant_id, code__iexact=value
    ).first()
    return str(row.id) if row is not None else value


def _iso_or_text(value: Any) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _edit_park(request: models.ServiceRequest) -> Any:
    """The one park holding this request's parked rest, or None."""
    from apps.tenancy.models import WizardPark

    return (
        WizardPark.objects.filter(
            tenant_id=request.tenant_id,
            flow="move_in",
            subject_ref__service_request_id=str(request.id),
        )
        .order_by("-parked_at", "-id")
        .first()
    )


def _parked_rest(values: dict[str, Any]) -> dict[str, Any]:
    """`values` with every request-owned key taken out — what the park holds."""
    rest = {k: v for k, v in values.items() if k not in TOP_OWNED}
    customer = values.get("customer")
    if isinstance(customer, dict):
        left = {
            k: v
            for k, v in customer.items()
            if k not in CUSTOMER_OWNED and k not in CUSTOMER_OWNED_ELSEWHERE
        }
        rest["customer"] = left
    preferences = values.get("preferences")
    if isinstance(preferences, dict):
        rest["preferences"] = {k: v for k, v in preferences.items() if k not in PREFERENCE_OWNED}
    return rest


def _merge(parked: dict[str, Any], owned: dict[str, Any]) -> dict[str, Any]:
    """The park's rest with the request's own facts laid over it."""
    merged = dict(parked or {})
    for key, value in owned.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def form(request_id: Any) -> dict[str, Any]:
    """`GET /service-requests/{id}/move-in-form` — the Add form, filled in."""
    request = writes.request_row(request_id)
    park = _edit_park(request)
    return {
        "request": {
            "id": str(request.id),
            "request_no": request.request_no,
            "state": request.state,
            "status": request_status(request.state),
            "editable": rules.is_editable(request.state),
        },
        "park_id": str(park.id) if park is not None else None,
        "step": park.step if park is not None else 1,
        "values": _merge(park.values if park is not None else {}, _owned_values(request)),
    }


def _request_payload(values: dict[str, Any], request: models.ServiceRequest) -> dict[str, Any]:
    """The `update_request` body: only what the form carries, only what moved."""
    payload: dict[str, Any] = {}
    customer = values.get("customer") if isinstance(values.get("customer"), dict) else {}
    for form_key, column in CUSTOMER_OWNED.items():
        if form_key not in customer:
            continue
        value = customer[form_key]
        if form_key in _WRITE_ONLY:
            if str(value or "").strip():
                payload[column] = value
            continue
        if _iso_or_text(getattr(request, column)) != _iso_or_text(value):
            payload[column] = value if value != "" else None
    if "customer_kind" in customer:
        kind = _KIND_TO_REQUEST.get(str(customer["customer_kind"] or ""))
        if kind and kind != request.applicant_kind:
            payload["applicant_kind"] = kind
    if "mailing_same" in customer and bool(customer["mailing_same"]) != bool(
        request.billing_address_same
    ):
        payload["billing_address_same"] = bool(customer["mailing_same"])
    if "opened_at" in values and _iso(request.requested_start) != str(values["opened_at"] or ""):
        payload["requested_start"] = values["opened_at"] or None
    unit_id = str(values.get("unit_id") or "")
    if unit_id and unit_id != str(request.resolved_unit_id or ""):
        payload["picked_unit_id"] = unit_id
    preferences = values.get("preferences") if isinstance(values.get("preferences"), dict) else {}
    if "preferred_language" in preferences and (request.preferred_language or "") != str(
        preferences["preferred_language"] or ""
    ):
        payload["preferred_language"] = preferences["preferred_language"] or None
    return payload


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def save_form(actor: Any, request_id: Any, body: Any) -> dict[str, Any]:
    """`PUT /service-requests/{id}/move-in-form` — *Save draft & exit* (J3)."""
    from apps.tenancy import wizard_parks

    data = body if isinstance(body, dict) else {}
    values = data.get("values")
    if not isinstance(values, dict):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="shell.wizardPark.objectExpected",
            params={"field": "values"},
        )
    step = data.get("step", 1)
    with transaction.atomic():
        request = writes.request_row(request_id, lock=True)
        # The writers below re-check this; asking first means a decided request
        # is refused even when the form changed none of the request's fields.
        writes._refuse_unless_editable(request)
        payload = _request_payload(values, request)
        if payload:
            writes.update_request(actor, request.id, payload)
        customer = values.get("customer") if isinstance(values.get("customer"), dict) else {}
        account_type = str(customer.get("account_type") or "")
        current_type = request.account_type.code if request.account_type_id else ""
        subtype_id = _subtype_id(request, str(customer.get("account_subtype") or ""))
        if account_type and (
            account_type != current_type or subtype_id != str(request.account_subtype_id or "")
        ):
            writes.set_customer_category(
                actor,
                request.id,
                account_type_code=account_type,
                account_subtype_id=subtype_id or None,
            )
        if isinstance(values.get("services"), list):
            wanted = [str(code) for code in values["services"] if str(code or "").strip()]
            have = {row.service.code: row for row in _request_services(request)}
            if sorted(wanted) != sorted(have):
                # Each service keeps the start the clerk already gave it
                # (BR-CUS-1070) — a bare code here would erase it.
                writes.set_services(
                    actor,
                    request.id,
                    [
                        {
                            "code": code,
                            "requested_start": _iso(have[code].requested_start)
                            if code in have
                            else None,
                        }
                        for code in wanted
                    ],
                )
        rest = _parked_rest(values)
        park = _edit_park(request)
        if park is None:
            park = wizard_parks.park(
                actor,
                {
                    "flow": "move_in",
                    "step": step,
                    "values": rest,
                    "waiting_on": "",
                    "subject_label": request.request_no or "",
                    "subject_ref": {
                        "service_request_id": str(request.id),
                        "request_no": request.request_no,
                        "unit_id": str(request.resolved_unit_id or "") or None,
                    },
                },
            )
        else:
            park = wizard_parks.update_park(actor, park.id, {"step": step, "values": rest})
    return form(request_id)
