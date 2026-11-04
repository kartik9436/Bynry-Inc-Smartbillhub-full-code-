# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-5 · task 15 — `POST /payments/{id}/reverse`, Admin-gated
#           IN THE SERVICE. The CR's own words: *"A returned cheque is a routine
#           weekly event, the whole machine is finished and tested, and no
#           person can reach it."*
# Story:    US-PAY-009 (NSF) · J12 the bounce chain
#           Screens: S33 · S35 · S21
# Rules:    BR-PAY-1070 (NEW 2026-09-01 — reversing a payment is Admin-only, in
#           the SERVICE and not only on the route) · BR-PAY-013 · BR-PAY-011
#           (only the clearing-side failure has a path here) · BR-PAY-021 (the
#           BANK's date, never a clock) · BR-PAY-028 + CLAUDE.md hard rule 6
#           (one reversal per payment, whatever the submit does) · BR-SHL-025 ·
#           hard rule 4 (a reversal is a NEW row) · hard rule 5 (only the
#           ledger posts) · hard rule 7 (audit) · hard-won law 2 (built is not
#           wired) · hard-won law 7 (prove it RED first)
# ───────────────────────────────────────────────────────
"""The door on a bounced payment, and the gate that decides who may open it.

The bounce ARITHMETIC — the −292.87 reversing row, the bills re-opening at their
ORIGINAL due dates, the ledger mirror, the NSF count, the ladder restart — is
proved in `test_us_pay_009_nsf.py` and `test_cr059_cs5_ladder_restart.py`
against the service, and none of it is restated here. What is proved HERE is the
four claims only a route can make:

  1. **A bounce can be REACHED.** Twenty-one live payment endpoints and not one
     of them called `reverse_payment`, which has been complete since 2026-08-11.
  2. **Admin-only, twice** — at the door AND inside the service, so a job, a
     shell or a second endpoint that forgot to gate is refused all the same
     (BR-SHL-025, and `BR-PAY-1070` is the rule CS-5 minted).
  3. **A double-clicked Reverse writes ONE row**, and answers 200 rather than a
     red 409 for a button that worked.
  4. **No figure is invented at the boundary** — the amount the door answers
     with is the service's, negative, exact, and beside its CHAR(3) code.

RED PROOF (hard-won law 7). Run in a DETACHED worktree at the pinned tip, never
by moving the shared tree, and quoted here as OBSERVED rather than as predicted:

  * **the door.** At the tip this whole file cannot even be collected —
    `ImportError: cannot import name 'reversal_api' from 'apps.payments'` — and
    all four of this lane's routes answer `Resolver404`. That is stronger than
    mutating the urlpattern, because there is nothing there to mutate.
  * **the service gate.** With `@permissions.require_role(...)` deleted from
    `reverse_payment`, `test_a_billing_clerk_is_refused_by_the_service_itself`
    fails `Failed: DID NOT RAISE <class 'core.errors.AuthError'>`.
  * **and the shape of the defect, read straight off the tip:**
    `reverse_payment`, `issue_refund` and `clear_refund` are all UNGATED while
    `approve_refund` beside them is GATED.

⚠ Two mutations named in the first draft of this docstring were NOT run and the
claim is removed rather than left standing: widening the door to `AdminOrClerk`,
and dropping `idempotency_reference`. Both are asserted GREEN by the cases below
and neither has been shown to fail on its own.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.payments import models, reversal, reversal_api
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import a_payment, pe1_bills
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: J12's own date — the bank returns the cheque on 3 Aug. An INPUT, never a
#: clock (BR-PAY-021 / BR-TEN-043, gate G6).
RETURNED_ON = datetime(2026, 8, 3, 11, 15, tzinfo=UTC)

#: PE-7, verbatim: *"cleared check 292.87 bounces → reversing payment row
#: −292.87"*. The bank's own charge is separate and is not this figure.
PE7_REVERSAL = Decimal("-292.87")


def _call(actor, tenant, *, role="system_admin", data=None, payment_id="P-1"):
    return api_call(
        reversal_api.payment_reverse,
        "post",
        user=actor.user,
        role=role,
        tenant=tenant,
        data=data if data is not None else {},
        payment_id=payment_id,
    )


def _body(**overrides):
    values = {
        "returned_on": RETURNED_ON.isoformat(),
        "idempotency_key": str(uuid.uuid4()),
    }
    values.update(overrides)
    return values


def _a_cleared_cheque(tenant, actor, *, account_no=None):
    """PE-1's two bills, met by PE-4's cheque — the thing that then bounces."""
    account = (
        an_account(actor, tenant, account_no=account_no)
        if account_no is not None
        else an_account(actor, tenant)
    )
    pe1_bills(tenant, account)
    return account, a_payment(actor, account)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ADDRESS — the whole of CS-5's "no person can reach it"
# ══════════════════════════════════════════════════════════════════════════


def test_the_reverse_door_is_mounted():
    """CS-5's defect in one line: the machine was finished and had no door.

    Resolved through `config/urls.py` rather than against `urlpatterns`
    directly, because the include is the half that has gone missing twice in
    this repo already (`apps/payments/api.py` and `apps/ledger/api.py` both
    landed complete behind no `include`).
    """
    match = resolve("/api/brazos/payments/11111111-1111-1111-1111-111111111111/reverse")
    assert match.func is reversal_api.payment_reverse


def test_the_door_does_not_shadow_the_payments_list():
    """`payments/<id>/reverse` is three segments and `payments` is one.

    Asserted rather than reasoned about: `apps/payments/api.py` is included
    BEFORE this module, and Django can only reach the first view given one path
    — which is a bug G52 found in the DEF-2032 lane's own code while it was
    being written.
    """
    from apps.payments import api as payments_api

    assert resolve("/api/brazos/payments").func is payments_api.payments
    assert resolve("/api/brazos/payments/summary").func is payments_api.payments_summary


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE BOUNCE, THROUGH THE DOOR
# ══════════════════════════════════════════════════════════════════════════


def test_an_admin_reverses_a_bounced_cheque_through_the_door(brazos, marcus, dana):
    """PE-7 end to end over HTTP — **−292.87**, and the bill re-opens.

    The figures are the service's and are asserted here only to prove nothing is
    recomputed at the boundary: `amount` is NEGATIVE and stays negative, because
    a screen rendering it unsigned would tell a clerk a second payment of 292.87
    had arrived.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    answered = _call(dana, brazos, data=_body(), payment_id=str(recorded.payment_id))

    assert answered.status_code == 201, answered.data
    assert answered.data["created"] is True
    assert Decimal(answered.data["amount"]) == PE7_REVERSAL, "PE-7: the reversing row"
    assert answered.data["reason"] == models.REVERSAL_REASON_NSF
    assert answered.data["original_payment_id"] == str(recorded.payment_id)
    # CLAUDE.md rule 2 — every amount travels beside its CHAR(3) code.
    assert answered.data["currency"] and len(answered.data["currency"]) == 3
    # Hard rule 5 — the ledger was asked, and it stamped its id back.
    assert answered.data["journal_entry_id"] is not None
    # The bills that re-opened, with the POSITIVE amount put back on each.
    assert answered.data["reopened"], "a bounce that re-opened nothing is not PE-7"
    assert Decimal(answered.data["allocations_reversed"]) == Decimal("292.87")

    with tenant_ctx(brazos):
        rows = models.Payment.objects.filter(reverses_payment_id=recorded.payment_id)
        assert rows.count() == 1
        assert rows.first().status == models.PAYMENT_REVERSED


def test_the_result_carries_what_the_bounce_could_not_do(brazos, marcus, dana):
    """`problems[]` verbatim — `PE-7`'s missing **30.00** is named, not hidden.

    BR-BIL-007 puts the customer's NSF fee in billing as a charge code, so this
    path cannot add it and says so on every result. A screen that dropped
    `problems` would show a clerk a balance of 292.87 where the customer owes
    322.87 and nothing anywhere would say why.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    answered = _call(dana, brazos, data=_body(), payment_id=str(recorded.payment_id))

    codes = {problem["code"] for problem in answered.data["problems"]}
    # DEF-PAY-10698 (2026-10-30) — this asserted the standing gap
    # `nsf_fee_not_added`. The fee is now the account's plan's NSF code; this
    # world's account has no unit, so the bounce NAMES that absence.
    assert "nsf_fee_not_added" not in codes
    assert "nsf_fee_no_plan" in codes
    # The ladder half of CR-059 CS-5: a default bounce PAUSES and says so.
    assert "collection_ladder_paused" in codes
    for problem in answered.data["problems"]:
        assert problem["br_ref"] and problem["detail"], problem


def test_asking_to_resume_collections_reaches_the_service(brazos, marcus, dana):
    """The clerk's choice travels — `resume_collections` is S35's checkbox.

    The ladder ARITHMETIC is `test_cr059_cs5_ladder_restart.py`'s. What is
    proved here is only that the door carries the choice at all: it was a
    parameter nothing read until 2026-09-01, and a door that dropped it would
    put the product straight back in that state (hard-won law 2).
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    answered = _call(
        dana,
        brazos,
        data=_body(resume_collections=True),
        payment_id=str(recorded.payment_id),
    )

    codes = {problem["code"] for problem in answered.data["problems"]}
    assert "collection_ladder_paused" not in codes
    assert {"collection_ladder_restarted", "collection_ladder_not_restarted"} & codes


# ══════════════════════════════════════════════════════════════════════════
# 3 · BR-PAY-1070 — ADMIN-ONLY, AND GATED TWICE
# ══════════════════════════════════════════════════════════════════════════


def test_a_billing_clerk_is_refused_at_the_door(brazos, marcus):
    """CS-5's one new rule: *"reversing a payment is Admin-only"*.

    The clerk who recorded the 292.87 cheque cannot record its return. That
    asymmetry is the rule as ruled and is the same one BR-PAY-014 imposes on
    money going out; it is asserted so a later lane widening the door has to
    delete a test rather than change a decorator.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    refused = _call(
        marcus,
        brazos,
        role="billing_clerk",
        data=_body(),
        payment_id=str(recorded.payment_id),
    )

    assert refused.status_code == 403, refused.data
    with tenant_ctx(brazos):
        assert not models.Payment.objects.filter(
            reverses_payment_id=recorded.payment_id
        ).exists(), "a refused reversal writes nothing"


def test_an_executive_is_refused_too(brazos, marcus, dana):
    """Admin-only means Admin, not "any senior role".

    A4 gives the Executive the finance/reconcile column, which is why CS-6 puts
    the refund CLEARING step in their hands — a bank fact. Reversing a payment
    is not a bank fact this end: it writes money rows and re-opens a customer's
    bills, so it stays where BR-PAY-1070 put it.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    refused = _call(
        dana, brazos, role="executive", data=_body(), payment_id=str(recorded.payment_id)
    )
    assert refused.status_code == 403, refused.data


def test_a_billing_clerk_is_refused_by_the_service_itself(brazos, marcus):
    """BR-SHL-025 — **server-side enforcement is THE enforcement.**

    The route is not the guard. This calls `reverse_payment` directly with a
    clerk, the way a job, a shell or a second endpoint would, and it must refuse
    without any HTTP layer present. `approve_refund` and `approve_write_off`
    have always been gated this way; `reverse_payment` was not, and CS-5's own
    words for that were *"the service carries no role gate today"*.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

        with pytest.raises(errors.AuthError) as refusal:
            reversal.reverse_payment(
                marcus,  # billing_clerk
                payment_id=recorded.payment_id,
                returned_on=RETURNED_ON,
                idempotency_reference=uuid.uuid4(),
            )
        assert refusal.value.code == errors.AUTH_PERMISSION_DENIED
        assert not models.Payment.objects.filter(reverses_payment_id=recorded.payment_id).exists()


def test_the_door_is_no_wider_than_the_service(brazos):
    """The two gates name the SAME role set, read off both declarations.

    A door wider than its service promises a reach the service denies, and the
    user meets it as a 403 from a layer they cannot see (`refunds_api`'s own
    argument). Read structurally rather than by exercising every role, so it
    stays true when a fourth role is added.
    """
    from core.permissions import SYSTEM_ADMIN, SystemAdminOnly

    (door,) = reversal_api.payment_reverse.cls.permission_classes
    assert door is SystemAdminOnly
    assert door.allowed_roles == frozenset({SYSTEM_ADMIN})
    # And the service really is decorated — `require_role` sets `__wrapped__`.
    assert hasattr(reversal.reverse_payment, "__wrapped__"), (
        "`reverse_payment` is not `@require_role`-gated, so the door above is the "
        "only guard and BR-PAY-1070's 'in the service as well' is untrue."
    )


# ══════════════════════════════════════════════════════════════════════════
# 4 · HARD RULE 6 — ONE REVERSAL, WHATEVER THE SUBMIT DOES
# ══════════════════════════════════════════════════════════════════════════


def test_a_double_clicked_reverse_writes_one_row(brazos, marcus, dana):
    """The same submit token twice → ONE reversing row, and **200, not 409**.

    ⚠ CS-33 (task 66) replaces `uq_payments_reverses` with a summed check so a
    payment can be reversed in parts, and its own spec says the idempotency
    guarantee *"has to be re-established a different way"*. When that index
    goes, this token is the only per-submit guard left standing — which is why
    the door requires one from its first day rather than after the index is
    gone.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    body = _body()
    first = _call(dana, brazos, data=body, payment_id=str(recorded.payment_id))
    second = _call(dana, brazos, data=body, payment_id=str(recorded.payment_id))

    assert first.status_code == 201 and first.data["created"] is True
    assert second.status_code == 200, "a button that worked must not answer red"
    assert second.data["created"] is False
    assert second.data["id"] == first.data["id"], "the FIRST reversal is reported"

    with tenant_ctx(brazos):
        assert models.Payment.objects.filter(reverses_payment_id=recorded.payment_id).count() == 1


def test_a_submit_with_no_token_is_refused_rather_than_given_one(brazos, marcus, dana):
    """`OQ-127`'s argument, applied to money going back out.

    `reverse_payment` stores no key when the caller names none, so a server that
    generated one here would produce a different string on the second submit and
    dedupe nothing **while looking as though it had**. The only honest options
    are "require it" and "reverse the payment twice".
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    refused = _call(
        dana,
        brazos,
        data={"returned_on": RETURNED_ON.isoformat()},
        payment_id=str(recorded.payment_id),
    )

    assert refused.status_code == 422, refused.data
    assert refused.data["code"] == errors.VAL_REQUIRED
    assert refused.data["message_key"] == "payments.record.idempotency_key_required"
    with tenant_ctx(brazos):
        assert not models.Payment.objects.filter(reverses_payment_id=recorded.payment_id).exists()


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE BOUNDARY REFUSES RATHER THAN GUESSES
# ══════════════════════════════════════════════════════════════════════════


def test_a_missing_return_date_is_refused_rather_than_read_off_the_clock(brazos, marcus, dana):
    """BR-PAY-021 / BR-TEN-043 and gate G6 — the BANK names the moment.

    A date taken from the clock would let the minute a request happened to be
    processed decide which accounting period the reversal lands in, and PE-7's
    whole point is that a bounce is dated 3 Aug while the payment was 18 Jul.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    refused = _call(
        dana,
        brazos,
        data={"idempotency_key": str(uuid.uuid4())},
        payment_id=str(recorded.payment_id),
    )

    assert refused.status_code == 422, refused.data
    assert refused.data["code"].startswith("VAL")


def test_a_staff_reversal_answers_to_br_pay_011_through_the_door(brazos, marcus, dana):
    """BR-PAY-011's other three reasons are OPEN — and the rule stands in the door.

    ⚠ **THIS CASE ASSERTED A FLAT REFUSAL UNTIL 2026-09-03 AND IT IS INVERTED,
    NOT DELETED.** `SUPPORTED_REASONS` was `(nsf,)` because a general Reverse
    needs windows (ACH 60 days, card 120), an approval path and a consequence
    message, and **none of the three was built** — without the refusal the door
    would have been a general Reverse with a default, letting a clerk reverse an
    ACH payment on day 200 with nobody approving it. Gate G10 caught exactly
    that in August and the refusal was right while it stood.

    `CR-059` CS-31 (task 35) built all three, so what the door now enforces is
    the rule rather than the absence of it: this cheque is already applied to an
    issued bill, so a staff correction of it is refused **for want of an
    approval**, by name, with the trigger stated — and the same request carrying
    one goes through.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    refused = _call(
        dana,
        brazos,
        data=_body(reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR),
        payment_id=str(recorded.payment_id),
    )

    assert refused.status_code == 422, refused.data
    assert refused.data["br_ref"] == "BR-PAY-011"
    assert "needs an approval" in refused.data["params"]["detail"]
    assert "applied_to_an_issued_bill" in refused.data["params"]["detail"]

    approved = _call(
        dana,
        brazos,
        data=_body(
            reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR,
            approval="approved by D. Whitfield — recorded against the wrong account",
        ),
        payment_id=str(recorded.payment_id),
    )
    assert approved.status_code == 201, approved.data


def test_a_float_bank_fee_is_refused_at_the_boundary_and_never_converted(brazos, marcus, dana):
    """CLAUDE.md rule 2 — money is never a binary fraction, at any point.

    Refused rather than converted, because a conversion hides the place money
    became binary. The boundary is the only layer that can still see a float for
    what it is: by the time it reaches a `Decimal` column it has already lost
    the digits somebody typed.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    refused = _call(
        dana,
        brazos,
        data=_body(bank_fee=12.0),
        payment_id=str(recorded.payment_id),
    )

    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "payments.record.amount_invalid"


def test_an_absent_bank_fee_is_absent_and_never_zero(brazos, marcus, dana):
    """A bank that charged nothing has no entry to make.

    `0.00` would ask the ledger for a balanced pair of nothing against 6800 Bank
    fees. `reverse_payment` types the argument `Decimal | None` and posts only
    when it is given, so the door must not fill the gap with a zero.
    """
    with tenant_ctx(brazos):
        _account, recorded = _a_cleared_cheque(brazos, marcus)

    answered = _call(dana, brazos, data=_body(), payment_id=str(recorded.payment_id))

    assert answered.data["bank_fee"] is None
    assert answered.data["bank_fee_entry_id"] is None


def test_a_neighbouring_utility_cannot_reverse_this_tenants_payment(brazos, lonestar, marcus, erin):
    """CLAUDE.md rule 1 — a cross-tenant id resolves to nothing, never to a row.

    Erin is the isolation tenant's own System Admin, so she passes BOTH gates
    — `SystemAdminOnly` at the door and `@require_role` in the service — and is
    stopped by TENANT SCOPING alone. That is the direction worth asserting: a
    role check that happened to be doing the isolation work would look
    identical here and would fall over the day a second Admin exists.

    The refusal is the ordinary *"not one of this tenant's payments"* and never
    a 403, which would confirm the payment exists (HR-1).

    ⚠ **THE PAYMENT IS BUILT IN BRAZOS AND CALLED FROM LONESTAR, rather than
    the other way round.** An earlier draft built the cheque inside the
    isolation tenant and failed on a queue write reaching a broker that is
    deliberately not running — which proved nothing about isolation and
    everything about the fixture. One tenant's data, the other tenant's
    request, is the smaller and more honest shape.
    """
    with tenant_ctx(brazos):
        _account, ours = _a_cleared_cheque(brazos, marcus)

    refused = _call(erin, lonestar, data=_body(), payment_id=str(ours.payment_id))

    assert refused.status_code == 422, refused.data
    assert refused.status_code != 403, "a cross-tenant miss is a MISS, never a denial"
    with tenant_ctx(brazos):
        assert not models.Payment.objects.filter(
            reverses_payment_id=ours.payment_id
        ).exists(), "the neighbour's request wrote nothing in our tenant"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 · §8 CS-5 · §11 task 15 · apps/payments/reversal_api.py ·
#         apps/payments/reversal.py · BR-PAY-1070 · BR-PAY-011 · BR-PAY-013
# generated: 2026-09-01 by the CR-059 W3 doors lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 task 16 owns P2) E=deferred(same) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 the bounce ARITHMETIC is not restated here — it is US-PAY-009's, and a
#      second copy of PE-7 is a second place for it to drift.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
