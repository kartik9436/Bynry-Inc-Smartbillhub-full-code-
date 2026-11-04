# ── Trace ──────────────────────────────────────────────
# Defect:   `DEF-PAY-6940` — the AR Ageing answers the same figures for every
#           `as_of` it is asked for: it BANDED by `as_of` and aged whatever
#           was outstanding NOW. Found by the Reports dashboard asking it
#           twice while building the period comparison.
#           `DEF-PAY-7020` — what a past-date read still cannot restore.
# Story:    US-REP-005 (AR ageing) · Finance blueprint `P2.21`, p035
# Rules:    `BR-TEN-043` (`as_of` is an ARGUMENT and never a clock) ·
#           `BR-REP-001` (this report is on the POSTING basis) ·
#           `BR-PAY-021` (posting date ≠ clearing date, always both) ·
#           `BR-BIL-004` / hard rule 4 (an issued bill is frozen, which is what
#           makes `issued_at` a sound clock) · `BR-REP-008` (the tie-out) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money) ·
#           hard-won law 7 (a blind spot with no NUMBER beside it is
#           indistinguishable from an empty one)
# ───────────────────────────────────────────────────────
"""Can a finance officer look back at a past month-end? Until now, no.

⚠ **WHAT THE OLD READ DID, AND WHY NOTHING CAUGHT IT.** `ar_aging` took
`as_of` and used it to decide which BAND each open bill fell in — correctly —
but the SET it aged was `status in ('issued','paid')` **as at the moment of
the query**, with every allocation ever written subtracted. So a date a year
earlier aged exactly the same population. Every existing case passes ONE date,
so no test had ever compared two, and a report that ANSWERS is
indistinguishable from one that answers CORRECTLY.

**RED PROVED FIRST, in the harness that runs these** (`pytest`, not
`python3 <file>`). Against the pre-fix seam every case below fails, and the
two that name the defect fail like this::

    test_two_as_at_dates_do_not_answer_the_same_thing
    AssertionError: DEF-PAY-6940: the ageing answered 247.87 at BOTH
    2026-08-20 and 2026-09-20, and a bill issued 2026-09-01 cannot be
    receivable on 2026-08-20
    assert Decimal('247.87') == Decimal('0')

    test_a_payment_posted_after_the_as_at_date_has_not_paid_the_bill
    AssertionError: DEF-PAY-6940: money posted on 2026-09-05 was subtracted
    from the position at 2026-08-31
    assert Decimal('0') == Decimal('247.87')

⚠ **AND THE REGRESSION SIDE IS A FINANCE MATTER, SO IT IS ASSERTED AND NOT
ASSUMED** — `test_a_date_after_everything_is_the_same_figure_it_always_was`
pins the read at a date past every bill and every payment to the whole open
set, which is what a clerk sees on the screen today. Measured on real
PostgreSQL 16 over the sample tenant, before and after: `2026-09-30` →
`total = 9581.530000`, 30 accounts, `1-30 = 8506.800000`,
`31-60 = 1074.730000` — IDENTICAL either side of the fix. What moved is the
PAST: `2025-09-30` and `2024-01-31` went from that same `9581.530000` to
`0`, and `2026-08-31` — a date inside the tenant's own history, where the old
read also said `9581.530000` — now says **`16301.090000` over 45 accounts**,
which is arithmetic anyone can redo by hand (the docstring of
`10-scripts/def_pay_6940_as_at_ageing.py` prints the SQL).
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.payments import models as payment_models
from apps.payments import reporting

from tests.test_us_bil_025_026_bills_read import an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc

#: One bill, issued on the FIRST of September, due at the end of it.
SEPTEMBER_BILL = dict(
    invoice_no="BL-SEP-000001",
    total=Decimal("247.87"),
    subtotal=Decimal("247.87"),
    tax_total=Decimal("0.00"),
    due_date=date(2026, 9, 25),
    issued_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
)
#: One bill, issued on the first of AUGUST, due at the end of it.
AUGUST_BILL = dict(
    invoice_no="BL-AUG-000001",
    total=Decimal("100.00"),
    subtotal=Decimal("100.00"),
    tax_total=Decimal("0.00"),
    due_date=date(2026, 8, 25),
    issued_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
)

BEFORE_SEPTEMBER = date(2026, 8, 20)
AFTER_SEPTEMBER = date(2026, 9, 20)
AUGUST_END = date(2026, 8, 31)


def _totals(tenant, as_of, **query):
    return reporting.ar_aging(as_of=as_of, per=None, **query)["totals"]


def _a_payment(tenant, account, amount, *, no, posted_at):
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=no,
        amount=amount,
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=posted_at,
        cleared_at=posted_at,
    )


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-PAY-6940` — two dates, two answers
# ═══════════════════════════════════════════════════════════════════════════
def test_two_as_at_dates_do_not_answer_the_same_thing(brazos, dana):
    """The register row's own escape_reason, as a case.

    *"Assert TWO as-at dates in one case and require the answers to DIFFER
    where the data says they must. A report parameter that nothing varies is a
    parameter nothing tests."*
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-ASAT-1", label="As-at one")
        an_invoice(brazos, account, **SEPTEMBER_BILL)

        before = _totals(brazos, BEFORE_SEPTEMBER)
        after = _totals(brazos, AFTER_SEPTEMBER)

        assert before["total"] == Decimal("0"), (
            f"DEF-PAY-6940: the ageing answered {before['total']} at both "
            f"{BEFORE_SEPTEMBER} and {AFTER_SEPTEMBER}, and a bill issued "
            f"{SEPTEMBER_BILL['issued_at'].date()} cannot be receivable on {BEFORE_SEPTEMBER}"
        )
        assert before["accounts"] == 0
        assert after["total"] == Decimal("247.87")
        assert after["accounts"] == 1
        assert after["total"] != before["total"]


def test_a_bill_issued_after_the_as_at_date_is_not_in_the_position(brazos, dana):
    """`issued_at` is the clock, and it is a sound one because it is FROZEN.

    `billing/migrations/0002`'s immutability trigger refuses any UPDATE that
    moves `issued_at` once it is set, and treats NULL as *not yet issued* —
    so the column cannot be back-dated after the fact and a past-date read
    built on it cannot be rewritten by anything that happens later.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-ASAT-2", label="As-at two")
        an_invoice(brazos, account, **AUGUST_BILL)
        an_invoice(brazos, account, **SEPTEMBER_BILL)

        august = _totals(brazos, AUGUST_END)
        # August's bill only — 100.00, due 25 August, six days late on the 31st.
        assert august["total"] == Decimal("100.00")
        assert august["1-30"] == Decimal("100.00")
        assert august["accounts"] == 1

        september = _totals(brazos, AFTER_SEPTEMBER)
        assert september["total"] == Decimal("347.87")


# ═══════════════════════════════════════════════════════════════════════════
# `BR-REP-001` / `BR-PAY-021` — the POSTING date, and only the posting date
# ═══════════════════════════════════════════════════════════════════════════
def test_a_payment_posted_after_the_as_at_date_has_not_paid_the_bill(brazos, dana):
    """A bill open at month-end that was settled a week later is OPEN at month-end.

    This is the half of `DEF-PAY-6940` that understates rather than overstates,
    and it is the one an auditor notices: every payment ever received was
    subtracted from every past-date position, so last August's receivable was
    reported net of this September's cash.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-ASAT-3", label="As-at three")
        bill = an_invoice(brazos, account, **AUGUST_BILL)
        payment = _a_payment(
            brazos,
            account,
            Decimal("100.00"),
            no="PMT-ASAT-3",
            posted_at=datetime(2026, 9, 5, 11, 0, tzinfo=UTC),
        )
        payment_models.Allocation.objects.create(
            tenant=brazos, payment=payment, invoice=bill, amount=Decimal("100.00")
        )

        august = _totals(brazos, AUGUST_END)
        assert august["total"] == Decimal("100.00"), (
            "DEF-PAY-6940: money posted on 2026-09-05 was subtracted from the "
            f"position at {AUGUST_END}"
        )
        september = _totals(brazos, AFTER_SEPTEMBER)
        assert september["total"] == Decimal("0")
        assert september["accounts"] == 0


def test_money_posted_late_on_the_closing_day_is_inside_the_closing_day(brazos, dana):
    """`as_of` is a DATE and `posted_at` is a timestamp — the boundary is the DAY.

    A payment taken at the counter at 16:20 on 31 August is August's cash. A
    naive `posted_at <= as_of` comparison puts it in September, which is the
    kind of off-by-one that only ever shows up on a month-end reconciliation.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-ASAT-4", label="As-at four")
        bill = an_invoice(brazos, account, **AUGUST_BILL)
        payment = _a_payment(
            brazos,
            account,
            Decimal("100.00"),
            no="PMT-ASAT-4",
            posted_at=datetime(2026, 8, 31, 16, 20, tzinfo=UTC),
        )
        payment_models.Allocation.objects.create(
            tenant=brazos, payment=payment, invoice=bill, amount=Decimal("100.00")
        )
        assert _totals(brazos, AUGUST_END)["total"] == Decimal("0")
        assert _totals(brazos, date(2026, 8, 30))["total"] == Decimal("100.00")


def test_a_bill_issued_late_on_the_as_at_day_is_inside_that_day(brazos, dana):
    """The same boundary on the other clock — a bill cut at 09:00 on the 31st."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-ASAT-5", label="As-at five")
        an_invoice(
            brazos,
            account,
            **AUGUST_BILL | {"issued_at": datetime(2026, 8, 31, 23, 45, tzinfo=UTC)},
        )
        assert _totals(brazos, AUGUST_END)["total"] == Decimal("100.00")
        assert _totals(brazos, date(2026, 8, 30))["total"] == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# THE REGRESSION SIDE — a finance matter, so it is pinned
# ═══════════════════════════════════════════════════════════════════════════
def test_a_date_after_everything_is_the_same_figure_it_always_was(brazos, dana):
    """What a clerk sees on the screen today does not move.

    Every bill issued and every payment posted before `as_of` means the as-at
    set IS the open set, which is precisely what the old read always returned.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-ASAT-6", label="As-at six")
        bill = an_invoice(brazos, account, **AUGUST_BILL)
        an_invoice(brazos, account, **SEPTEMBER_BILL)
        payment = _a_payment(
            brazos,
            account,
            Decimal("40.00"),
            no="PMT-ASAT-6",
            posted_at=datetime(2026, 9, 5, 11, 0, tzinfo=UTC),
        )
        payment_models.Allocation.objects.create(
            tenant=brazos, payment=payment, invoice=bill, amount=Decimal("40.00")
        )
        # 100.00 − 40.00 + 247.87 = 307.87, over one account, on any date past
        # the last of the five events.
        for as_of in (date(2026, 9, 30), date(2026, 12, 31), date(2027, 6, 30)):
            totals = _totals(brazos, as_of)
            assert totals["total"] == Decimal("307.87"), as_of
            assert totals["accounts"] == 1, as_of


def test_the_tie_out_population_is_struck_at_the_same_date(brazos, dana):
    """`BR-REP-008`'s two sides must be read at ONE date.

    The population is re-derived with every p035 criterion removed, so it is a
    SECOND statement — and a second statement read at today's set while the
    tiles are read at a past one accuses the books of not footing for exactly
    the reason `_aging_population` exists to prevent.
    """
    with tenant_ctx(brazos):
        # ⚠ `contact_name`, not `label` — `customer_name` reads the primary
        # CONTACT, so a name search over an account with none finds nothing and
        # the case would pass on an empty filtered set rather than on the rule.
        account = an_account(
            brazos, dana, account_no="AC-ASAT-7", label="Unit 7", contact_name="Seven Ltd"
        )
        an_invoice(brazos, account, **AUGUST_BILL)
        an_invoice(brazos, account, **SEPTEMBER_BILL)
        body = reporting.ar_aging(as_of=AUGUST_END, per=None, search="Seven")
        assert body["filtered"] is True
        # ⚠ **ASSERTED FIRST, BECAUSE A FILTER THAT MATCHED NOTHING WOULD MAKE
        # EVERY OTHER LINE HERE TRUE OVER AN EMPTY SET** — law 7 habit 2, and
        # the first draft of this case did exactly that.
        assert body["totals"]["accounts"] == 1
        assert body["totals"]["total"] == Decimal("100.00")
        # THE RULE: the population is the SAME date, so it is 100.00 and never
        # 347.87 (which is what today's unfiltered open set comes to).
        assert body["population_total"] == Decimal("100.00")


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-PAY-7020` — the blind spot, WITH ITS NUMBER (hard-won law 7)
# ═══════════════════════════════════════════════════════════════════════════
def test_a_retired_bill_is_counted_and_named_rather_than_silently_dropped(brazos, dana):
    """`invoices` has `issued_at` and no `voided_at`, so this cannot be restored.

    A bill that is `void` or `corrected` TODAY may have been live at `as_of`.
    Nothing records the day it stopped being live, so the read cannot put it
    back — and a silent understatement on a report an auditor reads is the one
    outcome worth refusing. It publishes the COUNT instead.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-ASAT-8", label="As-at eight")
        an_invoice(
            brazos,
            account,
            **AUGUST_BILL | {"status": billing_models.INVOICE_VOID},
        )
        body = reporting.ar_aging(as_of=AUGUST_END, per=None)
        named = [
            problem
            for problem in body["problems"]
            if problem["code"] == "retired_bills_cannot_be_restored_to_a_past_date"
        ]
        assert named, [problem["code"] for problem in body["problems"]]
        assert "1 bill(s)" in named[0]["detail"]
        assert body["totals"]["total"] == Decimal("0")


def test_a_tenant_with_no_retired_bills_is_told_nothing(brazos, dana):
    """A problem row that is always there is a problem row nobody reads."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-ASAT-9", label="As-at nine")
        an_invoice(brazos, account, **AUGUST_BILL)
        body = reporting.ar_aging(as_of=AUGUST_END, per=None)
        assert "retired_bills_cannot_be_restored_to_a_past_date" not in [
            problem["code"] for problem in body["problems"]
        ]
