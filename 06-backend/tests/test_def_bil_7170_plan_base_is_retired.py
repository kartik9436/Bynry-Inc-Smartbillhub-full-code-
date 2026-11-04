# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-7170 (critical, reported by the Product Owner) —
#          `gather._base_charge_for` read the RETIRED plan base (and the
#          equally retired rate-schedule column) beside the bound charge code,
#          and REFUSED the bill when they differed: *"Two base charges for
#          water. Clear 11.50 on the plan."* A tenant whose migration left a
#          stale figure had EVERY bill for that service stopped, told to clear
#          a value on an object the product itself says does not define it.
#          DEF-CWP-7001 — the portal demo fixture wrote `base_charge 8.0000`
#          into the plan for every service while its charge codes said water
#          12.00, sewer 8.00 and trash 9.00.
# Ruling:  12-governance/02-decision-log.md, 2026-09-28. PO, verbatim: *"we
#          ahve to take ot from Charge code - whya re you confuse about it -
#          charge code binded in plan - unitl it is part of plan we cannot take
#          amount from charge code - we will never take default value from plan
#          $8.0 - that is retired"*
# Rules:   BR-RAT-088 (the CHARGE CODE owns the base amount) · BR-RAT-1025 (the
#          schedule NAMES the code) · BR-RAT-108 (customer classes are an
#          INCLUSION list) · BR-BIL-055 (a refusal stops ONE account) · DEF-277
#          (a stored 0.00 is a PRICE and still bills $0.00) · B14 rules 32/33
#          (clerk copy: no rule id, rationale at zero words) · CLAUDE.md hard
#          rule 2 (money 4 dp stored, 2 dp displayed)
# Impacts: apps/billing/gather.py :: _base_charge_for, _tariff_config_for
#          apps/portal/sample_data.py :: the demo plan payload
# Proof:   10-scripts/def_bil_7170_plan_base_retired_proof.py — the same three
#          cases on the SEEDED tenant on real PostgreSQL 16, printed from
#          `gather.gather_account`. This file is the SQLite half.
# ───────────────────────────────────────────────────────
"""**A STALE FIGURE ON A PLAN MAY NOT STOP A BILL.**

⚠ **THE FIGURES ARE CHOSEN SO THAT NO CASE CAN PASS BY COINCIDENCE.** The
plan (and the rate schedule version under it) carry `$8.00`, which is what
`_water_plan` has always written; the charge code says **`$19.75`**. Every
assertion below is on `19.7500`, a figure neither retired column states, so a
green case cannot be a case where the two happened to agree — which is the
exact blind spot that let the old refusal ship. `BR-RAT-088`'s own entry
records it: *"all 47 ready accounts on the seeded tenant state the SAME figure
on both objects, so no bill moved"* — true, and it means **the refusal branch
was never exercised by a real account.** Law 7's *incapable of failing*, one
step removed.

**THE THREE CASES, AND THE THIRD IS THE ONE THAT STOPS A BILL:**

  1. the code and the plan AGREE          -> unchanged, bills the code's figure
  2. the code and the plan DISAGREE       -> was refused; now bills the CODE and
                                             the plan's figure is not read
  3. no bound charge code answers         -> REFUSES, by its own name, and never
                                             falls back to the retired column

⚠ **CASE 3 IS THE RULING'S SECOND SENTENCE AND IT IS NOT THE DEFECT.** *"we
will never take default value from plan $8.0 - that is retired"* — never a
source and never a fallback, **not even when the charge code is silent**. A
tenant that declared no `is_base` code for a service used to bill from the
plan; it is now told so in six words and pointed at Charge codes. That is the
only bill this change stops, and it is stopped deliberately.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import gather
from apps.rating import models as rating_models

from tests.test_def_438_parity import (
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

WATER = "water"

#: What the CHARGE CODE says. Deliberately not `8.00`, which is what
#: `_water_plan` writes onto both retired columns.
CODE_BASE = Decimal("19.75")
#: The migration artefact a real tenant is left with. Neither `8.00` (what the
#: fixture writes) nor `19.75` (what the code says), so a case that ends up on
#: it is unmistakable.
STALE_PLAN_BASE = Decimal("11.50")


def _plan_states(tenant, plan, amount):
    """Put `amount` on the PLAN's retired base column and nowhere else."""
    rating_models.PlanService.objects.filter(
        tenant=tenant, rate_plan_id=plan.id
    ).update(base_charge=amount)


def _schedule_states(tenant, amount):
    """Put `amount` on the RATE SCHEDULE VERSION's retired base column."""
    rating_models.TariffVersion.objects.filter(
        tenant=tenant, tariff__service__code=WATER
    ).update(base_charge=amount)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE THREE CASES, END TO END, THROUGH THE PATH THAT BILLS
# ══════════════════════════════════════════════════════════════════════════


def test_case_1__the_code_and_the_plan_AGREE__bills_the_same_as_before(brazos, dana):
    """**UNCHANGED, and this is the case the 2026-08-31 switch was measured on.**

    Both objects say `19.75`. The bill says `19.75`, as it did before this
    change and for the 47 seeded accounts that made the old behaviour look
    safe. It is here so that the fix cannot be mistaken for a change of
    ARITHMETIC: nothing about what a customer pays moves when the two agree.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _bind(brazos, plan, _base_code(brazos, "BASE-W-ONE", CODE_BASE))  # DEF-RAT-9832
        _plan_states(brazos, plan, CODE_BASE)
        _schedule_states(brazos, None)

        data = _price_live(account)

    assert _water_base(data) == CODE_BASE


def test_case_2__the_code_and_the_plan_DISAGREE__bills_the_CODE(brazos, dana):
    """**THE DEFECT.** The plan carries a stale `$11.50`; the bound code says
    `$19.75`.

    RED on the tip, through `pytest`, quoted:

        apps.billing.gather.GatherProblem: Two base charges for water.
        Clear 11.50 on the plan.

    On the seeded tenant on real PostgreSQL the same reproduction reads *"Two
    base charges for water. Clear 11.50 on the plan."* against a `SCW-RES`
    account — see the proof script named in this file's trace block.

    **The bill is now `$19.75` and the plan's `$11.50` is not read at all.**
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _bind(brazos, plan, _base_code(brazos, "BASE-W-ONE", CODE_BASE))  # DEF-RAT-9832
        _plan_states(brazos, plan, STALE_PLAN_BASE)
        _schedule_states(brazos, None)

        data = _price_live(account)

    assert _water_base(data) == CODE_BASE


def test_case_2b__the_RATE_SCHEDULE_s_stale_figure_is_ignored_too(brazos, dana):
    """The other retired column, and it was the other half of the same refusal
    (*"Clear 8.00 on the rate schedule."*). `BR-RAT-088` retired it first and
    `RateScheduleWizard` has had no control for it since, so any figure there
    is a migration artefact by definition."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _bind(brazos, plan, _base_code(brazos, "BASE-W-ONE", CODE_BASE))  # DEF-RAT-9832
        _plan_states(brazos, plan, None)
        _schedule_states(brazos, STALE_PLAN_BASE)

        data = _price_live(account)

    assert _water_base(data) == CODE_BASE


def test_case_2c__BOTH_retired_columns_stale_and_they_disagree_with_each_other(
    brazos, dana
):
    """The worst configuration a migration can leave: three figures, all
    different. There is still exactly ONE source, so there is nothing to choose
    between and nothing to refuse."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _bind(brazos, plan, _base_code(brazos, "BASE-W-ONE", CODE_BASE))  # DEF-RAT-9832
        _plan_states(brazos, plan, STALE_PLAN_BASE)
        _schedule_states(brazos, Decimal("48.00"))

        data = _price_live(account)

    assert _water_base(data) == CODE_BASE


def test_case_3__no_bound_charge_code__bills_ZERO_and_never_reads_the_plan(brazos, dana):
    """**THE RULING'S SECOND SENTENCE.** The plan states `$8.00` and no `is_base`
    code exists for water.

    Before this change the bill was produced from the plan's `$8.00`. It now
    refuses, in six words, and names the screen that can fix it. It must NOT
    name the plan: sending a clerk to type a figure into the column the product
    has stopped reading would refuse again on the next run and say nothing
    about why.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _plan_states(brazos, plan, Decimal("8.00"))
        _schedule_states(brazos, None)

        # ⚠ SUPERSEDED 2026-09-30: this REFUSED. PO: *"if user did not define
        # and bind base charges in rate schedule - then as a default you take 0
        # and complete the bill instead of refusing"*. The half this case is
        # named for — the plan's `$8.00` is never read — is exactly as it was.
        data = _price_live(account)

    assert _water_base(data) == Decimal("0")
    # AMENDED 2026-10-01 (billing red triage): + `noAgreements`, FIRST. Since
    # `31358c239` (2026-09-30, PO option C: *"The bill still goes out, and the
    # clerk sees the gap and can fix the account."*) an account with NO service
    # agreements on file bills everything and is WARNED, and this fixture's
    # account holds none. The base warning this case is about is unchanged.
    assert [w["key"] for w in data.warnings] == [
        "billing.oneTime.warn.noAgreements",
        "billing.oneTime.warn.baseNotSet",
    ]


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT MUST NOT WEAKEN — rating's own refusals, untouched
# ══════════════════════════════════════════════════════════════════════════


def test_a_NAMED_code_that_cannot_price_this_account_bills_ZERO_not_the_other_code(
    brazos, dana
):
    """`DEF-RAT-6918`. The schedule names `BASE-W-COM`, scoped to commercial;
    the account is residential. Rating's sentence reaches the clerk WHOLE and
    is not softened into a figure — and it must not be replaced by this
    change's own six words, which would name the wrong repair."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _plan_states(brazos, plan, None)
        _schedule_states(brazos, None)
        commercial = _base_code(
            brazos, "BASE-W-COM", Decimal("34.00"), classes=["commercial"]
        )
        _base_code(brazos, "BASE-W-ONE", CODE_BASE)
        _bind(brazos, plan, commercial)

        # ⚠ SUPERSEDED 2026-09-30: this REFUSED by name. A bound code that
        # cannot answer here is *no base bound for this account*, so it bills
        # `$0.00` with a warning — and still never the unbound `BASE-W-ONE`.
        data = _price_live(account)

    assert _water_base(data) == Decimal("0")
    assert _water_base(data) != CODE_BASE
    # AMENDED 2026-10-01 (billing red triage): + `noAgreements`, FIRST. Since
    # `31358c239` (2026-09-30, PO option C: *"The bill still goes out, and the
    # clerk sees the gap and can fix the account."*) an account with NO service
    # agreements on file bills everything and is WARNED, and this fixture's
    # account holds none. The base warning this case is about is unchanged.
    assert [w["key"] for w in data.warnings] == [
        "billing.oneTime.warn.noAgreements",
        "billing.oneTime.warn.baseNotSet",
    ]


def test_two_codes_and_NO_binding_still_refuse_on_the_AMBIGUITY(brazos, dana):
    """`DEF-468`. Two codes declaring themselves the base and nobody saying
    which is a bill decided by catalogue ORDER. That refusal is CORRECT and
    this change must not weaken it by one account — the plan's figure is not
    a tie-breaker, it is a retired column."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _plan_states(brazos, plan, Decimal("8.00"))
        _schedule_states(brazos, None)
        _base_code(brazos, "BASE-W-A", Decimal("8.00"))
        _base_code(brazos, "BASE-W-B", CODE_BASE)

        data = _price_live(account)

    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): still never catalogue
    # order and still never the plan's figure — but no longer a refusal. Nobody
    # named a code, so neither is taken: `$0.00` with the warning.
    assert _water_base(data) == Decimal("0")


def test_a_stored_ZERO_on_the_charge_code_still_bills_zero(brazos, dana):
    """PO ruling 2026-08-19, verbatim *"print $0.00"* (`DEF-277`). A stored
    zero is a PRICE and a blank is *this size is not served*. The ruling of
    2026-09-28 moved the SOURCE and touched neither."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _base_code(brazos, "BASE-W-FREE", Decimal("0"))
        _plan_states(brazos, plan, Decimal("8.00"))
        _schedule_states(brazos, None)

        data = _price_live(account)

    assert _water_base(data) == Decimal("0")


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-BIL-7170 · DEF-CWP-7001 · decision log 2026-09-28 · BR-RAT-088 ·
#         BR-RAT-1025 · hard-won law 7 (prove the guard red, in the harness
#         that runs it) · hard-won law 14 (a money path proved on PostgreSQL)
# generated: 2026-09-28 by lane BIL-PLANBASE (claude)
# gates: every case above was run RED first, through `pytest` and not through
#        `__main__`; cases 2, 2b and 2c raised *"Two base charges for water.
#        Clear 11.50 on the plan."* and case 3 billed 8.00 from the retired
#        column. The same three cases were reproduced and then proved on the
#        SEEDED tenant on real PostgreSQL 16 — see the proof script above.
# review: 🔒 apps/billing/gather.py is a sensitive path; the implementation row
#         is in 12-governance/09-human-review-ledger.md.
