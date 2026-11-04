# ── Trace ──────────────────────────────────────────────
# Change:  DEF-CUS-9836 — New Connect step 2's "This plan" Taxes summary read a
#          bare count, because the combined figure was the PLAN's and a plan
#          for every class with a class-limited tax has none (DEF-RAT-9519).
# Rules:   CLAUDE.md hard rule 2 (the sum is the server's, on the stored
#          six-place fractions) · DEF-RAT-9519 (the figure is what a bill
#          CHARGES)
# Tests:   this file
# Impacts: apps/rating/plan_reads.py `_taxes` · apps/rating/selectors.py
#          `plan_combined_tax_rate_display(class_codes=)`
# ───────────────────────────────────────────────────────
"""An every-class plan with a State tax of 6.25% that only Commercial pays and a
County tax of 2.00% that everyone pays. The plan alone has no single figure
(Residential pays 2.00%, Commercial 8.25%) and says none; a Residential
account's read (`?classes=residential`) says **2.00%**, a Commercial one's
**8.25%**.

WHAT WOULD MAKE THIS PASS WRONGLY: summing every percentage tax regardless of
class gives 8.25% for both and fails the Residential case; ignoring `classes`
leaves `None` and fails both.
"""

from __future__ import annotations

import pytest

from apps.rating import plan_reads
from tests.test_cr167_plans_round2 import _today  # noqa: F401 — the autouse "today"
from tests.test_def_cus_9821_new_connect_plan_block_read import _plan, _schedule
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _taxed_plan(env):
    schedule = _schedule(env)
    state = env.tax("State tax", rate="0.0625", applies_to_customer_classes=["commercial"])
    county = env.tax("County tax", rate="0.02")
    return _plan(env, schedule, taxes=[{"tax": str(state["id"])}, {"tax": str(county["id"])}])


def test_the_plan_alone_still_has_no_single_figure(env):
    plan = _taxed_plan(env)
    with tenant_ctx(env.tenant):
        assert plan_reads.plan_sections(plan["id"])["combined_tax_rate_display"] is None


def test_an_accounts_class_gets_what_its_bill_charges(env):
    plan = _taxed_plan(env)
    with tenant_ctx(env.tenant):
        residential = plan_reads.plan_sections(plan["id"], classes=["residential"])
        commercial = plan_reads.plan_sections(plan["id"], classes=["commercial"])
    assert residential["combined_tax_rate_display"] == "2.00%"
    assert commercial["combined_tax_rate_display"] == "8.25%"
    reach = {row["ref"]["name"]: row["reaches_plan_classes"] for row in residential["taxes"]}
    assert reach == {"State tax": "none", "County tax": "all"}
