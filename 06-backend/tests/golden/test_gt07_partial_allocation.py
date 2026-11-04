# ── Trace ──────────────────────────────────────────────
# Epics:    EP-PAY-02 (record payment + allocation)
#           Screens: — (allocation preview renders on S35/S36)
# Rules:    BR-PAY-010 (allocation order: DEFAULT oldest-invoice-first; within
#           an invoice usage+base -> taxes -> fees LAST; overpayment carries as
#           credit; tenant-reconfigurable) · BR-PAY-001 (default = oldest open
#           bill)
# Golden:   GT-7 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 30-31).
# Tests:    this file (xfail until payments publishes allocate_payment)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/payments (owner)
# ───────────────────────────────────────────────────────
"""GT-7 - BL-A $100 oldest + BL-B $147.30; pay $120 oldest-first -> A paid 100, B paid 20 (allocation order PLACEHOLDER)

B5 GT-7 verbatim
----------------
  line 30: "## GT-7 - Partial payment + allocation"
  line 31: "Input: balance across BL-A $100 (oldest), BL-B $147.30; payment $120
            'oldest first'. Expected: BL-A paid 100, BL-B paid 20, remaining
            127.30."
            ... SUPERSEDED stamp: "PO Q&A R6 2026-08-08 -> OQ-010 CLOSED ->
            BR-PAY-010: oldest invoice first; within an invoice usage+base ->
            taxes -> fees/late last; overpayment carries as credit;
            tenant-reconfigurable. GT-35..50 (PE workbook) are the full
            composite fixtures."

The stub docstring's "(allocation order PLACEHOLDER)" is the pre-freeze marker;
B5's own inline stamp records it SUPERSEDED and the order CONFIRMED.

NOT FROZEN IN B5: any date. B5 names BL-A as "(oldest)" and gives no issue
dates, so the fixture carries that ordering as B5 states it — a sequence — and
`issued_on` stays None rather than a calendar being invented to imply the order.
NOT FROZEN IN B5 either: the WITHIN-invoice split (usage+base -> taxes -> fees
last). BR-PAY-010 rules it, but GT-7 gives no line breakdown for BL-A or BL-B,
so it is not asserted here; B5 points at GT-35..50 for the composites.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

pytestmark = pytest.mark.golden

# ── INPUT (B5 GT-7 line 31) ─────────────────────────────────────────────────
BL_A = rating_seam.OpenInvoice(number="BL-A", balance=Decimal("100"))  # "BL-A $100 (oldest)"
BL_B = rating_seam.OpenInvoice(number="BL-B", balance=Decimal("147.30"))  # "BL-B $147.30"
# B5's stated ordering: BL-A is the oldest, so it leads the sequence.
OPEN_INVOICES = (BL_A, BL_B)
PAYMENT_AMOUNT = Decimal("120")  # "payment $120"
ORDER = "oldest_first"  # "'oldest first'"

# ── EXPECTED (B5 GT-7 line 31) ──────────────────────────────────────────────
EXPECTED_APPLIED_TO_A = Decimal("100")  # "BL-A paid 100"
EXPECTED_APPLIED_TO_B = Decimal("20")  # "BL-B paid 20"
EXPECTED_REMAINING = Decimal("127.30")  # "remaining 127.30"


def test_gt07_partial_allocation():
    # B5 FROZEN 2026-08-08 - the @requires_engine xfail was REMOVED 2026-08-11
    # (payments allocation lane) because apps.payments.services.allocate_payment
    # now publishes the seam and this reproduces every frozen figure. Must pass
    # forever from here; no expected value in this file was touched.
    outcome = rating_seam.allocate_payment(
        payment_amount=PAYMENT_AMOUNT,
        open_invoices=OPEN_INVOICES,
        order=ORDER,
    )

    assert outcome.applied_to("BL-A") == EXPECTED_APPLIED_TO_A
    assert outcome.applied_to("BL-B") == EXPECTED_APPLIED_TO_B
    assert outcome.remaining_balance == EXPECTED_REMAINING

    # The oldest bill is settled FIRST and in full before the next is touched —
    # that ordering is the rule GT-7 exists to pin (BR-PAY-010).
    assert [allocation.invoice_number for allocation in outcome.allocations] == ["BL-A", "BL-B"]

    # BR-PAY-010: overpayment carries as credit. GT-7 is a PARTIAL payment, so
    # nothing carries; B5 states no credit figure and none is asserted beyond
    # the absence the arithmetic implies.
    assert outcome.credit_carried == Decimal("0")

    # NOT FROZEN IN B5: the within-invoice split (usage+base -> taxes -> fees
    # last). GT-7 gives no line breakdown; B5 points at GT-35..50 for that.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (must NOT pass until payments publishes the seam)
# exceptions: PARTIAL — B5 GT-7 gives no invoice DATES (issued_on stays None; "oldest" is carried as the sequence B5 states) and no within-invoice line split, so the usage+base -> taxes -> fees ordering of BR-PAY-010 is NOT asserted here; B5 routes that to GT-35..50. `credit_carried == 0` is asserted as the absence a partial payment implies, not as a B5 figure.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
