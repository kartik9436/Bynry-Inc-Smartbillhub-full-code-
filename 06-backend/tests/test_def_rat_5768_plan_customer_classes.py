# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5768 — a plan could hold only ONE customer class, so a
#          utility pricing Residential and Municipal alike had to write the
#          plan twice.
# Ruling:  PO 2026-09-19, verbatim: *"your understanding is correct - we have
#          all option anyway in drop down list - that is default"* — one class
#          becomes a list of one, NULL becomes the empty list, and the empty
#          list means EVERY class.
# Rules:   DEF-273 / BR-RAT-108 (`charges.applies_to_customer_classes` — the
#          sibling shape this matches: a JSON list where NULL or [] means EVERY
#          class) · CLAUDE.md hard rule 1 (tenant scoping) · NFR-3 (the list
#          filter stays in SQL)
# Note:    ⚠ The `__contains` lookup Django offers for a JSONField **raises
#          NotSupportedError on SQLite**, measured in this container, and
#          `config/settings/test.py` hardcodes in-memory SQLite — hard-won law
#          14's trap with the two databases the other way round. The filter is
#          a text cast for that reason and this file is where it is proved.
# ───────────────────────────────────────────────────────
"""DEF-RAT-5768 — a plan's customer class is a LIST, and empty means every one."""

import pytest

from apps.rating import models, selectors, services
from core import errors
from core.pagination import ListParams

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

RES = "0198c1aa-0000-7000-8000-00000000c1a1"
COM = "0198c1aa-0000-7000-8000-00000000c1a2"
MUN = "0198c1aa-0000-7000-8000-00000000c1a3"


def _plan(env, code, classes):
    return env.plan("Plan " + code, code, [], account_type_ids=classes)


def test_the_column_is_gone_and_the_list_is_what_exists(env):
    """⚠ THE CONTROL, and it is the one that makes the rest mean anything: if
    the scalar were still on the model, every case below could pass while a
    second source of truth sat beside it."""
    names = {field.attname for field in models.RatePlan._meta.concrete_fields}
    assert "account_type_ids" in names
    assert "account_type_id" not in names, (
        "rating/0038 replaces the scalar; leaving it would give one question "
        "two stored answers, which is the defect and not the fix"
    )


def test_a_plan_can_name_two_classes(env):
    plan = _plan(env, "TWO", [RES, MUN])
    with tenant_ctx(env.tenant):
        detail = selectors.plan_detail(plan["id"])
    assert detail["account_type_ids"] == [RES, MUN]


def test_naming_nothing_stores_the_empty_list_and_means_every_class(env):
    """The PO's own default: *"we have all option anyway in drop down list"*."""
    plan = env.plan("Every class", "EVERY", [])
    with tenant_ctx(env.tenant):
        detail = selectors.plan_detail(plan["id"])
    assert detail["account_type_ids"] == []


def test_an_explicit_null_is_the_same_fact_as_an_empty_list(env):
    """`null` and `[]` are one answer here and are stored as one. Keeping them
    apart would give a screen a distinction it cannot draw."""
    plan = env.plan("Null class", "NULLC", [], account_type_ids=None)
    with tenant_ctx(env.tenant):
        assert selectors.plan_detail(plan["id"])["account_type_ids"] == []


def test_the_whole_set_is_replaced_never_merged(env):
    """The chip control means *these and no others*; a merge would leave a
    removed class attached for ever."""
    plan = _plan(env, "REPL", [RES, COM])
    with tenant_ctx(env.tenant):
        services.update_plan(env.admin, plan["id"], {"account_type_ids": [MUN]})
        assert selectors.plan_detail(plan["id"])["account_type_ids"] == [MUN]


def test_a_duplicate_class_is_refused_by_name(env):
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        env.plan("Dupe", "DUPE", [], account_type_ids=[RES, RES])
    assert any(
        error["message_key"] == "rating.plans.duplicate_customer_class"
        for error in caught.value.field_errors
    )


def test_a_non_list_is_refused_by_name(env):
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        env.plan("Scalar", "SCALAR", [], account_type_ids=RES)
    assert any(
        error["message_key"] == "rating.plans.classes_not_a_list"
        for error in caught.value.field_errors
    )


def test_the_retired_scalar_key_is_refused_rather_than_ignored(env):
    """A caller still sending `account_type_id` must find out. `_reject_unknown`
    names it; silently dropping it would store a plan for every class while the
    caller believed it had narrowed one."""
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError):
        env.plan("Old key", "OLDKEY", [], account_type_id=RES)


# ══════════════════════════════════════════════════════════════════════════
# THE LIST FILTER — and the SQLite trap that would have taken it down
# ══════════════════════════════════════════════════════════════════════════

def _filtered(env, class_id):
    params = ListParams(q="", filters={"customer_class": class_id}, sort=None, dir="asc")
    with tenant_ctx(env.tenant):
        return {row["code"] for row in selectors.plan_list(params)}


def test_the_filter_finds_a_plan_that_names_the_class(env):
    _plan(env, "RESONLY", [RES])
    _plan(env, "COMONLY", [COM])
    assert "RESONLY" in _filtered(env, RES)
    assert "COMONLY" not in _filtered(env, RES)


def test_the_filter_also_finds_the_EVERY_CLASS_plans(env):
    """⚠ **THIS ARM DID NOT EXIST UNDER THE OLD COLUMN AND IS THE RULING, NOT A
    PORT.** A plan for every class IS a plan for Residential; leaving it out
    would hide, from a clerk filtering on Residential, every plan that serves
    them."""
    env.plan("Every class", "EVERY", [])
    _plan(env, "COMONLY", [COM])
    found = _filtered(env, RES)
    assert "EVERY" in found
    assert "COMONLY" not in found


def test_the_filter_matches_a_plan_naming_SEVERAL_classes(env):
    _plan(env, "BOTH", [RES, MUN])
    assert "BOTH" in _filtered(env, RES)
    assert "BOTH" in _filtered(env, MUN)
    assert "BOTH" not in _filtered(env, COM)


def test_the_contains_lookup_this_filter_deliberately_avoids_is_unsupported():
    """⚠ **THE MEASUREMENT, PINNED — hard-won law 14.**

    This is not a style note. `account_type_ids__contains=[uuid]` is the
    obvious spelling, it works on PostgreSQL, and on the SQLite this suite runs
    on it raises. A filter written that way would pass review and take the plan
    list down on every test run. If this case ever stops raising, the cast in
    `selectors._plans_reaching_class` may be simplified — and until then it may
    not.
    """
    from django.db.utils import NotSupportedError

    with pytest.raises(NotSupportedError):
        list(models.RatePlan.objects.filter(account_type_ids__contains=[RES]))


# ══════════════════════════════════════════════════════════════════════════
# THE OTHER HALF OF THE TRUTH TABLE — `planWizardBetaWalk.dom.test.tsx`
# ══════════════════════════════════════════════════════════════════════════

def test_the_trigger_table_the_screen_is_held_in_step_with():
    """**HALF OF A PAIR. The other half is
    `07-frontend/src/features/rating/planWizardBetaWalk.dom.test.tsx`, case
    *THE TRUTH TABLE*, and it carries the same eight rows.**

    `BR-RAT-730` is now stated in THREE places: `resolution.rides_a_periodic
    _bill` (R4), `selectors._rides_a_periodic_bill` (the live fee path,
    `DEF-RAT-5784`) and `chargeApplication` in the plan wizard, which draws the
    *When it applies* column on step 4. The first two are held in step by
    `test_def_rat_5782_plan_named_codes_honour_the_trigger.py` and deliberately
    do not call each other, because the pricing shadow compares them and *"a
    comparison whose two sides are the same function is a check that cannot
    fail"*. The third is TypeScript and can call neither.

    ⚠ **SO THIS TABLE IS THE PIN, AND IT IS WRITTEN OUT RATHER THAN DERIVED.**
    A generated table would drift with the function it was generated from,
    which is the failure it exists to prevent.

    ⚠ **TWO ROWS DIFFER FROM THE SCREEN'S ANSWER, BOTH ON PURPOSE:** this
    selector never sees an `is_base` code (excluded one step earlier by
    `BR-RAT-088` — letting it in bills the base twice), and it OMITS an
    `auto_apply` non-recurring code rather than refusing it, because a new
    refusal on the live fee path can stop a bill run. The screen names that
    case instead, which is R4's own disposition. Both are marked in both files.
    """
    from apps.rating.selectors import _rides_a_periodic_bill

    class _Code:
        def __init__(self, auto_apply, charge_type):
            self.auto_apply = auto_apply
            self.charge_type = charge_type

    # (auto_apply, charge_type, rides) — the screen's `is_base` rows are not
    # here because this function is never asked about one.
    table = [
        (True, "recurring", True),
        (False, "recurring", False),   # recurring but nobody applies it
        (False, "one_time", False),
        (False, "penalty", False),     # LATE reaches a bill by its OWN route
        (False, "refundable", False),
        (True, "penalty", False),      # the CONFLICT — omitted here, NAMED on screen
    ]
    for auto_apply, charge_type, rides in table:
        assert _rides_a_periodic_bill(_Code(auto_apply, charge_type)) is rides, (
            f"auto_apply={auto_apply} charge_type={charge_type}"
        )


# ══════════════════════════════════════════════════════════════════════════
# DEF-RAT-5799 — the backfill that RLS silently emptied
# ══════════════════════════════════════════════════════════════════════════

def test_a_tenant_table_backfill_must_enter_a_tenant_first():
    """**THE CASE THAT WOULD HAVE CAUGHT `DEF-RAT-5799`, AND IT IS A SOURCE
    CHECK ON PURPOSE.**

    `rating/0038`'s `RunPython` did `RatePlan.objects.all()` with no tenant
    context. On PostgreSQL `rate_plans` carries RLS `FORCE` and the migration
    role does not bypass it, so that queryset answers ZERO ROWS: the loop ran
    over nothing, every row kept the column default `[]`, and three plans that
    named a customer class came out naming none — which under `DEF-RAT-5768`
    means EVERY class, the opposite of what they said.

    ⚠ **NO BEHAVIOURAL TEST ON THIS SUITE COULD HAVE SEEN IT.**
    `config/settings/test.py` hardcodes SQLite and SQLite has no row-level
    security, so the same loop sees every row here and every case over the
    migration passes green — CLAUDE.md hard-won law 14 with RLS in place of an
    aborted transaction. A test that cannot fail on the thing it is aimed at is
    worth less than one that reads the source and says what is missing, so this
    reads the source.

    It is written as *every migration in this module that touches a tenant
    table inside `RunPython` must set `app.tenant_id` first*, rather than as a
    check on one file, because the next one to get this wrong will be a
    different file.
    """
    import pathlib, re

    here = pathlib.Path(__file__).resolve().parents[1] / "apps" / "rating" / "migrations"
    offenders = []
    for path in sorted(here.glob("0*.py")):
        text = path.read_text(encoding="utf-8")
        if "RunPython" not in text:
            continue
        # Does it read a TENANT table through the historical model API?
        touches = re.search(r'apps\.get_model\(\s*["\']rating["\']', text) is not None
        if not touches:
            continue
        enters = "app.tenant_id" in text
        if not enters:
            offenders.append(path.name)
    assert offenders == ["0038_def_rat_5768_plan_customer_classes.py"], (
        "a rating migration runs Python over a tenant table without entering a "
        "tenant. On PostgreSQL that reads ZERO rows and writes nothing, and on "
        "the SQLite this suite uses it reads everything — so it passes here and "
        "loses data there (DEF-RAT-5799). Expected only the known one: %s" % offenders
    )


def test_the_repair_migration_exists_and_only_fills_an_empty_list():
    """`rating/0039` repairs what `0038` emptied, and the two properties that
    make it safe to run on any host are asserted from its source: it enters a
    tenant, and it never overwrites a list that already says something."""
    import pathlib

    path = (pathlib.Path(__file__).resolve().parents[1] / "apps" / "rating" / "migrations"
            / "0039_def_rat_5799_class_backfill_under_rls.py")
    assert path.exists(), "the repair for DEF-RAT-5799 is missing"
    text = path.read_text(encoding="utf-8")
    assert "app.tenant_id" in text
    assert "if plan.account_type_ids:" in text and "continue" in text
    # …and it reads the filed snapshot, because 0038 dropped the column it
    # would otherwise have read.
    assert "plan_versions" in text.lower() or "PlanVersion" in text
