# ── Trace ──────────────────────────────────────────────
# Change:   CR-137-BRC07 · P3.1 · P3.2 · P3.3 · P3.4 · P3.19 — the four doors a
#           payment has never had, and the fifth that hands a counter customer
#           paper. Blueprint `05-prototype/06 Payments Page Blueprint.pdf`
#           screen 2·2 (p035) and the modals 2·3d (p043) / 2·3h (p049).
# Story:    US-PAY-004 (S33 · §1 *"Cancel only while processing"* · TC-2 · TC-7
#           the isolation case that has always named a detail URL) ·
#           US-PAY-025 (the receipt) · US-NOT-011 §5 (the re-send)
#           Screens: S33 · S35 · 2·2 · 2·3d · 2·3h
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money is a
#           decimal STRING) · hard rule 4 · hard rule 5 · hard rule 6 · hard
#           rule 7 · `NFR-3` (the history is paginated in the DATABASE) ·
#           BR-SHL-011 (URL grammar) · BR-SHL-025 (server-enforced RBAC) ·
#           BR-TEN-043 / G6 (the caller names the moment; nothing reads a clock)
#           · B14 rule 31 (the address carries the `PMT-` number)
# Tests:    06-backend/tests/test_cr137_p3_detail_cancel_receipt.py
# Impacts:  apps/payments/api.py (ONE include line at the end of its
#           `urlpatterns` — see THE SHADOWING ANALYSIS below) ·
#           apps/payments/payment_detail.py · cancel.py · receipt_resend.py ·
#           07-frontend/src/features/payments/paymentDetail.tsx (P3.9/P3.10 make
#           it a page and delete the row panel in one commit)
# ───────────────────────────────────────────────────────
"""The five doors screen 2·2 opens — `GET /payments/{id}` and what it can do.

Its own module rather than more lines in `apps/payments/api.py`, on the
`reversal_api` / `refunds_api` / `amendments_api` precedent and for hard-won law
11's reason: a 1,778-line file eight lanes are live in is where a pathspec
commit eats somebody's work.

THIN BY LAW. Every write goes through a service — `cancel.cancel_payment`,
`receipt_resend.resend_receipt` — and every read through
`payment_detail`. **No ORM, no figure and no rounding in this file.**

THE ROUTES
══════════
    GET  /payments/{id}                  the payment, at its own address
    GET  /payments/{id}/history          its trail, paginated IN SQL
    POST /payments/{id}/cancel           undo one taken by mistake
    POST /payments/{id}/receipt          send the receipt again
    GET  /payments/{id}/receipt/document paper, rendered, now

`{id}` IS THE `PMT-` NUMBER **OR** THE UUID, AND THE NUMBER IS THE POINT
════════════════════════════════════════════════════════════════════════
p035 draws the address as `/:tenant/payments/PMT-2609-000418`. B14 rule 31 —
*no database id is ever the visible value of a field* — and an address a clerk
pastes into a message to a colleague is the most visible value on the screen.
`payment_detail.resolve_payment` takes either spelling; the front end links with
the number and every existing caller inside the product keeps its ids.

**Neither spelling widens what a caller can see** — both are filtered to the
current tenant before anything else, with RLS FORCE underneath. US-PAY-004 TC-7
is ratified and is what this obeys: another tenant's payment in the detail URL
is **404**, never 403, so existence never leaks (HR-1 / G4).

⚠ THE SHADOWING ANALYSIS, BECAUSE `payments/<id>` IS THE WIDEST PATTERN IN
   THE MODULE
═══════════════════════════════════════════════════════════════════════════
`payments/<str:payment_id>` is a TWO-segment pattern and three literal
two-segment patterns already exist: `payments/summary`, `payments/reason-codes`
and `payments/selection-total`. **Declared before this include, they win;
declared after it, the word "summary" resolves as a payment number and a clerk
opening the S33 summary gets a 404 on a payment that never existed.** That is
the identical trap `apps/payments/api.py` records above `deposit-batches/cut`.

So this module is included from the END of `apps.payments.api.urlpatterns`,
after all three, and `test_cr137_p3_detail_cancel_receipt` asserts all three
still resolve to their own views — **a comment claiming an ordering is not the
ordering** (hard-won law 1).

Everything else under `payments/<id>/…` is three or four segments
(`reverse`, `correct-reference`, `move`, `reapply`, `cheque/void`) and cannot
collide with a two-segment pattern at all. `receipt/document` is four and sits
under `receipt`'s three, which is a different whole pattern.

WHO MAY DO WHAT
═══════════════
* the two READS and the RESEND are `AdminOrClerk` — US-NOT-011 §5 puts the
  re-send on S35, *a clerk's screen*, and a payment's own page is the S33 row
  opened up;
* **CANCEL is `AdminOrClerk` too, and that is deliberate rather than an
  oversight.** Reverse is `SystemAdminOnly` because BR-PAY-1070 says so and
  because it moves money that reached the books. A cancel is *"I just took that
  from the wrong person"* thirty seconds later, on money that has not arrived
  and has posted nothing — the clerk who made the mistake is exactly the person
  who should fix it, and a two-person utility has nobody else at the counter.
  The asymmetry is the blueprint's own: p044 calls Cancel *"for the clerk who
  has just made a mistake"* and 2·3e marks Reverse *"Staff, and narrower than
  the rest — `SystemAdminOnly`"*.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import cancel, payment_detail, receipt_resend
from apps.payments.exceptions import PaymentRuleError
from core import errors  # noqa: F401 — the catalog this file's refusals come from (G9)
from core.pagination import StandardPagination
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant

# `_payload` and `_required_moment` are imported rather than restated:
# `_required_moment` is the G6 no-clock helper (BR-TEN-043 — *"posting and
# actual dates can differ; ask actual date to user"*), and a second copy of a
# rule that bans reading the server clock is a second place for it to drift back
# in. ⚠ `_actor` is NOT imported — `reversal_api` records why at length: it
# returns `request.user`, whose `.role` is attached by the identity layer as it
# passes and is not a property of the row.
from apps.payments.api import _payload, _required_moment

#: The i18n keys this file's refusals carry. Named once so the catalogue diff
#: and the code can be read against each other in one grep — G18 compares them
#: in both directions and G32 fails a key no catalogue answers, which is how a
#: refusal reaches a clerk as SILENCE.
KEY_REFUSED = "payments.detail.refused"


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id AND role.

    The role is server-attached by the identity layer (BE-04) and is never
    client input (BR-TEN-003). `audit_log.actor_user_id` is hard rule 7's
    evidence half, so `id` comes from the session user and from nowhere else.
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows.

    ⚠ **THE `message_key` IS RESOLVED AT THE RAISE SITE, WHICH IS WHAT G32
    CANNOT DO FOR US.** G32 reports a key unresolved only where the helper is
    DEFINED IN THE SAME FILE; a module that imports its helper from a sibling
    is invisible to it, and it reported **0 unresolved over 21 live refusals
    that reach a clerk as silence**. So `KEY_REFUSED` is declared in this file,
    beside the raise, and `test_cr137_p3_detail_cancel_receipt` asserts it
    resolves in `en.json` — a validator at the raise site, which is the only
    thing that found G32's blind spot.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-002",
        message_key=KEY_REFUSED,
        params={"detail": str(refusal)},
    )


def _payment_or_404(reference: str) -> Any:
    """This tenant's payment, or **404** — for BOTH reasons, indistinguishably.

    `deny_as_not_found` is the repo's own form (HR-1 / G4, and
    `bankrec_read._batch`'s precedent): a payment that does not exist and
    another tenant's payment answer the same body, so existence never leaks.
    US-PAY-004 TC-7 is the ratified case and names this URL.
    """
    payment = payment_detail.resolve_payment(reference)
    if payment is None:
        raise errors.deny_as_not_found()
    return payment


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def payment(request: Any, payment_id: str) -> Response:
    """`GET /payments/{id}` — one payment, at its own address (P3.1).

    **This is what a payment had no address for.** `paymentDetail.tsx` says so
    in its own words and lists the three things a page would need; this is the
    first, and `P3.9` is the other two.

    The body is `PaymentRow` — the same builder `GET /payments` uses, so the
    page and the list can never print different figures — plus the header strip
    (`source`, `reconciled`), the four controls' own preconditions (`actions`),
    the receipt rows the Resend modal draws its ① from, and `unavailable[]`.

    **The history is NOT in this body.** It is the one member that has to be
    paginated, and a paginated member inside an unpaginated body is exactly how
    an unbounded read hides (`NFR-3`). `GET /payments/{id}/history` serves it.
    """
    require_tenant(request)
    return Response(payment_detail.payment_detail(_payment_or_404(payment_id)))


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def payment_history(request: Any, payment_id: str) -> Response:
    """`GET /payments/{id}/history` — WHEN · WHAT · WHO · NOTE (P3.4).

    **This is what makes Cancel honest: a cancelled payment does not vanish.**
    The original keeps its row, its number and its amount, its status reads
    `cancelled`, and this says who did it and when.

    ⚠ **PAGINATED IN THE DATABASE** (`NFR-3`). `payment_detail.history_queryset`
    hands back a QuerySet that audit ordered on `ix_audit_entity`, and
    `StandardPagination` puts the `LIMIT/OFFSET` in the SQL. A busy payment's
    trail is unbounded — a recording, an allocation, a batch seal, a
    reconciliation, a correction, a resend, a cancel — and
    `apps/metering/connection_reads._history` materialising its whole trail is
    the shape this deliberately does not copy.

    ⚠ **IT NEVER CLAIMS PERMANENCE, AND IT SAYS NOTHING ABOUT WHY.**
    `audit_log` is pruned and no row type is exempt (PO ruling 2026-09-23,
    `OQ-1340` CLOSED). B14 rule 33 puts rationale at ZERO words on screen, so
    the fact travels as the `unavailable[]` CODE on the detail read and the
    panel explains no retention policy — a screen that explained it in order to
    be honest would break rule 33 while trying to obey the ruling.
    """
    require_tenant(request)
    found = _payment_or_404(payment_id)
    rows = payment_detail.history_queryset(found)
    paginator = StandardPagination()
    page = paginator.paginate_queryset(rows if rows is not None else [], request)
    return paginator.get_paginated_response(
        payment_detail.history_rows(page or [], found.tenant_id)
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # see WHO MAY DO WHAT in the module docstring
def payment_cancel(request: Any, payment_id: str) -> Response:
    """`POST /payments/{id}/cancel` — undo a payment taken by mistake (P3.2).

    The body is 2·3d's modal:

        reason         REQUIRED — the *Why* field, one of `cancel.CANCEL_REASONS`
        note           optional — *"What happened, in your words"*
        cancelled_on   REQUIRED — the caller's moment, never a clock (G6)

    **201 on a new cancel, 200 on a replay**, both carrying the reversing row's
    own `PMT-` number and `created`. A second click is the same act, not a new
    one: `cancel_payment` finds the payment already `cancelled` and answers with
    the first cancel rather than a 409 — *"a 409 toast for a button that worked
    is a wrong answer a clerk would act on"*.

    ⚠ **A CLEARED PAYMENT IS REFUSED AND THE REFUSAL NAMES REVERSE.** That is
    `P3.13`'s assertion and it is the point of the whole phase: Cancel and
    Reverse are one word to a clerk and two acts to the ledger. A bare *"cannot
    cancel"* leaves somebody holding a returned cheque with nowhere to go.

    `problems[]` travels verbatim and is not decoration here: it is where the
    cancel reports that **nothing was unposted and no bill re-opened**, because
    a `processing` payment reached neither. A screen that implied a bill moved
    would be describing a different act.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = cancel.cancel_payment(
            actor=_actor(request),
            payment_id=_payment_or_404(payment_id).pk,
            reason=payload.get("reason"),
            note=payload.get("note"),
            cancelled_on=_required_moment(payload, "cancelled_on"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    body = {
        "payment_id": result.payment_id,
        "payment_no": result.payment_no,
        "created": result.created,
        "status": result.status,
        "amount": result.amount,
        "currency": result.currency,
        # B14 rule 31 — the NUMBER a clerk reads. The id rides beside it for the
        # screen's own navigation, never as the value of a field.
        "reversing_payment_no": result.reversing_payment_no,
        "reversing_payment_id": result.reversing_payment_id,
        "reason": result.reason,
        "problems": list(result.problems),
    }
    return Response(body, status=201 if result.created else 200)


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # US-NOT-011 §5 — the re-send lives on a clerk's screen
def payment_receipt(request: Any, payment_id: str) -> Response:
    """`POST /payments/{id}/receipt` — send the receipt again (P3.3).

    The body is 2·3h's modal:

        channels   REQUIRED — `pdf_print` · `email` · `sms`, the three a receipt
                   goes out on. The drawing's *Send by* chips.
        copy_no    REQUIRED — and it is the whole idempotency guarantee
                   (hard rule 6). `GET /payments/{id}` serves `next_copy_no`, so
                   the number the clerk submits is the number the server just
                   showed them; a double-click resubmits it, collides with its
                   own row in the DATABASE and comes back `created: false`.
                   An endpoint that allocated the number itself would post a
                   second receipt on every double-click while looking perfectly
                   correct — `apps/notifications/api.py` records that argument
                   in full and this door obeys the same rule.

    **Nothing about the payment changes** (p050's act table: *Resend · a queue
    row · the ledger: Nothing*), and `problems[]` says so on every call.

    This RE-QUEUES AN EXISTING DOCUMENT. A channel this payment has no receipt
    on is refused by name rather than composed here — templates, channels and
    queue all exist, and building a second receipt path is what the PO ruled out
    on 2026-09-22.
    """
    require_tenant(request)
    payload = _payload(request)
    found = _payment_or_404(payment_id)
    try:
        result = receipt_resend.resend_receipt(
            actor=_actor(request),
            payment=found,
            channels=payload.get("channels"),
            copy_no=payload.get("copy_no"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "payment_id": result.payment_id,
            "payment_no": result.payment_no,
            "copy_no": result.copy_no,
            "queued": list(result.queued),
            "problems": list(result.problems),
        },
        # 201 when at least one NEW row was written; 200 when every channel
        # found its own row already there, which is a replay and not a failure.
        status=201 if any(one.get("created") for one in result.queued) else 200,
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def payment_receipt_document(request: Any, payment_id: str) -> Response:
    """`GET /payments/{id}/receipt/document` — paper at the window (P3.19).

    *"The queue is asynchronous; a counter needs a receipt in hand now."*

    ⚠ **IT IS A READ AND IT MINTS NO SEND ENDPOINT.** A11 Addendum r2 §4 —
    *"no synchronous send endpoint anywhere (queue only, BR-NOT-005)"* — and
    `apps/notifications/api.py` states that minting one is a gate failure. This
    renders a row that is ALREADY QUEUED, through notifications' own
    `render_for_dispatch` and its PINNED version (BR-BIL-026), and dispatches
    nothing: the queued row keeps its place and the print job will still take
    it. A customer standing at the counter has no address to resolve and no
    provider to hand off to; the delivery is a person taking a piece of paper.

    `receipt_resend`'s module docstring holds the whole argument and
    `12-governance/02-decision-log.md` holds the ruling, because the drawing
    does not settle it.

    The body is TEXT, not a PDF — `rendering.py`'s own exception (2), `OQ-149`
    CLOSED 2026-08-12: no page-rendering library is in the image and printable
    classes render their text body. The browser's print dialog does the rest.
    """
    require_tenant(request)
    found = _payment_or_404(payment_id)
    try:
        return Response(
            receipt_resend.counter_receipt_document(actor=_actor(request), payment=found)
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def payment_receipt_print(request: Any, payment_id: str) -> Response:
    """`GET /payments/{id}/receipt/print` — the one-page counter receipt's facts.

    PO 2026-10-30, Q3 = A: *Print receipt* opens a one-page receipt in the
    browser to print now. A READ: nothing is queued, sent or changed —
    `receipt_print`'s docstring says where each field comes from. `DEF-PAY-10743`.
    """
    from apps.payments import receipt_print

    require_tenant(request)
    return Response(receipt_print.print_receipt(_payment_or_404(payment_id)))


urlpatterns = [
    # ⚠ **ORDER IS LOAD-BEARING WITHIN THIS LIST TOO.** The three- and
    # four-segment patterns are declared FIRST so that `payments/<id>` — the
    # widest pattern in the module — is the last thing Django tries. See THE
    # SHADOWING ANALYSIS in the module docstring for why this whole list must be
    # included at the END of `apps.payments.api.urlpatterns`.
    path("payments/<str:payment_id>/receipt/document", payment_receipt_document),
    path("payments/<str:payment_id>/receipt/print", payment_receipt_print),
    path("payments/<str:payment_id>/receipt", payment_receipt),
    path("payments/<str:payment_id>/cancel", payment_cancel),
    path("payments/<str:payment_id>/history", payment_history),
    path("payments/<str:payment_id>", payment),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-137-BRC07 §3 P3.1 · P3.2 · P3.3 · P3.4 · P3.19 ·
#         05-prototype/06 Payments Page Blueprint.pdf pp.18–20, p035, p043–p044,
#         p049–p050 (on this branch since `da07c7f8d`) ·
#         04-docs/05-modules/08-payments/06-epics/EP-PAY-01 US-PAY-004 §1 + TC-2
#         + TC-7 · 04-docs/01-spec/11-api-contracts.md Addendum r2 §4 ·
#         apps/payments/reversal_api.py (the door precedent) · CLAUDE.md hard
#         rules 1, 2, 4, 5, 6, 7 · B14 rules 31, 33, 35 · NFR-3
# generated: 2026-09-23 by the CR-137 P3-BACK lane
# checklist: A✔ B=deferred(P3.9–P3.12 own screen 2·2 and the three modals) C✔
#            D✔ E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 ⚠ **THIS READ *"the blueprint PDF is NOT on this branch"* WHILE THIS LANE
#      WAS BUILDING, AND IT IS NO LONGER TRUE.** It was true at the pinned tip and
#      the drawing was read from `origin/claude/confirm-understanding-3ktufc`;
#      `da07c7f8d` put it on THIS branch at `05-prototype/06 Payments Page
#      Blueprint.pdf`, 2,905,141 bytes, sha256 `0cc31baf…`, and the copy read here
#      is byte-identical to it. `DEF-PAY-6230` is CLOSED. Read it from the branch.
#   E2 `POST /payments/{id}/cancel` is `AdminOrClerk` while
#      `POST /payments/{id}/reverse` is `SystemAdminOnly`. Deliberate, and the
#      blueprint's own asymmetry — see WHO MAY DO WHAT.
#   E3 NO `idempotency_key` on cancel: the STATUS is the guard and it is
#      stronger (`cancel.py` E5). The RESEND does require `copy_no`, which is
#      the same discipline one table along.
#   E4 `openapi/schema.json` IS regenerated, and it carries FAR more than these
#      five routes — say so plainly, on the `apps/payments/api.py` precedent.
#      **TC-05 was ALREADY RED at the tip this lane started from**, by 49 paths
#      and 26 changed bodies: the snapshot was last regenerated 2026-09-16
#      (`fdcd02682`) and routes have landed since 2026-09-18 (`3d37b2ce4`).
#      Every path it gains derives from code already COMMITTED on the branch, so
#      no lane's in-flight work is published. Dated and measured in
#      `DEF-GOV-6232`, which also records the OTHER red: TC-02's public-route
#      list names 4 of the 48 routes that are public today, and this lane did
#      NOT touch it — that list is a review in its own right.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
