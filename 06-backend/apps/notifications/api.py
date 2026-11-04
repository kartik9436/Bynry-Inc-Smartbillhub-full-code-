# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-013 (the platform delivery dashboard + re-queue — the S8
#           dispatch home, served: GET /outbound · GET /outbound/summary ·
#           POST /outbound/{id}/requeue · POST /outbound/requeue) ·
#           US-NOT-014 (bounces + returned mail: POST /deliveries/returned, and
#           the payments hand-off that turns a returned letter into the account's
#           bad-address flag) · US-NOT-001 (the queue table, read and re-written
#           through its one write path — the resend's extra copy) ·
#           US-NOT-009 (the notice record and the CERTIFIED-MAIL register:
#           GET /notices)
#           Screens: S8 · S30 · S34 · S35
# Rules:    BR-NOT-005 (the platform-wide queue; the dispatcher is the ONLY
#           sender and NO synchronous send endpoint may exist — A11 r2 §4 makes
#           minting one a gate failure) · BR-TEN-041 #8 (Settings →
#           Notifications IS the delivery/dispatch home) · BR-PAY-018 (returned
#           mail → bad-address flag → paper suppressed until verified; balances
#           unaffected; audited) · BR-CUS-039 (certified mail is REQUIRED on the
#           48-hour final tier; every send AND skip appends notice_history) ·
#           BR-BIL-016 (one delivery record per document per channel) ·
#           BR-SHL-011 (list grammar) · BR-SHL-025 / BR-IDN-009 (server-enforced
#           RBAC) · BR-TEN-003 / HR-1 (another tenant's row reads as absent) ·
#           BR-TEN-043 (a business date is an INPUT, never a clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money + currency) ·
#           rule 6 (idempotency — a resend never silently duplicates a contact) ·
#           rule 7 (every action audited)
# Tests:    06-backend/tests/test_def_128_notifications_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           06-backend/openapi/schema.json (the committed contract snapshot
#           moves with any endpoint added here — BE-11 TC05) ·
#           07-frontend/src/features/notifications/ (the S8 Notifications tab,
#           which calls exactly these paths)
# ───────────────────────────────────────────────────────
"""notifications API endpoints per 11b §2.13 + §2.9, and A11 Addendum r4.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — the re-send's `copy_no` IS a CLAUDE.md 🔒
idempotency key (hard rule 6): this file is where a human presses the button
that decides whether a customer receives a SECOND certified 48-hour notice, at
real postage and against the legal record. AI-authored 2026-08-16 under the PO
ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

THIN by law (B8 / LAW 0): parse → call a service or a selector → serialize.
There is no ORM here, no status transition, no clock and no send; every refusal
leaves this file as a `core.errors` catalog exception (gate G9).

╔══════════════════════════════════════════════════════════════════════════╗
║  WHY THIS FILE EXISTS TODAY AND NOT YESTERDAY — DEF-128, AND IT IS THE    ║
║  FOURTH TIME THIS EXACT DEFECT HAS BEEN WRITTEN UP IN THIS REPOSITORY.    ║
╚══════════════════════════════════════════════════════════════════════════╝
It was **72 BYTES**: one docstring line, no `urlpatterns`, and no `include()`
naming it in `config/urls.py`. Behind it sat **7,084 lines** — `dispatcher.py`
877, `services.py` 897, `template_service.py` 796, `notices.py` 701,
`delivery_ops.py` 635, `rendering.py` 568 and more, every one of them tested.
Billing's `api.py` is 56,528 bytes and payments' is 37,906.

So **nothing a customer was ever sent could be triggered, listed or audited
through the product.** A clerk could not see whether last night's 1,124 bills
had gone out, could not re-queue the six that failed, could not mark a returned
envelope, could not open the record of the disconnect notices this utility had
served, and could not send anybody a second copy of anything.

`config/urls.py` records the three that came before this one — billing, payments,
ledger — each with the same sentence. The durable half of the fix is
`10-scripts/gates/g25_engine_surface.py`, which counts a module's engine lines
against its MOUNTED routes and fails at zero; it was red-proved against this
module before the first route below was written.

────────────────────────────────────────────────────────────────────────────
THE SEVEN ROUTES, AND WHAT A PERSON CAN NOW DO
────────────────────────────────────────────────────────────────────────────
    GET  /outbound                    see every message the platform has queued
    GET  /outbound/summary            the dispatch home's counts, per type ×
                                      channel × status, with the two provider
                                      statuses named as NOT REPORTED
    POST /outbound/{id}/requeue       put one failed message back in the pool
    POST /outbound/requeue            …or a whole selection of them (bulk)
    GET  /outbound/selection          every id a filtered view matches, ≤ 500
                                      (DEF-NOT-10650, "Select all N matching")
    POST /outbound/{id}/retry-to      queue a NEW copy to a corrected address,
                                      this message only (DEF-NOT-10650, 3B)
    POST /outbound/{id}/resend        send a customer another copy — a NEW row
                                      at an explicit `copy_no`, never an edit
    POST /deliveries/returned         mark post returned (single or bulk) AND
                                      flag the account bad-address through
                                      payments' own writer
    GET  /notices                     the notice record — what this utility has
                                      told its customers, and the CERTIFIED-MAIL
                                      register (`f.certified=true`)

**THERE IS NO SEND ENDPOINT AND THERE MUST NEVER BE ONE.** A11 Addendum r2 §4
makes it explicit — *"no synchronous send endpoint anywhere (queue only,
BR-NOT-005)"* — and minting one is a gate failure. Everything here queues,
lists, or moves a row between queue states.

────────────────────────────────────────────────────────────────────────────
RESEND: `copy_no` IS REQUIRED, AND THAT IS THE WHOLE IDEMPOTENCY GUARANTEE
────────────────────────────────────────────────────────────────────────────
`outbound_messages` is keyed `UNIQUE (tenant, source_type, source_id, channel,
copy_no)`. `copy_no = 0` is the delivery record BR-BIL-016 mandates; 1, 2, … are
the deliberate extra copies a HUMAN asked for (US-NOT-011 §5, US-BIL-024 TC-4).

So the resend takes the copy number from the caller and **refuses without one**.
An endpoint that auto-incremented would post a second letter on every double
click, every retried request and every impatient refresh — and would look
perfectly correct doing it. With the number stated, a repeated submit collides
with its own row in the DATABASE and comes back `created: false`: same row, one
letter, no postage. That is CLAUDE.md rule 6 honoured by the same mechanism the
table was designed around, and it needs no second key table to do it.

⚠ **CERTIFIED MAIL IS WHY THIS IS NOT A JUDGEMENT CALL.** A duplicated 48-hour
final notice costs real certified postage AND misrepresents the legal record —
two mailings where `notice_history` shows one. The response says on every resend
whether the row it copied is a disconnect notice, so a screen can put the
confirmation in front of a clerk rather than behind one.

**HELD ROWS ARE NEVER RESENT.** A held row is a letter to an address the
customer's own mail already came back from (BR-PAY-018); `delivery_ops.requeue`
refuses those for the same reason and names it.

────────────────────────────────────────────────────────────────────────────
RETURNED MAIL CLOSES A GAP TWO MODULES EACH REPORTED AND NEITHER COULD CLOSE
────────────────────────────────────────────────────────────────────────────
`delivery_ops.mark_returned` stamps the queue row and EMITS the r12 #8 event; it
does not write `accounts.bad_address`, because that column is payments'.
`apps/payments/returned_mail.mark_returned_bulk` consumes such events and had no
caller. Both lanes wrote the gap down honestly and the two halves sat
unconnected. This endpoint is the caller: it hands payments the events through
`payments_seam.flag_returned_addresses`, and payments writes payments' table.

────────────────────────────────────────────────────────────────────────────
MONEY, ON THE ONE RESPONSE THAT CARRIES IT
────────────────────────────────────────────────────────────────────────────
A queue row holds no money. A NOTICE does — it states a balance and a reconnect
fee to a customer — so every money member on `GET /notices` is a STRING at
NUMERIC(18,6) fidelity and travels with the tenant's `currency` (rule 2,
BR-TEN-042). Never a JSON number, which is a double, and never a bare figure a
reader denominates for themselves.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from datetime import date, datetime, time, timezone as dt_timezone
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.notifications import (
    attention,
    delivery_ops,
    models,
    payments_seam,
    rendering,
    selectors,
    services,
    suppression,
    suppression_models,
    unsent_preview,
)
from core import errors  # noqa: F401 — the catalog this file's refusals come from (G9)
from core.pagination import StandardPagination
from core.permissions import AdminOrClerk, AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant

#: The i18n keys this file's refusals carry. Named once, so the catalogue diff
#: and the code can be read against each other in one grep (G18 compares them
#: in both directions and a key with no catalogue entry renders as a raw dotted
#: string to a clerk).
KEY_PAYLOAD = "notifications.payload_not_object"
KEY_IDS_REQUIRED = "notifications.message_ids_required"
KEY_COPY_NO_REQUIRED = "notifications.resend.copy_no_required"
KEY_RESEND_HELD = "notifications.resend.held"
KEY_RETURNED_DATE = "notifications.returned.date_required"
KEY_DELIVERY_REFUSED = "notifications.delivery.refused"
#: `DEF-NOT-5641` — the release path's OWN missing-date sentence. It exists
#: because the module's nearest key, `KEY_RETURNED_DATE`, reads *"Enter the
#: date the mail came back"* — true of a returned envelope and FALSE on the
#: blocked-addresses screen, where a clerk is letting an email address
#: through. A key name reads as its meaning and nobody opens the catalogue,
#: which is why that was worth a defect row rather than a reused constant.
KEY_RELEASE_DATE = "notifications.suppression.release_date_required"
KEY_QUEUE_REFUSED = "notifications.queue.refused"
#: DEF-NOT-10650 (PO 2026-10-29) — "Select all N matching" over the cap, and the
#: three refusals of *Fix address and retry*.
KEY_SELECTION_TOO_MANY = "notifications.selection.tooMany"
KEY_RETRY_TO_REFUSED = "notifications.retryTo.refused"
KEY_RETRY_TO_ADDRESS = "notifications.retryTo.addressInvalid"
KEY_RETRY_TO_UNCHANGED = "notifications.retryTo.addressUnchanged"


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key=KEY_PAYLOAD)
    return data


def _actor(request: Any) -> Any:
    """WHO is acting, from the SESSION — never from the body.

    `audit_log.actor`, `outbound_messages.returned_by` and every
    `delivery.*` trail row read this. The one thing they must not be is client
    input (BR-SHL-025: the screen is not the enforcement).
    """
    return getattr(request, "user", None)


def _message_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    """The selection a bulk action was performed over. REQUIRED, non-empty.

    An empty list is refused rather than treated as "all": a bulk re-queue that
    quietly meant *everything* would put nine hundred rows back in the pool
    because a checkbox did not register.
    """
    raw = payload.get("message_ids")
    if not isinstance(raw, list) or not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=KEY_IDS_REQUIRED,
            field_errors=[{"field": "message_ids", "code": errors.VAL_REQUIRED}],
        )
    return tuple(str(value) for value in raw)


def _business_date(payload: dict[str, Any], name: str) -> date:
    """An ISO calendar date from the body — never a server clock (BR-TEN-043).

    Tuesday's stack of returned post is marked as TUESDAY even when it is worked
    on Wednesday; `apps/payments/returned_mail.mark_returned` states the same
    rule from the other side and takes the same argument. Gate G6 greps this
    layer for a clock read, and there is none.
    """
    raw = payload.get(name)
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=KEY_RETURNED_DATE,
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem


def _at_midnight_utc(day: date) -> datetime:
    """A calendar day as the instant `outbound_messages.returned_at` stores.

    ⚠ WHICH instant a user-entered date becomes, in whose timezone, is **OQ-153**
    — CLOSED on 2026-08-12 as *midnight in the UTILITY'S OWN timezone*, and
    blocked in practice by DEF-082 (the timezone dropdown does not exist in
    Company settings, so no tenant has one to read). `apps/payments/api._moment`
    anchors at midnight UTC for exactly this reason and this layer matches it,
    rather than inventing a second convention for the same kind of value.

    Nothing depends on the INSTANT: BR-PAY-018 makes returned mail a
    balance-free event, the account flag is derived from an unresolved event row
    rather than from a timestamp, and the DATE — which is what a clerk and an
    auditor read — is preserved either way.
    """
    return datetime.combine(day, time.min, tzinfo=dt_timezone.utc)


def _as_catalog_refusal(refusal: Exception, *, br_ref: str, message_key: str) -> errors.BizError:
    """A service-layer refusal, as the ONE catalog exception G9 allows.

    `DeliveryOpsRefused` and `QueueWriteRefused` are deliberately not catalog
    exceptions — each is raised inside work that may run over a selection of
    hundreds, where the right handling is to record the break and carry on
    (BR-BIL-055's shape). This layer IS answering a request, so it is where the
    translation belongs, and it is the only place in the module that knows what
    HTTP is.

    ONE code — 422 BIZ-COMPLETENESS — for the reason `apps/billing/api.py`
    states: choosing among the nine BIZ codes per refusal would be this layer
    INTERPRETING rules it does not own. The refusal's own sentence travels in
    `params.detail` and its BR-ID in `br_ref`, which is what BR-AUD-018's
    attempt row records.

    ⚠ `params.detail` IS NOT RENDERED (BR-SHL-020 r2, PO ruling 2026-08-19:
    *"server detail text should not reach customer screens"*). It is kept because
    it is the DIAGNOSTIC: it reaches the BR-AUD-018 attempt row and the server log,
    where support can still read it. What the user sees is the catalogue entry for
    `message_key`, and nothing else — see DEF-322.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=br_ref,
        message_key=message_key,
        params={"detail": str(refusal)},
    )


# ══════════════════════════════════════════════════════════════════════════
# THE DELIVERY QUEUE — 11b §2.13 (US-NOT-013)
# ══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Settings = View for Executive, Full for Admin
def outbound(request: Any) -> Response:
    """S8's platform queue list, and the S30/S35 delivery panels (US-NOT-013).

    The S8 capability row's vocabulary, served: search on recipient/account/ref,
    filters on type · channel · status · date range (plus `f.held` and
    `f.account_id`), the five sortable columns, and the ratified default —
    *"failed+bounced first, then queued_at"*, so the six failures are not buried
    under nine hundred rows that are fine.

    Pagination is mandatory on every list (11b G5) at the ratified sizes
    50/100/200/500/1000, default 50 (A11 Addendum r2). The page is taken in the
    DATABASE: only the rows on screen are serialized.
    """
    require_tenant(request)
    params = selectors.list_params(request.query_params)
    paginator = StandardPagination()
    page = paginator.paginate_queryset(selectors.queue_list_queryset(params), request)
    # `queue_page`, not `queue_row` per row: it reads every row's account NUMBER
    # for the whole page in one statement, so the screens that list this queue
    # print `AC-2026-00054` rather than a database id (DEF-PAY-6344, B14 rule 31).
    response = paginator.get_paginated_response(selectors.queue_page(page or []))
    # The vocabulary the screen filters with, served WITH the list for the same
    # reason payments serves its method list there: `GET /lookups/…` has no
    # notifications handler, and a filter dropdown built from a hard-coded copy
    # of these tuples is a second home for BR-NOT-005's status set.
    response.data["vocabulary"] = {
        "statuses": list(models.STATUSES),
        "channels": list(models.CHANNELS),
        "source_types": list(models.SOURCE_TYPES),
        #: ⚠ Two of the five statuses can never appear — see `outbound_summary`.
        "unpopulated_statuses": list(delivery_ops.UNPOPULATED_STATUSES),
        #: ⚠ THE CHANNELS WHOSE CONTENT MAY BE READ ON THIS DEPLOYMENT RIGHT
        #: NOW — decision log 2026-09-05. A channel is in this list exactly
        #: while this tenant has NO provider connected for it, so it empties
        #: itself the day one is connected; `apps/notifications/
        #: unsent_preview.py` holds the whole gate and the reasoning.
        #:
        #: Served WITH the list, four reads per page rather than one per row,
        #: so the screen offers the control on exactly the rows it will work
        #: for. A screen that guessed from `status == "queued"` would offer it
        #: on rows that answer *a provider is connected* and nothing else.
        "disclosable_channels": list(unsent_preview.disclosable_channels()),
        #: DEF-NOT-10650 — where the screen may draw a checkbox (2A) and the
        #: *Fix address and retry* action (3B): the server's own tuples, so the
        #: control is offered exactly where the server would accept it.
        "requeueable_statuses": list(delivery_ops.REQUEUEABLE_STATUSES),
        "retry_to_statuses": list(attention.RETRY_TO_STATUSES),
        "retry_to_channels": list(attention.RETRY_TO_CHANNELS),
        "selection_cap": attention.SELECTION_CAP,
    }
    #: DEF-NOT-10650 (1A) — the count on *Needing attention*, served in BOTH
    #: views, because the switch shows it whichever side is open.
    response.data["attention_count"] = attention.attention_count()
    return response


@api_view(["GET"])
@permission_classes([SystemAdminOnly])  # it exists to feed the bulk re-queue, which is Admin's
def outbound_selection(request: Any) -> Response:
    """*"Select all N matching"* — DEF-NOT-10650 (PO 2026-10-29, 2A).

    The SAME list params as `GET /outbound` (search and `f.*`), resolved to
    every matching id rather than to a page, so the selection is the view the
    clerk is looking at. ⚠ **ABOVE `attention.SELECTION_CAP` IT REFUSES AND
    RETURNS NO IDS** — a selection the clerk cannot see the size of is never
    handed back to be re-queued. A view matching nothing returns an empty list,
    which the bulk re-queue then refuses: *empty* never becomes *all*.
    """
    require_tenant(request)
    params = selectors.list_params(request.query_params)
    try:
        selection = attention.resolve_selection(selectors.queue_list_queryset(params))
    except attention.SelectionTooLarge as refusal:
        raise errors.BizError(
            errors.BIZ_CAP,
            br_ref="BR-NOT-005",
            message_key=KEY_SELECTION_TOO_MANY,
            params={"count": refusal.count, "cap": attention.SELECTION_CAP},
        ) from refusal
    return Response(
        {
            "message_ids": list(selection.message_ids),
            "count": selection.count,
            "cap": attention.SELECTION_CAP,
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def outbound_summary(request: Any) -> Response:
    """The dispatch home's counts — US-NOT-013 TC-1, US-NOT-015 TC-1.

    ONE function answers both (`delivery_ops.queue_health`), because two
    counters over one table is how a dashboard and a canned report come to
    disagree about the same day.

    ⚠ **`delivered` AND `bounced` ARE SERVED AS NOT REPORTED, NEVER AS ZERO.**
    Both are provider facts — a delivery confirmation and an ESP bounce webhook
    — and no provider adapter exists on any channel, print included: delivery is
    out of this release by PO ruling (2026-08-15). "0 delivered of 142 sent"
    reads as a delivery failure when the truth is that nobody is reporting, so
    the two statuses travel on `unpopulated_statuses` and the reason travels in
    `problems` (`apps/billing/release.py`'s rule: *"'0 of 1,122 hold an address'
    and 'we could not count' must never render the same"*).
    """
    require_tenant(request)
    source_type = request.query_params.get("f.source_type") or None
    health = delivery_ops.queue_health(source_type=source_type)
    return Response(
        {
            "counts": [dict(entry) for entry in health.counts],
            "totals": dict(health.totals),
            "held": health.held,
            "returned": health.returned,
            "retry_exhausted": health.retry_exhausted,
            # US-NOT-013 §1's *"deferred channels show their queued backlogs"*.
            "queued_by_channel": delivery_ops.deferred_backlog(),
            "unpopulated_statuses": list(health.unpopulated_statuses),
            "problems": [dict(entry) for entry in health.problems],
        }
    )


def _requeue(request: Any, message_ids: tuple[str, ...]) -> Response:
    """The one implementation both re-queue routes call.

    US-NOT-013 TC-3 wants row AND bulk and the same rules for each; two code
    paths would be two places for the held-row refusal to drift.
    """
    outcome = delivery_ops.requeue(message_ids=message_ids, actor=_actor(request))
    return Response(
        {
            "requeued": list(outcome.requeued),
            # Every row that did NOT move, with its reason — a bulk action that
            # silently skipped four of eleven rows is a bulk action nobody can
            # trust (US-NOT-013 TC-4/TC-5 are both in here).
            "refused": [dict(entry) for entry in outcome.refused],
            #: US-NOT-013 TC-3, stated as a VALUE rather than left to be
            #: inferred: *"a re-queue never bypasses batching"*. Nothing was
            #: sent by this call and the next cycle takes at most the tenant's
            #: batch size, as always.
            "dispatched": False,
            "toast": outcome.toast,
        }
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # A4: Settings & lookup tables — System Admin Full
def outbound_requeue(request: Any, message_id: str) -> Response:
    """Put ONE failed message back in the pool (11b §2.13 · US-NOT-013 TC-3).

    Resolved through the tenant's own rows first, so a forged id from another
    tenant is a 404 that cannot be told from any other 404 (HR-1; TC-5).

    ⚠ This CLEARS `batch_id` — see `delivery_ops.requeue`'s box. A re-queue that
    reset only the status would look correct on every screen and would leave a
    crashed hand-off's rows permanently invisible to the dispatcher.
    """
    require_tenant(request)
    row = selectors.row_or_404(message_id)
    try:
        return _requeue(request, (str(row.pk),))
    except delivery_ops.DeliveryOpsRefused as refusal:
        raise _as_catalog_refusal(
            refusal, br_ref="BR-NOT-005", message_key=KEY_DELIVERY_REFUSED
        ) from refusal


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def outbound_requeue_bulk(request: Any) -> Response:
    """*"Re-queue selected"* — the S8 capability row's bulk action (US-NOT-013).

    Contracted here rather than in 11b §2.13, which lists the single-row form
    only; US-NOT-013 §1 ratifies both (*"a re-queue action (row + bulk)"*) and
    EP-NOT-04's capability matrix names the bulk one by name. A11 Addendum r4
    records it as a build-time addition under the r2 CONFIRMED-DIRECTIONAL
    clause.

    Per-row results, never one boolean: a selection containing one held row is
    a normal Tuesday and must not kill the other ten.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        return _requeue(request, _message_ids(payload))
    except delivery_ops.DeliveryOpsRefused as refusal:
        raise _as_catalog_refusal(
            refusal, br_ref="BR-NOT-005", message_key=KEY_DELIVERY_REFUSED
        ) from refusal


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # US-NOT-011 §5: the re-send lives on S35, a clerk's screen
def outbound_resend(request: Any, message_id: str) -> Response:
    """Send the customer ANOTHER COPY — a new row, never an edit (US-NOT-011).

    Body: `{"copy_no": 1}` — **REQUIRED**. Read the module docstring's resend
    section before changing that: the copy number IS the idempotency key
    (CLAUDE.md rule 6), the database is the arbiter, and an endpoint that
    allocated the number itself would post a second letter on every double
    click while looking perfectly correct.

    What is copied: the source document, the channel, the template PIN and the
    recipient snapshot — the same pinned version renders forever (BR-BIL-026,
    US-NOT-011 TC-3) and the recipient is the one snapshotted at queue time
    (BR-TEN-017).

    ⚠ **OQ-223 — whether a staff resend should RE-RESOLVE the recipient after
    an address change is not ruled anywhere**, and the response says so on every
    call rather than leaving a clerk to discover it. BR-TEN-017 is what IS
    signed, so the snapshot is reused; the question is raised, not answered.

    Refuses a HELD row (BR-PAY-018): that letter's address is already known to
    be wrong, and posting it again is the one outcome the hold exists to
    prevent.
    """
    require_tenant(request)
    row = selectors.row_or_404(message_id)
    payload = _payload(request)

    raw = payload.get("copy_no")
    try:
        copy_no = int(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=KEY_COPY_NO_REQUIRED,
            field_errors=[{"field": "copy_no", "code": errors.VAL_REQUIRED}],
        ) from problem
    if copy_no < 1:
        # 0 is the original delivery record BR-BIL-016 mandates. A "resend" at
        # copy 0 is not a resend; it is a collision with the message the
        # customer already has.
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key=KEY_COPY_NO_REQUIRED,
            field_errors=[{"field": "copy_no", "code": errors.VAL_RANGE}],
        )
    if row.held:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-PAY-018",
            message_key=KEY_RESEND_HELD,
            params={"message_id": str(row.pk), "held_reason": row.held_reason},
        )

    try:
        write = services.queue_document(
            source_type=row.source_type,
            source_id=row.source_id,
            channels=(row.channel,),
            template=services.TemplatePin(
                code=row.template_code,
                template_id=row.template_id,
                version=row.template_version,
                language=row.template_language,
            ),
            account_id=row.account_id,
            recipients=(
                services.Recipient(
                    channel=row.channel,
                    address=row.recipient_address,
                    snapshot=row.recipient_snapshot,
                    unavailable_reason=row.unavailable_reason,
                ),
            ),
            copy_no=copy_no,
            actor=_actor(request),
            # ⚠ `DEF-NOT-4449` — **THE FIGURES TRAVEL WITH THE COPY.** A resend
            # is the SAME letter again (US-NOT-011 TC-3), and until 2026-09-07
            # this call copied the source, the channel, the pin and the
            # recipient snapshot and dropped the one column that holds what the
            # letter SAYS. So a receipt reading *Amount 100.00 USD · Balance
            # after 57.50 USD* was resent as *Amount —— · Balance after ——*,
            # from the same pinned version, with every check green — the row is
            # well formed and the renderer is doing exactly what OQ-117
            # ratified over a context nobody gave it.
            #
            # DECODED on the way out because `queue_document` ENCODES on the way
            # in: `render_context` is stored with its `Decimal`s and dates
            # tagged, and handing the raw column back would re-wrap the tags and
            # print `{'__money__': '100.0000'}` on a customer's receipt.
            render_context=rendering.decode_context(row.render_context) or None,
        )
    except services.QueueWriteRefused as refusal:
        raise _as_catalog_refusal(
            refusal, br_ref="BR-BIL-016", message_key=KEY_QUEUE_REFUSED
        ) from refusal

    created = write.created
    return Response(
        {
            "copied_from": str(row.pk),
            "copy_no": copy_no,
            "messages": [
                {
                    "id": message.id,
                    "channel": message.channel,
                    "status": message.status,
                    # FALSE means this exact copy already existed — a replay, a
                    # double click, a retried request. One letter, not two.
                    "created": message.created,
                    "unavailable_reason": message.unavailable_reason,
                }
                for message in write.messages
            ],
            "created": bool(created),
            "dispatched": False,  # BR-NOT-005 — queueing is not sending
            #: ⚠ The screen needs this to put a confirmation in FRONT of a
            #: clerk. A duplicated 48-hour final notice costs certified postage
            #: and misstates the legal record (BR-CUS-039).
            "is_notice": row.source_type == "notice",
            "problems": [
                *(dict(entry) for entry in write.problems),
                {
                    "code": "resend_reuses_pinned_recipient",
                    "br_ref": "BR-TEN-017",
                    "oq_ref": "OQ-223",
                    "detail": "this copy goes to the address SNAPSHOTTED when the original "
                    "was queued, and renders the template version pinned then "
                    "(BR-BIL-026). Whether a staff resend should instead re-resolve the "
                    "customer's current address — the usual reason a copy is asked for is "
                    "that the first one did not arrive — is OQ-223 and is not decided "
                    "here.",
                },
            ],
        },
        status=201 if created else 200,
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # the clerk who works the failures fixes the typo
def outbound_retry_to(request: Any, message_id: str) -> Response:
    """*Fix address and retry* — DEF-NOT-10650 (PO 2026-10-29, ruling 3B).

    Body: `{"address": "jo.prather@example.com"}`. Queues a NEW message — the
    same document, template version and figures — to the corrected address,
    and changes NOTHING else: the failed message stays as the record and the
    customer's contact is not written. The audit row carries old → new.

    Refused on sent/delivered, queued, complained/unsubscribed and held rows,
    and on channels with no typed address (print, in-app, portal). A replay of
    the same correction finds the earlier click's row (rule 6).
    """
    require_tenant(request)
    row = selectors.row_or_404(message_id)
    payload = _payload(request)

    found = attention.refusal_for(row)
    if found is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-005",
            message_key=KEY_RETRY_TO_REFUSED,
            params={"reason": found[0], "detail": found[1]},
        )
    address = attention.normalise_typed_address(row.channel, payload.get("address"))
    if address is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=KEY_RETRY_TO_ADDRESS,
            field_errors=[{"field": "address", "code": errors.VAL_FORMAT}],
        )
    if address.strip().lower() == (row.recipient_address or "").strip().lower():
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=KEY_RETRY_TO_UNCHANGED,
            field_errors=[{"field": "address", "code": errors.VAL_FORMAT}],
        )
    try:
        outcome = attention.retry_to_address(row=row, address=address, actor=_actor(request))
    except attention.RetryToRefused as refusal:  # pragma: no cover - checked above
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-005",
            message_key=KEY_RETRY_TO_REFUSED,
            params={"reason": refusal.code},
        ) from refusal
    except services.QueueWriteRefused as refusal:
        raise _as_catalog_refusal(
            refusal, br_ref="BR-BIL-016", message_key=KEY_QUEUE_REFUSED
        ) from refusal
    return Response(
        {
            "retried_from": str(row.pk),
            "message": {
                "id": outcome.message_id,
                "channel": outcome.channel,
                "status": outcome.status,
                "held": outcome.held,
            },
            "created": outcome.created,
            "contact_record_changed": False,
            "dispatched": False,  # BR-NOT-005 — queueing is not sending
        },
        status=201 if outcome.created else 200,
    )


# ══════════════════════════════════════════════════════════════════════════
# RETURNED MAIL — 11b §2.9 `POST /deliveries/returned` (US-NOT-014)
# ══════════════════════════════════════════════════════════════════════════
@api_view(["POST"])
@permission_classes([AdminOrClerk])  # US-NOT-014 TC-1: Priya, a clerk, works the S30/S35 stack
def deliveries_returned(request: Any) -> Response:
    """A piece of post came back — single or bulk (US-NOT-014 TC-1/TC-2).

    Body: `{"message_ids": [...], "returned_on": "2026-08-16"}`. The date is
    REQUIRED and is the CALLER's business date (BR-TEN-043) — Tuesday's stack is
    marked as Tuesday even when it is worked on Wednesday.

    TWO THINGS HAPPEN AND BOTH ARE REPORTED:
      1. the queue row is stamped returned and audited (`delivery.returned`).
         The status does NOT move — a returned letter WAS sent, and overwriting
         that would destroy the fact an auditor needs;
      2. the r12 #8 delivery-return event is handed to **payments' own writer**,
         which sets the bad-address flag, the needs-attention row and the S21
         banner (BR-PAY-018 / US-PAY-016). Notifications writes none of that:
         `payments_seam.flag_returned_addresses` calls payments and payments
         writes payments' table (B1).

    **Balances are unaffected** (BR-PAY-018) and nothing here can reach an
    invoice, a payment or a journal line.

    Paper rows only (TC-6): an email that did not arrive comes back as a
    provider BOUNCE on a webhook, which is a fact from an ESP and not something
    a clerk can observe about an envelope. Refused rows come back named.

    Marking the same envelope twice is a no-op on both sides — the queue row
    already carries `returned_at`, and payments' event table is keyed
    `UNIQUE (tenant, outbound_message_id)`.
    """
    require_tenant(request)
    payload = _payload(request)
    message_ids = _message_ids(payload)
    returned_on = _business_date(payload, "returned_on")
    actor = _actor(request)

    try:
        events, refused = delivery_ops.mark_returned(
            message_ids=message_ids, at=_at_midnight_utc(returned_on), actor=actor
        )
    except delivery_ops.DeliveryOpsRefused as refusal:
        raise _as_catalog_refusal(
            refusal, br_ref="BR-PAY-018", message_key=KEY_DELIVERY_REFUSED
        ) from refusal

    flagged, seam_problems = payments_seam.flag_returned_addresses(
        events=events, returned_on=returned_on, actor=actor
    )
    return Response(
        {
            "returned_on": returned_on.isoformat(),
            "marked": [
                {
                    "message_id": event.message_id,
                    "account_id": str(event.account_id) if event.account_id else None,
                    "channel": event.channel,
                }
                for event in events
            ],
            # The BR-PAY-018 half: which accounts payments actually flagged.
            "flagged_accounts": flagged,
            "refused": [dict(entry) for entry in refused],
            "problems": [dict(entry) for entry in seam_problems],
            #: J18's invariance, stated on the response as well as on the audit
            #: trail: money does not move because the post office failed.
            "balances_affected": False,
        }
    )


# ══════════════════════════════════════════════════════════════════════════
# THE NOTICE RECORD + THE CERTIFIED-MAIL REGISTER (US-NOT-009 / US-NOT-010)
# ══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def notices(request: Any) -> Response:
    """What this utility has told its customers — sends AND skips.

    `notice_history` (r12 #7) is PAYMENTS' table; this reads it through
    `payments_seam.notice_history_window`, which resolves payments' published
    functions BY NAME (B1). It had no reader at all until DEF-128: every
    disconnect letter, every medical-hold skip and every certified 48-hour final
    was recorded where no surface could open it.

    ⚠ **THE PAGE IS TAKEN IN THE DATABASE AND THERE IS NO CEILING
    (`NFR-3` · `NFR-5`, `DEF-NOT-5750`, 2026-09-19).** Until today this read
    asked payments for 2,000 rows, built 2,000 dicts and let DRF slice fifty —
    so **the 2,001st notice was unreachable on every page**, `count` was a floor
    rather than a total, and a `notice_history_truncated` problem row said so.
    All three are gone: one `COUNT(*)` and one `LIMIT`/`OFFSET`, whatever the
    record holds. **The copy went with the cap.** A sentence telling a clerk
    where the record stopped is a lie once it stops anywhere, and an honest
    absence outliving the thing it was honest about is the shape hard-won law 2
    warns about.

    Filters: `f.account_id` · `f.notice_type` · `f.tier` · `f.outcome` ·
    **`f.certified=true`**, which is the CERTIFIED-MAIL REGISTER — the 48-hour
    final tier BR-CUS-039 makes certified mail mandatory for. Each row states
    `certified_mail`, and its `certified_number` is NULL with the reason beside
    it: the number arrives on a provider response at dispatch and no provider
    adapter exists on any channel (PO ruling 2026-08-15). A tracking number is
    never fabricated onto a legal record.

    SKIPS ARE INCLUDED BY DEFAULT and that is deliberate (J4 step 2): an account
    excluded for a medical hold must never be indistinguishable from one nobody
    ever chased.

    Money members carry the tenant's currency — see the module docstring.
    """
    require_tenant(request)
    params = selectors.parse_list_params(
        request.query_params, allowed_filters=selectors.NOTICE_FILTERS
    )
    wants_certified = str(params.filters.get("certified", "")).lower() in ("1", "true", "yes")
    window, problems = payments_seam.notice_history_window(
        account_id=params.filters.get("account_id"),
        notice_type=params.filters.get("notice_type"),
        # `f.certified` IS a tier filter — BR-CUS-039 makes certified mail a
        # property of the 48-hour final tier and of no other. Expressed here so
        # a caller cannot ask for "certified" and be handed the 10-day letters.
        tier=selectors.TIER_FINAL_48_HOUR if wants_certified else params.filters.get("tier"),
        outcome=params.filters.get("outcome"),
    )
    currency, currency_problems = selectors.tenant_currency()
    paginator = StandardPagination()
    page = paginator.paginate_queryset(window, request)
    response = paginator.get_paginated_response(
        [selectors.notice_row(row, currency=currency) for row in (page or [])]
    )
    response.data["currency"] = currency
    #: FALSE means the record could not be OPENED — not that no notice was
    #: ever sent. The two must never render the same (DEF-075).
    response.data["available"] = not problems
    response.data["certified_only"] = wants_certified
    response.data["problems"] = [
        *(dict(entry) for entry in problems),
        *(dict(entry) for entry in currency_problems),
        {
            "code": selectors.CERTIFIED_NUMBER_UNAVAILABLE,
            "br_ref": "BR-CUS-039",
            "detail": "no certified-mail tracking number appears on any row. The number "
            "arrives on the print provider's response at dispatch (field map §3, r10 #8) "
            "and no provider adapter exists on any channel — delivery is out of this "
            "release by PO ruling (2026-08-15). The absence is named; a number is never "
            "invented onto a legal record.",
        },
    ]
    return response


# ══════════════════════════════════════════════════════════════════════════
# WHAT IS WAITING TO GO OUT, WHEN NOTHING CAN SEND IT (decision log 2026-09-05)
# ══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AdminOrClerk])  # a code is a credential, not a settings read
def outbound_unsent(request: Any, message_id: str) -> Response:
    """Show me the message nobody could have sent — or say why it is not shown.

    ⚠ **THIS IS NOT `outbound/{id}/document` AND THE TWO MUST NEVER MERGE.**
    That route answers *what did we SEND this customer* and serves the sealed
    copy, never a render (`BR-NOT-027`). This one answers *what is WAITING to
    go, on a channel with nothing behind it* — a different fact about a
    different state, and the reason it exists is that a beta tenant with no
    provider otherwise cannot finish a portal enrolment at all.

    Always 200. A closed gate is `disclosable: false` with no content, because
    *a provider is connected* is a correct state a screen must be able to
    explain rather than an error.

    `AdminOrClerk` rather than the list's `AnyTenantRole`: the queue LIST is a
    settings read an Executive may hold, and a one-time code is a credential
    they have no reason to. This narrows what is already on screen; it widens
    nothing.
    """
    require_tenant(request)
    row = selectors.row_or_404(message_id)  # 404 == cross-tenant == unknown id
    return Response(unsent_preview.preview(row, actor=_actor(request)))


# ══════════════════════════════════════════════════════════════════════════
# THE DO-NOT-SEND LIST — DEF-NOT-5632
# ══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def suppressions(request: Any) -> Response:
    """The blocked-addresses list — every address this utility must not send to.

    ⚠ **PAGINATED, LIKE EVERY LIST IN THIS PRODUCT (`NFR-3`, 11b G5).** The page
    is taken in the DATABASE at the ratified sizes 50/100/200/500/1000, default
    50. There is no shape of tenant for which an unpaginated version of this
    would be correct: the list grows for ever — a released row is KEPT as
    history — and `DEF-PAY-4221` is what an unpaginated list costs when the
    ceiling moves.

    **Active first, newest first.** A released address is history and belongs
    below the thing a clerk came here to act on; `?f.state=released` asks for
    the history on its own and `?f.state=all` for both. Served from
    `suppression.active()` so that *active* means one thing in this module.

    **Three filters, all taken in SQL: `f.state`, `f.channel`, `f.reason`.**
    `f.reason` is one of `vocabulary.reasons` and narrows to nothing when it is
    a word this product does not have — see `suppression.listing` for why that
    is not a fall-back to *all reasons*.

    ⚠ **NO DATABASE ID IS THE VISIBLE VALUE OF A FIELD** (B14 rule 31). `id`
    travels because the Release call needs it, and the screen shows the ADDRESS.
    """
    require_tenant(request)
    rows = suppression.listing(
        state=(request.query_params.get("f.state") or suppression.STATE_ACTIVE).strip().lower(),
        channel=request.query_params.get("f.channel"),
        # ⚠ `f.reason` NARROWS IN THE DATABASE — `DEF-NOT-5637`. The screen
        # offers the four reasons because they are not interchangeable, and a
        # front end that filtered the PAGE it was handed would answer *no
        # complaints* over a tenant whose complaints are on page two.
        reason=request.query_params.get("f.reason"),
    )
    paginator = StandardPagination()
    page = paginator.paginate_queryset(rows, request)
    response = paginator.get_paginated_response(
        [
            {
                "id": str(row.pk),
                "channel": row.channel,
                "address": row.address,
                "reason": row.reason,
                "reason_detail": row.reason_detail,
                "suppressed_at": row.suppressed_at,
                "released_at": row.released_at,
                "released_note": row.released_note,
                #: The screen's own word for the row, computed ONCE here rather
                #: than by the front end reading `released_at` for null — two
                #: places deciding what *blocked* means is how a list and its
                #: own filter come to disagree.
                "state": "released" if row.released_at else "active",
            }
            for row in (page or [])
        ]
    )
    # The vocabulary the screen's filters are built from, served WITH the list
    # for `GET /outbound`'s stated reason: a dropdown built from a hard-coded
    # copy of these tuples is a second home for the reason set.
    response.data["vocabulary"] = {
        "reasons": list(suppression_models.REASONS),
        "channels": list(models.CHANNELS),
        "states": list(suppression.STATES),
    }
    return response


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # the clerk who corrected the typo is the one who releases
def suppression_release(request: Any, suppression_id: str) -> Response:
    """**Release** — let this address through again (the PO asked for it by name).

    Body: `{"note": "typo, corrected on the account", "released_on":
    "2026-09-17"}`. The date is the CALLER's business date (`BR-TEN-043`), like
    `POST /deliveries/returned` one screen over; the note is optional and is the
    one field in this table that is a person's own words.

    TWO THINGS HAPPEN AND BOTH ARE REPORTED:
      1. the suppression is stamped released and **KEPT** — this is not a
         delete, because *why did this customer stop getting email in March* has
         to stay answerable after `audit_log` is pruned;
      2. every queue row held BY THIS RULE for that address becomes selectable
         again. Nothing is re-rendered and nothing is re-created — the same
         rows, the same pins, the same recipient snapshots
         (`delivery_ops.release_held_for_accounts`' ratified shape).

    Releasing twice is refused rather than silently accepted: a clerk pressing
    Release a second time should be told the second press did nothing.

    ⚠ **THIS IS THE ONLY DOOR OUT, AND IT IS A PERSON'S DOOR.** Nothing
    automatic releases an address — an automatic un-suppression is a policy
    nobody has ruled, and `RB-122`'s own *Re-enable when the contact is updated*
    parameter is recorded as having nothing to watch. A clerk deciding that an
    address is good again is the whole mechanism.
    """
    require_tenant(request)
    payload = _payload(request)
    note = payload.get("note")
    if note is not None and not isinstance(note, str):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key=KEY_PAYLOAD)
    # ⚠ `released_on` IS REQUIRED AND IS THE CALLER'S BUSINESS DATE
    # (`BR-TEN-043`) — nothing in this module reads a wall clock and G6 greps
    # for it. It is validated HERE rather than through `_business_date` for one
    # reason, recorded so the next lane does not "tidy" it back:
    # `_business_date` refuses with `KEY_RETURNED_DATE`, whose catalogue entry
    # reads *"Enter the date the mail came back"* — which is TRUE of a returned
    # envelope and FALSE on this screen, where a clerk is letting an email
    # address through. Wrong copy reaching a clerk is `DEF-322`'s shape.
    #
    # ⚠ **IT HAS ITS OWN KEY SINCE 2026-09-17 — `DEF-NOT-5641`, CLOSED BY THE
    # `DEF-NOT-5637` SCREEN LANE**, which was already in all eleven catalogues
    # and so paid the G15-parity cost once instead of twice. It used to refuse
    # through the module's generic delivery key: generic, not FALSE, and unable
    # to tell a clerk WHICH field was missing. The precise sentence no longer
    # has to travel in `params.detail`, which is the diagnostic and is
    # deliberately not rendered (BR-SHL-020 r2).
    raw_date = payload.get("released_on")
    try:
        released_on = date.fromisoformat(str(raw_date)[:10])
    except (TypeError, ValueError) as problem:
        raise _as_catalog_refusal(
            suppression.SuppressionRefused(
                "a release needs the business date it happened on, as a calendar date "
                "(BR-TEN-043). Nothing here is dated from the server's clock, because the "
                "server's day is not necessarily the utility's."
            ),
            br_ref="BR-TEN-043",
            message_key=KEY_RELEASE_DATE,
        ) from problem
    try:
        row = suppression.release(
            suppression_id=suppression_id,
            actor=_actor(request),
            at=_at_midnight_utc(released_on),
            note=(note or None),
        )
    except suppression.SuppressionRefused as refusal:
        # The ONE catalog exception G9 allows at this layer, with the module's
        # existing delivery key: a release refused IS a delivery action refused,
        # and a new key would be a twelfth catalogue entry saying what
        # `notifications.delivery.refused` already says in eleven languages.
        raise _as_catalog_refusal(
            refusal, br_ref="BR-NOT-005", message_key=KEY_DELIVERY_REFUSED
        ) from refusal
    return Response(
        {
            "id": str(row.pk),
            "address": row.address,
            "channel": row.channel,
            "state": "released",
            "released_at": row.released_at,
            "released_note": row.released_note,
        }
    )


urlpatterns = [
    # Order matters: `outbound/summary` and `outbound/requeue` are LITERAL
    # segments and must be declared before nothing at all — there is no
    # `outbound/<id>` pattern to shadow them, and none may be added without
    # moving these two above it.
    path("outbound", outbound),
    path("outbound/summary", outbound_summary),
    path("outbound/requeue", outbound_requeue_bulk),
    # DEF-NOT-10650 — a literal segment; no `outbound/<id>` pattern shadows it.
    path("outbound/selection", outbound_selection),
    path("outbound/<str:message_id>/requeue", outbound_requeue),
    path("outbound/<str:message_id>/resend", outbound_resend),
    path("outbound/<str:message_id>/unsent", outbound_unsent),
    path("outbound/<str:message_id>/retry-to", outbound_retry_to),
    path("deliveries/returned", deliveries_returned),
    path("notices", notices),
    # DEF-NOT-5632 — the do-not-send list and its one door out. `suppressions`
    # is a literal segment and `<str:suppression_id>/release` cannot shadow it.
    path("suppressions", suppressions),
    path("suppressions/<str:suppression_id>/release", suppression_release),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-013@6c2a90f (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-04-delivery-ops.md — US-NOT-013 §1/§3/§5 + US-NOT-014 §1/§3/§5 + the S8 capability matrix — · 10-notifications/02-business-rules.md — BR-NOT-005 — · 04-docs/01-spec/11b-api-audit.md §2.13 + §2.9 · 08-qa/01-e2e/journeys/J18-returned-mail-tuesday.md; co-packets US-NOT-014, US-NOT-001 and US-NOT-009, same four sources)
# generated: 2026-08-16 by story-coder (DEF-128 notifications API lane — the routes 7,084 lines of engine had never had)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_def_128_notifications_api.py (RED-PROVED FIRST: django.urls.exceptions.Resolver404 on every one of the seven paths and AttributeError on every view name — verbatim in the lane report and in 12-governance/02-decision-log.md) · pytest tests -m isolation✔ · run_gates✔ including the NEW G25, which was itself red-proved against this module BEFORE a route existed · openapi/schema.json REGENERATED (BE-11 TC05 diffs it)
# exceptions: (1) THERE IS NO SEND ENDPOINT AND THERE MUST NEVER BE ONE (A11 r2 §4, BR-NOT-005) — every route here queues, lists or moves a row between queue states, and the dispatcher is the only sender.
#         (2) `copy_no` IS REQUIRED ON THE RESEND and a missing one is a 422 naming the field. Allocating it here would post a second letter on every double click while looking correct (hard rule 6); with it stated, the DATABASE refuses the duplicate. A replay answers 200 + `created:false`, not 409 — a staff double-click is not one of 11b G7's four enumerated operations, the same call `apps/payments/api.py` records for BR-PAY-028.
#         (3) A RESEND REUSES THE PINNED RECIPIENT SNAPSHOT (BR-TEN-017) AND OQ-223 IS RAISED, NOT ANSWERED: whether a staff resend should re-resolve a customer's current address is unruled, and every resend response carries the OQ-ID rather than letting a clerk discover it.
#         (4) NO NOTICE-GENERATION ENDPOINT. `POST /accounts/{id}/notices` (11b §2.6 S22 modal 5) and `POST /collections/notices` (§2.9 S34 bulk) are the CUSTOMERS' and PAYMENTS' doors to `apps/notifications/notices.py`, and `apps/customers/services.send_disconnect_notice` refuses today naming OQ-133/136/137. Minting a second door here would be this module deciding where an account stands on a ladder it does not own — the prime directive's exact prohibition. The generation service is REACHABLE THROUGH ITS RECORD (`GET /notices`) and its output (`GET /outbound`), which is what DEF-128 asked for.
#         (5) `GET /notices` SERVES `available:false` RATHER THAN AN EMPTY LIST when payments publishes no read. A record that cannot be opened and a customer who was never contacted must never render the same (DEF-075's shape).
#         (6) THE RETURNED-MAIL INSTANT IS MIDNIGHT UTC (OQ-153, CLOSED to the utility's own timezone and blocked in practice by DEF-082 — no tenant has a timezone to read). The DATE is preserved either way and is what BR-PAY-018 and every auditor read; `apps/payments/api._moment` anchors the same way for the same reason.
#         (7) NO EXPORT ROUTE. The S8 capability row's CSV rides the platform `POST /api/exports` (US-SHL-008 / IS-9) and `outbound` is not yet a REGISTERED exportable resource — REPORTED (DEF-135 names the same gap for invoices, payments, reads and audit) rather than mounted as a second download pipeline.
#         (8) RE-QUEUE IS SystemAdminOnly AND MARK-RETURNED/RESEND ARE AdminOrClerk. Not a guess: US-NOT-013 §4's actors are *"Alex Reed; Priya Menon (view)"* and the dispatch home is a SETTINGS surface (A4: System Admin Full, Clerk —), while US-NOT-014 TC-1 has Priya — a clerk — marking a letter returned from S30, and US-NOT-011 §5 puts the re-send on S35. Both screens are Full for a clerk.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
