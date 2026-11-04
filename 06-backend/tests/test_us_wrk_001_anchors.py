# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-001 (EP-WRK-01) — a work order may exist without a
#           connection: `connection_id` nullable, `premises_id` and
#           `account_id` beside it, at least one anchor (`WM-01` + our CHECK).
# Rules:    BR-WRK-006 (PROPOSED) · CLAUDE.md hard rule 1 (RLS FORCE unchanged
#           on `work_orders`) · hard rule 7 (the audit row names the anchor) ·
#           CR-070 §14 (phase 0 rolls back cleanly — no data moves)
# Tests:    this file — TC-1 · TC-2 · TC-3 (the Python refusal and, on this
#           suite's SQLite, Django's CheckConstraint too) · TC-4 · TC-5 (the
#           app layer half; the database half is `test_w6_connections.py`'s
#           RLS probe, which still runs over this table) · TC-6 lives in
#           `test_us_wrk_001_anchor_check_pg.py` (PostgreSQL only)
# ───────────────────────────────────────────────────────
"""US-WRK-001 — `77 Cedar Ct` gets its leak investigation.

The blueprint's one structural blocker, in its words: *"work_orders.
connection_id is NOT NULL. Every work order in the product must belong to a
new-connection build. A leak investigation, a meter exchange, a reconnect or
a backflow test … cannot be recorded at all, not even by hand."* These cases
are the exact rows of the story's §3, and every raise goes through the Work
module's own service — `apps.work.services.raise_work_order` — which is the
seam's named door onto metering's `create_work_order`.

⚠ TC-3 IS ASSERTED TWICE ON PURPOSE. First the SERVICE refuses (a sentence a
clerk can read, before any row exists); then the CHECK refuses a row written
AROUND the service. Django emits a real CHECK on SQLite as well as on
PostgreSQL, so the second half runs here too — and `test_us_wrk_001_anchor_
check_pg.py` runs it again on PostgreSQL 16 with a raw INSERT, because law 14
says the suite's vendor is not the product's.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import services as work_services
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def _cedar_court(actor):
    """`77 Cedar Ct` — a premises with a unit and NO new-connection build."""
    premises = make_premises(actor, address_line="77 Cedar Ct", services_available=["water"])
    unit = make_unit(actor, premises["id"])
    return premises, unit


def _account_on(actor, unit):
    from apps.customers import services as customers_services

    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": "2026-08-01",
            "contact": {"full_name": "Cedar Court Resident"},
            "customer": identity_fixtures.customer_block(
                "Cedar Court Resident", account_type="residential"
            ),
        },
    )


def test_us_wrk_001_tc1_a_leak_investigation_on_a_premises_with_no_build(dana, brazos):
    """TC-1: premises only, no connection — saved, numbered, `connection_id` NULL."""
    with tenant_ctx(brazos):
        premises, _unit = _cedar_court(dana)
        result = work_services.raise_work_order(
            dana,
            {"type": "Leak investigation", "service": "water", "premises_id": premises["id"]},
        )
        order = work_tables.WorkOrder.objects.get(pk=result["id"])

    assert result["order_no"] and result["order_no"].startswith("WO-")
    assert order.connection_id is None
    assert str(order.premises_id) == premises["id"]
    assert order.state == work_tables.WO_PLANNED
    assert order.mode == work_tables.MODE_OUR_CREW  # no step-1 default to inherit, so the platform's
    assert result["connection_id"] is None
    assert result["premises_id"] == premises["id"]


def test_us_wrk_001_tc2_an_account_alone_is_an_anchor(dana, brazos):
    """TC-2: `account_id` and nothing else — saved."""
    with tenant_ctx(brazos):
        _premises, unit = _cedar_court(dana)
        account = _account_on(dana, unit)
        result = work_services.raise_work_order(
            dana, {"type": "Reconnect", "service": "water", "account_id": account["id"]}
        )
        order = work_tables.WorkOrder.objects.get(pk=result["id"])

    assert order.connection_id is None and order.premises_id is None
    assert str(order.account_id) == account["id"]


def test_us_wrk_001_tc3_no_anchor_at_all_is_refused_before_any_row_exists(dana, brazos):
    """TC-3 (negative): no connection, premises, account or asset — refused."""
    with tenant_ctx(brazos):
        before = work_tables.WorkOrder.objects.count()
        with pytest.raises(errors.ValidationError) as refused:
            work_services.raise_work_order(dana, {"type": "Leak investigation"})
        assert refused.value.message_key == "work.order.anchor_required"
        assert refused.value.br_ref == "BR-WRK-006"
        assert work_tables.WorkOrder.objects.count() == before


def test_us_wrk_001_tc3_the_check_refuses_a_row_written_around_the_service(dana, brazos):
    """TC-3, the database half: `ck_work_orders_has_anchor` on THIS vendor.

    A row built straight through the ORM with every anchor empty must be
    refused by the constraint, not merely by `create_work_order`'s own guard.
    """
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError) as refused:
            with transaction.atomic():
                work_tables.WorkOrder.objects.create(tenant_id=brazos.id, type="floating", order_no="WO-0")
        assert (
            "ck_work_orders_has_anchor" in str(refused.value).lower()
            or "check" in str(refused.value).lower()
        )


def test_us_wrk_001_tc4_every_existing_order_keeps_its_connection(dana, brazos, audit_rows):
    """TC-4 (negative): the migration moves no data — a build's orders keep
    their connection, and the positional contract every caller uses still
    holds exactly as before."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        connection = work_tables.Connection.objects.get(pk=created["id"])
        state_before = connection.state
        old_shape = w6.create_work_order(dana, connection.id, {"type": "meter set"})
        order = work_tables.WorkOrder.objects.get(pk=old_shape["id"])
        assert order.connection_id == connection.id
        assert order.premises_id is None and order.account_id is None
        # The audit row names the anchor (hard rule 7) — read from the BE-03
        # capture sink the helpers register, which is where every row lands here.
        rows = [
            row
            for row in audit_rows
            if row["action"] == "work_order.created" and str(row["entity_id"]) == str(order.id)
        ]
        assert len(rows) == 1
        assert rows[0]["after"]["connection_no"] == connection.connection_no
        assert rows[0]["after"]["premise_no"] is None

        # …and an order with NO connection leaves `refresh_connection_state` alone:
        # the build's cached state is what it was, and the new order is not its.
        cedar, _unit = _cedar_court(dana)
        work_services.raise_work_order(
            dana, {"type": "Leak investigation", "premises_id": cedar["id"]}
        )
        connection.refresh_from_db()
        assert connection.state == state_before
        assert work_tables.WorkOrder.objects.filter(connection=connection).count() == 1


def test_us_wrk_001_tc4_the_migration_writes_no_data():
    """TC-4, read off the migration itself: four schema operations and no
    RunPython, no RunSQL — nothing can have moved a row."""
    from django.db import migrations
    from importlib import import_module

    module = import_module("apps.metering.migrations.0044_cr070_a_work_order_anchors")
    ops = module.Migration.operations
    assert [type(op).__name__ for op in ops] == [
        "AlterField",
        "AddField",
        "AddField",
        "AddConstraint",
    ]
    assert not any(isinstance(op, (migrations.RunPython, migrations.RunSQL)) for op in ops)
    assert ops[3].constraint.name == "ck_work_orders_has_anchor"


def test_us_wrk_001_tc5_lone_star_ridge_sees_none_of_brazos_bends_orders(
    dana, erin, brazos, lonestar
):
    """TC-5 (tenant isolation), the app layer: Lone Star lists zero of Brazos
    Bend's orders. The database half — RLS FORCE, unchanged by metering/0044 —
    is `test_w6_connections.py::test_w6_rls_scopes_all_five_tables` on
    PostgreSQL, which still probes `work_orders`."""
    from apps.work import selectors as work_selectors

    with tenant_ctx(brazos):
        premises, _unit = _cedar_court(dana)
        raised = work_services.raise_work_order(
            dana, {"type": "Leak investigation", "premises_id": premises["id"]}
        )
        assert work_selectors.open_orders()["total"] >= 1
    with tenant_ctx(lonestar):
        page = work_selectors.open_orders()
        assert page["total"] == 0
        assert raised["id"] not in {row["id"] for row in page["rows"]}
        # And Lone Star cannot raise ON Brazos Bend's premises: absent, not forbidden.
        with pytest.raises(errors.NotFoundError):
            work_services.raise_work_order(
                erin, {"type": "Leak investigation", "premises_id": premises["id"]}
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-001@87b94265 (EP-WRK-01 §3 TC-1..TC-6) · BR-WRK-006 · metering/0044
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D=deferred(POST /work-orders is wave B's) E✔ F✔ G✔ H=n/a
# gates: RED PROVED FIRST — with the CheckConstraint removed from the model, `tc3_the_check_refuses_a_row_written_around_the_service` fails with "DID NOT RAISE"; with the Python guard removed, `tc3_no_anchor_at_all` fails the same way. Quoted in the lane report.
# exceptions: TC-6 (PostgreSQL) is its own file so the SQLite suite reports a SKIP rather than a false PASS (law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
