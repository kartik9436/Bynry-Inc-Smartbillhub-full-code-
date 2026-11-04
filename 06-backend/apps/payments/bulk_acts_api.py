# ── Trace ──────────────────────────────────────────────
# Change:   Payments audit Q4 (PO 2026-10-30) · DEF-PAY-10747 · lane PAY-J
# Story:    US-PAY-004 (S33 — the list's bulk bar)
# Rules:    BR-PAY-024 · BR-PAY-031 · BR-PAY-020 (correcting an application is
#           operational: Admin or Clerk) · BR-TEN-043 (the caller names the day)
#           · CLAUDE.md hard rules 1, 7
# Tests:    06-backend/tests/test_pay_j_bulk_receipts_reapply.py
# ───────────────────────────────────────────────────────
"""The two doors the Payments list's bulk bar calls once per ticked payment.

    POST /payments/{id}/bulk-receipt   → `bulk_acts.send_receipt`
    POST /payments/{id}/bulk-reapply   → `bulk_acts.reapply_held`  (body: on_date)

Both answer **200 with `{payment_id, payment_no, outcome, …}`** for every
ordinary outcome — *waiting*, *no contact*, *nothing to reapply* are answers,
not errors, and the bar's result panel counts them by `outcome`. A payment the
clerk may NOT act on is a **422 refusal** naming why, which the panel shows
beside that payment's number (never skipped silently).

Three segments each, distinct whole patterns beside `reapply`, `reapply-plan`,
`reverse`, `move` and `receipt`; they are included above `detail_api`, whose
two-segment `payments/<id>` must stay last (`api.py` says why).
"""

from datetime import date
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import bulk_acts
from apps.payments.api import _actor, _payload
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant


def _refusal(refusal: PaymentRuleError, message_key: str) -> errors.BizError:
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-031",
        message_key=message_key,
        params={"detail": str(refusal)},
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def payment_bulk_receipt(request: Any, payment_id: str) -> Response:
    """One payment's email receipt, unless one is still waiting to go out."""
    require_tenant(request)
    try:
        return Response(bulk_acts.send_receipt(actor=_actor(request), payment_id=payment_id))
    except PaymentRuleError as refusal:
        raise _refusal(refusal, "payments.bulk.receiptRefused") from refusal


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-PAY-020, the single reapply's own gate
def payment_bulk_reapply(request: Any, payment_id: str) -> Response:
    """One payment's held credit onto its account's open bills, oldest first."""
    require_tenant(request)
    raw = _payload(request).get("on_date")
    if not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.date_required",
            params={"field": "on_date"},
            field_errors=[{"field": "on_date", "code": errors.VAL_REQUIRED}],
        )
    try:
        on_date = date.fromisoformat(str(raw)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": "on_date", "code": errors.VAL_FORMAT}],
        ) from bad
    try:
        return Response(
            bulk_acts.reapply_held(actor=_actor(request), payment_id=payment_id, on_date=on_date)
        )
    except PaymentRuleError as refusal:
        raise _refusal(refusal, "payments.bulk.reapplyRefused") from refusal


urlpatterns = [
    path("payments/<str:payment_id>/bulk-receipt", payment_bulk_receipt),
    path("payments/<str:payment_id>/bulk-reapply", payment_bulk_reapply),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: decision log 2026-10-30 "Q4 settled" · apps/payments/bulk_acts.py ·
#         apps/payments/reapply_api.py (the precedent door)
# generated: 2026-10-30 by lane PAY-J
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
