# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 CS-12 (task 49 — `POST /customers/{id}/payments` and the
#           customer roll-up) · CR-059 CS-27 (task 51 — the premises read and
#           the master-paying route)
#           Screens: S22 · S35 · S21 · S33 · P5 · P6 (CR-059 tasks 50 and 52 —
#           ANOTHER LANE. Nothing here draws anything, and nothing calls these
#           routes yet.)
# Rules:    BR-PAY-1126..1130 · BR-PAY-028 (idempotency — the client token is
#           REQUIRED, exactly as it is on `POST /accounts/{id}/payments`) ·
#           BR-SHL-020 (a refusal renders from its message key, never from
#           server prose) · BR-SHL-025 (a control a clerk cannot use states
#           why) · A4 payments_record (Admin or Clerk writes; Executive views) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money as a decimal
#           STRING, never a float)
# Tests:    06-backend/tests/test_cr059_cs12_multi_account_tender.py ·
#           06-backend/tests/test_cr059_cs27_master_pays_units.py
# Impacts:  config/urls.py (where these four paths mount, and WHY the ordering
#           is safe) · apps/payments/tenders.py (the writer) ·
#           apps/payments/customer_position.py · premises_position.py (the two
#           reads) · apps/payments/api.py (the sibling module whose helpers this
#           reuses rather than re-implementing)
# ───────────────────────────────────────────────────────
"""THE FOUR ROUTES FOR ONE CHEQUE THAT PAYS SEVERAL ACCOUNTS.

    GET  /customers/{id}/open-bills        CS-12 — every property, what each owes
    POST /customers/{id}/payments          CS-12 — record the cheque, all or none
    GET  /accounts/{id}/premises-position  CS-27 — the building, unit by unit
    POST /accounts/{id}/premises-payments  CS-27 — the master pays its tenants

**IT IS ITS OWN MODULE AND NOT FOUR MORE VIEWS IN `api.py`, FOR THE REASON
`reversal_api.py`, `amendments_api.py` and `transfer_api.py` ARE THEIRS:**
`apps/payments/api.py` declares `payments`, `payments/summary` and
`payments/selection-total` and mounts nineteen paths, and a lane adding a fifth
`customers/…` pattern into that list is a lane one merge conflict away from a
route that shadows another. Django matches whole patterns, so these four cannot
shadow anything and nothing can shadow them — see `config/urls.py`, which says
so at the mount point with the argument written out.

────────────────────────────────────────────────────────────────────────────
WHY `POST /customers/{id}/payments` CANNOT COLLIDE WITH CUSTOMERS' OWN ROUTES
────────────────────────────────────────────────────────────────────────────
`apps.customers.api` declares `customers` and `customers/<str:customer_id>` —
one and two segments. This is **three** segments, and Django resolves by the
whole pattern rather than by prefix, so the two-segment pattern cannot swallow
it however the includes are ordered. It is the same argument
`accounts/<id>/payments` has relied on since 2026-08-11, one noun along, and it
is written down rather than assumed because the failure mode is a 404 on a route
that exists.

────────────────────────────────────────────────────────────────────────────
`idempotency_key` IS REQUIRED AND REFUSING WITHOUT IT IS THE POINT
────────────────────────────────────────────────────────────────────────────
The same rule and the same sentence as `POST /accounts/{id}/payments`: a key
generated HERE would be a different string on the second submit and would dedupe
nothing while looking as though it had. **On this route it matters more, not
less.** One token guards the whole submission AND, through
`tenders.tender_part_reference`, derives a DISTINCT key for each account — which
is the fix for the silent trap CS-12 names, where one token reused across
accounts records payment one, reports success, and writes nothing for the rest:
**in the drawer $520.00, recorded $184.20, errors raised none.**

────────────────────────────────────────────────────────────────────────────
201 ON A NEW TENDER, 200 ON A REPLAY — NEVER 409
────────────────────────────────────────────────────────────────────────────
The same ruling `account_payments` records: 11b §3 G7 makes a duplicate a 409
for bill runs, imports, webhooks and tenant provisioning, and a staff
double-click is none of them. A 409 toast for a button that worked is a wrong
answer a clerk would act on. A replay answers 200 with the original tender and
every part it made, `created: false`.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import errors
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant

from apps.payments import counters, customer_position, premises_position, selectors, tenders
from apps.payments.api import _actor, _moment, _payload, _required, _targets
from apps.payments.exceptions import PaymentRuleError


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A service rule refusal, as the ONE catalog exception G9 allows.

    Same shape and same single code as `api._as_catalog_refusal` — 422
    BIZ-COMPLETENESS — because every refusal that reaches here says the same
    thing (*this cannot be done as asked, here is the rule and the sentence a
    clerk can act on*), and picking among the nine BIZ codes per refusal would
    be this layer INTERPRETING rules it does not own.

    The message key is the TENDER's own, not `payments.record.refused`: a clerk
    who typed three rows against three properties has to be told that **nothing
    was recorded**, and *"This payment can't be recorded"* would read as one
    failed row out of three (BR-PAY-1127 — nothing partial commits).
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-1126",
        message_key="payments.tender.refused",
        params={"detail": str(refusal)},
    )


def _parts(payload: dict[str, Any]) -> tuple[tenders.TenderPart, ...]:
    """The rows the clerk typed: one account, one amount, one allocation choice.

    Refused as a body error rather than passed on when it is not a list of
    objects — the service's own refusals are about RULES, and *"the list of
    properties was not readable"* is not a rule, it is a malformed request.
    """
    raw = payload.get("parts")
    if not isinstance(raw, list) or not raw:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.tender.parts_required",
            field_errors=[{"field": "parts", "code": errors.VAL_FORMAT}],
        )
    built: list[tenders.TenderPart] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.tender.parts_invalid",
                field_errors=[{"field": "parts", "code": errors.VAL_FORMAT}],
            )
        account_id = entry.get("account_id")
        if not account_id:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="payments.tender.part_account_required",
                field_errors=[{"field": "parts", "code": errors.VAL_REQUIRED}],
            )
        raw_amount = entry.get("amount")
        if raw_amount is None or (isinstance(raw_amount, str) and not raw_amount.strip()):
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="payments.tender.part_amount_required",
                field_errors=[{"field": "parts", "code": errors.VAL_REQUIRED}],
            )
        try:
            # CLAUDE.md rule 2 — read the digits the clerk typed. A JSON float
            # would already have lost them, which is why the form sends strings
            # and the service refuses a float outright rather than converting.
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, TypeError, ValueError) as problem:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.record.amount_invalid",
                field_errors=[{"field": "parts", "code": errors.VAL_FORMAT}],
            ) from problem
        built.append(
            tenders.TenderPart(
                account_id=account_id,
                amount=amount,
                # BR-PAY-001, PER ROW: a landlord may pay one tenant's oldest
                # bill and another's specific one in the same cheque.
                order=entry.get("apply_to") or "oldest_first",
                targets=_targets(entry),
                memo=entry.get("memo") or None,
            )
        )
    return tuple(built)


def _recorded_tender_dict(result: tenders.RecordedTender) -> dict[str, Any]:
    """The body. Money as decimal STRINGS beside a CHAR(3) (hard rule 2).

    Each part is served through `selectors.recorded_payment_dict`, the SAME
    shaper `POST /accounts/{id}/payments` uses, so a receipt drawn from one part
    of a cheque and a receipt drawn from a single payment cannot disagree about
    what a payment is.
    """
    return {
        # B14 rule 31 — served because a follow-up call names it; the screen
        # shows the cheque reference and the `PMT-` numbers.
        "tender_id": result.tender_id,
        "created": result.created,
        "scope": result.scope,
        "amount": str(result.amount),
        "currency": result.currency,
        "reference": result.reference,
        "payer_account_id": result.payer_account_id,
        "customer_id": result.customer_id,
        "authority": result.authority,
        "part_count": len(result.parts),
        "payments": [selectors.recorded_payment_dict(part) for part in result.parts],
        "problems": list(result.problems),
    }


def _open_till(request: Any, payload: dict[str, Any]) -> Any:
    """The open till for a hand tender, or a refusal — the SAME guard as `S35`.

    ⚠ **`DEF-PAY-7642` / `DEF-PAY-6322` (lane PAY-H, 2026-10-30).** Both doors
    below took a cheque across several accounts and never asked for a till, so a
    clerk could key $520.00 in cheques with no counter open and every dollar
    banked under the day's system till. `OQ-PAY-12601` closed on the PO's words
    *"back office or counter - if person is punching the payemnt in system - it
    is same process, they ahve to open the counter"*, and the 2026-10-30 audit
    ruling names this door by number (L1-08, *"with the till check"*).

    **The rule has ONE implementation**, `counters.assert_till_open_for_tender`;
    this is a call site, and the refusal is keyed exactly as
    `api.account_payments` keys it, so the clerk reads one sentence whichever
    door they came through. Checked BEFORE anything is written, so a refused
    cheque burns no `PMT-` number.
    """
    try:
        return counters.assert_till_open_for_tender(_actor(request), payload.get("method"))
    except PaymentRuleError as refusal:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-1186",
            # A LITERAL key at the raise site (G32 reads only same-file helpers).
            message_key="payments.counter.till_required",
            params={"detail": str(refusal)},
        ) from refusal


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 payments_record: Executive is VIEW
def customer_open_bills(request: Any, customer_id: str) -> Response:
    """CS-12 — every account this customer holds, and every bill still open.

    The list a clerk aims one cheque at. Read-only; nothing here writes.
    """
    require_tenant(request)
    try:
        return Response(customer_position.customer_open_bill_position(customer_id=customer_id))
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # A4 payments_record: Executive is VIEW
def customer_payments(request: Any, customer_id: str) -> Response:
    """CS-12 — ONE cheque from one customer, settling several of their accounts.

        amount           the cheque total, a decimal STRING > 0
        posted_at        the USER's posting date — required (BR-PAY-033)
        cleared_at       the clearing date, or absent = still processing
        method           a tenant method CODE (BR-PAY-026) — optional
        reference        the cheque number — optional, copied onto every part
        memo             optional, and a part may carry its own
        currency         optional; must equal the accounts' (BR-TEN-042)
        idempotency_key  the form's client token — REQUIRED (see the module
                         docstring; it also derives a DISTINCT key per account)
        parts[]          {account_id, amount, apply_to?, targets[]?, memo?}

    **The parts must sum to `amount` EXACTLY or nothing at all is recorded** —
    no payment, no allocation, no journal entry, no receipt (BR-PAY-1127). The
    refusal states both figures and their difference, because *"the amounts do
    not add up"* is not something a clerk can act on.

    201 on a new tender with every payment it made inline — a clerk who has just
    taken $520.00 across three properties has to be shown what each part paid,
    and the allocator worked all three out in the same transaction. 200 with
    `created: false` on a replay.
    """
    require_tenant(request)
    payload = _payload(request)
    _required(payload, "idempotency_key", message_key="payments.tender.idempotency_key_required")
    till = _open_till(request, payload)
    try:
        result = tenders.record_multi_account_payment(
            _actor(request),
            customer_id=customer_id,
            parts=_parts(payload),
            amount=Decimal(
                str(_required(payload, "amount", message_key="payments.tender.amount_required"))
            ),
            posted_at=_moment(
                payload, "posted_at", message_key="payments.tender.posted_at_required"
            ),
            cleared_at=_moment(payload, "cleared_at", message_key=None),
            method_code=payload.get("method"),
            reference=payload.get("reference"),
            currency=payload.get("currency"),
            memo=payload.get("memo"),
            submission_key=str(payload["idempotency_key"]),
            counter_session_id=None if till is None else till.pk,
        )
    except InvalidOperation as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        ) from problem
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(_recorded_tender_dict(result), status=201 if result.created else 200)


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 payments_record: Executive is VIEW
def premises_position_view(request: Any, account_id: str) -> Response:
    """CS-27 — the building this master may pay for, unit by unit.

    Read-only. `may_pay` rides on every row because CS-27's S22/S35 draws that
    column by name and BR-SHL-025 forbids a control that cannot say why.
    """
    require_tenant(request)
    try:
        return Response(premises_position.premises_payment_position(payer_account_id=account_id))
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # A4 payments_record: Executive is VIEW
def premises_payments(request: Any, account_id: str) -> Response:
    """CS-27 — a MASTER account pays its TENANTS' bills with one cheque.

    Same body as `POST /customers/{id}/payments`; the payer is the account in
    the path and every part must name a unit account on that master's premises,
    or the master's own account for money deliberately left as its credit.

    ⚠ **A PART THAT WOULD LEAVE MONEY AS A TENANT'S CREDIT IS REFUSED, WHOLE**
    (BR-PAY-1130): the landlord's money must never sit on a different person's
    account, where it would auto-apply to that person's next bill. Reduce the
    row to what the unit owes and put the remainder on the master, which is the
    only lawful home for a leftover.

    **The master gets the TENDER and no payment entry**, except that leftover —
    three signed rules force it and `premises_position.py`'s docstring carries
    all three, because the next lane will otherwise "simplify" the payment onto
    the master and credit a debt the master never had while four bills stay open.
    """
    require_tenant(request)
    payload = _payload(request)
    _required(payload, "idempotency_key", message_key="payments.tender.idempotency_key_required")
    till = _open_till(request, payload)
    try:
        result = tenders.record_multi_account_payment(
            _actor(request),
            payer_account_id=account_id,
            parts=_parts(payload),
            amount=Decimal(
                str(_required(payload, "amount", message_key="payments.tender.amount_required"))
            ),
            posted_at=_moment(
                payload, "posted_at", message_key="payments.tender.posted_at_required"
            ),
            cleared_at=_moment(payload, "cleared_at", message_key=None),
            method_code=payload.get("method"),
            reference=payload.get("reference"),
            currency=payload.get("currency"),
            memo=payload.get("memo"),
            submission_key=str(payload["idempotency_key"]),
            counter_session_id=None if till is None else till.pk,
        )
    except InvalidOperation as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        ) from problem
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(_recorded_tender_dict(result), status=201 if result.created else 200)


urlpatterns = [
    # THREE segments, so `apps.customers.api`'s `customers/<str:customer_id>`
    # (two) cannot swallow either of these however the includes are ordered —
    # Django resolves whole patterns, not prefixes.
    path("customers/<str:customer_id>/open-bills", customer_open_bills),
    path("customers/<str:customer_id>/payments", customer_payments),
    # A FIFTH and SIXTH literal last segment beside `payments`, `collections`
    # and `open-bills` on `accounts/<id>/…` — none of them can shadow another,
    # and no `accounts/<id>/<something>` catch-all may ever be added above them.
    path("accounts/<str:account_id>/premises-position", premises_position_view),
    path("accounts/<str:account_id>/premises-payments", premises_payments),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 CS-12 + CS-27 (12-governance/11-change-requests.md §8 · §10 P5/P6 · §11 tasks 49, 51)
# generated: 2026-09-03 by the CR-059 W9 multi-account/master-tender lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no UI — CR-059 tasks 50/52 are another lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every route was asserted to RESOLVE before it was trusted (DEF-524's lesson: a route nothing resolves is a feature that does not exist) · the four new message keys are in all ELEVEN catalogues, so no refusal on this path renders as silence (G32 baseline 0)
# exceptions: (1) NO SCREEN CALLS THESE ROUTES. CR-059 tasks 50 and 52 own P5,
#         P6, S21's two sides and S33's grouping; another lane holds
#         `07-frontend/src/features/payments/` while this was written. The
#         endpoints are live and unreachable from the product — hard-won law 2
#         with the halves in two lanes BY DESIGN, and REPORTED.
#         (2) `POST /customers/{id}/payments` IS THE ROUTE CS-12 NAMES; the
#         premises pair is mounted under `accounts/{id}/…` and NOT under a
#         `premises/{id}/…` prefix, because the payer is an ACCOUNT and the
#         premises is derived from it — a `premises/{id}/payments` route would
#         need the caller to resolve the master first, which is the join this
#         change exists to make for them.
#         (3) 2026-10-30 lane PAY-H: both POST doors now call
#         `counters.assert_till_open_for_tender` and stamp the open till on
#         every part (DEF-PAY-7642, DEF-PAY-6322) — tests/test_pay_h_pay_for_others.py.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
