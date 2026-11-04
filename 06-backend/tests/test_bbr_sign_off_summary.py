# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-039 TC-1 (accounts reconcile) · TC-2 (units reconcile) ·
#           TC-4 (usage and charges) · TC-5 (payments and balances)
# Rules:    BR-BIL-056/057 · BR-BIL-035 · BR-BIL-1054
# Defect:   DEF-BIL-8220 (no summary read behind Sign off)
# Plan:     15-bulk-bill-run-build-plan.md B19 · A8 · T1, T3 · changes row 37
# ───────────────────────────────────────────────────────
"""Sign off's figures add back to Scope's — written red first.

Red against `c0e8cbbe9`: there is no `apps.billing.signoff` and no
`GET …/sign-off-summary`.

The fixture: three accounts on one cycle; A-00102 BLOCKED (a reading with no
unit and none on its meter), A-00106 LEFT OUT by the clerk, A-00101 priced —
412 kWh of electric on its one draft.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import check_api, check_store, signoff
from apps.billing import models as billing_models

from tests.test_bbr_not_in_run import _checked, _priced
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _summary(brazos, dana, monkeypatch):
    run, accounts = _checked(brazos, dana, monkeypatch)
    check_store.leave_out(run, str(accounts["A-00106"].id))
    _priced(run)
    bill = billing_models.Invoice.objects.get(bill_run=run)
    return run, bill, signoff.sign_off_summary(run)


# BULK-CHG-37 · BULK-CHG-42
def test_8220_tc1_tc2__who_is_billed_adds_back_to_the_accounts_and_units(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        _run, _bill, summary = _summary(brazos, dana, monkeypatch)
    accounts = summary["who_is_billed"]["accounts"]
    units = summary["who_is_billed"]["units"]
    print(f"\nPROOF sign-off accounts {accounts} units {units}")
    assert (accounts["to_bill"], accounts["billed"], accounts["not_billed"]) == (3, 1, 2)
    assert (accounts["regular"], accounts["master"]) == (1, 0)
    assert (accounts["blocked"], accounts["left_out"], accounts["held"]) == (1, 1, 0)
    assert accounts["reconciles"] is True
    assert (units["in_cycle"], units["billed"], units["own_account"]) == (3, 1, 1)
    assert (units["account_not_billed"], units["nobody_to_bill"]) == (2, 0)
    assert units["reconciles"] is True


# BULK-CHG-37
def test_8220_tc4__usage_and_charges_per_service_add_up_to_this_runs_charges(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        _run, bill, summary = _summary(brazos, dana, monkeypatch)
    usage = summary["usage_and_charges"]
    [electric] = usage["services"]
    assert electric["service_code"] == "electric" and electric["bills"] == 1
    assert [(Decimal(u["quantity"]), u["unit"]) for u in electric["usage"]] == [
        (Decimal("412"), "kWh")
    ]
    assert Decimal(usage["this_run_charges"]) == bill.total
    assert Decimal(electric["total"]) == bill.total
    assert usage["reconciles"] is True


# BULK-CHG-37
def test_8220_tc5__payments_and_balances_foot_and_how_it_is_paid_adds_back(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        _run, bill, summary = _summary(brazos, dana, monkeypatch)
    money = summary["payments_and_balances"]
    assert Decimal(money["previous_balance"]) == 0 and Decimal(money["amount_due"]) == bill.total
    assert money["reconciles"] is True
    paid = money["how_paid"]
    assert paid["by_due_date"]["bills"] == 1
    assert sum(Decimal(v["amount"]) for v in paid.values()) == Decimal(money["amount_due"])
    assert summary["run_summary"]["bills"] == 1


# BULK-CHG-37
def test_t3__the_sign_off_summary_route_and_isolation(brazos, lonestar, dana, monkeypatch):
    with tenant_ctx(brazos):
        run, _bill, _summary_now = _summary(brazos, dana, monkeypatch)

    def get(tenant):
        return api_call(
            check_api.run_sign_off_summary,
            "get",
            user=FakeUser(),
            role="executive",
            tenant=tenant,
            run_id=str(run.pk),
        )

    answer = get(brazos)
    assert answer.status_code == 200
    assert answer.data["who_is_billed"]["accounts"]["reconciles"] is True
    assert get(lonestar).status_code == 404


# BULK-CHG-38 · BULK-CHG-37 — DEF-BIL-8242
def test_8242__sign_off_names_each_bill_the_accounts_credit_covers_in_full(
    brazos, dana, monkeypatch
):
    """*Credit covers the bill* (BR-BIL-1053; decision log 2026-09-30, coordinator
    judgement 4): the bill amount exists only after Calculate, so Sign off —
    where the drafts exist — names each drafted bill whose account's credit
    balance covers its total in full. A $500.00 credit against the priced bill."""
    from apps.billing import payments_seam

    # The seam's own type (DEF-BIL-8682: Sign off now carries the position
    # through `open_balance.whole_account`, which reads all of it).
    monkeypatch.setattr(
        payments_seam,
        "prior_position_for_account",
        lambda account_id, **_kw: payments_seam.PriorPosition(
            account_id=str(account_id),
            previous_balance=Decimal("-500"),
            payments_credits=Decimal("0"),
            open_balance=Decimal("-500"),
        ),
    )
    with tenant_ctx(brazos):
        _run, bill, summary = _summary(brazos, dana, monkeypatch)
        account_no = bill.account.account_no
    money = summary["payments_and_balances"]
    print(f"\nPROOF 8242: {money.get('credit_covers_bills')} of {money['how_paid']['credit_covers']}")
    assert money["how_paid"]["credit_covers"]["bills"] == 1
    assert money["credit_covers_bills"]["count"] == 1
    [row] = money["credit_covers_bills"]["results"]
    assert row["account_no"] == account_no
    assert Decimal(row["bill_total"]) == bill.total
    assert Decimal(row["credit"]) == Decimal("500")
    assert Decimal(row["left_after"]) == Decimal("500") - bill.total
