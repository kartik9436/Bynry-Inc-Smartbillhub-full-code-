# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2798 — the pricing shadow compared R1, R2 and a fused R3/R4 base
#          and NOTHING at R3b, R5, R6 or R7, so four of the eight cutover steps
#          could never reach a zero disagreement class because nothing could
#          ever produce a non-zero one. A x1000 meter-multiplier error passed
#          the whole harness silently.
# Rules:   BR-RAT-001 (the multiplier precedes the tier walk) · BR-RAT-102 (the
#          jurisdiction factor scales the money, per service) · BR-RAT-110 (the
#          plan makes a discount AVAILABLE, the enrolment GRANTS it) ·
#          DEF-273 (a failed tax condition means NO LINE, never a zero one) ·
#          PO ruling 2026-08-11 (metering applies the meter multiplier; the
#          pricing engine never does)
# Tests:   this file is the unit half; `10-scripts/cr052_r1r7_shadow_measure.py
#          --sabotage <step>` is the same five proofs on real rows.
# Impacts: apps/billing/resolution_shadow.compare
# ───────────────────────────────────────────────────────
"""Each of the four new comparisons, PROVED ABLE TO DISAGREE.

⚠ **A COMPARISON THAT CANNOT DISAGREE IS THE WORST KIND OF CHECK THIS REPO HAS
FOUND**, because it licenses switching a pricing rule on false evidence. So each
case below breaks ONE figure and asserts the divergence it must produce, and a
matching case asserts that identical figures produce none — a comparison that
always fires is as useless as one that never does.

**TWO NEGATIVE RESULTS ARE ASSERTED HERE ON PURPOSE**, because both are limits a
reader would otherwise have to take on trust from a docstring:

  * `TariffConfig.multiplier` is a TRIP-WIRE and not the live meter multiplier,
    so a thousandfold error on it moves nothing — and that is correct, not a gap;
  * a register difference of ZERO hides a multiplier error, because nothing
    times anything is nothing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.billing import resolution_shadow
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.billing.rating_seam import DiscountRule, Quantity, TariffConfig, TaxRule

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
PLAN_ID = "11111111-1111-1111-1111-111111111111"
VERSION_ID = "22222222-2222-2222-2222-222222222222"


class _Plan:
    plan_id = PLAN_ID


class _ServiceResolution:
    """`rating.resolution.ServiceResolution`'s shape, structurally.

    `compare()` reads the ruled side by attribute — rating is called BY billing
    and billing's tests do not import rating's dataclasses to build a fake of
    them — which is the same posture `apps/rating/pricing/stages/normalize.py`
    records for the seam it reads.
    """

    def __init__(
        self,
        *,
        service="water",
        base_charge=Decimal("8.00"),
        billable_quantity=Decimal("8.000000"),
        meter_multiplier=Decimal("1"),
        money_factor=Decimal("1"),
    ):
        self.service = service
        self.schedule_version_id = VERSION_ID
        self.connection_size = "W-58"
        self.base_charge = base_charge
        self.billable_quantity = billable_quantity
        self.meter_multiplier = meter_multiplier
        self.money_factor = money_factor
        self.base_source = "charge_code"
        self.quantity_source = "read"


class _Resolution:
    def __init__(self, *, services, discounts=(), taxes=()):
        self.plan = _Plan()
        self.services = tuple(services)
        self.charge_codes = ()
        self.discounts = _DiscountResolution(discounts)
        self.taxes = tuple(taxes)


class _DiscountResolution:
    def __init__(self, applied):
        self.modelled = True
        self.applied = tuple(applied)


class _CatalogueTax:
    def __init__(self, code):
        self.code = code


def _live(
    *,
    consumption=Decimal("8.000000"),
    multiplier=Decimal("1"),
    jurisdiction_factor=Decimal("1"),
    discounts=(),
    taxes=(),
) -> AccountBillingData:
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
        rate_plan_id=PLAN_ID,
        tariffs=(
            TariffConfig(
                service="water",
                model="tiered",
                billed_unit="kgal",
                base_charge=Decimal("8.00"),
                multiplier=multiplier,
                jurisdiction_factor=jurisdiction_factor,
                version_id=VERSION_ID,
                # `DEF-2823` — the live path CARRIES the size it priced at, so
                # R3 can be compared separately from R4. `gather` resolves it
                # from `metering.connection_size_for`, the same seam the shadow
                # adapter reads, so an ordinary account has one size on both
                # sides. Leaving it unset here would make every case below
                # report an R3 divergence that no real account can produce: the
                # adapter BLOCKS an account whose size is None rather than
                # comparing against it.
                size_class="W-58",
            ),
        ),
        readings=(
            ServiceReading(
                service_code="water",
                consumption=(
                    None if consumption is None else Quantity(amount=consumption, unit="kgal")
                ),
                prior_read=Decimal("100"),
                current_read=Decimal("108"),
            ),
        ),
        discounts=tuple(discounts),
        taxes=tuple(taxes),
    )


def _steps(divergences):
    return sorted(row.step for row in divergences)


# ══════════════════════════════════════════════════════════════════════════
# The baseline — identical figures produce NO divergence at any step
# ══════════════════════════════════════════════════════════════════════════


def test_two_paths_that_agree_everywhere_produce_no_divergence():
    """A comparison that always fires is as useless as one that never does."""
    found = resolution_shadow.compare(
        _live(), _Resolution(services=[_ServiceResolution()])
    )
    assert found == [], [row.sentence() for row in found]


# ══════════════════════════════════════════════════════════════════════════
# R3b · the billable quantity
# ══════════════════════════════════════════════════════════════════════════


def test_R3b_a_thousandfold_quantity_error_is_caught():
    """THE PROOF `DEF-2798` WAS FILED FOR, in one case.

    On real rows this ran as `--sabotage R3b`: account AC-2026-00001's live
    billable quantity for water was rewritten from `8.000000` to `8000.000000`
    kgal and R3b moved from `47 agree / 0 disagree` to `46 / 1`. Before the
    comparison existed the same class of error moved NOTHING ANYWHERE.
    """
    found = resolution_shadow.compare(
        _live(consumption=Decimal("8000.000000")),
        _Resolution(services=[_ServiceResolution()]),
    )
    assert _steps(found) == ["R3b"]
    assert "8000.000000" in found[0].sentence()


def test_R3b_a_missing_live_read_beside_a_ruled_quantity_is_caught():
    """*"No usable read"* against *"a quantity of 8 kgal"* is the most expensive
    disagreement on this list, and a `None` on one side must not be skipped."""
    found = resolution_shadow.compare(
        _live(consumption=None), _Resolution(services=[_ServiceResolution()])
    )
    assert _steps(found) == ["R3b"]


def test_R3b_a_service_the_live_path_carries_no_reading_row_for_is_caught():
    """The sentinel case: no reading ROW at all is a different fact from a row
    whose consumption is None, and both are divergences rather than silence."""
    live = _live()
    found = resolution_shadow.compare(
        # A live object with a tariff for water and no reading row for it.
        AccountBillingData(
            account_id=live.account_id,
            account_no=live.account_no,
            behavior_class=live.behavior_class,
            currency=live.currency,
            tax_exempt=live.tax_exempt,
            period_start=live.period_start,
            period_end=live.period_end,
            cycle_days=live.cycle_days,
            service_days=live.service_days,
            rate_plan_id=live.rate_plan_id,
            tariffs=live.tariffs,
            readings=(),
        ),
        _Resolution(services=[_ServiceResolution()]),
    )
    assert _steps(found) == ["R3b"]
    assert "no reading row" in found[0].note


def test_R3b_is_NOT_compared_on_TariffConfig_multiplier_and_that_is_correct():
    """⚠ **`DEF-2798`'s OWN SUGGESTED PAIRING IS WRONG AND THIS PINS IT.**

    The defect row proposes comparing `ServiceResolution.meter_multiplier`
    against `TariffConfig.multiplier`. That field is a TRIP-WIRE:
    `apps/rating/pricing/stages/normalize.py` REFUSES BY NAME any tariff
    reaching the engine with a multiplier that is not 1, and `gather` therefore
    sets none at all — *"consumption arrives here already post-multiplier"*. So
    a thousandfold error on it is an error in nothing a customer is billed, and
    comparing it against the chain's REAL meter multiplier would report a
    disagreement on every meter that is not x1.

    On real rows this is `--sabotage R3b-tariff-mult`, and the table does not
    move. **That non-movement is now the correct result rather than the
    defect** — which is the one sentence a future reader most needs, because the
    previous lane's proof used exactly this mutation.
    """
    found = resolution_shadow.compare(
        _live(multiplier=Decimal("1000")),
        _Resolution(services=[_ServiceResolution(meter_multiplier=Decimal("1"))]),
    )
    assert found == [], [row.sentence() for row in found]


def test_R3b_catches_the_DEMAND_REGISTER_FAULT_the_PO_ratified():
    """**THE CASE THE PO RATIFIED, AND THE SHAPE R3b EXISTS TO CATCH.**

    PO ruling 2026-08-31, verbatim: *"this case is correct"* — **a demand
    register records the PEAK, billed per kW, and the ordinary
    *this-reading-minus-last-reading* formula has no meaning on it** (`DEF-797`).

    The worked figures put to the PO, on one commercial account: the current
    path bills **$154.00** and the corrected path bills **$4,532.00**, a
    **$4,378.00** undercharge. At the seeded Industrial demand rate of
    `$11.00/kW` those are `14 kW` and `412 kW` — the DIFFERENCE between two
    monthly peaks (412 − 398) against the PEAK itself.

    ⚠ **THIS IS THE SINGLE BEST ARGUMENT FOR THE R3b COMPARISON EXISTING.** The
    two paths produce different quantities from the same registers, both bills
    are structurally perfect, and until 2026-08-31 the shadow put no figure
    beside the other at this step — so a $4,378.00 disagreement would have been
    reported as *"R3b: 0 disagreements"* on every run.

    ⚠ **AND IT NEEDS NO RE-BILL, WHICH IS THE OTHER HALF OF THE SAME RULING:**
    *"product is not live yet so we dont have to re-bill anything - just correct
    the logic and we are good to go"*. The remedy is the logic; the question this
    row puts to the PO is one sentence — which of the two quantities is right —
    and it is already answered for this shape.
    """
    live_peak_difference = Decimal("14")  # 412 − 398, x $11.00/kW = $154.00
    ruled_peak = Decimal("412")  # the peak itself, x $11.00/kW = $4,532.00
    found = resolution_shadow.compare(
        _live(consumption=live_peak_difference),
        _Resolution(
            services=[_ServiceResolution(billable_quantity=ruled_peak)]
        ),
    )
    assert _steps(found) == ["R3b"]
    assert found[0].live == live_peak_difference
    assert found[0].chain == ruled_peak
    rate = Decimal("11.00")
    assert (ruled_peak - live_peak_difference) * rate == Decimal("4378.00")


def test_R3b_is_blind_to_a_multiplier_error_on_a_ZERO_register_difference():
    """THE LIMIT, ASSERTED RATHER THAN LEFT IN A DOCSTRING.

    The quantity comparison catches a multiplier error because the multiplier's
    whole effect is inside the quantity — but `0 x 10` and `0 x 1` are both `0`,
    so a meter that did not move hides one. A reader deciding whether R3b is
    ready to switch needs to know that this evidence has a hole in it, and a
    fact in a test is a fact; a fact in a comment is a note.
    """
    found = resolution_shadow.compare(
        _live(consumption=Decimal("0")),
        _Resolution(
            services=[
                _ServiceResolution(
                    billable_quantity=Decimal("0"), meter_multiplier=Decimal("10")
                )
            ]
        ),
    )
    assert found == [], "a zero register difference is expected to hide this"


# ══════════════════════════════════════════════════════════════════════════
# R5 · the jurisdiction factor on the money
# ══════════════════════════════════════════════════════════════════════════


def test_R5_a_jurisdiction_factor_difference_is_caught():
    """On real rows: `--sabotage R5` rewrote AC-2026-00001's live factor from 1
    to 2 and R5 moved from `47 / 0` to `46 agree / 1 disagree`. On an $8.00 base
    that factor is the difference between $8.00 and $16.00 (BR-RAT-102)."""
    found = resolution_shadow.compare(
        _live(jurisdiction_factor=Decimal("2")),
        _Resolution(services=[_ServiceResolution(money_factor=Decimal("1"))]),
    )
    assert _steps(found) == ["R5"]
    assert "jurisdiction factor" in found[0].note


# ══════════════════════════════════════════════════════════════════════════
# R6 · the granted discount set
# ══════════════════════════════════════════════════════════════════════════


def _discount(code="PAPERLESS", value="1.00"):
    return DiscountRule(
        code=code,
        name="Paperless billing",
        discount_type="fixed_amount",
        value=Decimal(value),
        currency="USD",
        applies_to="whole_bill",
    )


def test_R6_a_discount_the_chain_drops_is_caught():
    """`--sabotage R6` on real rows: a granted `SABOTAGE-DISCOUNT` the catalogue
    does not offer moved R6 from `47 / 0` to `46 agree / 1 disagree`.

    ⚠ This is the ONE direction R6 can ever find. `adapt` builds the chain's
    enrolments FROM the live path's own discount set, so the chain can DROP a
    code the catalogue does not offer (BR-RAT-110) and can never ADD one.
    """
    found = resolution_shadow.compare(
        _live(discounts=(_discount(),)),
        _Resolution(services=[_ServiceResolution()], discounts=()),
    )
    assert _steps(found) == ["R6"]


def test_R6_compares_the_VALUE_and_not_only_the_code():
    """Two paths that agree to apply the same programme at two different
    percentages agree about nothing that matters, and a code-set comparison
    would report that as parity."""
    found = resolution_shadow.compare(
        _live(discounts=(_discount(value="1.00"),)),
        _Resolution(
            services=[_ServiceResolution()], discounts=(("PAPERLESS", Decimal("2.00")),)
        ),
    )
    assert _steps(found) == ["R6"]


def test_R6_agrees_when_both_paths_grant_the_same_programme_at_the_same_value():
    found = resolution_shadow.compare(
        _live(discounts=(_discount(),)),
        _Resolution(
            services=[_ServiceResolution()], discounts=(("PAPERLESS", Decimal("1.00")),)
        ),
    )
    assert found == [], [row.sentence() for row in found]


# ══════════════════════════════════════════════════════════════════════════
# R7 · the tax rules that attach — the step that can be evaluated NO OTHER WAY
# ══════════════════════════════════════════════════════════════════════════


def test_R7_a_tax_the_chain_does_not_attach_is_caught():
    """⚠ **R7 PUBLISHES NO REFUSAL CLASS AND NEVER WILL** — a failed
    applicability condition means NO LINE rather than an error (`DEF-273`) — so
    this comparison is the only thing that can ever evaluate it. Before it
    existed R7 was invisible to the shadow end to end, and a step that can
    produce no finding of any kind cannot be switched on evidence.

    On the seeded tenant this is not a hypothetical: the measurement of
    2026-08-31 found the live path attaching `Texas State` on the two commercial
    accounts and the ruled path attaching only `Local`.
    """
    found = resolution_shadow.compare(
        _live(taxes=(TaxRule(code="Local"), TaxRule(code="Texas State"))),
        _Resolution(services=[_ServiceResolution()], taxes=(_CatalogueTax("Local"),)),
    )
    assert _steps(found) == ["R7"]
    assert "Texas State" in found[0].sentence()


def test_R7_a_tax_the_chain_attaches_and_the_live_path_does_not_is_also_caught():
    """The other direction — over-charging — which is the one that costs a
    refund, a support cycle and a trust problem rather than a re-bill."""
    found = resolution_shadow.compare(
        _live(taxes=(TaxRule(code="Local"),)),
        _Resolution(
            services=[_ServiceResolution()],
            taxes=(_CatalogueTax("Local"), _CatalogueTax("Texas State")),
        ),
    )
    assert _steps(found) == ["R7"]


def test_R7_agrees_when_the_same_authorities_attach_on_both_paths():
    found = resolution_shadow.compare(
        _live(taxes=(TaxRule(code="Texas State"), TaxRule(code="Local"))),
        _Resolution(
            services=[_ServiceResolution()],
            taxes=(_CatalogueTax("Local"), _CatalogueTax("Texas State")),
        ),
    )
    assert found == [], [row.sentence() for row in found]


# ══════════════════════════════════════════════════════════════════════════
# All four at once — a step's divergence never swallows another's
# ══════════════════════════════════════════════════════════════════════════


def test_four_broken_figures_produce_four_named_divergences():
    """`compare()` collects rather than short-circuits, so an account wrong at
    four steps reports four rows and a reader can act on each. A comparator that
    returned the first difference would make three of the eight steps
    unmeasurable on any account that also differs earlier."""
    found = resolution_shadow.compare(
        _live(
            consumption=Decimal("8000.000000"),
            jurisdiction_factor=Decimal("2"),
            discounts=(_discount(),),
            taxes=(TaxRule(code="Local"),),
        ),
        _Resolution(services=[_ServiceResolution()], discounts=(), taxes=()),
    )
    assert _steps(found) == ["R3b", "R5", "R6", "R7"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2798 · CR-052 task 20 · decision log 2026-08-31 (the R1–R7
#         per-step disagreement count)
# generated: 2026-08-31 by the DEF-2799/DEF-2798 lane (claude)
# gates: golden-verify 33 PASS / 0 FAIL before and after — nothing here reads,
#        asserts or moves a ❄️ FROZEN B4/B5 figure; `compare()` prices nothing.
# ──────────────────────────────────────────────────────────
