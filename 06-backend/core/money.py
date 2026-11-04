"""Money type. Hard rule #2: 4-decimal storage + CHAR(3) currency; never float/cents.
Rounding: per line item, half-up, 2dp, at finalization/display ONLY (B4 §Rounding — CONFIRMED).
Implementation lands with the first financial model; rounding constants are HUMAN-OWNED.

⚠ **THE FIRST LINE SAID `NUMERIC(18,6)` UNTIL 2026-09-02, AND THAT PRECISION IS
SUPERSEDED** (`DEF-3228`'s lane, correcting a citation rather than a figure). The
PO re-signed hard rule 2 on 2026-08-22, verbatim: *"We already confirmed this -
MOney 4 decimal, percentage 6 decimal , display both 2 decimal"*. So money is
STORED to **four** decimals and percentages to six, and both DISPLAY two.
Existing `18,6` columns stay lawful containers — the rule governs what is
WRITTEN and what a new column declares (`rating 0013` is that change made:
`charge_code_amounts.amount` became `NUMERIC(18,4)`). **Nothing in this module's
behaviour changed:** `finalize` has always rounded to two places, half-up, and
that is the DISPLAY half of the rule, which the re-sign did not touch.

HUMAN-REVIEW-PENDING — added 2026-08-31 with the PO ruling that put this file
on 10-scripts/gates/human_owned.txt. It has declared HUMAN-OWNED since it was
written and held the other half of the protocol's enrolment marker not at all.
A review record is still owed and is tracked in
12-governance/09-human-review-ledger.md — **written 2026-09-02**, having been
promised on 2026-08-31 and missing until then (`DEF-3228`).
"""

from decimal import ROUND_HALF_UP, Decimal

TWO_DP = Decimal("0.01")


def finalize(amount: Decimal) -> Decimal:
    """Round for invoice-line finalization/display. Do NOT use mid-calculation."""
    return amount.quantize(TWO_DP, rounding=ROUND_HALF_UP)
