# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 after close (lane PLAN-TAIL, PO "complete these and
#          fix bugs").
# Defect:  DEF-RAT-9519 — a Residential plan listed TX State Utility Tax
#          (commercial and industrial only) and read "8.25% combined" on the
#          form, Review, the Charges tab and the Overview tile, while its bills
#          charge Bexar County's 2.00% alone. Our judgment (decision log
#          "A TAX THE PLAN'S CLASSES DO NOT PAY"): such a tax is listed MARKED
#          and left out of the combined figure — never refused on the form — and
#          the combined figure is the one a bill on the plan charges, or none
#          where the plan's classes pay different taxes.
# Rules:   BR-RAT-108 (a class list is an INCLUSION list) · PRB-19 (the
#          combined rate is the server's) · CLAUDE.md hard rule 2
# ───────────────────────────────────────────────────────
"""Written RED against the tip before the fix (quoted in `CR-167-BRC10` §20)."""

import pytest

from apps.rating import plan_reads, plan_writes, seams, selectors

from tests.test_cr167_plans_round2 import _contract, _schedule
from tests.test_cr167_plans_round2 import _today  # noqa: F401 — the autouse "today" (10/03/2026)
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _world(env):
    """The walk's two taxes: TX State Utility Tax 6.25 % (commercial and
    industrial only) and Bexar County 2.00 % (every class)."""
    schedule = _schedule(env)
    state = env.tax("TX State Utility Tax", rate="0.0625", applies_to_customer_classes=["commercial", "industrial"])
    county = env.tax("Bexar County", rate="0.02")
    with tenant_ctx(env.tenant):
        ids = {code: str(seams.account_type_id_by_code(code)) for code in ("residential", "commercial")}
    return schedule, state, county, ids


def _plan(env, schedule, taxes, classes, code):
    with tenant_ctx(env.tenant):
        return plan_writes.create(
            env.admin,
            _contract(
                schedule,
                details={"name": f"Plan {code}", "code": code, "customer_classes": classes},
                taxes=[{"tax": str(tax["id"])} for tax in taxes],
                publish=True,
            ),
        )


def _reach(sections):
    return {row["ref"]["name"]: row["reaches_plan_classes"] for row in sections["taxes"]}


def test_def_rat_9519__a_residential_plan_marks_the_commercial_tax_and_combines_2_percent(env):
    schedule, state, county, ids = _world(env)
    plan = _plan(env, schedule, [state, county], [ids["residential"]], "PT-RES")
    with tenant_ctx(env.tenant):
        sections = plan_reads.plan_sections(plan["id"])
        detail = selectors.plan_detail(plan["id"])
        # What the bill run is handed for a residential account on this plan.
        billed = selectors.plan_tax_rules(plan["id"], customer_class="residential", services=("water",))
    assert sections["combined_tax_rate_display"] == "2.00%"
    assert detail["combined_tax_rate_display"] == "2.00%"
    assert _reach(sections) == {"TX State Utility Tax": "none", "Bexar County": "all"}
    assert sorted(str(row["rate"]) for row in billed) == ["0.020000"]


def test_def_rat_9519__a_commercial_plan_pays_both_and_combines_8_25_percent(env):
    schedule, state, county, ids = _world(env)
    plan = _plan(env, schedule, [state, county], [ids["commercial"]], "PT-COM")
    with tenant_ctx(env.tenant):
        sections = plan_reads.plan_sections(plan["id"])
    assert _reach(sections) == {"TX State Utility Tax": "all", "Bexar County": "all"}
    assert sections["combined_tax_rate_display"] == "8.25%"


@pytest.mark.parametrize("which", ["every", "both"])
def test_def_rat_9519__classes_that_pay_different_taxes_have_no_one_combined_figure(env, which):
    """Residential pays 2.00 %, commercial 8.25 %: no single figure is what a
    bill on the plan charges, so none is served (the base total's own
    `differs_by_customer_class` answer, one section down)."""
    schedule, state, county, ids = _world(env)
    classes = [] if which == "every" else [ids["residential"], ids["commercial"]]
    plan = _plan(env, schedule, [state, county], classes, f"PT-{which.upper()}")
    with tenant_ctx(env.tenant):
        sections = plan_reads.plan_sections(plan["id"])
    assert sections["combined_tax_rate_display"] is None
    assert _reach(sections) == {"TX State Utility Tax": "some", "Bexar County": "all"}


def test_def_rat_9519__the_form_options_mark_the_tax_for_the_ticked_classes(env):
    _schedule_, _state, _county, ids = _world(env)
    with tenant_ctx(env.tenant):
        residential = plan_reads.form_options(classes=[ids["residential"]])
        commercial = plan_reads.form_options(classes=[ids["commercial"]])
    assert {row["ref"]["name"]: row["reaches_plan_classes"] for row in residential["taxes"]} == {
        "TX State Utility Tax": "none",
        "Bexar County": "all",
    }
    assert {row["ref"]["name"]: row["reaches_plan_classes"] for row in commercial["taxes"]} == {
        "TX State Utility Tax": "all",
        "Bexar County": "all",
    }


def test_def_rat_9519__the_form_never_refuses_the_tax(env):
    """Marked, never refused: a utility may attach it now and widen the plan's
    classes later."""
    schedule, state, county, ids = _world(env)
    plan = _plan(env, schedule, [state, county], [ids["residential"]], "PT-KEEP")
    with tenant_ctx(env.tenant):
        sections = plan_reads.plan_sections(plan["id"])
    assert len(sections["taxes"]) == 2
