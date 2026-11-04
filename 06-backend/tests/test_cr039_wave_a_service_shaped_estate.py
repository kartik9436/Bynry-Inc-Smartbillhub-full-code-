# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S8, S62
# Change:   CR-039 wave A tasks 1 · 3 · 4 · 5 (the sample estate becomes
#           service-shaped · a submetering shape beside the municipal one ·
#           per-service reads · one tenant per realistic mix)
# Defect:   DEF-795 (high, deployed) — "SAMPLE METER READS DO NOT LAND ON NEW
#           TENANTS", reported by the PO on 2–3 real tenants
# Rules:    BR-MET-003 (a unit takes only services the tenant SELLS) ·
#           BR-MET-012/015/017/018 (stage → validate → disposition → atomic
#           commit; nothing inserts a read) · BR-MET-119 (a premises DECLARES
#           what is available at the address) · BR-AST-003 (a sub-meter
#           requires a meter parent) · BR-AST-009 (a measuring asset declares
#           its service AND an explicit UoM) · BR-AST-010 (a net meter is an
#           electricity arrangement) · BR-RAT-015 ❄️ (sewer = % of the WATER
#           usage charge) · BR-TEN-056/060/063 (the sample set · a gap is
#           NAMED · idempotent per tenant) · CLAUDE.md rule 1 (tenant scoping)
#           · rule 3 (consumption carries its unit)
# Tests:    this file
# Impacts:  core/sample_fixture.py · apps/metering/sample_data.py ·
#           apps/assets/sample_data.py · apps/tenancy/selectors.py
# ───────────────────────────────────────────────────────
"""CR-039 wave A — **the demo fits the utility that signed up.**

WHAT WAS WRONG, MEASURED
------------------------
The entire sample estate was `water · sewer · trash` in literals: 49 water
meters, three months of water reads. `apps/metering/sample_data._fixture_
services()` intersected that with the tenant's ENABLED services, so on an
**electric + gas** utility the intersection was EMPTY —

  · the premises block returned `0` ("Nothing this fixture prices is enabled"),
  · `seed_sample_reads` returned early on `if "water" not in enabled`,
  · `stage_read_batch` would have refused the batch anyway
    (`metering.service_not_enabled`), because its `service` tag said `water`.

So the utility signed up successfully and received NOTHING, the seeder was
behaving CORRECTLY at every step, and the whole failure was invisible: a run
that seeded 0 rows for a good reason looks exactly like a tenant that never
asked for sample data. That is DEF-795.

WHAT THIS FILE PROVES
---------------------
1. **The water tenant is unmoved.** Byte for byte: the same 49 serials, the
   same `kgal`, the same frozen 8 on the GT-17 reference unit. A change that
   made an electric tenant work by moving the water one would be a worse defect
   than the one it fixed.
2. **The estate now fits.** One tenant per realistic mix is PROVISIONED through
   the real `provision_tenant` → plant job → `seed_sample_data` path, and each
   is asserted to hold premises, units, meters and reads that COMMITTED — or an
   honest NAMED refusal where the mix genuinely cannot be seeded.
3. **The refusal is not weakened.** A tenant is still never given a service it
   does not sell; a solar-only utility gets a sentence saying why, not a
   premises claiming to receive water.
4. **A replay still writes nothing** (BR-TEN-063).

RED PROVED FIRST — every guard here, with the failure quoted at the assertion
that catches it. The mutations were made in the working tree, run, quoted and
reverted; no `# BREAK:` marker survives (DEF-666).
"""

from decimal import Decimal

import pytest

from apps.assets import models as assets_models
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import sample_data as tenancy_sample
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)
from tests.test_us_met_helpers import staff_actor

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# PART 1 · THE WATER TENANT IS UNMOVED — pure, no database
# ══════════════════════════════════════════════════════════════════════════
#
# These are the assertions that would have caught a "fix" that made the estate
# service-shaped by MOVING the estate everybody already has. They need no
# tenant, so they run in milliseconds and fail first.


def test_the_water_estate_is_byte_for_byte_what_it_was():
    """`meter_plan()` with no arguments is still the water estate.

    RED PROVED FIRST — with `SERVICE_METER_PREFIX["water"]` changed from `"W"`
    to `"WM"` (the kind of tidy-up a later lane would make), this said:

        AssertionError: the water estate MOVED: W-5000 became WM-5000. Every
        seeded tenant's registers are named by these serials and
        `seed_sample_reads` stages every row against them
        assert 'WM-5000' == 'W-5000'
    """
    meters = fixture.meter_plan()
    assert len(meters) == fixture.UNIT_COUNT + 1, (
        "48 meters, one per unit, plus the ONE replacement spec §4 case 3 needs"
    )
    assert meters[0]["asset_no"] == "W-5000", (
        f"the water estate MOVED: W-5000 became {meters[0]['asset_no']}. Every seeded "
        "tenant's registers are named by these serials and `seed_sample_reads` stages "
        "every row against them"
    )
    assert meters[47]["asset_no"] == "W-5047"
    assert meters[-1]["asset_no"] == "W-9011", "the case-3 replacement serial"
    assert meters[-1]["replaces"] == "W-5011"
    assert all(row["service"] == "water" for row in meters)
    assert all(row["uom"] == fixture.WATER_UOM == "kgal" for row in meters)


def test_the_frozen_gt17_consumption_survives_the_scaling():
    """`consumption()` defaults to water at scale 1 — GT-17 ❄️ does not move.

    RED PROVED FIRST — with `CONSUMPTION_SCALE["water"]` set to 10:

        AssertionError: unit 0 must consume exactly 8 kgal in june — that is
        GT-17's own consumption and $39.50/$15.80 stand on it
        assert Decimal('80') == Decimal('8')
    """
    for period in ("june", "july", "august"):
        assert fixture.consumption(fixture.CASE_REFERENCE_BILL, period) == Decimal("8"), (
            f"unit 0 must consume exactly 8 kgal in {period} — that is GT-17's own "
            "consumption and $39.50/$15.80 stand on it"
        )
        assert fixture.consumption(
            fixture.CASE_REFERENCE_BILL, period
        ) == fixture.water_consumption_kgal(fixture.CASE_REFERENCE_BILL, period)


def test_a_water_tenant_still_leads_with_water_and_now_keeps_its_electric():
    """`estate_plan` on a water utility puts WATER FIRST, and every other
    metered service the tenant sells is seeded beside it.

    ⚠ **THIS CASE WAS `test_a_water_tenant_resolves_exactly_the_old_intersection`
    AND IT ASSERTED THAT ELECTRIC WAS REFUSED — `CR-062` C1/C2, 2026-09-02.** It
    read `plan.services == ("water", "sewer", "trash") == fixture.
    FIXTURE_SERVICES` and `[code for code, _ in plan.refused] == ["electric"]`,
    which was true, deliberate and exactly the thing the PO ruled out: a utility
    selling electric received 95 bills with no electric line on any of them, not
    even its `$12.00` monthly base (`DEF-3224`). *"this is not correct - you
    cannot drop electricty or gas"*.

    **What is NOT weakened is what the old case was protecting**: water is still
    FIRST, because every ❄️ frozen figure this fixture reproduces is a water
    figure and `plan.primary` is what the awkward-case demonstrations and the
    plan's name hang on.

    RED PROVED FIRST — with `METERED_ESTATE_SERVICES` reordered to catalog order
    (`electric` first, which is how the platform seeds them):

        AssertionError: a tenant that sells water must lead with WATER — every
        signed figure this fixture reproduces is a water figure
        assert 'electric' == 'water'
    """
    plan = fixture.estate_plan(
        ["electric", "water", "sewer", "trash"],
        {"electric": "kWh", "water": "kgal", "sewer": None, "trash": "month"},
    )
    assert plan.primary is not None and plan.primary.code == "water", (
        "a tenant that sells water must lead with WATER — every signed figure this "
        "fixture reproduces is a water figure"
    )
    assert plan.primary.uom == "kgal"
    assert plan.metered_codes == ("water", "electric")
    assert plan.services == ("water", "electric", "sewer", "trash")
    assert plan.refused == (), (
        "CR-062 C2 — no metered service is refused for being second any more: "
        f"{plan.refused!r}"
    )


def test_a_service_with_no_declared_unit_is_reported_and_never_guessed():
    """CLAUDE.md rule 3 has no "assume kWh" branch.

    A tenant that enables a METERED service and declares no unit for it must be
    TOLD, not handed a meter with a blank UoM — metering's own validation errors
    `unit_missing` on exactly that row.

    RED PROVED FIRST — with `estate_plan` falling back to `"unit"` when the
    tenant declares none:

        AssertionError: gas has no declared unit, so it gets no register — a
        meter would be created with a guessed UoM
        assert ('gas',) == ()

    ⚠ **THE EXEMPLAR WAS `thermal_heat` UNTIL 2026-09-07 AND IT HAD TO CHANGE,
    WHICH IS WORTH READING BEFORE ASSUMING THIS CASE WAS WEAKENED (`CR-080`).**
    The PO ruled thermal capacity-based on connected tonnage, so it no longer
    resolves a register at all and cannot demonstrate a REGISTER's missing unit:
    `estate_plan(["thermal_heat"], {})` is now a legitimate capacity rider with
    no refusal in it, which would have made this case pass for the wrong reason.
    `gas` carries exactly the same shape and is metered by the PO's own
    `BR-TEN-1180` table. **The rule under test — rule 3 has no "assume kWh"
    branch — is unchanged and is asserted on the same code path.**

    ⚠ **AND SINCE `CR-062` C1 THE REFUSAL IS PER SERVICE RATHER THAN PER
    ESTATE**, which is the second assertion below: a tenant selling water AND
    gas keeps its water meters and loses only gas, by name. Before this,
    whichever metered service came first decided the whole estate.
    """
    plan = fixture.estate_plan(["gas"], {"gas": None})
    assert plan.metered == (), (
        "gas has no declared unit, so it gets no register — a meter "
        "would be created with a guessed UoM"
    )
    reasons = dict(plan.refused)
    assert "gas" in reasons
    assert "no primary unit of measure" in reasons["gas"]

    # …and the same service WITH a unit is seedable, so the refusal is about the
    # missing unit and not about the service.
    assert fixture.estate_plan(["gas"], {"gas": "ccf"}).metered_codes == ("gas",)

    # CR-062 C1 — one service refused, the rest of the estate intact.
    mixed = fixture.estate_plan(["water", "gas"], {"water": "kgal", "gas": None})
    assert mixed.metered_codes == ("water",)
    assert [code for code, _why in mixed.refused] == ["gas"]


def test_sewer_without_water_is_refused_by_name_not_seeded_priceless():
    """BR-RAT-015 ❄️ prices sewer as 40% of the WATER usage charge.

    RED PROVED FIRST — with the water guard removed:

        AssertionError: a sewer service point on a tenant with no water has no
        basis to take a percentage of
        assert 'sewer' not in ('electric', 'sewer')
         +  where ('electric', 'sewer') = EstatePlan(metered=[MeteredService(
            'electric', 'kWh', x1)], companions=('sewer',), refused=[]).services

    ⚠ **THE GUARD CHANGED SHAPE WITH `CR-062` C1 AND THE RULE DID NOT.** It read
    `backbone != "water"` — identity with the estate's single metered service.
    Water is no longer *the* backbone, so the test is now MEMBERSHIP: sewer needs
    water to be one of the metered services. On every shape that sells water it
    is the same answer it always was, and on `electric + sewer` it is still a
    refusal.
    """
    plan = fixture.estate_plan(["electric", "sewer"], {"electric": "kWh", "sewer": None})
    assert "sewer" not in plan.services, (
        "a sewer service point on a tenant with no water has no basis to take a "
        "percentage of"
    )
    assert "BR-RAT-015" in dict(plan.refused)["sewer"]


def test_the_submetering_hierarchy_is_service_shaped():
    """CR-039 A3 — a submetering utility that sells ELECTRICITY gets an
    electric master with electric sub-meters behind it.

    Before this, `MASTER_METER` and `master_sub_meter_plan()` said `water` in a
    literal, and `apps/assets/sample_data._seed_cr028_r10_shape` skips (rightly)
    any row naming a service the tenant has not enabled — so the whole
    submetering story was missing on the one kind of tenant this product is
    built for.

    RED PROVED FIRST — with `master_meter()` ignoring its `service` argument:

        AssertionError: the master must speak the tenant's own service or the
        asset seeder skips it and a submetering utility gets no master at all
        assert 'water' == 'electric'
    """
    master = fixture.master_meter("electric", "kWh")
    assert master["service"] == "electric", (
        "the master must speak the tenant's own service or the asset seeder skips it "
        "and a submetering utility gets no master at all"
    )
    assert master["uom"] == "kWh"
    assert master["meter_type"] == "master"
    assert master["asset_no"] == fixture.MASTER_METER["asset_no"]

    subs = fixture.master_sub_meter_plan("electric", "kWh")
    assert len(subs) == 3
    assert all(row["parent_asset_no"] == master["asset_no"] for row in subs), (
        "BR-AST-003 — every one of these is parented ON THE MASTER; that is what "
        "makes it a submetering estate rather than three loose meters"
    )
    assert all(row["service"] == "electric" and row["uom"] == "kWh" for row in subs)
    # …and the per-unit subs move with them, or the block is half-shaped.
    assert all(
        row["service"] == "electric" and row["parent_asset_no"].startswith("E-")
        for row in fixture.sub_meter_plan("electric", "kWh")
    )
    # The default call is still the water shape every existing tenant holds.
    assert fixture.master_meter() == fixture.MASTER_METER


def test_the_net_meter_keeps_its_own_service_and_is_not_reshaped():
    """BR-AST-010: a net meter is an ELECTRICITY arrangement, not a shape.

    A gas utility has no net meter, and the asset seeder skipping `M-NET-01` by
    name on one is the right answer. Re-expressing it in gas would invent a
    device that does not exist.
    """
    plan = fixture.cr028_asset_plan("gas", "therm")
    net = next(row for row in plan if row["asset_no"] == "M-NET-01")
    assert net["service"] == "electric"
    assert net["uom"] == "kWh"


# ══════════════════════════════════════════════════════════════════════════
# PART 2 · ONE TENANT PER REALISTIC MIX — the deliverable that closes DEF-795
# ══════════════════════════════════════════════════════════════════════════

#: `(subdomain, services at signup, expected FIRST metered service, its UoM)`.
#: `primary=None` means the mix has no register at all and the assertion flips
#: to an honest NAMED refusal — never to a silent zero.
#:
#: ⚠ **THE THIRD FIELD WAS `expected backbone` AND MEANT *the one service the
#: estate is metered in* UNTIL `CR-062` C1 (2026-09-02).** It now means the
#: FIRST of possibly several: an `electric + water` tenant seeds BOTH, and this
#: table pins the one that leads — the service that carries the case-3 swap, the
#: three unreadable meters, the disputed read and the plan's name (`CR-062`
#: judgment 4). The per-mix assertions below are written against that service's
#: own serials (`meter_plan(primary, uom)`), so they say nothing about the other
#: metered services and are unmoved; **what asserts the others is
#: `tests/test_cr062_c_every_metered_service_gets_its_meters.py`**, which is
#: where that change belongs.
MIXES: tuple[tuple[str, tuple[str, ...], str | None, str | None], ...] = (
    # The utility the fixture was written for. Nothing about it may move.
    ("crmix-water", ("water",), "water", "kgal"),
    # ⛔ THE DEFECT ITSELF: this tenant received NOTHING before CR-039.
    ("crmix-elec-gas", ("electric", "gas"), "electric", "kWh"),
    # The commonest signup shape in this repo's own test data
    # (`brazosbend_payload`) — water wins, and that is deliberate.
    ("crmix-elec-water", ("electric", "water"), "water", "kgal"),
    # The solar utility the CR says is being onboarded now. Solar has no estate
    # shape and no declared unit; electric carries the estate and solar is NAMED.
    ("crmix-solar", ("electric", "solar"), "electric", "kWh"),
    # All ten. Water LEADS — and since `CR-062` C1 electric, gas and thermal are
    # seeded beside it rather than refused for being second. Nothing is refused
    # on this tenant at all now: the four metered services all have declared
    # units and the six others ride as companions or capacity.
    (
        "crmix-all-ten",
        (
            "electric",
            "water",
            "gas",
            "sewer",
            "trash",
            "storm_water",
            "solar",
            "broadband",
            "thermal_heat",
            "battery",
        ),
        "water",
        "kgal",
    ),
    # An estate with NO REGISTER. ⚠ **THIS ROW MEANT "the honest refusal — a
    # utility selling ONLY services this fixture has no shape for" UNTIL
    # 2026-09-01 (`DEF-2396`).** Solar is a CAPACITY service under the PO's
    # `DEF-2409` ruling, so it now gets the full estate and no meter; `None`
    # here still means *no metered service*, which is exactly what it always
    # meant — what changed is that no register no longer implies no estate.
    ("crmix-solar-only", ("solar",), None, None),
)


def _estate_counts(tenant):
    """What a person opening this tenant would actually find."""
    with tenant_ctx(tenant):
        # ⚠ The asset's SERVICE is on its service point, not on the asset row —
        # `assets.selectors._service_of` reads it the same way, through the
        # reviewed cross-module FK (B2 §2). `unit` on the asset IS its UoM
        # (BR-AST-009 / CLAUDE.md rule 3), which is the thing this asserts.
        # An UNASSIGNED asset (the inventory spares) has no service point and
        # therefore no service — `None` is the right answer for those and they
        # are matched by serial rather than swept in by a prefix.
        meters = {
            no: (service, uom)
            for no, service, uom in assets_models.Asset.objects.filter(
                tenant_id=tenant.id, is_sample=True
            ).values_list("asset_no", "service_point__service__code", "unit")
        }
        # ⚠ Keyed by the METER the read is on, because `A-10432`'s two CR-030
        # demo meters (`M-4021` electric, `M-4022` water) are read on the same
        # tenant and are a different demo — a bare unit-set assertion would sweep
        # their kWh in beside the estate's kgal and read as a defect.
        reads = list(
            metering_models.MeterRead.objects.filter(
                tenant_id=tenant.id, is_sample=True
            ).values_list("asset__asset_no", "unit", "lifecycle")
        )
        return {
            "premises": metering_models.Premises.objects.filter(
                tenant_id=tenant.id, is_sample=True
            ).count(),
            "units": metering_models.Unit.objects.filter(
                tenant_id=tenant.id, is_sample=True
            ).count(),
            "meters": meters,
            "reads": reads,
            "runs": {
                row.module: (row.outcome, row.seeded_count, row.detail or "")
                for row in tenancy_models.SampleDataRun.objects.filter(tenant_id=tenant.id)
            },
            "master": assets_models.Asset.objects.filter(
                tenant_id=tenant.id, asset_no=fixture.MASTER_METER["asset_no"]
            )
            .values_list("service_point__service__code", "unit")
            .first(),
            "master_subs": assets_models.Asset.objects.filter(
                tenant_id=tenant.id,
                asset_no__in=[
                    row["asset_no"] for row in fixture.master_sub_meter_plan()
                ],
            ).count(),
        }


def test_cr039_a5__every_realistic_mix_gets_an_estate_or_a_named_refusal(
    growth_plan, identity_seam, audit_rows, settings
):
    """**THE DEFERRED DELIVERABLE OF DEF-795.** One tenant per realistic mix,
    provisioned through the real signup → plant path, each asserted to hold a
    usable estate.

    RED PROVED FIRST, TWICE, and the failures are quoted VERBATIM.

    **(A) The whole of DEF-795 restored** — `_fixture_services()` back to
    `FIXTURE_SERVICES ∩ enabled`, the premises block back to `return 0`, the
    reads block back to `if "water" not in enabled: return posted`, and the
    meters block back to building a water estate. The water row still passed;
    the electric+gas row said:

        AssertionError: crmix-elec-gas: assets reported failed —
        ValidationError: VAL-005 (metering.service_not_enabled)
        assert 'failed' == 'seeded'

    Read that carefully, because it is the defect's own shape: **metering
    reported `seeded` with ZERO rows** (the invisible half), and the meters
    block then hit the PRODUCT's own refusal trying to mint a WATER service
    point on a utility that sells electricity and gas. Nothing was broken; the
    fixture was simply speaking a language the tenant does not.

    **(B) Only the two refusals turned back into zeros** — so mixes 1–5 still
    passed and the solar-only row was the one that went red:

        >   assert ast_outcome == "failed" and "no meters were seeded" in ast_detail
        E   AssertionError: assert ('seeded' == 'failed'
        E     - failed
        E     + seeded)

    A block reporting `seeded` over a tenant with no estate is exactly what made
    DEF-795 invisible for as long as it was.
    """
    settings.JOBS_EAGER = True
    table: list[str] = []

    for subdomain, services, primary, uom in MIXES:
        tenant, result = provisioned_tenant(
            brazosbend_payload(
                subdomain=subdomain,
                name=f"CR-039 {subdomain}",
                services=list(services),
                owner={
                    "full_name": "Dana Whitfield",
                    "email": f"dana@{subdomain}.example.invalid",
                    "password": "S3cure!passw0rd",
                    "phone": None,
                },
            )
        )
        assert result["created"] is True, "the tenant OPENS regardless — C-15 is soft"
        found = _estate_counts(tenant)
        met_outcome, met_count, met_detail = found["runs"]["metering"]
        ast_outcome, _ast_count, ast_detail = found["runs"]["assets"]

        if primary is None:
            # ── an estate with NO REGISTER — `DEF-2396`, 2026-09-01 ────────
            #
            # ⚠⚠ **THIS BRANCH ASSERTED THE OPPOSITE UNTIL 2026-09-01 AND THE
            # INVERSION IS THE FIX.** It required metering to have FAILED with a
            # sentence naming solar, and `found["premises"] == 0`, because the
            # fixture had no estate shape for a capacity service. That refusal
            # was honest and it was the whole product for a solar utility: 0
            # premises, 0 units, 0 accounts, 0 bills, 14 of 17 seeding blocks
            # failed, measured on PostgreSQL 16.13. `DEF-2396`'s own row names
            # this very case as the reason nothing flagged it — *"asserts the
            # solar-only tenant gets a NAMED refusal and that assertion passes;
            # the refusal is the ratified behaviour and the gap is the
            # coverage."*
            #
            # **What is NOT weakened is the thing the old branch was protecting:
            # a premises claiming to receive a service the utility does not
            # sell.** Solar IS sold here, and the PO's `DEF-2409` ruling makes
            # it a CAPACITY service — priced by counting what is installed
            # (`BR-RAT-090`), with no dial — so the estate is made to FIT rather
            # than the refusal being relaxed. `primary is None` still means
            # exactly what it says: no metered service, therefore no meter and
            # no read, and the meters and reads blocks still refuse BY NAME.
            # ⚠ **`met_outcome` IS THE MODULE'S WORST BLOCK, NOT THE PREMISES
            # BLOCK, so it is still `failed` here and that is CORRECT.** Three
            # of metering's blocks read REGISTERS and a capacity service has
            # none, so they refuse honestly — exactly as they do on the
            # trash-only tenant that bills 96 invoices with 8 of 17 blocks
            # failed. **The estate is what is asserted, and it is asserted by
            # COUNTING ROWS**; a first draft asserted `met_outcome == "seeded"`
            # and went red on the reads block's honest refusal, which would have
            # been a check that cannot tell success from failure.
            assert "no premises were seeded" not in met_detail, (
                f"{subdomain}: the PREMISES block must not be the one refusing — a "
                f"capacity utility receives an estate. It said: {met_detail!r}"
            )
            assert found["premises"] >= fixture.PREMISES_COUNT, (
                f"{subdomain} received {found['premises']} premises — DEF-2396 is a "
                "solar/broadband/battery/thermal utility getting an EMPTY product"
            )
            assert found["units"] >= fixture.UNIT_COUNT

            # …and the register half still refuses, BY NAME and for the RIGHT
            # reason. The sentence used to end *"the tenant has no enabled
            # service at all"*, which is false for this tenant and was already
            # false for a trash-only one; `EstatePlan.no_register_reason` now
            # says which services are priced without a register and that this is
            # correct rather than a fault (BR-TEN-060).
            assert ast_outcome == "failed" and "no meters were seeded" in ast_detail
            assert "priced WITHOUT a register" in ast_detail, (
                f"{subdomain}: the meters block must say WHY there is no meter, and the "
                f"reason must be true. It said: {ast_detail!r}"
            )
            assert "no enabled service at all" not in ast_detail, (
                f"{subdomain}: this utility HAS an enabled service — a refusal naming a "
                "cause that is not true sends the reader to Settings to switch on a "
                "service that is already on"
            )
            assert not found["meters"], (
                f"{subdomain}: a capacity service has no register, so no meter may be "
                f"planted for it — found {sorted(found['meters'])[:5]}"
            )
            table.append(
                f"{subdomain:18} {'+'.join(services):28} "
                f"NO-REGISTER estate — {found['premises']} premises, 0 meters"
            )
            continue

        # ── a usable estate ───────────────────────────────────────────────
        assert met_outcome == "seeded", (
            f"{subdomain}: metering reported {met_outcome} — {met_detail}"
        )
        assert ast_outcome == "seeded", f"{subdomain}: assets reported {ast_outcome} — {ast_detail}"
        assert found["premises"] >= fixture.PREMISES_COUNT, (
            f"{subdomain} ({'+'.join(services)}) received NOTHING — this is DEF-795 "
            "exactly: an electric+gas utility signs up successfully and the seeder "
            "correctly refuses to plant a water estate it does not sell"
        )
        assert found["units"] >= fixture.UNIT_COUNT

        # ⚠ **ASKED OF THE FIRST METERED SERVICE'S OWN SERIALS, so this block
        # says nothing about the other metered services a `CR-062` tenant now
        # receives.** That is deliberate: the prefix separates them
        # (`W-5000 …` beside `E-5000 …`), the case-3 swap is the first
        # service's alone (judgment 4), and the plural estate is asserted in
        # `tests/test_cr062_c_every_metered_service_gets_its_meters.py`.
        prefix = fixture.SERVICE_METER_PREFIX[primary]
        wanted = [row["asset_no"] for row in fixture.meter_plan(primary, uom)]
        assert wanted[0] == f"{prefix}-5000"
        landed = {no: found["meters"][no] for no in wanted if no in found["meters"]}
        assert len(landed) == len(wanted), (
            f"{subdomain}: {len(landed)} of {len(wanted)} {primary} meters landed "
            f"(expected {prefix}-5000 … {prefix}-5047 plus the case-3 replacement)"
        )
        assert {service for service, _u in landed.values()} == {primary}
        assert {u for _s, u in landed.values()} == {uom}, (
            f"{subdomain}: CLAUDE.md rule 3 — every meter carries its own explicit "
            f"unit, and it must be the tenant's OWN declared {primary} unit ({uom}), "
            f"found {sorted({u for _s, u in landed.values()})}"
        )
        estate_meters = landed

        # Reads that COMMITTED. Nothing writes `meter_reads` outside
        # `commit_read_batch` (BR-MET-012/018), so a row here IS a committed
        # read — and its unit is the backbone's, never a bare number (rule 3).
        estate_reads = [row for row in found["reads"] if row[0] in set(wanted)]
        assert len(estate_reads) > fixture.UNIT_COUNT, (
            f"{subdomain}: the reads block landed {len(estate_reads)} reads on the "
            "estate's own meters. Three months plus an opening baseline over 48 meters "
            "is what the fixture declares; this is the count DEF-795 reported as ZERO"
        )
        # ⚠ **THIS ASSERTED `lifecycle == "committed"` AND HAD BEEN RED ON THE
        # BRANCH FOR AN UNKNOWN LENGTH OF TIME — `DEF-3261`, found while running
        # the file in full for `CR-062` and PROVED PRE-EXISTING in a clean
        # detached worktree at `81c007c4`, the tip before that lane's first
        # code commit.** `committed` is not where a read STAYS: `metering.models
        # .READ_LIFECYCLES` is `("committed", "billed")` and `BR-MET-053`'s own
        # comment reads *"staged → ok/flagged/estimated → committed → BILLED"*,
        # so a read the bill run has consumed is LOCKED in `billed`. The seeded
        # plant bills June and July, so on `crmix-water` **95 of 189** reads on
        # `W-5000 …` were `billed` and the case called every one of them a
        # fault.
        #
        # **What the case was protecting is unchanged and is still refused:**
        # `staged`, `flagged` and `estimated` — a row that reached `meter_reads`
        # without going through `commit_read_batch` (BR-MET-012/018).
        #
        # ⚠ **AND THE MESSAGE NAMES THE ROWS NOW.** It was a bare `all()` over a
        # generator, so a red run could print only `assert False` and the repr
        # of a generator object — no mix, no serial, no lifecycle. A check whose
        # output cannot tell one cause from another is the shape CLAUDE.md law
        # 11 already records twice for git checks, met here in a test.
        LAWFUL_AFTER_COMMIT = {"committed", "billed"}
        unposted = [
            (no, lifecycle)
            for no, _u, lifecycle in estate_reads
            if lifecycle not in LAWFUL_AFTER_COMMIT
        ]
        assert not unposted, (
            f"{subdomain}: {len(unposted)} of {len(estate_reads)} reads on the estate's "
            f"own {primary} meters are neither committed nor billed — {unposted[:6]}. "
            "Nothing writes a `meter_reads` row outside `commit_read_batch` "
            "(BR-MET-012/018), so a row here IS a posted read"
        )
        assert {u for _n, u, _l in estate_reads} == {uom}, (
            f"{subdomain}: CLAUDE.md rule 3 — every consumption travels with its unit, "
            f"and on this tenant that unit is {uom}"
        )

        # CR-039 A3 — the submetering shape, in the tenant's own service.
        assert found["master"] == (primary, uom), (
            f"{subdomain}: the master meter is {found['master']}, not ({primary}, "
            f"{uom}) — a submetering utility must get a master it can actually read"
        )
        assert found["master_subs"] == 3, (
            f"{subdomain}: {found['master_subs']} of 3 sub-meters landed behind the "
            "master (BR-AST-003)"
        )

        table.append(
            f"{subdomain:18} {'+'.join(services):28} first={primary:11} uom={uom:6} "
            f"premises={found['premises']:3} units={found['units']:3} "
            f"meters={len(estate_meters):3} reads={len(estate_reads):4} master=ok"
        )

    print("\n── CR-039 wave A · per-mix estate ──")
    for line in table:
        print(line)


def test_cr039_a5__a_replay_on_a_reshaped_estate_still_writes_nothing(
    growth_plan, identity_seam, audit_rows, settings
):
    """BR-TEN-063 — the blocks stay insert-what-is-missing after CR-039.

    The parameterisation moved every asset number and every staged read row, so
    the idempotency guards (asset number, premises address, read date) had to
    keep keying on values that still exist. A replay that re-seeded would double
    a utility's demo estate.

    ⚠ **RED PROVED FIRST, AND THE FIRST VERSION OF THIS TEST WAS VACUOUS — the
    proof is what found it.** With `_seed_cr028_r10_shape`'s `if entry
    ["asset_no"] in existing: continue` removed, the counts were EXPECTED to
    double and the test was expected to say so. It **passed**:

        1 passed, 8 deselected in 120.65s

    …because the duplicate never reaches the database: `create_asset` refuses
    the second `M-MASTER-01`, the block RAISES, the orchestrator catches it and
    the tenant keeps exactly the rows it had. The counts are identical either
    way, so a count-only assertion cannot tell "idempotent" from "crashed and
    rolled back" — which is DEF-182's lesson in a new place (*a check whose
    output cannot distinguish pass from fail is worse than no check, because it
    is trusted*).

    So this asserts the OUTCOMES as well as the counts. With the same mutation
    re-run against the strengthened test:

        AssertionError: a replay turned assets from seeded into failed —
        BR-TEN-063's idempotency is 'insert what is missing', not 'crash on the
        second run'. It said: BizError: BIZ-STATE (assets.asset_no_duplicate)
        assert 'failed' == 'seeded'
    """
    settings.JOBS_EAGER = True
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            subdomain="crmix-replay",
            name="CR-039 replay",
            services=["electric", "gas"],
            owner={
                "full_name": "Dana Whitfield",
                "email": "dana@crmix-replay.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    before = _estate_counts(tenant)
    assert before["runs"]["metering"][0] == "seeded"
    assert before["runs"]["assets"][0] == "seeded"
    with tenant_ctx(tenant):
        # ⚠ A REAL `users` ROW, not a SimpleNamespace with a made-up uuid. The
        # first version of this test used one, every metering service refused it
        # with `AuthError: AUTH-002`, and the replay's metering block failed on
        # EVERY run — which the count-only assertions could not see either. Same
        # lesson as the docstring's: assert the outcome, not only the total.
        tenancy_sample.seed_sample_data(staff_actor(tenant, "system_admin"))
    after = _estate_counts(tenant)

    # ── the OUTCOMES first: a replay must still SUCCEED ───────────────────
    # This is the half a count-only assertion cannot see (see the docstring):
    # a block that crashes on its second run leaves the counts untouched and
    # looks exactly like a block that correctly found nothing to do.
    for module in ("metering", "assets"):
        outcome, _count, detail = after["runs"][module]
        assert outcome == "seeded", (
            f"a replay turned {module} from seeded into {outcome} — BR-TEN-063's "
            "idempotency is 'insert what is missing', not 'crash on the second run'. "
            f"It said: {detail}"
        )

    assert len(after["meters"]) == len(before["meters"]), (
        f"a replay wrote {len(after['meters']) - len(before['meters'])} more asset(s) — "
        "BR-TEN-063 says a second run changes no count"
    )
    assert after["premises"] == before["premises"]
    assert after["units"] == before["units"]
    # ⚠ **AMENDED 2026-09-01 FOR `DEF-2397`, AND THE NUMBER IS PINNED RATHER
    # THAN RELAXED.** This read `== len(before["reads"])` and was TRUE BY
    # ACCIDENT: an `electric + gas` tenant could never get past accounts, so
    # `billing/seed_sample_correction` failed on every run with *"the account
    # whose June bill was over-read does not exist"* and no correction read was
    # ever written. With rating service-shaped the replay reaches accounts and
    # bills, and the fixture's own case-3 correction finally lands —
    # `apps.metering.services.correct_billed_read` SUPERSEDES the reading, which
    # is one new `meter_reads` row (BR-MET-053). Measured: **193 → 194**, and
    # the lifecycles move from all-`committed` to a mix carrying `billed`,
    # which is the bill run consuming them.
    #
    # **THE GUARANTEE THIS CLAUSE EXISTS FOR IS UNTOUCHED.** A reads block that
    # re-posted would write the whole staged set again — `+193`, not `+1` — and
    # that still fails here. So does a correction that stops being written, and
    # so does a second one appearing. The count is EXACT, which is what makes
    # it a check rather than a tolerance.
    assert len(after["reads"]) == len(before["reads"]) + 1, (
        f"a replay moved the read count by {len(after['reads']) - len(before['reads'])}. "
        "Exactly ONE new row is expected — the fixture's case-3 over-read correction, "
        "written by billing/seed_sample_correction once the tenant has accounts to "
        "correct against (DEF-2397). A re-post of the staged reads would be +193, and "
        "the period guard keys on the read DATE, which the service parameterisation "
        "must not have moved"
    )


