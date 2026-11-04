# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-005 (the New Rate wizard — this is where the unit is typed)
#           Screens: S11 (the wizard's Basics step, where `uom` is chosen)
# Rules:    BR-RAT-038 (the UoM gate: the read unit must BE the billed unit; no
#           silent conversion) · BR-MET-143 (a reading's unit must match the
#           unit of the thing that PRICES it; SCALE is reconcilable, DIMENSION
#           never is) · B2 r6.4 (`tenant_services.billed_uom` +
#           `conversion_factor`, register→billed; mismatch without a factor
#           blocks rating) · CLAUDE.md hard rule 3
# Rulings:  PO 2026-09-02, verbatim: *"for Gas unit on rate schedule and unit on
#           meter read should match otherwise it is a problem ; same principle
#           is applied to all meter services and hence we have unit and
#           multiplier factor"* · PO 2026-08-27 (BR-MET-143, the reading side)
# Golden:   none moves. This file states no rate and no amount; it decides
#           whether a price may be applied at all. ❄️ B4/B5 untouched.
# Impacts:  apps/rating/selectors.uom_gate / uom_gate_for 🔒 ·
#           apps/rating/services._schedule_notices (the wizard's warning) ·
#           apps/rating/seams.unit_reconciliation_kinds
# ───────────────────────────────────────────────────────
"""**THE RATE SCHEDULE'S UNIT AGAINST THE METER'S — the PO ruling of 2026-09-02.**

WHAT WAS RED BEFORE THE FIX, VERBATIM
--------------------------------------
A gas tenant whose register reads `therm`, with a rate schedule priced in `ccf`
— the shipped fixture's own shape, and the `$1.15/ccf` the billing workbook
signs. Asked whether that was all right, the product said yes::

    NOTICES: []
    GATE: {'satisfied': True, 'reason': 'unconfigured', 'schedule_uom': 'ccf',
           'billed_uom': None, 'conversion_factor': None}
    SEAM billed_uom(): {'billed_uom': None, 'primary_uom': 'therm',
                        'conversion_factor': None}
    E   AssertionError: RED: gate cannot see a ccf tariff over a therm register
    E   assert True is False

`reason: "unconfigured"` is the whole defect. `tenant_services.billed_uom` is
NULL on every tenant this product has ever provisioned — `tenancy.services`
seeds `primary_uom` and `alt_uom` and nothing writes `billed_uom` — and the gate
read that NULL as *"nothing to contradict yet"*. The column's own reader says
the opposite (`tenancy.selectors.service_billed_uoms`: NULL *"means 'the
register's own unit is what is billed' and NOT 'unconfigured, refuse'"*), so the
gate was comparing a schedule against an always-empty column and reporting
SATISFIED over every mismatch there was.

WHAT WAS ALREADY GREEN, RECORDED SO THE NEXT LANE DOES NOT REBUILD IT
----------------------------------------------------------------------
The ENGINE already refuses this at bill time, and the same probe proved it::

    ENGINE REFUSAL: service 'gas': read unit 'therm' is not the billed unit
    'ccf' and the engine holds no conversion factor. BR-RAT-038 (PO R6):
    convert at rating input with a defined per-service factor, or block the
    read — never convert silently.

So the invariant was not missing end to end: it was missing at the **only place
a person could act on it**, which is why the SAVE-TIME gate is what this lane
fixed. tc5 pins the engine half so that removing it goes red in this file too,
and tc3 pins the one thing that is sized and NOT built — the save-time REFUSAL,
which turned 18 existing cases red because the shared fixtures price electric
schedules per kilogallon.

THE MONEY, WORKED
-----------------
One therm of pipeline gas is about `0.9643 ccf`. A `42`-unit gas read priced at
the signed `$1.15/ccf` bills **`$48.30`** when the register is read as ccf and
about **`$46.58`** when the same gas is converted honestly — roughly **4% over,
`$1.72` a month on one meter**, on a document that foots and that no gate
objected to.
"""

import pytest

from apps.rating import seams, selectors, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _register_reads(env, service_code, uom_code, alt=None):
    """Give the tenant's service a REGISTER unit and no billed_uom — which is
    every tenant this product provisions (`billed_uom` is seeded nowhere).

    ⚠ `alt` IS NOT DECORATION. `BR-TEN-027`'s `alt_equals_primary` refuses a
    service whose two units are the same string, so moving gas onto its OWN
    alternate has to move the other one out of the alternate slot **in the same
    call**. A lane that sends only `primary_uom` gets `VAL-002
    settings.services.alt_equals_primary` — the real refusal a utility switching
    its gas register would meet, so it is met here rather than discovered on a
    live tenant.

    ⚠ **AND `alt_uom` IS NOW SENT ON EVERY CALL, DEFAULTING TO `None` — which
    CLEARS the alternate (`DEF-3201`, 2026-09-02).** It used to be omitted when
    the caller passed nothing, and `update_tenant_service` reads an omitted key
    as *"keep what is on file"*. That was harmless only while gas was seeded
    `primary=therm, alt=ccf`. `BR-TEN-1180`/`DEF-3230` flipped it to
    `primary=ccf, alt=therm` the same day, and every `_register_reads(env,
    "gas", "therm")` in this file — four of them — then collided with the
    alternate it left in place and died on `alt_equals_primary` before reaching
    the assertion it was written for. Sending the key explicitly makes the
    helper say what it means: *this service reads THIS unit, and nothing else is
    claimed*.
    """
    from apps.tenancy import services as tenancy_services

    changes = {"enabled": True, "primary_uom": uom_code, "alt_uom": alt}
    with tenant_ctx(env.tenant):
        tenancy_services.update_tenant_service(env.admin, service_code, changes)


# ── tc1 · the defect itself, on the gas case the PO ruled on ────────────────
def test_tc1__a_ccf_schedule_over_a_therm_register_is_seen(env):
    """RED BEFORE THE FIX: `{'satisfied': True, 'reason': 'unconfigured'}`."""
    env.enable("gas")
    _register_reads(env, "gas", "therm")
    schedule = env.flat_schedule("Gas flat", "gas", "1.15", uom="ccf", effective_from=None)
    with tenant_ctx(env.tenant):
        gate = selectors.schedule_detail(schedule["id"])["uom_gate"]
    assert gate["satisfied"] is False
    # `therm` is declared ENERGY and `ccf` VOLUME (metering's `DIMENSION_OF`),
    # so no conversion factor reconciles them — the conversion needs a heating
    # value, which is a physical fact about the gas and not a column.
    assert gate["reason"] == "dimension_mismatch"
    assert gate["register_uom"] == "therm"
    # NULL `billed_uom` means the register's own unit is billed, so THAT is the
    # unit the schedule is compared against and the unit the copy must show.
    assert gate["billed_uom"] is None
    assert gate["priced_against"] == "therm"
    assert gate["reconciliation"]["multiplier_can_reconcile"] is False


def test_tc2__the_wizard_says_so_and_names_the_units(env):
    """The notice a clerk sees, with the EFFECTIVE unit in it rather than a
    blank — `params.billed_uom` used to carry the raw NULL column."""
    env.enable("gas")
    _register_reads(env, "gas", "therm")
    schedule = env.flat_schedule("Gas flat", "gas", "1.15", uom="ccf", effective_from=None)
    notice = next(n for n in schedule["notices"] if n["code"] == "rating.uom.mismatch_no_factor")
    assert notice["br_ref"] == "BR-RAT-038"
    assert notice["params"] == {"schedule_uom": "ccf", "billed_uom": "therm"}


# ── tc3 · what SAVE does today, pinned honestly ─────────────────────────────
def test_tc3__an_unreconcilable_schedule_still_ACTIVATES_and_that_is_reported(env):
    """⚠ **THE SAVE-TIME REFUSAL IS SIZED AND NOT BUILT, AND THIS CASE IS THE
    RECORD OF WHY** (`DEF-3106`).

    The PO's ruling prefers catching this where a person is typing, and a
    refusal at activation was WRITTEN — `_guard_uom_can_price`, refusing exactly
    the `dimension_mismatch` verdict at the four points a version goes into
    force. **Running it turned 18 cases of `tests/test_us_rat_schedules.py` red
    in one file**, and every one of them for the same honest reason: the shared
    fixtures price an ELECTRIC schedule per `kgal` (`test_us_rat_helpers
    .flat_schedule` / `.tiered_schedule` hardcode `"uom": "kgal"` for every
    service), which is a tariff quoted in kilogallons against a meter reading
    kilowatt-hours. **The refusal was right and the fixtures are wrong** —
    six test files carry that payload shape and 28 touch a hardcoded `kgal` —
    so landing the guard means sweeping them, and a half-swept sweep is a red
    branch. It is filed with that measurement rather than shipped half-done.

    **What the product does in the meantime is NOT nothing:** the gate now SEES
    the pair and says so on the wizard (tc1, tc2), and the ENGINE still refuses
    the bill by name (tc5). This case pins the gap so that closing it goes green
    here rather than silently.
    """
    env.enable("gas")
    _register_reads(env, "gas", "therm")
    schedule = env.flat_schedule("Gas flat", "gas", "1.15", uom="ccf")
    with tenant_ctx(env.tenant):
        gate = selectors.schedule_detail(schedule["id"])["uom_gate"]
    # It activated — no refusal — and the gate says plainly that it cannot price.
    assert schedule["current_version"]["effective_from"] == "2026-08-01"
    assert gate["satisfied"] is False and gate["reason"] == "dimension_mismatch"
    assert "rating.uom.mismatch_no_factor" in [n["code"] for n in schedule["notices"]]


def test_tc4__a_matching_unit_activates_exactly_as_it_always_did(env):
    """The gas case as the fixture now seeds it — `ccf` priced against a `ccf`
    register — so the signed `$1.15/ccf` applies AS SIGNED and nothing warns."""
    env.enable("gas")
    _register_reads(env, "gas", "ccf", alt="therm")
    schedule = env.flat_schedule("Gas flat", "gas", "1.15", uom="ccf")
    with tenant_ctx(env.tenant):
        gate = selectors.schedule_detail(schedule["id"])["uom_gate"]
    assert gate["satisfied"] is True
    assert gate["reason"] == "match"
    assert [n["code"] for n in schedule["notices"]] == []


# ── tc5 · the engine half, pinned rather than rebuilt ───────────────────────
def test_tc5__the_engine_still_refuses_the_same_pair_at_bill_time():
    """BR-RAT-038 at `pricing.stages.normalize`. It was ALREADY green — this
    case exists so that deleting it goes red beside the save-time guard, and so
    that the next lane does not add a second refusal believing there is none."""
    from decimal import Decimal
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


# ── tc6 · US-RAT-005 TC-7's ratified behaviour, UNMOVED ─────────────────────
def test_tc6__a_scale_mismatch_still_only_warns_and_a_factor_still_opens_it(env):
    """`kgal` against `ccf` is the SAME kind of quantity, so a factor can close
    it and the ratified posture is *warn now, rating blocked later*. Reversing
    that is a re-sign (HUMAN-GUIDE §6), not a change made in passing — so this
    case asserts it did NOT move."""
    env.set_billed_uom("water", "kgal")
    schedule = env.flat_schedule("Comm Water · ccf", "water", "2.90", uom="ccf")
    with tenant_ctx(env.tenant):
        gate = selectors.schedule_detail(schedule["id"])["uom_gate"]
    assert gate["satisfied"] is False
    assert gate["reason"] == "mismatch_no_factor"
    assert gate["reconciliation"]["multiplier_can_reconcile"] is True
    env.set_billed_uom("water", "kgal", factor="0.748")
    with tenant_ctx(env.tenant):
        reread = selectors.schedule_detail(schedule["id"])["uom_gate"]
    assert reread["satisfied"] is True
    assert reread["reason"] == "conversion_factor"


def test_tc7__a_declared_billed_uom_still_wins_over_the_register(env):
    """`billed_uom` is the DECLARATION and the register is the fallback for a
    NULL — not the other way round. A tenant that has said *"bill water in
    kgal"* is compared against kgal even where its register reads something
    else, which is `B2 r6.4`'s register→billed direction."""
    env.set_billed_uom("water", "kgal")
    with tenant_ctx(env.tenant):
        gate = selectors.uom_gate_for("water", "kgal")
    assert gate["satisfied"] is True and gate["reason"] == "match"
    assert gate["billed_uom"] == "kgal"
    assert gate["priced_against"] == "kgal"


def test_tc8__one_side_stating_no_unit_is_not_this_gates_business(env):
    """CLAUDE.md rule 3's ABSENCE is refused one step earlier (`estate_plan`
    refuses a service with no declared unit). A gate that ALSO refused it would
    send a clerk to the rate wizard for a Settings problem.

    ⚠ **THE SEWER LINE MOVED ON 2026-09-02 AND THAT IS THE FIX WORKING
    (`DEF-3201`).** It read `unconfigured` — right answer, accidental reason:
    sewer happened to have no declared unit, so it fell through the absence
    branch. Sewer is now answered on the SERVICE, before either unit is looked
    at, because `BR-RAT-015` ❄️ prices it as a share of the WATER usage charge
    and it reads no register at all. The old assertion would have gone green
    again the day somebody typed a unit into sewer's Settings row, and the
    verdict would have silently become `mismatch_no_factor`.
    """
    with tenant_ctx(env.tenant):
        assert selectors.uom_gate_for("water", None)["reason"] == "unconfigured"
        assert selectors.uom_gate_for("sewer", "kgal")["reason"] == "no_register"


def test_tc9__the_verdict_strings_come_from_metering_and_are_not_copied(env):
    """`BR-MET-143` owns match/scale/dimension and `apps.rating.seams` is the
    one door onto it. A rating file holding hand-typed copies of somebody
    else's enum stops matching the day metering renames one — and the branch
    not taken is the one that reports SATISFIED."""
    kinds = seams.unit_reconciliation_kinds()
    assert set(kinds) == {"match", "scale", "dimension", "unknown_dimension"}
    assert seams.unit_reconciliation("therm", "ccf")["kind"] == kinds["dimension"]
    assert seams.unit_reconciliation("kgal", "ccf")["kind"] == kinds["scale"]
    assert seams.unit_reconciliation("ccf", "ccf")["kind"] == kinds["match"]


def test_tc10__a_draft_is_gated_too_so_the_wizard_warns_before_activation(env):
    """A DRAFT carries the verdict as well, which is what makes the warning
    arrive while a clerk is still typing rather than after they commit.

    It is a warning and not a refusal, deliberately: refusing a draft would stop
    somebody saving work in progress on the way to fixing the very unit that is
    wrong."""
    env.enable("gas")
    _register_reads(env, "gas", "therm")
    with tenant_ctx(env.tenant):
        draft = services.create_rate_schedule(
            env.admin,
            {
                "name": "Gas draft",
                "service": "gas",
                "model": "flat",
                "uom": "ccf",
                "structure": {"unit_price": "1.15"},
            },
        )
    assert draft["uom_gate"]["reason"] == "dimension_mismatch"
    assert "rating.uom.mismatch_no_factor" in [n["code"] for n in draft["notices"]]


# ══════════════════════════════════════════════════════════════════════════
# DEF-3201 · A SERVICE WITH NO REGISTER IS OUTSIDE THIS RULE
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **WHAT WAS RED BEFORE tc11, VERBATIM, ON THE SCREEN A CLERK READS.** With
# the fixture's own trash schedule in place — `BR-RAT-090` prices trash per
# CART, three carts at `$15.00` is `$45.00` — the unit screen drew a
# `role="alert"` strip reading:
#
#     "This schedule prices in cart and the service is billed in , with no
#      conversion recorded. A bill cannot be produced from it until that is
#      settled."
#
# Two separate faults are visible in that one sentence and this block closes
# both.
#
#   1. **THE VERDICT WAS WRONG.** Measured on PostgreSQL 16.13 through
#      `tenancy.services.provision_tenant` with all ten services enabled, at
#      `4317090c`: trash resolved `priced_against='month'` (from the
#      `SERVICE_DEFAULT_UOMS` of the day) against a schedule priced in
#      `'cart'`, `unit_reconciliation` answered `unknown_dimension`, and the
#      gate answered `mismatch_no_factor` — telling a service that bills
#      perfectly well that it cannot produce a bill. The same tenant, provisioned
#      and seeded on PostgreSQL, produced **96 issued bills**.
#      **`cart` against `month` is not a mismatch, it is a CATEGORY ERROR.**
#      Trash reads no register, so there is nothing for a schedule unit to be
#      compared against, and the PO's own ruling says so: *"the same principle
#      is applied to all METER services"*.
#
#      ⚠ **`BR-TEN-1180` LANDED THE SAME DAY AND CHANGED THE FIX, NOT THE
#      FAULT.** The seed now gives trash `cart` as its own unit, so the two
#      strings happen to agree again — but the comparison was never meaningful,
#      and a tenant that types a different unit on S8 would meet the same
#      refusal tomorrow. The scope is now read from `billing_basis`, which is
#      the declaration the PO actually rules on.
#
#   2. **THE BLANK WAS THE FRONTEND, NOT THIS GATE.** `priced_against` is never
#      the empty string on any of the ten — measured, it is `kWh`, `kgal`,
#      `therm`, `month`, `ton-hr` or `None`. Three screens interpolated
#      `uom_gate.billed_uom`, the DECLARED column, which is NULL on every tenant
#      this product has ever provisioned because nothing seeds it. That half is
#      fixed in `UnitPricingPanel.tsx`, `RateScheduleDetail.tsx` and
#      `RateScheduleWizard.tsx` and pinned by their own suites; tc15 below holds
#      the backend end of it.


def _catalogue() -> tuple[str, ...]:
    """The ten service codes, READ from the platform seed and never retyped."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "apps/tenancy/migrations/0001_initial.py"
    spec = importlib.util.spec_from_file_location("_tenancy_0001_for_uom_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(code for code, _name in module.SERVICE_SEED)


# ── tc11 · the six services that read no register ──────────────────────────
@pytest.mark.parametrize(
    "service_code,schedule_uom",
    [
        # The PO's own case: the fixture's trash schedule, priced per CART
        # (BR-RAT-090) against trash's declared `month`. Both units present,
        # both correct, and comparing them is meaningless.
        ("trash", "cart"),
        ("sewer", "kgal"),  # BR-RAT-015 ❄️ — a share of the WATER usage charge
        ("storm_water", "kgal"),  # BR-MET-104 — impervious area
        ("solar", "month"),  # BR-TEN-170 — inverter capacity
        ("broadband", "month"),  # BR-MET-120 — "no register exists"
        ("battery", "month"),  # BR-TEN-170 — its rating
    ],
)
def test_tc11__a_service_with_no_register_is_outside_this_rule(env, service_code, schedule_uom):
    """RED BEFORE THE FIX for trash: `{'satisfied': False, 'reason':
    'mismatch_no_factor', 'schedule_uom': 'cart', 'priced_against': 'month'}`.

    The verdict is decided on the SERVICE, before either unit is read — which
    is what makes it a stated rule and not an accident of both sides happening
    to be blank. Trash proves that: it declares `month`, its schedule declares
    `cart`, both are present, and it is still outside the rule.
    """
    with tenant_ctx(env.tenant):
        gate = selectors.uom_gate_for(service_code, schedule_uom)
    assert gate["satisfied"] is True, gate
    assert gate["reason"] == "no_register", gate
    # The units are still REPORTED. The gate goes quiet about the VERDICT, not
    # about the facts, so a screen can still say what is on file.
    assert gate["schedule_uom"] == schedule_uom


# ── tc12 · THE REGRESSION GUARD: gas must still fail ───────────────────────
def test_tc12__gas_is_not_in_the_set_and_still_fails_the_gate(env):
    """⚠ **IF THIS EVER PASSES SATISFIED, `DEF-3108` HAS BEEN UNDONE RATHER
    THAN COMPLETED.** A `ccf` tariff over a `therm` register is roughly **4%
    over on every gas line — `$1.72` a month on one meter** — and catching it
    is the only reason this gate was made able to fail at all.

    Asserted two ways on purpose: the VERDICT, and the DECLARATION that decides
    it. A lane that re-based gas onto `capacity` in `SERVICE_DEFAULT_UOMS` would
    move the declaration without moving a single unit, and a verdict assertion
    alone would then be all that stood between that edit and a live bill.
    """
    with tenant_ctx(env.tenant):
        assert seams.service_bills_from_a_register("gas") is True
    env.enable("gas")
    _register_reads(env, "gas", "therm")
    with tenant_ctx(env.tenant):
        gate = selectors.uom_gate_for("gas", "ccf")
    assert gate["satisfied"] is False
    assert gate["reason"] == "dimension_mismatch"
    assert gate["priced_against"] == "therm"


# ── tc13 · a blank unit is an absent unit ──────────────────────────────────
def test_tc13__a_blank_unit_is_an_absent_unit_not_a_mismatch(env):
    """`rate_schedule_versions.uom` is `TextField(null=True, blank=True)`, so a
    blank is a lawful stored value and it says exactly what a NULL says: nobody
    has stated what this is priced in.

    RED BEFORE THE FIX (the branch read `is None`): `{'satisfied': False,
    'reason': 'mismatch_no_factor'}`, with the empty string interpolated into
    the clerk's sentence — *"this schedule prices in  and the service is billed
    in kgal"*.

    ⚠ **AND IT IS HONEST ABOUT BEING DEFENCE.** The product's own doors cannot
    store a blank today — `services._text` turns one into `None` before it is
    written — so no live path reaches this branch. It is held correct anyway
    because it is the branch that was WRONG, and re-deriving that it is
    unreachable costs more than keeping it right.
    """
    env.enable("water")
    _register_reads(env, "water", "kgal")
    with tenant_ctx(env.tenant):
        assert selectors.uom_gate_for("water", "")["reason"] == "unconfigured"
        assert selectors.uom_gate_for("water", "   ")["reason"] == "unconfigured"
        assert selectors.uom_gate_for("water", None)["reason"] == "unconfigured"


# ── tc14 · the scope is the tenant's DECLARATION, over all ten ─────────────
def test_tc14__every_catalogue_service_is_scoped_by_its_own_declaration(env):
    """**THE SCOPE IS DATA, NOT A LIST THIS MODULE KEEPS — and this case walks
    all ten to prove it.**

    The first draft of `DEF-3201` carried the classification as a frozenset in
    `rating.selectors`. `BR-TEN-1180` landed the same day and made it a COLUMN
    the PO rules on — `tenant_services.billing_basis`, seeded for all ten by
    `tenancy/0030` — so the frozenset would have been a second hand-kept copy of
    a declaration the database already holds. That is `G47`'s own reasoning,
    verbatim: *"a gate that carries its own copy of the list it is policing is
    the fifteenth copy, and would go green on the day the seed changed
    underneath it."*

    So the assertion is the DERIVED split, over the platform seed, read through
    the seam. Of the ten, exactly four read a register — and they are the four
    `BR-MET-067` (as amended by `BR-TEN-170`) names, which is the statement
    underneath. An eleventh catalogue service arrives here as a red test rather
    than as silence.
    """
    from apps.tenancy import models as tenancy_models
    from apps.tenancy.services import SERVICE_DEFAULT_UOMS

    catalogue = _catalogue()
    with tenant_ctx(env.tenant):
        gated = {code for code in catalogue if seams.service_bills_from_a_register(code)}
    # (a) THE CROSS-CHECK, and it is the clause that survives an eleventh
    # service: rating's seam and tenancy's ruled seed must classify every
    # catalogue service the same way. A service added to the catalogue and NOT
    # to the map falls back to `metered` (`_default_basis_for`), which is the
    # safe direction and is asserted here rather than assumed.
    ruled = {
        code
        for code in catalogue
        if getattr(SERVICE_DEFAULT_UOMS.get(code), "basis", None)
        in (None, tenancy_models.BILLING_BASIS_METERED)
    }
    assert gated == ruled, (gated, ruled)
    # (b) THE WORKED STATEMENT, written so an eleventh service does not fail it
    # for the wrong reason. `BR-MET-067` as amended by `BR-TEN-170` names four
    # meter services among the ten, and names six that read no register.
    # ⚠ **`thermal_heat` LEFT THIS LINE ON 2026-09-07 (`CR-080`)** — the PO
    # ruled it capacity-based on connected tonnage, so it reads no register and
    # belongs on the NOT-gated side below. Three meter services now, not four.
    assert {"electric", "water", "gas"} <= gated, gated
    assert not gated & {
        "sewer",
        "trash",
        "storm_water",
        "solar",
        "broadband",
        "thermal_heat",  # CR-080, 2026-09-07 — capacity, on connected tonnage
        "battery",
    }, gated


def test_tc14b__a_service_the_tenant_has_no_row_for_is_GATED(env):
    """**The fail-safe direction, asserted rather than assumed (hard-won law 3).**

    A tenant that has declared NOTHING for a service has not declared *"no
    register"*. Wrong-and-gated shows a person a warning they can act on;
    wrong-and-ungated shows nobody anything, and what goes quiet is the gas case
    this gate exists for — `4%` over on every line, `$1.72` a month on one
    meter. `tenancy.selectors.service_row` reads an absent row the same way.
    """
    with tenant_ctx(env.tenant):
        assert seams.service_bills_from_a_register("no_such_service") is True


# ── tc15 · the clerk's sentence never carries a blank ──────────────────────
def test_tc15__the_notice_names_the_effective_unit_and_never_the_null_column(env):
    """The blank the PO reported, closed at the source that feeds every screen.

    `params["billed_uom"]` is the EFFECTIVE unit — `priced_against` — and never
    `tenant_services.billed_uom`, which is NULL on every tenant ever
    provisioned. A screen that interpolates the declared column draws *"the
    service is billed in "* with nothing in it, which is exactly what
    `UnitPricingPanel.tsx` did.
    """
    env.enable("gas")
    _register_reads(env, "gas", "therm")
    schedule = env.flat_schedule("Gas flat", "gas", "1.15", uom="ccf", effective_from=None)
    notice = next(n for n in schedule["notices"] if n["code"] == "rating.uom.mismatch_no_factor")
    with tenant_ctx(env.tenant):
        gate = selectors.uom_gate_for("gas", "ccf")
    assert gate["billed_uom"] is None, "the DECLARED column is NULL on a provisioned tenant"
    assert notice["params"]["billed_uom"] == gate["priced_against"] == "therm"
    assert notice["params"]["billed_uom"], "a blank here is the sentence the PO reported"
