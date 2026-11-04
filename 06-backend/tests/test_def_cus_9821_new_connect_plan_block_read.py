# ── Trace ──────────────────────────────────────────────
# Change:  DEF-CUS-9821 — PO request 2026-10-06: New Connect step 2's "This
#          plan" block shows every component the plan binds (the approved
#          drawing, claude.ai/artifact/9poRZzcU1ooxCw9A78jXgy).
# Rules:   B14 rule 31 (names, never ids) · CLAUDE.md hard rule 2 (nothing
#          here prices anything) · decision log 2026-10-06 "NEW CONNECT STEP 2:
#          THE 'THIS PLAN' BLOCK IS REDRAWN …" judgments 2 and 4
# Tests:   this file
# Impacts: apps/rating/plan_reads.py (`_base_block`, `_services`, `_taxes`,
#          `_deposits`, `_discounts`, `plan_sections`) · apps/rating/api.py
#          (`GET /plans/{id}?classes=`)
# ───────────────────────────────────────────────────────
"""The five facts the drawing prints that the plan read did not serve, and the
account-class narrowing of the base.

WHAT WOULD MAKE THESE PASS WRONGLY: a `named` computed from "a base code was
found" rather than "the schedule names one" passes the first half and fails
`test_a_schedule_naming_no_base_code_says_so`, because the pooled code is still
found there. A `?classes=` that narrowed nothing passes the absent case and
fails the residential one (it stays *ambiguous*).
"""

from __future__ import annotations

import pytest

from apps.rating import models, plan_reads, plan_writes, seams
from apps.rating import discount_services
from apps.rating import discounts as discount_models

from tests.test_cr167_plans_round2 import _contract, _late_fee_code
from tests.test_cr167_plans_round2 import _today  # noqa: F401 — the autouse "today" (10/03/2026)
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db


def _schedule(env):
    env.enable("water")
    _late_fee_code(env)
    return env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)


def _plan(env, schedule, code="NC-PLAN", **extra):
    with tenant_ctx(env.tenant):
        return plan_writes.create(
            env.admin,
            _contract(schedule, details={"name": f"Plan {code}", "code": code, "customer_classes": []}, publish=True, **extra),
        )


def _unname(schedule):
    """The schedule's version names no base code — the drawing's Battery."""
    models.TariffVersion.objects.filter(tariff_id=schedule["id"]).update(base_charge_code=None)


def _class_name(code):
    return seams.account_type_names_by_code()[code]


def test_a_schedule_that_names_its_base_code_says_so_with_its_classes(env):
    schedule = _schedule(env)
    plan = _plan(env, schedule)
    with tenant_ctx(env.tenant):
        base = plan_reads.plan_sections(plan["id"])["services"][0]["base"]
    assert base["state"] == "ok"
    assert base["named"] is True
    assert base["classes"] == []  # every class


def test_a_schedule_naming_no_base_code_says_so(env):
    schedule = _schedule(env)
    plan = _plan(env, schedule)
    with tenant_ctx(env.tenant):
        _unname(schedule)
        base = plan_reads.plan_sections(plan["id"])["services"][0]["base"]
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): this read *"The pooled
    # code still serves (the bill charges it)"* and asserted `ok`. There is no
    # pool any more — a schedule naming none bills `$0.00` with the warning.
    assert base["state"] == "not_named"
    assert base["named"] is False
    assert base["code"] is None
    assert base["flat_display"] == "0.00"


def test_the_accounts_class_narrows_the_base_and_nothing_else(env):
    """An every-class plan, water base codes for Residential ($8.00) and
    Commercial ($15.00): the plan alone cannot say which; a Residential
    account's read can."""
    schedule = _schedule(env)
    env.charge(
        "BASE-W-RES",
        "Water base, residential",
        service="water",
        charge_type="recurring",
        amount="8.00",
        is_base=True,
        applies_to_customer_classes=["residential"],
    )
    plan = _plan(env, schedule)
    with tenant_ctx(env.tenant):
        models.Charge.objects.filter(code="BASE-W").update(applies_to_customer_classes=["commercial"])
        _unname(schedule)
        every = plan_reads.plan_sections(plan["id"])
        residential = plan_reads.plan_sections(plan["id"], classes=["residential"])
        name = _class_name("residential")
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): an UNNAMED schedule
    # used to be narrowed to BASE-W-RES by the account's class — a code taken
    # from the charge-code list by class, which the ruling forbids. Unnamed, it
    # is `$0.00` for every class; NAMED, it is the code the schedule names.
    assert every["services"][0]["base"]["state"] == "not_named"
    assert residential["services"][0]["base"]["state"] == "not_named"
    with tenant_ctx(env.tenant):
        models.TariffVersion.objects.filter(tariff_id=schedule["id"]).update(
            base_charge_code=models.Charge.objects.get(code="BASE-W-RES")
        )
        residential = plan_reads.plan_sections(plan["id"], classes=["residential"])
    base = residential["services"][0]["base"]
    assert base["state"] == "ok"
    assert base["code"]["code"] == "BASE-W-RES"
    assert base["flat_display"] == "8.00"
    assert base["classes"] == [name]
    # Charge codes, deposits and taxes are the plan's, whatever the class.
    assert residential["charge_codes"] == every["charge_codes"]
    assert residential["taxes"] == every["taxes"]


def _get(env, plan_id, query):
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.rating import api as rating_api

    request = APIRequestFactory().get(f"/api/t/plans/{plan_id}", query)
    force_authenticate(request, user=env.owner)
    request.tenant_role = "system_admin"
    request.tenant_id = env.tenant.id
    with tenant_ctx(env.tenant):
        response = rating_api.plan_item(request, str(plan_id))
    assert response.status_code == 200, getattr(response, "data", None)
    return response.data


def test_the_api_passes_classes_through(env):
    schedule = _schedule(env)
    env.charge(
        "BASE-W-RES",
        "Water base, residential",
        service="water",
        charge_type="recurring",
        amount="8.00",
        is_base=True,
        applies_to_customer_classes=["residential"],
    )
    plan = _plan(env, schedule)
    with tenant_ctx(env.tenant):
        models.Charge.objects.filter(code="BASE-W").update(applies_to_customer_classes=["commercial"])
        _unname(schedule)
    unnamed = _get(env, plan["id"], {"classes": "residential"})
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`): unnamed → `$0.00` for every class
    # (it read `ambiguous`, narrowed to BASE-W-RES by class). Named → that code.
    assert unnamed["services"][0]["base"]["state"] == "not_named"
    with tenant_ctx(env.tenant):
        models.TariffVersion.objects.filter(tariff_id=schedule["id"]).update(
            base_charge_code=models.Charge.objects.get(code="BASE-W-RES")
        )
    narrowed = _get(env, plan["id"], {"classes": "residential"})
    with tenant_ctx(env.tenant):
        residential_name = _class_name("residential")
    assert narrowed["services"][0]["base"]["code"]["code"] == "BASE-W-RES"
    assert narrowed["services"][0]["base"]["classes"] == [residential_name]


def test_a_tax_names_who_pays_it(env):
    schedule = _schedule(env)
    state = env.tax("State tax", rate="0.06", applies_to_customer_classes=["commercial"])
    county = env.tax("County tax", rate="0.02")
    plan = _plan(env, schedule, taxes=[{"tax": str(state["id"])}, {"tax": str(county["id"])}])
    with tenant_ctx(env.tenant):
        taxes = {row["ref"]["name"]: row for row in plan_reads.plan_sections(plan["id"])["taxes"]}
        commercial = _class_name("commercial")
    assert taxes["State tax"]["customer_classes"] == [commercial]
    assert taxes["County tax"]["customer_classes"] == []
    assert taxes["County tax"]["authority"] == "County tax"


def test_a_deposit_says_it_is_refundable(env):
    schedule = _schedule(env)
    env.charge("DEPOSIT", "Security deposit", charge_type="refundable", amount="150.00")
    plan = _plan(env, schedule, deposits=[{"charge": "DEPOSIT"}])
    with tenant_ctx(env.tenant):
        deposits = {row["ref"]["code"]: row for row in plan_reads.plan_sections(plan["id"])["deposits"]}
    # A plan's deposit code is refused unless its type is *refundable*
    # (`rating.plans.deposit_code_not_deposit`), so a coded deposit reads Yes.
    assert deposits["DEPOSIT"]["refundable"] is True


def test_a_discount_says_how_it_is_got_and_whether_proof_is_asked(env):
    from datetime import date

    schedule = _schedule(env)
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin,
            {
                "code": "PAPERLESS",
                "name": "Paperless",
                "discount_type": "percentage",
                "value": "15",
                "applies_to": "whole_bill",
                "effective_from": date(2026, 1, 1),
            },
        )
        version = discount_models.DiscountVersion.objects.get(tenant=env.tenant, discount_id=row["id"])
        discount_services.submit_discount_version(env.admin, version.id)
        discount_services.approve_discount_version(env.admin, version.id)
    plan = _plan(env, schedule, discounts=[{"discount": "PAPERLESS"}])
    with tenant_ctx(env.tenant):
        discounts = plan_reads.plan_sections(plan["id"])["discounts"]
    assert [one["ref"]["code"] for one in discounts] == ["PAPERLESS"]
    assert discounts[0]["enrolment_mode"] == "apply_and_approve"
    assert discounts[0]["proof_required"] is False
