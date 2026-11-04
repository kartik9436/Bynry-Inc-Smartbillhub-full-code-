# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 debt sweep D4 (PO 2026-08-22: "resolve any open technical
#           debt related to assets") — the BTM tab's "Exported · <month>" KPI
#           rendered "—" forever: no export rollup was served anywhere.
# Screens:  S49 Behind-the-meter tab (the r10 KPI strip's third card)
# Rules:    BR-MET-016/053 (committed lineage heads only) · BR-AST-029 (export
#           records exist ONLY on net-metering assets — no asset join needed) ·
#           BR-AST-025 (quantities only, never money) · BR-TEN-020 (the
#           tenant's calendar, never a wall clock) · CLAUDE.md rule 3 (a
#           quantity never travels without its unit — totals GROUP by unit,
#           two units are never added) · DEF-324 (one query)
# Tests:    this file
# Impacts:  apps/metering/selectors.py (export_rollup_last_month) ·
#           apps/assets/seams.py (the forwarder) · apps/assets/api.py (the
#           BTM list answer carries `export_rollup`)
# ───────────────────────────────────────────────────────
"""CR-028 debt sweep D4 — the export rollup behind "Exported · <month>".

RED-FIRST: run against the tree as W5 left it,
`apps.metering.selectors.export_rollup_last_month` did not exist
(AttributeError on the selector test; the API test failed with
`KeyError: 'export_rollup'`) — quoted in the lane report.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.metering import selectors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: Pinned tenant "today": mid-September ⇒ the last COMPLETE month is August.
TODAY = date(2026, 9, 15)


def _net_meter(actor, asset_no, *, service="electric", uom="kWh", **kw):
    from apps.assets import services as asset_services

    asset = a_meter(actor, asset_no=asset_no, service=service, uom=uom, **kw)
    asset_services.update_asset(actor, asset["id"], {"net_metering": True})
    return asset


def test_the_rollup_sums_the_export_channel_over_the_last_complete_month(brazos, marcus):
    """August export heads sum; July's and September's rows stay out, and so
    does August's TOTAL (consumption) channel."""
    with tenant_ctx(brazos):
        asset = _net_meter(marcus, "M-4021")
        # July (prior month — outside the window).
        commit_read(
            marcus, asset["id"], day="2026-07-03", value="120", channel="export", consumption="120"
        )
        # August — the last complete month: two export cycles, 21 + 9 kWh.
        commit_read(
            marcus, asset["id"], day="2026-08-03", value="141", channel="export", consumption="21"
        )
        commit_read(
            marcus, asset["id"], day="2026-08-28", value="150", channel="export", consumption="9"
        )
        # August TOTAL channel — consumption, never counted as export.
        commit_read(marcus, asset["id"], day="2026-08-03", value="43566", consumption="702")
        # September (the running month — incomplete, excluded).
        commit_read(
            marcus, asset["id"], day="2026-09-03", value="163", channel="export", consumption="13"
        )

        rollup = selectors.export_rollup_last_month(today=TODAY)
        assert rollup["month"] == "2026-08-01"
        assert rollup["totals"] == [{"quantity": "30.000000", "unit": "kWh"}]


def test_the_rollup_groups_by_unit_and_never_adds_two_units(brazos, marcus):
    """Rule 3: a kgal export total and a kWh export total are TWO totals."""
    with tenant_ctx(brazos):
        electric = _net_meter(marcus, "M-4021")
        water = _net_meter(
            marcus, "W-4022", service="water", uom="kgal", unit_label="Unit W", address="9 Well Rd"
        )
        commit_read(
            marcus,
            electric["id"],
            day="2026-08-03",
            value="141",
            channel="export",
            consumption="21",
        )
        commit_read(
            marcus,
            water["id"],
            day="2026-08-03",
            value="7",
            channel="export",
            unit="kgal",
            consumption="2.5",
        )
        rollup = selectors.export_rollup_last_month(today=TODAY)
        assert rollup["totals"] == [
            {"quantity": "21.000000", "unit": "kWh"},
            {"quantity": "2.500000", "unit": "kgal"},
        ]


def test_a_superseded_export_read_is_represented_by_its_correction(brazos, marcus):
    """BR-MET-016/053: lineage heads only — the corrected figure counts once."""
    from apps.metering import models

    with tenant_ctx(brazos):
        asset = _net_meter(marcus, "M-4021")
        wrong = commit_read(
            marcus, asset["id"], day="2026-08-03", value="900", channel="export", consumption="900"
        )
        # Supersede exactly as the service does: the pointer leaves the head
        # set BEFORE the correction lands (the r8 partial-unique holds over
        # lineage HEADS, so the order is the law's own).
        right_id = uuid.uuid4()
        models.MeterRead.objects.filter(id=wrong.id).update(superseded_by_id=right_id)
        right = commit_read(
            marcus, asset["id"], day="2026-08-03", value="141", channel="export", consumption="21"
        )
        models.MeterRead.objects.filter(id=wrong.id).update(superseded_by_id=right.id)
        rollup = selectors.export_rollup_last_month(today=TODAY)
        assert rollup["totals"] == [{"quantity": "21.000000", "unit": "kWh"}]


def test_an_empty_month_serves_no_total_and_never_a_zero(brazos, marcus):
    """No export record in the window ⇒ `totals` is EMPTY — the KPI renders
    its dash; a served 0 would claim a measurement nobody took."""
    with tenant_ctx(brazos):
        asset = _net_meter(marcus, "M-4021")
        commit_read(
            marcus, asset["id"], day="2026-06-03", value="80", channel="export", consumption="80"
        )
        rollup = selectors.export_rollup_last_month(today=TODAY)
        assert rollup["month"] == "2026-08-01"
        assert rollup["totals"] == []


def test_the_missing_export_placeholder_contributes_its_recorded_zero(brazos, marcus):
    """BR-AST-029's 0-value `status=missing` placeholder is a committed record
    — it adds exactly its recorded 0, never invents a quantity."""
    with tenant_ctx(brazos):
        asset = _net_meter(marcus, "M-4021")
        from apps.metering import models

        commit_read(
            marcus, asset["id"], day="2026-08-03", value="141", channel="export", consumption="21"
        )
        # The placeholder as _ensure_export_records mints it: no register value
        # (none was supplied — none invented), consumption 0, status missing.
        models.MeterRead.objects.create(
            tenant_id=brazos.id,
            asset_id=asset["id"],
            read_at=at("2026-08-28"),
            channel="export",
            current_value=None,
            consumption=Decimal("0"),
            unit="kWh",
            source="import",
            status="missing",
            lifecycle="committed",
        )
        rollup = selectors.export_rollup_last_month(today=TODAY)
        assert rollup["totals"] == [{"quantity": "21.000000", "unit": "kWh"}]
        assert Decimal(rollup["totals"][0]["quantity"]) == Decimal("21")


# ══════════════════════════════════════════════════════════════════════════
# The BTM list answer carries the rollup (apps/assets/api.py)
# ══════════════════════════════════════════════════════════════════════════


def test_the_btm_list_answer_carries_the_rollup_and_other_tabs_do_not(brazos, marcus):
    from apps.assets import api as assets_api

    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        asset = _net_meter(marcus, "M-4021")
        commit_read(
            marcus, asset["id"], day="2026-08-03", value="141", channel="export", consumption="21"
        )

    class _User:
        id = None
        pk = None
        is_authenticated = True

    btm = api_call(
        assets_api.assets,
        "get",
        user=_User(),
        role="system_admin",
        tenant=brazos,
        query={"f.tab": "behind_the_meter"},
    )
    assert btm.status_code == 200
    rollup = btm.data["export_rollup"]
    # The API path reads the TENANT's calendar (no test pin) — the month is
    # whatever the tenant's last complete month is; the shape and the unit
    # discipline are what this asserts. The August figure itself is pinned in
    # the selector tests above.
    assert set(rollup) == {"month", "totals"}
    for entry in rollup["totals"]:
        assert set(entry) == {"quantity", "unit"} and entry["unit"]  # rule 3

    meters = api_call(
        assets_api.assets,
        "get",
        user=_User(),
        role="system_admin",
        tenant=brazos,
        query={"f.tab": "meters"},
    )
    assert meters.status_code == 200
    assert "export_rollup" not in meters.data


@pytest.mark.isolation
def test_d10__the_rollup_is_tenant_scoped(brazos, lonestar, erin):
    """CR-028 debt sweep D10 — an aggregate over meter_reads is precisely the
    query shape that leaks (HR-1). The other tenant's export month must not
    reach this tenant's KPI, in either direction."""
    with tenant_ctx(lonestar):
        foreign = _net_meter(
            erin, "LS-NET-01", service="water", uom="kgal", unit_label="F1", address="9 Foreign Rd"
        )
        commit_read(
            erin,
            foreign["id"],
            day="2026-08-10",
            value="70",
            channel="export",
            unit="kgal",
            consumption="7",
        )
    with tenant_ctx(brazos):
        rollup = selectors.export_rollup_last_month(today=TODAY)
        assert rollup["totals"] == [], "lonestar's export month leaked into brazos's KPI"
    with tenant_ctx(lonestar):
        mirror = selectors.export_rollup_last_month(today=TODAY)
        assert mirror["totals"] == [{"quantity": "7.000000", "unit": "kgal"}]
