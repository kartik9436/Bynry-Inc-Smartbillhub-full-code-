# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-003 (EP-WRK-01) TC-5 — the approval queue is one tenant's
#           and RLS is what makes that true, not the Python filter above it.
#           US-WRK-002 TC-6 — the same, for the thirteen write doors.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE; never touch a tenant table
#           without `app.tenant_id`) · hard-won law 14 (the suite runs on
#           in-memory SQLite, which has no row-level security at all, so a
#           claim about RLS proved there is a claim about nothing) ·
#           BR-WRK-007 · BR-TEN-003
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""US-WRK-003 / US-WRK-002 on real PostgreSQL — the queue below the ORM.

Run it with a real database:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        DATABASE_URL=postgres://…/sbh_cr070b \\
        pytest tests/test_us_wrk_003_queue_pg.py

⚠ **WHY THIS FILE EXISTS AND WHAT THE SQLITE SUITE CANNOT SAY.** `config/
settings/test.py` hardcodes in-memory SQLite and ignores `DATABASE_URL` (law
14). SQLite has **no row-level security**, so `test_us_wrk_003_queue.py`'s
isolation case proves only that `apps/work/seams/metering_seam.py` writes
`tenant_id=` into its own `filter()`. That is worth proving and it is not the
rule: hard rule 1 says the DATABASE refuses, so that a query which forgot the
filter — a raw cursor, a migration, a future selector — returns nothing rather
than everything.

⚠ **AND A RAW CURSOR ON THIS CONNECTION IS NOT ENOUGH EITHER — THE FIRST DRAFT
OF THIS FILE PROVED NOTHING AND WENT RED SAYING SO.** The role the app connects
as in dev and CI, `smartbillhub`, **is a PostgreSQL superuser** (`rolsuper = t`,
measured), and **a superuser bypasses row-level security unconditionally, FORCE
or not**. So the draft's two cases read Brazos Bend's row under Lone Star
Ridge's marker and under no marker at all — not because RLS was missing, but
because the policy was never consulted. Had the assertions been written the
other way round they would have passed, green and vacuous, and reported a
guarantee this file cannot see.

`tests/isolation_helpers.py` had already met this and solved it: the `rls`
fixture runs every statement inside `SET ROLE sbh_rls_probe`, a NOLOGIN
NOSUPERUSER **NOBYPASSRLS** role, and `assert_is_a_real_proof()` fails rather
than skips if that role could bypass. This file uses it, so the assertions below
are about the DATABASE and not about the connection's privileges.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import selectors as work_selectors
from apps.work import services as work_services

from tests.isolation_helpers import (  # noqa: F401 — `rls`/`rls_probe_role` are fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import field_close  # CR-168 P1.34 — close as the field
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def _finished_order_on_a_build(actor, address, days_ago):
    premises = make_premises(actor, address_line=address)
    unit = make_unit(actor, premises["id"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    w6.add_connection_service(actor, created["id"], service_code="water", unit_id=unit["id"])
    order = w6.create_work_order(
        actor, created["id"], {"type": "Meter set", "service": "water"}
    )
    field_close(actor, order["id"], field_data={}, outcome=work_tables.OUTCOME_PASSED)
    work_tables.WorkOrder.objects.filter(pk=order["id"]).update(
        completed_at=timezone.now() - timedelta(days=days_ago)
    )
    return order


@requires_postgres
def test_us_wrk_003_tc5_the_queue_is_denied_outright_with_no_tenant_marker(dana, brazos, rls):
    """**Hard rule 1, from underneath the ORM and under a role RLS applies to.**

    With no `app.tenant_id` the table does not return zero rows — it ERRORS. The
    policy's `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL
    and the read is refused, which is the strongest form of the rule and the one
    `assert_denied_without_context` exists to state."""
    with tenant_ctx(brazos):
        _finished_order_on_a_build(dana, "500 Main St", 6)
    assert_denied_without_context(rls, "work_orders")


@requires_postgres
def test_us_wrk_003_tc5_lone_star_ridge_cannot_read_brazos_bends_queue_at_the_table(
    dana, erin, brazos, lonestar, rls
):
    """Not *"the selector filtered it out"* — **the table refuses**. The row is
    invisible under the other tenant's marker, so a query that forgot its filter
    returns nothing rather than everything.

    The app-layer filter is deliberately NOT in this path: the assertion runs on
    a raw `SELECT` under `sbh_rls_probe`, so what scopes it is the policy."""
    with tenant_ctx(brazos):
        order = _finished_order_on_a_build(dana, "500 Main St", 6)
    assert_rls_scoped(
        rls,
        "work_orders",
        owner=brazos,
        intruder=lonestar,
        owner_ids={order["id"]},
    )


@requires_postgres
def test_us_wrk_003_tc5_the_queues_own_two_conditions_are_scoped_by_the_policy(
    dana, erin, brazos, lonestar, rls
):
    """The same, asked as the QUEUE asks it: `state = completed AND accepted_by
    IS NULL`, with no tenant clause in the SQL at all."""
    with tenant_ctx(brazos):
        _finished_order_on_a_build(dana, "500 Main St", 6)

    sql = "SELECT count(*) FROM work_orders WHERE state = 'completed' AND accepted_by IS NULL"
    with live_tenant_context(brazos.id):
        ours = rls.scalar(sql)
    with live_tenant_context(lonestar.id):
        theirs = rls.scalar(sql)

    assert ours == 1, "the tenant's own queue is readable under its own marker"
    assert theirs == 0, (
        "LEAK — Lone Star Ridge's marker read Brazos Bend's approval queue. "
        "The queue is a query over a shared table, so RLS is the only thing "
        "between one utility's finished jobs and another's screen."
    )


@requires_postgres
def test_us_wrk_003_tc7_a_leak_investigation_closes_and_reaches_the_queue_on_postgresql(
    dana, brazos
):
    """**`DEF-WRK-3635`, end to end and on the real database.**

    Raise a job on an address with no build, send its field result, and accept
    it. Every one of those three steps read `order.connection` unguarded before
    this wave, so each raised `AttributeError` — a 500 — on the exact order
    phase 0 exists to make possible: it could be raised and then never closed.

    On PostgreSQL rather than SQLite for law 14's reason and one more: the
    acceptance runs inside `transaction.atomic()` and posts event reads through
    another module's door, so a failure anywhere in it aborts the transaction on
    a real database in a way SQLite does not model."""
    with tenant_ctx(brazos):
        cedar = make_premises(dana, address_line="77 Cedar Ct", services_available=["water"])
        leak = work_services.raise_work_order(
            dana,
            {"type": "Leak investigation", "service": "water", "premises_id": cedar["id"]},
        )
        assert leak["connection_id"] is None

        # STEP ONE — the field reports. It used to raise AttributeError here.
        reported = field_close(
            dana, leak["id"], field_data={"set_reads": []}, outcome=work_tables.OUTCOME_PASSED
        )
        assert reported["awaiting_review"] is True
        work_tables.WorkOrder.objects.filter(pk=leak["id"]).update(
            completed_at=timezone.now() - timedelta(days=1)
        )

        queued = work_selectors.awaiting_approval()
        assert queued["total"] == 1
        assert queued["rows"][0]["connection"] is None
        assert queued["rows"][0]["premise"]["address"] == "77 Cedar Ct"

        # STEP TWO — the human act. It used to raise AttributeError twice more.
        accepted = w6.accept_field_result(dana, leak["id"])
        # NO BUILD, so no build state — `None` rather than an invented word.
        assert accepted["connection_state"] is None
        # And no letter: "your service is live" is a sentence about a NEW
        # CONNECTION, and this job is not one. Reported, never silently skipped.
        assert accepted["communication"]["queued"] is False
        assert accepted["communication"]["no_connection"] is True

        assert work_selectors.awaiting_approval()["total"] == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-003@ab786097 · US-WRK-002@ab786097 (EP-WRK-01) · DEF-WRK-3635 · CLAUDE.md hard rule 1 · law 14
# generated: 2026-09-04 by the CR-070 wave B build lane
# checklist: A✔ B=n/a(a database proof has no screen) C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: run against a real PostgreSQL 16 (sbh_cr070b) and quoted in the lane report; skipped on the SQLite suite BY DESIGN
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
