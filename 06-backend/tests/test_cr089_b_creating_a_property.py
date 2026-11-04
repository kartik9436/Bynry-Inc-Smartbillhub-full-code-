"""CR-089 wave B — creating a property.

⚠ **EVERY CASE HERE WAS PROVED RED BEFORE THE CODE THAT MAKES IT GREEN, AND THE
PRE-CHANGE FAILURE IS QUOTED BESIDE THE CASE.** Hard-won law 7's first clause is
that a guard nobody has watched fail is not a guard; its 2026-09-04 amendment is
that the proof must run through the harness that will run the check, so these
were watched failing under `pytest`, which is what CI runs, and not through a
one-off script.

WHAT THIS FILE IS ABOUT, IN ONE SENTENCE EACH:

  * `B1` reverses `metering.premises.owner_required` — PO 2026-09-08, *"Owner =
    search ( it should be optional)"*. The refusal's own tests moved with the
    ruling and live beside the rule they used to hold (`test_def650_…`,
    `test_cr055_…`); what is HERE is the cost the reversal creates and the fence
    around it.
  * `B2` is that fence: an owner-less property lands on the **Needs an owner**
    list the moment it exists, and `B1` may not ship without it (CR-089 §2.1).
  * `B6` makes the `route` key REAL (`DEF-MET-4715`): it was on the create's
    tolerated-key list with no consumer, so a route reached the server, answered
    `201`, and was dropped.
  * `B7` previews the premise number the create is about to take and takes
    nothing (`BR-MET-1165`).
"""

from __future__ import annotations

import pytest

from apps.metering import models, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import owner_for, tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _in_tenant(sqlite_guc, brazos):  # noqa: F811 — the star-imported autouse fixture
    """Every case runs inside the tenant's own context.

    ⚠ **CLAUDE.md hard rule 1, and it names `sqlite_guc` for wave A's reason.**
    `RLS FORCE` is on, so a selector called with no `app.tenant_id` does not
    fail loudly — it answers with NOTHING, and a count assertion against an
    empty result is a test that passes for the wrong reason. The `sqlite_guc`
    argument fixes the order of two autouse fixtures that otherwise race.
    """
    with tenant_ctx(brazos):
        yield


# ── B1 + B2 — the reversal and the fence that makes it safe ────────────────


def test_b1_b2__an_ownerless_create_is_findable_the_moment_it_exists(dana):
    """**THE ONE ASSERTION THIS WAVE CANNOT SHIP WITHOUT.**

    CR-089 §2.1, on the reversal: *"a property can now exist with no party
    attached to it, so `PUJ-11` and the Needs an owner list are not optional
    extras — they are what stops the reversal creating orphans nobody can
    find."* So the create and the list are tested as ONE fact, in one case,
    deliberately: two cases could be half-deleted by a later lane and the suite
    would still be green over a hole.

    RED BEFORE: `core.errors.ValidationError: VAL-001
    metering.premises.owner_required` on field `owner_id` — the create never
    reached the list at all.
    """
    created = services.create_premises(dana, {"address_line": "901 Rockhound Way"})
    assert created["owner"] is None

    needs = {str(row.id) for row in selectors.premises_list(filters={"owner": "needs_owner"})}
    has = {str(row.id) for row in selectors.premises_list(filters={"owner": "has_owner"})}
    assert str(created["id"]) in needs
    assert str(created["id"]) not in has


def test_b2__the_filter_partitions_and_an_unknown_value_does_not_empty_the_list(dana):
    """Three things one case, because they are one behaviour.

    ⚠ **THE UNKNOWN-VALUE LEG IS THE ONE THAT MATTERS.** `BR-SHL-011`'s spirit
    is that a list URL never 4xxs over a param; the trap is answering with an
    EMPTY list instead, which reads to a clerk as *none of your properties have
    an owner* — a sentence that is false and unfalsifiable from the screen. It
    falls through to no filter, so the count is the whole tenant's.

    RED BEFORE: `owner` was not in `PREMISES_FILTERS`, so
    `core.pagination.parse_list_params` dropped it silently and all three of
    these counts were identical — the DEF-836 shape, on the list DEF-836 was
    found on.
    """
    with_owner = services.create_premises(
        dana, {"address_line": "1 Owned Way", "owner_id": owner_for(dana)}
    )
    without = services.create_premises(dana, {"address_line": "2 Unowned Way"})

    everything = list(selectors.premises_list())
    needs = list(selectors.premises_list(filters={"owner": "needs_owner"}))
    has = list(selectors.premises_list(filters={"owner": "has_owner"}))
    nonsense = list(selectors.premises_list(filters={"owner": "not-a-value"}))

    assert str(without["id"]) in {str(r.id) for r in needs}
    assert str(with_owner["id"]) in {str(r.id) for r in has}
    # A partition, not two overlapping questions.
    assert len(needs) + len(has) == len(everything)
    assert len(nonsense) == len(everything), (
        "an unknown filter value must fall through to NO filter — an empty list "
        "would read as 'none of your properties have an owner'"
    )


def test_b1__a_named_but_unknown_owner_is_still_refused_by_name(dana):
    """**`B1` RELAXES SAYING NOTHING. IT MUST NOT RELAX SAYING SOMETHING WRONG.**

    The easiest way to over-apply this ruling is to delete `_resolve_owner`'s
    refusal along with the requirement above it — both are about `owner_id` and
    both sit in the same twenty lines. This is the case that notices.
    """
    with pytest.raises(errors.ValidationError) as caught:
        services.create_premises(
            dana,
            {"address_line": "3 Ghost Ln", "owner_id": "01a08246-0000-7000-8000-000000000000"},
        )
    assert caught.value.message_key == "metering.premises.owner_unknown"


# ── B6 — the route key stops being a lie (`DEF-MET-4715`) ──────────────────


def _a_live_route(dana):
    """An active route with a cycle, made the way the product makes one."""
    return services.create_route(
        dana, {"code": "RT-B6", "name": "Wave B test route", "status": "active"}
    )


def test_b6__an_unknown_route_is_refused_by_name_and_not_swallowed(dana):
    """⚠ **THIS IS `DEF-MET-4715` AND IT IS THE WHOLE REASON `B6` TOUCHES THE
    SERVER AT ALL.**

    RED BEFORE, measured live on `brazosbend` 2026-09-09 rather than reasoned
    about: `POST /premises {"route": "COMPLETE NONSENSE, NOT A ROUTE"}` answered
    **HTTP 201**, allocated `P-00081`, and returned `routes_joined: []`. The key
    was on `_validate_premises`' tolerated list beside `units`/`unit`/
    `auto_create_unit` and NOTHING read it — so a create said a thing happened
    that did not, which is worse than refusing and worse than joining the wrong
    route.
    """
    with pytest.raises(errors.ValidationError) as caught:
        services.create_premises(
            dana,
            {"address_line": "5 Refusal Test Rd", "route": "COMPLETE NONSENSE, NOT A ROUTE"},
        )
    assert caught.value.message_key == "metering.premises.route_unknown"
    assert any(item.get("field") == "route" for item in caught.value.field_errors), (
        f"the refusal must NAME the field so B8 can focus it, got {caught.value.field_errors}"
    )


def test_b6__a_chosen_route_takes_the_buildings_units_and_reads_back(dana):
    """The route is OPTIONAL (PO: *"it should be optional"*) and honoured when
    given. The read half is asserted in the same case as the write half, because
    a route that is stored and not shown is the defect this task exists to fix:
    *"In header we are not shouding Route and Cycle information"*.
    """
    route = _a_live_route(dana)
    created = services.create_premises(
        dana,
        {
            "address_line": "412 Cypress Row",
            "route": "RT-B6",
            "units": [{"label": "Unit 1"}],
        },
    )
    assert any(entry["route_code"] == "RT-B6" for entry in created["routes_joined"])

    row = models.Premises.objects.get(pk=created["id"])
    assert "RT-B6" in {entry["code"] for entry in selectors.premises_routes(row)}

    # …and the id it resolves by is not only the code.
    by_id = services.create_premises(
        dana,
        {"address_line": "414 Cypress Row", "route": str(route["id"]), "units": [{"label": "A"}]},
    )
    assert any(entry["route_code"] == "RT-B6" for entry in by_id["routes_joined"])


def test_b6__no_route_named_is_not_an_error_and_reads_as_no_route(dana):
    """The absence has to be as ordinary as the presence, or *optional* is a
    word in a ruling rather than a behaviour."""
    created = services.create_premises(dana, {"address_line": "7 Quiet Ln"})
    row = models.Premises.objects.get(pk=created["id"])
    assert selectors.premises_routes(row) == []


# ── B7 — the number the review shows, taken by nobody (`BR-MET-1165`) ──────


def test_b7__the_preview_names_what_the_create_takes_in_BOTH_counter_states(dana):
    """**A review that names `P-00080` and then allocates something else is worse
    than no review at all — and the first draft of this preview did exactly
    that (`DEF-MET-4720`).**

    ⚠ **THE TRAP IS THAT `_allocate_unused_number` CATCHES UP ONLY ON
    COLLISION.** Its own docstring: *"allocate, and ONLY IF that number is
    already taken, catch the series up past everything that exists and allocate
    once more"*. Both previews first caught up UNCONDITIONALLY, so they
    disagreed with the allocator in exactly one state — the counter behind, and
    the number it renders to FREE — which is the ordinary state of a utility
    whose data was imported under its own numbering.

    **Measured live on `brazosbend` before the fix:** the shipped
    `GET /units/number-preview?count=1` answered `U-00421` (`caught_up: true`)
    and the very next `POST /premises` allocated **`U-00003`**.

    So this case walks BOTH states rather than one, because a test of the happy
    state alone is what let the defect ship:

      (a) counter behind, next number FREE  -> no catch-up, and the create takes
          the number the counter states;
      (b) counter behind, next number TAKEN -> catch up, and the create takes
          the caught-up number.
    """
    from apps.tenancy import models as tenancy_models

    tenant_id = services._tenant_id()

    def rewind_to(value: int) -> None:
        tenancy_models.NumberSeries.objects.filter(
            tenant_id=tenant_id, series=services.PREMISES_SERIES
        ).update(next_number=value)

    # ⚠ **THE SET-UP IS THE TEST.** A high number must be ON FILE while the
    # counter points at a LOW free one — that single state is the only place the
    # two arithmetics disagree, and a case that skips it passes against the bug.
    # (Proved: the first draft of this case did skip it. Sabotaging
    # `_preview_start` back to the shipped shape left all eight green, which is
    # what "ask what would make this check pass WRONGLY" is for.)
    rewind_to(50)
    high = services.create_premises(dana, {"address_line": "50 High Number Way"})
    assert high["premise_no"].endswith("00050")

    # (a) — the counter is behind, and the number it renders to is FREE.
    rewind_to(1)
    free = services.preview_premise_number()
    assert free["caught_up"] is False, (
        "DEF-MET-4720: P-00050 is on file but P-00001 is free, and "
        "_allocate_unused_number catches up ONLY on collision — so must this"
    )
    made = services.create_premises(dana, {"address_line": "9 Preview Way"})
    assert made["premise_no"] == free["number"], (
        f"the preview said {free['number']} and the create took {made['premise_no']}"
    )

    # (b) — rewind onto the number just used, so the stated one IS taken.
    rewind_to(1)
    blocked = services.preview_premise_number()
    assert blocked["caught_up"] is True, "P-00001 is now on file, so the catch-up must fire"
    assert blocked["number"] != free["number"]
    after = services.create_premises(dana, {"address_line": "11 Preview Way"})
    assert after["premise_no"] == blocked["number"]


def test_b7__the_preview_allocates_nothing(dana):
    """`BR-MET-1165` half (a): the number is taken ON THE PRESS. Two clerks
    reviewing at the same moment are both shown the same number, and the second
    to press gets the next one — so calling the preview twice must not move it.
    """
    first = services.preview_premise_number()
    second = services.preview_premise_number()
    assert first["number"] == second["number"]
    created = services.create_premises(dana, {"address_line": "13 Preview Way"})
    assert created["premise_no"] == first["number"]


# ── DEF-MET-4727 — a taken Parcel ID is a sentence, not a 500 ──────────────


def test_def_met_4727__a_parcel_already_on_file_is_refused_by_name(dana):
    """**RED BEFORE, and it was a `500` rather than a failing assertion:**

        django.db.utils.IntegrityError: duplicate key value violates unique
        constraint "uq_premises_tenant_external_ref_ci"

    ⚠ **THE GUARD WAS NOT MISSING — IT WAS WIRED TO ONE WRITER OF TWO.**
    `selectors.premises_external_ref_taken` exists, is tested, and says in its
    own docstring that it exists *"so a collision is a sentence and not a
    `500`"* (`DEF-INT-4273`). Only `integrations/seams/metering.py` called it,
    because until CR-089 wave A `A2` drew the **Parcel ID** box the City address
    lookup was the only thing that wrote the column.

    ⚠ **NO FIXTURE COULD HAVE FOUND THIS.** Every one of them invents a fresh
    parcel; it took a second WALKTHROUGH reusing the first walkthrough's own
    value on a live server. That is hard-won law 6 — *diff the running app* —
    and this case is the check that keeps it closed.

    The refusal must NAME the field, because CR-089 `B8` puts the clerk back on
    the control that caused it and a refusal with no field lands nowhere.
    """
    services.create_premises(
        dana, {"address_line": "1 Parcel Way", "external_ref": "R-114-0082-004"}
    )
    with pytest.raises(errors.BizError) as caught:
        services.create_premises(
            dana, {"address_line": "2 Parcel Way", "external_ref": "R-114-0082-004"}
        )
    assert caught.value.message_key == "metering.premises.external_ref_taken"
    assert any(item.get("field") == "external_ref" for item in caught.value.field_errors), (
        f"B8 needs the field named to focus it, got {caught.value.field_errors}"
    )

    # ⚠ CASE-INSENSITIVELY, BECAUSE THE INDEX IS. A check looser than the
    # constraint it stands in front of passes a value the database then refuses,
    # which is this defect again wearing a different case.
    with pytest.raises(errors.BizError):
        services.create_premises(
            dana, {"address_line": "3 Parcel Way", "external_ref": "r-114-0082-004"}
        )

    # …and a DIFFERENT parcel still saves, or the guard is just a wall.
    ok = services.create_premises(
        dana, {"address_line": "4 Parcel Way", "external_ref": "R-114-0082-005"}
    )
    assert ok["external_ref"] == "R-114-0082-005"


def test_def_met_4757__editing_onto_a_taken_parcel_is_refused_by_name(dana):
    """**THE SAME `500`, ONE WRITER ALONG — the PO hit it on the live product.**

    `DEF-MET-4727` (the case above) removed this on CREATE and the comment it
    left behind ended on:

        ⚠ **CREATE ONLY.** … The index still refuses a true duplicate there.

    **That sentence is true and it is the defect.** The index refusing it IS

        django.db.utils.IntegrityError: duplicate key value violates unique
        constraint "uq_premises_tenant_external_ref_ci"

    escaping unhandled out of `update_premises`, reaching a clerk as *"Something
    went wrong on our side. Nothing was saved."* — the exact failure the guard
    was written to remove.

    ⚠ **THE SELF-COLLISION THE OLD COMMENT WORRIED ABOUT IS REAL**, which is why
    the fix is an argument rather than a second check: an edit resending the
    row's OWN parcel must still save, and the case below asserts that in the
    same breath. A guard that refused it would break every ordinary save.
    """
    keeper = services.create_premises(
        dana, {"address_line": "10 Deed Row", "external_ref": "R-500-0001-000"}
    )
    mover = services.create_premises(dana, {"address_line": "12 Deed Row"})

    # 1 · typing a parcel another property already holds is a SENTENCE.
    with pytest.raises(errors.BizError) as caught:
        services.update_premises(dana, str(mover["id"]), {"external_ref": "R-500-0001-000"})
    assert caught.value.message_key == "metering.premises.external_ref_taken"
    assert any(item.get("field") == "external_ref" for item in caught.value.field_errors), (
        f"B8 needs the field named to focus it, got {caught.value.field_errors}"
    )

    # 2 · CASE-INSENSITIVELY, because the index is. A check looser than the
    #     constraint passes a value the database then refuses — the same defect
    #     wearing a different case.
    with pytest.raises(errors.BizError):
        services.update_premises(dana, str(mover["id"]), {"external_ref": "r-500-0001-000"})

    # 3 · ⚠ **AND THE ROW'S OWN PARCEL STILL SAVES.** This is the case that
    #     makes the guard usable on an edit at all: the edit form resends every
    #     field it drew, so the ordinary save carries the parcel already stored.
    #     Without `except_id` this row would be refused for colliding with
    #     itself and NO property with a parcel could ever be edited again.
    again = services.update_premises(
        dana, str(keeper["id"]), {"external_ref": "R-500-0001-000", "city": "Katy"}
    )
    assert again["external_ref"] == "R-500-0001-000"

    # 4 · and moving a parcel to a property that has none still works — a clerk
    #     correcting which building a deed belongs to is an ordinary edit.
    services.update_premises(dana, str(keeper["id"]), {"external_ref": ""})
    moved = services.update_premises(
        dana, str(mover["id"]), {"external_ref": "R-500-0001-000"}
    )
    assert moved["external_ref"] == "R-500-0001-000"
