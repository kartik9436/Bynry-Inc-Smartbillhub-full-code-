# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-017 (the service-request register)
#           Screens: blueprint entry 06 capture step 6 (p080–p081), the
#           `What goes out to the applicant` block and `Choosing a template`
# Rules:    BR-CUS-1076 (this block's rule) · BR-CUS-079 (the acknowledgement,
#           which is row one and already fires) · BR-CUS-1075 (the refusal
#           letter, which is row five on the refuse path) · BR-BIL-025 (three
#           axes, two fallbacks) · BR-BIL-027 (nothing renders from a draft) ·
#           BR-NOT-005 (queue only) · BR-NOT-013 (no adapter on any channel) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency) · rule 7
#           (every money action writes audit_log — and this one writes it for
#           every decision too) · B14 rules 31, 33, 37, 42
# Change:   CR-094-BRC01 lane J
# Tests:    06-backend/tests/test_cr094_applicant_messages_block.py
# Impacts:  apps/customers/applicant_message_models.py (the table) ·
#           apps/customers/notifications_seam.py (`queue_request_approved`,
#           `applicant_templates`) · apps/customers/service_request_service.py
#           (`approve_and_raise` and `refuse_request` call `on_decision`) ·
#           apps/customers/service_request_api.py (two routes) ·
#           apps/notifications/service_request_events.py (the writer and the
#           picker's read, both resolved BY NAME)
# ───────────────────────────────────────────────────────
"""The five messages a captured request may send, and the one that goes on a decision.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  a clerk at the counter says which messages this application will send   ║
║  and picks the wording, and when somebody later approves or refuses it   ║
║  the applicant is told — which, until this file, they never were.        ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠ **THE PO ASKED WHETHER THIS WORKED AND THE ANSWER WAS NO.** Verbatim,
2026-09-15: *"at the time of approval we are also linking notification and
templates to the modal - are you ensuring it will work?"* Before this file there
was no table holding which messages a request would send, no template choice on
a request at all, and **approving fired nothing** — a request could be approved
and the person who applied for it heard nothing, ever.

Blueprint entry 06, capture step 6, read AS IMAGES (p080 and p081, scale 2 and
scale 4 — B14 rule 42).

────────────────────────────────────────────────────────────────────────────
THE FIVE OCCASIONS, AND WHY `WHEN` IS THE COLUMN THAT MATTERS
────────────────────────────────────────────────────────────────────────────
The drawing's `WHEN` column carries THREE values and they are three different
kinds of thing, which is why they are modelled rather than displayed:

  * `on_submit` — it goes when the request is submitted;
  * `already_handed_over` — **it is not queued at all.** p081, read as an image:
    *"The receipt is already in their hand. It was written at the counter when
    the money was taken, so this row records what was given rather than queueing
    a second copy."* A tick here is a RECORD of a thing that happened, and a
    product that emailed a second copy would be telling somebody about a receipt
    they are holding.
  * `on_approve_or_refuse` — the decision, and the one this lane wires.

**A row whose moment has passed must not fire again.** `fired_at` is what
carries that, and it is stamped on the receipt row at capture because its moment
is behind it by definition.

────────────────────────────────────────────────────────────────────────────
THE DECISION ROW IS ONE OCCASION WITH TWO CLASSES, AND THE OUTCOME PICKS
────────────────────────────────────────────────────────────────────────────
The drawing draws ONE row — *"The decision, when it is made"*, template
*"Request decided v4"* — and one class cannot serve it, for exactly the reason
lane C split the acknowledgement in two on the same day: **a template body has
no conditional in it.** *"We are going ahead with your request"* and *"We are
not able to go ahead"* are two letters, not one letter with a word swapped, and
the refusal class additionally makes the clerk's own sentence mandatory content
while an approval has no such box drawn anywhere.

So the occasion offers two classes and the OUTCOME pins one. What the clerk
picked is kept on `template_code`; what actually rendered is stamped on
`fired_template_code`, and where those differ the row says so rather than
quietly rewriting the clerk's choice.

────────────────────────────────────────────────────────────────────────────
⚠ THE TICK IS A STANDING INSTRUCTION AND A CLERK IN FRONT OF THE REQUEST
  OUTRANKS IT — WHICH IS WHY REFUSING DOES NOT QUEUE A SECOND LETTER
────────────────────────────────────────────────────────────────────────────
Refusing already queues a letter (`BR-CUS-1075`, lane C): the Refuse dialog
carries a `What to tell them` box captioned *"Goes into the refusal letter."*,
and what the clerk types there IS the letter. That letter **is** the drawn row
five on the refuse path — *"The decision, when it is made"* — and queueing
another one would send an applicant two letters about one decision, one of them
generic.

So the two terminal paths are not symmetrical, and the asymmetry is the rule:

  * **Refusing** — a clerk is standing at the request typing the letter NOW.
    That present act outranks a tick set at capture, exactly as
    `queue_account_message` argues for a clerk pressing a button: a rule that
    silently swallowed it would leave them believing they had written to
    somebody when nothing was written. The letter goes; this module RECORDS it
    against the decision row, carrying the same queue row id.
  * **Approving** — nobody is typing anything, there is no dialog box, and until
    this file nothing at all went out. The tick decides, and it is the only
    instruction there is.

**Asking for more fires nothing here.** It is not a decision — the request stays
open — and it has its own letter already. That is the same posture the PO ruled
for the money on 2026-09-15: ask-for-more changes nothing.

────────────────────────────────────────────────────────────────────────────
THE PICKER'S FOUR RULES, WHICH ARE p081'S AND NOT THIS FILE'S INVENTIONS
────────────────────────────────────────────────────────────────────────────
Read as an image above the page break, each one a sentence:

1. *"A template resolves on three axes and falls back on two."* — that is
   `notifications.template_service.resolve` and `BR-BIL-025`, ALREADY BUILT.
   This module verifies it rather than reimplementing it: the pick travels as
   `override_template_id`, which is the same rule's own word for an explicit
   variant.
2. *"The draft version is listed and cannot be picked."* — a draft row is
   SERVED, with `pickable: false` and a reason, and refused if it is picked
   anyway. Filtering it out is what the rule explicitly rejects: *"Hiding it
   sends a clerk looking for something they can see exists."*
3. *"A text never replaces a posted notice."* — an occasion that must be in
   writing refuses a pick that cannot be read as writing. Today that is a
   variant a tenant has published on the SMS channel.
4. *"The receipt is already in their hand."* — see `WHEN`, above.

────────────────────────────────────────────────────────────────────────────
NOTHING IS SENT, AND NO SENTENCE PUBLISHED FROM HERE MAY SAY OTHERWISE
────────────────────────────────────────────────────────────────────────────
`BR-NOT-013` — no provider adapter exists on any channel, print included — so
the most this product can honestly claim is QUEUED: a row on
`outbound_messages`, addressed to the applicant's own email, that nothing picks
up. The drawing says so in its own last line and `nothing_is_sent()` publishes
it to every surface so no screen has to remember it (hard-won law 1: a comment
claiming a guarantee is not the guarantee, and here it would be a promise to a
customer).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers import models, notifications_seam, seams
from apps.customers.applicant_message_models import ServiceRequestMessage
from core import errors
from core import tenancy as core_tenancy

#: Stamped on a row the moment it fires, and the same three words the
#: acknowledgement already uses, so one screen reads one vocabulary.
STATE_QUEUED = "queued"
STATE_NOT_SENT = "not_sent"
STATE_ALREADY_HANDED_OVER = "already_handed_over"

#: The three moments of the drawn `WHEN` column.
WHEN_ON_SUBMIT = "on_submit"
WHEN_ALREADY_HANDED_OVER = "already_handed_over"
WHEN_ON_DECISION = "on_approve_or_refuse"

#: The classes `notifications` publishes for an applicant. Named here as
#: STRINGS rather than imported, because customers may not import notifications
#: (B1 · B2 §2) — the seam resolves the module by name and this file resolves
#: the class codes the same way.
CLASS_ACKNOWLEDGEMENT = "service_request_acknowledgement"
CLASS_ACKNOWLEDGEMENT_FEE = "service_request_acknowledgement_fee"
CLASS_APPROVED = "service_request_approved"
CLASS_REFUSED = "service_request_refused"

#: Why a row did not fire, when the act itself was fine. Codes, never
#: sentences — B14 rule 32 keeps our vocabulary off a clerk's screen, so each
#: one is rendered through the front end's own catalogue.
REASON_NOT_TICKED = "the_clerk_did_not_ask_for_this_one"
REASON_NO_WORDING = "this_product_has_no_wording_for_this_one_yet"
REASON_HANDED_OVER = "the_receipt_was_handed_over_at_the_counter"
REASON_NO_ADAPTER = "no_delivery_adapter_in_this_product"
REASON_ALREADY_FIRED = "this_one_had_already_gone"


@dataclass(frozen=True)
class Occasion:
    """One drawn row of `What goes out to the applicant`.

    Everything the drawing shows in a column that is NOT a choice lives here —
    the moment it fires, whether it is ticked to begin with, and which classes
    may render it. A row on `service_request_messages` stores only the choices.
    """

    code: str
    when: str
    #: The drawn tick state. Three of five are ticked (p080, read as an image).
    send_by_default: bool
    #: False for the counter receipt alone: its moment is behind it.
    queues: bool
    #: p081 rule *"A text never replaces a posted notice."*
    must_be_in_writing: bool
    #: The classes that may render it. EMPTY means this product has no wording
    #: for this occasion yet, which the payload says out loud rather than
    #: offering an empty picker.
    classes: tuple[str, ...]
    #: Decision occasions only: which class each terminal outcome pins.
    class_by_outcome: dict[str, str] | None = None


#: ⚠ **THE ORDER IS THE DRAWING'S AND IS PART OF THE CONTRACT.** Two clerks
#: reading the same block must see the same five rows in the same order, and a
#: screen that sorted them itself would be a second opinion about a picture.
#:
#: ⚠ **THE DRAWN LABELS ARE NOT HERE AND MUST NOT BE.** p080 reads *"A receipt
#: for the $25.00 taken"* and *"That $105.00 is still owed"*; those figures are
#: illustrations of one request (B14 rule 37) and the words are screen copy,
#: which belongs in the eleven catalogues in each language's own vocabulary
#: (B14 rule 35) and never in a server constant.
OCCASIONS: tuple[Occasion, ...] = (
    Occasion(
        code="request_received",
        when=WHEN_ON_SUBMIT,
        send_by_default=True,
        queues=True,
        must_be_in_writing=False,
        classes=(CLASS_ACKNOWLEDGEMENT, CLASS_ACKNOWLEDGEMENT_FEE),
    ),
    Occasion(
        code="documents_outstanding",
        when=WHEN_ON_SUBMIT,
        send_by_default=True,
        queues=True,
        must_be_in_writing=False,
        #: ⚠ **NO WORDING EXISTS AND THE ROW SAYS SO** (`DEF-CUS-5417`). The
        #: drawing calls this the row that *"makes this submission useful"*, and
        #: it is drawn TICKED — so the default stands as drawn and the payload
        #: carries `available: false` beside it. A tick over nothing is
        #: hard-won law 2's mirror, a live-looking control with a dead path
        #: behind it, and the only defence against it is saying the number out
        #: loud: TWO of five occasions have no class.
        classes=(),
    ),
    Occasion(
        code="counter_receipt",
        when=WHEN_ALREADY_HANDED_OVER,
        send_by_default=True,
        #: ⚠ **THE ONE ROW THAT NEVER QUEUES.** p081: *"The receipt is already
        #: in their hand."*
        queues=False,
        must_be_in_writing=False,
        classes=(),
    ),
    Occasion(
        code="balance_outstanding",
        when=WHEN_ON_SUBMIT,
        #: Drawn UNTICKED, and drawn with `— none chosen` in its template
        #: column, which is what this product still has.
        send_by_default=True,
        queues=True,
        must_be_in_writing=False,
        classes=(),
    ),
    Occasion(
        code="decision",
        when=WHEN_ON_DECISION,
        send_by_default=True,
        queues=True,
        #: p081: *"A text never replaces a posted notice. Where a decision has
        #: to be put in writing, the SMS on the last row is a courtesy alongside
        #: it and never instead of it."*
        must_be_in_writing=True,
        classes=(CLASS_APPROVED, CLASS_REFUSED),
        class_by_outcome={"approved": CLASS_APPROVED, "refused": CLASS_REFUSED},
    ),
)

OCCASION_CODES: tuple[str, ...] = tuple(one.code for one in OCCASIONS)
DECISION = "decision"

#: The two decisions row five fires on. ⚠ **THESE ARE THE REQUEST'S STATES —
#: `ServiceRequest.APPROVED` and `.REFUSED` — AND NOT ITS `outcome`.** The word
#: `outcome` is already taken on this table for what a request BECOMES (p081:
#: *"the five job outcomes are exactly the other five flows"*), so a parameter
#: called `outcome` carrying `approved` here would be two vocabularies sharing
#: one name on a customer-facing path.
DECISION_APPROVED = "approved"
DECISION_REFUSED = "refused"

_BY_CODE: dict[str, Occasion] = {one.code: one for one in OCCASIONS}

BR_REF = "BR-CUS-1076"


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def occasion(code: str) -> Occasion:
    """The occasion, or a refusal naming what this product actually has."""
    found = _BY_CODE.get(code)
    if found is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.messageOccasionUnknown",
            params={"value": str(code)},
        )
    return found


def nothing_is_sent() -> dict[str, Any]:
    """The drawing's own last line, published so no screen has to remember it.

    ⚠ **THIS IS A FACT ABOUT THE PRODUCT AND NOT A LABEL.** `BR-NOT-013`: no
    provider adapter exists on any channel, print included. A surface built on
    this block must not say a message *reached* anybody — the truest word this
    product has is QUEUED, and `delivers` is what says so. The SENTENCE a clerk
    reads is the front end's, in its own eleven catalogues (B14 rule 35); what
    travels here is the fact it renders.
    """
    return {
        "queued_only": True,
        "delivers": False,
        "br_ref": "BR-NOT-013",
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE BLOCK — five rows, stored where a clerk changed one and drawn otherwise
# ═══════════════════════════════════════════════════════════════════════════
def block_for(request_id: Any) -> dict[str, Any]:
    """The five drawn rows for one request, in the drawing's order.

    ⚠ **A READ THAT WROTE WOULD BE THE WRONG SHAPE HERE.** The five defaults are
    a CONSTANT, so a request nobody has touched needs no rows at all and the
    block is the constant read back. What is stored is a clerk's DEPARTURE from
    the drawing — which also means every request that existed before this table
    did answers this read correctly, rather than answering it empty.
    """
    stored = {
        row.occasion: row
        # ⚠ **TENANT-SCOPED EXPLICITLY AND NOT LEFT TO RLS** (hard rule 1). RLS
        # FORCE would catch this on PostgreSQL and **the test database is
        # SQLite, where the guarantee does not exist at all** — so a queryset
        # leaning on the policy would pass the entire suite and be the one thing
        # nothing here can check. That is hard-won law 14's shape, one rule over.
        for row in ServiceRequestMessage.objects.filter(
            tenant_id=_tenant_id(), request_id=request_id
        )
    }
    return {
        "rows": [_row_view(one, stored.get(one.code)) for one in OCCASIONS],
        "delivery": nothing_is_sent(),
    }


def _row_view(spec: Occasion, row: Any) -> dict[str, Any]:
    """One row as a screen needs it: the choices, the moment, and the truth."""
    return {
        "occasion": spec.code,
        "when": spec.when,
        "send": spec.send_by_default if row is None else bool(row.send),
        "send_is_default": row is None,
        "template_code": None if row is None else row.template_code,
        #: B14 rule 31 — a database id is never the visible value of a field.
        #: It travels so the picker can show which radio is filled and is not
        #: rendered as text anywhere.
        "template_id": None if row is None else (str(row.template_id) if row.template_id else None),
        "template_version_seen": None if row is None else row.template_version_seen,
        #: ⚠ **WHETHER THIS ROW CAN DO WHAT IT SAYS**, said out loud per row.
        #: Two of the five have no class at all, and a tick over one of those is
        #: a promise nobody is keeping unless the screen can see it.
        #:
        #: ⚠ **NOT SIMPLY *HAS A TEMPLATE*, AND THE COUNTER RECEIPT IS WHY.** It
        #: has no class either and needs none: its promise was kept at the
        #: counter before the clerk reached this screen (p081, *"The receipt is
        #: already in their hand"*). Reporting it as unavailable would tell a
        #: screen to warn about the one row that is definitely fine.
        "available": bool(spec.classes) or not spec.queues,
        "queues": spec.queues,
        "must_be_in_writing": spec.must_be_in_writing,
        "classes": list(spec.classes),
        "fired_at": None if row is None or not row.fired_at else row.fired_at.isoformat(),
        "fired_state": None if row is None else row.fired_state,
        "fired_reason": None if row is None else row.fired_reason,
        #: The queue row this message is, when there is one. ⚠ **A DATABASE ID
        #: AND NEVER A VISIBLE VALUE** (B14 rule 31): it travels so that *"was
        #: this actually written, and which row is it"* can be answered from the
        #: request rather than inferred from a 200 — hard-won law 1 applied to a
        #: promise made to a customer.
        "fired_ref": None if row is None else row.fired_ref,
        "fired_template_code": None if row is None else row.fired_template_code,
        "sent": False,
    }


def save_block(actor: Any, request_id: Any, rows: Any) -> dict[str, Any]:
    """Store what the clerk ticked and picked. Every row, or a named refusal.

    ⚠ **THE THREE GUARDS ARE p081'S RULES AND EACH ONE REFUSES BY NAME**, so a
    clerk reads a sentence rather than meeting silence (`G32`'s lesson: a
    refusal with no resolvable message key reaches a clerk as nothing at all).
    """
    from apps.customers import service_request_service as writes

    if not isinstance(rows, list):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.messageRowsList",
            params={"value": str(type(rows).__name__)},
        )
    request = writes.request_row(request_id)
    cleaned = [_clean_row(one) for one in rows]
    with transaction.atomic():
        for spec, choice in cleaned:
            _upsert(request, spec, choice)
        writes._audit(
            actor,
            "service_request.applicant_messages.saved",
            request.id,
            after={
                "rows": [
                    {
                        "occasion": spec.code,
                        "send": choice["send"],
                        "template_code": choice["template_code"],
                    }
                    for spec, choice in cleaned
                ]
            },
        )
    return block_for(request.id)


def _clean_row(raw: Any) -> tuple[Occasion, dict[str, Any]]:
    """One incoming row, validated against the drawing and against the registry."""
    if not isinstance(raw, dict):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.messageRowsList",
            params={"value": str(type(raw).__name__)},
        )
    spec = occasion(str(raw.get("occasion") or ""))
    code = (raw.get("template_code") or "").strip() or None
    template_id = raw.get("template_id") or None
    if code is not None and code not in spec.classes:
        # ⚠ A CLASS THIS OCCASION DOES NOT SEND. Refused rather than stored,
        # because a request carrying a template nothing will ever pin is a
        # choice a clerk believes they made.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.messageTemplateNotForOccasion",
            params={"value": code, "occasion": spec.code},
        )
    if template_id is not None:
        _refuse_unpickable(spec, str(template_id))
    return spec, {
        "send": bool(raw.get("send", spec.send_by_default)),
        "template_code": code,
        "template_id": str(template_id) if template_id else None,
        "template_version_seen": _version_seen(raw.get("template_version_seen")),
    }


def _version_seen(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.messageTemplateVersion",
            params={"value": str(value)},
        ) from None


def _refuse_unpickable(spec: Occasion, template_id: str) -> None:
    """p081's second and third rules, against the tenant's REAL registry.

    A draft is listed and cannot be picked; and where a decision has to be put
    in writing, a variant published on a channel that is not writing cannot
    carry it. Both are read from what notifications actually publishes, so
    neither is a rule this file asserts about itself.
    """
    offered = {
        str(one["template_id"]): one
        for one in notifications_seam.applicant_templates(codes=spec.classes)
    }
    row = offered.get(str(template_id))
    if row is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.messageTemplateUnknown",
            params={"occasion": spec.code},
        )
    if not row.get("pickable"):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.messageTemplateNotPickable",
            params={"reason": str(row.get("not_pickable_reason") or ""), "occasion": spec.code},
        )
    if spec.must_be_in_writing and not row.get("is_writing"):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.messageTemplateNotInWriting",
            params={"channel": str(row.get("channel") or ""), "occasion": spec.code},
        )


def _upsert(request: Any, spec: Occasion, choice: dict[str, Any]) -> Any:
    """Write one row, and stamp the receipt row's moment as already past.

    ⚠ **A ROW THAT HAS FIRED IS NOT REWRITTEN BY A LATER SAVE.** Its choices are
    kept as evidence of what was chosen when it went; changing the template on a
    letter already on the queue would make the record disagree with the letter.
    """
    row, _ = ServiceRequestMessage.objects.get_or_create(
        tenant_id=request.tenant_id,
        request_id=request.id,
        occasion=spec.code,
        defaults={"send": spec.send_by_default},
    )
    if row.fired_at is not None:
        return row
    row.send = choice["send"]
    row.template_code = choice["template_code"]
    row.template_id = choice["template_id"]
    row.template_version_seen = choice["template_version_seen"]
    if not spec.queues:
        # The counter receipt: its moment is behind it by definition, so it is
        # stamped here and can never be picked up by a firing pass.
        row.fired_at = timezone.now()
        row.fired_state = STATE_ALREADY_HANDED_OVER
        row.fired_reason = REASON_HANDED_OVER
    row.save(
        update_fields=[
            "send",
            "template_code",
            "template_id",
            "template_version_seen",
            "fired_at",
            "fired_state",
            "fired_reason",
            "updated_at",
        ]
    )
    return row


# ═══════════════════════════════════════════════════════════════════════════
# THE PICKER — `Choosing a template`
# ═══════════════════════════════════════════════════════════════════════════
def templates_for(occasion_code: str, *, search: str | None = None) -> dict[str, Any]:
    """What the drawn picker lists for one occasion.

    The search box is helped *"Searches the name a human gave it."* — so it
    matches the tenant-facing NAME and never the class code, which B14 rule 31
    keeps off a screen entirely.

    An occasion with no class answers an EMPTY list and says why, rather than
    answering an empty picker a clerk reads as a broken screen — the honest
    absence `channel_reachability` takes for an unknown route.
    """
    spec = occasion(occasion_code)
    if not spec.classes:
        return {
            "occasion": spec.code,
            "rows": [],
            "available": False,
            "reason": REASON_NO_WORDING,
            "delivery": nothing_is_sent(),
        }
    rows = notifications_seam.applicant_templates(codes=spec.classes, search=search)
    if spec.must_be_in_writing:
        # p081 rule 3, on the way OUT as well as on the way in: a row that
        # cannot be read as writing is still LISTED — hiding it is what rule 2
        # rejects — and carries the reason it cannot be chosen.
        rows = tuple(_marked_not_writing(one) for one in rows)
    return {
        "occasion": spec.code,
        "rows": list(rows),
        "available": True,
        "reason": None,
        "delivery": nothing_is_sent(),
    }


def _marked_not_writing(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("is_writing") or not row.get("pickable"):
        return row
    return {
        **row,
        "pickable": False,
        "not_pickable_reason": "a_text_never_replaces_a_posted_notice",
    }


# ═══════════════════════════════════════════════════════════════════════════
# FIRING — the decision, which is the whole reason this block exists
# ═══════════════════════════════════════════════════════════════════════════
def on_decision(
    actor: Any,
    request: Any,
    *,
    decision: str,
    already: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Row five, when a request is approved or refused.

    `decision` is the request's new STATE, `approved` or `refused` — not its
    `outcome`, which on this table means what the request BECOMES. `already` is
    the result of a letter that has ALREADY been queued for this decision — the
    refusal letter — in which case this records it and queues nothing.

    ⚠ **IT NEVER RAISES AND NEVER UNDOES THE DECISION IT DESCRIBES.** The
    approval or the refusal has committed by the time this runs; the seam's own
    savepoint is what makes that safe on PostgreSQL, where a failed statement
    aborts the whole transaction and a plain `try` would lose the decision at
    COMMIT while passing the entire suite on SQLite (hard-won law 14).

    ⚠ **APPROVING TWICE QUEUES ONE MESSAGE, NOT TWO.** `fired_at` is the key and
    it is stamped inside the same transaction as the write. `approve` is already
    refused on a request that is not approvable, but a retried HTTP call, a
    double-clicked button and a replayed job all reach here, and rule 6 admits
    no *"probably only once"*.
    """
    spec = _BY_CODE[DECISION]
    row = _decision_row(request, spec)
    if row.fired_at is not None:
        return _fired_view(spec, row, replayed=True)
    if already is not None:
        return _stamp_from(actor, request, spec, row, already)
    if not row.send:
        return _stamp(
            actor, request, spec, row, STATE_NOT_SENT, REASON_NOT_TICKED, None, None, None
        )
    if decision != DECISION_APPROVED:
        # ⚠ **APPROVAL IS THE ONLY DECISION THIS BLOCK QUEUES ITSELF**, and a
        # refusal reaches here with `already` because its letter is the clerk's
        # own (see the module docstring). A refusal whose clerk typed nothing,
        # and any other state, has no letter and is RECORDED rather than
        # guessed at — inventing wording is inventing a rule.
        return _stamp(
            actor, request, spec, row, STATE_NOT_SENT, REASON_NO_WORDING, None, None, None
        )
    # ⚠ **THE APPROVAL'S OWN APPEND-ONLY TIMELINE ROW IS THE QUEUE KEY, AND THE
    # OBVIOUS CHOICE — THE REQUEST — IS A TRAP THIS LANE FELL INTO AND THE TEST
    # CAUGHT.** The acknowledgement already keys on the request, so an approval
    # letter keyed there met its row, `queue_document` reported `created=False`,
    # and the applicant would have been sent *"we have your request"* on the day
    # they were approved. `fired_at` above is what makes this idempotent; the
    # key is what makes the letter the RIGHT one.
    occasion_row = _occasion_event(actor, request, spec, message_body=None)
    outcome_row = notifications_seam.queue_request_approved(
        occasion_id=occasion_row.id,
        request_no=request.request_no,
        applicant_name=request.applicant_name,
        applicant_email=request.applicant_email,
        service_address=_address(request),
        override_template_id=row.template_id,
        actor=actor,
        # The applicant's own language where the utility published this
        # letter in it, the utility's default otherwise (PO option B,
        # 2026-10-29, superseding `OQ-CUS-12619` (a) for messages). A clerk's
        # pick still wins outright — it is an override, and the resolver
        # honours one before any language.
        language=seams.tenant_default_language(),
        preferred_language=request.preferred_language,
    )
    return _stamp_from(actor, request, spec, row, outcome_row)


def _occasion_event(actor: Any, request: Any, spec: Occasion, *, message_body: str | None) -> Any:
    """One append-only timeline row recording that this message was attempted.

    Its id is the queue's idempotency key — the `move` precedent `BR-CUS-1075`
    already uses for the refusal letter and the ask, kept here so all three of
    the clerk-visible letters key the same way and none of them can collide with
    the acknowledgement, which keys on the request itself.
    """
    from apps.customers import service_request_service as writes

    return writes._event(
        request,
        actor,
        kind=models.ServiceRequestEvent.KIND_SYSTEM,
        note=message_body,
        note_type=f"applicant_message:{spec.code}",
    )


def _decision_row(request: Any, spec: Occasion) -> Any:
    row, _ = ServiceRequestMessage.objects.get_or_create(
        tenant_id=request.tenant_id,
        request_id=request.id,
        occasion=spec.code,
        defaults={"send": spec.send_by_default},
    )
    return row


def _address(request: Any) -> str:
    from apps.customers import service_request_service as writes

    return writes._applicant_address(request)


def _stamp_from(
    actor: Any, request: Any, spec: Occasion, row: Any, outcome: dict[str, Any]
) -> dict[str, Any]:
    """Record a seam outcome — ours, or the refusal letter's — on the row.

    ⚠ **THE STATE IS DERIVED FROM WHETHER A ROW EXISTS, NEVER FROM WHETHER THE
    CALL RETURNED** — the same posture `_record_applicant_outcome` takes next
    door, and hard-won law 1 in its original form: a function that came back
    without raising is not a guarantee that anything was written, and *"we told
    them"* is the one claim on a service request that must never be made
    loosely.
    """
    ref = outcome.get("ref") or outcome.get("message_id")
    queued = bool(ref)
    return _stamp(
        actor,
        request,
        spec,
        row,
        STATE_QUEUED if queued else STATE_NOT_SENT,
        REASON_NO_ADAPTER if queued else str(outcome.get("reason") or outcome.get("code") or ""),
        str(ref) if ref else None,
        outcome.get("template_code"),
        outcome.get("address"),
    )


def _stamp(
    actor: Any,
    request: Any,
    spec: Occasion,
    row: Any,
    state: str,
    reason: str,
    ref: str | None,
    template_code: str | None,
    address: str | None,
) -> dict[str, Any]:
    from apps.customers import service_request_service as writes

    with transaction.atomic():
        row.fired_at = timezone.now()
        row.fired_state = state
        row.fired_reason = reason
        row.fired_ref = ref
        row.fired_template_code = template_code
        row.save(
            update_fields=[
                "fired_at",
                "fired_state",
                "fired_reason",
                "fired_ref",
                "fired_template_code",
                "updated_at",
            ]
        )
        writes._event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note=reason,
            note_type=f"applicant_message:{spec.code}:{state}",
        )
        writes._audit(
            actor,
            f"service_request.applicant_message.{spec.code}",
            request.id,
            after={
                "state": state,
                "reason": reason,
                "ref": ref,
                "template_code": template_code,
                "address": address,
            },
        )
    view = _fired_view(spec, row, replayed=False)
    view["address"] = address
    return view


def _fired_view(spec: Occasion, row: Any, *, replayed: bool) -> dict[str, Any]:
    return {
        "occasion": spec.code,
        "when": spec.when,
        "state": row.fired_state,
        "reason": REASON_ALREADY_FIRED if replayed else row.fired_reason,
        "ref": row.fired_ref,
        "template_code": row.fired_template_code,
        #: Never True on any path, and not a field anybody sets. `BR-NOT-013`.
        "sent": False,
        "replayed": replayed,
        "delivery": nothing_is_sent(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# WHAT THE CUSTOMER IS TOLD — the review step's read-only card (REQ-03 step 4)
# ═══════════════════════════════════════════════════════════════════════════
#: The WHEN column when a row will not go. A CODE and never a sentence — the
#: eleven catalogues carry the words (`BR-SHL-020` r2, B14 rule 35).
NOT_SENT_NOTHING_OUTSTANDING = "none_outstanding"
NOT_SENT_NO_EMAIL = "applicant_supplied_no_email_address"

#: The one channel any of these can travel on. All four service-request
#: classes are EMAIL classes and an SMS carries 160 characters, so a phone
#: number alone cannot carry any of this wording (`send_acknowledgement`'s
#: `ACK_NO_EMAIL` is the same fact at the write door).
CHANNEL_EMAIL = "email"

#: The MESSAGE column's key per occasion. The catalogues own the words; this
#: names WHICH words, and nothing English crosses the wire.
TOLD_MESSAGE_KEY = "customers.serviceRequest.told"
TOLD_REASON_KEY = "customers.serviceRequest.toldNotSent"


def on_submit_card(
    request: Any,
    *,
    outstanding_money: Any = None,
    currency: str | None = None,
    outstanding_documents: int | None = None,
) -> dict[str, Any]:
    """`What the customer is told` — the read-only card drawn on REQ-03 step 4.

    Columns, from `04-review-1440.png` read as an image (B14 rule 42):
    **MESSAGE · CHANNEL · TO · WHEN**, for THIS request, ON SUBMIT.

    ⚠ **A MESSAGE THAT WILL NOT BE SENT STILL GETS A ROW SAYING SO.** The
    drawing prints *"Not sent — none outstanding"* in the WHEN column of the
    documents row, and that is the whole point of the card: **an absent row
    and a withheld one look identical**, so a clerk who sees two rows cannot
    tell whether the third was suppressed or never existed. Every on-submit
    occasion is listed, every time, in `OCCASIONS`' order.

    ⚠ **IT IS A READ. Nothing is written and no clock is read** — the same
    posture `notifications.customer_events.move_in_message_plan` takes for the
    move-in's review step (`DEF-CUS-6365`), which is the precedent this
    follows rather than a new idea.

    ════════════════════════════════════════════════════════════════════════
    ⚠ HOW MUCH OF THIS IS REAL TODAY, STATED RATHER THAN IMPLIED
    ════════════════════════════════════════════════════════════════════════
    **ONE of the three rows can actually send.** `request_received` has two
    published classes and `send_acknowledgement` really queues it on submit.
    `documents_outstanding` and `balance_outstanding` have **no template class
    in this product at all** (`OCCASIONS`, `classes=()`, `DEF-CUS-5417`), so
    whatever the clerk ticks, nothing leaves. The drawing shows the fee row
    going out `On submit`; **it does not, and this card says so** rather than
    drawing a promise nobody is keeping (hard-won law 2's mirror — a
    live-looking row over a dead path). `available` carries it per row and
    `available_rows` counts it, because a declared blind spot with no NUMBER
    beside it is indistinguishable from an empty one (law 7).

    **What would make those two rows real is NOTIFICATIONS work and not
    customers work:** two template classes published under `BR-NOT-002` and
    named in `OCCASIONS.classes`, exactly as the two acknowledgement classes
    are. Until then the honest build is this card with those rows saying
    `not_sent`.

    ⚠ **AND `queued` IS THE TRUEST WORD THE PRODUCT HAS.** `BR-NOT-013`: no
    provider adapter exists on any channel. `delivery` carries that fact so no
    screen has to remember it, and a surface built on this must never say a
    message REACHED anybody.

    ⚠ **THE REASON ORDER IS DELIBERATE AND IT IS NOT ALPHABETICAL.** A clerk
    can act on *you unticked it* and on *there is nothing outstanding*; they
    can do nothing at all about *this product has no wording*. So the reason
    naming something about THIS REQUEST wins, and the product-level absence is
    still always visible in `available`.

    ⚠ **THE THREE FACTS MAY BE HANDED IN, AND ON THE DETAIL THEY ARE.** The
    open fee balance and the count of unmet documents are both already read by
    `service_request_reads.detail`, which builds the fees tab and the documents
    tab a few lines earlier. Reading them a third and fourth time would put two
    more queries on the hottest read this module has, for figures the caller is
    already holding — the same argument `conditions_for` makes for one AR read
    and one fee read. Omit them and this reads them itself, so a standalone
    caller is still correct.
    """
    from apps.customers import service_request_service as writes

    stored = {
        row.occasion: row
        # ⚠ **TENANT-SCOPED EXPLICITLY AND NOT LEFT TO RLS**, for the reason
        # `block_for` states above: the default test database is SQLite, where
        # the policy does not exist at all, so a queryset leaning on it would
        # pass the whole suite and be the one thing nothing here can check.
        for row in ServiceRequestMessage.objects.filter(
            tenant_id=_tenant_id(), request_id=request.id
        )
    }
    to = (request.applicant_email or "").strip() or None
    if outstanding_documents is None:
        outstanding_documents = len(writes.unmet_required_documents(request))
    if outstanding_money is None:
        money = writes.fee_total_to_collect(request.id)
        outstanding_money, currency = money["outstanding"], money["currency"]
    rows = [
        _told_row(
            spec,
            stored.get(spec.code),
            to=to,
            outstanding_documents=outstanding_documents,
            outstanding_money=outstanding_money,
            currency=currency,
        )
        for spec in OCCASIONS
        if spec.when == WHEN_ON_SUBMIT
    ]
    return {
        "rows": rows,
        "channel": CHANNEL_EMAIL,
        "to": to,
        # Law 7: print what is covered beside what is not, as NUMBERS.
        "rows_total": len(rows),
        "available_rows": sum(1 for row in rows if row["available"]),
        "will_send_rows": sum(1 for row in rows if row["will_send"]),
        "delivery": nothing_is_sent(),
        "br_ref": BR_REF,
    }


def _told_row(
    spec: Occasion,
    row: Any,
    *,
    to: str | None,
    outstanding_documents: int,
    outstanding_money: Any,
    currency: str | None,
) -> dict[str, Any]:
    """One drawn row: the message, the channel, the address and the moment."""
    ticked = spec.send_by_default if row is None else bool(row.send)
    available = bool(spec.classes)
    # The fee row prints the figure the customer owes (`Fee due — $45.00` in
    # the drawing). It travels as a PARAMETER, never as a composed sentence,
    # and at four stored places with the currency beside it (hard rule 2 —
    # this read rounds nothing; the screen prints `fees.outstanding.display`).
    params: dict[str, Any] = {}
    nothing_outstanding = False
    if spec.code == "balance_outstanding":
        params = {"amount": str(outstanding_money), "currency": currency}
        nothing_outstanding = outstanding_money <= 0
    elif spec.code == "documents_outstanding":
        params = {"count": outstanding_documents}
        nothing_outstanding = outstanding_documents == 0

    reason: str | None = None
    if not ticked:
        reason = REASON_NOT_TICKED
    elif nothing_outstanding:
        reason = NOT_SENT_NOTHING_OUTSTANDING
    elif to is None:
        reason = NOT_SENT_NO_EMAIL
    elif not available:
        reason = REASON_NO_WORDING
    return {
        "occasion": spec.code,
        # MESSAGE — a key and its parameters; the screen composes the words.
        "message_key": f"{TOLD_MESSAGE_KEY}.{spec.code}",
        "params": params,
        # CHANNEL — a code. Email, and only email, for every one of these.
        "channel": CHANNEL_EMAIL,
        # TO — an email address is DATA and not prose, so it travels as itself.
        "to": to,
        # WHEN — the moment, or nothing when it will not go.
        "when": WHEN_ON_SUBMIT if reason is None else None,
        "will_send": reason is None,
        "not_sent_reason": reason,
        "not_sent_reason_key": None if reason is None else f"{TOLD_REASON_KEY}.{reason}",
        # Whether this PRODUCT has wording for it at all — a different
        # question from whether THIS request will send it, and always stated.
        "available": available,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 lane J (12-governance/11-change-requests.md → CR-094-BRC01 · 05-prototype/02 Accounts Menu Blueprint.pdf entry 06 p080 and p081, read AS IMAGES at scale 2 and 4 · apps/customers/applicant_message_models.py · apps/customers/notifications_seam.py · apps/notifications/service_request_events.py · apps/customers/service_request_service.py approve_and_raise + refuse_request · 04-docs/05-modules/03-customers/02-business-rules.md BR-CUS-1076 · CLAUDE.md hard rules 1, 6, 7 · hard-won laws 1, 2, 14)
# generated: 2026-09-15 by story-coder (CR-094-BRC01 lane J)
# checklist: A✔ B=deferred(the screen is lane D's — the payload and its worked example are published in this wave's conformance file) C✔ D✔ E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest under PostgreSQL, every guard proved RED first — quoted in the lane record
# exceptions: (1) NOTHING SENDS — `BR-NOT-013`, and `nothing_is_sent()` publishes the fact so no surface has to remember it. (2) TWO OF THE FIVE OCCASIONS HAVE NO WORDING (`documents_outstanding`, `balance_outstanding`) and say so per row as `available: false` — `DEF-CUS-5417`. (3) REFUSING QUEUES NO SECOND LETTER — the refusal letter IS row five on that path and this module records it. (4) ASKING FOR MORE FIRES NOTHING — it is not a decision.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
