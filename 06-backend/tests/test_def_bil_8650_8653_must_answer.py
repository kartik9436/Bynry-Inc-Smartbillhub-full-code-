# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-8650 (an account whose only open decisions are Standing
#           charges only and/or Gap or overlap was billed with no answer) ·
#           DEF-BIL-8653 (an unanswered No reading ended in two places: a
#           Calculate break and a Pending-billing row)
# Rules:    BR-BIL-1040 / changes row 45 (*"an account is Ready when every
#           problem on it is a warning or has an accepted decision"*) ·
#           PO 2026-08-11 (base-only: opt in or opt out, on screen) ·
#           BR-BIL-015 (no reading: estimate, hold or bill without it)
# Code:     apps/billing/decisions.py (MUST_ANSWER_CASES, apply_decisions) ·
#           apps/billing/check_store.py (_partition_one)
# ───────────────────────────────────────────────────────
"""Every DECISION the Check raises must be answered before Calculate prices the
account — and an account left unanswered ends in exactly ONE place.

RED FIRST: on the tip `base_only_billing` and `billing_continuity` (a gap) were
not must-answer, so `apply_decisions` kept the account in Ready and Calculate
billed it ($63.25 and $8.00 on the J72 walk), and an unanswered `missing_read`
went on to Calculate, broke there and was queued again at Send. Each case here
failed on that behaviour before the fix.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from apps.billing import check_store, decisions, pending, runs, selectors
from apps.billing import models as billing_models

from tests.test_bbr_accuracy_defects import _checked, _priced, _raise
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _with_problem(prepared, account, reason, service_code=None):
    """The prepare pass's own decision record for `account`, as the Check
    would raise it, without building the world that raises it."""
    problem = runs.AccountProblem(
        reason=reason,
        detail=f"{reason} on {account.account_no}",
        account_id=str(account.id),
        account_no=account.account_no,
        service_code=service_code,
    )
    return replace(prepared, decisions=tuple(prepared.decisions) + (problem,))


def _ready_ids(prepared):
    return {str(data.account_id) for data in prepared.ready}


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8650
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-45
@pytest.mark.parametrize("case", ["base_only_billing", "billing_continuity"])
def test_def_bil_8650__an_unanswered_decision_keeps_the_account_out_of_calculate(
    brazos, dana, monkeypatch, case
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        prepared = _with_problem(selectors.prepared_for(run), a101, case)
        assert str(a101.id) in _ready_ids(prepared)
        applied = decisions.apply_decisions(prepared, bill_run=run)
    assert str(a101.id) not in _ready_ids(applied)
    [waiting] = [p for p in applied.decisions if str(p.account_id) == str(a101.id)]
    assert waiting.reason == decisions.DECISION_NEEDED
    assert case in waiting.detail


# BULK-CHG-45
@pytest.mark.parametrize(
    "case, choice",
    [("base_only_billing", decisions.CHOICE_INCLUDE), ("billing_continuity", decisions.CHOICE_BILL_AS_IS)],
)
def test_def_bil_8650__an_answer_lets_it_through(brazos, dana, monkeypatch, case, choice):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        decisions.record_decision(bill_run=run, account_id=str(a101.id), case=case, choice=choice)
        prepared = _with_problem(selectors.prepared_for(run), a101, case)
        applied = decisions.apply_decisions(prepared, bill_run=run)
    assert str(a101.id) in _ready_ids(applied)


# BULK-CHG-37 · A1
@pytest.mark.parametrize("case", ["base_only_billing", "billing_continuity"])
def test_def_bil_8650__price_n_does_not_count_it(brazos, dana, monkeypatch, case):
    """The Check's own partition (Price N, Sign off, Not in this run) agrees
    with Calculate: unanswered is *undecided*, never *priced*."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        _raise(run, a101, case, params={"state": "gap"} if case == "billing_continuity" else None)
        partition = check_store.pricing_partition(run)
    assert partition[str(a101.id)] == check_store.UNDECIDED


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8653
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-40 · A3
def test_def_bil_8653__an_unanswered_no_reading_ends_in_one_place(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        _raise(run, a101, "missing_read", service_code="water")
        prepared = _with_problem(selectors.prepared_for(run), a101, "missing_read", "water")
        applied = decisions.apply_decisions(prepared, bill_run=run)
        assert str(a101.id) not in _ready_ids(applied)
        runs.calculate_run(applied, bill_run=run)
        breaks = billing_models.BillRunBreak.objects.filter(bill_run=run, account_id=a101.id).count()
        pending.queue_not_in_run(bill_run=run)
        queued = billing_models.BillRunExclusion.objects.filter(bill_run=run, account=a101).count()
        invoices = billing_models.Invoice.objects.filter(bill_run=run, account=a101).count()
    assert (breaks, queued, invoices) == (0, 1, 0)


# BULK-CHG-40 · A3
def test_def_bil_8653__an_answered_no_reading_is_priced(brazos, dana, monkeypatch):
    """*Hold* is an answer: the account is held (one place), never undecided."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        decisions.record_decision(
            bill_run=run, account_id=str(a101.id), case="missing_read", choice="hold"
        )
        prepared = _with_problem(selectors.prepared_for(run), a101, "missing_read", "water")
        applied = decisions.apply_decisions(prepared, bill_run=run)
    [row] = [p for p in applied.decisions if str(p.account_id) == str(a101.id)]
    assert row.reason != decisions.DECISION_NEEDED


def test_def_bil_8650__the_priced_helper_still_prices_the_untouched_accounts(
    brazos, dana, monkeypatch
):
    """Nothing about the change holds an account that raised nothing."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        _priced(run)
        drafts = set(
            billing_models.Invoice.objects.filter(bill_run=run).values_list("account__account_no", flat=True)
        )
    assert {"A-00101", "A-00106"} <= drafts
