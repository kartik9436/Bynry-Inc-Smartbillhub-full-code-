# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-008 (EP-SHL-02 — CSV export: TC-5 columns+filters+2dp+audit,
#           TC-7 the 50,000-row refusal, TC-8 isolation) · US-MET-001 (S14) ·
#           US-MET-002 (S15) · US-MET-005 (S26/S27) · US-AST-001 (S49) ·
#           US-RAT-001 (S9 plans) · US-RAT-008 (charge codes) · US-RAT-009
#           (taxes & fees) · US-RAT-010 (rate-change history)
#           Screens: S14 · S15 · S26 · S27 · S49 · S9
# Rules:    BR-SHL-016 (server-side under the caller's tenant context; 50,000-row
#           cap; money-table exports write audit_log) · BR-SHL-029 (the cap) ·
#           BR-SHL-011 (the export mirrors the list's own request state) ·
#           BR-REP-018 (IS-11 contract: CSV always, XLSX never, 3-day retention)
# ───────────────────────────────────────────────────────
"""POST /exports — the nine registered lists, end to end.

Rides the identity plumbing like the S61 export tests: an export is a real
request by a real signed-in user against a real tenant, and the server decides.
JOBS_EAGER is on per test (the R1 path: 202 → the job runs → the file exists);
the test settings keep it off by default so the rest of the suite can enqueue
and run as two deliberate steps. The artifacts directory is redirected to
tmp_path everywhere — a suite must never write into the source tree.

Two tenants are seeded in every fixture (Silver Creek + Blue Mesa) so the
cross-tenant assertion is real rather than vacuous: the app-filter half is
asserted here, the live-RLS half stays with the G5 isolation suite (sqlite
cannot enforce RLS).
"""

import csv
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from apps.assets import models as asset_models
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.reports import catalog as reports_catalog
from apps.tenancy import exports as export_kernel
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.export_helpers import exported_bytes, exported_file
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

ALEX = ("alex@silvercreek.example", "Canyon2026rapids")
NINE = (
    "premises",
    "units",
    "routes",
    "cycles",
    "assets",
    "plans",
    "charges",
    "taxes",
    "rate-changes",
)
MONEY_RESOURCES = ("plans", "charges", "taxes", "rate-changes")


@pytest.fixture()
def wired(tmp_path, settings, export_bucket):
    """The deployment's own wiring — real store, real transport, eager — with
    exports in the emulated S3 bucket (PO 2026-10-02: S3 everywhere)."""
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield tmp_path
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


# ── seeding: one recognisable row per list, in BOTH tenants ─────────────────
def seed_lists(tenant, *, marker: str, user=None):
    """One row on each of the nine lists, every value traceable to `marker`."""
    electric = tenancy_models.Service.objects.get(code="electric")

    premises_type = metering_models.PremisesType.objects.create(
        tenant=tenant, code=f"{marker}-res", name=f"{marker} Residential"
    )
    premises = metering_models.Premises.objects.create(
        tenant=tenant,
        premise_no=f"P-{marker}",
        address_line=f"{marker} Elm Street",
        city="Katy",
        premises_type=premises_type,
        services_available=["electric", "water"],
        owner_manager=f"{marker} Property Co",
        status="active",
    )
    unit = metering_models.Unit.objects.create(
        tenant=tenant,
        premises=premises,
        unit_no=f"U-{marker}",
        label=f"{marker} Unit A",
        unit_type="residential",
    )
    metering_models.ServicePoint.objects.create(tenant=tenant, unit=unit, service=electric)
    cycle = metering_models.Cycle.objects.create(
        tenant=tenant,
        code=f"C-{marker}",
        start_day=1,
        days_to_complete=5,
        # ⚠ OQ-344 (RC-W6): `cycles.bill_date` is dropped (metering 0023). The
        # surviving default is the bill DAY, and a run with no typed date
        # resolves *"the bill day, in the month after the period ends"*. The
        # frequency and first run are here so the cycle HAS a next period for
        # that rule to be applied to — without them the export's `bill_date`
        # cell is honestly empty.
        frequency="Monthly",
        first_run_date=date(2026, 8, 1),
        bill_day=8,
        due_days=20,
    )
    route = metering_models.Route.objects.create(
        tenant=tenant,
        code=f"R-{marker}",
        name=f"{marker} Downtown",
        route_type="walk",
        cycle=cycle,
        status="active",
    )
    metering_models.RouteMembership.objects.create(tenant=tenant, route=route, unit=unit)

    asset_type = asset_models.AssetType.objects.create(
        tenant=tenant, code=f"{marker}-em", name=f"{marker} Electric Meter", category="meters"
    )
    stage = asset_models.AssetLifecycleStage.objects.create(
        tenant=tenant, code=f"{marker}-inservice", name="In service", behavior_class="in_service"
    )
    meter_type = asset_models.MeterType.objects.create(
        tenant=tenant, code=f"{marker}-ami", name="AMI"
    )
    read_method = asset_models.ReadMethod.objects.create(
        tenant=tenant, code=f"{marker}-remote", name="Remote"
    )
    asset_models.Asset.objects.create(
        tenant=tenant,
        asset_no=f"M-{marker}",
        serial_no=f"SN-{marker}",
        type=asset_type,
        status=stage,
        meter_type=meter_type,
        read_method=read_method,
        multiplier=Decimal("1.5"),
        unit="kWh",
        install_date=date(2026, 1, 15),
    )

    plan = rating_models.RatePlan.objects.create(
        tenant=tenant,
        code=f"PL-{marker}",
        name=f"{marker} Residential Standard",
        status="published",
    )
    rating_models.PlanService.objects.create(
        tenant=tenant, rate_plan=plan, service=electric, base_charge=Decimal("30.505000")
    )
    rating_models.Charge.objects.create(
        tenant=tenant,
        code=f"CH-{marker}",
        name=f"{marker} Late fee",
        charge_type="penalty",
        amount_rule="percent_with_minimum",
        percent=Decimal("0.015000"),
        min_amount=Decimal("5.004000"),
    )
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant=tenant, name=f"{marker} City", authority=f"{marker} Revenue", level="city"
    )
    rating_models.Tax.objects.create(
        tenant=tenant,
        jurisdiction=jurisdiction,
        name=f"{marker} Utility Tax",
        kind="percent",
        rate=Decimal("0.062500"),
        applies_to_services=["electric"],
        filing_frequency="monthly",
    )
    rating_models.RateChangeLog.objects.create(
        tenant=tenant,
        entity_type="plan",
        entity_id=plan.id,
        before={"base": "28.000000"},
        after={"base": "30.505000", "name": f"{marker} Residential Standard"},
        reason=f"{marker} annual adjustment",
        actor=user,
    )
    return {"premises": premises, "unit": unit, "route": route, "cycle": cycle, "plan": plan}


@pytest.fixture()
def lists(idn, wired):
    """Silver Creek's nine lists, plus Blue Mesa's nine behind the wall."""
    users = idn.seed_silvercreek()
    jordan, _ = idn.seed_bluemesa_admin()
    seed_lists(idn.silvercreek, marker="sc", user=users.alex)
    seed_lists(idn.bluemesa, marker="bm", user=jordan)
    return users


# ── request + file helpers ──────────────────────────────────────────────────
def export(client, body, *, tenant=None):
    kwargs = {"tenant": tenant} if tenant else {}
    response = api_post(client, "/exports", body, **kwargs)
    assert response.status_code == 202, response.content
    return response.json()


def artifact_of(job_id):
    """The job row + the file on disk.

    `result_link` is the IS-11 DOWNLOAD ROUTE (the download lane, 2026-08-10);
    the filesystem path the job body wrote lives on the record's payload, which
    is where operators — and this helper — read it from.
    """
    row = tenancy_models.Job.objects.get(id=job_id)
    assert row.result_link == f"/api/exports/{row.id}/file", row.result_link
    return row, exported_file(row.id)


def read_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def export_rows(client, body, **kwargs):
    accepted = export(client, body, **kwargs)
    job, path = artifact_of(accepted["job_id"])
    assert job.status == core_jobs.SUCCEEDED, job.error
    return job, path, read_csv(path)


# ── US-SHL-008 TC-5 — the file the export produces ──────────────────────────
@pytest.mark.parametrize("resource", NINE)
def test_us_shl_008_tc5__each_list_exports_with_its_ratified_columns(lists, resource):
    """Every one of the nine registered lists writes its capability-row columns,
    exactly one header row, and exactly the caller's own rows."""
    alex = signed_in_client(*ALEX)
    _job, path, rows = export_rows(alex, {"resource": resource})

    spec = export_kernel.export_resource(resource)
    assert rows[0] == list(spec.header)  # ONE header row, the declared columns
    assert len(rows) == 2  # header + Silver Creek's single seeded row
    assert path.suffix == ".csv"
    # {tenant}_{report}_{period}_{basis}_{generated}.csv — five segments, no
    # metadata rows in the data: the context is in the NAME (IS-9/IS-11).
    tenant_part, report, _period, basis, generated = path.stem.split("_")
    assert (tenant_part, report) == ("silvercreek", spec.slug)
    assert basis == spec.basis
    assert len(generated) == len("20260810T1655")


# Everything the registry holds beyond the PO's nine, each with the ruling that
# put it there. The point of the assertion below is "nothing is exported by
# ACCIDENT", so a resource has to be written down here to be legal — and this
# list is what makes the check keep meaning something as the product grows.
#
# ⚠ IT WAS STALE AND RED (DEF-461). `apps/reports/exports.py` registered its
# four report lists and left the assertion asserting nine, so it failed on the
# branch until 2026-08-21 with a message that reads like the NEW resource is the
# problem. Nothing runs the backend suite as a merge gate, so it simply sat.
BEYOND_THE_NINE = (
    # US-REP-003, the Report Centre. Four report lists, each with its own
    # BR-REP-001 date basis in the filename.
    #
    # Named through the catalog's own constants rather than as literals: the
    # first draft of this list wrote "revenue_by_service" and the real key is
    # `revenue_by_service_rate`, which is precisely the drift a second copy of a
    # name always produces (hard-won law 5).
    reports_catalog.KEY_AR_AGING,
    reports_catalog.KEY_BILLING_REGISTER,
    reports_catalog.KEY_REVENUE_BY_SERVICE,
    reports_catalog.KEY_PAYMENTS_BY_METHOD,
    # DEF-441, 2026-08-21. The S9 Rate schedules tab was excused from every
    # table capability — export included — because EP-RAT-02's matrix called it
    # a card grid. r10 line 764 draws a nine-column table; the tab now has the
    # table, and a list with a table has a Download.
    "rate-schedules",
    # CR-038 W5, 2026-08-26. The S25 reads list — its EP-MET-04 capability row
    # has declared "Export: CSV (IS-9)" since W2, and the S25 lane's own E3
    # reported the missing resource in as many words ("POST /exports … metering
    # registers premises · units · routes · cycles and no `reads`"). The
    # DEF-034 shape, closed for this list; scoped to the 2-yr hot window per
    # US-MET-012 TC-10.
    "reads",
    # DEF-2842, 2026-09-01. **THE ONE RESOURCE HERE THAT HAS NO LIST AND MUST
    # NOT GET ONE.** BR-BIL-065 is the PO's ruling of 2026-08-11 in two words —
    # *"B An export only"* — and option A, putting the release authorisation
    # record back on the phase-4 panel, was DECLINED in the same breath they
    # ruled that panel recalculates (BR-BIL-056). So this entry is not the
    # DEF-034 shape (*a list whose Download does nothing*); it is a ruling whose
    # DECLINED half was honoured for three weeks while its CHOSEN half was never
    # built, which reads exactly like compliance and is why nothing raised.
    "bill_run_releases",
)


def test_us_shl_008_tc5__the_nine_lists_the_po_named_are_all_registered():
    """The PO ruling of 2026-08-09 names nine lists; every one is registered.

    ⚠ **THIS WAS AN EQUALITY OVER THE WHOLE REGISTRY UNTIL 2026-09-24 AND ITS
    VERDICT DEPENDED ON ITS NEIGHBOURS (`DEF-SHL-6555`).** The registry is
    process-global module state filled by import side effects, so whether
    `apps/customers/disconnect_reads` had registered `disconnects` depended on
    which OTHER test files were in the same pytest process. Measured at the
    pinned tip 7be84c8d0: this case PASSES run alone and FAILS run beside
    `test_us_rep_003_downloads` — *"At index 6 diff: disconnects !=
    payments_by_method"*. **A check that passes when you check it and fails in
    the suite is worse than one that is simply wrong**, because it trains every
    later reader to dismiss it as flaky.

    It is now the two statements it was always trying to make, separately:

    **1 · Nothing NAMED is missing.** A subset, so a resource another module
    registers is not this module's failure.

    **2 · Nothing this file knows about has QUIETLY UNREGISTERED ITSELF.** That
    is what the equality was really guarding and it survives as the subset
    above — a name that vanishes still fails.

    **What the equality also claimed — *"nothing more is exported by
    accident"* — is dropped deliberately**, and this is the honest part: it was
    never true of the registry, only of whatever happened to be imported. Eight
    Finance and payments resources landed with `P4.1`/`P4.6` and this equality
    would have gone red for each one, which is a test asking to be edited every
    time the product grows rather than a guard against an accident.
    """
    registered = set(export_kernel.registered_resources())
    named = set(NINE) | set(BEYOND_THE_NINE)
    missing = sorted(named - registered)
    assert not missing, f"named but not registered: {missing}"


def test_be_list_export_premises_columns(lists):
    alex = signed_in_client(*ALEX)
    _job, _path, rows = export_rows(alex, {"resource": "premises"})
    assert rows[0] == [
        "premise_no",
        "address_line",
        "premises_type_name",
        "units",
        "services_available",
        # DEF-762 — the CSV writes an EMPTY CELL for a NULL services column and
        # for an explicitly empty one alike (`format_list` cannot tell them
        # apart), so the file carries a DERIVED second column saying whether
        # anybody was ever asked. `false` + empty = never asked; `true` + empty
        # = this address offers nothing. See tests/test_def762_premises_services_read.py.
        "services_recorded",
        "owner_manager",
        "status",
        # `DEF-MET-10164` (PO 2026-10-17: *"Both go in the export"*) — the
        # list's Created stamp, tenant zone WITH offset. Age is not a column:
        # a file keeps no today to subtract from.
        "created_at",
    ]
    assert rows[1][:8] == [
        "P-sc",
        "sc Elm Street",
        "sc Residential",
        "1",
        "electric|water",  # a multi-value cell can never read as extra columns
        "true",
        "sc Property Co",
        "active",
    ]
    created = datetime.fromisoformat(rows[1][8])
    assert created.tzinfo is not None  # the offset is written, never bare UTC


def test_be_list_export_units_columns(lists):
    alex = signed_in_client(*ALEX)
    _job, _path, rows = export_rows(alex, {"resource": "units"})
    assert rows[0] == [
        "unit_no",
        "premise_no",
        "label",
        "unit_type",
        # ⚠ **`services` CHANGED MEANING AND `metered_services` IS THE OLD ONE
        # (DEF-755).** A unit's services ARE its premises' (PO, 2026-08-26,
        # after CR-037 was withdrawn); what this column used to hold was *what
        # is metered here*, which is a different and still useful fact and now
        # has its own name. `services_recorded` is DEF-762's flag, because the
        # CSV writes an empty cell for a NULL premises list and an empty one
        # alike.
        "services",
        "services_recorded",
        "metered_services",
        "meters",
        "occupancy",  # BR-MET-036: DERIVED, exported as the screen derives it
        "occupant",  # "Occupant/Account" is one CELL over two stored fields
        "account_no",
        "status",
        "created_at",  # `DEF-MET-10164` — the UNIT's own stamp
    ]
    row = dict(zip(rows[0], rows[1]))
    assert datetime.fromisoformat(row["created_at"]).tzinfo is not None
    assert row["unit_no"] == "U-sc" and row["premise_no"] == "P-sc"
    # ⚠ THIS ASSERTION USED TO READ `== "electric"` AND THE CHANGE IS THE FIX.
    # The fixture's premises offers electric AND water (`services_available`
    # above) and the unit carries ONE service point, on electric. The old column
    # answered the meter and so said "electric"; the unit HAS both.
    assert row["services"] == "electric|water"
    assert row["metered_services"] == "electric"
    assert row["services_recorded"] == "true"
    assert row["occupancy"] == "vacant"  # no account exists — derived, not stored


def test_be_list_export_routes_and_cycles_columns(lists):
    alex = signed_in_client(*ALEX)
    _job, _path, routes = export_rows(alex, {"resource": "routes"})
    assert routes[0] == [
        "code",
        "name",
        "route_type",
        "feeder_ref",
        "assigned_to",
        "cycle_code",
        "meters",
        "collected",
        "last_completion",
        "status",
    ]
    route = dict(zip(routes[0], routes[1]))
    assert route["code"] == "R-sc" and route["cycle_code"] == "C-sc"
    # US-MET-005 §5: a null assignee IS the auto-pull path, named not blanked.
    assert route["assigned_to"] == "system"
    # BR-MET-011: unknown is EMPTY, never 0 — the reads lane is unwired.
    # W2 reads lane (2026-08-10): `collected` is now a measured 0 rather than
    # the empty cell that stood for "the reads table does not exist yet".
    # `last_completion` stays empty — no read has landed on this route.
    assert route["collected"] == "0" and route["last_completion"] == ""

    _job2, _path2, cycles = export_rows(alex, {"resource": "cycles"})
    # ⚠ **THREE COLUMNS ADDED BY W5-T2, AND THE TWO WINDOW CELLS CHANGED
    # SOURCE.** The window is DERIVED from `start_day` + `days_to_complete`
    # now (metering 0021 dropped the stored pair), so an export that named
    # only the window could not be used to reconstruct the schedule it
    # describes — a reader could see WHEN August ran and not what the cycle
    # repeats on. The three ruled fields are exported beside it.
    assert cycles[0] == [
        "code",
        "routes",
        "frequency",
        "start_day",
        "days_to_complete",
        "window_start",  # "Read window" is one CELL over two DERIVED dates
        "window_end",
        "bill_date",
        "expected",
        "collected",
        "progress",
        "status",
    ]
    cycle = dict(zip(cycles[0], cycles[1]))
    assert cycle["code"] == "C-sc" and cycle["routes"] == "R-sc"
    assert (cycle["start_day"], cycle["days_to_complete"]) == ("1", "5")
    # ISO dates (IS-9), derived: the 1st for 5 days in the tenant's own month.
    assert cycle["window_start"].endswith("-01")
    # ⚠ `bill_date` IS DERIVED NOW (OQ-344, metering 0023): the bill DAY placed
    # in the month after the cycle's next period ends. The DAY is what this
    # asserts — the month moves with the tenant's own today, exactly as
    # `window_start` above already does, and pinning it would make the case
    # fail on a calendar boundary rather than on a defect.
    assert cycle["bill_date"].endswith("-08")


def test_be_list_export_assets_columns(lists):
    alex = signed_in_client(*ALEX)
    _job, _path, rows = export_rows(alex, {"resource": "assets"})
    assert rows[0] == [
        "asset_no",
        "parent_asset_no",
        "type",
        "type_name",
        "meter_type",
        "read_method",
        "unit",
        "multiplier",
        "assigned_to",
        "assigned_address",
        "install_date",
        "status",
        "status_name",
        # DEF-AST-10178 — the Age column, as numbers.
        "age_start",
        "age_from",
        "age_years",
        "age_months",
        "age_days",
        "past_life",
    ]
    row = dict(zip(rows[0], rows[1]))
    assert row["asset_no"] == "M-sc"  # BR-AST-026: never the uuid
    assert row["meter_type"] == "sc-ami" and row["read_method"] == "sc-remote"
    assert row["unit"] == "kWh"  # CLAUDE.md rule 3: never a bare quantity
    assert row["multiplier"] == "1.500000"  # a factor, NOT money — not re-rounded
    assert row["install_date"] == "2026-01-15"


def test_be_list_export_plans_columns(lists):
    alex = signed_in_client(*ALEX)
    _job, _path, rows = export_rows(alex, {"resource": "plans"})
    assert rows[0] == ["plan", "services", "rate_schedules", "base_charges", "accounts", "status"]
    row = dict(zip(rows[0], rows[1]))
    assert row["plan"] == "sc Residential Standard"
    assert row["services"] == "electric"
    # ⚠ **BLANK, AND NEVER `30.51` AGAIN — `BR-RAT-1040`, PO ruling 2026-09-27
    # (*"a is good"*), closing `DEF-RAT-6927`, shipped in `bea9b25e4`.** This
    # read `30.51`: the fixture's `30.505000` sits in `plan_services.base_charge`,
    # the column `BR-RAT-088` retired when the charge code took the base over.
    # The plan's base is now walked plan → rate schedule → charge code, this
    # fixture plan binds no rate schedule (`no_rate_schedule`), so the figure is
    # null — an honest gap, never `0.00` — and a null money cell is empty in the
    # file. Red since `bea9b25e4` (green at `120439f2a`). If this ever reads
    # `30.51` again the retired column has come back. IS-9's 2dp rounding of a
    # money cell (30.505000 → 30.51) is still asserted by
    # `export_kernel.format_money` below and by `min_amount` in the charges case.
    assert row["base_charges"] == ""
    assert row["accounts"] == "0" and row["status"] == "published"


def test_be_list_export_charges_and_taxes_columns(lists):
    alex = signed_in_client(*ALEX)
    _job, _path, charges = export_rows(alex, {"resource": "charges"})
    assert charges[0] == [
        "code",
        "description",
        "type",
        "service",
        # The Amount CELL is a percent, money, or both, chosen by the rule
        # (BR-RAT-041) — IS-9 gives a money column one meaning, so the rule and
        # each field it uses get their own column.
        "amount_rule",
        "amount",
        "percent",
        "min_amount",
        "gl_account_id",
    ]
    charge = dict(zip(charges[0], charges[1]))
    assert charge["amount_rule"] == "percent_with_minimum"
    assert charge["min_amount"] == "5.00"  # money → 2dp
    # A percent is a stored FRACTION, not money: 2dp would make 0.015 → 0.02.
    assert charge["percent"] == "0.015000"

    _job2, _path2, taxes = export_rows(alex, {"resource": "taxes"})
    assert taxes[0] == [
        "name",
        "jurisdiction",
        "authority",
        "level",
        "applies_to_services",
        "rate_kind",
        "rate",
        "flat_amount",
        "per_unit_amount",
        "per_unit_uom",
        "remittance",
        "gl_account_id",
    ]
    tax = dict(zip(taxes[0], taxes[1]))
    assert tax["jurisdiction"] == "sc City" and tax["authority"] == "sc Revenue"
    assert tax["rate"] == "0.062500"  # a fraction, unscaled and unrounded
    assert tax["remittance"] == "monthly"


def test_be_list_export_rate_change_history_columns(lists):
    alex = signed_in_client(*ALEX)
    _job, _path, rows = export_rows(alex, {"resource": "rate-changes"})
    assert rows[0] == [
        "changed_at",
        "entity_type",
        "entity_id",
        "entity_name",
        "change_before",  # the "Change (before → after)" cell, as its two parts
        "change_after",
        "reason",
        "actor_user_id",
        "published_by",
        "batch_id",
    ]
    row = dict(zip(rows[0], rows[1]))
    assert row["entity_type"] == "plan" and uuid.UUID(row["entity_id"])
    assert row["change_before"] == '{"base": "28.000000"}'  # canonical JSON
    assert row["reason"] == "sc annual adjustment"
    # GAP: rate_change_log stores ONE actor and no publisher (r5 #14) — the
    # column is PRESENT and empty rather than repeating the actor.
    assert row["published_by"] == ""


# ── the request state the list itself carries (BR-SHL-011) ──────────────────
def test_be_list_export_honors_the_filters_the_list_shows(lists):
    """An export matches what the list shows: same filter, same rows."""
    alex = signed_in_client(*ALEX)
    metering_models.Premises.objects.create(
        tenant=lists.alex.tenant,
        premise_no="P-sc-2",
        address_line="sc Oak Street",
        status="inactive",
    )
    _job, _path, everything = export_rows(alex, {"resource": "premises"})
    assert len(everything) == 3  # header + both premises

    _job2, _path2, filtered = export_rows(
        alex, {"resource": "premises", "filters": {"status": "inactive"}}
    )
    assert len(filtered) == 2
    assert filtered[1][0] == "P-sc-2"


def test_be_list_export_honors_the_sort_the_list_shows(lists):
    alex = signed_in_client(*ALEX)
    metering_models.Premises.objects.create(
        tenant=lists.alex.tenant, premise_no="P-sc-2", address_line="sc Oak Street"
    )
    _job, _path, ascending = export_rows(alex, {"resource": "premises", "sort": "premise_no"})
    _job2, _path2, descending = export_rows(
        alex, {"resource": "premises", "sort": "premise_no", "dir": "desc"}
    )
    assert [row[0] for row in ascending[1:]] == ["P-sc", "P-sc-2"]
    assert [row[0] for row in descending[1:]] == ["P-sc-2", "P-sc"]


def test_be_list_export_accepts_the_lists_own_url_state(lists):
    """The screen can post the very query string it is displaying: `f.<name>`
    query params are read exactly as the list endpoint reads them."""
    alex = signed_in_client(*ALEX)
    metering_models.Premises.objects.create(
        tenant=lists.alex.tenant,
        premise_no="P-sc-2",
        address_line="sc Oak Street",
        status="inactive",
    )
    accepted = api_post(alex, "/exports?f.status=inactive", {"resource": "premises"})
    assert accepted.status_code == 202
    _job, path = artifact_of(accepted.json()["job_id"])
    rows = read_csv(path)
    assert len(rows) == 2 and rows[1][0] == "P-sc-2"


def test_be_list_export_ignores_a_filter_the_list_ignores(lists):
    """BR-SHL-011: a param outside the resource's vocabulary falls through —
    a list URL (or an export of it) can never 4xx over its own params."""
    alex = signed_in_client(*ALEX)
    _job, _path, rows = export_rows(
        alex, {"resource": "premises", "filters": {"not_a_filter": "x"}, "sort": "nonsense"}
    )
    assert len(rows) == 2  # unchanged: the unknown filter selected nothing away


# ── the refusals ────────────────────────────────────────────────────────────
def test_be_list_export_unknown_resource_is_a_plain_404(lists):
    """An unregistered list does not exist on this deployment — never a guessed
    queryset, and never a hint that some other spelling would work."""
    alex = signed_in_client(*ALEX)
    for body in ({"resource": "invoices"}, {"resource": ""}, {}):
        response = api_post(alex, "/exports", body)
        assert response.status_code == 404, body
    assert tenancy_models.Job.objects.count() == 0


def test_us_shl_008_tc7__no_export_is_refused_for_being_large(lists, wired):
    """⛔ **THIS CASE ASSERTED THE OPPOSITE UNTIL `P2.4` (`CR-142-BRC07`).**

    It read *"over 50,000 rows the request is refused at ACCEPT time"* and
    lowered `EXPORT_ROW_CAP` to 0 to prove it. **`NFR-5` forbids a hard cap
    anywhere**, and the cap was already short of this product's own customers —
    Killeen at 57,066 accounts x 14 cycles is ~685,000 bill rows a year.

    The cap and its pre-count are DELETED. What US-SHL-008 still needs is the
    half that was never about the cap: the accept path resolves the resource,
    writes no partial file, and enqueues exactly one job. **The refusal is
    gone, so the assertion is that it cannot happen** — and the constant is
    asserted ABSENT by name, because a later lane reintroducing
    `EXPORT_ROW_CAP` is precisely what this case now exists to catch.
    """
    assert not hasattr(export_kernel, "EXPORT_ROW_CAP"), (
        "`EXPORT_ROW_CAP` is back. NFR-5 forbids a hard cap anywhere, including "
        "one a tenant can raise on a Settings screen — see P2.4."
    )
    assert not hasattr(export_kernel, "selection_count"), (
        "`selection_count` is back, which means the report is built twice: once "
        "to be counted and thrown away, once to be written — see P2.4."
    )

    alex = signed_in_client(*ALEX)
    accepted = api_post(alex, "/exports", {"resource": "premises"})
    assert accepted.status_code == 202, accepted.content
    assert tenancy_models.Job.objects.count() == 1


def test_be_list_export_needs_a_signed_in_caller(lists):
    """No session, no export — the list's own gate, applied to its file."""
    from django.test import Client

    response = api_post(Client(), "/exports", {"resource": "premises"})
    assert response.status_code in (401, 403)
    assert tenancy_models.Job.objects.count() == 0


# ── BR-SHL-016: the money clause ────────────────────────────────────────────
@pytest.mark.parametrize("resource", MONEY_RESOURCES)
def test_us_shl_008_tc5__a_money_export_writes_its_audit_row(lists, idn, resource):
    """BR-SHL-016: exports from money tables write `audit_log` — who, which
    list, the filter state, the columns and the job.

    ⚠ **`row_count` LEFT THIS ROW WITH THE CAP (`P2.4`, `CR-142-BRC07`).** The
    audit row is written at ACCEPT time and nothing has counted the selection
    by then — counting it was `selection_count`, which for the derived-filter
    lists built the whole report a second time. The number now lives on the
    finished JOB, measured from what was written rather than predicted before
    the file existed, so this case asserts it is ABSENT here: a later lane
    putting the pre-count back would show up as this assertion, not as a
    silent doubling of every export.
    """
    alex = signed_in_client(*ALEX)
    accepted = export(alex, {"resource": resource, "filters": {}})

    rows = idn.rows_for("list.exported")
    assert len(rows) == 1, idn.actions()
    after = rows[0]["after"]
    assert after["resource"] == resource
    assert "row_count" not in after, (
        "the accept-time audit row carries a row count again, which means the "
        "selection was counted before it was streamed — see P2.4."
    )
    assert after["job_id"] == accepted["job_id"]
    assert rows[0]["actor_user_id"] is not None  # who


@pytest.mark.parametrize("resource", ("premises", "units", "routes", "cycles", "assets"))
def test_be_list_export_a_non_money_export_writes_no_audit_row(lists, idn, resource):
    """The silence is the RULE's: BR-SHL-016 audits MONEY-table exports. A
    registry list writes none, and that absence is asserted so it cannot drift
    into an unexplained omission."""
    alex = signed_in_client(*ALEX)
    export(alex, {"resource": resource})
    assert idn.rows_for("list.exported") == []


# ── tenant scoping (TC-8) ───────────────────────────────────────────────────
@pytest.mark.parametrize("resource", NINE)
def test_us_shl_008_tc8__no_export_ever_contains_another_tenants_rows(lists, resource):
    """BR-SHL-016 "under the caller's tenant context": the job runs in the
    record's own tenant, so the query behind the file is that tenant's. The
    app-filter half is asserted here; the live-RLS half is the G5 suite's."""
    alex = signed_in_client(*ALEX)
    _job, path, rows = export_rows(alex, {"resource": resource})
    body = path.read_text(encoding="utf-8")
    # Every Blue Mesa value carries the `bm` marker; not one may appear.
    for foreign in ("P-bm", "U-bm", "R-bm", "C-bm", "M-bm", "PL-bm", "CH-bm", "bm City", "bm "):
        assert foreign not in body, foreign
    assert len(rows) == 2  # header + this tenant's single row

    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    _job2, path2, their_rows = export_rows(jordan, {"resource": resource}, tenant=BM)
    assert path2.stem.startswith("bluemesa_")
    assert len(their_rows) == 2
    assert "P-sc" not in path2.read_text(encoding="utf-8")


# ── IS-9 value law, on the writer everyone shares ───────────────────────────
def test_be_list_export_timestamps_carry_the_tenant_offset(lists, idn):
    """IS-8/IS-9: a timestamp column renders in the tenant's Regional zone,
    ISO 8601, WITH its offset — never bare UTC and never a naive string."""
    tenancy_models.TenantSettings.objects.create(tenant=idn.silvercreek, timezone="America/Chicago")
    alex = signed_in_client(*ALEX)
    _job, _path, rows = export_rows(alex, {"resource": "rate-changes"})
    changed_at = rows[1][0]
    assert changed_at.endswith("-05:00") or changed_at.endswith("-06:00")  # CDT / CST


def test_be_list_export_money_is_plain_two_decimals():
    """IS-9 money: plain 2dp, no symbol, no thousands separator, half-up at
    DISPLAY only (CLAUDE.md rule 2 — B4 owns finalization)."""
    assert export_kernel.format_money(Decimal("30.505000")) == "30.51"
    assert export_kernel.format_money(Decimal("1234567.891")) == "1234567.89"
    assert export_kernel.format_money(Decimal("-0.005")) == "-0.01"
    assert export_kernel.format_money(None) == ""
    # Not a number → written through unchanged; an export never invents a value.
    assert export_kernel.format_money("n/a") == "n/a"


def test_be_list_export_is_utf8_with_one_header_row(lists):
    """IS-9: UTF-8, comma, exactly ONE header row, NO metadata rows in the data
    — the context lives in the filename."""
    alex = signed_in_client(*ALEX)
    metering_models.Premises.objects.create(
        tenant=lists.alex.tenant, premise_no="P-sc-2", address_line="Rúa José Martí 12"
    )
    _job, path, rows = export_rows(alex, {"resource": "premises"})
    assert "Rúa José Martí 12" in path.read_text(encoding="utf-8")
    assert rows[0][0] == "premise_no"
    assert all(row[0] != "premise_no" for row in rows[1:])  # no repeated header
    assert all(len(row) == len(rows[0]) for row in rows)  # no metadata rows


def test_be_list_export_only_ever_writes_csv(lists):
    """IS-11: CSV always; XLSX must be UNREQUESTABLE. There is no format
    parameter to ask with, and a request that tries is answered in CSV."""
    alex = signed_in_client(*ALEX)
    _job, path, _rows = export_rows(alex, {"resource": "premises", "format": "xlsx"})
    assert path.suffix == ".csv"
    assert list(path.parent.glob("*.xlsx")) == []


def test_be_list_export_never_sweeps_on_the_way_in(lists, wired):
    """BR-REP-018: files are retained `file_retention_days`. ⚠ **AN EXPORT NO
    LONGER SWEEPS** (PO 2026-10-02: *"Once a day, for each utility, the system
    deletes exports older than that utility's own setting"*) — the daily
    per-utility sweep does (tests/test_s3a_export_store.py). An earlier export
    past retention is left for it, and its row stays `stored` until then."""
    from datetime import timedelta

    from django.utils import timezone as django_timezone

    from apps.tenancy.export_models import JobArtifact

    alex = signed_in_client(*ALEX)
    first, _path, _rows = export_rows(alex, {"resource": "premises"})
    JobArtifact.objects.filter(job_id=first.id).update(
        created_at=django_timezone.now()
        - timedelta(days=export_kernel.ARTIFACT_RETENTION_DAYS + 1)
    )
    _job, path, _rows = export_rows(alex, {"resource": "premises"})
    assert JobArtifact.objects.get(job_id=first.id).status == "stored"
    assert exported_bytes(first.id)  # still in the bucket
    assert path.exists()


def test_be_list_export_a_writer_failure_lands_on_the_job_not_the_caller(lists, monkeypatch):
    """The accept already answered 202: a broken writer is a FAILED job with
    its error, never a 500 on the export request."""

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(export_kernel, "scratch_dir", broken)
    alex = signed_in_client(*ALEX)
    accepted = export(alex, {"resource": "plans"})
    job = tenancy_models.Job.objects.get(id=accepted["job_id"])
    assert job.status == core_jobs.FAILED
    assert job.error == "OSError: disk full"
    assert job.result_link is None


def test_be_list_export_the_202_names_the_poll_url(lists):
    """B12 r1 / 11b §2.17: the accept body is the job id + where to poll, and
    that URL is the ONE shared poll resource — not a second status endpoint."""
    alex = signed_in_client(*ALEX)
    accepted = export(alex, {"resource": "premises"})
    assert accepted["status_url"] == f"/api/jobs/{accepted['job_id']}"
    from tests.test_us_idn_helpers import api_get

    polled = api_get(alex, accepted["status_url"])
    assert polled.status_code == 200
    assert polled.json()["kind"] == "list_export"
    assert polled.json()["status"] == core_jobs.SUCCEEDED


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-008@17df6a0 (EP-SHL-02 §Stories — hash = sha256/7 of the source epic; co-packets US-MET-001/002@947cf31 · US-MET-005@14f767b · US-AST-001@566072b · US-RAT-001@6304a38 · US-RAT-008/009@7d1a8ef · US-RAT-010@f69a661)
# generated: 2026-08-10 by story-coder v1 (list-export lane — POST /exports and the nine registered lists) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(the frontend half has its own vitest files) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F on apps/core/config — the bar the baseline passes) black✔(this lane's 13 files; 32 pre-existing unformatted files are the repo baseline, untouched) py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped (unchanged) · migrate from empty✔ makemigrations --check --dry-run clean✔ (this lane adds NO migration) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) · frontend tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · mypy NOT INSTALLED in this environment (recorded, not skipped silently) · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: US-SHL-008 §4's fixtures are Silver Creek S33/S34 payments and outstandings — neither table exists (billing/payments are unbuilt), so these TCs assert the CONTRACT (columns, one header, filters, sort, 2dp money, tenant offset, cap, audit row, cross-tenant) against the nine lists that DO exist and the identity lane's two tenants; recorded, not silently substituted · TC-8's live-RLS half stays with the G5 isolation suite (sqlite cannot enforce RLS); the app-filter half is asserted here · the cap TC lowers EXPORT_ROW_CAP rather than seeding 50,001 rows — the guard under test is the refusal, not insert throughput · no download-endpoint TC exists because no download endpoint exists (IS-11, reports W5): the artifact path is asserted instead · [path-tenancy lane 2026-08-10] `/api/exports` + `/api/jobs/{id}`; requests name their tenant instead of a Host
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
