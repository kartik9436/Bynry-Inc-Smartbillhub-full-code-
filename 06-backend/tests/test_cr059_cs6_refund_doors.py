# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-6 · task 17 — the three MISSING refund routes and the
#           role gate added IN THE SERVICE for issue and clear. The CR's own
#           words: *"A refund can be approved and voided from a screen but not
#           raised, paid out or cleared. The services are complete; only the
#           demo seeder calls them. So the approval queue that IS routed can
#           never have anything in it."*
# Story:    US-PAY-011 (refunds) · J15 steps 1–4
#           Screens: S58 (raise + issue) · S39 (clear, beside the bank line)
# Rules:    BR-PAY-1071 (NEW 2026-09-01 — issue is Admin-only, clear is Admin or
#           Executive, both in the SERVICE) · BR-PAY-014 (only from a REAL
#           credit balance; Admin approval; check/ACH v1; DR customer-credit /
#           CR cash) · BR-PAY-037 (both approval acts recorded distinctly) ·
#           BR-CUS-054 + OQ-135 CLOSED (offset first) · BR-SHL-025 ·
#           BR-TEN-043 / gate G6 (no clock) · CLAUDE.md hard rule 2 (money) ·
#           rule 4 (immutability) · rule 5 (only the ledger posts) · rule 6
#           (idempotency) · hard-won law 2 · hard-won law 7 (prove it RED)
# ───────────────────────────────────────────────────────
"""Raise, issue and clear — the three refund steps nobody could reach.

The refund ARITHMETIC and every worked PO figure are proved in
`test_us_pay_011_refunds.py` against the module, and the queue plus the two
Admin acts in `test_def2032_refund_doors.py`. What is proved HERE is what only
these three routes and the two new service gates can say:

  1. **A refund can be RAISED**, which is what makes the approval queue mounted
     on 2026-08-28 capable of holding a row at all. Until today only the demo
     seeder called `request_refund`.
  2. **The money can LEAVE, Admin-only, gated twice** — and the credit is tested
     AGAIN at issue, so an approval given on Tuesday cannot pay out a credit a
     Wednesday bounce pulled back.
  3. **A cheque can be recorded as CLEARED by an Admin or an Executive** — *"a
     bank fact, not an approval"* — and clearing posts nothing.
  4. **The account in the URL is a CONSTRAINT, not a label.**

RED PROOF (hard-won law 7). Run in a DETACHED worktree at the pinned tip, never
by moving the shared tree, and quoted here as OBSERVED rather than as predicted:

  * **the three doors.** At the tip `POST /accounts/{id}/refunds`,
    `/refunds/{id}/issue` and `/refunds/{id}/clear` all answer `Resolver404`.
  * **both service gates.** With `@permissions.require_role(...)` deleted from
    `issue_refund` and from `clear_refund`, the two "even without a door" cases
    below fail `Failed: DID NOT RAISE <class 'core.errors.AuthError'>`.
  * **and the shape of the defect, read straight off the tip:** `issue_refund`
    and `clear_refund` are UNGATED while `approve_refund` beside them is GATED —
    which is `DEF-3031` in one line.

⚠ **TWO CASES WENT RED ON THEIR FIRST RUN FOR REASONS THAT WERE THIS FILE'S OWN
FAULT, AND BOTH ARE RECORDED RATHER THAN QUIETLY FIXED.** The ownership case
built its neighbour with `an_overpaid_account`, which calls `pe1_bills`, which
writes PE-1's two invoice NUMBERS as literals — so a second account in the same
tenant collided on the invoice-number unique key. And the offset case asserted
`948.20` where the refusal names the OFFSET (`57.13`), because
`offset_before_refund` returns `min(requested, arrears)`. The second one is a
finding for the screen lane and is written up beside the case.

⚠ Two mutations named in the first draft of this docstring were NOT run and the
claim is removed rather than left standing: making
`_refuse_a_payment_on_another_account` a no-op, and flipping
`cross_account_check` to `False`.
"""

import uuid
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.payments import models, refunds, refunds_api, selectors
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import PE4_CREDIT, a_payment
from tests.test_us_pay_011_refunds import (  # noqa: F401
    APPROVED_AT,
    CLEARED_AT_BANK,
    ISSUED_AT,
    PE9_CHEQUE,
    REQUESTED_AT,
    TC5_OVER_REFUND,
    an_overpaid_account,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

from tests.test_us_ten_helpers import api_call  # noqa: E402 — after the star import


def _post(view, tenant, *, actor, role="system_admin", data=None, **kw):
    return api_call(view, "post", user=actor.user, role=role, tenant=tenant, data=data or {}, **kw)


def _raise_body(payment_id, **overrides):
    """S58's Record-refund form, at PE-9's own figures."""
    values = {
        "payment_id": str(payment_id),
        "amount": str(PE4_CREDIT),
        "method": models.REFUND_METHOD_CHECK,
        # ⚠ **NO `reference` — DEF-PAY-6331, 2026-09-23.** This body carried
        # `"reference": PE9_CHEQUE` until today, which is the defect: a refund
        # is REQUESTED before Finance approves it and before anybody writes a
        # cheque. The door now refuses one BY NAME (asserted below) and the
        # number is collected at `POST /refunds/{id}/issue`.
        "reason": "Overpayment",
        "requested_at": REQUESTED_AT.isoformat(),
        "idempotency_key": str(uuid.uuid4()),
    }
    values.update(overrides)
    return values


def _raised(brazos, marcus, dana, actor=None, role="billing_clerk"):
    """An account with PE-4's 57.13 credit, and a refund raised on it."""
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
    answered = _post(
        refunds_api.account_refunds,
        brazos,
        actor=actor or marcus,
        role=role,
        data=_raise_body(recorded.payment_id),
        account_id=str(account.pk),
    )
    return account, recorded, answered


def _approved(brazos, dana, refund_id):
    return _post(
        refunds_api.refund_approve,
        brazos,
        actor=dana,
        data={"approved_at": APPROVED_AT.isoformat()},
        refund_id=str(refund_id),
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE THREE ADDRESSES
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "path,view_name",
    [
        ("/api/brazos/accounts/A-1/refunds", "account_refunds"),
        ("/api/brazos/refunds/R-1/issue", "refund_issue"),
        ("/api/brazos/refunds/R-1/clear", "refund_clear"),
    ],
)
def test_the_three_missing_refund_doors_are_mounted(path, view_name):
    """CS-6's defect: three of the five refund steps had no route at all.

    `accounts/<id>/refunds` is the one that mattered most — without it nothing
    but the demo seeder could raise a refund, so the approval queue mounted in
    August could never hold a row.
    """
    match = resolve(path)
    assert match.func is getattr(refunds_api, view_name), path


def test_the_new_account_route_does_not_shadow_the_move_out_settlement():
    """`accounts/<id>/refunds` is PLURAL; customers owns `refunds` SINGULAR.

    `apps/customers/api.py` is included FIRST and declares
    `accounts/<id>/refund` — the move-out settlement instruction. Django reaches
    only the first view given one path, so the two must differ, and this asserts
    it rather than reasoning about it.
    """
    from apps.customers import api as customers_api

    singular = resolve("/api/brazos/accounts/A-1/refund")
    assert singular.func.__module__ == customers_api.__name__
    assert resolve("/api/brazos/accounts/A-1/refunds").func is refunds_api.account_refunds


# ══════════════════════════════════════════════════════════════════════════
# 2 · RAISE — the step that makes the approval queue mean anything
# ══════════════════════════════════════════════════════════════════════════


def test_a_clerk_raises_a_refund_and_it_reaches_the_approval_queue(brazos, marcus, dana):
    """J15 steps 1–2. **NO MONEY MOVES** and the row becomes visible.

    CS-6's whole point: `refund_approve` has been reachable since 2026-08-28 and
    the queue it approves from was structurally empty.
    """
    account, _recorded, answered = _raised(brazos, marcus, dana)

    assert answered.status_code == 201, answered.data
    assert answered.data["created"] is True
    assert answered.data["status"] == models.REFUND_REQUESTED
    assert Decimal(answered.data["amount"]) == PE4_CREDIT
    # DEF-PAY-6331: nothing has been written, so there is no cheque to name.
    assert answered.data["reference"] is None
    # BR-PAY-037 — both acts stay separate and neither is a boolean.
    assert answered.data["requested_by"] is not None
    assert answered.data["approved_by"] is None

    listed = api_call(
        refunds_api.refunds_queue,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"f.status": models.REFUND_REQUESTED},
    )
    assert answered.data["id"] in [row["id"] for row in listed.data["results"]]

    with tenant_ctx(brazos):
        assert (
            selectors.account_credit_position(account.pk) == PE4_CREDIT
        ), "a REQUEST moves no money (BR-PAY-014)"


def test_the_raise_answers_with_the_live_credit_rather_than_a_cached_one(brazos, marcus, dana):
    """CS-6's *"watch for"*, honoured by the payload rather than by a warning.

    *"The screen must not cache the credit figure between request and issue — a
    credit real on Tuesday can be gone by Thursday, and the money moves on
    Thursday."* Every step answers with the position computed inside its own
    transaction, so a screen never has to remember a figure it was shown.
    """
    _account, _recorded, answered = _raised(brazos, marcus, dana)
    # 57.13 credit, 57.13 requested → 0.00 left once this refund is paid.
    assert Decimal(answered.data["credit_position_after"]) == Decimal("0")
    assert isinstance(answered.data["problems"], list)


def test_a_double_clicked_record_refund_writes_one_row(brazos, marcus, dana):
    """Hard rule 6, on money going OUT. Same submit token → one refund, 200."""
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
    body = _raise_body(recorded.payment_id)

    first = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=body,
        account_id=str(account.pk),
    )
    second = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=body,
        account_id=str(account.pk),
    )

    assert first.status_code == 201 and first.data["created"] is True
    assert second.status_code == 200, "a button that worked must not answer red"
    assert second.data["created"] is False
    assert second.data["id"] == first.data["id"]
    with tenant_ctx(brazos):
        assert models.Refund.objects.count() == 1


def test_a_submit_with_no_token_raises_nothing(brazos, marcus, dana):
    """`OQ-127`'s argument: a key the server invents dedupes nothing."""
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
    body = _raise_body(recorded.payment_id)
    body.pop("idempotency_key")

    refused = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=body,
        account_id=str(account.pk),
    )

    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "payments.record.idempotency_key_required"
    with tenant_ctx(brazos):
        assert models.Refund.objects.count() == 0


def test_a_payment_on_another_account_cannot_fund_a_refund_here(brazos, marcus, dana):
    """The path segment is ENFORCED, not decorative.

    Without this a clerk on account A's screen could raise a refund funded by
    account B's overpayment: the credit test, the offset and the ledger posting
    would all be account B's while the screen said A. It matters more, not less,
    while `payment_id` is still in the body — which is CS-7's remaining half.

    ⚠ **THE NEIGHBOUR GETS A PAYMENT AND NO BILLS, DELIBERATELY.** `pe1_bills`
    writes PE-1's two invoice NUMBERS as literals, so calling it twice inside
    one tenant collides on the invoice-number unique key and tests nothing —
    which is how the first draft of this case failed. The ownership check runs
    before `request_refund` reads a credit at all, so a payment on a second
    account is the whole of what this needs.
    """
    with tenant_ctx(brazos):
        mine, _recorded = an_overpaid_account(brazos, marcus, account_no="ACC-7001")
        neighbour = an_account(marcus, brazos, account_no="ACC-7002")
        their_payment = a_payment(marcus, neighbour)

    refused = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=_raise_body(their_payment.payment_id),
        account_id=str(mine.pk),
    )

    assert refused.status_code == 422, refused.data
    assert "different account" in refused.data["params"]["detail"]
    with tenant_ctx(brazos):
        assert models.Refund.objects.count() == 0


def test_a_raise_with_no_payment_named_is_a_refund_against_the_account(brazos, marcus, dana):
    """An absent `payment_id` is LAWFUL: the refund is the ACCOUNT's (CR-059 CS-7).

    ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-24 (`DEF-PAY-6346`).** It
    was `test_a_raise_with_no_payment_named_is_refused_by_the_rule_that_owns_it`
    and expected **422**, on the premise that an absent `payment_id` *"falls
    through to `refunds._source_payment`"*. That was true when it was written and
    false from the day CS-7 landed: `payments/0018` (the PO's ruling of
    2026-09-01, `OQ-195` option (a)) made `refunds.payment_id` nullable and put
    `account_id` beside it, so a refund built from several overpayments names
    none of them — the PO's own figure is **$40.00 in June plus $17.13 in July,
    refunded as one $57.13 cheque**. The product answered 201 and the test went
    on demanding 422, red, for three weeks. **The TEST was wrong and the code was
    right**, so the test is what changed.

    The account in the URL is the address, so through this door a refund can
    never name NEITHER link. That refusal still exists and is proved where it
    can be reached — at the service, `test_cs7__neither_link_is_refused`.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
    body = _raise_body(recorded.payment_id)
    body.pop("payment_id")

    answered = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=body,
        account_id=str(account.pk),
    )

    assert answered.status_code == 201, answered.data
    assert Decimal(answered.data["amount"]) == PE4_CREDIT
    with tenant_ctx(brazos):
        raised = models.Refund.objects.get()
    assert str(raised.account_id) == str(account.pk), "the account in the URL is the address"
    assert raised.payment_id is None, "no payment was named, and none is invented"
    assert raised.status == models.REFUND_REQUESTED


def test_an_over_refund_is_refused_with_both_figures(brazos, marcus, dana):
    """US-PAY-011 TC-5 through the door — 80.00 against a 57.13 credit.

    The service's own sentence travels in `params.detail`, so the refusal a
    clerk reads names the credit they actually hold rather than a code.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)

    refused = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=_raise_body(recorded.payment_id, amount=str(TC5_OVER_REFUND)),
        account_id=str(account.pk),
    )

    assert refused.status_code == 422, refused.data
    assert refused.data["br_ref"] == "BR-PAY-014"
    detail = refused.data["params"]["detail"]
    assert "80.00" in detail and "57.13" in detail


def test_an_executive_cannot_raise_a_refund(brazos, marcus, dana):
    """CS-6: raise is *"Admin or Clerk"*. A4 gives the Executive VIEW here."""
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)

    refused = _post(
        refunds_api.account_refunds,
        brazos,
        actor=dana,
        role="executive",
        data=_raise_body(recorded.payment_id),
        account_id=str(account.pk),
    )
    assert refused.status_code == 403, refused.data


# ══════════════════════════════════════════════════════════════════════════
# 3 · ISSUE — the step that moves money, and BR-PAY-1071's Admin gate
# ══════════════════════════════════════════════════════════════════════════


def test_an_admin_issues_a_refund_and_the_credit_goes_to_zero(brazos, marcus, dana):
    """PE-9 over HTTP — 57.13 by cheque #10241 takes the credit to **0.00**.

    Raised by a clerk, approved and issued by an Admin: J15's own sequence, and
    the first time it has been possible without a Python shell.
    """
    account, _recorded, raised = _raised(brazos, marcus, dana)
    approved = _approved(brazos, dana, raised.data["id"])
    assert approved.status_code == 200, approved.data

    issued = _post(
        refunds_api.refund_issue,
        brazos,
        actor=dana,
        data={"issued_at": ISSUED_AT.isoformat(), "reference": PE9_CHEQUE},
        refund_id=raised.data["id"],
    )

    assert issued.status_code == 200, issued.data
    # DEF-PAY-6331 — the number reaches the row at the act that writes it.
    assert issued.data["reference"] == PE9_CHEQUE
    assert issued.data["status"] == models.REFUND_ISSUED
    assert Decimal(issued.data["credit_position_after"]) == Decimal("0"), "PE-9"
    # Hard rule 5 — the ledger posted and stamped its id write-once.
    assert issued.data["journal_entry_id"] is not None
    with tenant_ctx(brazos):
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")


def test_a_billing_clerk_issues_the_refund_an_admin_approved(brazos, marcus, dana):
    """BR-PAY-1071 AS AMENDED — PO 2026-09-03, *"q6 yes Clark can issue refund"*.

    ⚠ **THIS CASE ASSERTED A 403 UNTIL 2026-09-03 AND IT IS INVERTED, NOT
    DELETED.** The rule it tests was widened by the Product Owner two days after
    it was signed, and the reading that makes it coherent is theirs: **the
    APPROVAL is the control.** Dana (Admin) approves; Marcus (Clerk) writes the
    cheque. PE-9's figures do not move — **57.13** by cheque **#10241** takes the
    credit to **0.00**, and the ledger posts DR 2400 / CR 1000 exactly once.
    """
    account, _recorded, raised = _raised(brazos, marcus, dana)
    _approved(brazos, dana, raised.data["id"])

    issued = _post(
        refunds_api.refund_issue,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data={"issued_at": ISSUED_AT.isoformat(), "reference": PE9_CHEQUE},
        refund_id=raised.data["id"],
    )
    assert issued.status_code == 200, issued.data
    assert issued.data["status"] == models.REFUND_ISSUED
    assert Decimal(issued.data["credit_position_after"]) == Decimal("0"), "PE-9"
    assert issued.data["journal_entry_id"] is not None
    with tenant_ctx(brazos):
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")


def test_an_executive_is_still_refused_at_the_issue_door(brazos, marcus, dana):
    """The amendment WIDENED the gate; it did not remove it.

    An Executive was never named by the ruling and is refused at issue, which is
    the case that keeps the gate observable at all: a suite that only proved an
    Admin and a Clerk succeed would pass with the decorator deleted, and the
    decorator's total ABSENCE is the original finding BR-PAY-1071 exists for.
    """
    _account, _recorded, raised = _raised(brazos, marcus, dana)
    _approved(brazos, dana, raised.data["id"])

    refused = _post(
        refunds_api.refund_issue,
        brazos,
        actor=dana,
        role="executive",
        data={"issued_at": ISSUED_AT.isoformat()},
        refund_id=raised.data["id"],
    )
    assert refused.status_code == 403, refused.data
    with tenant_ctx(brazos):
        assert models.Refund.objects.get(pk=raised.data["id"]).status == models.REFUND_APPROVED


def test_an_executive_cannot_issue_a_refund_even_without_a_door(brazos, marcus, dana):
    """BR-SHL-025 — **the SERVICE is the enforcement**, and it still is.

    This is the half CS-6 called *"a real hole"*: `issue_refund` carried no role
    gate of any kind, so a job, a shell or any second endpoint could draw 57.13
    out of `2400 Customer credit` with nobody's approval. G52 could not see it
    either — that gate's universe IS the `@require_role` declarations, so an
    ungated money-out function is invisible to the check written to find
    doorless money-out functions.

    ⚠ **THIS CASE USED TO PASS A BILLING CLERK AND NOW PASSES AN EXECUTIVE
    (PO 2026-09-03).** The actor changed because the RULE changed and the case's
    subject did not: it exists to prove the decorator is on the function rather
    than only on the route, and that needs a role the amended rule refuses. A
    Clerk is now allowed and is covered two cases up.
    """
    _account, _recorded, raised = _raised(brazos, marcus, dana)
    _approved(brazos, dana, raised.data["id"])

    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError) as refusal:
            refunds.issue_refund(
                executive_actor(), refund_id=raised.data["id"], issued_at=ISSUED_AT
            )
        assert refusal.value.code == errors.AUTH_PERMISSION_DENIED
        assert models.Refund.objects.get(pk=raised.data["id"]).status == models.REFUND_APPROVED


def test_the_credit_is_tested_again_at_issue_through_the_door(brazos, marcus, dana):
    """*"A credit real on Tuesday can be gone by Thursday."*

    An over-refund can no longer be raised (the request test refuses it), so the
    Thursday case is made the way it really happens: the refund is raised and
    approved at 57.13, and then a SECOND refund of the same credit is raised and
    approved, so the first one to be issued spends it and the second refuses at
    the issue gate rather than paying the same 57.13 out twice.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)

    first = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=_raise_body(recorded.payment_id),
        account_id=str(account.pk),
    )
    second = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=_raise_body(recorded.payment_id),
        account_id=str(account.pk),
    )
    assert first.status_code == 201 and second.status_code == 201
    _approved(brazos, dana, first.data["id"])
    _approved(brazos, dana, second.data["id"])

    paid = _post(
        refunds_api.refund_issue,
        brazos,
        actor=dana,
        data={"issued_at": ISSUED_AT.isoformat(), "reference": PE9_CHEQUE},
        refund_id=first.data["id"],
    )
    assert paid.status_code == 200, paid.data

    refused = _post(
        refunds_api.refund_issue,
        brazos,
        actor=dana,
        data={"issued_at": ISSUED_AT.isoformat()},
        refund_id=second.data["id"],
    )
    assert refused.status_code == 422, refused.data
    assert "credit" in refused.data["params"]["detail"]
    with tenant_ctx(brazos):
        assert selectors.account_credit_position(account.pk) == Decimal(
            "0.00"
        ), "the same 57.13 was not paid out twice"


def test_an_unapproved_refund_cannot_be_issued(brazos, marcus, dana):
    """BR-PAY-014 — approval is what gates the money, so it must precede it."""
    _account, _recorded, raised = _raised(brazos, marcus, dana)

    refused = _post(
        refunds_api.refund_issue,
        brazos,
        actor=dana,
        data={"issued_at": ISSUED_AT.isoformat()},
        refund_id=raised.data["id"],
    )
    assert refused.status_code == 422, refused.data
    assert "APPROVED" in refused.data["params"]["detail"]


def test_a_missing_issue_moment_is_refused_rather_than_read_off_the_clock(brazos, marcus, dana):
    """BR-TEN-043 / gate G6 — the day a refund left decides its period."""
    _account, _recorded, raised = _raised(brazos, marcus, dana)
    _approved(brazos, dana, raised.data["id"])

    refused = _post(
        refunds_api.refund_issue, brazos, actor=dana, data={}, refund_id=raised.data["id"]
    )
    assert refused.status_code == 422, refused.data
    assert refused.data["code"].startswith("VAL")


# ── DEF-PAY-6331 · the cheque number, at the two doors ─────────────────────
def test_the_raise_door_refuses_a_cheque_number_by_name(brazos, marcus, dana):
    """A request carries none, and saying so beats dropping it in silence.

    ⚠ **REFUSED RATHER THAN IGNORED, AND THE REASON IS THIS DEFECT ONE LAYER
    DOWN.** A key the door quietly dropped would be a cheque number a caller
    believed it had recorded, stored nowhere, discovered by nobody. It also
    prevents a LOCKOUT: `refunds.reference` is write-once from `payments/0041`,
    so a number accepted here would refuse the clerk's real one at issue.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
    refused = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=_raise_body(recorded.payment_id, reference=PE9_CHEQUE),
        account_id=str(account.pk),
    )
    assert refused.status_code == 422, refused.data
    assert "cheque number" in refused.data["params"]["detail"]
    with tenant_ctx(brazos):
        assert models.Refund.objects.count() == 0, "nothing was written"


def test_a_cheque_refund_cannot_be_issued_with_no_cheque_number(brazos, marcus, dana):
    """US-PAY-011 §5 — *"required for check"*, at the act that writes it.

    ⚠ **AND THE CREDIT IS TESTED FIRST**, which is why this case has a real
    credit behind it: a refund whose credit has gone cannot be issued with or
    without a number, and being asked for the chequebook first would send a
    clerk away to fetch a fact that changes nothing.
    """
    _account, _recorded, raised = _raised(brazos, marcus, dana)
    _approved(brazos, dana, raised.data["id"])

    refused = _post(
        refunds_api.refund_issue,
        brazos,
        actor=dana,
        data={"issued_at": ISSUED_AT.isoformat()},
        refund_id=raised.data["id"],
    )
    assert refused.status_code == 422, refused.data
    assert "cheque number" in refused.data["params"]["detail"]
    with tenant_ctx(brazos):
        row = models.Refund.objects.get(pk=raised.data["id"])
        assert row.status == models.REFUND_APPROVED, "nothing moved"
        assert row.journal_entry_id is None, "and nothing posted"


def test_a_bank_transfer_refund_is_issued_with_no_cheque_number(brazos, marcus, dana):
    """`BR-PAY-014` is *"check/ACH v1"* — only the cheque half has a number.

    The mirror-image guard: a requirement widened past the method it belongs to
    would block every ACH refund in the product, and a test that only proved
    the refusal would pass just as well with it widened.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
    raised = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=_raise_body(recorded.payment_id, method=models.REFUND_METHOD_ACH),
        account_id=str(account.pk),
    )
    assert raised.status_code == 201, raised.data
    _approved(brazos, dana, raised.data["id"])

    issued = _post(
        refunds_api.refund_issue,
        brazos,
        actor=dana,
        data={"issued_at": ISSUED_AT.isoformat()},
        refund_id=raised.data["id"],
    )
    assert issued.status_code == 200, issued.data
    assert issued.data["reference"] is None


# ══════════════════════════════════════════════════════════════════════════
# 4 · CLEAR — a bank fact, not an approval (BR-PAY-1071)
# ══════════════════════════════════════════════════════════════════════════


def _issued(brazos, marcus, dana):
    """A refund that has actually gone out — the state the clear door needs.

    ⚠ **THE CHEQUE NUMBER IS PART OF ISSUING FROM 2026-09-23 (`DEF-PAY-6331`)**,
    so a helper that omitted it stopped producing an ISSUED refund at all and
    the three clear cases below failed on a state they never reached. Asserted
    rather than assumed, because a helper that silently returns the wrong state
    makes its callers fail somewhere else entirely.
    """
    _account, _recorded, raised = _raised(brazos, marcus, dana)
    _approved(brazos, dana, raised.data["id"])
    issued = _post(
        refunds_api.refund_issue,
        brazos,
        actor=dana,
        data={"issued_at": ISSUED_AT.isoformat(), "reference": PE9_CHEQUE},
        refund_id=raised.data["id"],
    )
    assert issued.status_code == 200, issued.data
    assert issued.data["status"] == models.REFUND_ISSUED, issued.data
    return raised.data["id"]


def test_an_executive_may_clear_a_refund_and_clearing_posts_nothing(brazos, marcus, dana):
    """CS-6, verbatim: *"Admin or Executive — it is a bank fact, not an
    approval"*.

    A4 gives the finance/reconcile column to the Executive, and every
    deposit-batch and bank-statement route in this module is already
    `AdminOrExecutive`. Gating this to Admin alone would mean the person doing
    the bank reconciliation cannot record that a cheque they can see on the
    statement has cleared.

    **And it posts nothing:** the money left at issue, and a second posting on
    clearing would take it out twice. Asserted by counting journal entries
    either side rather than by reading the service.
    """
    from apps.ledger import models as ledger_models

    refund_id = _issued(brazos, marcus, dana)
    with tenant_ctx(brazos):
        before = ledger_models.JournalEntry.objects.count()

    cleared = _post(
        refunds_api.refund_clear,
        brazos,
        actor=dana,
        role="executive",
        data={"cleared_at": CLEARED_AT_BANK.isoformat()},
        refund_id=refund_id,
    )

    assert cleared.status_code == 200, cleared.data
    assert cleared.data["status"] == models.REFUND_CLEARED
    assert cleared.data["cleared_at"] is not None
    with tenant_ctx(brazos):
        assert (
            ledger_models.JournalEntry.objects.count() == before
        ), "clearing is a date, not a second payment out"


def test_a_billing_clerk_is_refused_at_the_clear_door(brazos, marcus, dana):
    """Narrower than yesterday, when this service accepted anybody at all."""
    refund_id = _issued(brazos, marcus, dana)

    refused = _post(
        refunds_api.refund_clear,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data={"cleared_at": CLEARED_AT_BANK.isoformat()},
        refund_id=refund_id,
    )
    assert refused.status_code == 403, refused.data
    with tenant_ctx(brazos):
        assert models.Refund.objects.get(pk=refund_id).status == models.REFUND_ISSUED


def test_a_billing_clerk_cannot_clear_a_refund_even_without_a_door(brazos, marcus, dana):
    """BR-PAY-1071's service half, for the same reason as `issue_refund`."""
    refund_id = _issued(brazos, marcus, dana)

    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError) as refusal:
            refunds.clear_refund(marcus, refund_id=refund_id, cleared_at=CLEARED_AT_BANK)
        assert refusal.value.code == errors.AUTH_PERMISSION_DENIED
        assert models.Refund.objects.get(pk=refund_id).status == models.REFUND_ISSUED


def test_the_three_doors_are_no_wider_than_their_services(brazos):
    """Every gate read off its own declaration — narrower, never wider.

    Structural rather than exercised per role, so it stays true when a fourth
    role appears and nobody remembers to add a case.
    """
    from core.permissions import (
        BILLING_CLERK,
        EXECUTIVE,
        SYSTEM_ADMIN,
        AdminOrClerk,
        AdminOrExecutive,
        SystemAdminOnly,
    )

    (raise_gate,) = refunds_api.account_refunds.cls.permission_classes
    (issue_gate,) = refunds_api.refund_issue.cls.permission_classes
    (clear_gate,) = refunds_api.refund_clear.cls.permission_classes
    assert raise_gate is AdminOrClerk
    assert raise_gate.allowed_roles == frozenset({SYSTEM_ADMIN, BILLING_CLERK})
    # ⚠ ISSUE WAS `SystemAdminOnly` UNTIL 2026-09-03. BR-PAY-1071 as AMENDED —
    # PO: *"q6 yes Clark can issue refund"*. The APPROVE gate below is the
    # control and has not moved; this one carries out its decision.
    assert issue_gate is AdminOrClerk
    assert issue_gate.allowed_roles == frozenset({SYSTEM_ADMIN, BILLING_CLERK})
    assert clear_gate is AdminOrExecutive
    assert clear_gate.allowed_roles == frozenset({SYSTEM_ADMIN, EXECUTIVE})
    # The three the amendment did NOT loosen, asserted rather than assumed: a
    # ruling that names one channel is read as permission for every other.
    (approve_gate,) = refunds_api.refund_approve.cls.permission_classes
    (void_gate,) = refunds_api.refund_void.cls.permission_classes
    assert approve_gate is SystemAdminOnly
    assert void_gate is SystemAdminOnly
    # BR-PAY-1071's service half — `require_role` sets `__wrapped__`.
    assert hasattr(refunds.issue_refund, "__wrapped__")
    assert hasattr(refunds.clear_refund, "__wrapped__")


# ══════════════════════════════════════════════════════════════════════════
# 5 · OFFSET FIRST — a signed ruling the door cannot switch off
# ══════════════════════════════════════════════════════════════════════════


def test_a_customer_owing_elsewhere_is_offset_first_at_the_door(brazos, marcus, dana, monkeypatch):
    """PO 2026-08-12, `OQ-135` CLOSED — *"offset first"*, and it is not a flag.

    `cross_account_check` is always `True` at this door. Letting the form send
    `false` would let a screen switch a signed ruling off, and the refusal is
    the ruled behaviour: the credit goes against the debt before any refund is
    paid, and applying it is a balance TRANSFER with one reviewed writer that
    CS-8 has not built yet.

    The sibling arrears are faked through customers' OWN published read, by
    name, which is the seam `offset_before_refund` resolves — never by writing a
    second account's rows, which would be this test asserting a fixture.

    ⚠ **THE FIGURE THE CLERK IS TOLD IS THE OFFSET, NOT THE DEBT, AND THAT IS
    WORTH THE SCREEN LANE KNOWING (task 18).** `offset_before_refund` returns
    `min(requested, arrears)`, so against **948.20** of sibling arrears a
    **57.13** refund request is refused with the words *"owes about 57.13 on
    another of their accounts"* — which is how much is being WITHHELD, not how
    much is owed. The first draft of this case asserted `948.20` and went red
    on exactly that. It is not wrong (the sentence says *about*, and the cached
    balance it reads is explicitly not good enough to subtract from), but S58
    must not present it as the sibling's balance.
    """
    from apps.customers import selectors as customers_selectors

    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)

    monkeypatch.setattr(
        customers_selectors,
        "arrears_on_other_accounts",
        lambda account_id: Decimal("948.20"),
    )

    refused = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data=_raise_body(recorded.payment_id),
        account_id=str(account.pk),
    )

    assert refused.status_code == 422, refused.data
    assert refused.data["br_ref"] == "BR-CUS-054"
    detail = refused.data["params"]["detail"]
    assert "57.13" in detail, "the clerk is told what is being withheld"
    assert "2026-08-12" in detail, "and which ruling withholds it"
    with tenant_ctx(brazos):
        assert models.Refund.objects.count() == 0
        assert selectors.account_credit_position(account.pk) == PE4_CREDIT


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 · §8 CS-6 · §11 task 17 · apps/payments/refunds_api.py ·
#         apps/payments/refunds.py · BR-PAY-014 · BR-PAY-037 · BR-PAY-1071 ·
#         OQ-135 (CLOSED) · CS-7 (task 60, the account_id column)
# generated: 2026-09-01 by the CR-059 W3 doors lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 task 18 owns P3) E=deferred(same) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 the refund ARITHMETIC is not restated — it is US-PAY-011's.
#   E2 the offset case fakes customers' published read rather than building a
#      second account with arrears: `offset_before_refund` resolves that name at
#      call time, so the seam IS the contract under test.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
