# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8651 — Paid after cut-off, *Apply to this bill* on a
#           payment still `processing`: the bill printed payments $0.00
# Rules:    BR-BIL-1053 (payments & balances at Check) · BR-PAY-021 (a
#           processing payment meets no bill)
# Code:     apps/billing/decisions.py (accounts_paid_but_not_arrived,
#           record_decision, apply_decisions) · apps/billing/check_store.py ·
#           apps/billing/payments_seam.py · apps/payments/billing_seam.py
# ───────────────────────────────────────────────────────
"""*Apply to this bill* must either apply the payment or be refused.

A bill reads payments only through their allocations, and a `processing`
payment has none (no clearing date: it meets no bill). So for it the choice is
refused when written, and a tag's *Answer for all: Apply to this bill* does not
count as that account's answer — it waits. A cleared payment is applied as
before.

RED FIRST: on the tip the write was accepted and the account priced, so the
bill said *payments received $0.00* — every case below failed there.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import check_store, decisions, runs, selectors
from apps.billing.exceptions import BillingRuleError
from apps.payments import services as payment_services

from tests.test_bbr_accuracy_defects import _checked, _raise
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

POSTED = datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc)


def _paid(dana, account, *, cleared: bool):
    recorded = payment_services.record_payment(
        getattr(dana, "user", dana),
        account_id=account.id,
        amount=Decimal("120.0000"),
        posted_at=POSTED,
        cleared_at=POSTED if cleared else None,
        confirmation=f"T-{account.account_no}-{'c' if cleared else 'p'}",
    )
    return recorded.payment_no


def _with_paid_after_cutoff(run, account, payment_no):
    _raise(run, account, "paid_after_cutoff", params={"payment_no": payment_no, "amount": "120.00"})
    prepared = selectors.prepared_for(run)
    problem = runs.AccountProblem(
        reason="paid_after_cutoff",
        detail=f"paid after cut-off on {account.account_no}",
        account_id=str(account.id),
        account_no=account.account_no,
    )
    return replace(prepared, decisions=tuple(prepared.decisions) + (problem,))


def _ready(prepared):
    return {str(d.account_id) for d in prepared.ready}


# BULK-CHG-37
def test_def_bil_8651__apply_this_bill_on_a_processing_payment_is_refused(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        number = _paid(dana, a101, cleared=False)
        _with_paid_after_cutoff(run, a101, number)
        with pytest.raises(BillingRuleError) as refused:
            decisions.record_decision(
                bill_run=run,
                account_id=str(a101.id),
                case="paid_after_cutoff",
                choice=decisions.CHOICE_APPLY_THIS_BILL,
            )
        # Apply next bill is still an answer.
        decisions.record_decision(
            bill_run=run,
            account_id=str(a101.id),
            case="paid_after_cutoff",
            choice=decisions.CHOICE_APPLY_NEXT_BILL,
        )
    assert refused.value.message_key == "billing.check.paidAfterCutoff.notArrived"


# BULK-CHG-37
def test_def_bil_8651__answer_for_all_does_not_answer_it(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        number = _paid(dana, a101, cleared=False)
        prepared = _with_paid_after_cutoff(run, a101, number)
        decisions.set_standing_answer(
            bill_run=run, case="paid_after_cutoff", choice=decisions.CHOICE_APPLY_THIS_BILL
        )
        applied = decisions.apply_decisions(prepared, bill_run=run)
        partition = check_store.pricing_partition(run)
        status = check_store.account_statuses(run)[str(a101.id)]
    assert str(a101.id) not in _ready(applied)
    assert partition[str(a101.id)] == check_store.UNDECIDED
    assert status == "decision"


# BULK-CHG-37
def test_def_bil_8651__a_cleared_payment_is_applied(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        number = _paid(dana, a101, cleared=True)
        prepared = _with_paid_after_cutoff(run, a101, number)
        decisions.record_decision(
            bill_run=run,
            account_id=str(a101.id),
            case="paid_after_cutoff",
            choice=decisions.CHOICE_APPLY_THIS_BILL,
        )
        applied = decisions.apply_decisions(prepared, bill_run=run)
        partition = check_store.pricing_partition(run)
    assert str(a101.id) in _ready(applied)
    assert partition[str(a101.id)] == check_store.PRICED


def test_def_bil_8651__payments_cannot_answer_fails_closed(brazos, dana, monkeypatch):
    from apps.billing import payments_seam

    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        number = _paid(dana, a101, cleared=True)
        _with_paid_after_cutoff(run, a101, number)
        monkeypatch.setattr(payments_seam, "payment_statuses", lambda *_a, **_k: None)
        assert str(a101.id) in decisions.accounts_paid_but_not_arrived(run)
