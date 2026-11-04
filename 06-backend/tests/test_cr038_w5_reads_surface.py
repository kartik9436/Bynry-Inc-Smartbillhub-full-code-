# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-012 (S25 reads list — the capability row's TEN columns) ·
#           US-MET-013 (S29 read detail — tags + linkage from the same payload)
#           Change: CR-038 W5 (Reads list + read detail page)
#           Screens: S25, S29, SET-06D (route sheet)
# Rules:    BR-MET-016/053 (lineage heads) · BR-MET-055 (2-yr hot window; the
#           EXPORT is scoped to it too — US-MET-012 TC-10 verbatim: "scopes
#           queries to the 2-yr hot window") · BR-SHL-010 (the capability row
#           IS the column set) · BR-SHL-011 (the export mirrors the list's own
#           request state) · BR-SHL-016 (server-side export under the caller's
#           tenant context) · CLAUDE.md rule 1 (tenant scoping) · rule 3
#           (consumption always with its unit) · D11 (a route sheet stop is a
#           PREMISES) · DEF-324 (one-query discipline — no N+1 on a list page)
# Defects:  DEF-045 (the four missing S25 columns — closed here) ·
#           DEF-034-class (an export the capability row declares that resolves
#           to NO registered resource — `reads` now registers one, proved by a
#           202 that lands in a real file)
# ───────────────────────────────────────────────────────
"""CR-038 W5 — the reads surface: served columns, the export, the route sheet.

RED-FIRST RECORD (2026-08-26, this lane): every test below was run against the
pre-lane tree first.

  · the column tests failed `KeyError: 'cycle'` — `read_dict` served none of
    cycle/route/service/premise (DEF-045's exact finding);
  · the export tests failed at the 404 — `export_resource("reads")` was None
    (the DEF-034 shape: a declared CSV export with no registered resource);
  · the route-sheet tests failed at the 404 — no such path was mounted.
"""

import csv
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.metering import models as metering_models
from apps.metering import selectors, services
from apps.tenancy import exports as export_kernel
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.export_helpers import exported_file
from tests.test_us_idn_helpers import (  # noqa: F401 — fixture imports
    api_post,
    idn,
    signed_in_client,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db


# ── fixtures: one read on a routed, cycled meter ────────────────────────────


def routed_meter(tenant, actor, *, asset_no="M-7001", address="1408 Elm Street", label="Unit A"):
    """A meter whose service point carries a route AND a cycle — the joined
    world DEF-045's four columns read from. Built through the real services."""
    asset = a_meter(actor, asset_no=asset_no, address=address, unit_label=label)
    premises = metering_models.Premises.objects.get(tenant=tenant, address_line=address)
    cycle = services.create_cycle(
        actor, {"code": "08-A", "name": "Cycle 08-A", "frequency": "monthly"}
    )
    route = services.create_route(
        actor,
        {
            "code": "R-1",
            "name": "Downtown",
            "service_code": "electric",
            "premises_ids": [str(premises.id)],
            "cycle_id": cycle["id"],
        },
    )
    return asset, route, cycle


# ── DEF-045 — the four columns, SERVED ──────────────────────────────────────


def test_us_met_012_tc1__read_dict_serves_cycle_route_service_premise(brazos, dana):
    """The RDS-01 row: METER · CYCLE · ROUTE · SERVICE · PREMISE all present,
    joined server-side — never invented by a client-side join (DEF-045)."""
    with tenant_ctx(brazos):
        asset, route, cycle = routed_meter(brazos, dana)
        commit_read(
            dana,
            asset["id"],
            day="2026-08-03",
            value="42864",
            consumption=Decimal("684"),
            unit="kWh",
        )
        row = selectors.read_dict(selectors.read_list().first())
    assert row["cycle"] == "08-A"
    assert row["cycle_id"] == str(cycle["id"])
    assert row["route"] == "R-1"
    assert row["route_id"] == str(route["id"])
    assert row["service"] == "electric"
    assert row["premise"] == "1408 Elm Street"
    assert row["unit_label"] == "Unit A"
    assert row["premises_id"] is not None
    assert row["unit_id"] is not None


def test_us_met_012_tc1__an_unattached_meter_serves_honest_nulls(brazos, dana):
    """A stock meter (no service point) has no route, no cycle, no service and
    no premise — the row says so with nulls, never with invented values."""
    from apps.assets import services as asset_services

    with tenant_ctx(brazos):
        asset = asset_services.create_asset(
            dana,
            {
                "type": "meter",
                "asset_no": "M-STOCK",
                "service": "electric",
                "unit": "kWh",
                "read_method": "manual",
                "multiplier": "1",
                "register_digits": 5,
                "install_date": "2026-01-05",
                "status": "active",
            },
        )
        commit_read(
            dana, asset["id"], day="2026-08-03", value="10", consumption=Decimal("10"), unit="kWh"
        )
        row = selectors.read_dict(selectors.read_list().first())
    for field in (
        "cycle",
        "cycle_id",
        "route",
        "route_id",
        "service",
        "premise",
        "premise_no",
        "premises_id",
        "unit_label",
        "unit_id",
    ):
        assert row[field] is None, field


def test_def_324__the_list_page_serializes_in_one_query(brazos, dana, django_assert_num_queries):
    """DEF-324 discipline: the joins ride the ONE list query — serializing a
    page issues no per-row lookup for route, cycle, service or premises."""
    with tenant_ctx(brazos):
        asset, _route, _cycle = routed_meter(brazos, dana)
        for day in ("2026-08-01", "2026-08-02", "2026-08-03"):
            commit_read(
                dana, asset["id"], day=day, value="100", consumption=Decimal("10"), unit="kWh"
            )
        queryset = selectors.read_list()
        with django_assert_num_queries(1):
            rows = [selectors.read_dict(row) for row in queryset]
    assert len(rows) == 3
    assert {row["route"] for row in rows} == {"R-1"}


def test_def_045__the_route_filter_and_the_route_column_agree(brazos, dana):
    """DEF-045's sentence: *"a clerk narrows to Route 3 and sees no route
    column confirming it."* Now the filter and the column are one fact."""
    with tenant_ctx(brazos):
        asset, route, _cycle = routed_meter(brazos, dana)
        other = a_meter(dana, asset_no="M-9001", address="9 Other Rd", unit_label="Unit B")
        commit_read(
            dana, asset["id"], day="2026-08-03", value="100", consumption=Decimal("10"), unit="kWh"
        )
        commit_read(
            dana, other["id"], day="2026-08-03", value="200", consumption=Decimal("20"), unit="kWh"
        )
        rows = [
            selectors.read_dict(row) for row in selectors.read_list(filters={"route": route["id"]})
        ]
    assert [row["meter"] for row in rows] == ["M-7001"]
    assert {row["route"] for row in rows} == {"R-1"}


def test_us_met_013__the_chain_carries_the_linkage_in_one_query(
    brazos, dana, django_assert_num_queries
):
    """S29's tags block reads the same fields off the chain entries; the chain
    query carries the joins so no entry lazy-loads its way to a premises."""
    with tenant_ctx(brazos):
        asset, _route, _cycle = routed_meter(brazos, dana)
        read = commit_read(
            dana, asset["id"], day="2026-08-03", value="100", consumption=Decimal("10"), unit="kWh"
        )
        with django_assert_num_queries(1):
            chain = selectors.read_chain(read.id)
    assert chain[0]["cycle"] == "08-A"
    assert chain[0]["premise"] == "1408 Elm Street"


# ── the reads EXPORT (the DEF-034 class, closed for S25) ────────────────────

ALEX = ("alex@silvercreek.example", "Canyon2026rapids")


@pytest.fixture()
def wired(tmp_path, settings):
    """The export deployment wiring — real store, real transport, eager — with
    the artifacts directory pointed at tmp_path (test_be_list_export's own)."""
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield tmp_path
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


def metering_actor(tenant):
    """The metering services take a role-bearing actor (BR-MET-035); the idn
    users carry their role on the MEMBERSHIP, so service calls use this
    real-user-backed staff actor instead (test_us_met_helpers.staff_actor).

    The idn tenants are provisioned with NO services enabled, and BR-MET-003
    refuses a premises offering a service the tenant has not — so `electric` is
    enabled here first, through the row `services_overview` reads.

    ⚠ **AND THEY HOLD NO PREMISES-OWNER CATEGORIES — `DEF-MET-6158`.** A real
    tenant is given the five ratified ones at provisioning (`owner_categories`
    is a STRUCTURAL list, BR-TEN-150 clause 3 / BR-TEN-067), and
    `make_premises` creates its owner as a `landlord` (BR-MET-401). The idn
    tenants are built without provisioning, so every case reaching `a_meter`
    died on `VAL-005 metering.premises_owner.category_unknown` with
    `allowed: []` — red at the earliest commit this clone holds (`57d73d57d`,
    2026-08-29). The list is seeded here from the SAME platform fixture and
    through the SAME handler provisioning uses, never typed in this file."""

    from types import SimpleNamespace

    from apps.identity import models as identity_models
    from tests.test_us_met_helpers import staff_actor as make_staff_actor

    electric = tenancy_models.Service.objects.get(code="electric")
    tenancy_models.TenantService.objects.get_or_create(
        tenant=tenant, service=electric, defaults={"enabled": True}
    )
    # Insert-missing by code (BR-TEN-012), so calling this per seeding step is
    # idempotent.
    tenancy_services.PremisesOwnerCategoryLookupHandler().seed(
        tenant, tenancy_services._load_seed_fixture()["owner_categories"]
    )
    email = f"seeder@{tenant.subdomain}.test"
    existing = identity_models.User.objects.filter(tenant=tenant, email=email).first()
    if existing is not None:  # idempotent — tests call this per seeding step
        return SimpleNamespace(id=existing.id, pk=existing.id, role="system_admin", user=existing)
    return make_staff_actor(tenant, email=email)


def seed_read(tenant, *, asset_no, address, day, unit="kWh", value="42864", consumption="684"):
    with tenant_ctx(tenant):
        actor = metering_actor(tenant)
        asset = a_meter(actor, asset_no=asset_no, address=address)
        commit_read(
            actor, asset["id"], day=day, value=value, consumption=Decimal(consumption), unit=unit
        )
    return asset


def test_def_034_class__reads_is_a_REGISTERED_export_resource():
    """The button's 202 must land on a real resource — DEF-034's finding was a
    capability row whose export resolved to nothing."""
    resource = export_kernel.export_resource("reads")
    assert resource is not None
    assert resource.module == "metering"
    # BR-SHL-011: the export's vocabulary is the list endpoint's own.
    assert set(resource.filters) == set(selectors.READ_FILTERS)
    assert set(resource.sorts) == set(selectors.READ_SORTS)
    # The capability row's default: read_at, newest first.
    assert (resource.default_sort, resource.default_dir) == ("read_at", "desc")


def _export_file(client, body):
    response = api_post(client, "/exports", body)
    assert response.status_code == 202, response.content
    job = tenancy_models.Job.objects.get(id=response.json()["job_id"])
    assert job.status == core_jobs.SUCCEEDED, job.error
    return list(csv.reader(exported_file(job.id).open()))


def test_us_met_012_export__202s_into_a_real_csv_with_the_rows_columns(idn, wired):
    """POST /exports resource=reads → 202 → a real file whose header is the
    declared column set (incl. the UNIT cell — rule 3 in a CSV) and whose rows
    are the caller's own reads."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    day = (timezone.now() - timedelta(days=3)).date().isoformat()
    seed_read(idn.silvercreek, asset_no="M-SC-1", address="1 Silver St", day=day)
    # CLAUDE.md rule 1: the neighbour tenant's read must never reach the file.
    seed_read(idn.bluemesa, asset_no="M-BM-1", address="1 Mesa Rd", day=day)

    rows = _export_file(signed_in_client(*ALEX), {"resource": "reads"})
    header, data = rows[0], rows[1:]
    assert header == list(export_kernel.export_resource("reads").header)
    for column in (
        "meter",
        "cycle",
        "route",
        "service",
        "premise",
        "unit_label",
        "consumption",
        "unit",
        "status",
    ):
        assert column in header, column
    assert len(data) == 1
    row = dict(zip(header, data[0]))
    assert row["meter"] == "M-SC-1"
    assert row["unit"] == "kWh"  # the unit travels beside the quantity
    # ⚠ **AMENDED 2026-08-27 (OQ-620(b), DEF-1123).** This asserted
    # `"684.000000"` and its comment gave the reason: *written AS SERVED, the
    # same figure the screen's own usage cell renders ("684.000000 kWh")*. Both
    # halves have since stopped being true. The screen's usage cell renders
    # `684 kWh` (DEF-894 composed it server-side through BR-MET-144), and the
    # PO ruled the file follows: *"Is a downloaded CSV read by a person or
    # calculated by a spreadsheet? (a) Two decimals, like the screen"* — an
    # OVERRULE, taken with the risk to downstream reconciliation stated.
    #
    # A CSV is a reading surface in this product. The UNIT still travels in its
    # own parseable cell, asserted three lines up, which is what makes the
    # number checkable at all (hard rule 3).
    assert row["consumption"] == "684"
    assert row["premise"] == "1 Silver St"


def test_us_met_012_tc10__the_export_is_scoped_to_the_2yr_hot_window(idn, wired):
    """TC-10 verbatim: an export of all history is scoped to the hot window —
    an archived-age read stays out of the file (BR-MET-055)."""
    idn.seed_silvercreek()
    recent = (timezone.now() - timedelta(days=3)).date().isoformat()
    seed_read(idn.silvercreek, asset_no="M-HOT", address="2 Hot St", day=recent)
    seed_read(idn.silvercreek, asset_no="M-COLD", address="3 Cold St", day="2023-01-15")

    rows = _export_file(signed_in_client(*ALEX), {"resource": "reads"})
    meters = [dict(zip(rows[0], row))["meter"] for row in rows[1:]]
    assert meters == ["M-HOT"]


def test_br_shl_011__the_export_mirrors_the_list_filters(idn, wired):
    """The export runs the caller's own query — a status filter narrows the
    file exactly as it narrows the screen."""
    idn.seed_silvercreek()
    day = (timezone.now() - timedelta(days=3)).date().isoformat()
    seed_read(idn.silvercreek, asset_no="M-OK", address="4 Ok St", day=day)
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        flagged = a_meter(actor, asset_no="M-HI", address="5 Hi St")
        commit_read(
            actor,
            flagged["id"],
            day=day,
            value="99999",
            consumption=Decimal("999"),
            unit="kWh",
            status="high",
        )

    rows = _export_file(
        signed_in_client(*ALEX), {"resource": "reads", "filters": {"status": "flagged"}}
    )
    meters = [dict(zip(rows[0], row))["meter"] for row in rows[1:]]
    assert meters == ["M-HI"]


# ── the ROUTE SHEET (RDS-01's header button, served print-ready) ────────────


def test_route_sheet__prints_the_walk_in_order_with_meters_and_last_reads(idn):
    """GET /routes/{id}/route-sheet → print-ready HTML: route, cycle, and the
    ordered stops — position, premise/address, meter no, last read WITH UNIT."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        first = a_meter(actor, asset_no="M-4021", address="1408 Elm Street")
        second = a_meter(actor, asset_no="M-4108", address="2201 Cedar Ln")
        assert second  # the route below carries BOTH stops
        commit_read(
            actor,
            first["id"],
            day="2026-08-03",
            value="42864",
            consumption=Decimal("684"),
            unit="kWh",
        )
        cycle = services.create_cycle(
            actor, {"code": "08-A", "name": "Cycle 08-A", "frequency": "monthly"}
        )
        premises = {
            row.address_line: str(row.id)
            for row in metering_models.Premises.objects.filter(tenant=idn.silvercreek)
        }
        route = services.create_route(
            actor,
            {
                "code": "R-1",
                "name": "Downtown",
                "service_code": "electric",
                "premises_ids": [premises["1408 Elm Street"], premises["2201 Cedar Ln"]],
                "cycle_id": cycle["id"],
            },
        )
        # The ruled walk: Cedar first, Elm second (D11 — per premises).
        from apps.metering import walk_order

        walk_order.save_premises_order(
            actor,
            route_id=route["id"],
            order=[premises["2201 Cedar Ln"], premises["1408 Elm Street"]],
        )

    client = signed_in_client(*ALEX)
    response = client.get(f"/api/silvercreek/routes/{route['id']}/route-sheet")
    assert response.status_code == 200, response.content
    assert response["Content-Type"].startswith("text/html")
    html = response.content.decode()
    assert "R-1" in html and "Downtown" in html
    assert "08-A" in html
    # The stops print in the SAVED walk order, Cedar before Elm.
    assert html.index("2201 Cedar Ln") < html.index("1408 Elm Street")
    assert "M-4021" in html and "M-4108" in html
    # Rule 3: the last read prints WITH its unit; a meter never read prints
    # a dash, never a zero.
    assert "684" in html and "kWh" in html
    # Print-ready: the page carries its own print stylesheet.
    assert "@media print" in html


def test_route_sheet__cross_tenant_and_unknown_ids_are_one_404(idn):
    """HR-1: another tenant's route and a nonsense id answer identically."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    with tenant_ctx(idn.bluemesa):
        actor = metering_actor(idn.bluemesa)
        premise = a_meter(actor, asset_no="M-BM-9", address="9 Mesa Rd")
        assert premise  # the route below belongs to Blue Mesa
        bm_premises = metering_models.Premises.objects.get(
            tenant=idn.bluemesa, address_line="9 Mesa Rd"
        )
        bm_route = services.create_route(
            actor,
            {"code": "BM-1", "service_code": "electric", "premises_ids": [str(bm_premises.id)]},
        )

    client = signed_in_client(*ALEX)
    theirs = client.get(f"/api/silvercreek/routes/{bm_route['id']}/route-sheet")
    nonsense = client.get("/api/silvercreek/routes/not-a-route/route-sheet")
    assert theirs.status_code == 404
    assert nonsense.status_code == 404


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W5 (Reads list + detail page lane) — US-MET-012/013 §3 cases
# generated: 2026-08-26 by the CR-038 W5 lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(frontend half in 07-frontend tests) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest — see the lane report
# exceptions: the export deliberately has NO archive opt-in — US-MET-012 TC-10
#   scopes an export to the 2-yr hot window in as many words, and the ratified
#   POST /exports body carries q/sort/dir/filters only (no top-level archive
#   param) — REPORTED, not invented
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
