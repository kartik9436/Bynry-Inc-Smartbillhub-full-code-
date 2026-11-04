# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-30 (task 56) — the cheque surface's doors.
# Story:    US-PAY-001   Screens: S33 (uncleared · post-dated · returned, and
#           the Void action) · S37 (becoming bankable today) · S35 · S21
# Rules:    BR-PAY-880 (structured fields) · BR-PAY-881 (void before banking) ·
#           BR-PAY-883 (the post-dated hold) · BR-PAY-020 (an operational
#           correction is the clerk's) · BR-SHL-025 · BR-TEN-043 / gate G6
# Tests:    06-backend/tests/test_cr059_cs30_cheques.py
# Impacts:  apps/payments/api.py's urlpatterns (one `include`) ·
#           apps/payments/cheques.py (the writer; no logic lives here)
# ───────────────────────────────────────────────────────
"""The cheque surface — the list a bookkeeper asks for, and the counter void.

    GET  /cheques?as_of=YYYY-MM-DD   uncleared · bankable today · held
    POST /payments/{id}/cheque/void  torn up at the counter

**THIN BY LAW.** The write goes through `apps/payments/cheques.py` and the reads
through the same module's querysets. **No ORM, no figure and no rounding here.**

═══════════════════════════════════════════════════════════════════════════════
ONE READ, THREE LISTS, AND THAT IS DELIBERATE
═══════════════════════════════════════════════════════════════════════════════
CS-30 asks for *"an uncleared cheques view (uncleared · post-dated · returned)"*
on S33 and *"post-dated cheques becoming bankable today"* on S37. Those are the
same three sets of rows read on the same business day, and serving them from two
endpoints is two places for the day boundary to be applied differently — which
is the whole class of defect `DEF-127` records. One endpoint, three members, one
`as_of`.

**`returned` IS NOT SERVED AND ITS ABSENCE IS NAMED.** A returned cheque is a
payment carrying a reversal, which `GET /payments?f.status=reversed` already
lists; adding a fourth member here would be a second answer to a question the
list endpoint answers. Said out loud rather than left as a gap a screen lane
discovers.

═══════════════════════════════════════════════════════════════════════════════
`AdminOrClerk` ON BOTH, AND THE VOID IS THE ONE WORTH ARGUING
═══════════════════════════════════════════════════════════════════════════════
Reversing a payment is Admin-only (`BR-PAY-1070`) because it un-does money that
reached the books and can count an NSF against a customer. **A counter void does
neither**: the cheque never cleared, nothing posted, no bill was met and no
customer is marked. It is the clerk who took the cheque noticing, in the same
minute, that they should not have — and putting that behind an Admin gate would
send them to the harsher tool instead, which is exactly the outcome CS-30 exists
to remove.
"""

from datetime import date
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import cheques, selectors
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant

from apps.payments.api import _actor, _as_of, _payload


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows."""
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-881",
        message_key="payments.cheque.refused",
        params={"detail": str(refusal)},
    )


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
def cheque_list(request: Any) -> Response:
    """`GET /cheques?as_of=` — the three lists CS-30 asks for (S33 · S37).

        uncleared          structured cheques still `processing` — the money
                           has not arrived. *"the thing a bookkeeper actually
                           asks for"*, in CS-30's own words.
        bankable_today     post-dated cheques whose day has come and that are
                           not yet in a batch. **This is the half that makes the
                           hold safe**: without it a post-dated cheque sits in
                           the drawer and nothing ever says it is ready.
        held               post-dated cheques not yet bankable on `as_of`.

    `as_of` is REQUIRED and this module reads NO clock (BR-TEN-043, gate G6) —
    the same requirement `GET /outstandings` and `GET /payments/summary` already
    impose, and for the same reason: a server clock decides a business day in
    the SERVER's timezone.

    Unpaginated, matching `/outstandings`: a utility under 3,000 connections has
    a drawer, not a database, and the three counts must foot to the three lists
    exactly. A paginated body would make a count describe a page.
    """
    require_tenant(request)
    as_of = _as_of(request)
    uncleared = list(cheques.uncleared_cheques())
    bankable = list(cheques.bankable_on(as_of))
    held = list(cheques.held_after(as_of))
    return Response(
        {
            "as_of": as_of.isoformat(),
            "uncleared": selectors.payment_rows(uncleared),
            "bankable_today": selectors.payment_rows(bankable),
            "held": selectors.payment_rows(held),
            "uncleared_count": len(uncleared),
            "bankable_today_count": len(bankable),
            "held_count": len(held),
            "problems": [dict(problem) for problem in cheques.CHEQUE_UNAVAILABLE]
            + [
                {
                    "code": "returned_cheques_are_on_the_payments_list",
                    "br_ref": "BR-PAY-881",
                    # ⚠ THE ROUTE NAME LIVES HERE AND NOT IN `detail` (G28, CR-016).
                    # The endpoint this defers to is `GET /payments` filtered on
                    # the reversed status; naming it in a served string puts our
                    # own plumbing in front of a utility, and the sentence reads
                    # perfectly without it.
                    "detail": "a returned cheque is a payment carrying a reversal, and the "
                    "payments list already shows it as reversed. It is not a fourth member "
                    "here, because two places answering one question is two places for them "
                    "to disagree.",
                }
            ],
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-PAY-020 — a counter correction is operational
def cheque_void(request: Any, payment_id: str) -> Response:
    """`POST /payments/{id}/cheque/void` — torn up before the deposit (S33 · S35).

    The body:

        reason    REQUIRED — a payment that vanishes from the drawer with no
                  explanation is the one thing a bookkeeper cannot reconcile
        on_date   the caller's business day — REQUIRED, never a clock

    **200, not 201.** Nothing is created: the payment moves from `processing` to
    `failed` and an audit row records why. The thing a screen re-reads afterwards
    is the payment it already had.

    ⚠ **THIS IS NOT A REVERSAL AND THE SCREEN MUST NOT PRESENT IT AS ONE.** No
    reversing row, no journal entry, no NSF count, no cash-only flag. The cheque
    never cleared, so nothing reached the books — which is exactly why a counter
    void is expressible at all. A cheque that HAS cleared is refused here by
    name and goes to `POST /payments/{id}/reverse`, which is Admin-only and
    writes both.

    ⚠ **THE REASON LIVES ONLY IN `audit_log`, WHICH IS PRUNED** — the same cost
    the PO accepted for a corrected cheque number on 2026-09-02, and the same
    open question (`OQ-1340`). `problems[]` says so on every response, and no
    screen may describe this as a permanent record of why until that is answered.
    """
    require_tenant(request)
    payload = _payload(request)
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.cheque.reason_required",
            field_errors=[{"field": "reason", "code": errors.VAL_REQUIRED}],
        )
    try:
        result = cheques.void_cheque(
            _actor(request),
            payment_id=payment_id,
            reason=reason.strip(),
            on_date=_required_date(payload, "on_date"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.voided_cheque_dict(result))


# ── the routes ─────────────────────────────────────────────────────────────
# `cheques` is a new literal FIRST segment; nothing in `apps.payments.api`,
# `refunds_api`, `reversal_api`, `amendments_api`, `writeoffs_api`,
# `transfer_api` or `reapply_api` declares one, and no `<something>` catch-all
# exists at that level in any of them.
#
# `payments/<id>/cheque/void` is FOUR segments and is the only four-segment
# `payments/<id>/…` pattern in the module — it cannot shadow, and cannot be
# shadowed by, `reverse`, `reversal-plan`, `correct-reference`, `move`,
# `move-preview`, `reapply` or `reapply-plan`, all of which are three.
urlpatterns = [
    path("cheques", cheque_list),
    path("payments/<str:payment_id>/cheque/void", cheque_void),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-30 (RULED 2026-09-01) · §11 task 56 · §10 P7 ·
#         apps/payments/cheques.py · BR-PAY-880..883 · OQ-1340 (OPEN)
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 task 57 owns P7 and the S22/S35 fields;
#            this lane is 56) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 no `returned` member. A returned cheque is a payment carrying a reversal
#      and `GET /payments` lists it; a fourth member would be a second answer.
#      Stated on `problems[]` rather than left as a gap.
#   E2 no RE-PRESENT route. CS-30's second rule is not built (see
#      `cheques.py` E1) and a route without the walk behind it would state a
#      consequence it cannot honour — `apps/payments/api.py`'s own standing rule
#      that *"a route that answers 501 is a promise"*.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
