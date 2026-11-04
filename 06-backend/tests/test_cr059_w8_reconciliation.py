# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 wave W8 — reconciliation. Task 43 (CS-14, the two statement
#           balances and the period read) · task 44 (CS-16, a resolution may
#           hang off a LINE) · task 45 (CS-17, the match SET) · task 46 (CS-18,
#           the difference-reason lookup and its report)
#           Screens: S8 · S37 · S38 · S39 · S40 — every screen half is task 48's
# Rules:    BR-PAY-019 (every difference carries a reason AND a GL) ·
#           BR-PAY-004 (a reconciled batch LOCKS) · BR-PAY-035 ("Force match
#           anyway" permanently SUPERSEDED) · BR-TEN-034 (deactivate, never
#           delete) · BR-TEN-036 (a seeded row is not deletable) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money + CHAR(3)) ·
#           rule 4 (immutability) · rule 5 (only the ledger posts) · rule 6
#           (idempotency) · rule 7 (every money action writes audit_log)
# Ruling:   OQ-161 CLOSED 2026-08-12 — PO verbatim *"Build many-to-one
#           matching"*, worked on $2,840.00 + $14,280.00 posted by the bank as
#           ONE credit of $17,120.00. Every figure in the CS-17 block below is
#           that ruling's, copied and never computed.
# Golden:   PE-10 ❄️ and PE-11 ❄️ must not move. `test_frozen__pe11_still_
#           reconciles_with_the_reason_list_seeded` is the guard that matters:
#           CS-18 turns the reason into a checked code, so a seed that omitted
#           `bank_fee` would break the frozen −5.00 example silently.
# ───────────────────────────────────────────────────────
"""The four W8 reconciliation changes, driven end to end.

WHAT RUNS WHERE, because it changes what a green run is worth (and this file is
honest about it rather than implying more):

  * **Everything below runs on the in-memory SQLite developer database**, which
    has neither RLS nor triggers. So every refusal asserted here is the SERVICE
    refusing — `match_set` declining a second tie on the same bank line, and so
    on — and NOT the database.
  * **The DATABASE half of the same laws is NOT proved by this file and is not
    claimed.** `payments/0012` installs RLS on the three new tables and a
    write-once trigger on the two match-set tables; both are Postgres-only.
    Seeding a live cluster is blocked by `DEF-2395` and another lane is fixing
    it, so this lane could not run them. What that leaves untested is precise
    and worth saying plainly: **if a repair script bypassed the service and
    UPDATEd a match set directly, nothing in this file would have caught it.**

EVERY GUARD HERE WAS DRIVEN RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7);
the mutations and their verbatim failures are in the lane report.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import bankrec_models as bankrec
from apps.payments import bankrec_read, lookups, models, reconciliation, services
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import (
    PE11_BANK,
    PE11_DIFFERENCE,
    PE11_RECORDED,
    a_bank_account,
    a_batch,
    a_statement,
    an_account_of,
    an_issued_bill,
    audit_actions_for,
    gl_id,
    journal_legs,
    leg,
    the_days_batches,
)

pytestmark = pytest.mark.django_db

# ── OQ-161's own figures, verbatim (decision log 2026-08-12) ────────────────
# "a $2,840.00 cheque batch and a $14,280.00 ACH batch banked the same afternoon
#  and posted by the bank as ONE credit of $17,120.00."
SET_CHEQUES = Decimal("2840.00")
SET_ACH = Decimal("14280.00")
SET_COMBINED = Decimal("17120.00")
SET_DAY = date(2026, 8, 5)

# ── CS-14's four figures, and the PO's ruling on what is done with them ────
# CS-14 stated: "Bank's closing balance 48,112.40 · less deposits in transit
# −1,122.78 · add outstanding refund cheques +44.50 · less unexplained lines
# −88.00 → adjusted bank balance 46,946.12".
#
# ⚠ **THE ARITHMETIC IS SUPERSEDED, THE FOUR NUMBERS ARE NOT** (`OQ-1310`
# CLOSED, PO 2026-09-02, verbatim: *"we need to go on factual basis, if bank as
# report we count if bank did not report we dont count, and if clark wants to
# balance the book they can always make journal entries on their own - that is
# allowed"*). The bank reported 48,112.40 and that is counted as it stands; the
# books say 46,946.12; the 1,166.28 between them is EXPLAINED by the three
# reconciling items (1,122.78 − 44.50 + 88.00) and is never folded into either
# side. `CS14_BOOKS` is the spec's old "adjusted" figure re-read as what it
# actually is on a factual statement: the BOOKS' cash.
CS14_CLOSING = Decimal("48112.40")
CS14_IN_TRANSIT = Decimal("1122.78")
CS14_REFUNDS = Decimal("44.50")
CS14_UNEXPLAINED = Decimal("88.00")
CS14_BOOKS = Decimal("46946.12")
CS14_DIFFERENCE = Decimal("1166.28")

STATEMENT_AT = datetime(2026, 8, 11, 6, 40, tzinfo=UTC)
MATCHED_AT = datetime(2026, 8, 11, 9, 15, tzinfo=UTC)


def _import(actor, tenant, rows, *, opening=None, closing=None, start=None, end=None, account=None):
    return reconciliation.import_bank_statement(
        actor=actor,
        bank_account_id=(account or a_bank_account(tenant, name=f"Bank {uuid.uuid4().hex[:6]}")).pk,
        period_start=start or date(2026, 8, 1),
        period_end=end or date(2026, 8, 11),
        payload=a_statement(rows),
        imported_at=STATEMENT_AT,
        opening_balance=opening,
        closing_balance=closing,
    )


# ── CR-186-BRC10 · WHO OWNS A BATCH (PO 2026-10-21, `DEF-PAY-10346`) ────────
# *"One deposit batch per day for each counter TILL, and one for each PROVIDER
# or CHANNEL … All tenders share the batch"*, stamped at posting. So two
# batches on ONE day are two OWNERS, never two tenders: `a_batch` records
# through the default `office` channel and returns that day's single batch, so
# two `a_batch` calls on one day hand back the SAME batch holding both sums
# (the CS-17 fixture read 17,120.00 across 4 payments where it meant 14,280.00).
# Where this file needs two batches on one day it now names each one's channel.
CHANNEL_CHEQUES = "lockbox"  # mailed cheques, opened at the lockbox
CHANNEL_ACH = "invoice_cloud"  # ACH taken online by the provider
CHANNEL_DESK = "office"  # money keyed in by a clerk with no till


def _a_channel_batch(actor, tenant, *, amounts, method_code, day, channel):
    """Record `amounts` under one named channel and return THAT channel's day batch.

    The same money `a_batch` records (one account and one bill per payment,
    through the real `record_payment`), with `deposit_channel` set so the
    batch it joins at posting is this owner's and nobody else's.
    """
    last = None
    for amount in amounts:
        account = an_account_of(actor, tenant)
        an_issued_bill(
            tenant,
            account,
            number=f"BL-2608-{uuid.uuid4().hex[:6]}",
            total=amount,
            issued_on=date(2026, 7, 1),
        )
        last = services.record_payment(
            actor,
            account_id=account.pk,
            amount=amount,
            method_code=method_code,
            posted_at=datetime(day.year, day.month, day.day, 10, 30, tzinfo=UTC),
            idempotency_reference=uuid.uuid4(),
            deposit_channel=channel,
        )
    batch_id = str(models.Payment.objects.get(pk=last.payment_id).deposit_batch_id)
    (batch,) = [row for row in the_days_batches(tenant, day) if row.batch_id == batch_id]
    return batch


# ════════════════════════════════════════════════════════════════════════════
# CS-14 · task 43 — the two statement balances and the period read
# ════════════════════════════════════════════════════════════════════════════
def test_cs14__the_two_balances_are_stored_and_served(brazos, marcus):
    """The bank's own opening and closing figures survive the round trip.

    They are what makes a reconciliation PROVABLE: without a stored closing
    balance the books and the bank are compared batch by batch and never AS
    TOTALS, which is CS-14's whole complaint.
    """
    with tenant_ctx(brazos):
        imported = _import(
            marcus,
            brazos,
            [("2026-08-11", "CHECK DEPOSIT", "471.39")],
            opening=Decimal("40000.00"),
            closing=CS14_CLOSING,
        )
        row = bankrec.BankStatementImport.objects.get(pk=imported.statement_import_id)
        assert row.opening_balance == Decimal("40000.00")
        assert row.closing_balance == CS14_CLOSING

        served = bankrec_read.statement_review(imported.statement_import_id)["statement"]
        assert served["closing_balance"] == "48112.400000"
        assert served["opening_balance"] == "40000.000000"


def test_cs14__an_import_with_no_balances_says_so_and_never_says_zero(brazos, marcus):
    """CS-14: *"an import made before the change simply has no balances and says so."*

    The DEF-127 shape, on the one report that exists to prove the bank rec: a
    `0.00` here would read as *"the bank held nothing"* and the tie-out would
    read as *"difference 0.00 — reconciled"* over a sum nobody could do.
    """
    with tenant_ctx(brazos):
        imported = _import(marcus, brazos, [("2026-08-11", "CHECK DEPOSIT", "471.39")])
        statement = bankrec_read.reconciliation_statement(imported.statement_import_id)

        assert statement["statement"]["closing_balance"] is None
        assert statement["bank_closing_balance"] is None
        assert statement["difference_bank_less_books"] is None
        # NOT False. "We cannot say" and "they differ" are different answers and
        # only one of them is a problem to work.
        assert statement["bank_equals_books"] is None
        codes = {gap["code"] for gap in statement["unavailable"]}
        assert "no_closing_balance_captured" in codes


def _cs14_rows(marcus, brazos, monkeypatch=None, *, books=None):
    """CS-14's own three reconciling items, each as a REAL row, plus the bank's figure.

    The 1,122.78 is a cut batch the bank has not shown, the 44.50 is an issued
    refund cheque, and the 88.00 is a statement line nobody has matched or
    explained — CS-14's own requirement that the statement *"assembles from rows
    that already exist"*.

    `books` pins the LEDGER's side, because the ruling's worked difference needs
    both facts and only one of them is a payments row. Pinned through the same
    published seam the read resolves at call time (`ledger.reporting
    .cash_position`), never by writing the figure into the response.
    """
    transit = a_batch(
        marcus,
        brazos,
        amounts=(Decimal("1000.00"), Decimal("122.78")),
        method_code="cash",
        day=date(2026, 8, 3),
    )
    assert transit.recorded_total == CS14_IN_TRANSIT
    assert transit.status == bankrec.BATCH_IN_TRANSIT

    payment = _a_payment_with_credit(marcus, brazos, Decimal("44.50"))
    models.Refund.objects.create(
        tenant=brazos,
        payment=payment,
        # `DEF-PAY-9090` — a refund is addressed to an ACCOUNT (NOT NULL
        # since `831d3e5f3`, 2026-09-03): the one its payment belongs to.
        account_id=payment.account_id,
        amount=CS14_REFUNDS,
        currency="USD",
        status=models.REFUND_ISSUED,
        method="check",
        reference="10241",
        issued_at=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    )

    imported = _import(
        marcus,
        brazos,
        [("2026-08-10", "UNKNOWN CREDIT", "88.00")],
        closing=CS14_CLOSING,
    )
    if books is not None:
        from apps.ledger import reporting as ledger_reporting

        monkeypatch.setattr(ledger_reporting, "cash_position", lambda **kwargs: {"realised": books})
    return imported.statement_import_id


def _cs14_statement(marcus, brazos, monkeypatch=None, *, books=None):
    """CS-14's rows, and the statement read off them."""
    return bankrec_read.reconciliation_statement(
        _cs14_rows(marcus, brazos, monkeypatch, books=books)
    )


def test_cs14__the_statement_states_two_facts_and_the_difference_between_them(
    brazos, marcus, dana, monkeypatch
):
    """THE RULING'S OWN WORKED FIGURES, to the cent (`OQ-1310` CLOSED 2026-09-02).

    The bank reported **48,112.40** and it is counted exactly as reported — the
    88.00 unexplained line is already inside it. The books say **46,946.12**.
    The difference is **1,166.28**, and it is exactly the three reconciling
    items (`1,122.78 − 44.50 + 88.00`) — which is why they are the EXPLANATION
    and not addends.

    **Nothing is adjusted toward agreement.** A clerk who wants the books moved
    journals it themselves, which is the second half of the ruling.
    """
    with tenant_ctx(brazos):
        statement = _cs14_statement(marcus, brazos, monkeypatch, books=CS14_BOOKS)

        items = {row["code"]: row for row in statement["reconciling_items"]}
        assert items["deposits_in_transit"]["amount"] == "1122.780000"
        assert items["outstanding_refunds"]["amount"] == "44.500000"
        assert items["unexplained_lines"]["amount"] == "88.000000"

        assert statement["bank_closing_balance"] == f"{CS14_CLOSING:.6f}"
        assert statement["book_cash_balance"] == f"{CS14_BOOKS:.6f}"
        assert statement["difference_bank_less_books"] == f"{CS14_DIFFERENCE:.6f}"
        assert statement["bank_equals_books"] is False

        # The items EXPLAIN the gap — asserted here as arithmetic the test does
        # itself, deliberately, because the product must not do it. If the read
        # ever starts summing them for the caller, that is the closed question
        # being re-opened.
        assert CS14_IN_TRANSIT - CS14_REFUNDS + CS14_UNEXPLAINED == CS14_DIFFERENCE
        assert statement["currency"] == "USD"


def test_cs14__no_reconciling_item_carries_a_sign_or_an_adjusted_balance(
    brazos, marcus, dana, monkeypatch
):
    """THE GUARD ON THE RULING ITSELF — the wrong-sign failure cannot come back.

    `OQ-1310` was a sign question worth up to 2,244.56 on the one report that
    decides whether a month's reconciliation is proved, and the PO's answer was
    that there is no sign to get right: what the bank reported is counted, what
    it did not report is not. So a `sign`, a `signed_amount` or an adjusted
    balance reappearing on this body is a closed question being re-opened, and
    this case is what says so before it ships.
    """
    with tenant_ctx(brazos):
        statement = _cs14_statement(marcus, brazos, monkeypatch, books=CS14_BOOKS)

        assert "adjusted_bank_balance" not in statement
        # `reconciled` meant "book + reconciling items = the bank's figure",
        # which is the superseded arithmetic wearing a boolean.
        assert "reconciled" not in statement
        for item in statement["reconciling_items"]:
            assert "sign" not in item, f"{item['code']} grew a sign back"
            assert "signed_amount" not in item, f"{item['code']} grew a signed amount back"

        assert not hasattr(bankrec_read, "_CS14_SIGNS"), (
            "the sign vector was deleted by the ruling; a module-level constant "
            "is how it would come back"
        )


def test_cs14__every_reconciling_item_is_aged_from_the_periods_own_end(
    brazos, marcus, dana, monkeypatch
):
    """*"Keep the items aged and actionable."*

    A deposit in transit that never arrives is a real problem and the only thing
    that says so is its age. The batch was banked on 3 August and the statement
    proves the period ending 11 August, so it is **8 days** old — measured from
    the STATEMENT'S period end and never from a clock, so re-opening March's
    reconciliation in June shows the same ages the person who signed it saw
    (BR-TEN-043).
    """
    with tenant_ctx(brazos):
        statement = _cs14_statement(marcus, brazos, monkeypatch, books=CS14_BOOKS)
        items = {row["code"]: row for row in statement["reconciling_items"]}

        transit = items["deposits_in_transit"]
        assert transit["as_of"] == "2026-08-11"
        assert transit["oldest_age_days"] == 8
        assert [row["age_days"] for row in transit["rows"]] == [8]
        assert transit["rows"][0]["code"].startswith("DEP-")
        # B14 rule 31 — the batch's LABEL is what a clerk reads; the id rides
        # alongside for the link and is never the displayed value.
        assert transit["rows"][0]["amount"] == "1122.780000"

        # 9 August issue date against an 11 August period end.
        assert items["outstanding_refunds"]["oldest_age_days"] == 2
        assert items["outstanding_refunds"]["rows"][0]["reference"] == "10241"
        # 10 August bank line against an 11 August period end.
        assert items["unexplained_lines"]["oldest_age_days"] == 1
        assert items["unexplained_lines"]["rows"][0]["reference"] == "UNKNOWN CREDIT"

        # Every group's count is the length of its own row list — two figures
        # off one set, so a screen cannot show "4 cheques · 44.50" (DEF-3200).
        for item in statement["reconciling_items"]:
            assert item["count"] == len(item["rows"])


def test_cs14__the_outstanding_refund_count_and_amount_come_off_one_set(
    brazos, marcus, dana, monkeypatch
):
    """DEF-3200 — a cheque issued AFTER the period end raised the count, not the money.

    The amount was summed over refunds issued on or before the statement's
    period end and the count was taken over every issued refund in the tenant,
    so a cheque written the day after the period showed as a fourth outstanding
    item worth nothing. Two figures from two sets is DEF-127's shape.
    """
    with tenant_ctx(brazos):
        statement_id = _cs14_rows(marcus, brazos, monkeypatch, books=CS14_BOOKS)
        # A second cheque, issued NINE DAYS AFTER the period this statement
        # proves. It belongs to next month's reconciliation, not this one — so
        # it must raise neither the money nor the count on THIS statement.
        later = _a_payment_with_credit(marcus, brazos, Decimal("60.00"), day=date(2026, 7, 20))
        models.Refund.objects.create(
            tenant=brazos,
            payment=later,
            # `DEF-PAY-9090` — a refund is addressed to an ACCOUNT (NOT NULL
            # since `831d3e5f3`, 2026-09-03): the one its payment belongs to.
            account_id=later.account_id,
            amount=Decimal("60.00"),
            currency="USD",
            status=models.REFUND_ISSUED,
            method="check",
            reference="10299",
            issued_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
        )
        statement = bankrec_read.reconciliation_statement(statement_id)
        refunds = {row["code"]: row for row in statement["reconciling_items"]}[
            "outstanding_refunds"
        ]
        assert refunds["amount"] == f"{CS14_REFUNDS:.6f}"
        assert refunds["count"] == 1
        assert refunds["count"] == len(refunds["rows"])
        assert "10299" not in [row["reference"] for row in refunds["rows"]]


def test_cs14__the_statement_reproduces_cs14s_own_reconciling_items(brazos, marcus, dana):
    """The three items are still assembled from real rows — CS-14's own requirement.

    Kept as its own case after the ruling because the ITEMS did not move; only
    what the statement does with them did. Every input is a REAL row: the
    1,122.78 is a cut batch the bank has not shown, the 44.50 is an issued
    refund cheque, and the 88.00 is a statement line nobody has matched or
    explained.
    """
    with tenant_ctx(brazos):
        # 1,122.78 sitting in transit — cut, and the bank has not shown it.
        transit = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("1000.00"), Decimal("122.78")),
            method_code="cash",
            day=date(2026, 8, 3),
        )
        assert transit.recorded_total == CS14_IN_TRANSIT
        assert transit.status == bankrec.BATCH_IN_TRANSIT

        # 44.50 of refund cheque issued and not yet cleared by the bank.
        payment = _a_payment_with_credit(marcus, brazos, Decimal("44.50"))
        models.Refund.objects.create(
            tenant=brazos,
            payment=payment,
            # `DEF-PAY-9090` — a refund is addressed to an ACCOUNT (NOT NULL
            # since `831d3e5f3`, 2026-09-03): the one its payment belongs to.
            account_id=payment.account_id,
            amount=CS14_REFUNDS,
            currency="USD",
            status=models.REFUND_ISSUED,
            method="check",
            reference="10241",
            issued_at=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        )

        # 88.00 the bank moved and we have neither matched nor explained.
        imported = _import(
            marcus,
            brazos,
            [("2026-08-10", "UNKNOWN CREDIT", "88.00")],
            closing=CS14_CLOSING,
        )
        statement = bankrec_read.reconciliation_statement(imported.statement_import_id)

        items = {row["code"]: row for row in statement["reconciling_items"]}
        assert items["deposits_in_transit"]["amount"] == "1122.780000"
        assert items["outstanding_refunds"]["amount"] == "44.500000"
        assert items["unexplained_lines"]["amount"] == "88.000000"
        # The bank's figure is COUNTED AS REPORTED and never adjusted by them.
        assert statement["bank_closing_balance"] == f"{CS14_CLOSING:.6f}"
        # The books' side is the ledger's own cash position, read by name.
        assert statement["book_cash_balance"] is not None
        assert statement["currency"] == "USD"


def test_cs14__an_explained_line_leaves_the_unexplained_figure_and_gets_its_own(brazos, marcus):
    """CS-16 is what lets the unexplained figure fall — and the money stays visible.

    Once the 88.00 is explained it is no longer "unexplained", but NOTHING was
    posted (batch decision G3), so it is still a difference between the bank and
    the books. It moves to its own line rather than out of the report.
    """
    with tenant_ctx(brazos):
        imported = _import(
            marcus, brazos, [("2026-08-10", "INTEREST", "88.00")], closing=CS14_CLOSING
        )
        line_id = imported.not_in_our_system[0].bank_line_id
        reconciliation.resolve_bank_line(
            actor=marcus,
            bank_line_id=line_id,
            reason_code="bank_interest",
            gl_account_id=gl_id(brazos, "bank_fees"),
            amount=CS14_UNEXPLAINED,
            occurred_at=MATCHED_AT,
        )
        statement = bankrec_read.reconciliation_statement(imported.statement_import_id)
        items = {row["code"]: row for row in statement["reconciling_items"]}
        assert items["unexplained_lines"]["amount"] == "0.000000"
        assert items["unexplained_lines"]["count"] == 0
        assert statement["explained_not_posted"]["amount"] == "88.000000"
        assert statement["explained_not_posted"]["count"] == 1
        codes = {gap["code"] for gap in statement["unavailable"]}
        assert "explained_lines_are_not_posted" in codes


def test_cs14__book_cash_is_unknown_when_the_chart_designates_none(brazos, marcus, monkeypatch):
    """A ledger that cannot answer produces None and a reason, never 0.00.

    `ledger.reporting.cash_position` returns **ZERO** for a tenant with no
    designated cash account — which is exactly DEF-127's shape one module away.
    """
    from apps.ledger import selectors as ledger_selectors

    with tenant_ctx(brazos):
        imported = _import(
            marcus, brazos, [("2026-08-11", "CHECK DEPOSIT", "471.39")], closing=CS14_CLOSING
        )
        monkeypatch.setattr(
            ledger_selectors,
            "gl_account_id_for_designation",
            lambda designation: None,
        )
        statement = bankrec_read.reconciliation_statement(imported.statement_import_id)
        assert statement["book_cash_balance"] is None
        assert statement["difference_bank_less_books"] is None
        assert statement["bank_equals_books"] is None
        codes = {gap["code"] for gap in statement["unavailable"]}
        assert "no_cash_account_designated" in codes


# ════════════════════════════════════════════════════════════════════════════
# CS-16 · task 44 — a resolution may hang off a LINE
# ════════════════════════════════════════════════════════════════════════════
def test_cs16__an_unmatched_line_is_explained_with_a_reason_and_a_gl(brazos, marcus, audit_rows):
    """*"Every bank line ends the period either matched or explained."*

    Before this, a line that is genuinely not a deposit of ours could only be
    LEFT ALONE and it sat there forever with nothing said about it.
    """
    with tenant_ctx(brazos):
        imported = _import(marcus, brazos, [("2026-08-10", "INTEREST CREDIT", "12.40")])
        line_id = imported.not_in_our_system[0].bank_line_id

        result = reconciliation.resolve_bank_line(
            actor=marcus,
            bank_line_id=line_id,
            reason_code="bank_interest",
            gl_account_id=gl_id(brazos, "bank_fees"),
            amount=Decimal("12.40"),
            occurred_at=MATCHED_AT,
            note="Quarterly interest, confirmed on the statement",
        )
        assert result.created is True
        assert result.reason_code == "bank_interest"
        assert result.amount == Decimal("12.40")
        assert result.currency == "USD"

        row = bankrec.BankRecResolution.objects.get(pk=result.resolution_id)
        assert row.batch_id is None  # the parent is the LINE — CS-16's whole change
        assert str(row.bank_line_id) == line_id
        # hard rule 7 — a money action wrote its row.
        assert len(audit_actions_for(audit_rows, reconciliation.AUDIT_LINE_RESOLVED)) == 1

        # The screen reads it back as its own state, with the money on it.
        review = bankrec_read.statement_review(imported.statement_import_id)
        assert review["tiles"]["explained"] == 1
        assert review["rows"][0]["state"] == "explained"
        assert review["rows"][0]["posted"] is False


def test_cs16__explaining_a_line_posts_nothing_batch_decision_g3(brazos, marcus):
    """G3 is UNRULED, so the books are left exactly as they were.

    Creating a payment or a journal entry from an unmatched bank line is batch
    decision G3 and the PO has not ruled on it. The explanation is recorded and
    reportable; the ledger is untouched, and the result says so rather than
    leaving a caller to notice a missing key.
    """
    with tenant_ctx(brazos):
        imported = _import(marcus, brazos, [("2026-08-10", "INTEREST CREDIT", "12.40")])
        before = len(journal_legs(brazos))

        result = reconciliation.resolve_bank_line(
            actor=marcus,
            bank_line_id=imported.not_in_our_system[0].bank_line_id,
            reason_code="bank_interest",
            gl_account_id=gl_id(brazos, "bank_fees"),
            amount=Decimal("12.40"),
            occurred_at=MATCHED_AT,
        )
        assert len(journal_legs(brazos)) == before  # rule 5 — nothing posted
        assert (
            bankrec.BankRecResolution.objects.get(pk=result.resolution_id).journal_entry_id is None
        )
        codes = {gap["code"] for gap in result.unavailable}
        # LBX-05 (DEF-PAY-10694, 2026-10-30) — G3 is ruled, so the "counted only"
        # note is retired; an ordinary explanation still posts nothing (above).
        assert "unmatched_bank_lines_are_counted_only" not in codes


def test_cs16__the_same_explanation_twice_writes_one_row(brazos, marcus):
    """Hard rule 6, on the door where a double-apply writes a second reason.

    The second submit answers with the row that exists and `created=False` —
    deliberately not a red error, because a red error for a button that worked
    is a wrong answer a clerk would act on.
    """
    with tenant_ctx(brazos):
        imported = _import(marcus, brazos, [("2026-08-10", "INTEREST CREDIT", "12.40")])
        line_id = imported.not_in_our_system[0].bank_line_id
        args = dict(
            actor=marcus,
            bank_line_id=line_id,
            reason_code="bank_interest",
            gl_account_id=gl_id(brazos, "bank_fees"),
            amount=Decimal("12.40"),
            occurred_at=MATCHED_AT,
        )
        first = reconciliation.resolve_bank_line(**args)
        second = reconciliation.resolve_bank_line(**args)

        assert first.created is True and second.created is False
        assert first.resolution_id == second.resolution_id
        assert bankrec.BankRecResolution.objects.filter(tenant=brazos).count() == 1


def test_cs16__a_different_explanation_of_the_same_line_is_refused(brazos, marcus):
    """An explanation of a money difference is history the moment it is written."""
    with tenant_ctx(brazos):
        imported = _import(marcus, brazos, [("2026-08-10", "INTEREST CREDIT", "12.40")])
        line_id = imported.not_in_our_system[0].bank_line_id
        reconciliation.resolve_bank_line(
            actor=marcus,
            bank_line_id=line_id,
            reason_code="bank_interest",
            gl_account_id=gl_id(brazos, "bank_fees"),
            amount=Decimal("12.40"),
            occurred_at=MATCHED_AT,
        )
        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.resolve_bank_line(
                actor=marcus,
                bank_line_id=line_id,
                reason_code="bank_error",
                gl_account_id=gl_id(brazos, "bank_fees"),
                amount=Decimal("12.40"),
                occurred_at=MATCHED_AT,
            )
        assert "already explained as bank_interest" in str(refusal.value)


def test_cs16__a_matched_line_is_explained_on_its_batch_not_here(brazos, marcus):
    """Two parents for one difference would record the same money twice."""
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus, brazos, amounts=(Decimal("471.39"),), method_code="check", day=date(2026, 8, 8)
        )
        imported = _import(marcus, brazos, [("2026-08-11", "CHECK DEPOSIT", "471.39")])
        assert imported.matched[0].batch_id == batch.batch_id

        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.resolve_bank_line(
                actor=marcus,
                bank_line_id=imported.matched[0].bank_line_id,
                reason_code="bank_error",
                gl_account_id=gl_id(brazos, "bank_fees"),
                amount=Decimal("1.00"),
                occurred_at=MATCHED_AT,
            )
        assert "is MATCHED to deposit batch" in str(refusal.value)


# ════════════════════════════════════════════════════════════════════════════
# CS-17 · task 45 — the match SET (PO ruling 2026-08-12, OQ-161)
# ════════════════════════════════════════════════════════════════════════════
def _the_po_case(actor, tenant):
    """The PO's own worked case: two batches, one combined bank credit.

    ⚠ CR-186-BRC10 (`DEF-PAY-10346`): OQ-161's *"a $2,840.00 cheque batch and
    a $14,280.00 ACH batch banked the same afternoon"* were two batches because
    they were two TENDERS. Since 2026-10-21 a till's or a channel's day is ONE
    batch whatever the tenders, so the same afternoon's two batches are now two
    OWNERS — the cheques from the lockbox, the ACH from the online provider —
    and every figure of the ruling stands unchanged.
    """
    cheques = _a_channel_batch(
        actor,
        tenant,
        amounts=(Decimal("2000.00"), Decimal("840.00")),  # Σ = 2,840.00
        method_code="check",
        day=SET_DAY,
        channel=CHANNEL_CHEQUES,
    )
    ach = _a_channel_batch(
        actor,
        tenant,
        amounts=(Decimal("10000.00"), Decimal("4280.00")),  # Σ = 14,280.00
        method_code="ach",
        day=SET_DAY,
        channel=CHANNEL_ACH,
    )
    assert cheques.batch_id != ach.batch_id, "one afternoon, two owners, two batches"
    assert cheques.recorded_total == SET_CHEQUES
    assert ach.recorded_total == SET_ACH
    imported = _import(
        actor,
        tenant,
        [("2026-08-06", "COMBINED CREDIT", "17120.00")],
        start=date(2026, 8, 1),
        end=date(2026, 8, 8),
    )
    return cheques, ach, imported


def test_cs17__two_batches_tie_one_bank_credit(brazos, marcus, audit_rows):
    """**OQ-161, built.** $2,840.00 + $14,280.00 tie ONE credit of $17,120.00.

    Under the one-to-one link this money could never be reconciled by anybody:
    `bank_lines` carries `UNIQUE (tenant, deposit_batch)` and the auto-matcher
    compares one line to one batch, so both batches stayed unmatched forever.
    """
    with tenant_ctx(brazos):
        cheques, ach, imported = _the_po_case(marcus, brazos)
        # Auto-match refuses to guess it — nothing here is automatic.
        assert imported.matched == ()

        result = reconciliation.match_set(
            actor=marcus,
            bank_line_ids=(
                [imported.exceptions[0].bank_line_id]
                if imported.exceptions
                else [imported.not_in_our_system[0].bank_line_id]
            ),
            batch_ids=[cheques.batch_id, ach.batch_id],
            occurred_at=MATCHED_AT,
        )
        assert result.created is True
        assert result.matched_total == SET_COMBINED
        assert set(result.batch_codes) == {cheques.code, ach.code}

        # Each batch's share of the credit is its OWN recorded total — nothing
        # is apportioned, which is why the exact-equality rule earns its keep.
        assert bankrec.DepositBatch.objects.get(pk=cheques.batch_id).bank_total == SET_CHEQUES
        assert bankrec.DepositBatch.objects.get(pk=ach.batch_id).bank_total == SET_ACH
        assert bankrec.DepositBatch.objects.get(pk=ach.batch_id).status == bankrec.BATCH_MATCHED
        assert len(audit_actions_for(audit_rows, reconciliation.AUDIT_MATCH_SET)) == 1


def test_cs17__both_batches_reconcile_and_the_cash_debits_sum_to_the_credit(brazos, marcus):
    """The books' half of the ruling: 2,840.00 + 14,280.00 = the bank's 17,120.00.

    Two entries, one per batch, each at a difference of 0.00 — so no money
    figure is apportioned and no new posting shape is invented. This is the
    assertion that makes the exact-equality rule worth its refusals.
    """
    with tenant_ctx(brazos):
        cheques, ach, imported = _the_po_case(marcus, brazos)
        line_id = (imported.exceptions or imported.not_in_our_system)[0].bank_line_id
        reconciliation.match_set(
            actor=marcus,
            bank_line_ids=[line_id],
            batch_ids=[cheques.batch_id, ach.batch_id],
            occurred_at=MATCHED_AT,
        )
        for batch_id in (cheques.batch_id, ach.batch_id):
            outcome = reconciliation.reconcile_batch(
                actor=marcus, batch_id=batch_id, posted_at=MATCHED_AT
            )
            assert outcome.difference == Decimal("0")

        legs = journal_legs(brazos)
        assert leg(legs, "1000", "debit") == SET_COMBINED  # what the bank gave us
        assert leg(legs, "1010", "credit") == SET_COMBINED  # what the customers handed over
        assert (
            bankrec.DepositBatch.objects.get(pk=cheques.batch_id).status == bankrec.BATCH_RECONCILED
        )


def test_cs17__a_set_that_does_not_foot_is_refused_with_both_sums(brazos, marcus):
    """CS-17's new rule: *"the set's totals must be equal."* Nothing is matched.

    Not the tenant's amount tolerance: on ONE pair a difference has an owner and
    is explained with a reason and a GL, and across a set nothing rules how to
    apportion it between the members.
    """
    with tenant_ctx(brazos):
        cheques, ach, _ = _the_po_case(marcus, brazos)
        short = _import(
            marcus,
            brazos,
            [("2026-08-06", "COMBINED CREDIT", "17000.00")],
            start=date(2026, 8, 1),
            end=date(2026, 8, 8),
        )
        line_id = (short.exceptions or short.not_in_our_system)[0].bank_line_id
        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.match_set(
                actor=marcus,
                bank_line_ids=[line_id],
                batch_ids=[cheques.batch_id, ach.batch_id],
                occurred_at=MATCHED_AT,
            )
        message = str(refusal.value)
        assert "does not foot" in message
        assert "17000.00" in message and "17120.00" in message
        assert bankrec.BankRecMatchSet.objects.filter(tenant=brazos).count() == 0
        assert bankrec.DepositBatch.objects.get(pk=ach.batch_id).bank_total is None


def test_cs17__a_member_outside_the_date_window_is_refused(brazos, marcus):
    """*"every member's date within tolerance"* — a set is ONE event."""
    with tenant_ctx(brazos):
        cheques = a_batch(
            marcus,
            brazos,
            amounts=(SET_CHEQUES,),
            method_code="check",
            day=date(2026, 7, 1),  # a month before the credit
        )
        ach = a_batch(marcus, brazos, amounts=(SET_ACH,), method_code="ach", day=SET_DAY)
        imported = _import(
            marcus,
            brazos,
            [("2026-08-06", "COMBINED CREDIT", "17120.00")],
            start=date(2026, 7, 1),
            end=date(2026, 8, 8),
        )
        line_id = (imported.exceptions or imported.not_in_our_system)[0].bank_line_id
        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.match_set(
                actor=marcus,
                bank_line_ids=[line_id],
                batch_ids=[cheques.batch_id, ach.batch_id],
                occurred_at=MATCHED_AT,
            )
        assert "matching window" in str(refusal.value)


def test_cs17__one_line_and_one_batch_is_sent_to_the_ordinary_door(brazos, marcus):
    """Two doors doing one job is how a guarantee quietly moves between them."""
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus, brazos, amounts=(Decimal("471.39"),), method_code="check", day=date(2026, 8, 8)
        )
        imported = _import(marcus, brazos, [("2026-08-11", "CHECK DEPOSIT", "999.00")])
        line_id = (imported.exceptions or imported.not_in_our_system)[0].bank_line_id
        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.match_set(
                actor=marcus,
                bank_line_ids=[line_id],
                batch_ids=[batch.batch_id],
                occurred_at=MATCHED_AT,
            )
        assert "match_bank_line" in str(refusal.value)


def test_cs17__the_same_set_twice_writes_one_set(brazos, marcus):
    """Hard rule 6 — a matching set is ONE event however often it is submitted."""
    with tenant_ctx(brazos):
        cheques, ach, imported = _the_po_case(marcus, brazos)
        line_id = (imported.exceptions or imported.not_in_our_system)[0].bank_line_id
        args = dict(
            actor=marcus,
            bank_line_ids=[line_id],
            batch_ids=[cheques.batch_id, ach.batch_id],
            occurred_at=MATCHED_AT,
        )
        first = reconciliation.match_set(**args)
        second = reconciliation.match_set(**args)

        assert first.created is True and second.created is False
        assert first.match_set_id == second.match_set_id
        assert bankrec.BankRecMatchSet.objects.filter(tenant=brazos).count() == 1
        assert bankrec.BankRecMatchMember.objects.filter(tenant=brazos).count() == 3


def test_cs17__a_line_in_a_set_cannot_also_be_matched_one_to_one(brazos, marcus):
    """The two doors can never both hold, or the same credit is spent twice."""
    with tenant_ctx(brazos):
        cheques, ach, imported = _the_po_case(marcus, brazos)
        line_id = (imported.exceptions or imported.not_in_our_system)[0].bank_line_id
        reconciliation.match_set(
            actor=marcus,
            bank_line_ids=[line_id],
            batch_ids=[cheques.batch_id, ach.batch_id],
            occurred_at=MATCHED_AT,
        )
        # A third owner's batch the same day (CR-186-BRC10): on either of the
        # set's own channels it would simply have JOINED that batch.
        third = _a_channel_batch(
            marcus,
            brazos,
            amounts=(SET_COMBINED,),
            method_code="cash",
            day=SET_DAY,
            channel=CHANNEL_DESK,
        )
        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.match_bank_line(
                actor=marcus,
                batch_id=third.batch_id,
                bank_line_id=line_id,
                occurred_at=MATCHED_AT,
            )
        assert "already part of match set" in str(refusal.value)


def test_cs17__the_screens_read_the_set_back(brazos, marcus):
    """S38's line state and S39's set panel — or the screen contradicts the service.

    A set-matched line rendering as *"needs a look"*, or a set-matched batch
    rendering with an empty bank panel, is the screen telling a clerk the tie
    they just made did not happen.
    """
    with tenant_ctx(brazos):
        cheques, ach, imported = _the_po_case(marcus, brazos)
        line_id = (imported.exceptions or imported.not_in_our_system)[0].bank_line_id
        reconciliation.match_set(
            actor=marcus,
            bank_line_ids=[line_id],
            batch_ids=[cheques.batch_id, ach.batch_id],
            occurred_at=MATCHED_AT,
        )
        review = bankrec_read.statement_review(imported.statement_import_id)
        assert review["tiles"]["set_matched"] == 1
        row = review["rows"][0]
        assert row["state"] == "set_matched"
        assert set(row["match_set_batch_codes"]) == {cheques.code, ach.code}
        assert row["match_set_total"] == f"{SET_COMBINED:.6f}"

        panel = bankrec_read.batch_detail(cheques.batch_id)["match_set"]
        assert panel is not None
        assert len(panel["bank_lines"]) == 1
        assert len(panel["batches"]) == 2
        assert [row["is_this_batch"] for row in panel["batches"]].count(True) == 1

        # The sentence that told clerks this was impossible is GONE from the read.
        codes = {gap["code"] for gap in review["unavailable"]}
        assert "grouped_bank_credits_not_matchable" not in codes


# ════════════════════════════════════════════════════════════════════════════
# CS-18 · task 46 — the difference-reason lookup and its report
# ════════════════════════════════════════════════════════════════════════════
def test_cs18__the_list_is_seeded_on_a_provisioned_tenant(brazos):
    """A tenant arrives with a vocabulary, not with an empty picker.

    `bank_accounts` is the one declared list that seeding can never fill (nobody
    but the utility knows what their accounts are called). This one is the
    opposite: every utility's bank charges them fees, so the eight rows are
    seeded `is_system` and a tenant edits from there.
    """
    with tenant_ctx(brazos):
        rows = {row["code"] for row in bankrec_read.difference_reasons()}
        for code, _name in bankrec.SEED_DIFFERENCE_REASONS:
            assert code in rows
        # The two the engine already writes must be there, or PE-11 and the
        # PO's card day break the day this rule starts biting.
        assert {"bank_fee", "processor_fee"} <= rows
        assert all(
            row.is_system for row in bankrec.BankRecDifferenceReason.objects.filter(tenant=brazos)
        )


def test_cs18__a_reason_off_the_list_is_refused_at_reconcile(brazos, marcus):
    """Free text is what made *"how much was error"* unanswerable."""
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus, brazos, amounts=(PE11_RECORDED,), method_code="check", day=date(2026, 8, 8)
        )
        imported = _import(marcus, brazos, [("2026-08-11", "CHECK DEPOSIT 4410", "588.17")])
        reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=MATCHED_AT,
        )
        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.reconcile_batch(
                actor=marcus,
                batch_id=batch.batch_id,
                posted_at=MATCHED_AT,
                resolutions=(
                    reconciliation.ResolutionInput(
                        reason_code="whatever the clerk typed",
                        gl_account_id=gl_id(brazos, "bank_fees"),
                        amount=PE11_DIFFERENCE,
                    ),
                ),
            )
        message = str(refusal.value)
        assert "is not one of this utility's" in message
        assert "bank_fee" in message  # the refusal QUOTES the list


def test_cs18__an_empty_list_still_accepts_a_reason(brazos, marcus):
    """Required, not lenient: a tenant with no list must still reconcile.

    The list is DISCRETIONARY reference data, so a utility whose S111 toggle was
    off has none and every tenant provisioned before 2026-09-01 has none.
    Refusing on an empty list would break bank reconciliation for all of them on
    the day this control landed — a control that breaks the workflow it governs.
    """
    with tenant_ctx(brazos):
        bankrec.BankRecDifferenceReason.objects.filter(tenant=brazos).delete()
        batch = a_batch(
            marcus, brazos, amounts=(PE11_RECORDED,), method_code="check", day=date(2026, 8, 8)
        )
        imported = _import(marcus, brazos, [("2026-08-11", "CHECK DEPOSIT 4410", "588.17")])
        reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=MATCHED_AT,
        )
        result = reconciliation.reconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            posted_at=MATCHED_AT,
            resolutions=(
                reconciliation.ResolutionInput(
                    reason_code="a reason nobody listed",
                    gl_account_id=gl_id(brazos, "bank_fees"),
                    amount=PE11_DIFFERENCE,
                ),
            ),
        )
        assert result.explained == PE11_DIFFERENCE


def test_cs18__a_deactivated_reason_stops_being_offered_and_history_still_reads(brazos, marcus):
    """BR-TEN-034 on a money vocabulary: deactivate, never delete."""
    with tenant_ctx(brazos):
        imported = _import(marcus, brazos, [("2026-08-10", "INTEREST CREDIT", "12.40")])
        reconciliation.resolve_bank_line(
            actor=marcus,
            bank_line_id=imported.not_in_our_system[0].bank_line_id,
            reason_code="bank_interest",
            gl_account_id=gl_id(brazos, "bank_fees"),
            amount=Decimal("12.40"),
            occurred_at=MATCHED_AT,
        )
        row = bankrec.BankRecDifferenceReason.objects.get(tenant=brazos, code="bank_interest")
        lookups.BankRecReasonLookupHandler().set_active(row, False)

        assert "bank_interest" not in {r["code"] for r in bankrec_read.difference_reasons()}
        # The explanation already written still reads its own code.
        assert bankrec.BankRecResolution.objects.get(tenant=brazos).reason_code == "bank_interest"
        # And a NEW explanation under it is refused.
        second = _import(marcus, brazos, [("2026-08-10", "INTEREST CREDIT", "9.10")])
        with pytest.raises(PaymentRuleError):
            reconciliation.resolve_bank_line(
                actor=marcus,
                bank_line_id=second.not_in_our_system[0].bank_line_id,
                reason_code="bank_interest",
                gl_account_id=gl_id(brazos, "bank_fees"),
                amount=Decimal("9.10"),
                occurred_at=MATCHED_AT,
            )


def test_cs18__the_report_groups_by_reason_and_gl_account(brazos, marcus):
    """*How much was processor fees this quarter, how much was error.*

    Grouped by the PAIR, because BR-PAY-019 makes reason AND GL the control, and
    dated by the MONEY's own day rather than by the day somebody typed it.
    """
    with tenant_ctx(brazos):
        fees = gl_id(brazos, "bank_fees")
        first = _import(marcus, brazos, [("2026-08-10", "INTEREST", "12.40")])
        reconciliation.resolve_bank_line(
            actor=marcus,
            bank_line_id=first.not_in_our_system[0].bank_line_id,
            reason_code="bank_interest",
            gl_account_id=fees,
            amount=Decimal("12.40"),
            occurred_at=MATCHED_AT,
        )
        second = _import(marcus, brazos, [("2026-08-10", "SERVICE CHARGE", "-30.00")])
        reconciliation.resolve_bank_line(
            actor=marcus,
            # LBX-05 (DEF-PAY-10694, 2026-10-30): money the bank took OUT is
            # never "not in our system" — it needs a look (match or fee).
            bank_line_id=second.exceptions[0].bank_line_id,
            reason_code="bank_fee",
            gl_account_id=fees,
            amount=Decimal("-30.00"),
            occurred_at=MATCHED_AT,
        )

        report = bankrec_read.difference_report(start=date(2026, 8, 1), end=date(2026, 8, 31))
        by_reason = {row["reason_code"]: row for row in report["rows"]}
        assert by_reason["bank_interest"]["total"] == "12.400000"
        assert by_reason["bank_fee"]["total"] == "-30.000000"
        assert by_reason["bank_fee"]["line_count"] == 1
        assert by_reason["bank_fee"]["posted_count"] == 0  # G3 — nothing posted
        # SIGNED throughout: 12.40 and −30.00 net to −17.60, never to 42.40.
        assert report["total"] == "-17.600000"
        # B14 rule 31 — a uuid is never the visible value of a field.
        assert by_reason["bank_fee"]["gl_account_code"] == "6800"

        # A period that excludes the money excludes the rows.
        empty = bankrec_read.difference_report(start=date(2026, 9, 1), end=date(2026, 9, 30))
        assert empty["rows"] == [] and empty["resolution_count"] == 0


# ════════════════════════════════════════════════════════════════════════════
# ❄️ THE FROZEN FIGURES — CR-059 task 75's obligation, run here as well
# ════════════════════════════════════════════════════════════════════════════
def test_frozen__pe11_still_reconciles_with_the_reason_list_seeded(brazos, marcus):
    """PE-11 ❄️: bank **588.17** vs batch **593.17** → **−5.00**, explained.

    This case exists because CS-18 turned the reason into a CHECKED code. A seed
    that omitted `bank_fee` would leave the frozen example unreconcilable and
    nothing else in this file would have noticed — the failure would look like a
    validation message, not like a moved finance figure.
    """
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("400.00"), Decimal("193.17")),
            method_code="check",
            day=date(2026, 8, 8),
        )
        assert batch.recorded_total == PE11_RECORDED
        imported = _import(marcus, brazos, [("2026-08-11", "CHECK DEPOSIT 4410", "588.17")])
        assert (
            reconciliation.match_bank_line(
                actor=marcus,
                batch_id=batch.batch_id,
                bank_line_id=imported.exceptions[0].bank_line_id,
                occurred_at=MATCHED_AT,
            )
            == PE11_DIFFERENCE
        )
        result = reconciliation.reconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            posted_at=MATCHED_AT,
            resolutions=(
                reconciliation.ResolutionInput(
                    reason_code="bank_fee",
                    gl_account_id=gl_id(brazos, "bank_fees"),
                    amount=PE11_DIFFERENCE,
                ),
            ),
        )
        assert result.bank_total == PE11_BANK
        assert result.recorded_total == PE11_RECORDED
        assert result.difference == PE11_DIFFERENCE
        legs = journal_legs(brazos)
        assert leg(legs, "1000", "debit") == PE11_BANK
        assert leg(legs, "6800", "debit") == Decimal("5.00")
        assert leg(legs, "1010", "credit") == PE11_RECORDED


def _a_payment_with_credit(actor, tenant, amount, *, day=date(2026, 7, 15)):
    """One CLEARED payment whose row a refund can hang off (B2: `payment_id` NOT NULL).

    ⚠ CR-186-BRC10 (`DEF-PAY-10346`): a payment is `posted` at entry and joins
    its channel's batch AT POSTING, and it becomes `cleared` only when that
    batch is reconciled with the bank (PO 2026-10-21). Before the change this
    helper's payment sat in no batch until a cut, so it was invisible to the
    statement; after it, an unreconciled one is honestly a DEPOSIT IN TRANSIT
    and CS-14's 1,122.78 read 1,167.28 (1,122.78 + this 44.50). The money a
    refund is paid back out of was received and banked BEFORE the refund, so
    the fixture now does exactly that: posted in July, its July batch matched
    to the bank's July line and reconciled, which is what makes it `cleared`.
    """
    batch = _a_channel_batch(
        actor,
        tenant,
        amounts=(amount,),
        method_code="check",
        day=day,
        channel=CHANNEL_CHEQUES,
    )
    banked_on = date(day.year, day.month, day.day + 1)
    imported = _import(
        actor,
        tenant,
        [(banked_on.isoformat(), "CHECK DEPOSIT", f"{amount:.2f}")],
        start=date(day.year, day.month, 1),
        end=banked_on,
    )
    if not any(row.batch_id == batch.batch_id for row in imported.matched):
        reconciliation.match_bank_line(
            actor=actor,
            batch_id=batch.batch_id,
            bank_line_id=(imported.exceptions or imported.not_in_our_system)[0].bank_line_id,
            occurred_at=datetime(banked_on.year, banked_on.month, banked_on.day, 9, 0, tzinfo=UTC),
        )
    reconciliation.reconcile_batch(
        actor=actor,
        batch_id=batch.batch_id,
        posted_at=datetime(banked_on.year, banked_on.month, banked_on.day, 9, 15, tzinfo=UTC),
    )
    payment = models.Payment.objects.get(
        tenant=tenant, deposit_batch_id=batch.batch_id, amount=amount
    )
    assert payment.status == models.PAYMENT_CLEARED
    return payment


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/11-change-requests.md CR-059 §7 (how payments works today) + §8 CS-14/CS-16/CS-17/CS-18 + §9 (the fifteen surfaces) + §11 tasks 43–46 · 12-governance/01-open-questions.md OQ-161 (CLOSED 2026-08-12) · 12-governance/02-decision-log.md 2026-08-12 "BUILD MANY-TO-ONE BANK MATCHING" · 04-docs/05-modules/08-payments/07-pre-session-model.md §7 PE-10/PE-11
# generated: 2026-09-01 by the CR-059 W8 reconciliation lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no frontend half — S8's card, S38's line selection, S39's set panel and S40's picker are CR-059 task 48) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: JOBS_EAGER=false pytest tests/test_cr059_w8_reconciliation.py --reuse-db · every guard proved RED first, quoted in the lane report. THE FOUR CS-14 GUARDS ADDED FOR THE PO's 2026-09-02 RULING WERE RUN AGAINST THE PRE-RULING CODE AT 9ab15301 AND ALL FOUR FAILED, verbatim: `KeyError: 'bank_closing_balance'` · `AssertionError: assert 'adjusted_bank_balance' not in {… 'adjusted_bank_balance': '46946.120000' …}` · `KeyError: 'as_of'` · `assert 2 == 1` (DEF-3200 — the outstanding-cheque count read 2 where the money read one cheque)
# exceptions: (1) ⚠ EVERY CASE HERE RUNS ON SQLITE. The RLS policies and the two write-once triggers `payments/0012` installs are Postgres-only and are NOT exercised by this file — seeding a live cluster is blocked by DEF-2395 and another lane owns the fix. So the SERVICE refusals are proved and the DATABASE ones are not, and that is stated rather than implied
#         (2) `test_cs14__book_cash_is_unknown_when_the_chart_designates_none` monkeypatches the ledger's designation read: no fixture in this repo provisions a tenant with an undesignated cash account, and the branch it covers is the one where a ZERO would be read as a bank balance
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
