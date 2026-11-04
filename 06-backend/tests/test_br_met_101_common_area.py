# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-002/003 (units)   Change: CR-023 follow-on (W3 lane, 2026-08-22)
# Rules:    BR-MET-101 (a common area is a UNIT WITH A FLAG — no new table; the
#           flag separates it from a vacant unit billed to the owner,
#           BR-MET-094) · BR-MET-100 second half (an unplanned unit is COUNTED
#           AND FINDABLE — the Units tab carries a filter that lists them) ·
#           BR-MET-035 (unit writes = System Admin + Billing Clerk) ·
#           BR-MET-048 / hard rule 7 (every change is audited)
# Note:     `unit_type = "common_area"` (one of US-MET-002 §5's five types) and
#           the FLAG are deliberately independent on NEW writes: the flag is
#           the queryable fact BR-MET-101 ruled, the type stays a descriptive
#           label, and migration 0016's backfill closed the gap for rows typed
#           before the flag existed. Nothing here auto-couples them — coupling
#           would quietly make the TYPE authoritative, the opposite of the
#           ruling. Stated in _validate_unit's comment and asserted in TC-6.
# ───────────────────────────────────────────────────────
"""BR-MET-101 — the common-area flag; BR-MET-100 — unplanned units findable."""

import pytest

from apps.metering import api, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    FakeUser,
    api_call,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def test_br_met_101_tc1__the_flag_round_trips_create_read_update_and_is_audited(
    brazos, dana, audit_rows
):
    """A common area is created as a unit with the flag, served with the flag,
    and the flag is editable — every step through the real service."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        common = make_unit(
            dana, premise["id"], label="Hallway lighting", unit_type="common_area",
            is_common_area=True,
        )
        assert common["is_common_area"] is True

        served = selectors.unit_detail_dict(selectors.unit_row(common["id"]))
        assert served["is_common_area"] is True
        # ...and the S15 row dict carries it too — BR-MET-101: "the flag must
        # be visible everywhere it matters".
        assert selectors.unit_list_dict(selectors.unit_row(common["id"]))["is_common_area"] is True

        flipped = services.update_unit(dana, common["id"], {"is_common_area": False})
        assert flipped["is_common_area"] is False
        updates = [row for row in audit_rows if row["action"] == "unit.updated"]
        assert updates, "hard rule 7: the flag change writes audit_log"
        assert updates[-1]["before"]["is_common_area"] is True
        assert updates[-1]["after"]["is_common_area"] is False


def test_br_met_101_tc2__the_flag_defaults_false_and_a_non_boolean_is_refused(brazos, dana):
    """`"false"` is a non-empty string, i.e. truthy — accepting it would flag a
    lived-in unit as shared space. Strict boolean or refusal, nothing between."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        plain = make_unit(dana, premise["id"], label="Unit A")
        assert plain["is_common_area"] is False

        with pytest.raises(errors.ValidationError) as caught:
            services.update_unit(dana, plain["id"], {"is_common_area": "false"})
        fields = caught.value.field_errors or []
        assert any(
            f["field"] == "is_common_area"
            and f["message_key"] == "metering.unit.common_area_boolean"
            for f in fields
        )
        # the refusal wrote nothing
        assert selectors.unit_detail_dict(selectors.unit_row(plain["id"]))[
            "is_common_area"
        ] is False


def test_br_met_101_tc3__the_premises_rollup_serves_the_n_plus_m_common_split(brazos, dana):
    """r10's PRM-02 tile reads "3 + common" — BR-MET-101's own worked case is
    1408 Elm, 3 units + 2 common areas. `units` stays the TOTAL (BR-MET-037's
    delete guard counts on it); `units_common` rides beside it."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="1408 Elm St")
        for label in ("Unit A", "Unit B", "Unit C"):
            make_unit(dana, premise["id"], label=label)
        make_unit(
            dana, premise["id"], label="Hallway lighting", unit_type="common_area",
            is_common_area=True,
        )
        make_unit(
            dana, premise["id"], label="Shared irrigation", unit_type="common_area",
            is_common_area=True,
        )

        detail = selectors.premises_detail_dict(selectors.premises_row(premise["id"]))
        assert detail["units"] == 5  # the TOTAL — unchanged meaning
        assert detail["units_common"] == 2  # the M of "3 + 2 common"

        rollup = selectors.premises_rollup()
        assert rollup["units"] == 5
        assert rollup["common"] == 2


def test_br_met_100_tc4__the_units_list_filter_finds_unplanned_units(brazos, dana):
    """BR-MET-100: "the Units tab carries a filter that lists them." An
    unplanned unit never appears on a bill while looking complete — this filter
    is what makes that decided risk operable."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        planned = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        unplanned = make_unit(dana, premise["id"], label="Unit B")
        plan = make_plan(brazos)
        services.assign_unit_plan(
            dana, planned["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
        )

        without_plan = selectors.units_list(filters={"plan": "unplanned"})
        assert {u.label for u in without_plan} == {"Unit B"}
        with_plan = selectors.units_list(filters={"plan": "planned"})
        assert {u.label for u in with_plan} == {"Unit A"}
        # an unknown value carves nothing (BR-SHL-010: a list URL never 4xxs)
        assert {u.label for u in selectors.units_list(filters={"plan": "nonsense"})} == {
            "Unit A",
            "Unit B",
        }

    # the filter is DECLARED, so `f.plan` survives the API's allow-list —
    # an undeclared filter is silently ignored (BE-05) and the screen would
    # show every unit looking like a filtered slice.
    assert "plan" in api.UNIT_FILTERS
    listed = api_call(
        api.units,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        query={"f.plan": "unplanned"},
    )
    assert listed.status_code == 200
    assert [row["label"] for row in listed.data["results"]] == ["Unit B"]
    assert unplanned["id"] == listed.data["results"][0]["id"]


def test_br_met_101_tc5__a_common_area_is_distinguishable_from_a_vacant_unit(brazos, dana):
    """BR-MET-101's accepted cost, verbatim: "the flag is what separates a
    common area from a vacant unit billed to the owner (BR-MET-094), which
    would otherwise be the same row." Both are vacant — no active account —
    and the flag is the ONLY served difference this test allows to matter."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        vacant = make_unit(dana, premise["id"], label="Unit A")
        common = make_unit(
            dana, premise["id"], label="Hallway lighting", is_common_area=True
        )

        vacant_row = selectors.unit_list_dict(selectors.unit_row(vacant["id"]))
        common_row = selectors.unit_list_dict(selectors.unit_row(common["id"]))
        # the rows agree on everything occupancy-shaped…
        assert vacant_row["occupancy"] == "vacant"
        assert common_row["occupancy"] == "vacant"
        # …and disagree on exactly the flag
        assert vacant_row["is_common_area"] is False
        assert common_row["is_common_area"] is True


def test_br_met_101_tc6__the_type_label_and_the_flag_are_independent_on_new_writes(brazos, dana):
    """The FLAG is the ruled fact; `unit_type` stays a descriptive label. A new
    unit typed `common_area` without the flag stays flag-false — migration
    0016's backfill was a one-time closure for pre-flag rows, not a live
    coupling. If a future ruling couples them, this is the test to supersede."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        typed_only = make_unit(
            dana, premise["id"], label="Unit T", unit_type="common_area"
        )
        assert typed_only["is_common_area"] is False
        assert typed_only["unit_type"] == "common_area"
