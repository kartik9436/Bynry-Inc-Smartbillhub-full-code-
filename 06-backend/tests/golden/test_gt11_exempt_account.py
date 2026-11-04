# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — totals pass)
#           Screens: — (priced lines render in S31.2)
# Rules:    BR-RAT-006 (exemption is ACCOUNT-level: tax = 0 regardless of
#           service) · BR-RAT-005 (tax base = usage + base only) ·
#           BR-CUS-063 (exemption = flag + certificate ref + expiry)
# Golden:   GT-11 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 42-43). Every figure below is COPIED from those two lines.
# Tests:    this file (xfail until apps.rating.engine.price_period lands)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""GT-11 - same as GT-10, account tax_exempt -> tax 0, total 108.71; account-level exemption (B4.2 CONFIRMED)

B5 GT-11 verbatim
-----------------
  line 42: "## GT-11 - Exempt account - CONFIRMED account-level (B4.2)"
  line 43: "Input: same as GT-10 but account flagged tax-exempt. Tax = 0
            regardless of service. Total = 100.58 + 8.13 = **108.71**.
            [check] rule confirmed."

"same as GT-10" is honoured literally: this test and GT-10 drive ONE input
builder (conftest.gt10_price) and differ in exactly two arguments — the account
flag and the tax rules. The whole content of B4.2's exemption rule is that
nothing ELSE may differ, so the fixture is shared rather than copied.

Note the direction of the rule: exemption is decided at the ACCOUNT, not per
service. B4 is explicit that "when an account qualifies for exemption it is
exempt regardless of service; exemption is NOT decided per service type" — which
is why the flag lives on AccountContext and there is no per-service exemption
input anywhere in the seam to get this wrong with.

NOT FROZEN IN B5: the certificate reference and its expiry (BR-CUS-063 rules
them; GT-11 exercises neither), and the jurisdiction split behind 8.25%.

GT-11's own total IS internally consistent (100.58 + 8.13 = 108.71) and is
asserted below. Its twin is not: see the ⚠️ B5-INTERNAL-INCONSISTENCY block in
test_gt10_tax_base.py, where B5's stated total contradicts its own addends.
GT-11 is in fact one of the three cross-checks that exposes it — 108.71 plus
GT-10's own tax of 8.30 is 117.01, not the 116.01 B5 signs for GT-10.
"""

from decimal import Decimal

import pytest

from .conftest import (
    EXEMPT_ACCOUNT,
    GT10_EXPECTED_BASE,
    GT10_EXPECTED_FEE,
    GT10_EXPECTED_TAXABLE_SUBTOTAL,
    GT10_EXPECTED_USAGE,
    TAX_8_25,
    gt10_price,
)

pytestmark = pytest.mark.golden

# ── EXPECTED (B5 GT-11 line 43, on the GT-10 inputs of line 40) ─────────────
EXPECTED_USAGE = GT10_EXPECTED_USAGE  # unchanged from GT-10: "usage $82.08"
EXPECTED_BASE = GT10_EXPECTED_BASE  # unchanged from GT-10: "base $18.50"
EXPECTED_TAXABLE_SUBTOTAL = GT10_EXPECTED_TAXABLE_SUBTOTAL  # "100.58 + ..."
EXPECTED_FEE = GT10_EXPECTED_FEE  # "... + 8.13"
EXPECTED_TAX = Decimal("0")  # "Tax = 0 regardless of service"
EXPECTED_TOTAL = Decimal("108.71")  # "= 100.58 + 8.13 = **108.71**"


def test_gt11_exempt_account():
    # Rule CONFIRMED by finance (B4, 2026-08-07). Becomes a hard regression gate
    # the moment apps/rating/engine.py exists. Expected values: B5 GT-11.
    #
    # Identical inputs to GT-10 except the account flag. The tax RULES are still
    # supplied — the exemption must zero a tax that would otherwise apply, which
    # is a stronger assertion than simply passing no rules.
    bill = gt10_price(account=EXEMPT_ACCOUNT, taxes=TAX_8_25)

    # "same as GT-10": the priced lines are untouched by the exemption.
    assert bill.sole_line("usage").amount == EXPECTED_USAGE
    assert bill.sole_line("base").amount == EXPECTED_BASE
    assert bill.taxable_subtotal == EXPECTED_TAXABLE_SUBTOTAL
    assert bill.sole_line("fee").amount == EXPECTED_FEE
    assert bill.fee_total == EXPECTED_FEE

    # "Tax = 0 regardless of service" — B4.2, account-level.
    assert bill.tax_total == EXPECTED_TAX
    assert bill.lines_of("tax") == () or all(
        line.amount == Decimal("0") for line in bill.lines_of("tax")
    )

    # "Total = 100.58 + 8.13 = 108.71"
    assert bill.total == EXPECTED_TOTAL

    # NOT FROZEN IN B5: certificate ref / expiry handling (BR-CUS-063), and the
    # jurisdiction split behind 8.25%. Deliberately unasserted.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (must NOT pass until the engine lands)
# exceptions: GT-11 shares GT-10's input builder verbatim ("same as GT-10", B5 line 43) and differs in the account flag only. Tax rules are still passed so the exemption must ZERO a live tax rather than merely inheriting an absent one. The tax-LINE shape (no lines vs zero-valued lines) is not ruled on by B5, so either is accepted.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
