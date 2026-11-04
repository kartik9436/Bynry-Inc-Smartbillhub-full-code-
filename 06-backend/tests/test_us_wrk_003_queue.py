# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-003 (EP-WRK-01) — one worklist of every order the field has
#           finished and nobody has accepted, across every connection and every
#           anchor. Screen: Work-009 (`wireframes/Work-009.png`).
# Rules:    BR-WRK-007 (the queue is `accepted_by IS NULL AND state = completed`
#           — NO NEW TABLE) · BR-MET-110 (a person accepts; only then does a
#           service go live) · BR-WRK-006 (an order with no connection is in the
#           queue and its CONNECTION cell is a dash) · B14 rules 16, 17 ·
#           CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    this file — TC-1..7, named for the story's own case table
# ───────────────────────────────────────────────────────
"""US-WRK-003 TC-1..7 — the approval queue, and what is deliberately NOT in it.

⚠ **THE FIXTURE'S THREE ROWS ARE THE DRAWING'S THREE ROWS, AND TWO OF THEM
CANNOT BE SEEDED INTO THE DEMO TENANT.** `US-WRK-003` §4 names `WO-4906 · Meter
set · Gas`, `WO-4903 · Tap and service line · Water` and `WO-4917 · Container
delivery · Trash`. **Brazos Bend Utilities sells Electric and Water and nothing
else**, so its Gas and Trash orders are never planted — wave A recorded the same
fact about the Orders tab and about `CON-26-0117`. These cases therefore build
their own three orders with the drawing's TYPES, WAITING DAYS and OUTCOMES, on
the services the tenant actually runs, and the walkthrough asserts the shape of
the queue on the seeded fixture rather than three order numbers that cannot
exist there. The numbers are the drawing's; the services are the tenant's.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import resolve
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import api as work_api
from apps.work import selectors as work_selectors
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import field_close  # CR-168 P1.34 — close as the field
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _queue(tenant, actor, role="system_admin", query=None):
    return api_call(
        work_api.work_orders_awaiting_approval,
        "get",
        f"/api/{tenant.subdomain}/work-orders/awaiting-approval",
        user=actor.user,
        role=role,
        tenant=tenant,
        query=query,
    )


def _build(actor, address, service="water"):
    premises = make_premises(actor, address_line=address)
    unit = make_unit(actor, premises["id"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    w6.add_connection_service(actor, connection.id, service_code=service, unit_id=unit["id"])
    return connection


def _finished(actor, connection_id, *, order_type, service, outcome, days_ago, premises_id=None):
    """One order the field has finished `days_ago` days ago and nobody accepted.

    ⚠ **`completed_at` IS BACK-DATED WITH AN `update()`, WHICH IS THE ONLY
    COLUMN THIS FILE WRITES OUTSIDE A DOOR** — the same exception, for the same
    reason, that `sample_data._seed_w6_connections` records for `submitted_at`:
    *"6 days"* is a figure the drawing took on a day that has passed, no service
    accepts a completion date, and it is not a state. Everything else here goes
    through `create_work_order` and `submit_field_result`.
    """
    payload = {"type": order_type, "service": service}
    if premises_id is not None:
        payload["premises_id"] = premises_id
    order = w6.create_work_order(actor, connection_id, payload)
    field_close(
        actor, order["id"], field_data={"set_reads": []}, outcome=outcome
    )
    work_tables.WorkOrder.objects.filter(pk=order["id"]).update(
        completed_at=timezone.now() - timedelta(days=days_ago)
    )
    return order


def _the_drawings_three(actor):
    """`Work-009`'s three rows: 6 days Passed, 3 days Partially done, 1 day Passed."""
    first = _build(actor, "500 Main St")
    second = _build(actor, "Ridgeway Mews")
    third = _build(actor, "91 Fen Close")
    return (
        _finished(
            actor,
            first.id,
            order_type="Meter set",
            service="water",
            outcome=work_tables.OUTCOME_PASSED,
            days_ago=6,
        ),
        _finished(
            actor,
            second.id,
            order_type="Tap and service line",
            service="water",
            outcome=work_tables.OUTCOME_PARTIALLY_DONE,
            days_ago=3,
        ),
        _finished(
            actor,
            third.id,
            order_type="Container delivery",
            service="electric",
            outcome=work_tables.OUTCOME_PASSED,
            days_ago=1,
        ),
    )


def test_us_wrk_003_the_route_resolves_through_config_urls():
    """A future lane cannot lose the include, and cannot let a `<uuid:…>`
    converter swallow the literal `awaiting-approval` either."""
    match = resolve("/api/brazosbend/work-orders/awaiting-approval")
    assert match.func is work_api.work_orders_awaiting_approval


# ════════════════════════════════════════════════════════════════════════════
# TC-1 · three finished, unaccepted orders — three rows, oldest first, footer
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_003_tc1_three_rows_oldest_first_and_the_footers_two_figures(dana, brazos):
    with tenant_ctx(brazos):
        _the_drawings_three(dana)
    response = _queue(brazos, dana)
    assert response.status_code == 200, response.data
    rows = response.data["results"]
    assert response.data["count"] == 3
    # OLDEST FIRST — `completed_at` ascending (US-WRK-003 TC-1).
    assert [row["waiting_days"] for row in rows] == [6, 3, 1]
    assert [row["type"] for row in rows] == [
        "Meter set",
        "Tap and service line",
        "Container delivery",
    ]
    assert [row["outcome"] for row in rows] == ["passed", "partially_done", "passed"]
    # The footer's SECOND figure — *"3 orders · oldest waiting 6 days"*.
    assert response.data["oldest_waiting"] == 6


def test_us_wrk_003_tc1_the_oldest_waiting_figure_is_about_the_QUEUE_not_the_page(dana, brazos):
    """`DEF-1702`'s argument applied to a COUNT: a footer reading *oldest waiting
    1 day* because the six-day row sat on page two would be a true sentence
    about the wrong set.

    ⚠ **THIS CASE COSTS 51 ORDERS AND THE FIRST DRAFT TRIED TO DO IT WITH THREE.**
    `per=2` does not give a two-row page: `clamp_page_size` floors at
    `PAGE_SIZES[0]`, which is **50** (A11 r2), so three rows are one page and the
    assertion passed for a reason that had nothing to do with the claim. The only
    honest way to see page two is to fill page one, so the oldest row sits where
    a page-scoped footer would lose it. The 51 orders share ONE build, which is
    the cheap part; the expensive part is the premises and the unit."""
    with tenant_ctx(brazos):
        connection = _build(dana, "500 Main St")
        # The oldest goes in FIRST, so it lands on page one — a page-scoped
        # footer would then be RIGHT by luck. Page two is where the youngest is.
        _finished(
            dana,
            connection.id,
            order_type="Meter set",
            service="water",
            outcome=work_tables.OUTCOME_PASSED,
            days_ago=6,
        )
        for index in range(50):
            _finished(
                dana,
                connection.id,
                order_type=f"Filler {index}",
                service="water",
                outcome=work_tables.OUTCOME_PASSED,
                days_ago=1,
            )
    page_one = _queue(brazos, dana)
    page_two = _queue(brazos, dana, query={"page": 2})
    assert page_one.data["count"] == 51
    assert len(page_one.data["results"]) == 50
    assert len(page_two.data["results"]) == 1
    # THE CLAIM: page two holds only one-day rows, and its footer still reads 6.
    assert [row["waiting_days"] for row in page_two.data["results"]] == [1]
    assert page_two.data["oldest_waiting"] == 6
    assert page_two.data["count"] == 51


def test_us_wrk_003_tc1_a_per_below_the_ladder_clamps_and_never_errors(dana, brazos):
    """`BR-SHL-011` — `q`/`page`/`per` fall back or clamp, never error. `per=2`
    is below `PAGE_SIZES[0]`, so it comes back as 50 rather than as a 400."""
    with tenant_ctx(brazos):
        _the_drawings_three(dana)
    response = _queue(brazos, dana, query={"per": 2, "page": 900})
    assert response.status_code == 200, response.data
    assert len(response.data["results"]) == 3  # clamped UP to the ladder's floor
    assert response.data["count"] == 3


def test_us_wrk_003_tc1_the_row_carries_the_drawings_seven_columns(dana, brazos):
    """ORDER · CONNECTION · PREMISE · SERVICE · OUTCOME · COMPLETED · WAITING —
    asserted by NAME, so a column quietly dropped from the payload fails here
    rather than rendering as a blank cell nobody notices."""
    with tenant_ctx(brazos):
        connection = _build(dana, "500 Main St")
        _finished(
            dana,
            connection.id,
            order_type="Meter set",
            service="water",
            outcome=work_tables.OUTCOME_PASSED,
            days_ago=6,
        )
    row = _queue(brazos, dana).data["results"][0]
    for column in (
        "order_no",
        "connection",
        "premise",
        "service",
        "outcome",
        "completed_at",
        "waiting_days",
    ):
        assert column in row, f"Work-009 draws {column} and the payload has no such key"
    assert row["connection"]["connection_no"] == connection.connection_no
    assert row["premise"]["address"] == "500 Main St"
    assert row["service"] == "water"


# ════════════════════════════════════════════════════════════════════════════
# TC-2 · accepting one takes it out of the list
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_003_tc2_accepting_an_order_removes_it_and_the_count_falls(dana, brazos):
    with tenant_ctx(brazos):
        first, _second, _third = _the_drawings_three(dana)
    before = _queue(brazos, dana)
    assert before.data["count"] == 3
    with tenant_ctx(brazos):
        w6.accept_field_result(dana, first["id"])
    after = _queue(brazos, dana)
    assert after.data["count"] == 2
    assert first["id"] not in [row["id"] for row in after.data["results"]]
    # And the footer moves with it: the oldest is now the three-day row.
    assert after.data["oldest_waiting"] == 3
    with tenant_ctx(brazos):
        accepted = work_tables.WorkOrder.objects.get(pk=first["id"])
        assert accepted.accepted_by_id is not None
        assert accepted.accepted_at is not None


# ════════════════════════════════════════════════════════════════════════════
# TC-3 · NEGATIVE — the null alone is not enough
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_003_tc3_a_planned_order_is_not_in_the_queue(dana, brazos):
    """A `planned` order also has no `accepted_by`. It is not awaiting anybody's
    approval — it is waiting for a technician. **Both halves of `BR-WRK-007` are
    load-bearing**, and this is the case that says so."""
    with tenant_ctx(brazos):
        connection = _build(dana, "500 Main St")
        planned = w6.create_work_order(
            dana, connection.id, {"type": "Meter set", "service": "water"}
        )
        assert work_tables.WorkOrder.objects.get(pk=planned["id"]).accepted_by_id is None
    response = _queue(brazos, dana)
    assert response.data["count"] == 0
    assert response.data["oldest_waiting"] is None  # not 0 — nothing is waiting


def test_us_wrk_003_tc3_the_two_work_lists_never_show_the_same_row(dana, brazos):
    """The Orders tab is *open work*; this is *finished work nobody signed off*.
    The state sets are disjoint by construction and a row in both lists would be
    a job a dispatcher chases and a supervisor approves at the same time."""
    with tenant_ctx(brazos):
        connection = _build(dana, "500 Main St")
        w6.create_work_order(dana, connection.id, {"type": "Meter set", "service": "water"})
        _finished(
            dana,
            connection.id,
            order_type="Service drop",
            service="water",
            outcome=work_tables.OUTCOME_PASSED,
            days_ago=2,
        )
        open_ids = {row["id"] for row in work_selectors.open_orders()["rows"]}
        queue_ids = {row["id"] for row in work_selectors.awaiting_approval()["rows"]}
    assert open_ids and queue_ids
    assert open_ids.isdisjoint(queue_ids)


# ════════════════════════════════════════════════════════════════════════════
# TC-4 · NEGATIVE — a second acceptance is refused, idempotently
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_003_tc4_accepting_the_same_order_twice_is_refused(dana, brazos):
    """*"Refuses a second approval"* — and it refuses **loudly**, with
    `BIZ-IDEMPOTENT` and the order number in the message, rather than returning
    a quiet already-done. That is the right shape here and the story's word
    *"idempotently"* is about the EFFECT, not about the answer: pressing twice
    must not send the letter twice or activate the service twice, and a clerk
    who did press twice is owed a sentence saying the first press worked."""
    from core import errors

    with tenant_ctx(brazos):
        first, _second, _third = _the_drawings_three(dana)
        w6.accept_field_result(dana, first["id"])
        with pytest.raises(errors.BizError) as refused:
            w6.accept_field_result(dana, first["id"])
        assert refused.value.message_key == "metering.work_order_already_accepted"
        assert refused.value.br_ref == "BR-MET-110"
        # ONE acceptance, whatever a clerk's mouse did.
        assert work_tables.WorkOrder.objects.filter(pk=first["id"], accepted_by__isnull=False).count() == 1
    assert _queue(brazos, dana).data["count"] == 2


# ════════════════════════════════════════════════════════════════════════════
# TC-5 · TENANT ISOLATION — Lone Star Ridge sees its own queue and no other
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_003_tc5_lone_star_ridges_queue_holds_none_of_brazos_bends(
    dana, erin, brazos, lonestar
):
    with tenant_ctx(brazos):
        _the_drawings_three(dana)
    assert _queue(brazos, dana).data["count"] == 3
    theirs = _queue(lonestar, erin)
    assert theirs.status_code == 200, theirs.data
    assert theirs.data["count"] == 0
    assert theirs.data["results"] == []
    assert theirs.data["oldest_waiting"] is None


def test_us_wrk_003_tc5_with_no_tenant_in_context_the_queue_answers_nothing(dana, brazos):
    """Hard rule 1 from underneath, in the shape wave A's seam set already
    takes (`US-WRK-005` TC-7: *"every seam read answers nothing without a
    tenant"*): with no `app.tenant_id` the filter is on `None`, no row matches,
    and RLS `FORCE` sits under that in production.

    ⚠ **The answer is an EMPTY QUEUE, not a raise, and that is a deliberate
    difference from metering's own `_tenant_id`, which refuses.** A seam read is
    reached from a background job and a request alike; failing closed to zero
    rows is what stops one tenant's context leaking into another's loop. The
    HTTP door in front of it refuses first — `require_tenant` — so no caller
    reaches this state through the product."""
    from core import tenancy as core_tenancy

    with tenant_ctx(brazos):
        _the_drawings_three(dana)
        assert work_selectors.awaiting_approval()["total"] == 3
    core_tenancy.clear_current_tenant()
    assert core_tenancy.current_tenant_id() is None
    answered = work_selectors.awaiting_approval()
    assert answered["total"] == 0
    assert answered["rows"] == []
    assert answered["oldest_waiting_days"] is None


# ════════════════════════════════════════════════════════════════════════════
# TC-6 · the empty state's two figures
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_003_tc6_an_empty_queue_answers_zero_and_a_null_never_a_zero_day(
    dana, brazos
):
    """B14 rule 17 — the empty state says what is missing. The SERVER's half of
    that is honest nulls: `count` is 0 because nothing is there, and
    `oldest_waiting` is null because *"waiting 0 days"* is a sentence about
    something that does not exist."""
    response = _queue(brazos, dana)
    assert response.status_code == 200, response.data
    assert response.data["count"] == 0
    assert response.data["results"] == []
    assert response.data["oldest_waiting"] is None


# ════════════════════════════════════════════════════════════════════════════
# TC-7 · phase 0's leak investigation — a finished order with NO connection
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_003_tc7_an_order_with_no_connection_is_in_the_queue_with_a_dash(
    dana, brazos
):
    """**Phase 0's exit test ends here.** Until `metering/0044` this row could
    not exist at all — the column was NOT NULL — so a leak investigation on a
    meter that has been in the ground for years had nowhere to be recorded, let
    alone approved."""
    with tenant_ctx(brazos):
        cedar = make_premises(dana, address_line="77 Cedar Ct", services_available=["water"])
        leak = work_services.raise_work_order(
            dana,
            {"type": "Leak investigation", "service": "water", "premises_id": cedar["id"]},
        )
        field_close(
            dana, leak["id"], field_data={"set_reads": []}, outcome=work_tables.OUTCOME_PASSED
        )
        work_tables.WorkOrder.objects.filter(pk=leak["id"]).update(
            completed_at=timezone.now() - timedelta(days=1)
        )
    rows = _queue(brazos, dana).data["results"]
    assert len(rows) == 1
    # `connection` is NULL, which the screen draws as a dash — never a blank,
    # because a blank cell reads as a bug and a dash reads as "none".
    assert rows[0]["connection"] is None
    # And the PREMISE column carries the anchor it does have (US-WRK-003 TC-7).
    assert rows[0]["premise"]["address"] == "77 Cedar Ct"


def test_us_wrk_003_tc7_the_queue_spans_a_build_and_a_bare_address_in_one_list(
    dana, brazos
):
    """*"Across every connection and every anchor"* is the whole point of the
    screen: a supervisor should not have to know whether a job came from a new
    connection to find out that it is waiting for them."""
    with tenant_ctx(brazos):
        connection = _build(dana, "500 Main St")
        _finished(
            dana,
            connection.id,
            order_type="Meter set",
            service="water",
            outcome=work_tables.OUTCOME_PASSED,
            days_ago=6,
        )
        cedar = make_premises(dana, address_line="77 Cedar Ct", services_available=["water"])
        leak = work_services.raise_work_order(
            dana,
            {"type": "Leak investigation", "service": "water", "premises_id": cedar["id"]},
        )
        field_close(
            dana, leak["id"], field_data={"set_reads": []}, outcome=work_tables.OUTCOME_PASSED
        )
        work_tables.WorkOrder.objects.filter(pk=leak["id"]).update(
            completed_at=timezone.now() - timedelta(days=2)
        )
    rows = _queue(brazos, dana).data["results"]
    assert [row["waiting_days"] for row in rows] == [6, 2]
    assert [row["connection"] is None for row in rows] == [False, True]
    assert [row["premise"]["address"] for row in rows] == ["500 Main St", "77 Cedar Ct"]


# ── the queue is a NULL, not a table (BR-WRK-007) ───────────────────────────
def test_us_wrk_003_the_queue_has_no_table_of_its_own():
    """**`BR-WRK-007`'s own words, asserted rather than promised.** The wave's
    exit test is *"the queue is a null, not a table"*, and the cheapest way for
    that to stop being true is for somebody to add a `work_approval_queue`
    table because a list felt like it needed one.

    ⚠ **RE-POINTED 2026-09-04, EXACTLY AS ITS OWN FAILURE MESSAGE ASKED.** It
    used to assert that `apps/work/migrations/` was EMPTY, which was true for
    about a day: wave C then landed `0001_initial` and `0002_rls_force` for the
    six reference lists, and this case went red on a commit that had done
    nothing wrong. A folder is a proxy for the rule and not the rule — Work is
    allowed tables, the QUEUE is not one — so the case now reads the migrations
    and asserts what `BR-WRK-007` actually says: **no migration in this
    repository creates a table for the approval queue.** It survives every
    later Work table and still bites the one thing it is for.
    """
    from pathlib import Path

    work_app = Path(work_api.__file__).parent
    migrations = work_app / "migrations"
    created = []
    for path in sorted(migrations.glob("0*.py")) if migrations.exists() else []:
        body = path.read_text(encoding="utf-8")
        for name in ("CreateModel", "AddField"):
            if name not in body:
                continue
            # The queue by any of the names somebody would reach for.
            for banned in ("approval_queue", "ApprovalQueue", "awaiting_approval", "AwaitingApproval"):
                if banned in body:
                    created.append(f"{path.name} mentions {banned}")
    assert created == [], (
        "a migration creates something for the approval queue — BR-WRK-007 says "
        "the queue is a query over `accepted_by IS NULL AND state = completed`, "
        f"and nothing stores it: {created}"
    )


def test_us_wrk_003_the_selector_reads_the_two_conditions_and_not_a_stored_flag(dana, brazos):
    """`WM-03` — *one query, no new table*. Proved by making the queue change
    with nothing but `accepted_by` moving: no column is set to say "queued"."""
    with tenant_ctx(brazos):
        first, _second, _third = _the_drawings_three(dana)
        assert work_selectors.awaiting_approval()["total"] == 3
        # The ONLY thing that moves is the FK. No status column, no flag.
        work_tables.WorkOrder.objects.filter(pk=first["id"]).update(accepted_by=dana.user)
        assert work_selectors.awaiting_approval()["total"] == 2
        work_tables.WorkOrder.objects.filter(pk=first["id"]).update(accepted_by=None)
        assert work_selectors.awaiting_approval()["total"] == 3


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-003@ab786097 (EP-WRK-01) · 07-endpoints.md §1 row 15 · 08-screen-layouts.md Work-009 · wireframes/Work-009.png
# generated: 2026-09-04 by the CR-070 wave B build lane
# checklist: A✔ B✔ C✔ D✔ E✔(AwaitingApprovalPage.tsx draws this) F✔ G✔ H=n/a
# gates: RED PROVED FIRST — with `accepted_by__isnull=True` dropped from the seam's queryset, TC-2 fails "an accepted order is still in the queue"; quoted in the lane report
# exceptions: the drawing's Gas and Trash rows cannot be seeded into Brazos Bend (Electric and Water only) — the types and the waiting days are the drawing's, the services are the tenant's; stated in this file's docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
