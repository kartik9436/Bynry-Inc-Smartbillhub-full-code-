# ── Trace ──────────────────────────────────────────────
# Task:    one-time bill build plan B4 + B9 (04-docs/05-modules/07-billing/
#          12-one-time-bill-build-plan.md) — a base charge nobody defined and
#          bound bills $0.00 with a named warning; the warning travels on the
#          gathered data, the priced account, the preview, the draft answer
#          and the draft's frozen payload.
# Ruling:  12-governance/02-decision-log.md, 2026-09-30. PO, verbatim: *"here we
#          need to builf flexibility - if user did not define and bind base
#          charges in rate schedule - then as a default you take 0 and complete
#          the bill instead of refusing - if you want to show the warning you
#          can display it dueing the process"*. The 2026-09-28 ruling STANDS:
#          *"we will never take default value from plan $8.0 - that is
#          retired"* — so the default is $0.00 and never the retired figure.
# Contract: 13-one-time-bill-api-contract.md §2 — `warnings` at the top of the
#          answer, `{"key": "billing.oneTime.warn.baseNotSet", "params":
#          {"service": …}}`.
# Code:    apps/rating/selectors.py::base_charge_from_charge_code (🔒) ·
#          apps/rating/resolution.py::resolve (🔒) · apps/billing/gather.py
#          (🔒) · apps/billing/resolution_switch.py (🔒) · apps/billing/runs.py
#          · apps/billing/backbill.py · apps/billing/one_time.py
# ───────────────────────────────────────────────────────
"""**A BASE NOBODY DEFINED AND BOUND IS `$0.00` AND A WARNING — NEVER A REFUSAL,
NEVER THE RETIRED `$8.00`.**

⚠ **THE FIXTURE IS CHOSEN SO THAT THE WRONG ANSWER IS VISIBLE.** `_water_plan`
writes `$8.00` onto BOTH retired columns — the plan's and the rate schedule
version's. With R3 + R4 served (the shipped default), the chain still answers
the schedule's column for a service with no base code. So a fix that merely
stopped refusing would bill `$8.00` — the retired figure — on a bill that looks
entirely normal. Every `$0.00` case below is therefore also the proof that the
retired figure did not come back.

**WHAT STILL REFUSES** is the four shapes where the utility DID define something
and it contradicts itself — two codes, an amount AND sizes, a size the code
does not price, a connection whose size nobody recorded. Choosing between two
things a person wrote is a guess about money; a base nobody wrote is not.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import bill_warnings, gather, one_time, runs
from apps.billing import models as billing_models
from apps.rating import models as rating_models

from tests.test_def_2381_customer_type_not_covered import _typed
from tests.test_def_438_parity import (
    PERIOD_END,
    PERIOD_START,
    _account_on,
    _price_live,
    _water_plan,
)
from tests.test_def_rat_5782_the_bill_honours_the_named_base_code import (
    _base_code,
    _bind,
    _water_base,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _the_unit_bills_on_a_cycle(monkeypatch):
    """`BR-BIL-1066` (PO 2026-10-01) — an interim bill for an account on no
    billing cycle is now REFUSED (*"No billing cycle. Assign one on the
    account."*). This file's interim cases are about something else, so their
    unit is put on a cycle through the same metering seam the card and the
    refusal read. Only the cycle's NAME is given, not its calendar, so the
    denominator falls back to the window's own length and no figure here moves.
    """
    from apps.metering import selectors as _metering_selectors

    monkeypatch.setattr(
        _metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )

WATER = "water"
ZERO = Decimal("0")
#: What the retired columns say — the figure that must NOT come back.
RETIRED = Decimal("8.00")
#: What a live, bound code says, where a case needs one.
CODE_BASE = Decimal("19.75")


@pytest.fixture(autouse=True)
def _the_account_holds_water(monkeypatch):
    """⚠ **ADDED AT THE B4 × B8 MERGE, 2026-09-30.** `_account_on` builds an
    account with NO service agreements, and the B8 ruling (PO, option C: *"The
    bill still goes out, and the clerk sees the gap"*) now puts
    `billing.oneTime.warn.noAgreements` on exactly such an account. That
    warning is correct and is asserted in
    `test_br_bil_300_services_rulings_2026_09_30.py`; THIS file's subject is
    the base-not-set warning alone, so its accounts are stated to hold water —
    otherwise every `== (EXPECTED,)` here reads the other lane's warning as a
    regression (7 cases went red on exactly that before this fixture)."""
    from apps.customers import selectors as customer_selectors

    monkeypatch.setattr(
        customer_selectors, "billed_service_codes_for", lambda *_a, **_k: (WATER,)
    )


def _warned_services(data):
    return [
        row["params"]["service_code"]
        for row in data.warnings
        if row["key"] == bill_warnings.BASE_NOT_SET
    ]


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE FOUR CASES THAT NOW BILL $0.00 AND WARN
# ══════════════════════════════════════════════════════════════════════════


# BULK-CHG-3
def test_a__no_base_code_for_the_service__bills_zero_and_warns(brazos, dana):
    """Case (a). No `is_base` code for water at all; both retired columns say
    `$8.00`.

    RED on the tip (2026-09-30), through `pytest`:
        apps.billing.gather.GatherProblem: No base charge for water. Declare
        one on Charge codes.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        data = _price_live(account)

    assert _water_base(data) == ZERO
    assert _water_base(data) != RETIRED
    assert _warned_services(data) == [WATER]


# BULK-CHG-3
def test_b__the_schedule_binds_a_code_that_cannot_price_this_account__zero_and_warn(brazos, dana):
    """Case (b). The schedule binds `BASE-W-COM` (commercial only); the account
    is residential; an UNBOUND every-class code `BASE-W-ONE` also exists.

    `$0.00` — not `19.75` (the unbound code prices nothing, 2026-09-28) and not
    `8.00` (retired). RED on the tip: *"BASE-W-COM cannot price water here.
    Change it on the rate schedule."*
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, "residential")
        commercial = _base_code(brazos, "BASE-W-COM", Decimal("34.00"), classes=["commercial"])
        _base_code(brazos, "BASE-W-ONE", CODE_BASE)
        _bind(brazos, plan, commercial)
        data = _price_live(account)

    assert _water_base(data) == ZERO
    assert _warned_services(data) == [WATER]


# BULK-CHG-3
def test_b2__the_bound_code_was_retired_since__zero_and_warn(brazos, dana):
    """Case (b), the other way a binding stops answering: the code the schedule
    names has been retired. No other code exists, so this also proves the
    RETIRED schedule column is not the fallback for a dead binding."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        bound = _base_code(brazos, "BASE-W-GONE", CODE_BASE)
        _bind(brazos, plan, bound)
        from django.utils import timezone

        rating_models.Charge.objects.filter(pk=bound.pk).update(deleted_at=timezone.now())
        data = _price_live(account)

    assert _water_base(data) == ZERO
    assert _warned_services(data) == [WATER]


# BULK-CHG-3
def test_c__no_base_code_for_this_customer_type__zero_and_warn(brazos, dana):
    """Case (c). The only water base code names `commercial`; the account is
    `agricultural`. RED on the tip: *"No water base charge for agricultural.
    Add that type on Charge codes."*"""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, "agricultural")
        _base_code(brazos, "BASE-W-COM", Decimal("34.00"), classes=["commercial"])
        data = _price_live(account)

    assert _water_base(data) == ZERO
    assert _warned_services(data) == [WATER]


# BULK-CHG-3
def test_d__a_base_code_with_no_amount__zero_and_warn(brazos, dana):
    """Case (d). `BASE-W-BLANK` is ticked as water's base and states no amount
    and no sizes (`DEF-2340`'s shape). RED on the tip: *"BASE-W-BLANK states no
    base amount. Price it on the charge code."*"""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        blank = _base_code(brazos, "BASE-W-BLANK", None)
        rating_models.Charge.objects.filter(pk=blank.pk).update(amount_rule=None)
        data = _price_live(account)

    assert _water_base(data) == ZERO
    assert _warned_services(data) == [WATER]


# BULK-CHG-3
def test_a_live_bound_code_still_bills_its_figure_and_warns_nothing(brazos, dana):
    """The control. The code states `$19.75` and it is what bills; no warning,
    so no account that was fine yesterday gains a sentence today."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        # `DEF-RAT-9832` (2026-10-06): the schedule NAMES it — an unnamed code
        # now prices nothing, so the control binds the one code it means.
        _bind(brazos, plan, _base_code(brazos, "BASE-W-ONE", CODE_BASE))
        data = _price_live(account)

    assert _water_base(data) == CODE_BASE
    assert data.warnings == ()


# BULK-CHG-3
def test_a_stored_zero_is_a_price_and_is_not_warned_about(brazos, dana):
    """`DEF-277` / PO 2026-08-19 *"print $0.00"*. A code that STATES `0.00` has
    defined a base — it is free, not missing — so there is no warning."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _bind(brazos, plan, _base_code(brazos, "BASE-W-FREE", Decimal("0")))  # DEF-RAT-9832
        data = _price_live(account)

    assert _water_base(data) == ZERO
    assert data.warnings == ()


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE CONFLICTS STILL REFUSE
# ══════════════════════════════════════════════════════════════════════════


# BULK-CHG-3
def test_two_base_codes_both_apply__still_refuses(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _base_code(brazos, "BASE-W-A", Decimal("8.00"))
        _base_code(brazos, "BASE-W-B", CODE_BASE)
        data = _price_live(account)

    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): this asserted the
    # pool's refusal *"2 base charge codes for water. Scope them on Charge
    # codes."* The pool is retired — a schedule naming neither code takes
    # neither (*"if it is not provided then you will take it zeo"*), so the
    # bill completes at `$0.00` with the warning instead.
    assert _water_base(data) == ZERO
    assert _warned_services(data) == [WATER]


# BULK-CHG-3
def test_one_code_with_an_amount_AND_sizes__still_refuses(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        both = _base_code(brazos, "BASE-W-BOTH", CODE_BASE)
        _bind(brazos, plan, both)  # DEF-RAT-9832 — only a NAMED code is read
        rating_models.ChargeCodeAmount.objects.create(
            tenant=brazos, charge=both, size_class="W-58", amount=Decimal("9.00")
        )
        with pytest.raises(gather.GatherProblem) as refusal:
            _price_live(account)

    assert "BASE-W-BOTH states an amount and sizes." in str(refusal.value)


# BULK-CHG-3
def test_a_sized_code_with_no_price_for_this_size__still_refuses(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        sized = _base_code(brazos, "BASE-W-SIZED", None)
        _bind(brazos, plan, sized)  # DEF-RAT-9832 — only a NAMED code is read
        rating_models.ChargeCodeAmount.objects.create(
            tenant=brazos, charge=sized, size_class="W-34", amount=Decimal("11.00")
        )
        with pytest.raises(gather.GatherProblem) as refusal:
            _price_live(account)

    assert "BASE-W-SIZED has no price for W-58." in str(refusal.value)


# BULK-CHG-3
def test_a_sized_code_and_a_connection_whose_size_is_not_recorded__still_refuses(brazos, dana):
    """The size is unknown, so which price applies is unknown. Refused — by
    the gather's own size check or by rating's, both of which name the size."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan, size_class=None)
        sized = _base_code(brazos, "BASE-W-SIZED", None)
        _bind(brazos, plan, sized)  # DEF-RAT-9832 — only a NAMED code is read
        rating_models.ChargeCodeAmount.objects.create(
            tenant=brazos, charge=sized, size_class="W-58", amount=Decimal("11.00")
        )
        with pytest.raises(gather.GatherProblem) as refusal:
            _price_live(account)

    assert "size" in str(refusal.value)


# ══════════════════════════════════════════════════════════════════════════
# 3 · B9 — THE WARNING TRAVELS: priced account, draft payload, one-time answers
# ══════════════════════════════════════════════════════════════════════════

EXPECTED = {
    "key": "billing.oneTime.warn.baseNotSet",
    "params": {"service": "Water", "service_code": WATER},
}


# BULK-CHG-7
def test_B9_the_priced_account_and_its_payload_carry_the_warning(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        data = _price_live(account)
        priced = runs.price_account(data)

    assert data.warnings == (EXPECTED,)
    assert priced.warnings == (EXPECTED,)
    # What stage 6 freezes into `bill_payload` for a bulk run's draft.
    assert priced.usage.subscription.snapshot["warnings"] == [EXPECTED]
    base_lines = [line for line in priced.priced.lines if getattr(line, "kind", "") == "base"]
    assert base_lines and all(Decimal(str(line.amount)) == ZERO for line in base_lines)


# BULK-CHG-7
def test_B9_no_warning_leaves_the_payload_exactly_as_it_was(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _bind(brazos, plan, _base_code(brazos, "BASE-W-ONE", CODE_BASE))  # DEF-RAT-9832
        priced = runs.price_account(_price_live(account))

    assert priced.warnings == ()
    assert "warnings" not in priced.usage.subscription.snapshot


def _interim(account):
    return one_time.OneTimeRequest(
        account_id=str(account.id),
        kind=one_time.KIND_INTERIM,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        due_days=21,
    )


# BULK-CHG-7
def test_B9_one_time_preview_answers_the_warning_at_the_top(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        body = one_time.preview(_interim(account))

    assert body["priced"] is True, body.get("priced_unavailable")
    assert body["warnings"] == [EXPECTED]


# BULK-CHG-7
def test_B9_one_time_create_answers_it_and_the_draft_freezes_it(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        body = one_time.create(_interim(account))
        invoice = billing_models.Invoice.objects.get(pk=body["invoice_id"])

    assert body["warnings"] == [EXPECTED]
    assert invoice.bill_payload["warnings"] == [EXPECTED]


# BULK-CHG-7
def test_B9_a_preview_with_nothing_to_warn_answers_an_empty_list(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _bind(brazos, plan, _base_code(brazos, "BASE-W-ONE", CODE_BASE))  # DEF-RAT-9832
        body = one_time.preview(_interim(account))

    assert body["priced"] is True
    assert body["warnings"] == []
