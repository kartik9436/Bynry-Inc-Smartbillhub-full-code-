# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-AST-7660 — `+ Assign from inventory` could not record a
#          connection size, so a meter was installed with `size_class` NULL and
#          `BR-RAT-108` could not price its base charge. The Product Owner's
#          own report: *"the clerk cannot set the connection size, so the size
#          column in the unit's table is blank"*.
# Rules:   BR-AST-500 (the column — NULL is a real answer, never defaulted) ·
#          BR-AST-501 (billing-affecting) · BR-AST-530 (the size is offered for
#          METERS) · BR-AST-009 (a non-measuring device declares no service) ·
#          BR-RAT-108 (service → account type → size class picks the base
#          charge) · DEF-3098 (whether a service BANDS is a ruled fact, never
#          "does it have size rows") · CLAUDE.md hard rule 7 (every money
#          action writes `audit_log`)
# Tests:   this file — TC-B1..B8
# ───────────────────────────────────────────────────────
"""The server half of `DEF-AST-7660`: a reassign may CARRY a connection size,
and REFUSES a size-banded service that has none.

⚠ **THE REFUSAL IS DELIBERATELY NARROW AND TC-B6/TC-B7 ARE WHAT HOLD IT
THERE.** `BR-AST-009`'s own note in `services.py` records why: a refusal that
fired on every path would also fire on `AssetFlowPages`' full-page reassign
(S55) and on `bulk_assign`, *"neither of which draws a service control — so a
clerk who can assign a meter from the registry today could not assign one at
all"*. That is a live screen behind a refusal nobody can satisfy — hard-won law
2's mirror — so the rule binds only a payload that DECLARES the service.

RED-FIRST PROOF (r11 step 2d), before this lane's change, at `db075389b`:

    TC-B1 → AssertionError: assert None == 'W-2'
             (the size was accepted by nothing and written nowhere)
    TC-B2 → DID NOT RAISE <class 'core.errors.ValidationError'>
    TC-B5 → AssertionError: assert None == 'W-2'

and after the change, with `if asset.type.code not in MEASURING_TYPES: return`
deleted from `_guard_declared_size`, TC-B7 went RED with
`ValidationError: assets.size_class_required_for_banded_service` on a backflow
preventer — the "do not make it blanket-required across every asset class" half
is asserted, not assumed.
"""

import pytest

from apps.assets import models, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def a_unit(actor, label="Unit A", address="1408 Elm Street"):
    premise = make_premises(actor, address_line=address)
    return make_unit(actor, premise["id"], label=label, services=["electric", "water"])


def shelf_meter(actor, asset_no="M-7660", **overrides):
    """A spare with NO size recorded — the row the Product Owner reported.

    ⚠ `size_class=None` is passed EXPLICITLY. `make_asset` fits the service's
    smallest ratified band by default (`DEF-2965`), so a fixture that simply
    omitted it would create a meter that already has one and every case below
    would pass over the defect.
    """
    payload = {"asset_no": asset_no, "service": "water", "unit": "kgal", "size_class": None}
    payload.update(overrides)
    return make_asset(actor, **payload)


def stored_size(asset_id):
    return models.Asset.objects.get(id=asset_id).size_class


# ── The size is RECORDABLE on the assign ───────────────────────────────────
def test_tc_b1__an_assign_that_carries_a_size_writes_it_to_the_device(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = shelf_meter(dana)
        assert stored_size(asset["id"]) is None
        services.reassign_asset(
            dana,
            asset["id"],
            {
                "unit_id": unit["id"],
                "effective_date": "2026-08-08",
                "record_final_read": False,
                "service": "water",
                "size_class": "W-2",
            },
        )
        assert stored_size(asset["id"]) == "W-2"


def test_tc_b2__a_banded_service_with_no_size_anywhere_is_REFUSED(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = shelf_meter(dana)
        with pytest.raises(errors.ValidationError) as caught:
            services.reassign_asset(
                dana,
                asset["id"],
                {
                    "unit_id": unit["id"],
                    "effective_date": "2026-08-08",
                    "record_final_read": False,
                    "service": "water",
                },
            )
    assert caught.value.code == errors.VAL_REQUIRED
    assert (
        caught.value.field_errors[0]["message_key"]
        == "assets.size_class_required_for_banded_service"
    )
    assert caught.value.field_errors[0]["field"] == "size_class"


def test_tc_b3__the_refusal_fires_BEFORE_any_write(brazos, dana):
    """⚠ **THE ASSET MUST NOT HALF-MOVE.** `_reassign_inner` closes the current
    assignment and opens a new one before it reaches the service branch, so a
    refusal placed there would leave a row a human must clean up. This asserts
    the guard sits with the other two, at the top."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = shelf_meter(dana)
        before_status = models.Asset.objects.get(id=asset["id"]).status.code
        with pytest.raises(errors.ValidationError):
            services.reassign_asset(
                dana,
                asset["id"],
                {"unit_id": unit["id"], "record_final_read": False, "service": "water"},
            )
        row = models.Asset.objects.get(id=asset["id"])
        assert row.status.code == before_status
        assert models.AssetAssignment.objects.filter(asset_id=asset["id"]).count() == 0


def test_tc_b4__a_size_ALREADY_on_the_device_satisfies_the_rule(brazos, dana):
    """`make_asset` fits the smallest ratified band, so this meter arrives with
    one. Nothing need be re-typed at the counter to install it."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(dana, asset_no="M-7661", service="water", unit="kgal")
        assert stored_size(asset["id"]) is not None
        services.reassign_asset(
            dana,
            asset["id"],
            {"unit_id": unit["id"], "record_final_read": False, "service": "water"},
        )
        assert models.Asset.objects.get(id=asset["id"]).status.code == "active"


def test_tc_b5__the_old_and_new_size_are_BOTH_in_the_audit_row(brazos, dana, audit_rows):
    """CLAUDE.md hard rule 7. The `asset.reassigned` row already carries the
    whole `asset_dict` before and after, and `size_class` is in both — so a
    size recorded at the counter is traceable without one extra line of code.
    Asserted rather than assumed, because a reader finding the write in the
    to-unit branch will look for an audit call beside it and find none."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = shelf_meter(dana, asset_no="M-7662")
        services.reassign_asset(
            dana,
            asset["id"],
            {
                "unit_id": unit["id"],
                "record_final_read": False,
                "service": "water",
                "size_class": "W-2",
            },
        )
    row = [r for r in audit_rows if r["action"] == "asset.reassigned"][-1]
    assert row["before"]["size_class"] is None
    assert row["after"]["size_class"] == "W-2"


# ── The refusal is NARROW — these three keep it there ──────────────────────
def test_tc_b6__no_service_declared_means_no_refusal(brazos, dana):
    """S55's full-page reassign and `bulk_assign` draw no service control and
    send none, so neither is touched by this rule. `DEF-AST-5863` holds the
    wider change; breaking those two screens to fix this one would be the
    defect running backwards."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = shelf_meter(dana, asset_no="M-7663")
        services.reassign_asset(
            dana, asset["id"], {"unit_id": unit["id"], "record_final_read": False}
        )
        assert models.Asset.objects.get(id=asset["id"]).status.code == "active"
        assert stored_size(asset["id"]) is None


def test_tc_b7__a_NON_MEASURING_device_is_never_asked_for_a_size(brazos, dana):
    """`BR-AST-530` offers the connection size for METERS. A backflow preventer
    declaring water must not be refused for a fact no surface asks it for —
    that would refuse a legitimate row, which is the opposite of the fix."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(
            dana,
            asset_no="BF-7664",
            type="backflow",
            service="water",
            unit=None,
            size_class=None,
        )
        services.reassign_asset(
            dana,
            asset["id"],
            {"unit_id": unit["id"], "record_final_read": False, "service": "water"},
        )
        assert stored_size(asset["id"]) is None


def test_tc_b8__going_BACK_to_inventory_records_no_size_and_refuses_nothing(brazos, dana):
    """A device returning to the shelf says nothing about the connection it has
    just left, so a `size_class` on that payload is a caller mistake rather than
    an instruction — writing it would let a return quietly restate a
    billing-affecting fact."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(dana, asset_no="M-7665", service="water", unit="kgal", size_class=None)
        services.reassign_asset(
            dana, asset["id"], {"unit_id": unit["id"], "record_final_read": False}
        )
        services.reassign_asset(
            dana,
            asset["id"],
            {"to_inventory": True, "record_final_read": False, "size_class": "W-2"},
        )
        assert stored_size(asset["id"]) is None
        assert models.Asset.objects.get(id=asset["id"]).status.code == "inventory"


# ── The seam and the read the screen uses ──────────────────────────────────
def test_tc_b9__the_banded_answer_is_ratings_and_the_three_cases_stay_apart(brazos, dana):
    """⚠ **THE PROXY `DEF-3098` RETIRED MUST NOT COME BACK.** Water bands;
    solar has TEN size-class rows and does NOT band, because they are a
    capacity to SUM. Swapping the seam for *"does this service have size
    rows"* turns the four capacity lines red, which is the whole point of
    asserting them by name rather than asserting one.

    ⚠ **THE FIRST DRAFT OF THIS CASE ASSERTED `thermal_heat` AND `battery`
    ANSWER `None`, TAKING IT FROM THE `OQ-560` / `OQ-561` SENTENCES IN THE
    NEIGHBOURING DOCSTRINGS, AND IT WENT RED.** Both are RULED today and
    answer `False`: thermal sums in tons and battery in kW. The unruled thing
    is the DIMENSION `thermal_heat_steam`, which is not a service code at all
    (`UNBANDED_SERVICE_DIMENSIONS`) — *"thermal is half ruled, and this is the
    half that is not"*. Hard-won law 1: the sentence describing the boundary
    had outlived the boundary, and this is the assertion that dates it.
    """
    from apps.assets import seams

    with tenant_ctx(brazos):
        # BANDED — the band picks the rate (fire and trash multiply by COUNT).
        for code in ("water", "electric", "gas", "trash", "fire"):
            assert seams.service_prices_by_size_class(code) is True, code
        # CAPACITY — rows that are a quantity to SUM, never a rate axis.
        for code in ("solar", "battery", "storm_water", "broadband", "thermal_heat"):
            assert seams.service_prices_by_size_class(code) is False, code
        # RULED TO HAVE NONE — BR-RAT-015, a share of the water usage charge.
        assert seams.service_prices_by_size_class("sewer") is False
        # NOT RULED — the third answer, and it is `None` rather than `False`.
        assert seams.service_prices_by_size_class("thermal_heat_steam") is None
        assert seams.service_prices_by_size_class("moon_dust") is None


def test_tc_b10__the_screen_read_splits_this_tenants_services_three_ways(brazos, dana):
    """`GET /assets/size-banded-services`. Scoped to ENABLED services, because
    offering an answer about a service the utility does not sell would draw a
    requirement onto a screen that can never show it."""
    from apps.assets import selectors, seams

    with tenant_ctx(brazos):
        answer = selectors.size_banded_services()
        enabled = seams.enabled_service_codes()
    assert set(answer) == {"banded", "not_banded", "not_ruled"}
    assert "water" in answer["banded"]
    # ⚠ **COUNT WHAT WAS FOUND AGAINST WHAT SHOULD BE THERE** (hard-won law 7's
    # fifth shape). Every enabled service lands in exactly one of the three, so
    # a service silently dropped by a future branch cannot read as "not banded".
    placed = len(answer["banded"]) + len(answer["not_banded"]) + len(answer["not_ruled"])
    assert placed == len(enabled)
