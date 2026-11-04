# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (Check — a fix is re-checked; TC-6, TC-7, TC-A1)
# Defect:   DEF-BIL-8286 — every check sat in ONE 230-line function, so no
#           category could be called on its own, and a Fix / Re-check re-ran
#           the whole account
# Rules:    BR-BIL-1052 · BR-BIL-1053 · OQ-843 re-ruled (option C)
# Plan:     15-bulk-bill-run-build-plan.md B8, B12, B15, B24 · T1
# ───────────────────────────────────────────────────────
"""The Check's categories behind an ordered registry — written red first.

Red against `c0e8cbbe9` (2.412.1): `check_engine` has no `REGISTRY`, no
`run_category`, no `downstream`; `check_store.check_run` takes no
`categories`; `bill_run_checks` has no per-fact reader. Every existing
`test_bbr_*` test is the no-behaviour-change proof and is not edited.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import check_engine, check_models, check_staleness, check_store, gather, runs
from apps.payments import bill_run_checks
from apps.payments import models as payment_models

from tests.test_bbr_check_engine import (
    BILL_DATE,
    PERIOD_END,
    PERIOD_START,
    three_accounts,
)
from tests.test_bbr_check_store import a_run, checked_at, saved_status
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

DUE_DATE = date(2026, 7, 22)


def a_payment_after_the_cutoff(tenant, account, amount="120.000000"):
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=Decimal(amount),
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc),
    )


def a_context(**extra):
    return check_engine.CheckContext.for_pass(
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        price_date=PERIOD_END,
        cycle_days=30,
        scope_services=None,
        payment_window=extra.get("payment_window", (BILL_DATE, DUE_DATE)),
    )


# ══════════════════════════════════════════════════════════════════════════
# The registry: five categories, in the order `_check_all` ran them
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-22 · BULK-CHG-36
def test_8286__the_registry_runs_five_categories_in_the_old_order():
    assert [c.name for c in check_engine.REGISTRY] == [
        "account",
        "services",
        "decisions",
        "warnings",
        "payments",
    ]
    assert not hasattr(check_engine, "_check_all")


# BULK-CHG-36
def test_8286__a_fix_reruns_its_category_and_what_is_downstream_only():
    down = check_engine.downstream
    assert down(["payments"]) == {"payments"}
    assert down(["services"]) == {"services", "decisions", "warnings"}
    assert down(["account"]) == {"account", "services", "decisions", "warnings"}
    assert check_engine.upstream(["decisions"]) == {"account", "services"}
    assert check_engine.upstream(["payments"]) == frozenset()
    with pytest.raises(ValueError):
        down(["nonsense"])


# ══════════════════════════════════════════════════════════════════════════
# ONE category, called on its own
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-38
def test_8286__the_payments_category_runs_on_its_own_and_reads_no_reading(
    brazos, dana, monkeypatch
):
    """Payments alone: the $120.00 posted Jul 1 on a Jun 1–30 period billed
    Jul 1 is found, and neither the readings seam nor the gather is called."""
    with tenant_ctx(brazos):
        _cycle, _plan, accounts = three_accounts(brazos, dana)
        a_payment_after_the_cutoff(brazos, accounts["A-00106"])
        ctx = a_context()
        ctx.load_payment_facts([accounts["A-00106"]])

        def refuse(*_a, **_k):
            raise AssertionError("the payments category read a reading or gathered")

        monkeypatch.setattr(runs, "readings_for_account", refuse)
        monkeypatch.setattr(gather, "gather_account", refuse)
        checked = check_engine.run_category("payments", accounts["A-00106"], ctx)

    assert [(f.code, f.step) for f in checked.findings] == [("paid_after_cutoff", "payments")]
    assert checked.findings[0].params["amount"] == "120.000000"


# BULK-CHG-22
def test_8286__the_account_category_runs_on_its_own(brazos, dana, monkeypatch):
    """Account-level alone: the readings are read and nothing is gathered."""
    with tenant_ctx(brazos):
        _cycle, _plan, accounts = three_accounts(brazos, dana)
        monkeypatch.setattr(
            gather,
            "gather_account",
            lambda **_k: (_ for _ in ()).throw(AssertionError("gathered")),
        )
        checked = check_engine.run_category("account", accounts["A-00101"], a_context())

    assert checked.findings == []
    assert checked.data is None  # nothing priced: `services` did not run


# ══════════════════════════════════════════════════════════════════════════
# The payments facts: one reader each, the same answer composed
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-38
def test_8286__each_payment_fact_is_its_own_reader_and_the_composition_is_unchanged(brazos, dana):
    from apps.payments.collections_models import AccountCollectionState

    with tenant_ctx(brazos):
        _cycle, _plan, accounts = three_accounts(brazos, dana)
        a_payment_after_the_cutoff(brazos, accounts["A-00106"])
        AccountCollectionState.objects.create(
            tenant=brazos, account=accounts["A-00106"], tier="friendly"
        )
        ids = [a.id for a in accounts.values()]
        alone = bill_run_checks.paid_after_cutoff(ids, period_end=PERIOD_END, bill_date=BILL_DATE)
        composed = bill_run_checks.payment_facts_for_accounts(
            ids, period_end=PERIOD_END, bill_date=BILL_DATE, due_date=DUE_DATE
        )
        # A bill date inside the period has no "after the cut-off".
        none = bill_run_checks.paid_after_cutoff(ids, period_end=PERIOD_END, bill_date=PERIOD_END)

    assert [code for code, _r in bill_run_checks.FACT_READERS] == [
        "paid_after_cutoff",
        "plan_instalment_due",
        "in_collections",
        "autopay_card_expiring",
        # DEF-BIL-8240 (2026-09-30): appended LAST, so the four above keep
        # their order; tests/test_bbr_payment_checks.py proves it.
        "unmatched_payment",
    ]
    assert [(a, c) for a, c, _p in alone] == [(str(accounts["A-00106"].id), "paid_after_cutoff")]
    assert [f["code"] for f in composed[str(accounts["A-00106"].id)]] == [
        "paid_after_cutoff",
        "in_collections",
    ]
    assert none == []


# ══════════════════════════════════════════════════════════════════════════
# Re-check: only the category a change touched, merged into the saved result
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-53 · BULK-CHG-36
def test_8286__a_posted_payment_rechecks_only_payments_and_keeps_the_rest(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
        a106 = accounts["A-00106"]
        before_codes = saved_status(run, a106)[1]
        before = checked_at(run, a106)
        steps = set(
            check_models.BillRunFinding.objects.filter(bill_run=run).values_list(
                "check_step", flat=True
            )
        )
        assert None not in steps  # every saved finding names its category

        time.sleep(0.01)
        a_payment_after_the_cutoff(brazos, a106)
        gathered = []
        real = gather.gather_account
        monkeypatch.setattr(
            gather, "gather_account", lambda **kw: gathered.append(kw["account"]) or real(**kw)
        )
        assert check_staleness.stale_categories(run) == {str(a106.id): frozenset({"payments"})}
        swept = check_staleness.sweep(run)
        status, codes = saved_status(run, a106)

    assert swept == {"stale": 1, "rechecked": 1, "background": False}
    assert gathered == []  # no gather: the payments category only
    assert codes == sorted([*before_codes, "paid_after_cutoff"])
    assert status == "decision"
    assert checked_at(run, a106) > before


# BULK-CHG-36
def test_8286__a_services_recheck_asks_payments_nothing_and_keeps_its_findings(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        a106 = accounts["A-00106"]
        a_payment_after_the_cutoff(brazos, a106)
        run = a_run(cycle)
        check_store.check_run(run)
        assert "paid_after_cutoff" in saved_status(run, a106)[1]

        def refuse(*_a, **_k):
            raise AssertionError("a services re-check asked payments")

        monkeypatch.setattr(bill_run_checks, "payment_facts_for_accounts", refuse)
        check_store.check_run(run, only_accounts=[str(a106.id)], categories=["services"])
        status, codes = saved_status(run, a106)

    assert "paid_after_cutoff" in codes  # the payments row was kept
    assert status == "decision"


# BULK-CHG-36
def test_8286__an_account_saved_before_categories_is_rechecked_in_full(brazos, dana):
    """A row with no category (saved before `billing/0035`) cannot be merged
    into; the store re-checks that account in full rather than guess."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        a101 = accounts["A-00101"]
        run = a_run(cycle)
        check_store.check_run(run)
        row = check_models.BillRunAccountCheck.objects.get(bill_run=run, account_id=a101.id)
        check_models.BillRunFinding.objects.create(
            tenant=brazos,
            bill_run=run,
            account_check=row,
            account_id=a101.id,
            code="unit_has_no_plan",
            category="plans",
            severity="blocks",
            detail="legacy",
        )
        check_store.check_run(run, only_accounts=[str(a101.id)], categories=["payments"])
        status, codes = saved_status(run, a101)

    assert "unit_has_no_plan" not in codes  # the legacy row went with the full pass
    assert status == "ready"
