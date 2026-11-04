# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane ORDERS-LIST — DEF-WRK-9569 (critical):
#           an order the office accepts disappears from every list
# Rules:    BR-MET-110 (the office accepts what the field sent) · CR-168 §7.4
#           J3 (completed jobs are reached through the existing STATUS filter,
#           `status=complete` — BR-WRK-026 keeps six filters) · P1.6 · P1.31
# Tests:    this file
# ───────────────────────────────────────────────────────
"""DEF-WRK-9569 — an accepted order stays findable on the Orders list.

Walked on 2.490.6 (lane WORK-CR): WO-0037 was closed in the field and accepted;
afterwards a search for ``WO-0037`` on Orders answered *No results* and the
order was gone from Approvals too. Acceptance is when cost lines and meter reads
are written, so the lost row is a money-path row.

The fix is the server's (lane SRV-1: P1.6 serves completed jobs through
``status=complete``, P1.31 moves the dispatch status to ``complete`` on the
close). The screen half — the Status filter's *Complete* option and the queue's
accept — is lane ORDERS-LIST's and is proved in
``07-frontend/src/features/work/cr168OrdersList.dom.test.tsx``.

⚠ **RELEASED 2026-10-04 by lane SRV-1 (P1.6 + P1.31); it was held with ``xfail(strict=True)`` until then.** The day
they do, this case passes, the strict marker turns that into a failure naming
the defect, and the marker comes off in the commit that closes the row.

The close is made by the job's own TECHNICIAN, never by the office (ruling 18,
P1.34): a fixture that closed it as Dana would start failing for a different
reason the day the completion guard lands.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import dispatch
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _technician(email: str, name: str):
    from apps.identity import models as identity_models
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    user = identity_models.User.objects.create(tenant_id=tenant_id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant_id, user=user)


def test_def_wrk_9569_an_accepted_order_is_found_by_its_number(dana, brazos):
    """Fails on the tip with ``assert 0 == 1`` — the list's base queryset is
    open-only, so no filter can reach a completed job."""
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        work_services.seed_reference_list("work_order_types", [], "test")
        premises = make_premises(dana, address_line="240 Sable Court", services_available=["water"])
        raised = w6.create_work_order(
            dana, None, {"type": "Site inspection", "service": "water", "premises_id": premises["id"]}
        )
        tech = _technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        w6.submit_field_result(tech.user, raised["id"], field_data={"ok": True}, outcome="passed")
        w6.accept_field_result(dana, raised["id"])

        order_no = work_tables.WorkOrder.objects.get(pk=raised["id"]).order_no
        page = dispatch.dispatch_page(q=order_no, filters={"status": "complete"})
        assert page["total"] == 1
        assert page["rows"][0]["order_no"] == order_no
