# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-003 (POST /plans/{id}/publish) · the R1–R7 cutover, step 4
#           (rule each class of disagreement) for the class DEF-494 names
# Defects:  DEF-494 (high — the live path and the ruled path mean opposite
#           things by "a plan in force", and the same plan splits them)
# Rules:    BR-RAT-890 (a plan cannot be published without a start date, and a
#           published plan keeps it) · BR-RAT-030 (draft → published →
#           archived) · BR-RAT-031 (a draft is resumable and may be half-typed)
#           · BR-RAT-007 (a period prices on the terms in force AT the service
#           date) · CLAUDE.md hard rule 4 (nothing issued is restated)
# Tests:    this file
# Impacts:  apps/rating/services.publish_plan + update_plan · apps/rating/
#           migrations/0024_def494_publish_needs_a_start_date.py 🔒 ·
#           apps/rating/sample_data.py · apps/tenancy/management/commands/
#           seed_demo.py · 07-frontend PlanWizard step 7/8 + PlansTab confirm
# ───────────────────────────────────────────────────────
"""DEF-494 — a rate plan cannot be published without saying when it starts.

THE RULING THIS FILE PINS (PO, 2026-08-28)
------------------------------------------
The question put was *"a rate plan has been published, but nobody ever typed a
start date for it — should it be charging customers?"* The PO took neither of
the two obvious answers and chose a third: **require a date to publish** — *"you
cannot publish a plan without saying when it starts, so the situation stops
existing; any published plan today that has no date gets one."*

WHY IT MATTERED MORE THAN IT LOOKED
-----------------------------------
`rating.selectors.plan_ref` — what the bill run reads — filters on
`status="published"` and consults **no date at all**, so an undated published
plan bills **forever**. `resolution.PlanVersion.in_force_on` requires a stated
date, so the SAME plan is in force **never** and R1 refuses the account. Both
are defensible readings of BR-RAT-007 and the rule chooses neither.

Measured on the seeded Brazos Bend tenant at the tip, through the real bill run
and the real pricing-shadow report: **47 of 47 accounts refused at R1** on each
of three runs. R1 gates every later step, so R2–R7 could not be compared on a
single account.

⚠ WHAT IS *NOT* CLAIMED HERE
-----------------------------
Nothing in this file says which reading of an absent date was RIGHT. The state
was removed rather than adjudicated, which is what lets both engines agree at R1
**without either changing its meaning** — `plan_ref` and `in_force_on` are
untouched by this work.
"""

import importlib.util
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection

from apps.rating import models as rating_models
from apps.rating import sample_data as rating_sample_data
from apps.rating import services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared rating fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The date the two schedule helpers in `test_us_rat_helpers` already state, so
#: a plan built here starts the day its own prices do.
STARTS = "2026-08-01"


def _migration():
    """`rating/0024` as a module.

    Loaded BY PATH because the module name starts with a digit and cannot be
    imported by name. Asserting against the migration's OWN function rather
    than a copy of its rule is deliberate: a test that restates the arithmetic
    passes when the two drift together, which is the failure mode this whole
    defect is an instance of.
    """
    path = (
        Path(__file__).resolve().parents[1]
        / "apps"
        / "rating"
        / "migrations"
        / "0024_def494_publish_needs_a_start_date.py"
    )
    spec = importlib.util.spec_from_file_location("rating_migration_0024", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_backfill():
    """The migration's data half, over the real app registry."""
    _migration().state_when_every_published_plan_started(
        django_apps, SimpleNamespace(connection=connection)
    )


def _a_plan(env, *, code, dated):
    """A DRAFT plan complete enough to publish, dated or not."""
    schedule = env.flat_schedule(f"{code} water", "water")
    overrides = {"effective_from": STARTS} if dated else {}
    return env.plan(
        f"{code} plan",
        code,
        [{"service": "water", "base_charge": "8", "tariff": schedule["id"]}],
        **overrides,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE GATE — what a person now cannot do
# ══════════════════════════════════════════════════════════════════════════
def test_def494_tc1_publishing_a_plan_with_no_start_date_is_refused(env):
    """The ruling, as one refusal.

    ⚠ **THE REFUSAL IS AT THE WRITE PATH, NOT ON A SCREEN.** A screen-only
    check leaves every other caller — the API, a seeder, an import — able to
    create exactly the state the PO ruled out of existence.
    """
    plan = _a_plan(env, code="UNDATED", dated=False)
    assert plan["effective_from"] is None
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as refusal:
            services.publish_plan(env.admin, plan["id"])
        assert refusal.value.message_key == "rating.plans.no_effective_from"
        assert refusal.value.br_ref == "BR-RAT-890"
        # And it did NOT publish — a refusal that half-writes is worse than none.
        assert rating_models.RatePlan.objects.get(pk=plan["id"]).status == "draft"


def test_def494_tc2_publishing_a_dated_plan_still_works(env):
    """The other half of the same rule: state a date and the plan publishes.

    Without this, TC1 is also passed by a `publish_plan` that refuses
    everything.
    """
    plan = _a_plan(env, code="DATED", dated=True)
    with tenant_ctx(env.tenant):
        published = services.publish_plan(env.admin, plan["id"])
    assert published["status"] == "published"
    assert published["effective_from"] == STARTS


def test_def494_tc3_the_completeness_refusals_still_come_first(env):
    """A plan with no services is told about its services, not about a date.

    BR-RAT-025's two refusals describe the plan's CONTENT; this one says WHEN
    the content applies. Ordering them the other way round would answer a
    question the operator has not reached yet.
    """
    plan = env.plan("Empty plan", "EMPTY", [])
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as refusal:
            services.publish_plan(env.admin, plan["id"])
        assert refusal.value.message_key == "rating.plans.no_services"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE GATE CANNOT BE WALKED AROUND
# ══════════════════════════════════════════════════════════════════════════
def test_def494_tc4_a_published_plan_cannot_have_its_start_date_cleared(env):
    """⚠ **WITHOUT THIS THE PUBLISH GATE IS DECORATIVE.**

    Publish the plan, then blank the column one request later and the state the
    PO removed is back — on a plan that is already billing customers.
    """
    plan = _a_plan(env, code="KEEPS", dated=True)
    with tenant_ctx(env.tenant):
        services.publish_plan(env.admin, plan["id"])
        with pytest.raises(errors.ValidationError) as refusal:
            services.update_plan(
                env.admin, plan["id"], {"effective_from": None, "reason": "trying it on"}
            )
        assert refusal.value.message_key == "rating.plans.effective_from_required"
        assert rating_models.RatePlan.objects.get(pk=plan["id"]).effective_from is not None


def test_def494_tc5_a_draft_may_still_be_left_undated(env):
    """BR-RAT-031's save-and-come-back is untouched.

    A draft prices nothing, so a half-typed one is a work-in-progress and not a
    defect. The gate is at PUBLISH, which is where the ruling put it.
    """
    plan = _a_plan(env, code="RESUMABLE", dated=True)
    with tenant_ctx(env.tenant):
        cleared = services.update_plan(env.admin, plan["id"], {"effective_from": None})
    assert cleared["status"] == "draft"
    assert cleared["effective_from"] is None


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE BACKFILL — which date an existing published plan gets, and why
# ══════════════════════════════════════════════════════════════════════════
def test_def494_tc6_an_existing_undated_plan_is_dated_from_its_own_schedule(env):
    """The migration's rule, on the shape a migrated tenant actually has.

    **The date is the earliest `effective_from` among the ACTIVATED versions of
    the rate schedules the plan itself binds** — a date a human at the utility
    typed, about this plan's own prices, that the product already stores.

    Not today (that would put a plan's own issued bills outside its effective
    window — the seeded tenant has 90 of them starting 2026-06-01), and not the
    plan's creation date (which claims it priced periods it never priced).
    """
    plan = _a_plan(env, code="LEGACY", dated=True)
    with tenant_ctx(env.tenant):
        services.publish_plan(env.admin, plan["id"])
        # The shape a tenant provisioned before 2026-08-28 is in: published,
        # billing, and carrying no date at all.
        rating_models.RatePlan.objects.filter(pk=plan["id"]).update(effective_from=None)
        _run_backfill()
        row = rating_models.RatePlan.objects.get(pk=plan["id"])
    # `flat_schedule` states 2026-08-01, so that is the day this plan's own
    # prices began and therefore the day the plan has been in force since.
    assert row.effective_from == date(2026, 8, 1)


def test_def494_tc7_the_backfill_leaves_drafts_and_archived_plans_alone(env):
    """Only PUBLISHED plans are dated.

    A draft with no date is exactly what a draft is, and an archived plan
    assigns to nobody — dating either would invent a fact about a plan no
    account can be put on.
    """
    draft = _a_plan(env, code="STILLDRAFT", dated=False)
    archived = _a_plan(env, code="GONE", dated=True)
    with tenant_ctx(env.tenant):
        services.publish_plan(env.admin, archived["id"])
        services.archive_plan(env.admin, archived["id"])
        rating_models.RatePlan.objects.filter(pk=archived["id"]).update(effective_from=None)
        _run_backfill()
        assert rating_models.RatePlan.objects.get(pk=draft["id"]).effective_from is None
        assert rating_models.RatePlan.objects.get(pk=archived["id"]).effective_from is None


def test_def494_tc8_the_backfill_is_idempotent_and_never_moves_a_stated_date(env):
    """A second run finds nothing, and a date a utility typed is never revisited.

    The migration filters on `effective_from IS NULL`, so a plan that already
    says when it starts — including one a utility deliberately dated in the
    future — is not touched by a replay.
    """
    plan = _a_plan(env, code="CHOSEN", dated=True)
    chosen = date.today() + timedelta(days=90)
    with tenant_ctx(env.tenant):
        services.publish_plan(env.admin, plan["id"])
        rating_models.RatePlan.objects.filter(pk=plan["id"]).update(effective_from=chosen)
        _run_backfill()
        _run_backfill()
        assert rating_models.RatePlan.objects.get(pk=plan["id"]).effective_from == chosen


def test_def494_tc9_the_backfill_writes_no_invoice_and_no_invoice_line(env):
    """CLAUDE.md hard rule 4, asserted rather than asserted-in-prose.

    Backfilling a plan's date must not restate a bill already issued. It cannot:
    this touches `rate_plans` and nothing else, and the LIVE pricing path does
    not read the column at all.
    """
    from apps.billing import models as billing_models

    plan = _a_plan(env, code="NOBILLS", dated=True)
    with tenant_ctx(env.tenant):
        services.publish_plan(env.admin, plan["id"])
        rating_models.RatePlan.objects.filter(pk=plan["id"]).update(effective_from=None)
        before = (
            billing_models.Invoice.objects.count(),
            billing_models.InvoiceLine.objects.count(),
        )
        _run_backfill()
        after = (
            billing_models.Invoice.objects.count(),
            billing_models.InvoiceLine.objects.count(),
        )
    assert before == after


def test_def494_tc10_a_plan_whose_schedules_carry_no_dated_version_still_gets_a_date(env):
    """The fallback chain, at its narrowest rung.

    A published plan always has a bound schedule (`publish_plan` refuses
    otherwise), so this only reaches a plan whose schedules hold no ACTIVATED
    version at all — BR-RAT-031 makes a NULL `tariff_versions.effective_from`
    the resumable draft, and a draft has never priced anything, so it cannot
    date a plan. The plan is then dated from its v1 filing record, and failing
    that from its own creation day. **It is never left NULL**, because a NULL is
    the state the ruling removed.
    """
    plan = _a_plan(env, code="NOVERSION", dated=True)
    with tenant_ctx(env.tenant):
        services.publish_plan(env.admin, plan["id"])
        rating_models.TariffVersion.objects.filter(tenant=env.tenant).update(effective_from=None)
        rating_models.RatePlan.objects.filter(pk=plan["id"]).update(effective_from=None)
        _run_backfill()
        row = rating_models.RatePlan.objects.get(pk=plan["id"])
    assert row.effective_from is not None


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE SEEDER — a fresh tenant never reproduces the state
# ══════════════════════════════════════════════════════════════════════════
def test_def494_tc11_the_sample_plans_state_when_they_start(env):
    """The fixture's plans are dated, and dated to the day it starts billing.

    The sample tenant issues its first bills for the June 2026 period. A plan
    dated any later would be a plan that does not cover the bills the fixture
    goes on to issue on it.

    Asserted on what `_plan_payloads` EMITS, not on the constant alone: a
    constant nothing reads is exactly the shape of the defect this closes.
    """
    from core import sample_fixture as fixture

    assert rating_sample_data.PLAN_EFFECTIVE_FROM == fixture.PERIODS[0]["start"].isoformat()
    with tenant_ctx(env.tenant):
        payloads = rating_sample_data._plan_payloads(
            {
                rating_sample_data.SCHEDULE_WATER_RES: "01a04780-0000-7000-8000-000000000001",
                rating_sample_data.SCHEDULE_WATER_COM: "01a04780-0000-7000-8000-000000000002",
            }
        )
    assert len(payloads) == 2, payloads
    for payload in payloads:
        assert payload["effective_from"] == rating_sample_data.PLAN_EFFECTIVE_FROM


def test_def494_tc12_the_demo_plans_state_when_they_start():
    """`seed_demo`'s three plans take the same date as their own schedules."""
    from apps.tenancy.management.commands import seed_demo

    assert seed_demo.SCHEDULE_EFFECTIVE_FROM == "2026-08-01"
