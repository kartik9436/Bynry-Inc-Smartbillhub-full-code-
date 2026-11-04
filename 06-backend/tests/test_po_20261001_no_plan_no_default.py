# ── Trace ──────────────────────────────────────────────
# Ruling:  PO 2026-10-01 (decision log "SIX PO RULINGS IN ONE MESSAGE", (3)),
#          verbatim: *"we ahve to show the warning that no plan on unit,
#          please fi the plan first"*.
# Closes:  OQ-RAT-12782 as a DELIBERATE ABSENCE — there is no customer-type
#          default plan. Replaces tests/test_def_bil_8246_default_plan_unruled.py,
#          whose two cases were written to go red the day this was decided.
# Rules:   BR-BIL-1063 · BR-RAT-1047 · changes rows 44 (superseded alternative),
#          46 (fix on the row) and 57
# Rows:    BULK-CHG-44 · BULK-CHG-46 · BULK-CHG-57
# ───────────────────────────────────────────────────────
"""A unit with no plan: a warning, no bill, fix the plan first — and no default plan.

THE WORKED CASE. Account A-00102's unit has no plan. Before the ruling the Check
offered *"Use the customer type's default plan"* beside Hold, and the default
plan was a stub (`NotImplementedError("OQ-RAT-12782")`). Now:

  * the account STAYS BLOCKED under *No plan* — not a decision with an answer
    that could bill it, and nothing is priced;
  * the row carries the fix: set the unit's plan (changes row 46), and after it
    the account is re-checked and Ready;
  * there is no `use_default_plan` choice anywhere, and no default-plan seam.

Written RED FIRST (law 7): before the change the status was `decision`, the
choice list carried `use_default_plan`, and the rating seam existed.
"""

from __future__ import annotations

import pytest

from apps.billing import check_store, check_taxonomy, decisions
from apps.metering import models as metering_models
from apps.rating import selectors as rating_selectors

from tests.test_bbr_check_engine import FIXTURE_WARNINGS, three_accounts
from tests.test_bbr_check_store import a_run, saved_status
from tests.test_bbr_inline_fixes import _fix
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_there_is_no_default_plan_seam_and_no_default_plan_choice():
    assert not hasattr(rating_selectors, "default_plan_for_customer_type")
    assert not hasattr(decisions, "CHOICE_USE_DEFAULT_PLAN")
    every_choice = {c for choices in decisions.CHECK_CHOICES_BY_CASE.values() for c in choices}
    assert "use_default_plan" not in every_choice
    assert "unit_has_no_plan" not in decisions.CHECK_CHOICES_BY_CASE
    assert "unit_has_no_plan" not in decisions.MUST_ANSWER_CASES


def test_no_plan_is_a_tag_that_blocks_in_plans_and_rates():
    tag = check_taxonomy.TAGS["unit_has_no_plan"]
    assert tag.severity == check_taxonomy.BLOCKS
    assert tag.category == check_taxonomy.CAT_PLANS


def test_a_unit_with_no_plan_is_not_billed_and_the_row_offers_the_plan_fix(brazos, dana):
    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        cycle, plan, accounts = three_accounts(brazos, dana)
        a102 = accounts["A-00102"]
        metering_models.Unit.objects.filter(pk=a102.unit_id).update(rate_plan=None)
        run = a_run(cycle)
        check_store.check_run(run)
        status, codes = saved_status(run, a102)
        findings = check_store.account_findings(run, str(a102.id))["findings"]
        page = check_store.tag_accounts(run, "unit_has_no_plan", {})
        clerk = an_actor_user(brazos)

    assert status == "blocked" and "unit_has_no_plan" in codes
    [finding] = [f for f in findings if f["code"] == "unit_has_no_plan"]
    assert finding["fix_here"] == "set_plan"
    assert [r["account_no"] for r in page["results"]] == [a102.account_no]
    assert "use_default_plan" not in (page["tag"].get("choices") or ())

    # Fix the plan on the unit from the Check → re-checked → Ready.
    answer = _fix(run, brazos, clerk, {"account_id": str(a102.id), "fix": "set_plan", "plan_id": str(plan.id)})
    assert answer.status_code == 200, answer.data
    assert answer.data["account"]["status"] == "ready"
    with tenant_ctx(brazos):
        after = saved_status(run, a102)
    assert after[0] == "ready" and not set(after[1]) - FIXTURE_WARNINGS


def test_a_recorded_default_plan_answer_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        metering_models.Unit.objects.filter(pk=accounts["A-00102"].unit_id).update(rate_plan=None)
        run = a_run(cycle)
        check_store.check_run(run)
        with pytest.raises(Exception):
            decisions.set_standing_answer(bill_run=run, case="unit_has_no_plan", choice="use_default_plan")
