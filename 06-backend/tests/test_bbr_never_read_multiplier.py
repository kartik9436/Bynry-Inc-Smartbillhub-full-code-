# ── Trace ──────────────────────────────────────────────
# Change:   changes row 44 (PO 2026-09-30, *"these are correct"*) — "no
#           multiplier → Hold (default) / Bill with multiplier 1" — and rows
#           45–46 (every alternative is a clerk decision with a suggested
#           answer, each in its own tag bucket). Built 2026-10-01.
# Rules:    BR-MET-056 (a read stores the factor USED; a missing factor is
#           never 1) · BR-BIL-1040 as amended (answer per row or for all) ·
#           BR-BIL-870/871 (the ruled path R1–R7; R3 + R4 on by default)
# Plan:     04-docs/05-modules/07-billing/14-bulk-bill-run-changes.md rows 44–46
# ───────────────────────────────────────────────────────
"""A meter that has never been read has no multiplier — and the clerk decides.

**WHAT WAS WRONG.** Metering answers a meter's multiplier from its latest
billable read (`billing_multiplier_for`), so a meter never read has none. The
ruled path's adapter refused that as a BLOCK — *"ruled path refused"*, in the
Pricing-refused bucket with no answer — so the account never reached the
choice the PO ruled: **Hold** (the default) or **Bill with multiplier 1**.

**WHAT IT IS NOW.** Inside the bulk run's Check the refusal is its own decision
tag, `meter_has_no_multiplier` (Meter history), opening on **Hold**. A clerk's
*Bill with multiplier 1* is recorded with who and when like every other answer,
is read by the ruled path's adapter on the next pass (Re-check and Calculate are
both such a pass), and is the only thing that ever puts a 1 there. Outside the
Check (single, first, one-time bill) nobody can answer, so a meter with no
register difference this period is not refused for a factor nothing scales —
and a meter WITH a difference and no factor is refused exactly as before.
"""

from __future__ import annotations

import pytest

from apps.billing import check_store, decisions, gather, runs
from apps.billing import selectors as billing_selectors
from apps.metering import selectors as metering_selectors

from tests.test_bbr_check_engine import PERIOD_END, PERIOD_START, a_cycle
from tests.test_bbr_check_store import a_run, service_id
from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_bil_001_003_run_api import an_actor_user
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CASE = "meter_has_no_multiplier"


def _never_read(brazos, dana):
    """One account whose electric meter has NO read at all."""
    cycle = a_cycle(brazos)
    plan = a_priced_plan(brazos)
    unit = a_billed_unit(
        dana, brazos, cycle, plan, asset_no="M-04401", label="Unit 44", consumption=None
    )
    account = an_account(brazos, unit["id"], "A-00441")
    return cycle, account


def _tag(run, code):
    summary = check_store.findings_summary(run)
    return next(t for c in summary["categories"] for t in c["tags"] if t["code"] == code)


def _codes(run, account):
    found = check_store.account_findings(run, str(account.id))
    return sorted(f["code"] for f in found["findings"])


# BULK-CHG-44
def test_chg44_tc1__a_never_read_meter_is_a_decision_opening_on_hold_not_a_block(brazos, dana):
    """RED BEFORE THE FIX: the account was `ruled_path_refused` (BLOCKS)."""
    with tenant_ctx(brazos):
        cycle, account = _never_read(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)

        codes = _codes(run, account)
        assert CASE in codes, codes
        assert "ruled_path_refused" not in codes
        tag = _tag(run, CASE)
        assert tag["severity"] == "decision"
        assert tag["category"] == "meter_history"
        assert tag["count"] == 1
        assert tag["choices"] == ["hold", "bill_with_multiplier_1"]
        assert tag["default_choice"] == "hold"
        # Nothing is billed on an answer nobody gave.
        assert billing_selectors.prepared_for(run).ready == ()


# BULK-CHG-44
def test_chg44_tc2__bill_with_1_is_recorded_survives_recheck_and_flows_through_calculate(
    brazos, dana
):
    with tenant_ctx(brazos):
        cycle, account = _never_read(brazos, dana)
        run = a_run(cycle)
        clerk = an_actor_user(brazos)
        check_store.check_run(run)

        decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case=CASE,
            choice="bill_with_multiplier_1",
            service_id=service_id("electric"),
            decided_by=clerk,
        )
        # Re-check: the ×1 is read by the adapter, so the gather goes through and
        # the account's NEXT question — no reading — is asked. The multiplier
        # decision STAYS on the account, answered: Re-check does not lose it.
        check_store.check_run(run, only_accounts=[str(account.id)])
        codes = _codes(run, account)
        assert CASE in codes, codes
        assert "missing_read" in codes
        assert "ruled_path_refused" not in codes
        found = check_store.account_findings(run, str(account.id))
        mine = [f for f in found["findings"] if f["code"] == CASE]
        assert len(mine) == 1, mine
        assert mine[0]["answer"] == "bill_with_multiplier_1"
        # …and the answer is still on the record, with who and when.
        report = check_store.check_report(run, {})
        row = next(r for r in report["accounts"]["results"] if r["account_no"] == "A-00441")
        answered = [d for d in row["decisions"] if d["case"] == CASE]
        assert len(answered) == 1, row["decisions"]
        assert answered[0]["choice"] == "bill_with_multiplier_1"
        assert answered[0]["decided_by"]
        assert answered[0]["decided_at"]

        # The clerk bills it without the unread reading; Calculate's pass reads
        # the ×1 too, and the ruled path prices the bill (R3 + R4 served).
        decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="missing_read",
            choice="bill_without_service",
            service_id=service_id("electric"),
            decided_by=clerk,
        )
        prepared = billing_selectors.prepared_for(run)
        [data] = [d for d in prepared.ready if d.account_no == "A-00441"]
        assert {"R3", "R4"} <= set(data.resolution_steps)


# BULK-CHG-44
def test_chg44_tc3__hold_keeps_the_account_out_and_answer_for_all_covers_it(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account = _never_read(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
        decisions.set_standing_answer(bill_run=run, case=CASE, choice="hold")
        assert billing_selectors.prepared_for(run).ready == ()
        check_store.check_run(run, only_accounts=[str(account.id)])
        assert CASE in _codes(run, account), "Hold answers it; it never fixes it"


# BULK-CHG-44
def test_chg44_tc4__outside_the_check_a_read_with_no_factor_is_still_refused(
    brazos, dana, monkeypatch
):
    """The guard is narrowed only where nothing is scaled. A register difference
    with no factor is BR-MET-056's danger — a ×10 register billed at a tenth —
    and the single-bill path, where no clerk can answer, still refuses it."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-04402", label="Unit 45")
        account = an_account(brazos, unit["id"], "A-00442")
        monkeypatch.setattr(metering_selectors, "billing_multiplier_for", lambda *a, **k: None)
        readings, _unmeasured = runs.readings_for_account(
            account,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            scope_services=None,
        )
        assert any(r.consumption is not None for r in readings)
        with pytest.raises(gather.GatherProblem) as refused:
            gather.gather_account(
                account=account,
                service_date=PERIOD_END,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                cycle_days=30,
                readings=readings,
            )
        assert refused.value.reason == "ruled_path_refused"
        assert "NOT 1" in str(refused.value)


def test_chg44_tc5__a_one_is_never_a_default(brazos, dana):
    """Without a recorded ×1 nothing puts a 1 in: the case is not an AUTO case."""
    assert ("meter_has_no_multiplier", "bill_with_multiplier_1") in decisions.APPLIED_CHOICES
    assert decisions.CHECK_CHOICES_BY_CASE[CASE][0] == "hold"
    assert CASE in decisions.MUST_ANSWER_CASES
    # The adapter's DEFAULT is to refuse — the shadow and every caller that
    # names no policy keep BR-MET-056's guard exactly as it was.
    import inspect

    from apps.billing import resolution_shadow

    default = inspect.signature(resolution_shadow.adapt).parameters["unread_factor"].default
    assert default == resolution_shadow.UNREAD_FACTOR_REFUSE
