# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9679 (CR-168-BRC10 round 7, lane WALK-A) — image 22's Accept
#           confirm reads *"101 Silver Creek Rd · Water · closed by D. Ortiz"*;
#           the Approvals queue row served no closer, so the dialog could not say
#           who did the work the office is about to accept.
# Rules:    ruling 18 (the field completes, the office accepts) · B14 rule 31
#           (a name, never an id)
# ───────────────────────────────────────────────────────
"""The Approvals row names WHO closed the job — the same name the order page's
*Closed by* reads (`dispatch._closed_of`), from the close's own audit row."""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import api as work_api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_close, make_premises, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _audit_lands_in_the_table(audit_rows):  # after the helpers' capture sink
    """The close's audit row IS what this read reads, so the platform's own
    store — not the helpers' capture list — must receive it (the
    `test_cr137_p3_detail_cancel_receipt` posture)."""
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


def test_def_wrk_9679_the_queue_row_names_the_technician_who_closed_it(dana, brazos):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="101 Silver Creek Rd")
        order = w6.create_work_order(
            dana, None, {"type": "Meter set", "service": "water", "premises_id": premises["id"]}
        )
        field_close(dana, order["id"], field_data={"set_reads": []}, outcome=work_tables.OUTCOME_PASSED)
    response = api_call(
        work_api.work_orders_awaiting_approval,
        "get",
        f"/api/{brazos.subdomain}/work-orders/awaiting-approval",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    assert response.status_code == 200, response.data
    row = next(r for r in response.data["results"] if r["order_no"] == order["order_no"])
    # `field_close` closes as the job's own technician (`F. Close` when nobody
    # held it) — never Dana at her desk.
    assert row["closed_by"] == {"name": "F. Close"}


def test_def_wrk_9679_a_row_with_no_recorded_closer_says_none_not_a_guess(dana, brazos):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="12 Harbour View")
        order = w6.create_work_order(
            dana, None, {"type": "Meter set", "service": "water", "premises_id": premises["id"]}
        )
        # A finished job with NO close row — the seeded history's shape (a
        # demo job planted as completed). `audit_log` is append-only on
        # PostgreSQL, so the absence is made by never writing the row, not by
        # deleting it: the column is set directly, as the seed does.
        from django.utils import timezone

        work_tables.WorkOrder.objects.filter(pk=order["id"]).update(
            state="completed", outcome=work_tables.OUTCOME_PASSED, completed_at=timezone.now()
        )
    response = api_call(
        work_api.work_orders_awaiting_approval,
        "get",
        f"/api/{brazos.subdomain}/work-orders/awaiting-approval",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    row = next(r for r in response.data["results"] if r["order_no"] == order["order_no"])
    assert row["closed_by"] is None
