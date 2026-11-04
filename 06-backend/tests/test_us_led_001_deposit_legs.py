# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — the two FINAL-BILL
#           deposit rows of the DR/CR table, and TC-1's LE-1 month)
# Rules:    BR-BIL-013 · BR-CUS-050/057 · BR-PAY-012 · BR-LED-001 ·
#           CLAUDE.md rule 2 · rule 4 · rule 5 · rule 6
# Golden:   GT-23 / WE-7 ❄️ · LE-1 §7 (GT-51)
# Tests:    this file
# Impacts:  apps/ledger/deposit_legs.py (the module under test)
# ───────────────────────────────────────────────────────
"""The three deposit legs, against the ❄️ frozen figures that sign them.

**WHAT THESE TESTS ARE FOR.** Until 2026-08-16 a utility that took a $150.00
deposit had that money in the customer's record and nothing in its books on the
way back out: `apps/billing/final_bill.py` computed the interest and the credit
and **no code path posted either**. The trial balance still footed, because the
entries were never made at all, on either side.

Every figure below is copied from a signed source and none is computed here:

  * ❄️ **GT-23 / WE-7** (B5, finance-signed 2026-08-08): a **$150.00** deposit
    held 14 months at 2% simple earns **$3.50**, so **$153.50** applies FIRST.
    Case A's charges **142.30** → refund **11.20**; Case B's **289.40** → due
    **135.90**.
  * **LE-1 §7** (US-LED-001's own finance calculation): deposit interest expense
    DR **3.50**, deposit liability CR **0.00** = 150.00 + 3.50 − 153.50.

A fixture that re-derived any of those would agree with a broken engine.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import chart, deposit_legs, models, posting, selectors

from tests.isolation_helpers import (
    assert_rls_scoped,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.ledger_le_fixtures import make_accounts, uuid_for
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

# ── ❄️ GT-23 / WE-7, transcribed ────────────────────────────────────────────
DEPOSIT_PRINCIPAL = Decimal("150.00")
DEPOSIT_INTEREST = Decimal("3.50")
DEPOSIT_CREDIT = Decimal("153.50")  # "150.00 + 3.50 = 153.50, applies FIRST"
CASE_B_CHARGES = Decimal("289.40")
CASE_B_REMAINDER = Decimal("135.90")
CASE_A_CHARGES = Decimal("142.30")
CASE_A_REFUND = Decimal("11.20")

MOVE_OUT_ON = date(2026, 7, 31)
POSTED_AT = datetime(2026, 8, 3, 9, 15, tzinfo=dt_timezone.utc)


def a_final_invoice_id(seed="WE-7B"):
    """A stable source id per test, so a replay keys the same string."""
    return uuid_for(f"final-bill/{seed}")


def gl_totals(tenant, designation):
    account_id = selectors.gl_account_id_for_designation(designation)
    rows = models.JournalLine.objects.filter(tenant=tenant, ledger_account_id=account_id)
    debits = sum((row.amount for row in rows if row.side == models.SIDE_DEBIT), ZERO)
    credits = sum((row.amount for row in rows if row.side == models.SIDE_CREDIT), ZERO)
    return debits, credits


def accrue(account, *, source_id, interest=DEPOSIT_INTEREST):
    return deposit_legs.post_deposit_interest_accrued(
        account_id=account.id,
        source_type="invoice",
        source_id=source_id,
        interest=interest,
        entry_date=MOVE_OUT_ON,
        posted_at=POSTED_AT,
        currency="USD",
    )


def apply_deposit(account, *, source_id, credit=DEPOSIT_CREDIT, position=CASE_B_CHARGES):
    return deposit_legs.post_deposit_applied(
        account_id=account.id,
        source_type="invoice",
        source_id=source_id,
        credit=credit,
        closing_position=position,
        entry_date=MOVE_OUT_ON,
        posted_at=POSTED_AT,
        currency="USD",
    )


# ═══════════════════════════════════════════════════════════════════════════
# The interest accrual — US-LED-001's *"deposit interest expense | deposit
# liability"*, LE-1's 3.50
# ═══════════════════════════════════════════════════════════════════════════
def test_the_interest_accrual_is_dr_deposit_interest_expense_3_50_cr_liability_3_50(brazos, dana):
    """❄️ WE-7: $150 held 14 months at 2% simple earns **3.50**.

    LE-1 §7 books it *"deposit interest expense DR 3.50"* against the deposit
    liability. The customer is owed 153.50 back from that moment, and the 3.50
    is recognised as the COST of holding somebody else's money — never as a
    reduction of revenue, which would make a month's revenue depend on how many
    tenancies happened to end in it.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        leg = accrue(accounts["ACC-1055"], source_id=a_final_invoice_id())

        assert leg is not None
        assert leg.created is True
        assert leg.amount == DEPOSIT_INTEREST
        assert leg.debit_designation == chart.DEPOSIT_INTEREST_EXPENSE
        assert leg.credit_designation == chart.DEPOSIT_LIABILITY

        # Read back out of the DATABASE, not off what the function returned.
        expense_debits, _ = gl_totals(brazos, chart.DEPOSIT_INTEREST_EXPENSE)
        _, liability_credits = gl_totals(brazos, chart.DEPOSIT_LIABILITY)
        assert expense_debits == DEPOSIT_INTEREST
        assert liability_credits == DEPOSIT_INTEREST

        entry = models.JournalEntry.objects.get(pk=leg.entry_id)
        assert entry.entry_date == MOVE_OUT_ON
        assert entry.currency == "USD"


def test_zero_accrued_interest_posts_nothing_at_all(brazos, dana):
    """A deposit taken last week has accrued nothing, and 0.00 / 0.00 is not an
    entry — it is a journal row for money that did not move, filed on every
    closure in the product for ever."""
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        assert accrue(accounts["ACC-1055"], source_id=a_final_invoice_id(), interest=ZERO) is None
        assert models.JournalEntry.objects.count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# The application — US-LED-001's *"deposit liability | AR"*, LE-1's 153.50
# ═══════════════════════════════════════════════════════════════════════════
def test_the_application_is_dr_deposit_liability_153_50_cr_ar_153_50(brazos, dana):
    """❄️ WE-7 Case B: **153.50** applies against a closing position of
    **289.40**, leaving **135.90** — which is LE-1's master-transfer figure and
    US-BIL-011's *amount due*.

    The DEBIT leg is load-bearing beyond this entry: `reporting.revenue_and_ar`
    identifies an APPLIED deposit by exactly that leg (BR-REP-009 — *applied
    deposits count as collected*), so a version of this that credited AR from
    somewhere else would post the right money and break the collected figure.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        leg = apply_deposit(accounts["ACC-1055"], source_id=a_final_invoice_id())

        assert leg is not None
        assert leg.amount == DEPOSIT_CREDIT
        assert leg.debit_designation == chart.DEPOSIT_LIABILITY
        assert leg.credit_designation == chart.AR

        liability_debits, _ = gl_totals(brazos, chart.DEPOSIT_LIABILITY)
        _, ar_credits = gl_totals(brazos, chart.AR)
        assert liability_debits == DEPOSIT_CREDIT
        assert ar_credits == DEPOSIT_CREDIT

        # The arithmetic the whole rule exists for, stated as the rule states it.
        assert CASE_B_CHARGES - DEPOSIT_CREDIT == CASE_B_REMAINDER


def test_le1_ties_out_the_deposit_liability_to_zero_across_all_three_legs(brazos, dana):
    """LE-1 §7 verbatim: *"2300 deposit liability CR **0.00** (150.00 + 3.50 −
    153.50)"*.

    Three events, three entries, one account: payments credits the receipt on
    the way in (posted here in the same shape its seam uses), this module
    credits the interest and debits the application. The liability nets to
    **0.00** and the interest expense holds **3.50** — the two figures LE-1's
    trial balance carries, and the reason the month foots at 598.69.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        account = accounts["ACC-1055"]
        source_id = a_final_invoice_id()

        # The receipt — payments' half, in payments' own shape (DR cash /
        # CR deposit liability, the signed contract row).
        cash = models.LedgerAccount.objects.get(
            tenant=brazos, pk=selectors.gl_account_id_for_designation(chart.CASH)
        )
        liability = models.LedgerAccount.objects.get(
            tenant=brazos, pk=selectors.gl_account_id_for_designation(chart.DEPOSIT_LIABILITY)
        )
        dims = {"source_type": "payment", "source_id": uuid_for("DEP-1055")}
        posting.post(
            posting.PostingRequest(
                posting_key=posting.posting_key(
                    source_type="payment", source_id=dims["source_id"], event="deposit_taken"
                ),
                entry_date=date(2025, 6, 1),
                posted_at=POSTED_AT,
                currency="USD",
                source_type="payment",
                source_id=dims["source_id"],
                lines=(
                    posting.PostingLine(
                        ledger_account_id=cash.id,
                        side=models.SIDE_DEBIT,
                        amount=DEPOSIT_PRINCIPAL,
                        account_id=account.id,
                        **dims,
                    ),
                    posting.PostingLine(
                        ledger_account_id=liability.id,
                        side=models.SIDE_CREDIT,
                        amount=DEPOSIT_PRINCIPAL,
                        account_id=account.id,
                        **dims,
                    ),
                ),
            )
        )

        accrue(account, source_id=source_id)
        apply_deposit(account, source_id=source_id)

        debits, credits = gl_totals(brazos, chart.DEPOSIT_LIABILITY)
        assert credits - debits == Decimal("0.00")  # LE-1 §7's own 0.00
        assert credits == DEPOSIT_PRINCIPAL + DEPOSIT_INTEREST == Decimal("153.50")
        assert debits == DEPOSIT_CREDIT

        expense_debits, _ = gl_totals(brazos, chart.DEPOSIT_INTEREST_EXPENSE)
        assert expense_debits == DEPOSIT_INTEREST


def test_no_deposit_posts_nothing(brazos, dana):
    """An account that never paid a deposit has nothing to discharge."""
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        assert (
            apply_deposit(accounts["ACC-1042"], source_id=a_final_invoice_id(), credit=ZERO) is None
        )
        assert models.JournalEntry.objects.count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# OQ-248 — CLOSED 2026-09-30 (PO, option A: "A for deposit refund")
# ═══════════════════════════════════════════════════════════════════════════
def test_a_deposit_worth_more_than_the_closing_position_refunds_the_excess_oq_248(brazos, dana):
    """❄️ WE-7 **Case A**: a **153.50** credit against **142.30** of charges.

    This REFUSED until 2026-09-30, and its docstring said: *"If somebody later
    decides where the 11.20 lives, they change this test and the ruling arrives
    with it."* The PO ruled option A — the leftover is REFUNDED — so the 11.20
    goes to 2400 customer credit balances in the same entry and AR is never
    negative. The full set of cases is `test_oq_248_leftover_deposit_is_refunded`.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        leg = apply_deposit(
            accounts["ACC-1055"], source_id=a_final_invoice_id(), position=CASE_A_CHARGES
        )
        assert leg.refunded == CASE_A_REFUND
        _, ar_credits = gl_totals(brazos, chart.AR)
        _, credit_balance = gl_totals(brazos, chart.CUSTOMER_CREDIT_BALANCE)
        liability_debits, _ = gl_totals(brazos, chart.DEPOSIT_LIABILITY)
        assert ar_credits == CASE_A_CHARGES
        assert credit_balance == CASE_A_REFUND
        assert liability_debits == DEPOSIT_CREDIT
        assert models.JournalEntry.objects.count() == 1


def test_a_float_deposit_is_refused_rather_than_coerced(brazos, dana):
    """CLAUDE.md rule 2. Refused rather than converted: the conversion is the
    place a cent goes missing, and the entry it produces cannot be edited."""
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        with pytest.raises(deposit_legs.DepositPostingError) as refusal:
            apply_deposit(accounts["ACC-1055"], source_id=a_final_invoice_id(), credit=153.50)
        assert "float" in str(refusal.value)
        assert models.JournalEntry.objects.count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Idempotency — hard rule 6 / US-LED-001 TC-6
# ═══════════════════════════════════════════════════════════════════════════
def test_replaying_a_closure_writes_no_second_deposit_entry(brazos, dana):
    """*"one entry, ever"* per source event. A resumed release re-emits both
    legs; the second pass returns the first entries with `created=False` and
    writes nothing — which is the correct outcome of a resumed run, not an
    error anybody has to catch.

    The two legs key on the SAME document with DIFFERENT events, so both
    lawfully exist: a document is not the unit of identity, a document plus the
    event that happened to it is.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        account = accounts["ACC-1055"]
        source_id = a_final_invoice_id()

        first_interest = accrue(account, source_id=source_id)
        first_applied = apply_deposit(account, source_id=source_id)
        assert first_interest.posting_key != first_applied.posting_key
        assert models.JournalEntry.objects.count() == 2

        again_interest = accrue(account, source_id=source_id)
        again_applied = apply_deposit(account, source_id=source_id)

        assert again_interest.created is False and again_applied.created is False
        assert again_interest.entry_id == first_interest.entry_id
        assert again_applied.entry_id == first_applied.entry_id
        assert models.JournalEntry.objects.count() == 2

        # And the money did not double.
        debits, credits = gl_totals(brazos, chart.DEPOSIT_LIABILITY)
        assert (debits, credits) == (DEPOSIT_CREDIT, DEPOSIT_INTEREST)


# ═══════════════════════════════════════════════════════════════════════════
# Isolation — US-LED-001 TC-7
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_a_deposit_leg_never_crosses_a_tenant_boundary(rls, brazos, lonestar, dana, erin):
    """US-LED-001 TC-7's shape, on the deposit legs: two utilities discharge a
    deposit each, and neither can see or sum the other's.

    ⚠ **THE OBVIOUS VERSION OF THIS TEST IS VACUOUS AND WAS WRITTEN FIRST.**
    Asserting `JournalEntry.objects.count() == 1` inside the second tenant's
    context goes RED on live Postgres — measured, `assert 2 == 1` — because the
    role this app connects as (`smartbillhub`) is a SUPERUSER and superusers
    BYPASS row-level security unconditionally. The policy is never consulted,
    so the query returns both tenants' rows and the "isolation" test proves
    nothing about isolation. `tests/isolation_helpers.py` records that trap at
    length; the fix is its `rls` probe, which runs the same read under a
    NOSUPERUSER NOBYPASSRLS role on the same connection and transaction.

    So there are two assertions here and they are different promises: the
    per-tenant MONEY figure (app-layer scoping, provable on any vendor) and the
    row visibility (RLS, provable only under the probe).
    """
    with tenant_ctx(brazos):
        brazos_accounts = make_accounts(dana, brazos, {})
        mine = accrue(brazos_accounts["ACC-1055"], source_id=a_final_invoice_id("brazos"))

    with tenant_ctx(lonestar):
        lonestar_accounts = make_accounts(erin, lonestar, {}, service="water")
        accrue(lonestar_accounts["ACC-1055"], source_id=a_final_invoice_id("lonestar"))
        # Its own deposit liability only — never 7.00, which is what a query
        # that had lost its tenant scope would report.
        _, credits = gl_totals(lonestar, chart.DEPOSIT_LIABILITY)
        assert credits == DEPOSIT_INTEREST

    assert_rls_scoped(
        rls, "journal_entries", owner=brazos, intruder=lonestar, owner_ids={mine.entry_id}
    )
    assert_rls_scoped(rls, "journal_lines", owner=brazos, intruder=lonestar)
