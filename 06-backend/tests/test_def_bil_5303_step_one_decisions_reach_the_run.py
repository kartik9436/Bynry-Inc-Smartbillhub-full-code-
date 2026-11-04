# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-001 (S31 step 1 — the run's scope)   Screens: S31 · BIL-02
#           (blueprint §03 entry 16 Scope, p046–p048)
# Rules:    BR-BIL-1040 (the run's standing answers) · BR-BIL-1041 (the run's
#           template pin — PO 2026-09-14, *"in this step 1 scope - you will
#           ahve to also decide on billing template"*) · BR-BIL-005
# Defects:  DEF-BIL-5303 (the three columns had a resolver and no door)
# Impacts:  apps/billing/api.bill_runs
# ───────────────────────────────────────────────────────
"""The three things screen 16 decides reach the run THROUGH THE ROUTE.

`billing/0028` added `case_defaults`, `label` and `template_id`;
`runs.create_run` has accepted all three ever since and `resolve_case_defaults`
and `validated_template_pin` validate them. **`POST /billing/runs` passed none
of them**, so the blueprint's *"single biggest error-reducer in this redraw"*
had a column, a migration and a validated resolver with nowhere for a screen to
send its answers.

⚠ **WHY THIS FILE ASSERTS THROUGH THE ENDPOINT AND NOT THROUGH `create_run`.**
That is the whole defect. Both resolvers already had unit tests that call them
directly, and every one of them passed while the door was shut — a keyword
argument that defaults to `None` is valid Python, so nothing anywhere went red.
`DEF-BIL-5303`'s prevention column states the rule this file is: **when a
migration adds a column a screen is meant to write, assert the round trip
through the ROUTE, not through the function the route is supposed to call.**

⚠ **NO FIGURE HERE IS TAKEN FROM THE DRAWING.** B14 rule 37 — the labels and
choices on p047 (*"September, after the water rate change"*, *"Estimate from
history"*) are illustrations. The choices asserted below are read out of
`decisions.CHOICES_BY_CASE`, which is the vocabulary the resolver validates
against, so this file cannot pin a word the engine does not offer.
"""

from datetime import date

import pytest

from apps.billing import models as billing_models
from apps.metering import models as metering_models
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures (brazos, dana)
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

PERIOD = (date(2026, 6, 1), date(2026, 6, 30))


def _cycle(tenant, code):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        bill_day=1,
        due_days=21,
        start_day=1,
        days_to_complete=3,
        first_run_date=date(2026, 6, 1),
    )


def _door_ready(tenant, actor, cycle):
    """⚠ ADDED 2026-09-30 (bulk bill run plan A1/B4). The door now refuses a
    cycle with no units or no accounts and REQUIRES a run name and a published
    template, so every POST here that means to succeed needs one billed account
    on the cycle and the two fields. Returns the two fields' defaults."""
    from apps.billing import templates_service
    from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account

    with tenant_ctx(tenant):
        if not metering_models.ServicePoint.objects.filter(tenant=tenant, cycle=cycle).exists():
            unit = a_billed_unit(
                actor, tenant, cycle, a_priced_plan(tenant), asset_no=f"M-{cycle.code}", label=cycle.code
            )
            an_account(tenant, unit["id"], f"A-{cycle.code}")
        template = templates_service.tenant_fallback_template()
        if template is None or templates_service.published_version(template) is None:
            templates_service.seed_platform_default(on_date=date(2026, 1, 1))
            template = templates_service.tenant_fallback_template()
        return {"label": f"June 2026 {cycle.code}", "template_id": str(template.pk)}


def _create(tenant, actor, cycle, **extra):
    from apps.billing import api as billing_api
    from tests.test_us_met_helpers import FakeUser
    from tests.test_us_ten_helpers import api_call

    required = _door_ready(tenant, actor, cycle)
    return api_call(
        billing_api.bill_runs,
        "post",
        user=FakeUser(actor.id),
        role="billing_clerk",
        tenant=tenant,
        data={
            "cycle_id": str(cycle.id),
            "period_start": PERIOD[0].isoformat(),
            "period_end": PERIOD[1].isoformat(),
            **required,
            **extra,
        },
    )


def _a_case_and_two_choices():
    """One case kind the engine raises, and two choices it offers for it.

    Read from the engine's own vocabulary rather than typed here, so this file
    states no second copy of a list `resolve_case_defaults` validates against
    (the reason that function spells no literal either — PO 2026-09-14, *"no
    hardcoding"*).
    """
    from apps.billing import decisions

    for case_kind, choices in sorted(decisions.CHOICES_BY_CASE.items()):
        if len(choices) >= 2:
            return case_kind, choices[0], choices[1]
    raise AssertionError("no case kind offers two choices; the vocabulary moved")


def test_def_bil_5303__the_label_a_clerk_types_reaches_the_run(brazos, dana):
    """Callout ④ on p047. Without it every finished run reads `Draft` for ever
    and no past run can be told from another (`DEF-171`, `DEF-602`)."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "5303-A")
    response = _create(brazos, dana, cycle, label="After the water rate change")
    assert response.status_code == 201
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.get(pk=response.data["id"])
        assert run.label == "After the water rate change"


def test_def_bil_5303__a_blank_label_records_that_nobody_typed_one(brazos, dana):
    """Blank is an ABSENCE, not the empty string — `create_run` strips and
    stores NULL, and a screen must not have to know the difference.

    ⚠ **THIS ONE PASSES WITH THE DOOR SHUT TOO, AND IT IS KEPT ANYWAY.** Said
    plainly rather than left for a reader to discover: a shut door also stores
    NULL, so this asserts the STRIP-TO-NULL rule and proves nothing about
    `DEF-BIL-5303`. The test above it is the one that fails when the door
    closes.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "5303-B")
    response = _create(brazos, dana, cycle, label="   ")
    # ⚠ AMENDED 2026-09-30 (bulk bill run plan B4): a run name is now REQUIRED
    # (PO: *"What to bill - in drawring i will give run name"*), so blank is a
    # refusal on the label field — still read as blank after stripping.
    assert response.status_code == 422
    assert [e["reason"] for e in response.data["field_errors"]] == ["label_missing"]


def _a_case_and_a_choice_that_is_not_the_tenants(tenant):
    """A case the DEFAULTS group carries, and a choice the tenant is NOT on.

    ⚠ **THE "NOT THE TENANT'S" HALF IS THE WHOLE POINT, AND IT IS LAW 7's
    QUESTION ASKED OF THIS FILE.** A first draft picked the case's first two
    choices and asserted the stored value was the one it sent. With the door
    SHUT that assertion still passed whenever the tenant's own setting happened
    to equal the choice sent — a check that cannot fail for the defect it is
    written for, which is worse than no check because it is trusted. Choosing a
    value the tenant is demonstrably not on makes the clerk's answer the only
    thing that could have put it there.
    """
    from apps.billing import decisions, settings_seam

    opens_on = settings_seam.run_case_defaults()
    for case_kind, tenant_choice in sorted(opens_on.items()):
        for offered in decisions.CHOICES_BY_CASE.get(case_kind, ()):
            if offered != tenant_choice:
                return case_kind, tenant_choice, offered
    raise AssertionError("every case offers only what the tenant is already on")


def test_def_bil_5303__the_standing_answers_reach_the_run(brazos, dana):
    """Callout ③ — the DEFAULTS group, three decisions made once instead of
    hundreds of times per account."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "5303-C")
        case_kind, tenant_choice, clerk_choice = _a_case_and_a_choice_that_is_not_the_tenants(
            brazos
        )
    assert clerk_choice != tenant_choice, "the fixture must not make the two equal"
    response = _create(brazos, dana, cycle, case_defaults={case_kind: clerk_choice})
    assert response.status_code == 201
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.get(pk=response.data["id"])
        assert run.case_defaults[case_kind] == clerk_choice, (
            "the clerk's answer must win over the tenant's S66 setting"
        )


def test_def_bil_5303__an_untouched_control_falls_to_the_tenants_own_setting(brazos, dana):
    """`resolve_case_defaults` fills what the clerk did not touch from S66.
    The endpoint must not substitute anything of its own on the way past — a
    default written here would be a second copy of a figure the tenant's own
    Settings screen shows (BR-BIL-1040)."""
    from apps.billing import settings_seam

    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "5303-D")
        tenant_defaults = settings_seam.run_case_defaults()
    response = _create(brazos, dana, cycle)
    assert response.status_code == 201
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.get(pk=response.data["id"])
        assert run.case_defaults == tenant_defaults


def test_def_bil_5303__an_unknown_choice_is_refused_and_leaves_no_run(brazos, dana):
    """The refusal `resolve_case_defaults` raises must reach the CALLER rather
    than being swallowed into a 201 — and it must leave nothing behind, which is
    the posture the backwards-period and unknown-cycle refusals already take."""
    case_kind, _first, _second = _a_case_and_two_choices()
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "5303-E")
        before = billing_models.BillRun.objects.count()
    response = _create(
        brazos, dana, cycle, case_defaults={case_kind: "a-choice-nobody-offers"}
    )
    assert response.status_code != 201
    with tenant_ctx(brazos):
        assert billing_models.BillRun.objects.count() == before


def test_def_bil_5303__an_unknown_case_kind_is_refused_by_name(brazos, dana):
    """A run default naming a case nobody raises is a decision with nothing to
    apply it to, and the resolver says so. The door must not blunt that."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "5303-F")
    response = _create(brazos, dana, cycle, case_defaults={"not_a_case_kind": "x"})
    assert response.status_code != 201


def test_def_bil_5303__a_template_that_is_not_this_tenants_is_refused_at_step_one(
    brazos, dana
):
    """BR-BIL-1041, and the point of pinning at Scope: the refusal arrives
    BEFORE the clerk signs off, instead of surfacing in `issue`'s
    `template_problems` after they have."""
    import uuid

    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "5303-G")
        before = billing_models.BillRun.objects.count()
    response = _create(brazos, dana, cycle, template_id=str(uuid.uuid4()))
    assert response.status_code != 201
    with tenant_ctx(brazos):
        assert billing_models.BillRun.objects.count() == before


def test_def_bil_5303__omitting_the_name_and_template_is_now_refused_on_both(brazos, dana):
    """⚠ SUPERSEDED 2026-09-30. This case read *"omitting all three still
    creates a run"*, because the six-step wizard POSTed none of them. The bulk
    bill run redesign (plan B4) makes the run name and a published template
    REQUIRED at Scope and the PO ruled ONE bill-run screen (*"why two screens -
    this is not correct"*), so omitting them is now two refusals, each on its
    own field. The standing answers stay optional (they move to Check)."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "5303-H")
    response = _create(brazos, dana, cycle, label=None, template_id=None)
    assert response.status_code == 422
    assert {e["reason"] for e in response.data["field_errors"]} == {
        "label_missing",
        "template_missing",
    }


# ═══════════════════════════════════════════════════════════════════════════
# GET /billing/run-case-defaults — what the DEFAULTS group OFFERS
# ═══════════════════════════════════════════════════════════════════════════
#
# The three controls cannot be drawn without the server: which cases carry a
# standing answer, what each offers, and what the tenant is on. Typing any of
# that into the screen is what the PO's 2026-09-14 *"no hardcoding"* forbids,
# and the failure mode is a control that submits a choice the server refuses.
def _case_defaults_read(tenant, actor):
    from apps.billing import api as billing_api
    from tests.test_us_met_helpers import FakeUser
    from tests.test_us_ten_helpers import api_call

    return api_call(
        billing_api.run_case_defaults,
        "get",
        user=FakeUser(actor.id),
        role="billing_clerk",
        tenant=tenant,
    )


def test_def_bil_5303__the_defaults_group_is_served_not_typed(brazos, dana):
    """Every case the group carries, with what it opens on and what it offers."""
    from apps.billing import decisions, settings_seam

    response = _case_defaults_read(brazos, dana)
    assert response.status_code == 200
    with tenant_ctx(brazos):
        expected = settings_seam.run_case_defaults()
    served = {row["case"]: row for row in response.data["cases"]}
    assert set(served) == set(expected), "the cases are the seam's, not this file's"
    for case_kind, opens_on in expected.items():
        assert served[case_kind]["opens_on"] == opens_on
        assert [c["code"] for c in served[case_kind]["choices"]] == list(
            decisions.CHOICES_BY_CASE[case_kind]
        ), "the order is the rule's own order, not sorted here"


def test_def_bil_5303__every_option_says_whether_it_bills_or_holds(brazos, dana):
    """p036: *"Two of them hold and produce no bill, and a clerk cannot be
    expected to know which."* `holds` is read from the same set `_is_held`
    reads, so the word on the option and the behaviour at prepare time cannot
    disagree.

    ⚠ Asserted against `HOLDING_CHOICES` rather than against a list typed here:
    a hand-written expectation would be the second copy this endpoint exists to
    prevent, and it would go stale the day a rule moved.
    """
    from apps.billing import decisions

    response = _case_defaults_read(brazos, dana)
    assert response.status_code == 200
    seen_holding = 0
    for row in response.data["cases"]:
        for choice in row["choices"]:
            expected = (row["case"], choice["code"]) in decisions.HOLDING_CHOICES
            assert choice["holds"] == expected, (
                f"{row['case']}/{choice['code']} disagrees with HOLDING_CHOICES"
            )
            seen_holding += 1 if expected else 0
    assert seen_holding > 0, (
        "no option holds, so this assertion could not have failed — the drawing "
        "says two of them do, and a fixture where none does proves nothing"
    )
