# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (S16/S15 default-plan panel — the plan-assignment path) ·
#           US-MET-002 (S15 Units list, the Assign-plan row + bulk actions)
#           Screens: S15 · S16
# Rules:    BR-MET-040 (a unit must hold a plan before an account activates) ·
#           BR-MET-041 (bulk assignment) · BR-RAT-030 (only a PUBLISHED plan is
#           assignable) · BR-CUS-013/014 (the unit's plan is what the account
#           derives from; the history row snapshots the version)
# Defect:   DEF-114 (2026-08-15, CRITICAL) — the picker offered rate SCHEDULES
#           and the endpoint resolved rate PLANS.
# Gate:     10-scripts/gates/g22_picker_vocabulary.py is the STATIC half of the
#           same guard; the register both halves read is
#           10-scripts/gates/picker_endpoint_pairs.json.
# ───────────────────────────────────────────────────────
"""The LIVE half of the picker/endpoint guard: post what the picker serves.

WHY A TEST HAS TO REACH ACROSS THE TWO HALVES OF THE PRODUCT.

DEF-114 stopped the whole application, and every check in the repo was green
over it. The S15 *Assign plan* picker was filled from ``GET /rate-schedules``;
``POST /units/{id}/plan-assignments`` resolves the posted id against
``rate_plans``. So the option list held two TARIFF ids, every one of them came
back ``422 VAL-005 metering.plan.tariff_unknown`` — *"That plan wasn't found."*
— ``unit_plan_assignments`` was EMPTY on a fully seeded stack, and BR-MET-040
held **every account activation** behind a step no human could complete.

Both halves were CORRECT AND TESTED. The picker's own tests asserted the picker
against a hand-built response; the endpoint's own tests posted a real plan id
and got a 201. Neither suite could see the defect, because the defect is not in
either half — it is in the sentence *"the set the screen offers is the set the
server takes"*, and nothing in the repo had ever written that sentence down.

So this file does the one thing that cannot be faked from either side alone:

  1. it reads the picker's path literal OUT OF THE FRONTEND SOURCE —
     ``07-frontend/src/api/endpoints.ts``, the file a lane would edit to break
     this again — rather than from a constant maintained here;
  2. it resolves that path through the REAL root URLconf and calls it against a
     REAL database holding a published plan, a draft plan and a rate schedule,
     so all three vocabularies are genuinely on offer;
  3. it posts EVERY id the picker serves at the write endpoint and requires a
     201 and a written ``unit_plan_assignments`` row for each.

Repointing the picker at ``/rate-schedules`` turns step 3 red with the
customer-visible refusal itself. That is the property worth having: the guard
fails on the DEFECT, not on a description of it (hard-won law 1).

WHAT THIS FILE IS NOT. It is not a second copy of the endpoint's tests — it
asserts nothing about plan math, warnings, backdating or locking, all of which
tests/test_us_met_003_*.py already hold. Its whole subject is the AGREEMENT.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest

from apps.metering import api as metering_api
from apps.rating import models as rating_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    FakeUser,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = REPO_ROOT / "10-scripts" / "gates" / "picker_endpoint_pairs.json"
GATE = REPO_ROOT / "10-scripts" / "gates" / "g22_picker_vocabulary.py"
#: The tenant slug every path in this file is resolved under. It is the fixture
#: tenant's own subdomain (tests/test_us_ten_helpers.brazosbend_payload).
TENANT_SLUG = "brazosbend"


def _gate_module():
    """The gate's OWN extractor, imported by path.

    Deliberately not a second copy: if this file re-implemented "which path does
    that wrapper call", the two locks could disagree about what they are
    guarding, which is the DEF-114 shape one level up.
    """
    spec = importlib.util.spec_from_file_location("g22_picker_vocabulary", GATE)
    module = importlib.util.module_from_spec(spec)
    # The gate imports `common` from its own directory.
    import sys

    sys.path.insert(0, str(GATE.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(GATE.parent))
    return module


def _pairs():
    return json.loads(REGISTER.read_text(encoding="utf-8"))["pairs"]


def unit_plan_pair():
    for pair in _pairs():
        if pair["id"] == "unit-plan":
            return pair
    raise AssertionError("the `unit-plan` pair is missing from the picker register")


def picker_path_from_frontend(pair) -> str:
    """The path the SCREEN's wrapper actually calls, read out of the frontend."""
    gate = _gate_module()
    source = (REPO_ROOT / "07-frontend" / "src" / "api" / "endpoints.ts").read_text(
        encoding="utf-8"
    )
    body = gate.wrapper_body(source, pair["picker_wrapper"])
    assert body is not None, f"{pair['picker_wrapper']} is not in endpoints.ts"
    path = gate.declared_path(body)
    assert path is not None, f"cannot read the path {pair['picker_wrapper']} calls"
    return path


def resolve_view(path: str):
    """`/plans` → the view function the REAL URLconf serves it with. A path the
    router does not know fails here rather than in an assertion about ids."""
    from django.urls import resolve

    return resolve(f"/api/{TENANT_SLUG}{path}")


@pytest.fixture()
def three_vocabularies(brazos, dana):
    """A world where the RIGHT answer and the WRONG one are both available.

    A fixture holding only plans would let a picker pointed at
    ``/rate-schedules`` return an empty list, and an empty list is not the
    defect — the defect is a list full of ids the endpoint refuses. So:

      · one PUBLISHED plan  — assignable (BR-RAT-030), what the picker must offer
      · one DRAFT plan      — a real `rate_plans` row that `plan_ref` refuses
      · rate SCHEDULES      — created by `make_plan` under each plan, and what
                              the picker offered until 2026-08-15
    """
    with tenant_ctx(brazos):
        published = make_plan(brazos, name="Residential Standard", code="RES-STD")
        draft = make_plan(brazos, name="Residential Draft", code="RES-DRAFT")
        draft.status = "draft"
        draft.save(update_fields=["status"])
        premises = make_premises(dana, address_line="1408 Bluestem Ln")
        unit = make_unit(dana, premises["id"], label="Unit A", services=["electric"])
    return {"tenant": brazos, "actor": dana, "published": published, "draft": draft, "unit": unit}


def picker_results(pair, world):
    """Call the picker's OWN endpoint with the query its wrapper sends."""
    match = resolve_view(picker_path_from_frontend(pair))
    response = api_call(
        match.func,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=world["tenant"],
        query={**pair["list_query"], "per": 500},
        **match.kwargs,
    )
    assert response.status_code == 200, response.data
    return response.data["results"]


# ── the guard ───────────────────────────────────────────────────────────────


def test_def_114__every_id_the_picker_offers_is_accepted_by_its_endpoint(three_vocabularies):
    """unit-plan: the pair, end to end, on a real database.

    THIS IS THE ASSERTION DEF-114 BROKE. Before the fix the picker's endpoint
    served tariff ids and this loop's first POST answered
    `422 VAL-005 metering.plan.tariff_unknown`.
    """
    pair = unit_plan_pair()
    world = three_vocabularies
    options = picker_results(pair, world)

    # An empty picker is not a pass. A screen offering nothing is its own defect
    # and would make every assertion below vacuously true.
    assert options, "the picker's endpoint served no options — nothing could be proved"

    for option in options:
        response = api_call(
            metering_api.unit_plan_assignments,
            "post",
            user=world["actor"].user,
            role="system_admin",
            tenant=world["tenant"],
            data={pair["id_field"]: option["id"], "effective_from": "2026-08-01"},
            unit_id=str(world["unit"]["id"]),
        )
        assert response.status_code == 201, (
            f"the picker offered {option.get('name')!r} ({option['id']}) and the endpoint "
            f"refused it: {getattr(response, 'data', None)} — the screen and its server "
            f"are speaking different vocabularies (DEF-114)"
        )
        # Every field the screen reads back off this response must be there:
        # a 201 carrying keys nobody serves is the same defect one field along
        # (DEF-121 — `default_tariff_id` was typed for four days and never sent).
        for field in pair["echo_fields"]:
            assert field in response.data, (
                f"the write response has no {field!r} — the screen reads it "
                f"(register: {pair['id']})"
            )

    with tenant_ctx(world["tenant"]):
        rows = rating_models.UnitPlanAssignment.objects.filter(unit_id=world["unit"]["id"])
        assert rows.count() == len(options), "an accepted assignment wrote no history row"
        current = rows.filter(assigned_to__isnull=True)
        assert current.count() == 1, "BR-CUS-010: exactly one CURRENT plan per unit"


def test_def_114__the_picker_never_offers_an_unassignable_plan(three_vocabularies):
    """BR-RAT-030 from the SCREEN's side.

    `plan_ref` refuses a draft with the SAME unknown-plan message it gives an
    unknown id, so a picker that listed drafts would put a subset of its options
    back in the DEF-114 state — refused, with no way for the clerk to tell which
    ones. The query that prevents that lives in the wrapper, so this asserts on
    what the wrapper's query actually returns.
    """
    pair = unit_plan_pair()
    world = three_vocabularies
    ids = {option["id"] for option in picker_results(pair, world)}

    assert str(world["published"].id) in ids, "the assignable plan is missing from the picker"
    assert str(world["draft"].id) not in ids, (
        "the picker offered a DRAFT plan — BR-RAT-030 makes it unassignable and the "
        "endpoint refuses it with the unknown-plan message"
    )


def test_def_114__the_picker_wrapper_still_constrains_what_it_asks_for():
    """The register's query must still be the wrapper's query.

    The two tests above call the picker's endpoint with the register's
    `list_query`. If a lane deleted that filter from the wrapper, both would stay
    green while the screen offered drafts — so the wrapper's own source is read
    here and required to still carry every value the register claims it sends.
    This is a text check and is honest about being one: it is why the assertions
    above go through the real endpoint rather than stopping at source reading.
    """
    pair = unit_plan_pair()
    gate = _gate_module()
    source = (REPO_ROOT / "07-frontend" / "src" / "api" / "endpoints.ts").read_text(
        encoding="utf-8"
    )
    body = gate.wrapper_body(source, pair["picker_wrapper"])
    assert body is not None
    for key, value in pair["list_query"].items():
        name = key.removeprefix("f.")
        assert re.search(rf"\b{re.escape(name)}\b", body), (
            f"{pair['picker_wrapper']} no longer mentions the {name!r} filter the "
            f"register says it sends"
        )
        assert value in source, (
            f"the value {value!r} the register says {pair['picker_wrapper']} filters on "
            f"is nowhere in endpoints.ts"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-003@4ebc614 (EP-MET-01, sha1 of the epic file) + DEF-114
# generated: 2026-08-15 by the DEF-114/115 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — repointing `getUnitPlanOptions` back at
#   "/rate-schedules" fails the first test with the customer-visible refusal
#   (`metering.plan.tariff_unknown`); the failure text is quoted in the lane report
# exceptions: E3 the register lives under 10-scripts/gates/ rather than in
#   06-backend, because the STATIC lock (G22) must read it with no Django on the
#   path; this file imports the gate BY PATH so the two locks cannot disagree
#   about what "the path that wrapper calls" means · E3 the third test is a TEXT
#   check over the wrapper's source and says so — it guards the query, which the
#   other two supply themselves; the id VOCABULARY, which is the thing DEF-114
#   got wrong, is proved against the live endpoints and never from source
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
