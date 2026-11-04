# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the two payments-side writes that belong at the
#           moment a draft becomes a bill)   Screens: S30 · S31 step 6 · S32
# Rules:    BR-PAY-010 (a carried credit is drawn down against a newly issued
#           bill) · BR-PAY-041 (a NEGATIVE credit position is a DEBT and is
#           never floored to zero) · BR-PAY-015 (an autopay capture intent is
#           recorded at issue, dated the bill's DUE date; nothing is charged) ·
#           BR-PAY-012 (a deposit-purpose payment satisfies the first bill's
#           deposit line) · BR-BIL-055 (a break never blocks the run) ·
#           CLAUDE.md rule 2 (money) · rule 4 (immutability) · rule 6
#           (idempotency)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**BUILT IS NOT WIRED.** These tests exist because nothing called three
finished functions.

Hard-won law 2, in its exact shape: `apps/payments/credit.py` and
`apps/payments/autopay.py` shipped `apply_credit_at_issue`,
`record_intent_at_issue` and `deposit_payments_for_account`, every one of them
tested on the payments side and passing — and no code path in the product
reached any of them. `deposit_payments_for_account` says so on its own
docstring: *"⚠ NOTHING CALLS IT."* A feature nothing calls does not exist,
however green its unit tests are, and four defects in one day were this.

The payments lane could not close it: the caller is billing's issue path, and
B1 forbids payments writing into it. So the wire is `apps/billing/
payments_seam.py` and these are the tests that prove the CALL HAPPENS —
end-to-end, through `issue.issue_invoice`, never by calling the seam directly.

**THE FIGURES ARE THE PAYMENTS LANE'S OWN, RE-ASSERTED FROM THIS SIDE.** A
**57.13** credit against a **184.20** bill applies **57.13** and leaves
**0.00**; against a **42.10** bill it applies **42.10** and carries **15.03**;
a retried issue applies **0.00**; a **−57.13** position is a DEBT and applies
nothing. PE-12's intent is **292.87** scheduled **22 Aug 2026** in
`awaiting_rails`. Asserting them again here is not duplication: what the
payments tests prove is that the FUNCTION is right, and what these prove is
that issuing a bill actually runs it.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import issue, models, payments_seam
from apps.payments import models as payment_models
from apps.payments import selectors as payment_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_account,
    an_authorised_run,
)
from tests.test_us_pay_007_credit import PE4_CREDIT, _pay

pytestmark = pytest.mark.django_db

#: The payments lane's frozen figures, quoted rather than recomputed.
TC2_NEXT_BILL = Decimal("184.20")
TC3_NEXT_BILL = Decimal("42.10")
TC3_CARRIED = Decimal("15.03")
PE12_AMOUNT = Decimal("292.87")
PE12_DUE = date(2026, 8, 22)
POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=timezone.utc)


BASE_AMOUNT = Decimal("18.50")


def _a_draft_totalling(tenant, account, run, total, *, invoice_no):
    """A draft whose header total is a stated figure AND whose lines foot to it.

    The line COMPOSITION is scaffolding — these tests are about the payments
    write, whose input is the bill's own `total`. What is not scaffolding is
    that the lines add up: `posting_seam` refuses a bill that does not foot
    (BR-BIL-032's tie-out), so a fixture that moved the header without moving
    the lines would break every bill here for a reason that has nothing to do
    with what is under test. Usage takes the remainder; the base stays the
    shared fixture's 18.50.
    """
    draft = a_priced_draft(tenant, account, run, invoice_no=invoice_no, total=total, subtotal=total)
    lines = {line.kind: line for line in draft.lines.all()}
    lines["usage"].amount = total - BASE_AMOUNT
    lines["usage"].save(update_fields=["amount"])
    return draft


def _issue(draft, *, actor=None):
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=actor,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · CREDIT AUTO-APPLY AT ISSUE (BR-PAY-010)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_005_tc28__issuing_a_bill_draws_down_the_carried_credit(brazos, dana):
    """**57.13 credit, 184.20 bill → applies 57.13, credit 0.00.**

    Asserted through `issue_invoice` and then CHECKED AGAINST THE PAYMENTS
    MODULE's own position read, not only against the seam's return value: a
    seam that reported an application it never made would pass the first
    assertion and fail the second.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11042")
        run = an_authorised_run(brazos, dana, key="2026-08|credit-wire")
        _pay(dana, account, PE4_CREDIT)  # 57.13 sitting unapplied
        assert payment_selectors.account_credit_position(account.pk) == PE4_CREDIT

        draft = _a_draft_totalling(brazos, account, run, TC2_NEXT_BILL, invoice_no="BL-2609-018602")
        bill = _issue(draft, actor=dana.user)

        assert bill.credit.applied == PE4_CREDIT, "the CALL happened — law 2"
        assert bill.credit.remaining_credit == Decimal("0.00")
        assert payment_selectors.account_credit_position(account.pk) == Decimal("0.00")
        assert (
            payment_models.Allocation.objects.filter(invoice_id=bill.pk).count() >= 1
        ), "an allocation row names WHICH money met the bill"


def test_us_bil_005_tc29__a_credit_bigger_than_the_bill_carries_the_rest(brazos, dana):
    """**57.13 credit, 42.10 bill → applies 42.10, 15.03 CARRIED.**

    The carry is the assertion that matters: money that does not fit this bill
    is never dropped, it meets the next one.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11043")
        run = an_authorised_run(brazos, dana, key="2026-08|credit-carry")
        _pay(dana, account, PE4_CREDIT)

        draft = _a_draft_totalling(brazos, account, run, TC3_NEXT_BILL, invoice_no="BL-2609-018603")
        bill = _issue(draft, actor=dana.user)

        assert bill.credit.applied == TC3_NEXT_BILL
        assert bill.credit.remaining_credit == TC3_CARRIED
        assert payment_selectors.account_credit_position(account.pk) == TC3_CARRIED


def test_us_bil_005_tc30__a_negative_position_is_a_debt_and_applies_nothing(brazos, dana):
    """**−57.13 applies 0.00** (BR-PAY-041) — and is never floored to zero.

    A negative position is money the customer OWES. Reading it as credit would
    reduce a bill by an amount the utility is chasing, and flooring it to zero
    would hide the debt. Both are asserted: nothing applied, and the position
    still reads −57.13 afterwards.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11044")
        run = an_authorised_run(brazos, dana, key="2026-08|credit-debt")
        # A reversing row with no receipt behind it puts the position below
        # zero — the shape J15 reaches after a refunded overpayment bounces, and
        # the way the payments lane's own BR-PAY-041 case builds it (a NEGATIVE
        # `record_payment` is refused outright: a reversal is a new row).
        payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=-PE4_CREDIT,
            status=payment_models.PAYMENT_POSTED,
            posted_at=POSTED_AT,
        )
        assert payment_selectors.account_credit_position(account.pk) == -PE4_CREDIT

        draft = _a_draft_totalling(brazos, account, run, TC2_NEXT_BILL, invoice_no="BL-2609-018604")
        bill = _issue(draft, actor=dana.user)

        assert bill.credit.applied == Decimal("0.00")
        assert payment_selectors.account_credit_position(account.pk) == -PE4_CREDIT


def test_us_bil_005_tc31__a_bill_with_no_credit_reports_zero_applied(brazos, dana):
    """Zero applied is a real answer, and it is not the same as *nobody asked*.

    `applied == 0.00` here (the seam WAS reached and there was no credit) is
    asserted alongside `applied is None` in `tc33` (the seam could not be
    reached). A caller that rendered the two the same way would tell a customer
    their credit was spent when it was never looked at.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11045")
        run = an_authorised_run(brazos, dana, key="2026-08|credit-none")
        draft = _a_draft_totalling(brazos, account, run, TC2_NEXT_BILL, invoice_no="BL-2609-018605")
        bill = _issue(draft, actor=dana.user)
        assert bill.credit.applied == Decimal("0.00")
        assert bill.credit.problems == ()


# ═══════════════════════════════════════════════════════════════════════════
# 2 · AUTOPAY CAPTURE INTENT AT ISSUE (BR-PAY-015)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_005_tc32__issuing_an_enrolled_accounts_bill_records_one_intent(brazos, dana):
    """PE-12 — **292.87** scheduled **22 Aug 2026**, `awaiting_rails`.

    Three things, and the third is the one a reader must not misread: the
    intent EXISTS after issue (the call happened), it is dated the bill's own
    DUE date rather than today, and **nothing was charged**. There are no
    payment rails in this release; the intent is the record staff work from.

    Idempotent on the invoice (hard rule 6): the second issue of the same bill
    is a no-op that finds the first intent rather than promising the customer
    two drafts.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11046")
        account.autopay = True
        account.save(update_fields=["autopay"])
        run = an_authorised_run(brazos, dana, key="2026-08|autopay-wire")
        draft = _a_draft_totalling(brazos, account, run, PE12_AMOUNT, invoice_no="BL-2608-018410")
        bill = _issue(draft, actor=dana.user)

        assert bill.autopay.created is True, "the CALL happened — law 2"
        assert bill.autopay.amount == PE12_AMOUNT
        # DATED THE BILL'S OWN DUE DATE, whatever that turns out to be — the
        # intent is asserted against `bill.due_date`, which issue DERIVES
        # (BR-BIL-024), rather than against a date typed into this test. PE-12's
        # frozen 22 Aug is the payments lane's fixture and is asserted there; a
        # copy of it here would only prove that this fixture's cycle is dated
        # the way this fixture dates it, and would go red for the wrong reason
        # the day a cycle fixture moved.
        assert bill.autopay.scheduled_on == bill.due_date
        assert bill.due_date is not None
        assert bill.autopay.status == payment_models.INTENT_AWAITING_RAILS
        assert payment_models.AutopayCaptureIntent.objects.filter(invoice_id=bill.pk).count() == 1
        # The absence travels on the result rather than in a docstring nobody
        # reads: an intent is not a payment.
        assert "no_payment_rails_in_this_release" in {
            problem["code"] for problem in bill.autopay.problems
        }

        # Hard rule 6 — a resumed release must not promise two captures.
        second = payments_seam.record_autopay_intent(bill, actor=dana.user)
        assert second.created is False and second.intent_id == bill.autopay.intent_id
        assert payment_models.AutopayCaptureIntent.objects.filter(invoice_id=bill.pk).count() == 1


def test_us_bil_005_tc33__a_non_enrolled_account_issues_normally_with_no_intent(brazos, dana):
    """A run of 400 bills must not fail because 300 accounts are not on autopay.

    The account is not enrolled, the bill issues, and the reason is REPORTED
    rather than raised — which is BR-BIL-055 applied to a payments seam.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11047")
        run = an_authorised_run(brazos, dana, key="2026-08|autopay-off")
        draft = _a_draft_totalling(brazos, account, run, PE12_AMOUNT, invoice_no="BL-2608-018411")
        bill = _issue(draft, actor=dana.user)

        assert bill.status == models.INVOICE_ISSUED
        assert bill.autopay.created is False and bill.autopay.intent_id is None
        assert payment_models.AutopayCaptureIntent.objects.filter(invoice_id=bill.pk).count() == 0
        assert "account_not_enrolled" in {problem["code"] for problem in bill.autopay.problems}


# ═══════════════════════════════════════════════════════════════════════════
# 3 · AN UNWIRED SEAM REPORTS. IT NEVER ANSWERS ZERO.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_005_tc34__an_unpublished_payments_seam_reports_and_still_issues(
    brazos, dana, monkeypatch
):
    """A deployment whose payments module is not migrated still bills.

    And it says so: `applied is None` — *nobody asked* — which is the fact a
    screen must be able to tell apart from *this customer had no credit*. The
    difference is asserted directly against `tc31`'s `Decimal("0.00")`.
    """
    monkeypatch.setattr(payments_seam, "_resolve", lambda *args, **kwargs: None)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11048")
        run = an_authorised_run(brazos, dana, key="2026-08|payments-absent")
        draft = _a_draft_totalling(brazos, account, run, TC2_NEXT_BILL, invoice_no="BL-2609-018606")
        bill = _issue(draft, actor=dana.user)

        assert bill.status == models.INVOICE_ISSUED, "an unwired seam never blocks a bill"
        assert bill.credit.applied is None, "None is *nobody asked*, never 0.00"
        assert "payments_apply_credit_at_issue_not_published" in {
            problem["code"] for problem in bill.credit.problems
        }
        assert bill.autopay.intent_id is None
        assert "payments_record_intent_at_issue_not_published" in {
            problem["code"] for problem in bill.autopay.problems
        }


def test_us_bil_005_tc35__the_deposit_read_answers_none_rather_than_zero_when_unasked(
    brazos, dana, monkeypatch
):
    """BR-PAY-012 — and the difference here is $150.00 of somebody's money.

    `deposit_paid_for_account` returns the paid figure when payments is
    reachable and **None** when it is not. A caller that read None as zero would
    charge a deposit the customer has already paid, on a bill that is immutable
    the moment it issues.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11049")
        assert payments_seam.deposit_paid_for_account(account.pk) == Decimal("0")

        _pay(dana, account, Decimal("150.00"), purpose=payment_models.PURPOSE_DEPOSIT)
        assert payments_seam.deposit_paid_for_account(account.pk) == Decimal("150.00")

        monkeypatch.setattr(payments_seam, "_resolve", lambda *args, **kwargs: None)
        assert payments_seam.deposit_paid_for_account(account.pk) is None, (
            "None is 'we could not ask'; zero is 'they have paid nothing', and charging a "
            "deposit already paid takes $150.00 twice from somebody moving house"
        )


def test_us_bil_005_tc36__the_run_counts_credit_and_intents_once_with_their_bills(brazos, dana):
    """`issue_run` reports the payments outcomes the way it reports every other.

    DISTINCT problem codes with a bill count, never one dict per bill: a run of
    480 bills whose payments module is unmigrated must say so once.
    """
    with tenant_ctx(brazos):
        first = an_account(dana, brazos, account_no="A-11050")
        second = an_account(dana, brazos, account_no="A-11051")
        first.autopay = True
        first.save(update_fields=["autopay"])
        run = an_authorised_run(brazos, dana, key="2026-08|payments-run")
        _pay(dana, first, PE4_CREDIT)
        _a_draft_totalling(brazos, first, run, TC2_NEXT_BILL, invoice_no="BL-2609-018610")
        _a_draft_totalling(brazos, second, run, TC2_NEXT_BILL, invoice_no="BL-2609-018611")

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )
        assert len(result.issued) == 2
        assert result.credit_applied == PE4_CREDIT
        assert result.credit_bills == 1, "only one of the two had a credit"
        assert result.autopay_intents == 1, "only one of the two is enrolled"
        counts = {entry["code"]: entry["bills"] for entry in result.payment_problems}
        assert counts.get("account_not_enrolled") == 1
        assert counts.get("no_payment_rails_in_this_release") == 2


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         08-payments/02-business-rules.md)
# generated: 2026-08-15 by Eng-Lead (payments-wiring lane — hard-won law 2)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_bil_005_payments_wiring.py ·
#         three mutations proved RED (each call deleted from `issue_invoice`,
#         and `deposit_paid_for_account` returning 0 instead of None)
# exceptions: (1) the AUTOPAY intent carries `invoices.total`, which is the bill
#         BEFORE any credit drawdown — the payments contract asks for the bill's
#         total and PE-12's frozen 292.87 is that figure. Whether an enrolled
#         customer with a carried credit should be scheduled for the NET is a
#         question nobody has put to the PO; REPORTED on `ISSUE_UNAVAILABLE`
#         rather than answered by this lane.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
