# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 2 task 3 — the discounts redesign's back end.
# Defects: DEF-RAT-9293 (approved is not live) · DEF-RAT-9294 (off-plan
#          enrolment; unbind refused) · DEF-RAT-9295 (Automatic enrols nobody)
#          · DEF-RAT-9296 (Retire has no date and runs backwards) ·
#          DEF-RAT-9297 (the enrolment door answers 500)
# Rules:   PO 2026-10-03 lifecycle rulings 1–4 · the three dropdowns ·
#          currency fixed to the utility · CR-166 §9 contract
# ───────────────────────────────────────────────────────
"""The four lifecycle rulings, the per-utility lists and the §9 reads, on the
default (SQLite) suite. The database locks and the one-version-per-date proof
are on PostgreSQL in `test_cr166_discounts_round2_pg.py` (hard-won law 14).

Every case writes through the product's own services (DEF-658), with the
tenant's "today" pinned (`apps.rating.seams.tenant_today`) so a date in a
ruling's worked figure is the date the code sees.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.identity import models as identity_models
from apps.rating import (
    api as rating_api,
)
from apps.rating import (
    discount_enrolment_job,
    discount_lists,
    discount_pricing,
    discount_reads,
    discount_services,
    seams,
    selectors,
    services,
)
from apps.rating import discounts as dm
from core import errors

from tests.test_us_ten_helpers import api_call
from tests.test_w5_eligibility_and_deposit_carry import _occupant, _plan, _unit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

D = Decimal
TODAY = date(2026, 10, 15)
DEC_31 = date(2026, 12, 31)
JAN_01 = date(2027, 1, 1)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: TODAY)


def _user(actor):
    return identity_models.User.objects.get(pk=actor.id)


def _home(actor, tenant, label="Unit A", name="Alvarez, Rosa"):
    """A unit on Residential Standard since 01/01/2026, and its account."""
    unit = _unit(actor, tenant, label=label)
    from apps.rating import models as rating_models

    rating_models.UnitPlanAssignment.objects.filter(unit_id=unit["id"]).update(
        assigned_from=date(2026, 1, 1)
    )
    account = _occupant(actor, tenant, unit, name=name)
    return unit, account


def _discount(
    actor,
    code="SENIOR",
    *,
    value="15",
    start=date(2026, 8, 1),
    mode=dm.ENROLMENT_APPLY_AND_APPROVE,
    eligibility="age_65_or_over",
    approve=True,
    **extra,
):
    payload = {
        "code": code,
        "name": f"{code.title()} discount",
        "program_owner": "billing",
        "discount_type": dm.DISCOUNT_PERCENTAGE,
        "value": value,
        "applies_to": dm.SCOPE_WHOLE_BILL,
        "effective_from": start.isoformat(),
        "enrolment_mode": mode,
        "verification_method": (
            dm.VERIFY_AUTOMATIC if mode == dm.ENROLMENT_AUTOMATIC else dm.VERIFY_ONE_TIME_PROOF
        ),
        "eligibility": eligibility,
        **extra,
    }
    row = discount_services.create_discount(actor, payload)
    if approve:
        discount_services.submit_discount(actor, row["id"])
        discount_services.approve_discount(actor, row["id"])
    return dm.Discount.objects.get(pk=row["id"])


def _bind(actor, tenant, discount):
    plan = _plan(tenant)
    discount_services.attach_discount_to_plan(actor, plan.id, discount.id)
    return plan


def _reduction_on(account_id, day, amount="60.00"):
    lines = (discount_pricing.BillLine(service="electric", kind="usage", amount=D(amount)),)
    outcome = discount_services.price_account_discounts(account_id, lines, on_day=day)
    return outcome.total_reduction().quantize(D("0.01"))


# ═══ DEF-RAT-9297 — the enrolment door ══════════════════════════════════════
def test_def_rat_9297_the_enrol_door_reads_the_programme_from_the_body(brazos, dana):
    """`POST /accounts/{id}/discounts {"programme_id": …}` answered 500 every
    time: the view passed the WHOLE BODY as the programme id. RED before the
    fix with `ValidationError: ['"{'programme_id': …}" is not a valid UUID.']`."""
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana)
        _bind(dana, brazos, senior)
    response = api_call(
        customers_api.account_claim_assistance,
        "post",
        user=_user(dana),
        role="system_admin",
        tenant=brazos,
        data={"programme_id": str(senior.id)},
        account_id=account["id"],
    )
    assert response.status_code == 200, response.data
    assert response.data["claimed"] is True
    assert response.data["enrolment"]["discount"] == "SENIOR"


def test_def_rat_9297_a_missing_programme_is_a_field_error_not_a_500(brazos, dana):
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
    response = api_call(
        customers_api.account_claim_assistance,
        "post",
        user=_user(dana),
        role="system_admin",
        tenant=brazos,
        data={},
        account_id=account["id"],
    )
    assert response.status_code == 422, response.data
    assert response.data["field_errors"][0]["field"] == "programme_id"


# ═══ the three per-utility lists + currency ═════════════════════════════════
def test_form_options_serve_the_drawn_lists_and_the_utility_currency(brazos, dana):
    with tenant_ctx(brazos):
        options = discount_reads.form_options()
    assert [row["label"] for row in options["program_owners"]] == [
        label for _code, label in discount_lists.SEEDED_PROGRAM_OWNERS
    ]
    assert len(options["program_owners"]) == 8
    assert len(options["exclusivity_groups"]) == 6
    assert options["exclusivity_groups"][0] == {"value": "none", "label": "None"}
    assert len(options["eligibility"]) == 11
    by = {row["value"]: row["checked_by"] for row in options["eligibility"]}
    assert [code for code, kind in by.items() if kind == "system"] == [
        "everyone",
        "autopay_on",
        "paperless_on",
        "government_account",
    ]
    assert options["currency"] == "USD"
    for key in (
        "enrollment_modes",
        "verification",
        "lapse",
        "budget_periods",
        "budget_out",
        "types",
        "applies_to",
    ):
        assert options[key] and all({"value", "label"} <= set(row) for row in options[key])


def test_assistance_becomes_one_shared_group_never_a_drawn_one(brazos, dana):
    """PO 2026-10-03, verbatim: *"A Keep them excluding each other, so the
    customer gets one of the two"*. Today's free-text `assistance` maps to ONE
    utility-own group, *Assistance programs* — never *Low-income programs* or
    *Age-based*, which would let CAP and SENIOR stack."""
    with tenant_ctx(brazos):
        code_cap = discount_lists.map_or_add(dm.LIST_EXCLUSIVITY_GROUP, "assistance")
        code_senior = discount_lists.map_or_add(dm.LIST_EXCLUSIVITY_GROUP, "assistance")
        row = discount_lists.value_row(dm.LIST_EXCLUSIVITY_GROUP, "assistance")
        drawn = [option["value"] for option in discount_reads.form_options()["exclusivity_groups"]]
    assert code_cap == code_senior == "assistance"
    assert row.label == "Assistance programs" and row.is_system is False
    # The six drawn groups stay the seeded defaults, with the ruled one beside them.
    assert drawn[:6] == [code for code, _label in discount_lists.SEEDED_EXCLUSIVITY_GROUPS]
    assert "assistance" in drawn


def test_a_senior_on_cap_receives_exactly_one_of_the_two_on_a_60_bill(brazos, dana):
    """The ruling's worked case: CAP $25.00 and SENIOR 15% ($9.00) in ONE group
    on a $60.00 bill → exactly one applies (the larger, BR-RAT-073's
    exclusivity), so $25.00 off and never $34.00."""
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        group = discount_lists.map_or_add(dm.LIST_EXCLUSIVITY_GROUP, "assistance")
        cap = _discount(
            dana, "CAP", value="25", discount_type=dm.DISCOUNT_FIXED_AMOUNT,
            exclusivity_group=group, eligibility="state_assistance_program",
            proof_before_first_reduction=False,
        )
        senior = _discount(
            dana, "SENIOR", exclusivity_group=group, proof_before_first_reduction=False
        )
        for discount in (cap, senior):
            _bind(dana, brazos, discount)
            discount_services.enrol_account(
                dana, discount.id, account["id"], enrolled_on=date(2026, 9, 1)
            )
        lines = (discount_pricing.BillLine(service="electric", kind="usage", amount=D("60.00")),)
        outcome = discount_services.price_account_discounts(account["id"], lines, on_day=TODAY)
    assert [line.code for line in outcome.applied] == ["CAP"]
    assert outcome.total_reduction().quantize(D("0.01")) == D("25.00")


def test_legacy_who_qualifies_words_map_to_the_drawn_values(brazos, dana):
    with tenant_ctx(brazos):
        mapped = {
            text: discount_lists.map_or_add(dm.LIST_ELIGIBILITY, text)
            for text in (
                "Autopay enrolled",
                "E-bill on",
                "Government account",
                "Age 65+",
                "Veteran ID",
                "Program enrolment",
                "Lives in the flood zone",
            )
        }
        added = discount_lists.value_row(dm.LIST_ELIGIBILITY, mapped["Lives in the flood zone"])
    assert mapped["Autopay enrolled"] == "autopay_on"
    assert mapped["E-bill on"] == "paperless_on"
    assert mapped["Government account"] == "government_account"
    assert mapped["Age 65+"] == "age_65_or_over"
    assert mapped["Veteran ID"] == "veteran_or_military"
    assert mapped["Program enrolment"] == "state_assistance_program"
    assert added.checked_by == "proof" and added.label == "Lives in the flood zone"


def test_a_currency_other_than_the_utilitys_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            _discount(dana, approve=False, currency="CAD")
        saved = _discount(dana, code="NOCUR", approve=False)
        version = dm.DiscountVersion.objects.get(discount=saved)
    assert refused.value.field_errors[0]["message_key"] == "rating.discounts.currency_not_utility"
    assert version.currency == "USD"


def test_an_unknown_program_owner_and_automatic_with_proof_are_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as owner:
            _discount(dana, approve=False, program_owner="martians")
        with pytest.raises(errors.ValidationError) as automatic:
            _discount(
                dana,
                code="AUTOPROOF",
                approve=False,
                mode=dm.ENROLMENT_AUTOMATIC,
                eligibility="age_65_or_over",
            )
    assert owner.value.field_errors[0]["field"] == "program_owner"
    keys = {(fe["field"], fe["message_key"]) for fe in automatic.value.field_errors}
    assert ("eligibility", "rating.discounts.automatic_needs_system_check") in keys


def test_the_reference_card_cannot_mint_a_system_check_or_rename_a_used_code(brazos, dana):
    handler = discount_lists.DiscountListHandler(dm.LIST_ELIGIBILITY)
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            handler.create({"code": "is_tall", "name": "Is tall", "checked_by": "system"})
        added = handler.create({"code": "is_tall", "name": "Is tall"})
        _discount(dana, eligibility="is_tall", approve=False)
        with pytest.raises(errors.ValidationError):
            handler.update(added, {"code": "is_short"})
        renamed = handler.update(added, {"name": "Over two metres"})
    assert added.checked_by == "proof"
    assert renamed.label == "Over two metres"


# ═══ ruling 1 — approval is the last act ════════════════════════════════════
def test_ruling_1_an_approved_discount_is_live_on_its_past_start_without_activate(brazos, dana):
    """`DEF-RAT-9293`: approved with a start 10 days past priced nothing."""
    with tenant_ctx(brazos):
        discount = _discount(dana, start=date(2026, 10, 5))
        version = discount_services.active_version(discount, TODAY)
        row = selectors.discount_detail(discount.id)
    assert version is not None and version.version_no == 1
    assert row["status"] == "active"
    assert row["stored_status"] == dm.DISCOUNT_ACTIVE


def test_ruling_1_a_future_start_reads_scheduled_and_prices_from_its_date(brazos, dana):
    with tenant_ctx(brazos):
        discount = _discount(dana, start=date(2026, 11, 1))
        status = discount_reads.discount_status(discount)
        before = discount_services.active_version(discount, date(2026, 10, 31))
        after = discount_services.active_version(discount, date(2026, 11, 1))
    assert status == "scheduled"
    assert before is None and after is not None


def test_ruling_1_activate_is_gone_and_says_so(brazos, dana):
    with tenant_ctx(brazos):
        discount = _discount(dana, approve=False)
        version = dm.DiscountVersion.objects.get(discount=discount)
        with pytest.raises(errors.BizError) as refused:
            discount_services.activate_discount_version(dana, version.id)
    assert refused.value.message_key == "rating.discounts.activate_retired"


def test_send_back_returns_the_filing_to_draft_with_its_note(brazos, dana):
    with tenant_ctx(brazos):
        discount = _discount(dana, approve=False)
        discount_services.submit_discount(dana, discount.id)
        assert discount_reads.discount_status(discount) == "waiting_approval"
        row = discount_services.send_back_discount(dana, discount.id, {"note": "Wrong value"})
        version = dm.DiscountVersion.objects.get(discount=discount)
    assert row["status"] == dm.VERSION_DRAFT
    assert version.submitted_at is None and version.rejection_reason == "Wrong value"


# ═══ ruling 2 — the plan gate, and removal from a plan ══════════════════════
def test_ruling_2_an_account_whose_plan_does_not_carry_it_is_refused(brazos, dana):
    """`DEF-RAT-9294`: SENIOR, on no plan, enrolled A-10432 and took $9.00 off."""
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana)
        with pytest.raises(errors.BizError) as refused:
            discount_services.enrol_account(dana, senior.id, account["id"])
        _bind(dana, brazos, senior)
        row = discount_services.enrol_account(dana, senior.id, account["id"])
    assert refused.value.message_key == "rating.discounts.plan_does_not_carry"
    assert row["discount"] == "SENIOR"


def test_ruling_2_taking_it_off_the_plan_stops_it_from_the_next_bill(brazos, dana):
    """`OQ-322` CLOSED: no `NotImplementedError`; the binding ends yesterday,
    the enrolment ends yesterday, a bill dated before keeps it."""
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana, proof_before_first_reduction=False)
        plan = _bind(dana, brazos, senior)
        discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
        services._apply_plan_children(plan, {"discounts": []}, dana)
        rule = dm.PlanDiscountRule.objects.get(rate_plan=plan, discount=senior)
        enrolment = dm.DiscountEnrolment.objects.get(discount=senior)
        before = _reduction_on(account["id"], date(2026, 10, 14))
        after = _reduction_on(account["id"], date(2026, 10, 15))
        offered = selectors.plan_discount_rules(plan)
    assert rule.available_to == date(2026, 10, 14)
    assert enrolment.ended_on == date(2026, 10, 14)
    assert enrolment.end_reason == f"Removed from plan {plan.name}"
    assert before == D("9.00") and after == D("0.00")
    assert offered == []


# ═══ ruling 3 — Automatic enrols by a system check ══════════════════════════
def test_ruling_3_autopay_enrols_exactly_the_autopay_accounts_on_its_plans(brazos, dana):
    with tenant_ctx(brazos):
        _u1, on = _home(dana, brazos, label="Unit A", name="Alvarez, Rosa")
        _u2, off = _home(dana, brazos, label="Unit B", name="Baker, Sam")
        customers_models.Account.objects.filter(pk=on["id"]).update(autopay=True)
        autopay = _discount(
            dana,
            "AUTOPAY",
            value="0.5",
            start=date(2026, 8, 1),
            mode=dm.ENROLMENT_AUTOMATIC,
            eligibility="autopay_on",
            approve=False,
        )
        _bind(dana, brazos, autopay)  # bound before approval: approval enrols
        discount_services.submit_discount(dana, autopay.id)
        discount_services.approve_discount(dana, autopay.id)
        enrolled = set(
            dm.DiscountEnrolment.objects.filter(
                discount=autopay, ended_on__isnull=True
            ).values_list("account_id", flat=True)
        )
        autopay.refresh_from_db()  # approval moved it out of draft
        again = discount_enrolment_job.sync_discount(autopay)
        # A month later the customer turns autopay off: the next sweep ends it
        # from the next bill (the day before the sweep).
        dm.DiscountEnrolment.objects.filter(discount=autopay).update(enrolled_on=date(2026, 9, 15))
        customers_models.Account.objects.filter(pk=on["id"]).update(autopay=False)
        swept = discount_enrolment_job.sync_discount(autopay)
        ended = dm.DiscountEnrolment.objects.get(discount=autopay, account_id=on["id"])
    assert {str(one) for one in enrolled} == {str(on["id"])}
    assert again["enrolled"] == 0 and again["ended"] == 0  # idempotent
    assert swept["ended"] == 1
    assert ended.ended_on == date(2026, 10, 14) and ended.end_reason == "no_longer_qualifies"
    del off


# ═══ ruling 4 — the dated retire ════════════════════════════════════════════
def test_ruling_4_retire_on_a_date_keeps_december_and_stops_january(brazos, dana):
    """`DEF-RAT-9296`: retire took no date and ran backwards. Now 12/31/2026:
    December keeps −$9.00 off $60.00, January has none, enrolled included."""
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana, proof_before_first_reduction=False)
        _bind(dana, brazos, senior)
        discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
        discount_services.retire_discount(dana, senior.id, {"effective_to": "2026-12-31"})
        august = _reduction_on(account["id"], date(2026, 8, 15))
        december = _reduction_on(account["id"], DEC_31)
        january = _reduction_on(account["id"], JAN_01)
        enrolment = dm.DiscountEnrolment.objects.get(discount=senior)
        status_now = discount_reads.discount_status(dm.Discount.objects.get(pk=senior.pk))
        with pytest.raises(errors.ValidationError) as past:
            discount_services.retire_discount(dana, senior.id, {"effective_to": "2026-10-01"})
    assert (august, december, january) == (D("0.00"), D("9.00"), D("0.00"))
    assert enrolment.ended_on == DEC_31 and enrolment.end_reason == "discount_retired"
    assert status_now == "active"  # nothing changes before the date
    assert past.value.field_errors[0]["message_key"] == "rating.discounts.retire_in_past"


# ═══ new value from a date · one version per date ═══════════════════════════
def test_new_value_ends_the_old_version_the_day_before(brazos, dana):
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana, proof_before_first_reduction=False)
        _bind(dana, brazos, senior)
        discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
        with pytest.raises(errors.ValidationError) as early:
            discount_services.new_discount_value(
                dana, senior.id, {"value": "12", "effective_from": "2026-08-01"}
            )
        v2 = discount_services.new_discount_value(
            dana, senior.id, {"value": "12", "effective_from": "2027-01-01"}
        )
        v1 = dm.DiscountVersion.objects.get(discount=senior, version_no=1)
        dec = discount_services.active_version(senior, DEC_31)
        jan = discount_services.active_version(senior, JAN_01)
        cuts = (_reduction_on(account["id"], DEC_31), _reduction_on(account["id"], JAN_01))
        row = selectors.discount_detail(senior.id)
    assert (
        early.value.field_errors[0]["message_key"] == "rating.discounts.new_value_not_after_start"
    )
    assert v2["version_no"] == 2 and v2["status"] == dm.VERSION_ACTIVE
    assert v1.effective_to == DEC_31
    assert (dec.version_no, jan.version_no) == (1, 2)
    assert cuts == (D("9.00"), D("7.20"))
    assert row["scheduled_next"] == {"value_display": "12.00%", "effective_from": "2027-01-01"}


# ═══ PATCH — name and details only on a live discount ═══════════════════════
def test_patch_on_a_live_discount_refuses_value_limits_and_start_by_name(brazos, dana):
    with tenant_ctx(brazos):
        senior = _discount(dana)
        with pytest.raises(errors.ValidationError) as locked:
            discount_services.update_discount_details(
                dana,
                senior.id,
                {"value": "20", "cap_per_bill": "5", "effective_from": "2026-09-01"},
            )
        row = discount_services.update_discount_details(
            dana,
            senior.id,
            {"name": "Seniors", "program_owner": "finance", "recertification_months": 12},
        )
    fields = {fe["field"] for fe in locked.value.field_errors}
    assert fields == {"value", "cap_per_bill", "effective_from"}
    assert {fe["message_key"] for fe in locked.value.field_errors} == {
        "rating.discounts.locked_on_live"
    }
    assert row["name"] == "Seniors"
    assert row["program_owner"] == {"value": "finance", "label": "Finance"}
    assert row["recertification_months"] == 12
    assert row["version"] == 1


# ═══ the §9 reads ════════════════════════════════════════════════════════════
def test_the_row_carries_every_contract_field(brazos, dana):
    with tenant_ctx(brazos):
        fixed = _discount(
            dana,
            "CAP",
            value="25",
            discount_type=dm.DISCOUNT_FIXED_AMOUNT,
            exclusivity_group="low_income",
            eligibility="state_assistance_program",
        )
        row = selectors.discount_detail(fixed.id)
    for key in (
        "version",
        "status",
        "program_owner",
        "exclusivity_group",
        "eligibility",
        "value_display",
        "effective_from",
        "effective_to",
        "offered_to",
        "receiving",
        "granted_this_month",
        "scheduled_next",
        "currency",
    ):
        assert key in row, key
    assert row["value_display"] == "$25.00"
    assert row["exclusivity_group"] == {"value": "low_income", "label": "Low-income programs"}
    assert row["eligibility"] == {
        "value": "state_assistance_program",
        "label": "In a state assistance program",
        "checked_by": "proof",
    }
    # DEF-2430 (2026-10-03): grants are RECORDED at issue now, so a programme
    # nobody has been granted anything under this month reads a recorded
    # $0.00 — no longer null (which was "nothing is recorded anywhere").
    assert row["granted_this_month"] == "$0.00"


def test_the_list_filters_the_derived_status_and_the_type_in_sql(brazos, dana):
    from core.pagination import ListParams

    with tenant_ctx(brazos):
        _discount(dana, "LIVE", start=date(2026, 8, 1))
        _discount(dana, "LATER", start=date(2026, 12, 1))
        _discount(dana, "PARKED", approve=False)
        scheduled, n_s = selectors.discount_page(ListParams(filters={"status": "scheduled"}))
        drafts, n_d = selectors.discount_page(ListParams(filters={"status": "draft"}))
        percent, n_p = selectors.discount_page(ListParams(filters={"type": "percentage"}))
    assert [row["code"] for row in scheduled] == ["LATER"] and n_s == 1
    assert [row["code"] for row in drafts] == ["PARKED"] and n_d == 1
    assert n_p == 3
    assert selectors.discount_list_is_sql_pageable(ListParams(filters={"type": "percentage"}))


def test_the_accounts_tab_and_the_plans_tab_and_the_audit_tab(brazos, dana):
    # The shared helpers capture audit rows in a list (`audit_rows`, autouse);
    # this case READS `audit_log`, so the platform's own sink writes (the
    # `test_cr165_tax_versions` shape).
    from apps.audit.services import store_row
    from core import audit as core_audit

    captured = core_audit._sink
    core_audit.set_audit_sink(store_row)
    try:
        _accounts_plans_audit_case(brazos, dana)
    finally:
        core_audit.set_audit_sink(captured)


def _accounts_plans_audit_case(brazos, dana):
    from core.pagination import ListParams

    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana)
        plan = _bind(dana, brazos, senior)
        discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
        rows, total = selectors._sql_page(
            discount_reads.discount_accounts_queryset(senior, ListParams()),
            ListParams(),
            discount_reads.discount_account_rows,
        )
        pending, _n = selectors._sql_page(
            discount_reads.discount_accounts_queryset(
                senior, ListParams(filters={"status": "proof_pending"})
            ),
            ListParams(),
            discount_reads.discount_account_rows,
        )
        plans, _p = selectors._sql_page(
            discount_reads.discount_plans_queryset(senior),
            ListParams(),
            discount_reads.discount_plan_rows,
        )
    assert total == 1
    row = rows[0]
    assert row["customer_name"] == "Alvarez, Rosa"
    assert row["plan"] == plan.name
    # DEF-2430 (2026-10-03): a recorded $0.00 now — nothing was granted to this
    # enrolment this month, and grants ARE recorded at issue (was null).
    assert row["status"] == "proof_pending" and row["this_month"] == "$0.00"
    assert row["enrolment_id"] and row["account_number"]
    assert len(pending) == 1
    assert plans[0]["plan"] == plan.name and plans[0]["units"] == 1 and plans[0]["accounts"] == 1

    response = api_call(
        rating_api.discount_audit,
        "get",
        user=_user(dana),
        role="system_admin",
        tenant=brazos,
        discount_id=str(senior.id),
    )
    actions = [entry["action"] for entry in response.data["results"]]
    assert "discount.account_enrolled" in actions and "discount.created" in actions
    enrolled = next(
        e for e in response.data["results"] if e["action"] == "discount.account_enrolled"
    )
    assert enrolled["after"]["account"] == row["account_number"]  # a NAME, not an id
    assert "id" not in enrolled["after"]


def test_a_proof_condition_gets_its_documents_from_who_qualifies(brazos, dana):
    """The drawing has no *documents accepted* box (New-form lane, CR §11), so
    the server derives them from the condition instead of refusing the save."""
    with tenant_ctx(brazos):
        senior = _discount(dana, approve=False, proof_required=True)
        version = dm.DiscountVersion.objects.get(discount=senior)
    assert version.accepted_proof_kinds == ["government_id", "birth_certificate"]


def test_end_one_enrolment_with_a_date_and_a_reason(brazos, dana):
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana)
        _bind(dana, brazos, senior)
        row = discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
        with pytest.raises(errors.ValidationError):
            discount_services.end_enrolment(dana, row["id"], reason="", ended_on="2026-10-31")
        ended = discount_services.end_enrolment(
            dana, row["id"], reason="Moved away", ended_on="2026-10-31"
        )
    assert ended["ended_on"] == "2026-10-31" and ended["end_reason"] == "Moved away"


# ── CR-166-BRC10 round 3 task 6 · what the details page reads ───────────────
def test_details_plans_rows_name_the_plans_services_and_classes(brazos, dana):
    """Image 21 draws Plan · Services · Customer classes · Accounts · Since.
    The row carries the plan's service CODES (the screen words them) and its
    class NAMES (B14 rule 31); `[]` classes means every class."""
    from core.pagination import ListParams

    with tenant_ctx(brazos):
        senior = _discount(dana)
        plan = _bind(dana, brazos, senior)
        plans, _n = selectors._sql_page(
            discount_reads.discount_plans_queryset(senior),
            ListParams(),
            discount_reads.discount_plan_rows,
        )
    assert plans[0]["plan"] == plan.name
    assert plans[0]["services"] and all(isinstance(code, str) for code in plans[0]["services"])
    assert plans[0]["customer_classes"] == []


def test_details_accounts_name_an_account_with_no_customer_link(brazos, dana):
    """DEF-RAT-9308 — an account with no `customer_accounts` row (every account
    made before BR-CUS-054) is named by its primary contact, the Accounts
    list's own rule, never left blank."""
    from apps.customers import selectors as customers_selectors

    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        expected = customers_selectors.primary_contact_names_for([account["id"]]).get(str(account["id"]))
        customers_models.CustomerAccount.objects.filter(account_id=account["id"]).delete()
        facts = seams.discount_account_facts([account["id"]])
    assert expected
    assert facts[str(account["id"])]["customer_name"] == expected


def test_details_audit_names_the_plan_on_a_plan_link(brazos, dana):
    """DEF-RAT-9309 — image 22's *Added to plan · Residential Standard*: the
    audit read names the plan and never serves its id (B14 rule 31)."""
    from apps.audit.services import store_row
    from core import audit as core_audit

    captured = core_audit._sink
    core_audit.set_audit_sink(store_row)
    try:
        with tenant_ctx(brazos):
            senior = _discount(dana)
            plan = _bind(dana, brazos, senior)
        response = api_call(
            rating_api.discount_audit,
            "get",
            user=_user(dana),
            role="system_admin",
            tenant=brazos,
            discount_id=str(senior.id),
        )
    finally:
        core_audit.set_audit_sink(captured)
    linked = next(e for e in response.data["results"] if e["action"] == "discount.made_available_on_plan")
    assert linked["after"]["plan"] == plan.name
    assert "rate_plan" not in linked["after"]


def test_details_money_is_served_with_its_symbol(brazos, dana):
    """D27 — the details page shows `$` on money. The server decides the
    symbol beside the utility's currency; the bare `*_display` keys stay."""
    with tenant_ctx(brazos):
        senior = _discount(dana, cap_per_bill="4", budget_cap="2383")
        detail = selectors.discount_detail(senior.id)
    money = detail["money_display"]
    assert money["cap_per_bill"] == "$4.00"
    assert money["bill_floor_amount"] == "$0.00"
    assert money["cap_per_year"] is None
    assert money["budget_cap"].startswith("$") and money["budget_cap"].endswith(".00")
    assert detail["bill_floor_amount_display"] == "0.00"  # unchanged for older screens


def test_details_version_rows_carry_their_end_date(brazos, dana):
    """Image 19's versions table reads *08/01/2026 – 12/31/2026*: a version row
    serves `effective_to` beside `effective_from` (null = no end)."""
    with tenant_ctx(brazos):
        senior = _discount(dana)
        discount_services.retire_discount(dana, senior.id, {"effective_to": "2026-12-31"})
        chain = discount_services.discount_version_chain(senior)
    assert chain[0]["effective_from"] == "2026-08-01"
    assert chain[0]["effective_to"] == "2026-12-31"
