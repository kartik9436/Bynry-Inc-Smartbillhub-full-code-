# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2397 (high) — a tenant that sells electric, gas or storm water
#          gets a full metered estate and ZERO bills, because rating's sample
#          fixture was still `water` / `sewer` / `trash` in literals after
#          CR-039 wave A made metering and assets service-shaped.
# Story:   US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S8, S10, S11
# Rules:   BR-RAT-024 (the catalogue is TEN services) · BR-RAT-025 (plan as
#          bundle) · BR-RAT-088 / DEF-528 (an `is_base` charge code for EVERY
#          service the seed prices, or for none) · BR-RAT-108 (one service's
#          two amounts are separated by CLASS) · BR-RAT-120 / DEF-2799 (the
#          size axis) · BR-MET-040 (an account derives its plan from the unit)
#          · BR-TEN-060 (a gap is NAMED, never a silent zero) · BR-MET-108
#          (an absent characteristic bills as ZERO, stamped and surfaced) ·
#          CLAUDE.md rule 3 (a quantity carries its unit)
# Questions: OQ-1290 (what does a demo electric / gas / storm-water backbone
#          charge for USAGE?) — OPEN, and this file asserts only what is ruled
# Tests:   this file · tests/test_service_billing_coverage.py (the bill count)
# ───────────────────────────────────────────────────────
"""**RATING SEEDS THE ESTATE THE TENANT ACTUALLY HAS — AND ONLY SIGNED MONEY.**

`DEF-2397` had two halves and they need two different kinds of check.

**The SHAPE half is here.** Does `apps/rating/sample_data` build a schedule, a
plan and a base charge code for the backbone `core.sample_fixture.estate_plan`
resolved — the same backbone metering plants meters in and assets numbers them
for? Before the fix an electric tenant got **none of the three**, and the
failure appeared four blocks later in `apps/customers` under
`customers.account.plan_required_at_activation`, naming neither rating nor
electric.

**The BILL half is `tests/test_service_billing_coverage.py`**, which provisions
one tenant per catalogue service through the real signup service and counts
issued invoices. That file is the scoreboard; this one says why the number
moved and pins every figure it moved on.

WHAT IS ASSERTED, AND WHAT IS DELIBERATELY NOT
-----------------------------------------------
**Asserted: every figure that IS signed.** `[W] §1`'s Base/mo column — electric
`$12.00` residential and `$48.00` Small Commercial, gas `$6.00` — and the fact
that the plan's figure and `BR-RAT-088`'s charge code state the SAME number.
`DEF-2823` is what it costs when those two drift: `$180.00` on the plan against
`$12.00` on the code, a `$168.00` gap that nothing could see because the live
path reads one and the ruled chain reads the other.

**Asserted: the usage price is a stored `$0.00` and it NAMES its question.**
That is not an approval of `$0.00`; it is `BR-TEN-060`'s report-by-name and
`DEF-491`'s prevention — *a placeholder pending an answer must cite the question
at the place the placeholder lives* — made into a check, so closing `OQ-1290`
cannot leave the fixture behind the way closing `OQ-303` did for a day.

**NOT asserted: what the usage SHOULD cost.** No signed figure prices these
services against the single register this fixture plants (see
`core.sample_fixture.BACKBONE_USAGE_UNPRICED` for the evidence service by
service), and the prime directive forbids a lane answering an open question by
choosing a value.

**Asserted: a WATER tenant is unmoved, byte for byte.** Every frozen figure this
fixture reproduces is a water figure — GT-17 ❄️'s `$39.50` usage and `$15.80`
sewer stand on unit 0 drawing exactly 8 kgal — so the case that would have
mattered most is the one where this change did nothing.

RED PROVED FIRST, ON POSTGRESQL 16, BEFORE A LINE WAS WRITTEN
--------------------------------------------------------------
Four signup shapes through `tenancy.services.provision_tenant`::

    svc-electric   prem=70 units=118 sp=75 sched=0 plans=0 acct=0 issued=0  failed=9/17
    svc-gas        prem=70 units=118 sp=49 sched=0 plans=0 acct=0 issued=0  failed=9/17
    svc-stormwater prem=70 units=118 sp=49 sched=0 plans=0 acct=0 issued=0  failed=9/17
    svc-water      prem=70 units=118 sp=75 sched=3 plans=2 acct=70 issued=95 failed=0/17

and the first named cause on all three::

    customers/seed_sample_records: no sample account was created: every one of
    the 48 seats this tenant holds refused … SCW-U-001: BizError:
    BIZ-COMPLETENESS (customers.account.plan_required_at_activation)

Each case below states what it said when the fix was reverted.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import sample_data, service_base_amounts
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


#: The estate a MUNICIPAL utility gets — water backbone, sewer and trash
#: alongside. Stated rather than provisioned so the figure cases cost no tenant.
WATER_ESTATE = ("water", "sewer", "trash")


def _estate(*services: str, uom: str | None = None) -> fixture.EstatePlan:
    """The estate plan a tenant selling `services` resolves to.

    The same pure function metering, assets and rating all call, given the
    tenant's declared units — so a test that states an estate here is stating
    exactly what the product would have resolved, not a convenient shape.
    """
    from apps.tenancy.services import SERVICE_DEFAULT_UOMS

    uoms = {code: (uom or SERVICE_DEFAULT_UOMS.get(code, (None,))[0]) for code in services}
    return fixture.estate_plan(list(services), uoms)


def _payloads(monkeypatch, *services: str) -> dict[str, dict]:
    """`_schedule_payloads()` for a tenant selling `services`, keyed by name."""
    monkeypatch.setattr(sample_data, "estate", lambda: _estate(*services))
    monkeypatch.setattr(sample_data.seams, "billed_uom", lambda code: None)
    return {row["name"]: row for row in sample_data._schedule_payloads()}


def _plan_rows(monkeypatch, schedule_ids: dict[str, str], *services: str) -> list[dict]:
    """`_plan_payloads()` for a tenant selling `services`.

    Two tenant-scoped reads are stubbed and NEITHER is money: the tax
    jurisdictions the plan levies against, and the platform `account_types` id
    for the class the plan prices for. Stubbing them lets the FIGURES and the
    SERVICE be asserted without provisioning a tenant, which is the same
    posture `tests/test_def2799_seeded_size_axis.py` takes on the schedules.
    The live case at the end of this file runs the real seeder on a real tenant
    and asserts both again from the database, so nothing here is the only proof
    of anything.
    """
    monkeypatch.setattr(sample_data, "estate", lambda: _estate(*services))
    monkeypatch.setattr(sample_data.seams, "billed_uom", lambda code: None)
    monkeypatch.setattr(sample_data.selectors, "jurisdiction_list", lambda: [])
    monkeypatch.setattr(sample_data, "_account_type_id", lambda code: f"account-type-{code}")
    return sample_data._plan_payloads(schedule_ids)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE SHAPE — a backbone the tenant actually has gets priced
# ══════════════════════════════════════════════════════════════════════════


#: The non-water METERED services, which is what a "backbone schedule" is for.
#:
#: ⚠ **`storm_water` LEFT THIS LIST ON 2026-09-02 (`CR-062` C9, `DEF-3231`) AND
#: `thermal_heat` JOINED IT — AND THEN LEFT AGAIN ON 2026-09-07 (`CR-080`).**
#: The PO ruled storm water capacity-billed — on the size of the property, not
#: on a dial — so it gets a CAPACITY schedule and no register at all; thermal
#: gained a declared unit under `DEF-2396`, was metered for five days, and was
#: ruled capacity-billed on connected tonnage on 2026-09-07. **This list was
#: right on every one of those days without being edited once**, which is the
#: whole argument for the sentence after this one. Read from the fixture rather
#: than retyped, so the day the metered
#: list changes again this list changes with it instead of quietly testing a
#: service that has moved.
NON_WATER_METERED = [
    code for code in fixture.METERED_ESTATE_SERVICES if code != "water"
]

#: **THE PRICING MODEL EACH NON-WATER BACKBONE IS SEEDED WITH — AMENDED
#: 2026-09-02 (`CR-062` E1).**
#:
#: ⚠ **THIS CASE ASSERTED `"flat"` FOR ALL THREE UNTIL TODAY, AND IT WAS RIGHT
#: WHEN IT WAS WRITTEN.** Every non-water metered service was priced at
#: `BACKBONE_USAGE_UNPRICED` — a single stored zero — so one flat row was the
#: whole truth. The PO signed electric's ladder on 2026-09-02, statement (7)
#: verbatim: *"Electric $12.00 base kWh read - along with base you will need
#: rate schedule - Either Tiered or TOU"*, and TIERED was chosen over TOU
#: (`CR-062` judgment 2 — TOU needs three registers per meter and the seeded
#: estate plants one).
#:
#: **Gas and thermal stay FLAT and for different reasons**, which is why this is
#: a map and not a second literal: thermal is signed at a single `$0.045` per
#: ton-hour (`E6`), and gas is not part of group E at all — `[W] §1` signs it at
#: `$1.15/ccf` but seeding that is group B's task, so it keeps the stored zero
#: and `OQ-1290` stays open for gas alone.
#: ⚠ **`thermal_heat` LEFT THIS MAP ON 2026-09-07 (`CR-080`)** — the PO ruled
#: it capacity-billed on connected tonnage, so it has no BACKBONE schedule to
#: have a model. `NON_WATER_METERED` above is derived from the fixture, so it
#: dropped thermal on its own; this map is explicit and had to be told.
BACKBONE_MODEL: dict[str, str] = {
    "electric": "tiered",
    "gas": "flat",
}


@pytest.mark.parametrize("service", NON_WATER_METERED)
def test_a_non_water_backbone_gets_a_schedule_at_all(monkeypatch, service):
    """**THE DEFECT ITSELF.** Rating builds a usage schedule for the service.

    RED PROVED FIRST — with `_schedule_payloads` restored to its three literals:

        AssertionError: a tenant that sells electric gets NO rate schedule at
        all, so no plan can be published, every unit keeps rate_plan_id NULL and
        all 48 seats refuse at activation (BR-MET-040). That is DEF-2397.
        assert {} != {}
    """
    payloads = _payloads(monkeypatch, service)
    assert payloads, (
        f"a tenant that sells {service} gets NO rate schedule at all, so no plan "
        "can be published, every unit keeps rate_plan_id NULL and all 48 seats "
        "refuse at activation (BR-MET-040). That is DEF-2397"
    )
    name = sample_data.backbone_schedule_name(service)
    assert name in payloads, f"the backbone schedule is not among {sorted(payloads)}"
    row = payloads[name]
    assert row["service"] == service
    # CR-062 E1 — electric is TIERED since 2026-09-02; gas and thermal stay
    # flat. See BACKBONE_MODEL above for which ruling moved which service.
    assert row["model"] == BACKBONE_MODEL[service], (
        f"{service} is seeded as a {row['model']!r} schedule and this repo "
        f"expects {BACKBONE_MODEL[service]!r}"
    )


@pytest.mark.parametrize(
    ("service", "expected_uom"),
    # ⚠ **GAS READS `ccf` SINCE `CR-062` B1 AND STORM WATER IS NOT HERE SINCE
    # C9.** Gas's two units were SWAPPED so the register agrees with the signed
    # `$1.15 per ccf` — the fixture used to plant a `therm` register against a
    # `ccf` price, which is the mismatch the bill-time unit gate refuses. Storm
    # water is capacity-billed and reads nothing.
    # ⚠ **AND THERMAL LEFT ON 2026-09-07 (`CR-080`)** — the PO ruled it
    # capacity-billed on connected tonnage, so it plants no meter and there is
    # no register unit for a schedule to agree with. Two metered backbones are
    # measured here now; water has its own frozen cases elsewhere.
    [("electric", "kWh"), ("gas", "ccf")],
)
def test_the_backbone_schedule_is_priced_in_the_unit_the_meter_reads(
    monkeypatch, service, expected_uom
):
    """CLAUDE.md rule 3 — and the substance of it, not the form.

    The schedule's UoM is the tenant's OWN declared primary unit, which is the
    unit `assets.sample_data` creates the meter with. A price quoted in a
    different unit satisfies rule 3 in FORM and is wrong in SUBSTANCE, which is
    `DEF-497` — `$15.00` per *month* against a quantity of three *carts*, and
    the reason `[W] §1`'s `$1.15` per **ccf** is NOT seeded against a gas
    register that reads **therm**.
    """
    row = _payloads(monkeypatch, service)[sample_data.backbone_schedule_name(service)]
    primary = _estate(service).primary
    assert primary is not None
    assert row["uom"] == expected_uom == primary.uom


@pytest.mark.parametrize("service", NON_WATER_METERED)
def test_the_backbone_schedule_states_its_size_axis(monkeypatch, service):
    """BR-RAT-120 / `DEF-2799` — without it R3 refuses every meter by size.

    The axis is the PLATFORM's ratified ladder for the service, which is the
    same list `assets.sample_data` takes the seeded meter's own `size_class`
    from (its first band), so the meter's size is in the schedule's axis by
    construction rather than by luck.
    """
    from apps.tenancy import service_size_classes

    row = _payloads(monkeypatch, service)[sample_data.backbone_schedule_name(service)]
    ratified = [code for code, _name in service_size_classes.size_classes_for_service(service)]
    assert ratified, f"{service} has no ratified size bands — this test is measuring nothing"
    assert [r["size_class"] for r in row["size_rows"]] == ratified
    assert all("minimum_bill" not in r for r in row["size_rows"]), (
        "a seeded size row states that the size IS served and has no floor — a "
        "$0.00 minimum would be a price nobody signed"
    )


def test_the_plan_prices_the_backbone_service_and_not_the_literal_water(monkeypatch):
    """`_plan_payloads` names the service the estate resolved.

    RED PROVED FIRST — with `_services` restored to `"service": "water"`:

        AssertionError: the residential plan prices ['water'] on a tenant that
        sells only electric — a plan for a service this utility does not sell,
        which publish refuses and no unit could derive
    """
    name = sample_data.backbone_schedule_name("electric")
    # DEF-RAT-9842 — electric's two classes pay different bases ($12.00 /
    # $48.00), and a schedule names ONE base code, so the commercial plan binds
    # its own electric schedule.
    com_name = sample_data.backbone_commercial_schedule_name("electric")
    payloads = _plan_rows(
        monkeypatch,
        {
            name: "01a04780-0000-7000-8000-000000000001",
            com_name: "01a04780-0000-7000-8000-000000000002",
        },
        "electric",
    )

    assert [p["code"] for p in payloads] == [
        sample_data.PLAN_RESIDENTIAL,
        sample_data.PLAN_COMMERCIAL,
    ], "both sample plans must exist — metering puts commercial units on SCW-COM"
    for payload in payloads:
        priced = [row["service"] for row in payload["services"]]
        assert priced == ["electric"], (
            f"the {payload['code']} plan prices {priced} on a tenant that sells only "
            "electric — a plan for a service this utility does not sell, which "
            "publish refuses and no unit could derive"
        )


def test_both_plans_may_bind_the_one_backbone_schedule(monkeypatch):
    """One usage answer, one schedule, two plans — and it is legal.

    `uq_plan_rate_schedules_plan_service` is on `(rate_plan, service)`, so two
    plans pointing at one tariff is a supported shape. Water gets two schedules
    because its two are structurally different (inclining tiers against a flat
    rate); electric, gas and storm water have ONE usage answer today, so two
    identical rows on S11 would be a question a clerk has to ask for nothing.
    """
    monkeypatch.setattr(sample_data, "estate", lambda: _estate("gas"))
    monkeypatch.setattr(sample_data.seams, "billed_uom", lambda code: None)
    gas = _estate("gas").primary
    assert gas is not None
    (res_name, _res_base), (com_name, _com_base) = sample_data.backbone_plan_inputs(gas)
    assert res_name == com_name == sample_data.backbone_schedule_name("gas")
    assert len(_payloads(monkeypatch, "gas")) == 1


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE MONEY — every signed figure, and every unsigned one named
# ══════════════════════════════════════════════════════════════════════════


def test_the_signed_base_charges_are_the_workbook_figures():
    """`[W] §1`'s Base/mo column, in the one place the seeder reads it from.

    Residential Standard *"Base/mo … Electric $12"* · Small Commercial
    *"Elec $48"* · Gas add-on *"$6"*. A second literal for any of these anywhere
    would be a second source of truth for exactly the fact `DEF-2823` is about.
    """
    assert fixture.BACKBONE_BASE["electric"] == (fixture.ELECTRIC_BASE, "48.00")
    assert Decimal(fixture.BACKBONE_BASE["electric"][0]) == Decimal("12.00")
    assert Decimal(fixture.BACKBONE_BASE["electric"][1]) == Decimal("48.00")
    assert Decimal(fixture.BACKBONE_BASE["gas"][0]) == Decimal("6.00")
    assert fixture.BACKBONE_BASE["gas"][0] == fixture.BACKBONE_BASE["gas"][1], (
        "the workbook states ONE gas base and names no class — splitting it "
        "would be inventing the commercial half"
    )


def test_a_backbone_the_workbook_prices_nowhere_states_a_stored_zero():
    """Thermal/heat — and a stored zero is a PRICE, an omission is a REFUSAL.

    ⚠ **THIS CASE WAS ABOUT STORM WATER UNTIL 2026-09-02 (`CR-062` C9,
    `DEF-3231`).** The PO ruled storm water capacity-billed, so it left the
    metered map entirely and its base is `fixture.CAPACITY_BASE` — the same
    stored `"0"`, for the same reason, on the other side of the same
    distinction. Thermal/heat is the metered service the workbook prices
    nowhere, so it is what this clause is now measured on. **No figure moved:
    both were `"0"` before and both are `"0"` now.**

    `CR-013` part 1 (PO 2026-08-19) makes a BLANK base mean *this size is not
    served* and `gather._base_charge_for` stops the bill on it (`DEF-277`); a
    stored zero prints `$0.00`. This is the SEWER precedent applied to a second
    service, not a new judgment: `BASE-S` has read `"0"` since it was written
    because *"a base nobody signed is a base this fixture does not invent."*

    It is also the RULED answer rather than a fallback: `BR-MET-108` bills an
    absent characteristic as ZERO — *"Bill it as zero"*.
    """
    # ⚠ **THERMAL LEFT `BACKBONE_BASE` ON 2026-09-07 (`CR-080`), EXACTLY AS
    # STORM WATER LEFT IT ON 2026-09-02 AND FOR THE SAME REASON.** It held
    # `("0", "0")` — nothing signed — and the PO then ruled it capacity-billed
    # on connected tonnage, so its base is the CAPACITY path's now. **No figure
    # moved on the way across: it was `"0"` on the metered side and the
    # capacity path defaults to the same `CAPACITY_BASE` zero.**
    assert "thermal_heat" not in fixture.BACKBONE_BASE
    # ⚠ **AND THE RESEARCHED `$20.00` SURVIVES THE MOVE, WHICH IS THE PART TWO
    # LANES CROSSING ON ONE DAY COULD EASILY HAVE LOST.** A sibling lane
    # researched a municipal monthly base for thermal under the PO's own
    # delegation hours before `CR-080` moved the service; `capacity_base_charge
    # _codes` and `capacity_plan_services` BOTH call `base_for(code,
    # fixture.CAPACITY_BASE)`, so the figure is picked up on the capacity path
    # with no edit — asserted here rather than assumed, because a researched
    # figure silently reverting to `$0.00` moves money and nothing would say so.
    assert service_base_amounts.base_for("thermal_heat", fixture.CAPACITY_BASE) == "20.0000"
    # CR-062 C9 — storm water is capacity-billed now, so it states its zero
    # through `CAPACITY_BASE` and is deliberately absent from the metered map.
    assert "storm_water" not in fixture.BACKBONE_BASE
    assert Decimal(fixture.CAPACITY_BASE) == Decimal("0")
    # And the two metered backbones the workbook DOES price are untouched.
    assert Decimal(fixture.BACKBONE_BASE["electric"][0]) == Decimal("12.00")
    assert Decimal(fixture.BACKBONE_BASE["gas"][0]) == Decimal("6.00")


def test_oq_1290_is_closed_so_nothing_still_reports_it_as_a_gap():
    """BR-TEN-060 — a gap is a NAMED line, never a silent zero. **`OQ-1290` is
    no longer a gap, so the name must go too.**

    ⚠ **THIS CASE WAS `DEF-491`'s PREVENTION AND IT HAS BEEN TURNED ROUND
    (`DEF-RAT-4516`, 2026-09-07).** It used to assert that `NOT_SEEDED` CARRIES
    an `OQ-1290` entry quoting `$12.00`, `$48.00`, `$6.00`, `$1.15` and
    `therm` — because the trash schedule sat at `$0.00` for a day after
    `OQ-303` was ruled and nothing noticed, so a placeholder had to name its
    question where a check could read it. **The question is now CLOSED**:
    electric took `ELECTRIC_TIERS` and thermal `$0.045` (`CR-062` E1/E6,
    2026-09-02), storm water is a ruled zero on the capacity side
    (`BR-MET-108`), and gas takes the signed `$1.15/ccf` from 2026-09-07.

    **The check therefore asserts the OPPOSITE, and it is the same law doing
    the same job in the other direction.** `DEF-491`'s real lesson is that a
    placeholder and its question must move together; CLAUDE.md's is that a
    closed question's BODY goes on describing the open world and the body is
    what the next lane reads. A `NOT_SEEDED` row still reporting `OQ-1290`
    would tell a utility on the Sample data panel that its gas usage is
    unpriced while its bill charges `$46.00` for it.
    """
    stale = [entry for entry in sample_data.NOT_SEEDED if entry["oq"] == "OQ-1290"]
    assert not stale, (
        "NOT_SEEDED still reports OQ-1290 as an unseeded gap, and it closed on "
        "2026-09-07 when gas took the workbook's signed $1.15/ccf. A panel that "
        "says 'no usage price is seeded' over a bill charging $46.00 for usage "
        f"is worse than silence. Stale entry: {stale}"
    )
    # The constant itself is KEPT — it still has a live caller as the `.get()`
    # default for a metered service with no signed price — but no seeded
    # service lands on it now. See its own note in core/sample_fixture.py.
    assert fixture.BACKBONE_USAGE_UNPRICED == "0"


def test_the_signed_gas_usage_figure_is_seeded_as_signed(monkeypatch):
    """`[W] §1` line 22's *"Gas flat $1.15/ccf"* is what the seeded gas schedule
    actually charges.

    ⚠ **THIS CASE ASSERTED THE EXACT OPPOSITE UNTIL 2026-09-07, ON PURPOSE, AND
    IT IS FLIPPED DELIBERATELY RATHER THAN DELETED (`DEF-RAT-4516`).** It was
    named `..._is_recorded_and_seeded_nowhere` and its two live lines were
    `unit_price != GAS_FLAT_PER_CCF` and `unit_price == BACKBONE_USAGE_UNPRICED`
    — it GUARANTEED that the seeded price was not the signed one. That was
    correct when it was written: the figure is per `ccf` and the seeded gas
    register read `therm`, two units of DIFFERENT DIMENSIONS that no conversion
    factor can reconcile, so pricing the read on it would have been `OQ-004`'s
    forbidden silent conversion and `OQ-303` option (B) — a signed figure
    quietly made to mean something else, billing about 4% over.

    **`BR-TEN-1180` / the PO-filed `DEF-3230` removed that premise on
    2026-09-02** by swapping the seeded register to `ccf`. The test then went on
    guaranteeing a `$0.00` usage line for five days with nothing red, which is
    why the PO met it as *"One real gap, and it is money. Gas bills $0.00
    usage"* rather than a check meeting it first. A test that pins a deliberate
    wrong answer has to be moved BY HAND the day its reason expires — nothing
    can notice for you, which is the whole cost of writing one.

    **The two spellings are pinned to each other here** so the workbook quote
    (`"1.15"`) and the stored four-decimal figure (`"1.1500"`, CLAUDE.md hard
    rule 2) can never drift into two different prices.
    """
    assert fixture.GAS_FLAT_PER_CCF == "1.15"
    seeded = fixture.METERED_USAGE_PRICES["gas"]
    assert Decimal(seeded) == Decimal(fixture.GAS_FLAT_PER_CCF), (
        f"the seeded gas price {seeded!r} is not the workbook's signed "
        f"{fixture.GAS_FLAT_PER_CCF!r} per ccf"
    )
    row = _payloads(monkeypatch, "gas")[sample_data.backbone_schedule_name("gas")]
    assert Decimal(row["structure"]["unit_price"]) == Decimal(fixture.GAS_FLAT_PER_CCF)
    assert Decimal(row["structure"]["unit_price"]) != Decimal(
        fixture.BACKBONE_USAGE_UNPRICED
    ), "the gas usage schedule is back on the stored zero — this is DEF-RAT-4516"
    # The unit the price is quoted per is the register's own (CLAUDE.md rule 3),
    # and it is `ccf` — the whole reason the signed figure is usable at all.
    assert row["uom"] == "ccf"

    # ── THE ACCEPTANCE ARITHMETIC, FROM THE FIXTURE AND NOT FROM A LITERAL ──
    # The reference gas customer draws CONSUMPTION_SCALE["gas"] x the declared
    # shape. 40 ccf x $1.15 = $46.00 usage, plus the signed $6.00 base = $52.00
    # before tax, where it was $6.00 and twelve cents of tax before this landed.
    ccf = fixture.consumption(fixture.CASE_REFERENCE_BILL, "june", service="gas")
    assert ccf == Decimal("40"), f"the reference gas customer draws {ccf} ccf, expected 40"
    usage = (ccf * Decimal(fixture.GAS_FLAT_PER_CCF)).quantize(Decimal("0.01"))
    assert usage == Decimal("46.00")
    assert usage + Decimal(fixture.GAS_BASE) == Decimal("52.00")


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        # ⚠ `DEF-RAT-8811` — `CR-062` J3/J4 (2026-09-02, `DEF-3282`): the
        # residential code also claims `municipal` (a government account matched
        # no base and billed nothing), and electric carries a THIRD base for
        # `industrial`, so the commercial code stops claiming it (`DEF-468`).
        (
            "electric",
            (
                ("BASE-E", "12.00", ["residential", "municipal"]),
                ("BASE-E-COM", "48.00", ["commercial"]),
                ("BASE-E-IND", "180.00", ["industrial"]),
            ),
        ),
        ("gas", (("BASE-G", "6.00", []),)),
        # ⚠ **`thermal_heat` LEFT THIS LIST ON 2026-09-07 (`CR-080`)** — it
        # moved to the CAPACITY side with `BASE-TH` unchanged, exactly as storm
        # water moved with `BASE-SW` on 2026-09-02. `backbone_base_charge_codes`
        # is asked only of a METERED service, so asking it about thermal now
        # would be testing a path the product no longer takes — the researched
        # `$20.00` a sibling lane put on it the same day is asserted on the
        # CAPACITY path instead, in the case above.
    ],
)
def test_the_backbone_declares_its_base_charge_code(service, expected):
    """BR-RAT-088 / `DEF-528` — and without it NOTHING seeds at all.

    The guard is SELF-ACTIVATING per tenant: it returns early while no `is_base`
    charge exists and, once one does, refuses every schedule whose service has
    no base code. `DEF-528`'s own rule is *"a base charge code is seeded for
    EVERY service this seed prices, or for none."*

    `BR-RAT-108` separates one service's two amounts by CLASS and never by name
    — which is why electric has two codes and gas, whose workbook row names no
    class, has one.
    """
    # CR-062 C1 — asked of ONE metered service rather than of the estate, which
    # is what makes the all-ten tenant get all four sets instead of one.
    primary = _estate(service).primary
    assert primary is not None
    rows = sample_data.backbone_base_charge_codes(primary)
    got = tuple((r["code"], r["amount"], r["applies_to_customer_classes"]) for r in rows)
    assert got == expected
    for row in rows:
        assert row["service"] == service


def test_the_plan_and_the_charge_code_state_the_same_base_to_the_cent():
    """`DEF-455`'s requirement, and `DEF-2823` is what it costs to break it.

    Two sources for one figure drift, and this pair drifts INVISIBLY: the live
    bill path reads `plan_services.base_charge` and `BR-RAT-088`'s R4 chain
    reads the charge code, so a disagreement moves no bill and shows up only
    when somebody points both at one number. On the demo tenant that was
    `$180.00` against `$12.00` — a `$168.00` gap that had been there for weeks.
    """
    for service in NON_WATER_METERED:
        metered = _estate(service).primary
        assert metered is not None, service
        (_res_name, res_base), (_com_name, com_base) = sample_data.backbone_plan_inputs(metered)
        # ⚠ `DEF-RAT-8811` — keyed by the PLAN CLASS each code serves, not by
        # its exact class list: since `CR-062` J3/J4 the residential code also
        # claims `municipal` (`fixture.base_code_classes`), and the figure this
        # case compares is unchanged by that.
        rows = sample_data.backbone_base_charge_codes(metered)
        if len(rows) == 1 and rows[0]["applies_to_customer_classes"] == []:
            # one unscoped code — both plans read the same figure
            assert Decimal(rows[0]["amount"]) == Decimal(res_base) == Decimal(com_base), service
            continue
        by_class = {
            plan_class: row["amount"]
            for row in rows
            for plan_class in ("residential", "commercial", "industrial")
            if row["applies_to_customer_classes"] == fixture.base_code_classes(
                plan_class, industrial_code_exists=(service == "electric")
            )
        }
        assert Decimal(by_class["residential"]) == Decimal(res_base), service
        assert Decimal(by_class["commercial"]) == Decimal(com_base), service
        if service == "electric":
            assert Decimal(by_class["industrial"]) == Decimal(fixture.INDUSTRIAL_ELECTRIC_BASE)


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE WATER TENANT IS UNMOVED — the case that matters most
# ══════════════════════════════════════════════════════════════════════════


def test_a_water_tenant_still_gets_its_three_schedules_unchanged(monkeypatch):
    """Every frozen figure this fixture reproduces is a WATER figure.

    GT-17 ❄️'s `$39.50` usage basis and `$15.80` sewer line stand on unit 0
    consuming exactly 8 kgal on these tiers. If this change had moved any of
    them it would have moved a finance-signed number, which needs a re-sign
    through HUMAN-GUIDE §6 and never a lane's edit.
    """
    payloads = _payloads(monkeypatch, *WATER_ESTATE)
    assert set(payloads) == {
        sample_data.SCHEDULE_WATER_RES,
        sample_data.SCHEDULE_WATER_COM,
        sample_data.SCHEDULE_WATER_FILING,
        sample_data.SCHEDULE_SEWER,
        sample_data.SCHEDULE_TRASH,
    }
    res = payloads[sample_data.SCHEDULE_WATER_RES]
    assert res["model"] == "tiered" and res["uom"] == fixture.WATER_UOM
    assert [t["unit_price"] for t in res["structure"]["tiers"]] == ["4.00", "6.50", "8.00"]
    assert payloads[sample_data.SCHEDULE_WATER_COM]["structure"]["unit_price"] == "5.20"
    # ⚠ `DEF-RAT-8812` — `40` (a price ratio) until `CR-081` (PO re-sign
    # 2026-09-08, *"C — factor 90%, rate $5.00"*): sewer is 90% of the water
    # VOLUME. Water's own figures above are untouched by it.
    assert payloads[sample_data.SCHEDULE_SEWER]["structure"]["percent"] == "90"
    assert payloads[sample_data.SCHEDULE_SEWER]["structure"]["percent_basis"] == "usage"
    assert payloads[sample_data.SCHEDULE_TRASH]["structure"]["unit_price"] == "15.00"


def test_water_declares_no_extra_base_charge_code_and_every_other_metered_service_does():
    """Water's own two base codes live in `BASE_CHARGE_CODES`, so it declares no
    extra one — and since `CR-062` C1 every OTHER metered service declares its
    own, on the same tenant.

    ⚠ **THIS CASE ASSERTED THAT THE ALL-TEN TENANT DECLARED NONE UNTIL
    2026-09-02, AND THE INVERSION IS THE FIX.** It was called
    `test_a_water_backbone_declares_no_extra_base_charge_code` and its reason
    was *"a utility that sells everything still gets ONE metered backbone —
    water — so electric and gas are ENABLED and PRICED NOWHERE"*. That was
    accurate and it is the defect the PO ruled out: a tenant selling electric
    got no electric base charge on any bill, which is `$12.00` × 48 units a
    month. Electric, gas and thermal now each get their code.

    **The `DEF-528` argument the old case was protecting is unchanged and is
    the reason this MUST move together with the schedules**: a base charge code
    is seeded for EVERY service this seed prices, or for none — a schedule whose
    service has no `is_base` code cannot activate, and the whole sample load
    dies behind it.
    """
    water = _estate(*WATER_ESTATE).primary
    assert water is not None and water.code == "water"
    assert sample_data.backbone_base_charge_codes(water) == ()

    all_ten = _estate(
        "electric", "water", "gas", "sewer", "trash", "storm_water", "solar", "broadband",
        "thermal_heat", "battery",
    )
    assert all_ten.primary is not None and all_ten.primary.code == "water"
    codes = [
        row["code"]
        for metered in all_ten.metered
        for row in sample_data.backbone_base_charge_codes(metered)
    ]
    # ⚠ **`BASE-TH` LEFT THIS LIST ON 2026-09-07 (`CR-080`)** — thermal is
    # capacity-billed now and its base code moved to `CAPACITY_BASE_CODE` with
    # its letters unchanged. The DEF-528 rule under test is untouched: every
    # METERED service the tenant sells still needs its own `is_base` code.
    # `BASE-E-IND` JOINED it on 2026-09-02 (`CR-062` J4, `DEF-RAT-8811`) — the
    # industrial plant's own electric base.
    assert codes == ["BASE-E", "BASE-E-COM", "BASE-E-IND", "BASE-G"], (
        "every metered service the tenant sells needs its own `is_base` code or its "
        f"schedule cannot activate (DEF-528). Found {codes}"
    )


def test_a_water_tenant_keeps_its_two_plan_descriptions_word_for_word(monkeypatch):
    """The sentences on `plans.description` are copy, and this is not a copy change."""
    payloads = _plan_rows(
        monkeypatch,
        {
            sample_data.SCHEDULE_WATER_RES: "01a04780-0000-7000-8000-000000000001",
            sample_data.SCHEDULE_WATER_COM: "01a04780-0000-7000-8000-000000000002",
            sample_data.SCHEDULE_SEWER: "01a04780-0000-7000-8000-000000000003",
            sample_data.SCHEDULE_TRASH: "01a04780-0000-7000-8000-000000000004",
        },
        *WATER_ESTATE,
    )
    by_code = {p["code"]: p for p in payloads}
    assert by_code[sample_data.PLAN_RESIDENTIAL]["description"] == (
        "Sample plan. Water on inclining tiers, sewer at 40% of the water "
        "usage charge, trash at $15.00 per cart with no monthly base."
    )
    assert by_code[sample_data.PLAN_COMMERCIAL]["description"] == (
        "Sample plan. Water at a flat rate per kgal, sewer at 40% of the water "
        "usage charge, trash at $15.00 per cart with no monthly base."
    )


def test_a_non_water_plan_says_in_plain_english_what_it_charges(monkeypatch):
    """B14 rule 32 — the description carries the figure and no rule id.

    *"no rule id or internal code in clerk-facing copy"*. The question and the
    defect ids live in `NOT_SEEDED` and in the module's docstrings, where an
    engineer reads them; the plan card says what the customer pays.
    """
    name = sample_data.backbone_schedule_name("electric")
    # DEF-RAT-9842 — electric's two classes pay different bases ($12.00 /
    # $48.00), and a schedule names ONE base code, so the commercial plan binds
    # its own electric schedule.
    com_name = sample_data.backbone_commercial_schedule_name("electric")
    payloads = _plan_rows(
        monkeypatch,
        {
            name: "01a04780-0000-7000-8000-000000000001",
            com_name: "01a04780-0000-7000-8000-000000000002",
        },
        "electric",
    )
    by_code = {p["code"]: p["description"] for p in payloads}
    assert "$12.00" in by_code[sample_data.PLAN_RESIDENTIAL]
    assert "$48.00" in by_code[sample_data.PLAN_COMMERCIAL]
    for description in by_code.values():
        assert "usage is not priced" in description
        for forbidden in ("OQ-", "BR-", "DEF-", "[W]"):
            assert forbidden not in description, (
                f"{forbidden!r} is an internal code and this is clerk-facing copy (B14 rule 32)"
            )


# ══════════════════════════════════════════════════════════════════════════
# 4 · THROUGH THE REAL SEEDER — the shape half, on a real tenant
# ══════════════════════════════════════════════════════════════════════════


def test_an_electric_tenant_seeds_a_published_plan_its_units_can_derive(
    growth_plan, audit_rows, settings
):
    """**The end of the chain this defect broke, without waiting for a bill run.**

    `metering._backfill_missing_unit_plans` resolves `sample_plan_id(SCW-RES)`
    and `create_account` refuses to activate on a planless unit (`BR-MET-040`).
    Before the fix that lookup returned `None` for every one of the 48 seats.

    RED PROVED FIRST — with `_schedule_payloads` restored to its three literals:

        AssertionError: an electric tenant has no sample residential plan, so
        every unit keeps rate_plan_id NULL and all 48 seats refuse at
        activation — that is DEF-2397
    """
    from apps.rating import models as rating_models

    # The plant runs INLINE, as it does on a real signup. Without it
    # `provision_tenant` enqueues the job on a broker the suite does not run and
    # the call dies on `Error 111 connecting to localhost:6379`, which says
    # nothing about this defect.
    settings.JOBS_EAGER = True

    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            subdomain="def2397-electric",
            name="DEF-2397 electric",
            services=["electric"],
            owner={
                "full_name": "Dana Whitfield",
                "email": "dana@def2397-electric.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    # ⚠ **NOTHING IS RE-SEEDED HERE AND THAT IS THE POINT.** With the plant
    # inline, `provision_tenant` has ALREADY run rating's block through the same
    # path a real signup takes, so the assertions below read what the PRODUCT
    # built for itself rather than what this test asked it to build — which is
    # the whole reason `DEF-2397` needed a live case and not a unit test.
    #
    # An earlier draft called `seed_sample_records(_owner_user(tenant))` again
    # and failed with `AuthError: AUTH-002` inside
    # `discount_sample_data._attach_sample_plan_discounts`: that replay reaches
    # `attach_discount_to_plan`, which is role-gated, and the first user by
    # `created_at` on a planted tenant is not necessarily an admin. The replay
    # added nothing this case asserts, so it is gone rather than propped up
    # with a hand-picked actor.
    with tenant_ctx(tenant):
        plan_id = sample_data.sample_plan_id(sample_data.PLAN_RESIDENTIAL)
        assert plan_id is not None, (
            "an electric tenant has no sample residential plan, so every unit keeps "
            "rate_plan_id NULL and all 48 seats refuse at activation — that is DEF-2397"
        )
        row = rating_models.RatePlan.objects.get(pk=plan_id)
        assert row.status == "published", (
            "the plan exists and is not published, so no unit may be assigned it — "
            "publish refuses a service with no schedule (rating.plans.service_without_schedule)"
        )
        services_on_plan = {
            item.service.code: item.base_charge
            for item in rating_models.PlanService.objects.filter(
                tenant_id=tenant.id, rate_plan_id=plan_id
            ).select_related("service")
        }
        assert set(services_on_plan) == {"electric"}
        assert services_on_plan["electric"] == Decimal("12.00"), (
            "the seeded residential electric base is not [W] §1's $12.00"
        )
        # BR-RAT-088 / DEF-528 — and the code agrees with the plan to the cent.
        # `DEF-RAT-8813` — `Charge.amount` is retired (`CR-156-BRC10`,
        # 2026-10-01), and for these codes it had answered None since
        # 356664845 (2026-09-07): electric's base is a LADDER, one row per
        # ratified size, whose SMALLEST rung is the anchor the plan states
        # (`base_size_amounts.size_amounts`, multiplier 1 by construction).
        # So the figure compared is that rung, read through `charge_prices`.
        from apps.rating import base_size_amounts, charge_prices
        from apps.tenancy import service_size_classes

        smallest = next(
            code
            for code, _name in service_size_classes.size_classes_for_service("electric")
            if base_size_amounts.multiplier("electric", code) == 1
        )
        base_codes = list(
            rating_models.Charge.objects.filter(tenant_id=tenant.id, is_base=True)
        )
        tables = charge_prices.resolved_tables(base_codes)

        def _anchor(charge):
            table = tables.get(charge.id, {})
            row = table.get(smallest) or table.get(charge_prices.ALL_SIZES)
            return row.amount if row is not None else None

        codes = {c.code: _anchor(c) for c in base_codes}
        assert codes.get("BASE-E") == Decimal("12.00"), codes
        assert codes.get("BASE-E-COM") == Decimal("48.00"), codes

