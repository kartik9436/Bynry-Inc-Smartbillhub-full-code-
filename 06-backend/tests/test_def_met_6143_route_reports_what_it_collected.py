# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-6143 — a collected read's route follows CURRENT membership
#           on every screen a clerk reads, so BR-MET-081's "collected reads keep
#           their route" was true only of the stamp, which one delete guard read.
# Change:   CR-131-BRC07 step 2 (a route reports the readings COLLECTED on it).
# Ruling:   PO, verbatim 2026-09-22: "100" — answering whether RT-009 should
#           report the 100 readings collected on it or the 0 on its meters
#           today. Decision log 2026-09-22, "THE THREE ANSWERS THAT RE-OPEN
#           CR-131-BRC07".
# Rules:    BR-MET-081 (changes take effect next read window; collected reads
#           keep their route) · BR-MET-079 (the collection stamp) ·
#           BR-MET-011 (progress derives from committed reads) ·
#           BR-MET-074 (a membership conflict MOVES).
# ───────────────────────────────────────────────────────
"""The route a reading belongs to is the route it was COLLECTED on.

WHAT THIS PINS, AND WHY IT IS A WHOLE FILE
------------------------------------------
`DEF-MET-6143`'s own remedy sentence, quoted from the register so a later lane
cannot mistake this for an ordinary regression test:

    "A test that collects a read, moves its premises to another route, and
    asserts the reads list, the read progress and the last-read date all still
    answer the route the read was COLLECTED on — and that the receiving route
    does not inherit it."

Every pre-existing test of these three surfaces asks them about a route whose
membership has never moved, which is exactly why four screens could report a
hundred readings against the wrong route with a green suite over them.

⚠ **IT IS DEF-233's LESSON APPLIED ONE LAYER UP.** That defect installed the
rule *"any guard that reads a MUTABLE link must have a test that MUTATES that
link and then asserts the guard still fires"* — and then moved only the DELETE
GUARD onto the immutable stamp. The four REPORTING surfaces kept the mutable
link, so the rule was installed and three quarters of its subject was left out.

⚠ **THE PRINTED ROUTE SHEET IS DELIBERATELY NOT IN THIS FILE**, and that is a
judgment with a reason rather than an omission. The sheet is the walk a reader
is ABOUT TO MAKE, so it must list the meters on the route's premises TODAY. Ask
it of the collection stamp instead and a meter fitted last week — which has no
readings at all — would never print, while a meter that moved to another route
last month would send somebody to the wrong door. `CR-131-BRC07` §5 items 3 and
4 (*"add a unit … it is on the route"*, *"fit a meter. It is on the route"*)
are unsatisfiable under a stamped sheet. The sheet's fix is DERIVATION (step 3),
not the stamp.

WHAT WOULD MAKE THESE TESTS PASS WRONGLY
----------------------------------------
Asserting only that the SOURCE route keeps its readings. A filter that silently
matched everything would pass that half, so every case also asserts the
RECEIVING route does **not** inherit them — the two halves together are what
distinguish a stamp from a broken join.
"""

from datetime import date

import pytest

from apps.metering import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _premises_with_meter(actor, address, label="A"):
    premise = make_premises(actor, address_line=address)
    unit = make_unit(actor, premise["id"], label=label, services=["water"])
    asset = make_asset(
        actor, unit_id=unit["id"], service="water", unit="kgal", install_date="2026-01-05"
    )
    return premise, unit, asset


def _read_on(tenant, asset_id, route_id, day=date(2026, 7, 1)):
    """A committed read carrying the collection stamp — the shape `_post_row`
    writes, and deliberately with no import batch, because that is the shape
    every read on the shipped fixture has."""
    return models.MeterRead.objects.create(
        tenant_id=tenant.id,
        asset_id=asset_id,
        route_id=route_id,
        read_at=day,
        unit="kgal",
        source="manual",
    )


def _two_routes_and_a_read(actor, tenant):
    """One premises with one meter, read on `WALKED`, then moved to `TOOK-IT`.

    Both routes are ACTIVE, because `BR-MET-074`'s move is what an active route
    does and a draft is refused (`DEF-219`). The move goes through the product's
    own door — `services.update_route` — never a table write, so this test
    exercises what the wizard does.
    """
    premise, _unit, asset = _premises_with_meter(actor, "1 Collected Way")
    walked = services.create_route(
        actor,
        {
            "code": "WALKED",
            "service_code": "water",
            "status": "active",
            "premises_ids": [premise["id"]],
        },
    )
    read = _read_on(tenant, asset["id"], walked["id"])
    took_it = services.create_route(
        actor, {"code": "TOOK-IT", "service_code": "water", "status": "active"}
    )
    services.update_route(actor, took_it["id"], {"premises_ids": [premise["id"]]})
    return walked, took_it, read


def test_the_stamp_survives_the_move_and_the_projection_does_not(brazos, dana):
    """The premise of every case below, asserted rather than assumed.

    If the move did not actually re-point `service_points.route_id`, the three
    surfaces would pass for the wrong reason — so both halves are stated here
    once, and the other tests can then be about the surfaces alone.
    """
    with tenant_ctx(brazos):
        walked, took_it, _read = _two_routes_and_a_read(dana, brazos)
        assert models.MeterRead.objects.filter(route_id=walked["id"]).count() == 1
        assert models.MeterRead.objects.filter(route_id=took_it["id"]).count() == 0
        # the live projection DID move — this is what used to drag the reads
        assert models.ServicePoint.objects.filter(route_id=walked["id"]).count() == 0
        assert models.ServicePoint.objects.filter(route_id=took_it["id"]).count() == 1


def test_s25_reads_list_answers_the_route_it_was_collected_on(brazos, dana):
    """S25 filtered by route. Was 1 → 0 on the walked route before the fix."""
    with tenant_ctx(brazos):
        walked, took_it, _read = _two_routes_and_a_read(dana, brazos)
        kept = selectors.read_list(
            filters={"route": str(walked["id"])}, include_archive=True
        ).count()
        inherited = selectors.read_list(
            filters={"route": str(took_it["id"])}, include_archive=True
        ).count()
        assert kept == 1, "the route that was walked lost its own reading"
        assert inherited == 0, "the receiving route inherited a reading it never collected"


def test_read_progress_counts_what_was_collected(brazos, dana):
    """`BR-MET-011` progress. Was 1 → 0 on the walked route before the fix."""
    with tenant_ctx(brazos):
        walked, took_it, _read = _two_routes_and_a_read(dana, brazos)
        assert services.collected_read_count_impl(route_id=walked["id"]) == 1
        assert services.collected_read_count_impl(route_id=took_it["id"]) == 0


def test_last_read_completion_answers_the_route_it_was_collected_on(brazos, dana):
    """The route's last-read date. Was a date → None before the fix."""
    with tenant_ctx(brazos):
        walked, took_it, _read = _two_routes_and_a_read(dana, brazos)
        last = services.last_read_completion_impl(walked["id"])
        assert last is not None and last.date() == date(2026, 7, 1)
        assert services.last_read_completion_impl(took_it["id"]) is None


def test_an_unstamped_reading_is_absent_from_the_route_filter_and_that_is_the_stated_cost(
    brazos, dana
):
    """⚠ **THE COST THE RULING MAKES US STATE, PINNED SO IT CANNOT BE DENIED
    LATER.** A reading collected before `metering/0012` carries no stamp, so it
    belongs to NO route and leaves the route filter entirely. On the seeded
    fixture that is 0 of 516 readings; on a tenant that predates the column it
    is not zero, which is why the release note and the screen say so.

    It is asserted rather than left as prose because an absence is invisible to
    every check this repository has, and a later lane "fixing" it by falling
    back to the live join would silently restore `DEF-MET-6143`.
    """
    with tenant_ctx(brazos):
        premise, _unit, asset = _premises_with_meter(dana, "9 Before The Column")
        route = services.create_route(
            dana,
            {
                "code": "OLD-READS",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        unstamped = _read_on(brazos, asset["id"], None, day=date(2026, 6, 1))
        assert unstamped.route_id is None
        assert selectors.read_list(
            filters={"route": str(route["id"])}, include_archive=True
        ).count() == 0
        assert services.collected_read_count_impl(route_id=route["id"]) == 0
        # …and it is still a reading. It has simply not got a route.
        assert selectors.read_list(include_archive=True).filter(pk=unstamped.pk).exists()


def test_the_route_column_and_the_route_filter_agree_after_a_move(brazos, dana):
    """`DEF-045`'s own requirement, held at the new grain.

    That defect's test is named *"the route filter and the route column
    agree"*, and the reason is a clerk who narrows to one route and then reads
    a different one in the column has been told two things about one row. The
    filter moved onto the collection stamp; if the column had stayed on
    `asset.service_point.route` the two would disagree on every row whose
    premises has moved since it was read — which is `DEF-045` again, wearing
    this ruling's clothes.
    """
    with tenant_ctx(brazos):
        walked, took_it, _read = _two_routes_and_a_read(dana, brazos)
        rows = [
            selectors.read_dict(row)
            for row in selectors.read_list(
                filters={"route": str(walked["id"])}, include_archive=True
            )
        ]
        assert len(rows) == 1
        assert rows[0]["route"] == "WALKED", "the column named a route the filter did not"
        assert rows[0]["route_id"] == str(walked["id"])
        assert (
            selectors.read_list(filters={"route": str(took_it["id"])}, include_archive=True).count()
            == 0
        )


def test_an_unstamped_reading_renders_a_blank_route_cell(brazos, dana):
    """The VISIBLE half of the cost the PO accepted, pinned on screen.

    A reading collected before `metering/0012` is absent from the route filter,
    and the row itself must say why by carrying no route rather than borrowing
    one from wherever its meter happens to be today. A borrowed value would be
    the more comfortable answer and it is the one this ruling forbids.
    """
    with tenant_ctx(brazos):
        premise, _unit, asset = _premises_with_meter(dana, "11 No Stamp Rd")
        services.create_route(
            dana,
            {
                "code": "HAS-POINT",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        unstamped = _read_on(brazos, asset["id"], None, day=date(2026, 6, 2))
        rendered = selectors.read_dict(models.MeterRead.objects.get(pk=unstamped.pk))
        assert rendered["route"] is None
        assert rendered["route_id"] is None
        # …and the meter IS on a route today. The blank is the point.
        assert models.ServicePoint.objects.filter(unit__premises_id=premise["id"]).exclude(
            route_id=None
        ).exists()
