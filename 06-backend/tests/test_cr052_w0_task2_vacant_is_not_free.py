# ── Trace ──────────────────────────────────────────────
# Story:    CR-052 wave W0, task 2 — "handle the two measured consequences of
#           the `non_billable` class: the account stops occupying its unit, and
#           the unit reads vacant"
# Screens:  S90 (the disconnects tab) · the owner's bill document
# Rules:    BR-CUS-107 (a cut account gets the sixth status, `Disconnected`,
#           class `non_billable`) · BR-CUS-110 (a cut ENDS occupancy — PO
#           2026-08-26, closing OQ-386) · BR-CUS-170 + PO 2026-08-27 (the
#           owner's bill carries the empty units' base charges) ·
#           BR-RAT-028 (the minimum bill, both modes) · BR-BIL-028 (a vacation
#           hold bills base and no usage) · OQ-1166 (CLOSED, PO 2026-08-30)
# Tests:    this file
# Impacts:  apps/rating/pricing/stages/apply_charges.py ·
#           apps/rating/engine.py (the one caller that knows `base_only`)
# ───────────────────────────────────────────────────────
"""CR-052 task 2 — **THE MONEY HALF. A VACANT UNIT IS NOT A FREE UNIT.**

`tests/test_cr052_w0_disconnected_at_the_cut.py` already proves the OCCUPANCY
half of this task and this file does not repeat it: that the cut account stops
occupying (`test_the_cut_account_stops_occupying_and_the_unit_reads_vacant`),
that metering agrees through its own published door
(`test_metering_reads_the_same_vacancy_through_the_published_seam`), and that
the terminal path still exists (`test_the_terminal_path_exists`). Those three
are green and are not re-asserted here.

**WHAT THEY DO NOT ASSERT IS THE CONSEQUENCE THAT COSTS SOMEBODY MONEY**, and
it is the one the task's own words point at. "The unit reads vacant" is a
statement about occupancy; what a reader actually needs to know is what the
utility BILLS for a unit in that state. Two things must both be true, they pull
in opposite directions, and until this file neither was proved:

  1. **VACANT IS NOT FREE.** The moment the cut account stops occupying, the
     unit re-enters `customers.selectors.base_charge_only_coverage` and its
     standing charge moves onto the OWNER's bill (BR-CUS-170; PO 2026-08-27:
     *"when bill is generated for A - we should consider common areas and U6 to
     U10 base charges"*). `test_br_cus_170_tc4` proves the forward direction —
     a move-in takes the unit OFF the owner's bill — and nothing proved the
     reverse, which is the direction a disconnection travels. If the exclusion
     test ever stopped keying on `occupying_accounts_for_unit`, a cut would
     silently make a unit free for everybody and the only symptom would be a
     landlord's bill quietly getting smaller.

  2. **VACANT IS NOT TOPPED UP EITHER.** A vacant unit is charged its BASE and
     nothing else — no minimum-bill adjustment on top.

════════════════════════════════════════════════════════════════════════════
OQ-1166 IS CLOSED, AND THE CODE HELD THE SUPERSEDED ANSWER UNTIL THIS CHANGE
════════════════════════════════════════════════════════════════════════════
**PO ruling 2026-08-30, verbatim:**

    *"when units are vacant - at that time, we are only charging base rates.
    minimum rates are applied when consumer is suppose to use minimum usage,
    but they end up using less than what they are suppose ot use"*

The decision log of that date states the general test the ruling turns on — **a
minimum applies when a consumer was SUPPOSED to use a minimum and used less; a
vacant unit was not supposed to use anything, so there is nothing to fall short
of** — and names `OQ-1166`'s own worked figure as money that *"should never have
been charged"*.

⚠ **THAT RULING REACHED THE DECISION LOG AND NOT THE CODE.** On 2026-08-31,
the day this file was written, `apply_charges.py` still topped a base-only
service up like any other and said so in its own docstring, and
`12-governance/01-open-questions.md` still read `Status: OPEN` under the
heading *"Implemented as (a) — the rule as signed — and flagged"*, which is the
option the PO ruled AGAINST. This is exactly the failure CLAUDE.md's build
step 0 exists to catch: a ruling that reaches every document and not the code.

**THE FIGURE, WORKED, AND IT IS THE ROW'S OWN.** Six empty units on the
building the rules use as their standing example each take water at an `$8.00`
base. Under a `$15.00` per-service minimum each was topped up by `$7.00`:

    per unit   15.00 - 8.00 = 7.00
    six units  7.00 x 6     = 42.00 a month

`$42.00` a month charged to an owner for units nobody lives in. After this
change each of those six units prices `$8.00` and the six price `$48.00`, not
`$90.00`.

**WHAT THIS FILE DELIBERATELY DOES NOT CLAIM.** Mode B — the PLAN FLOOR, applied
once over the whole finished bill — is UNCHANGED and is asserted unchanged
below, because `OQ-1166` costed the per-service minimum and the ruling's worked
figure is the per-service one. A bill whose every line is base-only is a
different case with a different figure and no ruling behind it; it is filed as
`DEF-2822` rather than swept in here.

❄️ **NO B4/B5 FIGURE MOVES.** `WE-3`/`GT-19` is a METERED water household at
`0.4 kgal` — it prices a usage line, so it is not base-only and cannot reach the
new branch. `10-scripts/03-golden-verify.py` reads **33 PASS / 0 FAIL** on both
sides of this change, and `test_the_signed_we3_household_is_untouched` below
re-prices it here so the two are not two different claims.
"""

from decimal import Decimal

import pytest

from apps.billing import gather, models as billing_models, rating_seam, runs
from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_br_cus_068_master_bill import (
    COMMON_BILL,
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    _cycle,
    _priced_plan,
    _run,
    a_master,
    elm_1408,
)
from tests.test_br_cus_170_master_covers_the_unbilled import (
    ELECTRIC_BASE,
    OWNER_WITH_ONE_EMPTY_UNIT,
    _occupy,
    _planned_metered_unit,
    _run_readings,
)
from tests.test_br_rat_028_minimum_bill import (
    FULL_MONTH,
    TAXED,
    WATER_BASE,
    kgal,
    water,
)

pytestmark = pytest.mark.django_db

#: `OQ-1166`'s own worked example, in the figures the row states.
SIX_EMPTY_UNITS = 6
PER_SERVICE_MINIMUM = Decimal("15.00")
#: What each empty unit WAS topped up by, and what the ruling removes.
TOP_UP_PER_UNIT = PER_SERVICE_MINIMUM - WATER_BASE  # 7.00
OQ_1166_MONTHLY_COST = TOP_UP_PER_UNIT * SIX_EMPTY_UNITS  # 42.00


def _adjustments(bill):
    return tuple(line for line in bill.lines if line.kind == "minimum_adjustment")


def _price_base_only(*tariffs, taxes=()):
    """Price a bill made only of base-only services — a vacant unit's shape."""
    return rating_seam.price_bill(
        base_only_services=tuple(tariffs),
        period=FULL_MONTH,
        account=TAXED,
        taxes=taxes,
    )


def _disconnect(account):
    """Assign BR-CUS-107's seeded `Disconnected` row (class `non_billable`).

    The status and not `commit_cut`, deliberately: this file is about what the
    STATUS does to the money, and `commit_cut`'s own behaviour — the final
    bill, the settlement, the safety rule that HOLDS the status when billing
    refuses — is proved in `tests/test_cr052_w0_the_23_23_case.py` and is not
    re-litigated here. Using the real door would make every case below depend
    on a priceable cut bill, which is a different test's fixture.
    """
    account.status = customer_models.AccountStatus.objects.get(
        tenant_id=account.tenant_id, code="disconnected"
    )
    account.save(update_fields=["status", "updated_at"])
    return account


# ══════════════════════════════════════════════════════════════════════════
# (1) VACANT IS NOT FREE — the cut moves the standing charge, it does not
#     delete it. This is `test_br_cus_170_tc4` run BACKWARDS.
# ══════════════════════════════════════════════════════════════════════════
def test_a_cut_puts_the_units_standing_charge_back_on_the_owners_bill(brazos, dana):
    """CR-052 task 2's second consequence, PRICED.

    Unit D is planned, connected and occupied. Its customer is cut. Three
    things must happen together and the third is the one nothing asserted:

      * the account stops occupying (`occupying_accounts_for_unit` empties);
      * the unit reads vacant (`active_account_for_unit` is None);
      * **and its `$12.00` electric base reappears on the OWNER's bill**, so
        the utility is still paid for the connection it is still providing.

    `$69.60` of common areas becomes `$81.60`. If a future change ever made
    the exclusion test key on something other than occupancy, this case is the
    one that goes red — the two above would both still pass while the landlord
    quietly stopped being charged.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CR52-T2-1")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        unit = _planned_metered_unit(
            dana, brazos, cycle, plan, premises, label="Unit D", asset_no="M-5201"
        )
        master = customer_models.Account.objects.get(pk=a_master(dana, premises)["id"])

        occupant = _occupy(dana, unit, name="Marcus Webb")
        unit_id = str(unit["id"])

        # OCCUPIED — the owner is not charged for it (BR-CUS-170 / tc4).
        occupied_coverage = [
            entry["label"] for entry in customer_selectors.base_charge_only_coverage(master)
        ]
        assert "Unit D" not in occupied_coverage
        assert customer_selectors.active_account_for_unit(unit_id) is not None

        # ── THE CUT ───────────────────────────────────────────────────────
        _disconnect(occupant)

        # (a) stops occupying · (b) reads vacant — restated here only because
        # (c) is meaningless without them being true in the SAME fixture.
        assert list(customer_selectors.occupying_accounts_for_unit(unit_id)) == []
        assert customer_selectors.active_account_for_unit(unit_id) is None

        # (c) …AND THE STANDING CHARGE MOVED RATHER THAN VANISHED.
        vacant_coverage = customer_selectors.base_charge_only_coverage(master)
        back = [entry for entry in vacant_coverage if entry["label"] == "Unit D"]
        assert len(back) == 1, vacant_coverage
        assert back[0]["has_plan"] is True
        assert back[0]["service_point_count"] == 1

        gathered = gather.gather_account(
            account=master,
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=(PERIOD_END - PERIOD_START).days + 1,
            # `DEF-CUS-9060` — the readings the RUN hands the gather
            # (`DEF-BIL-8724`, 2026-10-01). With none, the ruled path saw every
            # metered service as meterless and refused R3 for the hallway.
            readings=_run_readings(master),
        )
        base_only = [config for config in gathered.tariffs if config.base_only]
        assert len(base_only) == 1, gathered.tariffs
        assert base_only[0].service == "electric"
        assert base_only[0].base_charge == ELECTRIC_BASE

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        owner_row = next(row for row in prepared.ready if row.account_no == master.account_no)
        invoice = runs.calculate_account(
            owner_row, bill_run=_run(brazos, cycle, "cr52-t2-1"), service_date=SERVICE_DATE
        )

    # ❄️ The money, and it is the whole point of the case.
    assert invoice.total == OWNER_WITH_ONE_EMPTY_UNIT == Decimal("81.60")
    assert invoice.total - COMMON_BILL == ELECTRIC_BASE == Decimal("12.00")


def test_the_cut_account_itself_is_out_of_the_run_so_nobody_is_billed_twice(brazos, dana):
    """The other side of the same coin, and the reason it is safe.

    The unit's base moves to the owner ONLY because the cut account has left
    the run. If both were true at once the connection would be billed twice —
    once to a disconnected customer and once to their landlord — which is the
    shape `DEF-990` warned about from the opposite direction.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CR52-T2-2")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        unit = _planned_metered_unit(
            dana, brazos, cycle, plan, premises, label="Unit D", asset_no="M-5202"
        )
        occupant = _occupy(dana, unit, name="Marcus Webb")
        unit_id = str(unit["id"])

        in_run_before = [
            str(row.id) for row in customer_selectors.accounts_for_bill_run([unit_id])
        ]
        _disconnect(occupant)
        in_run_after = [
            str(row.id) for row in customer_selectors.accounts_for_bill_run([unit_id])
        ]

    assert str(occupant.id) in in_run_before
    assert in_run_after == []


# ══════════════════════════════════════════════════════════════════════════
# (2) VACANT IS NOT TOPPED UP — OQ-1166 (b), PO 2026-08-30
# ══════════════════════════════════════════════════════════════════════════
def test_a_vacant_unit_is_charged_base_and_no_minimum(brazos):
    """**THE RULING, WORKED ON ITS OWN FIGURES.**

    A base-only water service at an `$8.00` base under a `$15.00` per-service
    minimum. Before the ruling this bill was `$15.00` and carried a `$7.00`
    line called *Minimum bill adjustment*; the PO ruled a vacant unit is
    charged base rates only, so it is `$8.00` and carries no such line.

    **Never a `$0.00` adjustment either** — a bill that prints an empty
    adjustment row states that a minimum bit when it did not.
    """
    bill = _price_base_only(water(minimum_amount=PER_SERVICE_MINIMUM))
    assert _adjustments(bill) == ()
    assert bill.taxable_subtotal == WATER_BASE == Decimal("8.00")
    assert bill.total == Decimal("8.00")
    # The base charge IS billed — this is the half that stops the fix from
    # becoming "a vacant unit is free".
    assert [line.kind for line in bill.lines] == ["base"]
    assert bill.lines[0].amount == Decimal("8.00")


def test_the_oq_1166_figure_itself_six_empty_units_and_42_00(brazos):
    """`OQ-1166`'s costed consequence, priced as six bills rather than quoted.

    Six empty units at `$8.00` under a `$15.00` minimum:

        was   15.00 x 6 = 90.00
        now    8.00 x 6 = 48.00
        saved  7.00 x 6 = 42.00   <- the row's own figure

    The `$42.00` is computed from the priced bills, not typed as a constant, so
    a change that reintroduced the top-up moves this number instead of leaving
    a comment that used to be true.
    """
    unit_bills = [
        _price_base_only(water(minimum_amount=PER_SERVICE_MINIMUM))
        for _ in range(SIX_EMPTY_UNITS)
    ]
    now = sum((bill.total for bill in unit_bills), Decimal("0"))
    was = PER_SERVICE_MINIMUM * SIX_EMPTY_UNITS

    assert now == Decimal("48.00")
    assert was == Decimal("90.00")
    assert was - now == OQ_1166_MONTHLY_COST == Decimal("42.00")


def test_a_metered_service_that_used_nothing_is_STILL_topped_up(brazos):
    """**THE DISTINCTION THE RULING TURNS ON, AND THE ONE A HEURISTIC LOSES.**

    A base-only service and a metered service that consumed nothing can both
    reach `apply_charges` with no usage worth printing. They are NOT the same
    customer and they do not bill the same:

      * the METERED zero is a consumer who was supposed to use a minimum and
        used less — the PO's own words — so the minimum applies;
      * the BASE-ONLY one was never expected to use anything.

    `0.0 kgal` of water: `0.00` usage + `8.00` base = `8.00`, topped up by
    `7.00` to the `15.00` minimum. Same tariff, same base, same shortfall, and
    the opposite answer to the case above — which is why `base_only` is passed
    down the stages as a fact and never inferred from the absence of a line.
    """
    metered_zero = rating_seam.price_bill(
        services=((water(minimum_amount=PER_SERVICE_MINIMUM), kgal("0")),),
        period=FULL_MONTH,
        account=TAXED,
    )
    lines = _adjustments(metered_zero)
    assert [(line.service, line.amount) for line in lines] == [("water", Decimal("7.00"))]
    assert metered_zero.total == PER_SERVICE_MINIMUM == Decimal("15.00")


def test_mode_b_the_plan_floor_is_deliberately_unchanged(brazos):
    """**WHAT THIS CHANGE DOES NOT DO, ASSERTED SO A LANE CANNOT "FINISH" IT.**

    `OQ-1166` costed the PER-SERVICE minimum and the PO's worked figure is the
    per-service one. The plan floor is a fact about the PLAN applied once over
    the whole bill, it was never costed, and no ruling covers it — so it still
    bites on a base-only bill and that consequence is filed as `DEF-2822` with
    its own arithmetic instead of being quietly swept into this change.

    `8.00` of base under a `40.00` plan floor is still topped up by `32.00`.
    **This test asserts a KNOWN GAP, not a desired behaviour**, and the day
    `DEF-2822` is ruled it is the test that must be re-pointed — which is
    DEF-705's lesson and why it says so here.
    """
    bill = _price_base_only(water(plan_floor=Decimal("40.00")))
    lines = _adjustments(bill)
    assert len(lines) == 1
    assert lines[0].service is None
    assert lines[0].amount == Decimal("32.00")
    assert bill.total == Decimal("40.00")


# ══════════════════════════════════════════════════════════════════════════
# (3) ❄️ THE FROZEN FIGURE, RE-PRICED RATHER THAN ASSUMED
# ══════════════════════════════════════════════════════════════════════════
def test_the_signed_we3_household_is_untouched(brazos):
    """`WE-3` / `GT-19` is a METERED household and cannot reach the new branch.

    `0.4 kgal` of water: `1.60` usage + `8.00` base = `9.60`, topped up by
    `5.40` to `15.00`. It prices a usage line, so it is not base-only. The
    frozen figure is re-priced here so "no signed figure moved" is a
    measurement in this file and not a claim made in a commit message.
    """
    bill = rating_seam.price_bill(
        services=((water(minimum_amount=PER_SERVICE_MINIMUM), kgal("0.4")),),
        period=FULL_MONTH,
        account=TAXED,
    )
    lines = _adjustments(bill)
    assert [(line.service, line.amount) for line in lines] == [("water", Decimal("5.40"))]
    assert bill.taxable_subtotal == PER_SERVICE_MINIMUM == Decimal("15.00")


# ══════════════════════════════════════════════════════════════════════════
# (4) CLAUDE.md RULE 1 — TENANT SCOPING ON THE READ THIS FILE LEANS ON
# ══════════════════════════════════════════════════════════════════════════
def test_another_tenant_cannot_read_the_owners_coverage(brazos, lonestar, dana):
    """`base_charge_only_coverage` is the read that decides whose bill carries
    a vacant unit's money. It never crosses a tenant."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CR52-T2-3")
        plan = _priced_plan(brazos)
        premises, _hallway, _irrigation = elm_1408(dana, brazos, cycle, plan)
        _planned_metered_unit(
            dana, brazos, cycle, plan, premises, label="Unit D", asset_no="M-5203"
        )
        master = customer_models.Account.objects.get(pk=a_master(dana, premises)["id"])
        # `1408 Elm`'s own Units A/B/C are unplanned and unoccupied, so they are
        # legitimately in this list too (`has_plan: False` — nothing to omit,
        # which is what leaves the signed $69.60 untouched). The unit this file
        # cares about is the PLANNED one.
        mine = customer_selectors.base_charge_only_coverage(master)
        assert "Unit D" in [entry["label"] for entry in mine]
        assert [entry for entry in mine if entry["has_plan"]][0]["label"] == "Unit D"
    with tenant_ctx(lonestar):
        assert customer_selectors.base_charge_only_coverage(master) == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-052 W0 task 2 · 12-governance/11-change-requests.md
# generated: 2026-08-31 by the CR-052 W0 task 2/3/18/19 lane
# checklist: A✔ B✔ C✔ D=n/a(no API half) E=n/a(no frontend half) F✔ G✔
# gates: 10-scripts/03-golden-verify.py 33 PASS/0 FAIL before AND after✔
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
