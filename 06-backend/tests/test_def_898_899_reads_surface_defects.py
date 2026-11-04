# ── Trace ──────────────────────────────────────────────
# Defects: DEF-898 (the route sheet can only be printed for a ROUTE, and a
#          clerk works CYCLES too — PO: "allow route of Cycle - both") ·
#          DEF-899 (the reading detail page prints a raw database key where a
#          person's name belongs) · DEF-951 (the co-signer had the identical
#          bug one row down and nobody had reported it)
# Rules:   BR-MET-162 (a sheet is printed for a route OR a cycle; a cycle
#          sheet is the union of its routes' stops in walk order) ·
#          BR-MET-163 (the compliance stamp renders people as people) ·
#          BR-MET-010 (one cycle per route) · BR-MET-076 (draft/active/
#          inactive) · D11 (a stop is a PREMISES) · BR-AUD-003 (a null actor
#          is a system job — the id renders, the name stays null) ·
#          CLAUDE.md rule 1 (tenant scoping — HR-1's one 404)
# Screens: S25 (the Route sheet dialog) · S29 (compliance metadata)
# ───────────────────────────────────────────────────────
"""DEF-898 + DEF-899 — the two reads-surface defects with a backend half.

RED-FIRST RECORD (2026-08-27, this lane). Every test below was run against the
pre-lane tree first and every one failed:

  · the cycle-sheet tests failed at the **404** — `/cycles/{id}/route-sheet`
    was not a mounted path, and `apps.metering.route_sheet` carried no
    `render_cycle_sheet` at all;
  · the uploader-name tests failed on `KeyError: 'uploaded_by_name'` —
    `read_batch_dict` served the bare UUID and nothing else, which is exactly
    what the screen printed.

⚠ **THE SECOND RED IS THE INTERESTING ONE.** `read_batch_dict` served
`uploaded_by` as a valid, populated, correctly-typed string the whole time, so
no existing test COULD have gone red on this defect — a UUID and a name are the
same type to every check in this repo. The assertion that finds it has to be
*"the name is present AND it is not the key"*, which is the shape below.
"""

from decimal import Decimal

import pytest
from django.apps import apps as django_apps

from apps.identity import models as identity_models
from apps.metering import models as metering_models
from apps.metering import route_sheet, selectors, services

from tests.test_cr038_w5_reads_surface import metering_actor
from tests.test_us_idn_helpers import (  # noqa: F401 — fixture imports
    api_post,
    idn,
    signed_in_client,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

ALEX = ("alex@silvercreek.example", "Canyon2026rapids")


def _asset_id(tenant, asset_no):
    return (
        django_apps.get_model("assets", "Asset")
        .objects.get(tenant_id=tenant.id, asset_no=asset_no)
        .id
    )


def _two_route_cycle(actor, tenant):
    """A cycle with TWO active routes on it, plus a spare premises for the
    off-cycle case."""
    elm = a_meter(actor, asset_no="M-4021", address="1408 Elm Street")
    a_meter(actor, asset_no="M-4108", address="2201 Cedar Ln")
    a_meter(actor, asset_no="M-4310", address="77 Industrial Way")
    commit_read(
        actor,
        elm["id"],
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
        for row in metering_models.Premises.objects.filter(tenant=tenant)
    }
    # ⚠ THE ROUTES ARE CREATED OUT OF ORDER ON PURPOSE — `R-2` first — so the
    # `code` ordering BR-MET-162 (3) promises is PROVED rather than accidentally
    # satisfied by insertion order.
    second = services.create_route(
        actor,
        {
            "code": "R-2",
            "name": "Cedar",
            "service_code": "electric",
            "premises_ids": [premises["2201 Cedar Ln"]],
            "cycle_id": cycle["id"],
        },
    )
    first = services.create_route(
        actor,
        {
            "code": "R-1",
            "name": "Downtown",
            "service_code": "electric",
            "premises_ids": [premises["1408 Elm Street"]],
            "cycle_id": cycle["id"],
        },
    )
    return cycle, first, second, premises


def _a_batch(tenant):
    """One posted batch to stamp. `commit_read` writes history DIRECTLY and
    carries no batch, so the compliance stamp under test is created here."""
    return metering_models.ReadImportBatch.objects.create(
        tenant_id=tenant.id,
        batch_no="RUN-9001",
        source_kind="file",
        status="posted",
        file_name="reads_08A.csv",
        certified_by_uploader=True,
    )


# ── DEF-898 · BR-MET-162 — the cycle is a way IN, not only a fact ──────────


def test_def_898__a_cycle_sheet_prints_every_active_route_in_code_order(idn):
    """The union of the cycle's routes, sectioned by route, routes in `code`
    order — so two prints of the same cycle are identical (BR-MET-162 (3))."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        cycle, first, second, _ = _two_route_cycle(actor, idn.silvercreek)

    client = signed_in_client(*ALEX)
    response = client.get(f"/api/silvercreek/cycles/{cycle['id']}/route-sheet")
    assert response.status_code == 200, response.content
    assert response["Content-Type"].startswith("text/html")
    html = response.content.decode()

    # The CYCLE is the sheet now, not a line in some route's header.
    assert "Cycle sheet" in html and "08-A" in html
    assert "2 route(s)" in html and "2 stop(s)" in html
    # Both active routes are sections, R-1 before R-2 — code order, NOT the
    # order they were created in (R-2 was created first).
    assert html.index("R-1") < html.index("R-2")
    assert "1408 Elm Street" in html and "2201 Cedar Ln" in html
    # Each section is a real walk sheet: the meters and the write-in column.
    assert "M-4021" in html and "M-4108" in html
    assert "write-in" in html
    # Rule 3 — the last read still prints WITH its unit.
    assert "684" in html and "kWh" in html
    assert "@media print" in html
    assert first["id"] and second["id"]


def test_def_898__a_route_off_the_cycle_is_not_on_its_sheet(idn):
    """BR-MET-010: membership is `routes.cycle_id`. A route on NO cycle — a
    real state, and the one a clerk would be surprised to find printed — is
    not on any cycle's sheet."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        cycle, _, _, premises = _two_route_cycle(actor, idn.silvercreek)
        services.create_route(
            actor,
            {
                "code": "R-9",
                "name": "Industrial",
                "service_code": "electric",
                "premises_ids": [premises["77 Industrial Way"]],
            },
        )

    client = signed_in_client(*ALEX)
    response = client.get(f"/api/silvercreek/cycles/{cycle['id']}/route-sheet")
    # ⚠ **THE 200 AND THE POSITIVE ASSERTIONS ARE LOAD-BEARING, and the RED
    # proof is what found that out.** With the route deleted from `urlpatterns`
    # this test PASSED — a 404 body contains neither "R-9" nor the address, so
    # a test built only from `not in` cannot tell "correctly excluded" from
    # "there is no page at all". DEF-182's shape: a check whose output cannot
    # distinguish pass from fail is worse than no check, because it is trusted.
    assert response.status_code == 200, response.content
    html = response.content.decode()
    assert "R-1" in html and "1408 Elm Street" in html  # the sheet really rendered
    assert "R-9" not in html
    assert "77 Industrial Way" not in html


def test_def_898__an_empty_cycle_says_so_rather_than_printing_a_blank_page(idn):
    """A cycle with no active routes is a CONFIGURATION fact somebody must fix,
    so the sheet states it. A blank page reads as a broken feature."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        cycle = services.create_cycle(
            actor, {"code": "09-Z", "name": "Cycle 09-Z", "frequency": "monthly"}
        )

    client = signed_in_client(*ALEX)
    response = client.get(f"/api/silvercreek/cycles/{cycle['id']}/route-sheet")
    assert response.status_code == 200
    html = response.content.decode()
    assert "no active routes" in html
    assert "0 route(s)" in html


def test_def_898__cross_tenant_and_unknown_cycle_ids_are_one_404(idn):
    """HR-1, exactly as the route sheet already answers: another tenant's cycle
    and a nonsense id are indistinguishable."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    with tenant_ctx(idn.bluemesa):
        actor = metering_actor(idn.bluemesa)
        theirs = services.create_cycle(
            actor, {"code": "BM-A", "name": "Blue Mesa A", "frequency": "monthly"}
        )

    client = signed_in_client(*ALEX)
    cross = client.get(f"/api/silvercreek/cycles/{theirs['id']}/route-sheet")
    unknown = client.get("/api/silvercreek/cycles/01920000-0000-7000-8000-000000000000/route-sheet")
    assert cross.status_code == 404
    assert unknown.status_code == 404


def test_def_898__the_route_sheet_is_unchanged(idn):
    """The refactor that made the cycle sheet possible must not have moved the
    ROUTE sheet, which is what CR-038 W5 shipped and what SET-06D prints."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        _, first, _, _ = _two_route_cycle(actor, idn.silvercreek)

    client = signed_in_client(*ALEX)
    response = client.get(f"/api/silvercreek/routes/{first['id']}/route-sheet")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Route sheet · R-1 · Downtown" in html
    assert "08-A" in html  # the cycle is still a FACT of a route sheet
    assert "1 stop(s)" in html
    assert "Generated " in html
    assert "M-4021" in html and "684" in html and "kWh" in html
    # And the other route's stop is NOT on it — a route sheet is one walk.
    assert "2201 Cedar Ln" not in html


def test_def_898__the_cycle_sheet_data_is_pure_and_names_its_routes(idn):
    """The payload behind the page, so the shape is pinned without HTML."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        cycle, _, _, _ = _two_route_cycle(actor, idn.silvercreek)
        data = route_sheet.cycle_sheet_data(cycle["id"])
    assert data["cycle"]["code"] == "08-A"
    assert [section["route"]["code"] for section in data["routes"]] == ["R-1", "R-2"]
    # Each section is a FULL route-sheet payload — same keys, same facts.
    assert data["routes"][0]["stops"][0]["address"] == "1408 Elm Street"


# ── DEF-899 / DEF-951 · BR-MET-163 — people are rendered as people ─────────


def test_def_899__the_batch_stamp_serves_the_uploaders_NAME(idn):
    """The compliance stamp printed `Uploaded by  01a01d99-…` to a clerk who
    wanted to know WHO uploaded the batch. The name is served now, resolved
    through audit's own published seam."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        user = identity_models.User.objects.get(id=actor.id)
        batch = _a_batch(idn.silvercreek)
        batch.uploaded_by_id = user.id
        batch.save(update_fields=["uploaded_by"])
        compliance = selectors.read_batch_dict(batch)["compliance"]

    # The RAW ID IS STILL SERVED — the evidence does not move (BR-MET-163 (4)).
    assert compliance["uploaded_by"] == str(user.id)
    # …and the NAME rides beside it, which is what a person is shown.
    assert compliance["uploaded_by_name"] == user.full_name
    assert compliance["uploaded_by_name"] not in ("", None)
    # The assertion that would have caught the defect, said plainly: the value
    # a person is shown is not the key.
    assert compliance["uploaded_by_name"] != compliance["uploaded_by"]


def test_def_899__an_unresolvable_uploader_serves_a_null_name_not_a_guess(idn):
    """BR-AUD-003's posture, unchanged: the stamp outlives any user row. A name
    that cannot be resolved is NULL — never invented, and never the id smuggled
    through the name field."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        # The tenant needs its metering actor seeded even though this case
        # deliberately leaves the batch UNSTAMPED — that absence is the subject.
        metering_actor(idn.silvercreek)
        batch = _a_batch(idn.silvercreek)
        compliance = selectors.read_batch_dict(batch)["compliance"]

    assert compliance["uploaded_by"] is None
    assert compliance["uploaded_by_name"] is None
    assert compliance["cosigned_by_name"] is None


def test_def_951__the_cosigner_is_a_person_too(idn):
    """The identical defect one row down, found while fixing DEF-899 and never
    reported: `cosigned_by` renders under *Approvals* on S29, so the first
    co-signature ever written would have printed a SECOND raw primary key."""
    idn.seed_silvercreek()
    with tenant_ctx(idn.silvercreek):
        actor = metering_actor(idn.silvercreek)
        user = identity_models.User.objects.get(id=actor.id)
        batch = _a_batch(idn.silvercreek)
        batch.cosigned_by_id = user.id
        batch.save(update_fields=["cosigned_by"])
        compliance = selectors.read_batch_dict(batch)["compliance"]

    assert compliance["cosigned_by"] == str(user.id)
    assert compliance["cosigned_by_name"] == user.full_name


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-895..899 reads-UI lane (PO defects on the live app at v2.61.1)
# generated: 2026-08-27 by the DEF-895..899 lane
# checklist: A✔ B=the frontend halves ship in the same lane (RouteSheetModal, ReadDetailPage, ReadsListPage) C✔ D✔(RED first — see the module docstring) E✔ F✔ G✔ H=deferred(not a 🔒 path — no money, no RLS policy and no idempotency key is authored here)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
