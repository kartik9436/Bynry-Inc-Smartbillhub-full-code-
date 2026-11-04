# ── Trace ──────────────────────────────────────────────
# Change:   CR-183-BRC10 T5 — a bill for a period partly on a temporary stop.
# Rules:    BR-CUS-1120 (B1: base charge only during the hold, by the day) ·
#           BR-CUS-055 · B4.3 (base prorated by service days — unchanged)
# ───────────────────────────────────────────────────────
"""Real rows, real stages: June, 412 kWh read on 28 Jun, $0.12/kWh, base $18.50.

    no hold                         18.50 + 49.44 = 67.94
    hold 21 Jun → still on (run)    18.50 + 49.44 = 67.94   (was 18.50 — the
                                                              412 kWh billed by
                                                              nobody)
    hold the WHOLE of June           18.50                    (base only)

The base is the same $18.50 in every row: B1 bills the base on hold days too,
so a hold never shortens `service_days`. What a hold removes is usage on the
hold days — and the meter recorded none, because nobody was home.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import runs
from apps.customers.temporary_stop_models import TemporaryStop
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _bill(brazos, dana, *, status, hold, asset_no, account_no):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=asset_no, label="Unit A")
        account = an_account(brazos, unit["id"], account_no, status_code=status)
        if hold is not None:
            stop_from, restart_on, hold_status = hold
            TemporaryStop.objects.create(
                tenant=brazos,
                account=account,
                channel="staff",
                status=hold_status,
                stop_from=stop_from,
                restart_on=restart_on,
            )
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        data = prepared.ready[0]
        invoice = runs.calculate_account(data, service_date=SERVICE_DATE)
        return data, invoice


def test_a_period_partly_on_hold_bills_its_base_and_the_usage_of_its_active_days(brazos, dana):
    data, invoice = _bill(
        brazos,
        dana,
        status="vacation_hold",
        hold=(date(2026, 6, 21), date(2026, 7, 10), "on_hold"),
        asset_no="M-8301",
        account_no="A-18301",
    )
    assert data.behavior_class == "billable"
    assert invoice.total == Decimal("67.940000")


def test_a_period_wholly_on_hold_bills_the_base_charge_only(brazos, dana):
    data, invoice = _bill(
        brazos,
        dana,
        status="vacation_hold",
        hold=(date(2026, 5, 25), date(2026, 7, 5), "on_hold"),
        asset_no="M-8302",
        account_no="A-18302",
    )
    assert data.behavior_class == "billable_base_only"
    assert invoice.total == Decimal("18.500000")


def test_a_hold_that_ended_inside_the_period_bills_as_active(brazos, dana):
    data, invoice = _bill(
        brazos,
        dana,
        status="active",
        hold=(date(2026, 5, 20), date(2026, 6, 11), "ended"),
        asset_no="M-8303",
        account_no="A-18303",
    )
    assert data.behavior_class == "billable"
    assert invoice.total == Decimal("67.940000")


def test_a_hand_set_vacation_hold_without_a_stop_row_is_unchanged(brazos, dana):
    data, invoice = _bill(
        brazos, dana, status="vacation_hold", hold=None, asset_no="M-8304", account_no="A-18304"
    )
    assert data.behavior_class == "billable_base_only"
    assert invoice.total == Decimal("18.500000")
