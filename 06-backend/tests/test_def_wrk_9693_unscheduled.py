# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9693 (CR-168-BRC10 round 8, lane FIX-8A) — a job given to a
#           technician with no visit booked never reached their Today or Week
#           list, so it could be assigned and never seen.
# Rules:    BR-WRK-035 (ordered by appointment; NULLs last) · US-WRK-041
# ───────────────────────────────────────────────────────
"""An assigned job with no visit window is on the technician's day — at the
end, marked *unscheduled* — whatever its deadline. Before the fix the day kept
it only when its SLA deadline fell inside the day (or the week), so a Normal
job (72 hours) given out this morning was invisible on Today."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import dispatch, mobile
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _technician(tenant):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(
        tenant_id=tenant.id, email="r-patel@brazos.test", full_name="R. Patel"
    )
    return work_models.Technician.objects.create(tenant_id=tenant.id, user=user)


def _raise(actor, address):
    premises = make_premises(actor, address_line=address, services_available=["water"])
    return w6.create_work_order(
        actor, None, {"type": "Leak investigation", "service": "water", "premises_id": premises["id"]}
    )


def test_an_assigned_job_with_no_visit_is_on_today_marked_unscheduled(dana, brazos):
    with tenant_ctx(brazos):
        for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
            work_services.seed_reference_list(code, [], "test")
        tech = _technician(brazos)
        booked = _raise(dana, "1 Kestrel Park")
        undated = _raise(dana, "2 Kestrel Park")
        soon = timezone.now() + timedelta(hours=2)
        dispatch.record_act(
            dana,
            booked["id"],
            {
                "act": "assign",
                "technician_id": str(tech.id),
                "window_start": soon.isoformat(),
                "window_end": (soon + timedelta(hours=2)).isoformat(),
            },
        )
        dispatch.record_act(dana, undated["id"], {"act": "assign", "technician_id": str(tech.id)})
        # A Normal deadline is days away — outside Today, and outside the Week.
        work_tables.WorkOrder.objects.filter(pk=undated["id"]).update(
            due_at=timezone.now() + timedelta(days=9)
        )

        actor = SimpleNamespace(id=tech.user_id, role="field_technician")
        for days in (1, 7):
            day = mobile.today(actor, days=days)
            numbers = [job["order_no"] for job in day["jobs"]]
            assert numbers == [booked["order_no"], undated["order_no"]], (days, numbers)
            flags = {job["order_no"]: job["unscheduled"] for job in day["jobs"]}
            assert flags == {booked["order_no"]: False, undated["order_no"]: True}
