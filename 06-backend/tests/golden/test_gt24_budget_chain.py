# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-05 (budget billing — level-pay)
#           Screens: S30 (Budget Bills tab)
# Rules:    BR-BIL-017 (level = trailing-12-month average, whole $; variance on
#           every bill; annual settle-up) · BR-BIL-011 (the monthly posting is
#           the ACTUALS posting — the level is never a price) · B4.2 (the
#           settle-up line is non-taxable AR-timing) · BR-RAT-003 (finalized
#           half-up 2dp, once)
# Golden:   GT-24 — WE-8 under B5's own mechanical allocation *"WE-n →
#           GT-(16+n)"* (05-golden-tests.md line 68), ❄️ FROZEN finance-signed
#           2026-08-08.
# Tests:    this file
# Impacts:  06-backend/apps/billing/budget.py (the owner of this arithmetic)
# ───────────────────────────────────────────────────────
"""GT-24 (WE-8) — level $242, and the frozen variance chain −50.87 → −40.27 → +2.98.

WE-8 verbatim (04-docs/05-modules/07-billing/08-worked-examples.md)
-------------------------------------------------------------------
  "Trailing-12 actuals $2,904 → level **$242**. July actual 292.87 → variance
   −50.87 · Aug actual 231.40 → +10.60 · Sep actual 198.75 → +43.25; running
   balance −50.87 → −40.27 → **+2.98** (bill shows all three columns).
   Settle-up month: balance collected/credited as a **non-taxable AR-timing
   line** — revenue and tax were already recognized on the monthly actuals; the
   level payment is a collection schedule, never a price. *(BR-BIL-017)*"

WHY THIS FILE EXISTS RATHER THAN A LINE IN THE HARNESS. GT-24 is inside B5's
frozen range by the mechanical WE-n → GT-(16+n) allocation, and
`10-scripts/03-golden-verify.py` does NOT recompute it — it checks WE-7, WE-9
and WE-16 from the workbook and skips WE-8. So the frozen chain had no executing
guard at all until this file. The harness count is untouched (33) on purpose:
adding a check there would change a number the whole repo quotes, and this
lane's job is to make the figures bite in the product's own suite.

NOT FROZEN IN WE-8: the settle-up MONTH (BR-BIL-017 makes it a tenant setting
and ratifies no month) and the AMOUNT DUE. The amount due is the PO's ruling of
2026-08-11 — *"Level is due"* — and it is asserted in
tests/test_us_bil_019_budget_bill.py against that ruling, not here against B5.
"""

from decimal import Decimal

import pytest

from apps.billing import budget

pytestmark = pytest.mark.golden

# ── INPUT (WE-8 verbatim) ───────────────────────────────────────────────────
TRAILING_12_TOTAL = Decimal("2904")  # "Trailing-12 actuals $2,904"
MONTHS = 12  # "trailing-12"
JULY_ACTUAL = Decimal("292.87")  # "July actual 292.87"
AUGUST_ACTUAL = Decimal("231.40")  # "Aug actual 231.40"
SEPTEMBER_ACTUAL = Decimal("198.75")  # "Sep actual 198.75"

# ── EXPECTED (WE-8 verbatim) ────────────────────────────────────────────────
EXPECTED_LEVEL = Decimal("242")  # "→ level **$242**"
EXPECTED_MOVEMENTS = (Decimal("-50.87"), Decimal("10.60"), Decimal("43.25"))
EXPECTED_RUNNING = (Decimal("-50.87"), Decimal("-40.27"), Decimal("2.98"))


def test_gt24_the_level_is_the_trailing_twelve_average_in_whole_dollars():
    """ "$2,904 ÷ 12 → $242" — computed from the input, never copied."""
    level = budget.compute_level(
        trailing_actuals=(TRAILING_12_TOTAL,),
        months=MONTHS,
        rounding=budget.ROUNDING_WHOLE_DOLLAR,
    )
    assert level == EXPECTED_LEVEL
    # The DIVISION is what is frozen, so the test states it as one: a level
    # asserted only as "242" would still pass if the divisor became 11.
    assert level * MONTHS == TRAILING_12_TOTAL


def test_gt24_the_variance_chain_lands_exactly_on_the_frozen_figures():
    """−50.87 → −40.27 → +2.98, month by month, from the actuals."""
    actuals = (JULY_ACTUAL, AUGUST_ACTUAL, SEPTEMBER_ACTUAL)

    movements = tuple(
        budget.variance_movement(level=EXPECTED_LEVEL, actual=actual) for actual in actuals
    )
    assert movements == EXPECTED_MOVEMENTS

    balance = Decimal("0")
    running = []
    for actual in actuals:
        balance = budget.running_balance(opening=balance, level=EXPECTED_LEVEL, actual=actual)
        running.append(balance)
    assert tuple(running) == EXPECTED_RUNNING

    # WE-8's own arithmetic identity, asserted rather than assumed: the closing
    # balance is the levels charged less the actuals recognised. If those two
    # ever disagree, revenue and collections have diverged.
    assert running[-1] == (EXPECTED_LEVEL * 3) - sum(actuals, Decimal("0"))


def test_gt24_the_settle_up_credits_the_positive_balance_and_is_never_taxable():
    """ "balance collected/credited as a non-taxable AR-timing line."

    +2.98 means the levels collected MORE than the customer used, so the utility
    owes them: a CREDIT of 2.98. Taxability is asserted because WE-8 states it
    in the same sentence — revenue and tax recognised monthly on the actuals, so
    taxing this line taxes the same money twice.
    """
    settlement = budget.settle_up(balance=EXPECTED_RUNNING[-1])
    assert settlement is not None
    assert (settlement.direction, settlement.amount) == (budget.SETTLE_CREDIT, Decimal("2.98"))
    assert settlement.taxable is False

    # The opposite sign, same line class (US-BIL-019 TC-4's fixture): the
    # mid-chain −40.27 collects.
    owing = budget.settle_up(balance=EXPECTED_RUNNING[1])
    assert (owing.direction, owing.amount) == (budget.SETTLE_COLLECT, Decimal("40.27"))
    assert owing.taxable is False


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-019@e9d5a48 (05-golden-tests.md + 07-billing/08-worked-examples.md + EP-BIL-05-budget-billing.md + 07-billing/02-business-rules.md)
# generated: 2026-08-11 by story-coder (W4 budget-billing lane — the frozen-figure encoding)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) `10-scripts/03-golden-verify.py` does NOT check WE-8/GT-24 —
#         it recomputes WE-7, WE-9 and WE-16 and skips this one — so the frozen
#         chain had no executing guard before this file. The harness count is
#         deliberately left at 33: changing a number the whole repo quotes is a
#         process event, and REPORTED as such rather than done here.
#         (2) The AMOUNT DUE is not asserted here. WE-8 froze the chain, not
#         what the customer owes; that is the PO's ruling of 2026-08-11 and its
#         home is tests/test_us_bil_019_budget_bill.py.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
