# ── Trace ──────────────────────────────────────────────
# Change:  **BR-REP-038**, PO ruling 2026-09-27, verbatim: *"it should be like
#          bank statement. this si correct - Build it on the ledger — the
#          account's running record, which holds both sides. Correct by
#          construction; more work"*. It unblocks `CR-142-BRC07` `P2.8`,
#          `P2.15` and `P2.16`.  Screens: 2·1 Report viewer at /reports/statement
# Rules:   BR-REP-038 · BR-REP-001 (a money report states its basis) ·
#          BR-LED-010 (`r_n = r_{n−1} + charge_n − payment_n`) · CLAUDE.md hard
#          rule 5 (only the posting service writes journal lines — this reads) ·
#          hard rule 2 (money to 4 decimals; never a float) · B14 rule 31 ·
#          hard-won law 2's MIRROR (a subject with no read model refuses BY NAME)
# ───────────────────────────────────────────────────────
"""THE WORKED CASE THE PO WAS SHOWN, ASSERTED.

    Dana opens Alia's statement for September. It shows the September bill of
    $84.20, the payment of $84.20 on the 14th, and the balance carried forward.

**WHY THE OLD READING COULD NOT PASS THIS FILE, WHICH IS THE POINT.** R24 was
seeded on the `invoices` dataset, and the invoices dataset's own refusal
sentence says what that meant: *"serving it here would show every bill and no
payment and still print a closing balance."* So the payment assertion below is
not one case among several — it is the whole ruling. A statement that cannot
show `$84.20` leaving is the defect BR-REP-038 exists to end.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (hard-won law 7 clause 2):

  * **ASSERTING ONLY THE TOTALS.** `charges == 84.20` and `payments == 84.20`
    are both satisfied by a report that draws one row and computes the rest, so
    the ROWS are asserted too — two of them, one carrying the charge and one
    carrying the payment, each with its own running balance.
  * **ASSERTING ONLY THE ROWS.** A report that listed both sides and footed
    them wrongly would pass a row check. So the closing balance is asserted as
    `opening + charges − payments`, struck independently of the last row.
  * **A ZERO THAT IS AN ABSENCE.** `$0.00` closing is the right answer here and
    it is also what an empty report foots to. The row count is asserted FIRST,
    so an empty statement cannot reach the balance assertions at all.
  * **A SUBJECT SILENTLY FALLING BACK.** `subject=customer` must REFUSE. A
    fall-back to `account` would answer a different question under a confident
    head, and it would pass every assertion about the account subject.

⚠ **THE SUITE RUNS ON SQLITE (hard-won law 14) AND THAT IS ENOUGH FOR THESE
CASES, WHICH ARE ABOUT ARITHMETIC AND SHAPE.** What SQLite cannot witness is
the PAGE being cut in SQL and the carry-forward surviving it; that is
`10-scripts/rep_p2_statement_pg_proof.py`, on real PostgreSQL 16, and it is
named here so a reader does not mistake this file for the whole proof.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import models, posting
from apps.reports import queries, runner, statement as statement_module

from tests.ledger_le_fixtures import POSTED_AT, gl, line, make_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The PO's own figure, at hard rule 2's stored precision.
BILL = Decimal("84.200000")

SEPT_START = date(2026, 9, 1)
SEPT_END = date(2026, 9, 30)
BILL_DAY = date(2026, 9, 1)
#: *"the payment of $84.20 on the 14th"* — the ruling names the day.
PAYMENT_DAY = date(2026, 9, 14)


def _post_ar(tenant, account, *, side, amount, key, entry_date, source_type, memo):
    """One balanced pair whose AR leg carries the account dimension.

    Written through `posting.post` and never by an INSERT: CLAUDE.md hard rule 5
    — only the ledger posting service writes journal lines — and a fixture that
    broke it would be proving the statement over rows the product cannot
    produce.
    """
    ar = gl(tenant, "1200", "asset")
    other = gl(tenant, "4100", "revenue")
    debit, credit = (ar, other) if side == models.SIDE_DEBIT else (other, ar)
    from tests.ledger_le_fixtures import uuid_for

    source_id = uuid_for(key)
    return posting.post(
        posting.PostingRequest(
            posting_key=key,
            entry_date=entry_date,
            posted_at=POSTED_AT,
            currency="USD",
            source_type=source_type,
            source_id=source_id,
            memo=memo,
            lines=(
                line(
                    debit,
                    models.SIDE_DEBIT,
                    amount,
                    source_type=source_type,
                    source_id=source_id,
                    **({"account_id": account.id} if debit is ar else {}),
                ),
                line(
                    credit,
                    models.SIDE_CREDIT,
                    amount,
                    source_type=source_type,
                    source_id=source_id,
                    **({"account_id": account.id} if credit is ar else {}),
                ),
            ),
        )
    )


@pytest.fixture()
def alia_september(brazos, dana):
    """One account, one September bill of $84.20, one payment of $84.20 on the 14th."""
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        account = accounts["ACC-1042"]
        _post_ar(
            brazos,
            account,
            side=models.SIDE_DEBIT,
            amount=BILL,
            key="br-rep-038-bill",
            entry_date=BILL_DAY,
            source_type="invoice",
            memo="September bill",
        )
        _post_ar(
            brazos,
            account,
            side=models.SIDE_CREDIT,
            amount=BILL,
            key="br-rep-038-payment",
            entry_date=PAYMENT_DAY,
            source_type="payment",
            memo="Payment received",
        )
        yield account


def _statement(account, **extra):
    params = {
        "from": SEPT_START.isoformat(),
        "to": SEPT_END.isoformat(),
        "subject_id": str(account.id),
    }
    params.update(extra)
    return statement_module.statement(params)


# ═══════════════════════════════════════════════════════════════════════════
# The ruling
# ═══════════════════════════════════════════════════════════════════════════
def test_br_rep_038__the_statement_holds_both_sides(brazos, alia_september) -> None:
    """The bill, the payment, and a balance that foots — the PO's worked case."""
    with tenant_ctx(brazos):
        payload = _statement(alia_september)

    rows = payload["rows"]
    assert len(rows) == 2, (
        "a statement of one bill and one payment is TWO rows. "
        f"Got {len(rows)}: {rows!r}. One row means the report is built on "
        "charges alone, which is exactly what BR-REP-038 reversed."
    )

    # ⚠ **COMPARED AS A NUMBER AND NEVER AS A STRING.** `queries._money` serves
    # the EXACT decimal the read model struck, so a zero arrives as `"0"` on a
    # row whose other side carries `"84.200000"` — the widths differ per row.
    # The first draft of this file tested `row["charge"] != "0.000000"` and
    # counted the payment row as a charge, which is the money-as-text trap
    # `financeShared.isZeroAmount` exists for one layer up.
    charge_rows = [row for row in rows if Decimal(row["charge"]) != 0]
    payment_rows = [row for row in rows if Decimal(row["payment"]) != 0]
    assert len(charge_rows) == 1 and Decimal(charge_rows[0]["charge"]) == BILL
    assert len(payment_rows) == 1, (
        "THE STATEMENT SHOWS NO PAYMENT. This is the defect the ruling names: "
        "'invoices are charges, so a statement built on them cannot show a "
        "payment at all'."
    )
    assert Decimal(payment_rows[0]["payment"]) == BILL
    assert payment_rows[0]["entry_date"] == PAYMENT_DAY.isoformat(), (
        "the ruling dates the payment to the 14th and the statement is in DATE "
        "ORDER, so the row must carry the book date it was posted on"
    )

    # In date order: the charge, then the payment.
    assert [row["entry_date"] for row in rows] == [
        BILL_DAY.isoformat(),
        PAYMENT_DAY.isoformat(),
    ]

    # BR-LED-010's formula, row by row — the carry-forward, not a re-derivation.
    assert Decimal(rows[0]["running_balance"]) == BILL
    assert Decimal(rows[1]["running_balance"]) == Decimal("0")


def test_br_rep_038__the_balance_is_carried_forward_and_foots(brazos, alia_september) -> None:
    """Opening + charges − payments = closing, struck without reading a row."""
    with tenant_ctx(brazos):
        payload = _statement(alia_september)

    totals = payload["totals"]
    opening = Decimal(totals["opening_balance"])
    charges = Decimal(totals["charges"])
    payments = Decimal(totals["payments"])
    closing = Decimal(totals["closing_balance"])

    assert charges == BILL and payments == BILL
    assert closing == opening + charges - payments, (
        f"the statement does not foot: {opening} + {charges} − {payments} "
        f"≠ {closing}. A closing balance that is not the movement applied to "
        "the opening is a document a clerk cannot defend to a customer."
    )
    assert opening == Decimal("0")
    assert closing == Decimal("0")


def test_br_rep_038__it_states_the_posting_basis(brazos, alia_september) -> None:
    """BR-REP-001 — and it is the LEDGER's word, not the seeded one.

    `0003` seeded R24 at the EVENT basis labelled *Statement date*. Every figure
    on this report comes off `journal_entries.entry_date`, the BOOK date, and
    the `journal_lines` dataset refuses `regulatory_filing` over exactly this
    mismatch. A statement claiming `event` over posting-dated rows would repeat
    that defect rather than avoid it.
    """
    with tenant_ctx(brazos):
        payload = _statement(alia_september)
    assert payload["basis"] == "posting"


def test_br_rep_038__the_kpis_are_the_four_a_bank_statement_prints(
    brazos, alia_september
) -> None:
    """Opening · charges · payments · closing — in that order, as figures."""
    with tenant_ctx(brazos):
        payload = _statement(alia_september)
    assert [tile["key"] for tile in payload["kpis"]] == [
        "opening_balance",
        "charges",
        "payments",
        "closing_balance",
    ]
    assert Decimal(payload["kpis"][3]["value"]) == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# The refusals — hard-won law 2's mirror, on a money screen
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("subject", ["customer", "premises", "unit"])
def test_br_rep_038__a_subject_with_no_read_model_refuses_by_name(
    brazos, alia_september, subject
) -> None:
    """Three of the four subjects have no running record, and they SAY SO.

    A fall-back to `account` would print one account's money under a heading
    naming a person, a building or a unit — a live control answering a
    different question, which `subject.py` calls *"worse than one that
    refuses"*.
    """
    with tenant_ctx(brazos):
        with pytest.raises(queries.DatasetCannotServe) as raised:
            _statement(alia_september, subject=subject)
    assert raised.value.key == "statement"
    assert raised.value.reason, "a refusal with no sentence is a blank screen"


def test_br_rep_038__no_account_named_is_an_absence_not_the_whole_tenant(brazos) -> None:
    """Handed no subject id it returns NO rows and states why.

    The alternative is every account's postings under one account's heading —
    the failure the `journal_lines` dataset refuses R25 over, in this file's
    own report.
    """
    with tenant_ctx(brazos):
        payload = statement_module.statement(
            {"from": SEPT_START.isoformat(), "to": SEPT_END.isoformat()}
        )
    assert payload["rows"] == []
    codes = [gap["code"] for gap in payload["unavailable"]]
    assert statement_module.NO_SUBJECT_ID["code"] in codes
    # BR-REP-024 — a null tile always carries its reason.
    for tile in payload["kpis"]:
        assert tile["value"] is None and tile["reason_code"]


def test_br_rep_038__no_database_id_reaches_the_rows(brazos, alia_september) -> None:
    """B14 rule 31 — the id travels in the URL and never into a cell."""
    with tenant_ctx(brazos):
        payload = _statement(alia_september)
    for row in payload["rows"]:
        assert "entry_id" not in row and "source_id" not in row
        assert str(alia_september.id) not in str(row.values())


# ═══════════════════════════════════════════════════════════════════════════
# The wiring — hard-won law 2: built is not wired
# ═══════════════════════════════════════════════════════════════════════════
def test_br_rep_038__the_runner_resolves_the_statement_viewer(brazos, alia_september) -> None:
    """`runner.run('statement')` reaches THIS module, not a dataset query.

    Built-not-wired is the shape that costs most here: a viewer nothing
    resolves renders nothing, every test of the function passes, and the card
    goes on refusing.
    """
    with tenant_ctx(brazos):
        result = runner.run(
            "statement",
            {
                "from": SEPT_START.isoformat(),
                "to": SEPT_END.isoformat(),
                "subject_id": str(alia_september.id),
            },
        )
    assert result.dataset == "journal_lines", (
        "the definition is still seeded on `invoices`. `0007` moves it; without "
        "the migration this report is refused by the invoices dataset by name."
    )
    assert len(result.payload["rows"]) == 2


def test_br_rep_038__bind_no_longer_drops_the_subject(brazos) -> None:
    """DEF-REP-6908 — `subject` and `subject_id` reach the query.

    Measured before the fix on real PostgreSQL: `runner.bind` returned only
    `{'basis': 'posting'}` and `runner.dropped()` named `subject`, `subject_id`
    and `account`. A stored vocabulary no query can receive is hard-won law 1
    written into a migration.
    """
    with tenant_ctx(brazos):
        definition = runner.resolve("statement")
        bound = runner.bind(definition, {"subject": "account", "subject_id": "abc"})
    assert bound.get("subject") == "account"
    assert bound.get("subject_id") == "abc"
