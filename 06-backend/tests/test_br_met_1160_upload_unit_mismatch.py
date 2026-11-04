# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-008 (the same rules run over STAGED rows — S28 steps 3–4) ·
#           US-MET-011 (the config-driven validation catalogue)
#           Screens: S28 (the import wizard, where a clerk stands) · S25
# Rules:    BR-MET-1160 (**the rule this file proves** — a reading's unit must
#           be the unit the tariff prices in, checked WHEN THE READING IS
#           UPLOADED) · BR-MET-143 (scale is reconcilable, dimension never is;
#           ONE implementation) · BR-MET-022 (self-describing outcomes) ·
#           BR-MET-052 (nothing auto-fixed) · BR-MET-020 (no hardcoded
#           threshold) · BR-MET-136 (judgment rules are switchable) ·
#           BR-RAT-038 (the engine's own gate, which still stands) ·
#           US-RAT-005 TC-7 (a SCALE mismatch warns — ratified, NOT moved) ·
#           CLAUDE.md hard rule 3
# Rulings:  PO 2026-09-02, verbatim: *"refula at the time of billing - it will
#           be too late to act , we have to ensure wehn we upload reading at
#           that time it is check and corrected"* · PO 2026-09-02 (the
#           schedule/meter invariant) · PO 2026-08-27 (BR-MET-143)
# Golden:   none moves. This file states no rate and no amount; it decides
#           whether a quantity may be priced at all. ❄️ B4/B5 untouched.
# Impacts:  apps/metering/validation.py (RULE_UNIT_MISMATCH) ·
#           apps/metering/completeness.py (pricing_unit_for_asset) ·
#           apps/metering/services.py (_build_context resolves it)
# ───────────────────────────────────────────────────────
"""**THE UNIT MISMATCH, CAUGHT WHERE A PERSON CAN FIX IT.**

WHAT WAS RED BEFORE THIS RULE, VERBATIM
----------------------------------------
A gas tenant whose register reads `therm`, on a unit whose plan prices gas at
the signed `$1.15/ccf` — the shipped fixture's own shape. A batch of one
reading was uploaded and validated, and the product said nothing at all::

    SEVERITY: warning
    OUTCOMES: [('negative_usage', 'ok'), ('days_threshold', 'not_evaluated'),
               ('out_of_window', 'not_evaluated'), ('vacant_unit', 'warning'),
               ('cycle_membership', 'not_evaluated'), ('factor_flag',
               'not_evaluated'), ('write_mode', 'ok'), ('plan_registers', 'ok')]

    E   AssertionError: no unit_mismatch outcome stored on the row — a therm
        reading was accepted against a ccf tariff with nothing said at upload
    E   assert None is not None

Read `plan_registers: ok` again: **the plan hop resolved**, so the product had
the ccf tariff in its hand at that moment and compared nothing. The one warning
on the row is `vacant_unit`, about the account and not the unit of measure — so
a clerk pressing *Accept all warnings* posted a therm reading against a ccf
tariff, on the screen the PO's ruling names.

THE MONEY, WORKED
------------------
One therm of pipeline gas is about `0.9643 ccf`. A `42`-unit gas read priced at
`$1.15/ccf` bills **`$48.30`** where the honest figure is about **`$46.58`** —
roughly **4% over, `$1.72` a month on one meter**, on a bill that foots.

THE THREE POINTS, AND WHY THIS ONE
-----------------------------------
The invariant is now checked at three places and none of them replaces another:

  * **SAVE** — `rating.selectors.uom_gate` warns the wizard when a tariff is
    typed (`DEF-3108`, fixed 2026-09-02).
  * **UPLOAD** — this rule. The PO's ruling: *"we have to ensure wehn we upload
    reading at that time it is check and corrected"*.
  * **BILL** — `rating.pricing.stages.normalize._gate_uom` (`BR-RAT-038`), the
    backstop, because a reading can predate a tariff change. **It is not
    softened by this file and tc7 pins it.**
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.metering import models, services, validation

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    csv_body,
    make_plan,
    make_premises,
    make_unit,
    seed_config,
    seed_service_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── fixture plumbing ────────────────────────────────────────────────────────


def register_reads(actor, service_code, uom_code, alt=None):
    """Give the tenant's service a REGISTER unit, and no `billed_uom` — which
    is every tenant this product has ever provisioned (`DEF-3108`: nothing
    seeds that column).

    ⚠ `alt` IS NOT DECORATION. `BR-TEN-027`'s `alt_equals_primary` refuses a
    service whose two units are the same string, so moving a service onto its
    own alternate has to move the old primary into the alternate slot in the
    SAME call.

    ⚠ **AND `alt_uom` IS NOW SENT ON EVERY CALL, DEFAULTING TO `None` — WHICH
    CLEARS THE ALTERNATE (`DEF-RAT-4516`, 2026-09-07; the identical repair
    `DEF-3201` made to `test_schedule_meter_unit_invariant._register_reads` on
    2026-09-02).** It used to be OMITTED when the caller passed nothing, and
    `update_tenant_service` reads an omitted key as *"keep what is on file"* —
    so the helper silently inherited whatever the SEED had put in the alternate
    slot. That was harmless only while gas was seeded `primary=therm,
    alt=ccf`. `BR-TEN-1180`/`DEF-3230` swapped it to `primary=ccf, alt=therm`
    the same day, and the three `register_reads(dana, "gas", "therm")` calls in
    this file then collided with the `therm` left behind in the alternate slot
    and died on `VAL-002 settings.services.alt_equals_primary` **before
    reaching the unit-gate assertion each was written for**. The file reported
    three failures that named neither the gate nor the seed, and they stayed
    red for five days among other reds (hard-won law 7's proved-red-then-never-
    read shape). Sending the key explicitly makes the helper say what it means:
    *this service reads THIS unit, and nothing else is claimed*.
    """
    from apps.tenancy import services as tenancy_services

    changes = {"enabled": True, "primary_uom": uom_code, "alt_uom": alt}
    tenancy_services.update_tenant_service(actor, service_code, changes)


def plan_priced_in(tenant, *, service_code, uom, name="Gas Residential", model="flat"):
    """A published plan whose <service> schedule carries an ACTIVATED version
    priced in `uom`.

    `make_plan` stops at the plan + tariff + link (no version), which is why
    every pre-existing fixture in this repo resolves to `no_version_in_force`
    and this rule stays out of their way — tc6 pins that.
    """
    from apps.rating import models as rating_models

    plan = make_plan(tenant, name=name, services=(service_code,))
    schedule_row = rating_models.PlanRateSchedule.objects.get(
        tenant=tenant, rate_plan=plan, service__code=service_code
    )
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=schedule_row.tariff,
        model=model,
        uom=uom,
        effective_from=date(2026, 1, 1),
    )
    if model == "demand":
        rating_models.DemandRateConfig.objects.create(
            tenant=tenant,
            tariff_version=version,
            energy_rate_per_kwh=Decimal("0.09"),
            demand_rate_per_kw=Decimal("14.50"),
        )
    return plan


def planned_meter(actor, plan, *, asset_no, service, uom, label="Unit 3F"):
    """A meter on a unit that HOLDS the plan (`unit.rate_plan_id`,
    BR-CUS-014) — the chain BR-MET-1160 walks to find what prices this read."""
    premises = make_premises(
        actor, address_line=f"1408 Bluestem Ln {asset_no}", services_available=[service]
    )
    unit = make_unit(actor, premises["id"], label=label, services=[service])
    if plan is not None:
        services.assign_unit_plan(
            actor,
            unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2026-06-01", "reason": "fixture"},
        )
    return a_meter(actor, asset_no, unit_id=unit["id"], service=service, uom=uom)


def outcome_named(row, rule):
    return next((o for o in (row.rule_outcomes or []) if o.get("rule") == rule), None)


def validated_row(actor, body, row_no=1, **tags):
    batch = stage(actor, csv_body(body), **tags)
    services.validate_read_batch(actor, batch["id"])
    return batch, models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=row_no)


# ── tc1 · the guard, proved RED first ───────────────────────────────────────


def test_tc1__a_therm_read_against_a_ccf_tariff_is_refused_at_upload(brazos, dana):
    """The PO's own case. `therm` is declared ENERGY and `ccf` VOLUME, so no
    multiplier and no conversion factor reconciles them — the conversion needs
    a heating value, a physical fact about the gas and not a column — and the
    row is an ERROR rather than a warning.

    RED FIRST: the module docstring quotes the pre-change outcome list verbatim.
    """
    with tenant_ctx(brazos):
        seed_config()
        register_reads(dana, "gas", "therm")
        plan = plan_priced_in(brazos, service_code="gas", uom="ccf")
        planned_meter(dana, plan, asset_no="M-9101", service="gas", uom="therm")

        _batch, row = validated_row(dana, "M-9101,2026-08-03,42,total")

        outcome = outcome_named(row, "unit_mismatch")
        assert outcome is not None, "BR-MET-1160 is not evaluated at upload"
        assert outcome["severity"] == validation.ERROR
        assert row.severity == validation.ERROR
        detail = outcome["detail"]
        # BR-MET-022/056 — the outcome says what it SAW, not merely that it fired.
        assert detail["read_uom"] == "therm"
        assert detail["pricing_uom"] == "ccf"
        assert detail["reconciliation"]["kind"] == "dimension"
        assert detail["reconciliation"]["multiplier_can_reconcile"] is False
        assert detail["summary"] == "reading is in therm, the rate schedule prices per ccf"
        # Both screens are named because we cannot know WHICH side has the typo.
        assert detail["resolutions"] == ["fix_schedule_uom", "set_asset_uom", "reject"]


# ── tc2 · what the refusal DOES, on the screen the ruling is about ──────────


def test_tc2__the_row_is_held_and_the_rest_of_the_file_still_posts(brazos, dana):
    """BR-MET-940: an error HOLDS its own row and refuses nothing else. So the
    mismatched gas meter waits for a person and the electric meter beside it
    bills — which is the whole difference from catching this at 2am, where the
    RUN stops and nobody is there to answer it.

    ⚠ A held row cannot be waved through: `set_row_disposition` refuses a plain
    `accept` on an ERROR by name (`metering.read_row.error_needs_resolution`),
    and `_unresolved_errors` resolves an error only by override / reject /
    field visit / skip — so *"nothing is auto-fixed"* (BR-MET-052) holds on the
    screen as well as in the engine.
    """
    from core import errors as core_errors

    with tenant_ctx(brazos):
        seed_config()
        register_reads(dana, "gas", "therm")
        gas_plan = plan_priced_in(brazos, service_code="gas", uom="ccf")
        planned_meter(dana, gas_plan, asset_no="M-9101", service="gas", uom="therm")
        electric_plan = plan_priced_in(
            brazos, service_code="electric", uom="kWh", name="Electric Residential"
        )
        planned_meter(
            dana, electric_plan, asset_no="M-7451", service="electric", uom="kWh", label="Unit 1A"
        )

        batch = stage(
            dana,
            csv_body("M-9101,2026-08-03,42,total", "M-7451,2026-08-03,1200,total"),
        )
        services.validate_read_batch(dana, batch["id"])

        with pytest.raises(core_errors.ValidationError) as excinfo:
            services.set_row_disposition(
                dana, batch["id"], 1, {"disposition": "accept", "reason": "looks fine to me"}
            )
        assert "error_needs_resolution" in str(excinfo.value.field_errors)

        accept_warnings(dana, batch["id"], reason="vacant unit confirmed on route sheet")
        result = services.commit_read_batch(dana, batch["id"], {"certified": True})

        assert result["counts"]["posted"] == 1  # the electric meter
        assert result["held_reads"] == 1  # the gas meter, waiting for a person
        assert result["unresolved_errors"] == 1


# ── tc3 · US-RAT-005 TC-7's ratified posture, UNMOVED ───────────────────────


def test_tc3__a_scale_mismatch_warns_and_stays_postable_with_a_reason(brazos, dana):
    """`kgal` against `ccf` is the SAME kind of quantity, so a multiplier can
    close it and `US-RAT-005 TC-7` is signed *"warn now, rating blocked
    later"*. Reversing a signed test case is a finance/PO re-sign
    (HUMAN-GUIDE §6), never a lane's change in passing — so this asserts the
    posture did NOT move when the dimension case became an error."""
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_priced_in(brazos, service_code="water", uom="ccf", name="Water Commercial")
        planned_meter(dana, plan, asset_no="W-3300", service="water", uom="kgal")

        _batch, row = validated_row(dana, "W-3300,2026-08-03,915,total")

        outcome = outcome_named(row, "unit_mismatch")
        assert outcome["severity"] == validation.WARNING
        assert outcome["detail"]["reconciliation"]["kind"] == "scale"
        assert outcome["detail"]["reconciliation"]["multiplier_can_reconcile"] is True
        assert row.severity == validation.WARNING


# ── tc4 · agreement is silent about everything except agreeing ─────────────


def test_tc4__a_matching_unit_passes_and_says_what_it_compared(brazos, dana):
    """The gas case as it SHOULD be configured: a `ccf` register priced per
    `ccf`, so the signed `$1.15/ccf` applies as signed. The outcome is still
    stored — `ok` and not absent — because a rule that produces no outcome is
    indistinguishable from a rule that never ran."""
    with tenant_ctx(brazos):
        seed_config()
        register_reads(dana, "gas", "ccf", alt="therm")
        plan = plan_priced_in(brazos, service_code="gas", uom="ccf")
        planned_meter(dana, plan, asset_no="M-9102", service="gas", uom="ccf")

        _batch, row = validated_row(dana, "M-9102,2026-08-03,42,total")

        outcome = outcome_named(row, "unit_mismatch")
        assert outcome["severity"] == validation.OK
        assert outcome["detail"]["read_uom"] == "ccf"
        assert outcome["detail"]["pricing_uom"] == "ccf"
        assert "resolutions" not in outcome["detail"]


# ── tc5 · the DEMAND register, which must NOT be gated ─────────────────────


def test_tc5__a_demand_peak_is_not_judged_against_the_energy_schedule(brazos, dana):
    """**The regression this rule could most easily have caused.** A demand
    register carries `kW` (`BR-MET-143` / `OQ-391`) and the schedule beside it
    is priced in `kWh`; the peak is priced by `demand_rate_per_kw` and by
    nothing this rule can see. `normalize._peak_demand` states the same thing
    in the engine — *"gating it against the ENERGY's unit would refuse every
    demand bill there is"* — so the rule REPORTS the skip with its reason
    rather than flagging every demand read in the product.
    """
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_priced_in(
            brazos, service_code="electric", uom="kWh", name="Electric Demand", model="demand"
        )
        planned_meter(dana, plan, asset_no="M-7460", service="electric", uom="kWh")

        _batch, row = validated_row(dana, "M-7460,2026-08-03,412,demand")

        outcome = outcome_named(row, "unit_mismatch")
        assert outcome["severity"] == validation.NOT_EVALUATED
        assert outcome["detail"]["reason"] == "maximum_register_not_priced_by_schedule_uom"
        assert outcome["detail"]["read_uom"] == "kW"
        assert row.severity != validation.ERROR


# ── tc6 · a gap is a gap and is never read as agreement ────────────────────


def test_tc6__an_unresolvable_pricing_unit_reports_by_name(brazos, dana):
    """DEF-075's lesson on a money path: *"we could not find out"* and *"the
    units agree"* are opposite facts. A unit with no plan, and a plan whose
    schedule has no version in force on the read's date, each report their own
    reason and neither is `ok`.

    This is also why the rule does not disturb the hundreds of existing
    fixtures in this repo: `make_plan` creates no version, so they resolve to
    `no_version_in_force`.
    """
    with tenant_ctx(brazos):
        seed_config()
        planned_meter(dana, None, asset_no="M-7452", service="electric", uom="kWh")
        _batch, row = validated_row(dana, "M-7452,2026-08-03,1200,total")
        assert outcome_named(row, "unit_mismatch")["severity"] == validation.NOT_EVALUATED
        assert outcome_named(row, "unit_mismatch")["detail"]["reason"] == "no_plan"

        undated = make_plan(brazos, name="Undated Electric", services=("electric",))
        planned_meter(
            dana, undated, asset_no="M-7453", service="electric", uom="kWh", label="Unit 2B"
        )
        _batch2, row2 = validated_row(dana, "M-7453,2026-08-03,1200,total")
        assert outcome_named(row2, "unit_mismatch")["detail"]["reason"] == "no_version_in_force"


# ── tc7 · the two neighbours this rule does NOT replace ────────────────────


def test_tc7__the_pricing_unit_is_the_same_string_the_engine_refuses_against(brazos, dana):
    """`BR-MET-1160` compares against `TariffVersion.uom`, which rating
    publishes as `pricing_inputs(...)["billed_unit"]` and which
    `normalize._gate_uom` refuses the bill against. **Same string, one source**
    — so a read this rule passes is a read the 2am run will price, and the two
    checks cannot drift apart.

    ⚠ It is NOT `tenant_services.billed_uom`. That column is NULL on every
    tenant this product has ever provisioned and a rule reading it would be
    blind everywhere, which is `DEF-3108` exactly. This case proves the column
    IS null while the rule still fires.
    """
    from apps.metering import completeness
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        seed_config()
        register_reads(dana, "gas", "therm")
        plan = plan_priced_in(brazos, service_code="gas", uom="ccf")
        asset = planned_meter(dana, plan, asset_no="M-9103", service="gas", uom="therm")

        gate = rating_selectors.uom_gate_for("gas", "ccf")
        assert gate["billed_uom"] is None  # the always-NULL column, unchanged

        meter = services.seams.meter_by_id(asset["id"])
        resolver = completeness.PlanRegisterResolver()
        pricing = resolver.pricing_unit_for_asset(meter, service_date=date(2026, 8, 3))
        assert pricing.unit == "ccf"
        assert pricing.absent_reason is None


def test_tc8__the_engine_still_refuses_the_same_pair_at_bill_time():
    """`BR-RAT-038` is the backstop and stays: a reading can predate a tariff
    change, so the run must still refuse a pair nobody caught at upload. This
    case exists so that softening the engine goes red HERE too."""
    from types import SimpleNamespace

    from apps.rating.pricing import errors as pricing_errors
    from apps.rating.pricing.stages import normalize as normalize_stage

    tariff = SimpleNamespace(
        service="gas",
        model="flat",
        billed_unit="ccf",
        base_charge=None,
        unit_price=Decimal("1.15"),
        tiers=(),
        multiplier=Decimal("1"),
    )
    with pytest.raises(pricing_errors.UomMismatch) as excinfo:
        normalize_stage.normalize(
            tariff=tariff,
            consumption=SimpleNamespace(amount=Decimal("42"), unit="therm"),
            period=SimpleNamespace(cycle_days=30, service_days=30),
            account=SimpleNamespace(tax_exempt=False),
        )
    assert "'therm' is not the billed unit 'ccf'" in str(excinfo.value)


# ── tc9 · the scale/dimension verdict has ONE implementation ───────────────


def test_tc9__the_verdict_is_br_met_143s_and_is_not_re_decided_here():
    """Two answers to *"is this scale or dimension"* is how a meter gets
    planted at ×1 on a pair no factor can reconcile. The rule reads
    `register_units.reconciliation` and rating reads the same function through
    its own seam."""
    from apps.metering import register_units
    from apps.rating import seams as rating_seams

    assert register_units.reconciliation("therm", "ccf").kind == register_units.DIMENSION
    assert register_units.reconciliation("kgal", "ccf").kind == register_units.SCALE
    assert rating_seams.unit_reconciliation("therm", "ccf")["kind"] == register_units.DIMENSION


# ── tc10 · BR-MET-136 — switchable, and it STATES itself when off ──────────


def test_tc10__a_tenant_that_switches_it_off_is_told_so_on_the_row(brazos, dana):
    """`BR-MET-136` defines the locked set by NAME (seven integrity rules) and
    everything else by subtraction, so this rule is switchable and the ruling
    is followed literally rather than amended here (`OQ-1330` raises the gap).

    It fails safe when a tenant switches it off — the engine still refuses the
    bill by name — and the row says `disabled` rather than falling silent,
    because a rule that produces no outcome is indistinguishable from one that
    passed.
    """
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", rule_enabled={"unit_mismatch": False})
        # DEF-3106's own fixture shape: an ELECTRIC schedule priced per kgal.
        plan = plan_priced_in(
            brazos, service_code="electric", uom="kgal", name="Electric priced per kgal"
        )
        planned_meter(dana, plan, asset_no="M-7454", service="electric", uom="kWh")

        _batch, row = validated_row(dana, "M-7454,2026-08-03,1200,total")

        outcome = outcome_named(row, "unit_mismatch")
        assert outcome["severity"] == validation.DISABLED
        assert row.severity != validation.ERROR
