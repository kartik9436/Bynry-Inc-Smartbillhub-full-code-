# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10184 — a field job's readings, accepted into Meter Reads,
#           always posted as `new_connect`. PO ruling 2026-10-17 (decision log
#           "WHERE A USER ENTERS A METER READING", gap 7): saved with the job's
#           real event type.
# Rules:    BR-MET-128 (an event read records its event) · BR-WRK-003 ·
#           BR-WRK-024 (the order's source) · hard rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""An accepted field reading carries the event of the job that took it.

RED FIRST: at the base commit a move-out job's reading posted with
`event_context == "new_connect"` (`assert 'new_connect' == 'move_out'`), and the
reconnect case failed the same way.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.work import sync
from apps.work.seams import metering_seam

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar · erin
from tests.test_us_met_helpers import field_actor, tenant_ctx
from tests.test_us_wrk_044_046_sync import _batch, _order_on_a_meter, _rows

pytestmark = pytest.mark.django_db


def _completed_job(dana, brazos, meter_no, source):
    """A meter job the field read (1,204 kWh) and closed, raised by `source`.

    The source is stamped directly: it is the one fact this defect is about,
    and raising each kind through its own flow would test six other screens.
    """
    oid = _order_on_a_meter(dana, brazos, asset_no=meter_no)
    work_tables.WorkOrder.objects.filter(pk=oid).update(source=source)
    sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
    return oid


def _events(meter_no):
    return list(
        metering_models.MeterRead.objects.filter(asset__asset_no=meter_no).values_list(
            "event_context", flat=True
        )
    )


def test_a_move_out_jobs_reading_posts_as_a_move_out_reading(brazos, dana):
    with tenant_ctx(brazos):
        oid = _completed_job(dana, brazos, "E-40161", "move_out")
        w6.accept_field_result(dana, oid)
        assert _events("E-40161") == ["move_out"]


def test_a_reconnect_jobs_reading_posts_as_a_reconnect_reading(brazos, dana):
    """The same job, raised by a reconnection: the source is what decides."""
    with tenant_ctx(brazos):
        oid = _completed_job(dana, brazos, "E-40162", "reconnect")
        w6.accept_field_result(dana, oid)
        assert _events("E-40162") == ["reconnect"]


def test_a_job_raised_for_no_lifecycle_reason_posts_as_a_meter_read_never_new_connect(brazos, dana):
    with tenant_ctx(brazos):
        oid = _completed_job(dana, brazos, "E-40163", "dispatcher")
        w6.accept_field_result(dana, oid)
        assert _events("E-40163") == ["meter_read"]


@pytest.mark.parametrize(
    "source, event",
    [
        ("move_out", "move_out"),
        ("move_in", "move_in"),
        ("transfer", "transfer"),
        ("disconnect", "disconnect"),
        ("dunning_auto", "disconnect"),
        ("reconnect", "reconnect"),
        ("new_connect", "new_connect"),
        ("meter_read", "meter_read"),
        ("assets", "exchange"),
        ("asset_age_rule", "exchange"),
        ("dispatcher", "meter_read"),
        ("service_request", "meter_read"),
        ("failed_outcome", "meter_read"),
        (None, "meter_read"),
    ],
)
def test_the_mapping_table(source, event):
    class Order:
        pass

    order = Order()
    order.source = source
    assert metering_seam.field_read_event(order) == event
    assert event in metering_models.EVENT_CONTEXTS


def test_every_work_order_source_maps_to_a_lawful_event():
    for source in work_tables.WORK_ORDER_SOURCES:
        order = type("O", (), {"source": source})()
        assert metering_seam.field_read_event(order) in metering_models.EVENT_CONTEXTS
        assert metering_seam.field_read_event(order) != "new_connect" or source == "new_connect"


def test_tenant_isolation_another_utility_cannot_accept_the_job(brazos, dana, lonestar, erin):
    from core import errors

    with tenant_ctx(brazos):
        oid = _completed_job(dana, brazos, "E-40164", "move_out")
    with tenant_ctx(lonestar):
        with pytest.raises((errors.NotFoundError, errors.BizError, errors.AuthError)):
            w6.accept_field_result(erin, oid)
    with tenant_ctx(brazos):
        assert _events("E-40164") == []
