# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2823 — R3 refuses every connection size on every schedule of
#          every tenant that has migrated to BR-RAT-088, because it read its
#          per-size base from `tariff_versions.base_charge` — the column the
#          ruling RETIRED and the S11 wizard has had no control for since.
# Rules:   BR-RAT-088 (PO 2026-08-20 — the CHARGE CODE owns the base amount; a
#          plan displays it, never defines it) · BR-RAT-108 (one service, two
#          amounts, separated by customer CLASS) · BR-RAT-120 + PO 2026-08-28
#          (an unpriced size is REFUSED and never substituted) · BR-RAT-012 /
#          BR-RAT-027 (both SUPERSEDED by BR-RAT-088) · PO 2026-08-19 ruling 1
#          (*"no plan cannot override prices"*) · CLAUDE.md hard rule 2
# Impacts: apps/rating/resolution.py (R3/R4) · apps/rating/selectors.py ·
#          apps/billing/gather.py · apps/billing/resolution_shadow.py
# ───────────────────────────────────────────────────────
"""THE BASE COMES FROM THE CHARGE CODE, AND R3 STOPS ASKING FOR A RETIRED COLUMN.

⚠ **THE RED HALF IS KEPT EXECUTABLE, NOT DESCRIBED.** `test_RED_*` below runs
the pre-ruling function on the exact data a real utility has — a size row the
tenant configured and a NULL `tariff_versions.base_charge` — and asserts that it
still refuses. That is the defect, reproduced, in a test that would go green if
somebody ever "tidied" the old behaviour away and left the new gate untested.

**AND THE GREEN HALF ASSERTS THE SOURCE, NOT THE NUMBER.** A test that asserts
`$8.00` passes when the figure is right and the SOURCING is wrong, which is
`DEF-154` exactly — *"the golden suite could not see it: B5 hands the base
charge to the engine directly, so the ARITHMETIC over it was right and the
SOURCING was wrong."* So the cases below blank the plan AND the schedule and
require the charge code alone to produce the figure, and change the CODE's
amount and require the bill to move with it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather
from apps.rating import resolution

pytestmark = pytest.mark.django_db


WATER = "water"
SIZE = "W-58"
UNPRICED = "3-inch"


def _schedule(size_rows: dict[str, Decimal | None]) -> resolution.ScheduleVersion:
    return resolution.ScheduleVersion(
        version_id="v-1",
        service=WATER,
        tariff_id="t-1",
        effective_from=date(2026, 1, 1),
        size_rows=size_rows,
    )


# ══════════════════════════════════════════════════════════════════════════
# R3 · THE DEFECT, AND THE GATE THAT REPLACED IT
# ══════════════════════════════════════════════════════════════════════════


def test_RED_the_pre_ruling_R3_refuses_a_size_the_tenant_configured():
    """**THE DEFECT.** `resolve_size_row` — R3 as it was — refuses a size that
    IS on the schedule, because the base beside it is blank.

    That blank is not a configuration mistake: `BR-RAT-088` retired
    `tariff_versions.base_charge` and `RateScheduleWizard.tsx` removed its
    control in the same ruling (*"CARRIED, NEVER EDITED … no control, no
    editing, no loss"*), and `decimalOut("")` omits the key, so **every
    schedule version a real utility creates through this product stores NULL
    there.** Measured on the shipped fixture: 47 of 47 accounts refused here
    while the live path billed all 47 correctly at `$8.00`.

    The refusal is asserted rather than described so that removing the old
    behaviour cannot quietly remove the evidence of what was wrong with it.
    """
    schedule = _schedule({SIZE: None})
    with pytest.raises(resolution.SizeNotServed) as refusal:
        resolution.resolve_size_row(schedule, resolution.MeterFacts(WATER, SIZE))
    assert "BLANK base charge" in str(refusal.value)
    assert SIZE in str(refusal.value)


def test_R3_now_asks_only_whether_the_schedule_SERVES_the_size():
    """`BR-RAT-088`: *"R3's refusal semantics are unchanged — a size absent from
    the schedule still means not served — but the base itself now resolves
    through R4."* Same data, same size, no money: the size resolves."""
    schedule = _schedule({SIZE: None})
    assert resolution.resolve_served_size(schedule, resolution.MeterFacts(WATER, SIZE)) == SIZE


def test_R3_STILL_refuses_a_size_the_schedule_does_not_serve():
    """⚠ **THE GATE IS MOVED, NOT WEAKENED**, and this is the assertion that
    says so. PO ruling 2026-08-28: an unpriced size is REFUSED and never
    substituted. A fix that made R3 stop refusing would be worse than the
    defect — `DEF-1810`'s `$8.00`/`$8.00` pair, a 3-inch connection billed at
    the 5/8 rate."""
    schedule = _schedule({SIZE: Decimal("8.00")})
    with pytest.raises(resolution.SizeNotServed) as refusal:
        resolution.resolve_served_size(schedule, resolution.MeterFacts(WATER, UNPRICED))
    assert UNPRICED in str(refusal.value)
    assert "no row on the rate schedule" in str(refusal.value)


# ══════════════════════════════════════════════════════════════════════════
# R4 · THE AMOUNT, AND THAT IT COMES FROM THE CODE
# ══════════════════════════════════════════════════════════════════════════


def _code(**kwargs) -> resolution.ChargeCode:
    base = {
        "code": "BASE-W",
        "service": WATER,
        "is_base": True,
        "charge_type": "recurring",
        "amount_rule": "flat",
    }
    base.update(kwargs)
    return resolution.ChargeCode(**base)


def test_R4_prices_the_PER_SIZE_amount_and_not_the_flat_one():
    """`BR-RAT-088`'s own worked example: `BASE-W` at `$8.00` for a 5/8" and
    `$34.00` for a 2". The per-size table is where the ruling put the base, and
    this is the assertion that the SIZE selects the figure."""
    code = _code(amounts={SIZE: Decimal("8.00"), '2"': Decimal("34.00")})
    assert resolution.charge_code_amount(code, SIZE) == Decimal("8.00")
    assert resolution.charge_code_amount(code, '2"') == Decimal("34.00")


def test_R4_refuses_a_size_the_CODE_does_not_price_and_never_substitutes():
    """PO ruling 2026-08-28. The refusal that used to live at R3 for a blank
    schedule column now lives here, where the money is."""
    code = _code(amounts={SIZE: Decimal("8.00")})
    with pytest.raises(resolution.ChargeCodeAmountMissing) as refusal:
        resolution.charge_code_amount(code, UNPRICED)
    assert "states no amount for connection size" in str(refusal.value)


def test_the_chain_resolves_the_base_from_the_CODE_with_a_BLANK_schedule():
    """**THE FIX, END TO END, ON THE DATA A REAL UTILITY HAS.**

    The schedule serves the size and states no base (the retired column); the
    charge code states `$8.00`. Before `DEF-2823` this refused at R3 and no
    bill was produced at all.

    ⚠ **AND `base_source` IS ASSERTED, WHICH IS WHAT MAKES THIS A TEST OF THE
    SOURCE RATHER THAN OF THE NUMBER.** `$8.00` is also what the pre-ruling
    path produced from the plan; only `base_source == "charge_code"` says the
    figure came from the object the PO ruled owns it.
    """
    catalogue = resolution.Catalogue(
        plan_versions=(
            resolution.PlanVersion(
                plan_id="p-1",
                version=1,
                services=(WATER,),
                schedules={WATER: "t-1"},
                effective_from=date(2026, 1, 1),
            ),
        ),
        # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES the code.
        schedule_versions=(resolution.replace(_schedule({SIZE: None}), base_charge_code="BASE-W"),),
        charge_codes=(_code(amounts={SIZE: Decimal("8.00")}),),
    )
    resolved = resolution.resolve(
        catalogue=catalogue,
        account=resolution.AccountFacts(account_no="AC-1", unit_id="u-1"),
        premises=resolution.PremisesFacts(),
        meters=(resolution.MeterFacts(WATER, SIZE, multiplier=Decimal("1")),),
        quantities={WATER: Decimal("10")},
        service_date=date(2026, 7, 1),
    )
    line = resolved.services[0]
    assert line.base_charge == Decimal("8.00")
    assert line.base_source == "named_charge_code"  # DEF-RAT-9832
    assert line.connection_size == SIZE


def test_the_chain_answers_NOT_SET_when_neither_the_code_nor_the_legacy_column_states_one():
    """⚠ SUPERSEDED 2026-09-30 — this case was *"…_REFUSES_when_neither…"*.

    PO ruling of that day: *"if user did not define and bind base charges in
    rate schedule - then as a default you take 0 and complete the bill instead
    of refusing"*. The chain no longer raises `ChargeCodeAmountMissing` here;
    it answers a `$0` base with `base_source="not_set"`, which billing turns
    into a named warning. It is no longer SILENT, which was the whole of
    `DEF-154`'s objection to a zero.
    """
    catalogue = resolution.Catalogue(
        plan_versions=(
            resolution.PlanVersion(
                plan_id="p-1",
                version=1,
                services=(WATER,),
                schedules={WATER: "t-1"},
                effective_from=date(2026, 1, 1),
            ),
        ),
        schedule_versions=(_schedule({SIZE: None}),),
        charge_codes=(),
    )
    resolved = resolution.resolve(
        catalogue=catalogue,
        account=resolution.AccountFacts(account_no="AC-1", unit_id="u-1"),
        premises=resolution.PremisesFacts(),
        meters=(resolution.MeterFacts(WATER, SIZE, multiplier=Decimal("1")),),
        quantities={WATER: Decimal("10")},
        service_date=date(2026, 7, 1),
    )
    assert resolved.services[0].base_charge == Decimal("0")
    assert resolved.services[0].base_source == "not_set"


def test_the_legacy_scalar_still_answers_for_a_tenant_with_no_base_code():
    """⚠ **THE FALLBACK IS DELIBERATE AND IT IS NOT A HEDGE.** `Charge.is_base`
    defaults False, so a tenant provisioned before the ruling has no
    charge-code answer to give. Refusing there would stop every bill for every
    such tenant the day this shipped. The schedule's retired scalar answers,
    and `base_source` RECORDS that it did, so the migration is observable
    rather than assumed."""
    catalogue = resolution.Catalogue(
        plan_versions=(
            resolution.PlanVersion(
                plan_id="p-1",
                version=1,
                services=(WATER,),
                schedules={WATER: "t-1"},
                effective_from=date(2026, 1, 1),
            ),
        ),
        schedule_versions=(_schedule({SIZE: Decimal("12.00")}),),
        charge_codes=(),
    )
    resolved = resolution.resolve(
        catalogue=catalogue,
        account=resolution.AccountFacts(account_no="AC-1", unit_id="u-1"),
        premises=resolution.PremisesFacts(),
        meters=(resolution.MeterFacts(WATER, SIZE, multiplier=Decimal("1")),),
        quantities={WATER: Decimal("10")},
        service_date=date(2026, 7, 1),
    )
    assert resolved.services[0].base_charge == Decimal("12.00")
    assert resolved.services[0].base_source == "schedule"


# ══════════════════════════════════════════════════════════════════════════
# THE LIVE PATH · `gather._base_charge_for`
# ══════════════════════════════════════════════════════════════════════════


def test_the_live_path_takes_the_CODE_over_the_plan_when_only_the_code_states_one():
    """`BR-RAT-088` — and this is the case that proves the SOURCE moved: both
    superseded objects say nothing and a figure still comes out.

    ⚠ **THE CALL LOST TWO ARGUMENTS ON 2026-09-28 (`DEF-BIL-7170`).** It read
    `_base_charge_for(WATER, None, None, Decimal("8.00"))` — the plan's figure
    and the rate schedule version's, both `None` here. Both parameters are gone
    and `code_base` is keyword-only; the ANSWER is the same figure it always
    was.
    """
    assert gather._base_charge_for(WATER, code_base=Decimal("8.00")) == Decimal("8.00")


def test_the_live_path_IGNORES_a_plan_figure_that_disagrees_with_the_code():
    """⚠ **SUPERSEDED BEHAVIOUR, AND THE SUPERSESSION IS THE POINT.**

    This case used to be `…_REFUSES_a_plan_figure_that_disagrees_with_the_code`
    and it asserted a `GatherProblem`. **PO ruling 2026-09-28**, verbatim: *"we
    ahve to take ot from Charge code - whya re you confuse about it - charge
    code binded in plan - unitl it is part of plan we cannot take amount from
    charge code - we will never take default value from plan $8.0 - that is
    retired"*.

    What the old refusal cost is `DEF-BIL-7170`, critical: a tenant whose
    migration left a different figure on the plan had **every bill for that
    service stopped**, told to clear a value on an object the product itself
    says does not define it. The old behaviour was measured as safe because
    *"all 47 ready accounts state the SAME figure on both objects"* — which
    means the refusal branch was never exercised by a real account at all.

    **The worked figure, and it is the fixture's own collision:** plan `IND`
    states `$180.00` for electric where `BASE-E` states `$12.00`. The bill is
    now `$12.00` and the plan's `$180.00` is not read.
    """
    assert gather._base_charge_for(
        "electric", code_base=Decimal("12.00")
    ) == Decimal("12.00")


def test_the_live_path_bills_ZERO_where_no_bound_charge_code_answers():
    """⚠ SUPERSEDED 2026-09-30 — this case was *"…_REFUSES_where…"*. PO: *"as
    a default you take 0 and complete the bill instead of refusing"*. The
    2026-09-28 half below still holds: the default is `$0.00`, never the
    plan's figure — there is still no fallback chain.

    The ruling's SECOND sentence, which is the half that stops a bill that
    used to be produced: *"we will never take default value from plan $8.0 -
    that is retired"* — never a source and never a fallback, **not even when
    the charge code is silent**.

    This case used to be `…_is_UNCHANGED_where_the_tenant_declares_no_base_code`
    and asserted the pre-ruling chain: the plan's figure, else the schedule's,
    else a refusal. There is no chain any more. A tenant that has declared no
    `is_base` code for a service is told so, in six words, and pointed at the
    one screen that can fix it — never at the plan, which would send a clerk to
    type a figure into the column the product has stopped reading.
    """
    assert gather._base_charge_for(WATER, code_base=None) == Decimal("0")


def test_the_two_retired_parameters_cannot_be_passed_BY_POSITION():
    """⚠ **THIS IS THE GUARD ON THE DELETION ITSELF, AND IT IS WHY
    `code_base` IS KEYWORD-ONLY.**

    The old call was `_base_charge_for(service, plan_base, schedule_base,
    code_amount)`. Had the new signature simply taken two positionals, every
    stale call in the tree would have passed **the plan's figure where the
    charge code's belongs** — and billed the retired column under the ruling
    that retired it, with no error anywhere. That is `DEF-154`'s shape: a
    well-formed bill nobody can see is wrong.
    """
    with pytest.raises(TypeError):
        gather._base_charge_for(WATER, Decimal("8.00"), None, Decimal("8.00"))


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2823 · BR-RAT-088 (04-docs/05-modules/06-rating/02-business-rules.md)
#         · PO ruling 2026-08-31 (*"plan -> charges code -> base scharges"*)
# generated: 2026-08-31 by the DEF-2823 lane (claude)
# gates: every case above was run RED first — the R3 pair by pointing the chain
#        at a NULL `tariff_versions.base_charge` on the seeded tenant (47 of 47
#        refused), the live-path pair by blanking `plan_services.base_charge`
#        on the same tenant and watching the run still bill $390.00.
# ──────────────────────────────────────────────────────────
