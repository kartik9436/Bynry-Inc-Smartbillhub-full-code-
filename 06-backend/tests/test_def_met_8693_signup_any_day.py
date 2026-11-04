# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-8693 — a utility signing up on the 1st to the 4th of a
#           month got a SHORT sample set: the sample cycle's start day was
#           `read day − 4`, the open period's read day is clamped to today, so
#           on 1 October it was −3, `create_cycle` refused it
#           (`metering.cycle.day_of_month_range`) and premises, meters,
#           accounts, reads and payments all failed behind it.
# Rules:    BR-MET-077 (a cycle is a day-of-month definition; bill day ≥ the
#           window's close) · BR-TEN-056/063 (the sample set; its failure never
#           fails provisioning — which is how this hid)
# Impacts:  apps/metering/sample_data.py (`sample_walk_days`) ·
#           core/sample_fixture.py (`route_read_on`: the open month's walk
#           never starts before the month; the water version dates travel —
#           DEF-RAT-8757) · apps/billing/sample_data.py (DEF-BIL-8755) ·
#           apps/payments/sample_data.py (DEF-PAY-8756)
# ───────────────────────────────────────────────────────
"""Every sign-up day of the month gets the whole sample set.

THE CLOCK IS THE FIXTURE'S OWN: `SBH_FIXTURE_TODAY` is the one declared day
the sample plant reads (BR-TEN-043, `core.sample_fixture.fixture_today`), so
"signing up on 1 October" is that variable set and the fixture module
reloaded — the same thing a real process started on that day sees.

RED with the old start day restored (`close − 4`, SQLite, 2026-10-01):

    AssertionError: signed up 2026-10-01: 16 seeding blocks failed:
    ['metering/seed_sample_records: ValidationError: VAL-003
    (metering.cycle.day_of_month_range)', 'metering/seed_sample_reads: …']

THREE MORE CAUSES OF A SHORT SET WERE BEHIND IT, each found by this file and
each filed before it was fixed: `DEF-BIL-8755` (signed up on the 1st, the
second cycle issued 5 of 49 bills — the busy day's payments sat in the *Paid
after cut-off* window), `DEF-PAY-8756` (the 1st to the 8th: the second-cycle
collections fell on the busy day's sealed till — 48 payments where mid-month
lands 83) and `DEF-RAT-8757` (from November 2026: the water schedule's typed
version dates did not travel — 4 accounts, 0 bills on 28 February 2027).

ON POSTGRESQL 16 (law 14), 2026-10-01: 1 and 4 October 2026 and 28 February
2026 land whole. **28 February 2027 lands one block short there and not on
SQLite** — the open month's reads (`seed_sample_next_cycle_reads`, 0 of 47 on
file) — and 28 February 2026 does not, so it is the DATABASE's own clock (real
today, 1 October 2026) meeting readings dated five months after it. A utility
really signing up on that day has a clock that agrees with its fixture. The
future dates stay in this list because the SQLite suite is where this runs.
"""

from __future__ import annotations

import importlib
import os
from datetime import date, timedelta

import pytest

from apps.assets import models as assets_models
from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.metering import models as metering_models
from apps.metering import sample_data as metering_sample
from apps.payments import models as payments_models
from apps.rating import sample_data as rating_sample
from apps.tenancy import models as tenancy_models
from core import sample_fixture as fixture
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

#: The days the defect named, both ends of a month, and the two Februaries.
SIGNUP_DAYS = (
    date(2026, 10, 1),
    date(2026, 10, 4),
    date(2026, 10, 9),
    date(2026, 10, 15),
    date(2026, 10, 31),
    # DEF-RAT-8757 — the first month the typed water-version dates broke.
    date(2026, 11, 2),
    date(2026, 2, 28),
    date(2027, 2, 28),
    date(2028, 2, 29),
)


def _on(day: date, monkeypatch) -> None:
    """Make `day` the fixture's today, as a process started on it would."""
    monkeypatch.setenv(fixture.FIXTURE_TODAY_ENV, day.isoformat())
    importlib.reload(fixture)
    monkeypatch.setattr(
        rating_sample, "PLAN_EFFECTIVE_FROM", fixture.PERIODS[0]["start"].isoformat()
    )


@pytest.fixture
def restore_calendar():
    """Put the settings pin (`config/settings/test.py`) back and reload, so
    every later test sees the anchor day. It restores the variable ITSELF
    rather than relying on monkeypatch: pytest tears this fixture down BEFORE
    monkeypatch, so a reload here would otherwise re-read the simulated day."""
    pinned = os.environ.get(fixture.FIXTURE_TODAY_ENV)
    yield
    if pinned is None:
        os.environ.pop(fixture.FIXTURE_TODAY_ENV, None)
    else:
        os.environ[fixture.FIXTURE_TODAY_ENV] = pinned
    importlib.reload(fixture)
    assert fixture.CALENDAR_OFFSET_MONTHS == 0 or pinned != "2026-08-14"


# ── Pure: every day of every month ──────────────────────────────────────────


@pytest.mark.parametrize("close_day", range(1, 15))
def test_the_cycle_definition_is_valid_for_every_close_day(close_day):
    start_day, days = metering_sample.sample_walk_days(close_day)
    assert 1 <= start_day <= close_day
    assert days >= 1
    assert start_day + days - 1 == close_day, "the window still closes on the read day"
    if close_day >= fixture.WALK_DAYS_TO_COMPLETE:
        assert (start_day, days) == (close_day - 4, 5), "mid-month is unchanged"


def test_the_anchor_cycle_is_unchanged():
    assert metering_sample.sample_walk_days(14) == (10, 5)


def test_the_open_month_is_never_walked_before_it_starts(monkeypatch, restore_calendar):
    day = date(2026, 10, 1)
    while day <= date(2026, 10, 31):
        _on(day, monkeypatch)
        open_period = fixture.PERIODS[-1]
        assert not open_period["billed"]
        for route in fixture.READ_ROUTES:
            walked = fixture.route_read_on(open_period["key"], route["walk_offset"])
            assert open_period["start"] <= walked <= day, (day, route["name"], walked)
        day += timedelta(days=1)


# ── Through the real sign-up ────────────────────────────────────────────────


def _counts(tenant) -> dict[str, int]:
    with tenant_ctx(tenant):
        failed = [
            f"{row.module}/{block.get('block')}: {block.get('detail')}"
            for row in tenancy_models.SampleDataRun.objects.filter(tenant_id=tenant.id)
            for block in (row.blocks or [])
            if block.get("outcome") != "seeded"
        ]
        tid = tenant.id
        return {
            "failed_blocks": failed,
            "cycles": metering_models.Cycle.objects.filter(tenant_id=tid).count(),
            "premises": metering_models.Premises.objects.filter(tenant_id=tid).count(),
            "units": metering_models.Unit.objects.filter(tenant_id=tid).count(),
            "meters": assets_models.Asset.objects.filter(tenant_id=tid).count(),
            "accounts": customers_models.Account.objects.filter(tenant_id=tid).count(),
            "reads": metering_models.MeterRead.objects.filter(tenant_id=tid).count(),
            "payments": payments_models.Payment.objects.filter(tenant_id=tid).count(),
            "issued_bills": billing_models.Invoice.objects.filter(
                tenant_id=tid, status="issued"
            ).count(),
        }


def _sign_up(day: date, monkeypatch) -> dict:
    _on(day, monkeypatch)
    subdomain = f"day-{day.isoformat().replace('-', '')}"
    tenant, result = provisioned_tenant(
        brazosbend_payload(
            subdomain=subdomain,
            name=f"Signed up {day.isoformat()}",
            services=["water"],
            owner={
                "full_name": "Dana Whitfield",
                "email": f"dana@{subdomain}.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    assert result["created"] is True
    return _counts(tenant)


#: What a mid-month sign-up lands (measured on 15 October 2026, water only),
#: and what every other sign-up day must land too.
MID_MONTH: dict[str, int] = {
    "cycles": 1,
    "premises": 73,
    "units": 121,
    "meters": 74,
    "accounts": 75,
    "reads": 202,
    "payments": 83,
    "issued_bills": 99,
}


@pytest.mark.django_db
@pytest.mark.parametrize("day", SIGNUP_DAYS, ids=lambda d: d.isoformat())
def test_every_signup_day_gets_the_whole_sample_set(
    day, growth_plan, audit_rows, settings, monkeypatch, restore_calendar
):
    """One tenant per sign-up day through the real sign-up, every seeding
    block landed, and the same counts as the mid-month sign-up."""
    settings.JOBS_EAGER = True  # the plant runs inline, as on a real sign-up
    counts = _sign_up(day, monkeypatch)
    failed = counts.pop("failed_blocks")
    print(f"DEF-MET-8693 signed up {day}: {counts}")
    assert not failed, f"signed up {day}: {len(failed)} seeding blocks failed: {failed[:3]}"
    assert counts == MID_MONTH, f"signed up {day}: {counts} vs mid-month {MID_MONTH}"
