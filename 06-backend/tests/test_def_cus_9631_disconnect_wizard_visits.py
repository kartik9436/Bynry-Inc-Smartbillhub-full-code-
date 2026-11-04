# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9631 (CR-168-BRC10 round 8, lane FIX-8A) — the disconnect
#           wizard's step 3 asks *Who goes: Work order* per service point and
#           its confirm step says *1 work orders will be raised*; the commit
#           sent no visit and the server raised none (DSC-26-0001/0002, 0 raised).
# Rules:    BR-CUS-1098 (one work order per affected service point) ·
#           BR-WRK-055 (a failed raise never fails the flow) · BR-WRK-024
#           (every order carries its source) · hard-won law 14
# ───────────────────────────────────────────────────────
"""`POST /disconnects/schedule` carries the wizard's work-order rows, and each
becomes a job standing on the account, raised by *Disconnection*, carrying the
clerk's instruction to the field."""

from __future__ import annotations

from typing import Any

import pytest

from apps.customers import disconnects
from apps.customers import transfer_disconnect_api as api
from apps.work import connection_models as work_tables
from apps.work import from_flows
from apps.work import services as work_services

from tests.test_def_cus_7680_schedule_refusals_carry_their_code import plant_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def test_9631_the_schedule_raises_one_job_per_work_order_row(dana, brazos, monkeypatch):
    with tenant_ctx(brazos):
        for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
            work_services.seed_reference_list(code, [], "test")
        account = plant_account(brazos, tag="9631")

    # The ladder half is proved elsewhere (`test_def_cus_7680_*`); this case is
    # about what the commit does with the rows, so the schedule itself is
    # answered as scheduled.
    def scheduled(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"state": "scheduled", "case_no": "DSC-26-0001"}

    monkeypatch.setattr(disconnects, "schedule_cut", scheduled)
    response = api_call(
        api.schedule_cut,
        "post",
        "/api/disconnects/schedule",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "account_id": str(account.id),
            "cut_on": "2026-10-20",
            "services": {"water": "full"},
            "visits": [{"service": "water", "instruction": "Lock the curb stop"}],
        },
    )
    assert response.status_code == 200, response.data
    raised = response.data.get("work_orders") or []
    assert len(raised) == 1, response.data

    with tenant_ctx(brazos):
        order = work_tables.WorkOrder.objects.get(pk=raised[0]["id"])
        assert order.source == from_flows.FLOW_DISCONNECT
        assert str(order.account_id) == str(account.id)
        assert order.technician_notes == "Lock the curb stop"
