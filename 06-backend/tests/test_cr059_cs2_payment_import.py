# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-2 — "Import a lockbox or CSV remittance file".
# Story:    US-PAY-003   Screens: S35 · S33
# Rules:    BR-PAY-023 (staged import; per-row errors skip WITH a report;
#           heuristics flag for review, never auto-guess) · BR-PAY-028 🔒
#           (file+tags idempotency) · BR-PAY-033 (the arrival date comes from
#           the file) · CLAUDE.md hard rule 7 (audit) · hard-won law 14
#           (a failed statement poisons the whole PostgreSQL transaction)
# ───────────────────────────────────────────────────────
"""CS-2 · a lockbox file becomes payments, and the ones we are unsure of do not.

WHAT THIS FILE IS ABOUT
=======================
A utility on a bank lockbox gets one file a day carrying hundreds of cheques and
types every one by hand today. The two rules CS-2 adds are the two this file
spends most of its cases on:

  1 · **nothing is applied on upload** — staging writes no payment at all;
  2 · **a row that cannot be matched with certainty waits for a person, and a
      name-and-amount heuristic never commits on its own.**

⚠ **THE POSTGRESQL CASES ARE NOT OPTIONAL COVERAGE.** Three things this feature
depends on do not exist on the default suite at all — the per-row SAVEPOINT that
CLAUDE.md hard-won law 14 is about, the committed-batch freeze trigger, and row
level security. SQLite has no aborted-transaction state and no plpgsql, so the
broken version of each is GREEN on every machine.

**RED PROOF, RUN AND WATCHED — not reasoned about (law 7).** With the nested
`transaction.atomic()` in `commit_batch`'s loop replaced by a no-op context
manager and the same three-row file driven against live PostgreSQL 16, the run
produces this chain, in this order:

    psycopg.errors.DivisionByZero: division by zero
    django.db.utils.DataError: division by zero
    psycopg.errors.InFailedSqlTransaction: current transaction is aborted,
        commands ignored until end of transaction block
    django.db.utils.InternalError: current transaction is aborted, commands
        ignored until end of transaction block
    django.db.transaction.TransactionManagementError: An error occurred in the
        current transaction. You can't execute queries until the end of the
        'atomic' block.

**Read the middle of that chain rather than the ends.** The poisoned statement
is row 2's; the `InFailedSqlTransaction` belongs to row 3, which did nothing
wrong and could not run. That is the whole of hard-won law 14 in five lines —
one refused row takes the batch with it — and the identical sabotage passes on
SQLite, which has no aborted-transaction state at all.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.payments import lockbox, models, payment_import, selectors
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import (
    requires_postgres,
    rls,  # noqa: F401 — fixture, and it must be IMPORTED to exist: pytest
    rls_probe_role,  # noqa: F401 — resolves fixtures by module namespace, so a
    # bare `rls` argument gives `fixture 'rls' not found` and the case ERRORS
    # rather than failing — which reads as broken plumbing, not as a missing
    # proof of tenant isolation.
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill

pytestmark = pytest.mark.django_db

#: The worked case, in the figures the CR and the decision log already use.
ANN = Decimal("292.87")
BOB = Decimal("1204.55")
CARA = Decimal("57.13")

#: The day the clerk is working — BR-TEN-043: the caller names the day, and this
#: is also the FALLBACK arrival date for a row whose file carried none.
RECORDED_ON = date(2026, 8, 25)
#: The lockbox tags: which account the file came from, and the day it covers.
TAGS = {"bank_account_id": "018f6f6a-0000-7000-8000-00000000b0a1", "received_on": "2026-08-21"}


def an_account(actor, tenant, *, account_no, address, external_ref=None):
    """One account this tenant really has, at its own address.

    A local helper rather than `an_account_of`, because these cases need to
    control the ACCOUNT NUMBER — that number is what a remittance file quotes
    and what the match ladder's first rung reads.
    """
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line=address, services_available=["electric"])
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
        external_ref=external_ref,
    )


def a_file(rows: str) -> bytes:
    header = "Account,Invoice,Payer,Amount,Paid on,Check no\n"
    return (header + rows).encode("utf-8")


def stage(actor, payload, *, tags=None, file_name="lockbox-2026-08-21.csv"):
    return payment_import.stage_import(
        actor, file_name=file_name, payload=payload, tags=dict(tags or TAGS)
    )


def rows_of(batch_id):
    return list(models.PaymentImportRow.objects.filter(batch_id=batch_id).order_by("row_no"))


# ══ RULE 1 · NOTHING IS APPLIED ON UPLOAD ══════════════════════════════════


def test_cs2__upload_creates_no_payment(brazos, dana):
    """CS-2's first new rule, asserted as the absence it is.

    *"A remittance import is staged: upload → validate → preview → commit;
    nothing is applied on upload."* The strongest possible test of that sentence
    is a payment count that has not moved.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        before = models.Payment.objects.count()

        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))

        assert staged.rows == 1
        assert models.Payment.objects.count() == before, (
            "staging created a payment. Nothing may be applied on upload — that is "
            "the whole point of the staged pattern (BR-PAY-023)."
        )
        batch = models.PaymentImportBatch.objects.get(pk=staged.batch_id)
        assert batch.status == models.IMPORT_STAGED
        assert batch.file_hash and len(batch.file_hash) == 64, "the file is stamped at upload"
        assert account.pk is not None


def test_cs2__the_same_file_committed_twice_is_refused(brazos, dana):
    """🔒 BR-PAY-028's file+tags key, and the refusal NAMES the first batch.

    OQ-044's closure asks a duplicate to block *"with who/when/link"*. A lockbox
    file imported twice pays every customer in it twice, which is money the
    utility does not have and hundreds of reversals to unwind.
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        payload = a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n")

        first = stage(dana, payload)
        payment_import.validate_batch(dana, batch_id=first.batch_id)
        payment_import.commit_batch(dana, batch_id=first.batch_id, recorded_on=RECORDED_ON)

        with pytest.raises(PaymentRuleError) as refusal:
            stage(dana, payload)
        assert str(first.batch_id) in str(
            refusal.value
        ), "a duplicate must name the batch that already imported it, not merely say no"
        assert "twice" in str(refusal.value)


def test_cs2__a_corrected_file_imports_normally(brazos, dana):
    """One changed row is a DIFFERENT file, so the bank's correction imports.

    The file half of the key is a hash of the exact bytes, deliberately: a
    utility whose bank re-sends a fixed file must not be locked out by the
    guard that stops a genuine double-import.
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        first = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=first.batch_id)
        payment_import.commit_batch(dana, batch_id=first.batch_id, recorded_on=RECORDED_ON)

        corrected = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10242\n"))
        assert corrected.batch_id != first.batch_id


def test_cs2__a_discarded_batch_moves_no_money_and_is_kept(brazos, dana):
    """A clerk puts the wrong file down. Nothing is undone because nothing was done."""
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        before = models.Payment.objects.count()

        payment_import.discard_batch(dana, batch_id=staged.batch_id, reason="last month's file")

        batch = models.PaymentImportBatch.objects.get(pk=staged.batch_id)
        assert batch.status == models.IMPORT_DISCARDED
        assert models.Payment.objects.count() == before
        assert models.PaymentImportRow.objects.filter(batch_id=batch.pk).exists(), (
            "the rows are KEPT — a bank file that arrived and was set aside is an "
            "event an auditor may need to see"
        )


def test_cs2__discarding_without_a_reason_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        with pytest.raises(PaymentRuleError) as refusal:
            payment_import.discard_batch(dana, batch_id=staged.batch_id, reason="  ")
        assert "reason" in str(refusal.value)


# ══ RULE 2 · THE MATCH LADDER, IN THE EPIC'S PRIORITY ORDER ════════════════


def test_cs2__the_account_number_matches_clean(brazos, dana):
    """Rung one: the customer quoting OUR number. The strongest statement there is."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)

        row = rows_of(staged.batch_id)[0]
        assert row.match_method == models.MATCH_ACCOUNT_NO
        assert row.match_state == models.ROW_CLEAN
        assert str(row.account_id) == str(account.pk)


def test_cs2__the_invoice_number_matches_clean_and_names_the_bill(brazos, dana):
    """Rung two: the customer quoting a bill WE issued — which also says which bill."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        bill = an_issued_bill(
            brazos, account, number="BL-0141", total=ANN, issued_on=date(2026, 7, 1)
        )
        staged = stage(dana, a_file(f",BL-0141,,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)

        row = rows_of(staged.batch_id)[0]
        assert row.match_method == models.MATCH_INVOICE_NO
        assert row.match_state == models.ROW_CLEAN
        assert str(row.account_id) == str(account.pk)
        assert str(row.invoice_id) == str(bill.pk)


def test_cs2__an_unknown_account_reference_is_review_and_not_an_error(brazos, dana):
    """⚠ **AN UNMATCHED CHEQUE IS WORK, NOT A FAULT** — and the distinction is
    the one the preview counts rest on.

    The file names an account this utility does not have: a legacy number, a
    typo, or an account not migrated yet. The money is real either way. A screen
    that reported it as an ERROR would tell a clerk their bank file is broken.
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-9999,,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)

        row = rows_of(staged.batch_id)[0]
        assert row.match_state == models.ROW_REVIEW, "unmatched is REVIEW, never ERROR"
        assert row.match_method == models.MATCH_NONE
        assert row.account_id is None
        assert "AC-9999" in (row.match_detail or ""), "the refusal names what the file said"


def test_cs2__a_name_only_row_is_a_suggestion_and_never_commits(brazos, dana):
    """**CS-2's second new rule, and the case the whole feature turns on.**

    *"A row that cannot be matched to an account with certainty is left
    unmatched for a person, and a name-and-amount heuristic never commits on its
    own."*

    Posting this automatically would put the money on a DIFFERENT customer's
    account, pay down THEIR bill, stop THEIR collection ladder, and leave the
    customer who actually paid being chased for arrears they had settled. Two
    accounts wrong, both silently, and neither fixable by an edit (hard rule 4).

    So the account IS filled in — the person needs to see the suggestion — and
    the commit skips the row anyway.
    """
    with tenant_ctx(brazos):
        account = an_account(
            dana, brazos, account_no="AC-1001", address="1 Bluestem Ln", external_ref="ann ross"
        )
        staged = stage(dana, a_file(f",,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)

        row = rows_of(staged.batch_id)[0]
        assert row.match_method == models.MATCH_NAME_AMOUNT
        assert row.match_state == models.ROW_REVIEW, "a guess is never clean"
        assert str(row.account_id) == str(account.pk), "the suggestion is shown, not hidden"
        assert "SUGGESTION" in (row.match_detail or "")

        before = models.Payment.objects.count()
        result = payment_import.commit_batch(
            dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON
        )
        assert result.committed == 0, "a name-and-amount match must never commit on its own"
        assert result.skipped == 1
        assert models.Payment.objects.count() == before
        assert result.skipped_rows[0]["row_no"] == 1


def test_cs2__a_person_places_a_review_row_and_then_it_commits(brazos, dana):
    """The other side of rule 2: the door a suggestion can eventually go through."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f",,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        row = rows_of(staged.batch_id)[0]

        payment_import.assign_row_account(
            dana, row_id=row.pk, account_id=account.pk, reason="rang the customer, it is theirs"
        )
        row.refresh_from_db()
        assert row.match_method == models.MATCH_MANUAL
        assert row.match_state == models.ROW_CLEAN

        result = payment_import.commit_batch(
            dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON
        )
        assert result.committed == 1
        assert models.Payment.objects.get(pk=result.payment_ids[0]).amount == ANN


def test_cs2__re_validating_does_not_overwrite_a_persons_decision(brazos, dana):
    """A heuristic does not get to argue with somebody who already decided.

    A clerk places a row by hand, then loads the missing accounts and re-runs
    validate — which is exactly the workflow the staged pattern invites. Their
    judgement must survive it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-9999,,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        row = rows_of(staged.batch_id)[0]
        payment_import.assign_row_account(
            dana, row_id=row.pk, account_id=account.pk, reason="legacy number AC-9999 is ours"
        )

        payment_import.validate_batch(dana, batch_id=staged.batch_id)

        row.refresh_from_db()
        assert row.match_method == models.MATCH_MANUAL
        assert str(row.account_id) == str(account.pk)


def test_cs2__placing_a_row_on_another_tenants_account_is_refused(brazos, lonestar, dana):
    """CLAUDE.md hard rule 1, at the one door a person types an account into."""
    with tenant_ctx(lonestar):
        from apps.customers import models as customer_models

        stranger = customer_models.Account.objects.filter(tenant=lonestar).first()
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f",,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        row = rows_of(staged.batch_id)[0]
        target = stranger.pk if stranger is not None else uuid.uuid4()

        with pytest.raises(PaymentRuleError) as refusal:
            payment_import.assign_row_account(
                dana, row_id=row.pk, account_id=target, reason="wrong tenant"
            )
        assert "not one of this tenant's" in str(refusal.value)


# ══ ERROR vs REVIEW, AND THE SKIP-WITH-REPORT ══════════════════════════════


def test_cs2__one_unreadable_row_does_not_cost_the_others(brazos, dana):
    """BR-PAY-023's *"per-row errors skip with a report"*, at the parse.

    ⚠ **THIS IS WHERE THE REMITTANCE PARSER DELIBERATELY DIFFERS FROM THE
    STATEMENT ONE.** `parse_bank_statement` refuses a whole file on one bad row,
    because half a statement reconciles to nothing. A remittance file is a stack
    of independent cheques: one smudged amount must not cost a clerk the other
    three hundred and ninety-nine.
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        an_account(dana, brazos, account_no="AC-1002", address="2 Bluestem Ln")
        staged = stage(
            dana,
            a_file(
                f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"
                ",,Bob Lane,not-money,2026-08-20,10242\n"
                f"AC-1002,,Cara Vale,{CARA},2026-08-20,10243\n"
            ),
        )
        preview = payment_import.validate_batch(dana, batch_id=staged.batch_id)

        assert preview.counts["clean"] == 2
        assert preview.counts["error"] == 1
        assert preview.counts["rows"] == 3

        result = payment_import.commit_batch(
            dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON
        )
        assert result.committed == 2, "the two good cheques bank"
        assert result.skipped == 1
        assert result.skipped_rows[0]["row_no"] == 2
        assert (
            "not an amount" in result.skipped_rows[0]["detail"]
        ), "the skip carries its reason — a row that vanished silently is money nobody chases"


def test_cs2__the_preview_total_is_the_clean_rows_only(brazos, dana):
    """The number a clerk decides on must be the number that will actually post.

    A total including review rows would say $1,554.55 is about to be banked when
    $1,204.55 of it is still waiting for somebody to say whose it is.
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(
            dana,
            a_file(
                f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"
                f",,Bob Lane,{BOB},2026-08-20,10242\n"
                f"AC-1001,,Cara Vale,{CARA},2026-08-20,10243\n"
            ),
        )
        preview = payment_import.validate_batch(dana, batch_id=staged.batch_id)

        assert preview.total_matched == ANN + CARA
        assert preview.counts["clean"] == 2
        assert preview.counts["review"] == 1

        served = selectors.payment_import_batch_dict(staged.batch_id, with_rows=True)
        assert (
            served["total_matched_display"] == "350.00"
        ), "money displays at two places (CLAUDE.md rule 2) beside its stored value"
        assert served["total_matched"] == "350.000000"


# ══ DATES — BR-PAY-033 AND THE PO'S FALLBACK ═══════════════════════════════


def test_cs2__the_arrival_date_comes_from_the_file(brazos, dana):
    """BR-PAY-033, which WON the 2026-08-11 contradiction (OQ-131 CLOSED).

    *"Imports default it from file data where present."* Lateness is judged on
    the day the money actually arrived, never on the import date — so a file
    banked on 20 August and imported on 25 August is judged on the 20th.
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        result = payment_import.commit_batch(
            dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON
        )

        payment = models.Payment.objects.get(pk=result.payment_ids[0])
        assert payment.posted_at.date() == date(
            2026, 8, 20
        ), "the posting date is the FILE's date, not the import day — the rule that won"
        # CR-186-BRC10 (PO 2026-10-21): every payment is POSTED at entry and
        # `cleared` only when its deposit batch is reconciled, so an import
        # writes no clearing date; the file's date is the posting date above.
        assert payment.status == models.PAYMENT_POSTED
        assert payment.cleared_at is None


def test_cs2__a_row_with_no_date_falls_back_to_the_recorded_day(brazos, dana):
    """PO ruling 2026-08-12, verbatim: *"a receipt with no arrival date falls
    back to its recorded date"* — worked there as *"entered 20 Aug against a
    bill due 22 Aug → no fee; entered 25 Aug → still overdue, so the fallback
    forgives nothing."*

    Recorded on the 25th, so the fallback is the 25th. **It forgives nothing.**
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        result = payment_import.commit_batch(
            dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON
        )

        payment = models.Payment.objects.get(pk=result.payment_ids[0])
        assert payment.posted_at.date() == RECORDED_ON
        row = rows_of(staged.batch_id)[0]
        assert row.paid_on is None, (
            "and the ROW still says the file carried no date — the fallback is not "
            "written back as though the bank had stated it"
        )


# ══ THE WALK ITSELF ════════════════════════════════════════════════════════


def test_cs2__an_unvalidated_batch_cannot_be_committed(brazos, dana):
    """The staged pattern is a walk, not four optional steps."""
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        with pytest.raises(PaymentRuleError) as refusal:
            payment_import.commit_batch(dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON)
        assert "has not been validated" in str(refusal.value)


def test_cs2__a_committed_batch_is_refused_by_the_service(brazos, dana):
    """The service says it in a sentence; `payments/0021` says it in the database.

    Two layers, not two copies: the trigger is the guarantee and this is the
    words a clerk reads instead of a constraint violation.
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        payment_import.commit_batch(dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON)

        with pytest.raises(PaymentRuleError) as refusal:
            payment_import.discard_batch(dana, batch_id=staged.batch_id, reason="changed my mind")
        assert "committed" in str(refusal.value)


def test_cs2__a_file_with_no_amount_column_is_refused(brazos, dana):
    """A file-level failure DOES refuse the file — the money is never guessed at."""
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError) as refusal:
            stage(dana, b"Account,Payer,Check no\nAC-1001,Ann Ross,10241\n")
        assert "no amount column" in str(refusal.value)


def test_cs2__an_ofx_file_is_refused_by_name(brazos, dana):
    """Refused BY NAME so the modal can say what to ask the bank for."""
    with tenant_ctx(brazos):
        with pytest.raises(lockbox.BankFileError) as refusal:
            lockbox.parse_remittance_file(b"anything", file_format="ofx")
        assert "OFX" in str(refusal.value)


# ══ HARD RULE 7 · EVERY MONEY ACTION WRITES `audit_log` ════════════════════


def test_cs2__staging_committing_and_discarding_are_each_audited(brazos, dana, audit_rows):
    """Three different acts by a person, three rows — and staging says it moved nothing."""
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        payment_import.commit_batch(dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON)

        # A SECOND file, put down rather than committed — the third act, and the
        # one that is easiest to leave untested because nothing happens in it.
        put_down = stage(
            dana,
            a_file(f"AC-1001,,Ann Ross,{CARA},2026-08-20,10299\n"),
            file_name="wrong-month.csv",
        )
        payment_import.discard_batch(dana, batch_id=put_down.batch_id, reason="last month's file")

    actions = [row.get("action") for row in audit_rows]
    assert payment_import.AUDIT_STAGED in actions
    assert payment_import.AUDIT_COMMITTED in actions
    assert payment_import.AUDIT_DISCARDED in actions

    staged_row = next(r for r in audit_rows if r.get("action") == payment_import.AUDIT_STAGED)
    assert (
        staged_row["after"]["payments_created"] == 0
    ), "the trail must say staging moved nothing — a reader must not have to know it"
    committed_row = next(r for r in audit_rows if r.get("action") == payment_import.AUDIT_COMMITTED)
    assert committed_row["after"]["payments_created"] == 1
    assert committed_row["after"]["recorded_on"] == RECORDED_ON.isoformat()


# ══ POSTGRESQL ONLY — hard-won law 14 and the freeze trigger ═══════════════


@requires_postgres
def test_cs2__one_refused_row_does_not_lose_the_batch(brazos, dana, monkeypatch):
    """⚠ **THE LAW 14 CASE. THE ONLY DATABASE THAT CAN SHOW IT.**

    A failed statement ABORTS a PostgreSQL transaction: every later query raises
    `InFailedSqlTransaction` and the work is lost at COMMIT — after the code has
    reported success. `commit_batch` puts each row in its own SAVEPOINT so a
    refused row costs one row.

    The failure is INJECTED rather than provoked, and that is deliberate: every
    natural way to make `record_payment` fail mid-batch would mean defeating a
    constraint the service exists to hold, and this case is about the LOOP's
    transaction handling and not about which error arrives. A division by zero
    in SQL is a real statement error on PostgreSQL and poisons the transaction
    exactly as a constraint violation does.

    **RED-PROVED, and the observed chain is quoted in this module's docstring.**
    With the nested `transaction.atomic()` removed, row 3 — which did nothing
    wrong — dies with `psycopg.errors.InFailedSqlTransaction: current
    transaction is aborted, commands ignored until end of transaction block`,
    carried up as `TransactionManagementError`. The same sabotage is GREEN on
    SQLite, which has no such state.
    """
    from apps.payments import services as payment_services

    real = payment_services.record_payment

    def poison_the_second_row(actor, **kwargs):
        if kwargs.get("amount") == BOB:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 / 0")  # a REAL aborted statement
        return real(actor, **kwargs)

    monkeypatch.setattr(payment_import.services, "record_payment", poison_the_second_row)

    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        an_account(dana, brazos, account_no="AC-1002", address="2 Bluestem Ln")
        an_account(dana, brazos, account_no="AC-1003", address="3 Bluestem Ln")
        staged = stage(
            dana,
            a_file(
                f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"
                f"AC-1002,,Bob Lane,{BOB},2026-08-20,10242\n"
                f"AC-1003,,Cara Vale,{CARA},2026-08-20,10243\n"
            ),
        )
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        result = payment_import.commit_batch(
            dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON
        )

        assert result.committed == 2, (
            "the two good rows must survive a poisoned one. Without the SAVEPOINT the "
            "transaction is aborted and NONE of them lands — while the count still says 3."
        )
        assert result.skipped == 1
        assert {row["row_no"] for row in result.skipped_rows} == {2}
        amounts = sorted(
            models.Payment.objects.filter(
                pk__in=[uuid.UUID(one) for one in result.payment_ids]
            ).values_list("amount", flat=True)
        )
        assert amounts == sorted([ANN, CARA])

        failed = rows_of(staged.batch_id)[1]
        assert failed.commit_error, (
            "and the reason is ON the row — the report survives even though the payment "
            "did not, which is what BR-PAY-023's skip-with-report asks for"
        )


@requires_postgres
def test_cs2__a_committed_batch_cannot_be_edited_in_the_database(brazos, dana):
    """`payments/0021`'s freeze, written past the service exactly as a shell would.

    Two independent checks on one fact is the discipline a money path keeps, and
    a check that exists only in Python is one check. Once a batch is committed
    its rows are the only record of which file created which payment.
    """
    from django.db import DatabaseError, transaction

    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))
        payment_import.validate_batch(dana, batch_id=staged.batch_id)
        payment_import.commit_batch(dana, batch_id=staged.batch_id, recorded_on=RECORDED_ON)

        # ⚠ **THE DELIBERATE VIOLATION NEEDS ITS OWN SAVEPOINT, AND FINDING THAT
        # OUT COST A RUN.** The trigger raises, which ABORTS the PostgreSQL
        # transaction — so without the nested `atomic()` every later statement
        # in the test, INCLUDING the shared fixture's teardown
        # `set_config('app.tenant_id', '')`, dies with
        # `InFailedSqlTransaction: current transaction is aborted` and takes the
        # NEXT test down with it. Measured: this case failed and the RLS case
        # after it errored, on a connection nobody had misused.
        #
        # That is hard-won law 14 arriving in the TEST rather than in the code
        # the test is about, and it is worth the comment: a case that proves a
        # database refusal has to roll that refusal back, or it is not a case,
        # it is a poisoned connection.
        with pytest.raises(DatabaseError) as refusal:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE payment_import_batches SET file_name = 'edited' WHERE id = %s",
                        [str(staged.batch_id)],
                    )
        assert "append-only" in str(refusal.value)


@requires_postgres
def test_cs2__one_tenants_import_is_invisible_to_another(brazos, lonestar, dana, rls):
    """RLS FORCE on both new tables (hard rule 1), proved through the NON-SUPERUSER
    probe — which is the only way the proof means anything.

    ⚠ **THE ORM WOULD NOT HAVE PROVED THIS.** The test connection runs as the
    app role, which is superuser here (`settings.RLS_ALLOW_BYPASSING_ROLE`, and
    `manage.py check` warns about it on every run), and PostgreSQL evaluates the
    BYPASSRLS exemption against `current_user` — so a queryset asserting "the
    other tenant sees nothing" would pass whether the policy existed or not. The
    `rls` fixture enters `sbh_rls_probe`, which is `NOSUPERUSER NOBYPASSRLS`, so
    the policies are really consulted.

    An import row carries an account id, a payer's name and a money figure. A
    cross-tenant read of it is a cross-tenant read of a customer's payment.
    """
    with tenant_ctx(brazos):
        an_account(dana, brazos, account_no="AC-1001", address="1 Bluestem Ln")
        staged = stage(dana, a_file(f"AC-1001,,Ann Ross,{ANN},2026-08-20,10241\n"))

    with rls.under(brazos):
        assert rls.rows(
            "SELECT count(*) FROM payment_import_batches WHERE id = %s", [str(staged.batch_id)]
        ) == [(1,)], "the owning tenant sees its own batch"
        assert rls.rows(
            "SELECT count(*) FROM payment_import_rows WHERE batch_id = %s", [str(staged.batch_id)]
        ) == [(1,)]

    with rls.under(lonestar):
        assert rls.rows(
            "SELECT count(*) FROM payment_import_batches WHERE id = %s", [str(staged.batch_id)]
        ) == [(0,)], "another utility must not see that a file was even uploaded"
        assert rls.rows(
            "SELECT count(*) FROM payment_import_rows WHERE batch_id = %s", [str(staged.batch_id)]
        ) == [(0,)], "and must not see a payer's name or a cheque amount"
