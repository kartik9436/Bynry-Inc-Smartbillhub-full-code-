# ── Trace ──────────────────────────────────────────────
# Change:   CR-150-BRC09, lane BUILD-ROW — the fields
#           `05-prototype/new-connect-detail-2026-09-28/00-list.png` draws and
#           `GET /connections` did not serve. `NewConnectsTab.tsx` §4 named
#           each one and left the columns OUT rather than draw a dash on every
#           row forever; this file is the backend half landing.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE) · hard rule 2
#           (money stored 4 dp, displayed 2, rounded ONCE server-side) ·
#           BR-CUS-106 (the AGE accent threshold, PO 2026-08-25 decision D4) ·
#           BR-TEN-043/081 (the utility's own clock decides the day) ·
#           BR-MET-113 (the owner account every connection charge is tagged
#           to) · BR-SHL-010 (a screen offers nothing the server does not
#           name) · NFR-3 (server pagination; a page of 25 at T5's 40,000)
# Questions: ⚠ **OQ-CUS-12771 — OPEN, and NOTHING IS BLOCKED ON IT.**
#           `BR-CUS-106`'s seven days was ruled on `REQ-01`'s AGE column and
#           `NCT-01` was never shown. The flag is served on the ruled figure
#           rather than on a second number minted here; that row is where a
#           build-specific threshold would be decided.
# Defects:  DEF-CUS-7620 (the oldest tile counted elapsed 24-hour periods from
#           UTC now — fixed here, RED proof below) · DEF-CUS-7619 (billing
#           publishes no batched invoice position, so DUE and the owed tile
#           cannot be served — stated, never invented)
# Tests:    this file; the drawn-figure suite is tests/test_w6_connection_list.py
# ───────────────────────────────────────────────────────
"""The 2026-09-28 drawing's columns, each asserted twice: once on a build that
HAS the fact and once on a build that does not.

⚠ **THE SECOND HALF IS THE POINT.** Every field here is nullable on a real
build — a build with no owner account, no work order, no quote, no scope and
no named raiser is the ordinary state of a draft — and `DEF-127` is what a
fabricated zero costs on a screen a clerk reads money from. A suite that only
ever asserted the populated case would go green over a `$0.00`, an empty
string or a `False` standing in for *nobody has answered*.

⚠ **AND THE THRESHOLD CASES ARE ASSERTED AGAINST THE RULE'S OWN CONSTANT, NOT
AGAINST `7`.** `BR-CUS-106`'s figure lives in `apps/customers/service_request`
and the whole reason this list asks for it rather than copying it is that two
copies drift. A test carrying its own `7` would be the third copy.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.db import connection as db_connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.customers import service_request as sr_rules
from apps.metering import connection_reads as reads
from apps.metering import connections as w6
from apps.work import connection_models as work_tables

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_rls_scoped,
    iso_tenants,
    requires_postgres,
    rls,
    # ⚠ **`rls` DEPENDS ON THIS ONE AND PYTEST RESOLVES FIXTURES BY NAME IN
    # THE IMPORTING MODULE'S NAMESPACE.** Importing `rls` alone gives
    # `fixture 'rls_probe_role' not found` — an ERROR rather than a failure,
    # which is `G5`'s own hazard wearing different clothes: the case does not
    # run and a reader skimming for `failed` sees none.
    rls_probe_role,
)

pytestmark = pytest.mark.django_db


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES — a build with everything, and a build with nothing
# ════════════════════════════════════════════════════════════════════════════
def _bare_build(actor, *, address="1200 Main St", submitted=True, days_old=0, service="electric"):
    """A build with NO owner account, NO work order, NO quote and NO scope.

    This is not a contrivance: `BR-MET-113`'s column is NULL on all eight of
    the seeded Brazos Bend builds and on any build whose owner the master door
    refused (`DEF-MET-5093`), so it is the ordinary row rather than the edge.

    ⚠ **`service` IS A PARAMETER BECAUSE THE ISOLATION CASE NEEDS IT.** Brazos
    Bend runs Electric + Water and Lone Star Ridge runs Water only, and
    `add_connection_service` REFUSES a service the tenant does not run — which
    is the rule working. A helper that hard-coded `electric` would make the
    cross-tenant case fail on a validation error rather than on the thing it is
    testing, and a case that fails for the wrong reason proves nothing about
    the right one.
    """
    premises = make_premises(actor, address_line=address, services_available=[service])
    make_unit(actor, premises["id"], label="Unit 1")
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    build = work_tables.Connection.objects.get(pk=created["id"])
    w6.add_connection_service(actor, build.id, service_code=service)
    if submitted:
        w6.submit_connection(actor, build.id)
        if days_old:
            work_tables.Connection.objects.filter(pk=build.id).update(
                submitted_at=timezone.now() - timedelta(days=days_old)
            )
    build.refresh_from_db()
    return build


def _row_for(build_no_or_id, rows):
    for row in rows:
        if row["id"] == str(build_no_or_id):
            return row
    raise AssertionError(f"no row for {build_no_or_id} in {[r['id'] for r in rows]}")


# ════════════════════════════════════════════════════════════════════════════
# 1 · `CUSTOMER` — the owner account's name and number (BR-MET-113)
# ════════════════════════════════════════════════════════════════════════════
def test_cr150_row_customer_is_the_owner_accounts_name_and_number(brazos, marcus):
    """The drawn cell is two lines — *Jonas Janssen* over *AC-2026-00011* — and
    both come off the owner account through `seams.account_references`.

    ⚠ **THE NAME IS THE PRIMARY CONTACT'S**, which is what every other screen
    in this product shows: `BR-CUS-054`'s first-class customer entity is not
    built, and the selector says so. Asserting the contact's name here is
    asserting that this column agrees with the rest of the product.
    """
    from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan
    from apps.customers import services as customers_services

    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos, label="Owner unit")
        account = customers_services.create_account(marcus, _create_payload(unit["id"]))
        build = _bare_build(marcus, address="1200 Main St")
        work_tables.Connection.objects.filter(pk=build.id).update(owner_account_id=account["id"])
        rows = reads.list_connections(segment="all")["rows"]

    row = _row_for(build.id, rows)
    assert row["customer"] is not None, (
        "a build WITH an owner account must name it — a null here is the CUSTOMER "
        "column empty on every row, which is the thing DEF-CUS-6109 taught about "
        "premises one column over"
    )
    assert row["customer"]["account_no"] == account["account_no"]
    assert row["customer"]["name"] == "Elena Rivera"


def test_cr150_row_customer_is_null_and_not_an_empty_block_with_no_owner(brazos, dana):
    """⚠ **`None`, NEVER `{"name": None, "account_no": None}` AND NEVER `""`.**

    *There is no owner yet* is ONE fact. Four nulls inside a block let a screen
    read `account_no` off an object meaning *nobody has been assigned* and draw
    it as *a customer with no number*; the drawing writes *"no account yet"*
    under the name and the words are the screen's to choose, which it cannot do
    from an empty string.
    """
    with tenant_ctx(brazos):
        build = _bare_build(dana)
        rows = reads.list_connections(segment="all")["rows"]

    row = _row_for(build.id, rows)
    assert row["customer"] is None
    # And the key is PRESENT — an omitted key renders as an empty cell, which is
    # indistinguishable from an absent fact once drawn (DEF-127).
    assert "customer" in row


# ════════════════════════════════════════════════════════════════════════════
# 2 · `AGING` — `age_days`, the SERVER's accent, and ONE clock (DEF-CUS-7620)
# ════════════════════════════════════════════════════════════════════════════
def test_cr150_row_age_days_counts_from_submitted_and_is_null_with_no_date(brazos, dana):
    """§2's start rule, on the row: submitted, falling back to created.

    A draft nobody submitted has only the day somebody opened it, so `age_days`
    is `0` on a build raised today and never `None` — a `Connection` always has
    a `created_at`. `None` is reserved for the case the store cannot produce,
    and the guard here is that the field exists and answers a number.
    """
    with tenant_ctx(brazos):
        old = _bare_build(dana, address="41 Old Row", days_old=41)
        fresh = _bare_build(dana, address="1 New Row")
        unsubmitted = _bare_build(dana, address="2 Draft Row", submitted=False)
        rows = reads.list_connections(segment="all")["rows"]

    assert _row_for(old.id, rows)["age_days"] == 41
    assert _row_for(fresh.id, rows)["age_days"] == 0
    # A draft has no `submitted_at`; its age is counted from the day it was
    # opened rather than being absent.
    assert _row_for(unsubmitted.id, rows)["age_days"] == 0


def test_cr150_row_age_accent_is_the_server_answer_at_br_cus_106s_boundary(brazos, dana):
    """**BR-CUS-106, INCLUSIVE, AND READ FROM THE RULE RATHER THAN FROM 7.**

    The boundary is the half a careless reading gets wrong — `>=`, never `>` —
    so the three builds are the threshold minus one, the threshold, and the
    threshold plus one, computed from `sr_rules.AGE_ACCENT_DAYS`. Move the
    ruled figure and this test follows it; write a second figure anywhere and
    this test goes red against it.

    ⛔ **THE SCREEN MUST NOT RE-DERIVE THIS** (`AgeCell`'s rule one tab along:
    *"two thresholds is how the list and a later KPI drift apart"*). That is
    what makes the flag a served field rather than a number the row also has.
    """
    edge = sr_rules.AGE_ACCENT_DAYS
    with tenant_ctx(brazos):
        below = _bare_build(dana, address="1 Below", days_old=edge - 1)
        on = _bare_build(dana, address="2 On", days_old=edge)
        above = _bare_build(dana, address="3 Above", days_old=edge + 1)
        rows = reads.list_connections(segment="all")["rows"]

    assert _row_for(below.id, rows)["age_is_accented"] is False
    assert _row_for(on.id, rows)["age_is_accented"] is True, (
        "BR-CUS-106 is INCLUSIVE — `age_days >= AGE_ACCENT_DAYS`, never `>`"
    )
    assert _row_for(above.id, rows)["age_is_accented"] is True


def test_cr150_the_row_and_the_oldest_tile_read_one_clock(brazos, dana):
    """**DEF-CUS-7620 — the tile counted elapsed 24-hour periods from UTC now
    and the row counts the utility's own calendar days.**

    The build below is submitted at 23:00 UTC, which is 17:00 the PREVIOUS day
    in Brazos Bend's `America/Chicago`. Nine hours later the old arithmetic
    answers `0` — nine twenty-fourths of a day, truncated — while the utility
    has turned a page and is a day into the job.

    ⚠ **THE ASSERTION IS THAT THE TWO AGREE, NOT THAT EITHER IS A PARTICULAR
    NUMBER.** A row and a tile printing the same word must not be able to print
    different numbers; pinning a figure would pass the day somebody fixed one
    of the two and not the other.
    """
    with tenant_ctx(brazos):
        build = _bare_build(dana, address="19 Clock Row")
        work_tables.Connection.objects.filter(pk=build.id).update(
            submitted_at=datetime(2026, 9, 25, 23, 0, tzinfo=dt_timezone.utc)
        )
        result = reads.list_connections(segment="all")
        today, zone = reads._tenant_clock()

    row = _row_for(build.id, result["rows"])
    oldest = result["kpis"]["oldest"]
    assert oldest is not None and oldest["days"] == row["age_days"]
    # And the figure is the UTILITY'S day rather than UTC's: 23:00 UTC on the
    # 25th is 18:00 on the 25th in Chicago (CDT, UTC-5), so the count is from
    # the 25th in both — the guard is that BOTH halves were converted, which is
    # what `_age_days` does and what the old subtraction did not.
    began = datetime(2026, 9, 25, 23, 0, tzinfo=dt_timezone.utc).astimezone(zone).date()
    assert row["age_days"] == (today - began).days


def test_cr150_a_draft_row_ages_on_the_same_clock_as_a_build(brazos, dana):
    """A parked draft is a ROW of this list since `DEF-CUS-5994`, so the AGING
    column has to answer for it too — and on the same clock, or one column
    prints two arithmetics."""
    with tenant_ctx(brazos):
        rows = reads.list_connections(segment="all")["rows"]
        today, zone = reads._tenant_clock()
    for row in rows:
        if row.get("row_kind") != reads.ROW_KIND_PARKED_NEW_CONNECT:
            continue
        if row["parked_at"] is None:
            continue
        assert row["age_days"] is not None
        assert row["age_days"] >= 0


# ════════════════════════════════════════════════════════════════════════════
# 3 · THE WAITING TILE — every kind of waiting, not one literal
# ════════════════════════════════════════════════════════════════════════════
def test_cr150_waiting_on_anyone_counts_every_kind_of_waiting(brazos, dana):
    """The drawn tile is *"Waiting on someone"* and `waiting_on` is FREE TEXT.

    §2's last warning is the whole case: `Connection.waiting_on` is an
    unconstrained `TextField`, so the older `waiting_on_inspection` tile — which
    matches one literal, case-insensitively and exactly — cannot see *"site
    inspection"* or *"fire marshal"*. Four builds wait here and the literal tile
    can count exactly one of them.

    ⚠ **A BUILD WAITING ON WHITESPACE IS NOT WAITING.** `park_state` already
    reads *empty after stripping* as *not waiting*, and a tile counting a build
    whose cell renders blank is a figure no row on the page explains.
    """
    with tenant_ctx(brazos):
        for label, waiting in (
            ("A", "inspection"),
            ("B", "site inspection"),
            ("C", "fire marshal"),
            ("D", "permit"),
        ):
            build = _bare_build(dana, address=f"{label} Waiting Row")
            w6.set_waiting_on(dana, build.id, waiting_on=waiting)
        blank = _bare_build(dana, address="E Blank Row")
        work_tables.Connection.objects.filter(pk=blank.id).update(waiting_on="   ")
        not_waiting = _bare_build(dana, address="F Quiet Row")
        kpis = reads.list_connections(segment="all")["kpis"]

    assert kpis["waiting_on_anyone"] == 4, (
        "every build with ANY waiting_on value, and NOT the whitespace one nor the quiet one"
    )
    assert kpis["waiting_on_inspection"] == 1, (
        "the older tile is unchanged and still matches one literal — this is why "
        "the drawn tile needed a second figure rather than a re-reading of the "
        "first (hard-won law 2: the live tile is not taken off the page)"
    )
    assert not_waiting is not None


# ════════════════════════════════════════════════════════════════════════════
# 4 · BEHIND THE COLUMN CHOOSER — charged, mode, scope, raised by, last event
# ════════════════════════════════════════════════════════════════════════════
def test_cr150_chooser_fields_are_served_for_a_build_that_has_them(brazos, dana):
    """`quote_total` · `mode` · `scope` · `raised_by` · `last_stamped_event`.

    ⚠ **`quote_total` IS THE `{stored, display}` PAIR AND NOT A NUMBER** —
    CLAUDE.md hard rule 2: 4 decimals stored, 2 displayed, rounded ONCE on the
    server. A screen that received `1035.0` would have to round it itself,
    which is the second rounding path `DEF-088` removed.
    """
    with tenant_ctx(brazos):
        build = _bare_build(dana, address="7 Chooser Row")
        w6.create_work_order(dana, build.id, {"type": "meter set"})
        work_tables.Connection.objects.filter(pk=build.id).update(
            quote_total="1035.0000", scope="new_estate"
        )
        rows = reads.list_connections(segment="all")["rows"]

    row = _row_for(build.id, rows)
    assert row["quote_total"] == {"stored": "1035.0000", "display": "1035.00"}
    assert row["mode"] == work_tables.MODE_OUR_CREW
    assert row["scope"] == "new_estate"
    assert row["raised_by"] == dana.user.full_name
    assert row["last_stamped_event"]["what"] == "submitted"
    assert row["last_stamped_event"]["at"] is not None


def test_cr150_chooser_fields_are_absent_rather_than_zero_when_there_is_nothing(brazos, dana):
    """⚠ **A BUILD NOBODY PRICED IS NOT A BUILD THAT COSTS NOTHING.**

    `{None, None}` and never `$0.00` — `DEF-127`'s whole lesson, and the rule
    `connection_record._money` already applies to the build record's own tiles:
    *a zero reads as settled and the truth is never priced*. `mode` is `None`
    on a build with no work order rather than the wizard's step-1 default,
    because `connections.mode` is a stamp to be COPIED onto orders and not an
    answer about orders that do not exist.

    `scope` is `None` because `CR-126-BRC07` deliberately did not back-fill it:
    NULL means *nobody was asked*, which is the truth on every build raised
    before that migration.
    """
    with tenant_ctx(brazos):
        build = _bare_build(dana, address="8 Empty Row")
        rows = reads.list_connections(segment="all")["rows"]

    row = _row_for(build.id, rows)
    assert row["quote_total"] == {"stored": None, "display": None}
    assert row["mode"] is None, "no work order means no mode, not the step-1 default"
    assert row["scope"] is None


def test_cr150_row_mode_agrees_with_connections_mode(brazos, dana):
    """**THE ANTI-DRIFT CHECK FOR THE ONE RULE THIS FILE RESTATES.**

    `_modes_by_connection` + `_mode_from` is `connections.connection_mode()`'s
    rule over a batched read, because calling the real function per row is a
    query per row. Splitting a rule across two files is how two answers appear,
    so both are run over the same builds in all three shapes the rule names —
    no orders, one mode, two modes. A comment claiming they agree would be
    hard-won law 1; this is the guarantee.
    """
    with tenant_ctx(brazos):
        none_yet = _bare_build(dana, address="9 No Orders")
        one = _bare_build(dana, address="10 One Mode")
        w6.create_work_order(dana, one.id, {"type": "meter set"})
        two = _bare_build(dana, address="11 Two Modes")
        first = w6.create_work_order(dana, two.id, {"type": "dig"})
        w6.create_work_order(dana, two.id, {"type": "meter set"})
        work_tables.WorkOrder.objects.filter(pk=first["id"]).update(mode="external")

        builds = [none_yet, one, two]
        modes = reads._modes_by_connection(reads._tenant_id(), [build.id for build in builds])
        for build in builds:
            assert reads._mode_from(modes.get(build.id) or set()) == w6.connection_mode(build), (
                f"the batched read and connection_mode() disagree on {build.id}"
            )
        # …and the third shape really is `mixed`, so the case is not vacuous.
        assert reads._mode_from(modes.get(two.id)) == "mixed"


def test_cr150_last_stamped_event_is_the_newest_stamp_and_names_which(brazos, dana):
    """The build's own stamped facts, newest first — and NOT the audit trail.

    ⛔ The History tab reads `audit.selectors.entity_trail`, which takes ONE
    entity id; a list column calling it per row would be a query per row to
    draw one optional cell, and audit publishes no many-id read (§5.3 reports
    that gap already). So this answers from columns the row already carries,
    and the field is named `last_stamped_event` so nobody later reads it as the
    trail's newest line.
    """
    with tenant_ctx(brazos):
        build = _bare_build(dana, address="12 Event Row")
        rows = reads.list_connections(segment="all")["rows"]
        assert _row_for(build.id, rows)["last_stamped_event"]["what"] == "submitted"

        w6.hold_connection(dana, build.id, reason="permit")
        rows = reads.list_connections(segment="all")["rows"]
        assert _row_for(build.id, rows)["last_stamped_event"]["what"] == "held"

        w6.cancel_connection(dana, build.id, reason="withdrawn")
        rows = reads.list_connections(segment="all")["rows"]
        assert _row_for(build.id, rows)["last_stamped_event"]["what"] == "cancelled"


# ════════════════════════════════════════════════════════════════════════════
# 5 · `DUE` AND THE OWED TILE — DEF-CUS-7619, STATED AND NEVER INVENTED
# ════════════════════════════════════════════════════════════════════════════
def test_cr150_the_owed_tile_is_null_with_its_reason_and_never_a_zero(brazos, dana):
    """**EXACTLY ONE OF THE FIGURE AND THE REASON IS EVER SET** — the shape
    `notices.stage_days` already uses, asserted in both directions.

    `$0.00` on this tile reads as *every build is paid for*, which is `DEF-127`
    exactly, on a screen a clerk chases money from. Until billing publishes a
    batched invoice position (`DEF-CUS-7619`), the honest answer is nothing
    with a sentence beside it.
    """
    with tenant_ctx(brazos):
        _bare_build(dana, address="13 Owed Row")
        kpis = reads.list_connections(segment="all")["kpis"]

    assert kpis["owed_on_open_builds"] is None
    assert kpis["owed_on_open_builds"] != 0
    reason = kpis["owed_on_open_builds_unavailable"]
    assert reason is not None
    assert reason["tracks"] == "DEF-CUS-7619"
    assert (kpis["owed_on_open_builds"] is None) != (reason is None)


def test_cr150_no_row_carries_a_due_figure_the_product_cannot_compute(brazos, dana):
    """⛔ **THE COLUMN IS ABSENT RATHER THAN EMPTY, AND THAT IS DELIBERATE.**

    A `due` key holding `{None, None}` on all 25 rows would be 25 copies of one
    sentence, and the screen's `BR-SHL-010` reading of *undeclared capability
    is not rendered* is what keeps the column off the page. The absence is
    stated ONCE, on the tile. This asserts the key is not there, so the day
    billing's read lands a lane adds it in one place and this test names itself.
    """
    with tenant_ctx(brazos):
        _bare_build(dana, address="14 No Due Row")
        rows = reads.list_connections(segment="all")["rows"]

    assert rows, "the fixture must produce a row or this case is vacuous"
    for row in rows:
        assert "due" not in row, (
            "a DUE figure appeared on a list row — if billing now publishes a "
            "batched invoice position, close DEF-CUS-7619 and rewrite this case "
            "to assert the figure; do not delete it"
        )


# ════════════════════════════════════════════════════════════════════════════
# 6 · THE WORK ORDER'S HOLDER — TWO FACTS, NEVER ONE (the detail's Work tab)
# ════════════════════════════════════════════════════════════════════════════
def test_cr150_a_work_order_reports_crew_and_technician_separately(brazos, dana):
    """**ONE FIELD CANNOT SAY WHAT TWO SAY.**

    A crew can hold an order with nobody named on it yet, and that is the case
    that stalls a build. `work.dispatch._holder` collapses the pair — person if
    there is one, crew otherwise — which is right for a dispatcher's single
    cell and cannot distinguish *the contractor has it* from *nobody has it* in
    a column.

    ⚠ **AT MOST ONE IS EVER SET** (`ck_work_orders_one_assignee`), so the three
    shapes are: crew only, technician only, and neither.
    """
    from apps.identity.models import User
    from apps.work import models as work_models

    with tenant_ctx(brazos):
        build = _bare_build(dana, address="15 Holder Row")
        unassigned = w6.create_work_order(dana, build.id, {"type": "dig"})
        to_crew = w6.create_work_order(dana, build.id, {"type": "meter set"})
        to_person = w6.create_work_order(dana, build.id, {"type": "commission"})

        crew = work_models.Crew.objects.create(
            tenant_id=brazos.id, name="Ridge Contracting", kind="contractor"
        )
        person = User.objects.create(
            tenant_id=brazos.id, email="rae@example.com", full_name="Rae Okafor"
        )
        technician = work_models.Technician.objects.create(
            tenant_id=brazos.id, user=person, crew=crew
        )
        work_tables.WorkOrder.objects.filter(pk=to_crew["id"]).update(assignee_crew_id=crew.id)
        work_tables.WorkOrder.objects.filter(pk=to_person["id"]).update(assignee_technician_id=technician.id)
        detail = reads.connection_detail(build.id)

    orders = {order["id"]: order for order in detail["work_orders"]}

    held_by_crew = orders[str(to_crew["id"])]
    assert held_by_crew["crew"] == "Ridge Contracting"
    assert held_by_crew["crew_kind"] == "contractor"
    assert held_by_crew["technician"] is None, (
        "the crew has it and NOBODY is named — this is the case a single holder "
        "field cannot express, and it is the one that blocks a build"
    )

    held_by_person = orders[str(to_person["id"])]
    assert held_by_person["technician"] == "Rae Okafor"
    assert held_by_person["crew"] is None, (
        "the crew cell reports the ASSIGNMENT and never the technician's own "
        "crew — inferring it would make 'the crew holds this' and 'a member of "
        "that crew holds this' render identically"
    )

    nobody = orders[str(unassigned["id"])]
    assert nobody["crew"] is None and nobody["technician"] is None


# ════════════════════════════════════════════════════════════════════════════
# 7 · THE COST — the three columns must not add a query per row (NFR-3)
# ════════════════════════════════════════════════════════════════════════════
def test_cr150_the_new_columns_cost_a_fixed_number_of_queries_not_one_per_row(brazos, dana):
    """**THE N+1 GUARD, MEASURED RATHER THAN ASSERTED IN PROSE.**

    §4 already pays ~3 derivation queries per row through `connections.py`. The
    new columns must add a FIXED cost: one clock read, one grouped query for
    the modes, one seam call for the customers and one for the names. So the
    difference between a page of 3 builds and a page of 6 must be the ROW cost
    alone, and the per-row cost must not have grown by the four new cells.

    **MEASURED on this fixture, 2026-09-28** (a page of builds each with one
    unit, one service and one work order): **26 queries for a page of 3 and 38
    for a page of 6** — a slope of **4.0 per build**. With the three CR-150
    batched reads stubbed out, the page of 6 costs **36**, so the whole of this
    change is **2 queries, once, whatever the page size** (a third is added
    when any build on the page HAS an owner account, still once for the page).

    ⚠ **THE ASSERTION IS ON THE SLOPE, NOT THE TOTAL**, because the total is
    §4's existing three-per-row and would pin a number that has nothing to do
    with this change. A per-row customer lookup would move the slope; a fixed
    cost cannot.
    """
    with tenant_ctx(brazos):
        for n in range(3):
            _bare_build(dana, address=f"{n} Cost Row A")
        with CaptureQueriesContext(db_connection) as three:
            reads.list_connections(segment="all", per=50)
        for n in range(3):
            _bare_build(dana, address=f"{n} Cost Row B")
        with CaptureQueriesContext(db_connection) as six:
            reads.list_connections(segment="all", per=50)

    slope = (len(six.captured_queries) - len(three.captured_queries)) / 3
    assert slope <= 4, (
        f"each extra build costs {slope} queries. §4 budgets ~3 derivation "
        "queries per row and the CR-150 columns are all batched, so a slope "
        "above 4 means one of them is asking per row"
    )


# ════════════════════════════════════════════════════════════════════════════
# 8 · TENANT SCOPING — hard rule 1, on REAL POSTGRES
# ════════════════════════════════════════════════════════════════════════════
def test_cr150_one_utilitys_builds_never_appear_in_anothers_list(brazos, lonestar, dana, erin):
    """**HARD RULE 1, THROUGH THE READ A CLERK ACTUALLY CALLS.**

    The RLS half is proved by `test_w6_rls_scopes_all_five_tables` under the
    non-superuser probe role. This is the APPLICATION half over the same rows:
    `list_connections` under Lone Star's context must not return one Brazos Bend
    build, one Brazos Bend customer name, or one Brazos Bend figure in a tile —
    and the new columns are exactly where a leak would show, because each one
    reaches into another module for its answer.
    """
    with tenant_ctx(brazos):
        theirs = _bare_build(dana, address="16 Brazos Row", days_old=12)
        w6.set_waiting_on(dana, theirs.id, waiting_on="permit")
    with tenant_ctx(lonestar):
        ours = _bare_build(erin, address="17 Lone Star Row", service="water")
        result = reads.list_connections(segment="all")

    ids = {row["id"] for row in result["rows"]}
    assert str(ours.id) in ids
    assert str(theirs.id) not in ids, "a build crossed a tenant boundary"
    # The tiles are aggregates over the whole tenant set and are the other place
    # a cross-tenant row would show up as a number with no row behind it.
    assert result["total"] == len(result["rows"])
    assert result["kpis"]["waiting_on_anyone"] == 0, (
        "Lone Star has no waiting build; a 1 here is Brazos Bend's permit "
        "counted into another utility's tile"
    )
    for row in result["rows"]:
        assert row["customer"] is None or row["customer"]["account_no"] is not None


@pytest.mark.isolation
@requires_postgres
def test_cr150_the_database_refuses_the_cross_tenant_read_too(
    rls,
    dana,
    erin,
    brazos,
    lonestar,  # noqa: F811
):
    """**THE SAME GUARANTEE ONE LAYER DOWN, AND IT CANNOT BE PROVED ON SQLITE.**

    `config/settings/test.py` hardcodes in-memory SQLite, which has no row-level
    security at all — `G5` once called 192 skips a pass, and a suite that cannot
    hold a guarantee is not evidence for it (hard-won law 14's neighbour). This
    case therefore SKIPS loudly off PostgreSQL and, when it runs, runs under the
    NOLOGIN NOSUPERUSER NOBYPASSRLS probe role, because a superuser bypasses the
    very policies it would be testing.
    """
    with tenant_ctx(brazos):
        _bare_build(dana, address="18 Brazos RLS Row")
    with tenant_ctx(lonestar):
        _bare_build(erin, address="19 Lone Star RLS Row", service="water")
    rls.assert_is_a_real_proof()
    assert_rls_scoped(rls, "connections", owner=brazos, intruder=lonestar)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-150-BRC09 · 05-prototype/new-connect-detail-2026-09-28/00-list.png
#         (the drawing of record, read as an IMAGE — B14 rule 42) and its
#         README · 07-frontend/src/features/customers/NewConnectsTab.tsx §4,
#         which names the field each drawn column needs
# generated: 2026-09-28 by lane BUILD-ROW
# checklist: A✔ B=n/a(no frontend half in this lane — the columns are the list
#         lane's to turn on, and the report names them) C✔ D✔ E=n/a F✔ G✔
#         H=deferred(PO 2026-08-09)
# exceptions: (1) **`DUE` AND `owed_on_open_builds` ARE NOT SERVED** —
#         `DEF-CUS-7619`. Billing publishes `invoice_detail` for ONE id and no
#         batched position, so a 25-row page would be 25 calls; the tile is
#         null beside its reason and no row carries a `due` key at all. Both
#         are asserted here so the day billing's read lands the cases name
#         themselves · (2) **the age accent reuses `BR-CUS-106`'s seven days,
#         which was ruled on `REQ-01` and not on this screen** —
#         `OQ-CUS-12771`, OPEN, nothing stubbed and nothing blocked. The
#         alternative was minting a second threshold, which is the drift the
#         rule's own single-source design exists to prevent · (3) the isolation
#         case at the DATABASE layer SKIPS off PostgreSQL by design and says so
#         · (4) the cost case asserts the SLOPE and not a total, because the
#         total is §4's pre-existing per-row derivation budget
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
