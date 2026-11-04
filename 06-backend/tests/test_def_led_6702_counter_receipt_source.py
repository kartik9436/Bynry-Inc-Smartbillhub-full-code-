# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-LED-6702 — the S56 Journal's SOURCE column printed the raw code
#          `counter_receipt` to a clerk, because `SOURCE_TYPE_TO_VOCABULARY` had
#          no key for the string `apps/payments/ledger_seam.py` writes on every
#          counter-receipt posting.
# Rules:   BR-REP-008 (the report foots to the AR tie-out — nothing invisible) ·
#          BR-REP-009 (applied deposits count as collected) · B14 rule 32 (no
#          internal code in clerk-facing copy) · CLAUDE.md hard rule 2 (money) ·
#          hard-won law 1 (a comment claiming a guarantee is not the guarantee)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""DEF-LED-6702 — a counter receipt is a PAYMENT, and it is NOT cash meeting AR.

⚠ **THE SECOND CASE IS THE REASON THIS FILE EXISTS AND THE FIRST IS THE FIX.**
The one-line change is `"counter_receipt": TYPE_PAYMENT`. The landmine beside it
is `CASH_SOURCE_TYPES`, which means *"cash met a RECEIVABLE"*: a counter receipt
posts DR 1010 / CR 2400 — cash against customer CREDIT — and never touches AR.
Adding it to that tuple would move `collected` and every billed-and-collected
figure on `revenue_and_ar`, **and in the diff it would look exactly like the
copy fix above it**. So the tuple's membership is asserted, by name.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A case that only asserted
`source_vocabulary_for("counter_receipt") == ("payment", True)` would go green
on a map that had ALSO put the string in `CASH_SOURCE_TYPES` — the money
regression and the copy fix are independent, so they are asserted independently.

⚠ **THE THIRD CASE IS A COUNT, NOT A LIST.** `source_vocabulary_for` returns
`mapped=False` for six strings this product's posting code still writes, and
that is `OQ-LED-12657` rather than a bug to paper over: five of them have no
word in BR-REP-008's ten-word vocabulary at all. The case pins the NUMBER so a
lane that maps one without answering the question, or that adds a twelfth
posting caller writing a new string, goes red and is told which.
"""

import pytest

from apps.ledger import reporting

pytestmark = pytest.mark.django_db


#: Every `source_type` the product's posting code writes today, counted from
#: the modules that post to the books. Kept here rather than derived, so that
#: adding a twelfth caller is a deliberate edit to a list a person reads.
WRITTEN_TODAY = (
    "invoice",
    "credit_note",
    "counter_receipt",
    "counter_session",
    "deposit_batch",
    "payment",
    "refund",
    "write_off",
    "manual_je",
    "journal_entry",
    "opening_balance",
    "remittance",
    "allowance_for_doubtful_accounts",
    "depreciation",
    "supplier_invoice",
    "unbilled_revenue_accrual",
    "unpaid_cost_accrual",
)

#: The six with no word yet — `OQ-LED-12657`, OPEN.
UNMAPPED_TODAY = (
    "counter_session",
    "allowance_for_doubtful_accounts",
    "depreciation",
    "supplier_invoice",
    "unbilled_revenue_accrual",
    "unpaid_cost_accrual",
)


def test_a_counter_receipt_reads_as_a_payment_and_not_as_a_raw_code():
    """RED BEFORE: `('counter_receipt', False)` — the code itself, on screen."""
    label, mapped = reporting.source_vocabulary_for("counter_receipt")
    assert mapped is True, "the raw code reaches the clerk"
    assert label == reporting.TYPE_PAYMENT
    assert label != "counter_receipt"


def test_a_counter_receipt_is_NOT_cash_meeting_a_receivable():
    """⚠ THE MONEY HALF. DR 1010 / CR 2400 never touches AR.

    A counter receipt in `CASH_SOURCE_TYPES` moves `collected` on
    `revenue_and_ar`, and the diff that did it would read as a copy fix.
    """
    assert "counter_receipt" not in reporting.CASH_SOURCE_TYPES
    assert "counter_receipt" not in reporting.BILL_SOURCE_TYPES
    # And the tuple is still exactly what it was, so this case cannot be made
    # to pass by emptying it.
    assert reporting.CASH_SOURCE_TYPES == ("payment", "deposit_batch")


def test_the_map_says_how_many_sources_it_cannot_name():
    """Hard-won law 1 — the comment claimed FOUR posting callers; there are 11.

    A blind spot with no number beside it is indistinguishable from an empty
    one, so the number travels.
    """
    unmapped = tuple(
        value for value in WRITTEN_TODAY if not reporting.source_vocabulary_for(value)[1]
    )
    assert unmapped == UNMAPPED_TODAY, (
        "the set of unnamed posting sources moved. Mapping one needs "
        "OQ-LED-12657 answered — five of them have no word in BR-REP-008's "
        "ten-word vocabulary at all. Adding a posting caller that writes a new "
        "string needs this list and the map's own comment updated together."
    )
    assert len(WRITTEN_TODAY) == 17
