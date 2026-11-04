# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane PERFORMANCE — P5.1 (the headline is its
#           rows' sum), P5.4 (the schedule board's drop), P5.5 (bulk raise
#           ACROSS buildings), P5.6 (the screen reads `results`; the one-round
#           `by_job_type` twin is removed). Image 65.
# Defects:  DEF-WRK-9586 · DEF-WRK-9656
# ───────────────────────────────────────────────────────
"""The server facts the three boards stand on, proved through the API.

Runs on SQLite (the default suite) AND on PostgreSQL 16
(`DJANGO_SETTINGS_MODULE=config.settings.pgtest`) — the bulk raise is one
savepoint per job (hard-won law 14), which only PostgreSQL can prove.

RED FIRST on the tip `3cd891cfb`: `test_performance_answers_the_house_envelope_
and_no_twin` failed — `assert 'by_job_type' not in {...}` — the one-round key
SRV-4 left for this lane to remove. The other cases are PROOFS of existing
server behaviour the new screens rely on (P5.11: *"The three new screens read
existing endpoints"*), and passed there too; they are here so the day that
behaviour moves, the board that reads it goes red with it.
"""

from __future__ import annotations

import datetime as dt
from datetime import timedelta

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from apps.work import api as work_api
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_asset, make_premises, make_unit
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db

T0 = dt.datetime(2026, 9, 1, 9, 0, tzinfo=dt.timezone.utc)


def _reference():
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")
    work_services.seed_reference_list("work_skills", [], "test")


def _done(tenant, premises, order_no, *, completed, due=None, kind="Meter set"):
    row = work_tables.WorkOrder.objects.create(
        tenant=tenant, type=kind, order_no=order_no, premises_id=premises["id"],
        state=work_tables.WO_COMPLETED, completed_at=completed, due_at=due,
    )
    work_tables.WorkOrder.objects.filter(pk=row.pk).update(created_at=T0)
    return row


def _get(view, path, brazos, dana, query=None):
    response = api_call(
        view, "get", f"/api/{brazos.subdomain}/{path}",
        user=dana.user, role="system_admin", tenant=brazos, query=query or {},
    )
    assert response.status_code == 200, response.data
    return response.data


# ── P5.6 · DEF-WRK-9656 — the house envelope, and no unpaged twin ───────────
def test_performance_answers_the_house_envelope_and_no_twin(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        premises = make_premises(dana, address_line="70 Envelope Way")
        _done(brazos, premises, "p-1", completed=T0 + timedelta(hours=1), due=T0 + timedelta(hours=4))
        _done(brazos, premises, "p-2", completed=T0 + timedelta(hours=9), due=T0 + timedelta(hours=4),
              kind="Service drop")
    body = _get(work_api.work_performance, "work/performance", brazos, dana, {"page": 1, "per": 50})
    assert "by_job_type" not in body
    assert body["count"] == 2 and len(body["results"]) == 2


# ── P5.1 · DEF-WRK-9586 — the headline is the sum of its rows, through the API ──
def test_the_headline_tiles_are_the_sum_of_the_rows(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        premises = make_premises(dana, address_line="71 Headline Rd")
        _done(brazos, premises, "h-1", completed=T0 + timedelta(hours=1), due=T0 + timedelta(hours=4))
        _done(brazos, premises, "h-2", completed=T0 + timedelta(hours=9), due=T0 + timedelta(hours=4))
        # No due date: the default target's 72 h — done in 100 h, missed.
        _done(brazos, premises, "h-3", completed=T0 + timedelta(hours=100), kind="Main tap")
    body = _get(work_api.work_performance, "work/performance", brazos, dana, {"page": 1, "per": 50})
    rows = body["results"]
    assert sum(r["volume"] for r in rows) == body["tiles"]["volume"] == 3
    assert sum(r["sla_measured"] for r in rows) == body["tiles"]["sla_measured"] == 3
    assert sum(r["sla_met"] for r in rows) == body["tiles"]["sla_met"] == 1
    assert body["tiles"]["sla_met_pct"] == "33.3"
    sla = _get(work_api.work_settings_sla, "work/settings/sla", brazos, dana)
    assert sla["hours"] == 72


# ── P5.5 · bulk raise ACROSS buildings: no premises travels ─────────────────
def test_bulk_raise_across_two_buildings_stands_each_job_on_its_own(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        template = work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id, name="Meter test", scope="per_asset",
            service=tenancy_models.Service.objects.get(code="water"), version=1,
        )
        made = []
        for n, address in enumerate(("14 Willow Bend", "8 Quarry Lane")):
            premises = make_premises(dana, address_line=address, services_available=["water"])
            unit = make_unit(dana, premises["id"], label=f"Unit {n + 1}")
            meter = make_asset(dana, asset_no=f"W-60{n}0", service="water", unit_id=unit["id"],
                               unit="gal", install_date="2026-01-15")
            made.append((premises, meter))
    response = api_call(
        work_api.work_orders_bulk_raise, "post", f"/api/{brazos.subdomain}/work-orders/bulk-raise",
        user=dana.user, role="system_admin", tenant=brazos,
        data={"template_id": str(template.id), "type": "Meter test",
              "asset_ids": [m["id"] for _, m in made], "idempotency_key": "across-1",
              "priority_id": None, "due_on": None, "assignee": None, "custom_data": {},
              "source": "dispatcher"},
    )
    assert response.status_code == 200, response.data
    assert response.data["done"] == 2 and response.data["failed"] == 0
    with tenant_ctx(brazos):
        for result, (premises, meter) in zip(response.data["results"], made):
            order = work_tables.WorkOrder.objects.get(pk=result["id"])
            assert str(order.premises_id) == str(premises["id"])
            assert result["asset"]["asset_no"] == meter["asset_no"]
    # A second press answers the first and raises nothing (P2.12).
    again = api_call(
        work_api.work_orders_bulk_raise, "post", f"/api/{brazos.subdomain}/work-orders/bulk-raise",
        user=dana.user, role="system_admin", tenant=brazos,
        data={"template_id": str(template.id), "type": "Meter test",
              "asset_ids": [m["id"] for _, m in made], "idempotency_key": "across-1"},
    )
    assert again.data["replayed"] is True
    with tenant_ctx(brazos):
        assert work_tables.WorkOrder.objects.filter(tenant_id=brazos.id, template_id=template.id).count() == 2


# ── P5.4 · the drop: an assign with a window lands in that day's load ────────
def test_a_drop_on_a_day_counts_in_that_holders_load_that_day(brazos, dana):
    from apps.identity import models as identity_models

    with tenant_ctx(brazos):
        _reference()
        premises = make_premises(dana, address_line="72 Board St")
        user = identity_models.User.objects.create(tenant_id=brazos.id, email="ortiz@x.test", full_name="D. Ortiz")
        tech = work_models.Technician.objects.create(tenant_id=brazos.id, user=user, status="on_shift")
        raised = w6.create_work_order(dana, None, {"type": "Meter set", "premises_id": premises["id"]})
    before = _get(work_api.raise_candidates, "work/candidates", brazos, dana, {"on": "2026-10-06"})
    row = next(r for r in before["results"] if r["id"] == str(tech.id))
    assert row["advice"]["jobs_that_day"] == 0
    response = api_call(
        work_api.work_orders_bulk, "post", f"/api/{brazos.subdomain}/work-orders/bulk",
        user=dana.user, role="system_admin", tenant=brazos,
        data={"act": "assign", "ids": [raised["id"]], "technician_id": str(tech.id),
              "window_start": "2026-10-06T08:00:00", "window_end": "2026-10-06T12:00:00"},
    )
    assert response.status_code == 200, response.data
    assert response.data["done"] == 1
    after = _get(work_api.raise_candidates, "work/candidates", brazos, dana, {"on": "2026-10-06"})
    row = next(r for r in after["results"] if r["id"] == str(tech.id))
    assert row["advice"]["jobs_that_day"] == 1
    queue = _get(work_api.work_orders, "work-orders", brazos, dana, {"technician": "none"})
    assert raised["id"] not in [r["id"] for r in queue["results"]]
