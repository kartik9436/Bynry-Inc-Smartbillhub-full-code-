# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-25 · task 62 — reject a request, and correct an approved
#           write-off.
# Story:    US-PAY-012   Screens: S36 (the queue) · S34 (the original age)
# Rules:    BR-PAY-1120 (the four-state set; both new acts Admin-only, gated in
#           the SERVICE) · BR-PAY-020 · BR-PAY-002 (append-only) · BR-PAY-037 ·
#           BR-CUS-043 (one live plan per account) · CLAUDE.md hard rule 4 ·
#           rule 5 · rule 6 · rule 7
# ───────────────────────────────────────────────────────
"""CS-25 on US-PAY-012's own figure: **A-10802 Novak $948.20, 91 days late**.

════════════════════════════════════════════════════════════════════════════
PROVED RED FIRST (hard-won law 7), IN A DETACHED WORKTREE AT THE PINNED TIP
════════════════════════════════════════════════════════════════════════════
Four sabotages were RUN in a detached worktree at the pinned tip `7d95b1d2`, and
what is quoted below is what pytest actually printed:

  * **the doors.** At the tip this file cannot be collected at all —
    `E   ImportError: cannot import name 'writeoffs_api' from 'apps.payments'`.
  * **the include.** With the modules present but the `include` removed from
    `config/urls.py`, `test_the_two_new_doors_are_mounted` fails
    `E   django.urls.exceptions.Resolver404: {'tried': […],
    'path': 'write-offs/abc/reject'}`.
  * **the service gate.** With `@permissions.require_role(SYSTEM_ADMIN)` deleted
    from `reject_write_off`,
    `test_a_clerk_is_refused_by_the_reject_service_itself` fails
    `E   Failed: DID NOT RAISE AuthError` — a Billing Clerk closing an
    approver's decision, silently.
  * **hard rule 4.** With `reverse_write_off` rewritten to move the ORIGINAL's
    status to `reversed` in place instead of inserting a new row, both
    `test_a_reversal_is_a_new_row` and
    `test_the_original_row_is_not_touched_by_a_reversal` fail —
    `E   django.db.utils.IntegrityError: CHECK constraint failed:
    ck_write_offs_reversal_pair`. **That is a better answer than the assertion
    they were written for**: the DATABASE refuses the in-place correction before
    the test can even read the row back, and it does so on SQLite, where the
    trigger half of the freeze does not exist.

⚠ **A FIFTH SABOTAGE WAS NAMED IN THE FIRST DRAFT OF THIS DOCSTRING AND NOT RUN,
SO THE CLAIM IS WITHDRAWN RATHER THAN LEFT STANDING** (hard-won law 1, and the
`CR-059` CS-5 lane's own wording for the same situation): re-dating the account's
open bill on reversal, to show `test_the_debt_keeps_its_original_age_throughout`
failing `assert 0 == 91`. That case is asserted GREEN below and has not been
*shown* to fail on its own.

════════════════════════════════════════════════════════════════════════════
⚠ WHAT SQLITE CANNOT PROVE HERE, SAID PLAINLY (CLAUDE.md law 14)
════════════════════════════════════════════════════════════════════════════
`config/settings/test.py` hardcodes in-memory SQLite and ignores `DATABASE_URL`,
and SQLite has **neither triggers nor RLS**. So migration 0011's five refusals —
the DELETE ban, the three terminal-status bans, the write-once entry link and the
deny-by-default frozen-column check — **are not exercised by this file**. Every
one of them is ALSO refused in `writeoffs.py` and it is the SERVICE half these
cases assert. The database half needs a PostgreSQL run, and seeding currently
collapses on PostgreSQL (`DEF-2395`, another lane's), so it is stated as owed
rather than claimed as done.

The same applies to `dunning.reopen_plan_on_write_off_reversal`'s SAVEPOINT: the
case below drives the *"a newer live plan exists"* branch through the SELECT that
precedes it, which is the branch a person will meet. The RACE — two plans agreed
in parallel, the unique index refusing the second, and the whole transaction
aborting on PostgreSQL where SQLite simply carries on — is what the savepoint is
for and is not provable here.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.urls import resolve

from core import errors

from apps.payments import dunning, outstandings, plans, writeoffs, writeoffs_api
from apps.payments.collections_models import (
    PLAN_ACTIVE,
    PLAN_CLOSED,
    PLAN_PROPOSED,
    WRITE_OFF_APPROVED,
    WRITE_OFF_REASON_UNCOLLECTIBLE,
    WRITE_OFF_REJECTED,
    WRITE_OFF_REQUESTED,
    WRITE_OFF_REVERSED,
    PaymentPlan,
    WriteOff,
)
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: US-PAY-012 §4, verbatim: "A-10802 Novak, P.: balance $948.20, 91 days late".
NOVAK = Decimal("948.20")
NOTE = "120+ days, 3 notices, phone contact failed ×4"
#: The bill is due 16 May and every figure below is read as of 15 August — 91
#: days, exactly the story's own number, and the 90+ bucket.
DUE_ON = date(2026, 5, 16)
AS_OF = date(2026, 8, 15)
NINETY_ONE = 91
REQUESTED_ON = AS_OF
POSTED_AT = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
#: Four months later. The point of the gap is that a debt reinstated in December
#: must NOT come back looking one day old.
REVERSED_ON = date(2026, 12, 15)
REVERSED_AT = datetime(2026, 12, 15, 9, 0, tzinfo=UTC)
REJECT_REASON = "raised against the wrong account — this is A-10820, not A-10802"
REVERSE_REASON = "raised against the wrong account; the debt is still collectable"


def _a_debtor(brazos, dana, *, account_no="A-10802", total=NOVAK):
    account = an_account(dana, brazos, account_no=account_no)
    an_issued_bill(
        brazos,
        account,
        number=f"BL-2605-{account_no[-5:]}",
        total=total,
        issued_on=DUE_ON,
        due_date=DUE_ON,
    )
    return account


def _a_request(dana, account, *, amount=NOVAK):
    return writeoffs.request_write_off(
        dana,
        account_id=account.pk,
        amount=amount,
        reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
        note=NOTE,
        requested_on=REQUESTED_ON,
    )


def _an_approved_write_off(dana, account, *, amount=NOVAK):
    requested = _a_request(dana, account, amount=amount)
    return writeoffs.approve_write_off(
        actor=dana,
        write_off_id=requested.write_off_id,
        approved_on=REQUESTED_ON,
        posted_at=POSTED_AT,
    )


def _row_snapshot(write_off_id):
    """Every column of one write-off, as a plain dict — hard rule 4's evidence.

    Compared before and after a reversal. `updated_at` is `auto_now`, so it is
    included deliberately: if the original were saved at all, even with no field
    changing, that column would move and this comparison would catch it.
    """
    row = WriteOff.objects.get(pk=write_off_id)
    return {field.attname: getattr(row, field.attname) for field in WriteOff._meta.concrete_fields}


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ADDRESS — CS-25's two acts had no route and no service
# ══════════════════════════════════════════════════════════════════════════


def test_the_two_new_doors_are_mounted():
    """`/write-offs/{id}/reject` and `/write-offs/{id}/reverse` resolve.

    Through `config/urls.py`, not through the module's own `urlpatterns`: a
    module whose routes are never included is DEF-100's mechanism, and every
    door lane in this CR asserts the include rather than the list.
    """
    assert resolve("/api/brazos/write-offs/abc/reject").func is writeoffs_api.write_off_reject
    assert resolve("/api/brazos/write-offs/abc/reverse").func is writeoffs_api.write_off_reverse


def test_the_approve_door_still_resolves_beside_them():
    """The new three-segment patterns shadow nothing that already worked."""
    from apps.payments import api as payments_api

    assert resolve("/api/brazos/write-offs/abc/approve").func is payments_api.approve_write_off
    assert resolve("/api/brazos/write-offs").func is payments_api.write_offs


# ══════════════════════════════════════════════════════════════════════════
# 2 · REJECT — a decision recorded, and NOT a deletion (CS-25's own words)
# ══════════════════════════════════════════════════════════════════════════


def test_a_rejection_moves_no_money_and_deletes_nothing(brazos, dana):
    """CS-25: *"rejection moves no money and is not a deletion."*

    The row stands at 948.20, `journal_entry_id` is still null, and the account
    still owes the whole 948.20 — because nothing was ever posted to unwind.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana)
        requested = _a_request(dana, account)
        result = writeoffs.reject_write_off(
            dana,
            write_off_id=requested.write_off_id,
            rejected_on=REQUESTED_ON,
            reason=REJECT_REASON,
        )
        assert result.status == WRITE_OFF_REJECTED
        assert result.posted_to_ledger is False
        row = WriteOff.objects.get(pk=requested.write_off_id)
        assert row.status == WRITE_OFF_REJECTED
        assert row.journal_entry_id is None
        assert row.gl_account_id is None
        assert row.approved_by_id is None and row.approved_on is None
        # NOT a deletion — the row is still there, and it says who and why.
        assert WriteOff.objects.filter(pk=requested.write_off_id).count() == 1
        assert row.rejected_by_id is not None
        assert row.rejected_on == REQUESTED_ON
        assert row.rejection_reason == REJECT_REASON
        # The debt is untouched. It never left the books to begin with.
        view = outstandings.outstandings(as_of=AS_OF)
        assert view.total_owed == NOVAK


def test_a_rejection_writes_an_audit_row(brazos, dana, audit_rows):
    """Hard rule 7 — every money ACTION writes `audit_log`, and *"no money
    moved"* is the fact this one carries.

    ⚠ **THE ROWS ARE READ FROM THE CAPTURE SINK, NOT FROM `audit_log`, AND THE
    FIRST DRAFT OF THIS CASE GOT THAT WRONG.** `tests/test_us_met_helpers`
    carries an AUTOUSE fixture that swaps `core.audit`'s sink for a list — so in
    any file importing those fixtures (this one does, for `brazos` and `dana`)
    nothing reaches the table and a query against it answers
    `AuditLog.DoesNotExist`, which reads exactly like *"the service never wrote
    one"*. It is the same class of wrong answer as a check that cannot fail:
    the query was right about the table and the table was not where to look.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10803")
        requested = _a_request(dana, account)
        before = len(audit_rows)
        writeoffs.reject_write_off(
            dana,
            write_off_id=requested.write_off_id,
            rejected_on=REQUESTED_ON,
            reason=REJECT_REASON,
        )
        written = [row for row in audit_rows[before:] if row["action"] == writeoffs.AUDIT_REJECTED]
        assert len(written) == 1, audit_rows[before:]
        after = written[0]["after"] or {}
        assert after["rejection_reason"] == REJECT_REASON
        assert after["journal_entry_id"] is None
        assert after["status"] == WRITE_OFF_REJECTED
        # WHO — hard rule 7's evidence half, from the session and nowhere else.
        assert written[0]["actor_user_id"] is not None
        # And the rejection is the ONLY thing it wrote: no approval, no posting.
        assert writeoffs.AUDIT_APPROVED not in {row["action"] for row in audit_rows[before:]}


def test_a_rejection_needs_a_reason(brazos, dana):
    """*"A request may be rejected WITH A REASON by an approver."*"""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10804")
        requested = _a_request(dana, account)
        with pytest.raises(PaymentRuleError) as refused:
            writeoffs.reject_write_off(
                dana,
                write_off_id=requested.write_off_id,
                rejected_on=REQUESTED_ON,
                reason="   ",
            )
        assert "reason" in str(refused.value)
        assert WriteOff.objects.get(pk=requested.write_off_id).status == WRITE_OFF_REQUESTED


def test_rejecting_twice_keeps_the_first_refusal(brazos, dana):
    """A double click must not overwrite the reason the first approver gave."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10805")
        requested = _a_request(dana, account)
        writeoffs.reject_write_off(
            dana,
            write_off_id=requested.write_off_id,
            rejected_on=REQUESTED_ON,
            reason=REJECT_REASON,
        )
        again = writeoffs.reject_write_off(
            dana,
            write_off_id=requested.write_off_id,
            rejected_on=date(2026, 9, 1),
            reason="a different reason entirely",
        )
        assert [problem["code"] for problem in again.problems] == ["already_rejected"]
        row = WriteOff.objects.get(pk=requested.write_off_id)
        assert row.rejection_reason == REJECT_REASON
        assert row.rejected_on == REQUESTED_ON


def test_an_approved_write_off_cannot_be_rejected(brazos, dana):
    """It has already posted. The correction is a reversing ROW, not a status."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10806")
        approved = _an_approved_write_off(dana, account)
        with pytest.raises(PaymentRuleError) as refused:
            writeoffs.reject_write_off(
                dana,
                write_off_id=approved.write_off_id,
                rejected_on=REQUESTED_ON,
                reason=REJECT_REASON,
            )
        assert "approved" in str(refused.value)
        assert WriteOff.objects.get(pk=approved.write_off_id).status == WRITE_OFF_APPROVED


def test_a_rejected_request_cannot_later_be_approved(brazos, dana):
    """BR-PAY-1120 — `rejected` is TERMINAL.

    Otherwise one debt could be written off twice: once through the resurrected
    row and once through the fresh request the clerk raised after being refused.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10807")
        requested = _a_request(dana, account)
        writeoffs.reject_write_off(
            dana,
            write_off_id=requested.write_off_id,
            rejected_on=REQUESTED_ON,
            reason=REJECT_REASON,
        )
        with pytest.raises(PaymentRuleError) as refused:
            writeoffs.approve_write_off(
                actor=dana,
                write_off_id=requested.write_off_id,
                approved_on=REQUESTED_ON,
                posted_at=POSTED_AT,
            )
        assert "terminal" in str(refused.value)
        assert WriteOff.objects.get(pk=requested.write_off_id).journal_entry_id is None


# ══════════════════════════════════════════════════════════════════════════
# 3 · REVERSE — a NEW ROW, and the original never moves (hard rule 4)
# ══════════════════════════════════════════════════════════════════════════


def test_a_reversal_is_a_new_row(brazos, dana):
    """CS-25: *"corrected by a REVERSING WRITE-OFF ROW … never by editing."*"""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10808")
        approved = _an_approved_write_off(dana, account)
        assert WriteOff.objects.filter(account_id=account.pk).count() == 1
        result = writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )
        assert WriteOff.objects.filter(account_id=account.pk).count() == 2
        assert result.write_off_id != approved.write_off_id
        assert result.status == WRITE_OFF_REVERSED
        assert result.reverses_write_off_id == approved.write_off_id
        reversing = WriteOff.objects.get(pk=result.write_off_id)
        # The MAGNITUDE, not a negation: a write-off's direction lives in its
        # posting and `ck_write_offs_amount_positive` holds on every row.
        assert reversing.amount == NOVAK
        assert reversing.reversal_reason == REVERSE_REASON
        # `str(...)` on the LEFT: the column gives a UUID and `WriteOffResult`
        # gives the string a screen will hold. They are the same id in two
        # shapes and the comparison has to say which one it is asking about.
        assert str(reversing.reverses_write_off_id) == approved.write_off_id
        # WHO reversed it — one Admin act, both halves of BR-PAY-037's pair.
        assert reversing.requested_by_id is not None
        assert reversing.approved_by_id == reversing.requested_by_id


def test_the_original_row_is_not_touched_by_a_reversal(brazos, dana):
    """Hard rule 4, column by column — INCLUDING `updated_at`.

    `updated_at` is `auto_now`, so a save of the original with no field changing
    would still move it. Comparing every concrete column is what makes *"not one
    column"* a measurement rather than a promise.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10809")
        approved = _an_approved_write_off(dana, account)
        before = _row_snapshot(approved.write_off_id)
        writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )
        assert _row_snapshot(approved.write_off_id) == before


def test_the_reversal_posts_the_ledgers_own_mirror(brazos, dana):
    """CS-25: *"asking the ledger for its own mirror — never composing a
    compensating entry."*

    Worked on TC-2's figures: the approval posted DR write-off **948.20** /
    CR accounts receivable **948.20**; the mirror posts the same two accounts
    with the sides swapped, so the write-off account nets to **0.00** and the
    receivable is whole.
    """
    from apps.ledger import models as ledger_models
    from apps.ledger import reporting as ledger_reporting
    from apps.ledger import selectors as ledger_selectors

    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10810")
        approved = _an_approved_write_off(dana, account)
        result = writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )
        assert result.posted_to_ledger is True
        assert result.journal_entry_id is not None
        assert result.journal_entry_id != approved.journal_entry_id

        mirror = ledger_models.JournalEntry.objects.get(pk=result.journal_entry_id)
        # Linked, not netted — `reverse_entry` stamps `reversal_of`, so both
        # halves render forever and neither reads as an independent adjustment.
        assert str(mirror.reversal_of_id) == str(approved.journal_entry_id)
        assert mirror.entry_date == REVERSED_ON

        # Balanced pairs (hard rule 5), and the same two GLs the approval used.
        original_lines = {
            (str(line.ledger_account_id), line.side): line.amount
            for line in ledger_models.JournalLine.objects.filter(
                journal_entry_id=approved.journal_entry_id
            )
        }
        mirror_lines = {
            (str(line.ledger_account_id), line.side): line.amount
            for line in ledger_models.JournalLine.objects.filter(journal_entry_id=mirror.pk)
        }
        assert len(mirror_lines) == len(original_lines) == 2
        for (gl, side), amount in original_lines.items():
            other = "credit" if side == "debit" else "debit"
            assert mirror_lines[(gl, other)] == amount

        # And the bad-debt account itself nets to zero over the whole window.
        write_off_gl = ledger_selectors.gl_account_id_for_designation("write_off")
        totals = [
            row
            for row in ledger_reporting.gl_totals(
                start=date(2026, 1, 1), end=date(2026, 12, 31), source_types=("write_off",)
            )
            if str(row.account_id) == str(write_off_gl)
        ]
        assert totals, "the write-off account carries no write-off-sourced lines"
        assert totals[0].debit == NOVAK
        assert totals[0].credit == NOVAK
        assert totals[0].debit - totals[0].credit == Decimal("0")


def test_a_write_off_is_reversed_only_once(brazos, dana):
    """Hard rule 6 — `uq_write_offs_reverses`. A second mirror would put the
    receivable back twice and double the customer's debt."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10811")
        approved = _an_approved_write_off(dana, account)
        first = writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )
        again = writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=date(2026, 12, 20),
            posted_at=datetime(2026, 12, 20, 9, 0, tzinfo=UTC),
            reason="a second attempt",
        )
        assert again.write_off_id == first.write_off_id
        assert [problem["code"] for problem in again.problems] == ["already_reversed"]
        assert WriteOff.objects.filter(account_id=account.pk).count() == 2


def test_only_an_approved_write_off_can_be_reversed(brazos, dana):
    """A request that posted nothing is REJECTED; there is nothing to unwind."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10812")
        requested = _a_request(dana, account)
        with pytest.raises(PaymentRuleError) as refused:
            writeoffs.reverse_write_off(
                dana,
                write_off_id=requested.write_off_id,
                reversed_on=REVERSED_ON,
                posted_at=REVERSED_AT,
                reason=REVERSE_REASON,
            )
        assert "requested" in str(refused.value)
        assert WriteOff.objects.filter(account_id=account.pk).count() == 1


def test_a_reversal_needs_a_reason(brazos, dana):
    """The only explanation a reviewer finds beside a bad-debt figure that came
    back."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10813")
        approved = _an_approved_write_off(dana, account)
        with pytest.raises(PaymentRuleError):
            writeoffs.reverse_write_off(
                dana,
                write_off_id=approved.write_off_id,
                reversed_on=REVERSED_ON,
                posted_at=REVERSED_AT,
                reason="",
            )
        assert WriteOff.objects.filter(account_id=account.pk).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE ORIGINAL AGE — the money-visible half of CS-25
# ══════════════════════════════════════════════════════════════════════════


def test_the_debt_keeps_its_original_age_throughout(brazos, dana):
    """**CS-25's own requirement, measured three times on one debt.**

    *"the debt comes back at its ORIGINAL age, exactly as a bounced payment
    reinstates arrears at the original due date."* An eight-month-old debt that
    came back looking one day old would drop out of every collections bucket.

    Read as of 15 August in all three states — 91 days late, 90+ bucket, every
    time. It cannot move, and the reason it cannot is worth stating: neither the
    write-off nor its reversal writes an allocation row or touches an invoice's
    due date, so `BR-PAY-032`'s anchor (*"today − the OLDEST UNPAID invoice's due
    date"*) has nothing to read but the bill's own 16 May.

    ⚠ **AND THE SAME MEASUREMENT IS `DEF-3121`.** The balance is 948.20 in all
    three states too — so approving the write-off did not take the debt OFF the
    Outstandings list either, while the ledger had already credited receivables
    by 948.20. The age guarantee CS-25 asks for holds; the disappearance CS-25
    assumes had happened never did. Filed, not fixed — closing it writes money
    onto the allocation path.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10814")

        def _seen():
            view = outstandings.outstandings(as_of=AS_OF)
            rows = [row for row in view.rows if row.account_id == str(account.pk)]
            assert len(rows) == 1
            return rows[0]

        before = _seen()
        assert before.days_late == NINETY_ONE
        assert before.bucket == outstandings.BUCKET_90_PLUS
        assert before.balance == NOVAK

        approved = _an_approved_write_off(dana, account)
        after_approval = _seen()
        assert after_approval.days_late == NINETY_ONE
        assert after_approval.bucket == outstandings.BUCKET_90_PLUS
        assert after_approval.balance == NOVAK  # DEF-3121, and it is the finding

        result = writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )
        after_reversal = _seen()
        assert after_reversal.days_late == NINETY_ONE
        assert after_reversal.bucket == outstandings.BUCKET_90_PLUS
        assert after_reversal.balance == NOVAK
        # And the reversal SAYS so rather than letting a screen infer it.
        assert "outstanding_unchanged_by_write_off" in {
            problem["code"] for problem in result.problems
        }


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE PLAN — CS-25's "⚠ WATCH FOR", and why this is ONE change
# ══════════════════════════════════════════════════════════════════════════


def _a_signed_plan(brazos, dana, account, *, signed=True):
    """GT-47's own plan: 267.30 − 50.00 down over 6 → 5 × 36.22 + 36.20."""
    plan = PaymentPlan.objects.create(
        tenant=brazos,
        account=account,
        total_amount=Decimal("267.30"),
        down_payment=Decimal("50.00"),
        currency="USD",
        installment_count=6,
        status=PLAN_ACTIVE if signed else PLAN_PROPOSED,
        proposed_on=date(2026, 6, 1),
        agreement_sent_on=date(2026, 6, 2) if signed else None,
        signed_on=date(2026, 6, 3) if signed else None,
    )
    return plan


def test_a_reversal_reopens_the_plan_the_approval_closed(brazos, dana):
    """CS-25: *"A reversal MUST reopen the payment plan the approval closed, or
    the customer is left with a debt and no schedule."*"""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10815")
        plan = _a_signed_plan(brazos, dana, account)
        approved = _an_approved_write_off(dana, account)
        plan.refresh_from_db()
        assert plan.status == PLAN_CLOSED  # the approval closed it (OQ-171)

        result = writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )
        plan.refresh_from_db()
        assert plan.status == PLAN_ACTIVE
        assert plan.closed_on is None
        assert result.plan_reopened == str(plan.pk)
        assert plans.live_plan_for(account.pk) is not None


def test_an_unsigned_plan_reopens_as_PROPOSED_and_never_as_ACTIVE(brazos, dana):
    """BR-CUS-044 — activation is the CUSTOMER's e-signature alone.

    Reopening every plan to `active` would activate a schedule nobody signed,
    with its late-fee suspension and its disconnect pause live. The pre-closure
    status is reconstructed from the plan's own date columns.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10816")
        plan = _a_signed_plan(brazos, dana, account, signed=False)
        approved = _an_approved_write_off(dana, account)
        plan.refresh_from_db()
        assert plan.status == PLAN_CLOSED

        writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )
        plan.refresh_from_db()
        assert plan.status == PLAN_PROPOSED
        assert plan.signed_on is None


def test_a_newer_live_plan_stops_the_reopen_and_is_named(brazos, dana):
    """BR-CUS-043 — one live plan per account. The newer schedule stands, and
    the reversal SAYS which one rather than failing silently."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10817")
        old = _a_signed_plan(brazos, dana, account)
        approved = _an_approved_write_off(dana, account)
        old.refresh_from_db()
        assert old.status == PLAN_CLOSED
        newer = PaymentPlan.objects.create(
            tenant=brazos,
            account=account,
            total_amount=Decimal("100.00"),
            down_payment=Decimal("0.00"),
            currency="USD",
            installment_count=4,
            status=PLAN_ACTIVE,
            proposed_on=date(2026, 10, 1),
            signed_on=date(2026, 10, 2),
        )

        result = writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )
        old.refresh_from_db()
        assert old.status == PLAN_CLOSED
        assert result.plan_reopened is None
        blocked = [problem for problem in result.problems if problem["code"] == "plan_not_reopened"]
        assert blocked and str(newer.pk) in blocked[0]["detail"]


def test_reopening_a_plan_that_is_not_closed_changes_nothing(brazos, dana):
    """Idempotent by nature, the shape `close_plan_on_write_off` already uses."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10818")
        plan = _a_signed_plan(brazos, dana, account)
        answer = dunning.reopen_plan_on_write_off_reversal(
            actor=dana, plan_id=plan.pk, reversed_on=REVERSED_ON, reason="none"
        )
        assert answer["created"] is False
        plan.refresh_from_db()
        assert plan.status == PLAN_ACTIVE


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE ROLE GATES — on the SERVICE, and mirrored on the door
# ══════════════════════════════════════════════════════════════════════════


def test_a_clerk_is_refused_by_the_reject_service_itself(brazos, dana, marcus):
    """BR-PAY-1120 / BR-SHL-025 — the SERVICE half is the real one, so a job or
    a second endpoint that forgot to gate is refused all the same."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10819")
        requested = _a_request(dana, account)
        with pytest.raises(errors.AuthError):
            writeoffs.reject_write_off(
                marcus,
                write_off_id=requested.write_off_id,
                rejected_on=REQUESTED_ON,
                reason=REJECT_REASON,
            )
        assert WriteOff.objects.get(pk=requested.write_off_id).status == WRITE_OFF_REQUESTED


def test_a_clerk_is_refused_by_the_reverse_service_itself(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10820")
        approved = _an_approved_write_off(dana, account)
        with pytest.raises(errors.AuthError):
            writeoffs.reverse_write_off(
                marcus,
                write_off_id=approved.write_off_id,
                reversed_on=REVERSED_ON,
                posted_at=REVERSED_AT,
                reason=REVERSE_REASON,
            )
        assert WriteOff.objects.filter(account_id=account.pk).count() == 1


def test_a_clerk_is_refused_at_the_door_too(brazos, dana, marcus):
    """The route mirrors the service — never wider (`reversal_api`'s argument)."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10821")
        requested = _a_request(dana, account)
    response = api_call(
        writeoffs_api.write_off_reject,
        "post",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        data={"rejected_on": REQUESTED_ON.isoformat(), "reason": REJECT_REASON},
        write_off_id=str(requested.write_off_id),
    )
    assert response.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
# 7 · THE DOORS, END TO END OVER HTTP
# ══════════════════════════════════════════════════════════════════════════


def test_reject_over_http(brazos, dana):
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10822")
        requested = _a_request(dana, account)
    response = api_call(
        writeoffs_api.write_off_reject,
        "post",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"rejected_on": REQUESTED_ON.isoformat(), "reason": REJECT_REASON},
        write_off_id=str(requested.write_off_id),
    )
    assert response.status_code == 200
    assert response.data["status"] == WRITE_OFF_REJECTED
    # Hard rule 2 — four decimals over the wire, never re-rounded on the way out.
    assert response.data["amount"] == "948.2000"
    assert response.data["posted_to_ledger"] is False
    with tenant_ctx(brazos):
        # WHO rejected it is recorded — the `_actor_id` shape, which reads the
        # door's `SimpleNamespace(id=…)` and not a model's `.pk`.
        assert WriteOff.objects.get(pk=requested.write_off_id).rejected_by_id is not None


def test_reverse_over_http_answers_201_then_200(brazos, dana):
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10823")
        approved = _an_approved_write_off(dana, account)
    body = {
        "reversed_on": REVERSED_ON.isoformat(),
        "posted_at": REVERSED_AT.isoformat(),
        "reason": REVERSE_REASON,
    }
    first = api_call(
        writeoffs_api.write_off_reverse,
        "post",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data=body,
        write_off_id=str(approved.write_off_id),
    )
    assert first.status_code == 201
    assert first.data["status"] == WRITE_OFF_REVERSED
    assert first.data["reverses_write_off_id"] == str(approved.write_off_id)
    assert first.data["amount"] == "948.2000"

    replay = api_call(
        writeoffs_api.write_off_reverse,
        "post",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data=body,
        write_off_id=str(approved.write_off_id),
    )
    # A double-clicked Reverse is a button that worked — 200, not a red 409.
    assert replay.status_code == 200
    assert replay.data["id"] == first.data["id"]


def test_the_queue_serves_both_new_states_and_their_columns(brazos, dana):
    """S36 must be able to render WHY a request was refused and WHAT a row
    reverses — a queue that only says `rejected` sends the same request back."""
    with tenant_ctx(brazos):
        rejected_account = _a_debtor(brazos, dana, account_no="A-10824")
        rejected = _a_request(dana, rejected_account)
        writeoffs.reject_write_off(
            dana,
            write_off_id=rejected.write_off_id,
            rejected_on=REQUESTED_ON,
            reason=REJECT_REASON,
        )
        reversed_account = _a_debtor(brazos, dana, account_no="A-10825")
        approved = _an_approved_write_off(dana, reversed_account)
        reversal = writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=REVERSED_ON,
            posted_at=REVERSED_AT,
            reason=REVERSE_REASON,
        )

        rows = {row["id"]: row for row in writeoffs.write_off_queue()}
        assert rows[str(rejected.write_off_id)]["rejection_reason"] == REJECT_REASON
        assert rows[str(rejected.write_off_id)]["rejected_by_name"] is not None
        assert rows[reversal.write_off_id]["reverses_write_off_id"] == approved.write_off_id
        assert rows[reversal.write_off_id]["reversal_reason"] == REVERSE_REASON

        # And both are filterable, because the constant widened with the states.
        assert len(writeoffs.write_off_queue(status=WRITE_OFF_REJECTED)) == 1
        assert len(writeoffs.write_off_queue(status=WRITE_OFF_REVERSED)) == 1
        with pytest.raises(PaymentRuleError):
            writeoffs.write_off_queue(status="cancelled")
# ── DEF-3420 · a write-off refusal reads as a write-off refusal ─────────────
def test_def_3420__a_write_off_refusal_does_not_read_as_a_payment_error(brazos, dana):
    """The catalogue key this module raises names the ACT, not another module's.

    ⚠ **IT RAISED `payments.record.refused` UNTIL 2026-09-02 AND THAT KEY
    RESOLVES**, which is precisely why nothing caught it: `G32` asks whether a
    raised `message_key` resolves to a sentence, and this one resolved to
    *"This payment can't be recorded as asked. Check the date, amount and
    account."* — shown, in eleven languages, to an approver who was not
    recording a payment. `DEF-3203` was this same path with the key resolving to
    NOTHING, and silence is the easier of the two to notice, because wrong copy
    looks healthy.

    No gate in this repository can ask whether a sentence that resolves is the
    RIGHT sentence, so the guard is a test and it is this one.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10899")
        approved = _an_approved_write_off(dana, account)
    refused = api_call(
        writeoffs_api.write_off_reject,
        "post",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"rejected_on": REQUESTED_ON.isoformat(), "reason": REJECT_REASON},
        write_off_id=str(approved.write_off_id),
    )
    assert refused.status_code == 422
    assert refused.data["message_key"] == "payments.write_off.refused"
    assert refused.data["message_key"] != "payments.record.refused"
