# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-AST-10178 — the Meters, Sub-meters and Behind-the-meter lists
#           show no age and cannot be sorted oldest to newest.
# Ruling:   12-governance/02-decision-log.md "2026-10-17 — ASSET AGE ON METERS,
#           SUB-METERS AND BEHIND-THE-METER LISTS" (PO: "this is all corect")
# Rules:    hard rule 1 (tenant scoping) · NFR-3 (the sort reaches SQL) ·
#           BR-TEN-081 (the tenant's own clock decides what day a stamp is)
# Tests:    this file
# Impacts:  apps/assets/selectors.py · apps/assets/exports.py · apps/assets/seams.py
# ───────────────────────────────────────────────────────
"""The server half of asset Age: what each row serves, the `age` sort, the download.

The age STARTS from the install date, else the purchase date, else the day the
record was entered (on the tenant's clock), and ENDS today or on the retire date.
The row serves the start, which of the three it came from, the end and the
expected life; the screen does the subtraction against the tenant's today. The
download carries the subtraction too, because a file has no screen to do it.

The `age` sort orders by the START DATE: ascending is OLDEST first, the same
direction the Premises/Units `created` sort takes (`DEF-MET-10164`).
"""

from datetime import date, datetime, timezone

import pytest

from apps.assets import api as assets_api
from apps.assets import exports as asset_exports
from apps.assets import models, seams, selectors
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, make_asset, tenant_ctx

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 17)


def _set(asset, **fields):
    models.Asset.objects.filter(pk=asset["id"]).update(**fields)


def _retype(asset, code):
    tenant_id = models.Asset.objects.get(pk=asset["id"]).tenant_id
    kind = models.AssetType.objects.get(tenant_id=tenant_id, code=code)
    models.Asset.objects.filter(pk=asset["id"]).update(type=kind)


def _get(tenant, **query):
    response = api_call(
        assets_api.assets,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        query={"f.status": "all", "per": "50", **query},
    )
    assert response.status_code == 200, response.data
    return response.data["results"]


@pytest.fixture()
def fleet(brazos, dana):
    """The PO's six worked examples (today 10/17/2026), on the three tabs."""
    with tenant_ctx(brazos):
        a = make_asset(dana, asset_no="334556")  # installed 09/12/2026 → 1 mo
        _set(a, install_date=date(2026, 9, 12), purchase_date=date(2026, 1, 1))
        b = make_asset(dana, asset_no="SM-7040")  # installed 01/15/2026 → 9 mos
        _set(b, install_date=date(2026, 1, 15))
        _retype(b, "sub_meter")
        c = make_asset(dana, asset_no="AST-04413")  # bought, never installed
        _set(c, install_date=None, purchase_date=date(2024, 3, 1))
        _retype(c, "pv")
        d = make_asset(dana, asset_no="AST-00010")  # entered 10/02/2026
        _set(
            d,
            install_date=None,
            purchase_date=None,
            created_at=datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc),
        )
        _retype(d, "backflow")
        e = make_asset(dana, asset_no="M-OLD-2010")  # life 15 → past life
        _set(e, install_date=date(2010, 5, 1), expected_life_years=15)
        f = make_asset(dana, asset_no="M-RET-2012")  # retired 06/30/2025
        _set(f, install_date=date(2012, 5, 15), retire_date=date(2025, 6, 30))
    return brazos


def _by_no(rows):
    return {row["asset_no"]: row for row in rows}


# ── each start source ──────────────────────────────────────────────────────
def test_each_row_serves_where_its_age_starts(fleet):
    rows = {}
    for tab in ("meters", "sub_meters", "behind_the_meter"):
        rows.update(_by_no(_get(fleet, **{"f.tab": tab})))
    assert (rows["334556"]["age_start"], rows["334556"]["age_start_source"]) == (
        "2026-09-12",
        "install",
    ), "the install date wins over a purchase date"
    assert rows["SM-7040"]["age_start"] == "2026-01-15"
    assert (rows["AST-04413"]["age_start"], rows["AST-04413"]["age_start_source"]) == (
        "2024-03-01",
        "purchase",
    )
    assert (rows["AST-00010"]["age_start"], rows["AST-00010"]["age_start_source"]) == (
        "2026-10-02",
        "record",
    )
    assert rows["M-OLD-2010"]["expected_life_years"] == 15
    assert rows["334556"]["expected_life_years"] is None
    assert rows["334556"]["age_end"] is None


def test_a_record_date_is_read_on_the_tenants_clock(fleet):
    """BR-TEN-081: 02:00 UTC on 3 October is still 2 October in Chicago."""
    with tenant_ctx(fleet):
        tenancy_models.TenantSettings.objects.filter(tenant_id=fleet.id).update(
            timezone="America/Chicago"
        )
        models.Asset.objects.filter(asset_no="AST-00010").update(
            created_at=datetime(2026, 10, 3, 2, 0, tzinfo=timezone.utc)
        )
    row = _by_no(_get(fleet, **{"f.tab": "behind_the_meter"}))["AST-00010"]
    assert row["age_start"] == "2026-10-02"


def test_a_retired_asset_stops_ageing_on_its_retire_date(fleet):
    row = _by_no(_get(fleet, **{"f.tab": "meters"}))["M-RET-2012"]
    assert (row["age_start"], row["age_end"]) == ("2012-05-15", "2025-06-30")


# ── the sort ───────────────────────────────────────────────────────────────
def test_age_sorts_by_the_start_date_in_both_directions(fleet):
    with tenant_ctx(fleet):
        oldest_first = [
            a.asset_no for a in selectors.asset_list(filters={"status": "all"}, sort="age")
        ]
        newest_first = [
            a.asset_no
            for a in selectors.asset_list(
                filters={"status": "all"}, sort="age", direction="desc"
            )
        ]
    ours = ["M-OLD-2010", "M-RET-2012", "AST-04413", "SM-7040", "334556", "AST-00010"]
    assert [n for n in oldest_first if n in ours] == ours
    assert [n for n in newest_first if n in ours] == list(reversed(ours))


def test_the_list_endpoint_accepts_the_age_sort(fleet):
    rows = _get(fleet, **{"f.tab": "meters", "sort": "age", "dir": "asc"})
    assert [r["asset_no"] for r in rows] == ["M-OLD-2010", "M-RET-2012", "334556"]
    rows = _get(fleet, **{"f.tab": "meters", "sort": "age", "dir": "desc"})
    assert [r["asset_no"] for r in rows] == ["334556", "M-RET-2012", "M-OLD-2010"]


# ── the download ───────────────────────────────────────────────────────────
def test_the_download_carries_the_age(fleet, monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: TODAY)
    header = list(asset_exports.ASSETS.header)
    for column in ("age_start", "age_from", "age_years", "age_months", "age_days", "past_life"):
        assert column in header
    with tenant_ctx(fleet):
        by_no = {}
        for asset in selectors.asset_list(filters={"status": "all"}):
            by_no[asset.asset_no] = asset_exports.ASSETS.serialize(asset)
    expect = {
        "334556": (0, 1, 5, False),
        "SM-7040": (0, 9, 2, False),
        "AST-04413": (2, 7, 16, False),
        "AST-00010": (0, 0, 15, False),
        "M-OLD-2010": (16, 5, 16, True),
        "M-RET-2012": (13, 1, 15, False),
    }
    for number, (years, months, days, past) in expect.items():
        row = by_no[number]
        assert (row["age_years"], row["age_months"], row["age_days"], row["past_life"]) == (
            years,
            months,
            days,
            past,
        ), number
    assert by_no["AST-04413"]["age_from"] == "purchase"


# ── tenant isolation (hard rule 1) ─────────────────────────────────────────
def test_the_age_sort_never_reaches_another_tenant(fleet, lonestar, erin):
    with tenant_ctx(lonestar):
        make_asset(erin, asset_no="LS-1", service="water", unit="kgal")
    rows = _get(fleet, sort="age")
    assert "LS-1" not in {r["asset_no"] for r in rows}
    theirs = _get(lonestar, sort="age")
    assert [r["asset_no"] for r in theirs] == ["LS-1"]
