# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9754 — a move-in payment is dated a day early: the clerk
#           types 10/10/2026 on Pay now and the move's Billing tab shows
#           10/09/2026 on a utility on America/Chicago.
# Rule:     OQ-153 (CLOSED, PO 2026-08-12): a typed date is midnight in the
#           UTILITY'S OWN timezone. Same fault as DEF-MET-9213 (New Connection).
# CR:       CR-171-BRC10 P4.02, M1 (MVI-26-0008, check 2041)
# ───────────────────────────────────────────────────────
"""The day the clerk typed is the day the utility sees, on both move-in writers.

`move_fees._instant` (Pay now) and `deposit._as_datetime` (the deposit step)
each anchored the typed day at midnight UTC — 19:00 the evening before in
Chicago — and every screen reads the instant back in the utility's zone.
"""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pytest

from apps.customers import deposit, move_fees
from apps.payments import models as payment_models
from apps.tenancy import models as tenancy_models
from tests.test_cr171_p1_12_move_in_fees import _move_in, _pay_now, _world
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CHICAGO = ZoneInfo("America/Chicago")


def _on_chicago(tenant):
    with tenant_ctx(tenant):
        tenancy_models.TenantSettings.objects.update_or_create(
            tenant_id=tenant.id, defaults={"timezone": "America/Chicago"}
        )


def test_both_helpers_anchor_the_typed_day_in_the_utility_zone(brazos):
    _on_chicago(brazos)
    with tenant_ctx(brazos):
        for moment in (move_fees._instant(date(2026, 10, 10)), deposit._as_datetime(date(2026, 10, 10))):
            assert moment.astimezone(CHICAGO).date() == date(2026, 10, 10), moment


def test_a_pay_now_check_keeps_the_typed_day(brazos, dana):
    _on_chicago(brazos)
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, payment=_pay_now("175.00", received_on="2026-08-15"))
        rows = list(payment_models.Payment.objects.filter(account_id=result["id"]))
    assert rows, "the fixture recorded no payment — the test would be vacuous"
    assert {row.posted_at.astimezone(CHICAGO).date() for row in rows} == {date(2026, 8, 15)}


def test_a_utility_on_utc_is_unchanged(brazos):
    with tenant_ctx(brazos):
        tenancy_models.TenantSettings.objects.filter(tenant_id=brazos.id).update(timezone="UTC")
        moment = move_fees._instant(date(2026, 10, 10))
    assert moment.utcoffset().total_seconds() == 0
    assert moment.date() == date(2026, 10, 10)
