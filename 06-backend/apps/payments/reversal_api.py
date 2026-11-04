# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-5 · task 15 — "Open the door on a bounced payment".
#           The CR's own words: *"A returned cheque is a routine weekly event,
#           the whole machine is finished and tested, and no person can reach
#           it. Today it is a support call and a hand-written journal entry."*
# Story:    US-PAY-009 (NSF) · J12 the bounce chain
#           Screens: S33 (the Reverse row action) · S35 (the Reverse modal) ·
#           S21 (the reversing row on the Payments tab — nothing to build)
# Rules:    BR-PAY-1070 (NEW 2026-09-01 — reversing a payment is Admin-only and
#           the gate is on the SERVICE as well as the route) · BR-PAY-013 (NSF:
#           reversing row + reversed allocations, AR reinstated at the ORIGINAL
#           due date) · BR-PAY-011 (reversal reasons; only the clearing-side
#           failure has a path — `SUPPORTED_REASONS` refuses the other three by
#           name) · BR-PAY-021 (NSF hangs off the CLEARING side, so the date is
#           the BANK's) · BR-PAY-028 + CLAUDE.md hard rule 6 (idempotency) ·
#           BR-SHL-025 (server-enforced RBAC) · BR-TEN-043 / gate G6 (the
#           caller names the moment; nothing here reads a clock)
# Ruling:   CR-059 §6, 2026-09-01. The collections half was ruled 2026-08-12
#           (OQ-133, *"Restart from the beginning"*).
# Tests:    06-backend/tests/test_cr059_cs5_reverse_door.py
# Impacts:  config/urls.py inclusion · apps/payments/reversal.reverse_payment
#           (now `@require_role`) · 10-scripts/gates/g52_no_door_baseline.txt
# ───────────────────────────────────────────────────────
"""The ONE door on a bounced payment — `POST /payments/{id}/reverse`.

Its own module rather than more lines in `apps/payments/api.py`, on the
`apps/payments/refunds_api.py` and `apps/billing/corrections_api.py` precedent
and for hard-won law 11's reason: a 1,269-line file several lanes edit is where
a pathspec commit eats somebody's work.

**`apps/payments/reversal.py` IS on `10-scripts/gates/human_owned.txt` and this
lane DID change it** — one decorator and the docstring that states it. That is
not the refunds-doors precedent, and the difference is the point: CS-5's one new
rule IS a change to the service (*"the service carries no role gate today"*), so
it cannot be honoured from a route. The change is a 🔒 sensitive-path edit with
its own row in `12-governance/09-human-review-ledger.md`.

THIN by law: the write goes through `reversal.reverse_payment` (sole writer of a
reversing payment row), the read back through `selectors`. **No ORM, no figure
and no rounding in this file.**

═══════════════════════════════════════════════════════════════════════════════
WHAT WAS BEHIND THIS DOOR, AND HOW LONG IT HAD BEEN FINISHED
═══════════════════════════════════════════════════════════════════════════════

`reverse_payment` has been complete and tested since 2026-08-11: it refuses a
payment sitting in a batch it cannot read, writes a NEW negative payment row
with its own `PMT-` number, writes one negative allocation row per row the
original wrote so the bills re-open **at their ORIGINAL due dates**, hands the
ledger the original entry id to mirror inverted, counts the NSF through
customers' own seam, releases the deposit register, posts the bank's own charge
to `6800` when one is given, queues the returned-payment letter and — since
2026-09-01 — restarts the collection ladder when the caller asks.

**Twenty-one live payment endpoints and not one of them reached it.** The whole
of that is `PE-7`'s chain: a **292.87** cheque bounces, the reversing row is
**−292.87**, and the bill re-opens at **292.87** owing. (`PE-7`'s **322.87** is
that plus the utility's **30.00** NSF charge code, which BILLING writes — since
2026-10-30 (`DEF-PAY-10698`) `reverse_payment` asks it to, for the NSF code the
account's plan lists, and the result names the outcome. It said
`nsf_fee_not_added` on every result until then.)

═══════════════════════════════════════════════════════════════════════════════
`SystemAdminOnly`, MIRRORING THE SERVICE — NEVER WIDER (BR-PAY-1070)
═══════════════════════════════════════════════════════════════════════════════

CS-5's one new rule, verbatim: **"reversing a payment is Admin-only, matching
the refund gate; the service carries no role gate today."** So the gate went on
the service first, and this decorator mirrors it. A wider door here would
promise a Billing Clerk a reach the service denies, and the clerk would meet it
as a 403 from a layer they cannot see — `refunds_api`'s own argument, and
`transfers_list`'s before it.

**The clerk who records the payment cannot record its return.** That asymmetry
is the rule as ruled and is the same one `BR-PAY-014` already imposes on money
going out. It is written here so the screen lane (task 16) renders the Reverse
action **visible and disabled with its reason** for a clerk rather than hiding
it (BR-SHL-025), and so nobody reads the narrower gate as an oversight.

═══════════════════════════════════════════════════════════════════════════════
`idempotency_key` IS REQUIRED, AND CS-33 IS WHY IT MATTERS MORE THAN IT LOOKS
═══════════════════════════════════════════════════════════════════════════════

`reverse_payment` computes its idempotency key **only when the caller names a
reference**, exactly as `record_payment` does, and for the reason `OQ-127`
settled: a key the server invented would differ on the second submit and would
dedupe nothing while looking as though it had. So the form mints it and this
door REFUSES without one.

Today a reversal is guarded three times over — the advice-key lookup, the
same-payment lookup, and `uq_payments_reverses` underneath both, which is what
makes a lost race and a replay the same fact. ⚠ **CS-33 (CR-059 task 66) REPLACES
`uq_payments_reverses` WITH A SUMMED CHECK** so a payment may be reversed in
parts, and its own spec says the idempotency guarantee *"has to be re-established
a different way"*. When that lands, **this required key becomes the only
per-submit guard left standing**, so it is required from the first day rather
than added after the index is gone.

A REPLAY ANSWERS **200** WITH THE FIRST REVERSAL AND `created: false`, not 409 —
`account_payments`' argument, applied to the same clerk and the same double
click: *"a 409 toast for a button that worked is a wrong answer a clerk would act
on."* 11b §3 G7's four 409 operations are bill runs, imports, webhooks and tenant
provisioning, and a staff double-click is none of them.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS DOOR DOES **NOT** DO
═══════════════════════════════════════════════════════════════════════════════

* **It does not widen the reasons.** `SUPPORTED_REASONS` is `(nsf,)` and the
  other three are refused BY NAME inside the service, because `BR-PAY-011`'s
  windows, its approval path and its consequence message are not built. That is
  CS-31 (task 35), and CS-5's own screen note says the modal shows **ONE reason
  — the bounce** for exactly this reason.
* **It does not add the customer's NSF fee.** That is billing's charge code
  (`BR-BIL-007`), and every result already says so.
* **It does not decide the ladder.** `resume_collections` defaults to `False`;
  a bounce PAUSES and a person resumes. What the PO ruled on 2026-08-12 is
  WHERE it restarts, not that it should happen with nobody asking.
* **It serves no `GET /payments/{id}`.** There deliberately is none, and this
  route adding one would be inventing a surface — the reversing row appears on
  `GET /payments` and on S21's Payments tab, which is where the CR puts it.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import billing_seam, models, reversal, reversal_rules, selectors
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core import tenancy as core_tenancy
from core.permissions import AdminOrClerk, AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant

# `_payload` and `_required_moment` are imported rather than restated:
# `_required_moment` is the G6 no-clock helper (BR-TEN-043 — *"posting and
# actual dates can differ; ask actual date to user"*), and a second copy of a
# rule that bans reading the server clock is a second place for it to drift
# back in.
#
# ⚠ **`_actor` IS *NOT* IMPORTED, AND `refunds_api` RECORDS WHY.**
# `apps/payments/api._actor` returns `request.user`. That works in the running
# stack only because `IdentitySessionAuthentication` happens to assign
# `user.role` on the way past (`apps/identity/auth.py:179`) — it is not a
# property of the identity `User` row, which declares no such field. The role
# this layer is entitled to read is the one the server attached to the REQUEST,
# `request.tenant_role`, and `reverse_payment` is now `@require_role`-gated, so
# reading the wrong one would be a silent AUTH-002 on every call: the door
# mounted, reachable, and refusing every Admin who used it.
from apps.payments.api import _payload, _required_moment


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id AND role.

    Byte-for-byte the shape `refunds_api._actor` builds, and deliberately a
    second definition rather than an import of it: this is the only other
    role-gated door in the module and importing across two API modules to share
    four lines would make `refunds_api` a dependency of this one for no reason.

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

    Identical in shape and reasoning to `apps/payments/api._as_catalog_refusal`
    and to `refunds_api`'s, and deliberately a separate function rather than an
    import: this module's refusals are `BR-PAY-013`'s, so the fallback `br_ref`
    differs. One code (422 `BIZ_COMPLETENESS`) for all of them, because every
    refusal that arrives here has the same shape and picking among the nine BIZ
    codes per refusal would be this layer interpreting rules it does not own.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-013",
        message_key="payments.record.refused",
        params={"detail": str(refusal)},
    )


def _optional_bank_fee(payload: dict[str, Any]) -> Decimal | None:
    """The utility's OWN charge from its bank, or ABSENT. Never zero.

    **Absent and 0.00 are different facts and only one of them is safe to
    post**: a `0.00` would ask the ledger for a balanced pair of nothing
    against `6800 Bank fees`, and a bank that charged nothing has no entry to
    make. `reverse_payment` types this `Decimal | None` and posts only when it
    is given, so the parse refuses a float rather than converting one — hard
    rule 2, at the boundary, which is the only place a float can still be seen
    for what it is.

    ⚠ **THIS IS NOT THE CUSTOMER'S NSF FEE.** The customer's is a charge code
    billing writes (`BR-BIL-007`); this is what OUR bank charged US for handling
    a returned item, and it posts DR `6800` / CR cash as its own entry touching
    no customer balance. `PE-7`'s **30.00** is the customer's and never arrives
    through this field.
    """
    raw = payload.get("bank_fee")
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "bank_fee", "code": errors.VAL_FORMAT}],
        )
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "bank_fee", "code": errors.VAL_FORMAT}],
        ) from bad


def _optional_reversal_amount(payload: dict[str, Any]) -> Decimal | None:
    """CR-059 CS-33 — how much of the payment came back, or ABSENT for all of it.

    **Absent and 0.00 are different facts**, exactly as `_optional_bank_fee`
    above records for its own field: absent means *"the whole of what still
    stands"* and 0.00 would be a reversal that takes nothing back, which the
    service refuses by name. A float is REFUSED rather than converted (hard
    rule 2) — the boundary is the only place a float can still be seen for what
    it is.
    """
    raw = payload.get("amount")
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
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


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-PAY-1070 — the service's gate, mirrored
def payment_reverse(request: Any, payment_id: str) -> Response:
    """`POST /payments/{id}/reverse` — a cheque came back (US-PAY-009 · CS-5).

    The body is S35's Reverse modal:

        returned_on      the BANK's return date — REQUIRED, never a clock
        reason           `nsf` (the default and, today, the only one served)
        memo             optional
        bank_memo        LBX-04 — the bank's own words, ≤ 60 characters, saved
                         on the REVERSING row (PO 2026-10-30)
        charge_nsf_fee   DEF-PAY-10698 — default TRUE: an `nsf` bounce charges
                         the NSF code the account's plan lists; FALSE is the
                         clerk unticking it and needs …
        nsf_fee_waive_reason   … the reason, REQUIRED when unticked
        bank_fee         OUR bank's charge for the returned item — optional,
                         and absent is not 0.00
        resume_collections   the clerk's choice; default False
        idempotency_key  the modal's submit token — REQUIRED (see the module
                         docstring)

    **201 on a new reversal, 200 on a replay**, both carrying the reversing row
    and `created`. A clerk who has just reversed **292.87** is shown what
    re-opened, because `reverse_payment` worked it out in the same transaction
    and making the screen ask again would be perverse — the same argument
    `account_payments` makes for showing an allocation.

    **`problems[]` travels verbatim**, and on this path it is not decoration: it
    is where the bounce reports the customer's NSF fee it cannot add, the
    account-balance cache it may not write, the notice-history row it will not
    invent — and, per bounce, whether the collection ladder was restarted or
    left paused. The screen groups on the code and renders the sentence.

    ⚠ **THE LOCKED-BATCH CASE IS NOT AN ERROR HERE AND THE SCREEN LANE MUST NOT
    RENDER ONE.** CS-5's screen note asks for *"the locked-batch refusal shown
    BEFORE the button, not as an error after it"* — but the PO closed `OQ-134`
    on 2026-08-12 and **a bounce inside a reconciled batch no longer refuses**:
    the batch total stands and the bounce is new rows. What this path still
    refuses is a payment naming a batch it cannot READ or that does not exist,
    which is a broken reference and not a state a screen can pre-empt.
    """
    require_tenant(request)
    payload = _payload(request)
    if not (payload.get("idempotency_key") or "").strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.record.idempotency_key_required",
            field_errors=[{"field": "idempotency_key", "code": errors.VAL_REQUIRED}],
        )
    try:
        result = reversal.reverse_payment(
            _actor(request),
            payment_id=payment_id,
            returned_on=_required_moment(payload, "returned_on"),
            reason=payload.get("reason") or models.REVERSAL_REASON_NSF,
            memo=payload.get("memo"),
            bank_fee=_optional_bank_fee(payload),
            resume_collections=bool(payload.get("resume_collections")),
            # CR-059 CS-33 — how much of it came back. ABSENT means the whole of
            # what still stands, which is what every caller meant before this
            # change and is still what the S35 modal submits by default.
            amount=_optional_reversal_amount(payload),
            # BR-PAY-885's override: which bills to re-open, in the clerk's own
            # order. Empty means newest-bill-first, which is the rule's default.
            targets=tuple(payload.get("targets") or ()),
            # BR-PAY-011's approval clause (CR-059 CS-31). It is NOT required by
            # this layer: the SERVICE decides whether one is needed, because only
            # it knows whether a bill re-opens or a closed month is touched, and
            # a second copy of that rule here is a second place for it to drift.
            approval=payload.get("approval"),
            idempotency_reference=payload["idempotency_key"],
            # DEF-PAY-10698 — ticked unless the screen says otherwise; a JSON
            # `false` is the clerk unticking it, and the service then demands
            # the reason (PO 2026-10-30).
            charge_nsf_fee=payload.get("charge_nsf_fee", True) is not False,
            nsf_fee_waive_reason=payload.get("nsf_fee_waive_reason"),
            bank_memo=payload.get("bank_memo"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.reversed_payment_dict(result), status=201 if result.created else 200)


# ══════════════════════════════════════════════════════════════════════════
# DEF-PAY-10698 — THE NSF FEE, SHOWN BEFORE CONFIRM (PO 2026-10-30)
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
# Read-only, and every office role: both Reverse doors (Admin) AND the bank
# statement's Match to payment, which an Executive may use (W1/W2,
# `DEF-PAY-10765`/`10766`, PO 2026-10-30) — a quote the Executive is refused
# would put "+$30.00 NSF fee" in front of exactly one of the two roles that commit it.
@permission_classes([AnyTenantRole])
def payment_nsf_fee(request: Any, payment_id: str) -> Response:
    """`GET /payments/{id}/nsf-fee?on=` — "+$30.00 NSF fee" before Confirm.

    BILLING's own quote (`apps/billing/nsf_fee.quote_nsf_fee`): the account →
    its unit → that unit's plan → the plan's NSF charge code, priced on `on`
    (the bank's return date the dialog holds). It is the SAME computation the
    write runs, so the figure the clerk is shown is the figure the fee bill
    carries. Writes nothing.

        {"status": "charged", "code": "NSF", "amount": "30.0000", "currency": "USD"}
        {"status": "nsf_fee_not_set_on_plan", "amount": null, ...}

    `amount` is null whenever no fee would be charged — never 0.00.
    """
    require_tenant(request)
    raw_on = request.query_params.get("on")
    if not raw_on:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.date_required",
            params={"field": "on"},
            field_errors=[{"field": "on", "code": errors.VAL_REQUIRED}],
        )
    try:
        on = date.fromisoformat(str(raw_on)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": "on", "code": errors.VAL_FORMAT}],
        ) from bad
    try:
        payment = reversal._original(core_tenancy.current_tenant_id(), payment_id)
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    quote = billing_seam.nsf_fee_quote(payment.account_id, on_date=on)
    amount = quote.get("amount")
    return Response(
        {
            "status": quote.get("status"),
            "code": quote.get("code"),
            "name": quote.get("name"),
            "amount": None if amount is None else str(amount),
            "currency": quote.get("currency"),
        }
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-059 CS-31 (task 35) — WHAT THIS REVERSAL WILL DO, BEFORE IT IS DONE
# ══════════════════════════════════════════════════════════════════════════
# BR-PAY-011's fourth clause is *"consequence message shown before confirm"*,
# and CS-31 is explicit about where it is composed: *"It must be computed by the
# service, not assembled on the screen, or the warning and the outcome can
# disagree."* So the screen READS this before it offers Confirm, rather than
# adding up allocation rows itself.
#
# A GET, because it writes nothing and changes nothing — the same read can be
# taken twice, by two clerks, with no consequence. It is `SystemAdminOnly` for
# the same reason the write is (BR-PAY-1070): the preview names every bill the
# customer owes and what their credit balance would become, and a role that may
# not take the action has no business being shown its consequences.


@api_view(["GET"])
@permission_classes([SystemAdminOnly])  # BR-PAY-1070 — the write's gate, mirrored
def payment_reversal_plan(request: Any, payment_id: str) -> Response:
    """`GET /payments/{id}/reversal-plan?reason=&on=` — BR-PAY-011's fourth clause.

    Answers, for the reason the clerk has picked and the business day they are
    working on:

      * **the window** — the tender, how many days ago the money moved, the limit
        BR-PAY-011 gives that tender, and whether this is inside it. Returned as
        those parts rather than as a boolean, so S35 can say *"this ACH cleared
        74 days ago — outside the 60-day window"* instead of *"not allowed"*.
      * **whether an approval is needed and WHY** — the payment is applied to an
        issued bill, or the day falls in a closed accounting period.
      * **the consequences** — every bill that re-opens and by how much, and what
        the account's credit balance becomes. A credit that goes below zero is
        flagged: that is money the customer never paid and is a real debt
        (PO 2026-08-11, `OQ-132`).

    `reason` defaults to the bounce, which is the only reason that needs no
    window and no approval, so a caller that omits it gets the LEAST restrictive
    preview and can never be misled into thinking a staff correction is allowed.

    `on` is the caller's business day and is REQUIRED for a staff reason
    (BR-TEN-043, gate G6): a window that expired at midnight in the server's
    timezone would refuse a correction a clerk started before closing time.
    """
    require_tenant(request)
    reason = request.query_params.get("reason") or models.REVERSAL_REASON_NSF
    raw_on = request.query_params.get("on")
    if not raw_on:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.date_required",
            params={"field": "on"},
            field_errors=[{"field": "on", "code": errors.VAL_REQUIRED}],
        )
    try:
        on = date.fromisoformat(str(raw_on)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": "on", "code": errors.VAL_FORMAT}],
        ) from bad
    try:
        payment = reversal._original(core_tenancy.current_tenant_id(), payment_id)
        reason = reversal._reason(reason)
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(reversal_rules.reversal_plan(payment, reason=reason, on=on))


# ══════════════════════════════════════════════════════════════════════════
# CR-175-BRC10 — A BILLING CLERK MARKS AN ACH PAYMENT RETURNED (PO 2026-10-07)
# ══════════════════════════════════════════════════════════════════════════


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # the service's gate, mirrored — never wider
def payment_mark_returned(request: Any, payment_id: str) -> Response:
    """`POST /payments/{id}/mark-returned` — the bank sent an ACH payment back.

    PO, 2026-10-07: *"(a) Let billing clerks mark an ACH payment returned, any
    day, with a reason and the bank code. The same effect follows: balance
    restored, fee and notice."* The body:

        returned_on      the BANK's return date — REQUIRED, never a clock
        reason           `nsf` or `bank_chargeback` — REQUIRED
        return_code      the Nacha code, e.g. `R01` — REQUIRED
        memo             optional
        idempotency_key  the dialog's submit token — REQUIRED

    **A SEPARATE DOOR, NOT A WIDER `/reverse`.** `/reverse` stays
    `SystemAdminOnly` with every reason, a partial amount, targets and the
    bank-fee field; this one carries only what an ACH return needs, and the
    service it calls refuses every other tender by name. Widening `/reverse`
    would promise a clerk a reach the service then denies (`BR-PAY-1070`'s own
    reason for mirroring the gate).

    `reason` and `return_code` are refused HERE when absent, by field, so the
    dialog can put the sentence under the box; their VALUES are the service's
    to judge, so a clerk meets one rule and not two copies of it.
    """
    require_tenant(request)
    payload = _payload(request)
    missing = [
        name
        for name in ("idempotency_key", "reason", "return_code")
        if not str(payload.get(name) or "").strip()
    ]
    if missing:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.markReturned.required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED} for name in missing],
        )
    try:
        result = reversal.mark_ach_returned(
            _actor(request),
            payment_id=payment_id,
            returned_on=_required_moment(payload, "returned_on"),
            reason=str(payload["reason"]).strip(),
            return_code=payload["return_code"],
            memo=payload.get("memo") or None,
            # LBX-04 — the bank's own words (PO 2026-10-30).
            bank_memo=payload.get("bank_memo"),
            idempotency_reference=payload["idempotency_key"],
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.reversed_payment_dict(result), status=201 if result.created else 200)


# ── the route ──────────────────────────────────────────────────────────────
# Three segments, so it shadows nothing in `apps/payments/api.py`: that module
# registers `payments` and `payments/summary` and no `payments/<id>/…` pattern
# of any kind. There is deliberately no `GET /payments/{id}` and this adds none.
urlpatterns = [
    # The static-segment rule this file already states: `reversal-plan` and
    # `reverse` are both three segments and neither shadows the other.
    path("payments/<str:payment_id>/reversal-plan", payment_reversal_plan),
    path("payments/<str:payment_id>/reverse", payment_reverse),
    # DEF-PAY-10698 — three segments, a static last word, shadows nothing.
    path("payments/<str:payment_id>/nsf-fee", payment_nsf_fee),
    # CR-175-BRC10 — three segments, a static last word, shadows nothing.
    path("payments/<str:payment_id>/mark-returned", payment_mark_returned),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 (how the module works today) · §8 CS-5 · §11 task 15 ·
#         apps/payments/reversal.py · BR-PAY-011 · BR-PAY-013 · BR-PAY-021 ·
#         BR-PAY-028 · BR-PAY-1070 · OQ-133 (CLOSED) · OQ-134 (CLOSED)
# generated: 2026-09-01 by the CR-059 W3 doors lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 task 16 owns S33/S35 — P2, and this lane
#            is task 15) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 `apps/payments/reversal.py` IS modified although it is on
#      `human_owned.txt` — one decorator and its docstring. CS-5's new rule is a
#      change to the SERVICE in terms, so it cannot be honoured from a route.
#      Row opened in 12-governance/09-human-review-ledger.md. REPORTED.
#   E2 no `GET /payments/{id}` is minted. §7 records that its absence is
#      deliberate and the reversing row is already on `GET /payments`.
#   E3 the four `BR-PAY-011` reversal reasons stay refused at three of four.
#      CS-31 (task 35) owns the windows, the approval and the consequence
#      message; opening them here would be this lane building that story.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
