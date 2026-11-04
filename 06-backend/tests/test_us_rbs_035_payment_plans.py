# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-035 (EP-RBS-05) — CR-075 wave R′, runbook 25.
# Rules:    BR-RBS-004 · BR-RBS-010 · BR-RBS-012 · BR-RBS-014 · BR-RBS-020 ·
#           BR-RBS-021 · BR-RBS-023 · BR-RBS-035 · BR-PAY-016 · BR-PAY-021 ·
#           CLAUDE.md hard rule 2 · B14 rules 31, 32
# Tests:    this file.
# Impacts:  apps/runbooks/definitions/payment_plans.py
# ───────────────────────────────────────────────────────
"""Runbook 25, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED, AND ONE CASE CAN BE PROVED NOWHERE ELSE.** The
seeded tenant carries exactly ONE payment plan and every account on it is
`is_sample=True`, so a plan **in good standing beside one being warned beside one
due to end** cannot be produced with real data. It is exercised here; what the
real tenant produces is in the lane report beside it, and neither is quoted
alone.

⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY** (hard-won law 7, habit 2):

* **Only one plan in the fixture.** A single plan at two misses is warned and
  ended whether the limit is read from Settings or hard-coded, so the default
  state carries THREE plans — 0, 1 and 2 misses — and every case asserts all
  three outcomes at once. That is what makes a build with the limit inlined go
  red.
* **Asserting `to_void` without asserting the run wrote nothing.** The void is
  the absence this runbook is built around, so the case asserts BOTH that the
  plan reaches `to_void` AND that no port was reached for it.
* **A miss counted from a CLEARING date.** `BR-PAY-021` is `posted_at ≤ due
  date`, and the fixture's *paid* instalment carries a posting date, so a build
  that read a clearing date would find the seam key absent rather than pass.
"""

import datetime as dt

import pytest
from django.utils import timezone

from apps.runbooks import models
from apps.runbooks.contract import BLOCK_TYPES, validate_report
from apps.runbooks.definitions import payment_plans as pp
from apps.runbooks.engine import executor
from core import tenancy as core_tenancy
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)

#: Real UUIDs, because `acts.plan()` writes a `runbook_run_records` row whose
#: `subject_id` is a `UUIDField` and whose `run_id` is NOT NULL. See
#: `test_us_rbs_027_deposit_review.py` for why a missing run row is a FALSE PASS
#: rather than a crash: every INSERT raises, `plan()` reads that as *already
#: done*, and the assertions hold their shape while proving the opposite.
CURRENT = "8b1d6c0e-0000-4000-8000-00000000aa01"
BEHIND = "8b1d6c0e-0000-4000-8000-00000000aa02"
ENDING = "8b1d6c0e-0000-4000-8000-00000000aa03"


def _plan_row(account_id, account_no, misses, missed_value="131.5000"):
    return {
        "plan_id": f"plan-{account_no}",
        "account_id": account_id,
        "account_no": account_no,
        "label": account_no,
        "status": "active",
        "currency": "USD",
        "total_amount": "657.4700",
        "installment_count": 4,
        "instalments_met": 4 - misses,
        "misses": misses,
        "missed_value": missed_value if misses else "0.0000",
        "earliest_missed_on": "2026-08-17" if misses else None,
        "next_due_on": None if misses >= 2 else "2026-09-14",
        "suspend_disconnect": True,
    }


@pytest.fixture()
def run_row(brazos):
    runbook = models.Runbook.objects.create(
        tenant=brazos,
        key=pp.RUNBOOK_KEY,
        name=pp.RUNBOOK.name,
        kind=pp.RUNBOOK.kind,
        category=pp.RUNBOOK.category,
        subject_type=pp.RUNBOOK.subject_type,
        unit_of_work=pp.RUNBOOK.unit_of_work,
    )
    return models.RunbookRun.objects.create(
        tenant=brazos,
        runbook=runbook,
        version=1,
        mode=models.MODE_DRY,
        status=models.RUN_STATUS_RUNNING,
        started_at=timezone.now(),
    )


@pytest.fixture
def seams(monkeypatch):
    """Three plans — in good standing, one miss, two misses — and the settings.

    THREE rather than one, deliberately: a single plan at the limit is ended
    whether the limit is read or inlined, so the fixture would be green on a
    build that never asked Settings anything.
    """
    state = {
        "plans": [
            _plan_row(CURRENT, "AC-2026-00001", 0),
            _plan_row(BEHIND, "AC-2026-00002", 1),
            _plan_row(ENDING, "AC-2026-00003", 2, "262.9800"),
        ],
        "settings": {
            "readable": True,
            "reminder_days_before": 3,
            "missed_notice_days_after": 1,
            "void_after_misses": 2,
            "returns_before_privilege_lost": 2,
        },
        "samples": frozenset(),
        "disputes": frozenset(),
    }
    monkeypatch.setattr(
        pp.payments_seam,
        "plans_in_flight",
        lambda *, as_of, grace_days=0: {
            "rows": list(state["plans"]),
            "plans_in_total": len(state["plans"]),
            "grace_days": grace_days,
            "as_of": as_of.isoformat(),
        },
    )
    monkeypatch.setattr(
        pp.payments_seam, "plan_notice_settings", lambda: dict(state["settings"])
    )
    monkeypatch.setattr(
        pp.customers_seam, "sample_account_ids", lambda: frozenset(state["samples"])
    )
    monkeypatch.setattr(
        pp.customers_seam,
        "account_anchors",
        lambda: [
            {
                "id": one["account_id"],
                "account_no": one["account_no"],
                "kind": "regular",
                "unit_id": f"unit-{one['account_no']}",
                "premises_id": None,
            }
            for one in state["plans"]
        ],
    )
    monkeypatch.setattr(
        pp.metering_seam,
        "unit_has_dispute_hold",
        lambda unit_id: unit_id in state["disputes"],
    )
    return state


def _run(run_row, params=None):
    ctx = executor.build_context(
        pp.RUNBOOK,
        tenant_id=run_row.tenant_id,
        run_id=run_row.pk,
        params={"as_of": TODAY.isoformat(), **(params or {})},
    )
    # ⚠ **THE GUC, NOT ONLY `ctx.tenant_id`.** The engine writes an audit row
    # for every act (hard rule 7) and `core.audit` refuses an orphaned one by
    # name — *"no tenant context set for audit row 'runbook.port_write'"*
    # (`BR-AUD-007`). A context object carrying a tenant id is not the same
    # thing as `app.tenant_id` being SET, and hard rule 1 is about the second.
    with core_tenancy.tenant_context(run_row.tenant_id):
        return executor.execute(pp.RUNBOOK, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _outcomes(result, step):
    return {
        one.subject.label: one.outcome for one in result.records if one.step_key == step
    }


# ── the day is an argument, never a clock (BR-TEN-043 / G6) ───────────────


def test_a_run_with_no_business_day_refuses_and_says_why(seams, run_row):
    with pytest.raises(ValueError) as caught:
        executor.execute(pp.RUNBOOK, tenant_id=run_row.tenant_id, params={})
    assert "never a clock read" in str(caught.value)


# ── TC-RBS-035.1 · warned and ended, each naming its rule in words ────────


def test_one_miss_is_warned_and_the_limit_ends_the_plan(seams, run_row):
    result = _run(run_row)
    warned = _outcomes(result, pp.STEP_WARN)
    assert warned["AC-2026-00001"] == pp.OUTCOME_CURRENT
    # `planned`, not `warned` — the port has no writer and a dry run must not
    # read like a live one (wave M's whole soak is about that difference).
    assert warned["AC-2026-00002"] == "planned"
    assert warned["AC-2026-00003"] == "planned"
    ended = _outcomes(result, pp.STEP_VOID)
    assert ended["AC-2026-00003"] == pp.OUTCOME_TO_VOID
    assert ended["AC-2026-00002"] == pp.OUTCOME_SKIPPED


def test_every_row_names_its_rule_in_words_with_no_rule_id(seams, run_row):
    """`BR-RBS-010` and B14 rule 32 in one case: a void with no stated rule is
    `TC-RBS-035.1`'s own *must first fail on*."""
    for record in _run(run_row).records:
        assert record.reason.strip()
        assert record.decided_by_rule.strip()
        assert "BR-" not in record.decided_by_rule
        assert "OQ-" not in record.decided_by_rule


def test_the_limit_is_read_from_settings_and_not_inlined(seams, run_row):
    """Move the tenant's limit to three and the plan at two misses is WARNED
    rather than ended. A build carrying `BR-PAY-016`'s default in code stays on
    two and goes red here."""
    seams["settings"]["void_after_misses"] = 3
    result = _run(run_row)
    assert _outcomes(result, pp.STEP_VOID) == {
        "AC-2026-00001": pp.OUTCOME_SKIPPED,
        "AC-2026-00002": pp.OUTCOME_SKIPPED,
        "AC-2026-00003": pp.OUTCOME_SKIPPED,
    }
    assert result.set_results[pp.STEP_COUNT]["to_warn"] == 2


def test_an_unreadable_setting_warns_and_ends_nothing(seams, run_row):
    """`settings_seam.collections` REFUSES rather than falling back to the signed
    defaults, and its reason holds word for word: *every step it takes reaches a
    real customer*."""
    seams["settings"] = {"readable": False, "why_not": "the settings row could not be read"}
    result = _run(run_row)
    assert set(_outcomes(result, pp.STEP_WARN).values()) == {pp.OUTCOME_NOT_CONFIGURED}
    assert set(_outcomes(result, pp.STEP_VOID).values()) == {pp.OUTCOME_SKIPPED}
    absences = _blocks(result)["downloads"]["stated_absences"]
    assert any("plan rules could not be read" in one for one in absences)


# ── TC-RBS-035.2 · a plan in good standing is NOT counted as skipped ──────


def test_a_plan_in_good_standing_is_walked_and_is_its_own_outcome(seams, run_row):
    """Two different facts must not share one number. *Current* and *not looked
    at* are the two, and a scope that filtered to plans with misses would make
    them the same."""
    result = _run(run_row)
    assert "AC-2026-00001" in _outcomes(result, pp.STEP_WARN)
    assert _outcomes(result, pp.STEP_WARN)["AC-2026-00001"] == pp.OUTCOME_CURRENT
    assert result.counts.get(pp.OUTCOME_CURRENT) == 1
    # And it is NOT in the skipped tally for the warn step.
    assert result.set_results[pp.STEP_COUNT]["current"] == 1


# ── TC-RBS-035.3 · the void is payments' act, and this module cannot do it ──


def test_the_void_is_planned_and_no_port_is_reached_for_it(seams, run_row):
    """The absence this runbook is built around. Both halves are asserted: the
    plan reaches `to_void` with its rule, AND nothing was written for it — a
    `to_void` outcome over a runbook that had quietly updated a plan status
    would read identically."""
    result = _run(run_row)
    ended = next(
        one
        for one in result.records
        if one.step_key == pp.STEP_VOID and one.outcome == pp.OUTCOME_TO_VOID
    )
    assert "End this plan on the account" in ended.reason
    # `queue_notice` is the only port it holds, so there is nothing it could
    # have reached to write a plan status.
    assert pp.RUNBOOK.ports == ("queue_notice",)
    assert not any(
        record.data.get("idempotency_key")
        for record in result.records
        if record.step_key == pp.STEP_VOID
    )


def test_the_result_says_out_loud_that_it_cannot_end_a_plan(seams, run_row):
    """A result that did not say so would let a clerk believe the plans ended."""
    absences = _blocks(_run(run_row))["downloads"]["stated_absences"]
    assert absences[0].startswith("this run cannot end a plan")


def test_the_plans_to_end_tile_carries_who_ends_them(seams, run_row):
    """A live-looking number behind a door that does not open is hard-won law
    2's mirror. The tile carries the sentence."""
    tile = next(
        one for one in _blocks(_run(run_row))["kpis"]["tiles"] if one["id"] == "void"
    )
    assert tile["value"]["text"] == "1"
    assert tile["detail"] == "A person ends a plan on the account"


# ── guards — absolute, before step 1 (BR-RBS-012) ─────────────────────────


def test_a_sample_plan_is_never_acted_on_and_is_still_counted(seams, run_row):
    seams["samples"] = frozenset({ENDING})
    result = _run(run_row)
    assert "AC-2026-00003" not in _outcomes(result, pp.STEP_WARN)
    # BR-RBS-035 — no record row, and still in the counts.
    assert result.counts.get("skipped", 0) >= 1


def test_a_disputed_account_is_not_chased(seams, run_row):
    seams["disputes"] = frozenset({"unit-AC-2026-00003"})
    assert "AC-2026-00003" not in _outcomes(_run(run_row), pp.STEP_WARN)


# ── the repeat rule (hard rule 6, and the discriminator that carries it) ──


def test_the_warning_key_carries_the_miss_count_and_not_the_run(seams, run_row):
    """A plan at two misses is warned ONCE however often the run fires; a plan
    that misses a third is a different key and is warned again. Drop the
    discriminator and a customer who falls further behind is never told."""
    keys = {
        one.subject.label: one.data.get("idempotency_key")
        for one in _run(run_row).records
        if one.step_key == pp.STEP_WARN and one.data.get("idempotency_key")
    }
    assert keys["AC-2026-00002"].endswith("|1")
    assert keys["AC-2026-00003"].endswith("|2")
    assert str(run_row.pk) not in keys["AC-2026-00002"]


# ── the report obeys the contract (BR-RBS-020 · BR-RBS-021 · DEF-RBS-4352) ──


def test_the_report_validates_at_close_and_names_only_the_twelve(seams, run_row):
    frozen = validate_report(_run(run_row).report, runbook_key=pp.RUNBOOK_KEY)
    assert {one["block"] for one in frozen} <= set(BLOCK_TYPES)


def test_the_breakdown_carries_heading_columns_and_cell_rows(seams, run_row):
    """`DEF-RBS-4352` itself: the ladder shipped `{by, rows, rungs}` and
    `RBS-006` drew an error boundary instead of 835 notices, with every test on
    both sides green."""
    breakdown = _blocks(_run(run_row))["breakdown"]
    assert set(breakdown) == {"heading", "columns", "rows"}
    assert all(set(one) >= {"id", "cells"} for one in breakdown["rows"])


def test_the_records_empty_state_carries_the_two_fields_the_renderer_reads(seams, run_row):
    seams["plans"] = []
    empty = _blocks(_run(run_row))["records"]["empty"]
    assert set(empty) == {"title", "helper"}


def test_no_database_id_reaches_a_clerk(seams, run_row):
    """B14 rule 31, and `decided_by_rule` in `meta` where no block draws it."""
    rows = _blocks(_run(run_row))["records"]["rows"]
    drawn = str([one["cells"] for one in rows])
    for account_id in (CURRENT, BEHIND, ENDING):
        assert account_id not in drawn
    assert all("decided_by_rule" in one["meta"] for one in rows)


def test_money_reaches_the_screen_at_four_places_and_never_as_a_float(seams, run_row):
    """Hard rule 2. The renderer displays two; the payload carries four, and a
    float would be a figure no column type could catch on the way through
    jsonb."""
    tile = next(
        one for one in _blocks(_run(run_row))["kpis"]["tiles"] if one["id"] == "missed_value"
    )
    assert tile["value"] == {"kind": "money", "amount": "394.4800", "currency": "USD"}
    assert isinstance(tile["value"]["amount"], str)


# ── the shape of the declaration ──────────────────────────────────────────


def test_the_two_read_steps_are_SET_and_the_two_writes_are_PER_RECORD(seams, run_row):
    """`TC-RBS-17`: registering a set step as per-record is a real mistake with a
    real cost — one settings read and one plan query per plan."""
    runs = _run(run_row).step_runs
    assert runs[pp.STEP_MISSED] == 1
    assert runs[pp.STEP_COUNT] == 1
    assert runs[pp.STEP_WARN] == 3
    assert runs[pp.STEP_VOID] == 3


def test_the_subject_is_an_account_because_payment_plan_is_not_a_subject_type():
    assert pp.RUNBOOK.subject_type == "account"
    assert "payment_plan" not in models.SUBJECT_TYPES
