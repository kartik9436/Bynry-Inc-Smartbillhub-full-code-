# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9642 — a field job closed on a day its meter already has a
#           reading could never be accepted (the duplicate rule on asset,
#           read_at, channel refused it and Accept offered no way out).
# Ruling:   PO 2026-10-04, verbatim: *"take the reading records in register and
#           use date and highest consumption reading if it is apprved and
#           validated"* — decision log, "TWO READINGS ON ONE REGISTER ON ONE
#           DAY: BOTH ARE KEPT, AND THE ONE THAT COUNTS IS THE HIGHEST OF THOSE
#           THAT ARE APPROVED AND VALIDATED".
# Rules:    BR-MET-1189 (new) · BR-MET-016 / BR-MET-052 (SUPERSEDED for the
#           same-day pair) · BR-MET-053 · BR-MET-129 · BR-MET-110
# Module:   apps/metering/counted_reading.py (🔒 HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
"""The worked case the PO was shown, end to end.

Meter E-5000 holds an office reading of **3,400 kWh** on 4 October. The
technician's move-in job posts **3,412 kWh** the same day. Both are kept; with
both approved and validated, **3,412 counts**; a higher reading that is not
approved or not validated never counts.

RED FIRST (quoted from the run before the fix, SQLite and PostgreSQL alike):

    test_the_same_day_second_reading_is_stored_not_refused
        core.errors.BizError: metering.event_reads.errors_refuse
    test_work_accept_succeeds_on_a_meter_read_earlier_that_day
        core.errors.BizError: metering.event_reads.errors_refuse
    test_the_highest_approved_and_validated_reading_counts
        IntegrityError: duplicate key value violates unique constraint
        "meter_reads_..._uq_meter_reads_head" (PostgreSQL) /
        UNIQUE constraint failed (SQLite)
"""

from decimal import Decimal

import pytest

from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import counted_reading
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services

from tests import identity_fixtures
from tests.test_us_met_helpers import field_close
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    make_premises,
    make_unit,
    seed_config,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

OFFICE = Decimal("3400")
TECHNICIAN = Decimal("3412")
DAY = "2026-10-04"


def _plan(tenant, service_code="electric"):
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="Same day", defaults={"code": "same-day", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"Same day — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _e5000(admin, tenant, asset_no="E-5000", service="electric", uom="kWh"):
    """E-5000 on a unit with an account, read 3,300 kWh on 4 September."""
    premises = make_premises(admin, services_available=[service])
    unit = make_unit(admin, premises["id"], label="Unit A", services=[service])
    metering_services.assign_unit_plan(
        admin, unit["id"], {"tariff_id": str(_plan(tenant, service).id)}
    )
    a_meter(admin, asset_no, unit_id=unit["id"], service=service, uom=uom)
    customers_services.create_account(
        admin,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": "Okafor, Ruth"},
            "customer": identity_fixtures.customer_block(
                "Okafor, Ruth", account_type="residential"
            ),
        },
    )
    from apps.metering import seams as metering_seams

    asset_id = next(
        row["id"]
        for row in metering_seams.assets_on_unit(unit["id"])
        if row["asset_no"] == asset_no
    )
    commit_read(admin, asset_id, day="2026-09-04", value="3300", consumption="100", unit=uom)
    return unit, asset_id


def _post(actor, value, *, event="move_in", asset_no="E-5000"):
    return metering_services.commit_event_reads(
        actor,
        {"event": event, "reads": [{"meter_no": asset_no, "read_at": DAY, "value": str(value)}]},
    )


def _day_heads(asset_id):
    return list(
        metering_models.MeterRead.objects.filter(
            asset_id=asset_id,
            read_at=at(DAY),
            superseded_by_id__isnull=True,
        )
    )


def _billing_row(unit):
    rows = metering_selectors.billing_reads_for_unit(
        unit["id"], period_start="2026-09-05", period_end="2026-10-04"
    )
    return next(row for row in rows if row["service_code"] == "electric")


# ════════════════════════════════════════════════════════════════════════════
def test_the_same_day_second_reading_is_stored_not_refused(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        _unit, asset_id = _e5000(dana, brazos)
        _post(dana, OFFICE, event="move_in")
        answer = _post(dana, TECHNICIAN, event="move_in")
        heads = metering_models.MeterRead.objects.filter(
            asset_id=asset_id, superseded_by_id__isnull=True, current_value__in=[OFFICE, TECHNICIAN]
        )
        values = sorted(read.current_value for read in heads)

    assert answer["posted_reads"] == 1
    assert values == [OFFICE, TECHNICIAN], "both readings are kept; neither replaced the other"


def test_the_highest_approved_and_validated_reading_counts(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit, asset_id = _e5000(dana, brazos)
        _post(dana, OFFICE)
        _post(dana, TECHNICIAN)
        reads = metering_models.MeterRead.objects.filter(
            asset_id=asset_id, superseded_by_id__isnull=True, current_value__in=[OFFICE, TECHNICIAN]
        )
        winner = counted_reading.counted_among(reads)
        in_sql = list(
            counted_reading.only_counted(
                metering_models.MeterRead.objects.filter(asset_id=asset_id)
            ).values_list("current_value", flat=True)
        )

    assert winner.current_value == TECHNICIAN
    assert TECHNICIAN in in_sql and OFFICE not in in_sql, in_sql


def test_billing_uses_the_counted_reading(brazos, dana):
    """3,412 − 3,300 = 112 kWh billed, never the office's 100 kWh."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _asset_id = _e5000(dana, brazos)
        _post(dana, OFFICE)
        _post(dana, TECHNICIAN)
        row = _billing_row(unit)

    assert row["consumption"] == Decimal("112.000000"), row


def test_the_order_of_arrival_does_not_decide_it(brazos, dana):
    """The technician's 3,412 posted FIRST and the office's 3,400 second: the
    newest row is NOT the answer, the highest approved and validated one is."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _asset_id = _e5000(dana, brazos)
        _post(dana, TECHNICIAN)
        _post(dana, OFFICE)
        row = _billing_row(unit)

    assert row["consumption"] == Decimal("112.000000"), row


@pytest.mark.parametrize(
    "spoil",
    [
        pytest.param({"status": "mismatch"}, id="not_validated"),
        pytest.param({"disputed_at": "now"}, id="not_approved_disputed"),
    ],
)
def test_a_higher_reading_that_is_not_approved_or_validated_never_counts(brazos, dana, spoil):
    from django.utils import timezone

    with tenant_ctx(brazos):
        seed_config()
        unit, asset_id = _e5000(dana, brazos)
        _post(dana, OFFICE)
        _post(dana, TECHNICIAN)
        fields = {k: (timezone.now() if v == "now" else v) for k, v in spoil.items()}
        metering_models.MeterRead.objects.filter(
            asset_id=asset_id, current_value=TECHNICIAN
        ).update(**fields)
        row = _billing_row(unit)
        flags = counted_reading.counted_flags(_day_heads(asset_id))
        by_value = {read.current_value: flags[str(read.id)] for read in _day_heads(asset_id)}

    assert row["consumption"] == Decimal("100.000000"), "the office's 3,400 counts"
    assert by_value == {OFFICE: True, TECHNICIAN: False}


def test_the_next_reading_is_measured_from_the_counted_one(brazos, dana):
    """5 November reads 3,500: measured from 3,412 (88 kWh), never from 3,400."""
    with tenant_ctx(brazos):
        seed_config()
        _unit, asset_id = _e5000(dana, brazos)
        _post(dana, OFFICE)
        _post(dana, TECHNICIAN)
        metering_services.commit_event_reads(
            dana,
            {
                "event": "move_out",
                "reads": [{"meter_no": "E-5000", "read_at": "2026-11-05", "value": "3500"}],
            },
        )
        november = metering_models.MeterRead.objects.get(
            asset_id=asset_id, current_value=Decimal("3500")
        )

    assert november.prior_value == TECHNICIAN
    assert november.consumption == Decimal("88.000000")


def test_the_meters_reading_list_marks_the_one_that_counts(brazos, dana):
    from apps.assets import selectors as assets_selectors

    with tenant_ctx(brazos):
        seed_config()
        _unit, asset_id = _e5000(dana, brazos)
        _post(dana, OFFICE)
        _post(dana, TECHNICIAN)
        rows = assets_selectors.asset_reads(asset_id)

    on_day = {row["reading"]: row["counts"] for row in rows if row["date"] == DAY}
    assert on_day == {"3400.000000": False, "3412.000000": True}, on_day
    alone = [row for row in rows if row["date"] == "2026-09-04"]
    assert alone and alone[0]["counts"] is None, "a reading alone on its date draws nothing"


def test_work_accept_succeeds_on_a_meter_read_earlier_that_day(brazos, dana):
    """WO-0043's shape: the office read 3,400 that morning, the field job's
    reading is 3,412 on the same day, and Accept posts it rather than failing
    forever. The accepted reading is the one that counts."""
    with tenant_ctx(brazos):
        seed_config()
        premises = make_premises(dana, services_available=["electric"])
        unit = make_unit(dana, premises["id"], services=["electric"])
        metering_services.assign_unit_plan(dana, unit["id"], {"tariff_id": str(_plan(brazos).id)})
        a_meter(dana, "E-5000", unit_id=unit["id"], service="electric", uom="kWh")
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        w6.add_connection_service(dana, created["id"], service_code="electric", unit_id=unit["id"])
        w6.submit_connection(dana, created["id"])
        order_id = w6.create_work_order(
            dana, created["id"], {"type": "meter set", "service": "electric"}
        )["id"]
        _post(dana, OFFICE, event="move_in")
        field_close(
            dana,
            order_id,
            field_data={
                "meter_serial": "E-5000",
                "set_reads": [{"meter_no": "E-5000", "value": str(TECHNICIAN), "read_at": DAY}],
            },
            outcome=work_tables.OUTCOME_PASSED,
        )

        accepted = w6.accept_field_result(dana, order_id)
        from apps.metering import seams as metering_seams

        asset_id = next(
            row["id"]
            for row in metering_seams.assets_on_unit(unit["id"])
            if row["asset_no"] == "E-5000"
        )
        winner = counted_reading.counted_among(_day_heads(asset_id))

    assert accepted["event_reads"]["posted_reads"] == 1
    assert winner.current_value == TECHNICIAN


def test_tenant_isolation__another_utility_never_decides_which_reading_counts(
    brazos, dana, lonestar, erin
):
    """Lone Star holds a HIGHER approved reading for its own E-5000 on the
    same date. Brazos Bend's counted reading is still its own 3,412 — the
    counted query is tenant-scoped on both sides of the subquery."""
    with tenant_ctx(lonestar):
        seed_config()
        # Lone Star sells water: its own meter, same number, same date.
        _e5000(erin, lonestar, service="water", uom="kgal")
        _post(erin, Decimal("9999"))
    with tenant_ctx(brazos):
        seed_config()
        unit, asset_id = _e5000(dana, brazos)
        _post(dana, OFFICE)
        _post(dana, TECHNICIAN)
        seen = list(
            counted_reading.only_counted(
                metering_selectors._read_heads().filter(read_at__gte="2026-10-04")
            ).values_list("tenant_id", "current_value")
        )
        row = _billing_row(unit)

    assert seen == [(brazos.id, TECHNICIAN)], seen
    assert row["consumption"] == Decimal("112.000000")


def test_the_same_value_again_is_already_recorded_not_refused_and_not_doubled(brazos, dana):
    """The technician reads exactly what the office read, 3,400. It is the same
    reading, not a second one: the door answers `already_recorded`, nothing is
    refused (Accept must not fail) and no second identical row is written."""
    with tenant_ctx(brazos):
        seed_config()
        _unit, asset_id = _e5000(dana, brazos)
        first = _post(dana, OFFICE)
        again = _post(dana, OFFICE, event="new_connect")
        rows = len(_day_heads(asset_id))

    assert again["posted_reads"] == 0
    assert again["already_recorded"][0]["existing_read_id"] == first["posted"][0]["id"]
    assert rows == 1
