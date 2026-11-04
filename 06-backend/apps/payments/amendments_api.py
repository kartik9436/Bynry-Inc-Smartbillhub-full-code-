# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-34 · task 41 — the NAMED amend endpoint, and the CR is
#           explicit that it is **not a PATCH**: *"Deliberately NOT a PATCH on
#           the payment resource. The rule that there is no edit verb on a
#           payment path is load-bearing and should stay absolute — a route that
#           accepts a partial body invites the next field to be added to it.
#           Instead a named endpoint that accepts only these fields and nothing
#           else, so what can be amended is visible in the route rather than
#           enforced inside it."*
# Story:    US-PAY-004 (the payment record) · US-PAY-020/023 (the bank
#           reconciliation that matches on the reference)
#           Screens: S35 (the "Correct reference" modal — CR-059 task 42) ·
#           S21 (the corrected value with the previous one on hover — task 42)
# Rules:    CLAUDE.md hard rule 4 / BR-PAY-002 (append-only) · hard rule 7
#           (audit) · hard rule 1 (tenant scoping) · BR-PAY-025 (batches group
#           by day × tender) · BR-PAY-004 (a reconciled batch is locked) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · BR-SHL-020
# Question: the write is stubbed on the open question `apps/payments/
#           amendments.OQ_AMEND_MECHANISM` — see that module's docstring.
# Tests:    06-backend/tests/test_cr059_cs34_amend_reference.py
# Impacts:  config/urls.py inclusion · apps/payments/amendments.py
# ───────────────────────────────────────────────────────
"""`POST /payments/{id}/correct-reference` — a mistyped cheque number.

**THE ROUTE IS THE SPEC.** CS-34's whole backend argument is that what may be
corrected should be *visible in the route rather than enforced inside it*, so
this file mounts ONE named verb that takes three fields and a note, and adds no
PATCH, PUT or DELETE to any payment path — the absence of an edit verb on
`payments` stays absolute, and a forged verb is a router 405 before any handler
runs, exactly as it is today.

Its own module rather than more lines in `apps/payments/api.py`, on the
`refunds_api` / `reversal_api` precedent and for hard-won law 11's reason: a
1,269-line file several lanes edit is where a pathspec commit eats somebody's
work.

═══════════════════════════════════════════════════════════════════════════════
⚠ THE WRITE IS LIVE SINCE 2026-09-02 — WHAT THAT CHANGED, AND WHAT IT DID NOT
═══════════════════════════════════════════════════════════════════════════════
**Working and provable:** every money field refused BY NAME (CS-34's first
proof), the tender refused once the payment is in a deposit batch (its second
new rule), the required note, the unknown-field refusal that keeps the route
from quietly growing a fourth field — **and now the correction itself**.

`OQ-1322` CLOSED, PO verbatim: *"(a) Allow those fields to change"*. CLAUDE.md
hard rule 4 is NARROWED for `confirmation`, `memo` and `method_id` and for
nothing else; `payments/0014` is the only place the database's allow list moves.
`apps/payments/amendments.py` carries the reasoning in full.

**SO THE SCREEN LANE (task 42) MAY NOW ENABLE THE CONTROL.** Until this landed,
S35's Correct-reference control had to render DISABLED WITH ITS REASON because
the service raised; that is no longer true and the row must not be built from
it. **One thing the screen still owes: the correction takes a REQUIRED note.**

⚠ **THE SECOND THING IT USED TO OWE IS NOW THE OPPOSITE INSTRUCTION, AND THAT
MATTERS MORE THAN THE FIRST (`P3.18`, 2026-09-23).** This paragraph read *"every
successful response carries an `unavailable[]` entry … so no screen may present
this as a permanent record"*, and the screen lane obeyed it by rendering
`CorrectionRetentionNote` — a `<details>` in eleven languages explaining the
retention policy. **`OQ-1340` is CLOSED** (PO: *"keep the same rule s; when audit
log is delete - it is deleted thats okay"*), so the entry no longer says
*undecided*; it is now `amendment_history_is_not_a_permanent_record` and says the
row IS pruned. **And the honest build is SILENCE, not a disclaimer:** B14 rule 33
puts RATIONALE at ZERO WORDS ON SCREEN, so the screen says nothing at all about
how long the old value survives — it simply never claims permanence. The
`unavailable[]` entry is a MACHINE fact for a caller, never copy. The note
component is deleted.

═══════════════════════════════════════════════════════════════════════════════
`AnyTenantRole`, MIRRORING WHO RECORDS THE PAYMENT
═══════════════════════════════════════════════════════════════════════════════
Recording a payment is Admin·Clerk (`POST /accounts/{id}/payments`), and
correcting the cheque number on one is the same clerk fixing their own typing.
CS-34 states no role rule of its own, and a lane inventing a narrower one would
be writing a rule rather than implementing one — `reversal_api`'s argument run
the other way. The reversal and refund doors are Admin-only because those move
money; this one moves no money by construction, which is the whole premise of
the spec.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import amendments
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant

# `_payload` is imported rather than restated — one definition of "the body must
# be an object", the same reason `reversal_api` imports it.
from apps.payments.api import _payload


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows.

    `BIZ_IMMUTABLE` rather than `BIZ_COMPLETENESS`, and the difference is not
    cosmetic: every refusal this path raises is *"that field is financial
    history"* or *"that batch is closed"*, which is what `BIZ-IMMUTABLE` names.
    A completeness code would tell the screen the clerk left something out.
    """
    return errors.BizError(
        errors.BIZ_IMMUTABLE,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-002",
        message_key="payments.correct_reference.refused",
        params={"detail": str(refusal)},
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # the clerk who records a payment
def payment_correct_reference(request: Any, payment_id: str) -> Response:
    """`POST /payments/{id}/correct-reference` — S35's Correct-reference modal.

    The body is the whole of what may be corrected, and nothing else:

        reference   the cheque or confirmation number — optional
        memo        the clerk's note on the payment itself — optional
        tender_id   the instrument, where the payment has not been banked yet
        note        WHY — REQUIRED (see `amendments.amend_reference`)

    **A body carrying `amount`, `account_id`, `posted_at`, `cleared_at` or
    `allocations` is refused with that field NAMED**, which is CS-34's first
    proof and is live today. So is an unknown field: the route accepts four
    things, and *"a route that accepts a partial body invites the next field to
    be added to it"* is the spec's own reason for that.

    ⚠ **A REQUEST THAT PASSES EVERY REFUSAL MEETS THE STUB** and raises, because
    the write is blocked on an open question. That is deliberate and is stated
    in this module's docstring; it refuses nothing that works today, because
    nothing corrects a reference today.
    """
    require_tenant(request)
    body = _payload(request)
    try:
        result = amendments.amend_reference(
            getattr(request, "user", None),
            payment_id=payment_id,
            note=body.get("note") or "",
            reference=body.get("reference"),
            memo=body.get("memo"),
            tender_id=body.get("tender_id"),
            body=body,
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(result, status=200)


# ── the route ──────────────────────────────────────────────────────────────
# THREE segments (`payments/<id>/correct-reference`). `apps/payments/api.py`
# registers only `payments` and `payments/summary` and no `payments/<id>/…`
# pattern; `reversal_api` registers `payments/<id>/reverse`, a different whole
# pattern. Django resolves by URL and not by method, so a duplicate path would
# SHADOW rather than merge — there is none. There is deliberately no
# `GET /payments/{id}` and this adds none.
urlpatterns = [
    path("payments/<str:payment_id>/correct-reference", payment_correct_reference),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 · §8 CS-34 · §11 task 41 · apps/payments/amendments.py ·
#         apps/payments/migrations/0002_rls_w4_and_immutability.py
# generated: 2026-09-02 by the CR-059 W7 correct-what-is-not-money lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(CR-059 task 42 owns S35 and S21 — and must
#            render the control DISABLED with its reason while the write is
#            stubbed) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 the write is stubbed on an open question — see amendments.py.
#   E2 NO PATCH/PUT/DELETE is added to any payment path, by design.
#   E3 the route is MOUNTED although its write is stubbed, so the refusals
#      CS-34 asks to be proved are reachable over real HTTP rather than only in
#      a unit test. Hard-won law 2 cuts the other way here and is why.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
