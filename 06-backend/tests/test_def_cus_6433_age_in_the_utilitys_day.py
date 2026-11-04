# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6433 — the AGE column on REQ-01 counted in the SERVER's day
#           while the request was dated in the utility's, so for five hours of
#           every evening every row read one day older than it is.
# Rules:    BR-TEN-043 (the utility's own clock decides what day it is) ·
#           BR-TEN-081 (one derivation of that clock) · BR-CUS-106 (the age
#           accent is seven days, inclusive)
# Tests:    this file
# Impacts:  06-backend/apps/customers/service_request_reads.py (`list_row`) ·
#           06-backend/apps/customers/seams.py (`tenant_timezone`)
# ───────────────────────────────────────────────────────
"""**THE CLOCK IS FROZEN, BECAUSE THE DEFECT ONLY EXISTS AT CERTAIN HOURS.**

`DEF-CUS-6433` was filed against three cases that are red between midnight UTC
and the utility's own midnight and green for the other nineteen hours of the
day — which is why every lane that ran them in daylight saw them pass, and why
the escape reason for this defect is *"every lane ran these tests in
daytime"*. A case that reads the real clock would inherit exactly that, so this
one pins `timezone.now()` at **01:00 UTC**, inside the window, and never leaves
it.

**Brazos Bend is in `America/Chicago`** (`US_STATE_TIMEZONES["TX"]`, prefilled
at provisioning from the signup state), so 01:00 UTC on 24 September is **20:00
on 23 September** at the counter. Every figure below is that one difference.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (hard-won law 7): asserting only the
number of days. A `list_row` that had stopped converting *either* half would
still produce a plausible integer — it is the SEVEN-DAY ACCENT that a clerk
acts on, so the second case pins the boundary at the exact instant where the
two clocks disagree about whether `BR-CUS-106` has been crossed.
"""

from datetime import UTC, datetime

import pytest
from django.utils import timezone

from apps.customers import models as customers_models
from apps.customers import service_request_reads as reads

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · sqlite_guc
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

#: 01:00 UTC = 20:00 the PREVIOUS DAY in Brazos Bend.
NOW_UTC = datetime(2026, 9, 24, 1, 0, tzinfo=UTC)


@pytest.fixture()
def frozen_evening(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW_UTC)
    return NOW_UTC


def _request(received_at):
    """An unsaved row — `list_row` reads attributes and writes nothing."""
    return customers_models.ServiceRequest(
        request_no="SR-26-0001",
        applicant_name="Alvarez, M.",
        address_as_given="14 Cedar St",
        received_at=received_at,
    )


def test_the_age_is_counted_in_the_utilitys_own_day(brazos, dana, frozen_evening):
    """**RED BEFORE THE FIX:** `assert 2 == 1` — the server's day was
    24 September while the counter's was the 23rd.

    Filed 22 September at 09:30 UTC, which is 04:30 on the 22nd in Brazos Bend.
    At 20:00 on the 23rd that request is **one day old**, and it read two.
    """
    with tenant_ctx(brazos):
        row = reads.list_row(_request(datetime(2026, 9, 22, 9, 30, tzinfo=UTC)))
        assert row["age_days"] == 1


def test_the_seven_day_accent_does_not_come_a_day_early(brazos, dana, frozen_evening):
    """`BR-CUS-106` — seven days, inclusive — **at the one instant where the two
    clocks disagree about whether it has been reached.**

    Filed 17 September at 09:30 UTC. On the utility's clock that is six days
    ago, so the row is NOT accented; on the server's it is seven, and it was.
    A request six days old was being flagged as a week old from 19:00 every
    evening, on the one screen a clerk decides their morning from.
    """
    with tenant_ctx(brazos):
        row = reads.list_row(_request(datetime(2026, 9, 17, 9, 30, tzinfo=UTC)))
        assert row["age_days"] == 6
        assert row["age_is_accented"] is False


def test_a_request_with_no_received_at_has_no_age_and_is_not_accented(brazos, dana, frozen_evening):
    """The absence, kept: no `received_at` means NO age, which is not the same
    fact as *not old* and must not collapse into it — `list_row`'s own comment.
    Asserted because the conversion added two attribute reads that would each
    raise on `None`."""
    with tenant_ctx(brazos):
        row = reads.list_row(_request(None))
        assert row["age_days"] is None
        assert row["age_is_accented"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-6433 (12-governance/10-defect-log.csv) · BR-TEN-043 · BR-TEN-081 · BR-CUS-106
# generated: 2026-09-24 by lane SMALL-CUS
# gates: pytest tests/test_def_cus_6433_age_in_the_utilitys_day.py
