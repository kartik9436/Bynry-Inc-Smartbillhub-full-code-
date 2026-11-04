# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-9254 — a New Connection's quote (a FEE bill, raised at
#          Create under BR-MET-1187) was read as the account's billed-through
#          date by the cycle run: the continuity check asked a clerk about a
#          false gap/overlap ("billed through 2026-10-03") and the period
#          opening moved the account's first cycle bill to start the day after
#          the quote.
# Rules:   DEF-CUS-6086 (`selectors.last_issued_service_period_end` — a fee
#          bill covers no service period, `NON_SERVICE_BILL_TYPES`) ·
#          DEF-BIL-5270 (the calendar anchor) · PO 2026-09-30 fixed-charge
#          case 4 (the overlap opening)
# Tests:   this file
# Impacts: apps/billing/runs.py · apps/billing/batch_seams.py ·
#          apps/billing/selectors.py
# ───────────────────────────────────────────────────────
"""A fee bill is not a billed-through date — on EVERY read the run makes.

`DEF-CUS-6086` fixed this shape in `selectors.last_issued_service_period_end`
for the move-out cut. The cycle run asked the same question through three
other reads — `runs.last_issued_window` (the register anchor and the Check's
period opening), `runs.period_anchor` (the continuity finding) and the bulk
Check's batch prime of both — and every one of them still counted the fee.

The worked case is the walk's: a master account whose only issued document is
its New Connection quote, dated inside the run's period. Before: the run
opened that account's period the day AFTER the quote and asked a clerk about an
overlap. After: it is the account's first bill, opening on the period's first
day, with no finding.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import batch_seams, models as billing_models, runs
from core import batch_reads

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_001_prepare import (
    PERIOD_START,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_bil_004_run_loop import prepared_for

pytestmark = pytest.mark.django_db

#: The quote's day — inside June, the run's period, as the walk's 2026-10-03
#: quote sat inside October.
QUOTE_DAY = date(2026, 6, 3)


def an_issued(tenant, account, *, start, end, bill_type="cycle"):
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        status=billing_models.INVOICE_ISSUED,
        bill_type=bill_type,
        bill_payload={"services": []},
        period_start=start,
        period_end=end,
        service_date=end,
        currency="USD",
        total=Decimal("75.0000"),
        subtotal=Decimal("75.0000"),
        tax_total=Decimal("0.0000"),
    )


def _continuity(prepared, account_no):
    return [
        p
        for p in prepared.decisions
        if p.reason == "billing_continuity" and p.account_no == account_no
    ]


def test_def_bil_9254_tc1__an_account_whose_only_bill_is_a_fee_is_a_first_bill(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-92541", label="Unit A")
        account = an_account(brazos, unit["id"], "A-92541")
        an_issued(brazos, account, start=QUOTE_DAY, end=QUOTE_DAY, bill_type="fee")

        assert runs.last_issued_window(str(account.id)) is None
        anchor = runs.period_anchor(str(account.id), period_start=PERIOD_START)
        assert anchor.state == runs.CONTINUITY_FIRST_BILL

        prepared = prepared_for(cycle)
        assert _continuity(prepared, "A-92541") == []
        [data] = [d for d in prepared.ready if d.account_no == "A-92541"]
        # Before the fix: 2026-06-04, the day after the quote.
        assert data.period_start == PERIOD_START


def test_def_bil_9254_tc2__a_fee_after_a_cycle_bill_does_not_move_the_anchor(brazos, dana):
    """Billed through 31 May by a cycle bill; a $75 fee on 3 June. The June run
    is CONTINUOUS — the fee covers no service."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-92542", label="Unit A")
        account = an_account(brazos, unit["id"], "A-92542")
        an_issued(brazos, account, start=date(2026, 5, 1), end=date(2026, 5, 31))
        an_issued(brazos, account, start=QUOTE_DAY, end=QUOTE_DAY, bill_type="fee")

        assert runs.last_issued_window(str(account.id)) == (date(2026, 5, 1), date(2026, 5, 31))
        anchor = runs.period_anchor(str(account.id), period_start=PERIOD_START)
        assert anchor.state == runs.CONTINUITY_ALIGNED
        assert anchor.billed_through == date(2026, 5, 31)

        prepared = prepared_for(cycle)
        assert _continuity(prepared, "A-92542") == []


def test_def_bil_9254_tc3__the_bulk_prime_answers_what_the_single_read_answers(brazos, dana):
    """The bulk Check primes these reads in three queries; the primed answer
    must be the per-account read's answer, fee bill skipped."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-92543", label="Unit A")
        account = an_account(brazos, unit["id"], "A-92543")
        an_issued(brazos, account, start=QUOTE_DAY, end=QUOTE_DAY, bill_type="fee")

        from apps.billing import selectors

        key = str(account.id)
        with batch_reads.batch():
            batch_seams.prime_billing_history([account], None)
            # Answered from the PRIME, not from a fresh query — else this case
            # would pass over a prime that disagreed.
            assert batch_reads.is_primed(runs.last_issued_window, key)
            assert batch_reads.is_primed(selectors.last_issued_service_period_end, key)
            assert runs.last_issued_window(key) is None
            assert selectors.last_issued_service_period_end(key) is None
            # The move-out guard's read still sees the fee — that one is about
            # what LEFT THE BUILDING, and a fee did (DEF-CUS-6086).
            assert selectors.last_issued_invoice_period_end(key) == QUOTE_DAY
