# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — the *"Opening balance
#           (cutover batch)"* row of the DR/CR table, and TC-3)
# Rules:    BR-CUS-049 · BR-LED-001 · BR-TEN-043 · CLAUDE.md rule 2 · rule 4 ·
#           rule 5 · rule 6
# Golden:   GT-16 ❄️ B5 FROZEN — the FIGURES are asserted by
#           tests/golden/test_gt16_opening_journal_entry.py, which drives the
#           same module. This file covers the contract's EDGES, which GT-16
#           does not state.
# Tests:    this file
# Impacts:  apps/ledger/opening_balances.py (the module under test)
# ───────────────────────────────────────────────────────
"""The cutover posting contract's edges — the cases GT-16 does not state.

The ❄️ frozen figures (267.30, 2026-08-31, the batch tie-out) are asserted next
door in `tests/golden/test_gt16_opening_journal_entry.py`, which now drives this
same module rather than its own private copy of the composition. Duplicating
them here would be two places to update the day a re-sign moves one.

What is here instead is everything a real migration hits and B5 is silent about:
a customer who owed nothing, a customer in CREDIT, a re-run of the same file,
a float in a spreadsheet column, and a chart with no clearing account.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import chart, models, opening_balances, selectors

from tests.ledger_le_fixtures import make_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

# B5 GT-16 line 55/56, transcribed — used as INPUT here, asserted in the golden.
GT16_BALANCE = Decimal("267.30")
GT16_CUTOVER = date(2026, 8, 31)
BATCH_ID = "0192f0aa-0000-7000-8000-00000000b47c"
IMPORTED_AT = datetime(2026, 9, 1, 8, 0, tzinfo=dt_timezone.utc)


def an_account(dana, brazos, key="ACC-1042"):
    """A REAL customer account — premises, unit and all.

    Not a synthetic uuid: `apps/ledger/posting._stamped` resolves BR-LED-001's
    account → unit → premises chain at posting time and REFUSES an account it
    cannot walk (US-LED-002 TC-5). A cutover entry carries the account
    dimension, so a fixture with a made-up id would prove the refusal rather
    than the contract.
    """
    return make_accounts(dana, brazos, {})[key]


def gl_totals(tenant, designation):
    account_id = selectors.gl_account_id_for_designation(designation)
    rows = models.JournalLine.objects.filter(tenant=tenant, ledger_account_id=account_id)
    debits = sum((row.amount for row in rows if row.side == models.SIDE_DEBIT), ZERO)
    credits = sum((row.amount for row in rows if row.side == models.SIDE_CREDIT), ZERO)
    return debits, credits


def a_batch(accounts):
    return opening_balances.post_opening_batch(
        batch_id=BATCH_ID,
        accounts=accounts,
        cutover_on=GT16_CUTOVER,
        imported_at=IMPORTED_AT,
        currency="USD",
    )


# ═══════════════════════════════════════════════════════════════════════════
# The account dimension — the reason a migrated balance appears on a CUSTOMER
# ═══════════════════════════════════════════════════════════════════════════
def test_a_cutover_balance_lands_on_the_customers_own_ar_position(brazos, dana):
    """A brought-forward balance is not just an AR total — it is what THIS
    customer owed on day one.

    Without BR-LED-001's `account_id` on the line, the money sits in the AR
    control total and on nobody's row: the account screen would say a migrated
    customer owes nothing (DEF-127's exact shape), and the reports lane's own
    note — *"a migrated utility's brought-forward balances are in the books and
    in no band"* — would be permanent rather than a gap.

    So this asserts the figure through the SAME read the account row, the
    account header and the S36 KPI all use.
    """
    from apps.ledger import reporting

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_batch(
            [
                opening_balances.OpeningAccount(
                    account_id=account.id, balance=GT16_BALANCE, account_ref="A-12103"
                )
            ]
        )
        positions = reporting.ar_positions()
        assert positions["available"] is True
        assert positions["positions"][str(account.id)] == GT16_BALANCE


# ═══════════════════════════════════════════════════════════════════════════
# The edges B5 is silent about
# ═══════════════════════════════════════════════════════════════════════════
def test_an_account_that_owed_nothing_at_cutover_posts_no_entry_and_says_so(brazos, dana):
    """A zero opening balance has no opening position to record.

    A 0.00 / 0.00 entry would be a journal entry for money that did not move,
    and GT-16's own fixture batch is 1,213 accounts — so the tempting version of
    this posts up to 1,213 rows a bookkeeper has to read past for ever. It is
    COUNTED as skipped rather than dropped, so the batch total still adds up to
    the number of accounts the importer handed over.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        batch = a_batch(
            [opening_balances.OpeningAccount(account_id=account.id, balance=Decimal("0.00"))]
        )
        assert batch.skipped_count == 1
        assert batch.created_count == 0
        assert len(batch.accounts) == 1  # counted, never dropped
        assert models.JournalEntry.objects.count() == 0


def test_a_customer_in_credit_at_cutover_is_refused_by_name(brazos, dana):
    """A NEGATIVE opening balance means the utility owes the customer money on
    day one, and BR-CUS-049 signs one shape only — *AR ↔ clearing* — with GT-16's
    four imported buckets being an AGEING, so every frozen figure is ≥ 0.

    Posting it as written would file a customer in credit as a receivable
    DEBIT; posting the mirror would be a contract row nobody has signed. The
    migration stops on the row instead, naming the account and the figure, so a
    human sees it on the one customer it affects rather than in a reconciliation
    three months later.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(opening_balances.OpeningBalanceError) as refusal:
            a_batch(
                [
                    opening_balances.OpeningAccount(
                        account_id=account.id, balance=Decimal("-42.10"), account_ref="A-12103"
                    )
                ]
            )
        message = str(refusal.value)
        assert "A-12103" in message and "-42.10" in message
        assert "BR-CUS-049" in message
        assert models.JournalEntry.objects.count() == 0


def test_a_float_opening_balance_is_refused_rather_than_coerced(brazos, dana):
    """CLAUDE.md rule 2. A spreadsheet import is exactly where a float arrives,
    and the entry it would produce is immutable."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(opening_balances.OpeningBalanceError) as refusal:
            a_batch(
                [
                    opening_balances.OpeningAccount(
                        account_id=account.id, balance=267.30, account_ref="A-12103"
                    )
                ]
            )
        assert "float" in str(refusal.value)
        assert models.JournalEntry.objects.count() == 0


def test_a_cutover_with_no_batch_id_is_refused(brazos, dana):
    """GT-16's identity is *per (batch, account)*. Without the batch, importing
    a corrected file for the same accounts would either collide with the first
    import or double the utility's opening receivables — and neither is
    recoverable, because a posted entry cannot be edited (hard rule 4)."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(opening_balances.OpeningBalanceError) as refusal:
            opening_balances.post_opening_batch(
                batch_id="",
                accounts=[
                    opening_balances.OpeningAccount(account_id=account.id, balance=GT16_BALANCE)
                ],
                cutover_on=GT16_CUTOVER,
                imported_at=IMPORTED_AT,
                currency="USD",
            )
        assert "rule 6" in str(refusal.value)
        assert models.JournalEntry.objects.count() == 0


def test_a_tenant_with_no_clearing_designation_cannot_cut_over(brazos, dana):
    """The credit side of every migrated balance goes to `opening_clearing`, and
    a tenant that has un-designated it gets a refusal naming the designation
    rather than a batch posted into a bucket nobody chose.

    Resolved BY DESIGNATION and never by the number 3000 — a tenant may
    renumber their chart (OQ-106), which is the whole reason the designation
    exists.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        clearing_id = selectors.gl_account_id_for_designation(chart.OPENING_CLEARING)
        models.LedgerAccount.objects.filter(pk=clearing_id).update(designation=None)

        with pytest.raises(opening_balances.OpeningBalanceError) as refusal:
            a_batch([opening_balances.OpeningAccount(account_id=account.id, balance=GT16_BALANCE)])
        assert "opening_clearing" in str(refusal.value)
        assert models.JournalEntry.objects.count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Re-running an import — hard rule 6, GT-16's *"no second JE set"*
# ═══════════════════════════════════════════════════════════════════════════
def test_a_resumed_import_reports_replays_separately_from_writes(brazos, dana):
    """A migration that dies halfway is re-run, and the accounts that already
    landed must no-op rather than double.

    `created_count` and `replayed_count` are separate on the result so a caller
    can say *"1,213 accounts, 400 written, 813 already there"* — a distinction a
    progress bar needs and a single count destroys. Both still contribute to the
    batch Σ, because GT-16's tie-out is a statement about the BATCH and not
    about one run of it.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        rows = [
            opening_balances.OpeningAccount(
                account_id=accounts["ACC-1042"].id, balance=GT16_BALANCE, account_ref="A-12103"
            ),
            opening_balances.OpeningAccount(
                account_id=accounts["ACC-1051"].id, balance=Decimal("1450.75")
            ),
        ]
        first = a_batch(rows)
        assert (first.created_count, first.replayed_count) == (2, 0)
        assert first.ties_out and first.ar_debits == Decimal("1718.05")

        again = a_batch(rows)
        assert (again.created_count, again.replayed_count) == (0, 2)
        assert again.ar_debits == first.ar_debits
        assert models.JournalEntry.objects.count() == 2

        # The money did not double — the whole point of the guard.
        ar_debits, _ = gl_totals(brazos, chart.AR)
        _, clearing_credits = gl_totals(brazos, chart.OPENING_CLEARING)
        assert ar_debits == clearing_credits == Decimal("1718.05")


def test_a_different_batch_touching_the_same_account_lawfully_posts(brazos, dana):
    """GT-16 keys *per (batch, account)*, not per account. A utility that
    imports a second, corrected file must be able to bring in a balance the
    first file missed — the guard exists to stop a REPLAY, not to stop a second
    import."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        row = [opening_balances.OpeningAccount(account_id=account.id, balance=GT16_BALANCE)]
        a_batch(row)
        second = opening_balances.post_opening_batch(
            batch_id="0192f0aa-0000-7000-8000-00000000ffff",
            accounts=row,
            cutover_on=GT16_CUTOVER,
            imported_at=IMPORTED_AT,
            currency="USD",
        )
        assert second.created_count == 1
        assert models.JournalEntry.objects.count() == 2
