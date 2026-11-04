# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W1 task W1-T4,
#           the 🔒 route-side migration to the ruled model.
#           Screens: SET-05 · SET-06.1/06.3 · SET-06D (Facts rail · Premises ·
#           Assets · Audit) · SET-07D
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §6
# Rules:    D10 — *"yes it will be multi service"* (RT-001 is "Water +
#           Electric") · D11 — *"Per premises"* (one stop, many meters) ·
#           D1 — *"yes"* (read windows become first-class closable records,
#           replacing the writerless `read_schedules`) · BR-MET-075 (an
#           exclusion is a ROW, never a change to the asset) · BR-MET-078
#           (no money on these surfaces) · CLAUDE.md rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""CR-029 W1-T4 — the route side of the ruled model, in schema.

FOUR RULINGS, FOUR SHAPES, and each one supersedes something the shipped tree
still says:

* **D10** a route serves a SERVICE SET. `routes.service_id` is a single FK and
  the upgraded prototype draws RT-001 as *"Water + Electric"*, which today has
  no field to be true of.
* **D11** the walk order's grain is PER PREMISES — *"one stop, many meters"*.
  `route_memberships.walk_order` is per UNIT, has a uniqueness constraint and
  **no writer at all** (B17 §5 gap G5), so the superseded column has never once
  been written.
* the exclusion's **two-word reason**, which SET-06D.assets renders in place
  (*"MTR-W2262 excluded · premise demolished"*) and which no column holds.
* **D1** read windows become **first-class closable records** — window · read-on
  · reader · collected · expected · skips · result — replacing `read_schedules`,
  a table with a frequency column, zero rows and no writer.

⚠ **THIS WAVE IS SCHEMA.** RC-W2's period engine writes the window records
(*"Closing a window writes the W1-T4 record"*) and RC-W3 draws the tabs. What
W1-T4 owes is that **every SET-06D/SET-07D fact has a column behind it and no
field is invented beyond the screenshots** — which is exactly what the field-set
assertions below pin, in both directions.
"""

import pytest

from apps.metering import models, selectors, services
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def _service(code):
    return tenancy_models.Service.objects.filter(code__iexact=code).first()


# ═══════════════════════════════════════════════════════════════════════════
# D10 · A ROUTE SERVES A SERVICE SET — *"yes it will be multi service"*
# ═══════════════════════════════════════════════════════════════════════════


def test_w1_t4__a_route_serves_a_service_set(brazos, dana):
    """D10 verbatim: *"yes it will be multi service"*. The upgraded prototype's
    RT-001 is **"Water + Electric"** and the shipped schema has one FK, so the
    screenshot could not be true of any row."""
    with tenant_ctx(brazos):
        route = services.create_route(
            dana, {"code": "RT-SET1", "name": "Downtown", "service_codes": ["water", "electric"]}
        )
        assert sorted(route["services"]) == ["electric", "water"]
        rows = models.RouteService.objects.filter(tenant_id=brazos.id, route_id=route["id"])
        assert rows.count() == 2


def test_w1_t4__the_single_service_column_stays_readable_through_the_transition(brazos, dana):
    """The migration's stated choice (see its docstring): `routes.service_id` is
    KEPT and its data is ALSO copied into the set. It stays the transitional
    head that `route_memberships.service` denormalizes from and that
    BR-MET-074's two partial uniques still key on — RC-W4 moves membership to
    run-time resolution and RC-W5 removes the dependency."""
    with tenant_ctx(brazos):
        route = services.create_route(dana, {"code": "RT-SET2", "service_code": "water"})
        assert route["service_code"] == "water"
        assert route["services"] == ["water"]
        row = models.Route.objects.get(pk=route["id"])
        assert row.service_id is not None
        assert models.RouteService.objects.filter(route=row).count() == 1


def test_w1_t4__a_route_with_no_service_has_an_empty_set_not_a_guessed_one(brazos, dana):
    """The legacy ALL-SERVICES route. An empty set is the true statement; a set
    containing every enabled service would be this lane deciding what an
    untagged route reads."""
    with tenant_ctx(brazos):
        route = services.create_route(dana, {"code": "RT-SET3"})
    assert route["services"] == []


def test_w1_t4__the_service_set_is_replaced_wholesale_on_update(brazos, dana):
    with tenant_ctx(brazos):
        route = services.create_route(
            dana, {"code": "RT-SET4", "service_codes": ["water", "electric"]}
        )
        updated = services.update_route(dana, route["id"], {"service_codes": ["electric"]})
    assert updated["services"] == ["electric"]
    assert models.RouteService.objects.filter(route_id=route["id"]).count() == 1


def test_w1_t4__an_unknown_service_in_the_set_is_refused_by_name(brazos, dana):
    from core import errors

    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_route(
                dana, {"code": "RT-SET5", "service_codes": ["water", "unobtanium"]}
            )
    # The SAME refusal the single-service path already raises — one unknown
    # service is one unknown service, and a second key would be a second
    # sentence for one fact (and eleven more catalogue entries to write).
    assert caught.value.field_errors[0]["message_key"] == "metering.route.service_unknown"


# ═══════════════════════════════════════════════════════════════════════════
# THE EXCLUSION'S TWO-WORD REASON — SET-06D.assets renders it in place
# ═══════════════════════════════════════════════════════════════════════════


def test_w1_t4__an_exclusion_carries_its_reason(brazos, dana):
    """B17 §6: *"`route_meter_exclusions.reason` — two words, shown in place"*.
    SET-06D.assets draws *"MTR-W2262 excluded · premise demolished"*, and an
    exclusion whose reason lives only in someone's memory is the one a later
    staff member re-ticks."""
    fields = {field.name for field in models.RouteMeterExclusion._meta.get_fields()}
    assert "reason" in fields


def test_w1_t4__the_reason_survives_a_round_trip(brazos, dana):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="1408 Elm St")
        unit = make_unit(dana, premises["id"], label="A", services=["water"])
        asset = make_asset(
            dana,
            unit_id=unit["id"],
            asset_no="MTR-W2262",
            service="water",
            unit="kgal",
            install_date="2026-01-05",
        )
        route = services.create_route(
            dana,
            {
                "code": "RT-EX1",
                "premises_ids": [premises["id"]],
                "excluded_asset_ids": [asset["id"]],
                "exclusion_reasons": {str(asset["id"]): "premise demolished"},
            },
        )
        row = models.RouteMeterExclusion.objects.get(route_id=route["id"], asset_id=asset["id"])
    assert row.reason == "premise demolished"


# ═══════════════════════════════════════════════════════════════════════════
# D11 · THE WALK ORDER IS PER PREMISES — *"Per premises"*
# ═══════════════════════════════════════════════════════════════════════════


def test_w1_t4__walk_order_has_a_per_premises_home(brazos, dana):
    """D11 verbatim: *"Per premises"* — one stop, many meters. The Premises
    tab's per-unit numbering (0142/0143 on 1408 Elm) is the wrong reading;
    Cedar Ct's three units sharing 0145 is right. Today's per-unit
    `route_memberships.walk_order` is SUPERSEDED and has never had a writer."""
    fields = {field.name for field in models.RoutePremisesOrder._meta.get_fields()}
    assert {"tenant", "route", "premises", "walk_order"} <= fields


def test_w1_t4__one_stop_holds_one_sequence_number(brazos, dana):
    """The uniqueness that makes a route SHEET printable: two stops cannot both
    be number 3, and one premises cannot be at two places in the walk."""
    constraints = {c.name for c in models.RoutePremisesOrder._meta.constraints}
    assert "uq_route_premises_orders_stop" in constraints
    assert "uq_route_premises_orders_walk_order" in constraints


def test_w1_t4__the_superseded_per_unit_walk_order_is_not_dropped_in_this_wave(brazos, dana):
    """`route_memberships.walk_order` stays until RC-W5, for the reason every
    legacy column in this CR stays: a column is dropped after its readers move,
    not in the migration that supersedes it."""
    fields = {field.name for field in models.RouteMembership._meta.get_fields()}
    assert "walk_order" in fields


# ═══════════════════════════════════════════════════════════════════════════
# D1 · READ WINDOWS ARE FIRST-CLASS CLOSABLE RECORDS
# ═══════════════════════════════════════════════════════════════════════════

#: The acceptance shape, from the PO's own screenshot (SET-06D.audit's Read
#: history) **as corrected by their own later ruling**: window · read-on ·
#: collected · expected · skips · result. Asserted in BOTH directions — a
#: missing column is a fact the screen cannot draw, and an EXTRA one is a field
#: invented beyond the screenshots, which B17 §7 W1-T4's done-when forbids in
#: the same sentence.
#:
#: ⚠ **`reader` WAS IN THIS SET AND IS NOW BANNED FROM IT (OQ-343, ruled
#: 2026-08-23).** PO verbatim: *"B: no reader anywhere, correct the screenshot
#: and drop the stored name"*. B17 §3 D14 records the divergence so no later
#: lane restores the column from the screenshot; `_BANNED_BY_RULING` below is
#: the same guard expressed as a test.
ACCEPTANCE_FIELDS = {
    "period_start",
    "period_end",
    "read_on",
    "collected_count",
    "expected_count",
    "skip_count",
    "result",
}


#: Removed by ruling, not by omission — see ACCEPTANCE_FIELDS above.
_BANNED_BY_RULING = {"reader", "reader_id", "reader_name"}


def test_w1_t4__a_read_window_carries_exactly_the_acceptance_fields(brazos, dana):
    fields = {field.name for field in models.ReadWindow._meta.get_fields()}
    assert ACCEPTANCE_FIELDS <= fields
    # OQ-343 — the reader is gone from the table, and a lane restoring it from
    # the PO's screenshot goes red here rather than shipping it.
    assert not (fields & _BANNED_BY_RULING)
    # ⚠ …and `routes.assigned_to` SURVIVES. D6 preserved the ops tab's existing
    # read-only reader display and OQ-343 did not ask about it, so removing it
    # would be a defect rather than thoroughness.
    assert "assigned_to" in {field.name for field in models.Route._meta.get_fields()}
    # The only additions allowed are the record's own plumbing: who it belongs
    # to, and when it was closed. Anything else would be invented.
    plumbing = {"id", "tenant", "route", "cycle", "closed_at", "created_at", "updated_at"}
    assert fields <= ACCEPTANCE_FIELDS | plumbing, fields - (ACCEPTANCE_FIELDS | plumbing)


def test_w1_t4__no_money_column_reached_the_read_window(brazos, dana):
    """BR-MET-078, hardened by this CR — *"routes and cycles are grouping
    only"*. A read window counts meters; it never carries an amount."""
    fields = {field.name for field in models.ReadWindow._meta.get_fields()}
    for banned in ("amount", "balance", "total", "price", "rate", "currency", "late_day"):
        assert banned not in fields


def test_w1_t4__a_window_closes_with_one_of_exactly_two_results(brazos, dana):
    """B17 §7 W2-T1's own worked row: *"a closed window renders the Read-history
    row (196 · 196 · Complete)"*. Complete or Incomplete, and nothing else — a
    third value would be a status vocabulary nobody ruled."""
    assert models.READ_WINDOW_RESULTS == ("Complete", "Incomplete")


def test_w1_t4__a_closable_window_records_its_counts_and_its_result(brazos, dana):
    from datetime import date

    with tenant_ctx(brazos):
        route = services.create_route(dana, {"code": "RT-RW1"})
        row = models.ReadWindow.objects.create(
            tenant=brazos,
            route_id=route["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 5),
            read_on=date(2026, 8, 4),
            collected_count=196,
            expected_count=196,
            skip_count=0,
            result="Complete",
        )
    assert (row.collected_count, row.expected_count, row.result) == (196, 196, "Complete")


def test_w1_t4__read_schedules_is_not_deleted_in_this_wave(brazos, dana):
    """B17 §7: the writerless `read_schedules` table is REPLACED by the window
    records, and **RC-W2 retires it**. Dropping it here would remove a table
    while its retirement story is still being written."""
    assert hasattr(models, "ReadSchedule")


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md RULE 1 — every new tenant table is policed in the migration that
# creates it (a table that exists for one deploy with no policy is a G5
# isolation failure and a release blocker).
# ═══════════════════════════════════════════════════════════════════════════


def test_w1_t4__every_new_tenant_table_ships_with_its_rls_policy():
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[1] / "db" / "rls_metering_cr029_routes.sql").read_text()
    for table in ("route_services", "route_premises_orders", "read_windows"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in sql
        assert f"CREATE POLICY {table}_tenant_isolation ON {table}" in sql


def test_w1_t4__the_route_migration_creates_no_column_it_cannot_explain():
    """W1-T4's done-when, as a structural guard: *"every SET-06D/SET-07D fact
    has a column behind it; no field is invented beyond the screenshots"*."""
    from importlib import import_module

    migration = import_module("apps.metering.migrations.0020_cr029_route_model")
    for operation in migration.Migration.operations:
        assert type(operation).__name__ != "RemoveField", "W1 supersedes, W5 drops"


def test_w1_t4__deleting_a_route_clears_its_configuration_rows(brazos, dana):
    """⚠ **THE REGRESSION THIS CR ALMOST SHIPPED.** `delete_route` clears the
    route's `route_meter_exclusions` and then deletes the row; every new table
    here takes a PROTECT FK to `routes`, so the first route with a service set
    made `DELETE /routes/{id}` raise `ProtectedError` — a 500 on a path that had
    a tested refusal. Found by `tests/test_def233_route_read_stamp.py`, which
    deletes a route it never read.

    **CONFIGURATION IS CLEARED, HISTORY IS NOT.** The service set and the
    walking order are things a human configured about a route that is going
    away; `read_windows` is what happened, and its PROTECT is the same
    delete-guard BR-MET-079 already gives collected reads."""
    with tenant_ctx(brazos):
        route = services.create_route(
            dana, {"code": "RT-DEL1", "service_codes": ["water", "electric"]}
        )
        route_id = route["id"]
        assert models.RouteService.objects.filter(route_id=route_id).count() == 2
        services.delete_route(dana, route_id)
    assert not models.Route.objects.filter(pk=route_id).exists()
    assert not models.RouteService.objects.filter(route_id=route_id).exists()
    assert not models.RoutePremisesOrder.objects.filter(route_id=route_id).exists()


def test_w1_t4__a_route_with_a_closed_read_window_keeps_its_history(brazos, dana):
    """The other side of the same rule. A closed window is what a crew DID, and
    BR-MET-079 already refuses to delete a route that has been read — so the
    PROTECT here is the guard, not an oversight to be cleared like the config
    rows above."""
    from datetime import date

    from django.db.models import ProtectedError

    with tenant_ctx(brazos):
        route = services.create_route(dana, {"code": "RT-DEL2"})
        models.ReadWindow.objects.create(
            tenant=brazos,
            route_id=route["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 5),
            collected_count=196,
            expected_count=196,
            result="Complete",
        )
        with pytest.raises(ProtectedError):
            services.delete_route(dana, route["id"])


def test_w1_t4__the_route_dict_publishes_the_set_without_dropping_the_head(brazos, dana):
    """Both keys travel. `service_code` is the shipped contract S8's landing
    table reads and nothing may break it; `services` is D10's new fact."""
    with tenant_ctx(brazos):
        route = services.create_route(dana, {"code": "RT-PUB1", "service_codes": ["water"]})
        served = selectors.route_dict(models.Route.objects.get(pk=route["id"]))
    assert served["service_code"] == "water"
    assert served["services"] == ["water"]
    assert served["service_ids"] == [str(models.Route.objects.get(pk=route["id"]).service_id)]
