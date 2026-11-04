# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 round 2 task 3 — the plan server (§7.3 contract).
# Defects: DEF-RAT-9328 (late fee on one list) · DEF-RAT-9330 (publish of a
#          published plan) · DEF-RAT-9337 (base code accepted as a charge code)
# Rules:   BR-RAT-1066 (a plan version has dates; the date picks one) ·
#          BR-RAT-1067 (name and details on the same version) · BR-RAT-023 as
#          amended (deposits named by class) · OQ-RAT-12786 (size: not ruled)
# ───────────────────────────────────────────────────────
"""The plans redesign's server, on the default suite (SQLite).

The overlap lock and the every-day one-version proof are PostgreSQL facts and
live in `test_cr167_plan_versions_pg.py` (law 14). Here: the contract body, its
refusals by name, the three edit verbs, and the three defects — each written
RED first against the tip before the fix (`CR-167-BRC10` §9 quotes the
failures).
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import models, plan_reads, plan_versioning, plan_writes, seams, selectors, services
from apps.rating import resolution_catalogue
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 3)
DEC_31 = date(2026, 12, 31)
JAN_01 = date(2027, 1, 1)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: TODAY)


def _schedule(env):
    env.enable("water")
    _late_fee_code(env)
    return env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)


def _late_fee_code(env):
    """The tenant's seeded late-fee code (`lookup_defaults.json`: 1.50%, min
    $5.00) — the empty-catalogue fixture starts without it."""
    with tenant_ctx(env.tenant):
        if models.Charge.objects.filter(code="LATE").exists():
            return
    env.charge(
        "LATE",
        "Late payment fee",
        charge_type="penalty",
        amount_rule="percent_with_minimum",
        amount=None,
        percent="0.015",
        min_amount="5.00",
    )


def _published(env, **overrides):
    schedule = _schedule(env)
    plan = env.plan(
        "Residential City Plan",
        "RCP",
        [{"service": "water", "tariff": schedule["id"]}],
        publish=True,
        minimum_bill_amount="10.00",
        **overrides,
    )
    return plan, schedule


def _contract(schedule, **overrides):
    body = {
        "details": {"name": "Residential City Plan", "code": "RCP", "customer_classes": []},
        "services": [{"service": "water", "schedule": schedule["id"], "surcharged": True}],
        "charge_codes": [],
        "taxes": [],
        "deposits": [],
        "discounts": [],
        "minimum_bill_amount": "10.00",
        "effective_from": "2026-09-01",
    }
    body.update(overrides)
    return body


def _keys(exc):
    return {(entry["field"], entry["message_key"]) for entry in exc.value.field_errors}


# ── DEF-RAT-9337 ─────────────────────────────────────────────────────────────


def test_def_rat_9337__a_base_code_is_refused_as_a_plan_charge_code(env):
    """RED at the tip: the write was ACCEPTED and BASE-W stored as a charge
    code (the README's check (a))."""
    plan, _ = _published(env)
    with tenant_ctx(env.tenant):
        base = models.Charge.objects.get(is_base=True, service__code="water")
        with pytest.raises(errors.ValidationError) as caught:
            services.update_plan(
                env.admin, plan["id"], {"charge_rules": [{"charge": base.code}], "reason": "x"}
            )
    assert ("charge_rules[0].charge", "rating.plans.base_code_on_charges") in _keys(caught)


# ── DEF-RAT-9330 ─────────────────────────────────────────────────────────────


def test_def_rat_9330__publishing_an_already_published_plan_is_answered_not_refused(env):
    """RED at the tip: `rating.plans.not_publishable` — the screen showed
    *"We couldn't publish this plan"* over a version it had just written."""
    plan, _ = _published(env)
    with tenant_ctx(env.tenant):
        answer = services.publish_plan(env.admin, plan["id"])
    assert answer["already_published"] is True
    assert answer["version"] == 1


# ── DEF-RAT-9328 ─────────────────────────────────────────────────────────────


def test_def_rat_9328__the_late_fee_is_ONE_row_of_the_charge_codes_list(env):
    """The plan's Charges list, Review and details read ONE list, and the late
    fee is in it once — with a flag, so the screen can say which row it is."""
    plan, _ = _published(env)
    with tenant_ctx(env.tenant):
        sections = plan_reads.plan_sections(plan["id"])
        options = plan_reads.form_options()
    late = [row for row in sections["charge_codes"] if row["late_fee"]]
    assert [row["ref"]["code"] for row in late] == ["LATE"]
    assert len([row for row in sections["charge_codes"] if row["ref"]["code"] == "LATE"]) == 1
    # A NEW plan's form starts with LATE as an ordinary, removable row (§7.6).
    assert [row["ref"]["code"] for row in options["charge_codes"] if row["default_on_new_plan"]] == ["LATE"]


def test_def_rat_9328__removing_the_late_fee_row_charges_no_late_fee(env):
    schedule = _schedule(env)
    with tenant_ctx(env.tenant):
        kept = plan_writes.create(env.admin, _contract(schedule, charge_codes=[{"charge": "LATE"}]))
        gone = plan_writes.create(
            env.admin,
            _contract(schedule, details={"name": "No late fee", "code": "NLF", "customer_classes": []}),
        )
    assert kept["late_fee_charge"]["code"] == "LATE"
    # `charge_codes: []` is the clerk's *no late fee* — never filled with LATE.
    assert gone["late_fee_charge"] is None


# ── the contract body and its refusals ──────────────────────────────────────


def test_contract_post__save_as_draft_then_publish_plan(env):
    schedule = _schedule(env)
    with tenant_ctx(env.tenant):
        draft = plan_writes.create(env.admin, _contract(schedule))
        published = plan_writes.create(
            env.admin,
            _contract(
                schedule,
                details={"name": "Published one", "code": "PUB", "customer_classes": []},
                publish=True,
            ),
        )
    assert draft["status"] == "draft"
    assert [v["status"] for v in draft["versions"]] == ["draft"]
    assert published["status"] == "published"
    assert published["plan_version"]["version"] == 1
    assert published["plan_version"]["effective_from"] == "2026-09-01"
    assert published["details"]["minimum_bill_display"] == "10.00"


def test_contract_post__a_refused_publish_leaves_no_draft_behind(env):
    schedule = _schedule(env)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError):
            plan_writes.create(env.admin, _contract(schedule, effective_from=None, publish=True))
        assert not models.RatePlan.objects.filter(code="RCP").exists()


def test_contract_refusals__each_box_is_named(env):
    schedule = _schedule(env)
    env.charge("CONN", "Connection fee")
    with tenant_ctx(env.tenant):
        env_charge = models.Charge.objects.get(code="CONN")
        with pytest.raises(errors.ValidationError) as caught:
            plan_writes.create(
                env.admin,
                _contract(
                    schedule,
                    services=[
                        {"service": "water", "schedule": schedule["id"]},
                        {"service": "water", "schedule": schedule["id"]},
                        {"service": "", "schedule": None},
                    ],
                    charge_codes=[{"charge": env_charge.code}, {"charge": env_charge.code}, {}],
                    taxes=[{}],
                    discounts=[{"discount": "SENIOR", "offered_from": "2026-10-31", "offered_until": "2026-09-01"}],
                ),
            )
    keys = _keys(caught)
    assert ("services[1].service", "rating.plans.service_listed_twice") in keys
    assert ("services[2].service", "rating.plans.row_empty") in keys
    assert ("charge_codes[1].charge", "rating.plans.charge_listed_twice") in keys
    assert ("charge_codes[2].charge", "rating.plans.row_empty") in keys
    assert ("taxes[0].tax", "rating.plans.row_empty") in keys
    assert ("discounts[0].offered_until", "rating.plans.offer_window_backwards") in keys


def test_contract_refusals__a_schedule_for_another_service(env):
    schedule = _schedule(env)
    env.enable("electric")
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        plan_writes.create(
            env.admin,
            _contract(schedule, services=[{"service": "electric", "schedule": schedule["id"]}]),
        )
    assert ("services[0].schedule", "rating.plans.schedule_wrong_service") in _keys(caught)


# ── deposits (ruling 9; BR-RAT-023 as amended; OQ-RAT-12786) ───────────────


def _deposit_code(env, code="DEPOSIT"):
    with tenant_ctx(env.tenant):
        return env.charge(code, "Security deposit", charge_type="refundable", amount="150.00")


def test_deposits__a_refundable_code_is_named_and_answers_the_deposit(env):
    schedule = _schedule(env)
    _deposit_code(env)
    with tenant_ctx(env.tenant):
        plan = plan_writes.create(
            env.admin, _contract(schedule, deposits=[{"charge": "DEPOSIT"}], publish=True)
        )
        residential = seams.account_type_id_by_code("residential")
        answer = selectors.deposit_rule_for(plan["id"], residential)
    assert [row["ref"]["code"] for row in plan["deposits"]] == ["DEPOSIT"]
    assert answer["amount"] == Decimal("150.00")
    # The Charges list does not list it — it is the Deposits table's row.
    assert "DEPOSIT" not in [row["ref"]["code"] for row in plan["charge_codes"]]


def test_deposits__a_code_that_is_not_a_deposit_is_refused_by_name(env):
    schedule = _schedule(env)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        plan_writes.create(env.admin, _contract(schedule, deposits=[{"charge": "LATE"}]))
    assert ("deposits[0].charge", "rating.plans.deposit_code_not_deposit") in _keys(caught)


def test_deposits__a_plan_naming_no_code_reads_nothing_new(env):
    """Not a cent moves: a plan with no deposit code answers as before (None)."""
    plan, _ = _published(env)
    with tenant_ctx(env.tenant):
        residential = seams.account_type_id_by_code("residential")
        assert selectors.deposit_rule_for(plan["id"], residential) is None


# ── Name and details (BR-RAT-1067) ───────────────────────────────────────────


def test_patch_live__name_and_details_save_on_the_same_version(env):
    plan, _ = _published(env)
    with tenant_ctx(env.tenant):
        answer = plan_writes.patch(
            env.admin,
            plan["id"],
            {"details": {"name": "Residential — City", "intended_for": {"owner_occupied": True}}},
        )
    assert answer["name"] == "Residential — City"
    assert answer["version"] == 1
    assert answer["details"]["intended_for"]["owner_occupied"] is True


def test_patch_live__a_price_is_refused_by_name(env):
    plan, _ = _published(env)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        plan_writes.patch(env.admin, plan["id"], {"details": {}, "minimum_bill_amount": "12.00"})
    assert caught.value.message_key == "rating.plans.field_needs_new_version"


# ── Change from a date (BR-RAT-1066) ─────────────────────────────────────────


def _new_version(env, plan, start="2027-01-01", publish=True, **body):
    with tenant_ctx(env.tenant):
        return plan_writes.new_version(
            env.admin,
            plan["id"],
            {
                "effective_from": start,
                "reason": "Minimum bill up for 2027",
                "minimum_bill_amount": "12.00",
                "publish": publish,
                **body,
            },
        )


def test_new_version__v1_ends_the_day_before_and_the_date_picks_one(env):
    """Image 41: *v1 · gets an end date; v2 · 01/01/2027 – No end*. Worked:
    12/31/2026 is v1 ($10.00 floor), 01/01/2027 is v2 ($12.00)."""
    plan, _ = _published(env)
    answer = _new_version(env, plan)
    with tenant_ctx(env.tenant):
        on_dec = plan_versioning.version_on(plan["id"], DEC_31)
        on_jan = plan_versioning.version_on(plan["id"], JAN_01)
        plan_row = models.RatePlan.objects.get(pk=plan["id"])
        terms_dec = plan_versioning.terms_on(plan_row, DEC_31)
        terms_jan = plan_versioning.terms_on(plan_row, JAN_01)
        candidates = resolution_catalogue.plan_version_facts.__wrapped__(plan["id"]) if hasattr(
            resolution_catalogue.plan_version_facts, "__wrapped__"
        ) else resolution_catalogue.plan_version_facts(plan["id"])
    assert (on_dec.version_no, on_jan.version_no) == (1, 2)
    assert str(on_dec.effective_to) == "2026-12-31"
    assert terms_dec["minimum_bill_amount"] == Decimal("10.000000")
    assert terms_jan["minimum_bill_amount"] == Decimal("12.000000")
    assert [(c.version, str(c.effective_from), str(c.effective_to)) for c in candidates] == [
        (1, "2026-08-01", "2026-12-31"),
        (2, "2027-01-01", "None"),
    ]
    # Units stay on the plan; the screen's counter reads the newest version.
    assert answer["version"] == 2
    assert [v["status"] for v in answer["versions"]][:2] == ["scheduled", "in_force"]


def test_new_version__a_start_in_the_past_is_refused(env):
    plan, _ = _published(env)
    with pytest.raises(errors.ValidationError) as caught:
        _new_version(env, plan, start="2026-09-15")
    assert caught.value.message_key == "rating.plans.version_start_in_past"


def test_new_version__no_start_and_no_reason_are_refused_by_name(env):
    plan, _ = _published(env)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        plan_writes.new_version(env.admin, plan["id"], {"minimum_bill_amount": "12.00"})
    keys = _keys(caught)
    assert ("effective_from", "rating.plans.version_start_required") in keys
    assert ("reason", "rating.reason_required") in keys


def test_new_version__one_draft_at_a_time_and_its_publish(env):
    plan, _ = _published(env)
    saved = _new_version(env, plan, publish=False)
    assert [v["status"] for v in saved["versions"]][0] == "draft"
    with pytest.raises(errors.ValidationError) as caught:
        _new_version(env, plan, start="2027-02-01", publish=False)
    assert ("effective_from", "rating.plans.one_draft_version") in _keys(caught)
    with tenant_ctx(env.tenant):
        # Nothing prices from a draft: 01/01/2027 still reads v1.
        assert plan_versioning.version_on(plan["id"], JAN_01).version_no == 1
        published = plan_writes.publish_version(env.admin, plan["id"], 2)
        assert plan_versioning.version_on(plan["id"], JAN_01).version_no == 2
    assert published["version"] == 2


def test_new_version__a_second_one_must_start_after_the_one_it_replaces(env):
    plan, _ = _published(env)
    _new_version(env, plan)
    with pytest.raises(errors.ValidationError) as caught:
        _new_version(env, plan, start="2027-01-01")
    assert caught.value.message_key in (
        "rating.plans.version_start_not_after_current",
        "rating.plans.versions_overlap",
    )


# ── Fix a mistake, by version ────────────────────────────────────────────────


def test_correction__names_the_version_and_keeps_its_number_and_dates(env):
    plan, _ = _published(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        answer = plan_writes.correct(
            env.admin,
            plan["id"],
            {"details": {}, "version": 1, "minimum_bill_amount": "11.00", "reason": "Typed 10 for 11"},
        )
        v1 = plan_versioning.version_on(plan["id"], DEC_31)
        plan_row = models.RatePlan.objects.get(pk=plan["id"])
        terms = plan_versioning.terms_on(plan_row, DEC_31)
    assert answer["issued_bills_unchanged"] is True
    assert v1.version_no == 1 and v1.corrects_id is not None
    assert (str(v1.effective_from), str(v1.effective_to)) == ("2026-08-01", "2026-12-31")
    assert terms["minimum_bill_amount"] == Decimal("11.000000")
    # v2 is untouched.
    assert plan_versioning.terms_on(plan_row, JAN_01)["minimum_bill_amount"] == Decimal("12.000000")


# ── reads ───────────────────────────────────────────────────────────────────


def test_priced_as_of__the_detail_reads_the_version_on_the_date(env):
    plan, _ = _published(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        dec = plan_reads.plan_sections(plan["id"], DEC_31)
        jan = plan_reads.plan_sections(plan["id"], JAN_01)
        now = plan_reads.plan_sections(plan["id"])
    assert dec["plan_version"]["version"] == 1
    assert dec["details"]["minimum_bill_display"] == "10.00"
    assert jan["plan_version"]["version"] == 2
    assert jan["details"]["minimum_bill_display"] == "12.00"
    assert now["upcoming"][0] == {
        "kind": "plan",
        "code": "RCP",
        "name": "Residential City Plan",
        "version": 2,
        "effective_from": "2027-01-01",
    }
    service = now["services"][0]
    assert service["schedule"]["kind"] == "schedule"
    assert service["schedule"]["version"] == 1
    assert service["schedule"]["effective_from"] == "2026-08-01"


# ── DEF-RAT-9354 — the list row names its classes ───────────────────────────


def test_def_rat_9354__a_list_row_serves_its_customer_classes_as_words(env):
    """RED at the tip: `GET /plans` rows carried no `customer_classes`, so the
    list read the tenant's whole class list a second time to name them. Served
    as the details read serves it — `[{value, label}]`, `[]` for every class —
    from ONE names read for the page (`NFR-3`)."""
    from core.pagination import ListParams

    from apps.rating import plan_reads

    schedule = _schedule(env)
    with tenant_ctx(env.tenant):
        residential = seams.account_type_id_by_code("residential")
    env.plan("Residential City Plan", "RCP", [{"service": "water", "tariff": schedule["id"]}],
             account_type_ids=[residential])
    env.plan("Every Class Plan", "ECP", [{"service": "water", "tariff": schedule["id"]}])
    with tenant_ctx(env.tenant):
        rows, total = plan_reads.plan_page(ListParams(sort="name"))
    by_code = {row["code"]: row for row in rows}
    assert total == 2
    assert by_code["RCP"]["customer_classes"] == [{"value": str(residential), "label": "Residential"}]
    assert by_code["ECP"]["customer_classes"] == []
