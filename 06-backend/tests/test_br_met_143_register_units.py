# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007/008 (S28 — a staged row becomes a committed read) ·
#           US-MET-012/013 (S25 / S29)   Screens: S25 · S28 · S29 · S31.3
# Rules:    BR-MET-143 (a reading's unit must match the unit of the thing that
#           PRICES it; a SCALE mismatch is reconciled by the meter's multiplier
#           and a DIMENSION mismatch never is) · BR-MET-051 (*"Demand: manual
#           demand-register value at cycle read"*) · BR-MET-019 (the delta rule
#           a maximum register is NOT subject to) · BR-RAT-014 (the demand
#           charge is per kW) · OQ-004's closure (*"no silent conversion"*) ·
#           CLAUDE.md hard rule 3
# CR:       the PO ruling of 2026-08-27 closing OQ-391 and DEF-797.
# ───────────────────────────────────────────────────────
"""**BR-MET-143 · DEF-797 — a demand reading carries kW, and its quantity is
the PEAK rather than the difference between two peaks.**

⛔ **THIS FILE IS ABOUT CUSTOMER-FACING MONEY THAT WAS WRONG IN THE PRODUCT.**
DEF-797, measured: peaks **398 → 412 kW** committed `consumption=14.000000`
stamped `unit=kWh`, and the Industrial schedule's `$11.00/kW` priced that as
**$154.00** where the correct charge is **412 × 11.00 = $4,532.00** — one
commercial account under-billed by **$4,378.00 in a single month**, with the
wrong unit printed on an issued document.

**THE DEFECT HAS TWO HALVES AND EACH GETS ITS OWN TEST**, because fixing the
unit alone would print a correct unit on a wrong number (the defect row says so
in as many words):

  · the **QUANTITY** — `_post_row` ran BR-MET-019's `(current − prior) ×
    multiplier` on EVERY channel, and a demand register is a MAXIMUM;
  · the **UNIT** — `_post_row` stamped `unit=asset.unit` on every channel, so
    a peak was stored in the meter's ENERGY unit.

The escape reason DEF-797 records is what the last two tests here close:
*"the tou_demand money triples take their demand quantity from a FROZEN dataset
rather than through the metering seam, so the golden tests prove the pricing and
never exercise the seam that feeds it."* So `test_..._the_billing_seam_hands_
rating_the_peak_in_kw` walks a real read all the way to the quantity billing
hands rating, and multiplies it by the schedule's own rate in the assertion.
❄️ **No golden fixture is touched — GT-20/GT-21 are untouched and unmoved.**
"""

from decimal import Decimal

import pytest

from apps.metering import models, register_units, selectors, services
from core import sample_fixture as fixture

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

HEADER = "meter_id,read_date,reading,channel,service,notes,demand_reset\n"

#: DEF-797's own measured case, verbatim from the register row.
PRIOR_PEAK = "398"
THIS_PEAK = "412"
INDUSTRIAL_DEMAND_RATE = Decimal("11.00")
CORRECT_CHARGE = Decimal("4532.00")
THE_WRONG_CHARGE = Decimal("154.00")


def csv(*rows: str) -> str:
    return HEADER + "".join(r if r.endswith("\n") else r + "\n" for r in rows)


def post(actor, content):
    batch = stage(actor, content)
    services.validate_read_batch(actor, batch["id"])
    accept_warnings(actor, batch["id"])
    services.commit_read_batch(actor, batch["id"], {"certified": True})
    return batch


# ══════════════════════════════════════════════════════════════════════
# THE PURE RULE (no database) — BR-MET-143
# ══════════════════════════════════════════════════════════════════════


def test_a_demand_register_carries_kw_and_the_energy_register_beside_it_carries_kwh():
    """OQ-391 option (a): the unit is per REGISTER, not per meter.

    RED (before this lane): AttributeError — `apps.metering.register_units`
    did not exist, and `_post_row` had one `unit=asset.unit` for every channel.
    """
    assert register_units.register_unit("kWh", "demand") == "kW"
    assert register_units.register_unit("kWh", "total") == "kWh"
    assert register_units.register_unit("kWh", "tou_on") == "kWh"
    assert register_units.register_unit("kWh", "export") == "kWh"


def test_an_undeclared_demand_unit_is_refused_and_never_defaulted_to_kw():
    """CLAUDE.md rule 3 has no assume branch and hard-won law 3 says the unsafe
    option is the one you type. A tenant metering in `kVAh` gets NO demand unit
    from this repo — the row is refused by `unit_missing` and a person rules.

    RED: `return "kW"` as a fallback would make this line pass a plausible unit
    onto an issued bill.
    """
    assert register_units.register_unit("kVAh", "demand") is None
    assert register_units.register_unit("kgal", "demand") is None
    assert register_units.demand_unit_for("therm") is None


def test_the_multiplier_reconciles_scale_and_is_refused_a_dimension():
    """**The general rule the PO gave with the demand ruling**, in four cases.

    PO verbatim: *"we have to match utility service unit and meter reading unit
    - if it does not match then we have intriduce multiplier factor on meter."*
    And the consequence the merge lane stated rather than resolved in silence:
    a multiplier is a SCALE factor and **kW → kWh is not a scale**.
    """
    same = register_units.reconciliation("kgal", "kgal")
    assert same.kind == register_units.MATCH and same.matches

    scale = register_units.reconciliation("ccf", "kgal")
    assert scale.kind == register_units.SCALE
    assert scale.multiplier_can_reconcile is True  # OQ-004's own ccf → kgal

    dimension = register_units.reconciliation("kW", "kWh")
    assert dimension.kind == register_units.DIMENSION
    assert dimension.multiplier_can_reconcile is False  # ⛔ power is not energy
    assert (dimension.reading_dimension, dimension.pricing_dimension) == ("power", "energy")

    unknown = register_units.reconciliation("kgal", "hogsheads")
    assert unknown.kind == register_units.UNKNOWN_DIMENSION
    assert unknown.multiplier_can_reconcile is False  # never guessed into SCALE


def test_no_configured_pricing_unit_is_a_match_and_not_a_refusal():
    """r6.4 made `billed_uom` an OPTION and nothing seeds it, so every tenant
    alive carries NULL. Reading that as a mismatch would refuse every estate."""
    assert register_units.reconciliation("kgal", None).kind == register_units.MATCH
    assert register_units.reconciliation("kgal", "").kind == register_units.MATCH


def test_a_maximum_register_bills_its_value_and_a_counter_bills_its_delta():
    """BR-MET-051 against BR-MET-019, as arithmetic. DEF-797's quantity half."""
    peak = register_units.billable_quantity(
        channel="demand",
        value=Decimal(THIS_PEAK),
        multiplier=Decimal("1"),
        delta_consumption=Decimal("14"),  # what the delta rule computed — ignored
    )
    assert peak == Decimal("412")
    total = register_units.billable_quantity(
        channel="total",
        value=Decimal("42864"),
        multiplier=Decimal("1"),
        delta_consumption=Decimal("820"),
    )
    assert total == Decimal("820")  # the delta rule still owns every counter


# ══════════════════════════════════════════════════════════════════════
# DEF-797, END TO END, THROUGH THE REAL POST PATH
# ══════════════════════════════════════════════════════════════════════


def test_def797_the_quantity_half__a_412_kw_peak_commits_as_412_not_as_14(brazos, marcus):
    """⛔ **DEF-797's QUANTITY half — the $4,378.00 one.**

    Two cycles of the same demand register, 398 then 412, exactly as the defect
    row measured them.

    RED (before this lane):
        assert Decimal('14.000000') == Decimal('412.000000')
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, uom="kWh")
        post(marcus, csv(f"M-7001,2026-07-03,{PRIOR_PEAK},demand,E,,"))
        post(marcus, csv(f"M-7001,2026-08-03,{THIS_PEAK},demand,E,,yes"))
        head = (
            models.MeterRead.objects.filter(channel="demand", superseded_at__isnull=True)
            .order_by("-read_at")
            .first()
        )
        served = selectors.read_dict(head)

    assert head.consumption == Decimal("412.000000")  # the PEAK, not 412 − 398
    assert head.prior_value == Decimal("398.000000")  # the prior is still recorded
    assert head.current_value == Decimal("412.000000")
    # And the money that follows from it, worked in the assertion rather than
    # asserted as a constant somebody could copy from the defect row:
    assert head.consumption * INDUSTRIAL_DEMAND_RATE == CORRECT_CHARGE
    assert Decimal("14") * INDUSTRIAL_DEMAND_RATE == THE_WRONG_CHARGE  # what it billed
    assert served["usage_display"] == "412 kW"


def test_a_ct_ratio_scales_the_peak__kw_to_kw_is_a_SCALE_and_the_multiplier_applies(brazos, marcus):
    """**BR-MET-143's multiplier, on a MAXIMUM register** — and the case that
    makes every other peak assertion in this file able to tell pass from fail.

    ⚠ On DEF-797's own numbers the meter multiplier is 1, so the raw register
    and the billed peak are the SAME number: a surface that rendered the wrong
    one of the two would pass every assertion pointed at it (proved by sabotage
    — reverting `UsageCell` to `current_value` left all eleven of its cases
    green). A CT ratio separates them, and it is a REAL case rather than a
    contrived one: a current transformer on a demand register scales **kW to
    kW** — the same dimension — which is precisely the mismatch the PO's ruling
    says the meter's multiplier is for.

    The dial reads **412**, the meter multiplies by **2**, the customer owes on
    **824 kW** — `824 × $11.00 = $9,064.00`.

    RED (before this lane): the delta rule ignored the value entirely and
    returned `(412 − 398) × 2 = 28`.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, uom="kWh", multiplier="2")
        post(marcus, csv(f"M-7001,2026-07-03,{PRIOR_PEAK},demand,E,,"))
        post(marcus, csv(f"M-7001,2026-08-03,{THIS_PEAK},demand,E,,yes"))
        head = (
            models.MeterRead.objects.filter(channel="demand", superseded_at__isnull=True)
            .order_by("-read_at")
            .first()
        )

    assert head.current_value == Decimal("412.000000")  # the RAW dial, unchanged
    assert head.multiplier == Decimal("2.000000")  # the factor USED, stored (BR-MET-056)
    assert head.consumption == Decimal("824.000000")  # the BILLED peak
    assert head.unit == "kW"
    assert head.consumption * INDUSTRIAL_DEMAND_RATE == Decimal("9064.00")
    # ⚠ and NOT the delta the old rule computed, which the multiplier also
    # scaled: (412 − 398) × 2 = 28, billing $308.00 on a $9,064.00 obligation.
    assert head.consumption != Decimal("28.000000")


def test_def797_the_unit_half__the_peak_is_stamped_kw_and_the_energy_row_kwh(brazos, marcus):
    """⛔ **DEF-797's UNIT half**, on ONE meter holding both registers — which
    is the whole of OQ-391 option (a).

    RED (before this lane):
        assert 'kWh' == 'kW'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, uom="kWh")
        post(
            marcus,
            csv(
                "M-7001,2026-08-03,42864,total,E,,",
                f"M-7001,2026-08-03,{THIS_PEAK},demand,E,,yes",
            ),
        )
        served = {r.channel: selectors.read_dict(r) for r in models.MeterRead.objects.all()}

    assert served["demand"]["unit"] == "kW"
    assert served["total"]["unit"] == "kWh"
    # hard rule 3: neither quantity is ever served without its own unit, and the
    # two units are DIFFERENT on the same meter — that is the fix in one line.
    assert served["demand"]["unit"] != served["total"]["unit"]
    assert served["demand"]["is_peak"] is True


def test_the_billing_seam_hands_rating_the_peak_in_kw(brazos, marcus):
    """**DEF-797's ESCAPE REASON, closed.** The register records it verbatim:
    *"the tou_demand money triples take their demand quantity from a FROZEN
    dataset rather than through the metering seam, so the golden tests prove the
    pricing and never exercise the seam that feeds it."*

    This walks the seam. `billing_reads_for_unit` is what `apps/billing/runs.
    _demand_quantity` reads, so the pair asserted here IS what rating prices.

    RED (before this lane):
        assert (Decimal('14.000000'), 'kWh') == (Decimal('412.000000'), 'kW')
    """
    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, uom="kWh")
        unit_id = meter["assigned_unit_id"]
        post(
            marcus,
            csv(
                "M-7001,2026-07-03,42044,total,E,,",
                f"M-7001,2026-07-03,{PRIOR_PEAK},demand,E,,",
            ),
        )
        post(
            marcus,
            csv(
                "M-7001,2026-08-03,42864,total,E,,",
                f"M-7001,2026-08-03,{THIS_PEAK},demand,E,,yes",
            ),
        )
        rows = selectors.billing_reads_for_unit(
            unit_id, period_start="2026-08-01", period_end="2026-08-31"
        )

    electric = next(r for r in rows if r["service_code"] == "electric")
    demand = electric["demand"]
    assert (demand["consumption"], demand["unit"]) == (Decimal("412.000000"), "kW")
    # BR-RAT-014 prices exactly this, per kW. The $4,532.00 the customer owes.
    assert demand["consumption"] * INDUSTRIAL_DEMAND_RATE == CORRECT_CHARGE
    # ⚠ AND THE ENERGY REGISTER IS UNMOVED — a peak fix that changed the kWh
    # figure beside it would be a second defect wearing the first one's fix.
    assert (electric["consumption"], electric["unit"]) == (Decimal("820.000000"), "kWh")


def test_a_correction_to_a_demand_read_stays_in_kw(brazos, marcus):
    """Hard rule 4: a correction is a NEW ROW (BR-MET-024/053). `_supersede_row`
    stamped `unit=asset.unit` too, so a corrected peak landed back in kWh —
    DEF-797's label re-created on the replacement head.

    RED (before this lane):
        assert 'kWh' == 'kW'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, uom="kWh")
        post(marcus, csv(f"M-7001,2026-08-03,{THIS_PEAK},demand,E,,yes"))
        original = models.MeterRead.objects.get(channel="demand")
        services.supersede_read(
            marcus,
            str(original.id),
            {"value": "455", "reason": "route sheet re-read"},
        )
        head = models.MeterRead.objects.get(channel="demand", superseded_at__isnull=True)

    assert head.unit == "kW"
    assert head.consumption == Decimal("455.000000")  # the new PEAK, not a delta


# ══════════════════════════════════════════════════════════════════════
# PART 3 — THE SEEDED MULTIPLIER (PO: "you will ahve to seed that data")
# ══════════════════════════════════════════════════════════════════════


def _reconcile(a, b):
    return register_units.reconciliation(a, b).as_dict()


def test_the_seeded_meter_carries_a_multiplier_of_one_when_the_units_match():
    """**×1 is not a placeholder here — it IS the reconciliation.** A tenant
    whose register reads kgal and whose service is billed in kgal needs no
    factor, and the fixture now SAYS that instead of hardcoding a literal.

    ⚠ This is also the regression guard for CR-039 wave A: a water tenant gets
    byte-for-byte the estate it had before BR-MET-143.
    """
    plan = fixture.estate_plan({"water", "sewer", "trash"}, {"water": "kgal"})
    ((code, uom, multiplier),) = [(m.code, m.uom, m.multiplier) for m in plan.metered]
    assert (code, uom, multiplier) == ("water", "kgal", "1")
    # `DEF-MET-9055` — one meter per estate unit plus the case-3 swap. The
    # estate is 50 units since CR-062 J2-J4 (`d5b6fecc2`), so the literal 49
    # this read became 51; the count is the estate's, the subject is the "1".
    rows = fixture.meter_plan("water", "kgal", multiplier)
    assert len(rows) == len(fixture.units_flat()) + 1
    assert [row["multiplier"] for row in rows] == ["1"] * len(rows)

    configured = fixture.estate_plan(
        {"water"},
        {"water": "kgal"},
        {"water": {"billed_uom": "kgal", "conversion_factor": None}},
        _reconcile,
    )
    assert configured.primary is not None
    assert configured.primary.multiplier == "1" and configured.refused == ()

    # ── CR-062 C1 · A FACTOR PER METERED SERVICE, WHICH IS WHAT THE RULE
    # ALWAYS SAID (BR-MET-143 as amended 2026-09-02) ────────────────────────
    # The factor reconciles ONE service's register with the unit THAT service is
    # billed in, so a single factor for the whole estate was a category error —
    # it simply could not be seen while the estate held one register. Here the
    # water register matches and the electric one is scaled, on one tenant, at
    # the same time.
    # ⚠ The pair is `ccf` → `kgal` because it is one metering CLASSIFIES as a
    # scale (`register_units.reconciliation` answers `dimension` for kWh → kW
    # and `unknown_dimension` for kWh → MWh, which this product has not been
    # told about). The point of the case is TWO SERVICES WITH TWO FACTORS, so
    # the pair has to be one a factor can actually reconcile.
    two = fixture.estate_plan(
        {"water", "electric"},
        {"water": "ccf", "electric": "kWh"},
        {"water": {"billed_uom": "kgal", "conversion_factor": "0.748052"}},
        _reconcile,
    )
    assert [(m.code, m.uom, m.multiplier) for m in two.metered] == [
        ("water", "ccf", "0.748052"),
        ("electric", "kWh", "1"),
    ]
    assert two.refused == ()


def test_a_scale_mismatch_seeds_the_tenants_own_conversion_factor():
    """BR-MET-143's seeded case: a `ccf` register billed in `kgal`. The factor
    is the TENANT's own `tenant_services.conversion_factor` read back, never a
    physical constant this repo typed — OQ-004's *"convert at rating input"*
    puts the number in configuration and nowhere else.
    """
    plan = fixture.estate_plan(
        {"water"},
        {"water": "ccf"},
        {"water": {"billed_uom": "kgal", "conversion_factor": "0.748052"}},
        _reconcile,
    )
    ((code, uom, multiplier),) = [(m.code, m.uom, m.multiplier) for m in plan.metered]
    assert (code, uom, multiplier) == ("water", "ccf", "0.748052")
    assert plan.refused == ()
    assert fixture.meter_plan("water", "ccf", multiplier)[0]["multiplier"] == "0.748052"


def test_a_scale_mismatch_with_no_configured_factor_seeds_nothing_and_says_why():
    """⚠ **A SEEDED VALUE NOBODY CHOSE IS WORSE THAN A BLANK.** OQ-004's
    closure is *"no silent conversion"*, so a 0.748052 typed into the fixture to
    make ccf → kgal come out would ride into every demo bill looking official.

    The estate is REFUSED with a sentence a person can act on, exactly as
    DEF-795's `_NO_DEFAULT_UOM` refusal is.
    """
    plan = fixture.estate_plan(
        {"water"},
        {"water": "ccf"},
        {"water": {"billed_uom": "kgal", "conversion_factor": None}},
        _reconcile,
    )
    assert plan.metered == () and plan.primary is None
    ((code, sentence),) = plan.refused
    assert code == "water"
    assert "no silent conversion" in sentence
    assert "ccf" in sentence and "kgal" in sentence  # both units NAMED

    # ── CR-062 C1 · THE REFUSAL IS THIS SERVICE'S AND NOT THE ESTATE'S ──────
    # A tenant selling water AND electric, whose WATER pair cannot be
    # reconciled, keeps its electric meters and loses only water — by name.
    # Before this change the first metered service decided the whole estate, so
    # one unreconcilable pair took every other service down with it.
    mixed = fixture.estate_plan(
        {"water", "electric"},
        {"water": "ccf", "electric": "kWh"},
        {"water": {"billed_uom": "kgal", "conversion_factor": None}},
        _reconcile,
    )
    assert mixed.metered_codes == ("electric",)
    assert [c for c, _why in mixed.refused] == ["water"]


def test_a_dimension_mismatch_is_refused_because_no_multiplier_can_close_it():
    """The consequence the merge lane stated rather than resolved in silence: a
    register in kWh billed per kW is not a scaling problem, and inventing a
    factor for it would put a fabricated number on every meter."""
    plan = fixture.estate_plan(
        {"electric"},
        {"electric": "kWh"},
        {"electric": {"billed_uom": "kW", "conversion_factor": "40"}},
        _reconcile,
    )
    assert plan.metered == () and plan.primary is None
    ((_code, sentence),) = plan.refused
    assert "DIFFERENT PHYSICAL QUANTITIES" in sentence
    assert "energy against power" in sentence


def test_with_no_classifier_a_mismatch_refuses_rather_than_assuming_scale():
    """Hard-won law 3 — defaults fail closed. `core/` holds no business rule, so
    called without metering's classifier the fixture will not decide that two
    unequal unit strings are the same quantity."""
    plan = fixture.estate_plan(
        {"water"},
        {"water": "ccf"},
        {"water": {"billed_uom": "kgal", "conversion_factor": "0.748052"}},
        None,  # no classifier supplied
    )
    assert plan.metered == ()
    assert "has not been told what kind of quantity" in plan.refused[0][1]
