# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10162 (no previous/current reading, no check result on the
#           Usage tab's Month by month) · DEF-CUS-5146 (Read on / Source stated
#           absent)
# Ruling:   decision log 2026-10-15 — USAGE TAB "MONTH BY MONTH" (PO: "go ahead")
# Rules:    BR-MET-106 (source_read_ids are the reads the month summed) ·
#           BR-MET-028 (an estimate carries no current_value) · BR-MET-021 (one
#           primary status per read) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           hard rule 3 (an explicit unit, always)
# ───────────────────────────────────────────────────────
"""The readings behind each month of `GET /accounts/{id}/usage`.

Worked row the PO was shown: *Sep 2026 · 204,207 gal · 1,240,310 · 1,444,517 ·
09/28/2026 · Manual (walk-by) · High*. TC-1 pins that exact row.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.metering import api as metering_api
from apps.metering import models as metering_models
from apps.metering import monthly_usage_reads as usage_reads
from apps.metering import monthly_usage_service as usage_service

from tests.test_br_met_106_monthly_usage import _account_on, _meter
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    erin,
    lonestar,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _read(
    tenant,
    account_id,
    asset_id,
    *,
    day,
    prior,
    current,
    consumption,
    unit="gal",
    source="manual",
    read_method="walk_by",
    status="ok",
    channel="total",
):
    """One committed read, written directly — HISTORY SETUP only (the same
    posture as `test_br_met_106_monthly_usage._read`), carrying the register
    values and the source this file is about."""
    return metering_models.MeterRead.objects.create(
        tenant_id=tenant.id,
        account_id=account_id,
        asset_id=asset_id,
        read_at=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
        channel=channel,
        prior_value=None if prior is None else Decimal(str(prior)),
        current_value=None if current is None else Decimal(str(current)),
        consumption=Decimal(str(consumption)),
        unit=unit,
        source=source,
        read_method=read_method,
        status=status,
        lifecycle="committed",
    )


def _point(payload, service_code, month):
    series = next(s for s in payload["series"] if s["service"]["code"] == service_code)
    return next(p for p in series["points"] if p["month"] == month)


def _water_account(actor, tenant, asset_no="W-9001", water_only_tenant=False):
    if water_only_tenant:
        # The isolation tenant enables Water only, and the shared fixture's
        # premises offers Electric too — which that tenant refuses.
        import tests.test_br_met_106_monthly_usage as base

        original = base.make_premises
        base.make_premises = lambda a, **kw: original(a, services_available=["water"], **kw)
        try:
            account, unit = _account_on(actor, tenant, services=("water",))
        finally:
            base.make_premises = original
    else:
        account, unit = _account_on(actor, tenant, services=("water",))
    meter = _meter(actor, unit["id"], asset_no=asset_no, service="water", uom="gal")
    return account, unit, meter


# TC-1 · the PO's worked row, exactly
def test_tc1__the_worked_row_previous_current_read_on_source_and_high(brazos, marcus):
    with tenant_ctx(brazos):
        account, _unit, meter = _water_account(marcus, brazos)
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 9, 28),
            prior="1240310",
            current="1444517",
            consumption="204207",
            status="high",
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        payload = usage_reads.usage_payload(
            account["id"], today=date(2026, 9, 1), include_reads=True
        )

    point = _point(payload, "water", "2026-09")
    assert point["quantity_display"] == "204207" and point["unit"] == "gal"
    reading = point["reading"]
    assert reading["previous_reading"] == "1240310.000000"
    assert reading["previous_reading_display"] == "1240310"
    assert reading["current_reading"] == "1444517.000000"
    assert reading["current_reading_display"] == "1444517"
    assert reading["reading_unit"] == "gal"  # hard rule 3: the pair carries its unit
    assert reading["read_on"] == "2026-09-28"
    assert reading["source"] == "manual"
    assert reading["read_method"] == "walk_by"
    assert reading["read_method_origin"] == "recorded"
    assert reading["check"] == "high" and reading["status"] == "high"
    assert reading["read_count"] == 1
    assert reading["readings_absent_reason"] is None


# TC-2 · several reads in one month: latest date/source, earliest prior, worst check
def test_tc2__several_reads_latest_date_and_source_earliest_prior_worst_check(brazos, marcus):
    with tenant_ctx(brazos):
        account, _unit, meter = _water_account(marcus, brazos, "W-9002")
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 3),
            prior="1000",
            current="1684",
            consumption="684",
            source="import",
            read_method="drive_by",
            status="low",
        )
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 31),
            prior="1684",
            current="1842",
            consumption="158",
            source="ami",
            read_method="ami",
            status="ok",
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        payload = usage_reads.usage_payload(
            account["id"], today=date(2026, 8, 1), include_reads=True
        )

    point = _point(payload, "water", "2026-07")
    reading = point["reading"]
    assert point["read_count"] == 2 and reading["read_count"] == 2
    assert reading["read_on"] == "2026-07-31", "the LATEST read's date"
    assert reading["source"] == "ami" and reading["read_method"] == "ami"
    assert reading["previous_reading_display"] == "1000", "the EARLIEST read's prior"
    assert reading["current_reading_display"] == "1842", "the LATEST read's current"
    assert reading["check"] == "low", "the WORST status of the month, not the latest"


# TC-3 · an estimated month: no current reading, check Estimated
def test_tc3__an_estimated_month_has_no_current_reading_and_says_estimated(brazos, marcus):
    with tenant_ctx(brazos):
        account, _unit, meter = _water_account(marcus, brazos, "W-9003")
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 8, 30),
            prior=None,
            current=None,
            consumption="9000",
            source="estimated",
            read_method=None,
            status="estimated",
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        payload = usage_reads.usage_payload(
            account["id"], today=date(2026, 9, 1), include_reads=True
        )

    point = _point(payload, "water", "2026-08")
    reading = point["reading"]
    assert point["estimated"] is True
    assert reading["current_reading"] is None and reading["current_reading_display"] is None
    assert reading["previous_reading"] is None
    assert reading["check"] == "estimated"
    assert reading["source"] == "estimated"
    assert reading["read_method"] is None


# TC-4 · an absent month carries no reading at all
def test_tc4__an_absent_month_has_reading_null(brazos, marcus):
    with tenant_ctx(brazos):
        account, _unit, meter = _water_account(marcus, brazos, "W-9004")
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 10),
            prior="10",
            current="20",
            consumption="10",
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        payload = usage_reads.usage_payload(
            account["id"], today=date(2026, 8, 1), include_reads=True
        )

    june = _point(payload, "water", "2026-06")
    assert june["absent"] is True
    assert june["reading"] is None
    assert _point(payload, "water", "2026-07")["reading"]["read_on"] == "2026-07-10"


# TC-5 · two services: each month's readings stay with their own service and unit
def test_tc5__two_services_each_carry_their_own_readings_and_unit(brazos, marcus):
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos, services=("electric", "water"))
        electric = _meter(marcus, unit["id"], asset_no="E-9005")
        water = _meter(marcus, unit["id"], asset_no="W-9005", service="water", uom="gal")
        _read(
            brazos,
            account["id"],
            electric["id"],
            day=date(2026, 7, 5),
            prior="5000",
            current="5842",
            consumption="842",
            unit="kWh",
            status="high",
        )
        _read(
            brazos,
            account["id"],
            water["id"],
            day=date(2026, 7, 9),
            prior="300000",
            current="303420",
            consumption="3420",
            unit="gal",
            source="import",
            read_method="manual",
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        payload = usage_reads.usage_payload(
            account["id"], today=date(2026, 8, 1), include_reads=True
        )

    e = _point(payload, "electric", "2026-07")["reading"]
    w = _point(payload, "water", "2026-07")["reading"]
    assert (e["read_on"], e["current_reading_display"], e["reading_unit"], e["check"]) == (
        "2026-07-05",
        "5842",
        "kWh",
        "high",
    )
    assert (w["read_on"], w["current_reading_display"], w["reading_unit"], w["check"]) == (
        "2026-07-09",
        "303420",
        "gal",
        "ok",
    )


# TC-6 · two registers in one month: no previous/current pair is invented
def test_tc6__two_meters_on_one_service_serve_no_reading_pair(brazos, marcus):
    with tenant_ctx(brazos):
        account, unit, first = _water_account(marcus, brazos, "W-9006")
        second = _meter(marcus, unit["id"], asset_no="W-9006B", service="water", uom="gal")
        _read(
            brazos,
            account["id"],
            first["id"],
            day=date(2026, 7, 3),
            prior="100",
            current="200",
            consumption="100",
        )
        _read(
            brazos,
            account["id"],
            second["id"],
            day=date(2026, 7, 20),
            prior="900000",
            current="900050",
            consumption="50",
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        payload = usage_reads.usage_payload(
            account["id"], today=date(2026, 8, 1), include_reads=True
        )

    reading = _point(payload, "water", "2026-07")["reading"]
    assert reading["previous_reading"] is None and reading["current_reading"] is None
    assert reading["reading_unit"] is None
    assert reading["readings_absent_reason"] == "several_registers"
    assert reading["read_on"] == "2026-07-20" and reading["read_count"] == 2


# TC-7 · the check vocabulary: five words plus `flagged`, worst wins
def test_tc7__check_of_maps_every_status_and_ranks_worst_first():
    assert [usage_reads.check_of(s) for s in ("high", "low", "zero", "estimated", "ok")] == [
        "high",
        "low",
        "zero",
        "estimated",
        "ok",
    ]
    for other in ("negative_usage", "rollover", "days_threshold", "stale_prior", "duplicate"):
        assert usage_reads.check_of(other) == "flagged", other
    assert usage_reads.check_of(None) == "ok" and usage_reads.check_of("") == "ok"
    # Every stored status lands in the ranked vocabulary.
    for status in metering_models.READ_STATUSES:
        assert usage_reads.check_of(status) in usage_reads.CHECK_RANK
    rank = usage_reads.CHECK_RANK
    assert rank.index("high") < rank.index("flagged") < rank.index("zero") < rank.index("ok")


# TC-8 · tenant scoping: an id from another tenant never surfaces
def test_tc8__a_foreign_tenants_read_id_never_surfaces(brazos, marcus, lonestar, erin):
    with tenant_ctx(lonestar):
        foreign_account, _u, foreign_meter = _water_account(
            erin, lonestar, "W-LS-1", water_only_tenant=True
        )
        foreign = _read(
            lonestar,
            foreign_account["id"],
            foreign_meter["id"],
            day=date(2026, 7, 30),
            prior="7777700",
            current="7777777",
            consumption="77",
            status="high",
        )

    with tenant_ctx(brazos):
        account, _unit, meter = _water_account(marcus, brazos, "W-9008")
        own = _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 2),
            prior="10",
            current="30",
            consumption="20",
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        head = metering_models.MonthlyUsage.objects.get(
            account_id=account["id"], superseded_by_id__isnull=True
        )
        # A stored id list is data. Plant the foreign id beside our own and the
        # read detail must still show only this tenant's reading.
        blob = {str(own.id), str(foreign.id)}
        metering_models.MonthlyUsage.objects.filter(pk=head.pk).update(source_read_ids=sorted(blob))
        payload = usage_reads.usage_payload(
            account["id"], today=date(2026, 8, 1), include_reads=True
        )

    reading = _point(payload, "water", "2026-07")["reading"]
    assert reading["read_count"] == 1
    assert reading["read_on"] == "2026-07-02"
    assert reading["current_reading_display"] == "30"
    assert reading["check"] == "ok", "the foreign HIGH read must not set this month's check"

    with tenant_ctx(lonestar):
        # …and the intruder asking for the account gets nothing at all.
        assert usage_reads.usage_payload(account["id"], include_reads=True)["series"] == []


# TC-9 · one query for all reads, however many months
def test_tc9__the_read_detail_is_one_query_however_many_months(brazos, marcus):
    def count_for(months_with_reads, asset_no):
        with tenant_ctx(brazos):
            account, _unit, meter = _water_account(marcus, brazos, asset_no)
            for month in range(1, months_with_reads + 1):
                _read(
                    brazos,
                    account["id"],
                    meter["id"],
                    day=date(2026, month, 15),
                    prior=str(month * 100),
                    current=str(month * 100 + 50),
                    consumption="50",
                )
            usage_service.recompute_account(account["id"], actor=marcus)
            with CaptureQueriesContext(connection) as plain:
                usage_reads.usage_payload(account["id"], today=date(2026, 9, 1))
            with CaptureQueriesContext(connection) as detailed:
                payload = usage_reads.usage_payload(
                    account["id"], today=date(2026, 9, 1), include_reads=True
                )
            present = [p for s in payload["series"] for p in s["points"] if not p["absent"]]
            assert len(present) == months_with_reads
            assert all(p["reading"] is not None for p in present)
            return len(detailed.captured_queries) - len(plain.captured_queries)

    assert count_for(1, "W-9009A") == 1
    assert count_for(8, "W-9009B") == 1, "the read detail must not grow with the months"


# TC-10 · the endpoint asks for the detail; the plain payload does not carry it
def test_tc10__the_endpoint_serves_readings_and_the_seam_payload_does_not(brazos, marcus):
    with tenant_ctx(brazos):
        account, _unit, meter = _water_account(marcus, brazos, "W-9010")
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 14),
            prior="50",
            current="80",
            consumption="30",
            status="zero",
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        plain = usage_reads.usage_payload(account["id"], today=date(2026, 8, 1))
        assert "reading" not in plain["series"][0]["points"][-1]

    served = api_call(
        metering_api.account_usage,
        "get",
        user=FakeUser(),
        tenant=brazos,
        role="billing_clerk",
        account_id=account["id"],
        query={"months": "12"},
    )
    assert served.status_code == 200
    points = served.data["series"][0]["points"]
    july = next(p for p in points if p["month"] == "2026-07")
    assert july["reading"]["check"] == "zero"
    assert july["reading"]["read_on"] == "2026-07-14"
    assert all(p["reading"] is None for p in points if p["absent"])
