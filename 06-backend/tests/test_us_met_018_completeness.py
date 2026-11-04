# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-018 (cycle completeness bar + chase list) · US-MET-019
#           (the S25 Missing chip) · US-MET-012 (Pending derivation)
#           Screens: S25 · S27 · S28 (batch review coverage)
# Rules:    BR-MET-057 (cycle read-window drives expectations; per-cycle
#           completeness bar + chase list) · BR-MET-049 (plan-driven required
#           set; completeness % = collected ÷ expected) · BR-MET-016/053
#           (lineage heads count once — TC-7) · BR-MET-011 (derived, never
#           stored) · CLAUDE.md rule 1 (tenant scoping — TC-8)
# TCs:      US-MET-018 TC-1 (figures reconcile) · TC-2 (chase row shape/order)
#           · TC-5 (no plan → no expectation, no chase row) · TC-6 (before
#           window open: nothing counted, "window opens <date>") · TC-7
#           (superseded chains count once) · TC-8 (isolation) — scaled to
#           unit-test size, same shapes as the §4 seed
# CR:       CR-038 W1 (backend of plan-driven read completeness)
# ───────────────────────────────────────────────────────
"""US-MET-018 surfaces — coverage, chase list, Missing chip, Pending status.

BR-MET-057, verbatim: "Cycle read-window drives expectations; per-cycle
completeness bar + chase list" (CONFIRMED — PO RD-15). The §4 seed's 762-record
fixture is scaled to unit-test size; every asserted SHAPE (records not meters,
window scoping, heads-once, no-plan-no-expectation, tenant isolation) is the
story's own TC, cited per test.
"""

from datetime import date

import pytest

from apps.metering import api, completeness, models, selectors, services

from tests.test_us_met_018_plan_registers import (  # noqa: F401 — same fixture world
    plan_with_version,
    planned_meter,
)
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    FakeUser,
    a_meter,
    api_call,
    commit_read,
    csv_body,
    lonestarridge_payload,
    make_premises,
    make_unit,
    provisioned_tenant,
    seed_config,
    staff_actor,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


AUG = date(2026, 8, 1)  # the §4 seed's reading month — window Aug 1–5


def seed_cycle_row(tenant, code="08-A", *, start_day=1, days_to_complete=5, status="active"):
    """A cycle DEFINITION written directly — fixture data on metering's own
    table (the `commit_read` posture: the past a test starts from, not the
    behaviour under test; `services.create_cycle`'s wizard validation is
    US-MET-006's business and is proven there)."""
    return models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        frequency="Monthly",
        start_day=start_day,
        days_to_complete=days_to_complete,
        bill_day=31,
        status=status,
    )


def routed_meters(
    actor,
    tenant,
    cycle,
    plan,
    *,
    asset_no="M-7451",
    route_code="Route 3",
    service="electric",
    uom="kWh",
):
    """One premises/unit/meter on a route in the cycle, holding `plan`."""
    unit, asset = planned_meter(
        actor,
        tenant,
        plan,
        asset_no=asset_no,
        label=f"Unit {asset_no}",
        service=service,
        uom=uom,
    )
    premises_id = str(models.Unit.objects.get(pk=unit["id"]).premises_id)
    route = services.create_route(
        actor,
        {"code": route_code, "cycle_id": str(cycle.id), "premises_ids": [premises_id]},
    )
    return unit, asset, route


def coverage_for(cycle, *, period=AUG, today=date(2026, 8, 4)):
    """The §4 seed's viewpoint: reading month Aug, viewed Aug 4 (in-window)."""
    return completeness.cycle_coverage(cycle, period_anchor=period, today=today)


# ── TC-1 · the figures reconcile (records, not meters) ──────────────────────


def test_us_met_018_tc1__expected_collected_and_completeness_reconcile(brazos, dana):
    """US-MET-018 §2: expected = Σ plan-driven required channel records over
    the cycle's route-member units; completeness % = collected ÷ expected.
    One flat meter (1 record) + one TOU meter (4) = 5 expected; the flat total
    and one TOU window committed = 2 collected → 40.0%."""
    with tenant_ctx(brazos):
        cycle = seed_cycle_row(brazos)
        flat_plan = plan_with_version(brazos, name="Flat Residential", model="flat")
        tou_plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        _unit_f, flat_meter, _ = routed_meters(
            dana, brazos, cycle, flat_plan, asset_no="M-7001", route_code="Route 1"
        )
        _unit_t, tou_meter, _ = routed_meters(
            dana, brazos, cycle, tou_plan, asset_no="M-7451", route_code="Route 2"
        )
        commit_read(dana, flat_meter["id"], day="2026-08-03", value="42864")
        commit_read(dana, tou_meter["id"], day="2026-08-03", value="400", channel="tou_on")

        coverage = coverage_for(cycle)

    assert coverage["window"] == {
        "period_start": "2026-08-01",
        "period_end": "2026-08-05",
        "state": "open",
    }
    assert coverage["expected_records"] == 5  # 1 flat + (3 windows + total)
    assert coverage["collected_records"] == 2
    assert coverage["missing_records"] == 3
    assert coverage["completeness_pct"] == "40.0"
    assert coverage["expected_meters"] == 2
    assert coverage["pending_meters"] == 1  # the TOU meter still owes records
    assert coverage["days_left"] == 1  # window ends Aug 5, viewed Aug 4 (TC-2)


# ── TC-2 · the chase list rows, shaped and ordered ──────────────────────────


def test_us_met_018_tc2__chase_list_names_the_missing_channels_per_meter(brazos, dana):
    """TC-2's row: Unit · Premise · Meter · Route · Service · Missing channels
    · Days left — the §4 shape ("Unit 3F · Cane Island Apts · M-7451 · Route 3
    · E · tou_on, tou_mid, tou_off, total · 1 day"), ordered days-left asc
    then unit label."""
    with tenant_ctx(brazos):
        cycle = seed_cycle_row(brazos)
        tou_plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        flat_plan = plan_with_version(brazos, name="Flat Residential", model="flat")
        routed_meters(dana, brazos, cycle, tou_plan, asset_no="M-7451", route_code="Route 3")
        _u, flat_meter, _r = routed_meters(
            dana, brazos, cycle, flat_plan, asset_no="M-7612", route_code="Route 1"
        )
        # The flat meter M-7612 is missing too (§4 names it) — nothing committed.

        listed = completeness.chase_list(cycle, period_anchor=AUG, today=date(2026, 8, 4))

    assert listed["count"] == 2
    by_meter = {row["meter"]: row for row in listed["rows"]}
    tou_row = by_meter["M-7451"]
    assert tou_row["unit"] == "Unit M-7451"
    assert tou_row["premises"] == "1408 Bluestem Ln M-7451"
    assert tou_row["route"] == "Route 3"
    assert tou_row["service"] == "electric"
    assert tou_row["missing_channels"] == ["total", "tou_on", "tou_mid", "tou_off"]
    assert tou_row["days_left"] == 1  # window ends Aug 5 (TC-2's "1 day")
    assert by_meter["M-7612"]["missing_channels"] == ["total"]
    # days-left asc then unit label: equal days → unit label order.
    assert [row["unit"] for row in listed["rows"]] == sorted(r["unit"] for r in listed["rows"])


def test_us_met_018_tc2b__the_chase_list_endpoint_serves_the_same_rows(brazos, dana):
    """GET /cycles/{id}/chase-list?period=2026-08 — the API door, tenant-gated,
    same figures as the computation (one derivation, two readers)."""
    with tenant_ctx(brazos):
        cycle = seed_cycle_row(brazos)
        tou_plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        routed_meters(dana, brazos, cycle, tou_plan, asset_no="M-7451", route_code="Route 3")

        response = api_call(
            api.cycle_chase_list,
            "get",
            user=FakeUser(),
            tenant=brazos,
            role="billing_clerk",
            query={"period": "2026-08"},
            cycle_id=str(cycle.id),
        )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["rows"][0]["meter"] == "M-7451"
    assert response.data["rows"][0]["missing_channels"] == [
        "total",
        "tou_on",
        "tou_mid",
        "tou_off",
    ]


# ── TC-5 · no plan → no expectation, no chase row ───────────────────────────


def test_us_met_018_tc5__a_unit_with_no_plan_contributes_nothing(brazos, dana):
    """US-MET-018 TC-5: unit 9C has a metered service but no plan → 0 expected
    records, never in the chase list (BR-MET-049 — no plan, no required set)."""
    with tenant_ctx(brazos):
        cycle = seed_cycle_row(brazos)
        routed_meters(dana, brazos, cycle, None, asset_no="M-9C01", route_code="Route 9")

        coverage = coverage_for(cycle)
        listed = completeness.chase_list(cycle, period_anchor=AUG, today=date(2026, 8, 4))

    assert coverage["expected_records"] == 0
    assert coverage["pending_meters"] == 0
    assert listed["count"] == 0
    # And it is not "unresolved" either — no plan is the RULED nothing (TC-5),
    # not a failure to answer.
    assert coverage["unresolved"] == []


def test_us_met_018__an_unresolvable_set_is_reported_beside_the_figures(brazos, dana):
    """A plan with NO version in force (BR-RAT-007) cannot state its set — the
    meter lands in `unresolved` WITH its reason, never silently in the bar."""
    with tenant_ctx(brazos):
        cycle = seed_cycle_row(brazos)
        from tests.test_us_met_helpers import make_plan

        versionless = make_plan(brazos, name="Versionless")  # schedule, no version
        routed_meters(dana, brazos, cycle, versionless, asset_no="M-7777", route_code="Route 7")

        coverage = coverage_for(cycle)

    assert coverage["expected_records"] == 0
    assert coverage["unresolved"] == [
        {
            "meter": "M-7777",
            "asset_id": coverage["unresolved"][0]["asset_id"],
            "reason": completeness.REGISTERS_ABSENT_NO_VERSION,
        }
    ]


# ── TC-6 · before window open, nothing is chased ────────────────────────────


def test_us_met_018_tc6__before_window_open_nothing_counts_and_the_opening_is_named(brazos, dana):
    """US-MET-018 TC-6: viewing a window not yet open → chase list empty with
    "window opens <date>"; nothing counted as missing (BR-MET-057)."""
    with tenant_ctx(brazos):
        cycle = seed_cycle_row(brazos, code="08-B", start_day=12)
        tou_plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        routed_meters(dana, brazos, cycle, tou_plan, asset_no="M-7451", route_code="Route 3")

        coverage = completeness.cycle_coverage(cycle, period_anchor=AUG, today=date(2026, 8, 4))
        listed = completeness.chase_list(cycle, period_anchor=AUG, today=date(2026, 8, 4))

    assert coverage["window"]["state"] == "before_open"
    assert coverage["window_opens"] == "2026-08-12"
    assert coverage["expected_records"] == 0
    assert coverage["missing_records"] == 0
    assert listed["count"] == 0 and listed["rows"] == []
    assert listed["window_opens"] == "2026-08-12"


# ── TC-7 · superseded chains count once ─────────────────────────────────────


def test_us_met_018_tc7__collected_counts_lineage_heads_exactly_once(brazos, dana):
    """US-MET-018 TC-7: a superseded read and its replacement count once —
    collected resolves HEADS only (BR-MET-016/053)."""
    from django.utils import timezone as dj_tz

    with tenant_ctx(brazos):
        cycle = seed_cycle_row(brazos)
        flat_plan = plan_with_version(brazos, name="Flat Residential", model="flat")
        _u, meter, _r = routed_meters(
            dana, brazos, cycle, flat_plan, asset_no="M-7001", route_code="Route 1"
        )
        v1 = commit_read(dana, meter["id"], day="2026-08-03", value="42860")
        v2 = commit_read(dana, meter["id"], day="2026-08-04", value="42864")
        v1.superseded_by_id = v2.id  # bare uuid, not a self-FK (partitioned table)
        v1.superseded_at = dj_tz.now()
        v1.save(update_fields=["superseded_by_id", "superseded_at"])

        coverage = coverage_for(cycle)

    assert coverage["expected_records"] == 1
    assert coverage["collected_records"] == 1  # the chain counts ONCE
    assert coverage["completeness_pct"] == "100.0"


# ── the batch review coverage (item 3) ──────────────────────────────────────


def test_us_met_018__validate_summary_carries_the_cycle_coverage(brazos, dana):
    """The S28 review step: expected meters from the cycle, received in THIS
    batch, and what posting would still leave missing (batches APPEND per
    cycle — BR-MET-054 — so committed heads count too)."""
    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle_row(brazos)
        flat_plan = plan_with_version(brazos, name="Flat Residential", model="flat")
        routed_meters(dana, brazos, cycle, flat_plan, asset_no="M-7001", route_code="Route 1")
        routed_meters(dana, brazos, cycle, flat_plan, asset_no="M-7612", route_code="Route 2")

        batch = stage(dana, csv_body("M-7001,2026-08-03,42864,total"), cycle_id=str(cycle.id))
        summary = services.validate_read_batch(dana, batch["id"])

    coverage = summary["cycle_coverage"]
    assert coverage["cycle_code"] == "08-A"
    assert coverage["window"] == {"period_start": "2026-08-01", "period_end": "2026-08-05"}
    assert coverage["expected_meters"] == 2
    assert coverage["received_in_batch"] == 1
    assert coverage["missing_after_batch"] == 1
    assert coverage["missing_meter_nos"] == ["M-7612"]
    assert coverage["missing_truncated"] is False


def test_us_met_018__a_cycleless_batch_states_the_absence(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        a_meter(dana, "M-7001")
        batch = stage(dana, csv_body("M-7001,2026-08-03,42864,total"))
        summary = services.validate_read_batch(dana, batch["id"])
    assert summary["cycle_coverage"] is None
    assert summary["cycle_coverage_absent_reason"] == "batch_not_tagged_with_cycle"


# ── the Missing chip (item 5) and Pending (item 6) ──────────────────────────


def month_long_cycle(tenant, code="NOW"):
    """A cycle whose window is open on ANY real today (start day 1, 31 days to
    complete — OQ-341 allows a window longer than its repeat, warned not
    refused), so the chip/pending tests are deterministic on the wall clock
    the tenant-today seam reads."""
    return seed_cycle_row(tenant, code=code, start_day=1, days_to_complete=31)


def test_us_met_019__the_missing_chip_serves_the_real_record_count(brazos, dana):
    """US-MET-019 §5: Missing = expected required records − collected heads,
    open window only — RECORDS, not bare meters. The null-with-reason payload
    this chip served since W2 is gone."""
    from apps.metering import seams

    with tenant_ctx(brazos):
        cycle = month_long_cycle(brazos)
        tou_plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        _u, meter, _r = routed_meters(
            dana, brazos, cycle, tou_plan, asset_no="M-7451", route_code="Route 3"
        )
        commit_read(dana, meter["id"], day=str(seams.tenant_today()), value="400", channel="tou_on")

        counts = selectors.needs_attention_counts()

    assert counts["missing"] == 3  # total + tou_mid + tou_off still owed
    assert counts["missing_unresolved_meters"] == 0
    assert "missing_unavailable_reason" not in counts


def test_us_met_019__a_cycle_whose_window_has_not_opened_adds_nothing(brazos, dana):
    """BR-MET-057 window-scoping on the chip: before open there is nothing to
    chase (US-MET-018 TC-6's rule, applied to the roll-up)."""
    from apps.metering import seams

    with tenant_ctx(brazos):
        today = seams.tenant_today()
        future_start = today.day + 2
        if future_start > 28:
            pytest.skip("month-end wall-clock window — the anchor day would clamp")
        cycle = seed_cycle_row(brazos, code="LATER", start_day=future_start, days_to_complete=3)
        tou_plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        routed_meters(dana, brazos, cycle, tou_plan, asset_no="M-7451", route_code="Route 3")

        counts = selectors.needs_attention_counts()

    assert counts["missing"] == 0


def test_us_met_012__pending_is_served_as_a_derived_status_filter(brazos, dana):
    """US-MET-012 §1, verbatim: "Pending = plan-required record (meter ×
    channel, BR-MET-049) with no committed read this cycle — derived, not
    stored." GET /reads?f.status=pending serves one id-less entry per missing
    record; a stored-status filter would have returned an empty page."""
    from apps.metering import seams

    with tenant_ctx(brazos):
        cycle = month_long_cycle(brazos)
        tou_plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        _u, meter, _r = routed_meters(
            dana, brazos, cycle, tou_plan, asset_no="M-7451", route_code="Route 3"
        )
        commit_read(dana, meter["id"], day=str(seams.tenant_today()), value="400", channel="tou_on")

        response = api_call(
            api.reads,
            "get",
            user=FakeUser(),
            tenant=brazos,
            role="billing_clerk",
            query={"f.status": "pending"},
        )

    assert response.status_code == 200
    rows = response.data["results"]
    assert [row["channel"] for row in rows] == ["total", "tou_mid", "tou_off"]
    for row in rows:
        assert row["status"] == "pending"
        assert row["id"] is None  # nothing exists to address
        assert row["derived"] == "pending"  # not stored — BR-MET-049/US-MET-012
        assert row["meter"] == "M-7451"
    # The channel filter narrows the derived entries like any declared filter.
    with tenant_ctx(brazos):
        narrowed = api_call(
            api.reads,
            "get",
            user=FakeUser(),
            tenant=brazos,
            role="billing_clerk",
            query={"f.status": "pending", "f.channel": "tou_off"},
        )
    assert [row["channel"] for row in narrowed.data["results"]] == ["tou_off"]


# ── TC-8 · isolation ────────────────────────────────────────────────────────


def test_us_met_018_tc8__colliding_cycle_codes_stay_tenant_scoped(brazos, dana):
    """US-MET-018 TC-8: Lone Star Ridge opens its own cycle 08-A (code
    collision) — expectations, counts and chase rows computed only from the
    asking tenant's units/plans/reads; no Brazos Bend id appears."""
    lonestar, _result = provisioned_tenant(lonestarridge_payload())
    okafor = staff_actor(lonestar, "system_admin", "j.okafor@lonestarridge.test")

    with tenant_ctx(brazos):
        brazos_cycle = seed_cycle_row(brazos)  # 08-A
        tou_plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        routed_meters(dana, brazos, brazos_cycle, tou_plan, asset_no="M-7451")

    with tenant_ctx(lonestar):
        lonestar_cycle = seed_cycle_row(lonestar)  # the SAME code 08-A
        flat_plan = plan_with_version(
            lonestar, name="LSR Flat", model="flat", service_code="water", uom="kgal"
        )
        routed_meters(
            okafor,
            lonestar,
            lonestar_cycle,
            flat_plan,
            asset_no="LSR-01",
            service="water",
            uom="kgal",
        )

        listed = completeness.chase_list(lonestar_cycle, period_anchor=AUG, today=date(2026, 8, 4))

    assert listed["count"] == 1
    assert listed["rows"][0]["meter"] == "LSR-01"
    assert all("M-7451" != row["meter"] for row in listed["rows"])
    # And Brazos Bend's own view never counts Lone Star Ridge's meter.
    with tenant_ctx(brazos):
        brazos_listed = completeness.chase_list(
            brazos_cycle, period_anchor=AUG, today=date(2026, 8, 4)
        )
    assert {row["meter"] for row in brazos_listed["rows"]} == {"M-7451"}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-018@EP-MET-03 (story §3 TCs, scaled) · US-MET-019/012 chip and
#         Pending clauses · CR-038 W1 task list
# generated: 2026-08-26 by the CR-038 W1 backend lane
# checklist: C✔ — TC-1/2/5/6/7/8 written from §3 BEFORE the surfaces were
#            wired (r11 step 2c: cases from the story, never after the code)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
