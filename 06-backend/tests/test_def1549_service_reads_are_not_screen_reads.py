# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-1549 (critical) — the asset import STILL times out after
#           DEF-1075: `service_default_uom` walks the whole S8 screen read PER
#           ROW, and the batched version it should have called already existed
# Rules:    BR-TEN-026 (the live active-account count the disable guard reads) ·
#           BR-AST-009 (a meter declares its service AND its explicit UoM) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 3 (a consumption
#           always carries its unit — so `None` stays a real answer here)
# Screens:  S8 Settings › Services (the read that was being walked) ·
#           WFL-01.meters.4 (the loop that was walking it)
# ───────────────────────────────────────────────────────
"""**A ONE-COLUMN QUESTION MUST NOT COST A WHOLE SCREEN.**

On 2026-08-27 the Product Owner's twenty-row meter import died a SECOND time
with `[CRITICAL] WORKER TIMEOUT (pid:44)`, hours after `DEF-1075` shipped a real
fix for the first N+1 on that path. The fix was real; it uncovered a larger one
behind it, which is the shape that makes a lane declare victory.

The chain, measured off the deployed traceback::

    _load_assets_rows              → per asset row
      _create_asset_inner:921
        seams.service_default_uom(service_code)          ← PER ROW
          metering/seams.py  for row in service_catalog()
            tenancy.services_overview()                  ← THE S8 SCREEN READ
              service_row(code)  FOR EVERY ACTIVE SERVICE
                customers.active_account_count(code)
                  seams.service_point_ref(point)         ← 2 QUERIES PER POINT

**20 rows × ~10 services × P service points.** Multiplicative, and none of it is
visible at test latency: measured on this harness before the fix, one call to
`service_default_uom("water")` cost **41 queries** — byte for byte the cost of
`services_overview()` itself — and the Product Owner's twenty-row file cost
**1,092 queries** on a tenant with NO service points at all. At 0.2 ms that is a
quarter of a second and every test passes. At 15–20 ms, with a real estate
behind `active_account_count`, it is minutes.

⚠ **THE CURE WAS ALREADY IN THE REPO AND THE CALL SITE NEVER MOVED ONTO IT.**
`DEF-324` diagnosed this exact mechanism one function along in August and built
`service_default_uoms()` — whose own docstring names the cost, *"~150 queries a
call"*. What was missing was the SINGULAR equivalent, so every per-row caller
kept reaching through the screen. `tenancy.selectors.service_default_uom` is
that missing equivalent.

**These are the checks that can see it.** A latency-shaped bug is invisible at
zero latency, so every assertion here counts QUERIES. The one in
`test_def1080_assets_commit_path.py` bounds the import end to end; these bound
the two reads underneath it, at the source, because both have callers beyond the
importer and a fix that only re-routed the importer would leave the next one
waiting.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import models as customers_models, services as customers_services
from apps.metering import models as metering_models, seams as metering_seams
from apps.tenancy import models as tenancy_models, selectors as tenancy_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


#: How many service points the planted estate carries. Deliberately MODEST —
#: the defect is multiplicative, so twelve points are already enough to separate
#: a batched read from a per-point one by an order of magnitude, and a bigger
#: number would only make the suite slower for no extra evidence.
ESTATE_UNITS = 4
ESTATE_SERVICES = ("water", "sewer", "trash")


def plant_estate(tenant, *, units: int = ESTATE_UNITS, tag: str = "a") -> int:
    """A tenant that has CUSTOMERS — the condition the harness never had.

    ⚠ **THIS IS THE FIXTURE GAP THAT LET DEF-1549 SHIP.** Every existing
    assets-import test drives a tenant with no units, no accounts and no service
    points, so `active_account_count` read an EMPTY agreement list and cost one
    query instead of `1 + 2P`. The per-row explosion was therefore multiplied by
    zero in the only place anyone was measuring, and the guard that was watching
    passed all the way through a production outage.

    Written through the ORM rather than the services on purpose: this plants a
    SHAPE to measure, not a workflow to prove, and the services' own validation
    (premises owners, move-in dating, numbering series) would add fixture
    coupling to three other lanes' rules for no gain to what is asserted here.

    Returns the number of service points planted, so a caller can state the `P`
    its assertion is about instead of assuming it. `tag` keeps account numbers
    unique so one test can plant a SECOND estate on the same tenant — which is
    how the flatness checks below compare two estate sizes rather than trusting
    a threshold.
    """
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line=f"1408 Elm St {tag}", city="Ottumwa", state="IA"
    )
    status = customers_models.AccountStatus.objects.filter(
        tenant=tenant, behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES
    ).first()
    assert status is not None, "the tenant has no occupying account status seeded"
    account_type = customers_models.AccountType.objects.first()
    points = 0
    for index in range(units):
        unit = metering_models.Unit.objects.create(
            tenant=tenant, premises=premises, label=f"Unit {tag}{index}"
        )
        account = customers_models.Account.objects.create(
            tenant=tenant,
            unit=unit,
            account_no=f"A-9{tag}{index:04d}",
            status=status,
            account_type=account_type,
        )
        for code in ESTATE_SERVICES:
            service = tenancy_models.Service.objects.filter(code=code, active=True).first()
            if service is None:  # pragma: no cover - the seed carries all ten
                continue
            point = metering_models.ServicePoint.objects.create(
                tenant=tenant, unit=unit, service=service
            )
            customers_models.ServiceAgreement.objects.create(
                tenant=tenant, account=account, service_point=point, started_on="2026-01-01"
            )
            points += 1
    return points


@pytest.fixture()
def ottumwa(growth_plan, identity_seam):  # noqa: F405
    """The Product Owner's own tenant: Water · Sewer · Trash."""
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Ottumwa Water Works",
            subdomain="ottumwa-water-works",
            services=list(ESTATE_SERVICES),
            owner={
                "full_name": "Ops Owner",
                "email": "owner@ottumwa-water-works.test",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    return tenant


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE SINGULAR LOOKUP IS A LOOKUP, NOT A SCREEN
# ══════════════════════════════════════════════════════════════════════════
def test_def1549__service_default_uom_costs_one_query_not_a_screen(ottumwa):
    """One service's unit in ONE query — and the ceiling is the SCREEN's own
    measured cost, never a number typed here.

    ⚠ **THE BOUND IS COMPUTED LIVE, FOR THE REASON DEF-1075's GUARD STATES:** a
    hand-written budget goes red for benign reasons and earns a `noqa` instead
    of a fix. So this measures `services_overview()` — the read that was being
    walked — in the same tenant, in the same test, and asserts the lookup costs
    a small fraction of it. If the screen gets cheaper the bound moves with it
    and the test keeps meaning the same thing.

    **RED before the fix, and by a mile:** `service_default_uom("water")` cost
    **41 queries** against a `services_overview()` of **41** — a ratio of 1.0,
    because it WAS the screen read.
    """
    with tenant_ctx(ottumwa):
        plant_estate(ottumwa)
        with CaptureQueriesContext(connection) as screen:
            tenancy_selectors.services_overview()
        with CaptureQueriesContext(connection) as lookup:
            unit = metering_seams.service_default_uom("water")

    print(
        f"\nDEF-1549 lookup cost: service_default_uom('water') = {len(lookup)} queries, "
        f"services_overview() = {len(screen)}"
    )
    assert unit is not None, "the seeded water service declares a unit; None would hide the cost"
    assert len(lookup) <= 2, (
        f"service_default_uom('water') issued {len(lookup)} queries. It answers ONE column of "
        "ONE row and must be a lookup, not a walk."
    )
    #: The relationship that IS the defect, stated as an assertion: asking for
    #: one service's unit must not approach the cost of drawing every service.
    assert len(lookup) * 8 < len(screen), (
        f"service_default_uom('water') cost {len(lookup)} queries against a services_overview() "
        f"of {len(screen)} on the same tenant. Before DEF-1549 those two numbers were EQUAL (41 "
        "and 41), because the lookup reached through the screen read. At 15 ms a round trip, "
        "paid once per import row, that is the gunicorn WORKER TIMEOUT the Product Owner saw."
    )


def test_def1549__service_default_uom_still_answers_for_a_switched_off_service(ottumwa):
    """⚠ **THE SEMANTIC GUARD, AND IT IS THE REASON THIS FIX IS NOT ONE LINE.**

    The obvious repair — point the singular at `service_default_uoms()` — is
    WRONG, and silently so. The plural filters `enabled=True`; the walk it
    replaces did not, because `service_row` reports the stored `primary_uom` of
    a present-but-off `tenant_services` row (New mandate 4 gives every catalog
    service a row at provisioning). A tenant who switches a service off still
    has meters on it, and narrowing the lookup would turn every one of their
    reads into a `unit_missing` refusal — a regression wearing a speed-up's
    clothes, found by no performance check anywhere.

    So: switched OFF, unit still answered. The plural, asked the same question,
    correctly says nothing — and that difference is the whole point.
    """
    with tenant_ctx(ottumwa):
        row = tenancy_models.TenantService.objects.get(
            tenant=ottumwa, service__code="water", enabled=True
        )
        stored = row.primary_uom.code if row.primary_uom else None
        row.enabled = False
        row.save(update_fields=["enabled"])

        assert metering_seams.service_default_uom("water") == stored
        assert "water" not in metering_seams.service_default_uoms()

    assert stored is not None, "the fixture must carry a stored unit or this proves nothing"


def test_def1549__an_unknown_service_is_still_None_never_a_guess(ottumwa):
    """CLAUDE.md hard rule 3 — `None` is the honest answer and stays one.

    Three ways to have no unit, all of which answered `None` through the walk
    and must answer `None` now: a code the catalog does not carry, and a
    catalog service the tenant declares no unit for. There is no fallback here
    and there must not be one — `service_default_uoms`' own docstring says so,
    and metering's validation errors `unit_missing` on exactly this meter.
    """
    with tenant_ctx(ottumwa):
        assert metering_seams.service_default_uom("not_a_service") is None
        assert metering_seams.service_default_uom("") is None
        #: `sewer` is one of the four catalog services with no design-stated
        #: default (see `tenancy.selectors.service_default_uoms`), so a tenant
        #: that enables it carries a NULL rather than a borrowed unit.
        assert metering_seams.service_default_uom("sewer") in (None, "kgal", "ccf")


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE COUNT UNDERNEATH IT — A REAL N+1 IN ITS OWN RIGHT
# ══════════════════════════════════════════════════════════════════════════
def test_def1549__active_account_count_does_not_query_per_service_point(ottumwa):
    """BR-TEN-026's live count is O(1) queries in the size of the estate.

    ⚠ **FIXED AT THE SOURCE RATHER THAN ROUTED AROUND, DELIBERATELY.** Moving
    `service_default_uom` off `services_overview()` takes this off the import's
    hot path, and that alone would have closed the Product Owner's ticket — but
    `active_account_count` is still called once per active service every time
    the S8 screen is drawn, and it resolved its points with a seam that costs
    **two queries each** (`service_point_ref`: the point row, then the platform
    catalog probe for its code) with no cache across calls. Left alone it would
    have bitten the next caller exactly as it bit this one.

    **The bound is the ESTATE, measured live**: whatever `P` the planted estate
    turns out to be, the count must not scale with it.
    """
    with tenant_ctx(ottumwa):
        points = plant_estate(ottumwa)
        with CaptureQueriesContext(connection) as captured:
            count = customers_services.active_account_count("water")

    print(
        f"\nDEF-1549 count cost: active_account_count('water') = {len(captured)} queries "
        f"for {points} service points"
    )
    assert points >= 8, "the estate must be big enough for a per-point cost to be visible"
    assert count == ESTATE_UNITS, (
        f"the count itself changed: {count} accounts on water, expected {ESTATE_UNITS}. A "
        "performance fix that alters BR-TEN-026's figure is a defect, not a fix — and a "
        "silent ZERO here would let a service be disabled underneath live accounts."
    )
    assert len(captured) <= 4, (
        f"active_account_count('water') issued {len(captured)} queries for {points} service "
        f"points. Before DEF-1549 it issued 1 + 2x{points} = {1 + 2 * points}, one pair per "
        "point, and services_overview() paid that once PER ACTIVE SERVICE."
    )


def test_def1549__the_screen_read_itself_stops_scaling_with_the_estate(ottumwa):
    """The S8 services screen — the read that was being walked — is now flat.

    Stated separately from the count above because it is the figure a PERSON
    experiences: `services_overview()` is what S8 renders, and before this fix
    it cost `~10 services x 2P` queries on top of its own rows. A utility with a
    real customer base was paying that on every visit to its own settings page,
    which nobody had measured because the only tenants in this suite are empty.

    ⚠ **THE COMPARISON IS ESTATE vs BIGGER ESTATE, NOT EMPTY vs ESTATE — AND
    THIS TEST'S FIRST DRAFT GOT THAT WRONG AND CAUGHT ITSELF.** Going from no
    agreements to some agreements DOES cost a little more (41 → 61 queries
    here): with rows to resolve, each of the ten `active_account_count` calls
    now issues its batched point lookup, which it skips entirely on an empty
    list. That step is **O(services), paid once**, and it is not the defect.
    The defect is O(POINTS). So the honest measurement holds the estate
    non-empty on both sides and only changes its SIZE: **triple the service
    points and the query count must not move at all.** A threshold could not
    have told those two shapes apart; two measurements can.
    """
    with tenant_ctx(ottumwa):
        small_points = plant_estate(ottumwa, units=2, tag="a")
        with CaptureQueriesContext(connection) as small:
            tenancy_selectors.services_overview()
        large_points = small_points + plant_estate(ottumwa, units=6, tag="b")
        with CaptureQueriesContext(connection) as large:
            tenancy_selectors.services_overview()

    print(
        f"\nDEF-1549 screen cost: services_overview() = {len(small)} queries at "
        f"{small_points} service points, {len(large)} at {large_points}"
    )
    assert large_points >= small_points * 3, "the second estate must be a real increase"
    assert len(large) == len(small), (
        f"services_overview() cost {len(small)} queries with {small_points} service points and "
        f"{len(large)} with {large_points} — it grew by {len(large) - len(small)} when the "
        "CUSTOMER BASE grew, which is DEF-1549's second N+1: active_account_count resolving one "
        "service point at a time, once per active service, every time the screen is drawn."
    )
