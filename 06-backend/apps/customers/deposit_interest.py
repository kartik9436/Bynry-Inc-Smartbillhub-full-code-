# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-20 · task 30 — "Accrue deposit interest". The CR's own
#           heading: *"blocks closing ANY account that holds a deposit — which
#           is every residential account at a utility that takes deposits. The
#           rate is a confirmed rule and a real setting on a real screen;
#           nothing computes with it."*
# Story:    US-CUS-023 §7 (the accrual engine)   Screens: S21 · S20 · S66
# Rules:    BR-CUS-057 (CONFIRMED — *"tenant-set simple annual rate, default 0%,
#           accrues monthly, pays out at refund/closure; accrual from original
#           receipt date"*) · BR-CUS-050 (the ORIGINAL receipt date) ·
#           BR-CUS-025 (the deposit is a LIABILITY, never revenue) ·
#           BR-TEN-043 / gate G6 (the caller names the day; nothing here reads a
#           clock) · CLAUDE.md rule 2 (money 4dp, percentages 6dp, DISPLAY 2)
# Golden:   ❄️ GT-61 — $150 @ 2.0%, 89 months → **$22.25** (B5, FROZEN) ·
#           WE-7 — $150 @ 2%, 14 months → **$3.50**
# Tests:    06-backend/tests/test_cr059_cs20_deposit_interest.py
# Impacts:  apps/customers/selectors.deposit_interest_accrued (the published
#           name `move_out_settlement` and `billing/final_bill` already resolve)
# ───────────────────────────────────────────────────────
"""What a customer's own deposit has earned — BR-CUS-057, at last computed.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this decides an amount of a customer's
money that goes back to them at closure, so it is enrolled under the CLAUDE.md
sensitive-path protocol. AI-authored 2026-09-03 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

**IT WRITES NOTHING AND IT STORES NOTHING.** The figure is recomputed from the
principal, the rate and the receipt date on every call, so there is no accrued
balance to go stale and no second implementation to disagree with the first.

════════════════════════════════════════════════════════════════════════════
WHAT WAS BLOCKED, AND IT WAS NOT A DISPLAY FIELD
════════════════════════════════════════════════════════════════════════════
`move_out_settlement` has been finished for weeks and **fails CLOSED on this
one term**: `_deposit_interest` resolves `apps.customers.selectors.
deposit_interest_accrued` by name, gets `None`, and the settlement reports
`deposit_interest_not_accrued` and states NO landing. `apps/billing/final_bill.
deposit_credit_for` hits the same wall and takes the same posture deliberately.

So **an account that holds a deposit could not be closed by anybody** — and the
refusal was right. Paying out principal alone is not a workaround: it keeps the
customer's own interest on a bill that foots perfectly, which is the worst shape
an error can take because nothing anywhere reports it.

An account holding NO deposit was never blocked. There is nothing to accrue on,
and both callers answer zero without consulting this engine at all.

════════════════════════════════════════════════════════════════════════════
THE ARITHMETIC, AND THE TWO FROZEN FIGURES IT REPRODUCES
════════════════════════════════════════════════════════════════════════════
BR-CUS-057 is a **simple** annual rate — not compound — accruing **monthly**
from the **original receipt date**:

    interest = principal × (annual rate ÷ 100) × completed months ÷ 12

Both signed figures fall straight out of it and neither needed a rounding
decision, which is itself worth stating:

    ❄️ GT-61   150.00 × 0.02 × 89 ÷ 12  =  22.25   exactly (B5, FROZEN)
       WE-7    150.00 × 0.02 × 14 ÷ 12  =   3.50   exactly

The multiplication is done in ONE Decimal expression and quantised ONCE, at the
end, to money's four places. Rounding the rate, or the monthly amount, before
summing would give a different answer on a long tenancy — the classic
report-that-does-not-foot — and 89 months is long enough for it to show.

**The rate is a PERCENTAGE.** `tenant_settings.deposit_interest_rate_annual` is
`NUMERIC(18,6)` and the Settings screen labels it with a per-cent unit, so 2%
is stored as `2.000000` and the fraction is `rate ÷ 100`. Reading it as a
fraction would pay 0.02% and nobody would notice for a year.

════════════════════════════════════════════════════════════════════════════
"COMPLETED MONTHS" IS A JUDGMENT AND IT IS WRITTEN DOWN (decision log 2026-09-03)
════════════════════════════════════════════════════════════════════════════
BR-CUS-057 says *"accrues monthly"* and no ruling says what a month is when the
receipt date has no counterpart in the month it lands in. This module decides it
rather than asking, because it is ours to decide and a question is the failure to
make the decision (CLAUDE.md law 13) — and it is recorded with its figure:

  * a month completes on the **anniversary DAY** of the receipt date. A deposit
    received on **2 February** is one month old on **2 March** and not on
    1 March;
  * where the month is too short for that day, the month completes on its **last
    day**. A deposit received on **31 January** is one month old on
    **28 February** — never zero months old, which is what a naive day-of-month
    comparison gives and which would silently under-pay every customer who paid
    on a 29th, 30th or 31st, for the rest of their tenancy.

Neither frozen figure exercises the short-month case, which is exactly why the
convention is stated here instead of being inferred from them later.

⚠ **AND THE CLOCK IS THE CALLER'S, WITHOUT EXCEPTION (BR-TEN-043, gate G6).**
`as_of` is REQUIRED and has no default. A settlement re-opened tomorrow must
show the same figure it showed today unless somebody moved the date, and a
`tenant_today()` here would be the wall-clock read in a money path that
`DEF-3205` was filed for one module along. The caller states the day, exactly as
`settlement_for` already makes the caller state the final bill.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

ZERO = Decimal("0")
MONEY_PLACES = Decimal("0.0001")
MONTHS_IN_YEAR = Decimal("12")
PER_CENT = Decimal("100")


def completed_months(received_on: date, as_of: date) -> int:
    """Whole months from the receipt date to `as_of`, on the convention above.

    Never negative: an `as_of` BEFORE the money arrived has accrued nothing, and
    a negative count would pay interest backwards — the customer would owe the
    utility for holding their deposit.
    """
    months = (as_of.year - received_on.year) * 12 + (as_of.month - received_on.month)
    if months <= 0:
        return 0 if months < 0 or as_of.day < received_on.day else months
    # The anniversary day, clamped to the length of the month it lands in. A
    # deposit received on the 31st completes its month on the 28th of February
    # rather than never — see the module docstring for why that is not a detail.
    last_day = calendar.monthrange(as_of.year, as_of.month)[1]
    anniversary = min(received_on.day, last_day)
    if as_of.day < anniversary:
        months -= 1
    return max(months, 0)


def accrued(
    *,
    principal: Decimal,
    annual_rate_percent: Decimal,
    received_on: date,
    as_of: date,
) -> Decimal:
    """BR-CUS-057's figure, from four stated facts. Pure — no database, no clock.

    Exported separately from the account-level read below so the arithmetic can
    be asserted on its own against ❄️ GT-61 and WE-7 without a fixture: a golden
    figure that can only be reached through three joins is a golden figure
    nobody re-checks.
    """
    if principal <= ZERO or annual_rate_percent <= ZERO:
        # A zero rate is the DEFAULT (BR-CUS-057, *"default 0%"*) and is the
        # ordinary case for a utility that pays no interest. It is a real answer
        # of zero, not an absence — the customer is owed their principal back.
        return ZERO
    months = completed_months(received_on, as_of)
    if months == 0:
        return ZERO
    # ONE expression, quantised ONCE. See the docstring: rounding the rate or a
    # monthly amount before summing is what makes a long tenancy not foot.
    exact = (
        Decimal(principal)
        * (Decimal(annual_rate_percent) / PER_CENT)
        * Decimal(months)
        / MONTHS_IN_YEAR
    )
    return exact.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def annual_rate_percent() -> Decimal | None:
    """The tenant's own rate, or None when the settings row cannot be read.

    Resolved BY NAME at call time (B1 / BR-TEN-013): customers never imports
    another module's models. **None is a REPORTED state and never a zero** —
    *"this utility pays no interest"* and *"we could not find out"* are opposite
    answers, and only one of them is safe to settle a closing account on.
    """
    from importlib import import_module

    try:
        selectors = import_module("apps.tenancy.selectors")
    except ImportError:  # pragma: no cover - the tenancy app always imports
        return None
    reader = getattr(selectors, "settings_family", None)
    if not callable(reader):  # pragma: no cover - defensive
        return None
    try:
        # The S66 Billing-defaults page, which is where the rate field lives and
        # has lived since it was built. Read through tenancy's OWN selector and
        # never through its models (B1 / DB-16) — `seams.tenant_currency` takes
        # the same route for the same reason.
        family = reader("billing-defaults")
    except Exception:  # pragma: no cover - an unreadable settings row REPORTS
        return None
    rate = family.get("deposit_interest_rate_annual")
    if rate is None or str(rate).strip() == "":
        return None
    try:
        # Decimals cross that boundary as STRINGS, deliberately, so this is the
        # one place they become numbers again — via `str`, never `float`.
        return Decimal(str(rate))
    except (ArithmeticError, ValueError):  # pragma: no cover - defensive
        return None


def deposit_interest_accrued(account_id: Any, as_of: date | None) -> Decimal | None:
    """**THE PUBLISHED NAME.** BR-CUS-057's accrual for one account.

    `move_out_settlement._deposit_interest` and `billing.final_bill.
    deposit_credit_for` have both resolved this by name for weeks and both have
    been getting `None`; this is the function that was missing.

    Returns `None` — never zero — when the answer cannot be computed truthfully:

      * **no day was stated.** `as_of` has no default and none is invented here:
        gate G6 keeps a clock out of a money path, and a figure accrued to a day
        nobody named is a figure nobody can check. This rule lives HERE and
        nowhere else — `move_out_settlement` forwards `as_of` straight through,
        `None` included, so there is one place it can be read from;
      * the account does not exist for this tenant;
      * it holds a deposit and **no receipt date was ever stamped**, so
        BR-CUS-057's clock has no start. A deposit with no receipt date is a
        register row that predates BR-CUS-050's stamping, and guessing the
        account's opening date instead would be wrong on every such account at
        once — the CR's own ⚠ warning;
      * the tenant's rate could not be read at all.

    Returns **ZERO** — a real answer — when the account holds no deposit, or
    when the utility's rate is 0%, which is the default and the common case.
    """
    from apps.customers import models
    from core import tenancy as core_tenancy

    if as_of is None:
        return None
    account = models.Account.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=account_id
    ).first()
    if account is None:
        return None
    principal = Decimal(account.deposit_on_file or ZERO)
    if principal <= ZERO:
        return ZERO
    received_on = getattr(account, "deposit_received_on", None)
    if received_on is None:
        return None
    rate = annual_rate_percent()
    if rate is None:
        return None
    return accrued(
        principal=principal,
        annual_rate_percent=rate,
        received_on=received_on,
        as_of=as_of,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-20 · §11 task 30 (sources: 12-governance/11-change-requests.md CR-059 §8 CS-20 verbatim · 04-docs/05-modules/03-customers/02-business-rules.md BR-CUS-057 / BR-CUS-050 / BR-CUS-025 · 04-docs/02-decisions/05-golden-tests.md GT-61 · apps/customers/move_out_settlement.py read function by function)
# generated: 2026-09-03 by the CR-059 W6 deposit-interest lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 task 34 owns P9 — S21, S20 step 5 and S66) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the suite will not collect at the pinned tip (`ImportError: cannot import name 'deposit_interest'`) and `move_out_settlement` gaps `deposit_interest_not_accrued` there. Proved on real PostgreSQL (law 14), not the SQLite default.
# exceptions: (1) `as_of` IS REQUIRED AND HAS NO DEFAULT — a `tenant_today()` here would be the wall-clock read in a money path that DEF-3205 was filed for one module along, and a settlement re-opened tomorrow must show today's figure unless somebody moved the date · (2) "COMPLETED MONTHS" IS A JUDGMENT, decided here and recorded in the decision log with its worked figure rather than raised as a question (CLAUDE.md law 13): the anniversary day, clamped to a short month's last day · (3) A DEPOSIT WITH NO RECEIPT DATE ANSWERS None, never a guessed start — the CR's own ⚠ says a single wrong start date is wrong on every account at once · (4) THIS FILE WRITES NOTHING and catches no database error, so no savepoint is involved (law 14) · (5) ❄️ GT-61's 22.25 and WE-7's 3.50 are ASSERTED, never recomputed by the test from this module's own formula
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
