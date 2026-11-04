# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-009 (NSF — TC-1 the PE-7 bounce, TC-2 the ORIGINAL due date,
#           TC-3 the counts and the privilege flag, TC-4 the notice, TC-5 the
#           uncleared payment, TC-6 the frozen rows, TC-7 isolation) ·
#           US-PAY-010 (Reverse — the reason set, always-reversing execution)
#           Screens: S33 · S35 · S40
# Rules:    BR-PAY-002 · BR-PAY-011 · BR-PAY-013 · BR-PAY-021 · BR-PAY-028 ·
#           BR-PAY-031 · BR-PAY-039 · BR-PAY-041 · BR-BIL-007 · BR-BIL-071 ·
#           BR-LED-003 · CLAUDE.md rules 1, 2, 4, 5, 6, 7
# Golden:   PE-7 (08-payments/07-pre-session-model.md §5) · PE-4 / PE-9 (the
#           $350.00 → $57.13 → refund chain J15 freezes) · J12 (the NSF life)
# ───────────────────────────────────────────────────────
"""A cheque comes back: every rule that stands around it, and the four proofs.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_pay_009_tc1__pe7_bounce_writes_a_reversing_row_and_reopens_the_bills`.
Until 2026-08-11 nothing in the product could reverse a payment.

EVERY FIGURE HERE IS COPIED, NEVER COMPUTED. PE-7 and the J15/PE-4/PE-9 chain
are the ratified worked examples and the numbers are transcribed with the line
they came from quoted beside them. A test that recomputed its own expectation
would agree with a broken implementation.

⚠ **THE PARAGRAPH BELOW IS HISTORY (`DEF-PAY-10698`, 2026-10-30).** The fee is
now charged: an `nsf` bounce asks billing for the NSF code the account's PLAN
lists, and `tests/test_def_pay_10698_nsf_fee.py` asserts the PO's worked figure
($76.40 → $106.40). This file's world has no unit, so TC-1 asserts the named
absence `nsf_fee_no_plan` instead. What it said:

**PE-7's 322.87 IS DELIBERATELY NOT ASSERTED, AND THAT IS THE HONEST OUTCOME.**
The frozen figure is *"reversing payment row −292.87 … NSF charge code +$30
(tenant-config) auto-added → balance 322.87"*. The $30 line is BILLING's write
(BR-BIL-007) priced from `rating.charges`, rating publishes no charge-code read,
and `apps/billing/penalty.penalty_charge_line` refuses on exactly that gap
today. So the −292.87 half is asserted exactly and the fee half is asserted as a
REPORTED GAP (`nsf_fee_not_added`) rather than faked with a hardcoded 30.

WHAT RUNS WHERE, because it changes what a green run is worth:

  * The SERVICE-LAYER laws — the reversing row, the reversed allocations, the
    untouched due date, the negative credit, both idempotency guards — run
    everywhere, including on the SQLite developer database which has no triggers
    and no RLS.
  * The DATABASE laws — the immutability triggers, the write-once ledger stamp,
    the two unique indexes and RLS — carry `requires_postgres` and SKIP on
    SQLite rather than passing vacuously.

EVERY GUARD IN THIS FILE WAS DRIVEN RED BEFORE IT WAS TRUSTED GREEN (hard-won
law 7). The proofs, each mutated, RUN, and quoted verbatim in the lane report:

  1. the bounce EDITING the original payment instead of writing a reversing row;
  2. the credit floored at zero instead of reaching −57.13;
  3. the ledger mirrored but the allocations left applied — and the reverse;
  4. the reinstated bill given the RETURN date as a new due date;
  5. each idempotency guard disabled ALONE. Those two observe the PATH and not
     the outcome, which is DEF-058's whole lesson: the second guard covers the
     same OUTCOME as the first, so a test that only checked "the debt did not
     double" would stay green with either one switched off.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from apps.payments import models, reversal, selectors
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import (
    NEW_BILL_TOTAL,
    OLD_BILL_TOTAL,
    PE1_CHECK,
    PE4_CREDIT,
    PE4_PAYMENT,
    a_payment,
    an_issued_bill,
    journal_legs,
    leg,
    pe1_bills,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

# ── PE-7, verbatim (08-payments/07-pre-session-model.md §5) ────────────────
# "cleared check 292.87 bounces → reversing payment row −292.87 (append-only,
#  BR-PAY-002), allocations reversed, AR reinstated at the ORIGINAL due date
#  (late-fee clock never reset — PA-2), NSF charge code +$30 (tenant-config)
#  auto-added → balance 322.87."
PE7_REVERSAL = Decimal("-292.87")

#: J12's own dates: the July bill is due **Jul 22**, the cheque is recorded
#: Jul 18 and the bank returns it **Aug 3**. The gap is the point — TC-2 is
#: about the due date NOT moving to the return date.
ORIGINAL_DUE = date(2026, 7, 22)
RETURNED_ON = datetime(2026, 8, 3, 11, 15, tzinfo=UTC)

#: The bank's OWN charge, which is the utility's (12-payments-decision-batch:
#: "Who pays the bank's own charge — **You do.**"). A sample figure like the
#: $30: what is asserted is the ACCOUNT it lands in (signed 6800), never a rate.
BANK_FEE = Decimal("12.00")


def a_bounce(actor, payment_id, **overrides):
    """The PE-7 bounce, through the real service — no ORM shortcuts."""
    values = dict(
        payment_id=payment_id,
        returned_on=RETURNED_ON,
        reason=models.REVERSAL_REASON_NSF,
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return reversal.reverse_payment(actor, **values)


def dated_bills(tenant, account):
    """PE-1's two bills, with J12's REAL due dates so TC-2 can assert them."""
    old = an_issued_bill(
        tenant,
        account,
        number="BL-2607-018311",
        total=OLD_BILL_TOTAL,
        issued_on=date(2026, 7, 1),
        due_date=ORIGINAL_DUE,
    )
    new = an_issued_bill(
        tenant,
        account,
        number="BL-2608-018410",
        total=NEW_BILL_TOTAL,
        issued_on=date(2026, 8, 1),
        due_date=date(2026, 8, 22),
    )
    return old, new


# ── TC-1 · the case this file exists for ────────────────────────────────────
def test_us_pay_009_tc1__pe7_bounce_writes_a_reversing_row_and_reopens_the_bills(
    brazos, marcus, dana, audit_rows
):
    """US-PAY-009 TC-1 / PE-7 — the $292.87 cheque bounces.

    Six things become true and all six are asserted, because any one of them
    missing is a broken bounce that every other test would still pass: the NEW
    reversing row at −292.87, the ORIGINAL row untouched, the reversing
    allocations, the re-opened bills, the ledger mirror, and the audit row.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        old, new = pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)
        original = models.Payment.objects.get(pk=recorded.payment_id)

        result = a_bounce(dana, original.pk)

        # ── hard rule 4 — a NEW ROW, and the original is untouched ──────────
        assert result.created is True
        assert result.amount == PE7_REVERSAL, "PE-7: reversing payment row −292.87"
        reversing = models.Payment.objects.get(pk=result.reversal_id)
        assert reversing.pk != original.pk, "a reversal is a NEW row, never an edit"
        assert reversing.reverses_payment_id == original.pk
        assert reversing.status == models.PAYMENT_REVERSED
        assert reversing.reversal_reason == models.REVERSAL_REASON_NSF
        assert reversing.payment_no, "BR-TEN-035: the reversing row is numbered too"

        original.refresh_from_db()
        assert original.amount == PE1_CHECK, "the bounced row still says what was taken"
        # CR-186-BRC10 — recorded `posted` (it is cleared only at reconciliation).
        assert original.status == models.PAYMENT_POSTED, (
            "the original's status NEVER changes — it was posted, and then it came back. "
            "'Has this been reversed?' is answered by the existence of the reversing row"
        )
        assert selectors.reversal_of(original.pk).pk == reversing.pk

        # ── the allocations are reversed, and the bills re-open exactly ─────
        assert result.allocations_reversed == PE1_CHECK
        reversing_rows = models.Allocation.objects.filter(payment=reversing).order_by("amount")
        assert [row.amount for row in reversing_rows] == [-NEW_BILL_TOTAL, -OLD_BILL_TOTAL]
        # The ORIGINAL's allocation rows are append-only and still there.
        assert models.Allocation.objects.filter(payment=original).count() == 2
        # Net position per bill: settled, then re-opened by exactly what was taken.
        from apps.payments import billing_seam

        assert billing_seam.allocated_so_far(old.pk) == Decimal("0")
        assert billing_seam.allocated_so_far(new.pk) == Decimal("0")
        position = billing_seam.open_invoices_for_account(account.pk)
        assert {i.number: i.balance for i in position.invoices} == {
            "BL-2607-018311": OLD_BILL_TOTAL,
            "BL-2608-018410": NEW_BILL_TOTAL,
        }

        # ── hard rule 7 ────────────────────────────────────────────────────
        nsf_rows = [row for row in audit_rows if row["action"] == reversal.AUDIT_NSF]
        assert len(nsf_rows) == 1
        assert Decimal(nsf_rows[0]["after"]["allocations_reversed"]) == PE1_CHECK

        # ── CLAUDE.md rule 5 — the LEDGER'S OWN MIRROR ─────────────────────
        assert result.journal_entry_id is not None
        assert result.posting_key == f"payment|{original.pk}|nsf_reversed"
        legs = journal_legs(brazos)
        # The receipt debited 1010 (BR-PAY-039), so the mirror CREDITS 1010 —
        # bank cash (1000) is never touched, because the money was never banked.
        assert leg(legs, "1010", "debit") == PE1_CHECK
        assert leg(legs, "1010", "credit") == PE1_CHECK
        assert leg(legs, "1000", "credit") == Decimal("0"), (
            "a bounce must not credit real bank cash the utility still holds — "
            "the receipt step is what is unwound (PO ruling 2026-08-11, OQ-143)"
        )
        assert leg(legs, "1200", "debit") == PE1_CHECK, "AR is reinstated"

        # ── PE-7's FEE HALF (DEF-PAY-10698, PO 2026-10-30) ─────────────────
        # This asserted `nsf_fee_not_added` — a standing gap — until the fee
        # was built. The fee is now the plan's NSF code, found account → unit
        # → plan; THIS world's account stands on no unit, so the bounce names
        # that absence instead of charging a guessed $30.00. The charged figure
        # — cheque 4102 $76.40 → $106.40 — is asserted end to end in
        # `tests/test_def_pay_10698_nsf_fee.py`.
        codes = {problem["code"] for problem in result.problems}
        assert "nsf_fee_not_added" not in codes
        assert result.nsf_fee_status == "nsf_fee_no_plan"
        assert result.nsf_fee_amount is None
        assert "nsf_fee_no_plan" in codes
        assert "collection_ladder_paused" in codes
        # DEF-069 / DEF-070 CLOSED 2026-08-15. These two codes were on EVERY
        # result and their absence is the fix: `nsf_count` is written through
        # customers' published seam and the privilege flag has a column.
        assert "nsf_count_not_incremented" not in codes
        assert "privilege_flag_not_available" not in codes
        assert result.nsf_count == 1
        assert result.cash_only_no_autopay is False  # N=2, so not yet


def test_us_pay_009_tc2__the_reinstated_bill_keeps_its_original_due_date(brazos, marcus, dana):
    """US-PAY-009 TC-2 — "Original due date Aug 22; NSF lands Sep 2".

    BR-PAY-013: *"AR reinstated at the ORIGINAL due date (late-fee clock never
    resets)"*. J12 step 2 states it as a consequence: *"the late-fee clock runs
    from Jul 22 as if the payment never happened"*.

    **The bill is due 22 Jul and the bank returns the cheque on 3 Aug.** If a
    bounce reinstated AR at the RETURN date the bill would fall due 3 Aug, the
    customer would gain twelve free days and the grace period would restart —
    which is precisely what the rule forbids.

    The late-fee ARITHMETIC is not restated here. `apps/billing/late_fee`
    already implements BR-BIL-071 and reads `invoices.due_date`; this asserts
    the input it consumes is unmoved, and then hands the reinstated position to
    billing's own function to prove the consequence end to end.
    """
    from apps.billing import late_fee

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        old, new = dated_bills(brazos, account)
        recorded = a_payment(marcus, account)

        a_bounce(dana, recorded.payment_id)

        old.refresh_from_db()
        new.refresh_from_db()
        assert old.due_date == ORIGINAL_DUE, (
            "the bill re-opens at its OWN due date — nothing in payments has ever written "
            "invoices.due_date, and that absence IS how the clock never resets"
        )
        assert new.due_date == date(2026, 8, 22)
        assert old.due_date != RETURNED_ON.date()

        # BILLING's own rule, consuming the reinstated position: with the
        # payment reversed, no money arrived, so the whole $45.00 is overdue as
        # of the ORIGINAL 22 Jul — not as of the 3 Aug return.
        overdue = late_fee.overdue_portion(
            amount_billed=OLD_BILL_TOTAL,
            due_date=old.due_date,
            payments=(),  # the payment was reversed: no money arrived
            assessed_on=date(2026, 8, 10),
        )
        assert overdue == OLD_BILL_TOTAL


def test_us_pay_009_negative_credit__a_refunded_bounce_drives_it_below_zero(brazos, marcus, dana):
    """BR-PAY-041 / PO ruling 2026-08-11 — **"Yes, it's a real debt"**.

    The PO's own worked chain, end to end through the real services:

        pay $350.00 against $292.87 open   ->  credit   57.13   (PE-4)
        refund cheque $57.13 issued        ->  credit    0.00   (PE-9)
        the $350.00 cheque bounces         ->  credit  −57.13

    **−57.13 is the assertion.** A credit floored at zero would report $0.00,
    the utility would never chase the money, and the books — where 2400 carries
    a real debit balance for this account — would disagree by exactly that.

    ⚠ **`DEF-3421` — THIS CASE WAS RED ON THE BRANCH FROM 2026-09-01 TO
    2026-09-03, AND THE FIX WAS THE RULE RATHER THAN THE TEST.** `issue_refund`
    was gated Admin-only that day (`BR-PAY-1071`), and the `refunds.issue_refund`
    call below still passes **Marcus, a Billing Clerk** — so it failed with
    `core.errors.AuthError: AUTH-002` at `core/permissions.py:197`, three calls
    before anything this case is about. The lane that found it FILED it rather
    than "fixing" it by changing the actor, on the ground that the question
    belonged to the rule's owner. It did: the Product Owner ruled *"q6 yes Clark
    can issue refund"* on 2026-09-03, `BR-PAY-1071` is AMENDED, and **the actor
    below is deliberately unchanged** — the TEST was right and the GATE was
    wrong. The approval above it is still Dana's, because approving is still
    Admin-only and that half of the rule did not move.
    """
    from apps.payments import refunds

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account, amount=PE4_PAYMENT)
        assert recorded.credit_carried == PE4_CREDIT  # PE-4, verbatim
        assert selectors.account_credit_position(account.pk) == PE4_CREDIT

        requested = refunds.request_refund(
            marcus,
            payment_id=recorded.payment_id,
            amount=PE4_CREDIT,
            method=models.REFUND_METHOD_CHECK,
            reference="10241",  # PE-9's cheque number
            requested_at=datetime(2026, 7, 24, 9, 0, tzinfo=UTC),
        )
        refunds.approve_refund(
            dana,  # BR-PAY-014: approval is Admin-only and server-enforced
            refund_id=requested.refund_id,
            approved_at=datetime(2026, 7, 24, 9, 30, tzinfo=UTC),
        )
        issued = refunds.issue_refund(
            marcus,
            refund_id=requested.refund_id,
            issued_at=datetime(2026, 7, 24, 10, 0, tzinfo=UTC),
        )
        assert issued.credit_position_after == Decimal("0.00")  # PE-9: credit → 0

        result = a_bounce(dana, recorded.payment_id)

        assert result.credit_reversed == PE4_CREDIT
        assert result.credit_position_after == -PE4_CREDIT, (
            "PO ruling 2026-08-11: the credit goes to −57.13 and that is a REAL DEBT the "
            "utility pursues — never floored at zero"
        )
        assert selectors.account_credit_position(account.pk) == Decimal("-57.13")
        assert selectors.account_credit_position(account.pk) < Decimal("0")

        # The books say the same thing from their own side: 2400 ends in DEBIT.
        legs = journal_legs(brazos)
        assert leg(legs, "2400", "debit") - leg(legs, "2400", "credit") == PE4_CREDIT


def test_us_pay_009_tc5__a_payment_that_never_cleared_cannot_bounce(brazos, marcus, dana):
    """US-PAY-009 TC-5 — "NSF attempted on a payment that never cleared".

    *"Rejected — NSF is a clearing failure (BR-PAY-021); processing payments
    cancel instead"*. Money that never arrived has nothing to go back.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        # ⚠ CR-186-BRC10 (PO 2026-10-21): a new payment is POSTED and CAN
        # bounce ("a bounce after posting uses the existing reversal"). Only a
        # row written before the change can still be `processing`, so the
        # refusal is proved on one built the way such a row was — by INSERT.
        legacy = models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=PE1_CHECK,
            currency=account.currency,
            status=models.PAYMENT_PROCESSING,
            posted_at=datetime(2026, 8, 8, 10, 30, tzinfo=UTC),
        )

        with pytest.raises(PaymentRuleError) as refusal:
            a_bounce(dana, legacy.pk)
        assert "PROCESSING" in str(refusal.value)
        assert models.Payment.objects.filter(reverses_payment__isnull=False).count() == 0


def test_us_pay_009_a_reversal_cannot_itself_be_reversed(brazos, marcus, dana):
    """Reversing a reversal would re-apply money the bank has taken back.

    A customer who pays again after a bounce makes a NEW payment (BR-PAY-036 —
    money is always accepted), which is a different row and a different event.
    """
    from apps.payments.exceptions import PaymentRuleError

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)
        result = a_bounce(dana, recorded.payment_id)

        with pytest.raises(PaymentRuleError) as refusal:
            a_bounce(dana, result.reversal_id)
        assert "reversing row" in str(refusal.value)


def test_us_pay_009_a_staff_reversal_still_answers_to_br_pay_011(brazos, marcus, dana):
    """The other three reasons have a path now — and it is BR-PAY-011's path.

    ⚠ **THIS CASE ASSERTED A FLAT REFUSAL UNTIL 2026-09-03 AND IT IS INVERTED,
    NOT DELETED.** It exists because gate G10 caught a door this file had opened
    past a CONFIRMED rule: the first version accepted all four S35 reasons, which
    made `reverse_payment` a general Reverse — and BR-PAY-011 governs a general
    reverse with WINDOWS (ACH 60 days, card 120 days), an Admin/Executive
    APPROVAL path for paid or cross-period payments, and a CONSEQUENCE MESSAGE
    before confirm. **None of the three was built, so the refusal was right.**

    `CR-059` CS-31 (task 35) built all three — `apps/payments/reversal_rules.py`
    — so what this case now asserts is the thing that replaced the refusal: a
    staff reversal of a payment sitting against an ISSUED bill is refused
    **without an approval**, by name, and every one of the three reasons behaves
    the same way. The door is open; the rule stands in it.

    A bounce needs none of those clauses: BR-PAY-011 itself puts cheques on an
    UNLIMITED window and names NSF as the reason, because a returned item is the
    bank's decision and not a staff correction.
    """
    from apps.payments.exceptions import PaymentRuleError

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        for reason in (
            models.REVERSAL_REASON_DATA_ENTRY_ERROR,
            models.REVERSAL_REASON_CUSTOMER_DISPUTE,
            models.REVERSAL_REASON_BANK_CHARGEBACK,
        ):
            recorded = a_payment(marcus, account, amount=Decimal("10.00"))
            with pytest.raises(PaymentRuleError) as refusal:
                a_bounce(dana, recorded.payment_id, reason=reason)
            assert "needs an approval" in str(refusal.value)
            assert "applied_to_an_issued_bill" in str(refusal.value)
            assert "BR-PAY-011" == refusal.value.br_ref

        # Nothing was written by any of the three: the refusal is BEFORE the
        # transaction, which is what makes it safe to retry with an approval.
        assert models.Payment.objects.filter(reverses_payment__isnull=False).count() == 0


def test_us_pay_009_the_bank_fee_is_the_utilitys_and_lands_in_6800(brazos, marcus, dana):
    """ "Who pays the bank's own charge — **You do.**" (already decided).

    Two things are asserted and a third deliberately is not: the fee lands in
    the SIGNED **6800 Bank fees** account, it does NOT touch the customer's
    balance, and the AMOUNT is an input — no rate is hardcoded anywhere, because
    the bank's charge is the bank's.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)

        result = a_bounce(dana, recorded.payment_id, bank_fee=BANK_FEE)

        assert result.bank_fee == BANK_FEE
        assert result.bank_fee_entry_id is not None
        legs = journal_legs(brazos)
        assert leg(legs, "6800", "debit") == BANK_FEE
        assert (
            leg(legs, "1000", "credit") == BANK_FEE
        ), "the bank has ALREADY taken this out of the real account — it is not undeposited"
        # It is the utility's expense, so it never lands on the customer's bills
        # and never moves their credit position.
        assert result.credit_position_after == Decimal("0")


def test_us_pay_009_the_two_rulings_of_20260812_are_built(brazos, marcus, dana):
    """**OQ-133 and OQ-134, both ruled 2026-08-12.** This test asserted two
    REFUSALS until then, and each refusal was correct while the question stood.

    **OQ-133** — *"Restart from the beginning"*. Resuming by AGE would make a
    certified 48-hour disconnection notice the customer's first contact after a
    cheque they believed had cleared.

    **OQ-134** — the lock HOLDS. A returned cheque does not rewrite a batch
    total the bank has already agreed; the bounce is new rows, and the fee is
    the utility's manual charge.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)

        # OQ-133: resuming no longer raises — the ladder restarts at rung 1.
        #
        # ⚠ THIS COMMENT WAS FALSE FOR THREE WEEKS, AND THIS TEST IS WHY IT
        # SURVIVED (CR-059 CS-5, DEF-2581, 2026-09-01). `resume_collections` was
        # declared, documented in eleven lines and READ NOWHERE, so the ladder
        # restarted for nobody — and the only test passing the flag asserted
        # `created is True` and nothing else. The ruling had a test, the reset
        # machinery had a test, and the JOIN between them had none, so every
        # suite stayed green over a customer being chased from whatever rung
        # their age selected. The sentence above is TRUE NOW; what makes it true
        # is asserted in tests/test_cr059_cs5_ladder_restart.py, which also pins
        # the two docstrings that made this claim. Left here rather than deleted
        # because a reader arriving at this line needs to know it is checked
        # somewhere, and where.
        bounced = a_bounce(dana, recorded.payment_id, resume_collections=True)
        assert bounced.created is True

        # OQ-134: a payment naming a batch that does NOT EXIST is still refused,
        # and that is a different question from a locked one — a broken
        # reference is not a lock, and proceeding blind was never the ruling.
        another = a_payment(marcus, account, idempotency_reference=uuid.uuid4())
        models.Payment.objects.filter(pk=another.payment_id).update(deposit_batch_id=uuid.uuid4())
        with pytest.raises(PaymentRuleError, match="does not exist"):
            a_bounce(dana, another.payment_id)


# ── idempotency: the two guards, each observed ALONE (hard rule 6 · DEF-058) ─
def test_us_pay_009_idem1__the_same_bank_advice_twice_writes_one_reversal(brazos, marcus, dana):
    """Guard 1 — the same ADVICE arrives twice (a retried webhook).

    Keyed on the EXISTING `webhook_key` mechanism
    (`idempotency.inbound_payment_key`); nothing new is invented.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)
        advice = "RET-99012"

        first = a_bounce(
            dana,
            recorded.payment_id,
            idempotency_source="webhook",
            idempotency_reference=advice,
        )
        second = a_bounce(
            dana,
            recorded.payment_id,
            idempotency_source="webhook",
            idempotency_reference=advice,
        )

        assert first.created is True
        assert second.created is False
        assert second.reversal_id == first.reversal_id
        assert models.Payment.objects.filter(reverses_payment__isnull=False).count() == 1
        assert models.Allocation.objects.filter(amount__lt=0).count() == 2
        assert "duplicate_bounce_ignored" in {p["code"] for p in second.problems}


def test_us_pay_009_idem2__the_same_payment_under_two_advice_ids_writes_one_reversal(
    brazos, marcus, dana
):
    """Guard 2 — the SAME payment bounced under two DIFFERENT advice ids.

    **This is the guard that would not exist if guard 1 and the ledger's replay
    were trusted to cover "the debt did not double" between them, and it is
    DEF-058's exact shape.** Two clerks, or a webhook and a manual S33 mark: the
    keys differ, so guard 1 cannot see it. `uq_payments_reverses` is what says a
    payment is reversed ONCE.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)

        first = a_bounce(
            dana, recorded.payment_id, idempotency_source="webhook", idempotency_reference="A-1"
        )
        second = a_bounce(
            dana, recorded.payment_id, idempotency_source="import", idempotency_reference="B-2"
        )

        assert first.created is True
        assert second.created is False, "different key, same payment — still ONE reversal"
        assert second.reversal_id == first.reversal_id
        assert models.Payment.objects.filter(reverses_payment__isnull=False).count() == 1
        # The debt did not double: exactly two reversing allocation rows exist.
        assert models.Allocation.objects.filter(amount__lt=0).count() == 2


def test_us_pay_009_idem1b__one_advice_reference_reused_for_a_second_payment_is_refused(
    brazos, marcus, dana
):
    """Guard 1's OWN fact — the one guard 2 structurally cannot see.

    **This test exists because the RED proof found the first version of guard 1
    standing in for nothing** (DEF-058's lesson, live): switching it off left
    both other idempotency tests green, because guard 2 catches the same-payment
    case on the same code path.

    The fact only guard 1 can see: a returns feed that reuses one reference for
    TWO different cheques. Without the check the insert reaches
    `uq_payments_webhook_key`, the IntegrityError handler finds the OTHER
    payment's reversal and reports "already reversed" — a REAL bounce silently
    swallowed, and that customer's bills left settled with money the bank has
    taken back. That is a lost bounce, not a redundant guard.
    """
    from apps.payments.exceptions import PaymentRuleError

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        first_payment = a_payment(marcus, account)
        second_payment = a_payment(marcus, account, amount=Decimal("10.00"))
        advice = "RET-99012"

        a_bounce(
            dana,
            first_payment.payment_id,
            idempotency_source="webhook",
            idempotency_reference=advice,
        )

        with pytest.raises(PaymentRuleError) as collision:
            a_bounce(
                dana,
                second_payment.payment_id,
                idempotency_source="webhook",
                idempotency_reference=advice,
            )
        assert "DIFFERENT payment" in str(collision.value)

        # The second cheque is NOT recorded as bounced — the clerk fixes the
        # feed. One reversal exists, and it belongs to the first payment.
        assert models.Payment.objects.filter(reverses_payment__isnull=False).count() == 1
        assert selectors.reversal_of(second_payment.payment_id) is None


def test_us_pay_009_idem_observes_the_path_not_the_outcome(brazos, marcus, dana, monkeypatch):
    """DEF-058's lesson, applied before it bites: watch the PATH.

    DEF-058 was a hard-rule-6 guard committed in the DISABLED state where
    nothing went red, *"because the database UNIQUE index covers the same
    OUTCOME"*. Its fix was a test that observes the path rather than the result.

    So this asserts that a replay **never reaches the write path at all**: the
    numbering kernel is booby-trapped, and a replay that got as far as
    allocating a PMT- number would explode even though the final row count would
    still be 1.
    """
    from core import numbering

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)
        a_bounce(
            dana, recorded.payment_id, idempotency_source="webhook", idempotency_reference="A-1"
        )

        def explode(*args, **kwargs):
            raise RuntimeError(
                "a replay reached numbering.next_number — a pre-insert idempotency lookup is "
                "gone (DEF-058)"
            )

        monkeypatch.setattr(numbering, "next_number", explode)

        # Guard 1's path: same advice.
        replay = a_bounce(
            dana, recorded.payment_id, idempotency_source="webhook", idempotency_reference="A-1"
        )
        assert replay.created is False
        # Guard 2's path: different advice, same payment.
        other = a_bounce(
            dana, recorded.payment_id, idempotency_source="import", idempotency_reference="B-2"
        )
        assert other.created is False


# ── the database's own laws (Postgres only) ─────────────────────────────────
@requires_postgres
def test_us_pay_009_tc6__the_bounced_row_and_its_allocations_are_frozen(brazos, marcus, dana):
    """US-PAY-009 TC-6 — "UPDATE attempt on the original or reversing row".

    *"Blocked — append-only triggers (BR-PAY-002, B2 §3)"*. Asserted on BOTH
    rows: the original because it is history, the reversing row because it is
    history the moment it commits.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)
        result = a_bounce(dana, recorded.payment_id)

        with pytest.raises(DatabaseError) as refusal, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE payments SET amount = %s WHERE id = %s",
                    [Decimal("1.00"), str(recorded.payment_id)],
                )
        assert "append-only" in str(refusal.value)

        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE payments SET amount = %s WHERE id = %s",
                    [Decimal("-1.00"), str(result.reversal_id)],
                )

        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM allocations WHERE payment_id = %s", [result.reversal_id]
                )


@requires_postgres
def test_us_pay_009_the_ledger_stamp_is_write_once(brazos, marcus):
    """Migration 0006's one door: NULL → set, once, and never re-pointed.

    The stamp is what lets a bounce name the entry `posting.reverse_entry` must
    mirror. If it could be re-pointed, a payment could be made to unwind a
    DIFFERENT payment's entry — which is the one thing this column exists to
    make impossible.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)
        payment = models.Payment.objects.get(pk=recorded.payment_id)
        assert payment.journal_entry_id is not None

        with pytest.raises(DatabaseError) as refusal, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE payments SET journal_entry_id = %s WHERE id = %s",
                    [str(uuid.uuid4()), str(payment.pk)],
                )
        assert "WRITE-ONCE" in str(refusal.value)


@requires_postgres
def test_us_pay_009_a_payment_is_reversed_once_at_the_database_too(brazos, marcus, dana):
    """`uq_payments_reverses` — guard 2's DATABASE half.

    The service refuses the second bounce; this proves the index would refuse it
    even if the service did not, which is what makes a lost race and a replay
    the same fact.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account)
        first = a_bounce(dana, recorded.payment_id)
        reversing = models.Payment.objects.get(pk=first.reversal_id)

        with pytest.raises(IntegrityError), transaction.atomic():
            models.Payment.objects.create(
                tenant_id=reversing.tenant_id,
                account_id=reversing.account_id,
                payment_no="PY-BYPASS-0001",
                type=models.PAYMENT_TYPE_PAYMENT,
                amount=Decimal("-1.00"),
                currency=reversing.currency,
                status=models.PAYMENT_REVERSED,
                posted_at=RETURNED_ON,
                cleared_at=RETURNED_ON,
                reverses_payment_id=recorded.payment_id,
                reversal_reason=models.REVERSAL_REASON_NSF,
            )


# ══════════════════════════════════════════════════════════════════════════
# DEF-069 + DEF-070 — J12's NSF MACHINE, which could not run at all
# ══════════════════════════════════════════════════════════════════════════
#
# BR-PAY-013 is CONFIRMED and says a bounce increments `accounts.nsf_count` and
# that at the tenant's N (default 2, `nsf_privilege_n`) the account goes
# cash-only and off autopay. NEITHER HAPPENED. `accounts` is customers' table
# and payments may not write another module's (B1 / DB-16); customers published
# no seam (DEF-069) and the privilege flag had NO COLUMN ANYWHERE (DEF-070). So
# every bounce left the count at 0, the threshold could never be reached, and
# **J12 step 4 was unreachable** — a journey step nothing could satisfy.
#
# The tests are written from the JOURNEY's side, not the column's. Asserting
# `nsf_count == 1` on a direct call would have passed the day `record_nsf` was
# written and proved nothing about a bounce; what matters is that a BOUNCE moves
# it, so that is what is driven.


def test_def_069_j12_step2__the_first_bounce_counts_and_trips_nothing(brazos, marcus, dana):
    """J12 step 2/3, verbatim: *"`nsf_count`=1 … no flag yet (N=2)"*."""
    from apps.customers import models as customers_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-11042")
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account, amount=PE1_CHECK)
        result = a_bounce(dana, recorded.payment_id)

        assert result.nsf_count == 1
        assert result.cash_only_no_autopay is False
        assert result.privilege_flag_tripped is False
        row = customers_models.Account.objects.get(pk=account.pk)
        assert row.nsf_count == 1
        assert row.cash_only_no_autopay is False


def test_def_070_j12_step4__the_second_bounce_trips_the_cash_only_flag(brazos, marcus, dana):
    """J12 step 4 — *"`nsf_count`=2 → cash-only/no-autopay privilege flag trips
    (tenant default N=2)"*. This step could not pass before 2026-08-15: there
    was no column for the flag to land in."""
    from apps.customers import models as customers_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-11043")
        pe1_bills(brazos, account)

        first = a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)
        assert first.nsf_count == 1 and first.privilege_flag_tripped is False

        second = a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)
        assert second.nsf_count == 2
        assert second.cash_only_no_autopay is True
        assert second.privilege_flag_tripped is True, (
            "the TRIP is its own fact — J12 step 4 wants an audit row for the "
            "moment, and a caller cannot tell a trip from an already-flagged "
            "account off the boolean alone"
        )
        row = customers_models.Account.objects.get(pk=account.pk)
        assert row.cash_only_no_autopay is True


def test_def_070_tc3__the_threshold_is_the_tenants_and_not_a_constant(brazos, marcus, dana):
    """US-PAY-009 TC-3, verbatim: *"tenant N changed to 3 → third NSF required
    (config, not constant)"*."""
    from apps.customers import models as customers_models
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        row = tenancy_models.TenantSettings.objects.filter(tenant_id=brazos.id).first()
        document = dict(row.collections or {})
        document["nsf_privilege_n"] = 3
        row.collections = document
        row.save(update_fields=["collections"])

        account = an_account(marcus, brazos, account_no="A-11044")
        pe1_bills(brazos, account)

        first = a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)
        second = a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)
        assert first.nsf_count == 1 and second.nsf_count == 2
        assert second.cash_only_no_autopay is False, (
            "at N=3 the SECOND bounce must not flag — a hardcoded 2 anywhere in "
            "this chain makes this assertion fail and that is the point of it"
        )

        third = a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)
        assert third.nsf_count == 3
        assert third.cash_only_no_autopay is True
        assert customers_models.Account.objects.get(pk=account.pk).cash_only_no_autopay is True


def test_def_070_j12_step6__nothing_auto_clears_the_flag(brazos, marcus, dana):
    """J12 step 6 — *"the cash-only flag REMAINS; no rule auto-clears it"*.

    The recovery payment of step 5 is taken (BR-PAY-036: money is ALWAYS
    accepted, in any state) and the account stays cash-only.
    """
    from apps.customers import models as customers_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-11045")
        pe1_bills(brazos, account)
        a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)
        a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)
        assert customers_models.Account.objects.get(pk=account.pk).cash_only_no_autopay is True

        # Step 5: the customer pays cash and it clears. Nothing about that
        # acceptance changes account state.
        a_payment(marcus, account, amount=PE1_CHECK)
        assert customers_models.Account.objects.get(pk=account.pk).cash_only_no_autopay is True


def test_def_070__the_flag_stops_autopay_and_leaves_the_election_intact(brazos, marcus, dana):
    """The *no-autopay* half of the flag's own name, made real (law 2).

    `autopay` is the customer's ELECTION and stays exactly as they set it; the
    flag is the ENFORCEMENT, and `autopay.is_enrolled` is where the two meet.
    Flipping the election instead would leave nothing to restore on a lift.
    """
    from apps.customers import models as customers_models
    from apps.payments import autopay

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-11046")
        customers_models.Account.objects.filter(pk=account.pk).update(autopay=True)
        pe1_bills(brazos, account)
        assert autopay.is_enrolled(account.pk) is True

        a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)
        a_bounce(dana, a_payment(marcus, account, amount=PE1_CHECK).payment_id)

        assert autopay.is_enrolled(account.pk) is False
        assert customers_models.Account.objects.get(pk=account.pk).autopay is True, (
            "the customer's own enrolment is untouched — a lifted sanction must "
            "not require them to re-enrol for a punishment that has ended"
        )


def test_def_069__a_staff_reversal_is_not_a_bounce_and_counts_nothing(brazos, marcus, dana):
    """BR-PAY-013 is the BOUNCE rule. A mis-keyed payment reversed by staff is
    not a customer's cheque coming back and must not push them towards
    cash-only.

    TODAY that is guaranteed twice, and the outer guarantee is the weaker one:
    `_supported_reason` refuses every non-NSF reason outright because
    US-PAY-010's windows, approval path and consequence messaging are unbuilt.
    When they land that refusal goes away — and `_write_reversal`'s
    `reason == nsf` condition is what still keeps the count off a staff
    reversal. This asserts the state that exists and names the one that will.
    """
    from apps.customers import models as customers_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-11047")
        pe1_bills(brazos, account)
        recorded = a_payment(marcus, account, amount=PE1_CHECK)
        with pytest.raises(PaymentRuleError) as refusal:
            a_bounce(
                dana,
                recorded.payment_id,
                reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR,
            )
        assert refusal.value.br_ref == "BR-PAY-011"
        assert customers_models.Account.objects.get(pk=account.pk).nsf_count == 0


def test_def_069__the_count_never_crosses_a_tenant_boundary(brazos, marcus, dana, lonestar):
    """Hard rule 1, asserted on the NEW seam rather than around it.

    A neighbouring utility calling `record_nsf` with this tenant's account id
    must not increment anything: the account is not theirs, so it does not
    exist as far as they are concerned (HR-1 — 404, never 403), and the count
    they cannot see stays where it was.
    """
    from apps.customers import models as customers_models
    from apps.customers import services as customers_services
    from core import errors as core_errors

    with tenant_ctx(brazos):
        mine = an_account(marcus, brazos, account_no="A-11048")
        pe1_bills(brazos, mine)
        a_bounce(dana, a_payment(marcus, mine, amount=PE1_CHECK).payment_id)
        assert customers_models.Account.objects.get(pk=mine.pk).nsf_count == 1

    with tenant_ctx(lonestar):
        with pytest.raises(core_errors.NotFoundError):
            customers_services.record_nsf(mine.pk)

    with tenant_ctx(brazos):
        assert customers_models.Account.objects.get(pk=mine.pk).nsf_count == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-009@f4d2b18 (the sources this suite asserts, in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md US-PAY-009 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-013/041 · 04-docs/05-modules/08-payments/07-pre-session-model.md §5 PE-7 · 08-qa/01-e2e/journeys/J12-nsf-life.md + J15-overpay-refund.md · 12-governance/02-decision-log.md 2026-08-11 OQ-132/OQ-143 closures)
# generated: 2026-08-11 by Eng-Lead (NSF + refunds lane, EP-PAY-03)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every case DRIVEN RED FIRST (hard-won law 7) — the five mutations are quoted verbatim in the lane report
# exceptions: (superseded 2026-10-30, DEF-PAY-10698 — the fee is charged
#         through the plan; see tests/test_def_pay_10698_nsf_fee.py)
#         PE-7's **322.87** IS NOT ASSERTED and its absence is the finding:
#         the $30 NSF fee is BILLING's line write (BR-BIL-007) priced from
#         `rating.charges`, rating publishes no charge-code read, and hardcoding
#         30 here would assert a number this product cannot produce. The
#         −292.87 half is asserted exactly and the fee half is asserted as a
#         REPORTED GAP (`nsf_fee_not_added`)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
