# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 — the recorded ETL runner) · DEF-771
#           Screens: WFL-01.units.2–5
# Rules:    BR-MET-096 (ONE runner, two targets) · BR-MET-100 (a units row
#           naming a plan that cannot be resolved LOADS, unplanned and
#           flagged) · BR-RAT-030 (only PUBLISHED plans are assignable) ·
#           BR-MET-117 posture (refusing beats a silent wrong answer)
# Journeys: the units migration — a utility's first 9,881 units
# ───────────────────────────────────────────────────────
"""**DEF-771 — THE SCREEN ASKS FOR A `Plan` AND THE MATCHER WANTED A CODE.**

A utility uploaded 9,881 units whose `rate_plan` column read `city customer
plan` on every row — the plan's NAME. The column is labelled **Plan** and
accepts the aliases `plan`, `rate plan` and `tariff`, three of which are the
words for a NAME; `rating.selectors` indexed plans by CODE alone. Every row
mapped clean, showed `Matched`, and loaded unplanned:
`LOADED 9,881 · FLAGGED 9,881 · UNITS WITH NO PLAN 9,881`.

⚠ **AND NO TEST IN THIS REPO COULD SEE IT.** The dominant plan fixture
(`tests/test_us_met_helpers.make_plan`) DERIVES the code from the name
(`name.lower().replace(" ", "-")`), and the units-import fixture's file names
its plan by CODE only — so "matched by code" and "matched by name" produced
the same answer everywhere the suite looked. **`a_plan()` below is the fixture
that makes them tell apart**: `PLN-A17` is nothing like `City Customer Plan`,
and `test_the_fixture_can_tell_the_two_behaviours_apart` fails if a later
edit lets them converge again.

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7) — the RED text for each new
assertion is recorded in the PLANREF lane report; every one of them was run
against the pre-fix tree, where the plan index was `{lowered code: id}`.
"""

import pytest

from apps.metering import import_runs, models
from apps.metering import services as metering_services

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    marcus,
    tenant_ctx,
)
from tests.test_cr023_import_stages import ALL_ON

pytestmark = pytest.mark.django_db


#: The PO's own cell, verbatim from the defect: the column carried the plan's
#: NAME, in lower case, on all 9,881 rows.
THE_NAME = "City Customer Plan"
#: …and a CODE that shares not one token with it. That is the whole fixture
#: change DEF-771 asked for.
THE_CODE = "PLN-A17"


def a_plan(*, code=THE_CODE, name=THE_NAME, status="published"):
    """One plan whose CODE and NAME are nothing like each other."""
    from apps.rating import models as rating_models
    from core import tenancy as core_tenancy

    return rating_models.RatePlan.objects.create(
        tenant_id=core_tenancy.current_tenant_id(),
        code=code,
        name=name,
        status=status,
        version=1,
    )


def a_premise(actor):
    """One premises, numbered by the SERVER's own series (BR-MET-005)."""
    created = metering_services.create_premises(actor, {"owner_id": owner_for(actor), "address_line": "1408 Elm Street"})
    return models.Premises.objects.get(pk=created["id"]).premise_no


def units_file(premise_no, plan_cell, *, rows=2):
    header = "UNIT_REF,PREMISE_ID,UNIT_TYPE,SQFT,PLAN"
    body = [
        f"U-1040{index},{premise_no},APT,{900 + index},{plan_cell}" for index in range(1, rows + 1)
    ]
    return "\n".join([header, *body]) + "\n"


MAPPING = {
    "UNIT_REF": "label",
    "PREMISE_ID": "premises",
    "UNIT_TYPE": "unit_type",
    "SQFT": "square_feet",
    "PLAN": "rate_plan",
}


def run_to_validated(actor, content):
    run = import_runs.extract(
        actor,
        {
            "target": "units",
            "source_kind": "file",
            "file_name": "riverside_units.csv",
            "content": content,
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
    return run["id"], import_runs.validate(actor, run["id"])


def load(actor, run_id):
    return import_runs.load(actor, run_id, {"write_mode": "insert"})


def plan_rule(checked):
    return {rule["code"]: rule for rule in checked["rules"]}["UNT.PLAN_ON_FILE"]


# ═══════════════════════════════════════════════════════════════════════════
# 0 · THE FIXTURE — without this the rest of the file proves nothing
# ═══════════════════════════════════════════════════════════════════════════


def test_the_fixture_can_tell_the_two_behaviours_apart(brazos, marcus):
    """⚠ **THE PRECONDITION OF EVERY OTHER CASE HERE.**

    If a plan's code and its name are the same token — or one is derived from
    the other — then "matched by code" and "matched by name" return the same
    id and no assertion below can distinguish them. That is exactly why
    DEF-771 lived in the tree with a green suite.
    """
    with tenant_ctx(brazos):
        plan = a_plan()
    assert plan.code.lower() != plan.name.lower()
    assert plan.code.lower() != plan.name.lower().replace(" ", "-")
    assert plan.name.lower() not in plan.code.lower()
    assert plan.code.lower() not in plan.name.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 1 · A NAME RESOLVES — the defect itself
# ═══════════════════════════════════════════════════════════════════════════


def test_def_771__a_units_file_naming_the_plan_by_NAME_loads_PLANNED(brazos, marcus):
    """The PO's file: the `Plan` column holds the plan's NAME."""
    with tenant_ctx(brazos):
        plan = a_plan()
        premise_no = a_premise(marcus)
        run_id, checked = run_to_validated(marcus, units_file(premise_no, THE_NAME.lower()))
        assert plan_rule(checked)["hits"] == 0, "a plan named by NAME is on file"
        result = load(marcus, run_id)
        planned = [
            str(unit.rate_plan_id)
            for unit in models.Unit.objects.filter(deleted_at__isnull=True).order_by("label")
        ]
    assert planned == [str(plan.id), str(plan.id)]
    assert result["receipt"]["unplanned_units"] == 0
    assert result["receipt"]["loaded"] == 2


def test_def_771__a_NAME_matches_case_folded(brazos, marcus):
    """`CITY CUSTOMER PLAN` and `city customer plan` are one plan — the same
    posture the code half already took."""
    with tenant_ctx(brazos):
        plan = a_plan()
        premise_no = a_premise(marcus)
        run_id, _ = run_to_validated(marcus, units_file(premise_no, THE_NAME.upper()))
        load(marcus, run_id)
        ids = {str(unit.rate_plan_id) for unit in models.Unit.objects.all()}
    assert ids == {str(plan.id)}


def test_def_771__the_CODE_still_matches(brazos, marcus):
    """The mirror, so the fix is an addition and not a swap."""
    with tenant_ctx(brazos):
        plan = a_plan()
        premise_no = a_premise(marcus)
        run_id, _ = run_to_validated(marcus, units_file(premise_no, "pln-a17"))
        load(marcus, run_id)
        ids = {str(unit.rate_plan_id) for unit in models.Unit.objects.all()}
    assert ids == {str(plan.id)}


# ═══════════════════════════════════════════════════════════════════════════
# 2 · AN AMBIGUOUS NAME REFUSES AND NAMES THE COLLISION
# ═══════════════════════════════════════════════════════════════════════════


def test_def_771__two_published_plans_sharing_a_case_folded_name_REFUSE(brazos, marcus):
    """⚠ **A NAME IS NOT UNIQUE THE WAY A CODE IS.**

    `uq_rate_plans_tenant_name` is `UniqueConstraint(fields=["tenant","name"])`
    — EXACT, not case-insensitive, unlike `uq_rate_plans_tenant_code_ci` which
    is `Lower("code")`. So two published plans of one tenant may differ only in
    case, and a case-folded match then has two answers. Picking one silently
    mis-plans the unit and bills it at the wrong rate, so the row keeps
    BR-MET-100's outcome (loads, unplanned, flagged) and the sentence NAMES
    BOTH plans instead of choosing.
    """
    with tenant_ctx(brazos):
        first = a_plan(code="PLN-A17", name="City Customer Plan")
        second = a_plan(code="PLN-B22", name="city customer plan")
        premise_no = a_premise(marcus)
        run_id, checked = run_to_validated(marcus, units_file(premise_no, "CITY CUSTOMER PLAN"))
        assert plan_rule(checked)["hits"] == 2
        rows = list(models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no"))
        problem = rows[0].problem or ""
        result = load(marcus, run_id)
        assigned = {unit.rate_plan_id for unit in models.Unit.objects.all()}
    assert assigned == {None}, "never pick one of two — that is a silent wrong bill"
    assert first.code in problem and second.code in problem, problem
    assert "more than one" in problem.lower(), problem
    assert result["receipt"]["unplanned_units"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# 3 · "NO SUCH PLAN" AND "THAT PLAN IS A DRAFT" ARE DIFFERENT SENTENCES
# ═══════════════════════════════════════════════════════════════════════════


def test_def_771__a_DRAFT_plan_says_it_is_a_draft(brazos, marcus):
    """BR-RAT-030 keeps a draft unassignable — but the operator's next action
    is *publish it*, not *check the spelling*, and only one of those two
    sentences leads there."""
    with tenant_ctx(brazos):
        a_plan(status="draft")
        premise_no = a_premise(marcus)
        run_id, checked = run_to_validated(marcus, units_file(premise_no, THE_NAME))
        row = models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no").first()
        problem, hint = row.problem or "", row.fix_hint or ""
        result = load(marcus, run_id)
    assert "draft" in problem.lower(), problem
    assert "not on file" not in problem.lower(), problem
    assert "publish" in hint.lower(), hint
    assert result["receipt"]["unplanned_units"] == 2


def test_def_771__an_ARCHIVED_plan_says_it_is_withdrawn(brazos, marcus):
    with tenant_ctx(brazos):
        a_plan(status="archived")
        premise_no = a_premise(marcus)
        run_id, _ = run_to_validated(marcus, units_file(premise_no, THE_NAME))
        row = models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no").first()
        problem = row.problem or ""
    assert "archived" in problem.lower(), problem
    assert "not on file" not in problem.lower(), problem


def test_def_771__a_plan_nobody_has_is_still_not_on_file(brazos, marcus):
    """The third sentence, unchanged — BR-MET-100's original case."""
    with tenant_ctx(brazos):
        a_plan()
        premise_no = a_premise(marcus)
        run_id, _ = run_to_validated(marcus, units_file(premise_no, "Rural Standard 2027"))
        row = models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no").first()
        problem = row.problem or ""
    assert "not on file" in problem.lower(), problem
    assert row.outcome == "flagged", "BR-MET-100 loads it — it does not reject"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE RECEIPT SAYS SOMETHING A PERSON CAN ACT ON
# ═══════════════════════════════════════════════════════════════════════════


def test_def_771__the_receipt_names_the_plan_every_unplanned_row_asked_for(brazos, marcus):
    """⚠ **9,881 FLAGGED ROWS IS NOT A REVIEW ANYBODY CAN PERFORM.** The
    receipt has to say HOW MANY, WHICH plan they all named, and WHY — one
    line per distinct unresolved token, not 9,881 identical ones."""
    with tenant_ctx(brazos):
        a_plan(status="draft")
        premise_no = a_premise(marcus)
        run_id, _ = run_to_validated(marcus, units_file(premise_no, THE_NAME, rows=3))
        rehearsed = import_runs.dry_run(marcus, run_id, "insert")
        result = load(marcus, run_id)
    entries = result["receipt"]["unplanned_plans"]
    assert [(entry["asked_for"], entry["rows"], entry["reason"]) for entry in entries] == [
        (THE_NAME, 3, "draft")
    ]
    assert THE_CODE in entries[0]["detail"], entries[0]["detail"]
    # the rehearsal says the SAME thing before anything is written (DEF-544's
    # rule: a dry run that disagrees with its commit is worse than none)
    assert rehearsed["unplanned_plans"] == entries


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE COLUMN SAYS WHICH IT TAKES
# ═══════════════════════════════════════════════════════════════════════════


def test_def_771__the_Plan_column_says_it_takes_a_code_OR_a_name(brazos, marcus):
    """The screen said `Plan` and the matcher wanted a code, and NOTHING
    ANYWHERE STATED THE DIFFERENCE. This is where it is stated."""
    with tenant_ctx(brazos):
        offered = {column["target"]: column for column in import_runs.target_columns("units")}
        entry = offered["rate_plan"]
    assert entry["label"] == "Plan"
    help_text = entry.get("help") or ""
    assert "code" in help_text.lower(), help_text
    assert "name" in help_text.lower(), help_text
