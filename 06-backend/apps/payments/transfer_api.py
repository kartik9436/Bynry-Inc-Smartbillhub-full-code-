# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-8 (task 31) — the ONE cross-account transfer writer's
#           door · CS-32 (task 39) — move a payment to another account.
# Story:    US-PAY-011 (the refund path CS-8 unblocks) · US-PAY-010
#           Screens: S21 (Transfer, and both accounts showing a move AS a move)
#           · S58 (the offset-first step) · S35 (the Move modal)
# Rules:    BR-PAY-864..867 · BR-PAY-1070 (a reversal is Admin-only, so a MOVE
#           is too — the door mirrors the service and is never wider) ·
#           BR-SHL-025 (server-enforced RBAC) · BR-TEN-043 / gate G6 (the caller
#           names the day; nothing here reads a clock) · CLAUDE.md hard rule 6
#           (a submit token, required)
# Tests:    06-backend/tests/test_cr059_cs8_transfer.py ·
#           06-backend/tests/test_cr059_cs32_move_payment.py
# Impacts:  apps/payments/api.py's urlpatterns (one `include`) ·
#           apps/payments/transfer.py (the writer; no logic lives here)
# ───────────────────────────────────────────────────────
"""The two doors on money crossing two accounts.

    POST /accounts/{id}/transfers          CS-8 · move this account's credit
    GET  /accounts/{id}/transfer-preview   CS-8 · what it would do
    POST /payments/{id}/move               CS-32 · this was the wrong account
    GET  /payments/{id}/move-preview       CS-32 · what it would do

Its own module rather than more lines in `apps/payments/api.py`, on the
`refunds_api` / `reversal_api` precedent and for hard-won law 11's reason: a
1,500-line file several lanes edit is where a pathspec commit eats somebody's
work.

**THIN BY LAW.** The writes go through `apps/payments/transfer.py`, which is the
sole writer of a cross-account movement, and the previews through the same
module's own read functions. **No ORM, no figure and no rounding in this file.**

═══════════════════════════════════════════════════════════════════════════════
EVERY MONEY FIGURE IS A DECIMAL STRING, AND THE SCREEN DOES NOT PARSE IT
═══════════════════════════════════════════════════════════════════════════════
CLAUDE.md rule 2: money travels as the stored decimal beside its CHAR(3) code,
never as a number and never as cents. `selectors._decimal_str` is what produces
it everywhere else in this module and it is what produces it here, through
`selectors.transferred_money_dict`.

═══════════════════════════════════════════════════════════════════════════════
THE TWO DOORS HAVE DIFFERENT GATES, AND THE DIFFERENCE IS A RULE
═══════════════════════════════════════════════════════════════════════════════
**A TRANSFER is `AdminOrClerk`.** It moves a customer's own credit between two
of that customer's own accounts; nothing leaves the utility and no bill is
re-opened on a customer who did nothing. It is the operational half of the same
job BR-PAY-020 calls operational for a write-off request.

**A MOVE is `SystemAdminOnly`.** Its source leg IS `reversal.reverse_payment`,
which has carried `@require_role(SYSTEM_ADMIN)` since BR-PAY-1070 was ruled on
2026-09-01, so the door cannot be wider than the service behind it — a Billing
Clerk promised a reach the service denies meets a 403 from a layer they cannot
see, which is `refunds_api`'s own argument. **What that costs, stated rather
than discovered: the clerk who recorded the cheque against the wrong Patel
cannot be the one who corrects it**, and the screen lane must render Move
**visible and disabled with its reason** for a clerk rather than hiding it
(BR-SHL-025).

═══════════════════════════════════════════════════════════════════════════════
`idempotency_key` IS REQUIRED ON BOTH WRITES
═══════════════════════════════════════════════════════════════════════════════
A double-clicked Transfer would otherwise move the money twice and a
double-clicked Move would try to reverse an already-reversed payment. The form
mints the token and these doors refuse without one — never generated here,
because a key the server invented would differ on the second submit and would
dedupe nothing while looking as though it had (OQ-127's argument).

A REPLAY ANSWERS **200** WITH THE FIRST MOVEMENT AND `created: false`, not 409:
*"a 409 toast for a button that worked is a wrong answer a clerk would act on"*
(`account_payments`), and 11b §3 G7's four 409 operations are bill runs,
imports, webhooks and tenant provisioning — a staff double-click is none of them.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import selectors, transfer
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.permissions import AdminOrClerk, SystemAdminOnly
from core.tenancy import require_tenant

# `_payload` and `_required_moment` are imported rather than restated:
# `_required_moment` is the G6 no-clock helper (BR-TEN-043) and a second copy of
# a rule that bans reading the server clock is a second place for it to drift
# back in. `_actor` is deliberately NOT imported — see below.
from apps.payments.api import _payload, _required_moment


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id AND role.

    The same shape `refunds_api._actor` and `reversal_api._actor` build, and
    deliberately a third definition rather than an import of either: both writes
    behind this module are `@require_role`-gated, and `apps/payments/api._actor`
    returns `request.user`, whose `role` is attached by the identity layer only
    as a side effect. The role this layer is entitled to read is the one the
    server attached to the REQUEST.
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows.

    One code (422 `BIZ_COMPLETENESS`) for all of them, because every refusal
    that arrives here has the same shape and picking among the nine BIZ codes
    per refusal would be this layer interpreting rules it does not own.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-864",
        message_key="payments.transfer.refused",
        params={"detail": str(refusal)},
    )


def _required_amount(payload: dict[str, Any]) -> Decimal:
    """The amount to move, as a Decimal. A float is REFUSED, never converted.

    Hard rule 2 at the boundary, which is the only place a float can still be
    seen for what it is: once it is inside the service it is already a value
    that may not be exactly what the clerk typed.
    """
    raw = payload.get("amount")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.amount_required",
            field_errors=[{"field": "amount", "code": errors.VAL_REQUIRED}],
        )
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        )
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        ) from bad


def _required_text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.reason_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    return value.strip()


def _required_idempotency_key(payload: dict[str, Any]) -> str:
    key = payload.get("idempotency_key")
    if not isinstance(key, str) or not key.strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.record.idempotency_key_required",
            field_errors=[{"field": "idempotency_key", "code": errors.VAL_REQUIRED}],
        )
    return key.strip()


def _required_query_date(request: Any, name: str) -> date:
    raw = request.query_params.get(name)
    if not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.date_required",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _required_body_date(payload: dict[str, Any], name: str) -> date:
    raw = payload.get(name)
    if not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.date_required",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


# ══════════════════════════════════════════════════════════════════════════
# CS-8 · the credit transfer
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_transfer_preview(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/transfer-preview?to=&amount=` — BR-PAY-866's *before*.

    A GET, because it writes nothing and changes nothing: the same read may be
    taken twice, by two clerks, with no consequence.

    Answers what the money will MEET on the destination — bill by bill, in that
    tenant's own order — what will carry as credit, and what the source will hold
    afterwards. CS-31's own note is why it is a server read rather than a screen
    sum: *"It must be computed by the service, not assembled on the screen, or
    the warning and the outcome can disagree."*
    """
    require_tenant(request)
    destination = request.query_params.get("to")
    if not destination:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.destination_required",
            field_errors=[{"field": "to", "code": errors.VAL_REQUIRED}],
        )
    raw_amount = request.query_params.get("amount")
    if not raw_amount:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.amount_required",
            field_errors=[{"field": "amount", "code": errors.VAL_REQUIRED}],
        )
    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        ) from bad
    try:
        return Response(
            transfer.preview_credit_transfer(
                source_account_id=account_id,
                destination_account_id=destination,
                amount=amount,
            )
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_transfers(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/transfers` — CS-8, the keystone (S21 · S58).

    The body is the Transfer modal:

        to_account_id    the sibling account — REQUIRED
        amount           a decimal STRING; a float is refused (rule 2)
        moved_on         the caller's business day — REQUIRED, never a clock
        reason           REQUIRED free text; the audit row is the only durable
                         record of why a customer's money moved
        memo             optional, written on both legs
        idempotency_key  the modal's submit token — REQUIRED

    **201 on a new transfer, 200 on a replay**, both carrying both legs and
    `created`.

    ⚠ **THIS DOOR DOES NOT OFFSET A REFUND AUTOMATICALLY, and that is the lane
    judgment recorded on 2026-09-03 rather than an omission.** `refunds.
    request_refund` still REFUSES when the customer owes elsewhere and names the
    arrear; a person then opens this door and presses Transfer. Making the
    refund path call this one would move a joint holder's money with nobody
    looking, which is the risk OQ-135's own option (b) was written against.
    """
    require_tenant(request)
    payload = _payload(request)
    destination = payload.get("to_account_id")
    if not destination:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.destination_required",
            field_errors=[{"field": "to_account_id", "code": errors.VAL_REQUIRED}],
        )
    try:
        result = transfer.transfer_credit_between_accounts(
            _actor(request),
            source_account_id=account_id,
            destination_account_id=destination,
            amount=_required_amount(payload),
            moved_on=_required_moment(payload, "moved_on"),
            reason=_required_text(payload, "reason"),
            memo=payload.get("memo"),
            idempotency_reference=_required_idempotency_key(payload),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.transferred_money_dict(result), status=201 if result.created else 200)


# ══════════════════════════════════════════════════════════════════════════
# CS-22 · the deposit carry-forward
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_deposit_carry_preview(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/deposit-carry-preview?to=` — what would move.

    A GET, writing nothing: what the closed account HOLDS, what the new one
    holds already, and the receipt date that travels with the money.

    ⚠ **NO `amount` PARAMETER, AND THAT IS THE CONTRACT.** The whole principal
    moves (PO 2026-09-01: the clerk ACCEPTS the offer, they do not size it), so
    a screen has nothing to choose and no figure to post back except the
    confirmation the write door takes.
    """
    require_tenant(request)
    destination = request.query_params.get("to")
    if not destination:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.destination_required",
            field_errors=[{"field": "to", "code": errors.VAL_REQUIRED}],
        )
    try:
        return Response(
            transfer.preview_deposit_carry_forward(
                source_account_id=account_id,
                destination_account_id=destination,
            )
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_deposit_carry_forward(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/deposit-carry-forward` — CS-22 (S19 step 4 · S21).

    `{id}` is the CLOSED account holding the deposit; the body names the new one:

        to_account_id     the account moving in — REQUIRED
        moved_on          the caller's business day — REQUIRED, never a clock
        reason            REQUIRED free text; the audit row is the only durable
                          record of why a customer's security moved
        expected_amount   OPTIONAL confirmation of the PRINCIPAL. When the offer
                          screen shows `carried $153.50` and posts that back,
                          the service REFUSES with both figures named rather
                          than silently moving $150.00 — see the writer.
        memo              optional, written on both legs
        idempotency_key   the wizard's submit token — REQUIRED

    **201 on a new carry, 200 on a replay.** A move-in wizard whose step 4 is
    submitted twice must carry the deposit ONCE; the second submit answers with
    the first movement and `created: false`.

    **`AdminOrClerk`, matching the credit transfer above.** Nothing leaves the
    utility, no bill is re-opened and no customer is charged: the same money
    stays held for the same person against a different account of theirs. A
    move-in is clerk work by definition — a door narrower than the transfer
    would mean no clerk could complete the wizard they are given.

    ⚠ **THE OFFER IS CUSTOMERS' DOOR AND THIS IS PAYMENTS'.** BR-CUS-089 gates
    the offer on a stored `strong` identity match and
    `GET /customers/{id}/deposit-carry-forward` is where that gate lives. This
    door proves the two accounts share a HOLDER and moves the money. A screen
    calls the offer first; that ordering is stated in the writer's docstring and
    in this lane's decision-log row rather than enforced here, because payments
    may not re-implement a customers judgment about a person.
    """
    require_tenant(request)
    payload = _payload(request)
    destination = payload.get("to_account_id")
    if not destination:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.destination_required",
            field_errors=[{"field": "to_account_id", "code": errors.VAL_REQUIRED}],
        )
    expected = None
    if payload.get("expected_amount") not in (None, ""):
        expected = _required_amount(payload | {"amount": payload["expected_amount"]})
    try:
        result = transfer.carry_deposit_forward(
            _actor(request),
            source_account_id=account_id,
            destination_account_id=destination,
            moved_on=_required_moment(payload, "moved_on"),
            reason=_required_text(payload, "reason"),
            expected_amount=expected,
            memo=payload.get("memo"),
            idempotency_reference=_required_idempotency_key(payload),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.transferred_money_dict(result), status=201 if result.created else 200)


# ══════════════════════════════════════════════════════════════════════════
# CS-32 · the payment move
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([SystemAdminOnly])  # the write's gate, mirrored
def payment_move_preview(request: Any, payment_id: str) -> Response:
    """`GET /payments/{id}/move-preview?to=` — what re-opens and what it meets.

    `SystemAdminOnly` for the same reason `reversal_api.payment_reversal_plan`
    is: the preview names every bill on both accounts and what each balance
    becomes, and a role that may not take the action has no business being shown
    its consequences.
    """
    require_tenant(request)
    destination = request.query_params.get("to")
    if not destination:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.destination_required",
            field_errors=[{"field": "to", "code": errors.VAL_REQUIRED}],
        )
    try:
        return Response(
            transfer.preview_payment_move(payment_id=payment_id, destination_account_id=destination)
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-PAY-1070 — the reversal's gate, inherited
def payment_move(request: Any, payment_id: str) -> Response:
    """`POST /payments/{id}/move` — this money was never that account's (S35 · S21).

    The body is the *"Move to another account"* modal:

        to_account_id    the account that should have had it — REQUIRED
        reason           REQUIRED (CS-32 asks for it in terms)
        moved_on         the day the correction is made — REQUIRED, never a clock
        approval         BR-PAY-011's acknowledgement, when the SERVICE asks for
                         one. Not required by this layer: only the service knows
                         whether a bill re-opens or a closed month is touched,
                         and a second copy of that rule here is a second place
                         for it to drift.
        idempotency_key  the modal's submit token — REQUIRED

    **201 on a new move**, carrying the reversing row on the source, the new
    payment on the destination, what re-opened, what the money met and both
    accounts' credit positions afterwards.

    ⚠ **A MOVE IS REFUSED WHILE THE DEPOSIT BATCH IS RECONCILED** (BR-PAY-867)
    and the refusal is a 422 the screen renders as a sentence, not an error
    toast. It is the OPPOSITE of the bounce rule and both are right: a returned
    cheque inside a reconciled batch IS recorded (PO 2026-08-12, OQ-134) because
    the bank returned it, while a move is our own choice about money the bank has
    already agreed a total for.
    """
    require_tenant(request)
    payload = _payload(request)
    destination = payload.get("to_account_id")
    if not destination:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.transfer.destination_required",
            field_errors=[{"field": "to_account_id", "code": errors.VAL_REQUIRED}],
        )
    try:
        result = transfer.move_payment_to_account(
            _actor(request),
            payment_id=payment_id,
            destination_account_id=destination,
            reason=_required_text(payload, "reason"),
            moved_on=_required_body_date(payload, "moved_on"),
            approval=payload.get("approval"),
            idempotency_reference=_required_idempotency_key(payload),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.transferred_money_dict(result), status=201 if result.created else 200)


# ── the routes ─────────────────────────────────────────────────────────────
# `accounts/<id>/transfers` and `accounts/<id>/transfer-preview` are a FOURTH
# and FIFTH literal last segment beside `payments`, `collections` and
# `open-bills` in `apps/payments/api.py`; none of the five can shadow another
# and no `accounts/<id>/<something>` catch-all may ever be added above them.
#
# `payments/<id>/move` and `payments/<id>/move-preview` are three segments each,
# distinct whole patterns from `reversal_api`'s `payments/<id>/reverse` and
# `payments/<id>/reversal-plan` and from `amendments_api`'s
# `payments/<id>/correct-reference`. `apps.payments.api` declares only
# `payments` and `payments/summary` and no `payments/<id>/…` pattern at all.
#
# ⚠ `accounts/<id>/transfers` is a payments URL and `apps.customers.api`
# registers `transfers` (a SERVICE transfer between addresses, BR-CUS-097) —
# a different first segment and a different resource. The word is shared; the
# pattern is not.
#
# ⚠ **CS-22's TWO ARE A SIXTH AND SEVENTH LITERAL LAST SEGMENT under
# `accounts/<id>/`**, and neither can collide with `apps.customers.api`'s
# `customers/<id>/deposit-carry-forward` — a different FIRST segment and a
# different resource. The customers route serves the OFFER (is this the same
# person, and what do they hold); this one MOVES the money.
urlpatterns = [
    path("accounts/<str:account_id>/transfer-preview", account_transfer_preview),
    path("accounts/<str:account_id>/transfers", account_transfers),
    path("accounts/<str:account_id>/deposit-carry-preview", account_deposit_carry_preview),
    path("accounts/<str:account_id>/deposit-carry-forward", account_deposit_carry_forward),
    path("payments/<str:payment_id>/move-preview", payment_move_preview),
    path("payments/<str:payment_id>/move", payment_move),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-8 · CS-32 · §11 tasks 31 and 39 · apps/payments/transfer.py
#         · BR-PAY-864..867 · BR-PAY-1070 · OQ-135 (CLOSED 2026-08-12)
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 tasks 32 and 40 own the screens; this
#            lane is 31 and 39) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 no `GET /transfers` list is minted. A transfer is two payment rows and
#      both already appear on `GET /payments` and on S21's Payments tab, which
#      is where CS-8 and CS-32 both put them. A second list would be a second
#      place for the same rows to be described.
#   E2 the routes are included from `apps/payments/api.py` rather than from
#      `config/urls.py`, where `refunds_api`, `reversal_api` and
#      `amendments_api` are included. `config/urls.py` is outside this lane's
#      write scope and four sibling lanes are live in it; an `include` from the
#      module that already owns `accounts/<id>/payments` reaches the same
#      resolver with no shared-file edit. REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
