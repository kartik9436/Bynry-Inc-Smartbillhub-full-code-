# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-005 (S26/S27 Reads Routes & Cycles operational tabs) ·
#           US-MET-006 (S8 Settings → Routes & Cycles configuration)
# Rules:    BR-MET-008 (route identity + delete audit-lock) · BR-MET-009
#           (cycle windows, bill date ≥ window end, due_days ≥ 0, delete
#           audit-lock) · BR-MET-010 (one cycle per route — assignment MOVES) ·
#           BR-MET-011 (S26/S27 read-only; progress derived from committed
#           reads) · BR-MET-033 (membership by selection + OPTIONAL walk order,
#           no sequence ranges) · BR-MET-048 (config audit)
# Note:     AMENDED 2026-08-10 (W2 reads lane): collected/progress are now
#           MEASURED (0 with no reads) because `meter_reads` exists; they were
#           NULL while it did not. last_completion stays null until a read
#           lands. The original note follows.
#           collected/progress/last_completion were NULL: they derive from
#           committed reads and `meter_reads` is the W2 reads lane's table
#           (B2 r16 #4). A fabricated 0 would claim "nothing collected".
# ───────────────────────────────────────────────────────
"""US-MET-005 / US-MET-006 — routes & cycles ops views and configuration."""

from datetime import date

import pytest

from apps.metering import api, models, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    FakeUser,
    api_call,
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def seed_cycle(actor, code="08-A", **overrides):
    """⚠ W5-T2 — the DEFAULTS are the ruled fields now.

    This sent `window_start` / `window_end` / `bill_date`, and metering 0021
    dropped the first two. The same window — 1 Aug to 5 Aug — is said as *start
    day 1, 5 days to complete*, which is what B17 §2 rules.

    ⚠ **AND `bill_date` LEFT THE PAYLOAD TOO (RC-W6, metering 0023 / OQ-344).**
    It stayed while the column did — billing's due-terms fallback read it and no
    ruling said what replaced it — and the PO ruled on 2026-08-23: *"I'd say B -
    these are defualt - user can override"*, the bill DAY in the month after the
    period ends. So the payload carries `bill_day` and the served `bill_date` /
    `due_date` are DERIVED from the cycle's next period, which is why the cases
    below assert their DAY rather than a fixed month (the month moves with the
    tenant's own today, exactly as `window_start` already did).

    An individual case may still pass `window_start=`/`window_end=` — they are
    ACCEPTED and IGNORED — and the two that do are testing exactly that.
    """
    payload = {
        "code": code,
        "frequency": "Monthly",
        "start_day": 1,
        "days_to_complete": 5,
        # OQ-344 — the DAY. The first run is here so the cycle HAS a next period
        # for the derived bill date to be computed against; without one, both
        # derived keys are honestly null.
        "bill_day": 8,
        "first_run_date": "2026-08-01",
        "due_days": 20,
    }
    payload.update(overrides)
    return services.create_cycle(actor, payload)


# ── US-MET-006 · S8 configuration ───────────────────────────────────────────
def test_us_met_006_tc1__route_membership_is_selection_with_optional_walk_order(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        cycle = seed_cycle(
            dana, "08-B", window_start="2026-08-12", window_end="2026-08-16", bill_day=19
        )
        premise = make_premises(dana, address_line="77 Gulf Fwy Industrial")
        unit = make_unit(dana, premise["id"], label="Bldg 1", services=["electric"])
        route = services.create_route(
            dana,
            {
                "code": "Route 5",
                "name": "Gulf Fwy",
                "route_type": "walk",
                "cycle_id": cycle["id"],
                "premises_ids": [premise["id"]],  # selecting a premise includes its units
            },
        )
        members = selectors.route_members(route["id"])
        point = models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
    assert route["members"] == 1 and route["cycle_code"] == "08-B"
    assert members[0]["walk_order"] is None  # BR-MET-033: walk order is OPTIONAL
    assert str(point.route_id) == route["id"] and str(point.cycle_id) == cycle["id"]
    assert "route.created" in [r["action"] for r in audit_rows]


def test_us_met_006_tc2__cycle_assignment_moves_a_route_never_duplicates_it(brazos, dana):
    with tenant_ctx(brazos):
        first = seed_cycle(dana, "08-A")
        second = seed_cycle(
            dana, "09-A", window_start="2026-09-01", window_end="2026-09-05", bill_day=8
        )
        route = services.create_route(dana, {"code": "Route 1", "cycle_id": first["id"]})
        services.update_cycle(dana, second["id"], {"route_ids": [route["id"]]})
        moved = selectors.route_detail(route["id"])
        cycles = {c["code"]: c for c in selectors.cycles_list()}
    assert moved["cycle_code"] == "09-A"  # BR-MET-010: moved, not duplicated
    assert cycles["09-A"]["routes"] == ["Route 1"] and cycles["08-A"]["routes"] == []
    # ⚠ `due_date` IS DERIVED NOW (OQ-344): the bill DAY placed in the month
    # after the cycle's next period ends, plus `due_days` — date math only, no
    # money. The DAY is what this asserts: 8 + 20 = the 28th. The MONTH moves
    # with the tenant's own today, so pinning it would fail on a calendar
    # boundary rather than on a defect.
    assert cycles["09-A"]["due_date"].endswith("-28")


def test_us_met_006_tc3__membership_and_walk_order_edit_in_place_with_before_after(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        unit_a = make_unit(dana, premise["id"], label="Unit A")
        unit_b = make_unit(dana, premise["id"], label="Unit B")
        route = services.create_route(
            dana, {"code": "Route 3", "members": [{"unit_id": unit_a["id"]}]}
        )
        services.update_route(
            dana,
            route["id"],
            {
                "members": [
                    {"unit_id": unit_a["id"], "walk_order": 1},
                    {"unit_id": unit_b["id"], "walk_order": 2},
                ]
            },
        )
        members = selectors.route_members(route["id"])
    assert [(m["unit_label"], m["walk_order"]) for m in members] == [("Unit A", 1), ("Unit B", 2)]
    updated = [r for r in audit_rows if r["action"] == "route.updated"]
    assert len(updated[0]["before"]["members"]) == 1 and len(updated[0]["after"]["members"]) == 2


def test_us_met_006_tc11__no_sequence_range_exists_anywhere(brazos, dana):
    """BR-MET-033 (OQ-041 CLOSED): the superseded numeric sequence/capacity
    range is refused as an unknown field, and no column carries one."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_route(dana, {"code": "Route 9", "sequence_from": 1, "sequence_to": 400})
    assert caught.value.field_errors[0]["message_key"] == "metering.route.sequence_range_removed"
    assert not any(
        f.name in ("sequence_from", "sequence_to", "capacity")
        for f in models.Route._meta.get_fields()
    )


def test_us_met_006_tc12__a_unit_sits_on_at_most_one_route(brazos, dana):
    """⚠ **AMENDED 2026-08-17 by CR-006 / BR-MET-074.** This case asserted that
    a second route MUST REFUSE a unit already on one, with the message key
    `metering.route.unit_on_another_route`. The PO's CR-006 requirement is the
    opposite — *"Premises already on another route for the same service show a
    badge… selecting moves them, with confirm"* — and the old refusal made that
    unbuildable, because the server refused before any confirm could be
    offered.

    **The invariant the original case protected is still protected**, and that
    is why this is an amendment and not a deletion: a unit is on AT MOST ONE
    route for a given service, before and after. What changed is the mechanism
    — the second route WINS and the first loses the member, instead of the
    second write failing. `moved_from` records where it came from so the audit
    can explain it (`test_cr006_routes_cycles.py` asserts that half).
    """
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        unit = make_unit(dana, premise["id"], label="Unit A")
        first = services.create_route(
            dana, {"code": "Route 1", "members": [{"unit_id": unit["id"]}]}
        )
        second = services.create_route(
            dana, {"code": "Route 2", "members": [{"unit_id": unit["id"]}]}
        )
        assert selectors.route_members(first["id"]) == []
        assert [m["unit_id"] for m in selectors.route_members(second["id"])] == [str(unit["id"])]
        assert (
            models.RouteMembership.objects.filter(tenant_id=brazos.id, unit_id=unit["id"]).count()
            == 1
        )


def test_us_met_006_tc4__deactivated_route_keeps_its_history(brazos, dana):
    with tenant_ctx(brazos):
        route = services.create_route(dana, {"code": "Route 4", "route_type": "drive"})
        result = services.deactivate_route(dana, route["id"])
        listed = {r["code"]: r for r in selectors.routes_list(filters={"status": "active"})}
    assert result["status"] == "inactive"
    assert "Route 4" not in listed  # hidden from active pickers, row intact


def test_us_met_006_tc5__delete_blocked_while_the_route_has_members(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        unit = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        route = services.create_route(
            dana, {"code": "Route 1", "members": [{"unit_id": unit["id"]}]}
        )
        with pytest.raises(errors.BizError) as caught:
            services.delete_route(dana, route["id"])
        assert models.Route.objects.filter(pk=route["id"]).exists()
    assert caught.value.br_ref == "BR-MET-008" and caught.value.code == errors.BIZ_LOCKED
    assert caught.value.params["alternative"] == "deactivate"


def test_us_met_006_tc6__a_backwards_window_CANNOT_BE_EXPRESSED_ANY_MORE(brazos, dana):
    """⚠ **TC-6 ASSERTED A REFUSAL AND THE FAILURE MODE NO LONGER EXISTS
    (CR-029 D2, W5-T2).**

    US-MET-006 TC-6 is *"window start after end is blocked"* — a real guard over
    two stored DATES a person typed independently, which could disagree.
    metering 0021 dropped both columns: the read window is `start_day` + a
    LENGTH (`days_to_complete ≥ 1`), so a window that ends before it begins
    cannot be stated, let alone stored. A validator that cannot fail is a
    guarantee a reader will believe (hard-won law 1), so `_check_cycle_window`
    is deleted rather than kept as a no-op.

    This test is INVERTED rather than removed: it now proves the impossibility
    the deletion rests on, so a lane that re-adds a stored date pair has to
    argue with a red test first. **BR-MET-009's window clause needs amending and
    that is REPORTED, not decided here.**
    """
    with tenant_ctx(brazos):
        # The old TC-6 payload, sent whole. It is ACCEPTED and IGNORED — see
        # `services._ACCEPTED_LEGACY_SCHEDULE_FIELDS` for why refusing a caller
        # over a field it is entitled to think exists buys nothing.
        created = seed_cycle(
            dana,
            "09-B",
            window_start="2026-09-06",
            window_end="2026-09-02",
            bill_day=10,
            start_day=6,
            days_to_complete=3,
        )
        assert models.Cycle.objects.filter(tenant=brazos).count() == 1
    # And what it HOLDS is a window that runs forwards, from the ruled fields.
    assert created["start_day"] == 6 and created["days_to_complete"] == 3
    start = date.fromisoformat(created["window_start"])
    end = date.fromisoformat(created["window_end"])
    assert end > start
    # A zero-or-negative length is the one way left to say "backwards", and it
    # is refused by name.
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            seed_cycle(dana, "09-B2", start_day=6, days_to_complete=0)
    assert caught.value.field_errors[0]["message_key"] == "metering.cycle.days_to_complete_range"


def test_us_met_006_tc7__the_bill_day_may_not_fall_before_the_window_closes(brazos, dana):
    """⚠ **TC-7 MOVED WITH THE COLUMNS (W5-T2), AND THE RULE SURVIVED.**

    It read *"bill date inside the window is blocked"* — `bill_date <
    window_end`, over two dropped columns. The same rule in the generation D9
    kept: the cycle's BILL DAY may not fall before the day its derived window
    CLOSES (`start_day + days_to_complete - 1`). A cycle reading the 1st–5th
    cannot bill on the 3rd, which is what TC-7 has always been about.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            seed_cycle(dana, "09-C", start_day=1, days_to_complete=5, bill_day=3)
    assert caught.value.field_errors[0]["message_key"] == "metering.cycle.bill_day_before_read"


def test_us_met_006_tc8__clerk_is_denied_server_side(brazos, marcus):
    """US-MET-006 TC-8: the tab shows disabled-with-reason; a direct API call
    is rejected 403 (BR-MET-035, server-enforced)."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError) as caught:
            services.create_route(marcus, {"code": "Route 6"})
    assert caught.value.code == errors.AUTH_PERMISSION_DENIED
    response = api_call(
        api.routes,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        data={"code": "Route 6"},
    )
    assert response.status_code == 403


def test_us_met_006_tc9__cycle_delete_blocked_while_routes_reference_it(brazos, dana):
    with tenant_ctx(brazos):
        cycle = seed_cycle(dana, "08-A")
        services.create_route(dana, {"code": "Route 1", "cycle_id": cycle["id"]})
        with pytest.raises(errors.BizError) as caught:
            services.delete_cycle(dana, cycle["id"])
        assert models.Cycle.objects.filter(pk=cycle["id"]).exists()
    assert caught.value.br_ref == "BR-MET-009" and caught.value.params["routes"] == 1


def test_us_met_006_tc13__due_days_must_not_be_negative(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            seed_cycle(dana, "09-D", due_days=-1)
    assert caught.value.field_errors[0]["field"] == "due_days"


@pytest.mark.isolation
def test_us_met_006_tc10__isolation_codes_collide_across_tenants(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        seed_cycle(dana, "09-A", window_start="2026-09-01", window_end="2026-09-05", bill_day=8)
        services.create_route(dana, {"code": "Route 5"})
    with tenant_ctx(lonestar):
        seed_cycle(erin, "09-A", window_start="2026-09-01", window_end="2026-09-05", bill_day=8)
        services.create_route(erin, {"code": "Route 5"})  # per-tenant uniqueness
        assert [r["code"] for r in selectors.routes_list()] == ["Route 5"]
        assert len(selectors.cycles_list()) == 1


# ── US-MET-005 · S26/S27 operational tabs ───────────────────────────────────
def test_us_met_005_tc1__routes_tab_renders_membership_derived_meters(brazos, dana):
    with tenant_ctx(brazos):
        cycle = seed_cycle(dana, "08-A")
        premise = make_premises(dana)
        unit = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        make_asset(
            dana,
            asset_no="M-7001",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-08-01",
        )
        services.create_route(
            dana,
            {
                "code": "Route 1",
                "name": "Katy Central",
                "route_type": "ami",
                "feeder_ref": "F-01",
                "cycle_id": cycle["id"],
                "members": [{"unit_id": unit["id"]}],
            },
        )
        rows = selectors.routes_list()
    row = rows[0]
    assert row["meters"] == 1  # derived from the BR-MET-033 membership
    assert row["assigned_to"] is None  # US-MET-005 §5: renders "System (auto-pull)"
    # BR-MET-011: collected/progress DERIVE from committed reads. Until the
    # W2 reads lane landed (2026-08-10) the seam was unwired and these rendered
    # null, because "no meter_reads table" and "zero reads collected" are
    # different claims. `meter_reads` now exists, so a real count is available
    # and 0 is the TRUE answer for a route with no reads yet — the honesty this
    # assertion protects is unchanged, its subject moved from "unknown" to
    # "measured". Original null-posture assertion is preserved just below so a
    # reviewer can see exactly what changed and why.
    # never a fabricated 0.
    assert row["collected"] == 0  # measured, not fabricated: no reads exist yet
    assert row["progress"] == 0
    assert row["last_completion"] is None  # still null — no read has ever landed


def test_us_met_005_tc2__cycles_tab_shows_window_bill_date_and_expected(brazos, dana):
    with tenant_ctx(brazos):
        cycle = seed_cycle(dana, "08-A")
        premise = make_premises(dana)
        unit = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        make_asset(
            dana,
            asset_no="M-7001",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-08-01",
        )
        services.create_route(
            dana, {"code": "Route 1", "cycle_id": cycle["id"], "members": [{"unit_id": unit["id"]}]}
        )
        row = selectors.cycles_list()[0]
    assert row["routes"] == ["Route 1"]
    # ⚠ W5-T2 — the two window keys are UNCHANGED and their source moved. They
    # are derived from start day 1 + 5 days in the tenant's own month, so the
    # tab renders a five-day window opening on the 1st rather than the stored
    # August dates it used to. ⚠ **`bill_date` STOPPED BEING A COLUMN TOO
    # (RC-W6 / OQ-344)** and is derived the same way — from the bill DAY and the
    # cycle's next period — so its DAY is what is asserted below.
    start = date.fromisoformat(row["window_start"])
    end = date.fromisoformat(row["window_end"])
    assert start.day == 1
    assert (end - start).days == 4  # 5 days INCLUSIVE
    assert row["read_window_source"] == "derived"
    assert row["bill_date"].endswith("-08")
    assert row["bill_day"] == 8
    # collected is now MEASURED (the W2 reads lane wired the seam); it was null
    # while `meter_reads` did not exist. expected/status are unchanged.
    assert row["expected"] == 1 and row["collected"] == 0 and row["status"] == "scheduled"


def test_us_met_005_tc4__ops_tabs_expose_no_write_verb(brazos, dana):
    """BR-MET-011: S26/S27 are read-only — all CRUD lives in Settings."""
    with tenant_ctx(brazos):
        seed_cycle(dana, "08-A")
    read = api_call(api.routes, "get", user=FakeUser(), role="billing_clerk", tenant=brazos)
    assert read.status_code == 200
    denied = api_call(
        api.routes, "post", user=FakeUser(), role="billing_clerk", tenant=brazos, data={"code": "X"}
    )
    assert denied.status_code == 403


def test_us_met_005_tc5__unknown_cycle_id_is_a_lawful_not_found(brazos):
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            selectors.route_detail("not-a-uuid")
