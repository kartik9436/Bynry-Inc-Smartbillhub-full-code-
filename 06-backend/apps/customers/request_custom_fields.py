# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W6 — the utility's own fields on the STAFF New
#           Request, read-only on Request detail, and COPIED to the real
#           records on approval with the R5 side-by-side pick.
# Rulings:  decision log 2026-10-02 *"TENANT CUSTOM FIELDS BECOME A COMPLETE
#           PLATFORM CAPABILITY …"* — Part 2 row 15 (*"Staff New Request ·
#           Request detail · Review / approval · On approval, copied to
#           Customer / Account / Premises"*), the line *"account / customer /
#           premises fields may also be placed on Staff New Request"*, gap 2
#           (*"Request detail always shows the request's copy of every intake
#           field"*) and gap 3 / R5 (RULED C: *"Existing: Metal · Requested:
#           Tile side by side; the EXISTING value is pre-selected; the clerk
#           picks; the choice is audited; a key with no existing value is
#           copied"*). W6's own judgment calls: decision log 2026-10-02
#           *"Custom fields on the staff service request (CR-161-BRC10 W6)"*.
# Rules:    BR-TEN-046/048/052 (as amended 2026-10-02) · BR-SHL-037 (the one
#           error envelope, `custom_data.<key>`) · CLAUDE.md hard rule 1
#           (tenant scoping — every read goes through a tenant-filtered door),
#           rule 7 (the copy writes `audit_log`), rule 8 (an answer is never an
#           address) · B1/B8 (premises is metering's — written through its door)
# Tests:    06-backend/tests/test_cr161_w6_request_custom_fields.py
# ───────────────────────────────────────────────────────
"""The service request's OWN COPY of the utility's fields, and the copy onto
the real records when the request is approved.

WHAT IS STORED, AND WHERE
-------------------------
`service_requests.custom_data` (`customers/0076`) holds ONE blob per record
type the request will feed — ``{"accounts": {…}, "customers": {…},
"premises": {…}}`` — each keyed by the field's immutable key (BR-TEN-049). It
is the REQUEST's copy: what the clerk typed on Staff New Request, kept on the
request whatever happens on approval, so the Request detail can always show
what was asked for (gap 2) and an audit reader can see what was proposed beside
what was kept.

There is no "Service request" record type of its own, deliberately: a field
that belonged only to the request would have nowhere to be copied, and the
ruling says the answers ARE copied to Customer / Account / Premises. So the
three record types' own fields are what a utility places on Staff New Request.

WHERE THE COPY GOES ON APPROVAL — ONLY TO A RECORD THAT EXISTS
---------------------------------------------------------------
Approving raises WORK and opens no account (`request_jobs`, *"No account opens,
no meter is fitted, nothing is energised"*). So at the moment of approval:

  * **premises** — the property the clerk picked off the register
    (`resolved_premises_id`). A brand-new address has no premises yet.
  * **customers** — the customer on file the request was linked to
    (`matched_customer`). A first-time applicant has no customer yet.
  * **accounts** — the account OCCUPYING the picked unit, and only when that
    account is held by the linked customer. The occupier of a unit somebody
    is moving INTO is the outgoing customer, and copying the applicant's
    answers onto their account would be writing one person's facts on
    another's record — so that is refused by construction, not by a check.

A record type with no target keeps its answers on the request, and the review
says so (`no_target`). They are carried LATER, by `carry_into_created` below,
at the moment the record is created from this request (`DEF-CUS-9211`).

AND INTO THE RECORDS CREATED LATER (`DEF-CUS-9211`, `2.467.5`)
--------------------------------------------------------------
Three doors create a record FROM a request after it is approved, and each calls
`carry_into_created` inside its own transaction:

  * the move-in that opens the applicant's account (`services._move_in`, the
    payload's `service_request_id`) — the new account and its holder;
  * an owner's account opened for the request (`create_master_account`,
    `create_build_owner_account`) — the account, its holder, and a master
    account's premises;
  * the New Connection commit of a build raised from the request
    (`metering.connections.commit_connection`, through metering's seam) — the
    build's premises.

The same rules as approval: only ACTIVE fields of that record type and THIS
utility (the request is read through a tenant-filtered door, so another
utility's id finds nothing), every value through the record type's own
validator, and **an answer already on the target is KEPT** — the R5 default,
because no clerk was shown a side-by-side for a record that did not exist yet.
A clerk's own pick at approval is never undone: whatever they chose is already
on that target and reads back as *same*. The account and customer are written
only when the account's holder IS the request's customer — the
`_account_target` refusal, one door later. An answer the validator now refuses
(an option removed since it was typed) stays on the request and is named in
the audit row; it never refuses the move-in or the build. One
`service_request.custom_fields_carried` audit row per carry that moved or kept
anything.

THE R5 PICK
-----------
A key the target already holds with a DIFFERENT value is a conflict: the review
shows both, the EXISTING value is pre-selected, and the clerk's choice travels
with the approval as ``{entity: {key: "existing" | "requested"}}``. Anything
not sent is ``existing`` — the pre-selection is the server's default too, so a
caller that sends nothing overwrites nothing. A key with no existing value is
copied. One `audit_log` row per approval names every key copied, every key
kept, and what the clerk picked.

A field switched off since the request was typed is NOT copied: its answer
stays on the request (BR-TEN-050 — old answers are kept, never deleted), and
the validator would refuse an inactive key on the target anyway.

NEVER A NUMBER IN A CALCULATION (BR-TEN-048)
--------------------------------------------
Nothing here reads money and nothing here returns a Decimal. The copy goes
through each record type's own validator (`tenancy.services.validate_custom_
data_for` via `seams.validate_custom_data`), which stores a number as the
string that was typed.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.customers import models, seams
from core import errors

#: The record types a service request may carry answers for (PO: *"account /
#: customer / premises fields may also be placed on Staff New Request"*), in
#: the order the review lists them.
INTAKE_ENTITIES: tuple[str, ...] = ("customers", "accounts", "premises")

#: The two screens, as `custom_fields.SLOTS` keys them.
SCREEN_NEW = "REQUEST_NEW"
SCREEN_DETAIL = "REQUEST_DETAIL"

PICK_EXISTING = "existing"
PICK_REQUESTED = "requested"
PICKS = (PICK_EXISTING, PICK_REQUESTED)

#: A row's state on the approval review.
COPY = "copy"  # the target holds nothing for this key — it is copied
CONFLICT = "conflict"  # the target holds a different value — the clerk picks
SAME = "same"  # the target already holds exactly this — nothing moves
NO_TARGET = "no_target"  # no record exists yet — the answer stays on the request


def _blank(value: Any) -> bool:
    return (
        value is None
        or value == ""
        or value == []
        or (isinstance(value, str) and not value.strip())
    )


def stored(request: models.ServiceRequest) -> dict[str, dict[str, Any]]:
    """The request's copy, one dict per intake record type — never `None`."""
    raw = request.custom_data if isinstance(request.custom_data, dict) else {}
    return {
        entity: dict(raw.get(entity) or {}) if isinstance(raw.get(entity), dict) else {}
        for entity in INTAKE_ENTITIES
    }


def clean(submitted: Any, *, existing: Any) -> dict[str, dict[str, Any]]:
    """Validate what a Staff New Request PATCH/POST sends and return the merged
    blob to store.

    Each record type's answers go through that type's own validator with the
    screen the clerk typed them on (`REQUEST_NEW`), so a required field binds
    here only when it is placed Input on Staff New Request (*"Required means
    required only where it's typed in"*), and only the record types the payload
    names are touched — an edit on step 2 does not re-judge step 1.

    A record type outside the three is refused by NAME, never dropped.
    """
    if not isinstance(submitted, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="settings.customFields.values_not_object"
        )
    unknown = sorted(set(submitted) - set(INTAKE_ENTITIES))
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.fieldNotAccepted",
            params={"field": f"custom_data.{unknown[0]}"},
        )
    held = existing if isinstance(existing, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for entity in INTAKE_ENTITIES:
        before = dict(held.get(entity) or {}) if isinstance(held.get(entity), dict) else {}
        if entity not in submitted:
            if before:
                out[entity] = before
            continue
        merged = seams.validate_custom_data(
            entity, submitted.get(entity), screen=SCREEN_NEW, existing=before
        )
        if merged:
            out[entity] = merged
    return out


#: `CR-161-BRC10` W7 — the customer portal's new-service form, as
#: `custom_fields.SLOTS` keys it.
SCREEN_PORTAL = "PORTAL_NEW_SERVICE"


def clean_from_portal(submitted: Any) -> dict[str, dict[str, Any]]:
    """The answers a portal application carries (W7), judged at this door again.

    The portal already judged them field by field as they were typed; this is
    the owning module refusing to take a stranger's word for it. Each record
    type's keys must be fields the utility asks ON THE PORTAL (*Ask the
    customer*) — a key that exists but is kept internal is refused exactly as
    an unknown key is — and each value goes through that type's own validator.
    Nothing is REQUIRED here (`screen=None`): Send already held the form until
    every required question was answered, and this door is not a screen.
    """
    if submitted is None or submitted == {}:
        return {}
    if not isinstance(submitted, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="settings.customFields.values_not_object"
        )
    unknown = sorted(set(submitted) - set(INTAKE_ENTITIES))
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.fieldNotAccepted",
            params={"field": f"custom_data.{unknown[0]}"},
        )
    out: dict[str, dict[str, Any]] = {}
    for entity in INTAKE_ENTITIES:
        answers = submitted.get(entity)
        if not answers:
            continue
        if not isinstance(answers, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="settings.customFields.values_not_object"
            )
        asked = {
            d["key"]
            for d in seams.custom_field_definitions(entity)
            if (d.get("placement") or {}).get(SCREEN_PORTAL) == "input"
        }
        internal = sorted(set(answers) - asked)
        if internal:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="customFields.invalid",
                field_errors=[
                    {
                        "field": f"custom_data.{key}",
                        "code": errors.VAL_UNKNOWN_LOOKUP,
                        "message_key": "customFields.unknown_key",
                        "params": {"key": key},
                    }
                    for key in internal
                ],
            )
        cleaned = seams.validate_custom_data(entity, answers, screen=None)
        if cleaned:
            out[entity] = cleaned
    return out


def refuse_unless_complete(request: models.ServiceRequest) -> None:
    """At SUBMIT: every field placed Input AND required on Staff New Request
    must hold an answer. A draft may be saved without one (a draft is unfinished
    by definition); the submit is where *required* means required.

    Asked of the same validator, with nothing submitted and the request's copy
    as the stored blob, so this cannot become a second copy of the rule.
    """
    copy = stored(request)
    for entity in INTAKE_ENTITIES:
        seams.validate_custom_data(entity, {}, screen=SCREEN_NEW, existing=copy[entity])


# ── where the copy goes ─────────────────────────────────────────────────────
def _account_target(request: models.ServiceRequest) -> dict[str, Any] | None:
    """The account occupying the picked unit — only when the linked customer
    holds it. See the module docstring for why the occupier alone is never
    enough."""
    from apps.customers import selectors
    from apps.customers import service_request_service as writes

    if not request.resolved_unit_id or not request.matched_customer_id:
        return None
    occupying = selectors.active_account_for_unit(request.resolved_unit_id)
    if occupying is None:
        return None
    if str(occupying["id"]) not in set(writes.customer_account_ids(request.matched_customer_id)):
        return None
    return {"id": str(occupying["id"]), "label": occupying["account_no"]}


def targets(request: models.ServiceRequest) -> dict[str, dict[str, Any] | None]:
    """The real record each intake type would be copied to today, or `None`.
    `label` is a NUMBER a clerk reads (B14 rule 31), never an id."""
    out: dict[str, dict[str, Any] | None] = {"customers": None, "accounts": None, "premises": None}
    if request.matched_customer_id:
        customer = (
            models.Customer.objects.filter(
                tenant_id=request.tenant_id, pk=request.matched_customer_id
            )
            .only("id", "customer_no", "display_name")
            .first()
        )
        if customer is not None:
            out["customers"] = {
                "id": str(customer.id),
                "label": customer.customer_no or customer.display_name,
            }
    out["accounts"] = _account_target(request)
    if request.resolved_premises_id:
        answers = seams.premises_custom_answers(request.resolved_premises_id)
        if answers is not None:
            out["premises"] = {
                "id": str(request.resolved_premises_id),
                "label": answers["premise_no"],
            }
    return out


def _target_answers(entity: str, target: dict[str, Any]) -> dict[str, Any]:
    if entity == "premises":
        answers = seams.premises_custom_answers(target["id"])
        return dict((answers or {}).get("custom_data") or {})
    model = models.Customer if entity == "customers" else models.Account
    row = model.objects.filter(pk=target["id"]).only("custom_data").first()
    return dict(row.custom_data or {}) if row is not None else {}


def copy_preview(request: models.ServiceRequest) -> list[dict[str, Any]]:
    """The approval review's *Your own fields* block, as data.

    One entry per intake record type the request holds answers for, each with
    its target (or `None`) and one row per ANSWERED, ACTIVE field:
    ``{key, label, data_type, requested, existing, state, default_pick}``.
    `label` and the two values are the tenant's own data and travel as
    themselves; every word around them is the catalogue's.
    """
    copy = stored(request)
    where = targets(request)
    out: list[dict[str, Any]] = []
    for entity in INTAKE_ENTITIES:
        answers = {k: v for k, v in copy[entity].items() if not _blank(v)}
        if not answers:
            continue
        definitions = {d["key"]: d for d in seams.custom_field_definitions(entity)}
        target = where[entity]
        held = _target_answers(entity, target) if target is not None else {}
        rows = []
        for key, requested in answers.items():
            definition = definitions.get(key)
            if definition is None:
                continue  # switched off since — kept on the request, not copied
            existing = held.get(key)
            if target is None:
                state = NO_TARGET
            elif _blank(existing):
                state = COPY
            elif existing == requested:
                state = SAME
            else:
                state = CONFLICT
            rows.append(
                {
                    "key": key,
                    "label": definition["label"],
                    "data_type": definition["data_type"],
                    "requested": requested,
                    "existing": None if _blank(existing) else existing,
                    "state": state,
                    # R5: the EXISTING value is pre-selected.
                    "default_pick": PICK_EXISTING if state == CONFLICT else None,
                }
            )
        if rows:
            out.append(
                {
                    "entity": entity,
                    "target": None if target is None else {"label": target["label"]},
                    "rows": rows,
                }
            )
    return out


def _clean_picks(raw: Any) -> dict[str, dict[str, str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.serviceRequest.customFieldPickInvalid",
            params={"field": "custom_field_picks"},
        )
    out: dict[str, dict[str, str]] = {}
    for entity, keys in raw.items():
        if entity not in INTAKE_ENTITIES or not isinstance(keys, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="customers.serviceRequest.customFieldPickInvalid",
                params={"field": f"custom_field_picks.{entity}"},
            )
        for key, pick in keys.items():
            if pick not in PICKS:
                raise errors.ValidationError(
                    errors.VAL_UNKNOWN_LOOKUP,
                    message_key="customers.serviceRequest.customFieldPickInvalid",
                    params={"field": f"custom_field_picks.{entity}.{key}"},
                )
        out[entity] = {str(k): str(v) for k, v in keys.items()}
    return out


def apply_on_approval(actor: Any, request: models.ServiceRequest, picks: Any) -> dict[str, Any]:
    """Copy the request's answers onto the records that exist, honouring the
    clerk's picks; called by `approve_and_raise` INSIDE its transaction, so a
    refused copy leaves the request unapproved and nothing half-written.

    Returns what moved, which is also the audit row's `after`.
    """
    from apps.customers import service_request_service as writes

    chosen = _clean_picks(picks)
    preview = copy_preview(request)
    where = targets(request)
    copied: dict[str, dict[str, Any]] = {}
    kept: dict[str, dict[str, Any]] = {}
    waiting: dict[str, list[str]] = {}
    before_all: dict[str, dict[str, Any]] = {}
    with transaction.atomic():
        for block in preview:
            entity = block["entity"]
            target = where[entity]
            if target is None:
                waiting[entity] = [row["key"] for row in block["rows"]]
                continue
            changes: dict[str, Any] = {}
            for row in block["rows"]:
                if row["state"] == COPY:
                    changes[row["key"]] = row["requested"]
                elif row["state"] == CONFLICT:
                    pick = chosen.get(entity, {}).get(row["key"], PICK_EXISTING)
                    if pick == PICK_REQUESTED:
                        changes[row["key"]] = row["requested"]
                    else:
                        kept.setdefault(entity, {})[row["key"]] = row["existing"]
            if not changes:
                continue
            held = _target_answers(entity, target)
            before_all[entity] = {k: held.get(k) for k in changes}
            if entity == "premises":
                seams.copy_premises_custom_answers(actor, target["id"], changes)
            else:
                model = models.Customer if entity == "customers" else models.Account
                row = model.objects.select_for_update().get(pk=target["id"])
                merged = seams.validate_custom_data(
                    entity, changes, screen=None, existing=row.custom_data or {}
                )
                row.custom_data = merged
                row.save(update_fields=["custom_data", "updated_at"])
            copied[entity] = {"target": target["label"], "values": changes}
        summary = {"copied": copied, "kept": kept, "waiting": waiting, "picks": chosen}
        if copied or kept or waiting:
            writes._audit(
                actor,
                "service_request.custom_fields_copied",
                request.id,
                before=before_all,
                after=summary,
            )
    return summary


# ── DEF-CUS-9211 · into the records a later step creates from this request ───
CARRIED_ACTION = "service_request.custom_fields_carried"


def _holder_of(tenant_id: Any, account_id: Any) -> Any:
    return (
        models.CustomerAccount.objects.filter(tenant_id=tenant_id, account_id=account_id)
        .values_list("customer_id", flat=True)
        .first()
    )


def carry_into_created(
    actor: Any,
    request_id: Any,
    *,
    account_id: Any = None,
    premises_id: Any = None,
) -> dict[str, Any] | None:
    """Copy the request's answers onto the record(s) a later door has just
    created from it — see the module docstring's *AND INTO THE RECORDS CREATED
    LATER*. Called INSIDE the creating door's transaction.

    Returns the audit row's `after`, or `None` when nothing was there to move
    (no request, another utility's request, no answers, no target).
    """
    if not request_id:
        return None
    from core import tenancy as core_tenancy

    request = models.ServiceRequest.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=request_id
    ).first()
    if request is None:
        return None
    copy = stored(request)
    if not any(copy.values()):
        return None
    where: dict[str, dict[str, Any] | None] = {e: None for e in INTAKE_ENTITIES}
    if account_id:
        account = (
            models.Account.objects.filter(tenant_id=request.tenant_id, pk=account_id)
            .only("id", "account_no", "premises_id", "unit_id")
            .first()
        )
        holder = _holder_of(request.tenant_id, account_id) if account is not None else None
        # The applicant's facts go on the applicant's records only.
        if holder is not None and str(holder) == str(request.matched_customer_id or ""):
            where["accounts"] = {"id": str(account.id), "label": account.account_no}
            customer = (
                models.Customer.objects.filter(tenant_id=request.tenant_id, pk=holder)
                .only("id", "customer_no", "display_name")
                .first()
            )
            if customer is not None:
                where["customers"] = {
                    "id": str(customer.id),
                    "label": customer.customer_no or customer.display_name,
                }
            if not premises_id:
                premises_id = account.premises_id or (
                    getattr(seams.unit_row(account.unit_id), "premises_id", None)
                    if account.unit_id
                    else None
                )
    if premises_id:
        answers = seams.premises_custom_answers(premises_id)
        if answers is not None:
            where["premises"] = {"id": str(premises_id), "label": answers["premise_no"]}

    copied: dict[str, dict[str, Any]] = {}
    kept: dict[str, dict[str, Any]] = {}
    refused: dict[str, list[str]] = {}
    before_all: dict[str, dict[str, Any]] = {}
    for entity in INTAKE_ENTITIES:
        target = where[entity]
        answers = {k: v for k, v in copy[entity].items() if not _blank(v)}
        if target is None or not answers:
            continue
        active = {d["key"] for d in seams.custom_field_definitions(entity)}
        held = _target_answers(entity, target)
        changes: dict[str, Any] = {}
        for key, requested in answers.items():
            if key not in active:
                continue  # switched off since — stays on the request (BR-TEN-050)
            existing = held.get(key)
            if _blank(existing):
                changes[key] = requested
            elif existing != requested:
                kept.setdefault(entity, {})[key] = existing
        if not changes:
            continue
        try:
            # A SAVEPOINT, so a refusal here can never poison the creating
            # door's transaction on PostgreSQL (hard-won law 14).
            with transaction.atomic():
                if entity == "premises":
                    seams.copy_premises_custom_answers(actor, target["id"], changes)
                else:
                    model = models.Customer if entity == "customers" else models.Account
                    row = model.objects.select_for_update().get(pk=target["id"])
                    row.custom_data = seams.validate_custom_data(
                        entity, changes, screen=None, existing=row.custom_data or {}
                    )
                    row.save(update_fields=["custom_data", "updated_at"])
        except errors.ValidationError:
            refused[entity] = sorted(changes)
            continue
        before_all[entity] = {k: held.get(k) for k in changes}
        copied[entity] = {"target": target["label"], "values": changes}
    if not (copied or kept or refused):
        return None
    summary = {"copied": copied, "kept": kept, "refused": refused}
    from apps.customers import service_request_service as writes

    writes._audit(actor, CARRIED_ACTION, request.id, before=before_all, after=summary)
    return summary
