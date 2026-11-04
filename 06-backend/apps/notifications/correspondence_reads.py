# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-036 (EP-CWP-07) — *"Documents and letters: what we sent,
#           when, and by which route"*. Screen: CWP-031 (blueprint `P17`).
#           Published here rather than in `apps/portal` so the STAFF Documents
#           tab — today a frame with no endpoint,
#           `07-frontend/src/features/customers/accountDetailTabs.tsx`
#           `AccountDocumentsTab` — can be built on this same read (PO ruling
#           2026-09-04, the portal reuse map `04-docs/05-modules/15-portal/
#           12-reuse-map.md`).
# Rules:    BR-CWP-083 (post and email remain the DELIVERY RECORD; a screen
#           shows the record) · BR-CWP-045 (documents are SERVED, never
#           re-rendered) · BR-NOT-005 (forward-only status; only the dispatcher
#           advances a row) · BR-NOT-027 (a sent legal document is frozen AS
#           the document) · BR-BIL-036 (an account with no email address is
#           NORMAL — the absence is recorded, never implied by a blank) ·
#           BR-CWP-010 (tenant AND the account set, both in the query) ·
#           BR-CWP-093 (nothing empty ever appears) · `OQ-1399` CLOSED
#           2026-09-04 — the portal is a CONVENIENCE COPY and post and email
#           stay the delivery record · CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_us_cwp_036_documents.py
# Impacts:  apps/portal/seams/notifications_seam.py (`documents_for`, the
#           portal's only caller) · apps/portal/selectors.py `documents`
# ───────────────────────────────────────────────────────
"""Every document this utility sent an account — WHAT, WHEN, and BY WHICH ROUTE.

WHY THIS READ DID NOT EXIST, AND WHY IT IS HERE RATHER THAN IN THE PORTAL
------------------------------------------------------------------------
`outbound_messages` has been written by every issuing bill run since
2026-08-11 and the only reads over it are the S8 triage list (every row, every
source, every account) and `deliveries_for_source` (one bill's rows). **Nobody
could ask "what has this customer been sent?"** — the staff Account details
screen draws its Documents tab as a FRAME for exactly that reason, with real
column headings over one spanning cell saying so.

So `US-CWP-036` is the first surface that needs the question answered, and the
PO's ruling of 2026-09-04 says where the answer belongs: *"all the services
that are required for Consumer portal - you will find it same set of services,
endpoints are already available for Accounts - account details view"*. The
portal must not become a second implementation in the other direction, so the
read is published HERE — by the module that owns the table — and the portal
reaches it through a seam like every other module does.

╔══════════════════════════════════════════════════════════════════════════╗
║  `outbound_messages` IS THE RECORD OF WHAT WAS **SENT**.                  ║
║  IT IS NOT, AND CANNOT BE, A RECORD OF WHAT WAS **DELIVERED**.            ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠ **THREE STATES, AND NONE OF THEM SAYS A LETTER ARRIVED.** This module defines
the vocabulary rather than inheriting it, so it is written down once, here:

  ``sent``            it left the building on at least one route
  ``queued``          it is written and waiting; **nothing has left yet**
  ``could_not_send``  we hold no address for that route, or the attempt failed
  ``held``            written, marked held, never dispatched, never lost
                      (`BR-PAY-018` paper suppression on a bad address)

**`delivered` and `bounced` are deliberately not here.** They are in
`models.STATUSES` and `delivery_ops.UNPOPULATED_STATUSES` names them as the two
that **nothing on this deployment can write** — both are provider facts and no
provider adapter exists on print, email or SMS. So every row of this read
carries `delivery_reported: False` with its reason, as DATA rather than as a
convention a screen might forget: *"'0 of 1,122 hold an address' and 'we could
not count' must never render the same"* (`apps/billing/release.py`), and *"a
notice that does not arrive still counts as sent"* (J47 step 1).

A screen built on this may say **we sent this** and may never say **you
received this**. `OQ-1399` closed on 2026-09-04 with the portal as a
CONVENIENCE COPY precisely so that this stays true.

⚠ **A ROW EXISTS EVEN WHEN NOTHING COULD BE DELIVERED, AND THAT IS DELIBERATE.**
`BR-BIL-036` — *"an account with NO email address is normal, not an
exception"* — is why `unavailable_reason` is a column: the absence is
RECORDED. A read that dropped those rows would report a smaller, tidier and
false history, and *"a message that was never queued leaves no trace"* is the
one thing the queue exists to prevent.

⚠ **ONE DOCUMENT, MANY ROUTES.** The queue's grain is one row per document per
CHANNEL (`BR-BIL-016`), so the August bill posted AND emailed is two rows. A
customer reading *"what did you send me"* sees ONE document that went by two
routes — J47 step 4's *"every row's How names every route it went by"* — so
rows are grouped on `(source_type, source_id)` here and never in a screen.
`copy_no > 0` is a deliberate extra copy of the SAME document and groups with
its original rather than appearing as a second letter.

⚠ **NO HUMAN REFERENCE IS COMPOSED HERE, AND THAT IS A BOUNDARY RATHER THAN A
GAP.** A bill's readable name is `BL-2608-0141`, which lives in `billing`, and
a receipt's is payments'. Reading either from this module is the cross-module
read `B1` forbids. Every row carries `source_type` and `source_id` so the
CALLER — which already holds its own module's seams — resolves the name it
needs and drops the id before anything reaches a screen (B14 rule 31: no
database id is ever a visible value, and a truncation of one is the same
breach — `DEF-3158`).

⚠ **AND THE CALLER MUST NOT DRAW AN EMPTY TABLE.** `[]` from this function
means the queue was ASKED and this account has nothing — a new customer, which
is the commonest first impression the portal makes (`US-CWP-036` TC-4). The
answer is a sentence naming what will fill the page, never column headings over
nothing: *"an empty `<tbody>` … asserts 'none', which on a Documents tab reads
as 'nothing was ever filed'"* (`accountDetailTabs.tsx`, and the portal inherits
the obligation).

Nothing here writes. No clock is read: `as_of` is not a parameter because no
figure on this read depends on today.
"""

from __future__ import annotations

from typing import Any

from apps.notifications import delivery_ops, frozen_documents, models
from apps.tenancy import document_store
from core import errors
from core import tenancy as core_tenancy

# ── the vocabulary (see the docstring — it is defined once, here) ───────────

#: It left the building on at least one route.
STATE_SENT = "sent"
#: Written and waiting. **Nothing has left yet.**
STATE_QUEUED = "queued"
#: Written, marked held, never dispatched, never lost (`BR-PAY-018`).
STATE_HELD = "held"
#: We hold no address for that route, or the attempt failed.
STATE_COULD_NOT_SEND = "could_not_send"

#: ⚠ **`delivered` AND `bounced` ARE ABSENT ON PURPOSE.** Both are provider
#: facts and `delivery_ops.UNPOPULATED_STATUSES` records that nothing on this
#: deployment writes either. A row that somehow carried one is read as SENT
#: below — which is the strongest thing this product may claim — rather than
#: being reported as an arrival nobody confirmed.
DOCUMENT_STATES = (STATE_SENT, STATE_QUEUED, STATE_HELD, STATE_COULD_NOT_SEND)

#: Carried on every row so a screen renders the honest sentence rather than
#: remembering the rule. `False` is the only value this deployment can produce.
DELIVERY_REPORTED = False
DELIVERY_NOT_REPORTED_REASON = (
    "no provider reports delivery on any channel, so this says what was sent "
    "and never that it arrived"
)

#: `models.STATUSES` values that mean the thing left. `delivered` and `bounced`
#: are included so that a future deployment which CAN write them still reads as
#: sent here rather than falling through to `could_not_send`.
_LEFT_THE_BUILDING = frozenset((models.STATUS_SENT, *delivery_ops.UNPOPULATED_STATUSES))

#: ⚠ **A ONE-TIME CODE IS NOT A DOCUMENT, AND THE VOCABULARY ALREADY SAID SO
#: (`DEF-CWP-4411`).** `models.SOURCE_TYPES` added `portal` on 2026-09-04 for
#: the customer portal's enrolment codes and password-reset links, and its own
#: comment states the rule this set enforces: *"a code is not a document, there
#: is no envelope for it, and it is worthless within ten minutes"* — which is
#: why `portal` is deliberately absent from `CHANNEL_FLOOR_BY_SOURCE`.
#:
#: **What the Product Owner saw.** Those rows carry an `account_id` (a resend
#: has to find the person), so this read listed them, and a sign-in code texted
#: to a customer appeared on *Documents and letters* as **A letter from us ·
#: Letter · How: Text message** — no kind, because no template class is
#: catalogued for it, and nothing to open, because a code freezes no document.
#: The SMS route was correct: `credentials.contact_for` prefers a mobile where
#: one is held, by design.
#:
#: **Excluded by SOURCE KIND rather than by template code**, so a second
#: credential class cannot be added and forgotten — the same reasoning `TC-5`
#: gives for excluding staff rows by the shape of the query. The day the portal
#: queues something that IS a document, it needs a source kind that is not this
#: one (it would need its own print floor anyway), and this set stays right.
NOT_A_DOCUMENT_SOURCE_TYPES = frozenset({"portal"})


def document_kind(template_code: str | None) -> str | None:
    """WHAT this document is, as one of `tenancy`'s `DOCUMENT_KINDS`, or None.

    ⚠ **`None` IS A STATED ABSENCE AND NOT A DEFAULT.** The map is
    `frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS`, whose own comment says
    *"anything absent still HOLDS on `OQ-1164` rather than being guessed"*, and
    guessing here would be worse than there: `OQ-1164` decides which classes
    are legal documents, and a class this map does not name is one nobody has
    ruled on. A caller shows the row with the kind it can state, never with the
    nearest one.

    Deliberately NOT derived from `source_type`: three different notices all
    carry `source_type = 'notice'`, and a customer asking *"what was that
    letter"* is asking for a KIND, never for a table.
    """
    return frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS.get(template_code or "") or None


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _route_state(row: models.OutboundMessage) -> tuple[str, str | None]:
    """One channel's honest state, and the reason when there is one.

    ⚠ **THE ORDER OF THESE TESTS IS THE RULE.** `held` is a FLAG rather than a
    status (`models.py` says why: the lifecycle is forward-only, so a `held`
    status would be a sixth state the re-queue action could reach), so a held
    row is still `queued` in the column — and *held* is the more useful thing
    to tell a customer, because it is the one with a reason and a fix.
    """
    if row.status in _LEFT_THE_BUILDING:
        return STATE_SENT, None
    if row.status == models.STATUS_FAILED:
        return STATE_COULD_NOT_SEND, row.last_error or None
    if row.unavailable_reason:
        # `BR-BIL-036` — the absence is RECORDED, and it is a fact about this
        # customer's contact details rather than about the platform.
        return STATE_COULD_NOT_SEND, row.unavailable_reason
    if row.held:
        return STATE_HELD, row.held_reason or None
    return STATE_QUEUED, None


#: Best outcome first. The DOCUMENT's headline state is the best any of its
#: routes achieved, and every route still reports its own state on the row, so
#: nothing is hidden by the summary.
_STATE_ORDER = (STATE_SENT, STATE_QUEUED, STATE_HELD, STATE_COULD_NOT_SEND)


def _document_state(route_states: list[str]) -> str:
    for candidate in _STATE_ORDER:
        if candidate in route_states:
            return candidate
    # Unreachable while a group has at least one row, which grouping guarantees.
    return STATE_COULD_NOT_SEND


def _stored(source_type: str, source_id: Any, message_ids: list[Any]) -> dict[str, Any]:
    """Is there a frozen document to serve, and if not, WHY not.

    ⚠ **TWO PLACES A DOCUMENT CAN BE FROZEN, AND BOTH ARE ASKED.** A bill is
    sealed at ISSUE against `source_type='invoice'`
    (`apps/billing/frozen_bill.freeze_at_issue`); everything else is sealed at
    DISPATCH against `source_type='outbound_message'` and the message row's own
    id (`apps/notifications/frozen_documents.freeze_for_dispatch`). Asking only
    one would report *"no file was kept"* over half the documents in the list.

    ⚠ **NEVER AN EMPTY SUCCESS** — `document_store.for_source` answers a
    `DocumentLookup` whose two halves cannot both be absent, and the reason is
    carried through unflattened so the control renders VISIBLY HELD with it
    (`BR-CWP-056`) rather than disappearing.
    """
    lookup = document_store.for_source(source_type=source_type, source_id=source_id)
    if lookup.found:
        return {"available": True, "reason": None}
    reason = lookup.unavailable_reason
    for message_id in message_ids:
        by_message = document_store.for_source(source_type="outbound_message", source_id=message_id)
        if by_message.found:
            return {"available": True, "reason": None}
        reason = by_message.unavailable_reason or reason
    return {"available": False, "reason": reason}


def message_ids_for_source(*, source_type: str, source_id: Any) -> list[Any]:
    """The queue rows that carried one source's document, newest first.

    ⚠ **WHY THIS IS PUBLISHED RATHER THAN INLINED BY ITS CALLER** (`CR-085`
    `CPB-03`). `_stored` above decides whether a document EXISTS by asking two
    places — the source itself, and then every outbound message that carried
    it — and a screen's *available* flag comes from that answer. A serving path
    that asked only the first would refuse a download the very same screen had
    just offered, which is a hold and a promise disagreeing about one document.
    So the second half of that question lives here, in the module that owns the
    queue, and both askers get the same list.

    ⚠ **TENANT-SCOPED IN THE QUERY**, like every read in this file, and RLS
    refuses a foreign row underneath it — two guarantees rather than a habit.

    ⚠ **IT DOES NOT FILTER BY ACCOUNT AND MUST NOT BE CALLED WITHOUT ONE.**
    `BR-CWP-010` belongs to the caller, which resolves the source from the
    session's own set before asking; adding an account filter here would be a
    second home for that rule and the two would eventually drift.
    """
    return list(
        models.OutboundMessage.objects.filter(
            tenant_id=_tenant_id(), source_type=source_type, source_id=source_id
        )
        .order_by("-created_at", "-id")
        .values_list("pk", flat=True)
    )


def account_correspondence(*, account_ids: list[Any]) -> list[dict[str, Any]]:
    """Every document sent to these accounts, newest first, one row per document.

    ⚠ **BOTH HALVES OF `BR-CWP-010` ARE IN THE QUERY** — the tenant and the
    account set — so a caller that passed the wrong set gets nothing rather
    than somebody else's mail, and the database's RLS `FORCE` is a second,
    independent guarantee.

    ⚠ **A ROW ADDRESSED TO NO ACCOUNT IS ABSENT BY CONSTRUCTION.**
    `outbound_messages.account_id` is nullable for the scheduled-report and
    bookkeeper messages addressed to STAFF, and `account_id__in` cannot match
    NULL — so `US-CWP-036` TC-5's *"a document the customer may not see — an
    internal letter"* is excluded by the shape of the query rather than by a
    list of kinds somebody has to keep up to date.

    ⚠ **AND A ONE-TIME CODE IS NOT HERE EITHER** — `NOT_A_DOCUMENT_SOURCE_TYPES`
    above, `DEF-CWP-4411`. The portal's enrolment codes and reset links are
    addressed to an account, so they would otherwise be listed; they are not
    documents, they freeze no copy, and the vocabulary already says so.

    ⚠ **AND A SKIPPED NOTICE IS NOT HERE, WHICH IS THE POINT OF TWO SCREENS.**
    A notice the ladder decided not to send writes a `NoticeHistory` row and no
    queue row at all, so it produced no document and cannot appear in a list of
    documents (`US-CWP-036` TC-8). It belongs on `CWP-068`, which reads
    `NoticeHistory`, and that split is deliberate — J47 step 2 asserts the row
    is on one screen and absent from the other.
    """
    ids = [str(one) for one in account_ids]
    if not ids:
        return []
    rows = (
        models.OutboundMessage.objects.exclude(source_type__in=NOT_A_DOCUMENT_SOURCE_TYPES)
        .filter(tenant_id=_tenant_id(), account_id__in=ids)
        # `created_at` IS `queued_at` (models.py) and is the only time every row
        # carries: `sent_at` is the dispatcher's and is null on everything this
        # deployment has ever written. Ordering on it would put the whole list
        # in an arbitrary order.
        .order_by("-created_at", "-id")
    )

    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row.source_type, str(row.source_id))
        state, reason = _route_state(row)
        group = groups.get(key)
        if group is None:
            group = {
                "source_type": row.source_type,
                "source_id": str(row.source_id),
                "account_id": str(row.account_id) if row.account_id else None,
                #: The pinned template class. It is the only thing on the queue
                #: row that says WHAT the document is, and
                #: `frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS` maps it
                #: onto the store's kind. `None` where the writer pinned
                #: nothing, which is a stated absence and not a bill.
                "template_code": row.template_code,
                #: The store's document kind, or `None` where the pinned class
                #: is one `OQ-1164` has not ruled on — a stated absence rather
                #: than the nearest kind (`document_kind` says why).
                "kind": document_kind(row.template_code),
                #: The queue's own day. A screen shows it as *Sent*; the state
                #: beside it is what stops that reading as an arrival.
                "queued_on": row.created_at.date().isoformat() if row.created_at else None,
                "sent_on": None,
                "routes": [],
                "message_ids": [],
                "delivery_reported": DELIVERY_REPORTED,
                "delivery_not_reported_reason": DELIVERY_NOT_REPORTED_REASON,
            }
            groups[key] = group
        group["message_ids"].append(row.pk)
        group["routes"].append(
            {
                "channel": row.channel,
                "state": state,
                "reason": reason,
                #: `copy_no > 0` is a deliberate, human-requested extra copy
                #: (`US-NOT-011`), not a second document.
                "copy_no": row.copy_no,
                #: A letter the post office sent back was GENUINELY SENT
                #: (`BR-NOT-005` forward-only), so this is a date beside a
                #: `sent` route and never a state of its own.
                "returned_on": row.returned_at.date().isoformat() if row.returned_at else None,
            }
        )
        if row.sent_at is not None:
            earliest = group["sent_on"]
            here = row.sent_at.date().isoformat()
            group["sent_on"] = here if earliest is None else min(earliest, here)

    out: list[dict[str, Any]] = []
    for group in groups.values():
        route_states = [route["state"] for route in group["routes"]]
        group["state"] = _document_state(route_states)
        group["stored_document"] = _stored(
            group["source_type"], group["source_id"], group.pop("message_ids")
        )
        out.append(group)
    return out
