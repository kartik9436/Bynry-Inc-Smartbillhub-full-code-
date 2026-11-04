# ── Trace ──────────────────────────────────────────────
# Change:  PO ruling 2026-10-06 11 (a) — *"Put grace on the late-fee code. When
#          Type is Penalty, the form asks Grace days (default 5) and Calendar /
#          Business days, and billing uses the code's grace. The Settings
#          default stays as the starting value for new codes."*
#          Decision log: "PO RULINGS — LATE FEE: THE GRACE PERIOD IS SET ON THE
#          LATE-FEE CHARGE CODE". 🔒 ❄️ B4/B5 late fee — finance RE-SIGN owed.
# Rules:   BR-BIL-008 (0–30, AMENDED 2026-10-06: set on the code) · BR-BIL-002
#          (calendar | business) · BR-BIL-001 · BR-RAT-1011 · GT-8 (unchanged)
# Tests:   this file
# Impacts: apps/rating/{models,services,selectors,plan_reads,seams}.py ·
#          apps/rating/migrations/0066 · apps/billing/late_fee.py
# ───────────────────────────────────────────────────────
"""The late fee's grace comes from the late-fee CHARGE CODE.

The worked figure put to finance for the re-sign: *"Due 1 Nov, grace 5 days on
LATE, $100.00 unpaid after 6 Nov → $5.00 on the next bill; grace 10 days on
LATE → no fee until after 11 Nov."* Both halves are asserted, so a reader that
went back to the tenant's Billing-defaults grace fails the 10-day half.

WHAT WOULD MAKE THESE PASS WRONGLY: a fix that kept reading the tenant's grace
passes the 5-day half (the tenant default is 5) — the 10-day half is what
fails it. A fix that let a caller's grace win passes when the caller passes 5
and the code says 5; `test_a_caller_grace_that_disagrees_is_refused` fails it.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from apps.billing import late_fee
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.rating import services as rating_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, make_plan, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

DUE = dt.date(2026, 11, 1)
UNPAID = Decimal("100.00")
REASON = "Board moved the late-fee grace, October"


def _penalty(actor, code, **extra):
    payload = {
        "code": code,
        "name": "Late payment",
        "charge_type": "penalty",
        "kind": "plan",
        "amount_rule": "percent_with_minimum",
        "percent": "0.015",
        "min_amount": "5.00",
        **extra,
    }
    return rating_services.create_charge(actor, payload)


def _plan_on(tenant, charge_id, name):
    plan = make_plan(tenant, name=name, code=name.lower().replace(" ", "-"))
    with tenant_ctx(tenant):
        rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge_id=charge_id)
    return plan


def _fee(plan, as_of, **grace):
    fee, terms = late_fee.assess_late_fee_for_plan(
        rate_plan_id=plan.id, overdue_amount=UNPAID, due_date=DUE, as_of=as_of, **grace
    )
    return fee, terms


def test_a_new_penalty_code_starts_at_the_billing_defaults_grace(brazos, dana):
    """*"The Settings default stays as the starting value for new codes."*"""
    with tenant_ctx(brazos):
        row = _penalty(dana, "LATE-G1")
        assert (row["grace_days"], row["grace_mode"]) == (5, "calendar")
        detail = rating_selectors.charge_detail(rating_selectors.charge_or_404(row["id"]))
        assert detail["grace_default"] == {"days": 5, "mode": "calendar"}


def test_the_form_sets_grace_days_and_mode_on_a_penalty_code(brazos, dana):
    with tenant_ctx(brazos):
        row = _penalty(dana, "LATE-G2", grace_days=10, grace_mode="business")
        assert (row["grace_days"], row["grace_mode"]) == (10, "business")
        moved = rating_services.update_charge(
            dana, row["id"], {"grace_days": 7, "grace_mode": "calendar", "reason": REASON}
        )
        assert (moved["grace_days"], moved["grace_mode"]) == (7, "calendar")


def test_grace_outside_0_to_30_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            _penalty(dana, "LATE-G3", grace_days=31)
        keys = {fe["message_key"] for fe in caught.value.field_errors}
        assert "rating.plans.grace_days_range" in keys


def test_only_a_penalty_carries_a_grace(brazos, dana):
    with tenant_ctx(brazos):
        row = rating_services.create_charge(
            dana,
            {
                "code": "RECON-G",
                "name": "Reconnection",
                "charge_type": "one_time",
                "kind": "plan",
                "amount_rule": "flat",
                "amount": "25.00",
                "grace_days": 9,
            },
        )
        assert (row["grace_days"], row["grace_mode"]) == (None, None)


def test_the_worked_figure_grace_5_on_late(brazos, dana):
    """Due 1 Nov, grace 5 days, $100.00 unpaid after 6 Nov → $5.00."""
    with tenant_ctx(brazos):
        row = _penalty(dana, "LATE-G5", grace_days=5, grace_mode="calendar")
    plan = _plan_on(brazos, row["id"], "Grace five plan")
    with tenant_ctx(brazos):
        on_6th, terms = _fee(plan, dt.date(2026, 11, 6))
        on_7th, _ = _fee(plan, dt.date(2026, 11, 7))
    assert on_6th == Decimal("0.00")
    assert on_7th == Decimal("5.00")
    assert (terms.grace_days, terms.grace_mode, terms.grace_from) == (5, "calendar", "charge_code")


def test_the_worked_figure_grace_10_on_late(brazos, dana):
    """Grace 10 days on the code → no fee until after 11 Nov (the tenant says 5)."""
    with tenant_ctx(brazos):
        row = _penalty(dana, "LATE-G10", grace_days=10, grace_mode="calendar")
    plan = _plan_on(brazos, row["id"], "Grace ten plan")
    with tenant_ctx(brazos):
        on_7th, _ = _fee(plan, dt.date(2026, 11, 7))
        on_11th, _ = _fee(plan, dt.date(2026, 11, 11))
        on_12th, _ = _fee(plan, dt.date(2026, 11, 12))
    assert on_7th == Decimal("0.00"), "the tenant's 5-day grace must not reach this fee"
    assert on_11th == Decimal("0.00")
    assert on_12th == Decimal("5.00")


def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana):
    """**FINANCE RE-SIGN (HUMAN-GUIDE §6). PO, verbatim, 2026-10-06: *"S1–S8
    approve"*** — S8, shown as: *"Due 1 Nov, grace 5 days on LATE, $100.00
    unpaid after 6 Nov → $5.00 on the next bill; grace 10 days on LATE → no
    fee until after 11 Nov."*

    The tenant's own LATE code, its grace set to 5 and then to 10 on the code
    (`BR-BIL-008` as re-signed): $100.00 unpaid, due 1 Nov. GT-8's own figure
    is asserted by `tests/golden`, unchanged.
    """
    with tenant_ctx(brazos):
        late = rating_models.Charge.objects.get(tenant=brazos, code="LATE", deleted_at__isnull=True)
        rating_services.update_charge(
            dana, str(late.id), {"grace_days": 5, "grace_mode": "calendar", "reason": REASON}
        )
    plan = _plan_on(brazos, late.id, "Signed grace plan")
    with tenant_ctx(brazos):
        on_6th, terms = _fee(plan, dt.date(2026, 11, 6))
        on_7th, _ = _fee(plan, dt.date(2026, 11, 7))
        rating_services.update_charge(
            dana, str(late.id), {"grace_days": 10, "grace_mode": "calendar", "reason": REASON}
        )
        ten_on_11th, ten_terms = _fee(plan, dt.date(2026, 11, 11))
        ten_on_12th, _ = _fee(plan, dt.date(2026, 11, 12))
    # Grace 5 on LATE: nothing on 6 Nov, $5.00 once 6 Nov has passed.
    assert (terms.grace_days, terms.grace_from) == (5, "charge_code")
    assert on_6th == Decimal("0.00")
    assert on_7th == Decimal("5.00")
    # Grace 10 on LATE: no fee until after 11 Nov.
    assert (ten_terms.grace_days, ten_terms.grace_from) == (10, "charge_code")
    assert ten_on_11th == Decimal("0.00")
    assert ten_on_12th == Decimal("5.00")


def test_a_plan_override_stated_before_the_ruling_keeps_applying(brazos, dana):
    """Our judgment: no customer's late-fee date moves on deploy."""
    with tenant_ctx(brazos):
        row = _penalty(dana, "LATE-G6", grace_days=10, grace_mode="calendar")
    plan = _plan_on(brazos, row["id"], "Grace override plan")
    with tenant_ctx(brazos):
        rating_models.PlanPenaltyRule.objects.create(
            tenant_id=brazos.id, rate_plan=plan, grace_days=3, grace_mode="calendar"
        )
        on_5th, terms = _fee(plan, dt.date(2026, 11, 5))
    assert on_5th == Decimal("5.00")
    assert (terms.grace_days, terms.grace_from) == (3, "plan")


def test_a_caller_grace_that_disagrees_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        row = _penalty(dana, "LATE-G7", grace_days=10, grace_mode="calendar")
    plan = _plan_on(brazos, row["id"], "Grace caller plan")
    with tenant_ctx(brazos):
        with pytest.raises(ValueError, match="disagrees"):
            _fee(plan, dt.date(2026, 11, 7), grace_days=5, grace_mode="calendar")
        agreeing, _ = _fee(plan, dt.date(2026, 11, 12), grace_days=10, grace_mode="calendar")
    assert agreeing == Decimal("5.00")


def test_a_plan_may_not_state_a_new_grace_override(brazos, dana):
    """The plan form offers none; the API refuses one by name."""
    with tenant_ctx(brazos):
        row = _penalty(dana, "LATE-G8")
    plan = _plan_on(brazos, row["id"], "Grace refusal plan")
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            rating_services._refuse_new_plan_grace(plan, {"grace_days": 9, "grace_mode": None})
        assert caught.value.field_errors[0]["message_key"] == "rating.plans.grace_on_charge_code"
        rating_models.PlanPenaltyRule.objects.create(
            tenant_id=brazos.id, rate_plan=plan, grace_days=3, grace_mode="calendar"
        )
        # Re-sending the stored override, or clearing it, is allowed.
        rating_services._refuse_new_plan_grace(plan, {"grace_days": 3, "grace_mode": "calendar"})
        rating_services._refuse_new_plan_grace(plan, {"grace_days": None, "grace_mode": None})


def test_the_plan_shows_the_codes_grace(brazos, dana):
    from apps.rating import plan_reads

    with tenant_ctx(brazos):
        row = _penalty(dana, "LATE-G9", grace_days=10, grace_mode="business")
    plan = _plan_on(brazos, row["id"], "Grace shown plan")
    with tenant_ctx(brazos):
        sections = plan_reads.plan_sections(plan.id)
        options = plan_reads.form_options()
    late = [code for code in sections["charge_codes"] if code["late_fee"]]
    assert late and late[0]["grace"] == {"days": 10, "mode": "business", "from": "charge_code"}
    offered = [code for code in options["charge_codes"] if code["ref"]["code"] == "LATE-G9"]
    assert offered[0]["grace"] == {"days": 10, "mode": "business", "from": "charge_code"}
