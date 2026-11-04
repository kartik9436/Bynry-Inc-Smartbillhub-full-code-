# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W3b items 2–7
#           and 9: the endpoints SET-06D and SET-07D call and the payload keys
#           they render — every one of them a table RC-W1 landed that nothing
#           served, which is why both screens carry a stated absence.
#           Screens: SET-06D (Assets · Accounts · Audit) · SET-07D (Schedule ·
#           Coverage) · SET-05 (both pagers)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3–§7
# Rules:    D1 (read windows are closable records) · D7 (*"Yes - please do it"*
#           — server-side paging, no N+1) · D12 (**no Balance column**) ·
#           D13 (**no account-level cycle assignment**) · BR-MET-011 ·
#           BR-MET-075 (both halves of the meter count) · BR-MET-078 (NO money)
#           · BR-MET-080 (coverage) · BR-SHL-011 (list grammar) ·
#           OQ-339 (month-end: **OPEN — never answered by a call site**) ·
#           CLAUDE.md rule 1 (tenant scoping · RLS FORCE)
# ───────────────────────────────────────────────────────
"""RC-W3b — the seven doors, and the one refusal that must stay a refusal.

**HARD-WON LAW 2 RUNS BOTH WAYS AND THAT IS WHY THIS FILE EXISTS.** A screen
whose endpoint is missing renders an honest absence; an endpoint no screen calls
is the same defect wearing the other coat. Each test below names the surface
that consumes what it asserts.

⚠ **OQ-339 IS OPEN AND THE LAST SECTION PROVES IT STAYS OPEN.** A cycle whose
start day is 29–31 has no such date in some months, and clamp / skip / roll
produce different bills. The payload must carry a NAMED silence, never a date —
answering it here would settle a PO question by call site.
"""

from datetime import date
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import services as customer_services
from apps.metering import api, models, read_windows, selectors, services

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_asset,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


# ── worlds ─────────────────────────────────────────────────────────────────
def _routed_premises(actor, *, code: str, address: str, units: int = 1) -> dict[str, Any]:
    """One premises with `units` metered units, on its own route."""
    premises = make_premises(actor, address_line=address)
    meters = []
    for index in range(units):
        unit = make_unit(actor, premises["id"], label=f"Unit {index + 1}", services=["water"])
        meters.append(
            make_asset(
                actor,
                unit_id=unit["id"],
                asset_no=f"{code}-MTR-{index + 1}",
                service="water",
                unit="kgal",
                install_date="2026-01-05",
            )
        )
    route = services.create_route(
        actor,
        {
            "code": code,
            "name": address,
            "service_codes": ["water"],
            "premises_ids": [premises["id"]],
        },
    )
    return {"premises": premises, "route": route, "meters": meters}


def _cycle(tenant, code="CY-W3B", **overrides):
    fields = {
        "code": code,
        "name": "Monthly water",
        "frequency": "Monthly",
        "start_day": 1,
        "days_to_complete": 3,
        "first_run_date": date(2026, 8, 1),
    }
    fields.update(overrides)
    return models.Cycle.objects.create(tenant=tenant, **fields)


def _account(actor, unit_id, *, tenant, full_name="R. Okonkwo"):
    """An OCCUPYING account on the unit — no money anywhere on it (D12).

    BR-MET-040: an account cannot ACTIVATE on a unit with no plan, and the
    account DERIVES its plan from the unit, so the fixture assigns an empty
    published plan first (the `cr029_dynamism_fixtures` posture: a container,
    no prices).
    """
    plan = make_plan(tenant, name="RC-W3b plan", services=("water",))
    services.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id)})
    return customer_services.create_account(
        actor,
        {
            "unit_id": str(unit_id),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-01-15",
            "contact": {"full_name": full_name, "email": "resident@example.test"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(full_name, account_type="residential"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 2 — THE EXCLUSION EXPLAINS ITSELF IN PLACE
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_2__the_meter_picker_serves_the_exclusion_reason(brazos, dana):
    """SET-06D.assets draws *"MTR-W2262 excluded · premise demolished"*. The
    reason has been STORED since RC-W1-T4 and served nowhere, so the tab could
    say that a meter is off the route and never why."""
    with tenant_ctx(brazos):
        world = _routed_premises(dana, code="RT-EXC", address="1408 Elm St", units=2)
        excluded = world["meters"][0]
        services.update_route(
            dana,
            world["route"]["id"],
            {
                "excluded_asset_ids": [excluded["id"]],
                "exclusion_reasons": {str(excluded["id"]): "premise demolished"},
            },
        )
        # ⚠ **NO UNIT IDS ARE SENT ANY MORE (`CR-131-BRC07` step 5).** The
        # route knows its own premises, so the caller names the route and
        # nothing else — which is what takes SET-06 step 3's URL from 37,994
        # characters back to one id.
        picker = selectors.route_meter_picker(route_id=world["route"]["id"])

    rows = {row["id"]: row for row in picker["meters"]}
    assert rows[str(excluded["id"])]["excluded"] is True
    assert rows[str(excluded["id"])]["exclusion_reason"] == "premise demolished"
    # An INCLUDED meter carries no reason, and an exclusion made before the
    # column exists carries None — never an invented sentence.
    included = rows[str(world["meters"][1]["id"])]
    assert included["excluded"] is False
    assert included["exclusion_reason"] is None


def test_w3b_2__the_route_serves_its_exclusions_with_reasons(brazos, dana):
    """The detail rail's *"N excluded"* count has always travelled; WHY has
    not. `excluded_asset_ids` keeps its shape for the wizard's pre-tick."""
    with tenant_ctx(brazos):
        world = _routed_premises(dana, code="RT-EXC2", address="12 Cedar Ct")
        meter = world["meters"][0]
        services.update_route(
            dana,
            world["route"]["id"],
            {
                "excluded_asset_ids": [meter["id"]],
                "exclusion_reasons": {str(meter["id"]): "master metered"},
            },
        )
        detail = selectors.route_detail(world["route"]["id"])

    assert detail["excluded_asset_ids"] == [str(meter["id"])]
    assert detail["exclusions"] == [{"asset_id": str(meter["id"]), "reason": "master metered"}]
    assert detail["meters_excluded"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 3 — THE READ HISTORY HAS A SOURCE
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_3__read_windows_are_served_newest_first(brazos, dana):
    """SET-06D's Read history: Window · Read on · Reader · Collected ·
    Expected · Result. RC-W2 wrote the closer; nothing served the rows."""
    with tenant_ctx(brazos):
        world = _routed_premises(dana, code="RT-RW", address="9 Mason Rd")
        for month in (6, 7, 8):
            read_windows.close_read_window(
                dana,
                route_id=world["route"]["id"],
                period_start=date(2026, month, 1),
                period_end=date(2026, month, 3),
                read_on=date(2026, month, 3),
                collected_count=196,
                expected_count=196,
                result="Complete",
            )
        response = api_call(
            api.route_read_windows,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            route_id=world["route"]["id"],
        )

    assert response.status_code == 200
    rows = response.data["windows"]
    assert [row["period_start"] for row in rows] == ["2026-08-01", "2026-07-01", "2026-06-01"]
    first = rows[0]
    assert (first["collected"], first["expected"], first["result"]) == (196, 196, "Complete")
    assert first["read_on"] == "2026-08-03"
    # BR-MET-078 — a read window counts meters. No money key, ever.
    assert not {key for key in first if "amount" in key or "balance" in key}


def test_w3b_3__the_read_window_limit_clamps_and_never_errors(brazos, dana):
    """BR-SHL-011: a list URL falls back or clamps; it does not 4xx."""
    with tenant_ctx(brazos):
        world = _routed_premises(dana, code="RT-RW2", address="4 Bluestem Ln")
        for month in (6, 7):
            read_windows.close_read_window(
                dana,
                route_id=world["route"]["id"],
                period_start=date(2026, month, 1),
                period_end=date(2026, month, 3),
                read_on=date(2026, month, 3),
                collected_count=10,
                expected_count=10,
                result="Complete",
            )
        limited = api_call(
            api.route_read_windows,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"limit": "1"},
            route_id=world["route"]["id"],
        )
        rubbish = api_call(
            api.route_read_windows,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"limit": "banana"},
            route_id=world["route"]["id"],
        )
    assert len(limited.data["windows"]) == 1
    assert rubbish.status_code == 200
    assert len(rubbish.data["windows"]) == 2


def test_w3b_3__another_tenants_route_has_no_read_history(brazos, dana, lonestar, erin):
    """Hard rule 1 — ABSENT, not an empty list that would read as "never
    walked".

    ⚠ Asserted as the STATUS the wire carries, not as a raised exception: the
    BE-02 handler renders the refusal, so a test that watched for the exception
    would pass on a view that swallowed it.
    """
    with tenant_ctx(brazos):
        world = _routed_premises(dana, code="RT-RW3", address="77 Katy Fwy")
    with tenant_ctx(lonestar):
        response = api_call(
            api.route_read_windows,
            "get",
            user=erin.user,
            role="system_admin",
            tenant=lonestar,
            route_id=world["route"]["id"],
        )
    assert response.status_code == 404
    assert "windows" not in (response.data or {})


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 4 — GET /cycles/{id}
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_4__the_cycle_id_route_answers_get(brazos, dana):
    """The id route was PATCH+DELETE only, so SET-07D read the whole list and
    picked its row. The GET serves the SAME dict — the screen's typed row —
    so nothing on the client changes shape."""
    from django.urls import resolve

    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        listed = [row for row in selectors.cycles_list() if row["id"] == str(cycle.id)][0]
        response = api_call(
            api.cycle_detail,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            cycle_id=str(cycle.id),
        )

    assert resolve(f"/api/brazosbend/cycles/{cycle.id}").func is api.cycle_detail
    assert response.status_code == 200
    assert set(response.data) == set(listed)
    assert response.data["code"] == "CY-W3B"
    assert response.data["frequency"] == "Monthly"


def test_w3b_4__another_tenants_cycle_is_absent(brazos, dana, lonestar, erin):
    from core import errors

    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code="CY-ISO")
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            selectors.cycle_detail(str(cycle.id))


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 5 — THE ROUTE'S ACCOUNTS, STATUS ONLY (D12)
# ═══════════════════════════════════════════════════════════════════════════
MONEY_WORDS = ("balance", "amount", "due", "total_owed", "arrears")


def test_w3b_5__a_routes_accounts_are_served_status_only(brazos, dana):
    """*"The accounts a missed read on this route affects"* — and **no Balance
    column** (D12, *"not required"*): routes and cycles are grouping only."""
    with tenant_ctx(brazos):
        world = _routed_premises(dana, code="RT-ACC", address="5 Pine St", units=2)
        members = selectors.route_members(world["route"]["id"])
        _account(dana, members[0]["unit_id"], tenant=brazos, full_name="R. Okonkwo")
        response = api_call(
            api.route_accounts,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            route_id=world["route"]["id"],
        )

    assert response.status_code == 200
    assert response.data["total"] == 1
    assert response.data["units"] == 2
    assert response.data["units_without_account"] == 1
    row = response.data["accounts"][0]
    assert row["customer_name"] == "R. Okonkwo"
    assert row["status"]
    assert row["premise_no"] is not None
    for key in row:
        assert not any(word in key for word in MONEY_WORDS), key


def test_w3b_5__a_route_with_no_accounts_says_so_without_inventing_rows(brazos, dana):
    with tenant_ctx(brazos):
        world = _routed_premises(dana, code="RT-ACC0", address="6 Pine St")
        served = selectors.route_accounts(world["route"]["id"])
    assert served == {
        "accounts": [],
        "total": 0,
        "units": 1,
        "units_without_account": 1,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 6 — COVERAGE ROWS, AND D13'S ABSENT ACTION
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_6__coverage_serves_the_rows_and_what_each_one_lacks(brazos, dana):
    """SET-07D's Coverage tab lists the uncovered accounts. **D13** — the
    remedy is a ROUTE, so the row names that, and there is no assignment."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="88 Uncovered Way")
        unit = make_unit(dana, premises["id"], label="A", services=["water"])
        _account(dana, unit["id"], tenant=brazos, full_name="U. Ncovered")
        response = api_call(
            api.cycle_coverage,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
        )

    assert response.data["uncovered_accounts"] == 1
    row = response.data["uncovered"][0]
    assert row["customer_name"] == "U. Ncovered"
    assert row["lacks"] == "route"
    assert row["unit_label"] == "A"
    for key in row:
        assert not any(word in key for word in MONEY_WORDS), key


def test_w3b_6__no_endpoint_assigns_a_cycle_to_an_account(brazos):
    """D13, asserted ABSENT: *"Cycles are not directlya ssing to accounts it is
    derived and determined at the time of bill run"*. A route that existed
    would be a promise a screen could call."""
    paths = {str(entry.pattern) for entry in api.urlpatterns}
    # ⚠ NARROW ON PURPOSE. `units/{id}/plan-assignments` is a different fact
    # with its own ruling, so the assertion is about a CYCLE being assigned —
    # to an account or to anything else — and not about the word "assign".
    assert not [path for path in paths if "cycle" in path and "assign" in path]
    assert not [path for path in paths if "cycle" in path and "account" in path]


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 7 — D7: THE SERVER PAGES, SORTS AND BATCHES
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_7__routes_answers_the_paged_envelope(brazos, dana):
    """`listPage()` reads the SHAPE: a `{count, results}` envelope means the
    server paged it and the client's own window stops firing — with ZERO
    frontend edits, which is the whole point of D7's split."""
    with tenant_ctx(brazos):
        for index in range(3):
            _routed_premises(dana, code=f"RT-P{index}", address=f"{index} Page St")
        response = api_call(
            api.routes,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"page": "2", "per": "50", "sort": "code", "dir": "asc"},
        )
    assert response.status_code == 200
    assert response.data["count"] == 3
    assert isinstance(response.data["results"], list)
    # BR-SHL-011: an out-of-range page CLAMPS into the last page, never 404s.
    assert len(response.data["results"]) == 3


def test_w3b_7__every_caller_gets_the_envelope_now_page_or_no_page(brazos, dana):
    """⚠ **REWRITTEN BY RC-W5-T6 — AND THE OLD ASSERTION WAS THIS WAVE'S JOB.**

    What stood here asserted the OPPOSITE: *"a caller that asks for no page
    still gets the whole list"*. That was RC-W3b protecting eight shipped call
    sites — the cycle detail's Routes tab, both wizards, the S26/S27 ops tabs,
    the reads list, the upload-reads wizard and the BILL RUN's cycle picker —
    every one of which read these two lists as bare arrays and called `.filter`
    or `.find` on the answer. An unconditional envelope would have broken all
    eight at runtime with every backend test still green.

    **W5-T6 moved those call sites**, so the branch they needed is gone:
    `getRoutes()`/`getCycles()` ask for a page, read `results`, and follow
    `count` until they hold every row (`src/api/routesCyclesLists.cr029.test.ts`
    is the other half of this pair). The shape no longer follows the ask — it is
    ONE shape, which is what D7 ruled and what BR-SHL-011's grammar assumes.

    This test is deliberately the same test turned around, rather than a new one
    beside it: the thing worth asserting is that no caller can still receive a
    bare array, and that is only visible where the old claim used to be.
    """
    with tenant_ctx(brazos):
        _routed_premises(dana, code="RT-BARE", address="1 Bare St")
        _cycle(brazos, code="CY-BARE")
        routes = api_call(api.routes, "get", user=dana.user, role="system_admin", tenant=brazos)
        cycles = api_call(api.cycles, "get", user=dana.user, role="system_admin", tenant=brazos)
        paged = api_call(
            api.routes,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"per": "50"},
        )

    for response in (routes, cycles, paged):
        assert not isinstance(response.data, list), "the bare-array branch is retired"
        assert set(response.data) >= {"count", "results"}
    assert routes.data["results"][0]["code"] == "RT-BARE"
    assert cycles.data["results"][0]["code"] == "CY-BARE"
    assert routes.data["count"] == 1


def test_w3b_7__a_derived_column_sorts_server_side(brazos, dana):
    """`meters` is a COUNT (BR-MET-075: available minus exclusions), not a
    column — so it is sorted from the built page rather than from SQL that
    cannot see it. An unknown sort key falls back and never errors."""
    with tenant_ctx(brazos):
        _routed_premises(dana, code="RT-S1", address="1 Sort St", units=1)
        _routed_premises(dana, code="RT-S3", address="3 Sort St", units=3)
        descending = selectors.routes_page(sort="meters", direction="desc")
        rubbish = selectors.routes_page(sort="nonsense", direction="asc")

    assert [row["code"] for row in descending] == ["RT-S3", "RT-S1"]
    assert [row["code"] for row in rubbish] == ["RT-S1", "RT-S3"]  # default: code asc


def test_w3b_7__cycles_sort_by_their_schedule_columns(brazos, dana):
    with tenant_ctx(brazos):
        _cycle(brazos, code="CY-A", start_day=15)
        _cycle(brazos, code="CY-B", start_day=2)
        rows = selectors.cycles_page(sort="start_day", direction="asc")
    assert [row["code"] for row in rows] == ["CY-B", "CY-A"]


def test_w3b_7__the_per_row_derivations_are_batched(brazos, dana):
    """D7's other half — *"the per-row derivations batched (no N+1)"*.

    The guard is SHAPE, not a magic number: adding units to a route must not
    add queries to the list, because the assets seam used to be asked once per
    member unit. A route with four units cost eight queries more than the same
    route with one.
    """
    with tenant_ctx(brazos):
        _routed_premises(dana, code="RT-N1", address="1 Batch St", units=1)
        with CaptureQueriesContext(connection) as small:
            selectors.routes_page()
        _routed_premises(dana, code="RT-N4", address="4 Batch St", units=4)
        with CaptureQueriesContext(connection) as bigger:
            selectors.routes_page()

    # One more ROUTE costs a bounded number of reads (the reads seam is still
    # per row, and is the next thing to batch); four more UNITS cost none.
    assert len(bigger) - len(small) <= 4, (len(small), len(bigger))


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 9 — THE PERIOD ENGINE IS SERVED, AND OQ-339 STAYS OPEN
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_9__the_cycle_payload_carries_the_next_three_windows(brazos, dana):
    """SET-07D's *"Next three windows"*. The engine landed in RC-W2 and the
    detail had no endpoint to reach it through; `GET /cycles/{id}` is that
    endpoint, so the arithmetic and the screen finally meet."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code="CY-WIN", start_day=1, days_to_complete=3)
        response = api_call(
            api.cycle_detail,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            cycle_id=str(cycle.id),
        )

    windows = response.data["proposed_windows"]
    assert len(windows) == 3
    assert response.data["schedule_gap"] is None
    assert {window["status"] for window in windows} <= {"Next", "Scheduled"}
    for window in windows:
        assert window["period_start"] < window["period_end"]


def test_w3b_9__a_month_end_start_day_serves_the_clamped_window(brazos, dana):
    """⚠ **THIS TEST ASSERTED A NAMED SILENCE UNTIL 2026-08-23.** A cycle
    starting on the 31st had no answer in months that lack one, so the payload
    carried `schedule_gap` and no date — putting one there would have settled a
    PO question by call site.

    OQ-339 is now CLOSED-RULED: *"there is no 31st feb so we have to manage
    either 28th or 29th of Feb."* So the endpoint serves real windows, the gap
    is null, and every occurrence opens on the last day its month actually has:
    the 31st in a long month, the 30th in April/June/September/November.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code="CY-31", start_day=31, first_run_date=date(2026, 8, 31))
        response = api_call(
            api.cycle_detail,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            cycle_id=str(cycle.id),
        )

    starts = [window["period_start"] for window in response.data["proposed_windows"]]
    assert starts, "a month-end cycle proposes windows since OQ-339 was ruled"
    assert response.data["schedule_gap"] is None
    assert response.data["next_period"] is not None
    for start in starts:
        month, day = int(start[5:7]), int(start[8:10])
        assert day == (30 if month in (4, 6, 9, 11) else 31), (
            f"{start}: a 31st-anchored cycle opens on the last day the month has "
            "(OQ-339, ruled 2026-08-23) — never a rolled or skipped one"
        )
