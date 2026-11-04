# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-002 / US-RAT-003 (EP-RAT-01) — the plan as a BOUND, VERSIONED
#           object, which is CR-013 part 5's reading of `rate_plans` and its
#           children.   Screens: PLN-01 · PLN-02 · PLN-03 (S9 · S10)
# Defects:  DEF-410 (a plan has no version history, so PLN-02's Versions tab can
#           show one row and its DATED banner promises something nothing
#           stores) · DEF-477 (after BR-RAT-088's migration, re-saving a plan
#           re-instates a base of $0.00 and every bill for that plan then
#           charges no base)
# Rules:    BR-RAT-110 (a plan BINDS discounts from the catalogue; enrolment
#           still decides who gets one — both gates) · BR-RAT-069 (plan
#           attachment makes a discount AVAILABLE, not granted) · BR-RAT-111
#           (a plan version is a filing record: who, when, why, and what
#           changed) · BR-RAT-037 (append-only versions + a REQUIRED reason) ·
#           BR-RAT-088 (the CHARGE CODE owns the base amount; a plan DISPLAYS
#           it, never defines it) · BR-RAT-094 (a plan attaches prices, it never
#           sets one) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2
#           (NUMERIC(18,6), never float) · hard rule 7 (audit on every money
#           action)
# Questions: OQ-322 (CLOSED 2026-10-03 by PO ruling (2): an unbind ends the
#           plan's enrolments the day before) · OQ-323 (which plan version prices an account
#           assigned at an older one) · OQ-324 (CLOSED 2026-10-03 (B), BR-RAT-1066 — does a plan version take effect
#           on save, or is it drafted and activated)
# ───────────────────────────────────────────────────────
"""Wave G — the plan BINDS, and the plan REMEMBERS.

Two halves, and they are the two things CR-013 part 5 asks of a plan that the
product could not do.

**Half 1 — binding.** `plan_discount_rules` shipped on 2026-08-19 as a table no
payload could name: `PLAN_FIELDS` had no `discounts` key, so `_reject_unknown`
refused one, and `plan_detail` served no list. The PO closed `OQ-300` on option
(A) on 2026-08-21 under the sentence `BR-RAT-096` carries — *"plan all steps are
bascailly binding everything together"* — so the plan binds discounts exactly the
way it binds taxes and charge codes.

⚠ **THE TEST THAT MATTERS IN THIS HALF IS THE ONE ABOUT WHAT BINDING DOES NOT
DO.** `BR-RAT-069`: attaching a discount makes it AVAILABLE, never granted. A
bill run reads `discount_enrolments`. If a later lane ever reads the availability
row instead, every account on the plan is discounted — 842 of them on Residential
Standard — and every one of those bills is wrong by the discount. So the
enrolment count is asserted to be UNMOVED by a binding, which is the assertion
that goes red the day somebody wires the wrong table.

**Half 2 — remembering.** `rate_plans.version` has been an integer since W1 and
`BR-RAT-037` has bumped it since W1, so the product could say a plan was on v3
and could not say what v1 held, who changed it or why (`DEF-410`). `plan_versions`
stores that now, in the shape the rate schedule's filing record already uses —
minus the docket, because `09-screen-inventory.md` §10 rules that a plan does not
have one.

**And one money fix that belongs to neither half but sits inside `_validate_plan`
— `DEF-477`.** The validator required `base_charge` on every service row weeks
after `BR-RAT-088` ruled that a plan may not define one, and the wizard sent the
literal `"0"` to satisfy it. A stored zero is a PRICE, so the first ordinary save
after the base migration nulls the column wrote the zero back and every base line
printed `$0.00`. On Silver Creek that is `$8.00` residential water, `$15.00`
commercial water and `$18.00` trash.
"""

from datetime import date, timedelta

import pytest

from apps.rating import discount_services
from apps.rating import discounts as discount_models
from apps.rating import models, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, audit_actions, tenant_ctx

pytestmark = pytest.mark.django_db


def _discount(env, code="SENIOR", name="Senior / Low-income", **overrides):
    """One catalogue discount, through the real service layer."""
    payload = {
        "code": code,
        "name": name,
        "discount_type": "percentage",
        "value": "15",
        "applies_to": "whole_bill",
        "effective_from": date(2026, 1, 1),
        "budget_cap": "500",
    }
    payload.update(overrides)
    with tenant_ctx(env.tenant):
        return discount_services.create_discount(env.admin, payload)


def _active_discount(env, **overrides):
    """A discount whose version is IN FORCE, so an account can be enrolled on it.

    `create_discount` leaves a DRAFT (BR-RAT-072), and `enrol_account` refuses a
    discount with no active version — correctly, since enrolling onto nothing
    would reduce a bill by an amount nobody approved. The three lifecycle calls
    are the real ones; a fixture that flipped the status column directly would
    be testing a state the product cannot reach.
    """
    row = _discount(env, **overrides)
    with tenant_ctx(env.tenant):
        version = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount_id=row["id"]
        )
        discount_services.submit_discount_version(env.admin, version.id)
        # PO ruling 2026-10-03 (1): approval is the last act — no Activate.
        discount_services.approve_discount_version(env.admin, version.id)
    return row


def _account(env, service="water", account_no="ACC-WAVE-G-1", plan=None):
    """One real account, through metering's own premises/unit helpers.

    An enrolment's `account_id` is a DEFERRED FK into the customers module
    (B2 §2) and `enrol_account` reads it through the seam, so a made-up uuid is
    a 404 rather than a test — which is the point of the seam.
    """
    from apps.customers import models as customer_models

    from tests.test_us_met_helpers import make_premises, make_unit

    with tenant_ctx(env.tenant):
        premises = make_premises(
            env.admin, address_line="1 Wave G Way", services_available=[service]
        )
        unit = make_unit(env.admin, premises["id"], label="A", services=[service])
        account = customer_models.Account.objects.create(
            tenant=env.tenant,
            unit_id=unit["id"],
            account_no=account_no,
            status=customer_models.AccountStatus.objects.get(tenant=env.tenant, code="active"),
            account_type=customer_models.AccountType.objects.first(),
        )
        if plan is not None:
            # `CR-166-BRC10` ruling 2: an account is enrolled only through a
            # plan that carries the discount, so the unit is put on `plan`.
            from apps.rating import models as rating_models

            rating_models.UnitPlanAssignment.objects.create(
                tenant=env.tenant,
                unit_id=unit["id"],
                rate_plan_id=plan["id"],
                plan_version=1,
                assigned_from=date(2026, 1, 1),
                source="change_plan",
            )
        return account


def _water_plan(env, **overrides):
    """A published water plan with a real schedule behind it."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    return env.plan(
        "Residential Standard",
        "RES-STD",
        [{"service": "water", "base_charge": "8.00", "tariff": schedule["id"]}],
        publish=True,
        **overrides,
    )


# ══════════════════════════════════════════════════════════════════════════
# Half 1 — the plan BINDS discounts (BR-RAT-110, closes OQ-300)
# ══════════════════════════════════════════════════════════════════════════


def test_br_rat_110__a_plan_binds_a_discount_and_serves_it_back(env):
    """RED before this slice with `rating.unknown_field` on `discounts`.

    `PLAN_FIELDS` carried no such key, so `_reject_unknown` refused the payload
    outright — the table existed and nothing could reach it. This is the whole
    of what OQ-300 asked and the PO answered on option (A).
    """
    discount = _discount(env)
    plan = _water_plan(env)
    with tenant_ctx(env.tenant):
        updated = services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": discount["id"]}], "reason": "Offer SENIOR"},
        )
    assert [row["code"] for row in updated["discounts"]] == ["SENIOR"]
    # The row is served in the shape every other plan child takes, so a screen
    # reading `charge_rules` can read this without a second vocabulary.
    row = updated["discounts"][0]
    assert row["discount_id"] == discount["id"]
    # BR-RAT-087 — `value_display`, not the stored value. `discount_versions.value`
    # holds percentage POINTS, so the raw figure through a fraction formatter
    # would print `1500.00%` for a 15% discount.
    assert row["value_display"] == "15.00%"
    assert "value" not in row


def test_br_rat_110__a_discount_may_be_bound_by_CODE_as_well_as_by_id(env):
    """The same latitude `_validate_plan_charge_rules` gives step 4. Two steps
    in one wizard must not disagree about what a reference is."""
    _discount(env)
    plan = _water_plan(env)
    with tenant_ctx(env.tenant):
        updated = services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": "SENIOR"}], "reason": "Offer SENIOR by code"},
        )
    assert [row["code"] for row in updated["discounts"]] == ["SENIOR"]


def test_br_rat_069__binding_a_discount_grants_it_to_NOBODY(env):
    """⚠ **THE LOAD-BEARING TEST OF THIS HALF, AND IT IS A MONEY TEST.**

    CR-013 part 3: *"plan attachment makes a discount available, not granted."*
    A bill run reads `discount_enrolments`. The day a lane reads
    `plan_discount_rules` instead, every account on the plan is discounted and
    every one of those bills is wrong — 842 of them on Residential Standard, at
    15%. So the assertion is the NUMBER OF GRANTS, before and after, and it is
    unmoved by a binding.
    """
    discount = _discount(env)
    plan = _water_plan(env)
    with tenant_ctx(env.tenant):
        before = discount_models.DiscountEnrolment.objects.filter(
            tenant=env.tenant, ended_on__isnull=True
        ).count()
        updated = services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": discount["id"]}], "reason": "Offer SENIOR"},
        )
        after = discount_models.DiscountEnrolment.objects.filter(
            tenant=env.tenant, ended_on__isnull=True
        ).count()
    assert before == 0
    assert after == 0
    # …and the read path says so on its face, so a screen cannot mistake one
    # number for the other.
    assert updated["discounts"][0]["enrolled"] == 0


def test_br_rat_110__the_binding_carries_availability_dates_and_NO_value(env):
    """`plan_discount_rules` has no value column (PO 2026-08-19, *"no plan
    cannot override prices"*), so a payload naming one is REFUSED rather than
    ignored — an ignored field is a control that looks like it saved."""
    discount = _discount(env)
    plan = _water_plan(env)
    with tenant_ctx(env.tenant):
        updated = services.update_plan(
            env.admin,
            plan["id"],
            {
                "discounts": [
                    {
                        "discount": discount["id"],
                        "available_from": "2026-09-01",
                        "available_to": "2027-09-01",
                    }
                ],
                "reason": "Offer SENIOR for a year",
            },
        )
        assert updated["discounts"][0]["available_from"] == "2026-09-01"
        assert updated["discounts"][0]["available_to"] == "2027-09-01"

        with pytest.raises(errors.ValidationError) as caught:
            services.update_plan(
                env.admin,
                plan["id"],
                {
                    "discounts": [{"discount": discount["id"], "value": "20"}],
                    "reason": "Try to reprice",
                },
            )
    fields = {row["field"] for row in (caught.value.field_errors or [])}
    assert "discounts[0].value" in fields


def test_br_rat_110__an_inverted_availability_window_is_refused(env):
    discount = _discount(env)
    plan = _water_plan(env)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        services.update_plan(
            env.admin,
            plan["id"],
            {
                "discounts": [
                    {
                        "discount": discount["id"],
                        "available_from": "2027-09-01",
                        "available_to": "2026-09-01",
                    }
                ],
                "reason": "Backwards",
            },
        )
    fields = {row["field"] for row in (caught.value.field_errors or [])}
    assert "discounts[0].available_to" in fields


def test_br_rat_110__the_same_discount_twice_on_one_plan_is_refused(env):
    """`uq_plan_discount_rules_plan_discount` makes it impossible; the
    validator names it as a field error rather than letting the DB raise, so
    the screen can point at the row."""
    discount = _discount(env)
    plan = _water_plan(env)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        services.update_plan(
            env.admin,
            plan["id"],
            {
                "discounts": [
                    {"discount": discount["id"]},
                    {"discount": discount["id"]},
                ],
                "reason": "Twice",
            },
        )
    fields = {row["field"] for row in (caught.value.field_errors or [])}
    assert "discounts[1].discount" in fields


def test_br_rat_110__an_unknown_discount_is_refused_by_name(env):
    plan = _water_plan(env)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": "NO-SUCH-CODE"}], "reason": "Typo"},
        )
    keys = {row["message_key"] for row in (caught.value.field_errors or [])}
    assert "rating.plans.unknown_discount" in keys


def test_hard_rule_1__a_plan_cannot_bind_ANOTHER_TENANTS_discount(env, other_env):
    """The id is real and belongs to somebody else, which is the only version of
    this test worth writing: a made-up uuid proves nothing about scoping."""
    theirs = _discount(other_env, code="THEIRS", name="Their discount")
    plan = _water_plan(env)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": theirs["id"]}], "reason": "Cross-tenant"},
        )
    keys = {row["message_key"] for row in (caught.value.field_errors or [])}
    # ABSENT, not forbidden — a cross-tenant id must read as not-found (HR-1/G4),
    # because "you may not have this" confirms it exists.
    assert "rating.plans.unknown_discount" in keys


def test_br_rat_110__re_posting_the_step_unchanged_keeps_the_binding(env):
    """⚠ THE SILENT FAILURE THIS GUARDS. `_apply_plan_children` REPLACES the set
    whenever the key is present, so a screen that did not read the server's
    bindings back would unbind every discount on the next rename — a change
    nobody asked for, on a save about something else."""
    discount = _discount(env)
    plan = _water_plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": discount["id"]}], "reason": "Offer SENIOR"},
        )
        served = selectors.plan_detail(plan["id"])
        # Exactly what a client re-posts from what it was served.
        renamed = services.update_plan(
            env.admin,
            plan["id"],
            {
                "name": "Residential Standard (2027)",
                "discounts": [
                    {"discount": row["discount_id"]} for row in served["discounts"]
                ],
                "reason": "Rename",
            },
        )
    assert [row["code"] for row in renamed["discounts"]] == ["SENIOR"]


def test_br_rat_110__a_binding_can_be_removed_when_NOBODY_is_enrolled(env):
    """The OQ-322 branch that IS decided: no enrolments, no money moves, so the
    unbind is an ordinary edit."""
    discount = _discount(env)
    plan = _water_plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": discount["id"]}], "reason": "Offer"},
        )
        cleared = services.update_plan(
            env.admin, plan["id"], {"discounts": [], "reason": "Withdraw"}
        )
    assert cleared["discounts"] == []


def test_oq_322_closed__unbinding_a_discount_WITH_LIVE_ENROLMENTS_ends_them_from_the_next_bill(env):
    """⚖️ `OQ-322` CLOSED by PO ruling 2026-10-03 (2): *"taking it off a plan
    stops it from the next bill."* This case asserted the `NotImplementedError`
    stub while the question was open; it now asserts the ruling — the save
    succeeds, the binding ENDS the day before (it is not deleted, so a bill for
    an earlier service date still finds it), and the plan's open enrolment
    ends on the same date with its reason."""
    from apps.rating import seams

    discount = _active_discount(env)
    plan = _water_plan(env)
    account = _account(env, plan=plan)
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": discount["id"]}], "reason": "Offer"},
        )
        discount_services.enrol_account(
            env.admin, discount["id"], account.id, enrolled_on=date(2026, 8, 15)
        )
        withdrawn = services.update_plan(
            env.admin, plan["id"], {"discounts": [], "reason": "Withdraw"}
        )
        yesterday = seams.tenant_today() - timedelta(days=1)
        rule = discount_models.PlanDiscountRule.objects.get(
            tenant=env.tenant, rate_plan_id=plan["id"], discount_id=discount["id"]
        )
        enrolment = discount_models.DiscountEnrolment.objects.get(
            tenant=env.tenant, discount_id=discount["id"]
        )
    assert withdrawn["discounts"] == []
    assert rule.available_to == yesterday
    assert enrolment.ended_on == yesterday
    assert enrolment.end_reason.startswith("Removed from plan")


def test_oq_312__the_gate_does_not_fire_on_a_binding_that_is_NOT_being_dropped(env):
    """The narrowness IS the test. A gate that refused any edit to a plan with
    an enrolled discount would make the plan uneditable, which is not what the
    open question asks about."""
    discount = _active_discount(env)
    plan = _water_plan(env)
    account = _account(env, account_no="ACC-WAVE-G-2", plan=plan)
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": discount["id"]}], "reason": "Offer"},
        )
        discount_services.enrol_account(env.admin, discount["id"], account.id)
        renamed = services.update_plan(
            env.admin,
            plan["id"],
            {
                "name": "Residential Standard (2027)",
                "discounts": [{"discount": discount["id"]}],
                "reason": "Rename",
            },
        )
    assert renamed["name"] == "Residential Standard (2027)"


def test_hard_rule_7__binding_a_discount_writes_the_plan_audit_row(env, audit_rows):
    discount = _discount(env)
    plan = _water_plan(env)
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {"discounts": [{"discount": discount["id"]}], "reason": "Offer SENIOR"},
        )
    assert "plan.version_created" in audit_actions(audit_rows)


# ══════════════════════════════════════════════════════════════════════════
# DEF-477 — the base charge a plan may not define (BR-RAT-088)
# ══════════════════════════════════════════════════════════════════════════


def test_def_477__a_plan_service_row_may_OMIT_the_base_charge(env):
    """⚠ **A CUSTOMER-FACING MONEY FIX.**

    RED before it: `rating.required` on `services[0].base_charge`. The validator
    demanded the figure BR-RAT-088 says a plan may not define — *"the CHARGE CODE
    owns the base amount … a plan displays the base rather than defining it"* —
    and because it demanded one, `PlanWizard.planPayload` sent the literal `"0"`
    for a blank. After the base migration nulls the column, the next ordinary
    save (a rename, a description edit) wrote that zero back; a stored zero is a
    PRICE, so `gather._base_charge_for` stopped letting the charge code answer
    and every base line printed `$0.00`.
    """
    env.enable("water")
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    plan = env.plan(
        "No stated base",
        "NO-BASE",
        [{"service": "water", "tariff": schedule["id"]}],
    )
    assert plan["services"][0]["base_charge"] is None
    # ⚠ NULL ON THE COLUMN, not zero. "This plan states no base for water" and
    # "water's base is zero" are different facts and only one of them is a price.
    with tenant_ctx(env.tenant):
        row = models.PlanService.objects.get(rate_plan_id=plan["id"])
    assert row.base_charge is None


def test_def_477__an_ordinary_edit_does_not_RE_INSTATE_a_zero_base(env):
    """The exact sequence the defect describes, end to end: a plan whose base is
    NULL is renamed, and the base is still NULL afterwards."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    plan = env.plan(
        "No stated base",
        "NO-BASE",
        [{"service": "water", "tariff": schedule["id"]}],
    )
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {
                "name": "No stated base (renamed)",
                "services": [{"service": "water", "tariff": schedule["id"]}],
            },
        )
        row = models.PlanService.objects.get(rate_plan_id=plan["id"])
    assert row.base_charge is None


def test_def_477__a_base_the_plan_DOES_state_still_round_trips(env):
    """What did NOT change. DEF-422 removed the wizard's control and kept the
    round trip so no stored figure is destroyed; dropping `required` must not
    also drop the value when one is sent."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    plan = env.plan(
        "Stated base",
        "HAS-BASE",
        [{"service": "water", "base_charge": "8.00", "tariff": schedule["id"]}],
    )
    with tenant_ctx(env.tenant):
        row = models.PlanService.objects.get(rate_plan_id=plan["id"])
    # Hard rule 2 — NUMERIC(18,6). The figure is a Decimal all the way down.
    assert str(row.base_charge) == "8.000000"


def test_def_477__a_NEGATIVE_base_is_still_refused(env):
    """US-RAT-002 TC-6's `base ≥ 0` survives. What was dropped is the demand
    that a figure be stated at all, never the bound on one that is."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        services.create_plan(
            env.admin,
            {
                "name": "Negative base",
                "code": "NEG",
                "services": [
                    {"service": "water", "base_charge": "-1.00", "tariff": schedule["id"]}
                ],
            },
        )
    fields = {row["field"] for row in (caught.value.field_errors or [])}
    assert "services[0].base_charge" in fields


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 PART 5 (verbatim, 12-governance/11-change-requests.md:6305) +
#         04-docs/05-modules/06-rating/02-business-rules.md (BR-RAT-110) +
#         09-screen-inventory.md §10 · §18
# screens: PLN-02 · PLN-03 (r10) / S9 · S10 (A1)
# generated: 2026-08-21 by the Wave G lane (CR-013 part 5 — the plan as a bound object)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — migrations 0020/0021 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: see the commit message — golden✔ makemigrations --check✔ tsc✔ vitest✔
# exceptions: [HISTORY — OQ-322 CLOSED 2026-10-03; the unbind now ends only THIS plan's enrolments] the OQ-322 enrolment count was TENANT-WIDE rather than plan-scoped,
#             because `discount_enrolments.account_id` is a deferred FK into the
#             customers module (B2 §2) and rating may not join it — widening a
#             refusal can only ever refuse MORE, which is the safe side of an
#             unruled question and is stated rather than hidden
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
