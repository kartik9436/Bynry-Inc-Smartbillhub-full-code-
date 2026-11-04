# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9688 (CR-168-BRC10 round 8, lane FIX-8A) — a visit window
#           typed in the utility's own time was stored as if it were UTC, so a
#           Brazos Bend (US Central) 08:00–12:00 read 03:00–07:00.
# Rules:    IS-8 (an instant shows in the TENANT's zone) · BR-TEN-081 (the
#           utility's own clock decides) · hard-won law 14's neighbour: the
#           suite runs in UTC, where the bug is invisible, so every case here
#           puts the tenant on America/Chicago.
# ───────────────────────────────────────────────────────
"""A window typed as *08:00–12:00* on a Central utility is 13:00Z–17:00Z, and
every surface built from it — the order, the edit form, the history line, the
technician's day, the customer's message and the printed sheet — reads it back
as 08:00–12:00."""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import dispatch, edit, mobile, print_docs, visit_notices
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc


def _central(brazos):
    from apps.tenancy import models as tenancy_models

    tenancy_models.TenantSettings.objects.filter(tenant_id=brazos.id).update(
        timezone="America/Chicago"
    )


def _reference():
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")


def _order(actor):
    premises = make_premises(actor, address_line="107 Mill Pond Ln", services_available=["water"])
    body = {"type": "Leak investigation", "service": "water", "premises_id": premises["id"]}
    return w6.create_work_order(actor, None, body)


def _technician(tenant):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(
        tenant_id=tenant.id, email="r-patel@brazos.test", full_name="R. Patel"
    )
    return work_models.Technician.objects.create(tenant_id=tenant.id, user=user)


def _booked(dana, brazos):
    """Dana books 08:00–12:00 on 6 Oct the way every screen sends it: naive."""
    _central(brazos)
    _reference()
    raised = _order(dana)
    tech = _technician(brazos)
    dispatch.record_act(
        dana,
        raised["id"],
        {
            "act": "assign",
            "technician_id": str(tech.id),
            "window_start": "2026-10-06T08:00:00",
            "window_end": "2026-10-06T12:00:00",
        },
    )
    return work_tables.WorkOrder.objects.get(pk=raised["id"]), tech


def test_a_typed_window_is_stored_in_the_utilitys_zone(dana, brazos):
    with tenant_ctx(brazos):
        order, _tech = _booked(dana, brazos)
        assert order.window_start == datetime(2026, 10, 6, 13, 0, tzinfo=UTC)
        assert order.window_end == datetime(2026, 10, 6, 17, 0, tzinfo=UTC)


def test_the_order_and_its_history_read_it_back_as_typed(dana, brazos):
    with tenant_ctx(brazos):
        order, _tech = _booked(dana, brazos)
        appointment = edit.form_values(order.id)["appointment"]
        assert (appointment["date"], appointment["start"], appointment["end"]) == (
            "2026-10-06", "08:00", "12:00",
        )
        assert edit._window_label(order) == "08:00–12:00"


def test_the_edit_page_moves_it_in_the_utilitys_zone(dana, brazos):
    with tenant_ctx(brazos):
        order, _tech = _booked(dana, brazos)
        edit.save_order_edit(
            dana,
            order.id,
            {"window_start": "2026-10-07T12:00:00", "window_end": "2026-10-07T17:00:00",
             "due_at": "2026-10-07T00:00:00"},
        )
        order.refresh_from_db()
        assert order.window_start == datetime(2026, 10, 7, 17, 0, tzinfo=UTC)
        assert order.due_at == datetime(2026, 10, 7, 5, 0, tzinfo=UTC)


def test_the_technicians_day_carries_the_utilitys_time(dana, brazos):
    with tenant_ctx(brazos):
        order, tech = _booked(dana, brazos)
        card = mobile._job_card(order, None)
        assert (card["appointment"]["start"], card["appointment"]["end"]) == ("08:00", "12:00")


def test_the_customer_text_and_the_printed_sheet_say_08_to_12(dana, brazos):
    with tenant_ctx(brazos):
        order, _tech = _booked(dana, brazos)
        context = visit_notices.customer_context(order)
        assert context["appointment_window"] == "08:00–12:00"
        assert context["appointment_date"] == "Tuesday, October 6, 2026"
        row = {
            "window_start": order.window_start.isoformat(),
            "window_end": order.window_end.isoformat(),
            "due_at": None,
        }
        assert print_docs.when_text(row) == "Tue Oct 6, 2026 · 08:00–12:00"
