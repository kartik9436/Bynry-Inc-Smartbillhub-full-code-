# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (guided add)   Change: CR-089 wave E (`E6`/`PUJ-26`)
# Rules:    BR-MET-1165 (a number a review shows is TAKEN ON THE PRESS, never
#           reserved by the preview — and the preview must SIMULATE the
#           allocator, not restate its idea) · BR-MET-001 (numbering) ·
#           BR-TEN-035 (a series counter moves forward only)
# Defects:  DEF-577 (a series handing out a number that already exists) ·
#           DEF-MET-4719 (the review said U-00421 and the create issued U-00001)
# ───────────────────────────────────────────────────────
"""`services.preview_unit_numbers` — what the add-units review may print.

**THE ONE THING THIS FILE HAS TO GET RIGHT.** A preview of an allocator is only
worth anything if it predicts the allocator, so every case below is written as a
PREDICTION TEST: ask for the numbers, then create the units, then compare. A
test that only asserted the endpoint agrees with itself is exactly the test that
was green while the screen printed `U-00421` and the product wrote `U-00001`
(`DEF-MET-4719`) — the endpoint was internally consistent and wrong.

⚠ **AND THE FULL PROOF IS NOT HERE.** These cases run the service; what runs the
SCREEN is `10-scripts/cr089_wave_e_add_units_walkthrough.mjs`, which reads the
numbers off the rendered review before pressing Create. That is the check that
found `DEF-MET-4719`, and it found it with this file's predecessor green.
"""

import pytest

from apps.metering import models, services
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def _series(tenant):
    return tenancy_models.NumberSeries.objects.get(tenant=tenant, series="unit")


def _put_counter_at(tenant, value):
    """Move the `unit` counter without going through the forward-only service.

    ⚠ Deliberate, and it is what makes the collision case reachable: `DEF-577`'s
    world is a counter standing BEHIND the column, and `advance_number_series`
    is forward-only by `BR-TEN-035` so it cannot build that state. The rows this
    creates are the ones a caller-supplied `unit_no` and the CR-023 import load
    stage leave behind in the product.
    """
    tenancy_models.NumberSeries.objects.filter(tenant=tenant, series="unit").update(
        next_number=value
    )


def test_the_numbers_it_shows_are_the_numbers_the_create_takes(dana, brazos):
    """`BR-MET-1165` (b), the plain case — no collision anywhere."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        shown = services.preview_unit_numbers(3)
        assert shown["series_missing"] is False
        assert shown["caught_up"] is False
        assert len(shown["numbers"]) == 3

        created = [
            make_unit(dana, premises["id"], label=str(index + 1))["unit_no"] for index in range(3)
        ]
        assert created == shown["numbers"]
        assert shown["last"] == created[-1]


def test_a_counter_standing_behind_the_column_is_caught_up_exactly_as_the_create_catches_it(
    dana, brazos
):
    """`DEF-577`'s world, and the half `DEF-MET-4719` got wrong.

    The counter is put BEHIND a number already on file, so the first allocation
    collides and the allocator's repair path fires. The preview has to predict
    the repaired block, not the raw counter — and it has to predict where the
    repair LANDS, which is one past the highest value this format could have
    written, never one past the counter.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        # A unit whose number this format COULD have written, well ahead of the
        # counter — the product gets these from a caller-supplied `unit_no`.
        make_unit(dana, premises["id"], label="High", unit_no="U-00420")
        # ⚠ **THE COUNTER IS PUT EXACTLY ON THE TAKEN NUMBER, AND THAT IS THE
        # WHOLE POINT.** The first draft of this test put it at 350 and asserted
        # a catch-up — it went RED with `assert False is True`, correctly,
        # because `U-00350` is on nobody's file in this fixture and there is
        # therefore no collision to repair. That is the same misreading
        # `DEF-MET-4719` is about, one layer up: *behind the highest number* is
        # not *colliding*. On the demo database 350 DID collide, which is how
        # the wrong premise looked right.
        _put_counter_at(brazos, 420)

        shown = services.preview_unit_numbers(3)
        assert shown["caught_up"] is True, "a collision must be predicted as a catch-up"
        created = [
            make_unit(dana, premises["id"], label=f"c{index}")["unit_no"] for index in range(3)
        ]
        assert created == shown["numbers"]
        assert created[0] == "U-00421", created


def test_a_counter_merely_lower_than_the_highest_number_is_NOT_caught_up(dana, brazos):
    """⛔ **THE CASE THAT MAKES `DEF-MET-4719` A DEFECT AND NOT A PREFERENCE.**

    `U-00420` is on file and the counter stands at 1. The obvious reading of
    `DEF-577` — *the counter is behind the table, catch it up* — is what the
    first implementation did, and it is WRONG: `_allocate_unused_number` asks
    whether the number it just rendered is taken, and `U-00001` is not. So the
    create issues `U-00001`, and a preview that printed `U-00421` would be
    lying about a number a clerk is looking at.

    This test was written against the fixed function and PROVED RED by putting
    the old always-catch-up behaviour back: it then reports
    `assert ['U-00421', 'U-00422'] == ['U-00001', 'U-00002']`.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        make_unit(dana, premises["id"], label="High", unit_no="U-00420")
        _put_counter_at(brazos, 1)

        shown = services.preview_unit_numbers(2)
        assert shown["caught_up"] is False
        assert shown["numbers"] == ["U-00001", "U-00002"], shown["numbers"]
        created = [
            make_unit(dana, premises["id"], label=f"p{index}")["unit_no"] for index in range(2)
        ]
        assert created == shown["numbers"]


def test_asking_twice_reserves_nothing(dana, brazos):
    """`BR-MET-1165` (a). Two clerks reviewing at the same moment see the same
    numbers, because looking is a read and takes nothing."""
    with tenant_ctx(brazos):
        before = _series(brazos).next_number
        first = services.preview_unit_numbers(3)
        second = services.preview_unit_numbers(3)
        assert first["numbers"] == second["numbers"]
        assert _series(brazos).next_number == before, "a preview moved the counter"
        assert models.Unit.objects.filter(tenant=brazos).count() == 0


def test_the_run_s_own_numbers_count_as_taken(dana, brazos):
    """A block of N is N allocations against a MOVING counter. Predicting each
    one as though the previous had not happened would repeat a number."""
    with tenant_ctx(brazos):
        shown = services.preview_unit_numbers(5)
        assert len(set(shown["numbers"])) == 5, shown["numbers"]


def test_a_run_larger_than_the_shown_window_still_names_where_it_ENDS(dana, brazos):
    """Forty units print five numbers and the fortieth — a rehearsal shows a
    shape, and `last` is what stops it being a shape with no end."""
    with tenant_ctx(brazos):
        shown = services.preview_unit_numbers(40)
        assert len(shown["numbers"]) == services.UNIT_PREVIEW_NUMBERS_SHOWN
        assert shown["count"] == 40
        assert shown["last"] is not None and shown["last"] not in shown["numbers"]


def test_a_tenant_with_no_unit_series_is_told_so_rather_than_shown_an_invented_number(
    dana, brazos
):
    """BE-06 makes seeding a series provisioning's job. A wizard that answered
    `U-00001` for a tenant whose numbering was never set up would be inventing
    the one thing this whole rule exists to protect."""
    with tenant_ctx(brazos):
        tenancy_models.NumberSeries.objects.filter(tenant=brazos, series="unit").delete()
        shown = services.preview_unit_numbers(3)
        assert shown["series_missing"] is True
        assert shown["numbers"] == []
        assert shown["last"] is None


def test_asking_for_nothing_answers_nothing(dana, brazos):
    with tenant_ctx(brazos):
        assert services.preview_unit_numbers(0)["numbers"] == []
        assert services.preview_unit_numbers(-4)["numbers"] == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 wave E · E6 (PUJ-26) · BR-MET-1165 · DEF-MET-4719
# generated: 2026-09-09 by the CR-089 wave E build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
# exceptions: E3 `_put_counter_at` writes `number_series.next_number` directly
#   because `advance_number_series` is forward-only (BR-TEN-035) and cannot
#   build the state DEF-577 describes. The rows it stands in for are real —
#   a caller-supplied `unit_no` and the import load stage both leave them.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
