# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — totals pass)
#           Screens: — (priced lines render in S31.2)
# Rules:    BR-RAT-005 (tax base = usage + base ONLY; fees/late never taxed) ·
#           BR-RAT-036 (tax forms; no tax-on-tax, no fee taxation) ·
#           BR-RAT-003 (round per line, half-up, 2dp, at finalization)
# Golden:   GT-10 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 39-40). Every figure below is COPIED from those two lines.
# Tests:    this file (xfail until apps.rating.engine.price_period lands)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""GT-10 - usage 82.08 + base 18.50 taxable; late fee 8.13 NOT taxed; tax 8.30 -> total 117.01 (B4.2 CONFIRMED; total re-signed 2026-08-10, DEF-028)

B5 GT-10 verbatim
-----------------
  line 39: "## GT-10 - Tax base excludes fees - CONFIRMED (B4.2)"
  line 40: "Input: usage $82.08 + base $18.50 = $100.58 taxable; late fee $8.13
            NOT taxable; tax 8.25% x 100.58 = 8.30. Total = 100.58 + 8.13 + 8.30
            = **117.01** (fee added after tax). [check] rule confirmed." (re-signed 2026-08-10)

The fee is an INPUT to the totals pass, not something the engine computes — that
is the only way to test B4.2's structural claim: hand the engine a fee that is
sitting on the bill and prove it never enters the tax base. EP-RAT-05
US-RAT-013 TC-1 states the fixture the same way ("late fee 8.13 present").

Shared with GT-11: B5 GT-11 line 43 says "same as GT-10 but account flagged
tax-exempt", so both tests drive ONE input builder in conftest.py. The sameness
IS the rule under test.

NOT FROZEN IN B5: the jurisdiction split behind "8.25%". B5 names one combined
rate for GT-10 and never decomposes it, so the fixture carries one rule and the
assertion is on the tax TOTAL.

    GT-10's TOTAL WAS WRONG IN B5, AND HAS BEEN RE-SIGNED (DEF-028)
    ---------------------------------------------------------------
    B5 line 40 originally read "Total = 100.58 + 8.13 + 8.30 = **116.01**".
    Those addends sum to 117.01 — the stated total contradicted its own stated
    components by exactly 1.00. Three independent cross-checks inside B5 all
    landed on 117.01:
      * GT-10's own addends:            100.58 + 8.13 + 8.30 = 117.01
      * GT-11 ("same as GT-10" without tax) states 108.71;
        adding GT-10's own tax gives    108.71 +        8.30 = 117.01
      * GT-1 prices the identical usage+base+tax at 108.88, and
        108.88 + GT-8's frozen fee 8.13                      = 117.01
    116.01 was reachable only from a fee of 7.13 or a tax of 7.30, and B5
    freezes both elsewhere (GT-8 at 8.13; GT-10 itself computes tax as 8.30).

    Resolved 2026-08-10: the Product Owner, holding finance authority, re-signed
    the line to 117.01 under HUMAN-GUIDE §6. The total is asserted below — which
    is the point of a re-sign. While the figure was in dispute this test could
    not assert it at all, and a figure nothing asserts is a figure nothing
    defends.

    Why it survived the 2026-08-08 freeze: 10-scripts/03-golden-verify.py
    recomputes the WORKBOOK composites (WE/PE/LE -> GT-17..GT-61) and GT-61. It
    does not touch GT-1..GT-16, so no machine had ever added GT-10's three
    numbers together. Extending the verifier over that range is the durable fix
    and is tracked on DEF-028.

    Route: finance re-sign via HUMAN-GUIDE §6. Until then this file carries the
    contradiction in the open rather than resolving it.
"""

from decimal import Decimal

import pytest

from .conftest import (
    GT10_EXPECTED_BASE,
    GT10_EXPECTED_FEE,
    GT10_EXPECTED_TAXABLE_SUBTOTAL,
    GT10_EXPECTED_USAGE,
    TAX_8_25,
    TAXED_ACCOUNT,
    gt10_price,
)

pytestmark = pytest.mark.golden

# ── EXPECTED (B5 GT-10 line 40) ─────────────────────────────────────────────
# Inputs live in conftest.py (shared with GT-11 — B5 line 43 "same as GT-10").
EXPECTED_USAGE = GT10_EXPECTED_USAGE  # "usage $82.08"
EXPECTED_BASE = GT10_EXPECTED_BASE  # "base $18.50"
EXPECTED_TAXABLE_SUBTOTAL = GT10_EXPECTED_TAXABLE_SUBTOTAL  # "= $100.58 taxable"
EXPECTED_FEE = GT10_EXPECTED_FEE  # "late fee $8.13 NOT taxable"
EXPECTED_TAX = Decimal("8.30")  # "tax 8.25% x 100.58 = 8.30"

# RESOLVED 2026-08-10 — finance re-sign under HUMAN-GUIDE §6 (DEF-028). B5's
# GT-10 stated 116.01 against its own addends of 100.58 + 8.13 + 8.30; the PO,
# holding finance authority, re-signed the line to 117.01. The total is
# therefore asserted now, which is the whole point of the re-sign: a figure
# nobody could assert was a figure nothing defended.
EXPECTED_TOTAL = Decimal("117.01")  # B5 line 40, re-signed 2026-08-10


def test_gt10_tax_base():
    # Rule CONFIRMED by finance (B4, 2026-08-07). Becomes a hard regression gate
    # the moment apps/rating/engine.py exists. Expected values: B5 GT-10.
    bill = gt10_price(account=TAXED_ACCOUNT, taxes=TAX_8_25)

    usage = bill.sole_line("usage")
    assert usage.amount == EXPECTED_USAGE
    assert usage.taxable is True  # "usage $82.08 ... taxable"

    base = bill.sole_line("base")
    assert base.amount == EXPECTED_BASE
    assert base.taxable is True  # "+ base $18.50 ... taxable"

    fee = bill.sole_line("fee")
    assert fee.amount == EXPECTED_FEE
    assert fee.taxable is False  # "late fee $8.13 NOT taxable"

    # B4.2: the base the percent tax is applied to is usage + base ONLY. The fee
    # is on the bill and must not be in this number.
    assert bill.taxable_subtotal == EXPECTED_TAXABLE_SUBTOTAL
    assert bill.tax_total == EXPECTED_TAX
    assert bill.fee_total == EXPECTED_FEE

    # The total is B5's re-signed figure (117.01), and it ties out to the
    # components asserted above rather than being an independent claim:
    #   taxable subtotal 100.58 + tax 8.30 + fee 8.13 = 117.01
    assert bill.total == EXPECTED_TOTAL
    assert EXPECTED_TAXABLE_SUBTOTAL + EXPECTED_TAX + EXPECTED_FEE == EXPECTED_TOTAL

    # "(fee added after tax)" — the ORDERING claim of GT-10 is still asserted:
    # the fee sits outside the taxed base, so removing it from the bill total
    # leaves exactly the taxed part, whatever the total's final signed value is.
    assert bill.total - bill.fee_total == EXPECTED_TAXABLE_SUBTOTAL + EXPECTED_TAX

    # NOT FROZEN IN B5: the jurisdiction split behind 8.25%. Only the tax TOTAL
    # is asserted — see the module docstring.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (must NOT pass until the engine lands)
# exceptions: ⚠️ B5-INTERNAL-INCONSISTENCY — B5 line 40's stated total 116.01 contradicts its own stated addends (100.58 + 8.13 + 8.30 = 117.01) by exactly 1.00; GT-11 and GT-1 both independently cross-check to 117.01. REPORTED for finance re-sign (HUMAN-GUIDE §6), NOT corrected; `bill.total` is therefore not asserted and both numbers are recorded in the file. The escape: 10-scripts/03-golden-verify.py covers the workbook composites (GT-17..GT-61) and never adds GT-1..GT-16's figures. · B5 GT-10 states the usage CHARGE (82.08) rather than a rate x quantity; the shared fixture uses the GT-1 tariff shape that produces it (684 kWh @ 0.12, base 18.50 — B5 line 11). · The 8.25% is carried as ONE rule because B5 does not decompose it for GT-10; only the tax total is asserted.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
