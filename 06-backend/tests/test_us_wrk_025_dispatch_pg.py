# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-025 TC-1…TC-6 — the append-only assignment history, proved
#           where "append-only" is actually enforced · US-WRK-027 TC-3 — one
#           refused order does not take the batch down with it
# Rules:    BR-WRK-025 (never an UPDATE) · BR-WRK-027 (one row per order) ·
#           CLAUDE.md hard rule 1 (RLS FORCE) · hard rule 4's shape (a
#           correction is a new row) · hard-won law 14 (the suite runs on
#           SQLite, which has neither PL/pgSQL nor an aborted-transaction
#           state, so BOTH proofs below pass by vacuum there)
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""US-WRK-025 · US-WRK-027 — the two guarantees SQLite cannot check.

Run it with a real database:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        pytest tests/test_us_wrk_025_dispatch_pg.py

WHY THIS FILE EXISTS, IN TWO SENTENCES
--------------------------------------
`work/0009` puts a `BEFORE UPDATE OR DELETE` trigger on
`work_order_assignments` so that `BR-WRK-025`'s *never an UPDATE* holds for the
ORM, for `.update()`, for `raw()`, for a migration and for a person at a psql
prompt — **and SQLite runs no PL/pgSQL, so on the suite's own database that
trigger does not exist and every assertion about it is green over nothing.**

And `dispatch.bulk_act` gives each order its own SAVEPOINT so that one refused
order does not lose the other seven — **and SQLite has no aborted-transaction
state, so the version without the savepoint passes the entire suite and loses
the whole batch the first time a real row is refused in production.** Two
different lanes found that trap independently on 2026-08-29; it is hard-won
law 14 and this is the file that pays it off for this wave.
"""

from __future__ import annotations

import pytest
from django.db import DatabaseError, connection, transaction

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import dispatch
from apps.work import models as work_models
from apps.work import services as work_services
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _job(actor, address="77 Cedar Ct"):
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")
    premises = make_premises(actor, address_line=address, services_available=["water"])  # noqa: F405
    return w6.create_work_order(
        actor,
        None,
        {"type": "Leak investigation", "service": "water", "premises_id": premises["id"]},
    )


def _a_technician(email, name):
    from apps.identity import models as identity_models
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    user = identity_models.User.objects.create(
        tenant_id=tenant_id, email=email, full_name=name
    )
    return work_models.Technician.objects.create(tenant_id=tenant_id, user=user)


# ══════════════════════════════════════════════════════════════════════════
# BR-WRK-025 — the history cannot be rewritten, and the DATABASE is what says so
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
def test_us_wrk_025_tc1_an_update_on_an_assignment_row_is_refused_by_postgresql(dana, brazos):
    """The exit test of wave G, in one case.

    The UPDATE is issued with a CURSOR — the shape a migration, a backfill or a
    person at a psql prompt would use — so nothing Django puts between the call
    and the table can be what refused it.
    """
    with tenant_ctx(brazos):
        raised = _job(dana)
        tech = _a_technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        row = work_models.WorkOrderAssignment.objects.get(work_order_id=raised["id"])

        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE work_order_assignments SET act = 'unassign' WHERE id = %s",
                        [str(row.id)],
                    )
    message = str(refused.value)
    assert "BR-WRK-025" in message, message
    assert "append-only" in message, message

    # And the row is EXACTLY as it was — the refusal is not a partial write.
    with tenant_ctx(brazos):
        row.refresh_from_db()
        assert row.act == "assign"


@requires_postgres
def test_us_wrk_025_tc2_a_delete_is_refused_too(dana, brazos):
    """Hard rule 4's shape on a table it does not name: a correction is a new
    row (`unassign`, then `assign`), never the removal of what happened."""
    with tenant_ctx(brazos):
        raised = _job(dana)
        tech = _a_technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        row = work_models.WorkOrderAssignment.objects.get(work_order_id=raised["id"])
        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM work_order_assignments WHERE id = %s", [str(row.id)]
                    )
    assert "BR-WRK-025" in str(refused.value)
    with tenant_ctx(brazos):
        assert work_models.WorkOrderAssignment.objects.filter(pk=row.id).exists()


@requires_postgres
def test_us_wrk_025_tc3_an_orm_update_is_refused_by_the_same_trigger(dana, brazos):
    """A service-layer refusal holds for the service layer. This one holds for
    `QuerySet.update()` as well, which is how a well-meaning lane would "fix" a
    typo six months from now."""
    with tenant_ctx(brazos):
        raised = _job(dana)
        tech = _a_technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                work_models.WorkOrderAssignment.objects.filter(
                    work_order_id=raised["id"]
                ).update(act="unassign")


@requires_postgres
def test_us_wrk_025_tc4_correcting_who_has_it_is_two_new_rows_and_the_cache_follows(dana, brazos):
    """The POSITIVE half — a rule that only ever refuses is a rule nobody can
    work with. Taking a job off one person and giving it to another leaves three
    rows and one cached answer."""
    with tenant_ctx(brazos):
        raised = _job(dana)
        ortiz = _a_technician("d-ortiz@brazos.test", "D. Ortiz")
        kaur = _a_technician("j-kaur@brazos.test", "J. Kaur")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        dispatch.record_act(dana, raised["id"], {"act": "unassign"})
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(kaur.id)})

        history = list(
            work_models.WorkOrderAssignment.objects.filter(work_order_id=raised["id"]).order_by(
                "at", "id"
            )
        )
        assert [r.act for r in history] == ["assign", "unassign", "assign"]
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.assignee_technician_id == kaur.id
        # The first assignment is still readable, unedited — which is the whole
        # point of refusing the UPDATE.
        assert history[0].technician_id == ortiz.id


@requires_postgres
def test_us_wrk_025_tc5_rls_force_is_on_the_new_table(dana, brazos):
    """B2 §3 — ENABLE is not enough, because the application's migration role
    OWNS every table in this schema and `ENABLE` alone exempts the owner."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class WHERE relname = 'work_order_assignments'
            """
        )
        enabled, forced = cursor.fetchone()
    assert enabled is True, "row-level security is not ENABLED on work_order_assignments"
    assert forced is True, "row-level security is not FORCED on work_order_assignments"


@requires_postgres
def test_us_wrk_025_tc6_every_row_belongs_to_one_utility_and_zero_to_the_other(
    dana, erin, brazos, lonestar, rls
):
    """The plain-English claim in the review-ledger row, asserted: *every row
    belongs to one utility, zero to the other*.

    ⚠ **THROUGH THE PROBE ROLE, AND THE FIRST VERSION OF THIS CASE WAS WRONG.**
    It read `WorkOrderAssignment.objects.count()` inside the other tenant's
    context and expected 0. That is not a test of RLS at all: the development
    role is a SUPERUSER and **PostgreSQL exempts superusers from row-level
    security unconditionally, `FORCE` included** (`DEF-2717`), and the model has
    no default tenant filter — so it counted 1 and was right to. The database
    layer is only checkable under `sbh_rls_probe` (NOLOGIN NOSUPERUSER
    NOBYPASSRLS), which is what the `rls` fixture supplies.

    ⚠ **AND THE COORDINATOR'S WARNING APPLIES HERE:** `DEF-GOV-4024` — the
    tenant-isolation GATE runs its suite on SQLite, where 192 of 238 proofs skip
    and it still exits 0. A green gate is not evidence about this table. This
    case is.
    """
    with tenant_ctx(brazos):
        raised = _job(dana)
        tech = _a_technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})

    # (1) NOTHING is visible with no tenant set — deny by default.
    assert_denied_without_context(rls, "work_order_assignments")
    # (2) Brazos Bend's row exists for Brazos Bend and VANISHES for Lone Star.
    assert_rls_scoped(rls, "work_order_assignments", owner=brazos, intruder=lonestar)
    # (3) The WITH CHECK half — a row stamped for the other utility is refused.
    #
    # ⚠ **WRITTEN HERE RATHER THAN CALLED FROM `isolation_helpers`, AND THE
    # REASON IS WORTH THE NEXT LANE'S TIME.** The shared
    # `assert_write_into_other_tenant_refused` proves WITH CHECK by RE-STAMPING
    # one of the owner's own rows with an `UPDATE` — "the table-agnostic form",
    # as it says. **It is not table-agnostic on an APPEND-ONLY table**: this
    # one's trigger refuses every UPDATE before the policy is ever consulted, so
    # the helper reports *"a cross-tenant write was refused, but not by the RLS
    # policy"* and is exactly right. Both guarantees hold; only the probe has to
    # change, from an UPDATE to an INSERT, which is the only write this table
    # accepts at all. Any future append-only table will hit the same wall.
    with live_tenant_context(brazos.id):
        message = rls.refused(
            """
            INSERT INTO work_order_assignments (id, tenant_id, work_order_id, act, at)
            VALUES (gen_random_uuid(), %s, %s, 'assign', now())
            """,
            [str(lonestar.id), str(raised["id"])],
        )
    assert "row-level security" in message, message


@requires_postgres
def test_us_wrk_025_tc6b_the_application_layer_agrees_with_the_policy(
    dana, erin, brazos, lonestar
):
    """The other half, and it is a DIFFERENT claim: the SELECTOR filters too.

    RLS is the floor and the selector is the door. A product that relied on the
    policy alone would leak the moment anything ran as a role RLS exempts — which
    is exactly what the case above had to be rewritten around.
    """
    with tenant_ctx(brazos):
        raised = _job(dana)
        tech = _a_technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        assert dispatch.order_audit(raised["id"])["rows"]
    with tenant_ctx(lonestar):
        assert dispatch.dispatch_page()["total"] == 0
        assert dispatch.kpis()["open_total"] == 0


# ══════════════════════════════════════════════════════════════════════════
# BR-WRK-027 — the per-order savepoint, which is the ONLY thing that works here
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
def test_us_wrk_027_tc3_pg_one_refused_order_does_not_lose_the_rest_of_the_batch(
    dana, brazos, monkeypatch
):
    """⚠ **HARD-WON LAW 14, PAID OFF — AND THE FIRST VERSION OF THIS CASE COULD
    NOT FAIL.**

    On PostgreSQL a failed STATEMENT aborts the whole transaction: every later
    query raises `InFailedSqlTransaction` and the work is lost at COMMIT anyway.
    So `try: … except: continue` inside one `atomic()` is not the tidy option —
    it is the broken one, and it passes the entire SQLite suite.

    ⚠ **THE FAILURE HAS TO COME FROM THE DATABASE, AND THAT IS THE WHOLE POINT.**
    This case first used a bad order id, which `_order_or_404` refuses in PYTHON
    after a SELECT that simply found nothing — no failed statement, no aborted
    transaction. Removing `bulk_act`'s nested `atomic()` and re-running it
    **still passed**, which is the "a check that cannot fail is worse than no
    check" shape this repo has been bitten by twice. It is recorded here rather
    than quietly fixed.

    So the failure is INJECTED, deliberately and visibly: one order's write is
    preceded by an INSERT that violates `ck_work_order_assignments_act` — a real
    CHECK, refused by PostgreSQL, which is exactly the statement-level failure a
    concurrent delete or a constraint violation would produce in production. The
    other six must be assigned AND STILL BE ASSIGNED after the request ends,
    which is the half a savepoint buys and a bare `except` does not.
    """
    with tenant_ctx(brazos):
        ids = [_job(dana, f"{n} Cedar Ct")["id"] for n in range(1, 8)]
        tech = _a_technician("d-ortiz@brazos.test", "D. Ortiz")
        doomed = ids[3]

        real_refresh = dispatch._refresh_cache

        def poison_one(order, act, *args, **kwargs):
            if str(order.id) == str(doomed):
                # A REAL refused statement: `act` is one of five and this is not.
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO work_order_assignments
                            (id, tenant_id, work_order_id, act, at)
                        VALUES (gen_random_uuid(), %s, %s, 'teleport', now())
                        """,
                        [str(brazos.id), str(order.id)],
                    )
            return real_refresh(order, act, *args, **kwargs)

        monkeypatch.setattr(dispatch, "_refresh_cache", poison_one)
        outcome = dispatch.bulk_act(
            dana, {"act": "assign", "ids": ids, "technician_id": str(tech.id)}
        )
        assert outcome["failed"] == 1
        assert outcome["done"] == 6

    # ⚠ **READ IT BACK IN A NEW TRANSACTION.** What matters is not what the
    # answer said — a poisoned transaction reports success right up to COMMIT —
    # but what SURVIVED it.
    with tenant_ctx(brazos):
        assert work_models.WorkOrderAssignment.objects.count() == 6
        assert (
            work_tables.WorkOrder.objects.filter(assignee_technician_id=tech.id).count() == 6
        ), "the cache columns were rolled back with the batch — the savepoint is not doing its job"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-025 · US-WRK-027 (EP-WRK-05) · 10-execution-plan.md wave G tasks G1, G2, G4 · CLAUDE.md hard-won law 14
# generated: 2026-09-05 by the CR-070 wave G build lane
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H✔(work/0009 is the 🔒 path this file proves; review-ledger row is G5)
# gates: RED PROVED FIRST — with work/0009's trigger reverted, tc1/tc2/tc3 pass no refusal; with bulk_act's nested atomic() removed, tc3_pg reports 7 done and reads back 0 rows. Both quoted in the lane report
# exceptions: SKIPPED on SQLite by design (`requires_postgres`) — a green skip here is not a proof and the file says so in its own docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
