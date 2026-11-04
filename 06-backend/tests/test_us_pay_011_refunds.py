# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-011 (Refunds — TC-1 the PE-9 cheque, TC-2 the final-bill
#           handoff, TC-3 the clearing, TC-4 the void, TC-5 over-refund and
#           zero credit, TC-6 self-approval and the card refusal, TC-7
#           isolation)
#           Screens: S58 · S33
# Rules:    BR-PAY-002 · BR-PAY-014 · BR-PAY-021 · BR-PAY-024 · BR-PAY-037 ·
#           BR-PAY-041 · BR-CUS-054 · BR-LED-003 · CLAUDE.md rules 1, 2, 4, 5,
#           6, 7
# Golden:   PE-9 (08-payments/07-pre-session-model.md §6: refund 57.13, cheque
#           #10241) · PE-4 (the 57.13 credit it draws on) · J15 (the whole
#           chain, with BR-PAY-037 exercised at step 3)
# ───────────────────────────────────────────────────────
"""Money the utility pays back — and the four things that stop it going wrong.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_pay_011_tc1__pe9_refund_draws_the_credit_to_zero_and_posts`, which is
J15 end to end: overpay $350.00 against $292.87, carry $57.13, request it,
approve it, issue cheque #10241, and watch the credit reach exactly 0.00 with
DR customer-credit / CR cash in the books.

EVERY FIGURE HERE IS COPIED, NEVER COMPUTED. PE-4, PE-9 and J15 are the ratified
worked examples.

EVERY GUARD WAS DRIVEN RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7). The
four proofs, each mutated, RUN and quoted verbatim in the lane report:

  1. the credit test floored at zero, so a NEGATIVE position funds a refund;
  2. the credit checked only at REQUEST, so an approval outlives the credit a
     Wednesday bounce pulled back;
  3. the void DELETING the row instead of writing a reversing posting;
  4. the Admin role guard removed from `approve_refund`.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from core import errors

from apps.payments import models, refunds, reversal, selectors
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import (
    PE4_CREDIT,
    PE4_PAYMENT,
    a_payment,
    journal_legs,
    leg,
    pe1_bills,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

# ── PE-9, verbatim (08-payments/07-pre-session-model.md §6 · EP-PAY-03 §4) ──
# "ACC-1042 credit 57.13 (from PE-4) → refund 57.13, check #10241, Aug 15, 2026."
PE9_CHEQUE = "10241"
#: J15's own timeline: pay 19 Jul, request and approve and issue 24 Jul.
REQUESTED_AT = datetime(2026, 7, 24, 9, 0, tzinfo=UTC)
APPROVED_AT = datetime(2026, 7, 24, 9, 30, tzinfo=UTC)
ISSUED_AT = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
CLEARED_AT_BANK = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)
VOIDED_AT = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)

#: US-PAY-011 TC-5: "Refund attempt for $80.00 against a $57.13 credit".
TC5_OVER_REFUND = Decimal("80.00")


def an_overpaid_account(brazos, marcus, *, account_no=None):
    """PE-4: open 292.87, pay 350.00 → credit 57.13 carried."""
    account = (
        an_account(marcus, brazos, account_no=account_no)
        if account_no is not None
        else an_account(marcus, brazos)
    )
    pe1_bills(brazos, account)
    recorded = a_payment(marcus, account, amount=PE4_PAYMENT)
    assert recorded.credit_carried == PE4_CREDIT
    return account, recorded


def a_request(actor, payment_id, *, amount=PE4_CREDIT, **overrides):
    values = dict(
        payment_id=payment_id,
        amount=amount,
        method=models.REFUND_METHOD_CHECK,
        reference=PE9_CHEQUE,
        reason="Overpayment",
        requested_at=REQUESTED_AT,
    )
    values.update(overrides)
    return refunds.request_refund(actor, **values)


# ── TC-1 · the case this file exists for ────────────────────────────────────
def test_us_pay_011_tc1__pe9_refund_draws_the_credit_to_zero_and_posts(
    brazos, marcus, dana, audit_rows
):
    """US-PAY-011 TC-1 / PE-9 — refund ACC-1042's credit 57.13, cheque #10241.

    *"Request → Alex approves → refund row (Issued), credit position → 0.00;
    posting handoff DR customer-credit 57.13 / CR cash 57.13; audit
    `refund.issued`."*
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
        assert selectors.account_credit_position(account.pk) == PE4_CREDIT

        requested = a_request(marcus, recorded.payment_id)
        assert requested.status == models.REFUND_REQUESTED
        # J15 step 2: "No money moved yet". The credit is still fully there.
        assert selectors.account_credit_position(account.pk) == PE4_CREDIT

        approved = refunds.approve_refund(
            dana, refund_id=requested.refund_id, approved_at=APPROVED_AT
        )
        assert approved.status == models.REFUND_APPROVED
        assert selectors.account_credit_position(account.pk) == PE4_CREDIT

        issued = refunds.issue_refund(dana, refund_id=requested.refund_id, issued_at=ISSUED_AT)

        assert issued.status == models.REFUND_ISSUED
        assert issued.amount == PE4_CREDIT
        assert issued.credit_position_after == Decimal("0.00"), "PE-9: credit → 0.00"
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")

        row = models.Refund.objects.get(pk=requested.refund_id)
        assert row.reference == PE9_CHEQUE
        assert row.method == models.REFUND_METHOD_CHECK
        assert row.journal_entry_id is not None

        # CLAUDE.md rule 5 — the signed contract row, verbatim.
        legs = journal_legs(brazos)
        assert leg(legs, "2400", "debit") == PE4_CREDIT, "DR customer credit"
        assert leg(legs, "1000", "credit") == PE4_CREDIT, "CR cash — the money left the bank"

        # hard rule 7 — three distinct acts, three rows.
        actions = [r["action"] for r in audit_rows]
        assert refunds.AUDIT_REQUESTED in actions
        assert refunds.AUDIT_APPROVED in actions
        assert refunds.AUDIT_ISSUED in actions

        # BR-PAY-024 — the notice IS queued, and the result says so.
        # This line read `no_refund_receipt_queued` until 2026-08-30: the
        # result carried a standing apology on every step, because nothing in
        # this path had ever queued the letter. CR-048 wave B task B11 wired it,
        # so the same assertion now names the outcome instead of the gap.
        assert "refund_notice_queued" in {p["code"] for p in issued.problems}


def test_us_pay_011_br_pay_037__one_user_may_initiate_and_approve_and_both_are_recorded(
    brazos, dana
):
    """J15 step 3 — Dana approves her OWN initiation. Allowed in v1.

    BR-PAY-037, verbatim: *"the SAME user holding the approver role MAY initiate
    AND approve in v1 — both acts recorded distinctly; enforced
    separation-of-duties = v2"*. The audit trail IS the control in v1, so the
    test is that the two acts survive SEPARATELY on the row — a single
    "approved" flag would erase exactly the control the rule leans on.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, dana)
        requested = a_request(dana, recorded.payment_id)
        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)

        row = models.Refund.objects.get(pk=requested.refund_id)
        assert row.requested_by_id == dana.id
        assert row.approved_by_id == dana.id
        assert row.requested_at == REQUESTED_AT
        assert row.approved_at == APPROVED_AT
        assert row.requested_at != row.approved_at, "two acts, two moments, both kept"


def test_us_pay_011_tc6__approval_is_admin_only_and_server_enforced(brazos, marcus):
    """US-PAY-011 TC-6 — "Clerk tries to self-approve".

    *"Approval is Admin-only, server-enforced"*. The guard is on the SERVICE, so
    a job or a shell that never went near an endpoint is refused all the same
    (BR-SHL-025).
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
        requested = a_request(marcus, recorded.payment_id)

        with pytest.raises(errors.AuthError):
            refunds.approve_refund(marcus, refund_id=requested.refund_id, approved_at=APPROVED_AT)

        assert models.Refund.objects.get(pk=requested.refund_id).status == models.REFUND_REQUESTED
        assert selectors.account_credit_position(account.pk) == PE4_CREDIT


def test_us_pay_011_tc6b__a_card_refund_is_refused_with_its_rails_note(brazos, marcus):
    """US-PAY-011 TC-6 — "card method chosen → card disabled with the W7 note".

    BR-PAY-014 puts card refunds behind the payment rails. A card refund
    recorded today would draw the customer's credit down and return them
    nothing, because there is no gateway to send the reversal to.
    """
    with tenant_ctx(brazos):
        _, recorded = an_overpaid_account(brazos, marcus)
        with pytest.raises(PaymentRuleError) as refusal:
            a_request(marcus, recorded.payment_id, method="card")
        assert "W7" in str(refusal.value)
        assert models.Refund.objects.count() == 0


def test_us_pay_011_tc5__a_refund_needs_a_real_credit_and_never_exceeds_it(brazos, marcus, dana):
    """US-PAY-011 TC-5 — over-refund, and a refund against no credit at all.

    *"Rejected — refunds only from a real credit balance (BR-PAY-014); amount ≤
    credit"*, and J15 step 5: the SECOND refund of the same $57.13 is REFUSED
    because no real credit remains.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)

        with pytest.raises(PaymentRuleError) as over:
            a_request(marcus, recorded.payment_id, amount=TC5_OVER_REFUND)
        assert "57.13" in str(over.value)
        assert models.Refund.objects.count() == 0

        # Spend the credit, then try again — J15 step 5.
        requested = a_request(marcus, recorded.payment_id)
        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
        refunds.issue_refund(dana, refund_id=requested.refund_id, issued_at=ISSUED_AT)
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")

        with pytest.raises(PaymentRuleError) as second:
            a_request(marcus, recorded.payment_id)
        assert "no credit balance" in str(second.value)
        # J15 step 5: "Books byte-identical to step 4."
        assert models.Refund.objects.count() == 1


def test_us_pay_011_a_negative_credit_is_a_debt_and_funds_no_refund(brazos, marcus, dana):
    """BR-PAY-041 — after a bounce the position is −57.13, and that is a DEBT.

    The refusal must say the customer OWES the money, not "insufficient credit":
    a credit floored at zero would read as "nothing to refund" when the truth is
    "they owe us $57.13" (PO ruling 2026-08-11: *"Yes, it's a real debt"*).
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
        requested = a_request(marcus, recorded.payment_id)
        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
        refunds.issue_refund(dana, refund_id=requested.refund_id, issued_at=ISSUED_AT)

        reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=datetime(2026, 8, 3, 11, 15, tzinfo=UTC),
            reason=models.REVERSAL_REASON_NSF,
            idempotency_reference="RET-1",
        )
        assert selectors.account_credit_position(account.pk) == Decimal("-57.13")

        with pytest.raises(PaymentRuleError) as refusal:
            a_request(marcus, recorded.payment_id, amount=Decimal("10.00"))
        assert "DEBT" in str(refusal.value)
        assert "OWES" in str(refusal.value)


def test_us_pay_011_the_credit_is_checked_again_at_issue(brazos, marcus, dana):
    """An approval must not outlive the credit it approved.

    A refund approved on Tuesday, and on Wednesday the cheque that created the
    credit bounces. The money moves on Thursday. Checking the credit only at
    REQUEST would pay out of a credit that no longer exists — the utility would
    be $57.13 down with nothing behind it.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
        requested = a_request(marcus, recorded.payment_id)
        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)

        # Wednesday: the cheque bounces and takes the credit with it.
        reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=datetime(2026, 7, 25, 11, 15, tzinfo=UTC),
            reason=models.REVERSAL_REASON_NSF,
            idempotency_reference="RET-2",
        )
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")

        with pytest.raises(PaymentRuleError) as refusal:
            refunds.issue_refund(dana, refund_id=requested.refund_id, issued_at=ISSUED_AT)
        assert "no credit balance" in str(refusal.value)
        assert models.Refund.objects.get(pk=requested.refund_id).status == models.REFUND_APPROVED


def test_us_pay_011_tc3_tc4__clearing_posts_nothing_and_a_void_restores_the_credit(
    brazos, marcus, dana, audit_rows
):
    """US-PAY-011 TC-3 and TC-4 — the cheque clears, then a lost cheque is VOID.

    TC-3: *"Status Issued → Cleared (cleared date recorded)"*. It posts NOTHING
    — the money left the books at ISSUE, and posting again on clearing would
    take it out twice.

    TC-4: *"Void an issued-but-lost check → Status → Void with reversing posting
    (credit restored 57.13); new refund issuable; no row deleted."*
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
        requested = a_request(marcus, recorded.payment_id)
        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
        refunds.issue_refund(dana, refund_id=requested.refund_id, issued_at=ISSUED_AT)

        from apps.ledger import models as ledger_models

        entries_after_issue = ledger_models.JournalEntry.objects.count()

        cleared = refunds.clear_refund(
            dana, refund_id=requested.refund_id, cleared_at=CLEARED_AT_BANK
        )
        assert cleared.status == models.REFUND_CLEARED
        assert (
            ledger_models.JournalEntry.objects.count() == entries_after_issue
        ), "clearing is a date, not a second payment out"
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")

        voided = refunds.void_refund(
            dana,
            refund_id=requested.refund_id,
            voided_at=VOIDED_AT,
            void_reason="cheque lost in the post",
        )

        assert voided.status == models.REFUND_VOID
        row = models.Refund.objects.get(pk=requested.refund_id)
        assert row.void_journal_entry_id is not None
        assert row.void_journal_entry_id != row.journal_entry_id
        # TC-4: the credit is RESTORED — by a mirror, not a recomputation.
        assert selectors.account_credit_position(account.pk) == PE4_CREDIT
        legs = journal_legs(brazos)
        assert leg(legs, "2400", "credit") - leg(legs, "2400", "debit") == PE4_CREDIT

        # "no row deleted" and "new refund issuable".
        assert models.Refund.objects.filter(pk=requested.refund_id).exists()
        again = a_request(marcus, recorded.payment_id)
        assert again.status == models.REFUND_REQUESTED

        assert refunds.AUDIT_VOIDED in [r["action"] for r in audit_rows]


def test_us_pay_011_a_request_or_approval_cannot_be_voided(brazos, marcus, dana):
    """Only a refund that actually went out can be voided.

    A REQUESTED or APPROVED refund has moved no money and posted nothing, so
    there is nothing to reverse — voiding one would write a mirror of an entry
    that does not exist.
    """
    with tenant_ctx(brazos):
        _, recorded = an_overpaid_account(brazos, marcus)
        requested = a_request(marcus, recorded.payment_id)

        with pytest.raises(PaymentRuleError) as refusal:
            refunds.void_refund(
                dana,
                refund_id=requested.refund_id,
                voided_at=VOIDED_AT,
                void_reason="changed our mind",
            )
        assert "moved no money" in str(refusal.value)


def test_us_pay_011_oq135__a_customer_owing_elsewhere_is_offset_first(brazos, marcus):
    """**PO ruling 2026-08-12, verbatim: _"offset first"_ — OQ-135 CLOSED.**

    Money does not leave while this customer owes on another of their accounts.
    The refund is not silently netted down either: the figure available here is
    the CACHED balance (BR-CUS-015), which is good enough to stop a payout and
    not good enough to subtract from one, so the refund refuses and the offset
    is applied as a balance transfer — one reviewed writer, not two.

    "ANOTHER ACCOUNT" MEANS THE CUSTOMER ENTITY (BR-CUS-054), never a shared
    surname or address: offsetting across those would move money between
    strangers.
    """
    from apps.customers import models as customer_models
    from apps.customers import selectors as customer_selectors

    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)

        # No linked customer, no siblings → nothing to offset, refund proceeds.
        assert customer_selectors.arrears_on_other_accounts(account.id) == Decimal("0")
        a_request(marcus, recorded.payment_id, cross_account_check=True)

    with tenant_ctx(brazos):
        # Now the same person holds a SECOND account, 948.20 in arrears. It
        # needs no bills of its own — what matters is that a debt exists on it.
        other_account = an_account(marcus, brazos, account_no="A-90210")
        customer_models.Account.objects.filter(pk=other_account.id).update(
            balance=Decimal("948.20")
        )
        customer = customer_models.Customer.objects.create(
            tenant=brazos, kind="person", display_name="Whitfield, Sara"
        )
        customer_models.CustomerAccount.objects.create(
            tenant=brazos, customer=customer, account_id=other_account.id
        )
        customer_models.CustomerAccount.objects.create(
            tenant=brazos, customer=customer, account_id=account.id
        )

        assert customer_selectors.arrears_on_other_accounts(account.id) == Decimal("948.20")
        with pytest.raises(PaymentRuleError, match="offset"):
            a_request(marcus, recorded.payment_id, cross_account_check=True)

        # The DEFAULT still performs no cross-account check and says so, rather
        # than performing one nobody asked for.
        result = a_request(marcus, recorded.payment_id)
        assert "cross_account_arrears_not_checked" in {p["code"] for p in result.problems}


def test_us_pay_011_a_double_clicked_submit_writes_one_request(brazos, marcus):
    """Hard rule 6, outbound: S58's Record-refund button, double-clicked.

    Without the token a second click writes a second request against the same
    credit, and each would pass its own credit test because neither has issued
    yet — two approvals, two cheques, one $57.13.
    """
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
        token = "s58-form-0001"

        first = a_request(marcus, recorded.payment_id, idempotency_key=token)
        second = a_request(marcus, recorded.payment_id, idempotency_key=token)

        assert first.created is True
        assert second.created is False
        assert second.refund_id == first.refund_id
        assert models.Refund.objects.count() == 1
        assert "duplicate_refund_request_ignored" in {p["code"] for p in second.problems}


def test_us_pay_011_a_cheque_refund_needs_its_cheque_number(brazos, marcus, dana):
    """US-PAY-011 §5: the cheque number is "required for check".

    A payment out that bank rec can never find is how a reconciliation stops
    tying (BR-PAY-021's family, applied outbound).

    ⚠ **THE ACT MOVED ON 2026-09-23 AND THE REQUIREMENT DID NOT (`DEF-PAY-6331`).**
    This case used to assert that `request_refund` refused a cheque with no
    number, and that was the defect: a refund is REQUESTED before Finance
    approves it and long before anybody writes a cheque, so the only ways to
    satisfy it were a blank the product could never fill in later — the column
    was frozen from row creation — or a guess standing in a money record.
    §5's text names no ACT. It is enforced at `issue_refund`, where the clerk
    is holding the cheque, and **the two halves are asserted together** so that
    neither can quietly go: raising without one now SUCCEEDS, and issuing
    without one is refused.
    """
    with tenant_ctx(brazos):
        _, recorded = an_overpaid_account(brazos, marcus)
        requested = a_request(marcus, recorded.payment_id, reference=None)
        assert requested.status == models.REFUND_REQUESTED, "a request cannot know one"

        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
        with pytest.raises(PaymentRuleError) as refusal:
            refunds.issue_refund(dana, refund_id=requested.refund_id, issued_at=ISSUED_AT)
        assert "cheque number" in str(refusal.value)
        # Nothing moved: the money is still in the books and the row is still
        # approved and waiting, which is what makes this recoverable.
        row = models.Refund.objects.get(pk=requested.refund_id)
        assert row.status == models.REFUND_APPROVED
        assert row.journal_entry_id is None


# ── the database's own laws (Postgres only) ─────────────────────────────────
@requires_postgres
def test_us_pay_011_tc4b__a_refund_row_is_frozen_and_can_never_be_deleted(brazos, marcus, dana):
    """hard rule 4 — *"immutable row"* (BR-PAY-014), and *"no row deleted"*.

    The amount, the payment it draws on, the method and the cheque number are
    facts from the instant the row exists; only the status walk moves. DELETE is
    refused in every status, because a refund that left the building is evidence
    even after it is voided.
    """
    with tenant_ctx(brazos):
        _, recorded = an_overpaid_account(brazos, marcus)
        requested = a_request(marcus, recorded.payment_id)
        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
        refunds.issue_refund(dana, refund_id=requested.refund_id, issued_at=ISSUED_AT)

        with pytest.raises(DatabaseError) as amount_refusal, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE refunds SET amount = %s WHERE id = %s",
                    [Decimal("9999.00"), str(requested.refund_id)],
                )
        assert "frozen" in str(amount_refusal.value)

        with pytest.raises(DatabaseError) as delete_refusal, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM refunds WHERE id = %s", [str(requested.refund_id)])
        assert "cannot be removed" in str(delete_refusal.value)


@requires_postgres
def test_us_pay_011_a_voided_refund_is_closed(brazos, marcus, dana):
    """Nothing moves after a void, or the restored credit could be spent twice."""
    with tenant_ctx(brazos):
        _, recorded = an_overpaid_account(brazos, marcus)
        requested = a_request(marcus, recorded.payment_id)
        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
        refunds.issue_refund(dana, refund_id=requested.refund_id, issued_at=ISSUED_AT)
        refunds.void_refund(
            dana,
            refund_id=requested.refund_id,
            voided_at=VOIDED_AT,
            void_reason="cheque lost in the post",
        )

        with pytest.raises(DatabaseError) as refusal, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE refunds SET status = %s WHERE id = %s",
                    ["issued", str(requested.refund_id)],
                )
        assert "VOID and is closed" in str(refusal.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-011@f4d2b18 (the sources this suite asserts, in order: 04-docs/02-decisions/02-database-design-brief.md §2 refunds + Addenda r2/r12 · 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md US-PAY-011 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-014/037/041 · 04-docs/05-modules/08-payments/07-pre-session-model.md §6 PE-9 · 08-qa/01-e2e/journeys/J15-overpay-refund.md)
# generated: 2026-08-11 by Eng-Lead (NSF + refunds lane, EP-PAY-03)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S58 has no server) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every case DRIVEN RED FIRST (hard-won law 7) — the four mutations are quoted verbatim in the lane report
# exceptions: US-PAY-011 TC-2 (the US-BIL-011 final-bill handoff, $11.20) is NOT
#         asserted here: billing publishes no call into this module and this lane
#         does not edit billing. `request_refund` is the function that handoff
#         will call, unchanged · TC-7 (isolation) is served by the module-wide
#         RLS sweep in the `-m isolation` suite, which enumerates every table
#         lacking a policy — `refunds` is enrolled by migration 0006
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
