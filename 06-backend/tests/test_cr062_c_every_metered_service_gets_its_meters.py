# ── Trace ──────────────────────────────────────────────
# Change:  **CR-062 group C + H1** (2026-09-02). PO verbatim, statement (8),
#          after being shown from the code that a utility selling Electric +
#          Water + Sewer receives water and sewer and NO ELECTRIC LINE ON ANY
#          BILL: *"this is not correct - you cannot drop electricty or gas -
#          can you tell me what corrections you will ahve to do"*.
# Defect:  DEF-3224 (a service sold and absent from every bill) · DEF-3231
#          (the estate plants a storm-water METER for a service the PO ruled
#          capacity-based) · DEF-3223 (the PO's own signup shape had never
#          been measured).
# Rules:   BR-MET-143 as AMENDED 2026-09-02 (a factor PER METERED SERVICE, not
#          one) · BR-RAT-024 (the catalogue is TEN services) · BR-MET-003 (a
#          unit takes only services the tenant SELLS) · BR-RAT-015 ❄️ / GT-17
#          ❄️ (water $39.50, sewer $15.80 — PER LINE, so an added line moves
#          neither) · BR-TEN-060 (a gap is NAMED, never a silent zero) ·
#          CLAUDE.md rule 3 (a quantity carries its unit).
# Tests:   this file
# Impacts: core/sample_fixture.py · apps/assets/sample_data.py ·
#          apps/metering/sample_data.py · apps/rating/sample_data.py
# ───────────────────────────────────────────────────────
"""**A UTILITY THAT SELLS ELECTRIC AND WATER GETS BOTH ON ITS BILLS.**

WHAT WAS WRONG, MEASURED BEFORE THIS LANE STARTED
--------------------------------------------------
`core/sample_fixture.estate_plan` took the FIRST enabled service of
`METERED_ESTATE_SERVICES` as the estate's single backbone and refused every
later one by name (`_NOT_THE_BACKBONE`). Verified by running the pure function
on 2026-09-02::

    electric + water + sewer  ->  services = ('water', 'sewer')
    electric + gas            ->  services = ('electric',)

The refusal was honest, it was written down, and it was the whole product for
the most ordinary shape a small utility ticks. On PostgreSQL 16 that tenant
produced **95 issued invoices, 70 premises, 70 accounts and 0 of 17 failed
seeding blocks** — every count green — while **48 units × $12.00 of electric
base, $576.00 a month, was on no document at all.**

WHAT THIS FILE ASSERTS
----------------------
Two layers, deliberately, for the reason `test_service_billing_coverage`
already records: a pure case costs milliseconds and a live one costs a whole
provisioning, so anything decidable by the pure estate plan is decided there.

* **PART 1 (pure, no database)** — the plan speaks EVERY enabled metered
  service, each with its own unit and its own multiplier; no service is
  refused for being second; storm water is no longer given a register; and the
  fixture's own metered/capacity lists cannot contradict the seed map that
  says how each service is priced (that last one is `DEF-3231`'s own
  prevention line, asked as one assertion over two literals).
* **PART 2 (live, one provisioning)** — a tenant selling **electric + water +
  sewer** gets meters, readings and BILL LINES for both metered services, and
  `GT-17` ❄️ is unmoved on the same bill that now also carries electric.

RED PROVED FIRST (law 7), against the tree at this lane's base
--------------------------------------------------------------
Every case below was run before a line of the fix was written. The pure ones
failed like this::

    test_pure_the_estate_speaks_every_enabled_metered_service
      AttributeError: 'EstatePlan' object has no attribute 'metered'

…which is C3 working as intended — the field was RENAMED so that every caller
breaks loudly rather than quietly going on seeding one service. Read through
the OLD field instead, the same shape says::

    electric+water+sewer: the estate speaks ('water', 'sewer') and refuses
    ['electric'] — a metered service the tenant SELLS gets no register, no
    reading and no bill line

and the live case::

    a tenant selling electric + water + sewer has 0 electric meter(s): the
    fixture planted 49 water meters and refused electric with 'electric: the
    estate is metered in water. This fixture declares ONE register per unit…'

PROVED ON REAL POSTGRESQL 16 (CLAUDE.md law 14)
------------------------------------------------
The seeding blocks catch database errors and continue, which the in-memory
SQLite suite cannot judge::

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
    SBH_TEST_DB_NAME=test_sbh_cr062c \\
    .venv/bin/python -m pytest \\
        tests/test_cr062_c_every_metered_service_gets_its_meters.py --reuse-db

The pure layer needs no database and runs everywhere: `-k pure`.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.assets import models as asset_models
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import sample_data as tenancy_sample_data
from apps.tenancy.services import SERVICE_DEFAULT_UOMS
from core import sample_fixture as fixture

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

#: ⚠ **THERE IS DELIBERATELY NO MODULE-LEVEL `django_db` MARK.** Part 1 is a
#: pure function and needs no database; marking the module would make every
#: pure case pay for a test database it never reads, and the whole argument for
#: splitting the layers is that the cheap half fails first. The live cases carry
#: the mark themselves.
_live = pytest.mark.django_db


#: The PO's own shape, named once so the pure case and the live one cannot
#: drift into measuring two different utilities.
PO_SHAPE: tuple[str, ...] = ("electric", "water", "sewer")

#: The units the tenant declares for it — the platform's own seed map, never
#: retyped (the `_platform_catalogue` argument in `test_service_billing_
#: coverage`: a gate carrying its own copy of the list it polices goes green
#: the day the seed changes underneath it).
PO_SHAPE_UOMS: dict[str, "str | None"] = {
    code: SERVICE_DEFAULT_UOMS[code].primary for code in PO_SHAPE
}


# ══════════════════════════════════════════════════════════════════════════
# PART 1 · THE PURE LAYER — no database, milliseconds, fails first
# ══════════════════════════════════════════════════════════════════════════


def test_pure_the_estate_speaks_every_enabled_metered_service():
    """**C1 · the PO's shape gets a register for electric AND for water.**

    Order is asserted too, and it is `METERED_ESTATE_SERVICES`' own: water is
    first in that tuple deliberately, because every ❄️ frozen figure this
    fixture reproduces is a water figure. What changes with `CR-062` is that
    being second no longer means being dropped.
    """
    plan = fixture.estate_plan(list(PO_SHAPE), PO_SHAPE_UOMS)
    assert tuple(row.code for row in plan.metered) == ("water", "electric"), (
        f"the estate speaks {plan.services!r} and refuses "
        f"{[code for code, _why in plan.refused]!r} — a metered service the tenant "
        "SELLS gets no register, no reading and no bill line"
    )
    assert plan.services == ("water", "electric", "sewer")
    assert not plan.refused, f"nothing may be refused on this shape: {plan.refused!r}"


def test_pure_each_metered_service_carries_its_own_unit_and_factor():
    """**C1 · a unit and a multiplier PER service, not one for the estate.**

    `BR-MET-143` as amended: the factor reconciles ONE service's register unit
    with the unit that service is BILLED in, so a per-estate factor was always
    a category error — it just could not be seen while the estate held one
    register.
    """
    plan = fixture.estate_plan(list(PO_SHAPE), PO_SHAPE_UOMS)
    by_code = {row.code: row for row in plan.metered}
    assert by_code["water"].uom == "kgal"
    assert by_code["electric"].uom == "kWh"
    assert by_code["water"].multiplier == "1"
    assert by_code["electric"].multiplier == "1"
    # The FIRST metered service is what the awkward cases hang on (CR-062
    # judgment 4) and what names the plan. It is water here, as it always was.
    assert plan.primary is not None and plan.primary.code == "water"


def test_pure_no_service_is_refused_for_being_second():
    """**C2 · `_NOT_THE_BACKBONE` is withdrawn — the sentence is no longer
    true.**

    A refusal that said *"seeding a second metered service would double the
    ready-to-run billing month"* was a fixture-size argument, and the PO has
    overruled it: a utility that sells electric and sees no electric anywhere
    has a broken product, not a slow demo.
    """
    assert not hasattr(fixture, "_NOT_THE_BACKBONE"), (
        "the one-register refusal is withdrawn by CR-062 statement (8); leaving the "
        "sentence in the module invites the next lane to reinstate the rule it states"
    )
    all_metered = fixture.estate_plan(
        list(fixture.METERED_ESTATE_SERVICES),
        {code: SERVICE_DEFAULT_UOMS[code].primary for code in fixture.METERED_ESTATE_SERVICES},
    )
    assert tuple(row.code for row in all_metered.metered) == fixture.METERED_ESTATE_SERVICES
    assert not all_metered.refused


def test_pure_storm_water_is_no_longer_given_a_register():
    """**C9 · `DEF-3231` closed — storm water is CAPACITY, so it gets no meter.**

    The defect is that `core/sample_fixture` gave storm water a register (and
    an `SD-` serial, and three months of readings) while
    `apps/tenancy/services.SERVICE_DEFAULT_UOMS` seeds it
    `billing_basis=capacity` per the PO's ruling of 2026-09-02 — so the demo
    tenant contradicted its own declaration and the run priced it by an asset
    count the fixture never planted.
    """
    assert "storm_water" not in fixture.METERED_ESTATE_SERVICES
    assert "storm_water" in fixture.CAPACITY_ESTATE_SERVICES
    assert "storm_water" in fixture.UNMETERED_ESTATE_SERVICES
    assert (
        "storm_water" not in fixture.SERVICE_METER_PREFIX
    ), "the SD- meter prefix is withdrawn with the register it named"
    assert "storm_water" not in fixture.CONSUMPTION_SCALE, (
        "a consumption scale for a service that reads no register is a number "
        "describing a reading nobody takes"
    )
    plan = fixture.estate_plan(["storm_water"], {"storm_water": "ERU"})
    assert plan.metered == ()
    assert plan.services == ("storm_water",)
    assert not plan.refused


def test_pure_the_fixtures_lists_cannot_contradict_the_seed_map():
    """**`DEF-3231`'s own prevention line, as one assertion over two literals.**

    Quoted from the defect row: *"every service in
    core.sample_fixture.METERED_ESTATE_SERVICES must be seeded
    billing_basis=metered by SERVICE_DEFAULT_UOMS, and every service in
    CAPACITY_ESTATE_SERVICES must be seeded capacity. That is one assertion
    over two literals and costs milliseconds."*

    The two halves live in different modules — `core/sample_fixture` decides
    which services get a REGISTER, `apps/tenancy/services` decides how each is
    PRICED — and nothing compared them, which is why the contradiction
    survived eight days.
    """
    problems: list[str] = []
    for code in fixture.METERED_ESTATE_SERVICES:
        basis = SERVICE_DEFAULT_UOMS[code].basis
        if basis != tenancy_models.BILLING_BASIS_METERED:
            problems.append(f"{code} is given a register by the fixture and seeded {basis!r}")
    for code in fixture.CAPACITY_ESTATE_SERVICES:
        basis = SERVICE_DEFAULT_UOMS[code].basis
        if basis != tenancy_models.BILLING_BASIS_CAPACITY:
            problems.append(f"{code} rides as capacity in the fixture and is seeded {basis!r}")
    assert not problems, "the fixture and the seed map disagree: " + "; ".join(problems)


def test_pure_the_awkward_cases_stay_on_the_first_metered_service_only():
    """**C8 · judgment 4 — three copies of one story makes the demo harder to
    read, not richer.**

    The three unreadable meters, the one disputed read and the one replaced
    meter are demonstrations, not coverage. They stay on `plan.primary`, and
    this case pins that the fixture plants exactly ONE replacement chain per
    service rather than one per service on every estate.
    """
    plan = fixture.estate_plan(list(PO_SHAPE), PO_SHAPE_UOMS)
    assert plan.primary is not None
    assert fixture.replacement_meter_no(plan.primary.code) == "W-9011"
    water = [row for row in fixture.meter_plan("water", "kgal") if row.get("replaces")]
    assert len(water) == 1, "the replacement case is one chain, and it is the first service's"


# ══════════════════════════════════════════════════════════════════════════
# PART 2 · THE LIVE RUN — one provisioning of the PO's own shape
# ══════════════════════════════════════════════════════════════════════════


def _payload(slug: str, services: list[str]) -> dict:
    data = dict(brazosbend_payload())
    data["subdomain"] = slug
    data["name"] = f"CR-062 C {slug}"
    data["services"] = services
    owner = dict(data["owner"])
    owner["email"] = f"owner@{slug}.test"
    data["owner"] = owner
    return data


def _plant(services: list[str]):
    """A tenant provisioned through the REAL signup service, then planted.

    The actor is the provisioning OWNER and not `admin_actor()` — `DEF-2722`'s
    trap: an invented uuid is stripped by `tenancy.sample_data._attributed`,
    `BR-BIL-058`'s release gate then refuses to issue anything, and every money
    block fails for a reason that has nothing to do with this change.
    """
    tenant, result = provisioned_tenant(_payload(f"cr062c-{uuid.uuid4().hex[:10]}", services))
    owner_id = result["owner_user_id"]
    actor = SimpleNamespace(
        id=uuid.UUID(str(owner_id)),
        pk=uuid.UUID(str(owner_id)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )
    with tenant_ctx(tenant):
        summary = tenancy_sample_data.seed_sample_data(actor)
    return tenant, actor, summary


@pytest.fixture(scope="module")
def po_shape_tenant(django_db_setup, django_db_blocker):
    """ONE planted electric + water + sewer utility for the whole file — the
    plant is minutes, not seconds, and every case reads the same end state."""
    with django_db_blocker.unblock():
        yield _plant(list(PO_SHAPE))


@_live
@requires_postgres
def test_live_both_metered_services_get_their_meters(po_shape_tenant):
    """**C4 · 48 meters PER metered service, and the serials do not renumber.**

    Water keeps `W-5000 … W-5047` plus the `W-9011` replacement — the numbers
    every existing tenant already carries and `test_us_ten_019_sample_records`
    pins. Electric arrives beside it as `E-5000 …`, which is what
    `meter_no(service, index)` has been able to produce since CR-039 wave A and
    what nothing ever asked it for.
    """
    tenant, _actor, _summary = po_shape_tenant
    with tenant_ctx(tenant):
        # ⚠ `Asset.type` is a FOREIGN KEY to `asset_types`, so it is matched by
        # the type's own `code` — `type="meter"` asks Django to read the string
        # as a uuid and raises. Found by running this file, not by reading it.
        serials = set(
            asset_models.Asset.objects.filter(
                tenant_id=tenant.id, type__code="meter", is_sample=True
            ).values_list("asset_no", flat=True)
        )
    assert "W-5000" in serials and "W-5047" in serials and "W-9011" in serials
    assert "E-5000" in serials and "E-5047" in serials, (
        "a tenant selling electric + water has "
        f"{len([s for s in serials if s.startswith('E-')])} electric meter(s); the "
        "fixture planted only the first metered service"
    )
    # ⚠ **COUNTED AGAINST THE ESTATE'S OWN PLAN, NOT BY PREFIX.** A prefix count
    # sweeps in the inventory spares (`W-5100` / `W-5101`) and the CR-028
    # registry shapes, which are different demonstrations on the same service
    # and are NOT what this case is about — measured: 51 serials started `W-`
    # where the estate declared 49, before the estate grew to 50 units.
    water = {row["asset_no"] for row in fixture.meter_plan("water", "kgal")}
    electric = {
        row["asset_no"]
        for row in fixture.meter_plan("electric", "kWh", replacement=False)
    }
    # ⚠ **49 → 51 AND 48 → 50 ON 2026-09-02 (`CR-062` addendum J3/J4).** The
    # estate gained a municipal building and an industrial plant, both APPENDED,
    # so every existing serial is where it was and the two counts are one meter
    # per unit (+1 for the water replacement) over a 50-unit estate. Written
    # against `fixture.UNIT_COUNT` so the next seat moves them by itself.
    assert len(water) == fixture.UNIT_COUNT + 1 == 51 and water <= serials, (
        f"{len(water - serials)} of the estate's {fixture.UNIT_COUNT + 1} water "
        f"meters are missing: {sorted(water - serials)[:5]}"
    )
    assert len(electric) == fixture.UNIT_COUNT == 50 and electric <= serials, (
        f"{len(electric - serials)} of the estate's {fixture.UNIT_COUNT} electric "
        f"meters are missing: {sorted(electric - serials)[:5]}"
    )
    # C8 — the replacement chain is the FIRST metered service's demonstration
    # only, so no `E-9011` was ever planted.
    assert fixture.replacement_meter_no("electric") not in serials


@_live
@requires_postgres
def test_live_both_metered_services_get_their_readings(po_shape_tenant):
    """**C6/C7 · readings per metered service, in one batch per service.**"""
    tenant, _actor, _summary = po_shape_tenant
    with tenant_ctx(tenant):
        by_service: dict[str, int] = {}
        for row in metering_models.MeterRead.objects.filter(
            tenant_id=tenant.id, is_sample=True
        ).select_related("asset"):
            prefix = str(row.asset.asset_no).split("-")[0]
            by_service[prefix] = by_service.get(prefix, 0) + 1
        # ⚠ The batch model is `ReadImportBatch` and its `service` is the batch
        # TAG — a plain text column, not a foreign key — which is the very thing
        # `stage_read_batch` validates against the tenant's enabled set. The
        # fixture's own batches are the ones it named `sample-<period>-<service>`.
        batch_services = sorted(
            {
                str(code)
                for code in metering_models.ReadImportBatch.objects.filter(
                    tenant_id=tenant.id, file_name__startswith="sample-"
                ).values_list("service", flat=True)
                if code
            }
        )
    assert by_service.get("W", 0) > 0
    assert by_service.get(
        "E", 0
    ), f"no electric reading was seeded; readings by serial prefix: {by_service}"
    assert "electric" in batch_services and "water" in batch_services, (
        f"C7 wants one read batch per service, tagged with that service: {batch_services}"
    )


@_live
@requires_postgres
def test_live_a_bill_carries_a_line_for_every_metered_service(po_shape_tenant):
    """**H1 · the statement (8) regression, and the assertion `DEF-3224` asks
    for.**

    A count of invoices cannot see a missing service on those invoices. This
    reads the invoice LINES and asks which services are on them.
    """
    tenant, _actor, _summary = po_shape_tenant
    with tenant_ctx(tenant):
        on_bills = sorted(
            str(code)
            for code in billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, invoice__status="issued"
            )
            .values_list("service__code", flat=True)
            .distinct()
            if code
        )
        issued = billing_models.Invoice.objects.filter(
            tenant_id=tenant.id, status="issued"
        ).count()
    assert issued > 0, "the PO's shape produced no bills at all"
    for code in PO_SHAPE:
        assert code in on_bills, (
            f"a tenant selling {'+'.join(PO_SHAPE)} issued {issued} bill(s) and {code!r} is "
            f"on NONE of their lines. Lines were found for {on_bills}. That is DEF-3224's "
            "shape and a bill COUNT cannot see it"
        )


@_live
@requires_postgres
def test_live_gt17_is_unmoved_on_a_bill_that_now_carries_electric_too(po_shape_tenant):
    """**F5 · ❄️ GT-17 — water `$39.50`, sewer `$15.80` — on the SAME bill that
    gained an electric line.**

    This is the guard the whole change rests on. `GT-17`'s reference bill is
    asserted as PER-LINE figures, not as a bill total, so adding an electric
    line ADDS a line and moves neither; sewer is 40% of the WATER charge, so it
    is unaffected too. If this case ever fails, the change STOPS — a frozen
    figure moves only by a finance re-sign (HUMAN-GUIDE §6), never by a lane.
    """
    tenant, _actor, _summary = po_shape_tenant
    with tenant_ctx(tenant):
        unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[
            fixture.CASE_REFERENCE_BILL
        ]
        unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
        account = customer_models.Account.objects.get(tenant_id=tenant.id, unit_id=unit.id)
        invoice = (
            billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=account.id)
            .order_by("period_start")
            .first()
        )
        assert invoice is not None, "the GT-17 reference account produced no bill"
        lines = list(
            billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, invoice_id=invoice.id
            ).select_related("service")
        )

    def total(service: str, kind: str) -> Decimal:
        return sum(
            (
                line.amount
                for line in lines
                if line.service_id is not None
                and line.service.code == service
                and line.kind == kind
            ),
            Decimal("0"),
        )

    assert total("water", "usage") == Decimal("39.50"), (
        "GT-17 ❄️ water usage is $39.50 (5 kgal × $4.00 + 3 kgal × $6.50) and this "
        "change may not move it"
    )
    assert total("sewer", "usage") == Decimal("15.80"), (
        "GT-17 ❄️ / BR-RAT-015 sewer is 40% of the WATER usage charge = $15.80"
    )
    # The whole point of the change, on the same document.
    assert any(
        line.service_id is not None and line.service.code == "electric" for line in lines
    ), "the reference bill still carries no electric line"


@_live
@requires_postgres
def test_live_the_seeding_blocks_all_ran(po_shape_tenant):
    """A seeded estate twice the size must not cost a single failed block.

    `BR-TEN-060` — a gap is NAMED, never a silent zero — so a block that could
    not run says why, and this case is what makes a new refusal visible instead
    of arriving as a quiet shortfall in the counts above.
    """
    tenant, _actor, _summary = po_shape_tenant
    with tenant_ctx(tenant):
        failed = [
            f"{row.get('module')}:{row.get('block')} — {(row.get('detail') or '')[:200]}"
            for row in tenancy_sample_data.stored_blocks()
            if row.get("outcome") not in ("seeded", "skipped")
        ]
    assert not failed, "seeding blocks failed:\n  " + "\n  ".join(failed)
