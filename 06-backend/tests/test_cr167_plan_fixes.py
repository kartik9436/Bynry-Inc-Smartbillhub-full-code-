# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 follow-up, lane PLAN-FIXES (2026-10-03) — the server
#          half of "complete these and fix bugs" on the plans redesign.
# Defects: DEF-RAT-9352 (Duplicate: a copy act) · DEF-RAT-9360 (Audit words
#          read like data) · DEF-RAT-9363 (a correction's Audit row does not say
#          what it changed)
# Rules:   BR-RAT-030 (a copy is a DRAFT) · BR-RAT-1066 / 1067 (versions;
#          name-and-details is the SAME version) · B14 rule 31 · hard rule 2
# ───────────────────────────────────────────────────────
"""Each case was written RED against the tip before the fix; the failures
are quoted in `CR-167-BRC10` §15. Runs on the default suite AND on
PostgreSQL (`--ds=config.settings.pgtest`) — the audit read is a SQL UNION
over the stored table, so the real audit sink is put back for those cases."""

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import models, plan_reads, plan_versioning, plan_writes, seams
from apps.rating import discounts as discount_models
from core import errors

from tests.test_cr167_plans_round2 import _new_version, _published
from tests.test_cr167_plans_round2 import _today  # noqa: F401 — the autouse "today"
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture()
def stored_audit():
    """The real audit store, so `plan_audit_queryset` has rows to UNION."""
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


def _keys(exc):
    return {(entry["field"], entry["message_key"]) for entry in exc.value.field_errors}


# ── DEF-RAT-9352 · Duplicate ────────────────────────────────────────────────


def test_def_rat_9352__a_duplicate_is_a_new_DRAFT_of_the_version_in_force(env):
    """v1 ($10.00 floor) is in force on 10/03/2026 and v2 ($12.00) starts
    01/01/2027. The copy offers what the plan offers TODAY: v1's terms and
    bindings, as a draft v1 of a new plan, with no units and no dates."""
    plan, schedule = _published(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        before_rows = models.PlanService.all_versions.filter(rate_plan_id=plan["id"]).count()
        copy = plan_writes.duplicate(env.admin, plan["id"], {"name": "Residential City Plan 2027", "code": "RCP-27"})
        row = models.RatePlan.objects.get(pk=copy["id"])
        versions = list(models.PlanVersion.objects.filter(rate_plan=row))
        bound = list(models.PlanRateSchedule.all_versions.filter(rate_plan=row).values_list("tariff_id", flat=True))
        services = list(models.PlanService.all_versions.filter(rate_plan=row).values_list("service__code", flat=True))
        units = models.UnitPlanAssignment.objects.filter(rate_plan=row).count()
        after_rows = models.PlanService.all_versions.filter(rate_plan_id=plan["id"]).count()
    assert copy["id"] != plan["id"]
    assert (row.name, row.code, row.status) == ("Residential City Plan 2027", "RCP-27", "draft")
    assert row.minimum_bill_amount == Decimal("10.000000")
    assert row.effective_from is None and row.effective_to is None
    assert [(v.version_no, v.status) for v in versions] == [(1, plan_versioning.VERSION_DRAFT)]
    assert services == ["water"]
    assert [str(one) for one in bound] == [str(schedule["id"])]
    assert units == 0
    assert before_rows == after_rows  # the source is read, never written


def test_def_rat_9352__the_late_fee_charge_codes_and_taxes_travel(env):
    plan, _ = _published(env)
    with tenant_ctx(env.tenant):
        source = models.RatePlan.objects.get(pk=plan["id"])
        copy = plan_writes.duplicate(env.admin, plan["id"], {"name": "Copy", "code": "COPY"})
        row = models.RatePlan.objects.get(pk=copy["id"])
        source_rules = sorted(
            str(one) for one in models.PlanChargeRule.all_versions.filter(rate_plan=source).values_list("charge_id", flat=True)
        )
        copy_rules = sorted(
            str(one) for one in models.PlanChargeRule.all_versions.filter(rate_plan=row).values_list("charge_id", flat=True)
        )
        source_taxes = models.PlanTaxRule.all_versions.filter(rate_plan=source).count()
        copy_taxes = models.PlanTaxRule.all_versions.filter(rate_plan=row).count()
    assert row.late_fee_charge_id == source.late_fee_charge_id
    assert copy_rules == source_rules
    assert copy_taxes == source_taxes


def test_def_rat_9352__a_new_name_and_code_are_required_and_must_be_free(env):
    plan, _ = _published(env)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as missing:
            plan_writes.duplicate(env.admin, plan["id"], {})
        with pytest.raises(errors.ValidationError) as taken:
            plan_writes.duplicate(env.admin, plan["id"], {"name": "Residential City Plan", "code": "rcp"})
        count = models.RatePlan.objects.count()
    assert _keys(missing) == {("name", "rating.required"), ("code", "rating.required")}
    assert ("code", "rating.plans.duplicate_code") in _keys(taken)
    assert ("name", "rating.plans.duplicate_name") in _keys(taken)
    assert count == 1


# ── DEF-RAT-9360 · Audit words ──────────────────────────────────────────────


def test_def_rat_9360__money_reads_with_its_currency(env):
    with tenant_ctx(env.tenant):
        before, after = plan_reads.words_diff(
            {"base_charges": "19.000000", "minimum_bill_amount": "10.000000"},
            {"base_charges": "20.000000", "minimum_bill_amount": "12.000000"},
        )
    assert before == "Base charges: $19.00 · Minimum bill: $10.00"
    assert after == "Base charges: $20.00 · Minimum bill: $12.00"


def test_def_rat_9360__a_list_fact_reads_by_name_and_an_empty_one_as_None(env):
    with tenant_ctx(env.tenant):
        before, after = plan_reads.words_diff(
            {"charge_rules": [], "reason": "x"},
            {"charge_rules": [{"code": "RECON", "name": "Reconnection fee"}], "reason": "Council order"},
        )
    assert before == "Charge codes: None"
    assert after == "Charge codes: Reconnection fee"


def test_def_rat_9360__a_status_reads_as_the_pill_does(env):
    with tenant_ctx(env.tenant):
        before, after = plan_reads.words_diff({"status": "draft"}, {"status": "published"})
    assert (before, after) == ("Status: Draft", "Status: Published")


def test_def_rat_9360__a_same_version_edit_names_the_version_IN_FORCE(env, stored_audit):
    """After v2 is filed from 01/01/2027, a *Name and details* edit today
    changes v1 — the row said *v2* (the head counter)."""
    plan, _ = _published(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        plan_writes.patch(env.admin, plan["id"], {"details": {"description": "Homes inside the city."}})
        rows = plan_reads.plan_audit_rows(list(plan_reads.plan_audit_queryset(plan["id"], "plan")))
    edited = [row for row in rows if row["change"] == "edited"]
    assert len(edited) == 1
    assert edited[0]["version"]["version"] == 1
    assert edited[0]["after_display"] == "Description: Homes inside the city."


# ── DEF-RAT-9363 · what a correction changed ─────────────────────────────────


def test_def_rat_9363__a_correction_names_exactly_the_field_it_moved(env, stored_audit):
    """v1 + v2 ($12.00 from 01/01/2027); *Fix a mistake* on v1 turns budget
    billing on. The row must say *Budget billing: No → Yes* — not v2's
    minimum, not the reason, not *Version terms: —*."""
    plan, _ = _published(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        plan_writes.correct(
            env.admin, plan["id"], {"details": {}, "version": 1, "budget_billing": True, "reason": "Budget billing was ticked"}
        )
        rows = plan_reads.plan_audit_rows(list(plan_reads.plan_audit_queryset(plan["id"], "plan")))
    fixed = [row for row in rows if row["change"] == "correction"]
    assert len(fixed) == 1
    assert fixed[0]["before_display"] == "Budget billing: No"
    assert fixed[0]["after_display"] == "Budget billing: Yes"
    assert fixed[0]["reason"] == "Budget billing was ticked"
    assert fixed[0]["version"]["version"] == 1


def test_def_rat_9363__a_corrected_minimum_reads_the_VERSIONs_figures(env, stored_audit):
    plan, _ = _published(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        plan_writes.correct(
            env.admin, plan["id"], {"details": {}, "version": 1, "minimum_bill_amount": "11.00", "reason": "Typed 10 for 11"}
        )
        rows = plan_reads.plan_audit_rows(list(plan_reads.plan_audit_queryset(plan["id"], "plan")))
    fixed = [row for row in rows if row["change"] == "correction"][0]
    assert fixed["before_display"] == "Minimum bill: $10.00"
    assert fixed["after_display"] == "Minimum bill: $11.00"


# ── DEF-RAT-9504 · an every-class plan names which class pays which base ────


def test_def_rat_9504__an_ambiguous_base_names_each_codes_classes(env):
    """A plan for EVERY class (no class ticked) and two water base codes, one
    per class: the bill picks by the account's class, so the screen cannot
    show one figure — but it must say which code each class pays."""
    env.enable("water")
    env.declare_base_charge_code("water")
    with tenant_ctx(env.tenant):
        first = models.Charge.objects.filter(is_base=True, service__code="water").order_by("code").first()
        first.applies_to_customer_classes = ["residential"]
        first.save(update_fields=["applies_to_customer_classes"])
        second = models.Charge.objects.get(pk=first.pk)
        second.pk = None
        second.id = None
        second.code = f"{first.code}-COM"
        second.applies_to_customer_classes = ["commercial"]
        second._state.adding = True
        second.save()
        names = seams.account_type_names_by_code()
        block = plan_reads._base_block("water", None, [None], date(2026, 10, 3), {})
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): a schedule naming no
    # base code is no longer `ambiguous` with each class's code listed — that
    # listing was the pool. It bills `$0.00` and reads *Choose a base code*.
    assert block["state"] == "not_named"
    assert block["options"] == [] and block["codes"] == []
    assert block["flat_display"] == "0.00"
    assert names is not None
