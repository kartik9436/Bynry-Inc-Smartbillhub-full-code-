# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-11 (task 37) — the reapply service's door. §0d.1 records
#           that *"reapply exists at NO layer — the only trace in the module is
#           a comment"*.
# Story:    US-PAY-006   Screens: S33 (the Reapply row action) · S35 (the modal)
# Rules:    BR-PAY-031 (CONFIRMED — reversing allocation rows plus new ones) ·
#           BR-PAY-020 (correcting an application is OPERATIONAL work) ·
#           BR-SHL-025 (server-enforced RBAC) · BR-TEN-043 / gate G6
# Tests:    06-backend/tests/test_cr059_cs11_reapply.py
# Impacts:  apps/payments/api.py's urlpatterns (one `include`) ·
#           apps/payments/reapply.py (the writer; no logic lives here)
# ───────────────────────────────────────────────────────
"""The two doors on moving a payment between one account's own bills.

    GET  /payments/{id}/reapply-plan   what this payment currently meets
    POST /payments/{id}/reapply        move it

**THIN BY LAW.** The write goes through `apps/payments/reapply.py` and the read
through the same module. **No ORM, no figure and no rounding in this file.**

═══════════════════════════════════════════════════════════════════════════════
`AdminOrClerk`, AND THE WIDER GATE IS THE CONSIDERED CHOICE
═══════════════════════════════════════════════════════════════════════════════
Reversing a payment is Admin-only (BR-PAY-1070) because it un-does money and can
count an NSF against a customer. **A reapply does neither.** No money enters or
leaves, nothing posts to the books, the payment keeps its number and its dates,
and the customer's history gains no reversed row. It is the clerk correcting
their own morning's typing, which is the operational half BR-PAY-020 already
puts with the clerk for a write-off REQUEST.

**Which is also the point of building it.** Before this the only correction was
Reverse-and-record — an Admin-only action that stamps `reversed` on a payment
that never bounced. Putting the gentle correction behind the harsher gate would
leave the clerk reaching for the harsher tool.

═══════════════════════════════════════════════════════════════════════════════
THE RIGHT-HAND SIDE OF THE MODAL IS CS-4's LIST, NOT A SECOND ONE
═══════════════════════════════════════════════════════════════════════════════
CS-11: *"Reuses CS-4's open-bill list."* So the modal reads
`GET /accounts/{id}/open-bills` for where the money can GO and
`GET /payments/{id}/reapply-plan` for where it currently IS. Two reads, one
source each — a second open-bill list here would be a second place for the
picker and the validator to disagree about which bills exist.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import reapply, selectors
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant

from apps.payments.api import _actor, _payload


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows.

    `br_ref` falls back to BR-PAY-031 because that is the rule this whole path
    implements; every refusal the service raises already carries its own.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-031",
        message_key="payments.reapply.refused",
        params={"detail": str(refusal)},
    )


def _targets(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """The clerk's instruction: which bills, and how much on each.

    A float is REFUSED at the boundary rather than converted (CLAUDE.md rule 2).
    This is the only place a float can still be seen for what it is; once it is
    a `Decimal(str(0.1))` inside the service it is already not what was typed.
    """
    rows = payload.get("targets")
    if not isinstance(rows, list) or not rows:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.reapply.targets_required",
            field_errors=[{"field": "targets", "code": errors.VAL_REQUIRED}],
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.reapply.targets_invalid",
                field_errors=[{"field": "targets", "code": errors.VAL_FORMAT}],
            )
        raw = row.get("amount")
        if isinstance(raw, float):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.record.amount_invalid",
                field_errors=[{"field": "targets.amount", "code": errors.VAL_FORMAT}],
            )
        try:
            amount = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError) as bad:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.record.amount_invalid",
                field_errors=[{"field": "targets.amount", "code": errors.VAL_FORMAT}],
            ) from bad
        out.append({"invoice_id": row.get("invoice_id"), "amount": amount})
    return tuple(out)


def _required_date(payload: dict[str, Any], name: str) -> date:
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


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def payment_reapply_plan(request: Any, payment_id: str) -> Response:
    """`GET /payments/{id}/reapply-plan` — the left-hand side of S35's modal.

    What this payment currently meets, bill by bill, NET of every mirror row —
    so a payment that has already been reapplied once, or partly released by a
    restatement, shows its true position rather than its original one.

    A GET: it writes nothing and may be taken twice with no consequence.
    """
    require_tenant(request)
    try:
        return Response(reapply.reapply_plan(payment_id=payment_id))
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-PAY-020 — correcting an application is operational
def payment_reapply(request: Any, payment_id: str) -> Response:
    """`POST /payments/{id}/reapply` — BR-PAY-031, at last (S33 · S35).

    The body is the Reapply modal:

        targets   `[{"invoice_id": …, "amount": "292.87"}, …]` — where the money
                  goes. EXPLICIT: a reapply exists because the automatic order
                  was wrong, so re-running that order would undo the correction.
        release   which bills to take it OFF. Optional; absent means every bill
                  this payment currently meets, which is the ordinary case.
        reason    REQUIRED — the audit row is the only record of why.
        on_date   the caller's business day — REQUIRED, never a clock.

    **200, not 201.** Nothing is created that a caller could go and fetch: a
    reapply moves an existing payment's money between existing bills, and the
    thing the screen re-reads afterwards is the payment it already had.

    ⚠ **NOTHING IS POSTED TO THE LEDGER AND `problems[]` SAYS SO ON EVERY
    RESPONSE.** It is the one write path in this module that posts nothing, and
    the row is there so a reviewer reading the payload does not have to know that
    already (CR-059 CS-11: *"a reapply that posted would double-count the
    money"*).

    ⚠ **NO IDEMPOTENCY TOKEN, AND THAT IS DELIBERATE RATHER THAN MISSING.** A
    double-clicked reapply is refused by the service on its own terms: the second
    call finds the money already off the named bills and answers *"payment … has
    nothing on bill …"*, because `_net_by_invoice` reads the CURRENT net position
    rather than the original rows. A token would add a second guard over a state
    check that is already exact — and unlike a payment, a reapply moves no money
    in or out, so a lost race costs a refusal rather than a duplicate receipt.
    """
    require_tenant(request)
    payload = _payload(request)
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.reapply.reason_required",
            field_errors=[{"field": "reason", "code": errors.VAL_REQUIRED}],
        )
    release = payload.get("release")
    try:
        result = reapply.reapply_payment(
            _actor(request),
            payment_id=payment_id,
            targets=_targets(payload),
            reason=reason.strip(),
            on_date=_required_date(payload, "on_date"),
            release=tuple(release) if isinstance(release, list) else None,
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.reapplied_dict(result))


# ── the routes ─────────────────────────────────────────────────────────────
# Three segments each, distinct whole patterns from `reversal_api`'s
# `payments/<id>/reverse` and `payments/<id>/reversal-plan`, `amendments_api`'s
# `payments/<id>/correct-reference` and `transfer_api`'s `payments/<id>/move`
# and `payments/<id>/move-preview`. `apps.payments.api` declares only
# `payments`, `payments/summary` and `payments/selection-total`, all literal.
urlpatterns = [
    path("payments/<str:payment_id>/reapply-plan", payment_reapply_plan),
    path("payments/<str:payment_id>/reapply", payment_reapply),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-11 · §0d.1 · §11 task 37 · BR-PAY-031 (CONFIRMED) ·
#         apps/payments/reapply.py · apps/payments/open_bills.py (CS-4)
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 task 38 owns S33/S35; this lane is 37)
#            E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 no open-bill list is served here. CS-11 says the modal *"reuses CS-4's
#      open-bill list"* and `GET /accounts/{id}/open-bills` is live; a second
#      one would be a second place for the picker and the validator to disagree.
#   E2 no idempotency token — see `payment_reapply`'s docstring. The service's
#      net-position read is an exact guard and a reapply moves no money in or
#      out, so the OQ-127 argument for a client token does not apply.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
