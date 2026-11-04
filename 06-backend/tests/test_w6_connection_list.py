# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W6 task 6.12 — `NCT-01` the New Connect worklist, BACKEND
#           half. `GET /connections` + `apps/metering/connection_reads.py`.
#           Screen: S86 (no frontend half in this lane — REPORTED).
# Rules:    B18 §5.4.1 (the five KPI tiles) · §5.4.2 (columns · search · the
#           sort footnote) · §5.4.8 (the eight seeded rows — the fixture below
#           IS that table) · §5.4.9 `NCT-01` · BR-SHL-011 (list grammar: fall
#           back or clamp, never error) · CLAUDE.md hard rule 1 (tenant scoping)
# Questions: ⛔ OQ-371 (which exclusive segment holds a build that is
#           `partly_activated` AND waiting) — OPEN. `segment=all` only; the
#           tests below assert that NO segment rule exists to be got wrong.
# ───────────────────────────────────────────────────────
"""The worklist, pinned to the eight rows the PO's own screen draws.

B18 §5.4.1 draws five KPI figures and defines no formula for any of them, so
§5.4.8's eight rows are the only published statement of what each one means.
This file rebuilds those eight rows in the product and asserts the drawn figures
come back out — which is what makes the arithmetic the DESIGN's and not
`connection_reads.py`'s own invention:

    CON-26-0110  1 unit   5 of 5  Aug 14  —            activated
    CON-26-0119  1 unit   5 of 9  Sep 08  permit       on_hold
    CON-26-0121  1 unit   2 of 5  Sep 15  materials    in_progress
    CON-26-0126  1 unit   3 of 9  Sep 22  inspection   partly_activated
    CON-26-0117  25 units 5 of 7  Sep 30  inspection   partly_activated
    CON-26-0128  1 unit   2 of 5  Oct 02  —            partly_activated
    CON-26-0124  1 unit   0 of 7  Oct 12  —            requested
    CON-26-0122  12 units 1 of 6  Nov 01  site access  in_progress

    → OPEN 7 · WAITING ON INSPECTION 2 · PARTLY ACTIVATED 3 ·
      UNITS AWAITING ACTIVATION 42 · OLDEST 19 days (CON-26-0119, permit)

⚠ **THE SERVICES ARE NOT THE DRAWN ONES AND CANNOT BE.** The drawn rows carry
gas, sewer, trash and battery; Brazos Bend runs **Electric + Water** and
`add_connection_service` refuses a service the tenant does not run — correctly.
Every figure asserted here is a count of UNITS, ORDERS, STATES or DATES and none
of them is a count of services, so the substitution changes no assertion. The
one thing it does change is the `SERVICES` badge set, which is asserted as what
was actually built rather than as `E W G`.
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.metering import api as metering_api
from apps.metering import connection_reads as reads
from apps.metering import connections as w6
from apps.work import connection_models as work_tables

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    api_call,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── the fixture: B18 §5.4.8, row by row ─────────────────────────────────────
#: (connection_no, address, units, orders_done, orders_total, target,
#:  waiting_on, shape, days_since_submitted)
#:
#: `days_since_submitted` is not drawn per row — only the OLDEST tile's *"19
#: days · CON-26-0119"* is. `CON-26-0110` is backdated FURTHEST (30 days) on
#: purpose: it is the one finished build, so if it ever surfaced as the oldest
#: the tile would be reporting a build nobody is waiting on.
DRAWN_ROWS = (
    ("CON-26-0110", "3450 Oak Ridge Dr", 1, 5, 5, date(2026, 8, 14), None, "activated", 30),
    ("CON-26-0119", "77 Foundry Row", 1, 5, 9, date(2026, 9, 8), "permit", "on_hold", 19),
    ("CON-26-0121", "14 Willow Bend", 1, 2, 5, date(2026, 9, 15), "materials", "in_progress", 12),
    ("CON-26-0126", "8 Quarry Lane", 1, 3, 9, date(2026, 9, 22), "inspection", "partly", 11),
    ("CON-26-0117", "500 Main Street", 25, 5, 7, date(2026, 9, 30), "inspection", "partly", 9),
    ("CON-26-0128", "240 Sable Court", 1, 2, 5, date(2026, 10, 2), None, "partly", 7),
    ("CON-26-0124", "12 Harbour View", 1, 0, 7, date(2026, 10, 12), None, "requested", 4),
    (
        "CON-26-0122",
        "Kestrel Park ph. 2",
        12,
        1,
        6,
        date(2026, 11, 1),
        "site access",
        "in_progress",
        2,
    ),
)


def _build_row(actor, *, no, address, units, done, orders, target, waiting_on, shape, age_days):
    """One drawn row, built through the real write paths.

    Multi-unit builds take ELECTRIC per unit and WATER at the premise
    (`unit_id=None`), which is B18 §8.2's own shape — *"a per-premise main tap
    belongs to the build, not to any one of its 25 units"* — and keeps the row
    count linear in units instead of doubling it.
    """
    premises = make_premises(actor, address_line=address)
    unit_ids = [
        make_unit(actor, premises["id"], label=f"{no} unit {n + 1}")["id"] for n in range(units)
    ]
    created = w6.create_connection(
        actor, {"premises_id": premises["id"], "target_activation": target}
    )
    connection = work_tables.Connection.objects.get(pk=created["id"])
    work_tables.Connection.objects.filter(pk=connection.id).update(connection_no=no)

    electric = [
        w6.add_connection_service(actor, connection.id, service_code="electric", unit_id=unit_id)[
            "id"
        ]
        for unit_id in unit_ids
    ]
    water = [w6.add_connection_service(actor, connection.id, service_code="water")["id"]]
    w6.submit_connection(actor, connection.id)

    if shape == "activated":
        for row_id in [*electric, *water]:
            w6.transition_service(actor, row_id, work_tables.SVC_ACTIVATED)
    elif shape == "partly":
        for row_id in electric:
            w6.transition_service(actor, row_id, work_tables.SVC_ACTIVATED)
    elif shape in ("in_progress", "on_hold"):
        for row_id in electric:
            w6.transition_service(actor, row_id, work_tables.SVC_IN_PROGRESS)
    # "requested" — every service left pending, which is CON-26-0124's `0 of 7`.

    if shape == "on_hold":
        w6.hold_connection(actor, connection.id, reason=waiting_on)
    elif waiting_on is not None:
        w6.set_waiting_on(actor, connection.id, waiting_on=waiting_on)

    order_ids = [
        w6.create_work_order(actor, connection.id, {"type": f"step {n + 1}"})["id"]
        for n in range(orders)
    ]
    if done:
        work_tables.WorkOrder.objects.filter(pk__in=order_ids[:done]).update(state=work_tables.WO_COMPLETED)

    # Backdated AFTER submission, because `submit_connection` stamps `now`.
    work_tables.Connection.objects.filter(pk=connection.id).update(
        submitted_at=timezone.now() - timedelta(days=age_days)
    )
    connection.refresh_from_db()
    return connection


def _seed_the_drawn_list(actor):
    """All eight rows of B18 §5.4.8."""
    return {
        row[0]: _build_row(
            actor,
            no=row[0],
            address=row[1],
            units=row[2],
            done=row[3],
            orders=row[4],
            target=row[5],
            waiting_on=row[6],
            shape=row[7],
            age_days=row[8],
        )
        for row in DRAWN_ROWS
    }


# ════════════════════════════════════════════════════════════════════════════
# ⛔ OQ-371 — THE SEGMENTS ARE NOT BUILT, AND THAT IS THE ASSERTION
# ════════════════════════════════════════════════════════════════════════════
def test_w6_list_no_segment_rule_is_shipped():
    """`CON-26-0126` is `partly_activated` AND waiting on `inspection`, the
    segments are drawn as one EXCLUSIVE strip, and nothing says which of the two
    holds it (OQ-371).

    The failure mode is not a crash — it is a build sitting quietly under the
    wrong tab on the PO's own screen with every test green — so the guard is
    that no rule EXISTS to be got wrong, not that some rule behaves.
    """
    assert not hasattr(reads, "segment_for")
    assert not hasattr(w6, "segment_for")
    # Nothing in the module maps a state, or a waiting_on, to a segment.
    for name in dir(reads):
        if name.startswith("_"):
            continue
        value = getattr(reads, name)
        if isinstance(value, dict):
            assert not (set(value) & set(work_tables.CONNECTION_STATES)), (
                f"{name} maps connection states to something — if that something is a "
                "segment, OQ-371 has been answered by a lane instead of by the PO"
            )
    assert reads.SEGMENTS_SERVED == ("all",)


@pytest.mark.parametrize("segment", ["in_progress", "waiting", "partly_activated", "done", ""])
def test_w6_list_every_segment_but_all_refuses_by_name(segment, dana, brazos):
    """Each of the four tabs `NCT-01` draws, refused with the OPEN question's id
    — the prime directive's form, and the posture
    `finance/cost-reconciliation/download` already takes for OQ-204."""
    with tenant_ctx(brazos):
        with pytest.raises(NotImplementedError) as refused:
            reads.list_connections(segment=segment)
        assert "OQ-371" in str(refused.value)


def test_w6_list_open_is_every_state_that_is_not_finished():
    """Pinned EXACTLY, so that adding a connection state token goes RED here
    rather than silently joining `open` and moving the tile's figure."""
    assert reads.OPEN_STATES == (
        work_tables.DRAFT,
        work_tables.REQUESTED,
        work_tables.IN_PROGRESS,
        work_tables.PARTLY_ACTIVATED,
        work_tables.ON_HOLD,
    )
    assert work_tables.ACTIVATED not in reads.OPEN_STATES
    assert work_tables.CANCELLED not in reads.OPEN_STATES


# ════════════════════════════════════════════════════════════════════════════
# THE FIVE KPI TILES — B18 §5.4.1's figures, over §5.4.8's eight rows
# ════════════════════════════════════════════════════════════════════════════
def test_w6_list_the_five_drawn_kpi_figures_come_out_of_the_eight_seeded_rows(dana, brazos):
    with tenant_ctx(brazos):
        _seed_the_drawn_list(dana)
        kpis = reads.list_connections(segment="all")["kpis"]

    assert kpis["open"] == 7, "OPEN 7 — eight builds, one of them finished"
    assert kpis["waiting_on_inspection"] == 2, "CON-26-0126 and CON-26-0117"
    assert kpis["partly_activated"] == 3, "CON-26-0126, CON-26-0117, CON-26-0128"
    # 1 + 1 + 1 + 25 + 1 + 1 + 12 — CON-26-0110's unit is NOT counted, because
    # that build is done and the tile reads "across the 7 open builds".
    assert kpis["units_awaiting_activation"] == 42
    # OLDEST 19 days · CON-26-0119 · waiting on permit. CON-26-0110 is 30 days
    # old and is excluded: a finished build is not what anybody is waiting on.
    assert kpis["oldest"] == {
        "days": 19,
        "connection_no": "CON-26-0119",
        "waiting_on": "permit",
    }


def test_w6_list_the_tiles_count_two_different_states_as_one_waiting_number(dana, brazos):
    """*"WAITING ON INSPECTION 2"* counts `CON-26-0126` and `CON-26-0117`, which
    do NOT share a state — which is why `waiting_on` is a column of its own
    beside STATE and not the hold's reason (B18 §5.4.9 finding 1a)."""
    with tenant_ctx(brazos):
        _seed_the_drawn_list(dana)
        result = reads.list_connections(segment="all")
    waiting = {
        row["connection_no"]: row["state"]
        for row in result["rows"]
        if row["waiting_on"] == "inspection"
    }
    assert waiting == {"CON-26-0126": work_tables.PARTLY_ACTIVATED, "CON-26-0117": work_tables.PARTLY_ACTIVATED}
    held = [row for row in result["rows"] if row["state"] == work_tables.ON_HOLD]
    assert [row["waiting_on"] for row in held] == ["permit"]
    # And two builds wait while NOT held — the finding the drawing settles.
    unheld_waiters = [
        row["connection_no"]
        for row in result["rows"]
        if row["waiting_on"] and row["state"] != work_tables.ON_HOLD
    ]
    assert sorted(unheld_waiters) == ["CON-26-0117", "CON-26-0121", "CON-26-0122", "CON-26-0126"]


def test_w6_list_an_empty_tenant_has_no_oldest_rather_than_a_zero(dana, brazos):
    """`None`, not `0 days` against no build: a fabricated zero reads as *"a
    build has been waiting no time at all"*, which is a different claim."""
    with tenant_ctx(brazos):
        result = reads.list_connections(segment="all")
    assert result["total"] == 0
    assert result["kpis"]["oldest"] is None
    assert result["kpis"]["units_awaiting_activation"] == 0


# ════════════════════════════════════════════════════════════════════════════
# THE ROWS — the drawn columns, and the drawn sort
# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# ⚠ THE DEFAULT ORDER IS `created` DESCENDING — `BR-CUS-1046`, AND THESE TWO
#   CASES ASSERTED THE ORDERING IT REPLACED (`DEF-CUS-7621`, closed 2026-09-29)
# ════════════════════════════════════════════════════════════════════════════
#
# **WHAT WAS RED, AND SINCE WHEN.** `test_..._is_sorted_by_target_date_soonest_
# first`, `test_..._a_build_with_no_target_sorts_last` and
# `test_..._endpoint_answers_the_house_envelope_with_the_kpi_strip` failed on
# one assertion each — the ROW ORDER — and had done since merge `c6caadf2f`
# (2026-09-22 14:13 +0530), which is the oldest commit in this branch's
# reachable history that touches either this file or
# `apps/metering/connection_reads.py`. Measured before anything was changed:
# `3 failed, 21 passed in 1236.53s`. None of the three was in
# `10-scripts/gates/backend_suite_known_reds.txt`.
#
# **WHICH WAS WRONG — THE RULE OR THE TEST.** The TEST, and it is not close.
# `BR-CUS-1046` (PO 2026-09-10, CONFIRMED 2026-09-12) reads, verbatim: ***"It
# should always sort it by the creation order. The new newly created entries
# should always show on the top."*** The PO then EXTENDED it the same day,
# answering `OQ-CUS-1790`: ***"(c) All eight open newest-first and the six gain
# a sort control."*** It shipped in `2.238.0`. Four independent things in this
# repository already agree with the rule and only these cases did not:
#
#   · `connection_reads.DEFAULT_SORT = "created"` / `DEFAULT_DIR = "desc"`;
#   · `connection_reads.SORTS`' own note on `target_activation` — *"The
#     ordering this tab OPENED ON until 2026-09-12 … Still available, now as
#     one click that survives a refresh"*;
#   · `NewConnectsTab.tsx`'s `defaultSort: {sort: "created", dir: "desc"}`,
#     with `TARGET` declared sortable;
#   · the on-screen footnote, rewritten in all eleven catalogues by that build
#     precisely because leaving *"Sorted by target date, soonest first"* under
#     a newest-first list would be hard-won law 1.
#
# B18 §5.4.2's footnote is the SUPERSEDED statement, and a test quoting it is
# quoting a sentence the product stopped making.
#
# ⚠ **REWRITTEN AND RENAMED, NEVER DELETED OR SKIPPED — AND THE RENAME IS HALF
# THE FIX.** `DEF-CUS-5393` records the identical pair one tab over, on the
# Requests list, with the reason: *"the fix is a rename as much as an
# assertion, and a case still called `oldest_first` that asserts newest-first
# is the next reader's trap."* So the name moved with the assertion.
#
# ⚠ **AND THE OLD ORDERING KEEPS A CASE OF ITS OWN**, because `BR-CUS-1046`'s
# SECOND clause — *"a clerk's chosen sort must still win"* — is the only
# reading under which the rule is true of this list at all. Dropping the
# target-date case would have thrown away the coverage that makes the
# supersession safe.
def test_w6_list_opens_on_what_was_just_created_not_on_the_target_date(dana, brazos):
    """`BR-CUS-1046` — newest first, with no `sort` asked for.

    The expected order is `DRAWN_ROWS` REVERSED, because `_seed_the_drawn_list`
    writes them top to bottom and `created` descending is therefore the seeding
    order run backwards. Each `_build_row` issues several writes, so no two
    rows share a `created_at` microsecond and the `-id` tie-break over random
    UUIDs is never reached.
    """
    with tenant_ctx(brazos):
        _seed_the_drawn_list(dana)
        rows = reads.list_connections(segment="all")["rows"]
    assert [row["connection_no"] for row in rows] == [row[0] for row in reversed(DRAWN_ROWS)]


def test_w6_list_target_date_soonest_first_is_still_one_click(dana, brazos):
    """`BR-CUS-1046`'s second clause — *"a clerk's chosen sort must still win"*.

    B18 §5.4.2's *"Sorted by target date, soonest first — the next thing due is
    at the top"* is no longer the DEFAULT and is still the ordering: it is one
    header press, and `SORTS["target_activation"]` is what carries it. This is
    the case the two stale ones became, rather than coverage that was dropped.
    """
    with tenant_ctx(brazos):
        _seed_the_drawn_list(dana)
        rows = reads.list_connections(segment="all", sort="target_activation", dir="asc")["rows"]
    assert [row["connection_no"] for row in rows] == [row[0] for row in DRAWN_ROWS]


def test_w6_list_a_build_with_no_target_sorts_last_under_the_target_sort(dana, brazos):
    """A missing target is not the most urgent thing on the list, **and it is
    not the stalest either** — `SORTS`' own claim is `nulls_last` in BOTH
    directions, and `order_terms` is written to preserve it when it flips a
    term. Both directions are asserted here, because a claim about two
    directions that only ever exercises one is half a check.

    ⚠ **IT PASSES `sort=` NOW, AND THAT IS THE WHOLE EDIT.** The case used to
    call `list_connections(segment="all")` and read the nulls-last rule off the
    DEFAULT ordering; since `BR-CUS-1046` the default is `created` descending,
    so it was asserting the target sort through a request that never asked for
    it (`DEF-CUS-7621`).
    """
    with tenant_ctx(brazos):
        _build_row(
            dana,
            no="CON-26-0110",
            address="3450 Oak Ridge Dr",
            units=1,
            done=5,
            orders=5,
            target=date(2026, 8, 14),
            waiting_on=None,
            shape="activated",
            age_days=30,
        )
        _build_row(
            dana,
            no="CON-26-0199",
            address="No target Ln",
            units=1,
            done=0,
            orders=1,
            target=None,
            waiting_on=None,
            shape="requested",
            age_days=1,
        )
        soonest = reads.list_connections(
            segment="all", sort="target_activation", dir="asc"
        )["rows"]
        latest = reads.list_connections(
            segment="all", sort="target_activation", dir="desc"
        )["rows"]
    assert [row["connection_no"] for row in soonest] == ["CON-26-0110", "CON-26-0199"]
    assert soonest[-1]["target_activation"] is None
    # Flipped, and the build with no date is STILL last — it has not become the
    # stalest thing on the list by having no date at all.
    assert [row["connection_no"] for row in latest] == ["CON-26-0110", "CON-26-0199"]
    assert latest[-1]["target_activation"] is None


def test_w6_list_a_row_reads_as_the_screen_draws_it(dana, brazos):
    """`CON-26-0119  77 Foundry Row  1  5 of 9  Sep 08  permit  On hold` —
    every drawn column of one row, in one assertion."""
    with tenant_ctx(brazos):
        _seed_the_drawn_list(dana)
        rows = reads.list_connections(segment="all")["rows"]
    row = next(r for r in rows if r["connection_no"] == "CON-26-0119")
    assert row["premises"]["address"] == "77 Foundry Row"
    assert row["units"] == 1
    assert row["orders"] == {"done": 5, "total": 9}
    assert row["target_activation"] == "2026-09-08"
    assert row["waiting_on"] == "permit"
    assert row["state"] == work_tables.ON_HOLD
    # The badge set is the services this build actually carries, sorted — the
    # `+1` overflow chip is the screen's, because only it knows what fits.
    assert row["services"] == ["electric", "water"]
    # `ORDERS` is a fraction and not a percentage (§5.4.2): both halves served,
    # no ratio computed here.
    assert "percent" not in row["orders"]


def test_w6_list_orders_is_done_of_total_and_the_25_unit_build_keeps_its_seven(dana, brazos):
    """`CON-26-0117` — 25 units and SEVEN orders, *"not 76"* (§8.2). The
    batching arithmetic is task 6.4's; what this asserts is that the LIST does
    not recount, multiply or expand it."""
    with tenant_ctx(brazos):
        _seed_the_drawn_list(dana)
        rows = reads.list_connections(segment="all")["rows"]
    row = next(r for r in rows if r["connection_no"] == "CON-26-0117")
    assert row["units"] == 25
    assert row["orders"] == {"done": 5, "total": 7}


def test_w6_list_units_count_only_the_units_this_build_services(dana, brazos):
    """A build's `UNITS` is what its services name, not what stands on the
    premise: a second connection on an existing block must not report the whole
    block. A per-premise service (`unit_id` NULL) adds no unit."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="12 Harbour View")
        units = [make_unit(dana, premises["id"], label=f"Flat {n}")["id"] for n in range(3)]
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        for unit_id in units[:2]:
            w6.add_connection_service(dana, created["id"], service_code="electric", unit_id=unit_id)
        w6.add_connection_service(dana, created["id"], service_code="water")  # per-premise
        w6.submit_connection(dana, created["id"])
        rows = reads.list_connections(segment="all")["rows"]
    assert len(rows) == 1
    assert rows[0]["units"] == 2, "three units stand on the premise; the build services two"


def test_w6_list_a_stale_cache_cannot_reach_the_row(dana, brazos):
    """§1 of `connection_reads`, proved rather than described.

    `connections.state` is a CACHE. A ROW reports `connection_state()` — the
    derivation — so a drifted cache can never put the wrong badge in front of a
    person. A TILE counts the cache, because *"a derived state cannot be a
    `WHERE` clause"*, which is the reason the column exists.

    This test forces the two apart deliberately. In the product they agree:
    `refresh_connection_state()` is the only writer and
    `tests/test_w6_connections.py` asserts the agreement row by row.
    """
    with tenant_ctx(brazos):
        connection = _build_row(
            dana,
            no="CON-26-0126",
            address="8 Quarry Lane",
            units=1,
            done=3,
            orders=9,
            target=date(2026, 9, 22),
            waiting_on="inspection",
            shape="partly",
            age_days=11,
        )
        assert connection.state == work_tables.PARTLY_ACTIVATED
        # Drift the cache behind the derivation's back.
        work_tables.Connection.objects.filter(pk=connection.id).update(state=work_tables.REQUESTED)
        result = reads.list_connections(segment="all")

    assert result["rows"][0]["state"] == work_tables.PARTLY_ACTIVATED, (
        "the row must report derive_connection_state(), never the cached column"
    )
    assert result["kpis"]["partly_activated"] == 0, (
        "the tile counts the cache — stated here so the asymmetry is a fact the "
        "suite records rather than a claim a docstring makes"
    )


# ════════════════════════════════════════════════════════════════════════════
# SEARCH · PAGINATION · ISOLATION
# ════════════════════════════════════════════════════════════════════════════
def _service_request(tenant, *, request_no, applicant_name):
    from apps.customers import models as customer_models

    return customer_models.ServiceRequest.objects.create(
        tenant=tenant,
        request_no=request_no,
        applicant_name=applicant_name,
        address_as_given="500 Main Street, Katy TX",
    )


def test_w6_list_search_matches_the_five_things_the_placeholder_names(dana, brazos):
    """*"Connection #, premise, address, applicant, or request #…"* (§5.4.2) —
    five things, so five searches. `applicant` and `request #` are read through
    `Connection.service_request`, the cross-module FK §5.4.6 draws."""
    with tenant_ctx(brazos):
        request = _service_request(brazos, request_no="SR-26-0043", applicant_name="Rosa Alvarez")
        connection = _build_row(
            dana,
            no="CON-26-0117",
            address="500 Main Street",
            units=1,
            done=5,
            orders=7,
            target=date(2026, 9, 30),
            waiting_on="inspection",
            shape="partly",
            age_days=9,
        )
        work_tables.Connection.objects.filter(pk=connection.id).update(service_request=request)
        _build_row(
            dana,
            no="CON-26-0122",
            address="Kestrel Park ph. 2",
            units=1,
            done=1,
            orders=6,
            target=date(2026, 11, 1),
            waiting_on="site access",
            shape="in_progress",
            age_days=2,
        )

        def found(term):
            found_rows = reads.list_connections(segment="all", q=term)["rows"]
            return [row["connection_no"] for row in found_rows]

        assert found("0117") == ["CON-26-0117"]  # connection #
        assert found("Main Street") == ["CON-26-0117"]  # address
        assert found("Rosa") == ["CON-26-0117"]  # applicant
        assert found("SR-26-0043") == ["CON-26-0117"]  # request #
        assert found("Kestrel") == ["CON-26-0122"]  # premise
        assert found("nothing matches this") == []
        # A search hit can explain itself: the two columns it matched on are
        # carried even though NCT-01 does not draw them.
        hit = reads.list_connections(segment="all", q="Rosa")["rows"][0]
        assert (hit["request_no"], hit["applicant"]) == ("SR-26-0043", "Rosa Alvarez")


def test_w6_list_pagination_clamps_and_never_errors(dana, brazos):
    """BR-SHL-011: *"invalid values fall back or clamp, NEVER error"*, and the
    page/per that come back are the ones that were USED."""
    with tenant_ctx(brazos):
        _seed_the_drawn_list(dana)

        # `per` clamps DOWN to the largest allowed size not above it (75 → 50).
        assert reads.list_connections(segment="all", per=75)["per"] == 50
        # A page past the end clamps to the last page rather than 404ing.
        page = reads.list_connections(segment="all", page=99, per=50)
        assert (page["page"], page["total"], len(page["rows"])) == (1, 8, 8)
        # Garbage falls back to page 1.
        assert reads.list_connections(segment="all", page="banana")["page"] == 1

        # And a real second page exists when `per` is small enough to make one.
        first = reads.list_connections(segment="all", page=1, per=1)
        second = reads.list_connections(segment="all", page=2, per=1)
        assert first["per"] == 50, "per clamps UP to the smallest allowed size, never below 50"
        assert first["rows"] == second["rows"], "one page holds all eight at per=50"


def test_w6_list_is_tenant_scoped(dana, brazos, erin, lonestar):
    """TC-NCT-9, verbatim: *given tenant B · when `GET /connections` · then none
    of tenant A's*. The app filter is convenience; RLS FORCE is the law."""
    with tenant_ctx(brazos):
        _build_row(
            dana,
            no="CON-26-0110",
            address="3450 Oak Ridge Dr",
            units=1,
            done=5,
            orders=5,
            target=date(2026, 8, 14),
            waiting_on=None,
            shape="activated",
            age_days=30,
        )
    with tenant_ctx(lonestar):
        result = reads.list_connections(segment="all")
    assert result["rows"] == []
    assert result["total"] == 0
    assert result["kpis"]["open"] == 0
    assert result["kpis"]["oldest"] is None


# ════════════════════════════════════════════════════════════════════════════
# THE ENDPOINT — GET /connections
# ════════════════════════════════════════════════════════════════════════════
def test_w6_list_endpoint_answers_the_house_envelope_with_the_kpi_strip(dana, brazos):
    """ONE shape. Every list in this product answers the DRF envelope, and this
    one does too even though its selector paginated (see
    `_connections_envelope`)."""
    with tenant_ctx(brazos):
        _seed_the_drawn_list(dana)
    response = api_call(
        metering_api.connections,
        "get",
        "/api/connections",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    assert response.status_code == 200
    body = response.data
    assert set(body) >= {"count", "next", "previous", "results", "kpis", "segment", "unavailable"}
    assert body["count"] == 8
    assert body["segment"] == "all"
    assert body["next"] is None and body["previous"] is None
    # `BR-CUS-1046` — the ROUTE opens on what was just created, like the
    # selector. This line read `[row[0] for row in DRAWN_ROWS]` and was the
    # third of `DEF-CUS-7621`'s reds: the envelope was right, one assertion
    # inside it named the ordering the rule replaced on 2026-09-12.
    assert [row["connection_no"] for row in body["results"]] == [
        row[0] for row in reversed(DRAWN_ROWS)
    ]
    assert body["kpis"]["open"] == 7


def test_w6_list_endpoint_refuses_a_segment_it_was_never_told_how_to_build(dana, brazos):
    """A named refusal, not a 404 and not a guess.

    `NotImplementedError("OQ-371")` is what the prime directive asks a lane to
    raise at an unruled boundary, and the DRF handler renders it as a system
    error whose trace names the question — the honest answer to a client that
    called a tab the screen is told not to offer, and a very different thing
    from a 404, which reads as a typo. Same posture as
    `cost_reconciliation_download` under OQ-204, asserted the same way.

    The refusal's WORDS are asserted at the selector
    (`test_w6_list_every_segment_but_all_refuses_by_name`); what matters here is
    that the view does not swallow it into an empty list — a segment that
    silently returned every build would be the worst of the three outcomes.
    """
    refused = api_call(
        metering_api.connections,
        "get",
        "/api/connections",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        query={"segment": "waiting"},
    )
    # ⚠ THIS ASSERTED `>= 500` UNTIL 2026-08-25 AND PINNED THE WRONG BEHAVIOUR
    # AS THOUGH IT WERE INTENDED — DEF-698. A prime-directive
    # NotImplementedError is correct in the SELECTOR and is never correct at the
    # EDGE: the sibling worklist, refusing the identical unruled segment for the
    # identical reason, caught it and served the catalogue sentence. Two lists,
    # one open question, two experiences — on one screen the product looks
    # broken and on the other it explains itself.
    #
    # Neither is reachable through the UI today (both tabs are disabled client-
    # side), which is exactly why it went unnoticed: an API contract nothing
    # calls is still an API contract.
    assert 400 <= refused.status_code < 500, "a refusal a client can act on, not a crash"
    assert refused.data["code"] == "VAL-005"
    # The WORDS stay asserted at the selector; what matters here is that the
    # view neither swallows the refusal into an empty list — a segment silently
    # returning every build is the worst of the three outcomes — nor lets it
    # escape as a server error.
    assert refused.data["message_key"] == "metering.connections.segment_unavailable"


def test_w6_list_endpoint_states_the_absence_in_words_a_utility_can_read(dana, brazos):
    """G28/CR-016: keep the honesty, drop the provenance. The sentence a clerk
    reads carries no OQ id, no route and no rule code; `br_ref`/`tracks` keep
    the provenance where support and engineers can still reach it."""
    response = api_call(
        metering_api.connections,
        "get",
        "/api/connections",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    absence = response.data["unavailable"][0]
    assert absence["tracks"] == "OQ-371", "an absence names the row whose closure kills it"
    assert set(absence["segments"]) == set(reads.SEGMENTS_DRAWN_BUT_UNSERVED)
    for internal in ("OQ-", "BR-", "§", "GET ", "/connections", "connection_reads"):
        assert internal not in absence["detail"], (
            f"{internal!r} is an internal reference and this string is read by a utility user"
        )


def test_w6_the_ROUTE_answers_the_filter_vocabulary_and_not_only_the_selector(dana, brazos):
    """**`DEF-CUS-5432` — THE ONE QUESTION NOBODY WAS ASKING.**

    `list_connections` has returned `filters`, `states`, `sorts`, `sort` and
    `dir` since CR-045 wave D. `_connections_envelope` forwards its keys BY
    NAME and was never amended, so for three weeks `GET /connections` answered
    with no `states` on it and **the New connects tab rendered no filter
    control at all** — `offerableFilters` dropping a group with no options,
    `FilterBar` returning `null` for a screen that declares none, every layer
    behaving exactly as written over a capability nobody could reach.

    ⚠ **EVERY CHECK THAT EXISTED PASSED, AND EACH ONE PROVED A DIFFERENT
    THING.** The frontend cases build their own payload WITH `states` in it, so
    they prove the fixture. `ConnectionList` declares both fields, so `tsc` is
    satisfied by the TYPE rather than by the server. And every case in this
    file called `list_connections` directly, so they prove the SELECTOR. **The
    envelope is the layer the value is lost in, so the envelope is the layer
    this asserts on.**

    The general form is worth more than the fix: where a selector and an
    envelope BOTH list keys by hand, the contract test belongs on the envelope.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().get("/api/brazosbend/connections")
    # ⚠ `request.user = …` on the raw request silently 401s — DRF's `Request`
    # runs the authenticators and overwrites it. The force hook plus the two
    # server-attached facts is what `core.permissions._role_of` actually reads.
    force_authenticate(request, user=dana.user)
    request.tenant_role = "system_admin"
    request.tenant_id = brazos.id

    with tenant_ctx(brazos):
        _build_row(dana, no="CON-ENV", address="1 Envelope Way", units=1, done=0, orders=1,
                   target="2026-09-10", waiting_on=None, shape="requested", age_days=1)
        response = metering_api.connections(request)

    assert response.status_code == 200, response.data
    body = response.data
    for key in ("filters", "states", "sorts", "sort", "dir"):
        assert key in body, f"the envelope dropped {key!r} — the screen cannot offer what it is not told"

    # The blueprint's three chips, in the drawn order, ON THE WIRE.
    offered = [state["code"] for state in body["states"]]
    assert offered[:3] == ["open", "partly_activated", "activated"]
    assert body["filters"] == ["state"]


def test_w6_list_endpoint_is_mounted(dana, brazos):
    """Built is not wired (hard-won law 2). `GET /connections` resolves through
    the module's OWN urlpatterns, which `config/urls.py` already includes — so
    this endpoint is reachable the moment it lands, and cannot repeat the
    six-times-recorded failure of shipping a read model with no route.

    ⚠ **The FRONTEND half is still missing and this test does not claim
    otherwise:** the Accounts *New connects* tab renders a placeholder and
    nothing calls this route yet. That is REPORTED, not hidden (r11 step 2b).
    """
    routes = {getattr(entry.pattern, "_route", None) for entry in metering_api.urlpatterns}
    assert "connections" in routes
    entry = next(
        e for e in metering_api.urlpatterns if getattr(e.pattern, "_route", None) == "connections"
    )
    assert entry.callback is metering_api.connections
