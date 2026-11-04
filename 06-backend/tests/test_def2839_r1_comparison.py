# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2839 — R1's comparison was `str(data.rate_plan_id) !=
#          str(resolved.plan.plan_id)`, and the catalogue is built as
#          `build_catalogue(plan_id=inputs.plan_id, …)` where `inputs.plan_id`
#          IS `data.rate_plan_id`. Both sides were the same value by
#          construction, so R1's `47 agree` was 47 restatements of ONE value and
#          `figures_differ` was unreachable — measured: 94 account evaluations
#          across a clean run and a `--sabotage R1` run produced it NOT ONCE.
#          The sabotage appeared to work only because it moved the row through
#          the REFUSAL path (`chain_refused:NoPlanInForce`).
# Rules:   BR-RAT-007 (a period is priced on the terms in force AT the service
#          date) · BR-RAT-030 (only PUBLISHED plans are assignable) ·
#          BR-CUS-013 (the plan version travels with the reference because the
#          bill SNAPSHOTS it) · BR-BIL-874 (a named step with no fork is a
#          REFUSAL, never a silent no-op)
# Tests:   this file is the unit half; `10-scripts/cr052_r1r7_shadow_measure.py
#          --sabotage R1-version` is the same proof on real rows.
# Impacts: apps/billing/resolution_shadow.compare (R1's rows) ·
#          10-scripts/cr052_r1r7_shadow_measure.probe_r1_r2 (which applies
#          `compare()`'s R1 expression verbatim and must not drift from it)
# ───────────────────────────────────────────────────────
"""R1's comparison, PROVED ABLE TO DISAGREE — and its residual limit stated.

⚠ **THE FAILURE THIS FILE EXISTS FOR IS A CHECK THAT CANNOT FAIL**, which this
repo found ELEVEN of in one day. R1's was the most expensive kind: it fed an
`agree` column that a Product Owner then ruled a pricing rule switchable on.

**WHAT R1 ACTUALLY DECIDES, and which half of it is comparable.** R1 is
*"account -> unit -> PLAN VERSION in force on the service-period end date"*. Its
answer object is a `resolution.PlanVersion`, whose identity is the pair
`(plan_id, version)`:

  * **`plan_id` IS AN INPUT.** `resolution_shadow.adapt` hands it to
    `build_catalogue`, and `resolution_catalogue.plan_version_facts` filters
    `pk=plan_id` and then stamps `plan_id=str(plan.id)` back onto the row it
    yields. Comparing it compares a value with itself. It is asserted as an
    INVARIANT here rather than counted as agreement: if it ever differs the
    shadow's own plumbing is broken and every other row of that run is
    meaningless, which is a louder thing than a pricing divergence.
  * **`version` IS RE-READ.** It never reaches the chain — `ChainInputs` carries
    `plan_id` and no version — so `plan_version_facts` reads
    `RatePlan.version` for itself while the live path reads it through
    `rating.selectors.plan_ref`. That is two derivations of one answer, which is
    what a comparison needs.

**THE RESIDUAL LIMIT, STATED RATHER THAN LEFT TO BE DISCOVERED** — the same
posture R3 and R6 already take about their own circularity. Both sides read the
same `rate_plans.version` column of the same row under the same
`status='published'` filter, so this comparison bites where the two paths TREAT
that column differently — `plan_version_facts` coerces (`int(plan.version or 1)`)
and `plan_ref` does not — and on the chain's in-force narrowing, which
`plan_ref` does not apply at all and which surfaces as `NoPlanInForce` rather
than as a figure. **It is strictly stronger than comparing an input to itself,
and it is weaker than R7's, whose two sides are narrowed by different code.**
That sentence is the honest content of R1's agree column and it belongs beside
any decision taken from it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import resolution_shadow
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.billing.rating_seam import Quantity, TariffConfig

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
PLAN_ID = "11111111-1111-1111-1111-111111111111"
VERSION_ID = "22222222-2222-2222-2222-222222222222"


class _Plan:
    """`rating.resolution.PlanVersion`'s shape, structurally.

    It carries `version` because the real dataclass does and because that is
    now the half of R1's answer the comparison reads. A fake that omitted it
    would let the comparison read `None` on both sides and pass — the exact
    shape of the defect this file closes.
    """

    def __init__(self, *, plan_id=PLAN_ID, version=1):
        self.plan_id = plan_id
        self.version = version


class _ServiceResolution:
    def __init__(self):
        self.service = "water"
        self.schedule_version_id = VERSION_ID
        self.connection_size = "W-58"
        self.base_charge = Decimal("8.00")
        self.billable_quantity = Decimal("8.000000")
        self.meter_multiplier = Decimal("1")
        self.money_factor = Decimal("1")
        self.base_source = "charge_code"
        self.quantity_source = "read"


class _DiscountResolution:
    def __init__(self, applied=()):
        self.modelled = True
        self.applied = tuple(applied)


class _Resolution:
    def __init__(self, *, plan=None):
        self.plan = plan if plan is not None else _Plan()
        self.services = (_ServiceResolution(),)
        self.charge_codes = ()
        self.discounts = _DiscountResolution()
        self.taxes = ()


def _live(*, plan_id=PLAN_ID, plan_version=1) -> AccountBillingData:
    return AccountBillingData(
        account_id="a1",
        account_no="AC-1",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=31,
        service_days=31,
        rate_plan_id=plan_id,
        rate_plan_version=plan_version,
        tariffs=(
            TariffConfig(
                service="water",
                model="tiered",
                billed_unit="kgal",
                base_charge=Decimal("8.00"),
                multiplier=Decimal("1"),
                jurisdiction_factor=Decimal("1"),
                version_id=VERSION_ID,
                size_class="W-58",
            ),
        ),
        readings=(
            ServiceReading(
                service_code="water",
                consumption=Quantity(amount=Decimal("8.000000"), unit="kgal"),
                prior_read=Decimal("100"),
                current_read=Decimal("108"),
            ),
        ),
    )


def _r1(divergences):
    return [row for row in divergences if row.step == "R1"]


# ══════════════════════════════════════════════════════════════════════════
# The comparison must be able to DISAGREE — the whole point of the defect
# ══════════════════════════════════════════════════════════════════════════


def test_r1_disagrees_when_the_two_paths_stamp_DIFFERENT_plan_versions():
    """THE RED PROOF. Before the fix this passed silently: the ids matched.

    The live path stamped v1 on the bill (`BR-CUS-013` — the reference
    SNAPSHOTS the version) and the chain resolved v2 for the same plan. That is
    two different sets of terms pricing one period and R1 is the step that owns
    it, so it must reach the disagree column as a FIGURE and not as a refusal.
    """
    found = resolution_shadow.compare(
        _live(plan_version=1), _Resolution(plan=_Plan(version=2))
    )
    rows = _r1(found)
    assert len(rows) == 1, [row.sentence() for row in found]
    assert str(rows[0].live) == "1"
    assert str(rows[0].chain) == "2"
    # The figures ARE the finding — carried verbatim into the clerk's sentence
    # rather than summarised into "the two paths disagree".
    assert "1" in rows[0].sentence() and "2" in rows[0].sentence()


def test_r1_disagrees_when_the_live_path_carries_NO_version_and_the_chain_does():
    """`plan_version_facts` coerces (`int(plan.version or 1)`) and `plan_ref`
    does not, so a NULL `rate_plans.version` is one place the two paths really
    do differ. It is a figure difference, not a refusal.
    """
    found = resolution_shadow.compare(
        _live(plan_version=None), _Resolution(plan=_Plan(version=1))
    )
    assert len(_r1(found)) == 1, [row.sentence() for row in found]


def test_r1_agrees_when_the_versions_match():
    """A comparison that ALWAYS fires is as useless as one that never does."""
    found = resolution_shadow.compare(
        _live(plan_version=1), _Resolution(plan=_Plan(version=1))
    )
    assert _r1(found) == [], [row.sentence() for row in found]


# ══════════════════════════════════════════════════════════════════════════
# The plan id is an INPUT — an invariant, never an agreement
# ══════════════════════════════════════════════════════════════════════════


def test_a_plan_id_that_differs_is_raised_as_BROKEN_PLUMBING_not_reported_as_a_divergence():
    """`adapt` hands the chain `data.rate_plan_id`; the catalogue stamps it
    back. The two CANNOT differ, so if they ever do, the shadow is comparing
    two different accounts and every other figure in that run is meaningless.

    That is louder than a pricing divergence and is raised rather than counted
    — the same posture `compare()` already takes for a run that compared
    nothing at all.
    """
    with pytest.raises(AssertionError) as caught:
        resolution_shadow.compare(
            _live(plan_id=PLAN_ID),
            _Resolution(plan=_Plan(plan_id="99999999-9999-9999-9999-999999999999")),
        )
    assert "plan" in str(caught.value).lower()


def test_the_chain_is_told_the_plan_ID_and_is_never_told_the_VERSION():
    """The defect and its fix, asserted STRUCTURALLY rather than as a story.

    `ChainInputs` is the whole of what the shadow hands the ruled path. It
    carries `plan_id` — which is why comparing that field compares an input to
    itself — and carries NO version at all, which is what makes
    `resolved.plan.version` a genuine second read of `rate_plans.version` and
    therefore the half of R1's answer a comparison can be built on.

    Asserted here so that a future lane which adds a version to `ChainInputs`
    is told, by a RED test, that it has just made R1's comparison circular
    again. That is the failure mode this whole file exists for and it would
    otherwise be invisible: the agree column would simply go on reading 47.
    """
    from dataclasses import fields

    names = {field.name for field in fields(resolution_shadow.ChainInputs)}
    assert "plan_id" in names
    assert not [name for name in names if "version" in name], sorted(names)
