# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 follow-up (lane DISC-SMALLS, PO 2026-10-03 "complete
#          these and fix bugs") — the four small things left on the discount
#          details page and the bill's Document tab.
# Defects: DEF-RAT-9310 (Duplicate) · DEF-478 (add/remove a plan from the
#          discount page) · DEF-1005 (CSV on Accounts and Audit) · DEF-BIL-9346
#          (the Document tab called discounts "Charged to the bill")
# Rules:   PO ruling 2 of 2026-10-03 (removal stops it from the next bill) ·
#          BR-RAT-037 (a reason on a published plan) · NFR-3 / NFR-5 (no cap) ·
#          B14 rule 31 (names, never ids)
# ───────────────────────────────────────────────────────
"""Each case was run RED against the tip before the change (quoted in CR-166
§18) and writes through the product's own services and views (DEF-658)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import selectors as billing_selectors
from apps.rating import api as rating_api
from apps.rating import discount_services, seams
from apps.rating import discounts as dm

from tests.test_cr166_discounts_round2 import TODAY, _bind, _discount, _home, _user
from tests.test_us_ten_helpers import api_call
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: TODAY)


@pytest.fixture
def audited():
    """Requested AFTER `brazos, dana` so it is set up after them.
    The default suite's audit sink stores nothing; the Audit tab and its CSV
    read `audit_log`, so these cases store each row (as DEF-RAT-9309's case)."""
    from apps.audit.services import store_row
    from core import audit as core_audit

    captured = core_audit._sink
    core_audit.set_audit_sink(store_row)
    yield
    core_audit.set_audit_sink(captured)


def _call(view, method, dana, brazos, data=None, query=None, **kwargs):
    return api_call(
        view,
        method,
        user=_user(dana),
        role="system_admin",
        tenant=brazos,
        data=data,
        query=query,
        **kwargs,
    )


# ═══ DEF-RAT-9310 — Duplicate ═══════════════════════════════════════════════
def test_def_rat_9310_duplicate_copies_the_version_in_force_into_a_new_draft(brazos, dana):
    """SENIOR 15% in force with 12% scheduled from 01/01/2027, on a plan, one
    account receiving it → the copy is a DRAFT at 15%, same conditions, no
    dates, on no plan, received by nobody."""
    with tenant_ctx(brazos):
        _unit, account = _home(dana, brazos)
        senior = _discount(
            dana,
            recertification_months=12,
            recertification_notice_days=30,
            recertification_grace_days=15,
            cap_per_bill="40.00",
            stacking_precedence=40,
        )
        _bind(dana, brazos, senior)
        discount_services.enrol_account(dana, senior.id, account["id"])
        discount_services.new_discount_value(
            dana, senior.id, {"value": "12", "effective_from": "2027-01-01"}
        )
    response = _call(
        rating_api.discount_duplicate,
        "post",
        dana,
        brazos,
        data={"code": "SENIOR-RURAL", "name": "Rural senior discount"},
        discount_id=str(senior.id),
    )
    assert response.status_code == 201, response.data
    with tenant_ctx(brazos):
        copy = dm.Discount.objects.get(pk=response.data["id"])
        versions = list(dm.DiscountVersion.objects.filter(discount=copy))
        assert copy.code == "SENIOR-RURAL"
        assert copy.name == "Rural senior discount"
        assert copy.status == dm.DISCOUNT_DRAFT
        assert copy.programme_owner == senior.programme_owner
        assert len(versions) == 1
        v = versions[0]
        assert v.status == dm.VERSION_DRAFT
        assert v.value == Decimal("15")
        assert v.effective_from is None and v.effective_to is None
        assert v.eligibility_code == "age_65_or_over"
        assert v.recertification_notice_days == 30
        assert v.recertification_grace_days == 15
        assert v.cap_per_bill == Decimal("40.00")
        assert v.stacking_precedence == 40
        assert not dm.DiscountEnrolment.objects.filter(discount=copy).exists()
        assert not dm.PlanDiscountRule.objects.filter(discount=copy).exists()
        # The source is untouched.
        assert dm.DiscountEnrolment.objects.filter(discount=senior).count() == 1


def test_def_rat_9310_duplicate_requires_a_new_code_and_name(brazos, dana):
    with tenant_ctx(brazos):
        senior = _discount(dana)
    blank = _call(
        rating_api.discount_duplicate, "post", dana, brazos, data={}, discount_id=str(senior.id)
    )
    assert blank.status_code == 422
    fields = {entry["field"] for entry in blank.data["field_errors"]}
    assert {"code", "name"} <= fields
    taken = _call(
        rating_api.discount_duplicate,
        "post",
        dana,
        brazos,
        data={"code": "senior", "name": "Another"},
        discount_id=str(senior.id),
    )
    assert taken.status_code == 422
    assert taken.data["field_errors"][0]["message_key"] == "rating.discounts.duplicate_code"


# ═══ DEF-478 — add / remove a plan from the discount page ══════════════════
def test_def_478_add_to_a_plan_from_the_discount_page_needs_a_reason_and_is_audited(brazos, dana, audited):
    from tests.test_w5_eligibility_and_deposit_carry import _plan

    with tenant_ctx(brazos):
        senior = _discount(dana)
        plan = _plan(brazos)
    no_reason = _call(
        rating_api.discount_plans, "post", dana, brazos, data={"plan": str(plan.id)}, discount_id=str(senior.id)
    )
    assert no_reason.status_code == 422
    assert no_reason.data["field_errors"][0]["field"] == "reason"
    added = _call(
        rating_api.discount_plans,
        "post",
        dana,
        brazos,
        data={"plan": str(plan.id), "reason": "Seniors on the main tariff"},
        discount_id=str(senior.id),
    )
    assert added.status_code == 201, added.data
    with tenant_ctx(brazos):
        rule = dm.PlanDiscountRule.objects.get(discount=senior, rate_plan=plan)
        assert rule.available_from == TODAY and rule.available_to is None
    rows = _call(rating_api.discount_plans, "get", dana, brazos, discount_id=str(senior.id))
    assert [row["plan"] for row in rows.data["results"]] == [plan.name]
    audit = _call(rating_api.discount_audit, "get", dana, brazos, discount_id=str(senior.id))
    added_rows = [row for row in audit.data["results"] if row["action"] == "discount.made_available_on_plan"]
    assert added_rows, audit.data
    assert added_rows[0]["reason"] == "Seniors on the main tariff"
    assert added_rows[0]["after"]["plan"] == plan.name
    twice = _call(
        rating_api.discount_plans,
        "post",
        dana,
        brazos,
        data={"plan": str(plan.id), "reason": "Again"},
        discount_id=str(senior.id),
    )
    assert twice.status_code == 422
    assert twice.data["field_errors"][0]["message_key"] == "rating.discounts.already_on_plan"


def test_def_478_remove_from_a_plan_ends_the_binding_and_the_enrolments_from_yesterday(brazos, dana, audited):
    """Ruling 2: taken off on 10/15/2026 → the binding and the account's
    enrolment end 10/14/2026; the person's reason is the Audit's reason."""
    with tenant_ctx(brazos):
        _unit, account = _home(dana, brazos)
        senior = _discount(dana)
        plan = _bind(dana, brazos, senior)
        enrolment = discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
    refused = _call(
        rating_api.discount_plan_item,
        "delete",
        dana,
        brazos,
        discount_id=str(senior.id),
        plan_id=str(plan.id),
    )
    assert refused.status_code == 422
    removed = _call(
        rating_api.discount_plan_item,
        "delete",
        dana,
        brazos,
        data={"reason": "Seniors move to the new plan"},
        discount_id=str(senior.id),
        plan_id=str(plan.id),
    )
    assert removed.status_code == 200, removed.data
    with tenant_ctx(brazos):
        rule = dm.PlanDiscountRule.all_versions.get(discount=senior, rate_plan=plan)
        assert rule.available_to == date(2026, 10, 14)
        row = dm.DiscountEnrolment.objects.get(pk=enrolment["id"])
        assert row.ended_on == date(2026, 10, 14)
        assert row.end_reason == f"Removed from plan {plan.name}"
    audit = _call(rating_api.discount_audit, "get", dana, brazos, discount_id=str(senior.id))
    gone = [row for row in audit.data["results"] if row["action"] == "discount.removed_from_plan"]
    assert gone and gone[0]["reason"] == "Seniors move to the new plan"


def test_def_rat_9512_added_and_removed_the_same_day_still_ends_the_enrolments_and_is_audited(
    brazos, dana, audited
):
    """The browser walk added SENIOR to a plan on 10/03, enrolled Ruth, and took
    it off the same day: the binding (from today) was DELETED as 'never
    started', Ruth stayed Receiving, and neither act was on the Audit."""
    from tests.test_w5_eligibility_and_deposit_carry import _plan

    with tenant_ctx(brazos):
        _unit, account = _home(dana, brazos)
        senior = _discount(dana)
        plan = _plan(brazos)
    added = _call(
        rating_api.discount_plans,
        "post",
        dana,
        brazos,
        data={"plan": str(plan.id), "reason": "Seniors on the main tariff"},
        discount_id=str(senior.id),
    )
    assert added.status_code == 201, added.data
    with tenant_ctx(brazos):
        enrolment = discount_services.enrol_account(dana, senior.id, account["id"])
    removed = _call(
        rating_api.discount_plan_item,
        "delete",
        dana,
        brazos,
        data={"reason": "Wrong plan"},
        discount_id=str(senior.id),
        plan_id=str(plan.id),
    )
    assert removed.status_code == 200, removed.data
    with tenant_ctx(brazos):
        row = dm.DiscountEnrolment.objects.get(pk=enrolment["id"])
        assert row.ended_on == TODAY
        assert row.end_reason == f"Removed from plan {plan.name}"
    audit = _call(rating_api.discount_audit, "get", dana, brazos, discount_id=str(senior.id))
    actions = {row["action"]: row for row in audit.data["results"]}
    assert actions["discount.made_available_on_plan"]["reason"] == "Seniors on the main tariff"
    assert actions["discount.removed_from_plan"]["reason"] == "Wrong plan"
    assert actions["discount.removed_from_plan"]["after"]["plan"] == plan.name


# ═══ DEF-1005 — CSV on the Accounts and Audit tabs ═════════════════════════
def _csv(response):
    assert response.status_code == 200, getattr(response, "data", None)
    return b"".join(response.streaming_content).decode().splitlines()


def test_def_1005_accounts_csv_streams_the_whole_filtered_set(brazos, dana):
    with tenant_ctx(brazos):
        senior = _discount(dana)
        _bind(dana, brazos, senior)
        numbers = []
        for index in range(3):
            _unit, account = _home(dana, brazos, label=f"Unit {index}", name=f"Person {index}")
            discount_services.enrol_account(dana, senior.id, account["id"])
            numbers.append(account["account_no"])
    lines = _csv(
        _call(
            rating_api.discount_accounts,
            "get",
            dana,
            brazos,
            query={"format": "csv", "per": "1"},
            discount_id=str(senior.id),
        )
    )
    assert lines[0] == "Account,Customer,Address,Plan,Enrolled,Renew by,This month,Status"
    # `per=1` pages the JSON; the CSV is never a page.
    assert len(lines) == 4
    assert {line.split(",")[0] for line in lines[1:]} == set(numbers)
    assert all(line.endswith("Proof pending") or line.endswith("Receiving") for line in lines[1:])
    one = _csv(
        _call(
            rating_api.discount_accounts,
            "get",
            dana,
            brazos,
            query={"format": "csv", "q": numbers[1]},
            discount_id=str(senior.id),
        )
    )
    assert len(one) == 2 and one[1].startswith(numbers[1])


def test_def_1005_audit_csv_has_every_row_in_words(brazos, dana, audited):
    with tenant_ctx(brazos):
        senior = _discount(dana)
        plan = _bind(dana, brazos, senior)
    lines = _csv(
        _call(rating_api.discount_audit, "get", dana, brazos, query={"format": "csv"}, discount_id=str(senior.id))
    )
    assert lines[0] == "When,Who,What,Change,Reason"
    paged = _call(rating_api.discount_audit, "get", dana, brazos, discount_id=str(senior.id))
    assert len(lines) - 1 == paged.data["count"]
    assert any("discount.created" in line for line in lines)
    assert any(plan.name in line for line in lines), lines
    assert str(plan.id) not in "\n".join(lines)  # B14 rule 31


# ═══ DEF-BIL-9346 — the Document tab names discounts, not charges ══════════
def test_def_bil_9346_the_bill_level_bucket_names_its_discounts():
    """Ruth's December bill: water $60.00, Senior −$9.00, Autopay −$0.26 →
    *Discounts −$9.26*, nothing else at bill level; the bucket is unchanged."""
    water = SimpleNamespace(code="water", name="Water", sort=2)

    def line(kind, amount, service=None):
        return SimpleNamespace(
            kind=kind, amount=Decimal(amount), service_id=1 if service else None, service=service
        )

    invoice = SimpleNamespace(currency="USD", total=Decimal("50.74"))
    lines = [
        line("base", "8.00", water),
        line("usage", "52.00", water),
        line("discount", "-9.00"),
        line("discount", "-0.26"),
    ]
    block = billing_selectors._charges_by_service(invoice, lines)
    level = block["bill_level"]
    assert level["subtotal_display"] == "-9.26"
    assert level["discounts"] == {"line_count": 2, "subtotal": level["discounts"]["subtotal"], "subtotal_display": "-9.26"}
    assert level["others"]["line_count"] == 0
    assert level["others"]["kinds"] == []
    assert block["tie_out"]["ties_out"] is True
    with_tax = billing_selectors._charges_by_service(
        SimpleNamespace(currency="USD", total=Decimal("53.74")), [*lines, line("tax", "3.00")]
    )
    assert with_tax["bill_level"]["others"]["kinds"] == ["tax"]
    assert with_tax["bill_level"]["others"]["subtotal_display"] == "3.00"
    assert with_tax["bill_level"]["discounts"]["subtotal_display"] == "-9.26"

