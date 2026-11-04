# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9696 — the disconnect case page listed no work order: since
#           DEF-CUS-9631 the wizard's cut visit is raised (source disconnect,
#           source_ref = the case number) and GET /disconnects/{ref} read none.
# Change:   CR-168-BRC10 (lane FIN-S, final round)
# Rules:    BR-CUS-1098 (one job per service point the clerk sends a crew to) ·
#           BR-WRK-024 (every order carries its source) · B14 rule 31 (the
#           job's number, never its id)
# ───────────────────────────────────────────────────────
"""The case record carries `work_orders`: the jobs raised for it, each with
its `WO-` number and state — or the reason there are none."""

from __future__ import annotations

import pytest

from apps.customers import disconnect_record, disconnects
from apps.work import from_flows
from apps.work import services as work_services

from tests.test_def_cus_7680_schedule_refusals_carry_their_code import plant_account, plant_case
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _case(brazos, tag):
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")
    account = plant_account(brazos, tag=tag)
    case = plant_case(brazos, account, state=disconnects.STATE_SCHEDULED)
    case.case_no = f"DSC-26-{tag}"
    case.save(update_fields=["case_no"])
    return account, case


def test_the_case_record_lists_the_cut_visit_it_raised(brazos, dana):
    with tenant_ctx(brazos):
        account, case = _case(brazos, "9696")
        raised = from_flows.raise_cut_visits(
            account.id, [{"service": "water", "instruction": "Lock the curb stop"}], dana
        )
        record = disconnect_record.record_detail(case.case_no)

    assert raised["count"] == 1, raised
    panel = record["work_orders"]
    assert panel["unavailable"] is None, panel
    assert panel["value"]["raised"] == 1
    order = panel["value"]["orders"][0]
    assert order["order_no"].startswith("WO-")
    assert order["state"] == "planned"
    assert order["done"] is False and order["accepted"] is False


def test_a_case_that_raised_nothing_says_so(brazos, dana):
    with tenant_ctx(brazos):
        _account, case = _case(brazos, "9697")
        record = disconnect_record.record_detail(case.case_no)

    assert record["work_orders"]["value"] is None
    assert record["work_orders"]["unavailable"]["code"] == "no_work_order_raised"
