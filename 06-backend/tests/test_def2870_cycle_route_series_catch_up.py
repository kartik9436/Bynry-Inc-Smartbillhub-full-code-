# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2870 — on a FRESH database, `manage.py seed_demo` followed by
#           `manage.py load_sample_data --tenant brazosbend` refuses metering's
#           premises block with `VAL-002 (metering.cycle.code_duplicate)`, ten
#           further blocks fall behind it, and the tenant ends with 0 accounts
#           and 0 customers. Filed UNDIAGNOSED on 2026-09-01; diagnosed and
#           fixed the same day.
# Rules:    BR-TEN-035 (a number is NEVER reused; gaps are fine; next-number
#           moves are FORWARD-ONLY) · BR-MET-073 (route numbering) ·
#           BR-MET-077 (cycle numbering) · BR-TEN-063 (the sample load is
#           idempotent and atomic per module)
# Tests:    this file. Its elder sibling is
#           tests/test_def577_series_catch_up.py — SAME invariant, two tables
#           further on.
# ───────────────────────────────────────────────────────
"""THE INVARIANT, ONE TABLE OVER: a series must never hand out a number that
already exists.

DEF-577 established it for `premises` and `unit` and built
`services._allocate_unused_number` to hold it. **`create_cycle` and
`create_route` were never moved onto that helper**, so they kept the original
bug — and `seed_demo` is the path that walks straight into it: it writes
`CY-001`..`CY-006` and `RT-001`..`RT-006` with EXPLICIT codes, and a
caller-supplied code consumes nothing from the series.

MEASURED ON A FRESH POSTGRESQL 16 DATABASE, 2026-09-01, after `seed_demo`::

     series  |  format   | next_number
    ---------+-----------+-------------
     cycle   | CY-{000}  |           1
     route   | RT-{000}  |           1

with six cycles and six routes on file. The next `create_cycle` with no code
therefore asked for `CY-001`, which exists.

PROVED RED FIRST (hard-won law 7). Against the code as it stood at
`c4261fc0`, both reproduction cases below reported::

    E   core.errors.ValidationError: VAL-002 (metering.cycle.code_duplicate)
    E   core.errors.ValidationError: VAL-002 (metering.route.code_duplicate)

which is exactly the sentence `manage.py load_sample_data` printed:

    NOT  Premises, units & service points   0 row(s)  [SD-REFUSED]
"""

import pytest

from apps.metering import models, services
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

CYCLE_FORMAT = "CY-{000}"
ROUTE_FORMAT = "RT-{000}"


def _series(tenant, series):
    return tenancy_models.NumberSeries.objects.get(tenant=tenant, series=series)


def _open_series_at(tenant, series, fmt, position):
    """Put a counter at a known place, creating the row when provisioning has
    not seeded one — which is what `seed_demo` leaves behind: a row standing at
    1 with six codes already written past it."""
    tenancy_models.NumberSeries.objects.update_or_create(
        tenant=tenant,
        series=series,
        defaults={"format": fmt, "next_number": position},
    )
    return position


def _cycle_payload(**overrides):
    payload = {
        "name": "Residential monthly",
        "frequency": "Monthly",
        "start_day": 1,
        "days_to_complete": 3,
        "bill_day": 5,
        "due_days": 20,
        "first_run_date": "2026-09-01",
    }
    payload.update(overrides)
    return payload


# ═══════════════════════════════════════════════════════════════════════════
# THE REPRODUCTION — cycles
# ═══════════════════════════════════════════════════════════════════════════


def test_a_cycle_with_no_code_does_not_collide_with_seed_demos_own_codes(brazos, dana):
    """DEF-2870 in its shipped shape: `seed_demo` names its own cycle codes, so
    the series never advances past them, and the sample plant — which sends NO
    code — is handed the first one back."""
    with tenant_ctx(brazos):
        _open_series_at(brazos, "cycle", CYCLE_FORMAT, 1)
        for n in range(1, 7):
            services.create_cycle(dana, _cycle_payload(code=f"CY-{n:03d}", name=f"Cycle {n}"))
        assert (
            _series(brazos, "cycle").next_number == 1
        ), "a caller-supplied code must not consume one from the series"

        result = services.create_cycle(dana, _cycle_payload(name="Silver Creek — monthly"))

        assert result["code"] == "CY-007"
        assert models.Cycle.objects.filter(code="CY-007").count() == 1
        # forward-only, and past everything that exists (BR-TEN-035)
        assert _series(brazos, "cycle").next_number == 8


def test_the_cycle_catch_up_clears_the_whole_block_in_one_move(brazos, dana):
    """One forward move, not one per collision — the same guarantee DEF-577
    bought for units."""
    with tenant_ctx(brazos):
        _open_series_at(brazos, "cycle", CYCLE_FORMAT, 1)
        for n in range(1, 21):
            services.create_cycle(dana, _cycle_payload(code=f"CY-{n:03d}", name=f"Cycle {n}"))

        result = services.create_cycle(dana, _cycle_payload(name="Silver Creek — monthly"))

        assert result["code"] == "CY-021"
        assert _series(brazos, "cycle").next_number == 22


def test_a_cycle_code_this_format_could_never_have_written_is_left_alone(brazos, dana):
    """`SCW-M` is the historical sample-plant code (`LEGACY_SAMPLE_CYCLE_CODE`).
    `CY-{000}` cannot render it at any counter value, so it can never collide
    and must not drag the counter anywhere."""
    with tenant_ctx(brazos):
        _open_series_at(brazos, "cycle", CYCLE_FORMAT, 1)
        services.create_cycle(dana, _cycle_payload(code="SCW-M", name="Legacy monthly"))

        result = services.create_cycle(dana, _cycle_payload(name="Silver Creek — monthly"))

        assert result["code"] == "CY-001"
        assert _series(brazos, "cycle").next_number == 2


def test_the_cycle_check_is_case_insensitive_because_its_refusal_is(brazos, dana):
    """`create_cycle` refuses on `code__iexact`, so a check that could only see
    an exact match would hand out a code the very next statement rejects."""
    with tenant_ctx(brazos):
        _open_series_at(brazos, "cycle", CYCLE_FORMAT, 1)
        services.create_cycle(dana, _cycle_payload(code="CY-001", name="Cycle one"))
        models.Cycle.objects.filter(code="CY-001").update(code="cy-001")

        result = services.create_cycle(dana, _cycle_payload(name="Silver Creek — monthly"))

        assert result["code"] != "CY-001"


# ═══════════════════════════════════════════════════════════════════════════
# THE SAME FAULT ON ROUTES
# ═══════════════════════════════════════════════════════════════════════════


def test_a_route_with_no_code_does_not_collide_with_seed_demos_own_codes(brazos, dana):
    """`seed_demo`'s own comment already records this shape happening in the
    OTHER direction — *"the first fresh seed after W5-T1 died on
    metering.route.code_duplicate proving it"*. This is the same collision with
    the two commands in the documented order."""
    with tenant_ctx(brazos):
        _open_series_at(brazos, "route", ROUTE_FORMAT, 1)
        for n in range(1, 7):
            services.create_route(
                dana,
                {"code": f"RT-{n:03d}", "name": f"Route {n}", "route_type": "walk"},
            )
        assert _series(brazos, "route").next_number == 1

        result = services.create_route(
            dana, {"name": "Silver Creek — walk", "route_type": "walk"}
        )

        assert result["code"] == "RT-007"
        assert _series(brazos, "route").next_number == 8
