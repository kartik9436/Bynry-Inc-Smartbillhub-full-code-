# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-6737 — `work_orders.outcome` had no CHECK, and live data
#           already held `completed` (a STATE word) in it
# Change:   CR-168-BRC10 (lane FIN-S, final round) · metering/0076
# Rules:    B18 §8.3 (the five outcomes) · hard rule 7 · hard-won law 14
# Tests:    this file — the CHECK half is skipped on SQLite BY DESIGN
# ───────────────────────────────────────────────────────
"""Three layers, each proved: the door refuses an outcome outside the five, the
database refuses one written underneath the door, and `metering/0076` clears a
value already stored and audits what it was."""

from __future__ import annotations

import importlib

import pytest
from django.db import IntegrityError, connection, transaction

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from core import errors

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_actor, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def _migration():
    return importlib.import_module("apps.metering.migrations.0076_def_wrk_6737_outcome_check")


def _order(actor, address):
    premises = make_premises(actor, address_line=address)
    unit = make_unit(actor, premises["id"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    w6.add_connection_service(actor, created["id"], service_code="water", unit_id=unit["id"])
    return w6.create_work_order(actor, created["id"], {"type": "Meter set", "service": "water"})


def test_the_door_refuses_a_state_word_as_an_outcome(dana, brazos):
    with tenant_ctx(brazos):
        order = _order(dana, "6737 Door St")
        tech = field_actor(order["id"], dana)
        with pytest.raises(errors.ValidationError) as raised:
            w6.submit_field_result(tech, order["id"], field_data={}, outcome="completed")
        stored = work_tables.WorkOrder.objects.get(pk=order["id"]).outcome

    assert raised.value.message_key == "metering.work_order.outcome_unknown"
    assert stored is None


def test_the_constraint_is_declared_on_the_model():
    names = {c.name for c in work_tables.WorkOrder._meta.constraints}
    assert "ck_work_orders_outcome" in names
    assert _migration().OUTCOMES == work_tables.WORK_ORDER_OUTCOMES


@requires_postgres
def test_the_database_refuses_an_outcome_written_underneath_the_door(dana, brazos):
    with tenant_ctx(brazos):
        order = _order(dana, "6737 Check St")
        with pytest.raises(IntegrityError) as raised:
            with transaction.atomic():
                work_tables.WorkOrder.objects.filter(pk=order["id"]).update(outcome="completed")
        # The savepoint took the failure; the transaction is still usable.
        work_tables.WorkOrder.objects.filter(pk=order["id"]).update(outcome="passed")

    assert "ck_work_orders_outcome" in str(raised.value)


@requires_postgres
def test_the_migration_clears_a_stored_state_word_and_audits_it(dana, brazos):
    from django.apps import apps as live_apps

    from apps.audit.models import AuditLog

    with tenant_ctx(brazos):
        order = _order(dana, "6737 Clean St")
        with connection.cursor() as cursor:
            # Deferred triggers on `work_orders` hold pending events from the
            # inserts above; an ALTER is refused until they fire.
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("ALTER TABLE work_orders DROP CONSTRAINT ck_work_orders_outcome")
        work_tables.WorkOrder.objects.filter(pk=order["id"]).update(outcome="completed")

        class _Editor:
            pass

        editor = _Editor()
        editor.connection = connection
        _migration().clear_outside_values(live_apps, editor)
        stored = work_tables.WorkOrder.objects.get(pk=order["id"]).outcome
        trail = AuditLog.objects.filter(
            action="work_order.outcome_cleared", entity_id=order["id"]
        ).first()

    assert stored is None
    assert trail is not None and trail.before == {"outcome": "completed"}
