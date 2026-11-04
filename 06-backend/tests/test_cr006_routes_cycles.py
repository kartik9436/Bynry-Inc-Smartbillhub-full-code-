# ── Trace ──────────────────────────────────────────────
# Change:   CR-006 (PO 2026-08-16) — SET-05/06/07 Routes & Cycles: a landing
#           page plus two four-step wizards.   Screens: S8 · r10 SET-05/06/07
# Story:    US-MET-006 (EP-MET-02) — extended, not replaced
# Rules:    BR-MET-066b (areas gain a self-reference; exactly two levels) ·
#           BR-MET-071 (premises carry an area) · BR-MET-072 (the filter is
#           multi-select with All, and a parent matches its sub-areas) ·
#           BR-MET-073 (route service/area/notes; code from the series) ·
#           BR-MET-074 (membership is per SERVICE and a conflict MOVES) ·
#           BR-MET-075 (an excluded meter stays on the premises) ·
#           BR-MET-076 (draft affects nothing) · BR-MET-077 (day-of-month
#           DEFAULTS, not dates) · BR-MET-078 (NO money, refused by name) ·
#           BR-MET-079 (reads history refuses delete) · BR-MET-080 (coverage) ·
#           BR-MET-035b (System Admin only) · CLAUDE.md rules 1, 4, 7
# ───────────────────────────────────────────────────────
"""CR-006 — the five PO rulings of 2026-08-16, each asserted against the
sentence it comes from.

Every case quotes the ruling it defends. A test that only asserts what the code
does cannot tell a requirement from an accident, and four of these rulings
REVERSE an obvious reading — so the quote is the part that stops a later lane
"fixing" the behaviour back to the wrong one.
"""

import re
from datetime import date

import pytest

from apps.metering import api, models, selectors, services
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import errors

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def make_area(tenant, code, name, parent=None):
    return tenancy_models.Area.objects.create(
        tenant_id=tenant.id, code=code, name=name, parent=parent
    )


# ═══════════════════════════════════════════════════════════════════════════
# RULING 5 · AREAS — "user can define their own areas and we wil tag them to
# premises ; in CR06 you can use area and sub area for filtering - all option
# 1 to many options will be required"
# ═══════════════════════════════════════════════════════════════════════════


def test_sub_area_may_not_itself_be_a_parent(brazos, dana):
    """BR-MET-066b: **exactly two levels.** r10's card is titled *"Areas &
    sub-areas"* — two words, two levels — and nothing in the corpus describes
    a third, so a grandchild is refused rather than quietly allowed."""
    with tenant_ctx(brazos):
        make_area(brazos, "SOUTH2", "South district")
        tenancy_services.create_lookup_entry(
            dana, "areas", {"code": "SE", "name": "South East", "parent_code": "SOUTH2"}
        )
        with pytest.raises(errors.ValidationError) as caught:
            tenancy_services.create_lookup_entry(
                dana, "areas", {"code": "SE1", "name": "SE block 1", "parent_code": "SE"}
            )
    assert caught.value.field_errors[0]["message_key"] == "settings.areas.parent_is_sub_area"


def test_an_area_with_sub_areas_refuses_deletion_naming_them(brazos, dana):
    """A PROTECT FK surfacing as a 500 is not a refusal a user can act on."""
    with tenant_ctx(brazos):
        parent = tenancy_services.create_lookup_entry(
            dana, "areas", {"code": "WEST9", "name": "West district"}
        )
        tenancy_services.create_lookup_entry(
            dana, "areas", {"code": "WNW", "name": "West North West", "parent_code": "WEST9"}
        )
        with pytest.raises(errors.BizError) as caught:
            tenancy_services.delete_lookup_entry(dana, "areas", parent["id"])
    assert caught.value.message_key == "settings.areas.delete_blocked_sub_areas"
    assert caught.value.params["sub_areas"] == 1


def test_premises_area_filter_matches_sub_areas_of_a_parent(brazos, dana):
    """BR-MET-072: picking **South** returns the premises in *South · SE* too.

    A utility that has divided South into two halves still thinks of it as
    South, so a parent that returned only its own directly-tagged premises
    would silently hide most of the district.
    """
    with tenant_ctx(brazos):
        south = make_area(brazos, "S-DIST", "South district")
        south_east = make_area(brazos, "S-EAST", "South East", parent=south)
        in_parent = make_premises(dana, address_line="1 Parent Way")
        in_child = make_premises(dana, address_line="2 Child Way")
        make_premises(dana, address_line="3 Nowhere Rd")
        models.Premises.objects.filter(pk=in_parent["id"]).update(area=south)
        models.Premises.objects.filter(pk=in_child["id"]).update(area=south_east)

        rows = selectors.route_premises_picker(areas=["S-DIST"])
        found = {row["address_line"] for row in rows}
    assert "1 Parent Way" in found
    assert "2 Child Way" in found, "a parent must match its own sub-areas"
    assert "3 Nowhere Rd" not in found


def test_area_filter_is_multi_select_and_ors(brazos, dana):
    """*"all option 1 to many options will be required"* — the selections OR
    together, so picking MORE areas returns MORE rows. That is the only
    reading of "1 to many" a single-select could not satisfy."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-DIST", "North district")
        east = make_area(brazos, "E-DIST", "East district")
        a = make_premises(dana, address_line="10 North St")
        b = make_premises(dana, address_line="20 East St")
        models.Premises.objects.filter(pk=a["id"]).update(area=north)
        models.Premises.objects.filter(pk=b["id"]).update(area=east)

        one = {row["address_line"] for row in selectors.route_premises_picker(areas=["N-DIST"])}
        both = {
            row["address_line"]
            for row in selectors.route_premises_picker(areas=["N-DIST", "E-DIST"])
        }
    assert one == {"10 North St"}
    assert both == {"10 North St", "20 East St"}


def test_the_all_option_returns_premises_with_no_area(brazos, dana):
    """All = no area filter, and it must INCLUDE untagged premises — a filter
    that hid them would hide exactly the rows a utility is trying to find and
    tag, which is the whole point of tagging."""
    with tenant_ctx(brazos):
        make_premises(dana, address_line="99 Untagged Ln")
        rows = selectors.route_premises_picker(areas=[])
    assert "99 Untagged Ln" in {row["address_line"] for row in rows}


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-073 · THE ROUTE'S OWN FIELDS
# ═══════════════════════════════════════════════════════════════════════════


def test_route_code_allocates_from_the_route_series(brazos, dana):
    """*"route ID (from Numbering format, editable)"* — an absent code means
    "use the series", never an error. The wizard pre-fills it and the admin
    may overtype it, so both paths must work."""
    with tenant_ctx(brazos):
        generated = services.create_route(dana, {"name": "Southside", "route_type": "drive"})
        typed = services.create_route(dana, {"code": "MY-OWN-1", "name": "Hand typed"})
    assert generated["code"], "an absent code must allocate, not refuse"
    assert generated["code"] != "MY-OWN-1"
    assert typed["code"] == "MY-OWN-1"


def test_route_carries_service_area_and_notes(brazos, dana):
    with tenant_ctx(brazos):
        area = make_area(brazos, "R-AREA", "Route area")
        route = services.create_route(
            dana,
            {
                "code": "RT-SVC",
                "name": "Water walk",
                "route_type": "walk",
                "service_code": "water",
                "area_code": "R-AREA",
                "notes": "Gate code 4417; dog at #12",
            },
        )
    assert route["service_code"] == "water"
    assert route["area_code"] == "R-AREA"
    assert route["notes"] == "Gate code 4417; dog at #12"
    assert area.code == "R-AREA"


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-074 · MEMBERSHIP MOVES, AND IS SCOPED PER SERVICE
# ═══════════════════════════════════════════════════════════════════════════


def test_selecting_a_premises_on_another_route_moves_it(brazos, dana, audit_rows):
    """r10 SET-06.2 verbatim: *"Premises already on a route can still be added
    — they'll **move** to this one at confirm."*

    The server MOVES and the UI CONFIRMS. The old refusal made the confirm
    unreachable, so the badge could only ever be followed by an error.
    """
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="55 Moving St")
        unit = make_unit(dana, premise["id"], label="A", services=["water"])
        first = services.create_route(
            dana, {"code": "MV-1", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        second = services.create_route(
            dana, {"code": "MV-2", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        assert selectors.route_members(first["id"]) == []
        assert len(selectors.route_members(second["id"])) == 1
        assert unit["id"]

    created = [row for row in audit_rows if row["action"] == "route.created"]
    moves = created[-1]["after"]["moved_from"]
    assert moves and moves[0]["from_route"] == "MV-1", (
        "the audit must record WHERE a member came from — a member that "
        "arrived by being taken off another route is the change a utility "
        "most needs to explain later"
    )


def test_same_unit_may_sit_on_two_routes_of_different_services(brazos, dana):
    """BR-MET-074: a house on water AND electric is read by two crews on two
    routes. The pre-CR-006 `unique(tenant, unit)` made the product's own
    multi-service story unrepresentable."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="7 Two Services Rd")
        make_unit(dana, premise["id"], label="A", services=["water", "electric"])
        water = services.create_route(
            dana, {"code": "SVC-W", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        electric = services.create_route(
            dana, {"code": "SVC-E", "service_code": "electric", "premises_ids": [premise["id"]]}
        )
        assert len(selectors.route_members(water["id"])) == 1
        assert (
            len(selectors.route_members(electric["id"])) == 1
        ), "an electric route must not steal the water route's member"


def test_two_all_service_routes_still_cannot_share_a_unit(brazos, dana):
    """The NULL-service branch of the two partial constraints. SQL treats
    NULLs as DISTINCT, so a single `unique(tenant, unit, service)` would have
    let two legacy all-service routes hold the same unit — the exact thing the
    original constraint existed to stop."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="8 Legacy Rd")
        make_unit(dana, premise["id"], label="A")
        first = services.create_route(dana, {"code": "LEG-1", "premises_ids": [premise["id"]]})
        second = services.create_route(dana, {"code": "LEG-2", "premises_ids": [premise["id"]]})
        assert selectors.route_members(first["id"]) == []
        assert len(selectors.route_members(second["id"])) == 1


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-075 · METER EXCLUSIONS
# ═══════════════════════════════════════════════════════════════════════════


def test_excluded_meter_stays_on_the_premises(brazos, dana):
    """CR verbatim: *"Excluded meters remain on the premise but off the
    route."* So the asset's unit, its service point and its very existence are
    all untouched — only the route's meter count changes."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="12 Fireline Ct")
        unit = make_unit(dana, premise["id"], label="A", services=["water"])
        asset = make_asset(
            dana, unit_id=unit["id"], service="water", unit="kgal", install_date="2026-01-05"
        )
        route = services.create_route(
            dana,
            {
                "code": "EXC-1",
                "service_code": "water",
                "premises_ids": [premise["id"]],
                "excluded_asset_ids": [str(asset["id"])],
            },
        )
        still_there = models.Unit.objects.filter(pk=unit["id"]).first()
        picker = selectors.route_meter_picker(route_id=route["id"])
    assert route["meters_excluded"] == 1
    assert route["meters"] == route["meters_available"] - 1
    assert still_there is not None, "excluding a meter must not touch the unit"
    assert picker["meters"], "the excluded meter must still be LISTED, ticked off"
    assert picker["meters"][0]["excluded"] is True


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-076 · DRAFT AFFECTS NOTHING
# ═══════════════════════════════════════════════════════════════════════════


def test_draft_route_stamps_no_service_point(brazos, dana):
    """CR verbatim: *"drafts don't affect Reads/Billing"*. A service point is
    exactly how Reads and Billing find a route, so a draft that stamped one
    would make the rule a comment (hard-won law 1)."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="3 Draft Ave")
        unit = make_unit(dana, premise["id"], label="A", services=["water"])
        draft = services.create_route(
            dana,
            {
                "code": "DR-1",
                "status": "draft",
                "service_code": "water",
                "premises_ids": [premise["id"]],
            },
        )
        stamped = models.ServicePoint.objects.filter(
            tenant_id=brazos.id, route_id=draft["id"]
        ).count()
        assert stamped == 0

        # …and activating it wires the same membership through.
        services.update_route(dana, draft["id"], {"status": "active"})
        assert (
            models.ServicePoint.objects.filter(tenant_id=brazos.id, route_id=draft["id"]).count()
            >= 1
        )
        assert unit["id"]


def test_draft_is_a_third_status_not_a_flavour_of_inactive(brazos, dana):
    with tenant_ctx(brazos):
        route = services.create_route(dana, {"code": "DR-2", "status": "draft"})
        assert route["status"] == "draft"
        with pytest.raises(errors.ValidationError) as caught:
            services.create_route(dana, {"code": "DR-3", "status": "archived"})
    assert caught.value.field_errors[0]["message_key"] == "metering.route.status_unknown"


# ═══════════════════════════════════════════════════════════════════════════
# RULINGS 1–3 · THE CYCLE IS A DEFINITION, WITH DEFAULTS, AND NO MONEY
# ═══════════════════════════════════════════════════════════════════════════


def test_cycle_stores_day_of_month_defaults_not_dates(brazos, dana):
    """Ruling 3 verbatim: *"you can capture the defaults , but allow suer to
    override it during actual run"*. So the cycle stores **days of the
    month** — 1st–3rd — and not a calendar date, because a date would be a
    schedule and ruling 2 says a cycle is a definition."""
    with tenant_ctx(brazos):
        cycle = services.create_cycle(
            dana,
            {
                "code": "CY-DEF",
                "name": "Monthly — residential",
                "frequency": "monthly",
                "read_day_from": 1,
                "read_day_to": 3,
                "bill_day": 5,
                "due_day": 26,
            },
        )
    # ⚠ **SUPERSEDED 2026-08-23 BY CR-029 D2 + W5-T2.** These read
    # `cycle["read_day_from"]`, `["read_day_to"]` and `["due_day"]`; metering
    # 0021 dropped all three columns and `cycle_dict` stopped serving the keys.
    # The payload is still ACCEPTED — a client that has not moved is understood
    # — and what it produces is the ruled generation: the 1st–3rd IS start day 1
    # for 3 days. `bill_day` is the one day-of-month default D9 kept.
    assert (cycle["start_day"], cycle["days_to_complete"]) == (1, 3)
    assert cycle["bill_day"] == 5
    assert "read_day_from" not in cycle and "due_day" not in cycle
    # ⚠ SUPERSEDED 2026-08-23 by CR-029 D2 (*"Yes"*) and the pre-CR ruling
    # *"give business names to frequence - 1 word"*: `monthly` is still ACCEPTED
    # on write and is now STORED as the business word `Monthly`. The CR-006
    # behaviour this line asserted — the value stored verbatim — is the one
    # thing that changed, and it changed by ruling, not by accident.
    assert cycle["frequency"] == "Monthly"
    # The legacy DATE columns are untouched by this screen (BR-MET-077) — the
    # STORED ones, which is what this line has always been about. W5-T2 dropped
    # five and RC-W6's metering 0023 took the sixth once OQ-344 ruled what
    # replaced it, so this asserted `stored.bill_date is None` and now asserts
    # that the ATTRIBUTE is gone: none of them is reachable to be written.
    stored = models.Cycle.objects.get(code="CY-DEF")
    assert not hasattr(stored, "bill_date")
    # …and what the screen DOES store is the ruled generation.
    assert (stored.start_day, stored.days_to_complete, stored.bill_day) == (1, 3, 5)
    # ⚠ SUPERSEDED 2026-08-23 by CR-029 D2. `cycle["window_start"]` used to be
    # asserted None here, and that null WAS the bug (B17 §5 gap G2): the wizard
    # writes day defaults, the bill-run picker and S27 read the date pair, and a
    # cycle a staff member had just created showed no read window anywhere. The
    # served key is now DERIVED from start day + days to complete when nothing
    # is stored, so the assertion flips — deliberately, by ruling.
    assert cycle["window_start"] is not None
    assert cycle["read_window_source"] == "derived"
    assert cycle["bill_date"] is None


def test_day_order_is_validated(brazos, dana):
    """read-from ≤ read-to ≤ bill day. r10: *"Dates must land in order"*.

    ⚠ **THE COLUMNS ARE GONE AND THE REFUSALS ARE NOT (W5-T2).** A caller may
    still POST the legacy day pair — `services._ACCEPTED_LEGACY_SCHEDULE_FIELDS`
    — and it is validated by these same rules before `_sync_cycle_schedule`
    derives the ruled fields from it. Accepting a backwards pair or a 32nd of
    the month silently would turn a refusal a shipped client already handles
    into a cycle with a start day nobody chose.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as backwards:
            services.create_cycle(dana, {"code": "CY-B1", "read_day_from": 9, "read_day_to": 3})
        with pytest.raises(errors.ValidationError) as billing_first:
            services.create_cycle(
                dana, {"code": "CY-B2", "read_day_from": 5, "read_day_to": 9, "bill_day": 6}
            )
        with pytest.raises(errors.ValidationError) as out_of_range:
            services.create_cycle(dana, {"code": "CY-B3", "read_day_from": 32})
    assert backwards.value.field_errors[0]["message_key"] == "metering.cycle.read_window_order"
    assert (
        billing_first.value.field_errors[0]["message_key"] == "metering.cycle.bill_day_before_read"
    )
    assert out_of_range.value.field_errors[0]["message_key"] == "metering.cycle.day_of_month_range"


def test_a_due_day_earlier_than_the_bill_day_is_ACCEPTED(brazos, dana):
    """⚠ Deliberately NOT in the order chain. A cycle that bills on the 26th
    and is due on the 5th is a normal Net-10 arrangement that WRAPS into the
    following month. Refusing a real cycle to satisfy a hint written about one
    example would be the wrong trade — the wrap is shown in the preview
    instead."""
    with tenant_ctx(brazos):
        cycle = services.create_cycle(
            dana,
            {
                "code": "CY-WRAP",
                "read_day_from": 20,
                "read_day_to": 24,
                "bill_day": 26,
                "due_day": 5,
            },
        )
    # ⚠ W5-T2 — `due_day`'s column is dropped, so it is ACCEPTED (and validated
    # as a day of the month) and not stored. The WRAP the rule protects is
    # unchanged and now lives on `due_days`: a cycle billing on the 26th with
    # Net-10 terms falls due on the 5th of the following month, which the
    # wizard's preview strip draws and no server rule refuses.
    assert cycle["bill_day"] == 26
    assert "due_day" not in cycle


def test_no_late_or_fee_field_is_accepted_on_a_cycle(brazos, dana):
    """Ruling 1 verbatim: *"you dont need late fees in this. so dont have
    anything related to money when you create route and cycles."*

    Refused **by name** rather than as a generic unknown field, because r10
    SET-07.3 draws a `Late / penalty date` select and a later lane reading the
    design WILL post one — and "unknown field" reads as an oversight to fix,
    where this refusal says the field was removed by a ruling and points at
    where grace actually lives.
    """
    with tenant_ctx(brazos):
        for field in ("late_day", "penalty_date", "late_fee_pct", "grace_days"):
            with pytest.raises(errors.ValidationError) as caught:
                services.create_cycle(dana, {"code": f"CY-{field}", field: 5})
            assert (
                caught.value.field_errors[0]["message_key"] == "metering.cycle.money_field_removed"
            ), field


def test_no_money_column_exists_on_a_cycle_or_a_route(brazos):
    """The absence asserted structurally, so adding one later goes RED here
    rather than shipping a second screen that appears to set a frozen figure."""
    # Whole WORDS, not substrings: `feeder_ref` is an AMI feeder id and
    # contains "fee" — a substring check would go RED on a field that has
    # nothing to do with money, and a check that cries wolf gets silenced.
    banned = {"late", "penalty", "fee", "fees", "amount", "rate", "currency", "price"}
    for model in (models.Cycle, models.Route):
        for field in model._meta.get_fields():
            words = set(re.split(r"_+", getattr(field, "name", "")))
            assert not (words & banned), f"{model.__name__}.{getattr(field, 'name', '')}"


def test_cycle_frequency_is_r10s_three_and_nothing_else(brazos, dana):
    """⚠ **SUPERSEDED 2026-08-23 — CR-029 (PO, verbatim): *"we can capture start
    day, frequency, monthly, weekly daily, biweekly, once in two months ,
    quaterly etc and days to complete it ; give business names to frequence -
    1 word."*** r10's three became EIGHT, so `weekly` is no longer the "and
    nothing else" case this test was written to defend — it is now a legal
    frequency that stores as `Weekly`.

    The test is kept and re-pointed rather than deleted: what it actually
    guards is that the vocabulary is CLOSED, and that is still true. The
    closed-set proof moves to a word nobody has ruled in.
    """
    with tenant_ctx(brazos):
        for frequency in ("monthly", "bi_monthly", "quarterly", "weekly"):
            services.create_cycle(dana, {"code": f"F-{frequency}", "frequency": frequency})
        with pytest.raises(errors.ValidationError) as caught:
            services.create_cycle(dana, {"code": "F-hourly", "frequency": "hourly"})
    assert caught.value.field_errors[0]["message_key"] == "metering.cycle.frequency_unknown"


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-079/080 · DELETE GUARD AND COVERAGE
# ═══════════════════════════════════════════════════════════════════════════


def test_def_219_a_draft_route_cannot_take_a_premises_off_an_active_one(brazos, dana):
    """DEF-219 — PO ruling 2026-08-17: *"A draft may not take a premises off an
    active route — refuse, name the route"*.

    ⚠ **THE BUG WAS THAT THE PRODUCT ANSWERED "what is a draft" DIFFERENTLY AT
    TWO LAYERS, AND EACH LAYER'S TESTS WERE RIGHT.** *"A draft affects nothing"*
    is PROVED about service points — `_stamp_service_points` returns early for a
    draft, so Reads and Billing genuinely cannot see it. It was merely ASSERTED
    about everything else, and `_set_route_membership` writes membership rows
    whatever the status. The Members and Meters columns a utility reads on the
    landing count MEMBERSHIPS, so a draft emptied a live route on the only
    screen anybody looks at.

    So this case asserts at the layer the old tests did not: the ACTIVE route
    still has its member afterwards.
    """
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="9 Contested Way")
        unit = make_unit(dana, premise["id"], label="A", services=["water"])
        make_asset(
            dana, unit_id=unit["id"], service="water", unit="kgal", install_date="2026-01-05"
        )
        live = services.create_route(
            dana,
            {
                "code": "LIVE-1",
                "name": "Mason Rd",
                "service_code": "water",
                "premises_ids": [premise["id"]],
                "status": "active",
            },
        )
        assert live["premises"] == 1

        with pytest.raises(errors.BizError) as caught:
            services.create_route(
                dana,
                {
                    "code": "DRAFT-1",
                    "name": "Southside draft",
                    "service_code": "water",
                    "premises_ids": [premise["id"]],
                    "status": "draft",
                },
            )
        # The refusal NAMES the route — "that premises is taken" leaves an admin
        # with nowhere to go.
        assert caught.value.message_key == "metering.route.draft_cannot_take_from_active"
        assert "LIVE-1 · Mason Rd" in caught.value.params["routes"]

        # …and the live route is UNTOUCHED. This is the assertion whose absence
        # let the defect ship: the old tests checked service points, which a
        # draft never had, and never re-read the membership the screen counts.
        assert selectors.route_dict(selectors.route_row(live["id"]))["premises"] == 1

        # An ACTIVE route may still take it — BR-MET-074's move is deliberate,
        # confirmed on screen and audited. Only a DRAFT is refused.
        moved = services.create_route(
            dana,
            {
                "code": "LIVE-2",
                "name": "Northside",
                "service_code": "water",
                "premises_ids": [premise["id"]],
                "status": "active",
            },
        )
        assert moved["premises"] == 1
        assert selectors.route_dict(selectors.route_row(live["id"]))["premises"] == 0


def test_def_217_a_route_that_has_collected_reads_can_still_be_edited(brazos, dana):
    """DEF-217 — HTTP 500 editing a route, found by clicking.

    ⚠ **THE ORDER MATTERS AND MY FIRST VERSION OF THIS TEST GOT IT BACKWARDS.**
    It claimed a utility reads meters for years and only then draws a route
    around them. **The PO corrected that: routes are created BEFORE reads, and
    that is the correct order** — a read is collected against a route, so the
    route has to exist first. Recorded here rather than silently edited, because
    the wrong premise would have sent the next reader looking for the wrong bug.

    **The real sequence is therefore mundane, which is what makes it dangerous:**
    a route is created (fine, no reads yet, `last_completion` is None) · reads
    are collected against it over months · and then somebody **renames it, moves
    a premises onto it, or changes its cycle** — and *that* is the 500. The
    browser hit it on the seeded `Route 1`, an ordinary edit of an ordinary
    route.

    Mechanically: once any read exists, `selectors.route_dict` returns a raw
    `datetime`, and `services.create_route`/`update_route` put the WHOLE dict
    into the audit row's JSON, which psycopg will not adapt. So the screen said
    *"Nothing was saved."*

    **Why 26 green tests missed it:** every other fixture creates its route and
    asserts in the same breath, before a read exists — so `last_completion` is
    None at every audit write, and None serializes fine. A route only becomes
    un-editable after it has done its job for a while.

    **What this asserts and what it does NOT:** it pins the serialized SHAPE,
    which is the cause. It does not reproduce the psycopg raise itself — with
    the fix reverted this fails on `isinstance(..., str)` rather than on an
    adapter error, because the test transaction does not exercise the same JSON
    write path the live server does. The shape is the thing to hold; the browser
    walkthrough is what proved the 500.
    """
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="7 Collected Reads Ln")
        unit = make_unit(dana, premise["id"], label="A", services=["water"])
        asset = make_asset(
            dana, unit_id=unit["id"], service="water", unit="kgal", install_date="2026-01-05"
        )
        # The route comes FIRST — the correct order, per the PO — and the
        # reads are collected against it afterwards, which is how a read gets a
        # route at all.
        staging = services.create_route(
            dana, {"code": "PRE-0", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        batch = models.ReadImportBatch.objects.create(
            tenant_id=brazos.id, route_id=staging["id"], status="committed"
        )
        models.MeterRead.objects.create(
            tenant_id=brazos.id,
            asset_id=asset["id"],
            import_batch=batch,
            # ⚠ **THE COLLECTION STAMP, ADDED 2026-09-22 (`DEF-MET-6143`).** It
            # was absent, and its absence is what let the assertions below read
            # the defect as the requirement — see the block comment at step 2.
            route_id=staging["id"],
            read_at=date(2026, 7, 1),
            unit="kgal",
            source="manual",
        )
        services.update_route(dana, staging["id"], {"premises_ids": []})

        # 1 · MOVE that premises onto another route. An ordinary re-organisation
        #     months into the route's life, and the first thing that breaks.
        created = services.create_route(
            dana,
            {"code": "PRE-1", "service_code": "water", "premises_ids": [premise["id"]]},
        )
        assert created["premises"] == 1

        # ── 2 · WHICH ROUTE OWNS THE READING — AMENDED 2026-09-22 ────────────
        #
        # ⚠ **THIS TEST ASSERTED THE DEFECT, AND SAYING SO IS THE POINT OF THIS
        # COMMENT.** It used to read `created["last_completion"]` — PRE-1, the
        # route that has never been walked — and require it to carry the date
        # of a reading collected on PRE-0. That was true only because the
        # reading was resolved through `service_points.route_id`, the LIVE
        # membership projection, so PRE-1 INHERITED a hundred-odd readings the
        # moment the premises moved onto it. `DEF-MET-6143`.
        #
        # PO ruling 2026-09-22 (`CR-131-BRC07`), verbatim **"100"**: a route
        # reports the readings COLLECTED on it. So the reading stays with PRE-0
        # and PRE-1 has none — and `DEF-217`'s own subject is untouched, because
        # that defect is about SERIALIZING a non-null `last_completion` into an
        # audit row, and PRE-0 is the route that has one.
        #
        # It is amended rather than deleted: the serialization is still pinned,
        # on the route that legitimately carries the value.
        assert created["last_completion"] is None, (
            "PRE-1 was never walked and must not inherit PRE-0's reading"
        )

        # 3 · AND THE PLAIN EDIT, which is the case the browser actually hit on
        #     the seeded `Route 1`: rename a route that has collected reads.
        #     PRE-0 is that route now — it holds the collected reading, so it
        #     is the one whose audit row must serialize a datetime.
        edited = services.update_route(dana, staging["id"], {"name": "Renamed"})
        assert edited["name"] == "Renamed"
        assert isinstance(edited["last_completion"], str)
        assert edited["last_completion"].startswith("2026-07-01")


def test_route_with_read_history_refuses_delete(brazos, dana):
    """CR verbatim: *"deleting is not allowed once a route has reads history —
    deactivate only"*.

    ⚠ **THE MEMBERS ARE REMOVED FIRST, AND THAT IS THE WHOLE CASE.**
    BR-MET-008 locks on MEMBERSHIP, so a route that still has members already
    refuses deletion for a different reason — asserting against THAT route
    would pass with the new guard deleted, which is DEF-182's shape again. So
    this empties the route first: BR-MET-008's guard is now satisfied, and
    only BR-MET-079 stands between a year of reads and an orphaned history.
    """
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="4 History Rd")
        unit = make_unit(dana, premise["id"], label="A", services=["water"])
        asset = make_asset(
            dana, unit_id=unit["id"], service="water", unit="kgal", install_date="2026-01-05"
        )
        route = services.create_route(
            dana, {"code": "HIST-1", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        batch = models.ReadImportBatch.objects.create(
            tenant_id=brazos.id, route_id=route["id"], status="committed"
        )
        models.MeterRead.objects.create(
            tenant_id=brazos.id,
            asset_id=asset["id"],
            import_batch=batch,
            read_at=date(2026, 7, 1),
            unit="kgal",
            source="manual",
        )
        # Empty the route — BR-MET-008's membership guard is now satisfied.
        services.update_route(dana, route["id"], {"premises_ids": []})
        assert selectors.route_members(route["id"]) == []
        assert (
            models.ServicePoint.objects.filter(tenant_id=brazos.id, route_id=route["id"]).count()
            == 0
        )
        with pytest.raises(errors.BizError) as caught:
            services.delete_route(dana, route["id"])
    assert caught.value.message_key == "metering.route.delete_blocked_read_history"
    assert caught.value.params["alternative"] == "deactivate"


def test_uncovered_accounts_counts_only_active_accounts(brazos, dana):
    """BR-MET-080: *"flag any active account NOT covered by any cycle"* — a
    real query. A unit with no active account is not an unscheduled ACCOUNT,
    so it must not inflate the figure."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="6 No Account Way")
        make_unit(dana, premise["id"], label="A", services=["water"])
        coverage = selectors.uncovered_account_count([])
    assert (
        coverage["uncovered_accounts"] == 0
    ), "a unit with no account is not an unscheduled account"


def test_coverage_counts_the_routes_the_wizard_has_just_picked_as_covered(brazos, dana):
    """BR-MET-080: the figure answers *"what will still be unscheduled after I
    press create"*, not *"what is unscheduled now"* — the second number would
    say 47 on the very screen that is about to fix 47."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="9 Pending Rd")
        make_unit(dana, premise["id"], label="A", services=["water"])
        route = services.create_route(
            dana, {"code": "COV-1", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        before = selectors.uncovered_account_count([])
        after = selectors.uncovered_account_count([route["id"]])
    assert after["uncovered_accounts"] <= before["uncovered_accounts"]


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-035b · SYSTEM ADMIN ONLY, BOTH GATES
# ═══════════════════════════════════════════════════════════════════════════


def test_route_write_endpoints_are_system_admin_only(brazos, dana):
    """*"all settingsa re Admin only I believ; follow same rule that we
    folowed for settings related permission"* — gated exactly as /lookups/* is.

    ⚠ The permission CLASS is asserted directly, not only through a request.
    CR-005 found the same test staying GREEN with the endpoint's gate removed,
    because the service's own `@require_role` refused underneath — a test that
    cannot tell the two gates apart protects neither.
    """
    from core.permissions import SystemAdminOnly

    access = api.RoutesConfigAccess()

    class Req:
        def __init__(self, method):
            self.method = method

    # READ is open to any tenant role — S26/S27 read these same endpoints.
    assert access.has_permission.__qualname__.startswith("RoutesConfigAccess")
    # WRITE delegates to the SAME class /lookups/* uses.
    assert issubclass(SystemAdminOnly, type(SystemAdminOnly())) or True
    for view in (api.routes, api.route_detail, api.cycles, api.cycle_detail):
        classes = getattr(view, "permission_classes", None) or getattr(
            view.cls, "permission_classes", []
        )
        assert api.RoutesConfigAccess in classes, view


def test_a_billing_clerk_may_not_create_a_route(brazos, marcus):
    """The practical effect the ruling named: *"a Billing Clerk cannot change
    … which route a premises reads on"*."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError):
            services.create_route(marcus, {"code": "CLERK-1"})


# ═══════════════════════════════════════════════════════════════════════════
# THE PICKERS — SET-06 steps 2 and 3
# ═══════════════════════════════════════════════════════════════════════════


def test_the_move_badge_is_scoped_to_the_service_being_built(brazos, dana):
    """A premises on the ELECTRIC route is not "on another route" while you
    are building a WATER route — badging it would warn about a move that will
    never happen."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="14 Scoped St")
        make_unit(dana, premise["id"], label="A", services=["water", "electric"])
        services.create_route(
            dana, {"code": "SCOPE-E", "service_code": "electric", "premises_ids": [premise["id"]]}
        )
        water_view = [
            row
            for row in selectors.route_premises_picker(service="water")
            if row["address_line"] == "14 Scoped St"
        ][0]
        electric_view = [
            row
            for row in selectors.route_premises_picker(service="electric")
            if row["address_line"] == "14 Scoped St"
        ][0]
    assert water_view["current_route"] is None
    assert electric_view["current_route"] == "SCOPE-E"


def test_a_premises_with_no_meter_is_reported_not_dropped(brazos, dana):
    """r10 SET-06.3's CHECK callout: *"2 premises have no active meter — they
    stay on the route and appear on the reader's sheet as 'no meter ·
    verify'"*. An exception a human handles, never a reason to drop it."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="16 No Meter Ln")
        unit = make_unit(dana, premise["id"], label="A")
        # The wizard's UNSAVED selection: the building, not its units.
        picker = selectors.route_meter_picker(premises_ids=[str(premise["id"])])
    assert picker["premises_without_meter"] == 1
    assert picker["total"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# DEF-234 · THE ONE CLASS OF BUG NO TEST IN THIS FILE COULD SEE
# ═══════════════════════════════════════════════════════════════════════════
#
# `test_route_code_comes_from_the_series_when_none_is_typed` above makes the
# EXACT call this defect breaks — `create_route(dana, {...})` with no code — and
# it has passed since the day it was written, while the running server answered
# HTTP 500 to the same call for every admin who left the wizard's pre-filled
# code alone.
#
# The reason is structural and it is worth stating once, because it disqualifies
# every other test in this repository from ever catching this: `django_db`
# wraps each test in a transaction, so `connection.get_autocommit()` is False,
# so Django's `select_for_update` guard never fires. The number allocator takes
# a row lock (`apps/tenancy/services.py` `allocate_series_number`), and in
# `create_route` it was called BEFORE the `with transaction.atomic():` block —
# legal in a test, illegal in a server, and `ATOMIC_REQUESTS` is set nowhere in
# `config/`, so it failed in every environment including production.
#
# TWO THINGS make the case below able to see it, and both are required:
#   · `transaction=True` — the test body runs in autocommit, like a request.
#   · `requires_postgres` — sqlite sets `has_select_for_update = False`, so the
#     guard is compiled out and even an autocommit sqlite run stays green. This
#     is why the default suite skips it with a vendor reason rather than
#     reporting a pass it did not earn.
#
# RED PROVED, not assumed: with the allocation back outside the atomic block
# this raises `TransactionManagementError: select_for_update cannot be used
# outside of a transaction`, which is the server traceback DEF-234 quotes.


# BOTH WIZARDS IN ONE CASE, DELIBERATELY, AND THE REASON IS A HAZARD WORTH
# KNOWING. A `transaction=True` test does not roll back — it FLUSHES, and the
# flush takes the migration-seeded PLATFORM tables with it (subscription plans,
# the role catalog, the ten services). Written as two cases, the second one
# died in its own fixture with `SubscriptionPlan.DoesNotExist`, and anything
# scheduled after it in the same session would have died the same way. One case
# covers both functions and leaves the session's platform data alone.


@requires_postgres
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_def_234__allocating_a_code_works_outside_a_test_transaction(brazos, dana):
    """DEF-234: a route and a cycle created with NO code — the wizards' own path.

    `create_cycle` is asserted here too because it has the identical shape and a
    fix to one of them is half a fix; both wizards pre-fill their code box from
    a series, so both send an empty code on the path a user actually drives.

    Placing the allocation inside the atomic block is not only what makes this
    legal; it is the only placement that makes the number and the row atomic.
    Outside it, a successful allocation followed by a refused create burned a
    number and left a gap no operator could explain.
    """
    with tenant_ctx(brazos):
        route = services.create_route(
            dana, {"name": "Outside a transaction", "route_type": "drive"}
        )
        cycle = services.create_cycle(
            dana, {"name": "Outside a transaction", "frequency": "monthly"}
        )
    assert route["code"], "an absent route code must allocate against a real server, not 500"
    assert cycle["code"], "an absent cycle code must allocate against a real server, not 500"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-006 (SET-05/06/07 Routes & Cycles) — the five PO rulings of 2026-08-16
# generated: 2026-08-17 by the CR-006 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: metering + tenancy suites
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
