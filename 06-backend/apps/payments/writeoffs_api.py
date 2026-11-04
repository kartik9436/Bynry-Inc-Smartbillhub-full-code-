# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-25 (task 62) + CS-26 (task 64) — "Reject a request, and
#           correct an approved write-off" and "Report what was written off, and
#           why". The CR's own words: *"Today an approver can only approve it or
#           ignore it… once approved, receivables have been permanently reduced
#           and there is no path back"* and *"nothing assembles it"*.
# Story:    US-PAY-012 (write-offs)   Screens: S36 (P10 — the queue and the
#           bad-debt tab) · S34 (the account reappearing at its original age)
# Rules:    BR-PAY-020 (initiated in payments, approved + REPORTED in finance) ·
#           BR-PAY-1120 (NEW 2026-09-01 — the four-state set, both new acts
#           Admin-only, and the gate on the SERVICE as well as the route) ·
#           BR-PAY-002 (append-only) · BR-SHL-025 (server-enforced RBAC) ·
#           BR-TEN-043 / gate G6 (the caller names the date; no clock here)
# Tests:    06-backend/tests/test_cr059_cs25_write_off_states.py ·
#           06-backend/tests/test_cr059_cs26_bad_debt_report.py
# Impacts:  config/urls.py inclusion · apps/payments/writeoffs.py (the services)
#           · apps/payments/bad_debt.py (the read)
# ───────────────────────────────────────────────────────
"""The two missing write-off doors, and the bad-debt report.

Its own module rather than more lines in `apps/payments/api.py`, on the
`apps/payments/reversal_api.py` and `refunds_api.py` precedent and for hard-won
law 11's reason: a 1,300-line file several lanes edit is where a pathspec commit
eats somebody's work, and three sibling lanes are in `apps/payments` today.

THIN by law: every write goes through `writeoffs.py` (the sole writer of a
write-off row) and every figure through `bad_debt.py`. **No ORM, no arithmetic
and no rounding in this file.**

═══════════════════════════════════════════════════════════════════════════════
`SystemAdminOnly`, MIRRORING THE SERVICE — NEVER WIDER (BR-PAY-1120)
═══════════════════════════════════════════════════════════════════════════════
Both new acts carry `@require_role(SYSTEM_ADMIN)` on the SERVICE, and these
decorators mirror them. A wider door would promise a Billing Clerk a reach the
service denies, and the clerk would meet it as a 403 from a layer they cannot
see — `reversal_api`'s own argument, and `refunds_api`'s before it.

**Rejecting is Admin-only because it is the same decision as approving.** CS-25
says *"A request may be rejected with a reason by an APPROVER"*, and an approver
is who BR-PAY-020 already names. A clerk who could reject would be able to close
their own colleague's request without the second pair of eyes the whole split
exists to provide. **So the screen (task 63) renders Reject and Reverse VISIBLE
AND DISABLED with their reason for a clerk, never hidden** (BR-SHL-025).

The bad-debt report is `AnyTenantRole`: A4 puts Reports at *Staff/Clerk read,
Executive full*, and it is a READ that writes nothing.

═══════════════════════════════════════════════════════════════════════════════
WHY THERE IS NO `idempotency_key` ON THESE TWO, WHEN THE BOUNCE DOOR HAS ONE
═══════════════════════════════════════════════════════════════════════════════
`POST /payments/{id}/reverse` requires a submit token because CS-33 is about to
remove `uq_payments_reverses` and leave that token the last per-submit guard
standing. Nothing of the kind is planned here, and both of these acts are
already idempotent on facts the DATABASE holds:

  * **reject** — the row's own status. A second click finds `rejected` and
    answers 200 with the first decision, rather than overwriting the reason the
    first approver gave.
  * **reverse** — `uq_write_offs_reverses`, a partial unique index on
    `(tenant, reverses_write_off_id)`. A write-off is reversed ONCE, and it is
    the index rather than the SELECT that makes a lost race and a replay the
    same fact (hard rule 6).

A REPLAY ANSWERS **200** WITH THE FIRST RESULT AND `created: false`, not 409 —
`account_payments`' argument applied to the same clerk and the same double
click: *"a 409 toast for a button that worked is a wrong answer a clerk would act
on."* 11b §3 G7's four 409 operations are bill runs, imports, webhooks and
tenant provisioning, and a staff double-click is none of them.

═══════════════════════════════════════════════════════════════════════════════
WHAT THESE DOORS DO **NOT** DO
═══════════════════════════════════════════════════════════════════════════════
* **No `GET /write-offs/{id}`.** `GET /write-offs` already serves every row of
  the queue with its reason, its note, both decisions and its ledger link; a
  detail route would add nothing and would be a surface to keep in step.
* **They do not touch the Outstandings figure.** Approving a write-off never
  removed the debt from S34 and reversing one never puts it back —
  **`DEF-3121`**, filed and not fixed, because closing it writes money onto the
  allocation path. Every reversal result says so in `problems[]`.
* **They do not add an allowance model.** `CR-060 C5` is the open question of
  whether direct write-off is acceptable at all, and this lane may not answer it.
"""

from datetime import date
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import errors
from core.permissions import AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant

from apps.payments import bad_debt, writeoffs
from apps.payments.exceptions import PaymentRuleError

# `_payload` and `_business_date` are imported rather than restated:
# `_business_date` is the G6 no-clock helper (BR-TEN-043 — *"posting and actual
# dates can differ; ask actual date to user"*), and a second copy of a rule that
# bans reading the server clock is a second place for it to drift back in.
#
# ⚠ **`_actor` IS *NOT* IMPORTED, AND `refunds_api` RECORDS WHY.**
# `apps/payments/api._actor` returns `request.user`. That works in the running
# stack only because `IdentitySessionAuthentication` happens to assign
# `user.role` on the way past — it is not a property of the identity `User` row,
# which declares no such field. The role this layer is entitled to read is the
# one the server attached to the REQUEST, `request.tenant_role`, and both
# services below are `@require_role`-gated, so reading the wrong one would be a
# silent AUTH-002 on every call: the door mounted, reachable, and refusing every
# Admin who used it.
from apps.payments.api import _business_date, _payload, _required_moment


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id AND role.

    Byte-for-byte the shape `reversal_api._actor` and `refunds_api._actor` build,
    and deliberately a third definition rather than an import of either: this is
    a third role-gated door module, and importing across two API modules to share
    four lines would make one a dependency of the other for no reason.

    The role is server-attached by the identity layer (BE-04) and is never client
    input (BR-TEN-003). `audit_log.actor_user_id` is hard rule 7's evidence half,
    so `id` comes from the session user and from nowhere else.
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows.

    Identical in shape to `apps/payments/api._as_catalog_refusal` and
    deliberately a separate function rather than an import: this module's
    refusals are `BR-PAY-020`'s and `BR-PAY-1120`'s, so the fallback `br_ref`
    differs. One code (422 `BIZ_COMPLETENESS`) for all of them, because every
    refusal arriving here has the same shape and picking among the nine BIZ codes
    per refusal would be this layer interpreting rules it does not own.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-020",
        # ⛔ **DEF-3420 — THIS RAISED `payments.record.refused` UNTIL 2026-09-02,
        # AND IT RESOLVED, WHICH IS WHY NOTHING CAUGHT IT.** That sentence reads
        # *"This payment can't be recorded as asked. Check the date, amount and
        # account."* — so an approver told that an already-reversed write-off
        # cannot be reversed again was shown an error about a payment they were
        # not recording, in all eleven languages. `G32` asks whether a raised
        # key RESOLVES and this one did; no gate in this repository can ask
        # whether a sentence that resolves is the RIGHT sentence. `DEF-3203` was
        # this same path with the key resolving to NOTHING, and that was the
        # easier failure to see, because silence looks broken and wrong copy
        # looks healthy. The key now names the ACT rather than the module.
        message_key="payments.write_off.refused",
        params={"detail": str(refusal)},
    )


def _result_dict(result: Any) -> dict[str, Any]:
    """One write-off decision, as the screen reads it.

    `amount` is served at FOUR decimals beside its CHAR(3) code and is never
    re-rounded here (hard rule 2, PO re-sign 2026-08-22): the display half is
    `MoneyCell`'s and a second formatter would be a second money policy.
    """
    return {
        "id": result.write_off_id,
        "status": result.status,
        "account_id": result.account_id,
        "amount": f"{result.amount:.4f}",
        "posted_to_ledger": result.posted_to_ledger,
        "journal_entry_id": (str(result.journal_entry_id) if result.journal_entry_id else None),
        "reverses_write_off_id": result.reverses_write_off_id,
        "plan_closed": result.plan_closed,
        "plan_reopened": result.plan_reopened,
        # Verbatim, and on this path it is not decoration: it is where a reversal
        # reports the plan it could not reopen and the Outstandings figure it
        # cannot move. The screen groups on the code and renders the sentence.
        "problems": [dict(problem) for problem in result.problems],
    }


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-PAY-1120 — the service's gate, mirrored
def write_off_reject(request: Any, write_off_id: str) -> Response:
    """`POST /write-offs/{id}/reject` — the approver's other answer (CS-25).

    The body is S36's Reject modal:

        rejected_on   the business date of the decision — REQUIRED, never a clock
        reason        REQUIRED free text — what the requester will be shown

    **200 on the decision and 200 on a replay**, both carrying the row. Nothing
    money-bearing happens on this path at all: no journal entry, no balance
    movement, no plan closed, no letter — and the result says all four in
    `problems[]` rather than leaving a screen to infer it.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = writeoffs.reject_write_off(
            _actor(request),
            write_off_id=write_off_id,
            rejected_on=_business_date(payload, "rejected_on"),
            reason=payload.get("reason") or "",
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(_result_dict(result))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-PAY-1120 — the service's gate, mirrored
def write_off_reverse(request: Any, write_off_id: str) -> Response:
    """`POST /write-offs/{id}/reverse` — put a wrongly-approved one back (CS-25).

    The body is S36's Reverse modal:

        reversed_on   the business date the correction is made — REQUIRED
        posted_at     the posting instant for the mirror — REQUIRED, never a clock
        reason        REQUIRED free text — why the write-off should not stand

    **201 on a new reversing row, 200 on a replay.** The response carries the
    NEW row's id, `reverses_write_off_id` naming the original, the mirror's
    ledger entry, and the plan that was reopened — worked, on US-PAY-012 TC-2's
    figure: a **948.20** write-off reverses to a **948.20** row at status
    `reversed`, the books post **DR accounts receivable 948.20 / CR write-off
    948.20**, and bad debt for the year nets to **0.00**.

    ⚠ **THE ORIGINAL IS NOT TOUCHED AND NO ROUTE HERE COULD TOUCH IT.** There is
    deliberately no PUT, PATCH or DELETE on a write-off anywhere in this product;
    hard rule 4 is the reason, and migration 0011's trigger is the database's
    half of it.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = writeoffs.reverse_write_off(
            _actor(request),
            write_off_id=write_off_id,
            reversed_on=_business_date(payload, "reversed_on"),
            posted_at=_required_moment(payload, "posted_at"),
            reason=payload.get("reason") or "",
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    replayed = any(problem.get("code") == "already_reversed" for problem in result.problems)
    return Response(_result_dict(result), status=200 if replayed else 201)


def _window(request: Any) -> tuple[date, date]:
    """The report window, from the query string. BOTH required, never a clock.

    BR-TEN-043 and gate G6: a board pack produced at 23:58 and re-run at 00:02
    must be the same document, and a default of *"this year"* computed here would
    be a clock read in the server's timezone.
    """
    values = []
    for name in ("f.start", "f.end"):
        raw = request.query_params.get(name)
        if not raw:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="payments.date_required",
                params={"field": name},
            )
        try:
            values.append(date.fromisoformat(str(raw)[:10]))
        except ValueError as bad:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.date_invalid",
                field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
            ) from bad
    return values[0], values[1]


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk read, Executive full
def bad_debt_report(request: Any) -> Response:
    """`GET /bad-debt?f.start=&f.end=` — CS-26's report (S36 Revenue & AR).

    Bad debt by reason and by month over the window, netted for CS-25 reversals,
    with the ledger's own write-off total computed independently and served
    beside it. Money at four decimals, shares at six, both beside a CHAR(3) code.

    `f.reason` narrows the ACCOUNT list (`/bad-debt/accounts`), not this — the
    totals are the whole point of the report and a filtered total that still
    called itself the total would be the defect this exists to avoid.
    """
    require_tenant(request)
    start, end = _window(request)
    try:
        return Response(bad_debt.bad_debt(start=start, end=end))
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def bad_debt_accounts(request: Any) -> Response:
    """`GET /bad-debt/accounts?f.start=&f.end=&f.reason=` — the rows behind a bar.

    Same window and same statuses as the report, one row per write-off, so a
    reviewer clicking *"uncollectible, 2,840.00"* sees exactly the rows that
    figure is made of and the two reads can never disagree about what is in it.
    """
    require_tenant(request)
    start, end = _window(request)
    try:
        return Response(
            bad_debt.bad_debt_accounts(
                start=start, end=end, reason=request.query_params.get("f.reason")
            )
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


# ── the routes ─────────────────────────────────────────────────────────────
# `write-offs/<id>/reject` and `…/reverse` are three segments and shadow nothing:
# `apps/payments/api.py` registers `write-offs` and `write-offs/<id>/approve` and
# no other `write-offs/…` pattern. `bad-debt` and `bad-debt/accounts` are claimed
# by no include in `config/urls.py`, and the STATIC segment is declared first so
# it is matched before any pattern that could swallow it — the ordering rule that
# file already states for payments.
urlpatterns = [
    path("write-offs/<str:write_off_id>/reject", write_off_reject),
    path("write-offs/<str:write_off_id>/reverse", write_off_reverse),
    path("bad-debt/accounts", bad_debt_accounts),
    path("bad-debt", bad_debt_report),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 (how the module works today) · §8 CS-25 + CS-26 · §11 tasks 62 and 64 · apps/payments/writeoffs.py · apps/payments/reversal_api.py (the precedent) · BR-PAY-020 · BR-PAY-002 · BR-PAY-037 · BR-PAY-1120 · BR-SHL-025
# generated: 2026-09-01 by the CR-059 W11 write-off lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 tasks 63 and 65 own P10, and this lane is 62 and 64) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every route proved RED first at the pinned tip (`Resolver404`) and each service gate proved RED by deleting its decorator — transcripts in the lane report
# exceptions: (1) NO `idempotency_key` ON EITHER DOOR. Both acts are idempotent on facts the database holds — the row's own status, and `uq_write_offs_reverses` — and nothing here is about to remove either, which is what made the token mandatory on the bounce door
#         (2) NO `GET /write-offs/{id}`. The queue read already serves every field a detail view would
#         (3) THE REPORT WINDOW IS REQUIRED AND HAS NO DEFAULT — a default would be a clock read here (BR-TEN-043, G6)
#         (4) `DEF-3121` IS NAMED, NOT FIXED: neither approving nor reversing a write-off moves the Outstandings figure, because nothing on that path writes an allocation
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
