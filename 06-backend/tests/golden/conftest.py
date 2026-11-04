# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core) · EP-BIL-01 (bill run) ·
#           EP-MET-05 (estimation/true-up) · EP-PAY-02 (allocation)
#           Screens: — (pure math; output renders in S31.2/S31.3)
#           No US-ID is cited here for the same reason as the seam module:
#           these files ship no story, they ship B5's frozen expectations.
# Rules:    BR-RAT-003 (round per line, half-up, 2dp, at finalization ONLY) ·
#           BR-RAT-005 (tax base = usage + base) · BR-RAT-006 (exemption is
#           account-level)
# Golden:   GT-1 .. GT-11 — B5 ❄️ FROZEN, finance-signed 2026-08-08.
# Tests:    every test_gt*.py in this directory
# Impacts:  06-backend/apps/billing/rating_seam.py (the interface under test)
# ───────────────────────────────────────────────────────
"""Golden-test fixtures (B5). These are the regression contract for the rating/billing
engine. B5 is FROZEN (finance-signed 2026-08-08): GT-1..61 are the billing-math contract;
expected values change only via finance re-sign (HUMAN-GUIDE section 6), never inline.
Every test is xfail until the engine exists (W3), then MUST pass forever.
Full-composite expectations are machine-verified today by 10-scripts/03-golden-verify.py (33/33).

HOW TO READ THESE FILES
-----------------------
Each test file states, as data, ONE frozen B5 case:

  * INPUT constants — the tariff shape, the consumption with its explicit unit
    (hard rule 3), the period day-counts, the multiplier, the exemption flag.
  * EXPECTED constants — every figure COPIED from B5, with the B5 line it came
    from quoted right above it. Nothing in this directory recomputes, re-rounds
    or "corrects" a frozen figure. If a B5 figure ever looks wrong, it goes to
    finance for re-sign (HUMAN-GUIDE §6) — never to an editor here.
  * A single test that hands the inputs to `apps.billing.rating_seam` and
    asserts the expected outputs.

Where B5 freezes only PART of a case (GT-3's base but not its total, GT-5's
usage but not its tax, GT-9's quantities but not its money), the test asserts
exactly the frozen part and carries a `# NOT FROZEN IN B5:` note naming what is
missing. A gap is recorded, never filled with a guess.

Money is Decimal throughout (`NUMERIC(18,6)`, hard rule 2) — no float appears in
this directory. Every expected amount is written as a Decimal string literal so
the value in the file is byte-for-byte the value in B5.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

requires_engine = pytest.mark.xfail(
    reason="rating engine not implemented (HUMAN-OWNED, B4) - lands W3", strict=False
)

# ── Shared fixture pieces ───────────────────────────────────────────────────

# B5 states no cycle length for the cases that are NOT prorated — what it states
# is that nothing about them is prorated. FULL_PERIOD encodes exactly that:
# service_days == cycle_days, so the B4.3 factor is 1 whatever the length is and
# no cycle length is being invented. Only GT-3 overrides this, with the 15/30
# ratio B5 names explicitly.
FULL_PERIOD = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

# B5 GT-1/GT-10/GT-11 name a single combined rate — "tax 8.25% on (usage+base)"
# (GT-1) and "tax 8.25% x 100.58" (GT-10). B5 does NOT decompose it into
# jurisdictions for these cases, so the fixture carries one rule and the tests
# assert the tax TOTAL. (B4 §Tax lists four component rates and EP-RAT-05
# US-RAT-013 §4 gives a two-jurisdiction split; neither decomposition is frozen
# in B5, so neither is asserted here.)
TAX_8_25 = (rating_seam.TaxRule(code="STATE+LOCAL", rate=Decimal("0.0825")),)

# Currency is the tenant's CHAR(3) (hard rule 2). B5 states USD only in GT-16;
# GT-1..GT-11 carry no currency, and USD here is fixture scaffolding, not a
# frozen figure — no assertion in this directory depends on it.
USD = "USD"

TAXED_ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=False)
EXEMPT_ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=True)


# ── GT-10 / GT-11 shared fixture ────────────────────────────────────────────
# B5 GT-11 line 43: "Input: same as GT-10 but account flagged tax-exempt."
# The two tests therefore share ONE input builder — the sameness is the rule
# under test (B4.2: exemption is account-level and changes nothing else), so it
# is expressed as shared code rather than as two copies that could drift.

# B5 GT-10 line 40: "usage $82.08 + base $18.50 = $100.58 taxable; late fee
# $8.13 NOT taxable". GT-10 states the usage CHARGE, not a rate x quantity, so
# the tariff is expressed with the GT-1 shape that produces it (684 kWh @ 0.12,
# base 18.50 — B5 GT-1 line 11) and the assertions are on the frozen amounts.
GT10_TARIFF = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("18.50"),
    unit_price=Decimal("0.12"),
)
GT10_CONSUMPTION = rating_seam.Quantity(amount=Decimal("684"), unit="kWh")

# B5 GT-10: the late fee is PRESENT on the bill and is NOT taxable. It arrives
# as an input because that is the only way to test B4.2's structural claim —
# hand the engine a fee and watch it stay out of the tax base. 8.13 is GT-8's
# frozen figure (B5 line 34), reused by GT-10 line 40 verbatim.
GT10_LATE_FEE_LINE = rating_seam.RatedLine(
    kind="fee",
    description="Late fee",
    amount=Decimal("8.13"),
    taxable=False,
)

# Shared expectations (identical in both cases — B4.2 changes only the tax).
GT10_EXPECTED_USAGE = Decimal("82.08")  # B5 GT-10 line 40: "usage $82.08"
GT10_EXPECTED_BASE = Decimal("18.50")  # B5 GT-10 line 40: "base $18.50"
GT10_EXPECTED_TAXABLE_SUBTOTAL = Decimal("100.58")  # B5 GT-10 line 40: "= $100.58 taxable"
GT10_EXPECTED_FEE = Decimal("8.13")  # B5 GT-10 line 40: "late fee $8.13 NOT taxable"


def gt10_price(account: rating_seam.AccountContext, taxes: tuple[rating_seam.TaxRule, ...]):
    """Price the shared GT-10 fixture. GT-10 passes the 8.25% rule and a taxed
    account; GT-11 passes the SAME inputs with the account flagged exempt."""
    return rating_seam.price_period(
        tariff=GT10_TARIFF,
        consumption=GT10_CONSUMPTION,
        period=FULL_PERIOD,
        account=account,
        taxes=taxes,
        fees=(GT10_LATE_FEE_LINE,),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of the four frozen sources, in order:
#         04-docs/02-decisions/05-golden-tests.md · 04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — test fixtures) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → 11 xfailed✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: FULL_PERIOD's 30-day length, USD, and GT-8's due/as-of dates are fixture SCAFFOLDING satisfying a condition B5 states in words; each is labeled at its definition and no assertion depends on it. Every asserted figure is copied from B5 with its source line quoted.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
