# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-RAT-9832 (the PO's chain not implemented for a schedule naming
#           no base code) · closes DEF-RAT-9829 (commercial accounts refused)
# Ruling:   PO 2026-10-06, verbatim: *"You will take the code from plan -> rate
#           schedule -> base charges - in that case if it is provided then you
#           will take it if it is not provided then you will take it zeo ; but
#           you cannot take W-COM because it is availabel in charge coede - I
#           have provided this before also- you have asked again"* — restating
#           2026-09-30 (*"if user did not define and bind base charges in rate
#           schedule - then as a default you take 0 and complete the bill
#           instead of refusing"*).
# Code:     apps/rating/selectors.py (🔒) · apps/rating/resolution.py (🔒) ·
#           apps/rating/plan_reads.py · apps/rating/seams.py ·
#           apps/rating/schedule_reads.py
# ───────────────────────────────────────────────────────
"""The figures put to the PO, asserted so drift goes RED.

*"A water rate schedule that names no base code bills a $0.00 base, with a
warning telling the clerk to choose one — for every account on it, residential
and commercial alike. A schedule that names W-COM bills its $15.00; nothing is
ever picked from the charge-code list by class."*

W-ALL `$8.00` (every class) + W-COM `$15.00` (Commercial):

=========================  ==================  ===================
schedule                    residential          commercial
=========================  ==================  ===================
names none (before)         `$8.00` (pool)       refused (2 codes)
names none (now)            `$0.00` + warning    `$0.00` + warning
names W-COM                 —                    `$15.00`, no warning
=========================  ==================  ===================
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import bill_warnings
from apps.rating import models as rating_models
from apps.rating import plan_reads, resolution, selectors

from tests.test_def_2381_customer_type_not_covered import _typed
from tests.test_def_438_parity import _account_on, _price_live, _water_plan
from tests.test_def_rat_5782_the_bill_honours_the_named_base_code import (
    _base_code,
    _bind,
    _water_base,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

WATER = "water"
W_ALL = Decimal("8.00")
W_COM = Decimal("15.00")


@pytest.fixture(autouse=True)
def _cycle_and_water(monkeypatch):
    """The same two fixtures `test_b4_missing_base_bills_zero_with_warning`
    carries, for its reasons: the unit bills on a cycle, and the account holds
    water — so the only warning in play is the base one."""
    from apps.customers import selectors as customer_selectors
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )
    monkeypatch.setattr(
        customer_selectors, "billed_service_codes_for", lambda *_a, **_k: (WATER,)
    )


def _warned(data):
    return [
        row["params"]["service_code"]
        for row in data.warnings
        if row["key"] == bill_warnings.BASE_NOT_SET
    ]


def _world(brazos, dana, customer_class):
    plan = _water_plan(brazos, base_code=False)
    account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
    _typed(account, customer_class)
    w_all = _base_code(brazos, "W-ALL", W_ALL)
    w_com = _base_code(brazos, "W-COM", W_COM, classes=["commercial"])
    return plan, account, w_all, w_com


# ── the bill ───────────────────────────────────────────────────────────────
def test_residential_on_a_schedule_naming_none_bills_zero_and_warns(brazos, dana):
    """RED before the fix: `8.0000` — W-ALL taken from the pool by class."""
    with tenant_ctx(brazos):
        _plan, account, _w_all, _w_com = _world(brazos, dana, "residential")
        data = _price_live(account)
    assert _water_base(data) == Decimal("0")
    assert _warned(data) == [WATER]


def test_commercial_on_a_schedule_naming_none_bills_zero_and_warns(brazos, dana):
    """`DEF-RAT-9829`. RED before the fix: `GatherProblem: 2 base charge codes
    for water. Scope them on Charge codes.` — the bill refused. Not `$15.00`
    either: W-COM is in the catalogue and is not bound (*"you cannot take W-COM
    because it is availabel in charge coede"*)."""
    with tenant_ctx(brazos):
        _plan, account, _w_all, _w_com = _world(brazos, dana, "commercial")
        data = _price_live(account)
    assert _water_base(data) == Decimal("0")
    assert _water_base(data) != W_COM
    assert _warned(data) == [WATER]


def test_a_schedule_naming_w_com_bills_15_and_warns_nothing(brazos, dana):
    with tenant_ctx(brazos):
        plan, account, _w_all, w_com = _world(brazos, dana, "commercial")
        _bind(brazos, plan, w_com)
        data = _price_live(account)
    assert _water_base(data) == W_COM
    assert _warned(data) == []


# ── rating's answer, each reader ───────────────────────────────────────────
def test_the_selector_answers_not_named_for_every_class(brazos, dana):
    with tenant_ctx(brazos):
        _world(brazos, dana, "residential")
        answers = [
            selectors.base_charge_from_charge_code(WATER, customer_class=klass, named_code=None)
            for klass in ("residential", "commercial", None)
        ]
    for answer in answers:
        assert answer["amount"] is None and answer["code"] is None
        assert answer["not_set"] is True
        assert answer["refusal_reason"] == selectors.BASE_NOT_NAMED


def test_the_chain_takes_no_code_from_the_pool(brazos, dana):
    """R4's retired arm 2: a schedule naming none is `BaseChargeNotBound`,
    which `resolve` turns into `$0` with `base_source="not_set"`."""
    w_all = resolution.ChargeCode(code="W-ALL", service=WATER, is_base=True)
    with pytest.raises(resolution.BaseChargeNotBound):
        resolution.resolve_base_charge(((w_all, W_ALL),), WATER, None)
    # Named: the code's figure, unchanged.
    assert resolution.resolve_base_charge(((w_all, W_ALL),), WATER, "W-ALL") == W_ALL


def test_plan_screens_read_zero_and_not_named(brazos, dana):
    with tenant_ctx(brazos):
        _world(brazos, dana, "residential")
        from datetime import date

        block = plan_reads._base_block(WATER, None, ["commercial"], date(2026, 10, 6), {})
    assert block["state"] == "not_named"
    assert block["named"] is False
    assert block["code"] is None and block["codes"] == []
    assert block["flat_display"] == selectors._display_money(Decimal("0"))
    assert block["monthly_amount"] == "0.0000"


def test_the_plan_list_base_total_is_zero_not_a_pooled_figure(brazos, dana):
    with tenant_ctx(brazos):
        plan, _account, _w_all, _w_com = _world(brazos, dana, "residential")
        schedules = list(
            rating_models.PlanRateSchedule.objects.filter(rate_plan=plan).select_related(
                "service", "tariff"
            )
        )
        total, why = selectors._plan_base_total(plan, schedules)
    assert (total, why) == (Decimal("0"), None)


def test_the_rating_seam_states_zero_as_the_bill_does(brazos, dana):
    """The rate-change impact and the portal's standing charge read this seam;
    it states the bill's `$0.00`, never W-ALL's `$8.00` or *unresolved*."""
    from apps.rating import seams

    with tenant_ctx(brazos):
        _world(brazos, dana, "commercial")
        answer = seams.base_charge_for(WATER, customer_class="commercial", named_code=None)
    assert answer == {"wired": True, "amount": Decimal("0.0000"), "refusal": None}


# ═══════════════════════════════════════════════════════════════════════════
# THE STATEMENT THE PO SIGNED ON 2026-10-06 ("S9–S13 approve", S12)
# ═══════════════════════════════════════════════════════════════════════════
def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana):
    """**SIGNED 2026-10-06 (S12)** — review-ledger AMENDMENT row *"SIGN-OFF
    RECORDED (S12 of S9–S13)"* for `DEF-RAT-9832`; decision log *"S9–S13
    SIGNED"*.

    Shown to the PO, verbatim: *"A water rate schedule that names no base code
    bills a $0.00 base, with a warning telling the clerk to choose one — for
    every account on it, residential and commercial alike. A schedule that
    names W-COM bills its $15.00; nothing is ever picked from the charge-code
    list by class."* PO, verbatim: *"S9–S13 approve"*.

    One account on one water schedule, W-ALL `$8.00` (every class) and W-COM
    `$15.00` (Commercial) in the catalogue, through billing's own
    `gather_account`:

    * names none, the account Residential → base `$0.00` (never W-ALL's
      `$8.00`), the bill warning `billing.oneTime.warn.baseNotSet` for water,
      and the plan screen's base reads *not named* (*Choose a base code*);
    * names none, the SAME account Commercial → `$0.00` and the same warning
      (never W-COM's `$15.00`, never a refusal);
    * the schedule names W-COM → `$15.00`, no warning.

    NOT carried by the statement, and stays on the agenda (the PENDING row):
    the rate-schedule list's *Base code needed on N schedules*, a named code
    with no price for the size or class, the deploy consequence for live
    utilities (ruled separately the same day, option (b)).
    """
    from datetime import date

    with tenant_ctx(brazos):
        plan, account, _w_all, w_com = _world(brazos, dana, "residential")

        # ── names none → $0.00 with a warning — residential ──
        residential = _price_live(account)
        assert _water_base(residential) == Decimal("0")
        assert _water_base(residential) != W_ALL, "nothing is picked from the list by class"
        assert _warned(residential) == [WATER]
        [warning] = [w for w in residential.warnings if w["key"] == bill_warnings.BASE_NOT_SET]
        assert warning["key"] == "billing.oneTime.warn.baseNotSet"
        # "… telling the clerk to choose one" — the plan's base reads not named.
        block = plan_reads._base_block(WATER, None, ["residential"], date(2026, 10, 6), {})
        assert (block["state"], block["named"], block["monthly_amount"]) == (
            "not_named",
            False,
            "0.0000",
        )

        # ── "… residential and commercial alike" ──
        _typed(account, "commercial")
        commercial = _price_live(account)
        assert _water_base(commercial) == Decimal("0")
        assert _water_base(commercial) != W_COM, "nothing is picked from the list by class"
        assert _warned(commercial) == [WATER]

        # ── "A schedule that names W-COM bills its $15.00" ──
        _bind(brazos, plan, w_com)
        named = _price_live(account)
    assert _water_base(named) == Decimal("15.00")
    assert _warned(named) == []
