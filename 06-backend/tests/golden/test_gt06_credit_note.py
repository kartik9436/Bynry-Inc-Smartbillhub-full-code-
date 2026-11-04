# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill issue + correction)
#           Screens: — (the consequence message renders before confirm, S31/S32)
# Rules:    BR-BIL-004 (issued invoices and their lines are immutable;
#           corrections = credit note / rebill) · BR-BIL-009 (void flows show a
#           plain-language consequence message before confirm) · BR-PAY-011
#           (always reversing entries, never edits) · HR-4 · HR-5
# Golden:   GT-6 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 27-28).
# Tests:    this file (xfail until billing publishes issue_credit_note)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/billing (owner) ·
#           apps/ledger/posting.py 🔒 (the sole journal writer)
# ───────────────────────────────────────────────────────
"""GT-6 - Issued invoice $247.30 + $25 billing-error credit -> invoice unchanged, credit note references it, balance 222.30, balanced reversing entry

B5 GT-6 verbatim
----------------
  line 27: "## GT-6 - Credit note against issued invoice"
  line 28: "Input: invoice $247.30 issued; billing-error credit $25. Expected:
            original invoice unchanged (immutable); new credit note references
            it; balance 222.30; balanced reversing journal entry."
            ... SUPERSEDED stamp: "PO Q&A R6 2026-08-08 -> OQ-012 CLOSED ->
            BR-PAY-011/BR-BIL-009: always reversing entries, never edits, with
            consequence messaging before the action; immutability itself is B2 +
            hard rule 4."

NOT FROZEN IN B5: the journal entry's ACCOUNTS and its amount. B5 says
"balanced reversing journal entry" and stops. So this test asserts that the
entry BALANCES (debits == credits) and asserts nothing about which accounts it
hits or what it is worth. The seed chart of accounts is signed in B5 (line 74)
but B5 never maps GT-6's credit onto it, and mapping it here would be inventing
the posting.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

from .conftest import requires_engine

pytestmark = pytest.mark.golden

# ── INPUT (B5 GT-6 line 28) ─────────────────────────────────────────────────
INVOICE_NUMBER = "GT-6-INVOICE"  # B5 names no document number; a label only
INVOICE_TOTAL = Decimal("247.30")  # "invoice $247.30 issued"
CREDIT_AMOUNT = Decimal("25")  # "billing-error credit $25"
REASON_CODE = "billing_error"  # "billing-error credit"

# ── EXPECTED (B5 GT-6 line 28) ──────────────────────────────────────────────
EXPECTED_INVOICE_TOTAL_UNCHANGED = Decimal("247.30")  # "original invoice unchanged (immutable)"
EXPECTED_BALANCE = Decimal("222.30")  # "balance 222.30"


@requires_engine
def test_gt06_credit_note():
    # B5 FROZEN 2026-08-08 - xfail flips to must-pass when the engine lands (W3).
    outcome = rating_seam.issue_credit_note(
        invoice_number=INVOICE_NUMBER,
        invoice_total=INVOICE_TOTAL,
        credit_amount=CREDIT_AMOUNT,
        reason_code=REASON_CODE,
    )

    # "original invoice unchanged (immutable)" — hard rule 4: the issued
    # document is never rewritten; the correction is a NEW row.
    assert outcome.invoice_total == EXPECTED_INVOICE_TOTAL_UNCHANGED

    # "new credit note references it"
    assert outcome.references_invoice == INVOICE_NUMBER
    assert outcome.credit_total == CREDIT_AMOUNT

    # "balance 222.30"
    assert outcome.balance == EXPECTED_BALANCE

    # "balanced reversing journal entry" — hard rule 5. B5 states balance and
    # nothing more, so balance and nothing more is asserted.
    assert outcome.journal_debits == outcome.journal_credits

    # NOT FROZEN IN B5: which GL accounts the reversing pair hits, and the
    # amount of the entry. Deliberately unasserted — see the module docstring.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (must NOT pass until billing publishes the seam)
# exceptions: PARTIAL — B5 GT-6 says "balanced reversing journal entry" without naming accounts or an amount, so only debits==credits is asserted. The invoice number is a fixture label (B5 names no document number) and nothing asserts its value beyond the credit note referencing it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
