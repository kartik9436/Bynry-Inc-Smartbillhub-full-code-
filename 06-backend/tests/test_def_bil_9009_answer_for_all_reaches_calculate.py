# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-9009 — an Answer for all saved at Check did not reach
#           Calculate for an account with MORE THAN ONE unread meter
# Story:    US-BIL-037 (bulk Check decisions) · plan B13 · BR-BIL-1040 amended
# Ruling:   PO 2026-09-30 fixed-charge case 1 — *Bill base, usage later*
# Tracker:  BULK-CHG-25 (Answer for all) · BULK-CHG-48 (bill without it)
# ───────────────────────────────────────────────────────
"""A tag's *Answer for all* covers EVERY unread meter of every account on it.

THE DEFECT (found on the 40,015-account close-out walk, 2026-10-01). The clerk
answered *No reading* for all 40,010 accounts with *Bill base, usage later*;
Check counted them Ready (*Price 40,009 accounts*), and Calculate then broke
40,005 of them with *"electric, water still has no usable read and no
decision"*. 4 bills ($32.00) were drafted: the 4 accounts with ONE unread meter.

ROOT CAUSE. The standing answer is saved (`bill_run_standing_answers`) and IS
read: `decisions.apply_decisions` synthesises a decision row for each account
that raised the case. But that synthesised row has no `service_id`, and
`_service_code_for` falls back to *the sole unread service* — so on an account
with two unread meters it answered `None`, nothing was deferred, and the
calculate-time guard found the reads still undecided. Every walk and test
before this one had one unread meter per account.

The fix: a tag-wide answer applies to every unread meter the account has that
no per-meter answer of the clerk's already covers.

RED FIRST: on 2.437.5 the first case fails with the account in
`calculated.breaks` as `missing_read_undecided_at_calculate` and no bill.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import decisions, runs
from apps.billing import models as billing_models

from tests.test_bbr_check_engine import a_cycle
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

BASE = Decimal("18.50")  # `a_priced_plan`'s bound base charge code


def _two_unread_meters(tenant, actor, *, no="9009"):
    """One account, one electric unit, TWO meters, both read in May and neither
    in June — so June's Check raises *No reading* twice on one account."""
    from tests.test_us_met_reads_helpers import a_meter, commit_read

    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    unit = a_billed_unit(
        actor,
        tenant,
        cycle,
        plan,
        asset_no=f"M-{no}",
        label="Unit A",
        consumption=None,
        read_last_month=True,
    )
    second = a_meter(actor, asset_no=f"M-{no}-B", unit_id=unit["id"])
    commit_read(
        actor,
        second["id"],
        day="2026-05-28",
        value="2200",
        prior_value="2000",
        consumption="200.000000",
        unit="kWh",
    )
    account = an_account(tenant, unit["id"], f"A-{no}1")
    return cycle, account


def _run_and_calculate(cycle, account, *, standing=None, per_meter=()):
    run = runs.create_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=SERVICE_DATE,
        label="June · DEF-BIL-9009",
    )
    prepared = runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )
    unread = [
        r
        for d in prepared.ready
        if d.account_id == str(account.id)
        for r in d.readings
        if r.consumption is None
    ]
    if standing:
        decisions.set_standing_answer(bill_run=run, case="missing_read", choice=standing)
    for index, choice in per_meter:
        decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="missing_read",
            choice=choice,
            service_id=unread[index].service_id,
        )
    calculated = runs.calculate_run(decisions.apply_decisions(prepared, bill_run=run), bill_run=run)
    bill = billing_models.Invoice.objects.filter(bill_run=run, account=account).first()
    return unread, calculated, bill


def _reasons(calculated):
    return [b.reason for b in calculated.breaks]


def test_def_bil_9009__answer_for_all_bills_base_only_for_an_account_with_two_unread_meters(
    brazos, dana
):
    with tenant_ctx(brazos):
        cycle, account = _two_unread_meters(brazos, dana)
        unread, calculated, bill = _run_and_calculate(
            cycle, account, standing=decisions.CHOICE_BILL_WITHOUT_SERVICE
        )
        assert len(unread) == 2, "the world must hold two unread meters on one account"
        assert runs.CALC_UNRESOLVED_READ not in _reasons(calculated)
        assert bill is not None, f"no bill; breaks: {_reasons(calculated)}"
        usage = billing_models.InvoiceLine.objects.filter(invoice=bill, kind="usage")
        base = billing_models.InvoiceLine.objects.filter(invoice=bill, kind="base")
        assert usage.count() == 0, "usage waits for the next bill — never a $0.00 usage line"
        assert base.exists()
        assert all(line.amount > 0 for line in base)


def test_def_bil_9009__a_per_meter_answer_wins_and_the_standing_answer_covers_the_rest(
    brazos, dana
):
    """The clerk answered the first meter Hold by hand; the tag says Bill base
    for the rest. ANY hold holds the account (`_is_held`), so the account is
    held — never billed half-decided, and never broken for 'no decision'."""
    with tenant_ctx(brazos):
        cycle, account = _two_unread_meters(brazos, dana, no="9019")
        _unread, calculated, bill = _run_and_calculate(
            cycle,
            account,
            standing=decisions.CHOICE_BILL_WITHOUT_SERVICE,
            per_meter=((0, decisions.CHOICE_HOLD),),
        )
        assert runs.CALC_UNRESOLVED_READ not in _reasons(calculated)
        assert bill is None


def test_def_bil_9009__one_meter_answered_by_hand_the_other_by_the_tag_bills(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account = _two_unread_meters(brazos, dana, no="9029")
        _unread, calculated, bill = _run_and_calculate(
            cycle,
            account,
            standing=decisions.CHOICE_BILL_WITHOUT_SERVICE,
            per_meter=((0, decisions.CHOICE_BILL_WITHOUT_SERVICE),),
        )
        assert runs.CALC_UNRESOLVED_READ not in _reasons(calculated)
        assert bill is not None, f"no bill; breaks: {_reasons(calculated)}"
