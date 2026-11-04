# ── Trace ──────────────────────────────────────────────
# Epics:    EP-CUS-06 (payment-plan wizard)   Screens: S24
# Rules:    BR-CUS-043 (installment = (total − down) ÷ n, 2dp half-up per
#           installment, remainder absorbed on the FINAL installment — A7
#           EXPLICIT; Σ must equal the total exactly) · BR-RAT-003 / B4.4
#           (half-up, 2dp, at finalization)
# Golden:   GT-47 — PE-13 under B5's own mechanical allocation *"PE-n →
#           GT-(34+n)"* (05-golden-tests.md line 68), ❄️ FROZEN finance-signed
#           2026-08-08 and recomputed by 10-scripts/03-golden-verify.py.
# Tests:    this file
# Impacts:  06-backend/apps/customers/payment_plan.py (the owner)
# ───────────────────────────────────────────────────────
"""GT-47 (PE-13) — 267.30 less 50.00 down over six → 5 × 36.22 + a final 36.20.

PE-13 verbatim (08-payments/07-pre-session-model.md · 04-flows.md §8 · J13)
---------------------------------------------------------------------------
  "PE-13 plan 5×36.22+36.20 + notice cadence"
  "(total − down) ÷ n, 2dp half-up, remainder on FINAL
   (PE-13: 267.30 − 50 over 6 → 5 × 36.22 + 36.20)"

THE HARNESS ALREADY RECOMPUTES THESE TWO FIGURES from the inputs
(`10-scripts/03-golden-verify.py`, "PE-13 inst" / "PE-13 final"). What it cannot
do is check that the PRODUCT reaches them: it is a standalone arithmetic script
over the frozen documents. This file asserts the same two numbers through
`apps.customers.payment_plan.build_schedule`, so the code and the freeze are
tied together rather than merely agreeing by coincidence.

The prototype's own S24 fixture (247.30 over 4 → 61.83 · 61.83 · 61.83 · 61.81)
is asserted here too. It is NOT a B5 figure — it comes from
`05-prototype/UtilityBilling.html` and US-CUS-018 §7 — and it is labelled as
such, because a prototype number and a finance-signed number must never be read
as carrying the same authority.

NOT FROZEN IN PE-13: the DATES. J13 puts the plan's instalments on the 1st of
each month from September; those are fixture scaffolding and no assertion below
depends on them beyond the cadence walk they exercise.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import payment_plan

pytestmark = pytest.mark.golden

# ── INPUT (PE-13 verbatim) ──────────────────────────────────────────────────
PE13_BALANCE = Decimal("267.30")  # "267.30"
PE13_DOWN = Decimal("50")  # "− 50"
PE13_INSTALLMENTS = 6  # "over 6"

# ── EXPECTED (PE-13 verbatim) ───────────────────────────────────────────────
PE13_INSTALLMENT = Decimal("36.22")  # "5 × 36.22"
PE13_FINAL = Decimal("36.20")  # "+ 36.20"

# Fixture scaffolding, NOT a frozen figure (J13's dates).
PE13_FIRST_DUE = date(2026, 10, 1)

# ── The PROTOTYPE's S24 fixture — NOT a B5 figure (US-CUS-018 §7) ───────────
PROTO_BALANCE = Decimal("247.30")
PROTO_INSTALLMENTS = 4
PROTO_SCHEDULE = (Decimal("61.83"), Decimal("61.83"), Decimal("61.83"), Decimal("61.81"))
PROTO_REMAINING = (Decimal("185.47"), Decimal("123.64"), Decimal("61.81"), Decimal("0.00"))


def test_gt47_the_frozen_plan_schedule():
    """5 × 36.22 + 36.20, and Σ equal to the spread to the cent."""
    schedule = payment_plan.build_schedule(
        total=PE13_BALANCE,
        down_payment=PE13_DOWN,
        installments=PE13_INSTALLMENTS,
        cadence=payment_plan.CADENCE_MONTHLY,
        first_due_date=PE13_FIRST_DUE,
    )
    amounts = tuple(row.amount for row in schedule.installments)
    assert amounts == (PE13_INSTALLMENT,) * 5 + (PE13_FINAL,)

    # BR-CUS-043's invariant, stated as arithmetic rather than trusted: the
    # spread is what is scheduled, exactly.
    assert schedule.spread == PE13_BALANCE - PE13_DOWN
    assert sum(amounts, Decimal("0")) == schedule.spread
    assert schedule.installments[-1].remaining == Decimal("0.00")
    assert schedule.installments[-1].final is True

    # The REMAINDER is on the final row and nowhere else — five identical rows
    # and one different one. A schedule that spread the two cents across the
    # earlier instalments would still sum correctly and would break A7.
    assert len(set(amounts[:-1])) == 1
    assert amounts[-1] != amounts[0]


def test_gt47_the_prototype_s24_fixture_matches_to_the_cent():
    """247.30 over 4 → 61.83 / 61.83 / 61.83 / 61.81, remaining to 0.00.

    Prototype-sourced (S24 step 2) and US-CUS-018 §7, NOT a B5 freeze — asserted
    because hard-won law 6 makes the running product's agreement with
    `05-prototype/` something a check has to state, and this is the only screen
    figure in this story that the prototype pins.
    """
    schedule = payment_plan.build_schedule(
        total=PROTO_BALANCE,
        installments=PROTO_INSTALLMENTS,
        cadence=payment_plan.CADENCE_MONTHLY,
        first_due_date=date(2026, 9, 1),
    )
    assert tuple(row.amount for row in schedule.installments) == PROTO_SCHEDULE
    assert tuple(row.remaining for row in schedule.installments) == PROTO_REMAINING
    # The prototype's own dates: Sep 1 / Oct 1 / Nov 1 / Dec 1 2026.
    assert tuple(row.due_date for row in schedule.installments) == (
        date(2026, 9, 1),
        date(2026, 10, 1),
        date(2026, 11, 1),
        date(2026, 12, 1),
    )


def test_gt47_the_down_payment_variant_divides_exactly():
    """US-CUS-018 TC-4: (247.30 − 47.30) ÷ 4 = 50.00 exactly, final 50.00.

    The case with NO remainder, which is what proves the final row carries the
    remainder rather than always carrying something different.
    """
    schedule = payment_plan.build_schedule(
        total=PROTO_BALANCE,
        down_payment=Decimal("47.30"),
        installments=4,
        cadence=payment_plan.CADENCE_MONTHLY,
        first_due_date=date(2026, 9, 1),
    )
    assert tuple(row.amount for row in schedule.installments) == (Decimal("50.00"),) * 4


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-018@bbed56d (05-golden-tests.md + EP-CUS-06-payment-plan.md + 03-customers/02-business-rules.md + J13-payment-plan-life.md)
# generated: 2026-08-11 by story-coder (W4 payment-plan lane — the frozen-figure encoding)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half — S24 is not built) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: the 247.30 / 61.83 / 61.81 fixture is PROTOTYPE-sourced and is
#         labelled as such — it is not in B5 and must not be read as
#         finance-signed. PE-13's DATES are scaffolding (J13's), not frozen.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
